---
id: OPS-R14-LONG-TERM-REPLAY
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

# Long-term replay and preservation semantics

The protocol is an accepted bounded research result. It is not a repository capability claim, and it
does not open the first-public-signature gate. The pinned repository has no complete long-horizon
replay chain or retained qualifying disconnected drill.

## 1. Replay is four questions, not one

A custody-grade replay must answer four separable questions:

1. **Byte and fixity question:** are the original bytes and every referenced object present and
   unchanged under the recorded digest method?
2. **Historical issuance question:** does retained signing-time evidence support that the identified
   issuer performed the recorded act at the recorded time?
3. **Historical semantic question:** can the record be interpreted under the format, canonicalization,
   rules, dependencies, and organizational facts applicable at that historical coordinate?
4. **Current authority question:** may the record or its result be relied on for the requested use at
   the current query coordinate?

The answers can differ. A record may be byte-perfect and historically authentic while no longer
current. A format may be interpretable while a required authority source is unavailable. A current
record may be non-public because evidence is competently restricted. PV-K01 requires separately
reportable dimensions and PV-K02 forbids present failure from rewriting a historical act
(`policy-engine/docs/system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md:91-123`).

Every replay gate applies P37. Mechanically decidable predicates are recomputed from retained bytes and
history; observations such as time, checkpoint order, custody independence, and admitted-instrument
identity/scope are independently reconciled. A decisive predicate that remains consumer-asserted,
institutionally supplied, or not established cannot produce a positive replay or current-authority
claim.

## 2. Preservation closure

The retained closure for a signed record includes, at minimum, the following semantic material. This
is a responsibility list, not a schema:

- exact original bytes, detached or embedded signature, and stable identity;
- canonicalization and signing profile actually used;
- signer credential chain, roots, policy identifiers, and signing-time status evidence;
- trusted-time evidence and the time semantics needed to interpret it;
- public-log inclusion, consistency, checkpoint, and independent observation evidence where used;
- revocation, compromise, withdrawal, and algorithm-deprecation evidence with effective intervals;
- every evidence-renewal/archive-timestamp event linked append-only to its prior closure;
- original format specification, parser behavior, and adversarial/differential vectors;
- rule, reducer, validator, model, source, and dependency versions that affected meaning;
- organizational mandate, delegation, and scoped lawful-succession evidence;
- preservation events, fixity checks, migrations, errors, and custodial transfers;
- a runnable or reproducibly rebuildable verifier closure outside the primary service;
- content identities and digests for the production-target canonicalizer, verifier, reducer, and
  profile so a permissive test substitute cannot satisfy the drill; and
- evidence-obtainability information for public, competent-records-process, restricted, and
  unavailable paths.

INT-R7's controlling amendment requires real production-intended paths and disconnected restore
before the first live authority-bearing signature; a paper runbook or mocked value does not pass
(`int-r7-public-verification-lifecycle.md:1003-1011`;
`int-r7/lifecycle-migration-preservation.md:558-606`). OPS-R14 consumes that requirement and supplies
custody/recovery mechanics.

## 3. Replay rulebook

### RP-01 - preserve original bytes

No migration, correction, reissue, or archival renewal replaces the original signed bytes. Derived
views may be created, but each view points to the original, transformation evidence, tool/version,
and output digest. A transformation is not evidence that transformed bytes were originally signed.

**Verifier:** recompute retained object identity and digest against the signing input and every
control-event reference. Exact closure, missing bytes, digest mismatch, and unsupported historical
digest are distinct. An unsupported digest is not silently treated as a mismatch.

### RP-02 - append renewal evidence

Cryptographic or archival renewal produces a new evidence event covering the prior evidence closure.
It does not re-sign the historical statement as though a new key had issued it. Renewal is valid only
when completed before the old mechanism becomes insufficient for the claimed assurance, or when
other retained evidence independently proves the required historical fact.

RFC 4998 supplies an engineering pattern for archive-timestamp and hash-tree renewal. It does not
establish PolicyOS legal authority, trust policy, or public-proof lifecycle.

**Verifier:** walk every renewal link, recompute the covered prior closure, independently reconcile
time ordering against compromise/deprecation evidence, and report gaps. A later timestamp over
already unprovable evidence does not repair the gap.

### RP-03 - never restore private signing authority by accident

Recovery of encrypted key material does not authorize activation. Old or compromised private signing
keys remain disabled. Historical verification uses public evidence; new signing requires separately
authorized current key evidence under INT-R7. A backup import directly into a live signer fails.

**Verifier:** inspect recovered key inventory and activation state, recompute post-restore signature
key IDs, and require content-bound authorization evidence. Expected outcome is zero signatures from a
retired, compromised, or historically restored private key.

