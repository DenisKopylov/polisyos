---
title: INT-R7 — Comparative Verification Models and Selection
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

# INT-R7 comparative models and selection

## 1. Decision criteria

The candidate models are evaluated without assuming the repository's current Ed25519 shape is the answer. The elimination criteria are properties the public profile must possess, not implementation preferences:

- exact statement/content integrity;
- institutional authority and succession evidence;
- trusted issuance time and signing-time status;
- revocation semantics that preserve pre-revocation history;
- anti-equivocation/common-view evidence;
- 10–30 year verification across key and algorithm changes;
- offline verification without live PolicyOS infrastructure;
- audience/jurisdiction/epoch/authority/basis binding;
- citizen-operable failure outcomes;
- privacy-safe addressing;
- no single vendor/service chosen as canonical by research;
- compatibility with append-only correction and GY-N12 rather than a new status lattice.

No single candidate supplies all properties. The selection is therefore a layered profile, but every layer must have a named job. “Defence in depth” without guarantee allocation is not a design.

## 2. Comparative table

| Model | What it guarantees under stated assumptions | Institutional/operational cost | Eliminating defect if used alone | Disposition |
| --- | --- | --- | --- | --- |
| 1. Detached signatures + published key directory | Exact statement integrity and unforgeability under EUF-CMA, uncompromised key and authentic directory | key custody, directory publication, rotation/revocation process, canonicalization stability | no trustworthy signing time, authority chain, split-view defence, archival renewal or historic/current distinction | **retain as primitive, reject as complete profile** |
| 2. X.509/PKI + CRL/OCSP | credential path, identity/policy constraints and revocation/status evidence at a time, under authentic trust anchors/status responders | CA/RA governance, certificate policy, trust-anchor distribution, revocation availability, cross-jurisdiction mapping | ordinary path validation does not itself preserve decades of status evidence or prevent publication equivocation | **select as one admissible authority layer, owner-neutral** |
| 3. PAdES/XAdES/CAdES archival levels + RFC 3161/LTA/ERS | binds signatures to trusted time and validation material; supports renewal before algorithms/certs weaken | preservation service, periodic validation/renewal, format expertise, policy/version retention | does not by itself prove one common public history or eliminate institutional authority questions | **select as long-term evidence layer; no final container chosen** |
| 4. Append-only Merkle transparency log | efficient inclusion and consistency proofs under hash assumptions | log operation, monitoring, checkpoint retention, availability, witness ecosystem | one log can serve different internally consistent views; consistency proof is not common-view proof | **select with independent witnesses/gossip, reject alone** |
| 5. Keyless/short-lived credential (Fulcio pattern) | narrows persistent-key exposure and binds signing to an identity-provider event under uncompromised IdP/CA/log | IdP availability and policy, identity claim governance, clock/log dependence, archival certificate evidence | workforce/OIDC identity does not establish public authority, succession or long-term preservation | **optional issuance pattern, not canonical authority model** |
| 6. Threshold/multi-party signing | fewer-than-threshold custodians cannot sign under sound share generation and threshold assumptions | ceremony, participant availability, share recovery, denial-of-service and governance complexity | no time, revocation history, log common view, archival longevity or legal authority | **recommended control for high-consequence issuance, not universal cryptographic requirement** |
| 7. Independent witness co-signing/notarization | adds evidence from a separately governed party and can corroborate time/checkpoint/issuance | external agreement, competence boundaries, liability, continuity and cross-agency recognition | witness may attest the wrong proposition; one witness can collude or disappear | **select for checkpoint/common-view corroboration where governance can sustain it** |
| 8. Blockchain/external public anchor | widely replicated timestamp/order commitment under consensus assumptions and continued chain availability | transaction costs, chain governance, privacy/metadata risk, external dependency, migration/fork handling | anchor proves only a commitment existed; not signer authority, content safety, revocation/currentness or legal custody | **reject as canonical; optional additional anchor only** |
| 9. Client-side salted 32-bit FNV | accidental-transmission detection only when attacker cannot recompute, an assumption false for public code | low | public deterministic recomputation lets anyone forge; 32-bit non-cryptographic hash; no secret, identity, time, authority, status, log or archive | **mandatory strangle; never positive verification** |

## 3. Model 1 — detached signatures and a published key directory

### Construction

The current repository signs canonical statement bytes with Ed25519 and stores a detached sidecar. The statement binds artifact ID, blob and manifest SHA-256 digests and key ID (`core/artifacts/signing.py:33-94, 291-411 @ 02c5b8d`). Verification checks a local trust directory, a timeless revoked-key directory, content digests and the Ed25519 signature (`:539-683`).

