---
title: INT-R7 — Lifecycle, Algorithm Migration, and 10–30 Year Preservation Profile
research_id: INT-R7
status: delivered
result_standing: GO_WITH_REVISIONS
repository: https://github.com/DenisKopylov/polisyos
pinned_repository_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
inspection_date: 2026-08-04
amended_after_audit: research/int-r7-independent-audit@54e8f41d790cb257a616c5bb5f96d996fbe3e9db
research_only: true
int_r8_seam: proof_only
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization, or API contract
  - canonical owner appointment
  - authority grant
  - capability claim
  - benchmark passage
  - legal compliance or institutional competence conclusion
  - permission to publish a governed result
  - automatic amendment of any plan or system-design decision
---

# Lifecycle, migration, and preservation

## 1. Governing distinction

The lifecycle has three related but non-identical objects:

1. **signing authority/key lifecycle** — whether a credential/key may create a new public proof;
2. **record authority lifecycle** — whether a historically issued record is current, stale, withdrawn, invalidated or superseded under GY-N12 and the existing authority lattice;
3. **verification-evidence lifecycle** — whether the cryptographic and institutional evidence needed to verify the old record remains usable after keys, certificates, formats and algorithms change.

Conflating these creates the two central failures:

- revoking a key erases every historically valid signature; or
- preserving a mathematically valid signature makes a withdrawn record look current.

The state machines below are semantic state machines. They do not authorize a database enum or a second canonical status owner.

## 2. Key/credential lifecycle state machine

### 2.1 States

| State | Meaning | May create new public signatures? | May validate historical signatures? |
| --- | --- | --- | --- |
| `generated_candidate` | key/share set created but not authorized, certified, logged or activated | no | no |
| `authorized_staged` | authority, credential and custody controls established; activation time not reached | no | no, except ceremony self-tests |
| `active` | authorized for named claim class, boundary, jurisdiction and interval | yes | yes |
| `overlap_next` | current and successor keys both available for controlled transition; statement identifies actual key/policy | yes, according to transition policy | yes |
| `retired_new_signing_closed` | normal rotation ended authorization for new records; no compromise asserted | no | yes for records within authorized interval |
| `archive_validation_only` | retained solely to verify historical evidence; private signing material destroyed or inaccessible by policy | no | yes |
| `suspected_compromise` | credible signal exists; new signing frozen pending adjudication | no | conditional; temporal result may be indeterminate |
| `suspended` | authority use disabled by control decision, without final compromise/revocation conclusion | no | historical validation continues with visible suspension context |
| `revoked_prospective` | authorization ended at an authenticated effective time, no claim that earlier signatures were forged | no | yes before effective cutoff if signing-time evidence passes |
| `compromised_known_cutoff` | compromise established with earliest trustworthy cutoff | no | before cutoff may pass; after cutoff fails |
| `compromised_uncertain_interval` | compromise window overlaps possible issuance time | no | records in overlap are temporally indeterminate |
| `algorithm_deprecated_new_signing` | suite forbidden for new issuance but still acceptable for historical validation/renewal | no under old suite | yes subject to policy |
| `algorithm_validation_expired` | suite no longer sufficient to support historical validation without timely archival chain | no | only through timely preserved renewal; otherwise evidence insufficient |
| `destroyed_with_evidence` | private key/shares destroyed through an auditable event after retirement | no | public verification material remains |

These states are control/evidence concepts. An implementation may represent compromise and algorithm status as orthogonal dimensions rather than one enum.

### 2.2 Normal transition path

```text
generated_candidate
  -> authorized_staged
  -> active
  -> overlap_next
  -> retired_new_signing_closed
  -> archive_validation_only
  -> destroyed_with_evidence
```

Preconditions for `active`:

- key generation/share ceremony evidence completed;
- institutional authority and credential path active for exact claim class;
- custody controls and signer authorization policy active;
- public key/credential and policy checkpoint independently published;
- trusted timestamp, transparency and status-evidence dependencies ready;
- offline trust snapshot can validate the key;
- recovery/compromise exercise passed for the named profile version;
- no first public signature precedes the preservation profile.

### 2.3 Compromise transition path

```text
active|overlap_next
  -> suspected_compromise
  -> suspended
  -> {false_alarm_return_to_active,
      revoked_prospective,
      compromised_known_cutoff,
      compromised_uncertain_interval}
```

