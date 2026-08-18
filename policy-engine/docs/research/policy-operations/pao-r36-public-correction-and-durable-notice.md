---
title: PAO-R36 - Public Correction and Durable Notice for Our Own Published Records
research_id: PAO-R36
status: amended_research
result_standing: accepted_narrow_scope
audit_disposition_of_submitted_version: NO_GO
amendment_status: pending_independent_conformance
result_reason: >-
  The two-boundary append-only correction architecture survives. The amendment reconciles the
  controlling order, removes the circular effective gate, freezes per-member notification
  obligations, constructs every load-bearing gate predicate under P37, binds the observer to the
  full correction tuple, and adds deterministic falsifiers. The repository still cannot issue a
  public correction at the pin because correction-specific notice, notification, feed, controlled
  registry, archive fan-out, translation parity, and currentness dependencies are absent or
  undelivered.
repository: https://github.com/DenisKopylov/polisyos
repository_branch_inspected: main
pinned_repository_commit: 109ba3f4
audited_commit: 1bccc012b636d6a13930735a4f748d1f8cf7b9cf
audit_commit: 9bbfd37a218222ae06c1f669b95dba37c4732765
amendment_branch: research/pao-r36-amendment
inspection_date: 2026-08-08
wave: 4
research_only: true
dependencies:
  - INT-R6
  - GY-N12
  - INT-R7
  - OPS-R14
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

# PAO-R36 - Public correction and durable notice for our own published records

## 1. Result standing and amendment status

**Research result: `accepted_narrow_scope`. Submitted-version audit disposition: `NO_GO`. Amendment:
`pending_independent_conformance`.**

The audit's three blockers were internal incoherence, not a refutation of the architecture. This
amendment preserves the audit-confirmed strengths and changes only the defective order and gate
construction:

- the staged notice is publicly resolvable before current authority changes;
- the authority fence is proved before the current-head event;
- `R_gate` contains only records that can exist before the effective declaration;
- the effective event creates `R_post = R_gate union {declaration}` rather than being silently
  excluded;
- every member's notification receipt obligation is frozen at admission;
- every load-bearing predicate has one P37 provenance class frozen at admission;
- `S/C` completeness binds exact controlled generations;
- every member receipt binds the exact correction tuple; and
- deterministic attacks exercise the repaired properties.

This document does not claim that independent conformance has passed. It does not claim that the
repository can currently issue a public correction.

## 2. Answer to the commission's question

The complete correction fan-out for a record PolicyOS published and signed is a two-boundary,
append-only authority transaction over frozen, generated, independently verifiable controlled sets:

1. admit one correction identity and freeze every denominator, generation, predicate-provenance
   class, external exclusion, and per-member notification obligation;
2. independently reconcile issuer authority, risk direction, old-version significance, affected
   cohort rule, and terminal INT-R7 verification dimensions;
3. append a distinct non-current successor without mutating the predecessor;
4. publish and verify a staged/non-current notice bound to the same correction identity;
5. stage exact-version/`as_of`, feed, archive, language, and notification-intent behavior;
6. arm and prove a fail-closed authority fence over every admitted surface/cache path;
7. append the single GY-N12 current-head event at `t_authority`;
8. probe all controlled members against exact correction-bound receipts and unchanged generations;
9. require every frozen synchronous member to have a qualifying receipt; and
10. append one bounded effective declaration at `t_effective`, thereby adding the declaration to the
    historical transaction record.

A crash immediately after the authority event cannot expose predecessor-current or
successor-current-without-notice because the notice and fence already exist. Physical convergence may
remain asynchronous; semantic authority cannot.

## 3. Fixed law and ownership boundary

PAO-R36 consumes rather than reopens:

- `PV-K01`: current authority is separately reportable and cutoff-bound;
- `PV-K02`: historical authenticity and current authority are distinct and non-erasing;
- `PV-K04`: projections may reduce detail but cannot amplify truth, certainty, authority, currency,
  or permission;
- `S0-K06`, applied through `P37`: a gate cannot receive authority from an unconstructed declaration
  inside its own decisive predicate;
- `S0-K08`: correction appends; history is not rewritten;
- `INT-K05`: composition cannot create a second canonical owner; and
- GY-N12: one currentness/epoch/reissue chronology owns the head and authenticated `as_of`.

