---
plan_id: layer3-g5-first-proving-ground-conversion
title: "G5 - First Proving-Ground Conversion"
type: slice-plan
status: completed
created: 2026-06-08
revised: 2026-06-10
completed: 2026-06-10
last_verified: 2026-06-10
stability: closed
slice: G5
depends_on:
  - docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md
  - docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
  - docs/plans/active/layer3-slices/G0-capability-data-inventory-triage-discipline-freeze.md
  - docs/plans/active/layer3-slices/G1-data-grounding-existing-assets-acquisition.md
  - docs/plans/active/layer3-slices/G2-causal-forecast-search-engine.md
  - docs/plans/active/layer3-slices/G3-analytics-search-engine.md
  - docs/plans/active/layer3-slices/GL-legal-mandate-search-engine.md
  - docs/plans/active/layer3-slices/G4-shadow-to-governed-promotion-gate.md
  - docs/adr/0175-layer3-grounding-subordination-discipline.md
  - architecture/policy_design_case/layer3_g0_readiness_manifest.json
  - architecture/policy_design_case/layer3_g1_readiness_manifest.json
  - architecture/policy_design_case/layer3_g1_grounded_source_contracts.json
  - architecture/policy_design_case/layer3_g2_readiness_manifest.json
  - architecture/policy_design_case/layer3_g2_grounded_forecast_handoffs.json
  - architecture/policy_design_case/layer3_g3_readiness_manifest.json
  - architecture/policy_design_case/layer3_g3_proof_carrying_analytics_records.json
  - architecture/policy_design_case/layer3_gl_readiness_manifest.json
  - architecture/policy_design_case/layer3_gl_legal_authority_report.json
  - architecture/policy_design_case/layer3_g4_readiness_manifest.json
  - architecture/policy_design_case/layer3_g4_dependency_readiness_snapshot.json
  - architecture/policy_design_case/layer3_g4_grounded_contract_set.json
  - architecture/policy_design_case/layer3_g4_a_completeness_ledger.json
  - architecture/policy_design_case/layer3_g4_human_decision_integrity_gate.json
  - architecture/policy_design_case/layer3_g4_weakest_boundary_composition.json
  - architecture/policy_design_case/layer3_g4_promotion_records.json
  - architecture/policy_design_case/layer3_g4_closeout_consumer_gate.json
  - architecture/policy_design_case/layer3_g4_pdc_compiler_consumer_gate.json
  - architecture/policy_design_case/layer3_g4_g5_promotion_handoff.json
  - architecture/policy_design_case/layer3_g4_public_export_projection_refs.json
  - architecture/policy_design_case/layer3_g4_conformance_report.json
  - architecture/policy_design_case/wave12d_universal_outcome_corpus_run_manifest.json
  - architecture/generated_artifacts.toml
  - architecture/policy_design_case/inventory.json
  - tools/quality/validation/run_universal_outcome_corpus.py
  - tools/quality/validation/check_policy_design_case_layer3_g4_readiness.py
  - src/polisyos/runtime/quality/proving_ground/pre_adapter_grounding_inventory.py
  - src/polisyos/runtime/quality/proving_ground/substrate_grounding_search.py
  - src/polisyos/runtime/quality/proving_ground/causal_forecast_search.py
  - src/polisyos/runtime/quality/proving_ground/proof_carrying_analytics_search.py
  - src/polisyos/runtime/quality/proving_ground/legal_mandate_search.py
  - src/polisyos/runtime/quality/proving_ground/governed_promotion_gate.py
  - src/polisyos/runtime/quality/evidence_independence.py
  - src/polisyos/corpus/_impl/expert_adjudication.py
context_inputs:
  - tests/fixtures/universal-corpus
  - tests/fixtures/layer2/s12/s12_resource_economics_case_signals.json
  - tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py
  - tests/unit/runtime/quality/test_layer3_g4_promotion_gate.py
  - tests/repo_quality/tools/test_policy_design_case_layer3_g4_readiness.py
  - tests/unit/runtime/quality/test_evidence_independence_map.py
  - tests/unit/corpus/test_expert_adjudication.py
  - src/polisyos/pdc/_impl/layer2_design_search.py
  - src/polisyos/pdc/_impl/layer2_readiness.py
  - src/polisyos/runtime/quality/closeout_reader.py
  - src/polisyos/runtime/quality/public_export.py
  - src/polisyos/runtime/quality/case_lifecycle.py
cells_closed:
  - layer3.g5_first_proving_ground_conversion
  - layer3.g5_dependency_artifact_resolution
  - layer3.g5_pinned_case_input_bundle
  - layer3.g5_conversion_eligibility_ledger
  - layer3.g5_status_composition
  - layer3.g5_w12d_conversion_gate
  - layer3.g5_envelope_expansion_delta
  - layer3.g5_conversion_record
  - layer3.g5_public_reviewer_expert_machine_surface
layer_cells_advanced:
  - layer3.g5_first_proving_ground_conversion
  - layer3.g5_dependency_artifact_resolution
  - layer3.g5_pinned_case_input_bundle
  - layer3.g5_conversion_eligibility_ledger
  - layer3.g5_status_composition
  - layer3.g5_w12d_conversion_gate
  - layer3.g5_envelope_expansion_delta
  - layer3.g5_conversion_record
  - layer3.g5_public_reviewer_expert_machine_surface
expected_open_cell_count: 0
floor_id: layer3_grounding_subordination
metric: layer3_g5_first_proving_ground_conversion
source_roadmap: docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md
constitution: docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
---

# G5 - First Proving-Ground Conversion

## For agentic workers

This is an executable slice spec, not a strategy note. Follow it red-first.
G5 is the first place where Layer 3 is allowed to change the proving-ground
conversion classification.

G5 consumes the full W12.D composed loop, the G1/G2/G3/GL grounded artifacts, and
the G4 promotion handoff. It emits a replayable `Layer3G5ConversionRecord` for
the pinned proving-ground case, plus W12.D conversion output, envelope-expansion
health, and all-audience surfaces.

G5 is not a new grounding/search engine, not a generator, not G6 agent
orchestration, not G7 widening, not production approval, and not a general
useful-design optimizer. A G4 `governed_promoted` record is necessary for a
conversion, but not sufficient. The conversion must be grounded for the declared
scope, and a source-only promotion cannot become a causal/effect/legal design by
being routed through G5. For G5, `grounded_limited` is a design-level conversion:
it requires the composed S4-S14 loop plus G2/G3 design evidence, not only source
truth promotion. Source-only promotion can support abstention, limitations, or a
source-grounded non-useful slice, but it cannot mint useful-design credit.

Frontmatter note: `layer_cells_advanced` entries are Layer 3 plan-local progress
labels, not governed `cluster_ownership_map.toml` cells.

## Intro

The master-plan milestone is:

```text
W12.D pinned case typed_blocker
-> full composed loop S4-S14
-> grounded contract refs from G1 and any required G2/G3/GL families
-> G4 PromotionRecord(governed_promoted) for the declared conversion scope
-> G5 conversion eligibility and status composition
-> typed_blocker -> grounded_limited
   or typed_blocker -> grounded_abstention
   or unchanged_blocker
-> W12.D emits conversion classification
-> envelope-expansion-rate recorded
-> public/reviewer/expert/machine surfaces
```

This is the first real Layer 3 value checkpoint. The target is not to maximize
the metric by relaxing definitions. It is to prove that a real typed blocker can
move through the waist into either a limited grounded design or an honest,
grounded abstention.

The current post-G4 state matters:

- G4 has a `g5_promotion_handoff` and two promotion records for
  `ua-msme-affordable-loans-2022`: one `governed_promoted` source-data scope and
  one blocked causal-forecast probe.
- W12.D already injects G0/G1/G2/G3 gates and intentionally keeps useful-design
  and conversion outcomes unchanged before G5.
- W12.D's canonical closeout `OUTCOMES` are still `pass`,
  `publish-with-limitation`, `accepted_deficit`, and `typed_blocker`.
  `grounded_limited` and `grounded_abstention` are Layer 3 conversion
  classifications, not a silent replacement status lattice.

Therefore G5 must add a conversion layer that composes with W12.D outcomes
explicitly. If the pinned case reaches `typed_blocker -> grounded_limited`, it
may map to bounded W12.D useful-design credit only through declared envelope and
closeout composition rules. If it reaches `typed_blocker -> grounded_abstention`,
it records a real conversion but does not count as useful design.

## Closure Contract

Source of truth: roadmap G5 closure contract in
`docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md`,
especially "G5 - First Proving-Ground Conversion (the milestone)".

G5 must deliver:

1. **Dependency readiness snapshot** proving G0, G1, G4, search recall/freshness,
   and engineering quality are ready. For `typed_blocker -> grounded_limited`,
   G2 and G3 are hard dependencies because a grounded design needs calibrated
   forecast/effect support and proof-carrying analytics. GL is a hard dependency
   whenever legal/mandate authority is inside the declared conversion scope. For
   `typed_blocker -> grounded_abstention`, G1 and G4 are sufficient only if the
   abstention quality checks prove the non-conversion reason is not search,
   freshness, manifest-only, or demand-inertia failure. The resolver must read
   slice-specific readiness keys, not just `manifest["status"]`: G2/G3/GL
   manifests do not all use the same top-level shape, and GL can report `pass`
   while still carrying `reissue_required` or reference-resolution limits.
2. **Pinned case input bundle** resolving a fresh full W12.D payload for
   `ua-msme-affordable-loans-2022`, including S2 design search, per-case
   S4-S14 composed blocks, G0/G1/G2/G3 gates, typed blockers, authority
   outcomes, and replay refs. The current per-case block keys are
   `s4_epistemic_regime`, `s5_coupling_composition`,
   `s6_blind_spot_firewalls`, `s7_delegation`, `s8_value_choice`,
   `s9_projection_lowering`, `s10_outcome_prediction`,
   `s11_predictive_knowledge`, `s12_resource_economics`,
   `s13_post_deploy_accountability`, and `s14_universality_assurance`. The
   W12.D manifest alone is not evidence, and a local `_build/.tmp/.../w12d*.json`
   cache is not a source of truth.
3. **Composed-loop completeness gate** proving the pinned case actually ran the
   full S4-S14 loop and that S14 did not block the declared grounded claim. G5
   cannot convert from a partial S2/G1/G4 bundle that skipped regime, coupling,
   blind-spot, delegation, value, projection, forecast, predictive, resource,
   post-deploy, or universality assurance checks.
4. **G4 handoff resolver** that reads persisted
   `layer3_g4_g5_promotion_handoff.json` and
   `layer3_g4_promotion_records.json`, admits only `governed_promoted` records
   for G5 input, and carries `promotion_blocked` records as typed blockers or
   limitations. Resolution is per promotion record and must match
   `promotion_record_id`, scope, `source_design_record_ref`, digest, claim
   family, blocker refs, and limitation refs. The single persisted
   `layer3_g4_weakest_boundary_composition.json` is not enough to prove every
   relevant G4 record is promotable.
5. **Grounded result evidence set** linking every conversion claim to concrete
   grounded contract rows and promotion refs, with an upstream scope-join matrix
   proving G1/G2/G3/GL rows cover the same case, design record, claim family,
   envelope, and promotion scope. A readiness summary, search ledger, public
   projection, generated-artifact family, or source-only promotion cannot stand
   in for a required grounded row.
6. **Effective evidence independence record** for `grounded_limited`, proving the
   support is not the same source/lineage/prompt/method counted through multiple
   wrappers. If effective independence cannot be established, the result is
   limited further or remains `unchanged_blocker`.
7. **Conversion eligibility ledger** deciding exactly one of:
   `typed_blocker -> grounded_limited`,
   `typed_blocker -> grounded_abstention`, or `unchanged_blocker`. The decision
   must include issue codes, blocker refs, limitation refs, envelope refs,
   rule/schema versions, and the reason non-conversion is search ceiling, domain
   ceiling, missing conversion route/bridge, stale index, blocked promotion,
   upstream scope mismatch, legal reissue, or unresolved human accountability.
8. **Status composition ledger** proving the conversion classification composes
   with W12.D `outcome`, `conversion_outcome`, authority outcomes, closeout
   readers, public exports, and useful-design metrics. It must not introduce a
   parallel uncontrolled status lattice.
9. **Grounded abstention quality record** for any abstention. A G5 abstention is
   honest only when search recall/freshness is measured and the no-conversion
   reason is not a search miss, stale index, missing replay payload, or hidden
   refusal.
10. **Demand-pull attempt record** for T6, linking abstention or non-conversion
    to S12 VOI/explore-exploit refs, S12 `demand_act_refs` / `growth_entries`,
    S3 reuse/acquisition refs, or accountable principal refs. A cheap refusal
    without demanded grounding effort is not a grounded abstention.
11. **Envelope-expansion delta** recording the first
   `envelope-expansion-rate` reading. It must identify the region/envelope
   gained, conversion effort refs, numerator/denominator, and why the result is
   `expanding`, `flat`, or blocked.
12. **W12.D consumer gate** injected after G3 and before W12.D summary. The
   current W12.D builder computes `_summary(cases)` before corpus-level S4-S14
   summaries, so this hook must consume per-case S4-S14 blocks at that point, or
   deliberately reorder/recompute summary with tests. G3 summary is currently
   emitted as a top-level Layer 3 G3 analytics-search summary, not inside the
   W12.D `summary` object, so G5 must not assume all upstream summaries share one
   location. It emits per-case `layer3_g5_conversion_gate`, updates G5-specific
   summary keys, and updates top-level grounded conversion counts only when G5
   actually routed. It must not erase G0/G1/G2/G3 gate histories.
