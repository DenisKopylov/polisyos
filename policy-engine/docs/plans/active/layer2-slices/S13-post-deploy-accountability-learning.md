---
title: PolicyOS Layer 2 S13 Post-Deploy Accountability And Learning Implementation Plan
status: active
owner: governance-board
created: 2026-06-03
last_verified: null
stability: draft
revision_note: Drafted after S12 verification; expands the roadmap S13 closure contract into an executable, red-first task plan.
slice: S13
slice_label: post_deploy_accountability_learning
roadmap: ../POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER2_IMPLEMENTATION_PLAN.md
source_design_doc: ../../../system-design-decisions/universal-policy-design-target-architecture-and-gap.md
cluster_ownership_map: ../../../../architecture/policy_design_case/cluster_ownership_map.toml
slice_cell_matrix: ../../../../architecture/policy_design_case/layer2_slice_cell_matrix.toml
floor_governance: ../../../../architecture/policy_design_case/layer2_floor_governance.toml
artifact_traceability: ../../../../architecture/policy_design_case/layer2_artifact_traceability.toml
failure_patterns: ../../../reference/policy-design-case-failure-patterns.md
depends_on:
  - S7
  - S9
  - S12
cells_closed: []
layer_cells_advanced:
  - DESIGNER_ITSELF.envelope_growth
expected_current_open_cell_count: 0
floor_id: s13_accountability
floor_metric: a_before_b_ratio_and_attribution_resolution
---

# PolicyOS Layer 2 S13 Post-Deploy Accountability And Learning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

Read this whole file before editing code. S13 is a post-deploy accountability and learning slice. It makes deployed designs accountable over time, learns only from attributable divergence, and records envelope expansion or shrink without rewriting closed-case authority.

S13 does not close a new open cell. It advances `DESIGNER_ITSELF.envelope_growth` from S12's value-of-information and resource allocation posture into bidirectional post-deploy envelope revision. The expected open-cell count remains `0`.

This plan is intentionally a task plan, not a roadmap rewrite. The roadmap owns strategy, sequencing, doctrine, and slice closure contracts. This file unfolds the S13 closure contract into exact contracts, files, wiring, tests, commands, expected failures, and repository-state deltas.

## S13 Closure Contract

- Slice: `S13 | Post-deploy accountability + learning`.
- Cell advanced: `DESIGNER_ITSELF.envelope_growth`.
- Layer: `post-deploy accountability`.
- Producer: divergence classifier, attribution gate, learning proposal builder, envelope revision builder, assurance-case delta builder.
- Persisted artifacts: `DeploymentDossier`, `DivergenceRecord`, `LearningUpdateProposal`, `EnvelopeRevision`, `CertifiedEnvelopeDelta`, `AssuranceCaseDelta`.
- Bridge and consumer: attribution -> governed update -> knowledge ledger/PDC posture/projection semantics/public export.
- Surface: public accountability note plus expert/machine/reviewer envelope revision and attribution details.
- Semantic test: seeded disconfirmation shrinks the envelope; validated reusable learning expands the envelope.
- Negative controls: post-policy data cannot become pre-policy evidence; a learned prior cannot occupy a current evidence slot; unattributable records produce accountability without training.
- Firewalls: anti-learning authority boundary, `C41` learned-prior firewall, A-before-B replay sequence, closed-case replay integrity.
- Floor: `s13_accountability` with metric `a_before_b_ratio_and_attribution_resolution`.

## Scope Boundaries

S13 implements accountability and governed learning posture. It may say what changed after deployment, whether divergence is attributable, whether a learning update is allowed, and whether an envelope should expand, shrink, split, or hold.

S13 must not implement or imply S14 universality. It must not grant production, rollout, approval, publication, recommendation, scorecard, preference-learning, automated value-learning, or naive model-update authority. It must not use post-policy observations as pre-policy evidence or silently rewrite a closed design case.

`unattributable` is a first-class accountability outcome, not a training signal. `implementation_failure` may justify delivery/capacity redesign, but it does not by itself refute policy theory.

## Pattern Pass

| Pattern | S13 risk | Closure move |
| --- | --- | --- |
| `P01` contract-only capability | New artifacts without producer/consumer/surface would be inert. | Add runtime producer, persisted manifest, PDC bridge, projection/public consumers, semantic tests, and repo-quality validation. |
| `P02` thin orchestration | Accountability posture could be built but not carried into downstream decisions. | Wire S13 posture through PDC context, corpus route, projection semantics, and public export. |
| `P03` hidden internal richness | Divergence and learning details could exist only in internal JSON. | Surface public accountability notes and expert/machine/reviewer revision details. |
| `P04` status lattice gap | `warn`, `pending`, `unattributable`, and `accountability_only` could collapse into pass/fail or a new S13-only reissue status set. | Add explicit dispositions, reuse the existing `case_lifecycle` reissue lattice, and test mixed blocked, advisory, accountability-only, deployable, reissue, supersede, and withdraw outcomes. |
| `P05` authority boundary leak | Post-deploy learning could masquerade as evidence or recommendation authority. | Add `may_not_use_for` firewalls and projection/public negative tests. |
| `P07` rule replay gap | Learning decisions could be unreplayable. | Carry schema version, rule version, timestamps, source refs, replay digest, and A-before-B checks. |
| `P08` time-role conflation | Deployment, observation, attribution, and reissue times could be mixed. | Model distinct deployment, observation, detection, attribution, reissue, and replay timestamps. |
| `P09` warning lifecycle gap | Divergence warnings could have no owner or closure path. | Require owner, due date, action class, and public/reviewer lifecycle status. |
| `P10` semantic adequacy gap | Tests could prove constructors only. | Start red with semantic shrink/expand and negative-control tests. |
| `P11` failure-only memory | Learning could only shrink envelopes and never expand reusable knowledge. | Require bidirectional envelope tests: shrink on seeded disconfirmation and expand on validated reuse. |
| `P12` producer handshake gap | The corpus route could emit summary fields without typed producer artifacts. | Route W12D through typed S13 builders and manifest validation. |
| `P13` governance gravity | S13 could become a giant lifecycle platform. | Wrap existing `case_lifecycle`, calibration, human-review, and S12 envelope substrates; keep S13 to accountability, attribution-gated learning, and envelope revision; leave universality/production to S14+. |
| `P15` LLM speculation laundering | Candidate narrative could become authoritative attribution. | Require non-LLM source refs, attribution status, and explicit candidate/authority separation. |
| `P24` strategic response/Lucas | Observed post-policy behavior could be treated as stable pre-policy evidence. | Add Lucas firewall and negative controls for post-policy data in pre-policy evidence slots. |
| `P25` search/control boundary | Learning updates could drive automated search or control. | S13 posture constrains reissue/accountability only; it is not a search objective or control policy. |
| `P26` human accountability | System could learn while owner accountability disappears, especially when a divergence passed through ineffective review. | Require owners, action items, governance class, public accountability note, and an explicit rubber-stamp-linked accountability state for design-error divergence after ineffective oversight. |

Capability label transition:

- Starting label: `surface_missing`, `verification_missing`, `semantic_test_missing` for the S13 post-deploy accountability layer.
- Target label: complete S13 capability chain with `cells_closed=[]`, `layer_cells_advanced=["DESIGNER_ITSELF.envelope_growth"]`, and open-cell count still `0`.

## Code-Grounded Reality Check

Existing substrates to reuse:

- `src/polisyos/runtime/quality/case_lifecycle.py` already models lifecycle, monitoring validation, reissue, public revision state, ex-post learning, prediction/outcome links, future-prior checks, and replay semantics.
- `case_lifecycle.build_ex_post_learning_record(...)`, `validate_ex_post_learning_record(...)`, `_validate_learning_records(...)`, and `detect_memory_contamination(...)` already enforce learning shape, outcome links, revocation conditions, reusable learning, and contamination controls. S13 `LearningUpdateProposal` must wrap this validated dict substrate rather than recreate a feedback engine.
- `case_lifecycle._public_revision_state(...)` already materializes public closed-case meaning preservation through `closed_case_historical_meaning="preserved"`, affected/unaffected claim ids, public diffs, `silent_upgrade_allowed=False`, and projection-only authority. S13 public accountability notes should project this state rather than add another silent-rewrite detector.
- `case_lifecycle._lifecycle_reissue_status(...)` already returns the lifecycle reissue lattice (`fail`, `withdraw_required`, `supersede_required`, `reissue_required`, `review_required`, `pass`). S13 change-control class `reissue_required` must map into this lattice and reviewer-visible lifecycle actions, not create parallel S13 reissue statuses.
- `case_lifecycle._validate_prediction_outcome_link(...)` and `_claim_future_prior_issues(...)` already implement the A-before-B prediction/outcome shape. S13 must reuse these barriers when a post-deploy signal proposes learning.
- `src/polisyos/runtime/quality/ddm_monitoring.py` already builds and validates decision monitoring/evaluation record dictionaries through `build_implementation_monitoring_evaluation_record(...)` and `validate_implementation_monitoring_evaluation_record(...)`; there is no `ImplementationMonitoringEvaluationRecord` class.
- `src/polisyos/core/contracts/feedback.py`, `src/polisyos/scientist/feedback/core.py`, and `src/polisyos/runtime/http/services/feedback.py` already provide monitoring contracts, reports, compare reports, and reissue plans.
- `src/polisyos/scientist/governance/continuous/reissue.py` already models governed reissue packets and partial publication state.
- `src/polisyos/pdc/_impl/layer2_design_search.py` already exports `TypedDiagnosticRecord`; S13 `DivergenceRecord` must compose that shared diagnostic shape, following the existing `RefinementDecision.diagnostic: TypedDiagnosticRecord` pattern, rather than inventing a local diagnostic vocabulary.
- `polisyos.pdc` already exports `GovernanceDecisionClass` and `AuthorityBoundary`; `src/polisyos/runtime/quality/layer2_delegation.py` exports `HumanDecisionRequest` and `HumanDecisionRecord`. High-stakes S13 reissue and envelope-revision paths must carry these refs instead of adding local governance-decision enums.
- `src/polisyos/runtime/quality/human_review.py` already computes oversight-effectiveness telemetry; S13 should link post-deploy divergence back to review/approval effectiveness without creating a seventh first-class S13 artifact.
- `src/polisyos/runtime/quality/calibration_ledger.py` already enforces the historical-prior/current-evidence boundary; S13 should reuse this C41 posture for learned-prior checks.
- `src/polisyos/runtime/quality/layer2_resource_economics.py` already provides the S12 `EnvelopeGrowthLedger`; S13 must build typed bidirectional revision on top of it instead of redefining S12 allocation economics.
- `architecture/policy_design_case/layer2_floor_governance.toml` already contains the `s13_accountability` floor.
- `architecture/policy_design_case/layer2_artifact_traceability.toml` already plans S13 artifacts.
- `architecture/policy_design_case/cluster_ownership_map.toml` currently marks `DESIGNER_ITSELF.envelope_growth` implemented by S12 and explicitly leaves shrink/bidirectional revision to S13.

