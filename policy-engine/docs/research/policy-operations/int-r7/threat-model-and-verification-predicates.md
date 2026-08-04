---
title: INT-R7 — Threat Model and Verification Predicates
research_id: INT-R7
status: delivered
result_standing: GO_WITH_REVISIONS
repository: https://github.com/DenisKopylov/polisyos
repository_branch_inspected: main
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

# Threat model and verification predicates

## 1. Security question

A public verifier does not ask only whether a signature equation holds. The verifier asks a compound, time-indexed institutional question:

> Does the evidence establish that these exact claim semantics were issued by an authority entitled to issue that claim, no later than an independently evidenced time, under the declared epoch and basis, entered a publicly comparable append-only history, and retain the stated historical or current standing at the verifier's authenticated `as_of` cutoff?

The answer is a vector of predicates, never a single undifferentiated Boolean.

The distinction is mandatory for PolicyOS because:

- `INT-K06` makes the first likely public claim a procedural custody statement about a history, not a probability;
- `INT-K02` makes a `delta` inseparable from its declared obligation set, maintained assumptions, and relative-basis rider;
- `INT-K01` and `S0-K08` require correction by append-only challenge, invalidation, new epoch, and reissue rather than historical rewriting;
- GY-N12 owns epoch/currentness semantics, so cryptographic authenticity cannot become a parallel status lattice; and
- `S0-K16` limits every passage result to the named implementation, revision, environment, evaluator, and tested predicates.

Repository anchors: `policy-engine/docs/system-design-decisions/int-wave-claim-semantics-ratification.md:1-379 @ 02c5b8d`; `policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:1-264 @ 02c5b8d`.

## 2. Protected objects

Let:

- `R` be the original governed decision record or custody statement;
- `C(R)` be the canonical semantic commitment to `R` under a named canonicalization/profile version;
- `P8(R)` be the projection/content relation and retained-claim commitment supplied by INT-R8;
- `B(R)` be the declared obligation set and maintained assumptions when the claim class is probabilistic;
- `H(R)` be the sealed chronology/prospectivity/firstness evidence when the claim class is procedural;
- `E(R)` be the GY-N12 epoch identity and semantic revision reference;
- `A(R)` be the claimed authority boundary, jurisdiction, audience, and claim class;
- `S` be the issuing signature and signer credential evidence;
- `T` be trusted issuance-time evidence and signing-time status evidence;
- `L` be transparency inclusion and append-only consistency evidence;
- `W` be independently governed checkpoint/witness evidence;
- `M` be preservation-renewal and algorithm/format migration evidence;
- `Q_v` be the authenticated status/currentness snapshot used by verifier `v`;
- `t_v` be the verifier's evaluation time; and
- `t_q` be the `as_of` cutoff authenticated by `Q_v`.

The proof lifecycle protects both the **original evidence** and the **meaning assigned to it**. A byte-perfect signature can still authenticate a false or incomplete semantic statement if the signed payload omits its audience, epoch, authority boundary, obligation basis, or chronology.

## 3. Verifier populations

### 3.1 Citizen verifier

Typical environment:

- phone or ordinary browser;
- may have intermittent connectivity;
- may scan a QR code or open a public URL;
- cannot be expected to understand PKI path building, Merkle proofs, algorithm deprecation, or GY-N12;
- may possess only the record, a proof closure, and a small independently authenticated trust application/snapshot.

Required result:

- plain-language bounded outcome;
- clear `as_of` time;
- visible separation of historical authenticity and current authority;
- a copyable machine report and challenge/access path;
- no silent live dependency when “offline” is claimed.

### 3.2 Journalist or civil-society monitor

Typical environment:

- verifies many records;
- retains checkpoints and compares public views;
- may mirror a transparency history;
- may seek evidence after an agency removes or changes its website;
- may correlate records, but must not be forced to disclose which record is being checked to a live status responder.

Required result:

- inclusion and consistency proofs;
- witnessed checkpoints and evidence of equivocation;
- bulk/machine verification;
- stable reason codes;
- retained historical and successor links.

### 3.3 Another public authority

Typical environment:

- configured institutional trust policies;
- may need cross-agency or cross-border recognition;
- must distinguish credential-chain validity from competence to issue this claim class;
- may need to verify after organizational succession.

Required result:

- authority/mandate/term evidence;
- jurisdiction, audience, claim class, and authority-boundary binding;
- policy identifiers and status at issuance;
- successor-custody evidence without retroactive identity substitution.

### 3.4 Court, tribunal, auditor, or archival institution

Typical environment:

- verifies years or decades later;
- needs original bytes, validation policies, status evidence, custody events, and preservation renewals;
- may not accept a live service's current answer as proof of historical state;
- may need to explain uncertainty rather than force a pass/fail conclusion.

Required result:

- complete validation closure;
- original-versus-preservation signer distinction;
- signing-time status and compromise interval evidence;
- format/hash/algorithm migration lineage;
- reproducible bounded report and retained verifier/test vectors.

### 3.5 Machine verifier

Typical environment:

- deterministic batch or API consumer;
- must not trust a server-supplied `verified: true` field;
- consumes independently authenticated trust/status inputs;
- may operate in a disconnected enclave.

Required result:

- predicate vector, evidence identifiers, policy versions, `as_of`, and typed terminal outcome;
- identical semantics to the human projection;
- no permissive unknown-algorithm or missing-evidence fallback.

## 4. Adversary capabilities

The profile assumes an adaptive adversary. Different adversaries may collude unless an explicit non-collusion assumption is named.

### A-01 — presentation and transport attacker

Controls or can alter:

- URL, QR code, page HTML, JavaScript bundle, browser storage, network response, downloadable package, and human-readable rendering;
- record bytes in transit;
- a server-provided “verified” badge or result field.

Observes:

- public records, public keys, salts, algorithms, proof formats, and verifier behavior.

Goals:

- make a replaced packet render `Verified`;
- substitute a different audience/jurisdiction/epoch;
- hide a withdrawal or successor;
- induce the verifier to trust a package-supplied key.

Required defence:

- independently authenticated trust root/snapshot;
- domain-separated signature over exact semantics;
- deterministic verification, not server assertion;
- no authority from the current public-salt FNV mechanism.

### A-02 — repository/application compromise attacker

Controls:

- current PolicyOS application server, database, object store, public route, or deployment key;
- may serve different records or checkpoints to different users;
- may omit status events or block access.

Does not necessarily control:

- historical independently retained checkpoints, witnesses, trusted timestamp evidence, or archived proof closures.

Goals:

- equivocate;
- rewrite history;
- erase a negative/refusal record;
- publish an unsigned or incompletely bound record;
- falsely label stale data current.

Required defence:

- append-only commitments;
- independent checkpoint witnesses/mirrors;
- offline proof closures;
- separate authority/status predicates;
- fail-closed missing material.

### A-03 — signing-key compromise attacker

Controls:

- one active signing key or enough threshold shares to meet the configured threshold;
- may know the key compromise time before defenders do;
- can create cryptographically valid signatures and backdate self-declared metadata.

Goals:

- forge a record after compromise and claim it predates revocation;
- issue under a wrong audience, jurisdiction, authority boundary, epoch, or basis;
- sign a procedural chronology that was not prospectively sealed.

Required defence:

- trusted issuance time independent of signer-controlled fields;
- signing-time credential/status evidence;
- transparency chronology and witnessed checkpoints;
- narrow credential/mandate scope;
- optional threshold/multi-party authorization;
- rapid freeze/revocation and uncertainty intervals.

Residual risk:

- if an authorized malicious signer signs a false statement while all controls attest only possession/authority, cryptography does not prove substantive truth. Procedural claims therefore require separately committed chronology/adjudication evidence.

### A-04 — malicious insider below signing threshold

Controls:

- record preparation, source selection, metadata, package assembly, or one custody/share role;
- may suppress negative evidence or attempt prohibited substitution;
- may exploit a signing service that signs opaque bytes.

Goals:

- obtain a valid signature over semantically incomplete content;
- remove the declared obligation set while retaining `delta`;
- change claim class from refusal/procedural to measurement;
- bypass independent review.

Required defence:

- semantic pre-sign validation;
- domain-separated, human-reviewable statement commitment;
- role separation/threshold where authorized;
- sealed chronology and append-only negative terminals;
- INT-R8 projection proof;
- no opaque “sign this digest” authority without bound semantics.

### A-05 — authorized malicious quorum or senior insider

Controls:

- enough signers/administrators to satisfy normal authorization;
- may also control the primary log and publication server.

Goals:

- issue a malicious but policy-shaped record;
- suppress later challenge or withdrawal;
- present split views.

Required defence and limit:

- external witnesses, public monitors, archives, and challenge/currentness history can make conduct detectable;
- no cryptographic construction can prevent an institutionally authorized quorum from making the exact statement it is authorized to make;
- the profile can prove who, what, when, scope, history, and later status, not the correctness of the underlying policy judgment.

### A-06 — certification, timestamp, identity-provider, or trust-service attacker

Controls one or more of:

- CA/registration authority;
- OCSP/CRL/status service;
- timestamp authority clock/key;
- workforce/OIDC identity provider;
- preservation service.

Goals:

- misissue a credential;
- lie about time or status;
- erase or fabricate preservation evidence;
- make a short-lived workforce identity appear to be public authority.

Required defence:

- explicit trust and policy identifiers;
- retained evidence and independent corroboration;
- separation of OIDC identity from institutional competence;
- multiple/heterogeneous witnesses where policy requires;
- compromise events and revalidation;
- no claim that one qualified or commercial service is infallible.

Residual risk:

- if the trusted-time service and signer collude and no independent chronology exists, backdating may be undetectable. The relevant assumption must be visible in the verification report.

### A-07 — transparency-log split-view attacker

Controls:

- one log operator and its signing key;
- can present internally consistent but different trees to different verifiers;
- can delay inclusion or deny service.

Goals:

- give citizens a sanitized view and insiders a different view;
- hide a forged or withdrawn record from selected monitors.

Required defence:

- inclusion and consistency proof verification;
- independently obtained, signed checkpoints;
- witness quorum/gossip/cross-publication under an explicit independence policy;
- cached checkpoints and monitor evidence.

Residual risk:

- Merkle mathematics alone establishes consistency inside a supplied view, not that all verifiers share one view.

### A-08 — archival/storage attacker

Controls:

- archive bytes, manifests, migration outputs, or old verifier packages;
- may delete status evidence while retaining the visible document;
- may replace payload, signature, and bundled public key together.

Goals:

- make a derivative look original;
- make an untrusted package self-authenticate;
- break old validation silently;
- rewrite preservation events.

Required defence:

- independently authenticated trust/checkpoint snapshots;
- original-byte retention and fixity;
- append-only preservation-event chain;
- timely re-anchoring under acceptable algorithms;
- recovery drills in a clean disconnected environment.

### A-09 — successor-organization adversary

Controls:

- infrastructure, records, staff, and public domain of a predecessor after merger, abolition, privatization, or reorganization;
- may possess predecessor public/private material or only custody copies;
- may publish a new trust policy.

Goals:

- rewrite predecessor records;
- present itself as the original issuer;
- suppress inconvenient records;
- declare every predecessor record current or void without a competent status process.

Required defence:

- predecessor signatures remain attributed to predecessor and issuance interval;
- succession/custody statements are appended under successor credentials;
- independent archives/witnesses preserve earlier checkpoints;
- current authority comes through GY-N12/competent status owners;
- conflicting succession evidence yields an explicit dispute/unknown outcome.

### A-10 — political or administrative suppression adversary

Controls:

- publication timing, budget, access channel, records request response, or institutional priority;
- may not break cryptography.

Goals:

- prevent access to proof material;
- publish only positive terminals;
- delay compromise disclosure;
- make verification technically possible but practically inaccessible.

Required defence and limit:

- public/offline copies, legal deposit/archival custody, monitors, and explicit access obligations;
- retained negative/refusal and withdrawal events;
- citizen UX and machine twin;
- technical design cannot establish institutional competence, FOI compliance, or lawful disclosure on its own.

### A-11 — verifier-environment attacker

Controls:

- verifier binary, dependency, trust snapshot, system clock, locale, or UI translation;
- may downgrade algorithms or hide reason codes.

Required defence:

- independently inspectable verifier;
- preserved build/dependency metadata and test vectors;
- signed policy/trust snapshots;
- no reliance on local wall clock for historical issuance;
- semantic parity tests across human/machine/locales;
- `S0-K16`-bounded conformance reports.

### A-12 — privacy attacker

Observes:

- public record locators, log leaves, status queries, issuance cadence, checkpoint size, and verifier network calls.

Goals:

- enumerate low-entropy or restricted records;
- infer identity or policy activity;
- correlate a citizen's verification query with a sensitive record.

Required defence:

- high-entropy public locators or hiding commitments with retained opening material;
- batched roots where appropriate;
- no raw PII or predictable case number as public log key;
- offline/stapled status evidence rather than per-record live queries where feasible;
- INT-R8 owns what content may be disclosed.

## 5. Trust assumptions

The profile cannot eliminate trust. It makes each assumption explicit and assigns a failure result.

| Assumption | Property relied on | Guarantee while assumption holds | Result when assumption degrades |
| --- | --- | --- | --- |
| Signature suite | EUF-CMA for the named suite and parameters | an attacker without sufficient signing authority cannot produce a new valid statement signature | if broken before timely renewal: `historical_authenticity_not_established`; after timely renewal: evaluate preservation chain |
| Content/hash commitment | collision and second-preimage resistance | replacement bytes cannot retain the same accepted commitment within policy | if weakened before migration: affected evidence becomes indeterminate; later hashing alone cannot repair ambiguity |
| Merkle log | collision/second-preimage resistance and correct inclusion/consistency verification | leaf membership and append-only extension relative to checkpoints | log proof invalid or unsupported; does not itself decide common view |
| Witness policy | sufficient independent witnesses do not collude and their keys/policies are valid | compared checkpoints establish common view to the declared quorum/independence policy | `common_view_not_established`; signature may remain valid |
| Trusted time | timestamp key, clock, policy, and validation evidence were valid | committed datum existed no later than the trusted time | `issuance_time_not_established`; do not infer pre-revocation issuance |
| Credential/trust path | authentic trust roots, correct path/status evaluation, competent issuance policy | key was credentialed for the declared role/purpose/interval | `authority_or_credential_not_established` |
| Authority evidence | mandate/delegation/succession evidence is authentic and interpreted by competent policy | signer role was within the declared authority boundary at issuance | no claim of institutional authority; signature math alone remains insufficient |
| GY-N12 status | authenticated canonical epoch/currentness snapshot | current/stale/withdrawn state is known as of `t_q` | historical result only; `current_authority_not_established` |
| INT-R8 proof | INT-R8-defined projection relation verifies | signed commitment corresponds to the governed retained public projection | `public_projection_not_established`; INT-R7 must not redefine content safety |
| Preservation renewal | each renewal occurred before prior evidence lost trust and covers complete prior closure | historical evidence remains verifiable under later acceptable suites | `preservation_chain_broken`; original bytes alone are insufficient |
| Verifier | implementation matches profile/policy for named revision and environment | reported predicates reflect tested semantics | result bounded or invalid; no broad benchmark/capability claim |

## 6. Verification input closure

A verifier may be online or offline, but it must identify the same semantic inputs.

Required inputs, directly or by authenticated reference:

1. original canonical semantic statement and record commitment;
2. claimed profile/domain/version and canonicalization identity;
3. signature(s) and signer credential/authority evidence;
4. trusted issuance-time token/evidence;
5. status/revocation/compromise evidence applicable to the issuance interval;
6. algorithm policy applicable to issuance and verification;
7. transparency leaf, inclusion proof, checkpoint, and consistency evidence;
8. independent witness/checkpoint evidence and witness policy;
9. GY-N12 epoch identity and authenticated status snapshot;
10. INT-R8 retained-claim/projection relation proof;
11. challenge, invalidation, withdrawal, supersession, and successor links;
12. preservation and migration chain;
13. trust roots/policies authenticated independently of the record package; and
14. verifier/profile specification and bounded test-vector identity.

If one mandatory item is unavailable, the verifier emits the corresponding incomplete predicate. It does not silently switch to “signature only.”

## 7. Predicate vector