13. **Typed `Layer3G5ConversionRecord`** with conversion state, W12.D case ref,
    source DesignRecord refs, G4 promotion refs, upstream grounded evidence refs,
    envelope refs, limitations, blockers, authority boundary, and replay refs.
14. **PUBLIC/REVIEWER/EXPERT/MACHINE surface** exposing the grounded result,
    declared envelope, limitations, blockers, search-health status, conversion
    classification, and safe upstream evidence refs. Public projection must be
    reference-only unless a fully tested export hook is implemented.
15. **Registry/ratchet delta** moving the G5 conversion bridge from missing
    labels to implemented only after producer, persisted artifact, W12.D
    consumer, all-audience surface, readiness CLI, and negative semantic tests
    are all wired.
16. **Conformance negatives** proving bypasses fail closed: conversion without
    G4 governed promotion, `grounded_limited` without G2/G3, conversion from
    source-only promotion into causal design, conversion without S4-S14/S14
    completeness, readiness-summary-only conversion, W12.D manifest-only
    conversion, stale-search abstention, search-recall false abstention, domain
    ceiling without recall/freshness, abstention without demand-pull attempt, G4
    promotion-only useful-design credit, blocked promotion used as conversion,
    public raw-payload leak, closeout authority leak, production authority leak,
    non-pinned case widening, arbitrary request attempt, and useful-design-rate
    optimization by lowering floors.

G5 is done when
`tools/quality/validation/check_policy_design_case_layer3_g5_readiness.py` passes
over persisted artifacts and a W12.D report contains one pinned-case conversion
gate whose conversion classification is `typed_blocker -> grounded_limited` or
`typed_blocker -> grounded_abstention`, with replayable evidence, envelope
delta, and no authority leakage.

## Scope Boundaries

In scope:

- Add G5 runtime-quality contracts and builders for dependency readiness, pinned
  case input, G4 handoff resolution, grounded result evidence, conversion
  eligibility, grounded abstention quality, status composition, W12.D consumer
  gate, envelope-expansion delta, conversion records, audit/public surfaces,
  conformance report, registry/ratchet delta, and readiness manifest.
- Reuse G1 grounded source contracts, G2 causal/forecast handoffs, G3
  proof-carrying analytics records, GL legal/mandate authority records, G4
  promotion records, S2 DesignRecord/W12.D payloads, S7/P26 human-decision
  posture, S9 projection boundaries, S12 envelope-growth conventions, and
  generated-artifact registration.
- Treat S4-S14/S14 completeness as a conversion gate, not only context copied
  into the pinned case bundle.
- Convert exactly the pinned proving-ground case first:
  `ua-msme-affordable-loans-2022`.
- Emit W12.D conversion gate output after G3 and before summary.
- Record the first envelope-expansion-rate reading.
- Keep G5's engineering bar explicit: strict Pydantic DTOs, structured JSON/TOML
  parsing, bounded artifact refs, lazy imports in W12.D, deterministic replay,
  and fail-closed validation.

Out of scope:

- No new search engine or new data acquisition path.
- No G6 arbitrary-request agent orchestration.
- No G7 regional widening or second-case scaleout.
- No lowering of evidence floors, calibration floors, or closeout floors.
- No production approval, publication authority, rollout authority, legal
  advice, or public recommendation authority.
- No claim that a source-only G4 promotion proves causal/effect usefulness.
- No `grounded_limited` useful-design credit from a source-only conversion slice.
- No rewrite of Layer 2 waist contracts unless the master plan and constitution
  are amended first.
- No filesystem-wide scans in runtime request paths.

## Pattern Pass

Relevant failure patterns:

| Pattern | G5 risk | Closure move |
| --- | --- | --- |
| P01 contract-only capability | A conversion record exists but W12.D does not emit or consume it. | Full chain: pinned case -> producer -> persisted record -> W12.D gate -> surface -> negatives. |
| P02 thin orchestration | G1/G2/G3/GL/G4 are green independently but not composed into conversion. | Conversion eligibility must consume concrete upstream rows and G4 promotion refs. |
| P03 hidden internal richness | Conversion appears only in JSON, not audience surfaces. | PUBLIC/REVIEWER/EXPERT/MACHINE projection with safe refs and authority boundary. |
| P04 status lattice gap | `grounded_limited` / `grounded_abstention` become uncontrolled W12.D outcomes. | Status composition ledger maps Layer 3 conversion to existing W12.D outcome semantics. |
| P05 authority dilution | Conversion is mistaken for production, closeout, publication, or policy recommendation. | `authoritative_for` is G5 conversion classification only; `may_not_use_for` denies downstream authority. |
| P07/P08 replay/time gap | Conversion ignores rule versions, legal time, observation time, or stale index time. | Persist rule/schema/time refs and block stale/reissue-sensitive claims. |
| P09 implicit soft gates | G5 emits warning-like caveats that do not affect conversion, useful-design credit, or surfaces. | G5 has no local soft-warning lifecycle: unresolved caveats are blockers or limitations unless they cite an existing owned warning lifecycle. |
| P10 semantic adequacy gap | Tests prove fields exist but not that conversion is grounded. | Semantic negatives and pinned-case evidence assertions are mandatory. |
| P13 governance gravity | G5 becomes a super-scorecard for every slice. | Keep G5 thin: resolve, compose, classify, emit; no new search or generator. |
| P14 evidence inflation | Multiple refs to the same source look like independent support. | Evidence set carries effective independence/collapse refs when claiming `grounded_limited`. |
| P15 LLM/speculation laundering | Shadow design becomes converted because it is fluent. | B-side output stays candidate until A-side grounded refs and G4 promotion cover the scope. |
| P23 stakes laundering | Low-stakes conversion floors are used for higher-stakes commitments. | Stakes and reversibility from W12.D/S7/S10 must limit or block conversion scope. |
| P25 search-control laundering | No-hit/search frontier is projected as domain ceiling or conversion evidence. | G5 requires recall/freshness health for abstention and separates search ceiling from domain ceiling. |
| P26 responsibility-integrity laundering | Human accountability is shifted without informed choice. | If conversion scope is high-stakes/value-laden, S7/P26 integrity must be concrete, not manifest-only. |

Capability transition:

| Capability | Current label | Target label | Acceptance signal |
| --- | --- | --- | --- |
| First proving-ground conversion | `producer_missing`, `artifact_missing`, `bridge_missing`, `consumer_missing`, `surface_missing`, `semantic_test_missing` | `implemented` | Pinned case -> conversion record -> persisted artifacts -> W12.D gate -> surfaces -> negatives. |
| W12.D Layer 3 conversion consumption | `implemented_but_not_orchestrated` for G4 input | `implemented` for G5 conversion output | W12.D emits `layer3_g5_conversion_gate` and G5 summary without erasing earlier gates. |
| Envelope-expansion health | `measured_by_prereq`, not G5-governed | `implemented` for first conversion reading | Persisted delta has envelope, effort refs, trend, and non-conversion reason taxonomy. |
| S4-S14 composed-loop conversion gate | `implemented_but_not_orchestrated` for Layer 2 summaries | `implemented` for G5 eligibility input | Conversion blocks when any required S4-S14/S14 component is absent, partial, or failed. |
| Upstream scope-join matrix | `verification_missing` for G5 conversion composition | `implemented` for G5 eligibility input | G1/G2/G3/GL refs are joined to the same case, design record, claim family, envelope, and G4 promotion scope. |
| G4 per-record conversion resolution | `consumer_missing` for G5 use of G4 handoff | `implemented` for G5 eligibility input | G5 matches promotion record id, state, design ref/digest, scope, blockers, limitations, and deny-list before conversion. |
| Effective evidence independence | `verification_missing` for G5 design conversion | `implemented` for `grounded_limited` only | Evidence set reports effective independence/collapse refs before useful-design credit can be considered. |
| Five health-metric reading | `measured_by_prereq`, not G5-owned | `implemented` for G5 snapshot/consumption | G5 records envelope-expansion-rate directly and carries upstream adapter-semantic-loss, governance-throughput, demand-pull-vs-abstention, and search-recall/index-staleness statuses as bounded inputs. |
| G5 generated/audit surface | `surface_missing` | `implemented` | G5 mirrors G4 exact artifact family, inventory/docs/public-surface registrations, projection-only public refs, and drift checks. |

Tradeoff guardrails:

- **T1 domain ceiling:** a flat envelope-expansion reading is allowed only when
  the domain ceiling is evidenced, not inferred from missing plumbing.
- **T6 honesty inertia:** `grounded_abstention` is acceptable value only when it
  is grounded and demanded work has actually been attempted; it must not become
  a cheap refusal path. The plan requires demand-pull attempt refs, not just a
  prose explanation.
- **T7 false abstention:** every abstention path must cite recall/freshness
  checks and distinguish search ceiling from domain ceiling.
- **All five health metrics:** G5 directly produces the first
  `envelope-expansion-rate` reading, but it must also snapshot upstream
  `adapter-semantic-loss`, `governance-throughput`,
  `demand-pull-vs-abstention`, and `search-recall@known-seeds +
  index-staleness` statuses. Snapshotting is consumption, not re-production or a
  new G5 scoring engine.

## Code-Grounded Reality

Existing strengths G5 should reuse:

- `tools/quality/validation/run_universal_outcome_corpus.py` already materializes
  the full W12.D report and injects G0/G1/G2/G3 gates in order.
- `_run_case(...)` already returns rich per-case S2 and S4-S14 blocks before
  G0/G1/G2/G3 are attached in the report builder. G5 should use these per-case
  blocks for conversion gating rather than inventing a second Layer 2 runner.
- Current W12.D pinned-case keys are concrete and reusable:
  `s2_design_search`, `s4_epistemic_regime`, `s5_coupling_composition`,
  `s6_blind_spot_firewalls`, `s7_delegation`, `s8_value_choice`,
  `s9_projection_lowering`, `s10_outcome_prediction`,
  `s11_predictive_knowledge`, `s12_resource_economics`,
  `s13_post_deploy_accountability`, `s14_universality_assurance`,
  `layer3_g0_grounding_gate`, `layer3_g1_grounding_gate`,
  `layer3_g2_forecast_gate`, and `layer3_g3_analytics_search_gate`.
- W12.D keeps `typed_blocker` out of useful-design credit and has tests proving
  G0/G1/G2/G3 do not overwrite conversion outcomes before G5.
- W12.D already separates runtime useful-design production from expert expected
  ceiling: `runtime_useful_design_count/rate`,
  `expert_useful_design_ceiling_count/rate`, and
  `useful_design_alignment_*` are distinct. G5 must update only runtime/G5-owned
  conversion counters when eligible; it must not make expert ceiling look like
  produced runtime usefulness.
- The outcome corpus already has a W11.C useful-design metric eligibility gate:
  `build_expert_adjudication_useful_design_gate(...)` can emit
  `status=eligible` and `counts_toward_useful_design=True`, but it is
  authoritative only for `useful_design_metric_eligibility` and denies claim,
  closeout, legal, producer-evidence, and public-recommendation authority. G5
  should join to this policy when it changes useful-design metrics instead of
  inventing a second useful-design gate.
- A current W12.D run against the repo still yields 13 typed blockers, zero
  runtime useful-design cases, and zero grounded conversions before G5. This is
  useful signal: G5 should prove one bounded conversion path instead of masking
  the whole corpus with a new status.
- `FIRST_VERTICAL_CORPUS_CASE_ID`, `G1_PINNED_CASE_ID`, and
  `S3_FIRST_PROVING_CASE_ID` already converge on
  `ua-msme-affordable-loans-2022`.
- G1 exposes search recall/freshness and hardcode-strangle health in W12.D
  gates, which G5 needs to distinguish search ceiling from domain ceiling.
- G0 already encodes the right health vocabulary for G5 to reuse:
  `layer3_health_metric_ledgers.toml` freezes all five constitution metrics at
  the pre-adapter baseline, with `envelope-expansion-rate` and
  `demand-pull-vs-abstention` explicitly at zero grounded conversions. G5
  should read this as baseline/owner/trend context, not invent a parallel health
  taxonomy.
- G0 search ledgers are explicitly control-plane artifacts. The discovery
  validator rejects search ledgers that claim `authoritative_for`; G5 must carry
  this distinction forward when explaining search ceiling versus domain ceiling.
- G1 current source-contract binding is concrete but limited:
  `firm_survival` is `observed_but_uncertain`, has a
  `source_contract_content_hash`, `observed_through`, `coverage_period_ref`, and
  lineage refs, and denies `claim_authority`, `adapter_promotion`,
  `useful_design_credit`, `production_authority`, and `search_hit_as_authority`.
  This is a usable substrate input, not design conversion authority.
- Current G1 lineage and later G3 source-lineage payloads contain duplicate refs
  in places. G5 must dedupe refs/source hashes before evidence strength or
  effective independence is calculated.
- `runtime/quality/evidence_independence.py` already implements P14 collapse
  semantics with `build_evidence_independence_map(...)`,
  `validate_evidence_independence_map_record(...)`, collapse dimensions such as
  `source_lineage_cluster_id`, `method_cluster_id`, `assumption_cluster_id`,
  and `shared_failure_mode_cluster_id`, and statuses including
  `inflated_raw_count`. G5 should reuse that map shape or emit a narrow adapter
  to it, not hand-roll a raw-ref counter.
