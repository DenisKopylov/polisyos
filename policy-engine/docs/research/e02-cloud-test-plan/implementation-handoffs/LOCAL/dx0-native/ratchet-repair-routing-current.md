# DX0 ratchet repair routing — current full census

## Evidence boundary

This is a read-only diagnostic of the current candidate tree at `4699fdf8419dd2c89609f68a3edf5f3bfb7c851a`. It is not an inherited-red claim: the report was replayed on this exact tree, and I did not modify source, tests, ratchets, or generators. The tree had concurrent dirty work from other authors; all complete-input hashes are retained so the snapshot can be distinguished from later waves.

The light command was run from `policy-engine/`:

```text
uv run --no-sync python tools/quality/testing/report_test_ratchets.py --format json --fail-on-regression
exit=1
```

Full stdout is retained at `LOCAL/raw/ratchet-repair-routing-current/ratchets-current.stdout` (113,053 bytes; SHA-256 `c92f56ed365d4928fcad1ec20690783a45f7be7e57dba3768055896fd9144f20`); stderr was empty. `ratchets-current.manifest.json` records argv, cwd, exit, and hashes of `report_test_ratchets.py`, `architecture/tests/ratchets.toml`, and the pinned phase-0–4 verification inventory.

The complete source/module and test/import-route census is `LOCAL/raw/ratchet-repair-routing-current/complete-mirror-and-import-routes.json` (24,029,998 bytes; SHA-256 `e96e2c9af52deda33693debea0e5e7d14dc917056b35d3f6fc0c8355585b22`). It contains every package source module, every strict/loose-missing identity, same-stem matches, direct test import routes, and the complete 2,898-file Python test-tree path/hash manifest (manifest SHA-256 `7b4013bdb1894da2fb0c8357424cf1503957bc09ef4127126c60a4bbdb070f6a`). Use that raw receipt as the complete enumeration; this note does not duplicate hundreds of derived paths.

## Current denominator and arithmetic

The report enumerated 2,400 production `.py` modules in 13 packages and the route census hashed all 2,898 Python test files. Exact package summary:

| Package | Source modules | Loose matched | Loose missing | Missing with a direct FQN test import | Strict missing |
|---|---:|---:|---:|---:|---:|
| berl | 26 | 10 | 16 | 14 | 25 |
| calibration | 8 | 6 | 2 | 1 | 2 |
| common | 13 | 8 | 5 | 3 | 9 |
| core | 180 | 91 | 89 | 57 | 145 |
| data_forge | 252 | 152 | 100 | 48 | 185 |
| ddm | 14 | 9 | 5 | 4 | 14 |
| fabric | 259 | 130 | 129 | 79 | 240 |
| foundry | 535 | 382 | 153 | 95 | 348 |
| ir | 174 | 106 | 68 | 58 | 149 |
| lex | 40 | 22 | 18 | 10 | 29 |
| runtime | 313 | 183 | 130 | 103 | 190 |
| scholar | 24 | 11 | 13 | 9 | 20 |
| scientist | 562 | 403 | 159 | 101 | 314 |

The ratchet summary has 4 non-excepted loose-floor regressions (common, data_forge, ddm, scholar), 2 strict regressions (common, scholar), and floor/strict regression exceptions elsewhere. Scientist is now green after the planned 23 meaningful tests: loose `403/562 = .7171` vs `.7099` floor, strict `248/562 = .4413` vs `.4120` baseline, and 5/5 property files. Do not disturb its threshold or relabel its result.

For the current seven target packages, the minimum additional distinct loose-name matches to reach the existing floors is: common 3 (`11/13`), data_forge 3 (`155/252`), ddm 1 (`10/14`), scholar 1 (`12/24`), fabric 1 (`131/259`), foundry 2 (`384/535`), runtime 41 (`224/313`). The runtime number is 41 for this exact denominator, not 46. These are arithmetic lower bounds only; they do not authorize filler. Each counted test must assert a source-owned behavior or be a meaningful existing test moved under its true owner with all path-based selectors preserved.

**P38:** the checker’s loose/strict match predicates measure filename stems and relative paths; they do not establish execution or behavior. The receipt’s FQN import routes help find the consumers but even an FQN import alone is not proof of a meaningful assertion. Use the following proposals as audit routes and counterexamples, not as a test-count recipe.

