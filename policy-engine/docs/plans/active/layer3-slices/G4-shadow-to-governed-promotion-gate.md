---
plan_id: layer3-g4-shadow-to-governed-promotion-gate
title: "G4 - Shadow-to-Governed Promotion Gate"
type: slice-plan
status: active
created: 2026-06-08
revised: 2026-06-08
slice: G4
depends_on:
  - docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md
  - docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
  - docs/plans/active/layer3-slices/G0-capability-data-inventory-triage-discipline-freeze.md
  - docs/plans/active/layer3-slices/G1-data-grounding-existing-assets-acquisition.md
  - docs/adr/0175-layer3-grounding-subordination-discipline.md
  - architecture/policy_design_case/layer3_g0_readiness_manifest.json
  - architecture/policy_design_case/layer3_discovery_search_discipline.json
  - architecture/policy_design_case/layer3_engineering_quality_check.json
  - architecture/policy_design_case/layer3_health_metric_ledgers.toml
  - architecture/policy_design_case/layer3_g1_readiness_manifest.json
  - architecture/policy_design_case/layer3_g1_grounded_source_contracts.json
  - architecture/policy_design_case/layer3_g1_adapter_admission_registry.json
  - architecture/policy_design_case/layer3_g1_conformance_report.json
  - architecture/policy_design_case/layer3_g1_coverage_lineage_abstention_surface.json
  - architecture/policy_design_case/layer2_s2_design_search_manifest.json
  - architecture/policy_design_case/layer2_s7_delegation_manifest.json
  - architecture/policy_design_case/wave12d_universal_outcome_corpus_run_manifest.json
  - architecture/generated_artifacts.toml
  - src/polisyos/runtime/quality/proving_ground/pre_adapter_grounding_inventory.py
  - src/polisyos/runtime/quality/proving_ground/substrate_grounding_search.py
  - src/polisyos/runtime/quality/authority.py
  - src/polisyos/runtime/quality/authority_reconciliation.py
  - src/polisyos/runtime/quality/adapter_contracts.py
  - src/polisyos/runtime/quality/claim_registry.py
  - src/polisyos/runtime/quality/semantic_binding.py
  - src/polisyos/runtime/quality/approval.py
  - src/polisyos/runtime/quality/human_review.py
  - src/polisyos/runtime/quality/design_axes/mandate_bounded_delegation.py
  - src/polisyos/runtime/quality/phase_barriers.py
  - src/polisyos/runtime/quality/scorecard.py
  - src/polisyos/runtime/quality/effective_mode.py
  - src/polisyos/runtime/quality/case_lifecycle.py
  - src/polisyos/runtime/quality/closeout_reader.py
  - src/polisyos/runtime/quality/public_export.py
  - src/polisyos/runtime/http/routes/control.py
  - src/polisyos/runtime/http/services/control/run_lifecycle.py
  - src/polisyos/pdc/_impl/layer2_readiness.py
  - src/polisyos/pdc/_impl/layer2_design_search.py
  - src/polisyos/pdc/_impl/compiler.py
  - tools/quality/validation/run_universal_outcome_corpus.py
context_inputs:
  - docs/plans/active/layer3-slices/G2-causal-forecast-search-engine.md
  - docs/plans/active/layer3-slices/G3-analytics-search-engine.md
  - docs/plans/active/layer3-slices/GL-legal-mandate-search-engine.md
  - architecture/policy_design_case/layer3_g2_readiness_manifest.json
  - architecture/policy_design_case/layer3_g2_grounded_forecast_handoffs.json
  - architecture/policy_design_case/layer3_g2_forecast_support_bindings.json
  - architecture/policy_design_case/layer3_g2_s10_prerequisite_bindings.json
  - architecture/policy_design_case/layer3_g2_conformance_report.json
  - architecture/policy_design_case/layer3_g3_readiness_manifest.json
  - architecture/policy_design_case/layer3_g3_proof_carrying_analytics_records.json
  - architecture/policy_design_case/layer3_g3_s11_predictive_posture_bindings.json
  - architecture/policy_design_case/layer3_g3_conformance_report.json
  - architecture/policy_design_case/layer3_gl_readiness_manifest.json
  - architecture/policy_design_case/layer3_gl_legal_authority_report.json
  - architecture/policy_design_case/layer3_gl_threshold_authority_records.json
  - architecture/policy_design_case/layer3_gl_mandate_authority_records.json
  - architecture/policy_design_case/layer3_gl_temporal_competence_records.json
  - architecture/policy_design_case/layer3_gl_amendment_lineage_records.json
  - architecture/policy_design_case/layer3_gl_reference_resolution_records.json
  - architecture/policy_design_case/layer3_gl_promotion_gate_handoff.json
  - architecture/policy_design_case/layer3_gl_g4_promotion_gate_consumer_gate.json
  - architecture/policy_design_case/layer3_gl_conformance_report.json
cells_closed: []
layer_cells_advanced:
  - layer3.g4_shadow_to_governed_promotion_gate
  - layer3.g4_dependency_artifact_resolution
  - layer3.g4_source_design_record_resolution
  - layer3.g4_promotion_input_set
  - layer3.g4_grounded_contract_set
  - layer3.g4_a_completeness_ledger
  - layer3.g4_weakest_boundary_composition
  - layer3.g4_human_decision_integrity_gate
  - layer3.g4_promotion_record
  - layer3.g4_closeout_consumer_gate
  - layer3.g4_pdc_compiler_consumer_gate
  - layer3.g4_g5_promotion_handoff
  - layer3.g4_governance_throughput_delta
  - layer3.g4_public_reviewer_expert_machine_surface
expected_open_cell_count: 0
floor_id: layer3_grounding_subordination
metric: layer3_g4_shadow_to_governed_promotion_gate
source_roadmap: docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md
constitution: docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
---

# G4 - Shadow-to-Governed Promotion Gate

## For agentic workers

This is an executable slice spec, not strategy. Follow it red-first. G4 builds
the D3.8 promotion gate: the only path that can convert a grounded B-side output
from `shadow` to `governed_promoted`.

G4 is not a new grounding/search engine. G1/G2/G3/GL have already produced
grounded contracts, handoffs, readiness manifests, and audit surfaces. G4 reads
those typed artifacts, checks A-completeness for the declared promotion scope,
composes the weakest authority boundary, routes high-stakes promotions through
S7/P26 human-decision integrity, and emits a typed `PromotionRecord`.

G4 should not rerun upstream Layer 3 builders in the request path. Its production
shape is a bounded resolver over persisted generated artifacts plus a G4 runtime
bundle. Tests may use builders as fixtures, and the G4 readiness CLI may compare
runtime-vs-persisted drift, but promotion decisions read the admitted artifact
surface that downstream governance will audit.

Promotion here means **governed**, not production, rollout, publication,
scorecard, approval, closeout, or useful-design credit. G4 is the lever G5 needs
to convert a proving-ground case. It does not itself count a case as converted.

Frontmatter note: `layer_cells_advanced` entries are Layer 3 plan-local progress
labels, not governed `cluster_ownership_map.toml` cells.

## Intro

The master plan's G4 contract is small and load-bearing:

```text
shadow DesignRecord / B output
-> grounded contract refs from G1 and any required G2/G3/GL claims
-> A-completeness check for the declared envelope region
-> P26/S7 human-decision integrity when high stakes or value-laden authority is requested
-> weakest-boundary composition
-> PromotionRecord(governed_promoted | promotion_blocked)
-> closeout/G5 consumer refs + all-audience promotion surface
```

Without this gate, even perfect grounding remains shadow. With a weak gate,
shadow output launders into authority. G4 is therefore intentionally narrow:
it decides promotion state only, and it fails closed when any required grounded
contract, authority boundary, rule version, replay ref, search-health dependency,
or human-accountability record is missing.

G4's first validation target is narrow. It should promote at least one grounded
output whose declared claim set is fully covered by the upstream artifact
families required for that declared promotion scope, and it should also produce a
blocked legal/mandate promotion attempt when GL handoffs carry `reissue_required`
or equivalent unresolved authority. This proves both sides of the gate:
promotion can happen, and it can refuse.

## Closure Contract

Source of truth: roadmap G4 closure contract in
`docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md`,
especially the "G4 - Promotion Gate (D3.8)" slice.

G4 must deliver:

1. **G0/G1 dependency gate** proving Layer 3 discipline, discovery/search health,
   engineering quality, and at least one G1 grounded source contract are ready.
   G2/G3/GL are context inputs unless the promotion request names claims that
   require causal, proof-carrying, or legal/mandate authority.
