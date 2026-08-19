---
id: OPS-R14-DISASTER-DRILLS
artifact_kind: research_fixture_protocol
status: research_only
research_standing: accepted_narrow_scope
capability_standing: NO_GO
gate_standing: NO_GO
repository_pin: 109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee
audited_head: 3a694212aa47c4c2d8a631f8edc4ba8f7e15dce7
audit_head: 34c65a04ef178b9a59f70b9fb2012edee17a67cd
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

# Disaster fixtures and drill evidence

## 1. Fixture execution contract

Each fixture is an executable semantic specification even though this research supplies no test code.
A later test must instantiate the stated corpus and failure injection, run the real intended paths,
and compare every expected predicate. Marker strings, declarations, field presence, or a hand-authored
green receipt do not pass.

Every execution freezes:

- repository and implementation commit;
- fixture corpus digest and generator/version;
- class, authority band, historical cutoff, and current query time;
- initial event prefix, control head, content digests, public-log head, trust/status closure, holds,
  watched dependencies, and independently retained high-water marks;
- failure injection and exact start/end clocks;
- network policy and custody-domain availability;
- expected predicates and permitted losses;
- predicate-provenance labels frozen at admission under P37;
- actual outputs, measurements, missing evidence, and unexpected side effects.

The predicates below are test assertions, not a new project status lattice. A decisive predicate
classified `consumer_asserted`, `institutionally_supplied`, or `not_established` cannot return a
positive gate result.

## 2. Required commission fixtures

### F-01 - content-addressed store restored but control database not

**Purpose:** prove that immutable bytes do not confer control authority and that the control plane can
be reconstructed only from admitted history.

**Given** one governed record and one published record whose control events reference known CAS
digests; one extra valid CAS object never admitted by a control event; an independently retained
immutable control-event journal and high-water mark; and no usable control database snapshot.

**When** CAS is restored, the control database is empty, and recovery first attempts a read and then
replays the journal into a clean database.

**Then** before replay `Restored(governed)` and `Restored(published)` are false; the orphan authorizes
nothing; every absent digest fails closure; replay creates the frozen deterministic head; no post-
cutoff object is admitted; and RPO/RTO ends only after all class predicates pass.

**Violated invariant:** `ControlRef(event,digest)` resolves to matching bytes, and CAS possession alone
never creates `ControlRef`.

**Detection:** compare the replayed prefix, independent high-water mark, control head, CAS census, and
oracle. Missing refs, orphans, divergence, and elapsed time are explicit.

### F-02 - duplicate control event

**Given** event `E`; byte-identical retry `E'` with the same identity and payload; conflicting `E''`
with the same identity but a different payload or predecessor; and an irreversible-effect counter.

**When** `E`, `E'`, and `E''` arrive in order with a restart between deliveries.

**Then** `E` creates one effect; `E'` creates none and records a duplicate receipt; `E''` is retained as
a conflict and cannot be collapsed into the retry; replay yields one admitted `E`; and the irreversible
counter is one.

**Violated invariant:** one event identity cannot denote two payloads, and retries cannot multiply a
logical effect.

**Detection:** identity/payload digest, predecessor relation, effect count, and replay equality.

### F-03 - duplicate wake

**Given** a durably suspended case, duplicate wakes, a later wake after restart, a dependency that
remains non-positive, and an irreversible action that would occur on resume.

**When** every wake is delivered and reevaluation runs.

**Then** suspension history remains; wakes schedule reevaluation only; the dependency failure remains;
no resume occurs; the irreversible count is zero; and duplicate receipts do not create duplicate
heads.

**Violated invariant:** S0-K10 makes wake a candidate, never authority to resume
(`stage0-custody-kernel-ratification.md:102-110`).

**Detection:** replay state transitions, dependency evidence, and side effects.

### F-04 - world head advanced but fan-out incomplete

**Given** public head `H1`; admitted successor `H2`; one controlled surface on `H2`, one still on `H1`,
and one missing completion receipt; with both signed versions and log evidence retained.

**When** recovery or reconciliation runs.

