---
plan_id: layer3-g7-envelope-widening-one-case-to-region
title: "G7 - Envelope Widening One Case To Region"
type: slice-plan
status: active
created: 2026-06-10
revised: 2026-06-10
stability: ready-for-implementation
slice: G7
depends_on:
  - docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md
  - docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
  - docs/reference/policy-design-case-failure-patterns.md
  - docs/plans/active/layer3-slices/G5-first-proving-ground-conversion.md
  - docs/plans/active/layer3-slices/G6-bounded-agent-arbitrary-request-grounded-result-or-abstention.md
  - docs/reference/policy-design-case-layer3-proving-ground-conversion.md
  - docs/reference/policy-design-case-layer3-bounded-agent.md
  - architecture/policy_design_case/layer3_g1_readiness_manifest.json
  - architecture/policy_design_case/layer3_g1_grounded_source_contracts.json
  - architecture/policy_design_case/layer3_g1_search_recall_freshness.json
  - architecture/policy_design_case/layer3_g1_substrate_search_ledgers.json
  - architecture/policy_design_case/layer3_g4_readiness_manifest.json
  - architecture/policy_design_case/layer3_g4_promotion_records.json
  - architecture/policy_design_case/layer3_g4_g5_promotion_handoff.json
  - architecture/policy_design_case/layer3_g4_governance_throughput_delta.json
  - architecture/policy_design_case/layer3_g5_readiness_manifest.json
  - architecture/policy_design_case/layer3_g5_conversion_records.json
  - architecture/policy_design_case/layer3_g5_w12d_consumer_gate.json
  - architecture/policy_design_case/layer3_g5_envelope_expansion_delta.json
  - architecture/policy_design_case/layer3_g5_status_composition_ledger.json
  - architecture/policy_design_case/layer3_g5_demand_pull_attempt_record.json
  - architecture/policy_design_case/layer3_g5_dependency_health_metric_snapshot.json
  - architecture/policy_design_case/layer3_g5_conversion_audit_surface.json
  - architecture/policy_design_case/layer3_g5_public_export_projection_refs.json
  - architecture/policy_design_case/layer3_g6_readiness_manifest.json
  - architecture/policy_design_case/layer3_g6_agent_run_records.json
  - architecture/policy_design_case/layer3_g6_grounded_result_or_abstention.json
  - architecture/policy_design_case/layer3_g6_g5_invocation_plan.json
  - architecture/policy_design_case/layer3_g6_search_ledger.json
  - architecture/policy_design_case/layer3_g6_demand_pull_vs_abstention_delta.json
  - architecture/policy_design_case/layer3_g6_orchestration_continuity.json
  - architecture/policy_design_case/layer3_g6_replay_manifest.json
  - architecture/policy_design_case/layer3_g6_agent_audit_surface.json
  - architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json
  - architecture/generated_artifacts.toml
  - architecture/public_surface/contract.toml
  - architecture/policy_design_case/inventory.json
  - src/polisyos/runtime/quality/proving_ground/pre_adapter_grounding_inventory.py
  - src/polisyos/runtime/quality/proving_ground/governed_promotion_gate.py
  - src/polisyos/runtime/quality/proving_ground/proving_ground_conversion.py
  - src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py
  - src/polisyos/runtime/quality/design_axes/resource_economics.py
  - src/polisyos/runtime/quality/design_axes/post_deploy_accountability.py
  - src/polisyos/runtime/quality/design_axes/universality_assurance.py
  - src/polisyos/runtime/quality/projection_semantics.py
  - src/polisyos/runtime/quality/public_export.py
  - src/polisyos/runtime/quality/capability_ratchet.py
  - src/polisyos/runtime/quality/nl_replay_orchestration.py
  - src/polisyos/runtime/quality/replay.py
  - tools/quality/validation/check_policy_design_case_layer3_g5_readiness.py
  - tools/quality/validation/check_policy_design_case_layer3_g6_readiness.py
  - tools/quality/validation/run_layer2_s14_universality_battery.py
context_inputs:
  - tests/unit/runtime/quality/test_layer3_g1_substrate_grounding.py
  - tests/unit/runtime/quality/test_layer3_g4_promotion_gate.py
  - tests/unit/runtime/quality/test_layer3_g5_proving_ground_conversion.py
  - tests/unit/runtime/quality/test_layer3_g6_bounded_agent.py
  - tests/unit/runtime/quality/test_layer2_s12_resource_economics.py
  - tests/unit/runtime/quality/test_layer2_s13_post_deploy_accountability.py
  - tests/unit/runtime/quality/test_layer2_s14_universality_assurance.py
  - tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py
  - tests/unit/runtime/quality/test_public_export.py
  - tests/repo_quality/tools/test_policy_design_case_layer3_g5_readiness.py
  - tests/repo_quality/tools/test_policy_design_case_layer3_g6_readiness.py
  - tests/repo_quality/tools/test_layer2_s14_universality_battery.py
cells_targeted:
  - layer3.g7_region_candidate_set
  - layer3.g7_region_grounding_matrix
  - layer3.g7_region_conversion_records
  - layer3.g7_status_composition
  - layer3.g7_s12_growth_thermometer_projection
  - layer3.g7_mechanism_reuse_ledger
  - layer3.g7_marginal_grounding_cost_ledger
  - layer3.g7_region_envelope_expansion
  - layer3.g7_region_semantic_loss
  - layer3.g7_s14_grounded_breadth_feed
  - layer3.g7_s14_battery_input_manifest
  - layer3.g7_region_scorecard_surface
expected_open_cell_count: 0
floor_id: layer3_grounding_subordination
metric: layer3_g7_region_widening
source_roadmap: docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md
constitution: docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
---

# G7 - Envelope Widening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scale the G5/G6 grounded loop from one proving-ground case to a
bounded region, such as UA-MSME-adjacent cases, while proving that any widening
comes from reused mechanisms and real grounded breadth, not relabeled bespoke
case work or fixtures.

**Architecture:** G7 lives in `runtime/quality` as a region-cohort adapter
around existing Layer 3 artifacts. It reads G1 search/source contracts, G4
promotion and governance-throughput state, G5 conversion/status/demand records,
G6 demand/orchestration records, S12-style growth/reuse signals, and S14
universality-assurance helpers. G7 does not widen G5 by fiat and does not make a
universal claim. It produces region widening audit authority only after a typed
G7 bridge proves per-case grounding, governed promotion, reuse, marginal cost,
semantic loss, replay, and S14-feed constraints.

**Tech Stack:** Python 3.14, strict Pydantic DTOs, existing G1/G4/G5/G6 typed
builders, S14 universality-assurance helpers, runtime replay/continuity helpers,
repo-quality artifact drift tests, generated-artifact registration, and
multi-audience audit/public projection surfaces.

---

## Current Reality After G6

Fresh local artifacts on 2026-06-10 show:

- G5 readiness passes as an engineering surface, but
  `g5_conversion_outcome = "unchanged_blocker"`.
- G5 has `g5_grounded_conversion_count = 0`,
  `g5_grounded_abstention_count = 0`, and
  `g5_envelope_expansion_rate = 0.0`.
- The only persisted G5 conversion record is
  `ua-msme-affordable-loans-2022` with
  `grounding_disposition = "ungrounded_blocked"` and blockers such as G4 blocked
  promotion, G1 uncertainty, G2/G3 support gaps, GL reissue, and S14 pending
  sealed overclaim.
- G5 `may_not_use_for` explicitly includes `g7_region_widening`.
- G6 readiness passes as an engineering surface, but
  `g6_grounded_value_closure_status =
  "blocked_by_current_g5_unchanged_blocker"`.
- G6 result projection is `outcome = "g5_unchanged_blocker"` and
  `grounding_disposition = "ungrounded_blocked"`.
- G6 `may_not_use_for` explicitly includes `g7_region_widening`.
- S14 has strict helpers for grounded-authority coverage, envelope revision
  dynamics, mechanism generality, claim gating, and false-clear detection, but
  current S14 battery fixtures are not a G7 grounded-breadth feed.
- G1 search/source artifacts are targeted at existing grounded constructs such
  as `firm_survival`; they prove source-contract health and recall for known
  seeds, not automatic regional candidate enumeration.
- G4 currently persists two promotion records for the pinned case: one governed
  source-data promotion and one blocked causal-forecast promotion. The existing
  governance-throughput delta is reusable, but it does not prove future region
  cases are governed.
- G5 has `Layer3G5S12DemandGrowthEvidence` and the
  `build_g5_s12_demand_growth_evidence(...)` builder in runtime code, but no
  standalone persisted `layer3_g5_s12_demand_growth_evidence.json`. The current
  persisted S12-like source of truth for G7 is the G5 demand-pull attempt,
  envelope-expansion delta, health snapshot, and public projection verification.
- G6 search ledger is `partial_budget_cutoff`, `authoritative_for = []`, and
  deny-listed for `g7_region_widening`; it is orchestration/search audit, not
  regional coverage authority.
- G1/G0 search discipline already has `GroundingSearchLedger`,
  `FreeGrowthFixture`, `MechanismGeneralityFixture`, hardcode-enumeration
  backlog, and no-hardcode lint contracts. G7 should extend that control-plane
  vocabulary for region candidate growth instead of inventing a new discovery
  proof.
- G4 promotion records are richer than `promotion_state`: full records carry
  grounded contract set refs, A-completeness ledger refs, weakest-boundary
  composition refs, human-decision integrity gate refs, G5 handoff refs, and
  rule/schema refs. G7 must validate that full gate shape before counting a case.
- S12 resource economics already validates envelope growth, growth thermometers,
  one-off refs, `held_out_status = "pending_s14"`, and deny-list propagation,
  including `s14_universality`. G7's S12 projection must preserve those
  semantics rather than publishing a looser local thermometer.
- S13 post-deploy accountability already distinguishes certified envelope
  expansion from pending, shrink, split, or hold revisions. G7 cannot count
  positive region expansion from a pending or non-expand revision.
- Public export/projection helpers already verify projection-only authority,
  official-use limits, redaction of raw/hidden payloads, and S12/S13/S14 consumer
  contracts. G7 should reuse those verification expectations in its public
  projection tests.
- The persisted S14 assurance manifest is a stable readiness/link manifest. The
  full S14 runner payload, including `public_summary`, is produced by
  `run_layer2_s14_universality_battery.py` under `_build/.tmp`; G7 must not
  depend on hidden battery payloads becoming persisted regional evidence.

This means G7 can implement engineering readiness now, but it cannot honestly
claim a grounded region until at least one additional region case is grounded
through the same bridge and the seed case is no longer an unchanged blocker. With
the current artifacts, the correct G7 value state is
`blocked_by_current_g5_unchanged_blocker` or
`blocked_by_no_real_grounded_region_breadth`, not `pass`.

