"""Portable replay evidence for an UNSAT finite-domain equivalence query."""
from __future__ import annotations

PROOF_SCOPE = ("Replay evidence for the declared nonempty finite domain; "
               "not a proof certificate or a claim about the generating program.")


def build_proof(problem, solver) -> dict:
    """Serialize the exact assertions used by the solver, not a minimized core."""
    import z3

    return dict(
        solver="Z3",
        version=z3.get_version_string(),
        problem_sha256=problem.fingerprint,
        declarations=[f"(declare-fun v{i} () (_ BitVec {problem.width}))"
                      for i in range(len(problem.variables))],
        assertions=[assertion.sexpr() for assertion in solver.assertions()],
        scope=PROOF_SCOPE,
    )