Strong seams:

- S13 should mirror the S12 posture-injection pattern in `src/polisyos/pdc/_impl/layer2_design_search.py`: strict posture input, optional run field, `SearchLedger` refs, handoff record, cluster interface, deterministic replay key, legacy defaults, persisted ledger round trip, and a no-runtime-producer-import test.
- `tools/quality/validation/run_universal_outcome_corpus.py` already has a mature S12 block route: `_s12_resource_economics_case_block`, `_s12_resource_posture_input`, and `_s12_resource_economics_summary`. S13 should add sibling helpers instead of reshaping the whole W12D runner.
- `src/polisyos/runtime/quality/projection_semantics.py` and `src/polisyos/runtime/quality/public_export.py` already have S10/S11/S12 consumer-contract verification and public-projection enrichment patterns. S13 should add a sibling consumer contract and export hook.
- `src/polisyos/runtime/quality/calibration_ledger.py` already exports `is_historical_prior_ref` and `historical_prior_claim_evidence_issues`. S13 learned-prior tests should call or mirror these helpers rather than creating another current-evidence-slot detector.

Weak or expensive seams:

- `tools/quality/validation/check_policy_design_case_layer2_readiness.py` is hardcoded through S12: it loads only the S12 manifest, has inventory-count guards for `19/20` and exact `20`, and rejects implemented S13/S14 traceability from S9, S10, S11, and S12 validators. Task 5 must explicitly add S13 constants, default manifest path, loader, validator invocation, inventory count `21`, and future-slice guards that allow S13 while still rejecting S14.
- `architecture/policy_design_case/cluster_ownership_map.toml` is validated by the S12 readiness check with exact `owner_module`, `p01_chain`, `gap`, and `firewall` values for `DESIGNER_ITSELF.envelope_growth`. Do not mutate those exact S12 fields unless the readiness validator is deliberately updated in the same task.
- S2 integration is wider than a single function argument. The real touch set includes request/run typing, constraint store, search ledger, design record, cluster interfaces, handoff records, deterministic replay key, projection serialization, persisted CAS compatibility, and legacy-default tests.
- S12 and S11 deny lists currently include future S13 authority tokens, including `s13_accountability_closure` and `s13_envelope_shrink`. S13 should not remove those historical deny-list protections unless a failing S13 test proves a specific current contract must change.

Overbuild guard:

- S13 implementation should extend these seams. Do not introduce a parallel lifecycle engine, feedback service, governance-decision enum, calibration firewall, historical-prior detector, or design-case replay framework.
- Prefer a narrow S13 validator copied in the existing readiness-validator style over a broad validator framework refactor. The cleanup may be worthwhile later, but it is not part of S13 closure.

## Reuse Map

S13 is the typed Layer 2 shell over A-side lifecycle substrates. It should add accountability and change-control semantics only where the substrate is intentionally missing them.

| Existing A-side substrate | S13 Layer 2 responsibility |
| --- | --- |
| `build_ex_post_learning_record(...)`, `_validate_learning_records(...)`, and `detect_memory_contamination(...)` in `case_lifecycle.py` | `LearningUpdateProposal` wraps the validated dict and adds attribution class/status, change-control class, learning target component, governance refs, and explicit A-before-B outcome. |
| `_public_revision_state(...)` in `case_lifecycle.py` plus `public_export.semantic_audit.public_revision_states` | Public accountability note projects the existing public revision state; S13 does not redetect silent closed-case rewrites. |
| `_lifecycle_reissue_status(...)` in `case_lifecycle.py` | `LearningChangeControlClass == "reissue_required"` resolves to existing lifecycle dispositions/reissue actions. No S13-only reissue status set. |
| `historical_prior_claim_evidence_issues(...)` and `is_historical_prior_ref(...)` in `calibration_ledger.py` | Learned-prior firewall uses recognized historical-prior refs; S13 learned-prior outputs must mint refs with accepted prefixes so C41 is actually exercised. |
| `_oversight_effectiveness(...)` in `human_review.py` | Divergence attributed to a design after ineffective or high-risk rubber-stamp review gets an explicit oversight-linked accountability state surfaced to reviewers. |
| `TypedDiagnosticRecord` in `layer2_design_search.py` | `DivergenceRecord` composes `diagnostic: TypedDiagnosticRecord` and keeps post-deploy attribution as a separate axis. |
| S12 `EnvelopeGrowthEntry.certified_envelope_delta_ref` in `layer2_resource_economics.py` | S13 `CertifiedEnvelopeDelta` materializes the deferred string ref for certified growth and adds native shrink/split revision semantics through `EnvelopeRevision`. |

## Implementation Design

### Design-Time Accountability Gate

Every deployable design case needs a `DeploymentDossier`. A dossier is deployable only when it has monitoring design, signposts, complaint/near-miss intake, attribution plan, reissue path, rollback/reconsideration path, owner, and due dates.

Disposition rules:

- `deployable`: monitorable and learnability gates are satisfied.
- `accountability_only`: monitorable enough for accountability, but not enough for governed learning.
- `advisory_only`: useful as advice, but missing deployment accountability requirements.
- `blocked`: violates authority, replay, ownership, or monitoring floor.

`accountability_only` must not become a training signal. It can produce public accountability notes and reviewer actions.

### Divergence And Attribution

S13 records divergence after deployment as a typed `DivergenceRecord`, using this initial attribution vocabulary:

- `design_error`
- `evidence_error`
- `regime_error`
- `coupling_error`
- `world_change`
- `strategic_response`
- `implementation_failure`
- `unattributable`

Attribution status is separate from attribution class:

- `attributed`
- `unattributable`
- `pending`

Learning requires `attributed`. Accountability notes may be produced for all three statuses.

`DivergenceRecord` is a post-deploy record that composes the shared `TypedDiagnosticRecord` shape. It must carry a `diagnostic: TypedDiagnosticRecord` field plus S13-specific fields for:

- class/code/severity.
- failed axis or firewall.
- evidence refs.
- attribution owner.
- allowed moves.
- learning eligibility.
- authority boundary.
- replay refs.
- whether B may learn from the divergence or A must be repaired first.
- action-item owner, deadline, status, and closure ref.

A divergence without an owned action-item closure path is an archive, not learning.

Oversight-linked accountability is mandatory when attribution points back to design approval:

- If an attributed `design_error` divergence links to an approving human review whose `effective_oversight == False` or `rubber_stamp_risk == "high"`, S13 marks `oversight_accountability_state == "rubber_stamp_divergence_review_required"`.
- If review was effective, S13 may mark `oversight_accountability_state == "effective_oversight_linked"`.
- This state is reviewer-visible accountability, not a new approval authority or a new governance enum.

### MAPE-K Trace

S13 must expose an attribution-gated MAPE-K trace inside its artifacts and summary:

- Monitor: deployed outcomes, implementation-fidelity signals, complaints, near misses, drift, and surprises.
- Analyze: `DivergenceRecord`, attribution class/status, and observable-subset/counterfactual credibility.
- Plan: acquisition, model update, regime/coupling reclassification, capacity repair, memory update, envelope shrink/expand/split/hold, or reissue.
- Execute: governed update or explicit accountability-only/public-note action.
- Knowledge: knowledge-ledger refs for calibration, memory, envelope revision, corpus labels, and historical-prior influence.

The MAPE-K trace is not a new first-class S13 manifest artifact. It is a required embedded trace across `DeploymentDossier`, `DivergenceRecord`, `LearningUpdateProposal`, `EnvelopeRevision`, and `AssuranceCaseDelta`.

### Governed Learning Proposal

A `LearningUpdateProposal` may be produced only after the A-before-B barrier passes:

- A: record deployment baseline, monitoring design, source refs, and pre-policy evidence boundary.
- B: observe post-deploy signal, classify divergence, attribute source, and propose update.

Implementation shape:

- `LearningUpdateProposal` wraps the dict shape produced by `build_ex_post_learning_record(...)` and accepted by `validate_ex_post_learning_record(...)`; it does not replace those functions.
- `case_lifecycle` remains responsible for clean outcome links, reusable learning, revocation conditions, memory contamination controls, and no publication-authority rewrite.
- S13 adds only attribution class/status, change-control class, explicit learning target component, governance refs, and an explicit A-before-B result.