2. **Promotion input set** that binds a shadow `DesignRecordV0` or equivalent
   B-side output to explicit claim refs, envelope refs, candidate refs, and the
   upstream grounded contract families required for the declared promotion scope.
3. **Dependency artifact resolver** that reads persisted Layer 3 artifacts through
   governed manifests/inventory/generated-artifact registrations, not through
   case-specific hardcoded claim lists. Artifact-family paths are governed config;
   promoted claim ids and required refs are data.
4. **Grounded contract set** that normalizes G1 SourceContract bindings, G2
   grounded forecast handoffs, G3 proof-carrying analytics records, and GL
   legal/mandate handoffs into a single promotion-readable reference set while
   preserving each source's `authoritative_for` / `may_not_use_for` boundary.
5. **A-completeness ledger** proving every promoted claim has the required A-side
   support for its declared purpose. Missing support blocks promotion. A green
   upstream readiness manifest is necessary but never sufficient: the promoted
   claim must reference the actual grounded contract rows.
6. **Weakest-boundary composition** that computes promotion scope from the weakest
   grounded link. Limited, contested, reissue-required, uncalibrated, or
   out-of-envelope dependencies either limit the promotion scope or block it;
   they never disappear behind a promoted aggregate.
7. **P26/S7 human-decision integrity gate** for high-stakes, value-laden, or
   human-accountability-sensitive promotion. Human approval can satisfy
   accountability and value authorization requirements; it cannot override missing
   A-completeness, stale search, unresolved legal lineage, or failed conformance.
8. **Typed `PromotionRecord`** with `promotion_state` exactly
   `governed_promoted` or `promotion_blocked`, plus blocker/limitation refs,
   weakest-boundary reasons, evidence refs, rule/schema versions, and promotion
   scope. No additional promotion-state lattice is introduced.
9. **Closeout/PDC-compiler/G5 consumer gates** that let downstream closeout,
   compiler, and G5 paths read the promotion state without treating it as
   production, approval, publication, or useful-design credit. The compiler gate
   is reference-only: it exposes promotion refs to graph assembly but does not
   rewrite Layer 2 waist authority or compile authority inside G4.
10. **PUBLIC/REVIEWER/EXPERT/MACHINE promotion surface** exposing promotion state,
    envelope, limitations, blockers, human-decision requirement/status, and
    upstream evidence refs with safe redaction.
11. **Governance-throughput health delta** recording admitted, blocked, stalled,
    and human-review-routed promotion attempts. It must distinguish hard
    A-incompleteness, search-health stalls, stale-index stalls, legal reissue
    stalls, and human-decision stalls so G5 does not misread a fixable search or
    lineage problem as a domain ceiling.
12. **Registry/ratchet delta** recording the G4 gate's admitted maturity,
    conformance refs, and whether the promotion bridge moved from missing-state
    labels to implemented. A green `PromotionRecord` without a registry/ratchet
    delta is not enough to close the slice.
13. **Conformance negatives** proving bypasses fail closed: shadow self-promotion,
    missing grounded contracts, readiness-summary-only promotion, stale/reissue
    dependencies, weakest-boundary override, human override of A-incompleteness,
    missing A-firewall refs, promotion as closeout, promotion as production, and
    public raw-payload leaks.

G4 is done when
`tools/quality/validation/check_policy_design_case_layer3_g4_readiness.py` passes
over persisted artifacts, and runtime tests prove at least one candidate follows:

```text
shadow DesignRecordV0 / B candidate
-> PromotionInputSet with explicit claim + envelope + required contract families
-> GroundedContractSet resolved from persisted G1/G2/G3/GL artifacts
-> ACompletenessLedger pass for the declared promotion scope
-> HumanDecisionIntegrityGate pass or not_required
-> WeakestBoundaryComposition
-> PromotionRecord(promotion_state="governed_promoted")
-> CloseoutPromotionConsumerGate / PdcCompilerConsumerGate / G5 handoff
-> PUBLIC/REVIEWER/EXPERT/MACHINE surface
```

and every bypass path emits `promotion_blocked` with typed issue codes.

## Scope Boundaries

In scope:

- Add G4 runtime-quality contracts and builders for promotion input sets,
  dependency snapshots, grounded contract sets, A-completeness ledgers,
  human-decision integrity gates, weakest-boundary composition, promotion
  records, closeout consumer gates, audit/public surfaces, conformance report,
  health delta, adapter/route registry, and readiness manifest.
- Reuse existing `AuthorityBoundary`, `DesignRecordV0`, `GovernanceDecisionClass`,
  `ClusterHandoffRecord`, G1/G2/G3/GL Layer 3 artifacts, S7 delegation posture,
  human-review/human-decision patterns, public-export redaction, scorecard/phase
  barrier conventions, and generated-artifact registration.
- Promote exactly to governed Layer 3 state for a declared scope, never to
  production or rollout.
- Emit both a passing promotion record and blocked negative promotion records.
- Register generated artifacts, reference docs, and inventory/public surfaces.
- Keep G4's engineering bar explicit: strict Pydantic DTOs, `tomllib`/structured
  parsers for repository metadata, bounded artifact reads, deterministic replay,
  and fail-closed validation. Do not parse TOML/JSON with ad hoc string logic or
  hide stale files behind mutable global caches.

Out of scope:

- No new domain grounding/search engine.
- No production approval packet, production rollout decision, or publication
  authority.
- No G5 proving-ground conversion classification or useful-design credit.
- No G6 agent orchestration.
- No compiler graph rewrite or PDC waist mutation.
- No repair of upstream G1/G2/G3/GL artifacts; G4 can only consume, limit, or
  block based on their persisted state.
- No human override of A-side completeness.
- No new status lattice beyond the controlled `shadow` / `governed_promoted` /
  `promotion_blocked` promotion states.

## Pattern Pass

Relevant failure patterns:

| Pattern | G4 risk | Closure move |
| --- | --- | --- |
| P01 contract-only capability | A `PromotionRecord` type exists but no producer/consumer/surface uses it. | Full chain: input -> gate -> persisted record -> closeout/G5 consumer -> surface -> negatives. |
| P02 thin orchestration | G1/G2/G3/GL stay rich but G4 reads only manifest summaries. | Resolve actual grounded contract rows and refs; readiness summaries are dependency gates only. |
| P03 hidden internal richness | Promotion decision exists only in JSON, not audience surfaces. | PUBLIC/REVIEWER/EXPERT/MACHINE surface with safe redaction and explicit authority boundary. |
| P04 status lattice gap | `governed_promoted` becomes a parallel closeout/approval status. | Promotion state composes with existing authority/status lattice and remains purpose-scoped. |
| P05 authority dilution | Promotion is mistaken for production, closeout, publication, or claim authority. | `authoritative_for` is promotion state only; `may_not_use_for` denies production/closeout/publication/useful-design credit. |
| P07/P08 replay/time gap | Promotion ignores rule versions, legal time, or stale/reissue dependencies. | Rule/schema/time refs are required; stale/reissue dependencies block or limit. |
| P10 semantic adequacy gap | Tests only assert a promotion record exists. | Semantic negatives prove every bypass blocks. |
| P13 governance gravity | G4 grows into a universal super-scorecard. | Keep the gate thin: resolve refs, check A-completeness, compose boundaries, emit promotion state. |
| P15 LLM/speculation laundering | Fluent B candidate self-promotes. | Candidate source remains shadow; only grounded A refs can promote. |
| P25 search-control laundering | Upstream search frontier or no-hit is treated as authority. | G4 accepts only admitted grounded contracts, never search ledgers alone. |
| P26 responsibility-integrity laundering | Human approval is missing, uninformed, or used to override A gaps. | S7/HumanDecisionRecord required for high stakes; it cannot override missing A-completeness. |

Capability transition:

| Capability | Current label | Target label | Acceptance signal |
| --- | --- | --- | --- |
| D3.8 promotion gate | `producer_missing`, `artifact_missing`, `bridge_missing`, `consumer_missing`, `surface_missing`, `semantic_test_missing` | `implemented` | Promotion input -> A-completeness -> PromotionRecord -> closeout/G5 consumer -> all-audience surface -> negatives. |
| Closeout/G5 promotion consumption | `bridge_missing` | `implemented` for promotion-state input only | Closeout consumer gate reads promotion record but cannot infer closeout/production approval. |
| Human-decision integrity for promotion | `bridge_missing` / `verification_missing` | `implemented` for G4 high-stakes path | High-stakes promotion without S7/HumanDecisionRecord blocks; human approval cannot bypass A gaps. |

