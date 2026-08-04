---
title: "INT-R8 falsifier suite and repository integration handoff"
research_id: INT-R8
artifact_role: falsifier-specification-and-handoff
status: accepted_narrow_scope
research_only: true
repository: DenisKopylov/polisyos
baseline_ref: main
baseline_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
prepared_at: 2026-08-04
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

## 1. Purpose

This file specifies red-first semantic tests for INT-R8. It is an executable **behavioral specification**, not production test code or a final fixture schema. A conforming implementation may choose its language and package layout, but it must preserve the inputs, mutations, checks and expected verdicts below.

The suite assumes the existing projection machinery remains the canonical source for audience, omission, redaction, contest, recourse, deficit, denied-use and audit semantics. It assumes the existing public-export gate remains a consumer. It does not appoint a new owner or authorize GY-PA3.

## 2. Test harness contract

### 2.1 Logical functions

A future harness needs these logical operations:

```text
project(full_record, audience, release_policy) -> projection
summarize(projection, compression_policy) -> candidate_summary
inventory(full_record, projection, candidate_summary) -> retained_dropped_map
candidate_channels(candidate_summary, delivery_surface) -> channel_bundle
append_candidate(history, projection, channel_bundle) -> candidate_transcript
verify_loss(full_record, projection, candidate_summary,
            retained_dropped_map, candidate_transcript,
            declared_uses, rule_version) -> CompressionLossReceipt
```

`verify_loss` must call or compose with existing S9-S14 and authority-boundary checks rather than replacing them.

### 2.2 Required result shape

For test purposes, the result exposes:

```text
loss_outcome ∈ {lossy_but_safe, blocked_material_omission}
issue_codes: set[str]
affected_claim_ids: set[str]
retained_item_ids: set[str]
dropped_item_ids: set[str]
transcript_check_status
source_revision_ref
rule_version_ref
```

This is a logical assertion surface only. It does not fix a wire schema.

### 2.3 Baseline invariant

Every red mutation starts from a valid green control that:

- uses one source revision;
- has all four canonical audience projections available as needed;
- carries a complete source semantic inventory;
- preserves the existing projection-only authority boundary;
- includes canonical omitted-item reasons;
- passes the existing per-projection consumer contracts;
- has an empty or known-safe prior transcript;
- receives `lossy_but_safe` only because it is genuinely shorter than the source.

A mutation test is invalid if the control is already red.

## 3. Required falsifiers

### INT-R8-F01 — retained limitation dropped

**Control.** Claim `C-1` says an estimated benefit applies only to municipalities with complete 2025 reporting and carries limitation `L-1`. Summary retains that condition.

**Mutation.** Remove `L-1` from visible summary and retained inventory while leaving the point estimate and favorable conclusion unchanged.

**Verifier.** Compare source limitations to the retained/dropped map; evaluate declared-use predicates for scope and conditionality.

**Expected.** Red:

```text
loss_outcome = blocked_material_omission
issue_codes contains compression_retained_limitation_missing
or compression_truth_condition_changed
affected_claim_ids contains C-1
```

**Anti-cheat assertion.** Adding a generic sentence “results have limitations” does not restore green unless it faithfully carries the load-bearing condition.

### INT-R8-F02 — bare `delta` without declared basis

**Control.** `C-delta` carries `delta`, declared obligation set `O-v7`, maintained assumptions `A-1..A-4`, and the relative-basis rider.

**Mutation.** Keep the number/label and remove any one of the declared set, maintained assumptions, or visible rider.

**Expected.** Red:

```text
loss_outcome = blocked_material_omission
issue_codes contains compression_delta_basis_missing
affected_claim_ids contains C-delta
```

**Binding basis.** INT-K02; no materiality override can convert this case to safe.

### INT-R8-F03 — negative terminal hidden

**Control.** The completed governed outcome is `refusal` after exhaustion; chronology and correction/recourse state are visible.

**Mutation.** Replace it with empty result, “not available,” omit the terminal, or render only a neutral absence icon.

**Expected.** Red:

```text
loss_outcome = blocked_material_omission
issue_codes contains compression_negative_terminal_hidden
```

Run the same mutation for `void`, `dispute`, `terminal_no_attempt` and `exhaustion_without_promotion`.

### INT-R8-F04 — two individually safe views reconstruct a withheld claim