Let `V(R, I, t_v)` return a vector over record `R`, evidence/input closure `I`, and verification time `t_v`.

### 7.1 Integrity and statement predicates

- `CanonicalStatementRecognized`: profile and canonicalization version are supported and unambiguous.
- `ContentBound`: recomputed commitments match the exact record/projection/evidence objects.
- `SignatureValid`: all required issuing signatures satisfy the named signature policy.
- `ClaimClassBound`: procedural/refusal/measurement class is signed and not inferred from rendering.
- `AudienceBound`: intended verifier/audience class is signed and matches use.
- `JurisdictionBound`: jurisdiction and recognition policy are signed and accepted for this evaluation.
- `AuthorityBoundaryBound`: the claimed authority purpose/scope is signed.
- `EpochBound`: GY-N12 epoch identity and semantic revision are signed.
- `BasisBound`: for a `delta` claim, declared obligation set, maintained assumptions, and relative-basis rider are signed atomically with the number.
- `ProceduralHistoryBound`: for a procedural claim, prospectivity, sealing, chronology, substitutions/deviations, adjudication, dissent, and negative terminals are committed as required by the claim profile.
- `ProjectionRelationValid`: INT-R8's retained-claim/redaction relation verifies.

A failure of `BasisBound` is not cosmetic incompleteness. It is semantic substitution: the authenticated statement is a different, false bare-`delta` claim under `INT-K02`.

### 7.2 Signer and temporal predicates

- `SignerCredentialValidAtIssuance`: credential/path/purpose/validity/status evidence validates at the trusted issuance interval.
- `AuthorityValidAtIssuance`: the signer role/mandate was competent for the exact claim class, authority boundary, jurisdiction, and interval under the configured institutional policy.
- `TrustedIssuanceTimeEstablished`: independent evidence bounds issuance no later than `t_s`.
- `PreCompromiseOrRevocationEstablished`: `t_s` is strictly before the applicable revocation/compromise cutoff, or outside a declared compromise interval, under the policy.
- `TemporalValidityIndeterminate`: signature math passes but evidence cannot order issuance against the compromise/revocation interval.

A self-declared `signed_at` field does not satisfy `TrustedIssuanceTimeEstablished`.

### 7.3 Transparency and common-view predicates

- `LogIncluded`: the exact commitment has a valid inclusion proof in checkpoint `h_n`.
- `LogAppendOnlyConsistent`: required consistency proofs connect retained checkpoints under the declared log policy.
- `WitnessPolicySatisfied`: enough independently governed witnesses signed/observed the required checkpoint relation.
- `CommonViewEstablished`: inclusion/consistency plus witness policy establish the same declared history for the bounded observer set.

`LogIncluded` does not imply `CommonViewEstablished`.

### 7.4 Epoch and authority predicates

- `EpochHistoricallyAuthentic`: the record's signed epoch exists and its historical closure evidence validates.
- `StatusSnapshotAuthentic`: `Q_v` is authenticated and names cutoff `t_q`.
- `CurrentAuthorityAtAsOf`: GY-N12/current-authority owner says the record is current at `t_q`.
- `StaleAtAsOf`: revalidation trigger crossed at or before `t_q`.
- `WithdrawnAtAsOf`: current authority explicitly withdrawn at or before `t_q`.
- `SupersededAtAsOf`: successor record/epoch is authoritative at or before `t_q`.
- `ChallengePendingAtAsOf`: an unresolved challenge affects the permitted top-level projection under the canonical status policy.

An offline verifier can establish these only **as of `t_q`**. It must not claim “current now” when `t_q < t_v` unless policy supplies an authenticated freshness guarantee covering that interval.

### 7.5 Preservation predicates

- `OriginalBytesRetained`: original signed bytes are available and fixity validates.
- `ValidationMaterialComplete`: certificates, status, timestamp, policies, checkpoints, witnesses, and required authority evidence are present.
- `PreservationChainValid`: every renewal covers the complete prior closure and occurred while the prior evidence was still acceptable.
- `AlgorithmPolicySatisfied`: each primitive is accepted for its historical/preservation purpose under the named policy.
- `VerifierClosureComplete`: profile, verifier, dependencies/test vectors, and reason-code semantics are sufficient for the bounded evaluation.

