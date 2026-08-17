---
id: OPS-R14-DISASTER-DRILLS
artifact_kind: research_fixture_protocol
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

# Disaster fixtures and drill evidence

## 1. Fixture execution contract

Each fixture is an executable specification even though this research supplies no test code. A later
semantic test must instantiate the stated corpus and failure injection, run the real intended paths,
and compare every expected predicate. A test that only searches for marker strings does not pass,
applying the repository's behavioral-gate rule at `AGENTS.md:28`.

Every execution freezes:

- repository and implementation commit;
- fixture corpus digest and generator/version;
- class, authority band, historical cutoff, and current query time;
- initial event prefix, control head, content digests, public-log head, trust/status closure, holds,
  watched dependencies, and independently retained high-water marks;
- failure injection and exact start/end clocks;
- network policy and custody-domain availability;
- expected predicates and permitted losses;
- actual outputs, measurements, missing evidence, and unexpected side effects.

The predicates below are test assertions, not a new project status lattice.

## 2. Required commission fixtures

### F-01 - content-addressed store restored but control database not

**Purpose:** prove that immutable bytes do not confer control authority and that the control plane can
be reconstructed only from admitted history.

**Given**

- one governed record and one published record whose control events reference known CAS digests;
- one extra valid CAS object that was never admitted by a control event;
- an independently retained immutable control-event journal and high-water mark;
- no usable control database snapshot.

**When**

- the CAS is restored;
- the control database is empty;
- recovery first attempts a read, then replays the event journal into a clean database.

**Then**

1. before replay, `Restored(governed)` and `Restored(published)` are false;
2. the orphan object is retained for investigation but authorizes no record, publication, or head;
3. every control reference whose digest is absent fails control-to-content closure;
4. replay creates the same deterministic control head as the frozen oracle;
5. no post-cutoff object is silently admitted;
6. RPO/RTO measurement starts at declared recovery start and ends only after all class predicates
   pass.

**Violated invariant:** `ControlRef(event,digest)` must resolve to matching bytes, and CAS possession
alone must not create `ControlRef`.

**Detection:** compare replayed event prefix, control head, CAS census, and oracle. Verdict identifies
missing refs, orphans, replay divergence, and elapsed time.

**Current-state comparator:** `replay-or-restore.md` and retained-artifact recovery contain useful
replay and digest procedures, but no inspected evidence proves a clean cross-store restore with an
independent high-water mark and orphan-authority negative assertion
(`policy-engine/docs/runbooks/replay-or-restore.md:1-128`;
`policy-engine/docs/runbooks/retained-artifact-recovery.md:1-180`). A runbook-only closeout fails this fixture.

### F-02 - duplicate control event

**Purpose:** prove idempotent admission without suppressing a conflicting event that reuses an
identity.

**Given**

- one event `E` that creates a governed control effect;
- byte-identical retry `E'` with the same event identity and payload;
- conflicting `E''` with the same event identity but a different payload or predecessor;
- an irreversible downstream action counter.

**When**

- `E`, `E'`, and `E''` are delivered in that order, including a restart between deliveries.

**Then**

1. `E` creates exactly one logical effect;
2. `E'` creates zero additional logical or irreversible effects and records a duplicate receipt;
3. `E''` is not collapsed into the retry; it is quarantined or otherwise made non-positive as a
   conflict;
4. replay before and after restart yields one admitted `E` and the retained conflict evidence;
5. the downstream irreversible action count is one.

**Violated invariant:** one event identity cannot denote two payloads, and a retry cannot multiply a
logical effect.

**Detection:** identity/payload digest comparison, predecessor check, effect-count oracle, and replay
comparison.

**Current-state comparator:** the fabric recovery runbook discusses deduplication and replay, but the
inspected acceptance evidence does not execute this authority-semantic conflict fixture
(`policy-engine/docs/runbooks/fabric-quarantine-dlq-and-data-plane-recovery.md:1-178`).

### F-03 - duplicate wake

**Purpose:** prove S0-K10: wake is a candidate, never authority to resume.

**Given**

- a case durably suspended for an expired dependency;
- two byte-identical wake deliveries and one later wake after a worker restart;
- the dependency remains non-positive;
- an irreversible action that would occur if the case resumed.

**When**

- all wakes are delivered and the case is reevaluated each time.

**Then**

