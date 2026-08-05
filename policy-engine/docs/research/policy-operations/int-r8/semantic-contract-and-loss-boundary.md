---
title: "INT-R8 semantic contract and loss-typing boundary"
research_id: INT-R8
artifact_role: semantic-contract
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

# INT-R8 semantic contract and loss-typing boundary

## 1. Decision

This artifact settles the **content semantics** of a `CompressionLossReceipt` and the boundary between:

- `lossy_but_safe`; and
- `blocked_material_omission`.

These are **receipt verdicts**, not a new PolicyOS status lattice. A blocked receipt feeds the existing publication/authority gate as a blocking issue. A safe receipt does not mint authority, publication permission, compliance, competence, or truth. Absence of a verified receipt is not a third favorable outcome; it is `verification_missing` and must fail closed at any surface that claims the INT-R8 gate.

The contract is an extension of the existing projection substrate. The pinned projection owner already emits `projection_gaps`, `omission_manifest`, `contested_records`, `recourse_pointer`, `deficit_register`, participation requirements, `redaction_summary`, denied uses and `audit_refs`, and then asserts that the result remains `projection_only` (`policy-engine/src/polisyos/runtime/quality/projection_semantics.py:275-475`). Public export already blocks omitted claim IDs not represented in that manifest (`policy-engine/src/polisyos/runtime/quality/public_export.py:1685-1814`). INT-R8 adds **classification and composition over those facts**, not a parallel omission registry.

## 2. Reuse versus new semantic delta

| Semantic concern | Reused canonical substrate | New INT-R8 delta |
|---|---|---|
| Audience | Existing `PUBLIC`, `REVIEWER`, `EXPERT`, `MACHINE` enumeration (`projection_semantics.py:648-655`) | None; no fifth audience. |
| Omitted claims | `omission_manifest`, normalization and deduplication; public-export omitted-ID check | For each affected item: retained/dropped disposition, semantic class, materiality predicate, affected use and outcome. |
| Redaction | `redaction_summary`; canonical scanner reasons in `public_export.py` | Canonical reason required for every dropped/redacted semantic item, not only scanner placeholders; reason must not disclose the protected value. |
| Limitations | Existing closeout/projection limitations, gaps and deficit register | Explicit retained-versus-dropped limitation inventory and proof that a retained claim did not lose a truth-changing qualifier. |
| Denied use | Existing `may_not_use_for` / `may_not_be_used_for` propagation | Per-claim denied-use retention check; no compression may narrow the prohibition set. |
| Contest, counterevidence and recourse | Existing contested records, recourse pointer, participation surface, audit refs | Material counterevidence/attack/dissent inventory, affected claim IDs, disposition and summary-preservation test. |
| Faithfulness | Existing S9 projection faithfulness and S9-S14 consumer gates | A use-relative semantic-parity verdict across claim type, basis, scope, status, limitations, denied uses and negative results. |
| Cross-view privacy | Existing per-view leak/firewall checks, including S14 hidden/gold payload protection | Joint and temporal transcript reconstruction test across all authorized projections, diffs, hashes, ordering, time, provenance, links, screenshots and exports. |
| Repeated release | Existing history/current-head and public revision structures | A no-number disclosure-discipline receipt over the actual transcript; no numeric budget is established by this research. |

## 3. Semantic object, not proposed wire schema

The following is a **semantic field inventory**. It deliberately does not fix Pydantic classes, JSON names, package location, cardinalities, serialization or API shape.

### 3.1 Receipt identity and boundary

A receipt must identify, by content-bound references suitable for the INT-R7 proof interface:

- the canonical source record and source revision;
- the projection audience and release surface;
- the release event and predecessor/current transcript head;
- the declared intended uses of the summary;
- the full-record semantic inventory version and rule version used by the loss verifier;
- the current/superseded status of the release;
- the existing authority boundary, unchanged and never upgraded by the receipt.

### 3.2 Retained/dropped inventory

For every source semantic item in the verifier's declared inventory, the receipt records exactly one of:

- **retained** — represented directly or by an unambiguous faithful condensation;
- **dropped_manifested** — absent from the summary but represented in the existing omission/redaction machinery with a canonical reason, semantic effect and affected claim IDs;
- **not_applicable_to_projection** — outside the audience contract, with a typed reason and no implication that the item does not exist.

The declared inventory must cover at least these classes:

1. claims and claim type;
2. basis, scope and maintained assumptions;
3. limitations and conditions;
4. attacks, rebuttals and unresolved defeaters;
5. denied uses;
6. counterevidence and conflicting evidence;
7. contest/dispute state;
8. dissent/minority position where material;
9. recourse and competent change-authority pointer;
10. negative terminal and chronology;
11. provenance/audit references;
12. privacy-sensitive material and redaction reason.

An item not inventoried is not silently classified as safe. It yields an incomplete receipt and therefore blocks the INT-R8 gate.

### 3.3 Per-item semantic effect

Every dropped item must state, without restating protected content:

- affected claim IDs;
- item class;
- canonical redaction/omission reason;
- whether it alters truth conditions, scope, authority/status, permitted use, contestability, procedural history or privacy;
- the declared summary use for which it was tested;
- whether an authorized full-record pointer exists;
- the verifier result and issue code.

### 3.4 Receipt verdict

The receipt contains only the two commission-required loss verdicts:

- `lossy_but_safe`: shorter and information-losing, but every mandatory semantic invariant below passes and the actual release transcript passes the declared reconstruction tests;
- `blocked_material_omission`: at least one materiality, parity, reason, reconstruction or completeness condition fails.

The verdict is accompanied by issue codes, affected claim IDs and verifier references. It is not accompanied by an invented probability, privacy score, confidence, approval or publication status.

## 4. Semantic parity

### 4.1 Why byte equality is wrong

A useful public summary must be shorter. Byte equality, sentence alignment and full entailment of every low-level detail would make compression impossible and would conflict with plain-language and accessibility duties. Conversely, “roughly the same meaning” is not testable.

INT-R8 defines parity as **use-relative conservative observational equivalence**.

Let:

- `R` be the full governed record at a fixed revision;
- `S` be one audience summary plus its receipt;
- `U` be a declared set of permitted and prohibited uses;
- `D_U` be a versioned set of decision predicates that a competent consumer/gate applies for those uses;
- `⊑` be the existing PolicyOS authority order, where a result may stay equal or become more conservative but may not broaden authority.

`S` has semantic parity with `R` for `U` exactly when all of the following hold:

1. **Claim identity:** every surfaced claim in `S` resolves to a claim in `R`; compression creates no new claim.
2. **Truth-condition preservation:** claim type, basis, scope, assumptions, conditions and material limitations needed to interpret that claim are retained.
3. **Conservative decision equivalence:** for every `d ∈ D_U`, `d(S)` equals `d(R)` or is strictly more conservative under `⊑`; it is never broader, more favorable, more certain or more authoritative.
4. **Denied-use monotonicity:** `may_not_use_for(S) ⊇ may_not_use_for(R)` for every retained claim and for the projection as a whole. Compression may add a prohibition; it may not remove one.
5. **Negative-state preservation:** refusal, void, dispute, no-attempt, exhaustion, supersession and blocked chronology remain visible whenever they affect interpretation.
6. **Contestability preservation:** material counterevidence, attack, dissent and recourse remain visible enough that a reasonable reader is not told or induced to infer that the result was uncontested or unanimous.
7. **Manifest completeness:** every dropped source item in the declared inventory has a typed row in the reused omission/redaction machinery.
8. **Transcript safety:** adding `S` and its delivery metadata to all prior releases does not make a declared withheld predicate reconstructible.

This definition is checkable. The verifier evaluates a finite governed predicate set, source inventory, summary inventory, authority boundary and actual release transcript. It does not claim perfect natural-language equivalence for every possible reader or future use.

### 4.2 What may legitimately be shorter

Compression may collapse:

- repeated wording and duplicated citations, when the support, independence, conflict and source class remain represented;
- boilerplate that does not alter a governed interpretation predicate;
- low-level storage paths replaced by public-safe opaque references;
- names replaced by roles when personal identity is not material to mandate, conflict, dissent, competence or recourse;
- several equivalent limitations into one lossless normalized limitation;
- raw confidential cells into an approved aggregate while retaining conditionality, uncertainty, disclosure-control reason and denied uses.

