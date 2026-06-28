---
title: PolicyOS Layer 2 S10 Outcome Prediction And Welfare Comparison Implementation Plan
status: active
owner: team-research
created: 2026-06-02
last_verified: null
stability: draft
revision_note: drafted 2026-06-02 after S9 verification to expand the roadmap S10 closure contract into red-first tasks
slice: S10
slice_label: outcome_prediction_welfare_comparison
roadmap: ../POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER2_IMPLEMENTATION_PLAN.md
source_design_doc: ../../../system-design-decisions/universal-policy-design-target-architecture-and-gap.md
cluster_ownership_map: ../../../../architecture/policy_design_case/cluster_ownership_map.toml
slice_cell_matrix: ../../../../architecture/policy_design_case/layer2_slice_cell_matrix.toml
floor_governance: ../../../../architecture/policy_design_case/layer2_floor_governance.toml
artifact_traceability: ../../../../architecture/policy_design_case/layer2_artifact_traceability.toml
failure_patterns: ../../../reference/policy-design-case-failure-patterns.md
depends_on:
  - S5
  - S6
  - S8
cells_closed: []
layer_cells_advanced:
  - outcome_prediction_welfare_comparison
expected_current_open_cell_count: 3
floor_id: s10_calibration
floor_metric: observable_subset_calibration
---

# Layer 2 S10 - Outcome Prediction And Welfare Comparison

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

Read this whole file before editing. Execute tasks in order, keep commits
task-sized, and preserve the repo rule that forecasts are scoped support
records, never recommendation authority. S10 advances the outcome-prediction
layer and the `s10_calibration` floor. It does **not** reduce the current open
cell count below `3`, and it does not mark S11 calibration/proof-carrying
analytics, S12 envelope growth, S13 accountability, production authority,
preference learning, rich simulation, portfolio optimization, or S14
universality as implemented.

## Goal

S10 turns the S5 forecast-support scope, S6 fail-closed blind-spot outputs, and
S8 value-choice provenance into replay-visible `ForecastSupport` records and
mandate-bounded welfare comparisons. It may promote a forecast only on the
observable subset where calibration evidence exists. Non-observable,
large-scale, simulation-only, or equilibrium-contested cases remain honest
limitations or advisory/routing signals.

The closure contract is the roadmap S10 contract:

- producer: tiered prediction support plus welfare comparison over S5/S6/S8
  inputs.
- persisted artifact: forecast support on the record plus calibration records
  for observable-subset checks.
- bridge/consumer: recommendation and projection surfaces inherit the weakest
  forecast boundary.
- surface: public/reviewer/expert/machine projections expose forecast tier,
  uncertainty, limitations, and welfare-value provenance.
- semantic test: observable-subset calibration passes; non-observable cases are
  downgraded instead of silently counted.
- negative control: `equilibrium_contested` refuses a single forecast, and
  `simulation_only` cannot be projected as evidence authority.
- floor: `observable_subset_calibration` is recorded from the governed floor
  table; false-clear counts remain zero.

## Architecture

S10 is a runtime-quality forecast support layer over existing Policy Design
Case and Foundry substrates:

- `src/polisyos/runtime/quality/design_axes/coupling_composition.py` already defines
  `ForecastSupportScope`, `ForecastSupportBaseOrigin`, `ForecastClaimScope`,
  and `SystemEffectSupportLabel`. S10 must reuse that dictionary rather than
  creating a separate forecast-tier vocabulary. Any serialized `forecast_tier`
  is a derived authority disposition over `base_origin x claim_scope x
  support_label`, not a second source taxonomy.
- `src/polisyos/pdc/_impl/layer2_design_search.py` already carries
  `forecast_support_label` through S5/S2 projection context. S10 should extend
  this into injected forecast posture refs; B-side search must not self-mint
  calibrated forecast authority.
- `src/polisyos/runtime/quality/design_axes/value_choice_provenance.py` already carries S8
  value schedules, Pareto archives, and tradeoff disclosures. S10 welfare
  comparisons must cite those refs and cannot rank alternatives without them.
  Scalar welfare summaries must not hide Pareto tradeoffs, social-weight
  provenance, or unresolved multi-principal conflict.
- `src/polisyos/runtime/quality/design_axes/blind_spot_firewalls.py` and S6 corpus
  summaries already expose measurability, capacity, mandate, aggregation, and
  strategic-response firewall results. Any failed or limited S6 axis caps S10
  forecast authority.
- Foundry causal/optimization/bayesian methods already exist in
  `src/polisyos/foundry/methods/` and tests under
  `tests/unit/foundry/methods/`. S10 does not build a new modeling engine; it
  records whether an existing method family has authority for the requested
  scope. For `validated_local_model` support, S10 must require source-contract,
  method-validity, calibration, sensitivity, and dynamic/equilibrium validation
  refs where the claim scope is system-level.
- `src/polisyos/runtime/quality/calibration_ledger.py` and runtime scorecard
  calibration behavior exist for longitudinal calibration. S10 uses a narrow
  observable-subset calibration record only; it must not close the S11
  `KNOWLEDGE.calibration` cell.

Boundary rule: S10 can produce `ForecastSupport` and
`ForecastCalibrationRecord` runtime-quality artifacts. PDC search and projection
may consume injected S10 posture refs, but `src/polisyos/pdc/_impl/layer2_design_search.py`
must not import `polisyos.runtime.quality.design_axes.outcome_prediction` or call
S10 producer helpers directly.

## Scope

In scope:

- strict Pydantic S10 runtime-quality contracts exported from
  `polisyos.runtime.quality`.
- `ForecastSupport` and `ForecastCalibrationRecord` as the two S10 traceability
  artifacts named by the roadmap.
- strict nested DTOs inside S10 for outcome distribution rows, welfare
  comparison rows, authority-envelope checks, and integrity reports, with field
  contracts in Task 2.
- `DesignGraph + context` input refs, including design graph, baseline,
  alternatives, jurisdiction/scope, horizon, and policy context refs.
- observable-subset calibration with denominator, numerator, pass rate,
  threshold/floor refs, credible-evaluation refs, metric refs, and rule version
  refs.
- welfare comparisons grounded in S8 value-choice provenance and Pareto/tradeoff
  refs.
- method/source authority refs: source contract, method validity, sensitivity,
  dynamic/equilibrium caveats, and source/method lineage.
- fail-closed caps from S6 axes and forecast-scope caps from S5 coupling.
- W12.D S10 blocks for all 13 universal corpus cases.
- negative controls for equilibrium-contested, simulation-only, uncalibrated
  promotion, missing S8 value provenance, hidden uncertainty, and forecast
  authority laundering, plus missing design graph/context, missing method/source
  validity, observed outcomes without credible evaluation evidence, and scalar
  welfare rankings that hide Pareto/value conflict.
- manifest, inventory, traceability, readiness validator, and repo-quality
  coverage.

Out of scope:

- rich blind-spot predictive models, longitudinal calibration history, or
  proof-carrying analytics. Those belong to S11.
- envelope growth, cold-start thermometers, or resource-economics policy. Those
  belong to S12.
- post-deploy accountability, realized regret, or attribution learning outside
  cases with credible counterfactuals. Those belong to S13.
- universality battery or self-description authority. That belongs to S14.
- production recommendation, rollout, publication, approval, closeout, claim,
  scorecard, or preference-learning authority.

## Pattern Pass

Open the failure register before implementation and before closeout:
`docs/reference/policy-design-case-failure-patterns.md`.

