---
title: PAO-R36 - Ordered Correction Fan-out and Completeness Contract
research_id: PAO-R36
status: delivered_research
result_standing: accepted_narrow_scope
pinned_repository_commit: 1a7a2d05ebba22fae80e9934329e4b880806588e
research_only: true
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization, media-type, or API contract
  - canonical owner, vendor, or service appointment
  - authority grant
  - capability claim
  - legal-sufficiency or jurisdictional conclusion
  - permission to publish or open a gate
  - automatic amendment of any plan, backlog, or system-design decision
---

# Ordered correction fan-out and completeness contract

## 1. Answer first

A correction is not one write followed by best-effort propagation. It is an append-only authority
transition with a public observer. PolicyOS may call the correction **effective** only after every
member of a frozen, enumerated synchronous control set has entered a safe state and produced evidence
of that state. Actual subscriber receipt may lag only when the complete subscriber cohort has already
been durably admitted to delivery, every failure is visible, and an institutional adverse-impact
rule has not required receipt before effect.

The selected contract is a two-boundary transaction:

1. **authority transition**: the corrected successor becomes the current head through GY-N12 while
   the predecessor remains historically authentic and retrievable; and
2. **effective declaration**: made only after controlled public surfaces and caches have been probed
   against enumerated denominators and all other synchronous gates are complete.

Between those boundaries a controlled surface may show the corrected current version, the old
version only as historical with its supersession link, or a fail-closed unavailable state. It may
not show the old version as current.

## 2. Fixed semantic law

This contract consumes, without reopening:

- `PV-K01`: current authority is separately reportable and bound to an `as_of` cutoff;
- `PV-K02`: historical authenticity and current authority are distinct, non-erasing propositions;
- `PV-K04`: a notice or other projection may reduce detail but may not amplify truth, certainty,
  authority, currency, or permission;
- `S0-K08`: correction appends; history is not rewritten; and
- GY-N12: one append-only epoch/currentness owner supplies the current head and reissue chronology.

Pinned anchors are
`policy-engine/docs/system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md:92-151`,
`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:101`, and
`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2052-2138`.

## 3. Correction states and time boundaries

The contract uses four semantic states. These are not wire values.

| State | Meaning | Permitted public representation |
| --- | --- | --- |
| `staged` | Successor, notice, and fan-out evidence are being prepared. The predecessor remains current. | Predecessor may remain current. Successor may be inspectable only as pending/non-current. |
| `authority_transitioned` | GY-N12 has appended the successor as current and made predecessor current-authority false. Synchronous fan-out verification is still running. | Corrected current, predecessor historical-with-link, or unavailable. Never predecessor-current. |
| `effective` | Every synchronous enumerated gate has passed and a completion assertion is appended. | Same safe states, now with a bounded completeness claim naming its set snapshots. |
| `dissemination_open` | Post-effect delivery or monitoring remains active. | Effective stays true only within its bounded synchronous claim; subscriber delivery status remains separately reportable. |

Let:

- `t_stage` be the first staging event;
- `t_authority` be the append-only current-head transition; and
- `t_effective` be the later effective declaration after synchronous verification.

`t_stage <= t_authority <= t_effective`. No derived surface may invent an earlier effective time.

## 4. Enumerated completeness sets

No phrase of the form "all X" is valid unless X is a named snapshot with a member list and a
count. The minimum sets are:

| Set | Enumerated members | Completeness source |
| --- | --- | --- |
| `R` - record set | Every canonical predecessor, successor, notice, and correction-status record in this transaction | Transaction admission snapshot |
| `S` - controlled surface set | Every PolicyOS-controlled public rendering that can assert record authority: public page, public export projection, supported API representation, machine projection, and any other registered authority-bearing surface | Controlled-surface registry snapshot at admission cutoff |
| `C` - controlled cache set | Every controlled cache namespace, variant family, edge or node class, and key derivation that can serve a member of `S` | Cache-control inventory snapshot tied to `S` and the correction identity |
| `N` - subscriber cohort | Every registered subscriber eligible at the declared cohort cutoff, including subscription scope and delivery class | Subscriber registry snapshot |
| `P` - affected-party cohort | Every directly affected person or organization the authorized institutional classifier has required to receive direct notice | Separate institutional cohort decision; not inferred by software |
| `F` - correction-feed set | Every controlled feed projection or partition in which the correction must be observable | Machine-consumer registry snapshot |
| `A` - archive set | Every named archive, preservation repository, or controlled copy for which PolicyOS claims correction linkage | Archive/custody registry snapshot |
| `L` - authoritative language set | Every language variant admitted for this record under D4 and the future INT-R6 parity contract | Language-admission snapshot; D4 currently fixes `uk` primary and `en` baseline/fallback while `ru` UI is frozen legacy |
| `K` - key/status evidence set | The original signature, successor signature, applicable key-status events, trusted time evidence, and currentness evidence required by INT-R7 | INT-R7 verification evidence closure |

An unknown external cache, screenshot, download, mirror, search index, or third-party republication is
not silently added to a controlled set and is not claimed cleared. It is recorded as an exclusion
and a public limitation. Third-party misinformation monitoring remains outside PAO-R36.

## 5. Structural definition of completeness

For a named set `X`, a claim `Complete(X, t)` is true only if all of the following are true:

1. a frozen snapshot identity exists;
2. the snapshot declares its cutoff, owner, membership rule, exact member list or independently
   resolvable member commitment, and count;
3. every member has a required-state assertion and evidence at or before `t`;
4. no member is in an unresolved or contradictory state;
5. exclusions, unknowns, and externally uncontrolled copies are explicit; and
6. the completion assertion names the same snapshot identity and reproduces its denominator.

In compact form:

`Complete(X, t) := Snapshot(X) AND for every x in X, VerifiedRequiredState(x, t) AND no unresolved x.`

A receipt that says "100 percent" without preserving the denominator is invalid. A later discovery
that the snapshot omitted a controlled member invalidates the completion assertion for that set; it
does not rewrite the correction record.

## 6. Ordered semantic contract

### Step 0 - Admit the correction case and freeze the claim boundary

**Precondition.** PolicyOS can identify the record it published, its canonical predecessor identity,
its current authority state and `as_of` cutoff, and the role requesting correction.

**Effect.** Open one correction transaction; freeze initial snapshots for `R`, `S`, `C`, `N`, `F`,
`A`, `L`, and `K`; identify whether an authorized institutional decision requires `P`; record known
external exclusions. No correction capability is claimed merely because this admission record
exists.

**Partway failure.** Stop before changing current authority. The predecessor remains current. Any
prepared object stays explicitly non-current and cannot appear as an effective correction.

**Verifiable by.** Snapshot identities, membership counts, cutoff times, owners, and a check that
completion assertions cannot refer to an unresolvable or mutable denominator.

**Effective gate.** Required before `t_authority` and `t_effective`.

### Step 1 - Classify authority, risk direction, old-version significance, and key status

**Precondition.** Step 0 exists. The original record and its signature/status evidence are
resolvable.

**Effect.** Record four independent determinations:

1. whether the proposed issuer role is authorized to issue the correction;
2. whether the correction can increase exposure, burden, liability, denial, or other adverse risk;
3. whether decisions or legal relations may have depended on the predecessor; and
4. the INT-R7 disposition of each signature and key-status interval.

No software inference is a legal conclusion. The institutional owner must supply any affected-party
or retroactivity determination needed for the case.

**Partway failure.** Fail closed before authority transition. Unknown risk direction is not treated
as beneficial or neutral. Unknown key compromise overlap is not treated as a current positive.

**Verifiable by.** Presence of separate, non-collapsed determinations and negative fixtures proving
that historical authenticity is not inferred from current key authorization, or vice versa.

**Effective gate.** Required before `t_authority`.

### Step 2 - Append the canonical successor without mutating the predecessor