## Code-Grounded Reality

Existing strengths G4 should reuse:

- `src/polisyos/pdc/_impl/layer2_readiness.py` already gives the waist
  `AuthorityBoundary`, `DesignRecordV0`, `CertifiedOperationEnvelope`, and
  `GovernanceDecisionClass`. `DesignRecordV0` cannot carry production authority.
- `src/polisyos/pdc/_impl/layer2_design_search.py` keeps S2 outputs shadow-only,
  emits cluster handoff records, and already has S7/S8/S10/S11/S12/S13 posture
  input seams.
- S2's `DesignRecordV0` is not currently exposed as one simple standalone
  generated JSON file. It appears through the S2 loop/CAS path, the S2 manifest,
  W12D corpus-run materialization, and downstream refs such as G2
  `s10_prerequisite_bindings.source_design_record_ref`. G4 needs a small source
  design-record resolver; it must not assume a hardcoded
  `layer2_s2_design_record.json` path.
- `src/polisyos/runtime/quality/proving_ground/pre_adapter_grounding_inventory.py` already defines
  `PromotionState = Literal["shadow", "governed_promoted", "promotion_blocked"]`
  and blocks pre-G4 promotion in G0.
- `src/polisyos/runtime/quality/proving_ground/substrate_grounding_search.py` persists G1
  grounded source contracts and explicitly denies claim, promotion, useful-design,
  and production authority.
- `src/polisyos/runtime/quality/proving_ground/causal_forecast_search.py` persists
  `layer3_g2_grounded_forecast_handoffs.json`; those handoffs are readable by
  G4/G5 but deny promotion/conversion authority.
- `src/polisyos/runtime/quality/proving_ground/proof_carrying_analytics_search.py` persists
  proof-carrying analytics records, S11 predictive posture bindings, and public
  projection refs while denying closeout/promotion authority.
- `src/polisyos/runtime/quality/proving_ground/legal_mandate_search.py` already emits
  `layer3_gl_g4_promotion_gate_consumer_gate.json` and
  `layer3_gl_promotion_gate_handoff.json`, and explicitly does not claim
  `governed_promoted`.
- `src/polisyos/runtime/quality/design_axes/mandate_bounded_delegation.py` already owns the S7
  `HumanDecisionRequest` / `HumanDecisionRecord` / five-rights /
  responsibility-integrity contracts G4 needs for P26. This is the primary human
  decision source for G4.
- `architecture/policy_design_case/layer2_s7_delegation_manifest.json` proves S7
  capability health, required artifacts, firewalls, and false-clear metrics.
  Treat it as a dependency-health gate, not as a per-case human decision.
- `tools/quality/validation/run_universal_outcome_corpus.py` can materialize a
  full W12D report with per-case `s2_design_search` and `s7_delegation` blocks.
  Its committed `wave12d_*_manifest.json` is a command contract, not the
  per-case payload itself.
- `src/polisyos/pdc/_impl/compiler.py` is graph-structure authority only and has
  closeout refs but no promotion refs. G4 should produce a reference-only
  compiler consumer artifact, not rewrite the compiler graph.
- `src/polisyos/runtime/quality/closeout_reader.py` already rejects readiness,
  dashboard, package, and public-export surfaces as closeout evidence. G4 should
  feed closeout only as an observed promotion input and should not modify
  closeout verdict semantics.
- `src/polisyos/runtime/quality/public_export.py` and
  `core/contracts/policy_design_case_projection.py` preserve projection-only
  semantics and deny claim, closeout, scorecard, and approval authority from
  public projections.
- G3/GL public projection ref surfaces already use the right pattern: safe refs
  and projection status, not raw proof/query/legal payload export.
- `approval.py`, `human_review.py`, `phase_barriers.py`, `scorecard.py`,
  `effective_mode.py`, and `closeout_reader.py` already model production
  approval/closeout as separate downstream governance. G4 must not replace them.

Existing weak spots G4 must not underestimate:

- There is no D3.8 `PromotionRecord` runtime module yet. Existing uses of the
  word "promotion" in Foundry, release gates, or production approval are not this
  Layer 3 promotion gate.
- Runtime HTTP already exposes `/data/promotion/...` and `PromotionLane` for
  ExploreLane/source-binding promotion. That flow updates data source bindings;
  it is not a G4 shadow-to-governed decision and must not be reused as G4.
- `architecture/generated_artifacts.toml` uses `promotion_target` for generated
  artifact lifecycle, and release/ops gates use promotion language for release
  management. Neither is D3.8 promotion.
- G1 can prove substrate binding, but its PUBLIC/REVIEWER claim projection is
  intentionally out of scope until G4/G5. G4 must add a promotion surface without
  rewriting G1.
- G2/G3/GL readiness manifests can pass while individual promotion-relevant
  contracts still carry limitations. G4 must consume contract rows, not only
  summary pass/fail.
- Upstream artifact shapes are family-specific, not uniform: G1 stores
  `grounded_source_contracts.bindings`, G2 stores
  `grounded_forecast_handoffs`, `forecast_support_bindings`, and
  `s10_prerequisite_bindings`, G3 stores `proof_carrying_analytics_records` and
  `s11_predictive_posture_bindings`, and GL exposes both single handoff/gate
  records and supporting legal/mandate record families. A generic list parser
  will either miss evidence or over-admit summaries.
- GL currently may carry `reissue_required` or unresolved reference/amendment
  status. Legal/mandate-dependent promotion must block or scope out that legal
  authority explicitly.
- GL's `gl_g4_promotion_gate_consumer_gate_status = "pass"` means "G4 can read
  this handoff"; it is not a legal-authority pass and must not override
  `gl_amendment_lineage_status`, `gl_reference_resolution_status`, or
  `gl_temporal_competence_status`.
- Human-review code is mostly production-approval oriented. G4 may reuse its
  calibration and packet-completeness patterns, but G4's actual accountability
  bridge should prefer S7 `HumanDecisionRecord` / delegation posture refs for
  policy-design promotion.
- S7 manifest pass, S7 corpus summary metrics, and S2 ledger refs are not enough
  to prove a specific high-stakes promotion was human-decided. G4 must validate
  a concrete per-case S7 posture/decision payload or block.
- W12D manifest-only evidence is insufficient. G4 may use a materialized full
  W12D report as a fixture/replay source, but must classify non-pinned S2
  summaries and ref-only design records as unresolved for promotion unless an
  explicit payload/digest is supplied.
- Approval and closeout code are nearby but stronger than G4. G4 should produce
  a closeout input, not a closeout verdict.
- G1/G2/G3/GL runtime-quality modules are already large. G4 should keep its own
  request path import-light and read bounded persisted JSON/TOML artifacts rather
  than importing upstream modules or recomputing upstream bundles to decide a
  promotion.
- G4 should not use filesystem-wide scans in request paths. Use bounded artifact
  paths from generated-artifact TOML, inventory, readiness manifests, and exact
  persisted JSON artifacts.
- Current GL artifacts can report `gl_amendment_lineage_status =
  "reissue_required"`, `gl_reference_resolution_status = "reissue_required"`,
  and `gl_temporal_competence_status = "pass_with_reissue_required"`. G4 must
  treat those as blockers for legal/mandate-dependent promotion unless the
  promotion scope explicitly excludes the affected legal authority.
- Public export is already a redacted projection mechanism. G4 should first emit
  a G4 public/export projection-ref surface; a direct `build_public_export_bundle`
  integration is a separate hook and must remain reference-only unless fully
  implemented and tested.

## Target File Map

Create:

- `src/polisyos/runtime/quality/proving_ground/governed_promotion_gate.py`
  - Strict G4 DTOs, builders, validators, dependency artifact resolver,
    A-completeness and weakest-boundary logic, conformance negatives, and bundle
    builder.
- `tools/quality/validation/check_policy_design_case_layer3_g4_readiness.py`
  - CLI matching G1/G2/G3/GL: `--repo-root`, `--write`, `--output`,
    `--output-format`.
- `tests/unit/runtime/quality/test_layer3_g4_promotion_gate.py`
  - Runtime DTO/builder/conformance tests.
- `tests/repo_quality/tools/test_policy_design_case_layer3_g4_readiness.py`
  - Persisted artifacts, manifest drift, docs/TOML/inventory registration,
    issue-code dictionary, surface visibility, and negative checks.
- `tests/repo_quality/tools/test_policy_design_case_layer3_g4_readiness_cli.py`
  - CLI write/validate behavior.
