---
title: PolicyOS Layer 2 S6 Thin Fail-Closed Blind-Spot Producers Implementation Plan
status: active
owner: team-runtime-quality
created: 2026-05-31
last_verified: null
stability: draft
roadmap: ../POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER2_IMPLEMENTATION_PLAN.md
slice: S6
slice_label: blind_spot_fail_closed_producers
source_design_doc: ../../../system-design-decisions/universal-policy-design-target-architecture-and-gap.md
cluster_ownership_map: ../../../../architecture/policy_design_case/cluster_ownership_map.toml
slice_cell_matrix: ../../../../architecture/policy_design_case/layer2_slice_cell_matrix.toml
failure_patterns: ../../../reference/policy-design-case-failure-patterns.md
depends_on: S5
---

# Layer 2 S6 Thin Fail-Closed Blind-Spot Producers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the five Layer 2 blind-spot cells as thin fail-closed A-side producers before B recommends, delegates, chooses values, or predicts. S6 does not make rich models; it makes absent or invalid blind-spot evidence visible, replayable, and authority-limiting.

**Architecture:** S6 adds gate-owned runtime-quality records for measurability adequacy, subject-granularity/aggregation validity, state-capacity feasibility, mandate/legitimacy, and strategic response. The producers emit `MeasurabilityAdequacyRecord`, `AggregationValidityRecord`, `CapacityFeasibilityRecord`, `MandateLegitimacyRecord`, `StrategicResponseRecord`, and `ClusterAuthorityDimensionRecord` artifacts, convert them into axis positions, firewall statuses, typed S2 constraint-store records, and C3 authority-dimension refs, inject a compact S6 posture into the S2/S4/S5 shadow loop as data, and persist top-level refs on `DesignRecordV0.ledger_refs`. The B loop consumes S6 posture and constraints; it may not self-clear proxy validity, aggregation scope, capacity feasibility, legitimacy, or strategic-response risk.

**Tech Stack:** Python 3.14, Pydantic v2 strict models through S0 `Layer2ReadinessModel`, S0 `AuthorityBoundary`, `AxisPositionDeclaration`, `AxisFirewallStatus`, S4 `EpistemicRegimeClaim` consumption constraints, S5 `CompositionReceipt` / `SystemDynamicsRequirement` posture, existing seeds in `runtime.quality.semantic_binding`, `runtime.quality.concept_spine`, `participation_requirement`, `runtime.quality.consultation`, `lex.interventions`, `foundry.methods.catalog.causal.strategic`, `foundry.methods.catalog.causal.policy_learning`, `foundry.methods.catalog.causal.dtr`, `scientist.policy_design.adversary`, `run_universal_outcome_corpus.py`, pytest, and existing `tools.quality.validation` validators.

---

## Scope

This task plan implements only roadmap slice S6.

It does **not** implement: S7 delegation contracts, S8 value-choice provenance or Pareto ranking, S10 outcome prediction, S11 predictive blind-spot models/calibration, production recommendation authority, public rollout authority, equilibrium simulation, portfolio optimization, S14 universality battery, or any relaxation from fail-closed to predictive maturity.

Cells moved by S6 (cluster cells, **closed as `maturity=fail_closed`**):

- `SYSTEM.measurability`: `producer_missing -> implemented` by wrapping semantic-binding seeds in construct-level measurability adequacy records.
- `SYSTEM.subject_granularity`: `producer_missing -> implemented` by wrapping concept-spine seeds in aggregation-validity records.
- `ACTOR.state_capacity_feasibility`: `producer_missing -> implemented` by adding a capacity-feasibility producer over actor, jurisdiction, instrument, and lifecycle context.
- `ACTOR.mandate_legitimacy`: `producer_missing -> implemented` by extending participation/consultation/legitimacy seeds into mandate records.
- `OTHER_AGENTS.strategic_response`: `implemented_but_not_orchestrated -> implemented` by wiring strategic/adversarial seeds into a response-model validity producer and post-intervention DGP handoff.

Open cell count delta:

- S0 baseline remains `17`.
- Current cluster-map open cell count becomes `5` after S6 (was `10` after S5; S6 closes five cells).
- S6 records the closed cells in its manifest and edits `cluster_ownership_map.toml` (flip all five `[cell.*]` entries to `implemented`, set owners, remove the matching `[open_cell_closure.*]` entries).
- The `fail_closed` maturity qualifier is recorded in the S6 manifest and already exists in `layer2_slice_cell_matrix.toml`; do not introduce a new ratchet state.

First proving ground:

- The standing 13 W12 real-producer corpus cases remain the proving ground.
- All 13 cases get an S6 blind-spot block with five per-axis records and expert/gold comparison.
- The negative controls `streetlight_proxy_laundering_probe`, `aggregation_scope_drift_probe`, `capacity_fantasy_probe`, `mandate_speculation_probe`, and `goodhart_post_intervention_probe` fail closed.
- `per_axis_fail_closed_negative_control_pass_rate` is computed from the five axis probes and must be `1.0`; `false_clear_count` must be `0`.
- The corpus summary records `case_count=13`, `axis_coverage_count=5`, `all_five_axes_covered=true`, and a per-case axis table.

S6 authority boundary:

- `authoritative_for`: `measurability_adequacy`, `aggregation_validity`, `capacity_feasibility`, `mandate_legitimacy`, `strategic_robustness`, `response_model_validity`, `fail_closed_axis_firewall`, `blind_spot_constraint_injection`, `c3_authority_dimension_input`, `per_axis_fail_closed_coverage_metric`.
- `may_not_use_for`: `production_claim_authority`, `rollout_authority`, `publication_authority`, `delegation_authority`, `value_choice_authority`, `outcome_prediction_authority`, `forecast_calibration_authority`, `rich_response_model_authority`, `capacity_transfer_authority`, `mandate_authority_from_llm`, `proxy_construct_equivalence_without_disclosure`, `aggregation_scope_transfer_without_validity`, `post_policy_effect_claim_without_response_model`.

## Architecture Decision

S6 producer contracts live in `polisyos.runtime.quality`, not in `pdc`, `scientist`, `foundry`, or `lex`.

Reason: the seeds live across several packages, but the fail-closed authority gate is a Policy Design Case runtime-quality concern. S6 should wrap existing seeds behind strict, replayable runtime-quality records, then expose only a compact posture, typed constraint updates, and C3 authority-dimension refs to the S2 narrow waist. That prevents generator-side laundering of proxy metrics, aggregation scope, actor capacity, mandate, or response-model assumptions.

Module placement:

- Create `src/polisyos/runtime/quality/design_axes/blind_spot_firewalls.py`.
- Modify `src/polisyos/runtime/quality/__init__.py` to export S6 contracts and producer functions.
- Modify `src/polisyos/pdc/_impl/layer2_readiness.py` only for the minimal shared envelope extension needed to carry C3 authority-dimension refs.
- Modify `src/polisyos/pdc/_impl/layer2_design_search.py` only to consume injected S6 data and project it. It must not import `runtime.quality.layer2_blind_spot_firewalls`.
- Modify `tools/quality/validation/run_universal_outcome_corpus.py` to produce S6 blocks for all 13 cases and inject the pinned case's S6 posture into the existing S2/S4/S5 shadow loop.

Import boundaries:

- `runtime.quality.layer2_blind_spot_firewalls` may import public S0 PDC contracts from `polisyos.pdc`, S4/S5 public runtime-quality types if needed, and seed packages by public facade.
- `pdc._impl.layer2_design_search` receives one PDC-local `Layer2S6BlindSpotPostureInput` DTO. It must not import the S6 runtime-quality producer or seed modules.
- The corpus route is the orchestrator: it calls existing S3/S4/S5 producers, calls S6 producers, then passes S4/S5/S6 posture into S2 for the pinned design case.
- If S6 creates a measurability or aggregation blocker for a claim whose S4 regime used absent S6 signals, S2 records a `regime_reissue_required` constraint and caps strategy; S6 itself does not rerun S4 or claim predictive calibration.

S6 public labels:

- `BlindSpotAxis`: `measurability`, `subject_granularity`, `state_capacity_feasibility`, `mandate_legitimacy`, `strategic_response`.
- `AxisFailClosedDisposition`: `pass`, `limit`, `block`.
- `ConstructMeasurabilityStatus`: `observed`, `proxy_only`, `qualitative`, `missing`.
- `ProxyValidityDisposition`: `valid_proxy`, `limited_proxy`, `invalid_proxy`, `not_applicable`.
- `AggregationClaimLevel`: `individual`, `household`, `firm`, `group`, `jurisdiction`, `system`.
- `AggregationValidityDisposition`: `valid`, `limited`, `block_ecological_error`, `block_simpson_risk`.
- `CapacityDimension`: `administrative`, `fiscal`, `enforcement`, `delivery`, `coordination`, `political_feasibility`, `institutional_credibility`, `participation_capacity`.
- `CapacityDisposition`: `grounded`, `capacity_building_required`, `limited`, `blocked`.
- `MandateBasis`: `statutory`, `delegated`, `participatory`, `affected_person`, `governance_board`, `absent`.
- `LegitimacyDisposition`: `grounded`, `limited`, `candidate_unverified`, `blocked`.
- `StrategicResponseChannel`: `goodhart`, `lucas_performativity`, `capture`, `sabotage`, `gaming`, `adaptation`, `compliance_response`.
- `StrategicResponseDisposition`: `modeled`, `limited`, `system_dynamics_required`, `blocked`.
- `BlindSpotOverallPosture`: `clear_fail_closed`, `limited`, `blocked`.

Fail-closed rule:

- Missing axis evidence cannot produce `pass`.
- Proxy-only measurability cannot satisfy the original value construct without proxy validity and value-loss disclosure.
- Evidence at one subject/granularity level cannot close a claim at another level without aggregation validity.
- Capacity copied from another jurisdiction or actor cannot ground implementability.
- LLM or reviewer text can propose a mandate hypothesis, but cannot authorize objectives or weights.
- A pre-policy effect cannot be projected unchanged into a post-policy world when Goodhart/Lucas/capture/gaming/adaptation risk is unresolved.

Consumer rule:

- S6 emits `AxisPositionDeclaration` and `AxisFirewallStatus` for all five cells.
- S6 emits `ClusterAuthorityDimensionRecord` rows for the canonical C3 authority dimensions: `measurability_adequacy`, `aggregation_validity`, `capacity_feasibility`, `mandate_legitimacy`, `strategic_robustness`, and `response_model_validity`.
- S2 records S6 ledger refs on `DesignRecordV0`, maps S6 constraint updates into typed `ConstraintStoreSnapshot` records, and stores C3 authority-dimension refs on `CertifiedOperationEnvelope`.
- S4/S5 strategy and composition remain unchanged unless S6 emits a blocking/limiting constraint; then S2 projects the limitation and routes refinement to acquire, reframe, capacity-build, mandate-review, or system-dynamics evidence.
- PUBLIC gets honest disclosures and limitations, not a machine-facing `BlindSpotOverallPosture` label; REVIEWER gets P18/P19/P21/P22/P24 status; EXPERT/MACHINE get full refs and per-axis rows.

Per-cell bridge contract:

- `SYSTEM.measurability` publishes to `KNOWLEDGE.epistemic_regime` as a regime-reissue or evidence-basis constraint, and to `ACTOR.value_choice_provenance` as an S8 pending value-choice gate.
- `SYSTEM.subject_granularity` publishes to `INTERVENTION.targeting` as a targeting-scope constraint, and to `KNOWLEDGE.epistemic_regime` as an evidence-scope constraint.
- `ACTOR.state_capacity_feasibility` publishes to `INTERVENTION.feasibility` and `DESIGNER_ITSELF.envelope_membership` as implementability and envelope constraints.
- `ACTOR.mandate_legitimacy` publishes to `ACTOR.value_choice_provenance`, `PUBLIC.legitimacy_disclosure`, and `INTERVENTION.design_candidate` as objective/weight closure constraints.
- `OTHER_AGENTS.strategic_response` publishes to `SYSTEM.post_intervention_dgp`, `SYSTEM.dynamics_feedback`, and `INTERVENTION.robustness` as response-model and system-dynamics constraints.
- If a downstream slice is not implemented yet, S6 still emits a typed pending handoff/constraint record; it does not silently treat the missing consumer as satisfied.

## Pattern Pass

Relevant failure patterns: `P01`, `P02`, `P03`, `P04`, `P05`, `P10`, `P12`, `P13`, `P15`, `P16`, `P17`, `P18`, `P19`, `P21`, `P22`, `P24`.

Existing risks found:

- `SYSTEM.measurability`, `SYSTEM.subject_granularity`, `ACTOR.state_capacity_feasibility`, and `ACTOR.mandate_legitimacy` are `producer_missing`; `OTHER_AGENTS.strategic_response` is `implemented_but_not_orchestrated`.
- Semantic binding and concept spine are real seeds, but they do not yet emit Policy Design Case authority records for measurability or aggregation.
- Strategic-response methods and adversarial seeds exist, but their response assumptions are not consumed by the S2/S5 composition surface or the C3 authority calculus.
- Participation and consultation packages can support legitimacy evidence, but no cluster producer currently decides whether objectives or social weights have mandate provenance.
- `ConstraintStoreSnapshot` currently carries only id lists, and `CertifiedOperationEnvelope` currently has no C3 authority-dimension ref field. S6 must minimally extend those shared contracts instead of pretending arbitrary S6 rows already fit.
- Without S6, B can optimize a measurable proxy, transport group evidence to an individual claim, assume capacity, infer legitimacy from prose, or keep pre-policy effects unchanged after incentive changes.

Correct pattern:

- A-side producers emit per-axis records first; B consumes a compact posture and cannot self-clear blind spots.
- Every axis has a typed record, producer, persisted ref, bridge/consumer effect, surface, semantic test, and negative control.
- S6 is `fail_closed`, not predictive: it blocks, limits, or creates obligations when evidence is absent. S11 is the later slice that may upgrade maturity to `predictive`.
- LLM output remains `candidate_unverified`, `limitation`, or `blocker` until a producer validates the axis.
- Strategic response routes back into `SYSTEM.post_intervention_dgp`, S5 dynamics/composition constraints, `INTERVENTION.robustness`, and C3 `strategic_robustness` / `response_model_validity` instead of remaining an isolated advisory note.
- Public projection must disclose unmeasured values, feasibility/legitimacy limits, and strategic-response caveats without exposing machine-only rows.
- Shared S2/S0 DTO changes remain narrow: add typed constraint records to `ConstraintStoreSnapshot` and C3 dimension refs to `CertifiedOperationEnvelope`; keep full S6 details in runtime-quality artifacts and EXPERT/MACHINE projections.

Missing capability labels before implementation:

- `producer_missing` for `SYSTEM.measurability`, `SYSTEM.subject_granularity`, `ACTOR.state_capacity_feasibility`, and `ACTOR.mandate_legitimacy`.
- `bridge_missing` for `OTHER_AGENTS.strategic_response`.
- `artifact_missing` for the six S6 named artifacts and their replayable refs.
- `consumer_missing` for typed S2 constraint records, C3 envelope refs, per-cell bridge consumers, and S4/S5 limitation handoffs.
- `surface_missing` for all audience projections.
- `semantic_test_missing` for P18/P19/P21/P22/P24 negative controls and 13-case blind-spot coverage.
- `verification_missing` for readiness, cluster map, inventory, corpus, and regression gates.

Acceptance signal:

- Five S6 cells move to `implemented` with manifest maturity `fail_closed`; cluster-map open cell count drops from `10` to `5`.
- All six S6 named artifacts are strict, replayable, and exported from `runtime.quality`.
- The S2 narrow waist consumes `Layer2S6BlindSpotPostureInput`, persists refs, writes typed constraint-store records and C3 envelope refs, and renders S6 posture across all four audiences without importing the S6 producer.
- All five negative controls fail closed and the S6 floor metric is `1.0`.
- All 13 corpus cases contain S6 blocks, per-axis table rows, and gold comparisons.
- Production-posture outcomes and closeout honesty are unchanged; S6 affects shadow/governed routing and authority limitations only.

## Code-Grounded Reality Check

Existing strengths to reuse:

- `Layer2ReadinessModel`, `AuthorityBoundary`, `AxisPositionDeclaration`, and `AxisFirewallStatus` already provide strict/frozen PDC records.
- S2 already has `ConstraintStoreSnapshot`, `ClusterInterfaceContract`, `ClusterHandoffRecord`, `Layer2S2DesignSearchRun`, and the S5 `composition_posture` injection path. S6 should extend these helpers, not add a parallel B-side bridge system.
- S4 and S5 already established the A-gate-owned pattern: runtime-quality classifies, W12.D injects a PDC-local DTO into S2, and S2 records refs without importing the classifier.
- `runtime.quality.semantic_binding` already exports `SemanticBindingLedger`, `ClaimBindingRecord`, `CoverageBinding`, `SourceFacetBinding`, `build_semantic_binding_ledger`, and `evaluate_semantic_binding_ledger`; S6 measurability should consume/wrap these instead of inventing a new semantic ledger.
- `runtime.quality.concept_spine` already models concept, jurisdiction, population, time, unit, scope, `ProducerHandshakeBinding`, and bridge authority records useful for aggregation validity and pending-consumer rows.
- `participation_requirement` already has strict participation requirement/evaluation records, `claim_use_allowed`, public projection rows, deficit records, and an explicit `llm_speculation_not_participation` blocker. S6 mandate should wrap that matrix instead of duplicating participation logic.
- `runtime.quality.consultation` already validates consultation records and high-severity unresolved objection blockers; S6 mandate should consume these legitimacy validations.
- `lex.interventions`, `scientist.methods.causal.readiness.StrategicResponseRunner`, `foundry.methods.catalog.causal.strategic`, `policy_learning`, `dtr`, and `ir.analytics.strategic` contain strategic-response specs, solver outputs, persisted bundle refs, and channel vocabulary. S6 should treat them as evidence sources when present and fail closed when absent.
- `run_universal_outcome_corpus.py` already emits S4 and S5 per-case blocks, computes summaries, and injects posture into S2 for the pinned case.

Weak spots that make S6 larger than a contract-only patch:

- Five axes must be produced together because the floor governance revision rule is `all_five_blind_spot_axes_required`.
- `ConstraintStoreSnapshot` currently has only `constraint_ids`, `hard_constraint_ids`, and `governance_owned_gap_ids`; Task 3 must add a typed bounded constraint-entry list or S6 constraints will be projection-only.
- `CertifiedOperationEnvelope` currently has no C3 authority-dimension ref field; Task 3 must add a minimal bounded ref list or C3 coverage will be an artifact without a consumer.
- S6 must write axis-level records, compact aggregate posture, per-cell bridge rows, typed constraint entries, and C3 authority-dimension refs; otherwise S2 projections either become too thin (P03) or too broad (P13).
- `DesignRecordV0.ledger_refs` has `max_length=40`. Store one ref per top-level S6 record plus compact dimension/report refs; do not ledger every row.
- `run_universal_outcome_corpus.py` is a large single integration route. Extend the existing S4/S5 pattern in place and keep helpers small; do not refactor the route while adding S6.
- PUBLIC projection needs honest text for unmeasured values and feasibility/legitimacy limits. Machine-only details belong in EXPERT/MACHINE.
- S6 must not update `layer2_slice_cell_matrix.toml`; the S0 assignment already exists. It may update live readiness snapshots and cluster-map state.
- S6 must not change `layer2_floor_governance.toml`; `s6_fail_closed_coverage` already exists.
- Capacity is the thinnest area: there are feasibility and institutional provenance seeds, but no governed state-capacity producer. Expect more new S6 logic here than for participation, semantic binding, concept spine, or strategic response.

