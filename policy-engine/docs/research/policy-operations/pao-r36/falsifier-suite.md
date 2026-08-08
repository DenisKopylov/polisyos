---
title: PAO-R36 - Public Correction Falsifier Suite
research_id: PAO-R36
status: amended_research
result_standing: accepted_narrow_scope
audit_disposition_of_submitted_version: NO_GO
amendment_status: pending_independent_conformance
pinned_repository_commit: 109ba3f4
audited_commit: 1bccc012b636d6a13930735a4f748d1f8cf7b9cf
audit_commit: 9bbfd37a218222ae06c1f669b95dba37c4732765
amendment_branch: research/pao-r36-amendment
research_only: true
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization, media-type, or API contract
  - canonical owner, vendor, archive, signer, publication-of-record venue, or service appointment
  - authority grant
  - capability claim
  - legal-sufficiency or jurisdictional conclusion
  - permission to publish or open a gate
  - translation-parity mechanism design
  - recovery objective, retention period, expiry rule, or disaster-mode design
  - automatic amendment of any plan, backlog, or system-design decision
---

# Public correction falsifier suite

## 1. Execution rule

Each fixture is one world with one named detector, one frozen detector-provenance class, one exact
terminal verdict, and one forbidden green outcome. No fixture uses “if”, “or”, “as applicable”, an
unnamed failed member, or a phase-dependent expected result. Where the submitted suite combined
phases or attacks, the amended suite uses lettered variants.

A future implementation passes only by exercising the real correction path. Marker strings, field
presence, self-authored receipts, or a test-only shortcut do not pass. This applies P29, P31, P32,
P33, P35, P36, and P37.

### 1.1 Outcome vocabulary

- `BLOCK_AUTHORITY`: no `e_authority` may be appended for the transaction.
- `REJECT_TRANSACTION`: the proposed transaction object is inadmissible.
- `REJECT_EVENT(event)`: the named append event is not admitted.
- `NO_EFFECTIVE`: no `e_effective` is appended for the transaction.
- `FAIL_CLOSED(member)`: the named member may emit no current-authority/effective positive.
- `FAIL_CLOSED_ALL(X)`: every authority-bearing member in frozen set `X` may emit no positive.
- `RED(gate)`: the named gate is visibly non-green with an owned reason.
- `APPEND_INCIDENT`: preserve the prior chronology and append the later failure.
- `REJECT_AGGREGATE`: the claimed aggregate/completion result is inadmissible.
- `REJECT_RECEIPTS(correction)`: the offered receipt family is inadmissible for the named correction.
- `REJECT_CLASS_CHANGE(member)`: the attempted notification-obligation change is not admitted.
- `READMIT_REQUIRED(correction,base)`: the correction must be newly admitted against the named base.
- `PRESERVE_EFFECTIVE_EVENT`: an already appended historical effective event is not rewritten.
- `PASS`: the detector observes the specified safe property over the complete frozen denominator.

An exact verdict may contain a fixed conjunction of these outcomes. The conjunction is the one
terminal result; no branch is selected at runtime.

## 2. Common fixture and evidence binding

Unless a variant overrides a field:

- correction `C1`, predecessor `v1`, successor `v2`, notice `n2`;
- `S@sg1 = {public_page, public_export, api_current, api_versioned, machine_projection}`, denominator 5;
- `C@cg1 = {page_edge, export_edge, api_edge, origin_object_cache}`, denominator 4;
- `F@fg1 = {public_correction_stream, machine_history_stream}`, denominator 2;
- `A@ag1 = {primary_archive, public_evidence_archive}`, denominator 2;
- `L@lg1 = {uk, en}`, denominator 2;
- `N@ng1 = {sub_1, sub_2, sub_3}`, denominator 3;
- each set snapshot, generation, owner, membership rule, and predicate-provenance class was frozen at
  Step 0;
- each receipt binds
  `(correction_id,set_id,snapshot_id,generation,member_id,predicate_id,v1,v2,n2,as_of,evidence_cutoff,verifier_identity,verifier_provenance,outcome)`;
- external copies are excluded explicitly; and
- detector classes are those frozen in the single P37 table in
  `ordered-fanout-and-completeness-contract.md` §6.