## Non-Negotiable Alignment Notes

G7 has two different status readings, and the implementation must keep them
separate:

- **Engineering readiness:** the G7 producer, typed artifacts, reuse/cost
  ledgers, S14 feed bridge, surfaces, registrations, replay, and negatives are
  implemented and replayable.
- **Region value closure:** a bounded region contains real grounded case records
  with sublinear marginal grounding cost and an S14-consumable grounded-breadth
  feed.

G7 may pass engineering readiness while reporting
`g7_region_value_closure_status = "blocked_by_current_g5_unchanged_blocker"` or
`"blocked_by_no_real_grounded_region_breadth"`. It must not mark region value
closure as `pass` until persisted region cases include G5-compatible grounded
records with `grounding_disposition` in `grounded_limited` or
`grounded_abstention`, the mechanism reuse ledger proves non-bespoke reuse, and
the S14 feed bridge accepts real grounded breadth.

G5 and G6 both deny direct use for `g7_region_widening`. G7 may read those
artifacts only as dependency inputs through a G7-owned bridge. A G5 conversion
record or G6 agent run record cannot by itself close G7, cannot become universal
authority, and cannot satisfy region scorecard authority.

G6 currently treats region widening as an explicit negative
(`layer3_g6_g7_region_widening_attempt`). G7 must add its own typed bridge and
conformance proof; it must not make G6 pass by weakening that negative or by
calling a non-pinned G5 case through the G6 path.

Region widening is not a universal claim. Untested cases, axes, instruments,
jurisdictions, or mandate variants are out-of-envelope by default. S14 owns any
universal wording, and G7 may only feed S14 with bounded grounded breadth plus
limitations.

Mechanism reuse must be computed from route, adapter, producer, artifact, and
verification refs. It is not enough for cases to share a region prefix, fixture
family name, or hand-written "same mechanism" label. Bespoke per-case patches
must lower or block the mechanism-generality and marginal-cost status.

Every grounded region case must be governed per case. A case cannot count as
grounded regional breadth unless the G7 conversion record joins a G4 governed
promotion or the same G4-compatible abstention/promotion gate used by G5. Region
aggregation cannot average away a blocked or shadow promotion state.

Region candidate discovery must obey Rule 12. A bounded default candidate set may
exist for readiness determinism, but it is a control-plane fixture, not a region
coverage source. The G7 producer must prefer existing search/discovery ledgers and
include a free-growth check proving that a correctly shaped candidate row can be
discovered or consumed without changing G7 code. A hardcoded case list in module
logic cannot satisfy coverage.

S14 feed must be honest. Fixture breadth, sealed-battery cases, dev labels, G6
candidates, search hits, or unchanged blockers cannot count as grounded
authority coverage. If real grounded breadth is missing, the S14 bridge emits a
typed blocker.

S14 battery consumption must be represented as a real bridge, not a local
surrogate. G7 should write a `Layer3G7S14BatteryInputManifest` that points to the
grounded-breadth feed, mechanism-generality projection, envelope deltas, and
limitations. The sealed battery partition, hidden cases, and freeze hash must not
be mutated; a narrow S14 runner/consumer reader may read the G7 manifest only as
external grounded-breadth input and must preserve sealed access controls.

## Closure Contract

Source of truth: roadmap G7 section in
`docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md`.

G7 must deliver:

1. A bounded `Layer3G7RegionCandidateSet` for one declared region envelope, with
   case ids, adjacency basis refs, demand refs, source/search refs, and explicit
   in/out/pending envelope posture per case.
2. A `Layer3G7RegionGroundingMatrix` joining each region case to available G1,
   G4, G5, G6, GL/S14, search-health, and replay refs. Missing refs are blockers
   or limitations, never silent caveats.
3. A `Layer3G7RegionConversionRecord` producer that preserves G5 conversion
   outcomes and grounding dispositions, counts only `grounded_limited` and
   `grounded_abstention` as grounded region breadth, and keeps unchanged blockers
   ungrounded.
4. A `Layer3G7StatusCompositionLedger` that composes engineering readiness,
   per-case grounding, G4 promotion, source/search health, mechanism reuse,
   marginal cost, semantic loss, S14 feed, and public projection status without
   inventing a parallel region status lattice.
5. A `Layer3G7S12GrowthThermometerProjection` that reuses the existing G5
   S12-demand-growth builder shape plus persisted G5 demand-pull/envelope/health
   artifacts to distinguish demand-pulled region expansion from bespoke one-off
   growth. This projection feeds S14 mechanism-generality helpers; it is not a
   replacement for S12 authority and must not assume a persisted
   `layer3_g5_s12_demand_growth_evidence.json` file exists. It must validate the
   actual S12 resource-economics invariants: counted growth needs a certified
   envelope delta, one-off refs lower/block mechanism generality, and
   `held_out_status` stays `pending_s14`.
6. A `Layer3G7MechanismReuseLedger` with mechanism-family refs, reused adapter
   refs, reused source/search/promotion/conversion route refs, one-off/bespoke
   patch refs, reuse rate, and issue codes.
7. A `Layer3G7MarginalGroundingCostLedger` with baseline seed cost, per-added
   case cost, normalized effort units, reuse discount explanation, sublinear
   status, cost-curve refs, and blockers when grounded case count is
   insufficient. It cannot pass if the seed case is still an unchanged blocker.
8. A `Layer3G7RegionEnvelopeExpansionDelta` measuring
   `envelope-expansion-rate(region)` from grounded region cases divided by
   attempted bounded region cases, with search health and demand refs. Positive
   expansion requires an S13-compatible certified `expand` envelope delta; pending,
   hold, shrink, or split revisions are limitations/blockers, not numerator wins.
9. A `Layer3G7RegionSemanticLossLedger` measuring whether widened cases preserve
   source truth, authority boundary, status composition, time roles, and envelope
   semantics. Semantic loss blocks marginal-cost pass when it hides a real
   narrowing or bespoke patch.
10. A persisted `Layer3G7GovernedPromotionJoin` proving
    every grounded region case has a governed G4 promotion or grounded-abstention
    path represented by `Layer3G4PromotionRecord`. The join must check the full G4 gate shape
    (`grounded_contract_set_ref`, `a_completeness_ledger_ref`,
    `weakest_boundary_composition_ref`, `human_decision_integrity_gate_ref`,
    `g5_handoff_ref`, rule/schema refs), not just a `promotion_state` string.
    Shadow, blocked, mapping-fallback, and ref-only promotion rows remain blocked.
11. A `Layer3G7G5G6AuthorityBoundaryReport` proving G5/G6 `may_not_use_for`
   values were preserved and that G7 did not treat G5/G6 artifacts as widening
   authority without a G7 bridge.
12. A `Layer3G7S14GroundedBreadthFeed` carrying only real grounded region refs,
   grounded authority coverage refs, mechanism generality refs, envelope revision
   refs, limitations, and denied uses.
13. A `Layer3G7S14BatteryInputManifest` that makes the G7 feed consumable by the
    S14 runner/consumer without mutating hidden battery fixtures, sealed case
    content, access controls, or freeze hashes.
14. A `Layer3G7S14ConsumerGate` that calls the existing S14 helper set named in
    Task 7 and blocks fixture breadth, universal wording, bespoke disguise, missing
    grounded authority refs, and untested-axis envelope expansion.
15. A per-region scorecard and audit surface for PUBLIC/REVIEWER/EXPERT/MACHINE.
    PUBLIC sees region id, certified envelope posture, grounded/blocked counts,
    cost/reuse status, limitations, and denied uses. It never sees hidden S14
    cases, raw prompts, or recommendation text.
16. A projection-only public export surface with the full G7 deny-list and no
    production, closeout, scorecard, recommendation, legal, or universal-claim
    authority. It must pass projection-only official-use checks and S12/S13/S14
    consumer-contract verification where those payloads are present.
17. Replay continuity over the candidate set, grounding matrix, conversion
    records, reuse/cost ledgers, S14 feed, scorecard, conformance report, and
    readiness manifest.
18. A readiness CLI and generated artifact family mirroring G5/G6 drift
    discipline.
19. Negative semantic tests proving that unchanged blockers, fixtures, G6
    candidates, bespoke patches, search hits, and bare universal claims cannot
    be counted as region grounded breadth.

G7 engineering readiness is done when the readiness CLI passes over persisted
G7 artifacts, current blockers are represented honestly, future grounded-region
fixtures pass through the same bridge without code-path change, and every
bespoke/universal/fixture laundering negative control fails closed. G7 region
value closure is done only when real grounded region cases produce sublinear
marginal grounding cost and S14 accepts the grounded-breadth feed or honestly
limits the claim.

## Scope Boundaries

In scope:

- Add a focused G7 runtime-quality module and readiness CLI.
- Reuse G1 search/source contracts, G4 promotion state, G5 conversion
  classifications/status/demand records, G6 demand/orchestration refs,
  S12-style growth signals, and S14 helpers.
- Persist region candidate, grounding matrix, conversion, reuse, cost,
  status-composition, semantic-loss, S14 feed, S14 battery-input, scorecard,
  replay, conformance, and readiness artifacts.
- Add multi-audience G7 audit/public projection surfaces.
- Add positive future-grounded fixtures that prove the region path works when
  G5-compatible grounded case records exist.
- Add negative tests for unchanged blockers, bespoke disguise, fixture breadth,
  G6-candidate laundering, ungoverned promotion, public overclaim, and
  universal wording.

Out of scope:

- No universal claim authority.
- No production, rollout, approval, publication, legal advice, public
  recommendation, policy recommendation, scorecard authority, or closeout
  authority.
- No mutation of S14 sealed battery fixtures or hidden battery access.
- No counting current G5 `unchanged_blocker` as grounded breadth.
- No use of G6 agent output as region widening authority.
- No lowering of G5, G4, S14, G1 search/freshness, GL legal, or W12.D floors.
- No generic "all Ukraine MSME policy" claim beyond the certified G7 region
  envelope.
- No new domain-specific region template engine. Region case input is a bounded
  readiness fixture/control-plane input and must remain replaceable by real
  candidate discovery later.
- No mutation of closed G5/G6 artifacts or S14 sealed fixtures to make G7 pass.
- No treating runtime-only G5 S12 helper objects as persisted source-of-truth
  artifacts. G7 may reuse the builder shape and persisted demand/envelope refs,
  but it owns any G7 projection it writes.
- No counting a G4 mapping/sequence fallback promotion record as governed region
  promotion. Fallback-blocked G4 records are useful negatives only.