Required event semantics:

- detection/notice time;
- earliest possible compromise time or interval;
- adjudication/evidence basis;
- affected credential/key IDs, roles, claim classes and jurisdictions;
- freeze time for new signing;
- authenticated revocation/status publication;
- transparency event and witnessed checkpoint;
- affected-record query/result;
- GY-N12 status impacts;
- successor key/profile activation;
- preservation of all original records and evidence.

The profile does not specify operational incident-response mechanics; those are an OPS-R14 dependency.

### 2.4 Rotation is not revocation

Normal rotation must not mark a key compromised. `retired_new_signing_closed` means:

- no new signatures accepted after the retirement cutoff;
- signatures trusted to predate the cutoff remain historically valid if all other predicates pass;
- the old public key, credential chain, status material and policy remain preserved;
- current record authority is evaluated separately.

The current `rotation.py` has active/next/retired/revoked operational sets but no public-record temporal proof (`core/security/rotation.py:1-237 @ 02c5b8d`). It should be extended as a canonical control owner, not treated as already satisfying these semantics.

## 3. Record/proof lifecycle state machine

### 3.1 States

| State | Meaning | Public verification outcome |
| --- | --- | --- |
| `draft_candidate` | not sealed, signed or public | no public proof |
| `sealed_prospective` | required commitments fixed before governed outcome; not yet issued | not publicly authoritative |
| `signed_pending_time_status` | signature exists but trusted time/signing-time status incomplete | verification incomplete; must not publish current |
| `time_status_established_pending_log` | issuance-time proof passes; common public history not yet established | not publishable as verified current |
| `logged_pending_witness` | included in one log view; witness/quorum not yet satisfied | included-in-view only |
| `published_current` | historical and current predicates pass as of authenticated status snapshot | verified current as of timestamp |
| `challenged_review_required` | challenge appended; current authority treatment comes from canonical owner | visible challenge/review state; no silent mutation |
| `stale_revalidation_required` | GY-N12 revision trigger crossed | historically authentic; not current pending revalidation |
| `withdrawn_but_verifiable` | current authority explicitly withdrawn; original remains reproducible | authentic historical; withdrawn |
| `superseded_but_verifiable` | a successor record/epoch replaces current authority | authentic historical; superseded, with successor link |
| `invalidated_basis_or_support` | declared basis moved or support lost; old computation remains historical | authentic historical issuance may remain, current authority invalidated |
| `temporal_validity_indeterminate` | signature math passes but trusted issuance time/compromise relation cannot be established | incomplete/indeterminate, never current |
| `content_or_signature_invalid` | commitment/signature/canonicalization fails | not verified/tampered |
| `archive_only` | active service retired; complete proof retained for historical verification | historical outcome according to retained status cutoff |
| `preservation_evidence_insufficient` | bytes survive but algorithm/status/migration closure is broken | historical authority not established |

### 3.2 Issuance path

```text
draft_candidate
  -> sealed_prospective
  -> signed_pending_time_status
  -> time_status_established_pending_log
  -> logged_pending_witness
  -> published_current
```

Fail-closed rules:

- a signature without trusted time/status does not skip to publication;
- a timestamp without log inclusion does not prove public availability;
- inclusion without independent checkpoint evidence does not prove common view;
- all proof predicates may pass while GY-N12 currentness fails;
- INT-R8 projection failure blocks the public projection even if cryptography passes;
- a `delta` without its signed basis cannot enter the issuance path;
- a procedural statement without bound chronology cannot enter the issuance path.

### 3.3 Append-only correction and reissue

```text
published_current
  -> challenged_review_required
  -> {annotation_only_return_current,
      stale_revalidation_required,
      withdrawn_but_verifiable,
      invalidated_basis_or_support}
  -> [new GY-N12 epoch]
  -> sealed_prospective(successor)
  -> ...
  -> published_current(successor)

old record -> superseded_but_verifiable
```

Required invariants:

- old bytes, signature, timestamp, log leaf and original status evidence are never rewritten;
- challenge, adjudication, invalidation, withdrawal and successor events are appended and logged;
- the successor binds its own epoch, authority, basis and proof;
- old record verification can return both “validly issued then” and “not current now”;
- the successor relation cannot imply the old record was always false;
- widening the obligation set under `INT-K01`/`INT-K02` changes the declared basis in a new epoch; it does not rewrite the earlier arithmetic;
- no status transition creates a second lattice; GY-N12/current authority owners remain canonical.

