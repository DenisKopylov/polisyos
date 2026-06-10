---
title: PolicyOS Layer 2 S11 Rich Blind-Spot Models And Knowledge Producers Implementation Plan
status: active
owner: team-research
created: 2026-06-02
last_verified: null
stability: draft
revision_note: drafted 2026-06-02 after S10 verification; hardened after plan review to preserve S10 compatibility, per-axis floor coverage, reviewer/public surfaces, and calibration consumers
slice: S11
slice_label: rich_blind_spot_models_knowledge_producers
roadmap: ../POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER2_IMPLEMENTATION_PLAN.md
source_design_doc: ../../../system-design-decisions/universal-policy-design-target-architecture-and-gap.md
cluster_ownership_map: ../../../../architecture/policy_design_case/cluster_ownership_map.toml
slice_cell_matrix: ../../../../architecture/policy_design_case/layer2_slice_cell_matrix.toml
floor_governance: ../../../../architecture/policy_design_case/layer2_floor_governance.toml
artifact_traceability: ../../../../architecture/policy_design_case/layer2_artifact_traceability.toml
failure_patterns: ../../../reference/policy-design-case-failure-patterns.md
depends_on:
  - S6
  - S10
cells_closed:
  - KNOWLEDGE.calibration
  - KNOWLEDGE.ir_proof_carrying_analytics
maturity_transitions:
  - OTHER_AGENTS.strategic_response: fail_closed -> predictive
  - ACTOR.state_capacity_feasibility: fail_closed -> predictive
  - SYSTEM.measurability: fail_closed -> predictive
  - SYSTEM.subject_granularity: fail_closed -> predictive
layer_cells_advanced:
  - CROSS_CUTTING.method_infrastructure
expected_current_open_cell_count: 1
floor_id: s11_axis_calibration
floor_metric: per_axis_predictive_calibration
---

# Layer 2 S11 - Rich Blind-Spot Models And Knowledge Producers

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

Read this whole file before editing. Execute tasks in order, keep commits
task-sized, and preserve the repo rule that rich models can relax S6 only where
per-axis calibration and proof-carrying evidence pass. S11 closes
`KNOWLEDGE.calibration` and `KNOWLEDGE.ir_proof_carrying_analytics`, advances
already-implemented `CROSS_CUTTING.method_infrastructure`, and upgrades only the
four S11 maturity-transition axes named by
`architecture/policy_design_case/layer2_slice_cell_matrix.toml`. It does **not**
mark `ACTOR.mandate_legitimacy` predictive unless that matrix gains an S11
maturity-transition row, and it does not mark S12 envelope growth, S13
accountability, production authority, calibrated equilibrium prediction, rich
simulation authority, portfolio optimization, preference learning, or S14
universality as implemented.

Matrix precedence rule: roadmap shorthand that "S6 cells -> maturity=predictive"
is interpreted through the committed slice-cell matrix. Today that means four
predictive-transition rows, not the S6 mandate/legitimacy cell.

## Goal

S11 turns S6 fail-closed blind-spot records and S10 forecast-support posture
into governed predictive-axis upgrade records where existing calibration,
method-validity, and proof-carrying analytics support relaxation. Every axis
that cannot pass the governed per-axis calibration floor remains at the S6
fail-closed limit, with residual limitations surfaced to REVIEWER, EXPERT, and
MACHINE audiences, plus public-visible limitation summaries where S11 constrains
a public-facing design status.

The closure contract is the roadmap S11 contract:

- producer: predictive axis models plus calibration/proof verifier over S6 and
  S10 inputs.
- persisted artifact: upgraded axis records with `maturity=predictive` only
  where calibration and proof-carrying evidence pass; reverted rows are counted
  separately.
- bridge/consumer: constraint store, S10 prediction posture, claim registry, and
  design-comparison consumers read S11 posture without rerunning producers.
- surface: EXPERT/MACHINE projections expose upgraded confidence, proof refs,
  calibration status, and residual limitations.
- semantic test: a model relaxes the fail-closed limit only where calibration
  passes and proof-carrying analytics bind to the claim/comparison.
- negative control: a model exceeding its evidence, using stale calibration, or
  citing unbound IR analytics reverts to the S6 fail-closed limit.
- floor: `per_axis_predictive_calibration` is recorded from the governed floor
  table; negative-control false-clear counts remain zero.

## Architecture

S11 is a runtime-quality predictive knowledge layer over existing S6, S10,
calibration, IR, and Foundry method substrates:

- `src/polisyos/runtime/quality/layer2_blind_spot_firewalls.py` already owns S6
  fail-closed axes and firewall records. S11 consumes S6 refs and dispositions;
  it does not rebuild S6 producers and does not weaken P18/P19/P21/P24 floors.
- `src/polisyos/runtime/quality/layer2_outcome_prediction.py` already owns S10
  `ForecastSupport` and `ForecastCalibrationRecord`. S11 consumes S10 forecast
  support refs and calibration posture; it does not reclassify S10 forecast
  tiers or claim recommendation authority.
- `src/polisyos/runtime/quality/calibration_ledger.py` already owns longitudinal
  calibration primitives. S11 wires those primitives into the design-loop gate
  for per-axis predictive relaxation. Historical priors can inform future
  acquisition or model scrutiny, but cannot be used as current-run evidence when
  scope, time window, or policy context do not match.
- `src/polisyos/runtime/quality/ir_analytics_bridge.py` already builds a
  claim-bound bridge for proof-carrying IR analytics. S11 wraps that bridge into
  strict `ProofCarryingAnalyticsRecord` artifacts, then feeds claim and
  design-comparison consumers through refs.
- `src/polisyos/foundry/methods/`,
  `src/polisyos/foundry/calibration/`, `src/polisyos/foundry/validation/`, and
  `src/polisyos/foundry/uncertainty/` are method substrates. S11 records
  governed method authority and calibration results; it does not create a rich
  simulation engine or a portfolio optimizer.
- `src/polisyos/pdc/_impl/layer2_design_search.py` already has the S10 injected
  posture pattern. S11 must add `Layer2S11PredictivePostureInput` and pass it as
  data. PDC search must not import
  `polisyos.runtime.quality.layer2_predictive_knowledge` or call S11 producer
  helpers directly.

Boundary rule: S11 can produce predictive knowledge artifacts and PDC posture.
Downstream consumers may inherit S11 limitations, but S11 does not create
production, publication, approval, rollout, or closeout authority.

## Scope

In scope:

- strict Pydantic runtime-quality contracts exported from
  `polisyos.runtime.quality`.
- `ProofCarryingAnalyticsRecord` as the S11 traceability artifact already named
  by `layer2_artifact_traceability.toml`.
- S11 calibration-upgrade artifacts:
  `PredictiveAxisCalibrationRecord`, `PredictiveAxisUpgradeRecord`, and
  `S11PredictiveKnowledgeIntegrityReport`.
- per-axis predictive maturity transitions for exactly:
  `OTHER_AGENTS.strategic_response`,
  `ACTOR.state_capacity_feasibility`, `SYSTEM.measurability`, and
  `SYSTEM.subject_granularity`.
- S6 floor refs, S10 forecast refs, calibration-ledger refs, method-validity
  refs, source-contract refs, source/method lineage refs, sensitivity refs,
  proof/certificate refs, and residual limitation refs.
- claim-bound IR analytics bridge consumption by claim and design-comparison
  consumers.
- calibration consumer wiring into forecast-quality and epistemic-regime
  constraint rows, so absent, stale, or poor calibration changes downstream
  posture instead of remaining a local metric.
- axis-specific evidence rows for capacity feasibility and strategic response:
  capacity dimensions must cover administrative, fiscal, enforcement, delivery,
  coordination, and political-feasibility assumptions where claimed; strategic
  rows must name Goodhart, Lucas/performativity, capture, gaming, adaptation, or
  compliance-response channels where claimed.
- W12.D S11 blocks for all 13 universal corpus cases.
- negative controls for stale calibration, scope-mismatched historical priors,
  unbound analytics, negative certificates, missing method validity, missing S6
  floor refs, mandate predictive laundering, production authority laundering,
  rich simulation laundering, and weakest-boundary bypass.
- manifest, inventory, traceability, readiness validator, floor metric, and
  repo-quality coverage.

Out of scope:

- S12 envelope-growth economics, value-of-information allocation, bootstrap
  thermometers, or resource-policy optimization.
- S13 accountability, realized regret, deployment dossiers, divergence records,
  post-deploy learning proposals, or oversight-effectiveness closure.
- S14 universality battery closure or self-description authority.
- calibrated equilibrium prediction, rich simulation authority, portfolio
  optimization, preference learning, public rollout, production recommendation,
  approval, claim authority, scorecard authority, or runtime closeout authority.
- `ACTOR.mandate_legitimacy` predictive upgrade. S11 continues to consume S6
  mandate/legitimacy refs where value/proof authority needs them, but the
  current matrix does not authorize a predictive maturity transition for that
  cell.

## Pattern Pass

Open the failure register before implementation and before closeout:
`docs/reference/policy-design-case-failure-patterns.md`.

