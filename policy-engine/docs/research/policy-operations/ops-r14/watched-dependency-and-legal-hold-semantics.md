---
id: OPS-R14-WATCHED-DEPENDENCY-HOLD
artifact_kind: research_semantic_contract
status: research_only
standing: NO_GO
repository_pin: 1a7a2d05ebba22fae80e9934329e4b880806588e
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization, or API contract
  - canonical owner, vendor, custodian, archive, or service appointment
  - escrow agent appointment
  - authority grant
  - delegation grant
  - capability claim
  - legal-sufficiency or jurisdictional conclusion
  - permission to publish or open a gate
  - permission to sign
  - automatic amendment of any plan, backlog, or system-design decision
  - automatic amendment of the status lattice
  - proof that any retention period is legally sufficient
  - absorption of OPS-R12 institutional-scale continuity scope
  - design of PAO-R36 correction, notice, subscriber fan-out, or correction-feed semantics
---

# Watched dependency and legal-hold semantics

## 1. Decision

Represent every expiring right that enables a protected PolicyOS use as a first-class, governed,
append-only watched dependency. Scheduled jobs and alerts may deliver reminders or wake candidates;
they are not the authority record. Renewal is established only by admissible renewal evidence from
the relevant authority source. A missed job, delayed queue, absent alert, or operator silence never
extends the right.

Represent legal hold as an orthogonal override over disposal operations, not as a mutation of the
underlying retention class. A hold suspends destructive disposition. It does not make an expired,
revoked, superseded, restricted, or historically inauthentic record valid or current.

This artifact is intentionally prose-only. It defines no wire format, schema, enum, database table,
package, serialization, or API.

## 2. `WatchedDependencyRecord` semantic contract

A `WatchedDependencyRecord` is an owner-neutral semantic contract for one relied-on right or
permission. It exists because PolicyOS used, plans to use, or publicly represents reliance on that
right. It is not merely a date field and not merely a calendar reminder.

### WD-01 - stable subject and right identity

The record must identify the governed subject whose use depends on the right and the particular
right being asserted. The subject may be a case, record family, dataset use, model use, signing
operation, review action, publication, or jurisdiction pack. The right identity must distinguish two
rights even when they share an expiry date or vendor.

**Checkability:** a dependency-coverage verifier consumes the protected action, its registered
authority-dependency edges, and the record set. It returns exactly one applicable right identity,
multiple conflicting candidates, or a missing dependency. A name match alone is insufficient.

### WD-02 - provenance and authority source

The record must point to the instrument, decision, credential issuer, contract, delegation,
certification, consent act, appropriation, or internal governance act that creates or evidences the
right. It must preserve the admitted source version and acquisition evidence used at the time.

**Checkability:** the verifier consumes the retained source bytes, source identity, version/effective
time, admission receipt, and the claimed right. It reports whether the source actually supports the
claimed scope. It must not infer legal scope from a filename, certificate subject, or vendor API
response.

### WD-03 - effective interval and explicit query time

The record must state when the right begins, when it expires or otherwise ceases under the admitted
evidence, and which temporal role each instant has. Revocation, withdrawal, termination, and
supersession are separate events, not aliases for scheduled expiry. The query always supplies the
time at which authority is being evaluated.