The verifier, not the editor, decides whether the condensation is equivalent for the declared use.

## 5. Derivation of the minimum retained set

The minimum is derived from the ways a shorter record could make an official claim materially broader, less contestable or privately reconstructible.

### 5.1 Derivation rule

For each candidate semantic atom `x`, ask whether removing `x` can change at least one of:

- the proposition's truth conditions;
- the population, subject, jurisdiction, time, envelope or obligation set to which it applies;
- its authority/status or currentness;
- a permitted or prohibited use;
- whether the outcome is positive, negative, contested or superseded;
- whether a person can understand reasons, identify material counterevidence, seek recourse or challenge the result;
- whether the release transcript reconstructs protected information.

If **yes**, `x` or a faithful typed condensation of `x` is mandatory. If no for every governed predicate in `D_U`, it may be manifested as dropped and can still yield `lossy_but_safe`.

### 5.2 Minimum retained set

Every summary must therefore carry, directly or through a faithful visible condensation:

1. **Record identity and currentness** — source record/revision, release version, current/superseded state and current-head pointer.
2. **Outcome and existing status** — the actual outcome from the existing lattice; no locally minted “approved”, “verified” or “successful” proxy.
3. **Claim identity and type** — at minimum `delta`, honest refusal/negative result, or no-number procedural custody claim.
4. **Scope and basis** — subject, jurisdiction, material time/envelope and the declared basis needed to stop a narrow claim becoming universal.
5. **`delta` rider** — declared obligation set, maintained assumptions and visible relative-basis rider. This is categorical under INT-K02.
6. **Procedural history for no-number claims** — the load-bearing ordered steps, commitments, substitutions/deviations, adjudication, dissent, negative terminals and correction state on which the custody claim depends.
7. **Material limitations and conditions** — including conditionality of numbers and known coverage/transport/measurement constraints.
8. **Denied uses** — all active `may_not_use_for` restrictions, monotonically preserved.
9. **Material counterevidence, attacks and dissent** — existence, affected claim, disposition and a faithful summary sufficient not to imply consensus; confidential detail may be withheld under a typed reason.
10. **Contest and recourse** — dispute state and a pointer to the competent challenge/correction route where one exists; absence must not be fabricated as “none”.
11. **Typed omission/redaction notice** — what class was removed, why, affected claim IDs and semantic effect, without revealing the protected value.
12. **Provenance/full-record pointer** — an audience-appropriate, non-leaking pointer that lets an authorized consumer reach the authoritative record and lets INT-R7 bind the release to it.
13. **Receipt verdict and audit reference** — the loss verdict, issue codes and verifier reference.

A pointer to the full record is necessary but not sufficient: a citizen cannot be expected to infer that the visible summary omitted the one limitation, dissent or negative terminal that changes its meaning.

## 6. Loss-typing decision procedure

The verifier consumes:

- the fixed full-record semantic inventory for one source revision;
- the audience summary and reused projection fields;
- the declared intended/prohibited uses and predicate set `D_U`;
- the accumulated actual disclosure transcript, including non-body metadata;
- canonical omission/redaction-reason vocabulary;
- the existing authority boundary and status.

It executes the following ordered procedure:

### Gate 1 — identity and inventory completeness

Reject as `blocked_material_omission` when the source revision, audience, rule version or declared semantic inventory cannot be resolved, or when a source item has no retained/dropped/not-applicable disposition.

Suggested issue families: `compression_source_unresolved`, `compression_inventory_incomplete`, `compression_item_unclassified`.

### Gate 2 — categorical retained semantics

Reject when any mandatory item from §5.2 is missing or transformed incompatibly. This includes bare `delta`, hidden refusal/void/dispute/exhaustion, missing material limitation, narrowed denied-use set, concealed supersession and a procedural custody claim with a load-bearing history step removed.

Suggested issue families: `compression_delta_basis_missing`, `compression_negative_terminal_hidden`, `compression_retained_limitation_missing`, `compression_denied_use_narrowed`, `compression_procedural_step_missing`.