| Pattern | S11 risk | Closure move |
| --- | --- | --- |
| P01 contract-only capability | Calibration and IR bridge primitives exist, but current open-cell contracts say bridge, consumer, verification, surface, and semantic tests are missing. | Add strict artifacts, producer/verifier, corpus route, PDC posture, manifest, readiness checks, and negative semantic tests. |
| P02 thin orchestration | IR proof outputs and Foundry method/calibration seeds can coexist without claim/comparison consumers. | Route `ProofCarryingAnalyticsRecord` through claim-bound bridge refs and design-comparison posture. |
| P03 hidden internal richness | Predictive confidence, proof refs, or residual limitations may remain internal. | Surface S11 confidence, proof refs, calibration status, and residual limitation refs in REVIEWER/EXPERT/MACHINE projections; PUBLIC receives limitation text when S11 affects visible design status. |
| P04 status lattice gap | `predictive`, `fail_closed`, `stale`, `limited`, and `proof_blocked` can look like global authority statuses. | Keep maturity as a cell qualifier and map relaxation decisions to existing authority boundaries. |
| P05 authority dilution | Rich model output can be confused with recommendation, rollout, publication, or claim authority. | Every S11 artifact and posture carries `authoritative_for` and `may_not_use_for`; consumers inherit weakest boundary. |
| P07 replay gap | A predictive upgrade can be impossible to replay if calibration rules or proof refs are missing. | Persist rule/schema versions, floor refs, calibration-window refs, source/method lineage refs, and proof/certificate refs. |
| P08 time-role conflation | Historical calibration, prediction time, data-valid time, and policy effective time can collapse. | Add explicit time-role fields to per-axis calibration records and block mismatched windows. |
| P10 semantic adequacy gap | Constructor tests can pass while stale calibration or unbound analytics promote a model. | Start with semantic and negative-control tests, including false-clear counts. |
| P13 contract gravity | S11 could become a full modeling platform instead of a governed relaxation layer. | Reuse S6/S10/calibration/IR/Foundry substrates; S11 records authority envelope and upgrade decisions only. |
| P14 evidence inflation | Multiple method outputs can share data, assumptions, or lineage but be counted independently. | Require source/method lineage and effective independence or collapse refs before proof can raise confidence. |
| P15 LLM speculation laundering | LLM-discovered blind spots or model claims can be treated as proof. | Allow LLM rows only as candidate/diagnostic refs; deterministic producer or governed human refs must authorize relaxation. |
| P12 producer fragmentation | Foundry method infrastructure can be "advanced" cosmetically while S11 uses bespoke rows. | Require method infrastructure refs and consumer evidence; S11 may advance `CROSS_CUTTING.method_infrastructure` only through consumed Foundry method/calibration/validation artifacts, not by declaring the substrate closed again. |
| P18/P19/P21/P24 blind-spot laundering | Rich models can bypass S6 floors for measurability, aggregation, capacity, or strategic response. | Require the corresponding S6 floor record and revert to fail-closed when the floor is absent or limiting. |

Current missing capability labels before S11:

- `KNOWLEDGE.calibration`: `implemented_but_not_orchestrated` with
  `bridge_missing`, `consumer_missing`, `verification_missing`,
  `surface_missing`, and `semantic_test_missing`.
- `KNOWLEDGE.ir_proof_carrying_analytics`: `implemented_but_not_orchestrated`
  with the same missing chain labels.

Target correct pattern after S11:

- both cells are `implemented`;
- predictive S6 rows carry `maturity=predictive` only as a qualifier, not as a
  new ratchet state;
- remaining open cell count is exactly `1`, with only
  `DESIGNER_ITSELF.envelope_growth` still open.

## Code-Grounded Reality Check

Use these anchors before editing:

- S6 axis contracts and fail-closed records:
  `src/polisyos/runtime/quality/layer2_blind_spot_firewalls.py`.
- S10 forecast-support contracts:
  `src/polisyos/runtime/quality/layer2_outcome_prediction.py`.
- Calibration primitives:
  `src/polisyos/runtime/quality/calibration_ledger.py`.
- IR claim bridge:
  `src/polisyos/runtime/quality/ir_analytics_bridge.py`.
- S10 injected posture pattern:
  `src/polisyos/pdc/_impl/layer2_design_search.py`.
- Universal corpus route:
  `tools/quality/validation/run_universal_outcome_corpus.py`.
- S10 manifest/readiness tests:
  `tests/repo_quality/tools/test_policy_design_case_layer2_s10_outcome_prediction.py`.

The S11 matrix contains four maturity transitions:

```text
OTHER_AGENTS.strategic_response: fail_closed -> predictive
ACTOR.state_capacity_feasibility: fail_closed -> predictive
SYSTEM.measurability: fail_closed -> predictive
SYSTEM.subject_granularity: fail_closed -> predictive
```

The current matrix does not contain
`ACTOR.mandate_legitimacy: fail_closed -> predictive`. Treat that as an
intentional authority boundary.

Code-grounded reuse points:

- S10 already provides the strict runtime-quality pattern to copy:
  `S10_FALSE_CLEAR_FIELDS` is the false-clear source of truth,
  `ForecastSupportIntegrityReport` validates exact keys, and builder/verifier
  helpers keep authority-envelope rules close to the DTOs. S11 should mirror
  that shape with `S11_FALSE_CLEAR_FIELDS` and an integrity report validator
  instead of using a loose summary dict.
- S6 already emits the rows S11 needs to preserve: `axis_rows`,
  `bridge_consumer_rows`, `constraint_store_updates`,
  `c3_authority_dimension_rows`, `post_intervention_dgp_update_ref`, and
  `system_dynamics_handoff_required`. S11 overlays predictive maturity and
  proof/calibration refs on those records; it must not rebuild the S6 axis
  plumbing or discard S6 handoff signals.
- The IR analytics bridge already normalizes claim bindings, proof statuses,
  proof-composability statuses, negative certificate refs, independence refs,
  blockers, limitations, and claim-registry merge behavior. S11 should wrap
  that bridge in `ProofCarryingAnalyticsRecord` and feed claim/design-comparison
  consumers through refs, not create a second IR bridge vocabulary.
- The calibration ledger already forbids historical priors from satisfying
  current-run claim evidence. S11 may consume calibration-ledger and influence
  refs as context or future posture, but current predictive relaxation still
  needs per-axis current-run calibration, method-validity, scope/time-window,
  and proof checks.

Code-grounded workload risks:

- PDC posture wiring is manual today. `Layer2S2DesignSearchRun`,
  `SearchLedger`, `_constraint_store(...)`, `_search_ledger(...)`,
  `_design_record(...)`, `_cluster_interfaces(...)`, `_handoff_records(...)`,
  `_deterministic_replay_key(...)`, projection helpers, and CAS
  load/default tests all require explicit S11 additions.
- Current S10 projection exposes detailed refs to EXPERT/MACHINE but not the
  same depth to REVIEWER. S11 REVIEWER exposure is an intentional
  architecture-hardening step, not a free copy of the S10 pattern.
- The readiness validator's S10 branch currently treats live open cells and
  inventory count as post-S10 facts. Task 5 must preserve S10 manifest-local
  assertions while allowing post-S11 live readiness to become open-count `1`
  and governed Layer 2 inventory count `19`.
- S11 is the first cell-closing slice since S8, so the open-count snapshot tax
  returns across per-slice repo-quality tests. Per-slice tests must stop
  asserting exact live open-cell count `3`; exact live count belongs in the
  readiness/S11 gate. Cluster-map negative controls that currently mutate
  `KNOWLEDGE.calibration` must be repointed to the remaining open cell
  `DESIGNER_ITSELF.envelope_growth`.
- W12.D can import runtime-quality S11 producer helpers the same way S10 imports
  `build_forecast_support`, but PDC search cannot. Keep the corpus producer path
  and injected PDC posture path separated.

## File Map

Create:

- `src/polisyos/runtime/quality/layer2_predictive_knowledge.py`
- `tests/unit/runtime/quality/test_layer2_s11_predictive_knowledge.py`
- `tests/fixtures/layer2/s11/s11_predictive_knowledge_case_signals.json`
- `tests/fixtures/layer2/s11/s11_predictive_knowledge_expert_labels.json`
- `tests/fixtures/layer2/s11/negative_controls/stale_calibration_relaxation_probe.json`
- `tests/fixtures/layer2/s11/negative_controls/scope_mismatched_historical_prior_probe.json`
- `tests/fixtures/layer2/s11/negative_controls/unbound_ir_analytics_probe.json`
- `tests/fixtures/layer2/s11/negative_controls/negative_certificate_ignored_probe.json`
- `tests/fixtures/layer2/s11/negative_controls/missing_method_validity_probe.json`
- `tests/fixtures/layer2/s11/negative_controls/missing_s6_floor_ref_probe.json`
- `tests/fixtures/layer2/s11/negative_controls/mandate_axis_predictive_upgrade_probe.json`
- `tests/fixtures/layer2/s11/negative_controls/production_authority_from_predictive_upgrade_probe.json`
- `tests/fixtures/layer2/s11/negative_controls/rich_simulation_authority_laundering_probe.json`
- `tests/fixtures/layer2/s11/negative_controls/weakest_boundary_bypass_probe.json`
- `architecture/policy_design_case/layer2_s11_predictive_knowledge_manifest.json`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s11_predictive_knowledge.py`

Modify:

- `src/polisyos/runtime/quality/__init__.py`
- `src/polisyos/pdc/_impl/layer2_design_search.py`
- `src/polisyos/pdc/__init__.py`
- `src/polisyos/runtime/quality/layer2_epistemic_regime.py`
- `src/polisyos/runtime/quality/projection_semantics.py`
- `src/polisyos/runtime/quality/public_export.py`
- `tools/quality/validation/run_universal_outcome_corpus.py`
- `tools/quality/validation/check_policy_design_case_layer2_readiness.py`
- `architecture/policy_design_case/cluster_ownership_map.toml`
- `architecture/policy_design_case/layer2_artifact_traceability.toml`
- `architecture/policy_design_case/inventory.json`
- `tests/unit/pdc/test_layer2_s2_design_search.py`
- `tests/unit/runtime/quality/test_claim_registry.py`
- `tests/unit/runtime/quality/test_layer2_s4_epistemic_regime.py`
- `tests/unit/pdc/test_layer2_readiness_contracts.py`
- `tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py`
- `tests/unit/runtime/quality/test_public_export.py`
- `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`
- `tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s2_design_search.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s3_substrate_acquisition.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s4_epistemic_regime.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s5_coupling_composition.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s6_blind_spot_firewalls.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s7_delegation.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s8_value_choice.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s9_projection_lowering.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s10_outcome_prediction.py`

Do not modify `layer2_slice_cell_matrix.toml` unless implementation discovers
that the matrix contradicts the roadmap. The current S11 assignments and
maturity transitions are already present.

## S11 Contract Dictionary

Runtime constants:

- `LAYER2_S11_PREDICTIVE_KNOWLEDGE_SCHEMA_VERSION =
  "policyos.policy_design_case.layer2_s11_predictive_knowledge.v1"`
- `LAYER2_S11_PREDICTIVE_KNOWLEDGE_RULE_VERSION =
  "policyos.layer2.s11.predictive_knowledge.v1"`
- `S11_AXIS_CALIBRATION_FLOOR_ID = "s11_axis_calibration"`
- `S11_PREDICTIVE_AXES = ("strategic_response", "state_capacity_feasibility",
  "measurability", "subject_granularity")`
- `S11_FALSE_CLEAR_FIELDS = ("stale_calibration_relaxation",
  "scope_mismatched_historical_prior", "unbound_ir_analytics",
  "negative_certificate_ignored", "missing_method_validity",
  "missing_s6_floor_ref", "mandate_axis_predictive_upgrade",
  "production_authority_from_predictive_upgrade",
  "rich_simulation_authority_laundering", "weakest_boundary_bypass")`

Runtime models:

- `PredictiveAxisCalibrationRecord`
- `PredictiveAxisUpgradeRecord`
- `ProofCarryingAnalyticsRecord`
- `S11PredictiveKnowledgeIntegrityReport`

Runtime producer/verifier helpers:

- `build_predictive_axis_calibration_record(...)`
- `build_predictive_axis_upgrade_record(...)`
- `build_proof_carrying_analytics_record(...)`
- `build_s11_predictive_knowledge_posture(...)`
- `summarize_s11_predictive_knowledge_integrity(...)`
- `verify_s11_predictive_knowledge_authority_envelope(...)`

PDC posture model:

- `Layer2S11PredictivePostureInput`

Authority boundary:

- `authoritative_for` includes
  `per_axis_predictive_calibration`,
  `predictive_axis_maturity_upgrade`,
  `proof_carrying_analytics_validity`,
  `claim_bound_ir_analytics_bridge`,
  `s6_fail_closed_relaxation_decision`,
  `s10_prediction_constraint_input`, and
  `expert_machine_calibration_projection`.
- `may_not_use_for` includes `production_authority`,
  `production_recommendation`, `production_claim_authority`,
  `rollout_authority`, `publication_authority`, `claim_authority`,
  `closeout_authority`, `runtime_closeout_authority`, `approval_authority`,
  `scorecard_authority`, `calibrated_equilibrium_prediction`,
  `rich_simulation_authority`, `portfolio_optimization_authority`,
  `preference_learning_authority`, `s12_envelope_growth`,
  `s13_accountability_closure`, `s14_universality`,
  `mandate_legitimacy_predictive_upgrade`,
  `historical_prior_current_evidence`, and `llm_method_authority`.

## Task 1: Red-First S11 Semantic And Negative Tests

**Intent:** make the S11 capability fail for the right reasons before adding
contracts or wiring.

**Files:**

- Create: `tests/unit/runtime/quality/test_layer2_s11_predictive_knowledge.py`
- Modify: `tests/unit/pdc/test_layer2_readiness_contracts.py`
- Modify: `tests/unit/pdc/test_layer2_s2_design_search.py`
- Modify: `tests/unit/runtime/quality/test_claim_registry.py`
- Modify: `tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py`
- Modify: `tests/unit/runtime/quality/test_public_export.py`
- Modify: `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`
- Create: `tests/repo_quality/tools/test_policy_design_case_layer2_s11_predictive_knowledge.py`

- [ ] **Step 1: Add runtime semantic tests**

Add tests with these names:

- `test_predictive_axis_upgrade_requires_s6_floor_s10_forecast_and_calibration_refs`
- `test_axis_relaxation_reverts_fail_closed_when_calibration_fails_or_stale`
- `test_unbound_ir_analytics_does_not_raise_claim_or_comparison_strength`
- `test_negative_certificate_blocks_proof_carrying_analytics`
- `test_mandate_legitimacy_is_not_predictive_transition_without_matrix_row`
- `test_historical_prior_outside_context_cannot_improve_current_authority`
- `test_capacity_predictive_upgrade_requires_axis_dimension_grounding`
- `test_strategic_response_predictive_upgrade_requires_goodhart_lucas_channel_rows`
- `test_s11_calibration_gate_changes_forecast_quality_and_regime_strategy`
- `test_method_infrastructure_advancement_is_consumed_not_reclosed`
- `test_s11_artifacts_have_authority_boundary_and_deny_production_surface`
- `test_s11_summary_counts_predictive_and_reverted_axes_separately`
- `test_s11_integrity_report_requires_exact_false_clear_keys`

Each test should import from `polisyos.runtime.quality` first. The initial red
failure should be `ImportError` or `AttributeError` for the missing S11
contracts.

Add claim-registry consumer tests with these names in
`tests/unit/runtime/quality/test_claim_registry.py`:

- `test_s11_proof_carrying_record_projects_bridge_refs_into_claim_registry`
- `test_s11_proof_carrying_record_preserves_design_comparison_refs`
- `test_s11_negative_certificate_blocks_claim_registry_evidence_upgrade`

These tests should use the existing `build_runtime_claim_registry(...)` and
`claim_registry_rows_by_id(...)` consumer path. They should prove S11
`ProofCarryingAnalyticsRecord` rows are translated through the existing
IR-analytics bridge into claim-local proof refs, blocker refs, baseline refs,
alternative refs, and comparison refs. If the existing consumer already passes,
do not edit `src/polisyos/runtime/quality/claim_registry.py`.

- [ ] **Step 2: Add PDC injected-posture tests**

Add tests with these names:

- `test_s11_predictive_posture_input_is_strict_and_exported`
- `test_s2_consumes_injected_s11_posture_without_runtime_producer_import`
- `test_s2_s11_replay_digest_changes_only_when_predictive_posture_changes`
- `test_s2_s11_search_ledger_defaults_preserve_legacy_cas_payloads`
- `test_s2_s11_handoff_records_consumed_posture_not_recommendation_authority`
- `test_s2_s11_persisted_search_ledger_round_trips_predictive_refs`
- `test_s11_weakest_boundary_caps_search_ledger_projection`

The producer-import test must read
`src/polisyos/pdc/_impl/layer2_design_search.py` as text and assert that it
does not contain `layer2_predictive_knowledge`.

The replay/default/persistence tests should mirror the S10 tests around
`deterministic_replay_key`, `SearchLedger.model_validate(...)`, handoff record
rendering, and `persist_s2_design_record(...)`/`load_s2_search_ledger(...)`.
This is required because the current PDC implementation carries posture fields
explicitly rather than through a generic posture registry.

- [ ] **Step 3: Add projection/public-export tests**

Add tests with these names:

- `test_expert_and_machine_projection_surface_s11_confidence_and_residual_limits`
- `test_reviewer_projection_surfaces_s11_proof_and_calibration_limitations`
- `test_public_projection_surfaces_required_s11_limitation_without_authority_promotion`
- `test_public_projection_does_not_promote_s11_to_recommendation_authority`

These tests should assert that REVIEWER/EXPERT/MACHINE payloads expose S11 refs
and limitations. PUBLIC output must not gain recommendation or claim authority
from S11, and when a public-visible design status is limited by S11 the PUBLIC
payload must retain a high-level limitation rather than hiding the constraint.

- [ ] **Step 4: Add W12.D corpus tests**

Add tests with these names:

- `test_w12d_emits_s11_predictive_knowledge_blocks_for_13_cases`
- `test_w12d_s11_blocks_consume_s6_s10_and_ir_without_rerunning_them`
- `test_w12d_s11_injects_first_case_s2_posture_without_full_search_for_all_cases`
- `test_w12d_s11_summary_records_per_axis_calibration_floor_and_negative_controls`
- `test_w12d_s11_keeps_mandate_legitimacy_at_s6_floor`

The tests should expect:

- every corpus case contains `s11_predictive_knowledge`;
- every block uses schema
  `policyos.policy_design_case.layer2_s11_predictive_knowledge.v1`;
- at least one axis is `effective_maturity="predictive"`;
- at least one axis is `effective_maturity="fail_closed"`;
- summary `case_count == 13`;
- summary `axis_count == 52`;
- summary `per_axis_predictive_calibration_denominator == axis_count`;
- summary `per_axis_predictive_calibration_numerator <= denominator`;
- summary `predictive_axis_count + reverted_fail_closed_axis_count == axis_count`;
- all S11 false-clear counts are `0`;
- S2 full search consumes S11 posture for the first case, while the remaining
  12 cases expose a lightweight `predictive_posture_ref`.

- [ ] **Step 5: Add manifest/readiness tests**

Add tests with these names:

- `test_layer2_s11_manifest_exists_and_open_count_drops_to_1`
- `test_layer2_s11_required_artifacts_are_traceable_and_exported`
- `test_layer2_s11_inventory_registration_exists`
- `test_layer2_s11_floor_and_false_clears_are_governed`
- `test_layer2_s11_does_not_mark_s12_s13_s14_or_production_authority`
- `test_layer2_s11_maturity_transitions_match_matrix`

The tests should expect inventory artifact count `19`, remaining open cells
`["DESIGNER_ITSELF.envelope_growth"]`, and manifest required artifacts:
`PredictiveAxisCalibrationRecord`, `PredictiveAxisUpgradeRecord`,
`ProofCarryingAnalyticsRecord`, and `S11PredictiveKnowledgeIntegrityReport`.
They should also expect manifest `axis_count == 52` and
`per_axis_predictive_calibration_denominator == axis_count`.

- [ ] **Step 6: Run the red tests**

Run:

```bash
cd /Users/deniskopylov/polisyos/policy-engine
uv run pytest \
  tests/unit/runtime/quality/test_layer2_s11_predictive_knowledge.py \
  tests/unit/runtime/quality/test_claim_registry.py \
  tests/unit/pdc/test_layer2_readiness_contracts.py \
  tests/unit/pdc/test_layer2_s2_design_search.py \
  tests/unit/runtime/quality/test_layer2_s4_epistemic_regime.py \
  tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py \
  tests/unit/runtime/quality/test_public_export.py \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s11_predictive_knowledge.py \
  -q
```

Expected before implementation: failures caused by missing
`layer2_predictive_knowledge` contracts, missing
`Layer2S11PredictivePostureInput`, absent S11 corpus blocks, and absent S11
manifest. No unrelated failures should be introduced.

- [ ] **Step 7: Commit**

Stage only the new/modified S11 test and fixture paths used in this task.

```bash
git add \
  tests/unit/runtime/quality/test_layer2_s11_predictive_knowledge.py \
  tests/unit/runtime/quality/test_claim_registry.py \
  tests/unit/pdc/test_layer2_readiness_contracts.py \
  tests/unit/pdc/test_layer2_s2_design_search.py \
  tests/unit/runtime/quality/test_layer2_s4_epistemic_regime.py \
  tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py \
  tests/unit/runtime/quality/test_public_export.py \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s11_predictive_knowledge.py
git commit -m "test: add layer2 s11 predictive knowledge red tests" \
  -m "Co-authored-by: Cursor <cursoragent@cursor.com>"