### Guarantee

If Ed25519 remains EUF-CMA secure, the private key was not compromised, the public key directory is authentic, canonicalization is unambiguous, and SHA-256 retains collision/second-preimage resistance, an adversary cannot create a valid signature for a different statement.

### What transfers

- detached, domain-separated signatures over canonical commitments;
- stable content-derived key IDs as locators, not authority by themselves;
- content/manifest integrity checks;
- offline signature verification.

### What fails

- `signed_at` and `signer_identity` are outside the signed statement and can be edited without signature failure;
- the revoked directory has no effective time or reason;
- an old valid signature and a forged-after-compromise signature both become a timeless `REVOKED` result;
- a directory has no credential path or institutional succession semantics;
- no proof that the record was logged or that all verifiers saw the same history;
- no archival evidence renewal or algorithm-agility policy;
- no audience, jurisdiction, authority boundary, GY-N12 epoch or declared obligation-set binding.

### Disposition

Extend the existing canonical signing owner rather than replacing it. The detached-signature idea is a primitive inside the selected profile, not the profile itself. Its current version is unsuitable for the first public signature.

## 4. Model 2 — X.509/PKI with certificate chains and CRL/OCSP

### Construction

A signer credential chains through intermediate certificates to a configured trust anchor. Path validation applies name, policy, key usage, validity and constraint rules. CRLs or OCSP provide signed status evidence with production/update times and, when revoked, a revocation time. Primary technical anchors are RFC 5280 and RFC 6960.

### Guarantee

Under authentic trust anchors, correct certification practice, secure CA/RA keys, correct path validation and authentic status evidence, the verifier can establish that a key was certified for a constrained identity/policy at a time and evaluate known revocation status.

### Government-specific value

- separates raw key possession from an institutionally recognized credential;
- supports certificate policies and role constraints;
- provides a cross-organization vocabulary familiar to public-sector signing regimes;
- eIDAS validation and qualified preservation explicitly distinguish validity at signing from later preservation;
- can carry succession/trust mappings without putting one opaque local key directory in every citizen's hands.

### Costs and failure modes

- CA or RA compromise/mis-issuance;
- status responder unavailable after years;
- certificate expired even though signature was valid when made;
- policy OIDs/names outlive their documentation;
- cross-border trust does not arise merely because a chain validates;
- OCSP “good” means no known revocation in the responder's scope, not proof the private key was never compromised;
- live status queries leak which record is being checked unless privacy is designed;
- institutional authority to issue a PolicyOS custody statement remains a separate mandate predicate.

### Disposition

Select an **institutional credential layer** capable of expressing the required authority and time constraints. X.509 is a leading interoperable construction, but this research does not appoint a CA, mandate qualified status, or declare legal sufficiency in a jurisdiction. A jurisdiction-recognized equivalent may satisfy the semantic contract.

## 5. Model 3 — long-term signature formats, trusted timestamps and evidence records

### Construction

PAdES, XAdES and CAdES baseline/archival profiles package a signature with certificates, status evidence, timestamps and later archival timestamps. RFC 3161 defines a timestamp token over a message imprint. RFC 4998 defines Evidence Record Syntax for long-term archives, including renewal as cryptographic algorithms weaken. ETSI EN 319 102-1 and TS 119 511 specify validation/preservation service concepts.

### Guarantee

A timestamp token can prove that a committed datum existed no later than a trusted time, assuming the timestamp authority's signature, clock policy and validation material were valid. Preserved validation data can show the signer credential's status at signing. Timely evidence renewal can carry forward the evidentiary chain before prior hashes/signatures cease to be trustworthy.

The guarantee is **not** “the old algorithm stays secure forever.” It is: while the old evidence was still trustworthy, a new trusted commitment was made to it under a then-acceptable suite, and the chain is preserved.

### Decade-scale value

- distinguishes signing time from verification time;
- keeps CRL/OCSP/certificate/trust-policy evidence with the proof rather than depending on a live responder decades later;
- supports periodic re-anchoring before algorithm deprecation;
- gives archival systems an event chain rather than silently replacing original signatures;
- aligns with eIDAS preservation concepts and public archival obligations.

### Failure modes

- renewal happens after the old primitive was already broken;
- timestamp service clock or key compromised;
- validation policy/version not preserved;
- format conversion drops embedded evidence;
- archive preserves a PDF rendering but not the signed semantic bytes;
- a preservation signature is misrepresented as the original authority signature;
- format-specific choices become a lock-in.

