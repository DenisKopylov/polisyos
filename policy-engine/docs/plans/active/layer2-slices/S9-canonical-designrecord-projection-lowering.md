---
title: PolicyOS Layer 2 S9 Canonical DesignRecord Projection/Lowering Implementation Plan
status: active
owner: team-runtime-quality
created: 2026-06-02
last_verified: null
stability: draft
revision_note: updated 2026-06-02 to require matured canonical record, lowering append artifacts, revision-aware projection grammar, and explicit faithfulness denominator
slice: S9
slice_label: canonical_designrecord_projection_lowering
roadmap: ../POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER2_IMPLEMENTATION_PLAN.md
source_design_doc: ../../../system-design-decisions/universal-policy-design-target-architecture-and-gap.md
cluster_ownership_map: ../../../../architecture/policy_design_case/cluster_ownership_map.toml
slice_cell_matrix: ../../../../architecture/policy_design_case/layer2_slice_cell_matrix.toml
floor_governance: ../../../../architecture/policy_design_case/layer2_floor_governance.toml
artifact_traceability: ../../../../architecture/policy_design_case/layer2_artifact_traceability.toml
failure_patterns: ../../../reference/policy-design-case-failure-patterns.md
depends_on:
  - S2
  - S5
  - S8
cells_closed: []
layer_cells_advanced:
  - DESIGNER_ITSELF.closeout_projection_ratchet
expected_current_open_cell_count: 3
floor_id: s9_projection_faithfulness
floor_metric: projection_faithfulness_pass_rate
---

# Layer 2 S9 - Canonical DesignRecord, Projection Faithfulness, And Governed Lowering

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

Read this whole file before editing. Execute the tasks in order, keep commits
task-sized, and preserve the repo rule that projections are views over runtime
truth, never substitutes for authority. S9 advances the existing
`DESIGNER_ITSELF.closeout_projection_ratchet` layer and the
`s9_projection_faithfulness` floor. It does **not** reduce the current open cell
count below `3`, and it does not mark S10 prediction, S11 calibration,
S12 envelope growth, S13 accountability, production authority, or S14
universality as implemented.

## Goal

S9 matures the S2 `DesignRecordV0` narrow waist into a replay-frozen
`CanonicalDesignRecord` that carries the graph/evidence/value/axis/assurance/
limitation/lowering substrate needed for faithful projection and governed
lowering. A request may ask for a public brief, reviewer view, expert dossier,
machine contract, or deeper legal/budget/procedure lowering, but every output
must be either a faithful projection of the canonical record or a governed
lowering request that re-enters verification.

The closure contract is the S9 roadmap contract:

- producer: canonical design record plus projection/lowering records over it.
- persisted artifact: projection render refs, faithfulness proofs, lowering
  request/gate records, and appended verified lowering artifacts.
- bridge/consumer: projection request -> faithful render, or lowering request ->
  authority gate and reissue/reopen route.
- surface: PUBLIC, REVIEWER, EXPERT, and MACHINE projections.
- semantic test: a public projection dropping a load-bearing limitation fails
  faithfulness.
- negative control: prose adding a claim absent from the record is rejected;
  legal/budget/procedure lowering without grounding is blocked while shallow
  projection remains allowed.
- floor: `projection_faithfulness_pass_rate` is recorded from the governed
  floor table and false-clear counts are zero.

## Architecture

S9 is a runtime-quality layer over existing PDC and projection substrates:

- `src/polisyos/pdc/_impl/layer2_readiness.py` already defines strict
  `DesignRecordV0`, `AxisPositionDeclaration`, `AxisFirewallStatus`,
  `CertifiedOperationEnvelope`, and `AuthorityBoundary`.
- S9 adds a neutral `CanonicalDesignRecord` in `polisyos.pdc`. It wraps and
  matures `DesignRecordV0`; it does not rename, remove, or mutate the S2 v0
  contract.
- `src/polisyos/pdc/_impl/layer2_design_search.py` already emits
  `DesignRecordV0`, search ledgers, and audience projections for S2/S4/S5/S6/S7/S8
  signals.
- `src/polisyos/runtime/quality/projection_semantics.py` already enforces
  projection-only authority boundaries for Policy Design Case projections.
- `src/polisyos/runtime/quality/public_export.py` already treats public export
  as redacted projection and verifies projection consumer contracts.
- S9 adds the Layer 2 projection/lowering producer in
  `src/polisyos/runtime/quality/layer2_projection_lowering.py` and exports the
  strict contracts from `polisyos.runtime.quality`.

S9 must wire existing projection semantics instead of replacing them. Its new
producer records the projection grammar expression
`audience x aspect x depth x redaction x format x revision`, verifies that
rendered output does not add claims, invert tradeoffs, hide load-bearing
blockers/limitations, or make shadow candidates look approved, and blocks
lowering requests unless the requested depth is already grounded or a
reissue/reopen path is recorded.

Boundary rule: the dependency direction is S9 runtime-quality -> PDC contracts,
not PDC search -> S9 producer. `polisyos.pdc` may define/export
`CanonicalDesignRecord` and may pass S9 source refs through projection contexts,
but `src/polisyos/pdc/_impl/layer2_design_search.py` must not import
`polisyos.runtime.quality.layer2_projection_lowering` or call S9 producer
helpers. This mirrors the S8 B-side import firewall.

## Scope

In scope:

- strict Pydantic S9 runtime-quality contracts exported from
  `polisyos.runtime.quality`.
- a neutral strict `CanonicalDesignRecord` exported from `polisyos.pdc`, with
  runtime-quality helper exports for S9 consumers.
- projection grammar requests over audience, aspect, depth, redaction, and
  format, plus revision/reissue semantics.
- faithfulness verification against `DesignRecordV0` and its ledger refs,
  axis positions, firewall statuses, authority boundary, envelope, and S8 value
  refs.
- faithfulness verification against the matured `CanonicalDesignRecord` fields:
  recursive design graph refs, claim-bound evidence portfolio refs,
  Pareto/tradeoff/value-choice refs, assurance-case refs, limitations,
  abstentions, and already-produced lowering artifacts.
- typed public/reviewer/expert/machine projection render records.
- lowering request records for legal diff, budget package, implementation
  procedure, monitoring protocol, and machine contract depths.
- lowering artifact records and append receipts for allowed lowering that
  re-enters search/verify.
- lowering authority gates that block deeper output when mandate, capacity,
  measurability, value provenance, coupling, or closeout/reissue authority is
  missing.
- post-closeout lowering behavior: already-in-scope lowering may replay from
  frozen refs; new lowering requires reopen/reissue.
- a reusable faithfulness verifier surface that can later be applied to
  system self-description or universality-claim projections, while S9 itself
  denies any universal/product/production claim unless future S14 authority refs
  are present.
- canonical corpus route with S9 blocks for all 13 W12.D cases.
- repo-quality manifest, inventory, floor, traceability, and validator coverage.

Out of scope:

- executable law, budget, procurement, or procedure generation as production
  artifacts.
- S10 outcome prediction or welfare forecasting.
- S11 calibration, proof-carrying analytics, or predictive upgrades.
- S12 certified envelope growth.
- S13 post-deploy accountability.
- S14 universality battery closure.
- any production recommendation, rollout, publication, claim, approval, or
  closeout authority granted by projection text.

## Pattern Pass

Open the failure register before implementation and before closeout:
`docs/reference/policy-design-case-failure-patterns.md`.