Scope correction from this code pass:

- Top-level S6 artifacts remain the roadmap/traceability set: `CapacityFeasibilityRecord`, `MandateLegitimacyRecord`, `MeasurabilityAdequacyRecord`, `AggregationValidityRecord`, `StrategicResponseRecord`, and `ClusterAuthorityDimensionRecord`.
- Nested row/check DTOs are exported for tests and projection clarity, but are not new traceability rows or independent manifest `required_artifacts`.
- `Layer2S6BlindSpotPostureInput` lives in `pdc._impl.layer2_design_search` as a B-side input DTO; it is not a runtime-quality artifact.
- `BlindSpotBridgeConsumerRecord` and `BlindSpotConstraintStoreUpdate` are S6 report rows that map into existing PDC `ClusterInterfaceContract`, `ClusterHandoffRecord`, and typed `ConstraintStoreSnapshot` entries; they are not replacement bridge infrastructure.
- S6 must not run a full strategic equilibrium/simulation by default. It consumes existing strategic bundle refs or channel evidence when supplied, and otherwise records `limited`/`blocked` fail-closed posture with a DGP/system-dynamics handoff.

## Source Of Truth

| Concern | Source |
| --- | --- |
| Roadmap closure contract | `docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER2_IMPLEMENTATION_PLAN.md#s6--thin-fail-closed-blind-spot-producers-a-completeness-before-b-recommends` |
| Failure patterns | `docs/reference/policy-design-case-failure-patterns.md` (`P18`, `P19`, `P21`, `P22`, `P24`) |
| Slice-cell assignments | `architecture/policy_design_case/layer2_slice_cell_matrix.toml` |
| Cluster closure contracts | `architecture/policy_design_case/cluster_ownership_map.toml` (`SYSTEM.measurability`, `SYSTEM.subject_granularity`, `ACTOR.state_capacity_feasibility`, `ACTOR.mandate_legitimacy`, `OTHER_AGENTS.strategic_response`) |
| Floor governance | `architecture/policy_design_case/layer2_floor_governance.toml#s6_fail_closed_coverage` |
| Artifact traceability | `architecture/policy_design_case/layer2_artifact_traceability.toml` (all six S6 named artifacts already listed) |
| S0 public contracts | `src/polisyos/pdc/__init__.py`, `src/polisyos/pdc/_impl/layer2_readiness.py` |
| S2 loop and projection narrow waist | `src/polisyos/pdc/_impl/layer2_design_search.py` |
| S4 regime constraints | `src/polisyos/runtime/quality/design_axes/epistemic_regime.py` |
| S5 composition/dynamics constraints | `src/polisyos/runtime/quality/design_axes/coupling_composition.py` |
| Measurability seed | `src/polisyos/runtime/quality/semantic_binding.py` |
| Aggregation seed | `src/polisyos/runtime/quality/concept_spine.py` |
| Capacity/feasibility seeds | `src/polisyos/runtime/quality/institutional_provenance.py`, `src/polisyos/scientist/policy_design/output.py`, `src/polisyos/scientist/agent/feasibility.py` |
| Mandate/legitimacy seeds | `src/polisyos/participation_requirement/`, `src/polisyos/runtime/quality/consultation.py`, `src/polisyos/lex/` |
| Strategic-response seeds | `src/polisyos/lex/interventions.py`, `src/polisyos/scientist/methods/causal/readiness.py`, `src/polisyos/foundry/methods/catalog/causal/strategic.py`, `src/polisyos/foundry/methods/catalog/causal/policy_learning.py`, `src/polisyos/foundry/methods/catalog/causal/dtr.py`, `src/polisyos/ir/analytics/strategic.py`, `src/polisyos/scientist/policy_design/adversary.py` |
| Canonical corpus route | `tools/quality/validation/run_universal_outcome_corpus.py` |

## Files

Create:

- `src/polisyos/runtime/quality/design_axes/blind_spot_firewalls.py`
- `architecture/policy_design_case/layer2_s6_blind_spot_firewalls_manifest.json`
- `tests/unit/runtime/quality/test_layer2_s6_blind_spot_firewalls.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s6_blind_spot_firewalls.py`
- `tests/fixtures/layer2/s6/streetlight_proxy_laundering_probe.json`
- `tests/fixtures/layer2/s6/aggregation_scope_drift_probe.json`
- `tests/fixtures/layer2/s6/capacity_fantasy_probe.json`
- `tests/fixtures/layer2/s6/mandate_speculation_probe.json`
- `tests/fixtures/layer2/s6/goodhart_post_intervention_probe.json`
- `tests/fixtures/layer2/s6/s6_blind_spot_case_signals.json`
- `tests/fixtures/layer2/s6/s6_blind_spot_expert_labels.json`

Modify:

- `src/polisyos/runtime/quality/__init__.py`
- `src/polisyos/pdc/__init__.py`
- `src/polisyos/pdc/_impl/layer2_readiness.py`
- `src/polisyos/pdc/_impl/layer2_design_search.py`
- `tests/unit/pdc/test_layer2_readiness_contracts.py`
- `tests/unit/pdc/test_layer2_s2_design_search.py`
- `tools/quality/validation/run_universal_outcome_corpus.py`
- `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`
- `tools/quality/validation/check_policy_design_case_layer2_readiness.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s2_design_search.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s3_substrate_acquisition.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s4_epistemic_regime.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s5_coupling_composition.py`
- `tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py`
- `architecture/policy_design_case/cluster_ownership_map.toml`
- `architecture/policy_design_case/inventory.json`

Do not modify:

- `architecture/policy_design_case/layer2_floor_governance.toml` (`s6_fail_closed_coverage` already exists).
- `architecture/policy_design_case/layer2_slice_cell_matrix.toml` (S6 assignments and maturity already exist).
- `architecture/policy_design_case/layer2_dependency_dag.json`.
- S7+ cells, S8 value-choice provenance, S10/S11 predictive/calibration artifacts, production authority, or sealed S14 battery fixtures.

---

## Task 1: Red-First S6 Semantic And Negative Tests

**Files:**

- Create: `tests/unit/runtime/quality/test_layer2_s6_blind_spot_firewalls.py`
- Create: the five negative-control fixtures under `tests/fixtures/layer2/s6/`
- Create: `src/polisyos/runtime/quality/design_axes/blind_spot_firewalls.py` (skeleton import target only)

- [ ] **Step 1: Add P18/P19/P21/P22/P24 negative-control fixtures**

Create fixtures with `schema_version`, `case_id`, `expected_error`, `axis`, `design_ref`, relevant construct/population/jurisdiction/actor fields, producer evidence refs, and expected fail-closed disposition:

- `streetlight_proxy_laundering_probe.json`
  - Axis: `SYSTEM.measurability`
  - Expected error: `P18StreetlightMeasurabilityError`
  - Scenario: the design optimizes an observable administrative throughput proxy while the objective also names dignity/trust/access fairness as unmeasured constructs.
  - Required result: proxy-only rows cannot satisfy the original value; value-loss disclosure and limitation/blocker are mandatory.
- `aggregation_scope_drift_probe.json`
  - Axis: `SYSTEM.subject_granularity`
  - Expected error: `P19AggregationLaunderingError`
  - Scenario: jurisdiction-level averages hide subgroup harm while the design makes individual/firm targeting claims.
  - Required result: ecological-error or Simpson-risk blocker/limitation is emitted.
- `capacity_fantasy_probe.json`
  - Axis: `ACTOR.state_capacity_feasibility`
  - Expected error: `P21CapacityFeasibilityError`
  - Scenario: high-capacity assumptions are copied from a different jurisdiction/actor into a lower-capacity implementation context.
  - Required result: implementability is blocked or converted to a capacity-building obligation.
- `mandate_speculation_probe.json`
  - Axis: `ACTOR.mandate_legitimacy`
  - Expected error: `P22MandateLegitimacyError`
  - Scenario: LLM text asserts affected-person mandate and objective authority without participation/legal/governance provenance.
  - Required result: mandate remains `candidate_unverified` or blocker; objectives/social weights cannot close.
- `goodhart_post_intervention_probe.json`
  - Axis: `OTHER_AGENTS.strategic_response`
  - Expected error: `P24StrategicResponseError`
  - Scenario: an incentive target is susceptible to gaming and capture, but the design projects pre-policy effect unchanged.
  - Required result: response risk and post-intervention DGP update are emitted; unchanged effect claim is blocked/limited and routed to S5 dynamics if needed.

- [ ] **Step 2: Add red unit tests**

Create these tests in `tests/unit/runtime/quality/test_layer2_s6_blind_spot_firewalls.py`:

- `test_proxy_only_construct_records_value_loss_and_blocks_streetlight_pass`
- `test_jurisdiction_average_hiding_subgroup_harm_fails_p19`
- `test_capacity_assumption_copied_across_jurisdictions_fails_p21`
- `test_llm_participation_speculation_cannot_authorize_mandate`
- `test_goodhart_probe_updates_post_intervention_dgp_and_blocks_unchanged_effect`
- `test_absent_axis_evidence_defaults_to_limit_or_block_not_pass`
- `test_cluster_authority_dimension_records_cover_all_five_axes`
- `test_s6_records_are_strict_frozen_and_replayable`
- `test_s6_report_exports_axis_positions_firewalls_and_refs`
- `test_s6_fail_closed_coverage_counts_all_five_negative_controls`

