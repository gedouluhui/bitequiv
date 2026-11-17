"""Strict, bounded syntax for uniform-width unsigned bitvectors. Never evals input."""
from __future__ import annotations

import ast
from dataclasses import dataclass
import hashlib
import json
import keyword
import math
import re

MAX_INPUT_BYTES = 65536
MAX_EXPRESSION_CHARS = 2048
MAX_NODES = 256
MAX_DEPTH = 32
BINARY = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.BitAnd: "&",
          ast.BitOr: "|", ast.BitXor: "^", ast.LShift: "<<", ast.RShift: ">>"}
UNARY = {ast.USub: "neg", ast.UAdd: "pos", ast.Invert: "not"}


class InvalidProblem(ValueError):
    """Input lies outside the documented language or resource limits."""


@dataclass(frozen=True)
class Node:
    kind: str
    value: int | str | None
    args: tuple[Node, ...]
    source: str


def _text(value, name, limit):
    if not isinstance(value, str) or len(value) > limit:
        raise InvalidProblem(f"{name} must be text of at most {limit} characters")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise InvalidProblem(f"{name} must be valid Unicode") from exc
    return value


def _integer(value, name, low, high):
    if type(value) is not int or not low <= value <= high:
        raise InvalidProblem(f"{name} must be an integer in [{low}, {high}]")
    return value


def _parse_expression(source, variables, width):
    source = _text(source, "expression", MAX_EXPRESSION_CHARS)
    if not re.fullmatch(r"[A-Za-z0-9_ \t()+*\-&|^~<>]+", source):
        raise InvalidProblem("expressions require ASCII tokens, spaces or tabs; comments are not supported")
    if not source.strip():
        raise InvalidProblem("expressions must be nonempty single lines")
    source = source.strip()
    try:
        tree = ast.parse(source, mode="eval")
    except (SyntaxError, ValueError, RecursionError) as exc:
        raise InvalidProblem("invalid expression syntax") from exc
    pending = [(tree, 0)]
    count = 0
    while pending:
        node, depth = pending.pop()
        count += 1
        if count > MAX_NODES or depth > MAX_DEPTH:
            raise InvalidProblem("expression exceeds AST node or depth limit")
        pending.extend((child, depth + 1) for child in ast.iter_child_nodes(node))

    def convert(node):
        text = ast.get_source_segment(source, node) or source
        if isinstance(node, ast.Constant):
            return Node("constant", _integer(node.value, "literal", 0, (1 << width) - 1), (), text)
        if isinstance(node, ast.Name) and node.id in variables:
            return Node("variable", node.id, (), text)
        if isinstance(node, ast.BinOp) and type(node.op) in BINARY:
            return Node(BINARY[type(node.op)], None, (convert(node.left), convert(node.right)), text)
        if isinstance(node, ast.UnaryOp) and type(node.op) in UNARY:
            return Node(UNARY[type(node.op)], None, (convert(node.operand),), text)
        raise InvalidProblem(f"unsupported syntax or undeclared variable: {text[:80]}")

    return source, convert(tree.body)