1. the suspension history remains present;
2. each wake may schedule reevaluation, but none directly changes authority or case state;
3. reevaluation returns the existing dependency failure;
4. the case does not resume and the irreversible action count remains zero;
5. duplicate wake receipts are retained without creating duplicate current heads.

**Violated invariant:** S0-K10 requires durable suspension and treats wake as only a candidate
(`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:102-110`).

**Detection:** replay the case history and compare state transitions, dependency evidence, and side
effects.

**Current-state comparator:** `ControlWorker` emits/handles wake and lease activity, but its lease
renewal is not an authority dependency and the inspected path does not establish a case-level
S0-K10 semantic test (`policy-engine/src/polisyos/runtime/http/services/control_worker.py:84-174`).

### F-04 - world head advanced but fan-out incomplete

**Purpose:** preserve one public history while respecting the PAO-R36 seam.

**Given**

- a published record with public head `H1`;
- an admitted change produces `H2` and advances the governed world head;
- one owned public surface has `H2`, another still exposes `H1`, and one subscriber completion receipt
  is missing;
- both signed versions and their public-log evidence remain present.

**When**

- recovery or reconciliation runs after the partial fan-out.

**Then**

1. both historical versions remain byte- and signature-verifiable;
2. no surface is allowed to claim fan-out complete;
3. `Restored(published)` remains false until PAO-R36's completion interface reconciles the surfaces;
4. current public posture for the affected set is non-positive or explicitly degraded rather than
   silently selecting whichever endpoint answered first;
5. OPS-R14 records the divergence, affected set, and completion evidence; it does not invent a notice
   or correction protocol.

**Violated invariant:** the canonical public head and completion evidence must reconcile across owned
surfaces.

**Detection:** compare head identities and PAO-R36-provided completion receipts against the frozen
surface census.

**Current-state comparator:** no inspected OPS-R14 primitive supplies fan-out-completion evidence;
PAO-R36 is parallel and owns the missing semantics. Treating a valid signature on `H2` as complete
publication would cross the seam and fail.

### F-05 - signing-key compromise

**Purpose:** separate historical authenticity, compromise interval, current authority, and future
signing.

**Given**

- signed records immediately before, within, and after a bounded compromise interval;
- signing-time status and trusted-time evidence of varying quality;
- independently retained public-log checkpoints;
- a backup containing the old private key;
- a separately authorized replacement key.

**When**

- compromise is declared, the primary signer is isolated, and records are replayed from independent
custody.

**Then**

1. zero new signatures are produced by the compromised or restored old key;
2. records proven before the compromise interval can retain historical issuer authenticity;
3. records in an unresolved interval are non-positive for the affected verification dimension;
4. a present revocation does not delete or rewrite original records;
5. replacement-key evidence appends and never backdates a replacement issuance;
6. public-log rollback and selective omission are checked independently.

**Violated invariant:** private-key possession is not authority; present evidentiary failure cannot
rewrite historical occurrence under PV-K02.

**Detection:** key-activation audit, signature-key census, interval-boundary verification, public-log
head reconciliation, and history digest comparison.

**Current-state comparator:** `key-rotation.md` provides rotation and emergency revocation procedure,
but no inspected drill proves signing-time interval replay, independent log recovery, or refusal to
reactivate a backed-up key over a decades-long closure
(`policy-engine/docs/runbooks/key-rotation.md:1-113`).

### F-06 - a vanished official source

**Purpose:** distinguish retained historical evidence from present official-source obtainability.

**Given**

- a governed and published record based on captured official-source bytes and acquisition evidence;
- the official endpoint, domain, and current API all become unavailable;
- no independently authenticated successor source is available;
- the retained capture remains intact.

**When**

- a historical replay and a current-authority query are run.

**Then**

1. the historical replay may use and attribute the retained capture;
2. source disappearance does not rewrite what PolicyOS used historically;
3. current source authority/obtainability is non-positive or not established;
4. every record whose current posture depended on that source appears in the affected query;
5. no mirror or cached page is silently promoted to official successor;
6. public effects are handed to PAO-R36 where needed.

**Violated invariant:** historical evidence and current official status are separate propositions.

**Detection:** source-identity and acquisition-receipt verification, network-denied current lookup,
successor-evidence check, and affected-set oracle.

**Current-state comparator:** retained-artifact mechanisms can preserve bytes, but the inspected
repository does not establish a first-class watched source right, renewal/currentness owner, or
complete affected-case query.