The first red run should fail on missing imports/types, not on skipped tests.

Run:

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer2_s6_blind_spot_firewalls.py -q
```

Expected red:

```text
ModuleNotFoundError or ImportError for polisyos.runtime.quality.design_axes.blind_spot_firewalls
```

- [ ] **Step 3: Keep the skeleton empty enough to stay red**

Create only a module docstring if needed. Do not implement DTOs or pass logic in Task 1.

## Task 2: Contracts, Producers, Cluster-Axis Records, And P18/P19/P21/P22/P24 Firewalls

**Files:**

- Modify: `src/polisyos/runtime/quality/design_axes/blind_spot_firewalls.py`
- Modify: `src/polisyos/runtime/quality/__init__.py`
- Modify: `tests/unit/runtime/quality/test_layer2_s6_blind_spot_firewalls.py`

- [ ] **Step 1: Implement strict S6 public DTOs**

In `src/polisyos/runtime/quality/design_axes/blind_spot_firewalls.py`, define:

- Schema constant: `LAYER2_S6_BLIND_SPOT_FIREWALLS_SCHEMA_VERSION = "policyos.policy_design_case.layer2_s6_blind_spot_firewalls.v1"`
- Errors:
  - `P18StreetlightMeasurabilityError`
  - `P19AggregationLaunderingError`
  - `P21CapacityFeasibilityError`
  - `P22MandateLegitimacyError`
  - `P24StrategicResponseError`
- Literals listed in "S6 public labels".
- Top-level traceability artifacts:
  - `MeasurabilityAdequacyRecord`
  - `AggregationValidityRecord`
  - `CapacityFeasibilityRecord`
  - `MandateLegitimacyRecord`
  - `StrategicResponseRecord`
  - `ClusterAuthorityDimensionRecord`
- Exported nested records:
  - `ConstructMeasurabilityRow`
  - `ProxyValidityRecord`
  - `ValueLossDisclosure`
  - `AggregationScopeRow`
  - `CapacityDimensionAssessment`
  - `CapacityBuildingObligation`
  - `MandateSourceRecord`
  - `ParticipationProvenanceRow`
  - `StrategicResponseChannelAssessment`
  - `PostInterventionDGPUpdate`
  - `BlindSpotBridgeConsumerRecord`
  - `BlindSpotConstraintStoreUpdate`
  - `BlindSpotFirewallReport`

All public DTOs must inherit `Layer2ReadinessModel`, use bounded lists, carry `schema_version`, `rule_version_ref`, `authority_boundary` where crossing workflow boundaries, and reject extra fields.

- [ ] **Step 2: Implement thin fail-closed producers**

Add deterministic producer functions with these public signatures:

- `evaluate_measurability_adequacy(*, case_id: str, design_ref: str, construct_rows: Sequence[Mapping[str, object]], semantic_binding_ledger: SemanticBindingLedger | Mapping[str, object] | None = None, rule_version_ref: str, authority_boundary: AuthorityBoundary | None = None) -> MeasurabilityAdequacyRecord`
- `evaluate_aggregation_validity(*, case_id: str, design_ref: str, claim_scope: AggregationClaimLevel, evidence_scope: AggregationClaimLevel, aggregation_rows: Sequence[Mapping[str, object]], concept_spine_carrier: Mapping[str, object] | None = None, rule_version_ref: str, authority_boundary: AuthorityBoundary | None = None) -> AggregationValidityRecord`
- `evaluate_capacity_feasibility(*, case_id: str, design_ref: str, actor_ref: str, jurisdiction_ref: str, instrument_ref: str, capacity_dimensions: Sequence[Mapping[str, object]], rule_version_ref: str, authority_boundary: AuthorityBoundary | None = None) -> CapacityFeasibilityRecord`
- `evaluate_mandate_legitimacy(*, case_id: str, design_ref: str, objective_refs: Sequence[str], mandate_sources: Sequence[Mapping[str, object]], participation_evaluations: Sequence[Mapping[str, object]] = (), consultation_validations: Sequence[Mapping[str, object]] = (), rule_version_ref: str, authority_boundary: AuthorityBoundary | None = None) -> MandateLegitimacyRecord`
- `evaluate_strategic_response(*, case_id: str, design_ref: str, response_channels: Sequence[Mapping[str, object]], pre_policy_effect_refs: Sequence[str] = (), s5_composition_posture: Mapping[str, object] | None = None, strategic_response_entries: Sequence[Mapping[str, object]] = (), rule_version_ref: str, authority_boundary: AuthorityBoundary | None = None) -> StrategicResponseRecord`
- `build_s6_blind_spot_firewall_report(*, case_id: str, design_ref: str, measurability: MeasurabilityAdequacyRecord, aggregation: AggregationValidityRecord, capacity: CapacityFeasibilityRecord, mandate: MandateLegitimacyRecord, strategic_response: StrategicResponseRecord, rule_version_ref: str) -> BlindSpotFirewallReport`
- `s6_firewall_report_to_axis_positions(report: BlindSpotFirewallReport) -> tuple[list[AxisPositionDeclaration], list[AxisFirewallStatus]]`
- `s6_firewall_report_to_constraint_store_updates(report: BlindSpotFirewallReport) -> list[BlindSpotConstraintStoreUpdate]`
- `s6_firewall_report_to_c3_dimension_records(report: BlindSpotFirewallReport) -> list[ClusterAuthorityDimensionRecord]`
- `s6_fail_closed_coverage(probe_results: Sequence[Mapping[str, object]]) -> dict[str, object]`

Import `Mapping` and `Sequence` from `collections.abc`; import `AxisPositionDeclaration`, `AxisFirewallStatus`, and `AuthorityBoundary` from the public `polisyos.pdc` facade.

Required behavior:

- Missing evidence for any axis returns `limit` or `block`, never `pass`.
- Measurability consumes existing `SemanticBindingLedger`, `ClaimBindingRecord`, `CoverageBinding`, and `SourceFacetBinding` payloads when available; it does not create a second semantic-binding system.
- Aggregation consumes existing concept-spine scope/population/geography/unit/time records and producer handshakes when available; it does not create a parallel concept-spine carrier.
- Mandate consumes `participation_requirement` evaluations and `runtime.quality.consultation` validation outputs when available; it preserves `llm_speculation_not_participation` and unresolved-objection blockers.
- Capacity consumes existing feasibility/provenance refs when supplied, but because no governed state-capacity producer exists yet, absent dimension evidence defaults to `limited`/`blocked` plus a capacity-building obligation.
- Strategic response consumes `StrategicResponseSpecsBundle`, `StrategicResponseEntry`, strategic bundle refs, or channel evidence when supplied; it must not run rich equilibrium/simulation work just to clear S6.
- Each top-level record has a stable replay ref:
  - `pdc://layer2/s6/{case_id}/measurability-adequacy`
  - `pdc://layer2/s6/{case_id}/aggregation-validity`
  - `pdc://layer2/s6/{case_id}/capacity-feasibility`
  - `pdc://layer2/s6/{case_id}/mandate-legitimacy`
  - `pdc://layer2/s6/{case_id}/strategic-response`
  - `pdc://layer2/s6/{case_id}/cluster-authority-dimensions`
- Each `ClusterAuthorityDimensionRecord` binds one `CLUSTER.axis` cell to its producer ref, firewall pattern id, disposition, maturity `fail_closed`, and authority boundary.
- `ClusterAuthorityDimensionRecord` rows use the canonical C3 authority dimensions from the architecture doc and cluster map, including `strategic_robustness` and `response_model_validity` for `OTHER_AGENTS.strategic_response`; do not invent `strategic_response_validity`.
- Each axis emits `BlindSpotBridgeConsumerRecord` report rows for the bridge contract above, including pending handoffs to S8/S10/S11-owned consumers where those slices are not yet implemented. These rows later map to existing PDC `ClusterInterfaceContract` / `ClusterHandoffRecord` records.
- Constraint-store updates must be replayable and typed: blocked axis -> `block_candidate` or `acquire/reframe`; limited axis -> scoped limitation; pending downstream axis -> explicit `pending_consumer_constraint`.
- `StrategicResponseRecord` consumes the S5 coupling/composition posture when present and emits `post_intervention_dgp_update_ref` plus `system_dynamics_handoff_required` when response risk changes system dynamics.

- [ ] **Step 3: Enforce P18/P19/P21/P22/P24 negative controls**

Implement producer-side checks so each fixture fails closed:

- P18: raise/record `P18StreetlightMeasurabilityError` when `declared_measurability_pass=true` but a target construct is `proxy_only`, `qualitative`, or `missing` without value-loss disclosure.
- P19: raise/record `P19AggregationLaunderingError` when evidence scope is coarser/finer than claim scope and no aggregation validity proof exists.
- P21: raise/record `P21CapacityFeasibilityError` when implementation requires a capacity dimension marked absent/unsupported and no capacity-building obligation is recorded.
- P22: raise/record `P22MandateLegitimacyError` when objective/weight authority depends on LLM or prose without mandate provenance.
- P24: raise/record `P24StrategicResponseError` when pre-policy effect is projected unchanged despite unresolved response channels.

- [ ] **Step 4: Export from `runtime.quality`**

Update `src/polisyos/runtime/quality/__init__.py` to export all six top-level artifacts, nested test-visible records, errors, and producer functions.