### Disposition

Select **LTA/ERS-class semantics**: trusted time, retained validation material, recursive evidence renewal and explicit original-versus-preservation lineage. Do not select a final PAdES/XAdES/CAdES package or wire format in research. The public semantic statement may need a format-neutral proof carrier plus human-readable archival rendering; final serialization remains implementation/design authority work.

## 6. Model 4 — append-only Merkle transparency structures

### Construction

Records or commitments are leaves in an append-only Merkle tree. A signed checkpoint/tree head commits to tree size and root. Inclusion proofs show a leaf belongs to a tree. Consistency proofs show a later tree extends an earlier one. RFC 9162 is the primary construction reference.

### Guarantee

Under collision/second-preimage resistance and correct proof verification:

- inclusion establishes that the exact commitment is in a particular tree;
- consistency establishes append-only extension between two checkpoints.

These are efficient and can be verified offline if proofs and checkpoints are retained.

### Public-administration value

- makes deletion or silent replacement detectable relative to retained checkpoints;
- supports journalists/agencies maintaining independent mirrors;
- provides a public chronology for issuance, withdrawal, supersession and preservation events;
- lets a citizen verify inclusion without downloading the whole log;
- gives successor organizations evidence they cannot rewrite without contradicting witnessed history.

### Split-view limitation

A malicious log can provide one internally consistent tree to one verifier and another to another verifier. Inclusion and consistency within each view still pass. RFC 9162 recognizes the need for monitors/auditors and checkpoint sharing; it does not make one server intrinsically non-equivocating.

### Disposition

Select transparency **only with** independent checkpoint witnesses, gossip/cross-publication or a quorum policy. Common-view verification rests on that independent corroboration, not on Merkle mathematics alone. Log operator and witness appointments are institutional decisions outside this research.

## 7. Model 5 — keyless or short-lived-credential signing

### Construction

The repository's Fulcio-style module obtains an OIDC identity token, creates an ephemeral P-256 key, requests a short-lived certificate and signs under it (`core/security/slsa/fulcio.py:1-400 @ 02c5b8d`). Sigstore combines this pattern with a transparency log and a verification bundle.

### Guarantee

Under uncompromised identity provider, CA, ephemeral-key handling and transparency service, the signature is tied to an authenticated identity event during a short credential lifetime. Long-lived private keys are reduced or eliminated.

### What transfers

- short-lived credentials reduce exposure of standing signing keys;
- identity evidence and log inclusion can be packaged with a signature;
- offline verification bundles are a useful operational model;
- public monitoring makes misuse more detectable.

### What does not transfer

- OIDC account identity is not authority to issue a government decision record;
- workforce account continuity is not institutional succession;
- software-build identity claims are typically narrower and shorter-lived than public-record retention;
- “signed by account X” does not establish the authority boundary, jurisdiction or mandate;
- long-term validation still requires timestamp/status/archive renewal;
- IdP availability and account lifecycle become critical dependencies.

### Disposition

Keep keyless/short-lived credentials as an optional issuance pattern or operator-authentication layer. Reject it as the sole or canonical public-record authority model. Any use must bind the short-lived credential to institutional authority evidence and the rest of the selected profile.

## 8. Model 6 — threshold or multi-party signing

### Construction

A threshold scheme such as FROST distributes a signing key across participants; a threshold cooperates to produce a standard signature. Alternatively, multiple independent signatures can be required by policy. RFC 9591 describes FROST for Schnorr-style signatures and its security assumptions.

### Guarantee

Under secure distributed/share generation, correct protocol execution, EUF-CMA assumptions and fewer than the threshold number of corrupt participants, one compromised custodian cannot issue a valid signature alone.

### Institutional value

- separates preparation from authorization;
- makes unilateral insider signing harder;
- can span records, security and substantive authority roles;
- provides a controlled emergency/recovery ceremony;
- can be aligned with public-administration separation of duties.

### Costs and failure modes

- participant unavailability can block issuance;
- malicious participants can deny service even if they cannot forge;
- share backup/recovery can recreate a single point of compromise;
- quorum composition may encode an authority decision this research cannot appoint;
- threshold math does not prove the participants were authorized for this record;
- threshold signing supplies no timestamp, status history, transparency common view or archival renewal.

### Disposition

Recommend threshold or multi-party authorization as the default **risk-control direction** for high-consequence public signing, subject to institutional selection. Do not make one threshold scheme, participant count or team canonical here. The profile's semantic contract must support more than one signer/authorization evidence path without requiring it for every jurisdiction.

