---
title: "INT-R8 falsifier suite and repository integration handoff"
research_id: INT-R8
artifact_role: falsifier-specification-and-handoff
status: accepted_narrow_scope
amendment_conformance: pending_independent_verification
research_only: true
repository: DenisKopylov/polisyos
baseline_ref: main
baseline_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
audited_head: 90b372964d29a9e97605a6ef733ef03ffe7938d2
prepared_at: 2026-08-04
suite_version: INT-R8-COMPRESSION-FALSIFIERS-v2
amended_after_audit: research/int-r8-independent-audit@f45f338f9d9b0de94edc16efbc334789e70e34e2
remediated_after_verification: research/int-r8-amendment-verification@ead4aca36f94d6014879c9f70b1074800c4ffabf
may_not_use_for:
  - production_implementation_authorization
  - final_wire_schema_package_database_serialization_or_api_contract
  - canonical_owner_appointment
  - authority_grant
  - capability_claim
  - benchmark_passage
  - legal_compliance_or_institutional_competence_conclusion
  - permission_to_publish_a_governed_result
  - automatic_amendment_of_any_plan_or_system_design_decision
  - signature_algorithm_or_key_policy_selection
  - numeric_disclosure_bound
---

# INT-R8 falsifier suite and repository integration handoff

## 0. Controlling suite notice

Suite v1 remains immutable at
`research/int-r8-compression-loss-and-disclosure@90b372964d29a9e97605a6ef733ef03ffe7938d2`.
The controlling specification is **`INT-R8-COMPRESSION-FALSIFIERS-v2`** below. It preserves
F01-F25 and G01-G05 as family identities, atomizes every expectation, and adds F26-F30 for the
five post-audit channel families. The suite has not run and authorizes no implementation or
benchmark claim.

## 1. Equality contract

Every row is one mutation over a fixed green baseline and has the exact tuple:

`fixture_id | family_id | mutation | loss_outcome | evaluation_status | issue_codes | affected_claim_ids | reconstruction_status`.

The fixed baseline binds source revision, use package, materiality predicate package, finite
record model, protected-predicate family, controlled release family, open channel registry,
coalition model, background model, complete controlled-history disposition, one disposition per
inventory item, projection-only authority, empty `authoritative_for`, canonical denied uses, and
all unchanged checks passing.

Later gates return `not_evaluated_precondition` after an earlier exact failure. An equality
harness may not substitute a similar code or infer an unstated premise.

## 2. Family registry and denominators

- `F01` — retained limitation dropped.
- `F02` — bare delta basis component removed.
- `F03` — negative terminal hidden.
- `F04` — locally safe views jointly reconstruct.
- `F05` — reason relation failure.
- `F06` — constitutive procedural history damaged.
- `F07` — denied use narrowed.
- `F08` — dissent converted to consensus.
- `F09` — selected evidence framed as broad consensus.
- `F10` — pointer-only cure.
- `F11` — diff reconstruction.
- `F12` — hash dictionary oracle.
- `F13` — ordering and count channel.
- `F14` — timing privacy and chronology integrity.
- `F15` — provenance join.
- `F16` — self-disclosing manifest.
- `F17` — screenshot, print, and accessibility loss.
- `F18` — export metadata and hidden content.
- `F19` — deep-link hidden payload.
- `F20` — stale object presented as current.
- `F21` — unknown or incomplete verifier input.
- `F22` — receipt mints authority.
- `F23` — adaptive release checked locally only.
- `F24` — controlled history rewritten.
- `F25` — unjustified numerical budget.
- `F26` — locale and translation channel.
- `F27` — notification and syndication channel.
- `F28` — network and compression oracle.
- `F29` — discovery and indexing channel.
- `F30` — proof metadata channel.

Complete v2 denominator: **30/30 red families** and
**71/71 mandatory atomic red subfixtures**. Family and subfixture counts are
different quantities.

## 3. Atomic red subfixtures