**Then** both versions remain historically verifiable; completion is non-positive; `Restored(published)`
is false; no endpoint may select whichever head answered first; and OPS-R14 records divergence without
inventing PAO-R36 notice or correction semantics.

**Violated invariant:** canonical public head and completion evidence reconcile over the frozen owned-
surface denominator.

**Detection:** compare head identities and PAO-R36 completion receipts against that denominator.

### F-05 - signing-key compromise

**Given** records before, within, and after a bounded compromise interval; mixed-quality signing-time
status and trusted time; independent log checkpoints; an old private key in backup; and a separately
authorized replacement key.

**When** compromise is declared, the signer is isolated, and records are replayed from independent
custody.

**Then** the old key produces zero new signatures; proven pre-compromise records may retain historical
authenticity; unresolved-interval records are non-positive for the affected dimension; revocation
rewrites nothing; replacement evidence appends without backdating; and log rollback is independently
checked.

**Violated invariant:** private-key possession is not authority, and present failure cannot rewrite a
historical occurrence under PV-K02.

**Detection:** key activation audit, signature-key census, interval verification, independent log
reconciliation, and history digest.

### F-06 - vanished official source

**Given** a governed and published record based on retained official-source bytes and acquisition
evidence; the official endpoint and domain unavailable; no authenticated successor source; and the
retained capture intact.

**When** historical replay and a current-authority query run.

**Then** historical attribution survives; source disappearance rewrites nothing; current official
status is non-positive; the affected set is complete; no mirror is promoted; and public effects are
handed to PAO-R36 where required.

**Violated invariant:** historical evidence and current official status are separate propositions.

**Detection:** source identity, acquisition receipt, network-denied lookup, successor evidence, and
affected-set oracle.

### F-07 - ten thousand cases go stale at once

**Given** 10,000 cases linked to one dependency across all custody classes; duplicate events and
wakes; constrained capacity; one restart; and an exact affected-set oracle.

**When** the dependency expires.

**Then** protected uses become non-positive immediately; exactly 10,000 unique cases and edges are
returned; duplicates create no duplicate effect; class priority is respected; overflow is durably
visible; restart resumes from durable progress; unprocessed cases remain visibly stale; and per-class
completion/RTO is measured.

**Violated invariant:** backlog pressure cannot extend authority or hide an affected case.

**Detection:** exact affected-set comparison, unique-effect counts, backpressure telemetry, restart
replay, and per-class clocks.

## 3. Additional fixtures retained from the original result

### F-08 - last legal hold released during deletion

**Given** an object covered by two holds, one prior release, the final release racing a deletion
worker, and a passed retention deadline.

**When** the worker reads stale hold state while the release event commits.

**Then** no object, proof closure, key, or derivation is deleted until release is visible and a later
independent disposal decision re-evaluates current policy. A stale worker loses the race.

**Invariant and detector:** an effective hold is a cross-store disposal barrier; compare the hold
prefix, worker precondition, disposal-decision time, and object/key census.

### F-09 - authentic old snapshot rollback

**Given** correctly signed snapshots `S1 < S2`, an independently retained observation proving `S2`,
and a recovery package containing only `S1`.

**When** `S1` validates cryptographically.

**Then** `S1` may pass as a historical fact, but latest-head selection fails; current authority and
public head remain non-positive; and `S1` is usable only for an explicitly historical query.

**Invariant and detector:** authentic does not imply latest applicable; compare the recovered head,
monotonic observations, and checkpoint chain.

### F-10 - organization splits and two successors claim custody

**Given** original issuer `O`; successors `A` and `B`; complete copies; and conflicting succession
instruments whose scopes cannot be adjudicated from retained evidence.

**When** both successors assert current custody and authority for the same disputed scope.

**Then** original issuer remains `O`; claims and conflict evidence remain; historical authenticity is
separate; present custody/current authority is not established for the disputed scope; and neither
successor re-signs or rewrites the original.

**Invariant and detector:** storage possession is not lawful succession; compare predecessor identity,
instrument scope, query-time currentness, and issuer substitution count.

### F-11 - historical algorithm verifier unavailable in disconnected restore

**Given** intact bytes and preservation evidence, an unsupported historical algorithm, a retained
build recipe and vectors, and no network.

