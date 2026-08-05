---
title: INT-R7 — Repository Integration Handoff, Dependencies, and Open Questions
research_id: INT-R7
status: delivered
result_standing: GO_WITH_REVISIONS
repository: https://github.com/DenisKopylov/polisyos
pinned_repository_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
inspection_date: 2026-08-04
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

# Repository integration handoff

## 1. Handoff rule

This is an ownership and missing-state map, not an implementation plan. It applies P27/P28:

- extend an existing canonical owner when its scope can honestly absorb the new contract;
- do not duplicate signing, rotation, verification, epoch or public-projection owners;
- strangle the decorative predecessor rather than maintain two live verification truths;
- classify the exact missing link instead of calling every gap `producer_missing`.

All claims below describe commit `02c5b8d23c757c92b9231e6e1e802d5701588908` only.

## 2. Capability handoff matrix

| Existing owner/surface | Pinned reality | INT-R7 semantic extension | Missing-state label at pin | Ownership disposition |
| --- | --- | --- | --- | --- |
| `core/artifacts/signing.py` | Ed25519 detached signature over artifact/blob/manifest/key ID; mutable `signed_at`/identity outside signed statement; timeless local revocation | domain-separated public semantic statement; authority/audience/jurisdiction/epoch/basis binding; suite policy; signing-time evidence references; separate historic/current result inputs | `contract_only` for public profile; `verification_missing` for temporal/authority/public semantics | **extend canonical signing owner**, do not create a second public signing library |
| `core/security/rotation.py` | JWT/operator trust-manifest rotation and local Ed25519 key-file rotation | public-signing authorization intervals; normal retirement vs compromise; effective-time revocation; overlap and archive-validation states; authenticated event outputs consumed by proof/status owners | `contract_only` for public lifecycle | **extend canonical rotation/control owner**; do not create an independent public-key lifecycle registry |
| `core/audit/verifier.py` | package/CAS/provenance/dependency and detached-signature verification | predicate-vector public proof verification; external trust snapshots; time/status/log/witness/epoch/archive/INT-R8 inputs; bounded reason codes | `verification_missing` | **extend verifier engine**, keeping audit-package concerns distinct from public authority semantics |
| `core/audit/standalone_verifier_template.py` | portable Python integrity/package verification, including package-provided key loading | offline execution shell over independently authenticated trust/status/checkpoint closure; citizen/machine report; no live fallback | `verification_missing` | **extend/derive from existing portable verifier**, not a second unrelated offline verifier; package self-key trust must fail |
| `core/security/slsa/fulcio.py` | short-lived OIDC-bound certificate path for supply-chain identity | optional issuance pattern only; if used, bind to institutional authority and archive all identity/cert/time/log evidence | `contract_only` for transferable pattern | **reuse selectively**, never promote software-build identity model to public authority owner |
| `runtime/quality/public_export.py` | real 2,103-line redacted public projection producer; no signature/proof issuance | export an INT-R8-governed retained-claim commitment and hand it to proof production; preserve projection-only authority limits | proof producer `producer_missing`; production HTTP/public bridge `bridge_missing` | **extend public-export producer at its boundary**, but INT-R8 owns content/projection semantics |
| Runtime HTTP layer | no production caller/route for `build_public_export_bundle`; tools/tests call it | authenticated public record/proof retrieval, status/checkpoint refresh and machine twin | `bridge_missing` | DS12-owned bridge; no inference that producer is absent |
| `publicationPacket.ts` | client-side public-salt 32-bit FNV “signature”; browser recomputation | presentation-only view model fed by verified predicate result; legacy token never positive | `verification_missing` and `semantic_test_missing` | **strangle under P28**; retain only explicit negative fixture/rendering model |
| `PublicDecisionViewerPage.tsx` | displays `Verified` from local FNV verification | bounded citizen outcomes, `as_of`, historical/current split, offline evidence details | `verification_missing`; `semantic_test_missing` | DS12 replaces verification source; no unsigned `verified=true` trusted from server |
| GY-N12 epoch owner | planned canonical epoch/currentness/stale/reissue semantics | provide epoch/status evidence consumed and signed by INT-R7 | dependency, not an INT-R7 missing owner | **consume; do not duplicate** |
| INT-R8 public projection/content contract | parallel research owns retained content, compression loss and disclosure composition | deterministic retained-claim/projection proof interface | dependency, not solved here | **consume by name; do not cross seam** |
| DS13 accountability/transparency surfaces | planned post-DS12 dispute/supersession/revocation/transparency history | later surface the proof/status history; DS12 still needs minimum anti-equivocation before first record | `producer_missing`/`bridge_missing` according to DS13 plan | INT-R7 defines proof requirements, not DS13 implementation |
| OPS-R14 resilience owner | active/undelivered custody-grade resilience and long-term replay task | durable proof closure, recovery, legal hold, expiring dependencies, compromised-primary drills | dependency | **declare outcomes only**, no DR/archive mechanics invented |

