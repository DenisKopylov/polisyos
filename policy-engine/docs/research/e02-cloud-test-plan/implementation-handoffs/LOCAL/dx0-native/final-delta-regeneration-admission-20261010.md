# Final delta regeneration admission

Read-only inspection at repository HEAD `00954ff836642ca3c2dca4032fcd1b83019bdfd0`, with two modified test files still in the working tree. No tests, generators, builds, native wave, or governance/config writes were run. The only artifact added for this inspection is this note.

## Delta and canonical companions

Relative to the source-freeze base `13e411da7d9e505856fc336b3d25fd0aabdb1f66`, the product and test delta is:

- `src/polisyos/scientist/methods/backtesting/orchestrator.py`
- `tests/integration/scientist/methods/backtesting/test_backtest_foundry_replicas.py`
- `tests/unit/scientist/orchestration/engine/runner/decimal_worker_transport.py` (new)
- `tests/unit/scientist/orchestration/engine/runner/test_activity_worker.py`
- `tests/unit/scientist/orchestration/engine/runner/test_serialization_e02.py`
- `tests/unit/scientist/orchestration/engine/test_async_executor_hardening.py`
- `tests/unit/scientist/orchestration/engine/test_skg_snapshot_replay.py`
- `tests/integration/core_runtime/test_acquisition_authority_served.py` (working-tree modification)
- `tests/unit/runtime/http/test_nl_pipeline_cost_projection.py` (working-tree modification)

The K3 production addition is the private `_resolve_replica_failure` helper. `BacktestOrchestrator` remains the module's only declared `__all__` export; the helper does not alter the public signature or package facade. The R1/R3 delta is test-only. The helper module is under `tests/unit/...`, not `tests/_helpers`; it does not define a pytest test filename and does not add a dynamic-import call.

No narrow generated companion regeneration is indicated:

| Surface | Current read-only result | Required change |
|---|---|---|
| Public surface inventory and docs | Recomputed from the current public contract/facades; both match byte-for-byte. `inventory.json` SHA-256 `9e4bdbf3772894f335512c2afd7f27cc03e206475790c0338a74feedabc3b924`; `public-surface.md` SHA-256 `c6dd74692dbd798b5bd44d21f81e5af71c81edeb220d03f07430785dad00422f`. The `polisyos.scientist` contract does not list backtesting's private orchestrator helper as an entrypoint. | None. Do not regenerate for private helper or test edits. |
| Generated-artifacts reference | Recomputed from its manifest; matches byte-for-byte, SHA-256 `162017153eca788c1afd12bde252f3b2a6862dbdce435c233ba3099af653292e`. | None. |
| Dynamic-import registry | The delta adds no dynamic import site; `architecture/imports/dynamic.toml` has no source row for `scientist/methods/backtesting/orchestrator.py` or the touched tests. Its existing backtesting rows point at package `__init__.py`/CLI sources, which did not change. | None. |
| W12.A local ladder manifest | In-memory `build_ladder_manifest()` serialization matches the committed artifact byte-for-byte, 14,802 bytes, SHA-256 `8380214707d01c86fd46fc166be1aaecb8103cf55f456a91d9ddf0a396b80e9f`. | None. The generator has no check-only flag; do not call `--write-manifest` for this delta. |
| ADR indices | `uv run --no-sync python tools/quality/validation/generate_adr_index.py --check` exited 0: `ADR indexes are up to date.` No `docs/adr` inputs changed. | None. |
| Native SOTA metadata/expiry rows | This delta touches no gate, exception, sunset, or SLO registry. The previously recomputed 33 current expiry findings remain unchanged. No expiry renewal, waiver, date shift, or acceptance was made. | No registry edit. Keep issuer-owned expiry findings separate from child-gate results. |

At final freeze, the normal generated guardrail check remains `uv run polisyos-tools architecture guardrails check --all-generated-checks`; it is not a narrow regeneration command and also checks the known deep-import baseline drift. The delta adds no imports in the K3 source, but this inspection did not recompute or accept the repository-wide deep-import baseline. The full native runner remains the single top-level command recorded in `sota-native-full-command-plan.md`; it should execute once only after final freeze with complete child receipts. The docs-freshness source baseline still has expected count zero, so the full runner invokes its docs-accuracy child after the 17 listed gates despite the historical expiry date.

## Helper-topology row: complete source inventory and disposition