Allowed change-control classes:

- `pre_authorized`
- `reissue_required`
- `envelope_shrink`
- `historical_prior_only`
- `public_accountability_note`

No S13 update may occupy a current evidence slot. Learned priors are historical priors or reissue inputs only.

Historical-prior refs minted by S13 must use a prefix recognized by `is_historical_prior_ref(...)`, preferably `historical-prior-influence:`. The accepted fallback prefixes are `runtime.calibration_ledger:` and `calibration-ledger:`. Without one of these prefixes, `historical_prior_claim_evidence_issues(...)` will not detect the learned-prior/current-evidence violation, so the negative control is invalid.

Learning update targets are explicit and attribution-gated:

- `substrate`
- `a_firewall`
- `b_prior`
- `calibration`
- `regime_classifier`
- `coupling_classifier`
- `strategic_response_model`
- `capacity_feasibility_model`
- `memory`
- `corpus_label`
- `envelope`
- `public_accountability_note`

Historical-prior outputs must carry provenance, TTL, decay, and contamination controls. They may influence routing, review, acquisition, generation, and future authority caps, but they cannot close current evidence slots.

High-stakes reissue, public correction, value conflict, mandate challenge, envelope shrink/expansion, and verifier-spec repair require existing governance refs: `GovernanceDecisionClass` from `polisyos.pdc`, `HumanDecisionRequest` from `layer2_delegation.py` when intervention is needed, and `HumanDecisionRecord` from `layer2_delegation.py` when a human/governance decision is used. S13 may propose one of these decisions, but it must not create a separate local governance-decision enum.

`LearningChangeControlClass == "reissue_required"` must resolve to the existing lifecycle reissue disposition from `_lifecycle_reissue_status(...)` (`reissue_required`, `supersede_required`, `withdraw_required`, `review_required`, `fail`, or `pass`). Reviewer-facing reissue actions are projections of that existing lifecycle status. Directional envelope revision (`expand`, `shrink`, `hold`, `split`) is orthogonal and may remain S13-native.

### Envelope Revision And Assurance

S13 emits `CertifiedEnvelopeDelta` and `EnvelopeRevision` with direction:

- `expand`
- `shrink`
- `hold`
- `split`

Every non-hold revision requires an `AssuranceCaseDelta`. Assurance changes are:

- `strengthened`
- `weakened`
- `invalidated`
- `unchanged`

Seeded disconfirmation must shrink or split the envelope. Validated reuse must expand it. Ambiguous or unattributable records must hold the envelope and produce accountability without training.

S13 closes a deliberate S12 deferral:

- S12 `EnvelopeGrowthEntry` is expand-only and stores `certified_envelope_delta_ref` as a string. Do not add `direction` to S12 growth entries.
- S13 `CertifiedEnvelopeDelta` materializes that deferred S12 ref when certified growth exists.
- Growth remains gated by certified-envelope delta because S12 counts only real mechanism growth.
- Shrink and split are asymmetric: they are gated by `AssuranceCaseDelta`, disconfirming signal time, revision effective time, and shrink latency. They are native S13 accountability behavior, not S12 growth-ledger behavior.

### Surfaces

Public projection:

- Shows a public accountability note.
- Shows whether a revision exists and whether historical meaning changed.
- Must preserve the historical meaning of closed cases.
- Reuses `case_lifecycle._public_revision_state(...)` and the existing `public_export.semantic_audit.public_revision_states` surface; S13 does not implement a second closed-case rewrite detector.

Expert and machine projection:

- Shows attribution status/class, change-control class, envelope delta, assurance-case delta, source refs, schema/rule versions, and replay digest.

Reviewer projection:

- Shows owners, deadlines, lifecycle status, pending attribution, oversight-linked accountability state, and reissue actions mapped from the existing lifecycle reissue lattice.

## Closure Metrics

Required S13 closeout metrics:

- `slice == "S13"`.
- `cells_closed == []`.
- `layer_cells_advanced == ["DESIGNER_ITSELF.envelope_growth"]`.
- `current_open_cell_count == 0`.
- `inventory_artifact_count == 21`.
- `required_artifact_count == 6` for the six S13 artifacts.
- `canonical_corpus_case_count == 13`.
- `monitorability_rate == 1.0` for canonical fixtures.
- `a_before_b_ratio == 1.0` for canonical learning proposals.
- `attribution_resolution_rate == 1.0` for canonical learning proposals.
- `envelope_shrink_count >= 1`.
- `envelope_expansion_count >= 1`.
- `envelope_shrink_latency_recorded_count >= 1` for seeded disconfirmation shrink/split cases.
- `unattributable_accountability_without_training_count >= 1`.
- `mape_k_trace_completeness_rate == 1.0`.
- `action_item_closure_rate == 1.0` for canonical closed accountability items.
- `oversight_effectiveness_link_rate == 1.0` for canonical cases with human review/approval refs.
- `rubber_stamp_divergence_review_required_count >= 1` for the seeded design-error-after-ineffective-review case.
- `learning_without_attribution_count == 0`.
- `growth_without_assurance_delta_count == 0`.
- All S13 false-clear counts are `0`.

## Contract Dictionary

Add runtime constants in `src/polisyos/runtime/quality/layer2_post_deploy_accountability.py`:

```python
LAYER2_S13_POST_DEPLOY_ACCOUNTABILITY_SCHEMA_VERSION = (
    "policyos.policy_design_case.layer2_s13_post_deploy_accountability.v1"
)
LAYER2_S13_POST_DEPLOY_ACCOUNTABILITY_RULE_VERSION = (
    "policyos.layer2.s13.post_deploy_accountability.v1"
)
S13_ACCOUNTABILITY_FLOOR_ID = "s13_accountability"
S13_FALSE_CLEAR_FIELDS = (
    "post_policy_data_as_pre_policy_evidence",
    "learned_prior_in_current_evidence_slot",
    "unattributable_updates_model",
    "silent_closed_case_rewrite",
    "learning_without_attribution",
    "envelope_shrink_without_assurance_delta",
    "b_update_before_a_baseline",
    "implementation_failure_as_theory_refutation",
    "outcome_learning_without_counterfactual",
    "s13_as_production_or_recommendation_authority",
)
```

Add strict Pydantic contracts:

- `DeploymentDossier`
- `DivergenceRecord`
- `LearningUpdateProposal`
- `CertifiedEnvelopeDelta`
- `EnvelopeRevision`
- `AssuranceCaseDelta`
- `PostDeployMapeKTrace`
- `PostDeployAccountabilitySummary`

Add literal types:

- `DeploymentReadinessDisposition = Literal["deployable", "advisory_only", "accountability_only", "blocked"]`
- `DivergenceAttributionClass = Literal["design_error", "evidence_error", "regime_error", "coupling_error", "world_change", "strategic_response", "implementation_failure", "unattributable"]`
- `AttributionStatus = Literal["attributed", "unattributable", "pending"]`
- `LearningChangeControlClass = Literal["pre_authorized", "reissue_required", "envelope_shrink", "historical_prior_only", "public_accountability_note"]`
- `LearningUpdateTarget = Literal["substrate", "a_firewall", "b_prior", "calibration", "regime_classifier", "coupling_classifier", "strategic_response_model", "capacity_feasibility_model", "memory", "corpus_label", "envelope", "public_accountability_note"]`
- `LifecycleReissueDisposition = Literal["fail", "withdraw_required", "supersede_required", "reissue_required", "review_required", "pass"]` mirroring `_lifecycle_reissue_status(...)`, not a new S13 status lattice.
- `EnvelopeRevisionDirection = Literal["expand", "shrink", "hold", "split"]`
- `AssuranceCaseChange = Literal["strengthened", "weakened", "invalidated", "unchanged"]`
- `PostDeployMapeKPhase = Literal["monitor", "analyze", "plan", "execute", "knowledge"]`
- `OversightLinkedAccountabilityState = Literal["not_applicable", "effective_oversight_linked", "rubber_stamp_divergence_review_required"]`

Add producer/helper functions:

- `build_deployment_dossier(...) -> DeploymentDossier`
- `classify_post_deploy_divergence(...) -> DivergenceRecord`
- `build_post_deploy_mape_k_trace(...) -> PostDeployMapeKTrace`
- `build_learning_update_proposal(...) -> LearningUpdateProposal`
- `build_certified_envelope_delta(...) -> CertifiedEnvelopeDelta`
- `build_assurance_case_delta(...) -> AssuranceCaseDelta`
- `build_envelope_revision(...) -> EnvelopeRevision`
- `verify_post_deploy_learning_authority(...) -> tuple[str, ...]`
- `summarize_post_deploy_accountability(...) -> PostDeployAccountabilitySummary`
- `build_s13_post_deploy_accountability_posture(...) -> dict[str, Any]`

S13 PDC posture payload fields returned by `build_s13_post_deploy_accountability_posture(...)` and accepted by `Layer2S13PostDeployAccountabilityPostureInput`:

- In `src/polisyos/pdc/_impl/layer2_design_search.py`, encode S13 enum-valued fields as local `Literal[...]` string types. Do not import S13 runtime aliases or the S13 runtime producer module into PDC internals.
- `phase: Literal["design_time_gate", "post_deploy_finalized"]`
- `accountability_posture_ref: str`
- `deployment_dossier_ref: str`
- `divergence_record_refs: tuple[str, ...] = ()`
- `learning_update_proposal_refs: tuple[str, ...] = ()`
- `envelope_revision_ref: str | None`
- `certified_envelope_delta_ref: str | None`
- `assurance_case_delta_ref: str | None`
- `attribution_status: Literal["attributed", "unattributable", "pending"] | None`
- `attribution_classes: tuple[Literal["design_error", "evidence_error", "regime_error", "coupling_error", "world_change", "strategic_response", "implementation_failure", "unattributable"], ...] = ()`
- `learning_change_control_classes: tuple[Literal["pre_authorized", "reissue_required", "envelope_shrink", "historical_prior_only", "public_accountability_note"], ...] = ()`
- `lifecycle_reissue_disposition: Literal["fail", "withdraw_required", "supersede_required", "reissue_required", "review_required", "pass"] | None`
- `envelope_revision_direction: Literal["expand", "shrink", "hold", "split"] | None`
- `assurance_case_change: Literal["strengthened", "weakened", "invalidated", "unchanged"] | None`
- `mape_k_trace_ref: str | None`
- `public_revision_state_ref: str | None`
- `public_accountability_note_ref: str | None`
- `action_item_status: Literal["open", "closed", "pending", "blocked"] | None`
- `action_item_closure_refs: tuple[str, ...] = ()`
- `human_decision_request_refs: tuple[str, ...] = ()`
- `human_decision_record_refs: tuple[str, ...] = ()`
- `oversight_effectiveness_ref: str | None`
- `oversight_accountability_state: Literal["not_applicable", "effective_oversight_linked", "rubber_stamp_divergence_review_required"] | None`
- `a_before_b_status: Literal["pass", "fail"] | None`
- `historical_prior_influence_refs: tuple[str, ...] = ()`
- `replay_digest: str`
- `authority_boundary: AuthorityBoundary`
- `may_not_use_for: tuple[str, ...]`
- `rule_version_ref: str`

Design-time gate-only contract:

- When `phase == "design_time_gate"`, S13 posture may carry `accountability_posture_ref`, `deployment_dossier_ref`, monitorability/readiness fields, governance request refs, authority boundary, and replay digest.
- When `phase == "design_time_gate"`, these post-deploy fields must be empty or `None`: `divergence_record_refs`, `learning_update_proposal_refs`, `envelope_revision_ref`, `certified_envelope_delta_ref`, `assurance_case_delta_ref`, `attribution_status`, `attribution_classes`, `learning_change_control_classes`, `lifecycle_reissue_disposition`, `envelope_revision_direction`, `assurance_case_change`, `mape_k_trace_ref`, `public_revision_state_ref`, `public_accountability_note_ref`, `action_item_status`, `action_item_closure_refs`, `oversight_accountability_state`, `a_before_b_status`, and `historical_prior_influence_refs`.
- Non-empty post-deploy refs are allowed only when `phase == "post_deploy_finalized"` after S9 projection records exist. Supplying post-deploy refs to the design-time S2 injection path is a negative-control failure under A-before-B and Lucas boundaries.

Authority posture:

- `authoritative_for`: `post_deploy_accountability`, `deployment_monitorability`, `divergence_attribution`, `learning_update_proposal`, `post_deploy_mape_k_trace`, `envelope_revision`, `assurance_case_delta`, `public_accountability_note`.
- `may_not_use_for`: `production_rollout_authority`, `recommendation_authority`, `publication_authority`, `approval_authority`, `scorecard_authority`, `pre_policy_evidence`, `current_evidence_slot`, `preference_learning`, `automated_value_learning`, `naive_ml_update`, `s14_universality`, `llm_attribution_authority`, `local_governance_enum_for_reissue`.

## File Map

Create:

- `src/polisyos/runtime/quality/layer2_post_deploy_accountability.py`
- `tests/unit/runtime/quality/test_layer2_s13_post_deploy_accountability.py`
- `tests/fixtures/layer2/s13/s13_post_deploy_case_signals.json`
- `tests/fixtures/layer2/s13/s13_post_deploy_expert_labels.json`
- `tests/fixtures/layer2/s13/negative_controls/monitoring_missing_for_deployable_probe.json`
- `tests/fixtures/layer2/s13/negative_controls/post_policy_data_as_pre_policy_evidence_probe.json`
- `tests/fixtures/layer2/s13/negative_controls/learned_prior_in_current_evidence_slot_probe.json`
- `tests/fixtures/layer2/s13/negative_controls/unattributable_updates_model_probe.json`
- `tests/fixtures/layer2/s13/negative_controls/silent_closed_case_rewrite_probe.json`
- `tests/fixtures/layer2/s13/negative_controls/learning_without_attribution_probe.json`
- `tests/fixtures/layer2/s13/negative_controls/envelope_shrink_without_assurance_delta_probe.json`
- `tests/fixtures/layer2/s13/negative_controls/b_update_before_a_firewall_probe.json`
- `tests/fixtures/layer2/s13/negative_controls/implementation_failure_as_theory_refutation_probe.json`
- `tests/fixtures/layer2/s13/negative_controls/outcome_learning_without_counterfactual_probe.json`
- `tests/fixtures/layer2/s13/negative_controls/s13_as_production_or_recommendation_authority_probe.json`
- `architecture/policy_design_case/layer2_s13_post_deploy_accountability_manifest.json`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s13_post_deploy_accountability.py`

Modify:

- `src/polisyos/runtime/quality/__init__.py`
- `src/polisyos/pdc/_impl/layer2_design_search.py`
- `src/polisyos/pdc/__init__.py`
- `src/polisyos/runtime/quality/projection_semantics.py`
- `src/polisyos/runtime/quality/public_export.py`
- `tools/quality/validation/run_universal_outcome_corpus.py`
- `tools/quality/validation/check_policy_design_case_layer2_readiness.py`
- `architecture/policy_design_case/cluster_ownership_map.toml`
- `architecture/policy_design_case/layer2_artifact_traceability.toml`
- `architecture/policy_design_case/inventory.json`
- `tests/unit/pdc/test_layer2_s2_design_search.py`
- `tests/unit/pdc/test_layer2_readiness_contracts.py`
- `tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py`
- `tests/unit/runtime/quality/test_public_export.py`
- `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`
- Prior Layer 2 repo-quality snapshot tests that assert exact inventory counts.

Read/reuse first; do not modify unless a failing test proves a contract gap:

- `src/polisyos/runtime/quality/case_lifecycle.py`
- `src/polisyos/runtime/quality/ddm_monitoring.py`
- `src/polisyos/runtime/quality/calibration_ledger.py`
- `src/polisyos/runtime/quality/human_review.py`
- `src/polisyos/runtime/quality/layer2_delegation.py`
- `src/polisyos/runtime/quality/layer2_resource_economics.py`

Do not modify unless a validator proves it is necessary:

- `architecture/policy_design_case/layer2_slice_cell_matrix.toml`
- `architecture/policy_design_case/layer2_floor_governance.toml`

## Task 1: Red-First S13 Semantic And Negative Tests

Write failing tests before adding implementation.

Runtime tests in `tests/unit/runtime/quality/test_layer2_s13_post_deploy_accountability.py`:

- `test_s13_contracts_are_strict_replayable_and_exported`
- `test_deployment_dossier_requires_monitoring_design_before_deployable`
- `test_monitorability_floor_allows_accountability_only_without_learning`
- `test_divergence_record_requires_attribution_before_learning`
- `test_divergence_record_composes_typed_diagnostic_record`
- `test_unattributable_divergence_records_accountability_without_training`
- `test_design_error_after_rubber_stamp_review_marks_oversight_accountability_state`
- `test_mape_k_trace_requires_monitor_analyze_plan_execute_knowledge_refs`
- `test_learning_update_proposal_enforces_a_before_b_sequence`
- `test_learning_update_proposal_wraps_validated_ex_post_learning_record`
- `test_learning_update_proposal_rejects_contaminated_ex_post_learning_record`
- `test_learning_update_targets_component_with_attribution_and_governance`
- `test_reissue_change_control_maps_to_existing_lifecycle_reissue_status`
- `test_historical_prior_influence_requires_ttl_decay_and_contamination_controls`
- `test_envelope_revision_can_shrink_on_seeded_disconfirmation`
- `test_envelope_revision_can_expand_on_validated_reusable_learning`
- `test_certified_envelope_delta_materializes_s12_deferred_delta_ref`
- `test_envelope_shrink_split_gated_by_assurance_delta_and_latency_not_s12_growth_entry`
- `test_assurance_case_delta_required_for_learning_update`
- `test_action_item_closure_rate_counts_owned_deadline_closure`
- `test_high_stakes_reissue_requires_human_decision_record_ref`
- `test_post_policy_data_cannot_fill_pre_policy_evidence_slot`
- `test_learned_prior_cannot_be_current_evidence`
- `test_learned_prior_firewall_rejects_prefixed_historical_prior_refs_in_evidence_slots`
- `test_implementation_failure_does_not_refute_policy_theory`
- `test_s13_summary_requires_exact_false_clear_keys`
- `test_no_preference_learning_or_production_authority_from_s13`

PDC tests in `tests/unit/pdc/test_layer2_s2_design_search.py` and `tests/unit/pdc/test_layer2_readiness_contracts.py`:

- `test_layer2_s13_post_deploy_accountability_posture_input_is_strict_and_exported`
- `test_s2_consumes_s13_posture_as_reissue_accountability_constraint_not_recommendation_authority`
- `test_s2_s13_replay_digest_changes_only_when_accountability_posture_changes`
- `test_s2_s13_defaults_preserve_legacy_cas_payloads`
- `test_s2_s13_persisted_search_ledger_round_trips_accountability_refs`
- `test_s2_s13_design_time_gate_posture_is_gate_only_without_post_deploy_refs`
- `test_s2_s13_handoff_records_accountability_refs_not_production_authority`
- `test_s2_s13_uses_existing_governance_decision_refs_without_local_reissue_enum`
- `test_s2_does_not_import_layer2_post_deploy_accountability`

Projection and export tests in `tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py` and `tests/unit/runtime/quality/test_public_export.py`:

- `test_expert_machine_projection_surfaces_attribution_and_envelope_revision`
- `test_public_projection_surfaces_accountability_note_and_preserves_historical_meaning`
- `test_public_accountability_note_projects_existing_public_revision_state`
- `test_public_projection_reuses_public_revision_state_silent_upgrade_firewall`
- `test_reviewer_projection_surfaces_mape_k_trace_action_closure_oversight_state_and_existing_reissue_disposition`
- `test_projection_blocks_learning_update_as_current_evidence_authority`
- `test_projection_blocks_s13_as_universality_or_production_authority`

Corpus route tests in `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`:

- `test_w12d_emits_s13_post_deploy_blocks_for_13_cases`
- `test_w12d_s13_monitorability_floor_and_attribution_gate_pass`
- `test_w12d_s13_envelope_revision_includes_shrink_and_expand`
- `test_w12d_s13_envelope_shrink_latency_is_recorded_for_seeded_disconfirmation`
- `test_w12d_s13_negative_controls_have_zero_false_clears`
- `test_w12d_s13_preserves_s2_shadow_only_outcome_effects`
- `test_w12d_s13_design_time_gate_posture_does_not_inject_post_deploy_learning_refs`
- `test_w12d_s13_gold_labels_cover_all_13_cases_without_leaking_gold_into_signals`

Manifest tests in `tests/repo_quality/tools/test_policy_design_case_layer2_s13_post_deploy_accountability.py`:

- `test_s13_manifest_exists_and_declares_closure_contract`
- `test_s13_manifest_registers_six_artifacts_and_firewalls`
- `test_s13_manifest_does_not_claim_new_closed_cell`
- `test_s13_manifest_keeps_current_open_cell_count_zero`
- `test_s13_artifact_traceability_is_implemented_once`
- `test_s13_cluster_map_advances_envelope_growth_without_reopening_cell`
- `test_s13_inventory_adds_one_manifest_and_no_s14_claims`
- `test_s13_readiness_validator_accepts_post_deploy_accountability`

Fixture requirements:

- 13 canonical post-deploy case signals, one per W12D case.
- At least one seeded disconfirmation case.
- At least one validated reuse case.
- At least one unattributable case.
- At least one implementation-failure case.
- At least one strategic-response/Lucas firewall case.
- At least one case with human-review/approval refs linked to oversight-effectiveness telemetry.
- At least one attributed design-error case whose approving review has `effective_oversight == false` or `rubber_stamp_risk == "high"` so `rubber_stamp_divergence_review_required` is exercised.
- Negative probes for every `S13_FALSE_CLEAR_FIELDS` value.
- The learned-prior/current-evidence negative probe must include a positive detector branch with a recognized historical-prior prefix, preferably `historical-prior-influence:`, proving `historical_prior_claim_evidence_issues(...)` is actually active.
- `monitoring_missing_for_deployable_probe.json` is an extra monitorability-floor probe, not a `false_clear_counts` member.
- `b_update_before_a_firewall_probe.json` must set JSON `false_clear_field` to `b_update_before_a_baseline`.

Execution steps:

- [ ] **Step 1: Add runtime red tests and S13 fixtures** in `tests/unit/runtime/quality/test_layer2_s13_post_deploy_accountability.py` and `tests/fixtures/layer2/s13`.
- [ ] **Step 2: Add PDC, projection, public-export, W12D, and manifest red tests** in the files named above.
- [ ] **Step 3: Run the red command** and verify the expected missing-module/missing-contract failures.
- [ ] **Step 4: Commit only tests and fixtures** with `test: add layer2 s13 post-deploy accountability red tests`.

Expected red command:

```bash
cd policy-engine
uv run pytest \
  tests/unit/runtime/quality/test_layer2_s13_post_deploy_accountability.py \
  tests/unit/pdc/test_layer2_s2_design_search.py \
  tests/unit/pdc/test_layer2_readiness_contracts.py \
  tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py \
  tests/unit/runtime/quality/test_public_export.py \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s13_post_deploy_accountability.py \
  -q
