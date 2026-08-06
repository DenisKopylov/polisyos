---
id: OPS-R14-CUSTODY-OBJECTIVES
artifact_kind: research_protocol
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

# Custody-class objectives and recovery closure

## 1. Decision

Adopt per-class recovery objectives with independently recoverable stores, content-addressed object
reconstruction, replay of an append-only control history, independently retained public-log and
trust/status evidence, continuous closure checks, and periodic clean-environment restores. Do not
require one universal, transactionally consistent snapshot across every store. A coordinated
snapshot may accelerate recovery, but it cannot be the sole proof because independently failing
stores can diverge before, during, or after the snapshot.

The objectives below are architecture targets for consolidation. They are not a claim that the
repository meets them, a legal retention schedule, or an authorization to implement them.

## 2. Recovery terms

### 2.1 Recovery point objective

For custody class `c`, the RPO is the maximum permitted interval between the latest acknowledged
custody-changing event before the incident and the latest event that can be reconstructed with its
referenced evidence after the assumed failure. "Zero acknowledged loss" means that no event which
received the class's durable acknowledgement may disappear. It does not promise preservation of an
operation that failed before durable acknowledgement.

An acknowledgement is custody-grade only when the event and the evidence needed to interpret it have
crossed the independent failure boundary required by the class. A database commit in one failure
domain is not a custody acknowledgement merely because the API returned success.

### 2.2 Recovery time objective

For custody class `c`, the RTO is the maximum elapsed time from declared recovery start until
`Restored(c, cutoff)` is established. A service that answers requests while the predicate remains
unknown is degraded, not restored. A class may expose safe historical read or offline verification
before full mutation resumes, but the published RTO below is the deadline for the class's minimum
safe service.

### 2.3 Assumed loss model

The objectives assume independent failure can affect any one of these custody domains, or a bounded
combination that does not destroy every independently governed copy:

1. the content-addressed artifact store;
2. the control database and its indexes;
3. the immutable control-event journal;
4. the public verification log, checkpoints, and independently retained observations;
5. the signing-time trust/status and timestamp evidence archive;
6. retained source captures and format/verifier closure;
7. a worker fleet, scheduler, queue, or cache;
8. one organization, service operator, or primary publication endpoint.

The objectives do **not** assume survival after simultaneous destruction or compromise of every
independent custody domain, the absence of any competent successor institution, a jurisdiction-wide
loss of legal mandate, or a national/institutional continuity event requiring replacement of whole
organizations. Those questions remain deferred with OPS-R12.

## 3. Custody classes

| Custody class | Proposed RPO | Proposed RTO | Why this class differs | Evidence that the objective was met |
| --- | ---: | ---: | --- | --- |
| `shadow` | 24 hours | 5 business days | Shadow material is not permitted to carry governed or public authority. It may be expensive to recompute but loss does not erase a relied-on public act. A wider loss window and slower restore are acceptable if promotion remains blocked. | Frozen event cutoff; source and recipe inventory; recomputation or restoration manifest; digest comparison; proof no governed/published reference targets the lost interval; explicit list of unrecoverable shadow work. |
| `governed` | 15 minutes | 24 hours | Governed material can shape internal review, promotion, and authority-bearing decisions. Limited recent work may be repeated, but losing a completed review, decision, or dependency change without detection is unacceptable. | Replayed event prefix; control-to-content closure; actor/authority evidence; deterministic head reconstruction; duplicate suppression; comparison against independently retained event high-water mark; no unauthorized promotion during recovery. |
| `published` | zero acknowledged loss | 4 hours for safe read and verification; 24 hours for full controlled mutation | A published signed record may already be relied on by citizens, officials, journalists, courts, or downstream systems. Lost acknowledged publication or status history creates equivocation and cannot be repaired by silently republishing. | Original bytes and signature; signing-time status; log inclusion and consistency evidence; public head reconciliation; PAO-R36 correction/supersession interface reconciliation; five INT-R7 reportable dimensions; divergence and outage receipt. |
| `active-incident` | zero acknowledged loss | 1 hour | The record is being used to contain harm, coordinate a response, preserve evidence, or issue a bounded warning. Delay can amplify injury and can also destroy the chronology needed to review the response. | Incident event sequence; last acknowledged command/evidence cutoff; protected read path; identity and authority recheck for every resumed mutation; no duplicate irreversible action; measured restoration clock; incident commander review evidence without appointing a canonical role here. |
| `appeal-relevant` | zero acknowledged loss | 4 hours | Appeal evidence is tied to procedural rights, filing windows, reasons, service, and the exact record considered. Reconstructing an approximate state can prejudice a party even if the underlying policy result is unchanged. | Complete case/evidence lineage; original reasons and versions; service/receipt evidence when consumed from an external system; legal-hold evaluation; exact historical query coordinate; no substitution of a later corrected version for the version under appeal. |
| `legal-release` | zero acknowledged loss | 4 hours | This class covers bundles subject to a legally governed release, disclosure, transfer, or restricted-access process. Both disclosure and wrongful disclosure can cause irreversible harm. Availability must be restored together with restrictions, provenance, and release authority. | Exact release scope and cutoff; access-control and restriction reconstruction; hold check; export digest; source-to-release lineage; proof no unapproved recipient or public endpoint received the bundle; separately recorded external authorization evidence. |
| `public-verification-log` | zero acknowledged loss | 2 hours for the online common view; the distributed disconnected verifier closure must remain usable without the primary | The log is anti-equivocation evidence, not merely a cache. Loss of an acknowledged leaf, checkpoint, witness observation, or consistency edge can make a valid record no longer durably verifiable and can conceal rollback. | Independent latest-head observations; inclusion and consistency proofs; checkpoint/witness reconciliation; rollback test; offline corpus verification; no dependence on the suspected primary; `DurablyVerifiableAt(t_v)` reported separately from historical authenticity and current authority. |

