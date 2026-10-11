# Canonical Ruff current residual

The scoped canonical Ruff command is red at `c9d0941864a8`: 2,029 diagnostics across 767 reported paths and 55 rule codes. It traversed 6,136 effective Python files. The full JSON output and complete by-code/by-file classification are retained in ignored raw receipts below.

The deciding command ran from `policy-engine/` with Ruff `ruff 0.14.10`:

```text
.venv/bin/python -m ruff check --output-format json \
  --extend-exclude benchmarks \
  --extend-exclude tools/research/benchmarks \
  --extend-exclude tools/research/demos \
  --extend-exclude tools/research \
  src/polisyos tests tools schemas scripts examples \
  gcp/upload_gonka_secrets.py ops/cloud/gcp/upload_gonka_secrets.py \
  jax_bootstrap.py migrate.py
```

The largest rule counts are `I001` 682, `F821` 448, `F401` 260, `E501` 217, `RUF001` 98, `S110` 96, `ANN401` 45, `TC003` 15. The largest file counts are `src/polisyos/foundry/methods/catalog/causal/causal_engine/discovery.py` 213; `src/polisyos/data_forge/domains/academic/batch/_resolve_extract_api.py` 171; `src/polisyos/data_forge/domains/academic/batch/_resolve_extract_transformers.py` 116; `src/polisyos/foundry/methods/catalog/causal/causal_engine/sensitivity.py` 104; `src/polisyos/data_forge/domains/academic/batch/_resolve_extract_providers.py` 100; `src/polisyos/data_forge/domains/academic/batch/_resolve_extract_io.py` 97. Two `E902` entries come from the explicit input arguments `gcp/upload_gonka_secrets.py` and `scripts`; those paths are absent in the base tree as well as the current checkout. The scope declarations are in `tools/devx/workspace/_repo_hygiene.py:18` and `:20`; the file has the same blob at base and head, and both paths are absent from both trees.

Between exact base `93d6aa62a8d236667fdf322a5fc17962523b185e` and head `c9d0941864a801e3f143b5cc2e94ec1c26f72e22`, 890 changed Python paths are in the declared source scope; 886 appear in Ruff’s effective 6,136-Python-file manifest. The four excluded paths are `tests/unit/benchmarks/symbolic/test_helpers.py, tools/research/benchmarks/jax/bench_simulation.py, tools/research/demos/run_laffer_demo.py, tools/research/demos/run_mechanism_design.py`. None of the 886 changed effective Python paths has a diagnostic. This is a path-level result, not an inherited-green result: the effective input intersection is nonzero, and the active Ruff configuration changed.

The six changed Ruff configuration paths are recorded in the classification JSON. The active product-root chain moved from `ruff.toml -> architecture/tooling/ruff/generated.toml` to `ruff.toml -> ruff.generated.toml`. After normalizing config-relative glob prefixes, lint rule selection, ignores, confusables, and per-file ignore entries match except for removal of `src/polisyos/calibration/**`. The current output has zero diagnostics under `src/polisyos/calibration/`, so that removal does not explain this run’s failures. The current root config also adds `src = [".", "src"]`; this can affect import sorting and makes the 682 `I001` findings config-sensitive. No base Ruff replay was made, so the I001 introduction question remains `not_established`. The new `workspace_root.toml` fragment is not loaded by this product-root command.

There are no directly attributable changed-source Ruff findings. The whole result is `not_established` for P41 inheritance because 886 changed files intersect the actual input set and the active config changed. Do not report the global gate as inherited or green. This work identifies no E02 source-format/type diagnostic in a changed file. The two nonexistent input paths are a narrow, same-class command-scope defect: make the declared scope resolve existing paths as one rule, or carry both as a bounded residual until that owner decides the intended path. The remaining unchanged-file diagnostics cannot be attributed to the E02 range without relying on a proxy or an unperformed config replay.

P40 classification: **same canonical-Ruff red class, one level deeper**. The expanded effective-file denominator is 6,136 Python files, not only the edited paths. The paired E902s widen one scope-resolution issue; they should be handled by a general scope-path invariant rather than separate one-path patches. The falsifier was run: the exact effective file manifest shows a nonzero changed-path intersection and zero changed-path diagnostics, disproving both “the full result is disjoint” and “changed source files account for the current findings.”

Evidence:

- Full diagnostics: `LOCAL/raw/canonical-ruff-current-residual-20261010/ruff.json` (SHA-256 `00fc7dedfea0a08db5fbadc5e6cfd01c5b334256d9f39007c01a26d94acbf34b`).
- Effective Ruff file manifest: `LOCAL/raw/canonical-ruff-current-residual-20261010/effective-files.txt` (SHA-256 `8d1cc03ea5357bb993aefba0cc50ce57b2866790ea9b34435758cf1209e9f1d4`).
- Complete by-code/by-file/by-file-code counts and Git intersection: `LOCAL/raw/canonical-ruff-current-residual-20261010/ruff-classification.json` (SHA-256 `8fef86aeab11c28e9f82aae5621183be56ee02f61f8078ccd02ae937467b8ee0`).

## Follow-up: shared authored-scope repair at `b45383cec354`

The preceding section records the pre-repair `c9d094` snapshot. At `b45383cec354a76fbb6bfb721f7a75e952bfa324`, the shared `AUTHORED_PYTHON_FORMAT_SCOPE` still named two paths absent from the product tree: `scripts` and `gcp/upload_gonka_secrets.py`. The relocated `ops/cloud/gcp/upload_gonka_secrets.py` is a real file and remains selected; the broader `tools` scope also remains. `format_check.py` and `lint_fast.py` consume the shared tuple (or its derived lint tuple), so the repair removes both stale entries once in `_repo_hygiene.py`. The test and companion search found no test pinning those entries; existing scope-sequence tests derive the command from the tuple. Historical receipts were preserved.

The canonical JSON lint command was rerun at the same HEAD before and after the tuple change. It fell from 2,029 to 2,027 diagnostics; `E902` fell by exactly two and every other rule count stayed the same. The effective manifest remained byte-identical at 6,143 paths, including 6,136 Python files (SHA-256 `8d1cc03ea5357bb993aefba0cc50ce57b2866790ea9b34435758cf1209e9f1d4`). The shared tuple now has no missing paths. `_repo_hygiene.py` is SHA-256 `7ed1b535f3a253e3cc53edf37429cac9a47ccd22742c7b3fa78ed0f748c65cb4`; its diff deletes only those two tuple entries.

The full format consumer also ran with the repaired tuple and reported no input-path errors. It remains red because 1,571 files would be reformatted and 4,758 are already formatted; that broader formatter debt is outside this repair. `ruff format --check tools/devx/workspace/_repo_hygiene.py` passes. The whole lint gate also remains red at 2,027 diagnostics, so this does not claim repository-wide lint closure.

P40 bucket: **same stale authored-scope path class, widened across the shared lint/format tuple**. Both sibling path failures are removed in one source owner and falsified through the real Ruff command, with the effective file manifest unchanged. This closes the current two-path instance without changing unrelated formatting or lint findings.

Follow-up receipts are in `LOCAL/raw/canonical-ruff-scope-repair-20261010/`: `before.json` SHA-256 `00fc7dedfea0a08db5fbadc5e6cfd01c5b334256d9f39007c01a26d94acbf34b`, `after.json` SHA-256 `164c3876c0a4e3336d2be98dc4821625abe87b8ecbbafefaa13e301235544344`, `after-effective-files.txt` with the unchanged manifest hash above, and `receipt.json` SHA-256 `bb1e0f037631b9f29b1f0e6c182600828acc6886bacefd66510387ba793ea1d8`. The complete format output is retained as `format-after.txt`.

## Follow-up: post-mechanical canonical Ruff snapshot at `6d514125`

The later product-root canonical Ruff command remained red: **229 findings in 65 finding-bearing paths** (63 `.py`, 2 `.pyi`). The count comes from every primary-location row in the complete JSON stdout, not a sample. The 65 are diagnostic paths, not the full Ruff input denominator: the command scans the listed source/test/tool roots, and this receipt does not include an expanded all-input file manifest. Do not equate 65 paths with the number of files Ruff analyzed.

The command ran at HEAD `6d514125e8c82ca3acad55d0f031ba7da2d1dbf8`, Ruff config `ruff.toml@8887d0a15457d44ebb1a5b5aee8110dd5101dc9e952649cd0490b845af2d933e` extending `ruff.generated.toml@51dd7d4fb4937537d815e7b791541c9f09b0b9f413ec06e6c69b221c0096d64f`, from the product root with this argv:

```text
.venv/bin/python -B -m ruff check --extend-exclude benchmarks --extend-exclude tools/research/benchmarks --extend-exclude tools/research/demos --extend-exclude tools/research src/polisyos tests tools schemas examples ops/cloud/gcp/upload_gonka_secrets.py jax_bootstrap.py migrate.py --output-format=json
```

It exited 1 in 0.211 seconds. Full deciding output is `LOCAL/raw/batched-blocking-focused-20261010/canonical-ruff-after-native-mechanical-r3/stdout.txt` (212,059 bytes, SHA-256 `100b7544fd49bfdccb2625f259bce0164fadff9e52258789fb15afc13145446f`); stderr is empty (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`). Exact argv/cwd/head, the 323-path before/after source/config hash subset, and output identities are in `command.json` (SHA-256 `5542f1cc768e24ba04c14185511d93e7aa8322ec7a53c9c6af6f8e1af304f6ae`). All 323 recorded hashes were unchanged during the run. This is a later snapshot than the `f52809e` 2,027-row receipt above; it is not a claim that the full repository is green.

### Complete finding-path inventory

The entries below are the complete set of 65 distinct paths in the JSON output. Counts and rule IDs are aggregated from all 229 rows; the raw output retains each message and source location.

| Findings | Path | Rule counts |
|---:|---|---|
| 1 | `migrate.py` | TC003×1 |
| 1 | `src/polisyos/common/hashing.py` | TC003×1 |
| 1 | `src/polisyos/data_forge/__init__.py` | RUF022×1 |
| 7 | `src/polisyos/data_forge/_impl/compliance.py` | ANN401×7 |
| 7 | `src/polisyos/data_forge/domains/academic/batch/_resolve_extract_api.py` | ANN401×2, I001×1, N806×2, SIM102×1, SIM113×1 |
| 11 | `src/polisyos/data_forge/domains/academic/batch/_resolve_extract_io.py` | ANN401×5, I001×1, S110×1, TC001×2, TC003×1, UP034×1 |
| 5 | `src/polisyos/data_forge/domains/academic/batch/_resolve_extract_providers.py` | I001×1, S311×3, UP034×1 |
| 5 | `src/polisyos/data_forge/domains/academic/batch/_resolve_extract_transformers.py` | I001×1, N806×1, SIM102×2, TC001×1 |
| 3 | `src/polisyos/data_forge/domains/academic/batch/resolve_extract.py` | I001×1, TC003×1, UP035×1 |
| 17 | `src/polisyos/data_forge/domains/catalog/batch/core_sources/transformers.py` | ANN401×12, B007×1, SIM117×1, TC001×2, TC003×1 |
| 30 | `src/polisyos/data_forge/domains/catalog/batch/core_sources/writers.py` | ANN401×14, S101×1, TC001×1, TC003×1, TC004×12, UP034×1 |
| 9 | `src/polisyos/data_forge/domains/catalog/batch/core_sources_ingest.py` | I001×1, SIM905×6, TC003×1, UP035×1 |
| 1 | `src/polisyos/data_forge/domains/legal/corpus/structure.py` | ANN001×1 |
| 3 | `src/polisyos/data_forge/read_api/compliance.py` | TC003×3 |
| 1 | `src/polisyos/ddm/integration/model_registry.py` | TC003×1 |
| 1 | `src/polisyos/fabric/identity/__init__.py` | I001×1 |
| 3 | `src/polisyos/fabric/quality/quality.py` | S608×3 |
| 1 | `src/polisyos/foundry/methods/artifacts/__init__.py` | I001×1 |
| 1 | `src/polisyos/foundry/methods/artifacts/_fingerprint.py` | S603×1 |
| 1 | `src/polisyos/foundry/methods/catalog/causal/causal_engine/discovery.py` | I001×1 |
| 1 | `src/polisyos/foundry/methods/composer.pyi` | I001×1 |
| 1 | `src/polisyos/foundry/methods/registry.pyi` | I001×1 |
| 3 | `src/polisyos/policy_grammar/_impl/compiler.py` | TC001×3 |
| 2 | `src/polisyos/policy_grammar/_impl/facets.py` | TC001×2 |
| 1 | `src/polisyos/policy_grammar/_impl/normalizer.py` | TC001×1 |
| 1 | `src/polisyos/policy_grammar/_impl/schema.py` | TC003×1 |
| 1 | `src/polisyos/runtime/http/_openapi_contract_helpers.py` | TC003×1 |
| 2 | `src/polisyos/runtime/http/services/control/admission.py` | ANN401×2 |
| 3 | `src/polisyos/runtime/http/services/control/production_data.py` | ANN401×3 |
| 1 | `src/polisyos/runtime/http/services/lineage.py` | S106×1 |
| 1 | `src/polisyos/runtime/quality/substrate_registry.py` | ANN401×1 |
| 1 | `src/polisyos/scholar/discover/transport.py` | TC003×1 |
| 1 | `src/polisyos/scientist/methods/search/contracts.py` | I001×1 |
| 1 | `src/polisyos/scientist/nodes/builtins/decide/build_decision_packet.py` | F403×1 |
| 1 | `tests/integration/scientist/test_checkpoint_resume.py` | S102×1 |
| 2 | `tests/property/foundry/methods/catalog/bayesian/test_bayesian_properties.py` | N806×2 |
| 4 | `tests/property/foundry/methods/catalog/causal/test_causal_properties.py` | S110×4 |
| 1 | `tests/property/foundry/methods/catalog/causal/test_did_properties.py` | S110×1 |
| 6 | `tests/property/foundry/methods/catalog/distributional/test_distributional_properties.py` | B007×1, S110×5 |
| 4 | `tests/property/foundry/methods/catalog/distributional/test_mobility_properties.py` | S110×4 |
| 8 | `tests/property/foundry/methods/catalog/econometrics/test_econometrics_properties.py` | S110×8 |
| 4 | `tests/property/foundry/methods/catalog/forecasting/test_forecasting_properties.py` | S110×4 |
| 3 | `tests/property/foundry/methods/catalog/mechanism/test_mechanism_properties.py` | S110×3 |
| 7 | `tests/property/foundry/methods/catalog/microsim/test_microsim_properties.py` | B007×2, S110×5 |
| 4 | `tests/property/foundry/methods/catalog/network/test_network_properties.py` | S110×4 |
| 1 | `tests/property/foundry/methods/catalog/optimization/test_lp_properties.py` | N806×1 |
| 7 | `tests/property/foundry/methods/catalog/optimization/test_optimization_properties.py` | B007×1, N806×1, S110×5 |
| 6 | `tests/property/foundry/methods/catalog/policy/test_policy_properties.py` | B007×1, S110×5 |
| 4 | `tests/property/foundry/methods/catalog/sensitivity/test_sensitivity_extended_properties.py` | S110×4 |
| 5 | `tests/property/foundry/methods/catalog/sensitivity/test_sensitivity_properties.py` | B007×1, S110×4 |
| 5 | `tests/property/foundry/methods/catalog/spatial/test_spatial_properties.py` | S110×5 |
| 3 | `tests/property/foundry/methods/catalog/survey/test_survey_design_properties.py` | S110×3 |
| 5 | `tests/property/foundry/methods/catalog/survey/test_survey_properties.py` | B007×1, S110×4 |
| 4 | `tests/property/foundry/methods/catalog/validation/test_validation_properties.py` | S110×4 |
| 1 | `tests/repo_quality/tools/test_layer3_gy_evidence_replay.py` | S110×1 |
| 1 | `tests/unit/core/phase0/test_metrics.py` | F821×1 |
| 1 | `tests/unit/foundry/methods/catalog/causal/test_causal_engine.py` | I001×1 |
| 2 | `tests/unit/scientist/search/strategies/test_space_codec.py` | S311×2 |
| 1 | `tools/archive/migrate_to_trinity.py` | TC003×1 |
| 3 | `tools/devx/refactor/move_module.py` | S603×1, S607×1, TC003×1 |
| 1 | `tools/ops_runners/experiments/run_msme_deadline_suite.py` | S112×1 |
| 1 | `tools/ops_runners/experiments/run_msme_e2e_showcase.py` | S311×1 |
| 2 | `tools/ops_runners/experiments/run_msme_final_fresg_suite.py` | ANN201×1, S311×1 |
| 2 | `tools/ops_runners/experiments/run_msme_final_fresg_suite_v2.py` | ANN201×1, S112×1 |
| 1 | `tools/quality/validation/check_layer3_gy_workflow_mode_truth_audit.py` | S110×1 |

Rule totals, summed over the full row set: ANN401 46; S110 75; TC003 16; I001 13; TC001 12; TC004 12; B007 8; N806 7; S311 7; SIM905 6; UP034 3; SIM102 3; S608 3; UP035 2; ANN201 2; S112 2; S603 2; and one each of ANN001, F403, F821, RUF022, S101, S102, S106, S607, SIM113, SIM117. The totals sum to 229.

### S110/S112: bounded absence versus swallowed behavior

Of the 75 `S110` rows, **72** are in 18 Foundry property-test files. All 72 catch bare `Exception` and pass; none names a permitted exception type. A complete AST check of these try bodies found 61 with Python `assert` statements, five with assertion-style `np.testing` calls, and six without direct assertion nodes. Seventy-one wrap generated method/property evaluation; the remaining `test_did_properties.py:40` wraps import plus method registration in an autouse fixture before `yield`, so a registration error is also suppressed. No affected try body uses Hypothesis `assume`/`reject` to delimit its caught branch. A method failure or assertion can therefore be reported as a passing property test, and a registration failure can leave a later test querying an unregistered method. One comment (`Small samples may legitimately fail`) is not a typed or row-visible error contract. These are not bounded expected-absence cases. The repair unit is the property-test mechanism across the slice: make generator preconditions explicit, use `assume` only for declared mathematical domains, assert successful outputs outside the exception catch, and separately test documented rejection cases with exact exception expectations.

The remaining three `S110` rows are distinct consumers. In `_resolve_extract_io.py:1231`, `pop()` catches any exception from `_read_at(offset)` despite an indexed key, then returns `args[0]` or raises `KeyError`; sibling `get()` also catches any exception and returns its default. `_build_index()` separately skips only `JSONDecodeError`/`UnicodeDecodeError`. A malformed or changed indexed record, I/O failure, and legitimate miss are therefore conflated across both readers. In `tests/repo_quality/tools/test_layer3_gy_evidence_replay.py:149` and `tools/quality/validation/check_layer3_gy_workflow_mode_truth_audit.py:50`, `Exception` covers both importing `loguru` and calling `logger.remove()`. `loguru>=0.7.2` is a declared project dependency; an import/configuration failure is not documented as an expected absence. These two output-hygiene helpers should catch only a declared optional-import case if one exists, and let logger setup errors surface; the indexed cache must retain a specific missing/corrupt/read-failure contract.

The two `S112` rows also need separate decisions. `run_msme_deadline_suite.py:1078` catches every exception from `json.loads` and silently skips the line; the caller writes the resulting sample and can fall back from a keyword-filtered sample to the first 250 rows. There is no malformed-row count or incomplete-evidence status. If tolerant JSONL is intended, its rejected-line count and limitation need to reach the output; otherwise reject corrupt input. `run_msme_final_fresg_suite_v2.py:1687` probes optional `pymc_bart` then `bartpy`, so a genuinely missing candidate is a legitimate bounded availability case. Catch-all `Exception` also misclassifies a broken installed backend or its initialization failure as absence; limit the optional branch to exact missing-module conditions and surface other import failures.

No per-file rule exception currently makes these 77 rows accepted. `tests/unit/foundry/**` has a scoped `S110` ignore but does not cover `tests/property/foundry/**`; the broad `tests/**` list does not include `S110`. `src/polisyos/data_forge/domains/academic/batch/resolve_extract.py` has a specific `S110` entry, not its sibling `_resolve_extract_io.py`. `tools/ops_runners/**` includes `S110`, but not `S112`; `tools/quality/**` does not include `S110`. The Ruff output itself is the observed evidence that these rows are not suppressed in the actual command.

### Issuer and expiry facts

`architecture/tooling/static_analysis_overrides.toml` declares the following matching **report-only ownership scopes** for findings in this set. They do not suppress Ruff rows or grant a rule-level waiver. The shared issue points to the archived repository best-in-class Phase 5.5 tool-config-split plan.

| Scope covering reported paths | Owner / mode | Sunset | Qualification |
|---|---|---|---|
| `src/polisyos/data_forge/**` | `team-data-forge` / report_only | 2026-12-31 | Ownership covers source rows; it is not approval to keep the broad S110 fallback. |
| `src/polisyos/common/**` | `team-core` / report_only | 2026-12-31 | Covers `common/hashing.py`. |
| `src/polisyos/fabric/**` | `team-fabric` / report_only | 2026-10-01 | Expired as of this 2026-10-10 snapshot; covers the three S608 rows and identity import. No renewal or blanket exception inferred. |
| `src/polisyos/foundry/**` | `team-foundry` / report_only | 2026-12-31 | Covers source findings only, not the Foundry test files under `tests/**`. |
| `src/polisyos/scientist/**` | `team-scientist` / report_only | 2026-12-31 | Covers the two Scientist source findings. |
| `src/polisyos/scholar/**` | `team-scholar` / report_only | 2026-12-31 | Covers the Scholar transport import. |
| `src/polisyos/runtime/quality/**` | `team-runtime-quality` / report_only | 2026-12-31 | Covers only `substrate_registry.py`; does not cover `runtime/http/**`. |
| `tests/**` | `team-quality` / report_only | 2026-12-31 | Applies as ownership to all test paths; its generic row is not a per-rule suppression. |
| `tools/**` and root `*.py` | `team-devx` / report_only | 2026-12-31 | Covers tool and `migrate.py` findings. |

The report-only registry also says `phase_3_6_dead_override_gate.fail_closed_not_before = 2026-10-01`, but the active status/mode remains report-only. Treat that as a governance transition fact, not as issuer acceptance of any current finding. `policy_grammar`, `ddm`, and `runtime/http` have no matching `override_scope` entry in this registry. Do not infer an owner, renewal, or exception for them from a neighboring package scope.

### Generic repair groups and disjoint author leases

Use these non-overlapping pathsets if the root assigns writers. Attach a focused import/runtime or property-semantic check to each group; do not replace this list with per-line noqa entries or broad `--fix`.

| Lease | Paths | Findings | Repair discriminator |
|---|---|---:|---|
| Data Forge catalog core sources | `src/polisyos/data_forge/domains/catalog/batch/core_sources/{transformers.py,writers.py}` and `src/polisyos/data_forge/domains/catalog/batch/core_sources_ingest.py` | 56 | `writers.py` has 12 TC004 runtime-used imports currently under `TYPE_CHECKING`; preserve lazy split/cycle behavior while aligning actual runtime imports and proxy contracts. Couple related annotation/loop/import cleanup in this exclusive pathset. |
| Data Forge academic extraction | `src/polisyos/data_forge/domains/academic/batch/{_resolve_extract_api.py,_resolve_extract_io.py,_resolve_extract_providers.py,_resolve_extract_transformers.py,resolve_extract.py}` | 31 | Type/IO contract, cache failure semantics, provider jitter, and facade import topology; no blanket `Any` or fallback. |
| Data Forge adjacent modules | `src/polisyos/data_forge/__init__.py`, `src/polisyos/data_forge/_impl/compliance.py`, `src/polisyos/data_forge/domains/legal/corpus/structure.py`, `src/polisyos/data_forge/read_api/compliance.py` | 12 | Sort public exports; type decoded compliance boundary; keep read API annotations import-safe. |
| Foundry property tests A | `tests/property/foundry/methods/catalog/{causal/test_causal_properties.py,causal/test_did_properties.py,econometrics/test_econometrics_properties.py,forecasting/test_forecasting_properties.py,mechanism/test_mechanism_properties.py}` | 20 | Rebuild the generator/error boundary; assertions must fail rather than be swallowed. |
| Foundry property tests B | `tests/property/foundry/methods/catalog/{distributional/test_distributional_properties.py,distributional/test_mobility_properties.py,microsim/test_microsim_properties.py,network/test_network_properties.py,survey/test_survey_design_properties.py,survey/test_survey_properties.py}` | 29 | Same property-test mechanism; includes four unused loop variables. |
| Foundry property tests C | `tests/property/foundry/methods/catalog/{bayesian/test_bayesian_properties.py,optimization/test_lp_properties.py,optimization/test_optimization_properties.py,policy/test_policy_properties.py,sensitivity/test_sensitivity_extended_properties.py,sensitivity/test_sensitivity_properties.py,spatial/test_spatial_properties.py,validation/test_validation_properties.py}` | 34 | Same property-test mechanism; includes matrix-symbol naming and three unused loop variables. |
| Runtime source | `src/polisyos/runtime/http/_openapi_contract_helpers.py`, `src/polisyos/runtime/http/services/control/{admission.py,production_data.py}`, `src/polisyos/runtime/http/services/lineage.py`, `src/polisyos/runtime/quality/substrate_registry.py` | 8 | Runtime payload types and scope-label false-positive review; keep runtime imports and public annotation semantics intact. |
| Fabric source | `src/polisyos/fabric/identity/__init__.py`, `src/polisyos/fabric/quality/quality.py` | 4 | Resolve the 3 validated-identifier SQL diagnostics with hostile-identifier tests; Fabric report-only sunset is already past. |
| Foundry source | `src/polisyos/foundry/methods/artifacts/{__init__.py,_fingerprint.py}`, `src/polisyos/foundry/methods/catalog/causal/causal_engine/discovery.py`, `src/polisyos/foundry/methods/{composer.pyi,registry.pyi}` | 5 | Import order plus subprocess command provenance and type-stub imports. |
| Policy grammar | `src/polisyos/policy_grammar/_impl/{compiler.py,facets.py,normalizer.py,schema.py}` | 7 | Check runtime/Pydantic annotation needs before moving imports into `TYPE_CHECKING`. |
| Scientist source | `src/polisyos/scientist/methods/search/contracts.py`, `src/polisyos/scientist/nodes/builtins/decide/build_decision_packet.py` | 2 | Preserve facade export set when replacing or narrowly documenting the star re-export. |
| Ops experiment runners | `tools/ops_runners/experiments/{run_msme_deadline_suite.py,run_msme_e2e_showcase.py,run_msme_final_fresg_suite.py,run_msme_final_fresg_suite_v2.py}` | 6 | The two S112 branches are semantically distinct; also make runner APIs typed and keep seeded experiment RNGs reproducible. |
| Other tools / root script | `migrate.py`, `tools/archive/migrate_to_trinity.py`, `tools/devx/refactor/move_module.py`, `tools/quality/validation/check_layer3_gy_workflow_mode_truth_audit.py` | 6 | Keep Git invocation argv/cwd controlled; narrow logger setup handling; move type-only imports only when runtime safe. |
| Common / DDM / Scholar | `src/polisyos/common/hashing.py`, `src/polisyos/ddm/integration/model_registry.py`, `src/polisyos/scholar/discover/transport.py` | 3 | Confirm runtime annotation/import requirements before the mechanical type-import move. |
| Other tests | `tests/integration/scientist/test_checkpoint_resume.py`, `tests/repo_quality/tools/test_layer3_gy_evidence_replay.py`, `tests/unit/core/phase0/test_metrics.py`, `tests/unit/foundry/methods/catalog/causal/test_causal_engine.py`, `tests/unit/scientist/search/strategies/test_space_codec.py` | 6 | Separate fixed-code test `exec`, missing `pytest` import, logging setup, deterministic RNG, and import-order fixes. |

The disjoint lease totals sum to 229. Cross-cutting subtype groups should remain inside the file owner’s lease: ANN401’s 46 dynamic annotations (40 in Data Forge and 6 in Runtime) need typed boundary reasoning; the 53 import-order/type-placement rows (I001 13, TC001 12, TC003 16, TC004 12) are not one blind transformation because TC004 marks runtime use; and SIM/UP/B007/N806 cleanups are lower-risk companions, not reasons to expand selectors. The security-coded S101/S608/S603/S607/S106/S102/S311 findings need the path-specific review above; a classifier message is neither proof of exploitability nor authority for a blanket suppression.

P40: **S110 property swallowing is one repeated mechanism**, so repair generator/error/assertion boundaries as a complete suite slice, not 72 local exception annotations. The cache fallback, optional logger setup, JSONL parser, and optional backend import are separate consumers and need their own defined absence contracts. **TC004 is a separate import-mechanism class** from type-only TC001/TC003; moving all imports the same way would change runtime behavior. P37/P38: Ruff directly recomputed its diagnostics from the scoped inputs, but this JSON is not the expanded all-file input inventory; its 65-path projection cannot prove whole-input disjointness or any semantic gate. P41 remains not_established for inheritance against an earlier slice because this note has no exact-base complete-input replay. All 18 repository SOTA child rows remain UNRUN per the separate native wave plan; this Ruff command executed none of them.