**When** the retained verifier path is rebuilt and executed.

**Then** the verdict is determined only by that reproducible path and frozen positive/negative/tamper
vectors. If the required verifier closure is absent, `DurablyVerifiableAt(t_v)` is non-positive while
fixity and record retention remain; no current algorithm substitutes and no history is rewritten.

**Invariant and detector:** byte preservation is not verifier closure; inspect build provenance,
dependency closure, vector outcomes, network denial, and the five-dimension report.

### F-12 - encrypted bytes restored without authorized decryption material

**Given** intact ciphertext and digest, complete control history, and unavailable authorized key
material.

**When** an appeal-relevant or legal-release record is evaluated.

**Then** fixity may pass, but readable evidentiary closure and `Restored` remain false; no unauthorized
key is imported; ciphertext is not presented as a usable record; and the affected set is retained.

**Invariant and detector:** ciphertext fixity is not evidence availability; compare digest result,
authorized-decryption result, key-destruction/hold audit, and class predicate.

### F-13 - scheduler down across authority expiry

**Given** a watched delegation expiring at `t_exp`; a scheduler outage spanning `t_exp`; no durable
due or expiry event in the independently retained history; a declaration that the alert was sent;
and a protected action requested at `t_exp + 1`.

**When** the protected-use gate and WD-05A delivery reconciliation run, and the scheduler later emits a
delayed event.

**Then** the action is non-positive at `t_exp + 1`; the late event retains effective time `t_exp` and
later processing time; the affected interval is returned; and the prospective delivery verdict is
exactly `delivery_gap` despite the intact declaration.

**Forbidden outcome:** authority-positive use or `delivery_reconciled` based on the alert declaration.

**Invariant and detector:** authority derives from evidenced time, while delivery success derives from
independently observed event history. Compare source time, query time, recomputed due set, independent
high-water mark, event history, declaration, and action count.

## 4. Four audit-amendment fixture families

F-14 remains one numbered fixture family but has two mutually exclusive executable worlds. F-14A and
F-14B each have one detector, one exact verdict, and one forbidden outcome. F-15–F-17 retain the same
discipline.

### F-14A - lawful partial succession from independently reconciled admitted instruments

**Input:** issuer `O`; content-bound instrument `IA` assigning successor `A` scope `X`; content-bound
instrument `IB` assigning successor `B` scope `Y`; canonical admission receipts for both instruments;
non-producing authoritative records against which identity, authority, scope, timing, notice,
conditions, and effective time can be reconciled; one predecessor record spanning `X union Y`; and a
conflict only over `X intersection Y`.

**Detector:** resolve every declaration and instrument reference to exact bytes and admission receipt,
independently reconcile both instruments against the non-producing authoritative records, bind each
query to its subject scope, and assert the original issuer identity remains `O`.

**Predicate provenance:** the admitted-instrument scope predicate is
`independently_reconciled` under PP-36. A declaration or marker alone never satisfies it.

**Expected verdict:** `scoped_succession_partial` — `A` is current custodian for `X-only`, `B` is current
custodian for `Y-only`, and custody/current authority is `not_established` for the overlap; original
issuer remains `O` everywhere.

**Forbidden outcome:** a global pass assigning the overlap to either successor, a global failure that
erases the independently reconciled non-overlapping scopes, or any positive conclusion obtained from
a declaration without the content-bound instrument reconciliation.

### F-14B - merely supplied or falsified succession premise

**Input:** the same issuer, successors, scope declarations, `admitted=true` markers, and claimed
instrument references remain intact, while the independently obtained instrument bytes or
non-producing authoritative record is absent, conflicts with the declaration, or proves that an
authority, scope, timing, notice, condition, or effective-time premise is false.

**Detector:** resolve the declared references, compare their exact bytes and admission receipts with
the independently obtained authoritative record, bind the query to the affected scope, and retain the
original issuer identity `O`.

**Predicate provenance:** the unresolved declaration remains `institutionally_supplied`; it does not
become PP-36 merely because an `admitted=true` marker is present.