- No counted S12-style growth unless the row satisfies S12 envelope-growth shape
  and the G7/S13 expansion delta proves a certified `expand` revision.

## Pattern Pass

| Pattern | G7 risk | Closure move |
| --- | --- | --- |
| P01 contract-only capability | Region DTOs exist but no producer persists or bridges to S14. | Build producer -> persisted artifacts -> S14 consumer gate -> surfaces -> negatives. |
| P02 thin orchestration | G5/G6/S14 components coexist but no typed handoff connects them. | G7 grounding matrix, S14 feed, and consumer gate connect refs explicitly. |
| P03 hidden internal richness | Reuse/cost status is buried in a manifest. | Multi-audience region scorecard, audit surface, and public projection refs. |
| P04 status lattice gap | Region `pass` hides unchanged blockers or partial cases. | Separate engineering readiness, region value closure, per-case conversion state, S14 feed state, and marginal-cost state. |
| P05 authority dilution | G5/G6 outputs are treated as G7 widening authority. | G7 bridge preserves upstream denied uses and owns only region audit/cost/feed authority. |
| P07 rule replay gap | Region widening cannot be reproduced under the same rules and case set. | Store region set fingerprint, rule/schema versions, route registry, and replay manifest. |
| P08 time-role conflation | Case observation time, demand time, conversion time, S14 feed time, and replay time blur. | Persist distinct observed-through, request, conversion, feed, generated, and replay timestamps/refs. |
| P10 semantic adequacy gap | Tests only check artifact presence. | Negative controls assert unchanged blocker, fixture breadth, bespoke patch, and universal wording are blocked. |
| P13 governance gravity | G7 becomes a full regional policy engine. | Keep G7 as a cohort adapter and measurement layer; no new domain producer. |
| P14 evidence independence inflation | Multiple region cases share one lineage but are counted as independent breadth. | Effective independence and lineage collapse reasons are part of the grounding matrix and semantic-loss ledger. |
| P15 LLM speculation laundering | G6 agent candidate branches become region cases. | G6 refs are demand/orchestration diagnostics only; candidate refs cannot satisfy grounded breadth. |
| P16 epistemic-regime laundering | A regional envelope implies regime/mandate precision not earned per case. | Per-case envelope posture and S14 default-out for untested axes. |
| P25 search-control laundering | Search hits or no-hits become proof of regional coverage. | Search ledgers remain control-plane; recall/freshness joins gate abstention/coverage claims. |
| P26 responsibility-integrity laundering | Region widening drops accountable-principal/demand-pull ownership. | Candidate rows and health deltas carry S12/S3/accountable-principal refs or remain blocked. |
| P27 projection-surface laundering | G7 public payload exposes hidden/raw/S14 material or authority-shaped fields. | Reuse public-export projection-only, redaction, official-use, and S12/S13/S14 consumer-contract checks. |
| P28 envelope-delta laundering | Pending or non-expand revisions are counted as region expansion. | Require S13-certified expand deltas for positive expansion; hold/shrink/split/pending stay limited or blocked. |

Capability transition:

| Capability | Current label | Target label | Acceptance signal |
| --- | --- | --- | --- |
| Region widening producer | `producer_missing`, `artifact_missing`, `bridge_missing`, `surface_missing`, `semantic_test_missing` | `implemented` for engineering readiness | Region candidate set -> grounding matrix -> region conversion records -> reuse/cost ledgers -> surfaces -> negatives. |
| Region value closure | `blocked_by_current_g5_unchanged_blocker` | `implemented` only after real grounded breadth | Grounded region case count >= 2, no unchanged-blocker counted, sublinear cost pass, S14 feed pass or honest limitation. |
| Status composition | `producer_missing` | `implemented` | G7 readiness cannot pass when local region status conflicts with per-case, S14 feed, semantic-loss, or public projection status. |
| Mechanism reuse and marginal cost | `producer_missing` | `implemented` | Reused mechanism refs and cost ledger compute pass/blocked/fail from case records and bespoke patch refs. |
| S14 grounded-breadth feed and battery input | `bridge_missing`, `consumer_missing` | `implemented` | G7 feed calls S14 helpers, emits a battery-input manifest, and blocks fixture/universal/bespoke laundering. |
| Region scorecard surface | `surface_missing` | `implemented` | PUBLIC/REVIEWER/EXPERT/MACHINE surfaces expose region state without raw or hidden authority leaks. |
| Universal claim authority | `surface_out_of_scope` for G7 | S14-owned only | G7 public projection says S14 gates universal wording and cannot authorize it. |

## Code-Grounded Reality

Existing strengths to reuse:

- `src/polisyos/runtime/quality/proving_ground/proving_ground_conversion.py` already has
  strict G5 conversion records, grounding dispositions, envelope-expansion
  deltas, W12.D consumer gate, public projections, and conformance negatives.
- G5 already persists a status-composition ledger and demand-pull attempt record;
  G7 should read those rather than inventing a separate region-only status or
  demand vocabulary.
- G5 already implements `Layer3G5S12DemandGrowthEvidence` and
  `build_g5_s12_demand_growth_evidence(...)`; G7 should reuse that shape, while
  recognizing that the S12 evidence itself is currently embedded in the G5 bundle
  and not persisted as its own artifact.
- G5 unit tests already exercise future `typed_blocker -> grounded_limited` and
  `typed_blocker -> grounded_abstention` paths even though the current persisted
  readiness bundle remains `unchanged_blocker`.
- G5 persists `region_ref = "region://ua"` in its envelope expansion delta, so
  G7 has a starting region ref without inventing a new region taxonomy.
- `src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py` already persists G6
  request class, envelope match, search ledger, orchestration audit, G5
  invocation, replay, demand-pull-vs-abstention, and public audit surfaces.
- G6 conformance already blocks `g7_region_widening_attempt`, which is exactly
  the boundary G7 must respect.
- G6 replay and orchestration continuity already wrap the shared
  `build_replay_manifest(...)` and
  `build_nl_replay_orchestration_continuity(...)` helpers. G7 should follow that
  pattern instead of creating a parallel replay vocabulary.
- `src/polisyos/runtime/quality/design_axes/universality_assurance.py` already
  exposes `build_grounded_authority_coverage_record`,
  `build_envelope_revision_dynamics_record`,
  `build_s14_mechanism_generality_from_growth_thermometer`,
  `build_mechanism_generality_report`, `gate_universality_claim`, and
  `verify_universality_claim_authority`.
- S14 tests already cover bare universal claim blocking, untested axis
  out-of-envelope behavior, mechanism generality requiring sublinear marginal
  bespoke cost, and battery-result authority leaks.
- S14's `EvaluationStatusCompositionRecord` explicitly rejects a
  `new_s14_authority_tier`; G7 status composition should follow that pattern and
  map region outcomes into existing closeout/projection statuses.
- `projection_semantics.py` already enforces required S12/S13/S14
  `may_not_be_used_for` sets, forbids authority laundering, blocks S12 growth
  without envelope delta, and blocks S14 aggregate universal scores or hidden/gold
  material.
- `public_export.py` already redacts raw/hidden/sealed payloads, enforces
  `authority_role = "projection_only"`, and rejects public exports that look like
  approval/scorecard/closeout authority.
- `layer2_resource_economics.py` has strict `EnvelopeGrowthLedger` and
  `GrowthThermometerRecord` semantics, including `held_out_status =
  "pending_s14"` and S14 deny-list propagation.
- `layer2_post_deploy_accountability.py` requires certified `expand` envelope
  deltas before an expansion can be treated as envelope revision evidence.
- G1 search recall/freshness and grounded source contracts already provide the
  search/source health signals G7 needs to avoid false regional coverage.
- G1 substrate search ledgers are complete for targeted source-contract searches,
  but their `authoritative_for` is empty and their denied uses include
  `search_hit_as_authority`; this is strong evidence for a control-plane join,
  not a regional coverage claim.
- G1/G0 `FreeGrowthFixture`, `MechanismGeneralityFixture`, hardcode backlog, and
  no-hardcode lint already encode the discovery-growth proof G7 needs for bounded
  region candidate input.
- G4 promotion records and G5 handoff already distinguish governed promoted and
  blocked promotion state.
- G4 `build_g4_promotion_records(...)` has a Mapping/Sequence fallback that emits
  blocked records when full promotion inputs are missing. That is safe behavior,
  but G7 tests must not accidentally treat fallback-blocked rows as positive
  governance.
- G4 governance-throughput delta is already a health signal that G7 can reuse for
  per-region governance-throughput instead of hand-counting promotion latency.
- G5/G6 readiness CLIs provide the artifact writer, drift, docs, inventory, and
  generated-artifacts registration patterns G7 should copy.

Current weak points G7 must account for:

- `build_layer3_g5_bundle(...)` is still pinned to
  `ua-msme-affordable-loans-2022` and currently produces only an
  `unchanged_blocker`. G7 must not pretend that this is a grounded seed.
- G5 contains an explicit non-pinned widening blocker. G7 should not remove that
  blocker in order to close itself; it should build a separate region cohort
  bridge that reads G5-compatible conversion records and reports blockers
  honestly.
- Current G5/G6 artifacts deny direct use for `g7_region_widening`; G7 must
  preserve that in its authority-boundary report.
- Current repo has zero real grounded region breadth. S14 feed status must be
  blocked until future grounded case records exist.
- Current G4 promotion records are seed-case records only. Future region-positive
  tests must either use G4-compatible synthetic records in test scope or wait for
  real persisted G4 records; G7 cannot infer governed promotion from shared
  region labels.
- Current G6 demand and search artifacts are diagnostic: the persisted G6 main
  run has no demand signal refs, and the demand-pull-vs-abstention health delta
  is a reading, not candidate authority.
- S14 battery fixtures contain grounded-authority refs for S14's own tests; G7
  must not reuse them as evidence that the region has real grounded breadth.
- S14's persisted assurance manifest stores status/ref summaries; it is not the
  same as the full runner output. Any G7 input hook should add a small external
  grounded-breadth reference to the runner payload and tests, not rewrite the
  persisted S14 manifest into a regional artifact.
- S12/S13 look deceptively easy to approximate, but their current contracts are
  doing real authority work. G7 must fail if a local projection omits S12 deny-list
  entries, marks `held_out_status` as completed, counts growth without certified
  delta, or counts pending/non-expand S13 revisions as expansion.
- Public projection can pass artifact-shape tests while still leaking authority.
  G7 readiness must check projection-only authority role, official-use limits, raw
  payload redaction, required deny-lists, and S12/S13/S14 consumer-contract
  statuses.
- Generated-artifact/docs registration can drift independently from runtime
  output. G7 must have exact path, exact drift-key, generated family, inventory,
  public-surface, docs inventory, index, and README checks like G5/G6.