### F-07 - ten thousand cases going stale at once

**Purpose:** prove bounded, deduplicated, priority-aware invalidation without extending authority
through overload.

**Given**

- 10,000 cases linked to one expiring dependency;
- a mix of shadow, governed, published, active-incident, appeal-relevant, and legal-release classes;
- duplicate expiry and wake deliveries;
- constrained worker capacity and one restart;
- an oracle containing the exact affected set.

**When**

- the dependency expires and the event is admitted once.

**Then**

1. authority-time checks make affected protected uses non-positive immediately, independent of queue
   delay;
2. the affected query returns exactly 10,000 unique cases with their dependency edges;
3. duplicate events and wakes create no duplicate irreversible effects;
4. processing is prioritized by custody class, with active incidents and public/appeal/release risks
   handled before shadow recomputation;
5. queue growth remains bounded by the declared operating envelope, and overflow is durably visible;
6. restart resumes from durable progress without skipping or repeating logical case effects;
7. every unprocessed case remains visibly stale rather than appearing current;
8. measured completion and per-class RTO are reported.

**Violated invariant:** backlog pressure cannot extend authority or hide an affected case.

**Detection:** affected-set exact comparison, unique-effect counts, queue/backpressure telemetry,
restart replay, and per-class clocks.

**Current-state comparator:** scattered expiry/TTL fields and worker leasing do not establish a
single governed dependency event, complete affected query, class priority, or mass-expiry semantic
test. This is the first commission falsifier in executable form.

## 3. Additional fixtures constructed by OPS-R14

### F-08 - last legal hold released during deletion

**Given** an object covered by two holds, one release already admitted, the second release racing a
retention deletion worker, and a retention deadline in the past.

**When** the worker reads stale hold state while the final release event commits.

**Then** no object, proof closure, key, or derivation is deleted until the final release is visible
**and** a later independent disposal decision re-evaluates current policy. Releasing one of two holds
never permits deletion. A stale worker precondition fails rather than winning the race.

**Violated invariant:** an effective hold is a cross-store disposal barrier; release is not a delete
command.

**Detection:** compare hold event prefix, worker precondition token, disposal decision time, and
object/key census.

**Current-state comparator:** snapshot GC can protect a legal-hold tag, but no inspected general hold
issuance/release or race protocol exists
(`policy-engine/src/polisyos/fabric/security/retention.py:32-38,100-112`;
`policy-engine/src/polisyos/fabric/world/store/snapshots.py:661-689`).

### F-09 - authentic old snapshot rollback

**Given** two correctly signed status/control snapshots `S1 < S2`, a later independently retained
checkpoint proving `S2`, and a recovery package containing only `S1`.

**When** recovery validates `S1`'s signature.

**Then** authenticity of `S1` passes as a historical fact, but latest-applicable-head selection fails
or rollback is detected. Current authority and current public head remain non-positive. `S1` may be
used only for an explicitly historical query.

**Violated invariant:** authentic does not imply latest applicable.

**Detection:** compare recovered head with independent monotonic observations and checkpoint chain.

**Current-state comparator:** INT-R7 specifies this anti-rollback outcome, but no inspected OPS-R14
drill evidence establishes it
(`policy-engine/docs/research/policy-operations/int-r7/lifecycle-migration-preservation.md:607-629`).

### F-10 - organization splits and two successors claim custody

**Given** original issuer `O`, two successor organizations `A` and `B`, both holding complete copies,
and conflicting succession instruments whose scopes cannot be adjudicated by retained evidence.

**When** each successor serves the same predecessor record and asserts current custody/authority.

**Then** original issuer attribution remains `O`; both custody claims and conflict evidence are
preserved; historical authenticity is evaluated independently; current custody/current authority is
not established for the disputed scope; neither successor may rewrite or re-sign the original as its
own act.

**Violated invariant:** storage possession and organizational continuity are not equivalent to lawful
succession.

**Detection:** predecessor identity check, succession-instrument scope comparison, query-time
currentness, and zero issuer-substitution assertion.

**Current-state comparator:** INT-R7 specifies lawful succession semantics, but the repository does
not establish an implemented succession adjudication or recovery chain.

### F-11 - historical algorithm verifier unavailable in a disconnected restore

