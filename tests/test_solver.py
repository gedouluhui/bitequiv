import dataclasses
import itertools
import unittest
from unittest.mock import patch
import z3

from bitequiv.language import Problem
from bitequiv.evaluate import evaluate
from bitequiv.solver import check, to_z3


def problem(left="x", right="x", width=8, variables=None, **extra):
    return Problem.from_dict(dict(width=width, variables=["x"] if variables is None else variables,
                                  left=left, right=right, **extra))


class SolverTests(unittest.TestCase):
    def test_wrapping_identity_is_proved(self):
        report = check(problem("(x+y)<<1", "(x<<1)+(y<<1)", variables=["x", "y"]))
        self.assertEqual(report["status"], "equivalent")
        self.assertEqual(report["coverage"]["domain_assignments"], "65536")
        self.assertFalse(report["coverage"]["proof_certificate"])

    def test_overflow_mean_has_replayed_witness(self):
        p = problem("(x+y)>>1", "(x&y)+((x^y)>>1)", variables=["x", "y"])
        report = check(p)
        self.assertEqual(report["status"], "different")
        witness = report["witness"]
        self.assertTrue(witness["replayed"])
        for side in ("left", "right"):
            self.assertEqual(witness[side]["value"], evaluate(p, side, witness["assignment"])["value"])
        self.assertNotEqual(witness["left"]["value"], witness["right"]["value"])
        self.assertEqual(witness["different_bits"], [7])

    def test_precondition_changes_the_answer(self):
        p = problem("(x+y)>>1", "(x&y)+((x^y)>>1)", variables=["x", "y"],
                    ranges={"x": [0, 127], "y": [0, 127]})
        self.assertEqual(check(p)["status"], "equivalent")

    def test_unsigned_high_range(self):
        p = problem("x>>7", "1", ranges={"x": [128, 255]})
        self.assertEqual(check(p)["status"], "equivalent")
        q = problem("x>>7", "0", ranges={"x": [128, 255]})
        result = check(q)
        self.assertEqual(result["status"], "different")
        self.assertGreaterEqual(result["witness"]["assignment"]["x"], 128)

    def test_constant_problems(self):
        self.assertEqual(check(problem("-1", "255", variables=[]))["status"], "equivalent")
        result = check(problem("1", "2", variables=[]))
        self.assertEqual(result["status"], "different")
        self.assertEqual(result["witness"]["assignment"], {})

    def test_64_bit_values_remain_exact(self):
        p = problem("x>>63", "0", width=64, ranges={"x": [1 << 63, (1 << 64)-1]})
        result = check(p)
        self.assertEqual(result["status"], "different")
        self.assertEqual(result["witness"]["left"]["value"], 1)

    def test_revalidates_public_problem_instead_of_trusting_mutated_ast(self):
        p = problem("x", "x+1")
        forged = dataclasses.replace(p, left_ast=p.right_ast)
        self.assertEqual(check(forged)["status"], "different")

    def test_bad_options_and_input_are_invalid(self):
        for options in ({"timeout_ms": True}, {"timeout_ms": 0}, {"timeout_ms": 60001},
                        {"rlimit": False}, {"rlimit": 0}, {"rlimit": 20000001}):
            with self.subTest(options=options):
                self.assertEqual(check(problem(), **options)["status"], "invalid")
        self.assertEqual(check({"width": 0})["status"], "invalid")

    def test_unknown_is_not_a_proof(self):
        with patch("z3.Solver.check", return_value=z3.unknown), patch("z3.Solver.reason_unknown", return_value="controlled timeout"):
            result = check(problem("x*x", "x+1"))
        self.assertEqual(result["status"], "unknown")
        self.assertIn("controlled timeout", result["reason"])
        self.assertNotIn("witness", result)

    def test_actual_resource_limit_has_unknown_outcome(self):
        p = problem("(x*x)+(y*y)", "(x+y)*(x-y)", width=32, variables=["x", "y"])
        result = check(p, rlimit=1)
        self.assertEqual(result["status"], "unknown")
        self.assertTrue(result["reason"])

    def test_replay_disagreement_is_not_a_counterexample_claim(self):
        with patch("bitequiv.solver.evaluate", return_value={"value": 0, "steps": []}):
            result = check(problem("x", "x+1"))
        self.assertEqual(result["status"], "unknown")
        self.assertIn("replay", result["reason"].lower())
        self.assertNotIn("witness", result)

    def test_symbolic_lowering_against_concrete_exhaustive_operator_tables(self):
        # Separately exercise EVERY operator result, not just an equality verdict.
        expressions = ["x+y", "x-y", "x*y", "x&y", "x|y", "x^y", "x<<y", "x>>y",
                       "~x", "-x", "+x", "(x+y)>>1"]
        for width in (1, 2, 3, 4):
            for expression in expressions:
                p = problem(expression, width=width, variables=["x", "y"])
                ctx = z3.Context()
                symbols = {n: z3.BitVec(n, width, ctx=ctx) for n in p.variables}
                term = to_z3(p.left_ast, symbols, width, ctx)
                for x, y in itertools.product(range(1 << width), repeat=2):
                    symbolic = z3.simplify(z3.substitute(term, (symbols["x"], z3.BitVecVal(x, width, ctx)),
                                                       (symbols["y"], z3.BitVecVal(y, width, ctx)))).as_long()
                    concrete = evaluate(p, "left", {"x": x, "y": y})["value"]
                    self.assertEqual(symbolic, concrete, (width, expression, x, y))

    def test_solver_verdict_matches_independent_small_domain_enumeration(self):
        expressions = ["x", "y", "x+y", "y+x", "x^x", "0", "(x<<1)>>1", "x&3", "x>>y", "x<<y"]
        for left, right in itertools.combinations(expressions, 2):
            p = problem(left, right, width=3, variables=["x", "y"])
            different = any(evaluate(p, "left", dict(x=x, y=y))["value"] != evaluate(p, "right", dict(x=x, y=y))["value"]
                            for x, y in itertools.product(range(8), repeat=2))
            self.assertEqual(check(p)["status"], "different" if different else "equivalent", (left, right))


if __name__ == "__main__":
    unittest.main()
