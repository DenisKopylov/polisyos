---
title: PolicyOS Layer 2 S8 Value-Choice Provenance Implementation Plan
status: active
owner: governance-board
created: 2026-06-01
last_verified: null
stability: draft
slice: S8
slice_label: normative_firewall_value_choice
roadmap: ../POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER2_IMPLEMENTATION_PLAN.md
source_design_doc: ../../../system-design-decisions/universal-policy-design-target-architecture-and-gap.md
cluster_ownership_map: ../../../../architecture/policy_design_case/cluster_ownership_map.toml
slice_cell_matrix: ../../../../architecture/policy_design_case/layer2_slice_cell_matrix.toml
floor_governance: ../../../../architecture/policy_design_case/layer2_floor_governance.toml
artifact_traceability: ../../../../architecture/policy_design_case/layer2_artifact_traceability.toml
failure_patterns: ../../../reference/policy-design-case-failure-patterns.md
depends_on:
  - S2
  - S6
  - S7
cells_closed:
  - ACTOR.value_choice_provenance
floor_id: s8_value_provenance
floor_metric: value_provenance_completeness
---

# Layer 2 S8 - Value-Choice Provenance, Normative Firewall, And Pareto Archive

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

Read this whole file before editing. Execute the tasks in order, keep commits
task-sized, and preserve the repo rule that LLM output is candidate material
only. S8 closes exactly `ACTOR.value_choice_provenance`; it does not close S9
projection maturity, S10 forecast support, S11 calibration or proof-carrying
analytics, S12 envelope growth, S13 accountability, production recommendation
authority, or S14 universality.

## Goal

S8 makes value choices explicit, mandate-backed, replayable, and visible across
audiences. The system may compute Pareto/frontier facts, but it must not rank,
select, scalarize, or recommend across conflicting objectives unless every
ranked recommendation carries authorized value-choice provenance.

The closure contract is the S8 roadmap contract:

- producer: frontier plus value-choice provenance.
- persisted artifact: value provenance on every ranked recommendation.
- bridge/consumer: ranking consumes authorized weights only.
- surface: frontier plus contested conflict, never a hidden scalar.
- semantic test: scalar ranking without authorized provenance is rejected.
- negative control: LLM or corpus-derived weights cannot satisfy P20 authority.
- floor: `value_provenance_completeness = 1.0`.

## Architecture

S8 is a gate-owned A-side runtime-quality capability. It wires the existing
foundry welfare seed modules into a Policy Design Case value firewall:

- `src/polisyos/foundry/welfare/social_weight_provenance.py` already defines
  strict social-weight provenance and LLM-source rejection.
- `src/polisyos/foundry/welfare/frontier_emitter.py` already separates Pareto
  frontier facts from `ValueChoiceDecisionPoint` and blocks scalar-only public
  welfare payloads.
- S8 adds the PDC narrow-waist producer in
  `src/polisyos/runtime/quality/design_axes/value_choice_provenance.py`, exports it from
  `runtime.quality`, and persists replay-visible refs.
- S8 injects a compact `Layer2S8ValuePostureInput` into the S2 shadow design
  loop. B can consume value posture refs, pause, block ranking, or expose
  contested value conflicts. B cannot choose weights, synthesize mandate, infer
  principal preferences, or convert S7 human decisions into S8 value authority.
- S8 reuses S7 delegation only as a route and record lifecycle for the shared
  `GovernanceDecisionClass` `value_authorization`; S7 refs must never appear as
  the value-source class that authorizes social weights by themselves.

## Scope

In scope:

- strict Pydantic S8 runtime-quality contracts exported from
  `polisyos.runtime.quality`.
- producer functions that consume S6 mandate/measurability refs, existing
  foundry welfare provenance/frontier records, and S7 delegation refs where
  relevant.
- P20/P22 normative firewalls for value-choice authority and mandate
  legitimacy.
- Pareto archive and value schedule refs in `SearchLedger`, `DesignRecord`
  ledger refs, `AxisPositionDeclaration`, `AxisFirewallStatus`, and typed
  `ConstraintStoreSnapshot.constraint_records`.
- W12.D canonical corpus route with S8 blocks on all 13 cases.
- public/reviewer/expert/machine projections that disclose tradeoffs without
  turning scalar welfare or AI-chosen weights into authority.
- scenario value schedules that may support shadow sensitivity analysis but
  remain non-authoritative until value authorization passes.
- Arrow/multi-principal disclosure rows for affected groups, dissent, blocking
  rights, incompatible principals, and alternative schedule sensitivity.
- cluster closure for `ACTOR.value_choice_provenance`, manifest registration,
  validator coverage, and inventory.

Out of scope:

- automated preference learning.
- social welfare theorem resolution, new moral philosophy machinery, or a
  universal social-weight library.
- S9 projection grammar maturity, S10 prediction, S11 calibration or
  proof-carrying analytics, S12 envelope growth, S13 accountability, production
  authority, calibrated simulations, portfolio optimization, or S14 battery
  closure.

## Pattern Pass

Open the failure register before implementation and before closeout:
`docs/reference/policy-design-case-failure-patterns.md`.

| Pattern | S8 risk | Closure move |
| --- | --- | --- |
| P01 contract-only capability | Existing welfare contracts exist, but `ACTOR.value_choice_provenance` is still `implemented_but_not_orchestrated`. | Add producer, persisted artifact refs, S2 consumer, surfaces, repo-quality validators, and negative semantic tests. |
| P02 thin orchestration | Calling `emit_welfare_frontier` alone would not make S8 a PDC gate. | Runtime-quality producer must own S8 disposition and must be consumed by S2. |
| P03 hidden internal richness | Foundry welfare richness is not enough if surfaces omit the refs. | Render PUBLIC/REVIEWER/EXPERT/MACHINE projections and closeout-visible refs. |
| P04 status lattice gap | `review_required`, `contested`, `blocked`, and `advisory_only` must not collapse into pass/fail. | Define S8 dispositions and propagate them into refinement routes and projections. |
| P05 authority boundary leak | Pareto facts and scalar scores can be mistaken for recommendations. | Frontier facts are authoritative only for frontier membership; value choices need authorized schedule refs. |
| P09 warning lifecycle gap | Value limitations can become permanent warnings with no decision path. | Contested/missing value provenance creates human/value-governance handoffs or blocks ranking. |
| P10 semantic adequacy gap | Constructor tests would miss silent social-weight choice. | Red-first corpus and negative-control tests must prove the signal is produced and consumed. |
| P12 producer handshake gap | S6/S7 refs may be present but ignored by S8. | S8 consumes exact S6 mandate firewall disposition and records S7 refs as non-substituting provenance. |
| P15 LLM speculation laundering | LLM or corpus-derived weights can look like preferences. | P20 denies all LLM/corpus weights as authority unless an authorized value schedule exists independently. |
| P20 normative choice laundering | The central S8 failure mode. | No ranked recommendation, selected alternative, or scalarized objective may pass without authorized value provenance; shadow scenario schedules remain visibly non-authoritative. |
| P22 mandate laundering | Mandate-limited or candidate-only authority can be stretched into weights. | S8 requires S6 `MandateLegitimacyRecord.firewall_disposition == "pass"` for authority-bearing value schedules. |
| P26 responsibility laundering | S7 human decisions can be misread as value provenance. | S7 requests/records can route value decisions, but cannot themselves satisfy S8 value authority. |

