---
title: INT-R7 — Public Verification Proof Lifecycle
status: delivered
kind: deep-research
research_task: INT-R7
result_type: GO_WITH_REVISIONS
result_standing: GO_WITH_REVISIONS
repository: https://github.com/DenisKopylov/polisyos
repository_branch_inspected: main
pinned_repository_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
delivery_branch: research/int-r7-public-verification-lifecycle
inspection_date: 2026-08-04
amended_after_audit: research/int-r7-independent-audit@54e8f41d790cb257a616c5bb5f96d996fbe3e9db
remediated_after_verification: research/int-r7-amendment-verification@5225f8bf6cc995f0d3a9cb622454c1af9432745d
controlling_post_audit_amendment: "§21 — Post-audit controlling amendment"
research_only: true
int_r8_seam: proof_only
authoritative_for:
  - research-level public verification lifecycle semantics
  - owner-neutral PublicVerificationProfile
  - separation of historical authenticity from current authority
  - minimum pre-first-signature preservation requirements
  - frozen public verification falsifier specification
  - repository integration and missing-state handoff
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

# INT-R7 — Public Verification Proof Lifecycle

## Executive finding

**Result: `GO_WITH_REVISIONS`.**

> **Controlling reading notice.** This report preserves the audited text. Section 21 is the controlling post-audit amendment. Before relying on any earlier aggregate formula, dependency status, capability label, suite denominator, recovery-gate wording, source transfer, or independence claim, follow the point-of-use notice to the named §21 subsection. Where earlier text conflicts with §21, the earlier text is audited history and is not the current research contract.

A coherent public-verification lifecycle exists, but it is not “Ed25519 plus a public-key directory.” The minimum viable profile is a composition of independently scoped layers:

1. a domain-separated signature over the complete semantic statement;
2. institutional credential/mandate evidence for the exact claim class, authority boundary, jurisdiction, audience, and interval;
3. trusted issuance time plus retained signing-time revocation/compromise evidence;
4. append-only transparency inclusion and consistency proofs;
5. independently witnessed checkpoints or equivalent common-view corroboration against split view;
6. GY-N12 epoch/currentness evidence, without a second status lattice;
7. the INT-R8 retained-claim/projection relation, without INT-R7 deciding public content;
8. LTA/ERS-class preservation and timely algorithm/hash/format renewal;
9. an independently authenticated offline trust/status/checkpoint closure; and
10. citizen and machine outcomes that separate historical authenticity from current authority.

No single surveyed model supplies all ten properties. The selected composition gives every guarantee one named owner and one named assumption. Detached signatures supply exact statement integrity; credentials supply bounded institutional identity; trusted time/status distinguishes pre-revocation issuance from post-compromise forgery; transparency plus independent witnesses supplies common-view evidence; GY-N12 supplies currentness; INT-R8 supplies the content/projection relation; preservation renewal carries the proof through key, certificate, algorithm, format, and organizational change.

> **Superseded dependency and suite snapshot.** The following pre-audit gate list is retained as history. Section 21.3 governs INT-R8/GY-N12 dependency status, §21.5 governs the suite denominator, and §21.6 governs the recovery drill.

The research profile is strong enough for consolidation and DS12 design work. The **first-public-signature gate remains closed** until:

- INT-R8's content/projection contract is available;
- GY-N12 supplies canonical epoch/currentness outputs;
- OPS-R14 supplies custody-grade durability, recovery, legal-hold, and replay outcomes;
- competent governance assigns issuing and preservation roles, trust/witness policy, retention, succession, and funding;
- concrete formats/services/algorithms are selected under implementation authority;
- the FNV predecessor is strangled; and
- all 18 frozen falsifiers pass for the named implementation and environment.

The result is `GO_WITH_REVISIONS`, rather than `GO`, because the semantic profile is coherent but those dependencies and institutional commitments are unresolved. It is not `NO_GO` because no open cryptographic impossibility prevents the profile; the remaining blocks are explicit governance, dependency, and implementation selections. Nothing here authorizes publication.

## 1. Deliverable map

The primary report is supported by nine bounded artifacts:

- [Pass-I orientation audit](int-r7/orientation-ledger.md)
- [Threat model and verification predicates](int-r7/threat-model-and-verification-predicates.md)
- [Comparative models and selection](int-r7/comparative-models.md)
- [`PublicVerificationProfile` semantic contract](int-r7/public-verification-profile.md)
- [Lifecycle, migration, and 10–30 year preservation](int-r7/lifecycle-migration-preservation.md)
- [Citizen verification UX requirements](int-r7/citizen-verification-ux.md)
- [Frozen 18-case falsifier suite](int-r7/frozen-falsifier-suite.md)
- [Repository integration, dependencies, and open questions](int-r7/repository-integration-and-dependencies.md)
- [External primary-source and transfer ledger](int-r7/external-source-and-transfer-ledger.md)

Every artifact contains the same research-only and `may_not_use_for` prohibitions.

## 2. Pass-I orientation verdict

### 2.1 Method qualification

The requested local clone could not be completed because the execution environment denied outbound GitHub DNS/egress. Exact-ref inspection, complete connected code search, branch creation, and repository writes were performed through the connected GitHub integration. The deviation is recorded in the orientation ledger. Exact lexical counts not independently reproducible under a retained tree-walk were marked `not_established`, not guessed.

### 2.2 Confirmed facts

At `02c5b8d23c757c92b9231e6e1e802d5701588908`:

- `policy-engine/src/polisyos/core/artifacts/signing.py:1-768` is a real Ed25519 detached-signature owner with canonical statement bytes, key IDs, a local trusted-key directory, a timeless revoked-key directory, verification states, and bulk reports.
- Its signature statement covers artifact ID, blob/manifest digests, and key ID, while `signed_at` and `signer_identity` are sidecar fields outside the signed statement (`signing.py:53-94, 291-302, 389-411, 539-683`). Those display fields therefore cannot establish trusted issuance time or institutional identity-at-time.
- Its revocation check is membership in a local revoked-key set with no effective time, reason, compromise interval, or signing-time status proof (`signing.py:469-517, 583-610`). It cannot distinguish “authentically signed before revocation” from “forged after compromise and backdated.”
- `policy-engine/src/polisyos/core/security/rotation.py:1-237` owns JWT/operator trust-anchor and local Ed25519 rotation. It has active/next/retired/revoked concepts for runtime security, not a public-record proof lifecycle.
- `policy-engine/src/polisyos/core/audit/verifier.py:1-981` and `standalone_verifier_template.py:1-559` provide substantial package/integrity/provenance/offline-verification substrate, but not independently authenticated public authority, trusted issuance time, witnessed transparency, GY-N12 currentness, or archival renewal.
- `policy-engine/src/polisyos/core/security/slsa/fulcio.py:1-400` is an existing short-lived OIDC-bound certificate path for software-supply-chain identity. Its ephemeral credential and bundle pattern transfers; workforce/OIDC identity does not become public administrative authority.
- The complete production Python import denominator for `cryptography`, `jwt`, or `hmac` is **14/14 paths**, listed in the orientation ledger. This is a primitive-use census, not a capability conclusion.
- `policy-engine/src/polisyos/runtime/quality/public_export.py:1-2103` is a real redacted public-projection producer and contains no public proof issuance, trusted timestamp, transparency receipt, or verification gate.
- `policy-engine/apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts:240-247, 357-369, 1050-1188` uses a source-visible salt and 32-bit FNV-1a over attacker-chosen JSON; `PublicDecisionViewerPage.tsx:1-53` turns browser recomputation into a positive `Verified` presentation.
- The Atlas Publication reconstruction row records missing packet-hash binding, private-data scan path, server signer/verifier/public-record producer, and persisted public dependency (`policy-engine/docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md:197-218`). DS12 requires the forged-packet negative control and the INT-R7/INT-R8 research gate before first publication (`:1194-1250`); DS13 later owns richer accountability/transparency surfaces (`:1293-1310`). These are plan obligations, not existing capabilities.
- Binding semantics come from findings `S0-K08`, `S0-K16`, `INT-K01`, `INT-K02`, `INT-K06`, and `INT-K08` in `policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:1-264` and `int-wave-claim-semantics-ratification.md:1-379`.
- P35 and P36 require full-set denominators and finding-ID warrant rather than sampled generalization or authority by adjacent prose (`policy-engine/docs/reference/policy-design-case-failure-patterns.md:83-135`).

### 2.3 Orientation correction

The supplied assertion that `build_public_export_bundle` appears in exactly two Python files was false. Complete pinned-tree function search found the definition plus calls in two tools and two tests:

- `policy-engine/src/polisyos/runtime/quality/public_export.py`;
- `policy-engine/tools/ops_runners/runtime/canary_evidence.py`;
- `policy-engine/tools/quality/validation/check_layer3_workflow_failure_authority.py`;
- `policy-engine/tests/unit/runtime/quality/test_multi_tenant_shared_cas.py`;
- `policy-engine/tests/unit/runtime/quality/test_public_export.py`.

`runtime/quality/__init__.py` is a re-export, not a caller. The narrower production conclusion remains true: no production caller outside the defining `src` module and no HTTP route were found.

> **Superseded capability labels.** The classification list below is retained as audited history. Section 21.4 and `int-r7/repository-integration-and-dependencies.md` §11 govern the pinned capability disposition; only the real export-producer-to-route connection remains `bridge_missing`.

The correct capability classification is:

- public projection producer: present;
- public proof producer: `producer_missing`;
- production publication bridge: `bridge_missing`;
- public temporal/authority verifier: `verification_missing`;
- adversarial semantic tests: `semantic_test_missing`.

This correction is material because calling the projection producer absent would invite P27 owner duplication.

## 3. Binding architectural consequences

## 3.1 The first public signature is likely procedural, not probabilistic

Finding `INT-K06` ratifies a third outcome class: a binding, falsifiable claim about procedure carrying no probability. The first public proof therefore likely attests prospectivity, sealing, firstness, chronology, no prohibited substitution, adjudication, dissent, and published negatives.

That changes the threat model. The claim is about a **history**, so:

- a signer-controlled timestamp is insufficient;
- the prospective seal must be independently time-evidenced;
- event order and allowed deviations must be committed;
- negative/refusal terminals must enter the same append-only public history;
- a later signature over a chronology narrative does not prove the chronology; and
- a preservation signature cannot be presented as the original prospective seal.

The selected profile binds claim class and procedural-history commitments and verifies them separately from signature mathematics.

## 3.2 A `delta` without its declared basis is a signature-security failure

Finding `INT-K02` makes a `delta` inseparable from the declared obligation set, maintained assumptions, and relative-basis rider. Omitting or substituting that basis is **semantic substitution**: the signature authenticates a different, false statement.

Consequently, the profile atomically binds:

- numeric `delta`;
- declared-obligation-set commitment;
- maintained-assumptions commitment;
- relative-basis rider;
- proof/evaluation profile and revision; and
- audience, jurisdiction, authority boundary, and epoch.

`BasisBound=false` blocks every positive outcome even if the signature equation succeeds.

## 3.3 Correction appends; history is not rewritten

Findings `INT-K01` and `S0-K08` require challenge → invalidation → new epoch → reissue. Discovery of a missed obligation moves the declared basis for a new epoch; it does not rewrite the old computation or signature.

The profile therefore treats **withdrawn-but-verifiable** and **superseded-but-verifiable** as first-class outcomes:

- old record: historically authentic under its own epoch;
- current authority: false after authenticated withdrawal/supersession;
- successor: separately signed under its own epoch, basis, and authority evidence;
- history: append-only, witnessed, and reproducible.

GY-N12 remains the canonical epoch/currentness owner. INT-R7 signs and verifies its outputs; it does not invent a parallel status lattice.

## 4. Threat model and meaning of “verified”

### 4.1 Adversaries

The model includes:

- presentation/network attacker replacing URL, QR, page, package, or server result;
- current application/database/object-store compromise;
- signing-key compromise and backdating;
- malicious insider below threshold and authorized malicious quorum;
- compromised CA/RA, status service, timestamp authority, OIDC provider, or preservation service;
- malicious transparency log serving split views;
- archive/storage attacker replacing payload, signature, and bundled key together;
- successor organization rewriting predecessor attribution or suppressing records;
- political/administrative suppression without cryptographic break;
- compromised verifier environment; and
- privacy attacker enumerating low-entropy records or observing status queries.

The full controls/observations/goals are in `threat-model-and-verification-predicates.md`.

### 4.2 Predicate vector

> **Superseded aggregate algebra.** The predicate list and formulas in this subsection are retained as audited history. Section 21.2 and `int-r7/threat-model-and-verification-predicates.md` §15 govern: issuer issuance, projection faithfulness, public history, durable verifiability, and current authority are separately reportable; current/projection positives require admitted GY-N12 and INT-R8 interfaces.

The verifier evaluates at least:

- `CanonicalStatementRecognized`;
- `ContentBound`;
- `SignatureValid`;
- `ClaimClassBound`;
- `AudienceBound`;
- `JurisdictionBound`;
- `AuthorityBoundaryBound`;
- `EpochBound`;
- `BasisBound` for `delta`;
- `ProceduralHistoryBound` for procedural claims;
- `ProjectionRelationValid` from INT-R8;
- `SignerCredentialValidAtIssuance`;
- `AuthorityValidAtIssuance`;
- `TrustedIssuanceTimeEstablished`;
- `PreCompromiseOrRevocationEstablished`;
- `LogIncluded`;
- `LogAppendOnlyConsistent`;
- `WitnessPolicySatisfied`;
- `CommonViewEstablished`;
- `StatusSnapshotAuthentic`;
- GY-N12 current/stale/withdrawn/superseded predicates;
- `PreservationChainValid`;
- `AlgorithmPolicySatisfied`; and
- `OfflineClosureComplete`.

A bounded current result is:

```text
VerifiedCurrent(R, t_v, t_q) :=
    HistoricalAuthenticity(R, t_v)
  ∧ CommonViewEstablished(R)
  ∧ ProjectionRelationValid(R)
  ∧ CurrentAuthority(R, t_q)
  ∧ freshness_claim_is_bounded_to(t_q)
```

A withdrawn historical result is:

```text
WithdrawnButVerifiable(R, t_v, t_q) :=
    HistoricalAuthenticity(R, t_v)
  ∧ StatusSnapshotAuthentic(t_q)
  ∧ WithdrawnAtAsOf(R, t_q)
  ∧ ¬CurrentAuthorityAtAsOf(R, t_q)
```

No unqualified `Verified` state exists.

### 4.3 Assumptions and degradation

- Exact signature binding rests on EUF-CMA of the named suite and uncompromised required signing authority.
- Record/hash/Merkle commitments rest on collision and second-preimage resistance.
- Inclusion and consistency prove membership/extension relative to checkpoints, not a universal common view.
- Common-view evidence rests on the declared witness quorum/independence and non-collusion assumption.
- Pre/post-revocation ordering rests on trusted timestamp clock/key/policy plus retained signing-time status.
- Institutional authority rests on authentic mandate/delegation/succession evidence interpreted under a configured policy.
- Long-term verification rests on timely renewal before prior algorithms or validation evidence lose trust.

When an assumption degrades, the corresponding predicate fails or becomes indeterminate. The verifier does not keep a green result by falling back to signature mathematics.

## 5. Comparative option-space decision

All mandatory comparators were evaluated before selection.

| Model | Retained contribution | Property eliminating it as a complete answer |
| --- | --- | --- |
| Detached signature + key directory | exact canonical statement integrity; offline primitive | no trusted time, authority chain, common view, archival renewal, or historical/current split |
| X.509/PKI + CRL/OCSP | credential path, purpose constraints, validity/status evidence | live/ordinary validation does not preserve decades of status evidence or prevent equivocation |
| PAdES/XAdES/CAdES archival levels + RFC 3161/ERS | trusted time, validation material, recursive archival renewal | no common public history or automatic public-authority competence |
| Merkle transparency log | inclusion and append-only consistency | one log can serve internally consistent split views |
| Fulcio/keyless short-lived credential | reduced standing-key exposure, identity event, bundle pattern | workforce/OIDC identity is not public authority, succession, or long-term preservation |
| Threshold/multi-party signing | resistance to one compromised custodian below threshold | no time, status, common view, authority, or archive semantics |
| Independent witness/notarization | corroborated checkpoint/time/custody proposition | witness may attest the wrong proposition, collude, or disappear |
| Blockchain/external anchoring | replicated external checkpoint commitment | no signer authority, content safety, revocation/currentness, custody, or migration guarantee; privacy/governance lock-in |
| Client-side salted FNV | at most accidental self-consistency | attacker chooses payload and recomputes public 32-bit function; no secret, identity, time, authority, status, log, or archive |

The selected composition and transfer analysis are in `comparative-models.md`. External anchors are optional heterogeneous witnesses only; blockchain is rejected as canonical trust root. Threshold/multi-party authorization is recommended for high-consequence issuance where governance can sustain it, but no scheme/quorum is appointed.

Primary technical anchors:

- temporal validation and preservation: [EU-01], [EU-02], [ETSI-01]–[ETSI-05];
- trusted timestamping and evidence renewal: [IETF-01]–[IETF-03];
- append-only transparency: [IETF-04];
- PKI/status: [IETF-05], [IETF-06];
- threshold construction: [IETF-07];
- key lifecycle/algorithm transition/post-quantum agility: [NIST-01]–[NIST-04];
- blockchain limits: [NIST-05];
- public records/trust documentation and long-term validation: [US-01], [US-02], [CA-01];
- archival responsibility/metadata: [ISO-01], [LOC-01];
- keyless/transparency/bundle transfer: [SIG-01]–[SIG-04].

Stable identifiers and exact transfer/non-transfer boundaries are in `external-source-and-transfer-ledger.md`. None establishes automatic legal sufficiency.

## 6. `PublicVerificationProfile`

The owner-neutral semantic contract is in `public-verification-profile.md`. Its minimum signed statement binds:

### 6.1 Domain and exact object

- PolicyOS public-proof domain separator;
- profile, claim-class, canonicalization, signature, commitment, and algorithm-policy versions;
- high-entropy public locator/hiding commitment;
- canonical semantic record commitment;
- original governed-record commitment where distinct;
- human/accessibility rendering commitments or verified transformation relation;
- evidence-set commitment;
- predecessor/successor references.

### 6.2 Content seam

- INT-R8 retained-claim-set commitment;
- INT-R8 projection/redaction policy identity;
- deterministic projection relation/proof reference;
- typed INT-R8 result;
- projection successor relation.

INT-R7 does not define retained content, material omission, compression loss, or disclosure budget.

### 6.3 Claim-specific semantics

For procedural claims:

- prospective seal and trusted-time reference;
- firstness population/order commitment;
- chronology/event-chain commitment;
- prohibited-substitution policy;
- declared deviations;
- adjudication/evaluator version;
- dissent and negative-terminal commitments;
- explicit no-probability claim.

For `delta` claims:

- value;
- declared-obligation-set commitment;
- maintained-assumptions commitment;
- relative-basis rider;
- proof/evaluation scope and revision.

### 6.4 Relying and authority context