**Control.** Secret predicate `q(R)` has two possible values after PUBLIC alone and two after REVIEWER alone; the joint transcript also leaves both possible.

**Mutation.** PUBLIC reveals total `A+B`; REVIEWER reveals `A`; neither names `B`, but their union uniquely determines protected `B`.

**Assertions.** First verify each view in isolation; both must pass their local checks. Then verify the coalition transcript.

**Expected.** Coalition red:

```text
local_public = not_reconstructed_under_declared_model
local_reviewer = not_reconstructed_under_declared_model
joint = reconstructed
loss_outcome = blocked_material_omission
issue_codes contains compression_cross_view_reconstruction
```

A suite that runs only the joint test without proving the two local controls is weaker than the required falsifier.

### INT-R8-F05 — missing or non-canonical redaction reason

**Control.** Dropped item `E-private` has a canonical reason class, affected claim IDs and semantic-effect row.

**Mutations.** Run separately:

1. remove the reason;
2. use free text not in the approved vocabulary;
3. use a canonical label inconsistent with the transformation;
4. encode the protected value in the reason string.

**Expected.** Red with one of:

```text
compression_redaction_reason_missing
compression_redaction_reason_noncanonical
compression_redaction_reason_mismatch
compression_reason_self_disclosing
```

The existing scanner reasons in `public_export.py` are reused where applicable; INT-R8 does not permit a second scanner vocabulary.

## 4. Additional mandatory falsifiers

### INT-R8-F06 — no-number procedural history broadened

**Control.** A custody claim lists pre-result sealing, first qualifying attempt, no prohibited substitution, adjudication, dissent, negative publication and correction history.

**Mutation.** Drop the firstness or substitution step and summarize as “the process was properly followed.”

**Expected.** Red: `compression_procedural_step_missing` and/or `compression_scope_broadened`.

### INT-R8-F07 — denied use narrowed

**Control.** Source claim forbids `production_recommendation` and `approval_authority` use.

**Mutation.** Summary carries only one prohibition, renames a prohibition into a weaker advisory caveat, or removes claim-level limits while retaining only projection-level boilerplate.

**Expected.** Red: `compression_denied_use_narrowed`.

**Property.** For every retained claim and projection, summary denied uses are a superset of source denied uses.

### INT-R8-F08 — dissent disappears into consensus

**Control.** One panel member dissents on a material issue; majority result remains unchanged. Public summary says majority decision, material dissent exists, issue/disposition and safe reference are retained.

**Mutation.** Remove dissent or say “the panel concluded”/“experts agreed” without qualification.

**Expected.** Red: `compression_contestability_reduced` or `compression_material_counterevidence_missing`.

### INT-R8-F09 — selected evidence framed as broad consensus

**Control.** Full record identifies candidate universe, selected set, rejected set, effective diversity and conflicting evidence.

**Mutation.** Keep only the selected favorable evidence and render “broad consensus.”

**Expected.** Red: `compression_consensus_overstated` and affected claim IDs. This closes the low-`k_eff` case already named by the GY-PA3 plan (`GY-engine-subordination.md:2304-2324`).

### INT-R8-F10 — pointer-only cure fails

**Control.** Material limitation/counterevidence is visible and a full-record pointer is present.

**Mutation.** Remove the visible semantic item but retain “see full report.”

**Expected.** Red. A provenance pointer does not cure a misleading summary.

### INT-R8-F11 — diff reconstructs protected content

**Control.** Two versions each suppress protected claim `H` and a public change notice states only safe change categories.

**Mutation.** Emit raw before/after text, deletion context, line number, or count that identifies `H`.

**Expected.** Red: `compression_temporal_reconstruction`.

### INT-R8-F12 — hash dictionary oracle

**Control.** Public binding covers only approved public content or an INT-R7-approved non-disclosing construction.

**Mutation.** Include deterministic hash/fingerprint of low-entropy secret, hidden claim ID, reviewer identity or suppressed cell.

**Attack.** Enumerate the finite dictionary and compare hashes.

**Expected.** Red: `compression_hash_oracle`.

### INT-R8-F13 — ordering/rank leak

**Control.** Public rows are sorted on public-safe keys after suppression.

**Mutation.** Keep private score order, visible rank gaps, total counts or stable pagination slots.

**Attack.** Infer category/score interval of the missing row.