**Given** intact signed bytes and preservation evidence, an algorithm no longer supported by the
current runtime, a retained build recipe and test vectors, and no network.

**When** a clean environment attempts verification.

**Then** the drill first tries the reproducible retained verifier path. If it can be rebuilt and passes
positive/negative/tamper vectors, durable verification may pass. If it cannot, fixity and historical
record retention remain, but `DurablyVerifiableAt(t_v)` is non-positive; no current algorithm is
substituted and no history is rewritten.

**Violated invariant:** byte preservation alone is not verifier closure.

**Detection:** build provenance, dependency closure, vector results, network-denial evidence, and
five-dimension report.

**Current-state comparator:** no inspected runbook demonstrates a disconnected historical verifier
rebuild or exact negative outcome.

### F-12 - encrypted bytes restored, only decryption key missing

**Given** intact CAS bytes, matching ciphertext digest, complete control history, and unavailable or
destroyed authorized decryption material.

**When** recovery evaluates an appeal-relevant or legal-release record.

**Then** fixity may pass, but readable evidentiary closure and `Restored` remain false. Recovery does
not import an unauthorized key or disclose ciphertext as a usable record. The missing-key event and
affected set are retained.

**Violated invariant:** ciphertext fixity is not evidence availability or legal-release readiness.

**Detection:** digest pass plus authorized-decryption failure, key-destruction/hold audit, and
class-specific restored predicate.

**Current-state comparator:** artifact recovery checks do not by themselves establish authorized key
recovery and appeal/release usability.

### F-13 - scheduler is down across authority expiry

**Given** a watched delegation expiring at `t_exp`, a scheduler outage from before `t_exp` until after
it, no expiry wake, and a protected action requested at `t_exp + 1`.

**When** the action gate evaluates the request and the scheduler later emits the delayed event.

**Then** the request is non-positive at `t_exp + 1`; absence of the event does not extend the
right; the late event is recorded with effective time `t_exp` and later processing time; no prior
unauthorized action becomes valid; the affected query covers the outage interval.

**Violated invariant:** authority derives from evidenced time, not successful timer delivery.

**Detection:** compare authority source, query time, scheduler logs, event effective/processing time,
and action count.

**Current-state comparator:** the repository has many time-to-live and expiry fields but no
established governed event with owner, renewal evidence, grace authority, affected query, and failure
consequence. A sudden runtime error after `t_exp` therefore remains plausible.

## 4. Mandatory negative comparator: present repository state

Against the current state, the fixture suite predicts these failures:

- F-01 can restore bytes or follow a runbook, but cannot prove the complete cross-store restored
  predicate and independent event high-water mark.
- F-02 has deduplication-related mechanisms, but no inspected authority-semantic conflict drill.
- F-03 has wake and lease mechanics, but no established rule tying duplicate wakes to S0-K10 case
  semantics.
- F-04 has no owned fan-out completion interface; PAO-R36 is still parallel.
- F-05 has rotation/revocation procedure, but no long-horizon independent compromise-interval drill.
- F-06 can retain artifacts, but has no governed source-expiry watch and complete affected query.
- F-07 has no first-class mass-expiry event/owner chain and no 10,000-case stale-storm fixture.
- F-08 protects selected snapshot tags but has no cross-store hold release/deletion race semantics.
- F-09 is specified by INT-R7, but no OPS-R14 recovery evidence executes it.
- F-10 has no implemented organizational-succession recovery owner.
- F-11 has no disconnected historical-verifier build-and-negative-evidence drill.
- F-12 does not prove authorized decryption closure merely by restoring ciphertext.
- F-13 can miss a timer and surface expiry as a runtime error because authority-time evaluation is
  not represented as the governed watched dependency defined here.

The comparison does not deny the runbooks or unit mechanisms. It denies promotion of those fragments
to a custody-grade capability without the missing chain and evidence.

## 5. Drill evidence contract

A qualifying drill is a retained event package proving that real intended paths were exercised. It
must contain all of the following.

### DE-01 - frozen scope

Identify the custody classes, exact corpus and digest, record counts, size distribution, dependency
classes, hold cases, public-log heads, cryptographic profiles, expected RPO/RTO, and all excluded
scope. Sampling must state the complete denominator and selection method.

### DE-02 - real failure injection