@dataclass(frozen=True)
class Problem:
    width: int
    variables: tuple[str, ...]
    left: str
    right: str
    ranges: tuple[tuple[str, int, int], ...]
    title: str
    left_ast: Node
    right_ast: Node

    @classmethod
    def from_dict(cls, data):
        if type(data) is not dict:
            raise InvalidProblem("problem must be an object")
        required = {"width", "variables", "left", "right"}
        if not required <= data.keys() or data.keys() - required - {"ranges", "title"}:
            raise InvalidProblem("expected width, variables, left, right and optional ranges/title only")
        width = _integer(data["width"], "width", 1, 64)
        variables = data["variables"]
        if type(variables) is not list or len(variables) > 8:
            raise InvalidProblem("variables must be a list of at most 8 identifiers")
        for name in variables:
            if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]{0,31}", name) or keyword.iskeyword(name):
                raise InvalidProblem("variable names must be non-keyword ASCII identifiers of length 1–32")
        if len(set(variables)) != len(variables):
            raise InvalidProblem("variable names must be distinct")
        raw_ranges = data.get("ranges", {})
        if type(raw_ranges) is not dict or raw_ranges.keys() - set(variables):
            raise InvalidProblem("ranges may only name declared variables")
        ranges = []
        for name in variables:
            bounds = raw_ranges.get(name, [0, (1 << width) - 1])
            if type(bounds) is not list or len(bounds) != 2:
                raise InvalidProblem(f"range for {name} must be [min,max]")
            low, high = (_integer(b, f"range for {name}", 0, (1 << width) - 1) for b in bounds)
            if low > high:
                raise InvalidProblem(f"range for {name} is empty; vacuous equivalence is rejected")
            ranges.append((name, low, high))
        title = _text(data.get("title", "Expression equivalence"), "title", 120)
        left, left_ast = _parse_expression(data["left"], variables, width)
        right, right_ast = _parse_expression(data["right"], variables, width)
        return cls(width, tuple(variables), left, right, tuple(ranges), title, left_ast, right_ast)

    def to_dict(self):
        # Validate the original representation BEFORE a dict conversion can hide duplicates.
        _integer(self.width, "width", 1, 64)
        if type(self.variables) is not tuple or any(type(n) is not str for n in self.variables):
            raise InvalidProblem("Problem.variables must be a tuple of string names")
        if len(set(self.variables)) != len(self.variables) or type(self.ranges) is not tuple:
            raise InvalidProblem("Problem variables/ranges must be unique canonical tuples")
        names = []
        for entry in self.ranges:
            if type(entry) is not tuple or len(entry) != 3 or type(entry[0]) is not str:
                raise InvalidProblem("raw range entries must be (name,min,max) tuples")
            name, low, high = entry
            _integer(low, "range minimum", 0, (1 << self.width) - 1)
            _integer(high, "range maximum", 0, (1 << self.width) - 1)
            if low > high or name in names:
                raise InvalidProblem("raw ranges must be nonempty and unique")
            names.append(name)
        if set(names) != set(self.variables):
            raise InvalidProblem("raw ranges must cover exactly the declared variables")
        return dict(width=self.width, variables=list(self.variables), left=self.left, right=self.right,
                    ranges={n: [lo, hi] for n, lo, hi in self.ranges}, title=self.title)

    @property
    def fingerprint(self):
        encoded = json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @property
    def domain_size(self):
        size = 1
        for low, high in self.to_dict()["ranges"].values():
            size *= high - low + 1
        return size


def load_json_object(text, max_bytes=MAX_INPUT_BYTES):
    if not isinstance(text, str):
        raise InvalidProblem("input must be UTF-8 JSON text")
    try:
        length = len(text.encode("utf-8"))
    except UnicodeError as exc:
        raise InvalidProblem("input must be valid Unicode") from exc
    if length > max_bytes:
        raise InvalidProblem(f"input exceeds {max_bytes} bytes")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise InvalidProblem(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def reject_constant(value):
        raise InvalidProblem(f"non-finite JSON value: {value}")

    try:
        data = json.loads(text, object_pairs_hook=unique, parse_constant=reject_constant)
    except (ValueError, RecursionError) as exc:
        if isinstance(exc, InvalidProblem):
            raise
        raise InvalidProblem("invalid JSON") from exc
    if type(data) is not dict:
        raise InvalidProblem("JSON must contain an object")
    pending = [(data, 0)]
    count = 0
    while pending:
        value, depth = pending.pop()
        count += 1
        if depth > 64 or count > 65536:
            raise InvalidProblem("JSON structure exceeds depth or item limit")
        if type(value) is dict:
            pending.extend((key, depth + 1) for key in value)
            pending.extend((v, depth + 1) for v in value.values())
        elif type(value) is list:
            pending.extend((v, depth + 1) for v in value)
        elif isinstance(value, str):
            _text(value, "JSON string", max_bytes)
        elif type(value) is float and not math.isfinite(value):
            raise InvalidProblem("non-finite JSON number")
    return data


def parse_json(text):
    return Problem.from_dict(load_json_object(text))