- A region candidate set could easily become a domain template list. Keep it as
  bounded control-plane input, with a free-growth test that accepts a correctly
  shaped new case row without code change and a no-hardcode check that prevents
  module constants from becoming the claimed coverage source.
- Marginal-cost claims can be gamed by hiding bespoke work in labels. G7 must
  expose one-off refs, semantic loss, effective lineage collapse, and cost
  denominators.
- If the S14 battery runner cannot yet consume a G7 input manifest, the G7
  readiness manifest must name that `consumer_missing` or
  `implemented_but_not_orchestrated`; it must not call S14 consumption complete.

## File Structure

Create:

- `src/polisyos/runtime/quality/proving_ground/region_widening.py` - G7 contracts,
  builders, dependency snapshot, region candidate set, grounding matrix,
  conversion records, status composition, S12 growth thermometer projection,
  mechanism reuse, marginal cost, semantic loss, S14 feed, S14 battery input
  manifest, scorecard, public/audit projections, replay, and conformance checks.
- `tools/quality/validation/check_policy_design_case_layer3_g7_readiness.py` -
  readiness CLI, write mode, exact artifact set, runtime drift, docs and
  registration checks.
- `tests/unit/runtime/quality/test_layer3_g7_region_widening.py` - DTO,
  builder, reuse/cost/S14 bridge, surface, replay, and negative unit tests.
- `tests/repo_quality/tools/test_policy_design_case_layer3_g7_readiness.py` -
  readiness report, artifact family, docs, public surface, and drift tests.
- `tests/repo_quality/tools/test_policy_design_case_layer3_g7_readiness_cli.py`
  - CLI JSON, write-artifact exact set, and issue-code smoke tests.
- `docs/reference/policy-design-case-layer3-region-widening.md` - generated
  audit surface documentation.

Modify:

- `architecture/generated_artifacts.toml` - register the G7 generated artifact
  family.
- `architecture/policy_design_case/inventory.json` - register
  `layer3_g7_region_widening_surface` and projection refs.
- `docs/reference/generated-artifacts.md` - add regenerated G7 artifacts.
- `docs/reference/public-surface.md` - add the G7 generated audit surface.
- `docs/reference/documentation-inventory.md` and `docs/reference/index.md` -
  add the G7 reference doc.
- `src/polisyos/runtime/quality/README.md` - add G7 as a runtime-quality region
  adapter and note that it is not eagerly exported.
- `tools/quality/validation/run_layer2_s14_universality_battery.py` - add a
  read-only G7 grounded-breadth input manifest hook with
  `g7_battery_input_manifest_path: str | Path | None = None` plus CLI flag
  `--g7-battery-input-manifest`, that preserves sealed-battery access and
  freeze-hash behavior.
- `tests/repo_quality/tools/test_layer2_s14_universality_battery.py` - prove the
  G7 input hook does not mutate hidden battery behavior.

Avoid unless explicitly justified:

- `src/polisyos/runtime/quality/proving_ground/proving_ground_conversion.py` - do not
  remove the pinned-case or non-pinned-widening protections just to make G7
  green. If implementation needs a reusable G5-compatible case conversion
  builder, add red replay/compat tests first and keep old G5 artifacts stable.
- `tools/quality/validation/run_layer2_s14_universality_battery.py` - do not
  mutate sealed-battery behavior. A narrow reader for the G7 battery
  input manifest is allowed only if hidden case content, access mode, partition
  ownership, and freeze-hash checks remain unchanged and tested.
- `src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py` - do not weaken the
  G6 `g7_region_widening_attempt` negative.
- `architecture/imports/policy.toml` - default G7 path should stay inside
  `runtime/quality` and existing allowed dependencies.
- `src/polisyos/runtime/quality/__init__.py` - G0, G5, and G6 are not eagerly
  exported; G7 should follow that pattern.

Expected persisted artifacts:

```text
architecture/policy_design_case/layer3_g7_dependency_readiness_snapshot.json
architecture/policy_design_case/layer3_g7_region_candidate_set.json
architecture/policy_design_case/layer3_g7_region_grounding_matrix.json
architecture/policy_design_case/layer3_g7_region_case_conversion_inputs.json
architecture/policy_design_case/layer3_g7_region_conversion_records.json
architecture/policy_design_case/layer3_g7_region_conversion_status_matrix.json
architecture/policy_design_case/layer3_g7_governed_promotion_join.json
architecture/policy_design_case/layer3_g7_status_composition_ledger.json
architecture/policy_design_case/layer3_g7_s12_growth_thermometer_projection.json
architecture/policy_design_case/layer3_g7_mechanism_reuse_ledger.json
architecture/policy_design_case/layer3_g7_marginal_grounding_cost_ledger.json
architecture/policy_design_case/layer3_g7_region_envelope_expansion_delta.json
architecture/policy_design_case/layer3_g7_region_semantic_loss_ledger.json
architecture/policy_design_case/layer3_g7_search_recall_freshness_join.json
architecture/policy_design_case/layer3_g7_g5_g6_authority_boundary_report.json
architecture/policy_design_case/layer3_g7_s14_grounded_breadth_feed.json
architecture/policy_design_case/layer3_g7_s14_mechanism_generality_projection.json
architecture/policy_design_case/layer3_g7_s14_battery_input_manifest.json
architecture/policy_design_case/layer3_g7_s14_consumer_gate.json
architecture/policy_design_case/layer3_g7_region_scorecard.json
architecture/policy_design_case/layer3_g7_region_widening_audit_surface.json
architecture/policy_design_case/layer3_g7_public_export_projection_refs.json
architecture/policy_design_case/layer3_g7_orchestration_continuity.json
architecture/policy_design_case/layer3_g7_replay_manifest.json
architecture/policy_design_case/layer3_g7_conformance_report.json
architecture/policy_design_case/layer3_g7_health_metric_delta.toml
architecture/policy_design_case/layer3_g7_region_route_contract_registry.toml
architecture/policy_design_case/layer3_g7_registry_ratchet_delta.json
architecture/policy_design_case/layer3_g7_readiness_manifest.json
```

## Task 1: Red Baseline And Constants

**Files:**

- Create: `tests/unit/runtime/quality/test_layer3_g7_region_widening.py`
- Create: `tests/repo_quality/tools/test_policy_design_case_layer3_g7_readiness.py`
- Create: `src/polisyos/runtime/quality/proving_ground/region_widening.py`
- Create: `tools/quality/validation/check_policy_design_case_layer3_g7_readiness.py`

- [x] **Step 1: Add red tests for the G7 contract surface**

Add a constants test that fails because the module does not exist:

```python
def test_layer3_g7_constants_define_region_boundary() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    assert g7.G7_SCHEMA_VERSION == (
        "policyos.policy_design_case.layer3_g7_region_widening.v1"
    )
    assert g7.G7_RULE_VERSION == "policyos.layer3.g7.region_widening.v1"
    assert "layer3_g7_region_widening_audit" in g7.G7_AUTHORITATIVE_FOR
    assert "universal_claim_authority" in g7.G7_MAY_NOT_USE_FOR
    assert "policy_recommendation" in g7.G7_MAY_NOT_USE_FOR
```

Add repo-quality expectations for the exact artifact set above.

- [x] **Step 2: Add minimal constants and issue dictionary**

In `src/polisyos/runtime/quality/proving_ground/region_widening.py`, add strict model
base and constants:

```python
G7_SCHEMA_VERSION = "policyos.policy_design_case.layer3_g7_region_widening.v1"
G7_RULE_VERSION = "policyos.layer3.g7.region_widening.v1"
G7_SURFACE_ID = "layer3_g7_region_widening_surface"
G7_GENERATED_ARTIFACT_FAMILY_ID = (
    "policy-design-case-layer3-g7-region-widening-artifacts"
)

G7_AUTHORITATIVE_FOR = (
    "layer3_g7_region_widening_audit",
    "layer3_g7_marginal_grounding_cost_reading",
    "layer3_g7_s14_grounded_breadth_feed",
)
G7_MAY_NOT_USE_FOR = (
    "production_authority",
    "production_claim_authority",
    "rollout_authority",
    "publication_authority",
    "approval_authority",
    "scorecard_authority",
    "closeout_authority",
    "runtime_closeout_authority",
    "public_recommendation",
    "policy_recommendation",
    "legal_advice",
    "claim_authority",
    "obligation_authority",
    "causal_effect_authority",
    "proof_authority",
    "legal_authority",
    "recommendation_authority",
    "universal_claim_authority",
    "universal_claim_authority_without_s14",
    "s14_universality_claim_without_s14_gate",
    "g8_metric_governance_authority",
)
```

Required issue-code families:

```text
layer3_g7_g5_readiness_missing
layer3_g7_g6_readiness_missing
layer3_g7_current_g5_unchanged_blocker
layer3_g7_no_real_grounded_region_breadth
layer3_g7_region_candidate_set_missing
layer3_g7_candidate_set_hardcoded_as_coverage
layer3_g7_region_case_without_grounding_matrix
layer3_g7_status_composition_missing
layer3_g7_g5_unchanged_blocker_counted_as_grounded
layer3_g7_g6_candidate_counted_as_grounded
layer3_g7_fixture_breadth_counted_as_grounded
layer3_g7_grounded_case_without_governed_promotion
layer3_g7_g4_seed_promotion_projected_to_region
layer3_g7_g4_promotion_gate_shape_missing
layer3_g7_g4_mapping_fallback_counted_as_governed
layer3_g7_bespoke_patch_counted_as_reuse
layer3_g7_marginal_cost_without_cost_ledger
layer3_g7_sublinear_claim_without_grounded_cases
layer3_g7_s12_growth_thermometer_missing
layer3_g7_s12_projection_bypasses_resource_economics_shape
layer3_g7_s12_growth_without_certified_delta
layer3_g7_s12_held_out_status_overclaimed
layer3_g7_s12_deny_list_omitted
layer3_g7_s13_certified_delta_missing
layer3_g7_pending_delta_counted_as_expansion
layer3_g7_search_hit_counted_as_coverage
layer3_g7_search_recall_or_freshness_missing
layer3_g7_governance_throughput_missing
layer3_g7_accountable_principal_missing
layer3_g7_effective_independence_inflated
layer3_g7_semantic_loss_hidden_by_region_score
layer3_g7_g5_may_not_use_for_ignored
layer3_g7_g6_may_not_use_for_ignored
layer3_g7_s14_feed_missing
layer3_g7_s14_battery_input_manifest_missing
layer3_g7_s14_feed_uses_fixtures
layer3_g7_s14_consumer_gate_missing
layer3_g7_s14_manifest_runner_output_conflated
layer3_g7_universal_claim_without_s14_gate
layer3_g7_public_projection_authority_leak
layer3_g7_public_raw_payload_leak
layer3_g7_projection_omits_required_deny_list
layer3_g7_public_projection_contract_failed
layer3_g7_generated_artifacts_family_missing
layer3_g7_inventory_surface_missing
layer3_g7_reference_index_missing
layer3_g7_route_contract_registry_missing
layer3_g7_manifest_runtime_drift
layer3_g7_replay_manifest_missing
layer3_g7_orchestration_continuity_missing
layer3_g7_replay_helper_bypassed
layer3_g7_closed_case_replay_mutated
layer3_g7_persisted_artifact_missing
```

