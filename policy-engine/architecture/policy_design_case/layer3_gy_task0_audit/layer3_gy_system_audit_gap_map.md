# GY System Audit Gap Map

Date: 2026-06-14
Scope: repo-wide understanding before any GY improvement/fix plan.
Status: audit-only map; not a remediation plan.

## Why This Exists

`layer3_gy_engine_census.json` is now mechanically stronger, but it is still a pinned-route engine census. It proves row consistency and several real execution facts; it does not claim full-system coverage across API surfaces, dashboard projections, generated artifact lifecycle, or every runtime-quality/IR/core subsystem.

This map records the weakly investigated areas that should be audited before writing improvement tasks.

## Coverage Heatmap

Approximate Python package footprint under `src/polisyos` versus current GY census rows:

| Package | Python files | Current GY rows | Audit reading |
| --- | ---: | ---: | --- |
| `foundry` | 596 | 3 | Registry + six representative direct method smokes are covered; route DAG consumption remains blocked upstream. |
| `scientist` | 580 | 42 | Strongest coverage, but mostly DAG nodes; agent roles, search frontier semantics, and consumer-side surfaces remain weak. |
| `fabric` | 296 | 15 | Connector existence is covered; real fetch, persistence, source-contract admissibility, and binding-shape truth are weak. |
| `data_forge` | 260 | 4 | Search is covered more than binding-to-fetch; `resolve_metric_bindings` needs route probes. |
| `core` | 198 | 0 | Artifact, audit, security, contracts, observability, and governance foundations not yet mapped into GY. |
| `ir` | 191 | 0 | Analytics/proof/transportability contracts are central but not route-executed or authority-mapped here. |
| `runtime` | 191 | 2 | Production call sites are covered; API, run index, raw artifact, lineage, review, and export surfaces are not. |
| `lex` | 41 | 0 direct rows | Lex is represented through the scientist DAG node only; failure root cause and frontier semantics need a separate probe. |
| `scholar` | 28 | 1 | OpenAlex/SKG substrate and KnowledgeToolkit have now been audited for P2; route authority remains bridge/semantic-test incomplete. |
| `berl`, `ddm`, `calibration`, `evidence`, requirement packages | 83+ | 0 | Broader-system capability surfaces remain mostly invisible to GY-0. |

Frontend/runtime API surface is also mostly outside the census: committed OpenAPI has 89 operations, `apps/runtime-dashboard/src` has roughly 970 files, and the generated API client/dashboard types are their own generated-artifact families.

## Highest-Priority Weak Areas

0. **P0 coverage gaps from review feedback**

Follow-up completed: see `layer3_gy_p0_coverage_audit.json` and `layer3_gy_p0_coverage_findings.md`.

Observed result: the production control path was finally proven through `launch_workflow_run -> _enqueue_job -> ControlWorker.dispatch_once -> _process_control_job -> _execute_workflow -> run_experiment`. It reached the real `scientist_policy_design` DAG and persisted a failed workflow report, but the control job still completed. That makes the GY-2 target mismatch load-bearing: `run_lifecycle.py:1408` discards the returned final state while `nl_pipeline.py:6596` captures it. GY-2 should govern the workflow-report/final-state authority boundary across both paths, not only the discarded production call site.

All `406` excluded candidate-positive statuses are now enumerated. The firewall result remains `candidate_positive_status_count=406`, `positive_status_count=0`, and `excluded_candidate_count=406`: `397` generic diagnostic `pass` fields without producer/reducer provenance, `8` search-health pass fields without producer/reducer provenance, and `1` external input-only demand-pull pass with explicit `may_not_use_for`. No false exclusions were found by the current rule; the residual risk is surface laundering of diagnostic pass fields.

Blocked input DAG nodes now map to concrete reads: `build_literature_prior` needs `params.causal_variables` (`route_omitted`), `reconcile_causal_graph` needs `params.data_causal_graph` and the skipped prior ref (`producer_missing`), and `run_causal_evaluation` needs top-level `observational_data_ref` even though snapshot/input-binding refs exist elsewhere (`available_elsewhere_not_wired`). The remaining 19 skipped nodes are blocked by lex upstream, not independent input gaps.