**Checkability:** the verifier applies the Custody Time Model and GY-N12 currentness interface. A late
scheduler event cannot move the expiry time. Processing time cannot become legal-effective time.
GY-N12 remains the sole currentness owner
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2053-2120`).

### WD-04 - renewal owner role and succession path

The record must name an accountable **role**, not a person or vendor, responsible for seeking and
admitting renewal evidence. It must also state the role to which non-response or vacancy escalates and
the evidence required to establish that a successor role may act. Naming a role does not appoint its
holder and this research does not appoint one.

**Checkability:** before the lead-time threshold, the verifier checks that an active role binding and
escalation route are evidenced. A person leaving office must not orphan the watch. A successor is not
accepted solely because it controls the same account or storage system.

### WD-05 - lead time and review cadence

The record must define the earliest point at which renewal work begins and any intermediate evidence
checks required before expiry. Lead time must be based on the renewal process's actual dependencies:
counterparty signature, procurement lead, budget cycle, competence review, security validation,
source review, or public-law process. It is not a fixed platform-wide constant.

**Checkability:** a watcher consumes the expiry time, declared lead policy, current time, and last
completed renewal step. It emits due and overdue evidence events. The watcher can prove that a notice
was emitted; it cannot prove that authority was renewed.

### WD-06 - renewal evidence

The record must state what evidence is sufficient to establish renewal and which authority is
competent to produce or authenticate it. A payment receipt, successful API call, calendar change, or
operator assertion is insufficient unless the governing instrument makes it sufficient.

Renewal evidence is appended. It never edits the original right interval. A renewed interval must be
linked to the prior interval and independently evaluated.

**Checkability:** the renewal verifier consumes the evidence, admitted authority source, scope,
effective time, signatures/approvals where applicable, and prior interval. It reports whether the new
interval is established, narrower, conflicting, future-only, or not established. These findings feed
the existing status machinery; they do not create a second status lattice.

### WD-07 - grace policy

The record must state whether a grace period is affirmatively supported, what uses remain allowed,
its start and end, and the authority source for it. No grace exists by default. A technical retry
window, certificate overlap, procurement expectation, or historical practice cannot create a legal
or institutional grace period.

**Checkability:** the verifier rejects any use during a claimed grace interval unless the retained
source supports that exact scope. It distinguishes a credential-overlap mechanism from continued
substantive authority.

### WD-08 - failure consequence

The record must state the protected actions that become prohibited, suspended, degraded, or subject
to human review when the right is non-positive. It must state whether historical replay remains
permitted and whether evidence can still be retained. The consequence is projected into the one
existing project status lattice and authority band; this contract does not mint a new one.

**Checkability:** a policy-specific verifier consumes the right finding and the requested action. It
returns allow only where the existing authority gates support it. A wake is only a candidate under
S0-K10, never authority to resume
(`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:94-110`).

### WD-09 - reproducible affected-case query

The record must define a query that enumerates every governed, published, incident, appeal, or
release record whose protected use relied on the right. The query must bind a historical cutoff,
dependency-graph version, rule/reducer version, and scope. It must return identifiers and the exact
edge by which each item was affected.

**Checkability:** the affected-set verifier runs the stored query against the recovered dependency
history, compares it with registered authority edges and an independently generated fixture oracle,
and reports omissions, extras, and non-reproducible results. A list hand-maintained in an alert is not
an affected-case query.

### WD-10 - public effect

The record must state whether loss or renewal of the right can change any public record's current
posture, availability, or verification dimensions. OPS-R14 supplies PAO-R36 with the affected public
record set, effective time, source evidence, and durability/fan-out-completion requirement. PAO-R36
owns the meaning and operation of correction, notice, supersession, cache invalidation, subscriber
fan-out, machine-readable correction feeds, and translation parity
(`policy-engine/docs/research/policy-operations-and-real-world-runtime-backlog.md:512-532`).

**Checkability:** OPS-R14 verifies that PAO-R36's declared completion evidence is durably retained and
reconciles after recovery. It does not define that evidence's wire shape or the correction protocol.

### WD-11 - append-only event history

Every creation, evidence admission, warning, attempted renewal, successful renewal, narrowing,
revocation, expiry, grace decision, affected-set calculation, escalation, and correction of the
record must append a new event. Earlier evidence remains available for historical queries. A present
failure never rewrites whether an earlier issuer act occurred, applying S0-K08 and PV-K02
(`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:94-101`;
`policy-engine/docs/system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md:106-123`).

**Checkability:** replay from the event prefix must reproduce the same interval history and affected
sets. An edit-in-place or missing predecessor relation fails.

### WD-12 - absence and delayed delivery fail closed

The system must evaluate expiry from retained authority time, not only from received timer events. If
the watcher, scheduler, queue, or notification channel is unavailable, the right still expires at
its evidenced time. The next protected use performs an authority-time check and refuses to treat a
missing alert as continued authority.

**Checkability:** a fixture disables the scheduler across expiry and then requests the protected use.
Expected result: the use is non-positive, the late expiry event is admitted with its original
effective time, and historical authenticity is unchanged.

## 3. Structural families of expiring rights

The eleven commissioned classes are not eleven parameter variants. They fall into six structurally
different families, each with a different renewal proposition.

### 3.1 External or bilateral instruments

A data-sharing agreement, model licence, audit right, and contract depend on an external or bilateral
instrument. Renewal may require another party's signature, an option exercise, consideration,
procurement action, or evidence that a survival clause continues after service termination. Local
intent cannot complete the renewal.

Escrow or dual custody can preserve the instrument, evidence, source code, model materials, or exit
package where the instrument permits it. Escrow cannot extend the right, exercise a government power,
or manufacture a counterparty signature.

### 3.2 Technical credentials

An API credential and an encryption certificate are technical means. Their expiry can interrupt
access or cryptographic operation even when the underlying legal authority continues. Conversely, a
fresh credential does not renew the legal authority to use the data or service. The watched record
must preserve both propositions and their link without collapsing them.

Dual custody is appropriate for recovery material where security policy permits, but recovery must
not reactivate a compromised signing key or treat secret possession as authority.

### 3.3 Personal or role competence

A delegation and reviewer certification depend on a competent holder, scope, time, and sometimes
supervision or continuing conditions. Retirement, reassignment, loss of certification, or expiry can
occur while cases are in flight. A successor can act only where succession/delegation evidence
supports it. There is no post hoc renewal that validates an action taken after authority lapsed.

### 3.4 Subject authorization

Consent is structurally different because the subject may withdraw it and because it may be scoped by
purpose, data, recipient, or time. It is not renewed by an institutional owner on the subject's
behalf. A watch can surface the need for fresh consent or stop a use; it cannot presume continuity,
use silence as renewal, or place consent itself in escrow.

### 3.5 Fiscal or statutory authority

Budget authority can end with a fiscal period, appropriation, spending control, or statutory limit.
Operational urgency and sunk work do not create grace. The expiry consequence may distinguish
retaining records, completing an already valid obligation, and incurring a new obligation, but that
distinction requires competent institutional evidence outside this research.

### 3.6 Internal governance currentness

A jurisdiction-pack review is an internal assurance/currentness dependency. It does not create the
external law or public authority represented by the pack. Its expiry can block current-use claims and
trigger re-review while leaving historical replay available. GY-N12 owns the currentness/epoch
projection; OPS-R14 only supplies the watched evidence and recovery mechanics.

## 4. Eleven right classes

### 4.1 Data-sharing agreement (DSA)

The watched proposition is that a named agreement authorizes a defined exchange or use, between
identified parties, for a stated purpose and interval. The renewal role begins work early enough for
counterparty review and signature. Sufficient evidence is the executed amendment, extension, or new
agreement plus effective-time and scope evidence. A successful transfer or unchanged API key is not
renewal. At expiry, new acquisition and any newly prohibited use fail closed; historical records and
lawfully retained evidence remain preserved. The affected query returns every case, derived artifact,
publication, and pending acquisition that relied on the agreement. Public effect is routed to PAO-R36
when a published record's current data-use authority changes.

### 4.2 API credential

The watched proposition is that a credential remains technically accepted for a named endpoint and
scope. Renewal evidence is issuer-side issuance/rotation and successful authenticated verification,
not merely local secret creation. The record must link to, but not substitute for, the DSA, contract,
or mandate that authorizes the use. Credential expiry blocks connection and acquisition; it does not
retroactively erase previously admitted source evidence. Overlap during rotation is allowed only as a
technical mechanism and must not be described as legal grace.

### 4.3 Model licence

The watched proposition includes model identity/version, permitted uses, deployment or redistribution
scope, audit/records duties, term, termination, and any survival clauses. Renewal evidence is the
competent licensor's instrument or another legally effective basis, not package availability.
Expiration can block new inference, retraining, distribution, or public representation while
preserving historical input/output records where retention remains authorized. The affected query
must find cases and publications using the exact licensed version and derivative scope. Escrow may
support exit or verification only where authorized; it does not extend licence rights.

### 4.4 Audit right

The watched proposition is the ability to inspect, obtain evidence from, or test a supplier,
processor, archive, or service under a contract, statute, or agreement. Renewal may depend on a
contract extension or a separately surviving clause. Expiry can remove future access even while the
need to investigate continues. The failure consequence is to mark audit-dependent assurance as
non-positive or not established, not to assert that the audited facts are false. The affected query
finds every current claim whose evidence depends on an audit that can no longer be performed or
repeated.

### 4.5 Delegation

The watched proposition is that a competent delegator conferred a defined power on a role or holder,
within scope, time, and conditions. Renewal evidence must come from the competent authority and must
be effective before the action it authorizes. Retirement or vacancy does not transfer power by
account control. Expiry blocks new authority-bearing action and triggers reassignment or fresh
authorization for in-flight work. Historical actions are evaluated at their action time; later expiry
does not erase a valid earlier act, and later renewal does not validate an unauthorized gap.

### 4.6 Reviewer certification

The watched proposition is that a reviewer satisfies a defined competence or certification regime
for the review being performed. Renewal evidence is the competent certifier's current evidence and
scope, including any continuing conditions. Expiry mid-case stops reliance on unfinished review work
until a competent process determines reuse, reassignment, or repetition. A completed historical
review remains attributed to the original reviewer and evaluated at its review time. A grace period
cannot be invented to avoid workload.

### 4.7 Encryption certificate

The watched proposition is the technical validity and intended use of a certificate or other public
credential. The record distinguishes expiry from revocation and key-compromise time. Rotation and
algorithm renewal append evidence; they do not replace original signed bytes or signing-time status.
Certificate expiry may block new encryption or authentication but does not by itself invalidate a
historical signature. Recovery never restores an old private signing key into service merely because
it is present in a backup.

### 4.8 Consent

The watched proposition is a subject's authorization for a defined purpose, scope, recipient, and
interval, including withdrawal. The renewal role may request fresh consent but cannot issue it.
Silence, continued system use, or a recurring payment is not renewal unless the governing regime
specifically establishes that effect. Withdrawal or expiry blocks affected future processing and
triggers a scoped review of retained records, holds, and legal bases. A legal hold may preserve
records but does not authorize continued operational use or publication.

### 4.9 Budget authority

The watched proposition is that a competent fiscal source permits the relevant obligation or
expenditure during the stated period and scope. Lead time follows the actual budget and approval
cycle. Renewal evidence is the appropriation, allotment, approval, or other competent fiscal act. A
purchase-order draft, expected continuation, or system balance is not sufficient. Expiry blocks new
fiscal commitments that require the authority; it does not command deletion of records or erase
historical spending evidence.

### 4.10 Contract

The watched proposition covers term, options, notice periods, termination, service continuity,
records custody, audit, security, exit, and survival clauses. Renewal evidence must show a valid
option exercise, extension, or replacement and its effective time. A supplier's continued service
cannot silently renew government authority. The affected query identifies cases, stored evidence,
keys, interfaces, audit rights, and public records dependent on the contract. Exit and escrow
materials can preserve continuity where the contract authorizes them; they cannot preserve powers
that terminate with the contract.

### 4.11 Jurisdiction-pack review

The watched proposition is that the pack's review/currentness evidence remains within the accepted
review interval for current use. Renewal evidence is a completed, competent review of the relevant
sources, identifiers, authority hierarchy, temporal rules, licences, and known gaps. Expiry blocks a
positive current-use claim and wakes a review candidate. It does not silently switch to a default
jurisdiction, rewrite historical cases, or create a new currentness owner beside GY-N12.

## 5. Watched record versus jobs and alerting

The selected model is a governed record plus delivery mechanisms:

- the record carries the authority proposition and append-only evidence;
- a timer or scheduler calculates when work is due;
- a queue delivers due events;
- alerts help accountable roles act;
- every protected use independently rechecks the authority proposition;
- a census reconciles due records against delivered wakes;
- duplicate wakes are safe because wake is only a candidate;
- a delayed or missing wake never extends authority.

A scheduled job alone is rejected because it does not preserve the source, owner role, renewal
proof, failure consequence, affected set, or public effect. Alerting alone is rejected because an
acknowledged notification is not renewal evidence and an unacknowledged notification cannot define
whether authority exists.

## 6. Escrow and dual custody

Use escrow or dual custody selectively where the disappearing holder controls something
**transferable**: retained source bytes, contract records, public verification evidence, recovery
keys under an approved key-management policy, software needed for replay, or an exit package.

Reject universal escrow. The eliminating property is non-transferable authority. A delegation,
certification, consent, budget authority, counterparty signature, or statutory competence cannot be
kept alive by depositing a copy. Escrow also fails if the same organization controls both copies,
the release condition is untestable, or opening escrow would violate the underlying right.

A custody drill must therefore test not only that escrow bytes can be read, but that the release
condition, provenance, scope, and resulting authority proposition are independently established.

## 7. Legal hold as an override layer

### LH-01 - effect

An effective hold suspends every destructive operation within its scope: scheduled deletion,
garbage collection, destructive compaction, overwrite, destructive format migration, crypto-erasure,
and destruction of the only decryption or verification material. It also requires notice or a
corresponding freeze where a third-party or records center holds in-scope material.

### LH-02 - what a hold cannot suspend

A hold cannot suspend or alter:

- the expiry, revocation, withdrawal, termination, or compromise time of an authority or credential;
- the duty to stop an unauthorized use;
- correction or append-only supersession of an erroneous record;
- quarantine of suspected corrupt or malicious evidence;
- access restrictions, confidentiality, privilege, classification, or data-minimization controls;
- the distinction between historical authenticity and current authority;
- a legal or institutional duty that independently requires another action.

Retention under hold is not permission to process, publish, rely on, or disclose the held record.

### LH-03 - scope and multiplicity

A hold must identify its evidence basis, effective time, record or query scope, and review/release
roles. Multiple holds combine as a union of preservation obligations. One hold's release cannot free
an object still covered by another. Scope is evaluated over content, control events, derived indexes,
public proof closure, relevant keys, source captures, and disposal logs; holding only one store while
another destroys required evidence fails.

**Checkability:** a hold-coverage verifier expands each hold's reproducible query at the historical
cutoff, compares the result with control-to-content and derivation edges, and reports uncovered
objects or stores.

### LH-04 - interaction with retention deletion

While any effective hold covers an object, a retention deadline may pass but disposal remains
blocked. The original retention schedule and the fact that its deadline passed remain recorded. When
the last hold is validly released, the system performs a new, separately authorized disposal
evaluation. It does not backdate deletion and does not treat release as an immediate delete command.

**Checkability:** a race fixture releases the last hold while a deletion worker is running. Expected
result: the worker cannot delete until it observes the release event and a later disposal decision
whose scope and preconditions are re-evaluated.

### LH-05 - correction and supersession

S0-K08 requires correction to append rather than rewrite history
(`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:94-101`). A hold
therefore preserves the original version and the correction/supersession lineage. It does not block a
new correction and does not force the old version to remain the public current head.

PAO-R36 owns the correction meaning, public notice, supersession operation, caches, subscribers,
feeds, and translation parity. OPS-R14 requires an interface exposing the immutable relation,
applicable public head, affected surfaces, and completion evidence so recovery can verify that a
held superseded version is retained but not rendered as current.

### LH-06 - public effect

A hold's existence is not automatically public and does not alter a signature's historical
validity. If a lawful restriction, release, correction, or availability change requires public
notice, PAO-R36 supplies the semantics. OPS-R14 preserves the evidence and verifies recovery of the
result. This research makes no disclosure or privilege determination.

### LH-07 - release authority and evidence

Hold release requires evidence from a competent role under the applicable process. The record must
show which hold was released, when, over what scope, and whether other holds remain. An administrator
changing a tag is not sufficient release evidence.

**Checkability:** the release verifier consumes the hold history and release evidence and returns
whether the preservation barrier remains. Any ambiguity keeps destructive disposal blocked while
leaving correction, quarantine, and access restrictions operational.

## 8. Current repository baseline

The repository implements one narrow fragment: snapshot retention classification and GC protection
for legal-hold tags (`policy-engine/src/polisyos/fabric/security/retention.py:32-38,100-112`;
`policy-engine/src/polisyos/fabric/world/store/snapshots.py:661-689`). That fragment is `implemented`
within its scope.

No inspected source establishes the full watched-dependency contract or the general hold lifecycle.
The Python `renewal` occurrence is worker-lease renewal
(`policy-engine/src/polisyos/runtime/http/services/control_worker.py:84-85,128-174`). The broader
watched-dependency and hold semantics are `absent/unallocated`, not a claimed live capability.