- [x] **Step 3: Run the constants test**

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer3_g7_region_widening.py::test_layer3_g7_constants_define_region_boundary -q
```

Expected: pass after constants exist.

## Task 2: Dependency Snapshot And Honest Current Blocker

**Files:**

- Modify: `src/polisyos/runtime/quality/proving_ground/region_widening.py`
- Modify: `tests/unit/runtime/quality/test_layer3_g7_region_widening.py`

- [x] **Step 1: Add dependency snapshot DTOs**

Implement:

- `Layer3G7DependencyReadinessSnapshot`
- `Layer3G7EngineeringReadinessStatus = Literal["pass", "fail", "blocked"]`
- `Layer3G7RegionValueClosureStatus = Literal[
  "pass",
  "blocked_by_current_g5_unchanged_blocker",
  "blocked_by_no_real_grounded_region_breadth",
  "blocked_by_bespoke_reuse",
  "blocked_by_s14_feed",
  "fail",
]`

The snapshot must read:

- G1 readiness and search recall/freshness.
- G1 substrate search ledgers as control-plane search evidence, not coverage
  authority.
- G4 readiness, promotion records, and governance-throughput delta.
- G5 readiness, conversion records, W12.D gate, envelope delta,
  status-composition ledger, demand-pull attempt record, dependency health
  metric snapshot, and `may_not_use_for`.
- G6 readiness, result projection, search ledger, agent run records, and
  `may_not_use_for`.
- G6 G5-invocation plan, demand-pull-vs-abstention delta, orchestration
  continuity, and replay manifest as diagnostics/continuity inputs.
- S14 assurance manifest presence and helper availability. Do not require
  `_build/.tmp` S14 runner output for G7 readiness.

- [x] **Step 2: Preserve current reality in tests**

Add a current-artifact test:

```python
def test_g7_dependency_snapshot_reports_current_g5_blocker() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    snapshot = g7.build_g7_dependency_readiness_snapshot(g7.DEFAULT_REPO_ROOT)

    assert snapshot.engineering_readiness_status == "pass"
    assert snapshot.g5_conversion_outcome == "unchanged_blocker"
    assert snapshot.g5_grounded_region_seed_count == 0
    assert snapshot.region_value_closure_status == (
        "blocked_by_current_g5_unchanged_blocker"
    )
    assert "g7_region_widening" in snapshot.g5_may_not_use_for
    assert "g7_region_widening" in snapshot.g6_may_not_use_for
```

- [x] **Step 3: Add validation that blocks overclaim**

`validate_layer3_g7_bundle(...)` must fail if:

- G5 readiness is missing or not `pass`.
- G6 readiness is missing or not `pass`.
- Current G5 `unchanged_blocker` is counted as grounded breadth.
- Current G6 `g5_unchanged_blocker` is counted as region conversion.
- A seed-case G4 promotion is copied onto adjacent region cases without a
  per-case promotion record or G4-compatible synthetic test record.
- G5/G6 `may_not_use_for` deny-list is dropped.
- G7 status composition claims `pass` while per-case, S14 feed, semantic-loss, or
  marginal-cost status is blocked.
- Closed G5/G6 replay payloads are mutated in order to make a G7 region pass.

## Task 3: Region Candidate Set And Grounding Matrix

**Files:**

- Modify: `src/polisyos/runtime/quality/proving_ground/region_widening.py`
- Modify: `tests/unit/runtime/quality/test_layer3_g7_region_widening.py`

- [x] **Step 1: Add region candidate DTOs**

Implement:

- `Layer3G7RegionCaseCandidate`
- `Layer3G7RegionCandidateSet`
- `Layer3G7RegionGroundingMatrixRow`
- `Layer3G7RegionGroundingMatrix`
- `Layer3G7SearchRecallFreshnessJoin`

Fields must include case id, region ref, adjacency basis refs, source/search
refs, demand refs, S12/VOI refs, S3 demand-pull refs,
accountable-principal refs, G6 request/agent refs or explicit missing-ref
limitations, G4/G5 refs or explicit missing-ref blockers, declared envelope refs,
time refs, posture, blockers, limitations, and full G7 denied uses.

Default readiness candidate set:

- seed case: `ua-msme-affordable-loans-2022`
- adjacent readiness fixture: `ua-msme-energy-resilience-2022`
- adjacent readiness fixture: `ua-msme-export-credit-2022`
- adjacent readiness fixture: `ua-msme-displaced-firm-recovery-2022`

These default rows are control-plane inputs only. They are not domain templates
and cannot become grounded breadth without conversion records. The builder must
tag fixture rows as `candidate_source = "readiness_control_plane_fixture"` and
must not treat the literal default list as regional coverage.

- [x] **Step 2: Add free-growth test**

Add a test proving a correctly shaped new case row can enter the candidate set
without code change:

```python
def test_g7_region_candidate_set_accepts_new_shaped_case_without_code_change() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    candidate_set = g7.build_g7_region_candidate_set(
        region_ref="region://ua/msme-adjacent",
        case_rows=[
            {
                "case_id": "ua-msme-working-capital-synthetic",
                "adjacency_basis_refs": ["adjacency://ua-msme/support-instrument"],
                "demand_refs": ["demand://s12/ua-msme/working-capital"],
                "search_ledger_refs": ["repo://architecture/policy_design_case/layer3_g1_search_recall_freshness.json"],
                "declared_envelope_refs": ["envelope://g7/ua-msme-adjacent"],
            }
        ],
    )

    assert candidate_set.case_count == 1
    assert candidate_set.cases[0].case_id == "ua-msme-working-capital-synthetic"
```

Add a no-hardcode coverage negative:

```python
def test_g7_hardcoded_candidate_rows_do_not_satisfy_coverage() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    candidate_set = g7.build_g7_region_candidate_set(
        region_ref="region://ua/msme-adjacent",
        case_rows=g7.default_readiness_candidate_rows(),
    )
    matrix = g7.build_g7_region_grounding_matrix(
        candidate_set=candidate_set,
        search_discovery_refs=(),
    )

    assert matrix.coverage_status == "blocked_control_plane_only"
    assert "layer3_g7_candidate_set_hardcoded_as_coverage" in matrix.issue_codes
```

- [x] **Step 3: Build grounding matrix joins**

The matrix must join each candidate to:

- G1 source contracts and search freshness.
- G1 substrate search-ledger refs and no-hit/incompleteness reasons, while
  preserving `authoritative_for = []` and `search_hit_as_authority` denial.
- G4 promotion state.
- G5 conversion records; missing records become typed blockers.
- G6 demand/orchestration refs; missing refs become limitations or blockers
  according to the row's authority need.
- GL legal status when legal authority is needed.
- S14 declared envelope and pending feed refs.
- S12/S3 demand/accountable-principal refs when the row is demand-pulled.

Missing joins produce typed blockers. Search hits alone produce
`control_plane_candidate`, not grounded coverage.

## Task 4: Region Conversion Records

**Files:**

- Modify: `src/polisyos/runtime/quality/proving_ground/region_widening.py`
- Modify: `tests/unit/runtime/quality/test_layer3_g7_region_widening.py`

- [x] **Step 1: Add conversion DTOs**

Implement:

- `Layer3G7RegionCaseConversionInput`
- `Layer3G7RegionConversionRecord`
- `Layer3G7RegionConversionStatusMatrix`
- `Layer3G7GovernedPromotionJoin`

The G7 conversion record must carry:

- `case_id`
- `region_ref`
- `g5_conversion_record_ref`
- `g5_conversion_outcome`
- `grounding_disposition`
- `region_grounding_status`
- `governed_promotion_status`
- `source_contract_status`
- `search_health_status`
- `effective_independence_status`
- `g4_promotion_record_ref`
- `g4_governed_promotion_join_status`
- `g4_grounded_contract_set_ref`
- `g4_a_completeness_ledger_ref`
- `g4_weakest_boundary_composition_ref`
- `g4_human_decision_integrity_gate_ref`
- `g4_g5_handoff_ref`
- blocker and limitation refs
- upstream `may_not_use_for`
- G7 authority boundary

Only these count as grounded breadth:

```text
grounding_disposition == "grounded_limited"
grounding_disposition == "grounded_abstention"
g4_governed_promotion_join_status == "pass"
required G4 promotion gate-shape refs are present
```

These never count:

```text
grounding_disposition == "ungrounded_blocked"
g5_conversion_outcome == "unchanged_blocker"
source_class == "g6_candidate"
source_class == "fixture_only"
search_status == "hit_without_adapter"
g4_governed_promotion_join_status in {"missing", "blocked", "shadow_only"}
g4_record_source == "mapping_fallback_blocked"
missing any required G4 gate-shape ref
```

`Layer3G7GovernedPromotionJoin` must validate synthetic and real positive
promotion/abstention rows with `Layer3G4PromotionRecord.model_validate(...)` and
the full G4 gate-shape refs above. A plain Mapping/Sequence fallback from
`build_g4_promotion_records(...)` is only a blocked negative fixture and cannot
be counted as governed region promotion.

- [x] **Step 2: Add current blocker test**

```python
def test_g7_does_not_count_current_g5_unchanged_blocker_as_region_grounded() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    bundle = g7.build_layer3_g7_bundle(g7.DEFAULT_REPO_ROOT)

    assert bundle.region_conversion_status_matrix.grounded_region_case_count == 0
    assert bundle.region_value_closure_status == (
        "blocked_by_current_g5_unchanged_blocker"
    )
    assert "layer3_g7_g5_unchanged_blocker_counted_as_grounded" not in (
        bundle.region_conversion_status_matrix.issue_codes
    )