## Existing cross-owner routes that must not be mistaken for owner mirrors

- `common/hashing.py` has the same-stem `tests/unit/core/test_hashing.py`, but that tests the Core facade, not the Common module contract. The existing Common callsites include the Core/IR facades; add Common-specific behavior only if it covers a gap.
- `common/migrations/manifest.py` is already imported from `tests/unit/common/test_migrations_purity.py` and `tests/unit/remediation/test_mig_04.py` / `test_mig_05.py`; `common/migrations/_engine.py` is imported by the Common purity test and MIG-05. Existing tests check migration effects, non-mutation/idempotence, and shared facade identity. They do not exercise every generic traversal branch (e.g. missing edge / cycle), so a focused owner test can add that distinction.
- `ddm/integration/incident.py` has same-stem `tests/unit/scientist/governance/continuous/test_incident.py`, but that is Scientist-owned and has no DDM import route.
- `scholar/provenance.py` has same-stem DataForge/Fabric tests. Scholar has `tests/unit/scholar/test_fabric_provenance.py` importing its public package facade and exercising conversion; it is real behavior coverage but not direct module ownership. `scholar/search/scoring.py` has a same-stem Foundry test unrelated to Scholar scoring. Its actual consumers are Scholar fetcher/service and Scientist claim support; the full report found no test FQN import of the scoring module.
- `fabric/connectors/contracts/validation_middleware.py` is directly imported and behavior-tested in `tests/unit/fabric/test_schema_semantic_correctness_phase3.py` (strict rejection of semantic ratio drift). A new mirror should target a different boundary such as registry-revision cache invalidation, not replay that same failure.
- `foundry/feedback/fixed_point.py` and `jacobian.py` are exercised through the public `polisyos.foundry.feedback` import in `tests/unit/foundry/analysis/test_feedback_fixed_point.py`; those tests prove reflection-map convergence, multi-start alternatives, budget stopping, multiplicity, a basin estimate, and a high spectral radius. They do not directly validate finite-difference Jacobian columns, fold/flip classification, or how unresolved/unassigned basin starts affect the share denominator.

## Partitionable owner work (six candidate slices)

Each test target below is a new candidate path in the source owner’s unit-test tree. First inspect the cited existing route and retain or extract its meaningful case only if test selectors remain covered. Otherwise add the stated *distinct* counterexample/property. No test should exist solely to make a stem appear.

### 1. Common — three loose matches; one strict match

| Source module | Target test path | Existing route / distinct behavior to prove |
|---|---|---|
| `src/polisyos/common/canonical.py` | `tests/unit/common/test_canonical.py` | No direct route. Assert key-order invariant bytes and typed value round-trip; reject unknown typed tag and default-forbidden float / over-depth input. |
| `src/polisyos/common/hashing.py` | `tests/unit/common/test_hashing.py` | Only same-stem Core facade test. Import Common directly; prove `streaming_hash(chunks)` equals `content_hash(joined)` across chunk boundaries, and explicit legacy SHA-1 warns while default hashing remains SHA-256. |
| `src/polisyos/common/migrations/_engine.py` | `tests/unit/common/migrations/test__engine.py` | Existing routes: `tests/unit/common/test_migrations_purity.py`, `tests/unit/remediation/test_mig_05.py`. Directly test generic no-op, missing-edge refusal, and cycle refusal; do not duplicate manifest migration happy-path checks. |

### 2. DataForge — three loose matches

| Source module | Target test path | Existing route / distinct behavior to prove |
|---|---|---|
| `src/polisyos/data_forge/domains/academic/batch/table_extractor.py` | `tests/unit/data_forge/domains/academic/batch/test_table_extractor.py` | No direct route; production bridge is `doc_normalize.py`. Exercise the pure numeric/table conversion path without installing Marker/PDF dependencies: preserve estimate, parenthesized SE / CI, and significance interpretation; malformed cells must not fabricate a value. |
| `src/polisyos/data_forge/domains/catalog/batch/material_inputs.py` | `tests/unit/data_forge/domains/catalog/batch/test_material_inputs.py` | No direct route; called by catalog config, harvester, core-source loaders, and proxy penalties. Prove the snapshot distinguishes “not selected” from selected-but-absent, binds exact bytes/presence, and cache changes after content replacement. |
| `src/polisyos/data_forge/domains/catalog/knowledge/country_codes.py` | `tests/unit/data_forge/domains/catalog/knowledge/test_country_codes.py` | No direct route; called by loaders/writers/validators/registry/transformers. Prove ISO2/ISO3/numeric/name-alias normalization, keep leading-zero numeric `051`, return empty for unknown code, and reject an unknown named scope. |