The fixture names are semantic test labels, not endpoint, package, schema, service, or vendor
appointments.

## 3. Commission-required attacks, split into deterministic worlds

### F01-A — language divergence before authority

**World.** `e_authority` does not exist. `uk` and `en` are admitted in `L@lg1`; the English staged
notice omits the appeal route retained by the Ukrainian staged notice.

**Attack.** Submit both variants as parity-complete.

**Detector.** `language_protected_query_reconciler(C1,L@lg1,n2)`.

**Detector class.** `independently_reconciled`, frozen at admission.

**Exact expected verdict.** `REJECT_TRANSACTION + BLOCK_AUTHORITY + RED(translation_parity)`.

**Forbidden green outcome.** Any authority event or parity-complete result for `C1`.

### F01-B — language widening after authority

**World.** `e_authority` exists; `e_effective` does not. `uk` denies the corrected benefit; `en`
states it remains available.

**Attack.** `public_page` requests the English representation as successor-current-linked.

**Detector.** `surface_tuple_probe(C1,public_page,en,t_authority)`.

**Detector class.** `independently_reconciled`, frozen at admission.

**Exact expected verdict.** `FAIL_CLOSED(public_page) + NO_EFFECTIVE + RED(translation_parity) + APPEND_INCIDENT`.

**Forbidden green outcome.** `successor_current_linked` for the English surface.

### F02 — predecessor-current after authority

**World.** `e_authority` exists; `e_effective` does not; GY-N12 says `v2` current.

**Attack.** `public_page` returns `v1` as current.

**Detector.** `surface_tuple_probe(C1,public_page,uk,t_authority)`.

**Detector class.** `independently_reconciled`, frozen at admission.

**Exact expected verdict.** `FAIL_CLOSED(public_page) + NO_EFFECTIVE + RED(surface_convergence) + APPEND_INCIDENT`.

**Forbidden green outcome.** Any predecessor-current response after `e_authority`.

### F03-A — predecessor byte mutation before authority

**World.** `e_authority` does not exist; archived `v1` digest is frozen.

**Attack.** Change bytes at the `v1` identity.

**Detector.** `predecessor_identity_reconciler(C1,v1,primary_archive)`.

**Detector class.** `independently_reconciled`, frozen at admission.

**Exact expected verdict.** `REJECT_TRANSACTION + BLOCK_AUTHORITY + RED(history_integrity)`.

**Forbidden green outcome.** Admission of the mutated object as the original predecessor.

### F03-B — predecessor semantic-identity mutation before authority

**World.** `e_authority` does not exist; bytes are reserialized under the same `v1` identity while a
protected proposition changes.

**Attack.** Present the object as semantically identical.

**Detector.** `predecessor_semantic_identity_reconciler(C1,v1)`.

**Detector class.** `independently_reconciled`, frozen at admission.

**Exact expected verdict.** `REJECT_TRANSACTION + BLOCK_AUTHORITY + RED(history_integrity)`.

**Forbidden green outcome.** Treating changed protected semantics as the same predecessor.

### F03-C — no distinct successor before authority

**World.** `e_authority` does not exist; the transaction has no distinct `v2` object or resolvable
predecessor relation.

**Attack.** Submit a correction instruction that only replaces `v1` in place.

**Detector.** `successor_relation_reconciler(C1,v1,v2)`.

**Detector class.** `independently_reconciled`, frozen at admission.

**Exact expected verdict.** `REJECT_TRANSACTION + BLOCK_AUTHORITY + RED(history_integrity)`.

**Forbidden green outcome.** A correction with no distinct successor identity and relation.

### F03-D — predecessor mutation discovered after authority

**World.** `e_authority` exists; `e_effective` does not; `primary_archive` now returns changed bytes at
`v1`.

**Attack.** Preserve the existing green history marker.

**Detector.** `predecessor_identity_reconciler(C1,v1,primary_archive)`.

**Detector class.** `independently_reconciled`, frozen at admission.

**Exact expected verdict.** `FAIL_CLOSED(primary_archive) + NO_EFFECTIVE + RED(history_integrity) + APPEND_INCIDENT`.

**Forbidden green outcome.** Effective completion over the changed predecessor.

### F04 — controlled cache serves predecessor-current after effect