```

## Task 2: Contracts, Producer, Calibration Verifier, And Authority Envelope

**Intent:** add the strict runtime-quality S11 artifacts and the producer logic
that decides whether each axis can relax from S6 fail-closed to predictive.

**Files:**

- Create: `src/polisyos/runtime/quality/layer2_predictive_knowledge.py`
- Modify: `src/polisyos/runtime/quality/__init__.py`
- Test: `tests/unit/runtime/quality/test_layer2_s11_predictive_knowledge.py`
- Test: `tests/unit/runtime/quality/test_claim_registry.py`

- [ ] **Step 1: Define strict models**

Implement the four S11 models as subclasses of the repo's strict PDC/runtime
model base. Every public DTO must have `extra="forbid"` through the inherited
config or explicit `model_config`.

`PredictiveAxisCalibrationRecord` must carry:

- `schema_version`
- `calibration_id`
- `calibration_ref`
- `case_id`
- `axis`
- `cell_ref`
- `s6_floor_record_ref`
- `s10_forecast_support_ref`
- `s10_forecast_calibration_record_ref`
- `calibration_ledger_ref`
- `calibration_scope_ref`
- `prediction_context_ref`
- `policy_context_ref`
- `model_family`
- `source_contract_ref`
- `method_validity_ref`
- `method_infrastructure_refs`
- `source_lineage_refs`
- `method_lineage_refs`
- `effective_independence_refs`
- `sensitivity_analysis_ref`
- `credible_evaluation_evidence_ref`
- `counterfactual_credibility_ref`
- `prediction_time`
- `observation_time`
- `policy_effective_time`
- `data_valid_time`
- `calibration_window_start`
- `calibration_window_end`
- `denominator`
- `numerator`
- `pass_rate`
- `threshold`
- `threshold_ref`
- `floor_id`
- `floor_passed`
- `calibration_status`
- `residual_limitation_refs`
- `authority_boundary`
- `may_not_use_for`
- `rule_version_ref`

`PredictiveAxisUpgradeRecord` must carry:

- `upgrade_id`
- `upgrade_ref`
- `case_id`
- `axis`
- `cell_ref`
- `from_maturity`
- `target_maturity`
- `effective_maturity`
- `relaxation_decision`
- `s6_floor_record_ref`
- `s6_floor_disposition`
- `s10_forecast_support_ref`
- `predictive_model_ref`
- `axis_model_evidence_refs`
- `capacity_dimension_rows`
- `strategic_response_channel_rows`
- `calibration_record_ref`
- `proof_carrying_analytics_ref`
- `dynamic_equilibrium_check_ref`
- `equilibrium_caveat_refs`
- `forecast_quality_disposition`
- `regime_strategy_constraint_ref`
- `residual_limitation_refs`
- `constraint_store_update_refs`
- `authority_boundary`
- `may_not_use_for`
- `rule_version_ref`

`ProofCarryingAnalyticsRecord` must carry:

- `proof_id`
- `proof_ref`
- `case_id`
- `claim_id`
- `design_comparison_ref`
- `baseline_design_ref`
- `alternative_design_refs`
- `ir_analytics_refs`
- `method_output_refs`
- `ir_certificate_refs`
- `negative_certificate_refs`
- `proof_status`
- `proof_composability_status`
- `proof_composability_refs`
- `method_requirement_refs`
- `uncertainty_refs`
- `independence_refs`
- `effective_independence_collapse_refs`
- `counter_evidence_refs`
- `limitation_refs`
- `blocker_refs`
- `ir_analytics_bridge_ref`
- `claim_registry_entry_ref`
- `comparison_consumer_ref`
- `source_lineage_refs`
- `method_lineage_refs`
- `authority_boundary`
- `may_not_use_for`
- `rule_version_ref`

`S11PredictiveKnowledgeIntegrityReport` must carry:

- `report_id`
- `case_count`
- `axis_count`
- `predictive_axis_count`
- `reverted_fail_closed_axis_count`
- `per_axis_predictive_calibration_numerator`
- `per_axis_predictive_calibration_denominator`
- `per_axis_predictive_calibration_pass_rate`
- `per_axis_predictive_calibration_threshold`
- `per_axis_predictive_calibration_threshold_ref`
- `per_axis_predictive_calibration_status`
- `per_axis_predictive_calibration_floor_passed`
- `proof_bound_claim_count`
- `unbound_analytics_rejected_count`
- `negative_certificate_block_count`
- `forecast_quality_downgrade_count`
- `regime_strategy_constraint_count`
- `method_infrastructure_consumed_count`
- `weakest_boundary_inheritance_count`
- `false_clear_counts`
- `authority_boundary`
- `may_not_use_for`
- `rule_version_ref`

The integrity report must validate that
`set(false_clear_counts) == set(S11_FALSE_CLEAR_FIELDS)`, mirroring
`ForecastSupportIntegrityReport`. Flat manifest/summary false-clear fields may
be generated from this tuple, but the tuple remains the source of truth.

- [ ] **Step 2: Add invariant checks**

Enforce these invariants in validators or builder helpers:

- `axis` can relax to predictive only if it is one of
  `strategic_response`, `state_capacity_feasibility`, `measurability`, or
  `subject_granularity`.
- `mandate_legitimacy` may appear only as a floor/limitation ref; it cannot
  produce `effective_maturity="predictive"`.
- `relaxation_decision="relaxed_to_predictive"` requires
  `floor_passed=True`, `calibration_status="pass"`, a non-empty
  `calibration_record_ref`, `source_contract_ref`, `method_validity_ref`,
  `method_infrastructure_refs`, `source_lineage_refs`, `method_lineage_refs`,
  `effective_independence_refs`, `sensitivity_analysis_ref`,
  `s6_floor_record_ref`, and `s10_forecast_support_ref`.
- `state_capacity_feasibility` predictive upgrades require at least one
  `capacity_dimension_rows` entry for the claimed capacity dimension, and rows
  must name administrative, fiscal, enforcement, delivery, coordination, or
  political-feasibility grounding where that dimension is used by the design.
- `strategic_response` predictive upgrades require
  `dynamic_equilibrium_check_ref` or at least one `equilibrium_caveat_refs`
  entry, plus `strategic_response_channel_rows` for the claimed Goodhart,
  Lucas/performativity, capture, gaming, adaptation, or compliance-response
  channel.
- any stale, failed, missing, or out-of-scope calibration forces
  `effective_maturity="fail_closed"` and
  `relaxation_decision="reverted_fail_closed"` and emits
  `forecast_quality_disposition="downgraded_by_s11_calibration"` plus a
  `regime_strategy_constraint_ref`.
- a proof record with `negative_certificate_refs` or blocking proof status
  cannot support a predictive upgrade.
- a historical prior outside current case scope, policy context, or
  calibration window cannot improve current-run authority.
- S11 posture must preserve S6 `axis_rows`, `bridge_consumer_rows`,
  `constraint_store_updates`, `c3_authority_dimension_rows`,
  `post_intervention_dgp_update_ref`, and
  `system_dynamics_handoff_required` refs when it relaxes or reverts an axis.
  A predictive overlay cannot drop the fail-closed handoff or consumer surface.
- Historical-prior influence records may adjust routing, review depth,
  uncertainty, evidence budget, or authority caps only through allowed ledger
  influence effects. They cannot satisfy current-run evidence, proof, or method
  validity slots for S11 relaxation.

- [ ] **Step 3: Build producer helpers**

`build_s11_predictive_knowledge_posture(...)` should accept existing S6/S10
records or mappings plus calibration/proof rows. It should return a replayable
mapping with:

- `schema_version`
- `case_id`
- `predictive_knowledge_ref`
- `axis_upgrade_refs`
- `axis_upgrade_rows`
- `proof_carrying_analytics_ref`
- `ir_analytics_bridge_ref`
- `s10_forecast_support_ref`
- `s6_floor_status_refs`
- `s6_axis_rows`
- `s6_bridge_consumer_rows`
- `s6_constraint_store_update_refs`
- `s6_c3_authority_dimension_refs`
- `post_intervention_dgp_update_ref`
- `system_dynamics_handoff_required`
- `s11_calibration_record_refs`
- `method_infrastructure_refs`
- `forecast_quality_disposition`
- `regime_strategy_constraint_ref`
- `per_axis_predictive_calibration_*` fields
- `effective_predictive_posture`
- `residual_limitation_refs`
- `authority_boundary`
- `may_not_use_for`
- `canonical_outcome_effect = "predictive_relaxation_only_not_production_authority"`
- `rule_version_ref`

The helper should reuse `normalize_ir_analytics_claim_bridge` or
`build_ir_analytics_claim_bridge` from
`polisyos.runtime.quality.ir_analytics_bridge` instead of duplicating bridge
logic.

- [ ] **Step 4: Export runtime-quality symbols**

Add imports and `__all__` entries in `src/polisyos/runtime/quality/__init__.py`
for all S11 models, constants, and helpers. Keep import ordering consistent with
the S10 export block.

- [ ] **Step 5: Run runtime tests**

Run:

```bash
cd /Users/deniskopylov/polisyos/policy-engine
uv run pytest \
  tests/unit/runtime/quality/test_layer2_s11_predictive_knowledge.py \
  tests/unit/runtime/quality/test_claim_registry.py \
  -q
```

Expected after Task 2: runtime S11 tests pass. PDC, projection, corpus, and
manifest tests still fail because wiring is not complete.

- [ ] **Step 6: Commit**

```bash
git add \
  src/polisyos/runtime/quality/layer2_predictive_knowledge.py \
  src/polisyos/runtime/quality/__init__.py \
  tests/unit/runtime/quality/test_layer2_s11_predictive_knowledge.py \
  tests/unit/runtime/quality/test_claim_registry.py
git commit -m "feat: add layer2 s11 predictive knowledge contracts" \
  -m "Co-authored-by: Cursor <cursoragent@cursor.com>"