### 3. DDM + Scholar — one loose match in each

| Source module | Target test path | Existing route / distinct behavior to prove |
|---|---|---|
| `src/polisyos/ddm/integration/incident.py` | `tests/unit/ddm/integration/test_incident.py` | No direct DDM route. Exercise the full R4→R0 severity/action lattice; especially R3 must not create a ticket/page and R0 must request rollback, page owner, and attach the root-cause event. |
| `src/polisyos/scholar/search/scoring.py` | `tests/unit/scholar/search/test_scoring.py` | No FQN test route; actual callers are `scholar/search/fetcher.py`, `scholar/search/service.py`, and `scientist/evidence/claim_support.py`. Distinguish mixed-direction evidence from a consistent claim; ensure emitted snippet offsets bind the exact text window and SEO spam cannot outrank a clean equally-ranked source. |

### 4. Fabric + Foundry — one Fabric, two Foundry loose matches

| Source module | Target test path | Existing route / distinct behavior to prove |
|---|---|---|
| `src/polisyos/fabric/connectors/contracts/validation_middleware.py` | `tests/unit/fabric/connectors/contracts/test_validation_middleware.py` | Existing direct route in `tests/unit/fabric/test_schema_semantic_correctness_phase3.py`. Add a different invariant: after a cached contract is replaced and `ContractRegistry.revision` advances, a stale permissive contract cannot continue to admit the fetch. Keep strict/warn/disabled behavior explicit. |
| `src/polisyos/foundry/feedback/jacobian.py` | `tests/unit/foundry/feedback/test_jacobian.py` | Existing indirect route in `tests/unit/foundry/analysis/test_feedback_fixed_point.py`. Directly compare finite differences with a known affine map (including a nonzero baseline), and prove fold/flip diagnostics at their boundary matrices. |
| `src/polisyos/foundry/feedback/basin.py` | `tests/unit/foundry/feedback/test_basin.py` | Existing indirect route in `tests/unit/foundry/analysis/test_feedback_fixed_point.py`. Assert failed and unassigned starts remain in the draw denominator, shares do not renormalize over only successful assignments, and empty-draw Wilson bounds remain `[0,1]`. |

### 5. Runtime HTTP — 20 candidate loose matches

All routes below are present in the complete route census. New target paths follow source ownership; use the existing file only as the route to audit. Each property is a counterexample target, not a claim that current behavior is defective.

