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
may_not_use_for:
  - production_implementation_authorization
  - final_wire_schema_package_database_serialization_or_api_contract
  - canonical_owner_appointment
n  - authority_grant
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

The audited F01-F25 and G01-G05 prose remains immutable at
`research/int-r8-compression-loss-and-disclosure@90b372964d29a9e97605a6ef733ef03ffe7938d2`.
It is historical suite v1 and no longer controls executable expectations.

**The controlling specification is `INT-R8-COMPRESSION-FALSIFIERS-v2` in this document.** It
preserves F01-F25 as family identities, splits every bundled or disjunctive case into atomic
subfixtures, preserves all five green-control purposes, and adds F26-F30 for the five channel
families required by R6. No v1 weakness is deleted or reclassified as safe.

This is an equality-ready Markdown specification, not production test code or a final fixture
schema. The suite has not run. Its existence establishes no capability or benchmark passage.

## 1. Harness contract

A conforming harness provides logical operations equivalent to:

```text
project(source_record, audience, projection_policy) -> projection
summarize(projection, compression_policy) -> candidate_object
inventory(source_record, projection, candidate_object) -> semantic_map
observe(candidate_object, release_family, channel_registry) -> observations
append_candidate(controlled_history, observations) -> candidate_prefix
verify_loss(source_record, projection, candidate_object, semantic_map,
            candidate_prefix, use_package, predicate_package,
            model_package, rule_version) -> CompressionLossReceipt
```

The verifier composes with the canonical projection and S9-S14 authority checks. It does not
replace them.

### 1.1 Fixed v2 baseline package

Unless a row states the exact changed field, every red and green subfixture uses:

- `source_revision_ref = git://int-r8-fixture/source-r1`;
- `rule_version_ref = int-r8-compression-v2`;
- `use_package_ref = use://public-audit-v1`;
- `predicate_package_ref = predicate://compression-materiality-v2`;
- `record_model_ref = model://finite-policy-record-v2`;
- `protected_predicate_family_ref = protected://int-r8-v2`;
- `release_family_ref = release-family://controlled-v2`;
- `channel_registry_ref = channels://int-r8-open-v2`;
- `coalition_model_ref = coalition://public-reviewer-expert-machine-v2`;
- `background_model_ref = background://public-known-v2`;
- `transcript_completeness = complete_for_declared_controlled_release_family`;
- one exact source semantic disposition per inventory item;
- `authority_role = projection_only`;
- `authoritative_for = []`;
- all canonical source denied uses; and
- all unchanged checks passing.

### 1.2 Exact result fields

Each row specifies exact values for:

- `loss_outcome`;
- `evaluation_status`;
- `issue_codes` as an exact set;
- `affected_claim_ids` as an exact set; and
- `reconstruction_status`.

Issue-code precedence is part of v2. A harness does not substitute a semantically similar code.
Later gates use `not_evaluated_precondition` when an earlier exact failure already determines the
outcome.

## 2. Family registry

| Family | Controlling purpose |
|---|---|
| F01 | retained limitation dropped |
| F02 | bare delta basis component removed |
| F03 | negative terminal hidden |
| F04 | locally safe views jointly reconstruct |
| F05 | reason relation failure |
| F06 | constitutive procedural history damaged |
| F07 | denied use narrowed |
| F08 | dissent converted to consensus |
| F09 | selected evidence framed as broad consensus |
| F10 | pointer-only cure |
| F11 | diff reconstruction |
| F12 | hash dictionary oracle |
| F13 | ordering and count channel |
| F14 | timing privacy and chronology integrity |
| F15 | provenance join |
| F16 | self-disclosing manifest |
| F17 | screenshot, print, and accessibility loss |
| F18 | export metadata and hidden content |
| F19 | deep-link hidden payload |
| F20 | stale object presented as current |
| F21 | unknown or incomplete verifier input |
| F22 | receipt mints authority |
| F23 | adaptive release checked locally only |
| F24 | controlled history rewritten |
| F25 | unjustified numerical budget |
| F26 | locale and translation channel |
| F27 | notification and syndication channel |
| F28 | network and compression oracle |
| F29 | discovery and indexing channel |
| F30 | proof metadata channel |