| Pattern | S10 risk | Closure move |
| --- | --- | --- |
| P01 contract-only capability | Existing Foundry methods and S5 forecast labels exist, but no Layer 2 S10 producer, corpus floor, manifest, or consumer path proves forecast support is used safely. | Add typed contracts, producer, corpus route, manifest, readiness checks, and semantic tests. |
| P03 hidden internal richness | Forecast uncertainty, weak support, or non-observable status may be hidden from public/reviewer output. | Surface forecast tier, uncertainty refs, limitations, and calibration status in all audience projections. |
| P04 status lattice gap | `calibrated`, `limited`, `simulation_only`, and `equilibrium_contested` can drift from support/admissibility/status semantics. | Keep local S10 tier statuses mapped to existing authority boundaries and add mixed-status tests. |
| P05 authority dilution | A forecast or welfare comparison can look like recommendation/claim authority. | Every S10 artifact carries `authoritative_for` and `may_not_use_for`; consumers inherit the weakest boundary. |
| P07 replay gap | Forecast support tiers can change without replay-visible calibration evidence. | Persist rule/schema versions, source refs, calibration record refs, and tier-change revision rules. |
| P08 time-role conflation | Forecast time, observation time, policy effective time, data-valid time, and calibration window can collapse into one date. | Add explicit time-role fields and block calibration if windows mismatch. |
| P10 semantic adequacy gap | Field presence can pass while simulation-only evidence is laundered as calibrated support. | Red-first semantic tests and negative probes for simulation-only, equilibrium-contested, and uncalibrated promotion. |
| P13 contract gravity | Prediction contracts can balloon into a modeling platform. | Reuse existing Foundry/calibration/S5 scopes; S10 records support authority, not model internals. |
| P14 evidence independence inflation | Multiple forecasts from shared data/model lineage can look independent. | Record method/source lineage refs and do not count dependent forecasts as independent support. |
| P15 candidate laundering | LLM prose can convert forecast support into a claim or recommendation. | Forecast prose is candidate-only unless producer/calibration authority validates the support tier. |
| P16 regime laundering | A regime label can be used to upgrade forecast authority. | Treat regime and forecast origin as orthogonal; regime alone cannot promote derived forecast disposition. |
| P17 partial-equilibrium laundering | Leaf claims can be composed into system-effect forecasts before coupling validity holds. | Require S5 claim scope and coupling support labels; system-effect claims need dynamic/equilibrium checks or downgrade. |
| P24 strategic-response laundering | Pre-policy effects can be projected into a changed incentive world. | Require strategic-response/firewall refs or explicit response caveats for system-effect support. |
| P25 search-control laundering | Forecast posture can make the current S2 frontier look exhaustive or recommended. | Preserve search incompleteness and keep forecast support separate from recommendation/closeout authority. |

Capability label transition:

- start: `ForecastSupport` and `ForecastCalibrationRecord` are planned
  traceability rows; `s10_calibration` floor exists but is not wired.
- target: S10 layer is `implemented`, inventory count increases by one
  governed manifest, and current open cell count remains `3`.
- missing chain to close: producer, persisted artifact, bridge/consumer,
  verification, projection surface, semantic tests, negative controls, manifest,
  and readiness validator.

## Code-Grounded Reality Check

Current S10 anchors:

- `architecture/policy_design_case/layer2_dependency_dag.json` declares
  `S10` label `outcome_prediction` with prerequisites `S5`, `S6`, and `S8`.
- `architecture/policy_design_case/layer2_floor_governance.toml` declares
  `floor_id = "s10_calibration"`, `metric = "observable_subset_calibration"`,
  `floor_owner = "team-research"`, and revision rule
  `forecast_support_tier_change_requires_calibration_record`.
- `architecture/policy_design_case/layer2_artifact_traceability.toml` already
  contains `ForecastSupport` and `ForecastCalibrationRecord` as S10
  `planned`.
- `architecture/policy_design_case/layer2_slice_cell_matrix.toml` assigns
  remaining `KNOWLEDGE.calibration` and
  `KNOWLEDGE.ir_proof_carrying_analytics` to S11, not S10. S10 must not close
  either cell.
- `src/polisyos/runtime/quality/design_axes/coupling_composition.py` has the S5
  `ForecastSupportScope` dictionary. S10 must extend this support scope into
  forecast authority records.
- `src/polisyos/pdc/_impl/layer2_design_search.py` carries
  `forecast_support_label` in S2 projections and ledger context. S10 should add
  forecast posture refs around this existing field, not replace S2/S5 logic.
- `tests/fixtures/layer2/s5/s5_coupling_expert_labels.json` already contains
  `forecast_support_scope` rows for all 13 cases, including
  `equilibrium_contested`, `simulation_only_system_effect`,
  `transported_with_heavy_limitation`, and
  `historical_prior_system_context`.
- `tools/quality/validation/run_universal_outcome_corpus.py` currently omits
  S10. Insert it between the existing S8 and S2 phases: build forecast posture
  from the case design graph/context plus S5/S6/S8, pass that posture into S2
  projection context, then let S9 consume the S2 record. S10 must not rerun
  S5/S6/S8.
- `tools/quality/validation/check_policy_design_case_layer2_readiness.py`
  currently validates up through S9 and reports inventory artifact count `17`.
  S10 registration should update this to `18`.

## Code-Grounded Workload Boundaries

Use these boundaries to avoid both underestimating S10 wiring and overbuilding a
new prediction platform:

- Strong substrate: `Layer2ReadinessModel` and `AuthorityBoundary` already live
  in `src/polisyos/pdc/_impl/layer2_readiness.py` and are strict/frozen. S10
  should reuse them; no new DTO base or authority-boundary abstraction is needed.
- Strong substrate: S5 already owns the D3.5 forecast dictionary in
  `src/polisyos/runtime/quality/design_axes/coupling_composition.py`. S10 should
  derive disposition from the raw `forecast_support_scope` block and should not
  expand `Layer2S5CompositionPostureInput` unless S2 actually needs extra S5
  fields.
- Strong substrate: S6 already emits `axis_rows`, `blocking_axis_refs`,
  `limiting_axis_refs`, `post_intervention_dgp_update_ref`,
  `system_dynamics_handoff_required`, and `false_clear_penalty`. S10 should map
  those refs into caps/caveats; it should not create new S6 measurability,
  capacity, mandate, aggregation, or strategic-response producers.
- Strong substrate: S8 already separates `ParetoArchive`,
  `ValueChoiceProvenanceRecord`, `ValueTradeoffDisclosureRecord`, social-weight
  provenance, conflict rows, rejected nondominated alternatives, and blocking
  rights. S10 welfare comparison should consume these refs. Do not build a
  second normative-choice firewall.
- Strong substrate: `public_export.py` already has scalar-welfare/frontier
  guards, and `projection_semantics.py` already has the S9 consumer-contract
  adapter shape. S10 should add forecast-specific checks around those surfaces,
  not duplicate general public-export redaction or S9 faithfulness machinery.
- Strong substrate: W12.D already computes S4/S5/S6/S7/S8 and injects S5/S6/S7/S8
  compact posture DTOs into the S2 loop. Follow that pattern for S10.
- Real wiring cost: S5/S6/S7/S8 posture DTOs are defined in
  `src/polisyos/pdc/_impl/layer2_design_search.py`, not in
  `layer2_readiness.py`. `Layer2S10ForecastPostureInput` belongs beside those
  DTOs and is exported through `polisyos.pdc`.
- Real wiring cost: S2 has no generic posture extension point. Task 3 must touch
  `Layer2S2DesignSearchRun`, `run_s2_shadow_design_loop(...)`, `_search_ledger`,
  `_design_record`, replay digest construction, cluster interface/handoff
  helpers, and projection helpers. A DTO plus public export is not enough.
- Real wiring cost: `SearchLedger` has explicit S8 value fields but no forecast
  fields. Add compact S10 fields such as `forecast_support_refs`,
  `forecast_calibration_record_refs`, `forecast_authority_status`,
  `forecast_authority_boundary`, and `forecast_posture_ref`; do not dump every
  S10 source ref into `DesignRecordV0.ledger_refs`, which is capped at 40.
- Real wiring cost: the current W12.D S2 full shadow loop runs only for the first
  proving case. For the other 12 cases, S10 can still produce corpus blocks and
  the lightweight S2 `not_applicable` branch should carry forecast posture refs,
  but Task 4 must not silently require full S2 search for all 13 cases.
- Real wiring cost: readiness/inventory tests currently hard-code the global
  inventory count as `17` after S9. S10 must update S8/S9 readiness assertions
  that read global inventory count while preserving S9's own manifest semantics.
- Real wiring cost: the inventory snapshot tax also exists in older S6/S7 repo
  tests. S10 must update every live `inventory_artifact_count == 17` assertion in
  S6/S7/S8/S9 coverage. Use one exact post-S10 count assertion in the central
  readiness/S10 closeout tests; older per-slice tests should assert their own
  manifest presence and a nondecreasing inventory lower bound so S11+ does not
  require another growing patch set.
- Weak spot: existing S5/S6/S8 fixtures do not carry complete S10
  `DesignGraph + context`, credible-evaluation, method-validity, or
  counterfactual-credibility refs. Task 4 fixture work is nontrivial and should
  be treated as semantic data modeling, not JSON padding.

## S10 Closure Metrics

S10 closure is measured against these exact constraints:

- slice: `S10`.
- cells closed: `[]`.
- open-cell delta: `0`; expected current open cell count remains `3`.
- remaining open cells stay exactly:
  - `DESIGNER_ITSELF.envelope_growth`
  - `KNOWLEDGE.calibration`
  - `KNOWLEDGE.ir_proof_carrying_analytics`
