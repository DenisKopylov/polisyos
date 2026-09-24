# R14 test-input safety audit

## Verdict

The R14 four-base test-file replay has one statically confirmed file-level safety blocker. Mark the whole-file cells for `policy-engine/tests/integration/runtime_quality/test_data_state_substrate.py` **UNRUN** at all four pinned bases. Its test `test_l5_proxy_identification_materializes_bounded_state_and_toggle_changes_it` calls `_repo_with_household_identification_mode`, which executes `shutil.copytree` from the appointed production-data D2 directory into a temporary repository before modifying the copy. The source data tree is read-only and must not be copied, so the whole file cannot run under the current harness. This is the same hazard already recorded in `P41_SAFETY_AUDIT.md`; R14 independently confirms it in the complete R14 file union.

The four exact source cells are:

| Pinned base | Test source blob | Copy call |
|---|---|---|
| E02 execution base `78187878ee188ff6d27442ba1498bd094da9785b` | `9e916b3310ee70bd9112d2db1a2b0508c8e7f65d` | line 177 |
| E02 head `00d946c2b7d052522be092f9c70eb9902f6521c2` | `bae992dfe8986d82559a1898cf4f1076632a977d` | line 178 |
| main `5fd3ebcc15637e98bbd4938de5d62ee5004504a8` | `9e916b3310ee70bd9112d2db1a2b0508c8e7f65d` | line 177 |
| Phase 0 merge `73c656744f051d9f40667da7f8bc91c61d8b4ebf` | `bae992dfe8986d82559a1898cf4f1076632a977d` | line 178 |

In both versions, `_L5_D2_DIR` resolves below `production_data/canonical/local_data_20260501/ukraine_server_support_20260410/runtime_calibration_internals/calibration/d2`; the copy source is `REPO_ROOT / _L5_D2_DIR`. The test then changes only the destination copy. No test was run for this audit.

## Complete four-tree denominator

The union was independently constructed from the paths returned by `git diff --name-only -z 78187878ee188ff6d27442ba1498bd094da9785b <revision>` for E02 head and main, deduplicated, and restricted to tracked `policy-engine/tests/**/test_*.py` paths. Git trees were enumerated with `git ls-tree -r -z --full-tree <revision>`; source presence and blob IDs were joined by exact path. Reproduction logic:

```text
U = union(diff_names(78187878e, 00d946c2b), diff_names(78187878e, 5fd3ebcc1))
U = {p in U | p starts with "policy-engine/tests/" and basename(p) matches "test_*.py"}
for r in [78187878e, 00d946c2b, 5fd3ebcc1, 73c656744]:
    T = {path: blob from ls-tree -r -z --full-tree(r)}
    present[r] = {p in U | p in T}
    cells[r] = |U|; absent[r] = |U| - |present[r]|
```

| Tree | Present test paths | Absent test paths | Path/base cells |
|---|---:|---:|---:|
| E02 execution base `78187878e` | 182 | 162 | 344 |
| E02 head `00d946c2b` | 274 | 70 | 344 |
| main `5fd3ebcc1` | 252 | 92 | 344 |
| Phase 0 merge `73c656744` | 344 | 0 | 344 |
| **Total** | **1,052 present cells** | **324 absent cells** | **1,376 cells** |

The 1,052 present cells contain 534 distinct `(path, blob)` source versions. Missing cells have no source blob to inspect and are reported as absent, not as passed or safe. The three repository-wide changed filenames matching `test_*.py` but outside `policy-engine/tests/` were excluded from this test-suite denominator: `policy-engine/architecture/atlas_surfaces/test_frontend_disposition_register.py`, `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/qa/test_verifier_controls.py`, and `policy-engine/docs/superpowers/journals/gy-builders/a/test_denominator_probe.py`. A repository-wide filename-only filter would produce 347 paths; the 344 count is the test-tree union.

## Static scan and disposition

Inspection read every present blob version in the denominator (534 distinct path/blob versions), without importing repository modules or executing tests. The static scan:

- resolved `shutil` module aliases and direct imports for `copy`, `copyfile`, `copyfileobj`, `copy2`, `copytree`, and `move`; reviewed every such call's source argument and enclosing helper/test;
- resolved `duckdb` module aliases and direct `connect` imports; inspected open arguments, read-only flags, SQL `ATTACH` statements, and production-data path references;
- searched source text for production-data roots, `POLISYOS_PRODUCTION_DATA_ROOT`, `cp -R`, `cp -c`, `rsync`, `ditto`, and tar-based duplication commands, then inspected matching call sites and literals.

The only production-data copy in the union is the D2 `copytree` above. No production-data-targeted writable DuckDB open or `ATTACH`, and no `cp -R`, `cp -c`, `rsync`, or `ditto` clone command was found. Tar references in the union are test archive fixtures; their paths are temporary fixtures, not the production-data tree.

Two nearby cases were checked to avoid a false positive. In `policy-engine/tests/unit/runtime/quality/test_proving_ground_substrate_grounding_search.py`, `_write_minimal_dcat_metric_binding` opens a DuckDB path writable, but its eight call sites use `tmp_path`, `canonical_root`, or `overlay_root`; none supplies `REPO_ROOT`. The separate `test_g1_catalog_search_finds_credit_access_from_construct_query` reads the real catalog through `DatasetCatalogStore`; its owner routes to `open_catalog_read_session`, which opens the baseline with `read_only=True` (`policy-engine/src/polisyos/data_forge/domains/catalog/knowledge/overlay.py@3008161c10dbf5d9726a2ab12737e8a7a188e109`).

This static verdict does not establish behavior of dynamically assembled callables, reflective imports, or shell commands assembled from nonliteral fragments. Those are `unresolved_by_construction`; no claim is made that static inspection proves arbitrary runtime behavior. The scan establishes that none of those mechanisms is explicitly present at the inspected production-data call sites. The R14 test runner must retain the four typed UNRUN cells until a safe behavior-test rewrite is committed.

## Closure signal

Replace the copying helper with a bounded test input that uses an owner-supported overlay or an explicitly synthetic scratch fixture and still demonstrates both sides of the proxy-to-point behavior. The test should also verify that the source production-data manifest digest is unchanged. The current proposed route and its unresolved owner-boundary question are documented in `P41_D2_SAFE_FIX_PLAN.md`; the whole-file replay remains UNRUN until the safe test is implemented and its four-base cells are re-established.

## Evidence references

- Hazardous test blobs: `policy-engine/tests/integration/runtime_quality/test_data_state_substrate.py@9e916b3310ee70bd9112d2db1a2b0508c8e7f65d` and `@bae992dfe8986d82559a1898cf4f1076632a977d`.
- Production catalog owner: `policy-engine/src/polisyos/data_forge/domains/catalog/knowledge/store.py@1f037ef49a940c80dd5592eac5e4bb5655699329` and `policy-engine/src/polisyos/data_forge/domains/catalog/knowledge/overlay.py@3008161c10dbf5d9726a2ab12737e8a7a188e109`.
- Related D2 safety audit and proposed test rewrite: `P41_SAFETY_AUDIT.md` and `P41_D2_SAFE_FIX_PLAN.md` in this package.