P40 bucket: `SAME_CLASS_DEEPER`. This is the second look at the already-reported helper-topology red, not a new class. Stop patching individual count examples. Either widen the checker to the declared consumer/ownership property or preserve the bounded red and its falsifier; no baseline or exception edit is authorized here.

The lightweight in-memory recomputation used the current `tools/quality/testing/report_test_ratchets.py::_build_payload` implementation (not pytest and not the native 17-child wave). The read-only CLI reproduction, which prints JSON and writes no report file, is `uv run --no-sync python tools/quality/testing/report_test_ratchets.py --format json --fail-on-regression`; the frozen native child adds `--output _build/.tmp/last-mile/test-ratchets.json`. Its complete relevant denominators are:

- `tests/_helpers/**/*.py`, excluding `__init__.py` and `__pycache__`: 23 helper files.
- `tests/**/conftest.py` admitted by `_iter_layer_local_conftests`: 27 files.
- All Python files under `tests/` admitted by `_iter_python_test_files` for helper-import AST analysis: 2,949 files.
- The reporter also evaluates 13 package mirror/property records; current full summary has zero mirror/property floor regressions. The helper-topology status is nevertheless `regression`, because `shared_helper_files` is 23 against baseline 10. Other helper metrics are 0 unused, 0 forbidden reverse imports, and 1 duplicate fixture group; that one `cas_store` group is explicitly registered for `tests/unit/scientist/governance/conftest.py` and `tests/unit/scientist/nodes/conftest.py`.

The complete 23-file helper denominator is:

```text
tests/_helpers/acquisition_chain.py
tests/_helpers/acquisition_epoch_production.py
tests/_helpers/acquisition_human_decision.py
tests/_helpers/acquisition_movement.py
tests/_helpers/acquisition_production.py
tests/_helpers/acquisition_supplier.py
tests/_helpers/artifacts.py
tests/_helpers/b61_timeout_worker.py
tests/_helpers/c7_synthetic_data.py
tests/_helpers/causal_scm_fixtures.py
tests/_helpers/chronology_qualification.py
tests/_helpers/control_worker.py
tests/_helpers/controlled_candidate_profile.py
tests/_helpers/custody_markdown.py
tests/_helpers/hds_quality.py
tests/_helpers/mirror_contracts.py
tests/_helpers/observability.py
tests/_helpers/policy_design_case_projection.py
tests/_helpers/runtime_api/legal_search_profile_fixture.py
tests/_helpers/runtime_http.py
tests/_helpers/scientist_runtime.py
tests/_helpers/search_strategies.py
tests/_helpers/semantic_epoch_native.py
```

The committed May 7 baseline is owned by `team-quality`, `status = active_baseline`, and records these 10 paths: `artifacts.py`, `c7_synthetic_data.py`, `causal_scm_fixtures.py`, `hds_quality.py`, `mirror_contracts.py`, `observability.py`, `policy_design_case_projection.py`, `runtime_http.py`, `scientist_runtime.py`, and `search_strategies.py` (all under `tests/_helpers/`). Its stated context is Phase 2.4's move of raw fixtures to `tests/_data`, goldens to `tests/_golden`, and Python helpers to `tests/_helpers`; single-slice helpers are intended to stay beside their owning tests. The ratchet contract sets `growth_policy = "ratchet_update_required"` and `mode = "fail_closed_no_regression"`. The 13 paths above that baseline are `acquisition_chain.py`, `acquisition_epoch_production.py`, `acquisition_human_decision.py`, `acquisition_movement.py`, `acquisition_production.py`, `acquisition_supplier.py`, `b61_timeout_worker.py`, `chronology_qualification.py`, `control_worker.py`, `controlled_candidate_profile.py`, `custody_markdown.py`, `runtime_api/legal_search_profile_fixture.py`, and `semantic_epoch_native.py`.

None of those 23 paths is changed by the current delta (`git diff --name-only 13e411da..HEAD -- tests/_helpers` is empty). Eight changed/new Python paths are nevertheless inside the reporter's 2,949-file consumer-AST denominator: the seven `tests/...` files listed above plus `decimal_worker_transport.py`. Their static `_helpers` import references match the base for the paths that import shared helpers; no changed import adds or removes a helper edge. The full native gate's red is therefore not explained by a new helper file in this slice, but the changed test paths intersect the complete AST input denominator, so gate-wide P41 provenance is `not_established` without the exact slice-base replay.