Capability label transition:

- start: `implemented_but_not_orchestrated` / `bridge_missing`.
- target: `implemented`.
- missing chain to close: producer, persisted artifact, orchestration bridge,
  consumer, verification, surface, semantic test.

## Code-Grounded Reality Check

Current S8 anchors:

- `architecture/policy_design_case/cluster_ownership_map.toml`
  has `[cell.ACTOR.value_choice_provenance]` with
  `ratchet_state = "implemented_but_not_orchestrated"`,
  `p01_chain = "bridge_missing"`, and firewall
  `P20_normative_choice_laundering`.
- `architecture/policy_design_case/cluster_ownership_map.toml`
  has `[open_cell_closure.ACTOR.value_choice_provenance]` with
  missing chain `producer`, `persisted_artifact`, `orchestration_bridge`,
  `consumer`, `verification`, `surface`, and `semantic_test`.
- `architecture/policy_design_case/layer2_slice_cell_matrix.toml`
  assigns `ACTOR.value_choice_provenance` to S8.
- `architecture/policy_design_case/layer2_floor_governance.toml`
  defines `floor_id = "s8_value_provenance"`,
  `metric = "value_provenance_completeness"`, and revision rule
  `ranked_recommendations_require_authorized_value_source`.
- `architecture/policy_design_case/layer2_artifact_traceability.toml`
  currently has only `ParetoArchive` for S8. This plan must add the missing
  S8 value-provenance artifacts instead of pretending `ParetoArchive` alone is
  the capability.
- `tests/unit/foundry/welfare/test_social_weight_provenance.py` already tests
  that LLM social-weight candidates cannot support value choice.
- `tests/unit/foundry/welfare/test_frontier_emitter.py` already tests that
  Pareto facts are separate from value-choice decisions and that scalar-only
  welfare publication is blocked.

## Source Of Truth

S8 closure is measured against these exact rows:

- slice: `S8`.
- cell: `ACTOR.value_choice_provenance`.
- firewall: `P20_normative_choice_laundering`, with P22 mandate support.
- floor: `s8_value_provenance`.
- floor metric: `value_provenance_completeness`.
- owner: `governance-board`.
- implementation prerequisites: S2 consumer/ledger, S6 mandate and
  measurability records, and S7 delegation route for `value_authorization`.
- existing seed files:
  - `src/polisyos/foundry/welfare/social_weight_provenance.py`
  - `src/polisyos/foundry/welfare/frontier_emitter.py`
- target producer module:
  - `src/polisyos/runtime/quality/design_axes/value_choice_provenance.py`

## Files

Expected new files:

- `src/polisyos/runtime/quality/design_axes/value_choice_provenance.py`
- `tests/unit/runtime/quality/test_layer2_s8_value_choice.py`
- `tests/fixtures/layer2/s8/s8_value_choice_case_signals.json`
- `tests/fixtures/layer2/s8/s8_value_choice_expert_labels.json`
- `tests/fixtures/layer2/s8/llm_social_weight_probe.json`
- `tests/fixtures/layer2/s8/blocked_mandate_value_choice_probe.json`
- `tests/fixtures/layer2/s8/pareto_ranking_without_value_source_probe.json`
- `tests/fixtures/layer2/s8/multi_principal_conflict_probe.json`
- `tests/fixtures/layer2/s8/s7_human_decision_substitution_probe.json`
- `tests/fixtures/layer2/s8/shadow_scenario_authority_spoof_probe.json`
- `tests/fixtures/layer2/s8/missing_arrow_disclosure_probe.json`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s8_value_choice.py`
- `architecture/policy_design_case/layer2_s8_value_choice_manifest.json`

Expected edited files:

- `src/polisyos/runtime/quality/__init__.py`
- `src/polisyos/runtime/quality/design_axes/mandate_bounded_delegation.py`
- `src/polisyos/pdc/_impl/layer2_design_search.py`
- `src/polisyos/pdc/__init__.py`
- `tools/quality/validation/run_universal_outcome_corpus.py`
- `tools/quality/validation/check_policy_design_case_layer2_readiness.py`
- `architecture/policy_design_case/cluster_ownership_map.toml`
- `architecture/policy_design_case/layer2_artifact_traceability.toml`
- `architecture/policy_design_case/inventory.json`
- `tests/unit/runtime/quality/test_layer2_s7_delegation.py`
- `tests/unit/pdc/test_layer2_s2_design_search.py`
- `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py`
- existing layer2 readiness/cluster-map repo-quality tests that assert current
  open-cell count.

Do not edit unrelated S9+ implementation files to mark later slices complete.

## Implementation Reality Pass

The code already gives S8 more than a blank slate:

- `src/polisyos/foundry/welfare/social_weight_provenance.py` already has strict
  `SocialWeightProvenance`, `AffectedGroupWeight`, `SocialWeightDissent`,
  sponsor disclosure, review status, CAS persistence, and an LLM-source
  authority check. S8 should wrap and project these records, not fork a second
  social-weight ontology.
- `src/polisyos/foundry/welfare/frontier_emitter.py` already has
  `ObjectiveSpec`, `AlternativeOutcome`, `ParetoFrontierRecord`,
  `ValueChoiceDecisionPoint`, `WelfareAuditTrail`, `WelfareFrontierEmission`,
  CAS persistence, and scalar-only publication blocking. S8 should adapt these
  into PDC `ParetoArchive`/value records instead of rewriting dominance logic.
- `src/polisyos/runtime/quality/design_axes/blind_spot_firewalls.py` already emits
  `MandateLegitimacyRecord` with top-level `firewall_disposition` values
  `pass`, `limit`, or `block`. Candidate-only mandate appears as nested
  `MandateSourceRecord.disposition == "candidate_unverified"` and therefore
  produces top-level `limit`. S8 tests must check both the exact top-level
  disposition and the nested source disposition where candidate-only semantics
  matter.
- `src/polisyos/runtime/quality/design_axes/mandate_bounded_delegation.py` has the S7
  `GovernanceDecisionClass` registry, `DecisionRightsMatrix`, request/record
  helpers, and five-rights checks, but it does **not** yet register
  `value_authorization`. S8 needs a narrow S7 extension for that shared decision
  class; otherwise the plan would pretend a route exists when it does not.
- `src/polisyos/pdc/_impl/layer2_design_search.py` is large but has clear
  extension hooks mirroring S6/S7: posture DTO, `_constraint_store`,
  `_refinement_decision`, `_search_ledger`, `_design_record`, projection
  fields, axis/firewall helpers, and ledger-ref helpers. Do not create a second
  S2 loop.
- `tools/quality/validation/run_universal_outcome_corpus.py` already builds S6
  and S7 blocks before injecting the pinned S2 case. S8 should follow that
  pattern: import the runtime-quality S8 helpers, build the per-case block, then
  pass a compact posture DTO into S2.
- Current inventory count is 15 after S7. Registering the S8 manifest should
  make the Layer 2 inventory artifact count 16.

## Task 1: Red-First S8 Semantic And Negative Tests

Intent: prove the current repo fails the S8 semantic contract before adding the
producer. The initial failure should be missing imports, missing fields, or
assertion failures around absent S8 posture. Do not weaken existing welfare
unit tests.

- [ ] **Step 1: Add runtime-quality red tests**

Create `tests/unit/runtime/quality/test_layer2_s8_value_choice.py` with these
tests:

- `test_value_choice_provenance_record_is_strict_replayable_and_mandate_bounded`
- `test_authorized_value_schedule_requires_s6_mandate_firewall_pass`
- `test_pareto_archive_cannot_rank_without_authorized_value_schedule`
- `test_p20_rejects_llm_or_corpus_derived_social_weights`
- `test_p22_rejects_absent_limit_block_or_candidate_unverified_mandate_source`
- `test_shadow_scenario_value_schedule_is_visible_but_not_authority`
- `test_multi_principal_conflict_is_contested_not_silent_average`
- `test_s7_human_decision_refs_cannot_substitute_for_s8_value_authority`
- `test_s7_value_authorization_route_requires_governance_decision_class_and_five_rights`
- `test_value_tradeoff_disclosure_has_audience_bounded_public_projection`
- `test_value_choice_records_are_exported_from_runtime_quality`

The tests must instantiate strict records and fail on extra fields. Use the S6
contract style: exact `MandateLegitimacyRecord.firewall_disposition` matters.
Top-level S6 disposition is `pass`, `limit`, or `block`; nested
`MandateSourceRecord.disposition == "candidate_unverified"` must be treated as a
candidate-only source and cannot authorize ranked autonomy.

- [ ] **Step 2: Add S7 value-authorization red tests**

Extend `tests/unit/runtime/quality/test_layer2_s7_delegation.py` with:

- `test_s7_registry_contains_value_authorization_decision_class`
- `test_value_authorization_matrix_row_is_request_driven_and_non_autonomous`

Expected initial failure: `value_authorization` is absent from the S7 registry.
This is a real code gap, not a new S8 abstraction.

- [ ] **Step 3: Add S2 consumer red tests**

Extend `tests/unit/pdc/test_layer2_s2_design_search.py` with:

- `test_s2_consumes_s8_value_posture_and_blocks_ranking_without_authorized_schedule`
- `test_s2_value_gap_records_p20_constraint_and_ledger_refs`
- `test_s2_public_projection_exposes_value_tradeoff_summary_only`
- `test_s2_reviewer_projection_renders_value_class_status_and_firewalls`
- `test_s2_expert_machine_projection_renders_value_refs_conflicts_and_integrity`
- `test_s2_does_not_treat_s8_as_production_recommendation_authority`

The test fixture should call `run_s2_shadow_design_loop(..., value_posture=...)`.
Red failure is acceptable until Task 3 adds the input model and wiring.

- [ ] **Step 4: Add canonical corpus route red tests**

Extend `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`:

- `test_w12d_emits_s8_value_choice_blocks_for_13_cases`
- `test_w12d_s8_negative_controls_have_zero_false_clears`
- `test_w12d_s8_ranked_recommendations_require_authorized_value_source`
- `test_w12d_s8_pinned_s2_case_injects_value_posture`
- `test_w12d_s8_preserves_s2_shadow_only_outcome_effects`

- [ ] **Step 5: Run the red S8 suite**

Expected failing command before implementation:

```bash
uv run pytest \
  tests/unit/runtime/quality/test_layer2_s7_delegation.py \
  tests/unit/runtime/quality/test_design_axes_value_choice_provenance.py \
  tests/unit/pdc/test_layer2_s2_design_search.py \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py \
  -q