### 3.4 Authority succession

When an agency is reorganized, merged or abolished:

- predecessor signatures remain attributed to the predecessor authority and issuance interval;
- a successor may append a custody/status/succession statement under its own credential;
- the succession statement identifies the legal/institutional authority evidence and effective interval;
- the successor cannot silently replace trust anchors or reinterpret the predecessor claim;
- conflicting succession claims yield `authority_succession_disputed`, not an inferred winner;
- independent archive/witness copies remain verifiable if the successor infrastructure is unavailable.

The profile does not determine which institution legally succeeds another.

## 4. Algorithm and format migration policy

## 4.1 Policy object semantics

An algorithm policy must be versioned, authenticated, preserved and independently retrievable. For each primitive it states:

- primitive and parameter identity;
- use purpose: signature, digest, timestamp, certificate, log, witness, preservation;
- allowed-for-new-issuance interval;
- allowed-for-historical-verification interval;
- renewal deadline or trigger;
- deprecation/prohibition source;
- accepted validation implementations/test vectors;
- transition target class, without requiring one vendor;
- emergency action if evidence emerges earlier than planned;
- relationship to post-quantum/hybrid policy when applicable.

Policy updates are append-only and logged. A verifier uses the policy applicable to the event being validated plus current archival-evidence rules; it does not apply today's new-signing prohibition retroactively as proof that a signature was never valid.

## 4.2 Migration triggers

At least:

- standards body or competent policy owner changes status;
- practical cryptanalytic advance;
- certificate/timestamp/log/witness suite approaches validation horizon;
- canonicalization/format implementation becomes unsupported;
- trust service ends operation;
- verifier dependency cannot be rebuilt;
- hash strength no longer meets preservation horizon;
- post-quantum transition policy reaches a milestone;
- recovery drill cannot validate a representative sample;
- authority/succession policy changes;
- GY-N12 revision changes the semantic interpretation needed for currentness.

## 4.3 Preservation re-anchoring operation

A preservation event must:

1. retrieve the original record and complete prior proof closure;
2. validate every prior link under the policy applicable before the old primitive's loss of trust;
3. record the validation result, verifier/spec version and evidence cutoff;
4. commit to the complete prior evidence object, not only the latest signature;
5. where hash migration occurs, bind both old and new digests over the same preserved object;
6. obtain new trusted time under an acceptable suite;
7. append the preservation event to transparency history and obtain independent checkpoint evidence;
8. preserve original and renewed proof side by side;
9. state that the new signature is a preservation attestation, not the original issuing authority's signature;
10. update offline evidence closures and recovery fixtures.

This is the core transfer from RFC 4998 and long-term ETSI profiles.

## 4.4 Hash migration

A safe hash transition preserves:

- original bytes and old digest;
- validation that old digest still identified the original when migration occurred;
- new digest over the same bytes/evidence object;
- signed/timestamped binding between old digest, new digest and migration event;
- transparency/witness evidence for that migration;
- algorithm-policy reason and time.

A new digest computed after the old hash is already collision-broken cannot prove that archived bytes are the original unless independent earlier evidence resolves the ambiguity.

## 4.5 Signature/credential migration

Do not “re-sign the old record” and replace the original sidecar. Instead:

- keep original signature/credential/status evidence;
- add preservation evidence covering it;
- if a current authority makes a new substantive statement, issue a successor record under a new epoch;
- if a successor merely preserves/custodies predecessor evidence, label that proposition exactly;
- retain trust anchor and certificate-policy documentation needed for original-time validation.

## 4.6 Format migration

The archive must distinguish:

- **bit-preserving copy** — identical original bytes;
- **representation migration** — new human-readable/renderable form;
- **semantic projection** — governed transformation subject to INT-R8;
- **evidence-container migration** — new carrier for the same proof closure.

A migrated rendering does not inherit an embedded signature automatically. The proof binds either the original bytes or a verified transformation relation. The original remains retained whenever permitted by retention/legal-hold policy.

## 4.7 Post-quantum transition