The source implementation is a file-count proxy: `_iter_shared_helper_files()` enumerates the 23 paths, `_build_test_helper_topology_report()` sets `shared_helper_files = len(helper_files)`, and `_baseline_count_regressions()` fails any count above 10. It does not measure that each helper is shared across actual test slices. The usage walk reports six clear one-consumer candidates for owner review: `acquisition_human_decision.py` (one integration test), `acquisition_movement.py` (one unit test), `acquisition_supplier.py` (one unit test), `b61_timeout_worker.py` (one unit test), `causal_scm_fixtures.py` (one unit test), and `search_strategies.py` (one unit conftest). Moving these to their owning test slices could satisfy the README's single-slice placement rule where confirmed, but would reduce the count only from 23 to 17, not to 10. The others have multiple test/helper consumers or are imported by the root `tests/conftest.py`; their contents cover distinct acquisition, chronology/epoch, worker, custody, runtime, and shared-quality fixtures. Collapsing unrelated domains into fewer large files just to hit 10 is not an honest repair.

The current gate checks `unused_helpers`, forbidden helper-to-test imports, and duplicate fixture registrations in addition to the raw count. Its stronger intended property is whether helper placement, allowed dependency direction, actual cross-slice reuse, and duplicate fixtures are correct. A decisive P38 falsifier for a widened checker is: one genuinely multi-slice helper added with valid owner/import direction must not fail solely because the module count increments; conversely, a one-slice helper left in `tests/_helpers` must still be rejected even if the count is at or below the historical baseline. The current checker would fail the first and has no explicit multi-slice predicate for the second. The minimum capability to close this is a source-derived helper-to-consumer graph that resolves transitive helper and conftest consumers to test slices, with a behavioral negative control for the one-slice case; no such generic predicate is present in the current reporter.

There is no support for reducing 23 to 10 by this slice without relocating or consolidating live fixtures, and no owner authorization to change the active baseline or its test pin. The honest native SOTA disposition is therefore: run the frozen wave once; expect child 9 (`report_test_ratchets.py --fail-on-regression`) to fail this helper-topology row; keep its owner as `team-quality`; do not waive, shift, or label the failure inherited. A future owner disposition must choose between evidence-backed local placement fixes plus an actual consumer-topology predicate, or an explicit issuer-reviewed baseline decision with a complete path ledger. `tests/repo_quality/tools/test_test_helper_contracts.py` pins the baseline count and status, so any future admitted baseline/predicate repair must change that mandatory test companion and retain the full reporter output.

## Current c4563fd delta supplement (read-only, 2026-10-10)

This supplement supersedes the older cutoff above for the current authorized delta. HEAD was `c4563fd4da93bf9cc06de3dc77554a8a0d117359`; there are nine tracked modified paths and no new product-source paths in this slice. I ran no pytest, build, native SOTA wave, or generator write. The checks below are in-memory renderer/validator calls plus ADR `--check`.

| Current modified path | Bytes | SHA-256 |
|---|---:|---|
| `src/polisyos/runtime/http/services/control/artifacts.py` | 47,129 | `f1b239ab73c05fa8fede8d060dabe636377a0d79d875b3872f7c54085c7a1ffa` |
| `src/polisyos/runtime/http/services/control/generation_cycle.py` | 85,038 | `c4492d44e17df4c18364bf1e23aee3dd9c346d3a12f3b689e341e86c288f35c9` |
| `src/polisyos/runtime/quality/data_forge_binding.py` | 143,100 | `3f4842247f5ff49f64860e06319b5c53f25659ab83429d889f15fa21a54bc592` |
| `tests/_helpers/acquisition_production.py` | 45,290 | `b3d6d8f8aa6a666d33ff56aa284a3499e45cd677f965e7c686bb947d983d1806` |
| `tests/integration/core_runtime/test_acquisition_authority_served.py` | 81,348 | `73991b22a09d76f0135a5b1f87f039430e4af2e13a92cf0364acc807df9927c4` |
| `tests/unit/runtime/http/test_control_service_di.py` | 165,051 | `78606569994f94ebe0fbc32bafa8385e9dc422f14fba5dd0a5d265f6d4ffb310` |
| `tests/unit/runtime/http/test_nl_pipeline_cost_projection.py` | 30,316 | `0f21107ca4ef732a93a9f6c42115279c2bbc10f9352f018b61d09d0605cc187e` |
| `tests/unit/runtime/quality/test_authority_reconciliation.py` | 41,624 | `15adc45402a43b43b634db2b603e6a9f090309f364c24bd0924f5d9871e4c82a` |
| `tests/unit/runtime/quality/test_workspace_loop.py` | 37,776 | `0d0eb8d750b820306e38ce8fa7bc42278a610652ca02950e70adf622d534eb9f` |