- floor: `s10_calibration`.
- floor metric: `observable_subset_calibration`.
- governed Layer 2 inventory artifact count after S10: `18`.
- required artifacts: `ForecastSupport`, `ForecastCalibrationRecord`.
- corpus case count: `13`.
- observable-subset calibration denominator: at least `4`.
- observable-subset calibration numerator equals denominator.
- observable-subset calibration status: `pass`.
- observable-subset calibration floor passed: `true`.
- observable-subset calibration pass rate meets the governed threshold ref; do
  not encode perfect prediction as the semantic contract.
- non-observable downgrade count: at least `1`.
- `equilibrium_contested` single-forecast block count: at least `1`.
- `simulation_only` evidence-laundering block count: at least `1`.
- weakest-boundary inheritance count: `13`.
- all S10 false-clear count fields: `0`.

## Task 1: Red-First S10 Semantic And Negative Tests

Intent: prove the current repo fails the S10 semantic contract before adding the
producer, manifest, and corpus wiring. Do not weaken existing S5/S6/S8/S9
assertions.

- [ ] **Step 1: Add runtime S10 contract tests**

Create `tests/unit/runtime/quality/test_layer2_s10_outcome_prediction.py`.

Add tests with these exact names:

- `test_forecast_support_requires_s5_s6_s8_authority_inputs`
- `test_forecast_support_requires_design_graph_and_prediction_context_refs`
- `test_forecast_authority_disposition_is_derived_from_s5_dictionary`
- `test_observable_subset_calibration_controls_forecast_promotion`
- `test_observable_calibration_requires_credible_evaluation_evidence`
- `test_equilibrium_contested_refuses_single_point_forecast`
- `test_simulation_only_projection_is_evidence_blocked`
- `test_welfare_comparison_requires_s8_value_choice_provenance`
- `test_scalar_welfare_summary_cannot_hide_pareto_tradeoff`
- `test_validated_local_model_requires_source_contract_and_method_validity`
- `test_regime_label_cannot_promote_forecast_tier`
- `test_prediction_authority_envelope_denies_production_and_s11`
- `test_hidden_uncertainty_interval_is_rejected`
- `test_transport_without_limitation_is_rejected`

The tests should import from
`polisyos.runtime.quality.design_axes.outcome_prediction` and initially fail with
`ModuleNotFoundError` or missing export errors.

- [ ] **Step 2: Add PDC wiring red tests**

Modify `tests/unit/pdc/test_layer2_readiness_contracts.py` and
`tests/unit/pdc/test_layer2_s2_design_search.py`.

Required assertions:

- `Layer2S10ForecastPostureInput` is strict and exported from `polisyos.pdc`.
- S2 search accepts an injected S10 forecast posture and records
  `forecast_support_refs`, `forecast_calibration_record_refs`,
  `forecast_authority_status`, and `forecast_authority_boundary` in its
  ledger/projection context.
- injected S10 posture carries `design_graph_ref`, `prediction_context_ref`,
  method/source validity refs, and credible-evaluation refs without letting S2
  recompute them.
- S2 replay digest changes when `forecast_posture` changes and remains stable
  when the same forecast posture is replayed.
- S2 replay digest remains exactly unchanged for a no-S10 run where
  `forecast_posture is None`, preserving pre-S10 S2/S4/S5/S6/S7/S8/S9
  determinism.
- `SearchLedger` carries compact forecast refs/status without overflowing
  `DesignRecordV0.ledger_refs`.
- `SearchLedger` defaults keep backward-compatible load behavior for old ledgers:
  empty forecast ref lists, `forecast_authority_status == "not_applicable"`, and
  no `forecast_authority_boundary` when no S10 posture was injected.
- S2 handoff/interface records include `Layer2S10ForecastPostureInput` as a
  consumed forecast-support posture, not recommendation authority.
- `src/polisyos/pdc/_impl/layer2_design_search.py` does not import
  `polisyos.runtime.quality.design_axes.outcome_prediction` and does not call
  `build_forecast_support(...)`.
- PUBLIC projection exposes forecast tier and limitations, but not production
  recommendation text.
- EXPERT/MACHINE projection exposes source refs, calibration refs, uncertainty
  interval refs, and weakest-boundary inheritance.

- [ ] **Step 3: Add projection/public export red tests**

Modify:

- `tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py`
- `tests/unit/runtime/quality/test_public_export.py`

Required test names:

- `test_s10_projection_semantics_blocks_simulation_only_as_evidence`
- `test_s10_projection_semantics_preserves_uncertainty_and_boundary`
- `test_s10_public_export_shows_forecast_tier_without_recommendation_authority`
- `test_s10_machine_export_requires_calibration_and_source_refs`
- `test_s10_machine_export_preserves_design_graph_context_and_method_validity_refs`
- `test_s10_projection_semantics_blocks_scalar_welfare_tradeoff_hiding`

- [ ] **Step 4: Add W12.D corpus red tests**

Modify `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`.

Add assertions:

- every one of the 13 cases contains `s10_outcome_prediction`.
- all S10 blocks consume existing `s5_coupling_composition`,
  `s6_blind_spot_firewalls`, and `s8_value_choice` summaries.
- the first proving case runs full S2 with injected forecast posture.
- the other 12 cases keep lightweight S2 `not_applicable` summaries but still
  expose S10 forecast posture refs and do not trigger full S2 search.
- `s10_outcome_prediction_summary["case_count"] == 13`.
- `observable_subset_calibration_denominator >= 4`.
- numerator equals denominator for the seed corpus, calibration status is `pass`,
  and floor-passed is `true`; do not encode perfect prediction as a reusable
  rule outside the seed fixture.
- `non_observable_downgrade_count >= 1`.
- `equilibrium_contested_single_forecast_false_clear_count == 0`.
- `simulation_only_evidence_laundering_false_clear_count == 0`.
- at least one case has `forecast_tier == "observable_calibrated"`.
- at least one case has `forecast_tier == "simulation_only_advisory"`.
- at least one case has `forecast_tier == "equilibrium_contested_blocked"`.

- [ ] **Step 5: Add readiness repo-quality red tests**

Create `tests/repo_quality/tools/test_policy_design_case_layer2_s10_outcome_prediction.py`.

Modify:

- `tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s6_blind_spot_firewalls.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s7_delegation.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s8_value_choice.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s9_projection_lowering.py`

Required assertions:

- S10 manifest exists at
  `architecture/policy_design_case/layer2_s10_outcome_prediction_manifest.json`.
- `summary["s10_case_count"] == 13`.
- `summary["s10_observable_subset_calibration_denominator"] >= 4`.
- `summary["s10_observable_subset_calibration_status"] == "pass"`.
- `summary["s10_observable_subset_calibration_floor_passed"] is True`.
- `summary["s10_non_observable_downgrade_count"] >= 1`.
- `summary["s10_false_clear_counts"]["simulation_only_evidence_laundering"] == 0`.
- `summary["s10_false_clear_counts"]["observed_outcome_without_credible_evaluation"] == 0`.
- `summary["s10_false_clear_counts"]["scalar_welfare_hides_pareto_tradeoff"] == 0`.
- `summary["current_open_cell_count"] == 3`.
- central readiness/S10 closeout coverage asserts
  `summary["inventory_artifact_count"] == 18`.
- legacy S6/S7/S8/S9 per-slice tests no longer assert the exact live global count
  `17`; they assert their own manifest remains registered and the inventory
  count is at least the post-S10 floor.
- `ForecastSupport` and `ForecastCalibrationRecord` are traceable and exported.
- no S11/S12/S13/S14 artifact maturity is marked `implemented`.

- [ ] **Step 6: Run the red S10 suite**

```bash
uv run pytest \
  tests/unit/runtime/quality/test_layer2_s10_outcome_prediction.py \
  tests/unit/pdc/test_layer2_readiness_contracts.py \
  tests/unit/pdc/test_layer2_s2_design_search.py \
  tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py \
  tests/unit/runtime/quality/test_public_export.py \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s6_blind_spot_firewalls.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s7_delegation.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s8_value_choice.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s9_projection_lowering.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s10_outcome_prediction.py \
  -q
```

Expected red output:

- `test_layer2_s10_outcome_prediction.py` fails because
  `polisyos.runtime.quality.design_axes.outcome_prediction` does not exist.
- W12.D tests fail because `s10_outcome_prediction_summary` and case blocks are
  absent.
- readiness tests fail because S10 manifest/inventory/summary fields are absent.

- [ ] **Step 7: Commit Task 1**