```

Expected red output:

- Import failure for `polisyos.runtime.quality.layer2_post_deploy_accountability`.
- Missing `Layer2S13PostDeployAccountabilityPostureInput`.
- Missing S13 corpus blocks/summary fields.
- Missing S13 manifest.

Commit:

```bash
git add tests/unit/runtime/quality/test_layer2_s13_post_deploy_accountability.py \
  tests/unit/pdc/test_layer2_s2_design_search.py \
  tests/unit/pdc/test_layer2_readiness_contracts.py \
  tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py \
  tests/unit/runtime/quality/test_public_export.py \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s13_post_deploy_accountability.py \
  tests/fixtures/layer2/s13
git commit -m "test: add layer2 s13 post-deploy accountability red tests"
```

## Task 2: Contracts, Producer, Accountability Gate, And Anti-Learning Firewalls

Implement `src/polisyos/runtime/quality/layer2_post_deploy_accountability.py`.

Implementation requirements:

- Strict Pydantic models with `extra="forbid"`.
- Google-style docstrings for public models/functions.
- Deterministic `replay_digest` built from stable semantic fields.
- Distinct deployment, observation, detection, attribution, reissue, and replay timestamps.
- `DeploymentDossier` blocks `deployable` when monitoring design, owners, or reissue path are missing; it should wrap or validate the dict shape produced by `build_implementation_monitoring_evaluation_record(...)` / `validate_implementation_monitoring_evaluation_record(...)` instead of importing a non-existent monitoring record class or duplicating monitoring-plan semantics.
- `DivergenceRecord` composes the shared `TypedDiagnosticRecord` through a `diagnostic: TypedDiagnosticRecord` field and carries action-item closure fields.
- Divergence linked to ineffective/high-risk approval review sets `oversight_accountability_state == "rubber_stamp_divergence_review_required"` and leaves authority with the existing governance/human-decision path.
- `PostDeployMapeKTrace` requires monitor/analyze/plan/execute/knowledge refs.
- `accountability_only` is allowed only when monitorability exists but learnability is blocked.
- `LearningUpdateProposal` wraps the dict produced by `build_ex_post_learning_record(...)` and accepted by `validate_ex_post_learning_record(...)`; it adds attribution, source refs, A-before-B result, explicit change-control class, update targets, and governance refs for high-stakes changes.
- S13 must delegate clean/contaminated learning checks to the existing `case_lifecycle` validation path where possible, including `detect_memory_contamination(...)`, instead of duplicating hidden-ref/canary-token logic.
- `LearningChangeControlClass == "reissue_required"` maps to `_lifecycle_reissue_status(...)` outputs and reviewer-visible lifecycle actions; no new S13 reissue status set is allowed.
- Historical-prior influence fields include provenance, TTL, decay, contamination controls, and a recognized historical-prior ref prefix. Current-evidence-slot checks should reuse `historical_prior_claim_evidence_issues`.
- `CertifiedEnvelopeDelta` materializes S12 `EnvelopeGrowthEntry.certified_envelope_delta_ref` string refs when present; do not modify S12 ledgers or add direction to `EnvelopeGrowthEntry`.
- `EnvelopeRevision` requires `AssuranceCaseDelta` for every non-hold revision.
- Shrink/split revisions carry disconfirming signal time, revision effective time, and shrink latency. This satisfies the architecture metric without adding a separate latency artifact.
- Shrink/split revisions are native S13 assurance behavior and are gated by `AssuranceCaseDelta` plus latency, not by S12 growth-only ledger counting.
- `verify_post_deploy_learning_authority` returns exact false-clear keys.
- `summarize_post_deploy_accountability` reports closure metrics and false-clear counts.
- Runtime package exports S13 public contracts from `src/polisyos/runtime/quality/__init__.py`.

Anti-learning firewalls:

- Post-policy data cannot populate pre-policy evidence or current evidence slots.
- Learned priors cannot become current evidence; the negative control must prove this with a recognized historical-prior ref prefix so the existing C41 detector fires.
- Unattributable or pending records cannot update models, priors, envelopes, or recommendations.
- Implementation failure cannot refute policy theory unless independent attribution supports it.
- High-stakes reissue or envelope revision cannot bypass S7 `HumanDecisionRecord` / governance-decision refs.
- No S13 artifact may declare production, publication, approval, recommendation, scorecard, S14 universality, preference learning, automated value learning, or LLM attribution authority.

Execution steps:

- [ ] **Step 1: Add module constants, literals, and strict models** in `src/polisyos/runtime/quality/layer2_post_deploy_accountability.py`.
- [ ] **Step 2: Implement producer helpers and deterministic replay digests** for dossier, divergence, MAPE-K, learning proposal, envelope delta, envelope revision, assurance delta, and summary.
- [ ] **Step 3: Implement anti-learning firewalls** so every `S13_FALSE_CLEAR_FIELDS` key is produced and summarized.
- [ ] **Step 4: Export runtime contracts** from `src/polisyos/runtime/quality/__init__.py`.
- [ ] **Step 5: Run runtime tests and ruff**, then commit `feat: add layer2 s13 post-deploy accountability contracts`.

Verification:

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer2_s13_post_deploy_accountability.py -q
uv run ruff check src/polisyos/runtime/quality/layer2_post_deploy_accountability.py tests/unit/runtime/quality/test_layer2_s13_post_deploy_accountability.py
```