### Canonical renderers and snapshot blockers

- **Dynamic-import registry:** the full current selector is 3,201 Python files under `src/`, `tools/`, `apps/`, and `packages/`; sorted path/content-hash manifest SHA-256 is `f0ffd8b584337226a9604d535c180e48c3f720a41e9c74350d02865643ba6ab6`. The collector returns 249 callsites, canonical rendered TOML is byte-identical to `architecture/imports/dynamic.toml` (current SHA-256 `4f45f4d1fe215969b8c266582fe7679831438663e64656a760231597865a74df`), and `validate_dynamic_imports()` returns 0 findings. No registry regeneration is needed; the expired registry review header remains separate issuer-owned debt.
- **Public contract rendering:** 38 declared entrypoints, 253 recorded read/presence operations over 85 unique paths. The current input path-state manifest is SHA-256 `9370fac3dc90931040eac0d880e417b81e03b68363a2d4b1942c20fa16007eab`; all recorded read hashes/byte counts and absent-file observations match current files. In-memory rendering is exact for `architecture/public_surface/inventory.json` (`9e4bdbf3772894f335512c2afd7f27cc03e206475790c0338a74feedabc3b924`), `docs/reference/public-surface.md` (`c6dd74692dbd798b5bd44d21f81e5af71c81edeb220d03f07430785dad00422f`), and `docs/reference/generated-artifacts.md` (`162017153eca788c1afd12bde252f3b2a6862dbdce435c233ba3099af653292e`). These canonical outputs need no regeneration.
- **W12.A:** `build_ladder_manifest()` serialization remains byte-identical to `architecture/policy_design_case/wave6_local_validation_ladder_manifest.json`, 14,802 bytes, SHA-256 `8380214707d01c86fd46fc166be1aaecb8103cf55f456a91d9ddf0a396b80e9f`.
- **ADR:** `./.venv/bin/python tools/quality/validation/generate_adr_index.py --check` exited 0 (`ADR indexes are up to date.`).
- **Separate Phase-3A source snapshot:** direct `decomposition_preflight.validate_public_surface_snapshot()` returned one finding, `snapshot drift detected`, in 5.568 s. Its full denominator is 2,748 Python files under `src/polisyos/`, with sorted path/content-hash manifest SHA-256 `d94f30fab3d954259970bdd25aea25624ea1bec21cc7fa2556b9bf466224afc9`; three paths intersect this delta. Comparing those three files only against HEAD `c4563fd` identifies 22 changed snapshot object records: 3 line-only record changes in `artifacts.py`, one actual signature change to `compile_and_run_recursive_generation_cycle` adding optional `root_n4_generation_client: object | None = None`, and 18 line-only record changes in `data_forge_binding.py`. The check records source line numbers as part of each object, so the 21 location-only deltas fail its snapshot equality even though their signatures are unchanged. This is distinct from the canonical public inventory/docs above. P40 is **NEW** for this separate snapshot consumer; P38 counterexample: inserting an unrelated line above an unchanged function alters the recorded `line` and fails. The new optional argument is a real interface delta and must remain explicit in review. The exact collector can refresh only `architecture/baselines/structure_remediation/public_surface_pre_decomp.json`, but that is a baseline decision, not a renderer drift fix; no baseline was written. P41 is `not_established`: 3/2,748 input paths intersect, and no exact slice-base replay was done.
- **Separate schema-diff check:** direct `validate_schema_diff()` returned one aggregate finding (`unexpected schema definition diff`) in 0.019 s: the checked schema currently has 583 definition keys versus 318 in its baseline (266 added, one removed). Its input files are `schemas/runtime_api_v1.openapi.json` (SHA-256 `5eb0e88bfdfb832332313eeb5c25d99f7a18a010c6f572d60eda5d6c7a587241`), `architecture/baselines/structure_remediation/schema_diff_pre_decomp.json` (`fbd3081dcc0bc2df8bcd97987d8bb9e57ff133be0f94e08207b34dd377c26988`), and the two current move-map sources `src/polisyos/foundry/_quickstart.py` and `src/polisyos/foundry/_registry.py` (2-file path/content manifest SHA `529a58f5a586e94fb3f6acc611846c4c6f220325ca00bec17bfe0d662af40537`). None of the nine current delta paths intersects those inputs. This finding is not resolved here and is not called inherited: no exact slice-base replay was done, so P41 remains `not_established` despite the measured zero path intersection.

