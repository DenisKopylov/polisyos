---
title: PAO-R36 - Ordered Correction Fan-out and Completeness Contract
research_id: PAO-R36
status: amended_research
result_standing: accepted_narrow_scope
audit_disposition_of_submitted_version: NO_GO
amendment_status: pending_independent_conformance
audited_commit: 1bccc012b636d6a13930735a4f748d1f8cf7b9cf
audit_commit: 9bbfd37a218222ae06c1f669b95dba37c4732765
pinned_repository_commit: 109ba3f4
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

# Ordered correction fan-out and completeness contract

## 1. Answer first

A correction is not one write followed by best-effort propagation. It is an append-only authority
transaction with a public observer and two distinct boundaries:

1. `t_authority`: the existing GY-N12 currentness owner appends the corrected successor as the
   current head and makes the predecessor non-current without erasing historical authenticity; and
2. `t_effective`: a later append-only declaration states that the explicitly enumerated synchronous
   fan-out has been independently verified against frozen snapshots, generations, predicates, and
   evidence cutoffs.

The observer invariant is not widened to repair an ordering error. From `t_authority` onward, a
controlled surface may expose only the successor as current and correctly linked, the predecessor as
historical and correctly linked, or a fail-closed unavailable state. The notice must already be
resolvable and the authority fence must already be armed before the current-head event is appended.

Actual delivery to an ordinary subscriber may continue after `t_effective` only when the member's
notification class was frozen at admission as asynchronous-permitted, the delivery intent was
accepted before authority transition, and every failure remains visible. A member classified as
requiring qualifying receipt before effect can never be moved to the asynchronous class inside the
same correction transaction.

This document is the controlling ordered contract. The step table in the primary report reproduces
Section 7 verbatim.

## 2. Fixed semantic law and ownership boundary

This contract consumes, without reopening:

- `PV-K01`: current authority is separately reportable and bound to an authenticated `as_of` cutoff;
- `PV-K02`: historical authenticity and current authority are distinct, non-erasing propositions;
- `PV-K04`: a projection may reduce detail but may not amplify truth, certainty, authority, currency,
  or permission;
- `S0-K08`: correction appends; history is not rewritten;
- `S0-K06`, applied through `P37`: a gate cannot obtain authority from a declared unknown inside its
  own decisive predicate;
- `INT-K05`: composition does not create a second canonical owner; and
- GY-N12: one append-only epoch/currentness owner supplies current head, `as_of`, stale,
  revalidation, reissue, withdrawal, and supersession chronology.

The final INT-R7 public-verification/current-authority decomposition is read through the terminal
controlling amendment at
`policy-engine/docs/research/policy-operations/int-r7/public-verification-profile.md:620-760`.
Earlier issuance, revocation, migration, and compromise examples remain historical detail only.

No rule below appoints a package, endpoint, database, media type, vendor, custodian, archive, signer,
or publication-of-record venue.

## 3. Event and time model

The contract distinguishes event append order from display timestamps.

- `e_stage` is the first admitted staging event.
- `e_authority` is the single current-head transition event.
- `e_effective` is the effective declaration event.
- `seq(e)` is the monotonically increasing position in the append-only correction chronology.
- `time(e)` is the authenticated event time assigned by the canonical chronology.

The required predicate is:

`seq(e_stage) < seq(e_authority) < seq(e_effective)`

and

`time(e_stage) <= time(e_authority) <= time(e_effective)`.

Equal authenticated timestamps are permitted only when append sequence still preserves the strict
order. A surface derives `t_stage`, `t_authority`, and `t_effective` from those authenticated events;
it cannot accept an earlier producer-supplied display time. Every evidence cutoff used by the
effective gate must be at or before `time(e_effective)`. A later append carrying a backdated
`effective_at`, an effective event before the final synchronous receipt, or equal display timestamps
with reversed sequence is rejected and leaves `t_effective` absent.

## 4. Frozen enumerated sets and phase-correct record membership

No phrase of the form "all X" is valid unless `X` is a named snapshot with a cutoff, owner,
membership rule, exact member list or independently resolvable commitment, count, and source
generation.