- audience and relying purpose;
- jurisdiction/recognition policy;
- authority boundary and claim class;
- issuing organization and institutional role at issuance;
- mandate/delegation evidence and interval;
- threshold/co-authorization policy where applicable;
- GY-N12 epoch and semantic revision;
- trusted issuance time and key/credential authorization interval.

### 6.5 Privacy-safe addressing

Use high-entropy opaque identifiers or nonce-hardened/hiding commitments and, where useful, batched Merkle roots. Do not expose raw PII, predictable case numbers, or unsalted hashes of low-entropy attributes. Prefer retained/stapled status evidence over privacy-leaking per-record live queries. INT-R8 still owns public content.

## 7. Key lifecycle

The lifecycle separates key/credential state from record state.

### 7.1 Key states

At the semantic level:

- `generated_candidate`;
- `authorized_staged`;
- `active`;
- `overlap_next`;
- `retired_new_signing_closed`;
- `archive_validation_only`;
- `suspected_compromise`;
- `suspended`;
- `revoked_prospective`;
- `compromised_known_cutoff`;
- `compromised_uncertain_interval`;
- `algorithm_deprecated_new_signing`;
- `algorithm_validation_expired`;
- `destroyed_with_evidence`.

These may be orthogonal dimensions in implementation; research does not authorize a database enum.

### 7.2 Normal rotation

Normal rotation:

- activates a successor under authenticated policy/authority evidence;
- permits a controlled overlap only under policy;
- closes the predecessor to new signing at an authenticated cutoff;
- preserves old public key, credential, status, policy, and proof material;
- does not imply compromise; and
- does not change record currentness by itself.

The existing `rotation.py` should be extended as the canonical control owner rather than bypassed with a new public-key registry (`policy-engine/src/polisyos/core/security/rotation.py:1-237 @ 02c5b8d`).

### 7.3 Compromise recovery

A compromise event appends:

- detection time;
- earliest supported compromise time or interval;
- affected keys/roles/claim classes/jurisdictions/records;
- freeze/revocation effective time;
- evidence/adjudication basis;
- successor activation;
- affected-record result;
- GY-N12 status impact;
- public log event and witnessed checkpoint.

OPS-R14 supplies operational recovery/storage mechanics. INT-R7 supplies the proof outcomes and drill requirements.

## 8. Revocation and temporal validity

Let trusted issuance time be `t_s`, prospective revocation be `t_r`, normal retirement be `t_ret`, and compromise interval be `[t_c_min, t_c_max]`.

- `t_s < t_ret`, no compromise: historical signature may remain valid; no new signing after `t_ret`.
- `t_s < t_r`, prospective revocation: historical signature may remain valid; record currentness is separately determined by GY-N12.
- `t_s >= t_r`: issuance unauthorized.
- `t_s < known t_c`: historical result may pass if policy permits and other evidence passes.
- `t_s >= known t_c`: historical authenticity fails.
- `t_s` overlapping an unresolved compromise interval: `TEMPORAL_VALIDITY_INDETERMINATE`.
- historical status missing: do not infer “not revoked” from absence or current OCSP state.

RFC 3161 explicitly supports evidence that data existed before a time, including evaluation relative to later revocation [IETF-01]. eIDAS validation/preservation and Canadian public-sector guidance likewise distinguish signing-time validity from later preservation/current evaluation [EU-01], [CA-01]. This is not a legal-sufficiency conclusion.

## 9. Record lifecycle

### 9.1 Issuance path

```text
draft_candidate
  -> sealed_prospective
  -> signed_pending_time_status
  -> time_status_established_pending_log
  -> logged_pending_witness
  -> published_current
```

No stage may be skipped by treating a signature as proof of time, authority, common view, projection safety, or currentness.

### 9.2 Post-issuance states

- `challenged_review_required`;
- `stale_revalidation_required`;
- `withdrawn_but_verifiable`;
- `superseded_but_verifiable`;
- `invalidated_basis_or_support`;
- `temporal_validity_indeterminate`;
- `content_or_signature_invalid`;
- `archive_only`;
- `preservation_evidence_insufficient`.

### 9.3 Organizational succession

A successor organization may append a custody/status/succession statement under its own credential. It cannot:

- become the predecessor issuer by possession;
- replace the predecessor signature/trust evidence;
- silently reinterpret the old claim;
- erase independently witnessed history.

Conflicting succession evidence yields an explicit disputed/authority-not-established outcome. The profile does not decide which institution legally succeeds another.

## 10. Anti-equivocation and split-view defence

A Merkle transparency layer provides:

- exact leaf inclusion under collision/second-preimage resistance;
- efficient consistency proof that a later checkpoint extends an earlier one;
- public chronology for issuance, refusal, challenge, withdrawal, supersession, key/algorithm events, and preservation renewal.

It does not alone prove one common view. A malicious log can maintain two internally consistent trees.

`CommonViewEstablished` therefore requires:

- independently obtained checkpoints;
- witness signatures, gossip, cross-publication, or an equivalent corroboration mechanism;
- declared quorum and independence policy;
- consistency comparison;
- typed failure on disagreement or insufficient independence.

The security guarantee rests on the non-collusion/independence assumption of the configured witness policy, not on Merkle mathematics alone [IETF-04]. No log operator or witness is appointed here.

The minimum common-view layer belongs before the first DS12 public record. DS13 may later add richer accountability feeds, but the first record cannot be published with no split-view defence.

## 11. Algorithm agility and archival migration

### 11.1 Policy distinction

For every primitive, authenticated policy distinguishes:

- permitted for new issuance;
- permitted for historical verification;
- permitted only through a preservation chain;
- deprecated pending migration;
- prohibited/unsupported;
- emergency-compromised.

Unknown algorithms fail closed. The profile does not freeze Ed25519 or any post-quantum choice for 30 years.

### 11.2 Re-anchoring rule

Before a prior primitive loses trust, a preservation event must:

1. retrieve original bytes and complete prior proof closure;
2. validate every prior link under the applicable policy;
3. record verifier/spec/policy/result and evidence cutoff;
4. commit to the complete prior closure;
5. bind old and new digests over the same object where hash migration occurs;
6. obtain new trusted time;
7. append to transparency history and obtain independent checkpoint evidence;
8. preserve original and renewal side by side; and
9. label the new signature as preservation, not original issuance.

RFC 4998 and ETSI archival/preservation profiles provide concrete constructions for recursive evidence renewal [IETF-03], [ETSI-01]–[ETSI-05]. They transfer as required semantics; no PAdES/XAdES/CAdES final container is selected.

### 11.3 Failure boundary