## 9. Model 7 — independent witness co-signing or notarization

### Construction

An independently governed party signs or publishes a commitment to a record/checkpoint/time/status observation. It may be an archival institution, another agency, notarial/trust service, civil-society monitor or cross-log witness. The attested proposition must be explicit.

### Guarantee

Under the witness's key/authority security and non-collusion assumption, the witness supplies independent evidence that it observed the named commitment/checkpoint or performed the named validation at a time.

### Institutional value

- survives abolition or compromise of the issuing organization;
- gives courts, journalists and other agencies an external evidence path;
- can detect a split-view log by co-signing checkpoints obtained independently;
- supports legal deposit or archival custody without making the archive the policy authority.

### Failure modes

- witness signs “checkpoint observed” but UI implies “decision approved”;
- witness lacks durable retention or competence;
- all witnesses share one vendor/control plane;
- witness disappears or changes policy;
- one witness can collude;
- privacy-sensitive record identifiers are exposed.

### Disposition

Select witnessed checkpoint/common-view evidence as a required **profile capability**, with a configurable independent-quorum policy. Do not appoint the witness or declare a specific notarization legally sufficient.

## 10. Model 8 — blockchain or external public anchoring

### Construction

Publish a digest or Merkle root in a public blockchain transaction or another widely mirrored public medium. Later prove the commitment was included in a block/history under the chain's consensus rules.

### Guarantee

Under the chain's consensus, hash and continued-availability assumptions, the anchor can provide evidence that a commitment was published no later than a chain position/time approximation and was difficult to rewrite under normal operation.

### Serious advantages

- independence from the issuing agency's infrastructure;
- many public replicas;
- public auditability;
- potentially strong anti-deletion evidence for a periodic root;
- useful as one witness among heterogeneous witnesses.

### Eliminating defects as canonical profile

- a chain does not identify or authorize the government signer;
- block time is not necessarily a qualified or precise trusted timestamp;
- revocation, authority succession, GY-N12 epoch and declared-basis semantics are absent;
- public transaction metadata may leak issuance cadence or enable dictionary attacks against low-entropy records;
- forks, chain governance, fees and protocol migration become long-term public-record dependencies;
- smart contracts do not solve archival preservation or legal competence;
- selecting one chain creates vendor/ecosystem lock-in and cross-jurisdiction recognition problems;
- an anchor cannot repair a forged commitment made by a compromised signer.

### Disposition

Reject blockchain as the canonical proof lifecycle or trust root. Permit an external chain anchor only as an additional, non-exclusive witness to a batched public checkpoint, with privacy analysis and a migration path. The profile must remain verifiable without that chain.

## 11. Model 9 — current client-side salted FNV comparator

### Construction and direct forgery

The salt is source-visible. The packet and “signature” are embedded in the URL. The verifier recomputes the same 32-bit FNV-1a value. An attacker does not need a collision: it chooses a replacement packet and calculates the expected value.

### Threat-by-threat failure

| Threat | Why the FNV mechanism fails |
| --- | --- |
| Payload replacement | attacker recomputes the public function over replacement payload |
| Impersonation | no private key, credential or authority chain exists |
| Revocation | no key or temporal status exists to revoke |
| Backdating | timestamps are attacker-controlled payload fields |
| Split view | each URL is self-contained; no shared append-only history or checkpoint |
| Wrong audience/jurisdiction | those values are not protected by an authority credential or domain-separated signature |
| Stale epoch | no GY-N12 status source is consulted |
| Algorithm deprecation | FNV is already unsuitable as a cryptographic commitment and has no migration chain |
| Offline verification | local recomputation verifies only attacker-consistent bytes |
| Institutional succession | no institution is identified cryptographically |
| Declared obligation set | a bare number can be included and “verified” as easily as a complete statement |
| Citizen UX | the browser renders `Verified`, converting self-consistency into authority |

### Disposition

Mandatory strangle under P27/P28. The packet builder may survive as a rendering view model only. The old signer/verifier must be unable to emit a positive public verification outcome and should remain only as an explicit negative fixture until deleted or fenced.

## 12. Selected composite profile

### Layer allocation