**World.** `e_effective` exists and historically names `C@cg1`; `page_edge` later serves `v1` as
current.

**Attack.** Keep the historical effective event and old green cache receipt unchanged.

**Detector.** `live_cache_tuple_probe(C1,page_edge,cg1,after_t_effective)`.

**Detector class.** `independently_reconciled`, frozen at admission.

**Exact expected verdict.** `FAIL_CLOSED(page_edge) + RED(cache_convergence) + APPEND_INCIDENT + PRESERVE_EFFECTIVE_EVENT`.

**Forbidden green outcome.** Continuing-current cache-safety claim while `page_edge` serves `v1`.

### F05-A — asynchronous subscriber failure hidden after effect

**World.** `e_effective` exists. `sub_3` was frozen as `asynchronous_receipt_permitted` and has neither
a qualifying delivery receipt nor a visible retry/escalation state.

**Attack.** Aggregate says “all subscribers notified”.

**Detector.** `notification_member_aggregate_recomputer(C1,N@ng1)`.

**Detector class.** `recomputed`, frozen at admission.

**Exact expected verdict.** `RED(notification_delivery) + REJECT_AGGREGATE + PRESERVE_EFFECTIVE_EVENT`.

**Forbidden green outcome.** An “all notified” result without 3/3 qualifying receipts.

### F05-B — synchronous subscriber unverified at effective gate

**World.** `e_authority` exists; `e_effective` does not. `sub_3` was frozen as
`qualifying_receipt_before_effect` and has no qualifying receipt.

**Attack.** Submit the effective declaration.

**Detector.** `synchronous_receipt_reconciler(C1,sub_3,ng1)`.

**Detector class.** `independently_reconciled`, frozen at admission.

**Exact expected verdict.** `REJECT_EVENT(e_effective) + NO_EFFECTIVE + RED(notification_receipt)`.

**Forbidden green outcome.** Effect while a synchronous member is unverified.

### F05-C — synchronous member moved to asynchronous after admission

**World.** `e_authority` exists; `e_effective` does not. `sub_3` was frozen as
`qualifying_receipt_before_effect`.

**Attack.** Append a transaction-local declaration changing `sub_3` to
`asynchronous_receipt_permitted` and submit effect without a receipt.

**Detector.** `notification_obligation_integrity_reconciler(C1,sub_3,ng1)`.

**Detector class.** `independently_reconciled`, frozen at admission.

**Exact expected verdict.** `REJECT_CLASS_CHANGE(sub_3) + REJECT_EVENT(e_effective) + NO_EFFECTIVE + RED(notification_obligation_integrity) + APPEND_INCIDENT`.

**Forbidden green outcome.** A transaction-local downgrade that enables effect.

### F06-A — named surface notice drops limitation before authority

**World.** `e_authority` does not exist. `public_page` staged notice omits the geographic limit
retained by the successor.

**Attack.** Submit `public_page` as notice-safe.

**Detector.** `notice_protected_query_reconciler(C1,public_page,n2)`.

**Detector class.** `independently_reconciled`, frozen at admission.

**Exact expected verdict.** `REJECT_TRANSACTION + BLOCK_AUTHORITY + RED(notice_semantic_parity)`.

**Forbidden green outcome.** Fence admission of `public_page` with the defective notice.

### F06-B — named surface notice drops limitation after authority

**World.** `e_authority` exists; `e_effective` does not. `public_page` exposes a notice omitting the
geographic limit.

**Attack.** Return successor-current-linked.

**Detector.** `surface_tuple_probe(C1,public_page,uk,t_authority)`.

**Detector class.** `independently_reconciled`, frozen at admission.

**Exact expected verdict.** `FAIL_CLOSED(public_page) + NO_EFFECTIVE + RED(notice_semantic_parity) + APPEND_INCIDENT`.

**Forbidden green outcome.** A positive observer label with the defective notice.

### F07-A — archive linkage missing before authority

**World.** `e_authority` does not exist. `public_evidence_archive` stores `v1`, `n2`, and `v2` but
cannot traverse `v1 -> n2 -> v2`.

**Attack.** Submit archive completion.

**Detector.** `archive_round_trip_reconciler(C1,public_evidence_archive,ag1)`.

**Detector class.** `independently_reconciled`, frozen at admission.