```

Expected red output:

- missing `polisyos.runtime.quality.design_axes.value_choice_provenance` exports, or
- missing `Layer2S8ValuePostureInput`, or
- missing `s8_value_choice` corpus block.

- [ ] **Step 6: Commit Task 1**

Stop Task 1 after committing only tests and fixtures.

## Task 2: Contracts, Producer, Pareto Archive, And P20/P22 Firewalls

Intent: implement the S8 A-side producer by wiring existing foundry welfare
seed records into PDC runtime-quality contracts.

- [ ] **Step 1: Add producer module**

Create `src/polisyos/runtime/quality/design_axes/value_choice_provenance.py`.

Use `Layer2ReadinessModel` for all PDC-facing DTOs. Keep strict Pydantic
defaults from the base model and add field bounds. Export all public names from
`src/polisyos/runtime/quality/__init__.py`.

Do not rewrite `foundry/welfare` unless a red test proves a seed contract is
wrong. The S8 module should be a thin PDC-facing adapter around foundry welfare
frontier/provenance facts plus S6/S7 authority refs.

Required constants:

- `LAYER2_S8_VALUE_CHOICE_SCHEMA_VERSION`
- `LAYER2_S8_VALUE_CHOICE_RULE_VERSION`
- `S8_VALUE_CHOICE_CELL_REF = "ACTOR.value_choice_provenance"`
- `S8_VALUE_CHOICE_FLOOR_ID = "s8_value_provenance"`

- [ ] **Step 2: Extend S7 only enough to route value authorization**

Edit `src/polisyos/runtime/quality/design_axes/mandate_bounded_delegation.py` before relying on S7
value routes:

- add `value_authorization` to `build_governance_decision_class_registry(...)`.
- set required role to `principal` and `high_stakes=True` for the default route.
- update `_role_for_decision_class(...)` so `value_authorization` maps to
  `principal`.
- keep `_mode_for_decision_class(...)` defaulting to `request_driven`; do not
  allow `ai_first` or `delegated_autonomous`.
- do not add any value-choice authority to S7 `authoritative_for`; S7 remains a
  routing/record lifecycle producer only.

Required records:

- `AuthorizedValueSchedule`
  - schedule ref, mandate record ref, exact S6 mandate firewall disposition,
    principal refs, source class, review status, effective time, social weight
    provenance refs, authority boundary, rule version, and may-not-use-for list.
- `ObjectiveFunctionProvenanceRecord`
  - objective refs, objective source refs, value schedule ref, measurability
    refs, proxy/value-loss disclosures, mandate refs, P20/P22 status, and
    authority boundary.
- `ParetoArchive`
  - frontier refs, nondominated alternative ids, rejected nondominated
    alternatives, objective refs, value schedule ref if ranking is attempted,
    archive status, scenario value schedule refs, claim refs, audit refs, and
    may-not-use-for list.
- `ValueChoiceProvenanceRecord`
  - selected alternative ref, objective provenance ref, value schedule ref,
    Pareto archive ref, social weight provenance refs, mandate refs,
    delegation refs, `value_authorization` decision refs, conflict rows,
    affected group rows, dissent refs, blocking rights refs, alternative
    schedule sensitivity rows, disposition, integrity status, and replay refs.
- `ValueTradeoffDisclosureRecord`
  - audience, decision-shaped public summary, reviewer status fields, expert
    refs, machine integrity fields, affected groups, dissent, blocking rights,
    alternative schedule sensitivity, and projection authority boundary.
- `ValueChoiceIntegrityReport`
  - completeness denominator, numerator, false-clear counts, negative-control
    results, case count, floor id, and metric name.

Required enums or Literal sets:

- source class: `authorized_governance_schedule`, `participatory_process`,
  `legal_mandate`, `foundry_social_weight_provenance`, `llm_candidate`,
  `corpus_derived`, `ad_hoc_reviewer_note`.
- delegation reference class: `s7_value_authorization_request`,
  `s7_value_authorization_record`, `s7_final_selection_record`. These are route
  and audit refs only; they are not value-source classes.
- value disposition: `authorized`, `advisory_only`, `contested_multi_principal`,
  `blocked_missing_value_provenance`, `blocked_mandate_not_pass`,
  `blocked_p20_normative_laundering`, `blocked_p22_mandate_laundering`,
  `shadow_scenario_only`.
- ranking mode: `unranked_frontier_only`, `ranked_with_authorized_values`,
  `shadow_scenario_ranking`, `ranking_blocked`.
- firewall status: `pass`, `limit`, `block`.

- [ ] **Step 3: Implement producer functions**

Implement:

- `coerce_social_weight_provenance_for_s8(...)`
  - accepts existing foundry `SocialWeightProvenance` or mapping.
  - rejects LLM and corpus-derived provenance for authority.
  - preserves source refs for advisory disclosure.
- `build_authorized_value_schedule(...)`
  - requires S6 mandate record ref and exact S6 mandate firewall disposition
    `pass`.
  - rejects top-level `limit`, top-level `block`, absent, or unknown
    dispositions for authority.
  - rejects nested `MandateSourceRecord.disposition == "candidate_unverified"`
    for authority even if a fixture tries to call it candidate-only.
  - accepts S7 `HumanDecisionRequest` / `HumanDecisionRecord` refs only when
    they are tied to the shared `GovernanceDecisionClass` `value_authorization`
    and a matching `DecisionRightsMatrix` row; even then the S7 refs are routing
    and ratification evidence, not the value-source class itself.
- `build_shadow_scenario_value_schedule(...)`
  - records alternative value schedules for sensitivity analysis.
  - marks them `shadow_scenario_only` and blocks them from satisfying ranked
    recommendation authority.
- `build_objective_function_provenance(...)`
  - requires objective refs, value schedule ref for ranking, and S6
    measurability/proxy disclosure refs when objectives rely on proxies.
- `build_pareto_archive(...)`
  - can persist frontier facts without ranking.
  - fails closed when `ranking_mode = "ranked_with_authorized_values"` and no
    authorized value schedule is present.
  - maps existing foundry `WelfareFrontierEmission` and `ParetoFrontierRecord`
    when provided.
- `build_value_choice_provenance_record(...)`
  - combines schedule, objective provenance, Pareto archive, conflict rows, S6
    mandate refs, and optional S7 request/record refs.
  - surfaces multi-principal incompatibility as
    `contested_multi_principal`, not a silent average.
  - requires affected group rows, dissent refs, blocking rights refs, and
    alternative schedule sensitivity rows when multi-principal conflict is
    detected.
- `project_value_tradeoff_disclosure(...)`
  - PUBLIC: decision-shaped tradeoff summary and accountability pull refs only.
  - REVIEWER: decision class, role/source, mode, action, P20/P22/P12/P15/P26
    statuses.
  - EXPERT/MACHINE: all refs, conflict rows, schedule details, mandate refs,
    affected groups, dissent refs, blocking rights refs, alternative schedule
    sensitivity, integrity checks, frontier refs, rejected nondominated
    alternatives, and authority boundary.
- `s8_value_provenance_integrity(...)`
  - computes completeness and false-clear metrics.
- `persist_value_choice_provenance_bundle(...)`
  - persists deterministic JSON through existing CAS helpers when a store is
    supplied, or returns stable refs for the corpus route.

- [ ] **Step 4: Implement firewall behavior**

P20 fails closed when:

- social weights are LLM-generated, corpus-derived, ad hoc, or reviewer notes
  without authorized schedule.
- a scalar ranking exists without a `ValueChoiceProvenanceRecord`.
- Pareto facts are used as value-choice authority.
- a `shadow_scenario` value schedule is projected as an authorized ranking.
- multiple principals have incompatible schedules and no authorized conflict
  resolution rule exists.

P22 fails closed when:

- S6 mandate legitimacy is absent.
- exact S6 mandate firewall disposition is not `pass`.
- nested S6 mandate source disposition is `candidate_unverified`.
- mandate is limited to evidence collection, consultation, workflow, budget
  planning, or candidate exploration.
- candidate-unverified mandate source is used for objective weights or social
  weights.

P26 boundary:

- S7 may request or record a human decision about value choice.
- S7 records do not themselves authorize social weights.
- S8 must record S7 refs as `delegation_refs` and still require an authorized
  value schedule.
- valid S7 routing for value authorization must cite the shared
  `GovernanceDecisionClass` `value_authorization`, the `DecisionRightsMatrix`
  row, and five-rights validation; wrong-role or oversight-theater records
  remain invalid.

- [ ] **Step 5: Run focused runtime tests**

Run:

```bash
uv run pytest \
  tests/unit/runtime/quality/test_layer2_s7_delegation.py \
  tests/unit/runtime/quality/test_design_axes_value_choice_provenance.py \
  -q