- `tests/fixtures/layer3/g4/`
  - Valid promotion input fixture, missing-contract fixture, readiness-summary-only
    fixture, legal-reissue fixture, high-stakes-missing-human-decision fixture,
    and shadow-self-promotion fixture.
- `docs/reference/policy-design-case-layer3-promotion-gate.md`
  - Reference doc explaining G4 promotion state, authority boundary, blockers,
    human-decision route, and closeout/G5 handoff.

Modify:

- `src/polisyos/runtime/quality/__init__.py` if local package exports require it.
- `architecture/generated_artifacts.toml`
  - Add G4 generated-artifact family.
- `architecture/policy_design_case/inventory.json`
  - Register G4 promotion surface and readiness artifacts.
- `docs/reference/generated-artifacts.md`
  - Add G4 generated artifact family.
- `docs/reference/documentation-inventory.md`
  - Add the G4 reference doc.
- `docs/reference/index.md`
  - Link the G4 reference doc if local pattern requires it.
- `docs/reference/public-surface.md`
  - Add G4 promotion public projection if local public-surface pattern requires it.

Do not modify:

- `src/polisyos/pdc/_impl/layer2_readiness.py` for G4. `governed_promoted` is a
  Layer 3 promotion-state output in `PromotionRecord`, not a new
  `AuthorityPosture`. If implementation appears to require changing the narrow
  waist, stop and amend the constitution/master plan first.
- `src/polisyos/runtime/quality/approval.py` or `scorecard.py` to treat G4 as
  production approval.
- Upstream G1/G2/G3/GL runtime modules to make G4 green. If implementation finds
  a real upstream defect, record it as an upstream repair or follow-up; G4 should
  consume the persisted contract surface, not reshape it opportunistically.

## Persisted Artifacts

Expected generated artifacts:

- `architecture/policy_design_case/layer3_g4_dependency_readiness_snapshot.json`
- `architecture/policy_design_case/layer3_g4_promotion_input_set.json`
- `architecture/policy_design_case/layer3_g4_grounded_contract_set.json`
- `architecture/policy_design_case/layer3_g4_a_completeness_ledger.json`
- `architecture/policy_design_case/layer3_g4_human_decision_integrity_gate.json`
- `architecture/policy_design_case/layer3_g4_weakest_boundary_composition.json`
- `architecture/policy_design_case/layer3_g4_promotion_records.json`
- `architecture/policy_design_case/layer3_g4_closeout_consumer_gate.json`
- `architecture/policy_design_case/layer3_g4_pdc_compiler_consumer_gate.json`
- `architecture/policy_design_case/layer3_g4_g5_promotion_handoff.json`
- `architecture/policy_design_case/layer3_g4_governance_throughput_delta.json`
- `architecture/policy_design_case/layer3_g4_promotion_audit_surface.json`
- `architecture/policy_design_case/layer3_g4_public_export_projection_refs.json`
- `architecture/policy_design_case/layer3_g4_conformance_report.json`
- `architecture/policy_design_case/layer3_g4_health_metric_delta.toml`
- `architecture/policy_design_case/layer3_g4_adapter_contract_registry.toml`
- `architecture/policy_design_case/layer3_g4_registry_ratchet_delta.json`
- `architecture/policy_design_case/layer3_g4_readiness_manifest.json`

Minimum write-mode paths must include dependency readiness, promotion inputs,
grounded contract set, A-completeness ledger, human-decision integrity gate,
weakest-boundary composition, promotion records, closeout consumer gate,
PDC compiler consumer gate, G5 handoff, governance-throughput delta, surfaces,
conformance report, health delta, adapter contract registry, registry/ratchet
delta, and readiness manifest. G4 cannot claim a real promotion if any of these
are missing.

## Runtime Contract Sketch

Add strict DTOs in `layer3_promotion_gate.py`:

- `Layer3G4ValidationIssue`
- `Layer3G4ValidationReport`
- `Layer3G4PromotionRequest`
- `Layer3G4DependencyReadinessSnapshot`
- `Layer3G4DependencyArtifactShape`
- `Layer3G4SourceDesignRecordResolution`
- `Layer3G4SourcePayloadStatus`
- `Layer3G4NamingCollisionGuard`
- `Layer3G4PromotionInputSet`
- `Layer3G4GroundedContractRef`
- `Layer3G4GroundedContractSet`
- `Layer3G4ACompletenessRequirement`
- `Layer3G4ACompletenessLedger`
- `Layer3G4HumanDecisionIntegrityGate`
- `Layer3G4S7DecisionPayloadResolution`
- `Layer3G4WeakestBoundaryComposition`
- `Layer3G4PromotionRecord`
- `Layer3G4CloseoutConsumerGate`
- `Layer3G4PdcCompilerConsumerGate`
- `Layer3G4G5PromotionHandoff`
- `Layer3G4GovernanceThroughputDelta`
- `Layer3G4PromotionAuditSurface`
- `Layer3G4PublicExportProjectionRefSurface`
- `Layer3G4ConformanceReport`
- `Layer3G4RegistryRatchetDelta`
- `Layer3G4ReadinessManifest`
- `Layer3G4Bundle`

Core constants:

- `LAYER3_G4_SCHEMA_VERSION = "policyos.policy_design_case.layer3_g4_promotion_gate.v1"`
- `LAYER3_G4_RULE_VERSION = "policyos.layer3.g4.shadow_to_governed_promotion.v1"`
- `G4_SURFACE_ID = "layer3_g4_shadow_to_governed_promotion_surface"`
- `G4_READINESS_CHECK_ID = "layer3_g4_shadow_to_governed_promotion_gate"`
- `PROMOTION_STATE_VALUES = ("shadow", "governed_promoted", "promotion_blocked")`
- `G4_FINAL_PROMOTION_RECORD_STATES = ("governed_promoted", "promotion_blocked")`
- `G4_SOURCE_PAYLOAD_STATUS_VALUES = ("full_payload", "ref_only", "manifest_only", "unresolved")`
- `G4_PUBLIC_EXPORT_HOOK_STATUS_VALUES = ("implemented", "out_of_scope_reference_only", "blocked")`
- `G4_MAY_NOT_USE_FOR` must include at least
  `("production_authority", "production_claim_authority", "rollout_authority", "publication_authority", "approval_authority", "scorecard_authority", "closeout_authority", "runtime_closeout_authority", "closeout_verdict", "claim_authority", "claim_authority_without_upstream_grounding", "source_data_truth_authority", "public_recommendation", "policy_recommendation", "useful_design_credit_before_g5", "causal_effect_authority_without_g2", "proof_authority_without_g3", "legal_authority_without_gl", "human_override_of_a_incompleteness")`

Public builder functions:

- `build_layer3_g4_bundle(repo_root: Path) -> Layer3G4Bundle`
- `validate_layer3_g4_bundle(repo_root: Path, bundle: Layer3G4Bundle) -> Layer3G4ValidationReport`
- `build_g4_dependency_readiness_snapshot(repo_root: Path) -> Layer3G4DependencyReadinessSnapshot`
- `load_g4_dependency_artifacts(...) -> tuple[Layer3G4DependencyArtifactShape, ...]`
- `resolve_g4_source_design_record(...) -> Layer3G4SourceDesignRecordResolution`
- `check_g4_naming_collisions(...) -> Layer3G4NamingCollisionGuard`
- `build_g4_promotion_input_set(...) -> Layer3G4PromotionInputSet`
- `build_g4_grounded_contract_set(...) -> Layer3G4GroundedContractSet`
- `build_g4_a_completeness_ledger(...) -> Layer3G4ACompletenessLedger`
- `build_g4_human_decision_integrity_gate(...) -> Layer3G4HumanDecisionIntegrityGate`
- `build_g4_weakest_boundary_composition(...) -> Layer3G4WeakestBoundaryComposition`
- `build_g4_promotion_records(...) -> tuple[Layer3G4PromotionRecord, ...]`
- `build_g4_closeout_consumer_gate(...) -> Layer3G4CloseoutConsumerGate`
- `build_g4_pdc_compiler_consumer_gate(...) -> Layer3G4PdcCompilerConsumerGate`
- `build_g4_g5_promotion_handoff(...) -> Layer3G4G5PromotionHandoff`
- `build_g4_governance_throughput_delta(...) -> Layer3G4GovernanceThroughputDelta`
- `build_g4_promotion_audit_surface(...) -> Layer3G4PromotionAuditSurface`
- `build_g4_public_export_projection_refs(...) -> Layer3G4PublicExportProjectionRefSurface`
- `build_g4_registry_ratchet_delta(...) -> Layer3G4RegistryRatchetDelta`
- `validate_g4_conformance(...) -> Layer3G4ConformanceReport`