Expected output:

- Runtime S13 tests pass.
- Ruff reports no issues for the new module and tests.

Commit:

```bash
git add src/polisyos/runtime/quality/layer2_post_deploy_accountability.py \
  src/polisyos/runtime/quality/__init__.py \
  tests/unit/runtime/quality/test_layer2_s13_post_deploy_accountability.py
git commit -m "feat: add layer2 s13 post-deploy accountability contracts"
```

## Task 3: Wire S13 Posture Into PDC Context, Semantics, And Export

Wire S13 without importing runtime-quality implementation into S2 internals.

Implementation requirements:

- Add `Layer2S13PostDeployAccountabilityPostureInput` to `src/polisyos/pdc/_impl/layer2_design_search.py`.
- Keep the posture input strict and serializable.
- Add optional S13 posture to the Layer 2 design search request/context.
- S2 may consume S13 only as reissue/accountability constraint and replay context.
- S2 must not treat S13 posture as recommendation, production, approval, or evidence authority.
- Add S13 refs to the design handoff metadata when present.
- Add S13 governance refs to the handoff when a high-stakes reissue or envelope revision is proposed.
- Replay digest changes only when S13 posture changes.
- Legacy CAS payloads without S13 posture remain valid.
- `src/polisyos/pdc/_impl/layer2_design_search.py` must not import `layer2_post_deploy_accountability`.

Concrete S2 touch points:

- Add `Layer2S13PostDeployAccountabilityPostureInput` beside the existing S10/S11/S12 posture input models and export it from `src/polisyos/pdc/__init__.py`.
- Extend `SearchLedger` with these S13 fields: `accountability_posture_refs`, `accountability_phase`, `deployment_dossier_refs`, `divergence_record_refs`, `learning_update_proposal_refs`, `envelope_revision_refs`, `certified_envelope_delta_refs`, `assurance_case_delta_refs`, `mape_k_trace_refs`, `public_revision_state_refs`, `public_accountability_note_refs`, `action_item_statuses`, `action_item_closure_refs`, `human_decision_request_refs`, `human_decision_record_refs`, `historical_prior_influence_refs`, `attribution_status`, `lifecycle_reissue_dispositions`, `envelope_revision_direction`, `oversight_accountability_state`, `a_before_b_status`, and `accountability_authority_boundary`. Defaults must preserve legacy CAS payloads.
- Add `accountability_posture` to `Layer2S2DesignSearchRun` and to `run_s2_shadow_design_loop(...)`.
- Thread the posture through `_constraint_store`, `_search_ledger`, `_design_record`, `_cluster_interfaces`, `_handoff_records`, and `_deterministic_replay_key`.
- Add these S13 helper functions: `_s13_constraint_entries`, `_s13_design_record_ledger_refs`, `_s13_handoff_refs`, `_s13_handoff_record`, `_s13_cluster_interface`, and `_s13_projection_fields`.
- Include S13 posture in `project_s2_design_search(...)` and in the serialized run payload only when present.
- Add a persisted CAS round-trip test for S13 search-ledger refs, mirroring `test_s2_s12_persisted_search_ledger_round_trips_resource_refs`.
- Add a no-import test that checks for absence of `polisyos.runtime.quality.layer2_post_deploy_accountability`, `layer2_post_deploy_accountability`, and `build_s13_post_deploy_accountability_posture` in S2 internals.

Projection semantics:

- Add S13 projection checks to `src/polisyos/runtime/quality/projection_semantics.py`.
- Add `verify_s13_post_deploy_accountability_projection_consumer_contract(...)` with S13-specific required fields and deny lists.
- EXPERT and MACHINE views include attribution, learning change-control class, envelope revision, assurance delta, source refs, and replay digest.
- PUBLIC view includes the accountability note and revision status by projecting existing `public_revision_states`, preserving closed-case historical meaning and keeping `authority_role == "projection_only"`.
- REVIEWER view includes owners, deadlines, pending attribution, MAPE-K trace, action-item closure state, oversight-effectiveness link, oversight-accountability state, and reissue actions mapped from existing lifecycle reissue dispositions.
- Projection checks block S13 posture as current evidence, recommendation, production, approval, or universality authority.

Public export:

- Update `src/polisyos/runtime/quality/public_export.py` so public accountability notes are exported as accountability/revision notes, not as evidence or corrected historical truth.
- Add a sibling `_apply_s13_post_deploy_accountability_projection(...)` hook in the same style as `_apply_s12_resource_projection(...)`.
- The hook should project the existing `_public_revision_state(...)`/`semantic_audit.public_revision_states` object when available; it must not duplicate silent-upgrade or authority-leak detection already covered by `policy_design_public_revision_state_silent_upgrade` and `policy_design_public_revision_state_authority_leak`.
- Include S13 verification and public projection in `semantic_audit` only when S13 posture is present.
- Add export fields only when S13 posture is present.

Execution steps:

- [ ] **Step 1: Add the strict PDC posture input and exports** in `layer2_design_search.py` and `src/polisyos/pdc/__init__.py`.
- [ ] **Step 2: Thread S13 posture through S2 internals** across ledger, design record, constraints, handoffs, cluster interfaces, replay key, projection serialization, and CAS compatibility.
- [ ] **Step 3: Add S13 projection-semantics verifier and projection fields** in `projection_semantics.py`.
- [ ] **Step 4: Add the S13 public-export hook** in `public_export.py`.
- [ ] **Step 5: Run PDC/projection/export tests and ruff**, then commit `feat: wire layer2 s13 accountability posture into projections`.

Verification:

```bash
cd policy-engine
uv run pytest \
  tests/unit/pdc/test_layer2_s2_design_search.py \
  tests/unit/pdc/test_layer2_readiness_contracts.py \
  tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py \
  tests/unit/runtime/quality/test_public_export.py \
  -q
uv run ruff check src/polisyos/pdc/_impl/layer2_design_search.py src/polisyos/pdc/__init__.py src/polisyos/runtime/quality/projection_semantics.py src/polisyos/runtime/quality/public_export.py
```

Expected output:

- PDC, projection, and public export tests pass.
- Ruff reports no issues for touched modules.

Commit:

```bash
git add src/polisyos/pdc/_impl/layer2_design_search.py \
  src/polisyos/pdc/__init__.py \
  src/polisyos/runtime/quality/projection_semantics.py \
  src/polisyos/runtime/quality/public_export.py \
  tests/unit/pdc/test_layer2_s2_design_search.py \
  tests/unit/pdc/test_layer2_readiness_contracts.py \
  tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py \
  tests/unit/runtime/quality/test_public_export.py
git commit -m "feat: wire layer2 s13 accountability posture into projections"
```

## Task 4: Canonical Corpus Route Wiring - 13-Case S13 Coverage

Wire S13 into `tools/quality/validation/run_universal_outcome_corpus.py`.

Route design:

- Avoid a circular dependency between S2 design search and S13 post-deploy finalization.
- Build a design-time accountability posture from dossier/accountability fixture refs when S13 constraints are needed by S2.
- Run the existing S2 path with optional S13 posture as a constraint.
- Run S9 projection/revision records.
- Finalize S13 post-deploy accountability blocks after S9 records exist.
- Do not treat finalized S13 learning as a current evidence input to the same case replay.

Target route:

```text
S4 -> S5 -> S6 -> S7 -> S8 -> S10 -> S11 -> S12
  -> S13 design-time accountability posture
  -> S2
  -> S9
  -> S13 finalized post-deploy accountability block
```

Implementation requirements:

- Load the 13 canonical S13 case fixtures.
- Load S13 expert labels and negative-control probes.
- Produce a typed S13 block per canonical case.
- Emit `s13_post_deploy_accountability_summary`.
- Include S13 refs in machine-readable per-case output.
- Preserve S2 `outcome_effects_posture == "shadow_only"` behavior from S10/S12.
- Summary must include:
  - `case_count`
  - `monitorability_rate`
  - `a_before_b_ratio`
  - `attribution_resolution_rate`
  - `envelope_shrink_count`
  - `envelope_expansion_count`
  - `envelope_shrink_latency_recorded_count`
  - `unattributable_accountability_without_training_count`
  - `mape_k_trace_completeness_rate`
  - `action_item_closure_rate`
  - `oversight_effectiveness_link_rate`
  - `rubber_stamp_divergence_review_required_count`
  - `learning_without_attribution_count`
  - `growth_without_assurance_delta_count`
  - `false_clear_counts`

Concrete W12D touch points:

- Import `Layer2S13PostDeployAccountabilityPostureInput` from `polisyos.pdc`.
- Import S13 runtime constants/builders from `polisyos.runtime.quality.layer2_post_deploy_accountability`.
- Add `S13_CASE_SIGNALS_PATH`, `S13_EXPERT_LABELS_PATH`, and `S13_NEGATIVE_CONTROL_PROBE_PATHS`.
- Add `_s13_post_deploy_accountability_case_block(...)`, `_s13_accountability_posture_input(...)`, `_s13_post_deploy_accountability_summary(...)`, `_s13_negative_control_probe_results(...)`, and `_s13_matches_gold(...)` as siblings of the S12 helpers.
- Extend `_s2_design_search_summary(...)` with an optional `s13_post_deploy_accountability`/design-time posture argument and keep non-UA cases on `canonical_outcome_effect == "none_shadow_only"`.
- Add `accountability_posture=...` to the `run_s2_shadow_design_loop(...)` calls only after the S2 PDC contract exists.
- The design-time posture built by `_s13_accountability_posture_input(...)` must set `phase="design_time_gate"` and must leave all post-deploy learning refs empty or `None`. The finalized `s13_post_deploy_accountability` block is emitted only after S9 records exist.
- Add `s13_post_deploy_accountability` to each case output and `s13_post_deploy_accountability_summary` to the top-level report.

