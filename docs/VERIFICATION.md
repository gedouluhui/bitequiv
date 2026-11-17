# Verification scope

## 0.2 local evidence-workflow verification

The 0.2 source extends the existing unsigned contract with a solver-independent SMT-LIB exporter and counterexample-report replay. It also fixes four review findings: caller-replaced Problem objects containing stale ASTs, Unicode normalization/comment stripping before AST validation, stderr failure corrupting an error response, and missing solver budgets in the HTML reproduction command. Each finding was reproduced by a failing regression before its repair.

The local suite and targeted mutations exercise both existing and new paths. `check_cross_solver.py` builds its fixed-width singleton expected values with plain integer operations, then compares the product's Z3 API path to its separately emitted query parsed by Z3 and cvc5. It checks equivalent and deliberately different variants, unsigned range identities, reserved source names, constant-only problems and actual SAT assignments. First full run: 580 cases, Z3 4.16.0 / cvc5 1.4.2, corpus SHA-256 `a8f30d074e393ff71b623981e6c669fa41ff26f269d4b9a14dd7bcff53dd48f1`. Counts and fingerprints in a new run must be recomputed, not assumed from this record.

Cross-solver equality is finite differential evidence. The parser/specification are shared; neither two agreeing solvers nor replayed JSON authenticates author identity, historical execution or a universal proof certificate. Missing cvc5 fails the explicit cross-check command. Production export/replay do not import it or Z3.

The package checker first installs the wheel without solver dependencies and checks export/replay, then installs runtime dependencies and checks the examples from outside the source checkout. New local artifacts use a distinct version/output directory; published 0.1.0 artifacts are not rewritten. A second pair of read-only reviews found additional native-API and verification-boundary issues. All were reproduced and repaired: validate native JSON types/string keys before serialization can coerce them; validate raw Problem ranges before duplicate keys can be overwritten; preserve replay's result key on argument errors; protect help-output writes/flushes; and compare sdist build configuration and every source module against the checkout instead of relying on a good wheel. The archive checker has a passing complete-archive control plus document-only and modified-source negative controls. The owner reran all regressions, source mutations and cross-engine checks after these fixes. A requested final independent follow-up was rejected before execution by service quota (403), so no post-fix independent approval is claimed.

The 0.2 cloud matrix is configured but has not been claimed run here; publication is coordinated separately.

For the HTML budget fix, the owner generated an actual unknown report with timeout1234ms / rlimit1, opened it in the browser, extracted its reproduction command from the HTML and ran that command in a fresh temporary directory. The resulting JSON again reported unknown/exit2 and preserved both budget values; output JSON matched stdout. This tests the user-facing reproduction path, not just a string presence assertion.

## Historical 0.1.0 verification

Owner-run local verification, 2026-11-18 (UTC+8). Python 3.12.3, Z3 4.16.0, Windows x64. These checks do not establish adoption, speedup, correctness of full programs, or independent proof certificates.

## Reproducible gates

```bash
python -m pip install . build
python -m unittest discover -s tests -v
python scripts/check_mutations.py
python -m build
python scripts/check_package.py
```

The unit suite checks the strict input format, hand-calculated integer boundaries, logical shifts, exhaustive concrete/symbolic operator results for widths 1–4, equality verdicts against small-domain enumeration, unsigned range preconditions, genuine resource-limit unknowns, model replay disagreements, and real subprocess output/file behavior.

Mutation checking starts with a passing baseline, patches only isolated temporary copies and requires a specifically named assertion failure. It distinguishes assertion failures from import errors, syntax errors, arbitrary nonzero exits and no-op mutations. Controls exercise the classifier itself; live source SHA-256 values must remain unchanged. Its runtime output is the authoritative mutation inventory, rather than a hand-maintained count here.

The package check reads back the source archive and wheel, compares required members against source bytes, installs the wheel in a fresh temporary virtual environment, asserts that the imported package came from that environment and runs all bundled CLI examples from outside the checkout. Dependency downloads may be required. The initial source archive omitted examples and the Chinese guide; a failing package check caught this and `MANIFEST.in` was added.

## Independent review

A separate read-only reviewer inspected the core, tests and documentation. It reported one medium-priority defect: stdout write/flush failure could escape the handler or return an incorrect status. The owner reproduced write failure, flush failure and an actual OS pipe with its reader closed, then added regression tests and a guarded explicit flush. The error path returns 3 and redirects the failed output descriptor to the null device to prevent a second interpreter-shutdown flush from changing the exit code. A source mutation of that outcome is included in the mutation gate.

The reviewer reported no blocker demonstrating a false equivalence result within its scope. That is not formal verification or a blanket approval. The owner verified the repair; no second independent post-repair review has been claimed.

## Browser report checks

The stored example report was generated by the actual CLI. Its JSON witness was x=212, y=76, with outputs 16 and 144; both differ at bit 7, and the intermediate wrapped sum is 32. Solver versions may select another valid witness.

The owner inspected screenshots at a desktop viewport and the actual minimum 501-pixel browser window, then used a 360-pixel mobile viewport override. The 360-pixel document scroll width was 360: no horizontal page overflow in this example. Tab focused the left trace disclosure; Enter changed it from closed to open and exposed the five actual trace rows. The example had no script elements or external resource requests.

These are scoped checks on this stored example, not a comprehensive accessibility certification, arbitrary-report fuzzing, or Firefox/Safari/real-phone testing. The browser screenshot-to-workspace operation was denied by its path policy; read-only inline screenshots were inspected instead. No path permissions were changed.

## Cloud CI

[Run 44172468713](https://github.com/gedouluhui/bitequiv/actions/runs/44172468713) passed for release commit `53f1f616bf42eb62f0695885b4a3bd6a2894f822`: Windows and Ubuntu, each on Python 3.11 and 3.12. Each job runs tests, targeted mutations, packaging and a clean-wheel check. This is evidence for those CI environments, not every dependency version or operating system.

## Not yet established by these checks

- Compatibility across the entire declared Z3 version range; local testing used the version above.
- Minimal counterexamples, whole-process memory bounds or strict wall-clock deadlines.
- Full C/LLVM, signed-language overflow/poison semantics, floating point, saturation, or multi-tenant isolation.
- Real external users or any Star growth.