Public DTOs crossing generated artifacts must carry the applicable subset of:

- `schema_version`
- `rule_version`
- `status`
- `promotion_state` where applicable
- `authority_boundary`
- `authoritative_for`
- `may_not_use_for`
- `producer_component`
- `producer_artifact_ref`
- `provenance_refs`
- `source_design_record_ref`
- `source_design_record_digest` or explicit blocker
- `promotion_scope`
- `case_id`
- `claim_refs`
- `envelope_ref`
- `required_contract_families`
- `grounded_contract_refs`
- `search_health_dependency_refs`
- `adapter_admission_refs`
- `conformance_refs`
- `weakest_boundary_reason`
- `human_decision_required`
- `human_decision_record_refs`
- `limitation_refs`
- `blocker_refs`
- `closeout_consumer_refs`
- `pdc_compiler_consumer_refs`
- `g5_handoff_refs`
- `registry_ratchet_delta_refs`
- `generated_at`

## Promotion Semantics

Promotion uses the shared G0/master vocabulary:

- `shadow`
- `governed_promoted`
- `promotion_blocked`

`shadow` remains the incoming source/pre-gate posture and may appear in upstream
admission/dependency records. The final G4 `PromotionRecord` outcomes are only
`governed_promoted` and `promotion_blocked`; `shadow` is not a successful G4
promotion result. G4 must not drop `shadow` from the shared status-composition
vocabulary.

These states compose with the existing status lattice. They do not create a
parallel closeout, approval, production, publication, or useful-design status.

G4 artifacts are authoritative only for:

- promotion decision replay;
- governed promotion state for the declared promotion scope;
- downstream closeout/PDC-compiler/G5 input refs that read promotion state.

G4 artifacts are not authoritative for:

- causal effect estimates;
- legal authority;
- proof/certificate authority;
- source data truth;
- production approval;
- public recommendation;
- scorecard/closeout verdicts;
- useful-design credit before G5 conversion.

Promotion can be limited by envelope, claim scope, time, jurisdiction, method,
audience, and authority purpose. G4 must expose those limitations, not mint a new
state for each combination.

## Bridge And Adapter Semantics

G4 is not an adapter to a domain source. It is the bridge that turns already
admitted upstream contracts into a governed promotion decision. Its adapter
registry must therefore describe semantic bridges between produced artifacts and
consumers, not summarize that "G4 checked things".

Required bridge records:

- `layer3_g4_s2_source_resolution_to_promotion_input`
- `layer3_g4_design_record_to_promotion_input`
- `layer3_g4_dependency_manifests_to_grounded_contract_set`
- `layer3_g4_grounded_contract_set_to_a_completeness_ledger`
- `layer3_g4_a_completeness_to_weakest_boundary`
- `layer3_g4_s7_human_decision_to_p26_gate`
- `layer3_g4_weakest_boundary_to_promotion_record`
- `layer3_g4_promotion_record_to_closeout_consumer_gate`
- `layer3_g4_promotion_record_to_pdc_compiler_consumer_gate`
- `layer3_g4_promotion_record_to_g5_handoff`
- `layer3_g4_promotion_record_to_public_projection_refs`

Each bridge record should name producer artifact family, consumer, authority
purpose, `authoritative_for`, `may_not_use_for`, semantic-loss status,
verification refs, and at least one negative proving the bridge fails closed.
An adapter registry that only lists bridge names is `adapter_registry_summary_only`
and cannot close G4.

## Implementation Tasks

### Task 0 - Red Baseline and Dependency Audit

Add failing tests before implementation.

Test expectations:

- G4 runtime module import currently fails or lacks required DTO/builders.
- G4 readiness CLI currently missing.
- Generated artifacts missing.
- Source design-record resolution is missing or assumes a standalone S2 JSON
  artifact.
- Promotion without actual grounded contract rows fails.
- A `DesignRecordV0` / B candidate cannot self-promote.
- G1/G2/G3/GL readiness summaries alone cannot promote.
- GL reissue-required legal handoff blocks legal-dependent promotion.
- High-stakes promotion without S7/HumanDecisionRecord blocks.
- S7 manifest pass or S2 ledger refs alone cannot satisfy the human-decision
  gate.
- W12D command manifest alone cannot satisfy source design-record or S7 payload
  requirements.
- Human decision cannot override missing grounded contracts.
- Runtime HTTP `PromotionLane` / `/data/promotion` cannot be used as G4
  promotion.
- Generated-artifact `promotion_target` cannot be used as G4 promotion state.
- Public projection cannot include raw upstream payloads or claim production.
- Public-export hook cannot be claimed implemented from a projection-ref artifact
  alone.

Acceptance:

- Red tests fail for the right reasons, not import noise unrelated to G4.
- Dependency audit records which upstream artifacts are hard requirements for the
  first passing promotion and which are context-only.

### Task 1 - G4 Contracts and Dependency Artifact Resolver

Implement `layer3_promotion_gate.py` with strict DTOs, constants, and dependency
resolver.

Resolver requirements:

- Load G0 and G1 readiness as hard dependencies.
- Load G2/G3/GL readiness as context dependencies and mark them required only
  when a promotion request requires forecast/proof/legal contract families.
- Resolve artifacts from governed paths:
  - `architecture/generated_artifacts.toml`;
  - `architecture/policy_design_case/inventory.json`;
  - readiness manifest `closure_artifact_paths` / expected artifact lists when
    present;
  - exact Layer 3 generated artifact files.
- Do not scan the whole repo or glob arbitrary JSON in the request path.
- Do not hardcode promoted claim ids, construct ids, or candidate ids.
- Do allow governed artifact-family path constants in the CLI and validator.
- Resolve the source design record from explicit promotion input first, then from
  S2/W12D/G2 S10 refs when available. A manifest that only says S2 is active is
  not enough; G4 needs a replayable ref plus digest or an explicit unresolved
  blocker.
- Classify source design-record resolution as `full_payload`, `ref_only`,
  `manifest_only`, or `unresolved`. Only `full_payload` or a replayable ref with
  explicit digest can enter the promotion input set.
- Treat W12D full report output as an optional fixture/replay source only when
  the report payload is present. The committed W12D run manifest and non-pinned
  minimal S2 summaries are not source design-record payloads.
- Parse dependency artifacts with family-specific shapes:
  - G1: `grounded_source_contracts.bindings`;
  - G2: `grounded_forecast_handoffs`, `forecast_support_bindings`,
    `s10_prerequisite_bindings`, `method_validity_transport`,
    `observable_calibration_report`, `transport_limit_declarations`, and
    `authority_envelopes`;
  - G3: `proof_carrying_analytics_records`,
    `s11_predictive_posture_bindings`, `certificate_resolution_report`,
    `method_requirement_bindings`, `s11_prerequisite_bindings`, and
    `s11_calibration_bindings`;
  - GL: handoff/gate/record families, including legal authority, threshold,
    mandate, temporal competence, amendment lineage, and reference-resolution
    records.
- Treat GL G4-compatibility pass as read-compatibility only. Legal/mandate
  readiness still comes from GL legal authority, temporal competence, amendment
  lineage, and reference-resolution records.
- Treat runtime HTTP `PromotionLane`, `PromotionCandidatesResponse`,
  `/data/promotion/*`, generated-artifact `promotion_target`, and release
  promotion gates as naming collisions only. They are not G4 inputs or outputs.
- Do not import or rerun G1/G2/G3/GL runtime builders to make a promotion
  decision. Read persisted artifacts; use upstream builders only in tests or
  upstream readiness checks.

Acceptance:

- Unit tests build `Layer3G4DependencyReadinessSnapshot`.
- Missing G1 readiness blocks all promotion.
- Missing optional G2/G3/GL artifacts blocks only promotion requests that require
  those families.
- Resolver records schema/rule versions and manifest drift inputs.
- Missing source design-record replay ref or digest blocks with a typed issue.
- Dependency artifact shape mismatches block instead of silently dropping rows.

### Task 2 - Promotion Input Set and Grounded Contract Set

Build the G4 input normalizer.

Promotion input must include:

- `source_design_record_ref`;
- `source_design_record_replay_ref`;
- `source_design_record_digest`;
- `source_design_record_resolution_status`;
- `case_id`;
- `candidate_ref`;
- `candidate_source`;
- `incoming_projection_status`;
- `promotion_scope`;
- `claim_refs`;
- `envelope_ref`;
- `required_contract_families`;
- `human_decision_policy`;
- `stakes_profile`;
- `may_not_use_for`.