| Set | Frozen membership at admission | Source of completeness |
| --- | --- | --- |
| `R_gate` | Every correction-transaction record required to exist before the effective declaration: admission record; predecessor; staged/current successor; notice; issuer/risk/old-version/key determinations; `S/C/N/P/F/A/L/K` snapshots; predicate-provenance snapshot; registry-generation records; notification-intent records; authority-transition event; and every required pre-effective status, evidence, and incident record. | Transaction admission rule plus append-only chronology. The effective declaration is not a member of `R_gate` because it does not yet exist; that phase rule is declared, frozen, and counted, not an ad hoc exclusion. |
| `R_post` | Exactly `R_gate` plus the effective declaration appended by Step 12. | The effective event names the `R_gate` snapshot and creates `R_post = R_gate union {effective_declaration}` with `|R_post| = |R_gate| + 1`. |
| `S` | Every PolicyOS-controlled authority-bearing public rendering and route variant that can answer currentness or render the record. | Controlled-surface registry snapshot and exact active registry generation. |
| `C` | Every controlled cache namespace, variant family, edge/node class, negative-cache path, and key derivation capable of serving a member of `S`. | Cache-control inventory snapshot and exact active configuration generation. |
| `N` | Every registered subscriber eligible at the cohort cutoff, including scope, delivery class, and accepted-intent requirement. | Subscriber registry snapshot. |
| `P` | Every directly affected person or organization admitted by the authorized institutional decision, together with each member's frozen receipt obligation. | Institutional cohort decision plus independently reconciled admission record. |
| `F` | Every controlled feed projection, partition, cursor domain, or replay segment in which the correction must be observable. | Machine-consumer registry snapshot and generation. |
| `A` | Every named archive, preservation repository, or controlled copy for which PolicyOS claims correction linkage. | Archive/custody registry snapshot. |
| `L` | Every authoritative language variant admitted for the record. | Language-admission snapshot under Atlas D4 and the future INT-R6 parity interface. |
| `K` | Original signature, successor signature, applicable key-status events, trusted-time evidence, preservation evidence, snapshot-selection evidence, and currentness evidence required for the reported INT-R7 outcome. | INT-R7 evidence closure read through terminal controlling Section 18. |

At the effective gate, the record-set predicate is `Complete(R_gate)`. Step 12 then appends the
declaration and thereby creates `R_post`; it does not silently leave the declaration outside the
record set. A post-append verifier checks the one-member count delta and the declaration's content
binding. A missing declaration cannot be hidden as an exclusion, and a draft or placeholder
declaration cannot satisfy `Complete(R_gate)`.

Unknown external caches, screenshots, downloads, mirrors, search indexes, and third-party
republications are not silently added to a controlled set and are not claimed cleared. They are
recorded as explicit exclusions and public limitations. A PolicyOS-controlled member discovered
later is never reclassified as external merely to preserve a denominator.

## 5. Structural completeness, generation lock, and receipt binding

For a frozen set `X`, `Complete(X,t)` is true only when:

1. the named snapshot and source generation resolve;
2. the live controlled generation equals the admitted generation at the relevant gate;
3. every frozen member joins to exactly one qualifying member result;
4. each result is independently recomputed or independently reconciled under the predicate class
   frozen at admission;
5. no member is unresolved, contradictory, stale beyond the admitted cutoff, or supported only by a
   declaration from the party constrained by the gate;
6. exclusions and uncontrolled copies are explicit; and
7. the completion assertion reproduces the same snapshot identity, generation, denominator, and
   evidence cutoff.

Compactly:

`Complete(X,t) := SnapshotFrozen(X) AND GenerationLive(X)=GenerationAdmitted(X) AND forall x in X: QualifyingBoundReceipt(x,t) AND no unresolved x`.

Every member receipt must content-bind this exact tuple:

`(correction_id, set_id, snapshot_id, source_generation, member_id, predicate_id, selected_predecessor_id, selected_successor_id, selected_notice_id, authenticated_as_of, evidence_cutoff, verifier_identity, verifier_provenance, outcome)`.

An aggregate joins only exact tuple matches. A valid receipt from another correction, another
snapshot, another generation, another predicate, another version/notice selection, or another cutoff
is invalid even when member names and counts are identical. A self-attested percentage, a preserved
green marker, or an aggregate without member-bound evidence is not a receipt.

If the live `S` or `C` generation changes after admission and before effect, the transaction cannot
remain on the old denominator. Before `t_authority`, it is re-admitted with new frozen snapshots.
After `t_authority`, the new member is covered by the already-armed global fail-closed fence, the
effective gate remains red, and a new admission/re-probe is required. The generation mismatch cannot
be waived by editing a hand-written member list.

## 6. `P37` predicate-provenance classification