| Pattern | S9 risk | Closure move |
| --- | --- | --- |
| P01 contract-only capability | Existing projection contracts exist, but S9 has no Layer 2 projection/lowering producer, manifest, or corpus floor. | Add producer, persisted projection/lowering records, corpus route, manifest, readiness checks, and semantic tests. |
| P03 hidden internal richness | DesignRecord and closeout truth may exist internally while public output hides blockers or limitations. | All four audience surfaces must preserve required truth; PUBLIC gets pull-first summary plus limitation/omission manifest. |
| P04 status lattice gap | `projection_only`, `lowering_required`, `lowering_blocked`, and `faithfulness_failed` can drift from existing status composition. | Keep local S9 statuses mapped to existing projection and closeout states; add mixed-status tests. |
| P05 authority boundary leak | Rendered prose, dashboard text, or public export can look like claim/recommendation authority. | Every S9 artifact carries projection-only or governed-lowering authority boundaries and `may_not_use_for` enforcement. |
| P07 replay gap | Post-closeout lowering can mutate or reinterpret closed cases. | Persist source refs, rule versions, source revision refs, projection request refs, faithfulness proofs, and lowering append receipts; new lowering after closeout requires reissue/reopen. |
| P10 semantic adequacy gap | Field-presence checks miss omissions, added claims, or hidden value limitations. | Red-first semantic tests compare rendered content to record truth and negative probes. |
| P13 contract gravity | Projection algebra can grow into a product taxonomy. | Keep grammar dimensions small and typed; do not enumerate every report product. |
| P15 candidate laundering | LLM-written public prose can become authority. | Candidate text is rendered/verified only; added claims fail faithfulness. |
| P25 search-control laundering | A projection can imply the S2/S5/S8 frontier is exhaustive or production-ready. | Preserve `search_incomplete`, shadow posture, and authority boundary in every audience projection. |

Capability label transition:

- start: `DESIGNER_ITSELF.closeout_projection_ratchet` is already
  `implemented`, but the S9 Layer 2 projection/lowering floor is
  `verification_missing` / `semantic_test_missing`.
- target: S9 layer is `implemented` with no open-cell count reduction.
- missing chain to close: producer, persisted artifact, bridge/consumer,
  verification, surface, semantic test, and negative controls.

## Code-Grounded Reality Check

Current S9 anchors:

- `architecture/policy_design_case/layer2_floor_governance.toml` defines
  `floor_id = "s9_projection_faithfulness"`,
  `metric = "projection_faithfulness_pass_rate"`, owner
  `team-runtime-quality`, and revision rule
  `faithfulness_negative_controls_required`.
- `architecture/policy_design_case/layer2_slice_cell_matrix.toml` assigns no
  remaining open cell to S9. The roadmap names
  `DESIGNER_ITSELF.closeout_projection_ratchet`, but the cluster map already
  has that cell as `implemented`. S9 must not pretend to burn down one of the
  three remaining open cells.
- `architecture/policy_design_case/cluster_ownership_map.toml` currently has
  `[cell.DESIGNER_ITSELF.closeout_projection_ratchet]` implemented with
  projection semantics, closeout reader, BERL, corpus, and ratchet seed files.
- `architecture/policy_design_case/layer2_artifact_traceability.toml` has
  `DesignRecord` under S0 as `v0_schema`; it does not yet contain S9 artifacts
  such as projection grammar, faithfulness record, or lowering gate.
- `src/polisyos/pdc/_impl/layer2_readiness.py` defines strict `DesignRecordV0`
  but no matured `CanonicalDesignRecord` or S9 projection/lowering records.
- `src/polisyos/pdc/_impl/layer2_design_search.py` has
  `project_s2_design_search(...)` and public projection assertions for S4/S5/S6/S7/S8,
  but no persisted S9 faithfulness proof or lowering gate.
- `src/polisyos/pdc/_impl/layer2_design_search.py` already uses injected
  posture inputs for S6/S7/S8 and deliberately avoids importing the S8
  runtime-quality producer. S9 should preserve this pattern: projection context
  may be injected, producer authority stays outside B-side search.
- `src/polisyos/runtime/quality/projection_semantics.py` already verifies that
  Policy Design Case projections are `projection_only` and preserve closeout
  truth across consumers.
- `src/polisyos/runtime/quality/public_export.py` already treats public export
  as a redacted projection over runtime truth.
- `src/polisyos/runtime/quality/projection_semantics.py` already has
  `verify_policy_design_case_projection_consumer_contract(...)`; S9 should call
  or adapt this verifier for closeout truth, blockers, omissions, contested
  records, and machine refs, then add only the S9-specific checks it does not
  cover: revision mismatch, tradeoff direction, shadow approval spoof, added
  canonical-record claims, and lowering gate/append boundaries.
- `src/polisyos/runtime/quality/public_export.py` already stores
  `projection_semantics`, `semantic_audit.omission_manifest`, `audit_refs`, and
  public revision states. S9 should add faithfulness/lowering refs into these
  existing audit surfaces instead of inventing a second public-export envelope.
- `src/polisyos/runtime/quality/layer2_value_choice.py` is the nearest
  producer template: strict `Layer2ReadinessModel` contracts, deterministic
  digest/CAS persistence, integrity report, false-clear counts, and manifest
  tests. S9 should copy that shape rather than create a separate persistence
  abstraction.
- `tools/quality/validation/check_policy_design_case_layer2_readiness.py` now
  validates S8 through constants, payload loader entries, summary fields,
  manifest/inventory count checks, traceability rows, false-clear fields, and
  runtime negative probes. S9 Task 5 must add the same concrete validator
  scaffolding; otherwise the manifest can exist without being governed.

## Code-Grounded Workload Boundaries

Use these boundaries to avoid both underestimating and overbuilding S9:

- Strong substrate: `Layer2ReadinessModel` already gives strict/frozen Pydantic
  behavior. `CanonicalDesignRecord` should extend this base; no new DTO base is
  needed.
- Strong substrate: S2 `DesignRecordV0` already carries axis positions,
  firewall statuses, envelope, ledger refs, authority boundary, and audience
  set. Do not mutate V0 or force every S9 ref into `DesignRecordV0.ledger_refs`
  because that field is bounded to 40 refs; use grouped fields on
  `CanonicalDesignRecord`.
- Strong substrate: S2 public projection already has S4/S5/S6/S7/S8 assertion
  helpers. S9 should reuse those surfaces and add a thin S9 context/verification
  layer; it should not rewrite the S2 projection engine.
- Strong substrate: W12.D already computes S4 -> S5 -> S6 -> S7 -> S8 -> S2 for
  the pinned case. Insert S9 after `_s2_design_search_summary(...)`, where both
  the S2 design record and S8 value block are available.
- Weak spot: no current object records `source_revision_ref`,
  `canonical_design_record_digest`, or lowering append receipts. Those are real
  additions, not fixture-only fields.
- Weak spot: existing projection semantics verifies closeout/omission/contested
  truth but not value-tradeoff direction, shadow-approval wording, or
  canonical-record claim addition. S9 must add those semantic probes.
- Weak spot: readiness inventory count is currently `16` after S8. S9
  registration should raise the governed Layer 2 inventory artifact count to
  `17`, while the cluster-map open cell count remains `3`.
- Complexity guard: avoid a legal/budget/procedure generator. S9 only emits a
  `LoweringArtifactRecord` for already-grounded synthetic corpus lowering, plus
  append receipt and replay refs; deeper real artifacts remain out of scope.

## Source Of Truth

S9 closure is measured against these exact rows and constraints:

- slice: `S9`.
- layer cell advanced: `DESIGNER_ITSELF.closeout_projection_ratchet`.
- open-cell delta: `0`; expected current open cell count remains `3`.
- governed Layer 2 inventory artifact count after S9: `17`.
- remaining open cells stay exactly:
  - `DESIGNER_ITSELF.envelope_growth`
  - `KNOWLEDGE.calibration`
  - `KNOWLEDGE.ir_proof_carrying_analytics`
- floor: `s9_projection_faithfulness`.
- floor metric: `projection_faithfulness_pass_rate`.
- owner: `team-runtime-quality`.
- implementation prerequisites: S2 design record/search ledger, S5 composition
  refs, and S8 value-choice refs.
- design-doc contract: D3.9 projection vs lowering distinction.
- roadmap closure: projection/lowering corpus passes, including faithfulness
  and blocked-lowering negative controls.
- faithfulness floor denominator: all generated projection renders across the
  13-case corpus, with a minimum denominator of `13 * 4 = 52` for
  PUBLIC/REVIEWER/EXPERT/MACHINE projections. Lowering gate counts are recorded
  separately and must not be folded into the projection denominator.

## Files

Expected new files:

- `src/polisyos/runtime/quality/layer2_projection_lowering.py`
- `tests/unit/runtime/quality/test_layer2_s9_projection_lowering.py`
- `tests/fixtures/layer2/s9/s9_projection_lowering_case_signals.json`
- `tests/fixtures/layer2/s9/s9_projection_lowering_expert_labels.json`
- `tests/fixtures/layer2/s9/public_projection_missing_limitation_probe.json`
- `tests/fixtures/layer2/s9/prose_added_claim_probe.json`
- `tests/fixtures/layer2/s9/legal_lowering_without_grounding_probe.json`
- `tests/fixtures/layer2/s9/projection_mints_authority_probe.json`
- `tests/fixtures/layer2/s9/redaction_hides_blocker_probe.json`
- `tests/fixtures/layer2/s9/post_closeout_lowering_without_reissue_probe.json`
- `tests/fixtures/layer2/s9/machine_projection_missing_refs_probe.json`
- `tests/fixtures/layer2/s9/tradeoff_inversion_probe.json`
- `tests/fixtures/layer2/s9/shadow_candidate_approved_probe.json`
- `tests/fixtures/layer2/s9/universal_self_claim_without_s14_probe.json`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s9_projection_lowering.py`
- `architecture/policy_design_case/layer2_s9_projection_lowering_manifest.json`

Expected edited files:

- `src/polisyos/runtime/quality/__init__.py`
- `src/polisyos/pdc/_impl/layer2_readiness.py`
- `src/polisyos/pdc/__init__.py`
- `src/polisyos/pdc/_impl/layer2_design_search.py`
- `src/polisyos/runtime/quality/projection_semantics.py`
- `src/polisyos/runtime/quality/public_export.py`
- `tools/quality/validation/run_universal_outcome_corpus.py`
- `tools/quality/validation/check_policy_design_case_layer2_readiness.py`
- `architecture/policy_design_case/layer2_artifact_traceability.toml`
- `architecture/policy_design_case/inventory.json`
- `tests/unit/pdc/test_layer2_readiness_contracts.py`
- `tests/unit/pdc/test_layer2_s2_design_search.py`
- `tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py`
- `tests/unit/runtime/quality/test_public_export.py`
- `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s6_blind_spot_firewalls.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s7_delegation.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s8_value_choice.py`
- `tests/repo_quality/tools/test_policy_design_case_layer2_s9_projection_lowering.py`

## Task 1: Red-First S9 Semantic And Negative Tests

Intent: prove the current repo fails the S9 semantic contract before adding the
producer. The initial failure should be missing imports, missing fields, or
assertion failures around absent S9 projection/lowering blocks. Do not weaken
existing projection-only tests.

- [ ] **Step 1: Add runtime-quality red tests**

Create `tests/unit/runtime/quality/test_layer2_s9_projection_lowering.py` with
these tests:

- `test_s9_projection_contracts_are_strict_replayable_and_exported`
- `test_canonical_design_record_contains_graph_evidence_assurance_limitations_and_lowering_refs`
- `test_projection_grammar_request_covers_audience_aspect_depth_redaction_format_revision`
- `test_public_projection_missing_load_bearing_limitation_fails_faithfulness`
- `test_prose_adding_claim_absent_from_design_record_is_rejected`
- `test_tradeoff_inversion_fails_faithfulness`
- `test_shadow_candidate_cannot_render_as_approved`
- `test_legal_lowering_without_grounding_is_blocked_while_public_projection_passes`
- `test_allowed_lowering_persists_verified_append_receipt`
- `test_machine_projection_preserves_refs_authority_boundary_and_omission_manifest`
- `test_post_closeout_lowering_requires_reissue_or_reopen`
- `test_projection_cannot_mint_claim_scorecard_or_closeout_authority`
- `test_s9_integrity_report_records_false_clear_counts`

The tests must instantiate strict records and fail on extra fields. Use the S8
contract style: exact authority purpose and source refs matter. A projection may
redact fields, but it must carry an omission manifest for load-bearing blockers,
limitations, value conflicts, and authority boundaries.

- [ ] **Step 2: Add PDC design-record red tests**

Extend `tests/unit/pdc/test_layer2_readiness_contracts.py` with:

- `test_canonical_design_record_requires_full_narrow_waist_refs_for_s9`
- `test_canonical_design_record_preserves_v0_shadow_projection_status`
- `test_design_record_maturity_report_requires_s2_s5_s8_refs_for_s9`

Extend `tests/unit/pdc/test_layer2_s2_design_search.py` with:

- `test_s2_projection_feed_carries_s9_source_refs_without_authority`
- `test_s2_public_projection_remains_shadow_when_s9_projection_passes`
- `test_s2_machine_projection_exposes_s9_faithfulness_and_lowering_boundary`
- `test_s2_does_not_import_s9_projection_lowering_producer`

Expected initial failure: `CanonicalDesignRecord`,
`DesignRecordMaturityReport`, and S9 projection source refs are absent.

- [ ] **Step 3: Add projection/public-export red tests**

Extend `tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py`
with:

- `test_s9_projection_semantics_reuses_pdc_consumer_contract_for_closeout_truth`
- `test_s9_projection_faithfulness_rejects_missing_closeout_blocker`
- `test_s9_projection_faithfulness_rejects_added_public_claim`
- `test_s9_projection_faithfulness_rejects_tradeoff_inversion`
- `test_s9_projection_faithfulness_rejects_shadow_candidate_as_approved`
- `test_s9_projection_faithfulness_preserves_contested_and_deficit_records`

Extend `tests/unit/runtime/quality/test_public_export.py` with:

- `test_public_export_requires_s9_faithfulness_pass_for_projection_release`
- `test_public_export_blocks_s9_projection_that_hides_redacted_blocker`
- `test_public_export_without_s9_block_keeps_existing_projection_behavior`

Expected initial failure: public export and projection semantics do not know the
S9 faithfulness proof fields yet.

- [ ] **Step 4: Add canonical corpus route red tests**

Extend `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py` with:

- `test_w12d_emits_s9_projection_lowering_blocks_for_13_cases`
- `test_w12d_s9_negative_controls_have_zero_false_clears`
- `test_w12d_s9_public_projection_faithfulness_preserves_load_bearing_limits`
- `test_w12d_s9_lowering_blocks_deeper_output_without_grounding`
- `test_w12d_s9_preserves_s2_shadow_only_and_s8_value_context_boundaries`

- [ ] **Step 5: Add repo-quality red tests**

Create `tests/repo_quality/tools/test_policy_design_case_layer2_s9_projection_lowering.py`
with:

- `test_layer2_s9_manifest_is_valid_and_open_count_stays_3`
- `test_layer2_s9_required_artifacts_are_traceable_and_exported`
- `test_layer2_s9_inventory_registration_exists`
- `test_layer2_s9_floor_is_governed_without_denominator_change`
- `test_layer2_s9_inventory_count_is_17_after_registration`
- `test_layer2_s9_b_side_does_not_import_projection_lowering_producer`
- `test_layer2_s9_projection_laundering_negative_controls_fail_closed`
- `test_layer2_s9_verifier_reuse_blocks_universal_self_claim_without_s14_refs`
- `test_layer2_s9_does_not_mark_s10_s11_s12_s13_or_s14_implemented`

- [ ] **Step 6: Run the red S9 suite**

Expected failing command before implementation:

```bash
uv run pytest \
  tests/unit/runtime/quality/test_layer2_s9_projection_lowering.py \
  tests/unit/pdc/test_layer2_readiness_contracts.py \
  tests/unit/pdc/test_layer2_s2_design_search.py \
  tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py \
  tests/unit/runtime/quality/test_public_export.py \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s9_projection_lowering.py \
  -q
```

Expected red output:

- missing `polisyos.runtime.quality.layer2_projection_lowering` exports, or
- missing `CanonicalDesignRecord`, or
- missing `DesignRecordMaturityReport`, or
- missing `s9_projection_lowering` corpus block, or
- missing `layer2_s9_projection_lowering_manifest.json`.

- [ ] **Step 7: Commit Task 1**

Stop Task 1 after committing only tests. Do not stage implementation files.

```bash
git add tests/unit/runtime/quality/test_layer2_s9_projection_lowering.py \
  tests/unit/pdc/test_layer2_readiness_contracts.py \
  tests/unit/pdc/test_layer2_s2_design_search.py \
  tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py \
  tests/unit/runtime/quality/test_public_export.py \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s9_projection_lowering.py