## 3. Why each existing owner is extended

### 3.1 Signing owner

`signing.py` already owns canonical statement bytes, detached signatures, key IDs and signature verification (`core/artifacts/signing.py:33-94, 291-411, 539-683 @ 02c5b8d`). A new `public_signing` package with independent key/trust logic would create the P27 duplicate-owner failure. The correct extension is to make the canonical signer capable of signing a richer, versioned semantic statement or delegate through one admitted interface while preserving one source of signing truth.

The extension must not silently change existing artifact-signature meaning. Public proof is a distinct domain-separated statement/profile, not an overloaded artifact sidecar that old verifiers misinterpret.

### 3.2 Rotation owner

`rotation.py` owns operational trust-anchor and Ed25519 rotation (`core/security/rotation.py:1-237 @ 02c5b8d`). Public proof needs more semantics, but key lifecycle control remains the same ownership class. Extend its outputs or canonical owner boundary to emit temporal, reasoned events; do not create a competing registry that can disagree on active/retired/revoked state.

Record currentness remains outside rotation. A key can be retired while records stay current; a record can be withdrawn while a key remains active.

### 3.3 Verification owner

The audit verifier and standalone template already own portable verification execution. Reusing them preserves hardened archive traversal, integrity and reporting work. Public verification adds trust/authority/time/status/log/witness/epoch/archive/projection predicates. It should not make audit-package self-consistency an authority result.

The most important interface change is not a new cryptographic primitive; it is a result vector that keeps `SignatureValid`, `HistoricallyAuthentic`, `CommonView` and `CurrentAuthority` separate.

### 3.4 Public export owner

`build_public_export_bundle` is a real projection producer and already enforces projection-only limits and scans artifacts (`runtime/quality/public_export.py:1-850, 1400-2103 @ 02c5b8d`). The exact orientation correction matters: tools and tests call it, but production `src` has no route/caller. Therefore:

- projection production exists;
- proof production is absent;
- production publication bridge is absent.

Calling all three `producer_missing` would erase existing work and invite duplication.

## 4. Genuinely new capabilities

The following capabilities do not have a canonical implemented owner at the pinned commit. Their eventual owner allocation requires architecture authorization; INT-R7 supplies only the semantic boundary.

### N-01 — public authority credential and succession evidence

A source of authenticated institutional role/mandate/term/succession evidence that can be preserved offline and evaluated at issuance/current time. It may integrate PKI or jurisdiction-specific trust. It is not equivalent to `signer_identity` text or workforce OIDC.

Missing state: `producer_missing` plus institutional dependency.

### N-02 — trusted issuance-time and signing-time status closure

Trusted timestamp plus retained credential/revocation/compromise evidence sufficient to distinguish pre-cutoff historical signatures from post-cutoff forgeries.

Missing state: `producer_missing`, `verification_missing`.

### N-03 — transparency/checkpoint/witness proof