Record the injected failure and prove it affected the intended domain: deleted or isolated control
database, inaccessible primary object store, corrupt object, stale checkpoint, queue duplication,
key quarantine, source disappearance, or network denial. A discussion of what would happen is not an
injection.

### DE-03 - clean and independently sourced recovery

Restore into a clean environment without hidden production state. For a cross-custody drill, obtain
objects, event history, trust/status, checkpoints, and source captures from the declared independent
domains. Record environment identity and prove the suspected primary was unavailable or untrusted.

### DE-04 - disconnected public-verification drill

Before the first live authority-bearing public signature, execute INT-R7 Phase A using a
non-authoritative ceremonial corpus through the real intended canonicalization, verifier, trust and
status inputs, log/checkpoint path, preservation event path, and clean disconnected restore. Network
denial must be evidenced, not asserted. Exact positive, negative, tamper, compromise, supersession,
algorithm-renewal, and rollback outcomes must be retained.

After the first live record, Phase B restores and verifies that exact record from retained closure in
a clean disconnected environment before any fleet-wide readiness claim. Phase B cannot retroactively
authorize the first record. These requirements come from INT-R7's controlling amendment
(`policy-engine/docs/research/policy-operations/int-r7/lifecycle-migration-preservation.md:558-606`).

### DE-05 - command and configuration transcript

Retain operator actions, tool and dependency versions, configuration digests, clock sources, error
output, access identity, key activation state, and network policy. Redact or protect secrets without
removing the evidence needed to prove which path ran.

### DE-06 - measured loss and elapsed recovery

Record the latest acknowledged pre-failure event, latest restored event, computed loss interval,
recovery declaration time, start, every major milestone, and completion only when the restored
predicate passes. Compare actual values with each class objective. A configured backup frequency is
not an RPO measurement; a runbook estimate is not an RTO measurement.

### DE-07 - clause-by-clause restored predicate

Retain event-prefix, control-to-content, deterministic-head, authority-time, hold, signed-record,
public-history, watched-dependency, and measurement results. Include every missing object, conflict,
or non-positive dimension. "Restore succeeded" is insufficient.

### DE-08 - negative and adversarial outcomes

The drill must prove fail-closed behavior, not only a happy path. At minimum include an orphan object,
missing control reference, duplicate/conflicting event, duplicate wake, stale authentic checkpoint,
expired right with delayed timer, and tampered signed record. Unexpected positives fail the drill.

### DE-09 - evidence integrity and review

Package the drill corpus, transcript, measurements, verifier results, and after-action decisions under
stable digests. Record responsible operating and independent review roles without appointing their
holders here. Every exception has an owner role, due condition, and retest requirement.

### DE-10 - remediation and retest

A failed drill remains retained. Remediation appends; it does not rewrite the first result. A later
retest references the same or declared revised corpus, proves the fix under the failed fixture, and
reports regressions across the full mandatory suite.

## 6. Why a paper runbook cannot satisfy the contract

A runbook describes intended procedure. It cannot by itself establish that:

- the backup existed at the incident cutoff;
- the independent copy was actually independent;
- credentials and keys were usable without violating security policy;
- all acknowledged events survived;
- cross-store references closed;
- an authentic but stale head was rejected;
- the verifier ran without the network;
- duplicate events and wakes caused zero duplicate effects;
- RPO and RTO were measured and met;
- the public and authority dimensions remained correctly separated.

The current acceptance material closes posture items from runbook presence and a tabletop review
(`policy-engine/docs/archive/reports/platform-acceptance.md:15,23,30`;
`policy-engine/docs/archive/reports/platform-acceptance-manual.md:85-95`). That is documentary
preparedness, not drill evidence under PV-K01.

## 7. Recommended exercise cadence

This is an engineering recommendation subject to institutional adoption, not a legal minimum:

- continuous fixity, event-prefix, public-head, dependency-due, and hold-barrier checks;
- monthly sampled restore into a clean non-production environment, with a complete denominator and
  reproducible sample;
- quarterly class-spanning cross-store replay/restore including duplicate and stale-head fixtures;
- annual disconnected public-verification and independent-custody exercise;
- event-triggered full drill after major storage, cryptographic, format, verifier, control-journal,
  organizational-custody, or public-correction integration change;
- immediate targeted drill after a real incident or a failed continuous check.

A cadence is accepted only when the retained drill packages show execution. Calendar entries and
"last tested" frontmatter are not evidence.
