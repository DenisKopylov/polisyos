# P41 production-data write/copy safety audit

## Scope and result

This was a read-only source census before the frozen baseline wave. The frozen
path set is the 100 unique entries in `BASELINE_HARNESS.py`
(sha256 `9fc09677e85757dc065bb864b905a1e43320ed40a1258a8b2ac6639e8e0c5c51`)
under the integration worktree. The four pinned trees are execution base
`78187878ee188ff6d27442ba1498bd094da9785b`, E02 head
`00d946c2b7d052522be092f9c70eb9902f6521c2`, main
`5fd3ebcc15637e98bbd4938de5d62ee5004504a8`, and Phase 0 merge
`73c656744f051d9f40667da7f8bc91c61d8b4ebf`.

The complete matrix is 100 paths × 4 trees = 400 path/base cells: 342 tracked
and 58 missing (71, 83, 88, and 100 present paths in the four trees,
respectively). The tracked cells contain 142 unique path/blob pairs and 142
distinct blob OIDs. Each present path/blob version was inspected once; absent
cells are not executable baseline inputs.

One frozen whole-file test copies from `production_data` and must be marked
`UNRUN` in all four cells unless the test is first made safe:

| Base | Test path and blob | Whole-file test that reaches the operation |
|---|---|---|
| `78187878e` (`78187878ee188ff6d27442ba1498bd094da9785b`) | `policy-engine/tests/integration/runtime_quality/test_data_state_substrate.py` @ `9e916b3310ee70bd9112d2db1a2b0508c8e7f65d` | `test_l5_proxy_identification_materializes_bounded_state_and_toggle_changes_it` |
| `00d946c2b` (`00d946c2b7d052522be092f9c70eb9902f6521c2`) | same path @ `bae992dfe8986d82559a1898cf4f1076632a977d` | same test |
| `5fd3ebcc1` (`5fd3ebcc15637e98bbd4938de5d62ee5004504a8`) | same path @ `9e916b3310ee70bd9112d2db1a2b0508c8e7f65d` | same test |
| `73c656744` (`73c656744f051d9f40667da7f8bc91c61d8b4ebf`) | same path @ `bae992dfe8986d82559a1898cf4f1076632a977d` | same test |

The test calls `_repo_with_household_identification_mode`; that helper calls
`shutil.copytree(REPO_ROOT / _L5_D2_DIR, d2_dst)`. `_L5_D2_DIR` resolves to
`production_data/canonical/local_data_20260501/ukraine_server_support_20260410/`
`runtime_calibration_internals/calibration/d2`. The copied tree is then made
writable and its `identification_mode_registry.json` is edited. Since the
harness runs the complete file, this test runs on all four present cells. The
fact that the destination is temporary does not make copying the appointed
production-data source safe.

## Other matched operations

No other statically visible operation in the 100-path/four-tree scope has a
source under `production_data` or can write to that tree based on its inspected
callsite:

- The remaining `shutil.copytree` in
  `tests/unit/runtime/quality/test_confidence_ledger.py` copies repository
  `src/` and `architecture/` into temporary test checkouts. The copy in
  `tests/unit/runtime/quality/test_epoch_deployment.py` copies the fixture CAS
  rooted at `tmp_path / "holder"` into a sibling temporary holder directory.
- `shutil.copy2` and tar handling in `tests/unit/remediation/test_cas_02.py`
  operate on temporary CAS export members and generated test archives. That
  path exists only at E02 head (`7ee7ccea67cc1fbcc176a5f6c2eb25b07160dbee`)
  and Phase 0 merge (same blob); it is absent at the execution base and main.
- Every write-mode `duckdb.connect` found in the frozen sources uses a
  `tmp_path`-owned database: the acquisition-planner and production-grounding
  fixtures create `source.duckdb`; acquisition-source-replay creates
  `retained.duckdb`; credal-reference creates
  `tmp_path / DEFAULT_L2_SCHOLAR_KG_PATH`; retrieval-fetch-custody builds
  `catalog.duckdb` through `build_real_fetch_owner(tmp_path)`; and the
  generation-cycle mutation test edits the overlay produced by
  `_real_epoch_scenario(tmp_path / "epoch-a")`. These writes execute only in
  their respective whole-file test modules and remain in scratch.
- Literal subprocess command arguments contain no `cp -R`, `rsync`, `ditto`,
  or APFS clone (`cp -c`) operation in this scope. The tar calls found above
  are the temporary CAS export fixture, not production data.

## Inspection method and limits

The census parsed the frozen harness arrays, read each pinned Git tree with
`git ls-tree -r -z`, and scanned each unique present path/blob pair (142) using
Python AST for `shutil.copytree`, `copy2`, related copy methods, tar operations,
and DuckDB connections without `read_only=True`. For each hit, the enclosing
test/helper and source/destination expressions were inspected. Literal shell
command arguments were searched for the copy/archive commands above. The full
path/blob cell denominator and missing cells were computed from those same
four Git trees.

This establishes the direct, statically visible callsites in these 100 files;
it does not resolve dynamic imports, aliased callables hidden behind wrappers,
commands assembled at runtime, or side effects in arbitrary imported helpers.
Those classes remain unresolved by construction. In particular, the production
D2 copy is directly visible and does not depend on dynamic resolution.

## Closure signal

Rewrite the household toggle fixture to expose only a derived, temporary
`identification_mode_registry.json` (and any required parent directories) while
keeping other owner data read-only via the existing symlink arrangement. Do not
copy the D2 source tree. The whole-file test must still show the proxy-to-point
behavioral change, and a negative guard must fail if any copy operation is
attempted with a source inside the canonical production-data root. Recompute
and record the production source file digest before/after as an unchanged
control. Only then may all four whole-file baseline cells be released from
`UNRUN`.
