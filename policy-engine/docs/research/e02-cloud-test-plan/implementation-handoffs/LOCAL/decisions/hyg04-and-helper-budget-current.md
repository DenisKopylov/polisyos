# HYG-04 and helper-budget current review

Date: 2026-10-10. Candidate checkout: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos`; product root: `policy-engine/`. The candidate remains WIP and was not frozen for this review. No Git operation, production JAX edit, helper-file edit, or G adjudication was performed. This packet records source/test assessment only.

## P40 buckets

- **HYG-04 reference census — same census-drift class, one level deeper.** The eight new matches are source/document references in closure and captured evidence records; the actual Python import caller set did not change. I kept the entire tracked match set in the census and classified each path. This is one bulk input change, not eight caller findings. If the same class recurs, stop adding path entries and widen to a source-bound document-role classifier; the current exact-path inventory is not a reusable classifier for future LOCAL records.
- **Hatch config lookup — new class.** HYG-04 read a retired `pyproject.toml[tool.hatch]` location while the live backend configuration is `hatch.toml`. The fix follows the canonical file and continues to assert that a duplicate `tool.hatch` table is absent.
- **Hatch sdist comparison — new class.** The packaging witness compared the declared force-include source set with the *artifact delta*, even when some forced files already existed in the legacy artifact. Its expected delta now subtracts old sdist members; full old/new byte parity remains asserted.
- **Helper topology — same helper-budget class, one level deeper.** The live graph now has zero forbidden reverse imports and zero unused paths, but the unchanged 23-vs-10 shared-helper count still fails. The reporter’s `unused` predicate is any static import, not the documented two-slice reuse rule. Do not make one import-line or baseline-count edits at a time.
- **Runtime mirror normalization — same coverage-measurement class, one level deeper.** The policy declares cross-module mappings, but the loose-ratio implementation matches filename stems only and does not consume the mapping rows. I made no reporter change; mapping semantics need an explicit owner decision and behavioral binding before they alter ratios.

## HYG-04 failures and repair

Baseline command, before edits:

```text
cd /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine
.venv/bin/python -m pytest -q tests/unit/remediation/test_hyg_04.py --junitxml=docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/hyg04-research-first/junit.xml
```

It reproduced **24 passed, 2 failed**. The original test bytes were SHA-256 `4c8504a43cc9d1f8e401dc2719b62d5a17e704aab653a32ccaf2c19145939c3e`; baseline stdout SHA-256 `96334d4c8ecdbe1eabf9145e506af468bb4523ec169c7effc08b902bb5430932`; JUnit SHA-256 `8505b337381711b7a35179844ccf906621d3b954f5386ca5f10d2ec53cf762dd`. Full baseline output and command receipt: `LOCAL/raw/hyg04-research-first/{stdout.txt,stderr.txt,junit.xml,command.json}`.

The caller census’s exact `git grep -I -l -F` selector is constructed in `tests/unit/remediation/test_hyg_04.py`. It searches the tracked tree for the three benchmark FQNs, the `from tools.research.benchmarks import` form, and both root-relative and `policy-engine/` file-path spellings. The file denominator is the test’s full declared text-suffix set plus `Dockerfile`, `Jenkinsfile`, `Makefile`, and `Procfile`; a match outside it fails. The source code then parses every matched `.py`/`.pyi` file and requires the sole AST importer to be the HYG-04 witness.

I captured the exact result of that selector without changing the source: **22 matched tracked paths**, with **one AST caller** (`tests/unit/remediation/test_hyg_04.py`) and no Python parse failures. The prior role list omitted eight documentary records: closure decision `C.md`, `coverage.json`, the C10 scanner diagnostic, two C10 source manifests, the C13 archive manifest, the F overlap inventory, and the measurement-plane survey. Their exact line contexts are retained in `LOCAL/raw/hyg04-research-first/new-reference-contexts.txt` (SHA-256 `e3c8915613a8ebf6553a7592bec5800262e4ca534a6812ffe08b7b5807a0a9ab`). The complete 22-path selector output is `tracked-grep-paths.txt` (SHA-256 `29ab7bde105f18f374a09880453625a04c327175aa2aa920b253f4c508318349`).

I renamed `non_caller_exemptions` to `documentary_reference_roles`, added explicit roles for those eight records, and kept the equality against the complete `matched_paths` set. No path was filtered from `git grep`, removed from the denominator, or broadly exempted. The post-edit set control reports 22 matches, 22 classifications, no missing paths, and no stale paths; raw control SHA-256 `06696b517535b4bad1cbda57f5ee8611b0b24b8a9203c0d735a3ac630585c141`.

The census falsifier injected an additional `README.md` result into the real selector output; `README.md` is already inside the test denominator. The actual test function failed on the unmatched path, with all original token/witness markers retained (`census-injected-unclassified-path.txt`, SHA-256 `8f9531759ed9762db96a2d098f01062465dc57d1c5132475eba6f937e8d76e01`). This proves that another unclassified path cannot turn green by being outside the path denominator. Future active documentation that instructs a user to execute a legacy entrypoint still requires human role review; the current test classifies document paths but does not parse every Markdown code example for invocation semantics.

The second baseline failure was a stale config path. `hatch.toml` is the canonical build config and contains `[build.targets.wheel]` plus `[build.targets.sdist]`; `pyproject.toml` intentionally contains no `tool.hatch` table. The HYG-04 package-boundary witness now parses `hatch.toml`, asserts the wheel package roots and sdist include/exclude boundaries, and asserts the duplicate pyproject table remains absent. Neither config file changed (`hatch.toml` SHA-256 `24ad192a85397fdf56e2722275e19adf79c10a27938640f5bc4f86353936efcd`; `pyproject.toml` SHA-256 `b205b652e2a16d342394988aa4a4dab0e2eb54acb0788ea8cc90c7b8cc10a267`).

The first real-backend positive run exposed an additional test assertion bug, not an artifact defect: two force-included worker files were already members of the old sdist, so they correctly did not appear in `new_sdist_members - old_sdist_members`. I changed the expected delta to `force_sources - set(old_sdist_members)` plus `hatch.toml`. All existing checks for wheel member hashes, unchanged legacy files, no old sdist member loss, and rebuilt-wheel equality remain. The initial red output is `hatch-native-after.stdout.txt` / `.xml`; the corrected real Hatch build and parity run passes in `hatch-native-after-fix.stdout.txt` / `.xml`.

Post-repair verification:

```text
.venv/bin/python -m pytest -q tests/unit/remediation/test_hyg_04.py
# 26 passed; JUnit: LOCAL/raw/hyg04-research-first/hyg04-final.xml