### 6.1 Classes and admission freeze

Step 0 appends one immutable `PredicateProvenanceSnapshot` for every load-bearing predicate in this
package. Each entry is labelled exactly one of:

- `recomputed`: derived from the canonical controlled artifact or append-only history;
- `independently_reconciled`: compared with a second source that did not produce the proposition;
- `consumer_asserted`: supplied by the downstream consumer whose action the gate constrains;
- `institutionally_supplied`: supplied by an authorized institutional process but not yet
  independently reconciled for this gate; or
- `not_established`: unavailable, conflicting, mutable, or unsupported.

The label, evidence source, owner, cutoff, and predicate identity are frozen at admission. A later
relabel is a new append-only decision and cannot change the gate result inside the existing
transaction. A decisive predicate labelled `consumer_asserted`, `institutionally_supplied`, or
`not_established` cannot produce a positive gate. It blocks, or—only where the contract explicitly
permits a lower-authority statement—degrades the claim. Institutionally supplied inputs may become
decisive only after the gate records independent reconciliation against the competent non-producing
record. Unknown notification obligation defaults to the stricter synchronous class.

### 6.2 Complete classification table

Every identifier below is a separate frozen predicate entry, even where several entries share one
row for readability.

| Predicate identifier(s) | What the gate turns on | Frozen class required for a positive | Fail-closed/degraded rule |
| --- | --- | --- | --- |
| `COMPLETE-R-GATE` | All pre-declaration transaction records exist and bind this correction. | `recomputed` | Any missing/mismatched record means no effective declaration. |
| `POST-R-APPEND` | `R_post = R_gate union {effective_declaration}` and the count rose by one. | `recomputed` | The event remains in history but no public effective positive is projected until the postcondition reconciles. |
| `COMPLETE-S` | Every admitted controlled surface is in a safe tuple state. | `independently_reconciled` | Missing, stale, self-attested, or generation-mismatched member means no effect and fail closed. |
| `COMPLETE-C` | Every admitted controlled cache/variant cannot serve predecessor-current. | `independently_reconciled` | Same; an invalidation acknowledgement without a read probe is not positive. |
| `COMPLETE-N-INTENT` | Every `N` member has an accepted intent bound to the frozen cohort. | `recomputed` | Missing intent blocks authority transition. |
| `COMPLETE-P-RECEIPT` | Every synchronous `P` member has a qualifying receipt. | `independently_reconciled` | `consumer_asserted`, merely `institutionally_supplied`, missing, or downgraded classification means no effect. |
| `COMPLETE-F` | Every feed member exposes the same correction tuple. | `independently_reconciled` | Missing partition/cursor result means no effect. |
| `COMPLETE-A` | Every claimed archive preserves identities and bidirectional links. | `independently_reconciled` | Disconnected bytes or missing archive member mean no effect. |
| `COMPLETE-L` | Every authoritative language preserves the protected semantic identity. | `independently_reconciled` | INT-R6 evidence absent/divergent means no multilingual positive and blocks the configured authority claim. |
| `COMPLETE-K` | INT-R7 dimensions, snapshot selection, and obtainability satisfy the requested outcome. | `independently_reconciled` | Read through terminal Section 18; any non-positive dimension prevents the public-current outcome. |
| `OBS-SUCCESSOR-CURRENT-LINKED` | A surface may assert the successor as current. | `independently_reconciled` | Wrong correction/notice, staged notice, stale `as_of`, unfaithful projection, or language divergence collapses to `unavailable_fail_closed`. |
| `OBS-PREDECESSOR-HISTORICAL-LINKED` | A surface may render the predecessor as historical. | `independently_reconciled` | Current-positive, missing successor/notice relation, or wrong cutoff collapses to fail closed. |
| `OBS-UNAVAILABLE-FAIL-CLOSED` | A surface emits no current-authority positive. | `recomputed` | It may expose a bounded failure, never a synthetic current answer. |
| `STEP-0-PRE` | Published predecessor, current head, requester role, and admission source resolve. | `independently_reconciled` | Otherwise transaction admission fails. |
| `STEP-0-GATE` | Set snapshots, generations, predicate classes, and notification obligation are immutable. | `recomputed` | Mutable/unresolved admission data blocks every later step. |
| `STEP-1-PRE` | Step 0 exists. | `recomputed` | No classification work is authoritative without the admitted transaction. |
| `STEP-1-GATE` | Issuer authority, risk direction, old-version significance, and INT-R7 disposition are usable. | `independently_reconciled` | Raw institutional declarations cannot produce a positive; unresolved values block. |
| `STEP-2-PRE` | Canonical predecessor identity and Step 1 gate resolve. | `recomputed` | Missing base blocks successor append. |
| `STEP-2-GATE` | Successor is distinct, immutable, and correctly linked to the admitted base. | `independently_reconciled` | Mutation, fork, cycle, or stale base blocks. |
| `STEP-3-PRE` | Predecessor and successor resolve. | `recomputed` | Notice cannot be derived from unresolved endpoints. |
| `STEP-3-GATE` | Staged notice is public, non-current, tuple-bound, and PV-K04 safe. | `independently_reconciled` | Missing/defective/wrong notice blocks the fence and authority transition. |
| `STEP-4-PRE` | Step 3 notice and version identities resolve. | `recomputed` | Retrieval staging cannot proceed on aliases alone. |
| `STEP-4-GATE` | Every `S` member can answer exact-version and authenticated `as_of` queries safely. | `independently_reconciled` | Any member failure blocks the fence. |
| `STEP-5-PRE` | Correction tuple is stable and staged. | `recomputed` | Feed admission cannot invent an effective state. |
| `STEP-5-GATE` | Every `F` member exposes the staged tuple without an effective positive. | `independently_reconciled` | Missing or amplified feed member blocks. |
| `STEP-6-PRE` | Record identities, signatures, and notice resolve. | `recomputed` | Archive linking cannot operate on unresolved objects. |
| `STEP-6-GATE` | Every `A` member passes identity and round-trip linkage. | `independently_reconciled` | Missing/disconnected archive blocks. |
| `STEP-7-PRE` | `L` and the INT-R6 interface are admitted. | `recomputed` | Unresearched mechanism is not invented locally. |
| `STEP-7-GATE` | Every authoritative language passes the external parity result. | `independently_reconciled` | `not_established` parity blocks the configured multilingual claim and authority transition. |
| `STEP-8-PRE` | `N/P` membership and per-member receipt class were frozen at Step 0. | `recomputed` | A missing or mutable obligation record blocks. |
| `STEP-8-GATE` | Intents are accepted and every pre-authority notification predicate is satisfied. | `independently_reconciled` | Attempted sync-to-async movement is rejected and recorded. |
| `STEP-9-PRE` | Steps 0-8 are green against the same snapshots and generations. | `recomputed` | Any earlier red gate prevents fence arming. |
| `STEP-9-GATE` | The authority fence is proved over every admitted `S/C` path before authority changes. | `independently_reconciled` | Marker/config assertion alone is insufficient; no `t_authority`. |
| `STEP-10-PRE` | Staged notice resolves and the proved fence remains armed. | `recomputed` | This closes the two crash windows; no append otherwise. |
| `STEP-10-GATE` | Exactly one authenticated current-head event is appended on the admitted base. | `recomputed` | Indeterminate append permits no current-authority positive. |
| `STEP-11-PRE` | `t_authority` exists and generations still match. | `recomputed` | Generation drift keeps effect red. |
| `STEP-11-GATE` | Exact member-bound probes satisfy `R_gate/S/C/F/A/L/K` and synchronous receipt predicates. | `independently_reconciled` | Any mismatch means no effect and an incident after authority. |
| `STEP-12-PRE-ORDER` | Event order, authenticated times, and evidence cutoffs are valid. | `recomputed` | Early/backdated/reversed chronology blocks the event. |
| `STEP-12-PRE-COMPLETENESS` | Every synchronous member predicate is positive. | `independently_reconciled` | A declaration without the independently observed property cannot pass. |
| `STEP-12-GATE` | Effective event is appended once, at its real chronology position, and creates `R_post`. | `recomputed` | Backdating, early append, duplicate append, or wrong record delta is rejected. |
| `STEP-13-PRE-TRANSACTION` | The correction transaction and accepted notification intents exist. | `recomputed` | Delivery processing cannot invent or rewrite authority/effect events. |
| `STEP-13-GATE` | Notification aggregates derive from frozen members and receipts. | `recomputed` | No “all notified” claim without every qualifying receipt. |
| `F01-A`, `F01-B`, `F02`, `F03-A`, `F03-B`, `F03-C`, `F03-D`, `F04`, `F06-A`, `F06-B`, `F07-A`, `F07-B`, `F09-A`, `F09-B`, `F10`, `F11-B`, `F15-A`, `F15-B`, `F17`, `F22-A`, `F22-B`, `F22-C` detectors | Live or second-source reconciliation of projection, identity, notice, surface/cache/archive, verification, risk, recovery-reference, and tuple properties. | `independently_reconciled` | Stored or producer-declared green status cannot override a contradictory property. |
| `F05-B`, `F05-C` detectors | Frozen synchronous receipt and notification-obligation integrity. | `independently_reconciled` | Missing receipt or transaction-local downgrade remains red. |
| `F05-A`, `F08-A`, `F08-B`, `F11-A`, `F11-C`, `F12`, `F13-A`, `F13-B`, `F14`, `F16`, `F18`, `F19`, `F20-A`, `F20-B`, `F20-C`, `F21` detectors | Canonical-history/member-join/generation/event-scope recomputation. | `recomputed` | Marker, live-registry, supplied snapshot, or reused receipt cannot replace canonical recomputation. |