## 8. Formal result predicates

For compactness, define:

```text
StatementComplete(R) :=
    CanonicalStatementRecognized
  ∧ ContentBound
  ∧ ClaimClassBound
  ∧ AudienceBound
  ∧ JurisdictionBound
  ∧ AuthorityBoundaryBound
  ∧ EpochBound
  ∧ ProjectionRelationValid
  ∧ (claim_class != delta ∨ BasisBound)
  ∧ (claim_class != procedural ∨ ProceduralHistoryBound)
```

```text
IssuanceAuthentic(R, t_s) :=
    StatementComplete(R)
  ∧ SignatureValid
  ∧ SignerCredentialValidAtIssuance
  ∧ AuthorityValidAtIssuance
  ∧ TrustedIssuanceTimeEstablished
  ∧ PreCompromiseOrRevocationEstablished
```

```text
PublicHistoryEstablished(R) :=
    LogIncluded
  ∧ LogAppendOnlyConsistent
  ∧ WitnessPolicySatisfied
  ∧ CommonViewEstablished
```

```text
HistoricalAuthenticity(R, t_v) :=
    IssuanceAuthentic(R, t_s)
  ∧ PublicHistoryEstablished(R)
  ∧ EpochHistoricallyAuthentic
  ∧ OriginalBytesRetained
  ∧ ValidationMaterialComplete
  ∧ PreservationChainValid
  ∧ AlgorithmPolicySatisfied
```

```text
CurrentAuthority(R, t_q) :=
    StatusSnapshotAuthentic
  ∧ CurrentAuthorityAtAsOf
  ∧ ¬StaleAtAsOf
  ∧ ¬WithdrawnAtAsOf
  ∧ ¬SupersededAtAsOf
  ∧ permitted_by_canonical_challenge_policy
```

```text
VerifiedCurrent(R, t_v, t_q) :=
    HistoricalAuthenticity(R, t_v)
  ∧ CurrentAuthority(R, t_q)
  ∧ freshness_claim_is_bounded_to(t_q)
```

```text
WithdrawnButVerifiable(R, t_v, t_q) :=
    HistoricalAuthenticity(R, t_v)
  ∧ StatusSnapshotAuthentic
  ∧ WithdrawnAtAsOf
  ∧ ¬CurrentAuthorityAtAsOf
```

```text
SupersededButVerifiable(R, t_v, t_q) :=
    HistoricalAuthenticity(R, t_v)
  ∧ StatusSnapshotAuthentic
  ∧ SupersededAtAsOf
  ∧ successor_link_valid
  ∧ ¬CurrentAuthorityAtAsOf
```

No top-level `Verified` result is permitted without specifying which predicate is meant.

## 9. Revocation and compromise semantics

Let:

- `t_s` be the latest time by which trusted evidence proves the signature/commitment existed;
- `t_r` be the authenticated effective revocation time;
- `[t_c_min, t_c_max]` be the best supported compromise interval;
- `t_ret` be normal retirement cutoff for new signing.

### 9.1 Normal retirement

If `t_s < t_ret` and no compromise evidence applies:

- historical signature may validate;
- new signatures after `t_ret` are unauthorized;
- current record standing is evaluated separately.

### 9.2 Prospective revocation without alleged prior compromise

If policy states revocation effective at `t_r` and `t_s < t_r`:

- the record may be historically authentic;
- current key authorization is false after `t_r`;
- record currentness is not automatically withdrawn unless the canonical status owner says so.

If `t_s >= t_r`, the signature is unauthorized for issuance.

### 9.3 Known compromise cutoff

If authenticated evidence establishes compromise no later than `t_c`:

- `t_s < t_c` may pass subject to policy and other evidence;
- `t_s >= t_c` fails `PreCompromiseOrRevocationEstablished`;
- backdated signer metadata cannot override trusted time.

### 9.4 Uncertain compromise interval

If `t_s` overlaps `[t_c_min, t_c_max]` and no stronger evidence resolves order:

- `SignatureValid` may be true;
- `TemporalValidityIndeterminate` is true;
- `HistoricalAuthenticity` and `VerifiedCurrent` are false/undetermined;
- the UI must not downgrade this to a warning on a green result.