The registry contains **30 red families**: F01-F30. The v2 table below contains
**67 mandatory atomic red subfixtures**. Family count and subfixture count are different
denominators.

## 3. Atomic red subfixtures

| Fixture | Family | Single mutation | Expected loss outcome | Expected evaluation status | Exact issue-code set | Exact affected-claim set | Expected reconstruction status |
|---|---|---|---|---|---|---|---|
| F01-A | F01 | remove visible L-1 and its retained mapping | blocked_material_omission | evaluated | {compression_retained_limitation_missing} | {C-1} | not_evaluated_precondition |
| F01-B | F01 | replace L-1 with generic text 'results have limitations' | blocked_material_omission | evaluated | {compression_retained_limitation_missing} | {C-1} | not_evaluated_precondition |
| F02-A | F02 | remove obligation_set_ref=O-v7 | blocked_material_omission | evaluated | {compression_delta_basis_missing} | {C-delta} | not_evaluated_precondition |
| F02-B | F02 | remove maintained_assumptions_ref=A-v4 | blocked_material_omission | evaluated | {compression_delta_basis_missing} | {C-delta} | not_evaluated_precondition |
| F02-C | F02 | remove visible relative_basis_rider | blocked_material_omission | evaluated | {compression_delta_basis_missing} | {C-delta} | not_evaluated_precondition |
| F03-A | F03 | replace outcome=refusal with outcome=absent | blocked_material_omission | evaluated | {compression_negative_terminal_hidden} | {C-terminal} | not_evaluated_precondition |
| F03-B | F03 | replace outcome=void with outcome=absent | blocked_material_omission | evaluated | {compression_negative_terminal_hidden} | {C-terminal} | not_evaluated_precondition |
| F03-C | F03 | replace outcome=dispute with outcome=absent | blocked_material_omission | evaluated | {compression_negative_terminal_hidden} | {C-terminal} | not_evaluated_precondition |
| F03-D | F03 | replace outcome=terminal_no_attempt with outcome=absent | blocked_material_omission | evaluated | {compression_negative_terminal_hidden} | {C-terminal} | not_evaluated_precondition |
| F03-E | F03 | replace outcome=exhaustion_without_promotion with outcome=absent | blocked_material_omission | evaluated | {compression_negative_terminal_hidden} | {C-terminal} | not_evaluated_precondition |
| F04-A | F04 | set PUBLIC observation to A_plus_B=11 and REVIEWER observation to A=4 so B=7 is unique | blocked_material_omission | evaluated | {compression_cross_view_reconstruction} | {C-private-B} | public=not_reconstructed;reviewer=not_reconstructed;joint=reconstructed |
| F05-A | F05 | delete transformation_reason | blocked_material_omission | evaluated | {compression_redaction_reason_missing} | {C-private} | not_evaluated_precondition |
| F05-B | F05 | set transformation_reason=editor_removed | blocked_material_omission | evaluated | {compression_redaction_reason_noncanonical} | {C-private} | not_evaluated_precondition |
| F05-C | F05 | map email scanner removal to keyed_secret reason | blocked_material_omission | evaluated | {compression_redaction_reason_mismatch} | {C-private} | not_evaluated_precondition |
| F05-D | F05 | put protected value Alice-Secret in safe_public_explanation | blocked_material_omission | evaluated | {compression_reason_self_disclosing} | {C-private} | reconstructed |
| F06-A | F06 | remove constitutive event first_qualifying_attempt | blocked_material_omission | evaluated | {compression_procedural_step_missing} | {C-custody} | not_evaluated_precondition |
| F06-B | F06 | remove constitutive event no_prohibited_substitution | blocked_material_omission | evaluated | {compression_procedural_step_missing} | {C-custody} | not_evaluated_precondition |
| F06-C | F06 | remove order edge seal_before_execution | blocked_material_omission | evaluated | {compression_procedural_order_not_established} | {C-custody} | not_evaluated_precondition |
| F06-D | F06 | remove procedure_package_ref | blocked_material_omission | evaluated | {compression_procedural_basis_not_established} | {C-custody} | not_evaluated_precondition |
| F07-A | F07 | delete denied use production_recommendation from claim C-1 | blocked_material_omission | evaluated | {compression_denied_use_narrowed} | {C-1} | not_evaluated_precondition |
| F07-B | F07 | replace denied use approval_authority with advisory text | blocked_material_omission | evaluated | {compression_denied_use_narrowed} | {C-1} | not_evaluated_precondition |
| F08-A | F08 | delete dissent record D-1 from visible summary | blocked_material_omission | evaluated | {compression_contestability_reduced} | {C-1} | not_evaluated_precondition |
| F08-B | F08 | replace majority_with_dissent wording with experts_agreed | blocked_material_omission | evaluated | {compression_consensus_overstated} | {C-1} | not_evaluated_precondition |
| F09-A | F09 | remove rejected_set and conflict rows while setting summary_consensus=broad | blocked_material_omission | evaluated | {compression_consensus_overstated} | {C-evidence} | not_evaluated_precondition |
| F10-A | F10 | delete visible limitation L-1 while retaining full_record_pointer | blocked_material_omission | evaluated | {compression_retained_limitation_missing} | {C-1} | not_evaluated_precondition |
| F10-B | F10 | delete visible counterevidence E-counter while retaining full_record_pointer | blocked_material_omission | evaluated | {compression_material_counterevidence_missing} | {C-1} | not_evaluated_precondition |
| F11-A | F11 | publish deleted protected text in version diff | blocked_material_omission | evaluated | {compression_temporal_reconstruction} | {C-hidden} | reconstructed |
| F11-B | F11 | publish exact deletion line index that uniquely identifies protected row | blocked_material_omission | evaluated | {compression_temporal_reconstruction} | {C-hidden} | reconstructed |
| F12-A | F12 | publish sha256 of secret drawn from dictionary {red,blue} | blocked_material_omission | evaluated | {compression_hash_oracle} | {C-secret} | reconstructed |
| F13-A | F13 | preserve private score ordering with visible rank gap 3 | blocked_material_omission | evaluated | {compression_ordering_channel} | {C-hidden} | reconstructed |
| F13-B | F13 | publish total_count=6 after suppressing one private row from five visible rows | blocked_material_omission | evaluated | {compression_ordering_channel} | {C-hidden} | reconstructed |
| F14-A | F14 | publish exact timestamp 2026-08-04T10:03:12Z that identifies protected event | blocked_material_omission | evaluated | {compression_timing_channel} | {C-private-event} | reconstructed |
| F14-B | F14 | delete chronology edge attempt_1_before_attempt_2 from custody claim | blocked_material_omission | evaluated | {compression_procedural_order_not_established} | {C-custody} | not_evaluated_precondition |
| F15-A | F15 | reuse private reviewer identifier reviewer-17 in PUBLIC and EXPERT observations | blocked_material_omission | evaluated | {compression_provenance_join_reconstruction} | {C-reviewer} | reconstructed |
| F16-A | F16 | set manifest explanation to allegation_type=X for person_id=P-7 | blocked_material_omission | evaluated | {compression_manifest_self_disclosing} | {C-private} | reconstructed |
| F17-A | F17 | desktop CSS sets display:none on L-1 | blocked_material_omission | evaluated | {compression_screenshot_minimum_missing} | {C-1} | not_evaluated_precondition |
| F17-B | F17 | narrow viewport clips relative_basis_rider outside captured region | blocked_material_omission | evaluated | {compression_screenshot_minimum_missing} | {C-delta} | not_evaluated_precondition |
| F17-C | F17 | print CSS removes denied_use section | blocked_material_omission | evaluated | {compression_screenshot_minimum_missing} | {C-1} | not_evaluated_precondition |
| F17-D | F17 | accessibility tree omits negative terminal label | blocked_material_omission | evaluated | {compression_screenshot_minimum_missing} | {C-terminal} | not_evaluated_precondition |
| F18-A | F18 | add private author identity to PDF metadata | blocked_material_omission | evaluated | {compression_export_channel} | {C-private} | reconstructed |
| F18-B | F18 | embed tracked-change text containing protected value in DOCX | blocked_material_omission | evaluated | {compression_export_channel} | {C-private} | reconstructed |
| F18-C | F18 | retain spreadsheet formula referencing suppressed raw cell B7 | blocked_material_omission | evaluated | {compression_export_channel} | {C-private-cell} | reconstructed |
| F19-A | F19 | add unrendered protected_field=secret-7 to encoded deep-link packet | blocked_material_omission | evaluated | {compression_deep_link_payload_leak} | {C-private} | reconstructed |
| F20-A | F20 | serve superseded screenshot without current_head_ref | blocked_material_omission | evaluated | {compression_currentness_missing} | {C-1} | not_evaluated_precondition |
| F20-B | F20 | export old PDF without superseded marker | blocked_material_omission | evaluated | {compression_currentness_missing} | {C-1} | not_evaluated_precondition |
| F20-C | F20 | cache returns old HTML without currentness state | blocked_material_omission | evaluated | {compression_currentness_missing} | {C-1} | not_evaluated_precondition |
| F21-A | F21 | force exact solver timeout | blocked_material_omission | not_established_timeout | {compression_reconstruction_not_established} | {C-private} | not_established_timeout |
| F21-B | F21 | remove materiality_predicate_package_ref | blocked_material_omission | not_evaluated_missing_input | {compression_input_package_incomplete} | {C-1} | not_evaluated_precondition |
| F21-C | F21 | remove semantic inventory item disposition for L-1 | blocked_material_omission | evaluated | {compression_item_disposition_invalid} | {C-1} | not_evaluated_precondition |
| F22-A | F22 | set receipt authority_role=approval_input | blocked_material_omission | evaluated | {compression_receipt_mints_authority} | {} | not_evaluated_precondition |
| F22-B | F22 | set receipt authoritative_for={public_decision} | blocked_material_omission | evaluated | {compression_receipt_mints_authority} | {} | not_evaluated_precondition |
| F23-A | F23 | reuse pre-history local pass without evaluating candidate prefix | blocked_material_omission | evaluated | {compression_transcript_prefix_not_checked} | {C-private} | not_evaluated_precondition |
| F24-A | F24 | delete controlled release event release-1 from candidate history | blocked_material_omission | evaluated | {compression_transcript_membership_rewritten} | {} | not_evaluated_precondition |
| F24-B | F24 | remove REVIEWER from coalition model after joint reconstruction is found | blocked_material_omission | evaluated | {compression_transcript_membership_rewritten} | {} | not_evaluated_precondition |
| F25-A | F25 | add epsilon=1.0 to receipt without established model | blocked_material_omission | evaluated | {compression_numeric_budget_unjustified} | {} | not_evaluated_precondition |
| F25-B | F25 | add cumulative_safety_percentage=99 to receipt | blocked_material_omission | evaluated | {compression_numeric_budget_unjustified} | {} | not_evaluated_precondition |
| F25-C | F25 | add remaining_disclosure_budget=0.4 to receipt | blocked_material_omission | evaluated | {compression_numeric_budget_unjustified} | {} | not_evaluated_precondition |
| F26-A | F26 | remove L-1 only from locale=uk-UA rendered object | blocked_material_omission | evaluated | {compression_locale_translation_channel} | {C-1} | not_evaluated_precondition |
| F26-B | F26 | reuse translation_memory_id=tm-private-7 across PUBLIC and REVIEWER locales | blocked_material_omission | evaluated | {compression_locale_translation_channel} | {C-private} | reconstructed |
| F27-A | F27 | email notification omits relative_basis_rider | blocked_material_omission | evaluated | {compression_syndication_channel} | {C-delta} | not_evaluated_precondition |
| F27-B | F27 | Open Graph description contains unrendered protected identity | blocked_material_omission | evaluated | {compression_syndication_channel} | {C-private} | reconstructed |
| F28-A | F28 | gzip byte length distinguishes secret value red from blue | blocked_material_omission | evaluated | {compression_network_oracle_channel} | {C-secret} | reconstructed |
| F28-B | F28 | TLS record count distinguishes presence of protected attachment | blocked_material_omission | evaluated | {compression_network_oracle_channel} | {C-private} | reconstructed |
| F29-A | F29 | sitemap contains URL only when protected case exists | blocked_material_omission | evaluated | {compression_discovery_index_channel} | {C-private} | reconstructed |
| F29-B | F29 | autocomplete result count reveals protected category membership | blocked_material_omission | evaluated | {compression_discovery_index_channel} | {C-private} | reconstructed |
| F30-A | F30 | reuse proof key_id=reviewer-key-17 across audience objects | blocked_material_omission | evaluated | {compression_proof_metadata_channel} | {C-reviewer} | reconstructed |
| F30-B | F30 | proof object size uniquely identifies protected dissent attachment | blocked_material_omission | evaluated | {compression_proof_metadata_channel} | {C-dissent} | reconstructed |