### Helper-topology update for this cutoff

The previous statement that no shared helper changed is stale for this cutoff. There are still 23 current `tests/_helpers/**/*.py` files (manifest SHA-256 `a52a9ab8385cc93caaacd02e19ac4754f8502e0846fc33e78cedfff3e8fa6f99`) versus the unchanged baseline of 10; the changed shared helper is `tests/_helpers/acquisition_production.py`. The helper-import AST selector still covers 2,949 Python test files (manifest SHA-256 `8995d0a212c6724a0d501446d7e963d31917db9ac327f98d33df0833dda0f5d0`), and the conftest selector covers 27 files (`c5bd1d133db985b700901e3374150a3d6607e3aafe3e3ac6a733e33cac2b5047`). Five modified test modules also intersect that AST denominator. I did not pre-run child 9. The unchanged reporter defines the count from helper-file cardinality, so the 23-vs-10 helper metric remains a known failure condition; other current report fields are unmeasured here. P41 for the complete helper-topology gate is `not_established`, not inherited, because one helper and five test inputs changed.

### Frozen execution commands and output roots (not run)

The current source-freeze identifier is still unset. Do not use the older candidate/base P41 statements in the existing wave plan for this cutoff. Once root declares the frozen source ID, use fresh unique roots `LOCAL/raw/native-sota-frozen-<source-id>/` and `LOCAL/raw/native-repo-gates-<source-id>/`; retain complete stdout, stderr, status, command/argv, and hashes there. Do not create these roots before freeze.

The one-shot aggregate command remains the existing recipe; its full 17 sequential child commands and expected `_build/.tmp/last-mile/` artifacts are enumerated in `sota-native-full-command-plan.md`:

```bash
uv run polisyos-tools workspace repository-sota-closeout \
  --output-json docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-sota-frozen-<source-id>/report.json \
  --subprocess-receipt-dir docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-sota-frozen-<source-id>/children
```

Capture the top-level streams/status under that same root. The conditional independent docs-accuracy command is `uv run polisyos-tools validation check-docs-accuracy --repo-root .`; the current expired/zero-count metadata causes the aggregate docs child to short-circuit before this command, so any separate docs run must be reported separately and must not alter expiry metadata.

The four repository-wide commands documented in `AGENTS.md` are separate from the 17-child aggregate and are also reserved until source freeze:

1. `uv run polisyos-tools workspace verify --backend-only`
2. `uv run polisyos-tools workspace ci-parity --skip-browser`
3. `uv run polisyos-tools architecture guardrails check`
4. `uv run --extra runtime --extra ml polisyos-tools runtime check-runtime-api-contract`

None was run here. The issuer-owned expiry rows are untouched by this nine-path delta; do not infer renewal or closure from the SOTA contract report or generated-surface checks.

## Full snapshot and schema-denominator recheck (append-only, same cutoff)

This appendix supersedes only the earlier snapshot input-manifest hash and expands the snapshot/schema denominators. It remains read-only. The snapshot base is HEAD `c4563fd4da93bf9cc06de3dc77554a8a0d117359`; the latest source delta touches four files in the collector's tree.

`tools/quality/validation/decomposition_preflight.py::collect_public_surface_snapshot()` walks every `.py` under `src/polisyos`, then records modules with a literal `__all__` or non-private top-level function, async function, or class. Object rows include `signature` or class `bases`/`pydantic`, and source `line`. The checker normalizes the entire structure and ignores only `generated_at`. Current input is 2,748 `.py` files; sorted path/content-hash manifest SHA-256 is `5d847a9ac0ae3d4898c5287d0753058202a59c1add174b8f933f48d91c31e4c3`. Against the June 14 baseline (2,387 module rows), current collection has 2,615 module rows: +265/−37 modules and 638 changed common-module rows. Full object drift is 699 added, 125 removed, and 3,676 changed common-object rows; there are 175 `__all__` changes, 3,546 line-only object changes, 120 signature changes, 10 base changes, and one `pydantic` change. Among changed objects, `line` differs in 3,665 and signatures in 120; fields can co-occur. No `source_file` field changed. These are baseline-to-current totals, not changes attributable to the latest slice.