Required summary assertions:

```python
assert summary["case_count"] == 13
assert summary["monitorability_rate"] == 1.0
assert summary["a_before_b_ratio"] == 1.0
assert summary["attribution_resolution_rate"] == 1.0
assert summary["envelope_shrink_count"] >= 1
assert summary["envelope_expansion_count"] >= 1
assert summary["envelope_shrink_latency_recorded_count"] >= 1
assert summary["unattributable_accountability_without_training_count"] >= 1
assert summary["mape_k_trace_completeness_rate"] == 1.0
assert summary["action_item_closure_rate"] == 1.0
assert summary["oversight_effectiveness_link_rate"] == 1.0
assert summary["rubber_stamp_divergence_review_required_count"] >= 1
assert summary["learning_without_attribution_count"] == 0
assert summary["growth_without_assurance_delta_count"] == 0
assert all(count == 0 for count in summary["false_clear_counts"].values())
```

Execution steps:

- [ ] **Step 1: Add S13 corpus fixtures and negative probes** under `tests/fixtures/layer2/s13`.
- [ ] **Step 2: Add W12D S13 imports, paths, and helper functions** as siblings of the S12 route helpers.
- [ ] **Step 3: Thread design-time S13 posture into `_s2_design_search_summary(...)`** without letting finalized S13 learning become same-run evidence.
- [ ] **Step 4: Emit per-case `s13_post_deploy_accountability` blocks and top-level `s13_post_deploy_accountability_summary`**.
- [ ] **Step 5: Run W12D repo-quality tests**, then commit `feat: classify layer2 s13 post-deploy accountability coverage`.

Verification:

```bash
cd policy-engine
uv run pytest tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py -q
```

Expected output:

- W12D corpus tests pass with 13 S13 case blocks.
- Summary shows both shrink and expansion coverage.
- All S13 negative-control false-clear counts are zero.

Commit:

```bash
git add tools/quality/validation/run_universal_outcome_corpus.py \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py \
  tests/fixtures/layer2/s13
git commit -m "feat: classify layer2 s13 post-deploy accountability coverage"
```

## Task 5: S13 Manifest, Readiness Validator, Traceability, And Inventory

Create `architecture/policy_design_case/layer2_s13_post_deploy_accountability_manifest.json`.

Use `architecture/policy_design_case/layer2_s10_outcome_prediction_manifest.json` as the structural precedent for S13's advance-only shape: `cells_closed == []` plus `layer_cells_advanced`. Use S12 only as the nearest precedent for readiness false-clear and inventory-count patterns, not for cell closure semantics.

Manifest requirements:

- `slice == "S13"`.
- `schema_version == "policyos.policy_design_case.layer2_s13_post_deploy_accountability_manifest.v1"`.
- `status == "active"`.
- `owner == "governance-board"`.
- `depends_on == ["S7", "S9", "S12"]`.
- `slice_label == "post_deploy_accountability_learning"`.
- `cells_closed == []`.
- `layer_cells_advanced == ["DESIGNER_ITSELF.envelope_growth"]`.
- `expected_current_open_cell_count == 0`.
- `remaining_open_cells == []`.
- `burn_down_complete == true`.
- `floor_id == "s13_accountability"`.
- Six implemented artifacts:
  - `DeploymentDossier`
  - `DivergenceRecord`
  - `LearningUpdateProposal`
  - `EnvelopeRevision`
  - `CertifiedEnvelopeDelta`
  - `AssuranceCaseDelta`
- Firewalls:
  - `anti_learning_authority_boundary`
  - `c41_learned_prior_current_evidence_slot`
  - `a_before_b_sequence`
  - `closed_case_replay_integrity`
  - `lucas_post_policy_pre_policy_evidence`
  - `s7_governance_decision_bypass`
- Surfaces:
  - public accountability note
  - expert projection
  - machine projection
  - reviewer action/reissue view
- Embedded trace requirements:
  - MAPE-K monitor/analyze/plan/execute/knowledge refs
  - `TypedDiagnosticRecord` composition refs
  - action-item closure refs
  - oversight-effectiveness refs where human review/approval exists
  - oversight-accountability state coverage for ineffective/rubber-stamp review
  - public revision-state refs projected as accountability notes
  - lifecycle reissue disposition refs mapped from the existing `case_lifecycle` lattice
- Closure metrics from this plan.

Readiness validator:

- Update `tools/quality/validation/check_policy_design_case_layer2_readiness.py` to validate the S13 manifest, traceability, inventory, and no-open-cell invariant.
- Keep S13 as an advanced layer cell, not a newly closed open cell.
- Validate exact false-clear fields.
- Validate the six artifacts are implemented once in traceability.
- Validate S13 MAPE-K trace, action-item closure, S7 oversight-effectiveness refs, oversight-accountability state, public revision-state projection, and lifecycle reissue-disposition mapping are declared in the manifest metrics/surfaces.
- Validate no S14/universality/production authority claim exists.

Concrete readiness-validator touch points:

- Add `DEFAULT_S13_POST_DEPLOY_ACCOUNTABILITY_MANIFEST_PATH`.
- Add `S13_REQUIRED_ARTIFACTS`, `S13_REQUIRED_AUTHORITY_SCOPE`, `S13_REQUIRED_DENY`, `S13_FALSE_CLEAR_FIELDS`, and `S13_INVENTORY_ID`.
- Load `"s13_post_deploy_accountability"` in `load_layer2_readiness_payloads(...)`.
- Add `_validate_s13_post_deploy_accountability(...)` and call it from `validate_layer2_readiness(...)` after S12 validation.
- Update all existing future-slice maturity guards that currently reject implemented S13 artifacts:
  - Change `S9_LATER_SLICES = {"S13", "S14"}` to `{"S14"}`. This single constant feeds both the S9 guard (`layer2_s9_future_slice_maturity_invalid`) and the S10 guard (`layer2_s10_future_slice_maturity_invalid`).
  - Change the S11 inline traceability guard `row.get("slice") in {"S13", "S14"}` to `{"S14"}` for `layer2_s11_future_slice_maturity_invalid`.
  - Change the S12 inline traceability guard `row.get("slice") in {"S13", "S14"}` to `{"S14"}` for `layer2_s12_future_slice_maturity_invalid`.
  - Do not add S13 assignments to `layer2_slice_cell_matrix.toml`; if an implementation does add S13 assignment rows, update the S11 future-cell guard (`slice_name in {"S13", "S14"}`) deliberately while preserving rejection for S14.
- Update all inventory-count guards that assume S12 is the latest slice:
  - Change the S11-era shared guard `_inventory_layer2_artifact_count(inventory) not in {19, 20}` to allow S13 count `21`, and update the message from "19 after S11 or 20 after S12" to include "21 after S13".
  - Change the S12 exact guard `_inventory_layer2_artifact_count(inventory) != 20` so full readiness after S13 accepts `21` while S12 repo-quality tests remain scoped to the S12 manifest.
- Keep `S12_CLOSED_CELLS == {"DESIGNER_ITSELF.envelope_growth"}` unchanged. S13 advances the same layer cell and must not add it to `cells_closed`.
- Validate S13 does not alter `current_open_cells`; open-cell count stays `0`.
- Validate S13 summary metrics and false-clear fields both in nested `false_clear_counts` and flat `*_false_clear_count` form, following S12's pattern.

Traceability:

- Update S13 entries in `architecture/policy_design_case/layer2_artifact_traceability.toml` from planned to implemented.
- Keep traceability in the current minimal schema: `name`, `slice`, and `maturity`. Do not add path fields to `layer2_artifact_traceability.toml` unless Task 5 intentionally expands `_validate_artifact_traceability(...)`.
- Put exact artifact path bindings in the S13 manifest and in `tests/repo_quality/tools/test_policy_design_case_layer2_s13_post_deploy_accountability.py`.

Cluster map:

- Update `architecture/policy_design_case/cluster_ownership_map.toml` for `DESIGNER_ITSELF.envelope_growth` to mention S13 bidirectional envelope revision.
- Do not reopen the cell.
- Open count remains zero.
- Preserve existing S12-validated fields unless the readiness validator is intentionally changed in the same commit:
  - `owner_module = "src/polisyos/runtime/quality/layer2_resource_economics.py"`
  - `ratchet_state = "implemented"`
  - `p01_chain = "implemented"`
  - `gap = "none_for_s12_resource_economics_scope"`
  - `firewall = "P13_governance_gravity"`
- Prefer adding S13 context through `action` text or a validator-approved extension field; do not turn the cell into S13-owned if S12 readiness still expects resource-economics ownership.

Inventory:

- Update `architecture/policy_design_case/inventory.json` so the Layer 2 manifest inventory count becomes `21`.
- Add one S13 manifest entry.
- Do not add S14 claims.

Execution steps:

- [ ] **Step 1: Create the S13 manifest** at `architecture/policy_design_case/layer2_s13_post_deploy_accountability_manifest.json`.
- [ ] **Step 2: Extend the readiness validator** with S13 constants, loader, validator call, manifest checks, staged future-slice guards, and inventory count `21`.
- [ ] **Step 3: Update traceability, cluster map action text, and inventory** without reopening `DESIGNER_ITSELF.envelope_growth`.
- [ ] **Step 4: Add and run S13 repo-quality tests plus JSON/cluster/readiness validators**.
- [ ] **Step 5: Commit** `chore: register layer2 s13 post-deploy accountability`.