Final public-verification/current-authority semantics are read through terminal controlling INT-R7
Section 18 at
`policy-engine/docs/research/policy-operations/int-r7/public-verification-profile.md:620-760`.
Earlier key/revocation examples are historical detail interpreted through that terminal layer.

## 4. Settled orientation and census

Documentation anchors use `main@109ba3f4`. The architect established that `policy-engine/src` is
byte-identical there to the original pin. The complete source census was supplied from `git grep` at
the pinned ref; it is recorded rather than re-derived.

Common method: path denominator `policy-engine/src`; case-sensitive fixed string; binary excluded;
file-type denominator stated per row.

| Token | File-type denominator | Files | Matching lines | Occurrences |
| --- | --- | ---: | ---: | ---: |
| `supersede` | all source; all 48 are Python | **48** | **215** | **260** |
| `superseded` | all source | **34** | **154** | **183** |
| `retraction` | all source | **7** | **40** | **45** |
| `retraction` | Python only | **6** | **39** | **44** |
| `cache_invalidat` | all source | **3** | **5** | **6** |
| `subscriber` | all source | **3** | **18** | **21** |
| `correction_notice` | all source | **0** | **0** | **0** |
| `notify_subscribers` | all source | **0** | **0** | **0** |
| `correction_feed` | all source | **0** | **0** | **0** |

The audit's 47/203/246 `supersede` correction is declined. Its two uppercase-only subtractions were
correct, but the connector candidate set was one file short. This is the P35 index rider: an index is
not a denominator in either direction.

Structural orientation still reproduces: the INT-R7/R8 ratification record is 439 lines;
`rule_evolution.py` is 839 lines with 28 top-level functions and 2 top-level classes;
`public_export.py` is 2,103 lines; and `projection_semantics.py` is 3,763 lines with the four existing
audiences. The complete zeroes strengthen, rather than weaken, the `absent/unallocated` conclusion
for correction notice, notification, and feed.

## 5. Selected model and external-transfer limits

The selected design remains composite: append-only evolution, exact version/`as_of`, separate notice,
statistical-revision discipline, push plus pull, generation-bound controlled convergence, archive
relations, and an INT-R6 parity interface.

Statistical-agency practice transfers published revision policy, classification, vintages, schedules,
reasons, and revision analysis. It does not transfer signer authority, individual administrative
effect, affected-party receipt, or legal significance. Accessibility regimes require accessibility
of otherwise-required notice, status, links, feedback, and independently grounded recourse; they do
not create substantive recourse. Council Regulation No 1 supports governed language enumeration,
not language-invariant semantic identity. COPE is pinned to Retraction Guidelines Version 3, August
2025, DOI `10.24318/cope.2019.1.4`.

No external source establishes a PolicyOS duty, legal sufficiency, deadline, venue, retention period,
remedy, signer, or owner.

## 6. Amended formal contract

### 6.1 Event order and anti-backdating

Let `e_stage`, `e_authority`, and `e_effective` be append-only chronology events. The required
sequence is:

`seq(e_stage) < seq(e_authority) < seq(e_effective)`

with authenticated event times:

`time(e_stage) <= time(e_authority) <= time(e_effective)`.

Equal timestamps do not erase strict append order. Every decisive evidence cutoff is at or before the
effective event. A later append with an earlier displayed effective time, an effective event before
the final synchronous receipt, or reversed append order hidden by equal timestamps is rejected. F13
continues to test version/currentness selection; F20-A/B/C test event order and anti-backdating.

### 6.2 Frozen sets and phase-correct record membership

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

### 6.3 Completeness, generation, and receipt binding

For a frozen set `X`:

`Complete(X,t) := SnapshotFrozen(X) AND GenerationLive(X)=GenerationAdmitted(X) AND forall x in X: QualifyingBoundReceipt(x,t) AND no unresolved x`.

Every receipt content-binds the exact correction id, set/snapshot/generation, member, predicate,
predecessor, successor, notice, authenticated `as_of`, evidence cutoff, verifier identity/provenance,
and outcome. A receipt from another correction or snapshot is inadmissible even when member names
and counts match.

If live `S/C` generation changes before effect, the old denominator cannot pass. Before authority the
transaction is re-admitted; after authority the global fence covers the new path fail-closed and the
effective gate remains red until re-admission/re-probe. A controlled new member can never be relabelled
external to preserve green.

### 6.4 `P37` predicate provenance