NIST FIPS 204 (ML-DSA) and FIPS 205 (SLH-DSA) provide standardized post-quantum signature primitives; migration planning is active, while the exact public-sector interoperability and archival profiles continue to evolve. The profile therefore requires agility and permits hybrid/dual evidence, but does not freeze a post-quantum algorithm now.

A transition may:

- add a post-quantum preservation attestation to existing evidence;
- use a hybrid issuance profile during an authorized overlap;
- preserve both classical and post-quantum validation material;
- avoid claiming that a post-quantum re-sign retroactively proves an original classical signature if the classical primitive had already failed.

## 5. Minimum 10–30 year preservation profile before first signature

The preservation profile is a **precondition**, not a later enhancement. At first issuance the following must already have named owner roles, retention rules and tested recovery paths.

## 5.1 Retained record material

- original canonical semantic statement bytes;
- original public record/projection bytes or deterministic reconstruction inputs;
- original human-readable rendering(s), accessibility representation and locale identity;
- canonicalization/commitment specification and test vectors;
- INT-R8 retained-claim commitment/projection proof outputs;
- immutable record locator and content commitments;
- all original signatures and signer credential material required for validation;
- explicit claim class, audience, jurisdiction, authority boundary, epoch and basis.

## 5.2 Retained signing-time verification material

- signer certificate/credential chain and trust anchors;
- certificate/credential policy and validation rules/version;
- CRL/OCSP or equivalent status evidence applicable at trusted issuance time;
- authenticated revocation/compromise history and effective times/intervals;
- trusted timestamp token, timestamp credential/status/policy;
- threshold/co-authorization evidence where required;
- institutional mandate/role/term evidence sufficient for technical authority binding;
- succession mappings and their evidence as later appended.

NARA guidance is especially direct that the Trust Documentation Set should accompany records for their retention period and that reliance on third-party retention requires enforceable arrangements. The profile adopts the evidence-retention principle without declaring US legal applicability elsewhere.

## 5.3 Retained transparency material

- leaf commitment and inclusion proof;
- log identity and policy;
- signed checkpoint/tree head;
- consistency proofs or enough retained checkpoints to reconstruct the chain;
- independent witness signatures/cross-publication evidence;
- monitor observations and equivocation evidence, if any;
- append-only withdrawal, challenge, supersession and migration events;
- privacy-preserving addressing/rand values needed to verify commitments.

## 5.4 Retained epoch/currentness material

- GY-N12 epoch identity and semantic references;
- closure cutoff and revision triggers relevant to the claim;
- status snapshots and authenticated `as_of` times;
- challenge/adjudication/invalidation/reissue/supersession/withdrawal events;
- source validity events that affect authority;
- successor record links;
- OpenWorldRisk/revalidation outcomes where applicable.

The archive preserves history; the canonical GY-N12/current-authority owner determines live status.

## 5.5 Retained preservation metadata

Use OAIS/PREMIS-class semantics, regardless of final implementation:

- intellectual/record object identity;
- files/bitstreams and fixity;
- preservation events with time, agent role, input/output, outcome and evidence;
- rights/retention/legal-hold constraints;
- custody transfers;
- format identification and migration events;
- verifier and algorithm-policy versions;
- evidence-renewal lineage;
- recovery/drill results;
- anomalies and unresolved gaps.

No claim is made that adopting OAIS or PREMIS alone ensures a trustworthy archive.

## 5.6 Retained verifier closure

- normative semantic profile and algorithm policy versions;
- source code or independently inspectable verifier implementation;
- build/dependency manifests and reproducible-build evidence where available;
- supported platform/environment description;
- known-good and known-bad test vectors;
- frozen falsifier fixtures and expected outcomes;
- canonicalization libraries/specification;
- trust snapshot update/verification mechanism;
- machine-readable reason-code documentation;
- human-readable verification report format.

A preserved executable without its validation policy and trust inputs is insufficient.

## 5.7 Custody-owner role

A designated **Public Verification Custody Owner role** must be institutionally assigned before issuance. This research does not appoint a person, team, agency or vendor. The role's minimum accountabilities are:

- preserve original and renewed proof closures;
- maintain algorithm/format migration watch and execute authorized renewals;
- maintain authenticated trust/status/checkpoint snapshots;
- coordinate succession and custody transfer evidence;
- ensure legal-hold/retention constraints are applied by the competent owner;
- run and publish bounded recovery-drill evidence;
- ensure no preservation event is represented as original issuance;
- escalate unresolved breaks and freeze current verification where needed;
- maintain citizen and machine verifier availability independent of one presentation server.

The role does not acquire policy authority merely by preserving evidence.

## 5.8 Institutional commitments required

Before first signature, authorized governance must commit to:

- retention horizon by record class, including permanent/extended cases;
- funding and succession for verification custody;
- authority to preserve and migrate evidence;
- trust-service/log/witness continuity or exit arrangements;
- format and algorithm watch process;
- compromise/revocation publication obligations;
- cross-agency/archive custody transfer process;
- public access and accessibility posture;
- freedom-of-information/disclosure interaction without exposing restricted evidence;
- legal hold override and destruction controls, supplied through OPS-R14/competent records governance;
- periodic independent drill/review.

Without those commitments, cryptographic design alone cannot meet the 30-year requirement.

## 6. Recovery drill specification

This is an executable drill contract at the outcome level. OPS-R14 must supply the storage/restore/resilience mechanics; INT-R7 does not invent them.

### 6.1 Drill objective

Demonstrate that a verifier isolated from live PolicyOS, live signer infrastructure, live IdP, live CA/OCSP/TSA and the primary transparency endpoint can reconstruct the bounded verification outcomes from preserved evidence.

### 6.2 Sample selection

The drill sample must include at least one record from every available class:

- current record under active key;
- historical record under normally retired key;
- record signed before a known prospective revocation;
- record in a compromise-uncertainty interval;
- withdrawn-but-verifiable record;
- superseded/new-epoch pair;
- stale/revalidation-required record;
- record with at least one algorithm/hash preservation renewal;
- negative/refusal procedural outcome;
- `delta` record, if any are authorized, with declared basis;
- record whose public projection exercises the INT-R8 proof;
- deliberately malformed/tampered fixture.

Sampling method, denominator and random seed or selection rationale must be preserved. No claim is made beyond the sampled classes.

### 6.3 Isolation conditions

- deny network access to PolicyOS services;
- deny live credential/status/timestamp/log endpoints;
- use a clean verifier environment built from preserved material;
- restore from the custody substrate through OPS-R14's authorized recovery path;
- independently obtain or use preserved witness checkpoints rather than the primary log;
- record every dependency unexpectedly contacted.

A drill that silently falls back to a live service does not prove offline verification.

### 6.4 Required steps

1. restore original bytes and proof closure;
2. validate fixity and preservation event chain;
3. reproduce canonical statement commitment;
4. validate original signature and credential path at trusted issuance time;
5. validate status/revocation relation to issuance time;
6. validate trusted timestamp;
7. validate transparency inclusion and consistency;
8. validate independent common-view evidence;
9. validate authority role/jurisdiction/audience binding;
10. validate GY-N12 epoch and currentness as of the preserved snapshot;
11. validate INT-R8 projection proof;
12. validate each preservation renewal and old/new digest link;
13. render the bounded citizen and machine outcomes;
14. confirm a withdrawn record reports historical authenticity and current=false;
15. confirm a stale snapshot never reports current now;
16. confirm tampered and package-self-key-substitution fixtures fail;
17. produce a signed, logged drill report with limitations and exact environment.

### 6.5 Success criteria

- every sampled good record yields its predeclared bounded outcome;
- every negative fixture yields its exact failure code;
- zero undisclosed network dependencies;
- originals remain byte-identical;
- no preservation signer is labeled original authority;
- currentness never exceeds the status snapshot cutoff;
- every missing item is a typed failure, not a warning-only pass;
- full evidence needed to reproduce the drill is retained;
- result is reported under `S0-K16`: named sample, implementation, revision, environment and verifier only.

### 6.6 Failure disposition

A failed drill triggers:

- freeze on new public issuance where the failed property is material;
- typed impact analysis over affected records;
- no deletion/rewrite of prior records;
- OPS-R14 incident/recovery handling;
- GY-N12 revalidation/status impact where applicable;
- remediation and rerun under a new drill event;
- public limitation where verification availability/currentness is affected.

