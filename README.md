# BitEquiv

**Same inputs. Different bits. Find the counterexample before shipping the optimization.**

BitEquiv checks two small, fixed-width unsigned integer expressions with Z3, replays counterexamples in an independent Python interpreter, and produces a self-contained HTML explanation. No GPU, account, API key, or network access during checking.

[中文快速说明](README.zh-CN.md) · [Example report source](docs/example-report.html) · [Language and evidence contract](docs/DESIGN.md)

> Alpha: a focused bitvector workflow, not a C/LLVM verifier. A solver proof is not a proof about the program that produced your expressions. No independently checkable proof certificate is emitted.

## The 30-second example

These two expressions can both look like an integer average:

```text
left:   (x + y) >> 1
right:  (x & y) + ((x ^ y) >> 1)
```

At 8 bits, `x=128, y=128` gives **left=0, right=128**: the left addition wraps before the shift. Restrict both inputs to `0..127` and they become equivalent. This is a mathematical example; the solver may choose a different valid witness.

```bash
# From a downloaded or cloned source checkout; no PyPI publication is claimed.
python -m venv .venv
# Activate .venv using your shell's activation command, then:
python -m pip install .
python -m bitequiv check examples/overflow-mean.json --json result.json --html result.html
```

The first check intentionally exits **1** because it found a counterexample. Open `result.html` locally: the report shows the exact assignment, differing output bits, each intermediate value, the input domain and a reproducible JSON case. Existing output files are never overwritten; choose new names on repeat runs.

```bash
python -m bitequiv check examples/bounded-mean.json
# exit 0: equivalent within the restricted domain
python -m bitequiv check examples/shift-distribution.json
# exit 0: wrapping addition distributes over this shift
python -m bitequiv check examples/lost-high-bit.json
# exit 1: shifting left and back right loses the high bit
```

Requires Python 3.11+ and `z3-solver>=4.12,<5`. The console command `bitequiv` is also installed. Source and wheel installation work without installing development tools. Installing dependencies may require network access; checking and viewing do not.

## Put a check in CI

Create a problem file:

```json
{
  "title": "Addition distributes over a left shift",
  "width": 32,
  "variables": ["x", "y"],
  "left": "(x + y) << 1",
  "right": "(x << 1) + (y << 1)"
}
```

Then use `bitequiv check case.json`. Only **exit 0** means equivalence was established. Do not treat all non-crashing checks as success.

| Exit | JSON status | Meaning |
|---|---|---|
| 0 | `equivalent` | Z3 proved inequality unsatisfiable over the nonempty declared domain. |
| 1 | `different` | A satisfying assignment was independently replayed and both solver outputs matched. |
| 2 | `unknown` | Solver timeout/resource failure/missing dependency, or replay disagreement. No conclusion. |
| 3 | `invalid` | Rejected input/options, unreadable file, or an output I/O problem. |

The default solver budget is 5000 ms and 2000000 resource units. Set `--timeout-ms` and `--rlimit` explicitly when needed, up to 60000 and 20000000. These are **solver query limits**, not a process-wide time or memory sandbox. Resource units are solver-specific, not seconds.

## Python API

```python
from bitequiv import Problem, check, evaluate

p = Problem.from_dict({
    "width": 8, "variables": ["x"],
    "left": "(x << 1) >> 1", "right": "x",
    "ranges": {"x": [128, 255]}
})
report = check(p)
assert report["status"] == "different"
assignment = report["witness"]["assignment"]
assert evaluate(p, "left", assignment)["value"] != evaluate(p, "right", assignment)["value"]
```

`Problem.from_dict` and `parse_json` reject invalid inputs with `InvalidProblem`. `check` accepts a `Problem` or dictionary and returns a JSON-compatible report. The pure evaluator validates assignment ranges. Use separate CLI processes for parallel jobs; concurrent Python API calls have not been verified.

## Precisely which language?