The detailed contract §6 contains the single complete classification table. Every `Complete(X)`,
observer label, step precondition/effect gate, and falsifier detector is labelled exactly one of
`recomputed`, `independently_reconciled`, `consumer_asserted`, `institutionally_supplied`, or
`not_established`, with label/source/owner/cutoff frozen at admission.

A decisive `consumer_asserted`, `institutionally_supplied`, or `not_established` predicate cannot
produce a positive. Institutionally supplied material must be independently reconciled against a
non-producing competent record. Unknown notification obligation defaults synchronous. F17 falsifies
a declaration while keeping its markers intact and requires the live gate to turn red.

## 7. Why the order is repaired rather than the observer model widened

Two submitted-order crash windows were forbidden by the already-confirmed three-state observer model:

1. Authority before fence: a controlled path can serve predecessor-current after `t_authority`.
2. Authority before notice: a controlled path can serve successor-current with no notice, which is
   not successor-current-**linked**.

The amendment closes the windows by placing staged notice publication at Step 3 and fence proof at
Step 9, both before the Step 10 authority event. It does not add a fourth observer state.

## 8. Single controlling order

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

## 9. Crash-cut proof

### 9.1 Crash after staged notice, before fence

The predecessor remains current because Step 10 has not executed. The staged notice is public and
explicitly non-current. No post-authority observer invariant is yet invoked.

### 9.2 Crash after fence proof, before authority transition

The predecessor remains current; the staged notice resolves; the fence is armed but has not changed
current authority. Recovery can resume or abandon without exposing a successor-current claim.

### 9.3 Crash immediately after `t_authority`, before any Step 11 probe

The notice already resolves because Step 3 passed. The fence already covers every admitted `S/C`
path because Step 9 passed. Therefore each controlled observation is already one of the three full
tuple states in Section 10. A predecessor-current response is prevented by the fence, and a
successor-current response without the correct notice is prevented by the notice-binding part of the
same fence. A path whose local state has not converged returns unavailable rather than inventing a
fourth state.

### 9.4 Crash during Step 11

Completed probes remain evidence; unprobed or failed members remain fail closed. No effective event
exists. The canonical successor remains current and the predecessor remains historical.

### 9.5 Crash during Step 12 append

An indeterminate append permits no public effective positive until the canonical chronology resolves
whether `e_effective` exists and the post-append `R_post` delta reconciles. It never restores the
predecessor as current.

## 10. Full public-observer invariant

For correction `c`, controlled surface `s in S`, and `t >= t_authority`, define the observed tuple:

`Obs(c,s,t) = (correction_id, selected_record_id, authority_role, predecessor_id, successor_id, notice_id, notice_phase, authenticated_as_of, projection_relation, authoritative_language_result, availability)`.

The three permitted labels are projections of the full tuple, not free-standing strings.

### 10.1 `successor_current_linked`

This label is true only when:

- `correction_id` equals the admitted correction;
- `selected_record_id` is the admitted successor;
- GY-N12 establishes successor current and predecessor non-current at `authenticated_as_of`;
- the selected notice is the admitted notice for the same correction and its phase is
  `authority_transitioned`, `effective`, or `dissemination_open`, never `staged`;
- predecessor, successor, and notice links resolve in both required directions;
- the projection relation is established under PV-K04; and
- the authoritative-language result required for this surface is established through INT-R6.

### 10.2 `predecessor_historical_linked`

This label is true only when:

- the selected record is the admitted predecessor;
- GY-N12 establishes it as non-current at the authenticated cutoff;
- its historical issuance result is reported separately through INT-R7;
- the admitted successor and notice resolve for the same correction;
- the notice is not staged after `t_authority`; and
- projection and authoritative-language relations are established for the representation shown.

### 10.3 `unavailable_fail_closed`

This label is true only when the surface returns no current-authority positive and exposes a bounded
failure/unavailability state. It is mandatory whenever either positive tuple cannot be established.

The invariant is:

`forall s in S, forall t >= t_authority: Label(Obs(c,s,t)) in {successor_current_linked, predecessor_historical_linked, unavailable_fail_closed}`.

A correct successor paired with the wrong notice, a staged notice after authority transition, a stale
currentness snapshot, an unfaithful projection, or a divergent authoritative language satisfies none
of the two positive labels and must become `unavailable_fail_closed`. The contract does not add a
fourth state.