| Target test path | Existing route | Candidate property boundary |
|---|---|---|
| `tests/unit/runtime/http/test_authorization.py` | `test_runtime_api_authz.py` | Wrong tenant or audience must deny at the service boundary, with a denial audit event. |
| `tests/unit/runtime/http/test_deployment_security.py` | `test_acquisition_authority_deployment.py` | Missing or stale deployment evidence must fail closed before activation. |
| `tests/unit/runtime/http/test_opa_input.py` | `test_runtime_rego_authorization_parity.py` | Caller-controlled fields cannot forge authority in the OPA request projection. |
| `tests/unit/runtime/http/test_permissions.py` | `test_runtime_permission_vocabulary.py` | Unknown permission and absent permission remain denied; no broad fallback. |
| `tests/unit/runtime/http/test_production_approval_binding.py` | `test_human_decision_service.py` | Approval binds to the exact decision/revision; stale approval cannot authorize changed content. |
| `tests/unit/runtime/http/routes/test_governed_projections.py` | `test_governed_projection_api.py` | Unknown projection/version and cross-tenant request do not return a publishable projection. |
| `tests/unit/runtime/http/routes/test_human_decisions.py` | `test_runtime_authorization_access_audit.py` | Decision route preserves authorization and audit identity through the handler. |
| `tests/unit/runtime/http/services/test_acquisition_action_service.py` | `test_acquisition_control_worker.py` | Replayed action with the same idempotency identity cannot duplicate a persisted effect. |
| `tests/unit/runtime/http/services/test_acquisition_surface_contracts.py` | `test_acquisition_surface_projection.py` | Missing required source stays limited/refused; “partial” does not become complete by projection. |
| `tests/unit/runtime/http/services/test_acquisition_surface_execution.py` | `test_live_acquisition_executor.py` | Quarantine retains zero world growth until the independent admission/appointment path is satisfied. |
| `tests/unit/runtime/http/services/test_case_inspection.py` | `test_case_inspection_api.py` | Tenant and case binding prevents inspection of another case’s artifacts. |
| `tests/unit/runtime/http/services/test_case_inspection_contracts.py` | `test_run_paper_api.py` | Incomplete evidence identity is refused instead of coerced into a public case contract. |
| `tests/unit/runtime/http/services/control/test_admission.py` | `tests/unit/runtime/http/services/test__control_contracts.py` | Invalid intent/scope is rejected before any producer is dispatched. |
| `tests/unit/runtime/http/services/control/test_response_shapes.py` | `test_response_shapes_monetary.py` | Monetary values preserve exact units/precision and cannot be mistaken for an untyped float. |
| `tests/unit/runtime/http/services/control/test_nl_pipeline_testing.py` | `test_nl_pipeline_materialization.py` | Materialization consumes the exact validated span support; malformed or mismatched spans are refused. |
| `tests/unit/runtime/http/services/test_control_worker.py` | `test_control_worker_custody.py` | Restart/retry after a partially persisted failure does not publish success or duplicate the terminal artifact. |
| `tests/unit/runtime/http/services/test_cycle_board_projection.py` | `test_cycle_board_projection_access_replay.py` | Replay binds the requested immutable projection/ref and does not widen visibility. |
| `tests/unit/runtime/http/services/test_cycle_board_sources.py` | `test_cycle_board_historical_availability.py` | Historical availability is not projected as current availability when source epochs differ. |
| `tests/unit/runtime/http/services/test_export_replay.py` | `test_confidence_ledger_risk_spend_contracts.py` | Content/hash mismatch in replayed export fails closed. |
| `tests/unit/runtime/http/services/test_feedback.py` | `test_runs_api.py` | Feedback read/write remains scoped to a run and does not silently mutate a published result. |

### 6. Runtime quality — 21 candidate loose matches