```

- [x] **Step 3: Add synthetic future grounded test**

Add a synthetic test-record builder with two G5-compatible grounded records. This
is not a persisted current claim; it proves future G5 outputs will flow through
G7 without code-path change. These synthetic test records should be labeled
`source_class = "synthetic_g5_compatible_test_record"`, never
persisted as current breadth, and joined to G4-compatible promotion records in
test scope. The synthetic conversion inputs must validate through the G5
conversion-record shape, and the synthetic promotion inputs must validate
through `Layer3G4PromotionRecord.model_validate(...)` with the full gate-shape
refs required by `Layer3G7GovernedPromotionJoin`.

```python
def test_g7_future_grounded_region_cases_count_only_after_g5_grounding() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    records = g7.build_g7_region_conversion_records(
        region_ref="region://ua/msme-adjacent",
        conversion_inputs=g7.synthetic_future_grounded_region_records(),
    )

    assert sum(row.is_grounded for row in records) >= 2
    assert all(row.source_class != "fixture_only" for row in records)
```

Add an ungoverned-promotion negative:

```python
def test_g7_grounded_record_without_governed_promotion_is_blocked() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    records = g7.build_g7_region_conversion_records(
        region_ref="region://ua/msme-adjacent",
        conversion_inputs=g7.synthetic_future_grounded_region_records(
            governed_promotion_status="missing"
        ),
    )

    assert sum(row.is_grounded for row in records) == 0
    assert "layer3_g7_grounded_case_without_governed_promotion" in {
        code for row in records for code in row.issue_codes
    }
```

Add a full-gate-shape negative:

```python
def test_g7_governed_promotion_join_requires_full_g4_gate_shape() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    records = g7.build_g7_region_conversion_records(
        region_ref="region://ua/msme-adjacent",
        conversion_inputs=g7.synthetic_future_grounded_region_records(
            omit_g4_gate_ref="weakest_boundary_composition_ref",
        ),
    )

    assert sum(row.is_grounded for row in records) == 0
    assert "layer3_g7_g4_promotion_gate_shape_missing" in {
        code for row in records for code in row.issue_codes
    }
```

Add a mapping-fallback negative:

```python
def test_g7_does_not_count_g4_mapping_fallback_as_governed() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    records = g7.build_g7_region_conversion_records(
        region_ref="region://ua/msme-adjacent",
        conversion_inputs=g7.synthetic_future_grounded_region_records(
            g4_record_source="mapping_fallback_blocked",
        ),
    )

    assert sum(row.is_grounded for row in records) == 0
    assert "layer3_g7_g4_mapping_fallback_counted_as_governed" in {
        code for row in records for code in row.issue_codes
    }
```

## Task 5: Mechanism Reuse And Marginal Cost

**Files:**

- Modify: `src/polisyos/runtime/quality/proving_ground/region_widening.py`
- Modify: `tests/unit/runtime/quality/test_layer3_g7_region_widening.py`

- [x] **Step 1: Add reuse and cost DTOs**

Implement:

- `Layer3G7S12GrowthThermometerProjection`
- `Layer3G7MechanismReuseRecord`
- `Layer3G7MechanismReuseLedger`
- `Layer3G7MarginalGroundingCostRow`
- `Layer3G7MarginalGroundingCostLedger`

The S12 growth thermometer projection must expose:

- `thermometer_ref`
- refs or digests for the G5 demand-pull attempt, envelope-expansion delta, and
  dependency health snapshot used as inputs
- `demand_pull_refs`
- `accountable_principal_refs`
- `reused_primitive_refs`
- `one_off_growth_refs`
- `held_out_status`
- `held_out_battery_ref`
- `certified_envelope_delta_refs`
- `growth_without_envelope_delta_count`
- `growth_counting_disposition`
- `reuse_rate`
- `may_not_use_for`

It is a projection over demand/reuse evidence consumed by G7 and S14 helpers,
not a new S12 authority producer.

Implementation note: build this projection from persisted G5 demand-pull and
envelope artifacts plus explicit S12 case signals supplied by the G7 builder
parameters and validated through the G5 builder shape. Absence of those signals is
represented by the current G7 blocker states. Do not add a dependency on a nonexistent
`layer3_g5_s12_demand_growth_evidence.json` artifact.

Also validate against the existing S12 resource-economics shape:

- counted mechanism growth requires a certified envelope delta ref,
- `held_out_status` must remain `pending_s14`,
- `held_out_battery_ref` must stay empty before S14 runs,
- `may_not_use_for` must include S12's forbidden uses, including
  `s14_universality`,
- one-off growth refs lower/block mechanism generality instead of disappearing
  into reuse labels,
- every PUBLIC or audit projection payload written by G7 must pass
  `verify_s12_resource_projection_consumer_contract(...)`.

Reuse refs should come from route/adapter/producer artifacts, not text labels:

- G1 adapter/source contract refs.
- G4 promotion gate refs.
- G5 conversion route refs.
- G6 demand/orchestration refs, diagnostic only.
- S14 mechanism-generality refs.

Cost fields:

- `baseline_seed_effort_units`
- `added_case_effort_units`
- `mean_added_case_effort_units`
- `marginal_cost_ratio_to_seed`
- `cumulative_grounding_cost_curve`
- `grounded_region_case_count`
- `bespoke_patch_count`
- `semantic_loss_blocker_count`
- `sublinear_marginal_cost_status`

`sublinear_marginal_cost_status = "pass"` requires:

- at least two grounded region cases,
- at least one added case beyond the seed class,
- the seed case itself is grounded or grounded-abstained, not `unchanged_blocker`,
- no bespoke patch refs,
- no semantic-loss blockers,
- `marginal_cost_ratio_to_seed < 1.0`,
- mechanism reuse rate above the local threshold, initially `0.5`.
- a non-empty S12 growth thermometer projection with no one-off growth refs.

With the current repo, status must be `blocked_insufficient_grounded_cases`.

- [x] **Step 2: Add bespoke-disguise negatives**

```python
def test_g7_bespoke_patch_blocks_reuse_and_sublinear_cost() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    ledger = g7.build_g7_mechanism_reuse_ledger(
        conversion_records=g7.synthetic_future_grounded_region_records(),
        bespoke_patch_refs=("one-off://ua-msme/custom-energy-template",),
    )
    cost = g7.build_g7_marginal_grounding_cost_ledger(
        conversion_records=g7.synthetic_future_grounded_region_records(),
        mechanism_reuse_ledger=ledger,
    )

    assert ledger.reuse_status == "blocked_by_bespoke_patch"
    assert cost.sublinear_marginal_cost_status != "pass"
    assert "layer3_g7_bespoke_patch_counted_as_reuse" in cost.issue_codes
```

Add a missing-growth-thermometer negative:

```python
def test_g7_sublinear_cost_requires_s12_growth_thermometer() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    records = g7.synthetic_future_grounded_region_records()
    reuse = g7.build_g7_mechanism_reuse_ledger(conversion_records=records)
    cost = g7.build_g7_marginal_grounding_cost_ledger(
        conversion_records=records,
        mechanism_reuse_ledger=reuse,
        s12_growth_thermometer_projection=None,
    )

    assert cost.sublinear_marginal_cost_status != "pass"
    assert "layer3_g7_s12_growth_thermometer_missing" in cost.issue_codes
```

Add S12-shape negatives:

```python
def test_g7_s12_projection_requires_certified_delta_for_counted_growth() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    projection = g7.build_g7_s12_growth_thermometer_projection(
        conversion_records=g7.synthetic_future_grounded_region_records(),
        growth_without_envelope_delta_count=1,
        growth_counting_disposition="counted_mechanism_growth",
    )

    assert projection.status != "pass"
    assert "layer3_g7_s12_growth_without_certified_delta" in projection.issue_codes


def test_g7_s12_projection_preserves_pending_s14_and_deny_list() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    projection = g7.build_g7_s12_growth_thermometer_projection(
        conversion_records=g7.synthetic_future_grounded_region_records(),
        held_out_status="executed",
        may_not_use_for=("production_authority",),
    )

    assert projection.status != "pass"
    assert "layer3_g7_s12_held_out_status_overclaimed" in projection.issue_codes
    assert "layer3_g7_s12_deny_list_omitted" in projection.issue_codes
```

- [x] **Step 3: Add positive future-cost test**

The positive fixture must use reused mechanism refs and no one-off refs:

```python
def test_g7_future_region_cost_passes_when_reuse_is_real() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    records = g7.synthetic_future_grounded_region_records()
    growth = g7.build_g7_s12_growth_thermometer_projection(
        conversion_records=records,
        demand_pull_refs=("s12-growth://ua-msme-adjacent/future",),
        accountable_principal_refs=("principal://ua-msme/region-owner",),
    )
    reuse = g7.build_g7_mechanism_reuse_ledger(
        conversion_records=records,
        s12_growth_thermometer_projection=growth,
    )
    cost = g7.build_g7_marginal_grounding_cost_ledger(
        conversion_records=records,
        mechanism_reuse_ledger=reuse,
        s12_growth_thermometer_projection=growth,
    )

    assert reuse.mechanism_reuse_rate >= 0.5
    assert cost.marginal_cost_ratio_to_seed < 1.0
    assert cost.sublinear_marginal_cost_status == "pass"
```

## Task 6: Region Envelope Expansion And Semantic Loss

**Files:**

- Modify: `src/polisyos/runtime/quality/proving_ground/region_widening.py`
- Modify: `tests/unit/runtime/quality/test_layer3_g7_region_widening.py`

- [x] **Step 1: Add region health DTOs**

Implement:

- `Layer3G7StatusCompositionLedger`
- `Layer3G7RegionEnvelopeExpansionDelta`
- `Layer3G7RegionSemanticLossRow`
- `Layer3G7RegionSemanticLossLedger`
- `Layer3G7HealthMetricDelta`

The health metric delta must include:

```text
envelope-expansion-rate(region)
adapter-semantic-loss(region)
governance-throughput(region)
search-recall@known-seeds+index-staleness(region)
demand-pull-vs-abstention(region)
```

It should not optimize useful-design rate. It should show whether external
demand plus reuse actually expands grounded envelope coverage.

Positive `envelope-expansion-rate(region)` numerator rows must carry an
S13-compatible certified envelope delta:

- `certified_envelope_delta_ref` present,
- `envelope_revision_direction = "expand"`,
- `materialized_from_s12_growth_entry_ref` present when the delta comes from S12,
- `assurance_case_delta_ref` present for non-hold revision evidence,
- pending, hold, shrink, and split revisions are recorded as limitations or
  blockers, never as positive expansion.

- [x] **Step 2: Add semantic-loss blockers**

Semantic loss blocks region pass when:

- source truth is lost or lineage collapses silently,
- authority boundary is weaker than the upstream weakest link,
- time roles are merged,
- legal/mandate status is dropped,
- G6 candidate text becomes evidence,
- case-specific caveats disappear from the region score.
- S12/S13 certified envelope delta refs disappear while the region score still
  claims expansion.

Status composition blocks region pass when:

- engineering readiness is pass but region value closure is blocked,
- S14 feed is blocked while the region scorecard claims coverage,
- marginal-cost status is pass while semantic loss is blocked,
- public projection claims a stronger status than the weakest per-case record,
- governance-throughput is missing for a region that claims governed promotion.
- a pending or non-expand envelope delta is counted as positive region expansion.

- [x] **Step 3: Add tests**

Add tests for:

- Current expansion rate stays `0.0` and status is blocked/flat.
- Future grounded fixture yields positive region expansion.
- Future positive expansion fixture fails without S13 certified `expand` delta.
- Pending, hold, shrink, or split deltas do not increase the expansion numerator.
- Semantic loss prevents marginal-cost `pass` even if raw cost ratio looks
  sublinear.
- Status composition downgrades any region scorecard that conflicts with S14,
  marginal-cost, semantic-loss, or governed-promotion status.

Example:

```python
def test_g7_region_expansion_requires_s13_certified_expand_delta() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    delta = g7.build_g7_region_envelope_expansion_delta(
        conversion_records=g7.synthetic_future_grounded_region_records(),
        certified_envelope_delta_refs=(),
    )

    assert delta.expansion_status != "pass"
    assert "layer3_g7_s13_certified_delta_missing" in delta.issue_codes