The times deliberately differ. A one-hour incident target is driven by harm containment, while a
five-day shadow target is tolerable because shadow artifacts must not authorize an act. Published and
public-log classes require zero acknowledged loss because a missing acknowledged append creates an
observable history fork. Appeal and legal-release classes also require zero acknowledged loss because
loss can impair a procedural or access right even when public availability is not involved.

## 4. The restored predicate

`Restored(c, cutoff)` is true only when every mandatory clause for class `c` below passes. A verifier
must consume retained evidence and emit a clause-by-clause result plus the concrete missing or
conflicting objects. It must not return one green Boolean that hides an unknown clause.

### RC-01 - event-prefix closure

**Input:** the independent event journal, recovered control database, independently retained
high-water mark, event identities, sequence/predecessor relations, and declared cutoff.

**Check:** every acknowledged event through the class cutoff is present exactly once in the logical
history; duplicates are either byte-identical retries or explicitly conflicting events; no fork is
silently linearized.

**Verdict:** pass, replay required, conflict found, missing acknowledged event, or not established.
These are verifier findings to feed the existing status machinery, not a new status lattice.

### RC-02 - control-to-content closure

For every recovered control reference `(event, digest)`:

`ControlRef(event, digest) -> CASContains(digest) and Hash(CASBytes(digest)) = digest`.

**Input:** recovered control records, referenced digests, artifact bytes, and algorithm identifiers.

**Check:** every authoritative control reference resolves to bytes whose digest matches. A control
record without its object is an integrity failure. An object without a control record is an orphan;
it may be retained and investigated but it confers no authority.

**Verdict:** closed, missing object, digest mismatch, unsupported digest algorithm, or orphan-only.

### RC-03 - deterministic control head

**Input:** the closed event prefix, reducer/version identity, historical migration rules, and
recovered indexes.

**Check:** rebuilding from the admitted prefix produces exactly one control head for the requested
historical coordinate. Indexes must agree with replay; a recovered index never outranks the journal.

**Verdict:** one head, index stale, reducer unavailable, replay divergence, or fork not adjudicated.

### RC-04 - authority-time closure

**Input:** the relevant expiring-right records, effective and expiry times, revocations, renewal
evidence, query time, and the GY-N12 currentness interface.