git commit -m "test: add layer2 s9 projection-lowering red tests" \
  -m "Co-authored-by: Cursor <cursoragent@cursor.com>"
```

## Task 2: Contracts, Producer, Faithfulness Verifier, And Lowering Gate

Intent: implement the S9 A-side producer by maturing `DesignRecordV0` into a
neutral `CanonicalDesignRecord`, then wiring existing projection semantics into
a strict runtime-quality projection/lowering module.

- [ ] **Step 1: Add neutral canonical design record contract**

Modify `src/polisyos/pdc/_impl/layer2_readiness.py` and
`src/polisyos/pdc/__init__.py`.

Add `CanonicalDesignRecord` as the mature S9 narrow waist. It must be strict,
frozen, and replayable. Required fields:

- `schema_version`
- `record_id`
- `record_ref`
- `source_design_record_ref`
- `source_design_record_digest`
- `source_revision_ref`
- `canonical_design_record_revision_ref`
- `recursive_design_graph_refs`
- `claim_bound_evidence_portfolio_refs`
- `pareto_tradeoff_value_choice_refs`
- `axis_position_refs`
- `firewall_status_refs`
- `certified_envelope_ref`
- `search_ledger_refs`
- `counterexample_refinement_refs`
- `assurance_case_refs`
- `limitation_refs`
- `abstention_refs`
- `lowering_artifact_refs`
- `projection_audiences`
- `projection_status`
- `authority_boundary`
- `rule_version_ref`

`CanonicalDesignRecord` may wrap `DesignRecordV0`; it must not rename or remove
`DesignRecordV0`, mutate closed v0 refs, or grant production authority.
Do not put S9 runtime producer helpers in `polisyos.pdc`; keep PDC limited to
neutral contracts and B-side projection context fields.

- [ ] **Step 2: Add producer module**

Create `src/polisyos/runtime/quality/layer2_projection_lowering.py`.

Use `Layer2ReadinessModel` for all Layer 2 DTOs. Keep strict Pydantic defaults
from the base model and add field bounds. Public contracts:

- `CanonicalDesignRecord` helper export, imported from `polisyos.pdc`
- `ProjectionAlgebraRequest`
- `ProjectionRenderRecord`
- `ProjectionFaithfulnessRecord`
- `LoweringRequestRecord`
- `LoweringAuthorityGateRecord`
- `LoweringArtifactRecord`
- `LoweringAppendReceipt`
- `DesignRecordMaturityReport`
- `ProjectionLoweringIntegrityReport`

Public helpers:

- `build_projection_algebra_request`
- `build_projection_render_record`
- `verify_projection_faithfulness`
- `gate_lowering_request`
- `build_canonical_design_record`
- `build_design_record_maturity_report`
- `append_verified_lowering_artifact`
- `s9_projection_lowering_integrity`
- `persist_projection_lowering_bundle`

Required constants:

- `LAYER2_S9_PROJECTION_LOWERING_SCHEMA_VERSION =
  "policyos.policy_design_case.layer2_s9_projection_lowering.v1"`
- `LAYER2_S9_PROJECTION_LOWERING_RULE_VERSION =
  "policyos.layer2.s9.projection_lowering.v1"`
- `S9_PROJECTION_FLOOR_ID = "s9_projection_faithfulness"`

Persistence shape:

- import `artifacts` and `canon` the same way
  `src/polisyos/runtime/quality/layer2_value_choice.py` does when needed.
- `persist_projection_lowering_bundle(...)` must use deterministic
  `json.dumps(..., sort_keys=True, separators=(",", ":"))` hashing when no
  `FileSystemCAS` store is supplied.
- CAS writes, when a store is supplied, must use kind
  `policyos.layer2_s9.projection_lowering_bundle` and schema
  `policyos.layer2_s9.projection_lowering_bundle`.
- no new persistence abstraction should be introduced for S9.

- [ ] **Step 3: Define maturity, render, and faithfulness record fields**

`DesignRecordMaturityReport` must require:

- `design_record_ref`
- `canonical_design_record_ref`
- `design_record_schema_version`
- `canonical_design_record_schema_version`
- `source_revision_ref`
- `axis_position_refs`
- `firewall_status_refs`
- `ledger_refs`
- `assurance_case_refs`
- `limitation_refs`
- `abstention_refs`
- `lowering_artifact_refs`
- `projection_audiences`
- `missing_maturity_fields`
- `authority_boundary`
- `rule_version_ref`

`ProjectionRenderRecord` must require:

- `render_id`
- `render_ref`
- `request_ref`
- `canonical_design_record_ref`
- `canonical_design_record_digest`
- `source_revision_ref`
- `audience`
- `aspect`
- `depth`
- `redaction`
- `format`
- `rendered_claim_refs`
- `omission_manifest`
- `authority_boundary`
- `may_not_use_for`
- `rule_version_ref`

`ProjectionFaithfulnessRecord` must require:

- `faithfulness_id`
- `faithfulness_ref`
- `render_ref`
- `request_ref`
- `canonical_design_record_ref`
- `canonical_design_record_digest`
- `source_revision_ref`
- `faithfulness_status` in `pass | fail`
- `issue_codes`
- `added_claim_refs`
- `hidden_blocker_refs`
- `hidden_limitation_refs`
- `tradeoff_direction_status`
- `shadow_approval_status`
- `consumer_contract_ref`
- `authority_boundary`
- `rule_version_ref`

- [ ] **Step 4: Implement projection grammar request validation**

`ProjectionAlgebraRequest` must contain:

- `request_id`
- `request_ref`
- `source_design_record_ref`
- `source_design_record_digest`
- `canonical_design_record_ref`
- `canonical_design_record_digest`
- `operation` in `projection | lowering`
- `audience` in `PUBLIC | REVIEWER | EXPERT | MACHINE`
- `aspect` such as `tradeoff_brief`, `evidence_view`, `legal_diff`,
  `budget_package`, `procedure`, `machine_contract`
- `depth` such as `problem_frame`, `design_sketch`, `design_candidate`,
  `policy_program`, `legal_budget_procedure`
- `redaction` in `none | public_redacted | reviewer_private | machine_full`
- `format` such as `json`, `markdown`, `public_brief`, `machine_contract`
- `revision_policy` in `same_revision | reissue_required | reopen_required`
- `source_revision_ref`
- `reissue_ref`
- `requested_field_refs`
- `authority_boundary`
- `rule_version_ref`

Validation rules:

- `PUBLIC` cannot use `machine_full` redaction.
- `operation == "projection"` cannot request new legal/budget/procedure
  content absent from the source record.
- `operation == "lowering"` must create a `LoweringRequestRecord`.
- post-closeout requests with a new `source_revision_ref` must select
  `reissue_required` or `reopen_required`.

- [ ] **Step 5: Implement faithfulness verifier**

`verify_projection_faithfulness(...)` must compare a projection render against
source record truth:

- first adapt or call
  `verify_policy_design_case_projection_consumer_contract(...)` for closeout
  truth, blocker, omission-manifest, contested-state, and MACHINE ref checks
  when those fields are present.
- then apply S9-only checks over the `CanonicalDesignRecord`, value-tradeoff
  rows, revision refs, and lowering gate/append rows.
- preserve blocker codes, limitation codes, contested state, value-tradeoff
  disposition, S6/S7/S8 authority boundaries, and search incompleteness.
- reject `added_claim_refs` or claims absent from the source record.
- reject inverted tradeoff direction, hidden value-choice disposition, or
  rendered approval language for a shadow candidate.
- reject hidden load-bearing omissions unless `omission_manifest` names the
  omitted field, audience, reason, source ref, and publication effect.
- reject public projection that hides an S6/S8 blocker or contested value row.
- pass redaction only when the redaction is declared and non-authority-bearing.
- reject self-description or universality-claim projection payloads unless they
  cite a future S14 universality assurance ref; for S9 this path is verifier
  reuse only and must not mark S14 implemented.

Failure codes:

- `s9_public_projection_missing_limitation`
- `s9_projection_added_claim`
- `s9_projection_mints_authority`
- `s9_redaction_hides_blocker`
- `s9_machine_projection_missing_refs`
- `s9_tradeoff_inversion`
- `s9_shadow_candidate_rendered_as_approved`
- `s9_universal_self_claim_without_s14_refs`

- [ ] **Step 6: Implement lowering authority gate**

`gate_lowering_request(...)` must allow shallow projection while blocking
deeper lowering when grounding is missing. It must inspect:

- `DesignRecordV0.projection_status`
- `DesignRecordV0.authority_boundary`
- `AxisFirewallStatus` for S5/S6/S7/S8 cells
- `CertifiedOperationEnvelope.certified_for`
- `ledger_refs`
- rights, budget, and legal-access grounding refs where a legal/budget/procedure
  lowering depth is requested.
- `post_closeout_state`

Gate statuses:

- `projection_allowed`
- `lowering_allowed_existing_scope`
- `lowering_blocked_missing_grounding`
- `lowering_blocked_requires_reissue`
- `lowering_blocked_projection_only`

The gate must never return `production`, `rollout`, `publication`,
`recommendation`, `claim`, `approval`, or `closeout` authority.

- [ ] **Step 7: Implement verified lowering append receipts**

Allowed lowering must persist as a typed append, not just a gate status.
`append_verified_lowering_artifact(...)` must create:

- `LoweringArtifactRecord` with `artifact_ref`, `lowering_kind`,
  `source_canonical_design_record_ref`, `verification_ref`, `rule_version_ref`,
  and projection/authority limits.
- `LoweringAppendReceipt` with immutable `append_ref`, source revision,
  verification status, reissue/reopen refs when applicable, and replay refs.

The helper must reject append attempts when `LoweringAuthorityGateRecord.status`
is any blocked status.
At least one test and one corpus row must cover the allowed append path. Most
legal/budget/procedure probes should still block; one synthetic already-grounded
machine-contract or monitoring-protocol lowering is enough to prove the append
chain without generating production legal or budget artifacts.

- [ ] **Step 8: Export S9 public API**

Modify `src/polisyos/runtime/quality/__init__.py` to import and include in
`__all__` all S9 contracts, helpers, and constants. The export test from Task 1
must pass without importing private module paths.

- [ ] **Step 9: Run Task 2 tests**

```bash
uv run pytest \
  tests/unit/runtime/quality/test_layer2_s9_projection_lowering.py \
  tests/unit/pdc/test_layer2_readiness_contracts.py \
  -q