Run:

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer2_s6_blind_spot_firewalls.py -q
uv run ruff check src/polisyos/runtime/quality/design_axes/blind_spot_firewalls.py tests/unit/runtime/quality/test_layer2_s6_blind_spot_firewalls.py
```

Expected:

```text
S6 unit tests pass.
Ruff passes.
```

## Task 3: Inject S6 Fail-Closed Posture Into The B-Side Shadow Loop

**Files:**

- Modify: `src/polisyos/pdc/_impl/layer2_readiness.py`
- Modify: `src/polisyos/pdc/_impl/layer2_design_search.py`
- Modify: `src/polisyos/pdc/__init__.py`
- Modify: `tests/unit/pdc/test_layer2_readiness_contracts.py`
- Modify: `tests/unit/pdc/test_layer2_s2_design_search.py`

- [ ] **Step 1: Add minimal shared S0/S2 carrier extensions**

In `src/polisyos/pdc/_impl/layer2_readiness.py`, extend `CertifiedOperationEnvelope` with:

- `cluster_authority_dimension_refs: list[str] = Field(default_factory=list, max_length=40)`

This is an internal PDC contract extension only. Do not add the field to runtime HTTP DTOs or public OpenAPI surfaces; Task 7 must keep `check-runtime-api-contract` green without broadening runtime API.

In `src/polisyos/pdc/_impl/layer2_design_search.py`, add a strict PDC-local `ConstraintStoreEntry(Layer2ReadinessModel)` and extend `ConstraintStoreSnapshot` with:

- `constraint_records: list[ConstraintStoreEntry] = Field(default_factory=list, max_length=40)`

Required `ConstraintStoreEntry` fields:

- `schema_version: str = S2_DESIGN_SEARCH_SCHEMA_VERSION`
- `constraint_id: str`
- `cell_ref: str`
- `status: Literal["pass", "warn", "limit", "block"]`
- `source_ref: str`
- `consumer_ref: str`
- `refinement_route: Literal["none", "acquire", "reframe", "human_decision", "block_candidate", "pending_consumer_constraint"]`
- `evidence_refs: list[str] = Field(default_factory=list, max_length=20)`
- `reason: str`
- `rule_version_ref: str`

Keep the existing `constraint_ids`, `hard_constraint_ids`, and `governance_owned_gap_ids` fields for compatibility.

Add/extend tests:

- `test_certified_operation_envelope_carries_cluster_authority_dimension_refs`
- `test_constraint_store_snapshot_carries_typed_constraint_records`
- `test_constraint_store_snapshot_rejects_extra_constraint_fields`

- [ ] **Step 2: Add PDC-local input DTO**

In `src/polisyos/pdc/_impl/layer2_design_search.py`, define `Layer2S6BlindSpotPostureInput(Layer2ReadinessModel)` with:

- `overall_posture: Literal["clear_fail_closed", "limited", "blocked"]`
- `maturity: Literal["fail_closed"] = "fail_closed"`
- `measurability_record_ref: str`
- `aggregation_validity_record_ref: str`
- `capacity_feasibility_record_ref: str`
- `mandate_legitimacy_record_ref: str`
- `strategic_response_record_ref: str`
- `cluster_authority_dimension_refs: list[str]`
- `bridge_consumer_rows: list[dict[str, object]]`
- `constraint_store_updates: list[dict[str, object]]` (mapped into typed `ConstraintStoreEntry` records inside S2)
- `c3_authority_dimension_rows: list[dict[str, object]]`
- `axis_rows: list[dict[str, object]]`
- `blocking_axis_refs: list[str]`
- `limiting_axis_refs: list[str]`
- `post_intervention_dgp_update_ref: str | None`
- `system_dynamics_handoff_required: bool`
- `regime_reissue_required: bool`
- `limitation_summary: str`
- `false_clear_penalty: float`

This DTO is the only S6 object the B loop understands.

Export `Layer2S6BlindSpotPostureInput` and `ConstraintStoreEntry` from `src/polisyos/pdc/__init__.py` and add both names to `__all__`.

- [ ] **Step 3: Record S6 posture on `DesignRecordV0`**

Extend `run_s2_shadow_design_loop` and internal helpers to accept `blind_spot_posture: Layer2S6BlindSpotPostureInput | None`.

When present:

- Add five `AxisPositionDeclaration` rows for the S6 cells.
- Add five `AxisFirewallStatus` rows with pattern ids `P18`, `P19`, `P21`, `P22`, `P24`.
- Add all six top-level S6 refs to `DesignRecordV0.ledger_refs`.
- Add S6 updates to `ConstraintStoreSnapshot.constraint_records`, not only projection text.
- Add S6 `cluster_authority_dimension_refs` to `CertifiedOperationEnvelope.cluster_authority_dimension_refs`, and ensure limit/block dimensions prevent downstream closeout authority composition.
- Add cluster interface contracts / handoff records using existing `ClusterInterfaceContract` and `ClusterHandoffRecord`, showing S2 consumed `Layer2S6BlindSpotPostureInput`, including per-cell bridge rows for future consumers.
- If `overall_posture == "blocked"`, route refinement to `block_candidate`, `acquire`, `reframe`, or `human_decision`, not point optimization.
- If `regime_reissue_required`, cap S4-derived strategy in the projection with an explicit limitation until S4 is rerun with S6 evidence.
- If `system_dynamics_handoff_required`, keep S5 dynamics requirement visible and do not project unchanged post-policy effects.

- [ ] **Step 4: Add four-audience S6 projection**

Extend `project_s2_design_search`:

- PUBLIC: concise disclosures/limitations for unmeasured values, capacity/mandate, aggregation, and response risk; do not expose `BlindSpotOverallPosture` as a user-facing product label.
- REVIEWER: per-axis firewall status, P18/P19/P21/P22/P24 pattern ids, overall disposition, and S2 refinement route.
- EXPERT: S6 refs, axis rows, proxy validity/value-loss rows, aggregation scope rows, capacity dimensions, mandate provenance, strategic-response channels, DGP update, false-clear penalty.
- MACHINE: same as EXPERT plus normalized row payloads and all ledger refs for replay.

Add `assert_s2_public_projection_has_blind_spot_disclosure(projection)` and call it for PUBLIC when S6 posture is present.

- [ ] **Step 5: Add PDC import-boundary and behavior tests**

In `tests/unit/pdc/test_layer2_s2_design_search.py`, add:

- `test_injected_s6_blind_spot_posture_recorded_without_b_side_self_classification`
- `test_four_audience_surface_renders_s6_fail_closed_posture`
- `test_public_projection_discloses_unmeasured_values_and_feasibility_limits`
- `test_s6_blocking_axis_routes_refinement_to_reframe_or_acquire_not_point_optimize`
- `test_s6_constraints_written_to_constraint_store_snapshot`
- `test_s6_constraint_records_are_typed_not_projection_only`
- `test_s6_cluster_authority_dimension_refs_enter_certified_envelope`
- `test_blocking_s6_dimension_prevents_closeout_authority_composition`
- `test_s6_regime_reissue_constraint_caps_strategy_without_rerunning_s4`
- `test_pdc_exports_s6_posture_and_constraint_store_entry`
- `test_pdc_does_not_import_layer2_blind_spot_firewalls`

Run:

```bash
cd policy-engine
uv run pytest tests/unit/pdc/test_layer2_readiness_contracts.py \
  tests/unit/pdc/test_layer2_s2_design_search.py -q
