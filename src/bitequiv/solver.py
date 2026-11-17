"""Z3-backed equivalence query. Concrete replay must agree before witness publication."""
from .evaluate import evaluate
from .language import InvalidProblem, Problem, _integer

SEMANTICS = "Uniform-width unsigned bitvectors; wrapping arithmetic; logical right shift; overshift yields zero. Not C/LLVM semantics."


def to_z3(node, symbols, width, ctx):
    import z3
    if node.kind == "constant":
        return z3.BitVecVal(node.value, width, ctx)
    if node.kind == "variable":
        return symbols[node.value]
    args = [to_z3(child, symbols, width, ctx) for child in node.args]
    if node.kind == "neg":
        return -args[0]
    if node.kind == "pos":
        return args[0]
    if node.kind == "not":
        return ~args[0]
    a, b = args
    if node.kind == "+":
        return a + b
    if node.kind == "-":
        return a - b
    if node.kind == "*":
        return a * b
    if node.kind == "&":
        return a & b
    if node.kind == "|":
        return a | b
    if node.kind == "^":
        return a ^ b
    if node.kind == "<<":
        return a << b
    if node.kind == ">>":
        return z3.LShR(a, b)
    raise InvalidProblem("unrecognized symbolic operation")


def check(problem, *, timeout_ms=5000, rlimit=2000000):
    """Return JSON-compatible evidence. Invalid options never invoke the solver."""
    try:
        p = Problem.from_dict(problem.to_dict() if isinstance(problem, Problem) else problem)
        _integer(timeout_ms, "timeout_ms", 1, 60000)
        _integer(rlimit, "rlimit", 1, 20000000)
    except InvalidProblem as exc:
        return dict(schema_version=1, status="invalid", reason=str(exc))
    report = dict(schema_version=1, status="unknown", problem=p.to_dict(), fingerprint=p.fingerprint,
                  semantics=SEMANTICS,
                  engine=dict(name="Z3", timeout_ms=timeout_ms, rlimit=rlimit),
                  coverage=dict(domain_assignments=str(p.domain_size), proof_certificate=False,
                                scope="Only these expressions and declared input ranges; not the generating program."))
    try:
        import z3
    except ImportError:
        report["reason"] = "Z3 is unavailable; install the declared z3-solver dependency."
        return report
    report["engine"]["version"] = z3.get_version_string()
    try:
        ctx = z3.Context()
        symbols = {name: z3.BitVec(name, p.width, ctx=ctx) for name in p.variables}
        left = to_z3(p.left_ast, symbols, p.width, ctx)
        right = to_z3(p.right_ast, symbols, p.width, ctx)
        solver = z3.Solver(ctx=ctx)
        solver.set(timeout=timeout_ms, rlimit=rlimit)
        for name, low, high in p.ranges:
            solver.add(z3.UGE(symbols[name], low), z3.ULE(symbols[name], high))
        # Every validated inclusive range is nonempty; their Cartesian product is nonempty.
        solver.add(left != right)
        result = solver.check()
        if result == z3.unsat:
            report["status"] = "equivalent"
            report["coverage"]["method"] = "Z3 found the inequality unsatisfiable over the nonempty declared domain."
        elif result == z3.sat:
            model = solver.model()
            assignment = {name: model.eval(term, model_completion=True).as_long() for name, term in symbols.items()}
            try:
                lvalue = evaluate(p, "left", assignment)
                rvalue = evaluate(p, "right", assignment)
            except InvalidProblem as exc:
                report["reason"] = "Counterexample replay rejected the assignment: " + str(exc)
                return report
            if (lvalue["value"] == rvalue["value"] or
                    lvalue["value"] != model.eval(left, model_completion=True).as_long() or
                    rvalue["value"] != model.eval(right, model_completion=True).as_long()):
                report["reason"] = "Counterexample replay disagreed with the solver; no claim is made."
                return report
            report["status"] = "different"
            report["coverage"]["method"] = "Satisfying assignment with independent concrete replay; witness need not be minimal."
            difference = lvalue["value"] ^ rvalue["value"]
            report["witness"] = dict(assignment=assignment, left=lvalue, right=rvalue, replayed=True,
                                     different_bits=[i for i in range(p.width) if (difference >> i) & 1])
        else:
            report["reason"] = solver.reason_unknown() or "Z3 returned unknown."
    except z3.Z3Exception as exc:
        report["status"] = "unknown"
        report["reason"] = "Z3 failed: " + str(exc)
        report.pop("witness", None)
    return report