A new digest/signature computed **after** the old hash or signature is already untrustworthy cannot establish that surviving bytes are original unless independent earlier evidence resolves the ambiguity. Late re-signing is not retroactive repair.

### 11.4 Post-quantum planning

FIPS 204 and 205 provide standardized post-quantum signature families [NIST-03], [NIST-04]. The profile requires plural algorithm identifiers and permits hybrid/dual preservation evidence, but does not mandate an immediate suite or claim that public-sector archival interoperability is settled.

## 12. Minimum 10–30 year preservation profile before first signature

The following must exist **before issuance**.

### 12.1 Retained record and semantics

- original canonical statement bytes;
- original public projection and governed-record commitments;
- human/accessibility renderings and transformation relation;
- profile/canonicalization specifications and test vectors;
- INT-R8 proof outputs;
- audience/jurisdiction/authority/epoch/basis/history commitments;
- all original signatures.

### 12.2 Retained signing-time closure

- signer credential chain/equivalent;
- trust anchors and validation policies;
- CRL/OCSP/equivalent status evidence applicable to issuance;
- revocation/compromise history and intervals;
- trusted timestamp plus its credential/status/policy;
- mandate/delegation/role/term evidence;
- threshold/co-authorization evidence where required;
- later succession statements.

> **Superseded source transfer.** The US-01 sentence below is retained as audited history. Section 21.7 and `int-r7/external-source-and-transfer-ledger.md` §6 govern: US-01 is historical-only and officially superseded.

NARA's Trust Documentation Set guidance is a strong public-record transfer: preserve transaction signature/certificate/status/time evidence together with administrative policy, configuration, testing, and operational records for the retention period [US-01]. The transfer does not make US guidance universally applicable.

### 12.3 Retained public-history closure

- leaf and inclusion proof;
- log identity/policy/checkpoints;
- consistency chain;
- independent witness/cross-publication evidence;
- challenge/withdrawal/supersession/key/algorithm/preservation events;
- privacy-safe commitment openings needed for verification.

### 12.4 Retained epoch/currentness closure

- GY-N12 epoch/revision;
- authenticated status snapshots and `as_of` cutoffs;
- revision triggers;
- challenge/adjudication/invalidation/reissue/withdrawal/supersession relations;
- successor links.

### 12.5 Retained preservation and verifier closure

- fixity, custody transfer, rights/retention/legal-hold, format/migration, and renewal events under OAIS/PREMIS-class semantics [ISO-01], [LOC-01];
- algorithm-policy history;
- verifier source or independently inspectable specification;
- dependency/build/environment metadata;
- known-good and known-bad vectors;
- frozen falsifier fixtures;
- reason-code and human-report semantics.

OAIS/PREMIS do not themselves verify signatures; cryptography does not itself operate an archive. The layers compose.

### 12.6 Custody-owner role

A Public Verification Custody Owner **role** must be assigned before issuance. Research does not appoint a person, team, institution, or vendor. The role must:

- preserve original and renewed closures;
- monitor algorithm/format/trust-service horizons;
- execute authorized timely renewals;
- maintain authenticated trust/status/checkpoint snapshots;
- coordinate succession/custody transfer;
- apply competent legal-hold/retention outcomes;
- run bounded recovery drills;
- prevent preservation attestations from being represented as original issuance;
- expose unresolved breaks and freeze affected positive outcomes.

### 12.7 Recovery drill

A clean verifier with network denied must restore a representative sample and validate:

- originals/fixity;
- signature/authority at issuance;
- trusted time/status;
- transparency/witness common view;
- GY-N12 epoch/currentness as of snapshot;
- INT-R8 proof;
- every preservation renewal;
- withdrawn/superseded/stale outcomes;
- tamper and package-self-key negatives.

Success requires zero undisclosed network dependencies and exact predeclared outcomes. The report is bounded by `S0-K16`. OPS-R14 supplies actual storage/restore mechanics.

## 13. Offline verification

An offline party must possess the complete validation closure:

- record/projection and canonical statement;
- signatures;
- independently authenticated trust/authority policy;
- signer credential and signing-time status;
- trusted timestamp;
- log inclusion/consistency;
- witnessed checkpoints;
- GY-N12 status snapshot with `as_of`;
- INT-R8 proof;
- challenge/successor events;
- algorithm policy and preservation chain;
- verifier/profile/test vectors.

A package cannot authenticate a public key merely because that key is inside the package. Replacing payload, signature, and bundled key together must fail the independent trust/authority predicate.

Offline currentness is always expressed as `current as of t_q`. A stale snapshot yields historical/stale or incomplete status, never “current now.” No hidden network fallback is permitted.

Sigstore's verification bundles demonstrate the operational utility of carrying certificate, inclusion, checkpoint, and signed material together [SIG-04]. The public-record transfer requires separately authenticated institutional authority, status, epoch, preservation, and succession evidence.

## 14. Citizen verification UX

The behavior is specified in `citizen-verification-ux.md`. Required top-level outcomes include:

- `VERIFIED_CURRENT_AS_OF`;
- `AUTHENTIC_HISTORICAL_WITHDRAWN`;
- `AUTHENTIC_HISTORICAL_SUPERSEDED`;
- `AUTHENTIC_HISTORICAL_STALE`;
- `AUTHENTIC_HISTORICAL_AS_OF`;
- `TEMPORAL_VALIDITY_INDETERMINATE`;
- `COMMON_VIEW_NOT_ESTABLISHED`;
- `AUTHORITY_NOT_ESTABLISHED`;
- `PROJECTION_RELATION_NOT_ESTABLISHED`;
- `BASIS_INCOMPLETE`;
- `PROCEDURAL_HISTORY_NOT_ESTABLISHED`;
- `PRESERVATION_CHAIN_BROKEN`;
- `TAMPERED_OR_SIGNATURE_INVALID`;
- `PROFILE_OR_ALGORITHM_UNSUPPORTED`;
- `OFFLINE_CLOSURE_INCOMPLETE`.

Every current result shows authenticated `as_of`. Every human result has a machine twin and stable reason codes. Color is never the only distinction. Issuer, preservation custodian, log, witness, and status source are separately labeled.

Structurally impossible states include:

- forged FNV packet showing `Verified`;
- revoked/compromised-after-cutoff signature showing authentic/current;
- withdrawn record shown current;
- stale epoch without staleness;
- package-supplied key establishing trust;
- one log's inclusion treated as common view;
- bare `delta` shown verified;
- procedural claim shown verified without chronology;
- preservation signer shown as original issuer;
- offline status shown current beyond its cutoff;
- INT-R8 failure hidden by signature success;
- unsigned server Boolean treated as proof.