## 4. Atomic green controls

These rows prevent a reject-everything implementation. Each premise is an evaluated fixture
fact, not an editorial assertion.

| Fixture | Family | Single safe transformation | Expected loss outcome | Expected evaluation status | Exact issue-code set | Exact affected-claim set | Expected reconstruction status |
|---|---|---|---|---|---|---|---|
| G01-A | G01 | collapse five duplicate citations to one; duplicate relation is established | lossy_but_safe | evaluated | {} | {C-1} | not_reconstructed_under_declared_model |
| G02-A | G02 | replace person name with role; materiality=non_material_for_declared_use; no cross-view join | lossy_but_safe | evaluated | {} | {C-dissent} | not_reconstructed_under_declared_model |
| G03-A | G03 | replace raw cells with approved aggregate retaining population, time, uncertainty, rule, reason, and denied uses | lossy_but_safe | evaluated | {} | {C-stat} | not_reconstructed_under_declared_model |
| G04-A | G04 | remove duplicate event prose while preserving every constitutive event and order edge | lossy_but_safe | evaluated | {} | {C-custody} | not_reconstructed_under_declared_model |
| G05-A | G05 | add denied use production_recommendation and retain every source semantic | lossy_but_safe | evaluated | {} | {C-1} | not_reconstructed_under_declared_model |