| Target test path | Existing route | Candidate property boundary |
|---|---|---|
| `tests/unit/runtime/quality/test_adapter_contracts.py` | `test_adapter_registry_capability_discovery.py` | Unknown capability is not inferred from a nearby adapter or label. |
| `tests/unit/runtime/quality/test_capability_index.py` | `test_capability_index_compiler.py` | Index entries derive from registered/validated capabilities, not declarations alone. |
| `tests/unit/runtime/quality/test_case_lifecycle.py` | `test_policy_design_case_lifecycle.py` | A stale or missing lifecycle obligation blocks closeout instead of being skipped. |
| `tests/unit/runtime/quality/test_data_state_substrate.py` | `tests/integration/runtime_quality/test_data_state_substrate.py` and `tests/unit/runtime/quality/test_acquisition_planner.py` | Absent, unavailable, and not-requested data states remain distinct after composition. |
| `tests/unit/runtime/quality/test_ddm_monitoring.py` | `test_policy_design_case_lifecycle.py` | Readiness severity/action mapping preserves the adverse state and required response. |
| `tests/unit/runtime/quality/design_axes/test_blind_spot_firewalls.py` | `test_design_axes_blind_spot_firewalls.py` | An unknown/contested premise remains visible and cannot be collapsed into no-risk. |
| `tests/unit/runtime/quality/design_axes/test_epistemic_regime.py` | `test_design_axes_epistemic_regime.py` | Candidate, contested, and grounded regimes compose without authority promotion. |
| `tests/unit/runtime/quality/design_axes/test_outcome_prediction.py` | `test_design_axes_outcome_prediction.py` | Interventional outcome distribution remains bound to the declared `do()` target/effect bundle. |
| `tests/unit/runtime/quality/design_axes/test_post_deploy_accountability.py` | `test_design_axes_post_deploy_accountability.py` | Expired evidence/epoch triggers revalidation rather than retaining a current accountability claim. |
| `tests/unit/runtime/quality/design_axes/test_value_choice_provenance.py` | `test_design_axes_value_choice_provenance.py` | Selected value choice remains traceable to its candidate source and declared audience. |
| `tests/unit/runtime/quality/test_epoch_certificate_issuance.py` | `tests/unit/scientist/validation/test_epoch_certificate_issuance.py` | Issuance refuses a mismatched signed evidence binding or stale epoch basis. This existing route crosses into Scientist; do not relocate it without ownership review. |
| `tests/unit/runtime/quality/test_epoch_evidence_exchange.py` | `test_epoch_deployment.py` | Exchange replays the exact epoch identity and cannot silently substitute a successor. |
| `tests/unit/runtime/quality/test_evaluation_modes.py` | `test_evaluation_safety.py` | Exploratory evidence cannot enter the confirmatory promotion path. |
| `tests/unit/runtime/quality/test_event_log.py` | `test_runtime_event_log.py` | Duplicate/reordered events preserve idempotency and temporal order, including refusal records. |
| `tests/unit/runtime/quality/test_evidence_independence.py` | `test_evidence_independence_map.py` | Shared source lineage is not counted as independent evidence. |
| `tests/unit/runtime/quality/test_evidence_line.py` | `test_evidence_line_model.py` | Evidence line binds claim, source, and provenance identity; a dangling reference is rejected. |
| `tests/unit/runtime/quality/test_evidence_synthesis.py` | `test_evidence_synthesis_report.py` | Mixed directional evidence remains contested rather than averaged into a confident positive. |
| `tests/unit/runtime/quality/test_explanation_reliability.py` | `test_berl_warrant_reliability.py` | Reliability scoring does not upgrade source authority or ground an unsupported claim. |
| `tests/unit/runtime/quality/test_graded_outcomes.py` | `test_design_axes_graded_outcomes.py` | Mixed/partial outcomes compose to the declared lattice state; no coercion to pass. |
| `tests/unit/runtime/quality/test_projection_semantics.py` | `test_policy_design_case_projection_semantics.py` | Projection cannot upgrade `limited`, `contested`, or `review_required` to publishable. |
| `tests/unit/runtime/quality/test_source_truth.py` | `test_source_truth_lattice.py` | Missing source evidence remains unknown, not false or complete. |

The 41 runtime entries are a partitionable starting surface only. Several source modules already have substantial direct FQN coverage through omnibus tests; avoid duplicating those exact cases. First use the complete route manifest to move a meaningful function when the same owner owns the property and the existing test-layer selector continues to include the moved test. Where that is not true, add only a distinct negative or consumer boundary case and retain the existing test.

## Helper topology: complete current result and repair routing

Current exact helper summary is `shared_helper_files=24`, `layer_local_conftest_files=27`, `duplicated_fixture_factories=1`, `unused_helpers=1`, `forbidden_reverse_imports=11`. The pinned baseline is `10 / 27 / 1 / 0 / 0`. Thus the three count regressions are shared helper files `24 vs 10`, forbidden reverse imports `11 vs 0`, and “unused” helper files `1 vs 0`; duplicate fixture count and layer-local conftest count are unchanged. The full helper list, all usages, and all 11 finding lines are in the report output above and the complete census JSON.

The 11 reverse-import edges are concentrated in seven helper files:

| Helper source | Unit-test modules imported by the helper | Smallest correct repair direction |
|---|---|---|
| `tests/_helpers/acquisition_chain.py` lines 30, 35, 157 | `tests.unit.data_forge.domains.catalog.knowledge.test_acquisition_authority`; `tests.unit.runtime.quality.test_live_acquisition_executor`; `tests.unit.runtime.quality.test_generation_cycle` | Move `_entry`, `_resolver`, `_write_family_receipt`, `_ATTEMPT_ID`, `_family_receipt`, and `_CgfGenerationPort` fixture producers to a neutral acquisition fixture owner. The integration helper then imports fixtures, never test modules. |
| `tests/_helpers/acquisition_epoch_production.py` line 18 | `tests.unit.runtime.quality.test_live_acquisition_executor` | Extract the `_run` test scenario builder into a neutral semantic-epoch test support owner and have both tests import that owner. |
| `tests/_helpers/acquisition_production.py` lines 37, 365 | `tests.unit.runtime.quality.test_generation_cycle`; `tests.unit.runtime.quality.test_live_acquisition_executor` | Move only the `_normalized_rows` / `_raw_body` transport fixture and the required generation-cycle fixture producers to neutral helpers; preserve the real HTTP/epoch/source owners in the integration path. |
| `tests/_helpers/acquisition_supplier.py` line 12 | `tests.unit.runtime.http.test_control_service_di` | Move `_build_control_service` fixture construction to the existing runtime HTTP test-support owner and import it from both layers. |
| `tests/_helpers/controlled_candidate_profile.py` line 360 | `tests.unit.runtime.quality.test_generation_cycle` | Extract `_cyc01_owner_bound_n5_case` and `_record_with_selected_ncm_ref` into a neutral candidate-scenario fixture owner. |
| `tests/_helpers/runtime_api/catalog_profile_source_fixture.py` lines 356, 387 | `tests.unit.runtime.http.test_nl_pipeline_materialization`; `tests.unit.runtime.http.test_control_job_execution_intent` | Move `_DeterministicSpanSupportClient` and `_valid_intake_for_mode` to a neutral support owner; keep the materialization and job-intent tests as consumers. |
| `tests/_helpers/semantic_epoch_native.py` line 27 | `tests.unit.runtime.quality.test_acquisition_executor` | Move `_emit_admitted_ref` and `_real_epoch_scenario` into neutral epoch test support; retain the independent test policy signatures and real consumer execution. |

These are same-class, deeper P40 findings for helper topology: the earlier count-only view did not expose the dependency direction or where the fixture behavior belongs. Widen the repair to the whole helper/import graph; do not patch one import line at a time or bless the current count. A complete closure must prove all helper files’ consumers and import directions from the complete test tree after extraction.

One reported “unused” helper is a measurement/ownership split, not safe deletion debt: `tests/_helpers/runtime_api/catalog_profile_source_fixture.py` has no AST import consumer in the test tree, but `apps/runtime-dashboard/scripts/serve_fixture_runtime_api.py` dynamically imports `_helpers.runtime_api.catalog_profile_source_fixture`; `architecture/imports/dynamic.toml` also has the corresponding dynamic entry. `rg` found those exact external references. Do not remove this file. The real ownership issue is that app dev-support imports from `tests/_helpers`; move fixture serving support under an app/dev-support owner and update its dynamic-import contract, or explicitly teach the generic topology consumer about that production/dev tool route. Test the script’s behavior after the move. Merely turning the metric green by marking the helper “used” is a proxy fix.

The 14 added helper paths beyond the pinned ten are `acquisition_chain.py`, `acquisition_epoch_production.py`, `acquisition_human_decision.py`, `acquisition_movement.py`, `acquisition_production.py`, `acquisition_supplier.py`, `b61_timeout_worker.py`, `chronology_qualification.py`, `control_worker.py`, `controlled_candidate_profile.py`, `custody_markdown.py`, `runtime_api/catalog_profile_source_fixture.py`, `runtime_api/legal_search_profile_fixture.py`, and `semantic_epoch_native.py`. Several are genuinely reused and carry test scenario boundaries; do not consolidate them merely to hit a file count. The new helpers with a single test-tree user are acquisition_human_decision, acquisition_movement, acquisition_supplier, and b61_timeout_worker; consider localizing only after verifying no dynamic/script consumer and no cross-layer reuse. The catalog-profile fixture is the separately verified app-script case above. The registered `cas_store` duplicate factory in the two Scientist conftests is unchanged and remains explicitly registered.

## P40 / P41 closeout

- **P40:** same helper-topology class, one level deeper. The full generic source/helper/test import graph is required; the three summary counts are not repair units on their own. Retain the helper ownership and source-import counterexamples above when the root allocates edits.
- **P41:** no inherited-red classification is made. This report was actually replayed at HEAD `4699…`; this packet does not claim the report existed before any other current dirty work or that a nearby base is disjoint. The raw full-denominator input manifest is the evidence needed for a later author’s exact-slice base replay.
- **Repair principle:** only retire the current red by actual behavior tests / correct test ownership / structural fixture direction. Do not alter `ratchets.toml`, floors, baselines, dates, exceptions, or add import-only/re-export tests.