### 6.3 Falsify-the-declaration probe

The declaration layer is itself adversarially tested. Keep an admitted declaration and every marker
string intact, then make the declared property false—for example, make `page_edge` return
predecessor-current while its receipt still says safe. `COMPLETE-C`, `STEP-11-GATE`, and the
effective gate must turn red because they re-probe/reconcile the property. A green result would prove
that the procedure tests the declaration rather than the predicate and would violate `P37`.

## 7. Single controlling order

The following table is normative for the research contract and is reproduced verbatim in the primary
report.

| Step | Preconditions | Effect | Failure-partway behavior | Verifiable evidence | Gate timing | Forbidden observation closed by this order |
| --- | --- | --- | --- | --- | --- | --- |
| 0. Admit and freeze | Published predecessor, current-head answer, requester role, and correction identity resolve. | Open one transaction; freeze `R_gate/S/C/N/P/F/A/L/K`, source generations, predicate-provenance labels, external exclusions, and each member's notification obligation at one cutoff. | No authority change; prepared objects remain non-current. | Snapshot identities, members, counts, owners, generation ids, obligation classes, and immutable predicate ledger. | Before every later step. | Prevents a mutable denominator or gate predicate from being chosen after the transaction begins. |
| 1. Classify and reconcile | Step 0 exists; original record and status evidence resolve. | Independently reconcile issuer authority, risk direction, old-version significance, affected-party rule, and INT-R7 dimensions. | Unknown, merely declared, or contradictory predicates block. | Non-producing reconciliation evidence and terminal INT-R7 Section 18 outcome. | Before successor admission. | Prevents neutral/admissible labels from being manufactured by the party constrained by the gate. |
| 2. Append staged successor | Steps 0-1 pass; admitted base head is still canonical. | Append a distinct non-current successor with immutable predecessor relation and change basis. | Mutation, fork, cycle, stale base, or partial append remains staged/abandoned and non-current. | Identity comparison, graph traversal, base-head check, replay of predecessor. | Before notice publication. | Prevents in-place rewrite and serialized last-writer loss. |
| 3. Publish the staged notice | Predecessor and successor resolve; PV-K04 protected semantics are available. | Create, verify, and make publicly resolvable a separately identified notice in `staged/non-current` phase, bound to the same correction tuple. | Defective or unreachable notice is rejected; successor remains non-current. | Protected-query comparison, notice/predecessor/successor links, public resolution probe. | Before fence arming and before `t_authority`. | Closes the window in which the successor could become current with no notice. |
| 4. Stage versioned and `as_of` retrieval | Step 3 passes. | Every `S` member can distinguish exact versions, historical authenticity, current authority, notice phase, and authenticated cutoff. | Failed member cannot be admitted to the fence proof. | Exact-version and before/after-cutoff probes for every admitted surface. | Before fence arming. | Prevents aliases/default views from selecting the predecessor as current after transition. |
| 5. Stage correction-feed observation | Correction tuple and staged notice resolve. | Every `F` member exposes the staged non-effective correction tuple. | Missing/amplified feed member blocks. | Per-member feed observation bound to `F` snapshot/generation. | Before fence arming. | Prevents a machine path from omitting the correction while public paths prepare to switch. |
| 6. Establish archive linkage | Record identities, notice, signatures, and status evidence resolve. | Every `A` member preserves predecessor, notice, successor, and bidirectional relations. | Missing or disconnected archive member blocks. | Round-trip traversal and independent content identity. | Before fence arming. | Prevents preservation of bytes without the correction relation. |
| 7. Reconcile authoritative-language parity | `L` is frozen; the future INT-R6 interface supplies evidence. | Every authoritative language binds the same protected correction semantics. | `not_established` or divergent parity blocks; PAO-R36 defines no mechanism. | INT-R6 result against the frozen `L` snapshot. | Before fence arming. | Prevents one language from widening permission or omitting recourse during the switch. |
| 8. Admit notification intents | `N/P` membership and receipt obligations were frozen at Step 0; notice is complete. | Accept a correction-bound intent for every member and verify every pre-authority obligation. | Missing intent or attempted obligation downgrade blocks and is appended as an attempted change. | Exact cohort join, immutable obligation class, accepted-intent evidence. | Before fence arming. | Prevents a missed recipient from being removed or reclassified to obtain green. |
| 9. Arm and prove the authority fence | Steps 0-8 pass against unchanged snapshots and generations. | Prove that every admitted `S/C` path will return only a safe full correction tuple or fail closed from the instant of authority transition. | No authority event is appended; marker-only/config-only proof is insufficient. | Live adversarial probes over every surface/cache variant and global fallback path. | Required before `t_authority`. | Closes the window in which a controlled surface or cache could serve predecessor-current after the head changes. |
| 10. Append the current-head transition | The staged notice resolves; the proved fence remains armed; admitted base head is still canonical. | GY-N12 appends exactly one current-head event; notice/feed phase becomes `authority_transitioned` by chronology, not in-place rewrite. | Indeterminate append permits no current positive; any correction to it is another event. | One head, event identity/sequence/time, base-head match, authenticated `as_of`. | Creates `t_authority`; never creates `t_effective`. | Because Steps 3 and 9 already hold, a crash immediately after this event yields no predecessor-current and no successor-current-without-notice observation. |
| 11. Probe controlled convergence | `t_authority` exists; admitted generations still match. | Invalidate or otherwise neutralize every `C` member; probe every `S/C/F` member; recheck `R_gate/A/L/K` and all synchronous receipts using exact bound tuples. | Unsafe member fails closed; effective gate stays red; append incident; never restore predecessor-current. | Member-bound live probes, exact receipt joins, generation comparison, remove/replay/falsify-declaration probes. | Required before `t_effective`. | Prevents a green aggregate from hiding stale, wrong-notice, wrong-generation, or replayed-receipt state. |
| 12. Append the effective declaration | `Complete(R_gate/S/C/F/A/L/K)` is true; notification intents are complete; every frozen synchronous member has a qualifying receipt; event order is valid. | Append one bounded declaration naming all snapshots, generations, counts, cutoffs, exclusions, and lagging asynchronous states; the event creates `R_post = R_gate union {declaration}`. | Early, backdated, duplicate, circular, or declaration-only positive is rejected; no `t_effective`. | Independent gate recomputation, append-order verifier, `R_post` one-member count delta, exact content binding. | Creates `t_effective`. | Prevents effect from being declared before its evidence exists or by excluding its own event from history. |
| 13. Continue delivery and monitoring | Intents exist; the correction is authority-transitioned or effective. | Move asynchronous members to delivered or visible owned retry/escalation states; retain incidents and renewed `as_of` reports. | Failure stays red and cannot rewrite snapshots, obligation class, authority event, or historical completion record. | Per-member state derived from the frozen cohort and correction-bound receipts. | May continue after `t_effective`; never repairs a missing synchronous receipt retroactively. | Prevents post-effect delivery changes from manufacturing an earlier effective pass. |

