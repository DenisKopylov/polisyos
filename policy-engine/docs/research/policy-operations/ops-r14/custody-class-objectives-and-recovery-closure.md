---
id: OPS-R14-CUSTODY-OBJECTIVES
artifact_kind: research_protocol
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

# Custody-class objectives and recovery closure

## 1. Decision

Adopt per-class recovery objectives with independently recoverable stores, content-addressed object
reconstruction, replay of an append-only control history, independently retained public-log and
trust/status evidence, continuous closure checks, and periodic clean-environment restores. Do not
require one universal, transactionally consistent snapshot across every store. A coordinated
snapshot may accelerate recovery, but it cannot be the sole proof because independently failing
stores can diverge before, during, or after the snapshot.

The architecture is an accepted bounded research result. The objectives below are targets for
consolidation, not a claim that the repository meets them, a legal retention schedule, or an
authorization to implement them. This amendment supplies no runtime chain, institutional commitment,
or qualifying drill; capability and first-public-signature gate standings remain `NO_GO`.

## 2. Recovery terms

### 2.1 Recovery point objective

For custody class `c`, the RPO is the maximum permitted interval between the latest acknowledged
custody-changing event before the incident and the latest event that can be reconstructed with its
referenced evidence after the assumed failure. "Zero acknowledged loss" means that no event which
received the class's durable acknowledgement may disappear. It does not promise preservation of an
operation that failed before durable acknowledgement.

An acknowledgement is custody-grade only when the event and the evidence needed to interpret it have
crossed the independently governed failure boundary required by the class. A database commit in one
failure domain is not a custody acknowledgement merely because an API returned success.

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

Independence is a predicate over administration, substrate, credential/root-key, failure, and
observation provenance. Two services or observers that share a load-bearing control account,
storage substrate, signing root, or compromised administrator are not counted as two independent
domains. The predicate must be independently reconciled; a producer's `independent=true` declaration
cannot support `Restored`.

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
| `active-incident` | zero acknowledged loss | 1 hour | The record is being used to contain harm, coordinate a response, preserve evidence, or issue a bounded warning. Delay can amplify injury and can also destroy the chronology needed to review the response. | Incident event sequence; last acknowledged command/evidence cutoff; protected read path; identity and authority recheck for every resumed mutation; no duplicate irreversible action; measured restoration clock; incident review evidence without appointing a canonical role here. |
| `appeal-relevant` | zero acknowledged loss | 4 hours | Appeal evidence is tied to procedural rights, filing windows, reasons, service, and the exact record considered. Reconstructing an approximate state can prejudice a party even if the underlying policy result is unchanged. | Complete case/evidence lineage; original reasons and versions; service/receipt evidence when consumed from an external system; legal-hold evaluation; exact historical query coordinate; no substitution of a later corrected version for the version under appeal. |
| `legal-release` | zero acknowledged loss | 4 hours | This class covers bundles subject to a legally governed release, disclosure, transfer, or restricted-access process. Both disclosure and wrongful disclosure can cause irreversible harm. Availability must be restored together with restrictions, provenance, and release authority. | Exact release scope and cutoff; access-control and restriction reconstruction; hold check; export digest; source-to-release lineage; proof no unapproved recipient or public endpoint received the bundle; separately recorded external authorization evidence. |
| `public-verification-log` | zero acknowledged loss | 2 hours for the online common view; the distributed disconnected verifier closure must remain usable without the primary | The log is anti-equivocation evidence, not merely a cache. Loss of an acknowledged leaf, checkpoint, witness observation, or consistency edge can make a valid record no longer durably verifiable and can conceal rollback. | Independently reconciled latest-head observations; inclusion and consistency proofs; checkpoint/witness reconciliation; rollback test; offline corpus verification; no dependence on the suspected primary; `DurablyVerifiableAt(t_v)` reported separately from historical authenticity and current authority. |

The times deliberately differ. A one-hour incident target is driven by harm containment, while a
five-day shadow target is tolerable because shadow artifacts must not authorize an act. Published and
public-log classes require zero acknowledged loss because a missing acknowledged append creates an
observable history fork. Appeal and legal-release classes also require zero acknowledged loss because
loss can impair a procedural or access right even when public availability is not involved.

## 4. The restored predicate

`Restored(c, cutoff)` is true only when every mandatory clause for class `c` below passes. A verifier
must consume retained evidence and emit a clause-by-clause result plus the concrete missing or
conflicting objects. It must not return one green Boolean that hides an unknown clause.