For an exact read-only replay of slice base `c4563fd`, I reconstructed the collector output in memory with the four current source files replaced by `git show HEAD:` contents. The snapshot gate was already red at that base. Current work changes 22 snapshot records against base: 21 line-only records and one signature. The red therefore predates this slice, but four changed paths intersect its 2,748-file input set. Under P41's required zero-intersection rule this is **not inherited**. The replay does not authorize a baseline refresh.

The gate contract is `public_surface_snapshot_gate`: owner `team-architecture`, mode `fail_closed`, target phase `3A`, evidence `architecture/baselines/structure_remediation/public_surface_pre_decomp.json`, command `uv run pytest tests/repo_quality/architecture/test_public_surface_snapshot.py -q`. Accepted ADR-0143, `docs/plans/active/DECOMPOSITION_BLUEPRINT.md`, is owned by `team-scientist/team-foundry`, has `stability = phase-3a-baseline`, freezes scientist/foundry decomposition contracts, authorizes no physical moves in those packages, and requires all Phase 3A gates green before Phase 5/6. It does not authorize a full snapshot reset or acceptance of a runtime HTTP signature change. Baseline SHA-256 is `4d8b67ee939c769b8cd52b9cdae49597d040b9680304e63356b1c449b0eef589`; recorded generation time is 2026-06-14.

There is no isolated baseline writer. The only CLI is `uv run python tools/quality/validation/decomposition_preflight.py generate [--skip-import-time]`. `write_phase3a_artifacts()` also updates dynamic and lazy registries, import graph, pickle inventory, schema baseline, and blueprint, and creates checkpoint fixtures; no `--only public-surface` option exists. `--skip-import-time` avoids measuring import time but does not narrow the other writes. The checking recipe is the pytest command above; the aggregate `decomposition_preflight.py gate` runs the other preflight checks too. A 22-row patch would neither be a complete baseline reconciliation nor make this gate pass. A full refresh would admit the complete drift counts above, so it requires an explicit decision from the named gate owner.

P40 is **SAME_CLASS_DEEPER**: this full census deepens the already identified Phase-3A snapshot finding. P38 counterexample: inserting a comment above an unchanged public function leaves its signature and behavior identical, but changes AST `line` and fails the current equality check. The slice's 21 line-only record changes demonstrate the divergence. The 120 full-baseline signature changes and 175 export-set changes remain separate API decisions, not location noise.

### Narrow G packet: `root_n4_generation_client`

The current API delta is the optional parameter `root_n4_generation_client: object | None = None` on `polisyos.runtime.http.services.control.generation_cycle.compile_and_run_recursive_generation_cycle`. The function is included in that module's `__all__`, but is not declared in `architecture/public_surface/contract.toml` or the package-level public-surface inventory. Its only product use passes the value to `N4GenerationPort(llm_client=...)` in the branch where no N4 source was supplied, `n4_proposal_only` is true, execution is `simulate_only`, and a candidate-simulation handoff exists. The changed `tests/unit/runtime/http/test_control_service_di.py` supplies a recorded client through a monkeypatch wrapper. The container-owned `RunLifecycle.compile_and_run_recursive_generation_cycle()` wrapper does not accept or forward the parameter, so the normal service route does not currently provide it. This is a candidate-producer seam, not authority promotion.

The narrow owner decision is whether this module-exported callable is an intentional supported contract, or an internal composition/test seam not yet bridged through the service owner. `team-architecture` owns the snapshot gate; the current public-surface contract does not establish this function as a published package entrypoint. A baseline-only update would not prove the seam is wired. If this is supported product behavior, the bridge and a typed client contract need their own owner and consumer proof. If it is internal, the API owner should state that before any baseline admission. No such decision was inferred here.

### Schema-diff finding: output and complete input denominator

`validate_schema_diff()` returns one finding; its formatter emits at most the first 20 unexpected definition names. The complete observed finding text is:

```text
[schema_diff_gate] unexpected schema definition diff :: AbsentFact, AcquisitionBacklogProjection, AcquisitionDecisionRequestResponse, AcquisitionExecutionResponse, AcquisitionGrowthPayload, AcquisitionGrowthSummary, AcquisitionMovementArtifact, AcquisitionRouteListResponse, AcquisitionRouteMutationRequest, AcquisitionRouteProjection, AcquisitionRouteReplayPins, AcquisitionRoutingPayload, AgentPipelineCostEvent, AppointmentPosture, ArtifactID-Input, ArtifactMissingConfidenceLedgerRiskSpendPacket, ArtifactMissingGovernedProjectionPacket, AudienceClass, AuthorityAbstainingRunPaperCase, AuthorityBoundary
```