.venv/bin/python -m pytest -q tests/repo_quality/tools/test_hatch_packaging.py::test_native_backend_preserves_complete_wheel_and_sdist_contract
# 1 passed; 63.202 seconds; JUnit: LOCAL/raw/hyg04-research-first/hatch-native-after-fix.xml

.venv/bin/python -m ruff check --select E4,E7,E9,F tests/unit/remediation/test_hyg_04.py tests/repo_quality/tools/test_hatch_packaging.py
# All checks passed
.venv/bin/python -m ruff format --check tests/unit/remediation/test_hyg_04.py tests/repo_quality/tools/test_hatch_packaging.py
# 2 files already formatted
.venv/bin/python -m py_compile tests/unit/remediation/test_hyg_04.py tests/repo_quality/tools/test_hatch_packaging.py
# exit 0
```

For transparency, the default all-rules Ruff invocation over these two test modules exits 1 with 122 diagnostics (including assert, test typing, subprocess-path, and print rules); its complete concise output is `LOCAL/raw/hyg04-research-first/ruff-all-test-files.stdout.txt` (SHA-256 `4a591610c5e2ec96cdbf2f75b80a9acd0d268d78d1b4e17cb063db6c1a8b46a0`). I did not broaden this task into unrelated test-style cleanup.

The only source-tree edits in this assignment are the two test files: `tests/unit/remediation/test_hyg_04.py` (current SHA-256 `9664995c865e029c59c81f997b302fbd90630f6a709df0b42833a2bb99a947cc`) and `tests/repo_quality/tools/test_hatch_packaging.py` (current SHA-256 `a9715f30e89511b0a0b902b1ba11c252b74edefd5af537d3a1b3299a765dd4e9`). No production JAX, `hatch.toml`, or `pyproject.toml` edit was made.

## Helper topology and budget assessment

I independently called `report_test_ratchets._build_test_helper_topology_report()` using the current `architecture/tests/ratchets.toml` and baseline. The complete emitted report is `LOCAL/raw/hyg04-research-first/helper-topology-current.json` (SHA-256 `7a09390d6af9f8e8fad9e6da683c17902c5194d6e81affd8f967621c02c2f92b`). The run hashed the 2,945 Python files under `tests/**`, the ratchet TOML and baseline JSON (2,947 unique input paths); manifest SHA-256 `48d2f1734c2d6facc9034617e2c8b7eac07ff00d4eb3fa18a365cdfb93a2c13e`. Python was 3.14.3. Reporter, contract, and baseline source hashes are respectively `800609f4f72be54392390ee2929a67621f9a104facc3d9c715d8274d93ce2f2b`, `88a9a3595f82e7456fd483140aadcc1ef051dfc05b4375dfef1db87381f27792`, and `d3725f4bc510655204a00202be9081ea6851d017b9d986c3e6af31af3b17fee0`.

The complete summary is:

| Measure | Current | Baseline |
| --- | ---: | ---: |
| `shared_helper_files` | 23 | 10 |
| `layer_local_conftest_files` | 27 | 27 |
| `duplicated_fixture_factories` | 1 | 1 |
| `unused_helpers` | 0 | 0 |
| `forbidden_reverse_imports` | 0 | 0 |

Only the shared-helper file count is a reported regression. `report_test_ratchets.py::_find_helper_usages` scans Python imports and literal `pytest_plugins` declarations in the test tree; any test, conftest, or helper import makes a helper “used.” It does not count independent test slices, nor enforce `shared_helper_allowed_imports`. The documented helper extension rule is stronger: promote after two or more test slices; single-slice helpers stay local. Therefore `unused_helpers == 0` does **not** establish that all 23 modules are shared or reusable.

The current report makes the proxy concrete: `acquisition_human_decision.py` has one direct integration-test importer; `acquisition_movement.py` and `acquisition_supplier.py` each have one direct unit-test importer (the supplier helper also participates in helper composition); `b61_timeout_worker.py` has one direct unit-test importer; `causal_scm_fixtures.py` has one direct unit-test importer and is already part of the pinned ten. `acquisition_epoch_production.py` has one direct unit-test importer plus `acquisition_chain.py`. `observability.py` and `search_strategies.py` enter through root/local conftests, where the true pytest consumer set is broader than the importer file. Do not count those conftests as a single behavioral slice without resolving their fixture consumers. The two larger acquisition helpers and the chronology, HTTP, mirror-contract, HDS-quality, artifact, control-worker, and PDC-projection modules have multiple consuming tests/helpers in the report. The prior app-only catalog profile fixture is no longer in `tests/_helpers`; root reports that its app-owned move and context-equivalence check are complete.

The ratchet is `growth_policy = ratchet_update_required` plus `mode = fail_closed_no_regression`; the 10 value is the measured May baseline, not a declared maximum helper budget. Options for the owner/G decision:

1. Keep 10 unchanged while localizing only demonstrably single-slice additions and preserving semantically distinct, genuinely reused fixtures. Recompute the full graph after each owner move; do not merge unrelated helpers solely to reach ten.
2. If the full set of remaining modules is intentionally shared, make a G/owner budget decision to accept the new measured count and document why 23 semantic owners are necessary. Do not edit the generated date or baseline count alone to silence the red.
3. If the contract intends to enforce reuse rather than cap file count, add a separate measured `consuming_test_slices` property: record direct tests, conftest-provided consumers, and helper composition distinctly; name the slice partition; test a one-slice helper, a second independent slice, zero consumers, and the app/script dynamic-import boundary. This changes what the gate measures and needs an explicit contract decision. The smallest currently absent capability is a source-bound consumer/slice map with a real negative control; the current reporter does not produce it.

No helper topology source or baseline was changed.

## Existing module-mapping policy versus ratio implementation

`architecture/tests/ratchets.toml` says `runtime_over_coverage_policy = "Normalize runtime over-coverage through module mappings or declared cross-module behavior tests; raw test-file count does not satisfy module mirror presence."` It declares `runtime-http-cross-module-behavior` with `test_path = tests/unit/runtime/http`, source globs `src/polisyos/runtime/api.py` and `src/polisyos/runtime/http/**`, and `counts_toward = integration_coverage_decision`. Other normalization rows explicitly use `counts_toward = behavior_test_mapping`.

The live ratio mechanism does not consume those mapping rows: `_loose_test_names()` only extracts test filename stems, and `_build_package_report()` marks a source module as loosely mirrored only when its stem appears in that set. `report_test_ratchets.py` has no read of `coverage_normalization`, `counts_toward`, or the package `normalization` key. The package report does carry the separate `integration_decision` and `integration_path` fields, but it neither verifies the source/test globs nor incorporates their evidence into the module ratio.

Concrete discriminator: the current mapping selects `src/polisyos/runtime/http/routes/public_decisions.py`, which has no same-stem `test_public_decisions.py`. `app.py` imports and includes its router, and `tests/unit/runtime/http/test_public_decision_verification_routes.py` and `test_public_export.py` exercise the routes through `TestClient`. The current same-stem ratio does not recognize those cross-module tests for that source module. This is evidence that the declared mapping and ratio are different measures; it is **not** enough to declare every source under `http/**` behavior-covered. The mapping has 120 source modules; 45 lack a same-stem test filename in the current unit root, so each claimed mapped coverage needs source/test binding before a ratio can change.

The complete module census is `LOCAL/raw/hyg04-research-first/runtime-mapping-census.json` (SHA-256 `dde4b00796a61eb7c18be708bdc56277d8e1b480324edcbe40815e2461399921`); its source-input manifest is `runtime-mapping-input-manifest.json` (SHA-256 `f6c8d84632248ef45fb2efb47eefe7ef4c536315a54a57bf92c64d09d32cbe68`). A removal/narrowing-style mechanism control changed only the runtime normalization ID and declared mapping test/source selectors in memory while leaving runtime source and tests intact. `_build_payload()` returned identical runtime loose and strict mirror counts/ratios and the separate integration decision/path: the output fields were unchanged (`runtime-mapping-blindness-control.json`, SHA-256 `2f354dae766e390ea1b7efe8f96944b9cca252fece2cc022709c6757dfd45bb0`). Thus this is a present implementation/property divergence, not a hypothetical requirement to recursively test a generic mapper.

Before implementing mapping counts, preserve the existing filename-based ratio as a separate, unchanged metric and choose one explicit interpretation: mappings supplement the ratio, satisfy a separate integration criterion, or replace selected source modules in its denominator. A source-bound mapping should list the actual collected behavior tests per source group and contain removal/narrowing controls. The falsifier is to remove or alias a declared test while leaving its map row intact; the report must stop counting that mapped coverage. The five new runtime test candidates root says were skipped as aliases/already-covered paths are not legitimate ratio fillers and were not added here. This metric decision remains open; no ratio implementation, floor, exception, or baseline was changed.

## Commands and recorded evidence

The main commands and complete outputs are retained under `LOCAL/raw/hyg04-research-first/`:

- Baseline HYG-04 reproduction: `command.json`, `stdout.txt`, `stderr.txt`, `junit.xml`.
- Complete tracked citation set and line contexts: `tracked-grep-paths.txt`, `new-reference-contexts.txt`; complete post-edit map check and fail-closed injected-path probe: `census-classification-control.json`, `census-injected-unclassified-path.txt`.
- Post-edit HYG-04 and real Hatch artifact parity: `hyg04-final.stdout.txt`, `hyg04-final.xml`, `hatch-native-after-fix.stdout.txt`, `hatch-native-after-fix.xml`.
- First Hatch run’s assertion red: `hatch-native-after.stdout.txt`, `hatch-native-after.xml`.
- Helper topology source/consumer report and full Python-input hash manifest: `helper-topology-current.json`, `helper-topology-input-manifest.json`.
- Broad Ruff diagnostic output: `ruff-all-test-files.stdout.txt`.

These are pre-freeze measurements over the bytes hashed in the manifest, not a final composed candidate run. No original finding is formally closed by this note.
