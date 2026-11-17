import dataclasses
import hashlib
import unittest
import z3

from bitequiv import Problem, InvalidProblem
from bitequiv.smtlib import export_smt2


def case(left="x", right="x", width=8, **rest):
    return dict(width=width, variables=["x"], left=left, right=right, **rest)


def query_result(data):
    solver = z3.Solver()
    solver.set(timeout=5000)
    solver.from_string(export_smt2(data))
    return solver.check()


class SmtlibTests(unittest.TestCase):
    def test_standard_query_identity_and_deterministic_bytes(self):
        p = Problem.from_dict(case())
        text = export_smt2(p)
        self.assertEqual(text, export_smt2(p.to_dict()))
        self.assertIn(p.fingerprint, text)
        self.assertIn("(set-logic QF_BV)", text)
        self.assertTrue(text.endswith("(check-sat)\n"))
        self.assertEqual(query_result(p.to_dict()), z3.unsat)

    def test_logical_shift_with_known_singleton_answer(self):
        self.assertEqual(query_result(case("x>>1", "64", ranges={"x": [128,128]})), z3.unsat)
        self.assertEqual(query_result(case("x>>1", "192", ranges={"x": [128,128]})), z3.sat)

    def test_ranges_are_present_and_unsigned(self):
        self.assertEqual(query_result(case("x>>7", "1", ranges={"x": [128,255]})), z3.unsat)
        self.assertEqual(query_result(case("x", "128", ranges={"x": [128,128]})), z3.unsat)
        self.assertEqual(query_result(case("x", "128")), z3.sat)

    def test_fresh_names_prevent_reserved_symbol_collisions(self):
        d = dict(width=8, variables=["let", "ite", "v0", "bvadd", "true"],
                 left="let + ite + v0 + bvadd + true", right="true + bvadd + v0 + ite + let")
        text = export_smt2(d)
        self.assertNotIn("declare-fun let", text)
        self.assertEqual(query_result(d), z3.unsat)

    def test_title_cannot_inject_commands(self):
        d = case(title="\n(exit)\n(set-option :regular-output-channel \"private\")")
        text = export_smt2(d)
        self.assertNotIn("(exit)", text)
        self.assertNotIn("private", text)
        self.assertEqual(query_result(d), z3.unsat)

    def test_wide_constants_and_shift_count_wrapping(self):
        self.assertEqual(query_result(case("x<< (255+1)", "x")), z3.unsat)
        self.assertEqual(query_result(case("x>>63", "1", width=64,
                                           ranges={"x": [1<<63, (1<<64)-1]})), z3.unsat)

    def test_rebuilds_stale_ast_and_rejects_invalid(self):
        p = Problem.from_dict(case())
        self.assertEqual(query_result(dataclasses.replace(p, left="x+1").to_dict()), z3.sat)
        with self.assertRaises(InvalidProblem):
            export_smt2(case("x # discarded"))

    def test_constants_need_no_declared_variables(self):
        d = dict(width=8, variables=[], left="-1", right="255")
        self.assertEqual(query_result(d), z3.unsat)
        d["right"] = "254"
        self.assertEqual(query_result(d), z3.sat)


if __name__ == "__main__":
    unittest.main()