**Expected verdict:** `succession_scope_not_established`; no positive current-custodian or
current-authority conclusion is returned for the affected scope, the original issuer remains `O`, and
the declaration, conflict, and failed reconciliation append.

**Forbidden outcome:** `scoped_succession_partial`, a current-custodian positive, or any other green
result based on the intact declaration or marker.

### F-15 - declared independence with a shared substrate

**Input:** two checkpoint observers whose records declare `independent=true`, while provenance shows
both use one control account, one storage substrate, and one root signing key that is compromised.

**Detector:** reconstruct administration, storage, key, and observation provenance from non-producing
records and collapse observers sharing any load-bearing root.

**Expected verdict:** `custody_independence_not_established`; the independent-observer count is one and
`Restored(published)` is false.

**Forbidden outcome:** counting the declarations as two independent observations or returning a green
restoration result.

### F-16 - authenticated-time rollback across expiry

**Input:** a right expires at `t_exp`; scheduler and protected-use gate share a rolled-back local
clock; an independent authenticated monotonic checkpoint proves the real coordinate is after
`t_exp`; and an action is requested.

**Detector:** compare local wall clock, trusted-time chain, checkpoint sequence, event effective time,
and action timestamp.

**Expected verdict:** `authority_time_not_established`; the protected action is blocked and the
rollback incident/affected interval appends.

**Forbidden outcome:** accepting the action because the shared local clock reports `t_exp - 1`.

### F-17 - parser and canonicalization differential after migration

**Input:** identical original signed bytes; retained parser/canonicalizer implementations `P1` and
`P2`; one migrated representation; and protected-query vectors on which `P1` and `P2` derive materially
different statements while both report syntactic success.

**Detector:** compare implementation digests, canonical signing-input bytes, protected-query results,
and original-to-migrated linkage against the frozen vectors.

**Expected verdict:** `historical_semantic_interpretation_not_established`; original bytes and both
interpretations remain retained and the differential appends.

**Forbidden outcome:** selecting either parser as authoritative merely because it is newer or returns
success.

## 5. P37 falsify-the-declaration probes

The fixture oracle is applied with declarations and markers left intact and the underlying premise
falsified:

| Probe | Declaration or marker left intact | Falsified property | Required red result |
| --- | --- | --- | --- |
| F-13 | “alert sent” | No due/expiry event exists in independent history. | `delivery_gap`; use blocked. |
| F-14B | `admitted=true`, successor identities, scope declarations, and claimed instrument refs | Exact instrument bytes or the non-producing authoritative record fails authority, scope, timing, notice, conditions, or effective time. | `succession_scope_not_established`; no current-custodian positive. |
| F-15 | `independent=true` on two observers | Both share one compromised substrate/root. | `custody_independence_not_established`; restoration false. |

These probes go red because the decisive predicates are recomputed or independently reconciled. A
fixture that accepted any intact declaration or marker would test the declaration rather than the
property.

## 6. Mandatory current-state comparator

At the pin, the suite predicts that:

- complete cross-store closure, independent high-water marks, prospective due-event reconciliation,
  mass-expiry behavior, scoped succession, common-mode independence, authenticated time, and parser
  differential handling are `absent/unallocated`;
- deduplication, runbooks, key rotation, retained artifacts, and narrow snapshot hold protection are
  useful fragments, not the aggregate capability;
- PAO-R36 and GY-N12 remain declared semantic dependencies rather than delivered runtime endpoints;
- no inspected event package satisfies the drill evidence contract.

The comparison preserves implemented fragments while refusing capability promotion.

## 7. Drill evidence contract

A qualifying drill is a retained event package proving that real intended paths were exercised.

### DE-01 - frozen scope

Identify custody classes, exact corpus and digest, counts, size distribution, dependency classes,
hold cases, public-log heads, cryptographic profiles, expected RPO/RTO, and excluded scope. Sampling
states the complete path/member denominator and method.

### DE-02 - real failure injection

Record the injection and prove it affected the intended domain. A discussion, declaration, or mocked
Boolean is not an injection.

### DE-03 - clean and independently sourced recovery

