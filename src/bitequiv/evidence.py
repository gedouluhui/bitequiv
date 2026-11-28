"""Check saved counterexample mathematics, NOT historical authorship or solver claims."""
import json

from .evaluate import evaluate
from .language import InvalidProblem, Problem, _integer, _text, load_json_object
from .solver import SEMANTICS

MAX_REPORT_BYTES = 1048576
_SCOPE = ("Verifies only the concrete inequality for the included problem and assignment; "
          "does not authenticate authorship, historical solver execution or metadata, "
          "and does not prove equivalence for all inputs.")


def parse_report(text):
    return load_json_object(text, MAX_REPORT_BYTES)


def _same(left, right):
    """JSON equality that never identifies bool/float with an integer."""
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(_same(left[k], right[k]) for k in left)
    if type(left) is list:
        return len(left) == len(right) and all(_same(a, b) for a, b in zip(left, right))
    return left == right


def _validate_native_json(value):
    count = 0

    def visit(item, depth):
        nonlocal count
        count += 1
        if depth > 64 or count > 65536:
            raise InvalidProblem("native JSON exceeds depth or item limit")
        kind = type(item)
        if kind is dict:
            if len(item) > 65536 or any(type(key) is not str for key in item):
                raise InvalidProblem("native JSON object keys must be strings")
            for key, val in item.items():
                visit(key, depth + 1)
                visit(val, depth + 1)
        elif kind is list:
            if len(item) > 65536:
                raise InvalidProblem("native JSON list exceeds item limit")
            for val in item:
                visit(val, depth + 1)
        elif kind is str:
            _text(item, "native JSON string", MAX_REPORT_BYTES)
        elif kind not in (int, float, bool, type(None)):
            raise InvalidProblem("report must contain native JSON types without coercion")

    visit(value, 0)


def replay_report(report):
    def answer(status, reason, **facts):
        return dict(verification_status=status, reason=reason, scope=_SCOPE, **facts)

    try:
        if type(report) is not dict:
            raise InvalidProblem("report must be an object")
        # Reject non-JSON native values before serialization can coerce keys or tuples.
        _validate_native_json(report)
        # Snapshot and bound external data. This also rejects non-finite/invalid Unicode.
        r = parse_report(json.dumps(report, ensure_ascii=True, allow_nan=False))
        allowed = {"schema_version", "status", "problem", "fingerprint", "semantics", "engine", "coverage", "witness", "proof", "reason"}
        if r.keys() - allowed or type(r.get("schema_version")) is not int or r["schema_version"] != 1:
            raise InvalidProblem("unsupported schema version or unknown report fields")
        status = r.get("status")
        if type(status) is not str or status not in ("equivalent", "different", "unknown", "invalid"):
            raise InvalidProblem("unrecognized check status")
        if status != "different":
            if "proof" in r and status != "equivalent":
                raise InvalidProblem("UNSAT replay evidence requires an equivalent status")
            return answer("unverifiable", "Only concrete counterexamples can be replayed; re-solve universal claims.")
        required = allowed - {"reason", "proof"}
        if r.keys() != required:
            raise InvalidProblem("counterexample report must contain exactly its required fields")
        p = Problem.from_dict(r["problem"])
        for name in ("coverage", "engine", "witness"):
            if type(r[name]) is not dict:
                raise InvalidProblem(f"{name} must be an object")
        if r["coverage"].keys() != {"domain_assignments", "proof_certificate", "scope", "method"}:
            raise InvalidProblem("unsupported coverage fields")
        if r["engine"].keys() != {"name", "version", "timeout_ms", "rlimit"}:
            raise InvalidProblem("unsupported engine fields")
        _text(r["engine"]["name"], "engine name", 128)
        _text(r["engine"]["version"], "engine version", 128)
        _integer(r["engine"]["timeout_ms"], "timeout_ms", 1, 60000)
        _integer(r["engine"]["rlimit"], "rlimit", 1, 20000000)
        _text(r["coverage"]["scope"], "coverage scope", 1024)
        _text(r["coverage"]["method"], "coverage method", 1024)
        checks = [("problem fingerprint", r["fingerprint"], p.fingerprint),
                  ("semantics", r["semantics"], SEMANTICS),
                  ("domain size", r["coverage"]["domain_assignments"], str(p.domain_size)),
                  ("proof certificate claim", r["coverage"]["proof_certificate"], False)]
        for name, supplied, expected in checks:
            if not _same(supplied, expected):
                return answer("mismatch", f"Report {name} does not match the included problem or supported contract.")
        assignment = r["witness"].get("assignment")
        try:
            left = evaluate(p, "left", assignment)
            right = evaluate(p, "right", assignment)
        except InvalidProblem as exc:
            return answer("mismatch", f"Witness assignment rejected: {exc}")
        if left["value"] == right["value"]:
            return answer("mismatch", "The supplied assignment does not demonstrate unequal outputs.")
        xor = left["value"] ^ right["value"]
        expected = dict(assignment=assignment, left=left, right=right, replayed=True,
                        different_bits=[i for i in range(p.width) if (xor >> i) & 1])
        if not _same(r["witness"], expected):
            return answer("mismatch", "Witness values, complete trace, bit positions or replay marker do not match recomputation.")
        return answer("verified_counterexample", "Both outputs and the complete concrete evaluation trace agree.",
                      fingerprint=p.fingerprint, assignment=assignment,
                      values={"left": left["value"], "right": right["value"]}, different_bits=expected["different_bits"])
    except (InvalidProblem, TypeError, ValueError, RecursionError, UnicodeError) as exc:
        return answer("invalid", str(exc))
