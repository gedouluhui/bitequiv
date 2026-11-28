import unittest
from unittest.mock import patch

import z3

from bitequiv import check
from bitequiv.language import Problem


def fresh_solver(proof):
    """Replay only serialized evidence in a context unrelated to the original check."""
    query = "\n".join([
        *proof["declarations"],
        *(f"(assert {assertion})" for assertion in proof["assertions"]),
    ])
    ctx = z3.Context()
    assertions = z3.parse_smt2_string(query, ctx=ctx)
    solver = z3.Solver(ctx=ctx)
    solver.add(assertions)
    return solver


class ProofTests(unittest.TestCase):
    def test_equivalent_report_contains_exact_replayable_assertions(self):
        data = dict(width=8, variables=["x"], left="x", right="x")
        report = check(Problem.from_dict(data))
        self.assertEqual(report["status"], "equivalent")
        self.assertIn("proof", report)
        proof = report["proof"]
        self.assertEqual(proof["solver"], "Z3")
        self.assertEqual(proof["version"], z3.get_version_string())
        self.assertEqual(proof["problem_sha256"], report["fingerprint"])
        self.assertEqual(proof["declarations"], ["(declare-fun v0 () (_ BitVec 8))"])
        ctx = z3.Context()
        x = z3.BitVec("v0", 8, ctx=ctx)
        expected = [z3.UGE(x, 0), z3.ULE(x, 255), x != x]
        self.assertEqual(proof["assertions"], [assertion.sexpr() for assertion in expected])
        self.assertFalse(report["coverage"]["proof_certificate"])
        self.assertIn("declared", proof["scope"])

    def test_serialized_unsat_query_replays_in_a_fresh_solver(self):
        problems = [
            dict(width=8, variables=["x"], left="x", right="x"),
            dict(width=8, variables=["x", "y"], left="(x+y)<<1", right="(x<<1)+(y<<1)"),
            dict(width=8, variables=["x", "y"], left="(x+y)>>1", right="(x&y)+((x^y)>>1)",
                 ranges={"x": [0, 127], "y": [0, 127]}),
            dict(width=64, variables=["x"], left="x+0", right="x",
                 ranges={"x": [1 << 63, (1 << 64) - 1]}),
            dict(width=8, variables=[], left="-1", right="255"),
            dict(width=8, variables=["_", "let"], left="_+let", right="let+_"),
        ]
        for data in problems:
            with self.subTest(data=data):
                report = check(data)
                self.assertEqual(report["status"], "equivalent")
                self.assertIn("proof", report)
                replay = fresh_solver(report["proof"])
                self.assertEqual(replay.check(), z3.unsat)

    def test_problem_hash_changes_with_the_declared_finite_domain(self):
        full = check(dict(width=8, variables=["x"], left="x", right="x"))
        restricted = check(dict(width=8, variables=["x"], left="x", right="x",
                                ranges={"x": [128, 255]}))
        self.assertEqual(full["status"], "equivalent")
        self.assertEqual(restricted["status"], "equivalent")
        self.assertIn("proof", full)
        self.assertIn("proof", restricted)
        self.assertNotEqual(full["proof"]["problem_sha256"], restricted["proof"]["problem_sha256"])
        for report in (full, restricted):
            self.assertEqual(report["proof"]["problem_sha256"], report["fingerprint"])

    def test_non_equivalent_results_do_not_claim_unsat_evidence(self):
        different = check(dict(width=8, variables=["x"], left="x", right="x+1"))
        self.assertEqual(different["status"], "different")
        self.assertNotIn("proof", different)
        with patch("z3.Solver.check", return_value=z3.unknown):
            unknown = check(dict(width=8, variables=["x"], left="x*x", right="x+1"))
        self.assertEqual(unknown["status"], "unknown")
        self.assertNotIn("proof", unknown)


if __name__ == "__main__":
    unittest.main()
