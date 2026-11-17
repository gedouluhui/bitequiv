import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from bitequiv import check, InvalidProblem
from bitequiv.evidence import replay_report, parse_report

ROOT = Path(__file__).resolve().parents[1]


def real_report():
    return check(dict(width=8, variables=["x","y"], left="(x+y)>>1", right="(x&y)+((x^y)>>1)",
                      ranges={"x":[128,128], "y":[128,128]}))


class EvidenceTests(unittest.TestCase):
    def test_replays_actual_counterexample_without_solver(self):
        report = real_report()
        with patch("z3.Solver.check", side_effect=AssertionError("must not call solver")):
            result = replay_report(report)
        self.assertEqual(result["verification_status"], "verified_counterexample")
        self.assertEqual(result["values"], {"left": 0, "right": 128})
        self.assertIn("not authenticate", result["scope"])

    def test_accepts_historical_real_v01_report(self):
        data = parse_report((ROOT/"docs"/"example-report.json").read_text("utf-8"))
        self.assertEqual(replay_report(data)["verification_status"], "verified_counterexample")

    def test_identity_and_domain_claims_are_not_trusted(self):
        for field in ("fingerprint", "problem", "semantics", "domain", "certificate"):
            r = real_report()
            if field == "fingerprint": r[field] = "0"*64
            if field == "problem": r[field]["left"] = "x"
            if field == "semantics": r[field] = "signed integers"
            if field == "domain": r["coverage"]["domain_assignments"] = "0"
            if field == "certificate": r["coverage"]["proof_certificate"] = True
            with self.subTest(field=field):
                self.assertEqual(replay_report(r)["verification_status"], "mismatch")

    def test_both_values_every_step_and_bit_positions_are_recomputed(self):
        for field in ("left", "right", "source", "operation", "step_value", "binary", "bits", "assignment", "replayed", "extra"):
            r = real_report(); w = r["witness"]
            if field in ("left", "right"): w[field]["value"] += 1
            if field == "source": w["left"]["steps"][0]["expression"] = "y"
            if field == "operation": w["left"]["steps"][0]["operation"] = "constant"
            if field == "step_value": w["left"]["steps"][0]["value"] = 1
            if field == "binary": w["left"]["steps"][0]["binary"] = "00000000"
            if field == "bits": w["different_bits"] = [0]
            if field == "assignment": w["assignment"]["x"] = 0
            if field == "replayed": w["replayed"] = False
            if field == "extra": w["hidden"] = "unchecked"
            with self.subTest(field=field):
                self.assertEqual(replay_report(r)["verification_status"], "mismatch")

    def test_bool_and_float_cannot_match_integer_evidence(self):
        for value in (False, 0.0):
            r = real_report(); r["witness"]["left"]["value"] = value
            with self.subTest(value=repr(value)):
                self.assertEqual(replay_report(r)["verification_status"], "mismatch")
        r = real_report(); r["witness"]["replayed"] = 1
        self.assertEqual(replay_report(r)["verification_status"], "mismatch")

    def test_no_universal_or_unknown_claim_gets_verified(self):
        for report in (check(dict(width=8,variables=["x"],left="x",right="x")),
                       check(dict(width=32,variables=["x"],left="x*x",right="x+1"),rlimit=1),
                       check({"width":False})):
            with self.subTest(status=report["status"]):
                self.assertEqual(replay_report(report)["verification_status"], "unverifiable")

    def test_untrusted_schema_and_missing_fields(self):
        for change in ({"schema_version":True}, {"schema_version":2}, {"status":"verified"},
                       {"extra":"unrecognized"}, {"witness":None}, {"engine":None}):
            r = real_report(); r.update(change)
            with self.subTest(change=change):
                self.assertEqual(replay_report(r)["verification_status"], "invalid")
        r = real_report(); del r["fingerprint"]
        self.assertEqual(replay_report(r)["verification_status"], "invalid")

    def test_metadata_is_explicitly_not_authenticated(self):
        r = real_report(); r["engine"]["version"] = "historical-version-unverified"
        result = replay_report(r)
        self.assertEqual(result["verification_status"], "verified_counterexample")
        self.assertIn("historical", result["scope"])

    def test_bounded_duplicate_safe_json_and_no_nonfinite_values(self):
        for text in (" "*(1048576+1), '{"status":"different","status":"equivalent"}',
                     '{"x":NaN}', "null", "[1]", '{"x":1e999}', '{"x":"\\ud800"}'):
            with self.subTest(text=text[:40]), self.assertRaises(InvalidProblem):
                parse_report(text)

    def test_native_assignment_keys_are_not_coerced_into_valid_json_keys(self):
        r = check(dict(width=8,variables=["null"],left="null",right="null+1"))
        value = r["witness"]["assignment"].pop("null")
        r["witness"]["assignment"][None] = value
        self.assertEqual(replay_report(r)["verification_status"], "invalid")

    def test_native_tuples_and_non_string_keys_are_rejected_before_serializing(self):
        for field in ("tuple", "key"):
            r = real_report()
            if field == "tuple": r["witness"]["left"]["steps"] = tuple(r["witness"]["left"]["steps"])
            else: r["coverage"][None] = "value"
            self.assertEqual(replay_report(r)["verification_status"], "invalid")

    def test_direct_api_rejects_non_json_objects_and_depth(self):
        for report in ([], None, {"x":{1,2}}, {"x":float("nan")}, {"x": "\ud800"}):
            with self.subTest(report=repr(report)):
                self.assertEqual(replay_report(report)["verification_status"], "invalid")


if __name__ == "__main__":
    unittest.main()