rg -n "layer2_blind_spot_firewalls|evaluate_measurability|evaluate_aggregation|evaluate_capacity|evaluate_mandate|evaluate_strategic_response" src/polisyos/pdc/_impl/layer2_design_search.py
```

Expected:

```text
S2 and readiness-contract tests pass.
The rg command returns no matches.
```

## Task 4: Canonical Corpus Route Wiring - 13-Case S6 Blind-Spot Coverage

**Files:**

- Create: `tests/fixtures/layer2/s6/s6_blind_spot_case_signals.json`
- Create: `tests/fixtures/layer2/s6/s6_blind_spot_expert_labels.json`
- Modify: `tools/quality/validation/run_universal_outcome_corpus.py`
- Modify: `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`

- [ ] **Step 1: Add 13-case S6 signal and gold fixtures**

`s6_blind_spot_case_signals.json` must cover every canonical W12 case id and include:

- objective/construct refs for measurability;
- proxy rows and value-loss notes;
- claim scope and evidence granularity;
- actor/jurisdiction/instrument/lifecycle capacity dimensions;
- mandate source and participation provenance;
- strategic-response channels, pre-policy effect refs, post-intervention DGP assumptions;
- bridge consumer expectations for each axis, including pending downstream consumers;
- expected S2 constraint-store updates, typed `ConstraintStoreEntry` rows after mapping, and C3 authority-dimension refs/rows;
- optional S5 coupling/composition refs used by strategic response.

`s6_blind_spot_expert_labels.json` must cover every canonical W12 case id and include:

- `expected_measurability_disposition`
- `expected_aggregation_disposition`
- `expected_capacity_disposition`
- `expected_mandate_disposition`
- `expected_strategic_response_disposition`
- `expected_overall_posture`
- `expected_blocking_axis_refs`
- `expected_limiting_axis_refs`
- `expected_bridge_consumer_refs`
- `expected_c3_authority_dimensions`

At least one case must exercise each axis as a blocker or limitation. Do not hide all hard cases in the five negative probes.

- [ ] **Step 2: Produce S6 blocks in W12.D**

Modify `run_universal_outcome_corpus.py`:

- Add constants:
  - `S6_CASE_SIGNALS_PATH = Path("tests/fixtures/layer2/s6/s6_blind_spot_case_signals.json")`
  - `S6_EXPERT_LABELS_PATH = Path("tests/fixtures/layer2/s6/s6_blind_spot_expert_labels.json")`
- Add `_s6_blind_spot_summary(case: Mapping[str, object], *, repo_root: Path, s5_coupling_composition: Mapping[str, object] | None = None) -> dict[str, object]` per case.
- Add `_s6_blind_spot_corpus_summary(cases)`.
- Add `_s6_blind_spot_posture_input(s6_block) -> Layer2S6BlindSpotPostureInput`.
- Add `_s6_fixed_refs(case_id)` mirroring S4/S5 stable refs.
- Add `s6_blind_spot_firewalls` to every case block.
- Add top-level `s6_blind_spot_summary`.
- Inject the pinned case's S6 posture into S2 alongside existing S5 posture.
- Follow the existing S4/S5 helper style (`_s5_composition_posture_input`, `_s5_fixed_refs`) and keep this as an in-place route extension; do not refactor W12.D while adding S6.

Per-case S6 block required keys:

- `schema_version`
- `case_id`
- `overall_posture`
- `maturity`
- `axis_firewall_table`
- `measurability_record_ref`
- `aggregation_validity_record_ref`
- `capacity_feasibility_record_ref`
- `mandate_legitimacy_record_ref`
- `strategic_response_record_ref`
- `cluster_authority_dimension_refs`
- `bridge_consumer_table`
- `constraint_store_update_table`
- `constraint_store_entry_table`
- `c3_authority_dimension_table`
- `post_intervention_dgp_update_ref`
- `system_dynamics_handoff_required`
- `regime_reissue_required`
- `false_clear_penalty`
- `matches_gold`
- the five full record payloads for audit replay.

Top-level summary required keys:

- `schema_version = "policyos.policy_design_case.layer2_s6.blind_spot_corpus_summary.v1"`
- `case_count = 13`
- `axis_coverage_count = 5`
- `all_five_axes_covered = true`
- `per_axis_fail_closed_negative_control_pass_rate = 1.0`
- `false_clear_count = 0`
- `per_axis_disposition_counts`
- `bridge_consumer_coverage` as a dict keyed by every required bridge consumer, with every value `true`
- `c3_authority_dimension_coverage` as a dict keyed by every required C3 dimension, with every value `true`
- `overall_posture_counts`
- `system_dynamics_handoff_count`
- `regime_reissue_required_count`
- `per_case_axis_table`

- [ ] **Step 3: Add corpus route tests**

In `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`, add:

- `test_w12d_emits_s6_blind_spot_firewalls_for_13_cases`
- `test_w12d_s6_records_per_axis_fail_closed_coverage`
- `test_w12d_s6_gold_labels_cover_all_13_cases_and_five_axes`
- `test_w12d_s6_pinned_case_injects_posture_into_s2`
- `test_w12d_s6_reflexive_other_agents_flow_updates_system_dgp`
- `test_w12d_s6_bridge_consumer_table_covers_cluster_map_consumers`
- `test_w12d_s6_c3_authority_dimension_table_uses_canonical_dimensions`
- `test_w12d_s6_canonical_outcome_effect_remains_shadow_only`

Run:

```bash
cd policy-engine
uv run pytest tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py -q
```

Expected:

```text
W12.D route emits s4_epistemic_regime, s5_coupling_composition, and s6_blind_spot_firewalls for all 13 cases.
s6_blind_spot_summary.case_count == 13
s6_blind_spot_summary.axis_coverage_count == 5
s6_blind_spot_summary.bridge_consumer_coverage covers all five S6 cells
s6_blind_spot_summary.c3_authority_dimension_coverage includes strategic_robustness and response_model_validity
s6_blind_spot_summary.per_axis_fail_closed_negative_control_pass_rate == 1.0
s6_blind_spot_summary.false_clear_count == 0
canonical_outcome_effect remains none_shadow_only / production posture unchanged.
```

## Task 5: S6 Manifest, Readiness Validator, And Cluster-Map Cell Closure

**Files:**

- Create: `architecture/policy_design_case/layer2_s6_blind_spot_firewalls_manifest.json`
- Modify: `tools/quality/validation/check_policy_design_case_layer2_readiness.py`
- Modify: `architecture/policy_design_case/cluster_ownership_map.toml`
- Modify: `architecture/policy_design_case/inventory.json`
- Modify: `tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py`
- Modify: `tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py`

- [ ] **Step 1: Add S6 manifest**

Create `architecture/policy_design_case/layer2_s6_blind_spot_firewalls_manifest.json` with:

```json
{
  "schema_version": "policyos.policy_design_case.layer2_s6_blind_spot_firewalls_manifest.v1",
  "slice": "S6",
  "slice_label": "blind_spot_fail_closed_producers",
  "status": "active",
  "owner": "team-runtime-quality",
  "depends_on": ["S5"],
  "maturity": "fail_closed",
  "cells_closed": [
    "SYSTEM.measurability",
    "SYSTEM.subject_granularity",
    "ACTOR.state_capacity_feasibility",
    "ACTOR.mandate_legitimacy",
    "OTHER_AGENTS.strategic_response"
  ],
  "expected_current_open_cell_count": 5,
  "required_artifacts": [
    "MeasurabilityAdequacyRecord",
    "AggregationValidityRecord",
    "CapacityFeasibilityRecord",
    "MandateLegitimacyRecord",
    "StrategicResponseRecord",
    "ClusterAuthorityDimensionRecord"
  ],
  "required_firewalls": ["P18", "P19", "P21", "P22", "P24"],
  "floor_id": "s6_fail_closed_coverage",
  "floor_metric": "per_axis_fail_closed_negative_control_pass_rate",
  "floor_expected_minimum": 1.0,
  "false_clear_count": 0,
  "case_count": 13,
  "axis_coverage_count": 5,
  "all_five_axes_covered": true,
  "per_axis_fail_closed_negative_control_pass_rate": 1.0,
  "bridge_consumer_coverage": {
    "KNOWLEDGE.epistemic_regime": true,
    "ACTOR.value_choice_provenance": true,
    "INTERVENTION.targeting": true,
    "INTERVENTION.feasibility": true,
    "DESIGNER_ITSELF.envelope_membership": true,
    "PUBLIC.legitimacy_disclosure": true,
    "INTERVENTION.design_candidate": true,
    "SYSTEM.post_intervention_dgp": true,
    "SYSTEM.dynamics_feedback": true,
    "INTERVENTION.robustness": true
  },
  "c3_authority_dimension_coverage": {
    "measurability_adequacy": true,
    "aggregation_validity": true,
    "capacity_feasibility": true,
    "mandate_legitimacy": true,
    "strategic_robustness": true,
    "response_model_validity": true
  },
  "authority_scope": [
    "measurability_adequacy",
    "aggregation_validity",
    "capacity_feasibility",
    "mandate_legitimacy",
    "strategic_robustness",
    "response_model_validity",
    "fail_closed_axis_firewall"
  ],
  "c3_authority_dimensions": [
    "measurability_adequacy",
    "aggregation_validity",
    "capacity_feasibility",
    "mandate_legitimacy",
    "strategic_robustness",
    "response_model_validity"
  ],
  "required_bridge_consumers": [
    "KNOWLEDGE.epistemic_regime",
    "ACTOR.value_choice_provenance",
    "INTERVENTION.targeting",
    "INTERVENTION.feasibility",
    "DESIGNER_ITSELF.envelope_membership",
    "PUBLIC.legitimacy_disclosure",
    "INTERVENTION.design_candidate",
    "SYSTEM.post_intervention_dgp",
    "SYSTEM.dynamics_feedback",
    "INTERVENTION.robustness"
  ],
  "may_not_use_for": [
    "production_claim_authority",
    "rollout_authority",
    "publication_authority",
    "delegation_authority",
    "value_choice_authority",
    "outcome_prediction_authority",
    "forecast_calibration_authority",
    "rich_response_model_authority",
    "capacity_transfer_authority",
    "mandate_authority_from_llm",
    "proxy_construct_equivalence_without_disclosure",
    "aggregation_scope_transfer_without_validity",
    "post_policy_effect_claim_without_response_model"
  ],
  "producer_module": "src/polisyos/runtime/quality/design_axes/blind_spot_firewalls.py",
  "consumer_module": "src/polisyos/pdc/_impl/layer2_design_search.py",
  "canonical_route": "tools/quality/validation/run_universal_outcome_corpus.py",
  "validator": "tools/quality/validation/check_policy_design_case_layer2_readiness.py"
}
```

The final manifest may include measured summary fields from the corpus run, but it must keep the authority and `may_not_use_for` boundary above.

- [ ] **Step 2: Register S6 manifest in inventory**

Add one `artifacts[]` entry to `architecture/policy_design_case/inventory.json` before running the readiness validator:

```json
{
  "id": "layer2_s6_blind_spot_firewalls_manifest",
  "path": "architecture/policy_design_case/layer2_s6_blind_spot_firewalls_manifest.json",
  "kind": "layer2_s6_blind_spot_firewalls_manifest",
  "schema_version": "policyos.policy_design_case.layer2_s6_blind_spot_firewalls_manifest.v1",
  "owner": "team-runtime-quality",
  "status": "active",
  "capability_reality_label": "implemented",
  "maturity": "fail_closed",
  "authority_scope": [
    "measurability_adequacy",
    "aggregation_validity",
    "capacity_feasibility",
    "mandate_legitimacy",
    "strategic_robustness",
    "response_model_validity",
    "fail_closed_axis_firewall"
  ],
  "may_not_use_for": [
    "production_claim_authority",
    "rollout_authority",
    "publication_authority",
    "delegation_authority",
    "value_choice_authority",
    "outcome_prediction_authority",
    "forecast_calibration_authority",
    "rich_response_model_authority",
    "capacity_transfer_authority",
    "mandate_authority_from_llm",
    "proxy_construct_equivalence_without_disclosure",
    "aggregation_scope_transfer_without_validity",
    "post_policy_effect_claim_without_response_model"
  ],
  "validator": "tools/quality/validation/check_policy_design_case_layer2_readiness.py",
  "canonical_route": "tools/quality/validation/run_universal_outcome_corpus.py"
}
```

Expected readiness inventory count after S6: `14` layer2 artifacts (S5 reported `13`; S6 adds one manifest).

- [ ] **Step 3: Extend readiness validator**

In `check_policy_design_case_layer2_readiness.py`:

- Add `DEFAULT_S6_BLIND_SPOT_FIREWALLS_MANIFEST_PATH`.
- Add `_validate_s6_blind_spot_firewalls(*, s6: object, floor_governance: dict[str, Any], artifact_traceability: dict[str, Any], current_open_cells: set[str], assigned_cells: set[str], inventory: dict[str, Any], issues: list[dict[str, str]]) -> None`.
- Verify the manifest exists, has status active, maturity `fail_closed`, six required artifacts, five firewalls, all five cells, and `expected_current_open_cell_count == 5`.
- Verify manifest `c3_authority_dimensions` equals the architecture C3 dictionary for S6 and uses `strategic_robustness` / `response_model_validity`.
- Verify manifest `required_bridge_consumers` covers the bridge consumers in `cluster_ownership_map.toml` for all five S6 cells.
- Verify `s6_fail_closed_coverage` exists in floor governance and its revision rule is `all_five_blind_spot_axes_required`.
- Verify the S6 manifest carries the corpus metric fields that W12.D will generate: `case_count=13`, `axis_coverage_count=5`, `bridge_consumer_coverage` covers every required bridge consumer with `true`, `c3_authority_dimension_coverage` covers every required C3 dimension with `true`, `per_axis_fail_closed_negative_control_pass_rate >= 1.0`, and `false_clear_count=0`.
- Keep readiness validation static: do not run the W12.D corpus inside `check_policy_design_case_layer2_readiness.py`. Repo-quality tests in Task 6 compare the manifest metrics against the generated W12.D `s6_blind_spot_summary`.
- Verify inventory registration exists now, because Task 5 must pass the readiness validator before Task 6 snapshot burn-down.
- Add summary keys:
  - `s6_maturity`
  - `s6_case_count`
  - `s6_axis_coverage_count`
  - `s6_bridge_consumer_coverage`
  - `s6_c3_authority_dimension_coverage`
  - `s6_fail_closed_coverage`
  - `s6_false_clear_count`
  - `s6_expected_current_open_cell_count`

- [ ] **Step 4: Close the five cluster-map cells**

Update `architecture/policy_design_case/cluster_ownership_map.toml`:

- Remove `[open_cell_closure.SYSTEM.measurability]`.
- Remove `[open_cell_closure.SYSTEM.subject_granularity]`.
- Remove `[open_cell_closure.ACTOR.state_capacity_feasibility]`.
- Remove `[open_cell_closure.ACTOR.mandate_legitimacy]`.
- Remove `[open_cell_closure.OTHER_AGENTS.strategic_response]`.
- For each corresponding `[cell.*]`, set:
  - `owner_module = "src/polisyos/runtime/quality/design_axes/blind_spot_firewalls.py"` for the S6 fail-closed wrapper cells.
  - `owner_module = "src/polisyos/runtime/quality/design_axes/blind_spot_firewalls.py"` for `OTHER_AGENTS.strategic_response` as the PDC wrapper, while preserving strategic seed files.
  - `ratchet_state = "implemented"`.
  - `p01_chain = "implemented"`.
  - `gap = "none_for_s6_fail_closed_scope"`.
  - `action` text explicitly says predictive upgrade remains S11.

Do not touch S11 maturity transitions in `layer2_slice_cell_matrix.toml`.

- [ ] **Step 5: Add readiness/cluster tests for S6**

Update existing readiness and cluster tests to expect live open cell count `5` and the full S6 closure delta.

In `tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py`:

- Update `summary["current_open_cell_count"] == 5`.
- Update `cells_closed_since_s0` to include the five S6 cells in addition to S2/S4/S5:
  - `ACTOR.mandate_legitimacy`
  - `ACTOR.state_capacity_feasibility`
  - `INTERVENTION.design_candidate`
  - `INTERVENTION.design_grammar`
  - `INTERVENTION.reversibility_lifecycle_stakes`
  - `INTERVENTION.scale_composition`
  - `KNOWLEDGE.epistemic_regime`
  - `OTHER_AGENTS.strategic_response`
  - `SYSTEM.connectivity_modularity`
  - `SYSTEM.dynamics_feedback`
  - `SYSTEM.measurability`
  - `SYSTEM.subject_granularity`
- Update `assigned - current_open_cells` to the same closed-through-S6 set.

In `tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py`:

- Update `test_cluster_ownership_map_keeps_known_blind_spots_explicit` so `OTHER_AGENTS.strategic_response`, `ACTOR.state_capacity_feasibility`, and `ACTOR.mandate_legitimacy` are asserted as implemented S6 cells:
  - `owner_module == "src/polisyos/runtime/quality/design_axes/blind_spot_firewalls.py"`
  - `ratchet_state == "implemented"`
  - `p01_chain == "implemented"`
  - `gap == "none_for_s6_fail_closed_scope"`
  - `action` keeps the predictive/mature upgrade routed to S11.
- Remove the old `open_cell_closure["OTHER_AGENTS"]["strategic_response"]` assertion from that test; the row is no longer open after S6.
- Update `open_cell_closure["open_cell_count"] == 5`.
- Redirect `test_cluster_ownership_validator_rejects_missing_open_cell_closure` from `SYSTEM.measurability` to a still-open row such as `KNOWLEDGE.calibration`.
- Redirect `test_cluster_ownership_validator_rejects_closure_without_semantic_gap` from `OTHER_AGENTS.strategic_response` to a still-open row such as `KNOWLEDGE.calibration`.
- Add a stale-snapshot search before accepting the patch:

```bash
rg -n 'strategic_response.*implemented_but_not_orchestrated|state_capacity_feasibility.*producer_missing|mandate_legitimacy.*producer_missing|open_cell_closure.*(measurability|subject_granularity|state_capacity_feasibility|mandate_legitimacy|strategic_response)' \
  tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py