The cadence is an institutional policy decision. The minimum research recommendation is a recurring drill and an additional drill before/after major algorithm, format, trust-service, custody or organizational succession transitions.

## 7. Dependency on OPS-R14

INT-R7 requires OPS-R14 to provide outcomes for:

- durable storage/recovery of every retained proof class;
- custody-class recovery objectives and evidence;
- expiring authority and key/status dependency monitoring;
- long-term replay of signed records and proof closures;
- legal-hold override and retention enforcement;
- immutable/tamper-evident recovery event evidence;
- successor custody transfer;
- recovery under compromised primary infrastructure;
- drills that prove restoration without inventing data.

INT-R7 does not specify replication topology, RPO/RTO numbers, backup product, cloud, archive vendor, HSM, key escrow or legal-hold mechanism.

## 8. Dependency on GY-N12

INT-R7 requires GY-N12 to provide:

- stable epoch identity and semantic revision references;
- canonical `current_valid`, `stale`, `revalidation_required` and OpenWorldRisk outcomes;
- append-only challenge/invalidation/new-epoch/reissue/supersession/withdrawal relations;
- current-head/status projection with authenticated `as_of`;
- propagation of evidence/source invalidity;
- no silent mutation of closed cases.

INT-R7 signs and verifies those outputs; it does not define or own them.

## 9. Hard failure boundaries

- **No timely re-anchor:** later re-signing cannot restore lost historical authenticity.
- **No trusted issuance time:** self-declared timestamps cannot distinguish pre/post compromise.
- **No signing-time status material:** live “not revoked” years later cannot prove status then.
- **No independent checkpoint:** log inclusion does not establish common view.
- **No succession evidence:** current custodian cannot inherit authority by possession.
- **No INT-R8 proof:** cryptography cannot establish retained-content safety.
- **No GY-N12 current status:** historical proof cannot become current authority.
- **No recovery drill:** preservation readiness is not established.
- **No institutional owner/funding:** a 30-year technical profile is not credible.

## 10. Preservation profile conclusion

The minimum profile is feasible only as a continuing institutional service, not as one signature operation. Its defining act is not choosing Ed25519, PAdES or a blockchain. It is committing before issuance to preserve the entire validation closure, publish append-only status/common-view evidence, renew it before cryptographic degradation, and keep historical authenticity separate from current authority through organizational succession.

## 11. Post-audit preservation and recovery amendment

This section supersedes the aggregate historical-verification wording in §§3, 5, 6, 9 and 10 wherever it lets a present projection, witness or archive failure rewrite issuer-side issuance. It executes `R1`, `R10`, `R11`, `R12`, `R18`, and `R19`.

### 11.1 Preservation affects current proof, not past occurrence

The lifecycle reports these dimensions separately:

- `IssuerIssuanceAuthentic` — issuer-side issuance evidence only;
- `ProjectionFaithful` — INT-R8 projection evidence;
- `PublicHistoryEstablished` — log/common-view evidence;
- `DurablyVerifiableAt(t_v)` — preservation and verifier closure at the evaluation time;
- `CurrentAuthorityAsOf(t_q)` — GY-N12 currentness under a selected latest-applicable snapshot.

A broken preservation chain returns `DurablyVerifiableAt(t_v) = not_established` or `contradicted` according to evidence. It does not assert that an earlier issuer act never occurred. Original issuance evidence, its loss and the resulting inability to prove it are distinct historical facts.

The state labels in §3 remain semantic descriptions. A public report must expose the five dimensions rather than infer one Boolean from a lifecycle label.

### 11.2 Two-phase drill gate

The phrase “before first signature” means before the first **live public authority-bearing signature**, not before candidate work, test keys or ceremonial fixtures.

#### Phase A — pre-live disconnected ceremonial drill

Before live issuance, run a representative **non-authoritative/ceremonial corpus** through the real paths intended for production:

- real canonical statement/profile dispatch;
- real verifier and independently authenticated trust inputs;
- signing-time status and trusted-time fixtures;
- real log/inclusion/consistency and independently supplied witness/checkpoint fixtures;
- INT-R8 projection/currentness fixtures explicitly labelled hypothetical where dependencies are unaudited or planned;
- preservation event generation and retained verifier closure;
- disconnected restore into a clean environment;
- exact positive, negative, withdrawn, superseded, compromise-interval, algorithm-renewal and tamper outcomes.