## 15. Frozen falsifier suite

> **Superseded suite version.** The v1/18-case material below is retained as audited history. Section 21.5 and `int-r7/frozen-falsifier-suite.md` §9, as remediated after verification, govern the 23-family/29-subfixture v2 specification.

`frozen-falsifier-suite.md` defines exactly 18 minimum cases:

1. attacker-chosen legacy FNV packet with correctly recomputed code;
2. replaced payload under an otherwise valid proof;
3. payload, signature, and package key replaced together;
4. post-revocation forgery with backdated signer metadata;
5. authentic pre-revocation issuance;
6. issuance inside an uncertain compromise interval;
7. stale GY-N12 epoch;
8. split-view transparency server;
9. replay under wrong audience;
10. wrong jurisdiction/authority boundary;
11. stripped/substituted `delta` basis;
12. procedural backdating/firstness substitution;
13. one compromised signer below required threshold;
14. archival verification after rotation/deprecation with timely renewal;
15. algorithm failure without timely renewal;
16. complete disconnected offline verification;
17. withdrawn-but-verifiable record;
18. successor organization identity substitution.

Exact passing result:

```yaml
suite_id: INT-R7-PV-FALSIFIERS-v1
cases_total: 18
cases_passed: 18
cases_failed: 0
unexpected_positive_outcomes: 0
offline_network_contacts: 0
human_machine_semantic_mismatches: 0
legacy_fnv_positive_authority_paths: 0
```

Any failure keeps the first-signature gate closed. Passage is not a capability, legal-compliance, or broad benchmark claim.

## 16. Repository integration handoff

### 16.1 Extend existing canonical owners

| Owner | Pinned state | INT-R7 handoff |
| --- | --- | --- |
| `core/artifacts/signing.py` | detached Ed25519 artifact signature; public lifecycle absent | extend with domain-separated public semantic statement and policy-dispatched verification; do not create competing signer owner |
| `core/security/rotation.py` | runtime/JWT/operator rotation | extend canonical control boundary with public signing authorization intervals, retirement vs compromise, and authenticated temporal events |
| `core/audit/verifier.py` | package/CAS/provenance/signature substrate | extend one predicate core for authority/time/log/witness/epoch/archive/INT-R8 verification |
| `core/audit/standalone_verifier_template.py` | portable package verification | derive offline execution from same predicate core; remove package-relative trust shortcut |
| `core/security/slsa/fulcio.py` | short-lived OIDC software-signing pattern | reuse optionally; never treat workforce identity as public authority |
| `runtime/quality/public_export.py` | real projection producer | expose INT-R8-governed commitment at proof boundary; do not move content ownership into INT-R7 |
| dashboard packet/viewer | FNV self-consistency presentation | strangle positive path; retain only rendering model or explicit negative fixture |

### 16.2 Genuine new capability classes

> **Superseded missing-state labels.** The capability labels below are retained as audited history. Section 21.4 and the repository handoff §11 govern; N-01–N-07 are absent/unallocated at the pinned commit, while the real export-to-route connection remains `bridge_missing`.

- public authority credential and organizational-succession evidence: `producer_missing` plus institutional dependency;
- trusted issuance-time and signing-time status closure: `producer_missing`, `verification_missing`;
- transparency/checkpoint/witness proof: `producer_missing`, `bridge_missing`, `verification_missing`;
- append-only public proof/status history consuming GY-N12: `producer_missing`;
- preservation evidence renewal: `producer_missing` plus OPS-R14/institutional dependency;
- independently authenticated offline trust/status closure: `producer_missing`, `verification_missing`;
- citizen outcome projection: `verification_missing`, `semantic_test_missing`;
- production route/orchestration from projection to persisted public proof: `bridge_missing`.

These labels describe the pinned commit only and do not claim a later branch is unchanged.

### 16.3 FNV strangle

P28 requires the old path to become incapable of authority:

- `signatureForPayload()` and `verifySignedPublicDecisionPacket()` cannot cause any positive authenticity/currentness state;
- legacy URLs are non-authoritative or explicitly migrated through an authorized process;
- the route consumes the canonical predicate result, not FNV;
- search/lint/semantic tests prevent future positive dependencies on the legacy verifier;
- documentation warnings do not cure a green badge.

## 17. Dependencies

## 17.1 INT-R8

Required interface:

- stable retained-claim-set commitment;
- deterministic projection/redaction proof relation;
- policy/version;
- typed outcome;
- successor relation;
- offline-verifiable evidence.

INT-R7 binds that output. It does not define public content, material omission, compression loss, or disclosure budget.

## 17.2 GY-N12

Required interface:

- epoch identity and semantic revision;
- authenticated current-head/status projection and `as_of`;
- current, stale, revalidation-required, OpenWorldRisk, unresolved-scope outcomes;
- append-only challenge/invalidation/new-epoch/reissue/withdrawal/supersession links;
- historical replay.

INT-R7 does not own revision triggers or currentness adjudication.

## 17.3 OPS-R14

Required outcomes:

- custody-grade durable proof closure;
- recovery under unavailable/compromised primary infrastructure;
- expiring authority/key/certificate/timestamp/log/witness monitoring;
- long-term replay of signed records;
- legal-hold and retention outcomes;
- tamper-evident recovery/custody transfer;
- bounded disconnected recovery drills.

INT-R7 does not choose replication topology, RPO/RTO, backup/archive product, HSM/share recovery, cloud, or legal-hold mechanics. OPS-R14's active scope is recorded in `policy-engine/docs/research/policy-operations-and-real-world-runtime-backlog.md:400-510 @ 02c5b8d`.

## 17.4 Institutional governance

Required decisions:

- competent issuing role for each claim class;
- preservation custody role and succession;
- credential/trust/timestamp/preservation recognition policy;
- key custody and optional threshold/quorum;
- log/witness independence policy;
- retention, permanent-record, legal-deposit, FOI/access, restricted-evidence, and legal-hold rules;
- compromise disclosure and succession dispute process;
- provider exit/export commitments;
- 10–30 year funding and accountability.

Cryptography cannot manufacture these institutional facts.

## 18. Open questions for consolidation

### Engineering

- canonical integration point for a versioned public statement inside the existing signing owner;
- one predicate core shared by audit verifier, standalone verifier, dashboard, and machine consumers;
- transparency/witness composition that does not duplicate DS13/GY-N12 owners;
- independent offline trust/status/checkpoint update mechanism;
- binding machine semantics to human/localized/accessibility renderings;
- privacy-safe log commitment construction;
- historical multi-algorithm verifier dispatch and preserved implementations;
- proof-closure size/deduplication/fetch without warning-only missing material;
- threshold scheme/quorum/ceremony if authorized;
- exact checkpoint status content needed to separate log consistency from record currentness.