**Exact expected verdict.** `BLOCK_AUTHORITY + RED(archive_linkage)`.

**Forbidden green outcome.** Archive completion from disconnected bytes.

### F07-B — archive linkage missing after authority

**World.** `e_authority` exists; `e_effective` does not. `public_evidence_archive` loses the reverse
successor-to-notice-to-predecessor relation.

**Attack.** Preserve its old green receipt.

**Detector.** `archive_round_trip_reconciler(C1,public_evidence_archive,ag1)`.

**Detector class.** `independently_reconciled`, frozen at admission.

**Exact expected verdict.** `FAIL_CLOSED(public_evidence_archive) + NO_EFFECTIVE + RED(archive_linkage) + APPEND_INCIDENT`.

**Forbidden green outcome.** Effective archive completion with a broken reverse relation.

## 4. Additional attacks and audit-required variants

### F08-A — proposed transition would create two current heads

**World.** `v1` is current. A first accepted transition proposal for `v2a` is pending at the canonical
append point; a second proposal for `v2b` would occupy the same predecessor epoch and leave both
current.

**Attack.** Submit the second current-head event.

**Detector.** `single_head_event_recomputer(v1,v2a,v2b)`.

**Detector class.** `recomputed`, frozen at admission.

**Exact expected verdict.** `REJECT_EVENT(e_authority_v2b) + BLOCK_AUTHORITY + RED(single_current_head)`.

**Forbidden green outcome.** Two current heads at one authenticated cutoff.

### F08-B — restore contains two current heads

**World.** Recovery completes with `v2a` and `v2b` both current at the same authenticated cutoff.

**Attack.** Resume authority-positive service.

**Detector.** `restored_head_recomputer(C1,restored_chronology)`.

**Detector class.** `recomputed`, frozen at admission.

**Exact expected verdict.** `FAIL_CLOSED_ALL(S) + NO_EFFECTIVE + RED(single_current_head) + APPEND_INCIDENT`.

**Forbidden green outcome.** Any current-authority response from the forked restore.

### F09-A — later revocation erases historical issuance

**World.** `v1` was signed before an authenticated revocation cutoff with no contrary compromise
evidence; terminal INT-R7 dimensions establish issuer issuance and durable verification.

**Attack.** Verifier reports the original was never authentic solely because the key is now revoked.

**Detector.** `int_r7_dimension_reconciler(v1,query_after_revocation)`.

**Detector class.** `independently_reconciled`, frozen at admission.

**Exact expected verdict.** `RED(verification_semantics) + REJECT_AGGREGATE`.

**Forbidden green outcome.** A collapsed result that rewrites established issuance as false.

### F09-B — historical signature mints current authority

**World.** `v1` remains historically authentic; `e_authority` establishes `v2` current.

**Attack.** `api_current` treats the valid `v1` signature as proof that `v1` remains current.

**Detector.** `surface_tuple_probe(C1,api_current,uk,t_authority)`.

**Detector class.** `independently_reconciled`, frozen at admission.

**Exact expected verdict.** `FAIL_CLOSED(api_current) + RED(verification_semantics) + APPEND_INCIDENT`.

**Forbidden green outcome.** Current authority derived from historical signature validity.

### F10 — adverse correction disguised as neutral

**World.** `e_authority` does not exist. `v2` reduces eligibility for a known class; the proposed
classification says typographical/neutral and supplies no independently reconciled affected-party
rule.

**Attack.** Submit the ordinary asynchronous notification path.

**Detector.** `risk_and_obligation_reconciler(C1,v1,v2)`.

**Detector class.** `independently_reconciled`, frozen at admission.

**Exact expected verdict.** `BLOCK_AUTHORITY + RED(risk_direction) + RED(affected_party_decision)`.

**Forbidden green outcome.** Neutral classification or asynchronous admission from producer assertion.

### F11-A — recovery restores predecessor-current

**World.** Before recovery, `v2` is current and effective. Restored chronology makes `v1` current.

**Attack.** Resume public service.

**Detector.** `restored_head_recomputer(C1,restored_chronology)`.

**Detector class.** `recomputed`, frozen at admission.