Depth-2 generalization was attempted on `pl-household-energy-affordability-2024`. Country-filtered catalog probes returned zero despite plausible unfiltered hits, the real DAG reproduced the same lex optional-bounds failure once given a minimal valid non-authority snapshot, and GX reducers are still pinned to the committed `layer3_gx_data_home` request rather than arbitrary case input.

Validator: `tools/quality/validation/check_layer3_gy_p0_coverage_audit.py`.

0.5. **P1 high-risk substrate authority**

Follow-up completed: see `layer3_gy_p1_substrate_authority_audit.json` and `layer3_gy_p1_substrate_authority_findings.md`.

Observed result: core substrate capability is real but not authority-complete for the pinned route. CAS byte integrity/dedup/tamper checks passed a temporary probe, but the P0 DAG CAS scan found `178` manifests and `0` `manifest.authority` records across production-worker and depth-2 DAG runs. Runtime-quality reports have an authority writer and durable diagnostic event reconciliation; Scientist workflow report/final state/run_dag still use ordinary `put_json`. There is also no general `FileSystemCAS` GC/sweep API.

Time semantics are split. Runtime bitemporality supports details/timeline/lineage/quantities/fabric/compare, but explicitly excludes `run_workflow`, `run_nodes`, and `artifact_content`. PDC legal-time fields exist, yet `legal_as_of` has `44` null/empty occurrences out of `87`, and committed PDC JSON artifacts scanned had `0` catalog watermark/source timestamp/source_updated_at/fetched_at occurrences. DAG blobs mostly carry CAS `created_at`, not source freshness or replay time.

Secret/PII protection is preview-bound and opt-in. The selected scan found `5` secret-like match lines and `0` PII regex hits; the load-bearing hit is a P0 DAG workflow-report blob containing `error.details.api_token = "Bearer should-not-leak"`. Preview redaction exists, but raw `/artifacts/{id}/content` and `/download` return raw bytes. PII detection exists and ingestion can apply it when enabled, but it defaults off and `FetchExecutor` does not apply it.

S12 resource economics exists as a real package and manifest, but G5 pinned pass exact refs are not produced S12 objects. `demand-act://ua-msme/principal` and `voi://ua-msme/site-1` appear only in the G5 composed loop/pinned input bundle path and originate from the hardcoded readiness payload; they did not dereference to exact ResourceAllocationPolicy/ValueOfInformationAllocation/EnvelopeGrowthLedger objects.

Validator: `tools/quality/validation/check_layer3_gy_p1_substrate_authority_audit.py`.

Next audit probe: after P1 repairs are planned, prove one end-to-end authority-safe path where DAG CAS output, temporal admission envelope, secret/PII gate, and S12 cost/VOI refs all reach an API/dashboard/public surface with explicit authority boundaries.

1. **Runtime/API/dashboard/public export surfaces**

Current census covers `run_experiment` persistence and NL surfacing, but not the consumers that can turn "report exists" into perceived authority.

Evidence points:

- `src/polisyos/runtime/http/services/adapters/core_run.py:131` extracts `scientist.workflow_report`.
- `src/polisyos/runtime/http/services/run_index.py:339` exposes `has_workflow_report` / `workflow_report_ref`.
- `src/polisyos/runtime/http/routes/runs.py` exposes `/runs/{run_id}` and `/runs/{run_id}/workflow`.
- `src/polisyos/runtime/http/routes/artifacts.py` exposes manifest/content/schema/download/export routes.
- `src/polisyos/runtime/http/routes/lineage.py` exposes OpenLineage/PROV exports.
- `apps/runtime-dashboard/src` consumes workflow, lineage, run detail, and public decision packet surfaces.

Follow-up completed: see `layer3_gy_runtime_surface_audit.json` and `layer3_gy_runtime_surface_audit_findings.md`.

Observed result: the failed workflow is visible on `/runs/{id}/workflow`, but cross-surface consumers do not carry an explicit authority ceiling. Raw artifact content, runtime lineage, OpenLineage/PROV export, bureaucratic render/export, dashboard score/explainability, and public packet construction remain laundering-risk surfaces unless they consume workflow failure as a load-bearing gate.

