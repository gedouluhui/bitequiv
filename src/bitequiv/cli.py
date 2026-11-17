"""CLI boundaries: bounded reads, command-specific outcomes, no file overwrites."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

from .evidence import MAX_REPORT_BYTES, parse_report, replay_report
from .language import InvalidProblem, MAX_INPUT_BYTES, parse_json
from .report import render_html
from .smtlib import export_smt2
from .solver import check

EXIT_CODES = {"equivalent": 0, "different": 1, "unknown": 2, "invalid": 3}
REPLAY_CODES = {"verified_counterexample": 0, "mismatch": 1, "unverifiable": 2, "invalid": 3}


class _HelpExit(Exception):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise InvalidProblem(message)

    def _print_message(self, message, file=None):
        if message:
            stream = file if file is not None else sys.stdout
            stream.write(message)
            stream.flush()

    def exit(self, status=0, message=None):
        if status:
            raise InvalidProblem(message or "argument parsing failed")
        raise _HelpExit()


def _save_outputs(items, input_path):
    # Multiple files are not a transaction; a later I/O failure can leave earlier outputs.
    resolved = [path.resolve() for path, _ in items]
    if len(set(resolved)) != len(resolved) or input_path.resolve() in resolved:
        raise InvalidProblem("output paths must be distinct and must not name the input")
    for path, _ in items:
        if path.exists() or path.is_symlink():
            raise InvalidProblem(f"refusing to overwrite existing output: {path.name}")
        if not path.parent.is_dir():
            raise InvalidProblem(f"output parent directory does not exist: {path.parent.name}")
    for path, content in items:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(content)


def _silence_failed_stream(stream):
    # Prevent interpreter shutdown from re-flushing a failed descriptor and changing rc.
    try:
        with open(os.devnull, "w") as sink:
            os.dup2(sink.fileno(), stream.fileno())
    except (OSError, AttributeError, ValueError):
        pass


def _diagnostic(message):
    try:
        print("bitequiv: " + message, file=sys.stderr)
        sys.stderr.flush()
    except OSError:
        _silence_failed_stream(sys.stderr)


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = Parser(prog="bitequiv", description="Check, export and replay fixed-width unsigned expression evidence.")
    commands = parser.add_subparsers(dest="command", required=True, parser_class=Parser)
    command = commands.add_parser("check", help="solve one JSON problem")
    command.add_argument("input", type=Path)
    command.add_argument("--json", type=Path, metavar="FILE", help="save JSON to a NEW file")
    command.add_argument("--html", type=Path, metavar="FILE", help="save an offline report to a NEW file")
    command.add_argument("--timeout-ms", type=int, default=5000)
    command.add_argument("--rlimit", type=int, default=2000000)
    export = commands.add_parser("export", help="export a standard SMT-LIB query, without solving")
    export.add_argument("input", type=Path)
    export.add_argument("--smt2", type=Path, required=True, metavar="FILE", help="write query to a NEW file")
    replay = commands.add_parser("replay", help="recompute a saved concrete counterexample, without a solver")
    replay.add_argument("input", type=Path)
    raw_args = list(sys.argv[1:] if argv is None else argv)
    result_key = "verification_status" if raw_args and raw_args[0] == "replay" else "status"
    try:
        args = parser.parse_args(raw_args)
        result_key = "verification_status" if args.command == "replay" else "status"
        limit = MAX_REPORT_BYTES if args.command == "replay" else MAX_INPUT_BYTES
        if not args.input.is_file():
            raise InvalidProblem("input must be an existing regular JSON file")
        with args.input.open("rb") as stream:
            content = stream.read(limit + 1)
        if len(content) > limit:
            raise InvalidProblem(f"input exceeds {limit} bytes")
        text = content.decode("utf-8")
        outputs = []
        if args.command == "replay":
            report = replay_report(parse_report(text))
            exit_code = REPLAY_CODES[report["verification_status"]]
        elif args.command == "export":
            problem = parse_json(text)
            query = export_smt2(problem)
            outputs.append((args.smt2, query))
            report = dict(status="exported", fingerprint=problem.fingerprint,
                          query_sha256=hashlib.sha256(query.encode("utf-8")).hexdigest(),
                          scope="Export succeeded, not a verdict. Solve this query: unsat=equivalent, sat=different, unknown=no conclusion.")
            exit_code = 0
        else:
            report = check(parse_json(text), timeout_ms=args.timeout_ms, rlimit=args.rlimit)
            exit_code = EXIT_CODES[report["status"]]
            if args.json:
                outputs.append((args.json, json.dumps(report, indent=2, ensure_ascii=True) + "\n"))
            if args.html:
                outputs.append((args.html, render_html(report)))
        _save_outputs(outputs, args.input)
    except _HelpExit:
        return 0
    except (InvalidProblem, OSError, UnicodeError) as exc:
        report = {result_key: "invalid", "reason": str(exc)}
        exit_code = 3
        _diagnostic(str(exc))
    serialized = json.dumps(report, indent=2, ensure_ascii=True) + "\n"
    try:
        sys.stdout.write(serialized)
        sys.stdout.flush()
    except OSError as exc:
        _silence_failed_stream(sys.stdout)
        _diagnostic("stdout output failed: " + str(exc))
        return 3
    return exit_code
