# BitEquiv design

A focused local workflow for checking two fixed-width integer expressions and understanding a concrete counterexample. This is a Z3-backed tool, not a new solver, C interpreter, LLVM validator, or proof certificate checker.

## Contract

Python 3.11+, Z3 4.12–4.x. No cloud service, model download, API key, or GPU. Each problem is a strict JSON object with `width` (integer 1–64), `variables` (up to 8 distinct ASCII identifiers), `left`, `right` (expressions), optional `ranges` mapping names to inclusive unsigned `[min,max]`, and optional `title` (plain text, at most 120 characters). Unknown keys, duplicate JSON keys, undeclared names, booleans masquerading as integers, empty intervals, and out-of-range bounds/literals are invalid.

Only integer literals, variables, parentheses, unary `-`, `~`, `+`, and binary `+ - * & | ^ << >>` are accepted. Python syntax and precedence are used, NOT Python integer semantics. Every operand and intermediate is the same width; arithmetic wraps modulo 2^width. `>>` is logical; shift count is itself a same-width value, and a count at least width yields zero. Constants must fit the width; negative values can be expressed using unary minus. No division, comparison, calls, indexing, attributes, strings, floating point, imports, or arbitrary code execution.

Limit input JSON to 64 KiB, each expression to 2048 characters, AST to 256 nodes and 32 levels. User variable values must fit declared ranges. A valid empty variables list is a constant expression domain with one assignment. Cartesian nonempty ranges establish that the domain is nonempty without another solver call.

## Outcomes

- `equivalent`: Z3 proved the inequality unsatisfiable over the declared domain. Not a proof about the generating program, C undefined behavior, performance, timing, or side channels. The solver and translation remain trusted.
- `different`: Z3 found an assignment; an independent Python bitvector interpreter evaluates both expressions, checks range membership and agrees with BOTH solver outputs. Include per-node intermediate values and differing bits. Failure of replay becomes `unknown`, never a counterexample claim.
- `unknown`: resource limit, timeout, solver failure, missing solver, or a replay disagreement. No equivalence claim.
- `invalid`: rejected input or options. CLI exit codes 0 / 1 / 2 / 3 respectively for equivalent / different / unknown / invalid; operational output failures also exit 3.

Default solver timeout 5000 ms (maximum 60000) and resource limit 2000000 (maximum 20000000). These constrain Z3 checking, not a hard whole-process memory or wall-clock sandbox. No concurrency guarantee for the Python API; independent CLI processes are the recommended parallelism boundary.

## Architecture

`language.py` strictly parses and validates; `evaluate.py` evaluates concrete values with Python integers; `solver.py` separately lowers the AST into Z3 bitvectors, checks inequality, and replays models; `report.py` builds fully escaped static HTML; `cli.py` handles bounded JSON reads and explicit file outputs. No filesystem/network access from expression evaluation. Canonical input SHA-256 and solver version accompany every valid report. JSON reports contain expressions and concrete witness values: treat them as source code if inputs are sensitive.

HTML is self-contained with CSS, no JavaScript, fonts, external assets, or telemetry. Native details/summary provides expandable traces. JSON/HTML output creation refuses to overwrite existing files; it must not overwrite the problem file. Static example report comes from a real CLI run, not a hand-written verdict.

## Examples and tests

1. Shift distribution `(x+y)<<1` vs `(x<<1)+(y<<1)` is equivalent under wrapping.
2. Unsafely shifted mean `(x+y)>>1` vs `(x&y)+((x^y)>>1)` differs on overflow; restricted to x,y ≤127 at width 8 it agrees.
3. `(x<<1)>>1` loses the high bit; logical right shift of a high bit never sign-extends.
4. Saturation is not wrapping: no saturating arithmetic claim.

Test every binary/unary operator, fixed and variable shifts, width boundaries, deterministic parser limits, executable-looking rejected input, canonical fingerprints, range preconditions, constant-only problems, independent exhaustive small domains, witness traces, mocked solver-unknown and replay disagreement, and real CLI round trips. Exhaustive comparison must use the independent concrete evaluator rather than prefilled expected results. Add targeted source mutations in isolated copies, never mutate a shared worktree.

## Relationship to other tools

Z3 supplies the reasoning engine. BitEquiv adds a bounded input format, explicit unsigned semantics, independent witness replay and shareable offline reports. It does not replace SMT-LIB/Z3 for general logic or Alive2 for LLVM transformations. This limited convenience/teaching value is a positioning hypothesis, not evidence of adoption or originality.

Primary semantics: https://smt-lib.org/theories-FixedSizeBitVectors.shtml and https://microsoft.github.io/z3guide/docs/theories/Bitvectors/ . The fixed-size theory defines word-level arithmetic and unsigned shifts separately from host-language semantics.