- **One width, 1–64 bits**, for variables, literals, and EVERY intermediate operation.
- **Unsigned inclusive ranges**, independently declared per variable. Omitted ranges cover the full width. Empty ranges are rejected, not reported as vacuous proofs.
- Python expression syntax and precedence for `+ - * & | ^ << >>`, unary `+ - ~`, parentheses, and integer literals. **Not Python integer semantics.**
- Addition, subtraction, multiplication and unary negation wrap modulo `2**width`.
- `>>` is logical, not sign-extending. Shift counts are same-width bitvectors; counts at least the width yield zero. For example, at width 8, `x << (255 + 1)` shifts by zero.
- Literals must fit the width. Write `-1` to construct the all-ones vector, not an oversized literal. At width 8, `256` is rejected.
- No calls, imports, attributes, indexing, assignments, loops, division, comparisons or arbitrary Python execution.
- Up to 8 variables, 64 KiB of UTF-8 JSON, 2048 characters per expression, 256 AST nodes, 32 levels. Duplicate JSON keys, unknown fields and booleans used as integers are rejected.

This explicitly differs from C integer promotions and undefined shifts, signed overflow, saturating quantization, floating point, and LLVM poison/undef semantics. If you need LLVM transformation validation, use [Alive2](https://github.com/AliveToolkit/alive2); for general logic, use [Z3](https://github.com/Z3Prover/z3) directly. BitEquiv is not a performance optimizer and makes no constant-time or security claim.

## Why another tool?

Z3 already supplies the hard reasoning. BitEquiv adds a small declarative input format, strict language limits, independent witness replay, CI exit semantics, and readable offline evidence. The aim is to make small word-level rewrites easier to explain and regression-test, not to compete with full compiler verification or claim a novel algorithm.

Reports include canonical input SHA-256, solver version, budgets and the exact domain. The hash identifies normalized input, not a signature or proof certificate. Equivalent results still trust Z3 and our translation. The concrete interpreter shares the parser but not the symbolic operator implementation; independent does not mean independently developed or formally verified.

## Tests and contributing

```bash
python -m pip install .
python -m unittest discover -s tests -v
python scripts/check_mutations.py
python -m pip install build
python -m build
python scripts/check_package.py
```

The package check creates a temporary virtual environment, installs the built wheel and runs all supplied examples outside the source checkout; it may download dependencies.

The suite includes hand-calculated wrap/shift cases, exhaustive operator tables at widths 1–4, small-domain solver/enumerator comparisons, actual resource-limit unknowns, witness disagreement controls, and real subprocess CLI/file round trips. Targeted mutations run in temporary copies, never the live source tree. A passing suite does not establish full program correctness or measured user adoption.

Useful contributions include a minimized wrong-result case, independently checked semantic examples, or better diagnostics. New language operators require explicit concrete and symbolic semantics plus boundary tests. Do not silently broaden the supported language. See [the design](docs/DESIGN.md) for the implementation boundaries.

## Privacy and limitations

The package performs no network requests. Inputs are never executed as Python. Reports contain your expressions and counterexample values; **review before sharing private code**. HTML uses no JavaScript or external assets. The CLI does not modify inputs or existing output files. Multiple output writes are not an atomic transaction: a later I/O failure may leave an earlier newly created file. Run only one writer per output destination.

Not a hardened multi-tenant execution service. No proof certificates, full C programs, automatic LLVM extraction, minimal-witness guarantee, model-quality guarantee or hardware timing validation. Benchmarks and cross-platform claims must be measured, not inferred from implementation language.

## License and foundations

MIT. Z3 is a separately installed dependency under its own MIT license. The project is AI-assisted; review and reproducible evidence matter more than authorship marketing.

Semantics follow the [SMT-LIB fixed-size bitvector theory](https://smt-lib.org/theories-FixedSizeBitVectors.shtml) and the [Z3 bitvector guide](https://microsoft.github.io/z3guide/docs/theories/Bitvectors/).