```text
fixture | family | mutation | loss_outcome | evaluation_status | issue_codes | affected_claim_ids | reconstruction_status
F01-A | F01 | remove visible L-1 and its retained mapping | blocked_material_omission | evaluated | {compression_retained_limitation_missing} | {C-1} | not_evaluated_precondition
F01-B | F01 | replace L-1 with generic text 'results have limitations' | blocked_material_omission | evaluated | {compression_retained_limitation_missing} | {C-1} | not_evaluated_precondition
F02-A | F02 | remove obligation_set_ref=O-v7 | blocked_material_omission | evaluated | {compression_delta_basis_missing} | {C-delta} | not_evaluated_precondition
F02-B | F02 | remove maintained_assumptions_ref=A-v4 | blocked_material_omission | evaluated | {compression_delta_basis_missing} | {C-delta} | not_evaluated_precondition
F02-C | F02 | remove visible relative_basis_rider | blocked_material_omission | evaluated | {compression_delta_basis_missing} | {C-delta} | not_evaluated_precondition
F03-A | F03 | replace outcome=refusal with outcome=absent | blocked_material_omission | evaluated | {compression_negative_terminal_hidden} | {C-terminal} | not_evaluated_precondition
F03-B | F03 | replace outcome=void with outcome=absent | blocked_material_omission | evaluated | {compression_negative_terminal_hidden} | {C-terminal} | not_evaluated_precondition
F03-C | F03 | replace outcome=dispute with outcome=absent | blocked_material_omission | evaluated | {compression_negative_terminal_hidden} | {C-terminal} | not_evaluated_precondition
F03-D | F03 | replace outcome=terminal_no_attempt with outcome=absent | blocked_material_omission | evaluated | {compression_negative_terminal_hidden} | {C-terminal} | not_evaluated_precondition
F03-E | F03 | replace outcome=exhaustion_without_promotion with outcome=absent | blocked_material_omission | evaluated | {compression_negative_terminal_hidden} | {C-terminal} | not_evaluated_precondition
F04-A | F04 | set PUBLIC observation to A_plus_B=11 and REVIEWER observation to A=4 so B=7 is unique | blocked_material_omission | evaluated | {compression_cross_view_reconstruction} | {C-private-B} | public=not_reconstructed;reviewer=not_reconstructed;joint=reconstructed
F05-A | F05 | delete transformation_reason | blocked_material_omission | evaluated | {compression_redaction_reason_missing} | {C-private} | not_evaluated_precondition
F05-B | F05 | set transformation_reason=editor_removed | blocked_material_omission | evaluated | {compression_redaction_reason_noncanonical} | {C-private} | not_evaluated_precondition
F05-C | F05 | map email scanner removal to keyed_secret reason | blocked_material_omission | evaluated | {compression_redaction_reason_mismatch} | {C-private} | not_evaluated_precondition
F05-D | F05 | put protected value Alice-Secret in safe_public_explanation | blocked_material_omission | evaluated | {compression_reason_self_disclosing} | {C-private} | reconstructed
F06-A | F06 | remove constitutive event first_qualifying_attempt | blocked_material_omission | evaluated | {compression_procedural_step_missing} | {C-custody} | not_evaluated_precondition
F06-B | F06 | remove constitutive event no_prohibited_substitution | blocked_material_omission | evaluated | {compression_procedural_step_missing} | {C-custody} | not_evaluated_precondition
F06-C | F06 | remove order edge seal_before_execution | blocked_material_omission | evaluated | {compression_procedural_order_not_established} | {C-custody} | not_evaluated_precondition
F06-D | F06 | remove procedure_package_ref | blocked_material_omission | evaluated | {compression_procedural_basis_not_established} | {C-custody} | not_evaluated_precondition
F07-A | F07 | delete denied use production_recommendation from claim C-1 | blocked_material_omission | evaluated | {compression_denied_use_narrowed} | {C-1} | not_evaluated_precondition
F07-B | F07 | replace denied use approval_authority with advisory text | blocked_material_omission | evaluated | {compression_denied_use_narrowed} | {C-1} | not_evaluated_precondition
F08-A | F08 | delete dissent record D-1 from visible summary | blocked_material_omission | evaluated | {compression_contestability_reduced} | {C-1} | not_evaluated_precondition
F08-B | F08 | replace majority_with_dissent wording with experts_agreed | blocked_material_omission | evaluated | {compression_consensus_overstated} | {C-1} | not_evaluated_precondition
F09-A | F09 | remove rejected_set only | blocked_material_omission | evaluated | {compression_material_counterevidence_missing} | {C-evidence} | not_evaluated_precondition
F09-B | F09 | remove conflict rows only | blocked_material_omission | evaluated | {compression_material_counterevidence_missing} | {C-evidence} | not_evaluated_precondition
F09-C | F09 | set summary_consensus=broad only | blocked_material_omission | evaluated | {compression_consensus_overstated} | {C-evidence} | not_evaluated_precondition
F10-A | F10 | delete visible limitation L-1 while retaining full_record_pointer | blocked_material_omission | evaluated | {compression_retained_limitation_missing} | {C-1} | not_evaluated_precondition
F10-B | F10 | delete visible counterevidence E-counter while retaining full_record_pointer | blocked_material_omission | evaluated | {compression_material_counterevidence_missing} | {C-1} | not_evaluated_precondition
F11-A | F11 | publish deleted protected text in version diff | blocked_material_omission | evaluated | {compression_temporal_reconstruction} | {C-hidden} | reconstructed
F11-B | F11 | publish exact deletion line index that uniquely identifies protected row | blocked_material_omission | evaluated | {compression_temporal_reconstruction} | {C-hidden} | reconstructed
F12-A | F12 | publish sha256 of secret drawn from dictionary {red,blue} | blocked_material_omission | evaluated | {compression_hash_oracle} | {C-secret} | reconstructed
F13-A | F13 | preserve private score ordering with visible rank gap 3 | blocked_material_omission | evaluated | {compression_ordering_channel} | {C-hidden} | reconstructed
F13-B | F13 | publish total_count=6 after suppressing one private row from five visible rows | blocked_material_omission | evaluated | {compression_ordering_channel} | {C-hidden} | reconstructed
F14-A | F14 | publish exact timestamp 2026-08-04T10:03:12Z that identifies protected event | blocked_material_omission | evaluated | {compression_timing_channel} | {C-private-event} | reconstructed
F14-B | F14 | delete chronology edge attempt_1_before_attempt_2 from custody claim | blocked_material_omission | evaluated | {compression_procedural_order_not_established} | {C-custody} | not_evaluated_precondition
F15-A | F15 | reuse private reviewer identifier reviewer-17 in PUBLIC and EXPERT observations | blocked_material_omission | evaluated | {compression_provenance_join_reconstruction} | {C-reviewer} | reconstructed
F16-A | F16 | set manifest explanation to allegation_type=X for person_id=P-7 | blocked_material_omission | evaluated | {compression_manifest_self_disclosing} | {C-private} | reconstructed
F17-A | F17 | desktop CSS sets display:none on L-1 | blocked_material_omission | evaluated | {compression_screenshot_minimum_missing} | {C-1} | not_evaluated_precondition
F17-B | F17 | narrow viewport clips relative_basis_rider outside captured region | blocked_material_omission | evaluated | {compression_screenshot_minimum_missing} | {C-delta} | not_evaluated_precondition
F17-C | F17 | print CSS removes denied_use section | blocked_material_omission | evaluated | {compression_screenshot_minimum_missing} | {C-1} | not_evaluated_precondition
F17-D | F17 | accessibility tree omits negative terminal label | blocked_material_omission | evaluated | {compression_screenshot_minimum_missing} | {C-terminal} | not_evaluated_precondition
F18-A | F18 | add private author identity to PDF metadata | blocked_material_omission | evaluated | {compression_export_channel} | {C-private} | reconstructed
F18-B | F18 | embed tracked-change text containing protected value in DOCX | blocked_material_omission | evaluated | {compression_export_channel} | {C-private} | reconstructed
F18-C | F18 | retain spreadsheet formula referencing suppressed raw cell B7 | blocked_material_omission | evaluated | {compression_export_channel} | {C-private-cell} | reconstructed
F19-A | F19 | add unrendered protected_field=secret-7 to encoded deep-link packet | blocked_material_omission | evaluated | {compression_deep_link_payload_leak} | {C-private} | reconstructed
F20-A | F20 | serve superseded screenshot without current_head_ref | blocked_material_omission | evaluated | {compression_currentness_missing} | {C-1} | not_evaluated_precondition
F20-B | F20 | export old PDF without superseded marker | blocked_material_omission | evaluated | {compression_currentness_missing} | {C-1} | not_evaluated_precondition
F20-C | F20 | cache returns old HTML without currentness state | blocked_material_omission | evaluated | {compression_currentness_missing} | {C-1} | not_evaluated_precondition
F21-A | F21 | force exact solver timeout | blocked_material_omission | not_established_timeout | {compression_reconstruction_not_established} | {C-private} | not_established_timeout
F21-B | F21 | remove materiality_predicate_package_ref | blocked_material_omission | not_evaluated_missing_input | {compression_input_package_incomplete} | {C-1} | not_evaluated_precondition
F21-C | F21 | remove semantic inventory item disposition for L-1 | blocked_material_omission | evaluated | {compression_item_disposition_invalid} | {C-1} | not_evaluated_precondition
F21-D | F21 | select record model M-empty in which no admitted record emits controlled observation t-7 | blocked_material_omission | model_observation_inconsistent | {model_observation_inconsistent} | {C-private} | model_observation_inconsistent
F21-E | F21 | use sampled_search_100 as the reconstruction evaluator and return safe after it finds no reconstruction witness | blocked_material_omission | not_established_unowned_approximation | {not_established_unowned_approximation} | {C-private} | not_established_unowned_approximation
F22-A | F22 | set receipt authority_role=approval_input | blocked_material_omission | evaluated | {compression_receipt_mints_authority} | {} | not_evaluated_precondition
F22-B | F22 | set receipt authoritative_for={public_decision} | blocked_material_omission | evaluated | {compression_receipt_mints_authority} | {} | not_evaluated_precondition
F23-A | F23 | reuse pre-history local pass without evaluating candidate prefix | blocked_material_omission | evaluated | {compression_transcript_prefix_not_checked} | {C-private} | not_evaluated_precondition
F24-A | F24 | delete controlled release event release-1 from candidate history | blocked_material_omission | evaluated | {compression_transcript_membership_rewritten} | {} | not_evaluated_precondition
F24-B | F24 | remove REVIEWER from coalition model after joint reconstruction is found | blocked_material_omission | evaluated | {compression_transcript_membership_rewritten} | {} | not_evaluated_precondition
F25-A | F25 | add epsilon=1.0 to receipt without established model | blocked_material_omission | evaluated | {compression_numeric_budget_unjustified} | {} | not_evaluated_precondition
F25-B | F25 | add cumulative_safety_percentage=99 to receipt | blocked_material_omission | evaluated | {compression_numeric_budget_unjustified} | {} | not_evaluated_precondition
F25-C | F25 | add remaining_disclosure_budget=0.4 to receipt | blocked_material_omission | evaluated | {compression_numeric_budget_unjustified} | {} | not_evaluated_precondition
F26-A | F26 | remove L-1 only from locale=uk-UA rendered object | blocked_material_omission | evaluated | {compression_locale_translation_channel} | {C-1} | not_evaluated_precondition
F26-B | F26 | reuse translation_memory_id=tm-private-7 across PUBLIC and REVIEWER locales | blocked_material_omission | evaluated | {compression_locale_translation_channel} | {C-private} | reconstructed
F27-A | F27 | email notification omits relative_basis_rider | blocked_material_omission | evaluated | {compression_syndication_channel} | {C-delta} | not_evaluated_precondition
F27-B | F27 | Open Graph description contains unrendered protected identity | blocked_material_omission | evaluated | {compression_syndication_channel} | {C-private} | reconstructed
F28-A | F28 | gzip byte length distinguishes secret value red from blue | blocked_material_omission | evaluated | {compression_network_oracle_channel} | {C-secret} | reconstructed
F28-B | F28 | TLS record count distinguishes presence of protected attachment | blocked_material_omission | evaluated | {compression_network_oracle_channel} | {C-private} | reconstructed
F29-A | F29 | sitemap contains URL only when protected case exists | blocked_material_omission | evaluated | {compression_discovery_index_channel} | {C-private} | reconstructed
F29-B | F29 | autocomplete result count reveals protected category membership | blocked_material_omission | evaluated | {compression_discovery_index_channel} | {C-private} | reconstructed
F30-A | F30 | reuse proof key_id=reviewer-key-17 across audience objects | blocked_material_omission | evaluated | {compression_proof_metadata_channel} | {C-reviewer} | reconstructed
F30-B | F30 | proof object size uniquely identifies protected dissent attachment | blocked_material_omission | evaluated | {compression_proof_metadata_channel} | {C-dissent} | reconstructed
```