The green registry contains **5 families and 5 atomic subfixtures**: G01-G05.

## 5. Family-specific invariants preserved

### F04 local-before-joint reconstruction

F04-A must first establish exact local statuses for PUBLIC and REVIEWER, then establish joint
reconstruction. A harness that skips the local checks does not execute F04.

### F12 dictionary oracle

The dictionary is exactly `{red, blue}`, the hash function and serialization are fixed by the
fixture, and the expected secret value is unique. The case does not depend on a probabilistic
threshold.

### F19 deep-link payload

The harness decodes the complete path/query/fragment representation and compares it with the
accepted public object. A visible-DOM snapshot alone cannot pass F19.

### F24 append-only controlled history

The baseline contains `release-1` and `release-2`. Removing `release-1` or changing the coalition
model is a membership rewrite, even when the latest bytes are unchanged.

### F25 no differently named scalar

Epsilon, percentage, remaining budget, leakage score, or any other scalar requires a separately
established model. Renaming the field does not change the issue code.

## 6. Property invariants

For generated source/summary pairs:

```text
P1: surfaced_claim_ids(summary) subset_of claim_ids(source)
P2: denied_uses(summary, c) superset_of denied_uses(source, c)
P3: every source inventory item has exactly one disposition
P4: every material source effect has a faithful retained representative
P5: every dropped item has exactly one canonical reason relation
P6: every governed decision is equal or more conservative
P7: negative terminals and currentness cannot become absence
P8: every constitutive event and order edge is retained or faithfully represented
P9: authority_role(receipt) == projection_only
P10: authoritative_for(receipt) == empty_set
P11: every accepted controlled prefix passes all declared exact checks
P12: a new release never removes a controlled predecessor
P13: missing, empty, timeout, unsupported, out-of-model, or unowned approximation cannot yield lossy_but_safe
P14: unclassified channel cannot inherit a safe result
P15: projection failure cannot erase issuer-side source issuance authenticity
```