Grounded contract set must normalize:

- G1 `grounded_source_contracts.bindings` refs and lineage/coverage refs;
- G2 `grounded_forecast_handoffs`, `forecast_support_bindings`, and
  `s10_prerequisite_bindings` refs, calibration refs, method validity refs,
  uncertainty refs, and transport limitation refs;
- G3 `proof_carrying_analytics_records` and `s11_predictive_posture_bindings`
  refs, certificate resolution refs, and method requirement refs;
- GL legal/mandate handoff refs, threshold/mandate refs, temporal competence,
  amendment/reference status, and G4 compatibility refs;
- adapter admission/conformance refs from each upstream family.

Acceptance:

- A minimal promotion request over the required upstream family refs for its
  declared scope produces a grounded contract set.
- A legal/mandate promotion request consumes GL handoff refs and preserves
  `reissue_required`/limitation status.
- Search ledgers alone are rejected as grounded contracts.
- Readiness manifest summaries alone are rejected as grounded contracts.
- A legal/mandate request cannot pass merely because the GL G4-compatibility gate
  passed; the GL legal authority/reissue statuses must also support the scope.

### Task 3 - A-Completeness and Weakest-Boundary Composition

Implement A-completeness over the declared promotion scope.

Rules:

- Every promoted claim must map to required contract families.
- A source/data claim requires G1 grounded source contract.
- A causal/forecast/effect claim requires G2 forecast support and calibration or
  a declared limitation that prevents overclaim.
- A proof/analytics claim requires G3 proof-carrying record and certificate
  resolution.
- A legal/mandate/threshold claim requires GL legal/mandate records with temporal
  competence and no unresolved reissue blocker for the promoted legal purpose.
- S6/S7/S8/S10/S11/S12/S13 posture refs are required when the promotion scope
  carries those authority dimensions.
- Search recall/freshness dependencies from upstream slices must be pass/fresh
  for any promoted claim family that depends on search.
- Adapter admission/conformance must be pass for every upstream contract used.

Weakest-boundary composition:

- `promotion_blocked` if any required family is missing, stale, reissue-required
  for the promoted purpose, or conformance-failed.
- `promotion_blocked` if any `may_not_use_for` in upstream artifacts denies the
  requested promotion purpose.
- `governed_promoted` only for the declared scope that survives all limitations.
- Limitations and blockers are preserved as refs and reasons.

Acceptance:

- Missing G2 for an effect claim blocks.
- Missing G3 for a proof claim blocks.
- GL `reissue_required` blocks legal-dependent promotion or requires explicit
  legal scope exclusion.
- A limited upstream boundary cannot be promoted as unlimited.
- Weakest-boundary reason is deterministic and replayable.

### Task 4 - P26 / Human-Decision Integrity Gate

Implement the human-decision integrity gate.

Rules:

- High-stakes, value-laden, ranked-value, accountability-sensitive, or
  out-of-routine governed promotion requires S7 delegation refs and a
  `HumanDecisionRecord`. `human_decision_not_required` is valid only for
  non-high-stakes bounded promotion scopes with explicit routine/in-envelope
  rationale.
- Use `src/polisyos/runtime/quality/design_axes/mandate_bounded_delegation.py` as the primary contract
  source: `HumanDecisionRequest`, `HumanDecisionRecord`, `FiveRightsCheck`, and
  `ResponsibilityIntegrityCheck`. `human_review.py` is adjacent production-review
  machinery, not the authority source for G4 promotion decisions.
- Use `layer2_s7_delegation_manifest.json` only as a dependency-health signal.
  It cannot substitute for a case-specific S7 posture or `HumanDecisionRecord`.
- S2 search-ledger `delegation_request_refs` / `delegation_record_refs` are
  replay-visible pointers. They help locate evidence, but a ref-only ledger entry
  cannot satisfy the G4 human-decision gate without resolving the corresponding
  S7 payload or an explicit typed blocker.
- W12D `s7_delegation` blocks may be used as test/replay fixtures when a full
  report payload is materialized; the W12D manifest or S7 corpus summary alone is
  insufficient.
- Human decision must reference the same case/candidate/promotion scope and the
  material limitations the human accepted.
- Human decision must show active choice, available alternatives, and
  responsibility-integrity status. Five-rights checks must pass for the required
  role, information, channel, time, and decision class.
- Human decision cannot override:
  - missing grounded contracts;
  - failed A-completeness;
  - stale search/indices;
  - unresolved legal reissue/reference lineage;
  - failed adapter conformance;
  - production/approval/closeout floors.

Acceptance:

- High-stakes promotion without human-decision refs blocks.
- High-stakes promotion with `human_decision_not_required` blocks.
- S7 manifest-only or S2 ledger-ref-only evidence blocks.
- Human-decision refs with mismatched candidate/scope block.
- Human-decision refs with inactive choice, failed five-rights checks, wrong
  role, or non-pass responsibility integrity block.
- Human approval over A-incomplete promotion still blocks with a specific issue
  code.
- Non-high-stakes bounded promotion can pass with `human_decision_required=false`
  and an explicit rationale.

### Task 5 - Promotion Records, Consumer Gates, and G5 Handoff

Implement `Layer3G4PromotionRecord`.

Each promotion record must include:

- `promotion_record_id`;
- `promotion_state`;
- `promotion_scope`;
- `case_id`;
- `source_design_record_ref`;
- `grounded_contract_set_ref`;
- `a_completeness_ledger_ref`;
- `weakest_boundary_composition_ref`;
- `human_decision_integrity_gate_ref`;
- `authoritative_for`;
- `may_not_use_for`;
- `blocker_refs`;
- `limitation_refs`;
- `upstream_contract_refs`;
- `closeout_consumer_gate_ref`;
- `pdc_compiler_consumer_gate_ref`;
- `g5_handoff_ref`;
- `registry_ratchet_delta_ref`;
- `rule_version`;
- `schema_version`.

Closeout consumer gate:

- Exposes `promotion_state` as a closeout/G5 input.
- Does not set `can_closeout`, `approval_ready`, `publishable`, or
  `useful_design_rate`.
- Fails if closeout or scorecard code attempts to infer a closeout verdict from
  promotion alone.
- Does not modify `closeout_reader.py` module readers or closeout verdict rules
  in this slice. If a future closeout reader wants to consume G4 directly, that
  is a separate governed integration plan; G4's artifact is reference-only.

PDC compiler consumer gate:

- Exposes promotion-state refs as compile-time inputs for PDC graph assembly.
- Does not rewrite Layer 2 `DesignRecordV0` authority posture or claim production
  authority.
- Fails if compiler integration treats promotion as source-data, legal, causal,
  proof, closeout, or publication authority.
- Remains a reference-only artifact in G4; any real compiler graph rewrite belongs
  to a later slice or a separately governed waist-change plan.
- Does not modify `src/polisyos/pdc/_impl/compiler.py` or
  `layer2_readiness.py` to make the G4 plan green.

G5 handoff:

- Carries only the governed promotion state, promotion scope, blockers,
  limitations, and upstream contract refs required for first proving-ground
  conversion.
- Does not declare conversion, usefulness, or publishability; G5 must still earn
  those states.

Acceptance:

- At least one promotion record is `governed_promoted` for a narrow fully
  grounded scope.
- At least one negative promotion record is `promotion_blocked`.
- Closeout consumer gate can read promotion refs and preserves
  `may_not_use_for`.
- PDC compiler consumer gate and G5 handoff are persisted and preserve
  `may_not_use_for`.
- No G4 artifact claims production, publication, approval, scorecard, or
  useful-design credit.
- Passing G4 does not require edits to production approval, scorecard, closeout
  verdict, PDC compiler graph authority, or Layer 2 readiness status enums.

### Task 6 - Surfaces, Generated Artifacts, Readiness CLI, and Docs

Implement all generated artifacts and registration.

Readiness CLI:

- Add `tools/quality/validation/check_policy_design_case_layer3_g4_readiness.py`.
- Match G1/G2/G3/GL CLI shape: `--repo-root`, `--write`, `--output`,
  `--output-format`.
- Use `tools.lib.fs.atomic_write_text`.
- Follow the stricter G2/G3/GL readiness pattern: module-level
  `EXPECTED_ARTIFACT_PATHS`, `EXPECTED_MANIFEST_DRIFT_KEYS`, and
  `ALL_ISSUE_CODES`; exact `--write` artifact-set validation; missing and
  unexpected write paths both fail.