```

Expected green output:

```text
... passed
```

- [ ] **Step 10: Commit Task 2**

Commit message:

```bash
git add src/polisyos/runtime/quality/layer2_projection_lowering.py \
  src/polisyos/pdc/_impl/layer2_readiness.py \
  src/polisyos/pdc/__init__.py \
  src/polisyos/runtime/quality/__init__.py \
  tests/unit/runtime/quality/test_layer2_s9_projection_lowering.py \
  tests/unit/pdc/test_layer2_readiness_contracts.py
git commit -m "feat: add layer2 s9 projection faithfulness contracts" \
  -m "Co-authored-by: Cursor <cursoragent@cursor.com>"
```

## Task 3: Wire S9 Into DesignRecord Projection Context, Semantics, And Public Export

Intent: bridge S9 from strict contracts into consumers. Existing S2 projections
may remain a raw source, but the S9 consumer path must use a
`CanonicalDesignRecord` plus replay-visible faithfulness, revision, and lowering
append records.

- [ ] **Step 1: Expose canonical source context from S2/S5/S8 refs**

Modify `src/polisyos/pdc/_impl/layer2_design_search.py`.

The S2 run/projection path must expose a canonical source context without
granting B authority to certify it. Prefer an optional projection-context
argument or projection metadata block with a default of `None`; avoid changing
`Layer2S2DesignSearchRun` unless a focused test proves that the run contract
must carry the field.

Add source refs for:

- `canonical_design_record_ref`
- `canonical_design_record_digest`
- `canonical_design_record_schema_version`
- `canonical_design_record_revision_ref`
- `s9_projection_policy = "reads_canonical_design_record"`

The actual `CanonicalDesignRecord` must be built by the S9 runtime-quality
producer from `DesignRecordV0`, `SearchLedger`, S5 composition refs, S8
value-choice refs, existing closeout/assurance refs if present, and explicit
limitation/abstention refs. PDC may carry the refs and source digest; it must
not self-certify the record or faithfulness proof. Missing rich refs must be
recorded by S9 as `missing_maturity_fields`, not silently omitted.

Do not import S9 producer functions into B-side candidate generation. B can pass
refs into the S9 producer; B cannot self-certify projection faithfulness.
The Task 1 import-firewall test must read
`src/polisyos/pdc/_impl/layer2_design_search.py` and assert it does not contain:

- `runtime.quality.layer2_projection_lowering`
- `layer2_projection_lowering`
- `build_canonical_design_record`
- `verify_projection_faithfulness`

- [ ] **Step 2: Expose DesignRecord maturity report refs**

Use the `DesignRecordMaturityReport` produced in Task 2. Task 3 must pass its
refs through S2 projection context and public/export audit surfaces, but it must
not redefine the report contract or rebuild it inside B-side search.

- [ ] **Step 3: Add S9 source refs to S2 projection feed**

Modify `src/polisyos/pdc/_impl/layer2_design_search.py`.

The S2 run/projection path must expose:

- `s9_projection_source_ref`
- `s9_projection_policy = "reads_canonical_design_record"`
- `s9_projection_authority_boundary`
- `s9_lowering_boundary = "projection_only_until_grounded"`
- `s9_source_revision_ref`
- `s9_reissue_required`

If `project_s2_design_search(...)` needs S9 metadata, pass it as an input or
derive it from the canonical record refs only.

- [ ] **Step 4: Bridge S9 verifier into projection semantics**

Modify `src/polisyos/runtime/quality/projection_semantics.py`.

Add a small S9-compatible verifier entrypoint that accepts a
`ProjectionFaithfulnessRecord` or mapping. It must:

- require `faithfulness_status == "pass"` for public release.
- keep `authority_role == "projection_only"`.
- preserve `closeout_truth`, `projection_gaps`, `omission_manifest`,
  `contested_records`, `deficit_register`, and S8 value-tradeoff disclosures.
- preserve source revision refs and reject stale/revision-mismatched projection
  payloads unless a reissue/reopen path is present.
- fail if the projection source tries to satisfy `claim_authority`,
  `scorecard_authority`, or `runtime_closeout_authority`.

Implementation note: do not duplicate the existing PDC consumer-contract
verifier. Add a narrow adapter that converts S9 projection records into the
fields expected by `verify_policy_design_case_projection_consumer_contract(...)`
where possible, then appends S9-specific issue codes for revision/tradeoff/
shadow-approval/lowering checks.

- [ ] **Step 5: Bridge S9 verifier into public export**

Modify `src/polisyos/runtime/quality/public_export.py`.

When a public export receives `s9_projection_faithfulness` or an S9 projection
block:

- require pass status before release.
- include faithfulness refs in existing `projection_semantics.audit_refs` and
  `semantic_audit.audit_refs`.
- include omission manifest rows for redacted blockers through existing
  `semantic_audit.omission_manifest`.
- include source revision refs and lowering append refs when present.
- preserve projection-only authority limits.

Regression guard: public exports without any S9 block must keep the existing
behavior from `build_public_export_bundle(...)`. S9 pass/fail must be required
only when S9 faithfulness fields are present.

- [ ] **Step 6: Run Task 3 tests**

```bash
uv run pytest \
  tests/unit/pdc/test_layer2_s2_design_search.py \
  tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py \
  tests/unit/runtime/quality/test_public_export.py \
  -q