```bash
git add tests/unit/runtime/quality/test_layer2_s10_outcome_prediction.py \
  tests/unit/pdc/test_layer2_readiness_contracts.py \
  tests/unit/pdc/test_layer2_s2_design_search.py \
  tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py \
  tests/unit/runtime/quality/test_public_export.py \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s6_blind_spot_firewalls.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s7_delegation.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s8_value_choice.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s9_projection_lowering.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s10_outcome_prediction.py
git commit -m "test: add layer2 s10 prediction red tests" \
  -m "Co-authored-by: Cursor <cursoragent@cursor.com>"
```

## Task 2: Contracts, Producer, Calibration Verifier, And Authority Envelope

Intent: implement the S10 A-side/runtime-quality producer and strict contracts
without building a new modeling engine.

- [ ] **Step 1: Add S10 runtime-quality module**

Create `src/polisyos/runtime/quality/design_axes/outcome_prediction.py`.

Required constants:

- `LAYER2_S10_OUTCOME_PREDICTION_SCHEMA_VERSION =
  "policyos.policy_design_case.layer2_s10_outcome_prediction.v1"`
- `LAYER2_S10_OUTCOME_PREDICTION_RULE_VERSION =
  "policyos.layer2.s10.outcome_prediction.v1"`
- `S10_CALIBRATION_FLOOR_ID = "s10_calibration"`

Required literals:

- `ForecastAuthorityDisposition = Literal["observable_calibrated",
  "transported_limited", "historical_prior_context",
  "simulation_only_advisory", "equilibrium_contested_blocked", "blocked"]`
  serialized as `forecast_tier` in projection/corpus payloads for compatibility.
  This is derived from the S5 `ForecastSupportScope`; it is not a second source
  forecast ladder.
- `ForecastMethodFamily = Literal["foundry_causal", "foundry_optimization",
  "foundry_bayesian", "historical_prior", "simulation", "abstain"]`
- `ObservableSubsetCalibrationStatus = Literal["pass", "limit", "blocked",
  "not_applicable_non_observable", "insufficient_history"]`
- `WelfareComparisonStatus = Literal["value_grounded", "value_limited",
  "blocked_missing_value_provenance", "blocked_hidden_pareto_tradeoff"]`

- [ ] **Step 2: Add strict S10 contracts**

Add these strict Pydantic models:

- `ForecastSupport`
- `ForecastCalibrationRecord`
- `OutcomeDistributionRecord`
- `WelfareComparisonRecord`
- `PredictionAuthorityEnvelope`
- `ForecastSupportIntegrityReport`

`ForecastSupport` must include:

- `support_id`, `support_ref`, `case_id`
- `source_design_record_ref`
- `design_graph_ref`, `prediction_context_ref`, `policy_context_ref`
- `candidate_design_ref`, `baseline_design_ref`, `alternative_design_refs`
- `prediction_horizon_ref`, `target_outcome_refs`, `jurisdiction_scope_ref`
- `s5_forecast_support_ref`, `s5_support_label`, `s5_base_origin`,
  `s5_claim_scope`
- `s6_firewall_status_refs`, `s6_limitation_refs`
- `s8_value_choice_provenance_ref`, `s8_value_tradeoff_disclosure_ref`
- `source_contract_ref`, `method_validity_ref`, `sensitivity_analysis_ref`
- `dynamic_equilibrium_check_ref`, `equilibrium_caveat_refs`,
  `strategic_response_caveat_refs`
- `outcome_distribution_refs`, `welfare_comparison_ref`
- `forecast_tier`, `forecast_authority_disposition_reason`, `method_family`
- `observable_subset_ref`, `calibration_record_ref`
- `uncertainty_interval_refs`, `limitation_refs`, `abstention_refs`
- `authority_boundary`, `may_not_use_for`, `rule_version_ref`

`ForecastCalibrationRecord` must include:

- `calibration_id`, `calibration_ref`, `case_id`
- `forecast_support_ref`
- `observable_subset_ref`
- `prediction_ref`, `observed_outcome_ref`
- `historical_implementation_ref`, `evaluation_design_ref`
- `credible_evaluation_evidence_ref`, `counterfactual_credibility`
- `prediction_time`, `observation_time`, `policy_effective_time`,
  `data_valid_time`, `calibration_window_start`, `calibration_window_end`
- `metric_name = "observable_subset_calibration"`
- `denominator`, `numerator`, `pass_rate`, `calibration_threshold_ref`,
  `floor_passed`
- `calibration_status`
- `interval_coverage_metric`, `calibration_error_metric`
- `source_lineage_refs`, `method_lineage_refs`
- `floor_id`, `authority_boundary`, `may_not_use_for`, `rule_version_ref`

`OutcomeDistributionRecord` must include:

- `distribution_id`, `distribution_ref`, `case_id`
- `forecast_support_ref`
- `design_graph_ref`, `prediction_context_ref`, `policy_context_ref`
- `candidate_design_ref`, `baseline_design_ref`, `alternative_design_refs`
- `target_outcome_ref`, `outcome_unit_ref`, `prediction_horizon_ref`,
  `jurisdiction_scope_ref`
- `method_family`, `source_contract_ref`, `method_validity_ref`
- `point_estimate_ref`, `uncertainty_interval_ref`, `interval_lower_ref`,
  `interval_upper_ref`
- `distribution_shape`, `forecast_tier`, `s5_support_label`
- `non_observable_downgrade_reason`, `limitation_refs`, `rule_version_ref`

`WelfareComparisonRecord` must include:

- `comparison_id`, `comparison_ref`, `case_id`
- `forecast_support_ref`
- `candidate_design_ref`, `baseline_design_ref`, `alternative_design_refs`
- `outcome_distribution_refs`
- `s8_value_choice_provenance_ref`, `s8_value_tradeoff_disclosure_ref`
- `pareto_archive_ref`, `authorized_value_schedule_ref`
- `social_weight_provenance_refs`, `principal_refs`, `conflict_refs`,
  `blocking_rights_refs`
- `welfare_comparison_status`, `ranking_mode`, `scalar_summary_allowed`
- `scalar_welfare_summary_ref`, `pareto_frontier_ref`,
  `rejected_nondominated_alternative_refs`
- `limitation_refs`, `authority_boundary`, `may_not_use_for`,
  `rule_version_ref`

`PredictionAuthorityEnvelope` must include:

- `envelope_id`, `envelope_ref`, `case_id`
- `forecast_support_ref`, `forecast_tier`, `forecast_authority_disposition_reason`
- `weakest_boundary_source`
- `legal_boundary_ref`, `data_boundary_ref`, `method_boundary_ref`,
  `participation_boundary_ref`, `epistemic_regime_boundary_ref`,
  `coupling_boundary_ref`, `prediction_boundary_ref`,
  `welfare_value_choice_boundary_ref`, `state_capacity_boundary_ref`,
  `reversibility_stakes_boundary_ref`, `strategic_response_boundary_ref`
- `calibration_status`, `observable_subset_ref`, `calibration_record_ref`
- `source_contract_ref`, `method_validity_ref`,
  `credible_evaluation_evidence_ref`
- `denies_production_authority`, `denies_recommendation_authority`,
  `denies_claim_authority`, `denies_closeout_authority`,
  `denies_s11_authority`
- `issue_codes`, `envelope_status`, `authority_boundary`,
  `may_not_use_for`, `rule_version_ref`

`ForecastSupportIntegrityReport` must include:

- `report_id`, `report_ref`
- `case_count`
- `forecast_support_refs`, `forecast_calibration_record_refs`
- `observable_subset_calibration_denominator`,
  `observable_subset_calibration_numerator`,
  `observable_subset_calibration_pass_rate`,
  `observable_subset_calibration_status`,
  `observable_subset_calibration_threshold_ref`,
  `observable_subset_calibration_floor_passed`
- `non_observable_downgrade_count`
- `equilibrium_contested_single_forecast_block_count`
- `simulation_only_evidence_block_count`
- `weakest_boundary_inheritance_count`
- `false_clear_counts`
- `false_clear_counts` keys must exactly match `S10_FALSE_CLEAR_FIELDS`
- `issue_codes`, `authority_boundary`, `may_not_use_for`,
  `rule_version_ref`

- [ ] **Step 3: Add producer and verifier helpers**

Add functions:

- `build_prediction_authority_boundary(...) -> AuthorityBoundary`
- `build_forecast_calibration_record(...) -> ForecastCalibrationRecord`
- `build_forecast_support(...) -> ForecastSupport`
- `build_welfare_comparison_record(...) -> WelfareComparisonRecord`
- `verify_prediction_authority_envelope(...) -> PredictionAuthorityEnvelope`
- `summarize_forecast_support_integrity(...) -> ForecastSupportIntegrityReport`

Rules:

- `equilibrium_contested` always maps to
  `forecast_tier = "equilibrium_contested_blocked"` for system-effect claims.
- `simulation_only` can map only to `simulation_only_advisory`, never
  `observable_calibrated`.
- `observable_calibrated` requires a `ForecastCalibrationRecord` with
  `calibration_status == "pass"`, `floor_passed is True`, a
  `calibration_threshold_ref`, and credible evaluation evidence for the
  observable subset.
- `validated_local_model` requires source contract, method validity, method
  lineage, source lineage, sensitivity, and calibration refs before it can
  produce governed support.
- `claim_scope == "system_effect"` requires dynamic/equilibrium checks or
  explicit caveat refs; otherwise downgrade to `simulation_only_advisory` or
  `equilibrium_contested_blocked` according to S5 support label.
- `historical_prior` remains context/routing influence only and never current-run
  evidence, even when it improves review ordering.
- welfare comparison requires S8 value-choice provenance and tradeoff refs.
- welfare comparison cannot collapse Pareto tradeoffs, unresolved social-weight
  provenance, or multi-principal conflict into a single hidden scalar rank.
- any S6 failed/blocked axis caps forecast tier to `blocked` or
  `simulation_only_advisory`.
- risk/regime labels alone never promote forecast tier.
- consumers inherit the weakest boundary among legal, data, method,
  participation, epistemic regime, coupling, prediction, welfare/value-choice,
  state-capacity, reversibility/stakes, and strategic-response assumptions.
- `may_not_use_for` must include production/recommendation/claim/closeout/S11
  authority denials.

- [ ] **Step 4: Export public API**

Modify `src/polisyos/runtime/quality/__init__.py`.

Export all S10 contracts, literals, constants, and helpers.

- [ ] **Step 5: Run Task 2 tests**

```bash
uv run pytest tests/unit/runtime/quality/test_layer2_s10_outcome_prediction.py -q
uv run ruff check src/polisyos/runtime/quality/design_axes/outcome_prediction.py \
  src/polisyos/runtime/quality/__init__.py \
  tests/unit/runtime/quality/test_layer2_s10_outcome_prediction.py
```

Expected green output:

- pytest exits `0`.
- ruff prints `All checks passed!`.

- [ ] **Step 6: Commit Task 2**

```bash
git add src/polisyos/runtime/quality/design_axes/outcome_prediction.py \
  src/polisyos/runtime/quality/__init__.py \
  tests/unit/runtime/quality/test_layer2_s10_outcome_prediction.py
git commit -m "feat: add layer2 s10 forecast support contracts" \
  -m "Co-authored-by: Cursor <cursoragent@cursor.com>"
```

## Task 3: Wire S10 Forecast Posture Into PDC Context, Semantics, And Export

Intent: make S10 consumable by existing PDC projection and export surfaces
without letting B-side search self-certify forecast authority.

- [ ] **Step 1: Add PDC S10 posture input**

Modify:

- `src/polisyos/pdc/_impl/layer2_design_search.py`
- `src/polisyos/pdc/__init__.py`

Add strict `Layer2S10ForecastPostureInput` next to the existing
`Layer2S5CompositionPostureInput`, `Layer2S6BlindSpotPostureInput`,
`Layer2S7DelegationPostureInput`, and `Layer2S8ValuePostureInput` classes with:

- `forecast_support_ref`
- `forecast_tier`
- `forecast_authority_disposition_reason`
- `forecast_support_label`
- `forecast_calibration_record_ref`
- `design_graph_ref`
- `prediction_context_ref`
- `policy_context_ref`
- `candidate_design_ref`
- `baseline_design_ref`
- `alternative_design_refs`
- `prediction_horizon_ref`
- `observable_subset_ref`
- `uncertainty_interval_refs`
- `welfare_comparison_ref`
- `s5_forecast_support_ref`
- `s6_firewall_status_refs`
- `s8_value_choice_provenance_ref`
- `s8_value_tradeoff_disclosure_ref`
- `source_contract_ref`
- `method_validity_ref`
- `credible_evaluation_evidence_ref`
- `dynamic_equilibrium_check_ref`
- `sensitivity_analysis_ref`
- `authority_boundary`
- `may_not_use_for`
- `rule_version_ref`

Export it from `src/polisyos/pdc/__init__.py`.

Do not add this DTO to `src/polisyos/pdc/_impl/layer2_readiness.py` unless a
future S10 task needs a shared base contract; current posture inputs live in
`layer2_design_search.py`.

- [ ] **Step 2: Inject S10 posture into S2 search**

Modify `src/polisyos/pdc/_impl/layer2_design_search.py`.

Rules:

- add optional `forecast_posture: Layer2S10ForecastPostureInput | None` to
  `run_s2_shadow_design_loop(...)`.
- add `forecast_posture: Layer2S10ForecastPostureInput | None = None` to
  `Layer2S2DesignSearchRun`, following the existing S5/S6/S7/S8 posture fields.
- pass `forecast_posture` through `_search_ledger(...)`, `_design_record(...)`,
  `_deterministic_replay_key(...)`, `_cluster_interfaces(...)`,
  `_handoff_records(...)`, and `project_s2_design_search(...)`.
- add compact `SearchLedger` fields such as `forecast_support_refs`,
  `forecast_calibration_record_refs`, `forecast_posture_refs`,
  `forecast_authority_status`, and `forecast_authority_boundary`; avoid adding
  every S10 source ref to `DesignRecordV0.ledger_refs`.
- give new `SearchLedger` forecast fields backward-compatible defaults:
  `forecast_support_refs`, `forecast_calibration_record_refs`, and
  `forecast_posture_refs` use empty default lists,
  `forecast_authority_status` defaults to `"not_applicable"`, and
  `forecast_authority_boundary` defaults to `None`.
- `_deterministic_replay_key(...)` must omit S10 fields when
  `forecast_posture is None`, so legacy no-S10 S2 runs keep their exact replay
  key; include S10 posture refs only when a posture is injected.
- copy `Layer2S10ForecastPostureInput.authority_boundary` into S2
  ledger/projection payloads as `forecast_authority_boundary`; keep
  `authority_boundary` as the posture DTO field name so it matches the existing
  S5/S6/S7/S8 posture pattern.
- add S10 cluster interface/handoff rows that publish/consume
  `Layer2S10ForecastPostureInput` without minting recommendation authority.
- add S10 projection context for PUBLIC/REVIEWER/EXPERT/MACHINE using the
  existing `project_s2_design_search(...)` audience pattern.
- add a lightweight S10 branch to the W12.D non-UA S2 `not_applicable` summary so
  all 13 cases can carry forecast refs without forcing full S2 search for every
  corpus row.
- keep existing `forecast_support_label` behavior for S5 compatibility.
- do not import `polisyos.runtime.quality.design_axes.outcome_prediction`.
- public projection should show forecast tier and limitations.
- expert/machine projection should show calibration refs, uncertainty refs,
  S5/S6/S8 source refs, and authority boundary.

- [ ] **Step 3: Extend projection semantics**

Modify `src/polisyos/runtime/quality/projection_semantics.py`.

Add a narrow verifier entrypoint:

- `verify_s10_forecast_projection_consumer_contract(...)`

It should reuse existing PDC projection consumer checks where possible and add
S10-specific issue codes:

- `s10_missing_design_graph_or_prediction_context`
- `s10_simulation_only_laundered_as_evidence`
- `s10_equilibrium_contested_single_forecast`
- `s10_uncalibrated_observable_promotion`
- `s10_observed_outcome_without_credible_evaluation`
- `s10_validated_model_missing_source_or_method_validity`
- `s10_missing_value_provenance`
- `s10_scalar_welfare_hides_pareto_tradeoff`
- `s10_hidden_uncertainty_interval`
- `s10_prediction_authority_laundering`

- [ ] **Step 4: Extend public export**

Modify `src/polisyos/runtime/quality/public_export.py`.

Rules:

- public export may include `forecast_tier`,
  `observable_subset_calibration_status`, `uncertainty_interval_refs`, and
  `limitations`.
- public export must not include production recommendation or claim-authority
  language derived from S10.
- machine export requires design graph/context refs, source refs, method validity
  refs, calibration/evaluation refs, rule version, and authority boundary when
  S10 fields are present.

- [ ] **Step 5: Run Task 3 tests**

```bash
uv run pytest \
  tests/unit/pdc/test_layer2_readiness_contracts.py \
  tests/unit/pdc/test_layer2_s2_design_search.py \
  tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py \
  tests/unit/runtime/quality/test_public_export.py \
  -q
uv run ruff check src/polisyos/pdc/__init__.py \
  src/polisyos/pdc/_impl/layer2_design_search.py \
  src/polisyos/runtime/quality/projection_semantics.py \
  src/polisyos/runtime/quality/public_export.py
```