**Exact expected verdict.** `FAIL_CLOSED_ALL(S) + RED(ops_r14_recovery_invariant) + APPEND_INCIDENT + PRESERVE_EFFECTIVE_EVENT`.

**Forbidden green outcome.** Any predecessor-current response from the restored system.

### F11-B — recovery omits notice while successor is current

**World.** Restored chronology establishes `v2` current but `n2` is absent.

**Attack.** Resume successor-current service.

**Detector.** `restored_tuple_reconciler(C1,v1,v2,n2)`.

**Detector class.** `independently_reconciled`, frozen at admission.

**Exact expected verdict.** `FAIL_CLOSED_ALL(S) + RED(ops_r14_recovery_invariant) + APPEND_INCIDENT + PRESERVE_EFFECTIVE_EVENT`.

**Forbidden green outcome.** Successor-current without the admitted notice after restore.

### F11-C — recovery omits completion evidence

**World.** Restored chronology contains `v1`, `v2`, `n2`, and the current-head event, but lacks the
member-bound evidence needed to establish the effective declaration.

**Attack.** Project the correction as effective.

**Detector.** `restored_completion_recomputer(C1,R_post,S,C,F,A,L,K)`.

**Detector class.** `recomputed`, frozen at admission.

**Exact expected verdict.** `FAIL_CLOSED_ALL(S) + RED(ops_r14_recovery_invariant) + APPEND_INCIDENT + PRESERVE_EFFECTIVE_EVENT`.

**Forbidden green outcome.** Effective projection from incomplete restored evidence.

### F12 — mutable live subscriber registry rewrites frozen denominator

**World.** `N@ng1` contains 3 members. `sub_3` lacks a qualifying receipt. The live registry later
contains only `sub_1` and `sub_2`.

**Attack.** Recompute completion as 2/2 using the live registry.

**Detector.** `notification_member_aggregate_recomputer(C1,N@ng1)`.

**Detector class.** `recomputed`, frozen at admission.

**Exact expected verdict.** `RED(notification_cohort_integrity) + REJECT_AGGREGATE`.

**Forbidden green outcome.** Changing historical denominator 3 to live denominator 2.

### F13-A — historical query made retroactive

**World.** `v1` is current until `e_authority`; a query cutoff is one chronology position before
`e_authority`.

**Attack.** `api_versioned` returns `v2` as current at the historical cutoff.

**Detector.** `current_at_cutoff_recomputer(C1,api_versioned,before_e_authority)`.

**Detector class.** `recomputed`, frozen at admission.

**Exact expected verdict.** `FAIL_CLOSED(api_versioned) + NO_EFFECTIVE + RED(temporal_semantics)`.

**Forbidden green outcome.** Retroactive currentness for `v2`.

### F13-B — current query returns predecessor after authority

**World.** `e_authority` exists; query cutoff is immediately after it; `e_effective` does not exist.

**Attack.** `api_current` returns `v1` as current.

**Detector.** `current_at_cutoff_recomputer(C1,api_current,after_e_authority)`.

**Detector class.** `recomputed`, frozen at admission.

**Exact expected verdict.** `FAIL_CLOSED(api_current) + NO_EFFECTIVE + RED(temporal_semantics) + APPEND_INCIDENT`.

**Forbidden green outcome.** Predecessor-current after the canonical transition.

### F14 — uncontrolled mirror counted as cleared

**World.** Controlled sets are complete. An external third-party mirror still shows `v1` without
notice.

**Attack.** Proposed effective notice says “all copies and all caches have been corrected”.

**Detector.** `completion_scope_recomputer(C1,S,C,external_exclusions)`.

**Detector class.** `recomputed`, frozen at admission.

**Exact expected verdict.** `REJECT_TRANSACTION + RED(completeness_scope)`.

**Forbidden green outcome.** Universal internet-cleared language from bounded evidence.

### F15-A — notice reachable but successor unreachable before authority

**World.** `e_authority` does not exist. `public_page` can retrieve `n2` but cannot retrieve/verify
`v2`.

**Attack.** Submit the staged notice as transition-ready.

**Detector.** `notice_relation_reconciler(C1,public_page,n2,v2)`.

**Detector class.** `independently_reconciled`, frozen at admission.

**Exact expected verdict.** `BLOCK_AUTHORITY + RED(referential_integrity)`.