**Expected.** Red: `compression_ordering_channel`.

### INT-R8-F14 — timing leak versus custody chronology

Run two paired tests:

1. **Privacy mutation:** exact timestamp identifies a protected event when only coarse date is needed → red `compression_timing_channel`.
2. **Integrity mutation:** remove the ordering/time fact that proves firstness or prospectivity for an INT-K06 custody claim → red `compression_procedural_step_missing`.

This pair prevents the false rule “always remove timestamps.”

### INT-R8-F15 — provenance cross-view join

**Control.** Audience-safe references are unlinkable except through authorized resolution.

**Mutation.** PUBLIC and EXPERT receive the same private artifact/reviewer/CAS identifier and their fields jointly identify protected content.

**Expected.** Red: `compression_provenance_join_reconstruction`.

### INT-R8-F16 — omission manifest self-discloses

**Control.** Manifest gives safe semantic class, affected public claim and reason.

**Mutation.** Manifest says enough to identify a protected person/allegation/cell.

**Expected.** Red: `compression_manifest_self_disclosing`.

### INT-R8-F17 — screenshot drops caveat

**Control.** Desktop, narrow viewport and print capture all visibly include claim type, currentness, basis/rider, material limitations, denied uses, negative/contest indicator and omission notice.

**Mutation.** CSS hides a caveat, moves it behind hover/collapse, truncates it off-screen, or print CSS removes it.

**Expected.** Red: `compression_screenshot_minimum_missing`.

The verifier operates on rendered fixtures/accessibility tree, not only source component props.

### INT-R8-F18 — export metadata leak

**Control.** Exported PDF/DOCX/HTML/JSON contains approved visible content and safe metadata only.

**Mutation.** Add author identity, revision history, hidden comments, tracked changes, embedded source JSON, private file path, attachment or formula that reveals raw values.

**Expected.** Red: `compression_export_channel`.

### INT-R8-F19 — deep-link payload contains unrendered field

**Control.** Deep-link representation contains only the accepted public object or an opaque handle.

**Mutation.** Add a field to the encoded URL payload that the UI does not render and the visible snapshot test ignores.

**Expected.** Red: `compression_deep_link_payload_leak`.

This targets the current packet pattern in which the packet itself is encoded into `signedId` (`publicationPacket.ts:1019-1174`).

### INT-R8-F20 — stale/superseded export appears current

**Control.** Old release is visibly superseded and carries a current-head pointer.

**Mutation.** Screenshot/export/cache shows old content without supersession/currentness.

**Expected.** Red: `compression_currentness_missing`.

### INT-R8-F21 — materiality unknown treated as safe

**Control.** All dropped items receive a determinate materiality decision.

**Mutation.** Force verifier timeout, missing rule, unresolved claim mapping or incomplete full-record inventory and coerce to safe.

**Expected.** Red: `compression_materiality_unknown` or `compression_inventory_incomplete`.

### INT-R8-F22 — receipt mints authority

**Control.** Receipt remains `projection_only`, `authoritative_for = []`, and carries all existing prohibitions.

**Mutation.** Set approval/publication/closeout/claim authority or infer “verified public decision” from `lossy_but_safe`.

**Expected.** Existing authority-laundering gate red plus `compression_receipt_mints_authority`.

### INT-R8-F23 — adaptive release passes local-only check

**Control.** Candidate release selected after observing history is evaluated against the complete actual prefix.

**Mutation.** Check only the new item or use a pre-history local result; the pair reconstructs a secret.

**Expected.** Red: `compression_transcript_prefix_not_checked` and/or cross-view reconstruction.

### INT-R8-F24 — post-hoc transcript narrowing

**Control.** All releases remain in append-only logical history; corrections append supersession.

**Mutation.** Delete an earlier disclosure from accounting or redefine coalition membership after a leak is found.

**Expected.** Red: `compression_transcript_membership_rewritten`.

### INT-R8-F25 — invented numeric budget

**Control.** Receipt carries no scalar privacy/composition guarantee and only the procedural prefix claim.

**Mutation.** Add epsilon, percentage, risk score, “remaining budget” or cumulative safety number without a mechanism-specific theorem, local enforced bounds and owner reproduction.

**Expected.** Red: `compression_numeric_budget_unjustified`.

## 5. Positive controls

A red-only suite can pass by rejecting everything. These green controls are required.

