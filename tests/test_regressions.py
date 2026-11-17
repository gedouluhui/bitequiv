"""Review findings: fail for behavior, not merely a thrown exception."""
import dataclasses
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from bitequiv import Problem, check, evaluate, InvalidProblem
from bitequiv.report import render_html

ROOT = Path(__file__).resolve().parents[1]


class ReviewRegressions(unittest.TestCase):
    def test_replaced_problem_replays_the_same_expression_as_check(self):
        p = Problem.from_dict(dict(width=8, variables=["x"], left="x", right="x"))
        q = dataclasses.replace(p, left="x+1")
        self.assertEqual(check(q)["status"], "different")
        self.assertEqual(evaluate(q, "left", {"x": 0})["value"], 1)
        self.assertEqual(evaluate(q, "right", {"x": 0})["value"], 0)

    def test_duplicate_or_missing_raw_ranges_cannot_be_lost_in_serialization(self):
        from bitequiv import export_smt2
        p = Problem.from_dict(dict(width=8,variables=["x"],left="x",right="0"))
        for ranges in ((("x",1,0),("x",0,0)), (), (("x",0,0),("x",0,0)), ((None,0,0),)):
            q = dataclasses.replace(p,ranges=ranges)
            self.assertEqual(check(q)["status"], "invalid")
            with self.assertRaises(InvalidProblem): export_smt2(q)
            with self.assertRaises(InvalidProblem): evaluate(q,"left",{"x":0})

    def test_lexical_normalization_is_not_accepted_as_declared_input(self):
        for expression in ("ｘ", "𝑥", "x # +1", "x\f", "x\v"):
            with self.subTest(expression=expression):
                report = check(dict(width=8, variables=["x"], left=expression, right="x"))
                self.assertEqual(report["status"], "invalid")

    def test_report_reproduction_preserves_solver_budgets(self):
        p = dict(width=32, variables=["x"], left="x*x", right="x+1")
        r = check(p, timeout_ms=1234, rlimit=1)
        self.assertEqual(r["status"], "unknown")
        html = render_html(r)
        self.assertIn("--timeout-ms 1234 --rlimit 1", html)

    def test_broken_stderr_preserves_invalid_json_and_exit_three(self):
        code = ("import os,sys; from bitequiv.cli import main; "
                "r,w=os.pipe(); os.close(r); original=sys.stderr; sys.stderr=os.fdopen(w,'w'); "
                "result=main(['check',sys.argv[1]]); sys.stderr.close(); sys.stderr=original; "
                "raise SystemExit(result)")
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, PYTHONPATH=str(ROOT/"src"))
            result = subprocess.run([sys.executable, "-c", code, str(Path(tmp)/"missing.json")],
                                    env=env, cwd=tmp, capture_output=True, text=True, encoding="utf-8", timeout=20)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "invalid")
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
