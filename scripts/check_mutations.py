"""Targeted falsification in isolated source copies; never patches the live project."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    ("arithmetic-right-shift", "solver.py", "return z3.LShR(a, b)", "return a >> b",
     "test_solver.SolverTests.test_symbolic_lowering_against_concrete_exhaustive_operator_tables"),
    ("missing-intermediate-wrap", "evaluate.py", "result &= mask", "result = int(result)",
     "test_language.LanguageTests.test_wrap_at_every_node"),
    ("signed-range-constraints", "solver.py", "solver.add(z3.UGE(symbols[name], low), z3.ULE(symbols[name], high))",
     "solver.add(symbols[name] >= low, symbols[name] <= high)",
     "test_solver.SolverTests.test_overflow_mean_has_replayed_witness"),
    ("unknown-as-equivalent", "solver.py", 'report["reason"] = solver.reason_unknown() or "Z3 returned unknown."',
     'report["status"] = "equivalent"; report["reason"] = solver.reason_unknown() or "Z3 returned unknown."',
     "test_solver.SolverTests.test_actual_resource_limit_has_unknown_outcome"),
    ("replay-gate-disabled", "solver.py", 'if (lvalue["value"] == rvalue["value"] or',
     'if False and (lvalue["value"] == rvalue["value"] or',
     "test_solver.SolverTests.test_replay_disagreement_is_not_a_counterexample_claim"),
    ("booleans-as-integers", "language.py", "if type(value) is not int or not low <= value <= high:",
     "if not isinstance(value, int) or not low <= value <= high:",
     "test_language.LanguageTests.test_strict_schema"),
    ("stdout-failure-as-counterexample", "cli.py", '        return 3\n    return EXIT_CODES[report["status"]]',
     '        return 1\n    return EXIT_CODES[report["status"]]',
     "test_cli.CliTests.test_real_broken_pipe_is_not_reported_as_counterexample"),
]


def caught(returncode, output, test):
    name = test.rsplit(".", 1)[-1]
    # A crash, ImportError, output encoding failure or a different failing test is not evidence.
    named = re.search(r"^FAIL: " + re.escape(name) + r"(?:\s|\()", output, flags=re.M)
    return returncode == 1 and bool(named) and "AssertionError" in output and "\nERROR:" not in output


def self_test():
    t = "m.C.test_real"
    good = "\nFAIL: test_real (m.C.test_real)\nAssertionError: expected\n"
    controls = [(1, good, True), (0, good, False), (2, good, False),
                (1, "Traceback: SyntaxError", False), (1, good.replace("test_real", "test_other"), False),
                (1, good + "\nERROR: test_another\nImportError", False)]
    for code, output, expected in controls:
        if caught(code, output, t) is not expected:
            raise AssertionError("mutation classifier self-test failed")
    return len(controls)


def run_tests(folder, names):
    env = dict(os.environ, PYTHONPATH=str(folder / "src") + os.pathsep + str(folder / "tests"), PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, "-m", "unittest", "-v", *names], cwd=folder, env=env,
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    controls = self_test()
    if args.self_test:
        print(json.dumps({"classifier_controls": controls, "status": "passed"}))
        return 0
    sources = {p.name: p.read_text("utf-8") for p in (ROOT / "src" / "bitequiv").glob("*.py")}
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT / "src" / "bitequiv").glob("*.py")}
    baseline = run_tests(ROOT, list(dict.fromkeys(c[4] for c in CASES)))
    if baseline.returncode != 0:
        print(baseline.stdout + baseline.stderr)
        print("BASELINE_FAILED: mutation evidence is invalid")
        return 1
    records = []
    for name, filename, old, new, test in CASES:
        source = sources[filename]
        if source.count(old) != 1 or old == new:
            raise AssertionError(f"{name}: mutation anchor is not unique or unchanged")
        mutated = source.replace(old, new, 1)
        if mutated == source:
            raise AssertionError(f"{name}: mutation was a no-op")
        with tempfile.TemporaryDirectory(prefix="bitequiv-mutation-") as tmp:
            folder = Path(tmp)
            shutil.copytree(ROOT / "src", folder / "src", ignore=shutil.ignore_patterns("__pycache__", "*.egg-info"))
            shutil.copytree(ROOT / "tests", folder / "tests", ignore=shutil.ignore_patterns("__pycache__"))
            path = folder / "src" / "bitequiv" / filename
            with path.open("w", encoding="utf-8", newline="\n") as stream:
                stream.write(mutated)
            run = run_tests(folder, [test])
            detected = caught(run.returncode, run.stdout + run.stderr, test)
            record = dict(name=name, caught=detected, assertion=test, returncode=run.returncode)
            records.append(record)
            print(json.dumps(record), flush=True)
            if not detected:
                print(run.stdout + run.stderr, flush=True)
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT / "src" / "bitequiv").glob("*.py")}
    unchanged = before == after
    total = sum(item["caught"] is True for item in records)
    print(json.dumps(dict(caught=total, total=len(records), source_unchanged=unchanged,
                          classifier_controls=controls, source_sha256=before), indent=2))
    return 0 if total == len(records) and unchanged else 1


if __name__ == "__main__":
    raise SystemExit(main())
