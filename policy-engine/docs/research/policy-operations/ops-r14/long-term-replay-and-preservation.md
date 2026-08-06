---
id: OPS-R14-LONG-TERM-REPLAY
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

# Long-term replay and preservation semantics

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

## 2. Preservation closure

The retained closure for a signed record includes, at minimum, the following semantic material. This
is a responsibility list, not a schema.

- the exact original bytes, detached or embedded signature, and stable record identity;
- the canonicalization and signing profile actually used;
- signer credential chain, trust roots, policy identifiers, and signing-time status evidence;
- trusted-time evidence and the time semantics needed to interpret it;
- public-log inclusion, consistency, checkpoint, and independent observation evidence where used;
- revocation, compromise, withdrawal, and algorithm-deprecation evidence with effective intervals;
- every evidence-renewal or archive-timestamp event, linked append-only to the prior closure;
- the original storage-format specification, parser behavior needed for interpretation, and
  adversarial test vectors;
- rule, reducer, validator, model, source, and dependency versions that affected meaning;
- organizational mandate, delegation, and lawful-succession evidence relevant to issuer attribution;
- preservation events, fixity checks, media/format migrations, errors, and custodial transfers;
- a runnable or reproducibly rebuildable verifier closure that can operate without the primary
  production service;
- evidence-obtainability information for public, competent-records-process, restricted, and
  unavailable paths.

INT-R7's controlling amendment already requires real production-intended paths and disconnected
restore before the first live authority-bearing signature; a paper runbook or mocked value does not
pass (`policy-engine/docs/research/policy-operations/int-r7-public-verification-lifecycle.md:1003-1011`;
`policy-engine/docs/research/policy-operations/int-r7/lifecycle-migration-preservation.md:558-606`).
OPS-R14 consumes that requirement and supplies the custody/recovery mechanics.

## 3. Replay rulebook

### RP-01 - preserve original bytes

No migration, correction, reissue, or archival renewal replaces the original signed bytes. Derived
views may be created, but each view points to the original, its transformation evidence, tool/version,
and output digest. A transformation is not evidence that the transformed bytes were originally
signed.

**Verifier:** compare retained object identity and digest against the signing input and all
control-event references. Expected verdicts identify exact closure, missing bytes, digest mismatch,
or unsupported historical digest. An unsupported digest is not silently treated as a mismatch.

### RP-02 - append renewal evidence

Cryptographic or archival renewal produces a new evidence event covering the prior evidence closure.
It does not re-sign the historical statement as though the new key had issued it. Renewal is valid
only when completed before the old mechanism becomes insufficient for the claimed assurance, or when
other retained evidence independently proves the required historical fact.

RFC 4998 supplies a transferable engineering pattern: archive timestamp and hash-tree renewal before
algorithm or certificate weakness. It does not establish PolicyOS's legal authority, trust policy, or
complete public-proof lifecycle. INT-R7 remains the controlling project input.

**Verifier:** walk every renewal link, verify the covered prior closure, check time ordering against
algorithm/credential compromise evidence, and report gaps. A later timestamp over already
unprovable evidence does not repair the gap.

### RP-03 - never restore private signing authority by accident

Recovery of encrypted key material does not authorize activation. Old or compromised private signing
keys remain disabled. Historical verification uses public evidence; new signing uses a separately
authorized current key under INT-R7's lifecycle. Recovery scripts that import a backup key directly
into a live signer fail this rule.

**Verifier:** inspect recovered key inventory, activation state, key identifiers used for post-restore
signatures, and authorization evidence. Expected outcome is zero signatures from a retired,
compromised, or historically restored private key.

### RP-04 - preserve compromise intervals

Key compromise is an event with an evidenced or bounded interval, not a timeless Boolean. Records
before, during, and after the interval are evaluated separately. Historical issuer-side authenticity
can remain supported for an earlier record when signing-time and compromise evidence allow it; a
present revocation does not automatically erase that history. Records in an unresolved interval
remain non-positive or not established for the affected dimension.

**Verifier:** replay boundary fixtures immediately before, at, and after the earliest and latest
plausible compromise times. No single global invalidation is accepted unless the evidence supports
that scope.

### RP-05 - algorithm change

Before a signature, hash, timestamp, or canonicalization algorithm becomes unacceptable for the
intended horizon, preservation appends stronger evidence over the existing closure. The original
algorithm identifier and result remain. If the old verifier no longer runs on current platforms, an
isolated retained environment, emulator, formally specified parser, or reproducible implementation
may be used, but it must be tested against frozen positive and adversarial vectors.

**Verifier:** in a clean disconnected environment, execute the retained verifier closure against
positive, negative, tamper, parser-differential, and algorithm-renewal fixtures. If no competent
verifier can be operated or rebuilt, `DurablyVerifiableAt(t_v)` is non-positive; the historical
record is not deleted or rewritten.

### RP-06 - storage-format change

Format migration preserves the original bitstream, format identification, representation
information, migration tool/version, input/output digests, errors, and semantic comparison. Where a
format carries signatures, embedded timestamps, or external references, the preservation plan must
show which properties survive transformation and which require the original.

OAIS contributes the responsibility to preserve information for a designated community across
technology, media, format, and knowledge-base change. PREMIS contributes a practical vocabulary for
objects, events, rights, and agents. Neither source supplies a PolicyOS schema, legal retention term,
or appointed archive.

**Verifier:** render and interpret both original and migrated representations against a frozen corpus;
compare required semantic propositions, embedded evidence, and linkage. A visually similar render is
not enough.

### RP-07 - rule and dependency change

Historical replay binds the exact rule, reducer, model, source capture, authority-dependency graph,
and time coordinate used for the original result. A current replay is a different query and must not
silently replace the historical answer. Processing time never enters a content hash where the
Custody Time Model forbids it.