## 11. Frozen notification obligation

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

The conformance-critical deterministic worlds are F05-B (effect with an unverified synchronous
member) and F05-C (attempted sync-to-async mutation). Both have one exact detector and terminal
verdict.

## 12. External-copy honesty

Completion is bounded to named controlled snapshots and generations. Unknown external caches,
screenshots, downloads, mirrors, search indexes, and third-party republications remain explicit
exclusions. The notice may state “complete over `S@snapshot` and `C@snapshot` at the stated cutoff”;
it may not state that all copies, all caches, or the internet has been cleared.

F14 rejects amplified universal wording. A PolicyOS-controlled member discovered after snapshot is
not an external copy; generation integrity forces re-admission/re-probe.

## 13. Notice semantics under `PV-K04`

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

## 14. Machine correction-feed semantics

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

## 15. The three hard cases

### 15.1 Correction increases exposure

Risk direction is independently reconciled before authority. Per-member receipt obligations are
frozen at admission; unknown defaults synchronous. The notice names the safely described affected
class, change, reason, direction of exposure, limitations, uncertainty, and otherwise-required
recourse without declaring legal sufficiency or retroactivity. F10, F05-B, and F05-C make the
disposition decidable.

### 15.2 Superseded version remains significant

The predecessor, publication interval, proof closure, reasons, and exact prior decisions remain
retrievable. Current default selects the successor only from the real authority event onward;
historical queries reproduce the predecessor and its correction relation. The correction does not
itself void, validate, reopen, grandfather, or remedy past decisions. F13-A/B and F18 test temporal
and stale-base failures.

### 15.3 Original key later revoked

Terminal INT-R7 dimensions remain separate: issuance authenticity, projection faithfulness, public
history, durable verifiability, current authority, snapshot selection, and evidence obtainability. A
later revocation cannot erase established issuance; an old valid signature cannot mint current
authority. F09-A/B and F22-C test both laundering directions and supplied-old-snapshot misuse.

The full worked fixtures remain in `pao-r36/comparative-models-and-hard-cases.md`.

## 16. Falsifier coverage and amendment probes

The amended suite uses deterministic variants for every formerly conditional/phase-dependent case.
It preserves F09, F13, and F16 and adds:

- F17: falsify declaration, keep markers;
- F18: serialized stale-base C1/C2 correction;
- F19: cross-correction receipt-family replay;
- F20-A/B/C: early event, backdating, reversed equal-time sequence;
- F21: controlled generation drift; and
- F22-A/B/C: wrong notice, staged notice, and stale snapshot under the full observer tuple.

Each world names one detector, one frozen provenance class, one exact terminal verdict, and one
forbidden green outcome.

## 17. Dependency seams

- **GY-N12:** sole currentness/epoch/reissue owner; PAO consumes one admitted-base current-head event.
- **INT-R6:** supplies identity/parity result/denominator/cutoff; PAO defines no translation mechanism.
- **INT-R7:** final outcomes read through terminal Section 18; PAO selects no cryptographic or custody
  mechanism.
- **OPS-R14:** owns preservation/recovery/watched dependency/hold mechanics; PAO owns correction
  meaning, notice, observer, fan-out, and notification semantics. RP-10 and F11 meet at “recovery must
  never un-correct”.

The seams remain confirmed and are not re-adjudicated.

## 18. Present capability boundary

At `main@109ba3f4`, complete walk under `policy-engine/src`, all source file types, establishes
0 files / 0 matching lines / 0 occurrences for `correction_notice`, `notify_subscribers`, and
`correction_feed`. Correction-specific notice, notification, and feed are `absent/unallocated`.
GY-N12 is undelivered; INT-R6 is unresearched; no complete controlled registry/archive chain exists.

Existing public-export producer-to-HTTP consumer remains `bridge_missing` for that existing relation;
this does not create a correction consumer. End-to-end correction verification is
`absent/unallocated`, not `verification_missing`.

## 19. Amendment conclusion

The amendment executes R1-R14 and records every audit-finding disposition in
`pao-r36/amendment-ledger.md`. It preserves the two-boundary architecture and narrows no confirmed
strength. It also does not claim independent conformance, implementation, publication permission,
notification sufficiency, owner/vendor appointment, translation mechanics, or recovery/retention/
expiry rules.

The next valid step is independent conformance verification of the actual predicates and fixtures,
not marker presence.