Append-only inclusion/consistency plus independent checkpoint corroboration and retained offline proofs. The minimum anti-equivocation property is required before the first public record even if DS13 later owns richer feeds.

Missing state: `producer_missing`, `bridge_missing`, `verification_missing`.

### N-04 — public proof/status history

Persisted append-only relation among issuance, challenge, invalidation, withdrawal, supersession, reissue, key/algorithm events and preservation renewals, consuming GY-N12/current-authority outputs.

Missing state: `producer_missing`; owner relation must avoid duplicating GY-N12/DS13.

### N-05 — preservation evidence renewal

LTA/ERS-class validation closure, algorithm/hash migration events, verifier/spec preservation and renewal before deprecation.

Missing state: `producer_missing`, OPS-R14/institutional dependency.

### N-06 — independently authenticated offline trust/status bundle

Trust anchor/policy/status/checkpoint snapshot that cannot be replaced together with the payload. It may use the standalone verifier substrate, but the trust distribution/custody capability is new.

Missing state: `producer_missing`, `verification_missing`.

### N-07 — citizen proof outcome projection

Behavioral UX over the predicate vector, not a new status lattice. The current viewer has a component substrate but the verification semantics are missing.

Missing state: `verification_missing`, `semantic_test_missing`.

## 5. Strangle contract for the FNV predecessor

P28 requires more than adding a new path. The predecessor must be made incapable of authority.

Required disposition:

1. `signatureForPayload()`/`verifySignedPublicDecisionPacket()` can never cause `Verified current` or `Authentic historical`.
2. Existing packet construction may remain a rendering model while no longer being a signature source.
3. The inherited public route consumes a verified predicate report/evidence, not FNV result.
4. Legacy URLs either fail as non-authoritative or are explicitly migrated through an authorized process; browser recomputation is not grandfathered.
5. F-01 remains a permanent negative until the predecessor is deleted or fully fenced.
6. Search/lint test rejects any positive-label dependency on the legacy verifier.
7. Documentation caveats do not cure a green `Verified` badge; behavior must change.

Repository evidence: `publicationPacket.ts:240-247, 357-369, 1050-1188` and `PublicDecisionViewerPage.tsx:1-53 @ 02c5b8d`; Atlas DS12's negative control is at `POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md:1194-1250 @ 02c5b8d`.

## 6. Required semantic tests beyond the frozen adversarial cases

Missing state: `semantic_test_missing` at the pinned commit.

Positive/boundary properties required:

- normal key retirement preserves historical verification;
- trusted pre-revocation issuance plus withdrawal returns historical=true/current=false;
- unknown compromise interval returns indeterminate;
- offline report is bounded to snapshot `as_of`;
- one-view inclusion without witness remains incomplete;
- current GY-N12 epoch required for current result;
- old epoch remains replayable after append-only reissue;
- `delta` basis and assumptions are atomic with the number;
- procedural claim binds sealed chronology and no probability;
- preservation renewal keeps originals and labels roles correctly;
- successor organization cannot become predecessor issuer;
- INT-R8 failure blocks public projection without INT-R7 reclassification;
- unknown algorithm policy fails closed without defaulting to Ed25519;
- result meaning is invariant across human and machine projections/locales.

## 7. Dependency declarations

## 7.1 OPS-R14 — active, not delivered

Required outcomes from OPS-R14:

- custody-class durability and recovery evidence for original and renewed proof closures;
- expiring authority/key/certificate/timestamp/log/witness dependency monitoring;
- long-term replay of signed records without live original services;
- restore under compromised/unavailable primary infrastructure;
- legal-hold override and retention/destruction controls from competent governance;
- tamper-evident recovery/custody-transfer event history;
- recovery drills with bounded sample/implementation results;
- succession of storage/custody responsibility.

Not supplied by INT-R7:

- replication topology;
- RPO/RTO values;
- backup/archive vendor;
- HSM/share backup mechanics;
- legal-hold implementation;
- disaster-recovery runbook;
- storage class.

## 7.2 GY-N12 — canonical epoch semantics

