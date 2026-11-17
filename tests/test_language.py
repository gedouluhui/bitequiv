import copy
import json
import unittest

from bitequiv.language import InvalidProblem, Problem, parse_json
from bitequiv.evaluate import evaluate


def problem(left="x", right="x", width=8, variables=None, **extra):
    return Problem.from_dict(dict(width=width, variables=["x"] if variables is None else variables,
                                  left=left, right=right, **extra))


class LanguageTests(unittest.TestCase):
    def test_wrap_at_every_node(self):
        self.assertEqual(evaluate(problem("(x + 1) >> 1"), "left", {"x": 255})["value"], 0)

    def test_logical_right_shift(self):
        self.assertEqual(evaluate(problem("x >> 1"), "left", {"x": 128})["value"], 64)

    def test_shift_oversize(self):
        for expression in ("x << 8", "x >> 8", "x << 255", "x >> 255"):
            with self.subTest(expression=expression):
                self.assertEqual(evaluate(problem(expression), "left", {"x": 255})["value"], 0)

    def test_shift_count_is_wrapped_expression(self):
        self.assertEqual(evaluate(problem("x << (255 + 1)"), "left", {"x": 7})["value"], 7)

    def test_all_operators_with_hand_computed_values(self):
        answers = {"x + 3": 253, "x - 251": 255, "x * 3": 238, "x & 15": 10,
                   "x | 15": 255, "x ^ 15": 245, "~x": 5, "-x": 6, "+x": 250}
        for expression, expected in answers.items():
            with self.subTest(expression=expression):
                self.assertEqual(evaluate(problem(expression), "left", {"x": 250})["value"], expected)

    def test_high_bit_and_width_boundaries(self):
        for width in (1, 2, 32, 64):
            with self.subTest(width=width):
                p = problem("x+1", width=width)
                self.assertEqual(evaluate(p, "left", {"x": (1 << width) - 1})["value"], 0)

    def test_trace_contains_actual_intermediates(self):
        answer = evaluate(problem("(x + 1) >> 1"), "left", {"x": 255})
        values = {s["expression"]: s["value"] for s in answer["steps"]}
        self.assertEqual(values["x + 1"], 0)
        self.assertEqual(answer["steps"][-1]["value"], answer["value"])

    def test_immutable_input_snapshot_and_fingerprint(self):
        data = dict(width=8, variables=["x"], left="x", right="x", ranges={"x": [2, 8]})
        original = copy.deepcopy(data)
        p = Problem.from_dict(data)
        data["ranges"]["x"][0] = 7
        self.assertEqual(p.to_dict()["ranges"]["x"], [2, 8])
        self.assertEqual(p.fingerprint, Problem.from_dict(original).fingerprint)
        self.assertNotEqual(p.fingerprint, Problem.from_dict(data).fingerprint)

    def test_json_duplicate_keys_are_rejected(self):
        with self.assertRaises(InvalidProblem):
            parse_json('{"width":8,"width":4,"variables":[],"left":"1","right":"1"}')

    def test_json_size_and_non_finite_rejected(self):
        for text in (" " * 65537, '{"width":NaN}', "[]", "null", '{"x":Infinity}'):
            with self.subTest(text=text[:40]), self.assertRaises(InvalidProblem):
                parse_json(text)

    def test_json_unicode_surrogate_is_rejected(self):
        with self.assertRaises(InvalidProblem):
            parse_json(json.dumps(dict(width=8, variables=[], left="1", right="1", title="\ud800")))

    def test_strict_schema(self):
        base = dict(width=8, variables=["x"], left="x", right="x")
        invalids = [dict(width=True), dict(width=0), dict(width=65), dict(width=8.0),
                    dict(variables=["x", "x"]), dict(variables=["for"]), dict(variables=["True"]),
                    dict(variables=["α"]), dict(variables="x"), dict(variables=["v" * 33]),
                    dict(variables=[f"x{i}" for i in range(9)]), dict(title="t" * 121),
                    dict(ranges={"y": [0, 1]}), dict(ranges={"x": [5, 4]}),
                    dict(ranges={"x": [-1, 2]}), dict(ranges={"x": [0, 256]}),
                    dict(ranges={"x": [False, 1]}), dict(ranges={"x": [0, 1.0]}),
                    dict(ranges={"x": [0]}), dict(ranges=[]), dict(unknown="ignored?")]
        for change in invalids:
            with self.subTest(change=change), self.assertRaises(InvalidProblem):
                Problem.from_dict({**base, **change})

    def test_language_is_an_allowlist_not_python_execution(self):
        expressions = ["__import__('os')", "x.real", "x[0]", "[x]", "x / 1", "x // 1",
                       "x % 2", "x ** 2", "x < 1", "x and 1", "True", "1.0", "'x'",
                       "(lambda: x)()", "y", "256", "0x100", "", "x\n+1", "x; x", "{x}"]
        for expression in expressions:
            with self.subTest(expression=expression), self.assertRaises(InvalidProblem):
                problem(expression)

    def test_bounded_expression_complexity(self):
        for expression in ("x" * 2049, "+" * 34 + "x", "+".join(["x"] * 260)):
            with self.subTest(expression=expression[:20]), self.assertRaises(InvalidProblem):
                problem(expression)

    def test_domain_validation_in_concrete_execution(self):
        p = problem(ranges={"x": [2, 5]})
        for assignment in ({}, {"x": True}, {"x": 1}, {"x": 6}, {"x": 3, "y": 2}):
            with self.subTest(assignment=assignment), self.assertRaises(InvalidProblem):
                evaluate(p, "left", assignment)
        with self.assertRaises(InvalidProblem):
            evaluate(p, "middle", {"x": 3})

    def test_constant_domain_has_one_assignment(self):
        p = problem("-1", "255", variables=[])
        self.assertEqual(p.domain_size, 1)
        self.assertEqual(evaluate(p, "left", {})["value"], 255)


if __name__ == "__main__":
    unittest.main()