**Forbidden green outcome.** Authority transition with an unreachable successor.

### F15-B — notice reachable but successor unreachable after authority

**World.** `e_authority` exists; `e_effective` does not. `public_page` can retrieve `n2` but not `v2`.

**Attack.** Return successor-current-linked.

**Detector.** `notice_relation_reconciler(C1,public_page,n2,v2)`.

**Detector class.** `independently_reconciled`, frozen at admission.

**Exact expected verdict.** `FAIL_CLOSED(public_page) + NO_EFFECTIVE + RED(referential_integrity) + APPEND_INCIDENT`.

**Forbidden green outcome.** A current notice with an unreachable successor.

### F16 — self-attested completion survives member-result deletion

**World.** A draft effective declaration says `C@cg1` is 4/4 complete. Remove the `page_edge` result;
keep denominator, aggregate count, and every green marker.

**Attack.** Submit effect.

**Detector.** `completion_member_join_recomputer(C1,C@cg1)`.

**Detector class.** `recomputed`, frozen at admission.

**Exact expected verdict.** `REJECT_AGGREGATE + REJECT_EVENT(e_effective) + NO_EFFECTIVE + RED(completeness_evidence)`.

**Forbidden green outcome.** Completion with 3 member results and 4/4 markers.

## 5. Amendment-specific attacks

### F17 — falsify the declaration while keeping it intact

**World.** `page_edge` has a valid-looking declaration and green receipt saying it cannot serve
predecessor-current. The declaration, receipt, hashes, and marker strings remain intact. The live
property is changed so `page_edge` serves `v1` as current.

**Attack.** Submit `Complete(C)` and effect.

**Detector.** `live_cache_tuple_probe(C1,page_edge,cg1,before_e_effective)`.

**Detector class.** `independently_reconciled`, frozen at admission.

**Exact expected verdict.** `FAIL_CLOSED(page_edge) + REJECT_EVENT(e_effective) + NO_EFFECTIVE + RED(declared_predicate_false)`.

**Forbidden green outcome.** A gate that tests the declaration rather than the live property.

### F18 — serialized stale-base correction loses an intervening correction

**World.** C1 and C2 are both staged against `v1`. C1 appends `v1 -> v2`; exactly one current head
exists. C2 then proposes `v1 -> v3`; exactly one head would still exist under last-writer wins.

**Attack.** Append C2 without re-admission against `v2`.

**Detector.** `admitted_base_head_recomputer(C2,v1,current_head=v2)`.

**Detector class.** `recomputed`, frozen at admission.

**Exact expected verdict.** `REJECT_EVENT(e_authority_C2) + READMIT_REQUIRED(C2,v2) + RED(base_head_integrity)`.

**Forbidden green outcome.** A single-head `v3` state that silently loses C1.

### F19 — complete receipt family replayed from another correction

**World.** C1 and C2 use identical member names and denominators. Every C1 receipt is valid for C1.
C2 has no own receipts.

**Attack.** Offer the complete C1 receipt family to `Complete(S/C)` for C2.

**Detector.** `receipt_tuple_join_recomputer(C2,S,C)`.

**Detector class.** `recomputed`, frozen at admission.

**Exact expected verdict.** `REJECT_RECEIPTS(C2) + REJECT_EVENT(e_effective_C2) + NO_EFFECTIVE + RED(receipt_binding)`.

**Forbidden green outcome.** C2 completion using C1-bound evidence.

### F20-A — effective event appended before final synchronous receipt

**World.** `sub_3` is synchronous and unverified. All other gates are green.

**Attack.** Append `e_effective` before the receipt.

**Detector.** `event_precedence_recomputer(C1,chronology,receipt_cutoffs)`.

**Detector class.** `recomputed`, frozen at admission.

**Exact expected verdict.** `REJECT_EVENT(e_effective) + NO_EFFECTIVE + RED(event_order)`.

**Forbidden green outcome.** Effect before the final synchronous evidence exists.

### F20-B — later append carries a backdated effective time

**World.** Final synchronous evidence arrives at time `T2`. Proposed `e_effective` is appended later
at `T3` but declares effective time `T1`, where `T1 < T2`.

**Attack.** Project `T1` as `t_effective`.