### Gate 3 — materiality and conservative parity

For every dropped item, evaluate its effect over `D_U`. Reject if any predicate becomes more favorable, broader, more certain, less contested, less reviewable or more authoritative. An unknown materiality result blocks; uncertainty is not converted into safe loss.

Suggested issue families: `compression_truth_condition_changed`, `compression_scope_broadened`, `compression_authority_broadened`, `compression_contestability_reduced`, `compression_materiality_unknown`.

### Gate 4 — reason and manifest integrity

Reject if a dropped/redacted item lacks a canonical reason, the reason is inconsistent with the transformation, the affected claim set is absent, or the reason itself leaks the protected value.

Suggested issue families: `compression_redaction_reason_missing`, `compression_redaction_reason_noncanonical`, `compression_affected_claim_missing`, `compression_reason_self_disclosing`.

### Gate 5 — cross-view and temporal reconstruction

Append the proposed release and every delivery channel to the candidate transcript. Reject if any declared withheld predicate becomes reconstructible through union, differencing, hash comparison, order/rank, timing, provenance joins, deep-link payload, screenshot/export, cache or prior versions.

Suggested issue families: `compression_cross_view_reconstruction`, `compression_temporal_reconstruction`, `compression_hash_oracle`, `compression_ordering_channel`, `compression_timing_channel`, `compression_export_channel`.

### Gate 6 — final verdict

Only if Gates 1-5 pass may the verifier issue `lossy_but_safe`. Any failure yields `blocked_material_omission` with the exact issue, item and affected claim IDs. A gate timeout, unresolved predicate or unavailable transcript is failure, not safe loss.

## 7. Boundary anchors and worked examples

### 7.1 Categorical blocked: INT-K02 bare `delta`

Full record:

> Within declared obligation set `O_v7`, under assumptions `A1-A4`, the bounded false-promotion quantity is `delta`; the result is relative to that basis and is not a probability that no applicable obligation was omitted.

Compressed summary:

> The policy passed with risk `delta`.

The summary drops the declared set, maintained assumptions and relative-basis rider. The visible sentence changes a conditional statement into a broad risk claim. Outcome: **`blocked_material_omission`**, even when the number itself is copied exactly.

### 7.2 Categorical blocked: INT-K08 hidden negative terminal

Full record: the governed process ends in `refusal` after exhaustion; no positive promotion exists.

Compressed summary:

> No recommendation is shown.

The summary turns a completed governed negative into ambiguous absence and allows a reader to infer that the process is pending, omitted for convenience or available for gate weakening. Outcome: **`blocked_material_omission`**.

A safe condensation would say, in plain language, that the process completed in refusal/exhaustion, preserve the decisive reason class and recourse/correction state, and manifest any confidential detail withheld.

### 7.3 Frontier: INT-K06 no-number procedural custody claim

Full record supports only:

> Commitments were sealed before result-bearing execution; the earliest qualifying attempt was used; no prohibited substitution occurred; the chronology, dissent, negative terminal and correction history are preserved.

Unsafe summary:

> The process was properly followed.

The broad sentence hides which history was actually established and may imply compliance, competence or substantive correctness. Dropping one load-bearing history step can convert a bounded falsifiable claim into an unbounded endorsement. Outcome: **`blocked_material_omission`**.

Safe shorter form:

> The release carries a no-number custody claim: pre-result sealing, first qualifying attempt, no prohibited substitution, chronology, dissent and negative outcomes are recorded. It does not establish legal compliance, competence, efficacy or production readiness.

Duplicated event prose and low-level storage paths may be dropped with manifested reasons. Outcome may be **`lossy_but_safe`** if the transcript check also passes.

### 7.4 Safe: duplicate evidence references

Full record cites the same public report in five equivalent locations. The summary retains one citation, the support relationship, source class, independence/conflict state and affected claim. The four duplicates are manifested as `duplicate_nonsemantic_reference`. No decision predicate changes. Outcome: **`lossy_but_safe`**.

### 7.5 Safe: confidential identity replaced by role