| Selected layer | Sole or primary responsibility |
| --- | --- |
| Domain-separated semantic signature | exact statement integrity and signer-key proof |
| Institutional credential/authority evidence | who/what role was authorized, for which jurisdiction, purpose and interval |
| Trusted timestamp + signing-time status | existed before a time and before the relevant revocation/compromise cutoff |
| Transparency inclusion/consistency | append-only public history and efficient membership proof |
| Independent witnessed checkpoints | common-view/split-view resistance under non-collusion/quorum assumption |
| GY-N12 epoch/status link | historical epoch validity, current/stale/revalidation/withdrawal meaning |
| INT-R8 projection proof interface | content-retention/redaction relation owned by INT-R8 |
| LTA/ERS-class preservation chain | continued validation across certificate, key, hash, algorithm and format change |
| Optional threshold/multi-party authorization | resistance to unilateral signing/insider compromise |
| Optional heterogeneous external anchor | extra evidence of checkpoint publication, never the sole trust root |

### Why this wins

It is the smallest composition that assigns every mandatory guarantee to a construction designed for it:

- signatures authenticate exact statements;
- credentials/mandates establish institutional role;
- trusted time and retained status separate pre- from post-revocation signatures;
- transparency plus witnesses addresses equivocation;
- GY-N12 supplies currentness without a parallel lattice;
- archival renewal addresses 10–30 year cryptographic change;
- offline bundles preserve the verification closure;
- INT-R8 remains the content owner.

Removing any selected mandatory layer loses a required property:

- remove trusted time: compromise backdating is unresolved;
- remove witnessed transparency: split view is unresolved;
- remove preservation renewal: algorithm deprecation breaks the archive;
- remove authority evidence: a key is mistaken for a public mandate;
- remove epoch/status: historical authenticity is mistaken for current authority;
- remove INT-R8 interface: proof no longer knows what retained public content it binds.

### What is deliberately not selected

- no final wire/container or PAdES/XAdES/CAdES choice;
- no CA, TSA, log, witness, blockchain, vendor or archive appointment;
- no fixed signature/hash suite for 30 years;
- no universal threshold count;
- no legal-sufficiency conclusion;
- no new status lattice;
- no disclosure/compression semantics.

## 13. Recommendation standing

**Recommendation: GO_WITH_REVISIONS for the research profile.** The composite is technically coherent and institutionally recognizable. The first-public-signature gate remains closed until the dependencies and institutional commitments named in the integration handoff are resolved, and until implementation authority selects concrete formats, services, owners and policies.

## 14. Post-audit comparative clarification

This section controls the comparative conclusion after findings `INT-R7-III-002`, `INT-R7-III-003`, `INT-R7-II-005`, and `INT-R7-II-006`.

### 14.1 Separately reportable dimensions, not logically independent predicates

The selected layers remain justified, but their outputs are **separately reportable dimensions**. They are not claimed to be statistically or logically independent. In particular:

- signature, credential, trusted time and signing-time status support `IssuerIssuanceAuthentic`;
- INT-R8 supports `ProjectionFaithful`;
- log plus independently governed checkpoint evidence supports `PublicHistoryEstablished`;
- preservation and verifier closure support `DurablyVerifiableAt(t_v)`;
- GY-N12 supports `CurrentAuthorityAsOf(t_q)`.

A later projection, witness, archive or currentness failure cannot retroactively make a genuine issuer-side issuance event not have happened. It changes what can presently be proved or publicly relied upon. Public-current outcomes require the conjunction of all five dimensions, but every dimension remains visible when another fails.

### 14.2 Source-transfer narrowing

- RFC 9162 supports Merkle inclusion/consistency and the need for monitoring/checkpoint comparison. The requirement for a declared independent witness/quorum policy is INT-R7's design inference under a named non-collusion assumption, not an RFC 9162 standardized quorum.
- Sigstore's exact bundle structure is anchored by supplemental source `SIG-05`, *Sigstore Bundle Format*, Version 0.3.2. It demonstrates verification material and signature-content packaging; it does not establish public administrative competence.
- ETSI EN 319 142-1 V1.2.1 metadata is corrected to 2024-01 in the source ledger.
- NARA `US-01` is historical-only and is not used as current authority; Federal PKI `US-02` is nonbinding and Federal Register-specific.

### 14.3 Selection survives the audit

All nine mandatory models remain genuinely evaluated by eliminating property. No option is rejected because the current repository makes it awkward. The composite still wins because no surveyed single model supplies issuer authenticity, projection faithfulness, public-history evidence, durable verifiability and current authority together.

### 14.4 Anti-wire-format warning

The layer names and five dimension names are semantic allocation vocabulary. They do not prescribe a result enum, serialized proof object, endpoint, database table or container. A conforming implementation may represent them differently if it preserves the exact propositions, failures and composition boundary.