Metamorphic tests may permute nonsemantic prose and duplicate references. A mutation to a bound
effect, constitutive event, reason relation, channel observation, model identity, or authority
boundary must change the outcome exactly as specified.

## 7. Corrected repository integration handoff

Missing-state labels are used only when their prerequisite evidence exists.

| Capability/surface | Pinned prerequisite evidence | Amended reality | Handoff constraint |
|---|---|---|---|
| Four-audience projection substrate | Source producer, contracts, consumers/tests | `implemented` for existing scope | Reuse audience, claim, omission, contest, recourse, audit, denied-use, and authority IDs. |
| Public-export producer | `build_public_export_bundle` plus tests and tooling | Existing producer present | Do not erase or duplicate it. |
| Public-export producer to intended public/runtime route | Existing producer and existing intended surface; no binding caller | `bridge_missing` | Bind only after normal architecture approval. |
| Compression-loss semantic relation | Amended research contract; no runtime chain | `contract_only` | No producer, owner, or publication capability is implied. |
| GY-PA3 runtime producer | Plan text only | Absent/unallocated at pinned commit | Plan text is not a consumer or producer. |
| Material-loss publication gate | No receipt artifact or wired chain | Absent/unallocated at pinned commit | Do not label `verification_missing`. |
| Controlled transcript custody/verifier | No approved owner, artifact, or consumer | Absent/unallocated at pinned commit | Architecture decision is required; no owner is appointed here. |
| Atlas receipt rendering | Existing viewer/packet, no receipt endpoint/artifact | Receipt integration absent/unallocated | Browser does not decide materiality. |
| Screenshot/print/export semantic cases | Real rendering/export surfaces exist | `semantic_test_missing` for those scoped surfaces | Test actual bytes, render, accessibility tree, and metadata. |
| INT-R7 proof relation | Parallel research semantic contract | `contract_only` | Bind the complete semantic model; proof mechanics remain INT-R7. |
| Numerical accountant | No authorized model or consumer | Not a missing capability | Future research only after a competent model and consumer exist. |