Required interface:

- epoch identity and semantic/version commitment;
- authenticated status/current-head projection with `as_of`;
- `current_valid`, `stale`, `revalidation_required`, OpenWorldRisk and unresolved-scope results;
- append-only challenge/adjudication/invalidation/new-epoch/reissue/supersede/withdraw links;
- source/evidence invalidity propagation;
- historic replay under closure epoch.

INT-R7 binds/verifies the interface output. It does not own revision triggers, currentness adjudication or the lattice.

## 7.3 INT-R8 — content/projection seam

Required interface:

- stable retained-claim-set commitment;
- deterministic projection/redaction proof relation;
- policy/version identity;
- typed pass/failure outcome;
- successor relation when retained content changes;
- evidence sufficient for offline proof.

INT-R7 does not decide public content, material omission, compression loss, disclosure budget or cross-projection composition.

## 7.4 Institutional authority/trust governance

Required decisions outside research:

- which institutional role may issue each claim class;
- authority/mandate evidence and succession policy;
- accepted credential/trust policies and cross-jurisdiction recognition;
- key custody/quorum policy;
- timestamp/log/witness governance and independence assumptions;
- retention and archival-law obligations;
- public access/FOI and restricted-evidence handling;
- funding and continuity for 10–30 years;
- legal interpretation and admissibility.

No technical profile can manufacture these facts.

## 8. DS12 and DS13 consumption boundary

### DS12 minimum before first public record

- domain-separated semantic statement/profile;
- real signer credential and authority evidence;
- trusted time and signing-time status retention;
- minimum log inclusion/consistency and independent common-view evidence;
- GY-N12 currentness;
- INT-R8 proof;
- offline closure and citizen outcomes;
- algorithm/preservation policy and owner role;
- FNV strangle;
- frozen falsifiers.

### DS13 later expansion

- dispute/consultation history surfaces;
- rich supersession/revocation/transparency feeds;
- response-to-comment and accountability ledgers;
- public monitoring history.

The DS13 sequencing does not permit DS12 to publish without minimum anti-equivocation/status history. Conversely, INT-R7 does not pull the entire DS13 product into DS12.

## 9. Open questions for consolidation

Each question is typed and states why it cannot be answered here.

### Engineering

**E-01 — canonical public statement integration point.** Should the richer public statement be a versioned statement family inside `core/artifacts/signing.py` or a generic statement protocol implemented by that owner? Constraint: one canonical signer, no silent reinterpretation of existing artifact signatures.

**E-02 — verifier architecture.** Should the public verifier be a mode/plugin of `AuditPackageVerifier`, a generated standalone derivative, or both over one predicate core? Required property: identical semantic outcomes and no package-relative trust shortcut.

**E-03 — transparency/witness composition.** What implementation supports append-only inclusion, efficient consistency, independent checkpoint distribution and offline proofs while avoiding a second DS13 ledger owner?

**E-04 — authenticated offline snapshot.** How are trust anchors, authority evidence, revocation/compromise history, GY-N12 status and witnessed checkpoints packaged and updated without making the package self-authorizing?

**E-05 — canonicalization/rendering relation.** How are machine semantic bytes, human documents, locales and accessible renderings bound without finalizing a universal wire format in research?

**E-06 — privacy-safe log commitment.** Which commitment construction prevents low-entropy/dictionary leakage while preserving inclusion, migration and public audit?

**E-07 — suite agility.** How does one verifier dispatch among historical suites/policies and preserve implementations/test vectors without a permissive unknown-algorithm fallback?

**E-08 — large evidence closure.** How are multi-decade proof bundles sized, deduplicated and fetched offline without allowing missing material to become a warning-only pass?

**E-09 — threshold implementation.** If authorized, which scheme/quorum/ceremony integrates with institutional roles and recovery without creating unavailability or secret-share concentration?

**E-10 — witnessed currentness.** Which status elements must be in each checkpoint so a verifier can distinguish log consistency, record currentness and GY-N12 epoch status?