Validator: `tools/quality/validation/check_layer3_gy_runtime_surface_audit.py`.

Next audit probe: add no-fix characterization tests for dashboard/public packet behavior with `run.status = failed`, `has_workflow_report = true`, `decision_review_required = true`, and an otherwise present decision/evaluator payload; then decide whether public viewer must be static-with-embedded-authority or live-rechecking.

2. **Catalog binding to fetch to measurement-root chain**

The current census proves catalog search and RetrievalService fastlane, but the real route is `resolve_metric_bindings -> FetchPlan -> preview/execute -> persisted measurement root`. That chain is not proven.

Evidence points:

- `src/polisyos/fabric/retrieval/service.py:726` calls `resolve_metric_bindings`.
- `src/polisyos/fabric/retrieval/service.py:869` builds `FetchPlan`.
- `src/polisyos/fabric/retrieval/executor.py:140` receives `persist_payload=True`, but persistence is intentionally deferred; no CAS digest is emitted there.

Follow-up completed: see `layer3_gy_catalog_fetch_audit.json` and `layer3_gy_catalog_fetch_audit_findings.md`.

Observed result: the production catalog is real (`137,176` datasets / `605,408` distributions / `56,846` metric bindings / `176,249` schema profiles), and an injected `DatasetCatalogGraph` produced a catalog `FetchPlan` that a real WorldBank connector executed. The retrieval route still stops before a measurement root: both deterministic fake connector and real connector probes returned rows with `persist_payload=True` and CAS file delta `0`; `DataContextMetric` exposes no payload/root/request/content-hash fields. `/data/ingest` can accept `fetch_plans` and produce `evidence_bundle_ref` / `data_snapshot_ref`, but that is a separate root producer, not the normal `/data/resolve -> execute_fetch_plans` bridge.

Validator: `tools/quality/validation/check_layer3_gy_catalog_fetch_audit.py`.

Next audit probe: run `/data/ingest` with the exact catalog-derived `FetchPlan` and inspect artifact lineage/root-chain joins back to the resolve plan. This should remain a separate bridge audit unless retrieval execution is changed to call ingestion or emit its own canonical fetch envelope.

3. **Connector family truth**

The 12 connector rows are too uniform. Connector implementations have different request id/profile/filter semantics, and replay fixtures are scaffolds.

Evidence points:

- `src/polisyos/fabric/connectors/sources/world_bank.py:147`
- `src/polisyos/fabric/connectors/sources/ckan_resource.py:211`
- `src/polisyos/fabric/connectors/sources/sdmx_source.py:183`

Follow-up completed: see `layer3_gy_connector_family_truth_audit.json` and `layer3_gy_connector_family_truth_findings.md`.

Observed result: the connector rows are not uniform. Across `56,846` production bindings for the 12 families, the family-shape probe found `8` structural passes, `1` warning, `2` contract mismatches, and `1` catalog-tier-only row. `rest.json` is a contract mismatch because Generic REST fetch uses the profile `base_url`, not the full `request_dataset_id` URL carried by `data_gov_pl` bindings. `unpd.data` is a contract mismatch because `transport_ready` bindings lack the location and time filters that the connector requires. `ukons.datasets` is not execution-ready because all production bindings are still `catalog` tier. `sdmx.source` is structurally valid but warning-level because empty filters produce an unbounded dimension key path.

Validator: `tools/quality/validation/check_layer3_gy_connector_family_truth_audit.py`.

Next audit probe: run the bounded network/replay suite only after this shape gate. For pass rows, prove payload fields, source-contract admissibility, and measurement-root persistence. For `rest.json`, `unpd.data`, and `ukons.datasets`, repair or downgrade before counting them as execution-ready.

4. **Source-contract rights, freshness, and admissibility**

GY-1 asks for rights/freshness, but the route census does not prove that catalog bindings carry source-contract facets into fetch admission.

Evidence points:

- `src/polisyos/fabric/retrieval/service.py:198` source-policy lookup.
- `src/polisyos/fabric/retrieval/service.py:888` history policy metadata.
- `src/polisyos/fabric/catalog/data_requirement_adapter.py:120` can reject missing requirement facets.