### Institutional

- competent issuing authority and mandate evidence;
- institution accepting preservation-custody/funding/succession obligations;
- credible witness independence/quorum;
- jurisdiction-specific trust-service recognition;
- archival disposition and legal deposit;
- FOI/access handling for restricted validation evidence;
- compromise disclosure duty;
- succession dispute adjudication;
- enforceable provider exit/continuity;
- citizen support and challenge routing.

### Additional research

- target-jurisdiction profile mapping without conflating technical conformance and legal sufficiency;
- witness governance under insider/successor threats;
- privacy-preserving public commitments;
- post-quantum archival transition timing/profile;
- long-term verifier preservation/emulation/reproducibility;
- compromise-time adjudication under uncertain intervals;
- institutional succession proof across abolition/merger/devolution/privatization;
- durable accessible rendering across migration;
- independent preservation validation propositions;
- adversarial mobile usability for current/historical/withdrawn/incomplete outcomes.

The full typed list is in `repository-integration-and-dependencies.md`.

## 19. Before-first-signature gate

> **Superseded generic gate wording.** The pre-audit gate below is retained as history. Section 21.5 governs the v2 suite denominator and §21.6 governs the pre-live ceremonial and bounded first-live recovery drills.

DS12 may not emit the first public signature until all of the following are evidenced:

- versioned canonical semantic statement;
- exact claim-class/basis/history binding;
- INT-R8 projection proof;
- GY-N12 epoch/currentness interface;
- competent issuing authority and credential/mandate evidence;
- key lifecycle, rotation, compromise, and recovery policy;
- trusted issuance time and retained signing-time status;
- append-only log and independent common-view evidence;
- privacy-safe addressing;
- offline verification closure;
- algorithm/format migration policy;
- 10–30 year retention and succession commitment;
- named Public Verification Custody Owner role;
- disconnected recovery drill;
- citizen/machine semantic parity;
- FNV predecessor strangle;
- 18/18 frozen falsifiers passing with zero unexpected positive outcomes.

A technically valid signature emitted before those conditions would authenticate a weaker proposition than the architecture requires.

## 20. Result standing and exact reason

**`GO_WITH_REVISIONS`.**

> **Superseded independence wording.** The consolidation list below is retained as audited history where it says dimensions are “independent.” Section 21.2 governs: they are separately reportable and are not claimed to be logically or statistically independent.

### Safe to consolidate as research semantics

- verification is a predicate vector, not a Boolean;
- historical authenticity and current authority are independent;
- a procedural claim requires authenticated chronology, not merely a signature;
- `delta` and declared basis are one atomic signed proposition;
- trusted time/status is mandatory for pre/post-revocation distinction;
- one transparency log is insufficient against split view;
- algorithm migration appends timely preservation evidence and never rewrites originals;
- organizational succession appends custody/status evidence and never changes original issuer attribution;
- offline currentness is bounded by authenticated `as_of`;
- 10–30 year preservation must be operational before first issuance;
- existing signing/rotation/verifier/public-export owners should be extended;
- the FNV predecessor must be strangled;
- INT-R8, GY-N12, and OPS-R14 boundaries remain intact.

### Revisions/closures required before implementation authority can act

- settle target-jurisdiction institutional/legal trust profiles;
- assign issuing and preservation roles;
- close INT-R8, GY-N12, and OPS-R14 interfaces;
- select concrete signature, credential, timestamp, log/witness, preservation, and post-quantum transition profiles;
- decide witness independence/quorum and privacy-safe addressing construction;
- implement one canonical predicate verifier and production bridge;
- pass recovery and falsifier suites;
- retain the research prohibitions in downstream plans until separately authorized.

### Explicitly not established

- that the pinned repository can publish a verifiable public record;
- that any particular signature/profile is legally sufficient;
- that any institution, person, team, CA, TSA, log, witness, archive, or vendor is appointed;
- that the selected semantics authorize a final wire/schema/API;
- that a passing falsifier suite would prove production capability beyond its named implementation and environment;
- that this research grants permission to publish or automatically amends Atlas or a system-design decision.

The first-public-signature gate therefore remains closed even though INT-R7 itself is a positive research completion.

## 21. Post-audit controlling amendment

This section is the controlling primary-report amendment after audit `research/int-r7-independent-audit@54e8f41d790cb257a616c5bb5f96d996fbe3e9db`. It supersedes earlier aggregate formulas, capability labels, source uses, suite counts and dependency-status statements where they conflict with the amended supporting artifacts. It does not delete the audited text or weaken any commendation-backed result.

### 21.1 Audit verdict and preserved core

The hostile audit returned `GO_WITH_REVISIONS` with **42 findings / 42 total findings**: **1 blocking, 15 material, 6 minor and 20 commendations**. The amendment accepts that count and preserves the audit's core confirmations:

- signature validity is one bounded dimension and does not establish an administrative fact by itself;
- `signed_at` and `signer_identity` remain outside the current signed `SignatureStatement`;
- revocation remains timeless key-ID membership without effective time, reason or compromise interval;
- the current implementation therefore cannot distinguish a genuine pre-compromise signature from a later cryptographically valid forgery backdated through mutable metadata;
- `INT-K06` makes chronology and anti-backdating security semantics for the first procedural claim;
- `INT-K02` keeps `delta`, declared obligation set, maintained assumptions and rider atomic;
- correction, withdrawal and supersession append without erasing reproducible history;
- one log view is not a common view;
- preservation or successor custody never launders original issuer identity;
- INT-R7 owns proof, INT-R8 owns content/projection semantics and GY-N12 owns epoch/currentness.

### 21.2 Controlling five-dimension model

The phrase “independent predicates” is replaced by **separately reportable dimensions**. Public verification reports:

1. `IssuerIssuanceAuthentic`;
2. `ProjectionFaithful`;
3. `PublicHistoryEstablished`;
4. `DurablyVerifiableAt(t_v)`;
5. `CurrentAuthorityAsOf(t_q)`.

It additionally reports `StatusSnapshotSelection` and `EvidenceObtainability`.

A public-current positive requires all five dimensions to be established, a latest-applicable authenticated status snapshot, bounded freshness, and evidence obtainable publicly or through a competent records process. A failure of projection, witness evidence, preservation or currentness cannot retroactively negate an established issuer-side issuance event; it changes what can currently be proved or relied upon.