**Precondition.** Steps 0-1 pass; the current canonical record and exact content identity are
resolved.

**Effect.** Create a new canonical successor carrying an immutable predecessor relation, a declared
change basis, the applicable claim type/scope/limitations, and an initially non-current state. The
predecessor bytes and historical signature remain unchanged.

**Partway failure.** No current-head transition occurs. A partially persisted successor is either
recoverably staged or explicitly abandoned; it never replaces the predecessor in place.

**Verifiable by.** Content identity comparison, predecessor immutability check, graph check for one
resolved predecessor, and replay proving the old version remains reproducible.

**Effective gate.** Required before `t_authority`.

### Step 3 - Derive and verify the separate public correction notice

**Precondition.** The canonical successor and predecessor are both resolvable. Projection semantics
are available from `projection_semantics.py`.

**Effect.** Create a separately identifiable notice linked in both directions to predecessor and
successor. The notice retains every PV-K04-protected semantic item listed in Section 9 and states
whether the correction is staged, authority-transitioned, or effective. It does not impersonate the
canonical record.

**Partway failure.** Keep the successor non-current. A notice that omits a retained limitation,
denied use, adverse impact, contest path, or old-version significance is rejected, not published as
an abbreviated success.

**Verifiable by.** Protected-query comparison against predecessor and successor, resolvable links,
and adversarial omission tests.

**Effective gate.** Required before `t_authority`; the notice must become visible no later than the
current-head transition.

### Step 4 - Stage versioned and `as_of` retrieval semantics

**Precondition.** Steps 2-3 pass.

**Effect.** Every member of `S` that retrieves or renders the record can distinguish:

- exact predecessor and successor versions;
- historical authenticity from current authority;
- the `as_of` cutoff used for a currentness answer;
- supersession direction; and
- the notice and correction status.

The predecessor remains retrievable for historically bounded decisions. A default current view is
not permitted to select it after `t_authority`.

**Partway failure.** Do not transition authority. If a post-transition failure is discovered, the
affected controlled surface fails closed and the completion assertion turns red; no in-place
rollback to predecessor-current is allowed.

**Verifiable by.** Exact-version retrieval fixtures, past/current `as_of` fixtures, and a negative
probe proving a predecessor cannot render as current after `t_authority`.

**Effective gate.** Required before `t_authority` for staging and before `t_effective` for every
member of `S`.

### Step 5 - Stage the machine-readable correction feed semantics

**Precondition.** The correction identity, predecessor, successor, notice, and currentness semantics
are stable enough to expose without claiming effect prematurely.

**Effect.** Every member of `F` can determine the propositions in Section 10. A staged item is marked
non-effective; at `t_authority` the item can expose the current-head transition without asserting
synchronous completion until `t_effective`.

**Partway failure.** Do not claim feed completeness. Before authority transition, block the
transition. After authority transition, fail the affected feed member closed or expose an explicit
incomplete status; never omit the correction while continuing to call the feed complete.

**Verifiable by.** Per-member observation using the frozen `F` denominator and negative consumer
assertions for every prohibited inference.

**Effective gate.** Required before `t_authority` for admission and before `t_effective` for complete
observation across `F`.

### Step 6 - Establish bidirectional archive linkage

**Precondition.** The predecessor, successor, notice, signatures, and key-status evidence are
resolvable.

**Effect.** Every archive member in `A` preserves the old record and can traverse old -> correction
notice -> successor and successor -> notice -> predecessor. Preservation of the old signature is
separate from any current-authority conclusion.

**Partway failure.** Block authority transition while pre-effect. If discovered later, mark archive
completeness false, fail any affected authoritative archive projection closed, and append repair
evidence. Never delete or overwrite the predecessor to hide the break.

**Verifiable by.** Per-archive round-trip traversal, independent content identity checks, and proof
that predecessor preservation remains intact.

**Effective gate.** Required before `t_authority` for every claimed member of `A`.