Follow-up completed: see `layer3_gy_source_contract_admissibility_audit.json` and `layer3_gy_source_contract_admissibility_findings.md`.

Observed result: strict SourceContract/DataRequirement gates exist, but the normal catalog-derived fetch path does not consume them before connector execution. `DataRequirementSpec` requires `16` mandatory facets including `source_rights`, `field_refs`, `time_coverage_refs`, `freshness_ref`, and `claim_bindability_refs`; a no-write probe using a production WorldBank binding with `CC-BY-4.0` license and inferred value/geography columns produced a `FetchPlan` containing `0/16` of those facets. `FetchExecutor._fetch` builds a connector `FetchRequest` from dataset id, filters, date bounds, schema flags, and page size; it does not inspect source-contract binding status. Separately, `build_source_contract_requirement_bindings` rejects the same missing-facet shape with `source_contract_facets_missing`, and `build_fabric_source_selection_trace` fails it with `18` blocking issues. This is therefore `implemented_but_not_orchestrated` + `bridge_missing`, not a missing-validator problem.

Validator: `tools/quality/validation/check_layer3_gy_source_contract_admissibility_audit.py`.

Next audit probe: define the exact admission envelope that joins catalog metric bindings to selected SourceContract/DataRequirement rows, then prove `/data/resolve -> execute_fetch_plans` blocks or downgrades plans with missing rights, freshness/watermark, field refs, time coverage, or claim bindability.

5. **`data_requirement` compiler invisibility**

The census covers `DataNeedSpec` and `RequiredDataSpec`, but not `src/polisyos/data_requirement`, which is a real compiler/audit surface.

Evidence points:

- `src/polisyos/data_requirement/compiler.py:177` emits `DataRequirementCompilationReport`.
- `src/polisyos/data_requirement/compiler.py:447` exposes `data_requirement_compilation_audit_surface`.
- `src/polisyos/data_requirement/compiler.py:476` persists deterministic reports.
- `src/polisyos/fabric/catalog/data_requirement_adapter.py:15` binds requirements to Fabric source contracts.

Follow-up completed: see `layer3_gy_data_requirement_compiler_audit.json` and `layer3_gy_data_requirement_compiler_findings.md`.

Observed result: `polisyos.data_requirement` is **near_route**, not route-pinned, not out_of_route, and not pure built_not_wired. The compiler has typed contracts, a deterministic producer, an audit surface, a replayable writer, Fabric/source-contract consumers, runtime-quality consumers, and targeted tests. With a G1 release-backed resolver and mapped constructs (`firm_survival`, `regional_displacement_pressure`, `credit_program_enrollment`), it emitted 9 `DataRequirementSpec` rows carrying 16 mandatory facets and 7 admissibility predicates; the embedded capability binding status was `blocked_construct_not_observed`. However, the public scenario wrapper emitted 0 specs for the UA MSME scenario without an injected resolver, and the public golden scenario contract still serializes `data_requirement_specs=[]` while exposing only the legacy family projection. The normal catalog `resolve_metric_bindings -> FetchPlan -> FetchExecutor._fetch` route has no typed `DataRequirementSpec`, source-contract binding status, or mandatory-facet gate before connector fetch. This is therefore `bridge_missing` + `implemented_but_not_orchestrated` at pinned fetch admission, and a census coverage gap.

Validator: `tools/quality/validation/check_layer3_gy_data_requirement_compiler_audit.py`.

Next audit probe: define the exact GY-1 admission envelope that joins compiled `DataRequirementSpec`, SourceContract binding report, `MetricBindingMatch`, and `FetchPlan`, then prove missing specs or rejected source-contract bindings fail closed or downgrade the run before `connector.fetch`.

6. **Lex failure root cause and search frontier semantics**

The census identified lex as `wired_but_rotten`, but not whether the failure was a true lex bug, thin verified-option input, synthetic scaffold, bad bounds, or search-frontier laundering.

Evidence points:

- `src/polisyos/scientist/orchestration/workflows/policy_design.py:110`
- `src/polisyos/scientist/nodes/builtins/planning/run_hierarchical_policy_search.py:201`
- `src/polisyos/lex/interventions.py` includes temporal/scaffold paths.
- `src/polisyos/scientist/policy_design/search.py` and `objectives.py` govern frontier and diagnostic scalar ranking.

Follow-up completed: see `layer3_gy_lex_frontier_root_cause_audit.json` and `layer3_gy_lex_frontier_root_cause_findings.md`.

Observed result: primary root cause is **`implementation_bug_optional_bounds_none_normalized_to_zero`**. The persisted Trinity bundle produced by `formalize_verified_policy` has `verified_policy_option_rate` with `default_value="0.1"`, `min_value=null`, `max_value=null`, and `tunable=true`. The Lex adapter is wired and invoked; it calls `HierarchicalSearchCoordinator.build_parameter_search_spec`, which normalizes optional `None` bounds into `0.0` before `_derive_bounds`. That synthesizes an explicit `0.0..0.0` range, and `ParameterBounds` correctly rejects it with `lower >= upper`. The same value derives `0.08..0.12000000000000001` when `None` is preserved through the schedule branch.

This is **not** upstream bad bounds: no equal min/max exists in the real CAS bundle. It is **not** thin input as the primary cause: the bundle has a numeric tunable default sufficient for range derivation. The verified-policy formalization is still scaffolded (`tax_subsidy`, `rate`, `avg_income`), so it remains a frontier-quality concern, but it did not cause the crash. Search-frontier laundering is **not observed** in the current run because no `policy_frontier_report_ref` is persisted; the node fails first and downstream nodes are `blocked_upstream`.

Post-repair P25 risk remains load-bearing: existing `PolicyFrontierReport` persistence has thin metadata (`source=c6c_hierarchical_policy_search`), lacks typed search-space/objective/bound provenance, and `_iter_candidate_records` can mark unevaluated structure fallback records as `feasible=True`. GY-2 should not govern downstream on a mere bounds fix. Acceptance must include optional-bound preservation, fail-closed explicit bad bounds, a typed search/frontier ledger with budget/stop/objective/source provenance, and a negative proving unevaluated candidates cannot become feasible frontier members.

Validator: `tools/quality/validation/check_layer3_gy_lex_frontier_root_cause_audit.py`.

Follow-up completed in the P0 coverage pass: blocked/skipped DAG state reads are mapped in `layer3_gy_p0_coverage_audit.json`.

7. **Blocked-input DAG nodes**

Follow-up completed in the P0 coverage pass.

Observed result: `build_literature_prior` is blocked on `params.causal_variables` (`route_omitted`), `reconcile_causal_graph` is blocked on `params.data_causal_graph` and the skipped literature prior ref (`producer_missing`), and `run_causal_evaluation` is blocked on top-level `observational_data_ref` even though snapshot/input-binding refs exist elsewhere (`available_elsewhere_not_wired`). The other skipped downstream nodes are `blocked_upstream` by lex.

Validator: `tools/quality/validation/check_layer3_gy_p0_coverage_audit.py`.

8. **Foundry method breadth and route consumption**

Registry coverage is not method execution. The follow-up audit proves one representative direct `pure_step` smoke per top family in the pinned 172-method envelope, but still no DAG-consumed Foundry method output.

Follow-up completed: see `layer3_gy_foundry_breadth_audit.json` and `layer3_gy_foundry_breadth_findings.md`.

Observed result: the builtin registry count remains `389`; live registry is `390` because dev-scan adds one `example` family. The pinned route-relevant `172` is a curated filter: `causal=151`, `forecasting=10`, `validation=4`, `ml.uncertainty=5`, plus cross-family causal rows in `econometrics=1` and `survey=1`. A broad metadata/tag envelope is `232`, so future plans must name which filter they use. Six representative direct smokes passed: Manski bounds, Theta forecasting, conformal prediction, probabilistic validation scoring, post-double-selection, and causal-frontier Fay-Herriot. All are tagged `direct_smoke_only`; `dag_consumed_method_outputs_count=0` because the pinned DAG still skips `compile_foundry` and `run_simulation` after the Lex failure.

