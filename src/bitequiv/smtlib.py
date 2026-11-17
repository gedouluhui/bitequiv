"""Solver-independent SMT-LIB 2 export for the explicit QF_BV contract."""
from .language import InvalidProblem, Problem

_OPERATORS = {"+": "bvadd", "-": "bvsub", "*": "bvmul", "&": "bvand", "|": "bvor",
              "^": "bvxor", "<<": "bvshl", ">>": "bvlshr", "neg": "bvneg", "not": "bvnot"}


def export_smt2(problem) -> str:
    """Emit a fresh query, not a verdict. UNSAT proves inequality impossible."""
    p = Problem.from_dict(problem.to_dict() if isinstance(problem, Problem) else problem)
    names = {name: f"v{i}" for i, name in enumerate(p.variables)}

    def emit(node):
        if node.kind == "constant":
            return f"(_ bv{node.value} {p.width})"
        if node.kind == "variable":
            return names[node.value]
        if node.kind == "pos":
            return emit(node.args[0])
        if node.kind not in _OPERATORS:
            raise InvalidProblem("unsupported SMT-LIB operation")
        return f"({_OPERATORS[node.kind]} {' '.join(emit(a) for a in node.args)})"

    lines = ["; BitEquiv: inequality of unsigned fixed-width expressions",
             f"; canonical-problem-sha256: {p.fingerprint}", "(set-logic QF_BV)"]
    for name in p.variables:
        lines.append(f"(declare-fun {names[name]} () (_ BitVec {p.width}))")
    for name, low, high in p.ranges:
        symbol = names[name]
        lines.append(f"(assert (bvuge {symbol} (_ bv{low} {p.width})))")
        lines.append(f"(assert (bvule {symbol} (_ bv{high} {p.width})))")
    lines += [f"(assert (distinct {emit(p.left_ast)} {emit(p.right_ast)}))", "(check-sat)"]
    return "\n".join(lines) + "\n"