```

## Task 3: Wire S11 Predictive Posture Into PDC Context, Semantics, And Export

**Intent:** make PDC and projection consumers read injected S11 posture as
constraint data, without importing runtime-quality producers.

**Files:**

- Modify: `src/polisyos/pdc/_impl/layer2_design_search.py`
- Modify: `src/polisyos/pdc/__init__.py`
- Modify: `src/polisyos/runtime/quality/layer2_epistemic_regime.py`
- Modify: `src/polisyos/runtime/quality/projection_semantics.py`
- Modify: `src/polisyos/runtime/quality/public_export.py`
- Test: `tests/unit/pdc/test_layer2_readiness_contracts.py`
- Test: `tests/unit/pdc/test_layer2_s2_design_search.py`
- Test: `tests/unit/runtime/quality/test_layer2_s4_epistemic_regime.py`
- Test: `tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py`
- Test: `tests/unit/runtime/quality/test_public_export.py`

- [ ] **Step 1: Add PDC posture contract**

Add `Layer2S11PredictivePostureInput` near `Layer2S10ForecastPostureInput`.
Required fields:

- `predictive_knowledge_ref`
- `effective_predictive_posture`
- `axis_upgrade_refs`
- `predictive_axis_rows`
- `proof_carrying_analytics_ref`
- `ir_analytics_bridge_ref`
- `s10_forecast_support_ref`
- `s10_forecast_tier`
- `s6_floor_status_refs`
- `s6_axis_rows`
- `s6_bridge_consumer_rows`
- `s6_constraint_store_update_refs`
- `s6_c3_authority_dimension_refs`
- `post_intervention_dgp_update_ref`
- `system_dynamics_handoff_required`
- `s11_calibration_record_refs`
- `method_infrastructure_refs`
- `forecast_quality_disposition`
- `regime_strategy_constraint_ref`
- `residual_limitation_refs`
- `per_axis_predictive_calibration_threshold_ref`
- `per_axis_predictive_calibration_denominator`
- `per_axis_predictive_calibration_numerator`
- `per_axis_predictive_calibration_pass_rate`
- `per_axis_predictive_calibration_status`
- `weakest_boundary_reason`
- `authority_boundary`
- `may_not_use_for`
- `rule_version_ref`

The model must be strict and exported from `polisyos.pdc`.

- [ ] **Step 2: Thread posture through S2 run state**

Add an optional `predictive_posture` parameter to:

- `Layer2S2DesignSearchRun`
- `run_s2_shadow_design_loop(...)`
- helper functions that build search ledger refs, axis positions, firewall
  statuses, design record ledger refs, constraint-store rows, handoff records,
  and serialized lightweight summaries.

Use helper names parallel to S10:

- `_s11_projection_fields(...)`
- `_s11_axis_position(...)`
- `_s11_firewall_status(...)`
- `_s11_constraint_entries(...)`
- `_s11_refinement_decision(...)`
- `_s11_run_status(...)`
- `_s11_iteration_status(...)`
- `_s11_design_record_ledger_refs(...)`
- `_s11_predictive_posture_refs(...)`
- `_s11_predictive_authority_status(...)`
- `_s11_handoff_record(...)`

Add explicit `SearchLedger` fields with backward-compatible defaults:

- `predictive_knowledge_refs`
- `predictive_axis_upgrade_refs`
- `proof_carrying_analytics_refs`
- `ir_analytics_bridge_refs`
- `s11_calibration_record_refs`
- `s11_forecast_quality_constraint_refs`
- `s11_regime_strategy_constraint_refs`
- `s11_residual_limitation_refs`
- `predictive_authority_status`
- `predictive_authority_boundary`

Because the current S2 implementation is manual, also update
`_constraint_store(...)`, `_cluster_interfaces(...)`, `_handoff_records(...)`,
`_deterministic_replay_key(...)`, `persist_s2_design_record(...)` payload
round-trip expectations, and `SearchLedger.model_validate(...)` legacy-default
tests. Do not rely on a generic posture bag that does not exist.

- [ ] **Step 3: Enforce consumer boundary**

PDC search may use only `Layer2S11PredictivePostureInput` fields. It must not
import `polisyos.runtime.quality.layer2_predictive_knowledge` or any S11
producer helper.

When S11 posture says the weakest boundary is fail-closed, S2 should:

- add a constraint-store row with status `limit` or `block`;
- include residual limitation refs in the search ledger;
- keep candidate ranking advisory/shadow;
- not convert S11 confidence into recommendation authority.

When S11 posture says calibration is absent, stale, poor, or out of scope, S2
must also emit explicit consumer constraints:

- `KNOWLEDGE.epistemic_regime` receives a regime strategy constraint ref;
- `INTERVENTION.forecast_quality` receives a forecast-quality downgrade row;
- neither row reruns S4 or S10 producers.

- [ ] **Step 4: Add regime/forecast-quality consumer tests**

Add or update tests in
`tests/unit/runtime/quality/test_layer2_s4_epistemic_regime.py` and
`tests/unit/pdc/test_layer2_s2_design_search.py`:

- `test_s11_stale_calibration_creates_regime_strategy_constraint`
- `test_s11_poor_calibration_downgrades_forecast_quality_without_reclassifying_s10_tier`
- `test_s2_records_s11_forecast_quality_constraint_without_rerunning_s4_or_s10`

These tests should prove that S11 calibration changes downstream posture while
S10 remains the owner of `forecast_tier`.

- [ ] **Step 5: Add projection fields**

REVIEWER, EXPERT, and MACHINE projections must expose:

- `s11_predictive_posture_ref`
- `predictive_axis_upgrade_refs`
- `predictive_axis_rows`
- `per_axis_predictive_calibration_status`
- `per_axis_predictive_calibration_threshold_ref`
- `proof_carrying_analytics_ref`
- `ir_analytics_bridge_ref`
- `residual_limitation_refs`
- `weakest_boundary_reason`

PUBLIC projection must expose a high-level S11 limitation when S11 changes a
public-visible design status, but it must not expose S11 as recommendation or
claim authority.

Note that this deliberately extends beyond the current S10 pattern, where deep
forecast refs are mainly EXPERT/MACHINE-facing. REVIEWER must receive enough
S11 calibration/proof/residual-limitation detail to audit the relaxation
decision, while PUBLIC receives only the limitation summary.

- [ ] **Step 6: Run PDC/projection tests**

Run:

```bash
cd /Users/deniskopylov/polisyos/policy-engine
uv run pytest \
  tests/unit/pdc/test_layer2_readiness_contracts.py \
  tests/unit/pdc/test_layer2_s2_design_search.py \
  tests/unit/runtime/quality/test_layer2_s4_epistemic_regime.py \
  tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py \
  tests/unit/runtime/quality/test_public_export.py \
  -q
```

Expected after Task 3: PDC and projection tests pass. Corpus and readiness tests
still fail because S11 is not yet routed through W12.D or registered in
architecture inventory.

- [ ] **Step 7: Commit**

```bash
git add \
  src/polisyos/pdc/_impl/layer2_design_search.py \
  src/polisyos/pdc/__init__.py \
  src/polisyos/runtime/quality/layer2_epistemic_regime.py \
  src/polisyos/runtime/quality/projection_semantics.py \
  src/polisyos/runtime/quality/public_export.py \
  tests/unit/pdc/test_layer2_readiness_contracts.py \
  tests/unit/pdc/test_layer2_s2_design_search.py \
  tests/unit/runtime/quality/test_layer2_s4_epistemic_regime.py \
  tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py \
  tests/unit/runtime/quality/test_public_export.py
git commit -m "feat: wire layer2 s11 predictive posture into projections" \
  -m "Co-authored-by: Cursor <cursoragent@cursor.com>"