- Validate runtime bundle, persisted artifacts, docs/TOML/inventory registration,
  issue-code dictionary, manifest drift, write-path completeness, and authority
  leaks.

Surfaces:

- Add `layer3_g4_promotion_audit_surface.json`.
- Add `layer3_g4_public_export_projection_refs.json`.
- Surface audiences: `PUBLIC`, `REVIEWER`, `EXPERT`, `MACHINE`.
- Follow `PolicyDesignCaseProjection` / G3 / GL projection-only patterns:
  projection refs may explain G4 state, but they are not claim, scorecard,
  closeout, approval, production, publication, or useful-design authority.
- PUBLIC fields must include promotion state, envelope/scope, high-level blocker
  and limitation codes, and safe evidence refs only.
- EXPERT/MACHINE fields may include full upstream refs, conformance refs, and
  replay refs, but not raw sensitive payloads.
- If G4 is not wired directly into `build_public_export_bundle`, record
  `public_export_hook_status = "out_of_scope_reference_only"` or equivalent.
  Do not claim a public-export hook merely because the G4 projection-ref artifact
  exists.

Registrations:

- Add generated-artifact family to `architecture/generated_artifacts.toml`.
- Update `docs/reference/generated-artifacts.md`.
- Register surfaces/readiness in `architecture/policy_design_case/inventory.json`.
- Add `docs/reference/policy-design-case-layer3-promotion-gate.md`.
- Update documentation inventory, reference index, and public surface docs when
  required by local pattern.

Acceptance:

- CLI `--write` writes the exact expected artifact set.
- CLI without `--write` validates persisted artifacts.
- Generated-artifact TOML/docs/inventory registrations are complete.
- Manifest drift keys match runtime builder output.
- Public projection has no raw payload leak and no authority overclaim.
- Public-export hook status is truthful: reference-only if no actual public
  export integration was implemented.

### Task 7 - Conformance, Performance, and Closeout Verification

Add conformance negatives:

- `shadow_design_record_self_promotes`
- `promotion_without_g1_grounded_source_contract`
- `source_design_record_resolution_unresolved`
- `source_design_record_digest_missing`
- `dependency_artifact_shape_mismatch`
- `effect_claim_without_g2_forecast_support`
- `proof_claim_without_g3_proof_record`
- `legal_claim_without_gl_legal_authority`
- `missing_a_firewall_ref_promoted`
- `gl_reissue_required_promoted`
- `gl_g4_compatibility_gate_overclaimed_as_legal_authority`
- `readiness_summary_only_promoted`
- `search_ledger_only_promoted`
- `s7_manifest_only_promoted`
- `s2_ledger_ref_only_human_decision`
- `w12d_manifest_only_source_payload`
- `source_design_record_ref_only_promoted`
- `data_promotion_lane_reused_for_g4`
- `generated_artifact_promotion_target_reused_for_g4`
- `upstream_builder_rerun_in_request_path`
- `upstream_may_not_use_for_ignored`
- `weakest_boundary_ignored`
- `human_decision_missing_for_high_stakes`
- `high_stakes_human_decision_not_required_bypass`
- `human_decision_scope_mismatch`
- `human_decision_overrides_a_incompleteness`
- `promotion_record_claims_closeout`
- `promotion_record_rewrites_closeout_reader`
- `promotion_record_claims_pdc_compile_authority`
- `promotion_record_rewrites_pdc_compiler`
- `promotion_record_claims_production`
- `promotion_record_claims_publication`
- `promotion_record_claims_approval`
- `promotion_record_claims_scorecard`
- `promotion_record_claims_useful_design_credit`
- `promotion_record_incomplete_may_not_use_for`
- `public_projection_raw_payload_leak`
- `public_export_hook_overclaimed`
- `policy_design_case_projection_authority_leak`
- `manifest_runtime_drift`
- `promotion_state_vocab_drops_shadow`
- `promotion_gate_admission_without_conformance`

Performance/scaling checks:

- Artifact resolution uses bounded generated-artifact/inventory/readiness paths,
  not recursive repo scans.
- JSON artifact loads are limited to declared upstream families.
- G4 promotion decisions read persisted G1/G2/G3/GL artifacts and do not
  recompute upstream bundles.
- No domain-corpus DuckDB full scans occur in G4 request path.
- Repeated artifact loads use small helper cache or deterministic one-shot bundle
  build; no mutable global cache that hides file changes in tests.