```

Expected: no output; an `rg` exit code of `1` is acceptable because it means no stale S6 open-state assertions remain.

Run:

```bash
cd policy-engine
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py -q
uv run python tools/quality/validation/check_policy_design_case_layer2_readiness.py
uv run python tools/quality/validation/check_policy_design_case_cluster_ownership_map.py
```

Expected:

```text
Readiness tests pass.
Cluster ownership tests pass.
Layer 2 readiness validator status=pass.
current_open_cell_count=5.
s6_fail_closed_coverage=1.0.
s6_false_clear_count=0.
Cluster validator status=pass.
open_or_incomplete_count=5.
```

## Task 6: Repo-Quality Tests, Inventory, Snapshot Updates, And Burn-Down Confirmation

**Files:**

- Create: `tests/repo_quality/tools/test_policy_design_case_layer2_s6_blind_spot_firewalls.py`
- Modify: prior slice live-count snapshot tests listed in Files.

- [ ] **Step 1: Confirm S6 inventory registration**

Task 5 already registers `layer2_s6_blind_spot_firewalls_manifest` in `architecture/policy_design_case/inventory.json` so the readiness validator can pass. In this task, add repo-quality assertions that the inventory entry exists, matches the manifest authority boundary, and keeps the expected layer2 artifact count at `14`.

- [ ] **Step 2: Add S6 repo-quality tests**

Create `tests/repo_quality/tools/test_policy_design_case_layer2_s6_blind_spot_firewalls.py` with:

- `test_layer2_s6_manifest_is_valid_and_open_count_is_5`
- `test_layer2_s6_closes_five_cells_with_fail_closed_maturity`
- `test_layer2_s6_required_artifacts_are_traceable_and_exported`
- `test_layer2_s6_firewalls_are_registered_and_all_five_axes_required`
- `test_layer2_s6_inventory_registration_exists`
- `test_layer2_s6_inventory_and_manifest_authority_boundaries_match`
- `test_layer2_s6_c3_authority_dimensions_are_canonical`
- `test_layer2_s6_bridge_consumers_cover_cluster_map_contracts`
- `test_layer2_s6_cluster_map_marks_cells_implemented_and_unlisted_as_open`
- `test_layer2_s6_may_not_use_for_blocks_prediction_delegation_value_and_production_authority`
- `test_layer2_s6_manifest_metrics_match_generated_corpus_summary`
- `test_layer2_s6_corpus_summary_records_zero_false_clear`

- [ ] **Step 3: Confirm prior-slice live-count snapshots**

Closing five cells moves the live open count `10 -> 5`. Task 5 already updates the readiness and cluster-map tests that must pass before validator closure. In this task, update only the prior-slice regression snapshots and confirm no stale S6 open-cell rows remain.

- `tests/repo_quality/tools/test_policy_design_case_layer2_s2_design_search.py`
  - live readiness open count `5`; keep S2 static manifest `expected_current_open_cell_count == 15`.
- `tests/repo_quality/tools/test_policy_design_case_layer2_s3_substrate_acquisition.py`
  - live readiness open count `5`; keep S3 static manifest `expected_current_open_cell_count == 15`.
- `tests/repo_quality/tools/test_policy_design_case_layer2_s4_epistemic_regime.py`
  - live readiness open count `5`; keep S4 static manifest `expected_current_open_cell_count == 13`.
- `tests/repo_quality/tools/test_policy_design_case_layer2_s5_coupling_composition.py`
  - live readiness open count `5`; keep S5 static manifest `expected_current_open_cell_count == 10`.
- Re-run the stale-snapshot `rg` command from Task 5 Step 5 and confirm no S6 cells remain asserted as open.

- [ ] **Step 4: Run repo-quality burn-down tests**

Run:

```bash
cd policy-engine
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s2_design_search.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s3_substrate_acquisition.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s4_epistemic_regime.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s5_coupling_composition.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s6_blind_spot_firewalls.py -q
uv run python tools/quality/validation/check_policy_design_case_layer2_readiness.py
uv run python tools/quality/validation/check_policy_design_case_cluster_ownership_map.py
python3 -m json.tool architecture/policy_design_case/inventory.json >/dev/null
python3 -m json.tool architecture/policy_design_case/layer2_s6_blind_spot_firewalls_manifest.json >/dev/null
git diff --check
```

Expected:

```text
Repo-quality tests pass.
Readiness validator status=pass.
current_open_cell_count=5.
inventory_artifact_count=14.
s6_bridge_consumer_coverage has every required bridge consumer set to true.
s6_c3_authority_dimension_coverage has every required C3 dimension set to true.
s6_fail_closed_coverage=1.0.
s6_false_clear_count=0.
Cluster validator status=pass.
open_or_incomplete_count=5.
JSON files parse.
git diff --check reports no whitespace errors.
```

## Task 7: Full S6 Verification

- [ ] **Step 1: Run the full S6 + regression gate**

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer2_s6_blind_spot_firewalls.py -q
uv run pytest tests/unit/pdc/test_layer2_readiness_contracts.py tests/unit/pdc/test_layer2_s2_design_search.py -q
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer2_s6_blind_spot_firewalls.py -q
uv run pytest tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py -q
uv run pytest tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py tests/repo_quality/tools/test_policy_design_case_capability_ratchet.py -q
uv run pytest tests/unit/runtime/quality/test_layer2_s5_coupling_composition.py tests/unit/runtime/quality/test_layer2_s4_epistemic_regime.py tests/unit/runtime/quality/test_layer2_s3_substrate_acquisition.py tests/unit/runtime/quality/test_layer2_graded_outcomes.py -q
uv run python tools/quality/validation/check_policy_design_case_layer2_readiness.py
uv run python tools/quality/validation/check_policy_design_case_cluster_ownership_map.py
PYTHONPATH=src:. uv run --extra runtime --extra ml polisyos-tools runtime check-runtime-api-contract
uv run polisyos-tools architecture guardrails check
```