### Step 7 - Establish translation parity for the authoritative language set

**Precondition.** `L` is frozen under D4 and the future INT-R6 interface. Each language variant is
linked to the same correction semantic identity.

**Effect.** Every member of `L` preserves claim type, scope, change, limitations, denied uses,
currentness, adverse-impact classification, old-version significance, and recourse. Language changes
may alter expression but not authority or permission.

**Partway failure.** Block authority transition. After transition, fail the divergent language
surface closed, turn the parity gate red, and append a parity incident. Do not silently treat one
language as an editorial summary of another.

**Verifiable by.** INT-R6 parity evidence against one language-invariant semantic identity. PAO-R36
does not define that mechanism.

**Effective gate.** Required before `t_authority`. A multilingual effective claim is impossible
without complete `L` evidence.

### Step 8 - Admit subscriber and affected-party notification obligations

**Precondition.** `N` is frozen and any institutionally required `P` decision exists. The notice is
semantically complete.

**Effect.** Every eligible member of `N` has a durably accepted notification intent tied to this
correction and cohort snapshot. Each member has a separately observable delivery state. For a
risk-increasing correction, the institutional classifier decides whether members of `P` require
actual receipt before effect; PAO-R36 does not declare that duty legally sufficient.

**Partway failure.** Before authority transition, a missing cohort member or unaccepted intent blocks.
After transition, a delivery failure becomes visible and actionable; it cannot disappear into a
green aggregate. Where the authorized `P` rule required pre-effect receipt, failure blocks
`t_effective` and triggers the declared institutional response.

**Verifiable by.** Denominator equality between `N`/`P` snapshots and notification intents, plus
per-member terminal or pending states and a proof that any failure changes the gate.

**Effective gate.** Complete cohort admission is required before `t_authority`. Actual delivery may
lag only for members not placed behind a pre-effect `P` receipt rule.

### Step 9 - Arm the controlled-surface authority fence

**Precondition.** Steps 0-8 pass. Every member of `S` and `C` is known, and fail-closed behavior has
been proved.

**Effect.** At and after `t_authority`, a controlled surface or cache may return only:

1. successor-current with notice and predecessor relation;
2. predecessor-historical with supersession relation; or
3. unavailable/fail-closed.

The fence is a semantic invariant, not a selected product or implementation mechanism.

**Partway failure.** Do not append the current-head transition. If a bypass is found after the
transition, immediately treat the affected controlled surface as unsafe, prevent an authority
positive, and append an incident. Do not restore predecessor-current.

**Verifiable by.** Adversarial probes against every `S` and `C` member, including stale and alternate
variant paths.

**Effective gate.** Required before `t_authority`.

### Step 10 - Append the single current-head transition

**Precondition.** All pre-authority gates pass, including `R`, `A`, `L`, `K`, admitted `F`, and
notification-cohort admission. The authority fence is armed.

**Effect.** GY-N12 appends one current-head event: successor current authority becomes true at the
specified cutoff; predecessor current authority becomes false without changing historical
authenticity. Notice and feed status change from staged to authority-transitioned.

**Partway failure.** There is no in-place rollback. If the append is indeterminate, no surface may
claim current authority until the owner resolves the event. If a correction to the transition is
needed, it is another append-only event.

**Verifiable by.** One current head, no forked successors, a resolved predecessor edge, authenticated
cutoff, and replay from the event history.

**Effective gate.** This creates `t_authority`; it does not alone create `t_effective`.

### Step 11 - Invalidate and verify every controlled cache and surface

**Precondition.** `t_authority` exists and the fence prevents stale-current authority.

**Effect.** Every member of `C` is invalidated or otherwise proved unable to serve predecessor-current;
every member of `S` is probed for a safe state. Corrected objects may be repopulated only under the
new currentness relation. Each result is bound to the frozen member and correction identity.

**Partway failure.** Keep the effective gate red. The correction remains appended and current at its
canonical owner, but controlled unsafe surfaces fail closed. A stale-current response is an incident,
not a tolerable propagation delay.