## 4. Atomic green controls

```text
fixture | family | transformation | loss_outcome | evaluation_status | issue_codes | affected_claim_ids | reconstruction_status
G01-A | G01 | collapse five duplicate citations to one; duplicate relation is established | lossy_but_safe | evaluated | {} | {C-1} | not_reconstructed_under_declared_model
G02-A | G02 | replace person name with role; materiality=non_material_for_declared_use; no cross-view join | lossy_but_safe | evaluated | {} | {C-dissent} | not_reconstructed_under_declared_model
G03-A | G03 | replace raw cells with approved aggregate retaining population, time, uncertainty, rule, reason, and denied uses | lossy_but_safe | evaluated | {} | {C-stat} | not_reconstructed_under_declared_model
G04-A | G04 | remove duplicate event prose while preserving every constitutive event and order edge | lossy_but_safe | evaluated | {} | {C-custody} | not_reconstructed_under_declared_model
G04-B | G04 | condense events adjudication_opened and adjudication_closed into 'adjudication completed' while retaining both event refs, effects={authority_or_status,contestability_or_recourse,history_or_currentness}, and order edges={seal_before_adjudication,adjudication_before_publication} | lossy_but_safe | evaluated | {} | {C-custody} | not_reconstructed_under_declared_model
G05-A | G05 | add denied use production_recommendation and retain every source semantic | lossy_but_safe | evaluated | {} | {C-1} | not_reconstructed_under_declared_model
G05-B | G05 | admit unknown external-copy possibility, set completeness=external_history_not_established, and emit only bounded_to_declared_release_family claim | lossy_but_safe | evaluated | {} | {C-release-boundary} | external_history_not_established
```