**Verifier:** replay the historical event prefix in the retained environment and compare the
specified semantic outputs. Then run the current query separately. Differences are recorded and
routed to existing currentness/correction owners; they do not mutate the original record.

### RP-08 - organization change and lawful succession

A successor organization may preserve and serve predecessor evidence and append a custody or status
statement where competent succession evidence and effective time are established. It does not become
the original issuer. The replay preserves predecessor identity, original bytes, issuance-time
credentials, and the separate succession proposition. Conflicting plausible successors leave current
custody or authority not established until the canonical institutional process resolves them.

This follows INT-R7's controlling succession rule
(`policy-engine/docs/research/policy-operations/int-r7/lifecycle-migration-preservation.md:630-650`).

**Verifier:** test three cases: no successor evidence, one competent successor, and two conflicting
successors. Expected results preserve original attribution in all three and differ only in the
separate present custody/currentness finding.

### RP-09 - vanished source

The retained source capture can establish what evidence PolicyOS used historically, including source
identity, acquisition time, bytes, signature or publication evidence, and admission receipt. It does
not prove that the source remains current or obtainable today. If the official source vanishes,
historical replay may remain possible while current authority becomes non-positive or not
established.

**Verifier:** disconnect the official source, restore only retained captures, and run both historical
and current queries. Expected result: historical evidence remains attributable; currentness does not
silently pass; the watched-dependency and source-census paths produce an affected set.

### RP-10 - correction and supersession

A correction appends and preserves the erroneous/superseded record, applying S0-K08
(`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:94-101`). OPS-R14
preserves every version, relation, public head, and completion receipt. PAO-R36 alone defines the
correction meaning, notice, cache/subscriber behavior, feed, and translation parity. Recovery that
restores an old version must not render it as current merely because its signature verifies.

**Verifier:** restore a state containing both versions but omit PAO-R36 completion evidence. Expected
result: historical versions remain verifiable, while the public current head or fan-out completion is
not established and publication mutation remains blocked.

### RP-11 - replay failure is an event

A replay attempt records its corpus, environment, tools, query coordinate, missing dependencies,
errors, and dimension-by-dimension result. It never deletes the source record or changes the earlier
issuance event. A later successful replay appends another result and links to the failed attempt.

**Verifier:** induce missing verifier, unsupported format, absent trust root, stale checkpoint, and
conflicting succession evidence. Each produces a retained failure receipt and zero historical
rewrites.

## 4. Replay after specific changes

### 4.1 Signing key rotated normally

Retain both public credential histories and signing-time status. Verify the old record with the old
public evidence. Use the new key only for new evidence or permitted archival renewal. Expected
outcome: historical attribution remains the old issuer/key; current signer is separate.

### 4.2 Signing key compromised

Stop new signing under the key, establish the best supported compromise interval, append status and
public-log evidence, and evaluate records against signing time. Never backdate a replacement
signature. Expected outcome: unaffected historical records may remain historically authentic;
records in the uncertain interval are non-positive for the affected dimension; current authority is
separate.

### 4.3 Algorithm deprecated

Append stronger timestamp/evidence closure before the old mechanism loses adequate security. Retain
the old algorithm and test vectors. Expected outcome: the new evidence supports continued
verification of the original, not a new issuance.

### 4.4 Format migrated

Keep original and derivative. Preserve representation information and migration event. Expected
outcome: original signature remains bound only to the original; the derivative is a verifiable
rendering or interpretation with its own provenance.

### 4.5 Organization renamed, merged, split, or abolished

Preserve stable predecessor identity and append independently evidenced organizational events. A
simple rename can retain continuity if the competent record establishes it. A split requires scoped
succession evidence; account control or data possession is insufficient. Expected outcome: no
substitution of issuer identity and no automatic authority transfer.

### 4.6 Storage provider or archive changed

Perform fixity census before and after transfer; preserve transfer manifests, errors, custody
statements, and independently retained public-log/trust evidence. Expected outcome: all referenced
objects and closure elements match, and the new custodian is not represented as original issuer.

## 5. Archival-grade duties selected

Apply OAIS-style duties as an operating discipline:

- negotiate and document what information and representation information are accepted;
- verify ingest completeness and fixity;
- preserve originals and preservation metadata;
- monitor media, format, algorithm, software, and designated-community knowledge risks;
- plan and record migrations and evidence renewals before failure;
- maintain data management that can locate every closure element;
- provide controlled access and evidence-obtainability routes;
- test disaster recovery and succession from independent custody;
- preserve provenance and rights evidence for every preservation action.

Reject "OAIS compliance" as a capability claim. This research neither certifies an archive nor
appoints a custodian. The selected transfer is the responsibility model and lifecycle discipline,
not a vendor architecture or legal conclusion.

## 6. Current repository baseline

The inspected key-rotation runbook gives current operational procedures for rotation, overlap, and
emergency revocation (`policy-engine/docs/runbooks/key-rotation.md:1-113`). The replay and artifact
recovery runbooks provide useful mechanisms (`policy-engine/docs/runbooks/replay-or-restore.md:1-128`;
`policy-engine/docs/runbooks/retained-artifact-recovery.md:1-180`; `policy-engine/docs/runbooks/artifact-corruption-recovery.md:1-119`). None of those files,
alone or together, establishes a 10-30 year signed-record preservation service, algorithm/format
migration closure, organizational succession replay, independent public-log anti-rollback, or a
qualifying disconnected drill. INT-R7 explicitly says the live capability remains unclaimed. The
repository status for this complete replay chain is therefore `absent/unallocated`, with reusable
implemented procedures, not `verification_missing` over an already wired end-to-end chain.