The full machine-derived delta is 318 baseline schema definition keys versus 583 current keys: 266 added and one removed, all 267 unexpected against the four allowed FQNs from the current two-row move map. Sorted added/removed change-set SHA-256 is `18355ebc03db6d9267edbcbb9f030bffd4cbd09681b0ed0a7e1b6801ccdfa48a`; the complete sorted unexpected-key-set SHA-256 is `9742d7b07eb2a2a81761ac53a114086eafbae9fa931357863e41198cc641b1fd`.

The five-file execution/input denominator and file hashes are:

| Input | SHA-256 |
|---|---|
| `architecture/baselines/structure_remediation/schema_diff_pre_decomp.json` | `fbd3081dcc0bc2df8bcd97987d8bb9e57ff133be0f94e08207b34dd377c26988` |
| `schemas/runtime_api_v1.openapi.json` | `5eb0e88bfdfb832332313eeb5c25d99f7a18a010c6f572d60eda5d6c7a587241` |
| `tools/quality/validation/decomposition_preflight.py` | `fbdc576306832fd849a4aa557fce7d719efad045ca6bc2da6b39d1f3d187de17` |
| `src/polisyos/foundry/_quickstart.py` | `ad2f24273766ea98e80b543002c8b6e729a2803cd3878796c1ba70eeda4db481` |
| `src/polisyos/foundry/_registry.py` | `f9a3b8ef31a5be5a3b0010b2bc25ffb75fb6e2c5c7d567b75f1bac0c021de9a9` |

The sorted two-source path/content manifest SHA-256 is `bc44228767148d611265a17df9b575d6524cfe2e451008e292b325cb8cfdbba4`; the five-file input manifest SHA-256 is `79324b6ae4d36df90985a132f0f2749664336198daee5b821e93ab354b435446`. None of the current ten changed paths intersects those inputs. P41 remains `not_established`: no separate exact slice-base replay of the schema finding was performed. The schema check is called by `run_all_gates()` and the preflight CLI, but it has no standalone `schema_diff_gate` row in `architecture/gates/structure_remediation.toml`; the aggregate command is listed under `dynamic_imports_gate`. The earlier two-source hash `529a58f5...` used a different manifest encoding and is superseded by the hashes above.

#### Latest same-cutoff source-path change

A later status check found one additional tracked source edit, `src/polisyos/runtime/quality/acquisition_world_growth.py` (SHA-256 `90a68276f423f2b3dadcc0ecdf01d7ac0ba42188229ca0fc39517eb0c95213a7`), alongside the prior three. The tracked working-tree footprint is now ten paths: four product sources and six tests. This edit changes an interior string literal, not a top-level export, signature, class base, or line; its collector module record is identical to the exact HEAD version. Reconstructing the snapshot at `c4563fd` with all four current source files replaced in memory by their `git show HEAD:` contents still yields 22 slice-delta records and the same already-red gate result. The full 2,748-file content manifest is now `5d847a9ac0ae3d4898c5287d0753058202a59c1add174b8f933f48d91c31e4c3`, superseding the immediately prior `b0a09f...` hash. This added source edit does not alter the full baseline drift counts above.


## Architecture iteration gate receipt (c4563fd + 10-path WIP; partial coverage)

This is the already-run iteration receipt, not the post-freeze architecture verdict. The full raw output is `LOCAL/raw/r3-architecture-iteration-20261010/stdout.txt` (1,819,178 bytes, SHA-256 `080f52cd1eff7c04f1311b421c53a509090cde2a74732fb325eb609337038fcb`); exact argv, cwd, environment, exit and wall time are in the adjacent `command.json` (SHA-256 `96a3319a04ffb34ea42b43b5e734063b7b3e90c8013107b2726618ea841b45bd`). Command: `uv run polisyos-tools architecture guardrails check`, cwd `policy-engine`, `UV_FROZEN=1`, `UV_NO_SYNC=1`, captured HEAD `c4563fd4da93bf9cc06de3dc77554a8a0d117359`, exit 2, 159.501 seconds; stderr is empty. The stdout is text, not JSON. Its leading verdict explicitly says `UNRUN ... no complete verdict`; the four generated-family attempts are unavailable measurements, not green results or 1,876 distinct product failures.