Expected green output:

- pytest exits `0`.
- ruff prints `All checks passed!`.

- [ ] **Step 6: Commit Task 3**

```bash
git add src/polisyos/pdc/__init__.py \
  src/polisyos/pdc/_impl/layer2_design_search.py \
  src/polisyos/runtime/quality/projection_semantics.py \
  src/polisyos/runtime/quality/public_export.py \
  tests/unit/pdc/test_layer2_readiness_contracts.py \
  tests/unit/pdc/test_layer2_s2_design_search.py \
  tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py \
  tests/unit/runtime/quality/test_public_export.py
git commit -m "feat: wire layer2 s10 forecast posture into projections" \
  -m "Co-authored-by: Cursor <cursoragent@cursor.com>"
```

## Task 4: Canonical Corpus Route Wiring - 13-Case S10 Coverage

Intent: every W12.D corpus case must carry an S10 forecast-support block while
preserving S5/S6/S8 boundaries.

- [ ] **Step 1: Add S10 fixtures**

Create `tests/fixtures/layer2/s10/s10_outcome_prediction_case_signals.json`.

Each of the 13 rows must include:

- `case_id`
- `forecast_support_input_ref`
- `source_design_record_ref`
- `design_graph_ref`
- `prediction_context_ref`
- `policy_context_ref`
- `candidate_design_ref`
- `baseline_design_ref`
- `alternative_design_refs`
- `prediction_horizon_ref`
- `target_outcome_refs`
- `jurisdiction_scope_ref`
- `s5_forecast_support_ref`
- `s5_base_origin`
- `s5_claim_scope`
- `s5_support_label`
- `s6_firewall_status_refs`
- `s6_limitation_refs`
- `s8_value_choice_provenance_ref`
- `s8_value_tradeoff_disclosure_ref`
- `source_contract_ref`
- `method_validity_ref`
- `source_lineage_refs`
- `method_lineage_refs`
- `sensitivity_analysis_ref`
- `dynamic_equilibrium_check_ref`
- `equilibrium_caveat_refs`
- `strategic_response_caveat_refs`
- `outcome_distribution_refs`
- `welfare_comparison_ref`
- `observable_subset_ref`
- `backtestable_observable`
- `historical_implementation_ref`
- `evaluation_design_ref`
- `credible_evaluation_evidence_ref`
- `counterfactual_credibility`
- `forecast_tier`
- `forecast_authority_disposition_reason`
- `method_family`
- `uncertainty_interval_refs`
- `calibration_record_ref`
- `calibration_status`
- `calibration_threshold_ref`
- `calibration_floor_passed`
- `calibration_denominator`
- `calibration_numerator`
- `non_observable_downgrade_reason`
- `limitation_refs`
- `abstention_refs`
- `expected_authority_boundary`

Create `tests/fixtures/layer2/s10/s10_outcome_prediction_expert_labels.json`.

Coverage labels must include:

- `observable_subset_calibrated`
- `non_observable_honestly_downgraded`
- `equilibrium_contested_blocked`
- `simulation_only_advisory`
- `transported_estimate_limited`
- `historical_prior_context_only`
- `s5_support_scope_preserved`
- `s6_firewall_cap_preserved`
- `s8_value_provenance_preserved`
- `weakest_boundary_inherited`
- `uncertainty_interval_visible`
- `welfare_comparison_value_grounded`

- [ ] **Step 2: Add negative-control fixtures**

Create:

- `tests/fixtures/layer2/s10/equilibrium_contested_single_forecast_probe.json`
- `tests/fixtures/layer2/s10/simulation_only_evidence_laundering_probe.json`
- `tests/fixtures/layer2/s10/uncalibrated_observable_promotion_probe.json`
- `tests/fixtures/layer2/s10/welfare_without_value_provenance_probe.json`
- `tests/fixtures/layer2/s10/fail_closed_axis_prediction_promotion_probe.json`
- `tests/fixtures/layer2/s10/regime_forecast_tier_laundering_probe.json`
- `tests/fixtures/layer2/s10/transported_estimate_without_limitation_probe.json`
- `tests/fixtures/layer2/s10/hidden_uncertainty_interval_probe.json`
- `tests/fixtures/layer2/s10/non_observable_claim_as_calibrated_probe.json`
- `tests/fixtures/layer2/s10/production_authority_from_forecast_probe.json`
- `tests/fixtures/layer2/s10/missing_design_graph_context_probe.json`
- `tests/fixtures/layer2/s10/observed_outcome_without_credible_evaluation_probe.json`
- `tests/fixtures/layer2/s10/validated_local_model_without_method_validity_probe.json`
- `tests/fixtures/layer2/s10/scalar_welfare_hides_pareto_tradeoff_probe.json`
- `tests/fixtures/layer2/s10/weakest_boundary_ignored_probe.json`

Every probe must include:

- `case_id`
- `failure_pattern`
- `expected_disposition`
- `expected_false_clear: false`
- exact S5/S6/S8/forecast fields that trigger the block.

- [ ] **Step 3: Extend W12.D runner**

Modify `tools/quality/validation/run_universal_outcome_corpus.py`.

Add:

- `S10_CASE_SIGNALS_PATH`
- `S10_EXPERT_LABELS_PATH`
- `S10_NEGATIVE_CONTROL_PROBE_PATHS`
- `S10_MAY_NOT_USE_FOR`
- `_s10_outcome_prediction_case_block(...)`
- `_s10_outcome_prediction_summary(...)`
- `_s10_negative_control_probe_results(...)`

Insertion point:

- build `s10_outcome_prediction` after `s8_value_choice` and before returning
  the case result using this order:
  `S4 -> S5 -> S6 -> S7 -> S8 -> S10 -> S2(+forecast_posture) -> S9`.
- consume already-built `s5_coupling_composition`,
  `s6_blind_spot_firewalls`, and `s8_value_choice`, plus the case-level
  `design_graph_ref` and `prediction_context_ref`.
- compute S10 posture before S2; resolve `source_design_record_ref` in the final
  S10 case block after S2 records the injected posture. Do not rerun S10 just to
  fill that ref.
- preserve the current W12.D workload shape: full S2 loop remains scoped to
  `ua-msme-affordable-loans-2022`; non-UA cases get S10 corpus blocks plus
  lightweight S2 forecast-posture refs.
- do not rerun S5, S6, or S8 from inside S10.
- add top-level `"s10_outcome_prediction"` to each case and
  `"s10_outcome_prediction_summary"` to corpus output.

Each case block must include:

- `schema_version = "policyos.policy_design_case.layer2_s10_outcome_prediction.v1"`
- `forecast_support_ref`
- `forecast_calibration_record_ref`
- `forecast_tier`
- `forecast_authority_disposition_reason`
- `design_graph_ref`
- `prediction_context_ref`
- `policy_context_ref`
- `candidate_design_ref`
- `baseline_design_ref`
- `alternative_design_refs`
- `s5_forecast_support_ref`
- `s6_firewall_status_refs`
- `s8_value_choice_provenance_ref`
- `source_contract_ref`
- `method_validity_ref`
- `credible_evaluation_evidence_ref`
- `dynamic_equilibrium_check_ref`
- `sensitivity_analysis_ref`
- `welfare_comparison_ref`
- `observable_subset_ref`
- `calibration_status`
- `calibration_threshold_ref`
- `calibration_floor_passed`
- `calibration_denominator`
- `calibration_numerator`
- `calibration_pass_rate`
- `uncertainty_interval_refs`
- `non_observable_downgrade_reason`
- `authority_boundary`
- `may_not_use_for`
- `canonical_outcome_effect = "forecast_support_only_not_outcome_authority"`

- [ ] **Step 4: Run Task 4 tests**

```bash
uv run pytest tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py -q
uv run ruff check tools/quality/validation/run_universal_outcome_corpus.py
python3 -m json.tool tests/fixtures/layer2/s10/s10_outcome_prediction_case_signals.json >/dev/null
python3 -m json.tool tests/fixtures/layer2/s10/s10_outcome_prediction_expert_labels.json >/dev/null
for f in tests/fixtures/layer2/s10/*_probe.json; do python3 -m json.tool "$f" >/dev/null || exit 1; done
```

Expected green output:

- pytest exits `0`.
- ruff prints `All checks passed!`.
- JSON validation exits `0`.

- [ ] **Step 5: Commit Task 4**