## 8. API-independent semantic handshakes

### Projection to semantic verifier

Supply source revision, audience, concrete projection carriers, canonical IDs, semantic inventory,
uses, predicate package, constitutive procedure package when applicable, and unchanged authority
boundary.

### Semantic verifier to controlled release gate

Supply the exact two-valued outcome, exact issue codes, affected IDs, model/version identities,
rendered-object identities, transcript head, completeness disposition, and exact verifier status.
No wire representation is selected.

### Release object to Atlas

Supply the accepted render-safe minimum set and currentness. Atlas renders; it does not recompute
materiality or suppress owner-issued semantics.

### Semantic relation to INT-R7

Supply the complete binding list in `semantic-contract-and-loss-boundary.md` section 13. Proof
metadata is itself a disclosure channel. A failed projection relation blocks public faithfulness
without negating issuer-side issuance.

## 9. Open questions retained

### Engineering

- Which existing custody boundary is competent to host a declared controlled release family?
- Which finite/decidable semantic models can produce exact or proved no-false-safe results?
- How are renderer, locale, notification, network, index, and proof observations registered?
- How is the canonical reason relation extended without a duplicate registry?

### Institutional

- Which competent office governs materiality bases, constitutive procedure packages, and reason
  relations?
- Which coalition/delegation and auxiliary-information assumptions are defensible?
- What recourse and authorized full-record access survives lawful withholding?

### Additional research

- Can a bounded statistical release family obtain a real DP contract and accountant?
- Can a deterministic QIF model be competently defined without collapsing heterogeneous harms?
- Which symbolic fragments and conservative abstractions are operationally tractable?
- How should later appeal, law change, incident, or discovered bias invalidate prior receipts?

## 10. Suite and handoff standing

`INT-R8-COMPRESSION-FALSIFIERS-v2` is a controlling research specification with 67 atomic
red subfixtures and 5 atomic green subfixtures. It has not run. The corrected handoff
preserves real existing substrate, uses one genuine `bridge_missing`, marks the research relation
`contract_only`, and leaves absent capabilities unallocated. No implementation, owner, schema,
benchmark passage, publication authority, or numerical guarantee follows.
