# BitEquiv Implementation Plan

> Execute inline with test-first checkpoints. Independent review is requested once the implementation exists; service availability is reported honestly.

**Goal:** Check unsigned fixed-width expression equivalence and export independently replayed counterexample evidence.

**Architecture:** Strict JSON/AST front end, separate concrete and symbolic interpreters, bounded Z3 query, escaped static report, CLI. No arbitrary code evaluation or network behavior in the package.

**Tech Stack:** Python 3.11+, unittest, z3-solver >=4.12,<5, setuptools, static HTML/CSS.

**Spec:** [DESIGN.md](DESIGN.md).

## Global constraints

Width 1–64; at most 8 variables; JSON at most 65536 bytes; expression at most 2048 characters; AST at most 256 nodes / 32 levels. Solver timeout 5000 ms by default, maximum 60000; rlimit 2000000 by default, maximum 20000000. No changes outside this independent project except its designated local handover entry. MIT code; retain solver attribution.

## 1. Language and concrete execution

Files: `src/bitequiv/language.py`, `evaluate.py`, `tests/test_language.py`.

Interface: `Problem.from_dict(data)`, `parse_json(text) -> Problem`; `evaluate(problem, side, values) -> {value, steps}`. Problem has `width`, `variables`, `ranges`, `left`, `right`, `title`, `left_ast`, `right_ast`, `to_dict()` and `fingerprint`.

- Write tests using 8-bit `x+1` at x=255 => 0, logical `x>>1` at x=128 =>64, `(x<<1)>>1` at x=128 =>0, and overshift =>0.
- Verify initial tests fail because package functionality is absent.
- Implement strict schema, bounded AST traversal, operator allowlist, and separate pure evaluator without eval/exec.
- Run `python -m unittest discover -s tests -p test_language.py -v`.

## 2. Equivalence engine

Files: `src/bitequiv/solver.py`, `tests/test_solver.py`.

Interface: `check(problem, *, timeout_ms=5000, rlimit=2000000) -> dict`. JSON-compatible report carries status, problem, fingerprint, solver version, coverage explanation, witness if different, and reason if unknown.

- Assert overflowing mean is different, the x,y≤127 domain is equivalent, wrapping distributivity is equivalent, and constant-only problems work.
- Cross-check a deterministic family of small-domain expression pairs against independent enumeration.
- Lower operators with unsigned Z3 comparison and `LShR`; guard check outcomes, replay model outputs and range membership before reporting different.
- Test unknown and replay mismatch using narrowly scoped mocks with named diagnostics; validate budget booleans and out-of-range inputs.

## 3. CLI and report

Files: `src/bitequiv/cli.py`, `__main__.py`, `report.py`, `tests/test_cli.py`.

Command: `python -m bitequiv check examples/overflow-mean.json --json result.json --html result.html`.

- Write real subprocess tests for exit 0/1/2/3, JSON reread, exclusive output creation and input preservation, missing input, malformed JSON, and malicious title escaping.
- Implement bounded input reads, strict options and exclusive UTF-8 output files. Print JSON to stdout; human diagnostics to stderr only on operational failure.
- Render static escaped report with numerical and bit-level counterexample, separate expression traces, input-domain summary and explicit evidence limits.

## 4. Packaging and release verification

Files: `pyproject.toml`, `.gitignore`, `LICENSE`, `README.md`, `README.zh-CN.md`, `examples/*.json`, `.github/workflows/ci.yml`.

- Package src layout with command `bitequiv = bitequiv.cli:main`.
- Run unit tests, compileall, real example commands and package build.
- Install wheel into a second project-local venv, run CLI from outside source directory, compare saved reports.
- Run targeted mutations in separate temporary copies; never modify live sources concurrently.
- Check HTML in a separate browser tab, including narrow viewport and literal escaping.
- Request independent source review; record any unavailable verification, repair verified findings, rerun checks.
- Inspect explicit release file list and secrets; initialize only this repository, commit and publish using normal GitHub authorization; verify remote HEAD and CI before claiming published.