def test_g7_pending_delta_is_not_counted_as_region_expansion() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    delta = g7.build_g7_region_envelope_expansion_delta(
        conversion_records=g7.synthetic_future_grounded_region_records(),
        envelope_revision_direction="pending",
    )

    assert delta.expanded_case_count == 0
    assert "layer3_g7_pending_delta_counted_as_expansion" in delta.issue_codes
```

## Task 7: S14 Grounded Breadth Feed And Consumer Gate

**Files:**

- Modify: `src/polisyos/runtime/quality/proving_ground/region_widening.py`
- Modify: `tests/unit/runtime/quality/test_layer3_g7_region_widening.py`
- Modify: `tools/quality/validation/run_layer2_s14_universality_battery.py` -
  add the read-only G7 input-manifest hook.
- Modify: `tests/repo_quality/tools/test_layer2_s14_universality_battery.py` -
  prove the hook preserves sealed-battery freeze hash and access semantics.

- [x] **Step 1: Add S14 feed DTOs**

Implement:

- `Layer3G7S14GroundedBreadthFeed`
- `Layer3G7S14MechanismGeneralityProjection`
- `Layer3G7S14BatteryInputManifest`
- `Layer3G7S14ConsumerGate`

The feed must include:

- grounded region case refs,
- grounded authority coverage refs,
- A-firewall refs,
- claim/evidence binding refs,
- mandate/legal refs where applicable,
- capacity/regime/coupling refs or explicit missing-ref limitation codes,
- mechanism generality report refs,
- envelope revision/delta refs,
- limitations,
- denied uses.

The battery input manifest must include:

- `s14_battery_input_manifest_id`
- `grounded_breadth_feed_ref`
- `mechanism_generality_projection_ref`
- `grounded_authority_coverage_ref`
- `envelope_revision_dynamics_ref`
- `certified_envelope_delta_refs`
- `visible_limitation_refs`
- `sealed_battery_mutation_status = "not_mutated"`
- `hidden_case_access_status = "not_accessed_by_g7"`
- `may_not_use_for`

- [x] **Step 2: Reuse S14 helpers**

Use existing S14 helpers from `layer2_universality_assurance.py`:

- `build_grounded_authority_coverage_record(...)`
- `build_envelope_revision_dynamics_record(...)`
- `build_s14_mechanism_generality_from_growth_thermometer(...)`
- `build_mechanism_generality_report(...)`
- `gate_universality_claim(...)`
- `verify_universality_claim_authority(...)`

G7 should not run or mutate the sealed S14 battery. It should produce a
consumer-ready grounded-breadth feed for S14, and S14 remains the gate for
universal wording.

The G7 S14 projection must satisfy the same shape expected by S14 public
projection verification:

- no aggregate universal score,
- non-empty `universality_claim_gate_ref` only when S14 owns the gate,
- non-empty `s9_projection_faithfulness_refs` if public universality wording is
  surfaced,
- required S14 refs such as grounded-authority coverage, status-composition,
  axis scorecard, sealed-battery run, mechanism-generality, and breadth floor
  refs are either present or explicitly limited,
- hidden/gold/sealed case payload keys are absent from public projections,
- `authority_boundary.authoritative_for` cannot cross into production,
  recommendation, approval, runtime closeout, scorecard, or publication uses.

Keep the `run_layer2_s14_universality_battery.py` change narrow: the runner may
read the G7 input manifest as an external grounded-breadth ref, but it must not
change configured partition path, owner, access mode, hidden case content,
freeze-hash computation, or `allow_sealed_battery` semantics. Add a test
asserting the freeze hash is unchanged with and without the G7 manifest.
The runner payload should expose the hook as a small diagnostic object such as
`external_grounded_breadth_input` with `status`, `manifest_ref`, and
`issue_codes`; it must not merge G7 rows into sealed case rows or S14 fixture
grounded-authority refs.

- [x] **Step 3: Add S14 negatives**

Tests must prove:

- Fixture-only breadth is blocked.
- Current G5 unchanged blocker is blocked.
- G6 candidate refs are blocked.
- Missing S14 battery input manifest is blocked or labeled `consumer_missing`.
- S14 readiness manifest refs are not treated as full runner output or as
  region grounded-breadth payloads.
- Bare universal claim without S14 gate is blocked.
- Bespoke cost hidden as generality is blocked.
- Untested axis expansion remains out-of-envelope.
- Aggregate universal score is blocked.
- Hidden/gold/sealed S14 payload material is redacted or blocked in public
  projection tests.

Example:

```python
def test_g7_s14_feed_blocks_fixture_breadth() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    feed = g7.build_g7_s14_grounded_breadth_feed(
        region_ref="region://ua/msme-adjacent",
        conversion_records=[],
        fixture_grounded_refs=("fixture://s14/dev-grounded-authority",),
    )

    assert feed.status == "blocked_no_real_grounded_breadth"
    assert "layer3_g7_s14_feed_uses_fixtures" in feed.issue_codes