Steps 3 and 9 are deliberately before Step 10. Reversing either choice admits one of the two
forbidden observations identified by the independent audit.

## 8. Crash-cut proof for the repaired order

### 8.1 Crash after staged notice, before fence

The predecessor remains current because Step 10 has not executed. The staged notice is public and
explicitly non-current. No post-authority observer invariant is yet invoked.

### 8.2 Crash after fence proof, before authority transition

The predecessor remains current; the staged notice resolves; the fence is armed but has not changed
current authority. Recovery can resume or abandon without exposing a successor-current claim.

### 8.3 Crash immediately after `t_authority`, before any Step 11 probe

The notice already resolves because Step 3 passed. The fence already covers every admitted `S/C`
path because Step 9 passed. Therefore each controlled observation is already one of the three full
tuple states in Section 9. A predecessor-current response is prevented by the fence, and a
successor-current response without the correct notice is prevented by the notice-binding part of the
same fence. A path whose local state has not converged returns unavailable rather than inventing a
fourth state.

### 8.4 Crash during Step 11

Completed probes remain evidence; unprobed or failed members remain fail closed. No effective event
exists. The canonical successor remains current and the predecessor remains historical.

### 8.5 Crash during Step 12 append

An indeterminate append permits no public effective positive until the canonical chronology resolves
whether `e_effective` exists and the post-append `R_post` delta reconciles. It never restores the
predecessor as current.