- S2 design search is already a rich narrow waist: it has a deterministic replay
  key, `design_record`, `search_ledger`, S7 delegation refs, S12 resource refs,
  and S4-S14 axis positions. G5 should read these existing fields rather than
  creating another pinned-case design record.
- Current S12 resource economics already exposes demand/growth evidence:
  `growth_entries[].demand_act_ref`, `certified_envelope_delta_ref`,
  `reuse_evidence_refs`, five VOI sites, typed budgets, and an
  `explore_exploit_posture`. G5 should consume those refs for demand-pull and
  envelope-expansion evidence.
- Current S14 universality assurance is useful as declared-envelope projection:
  it carries `declared_posture=limited`, `grounded_authority_status=pass`, and a
  declared envelope ref, while `universal_claim_gate_status=pending_sealed` and
  `battery_status=not_tested` keep universal claims out of scope.
- G2 and G3 already have W12.D consumer gates and explicitly report zero
  useful-design delta before G5.
- G3's current W12.D hook intentionally passes
  `useful_design_before == useful_design_after`, so
  `layer3_g3_analytics_search_summary.useful_design_delta_count` remains zero.
  This is a useful regression pattern for G5: G5 becomes the first allowed
  conversion overlay, while G3 remains proof-consumption context.
- G2 exposes G4/G5-readable forecast handoffs, but the case/design scope is
  encoded through refs such as `s10_forecast_support_ref` and
  `design_record_ledger_refs`, not as a simple top-level `case_id`. G3 exposes
  proof records with the strongest case/design evidence nested in `s11_record`.
  G5 must join through those refs instead of trusting only manifest counts.
- G2 and G3 handoffs already preserve authority boundaries: their readable refs
  are evidence inputs, not conversion, publication, closeout, or useful-design
  authority. G5 should reuse that deny-list rather than widening it.
- G2 forecast support is stronger than a search hit: it has observable
  calibration, credible-evaluation refs, method-validity refs, uncertainty
  intervals, and an authority envelope for forecast tiering. It still denies
  claim, recommendation, closeout, S11, S12, S13, and S14 authority.
- G3 proof-carrying analytics is stronger than a narrative proof: it has a
  proof ref, certificate refs, S11 per-axis calibration, and IR bridge refs. It
  still has `proof_status=identified`, `proof_composability_status=reusable`,
  posture `shadow`, and denies claim/recommendation/closeout/S12-S14 authority.
- G4 now persists `layer3_g4_g5_promotion_handoff.json` and
  `layer3_g4_promotion_records.json`; the handoff is authoritative only for
  G5 promotion-state input refs and denies useful-design credit before G5.
- G4's G5 handoff is valuable but mixed: it has `status=pass` and
  `authoritative_for=["g5_first_proving_ground_promotion_state_input_refs"]`,
  while also carrying blocker refs from the blocked causal-forecast promotion
  path. G5 must treat handoff `pass` as "handoff formed", not "all scopes
  usable".
- G4 already contains much of the semantic machinery G5 needs: A-completeness,
  grounded-contract-row rejection of readiness summaries/search ledgers,
  weakest-boundary composition, S7/P26 human-decision integrity, authority
  deny-lists, conformance negatives, exact write-mode artifact sets,
  manifest-runtime drift checks, generated-artifact registration checks,
  inventory/docs/public-surface checks, and PUBLIC/REVIEWER/EXPERT/MACHINE
  surfaces.
- `architecture/generated_artifacts.toml`, `docs/reference/generated-artifacts.md`,
  `architecture/policy_design_case/inventory.json`, and
  `docs/reference/public-surface.md` already contain the G4 family and surface
  pattern G5 should mirror.
- Generated-artifact families are not informal lists: the committed registry
  carries owner, lifecycle, generator/verifier, stale-output behavior,
  regenerate command, drift gate, and exact outputs. G5 must create a new family
  with the same level of machine-checkable ownership and stale-output behavior,
  not only append names to a plan.
- Runtime quality already has the consumer-side boundary tools G5 needs:
  `authority_purpose_blockers(...)`,
  `assert_policy_design_projection_not_authority(...)`,
  S10-S14 projection consumer-contract verifiers, closeout-reader substitute
  rejection, and the hypothesis/candidate firewall. G5 should call or mirror
  these, not create a new authority firewall vocabulary.
- The Layer 3 runtime modules use strict Pydantic models and bundle builders
  with readiness CLIs; G5 should follow the same contract shape rather than
  inventing another validator style.

Existing weak spots G5 must not underestimate:

- There is no `layer3_proving_ground_conversion.py` module, no G5 readiness CLI,
  no G5 artifact family, and no G5 W12.D hook yet.
- G2/G3/GL readiness manifests are not shape-identical. G2/G3 expose
  slice-specific conformance, W12.D consumer, public-projection, and
  health-metric keys; GL can be `pass` while legal lineage/reference resolution
  remains `reissue_required` or reference-only. G5 must read exact dependency
  keys and artifact rows, not a single generic status.
- `build_w12d_universal_outcome_corpus_report()` currently computes
  `_summary(cases)` before corpus-level S4-S14 summaries are built. A G5 hook
  placed after G3 and before summary can see per-case S4-S14 blocks, but cannot
  depend on report-level S4-S14 summaries unless the builder order is changed
  and covered by tests.
- G3 analytics-search summary is currently top-level outside the W12.D
  `summary` object. G5 summary wiring must account for this location or tests
  will accidentally prove only G0/G1/G2 summary behavior.
- Existing `_build/.tmp/production-quality/w12d*.json` files are local caches
  and may be stale relative to current code. G5 must never auto-discover a
  latest `_build` report as evidence; it must build or receive an explicit fresh
  W12.D payload and persist the pinned bundle it used.
- W12.D's top-level `grounded_conversion_count` currently derives from G0 gates,
  which is correct before G5 but wrong as the final Layer 3 conversion signal
  after G5. G5 must introduce G5-owned conversion counts and only then update any
  top-level grounded conversion summary.
- W12.D's useful-design metrics already carry runtime-vs-expert separation.
  If G5 updates `runtime_useful_design_count/rate` or legacy
  `useful_design_count/rate`, it must also preserve
  `expert_useful_design_ceiling_*` and `useful_design_alignment_*` semantics.
  A `grounded_limited` conversion is not allowed to rewrite expert ceiling or
  lower the existing typed-blocker metric policy.
- W12.D `OUTCOMES` do not include `grounded_limited` or
  `grounded_abstention`. G5 must not silently append them or let them leak into
  closeout as production states. Use a separate conversion gate and explicit
  mapping to existing outcome semantics.
- W11.C expert-adjudication useful-design eligibility is a metric gate, not
  conversion authority. G5 must join to it or explicitly mark it
  `surface_out_of_scope` for first conversion; it cannot cite expert labels as
  claim/closeout/legal authority or bypass G5's own conversion evidence.
- Current S2 status is `acquisition_required`, with
  `acquisition_branch_state=bridge_missing`. A full S4-S14 payload exists, but
  G5 must not treat this as acquisition/composition closure. It must surface an
  abstention/blocker reason unless the acquisition branch is actually resolved.
- Current S2 `design_record.firewall_status` and constraint-store rows include
  `warn`, `limit`, and `block` states. G5 must inspect and compose these
  per-axis records; the presence of a design record is not enough.
- Current S7 responsibility evidence is present under
  `delegation_posture.human_decision_record_ref` and
  `search_ledger.delegation_record_refs`; generic
  `search_ledger.human_decision_record_refs` may be empty. A P26 resolver that
  reads only the generic list will falsely miss or falsely clear delegation.
- The current G4 passing promotion record is source-data scope only. It can
  support a bounded source-grounded non-useful slice or a grounded abstention
  input, but not `grounded_limited` useful-design credit unless G2/G3 design
  evidence also covers the scope.
- `layer3_g4_weakest_boundary_composition.json` currently reflects the promoted
  source-data chain, while `layer3_g4_promotion_records.json` also carries a
  blocked causal-forecast probe. G5 must inspect promotion records and handoff
  refs per scope; treating the weakest-boundary artifact alone as the whole G4
  truth would miss the blocked design-level path.
- The G4 blocked causal-forecast record is valuable negative evidence. G5 must
  keep it as a blocker or limitation; using it as conversion evidence is a
  laundering bug.
- `layer3_g4_grounded_contract_set.json` currently repeats the same G1 source
  contract binding. G5 must dedupe grounded-contract refs and lineage/source
  hashes before calculating evidence strength.
- G4 readiness is `pass`, but the current summary reports generated-artifact,
  inventory, and reference-doc registration statuses as `unknown`. G5 must not
  inherit G4 pass as its own external-surface readiness.
- G4 public projection exposes promotion-state explanation with safe refs and a
  full deny-list. It is a projection surface, not a source of conversion
  authority.
- G4 readiness and docs registration are strong patterns to reuse, but G5 should
  be stricter for its own closure than an inherited upstream `pass`: if G5's
  artifact family, inventory, reference docs, public-surface marker, write set,
  or manifest drift checks are missing, G5 readiness remains red.
- Current persisted artifacts therefore make `grounded_abstention` or
  `unchanged_blocker` the realistic current-repo path. A
  `grounded_limited` fixture is allowed only if it includes explicit
  scope-matching G2/G3 evidence and a matching design-level G4 governed
  promotion; it must not be inferred from the current source-only G4 record.
- GL readiness is `pass`, but reference resolution/amendment lineage can be
  `reissue_required`. If legal/mandate scope is part of the G5 conversion,
  reissue status must block or narrow the legal part of the conversion; it is
  not harmless readiness noise.
- Current GL legal authority report is especially easy to overread:
  `status=pass`, but `applicability_status=fail`, `case_id=null`,
  `authoritative_for=[]`, `legal_requirement_artifact_ref=null`,
  `reference_resolution_status=null`, and `temporal_resolution_status=null`.
  G5 must treat this as legal-search/report formation, not applicable legal
  authority for the pinned case.
- GL's typed legal requirement compiler is a real strength:
  `layer3_gl_legal_requirement_bindings.json` contains a typed requirement
  artifact with legal time window and authority boundary. G5 should use it as a
  requirement input, while still blocking/narrowing because applicability,
  reference resolution, amendment lineage, and mandate compatibility remain
  unresolved or compatibility-only.
- GL mandate records currently show `status=compatibility_only` with
  `s6_evaluation_ref=null`; S6/mandate pass cannot be inferred from GL.
- G2 current handoff joins are nontrivial: `design_record_ledger_refs` use a
  shorter S2 alias, `s2_deterministic_replay_key_refs` is empty, and
  `source_contract_ref` differs from the current G1 source contract ref. G5
  needs explicit alias normalization or a typed scope-join blocker.
- G3 current proof record has duplicate source-lineage hashes and
  `proof_status=identified`. This is proof-validity input, not claim authority
  or independent multi-source evidence by itself.
- Demand-pull evidence is already strongest in S12 case signals and per-case
  S12 payloads (`principal_ref`, `demand_act_refs`, `growth_entries`,
  `voi_allocation_refs`, and S3 reuse refs). G5 should consume those refs
  instead of requiring a non-existent top-level S3 demand field.
- W12.D imports are already large. G5 should use lazy import for the G5 consumer
  gate, mirroring the G3 pattern, rather than increasing top-level import cost.
- W12.D manifest-only evidence remains insufficient. G5 needs full per-case
  payload/replay refs or an explicit unresolved blocker.
- Public export surfaces are projection-only by default. G5 should emit
  projection refs first; direct export bundle integration is only allowed if it
  is fully tested and authority bounded.
- Closeout readers reject dashboard/readiness/package/public-export surfaces as
  substitute evidence. G5 surfaces must remain audit projections and must not be
  fed back into closeout, approval, scorecard, or publication authority.
- Runtime projection contracts already fail closed on projection authority
  laundering and candidate laundering. G5 must not weaken these by creating a
  "conversion projection" path that fills `authoritative_for` or accepts
  `candidate_unverified` refs.
- Effective independence already has a full collapse model. If G5 only dedupes
  exact string refs without producing a collapse record over lineage/method/
  assumption/shared-failure dimensions, it has not closed P14 for
  `grounded_limited`.

Simplifications from this audit:

- Reuse the G4 readiness CLI scaffold for expected paths, `--write`,
  manifest-runtime drift, registration/docs checks, public-surface checks,
  conformance negatives, and performance contract. Do not invent a new readiness
  framework for G5.
- Reuse G4 negative-test vocabulary where it already names the failure:
  readiness-summary-only conversion, GL compatibility overclaim, public raw
  payload leak, authority leak, human-decision bypass, weakest-boundary ignored,
  and upstream-builder rerun in the request path.
- Keep G5 as resolver/composer/classifier/emitter. New search, new acquisition,
  new closeout semantics, and new public-export routing are unnecessary for the
  first proving-ground conversion.
- Reuse existing S10-S14 projection consumer-contract verifiers where G5 emits
  public/reviewer/expert/machine projections. Add G5-specific source fields to
  those projections instead of bypassing their authority checks.
- Reuse closeout-reader tests as negative patterns: readiness pass, scorecard
  pass, projection, package, and public export may be observed, but cannot
  substitute for closeout evidence.
- Reuse the candidate firewall for any LLM/hypothesis-derived text in G5
  projections; unverified candidates become blockers/limitations, never
  conversion authority.