**Check:** restored execution does not infer current authority from a historical signature or from a
scheduler's failure to emit an expiry event. Currentness is evaluated at the explicit query
coordinate. GY-N12 remains the sole epoch/currentness owner
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2053-2120`).

**Verdict:** currentness evidence supports the requested use, currentness is non-positive, or
currentness is not established. Recovery never upgrades the result.

### RC-05 - hold and disposal closure

**Input:** all hold assertions and releases known to the independent event history, their scope and
effective times, disposal decisions, deletion logs, encryption-key destruction logs, and recovered
objects.

**Check:** no object under any effective hold was deleted, garbage-collected, crypto-erased,
destructively compacted, or replaced without retained originals. A last-hold release must be
followed by a separate post-release disposal evaluation; release is not an implicit delete command.

**Verdict:** no violation, attempted violation blocked, held object missing, release race, or scope not
established.

### RC-06 - signed-record verification closure

**Input:** original bytes, signature, canonicalization and format profile, signing-time credential and
status, trusted-time evidence, policy/trust roots, log/checkpoint evidence, preservation events,
algorithm-renewal evidence, verifier implementation or reproducible specification, and test vectors.

**Check:** the five INT-R7 dimensions can be separately evaluated: issuer issuance authenticity,
projection faithfulness, public history, durable verifiability at evaluation time, and current
authority at the selected query time. A failure in one dimension does not overwrite another. This is
required by PV-K01 and PV-K02
(`policy-engine/docs/system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md:91-123`).

**Verdict:** dimension-by-dimension evidence finding, never one aggregate "valid" flag.

### RC-07 - public-history and correction-head closure

**Input:** publication events, log/checkpoints, independently retained observations, and the
PAO-R36-provided immutable correction/supersession relation plus fan-out completion evidence.

**Check:** the recovered system exposes the same canonical public head and historical lineage at all
owned surfaces. OPS-R14 checks durability and reconciliation. It does not define what a correction
means, its notice format, cache behavior, subscriber protocol, translation parity, or correction
feed; those remain PAO-R36's work
(`policy-engine/docs/research/policy-operations-and-real-world-runtime-backlog.md:512-532`).

**Verdict:** reconciled, incomplete fan-out, split head, missing historical version, or dependency not
available.

### RC-08 - watched-dependency coverage

**Input:** restored governed/published/incident/appeal/release records, their authority-dependency
edges, all watched-dependency events through the cutoff, and a reproducible affected-case query.

**Check:** every right that enabled a protected use is represented, every expiration or revocation
through the cutoff is applied, and the affected set is complete relative to the registered edges.

**Verdict:** covered, missed dependency edge, affected-set mismatch, expired right still enabling
use, or not established.

### RC-09 - measured objective

**Input:** incident declaration time, recovery start, latest acknowledged pre-incident event, latest
restored event, all intermediate clocks, and test-environment identity.

**Check:** compute actual data loss and elapsed recovery. Compare the measurements with the class
RPO/RTO. Configuration values or backup schedules do not count as measurements.

**Verdict:** met, missed, or measurement not established, with actual values and clock sources.

## 5. Independent recovery paths

A custody-grade recovery design needs at least these logically independent paths. This list describes
required properties, not a vendor topology.

1. **Content path.** Restore immutable objects and fixity manifests from a domain that can be read
   without the primary control database.
2. **Control path.** Rebuild control state from an immutable journal, not only from a database
   snapshot. The recovered database is a projection whose equality to replay is checked.
3. **Public-history path.** Recover log leaves, checkpoints, consistency proofs, and independent
   observations from outside the primary publication service.
4. **Trust/status path.** Recover signing-time credential status, trusted-time, policy roots,
   revocation/compromise intervals, and algorithm-renewal evidence without reactivating any old
   private signing key.
5. **Source-capture path.** Preserve the exact official-source bytes and acquisition evidence used at
   the historical time, while separately reporting whether a current official source remains
   obtainable.
6. **Dependency path.** Rebuild authority-dependency edges and affected-case queries so expiry does
   not wait for an application error.
7. **Hold path.** Recover hold assertions before any disposal or compaction job resumes.

No path is allowed to infer another path's truth. Restored CAS bytes do not prove control history;
restored control rows do not prove object fixity; a valid historical signature does not prove current
authority; an authentic old checkpoint does not prove it is the latest applicable checkpoint.

## 6. Comparative recovery models

| Model | Decision | Selecting or eliminating property |
| --- | --- | --- |
| Per-class RPO/RTO with independent store paths | **Select.** | It reflects unequal public, procedural, and harm consequences and exposes which store failed. Objectives are measured against a restored predicate, not a backup setting. |
| One consistent snapshot across every store | **Reject as the universal basis; retain as an accelerator.** | It couples independently failing systems, may be impossible across external logs and custody domains, and can still restore an authentic but stale world. It cannot prove anti-rollback or post-snapshot append closure. |
| Content-addressed reconstruction plus control-event replay | **Select with independent high-water marks and reducer/version custody.** | It distinguishes immutable bytes from authority-bearing control history and makes divergence detectable. It fails closed when an object, event, or replay environment is missing. |
| Continuous verification versus point-in-time backup validation | **Select continuous closure checks plus periodic full restore-and-verify. Reject either alone.** | Continuous checks shorten detection but can share the production failure mode. Backup validation proves readability at one time but not replay, authority, or disconnected operation. |

## 7. What the current repository would do

The repository has useful recovery fragments in the five inspected runbooks and narrow snapshot
retention/GC protection. It does not establish the class objectives, durable acknowledgement rules,
independent high-water marks, cross-store restored predicate, public-log anti-rollback drill, or
watched-dependency closure described above. The acceptance evidence currently treats runbook and
policy presence as recovery posture (`policy-engine/docs/archive/reports/platform-acceptance.md:15,23,30`).
Accordingly, every proposed objective remains research guidance and the overall standing remains
`NO_GO`.