## 9. Full public-observer invariant

For correction `c`, controlled surface `s in S`, and `t >= t_authority`, define the observed tuple:

`Obs(c,s,t) = (correction_id, selected_record_id, authority_role, predecessor_id, successor_id, notice_id, notice_phase, authenticated_as_of, projection_relation, authoritative_language_result, availability)`.

The three permitted labels are projections of the full tuple, not free-standing strings.

### 9.1 `successor_current_linked`

This label is true only when:

- `correction_id` equals the admitted correction;
- `selected_record_id` is the admitted successor;
- GY-N12 establishes successor current and predecessor non-current at `authenticated_as_of`;
- the selected notice is the admitted notice for the same correction and its phase is
  `authority_transitioned`, `effective`, or `dissemination_open`, never `staged`;
- predecessor, successor, and notice links resolve in both required directions;
- the projection relation is established under PV-K04; and
- the authoritative-language result required for this surface is established through INT-R6.

### 9.2 `predecessor_historical_linked`

This label is true only when:

- the selected record is the admitted predecessor;
- GY-N12 establishes it as non-current at the authenticated cutoff;
- its historical issuance result is reported separately through INT-R7;
- the admitted successor and notice resolve for the same correction;
- the notice is not staged after `t_authority`; and
- projection and authoritative-language relations are established for the representation shown.