Verification:

```bash
cd policy-engine
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer2_s13_post_deploy_accountability.py -q
uv run python tools/quality/validation/check_policy_design_case_layer2_readiness.py
uv run python tools/quality/validation/check_policy_design_case_cluster_ownership_map.py
uv run python -m json.tool architecture/policy_design_case/layer2_s13_post_deploy_accountability_manifest.json > /tmp/layer2_s13_manifest.json
uv run python -m json.tool architecture/policy_design_case/inventory.json > /tmp/pdc_inventory.json
```

Expected output:

- S13 repo-quality tests pass.
- Readiness validator passes and reports open-cell count `0`.
- Cluster map validator passes.
- JSON files parse cleanly.

Commit:

```bash
git add architecture/policy_design_case/layer2_s13_post_deploy_accountability_manifest.json \
  architecture/policy_design_case/layer2_artifact_traceability.toml \
  architecture/policy_design_case/cluster_ownership_map.toml \
  architecture/policy_design_case/inventory.json \
  tools/quality/validation/check_policy_design_case_layer2_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s13_post_deploy_accountability.py
git commit -m "chore: register layer2 s13 post-deploy accountability"
```

## Task 6: Repo-Quality Snapshots, No-Open-Cell Regression, And Inventory Confirmation

Update repo-quality snapshots after S13 is registered.

Required snapshot changes:

- Exact Layer 2 inventory count becomes `21`.
- S12 current-slice snapshot should not fail because S13 now exists; update `test_layer2_s12_inventory_count_is_20_after_registration` and any equivalent exact-count checks so S12 assertions remain scoped to the S12 manifest while full readiness after S13 expects `21`.
- S13 snapshot asserts exact inventory count `21`.
- Open-cell count remains `0`.
- `DESIGNER_ITSELF.envelope_growth` remains implemented and now documents S12 resource allocation plus S13 bidirectional accountability learning.
- No snapshot may claim S14 is implemented.
- Existing S12 tests that assert future S13 is not implemented should become staged tests: S12 manifest remains non-authoritative for S13, but S13 implemented artifacts are allowed after the S13 manifest and readiness validator exist.

Regression checks:

- Capability ratchet still passes.
- Cluster ownership map still has no open Layer 2 cells.
- S13 negative-control registration is visible to readiness validator.
- W12D route emits S13 without changing S10/S12 shadow-only outcome authority.

Execution steps:

- [ ] **Step 1: Update prior exact-count snapshot tests** so S10/S11/S12 remain scoped and S13 owns the exact `21` count.
- [ ] **Step 2: Run the repo-quality regression gate** listed below.
- [ ] **Step 3: Commit** `chore: confirm layer2 s13 accountability regression`.

Verification:

```bash
cd policy-engine
uv run pytest \
  tests/repo_quality/tools/test_policy_design_case_layer2_s10_outcome_prediction.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s11_predictive_knowledge.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s12_resource_economics.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s13_post_deploy_accountability.py \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py \
  tests/repo_quality/tools/test_policy_design_case_capability_ratchet.py \
  tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py \
  -q
uv run python tools/quality/validation/check_policy_design_case_layer2_readiness.py
uv run python tools/quality/validation/check_policy_design_case_cluster_ownership_map.py
```

Expected output:

- All listed repo-quality tests pass.
- Open-cell count remains `0`.
- Inventory count is `21`.

Commit:

```bash
git add tests/repo_quality/tools/test_policy_design_case_layer2_s10_outcome_prediction.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s11_predictive_knowledge.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s12_resource_economics.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s13_post_deploy_accountability.py \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py \
  tests/repo_quality/tools/test_policy_design_case_capability_ratchet.py \
  tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py \
  architecture/policy_design_case/inventory.json \
  architecture/policy_design_case/cluster_ownership_map.toml
git commit -m "chore: confirm layer2 s13 accountability regression"
```

## Task 7: Full S13 Verification Done When

Run the full S13 gate after Tasks 1-6 are committed.

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer2_s13_post_deploy_accountability.py -q
uv run pytest \
  tests/unit/pdc/test_layer2_s2_design_search.py \
  tests/unit/pdc/test_layer2_readiness_contracts.py \
  tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py \
  tests/unit/runtime/quality/test_public_export.py \
  -q
uv run pytest \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s13_post_deploy_accountability.py \
  tests/repo_quality/tools/test_policy_design_case_capability_ratchet.py \
  tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py \
  -q
uv run python tools/quality/validation/check_policy_design_case_layer2_readiness.py
uv run python tools/quality/validation/check_policy_design_case_cluster_ownership_map.py
uv run polisyos-tools architecture guardrails check
uv run --extra runtime --extra ml polisyos-tools runtime check-runtime-api-contract
```

- [ ] **Step 1: Run the full S13 verification gate** exactly as listed above.
- [ ] **Step 2: Reopen the failure-pattern register and complete the closeout pattern check.**
- [ ] **Step 3: Only mark S13 complete when every Done When condition below is true.**

Done when all of the following are true:

- Red-first tests were committed before implementation.
- S13 runtime contracts are strict, typed, exported, and replayable.
- Deployment dossier blocks deployable cases without monitoring design.
- `accountability_only` records accountability without governed learning.
- Divergence records compose the shared `TypedDiagnosticRecord` shape through `diagnostic: TypedDiagnosticRecord`.
- MAPE-K trace carries monitor/analyze/plan/execute/knowledge refs.
- Learning update proposals require attribution and A-before-B sequence.
- Learning update proposals wrap `case_lifecycle` ex-post learning records validated by `validate_ex_post_learning_record(...)`; no parallel feedback/learning engine is introduced.
- Learning update proposals target only explicit update components and carry governance refs for high-stakes changes.
- Reissue-required learning maps to existing lifecycle reissue dispositions; no S13-only reissue status set exists.
- Historical-prior influence carries provenance, TTL, decay, contamination controls, and refs with recognized historical-prior prefixes.
- Post-policy data cannot become pre-policy evidence.
- Learned priors cannot occupy current evidence slots.
- Unattributable divergence creates accountability notes but no model/prior/envelope update.
- Design-error divergence after ineffective or high-risk review marks `rubber_stamp_divergence_review_required`.
- Implementation failure does not automatically refute policy theory.
- Seeded disconfirmation shrinks or splits the envelope.
- Seeded disconfirmation shrink/split rows record disconfirming signal time, revision effective time, and shrink latency.
- Validated reuse expands the envelope.
- `CertifiedEnvelopeDelta` materializes S12 `certified_envelope_delta_ref` strings where growth exists, and S12 `EnvelopeGrowthEntry` remains expand-only without a direction field.
- Every non-hold envelope revision has an assurance-case delta.
- Public export surfaces an accountability note by projecting existing `public_revision_states` while preserving closed-case historical meaning.
- Expert/machine/reviewer projections expose attribution, revision, assurance, owner, deadline, MAPE-K, action closure, oversight-effectiveness, oversight-accountability state, lifecycle reissue disposition, and replay details.
- Design-time S13 posture uses `phase == "design_time_gate"` and carries no finalized post-deploy refs.
- W12D emits 13 S13 blocks and zero false clears.
- Manifest declares six implemented S13 artifacts.
- Inventory count is `21`.
- `current_open_cell_count == 0`.
- `DESIGNER_ITSELF.envelope_growth` remains implemented and advanced, not reopened.
- No S14, production, recommendation, preference-learning, automated value-learning, or LLM attribution authority leaks into S13.
- Architecture guardrails and runtime API contract checks pass.

No additional commit is required for Task 7 unless verification forces a fix. If a fix is needed, commit it with a precise message describing the verified correction.

## Commit Sequence

Use this sequence unless a red/green split requires a smaller corrective commit:

1. `test: add layer2 s13 post-deploy accountability red tests`
2. `feat: add layer2 s13 post-deploy accountability contracts`
3. `feat: wire layer2 s13 accountability posture into projections`
4. `feat: classify layer2 s13 post-deploy accountability coverage`
5. `chore: register layer2 s13 post-deploy accountability`
6. `chore: confirm layer2 s13 accountability regression`

Do not combine Task 1 with implementation. Do not claim S13 complete until Task 7 passes.

## Closeout Pattern Check

Before final response, reopen `docs/reference/policy-design-case-failure-patterns.md` and verify:

- No contract-only capability remains for S13.
- No producer or bridge is missing.
- No S13 artifact is hidden from projection/public/reviewer surfaces.
- Status lattice distinguishes deployable, advisory-only, accountability-only, blocked, attributed, unattributable, and pending.
- Existing lifecycle reissue dispositions are reused; S13 does not add a parallel reissue lattice.
- A-before-B and closed-case replay integrity are tested.
- `DivergenceRecord` stays a post-deploy record that composes `TypedDiagnosticRecord`.
- `LearningUpdateProposal` wraps the existing validated ex-post learning dict shape.
- Public accountability notes project the existing public revision-state surface.
- MAPE-K, action-item closure, oversight-effectiveness, oversight-accountability state, lifecycle reissue disposition, and knowledge-ledger refs are visible in tests and surfaces.
- False-clear counts are exact and zero.
- S13 does not claim S14 universality or production authority.

Final response should include:

- Commits created.
- Verification commands and pass/fail results.
- Open-cell count.
- Inventory count.
- Any deliberate out-of-scope surface or semantic authority.