Expected:

```text
S6 unit + repo-quality tests pass.
S1/S2/S3/S4/S5 regression tests pass.
W12.D route emits s4_epistemic_regime, s5_coupling_composition, and s6_blind_spot_firewalls for all 13 cases.
S6 bridge consumer coverage and C3 authority-dimension coverage have every required key set to true.
Layer 2 readiness validator: status pass; open_cell_count/current_open_cell_count 5; S6 cells closed.
Cluster ownership validator: status pass; open_or_incomplete/open-cell count 5.
Capability ratchet unchanged/green.
Runtime API contract pass.
CertifiedOperationEnvelope.cluster_authority_dimension_refs remains PDC-internal and does not require runtime OpenAPI surface changes.
Architecture guardrails pass.
```

Record under this task:

- `case_count`
- `axis_coverage_count`
- `bridge_consumer_coverage`
- `c3_authority_dimension_coverage`
- `per_axis_fail_closed_negative_control_pass_rate`
- `false_clear_count`
- `overall_posture_counts`
- `per_axis_disposition_counts`
- `system_dynamics_handoff_count`
- `regime_reissue_required_count`
- any Done-When caveat.

- [ ] **Step 2: Manual Done-When probes**

Run:

```bash
cd policy-engine
python3 - <<'PY'
import polisyos.runtime.quality as rq
names = [
    "CapacityFeasibilityRecord",
    "MandateLegitimacyRecord",
    "MeasurabilityAdequacyRecord",
    "AggregationValidityRecord",
    "StrategicResponseRecord",
    "ClusterAuthorityDimensionRecord",
]
for name in names:
    obj = getattr(rq, name)
    print(name, getattr(obj, "model_config", {}).get("extra"))
PY
rg -n "layer2_blind_spot_firewalls|evaluate_measurability|evaluate_aggregation|evaluate_capacity|evaluate_mandate|evaluate_strategic_response" src/polisyos/pdc/_impl/layer2_design_search.py
python3 - <<'PY'
from polisyos.pdc import CertifiedOperationEnvelope
print("cluster_authority_dimension_refs" in CertifiedOperationEnvelope.model_fields)
PY
```

Expected:

```text
All six S6 artifacts are exported from runtime.quality and use extra=forbid through Layer2ReadinessModel.
The rg command returns no matches, proving B consumes only injected posture.
CertifiedOperationEnvelope exposes cluster_authority_dimension_refs.
```

## Done When

1. The named S6 artifacts (`CapacityFeasibilityRecord`, `MandateLegitimacyRecord`, `MeasurabilityAdequacyRecord`, `AggregationValidityRecord`, `StrategicResponseRecord`, and `ClusterAuthorityDimensionRecord`) plus nested rows/check records are strict, replayable, and exported from `runtime.quality`.
2. S6 is A-gate-owned. B consumes injected `Layer2S6BlindSpotPostureInput` and cannot self-clear measurability, aggregation, capacity, mandate, or strategic-response risk.
3. Every S6 cell is implemented with `maturity=fail_closed`: `SYSTEM.measurability`, `SYSTEM.subject_granularity`, `ACTOR.state_capacity_feasibility`, `ACTOR.mandate_legitimacy`, and `OTHER_AGENTS.strategic_response`.
4. Missing axis evidence defaults to `limit` or `block`, never `pass`.
5. P18 fails closed: proxy-only measurable outputs cannot satisfy original unmeasured/qualitative policy values without proxy validity and value-loss disclosure.
6. P19 fails closed: group/jurisdiction/system evidence cannot close individual/firm/subgroup targeting claims without aggregation validity; ecological-error and Simpson-risk probes block or limit.
7. P21 fails closed: designs requiring absent administrative, fiscal, enforcement, delivery, coordination, political-feasibility, institutional-credibility, or participation capacity are blocked/limited or converted into capacity-building obligations.
8. P22 fails closed: LLM/reviewer speculation cannot authorize objectives, social weights, or affected-person mandate; mandate gaps remain candidate, limited, or blocked.
9. P24 fails closed: Goodhart/Lucas/performativity/capture/sabotage/gaming/adaptation risk updates `SYSTEM.post_intervention_dgp` and prevents unchanged pre-policy effect claims.
10. S6 emits per-axis `AxisPositionDeclaration` and `AxisFirewallStatus` rows with P18/P19/P21/P22/P24 pattern ids, writes typed S2 `ConstraintStoreSnapshot.constraint_records`, emits canonical C3 `ClusterAuthorityDimensionRecord` rows, stores their refs on `CertifiedOperationEnvelope.cluster_authority_dimension_refs`, and persists all six top-level refs on `DesignRecordV0.ledger_refs`.
11. S6 bridge consumers cover the cluster-map contract: measurability -> regime/value-choice gates; aggregation -> targeting/regime gates; capacity -> feasibility/envelope gates; mandate -> value-choice/public/design-candidate gates; strategic response -> post-intervention DGP/dynamics/robustness gates. Missing downstream slices become typed pending constraints, not silent passes.
12. S6 posture renders in all four audience projections via `project_s2_design_search`:
    - PUBLIC: disclosed unmeasured-value / feasibility / legitimacy / response limitations only; no machine-facing `BlindSpotOverallPosture` label is presented as a user-facing posture.
    - REVIEWER: per-axis firewall status + P18/P19/P21/P22/P24 disposition.
    - EXPERT/MACHINE: all record refs, axis rows, proxy/aggregation/capacity/mandate/strategic-response details, DGP update, false-clear penalty, maturity, and authority boundary.
13. All 13 corpus cases contain S6 blocks; `per_axis_fail_closed_negative_control_pass_rate == 1.0`; `false_clear_count == 0`; `bridge_consumer_coverage` and `c3_authority_dimension_coverage` have every required key set to true; per-case axis table is recorded.
14. Production-posture outcomes and closeout honesty are unchanged by S6; S6 affects shadow/governed constraint routing only.
15. `s6_fail_closed_coverage` floor is recorded from the governed floor table; no denominator/floor is changed.
16. Cluster-map open cell count is `5`; both validators pass; the S6 manifest is registered in inventory.
17. No S7 delegation, S8 value-choice provenance, S10 forecast support, S11 predictive blind-spot maturity, production authority, calibrated equilibrium prediction, rich simulation, portfolio optimization, or S14 universality battery cell is marked implemented.

## Verification Commands

See Task 7. Plan-level done = all Task 7 commands pass with the expected output, the open cell count is `5`, S6 corpus blind-spot metrics are recorded, and no production floor is weakened.

## Commit Guidance

Mirror the S4/S5 red-first sequence, one logical commit per task:

```text
test: add layer2 s6 blind-spot fail-closed red tests
feat: add layer2 s6 blind-spot firewalls and axis records
feat: inject layer2 s6 blind-spot posture into shadow design loop
feat: classify layer2 s6 corpus blind-spot coverage
chore: close layer2 s6 fail-closed blind-spot cells
chore: register layer2 s6 blind-spot progress
```

End commit messages with the repo's standard co-author trailer. Do not mark any S7+ cell, production authority, calibrated prediction, rich simulation, predictive blind-spot maturity, portfolio optimization, or S14 universality battery cell as implemented.
