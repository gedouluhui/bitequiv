"""Concrete interpreter, independent of Z3 lowering and operator implementations."""
from .language import InvalidProblem, Problem


def evaluate(problem: Problem, side: str, values: dict) -> dict:
    # A frozen dataclass can still be replaced with new text and stale AST fields.
    # Use the same serialized-input boundary as check(), never caller-supplied nodes.
    problem = Problem.from_dict(problem.to_dict())
    if side not in ("left", "right"):
        raise InvalidProblem("side must be left or right")
    if type(values) is not dict or set(values) != set(problem.variables):
        raise InvalidProblem("assignment must contain exactly the declared variables")
    for name, low, high in problem.ranges:
        if type(values[name]) is not int or not low <= values[name] <= high:
            raise InvalidProblem(f"assignment for {name} is outside its unsigned range")
    mask = (1 << problem.width) - 1
    steps = []

    def walk(node):
        operands = [walk(child) for child in node.args]
        op = node.kind
        if op == "constant":
            result = node.value
        elif op == "variable":
            result = values[node.value]
        elif op == "neg":
            result = -operands[0]
        elif op == "pos":
            result = operands[0]
        elif op == "not":
            result = ~operands[0]
        else:
            a, b = operands
            if op == "+":
                result = a + b
            elif op == "-":
                result = a - b
            elif op == "*":
                result = a * b
            elif op == "&":
                result = a & b
            elif op == "|":
                result = a | b
            elif op == "^":
                result = a ^ b
            elif op == "<<":
                result = 0 if b >= problem.width else a << b
            elif op == ">>":
                result = 0 if b >= problem.width else a >> b
            else:
                raise InvalidProblem("unrecognized concrete operation")
        result &= mask
        steps.append(dict(expression=node.source, operation=op, value=result,
                          binary=format(result, f"0{problem.width}b")))
        return result

    value = walk(problem.left_ast if side == "left" else problem.right_ast)
    return dict(value=value, steps=steps)