### 9.3 `unavailable_fail_closed`

This label is true only when the surface returns no current-authority positive and exposes a bounded
failure/unavailability state. It is mandatory whenever either positive tuple cannot be established.

The invariant is:

`forall s in S, forall t >= t_authority: Label(Obs(c,s,t)) in {successor_current_linked, predecessor_historical_linked, unavailable_fail_closed}`.

A correct successor paired with the wrong notice, a staged notice after authority transition, a stale
currentness snapshot, an unfaithful projection, or a divergent authoritative language satisfies none
of the two positive labels and must become `unavailable_fail_closed`. The contract does not add a
fourth state.

## 10. Frozen notification obligation

Step 0 freezes, for every member in `N` and `P`:

- cohort snapshot and member identity;
- `receipt_obligation` equal to `intent_before_authority`, `qualifying_receipt_before_effect`, or
  `asynchronous_receipt_permitted`;
- predicate-provenance class;
- institutional source, independent reconciliation source, owner, cutoff, and evidence identity;
- the result for missing, conflicting, or merely declared evidence.

Only an independently reconciled `asynchronous_receipt_permitted` result can relax receipt beyond the
effective boundary. Missing, `consumer_asserted`, merely `institutionally_supplied`, conflicting, or
`not_established` obligation evidence is treated as `qualifying_receipt_before_effect`. The rule is
immutable inside the transaction.

An attempted move from synchronous to asynchronous after admission is appended as a rejected change.
If it occurs before `t_authority`, authority remains blocked. If it occurs after `t_authority`, the
member remains synchronous, `t_effective` remains absent, the obligation-integrity gate is red, and
an incident is appended. A later competent institutional decision may govern a newly admitted
transaction; it cannot retroactively create the earlier effective pass.

PAO-R36 does not decide whether any real person legally requires notice, hearing, protection, or
receipt. It defines how an admitted institutional decision is frozen, reconciled, and prevented from
being changed by the transaction it constrains.

## 11. Notice semantics under `PV-K04`

A public correction notice must retain at least:

1. correction, predecessor, successor, and notice identities with resolvable relations;
2. what changed and the reason class;
3. claim type, basis, scope, assumptions, material conditions, and limitations affected;
4. currentness, notice phase, effective state, authenticated `as_of`, and bounded fan-out status;
5. every denied use and authority boundary that remains applicable;
6. active dissent, contest, otherwise-required recourse, audit references, and negative/refusal
   terminals;
7. whether risk/exposure increased, decreased, was mixed, or remained unresolved, plus the safely
   described affected class;