### INT-R8-G01 — duplicate citations condensed

Five duplicate references become one; support relation, source class, conflict/independence and affected claim remain. Dropped duplicates have canonical nonsemantic reason. Expected: `lossy_but_safe`.

### INT-R8-G02 — confidential name replaced by role

Identity is non-material for declared use. Dissent, mandate, affected issue, date/signature status and recourse remain; no cross-view join. Expected: `lossy_but_safe`.

### INT-R8-G03 — disclosure-controlled aggregate

Raw cells are removed; population/time, conditionality, uncertainty, threshold/reason and denied uses remain; prior releases do not allow differencing. Expected: `lossy_but_safe`.

### INT-R8-G04 — no-number history faithfully condensed

Repeated event prose and low-level paths are removed, while prospectivity, firstness, sealing, substitution, chronology, adjudication, dissent, negatives and correction remain. Expected: `lossy_but_safe`.

### INT-R8-G05 — additional caution

Summary adds a denied use or conservatively returns “insufficient for this use” while preserving source truth. Expected: `lossy_but_safe`; the receipt does not call the source more authoritative.

## 6. Property-based invariants

For generated source/summary pairs, assert:

```text
P1: surfaced_claim_ids(summary) ⊆ claim_ids(source)
P2: denied_uses(summary, c) ⊇ denied_uses(source, c)
P3: mandatory_semantics(source, c, declared_uses)
    ⊆ faithful_semantics(summary, c)
P4: every source inventory item has exactly one disposition
P5: every dropped/redacted item has canonical reason + affected claims + effect
P6: decision(summary, d) == decision(source, d)
    or decision(summary, d) is more conservative, for every governed d
P7: negative terminals and supersession cannot become absence
P8: authority_role(receipt) == projection_only
P9: authoritative_for(receipt) == []
P10: accepted transcript prefix passes every declared reconstruction predicate
P11: adding a new release can never remove a prior transcript member
P12: missing/unknown verifier input cannot yield lossy_but_safe
```

Metamorphic tests should permute prose, reorder nonsemantic references, change viewport/export format and add unrelated public material without changing the verdict. Mutations to any load-bearing qualifier must turn green to red.

## 7. Repository integration handoff

### 7.1 Reality map

| Capability | Pinned reality | Required extension point | Missing-state label | Handoff constraint |
|---|---|---|---|---|
| Four-audience projection semantics and omission/redaction/contest/recourse substrate | Present in `runtime/quality/projection_semantics.py` | Extend this canonical semantic owner or its approved adjacent contract; do not create parallel projection semantics | `implemented` for substrate; `producer_missing` for compression receipt | Reuse IDs, audiences, authority boundary, omissions and denied uses. |
| Public-export bundle | Present in `runtime/quality/public_export.py`; omitted-ID and S9-S14 gates exist | Consume a verified receipt and reject blocked/missing/wrong-revision receipt | `verification_missing` for loss gate | Public export must not decide materiality itself from ad hoc prose. |
| HTTP publication caller for `build_public_export_bundle` | No production-source HTTP caller at pin | Bind existing producer through approved runtime surface | `bridge_missing` | Do not mislabel the export producer as absent. |
| GY-PA3 compression-loss ledger producer | Plan entry only | Planned runtime-quality producer reusing G6 ledgers, projection semantics and public export | `producer_missing` | INT-R8 semantics are an input; plan text is not capability. |
| Cross-view/temporal transcript owner and verifier | No source owner | Architecture decision required; candidate must extend existing custody/history boundaries rather than confidence authority | `producer_missing`, `verification_missing` | No second confidence/risk ledger and no owner appointment by this research. |
| Frontend packet/viewer | Rendering packet and client integrity cue exist | Render owner-issued receipt/minimum set; never infer safe loss | `bridge_missing` for owner receipt; `semantic_test_missing` for capture/export cases | DS12 rendering model remains non-authoritative. |
| Screenshot/print/export checks | No INT-R8 semantic suite | Consumer/render tests over actual artifacts | `semantic_test_missing` | Test bytes/rendered output, not only component state. |
| INT-R7 proof binding | Parallel research | Bind receipt/source/retained set/reasons/transcript head | `contract_only` dependency until INT-R7 closes | INT-R8 chooses no algorithm or key policy. |
| Numeric composition accountant | No owner or valid local guarantees | Not authorized by this result | `producer_missing`; additional research | Procedural no-number alternative is the accepted current result. |