Closeout commands:

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer3_g4_promotion_gate.py
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer3_g4_readiness.py
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer3_g4_readiness_cli.py
uv run python tools/quality/validation/check_policy_design_case_layer3_g4_readiness.py --write --output-format json
uv run python tools/quality/validation/check_policy_design_case_layer3_g4_readiness.py --output-format json
uv run polisyos-tools architecture guardrails check
python3 -m tools.cli workspace verify --backend-only
```

Acceptance:

- All targeted G4 tests pass.
- Readiness CLI returns pass after `--write`.
- Architecture guardrails pass.
- Backend verification passes or any failure is unrelated and explicitly
  documented.

## Readiness Manifest Keys

Readiness manifest drift keys should include:

- `schema_version`
- `rule_version`
- `g0_dependency_status`
- `g1_dependency_status`
- `g2_context_status`
- `g3_context_status`
- `gl_context_status`
- `g4_dependency_readiness_status`
- `g4_source_design_record_resolution_status`
- `g4_source_design_record_payload_status`
- `g4_source_design_record_digest_status`
- `g4_w12d_payload_source_status`
- `g4_dependency_artifact_shape_status`
- `g4_runtime_promotion_lane_collision_status`
- `g4_generated_artifact_promotion_target_collision_status`
- `g4_promotion_input_count`
- `g4_grounded_contract_set_status`
- `g4_grounded_contract_ref_count`
- `g4_a_completeness_status`
- `g4_a_completeness_requirement_count`
- `g4_a_completeness_missing_requirement_count`
- `g4_human_decision_integrity_status`
- `g4_s7_human_decision_payload_status`
- `g4_high_stakes_human_decision_bypass_status`
- `g4_s7_manifest_only_blocker_count`
- `g4_weakest_boundary_status`
- `g4_promotion_record_count`
- `g4_governed_promoted_count`
- `g4_promotion_blocked_count`
- `g4_may_not_use_for_completeness_status`
- `g4_closeout_consumer_gate_status`
- `g4_pdc_compiler_consumer_gate_status`
- `g4_g5_promotion_handoff_status`
- `g4_public_export_projection_status`
- `g4_public_projection_mode`
- `g4_public_export_hook_status`
- `g4_promotion_surface_status`
- `g4_governance_throughput_status`
- `g4_conformance_status`
- `g4_adapter_contract_registry_status`
- `g4_registry_ratchet_delta_status`
- `g4_promotion_gate_admission_maturity`
- `g4_promotion_gate_admission_conformance_ref_count`
- `g4_generated_artifacts_registration_status`
- `g4_inventory_surface_status`
- `g4_reference_docs_status`
- `g4_health_metric_ids`

## Issue Codes

The runtime and CLI should expose at least these issue codes:

- `layer3_g4_g0_dependency_not_ready`
- `layer3_g4_g1_dependency_not_ready`
- `layer3_g4_context_dependency_missing`
- `layer3_g4_dependency_readiness_snapshot_missing`
- `layer3_g4_promotion_input_missing`
- `layer3_g4_source_design_record_missing`
- `layer3_g4_source_design_record_unresolved`
- `layer3_g4_source_design_record_digest_missing`
- `layer3_g4_source_design_record_payload_ref_only`
- `layer3_g4_source_design_record_shape_mismatch`
- `layer3_g4_source_design_record_not_shadow`
- `layer3_g4_w12d_manifest_only_not_payload`
- `layer3_g4_shadow_self_promotion`
- `layer3_g4_data_promotion_lane_confused`
- `layer3_g4_generated_artifact_promotion_target_confused`
- `layer3_g4_dependency_artifact_shape_mismatch`
- `layer3_g4_grounded_contract_set_missing`
- `layer3_g4_grounded_contract_ref_missing`
- `layer3_g4_readiness_summary_only_promotion`
- `layer3_g4_search_ledger_only_promotion`
- `layer3_g4_missing_g1_grounded_source_contract`
- `layer3_g4_missing_g2_forecast_support`
- `layer3_g4_missing_g2_calibration_ref`
- `layer3_g4_missing_g3_proof_record`
- `layer3_g4_missing_g3_certificate_resolution`
- `layer3_g4_missing_gl_legal_authority`
- `layer3_g4_missing_a_firewall_ref`
- `layer3_g4_gl_reissue_required_blocks_promotion`
- `layer3_g4_gl_reference_resolution_blocks_promotion`
- `layer3_g4_gl_compatibility_gate_overclaimed`
- `layer3_g4_search_recall_dependency_unhealthy`
- `layer3_g4_stale_upstream_index_blocks_promotion`
- `layer3_g4_upstream_builder_rerun_in_request_path`
- `layer3_g4_adapter_admission_missing`
- `layer3_g4_adapter_conformance_missing`
- `layer3_g4_upstream_may_not_use_for_ignored`
- `layer3_g4_a_completeness_ledger_missing`
- `layer3_g4_a_completeness_failed`
- `layer3_g4_weakest_boundary_missing`
- `layer3_g4_weakest_boundary_ignored`
- `layer3_g4_limited_boundary_overpromoted`
- `layer3_g4_human_decision_required`
- `layer3_g4_human_decision_record_missing`
- `layer3_g4_high_stakes_human_decision_not_required_bypass`
- `layer3_g4_s7_manifest_only_human_decision`
- `layer3_g4_s2_ledger_ref_only_human_decision`
- `layer3_g4_human_decision_scope_mismatch`
- `layer3_g4_human_decision_inactive_choice`
- `layer3_g4_human_decision_five_rights_failed`
- `layer3_g4_human_decision_overrides_a_incompleteness`
- `layer3_g4_p26_responsibility_integrity_failed`
- `layer3_g4_promotion_record_missing`
- `layer3_g4_no_governed_promotion_record`
- `layer3_g4_no_blocked_negative_promotion_record`
- `layer3_g4_invalid_promotion_state`
- `layer3_g4_shared_promotion_state_vocabulary_dropped_shadow`
- `layer3_g4_closeout_consumer_gate_missing`
- `layer3_g4_pdc_compiler_consumer_gate_missing`
- `layer3_g4_g5_promotion_handoff_missing`
- `layer3_g4_pdc_compile_authority_leak`
- `layer3_g4_pdc_compiler_graph_rewrite_attempt`
- `layer3_g4_closeout_authority_leak`
- `layer3_g4_closeout_reader_rewrite_attempt`
- `layer3_g4_production_authority_leak`
- `layer3_g4_publication_authority_leak`
- `layer3_g4_approval_authority_leak`
- `layer3_g4_scorecard_authority_leak`
- `layer3_g4_useful_design_credit_leak`
- `layer3_g4_may_not_use_for_incomplete`
- `layer3_g4_public_raw_payload_leak`
- `layer3_g4_public_export_hook_overclaimed`
- `layer3_g4_policy_projection_authority_leak`
- `layer3_g4_public_surface_visibility_missing`
- `layer3_g4_generated_artifacts_family_missing`
- `layer3_g4_inventory_surface_missing`
- `layer3_g4_reference_index_missing`
- `layer3_g4_adapter_contract_registry_missing`
- `layer3_g4_adapter_registry_summary_only`
- `layer3_g4_registry_ratchet_delta_missing`
- `layer3_g4_promotion_gate_admission_maturity_invalid`
- `layer3_g4_promotion_gate_admission_without_conformance`
- `layer3_g4_manifest_runtime_drift`
- `layer3_g4_persisted_artifact_missing`
- `layer3_g4_import_laziness_violation`
- `layer3_g4_unbounded_artifact_scan`

## Acceptance Checklist

Implementation is ready to claim G4 complete only when:

- [ ] G4 runtime module exists with strict DTOs and no eager heavy imports.
- [ ] G4 readiness CLI exists and follows G1/G2/G3/GL write/validate
      conventions.
- [ ] Shared promotion-state vocabulary remains `shadow`, `governed_promoted`,
      `promotion_blocked`; final G4 promotion records use only
      `governed_promoted` or `promotion_blocked`.
- [ ] G0 and G1 dependency gates pass.
- [ ] Source design-record resolution is replayable and carries a digest; an
      unresolved S2 ref blocks promotion.
- [ ] Resolver distinguishes `full_payload`, `ref_only`, `manifest_only`, and
      `unresolved` source design-record states; ref-only or manifest-only states
      cannot promote.
- [ ] G2/G3/GL are consumed as context and required only when the promotion scope
      requires their contract families.
- [ ] Promotion input set binds a shadow design/candidate to explicit claim,
      envelope, scope, and required contract families.
- [ ] Grounded contract set resolves actual upstream contract rows, not readiness
      summaries.
- [ ] G4 resolver validates the real family-specific artifact shapes and does not
      rerun upstream builders in the promotion decision path.
- [ ] A-completeness blocks missing, stale, reissue-required, or conformance-failed
      dependencies.
- [ ] Weakest-boundary composition is deterministic and preserves limitations.
- [ ] High-stakes/value-laden promotion requires S7/HumanDecisionRecord; missing
      or bypassed human-decision evidence emits an explicit typed blocker.
      `human_decision_not_required` is only valid for non-high-stakes bounded
      scopes.
- [ ] S7 manifest pass, W12D manifest pass, and S2 delegation ledger refs alone
      do not satisfy the G4 human-decision gate.
- [ ] Human decision cannot override missing A-completeness.
- [ ] At least one `PromotionRecord` is `governed_promoted`.
- [ ] At least one negative `PromotionRecord` is `promotion_blocked`.
- [ ] Every G4 authority boundary carries the complete G4 `may_not_use_for`
      deny-list for production, claim, source-data, recommendation, closeout,
      scorecard, approval, and pre-G5 useful-design authority.
- [ ] Closeout consumer gate reads promotion state without minting closeout,
      approval, production, publication, or useful-design credit.
- [ ] PDC compiler consumer gate and G5 handoff read promotion state without
      rewriting Layer 2 authority or minting G5 conversion.
- [ ] GL G4-compatibility pass is treated as read-compatibility only, not legal
      authority.
- [ ] PUBLIC/REVIEWER/EXPERT/MACHINE surfaces expose promotion state and envelope
      safely.
- [ ] Public projection mode is `projection_only`; public-export hook status is
      truthful and reference-only unless an actual hook was implemented.
- [ ] Runtime HTTP `PromotionLane`, `/data/promotion`, generated-artifact
      `promotion_target`, and release promotion gates are treated as naming
      collisions, not G4 promotion mechanisms.
- [ ] Governance-throughput delta records admitted/blocked/stalled/human-routed
      promotion attempts.
- [ ] Registry/ratchet delta records G4 gate admission maturity, conformance refs,
      and movement from missing capability labels to implemented.
- [ ] Generated artifacts are persisted and registered in generated-artifact
      TOML/docs, policy-design-case inventory, and reference/public-surface docs
      where required.
- [ ] Conformance negatives fail closed.
- [ ] Targeted tests, readiness CLI, architecture guardrails, and backend verify
      pass or failures are explicitly unrelated.

## Non-Negotiables

- G4 promotes to governed only; never production, rollout, publication, approval,
  scorecard, closeout, or useful-design credit.
- No shadow self-promotion.
- No readiness-summary-only promotion.
- No search-ledger/frontier-only promotion.
- No promotion without actual upstream grounded contract refs.
- No promotion from unresolved source design-record refs or missing replay digest.
- No promotion from source design-record ref-only, W12D manifest-only, or S2
  manifest-only evidence.
- No upstream builder rerun as the promotion decision mechanism.
- No human approval override of A-incompleteness.
- No `human_decision_not_required` bypass for high-stakes, value-laden,
  ranked-value, accountability-sensitive, or out-of-routine promotion.
- No S7 manifest, S7 corpus summary, or S2 delegation ledger ref as a substitute
  for a concrete case-specific S7 posture/HumanDecisionRecord payload.
- No legal/mandate promotion while GL reports reissue-required or unresolved
  reference lineage for the promoted legal purpose.
- No weakest-boundary override.
- No new promotion-state lattice beyond `governed_promoted` and
  `promotion_blocked` as final G4 outcomes; do not drop shared pre-gate `shadow`
  from the Layer 3 promotion vocabulary.
- No recursive repo scans or domain-corpus full scans in the G4 request path.
- No raw upstream payloads in PUBLIC output.
- No public-export hook overclaim; projection refs alone are not public-export
  integration.
- No reuse of runtime HTTP `PromotionLane`, `/data/promotion` APIs, generated
  artifact `promotion_target`, or release promotion gates as G4.
- No PDC compiler graph rewrite or narrow-waist mutation in G4.
- No closeout-reader rewrite to make promotion look like closeout evidence.
- No changes to production approval/closeout semantics to make G4 look green.