8. whether the predecessor may remain legally or administratively significant for prior decisions,
   without deciding that effect automatically;
9. authoritative-language status and any parity limitation;
10. archive linkage, controlled denominators, source generations, and known external-copy
    limitations; and
11. INT-R7 distinctions: issuance authenticity, projection faithfulness, public-history status,
    durable verifiability, snapshot selection, current authority, and evidence obtainability, read
    through terminal Section 18.

The notice may compress unchanged detail only when omitted material remains source-resolvable, the
omission has a governed reason/effect disposition, and no protected query becomes less conservative.
Accessibility regimes require accessibility of the otherwise-required notice, status, links,
feedback, and any independently grounded recourse route; they do not create substantive recourse.

## 12. Machine correction-feed semantics

This section states propositions only and defines no schema, serialization, topic, media type,
package, or endpoint. A machine consumer must be able to determine:

- correction identity and responsible issuing role;
- predecessor, successor, and notice identities/direction;
- staged, authority-transitioned, effective, or dissemination-open phase;
- reason class, change scope, risk direction, and old-version significance;
- historical issuance and current authority separately;
- authenticated `as_of`, event sequence, and effective event time;
- protected limitations, denied uses, dissent, contest, and otherwise-required recourse;
- authoritative-language status;
- archive and uncontrolled-copy limitations;
- exact set snapshots, generations, denominators, and completion status; and
- notification completion separately from correction effectiveness.

A feed member cannot call the correction complete while omitting its own tuple or relying on another
correction's receipts.

## 13. The three hard cases

### 13.1 Correction increases exposure

Risk direction is independently reconciled before authority transition. Unknown or merely declared
neutrality blocks. An admitted `P` cohort and each receipt obligation are frozen at Step 0. The notice
names the affected class safely, preserves limitations and otherwise-required recourse, and does not
assert retroactive effect or legal sufficiency.

### 13.2 Superseded version remains significant

The predecessor, publication interval, reasons, signature evidence, and exact decisions that used it
remain retrievable. Current default retrieval selects the successor only after `t_authority`;
historical retrieval reproduces the predecessor and its correction relation. The correction does not
itself void, validate, reopen, grandfather, or remedy an earlier decision.

### 13.3 Original key later revoked

The operation preserves and separately reports the terminal INT-R7 dimensions. A later revocation
cannot erase an established issuance event; an historically authentic signature cannot mint current
authority. Compromise uncertainty remains non-positive for the affected dimension, and the
successor's authority depends on its own issuance/status evidence and GY-N12 head.

## 14. External-copy honesty

Completion is always bounded to the named controlled sets and source generations. Public language
may say, for example, "complete over `S@snapshot` and `C@snapshot` at the stated cutoff." It may not
say "all copies", "all caches", or "the internet" has been corrected. External copies may continue
to display the predecessor without notice; that is disclosed as an exclusion, not silently absorbed
into a denominator.

## 15. Dependency seams

- **OPS-R14:** preserves versions, relations, public head, and completion evidence across recovery.
  Its RP-10 verifier must never restore predecessor-current merely because the old signature
  verifies. PAO-R36 owns correction meaning, notice, fan-out, and observer semantics.
- **INT-R6:** supplies a language-invariant semantic identity, parity result, denominator, cutoff, and
  fail-closed outcome. PAO-R36 does not define translation workflow or equivalence mechanics.
- **INT-R7:** supplies the five separately reportable verification dimensions, latest-snapshot
  selection, evidence obtainability, succession, and key lifecycle through terminal controlling
  Section 18. PAO-R36 adds only correction-chain and fan-out obligations.
- **GY-N12:** remains the sole currentness/epoch/reissue chronology owner. PAO-R36 consumes its event;
  it does not create another head.

## 16. Present capability boundary and standing

The complete source census supplied by the architect at pin `109ba3f4`, path denominator
`policy-engine/src`, all source file types, case-sensitive fixed strings, binary files excluded,
finds zero files, zero matching lines, and zero occurrences for each of `correction_notice`,
`notify_subscribers`, and `correction_feed`. The correction-specific notice, notification chain, and
feed are therefore `absent/unallocated` at the pin. This settled zero does not change the owner-first
handoff or authorize implementation.

The amended semantic contract remains `accepted_narrow_scope`: it answers the research question and
continues to refuse a live capability claim. The independent audit's `NO_GO as submitted` is not
claimed closed by this document; closure depends on independent conformance verification of the
amended branch.