```

## Task 4: Canonical Corpus Route Wiring - 13-Case S11 Coverage

**Intent:** add S11 to W12.D so all 13 canonical cases carry predictive
knowledge blocks, floor metrics, and false-clear probes.

**Files:**

- Modify: `tools/quality/validation/run_universal_outcome_corpus.py`
- Create: `tests/fixtures/layer2/s11/s11_predictive_knowledge_case_signals.json`
- Create: `tests/fixtures/layer2/s11/s11_predictive_knowledge_expert_labels.json`
- Create: all `tests/fixtures/layer2/s11/negative_controls/*.json` probes
- Test: `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`

- [ ] **Step 1: Add S11 constants and fixture paths**

Add:

- `LAYER2_S11_PREDICTIVE_KNOWLEDGE_SCHEMA_VERSION`
- `LAYER2_S11_PREDICTIVE_KNOWLEDGE_RULE_VERSION`
- `S11_AXIS_CALIBRATION_FLOOR_ID`
- `S11_CASE_SIGNALS_PATH`
- `S11_EXPERT_LABELS_PATH`
- `S11_NEGATIVE_CONTROL_PROBE_PATHS`
- `S11_MAY_NOT_USE_FOR`
- `S11_FALSE_CLEAR_FIELDS`

`S11_MAY_NOT_USE_FOR` must include every deny item listed in the contract
dictionary.

- [ ] **Step 2: Add S11 case-signal fixtures**

The case-signal fixture must include all 13 W12.D case ids. For each case,
include:

- `case_id`
- `predictive_knowledge_input_ref`
- `s6_floor_status_refs`
- `s6_axis_rows`
- `s6_bridge_consumer_rows`
- `s6_constraint_store_update_refs`
- `s6_c3_authority_dimension_refs`
- `post_intervention_dgp_update_ref`
- `system_dynamics_handoff_required`
- `s10_forecast_support_ref`
- `s10_forecast_tier`
- `calibration_ledger_ref`
- `ir_analytics_bridge_ref`
- `proof_carrying_analytics_ref`
- `method_infrastructure_refs`
- `forecast_quality_disposition`
- `regime_strategy_constraint_ref`
- `axis_rows` with exactly the four S11 predictive-transition axes
- `expected_authority_boundary`
- `expected_effective_predictive_posture`
- `expected_residual_limitation_refs`
- `per_axis_predictive_calibration_threshold`
- `per_axis_predictive_calibration_threshold_ref`

At least one row across the corpus must relax to predictive, and at least one
row must revert to fail-closed.

Every case must carry exactly four `axis_rows`. Across the 13-case corpus,
`axis_count` is therefore `52`. Each row must be either
`effective_maturity="predictive"` or `effective_maturity="fail_closed"`;
there is no uncounted middle bucket. Capacity rows must include dimension
grounding for the capacity dimension being claimed. Strategic-response rows
must include named Goodhart/Lucas/performativity/capture/gaming/adaptation or
compliance-response channels.

- [ ] **Step 3: Add negative control probes**

Each negative probe should contain:

- `probe_id`
- `case_id`
- `false_clear_field`
- `expected_false_clear_count = 0`
- `expected_disposition = "reverted_fail_closed"` or
  `"proof_blocked"`
- `why_it_must_not_clear`

Probe ids:

- `stale_calibration_relaxation`
- `scope_mismatched_historical_prior`
- `unbound_ir_analytics`
- `negative_certificate_ignored`
- `missing_method_validity`
- `missing_s6_floor_ref`
- `mandate_axis_predictive_upgrade`
- `production_authority_from_predictive_upgrade`
- `rich_simulation_authority_laundering`
- `weakest_boundary_bypass`

- [ ] **Step 4: Add S11 corpus block builder**

Add `_s11_predictive_knowledge_case_block(...)` after the S10 helpers. It must
consume the already-built `s6_blind_spot_firewalls` and
`s10_outcome_prediction` mappings, plus S11 fixture rows. It must build S11
runtime records using the Task 2 helper and return a dict with:

- `schema_version`
- `case_id`
- `predictive_knowledge_ref`
- `effective_predictive_posture`
- `axis_upgrade_refs`
- `axis_upgrade_rows`
- `proof_carrying_analytics_ref`
- `ir_analytics_bridge_ref`
- `s10_forecast_support_ref`
- `s10_forecast_tier`
- `s6_floor_status_refs`
- `s6_axis_rows`
- `s6_bridge_consumer_rows`
- `s6_constraint_store_update_refs`
- `s6_c3_authority_dimension_refs`
- `post_intervention_dgp_update_ref`
- `system_dynamics_handoff_required`
- `method_infrastructure_refs`
- `forecast_quality_disposition`
- `regime_strategy_constraint_ref`
- `per_axis_predictive_calibration_*`
- `residual_limitation_refs`
- `authority_boundary`
- `may_not_use_for`
- `canonical_outcome_effect`
- `coverage_labels`
- `matches_gold`
- `rule_version_ref`

Do not rerun S6, S10, calibration-ledger, or IR producers inside this helper.
It should consume refs and normalized rows.

The corpus tool may import and call S11 runtime-quality helpers to build the S11
block, just as it imports S10 forecast helpers. Keep that producer path inside
W12.D. The PDC/S2 search path must receive only
`Layer2S11PredictivePostureInput`.

If the S11 block needs a `source_design_record_ref` or digest that is only known
after `_s2_design_search_summary(...)`, follow the S10
`_s10_with_source_design_record(...)` finalization pattern instead of creating a
circular producer dependency.

- [ ] **Step 5: Add S11 posture input helper**

Add `_s11_predictive_posture_input(...) -> Layer2S11PredictivePostureInput`.
Pass this posture into `_s2_design_search_summary(...)` and then into
`run_s2_shadow_design_loop(...)`.

For the 12 lightweight cases, include:

- `predictive_posture_ref`
- `proof_carrying_analytics_ref`
- `per_axis_predictive_calibration_status`
- `effective_predictive_posture`
- `predictive_authority_boundary`

- [ ] **Step 6: Add S11 summary**

Add `_s11_predictive_knowledge_summary(...)` and include it in
`build_w12d_universal_outcome_corpus_report(...)` under
`s11_predictive_knowledge_summary`.

Summary fields must include:

- `case_count`
- `axis_count`
- `predictive_axis_count`
- `reverted_fail_closed_axis_count`
- `per_axis_predictive_calibration_numerator`
- `per_axis_predictive_calibration_denominator`
- `per_axis_predictive_calibration_pass_rate`
- `per_axis_predictive_calibration_threshold`
- `per_axis_predictive_calibration_threshold_ref`
- `per_axis_predictive_calibration_status`
- `per_axis_predictive_calibration_floor_passed`
- `proof_bound_claim_count`
- `unbound_analytics_rejected_count`
- `negative_certificate_block_count`
- `forecast_quality_downgrade_count`
- `regime_strategy_constraint_count`
- `method_infrastructure_consumed_count`
- `weakest_boundary_inheritance_count`
- all flat S11 false-clear count fields
- nested `false_clear_counts`

- [ ] **Step 7: Run corpus tests**

Run:

```bash
cd /Users/deniskopylov/polisyos/policy-engine
uv run pytest tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py -q
```

Expected after Task 4: W12.D S11 corpus tests pass; manifest/readiness tests
still fail until registration is done.

- [ ] **Step 8: Commit**

```bash
git add \
  tools/quality/validation/run_universal_outcome_corpus.py \
  tests/fixtures/layer2/s11/s11_predictive_knowledge_case_signals.json \
  tests/fixtures/layer2/s11/s11_predictive_knowledge_expert_labels.json \
  tests/fixtures/layer2/s11/negative_controls/stale_calibration_relaxation_probe.json \
  tests/fixtures/layer2/s11/negative_controls/scope_mismatched_historical_prior_probe.json \
  tests/fixtures/layer2/s11/negative_controls/unbound_ir_analytics_probe.json \
  tests/fixtures/layer2/s11/negative_controls/negative_certificate_ignored_probe.json \
  tests/fixtures/layer2/s11/negative_controls/missing_method_validity_probe.json \
  tests/fixtures/layer2/s11/negative_controls/missing_s6_floor_ref_probe.json \
  tests/fixtures/layer2/s11/negative_controls/mandate_axis_predictive_upgrade_probe.json \
  tests/fixtures/layer2/s11/negative_controls/production_authority_from_predictive_upgrade_probe.json \
  tests/fixtures/layer2/s11/negative_controls/rich_simulation_authority_laundering_probe.json \
  tests/fixtures/layer2/s11/negative_controls/weakest_boundary_bypass_probe.json \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py
git commit -m "feat: classify layer2 s11 predictive knowledge coverage" \
  -m "Co-authored-by: Cursor <cursoragent@cursor.com>"
```

## Task 5: S11 Manifest, Readiness Validator, Traceability, And Inventory

**Intent:** register S11 as a real Layer 2 capability, close the two knowledge
cells, update S6 maturity qualifiers, and keep future-slice firewalls intact.

**Files:**

- Create: `architecture/policy_design_case/layer2_s11_predictive_knowledge_manifest.json`
- Modify: `architecture/policy_design_case/cluster_ownership_map.toml`
- Modify: `architecture/policy_design_case/layer2_artifact_traceability.toml`
- Modify: `architecture/policy_design_case/inventory.json`
- Modify: `tools/quality/validation/check_policy_design_case_layer2_readiness.py`
- Modify: `tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py`
- Modify: `tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py`
- Modify: `tests/repo_quality/tools/test_policy_design_case_layer2_s2_design_search.py`
- Modify: `tests/repo_quality/tools/test_policy_design_case_layer2_s3_substrate_acquisition.py`
- Modify: `tests/repo_quality/tools/test_policy_design_case_layer2_s4_epistemic_regime.py`
- Modify: `tests/repo_quality/tools/test_policy_design_case_layer2_s5_coupling_composition.py`
- Modify: `tests/repo_quality/tools/test_policy_design_case_layer2_s6_blind_spot_firewalls.py`
- Modify: `tests/repo_quality/tools/test_policy_design_case_layer2_s7_delegation.py`
- Modify: `tests/repo_quality/tools/test_policy_design_case_layer2_s8_value_choice.py`
- Modify: `tests/repo_quality/tools/test_policy_design_case_layer2_s9_projection_lowering.py`
- Modify: `tests/repo_quality/tools/test_policy_design_case_layer2_s10_outcome_prediction.py`
- Test: `tests/repo_quality/tools/test_policy_design_case_layer2_s11_predictive_knowledge.py`

- [ ] **Step 1: Create manifest**

The manifest must include:

- `schema_version =
  "policyos.policy_design_case.layer2_s11_predictive_knowledge_manifest.v1"`
- `status = "active"`
- `owner = "team-research"`
- `slice = "S11"`
- `depends_on = ["S6", "S10"]`
- `cells_closed = ["KNOWLEDGE.calibration",
  "KNOWLEDGE.ir_proof_carrying_analytics"]`
- `maturity_transitions` matching the four matrix rows exactly
- `layer_cells_advanced = ["CROSS_CUTTING.method_infrastructure"]`
- `required_artifacts = ["PredictiveAxisCalibrationRecord",
  "PredictiveAxisUpgradeRecord", "ProofCarryingAnalyticsRecord",
  "S11PredictiveKnowledgeIntegrityReport"]`
- `floor_id = "s11_axis_calibration"`
- `floor_metric = "per_axis_predictive_calibration"`
- `case_count = 13`
- `axis_count = 52`
- `expected_current_open_cell_count = 1`
- `remaining_open_cells = ["DESIGNER_ITSELF.envelope_growth"]`
- per-axis floor numerator, denominator, pass rate, threshold, threshold ref,
  status, and floor-passed flag, with denominator equal to `axis_count`
- predictive/reverted axis counts, with
  `predictive_axis_count + reverted_fail_closed_axis_count == axis_count`
- proof-bound, unbound-rejected, negative-certificate-block, and
  weakest-boundary counts
- forecast-quality downgrade count, regime-strategy constraint count, and
  method-infrastructure consumed count
- flat and nested S11 false-clear counts, all zero
- `authority_scope`
- `may_not_use_for`

Perfect pass rate is allowed for fixture evidence but is not required as the
universal semantic rule. The semantic rule is that no axis may be predictive
without passing governed calibration and proof checks.

- [ ] **Step 2: Update cluster ownership map**

Remove the two S11 rows from `[open_cell_closure.*]`:

- `KNOWLEDGE.calibration`
- `KNOWLEDGE.ir_proof_carrying_analytics`

Update relevant `[cell.*]`, `architecture_core.package_group`, and
`architecture_core.subpackage_group` rows so calibration and IR proof-carrying
analytics are `ratchet_state = "implemented"` and `p01_chain = "implemented"`.
Use action/gap text that says S11 now routes calibration/proof into forecast
quality, regime/design-loop constraints, claim records, and design comparison.

For S6 cells with S11 maturity transitions, preserve their S6 implemented
state and record that predictive maturity is now governed by S11. Do not mark
`ACTOR.mandate_legitimacy` predictive.

For `CROSS_CUTTING.method_infrastructure`, preserve `ratchet_state =
"implemented"` and do not add or remove it from open-cell closure rows. Update
only action/gap text or manifest references needed to show that S11 consumed
Foundry method/calibration/validation refs as infrastructure.

- [ ] **Step 3: Update artifact traceability**

Set `ProofCarryingAnalyticsRecord` maturity to `implemented`.

Add S11 artifact rows for:

- `PredictiveAxisCalibrationRecord`
- `PredictiveAxisUpgradeRecord`
- `S11PredictiveKnowledgeIntegrityReport`

All three should have `slice = "S11"` and `maturity = "implemented"`.

- [ ] **Step 4: Register inventory artifact**

Add one inventory artifact:

- `id = "layer2_s11_predictive_knowledge_manifest"`
- `path =
  "architecture/policy_design_case/layer2_s11_predictive_knowledge_manifest.json"`
- `kind = "layer2_s11_predictive_knowledge_manifest"`
- `schema_version =
  "policyos.policy_design_case.layer2_s11_predictive_knowledge_manifest.v1"`
- `owner = "team-research"`
- `status = "active"`
- `capability_reality_label = "implemented"`
- `authority_scope` equal to manifest authority scope
- `may_not_use_for` equal to manifest deny list

The governed Layer 2 inventory artifact count should become `19`.
Use the validator's governed Layer 2 inventory count helper
(`_inventory_layer2_artifact_count(...)`), not raw
`len(inventory["artifacts"])`, because the inventory file may contain
non-Layer-2 artifacts.

- [ ] **Step 5: Update readiness validator**

Extend `tools/quality/validation/check_policy_design_case_layer2_readiness.py`
to load the S11 manifest and summarize:

- `s11_case_count`
- `s11_expected_current_open_cell_count`
- `s11_axis_count`
- `s11_per_axis_predictive_calibration_threshold_ref`
- `s11_per_axis_predictive_calibration_denominator`
- `s11_per_axis_predictive_calibration_numerator`
- `s11_per_axis_predictive_calibration_pass_rate`
- `s11_per_axis_predictive_calibration_status`
- `s11_per_axis_predictive_calibration_floor_passed`
- `s11_predictive_axis_count`
- `s11_reverted_fail_closed_axis_count`
- `s11_proof_bound_claim_count`
- `s11_unbound_analytics_rejected_count`
- `s11_negative_certificate_block_count`
- `s11_forecast_quality_downgrade_count`
- `s11_regime_strategy_constraint_count`
- `s11_method_infrastructure_consumed_count`
- `s11_weakest_boundary_inheritance_count`
- all `s11_*_false_clear_count` fields

Validation must fail if:

- current open cell count is not `1`;
- remaining open cell is not exactly `DESIGNER_ITSELF.envelope_growth`;
- inventory artifact count is not `19`;
- `s11_axis_count` is not `52`;
- S11 per-axis calibration threshold ref is missing;
- S11 per-axis calibration threshold is not numeric;
- S11 per-axis calibration denominator is not equal to `s11_axis_count`;
- S11 per-axis calibration pass rate is below the governed threshold;
- S11 per-axis calibration status is not `pass`;
- S11 per-axis calibration floor-passed flag is not `true`;
- S11 predictive plus reverted fail-closed axis counts do not equal
  `s11_axis_count`;
- S11 method-infrastructure consumed count is `0`;
- S11 false-clear counts are non-zero;
- any S12/S13/S14 or production authority cell is marked implemented;
- `ACTOR.mandate_legitimacy` is marked as predictive maturity without a matrix
  row.

Also update the existing S10 validation branch. Today
`_validate_s10_outcome_prediction(...)` checks live `current_open_cells` against
the post-S10 set and checks governed Layer 2 inventory count `18`. After S11,
it must:

- keep `s10["expected_current_open_cell_count"] == 3` as the S10 manifest-local
  contract;
- allow live `current_open_cells == {"DESIGNER_ITSELF.envelope_growth"}` when
  the S11 manifest is present and valid;
- continue rejecting S10 manifest claims that close S11/S12/S13/S14 or future
  authority;
- replace S10-branch inventory exact `== 18` with `>= 18`, while preserving the
  S10 inventory artifact's own id/path/kind/schema/authority checks. The exact
  post-S11 inventory count `19` belongs to the central readiness/S11 gate, not
  to S10 as a previous-slice compatibility test.

- [ ] **Step 6: Update open-count snapshot tests and cluster negative controls**

Update the full repo-quality open-count snapshot surface instead of waiting for
`workspace verify --backend-only` to find failures.

In `tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py`:

- add `CELLS_CLOSED_THROUGH_S11 = sorted({*CELLS_CLOSED_THROUGH_S8,
  "KNOWLEDGE.calibration", "KNOWLEDGE.ir_proof_carrying_analytics"})`;
- change live `current_open_cell_count` expectations from `3` to `1`;
- change `cells_closed_since_s0 == CELLS_CLOSED_THROUGH_S8` to
  `cells_closed_since_s0 == CELLS_CLOSED_THROUGH_S11`;
- change `assigned - current_open_cells == set(CELLS_CLOSED_THROUGH_S8)` to
  `assigned - current_open_cells == set(CELLS_CLOSED_THROUGH_S11)`;
- keep historical manifest-local expected counts such as
  `s8_expected_current_open_cell_count == 3`,
  `s9_expected_current_open_cell_count == 3`, and
  `s10_expected_current_open_cell_count == 3`.

In `tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py`:

- change live `open_cell_closure["open_cell_count"]` expectation from `3` to
  `1`;
- update the four negative-control tests that currently mutate
  `payload["open_cell_closure"]["KNOWLEDGE"]["calibration"]` so they mutate the
  remaining open-cell closure
  `payload["open_cell_closure"]["DESIGNER_ITSELF"]["envelope_growth"]`;
- make the mutation helper select the remaining open closure programmatically
  where practical, so future cell-closing slices do not require hardcoded
  `KNOWLEDGE.calibration` edits.

In the per-slice repo-quality tests below, remove exact live open-count `== 3`
assertions and replace them with stable checks:

- keep each slice manifest-local `expected_current_open_cell_count` assertion;
- assert the slice's own closed cells are absent from
  `summary["remaining_open_cells"]` or the cluster map;
- assert `summary["current_open_cell_count"] >= 1` only as a post-S11 live
  floor, not as the slice's closure contract;
- for files with `EXPECTED_LIVE_OPEN_CELLS`, replace exact equality with a
  post-S11 minimum/remaining-open assertion against
  `{"DESIGNER_ITSELF.envelope_growth"}`.

Update these files:

- `tests/repo_quality/tools/test_policy_design_case_layer2_s2_design_search.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s3_substrate_acquisition.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s4_epistemic_regime.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s5_coupling_composition.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s6_blind_spot_firewalls.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s7_delegation.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s8_value_choice.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s9_projection_lowering.py`

- [ ] **Step 7: Update S10 repo-quality assertions for S11 burn-down**

Update `tests/repo_quality/tools/test_policy_design_case_layer2_s10_outcome_prediction.py`
so S10's manifest-local contract remains true while global readiness reflects
S11 completion:

- keep `manifest["expected_current_open_cell_count"] == 3`;
- keep `summary["s10_expected_current_open_cell_count"] == 3`;
- replace global `summary["current_open_cell_count"] == 3` with a stable live
  post-S11 check: current open cells include only
  `{"DESIGNER_ITSELF.envelope_growth"}` where this test checks live state, or
  use the central readiness exact assertion instead of duplicating it;
- change `summary["inventory_artifact_count"] == 18` to
  `summary["inventory_artifact_count"] >= 18`; exact post-S11 inventory `19`
  belongs in the readiness/S11 tests, not in S10's previous-slice test;
- change live `EXPECTED_LIVE_OPEN_CELLS` use from exact equality to a
  remaining-open/minimum assertion for `{"DESIGNER_ITSELF.envelope_growth"}`;
- keep assertions that the S10 manifest itself does not grant S11, S12, S13,
  S14, production, rich simulation, portfolio, or preference-learning authority.

The test name may stay as-is if the assertions clearly distinguish S10 manifest
state from live post-S11 readiness state.

- [ ] **Step 8: Run manifest/readiness and snapshot-tax tests**

Run:

```bash
cd /Users/deniskopylov/polisyos/policy-engine
uv run pytest \
  tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s2_design_search.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s3_substrate_acquisition.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s4_epistemic_regime.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s5_coupling_composition.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s6_blind_spot_firewalls.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s7_delegation.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s8_value_choice.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s9_projection_lowering.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s10_outcome_prediction.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s11_predictive_knowledge.py \
  -q
```

Expected after Task 5: cluster-map, S2-S10 previous-slice compatibility,
central readiness, and S11 manifest/readiness tests pass. No per-slice
repo-quality test should fail solely because live open-cell count moved from
`3` to `1`.

- [ ] **Step 9: Commit**

```bash
git add \
  architecture/policy_design_case/layer2_s11_predictive_knowledge_manifest.json \
  architecture/policy_design_case/cluster_ownership_map.toml \
  architecture/policy_design_case/layer2_artifact_traceability.toml \
  architecture/policy_design_case/inventory.json \
  tools/quality/validation/check_policy_design_case_layer2_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s2_design_search.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s3_substrate_acquisition.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s4_epistemic_regime.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s5_coupling_composition.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s6_blind_spot_firewalls.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s7_delegation.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s8_value_choice.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s9_projection_lowering.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s10_outcome_prediction.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s11_predictive_knowledge.py
git commit -m "chore: register layer2 s11 predictive knowledge maturity" \
  -m "Co-authored-by: Cursor <cursoragent@cursor.com>"
```

## Task 6: Repo-Quality Tests, Snapshots, And Burn-Down Confirmation

**Intent:** prove S11 is complete end to end and did not silently promote future
authority.

**Files:**

- Modify only files required by failing verification discovered in this task.

- [ ] **Step 1: Run targeted S11 suite**

Run:

```bash
cd /Users/deniskopylov/polisyos/policy-engine
uv run pytest \
  tests/unit/runtime/quality/test_layer2_s11_predictive_knowledge.py \
  tests/unit/runtime/quality/test_claim_registry.py \
  tests/unit/pdc/test_layer2_readiness_contracts.py \
  tests/unit/pdc/test_layer2_s2_design_search.py \
  tests/unit/runtime/quality/test_layer2_s4_epistemic_regime.py \
  tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py \
  tests/unit/runtime/quality/test_public_export.py \
  tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s2_design_search.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s3_substrate_acquisition.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s4_epistemic_regime.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s5_coupling_composition.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s6_blind_spot_firewalls.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s7_delegation.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s8_value_choice.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s9_projection_lowering.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s10_outcome_prediction.py \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s11_predictive_knowledge.py \
  -q
```

Expected: all targeted S11 tests pass.

- [ ] **Step 2: Run readiness and architecture checks**

Run:

```bash
cd /Users/deniskopylov/polisyos/policy-engine
uv run pytest \
  tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s2_design_search.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s3_substrate_acquisition.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s4_epistemic_regime.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s5_coupling_composition.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s6_blind_spot_firewalls.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s7_delegation.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s8_value_choice.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s9_projection_lowering.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s10_outcome_prediction.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s11_predictive_knowledge.py \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py \
  -q
uv run polisyos-tools architecture guardrails check
uv run --extra runtime --extra ml polisyos-tools runtime check-runtime-api-contract
```

Expected:

- S10 manifest-local assertions still report its pre-S11 expected open cells as
  `DESIGNER_ITSELF.envelope_growth`, `KNOWLEDGE.calibration`, and
  `KNOWLEDGE.ir_proof_carrying_analytics`, while live readiness reports the
  post-S11 current open-cell set.
- S11 readiness reports current open cells as only
  `DESIGNER_ITSELF.envelope_growth`.
- cluster-map open-cell closure tests pass after repointing negative controls
  to `DESIGNER_ITSELF.envelope_growth`.
- S2-S10 previous-slice repo-quality tests no longer fail on live open-count
  snapshot drift from `3` to `1`.
- architecture guardrails pass.
- runtime API contract passes and exports S11 runtime-quality contracts.

- [ ] **Step 3: Run backend verification**

Run:

```bash
cd /Users/deniskopylov/polisyos/policy-engine
python3 -m tools.cli workspace verify --backend-only
```

Expected: backend verification passes. If it fails for unrelated dirty-state
reasons, capture the failing command and rerun the smallest relevant test after
fixing only S11-owned paths.

- [ ] **Step 4: Burn-down confirmation**

Use `uv run pytest` or the readiness validator output to confirm:

- `ForecastSupport` and `ForecastCalibrationRecord` remain strict and exported
  from `polisyos.runtime.quality`.
- `PredictiveAxisCalibrationRecord`, `PredictiveAxisUpgradeRecord`,
  `ProofCarryingAnalyticsRecord`, and `S11PredictiveKnowledgeIntegrityReport`
  are strict and exported from `polisyos.runtime.quality`.
- `Layer2S11PredictivePostureInput` is strict and exported from `polisyos.pdc`.
- S11 consumes S6 firewall outputs and S10 forecast posture without rerunning
  those producers.
- B-side PDC search consumes injected S11 posture only and does not import the
  S11 runtime-quality producer.
- S2 replay digest, legacy `SearchLedger` defaults, persisted ledger round-trip,
  cluster-interface contracts, and handoff records all include S11 predictive
  posture refs without authority promotion.
- four matrix maturity-transition axes are either calibrated predictive or
  explicitly reverted to fail-closed.
- all 13 corpus cases carry exactly four S11 axis rows; `axis_count` and
  per-axis calibration denominator are `52`.
- `ACTOR.mandate_legitimacy` is not marked predictive.
- proof-carrying analytics bind to claim/comparison consumers and negative or
  unbound analytics do not raise evidence strength.
- per-axis calibration records explicit time roles and governed floor refs.
- stale/poor/out-of-scope calibration emits forecast-quality downgrade and
  epistemic-regime strategy constraint rows without rerunning S4 or S10.
- REVIEWER/EXPERT/MACHINE surfaces expose calibration/proof/residual
  limitations, and PUBLIC surfaces keep required S11 limitation summaries
  without promotion.
- `CROSS_CUTTING.method_infrastructure` is advanced only through consumed
  Foundry method/calibration/validation refs and is not counted as a reopened or
  reclosed open cell.
- negative-control false-clear counts are zero.
- governed Layer 2 inventory artifact count is `19`.
- cluster-map open cell count is `1`.
- remaining open cell is exactly `DESIGNER_ITSELF.envelope_growth`.
- no S12 envelope growth, S13 accountability, production authority, calibrated
  equilibrium prediction, rich simulation, portfolio optimization, preference
  learning, or S14 universality cell is marked implemented.

- [ ] **Step 5: Commit**

If Task 6 changes no files, do not create an empty commit. If verification
fixes changed files, inspect the exact paths first:

```bash
git status --short
```

Then stage only the S11-owned paths shown by that status output, using explicit
path arguments. The likely Task 6 paths are:

```bash
git add \
  src/polisyos/runtime/quality/layer2_predictive_knowledge.py \
  src/polisyos/runtime/quality/__init__.py \
  src/polisyos/pdc/_impl/layer2_design_search.py \
  src/polisyos/pdc/__init__.py \
  src/polisyos/runtime/quality/layer2_epistemic_regime.py \
  src/polisyos/runtime/quality/projection_semantics.py \
  src/polisyos/runtime/quality/public_export.py \
  tools/quality/validation/run_universal_outcome_corpus.py \
  tools/quality/validation/check_policy_design_case_layer2_readiness.py \
  architecture/policy_design_case/layer2_s11_predictive_knowledge_manifest.json \
  architecture/policy_design_case/cluster_ownership_map.toml \
  architecture/policy_design_case/layer2_artifact_traceability.toml \
  architecture/policy_design_case/inventory.json \
  tests/unit/runtime/quality/test_layer2_s11_predictive_knowledge.py \
  tests/unit/runtime/quality/test_claim_registry.py \
  tests/unit/pdc/test_layer2_readiness_contracts.py \
  tests/unit/pdc/test_layer2_s2_design_search.py \
  tests/unit/runtime/quality/test_layer2_s4_epistemic_regime.py \
  tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py \
  tests/unit/runtime/quality/test_public_export.py \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s10_outcome_prediction.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s11_predictive_knowledge.py
git commit -m "chore: verify layer2 s11 predictive knowledge progress" \
  -m "Co-authored-by: Cursor <cursoragent@cursor.com>"
```

## Task 7: Full S11 Verification Done When

S11 is complete only when all statements below are true:

- `PredictiveAxisCalibrationRecord`, `PredictiveAxisUpgradeRecord`,
  `ProofCarryingAnalyticsRecord`, and
  `S11PredictiveKnowledgeIntegrityReport` are strict, replayable, and exported
  from `polisyos.runtime.quality`.
- `Layer2S11PredictivePostureInput` is strict and exported from `polisyos.pdc`.
- S11 records DesignGraph/context refs through S10 posture: design graph,
  prediction context, policy context, candidate, baseline, alternatives,
  horizon, target outcomes, and jurisdiction/scope.
- S11 consumes S6 fail-closed records, S10 forecast support, calibration-ledger
  refs, and IR claim-bridge/proof refs without rerunning those producers.
- B-side PDC search consumes injected S11 posture only and does not import the
  S11 runtime-quality producer.
- S2 replay digest changes only when S11 predictive posture changes, and legacy
  `SearchLedger` payloads without S11 fields still validate with safe defaults.
- persisted S2 search ledgers round-trip S11 predictive refs through
  `persist_s2_design_record(...)` and `load_s2_search_ledger(...)`.
- S2 cluster-interface contracts and handoff records explicitly show
  `Layer2S11PredictivePostureInput` was consumed without recommendation or
  production authority.
- S11 preserves S6 axis rows, bridge consumer rows, constraint-store update
  refs, C3 authority-dimension refs, post-intervention DGP update refs, and
  system-dynamics handoff requirements.
- `maturity=predictive` is a derived cell qualifier over S6 floor status,
  per-axis calibration, and proof-carrying analytics, not a second source
  vocabulary.
- forecast tier remains owned by S10; S11 does not promote or rewrite S10
  forecast-tier authority.
- model confidence is independent of epistemic-regime label; regime alone
  cannot relax an S6 fail-closed floor.
- predictive support requires source contract, method validity, source/method
  lineage, effective independence refs, method-infrastructure refs,
  sensitivity, calibration refs, proof refs, and S6 floor refs.
- `state_capacity_feasibility` predictive support carries capacity-dimension
  grounding for the claimed administrative, fiscal, enforcement, delivery,
  coordination, or political-feasibility dimension.
- strategic-response predictive support requires dynamic/equilibrium checks or
  explicit caveat refs, plus Goodhart/Lucas/performativity/capture/gaming/
  adaptation/compliance-response channel rows, before governed relaxation is
  allowed.
- stale, failed, out-of-scope, or non-observable calibration reverts to S6
  fail-closed and is counted separately.
- stale, failed, out-of-scope, or non-observable calibration also emits
  forecast-quality downgrade and epistemic-regime strategy constraint rows
  without rerunning S4 or S10.
- historical priors outside current scope, policy context, or calibration window
  cannot improve current forecast or axis authority.
- unbound IR analytics cannot increase evidence strength or design-comparison
  ranking.
- negative certificates and blocking proof/composability statuses create
  blockers or limitations, not confidence upgrades.
- `ACTOR.mandate_legitimacy` is not marked predictive unless the matrix gains an
  S11 maturity-transition row.
- proof-carrying analytics cite claim ids, design-comparison refs, baseline and
  alternative refs, certificate refs, method requirement refs, uncertainty refs,
  and source/method lineage.
- recommendation/projection consumers inherit the weakest boundary among legal,
  data, method, participation, epistemic regime, coupling, prediction,
  welfare/value-choice, S11 predictive knowledge, state-capacity,
  reversibility/stakes, and strategic-response assumptions.
- all 13 corpus cases contain S11 blocks with exactly four axis rows each;
  corpus `axis_count` is `52`.
- negative-control false-clear counts are zero.
- `per_axis_predictive_calibration` floor is recorded from the governed floor
  table with numerator, denominator, pass rate, threshold, threshold ref, and
  status, and denominator is equal to the 52-row axis count.
- REVIEWER/EXPERT/MACHINE surfaces expose calibration/proof/residual
  limitations; PUBLIC surfaces preserve S11 limitation summaries when they
  constrain public-visible design status, without authority promotion.
- S11 manifest is registered in inventory; governed Layer 2 inventory artifact
  count is `19`.
- S10 repo-quality tests distinguish S10 manifest-local open count `3` from the
  post-S11 live readiness open count `1`.
- `CROSS_CUTTING.method_infrastructure` is advanced through consumed Foundry
  method/calibration/validation refs and is not counted as an open-cell closure.
- cluster-map open cell count is `1`.
- remaining open cell is exactly `DESIGNER_ITSELF.envelope_growth`.
- no S12 envelope growth, S13 accountability, production authority, calibrated
  equilibrium prediction, rich simulation, portfolio optimization, preference
  learning, or S14 universality cell is marked implemented.

## Commit Guidance

Use one logical commit per task:

- `test: add layer2 s11 predictive knowledge red tests`
- `feat: add layer2 s11 predictive knowledge contracts`
- `feat: wire layer2 s11 predictive posture into projections`
- `feat: classify layer2 s11 predictive knowledge coverage`
- `chore: register layer2 s11 predictive knowledge maturity`
- `chore: verify layer2 s11 predictive knowledge progress`

End commit messages with the repo's standard co-author trailer:

```text
Co-authored-by: Cursor <cursoragent@cursor.com>
```

Never use `git add .` for this plan. If `git status --short` shows unrelated
user changes, stage only the S11 paths listed in the relevant task or use
`git add -p`.