### RP-04 - preserve compromise intervals

Key compromise is an event with an evidenced or bounded interval, not a timeless Boolean. Records
before, during, and after it are evaluated separately. Historical issuer-side authenticity can remain
supported for an earlier record when signing-time and compromise evidence allow it; a present
revocation does not erase history. Records in an unresolved interval remain non-positive for the
affected dimension.

**Verifier:** replay fixtures immediately before, at, and after the earliest/latest plausible
compromise times. No global invalidation or global pass is accepted unless independently reconciled
evidence supports that scope.

### RP-05 - algorithm change

Before a signature, hash, timestamp, or canonicalization algorithm becomes unacceptable for the
intended horizon, preservation appends stronger evidence over the existing closure. The original
algorithm identifier and result remain. An isolated retained environment, emulator, formally
specified parser, or reproducible implementation may be used only when its identity is content-bound
to the production-target closure and tested against frozen vectors.

**Verifier:** in a clean disconnected environment, execute the retained verifier closure against
positive, negative, tamper, parser-differential, algorithm-renewal, and permissive-stub substitution
fixtures. If the competent closure cannot be operated or rebuilt, `DurablyVerifiableAt(t_v)` is
non-positive; the historical record is retained and unchanged.

### RP-06 - storage-format and interpretation change

Format migration preserves the original bitstream, format identification, representation
information, migration tool/version, input/output digests, errors, and semantic comparison. Where a
format carries signatures, timestamps, or external references, the plan states which properties
survive transformation and which require the original.

OAIS contributes preservation responsibility across technology, media, format, and knowledge-base
change. PREMIS contributes a vocabulary for objects, events, rights, and agents. Neither supplies a
PolicyOS schema, legal retention term, or appointed archive.

**Verifier:** render and interpret original and migrated forms with every retained parser/
canonicalizer identified by digest; compare canonical signing input and protected-query outcomes
against frozen vectors. If two syntactically successful implementations derive materially different
statements, the exact verdict is `historical_semantic_interpretation_not_established`; no newer parser
wins by assertion.

### RP-07 - rule and dependency change

Historical replay binds the exact rule, reducer, model, source capture, authority-dependency graph,
and time coordinate used for the original result. A current replay is a different query and must not
replace the historical answer. Processing time never enters a content hash where the Custody Time
Model forbids it.

**Verifier:** replay the historical prefix in the retained environment, compare specified semantic
outputs, then run the current query separately. Differences append and route to existing currentness/
correction owners; they never mutate the original record.

### RP-08 - organization change and lawful succession

A successor organization may preserve and serve predecessor evidence and append a custody/status
statement only where the exact succession instrument is content-bound, canonically admitted, and
independently reconciled against a non-producing authoritative record for authority, scope, timing,
notice, conditions, and effective time. It does not become the original issuer. Replay preserves
predecessor identity, original bytes, issuance-time evidence, and the separate succession proposition.

A split is query-specific and has two deterministic worlds. Where admitted instruments for `A` scope
`X` and `B` scope `Y` pass that reconciliation, established non-overlapping scopes may return
`scoped_succession_partial` while a disputed overlap remains `not_established`. Where the same scope
declarations or `admitted=true` markers are merely supplied, cannot be resolved to exact instrument
bytes, or are contradicted by the independent record, the exact verdict is
`succession_scope_not_established` and no current-custodian positive is permitted. A global pass
launders the overlap; a global failure erases valid independently reconciled scope. This follows the
INT-R7 succession rule (`int-r7/lifecycle-migration-preservation.md:630-650`) and is exercised by F-10,
F-14A, and F-14B.

**Verifier:** resolve declarations and instrument references to exact bytes and admission receipts;
independently reconcile authority, scope, timing, notice, conditions, and effective time against the
non-producing authoritative record; bind the subject/query scope; and require zero issuer
substitution. Leaving declarations and markers intact while falsifying the instrument premise must
return `succession_scope_not_established`.

### RP-09 - vanished source

A retained source capture can establish what evidence PolicyOS used historically, including source
identity, acquisition time, bytes, signature/publication evidence, and admission receipt. It does not
prove that the source remains current or obtainable today. Source disappearance may leave historical
replay possible while current authority is non-positive.

**Verifier:** disconnect the official source, restore retained captures, and run historical and
current queries. Historical attribution is recomputed; current official status remains non-positive
unless independently authenticated successor evidence is admitted; watched-dependency paths produce
the affected set.

### RP-10 - correction and supersession