**Detector.** `anti_backdating_recomputer(C1,e_effective,evidence_cutoffs)`.

**Detector class.** `recomputed`, frozen at admission.

**Exact expected verdict.** `REJECT_EVENT(e_effective) + NO_EFFECTIVE + RED(anti_backdating)`.

**Forbidden green outcome.** An effective time earlier than its decisive evidence.

### F20-C — equal display timestamps hide reversed append order

**World.** `e_effective` and the final member receipt display the same timestamp; append sequence puts
`e_effective` first.

**Attack.** Accept equality of timestamps as sufficient ordering.

**Detector.** `event_sequence_recomputer(C1,chronology)`.

**Detector class.** `recomputed`, frozen at admission.

**Exact expected verdict.** `REJECT_EVENT(e_effective) + NO_EFFECTIVE + RED(event_order)`.

**Forbidden green outcome.** Reversed event sequence hidden by equal display timestamps.

### F21 — controlled generation changes after snapshot

**World.** `S@sg1` is frozen. Before effect, live generation `sg2` adds controlled surface
`api_mobile`. `api_mobile` has no member probe.

**Attack.** Keep the old 5-member denominator and classify `api_mobile` as external.

**Detector.** `controlled_generation_recomputer(C1,S@sg1,live=sg2)`.

**Detector class.** `recomputed`, frozen at admission.

**Exact expected verdict.** `FAIL_CLOSED(api_mobile) + REJECT_EVENT(e_effective) + NO_EFFECTIVE + READMIT_REQUIRED(C1,v2) + RED(generation_integrity)`.

**Forbidden green outcome.** Effect against stale `sg1` while controlled `sg2` is live.

### F22-A — correct successor paired with wrong notice

**World.** `e_authority` exists; `public_page` selects `v2` but links notice `n_other` from another
correction.

**Attack.** Label the response successor-current-linked.

**Detector.** `surface_tuple_probe(C1,public_page,uk,t_authority)`.

**Detector class.** `independently_reconciled`, frozen at admission.

**Exact expected verdict.** `FAIL_CLOSED(public_page) + NO_EFFECTIVE + RED(observer_tuple) + APPEND_INCIDENT`.

**Forbidden green outcome.** Positive observer label with a wrong correction notice.

### F22-B — staged notice after authority

**World.** `e_authority` exists; `public_page` selects `v2` and correct `n2`, but notice phase remains
`staged`.

**Attack.** Label the response successor-current-linked.

**Detector.** `surface_tuple_probe(C1,public_page,uk,t_authority)`.

**Detector class.** `independently_reconciled`, frozen at admission.

**Exact expected verdict.** `FAIL_CLOSED(public_page) + NO_EFFECTIVE + RED(observer_tuple) + APPEND_INCIDENT`.

**Forbidden green outcome.** Positive observer label with a staged notice after authority.

### F22-C — stale authenticated currentness snapshot

**World.** `e_authority` exists in the latest canonical chronology. `public_page` supplies an older
authentic snapshot in which `v1` was current.

**Attack.** Present the supplied snapshot as latest and label `v1` current.

**Detector.** `surface_tuple_probe(C1,public_page,uk,t_authority)`.

**Detector class.** `independently_reconciled`, frozen at admission.

**Exact expected verdict.** `FAIL_CLOSED(public_page) + NO_EFFECTIVE + RED(observer_tuple) + APPEND_INCIDENT`.

**Forbidden green outcome.** A current positive from `supplied_snapshot_only` rather than
`latest_established_under_policy`.

## 6. Suite coverage and preservation of confirmed strengths

The amended suite preserves the audit-confirmed attacks:

- F09 remains two real revoked-key laundering directions;
- F13 remains exact before/after `as_of` inversion;
- F16 remains remove-property/keep-markers at the member-evidence layer;
- F17 extends the same instinct to declared gate predicates;
- F18 covers serialized stale-base corrections with one head at every instant;
- F19 rejects cross-correction receipt replay;
- F20 makes event order and anti-backdating falsifiable;
- F21 binds frozen sets to source generations; and
- F22 proves the three observer labels are projections of a full correction tuple.

No fixture defines translation mechanics, recovery objectives, expiry rules, schemas, endpoints, or
legal sufficiency. Those ownership boundaries remain unchanged.