Validator: `tools/quality/validation/check_layer3_gy_foundry_breadth_audit.py`.

Next audit probe: after Lex repair, rerun the pinned DAG through `compile_foundry` and `run_simulation`, then audit method refs, input bindings, output artifacts, and API/dashboard/public consumers as route-consumed Foundry truth rather than direct producer smokes.

9. **Scientist agent event backing**

`DataNeedSpec` is now credited, but the NL circuit also instantiates PI, drafter, formalizer, critic, and tool-loop components. Those are G6-relevant and not event-backed in the census.

Follow-up completed: see `layer3_gy_agent_workflow_event_backing_audit.json` and `layer3_gy_agent_workflow_event_backing_findings.md`.

Observed result: the NL runtime path really invokes PI, DataNeedExtractor, Drafter, Formalizer, and Critic, and a simulated no-network NL probe produced `13` model-variant steps including those roles. `/runs/{run_id}/agents` projects those steps through `experiment_state.params.llm_model_variants`, so they are runtime-visible. However, they are not yet G6 event-backed assets: PI/drafter/formalizer/critic have no dedicated persisted role-event artifacts, and committed G6 `AgentRunRecord` artifacts are readiness projections for `req-layer3-g6-readiness`, not live NL run records.

The serious-profile probe also proved `prompt_tool_ledger_ref` persistence to CAS and report index, but that ledger is built from model-variant steps and had `tool_names=[]`; it is parser/status lineage, not `ToolLoopResult` backing. `nl_pipeline.py` has no `run_tool_loop` invocation; the real tool loop exists in `runtime/quality/layer3_bounded_agent.py` for G6 quality projection only.

Validator: `tools/quality/validation/check_layer3_gy_agent_workflow_event_backing_audit.py`.

Next audit probe: run one persisted NL control job through the worker-backed API and fetch `/runs/{run_id}`, `/runs/{run_id}/agents`, the raw `prompt_tool_ledger_ref` artifact, and control outbox/diagnostic events. Decide whether generic control events can become the role-event producer-root chain or whether G6 needs dedicated role-event artifacts.

10. **Governance/status reducers/generated artifacts/public surface lifecycle**

GX validates reducer provenance, but a full-system audit also needs to know whether generated artifact families, public-surface inventory, and API/dashboard generated types are current consumers of those semantics.

Evidence points:

- `src/polisyos/runtime/quality/layer3_status_reducers.py`
- `src/polisyos/runtime/quality/public_export.py`
- `src/polisyos/runtime/quality/authority.py`
- `architecture/generated_artifacts.toml`
- `docs/reference/generated-artifacts.md`
- `docs/reference/public-surface.md`

Follow-up completed: see `layer3_gy_generated_public_lifecycle_audit.json` and `layer3_gy_generated_public_lifecycle_findings.md`.

Observed result: generated-artifact lifecycle is strong for core Layer 3 and runtime surfaces but not for GY Task 0. `architecture/generated_artifacts.toml` has 45 generated families; 10 Layer 3 families are registered (G1, G2, G3, GL, G4, G5, G6, G7, G8, GX) with 243 registered outputs, and runtime OpenAPI/client/dashboard generated types are also registered. But after this audit, 31 `layer3_gy*` files now live under `architecture/policy_design_case/layer3_gy_task0_audit/`, 15 GY validators, and 14 GY repo-quality tests exist with **0** registered generated outputs. `architecture/policy_design_case/inventory.json` contains 42 PDC artifacts and 0 GY entries, and it is not itself registered as a generated-artifact output. `docs/reference/public-surface.md` mentions PDC generated audit surfaces for G4-G8 and GX through hardcoded renderer prose, not a registry-derived GY surface.

Authority boundary implication: projection refs are useful but not enough. Seven Layer 3 public-export projection refs are generated outputs and many carry projection-only / out-of-scope / `may_not_use_for` semantics, while OpenAPI/dashboard generated families can carry `PolicyDesignCaseProjection` authority fields. None of that registers the GY audit family or proves API/dashboard/public-export enforcement for failed workflow authority.

Validator: `tools/quality/validation/check_layer3_gy_generated_public_lifecycle_audit.py`.