Complete green denominator: **5/5 families and 7/7 atomic controls**.

## 5. Preserved high-value cases

- F04-A must establish both local non-reconstruction results before the joint reconstruction
  result.
- F12-A fixes the two-value dictionary and serialization; no probability threshold is used.
- F19-A decodes the complete deep-link representation rather than testing visible DOM only.
- F24-A/F24-B preserve append-only membership and reject post-hoc coalition narrowing.
- F25-A/F25-B/F25-C reject differently named scalars under one exact issue code.
- G04-B is green only while every listed effect and order edge remains; deleting any one invokes
  the corresponding materiality or procedural-order block.
- G05-B limits the claim to the declared release family; it neither treats unknown external
  history as complete nor converts that bounded limitation into a full block.
- G01-G05 preserve duplicate condensation, non-material role replacement, controlled aggregate,
  faithful no-number history condensation, and added conservative caution.

## 6. Property invariants

```text
P1 surfaced claims are a subset of source claims
P2 summary denied uses are a superset of source denied uses
P3 every source item has exactly one disposition
P4 every material governed effect has a faithful representative
P5 every drop has exactly one canonical reason relation
P6 governed decisions are equal or more conservative
P7 negative terminals and currentness never become absence
P8 constitutive events and order edges remain established
P9 receipt authority_role equals projection_only
P10 receipt authoritative_for is empty
P11 every accepted controlled prefix passes declared exact checks
P12 a new release never removes a controlled predecessor
P13 missing, empty, timeout, unsupported, out-of-model, or unowned approximation never passes
P14 an unclassified channel never inherits safety
P15 projection failure never erases issuer-side source issuance authenticity
```