```

Expected green after Task 2:

- S7 `value_authorization` registry/matrix tests pass.
- strict contract tests pass.
- P20/P22 negative controls fail closed.
- runtime.quality exports S8 contracts and producer helpers.

- [ ] **Step 6: Commit Task 2**

## Task 3: Inject S8 Value Posture Into The S2 Shadow Loop

Intent: B consumes S8 posture as injected A-side authority. B cannot self-rank
or import foundry/S8 producer modules as authority.

- [ ] **Step 1: Add PDC posture input**

Edit `src/polisyos/pdc/_impl/layer2_design_search.py`:

- add `Layer2S8ValuePostureInput(Layer2ReadinessModel)`.
- add `value_posture: Layer2S8ValuePostureInput | None = None` to:
  - `Layer2S2DesignSearchRun`
  - `run_s2_shadow_design_loop`
  - `_constraint_store(...)`
  - `_refinement_decision(...)`
  - `_search_ledger(...)`
  - `_design_record(...)`
  - projection helpers around `project_s2_design_search(...)`.
- export `Layer2S8ValuePostureInput` from `src/polisyos/pdc/__init__.py`.

Posture fields:

- `value_choice_provenance_ref`
- `authorized_value_schedule_ref`
- `shadow_scenario_value_schedule_refs`
- `objective_function_provenance_ref`
- `pareto_archive_ref`
- `value_tradeoff_disclosure_ref`
- `mandate_record_ref`
- `s6_mandate_firewall_disposition`
- `ranking_mode`
- `disposition`
- `p20_firewall_status`
- `p22_firewall_status`
- `value_provenance_completeness`
- `principal_refs`
- `conflict_rows`
- `affected_group_rows`
- `dissent_refs`
- `blocking_rights_refs`
- `alternative_schedule_sensitivity`
- `rejected_nondominated_alternative_ids`
- `social_weight_provenance_refs`
- `delegation_refs`
- `value_authorization_decision_refs`
- `constraint_store_updates`
- `handoff_rows`
- `limitation_summary`
- `authority_boundary`

- [ ] **Step 2: Add S2 consumption behavior**

When S8 posture is absent and the run attempts a ranked value choice, S2 must:

- emit a `ConstraintStoreEntry` for `ACTOR.value_choice_provenance`.
- set status `limit` or `block` based on ranking attempt.
- route to `human_decision` or `block_candidate` for value-laden ranking.
- include S8 refs in `SearchLedger` and `DesignRecord.ledger_refs` when
  posture exists.

When S8 posture is present:

- `authorized` allows governed/shadow ranking context only, not production
  authority.
- `advisory_only` leaves recommendations unranked or clearly advisory.
- `shadow_scenario_only` may show sensitivity under alternative schedules but
  cannot satisfy an authorized ranked recommendation.
- `contested_multi_principal` surfaces contested conflict and prevents silent
  scalarization.
- `blocked_*` blocks ranked selection and records P20/P22 status.

Add ledger fields or a stable ledger-ref projection equivalent:

- `value_choice_provenance_refs`
- `pareto_archive_refs`
- `authorized_value_schedule_refs`
- `shadow_scenario_value_schedule_refs`
- `value_authorization_decision_refs`
- `value_choice_status`

Add S8 `ClusterHandoffRecord` rows with:

- source cell `ACTOR.value_choice_provenance`.
- target cell `INTERVENTION.design_candidate` or
  `INTERVENTION.design_grammar`.
- disposition `consumed`, `blocked`, or `rejected`.
- may-not-use-for includes production, prediction, calibration, preference
  learning, and S9+ authority.

- [ ] **Step 3: Add audience projections**

Update `project_s2_design_search`:

- PUBLIC:
  - `value_tradeoff_disclosure_present`
  - no raw weights unless already public disclosure text.
  - summary states that frontier/ranking depends on authorized value source.
- REVIEWER:
  - value disposition, ranking mode, P20/P22/P12/P15/P26 status, action route.
- EXPERT:
  - refs, objective provenance, authorized and scenario schedule refs, principal
    conflicts, affected groups, dissent, blocking rights, alternative schedule
    sensitivity, rejected nondominated alternatives, mandate refs, integrity
    status.
- MACHINE:
  - everything in EXPERT plus raw rows and deterministic replay refs.

Add an assertion helper:

- `assert_s2_public_projection_has_value_tradeoff_disclosure(...)`

- [ ] **Step 4: Run focused S2 tests**

Run:

```bash
uv run pytest tests/unit/pdc/test_layer2_s2_design_search.py -q
```

Expected green after Task 3:

- S2 consumes injected S8 posture.
- SearchLedger and DesignRecord carry S8 refs.
- B-side code has no import from `polisyos.runtime.quality.design_axes.value_choice_provenance`,
  `polisyos.foundry.welfare.frontier_emitter`, or
  `polisyos.foundry.welfare.social_weight_provenance` for S8 authority inside
  `src/polisyos/pdc/_impl/layer2_design_search.py`.

- [ ] **Step 5: Commit Task 3**

## Task 4: Canonical Corpus Route Wiring - 13-Case S8 Coverage

Intent: W12.D emits an S8 block for every canonical corpus case and proves the
negative controls have zero false clears.

- [ ] **Step 1: Add fixtures**

Create:

- `tests/fixtures/layer2/s8/s8_value_choice_case_signals.json`
- `tests/fixtures/layer2/s8/s8_value_choice_expert_labels.json`

Every one of the 13 cases must have an S8 row. Include at least these signal
families:

- authorized schedule present.
- no value ranking needed, frontier-only.
- shadow scenario value schedule used for sensitivity, not authority.
- high-stakes value-laden ranking.
- mandate-limited value choice.
- budget/legal-use value choice.
- acquisition tradeoff.
- final-choice ranking.
- proxy-only objective with value-loss disclosure.
- multi-principal conflict with affected groups, dissent, blocking rights, and
  alternative schedule sensitivity.
- LLM-proposed weights.
- corpus-derived weights.
- blocked/limited/candidate-unverified mandate source.
- S7 human decision present but no S8 value schedule.
- S7 value authorization request/record with wrong role or missing five-rights
  validation.

Follow the existing S6/S7 fixture split: `s8_value_choice_case_signals.json`
contains observable inputs and refs; `s8_value_choice_expert_labels.json`
contains expected disposition, expected false-clear behavior, and expected
coverage labels. Do not put gold labels into case signals.

Negative-control fixture files:

- `llm_social_weight_probe.json`
- `blocked_mandate_value_choice_probe.json`
- `pareto_ranking_without_value_source_probe.json`
- `multi_principal_conflict_probe.json`
- `s7_human_decision_substitution_probe.json`
- `shadow_scenario_authority_spoof_probe.json`
- `missing_arrow_disclosure_probe.json`

- [ ] **Step 2: Wire runner**

Edit `tools/quality/validation/run_universal_outcome_corpus.py`:

- load S8 fixtures beside S6/S7 fixtures.
- create `_s8_value_choice_summary(...)` for each case.
- create `_s8_value_choice_corpus_summary(...)` for floor metrics.
- create `_s8_value_posture_input(...)` and inject it into the pinned S2 case.
- include `s8_value_choice` in every case block.
- include `s8_value_choice_summary` in the top-level report.
- include S8 refs in closeout-visible refs.

Per-case `s8_value_choice` block fields:

- `schema_version = "policyos.policy_design_case.layer2_s8_value_choice.v1"`
- `case_id`
- `value_choice_provenance_ref`
- `authorized_value_schedule_ref`
- `shadow_scenario_value_schedule_refs`
- `objective_function_provenance_ref`
- `pareto_archive_ref`
- `value_tradeoff_disclosure_ref`
- `mandate_record_ref`
- `s6_mandate_firewall_disposition`
- `ranking_mode`
- `disposition`
- `p20_firewall_status`
- `p22_firewall_status`
- `value_provenance_completeness`
- `principal_refs`
- `conflict_rows`
- `affected_group_rows`
- `dissent_refs`
- `blocking_rights_refs`
- `alternative_schedule_sensitivity`
- `rejected_nondominated_alternative_ids`
- `social_weight_provenance_refs`
- `delegation_refs`
- `value_authorization_decision_refs`
- `constraint_store_updates`
- `handoff_rows`
- `canonical_outcome_effect = "none_shadow_or_governed_pilot_value_context_only"`
- `may_not_use_for`

Top-level summary fields:

- `schema_version = "policyos.policy_design_case.layer2_s8.value_choice_corpus_summary.v1"`
- `case_count = 13`
- `value_provenance_completeness = 1.0`
- `authorized_value_schedule_recall = 1.0`
- `pareto_archive_coverage = 1.0`
- `tradeoff_disclosure_coverage = 1.0`
- `s2_value_posture_injection_count = 1`
- `llm_weight_false_clear_count = 0`
- `corpus_weight_false_clear_count = 0`
- `blocked_mandate_value_choice_false_clear_count = 0`
- `pareto_ranking_without_value_source_false_clear_count = 0`
- `multi_principal_silent_average_false_clear_count = 0`
- `s7_decision_substitution_false_clear_count = 0`
- `shadow_scenario_authority_false_clear_count = 0`
- `missing_arrow_disclosure_false_clear_count = 0`
- `negative_control_results`

- [ ] **Step 3: Run corpus route tests**

Run:

```bash
uv run pytest tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py -q
```

Expected green after Task 4:

- all 13 cases contain S8 blocks.
- pinned S2 case consumes S8 posture.
- negative-control false-clear counts are zero.
- production-posture outcomes remain unchanged by S8.

- [ ] **Step 4: Commit Task 4**

## Task 5: S8 Manifest, Readiness Validator, Cluster Closure, And Inventory

Intent: close `ACTOR.value_choice_provenance` in repo metadata without changing
floors, denominators, or later-slice cells.

- [ ] **Step 1: Add S8 manifest**

Create `architecture/policy_design_case/layer2_s8_value_choice_manifest.json`.

Required fields:

```json
{
  "schema_version": "policyos.policy_design_case.layer2_s8_value_choice_manifest.v1",
  "status": "active",
  "owner": "governance-board",
  "slice": "S8",
  "depends_on": ["S2", "S6", "S7"],
  "cells_closed": ["ACTOR.value_choice_provenance"],
  "producer_module": "src/polisyos/runtime/quality/design_axes/value_choice_provenance.py",
  "expected_current_open_cell_count": 3,
  "floor_id": "s8_value_provenance",
  "floor_metric": "value_provenance_completeness",
  "required_artifacts": [
    "AuthorizedValueSchedule",
    "ObjectiveFunctionProvenanceRecord",
    "ParetoArchive",
    "ValueChoiceProvenanceRecord",
    "ValueTradeoffDisclosureRecord",
    "ValueChoiceIntegrityReport"
  ],
  "required_firewalls": ["P20", "P22", "P12", "P15", "P26"],
  "case_count": 13,
  "value_provenance_completeness": 1.0,
  "authorized_value_schedule_recall": 1.0,
  "pareto_archive_coverage": 1.0,
  "tradeoff_disclosure_coverage": 1.0,
  "llm_weight_false_clear_count": 0,
  "corpus_weight_false_clear_count": 0,
  "blocked_mandate_value_choice_false_clear_count": 0,
  "pareto_ranking_without_value_source_false_clear_count": 0,
  "multi_principal_silent_average_false_clear_count": 0,
  "s7_decision_substitution_false_clear_count": 0,
  "shadow_scenario_authority_false_clear_count": 0,
  "missing_arrow_disclosure_false_clear_count": 0,
  "canonical_route": "tools/quality/validation/run_universal_outcome_corpus.py",
  "validator": "tools/quality/validation/check_policy_design_case_layer2_readiness.py",
  "authority_scope": [
    "value_choice_provenance",
    "authorized_value_schedule",
    "shadow_scenario_value_schedule",
    "pareto_frontier_fact",
    "value_tradeoff_disclosure"
  ],
  "may_not_use_for": [
    "production_claim_authority",
    "production_recommendation",
    "rollout_authority",
    "publication_authority",
    "claim_authority",
    "scalar_welfare_authority",
    "preference_learning_authority",
    "mandate_creation",
    "social_weight_selection_without_authorized_schedule",
    "outcome_prediction_authority",
    "forecast_calibration_authority",
    "s9_projection_maturity",
    "s10_forecast_support",
    "s11_calibration",
    "s12_envelope_growth",
    "s13_accountability_closure",
    "s14_universality"
  ]
}
```

- [ ] **Step 2: Update artifact traceability**

Edit `architecture/policy_design_case/layer2_artifact_traceability.toml` so S8
rows exactly match the manifest required artifacts:

- `AuthorizedValueSchedule`
- `ObjectiveFunctionProvenanceRecord`
- `ParetoArchive`
- `ValueChoiceProvenanceRecord`
- `ValueTradeoffDisclosureRecord`
- `ValueChoiceIntegrityReport`

Set maturity to `planned` or the repo's current slice convention before the
implementation task and `implemented` only when the validator expects it.

- [ ] **Step 3: Update cluster map**

Edit `architecture/policy_design_case/cluster_ownership_map.toml`:

- remove `[open_cell_closure.ACTOR.value_choice_provenance]`.
- update `[cell.ACTOR.value_choice_provenance]`:
  - `owner_module = "src/polisyos/runtime/quality/design_axes/value_choice_provenance.py"`
  - `ratchet_state = "implemented"`
  - `p01_chain = "implemented"`
  - `gap = "none_for_s8_value_choice_provenance_scope"`
  - `action = "preserve P20/P22 value provenance firewalls before any ranked recommendation."`
- current open cell count becomes 3.
- remaining open cells must be exactly:
  - `DESIGNER_ITSELF.envelope_growth`
  - `KNOWLEDGE.calibration`
  - `KNOWLEDGE.ir_proof_carrying_analytics`

- [ ] **Step 4: Update readiness validator**

Edit `tools/quality/validation/check_policy_design_case_layer2_readiness.py`:

- add `DEFAULT_S8_VALUE_CHOICE_MANIFEST_PATH`.
- add `S8_CLOSED_CELLS = {"ACTOR.value_choice_provenance"}`.
- add `S8_REQUIRED_ARTIFACTS`.
- add `S8_REQUIRED_FIREWALLS = {"P20", "P22", "P12", "P15", "P26"}`.
- add `S8_REQUIRED_AUTHORITY_SCOPE`.
- add `S8_REQUIRED_DENY`.
- add `S8_INVENTORY_ID = "layer2_s8_value_choice_manifest"`.
- load the manifest into payloads.
- implement `_validate_s8_value_choice(...)`.
- add S8 summary fields:
  - `s8_value_provenance_completeness`
  - `s8_expected_current_open_cell_count`
  - S8 false-clear counts.

Validator requirements:

- manifest schema version matches.
- status is active and owner is governance-board.
- `depends_on == ["S2", "S6", "S7"]`.
- closed cells exactly `ACTOR.value_choice_provenance`.
- expected current open-cell count is 3.
- cluster map current open-cell count is 3.
- Layer 2 inventory artifact count is 16 after registering S8.
- cluster cell ratchet state and P01 chain are implemented.
- cluster cell owner matches producer module.
- cluster cell firewall is `P20_normative_choice_laundering`.
- artifact traceability S8 rows match required artifacts.
- floor governance row matches `s8_value_provenance`.
- floor metric is `value_provenance_completeness`.
- floor revision rule is `ranked_recommendations_require_authorized_value_source`.
- S7 runtime exports a `value_authorization` `GovernanceDecisionClass` and
  matching `DecisionRightsMatrix` row used by S8; S7 still denies value-choice
  authority in its own manifest.
- all completeness and coverage metrics are 1.0.
- all S8 false-clear counts are 0.
- validator blocks `shadow_scenario` schedules from satisfying authorized
  ranking and blocks multi-principal records that omit affected groups,
  dissent/blocking-right refs, or alternative schedule sensitivity.
- inventory entry mirrors manifest path, schema version, owner, status,
  authority scope, deny list, validator, and canonical route.

- [ ] **Step 5: Register inventory**

Edit `architecture/policy_design_case/inventory.json`:

- add artifact id `layer2_s8_value_choice_manifest`.
- kind `layer2_s8_value_choice_manifest`.
- schema version matches the manifest.
- capability reality label `implemented`.
- owner `governance-board`.
- canonical route and validator match the manifest.

- [ ] **Step 6: Run validators**

Run:

```bash
uv run python tools/quality/validation/check_policy_design_case_layer2_readiness.py
uv run python tools/quality/validation/check_policy_design_case_cluster_ownership_map.py
```

Expected output:

- readiness validator issues: `[]`.
- cluster map validator issues: `[]`.
- current open-cell count: `3`.
- inventory artifact count: `16`.

- [ ] **Step 7: Commit Task 5**

## Task 6: Repo-Quality Tests, Snapshots, And Burn-Down Confirmation

Intent: make S8 closure durable in repo-quality checks and avoid stale S7-era
open-count assertions.

- [ ] **Step 1: Add S8 repo-quality test file**

Create `tests/repo_quality/tools/test_policy_design_case_layer2_s8_value_choice.py`.

Required tests:

- `test_layer2_s8_manifest_is_valid_and_open_count_is_3`
- `test_layer2_s8_closes_actor_value_choice_provenance_cell`
- `test_layer2_s8_required_artifacts_are_traceable_and_exported`
- `test_layer2_s8_firewalls_are_registered_and_floor_is_governed`
- `test_layer2_s8_inventory_registration_exists`
- `test_layer2_s8_inventory_and_manifest_authority_boundaries_match`
- `test_layer2_s8_b_side_consumes_injected_posture_only`
- `test_layer2_s8_search_ledger_refs_are_persisted_and_replay_visible`
- `test_layer2_s8_public_projection_is_tradeoff_shaped_pull_first`
- `test_layer2_s8_shadow_scenario_schedules_are_not_authority`
- `test_layer2_s8_arrow_disclosure_rows_are_required_for_multi_principal_conflict`
- `test_layer2_s8_negative_controls_fail_closed`
- `test_layer2_s8_manifest_metrics_match_generated_corpus_summary`
- `test_layer2_s8_corpus_summary_records_floor_and_integrity`
- `test_layer2_s8_does_not_mark_s9_s10_s11_s12_s13_or_s14_cells_implemented`

- [ ] **Step 2: Update existing open-count assertions**

Search for live current-open-cell assertions:

```bash
rg -n "current_open_cell_count.*== 4|summary\\[\\\"current_open_cell_count\\\"\\] == 4|open_cell_closure\\[\\\"open_cell_count\\\"\\] == 4" tests/repo_quality tools architecture docs/plans/active/layer2-slices
```

Update live current-open-cell assertions to 3 after S8 closure. Do not rewrite
historical manifest expected counts for S3/S4/S5/S6/S7; those remain their
slice-specific values. The live readiness summary becomes 3, while S7 manifest
still records S7's expected count of 4.

Update named closed-cell constants that the numeric `rg` will not catch:

- in `tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py`,
  add:
  ```python
  CELLS_CLOSED_THROUGH_S8 = sorted([
      *CELLS_CLOSED_THROUGH_S7,
      "ACTOR.value_choice_provenance",
  ])
  ```
- update the assertion for `summary["cells_closed_since_s0"]` to compare with
  `CELLS_CLOSED_THROUGH_S8`.
- update the assertion for `assigned - current_open_cells` to compare with
  `set(CELLS_CLOSED_THROUGH_S8)`.

Leave historical expected-count assertions alone:

- keep `summary["s6_expected_current_open_cell_count"] == 5`.
- keep `summary["s7_expected_current_open_cell_count"] == 4`.
- keep S7 manifest/test assertions that its own
  `expected_current_open_cell_count` is 4.

- [ ] **Step 3: Run full S8 verification commands**

Run focused checks:

```bash
uv run pytest \
  tests/unit/runtime/quality/test_layer2_s7_delegation.py \
  tests/unit/runtime/quality/test_design_axes_value_choice_provenance.py \
  tests/unit/pdc/test_layer2_s2_design_search.py \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s8_value_choice.py \
  -q