A dissenting panel member's name is protected in this audience, but the fact of dissent, the member's decision role, affected material issue, disposition and signed/dated dissent reference are preserved. Identity is dropped under a canonical confidentiality reason and is not material to mandate, conflict or recourse for the declared use. Outcome may be **`lossy_but_safe`**.

If identity is material to a disclosed conflict of interest, competence or recusal issue, the same removal becomes **`blocked_material_omission`** unless a faithful non-identifying disclosure preserves that issue.

### 7.6 Blocked: “broad consensus” after selected-set compression

The full record contains several counterexamples, one dissent and a selected low-effective-diversity subset. The summary says “experts broadly agreed” and omits the attack/counterevidence inventory. Even if no individual sentence is false in isolation, the framing changes the contestability and apparent evidential breadth. Outcome: **`blocked_material_omission`**.

### 7.7 Safe statistical redaction, conditional

Raw cells are suppressed under an approved disclosure-control rule. The public summary retains the aggregate, population/time definition, conditionality, uncertainty, contributor-threshold statement, disclosure-control reason and prohibited uses. The proposed release is checked against previous tables for differencing. Outcome may be **`lossy_but_safe`**.

The same table released without the threshold/conditionality, or in combination with a prior table that reconstructs a cell, is **`blocked_material_omission`**.

## 8. Hard cases and dispositions

| Hard case | Disposition |
|---|---|
| A limitation is “obvious” to an expert but absent from the summary. | Block unless the governed predicate set proves it immaterial for the declared audience/use. Expertise is not a substitute for visible qualification. |
| Counterevidence is confidential. | Preserve existence, affected claim, reason category, disposition and contest state; drop protected detail with canonical reason. Silence is blocked. |
| Dissent exists but did not change the majority result. | Preserve when it concerns a material issue or changes the apparent degree of consensus/reviewability. |
| Full record is available by link. | Link does not cure a materially misleading summary. |
| Summary is “more cautious” but omits the actual negative terminal. | Block. Generic caution is not equivalent to the completed negative outcome. |
| A numeric claim is replaced with qualitative language. | Safe only when the qualitative statement is entailed, does not conceal conditionality or broaden use, and the number is not needed for reasons/contestability. |
| A no-number custody claim drops a duplicated event but preserves the unique ordered history. | Potentially safe; verifier must establish that order, firstness, substitution and correction predicates are unchanged. |
| Materiality verifier returns unknown. | Block; unknown does not imply safe. |
| Individually safe views become unsafe together. | Block the proposed release or alter its content/metadata; per-view safety is not sufficient. |

## 9. Producer and gate obligations

### Producer must emit

A future approved producer extending the canonical projection/runtime-quality path must emit:

- the resolved source semantic inventory and retained/dropped mapping;
- all required per-item effects and reasons;
- the declared use/predicate version;
- transcript predecessor/current-head references;
- the two-valued loss verdict with issue codes;
- an unchanged projection-only authority boundary.

### Gate must reject

A consumer gate must reject:

- a missing, unverifiable or wrong-revision receipt;
- any `blocked_material_omission`;
- any incomplete inventory or unknown materiality;
- a receipt whose denied-use set is narrower than the source;
- a source/summary/transcript mismatch;
- a safe verdict produced before the actual candidate release, metadata and prior transcript were evaluated;
- any receipt that attempts to mint authority, approval, publication permission or a privacy/confidence number.

## 10. INT-R7 seam

INT-R8 requires, but does not construct, a proof interface in which the public proof can bind:

- source record/revision;
- audience and surface;
- retained semantic-item identifiers;
- omission classes, affected claims and canonical reasons;
- the loss verdict and rule version;
- predecessor/current transcript head and current/superseded state.

Redaction must be a well-defined operation on the proof-bound object, and the proof must not reveal dropped content merely by binding it. Signature algorithm, key policy, verification construction, rotation, revocation and anti-equivocation mechanics remain entirely with INT-R7.

## 11. Result standing

**`accepted_narrow_scope`.** The receipt semantics, parity definition, minimum retained set and loss-typing decision procedure are settled for research handoff. This artifact does not authorize the producer, wire contract or publication path, and it intentionally carries no numeric disclosure budget.