Restore into a clean environment without hidden production state. Obtain content, history,
trust/status, checkpoints, and source captures from declared independent domains, and independently
reconcile whether those domains share an administrative, storage, or key root.

### DE-04 - disconnected public-verification drill

Before the first live authority-bearing public signature, execute INT-R7 Phase A with a non-
authoritative ceremonial corpus through the real intended canonicalizer, verifier, trust/status,
log/checkpoint, preservation-event, and clean disconnected restore paths. Retain content identities
and digests for every production-target component and profile. Evidence network denial. Retain exact
positive, negative, tamper, compromise, supersession, algorithm-renewal, rollback, and parser-
differential outcomes.

After the first live record, Phase B restores that exact record from retained closure before any
fleet-wide readiness claim. Phase B cannot retroactively authorize the first record
(`int-r7/lifecycle-migration-preservation.md:558-606`).

### DE-05 - command, configuration, and anti-substitution transcript

Retain commands, tool and dependency versions, executable/component content digests, configuration
and profile digests, clock sources, errors, access identity, key activation state, and network policy.
Run one negative substitution: replace a production-target canonicalizer, verifier, reducer, or
profile with a permissive test stub while leaving marker strings and declarations intact. The drill
must fail with `real_path_identity_mismatch`.

### DE-06 - measured loss and elapsed recovery

Record latest acknowledged pre-failure event, latest restored event, computed loss interval,
recovery declaration/start/milestones/completion, and compare actual values with every class
objective. Backup settings and runbook estimates are not measurements.

### DE-07 - clause-by-clause restored predicate

Retain event-prefix, content closure, deterministic head, authority time, hold, signed-record,
public-history, correction-chain, watched-dependency, delivery-reconciliation, independence, and
measurement results. “Restore succeeded” is insufficient. PAO-R36 F11 closes only through the
conjunction `RP-10 + RC-01 + RC-07 + F-04 + F-09 + DE-07`.

### DE-08 - negative and adversarial outcomes

Include orphan content, missing control reference, duplicate/conflicting event, duplicate wake,
stale authentic checkpoint, expired right with delayed timer, tampered record, a supplied succession
declaration whose premise is falsified with markers intact, false independence, time rollback, and
parser differential. Unexpected positives fail the drill.

### DE-09 - evidence integrity and review

Package corpus, transcript, measurements, verifier results, predicate-provenance labels, and after-
action decisions under stable digests. Record operating and independent review roles without
appointing holders. Every exception has a role, due condition, and retest requirement.

### DE-10 - remediation and retest

A failed drill remains retained. Remediation and retest append, reference the same or declared revised
corpus, re-run the failed fixture, and report regression across the full seventeen-fixture-family
denominator, including both mutually exclusive F-14 worlds where applicable.

## 8. Acceptance-evidence taxonomy and closure signal

At `109ba3f4`, `platform-acceptance.md:15,23,30` records runbook presence, retention/restore posture,
and an incident/runbook tabletop as passing. `platform-acceptance-manual.md:85-95` records reading the
alert-to-runbook path and validating compose syntax. It does not claim an exercised custody-grade
restore, measured RPO/RTO, or PV-K01 passage.

The defect is the missing distinction between document presence, tabletop, exercised restore, and
custody-grade drill evidence. `OPS-R14-ACCEPTANCE-001` closes only when the acceptance surface carries
a separate non-green exercised-recovery row until a real restore runs, or links a retained DE-01–
DE-10 package with a bounded result.

## 9. Recommended exercise cadence

This is engineering research subject to institutional adoption, not a legal minimum: continuous
closure and delivery reconciliation; monthly sampled clean restore; quarterly class-spanning replay;
annual disconnected verification and independent-custody exercise; event-triggered full drill after
material change; and immediate targeted retest after incident or failed check. Calendar entries and
“last tested” metadata are not execution evidence.

## 10. Standing

The seventeen-fixture-family suite and DE-01–DE-10 are accepted bounded research specifications. No
fixture has been executed against a delivered custody chain by this amendment.

**Research standing:** `accepted_narrow_scope`.  
**Capability standing:** `NO_GO`.  
**First-public-signature gate standing:** `NO_GO`.