Next audit probe: package-level capability inventory, not fixes: for each package, list public contracts, producer functions, persisted artifacts/events, consumers, tests, and whether it participates in the pinned route or only broader-system capability. Before repair planning, decide whether GY Task 0 outputs become one `generated_committed` family or are explicitly classified as `source_committed` / `surface_out_of_scope`.

11. **Core, IR, evidence, BERL/DDM/calibration, and requirement packages**

These are mostly absent from GY-0 despite being substrate for artifacts, proof, transportability, authority envelopes, outcome learning, benchmarks, and diagnostics.

Follow-up completed: see `layer3_gy_substrate_package_capability_inventory.json` and `layer3_gy_substrate_package_capability_findings.md`.

Observed result: the substrate is large and real, but not GY-censused route authority. The 11 audited packages (`core`, `ir`, `evidence`, `berl`, `calibration`, `ddm`, `data_requirement`, `method_requirement`, `participation_requirement`, `obligation_rules`, `obligation_graph`) contain `466` Python files, `435` root-facade exports, `2,639` classes, and `2,114` top-level functions, while the current GY engine census has `0` rows referencing those package modules.

`core` and `ir` are route-pinned substrate, not domain authority. `data_requirement`, `method_requirement`, `evidence`, `calibration`, `obligation_rules`, and `obligation_graph` are near-route bridges/substrates whose GY risk is orchestration and authority consumption rather than missing contracts. `BERL` and `participation_requirement` are broader support/legitimacy gates with real consumers but no pinned-route proof. `DDM` is implemented production monitoring/readiness and remains out-of-route unless GY adds an explicit invalidation/reissue bridge.

Key risk: do not convert package maturity into PDC authority. `data_requirement` remains `bridge_missing` + `surface_missing` at pinned FetchPlan admission; evidence conflict/effective-independence records protect against support-count inflation but are not support strength; BERL/calibration diagnostics require route-bound measurement or method-output roots; obligation and participation packages carry strong anti-LLM/candidate authority ceilings that GY must consume rather than infer.

Validator: `tools/quality/validation/check_layer3_gy_substrate_package_capability_inventory.py`.

Next audit probe: Scholar/OpenAlex/KnowledgeToolkit provider/tool registration. Keep this substrate inventory as a package map, not a repair plan.

12. **P2 semantic adequacy: catalog search, Scholar/OpenAlex, and KnowledgeToolkit**

Follow-up completed: see `layer3_gy_p2_semantic_evidence_quality_audit.json` and `layer3_gy_p2_semantic_evidence_quality_findings.md`.

Observed result: the catalog and Scholar substrates are real, but P2 route authority is not proven. The production catalog has `137,176` datasets, `605,408` distributions, and `56,846` metric bindings. HNSW index files exist, but `sentence_transformers` is unavailable, so catalog search falls back to text-only. On a five-case GY-like silver benchmark, construct-only precision@5 was `0.56`, while route-admissible construct+scope precision@5 was `0.0`. All four country-filtered scoped cases returned zero.

Metric binding search is stronger but incomplete: `credit_access`, `poverty_rate`, `displacement`, and `social_protection_coverage` resolve, but `firm survival` and `cash transfer` return zero; `energy poverty` and `electricity price` split into adjacent or weak metric ids.

The production Scholar SKG is large (`310,829` articles, `7,607` edges, `62,248` parameter estimates), but natural-language route-like work queries returned zero. Canonical SKG queries work for known pairs such as `fiscal.cash_transfer -> economic.consumption`, while the small-business lending route pairs returned zero. Web evidence bundles are real and can persist/project into a research DAG, but G2 correctly guards against laundering `web_evidence_bundle_ref` as canonical L2 SKG search.

`KnowledgeToolkit` is built but not route-tool complete. A runtime registry probe registered only `3` of `20` expected tools because most typed methods use annotations imported only under `TYPE_CHECKING`, which `get_type_hints` cannot resolve at runtime. Found production uses were legal-only or formatting-only; no default GY route injection of `DatasetCatalogGraph` or `ScholarKnowledgeGraph` was found.