```

Expected green output:

```text
... passed
```

- [ ] **Step 7: Commit Task 3**

Commit message:

```bash
git add src/polisyos/pdc/_impl/layer2_design_search.py \
  src/polisyos/runtime/quality/projection_semantics.py \
  src/polisyos/runtime/quality/public_export.py \
  tests/unit/pdc/test_layer2_s2_design_search.py \
  tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py \
  tests/unit/runtime/quality/test_public_export.py
git commit -m "feat: wire layer2 s9 projection faithfulness into design records" \
  -m "Co-authored-by: Cursor <cursoragent@cursor.com>"
```

## Task 4: Canonical Corpus Route Wiring - 13-Case S9 Coverage

Intent: every W12.D corpus case must carry an S9 projection/lowering block, and
the pinned S2 case must prove that S9 preserves S2/S8 shadow and value
boundaries without granting production authority.

- [ ] **Step 1: Add S9 fixtures**

Create `tests/fixtures/layer2/s9/s9_projection_lowering_case_signals.json`.

Each of the 13 case rows must include:

- `case_id`
- `projection_request_refs`
- `source_design_record_ref`
- `source_design_record_digest`
- `canonical_design_record_ref`
- `source_revision_ref`
- `revision_policy`
- `required_audiences`
- `load_bearing_limitation_refs`
- `closeout_blocker_refs`
- `value_tradeoff_refs`
- `search_incompleteness_ref`
- `assurance_case_refs`
- `abstention_refs`
- `lowering_requested`
- `lowering_kind`
- `lowering_artifact_refs`
- `lowering_append_receipt_refs`
- `expected_lowering_gate_status`
- `expected_faithfulness_status`
- `post_closeout_state`

Create `tests/fixtures/layer2/s9/s9_projection_lowering_expert_labels.json`.

Coverage labels must include:

- `public_limitation_preserved`
- `reviewer_status_preserved`
- `expert_refs_preserved`
- `machine_refs_preserved`
- `legal_lowering_blocked_without_grounding`
- `budget_lowering_blocked_without_grounding`
- `procedure_lowering_reissue_required`
- `post_closeout_lowering_reissue_required`
- `redaction_omission_manifest`
- `revision_ref_preserved`
- `projection_only_authority_boundary`
- `s8_value_tradeoff_preserved`
- `s2_shadow_status_preserved`
- `tradeoff_direction_preserved`
- `shadow_approval_blocked`
- `universal_self_claim_blocked_without_s14`

- [ ] **Step 2: Add negative-control fixtures**

Create:

- `tests/fixtures/layer2/s9/public_projection_missing_limitation_probe.json`
- `tests/fixtures/layer2/s9/prose_added_claim_probe.json`
- `tests/fixtures/layer2/s9/legal_lowering_without_grounding_probe.json`
- `tests/fixtures/layer2/s9/projection_mints_authority_probe.json`
- `tests/fixtures/layer2/s9/redaction_hides_blocker_probe.json`
- `tests/fixtures/layer2/s9/post_closeout_lowering_without_reissue_probe.json`
- `tests/fixtures/layer2/s9/machine_projection_missing_refs_probe.json`
- `tests/fixtures/layer2/s9/tradeoff_inversion_probe.json`
- `tests/fixtures/layer2/s9/shadow_candidate_approved_probe.json`
- `tests/fixtures/layer2/s9/universal_self_claim_without_s14_probe.json`

Every probe must include:

- `case_id`
- `failure_pattern`
- `expected_disposition`
- `expected_false_clear: false`
- exact source/projection/lowering fields that trigger the block.

- [ ] **Step 3: Extend canonical corpus runner**

Modify `tools/quality/validation/run_universal_outcome_corpus.py`.

Add:

- `S9_CASE_SIGNALS_PATH`
- `S9_EXPERT_LABELS_PATH`
- `S9_NEGATIVE_CONTROL_PROBE_PATHS`
- `_s9_projection_lowering_summary(...)`
- `_s9_projection_lowering_case_block(...)`
- `_s9_negative_control_probe_results(...)`

Insertion point:

- add S9 imports near the S8 imports.
- in the per-case runner, build `s9_projection_lowering` after
  `_s2_design_search_summary(...)`, because S9 needs the serialized
  `s2_design_search.design_record`, `s2_design_search.search_ledger`, and
  `s8_value_choice` block.
- add top-level `"s9_projection_lowering": s9_projection_lowering` to each case
  and top-level `"s9_projection_lowering_summary"` to the corpus output.
- do not rerun S2 from inside S9; consume the already-built S2 summary.

Each case block must include:

- `schema_version = "policyos.policy_design_case.layer2_s9_projection_lowering.v1"`
- `projection_request_refs`
- `projection_render_refs`
- `projection_faithfulness_refs`
- `lowering_request_refs`
- `lowering_gate_refs`
- `lowering_artifact_refs`
- `lowering_append_receipt_refs`
- `canonical_design_record_ref`
- `source_revision_ref`
- `design_record_maturity_ref`
- `faithfulness_status`
- `lowering_gate_status`
- `canonical_outcome_effect = "none_projection_only_or_reissue_required"`
- `may_not_use_for` containing production/recommendation/claim/rollout/closeout
  authority.

- [ ] **Step 4: Extend W12.D tests**

The Task 1 W12.D tests must assert:

- all 13 cases contain `s9_projection_lowering`.
- all S9 case blocks preserve S2 `canonical_outcome_effect == "none_shadow_only"`.
- all S9 case blocks preserve S8 value context boundaries.
- all negative-control false-clear counts are zero.
- `projection_faithfulness_denominator >= 52`.
- all four audience projections are counted separately.
- lowering can be blocked while public projection passes.
- at least one case records `lowering_append_receipt_refs` and at least one
  blocked lowering case records no append receipt.

- [ ] **Step 5: Run Task 4 tests**

```bash
uv run pytest \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py \
  -q
```

Expected green output:

```text
... passed
```

- [ ] **Step 6: Commit Task 4**

Commit message:

```bash
git add tools/quality/validation/run_universal_outcome_corpus.py \
  tests/fixtures/layer2/s9 \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py
git commit -m "feat: classify layer2 s9 projection-lowering coverage" \
  -m "Co-authored-by: Cursor <cursoragent@cursor.com>"
