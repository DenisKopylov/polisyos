# Canonical candidate vocabulary crosswalk

The versioned [machine reference](canonical-vocabulary-crosswalk.v1.json) covers movement diagnosis,
E/X/V/C coordinates, the eight ceiling dimensions, proposed and delivered acquisition process states,
INT-R6's binding semantic identifiers, and INT-R5's local results, lifecycle, cure results and complete
qualified candidate-reason vocabulary. It preserves source identities beside the existing
custody-status adjunct. It appoints no institutional or lifecycle owner and establishes no
institutional authority, diagnosis, legal equivalence, authoritative closure or currentness, or new
Atlas status.

Owner: team-architecture
Source of truth: `docs/reference/canonical-vocabulary-crosswalk.v1.json`, `tools/quality/validation/check_canonical_vocabulary_crosswalk.py`, `src/polisyos/runtime/quality/vocabulary_crosswalk.py`, `src/polisyos/runtime/quality/adaptation_transition.py`, and the [GY-VC1 decision at its source snapshot](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/docs/superpowers/specs/2026-09-10-gy-vc1-decision.md).
Snapshot and evidence level: implementation sources were inspected at `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`. A later resolver edit caused one bound-source digest to drift while leaving the acquisition-state vocabulary unchanged. The canonical generator refreshed that digest, and `--check` passed at source snapshot `78a7b7b9cdab2b16e9d4ecd56c15bece38728f3b`; a changed alternate `entries[0].source_term` was rejected. All 14 source-file entries match the refreshed artifact's declared hashing method at that snapshot. The third-pass maintenance report records the commands, artifact digest and deciding-output bindings. This verifies the crosswalk against its declared inputs and recorded corruption probe; it does not establish full runtime behavior, an appointed lifecycle owner or E02 completion.

The source/target and owner decisions, source boundaries, production caller and falsifiers are in
[the VC1 decision at the source snapshot](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/docs/superpowers/specs/2026-09-10-gy-vc1-decision.md). The JSON is the sole crosswalk
artifact; this page explains its use rather than repeating its rows.

`source_sha256` hashes the UTF-8 encoding of text read with UTF-8 decoding and universal-newline
normalization; it is not a general raw-byte digest (the current LF source files have matching raw
byte digests). `vocabularies` names every source denominator and the complete member set. `entries`
preserve each source identity alongside the existing custody status; they appoint no lifecycle owner
and establish no authoritative closure or currentness.
`target_statuses` is derived from the actual `KPIControlStateSnapshot.status` Literal. A transport
passes through an already produced value; a vocabulary term cannot decide lifecycle status. The
source meaning, restrictions and remedy remain part of the result. In particular, a candidate
`pre_action_valid` term does not become an authorization, and `reentry_closed` is not publication.

Every loss is classified by `loss_policy`: only dropping a display label while retaining the exact
source identity is tolerable. Losing a source ID, namespace/version, owner, purpose, provenance,
time scope, blocking contributor, negative-state remedy, permission/prohibition, claim/version scope,
partial-order relation, lifecycle owner or source qualifier is blocking. An unknown dimension also
refuses. The runtime projector enforces this independently of the table's declared classifications.

The admitted movement channel accepts only `SMDV-1@1` and its complete canonical class definition.
A second registration fails even under an arbitrary name with no lexical similarity. CR2's real
request intake calls this mechanism. This does not claim to semantically classify arbitrary dead
code or prose elsewhere in the repository. SMDV identifies movement sources; S13 identifies accountable
destinations. They are not interchangeable cause vocabularies. A lookup is not a diagnosis producer.

Relation claim strength conditionally uses `maximum_claim_strength` and the supplied strength partial
order. Capacity stages conditionally use `maximum_commitment_stage`, its supplied partial order and
the separate load constraint. Those comparisons require domain-defined and independently justified
nodes/edges. Estimand binding strength, legal/normative/write operations and assurance levels retain
explicit missing owner/registered-term requirements. The artifact details precisely what each owner
must supply; it does not invent terms or appoint an institution.

The institutional reconciliation compares predicted names with delivered contracts. AQ1's runtime,
CB1's comprehension instrument and ML1's assurance packets exist under their delivered vocabulary.
ML1 remains finite candidate comparison. Its RTL source support does not establish co-authentic legal
authority, and none of these mechanisms supplies an appointed institutional holder.

Run the deciding checker from `policy-engine/`:

```sh
PYTHONPATH=src .venv/bin/python -m tools.quality.validation.check_canonical_vocabulary_crosswalk --check
```

An alternate artifact can be supplied with `--artifact PATH`; a corrupted semantic field must return
nonzero. The checker reconstructs the source sets, checks runtime enum/type membership, independently
counts the emitted identities, executes projections for every source row and target-owner value,
and runs removal-sensitive anti-fork and blocking-loss probes. `--write` regenerates the reference
for a reviewed revision; it cannot make a runtime/source mismatch pass.

Atlas rendering is deferred to DS12. Live monitoring/learning integration is owned by later GY-O1
and GY-O3; GY-AS3 separately owns its real posterior-consumer assertion. The immediate projection
consumer is the non-test architecture checker; the immediate movement consumer is CR2. The absence
of legal/assurance/estimand semantic producers remains a limitation, never a positive mapping.