A correction appends and preserves the erroneous/superseded record, applying S0-K08
(`stage0-custody-kernel-ratification.md:94-101`). OPS-R14 preserves every version, relation, public
head, and completion receipt. PAO-R36 alone defines correction meaning, notice, cache/subscriber
behavior, feed, and translation parity. Recovery that restores an old version must not render it as
current merely because its signature verifies.

**Verifier:** restore both versions while omitting PAO-R36 completion evidence. Historical versions
remain verifiable, but public current head/fan-out completion is not established and publication
mutation remains blocked.

RP-10 is necessary but not sufficient for PAO-R36 F11. The complete semantic-specification closure is
**`RP-10 + RC-01 + RC-07 + F-04 + F-09 + DE-07`**: event order, independently reconciled latest head,
incomplete-fan-out failure, authentic-old-snapshot rollback, and clause-by-clause drill evidence are
all required. This conjunction defines no PAO-R36 mechanism and claims no implementation.

### RP-11 - replay failure is an event

A replay attempt records its corpus, environment, executable/profile identities, query coordinate,
missing dependencies, errors, predicate-provenance labels, and dimension-by-dimension result. It
never deletes the source record or changes the earlier issuance event. A later successful replay
appends and links to the failed attempt.

**Verifier:** induce missing verifier, unsupported format, absent trust root, stale checkpoint,
conflicting/scoped succession, false independence, time rollback, parser differential, and test-stub
substitution. Each produces a retained failure receipt and zero historical rewrites.

## 4. Replay after specific changes

### 4.1 Signing key rotated normally

Retain both public credential histories and signing-time status. Verify the old record with old
public evidence. Use the new key only for new evidence or permitted archival renewal. Historical
attribution remains the old issuer/key; current signer is separate.

### 4.2 Signing key compromised

Stop new signing under the key, establish the best-supported interval, append status/log evidence,
and evaluate records against signing time. Never backdate a replacement signature. Unaffected
historical records may remain authentic; uncertain-interval records are non-positive; current
authority is separate.

### 4.3 Algorithm deprecated

Append stronger timestamp/evidence closure before the old mechanism loses adequate security. Retain
the old algorithm and vectors. The new evidence supports continued verification of the original, not
a new issuance.

### 4.4 Format migrated

Keep original and derivative with representation information and migration event. The original
signature remains bound to the original; the derivative is a provenance-bound rendering or
interpretation. Differential interpretation blocks a positive semantic replay.

### 4.5 Organization renamed, merged, split, or abolished

Preserve stable predecessor identity and append independently evidenced organizational events. A
rename may retain continuity only when the content-bound competent record is canonically admitted and
independently reconciled for the relevant scope. A split uses the two RP-08 worlds: independently
reconciled admitted instruments can preserve scoped non-overlap, while merely supplied declarations
or a falsified premise return `succession_scope_not_established`. Account control or data possession
is insufficient, and disputed overlap remains not established.

### 4.6 Storage provider or archive changed

Perform fixity census before and after transfer; preserve manifests, errors, custody statements, and
independently retained log/trust evidence. Referenced objects and closure elements must match; the new
custodian is never represented as original issuer.

## 5. Archival-grade duties selected

Apply OAIS-style duties as an operating discipline:

- define accepted information and representation information;
- verify ingest completeness and fixity;
- preserve originals and preservation metadata;
- monitor media, format, algorithm, software, and designated-community knowledge risks;
- append migrations/evidence renewals before failure;
- locate every closure element;
- provide controlled access and evidence-obtainability routes;
- test disaster recovery, common-mode independence, and scoped succession; and
- preserve provenance and rights evidence for every preservation action.

Reject `OAIS compliance` as a capability claim. This research neither certifies an archive nor
appoints a custodian. It transfers responsibility and lifecycle discipline, not a vendor architecture
or legal conclusion.

## 6. Current repository and standing

The key-rotation, replay, retained-artifact, and corruption-recovery runbooks provide useful
procedures (`docs/runbooks/key-rotation.md:1-113`; `replay-or-restore.md:1-128`;
`retained-artifact-recovery.md:1-180`; `artifact-corruption-recovery.md:1-119`). They do not establish
a 10–30 year signed-record preservation service, algorithm/format migration closure, scoped
succession replay, common-mode independence, anti-rollback, parser differential closure, real-path
anti-substitution, or a qualifying disconnected drill. INT-R7 explicitly leaves the live capability
unclaimed.

The complete replay capability is therefore `absent/unallocated`, with reusable procedures—not
`verification_missing` over an already wired chain.

**Research standing:** `accepted_narrow_scope`.  
**Capability standing:** `NO_GO`.  
**First-public-signature gate standing:** `NO_GO`.