Under P37, each decisive predicate is frozen at admission with one provenance classification. A
predicate that remains `consumer_asserted`, `institutionally_supplied`, or `not_established` cannot
make `Restored` positive; the relevant clause fails closed or reports a degraded/non-positive result.
The complete package-level classification appears in the primary report.

### RC-01 - event-prefix closure

**Input:** the immutable event journal, recovered control database, independently retained high-water
mark, event identities, sequence/predecessor relations, and declared cutoff.

**Check:** recompute the logical prefix and independently reconcile it against the high-water mark.
Every acknowledged event through the cutoff is present exactly once; duplicates are byte-identical
retries or explicit conflicts; no fork is silently linearized.

**Verdict:** pass only after recomputation and independent reconciliation; otherwise replay required,
conflict found, missing acknowledged event, or not established. These are verifier findings for the
existing status machinery, not a new status lattice.

### RC-02 - control-to-content closure

For every recovered control reference `(event, digest)`:

`ControlRef(event, digest) -> CASContains(digest) and Hash(CASBytes(digest)) = digest`.

**Input:** recovered control records, referenced digests, artifact bytes, and algorithm identifiers.

**Check:** recompute every digest and reference relation. A control record without its object is an
integrity failure. An object without a control record is an orphan; it may be retained and
investigated but confers no authority.

**Verdict:** closed, missing object, digest mismatch, unsupported digest algorithm, or orphan-only.

### RC-03 - deterministic control head

**Input:** the closed event prefix, reducer/version identity, historical migration rules, and
recovered indexes.

**Check:** recompute the head from the admitted prefix and compare it with recovered indexes. The
journal outranks an index; a declared expected head cannot substitute for replay.

**Verdict:** one head, index stale, reducer unavailable, replay divergence, or fork not adjudicated.

### RC-04 - authority-time closure

**Input:** expiring-right records, effective/expiry times, revocations, renewal evidence, query time,
and the GY-N12 currentness interface.

