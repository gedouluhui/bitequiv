# BitEquiv 0.2 Evidence Workflow Implementation Plan

> Execution: inline, test-first. Independent reviewers are read-only; this checkout has one writer. Prior 0.1.0 implementation is frozen at its release tag, not rewritten.

**Goal:** Let a user export the exact verification problem and independently replay a shared counterexample report.

**Architecture:** Existing strict parser produces immutable nodes. A new SMT-LIB emitter translates them without Z3. A new evidence verifier validates and replays report input, never trusting a saved verdict. CLI subcommands retain separate result/exit vocabularies.

**Tech Stack:** Python 3.11+, unittest, existing Z3 runtime, optional cvc5 development extra. Static HTML remains script-free.

**Spec:** [DESIGN.md](DESIGN.md), section “0.2 evidence workflow”.

## Global constraints

Same 1–64 bit language and nonempty unsigned domain as 0.1.0; no new operators. Problem input at most 65536 bytes, report input at most 1048576 bytes. No arbitrary SMT import/execution. No external solver in production. No changes to existing release assets or remote repositories. Only this source directory is authoritative; use branch evidence-v0.2 and build new artifacts beneath artifacts/v0.2.0.

## 1. Independent SMT-LIB export

Files: create `src/bitequiv/smtlib.py`, `tests/test_smtlib.py`; extend `cli.py` and `tests/test_cli.py`.

Interfaces: `export_smt2(problem: Problem | dict) -> str`; CLI `bitequiv export case.json --smt2 query.smt2`, stdout metadata includes status `exported`, problem fingerprint and query SHA256; exit 0 means export succeeded, not equivalence.

- [x] Write import-failing tests, then `export_smt2` tests for deterministic bytes, fresh names, no title injection, literal width and complete bounds.
- [x] Test exact singleton query behavior with Z3 parsing, independent of `to_z3`: x=128 with x>>1 must equal64; x=255 with (x+1)>>1 must equal0; x=128 with (x<<1)>>1 differs from x.
- [x] Emit `(set-logic QF_BV)`, numbered declarations, unsigned lower/upper assertions, `(assert (distinct left right))`, `(check-sat)`. Convert operators explicitly; literal is `(_ bvN W)`, negation `bvneg`, invert `bvnot`, right shift `bvlshr`.
- [x] Run `PYTHONPATH=src .venv/Scripts/python.exe -m unittest discover -s tests -p test_smtlib.py -v` and full existing suite.

## 2. Untrusted report replay

Files: create `src/bitequiv/evidence.py`, `tests/test_evidence.py`; generalize strict JSON reading in `language.py`; extend `cli.py`, exports in `__init__.py`.

Interfaces: `replay_report(report: dict) -> dict`, `parse_report(text: str) -> dict`, CLI `bitequiv replay report.json`. Every output uses `verification_status` and explanatory scope. Return verified_counterexample=0, mismatch=1, unverifiable=2, invalid=3.

- [x] Generate test reports by actually running `check`, not prefilling verdict fixtures; replay real counterexamples and historical stored example.
- [x] Deep-copy a real report, then separately mutate problem, fingerprint, schema version/type, either output, intermediate source/value/binary, assignment/range, different_bits, replay marker and domain count. Each must stop verification for the appropriate named reason.
- [x] Reject duplicate JSON keys and over-limit data. Equivalent/unknown/invalid reports return unverifiable without running Z3. Confirm this in a subprocess whose import hook rejects z3.
- [x] Validate the problem anew, compare canonical fingerprint, recompute the complete witness with the independent concrete evaluator; compare nested values type-strictly so True cannot match1. Historical solver metadata is explicitly not authenticated.
- [x] Run new tests and all old tests. Preserve original CLI file-protection and stdout-failure regression behavior.

## 3. Independent-engine controls and release integration

Files: create `scripts/check_cross_solver.py`; extend `scripts/check_mutations.py`, `scripts/check_package.py`, tests for installed CLI, `pyproject.toml`, version source, `.github/workflows/ci.yml`, README files and existing verification documentation.

- [x] Validate cvc5 parser against a literal read-only QF_BV query before implementing a driver. Only feed product-generated SMT-LIB, use timeout/resource options and an outer subprocess deadline.
- [x] Use an explicit deterministic corpus with real equivalent/different cases, each operator, widths1/2/4/8/32/64, singleton and ranged domains. Compare in-process Z3 to both parsers. Obtain each SAT model and check its assignment independently; unknowns are visible non-passing outcomes, not omitted rows. Explicit cross-check must fail when cvc5 is absent.
- [x] Add source mutations for logical-right-shift exporter, omitted bounds, wrong identity/replay verdict, bool/int confusion and disabled trace verification. Keep live source untouched and require named assertion failures.
- [x] Read version from pyproject.toml in package verification; add --dist-dir; build0.2.0 separately. Install wheel in fresh environment without Z3 first to prove export/replay have no solver import, then install declared dependencies and test check/export/replay console flow outside checkout.
- [x] Update CLI docs with exact command-dependent exit codes, private report caveats and distinction between replay, solver agreement and proof certificates. Do not replace the published historical demo or claim a new public release.
- [x] Request read-only review and reproduce findings before fixes. Two reviews returned additional issues; each was fixed with regression controls. The final follow-up reviewer was rejected before execution (403 quota), so post-fix checks are owner-run, not independent approval.
- [ ] Freeze the tested commit/file fingerprints and report to the release coordinator. No remote publishing from this session.

## Acceptance commands

```bash
PYTHONPATH=src .venv/Scripts/python.exe -m unittest discover -s tests -v
PYTHONPATH=src .venv/Scripts/python.exe scripts/check_cross_solver.py
.venv/Scripts/python.exe scripts/check_mutations.py
.venv/Scripts/python.exe -m build --outdir artifacts/v0.2.0/dist
.venv/Scripts/python.exe scripts/check_package.py --dist-dir artifacts/v0.2.0/dist
```

Known scope limits are explicit: shared parser and spec, no proof certificate, no all-version compatibility, no claim that artifact identity authenticates an author. Cross-engine agreement is a test, not a new mathematical guarantee.