```

Run validators:

```bash
uv run python tools/quality/validation/check_policy_design_case_layer2_readiness.py
uv run python tools/quality/validation/check_policy_design_case_cluster_ownership_map.py
```

Run guardrails:

```bash
uv run polisyos-tools architecture guardrails check
uv run --extra runtime --extra ml polisyos-tools runtime check-runtime-api-contract
```

Run backend verification if the focused suite is green:

```bash
python3 -m tools.cli workspace verify --backend-only
```

Expected outputs:

- focused pytest suite: all green.
- both validators: `issues=[]`.
- architecture guardrails: pass.
- runtime API contract: pass.
- backend-only verify: pass.

- [ ] **Step 4: Commit Task 6**

## Task 7: Full S8 Verification Done When

S8 is complete only when all statements below are true:

1. `AuthorizedValueSchedule`, `ObjectiveFunctionProvenanceRecord`,
   `ParetoArchive`, `ValueChoiceProvenanceRecord`,
   `ValueTradeoffDisclosureRecord`, and `ValueChoiceIntegrityReport` are
   strict, replayable, and exported from `runtime.quality`.
2. S8 consumes S6 mandate refs and exact
   `MandateLegitimacyRecord.firewall_disposition`. It cannot authorize ranking
   or social weights when mandate is absent, top-level `limit`, top-level
   `block`, nested `candidate_unverified`, or otherwise not `pass`.
3. S8 consumes existing foundry welfare `SocialWeightProvenance` and
   Pareto/frontier records without reclassifying Pareto facts as value-choice
   authority.
4. B consumes injected `Layer2S8ValuePostureInput` and cannot self-rank,
   choose social weights, import S8 producers, or import foundry welfare
   modules as S8 authority.
5. Scenario value schedules are allowed only as shadow sensitivity rows; they
   cannot satisfy ranked recommendation authority until admitted through
   authorized value provenance.
6. P20 fails closed: LLM-proposed weights, corpus-derived weights, reviewer
   notes, scalar ranking without authorized schedule, and Pareto ranking without
   value source all block authority-bearing ranking.
7. P22 remains bounded: S8 can require mandate-backed value schedules but
   cannot invent mandate, expand limited mandate, or treat consultation as
   authorization.
8. P26 remains bounded: S7 can route or record human decisions, but cannot
   substitute for S8 value provenance or authorize social weights by itself.
   Valid value authorization routing cites the shared `GovernanceDecisionClass`
   `value_authorization`, matching `DecisionRightsMatrix` row, and five-rights
   validation.
9. Multi-principal incompatibility surfaces as contested conflict with affected
   groups, dissent, blocking-right refs, alternative schedule sensitivity, and
   rejected alternatives, never as a silent averaged objective.
10. Proxy-only objectives carry measurability/value-loss disclosures from S6 and
   cannot become hidden value choices.
11. S8 emits `AxisPositionDeclaration`, `AxisFirewallStatus`, typed
    `ConstraintStoreSnapshot.constraint_records`, `ClusterHandoffRecord` rows,
    persisted/replayable `SearchLedger` value refs, closeout-visible
    non-production value refs, and `DesignRecord.ledger_refs`.
12. S8 posture renders in all four audience projections:
    - PUBLIC: tradeoff-shaped, pull-first accountability summary only.
    - REVIEWER: value disposition, ranking mode, action, and P20/P22/P12/P15/P26
      statuses.
    - EXPERT/MACHINE: all refs, authorized and scenario schedule rows, objective
      provenance, conflict rows, affected groups, dissent refs, blocking rights,
      schedule sensitivity, frontier refs, rejected nondominated alternatives,
      mandate refs, integrity checks, and authority boundary.
13. All 13 corpus cases contain S8 blocks; the pinned S2 case injects S8
    posture.
14. Precision/recall/integrity metrics include budget/legal-use, acquisition,
    final-choice, proxy-only, multi-principal, LLM-weight, corpus-weight,
    blocked-mandate, Pareto-ranking-without-source, shadow-scenario spoof,
    missing Arrow disclosure, and S7-substitution triggers.
15. Negative-control false-clear counts are zero.
16. Production-posture outcomes are unchanged by S8; S2
    `canonical_outcome_effect` remains shadow-only, and S8 affects governed
    routing/value context only without granting production authority.
17. `value_provenance_completeness` floor is recorded from the governed floor
    table; no denominator or floor is changed.
18. Cluster-map open cell count is 3; both validators pass; S8 manifest is
    registered in inventory.
19. Remaining open cells are exactly `DESIGNER_ITSELF.envelope_growth`,
    `KNOWLEDGE.calibration`, and `KNOWLEDGE.ir_proof_carrying_analytics`.
20. No S9 projection maturity, S10 forecast support, S11 calibration or
    proof-carrying analytics, S12 envelope growth, S13 accountability,
    production authority, calibrated prediction, rich simulation, portfolio
    optimization, preference learning, or S14 universality battery cell is
    marked implemented.

## Commit Guidance

Mirror the S4/S5/S6/S7 red-first sequence, one logical commit per task:

```text
test: add layer2 s8 value-choice red tests
feat: add layer2 s8 value-choice contracts and P20 checks
feat: inject layer2 s8 value posture into shadow design loop
feat: classify layer2 s8 value-choice coverage
chore: close layer2 s8 value provenance cell
chore: register layer2 s8 value-choice progress
```

The Task 2 feature commit may include the narrow S7 `value_authorization`
registry/matrix extension because S8 cannot route value authorization without
it. It must not change S7's authority scope into value-choice authority.

End commit messages with the repo's standard co-author trailer. Do not mark any
S9+ projection, prediction, calibration, envelope-growth, accountability,
production, preference-learning, or S14 universality cell as implemented.