```bash
git add tools/quality/validation/run_universal_outcome_corpus.py \
  tests/fixtures/layer2/s10 \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py
git commit -m "feat: classify layer2 s10 forecast support coverage" \
  -m "Co-authored-by: Cursor <cursoragent@cursor.com>"
```

## Task 5: S10 Manifest, Readiness Validator, Traceability, And Inventory

Intent: register S10 as a governed Layer 2 layer with calibration floor coverage
without claiming S11 calibration or any remaining open cell.

- [ ] **Step 1: Add S10 manifest**

Create `architecture/policy_design_case/layer2_s10_outcome_prediction_manifest.json`.

Required fields:

- `schema_version = "policyos.policy_design_case.layer2_s10_outcome_prediction_manifest.v1"`
- `status = "active"`
- `owner = "team-research"`
- `slice = "S10"`
- `depends_on = ["S5", "S6", "S8"]`
- `cells_closed = []`
- `layer_cells_advanced = ["outcome_prediction_welfare_comparison"]`
- `expected_current_open_cell_count = 3`
- `floor_id = "s10_calibration"`
- `floor_metric = "observable_subset_calibration"`
- `required_artifacts = ["ForecastSupport", "ForecastCalibrationRecord"]`
- `case_count = 13`
- `observable_subset_case_count >= 4`
- `observable_subset_calibration_denominator >= 4`
- `observable_subset_calibration_numerator == observable_subset_calibration_denominator`
- `observable_subset_calibration_status = "pass"`
- `observable_subset_calibration_floor_passed = true`
- `observable_subset_calibration_threshold_ref` present
- `observable_subset_calibration_pass_rate` meets the governed threshold; the
  seed fixture may be perfect, but perfect prediction is not the contract.
- `non_observable_downgrade_count >= 1`
- `equilibrium_contested_single_forecast_block_count >= 1`
- `simulation_only_evidence_block_count >= 1`
- `weakest_boundary_inheritance_count = 13`
- all S10 false-clear count fields set to `0`
- `canonical_route = "tools/quality/validation/run_universal_outcome_corpus.py"`
- `validator = "tools/quality/validation/check_policy_design_case_layer2_readiness.py"`
- `authority_scope` limited to forecast-support tiering, observable-subset
  calibration, value-grounded welfare comparison, and advisory/routing
  uncertainty.
- `may_not_use_for` denying production, recommendation, rollout, publication,
  claim, closeout, approval, scorecard, preference learning, S11, S12, S13, and
  S14 authority.

False-clear fields must include:

- `equilibrium_contested_single_forecast_false_clear_count`
- `simulation_only_evidence_laundering_false_clear_count`
- `uncalibrated_observable_promotion_false_clear_count`
- `welfare_without_value_provenance_false_clear_count`
- `fail_closed_axis_prediction_promotion_false_clear_count`
- `regime_forecast_tier_laundering_false_clear_count`
- `transported_estimate_without_limitation_false_clear_count`
- `hidden_uncertainty_interval_false_clear_count`
- `non_observable_claim_as_calibrated_false_clear_count`
- `production_authority_from_forecast_false_clear_count`
- `missing_design_graph_context_false_clear_count`
- `observed_outcome_without_credible_evaluation_false_clear_count`
- `validated_local_model_without_method_validity_false_clear_count`
- `scalar_welfare_hides_pareto_tradeoff_false_clear_count`
- `weakest_boundary_ignored_false_clear_count`

- [ ] **Step 2: Update artifact traceability and inventory**

Modify `architecture/policy_design_case/layer2_artifact_traceability.toml`:

- set S10 `ForecastSupport` maturity to `implemented`.
- set S10 `ForecastCalibrationRecord` maturity to `implemented`.
- leave S11/S12/S13/S14 artifact rows as `planned`.

Modify `architecture/policy_design_case/inventory.json`.

Add `layer2_s10_outcome_prediction_manifest` with:

- `kind = "layer2_s10_outcome_prediction_manifest"`
- schema version matching the manifest.
- `capability_reality_label = "implemented"`
- authority scope and deny list matching the manifest.
- validator and canonical route paths.

- [ ] **Step 3: Extend readiness validator**

Modify `tools/quality/validation/check_policy_design_case_layer2_readiness.py`.

Add near S9 constants:

- `DEFAULT_S10_OUTCOME_PREDICTION_MANIFEST_PATH`
- `S10_REQUIRED_ARTIFACTS`
- `S10_REQUIRED_AUTHORITY_SCOPE`
- `S10_REQUIRED_DENY`
- `S10_FALSE_CLEAR_FIELDS`
- `S10_INVENTORY_ID = "layer2_s10_outcome_prediction_manifest"`

Wire:

- `payloads["s10_outcome_prediction"]` in `load_layer2_readiness_payloads(...)`.
- `_validate_s10_outcome_prediction(...)` after `_validate_s9_projection_lowering(...)`.
- flat summary fields such as `summary["s10_observable_subset_calibration_pass_rate"]`.
- flat summary fields for `summary["s10_observable_subset_calibration_status"]`,
  `summary["s10_observable_subset_calibration_floor_passed"]`, and
  `summary["s10_observable_subset_calibration_threshold_ref"]`.
- nested concise names such as
  `summary["s10_false_clear_counts"]["simulation_only_evidence_laundering"]`.
- inventory artifact count from `17` to `18` after S10 registration.
- replace the current S8 and S9 validator hard gates that require inventory count
  `17` with post-S10-aware assertions: S8/S9 manifest semantics stay unchanged,
  while the governed Layer 2 inventory count is `18` once S10 is registered.
- update the S9 future-slice maturity guard so S10 can be implemented by S10;
  after this task it must continue to block only S11/S12/S13/S14 maturity claims.

Validation must assert:

- S10 manifest exists and is registered in inventory.
- S10 case count is `13`.
- observable-subset calibration denominator is at least `4`.
- numerator equals denominator.
- calibration status is `pass`, floor-passed is `true`, threshold ref is present,
  and pass rate meets that threshold.
- non-observable downgrade count is at least `1`.
- equilibrium-contested and simulation-only block counts are at least `1`.
- weakest-boundary inheritance count is `13`.
- all S10 false-clear counts are `0`.
- expected current open cell count remains `3`.
- `cells_closed == []`.
- remaining open cells are exactly `DESIGNER_ITSELF.envelope_growth`,
  `KNOWLEDGE.calibration`, and `KNOWLEDGE.ir_proof_carrying_analytics`.
- governed Layer 2 inventory artifact count is `18`.
- no S11/S12/S13/S14 maturity is marked implemented by S10.

- [ ] **Step 4: Extend repo-quality tests**

Modify:

- `tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s6_blind_spot_firewalls.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s7_delegation.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s8_value_choice.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s9_projection_lowering.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s10_outcome_prediction.py`

Update previous S6/S7/S8/S9 tests that asserted global inventory count `17` so
they assert their own manifest presence and unchanged slice semantics. Use a
nondecreasing inventory lower bound such as
`summary["inventory_artifact_count"] >= 18` in those legacy per-slice tests
instead of an exact live count. Keep the exact post-S10 count
`summary["inventory_artifact_count"] == 18` in the central readiness/S10 closeout
coverage only.

Assertions must include:

- `summary["s10_case_count"] == 13`
- `summary["s10_observable_subset_calibration_denominator"] >= 4`
- `summary["s10_observable_subset_calibration_numerator"] == summary["s10_observable_subset_calibration_denominator"]`
- `summary["s10_observable_subset_calibration_status"] == "pass"`
- `summary["s10_observable_subset_calibration_floor_passed"] is True`
- `summary["s10_observable_subset_calibration_threshold_ref"]`
- `summary["s10_non_observable_downgrade_count"] >= 1`
- `summary["s10_equilibrium_contested_single_forecast_block_count"] >= 1`
- `summary["s10_simulation_only_evidence_block_count"] >= 1`
- `summary["s10_weakest_boundary_inheritance_count"] == 13`
- `summary["s10_false_clear_counts"]["simulation_only_evidence_laundering"] == 0`
- `summary["s10_false_clear_counts"]["production_authority_from_forecast"] == 0`
- `summary["s10_false_clear_counts"]["observed_outcome_without_credible_evaluation"] == 0`
- `summary["s10_false_clear_counts"]["scalar_welfare_hides_pareto_tradeoff"] == 0`
- `summary["s10_false_clear_counts"]["weakest_boundary_ignored"] == 0`
- `summary["s10_expected_current_open_cell_count"] == 3`
- `summary["current_open_cell_count"] == 3`
- central readiness/S10 closeout test:
  `summary["inventory_artifact_count"] == 18`
- legacy S6/S7/S8/S9 tests:
  `summary["inventory_artifact_count"] >= 18`