### 9.5 Revocation evidence unavailable

If the verifier cannot retrieve or preserve status applicable to issuance:

- do not infer “not revoked” from absence;
- return `signing_time_status_not_established`;
- live current status years later is not a substitute for historical status evidence.

## 10. Procedural claim threat model

Under `INT-K06`, the first public signature likely attests a bounded procedural history: prospectivity, firstness, sealing, chronology, no prohibited substitution, adjudication, dissent, published negatives, or a governed refusal. The proposition is about **events and order**, so chronology is part of the authenticated semantics.

Threats specific to procedural claims:

- record prepared after outcome but backdated;
- “first candidate” substituted after inspection;
- negative/refusal terminal omitted from public history;
- sealed inputs reopened without a logged deviation;
- adjudicator or dissent evidence replaced;
- sequence-level probability reintroduced in a rendering despite its withdrawal;
- a later preservation signature represented as original prospective sealing.

Required predicates:

- prospective seal commitment precedes governed outcome under trusted time;
- each allowed substitution/deviation is append-only and typed;
- chronology edges are committed and log-consistent;
- identity of evaluator/adjudicator versions is bound;
- negative terminals are included in the same public history policy;
- the claim class explicitly carries no probability;
- a verifier can falsify “firstness” or “no prohibited substitution” from contradictory logged evidence.

A valid signature over an unproved narrative of chronology is not a verified procedural claim.

## 11. `delta` claim threat model

A later probabilistic claim is complete only when the signed statement binds:

- the numeric `delta`;
- declared obligation set identifier/commitment;
- maintained assumptions identifier/commitment;
- relative-basis rider;
- evaluation/proof profile and revision;
- relevant audience, jurisdiction, authority boundary, and epoch.

Attacks:

- strip the declared set and show a bare number;
- substitute a smaller obligation set while preserving the displayed `delta`;
- change maintained assumptions without reissue;
- present an historical basis as current after a new obligation is discovered;
- translate the rider away in one locale;
- sign a number separately from the statement that defines its basis.

Security classification:

- this is **semantic substitution**, not merely misleading copy;
- the signature must cover the complete statement atomically;
- discovery of a missed obligation triggers challenge/invalidation/new epoch/reissue under `INT-K01`; it does not alter old bytes or claim the earlier computation never occurred.

## 12. What verification does not prove

Even `VerifiedCurrent` does not establish:

- that the policy is wise, fair, lawful, effective, or cost-beneficial;
- that an external institution actually performed an administrative function;
- that the signer's institution has legal competence in every jurisdiction;
- that the public projection is materially complete beyond the INT-R8 contract;
- that source evidence is true merely because its commitment is signed;
- that a qualified signature or certificate is legally sufficient for the intended proceeding;
- that an authorized malicious quorum did not make an intentionally false substantive statement;
- that an offline status snapshot remains current after its authenticated `as_of` cutoff;
- that one passing implementation proves a general cryptographic theorem or production capability.

## 13. Failure ordering

The verifier must preserve multiple failures, but top-level citizen outcomes should prioritize safety:

1. unrecognized/ambiguous profile or canonicalization;
2. content/signature tamper;
3. package-relative trust/self-key substitution;
4. authority/credential failure;
5. issuance-time/status/compromise indeterminacy;
6. projection/basis/procedural semantic incompleteness;
7. transparency/common-view failure;
8. preservation-chain/algorithm failure;
9. epoch/status currentness result;
10. bounded current or historical outcome.

This ordering prevents a mathematically valid signature from masking a more important authority, time, common-view, or currentness failure.

## 14. Threat-model conclusion

The decisive security property is not “Ed25519 verification succeeds.” It is the conjunction of exact statement binding, institutional authority-at-time, trusted chronology, witnessed append-only publication, canonical epoch/currentness, INT-R8 projection relation, and timely preserved migration evidence. Each layer has a distinct assumption and a distinct failure outcome. That separation is what makes `withdrawn-but-verifiable`, post-compromise recovery, split-view detection, organizational succession, and twenty-year offline verification representable without rewriting history.