### Institutional

**I-01 — issuing authority.** Which institution/role is competent to issue a PolicyOS procedural custody statement, and what evidence proves that authority over time?

**I-02 — preservation custodian.** Which institution accepts the Public Verification Custody Owner role, funding and succession obligations? Research may name the role only.

**I-03 — independent witnesses.** What independence/quorum is institutionally credible across agency reorganization, outsourcing and political pressure?

**I-04 — trust-service recognition.** Which credential/timestamp/preservation policies are accepted in each target jurisdiction and for cross-agency/cross-border use? No legal sufficiency is established here.

**I-05 — archival disposition.** Which records are temporary, long-retention or permanent; what human-readable forms and trust documentation sets are required; how does legal deposit apply?

**I-06 — FOI/access interaction.** How are public proof closures supplied when some underlying validation/authority evidence is restricted, personal, security-sensitive or exempt?

**I-07 — compromise disclosure.** Who must publish compromise intervals, affected-record scope and uncertainty, and how are politically inconvenient records protected from suppression?

**I-08 — succession disputes.** What competent process adjudicates conflicting claims that a successor inherited custody or authority?

**I-09 — vendor/service exit.** What enforceable continuity/export obligations apply to CA/TSA/log/witness/archive providers so third-party disappearance does not destroy public verification?

**I-10 — citizen support.** Which competent records/challenge channel supports non-expert verification failures without turning PolicyOS into case management?

### Additional research

**R-01 — jurisdictional profile mapping.** Map the semantic profile to concrete public-sector signature/preservation regimes for intended launch jurisdictions, preserving the distinction between technical conformance and legal sufficiency.

**R-02 — transparency witness governance.** Compare multi-log, cosigning, gossip and public-notice anchoring models for government records under insider/successor threats.

**R-03 — privacy-preserving public commitments.** Evaluate salted commitments, keyed transparency, verifiable maps and batched disclosure proofs against public audit and dictionary attacks.

**R-04 — post-quantum archival transition.** Determine when and how existing classical public records should receive hybrid/post-quantum preservation evidence as standards and public-sector profiles mature.

**R-05 — long-term verifier preservation.** Compare source preservation, reproducible builds, WebAssembly, emulation and formally specified verification for 30-year citizen access.

**R-06 — compromise-time adjudication.** Develop evidence rules for uncertain compromise windows and mixed CA/TSA/log failures; avoid optimistic point estimates.

**R-07 — institutional succession proof.** Research public-record authority/custody succession across abolition, merger, devolution and privatization in target jurisdictions.

**R-08 — accessibility and durable human rendering.** Determine how signed semantic claims remain faithfully accessible across locale, assistive technology and format migrations without crossing INT-R8 content ownership.

**R-09 — independent preservation validation.** Determine whether and when an independent preservation service/witness is required, and what exact proposition it attests.

**R-10 — adversarial verifier usability.** Test whether citizens/journalists correctly distinguish current, historical-withdrawn, offline-as-of and incomplete outcomes under realistic mobile conditions.

## 10. Consolidation recommendations

Safe to ratify as research-level semantics:

- historical authenticity and current authority are separate;
- trusted time/status is mandatory for pre/post-revocation distinction;
- transparency requires independent common-view evidence;
- algorithm migration appends preservation evidence and never rewrites originals;
- offline currentness is bounded by authenticated `as_of`;
- `delta` basis and procedural chronology are signature-bound semantics;
- first-signature preservation profile is a gate, not backlog;
- existing owners should be extended and FNV strangled.

Must remain blocked:

- any claim the repository can publish a verifiable public record;
- first public signature before INT-R8, GY-N12, OPS-R14 outcomes and institutional commitments;
- final format, CA/TSA/log/witness/vendor, key quorum or owner appointment;
- legal sufficiency/compliance conclusions;
- automatic plan/SDD amendment.

Result: **GO_WITH_REVISIONS for INT-R7 research closure; the first-public-signature gate remains closed.**