- [ ] **Step 5: Run Task 5 validators and tests**

```bash
uv run python tools/quality/validation/check_policy_design_case_layer2_readiness.py
uv run python tools/quality/validation/check_policy_design_case_cluster_ownership_map.py
uv run pytest \
  tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s6_blind_spot_firewalls.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s7_delegation.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s8_value_choice.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s9_projection_lowering.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s10_outcome_prediction.py \
  -q
```

Expected output:

- both validator commands print `"status": "pass"` and `"issues": []`.
- pytest exits `0`.

- [ ] **Step 6: Commit Task 5**

```bash
git add architecture/policy_design_case/layer2_s10_outcome_prediction_manifest.json \
  architecture/policy_design_case/layer2_artifact_traceability.toml \
  architecture/policy_design_case/inventory.json \
  tools/quality/validation/check_policy_design_case_layer2_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s6_blind_spot_firewalls.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s7_delegation.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s8_value_choice.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s9_projection_lowering.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s10_outcome_prediction.py
git commit -m "chore: register layer2 s10 forecast support maturity" \
  -m "Co-authored-by: Cursor <cursoragent@cursor.com>"
```

## Task 6: Repo-Quality Tests, Snapshots, And Burn-Down Confirmation

Intent: prove S10 is complete without weakening Layer 2 burn-down truth.

- [ ] **Step 1: Run focused S10 suite**

```bash
uv run pytest \
  tests/unit/runtime/quality/test_layer2_s10_outcome_prediction.py \
  tests/unit/pdc/test_layer2_readiness_contracts.py \
  tests/unit/pdc/test_layer2_s2_design_search.py \
  tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py \
  tests/unit/runtime/quality/test_public_export.py \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s6_blind_spot_firewalls.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s7_delegation.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s8_value_choice.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s9_projection_lowering.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s10_outcome_prediction.py \
  -q
```

Expected output:

```text
... passed
```

- [ ] **Step 2: Run architecture/readiness validators**

```bash
uv run python tools/quality/validation/check_policy_design_case_cluster_ownership_map.py
uv run python tools/quality/validation/check_policy_design_case_layer2_readiness.py
uv run polisyos-tools architecture guardrails check
uv run --extra runtime --extra ml polisyos-tools runtime check-runtime-api-contract
```

Expected output:

- cluster map validator: `"status": "pass"`, `"issues": []`, open cell count
  `3`.
- Layer 2 readiness validator: `"status": "pass"`, `"issues": []`,
  S10 metrics present, open cell count `3`, inventory count `18`.
- architecture guardrails: pass.
- runtime API contract: pass.

- [ ] **Step 3: Confirm no forbidden maturity claims**

Run:

```bash
rg -n "s11_calibration|s11_axis_calibration|s12_envelope_growth|s13_accountability|s14_universality|production_authority|calibrated_equilibrium_prediction|rich_simulation|portfolio_optimization|preference_learning|claim_authority|closeout_authority" \
  architecture/policy_design_case \
  src/polisyos \
  tests/repo_quality/tools/test_policy_design_case_layer2_s10_outcome_prediction.py
```

Expected result:

- hits are allowed only in `may_not_use_for`, deny lists, negative assertions,
  future floor rows, planned future-slice rows, or unrelated production-quality
  tests.
- no S10 manifest or readiness summary marks S11/S12/S13/S14 or production
  capabilities implemented.

- [ ] **Step 4: Heavy suite policy**

Do not run full backend pytest or benchmark lanes locally if the machine is
thermally constrained. Local closeout evidence for S10 is the focused suite plus
validators above; full backend parity may be recorded as separate CI/cloud
evidence.

- [ ] **Step 5: Commit Task 6 if files changed**

If Task 6 only verifies and produces no target-file diff, do not create an empty
commit. If verification required code/test fixes, commit with:

```bash
git add src/polisyos/runtime/quality/design_axes/outcome_prediction.py \
  src/polisyos/runtime/quality/__init__.py \
  src/polisyos/pdc/__init__.py \
  src/polisyos/pdc/_impl/layer2_design_search.py \
  src/polisyos/runtime/quality/projection_semantics.py \
  src/polisyos/runtime/quality/public_export.py \
  tools/quality/validation/run_universal_outcome_corpus.py \
  tools/quality/validation/check_policy_design_case_layer2_readiness.py \
  architecture/policy_design_case/layer2_s10_outcome_prediction_manifest.json \
  architecture/policy_design_case/layer2_artifact_traceability.toml \
  architecture/policy_design_case/inventory.json \
  tests/unit/runtime/quality/test_layer2_s10_outcome_prediction.py \
  tests/unit/pdc/test_layer2_readiness_contracts.py \
  tests/unit/pdc/test_layer2_s2_design_search.py \
  tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py \
  tests/unit/runtime/quality/test_public_export.py \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s6_blind_spot_firewalls.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s7_delegation.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s8_value_choice.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s9_projection_lowering.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s10_outcome_prediction.py \
  tests/fixtures/layer2/s10
git commit -m "chore: verify layer2 s10 forecast support progress" \
  -m "Co-authored-by: Cursor <cursoragent@cursor.com>"
```

## Task 7: Full S10 Verification Done When

S10 is complete only when all statements below are true:

- `ForecastSupport` and `ForecastCalibrationRecord` are strict, replayable, and
  exported from `polisyos.runtime.quality`.
- `Layer2S10ForecastPostureInput` is strict and exported from `polisyos.pdc`.
- `ForecastSupport` records `DesignGraph + context` refs: design graph,
  prediction context, candidate, baseline, alternatives, horizon, target
  outcomes, and jurisdiction/scope.
- `forecast_tier` is a derived authority disposition over S5
  `base_origin x claim_scope x support_label`, not a second source vocabulary.
- S10 consumes S5 `ForecastSupportScope`, S6 firewall outputs, and S8 value
  provenance without rerunning those producers.
- B-side PDC search consumes injected S10 posture only and does not import the
  S10 runtime-quality producer.
- Forecast tier is independent of epistemic-regime label; regime alone cannot
  promote a forecast.
- `validated_local_model` support requires source contract, method validity,
  source/method lineage, sensitivity, and calibration refs.
- system-effect forecasts require dynamic/equilibrium checks or explicit caveat
  refs before governed support is allowed.
- `equilibrium_contested` refuses a single system-effect forecast.
- `simulation_only` projections are advisory/routing only and cannot satisfy
  evidence authority.
- observable-subset calibration records explicit time roles:
  prediction time, observation time, policy effective time, data valid time,
  and calibration window.
- observable-subset calibration requires credible evaluation evidence and
  counterfactual-credibility refs where observed outcomes are used.
- calibration is judged by governed threshold/floor refs; perfect pass rate is
  allowed as fixture evidence but not required as the universal semantic rule.
- non-observable cases are honestly downgraded and counted separately.
- welfare comparisons cite S8 value-choice provenance and tradeoff disclosures.
- scalar welfare summaries do not hide Pareto tradeoffs, social-weight
  provenance, or multi-principal conflict.
- recommendation/projection consumers inherit the weakest boundary among legal,
  data, method, participation, epistemic regime, coupling, prediction,
  welfare/value-choice, state-capacity, reversibility/stakes, and
  strategic-response assumptions.
- all 13 corpus cases contain S10 blocks.
- negative-control false-clear counts are zero.
- `observable_subset_calibration` floor is recorded from the governed floor
  table with numerator/denominator/pass rate.
- S10 manifest is registered in inventory; governed Layer 2 inventory artifact
  count is `18`.
- cluster-map open cell count remains `3`.
- remaining open cells are exactly `DESIGNER_ITSELF.envelope_growth`,
  `KNOWLEDGE.calibration`, and `KNOWLEDGE.ir_proof_carrying_analytics`.
- no S11 calibration/proof-carrying analytics, S12 envelope growth, S13
  accountability, production authority, calibrated equilibrium prediction, rich
  simulation, portfolio optimization, preference learning, or S14 universality
  cell is marked implemented.

## Commit Guidance

Use one logical commit per task:

```text
test: add layer2 s10 prediction red tests
feat: add layer2 s10 forecast support contracts
feat: wire layer2 s10 forecast posture into projections
feat: classify layer2 s10 forecast support coverage
chore: register layer2 s10 forecast support maturity
chore: verify layer2 s10 forecast support progress
```

End commit messages with the repo's standard co-author trailer:

```text
Co-authored-by: Cursor <cursoragent@cursor.com>
```

Never use `git add .` for this plan. If `git status --short` shows unrelated
user changes, stage only the S10 paths listed in the relevant task or use
`git add -p`.