**Verifiable by.** Per-member probes over the exact `C` and `S` denominators, including variants,
negative-cache paths, and alternate current views.

**Effective gate.** Required before `t_effective`.

### Step 12 - Declare the correction effective

**Precondition.** `Complete(R)`, `Complete(S)`, `Complete(C)`, `Complete(F)`, `Complete(A)`,
`Complete(L)`, and `Complete(K)` are true; `N` and any `P` pre-effect obligations satisfy Step 8.

**Effect.** Append a bounded effective declaration naming every snapshot identity, count, completion
time, exclusion, and lagging notification state. Public surfaces may now say effective, but only
with respect to those enumerated sets and cutoff.

**Partway failure.** No effective declaration is issued. A partially prepared declaration is
non-authoritative. A later-discovered omitted controlled member invalidates the applicable
completeness assertion and requires an appended incident/correction; it does not erase the canonical
successor.

**Verifiable by.** Independent recomputation of each set denominator and evidence join, plus a
remove-one-member fixture that must fail the declaration.

**Effective gate.** This is `t_effective`.

### Step 13 - Complete asynchronous delivery and monitor durable notice

**Precondition.** Notification intents were accepted under Step 8.

**Effect.** Each `N` member moves to a terminal delivery state or a visible, owned retry/escalation
state. The public/machine correction feed continues to expose the correction and completion status.

**Partway failure.** A failed delivery remains red and owned. The system may not report "all
subscribers notified" unless every member of the frozen cohort has a qualifying delivery receipt.
The correction may remain effective if the predeclared policy allowed delivery to lag, but the
notification dimension remains incomplete.

**Verifiable by.** Per-member state, cohort denominator, retry/escalation evidence, and an aggregate
computed from members rather than self-attested.

**Effective gate.** May lag after `t_effective`, except where the authorized `P` rule requires receipt
before effect.

## 7. Synchronous and lagging obligations

### Must be complete before authority transition

- transaction and controlled-set snapshots;
- authority/risk/old-version/key classification;
- immutable canonical successor;
- complete public notice;
- staged version/`as_of` retrieval;
- admitted correction-feed observation;
- archive linkage;
- authoritative-language parity;
- complete subscriber/affected-party cohort admission; and
- proved authority fence.

### Must be complete before the correction may be called effective

- the current-head append;
- every controlled cache result in `C`;
- every controlled authority-bearing surface result in `S`;
- complete observation across `F`;
- still-valid archive, language, record, and key/status gates; and
- any institutionally required pre-effect affected-party receipt.

### May lag after effective

- actual delivery to ordinary registered subscribers, but only where every cohort member already has
  a durable notification intent and every failure turns a gate red;
- external uncontrolled caches, screenshots, downloads, mirrors, or third-party republications, which
  are explicitly excluded from the completeness claim; and
- long-term resilience/replay/drill evidence owned by OPS-R14, provided recovery can never un-correct
  the record.

## 8. Public-observer consistency model

For every controlled surface `s` in the frozen `S` snapshot and every time `t >= t_authority`, the
following safety invariant holds:

`state(s,t) is one of {successor_current_linked, predecessor_historical_linked, unavailable}`.

The following states are forbidden:

- predecessor current after `t_authority`;
- successor current without a resolvable predecessor and correction notice;
- notice saying effective before `t_effective`;
- a current response with no authenticated `as_of` cutoff;
- one authoritative language widening scope or shrinking a denied use;
- an archive copy that preserves bytes but loses the supersession relation; and
- a green completion claim over an unenumerated set.

A public observer can therefore see mixed but safe states during the authority-to-effective interval:
one surface may already show the successor, another may show the predecessor as historical, and a
third may be unavailable. The observer must never see a controlled surface claim that the predecessor
is still current. This is the key distinction between bounded convergence and dangerous eventual
consistency.

Unknown external copies can continue to show the old version without a notice. The public correction
must disclose that PolicyOS does not control or enumerate them. No completion assertion may imply
that the internet has been cleared.