**Check:** restored execution does not infer current authority from a historical signature or a
scheduler's failure to emit an event. Authority time is independently reconciled against retained
trusted-time/checkpoint evidence. OPS-R14 routes the currentness proposition to GY-N12, the sole
project semantic/plan contract owner; its runtime capability remains absent/undelivered
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2053-2120`).

**Verdict:** OPS-R14 never upgrades an institutionally supplied authority declaration. The requested
use is non-positive until the canonical owner returns a content-bound currentness result at the
explicit coordinate; rollback or unresolved time yields not established.

### RC-05 - hold and disposal closure

**Input:** all hold assertions/releases known to the independent history, scope/effective times,
disposal decisions, deletion logs, key-destruction logs, and recovered objects.

**Check:** recompute coverage and independently reconcile destructive-operation logs. No object under
an effective hold was deleted, garbage-collected, crypto-erased, destructively compacted, or replaced
without retained originals. Final release is followed by a distinct later disposal evaluation.

**Verdict:** no violation, attempted violation blocked, held object missing, release race, or scope not
established. An institutionally supplied release declaration alone cannot make disposal positive.

### RC-06 - signed-record verification closure

**Input:** original bytes, signature, canonicalization/format profile, signing-time credential/status,
trusted time, policy/trust roots, log/checkpoint evidence, preservation events, algorithm-renewal
evidence, verifier implementation/specification, and test vectors.

**Check:** recompute every mechanically decidable relation and independently reconcile public-history
and time observations. Report separately issuer authenticity, projection faithfulness, public
history, durable verifiability at evaluation time, and current authority. Parser/canonicalization
differentials make historical semantic interpretation non-positive; no newer parser wins by
assertion.

**Verdict:** dimension-by-dimension evidence finding, never one aggregate `valid` flag. An unresolved
institutional trust policy or competent-authority proposition degrades only its own dimension and
never rewrites another, as required by PV-K01/PV-K02
(`int-r7-r8-public-verification-and-disclosure-ratification.md:91-123`).

### RC-07 - public-history and correction-head closure

**Input:** publication events, log/checkpoints, independent observations, and PAO-R36's immutable
correction/supersession relation plus frozen denominator and fan-out completion evidence.

**Check:** recompute event order and historical lineage, then independently reconcile every controlled
member. OPS-R14 does not define correction meaning, notice, cache, subscriber, translation, or feed
semantics; those remain PAO-R36's work
(`policy-engine/docs/research/policy-operations-and-real-world-runtime-backlog.md:512-532`).

**Verdict:** reconciled only from member-bound evidence; otherwise incomplete fan-out, split head,
missing historical version, or dependency unavailable. A consumer assertion of completion cannot
make the clause positive.

PAO-R36 F11 is closed at the semantic-specification level only by the conjunction
`RP-10 + RC-01 + RC-07 + F-04 + F-09 + DE-07`; RP-10 alone is insufficient.

### RC-08 - watched-dependency coverage and prospective delivery

**Input:** restored protected records, authority-dependency edges, watched-dependency events, lead
policies, named reconciliation window, independent event high-water mark, and reproducible affected-
case query.

**Check:** recompute every right and due-event obligation; independently reconcile expected due,
overdue, expiry, or missed-delivery events against observed history; apply every expiry/revocation;
and compare the affected set with registered edges and fixture oracle.

**Verdict:** covered and `delivery_reconciled` only when both recomputation and independent
reconciliation pass; otherwise missed edge, affected-set mismatch, expired right still enabling use,
`delivery_gap`, or not established. Safe refusal at use time cannot conceal a delivery gap.

### RC-09 - measured objective

**Input:** incident declaration time, recovery start, latest acknowledged pre-incident event, latest
restored event, intermediate clocks, and test-environment identity.

**Check:** recompute actual data loss and elapsed recovery, independently reconcile load-bearing time
against authenticated/monotonic evidence, and compare with the class RPO/RTO. Configuration values,
runbook estimates, or consumer-reported completion are not measurements.

**Verdict:** met only after recomputation and time reconciliation; otherwise missed or measurement not
established, with actual values and clock sources.

## 5. Independent recovery paths

A custody-grade recovery design needs at least these logically independent paths. This list describes
required properties, not a vendor topology.

1. **Content path.** Restore immutable objects and fixity manifests without the primary control DB.
2. **Control path.** Rebuild control state from immutable history; the database is a checked projection.
3. **Public-history path.** Recover leaves, checkpoints, consistency proofs, and observations outside
   the primary publication service.
4. **Trust/status path.** Recover signing-time status, trusted time, roots, compromise intervals, and
   renewal evidence without reactivating an old private key.
5. **Source-capture path.** Preserve exact historical source bytes while separately reporting current
   official obtainability.
6. **Dependency path.** Rebuild dependency edges, due-event obligations, reconciliation windows, and
   affected-case queries so expiry does not wait for an application error.
7. **Hold path.** Recover holds before any destructive worker resumes.

No path may infer another path's truth. Store count is not proof of independence; restored bytes do
not prove control history; control rows do not prove fixity; a historical signature does not prove
current authority; an authentic checkpoint does not prove latest-applicable status.

## 6. Comparative recovery models

| Model | Decision | Selecting or eliminating property |
| --- | --- | --- |
| Per-class RPO/RTO with independent store paths | **Select.** | It reflects unequal consequences, exposes the failed evidence path, and measures recovery against a predicate rather than a backup setting. |
| One consistent snapshot across every store | **Reject as universal basis; retain as accelerator.** | It couples systems, cannot include every external domain, and can restore an authentic but stale world without anti-rollback or append closure. |
| Content-addressed reconstruction plus control-event replay | **Select with independent high-water marks and reducer/version custody.** | It separates bytes from authority chronology and makes divergence detectable. Missing content, event, environment, or independent observation fails closed. |
| Continuous verification versus point-in-time backup validation | **Select both continuous closure checks and periodic full restore; reject either alone.** | Continuous checks detect quickly but can share production failures. Backup validation proves readability, not replay, authority, public history, independence, or disconnected operation. |

## 7. Current repository and standing

The repository has useful recovery fragments in five substantive runbooks and narrow snapshot
retention/GC protection. It does not establish the class objectives, durable acknowledgement rules,
independent high-water marks, common-mode independence verifier, cross-store restored predicate,
public-log anti-rollback drill, prospective dependency delivery reconciliation, or watched-dependency
closure described above. The acceptance surface distinguishes neither exercised restore nor the full
DE-01–DE-10 package from documentation/tabletop posture
(`policy-engine/docs/archive/reports/platform-acceptance.md:15,23,30`).

**Research standing:** `accepted_narrow_scope`.  
**Capability standing:** `NO_GO`.  
**First-public-signature gate standing:** `NO_GO`.