Validator: `tools/quality/validation/check_layer3_gy_p2_semantic_evidence_quality_audit.py`.

Next audit probe: after P2 is used in planning, decide exact semantic benchmark thresholds and whether GY-6 must consume canonical SKG, web evidence bundles, or both. Acceptance should include persisted query traces/no-hit frontiers, route-scope precision gates, and event-backed KnowledgeToolkit/tool-loop outputs.

13. **Workflow-mode truth (which of the 3 execution modes the route actually runs)**

The census, lex root-cause, and foundry-breadth audits all ran `scientist_policy_design`. GY-0 finding #1 showed no production runtime path selects it.

Follow-up completed: see `layer3_gy_workflow_mode_truth_audit.json` and `layer3_gy_workflow_mode_truth_findings.md`.

Observed result (proven on the real panel, `JAX_PLATFORMS=cpu`): the NL route resolves to `scientist_causal_full` (transport/serious) or `scientist_policy_verified` (policy question), never `scientist_policy_design` (only an explicit `workflow_id`/`policy_mode` selects it, which no runtime caller sets). Two resolver bugs: (1) NL never sets `policy_mode`/`workflow_id`; (2) an explicit `scientist_causal_full` request is silently overridden to `scientist_policy_verified` because the explicit check sits at `selection.py:57`, after the policy_verified heuristic (line 53) — proven by an explicit causal_full call executing the 28-node policy_verified spec. The 3 specs share a **19-node spine with identical `node_id`** (real reuse); `policy_verified` has **0 unique nodes** (subset of `policy_design`). Real failure modes differ by mode but converge on the **shared governance/validation tail**: `policy_design` fails at lex (`run_hierarchical_policy_search`); `policy_verified`/`causal_full` reach the tail and fail at `run_normative_arbitration` (`node.invalid_outcome`, a pydantic re-validation failure) or `build_verified_policy_report` (`phase5_validation_failed`, all 6 judges fatal). lex is masked in `policy_design` because it fails first; **repairing lex alone does not unblock the route**.

Consolidation map (reuse 19-node spine; merge legal + literature arms; build-out/fold lex-design-space and transport-ensemble arms as conditional sub-DAGs; `policy_verified` is redundant; fix `trinity_bundle_ref` from hard-required-bind to produced-or-supplied) is in the findings file.

Validator: `tools/quality/validation/check_layer3_gy_workflow_mode_truth_audit.py` (recomputes the node-set algebra from the live specs).

Next audit probe: trace which production caller (if any) sets `workflow_id=scientist_policy_design` via `launch_workflow_run`; and define the single-mode spine + conditional-arm topology before any GY-2 governance work.

## Recommended Audit Order

1. Completed: the **repo-wide capability coverage matrix** (`layer3_gy_capability_coverage_matrix.json` / `..._findings.md`): 29 capabilities × the chain `contract → producer → artifact/event → bridge → consumer → surface → semantic test`. Result: contract proven 26/29, producer proven/partial 29/29, but `bridge_missing` 20/29, `surface_missing` 10/29, `semantic_test` absent 16/29; only 1/29 chains fully green. The break is integration + governance + verification, not absent capability. Validator: `tools/quality/validation/check_layer3_gy_capability_coverage_matrix.py`.
2. Completed: run the **no-write catalog-to-fetch measurement-root probe** for the pinned route.
3. Completed: run the **surface laundering probe** across run index, API, artifact, lineage, public export, and dashboard fixtures.
4. Completed: run the **DAG diagnostic probe**: lex root cause, blocked-input state reads, foundry method breadth.
5. Completed: run the **generated/public surface lifecycle probe** for GY/GX/Layer 3 artifacts and OpenAPI/dashboard/client generated families.
6. Remaining before GY-0.5: build the repo-wide coverage matrix, audit Scholar/OpenAlex/KnowledgeToolkit, and decide GY Task 0 artifact lifecycle classification.

## Non-Goals

- Do not fix connectors, lex, dashboard, public exports, or reducers during this audit.
- Do not expand GY-0 by pretending all broader-system packages are pinned-route rows.
- Do not treat a green census validator as omission-completeness; it is row-consistency plus known blocker discipline.