## 9. Notice semantics under PV-K04

A public correction notice must retain at least:

1. identities of predecessor, successor, and notice, with resolvable relations;
2. what changed and the reason class for the change;
3. claim type, basis, scope, assumptions, material conditions, and limitations affected by the
   correction;
4. currentness state, effective state, authenticated `as_of` cutoff, and whether fan-out is complete;
5. every denied use and authority boundary that remains applicable;
6. active dissent, contest, recourse, audit references, and negative/refusal terminals;
7. whether risk or exposure increased, decreased, was mixed, or remained unresolved, plus the named
   affected class without exposing protected personal information;
8. whether the predecessor may remain legally or administratively significant for prior decisions,
   without deciding that effect automatically;
9. authoritative-language status and any parity limitation;
10. archive linkage and known external-copy limitations; and
11. INT-R7 key/status distinctions where relevant: historical issuance authenticity, current signing
    authorization, revocation timing, and any indeterminate interval.

The notice may compress:

- unchanged narrative detail;
- unchanged supporting evidence lists;
- proof internals that remain resolvable through a governed reference; and
- repeated context that does not affect a protected query.

Compression is permitted only where the omitted material remains source-resolvable, the omission has
a governed reason/effect disposition, and no protected query becomes less conservative. Omitting a
limitation, denied use, adverse effect, old-version significance, dissent, recourse, key-status
qualification, or currentness cutoff converts the notice from a correction into a misleading rewrite.

## 10. Machine-readable correction feed semantics

This section specifies propositions only. It defines no schema, serialization, media type, package,
or endpoint.

A machine consumer must be able to determine:

- the correction identity and responsible issuing role;
- predecessor, successor, and notice identities and direction;
- whether the item is staged, authority-transitioned, effective, or dissemination-open;
- the correction reason class and change scope;
- risk direction, including risk increase or unresolved direction;
- historical-authenticity and current-authority dispositions separately;
- the applicable `as_of` cutoff and effective time;
- whether an old version remains relevant to prior decisions;
- retained limitations, denied uses, dissent, contest, and recourse;
- key/status events needed to interpret a signature across revocation or rotation;
- the snapshot identities and denominators for every claimed complete fan-out set;
- archive and authoritative-language parity status; and
- notification cohort status without exposing protected subscriber identities.

A machine consumer must never be able to conclude solely from the feed that:

- the predecessor was deleted, forged, or never authentic;
- key revocation proves the old signature was fraudulent;
- the successor retroactively invalidates every decision made under the predecessor;
- legal notice duties are satisfied in a jurisdiction;
- every affected person actually received notice unless the complete named cohort proves it;
- every internet cache or third-party copy has been corrected;
- historical authenticity establishes current authority;
- one language may narrow limitations or denied uses; or
- a correction is effective when any enumerated synchronous set is incomplete.

## 11. Recovery interface to OPS-R14

PAO-R36 sets one interface obligation and no recovery mechanism:

> A recovery, replay, restoration, failover, legal-hold, or disaster operation must never be able to
> un-correct a record, restore the predecessor as current, lose the correction notice or archive
> relation, or suppress a later current-head event.

OPS-R14 owns recovery objectives, replay mechanics, expiring rights, legal hold, disaster behavior,
and drill evidence. PAO-R36 does not set recovery times, expiry periods, or renewal rules. PAO-R36
requires only that restored state preserve the append order and re-run or preserve evidence for the
same `R`, `S`, `C`, `F`, `A`, `L`, and key/currentness relations before an authority positive is
served.

## 12. `may_not_use_for`

This contract may not be used for production implementation authorization; a final wire, schema,
package, database, serialization, media-type, or API contract; canonical owner, vendor, or service
appointment; an authority grant; a capability claim; legal sufficiency or a jurisdictional
conclusion; permission to publish or open a gate; or automatic amendment of any plan, backlog, or
system-design decision.