- Reuse `build_evidence_independence_map(...)` /
  `validate_evidence_independence_map_record(...)` or a deliberately narrow
  G5 adapter to their schema for effective-independence evidence.
- Reuse the existing W12.D useful-design metric policy and W11.C
  `build_expert_adjudication_useful_design_gate(...)` boundary for metric
  eligibility; do not make G5 conversion classification itself the useful-design
  metric authority.

## Target File Map

Create:

- `src/polisyos/runtime/quality/proving_ground/proving_ground_conversion.py`
  - Strict G5 DTOs, builders, validators, dependency resolver, conversion
    eligibility logic, W12.D consumer gate builder, conformance negatives, and
    bundle builder.
- `tools/quality/validation/check_policy_design_case_layer3_g5_readiness.py`
  - CLI matching earlier slices: `--repo-root`, `--write`, `--output`,
    `--output-format`.
- `tests/unit/runtime/quality/test_layer3_g5_proving_ground_conversion.py`
  - Runtime DTO/builder/conformance tests and semantic negatives.
- `tests/repo_quality/tools/test_policy_design_case_layer3_g5_readiness.py`
  - Persisted artifacts, manifest drift, docs/TOML/inventory registration,
    issue-code dictionary, surface visibility, and readiness checks.
- `tests/repo_quality/tools/test_policy_design_case_layer3_g5_readiness_cli.py`
  - CLI write/validate behavior.
- `tests/fixtures/layer3/g5/`
  - Valid bounded conversion fixture, grounded abstention fixture, source-only
    overclaim fixture, missing-G2/G3 design-support fixture, S14
    missing-or-failed fixture, effective-independence-missing fixture,
    upstream-scope-mismatch fixture, demand-pull-missing fixture,
    stale-build-cache fixture, blocked-promotion fixture, manifest-only fixture,
    stale-search fixture, search-recall-miss fixture, G4 weakest-boundary
    mismatch fixture, GL reissue-required fixture, GL applicability-fail
    fixture, G1 observed-but-uncertain overclaim fixture, duplicate-lineage
    inflation fixture, S2 acquisition-required/bridge-missing fixture, S2
    firewall block fixture, S7 delegation-ref location fixture, S12 growth
    without envelope-delta fixture, S14 pending-sealed overclaim fixture, G2
    design-record alias mismatch fixture, G2 missing S2 replay-key fixture, G2
    source-contract mismatch fixture, G3 identified-proof overclaim fixture,
    G4 handoff-pass-with-blockers fixture, current-repo unchanged-blocker
    fixture, useful-design metric gate missing fixture, expert ceiling/runtime
    credit confusion fixture, independence-map raw-count inflation fixture, and
    non-pinned widening fixture.
- `docs/reference/policy-design-case-layer3-proving-ground-conversion.md`
  - Reference doc explaining G5 conversion states, W12.D composition, envelope
    expansion, search-ceiling/domain-ceiling distinction, and surfaces.

Modify:

- `tools/quality/validation/run_universal_outcome_corpus.py`
  - Add G5 conversion gate after G3 and before summary, with lazy import and
    G5-owned summary keys.
- `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`
  - Add W12.D G5 routing, non-overwrite, useful-design-credit, and negative
    tests.
- `architecture/generated_artifacts.toml`
  - Add G5 generated-artifact family.
- `architecture/policy_design_case/inventory.json`
  - Register G5 conversion surface and readiness artifacts.
- `docs/reference/generated-artifacts.md`
  - Add G5 generated artifact family.
- `docs/reference/documentation-inventory.md`
  - Add G5 reference doc if local docs inventory requires it.
- `docs/reference/index.md`
  - Link G5 reference doc if local pattern requires it.
- `docs/reference/public-surface.md`
  - Add G5 conversion projection surface.

Do not modify:

- `tools/quality/validation/check_policy_design_case_layer3_g4_readiness.py`
  for G5 behavior. Use it as implementation template and regression reference
  for exact-artifact, drift, registration, docs, and surface checks.
- G1/G2/G3/GL runtime modules to make G5 green. If upstream artifacts are
  insufficient, G5 records `unchanged_blocker` or grounded abstention rather than
  reshaping upstream truth.
- G4 promotion semantics. G5 consumes G4 handoff; it does not redefine
  `governed_promoted`.
- `approval.py`, `scorecard.py`, or production closeout logic to treat G5 as
  approval.
- W12.D `OUTCOMES` without an explicit status-composition decision and tests.

## Execution File Matrix

Use this matrix when executing task-by-task. It is intentionally narrower than
the full dependency list: these are the files each task is expected to create or
modify.

| Task | Create | Modify | Test |
| --- | --- | --- | --- |
| Task 0 | `tests/unit/runtime/quality/test_layer3_g5_proving_ground_conversion.py`; `tests/repo_quality/tools/test_policy_design_case_layer3_g5_readiness.py`; `tests/repo_quality/tools/test_policy_design_case_layer3_g5_readiness_cli.py` | `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py` | Same four test files |
| Task 1 | `src/polisyos/runtime/quality/proving_ground/proving_ground_conversion.py`; selected `tests/fixtures/layer3/g5/*.json` negatives | none outside G5 module/tests | `tests/unit/runtime/quality/test_layer3_g5_proving_ground_conversion.py` |
| Task 2 | additional `tests/fixtures/layer3/g5/*.json` W12.D/S2/S7/S12/S14 fixtures | `src/polisyos/runtime/quality/proving_ground/proving_ground_conversion.py`; `tests/unit/runtime/quality/test_layer3_g5_proving_ground_conversion.py` | `tests/unit/runtime/quality/test_layer3_g5_proving_ground_conversion.py` |
| Task 3 | additional `tests/fixtures/layer3/g5/*.json` scope/status/useful-design fixtures | `src/polisyos/runtime/quality/proving_ground/proving_ground_conversion.py`; `tests/unit/runtime/quality/test_layer3_g5_proving_ground_conversion.py` | `tests/unit/runtime/quality/test_layer3_g5_proving_ground_conversion.py` |
| Task 4 | G5 health TOML/JSON artifact producers inside `src/polisyos/runtime/quality/proving_ground/proving_ground_conversion.py` | `src/polisyos/runtime/quality/proving_ground/proving_ground_conversion.py`; `tests/unit/runtime/quality/test_layer3_g5_proving_ground_conversion.py` | `tests/unit/runtime/quality/test_layer3_g5_proving_ground_conversion.py` |
| Task 5 | none | `tools/quality/validation/run_universal_outcome_corpus.py`; `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py` | `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py` |
| Task 6 | `tools/quality/validation/check_policy_design_case_layer3_g5_readiness.py`; `docs/reference/policy-design-case-layer3-proving-ground-conversion.md`; G5 persisted artifacts under `architecture/policy_design_case/` | `architecture/generated_artifacts.toml`; `architecture/policy_design_case/inventory.json`; `docs/reference/generated-artifacts.md`; `docs/reference/documentation-inventory.md`; `docs/reference/index.md`; `docs/reference/public-surface.md`; `tests/repo_quality/tools/test_policy_design_case_layer3_g5_readiness.py`; `tests/repo_quality/tools/test_policy_design_case_layer3_g5_readiness_cli.py` | `tests/repo_quality/tools/test_policy_design_case_layer3_g5_readiness.py`; `tests/repo_quality/tools/test_policy_design_case_layer3_g5_readiness_cli.py` |
| Task 7 | any remaining `tests/fixtures/layer3/g5/*.json` conformance/performance fixtures | `src/polisyos/runtime/quality/proving_ground/proving_ground_conversion.py`; `tools/quality/validation/check_policy_design_case_layer3_g5_readiness.py`; G5 test files | all required commands in Task 7 |

Exact fixture filenames:

- `tests/fixtures/layer3/g5/valid_bounded_conversion.json`
- `tests/fixtures/layer3/g5/grounded_abstention.json`
- `tests/fixtures/layer3/g5/source_only_overclaim.json`
- `tests/fixtures/layer3/g5/missing_g2_g3_design_support.json`
- `tests/fixtures/layer3/g5/s14_missing_or_failed.json`
- `tests/fixtures/layer3/g5/effective_independence_missing.json`
- `tests/fixtures/layer3/g5/upstream_scope_mismatch.json`
- `tests/fixtures/layer3/g5/demand_pull_missing.json`
- `tests/fixtures/layer3/g5/stale_build_cache.json`
- `tests/fixtures/layer3/g5/blocked_promotion.json`
- `tests/fixtures/layer3/g5/manifest_only_w12d.json`
- `tests/fixtures/layer3/g5/stale_search.json`
- `tests/fixtures/layer3/g5/search_recall_miss.json`
- `tests/fixtures/layer3/g5/g4_weakest_boundary_mismatch.json`
- `tests/fixtures/layer3/g5/gl_reissue_required.json`
- `tests/fixtures/layer3/g5/gl_applicability_fail.json`
- `tests/fixtures/layer3/g5/g1_observed_but_uncertain_overclaim.json`
- `tests/fixtures/layer3/g5/duplicate_lineage_inflation.json`
- `tests/fixtures/layer3/g5/s2_acquisition_required_bridge_missing.json`
- `tests/fixtures/layer3/g5/s2_firewall_block.json`
- `tests/fixtures/layer3/g5/s7_delegation_ref_location.json`
- `tests/fixtures/layer3/g5/s12_growth_without_envelope_delta.json`
- `tests/fixtures/layer3/g5/s14_pending_sealed_overclaim.json`
- `tests/fixtures/layer3/g5/g2_design_record_alias_mismatch.json`
- `tests/fixtures/layer3/g5/g2_missing_s2_replay_key.json`
- `tests/fixtures/layer3/g5/g2_source_contract_mismatch.json`
- `tests/fixtures/layer3/g5/g3_identified_proof_overclaim.json`
- `tests/fixtures/layer3/g5/g4_handoff_pass_with_blockers.json`
- `tests/fixtures/layer3/g5/current_repo_unchanged_blocker.json`
- `tests/fixtures/layer3/g5/useful_design_metric_gate_missing.json`
- `tests/fixtures/layer3/g5/expert_ceiling_runtime_credit_confusion.json`
- `tests/fixtures/layer3/g5/independence_map_raw_count_inflation.json`
- `tests/fixtures/layer3/g5/non_pinned_widening.json`

## Persisted Artifacts

Expected generated artifacts:

- `architecture/policy_design_case/layer3_g5_dependency_readiness_snapshot.json`
- `architecture/policy_design_case/layer3_g5_pinned_case_input_bundle.json`
- `architecture/policy_design_case/layer3_g5_w12d_case_block_index.json`
- `architecture/policy_design_case/layer3_g5_composed_loop_completeness_gate.json`
- `architecture/policy_design_case/layer3_g5_g4_handoff_resolution.json`
- `architecture/policy_design_case/layer3_g5_g4_promotion_record_resolution.json`
- `architecture/policy_design_case/layer3_g5_upstream_scope_join_matrix.json`
- `architecture/policy_design_case/layer3_g5_grounded_result_evidence_set.json`
- `architecture/policy_design_case/layer3_g5_effective_evidence_independence.json`
- `architecture/policy_design_case/layer3_g5_useful_design_metric_eligibility_join.json`
- `architecture/policy_design_case/layer3_g5_conversion_eligibility_ledger.json`
- `architecture/policy_design_case/layer3_g5_status_composition_ledger.json`
- `architecture/policy_design_case/layer3_g5_grounded_abstention_quality_record.json`
- `architecture/policy_design_case/layer3_g5_demand_pull_attempt_record.json`
- `architecture/policy_design_case/layer3_g5_dependency_health_metric_snapshot.json`
- `architecture/policy_design_case/layer3_g5_envelope_expansion_delta.json`
- `architecture/policy_design_case/layer3_g5_conversion_records.json`
- `architecture/policy_design_case/layer3_g5_w12d_consumer_gate.json`
- `architecture/policy_design_case/layer3_g5_conversion_audit_surface.json`
- `architecture/policy_design_case/layer3_g5_public_export_projection_refs.json`
- `architecture/policy_design_case/layer3_g5_conformance_report.json`
- `architecture/policy_design_case/layer3_g5_health_metric_delta.toml`
- `architecture/policy_design_case/layer3_g5_conversion_route_contract_registry.toml`
- `architecture/policy_design_case/layer3_g5_registry_ratchet_delta.json`
- `architecture/policy_design_case/layer3_g5_readiness_manifest.json`

Minimum write-mode paths must include all artifacts above. G5 cannot close from
runtime-only success or a W12.D report that was not persisted through the G5
readiness writer.

## Runtime Contract Sketch

Add strict DTOs in `layer3_proving_ground_conversion.py`:

- `Layer3G5ValidationIssue`
- `Layer3G5ValidationReport`
- `Layer3G5DependencyReadinessSnapshot`
- `Layer3G5PinnedCaseInputBundle`
- `Layer3G5W12DCaseBlockIndex`
- `Layer3G5Layer2StatusReading`
- `Layer3G5S2ReplayScopeJoin`
- `Layer3G5ComposedLoopCompletenessGate`
- `Layer3G5G4HandoffResolution`
- `Layer3G5G4PromotionRecordResolution`
- `Layer3G5UpstreamScopeJoinMatrix`
- `Layer3G5ScopeJoinAliasResolution`
- `Layer3G5GroundedEvidenceRef`
- `Layer3G5GroundedResultEvidenceSet`
- `Layer3G5EffectiveEvidenceIndependenceRecord`
- `Layer3G5UsefulDesignMetricEligibilityJoin`
- `Layer3G5LineageDeduplicationRecord`
- `Layer3G5ConversionEligibilityLedger`
- `Layer3G5StatusCompositionLedger`
- `Layer3G5GroundedAbstentionQualityRecord`
- `Layer3G5DemandPullAttemptRecord`
- `Layer3G5S12DemandGrowthEvidence`
- `Layer3G5S14DeclaredEnvelopeReading`
- `Layer3G5DependencyHealthMetricSnapshot`
- `Layer3G5EnvelopeExpansionDelta`
- `Layer3G5ConversionRecord`
- `Layer3G5W12DConsumerGate`
- `Layer3G5ConversionAuditSurface`
- `Layer3G5PublicExportProjectionRefs`
- `Layer3G5ProjectionCloseoutBoundaryCheck`
- `Layer3G5ConformanceNegativeResult`
- `Layer3G5ConformanceReport`
- `Layer3G5RegistryRatchetDelta`
- `Layer3G5ReadinessManifest`
- `Layer3G5Bundle`

Controlled values:

```python
Layer3G5ConversionOutcome = Literal[
    "typed_blocker -> grounded_limited",
    "typed_blocker -> grounded_abstention",
    "unchanged_blocker",
]

Layer3G5GroundingDisposition = Literal[
    "grounded_limited",
    "grounded_abstention",
    "ungrounded_blocked",
]
```

Authority boundary:

```python
G5_AUTHORITATIVE_FOR = (
    "layer3_g5_proving_ground_conversion_classification",
    "layer3_g5_envelope_expansion_reading",
    "w12d_layer3_conversion_gate",
)

G5_MAY_NOT_USE_FOR = (
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
    "claim_authority_without_upstream_grounding",
    "causal_effect_authority_without_g2",
    "proof_authority_without_g3",
    "legal_authority_without_gl",
    "useful_design_rate_floor_relaxation",
    "g6_arbitrary_request_orchestration",
    "g7_region_widening",
)
```

Core builder signatures:

```python
def build_layer3_g5_bundle(repo_root: Path) -> Layer3G5Bundle: ...

def validate_layer3_g5_bundle(
    repo_root: Path,
    persisted: Mapping[str, Any] | Layer3G5Bundle,
) -> Layer3G5ValidationReport: ...

def build_g5_w12d_consumer_gate(
    case: Mapping[str, Any],
    *,
    conversion_records: Sequence[Layer3G5ConversionRecord | Mapping[str, Any]] = (),
    dependency_snapshot: Layer3G5DependencyReadinessSnapshot | Mapping[str, Any] | None = None,
) -> Layer3G5W12DConsumerGate: ...
```

## Conversion Semantics

`typed_blocker -> grounded_limited` requires:

- pinned case is `ua-msme-affordable-loans-2022`;
- the original W12.D state is a typed blocker or pre-G5 conversion blocker;
- full S4-S14 composed-loop completeness gate passes, including S14 universality
  assurance for the declared grounded claim;
- G1 grounded source contracts cover the required source/construct claims;
- G1 `observed_but_uncertain` source-contract bindings can support bounded
  substrate evidence only with their `source_contract_content_hash`,
  `observed_through`, `coverage_period_ref`, lineage refs, and deny-list
  preserved; they cannot satisfy claim authority, adapter promotion, or
  useful-design credit by themselves;
- G4 has a matched `governed_promoted` promotion record for the exact declared
  conversion scope. The match is by promotion record, not by G4 readiness
  summary or the single weakest-boundary artifact alone;
- G2 calibrated forecast/effect support and required S10 posture refs cover the
  design-level claim;
- G2 source joins are exact or explicitly normalized: S2 design-record aliases,
  S2 deterministic replay-key refs, source-contract refs, calibration refs, and
  uncertainty refs must all align or the design-level portion is blocked;
- G3 proof-carrying analytics and S11 posture refs cover the design-level claim;
- G3 proof records are consumed as proof-validity/S11 calibration inputs only;
  `proof_status=identified` and duplicated source-lineage refs do not become
  claim authority or independent evidence;
- the upstream scope-join matrix proves G1/G2/G3/GL refs align with the same
  case id, source design record, claim family, envelope, and G4 promotion scope;
- weakest-boundary composition proves the conversion cannot outrank the weakest
  S4-S14, G1, G2, G3, GL, G4, search-health, or human-accountability boundary,
  and records `weakest_boundary_reason`;
- mixed upstream statuses such as `warn`, `partial`, `contested`,
  `review_required`, `limited`, or `near_binding` narrow or block the conversion
  instead of being flattened into `grounded_limited`;
- any legal/mandate claim has GL legal/mandate authority with no unresolved
  reissue/reference/temporal/applicability blocker. GL `status: pass` is
  insufficient when lineage or reference resolution is `reissue_required`;
- GL legal requirement artifacts are inputs to the legal requirement join, but
  `applicability_status=fail`, `case_id=null`, `mandate status=compatibility_only`,
  or `s6_evaluation_ref=null` blocks legal/mandate conversion even when the GL
  readiness manifest passes;
- high-stakes, value-laden, irreversible, or out-of-envelope scope has concrete
  S7/P26 responsibility-integrity evidence, including a `HumanDecisionRecord`
  where required, or the conversion scope is narrowed;
- S7/P26 evidence is resolved from both `delegation_posture.human_decision_record_ref`
  and `search_ledger.delegation_record_refs`; an empty generic
  `human_decision_record_refs` list alone is not enough to fail or pass the
  resolver;
- effective evidence independence is recorded, including collapse reasons for
  duplicated source/method/lineage/prompt support;
- effective independence is computed through the existing independence-map
  semantics or a G5 adapter to that schema; raw ref count, exact-string dedupe,
  or duplicate source hashes alone cannot satisfy `grounded_limited`;
- useful-design credit, when allowed, is separate from conversion
  classification: G5 must emit a useful-design metric eligibility join that
  preserves W12.D runtime-vs-expert metric separation and either joins to the
  existing W11.C useful-design gate or records why that gate is out of scope for
  the first conversion;
- S2 `acquisition_required`, `bridge_missing`, firewall `warn`/`limit`/`block`,
  and constraint-store statuses are composed before conversion; full S2 payload
  presence does not equal acquisition or design closure;
- search recall/freshness is healthy enough that no hidden search ceiling is
  being laundered as a domain ceiling;
- S12 growth evidence may count only when a demand act, certified envelope
  delta, and reuse/acquisition refs align; growth without an envelope delta is a
  limitation/blocker, not envelope expansion;
- S14 `pending_sealed` and `not_tested` statuses allow declared-envelope
  projection only; they block universal-claim or aggregate-universality
  conversion language;
- the declared envelope is bounded and the status composition ledger maps the
  result to existing W12.D outcome semantics.

`typed_blocker -> grounded_abstention` requires:

- G1 observed or grounded the relevant construct path;
- G1 `observed_but_uncertain` can support abstention only if the uncertainty,
  observation time, coverage period, and deny-list remain visible in the
  abstention quality record;
- full S4-S14 composed-loop payload is present; if S14 or another composed-loop
  gate fails, the abstention must carry that as the reason rather than hide it;
- S2 `acquisition_required` or `bridge_missing` is a valid abstention/blocker
  reason only when replay and demand-pull attempt refs prove it is the current
  limiting boundary;
- the abstention does not reuse unrelated green G2/G3/GL artifacts whose scope
  does not join to the pinned case or declared envelope;
- search recall/freshness and index staleness checks pass;
- no credible causal/proof/legal support exists inside the declared envelope, or
  the needed authority is genuinely out of envelope;
- the abstention has evidence refs and frontier/replay refs;
- demand-pull attempt refs show the system tried the demanded grounding path
  through S3/S12/accountable-principal signals before refusing;
- S12 demand/growth refs are reused when present; if the current payload has
  demand/growth refs but they do not join to the conversion scope, the
  abstention names that mismatch rather than claiming no demand evidence exists;
- any warning-like caveat is either an owned upstream warning with lifecycle refs
  or a G5 blocker/limitation; G5 does not create unowned soft gates;
- the result does not count as useful design and does not hide a fixable search,
  stale-index, missing conversion route/bridge, or manifest-only problem.

`unchanged_blocker` is required when:

- G1 or G4 readiness is missing;
- S4-S14/S14 composed-loop completeness is missing, partial, or failed for the
  declared conversion scope;
- no `governed_promoted` G4 record covers the conversion scope;
- a G4 `promotion_blocked` record is the only relevant promotion record;
- the G4 G5 handoff is `pass` but carries blocker refs for the requested scope;
- G4 grounded-contract refs duplicate the same underlying source/lineage and no
  effective-independence collapse record is present;
- G4 readiness is green but only for source-data scope while the requested
  conversion is causal/effect/proof/legal design-level scope;
- `grounded_limited` is attempted without G2/G3 design-level support;
- G2/G3 artifacts are green but the matching G4 design-level promotion record is
  blocked or absent;
- G2/G3/GL evidence exists but does not scope-join to the same case, design
  record, claim family, envelope, and promotion scope;
- G2 design-record alias normalization, S2 replay-key refs, or source-contract
  refs are missing or mismatched;
- G3 proof is only `identified`/shadow and is used as claim authority instead
  of proof-validity input;
- S2 acquisition branch remains `bridge_missing`;
- S14 is `pending_sealed`/`not_tested` and the requested conversion requires
  universality;
- GL legal report is `pass` but applicability fails, mandate is
  compatibility-only, reference resolution is unresolved, or amendment lineage
  requires reissue;
- upstream search health is stale or recall-degraded;
- W12.D payload is manifest-only or ref-only;
- human-accountability, legal reissue, demand-pull, evidence-independence, or
  calibration gaps remain unresolved;
- upstream `warn`, `partial`, `contested`, `review_required`, `limited`, or
  `near_binding` statuses lack composition rules for the declared conversion
  scope;
- the case is non-pinned or the request attempts G6/G7 scope.

G5 appends a conversion overlay and W12.D gate. It must not mutate pre-G5 W12.D
closed-case replay, canonical pre-G5 outcomes, or historical G0/G1/G2/G3 gate
payloads. Any changed summary is G5-owned and replayable back to the exact G5
rule/schema/time refs that produced it.

## Implementation Tasks

### Task 0 - Red Baseline and Dependency Audit

Tests first:

- Add `tests/unit/runtime/quality/test_layer3_g5_proving_ground_conversion.py`
  with imports expecting `polisyos.runtime.quality.proving_ground.proving_ground_conversion`.
- Add repo-quality tests expecting
  `tools/quality/validation/check_policy_design_case_layer3_g5_readiness.py`.
- Add W12.D tests proving no `layer3_g5_conversion_gate` exists yet and top-level
  `grounded_conversion_count` remains pre-G5.
- Confirm the red baseline fails only on missing G5 module/CLI/hook/artifacts.

Acceptance:

- Red failures are targeted.
- Pattern pass is recorded in the test names or comments.
- No G1/G2/G3/GL/G4 files are changed in Task 0.

### Task 1 - G5 Contracts and Dependency Resolver

Implement:

- Strict DTOs, constants, issue-code dictionary, and bundle skeleton.
- Dependency resolver over bounded artifact paths from generated-artifacts,
  inventory, G0/G1/G2/G3/GL/G4 readiness manifests, and persisted artifacts.
- Dependency resolver reads exact slice keys rather than assuming every
  manifest has a top-level `status`. It must resolve G2/G3 W12.D consumer,
  conformance, public projection, and five-health keys; GL lineage/reference
  reissue keys; and G4 promotion/admission/registration/drift keys.
- Resolver must ignore local `_build/.tmp` W12.D reports unless an explicit test
  passes one as payload; build-cache discovery is not evidence.
- G4 handoff resolver for `layer3_g4_g5_promotion_handoff.json` and
  `layer3_g4_promotion_records.json`.
- Per-record G4 promotion resolver that matches promotion record id,
  promotion state, source design record ref/digest, declared scope, claim
  families, blocker refs, limitation refs, and `may_not_use_for`. It must not
  treat `layer3_g4_weakest_boundary_composition.json` as a universal
  per-record proof.
- Resolver must treat G4 G5 handoff `status=pass` with scope blocker refs as a
  formed handoff with blocked sub-scope, not as all-clear conversion evidence.
- Resolver must carry G1 `grounding_status`, `source_contract_content_hash`,
  `observed_through`, `coverage_period_ref`, lineage refs, and `may_not_use_for`
  into the scope-join matrix.
- Resolver must build a deduplication record for repeated grounded-contract,
  lineage, source-hash, and proof-certificate refs before any evidence-strength
  or independence calculation.
- Resolver must feed deduped evidence candidates into the existing
  evidence-independence map shape, or record an explicit adapter payload that can
  be validated with `validate_evidence_independence_map_record(...)`.
- Resolver must read G2 design-record aliases, S2 replay-key refs, calibration
  refs, uncertainty refs, source-contract refs, and G3 S11 nested proof fields
  instead of relying on manifest counts.
- Fail-closed validation for missing G0/G1/G4, stale search health, malformed
  G4 handoff, missing `may_not_use_for`, or promotion-state authority leakage.

Tests:

- `test_layer3_g5_contracts_are_strict_and_frozen`
- `test_layer3_g5_dependency_snapshot_requires_g0_g1_g4`
- `test_layer3_g5_dependency_resolver_reads_slice_specific_readiness_keys`
- `test_layer3_g5_dependency_resolver_ignores_stale_build_cache_reports`
- `test_layer3_g5_g4_handoff_resolution_admits_governed_only`
- `test_layer3_g5_blocked_promotion_cannot_be_conversion_input`
- `test_layer3_g5_g4_weakest_boundary_artifact_is_not_enough_without_matching_record`
- `test_layer3_g5_g4_handoff_pass_with_blockers_blocks_requested_scope`
- `test_layer3_g5_g4_grounded_contract_duplicates_do_not_inflate_evidence`
- `test_layer3_g5_g1_observed_but_uncertain_binding_limits_conversion_scope`
- `test_layer3_g5_g1_source_contract_hash_and_observed_time_required_for_scope_join`
- `test_layer3_g5_g1_may_not_use_for_denials_are_preserved`
- `test_layer3_g5_g2_design_record_alias_requires_explicit_normalization`
- `test_layer3_g5_g2_empty_s2_replay_key_refs_block_grounded_limited`
- `test_layer3_g5_g2_source_contract_ref_mismatch_blocks_scope_join`
- `test_layer3_g5_g3_duplicate_source_lineage_refs_do_not_inflate_independence`
- `test_layer3_g5_independence_adapter_uses_existing_collapse_dimensions`
- `test_layer3_g5_gl_pass_with_reissue_required_narrows_or_blocks_legal_scope`

Acceptance:

- G5 can build a dependency snapshot from current repo artifacts.
- A missing G4 handoff or missing G1 readiness produces typed issue codes.
- No upstream builders are rerun in the conversion decision path.
- Current green G2/G3 artifacts remain evidence inputs only; they do not
  override a blocked or missing G4 design-level promotion record.
- Scope join must prove actual ref compatibility. Aliases are allowed only when
  an explicit alias-resolution record explains the normalization.

### Task 2 - Pinned Case Input Bundle

Implement:

- `Layer3G5PinnedCaseInputBundle` for the full W12.D pinned case.
- `Layer3G5ComposedLoopCompletenessGate` over S4-S14 summaries and per-case
  blocks; S14 must be present and compatible with the declared grounded scope.
  In the W12.D hook path, the gate must read per-case blocks because
  corpus-level S4-S14 summaries are built later in the current report builder.
- Exact W12.D per-case block extraction for `s4_epistemic_regime`,
  `s5_coupling_composition`, `s6_blind_spot_firewalls`, `s7_delegation`,
  `s8_value_choice`, `s9_projection_lowering`, `s10_outcome_prediction`,
  `s11_predictive_knowledge`, `s12_resource_economics`,
  `s13_post_deploy_accountability`, and `s14_universality_assurance`.
- Resolver that accepts an explicit W12.D full report payload or builds a
  deterministic local report for tests/readiness, but rejects manifest-only
  evidence and stale build-cache reports for conversion.
- Extraction of S2 design search, S4-S14 summaries, G0/G1/G2/G3 gates,
  typed blockers, authority outcomes, replay refs, and case digest.
- Extraction of S2 `status`, `acquisition_branch_state`,
  `design_record.firewall_status`, constraint-store statuses, S7 delegation
  refs, S12 growth entries, and S14 pending-sealed/declared-envelope fields.
- The W12.D freshness path must use
  `run_w12d_universal_outcome_corpus(...)` or call
  `build_w12d_universal_outcome_corpus_report(...)` with keyword-only
  `case_results`; G5 tests must not encode a positional repo-root call that the
  builder does not support.
- Non-pinned case rejection.

Tests:

- `test_layer3_g5_pinned_case_bundle_requires_full_w12d_payload`
- `test_layer3_g5_w12d_bundle_extracts_exact_s4_s14_case_keys`
- `test_layer3_g5_composed_loop_completeness_requires_s4_s14_and_s14`
- `test_layer3_g5_s14_missing_or_failed_blocks_conversion`
- `test_layer3_g5_manifest_only_w12d_input_fails_closed`
- `test_layer3_g5_stale_build_cache_w12d_input_fails_closed`
- `test_layer3_g5_w12d_hook_uses_per_case_s4_s14_before_corpus_summaries`
- `test_layer3_g5_s2_acquisition_required_routes_to_abstention_or_blocker`
- `test_layer3_g5_design_record_firewall_warn_limit_block_statuses_compose_before_conversion`
- `test_layer3_g5_constraint_store_block_status_blocks_or_limits_conversion`
- `test_layer3_g5_p26_resolver_reads_s7_delegation_record_ref_not_only_generic_human_refs`
- `test_layer3_g5_s12_growth_entry_demand_act_and_envelope_delta_are_reused`
- `test_layer3_g5_s14_pending_sealed_limits_universality_claim_but_not_declared_envelope_ref`
- `test_layer3_g5_w12d_fresh_payload_builder_uses_supported_signature`
- `test_layer3_g5_non_pinned_case_widening_attempt_fails_closed`
- `test_layer3_g5_pinned_case_digest_is_replayable`

Acceptance:

- Pinned case input has stable digest and replay refs.
- S4-S14/S14 completeness is a hard conversion gate.
- Manifest-only W12.D input cannot produce conversion.
- A renamed, missing, or report-summary-only S4-S14 field produces a typed G5
  blocker instead of a silent partial conversion.
- S2/S7/S12/S14 extraction produces typed blockers for missing fields whose
  current location is non-obvious.

### Task 3 - Conversion Eligibility and Status Composition

Implement:

- Grounded result evidence set with exact upstream contract refs.
- Upstream scope-join matrix that links G1 source contracts, G2 forecast
  handoffs, G3 proof records, optional GL legal refs, and G4 promotion records
  to the same case/design/claim-family/envelope tuple.
- Effective evidence independence record for `grounded_limited`, including
  collapse refs for shared source, method, lineage, prompt, institution, or
  assumptions.
- Useful-design metric eligibility join that preserves W12.D
  runtime-vs-expert metric separation and joins to the W11.C useful-design gate
  when the conversion claims bounded useful-design credit.
- Conversion eligibility ledger and status composition ledger.
- Weakest-boundary composition over S4-S14, G1, G2, G3, GL, G4,
  search-health, and human-accountability inputs, with `weakest_boundary_reason`
  preserved in the status composition ledger.
- Criteria for `grounded_limited`, `grounded_abstention`, and
  `unchanged_blocker`.
- Mixed-status composition rules for upstream `warn`, `partial`, `contested`,
  `review_required`, `limited`, and `near_binding` inputs.
- Guard that source-data promotion alone cannot become causal/effect/legal
  conversion.
- Guard that source-data promotion alone cannot become `grounded_limited`
  useful-design credit.
- Guard that `grounded_limited` requires G2/G3 design-level evidence, not only
  G1/G4 source truth.
- Guard that `grounded_limited` conversion classification does not itself grant
  useful-design metric credit without the G5 useful-design eligibility join and
  status composition.
- Guard that G2/G3 green artifacts do not override the current blocked G4
  causal/design promotion record.
- Guard that GL `pass` with `reissue_required`, unresolved reference resolution,
  or applicability failure narrows or blocks legal/mandate conversion scope.
- Guard that GL legal requirement artifact refs do not override
  applicability/reference/amendment/mandate compatibility blockers.
- Guard that G1 `observed_but_uncertain` source contracts cannot become claim
  authority, adapter promotion, or useful-design evidence without downstream
  scope-matched conversion support.
- Guard that S2 `acquisition_required` and `bridge_missing` block or narrow
  conversion unless an acquisition branch is explicitly resolved.
- Guard that S14 `grounded_authority_status=pass` does not override
  `pending_sealed`/`not_tested` for universality.
- Guard that `grounded_abstention` requires measured recall/freshness and cannot
  mask search ceiling.
- Guard that high-stakes, value-laden, irreversible, or out-of-envelope
  conversion scope requires concrete S7/P26 responsibility-integrity refs, or
  narrows/blocks conversion.

Tests:

- `test_layer3_g5_source_only_promotion_cannot_claim_causal_design`
- `test_layer3_g5_source_only_promotion_cannot_claim_grounded_limited`
- `test_layer3_g5_grounded_limited_requires_g2_g3_design_support`
- `test_layer3_g5_does_not_treat_g4_pass_as_design_level_promotion`
- `test_layer3_g5_g2_g3_green_artifacts_do_not_override_blocked_g4_design_scope`
- `test_layer3_g5_gl_pass_with_reissue_required_narrows_or_blocks_legal_scope`
- `test_layer3_g5_grounded_limited_requires_upstream_scope_join`
- `test_layer3_g5_unrelated_green_g2_g3_artifacts_do_not_satisfy_conversion`
- `test_layer3_g5_effective_independence_missing_blocks_grounded_limited`
- `test_layer3_g5_raw_ref_dedup_without_independence_map_blocks_grounded_limited`
- `test_layer3_g5_grounded_limited_requires_useful_design_metric_eligibility_join_for_credit`
- `test_layer3_g5_expert_useful_design_ceiling_is_not_runtime_credit`
- `test_layer3_g5_grounded_limited_requires_scope_covering_evidence`
- `test_layer3_g5_grounded_abstention_requires_search_recall_and_freshness`
- `test_layer3_g5_search_ceiling_is_not_domain_ceiling`
- `test_layer3_g5_status_composition_does_not_add_uncontrolled_w12d_outcome`
- `test_layer3_g5_conversion_cannot_outrank_weakest_boundary`
- `test_layer3_g5_mixed_upstream_statuses_narrow_or_block_conversion`
- `test_layer3_g5_high_stakes_scope_requires_human_decision_record_or_narrows`
- `test_layer3_g5_g1_observed_but_uncertain_cannot_be_claim_authority`
- `test_layer3_g5_s2_bridge_missing_blocks_or_limits_conversion`
- `test_layer3_g5_gl_requirement_artifact_does_not_override_applicability_fail`
- `test_layer3_g5_gl_mandate_compatibility_only_blocks_mandate_conversion`
- `test_layer3_g5_s14_grounded_authority_pass_does_not_override_pending_sealed_gate`
- `test_layer3_g5_g3_identified_proof_is_not_claim_authority`

Acceptance:

- Current G4 source-only promotion does not overclaim.
- Current G4 source-only promotion cannot be the only evidence for
  `grounded_limited`.
- Current persisted artifacts are expected to produce grounded abstention or
  unchanged blocker unless a fixture supplies a matching design-level G4
  promotion plus scope-joined G2/G3 evidence.
- The valid fixture reaches either `typed_blocker -> grounded_limited` or
  `typed_blocker -> grounded_abstention` with explicit evidence and limitations.
- The blocked causal probe remains a blocker/limitation.
- Status composition preserves weakest-boundary and mixed-status reasons instead
  of flattening them into a cleaner conversion label.
- Current repo artifacts should naturally explain why the first G5 path is
  source-bounded/abstention/unchanged-blocker unless fixtures add true
  scope-joined design-level promotion.

### Task 4 - Envelope Expansion and Health Metric

Implement:

- `Layer3G5EnvelopeExpansionDelta`.
- `Layer3G5DemandPullAttemptRecord` for T6, with S3 demand-pull refs, S12
  reuse/acquisition refs, S12 `demand_act_refs`, `growth_entries`,
  VOI/explore-exploit refs where available, accountable-principal refs, and
  attempted grounding path refs.
- Health TOML with `envelope-expansion-rate`, trend, numerator/denominator,
  effort refs, demand-pull refs, search health refs, and conversion reason
  taxonomy.
- Health snapshot for all five constitution metrics: G5-owned
  `envelope-expansion-rate`, plus consumed upstream `adapter-semantic-loss`,
  `governance-throughput`, `demand-pull-vs-abstention`, and
  `search-recall@known-seeds + index-staleness` statuses. G5 records unresolved
  or stale upstream readings as blockers/limitations instead of recomputing them.
- Link to S12 envelope-growth refs where available; otherwise record a bounded
  G5 envelope delta without claiming S12 authority.
- S12 growth/demand evidence requires `demand_act_ref`,
  `certified_envelope_delta_ref`, and reuse/acquisition refs to align. G5 must
  distinguish "no demand evidence" from "demand evidence exists but does not
  join to this scope".

Tests:

- `test_layer3_g5_envelope_expansion_delta_records_first_reading`
- `test_layer3_g5_grounded_abstention_requires_demand_pull_attempt_refs`
- `test_layer3_g5_demand_pull_resolves_from_s12_case_signals`
- `test_layer3_g5_flat_expansion_records_reason_not_metric_failure`
- `test_layer3_g5_health_snapshot_carries_all_five_constitution_metrics`
- `test_layer3_g5_stale_upstream_health_reading_blocks_or_limits_conversion`
- `test_layer3_g5_missing_envelope_delta_blocks_readiness`
- `test_layer3_g5_s12_growth_without_envelope_delta_cannot_count_expansion`
- `test_layer3_g5_s12_demand_act_ref_missing_blocks_demand_pull_credit`

Acceptance:

- Health delta distinguishes expanding, flat/domain-ceiling, flat/search-ceiling,
  and unchanged-blocker.
- Abstention or non-conversion cannot pass as honest when demand-pull attempt
  refs are absent.
- Health delta is not a one-metric report; it carries G5's direct envelope
  reading plus bounded upstream health readings used in the conversion decision.

### Task 5 - W12.D Consumer Gate