The complete result classes parsed from all 5,938 output lines are:

| Result class | Count | Meaning |
|---|---:|---|
| Required generated-freshness families `UNRUN` | 4 families | `runtime-openapi-snapshot`, `runtime-api-client`, `runtime-dashboard-api-types`, and `trust-claim-posture-register`; these are all 4 families selected by the current manifest's default-freshness predicate. |
| Copy errors listed per family | 469 each; 469 unique source paths shared by all four lists | Each list has 27 named pipes and 442 `[Errno 28] No space left on device` entries. The checker uses `shutil.copytree(repo_root, ...)` with explicit ignores for caches, `.git`, `node_modules`, `production_data`, etc.; it does not ignore the handoff `LOCAL/raw` tree or named pipes. This prevented the isolated-source checks from reaching a verdict. |
| Deep-import baseline drift | 1 | Completed baseline-vs-current artifact finding; no baseline was updated or accepted. |
| New deep-import creep | 475 edges from 215 distinct source files | Completed source findings, grouped below. |
| Unresolved public export totals | 38 module totals | Completed public-surface findings, grouped below. |

The public-surface contract contains 20 package policies. The 38 unresolved totals occur in these discovered module roots: `common` 2, `core` 5, `ir` 3, `obligation_rules` 1, `obligation_graph` 1, `method_requirement` 1, `participation_requirement` 1, `fabric` 3, `foundry` 6, `scientist` 4, `evidence` 1, `runtime` 2, `lex` 2, `scholar` 1, `data_forge` 2, `berl` 1, `calibration` 1, and `ddm` 1 (sum 38). The exact module identities are preserved in the raw output. No exception-expiry diagnostic appeared in this command's completed findings.

The 475 deep-import findings distribute by source root as follows: `berl` 3, `calibration` 5, `core` 3, `data_forge` 15, `fabric` 13, `foundry` 45, `ir` 3, `lex` 7, `pdc` 1, `runtime` 92, `scholar` 11, and `scientist` 277. `collect_deep_import_edges()` reads every `*.py` under `SRC_ROOT` (except `__pycache__`) and AST-parses cross-package imports; the same-cutoff source denominator is 2,748 Python files as recorded in the full snapshot manifest above, and tests are outside this selector. Four changed product sources intersect that 2,748-file input. Two of them produce four of the 475 findings: `src/polisyos/runtime/http/services/control/generation_cycle.py` contributes 3 edges (`core.artifacts.manifest`, `core.contracts.control`, `scientist.orchestration.engine.budget_middleware`), and `src/polisyos/runtime/quality/data_forge_binding.py` contributes 1 (`data_forge.read_api.catalog`). The changed `artifacts.py` and `acquisition_world_growth.py` contribute no listed deep-import edge. These are still source-input intersections; this is not a zero-intersection P41 replay.

The exact ten modified paths at capture were four product sources—`src/polisyos/runtime/http/services/control/artifacts.py`, `src/polisyos/runtime/http/services/control/generation_cycle.py`, `src/polisyos/runtime/quality/acquisition_world_growth.py`, `src/polisyos/runtime/quality/data_forge_binding.py`—and six tests—`tests/_helpers/acquisition_production.py`, `tests/integration/core_runtime/test_acquisition_authority_served.py`, `tests/unit/runtime/http/test_control_service_di.py`, `tests/unit/runtime/http/test_nl_pipeline_cost_projection.py`, `tests/unit/runtime/quality/test_authority_reconciliation.py`, `tests/unit/runtime/quality/test_workspace_loop.py`. All ten are within the whole-repository copy source used by the generated-family checks; four source paths also lie in the deep-import selector. No exact pre-slice-base replay was performed for this architecture gate. Gate-wide P41 is therefore `not_established`, not inherited, and the completed findings must not be carried as issuer-approved exceptions. The gate's leading informational line also says the standalone Atlas status-retirement inventory checker is not run by this command; that is a separate command, not a fifth `UNRUN` family.

This iteration command is not the final native wave or final four repository gates. Preserve this receipt as a partial measurement with the 4 generated checks unresolved, 514 completed finding records (1 baseline drift + 475 edges + 38 export totals), and no inherited-red or expiry waiver claim. The final frozen wave remains pending.