```

## Task 5: S9 Manifest, Readiness Validator, Traceability, And Inventory

Intent: register S9 as a governed Layer 2 layer with a floor and manifest
without claiming any remaining open cells.

- [ ] **Step 1: Add S9 manifest**

Create `architecture/policy_design_case/layer2_s9_projection_lowering_manifest.json`.

Required fields:

- `schema_version = "policyos.policy_design_case.layer2_s9_projection_lowering_manifest.v1"`
- `status = "active"`
- `owner = "team-runtime-quality"`
- `slice = "S9"`
- `depends_on = ["S2", "S5", "S8"]`
- `cells_closed = []`
- `layer_cells_advanced = ["DESIGNER_ITSELF.closeout_projection_ratchet"]`
- `expected_current_open_cell_count = 3`
- `floor_id = "s9_projection_faithfulness"`
- `floor_metric = "projection_faithfulness_pass_rate"`
- `required_artifacts` listing exactly:
  - `CanonicalDesignRecord`
  - `ProjectionAlgebraRequest`
  - `ProjectionRenderRecord`
  - `ProjectionFaithfulnessRecord`
  - `LoweringRequestRecord`
  - `LoweringAuthorityGateRecord`
  - `LoweringArtifactRecord`
  - `LoweringAppendReceipt`
  - `DesignRecordMaturityReport`
  - `ProjectionLoweringIntegrityReport`
- `case_count = 13`
- `projection_render_count >= 52`
- `projection_faithfulness_denominator >= 52`
- `projection_faithfulness_numerator == projection_faithfulness_denominator`
- `projection_faithfulness_pass_rate = 1.0`
- `lowering_gate_count >= 13`
- `lowering_append_receipt_count >= 1`; the corpus must include at least one
  allowed lowering append receipt to prove the persisted lowering-artifact path.
- all S9 false-clear count fields set to `0`.
- `canonical_route = "tools/quality/validation/run_universal_outcome_corpus.py"`
- `validator = "tools/quality/validation/check_policy_design_case_layer2_readiness.py"`
- `authority_scope` limited to canonical design-record maturity,
  projection/lowering faithfulness, verified lowering append receipts, and
  reissue/reopen routing.
- `may_not_use_for` denying production, recommendation, rollout, publication,
  claim, closeout, approval, S10, S11, S12, S13, and S14 authority.

False-clear fields must include:

- `public_limitation_omission_false_clear_count`
- `added_prose_claim_false_clear_count`
- `tradeoff_inversion_false_clear_count`
- `shadow_candidate_approval_false_clear_count`
- `legal_lowering_without_grounding_false_clear_count`
- `projection_authority_laundering_false_clear_count`
- `redaction_hides_blocker_false_clear_count`
- `post_closeout_lowering_without_reissue_false_clear_count`
- `machine_ref_omission_false_clear_count`
- `revision_mismatch_false_clear_count`
- `universal_self_claim_without_s14_false_clear_count`

- [ ] **Step 2: Add artifact traceability rows**

Modify `architecture/policy_design_case/layer2_artifact_traceability.toml`.

Add S9 rows:

- `CanonicalDesignRecord`
- `ProjectionAlgebraRequest`
- `ProjectionRenderRecord`
- `ProjectionFaithfulnessRecord`
- `LoweringRequestRecord`
- `LoweringAuthorityGateRecord`
- `LoweringArtifactRecord`
- `LoweringAppendReceipt`
- `DesignRecordMaturityReport`
- `ProjectionLoweringIntegrityReport`

Set `slice = "S9"` and `maturity = "implemented"` only after Task 2-4 are
green.

- [ ] **Step 3: Register S9 inventory artifact**

Modify `architecture/policy_design_case/inventory.json`.

Add `layer2_s9_projection_lowering_manifest` with:

- `kind = "layer2_s9_projection_lowering_manifest"`
- `schema_version = "policyos.policy_design_case.layer2_s9_projection_lowering_manifest.v1"`
- `capability_reality_label = "implemented"`
- `authority_scope` matching the manifest.
- `may_not_use_for` matching the manifest.
- validator and canonical route paths.

- [ ] **Step 4: Extend readiness validator**

Modify `tools/quality/validation/check_policy_design_case_layer2_readiness.py`.

Add validator scaffolding near the existing S8 constants and loader entries:

- `DEFAULT_S9_PROJECTION_LOWERING_MANIFEST_PATH =
  Path("architecture/policy_design_case/layer2_s9_projection_lowering_manifest.json")`
- `S9_REQUIRED_ARTIFACTS`
- `S9_REQUIRED_AUTHORITY_SCOPE`
- `S9_REQUIRED_DENY`
- `S9_FALSE_CLEAR_FIELDS`
- `S9_INVENTORY_ID = "layer2_s9_projection_lowering_manifest"`
- `payloads["s9_projection_lowering"]` in `load_layer2_readiness_payloads(...)`
- `_validate_s9_projection_lowering(...)` called after `_validate_s8_value_choice(...)`
- S9 summary fields merged into `validate_layer2_readiness_payloads(...)`
- update the existing S8 inventory-count check from `16` to `17` after S9
  registration, without weakening any S8 value-choice artifact, firewall, or
  authority assertion.
- expose both flat false-clear fields such as
  `summary["s9_tradeoff_inversion_false_clear_count"]` and nested concise names
  such as `summary["s9_false_clear_counts"]["tradeoff_inversion"]`.

Validation must assert:

- S9 manifest exists and is registered in inventory.
- S9 case count is `13`.
- `projection_render_count >= 52`.
- `projection_faithfulness_denominator >= 52`.
- `projection_faithfulness_numerator == projection_faithfulness_denominator`.
- `projection_faithfulness_pass_rate == 1.0`.
- `lowering_gate_count >= 13`.
- `lowering_append_receipt_count >= 1` and matches persisted append receipts.
- all S9 false-clear counts are `0`.
- `expected_current_open_cell_count == 3`.
- `cells_closed == []`.
- `layer_cells_advanced` contains only
  `DESIGNER_ITSELF.closeout_projection_ratchet`.
- current open cells remain exactly:
  - `DESIGNER_ITSELF.envelope_growth`
  - `KNOWLEDGE.calibration`
  - `KNOWLEDGE.ir_proof_carrying_analytics`
- governed Layer 2 inventory artifact count is `17` after S9 registration.
- no S10/S11/S12/S13/S14 maturity is marked implemented by S9.

- [ ] **Step 5: Extend readiness repo-quality tests**

Modify `tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py`,
`tests/repo_quality/tools/test_policy_design_case_layer2_s6_blind_spot_firewalls.py`,
`tests/repo_quality/tools/test_policy_design_case_layer2_s7_delegation.py`,
`tests/repo_quality/tools/test_policy_design_case_layer2_s8_value_choice.py`,
and `tests/repo_quality/tools/test_policy_design_case_layer2_s9_projection_lowering.py`.

Assertions must include:

- `summary["s9_case_count"] == 13`
- `summary["s9_projection_render_count"] >= 52`
- `summary["s9_projection_faithfulness_denominator"] >= 52`
- `summary["s9_projection_faithfulness_numerator"] == summary["s9_projection_faithfulness_denominator"]`
- `summary["s9_projection_faithfulness_pass_rate"] == 1.0`
- `summary["s9_lowering_gate_count"] >= 13`
- `summary["s9_lowering_append_receipt_count"] >= 1`
- `summary["s9_false_clear_counts"]["tradeoff_inversion"] == 0`
- `summary["s9_false_clear_counts"]["shadow_candidate_approval"] == 0`
- `summary["s9_false_clear_counts"]["revision_mismatch"] == 0`
- `summary["s9_false_clear_counts"]["universal_self_claim_without_s14"] == 0`
- `summary["s9_expected_current_open_cell_count"] == 3`
- `summary["current_open_cell_count"] == 3`
- `summary["inventory_artifact_count"] == 17`
- the S6 repo-quality tests keep all S6 manifest/firewall/coverage assertions
  but update both existing `summary["inventory_artifact_count"] == 16` asserts
  to `17`.
- the S7 repo-quality test keeps all S7 manifest/delegation assertions but
  updates its existing `summary["inventory_artifact_count"] == 16` assert to
  `17`.
- the S8 repo-quality test keeps all S8 manifest/firewall/value assertions but
  expects `summary["inventory_artifact_count"] == 17`.
- remaining open cells are exactly `DESIGNER_ITSELF.envelope_growth`,
  `KNOWLEDGE.calibration`, and `KNOWLEDGE.ir_proof_carrying_analytics`.

- [ ] **Step 6: Run Task 5 validators and tests**

```bash
uv run python tools/quality/validation/check_policy_design_case_layer2_readiness.py
uv run python tools/quality/validation/check_policy_design_case_cluster_ownership_map.py
uv run pytest \
  tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s6_blind_spot_firewalls.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s7_delegation.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s8_value_choice.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s9_projection_lowering.py \
  -q
```

Expected output:

- both validator commands print `"status": "pass"` and `"issues": []`.
- pytest exits green.

- [ ] **Step 7: Commit Task 5**

Commit message:

```bash
git add architecture/policy_design_case/layer2_s9_projection_lowering_manifest.json \
  architecture/policy_design_case/layer2_artifact_traceability.toml \
  architecture/policy_design_case/inventory.json \
  tools/quality/validation/check_policy_design_case_layer2_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s6_blind_spot_firewalls.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s7_delegation.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s8_value_choice.py \
  tests/repo_quality/tools/test_policy_design_case_layer2_s9_projection_lowering.py
git commit -m "chore: register layer2 s9 projection maturity" \
  -m "Co-authored-by: Cursor <cursoragent@cursor.com>"
```

## Task 6: Repo-Quality Tests, Snapshots, And Burn-Down Confirmation

Intent: prove S9 is complete without weakening Layer 2 burn-down truth.

- [ ] **Step 1: Run focused S9 suite**

```bash
uv run pytest \
  tests/unit/runtime/quality/test_layer2_s9_projection_lowering.py \
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
  S9 metrics present, open cell count `3`.