### 7.2 Candidate ownership rule without appointment

The project should extend existing canonical owners as follows, subject to normal architecture approval:

- `projection_semantics.py` remains the source of projection truth and reusable omission/redaction/contest semantics;
- a future GY-PA3-class runtime-quality producer may classify retained/dropped items and emit the receipt;
- `public_export.py` should consume and gate the receipt;
- Atlas `publicationPacket.ts` should render the owner-issued receipt and minimum visible set only;
- the release-history owner must be the existing competent custody/history boundary chosen by architecture, not a new confidence ledger or frontend-local store.

This is an integration direction, not canonical owner appointment.

### 7.3 Required API-independent handshakes

#### Projection → receipt producer

Must provide source revision, canonical audience, semantic inventory, omissions/redactions, limitations, denied uses, contests, recourse, negative outcome, audit refs and authority boundary.

#### Receipt producer → public export

Must provide verified two-valued loss verdict, affected claims, rule/source revisions, transcript predecessor/current head and issue codes. Public export rejects any non-safe/missing/mismatched receipt.

#### Receipt/public export → Atlas

Must provide render-safe minimum semantics and current/superseded state. Atlas must not recompute materiality, infer authority or silently truncate owner semantics.

#### Receipt → INT-R7 proof

Must expose bindable identifiers and canonical transformed public object while keeping protected content non-reconstructible. Proof mechanics are delegated to INT-R7.

## 8. Open questions for consolidation

### Engineering

- **ENG-01:** Which existing custody/history owner can reproduce the complete cross-surface transcript, including deep links, screenshots and exports, without becoming a second confidence ledger?
- **ENG-02:** How will a verifier enumerate the full semantic inventory across heterogeneous claim types without fixing premature package/schema cardinality?
- **ENG-03:** Which rendered-artifact harness can inspect PDF/DOCX/print CSS/accessibility tree and metadata in CI?
- **ENG-04:** How will audience-scoped provenance refs remain resolvable for authorized audit without becoming coalition join keys?
- **ENG-05:** What is the fail-closed behavior when historical release bytes or delivery metadata are unavailable?
- **ENG-06:** How will corrections preserve append-only transcript membership while limiting unsafe raw diffs?

### Institutional

- **INST-01:** Which office is competent to define “material issue,” approve redaction-reason classes and decide when dissent identity is itself material?
- **INST-02:** Which audience coalitions are realistic under delegation, FOI access, litigation discovery, insider access and public copying?
- **INST-03:** What full-record access/recourse route must remain available to an affected person when public detail is lawfully withheld?
- **INST-04:** Which official-language, accessibility and plain-language reviews are required before a condensed reason can be considered understandable but faithful?
- **INST-05:** What retention and correction rules apply to cached, archived, screenshot and exported versions?

### Additional research

- **RES-01:** Can a bounded class of statistical releases be defined as a genuine randomized DP mechanism with adjacency, local guarantees and an owner-verifiable adaptive accountant?
- **RES-02:** Which secret predicates and gain functions best represent policy-record harms for maximal-leakage analysis, and can a justified distribution be established?
- **RES-03:** How can automated semantic entailment/materiality checks be made sound enough to block broadening while admitting useful condensation?
- **RES-04:** What auxiliary-information model is conservative but operationally testable for public records?
- **RES-05:** How should multilingual summaries preserve legal/policy qualifiers across translation and plain-language transformation?
- **RES-06:** How should withdrawal, appeal, legal change and discovered bias invalidate prior `lossy_but_safe` receipts without implying that historical releases disappear?

## 9. Exit criteria for implementation planning

Implementation planning may begin only after architecture records:

1. an approved canonical extension point and transcript owner;
2. the semantic inventory/predicate governance process;
3. canonical omission/redaction reason governance;
4. INT-R7's bindable proof interface;
5. fail-closed behavior for missing history;
6. red-first fixtures F01-F25 and green controls G01-G05;
7. explicit confirmation that no numeric disclosure budget is being inferred from this research.

## 10. Result standing

**`accepted_narrow_scope`.** The suite is sufficient to falsify the commission's required boundary and the major release-channel attacks. Repository handoff is explicit and reuse-first. Production capability remains absent until independently implemented, reviewed and verified.