## 7. Corrected capability reality

| Capability/surface | Pinned prerequisite evidence | Amended reality |
|---|---|---|
| Four-audience projection substrate | Source producer, contracts, consumers/tests | `implemented` for its existing scope. |
| Public-export producer | `build_public_export_bundle`, tests, and tooling | Existing producer present. |
| Producer to intended public/runtime route | Both sides exist; no binding caller | `bridge_missing`. |
| Compression-loss semantic relation | Amended research contract; no runtime chain | `contract_only`. |
| GY-PA3 producer | Plan text only | Absent/unallocated at pinned commit. |
| Material-loss publication gate | No receipt artifact or wired chain | Absent/unallocated at pinned commit. |
| Controlled transcript custody/verifier | No approved owner, artifact, or consumer | Absent/unallocated at pinned commit. |
| Atlas receipt rendering | Existing viewer; no receipt artifact/endpoint | Integration absent/unallocated. |
| Screenshot/print/export semantic cases | Real scoped surfaces exist | `semantic_test_missing`. |
| INT-R7 proof relation | Parallel research contract | `contract_only`. |
| Numerical accountant | No authorized model or consumer | Not a missing capability. |

Only the public-export route row uses `bridge_missing`; its producer and intended surface are both
real. No row appoints an owner.

## 8. Semantic handshakes

- Projection to verifier: source revision, audience, concrete projection carriers, semantic
  inventory, declared uses, predicate package, constitutive procedure package, and authority
  boundary.
- Verifier to controlled release gate: exact outcome, exact issue codes, affected IDs, model and
  rendered-object identities, transcript head, completeness disposition, and verifier status.
- Release object to Atlas: accepted minimum semantics and currentness; the browser does not
  recompute materiality.
- Semantic relation to INT-R7: the complete binding list in
  `semantic-contract-and-loss-boundary.md` section 13. Proof metadata is a disclosure channel,
  and failed projection faithfulness does not negate issuer issuance.

## 9. Open questions

Engineering, institutional, and additional-research questions remain open for custody ownership,
finite/decidable models, observation registration, canonical reason governance, competent
materiality bases, coalition assumptions, recourse, bounded DP, deterministic QIF, tractable
symbolic abstraction, and later invalidation of receipts. They are not silently promoted to
implementation tasks.

## 10. Standing

The v2 specification contains 71 atomic red subfixtures and 7 atomic green
subfixtures. It has not run. The handoff preserves existing substrate, uses prerequisite-valid
labels, and authorizes no owner, schema, implementation, publication, benchmark passage, or
numerical guarantee.