The exact controlling algebra is in `int-r7/threat-model-and-verification-predicates.md` §15 and `int-r7/public-verification-profile.md` §18.

### 21.3 Dependency status after INT-R8 delivery

INT-R8 was delivered after the audit at `research/int-r8-compression-loss-and-disclosure@90b372964d29a9e97605a6ef733ef03ffe7938d2`, standing `accepted_narrow_scope`. It has not been independently audited for use by this amendment. Therefore:

- INT-R8 is no longer described as absent;
- no INT-R8 conclusion is imported as established;
- every `ProjectionFaithful` positive remains hypothetical and unsatisfied;
- the item-by-item comparison against INT-R8's declared §9 offer is provisional pending its audit;
- the comparison records matches, partial matches and a disconnected/offline-evidence gap without weakening INT-R7's interface.

The provisional comparison is in `int-r7/repository-integration-and-dependencies.md` §11.3.

GY-N12 remains contract-only/planned. Every current-authority positive remains hypothetical and unsatisfied.

### 21.4 Capability honesty

The audit's sole blocking finding is executed. Research-only capability sketches are not labelled as if a consumer or wired chain already exists.

At the pinned commit:

- the artifact signer, operational rotation, audit verifier, standalone verifier substrate, Fulcio supply-chain path and public-export producer remain honestly recognized for their existing scopes;
- N-01 through N-07 and the proposed public proof/evaluator/outcome capabilities are **absent/unallocated at pinned commit**;
- the real `runtime/quality/public_export.py` producer is preserved;
- its missing production connection to the intended runtime/public surface remains correctly classified as `bridge_missing`.

The corrected evidence map is in `int-r7/repository-integration-and-dependencies.md` §11.

### 21.5 Executable falsifier suite

Suite v1 remains preserved as the audited historical specification. The controlling suite is now `INT-R7-PV-FALSIFIERS-v2`:

- **23 families / 23 total families**;
- **29 mandatory subfixtures / 29 total mandatory subfixtures**;
- exact typed values and a separate evaluation-status field;
- a static validator that rejects conditional/disjunctive/free-prose pseudo-values;
- `F-04` returns `ISSUANCE_TEMPORALLY_UNAUTHORIZED` while preserving `SignatureValid = true`;
- `F-08` preserves issuer issuance while public history/common view is non-positive;
- `F-18` includes both substitution failure and positive lawful succession;
- added signer+TSA collusion, authentic-snapshot rollback, conflicting succession, parser/canonicalization differential and selective negative-terminal withholding attacks;
- evidence obtainability is also falsified under competent restriction.

Exact v2 passage is 29/29 with zero unexpected positives, network contacts, semantic mismatches, legacy-positive paths and pseudo-value validation errors. Passage remains bounded by `S0-K16`.

### 21.6 Preservation and public access

Before the first **live public authority-bearing signature**, a representative non-authoritative/ceremonial corpus must traverse the real intended verifier, trust/status, log/witness, projection/currentness fixture, preservation and disconnected-restore paths. A paper runbook or mocked Boolean does not pass. After first live issuance, a bounded first-live-record drill restores and verifies that exact closure without converting the drill into retroactive authorization.

Recovery must detect authentic-snapshot rollback and operate from an independently governed custody domain when the primary is unavailable or suspected compromised. A lawful successor can preserve and serve predecessor evidence without becoming the original issuer. The verifier separately reports whether evidence is public, available through a competent records process, competently restricted or not established.

### 21.7 Source corrections

The amended source ledger preserves the original 30/30 source audit and adds two supplemental official rows, producing **32 source rows / 32 total rows** for the amended corpus.

- ETSI EN 319 142-1 V1.2.1 metadata is corrected to 2024-01.
- NARA `US-01` is historical-only and officially superseded; it is not current authority.
- Federal PKI `US-02` is nonbinding and Federal Register submission-specific.
- RFC 9162 supports inclusion/consistency and external observation; INT-R7's witness quorum remains a separate design inference.
- exact Sigstore bundle structure is anchored through supplemental `SIG-05`.
- current-status-limited NARA `US-03` is added without making it universally applicable.

Every source row has amended currentness/recheck metadata, and institutional guidance requires manual revalidation before consolidation or implementation.

### 21.8 Orientation correction and reproduction evidence

The supplied assertion that the INT-wave ratification occurred “four days before” the research was false and was missed in the original orientation pass. The ratification, pinned repository object and inspection date are all 2026-08-04. No substantive design conclusion follows from the correction.

The orientation ledger preserves static complete-set records for O-05 (14/14 paths) and O-09 (5/5 AST call/definition expressions) and preserves `not_established` for the exact O-02 and O-08 lexical counts. Ordinary local clone access remained unavailable; that limitation is not hidden.

### 21.9 Updated standing

**Amended standing: `GO_WITH_REVISIONS`, retained pending independent conformance verification.**

R1–R15 are executed in the amended artifacts. R16–R22 are also executed; R20 is executed with a recorded environment variation because the original complete-set outputs are preserved but a fresh independent local AST rerun was unavailable. The amendment ledger records every revision and all 42 finding dispositions.

The standing remains `GO_WITH_REVISIONS`, not `CONFORMS`, because:

- amendment execution has not yet been independently verified;
- INT-R8 remains unaudited for this seam;
- GY-N12 and OPS-R14 remain unresolved dependencies;
- the proposed public-verification capabilities remain absent/unallocated at the pinned commit;
- suite v2 and the two-phase recovery drills have not run;
- institutional roles, trust policies, retention rules and jurisdiction-specific legal mappings remain unassigned;
- no present publication capability or permission is established.

The first-public-signature gate remains closed. That is a correct outcome, not an amendment failure.

### 21.10 Anti-wire-format warning

Dimension names, predicate names, outcome names, YAML-like fixtures, lifecycle states, function-like notation and evidence classes throughout the amended research are semantic propositions and conformance vocabulary only. They do not prescribe or authorize an enum, class, database schema, event envelope, API response, package, wire format, container or vendor implementation.

### 21.11 Bounded remediation status

Conformance findings `INT-R7-V-102`, `INT-R7-V-103`, and `INT-R7-V-104` are closed at the authoring level by reachable supersession markers, a self-consistent typed validator/baseline, and separation of issuer-side declaration from requested-use and released-history predicates. Standing remains **`GO_WITH_REVISIONS` pending independent delta-only re-verification**. The first-public-signature gate remains closed.