Implement:

- Lazy import of `build_g5_w12d_consumer_gate` inside
  `run_universal_outcome_corpus.py`.
- `_with_layer3_g5_conversion_gate(...)` after G3 and before summary.
- `_layer3_g5_summary(...)` with G5-owned keys.
- The hook must not require corpus-level S4-S14 summaries that are built after
  `_summary(cases)` today; if implementation changes that order, add regression
  tests proving existing S4-S14 summary keys and W12.D metrics remain stable.
- The hook must not assume G3 analytics-search summary is inside W12.D
  `summary`; current G3 summary is a top-level report field.
- Top-level `grounded_conversion_count` should use G5 counts when G5 routed;
  preserve G0 pre-G5 grounding counts under G0-specific keys.
- Useful-design summary updates must preserve W12.D's runtime/expert split:
  runtime and legacy useful-design counts may change only through the G5
  eligibility join, while expert ceiling and alignment keys retain their
  original meanings.
- Per-case `layer3_g5_conversion_gate` for pinned case only.
- No erasure of `layer3_g0_grounding_gate`, `layer3_g1_grounding_gate`,
  `layer3_g2_forecast_gate`, or `layer3_g3_analytics_search_gate`.
- G5 emits an overlay/gate only; it must not mutate pre-G5 W12.D closed-case
  replay payloads, canonical pre-G5 outcomes, or historical G0/G1/G2/G3 gates.

Tests:

- `test_w12d_layer3_g5_gate_is_inserted_after_g3_before_summary`
- `test_w12d_layer3_g5_handles_g3_summary_top_level_not_inside_summary`
- `test_w12d_layer3_g5_emits_pinned_case_conversion_classification`
- `test_w12d_layer3_g5_grounded_conversion_count_is_g5_owned`
- `test_w12d_layer3_g5_does_not_overwrite_g0_g1_g2_g3_histories`
- `test_w12d_layer3_g5_preserves_pre_g5_closed_case_replay`
- `test_w12d_layer3_g5_grounded_abstention_does_not_count_as_useful_design`
- `test_w12d_layer3_g5_grounded_limited_counts_only_with_status_composition`
- `test_w12d_layer3_g5_preserves_runtime_vs_expert_useful_design_metrics`

Acceptance:

- W12.D report exposes G5 conversion gate and summary.
- Existing W12.D useful-design and typed-blocker tests continue to pass with
  updated G5-aware expectations.

### Task 6 - Surfaces, Generated Artifacts, Readiness CLI, and Docs

Implement:

- Readiness CLI write/read path for all G5 artifacts.
- Mirror the G4 readiness scaffold: exact expected artifact set, `--write`,
  manifest-runtime drift check, generated-artifacts registration, inventory
  marker, docs/reference/public-surface marker, runtime surface validation,
  conformance negatives, and performance contract.
- Generated-artifacts registration.
- Generated-artifacts registration must include owner, lifecycle, generator,
  verifier, stale-output behavior, regenerate/check commands, exact outputs, and
  drift gate, matching the existing family contract style.
- Policy Design Case inventory entries.
- Public-surface reference.
- G5 reference doc.
- Conversion-route contract registry and registry/ratchet delta.
- Projection boundary checks using existing
  `assert_policy_design_projection_not_authority(...)` and S10-S14 projection
  consumer-contract verifiers where G5 emits audience projections.

Tests:

- `test_layer3_g5_readiness_passes_for_persisted_runtime_bundle`
- `test_layer3_g5_readiness_mirrors_g4_exact_artifact_and_drift_scaffold`
- `test_layer3_g5_write_path_must_include_every_expected_artifact`
- `test_layer3_g5_generated_artifacts_and_inventory_are_registered`
- `test_layer3_g5_public_surface_denies_raw_payload_and_downstream_authority`
- `test_layer3_g5_uses_conversion_route_registry_not_adapter_registry`
- `test_layer3_g5_public_projection_reuses_runtime_projection_authority_checks`
- `test_layer3_g5_s12_s14_projection_contracts_preserve_limits`

Acceptance:

- `--write` refreshes every G5 artifact.
- Persisted readiness manifest matches runtime bundle and detects drift.

### Task 7 - Conformance, Performance, and Closeout Verification

Implement:

- Conformance negative suite with expected issue codes.
- Performance/scaling contract: bounded artifact reads, no unbounded repo scans,
  no upstream bundle rerun in request path, lazy W12.D import.
- Closed-case replay integrity check proving G5 writes overlay artifacts and
  G5-owned summaries only.
- Closeout-boundary negative proving G5 readiness, scorecard, projection, package,
  and public-export surfaces may be observed by closeout readers but cannot
  substitute for module-owned closeout evidence.
- Candidate-firewall negative proving `candidate_unverified` or
  `rejected_speculation` refs in G5 projection text cannot satisfy conversion,
  limitation, blocker, claim, or projection authority slots.
- P09 check proving G5 does not emit unowned warning-like soft gates; every
  unresolved caveat is either an existing owned warning lifecycle ref, a
  limitation, or a blocker.
- Final readiness report with issue-code dictionary.

Required commands:

```bash
cd policy-engine
uv run ruff check src/polisyos/runtime/quality/proving_ground/proving_ground_conversion.py tools/quality/validation/check_policy_design_case_layer3_g5_readiness.py tools/quality/validation/run_universal_outcome_corpus.py tests/unit/runtime/quality/test_layer3_g5_proving_ground_conversion.py tests/repo_quality/tools/test_policy_design_case_layer3_g5_readiness.py tests/repo_quality/tools/test_policy_design_case_layer3_g5_readiness_cli.py tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py
uv run pytest tests/unit/runtime/quality/test_layer3_g5_proving_ground_conversion.py
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer3_g5_readiness.py
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer3_g5_readiness_cli.py
uv run pytest tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py
uv run python tools/quality/validation/check_policy_design_case_layer3_g5_readiness.py --repo-root . --write --output-format json
uv run python tools/quality/validation/check_policy_design_case_layer3_g5_readiness.py --repo-root . --output-format json
uv run polisyos-tools architecture guardrails check
```

Acceptance:

- G5 readiness status is `pass`.
- W12.D emits the pinned-case G5 conversion gate.
- The conversion is replayable and authority-bounded.
- Negative fixtures pass and issue codes are stable.
- Architecture/generated-artifact/public-surface registrations pass guardrails.
- No pre-G5 replay payload, canonical pre-G5 outcome, or historical Layer 3 gate
  is mutated by G5.
- No G5-local warning bypass can affect conversion or useful-design credit.

## Readiness Manifest Keys

Minimum readiness summary keys:

- `status`
- `schema_version`
- `rule_version`
- `g5_dependency_readiness_status`
- `g5_g0_dependency_status`
- `g5_g1_dependency_status`
- `g5_g2_dependency_status`
- `g5_g3_dependency_status`
- `g5_gl_dependency_status`
- `g5_g4_dependency_status`
- `g5_dependency_manifest_key_resolution_status`
- `g5_g1_grounding_status`
- `g5_g1_source_contract_hash_status`
- `g5_g1_observed_through_status`
- `g5_g1_may_not_use_for_status`
- `g5_lineage_deduplication_status`
- `g5_search_recall_status`
- `g5_index_freshness_status`
- `g5_pinned_case_input_status`
- `g5_w12d_case_block_index_status`
- `g5_w12d_s4_s14_case_key_status`
- `g5_w12d_payload_status`
- `g5_w12d_payload_freshness_status`
- `g5_w12d_g3_summary_location_status`
- `g5_s2_design_search_status`
- `g5_s2_acquisition_branch_status`
- `g5_design_record_firewall_status`
- `g5_constraint_store_status`
- `g5_s7_delegation_record_resolution_status`
- `g5_s12_growth_entry_status`
- `g5_s12_certified_envelope_delta_status`
- `g5_s14_pending_sealed_status`
- `g5_s14_declared_envelope_status`
- `g5_composed_loop_completeness_status`
- `g5_s14_gate_status`
- `g5_g4_handoff_resolution_status`
- `g5_g4_handoff_blocker_status`
- `g5_g4_promotion_record_resolution_status`
- `g5_g4_design_scope_promotion_status`
- `g5_g4_registration_dependency_status`
- `g5_g4_grounded_contract_dedup_status`
- `g5_gl_reissue_status`
- `g5_gl_applicability_status`
- `g5_gl_requirement_artifact_status`
- `g5_gl_mandate_compatibility_status`
- `g5_gl_reference_resolution_status`
- `g5_gl_amendment_lineage_status`
- `g5_g2_design_record_alias_resolution_status`
- `g5_g2_s2_replay_key_ref_status`
- `g5_g2_source_contract_join_status`
- `g5_g3_proof_authority_boundary_status`
- `g5_upstream_scope_join_status`
- `g5_weakest_boundary_status`
- `g5_weakest_boundary_reason`
- `g5_mixed_status_composition_status`
- `g5_governed_promotion_input_count`
- `g5_blocked_promotion_input_count`
- `g5_grounded_evidence_ref_count`
- `g5_effective_evidence_independence_status`
- `g5_evidence_independence_map_status`
- `g5_useful_design_metric_eligibility_status`
- `g5_runtime_vs_expert_metric_separation_status`
- `g5_conversion_record_count`
- `g5_conversion_outcome`
- `g5_grounded_limited_count`
- `g5_grounded_abstention_count`
- `g5_unchanged_blocker_count`
- `g5_grounded_conversion_count`
- `g5_useful_design_credit_count`
- `g5_grounded_abstention_useful_design_credit_count`
- `g5_status_composition_status`
- `g5_w12d_consumer_gate_status`
- `g5_demand_pull_attempt_status`
- `g5_envelope_expansion_status`
- `g5_envelope_expansion_rate`
- `g5_adapter_semantic_loss_status`
- `g5_governance_throughput_status`
- `g5_demand_pull_vs_abstention_status`
- `g5_dependency_health_metric_snapshot_status`
- `g5_domain_ceiling_count`
- `g5_search_ceiling_repair_required_count`
- `g5_closed_case_replay_integrity_status`
- `g5_warning_lifecycle_status`
- `g5_projection_boundary_status`
- `g5_closeout_surface_substitution_status`
- `g5_candidate_firewall_status`
- `g5_public_surface_status`
- `g5_public_export_hook_status`
- `g5_conformance_status`
- `g5_conformance_negative_count`
- `g5_conformance_negative_pass_count`
- `g5_registry_ratchet_delta_status`
- `g5_generated_artifacts_registration_status`
- `g5_inventory_surface_status`
- `g5_reference_docs_status`
- `g5_performance_contract_status`
- `issue_codes`

## Issue Codes

Minimum issue-code dictionary:

- `layer3_g5_g0_dependency_not_ready`
- `layer3_g5_g1_dependency_not_ready`
- `layer3_g5_g4_dependency_not_ready`
- `layer3_g5_context_dependency_missing`
- `layer3_g5_dependency_readiness_snapshot_missing`
- `layer3_g5_dependency_manifest_status_key_missing`
- `layer3_g5_dependency_manifest_status_overclaimed`
- `layer3_g5_g2_g3_artifact_without_g4_design_promotion`
- `layer3_g5_g4_registration_unknown_blocks_readiness`
- `layer3_g5_g1_observed_but_uncertain_overclaimed`
- `layer3_g5_g1_source_contract_hash_missing`
- `layer3_g5_g1_observed_time_missing`
- `layer3_g5_g1_may_not_use_for_dropped`
- `layer3_g5_duplicate_lineage_ref_inflates_independence`
- `layer3_g5_duplicate_source_lineage_ref_inflates_independence`
- `layer3_g5_pinned_case_missing`
- `layer3_g5_non_pinned_case_widening_attempt`
- `layer3_g5_w12d_full_payload_missing`
- `layer3_g5_w12d_manifest_only_not_payload`
- `layer3_g5_w12d_build_cache_not_source_of_truth`
- `layer3_g5_w12d_s4_s14_case_key_missing`
- `layer3_g5_w12d_g3_summary_location_unhandled`
- `layer3_g5_s4_s14_composed_loop_incomplete`
- `layer3_g5_s14_gate_missing_or_failed`
- `layer3_g5_s2_acquisition_required_unresolved`
- `layer3_g5_s2_bridge_missing_unresolved`
- `layer3_g5_design_record_firewall_status_flattened`
- `layer3_g5_constraint_store_block_ignored`
- `layer3_g5_s7_delegation_record_ref_unresolved`
- `layer3_g5_s12_growth_without_envelope_delta`
- `layer3_g5_s12_demand_act_ref_missing`
- `layer3_g5_s14_pending_sealed_overclaimed`
- `layer3_g5_s14_grounded_authority_status_overclaimed`
- `layer3_g5_source_design_record_unresolved`
- `layer3_g5_source_design_record_digest_missing`
- `layer3_g5_g4_handoff_missing`
- `layer3_g5_g4_handoff_authority_leak`
- `layer3_g5_g4_handoff_pass_with_blockers_overclaimed`
- `layer3_g5_g4_weakest_boundary_record_mismatch`
- `layer3_g5_g4_grounded_contract_duplicate_inflates_evidence`
- `layer3_g5_promotion_record_missing`
- `layer3_g5_no_governed_promotion_record`
- `layer3_g5_g4_pass_without_design_scope`
- `layer3_g5_blocked_promotion_used_as_conversion`
- `layer3_g5_promotion_only_conversion`
- `layer3_g5_source_only_promotion_overclaims_causal_design`
- `layer3_g5_source_only_promotion_overclaims_grounded_limited`
- `layer3_g5_upstream_scope_join_missing`
- `layer3_g5_g2_g3_scope_mismatch`
- `layer3_g5_g4_scope_mismatch`
- `layer3_g5_weakest_boundary_missing`
- `layer3_g5_conversion_exceeds_weakest_boundary`
- `layer3_g5_mixed_status_composition_missing`
- `layer3_g5_contested_status_flattened`
- `layer3_g5_review_required_status_flattened`
- `layer3_g5_partial_status_flattened`
- `layer3_g5_grounded_contract_ref_missing`
- `layer3_g5_missing_g1_grounded_source_contract`
- `layer3_g5_missing_g2_forecast_support`
- `layer3_g5_missing_g2_calibration_ref`
- `layer3_g5_g2_design_record_ref_unresolved`
- `layer3_g5_g2_s2_replay_key_ref_missing`
- `layer3_g5_g2_source_contract_ref_mismatch`
- `layer3_g5_missing_g3_proof_record`
- `layer3_g5_g3_proof_status_overclaimed`
- `layer3_g5_g3_may_not_use_for_dropped`
- `layer3_g5_grounded_limited_without_g2_g3_design_support`
- `layer3_g5_missing_gl_legal_authority`
- `layer3_g5_gl_pass_with_reissue_required`
- `layer3_g5_gl_reissue_required_blocks_conversion`
- `layer3_g5_gl_reissue_scope_unresolved`
- `layer3_g5_gl_applicability_fail_blocks_conversion`
- `layer3_g5_gl_requirement_artifact_missing`
- `layer3_g5_gl_requirement_artifact_overrides_applicability`
- `layer3_g5_gl_mandate_compatibility_only_blocks_conversion`
- `layer3_g5_gl_reference_resolution_unresolved`
- `layer3_g5_gl_amendment_lineage_reissue_required`
- `layer3_g5_effective_independence_missing`
- `layer3_g5_evidence_independence_map_missing`
- `layer3_g5_raw_ref_dedup_used_as_independence`
- `layer3_g5_useful_design_metric_eligibility_join_missing`
- `layer3_g5_expert_adjudication_gate_overclaimed`
- `layer3_g5_expert_useful_design_ceiling_used_as_runtime_credit`
- `layer3_g5_search_recall_seed_miss_blocks_abstention`
- `layer3_g5_stale_index_blocks_abstention`
- `layer3_g5_search_ceiling_not_domain_ceiling`
- `layer3_g5_grounded_abstention_without_evidence`
- `layer3_g5_grounded_abstention_without_demand_pull_attempt`
- `layer3_g5_demand_pull_ref_unresolved`
- `layer3_g5_human_decision_record_required`
- `layer3_g5_responsibility_integrity_missing`
- `layer3_g5_grounded_abstention_counts_as_useful_design`
- `layer3_g5_grounded_limited_without_status_composition`
- `layer3_g5_uncontrolled_w12d_outcome_status`
- `layer3_g5_useful_design_rate_floor_relaxed`
- `layer3_g5_envelope_expansion_delta_missing`
- `layer3_g5_envelope_expansion_reason_missing`
- `layer3_g5_w12d_consumer_gate_missing`
- `layer3_g5_grounded_conversion_count_still_g0_only`
- `layer3_g5_g0_g1_g2_g3_history_overwritten`
- `layer3_g5_pre_g5_closed_case_replay_mutated`
- `layer3_g5_unowned_warning_lifecycle`
- `layer3_g5_warning_used_as_conversion_pass`
- `layer3_g5_upstream_health_metric_missing`
- `layer3_g5_stale_upstream_health_metric`
- `layer3_g5_closeout_authority_leak`
- `layer3_g5_production_authority_leak`
- `layer3_g5_publication_authority_leak`
- `layer3_g5_claim_authority_leak`
- `layer3_g5_public_raw_payload_leak`
- `layer3_g5_public_export_hook_overclaimed`
- `layer3_g5_projection_mints_authority`
- `layer3_g5_projection_omits_required_deny_list`
- `layer3_g5_closeout_surface_substitution_attempt`
- `layer3_g5_candidate_unverified_used_as_authority`
- `layer3_g5_rejected_speculation_used_as_authority`
- `layer3_g5_arbitrary_request_attempt`
- `layer3_g5_g7_widening_attempt`
- `layer3_g5_registry_ratchet_delta_missing`
- `layer3_g5_generated_artifacts_family_missing`
- `layer3_g5_inventory_surface_missing`
- `layer3_g5_reference_index_missing`
- `layer3_g5_conversion_route_contract_registry_missing`
- `layer3_g5_manifest_runtime_drift`
- `layer3_g5_persisted_artifact_missing`
- `layer3_g5_import_laziness_violation`
- `layer3_g5_unbounded_artifact_scan`
- `layer3_g5_upstream_builder_rerun_in_request_path`

## Acceptance Checklist

- [x] G5 module exists with strict DTOs and stable issue-code dictionary.
- [x] G5 readiness CLI exists and supports write/read validation.
- [x] G5 readiness CLI mirrors the G4 exact-artifact/write/drift/registration/
      docs/surface/conformance scaffold instead of inventing a new readiness
      pattern.
- [x] All G5 persisted artifacts are generated and registered.
- [x] G5 reads slice-specific G2/G3/GL/G4 readiness keys and does not trust a
      generic top-level status.
- [x] G1 `observed_but_uncertain` source contracts preserve source hash,
      observation time, coverage period, lineage, uncertainty, and deny-list,
      and cannot be promoted to claim/useful-design authority by G5.
- [x] Duplicate G1/G3/G4 source, lineage, grounded-contract, and certificate
      refs are deduped before evidence independence or strength is calculated.
- [x] Pinned case input bundle uses full W12.D payload, not manifest-only input.
- [x] Pinned case bundle extracts the exact W12.D per-case S4-S14 keys used by
      the current builder.
- [x] Pinned case bundle extracts S2 acquisition status, bridge state,
      design-record firewall statuses, constraint-store rows, S7 delegation
      refs, S12 growth refs, and S14 pending-sealed/declared-envelope fields.
- [x] S4-S14/S14 composed-loop completeness is a hard conversion gate.
- [x] S2 `acquisition_required`/`bridge_missing` becomes a visible
      abstention/blocker reason rather than a hidden non-closure.
- [x] G4 handoff is consumed as promotion-state input only, and G4 promotion is
      resolved per record/scope/design digest rather than from a single summary
      or weakest-boundary artifact.
- [x] G4 handoff `pass` with blocker refs does not clear the blocked requested
      scope.
- [x] G4 blocked promotion is preserved as blocker/limitation.
- [x] G4 registration/docs/public-surface `unknown` cannot satisfy G5 external
      surface readiness.
- [x] Source-only promotion cannot overclaim causal/effect/legal design.
- [x] Source-only promotion cannot be the only evidence for
      `grounded_limited`.
- [x] `grounded_limited` requires G2/G3 design-level support and effective
      evidence independence.
- [x] Effective independence uses the existing independence-map collapse
      semantics or a validated G5 adapter, not only exact-ref dedupe.
- [x] Useful-design credit requires a G5 useful-design metric eligibility join
      and preserves W12.D runtime-vs-expert metric separation.
- [x] Expert useful-design ceiling and W11.C useful-design eligibility are not
      treated as claim, closeout, legal, or conversion authority.
- [x] Green G2/G3 artifacts do not override a blocked or absent G4 design-level
      promotion record.
- [x] G2 design-record aliases, S2 replay-key refs, calibration refs,
      uncertainty refs, and source-contract refs must join explicitly or block.
- [x] G3 `identified` proof is proof-validity input only and cannot become claim
      authority.
- [x] GL `pass` with reissue/reference/applicability limits narrows or blocks
      legal/mandate conversion scope.
- [x] GL requirement artifacts are reused as requirement inputs, but cannot
      override applicability fail, reference-resolution gaps, amendment reissue,
      or mandate compatibility-only status.
- [x] Conversion cannot outrank the weakest S4-S14/G1/G2/G3/GL/G4/search-health
      or human-accountability boundary.
- [x] Mixed upstream statuses (`warn`, `partial`, `contested`,
      `review_required`, `limited`, `near_binding`) narrow or block conversion
      instead of being flattened.
- [x] Conversion record is `typed_blocker -> grounded_limited`,
      `typed_blocker -> grounded_abstention`, or `unchanged_blocker`.
- [x] Grounded abstention requires recall/freshness and cannot hide search
      ceiling.
- [x] Grounded abstention requires demand-pull attempt refs and cannot hide
      honesty inertia.
- [x] Envelope-expansion-rate is recorded with reason taxonomy, and the G5 health
      snapshot carries all five constitution health metrics.
- [x] High-stakes, value-laden, irreversible, or out-of-envelope scope has
      concrete S7/P26 responsibility-integrity refs, or the conversion is
      narrowed/blocked.
- [x] S14 `pending_sealed`/`not_tested` permits declared-envelope projection
      only and blocks universality/aggregate claim language.
- [x] W12.D emits `layer3_g5_conversion_gate` after G3.
- [x] W12.D G5 hook handles current G3 summary location outside W12.D
      `summary`.
- [x] G5 preserves pre-G5 closed-case replay and historical G0/G1/G2/G3 gate
      payloads.
- [x] Top-level grounded conversion summary is G5-owned after G5 routes.
- [x] W12.D useful-design metrics are not optimized by lowering floors.
- [x] G5 has no unowned local soft-warning lifecycle; unresolved caveats are
      blockers, limitations, or existing owned warning refs.
- [x] PUBLIC/REVIEWER/EXPERT/MACHINE surface exists and is authority-bounded.
- [x] G5 public/reviewer/expert/machine projections reuse runtime projection
      boundary checks and S10-S14 projection consumer contracts where relevant.
- [x] G5 readiness/scorecard/projection/package/public-export surfaces cannot
      substitute for closeout reader evidence.
- [x] G5 candidate/hypothesis refs remain behind the candidate firewall;
      unverified or rejected candidates cannot satisfy conversion authority.
- [x] Negative fixtures pass and cover laundering, false abstention, status,
      public payload, and scope-widening failures.
- [x] `ruff check` passes for touched Python files.
- [x] Readiness CLI passes after `--write`.

## Non-Negotiables

- G5 conversion is not G4 promotion. Promotion is an input; conversion is a
  composed W12.D/Layer 3 result.
- G4 `pass` is not design-level conversion readiness unless the matched
  promotion record covers the requested design scope.
- A source-only promotion cannot become causal/effect usefulness.
- A source-only promotion cannot become `grounded_limited` useful-design credit.
- G1 `observed_but_uncertain` is bounded substrate evidence, not claim,
  adapter-promotion, or useful-design authority.
- Duplicate refs never create independent evidence.
- Exact-ref dedupe is not enough for `grounded_limited`; G5 must preserve
  collapse reasons over lineage, method, assumption, and shared-failure
  dimensions.
- `grounded_limited` needs G2/G3 design evidence, S4-S14/S14 completeness, and
  effective independence; G1/G4 alone is not enough.
- `grounded_limited` conversion classification is not automatically
  useful-design metric eligibility.
- Expert useful-design ceiling is not runtime useful-design credit.
- G2/G3 design evidence must scope-join by case, design record/replay key,
  source contract, claim family, envelope, and promotion scope; green artifacts
  alone are not enough.
- `grounded_limited` cannot outrank the weakest grounded boundary, and mixed
  upstream statuses must remain visible in the status composition ledger.
- S2 `acquisition_required` and `bridge_missing` are not closure.
- S14 `pending_sealed` is not universality.
- A grounded abstention is valuable, but it is not useful-design credit.
- A grounded abstention without demand-pull attempt refs is honesty inertia, not
  closure.
- False abstention from bad search is a defect, not honesty.
- Do not add `grounded_limited` or `grounded_abstention` to W12.D closeout
  outcomes without explicit status-composition tests.
- Do not update `runtime_useful_design_rate` unless the conversion is
  `grounded_limited` and status composition permits bounded useful-design credit.
- Do not use expert useful-design ceiling, W11.C adjudication labels, or
  `useful_design_metric_eligibility` as conversion, claim, legal, closeout, or
  publication authority.
- Do not mutate pre-G5 W12.D replay or historical G0/G1/G2/G3 gate payloads; G5
  appends a replayable overlay.
- Do not let unowned G5 warning-like caveats pass as soft gates.
- Do not use W12.D manifest-only or readiness-summary-only evidence for
  conversion.
- Do not use GL `pass` to ignore legal reissue/reference/applicability blockers.
- Do not use a GL requirement artifact to ignore applicability, mandate, S6, or
  amendment/reference blockers.
- Do not use G4 handoff `pass` to ignore G4 handoff blocker refs.
- Do not inherit G4 external-surface readiness when G5 generated artifacts,
  inventory, docs, public-surface marker, or drift checks are missing.
- Do not use G2/G3 green artifacts to bypass a blocked or absent G4 design-level
  promotion record.
- Do not create a G5 projection or public export path that fills authority slots
  or bypasses the runtime candidate firewall.
- Do not let G5 readiness, scorecard, projection, package, or public export
  substitute for closeout evidence.
- Do not route non-pinned cases in G5. That is G7.
- Do not route arbitrary requests in G5. That is G6.
- Do not relax floors to make the first conversion look good.
