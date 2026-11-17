"""CLI boundary: bounded reads, explicit exit codes, non-overwriting output files."""
import argparse
import json
import os
from pathlib import Path
import sys

from .language import InvalidProblem, MAX_INPUT_BYTES, parse_json
from .report import render_html
from .solver import check

EXIT_CODES = {"equivalent": 0, "different": 1, "unknown": 2, "invalid": 3}


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise InvalidProblem(message)


def _save_outputs(items, input_path):
    # Preflight all paths before writing any. Exclusive creation closes overwrite races.
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


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = Parser(prog="bitequiv", description="Check fixed-width unsigned expressions. Local inputs, replayed counterexamples.")
    commands = parser.add_subparsers(dest="command", required=True, parser_class=Parser)
    command = commands.add_parser("check", help="check one JSON problem")
    command.add_argument("input", type=Path)
    command.add_argument("--json", type=Path, metavar="FILE", help="save JSON to a NEW file")
    command.add_argument("--html", type=Path, metavar="FILE", help="save an offline report to a NEW file")
    command.add_argument("--timeout-ms", type=int, default=5000)
    command.add_argument("--rlimit", type=int, default=2000000)
    try:
        args = parser.parse_args(argv)
        if not args.input.is_file():
            raise InvalidProblem("input must be an existing regular JSON file")
        with args.input.open("rb") as stream:
            content = stream.read(MAX_INPUT_BYTES + 1)
        if len(content) > MAX_INPUT_BYTES:
            raise InvalidProblem(f"input exceeds {MAX_INPUT_BYTES} bytes")
        p = parse_json(content.decode("utf-8"))
        report = check(p, timeout_ms=args.timeout_ms, rlimit=args.rlimit)
        serialized = json.dumps(report, indent=2, ensure_ascii=True) + "\n"
        outputs = []
        if args.json:
            outputs.append((args.json, serialized))
        if args.html:
            outputs.append((args.html, render_html(report)))
        _save_outputs(outputs, args.input)
    except (InvalidProblem, OSError, UnicodeError) as exc:
        report = dict(schema_version=1, status="invalid", reason=str(exc))
        serialized = json.dumps(report, indent=2, ensure_ascii=True) + "\n"
        print("bitequiv: " + str(exc), file=sys.stderr)
    try:
        sys.stdout.write(serialized)
        sys.stdout.flush()
    except OSError as exc:
        # Drain any remaining buffer to the null device so interpreter shutdown
        # does not retry a broken pipe and replace exit 3 with an unrelated code.
        try:
            with open(os.devnull, "w") as sink:
                os.dup2(sink.fileno(), sys.stdout.fileno())
        except (OSError, AttributeError, ValueError):
            pass
        try:
            print("bitequiv: stdout output failed: " + str(exc), file=sys.stderr)
        except OSError:
            pass
        return 3
    return EXIT_CODES[report["status"]]