The corpus carries no external authority and cannot be shown as a public governed record. Passing Phase A proves only the named implementation, environment and fixtures under `S0-K16`.

A paper runbook, diagram, tabletop discussion or mocked `verified=true` value does not satisfy Phase A.

#### Phase B — bounded first-live-record drill

After the first live record is issued—but before claiming fleet-wide readiness—restore and verify that exact record from the retained closure in a clean, disconnected environment. Report the five dimensions, snapshot selection, evidence obtainability and all limitations. This drill is bounded to the first live record and does not retroactively authorize its issuance; Phase A and all other preconditions must already have passed.

### 11.3 Authentic-snapshot anti-rollback outcomes

Recovery must distinguish an authentic snapshot from the latest applicable authentic snapshot. The restored verifier reports:

- `latest_established_under_policy` when independently authenticated monotonic evidence establishes the applicable head;
- `supplied_snapshot_only` when authenticity passes but no-later-snapshot suppression cannot be excluded;
- `rollback_detected` when a later authenticated applicable head is evidenced; or
- `not_established` when selection cannot be proved.

Current authority cannot be reported from `supplied_snapshot_only`, `rollback_detected` or `not_established`. An authentic old snapshot may be used only for an explicitly historical query.

Required anti-rollback fixtures include:

- restore an older correctly signed status snapshot while retaining a later witnessed head;
- remove the later head from the restored package but retain it in an independent custody domain;
- present a recovered catalog whose internal signatures validate but whose monotonic position is stale;
- restore conflicting checkpoint/status heads and require non-positive currentness.

### 11.4 Compromised-primary and cross-custody recovery

The recovery path must operate when the primary storage, publication server, trust snapshot distribution point or preservation operator is unavailable or suspected compromised.

A successful cross-custody drill must:

1. begin from an independently governed retained copy or legal-deposit/archival custody domain;
2. authenticate its trust, status, checkpoint and policy roots independently of the compromised primary;
3. compare the restored head against independently retained witness/checkpoint observations;
4. detect deletion, rollback, replacement and unlogged renewal;
5. preserve original issuer attribution and label the recovering/successor institution only as custodian or preservation signer;
6. keep current authority non-positive until the canonical currentness interface is authenticated;
7. record divergence, unresolved evidence and affected-record scope;
8. avoid reactivating old private signing authority or silently trusting recovered secret material;
9. expose `EvidenceObtainability` for citizens and monitors after the primary channel is lost.

Recovery from the same compromised control plane without an independent trust/checkpoint path is not evidence of recovery correctness.

### 11.5 Positive lawful succession

A lawful successor may preserve and serve predecessor proof closures and append its own custody/status statement when competent succession evidence and effective time are established. The result must preserve:

- predecessor as original issuer;
- successor as current custodian/preservation signer only;
- original bytes, signature and issuance-time evidence;
- separately authenticated succession proposition;
- canonical current/superseded status;
- conflicting-claim outcome when two valid-looking succession statements cannot be adjudicated.

The suite includes both the substitution failure and a positive lawful-succession fixture.

### 11.6 Corrected NARA use

The present-tense NARA sentence in §5.2 is superseded. `US-01` is officially superseded and may be cited only as historical precedent for a “Trust Documentation Set.” Current U.S. records-management support must be re-established from current guidance, including current-status-limited `US-03`, before any implementation or legal conclusion. The preservation profile remains an INT-R7 design conclusion supported by the broader technical and archival corpus; it is not a current NARA mandate.

### 11.7 Evidence obtainability and lawful restriction

Long-term custody must preserve not only bytes but a route by which a citizen, journalist, court, archive or other authorized verifier can obtain the permitted evidence. Each drill records:

- `public_available`;
- `records_process_available`;
- `competently_restricted`; or
- `not_established`.

A lawful restriction identifies the competent decision, scope, review route and exact effect on verification. It does not become a silent “proof exists somewhere” positive.

### 11.8 Anti-wire-format warning

The lifecycle states, drill phases, dimension names and recovery outcomes are semantic requirements and test propositions. They do not prescribe a persisted state enum, event envelope, archive package, API, schema or vendor topology. OPS-R14 and implementation authority retain mechanics, provided the observable outcomes above remain reproducible.