```

## Task 8: Region Scorecard, Audit Surface, And Replay

**Files:**

- Modify: `src/polisyos/runtime/quality/proving_ground/region_widening.py`
- Modify: `tests/unit/runtime/quality/test_layer3_g7_region_widening.py`

- [x] **Step 1: Add surface DTOs**

Implement:

- `Layer3G7RegionScorecard`
- `Layer3G7RegionWideningAuditSurface`
- `Layer3G7PublicExportProjectionRefs`
- `Layer3G7OrchestrationContinuity`
- `Layer3G7ReplayManifest`

PUBLIC surface must include:

- region ref,
- region envelope posture,
- grounded/blocked/pending case counts,
- current `g7_region_value_closure_status`,
- mechanism reuse status,
- marginal cost status,
- S14 feed status,
- visible limitations,
- denied uses,
- `authority_role = "projection_only"`,
- official use limited to public audit/operator triage/external explanation,
- S12/S13/S14 projection-contract verification status for every projection payload
  G7 writes; if a payload is not written, expose `not_applicable_no_payload`
  instead of omitting the status,
- safe artifact refs only.

PUBLIC surface must not include:

- raw prompts,
- hidden S14 case ids/content,
- raw evidence payloads,
- recommendation text,
- legal advice,
- universal claim allowed language.
- authority-shaped fields such as approval, scorecard, runtime closeout, legal,
  rollout, or production recommendation slots.

- [x] **Step 2: Add replay continuity**

Replay manifest must include:

- region candidate set fingerprint,
- grounding matrix fingerprint,
- conversion status matrix fingerprint,
- governed promotion join fingerprint,
- status-composition ledger fingerprint,
- S12 growth thermometer projection fingerprint,
- mechanism reuse and marginal-cost ledger fingerprints,
- S14 feed, battery-input manifest, and consumer gate fingerprints,
- scorecard/public projection fingerprints,
- rule/schema versions,
- dependency artifact refs,
- upstream closed G5/G6 replay fingerprints,
- generated artifact paths.

Reuse the shared `build_replay_manifest(...)` and
`build_nl_replay_orchestration_continuity(...)` helpers, following the G6 wrapper
pattern. Continuity drift is a blocker for G7 readiness, not a warning.

- [x] **Step 3: Add public projection negatives**

Tests must fail closed when:

- PUBLIC projection contains raw case payloads or hidden S14 refs.
- PUBLIC projection declares universal authority.
- Projection omits the G7 deny-list.
- Projection omits required S12/S13/S14 deny-list entries inherited from
  consumer-contract verification.
- Public export has `authority_role` other than `projection_only` or lacks
  official-use limits forbidding approval, scorecard, and runtime closeout use.
- Public projection contract status is absent or `fail` while readiness claims
  pass.
- A region score is presented as aggregate universal score.
- Replay wrappers bypass the shared replay/orchestration-continuity helpers.
- Replay continuity mutates or replaces a G5/G6 closed payload instead of
  pointing to it by ref/fingerprint.

## Task 9: Readiness CLI, Artifact Writer, And Registrations

**Files:**

- Modify: `tools/quality/validation/check_policy_design_case_layer3_g7_readiness.py`
- Modify: `tests/repo_quality/tools/test_policy_design_case_layer3_g7_readiness.py`
- Modify: `tests/repo_quality/tools/test_policy_design_case_layer3_g7_readiness_cli.py`
- Modify: `architecture/generated_artifacts.toml`
- Modify: `architecture/policy_design_case/inventory.json`
- Modify: `docs/reference/generated-artifacts.md`
- Modify: `docs/reference/public-surface.md`
- Modify: `docs/reference/documentation-inventory.md`
- Modify: `docs/reference/index.md`
- Modify: `src/polisyos/runtime/quality/README.md`

- [x] **Step 1: Add readiness CLI**

Mirror G6:

```bash
uv run python tools/quality/validation/check_policy_design_case_layer3_g7_readiness.py --repo-root . --output-format json
uv run python tools/quality/validation/check_policy_design_case_layer3_g7_readiness.py --repo-root . --write --output-format json
```

The report must expose these summary keys:

```text
g7_engineering_readiness_status
g7_region_value_closure_status
g7_region_candidate_set_status
g7_region_grounding_matrix_status
g7_region_grounded_case_count
g7_region_blocked_case_count
g7_status_composition_status
g7_governed_promotion_join_status
g7_g4_region_promotion_projection_status
g7_current_g5_conversion_outcome
g7_g1_search_control_plane_status
g7_s12_growth_thermometer_status
g7_mechanism_reuse_status
g7_mechanism_reuse_rate
g7_marginal_cost_status
g7_region_envelope_expansion_rate
g7_region_semantic_loss_status
g7_governance_throughput_status
g7_s14_grounded_breadth_feed_status
g7_s14_battery_input_manifest_status
g7_s14_consumer_gate_status
g7_s14_runner_input_hook_status
g7_public_projection_contract_status
g7_replay_manifest_status
g7_orchestration_continuity_status
g7_conformance_status
```

With current artifacts:

```text
g7_engineering_readiness_status = pass
g7_region_value_closure_status = blocked_by_current_g5_unchanged_blocker
g7_region_grounded_case_count = 0
g7_marginal_cost_status = blocked_insufficient_grounded_cases
g7_s14_grounded_breadth_feed_status = blocked_no_real_grounded_breadth
g7_s14_battery_input_manifest_status = blocked_no_real_grounded_breadth
```

The readiness writer must also expose an exact
`EXPECTED_MANIFEST_DRIFT_KEYS`-style list and tests must assert the exact set:

```text
g7_engineering_readiness_status
g7_region_value_closure_status
g7_current_g5_conversion_outcome
g7_current_g5_unchanged_blocker_status
g7_g1_search_control_plane_status
g7_g1_free_growth_status
g7_g1_no_hardcode_lint_status
g7_g4_promotion_gate_shape_status
g7_g4_region_promotion_projection_status
g7_g5_g6_authority_boundary_status
g7_region_candidate_set_status
g7_region_grounding_matrix_status
g7_region_grounded_case_count
g7_region_blocked_case_count
g7_status_composition_status
g7_governed_promotion_join_status
g7_s12_growth_thermometer_status
g7_s12_resource_projection_contract_status
g7_s13_certified_delta_status
g7_mechanism_reuse_status
g7_mechanism_reuse_rate
g7_marginal_cost_status
g7_region_envelope_expansion_rate
g7_region_semantic_loss_status
g7_governance_throughput_status
g7_s14_grounded_breadth_feed_status
g7_s14_mechanism_generality_status
g7_s14_battery_input_manifest_status
g7_s14_consumer_gate_status
g7_s14_runner_input_hook_status
g7_s14_projection_contract_status
g7_public_projection_contract_status
g7_public_projection_official_use_status
g7_replay_manifest_status
g7_orchestration_continuity_status
g7_generated_artifacts_registration_status
g7_inventory_surface_status
g7_reference_docs_status
g7_route_contract_registry_status
g7_registry_ratchet_status
g7_conformance_status
```

- [x] **Step 2: Add exact write-artifact tests**

The `--write` command must emit exactly the expected G7 artifact set and fail if
any path is missing or extra.

Repo-quality tests should mirror the concrete G5/G6 test style:

- exact `EXPECTED_ARTIFACT_PATHS`,
- exact `EXPECTED_MANIFEST_DRIFT_KEYS`,
- exact issue-code dictionary keys,
- `--write` omitted-path failure,
- stale persisted artifact failure,
- route contract registry is a generated route contract registry, not an adapter
  registry,
- runtime bundle writes TOML for health delta and route contract registry only
  where expected.

- [x] **Step 3: Register surfaces and docs**

Follow the G6 pattern:

- generated artifact family in `architecture/generated_artifacts.toml`,
- PDC inventory surface and projection refs,
- generated artifacts reference row and detail section,
- public surface reference,
- documentation inventory and index entries,
- runtime-quality README note.

Registration checks must fail closed if:

- `architecture/generated_artifacts.toml` lacks
  `policy-design-case-layer3-g7-region-widening-artifacts`,
- family metadata lacks `source_of_truth`, regenerate command, check command,
  `stale_output_behavior = "fail"`, or `drift_gate = "automated"`,
- any expected G7 path is missing from the generated family,
- `architecture/policy_design_case/inventory.json` lacks
  `layer3_g7_region_widening_surface`, producer, validator,
  runtime validator, readiness manifest, artifact paths, or upstream source
  surfaces,
- `docs/reference/generated-artifacts.md` omits the G7 readiness manifest,
- `docs/reference/public-surface.md` omits the G7 surface or overstates public
  authority,
- `docs/reference/documentation-inventory.md`, `docs/reference/index.md`, or
  `src/polisyos/runtime/quality/README.md` omit the G7 reference entry.

- [x] **Step 4: Add runtime-surface readiness checks**

The readiness CLI should validate runtime surfaces, not only file existence:

- current G5 unchanged blocker is represented as region-value blocker,
- G1 search ledgers remain `authoritative_for = []` and deny
  `search_hit_as_authority`,
- G1 free-growth and no-hardcode statuses pass for G7 candidate input,
- G4 governed-promotion join validates full gate shape,
- S12 projection preserves `pending_s14`, certified delta, and deny-list
  semantics,
- S13 expansion status requires certified `expand` delta,
- public projection has no raw/hidden payload and passes projection-only
  official-use checks,
- S12/S13/S14 projection-contract statuses are pass for every projection payload
  written by G7,
- S14 runner hook status is either implemented and non-mutating or explicitly
  labeled `consumer_missing`/`implemented_but_not_orchestrated`,
- replay and orchestration continuity use shared helpers and have no unexplained
  drift,
- conformance report includes every required negative and all observed issue codes.

## Task 10: Conformance Negatives And Final Verification

**Files:**

- Modify: `src/polisyos/runtime/quality/proving_ground/region_widening.py`
- Modify: `tests/unit/runtime/quality/test_layer3_g7_region_widening.py`
- Modify: `tests/repo_quality/tools/test_policy_design_case_layer3_g7_readiness.py`

- [x] **Step 1: Implement G7 conformance report**

Required negative ids:

```text
g5_unchanged_blocker_as_region_grounded
g6_candidate_as_region_grounded
fixture_breadth_as_grounded
hardcoded_candidate_set_as_region_coverage
search_hit_as_region_coverage
grounded_case_without_governed_promotion
g4_seed_promotion_as_region_governance
g4_promotion_without_full_gate_shape
g4_mapping_fallback_as_region_governance
bespoke_patch_as_mechanism_reuse
sublinear_cost_without_cost_ledger
sublinear_cost_without_grounded_cases
s12_growth_thermometer_missing
s12_projection_bypasses_resource_economics_shape
s12_growth_without_certified_delta
s12_held_out_status_overclaimed
s12_deny_list_omitted
s13_certified_delta_missing
pending_delta_as_region_expansion
semantic_loss_hidden_by_region_score
effective_independence_inflated
g5_may_not_use_for_ignored
g6_may_not_use_for_ignored
s14_feed_missing
s14_battery_input_manifest_missing
s14_feed_uses_fixtures
s14_manifest_as_runner_output
universal_claim_without_s14_gate
public_projection_authority_leak
public_projection_raw_payload_leak
public_projection_required_deny_list_missing
public_projection_contract_missing_or_failed
generated_artifacts_family_missing
inventory_surface_missing
reference_index_missing
route_contract_registry_missing
manifest_runtime_drift
replay_manifest_missing
orchestration_continuity_missing
replay_helper_bypassed
closed_case_replay_mutated
```

Every negative must have expected issue codes and observed issue codes.
Readiness fails if any negative is missing or failing.

- [x] **Step 2: Run focused tests**

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer3_g7_region_widening.py -q
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer3_g7_readiness.py tests/repo_quality/tools/test_policy_design_case_layer3_g7_readiness_cli.py -q
```

- [x] **Step 3: Generate artifacts and run readiness**

```bash
cd policy-engine
uv run python tools/quality/validation/check_policy_design_case_layer3_g7_readiness.py --repo-root . --write --output-format json
uv run python tools/quality/validation/check_policy_design_case_layer3_g7_readiness.py --repo-root . --output-format json
```

- [x] **Step 4: Run guardrails**

```bash
cd policy-engine
uv run polisyos-tools architecture guardrails check
python3 -m tools.cli workspace verify --backend-only
```

If backend verify is too broad for the slice, at minimum run:

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer3_g7_region_widening.py tests/repo_quality/tools/test_policy_design_case_layer3_g7_readiness.py tests/repo_quality/tools/test_policy_design_case_layer3_g7_readiness_cli.py -q
uv run python tools/quality/validation/check_policy_design_case_layer3_g7_readiness.py --repo-root . --output-format json
```

## Acceptance Criteria

G7 is ready to merge when:

- The G7 runtime module and readiness CLI exist with strict DTOs and no broad
  package exports.
- The readiness CLI writes exactly the expected artifact set.
- Current repo state reports G7 engineering readiness honestly while keeping
  region value closure blocked by current G5/G6 grounded-value reality.
- Future grounded-region fixtures prove sublinear-cost and S14-feed positive
  paths without changing code branches.
- Current G5 unchanged blocker is never counted as grounded breadth.
- Grounded region cases require governed G4 promotion or grounded-abstention
  represented by `Layer3G4PromotionRecord` with full G4 gate-shape refs.
- G7 status composition downgrades pass claims when per-case, S14, semantic-loss,
  marginal-cost, projection, or replay state is weaker.
- G6 agent candidates and search hits are never counted as region grounded
  breadth.
- Bespoke per-case patches block mechanism reuse and marginal cost pass.
- S12-style growth/reuse projection is present before sublinear marginal cost can
  pass.
- S14 feed and S14 battery input manifest use only real grounded refs and block
  fixture/universal laundering without mutating sealed battery fixtures.
- PUBLIC/REVIEWER/EXPERT/MACHINE surfaces expose the region scorecard with safe
  refs and full deny-list.
- Replay and orchestration continuity are persisted and drift-checked, including
  proof that G5/G6 closed payloads were not mutated for G7.
- Region health delta exposes envelope-expansion, semantic-loss,
  governance-throughput, demand-pull-vs-abstention, and search recall/freshness.
- Generated artifacts, PDC inventory, public-surface docs, reference docs, and
  runtime README are registered.
- Focused unit/repo-quality tests, readiness CLI, and architecture guardrails
  pass.

## Implementation Notes

- Keep G7 as a cohort adapter and measurement layer. It is tempting to generalize
  G5 in this slice, but that risks changing the meaning of the already closed G5
  artifacts. If reusable G5 conversion is necessary, split it into a small,
  replay-preserving subtask with red tests that prove old pinned behavior is
  unchanged.
- Do not use S14 sealed-battery fixture refs as G7 grounded breadth. The G7 S14
  feed should be empty/blocked on the current repo and positive only in future
  grounded-region tests.
- Do not treat the readiness candidate list as regional coverage. The list is a
  deterministic control-plane seed; search/discovery and conversion refs decide
  coverage.
- Name the blocker precisely in the readiness manifest. A pass with
  `blocked_by_current_g5_unchanged_blocker` is honest engineering readiness; a
  pass that implies real grounded region value is not.