- architecture guardrails: pass.
- runtime API contract: pass.

- [ ] **Step 3: Confirm no forbidden maturity claims**

Run:

```bash
rg -n "s10_forecast_support|s11_calibration|s12_envelope_growth|s13_accountability|s14_universality|production_authority|calibrated_prediction|rich_simulation|portfolio_optimization|preference_learning" \
  architecture/policy_design_case \
  src/polisyos \
  tests/repo_quality/tools/test_policy_design_case_layer2_s9_projection_lowering.py
```

Expected result:

- hits are allowed only in `may_not_use_for`, deny lists, negative assertions,
  roadmap text, or planned future-slice rows.
- no S9 manifest or readiness summary marks those capabilities implemented.

- [ ] **Step 4: Heavy suite policy**

Do not run the full backend pytest or benchmark lane locally if the machine is
thermally constrained. For final CI parity, use CI/cloud when available. The
local closeout evidence for S9 is the focused suite plus validators above; a
full backend run may be recorded as separate cloud evidence.

- [ ] **Step 5: Commit Task 6**

Commit message:

```bash
git status --short
git add src/polisyos/runtime/quality/layer2_projection_lowering.py \
  src/polisyos/runtime/quality/__init__.py \
  src/polisyos/pdc/_impl/layer2_readiness.py \
  src/polisyos/pdc/__init__.py \
  src/polisyos/pdc/_impl/layer2_design_search.py \
  src/polisyos/runtime/quality/projection_semantics.py \
  src/polisyos/runtime/quality/public_export.py \
  tools/quality/validation/run_universal_outcome_corpus.py \
  tools/quality/validation/check_policy_design_case_layer2_readiness.py \
  architecture/policy_design_case/layer2_s9_projection_lowering_manifest.json \
  architecture/policy_design_case/layer2_artifact_traceability.toml \
  architecture/policy_design_case/inventory.json \
  tests/unit/runtime/quality/test_layer2_s9_projection_lowering.py \
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
  tests/fixtures/layer2/s9
git commit -m "chore: verify layer2 s9 projection-lowering progress" \
  -m "Co-authored-by: Cursor <cursoragent@cursor.com>"
```

If `git status --short` shows unrelated user changes, stage only the S9 paths
above or use `git add -p` for touched files. Never use `git add .` in this
task.

## Task 7: Full S9 Verification Done When

S9 is complete only when all statements below are true:

- `CanonicalDesignRecord`, `ProjectionAlgebraRequest`, `ProjectionRenderRecord`,
  `ProjectionFaithfulnessRecord`, `LoweringRequestRecord`,
  `LoweringAuthorityGateRecord`, `LoweringArtifactRecord`,
  `LoweringAppendReceipt`, `DesignRecordMaturityReport`, and
  `ProjectionLoweringIntegrityReport` are strict, replayable, and exported from
  `runtime.quality`; `CanonicalDesignRecord` is also exported from `polisyos.pdc`.
- `CanonicalDesignRecord` contains recursive design graph refs, claim-bound
  evidence portfolio refs, Pareto/tradeoff/value-choice refs, axis/firewall
  refs, certified envelope refs, search ledger refs, counterexample/refinement
  refs, assurance-case refs, limitation refs, abstention refs, and lowering
  artifact refs without mutating `DesignRecordV0`.
- S9 consumes S2 `DesignRecordV0`, `SearchLedger`, axis positions, firewall
  statuses, authority boundary, envelope, and ledger refs without upgrading
  `projection_status` out of shadow/advisory.
- S9 consumes S5 composition refs and S8 value-choice refs where present, and
  preserves their limitations and authority boundaries in projection.
- `src/polisyos/pdc/_impl/layer2_design_search.py` does not import
  `polisyos.runtime.quality.layer2_projection_lowering`, does not call S9
  producer helpers, and only exposes/pass-throughs S9 source context.
- S9 projection semantics reuses/adapts the existing PDC projection consumer
  contract verifier for closeout truth, blocker, omission-manifest, contested
  state, and MACHINE ref checks instead of duplicating that logic.
- Projection grammar covers
  `audience x aspect x depth x redaction x format x revision` without
  hard-coding product-specific report templates.
- PUBLIC projection is pull-first and limitation-shaped: it may summarize, but
  cannot hide blockers, contested state, value-tradeoff disclosures,
  search incompleteness, or redaction omissions.
- REVIEWER projection shows projection disposition, faithfulness status,
  lowering gate status, action route, and P03/P05/P07/P10/P15/P25 statuses.
- EXPERT and MACHINE projections show all source refs, ledger refs, omitted
  refs, added-claim checks, faithfulness proof refs, lowering gate refs,
  authority boundary, rule version refs, and reissue/reopen disposition.
- A shallow projection can pass when deeper legal/budget/procedure lowering is
  blocked.
- Legal diff, budget package, implementation procedure, monitoring protocol,
  and machine contract lowering require grounding and cannot be produced from
  projection-only or shadow candidate authority.
- Post-closeout lowering cites an already-in-scope lowering artifact or records
  `lowering_blocked_requires_reissue`; it never mutates closed-case replay.
- Allowed lowering persists a replayable `LoweringArtifactRecord` plus immutable
  `LoweringAppendReceipt`; the corpus contains at least one allowed append
  receipt, and blocked lowering never creates an append receipt.
- Prose adding a claim absent from the canonical record is rejected.
- Prose inverting the direction of a tradeoff is rejected.
- Prose making a shadow candidate look approved is rejected.
- A stale or mismatched source revision is rejected unless a reissue/reopen path
  is recorded.
- Self-description or universality-claim projections without S14 assurance refs
  are rejected by verifier reuse; S9 does not implement S14.
- Redaction that hides a blocker without an omission manifest is rejected.
- Projection cannot satisfy claim, scorecard, approval, runtime closeout,
  rollout, publication, or production authority.
- All 13 corpus cases contain S9 blocks; the pinned S2 case records S9
  projection source refs while preserving S2 `canonical_outcome_effect` as
  shadow-only.
- W12.D builds S9 after the existing S2 summary and consumes the serialized S2
  and S8 blocks; it does not rerun S2 from inside S9.
- S9 precision/recall/integrity metrics include public limitation omission,
  added prose claim, tradeoff inversion, shadow candidate approval spoof, legal
  lowering without grounding, projection authority laundering, redaction hides
  blocker, post-closeout lowering without reissue, machine ref omission,
  revision mismatch, and universal self-claim without S14 triggers.
- Negative-control false-clear counts are zero.
- `projection_faithfulness_pass_rate` floor is recorded from the governed floor
  table; projection render count, numerator, and denominator are recorded with
  denominator at least `52`; lowering gate counts are separate; no denominator
  or floor is changed silently.
- Cluster-map open cell count remains `3`; both validators pass; S9 manifest is
  registered in inventory; governed Layer 2 inventory artifact count is `17`.
- Remaining open cells are exactly `DESIGNER_ITSELF.envelope_growth`,
  `KNOWLEDGE.calibration`, and `KNOWLEDGE.ir_proof_carrying_analytics`.
- No S10 forecast support, S11 calibration or proof-carrying analytics,
  S12 envelope growth, S13 accountability, production authority, calibrated
  prediction, rich simulation, portfolio optimization, preference learning, or
  S14 universality battery cell is marked implemented.

## Commit Guidance

Mirror the S4/S5/S6/S7/S8 red-first sequence, one logical commit per task:

```text
test: add layer2 s9 projection-lowering red tests
feat: add layer2 s9 projection faithfulness contracts
feat: wire layer2 s9 projection faithfulness into design records
feat: classify layer2 s9 projection-lowering coverage
chore: register layer2 s9 projection maturity
chore: verify layer2 s9 projection-lowering progress
```

End commit messages with the repo's standard co-author trailer:

```text
Co-authored-by: Cursor <cursoragent@cursor.com>
```

Do not mark any S10 prediction, S11 calibration/proof-carrying analytics,
S12 envelope growth, S13 accountability, production, preference-learning, or
S14 universality cell as implemented. S9 advances projection faithfulness and
governed lowering only.
