---
title: INT-R7 — PublicVerificationProfile Semantic Contract
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

# `PublicVerificationProfile`

## 1. Standing and scope

`PublicVerificationProfile` is an owner-neutral semantic contract for creating, preserving, and verifying a public cryptographic proof over a governed PolicyOS decision record. It specifies:

- the proposition that must be bound;
- the roles and evidence classes that may support it;
- the temporal and algorithm policy needed to evaluate it;
- the proof closure an offline verifier must possess;
- the separation between historical authenticity and current authority; and
- the exact classes of failure that must remain visible.

It deliberately does **not** specify a final wire format, package name, database table, API, serialization, certificate authority, timestamp service, transparency-log operator, witness, archive, vendor, team, person, or jurisdictional legal conclusion.

The profile is consumed by DS12 and later DS13 work. It extends existing signing, rotation, verification, and public-export owners rather than authorizing duplicate owners. Repository integration is specified separately in `repository-integration-and-dependencies.md`.

## 2. Profile proposition

A conforming proof attests only this bounded proposition:

> An identified issuing authority role, acting within a declared authority boundary, jurisdiction, audience, claim class, and authorization interval, signed the exact canonical semantic statement for the named PolicyOS record and GY-N12 epoch; independently evidenced time and signing-time status support the issuance interval; the record commitment entered a declared append-only public history whose checkpoint was corroborated under the declared witness policy; the proof binds the INT-R8 projection relation and any claim-specific basis or procedural chronology; and the supplied status/preservation evidence supports the stated historical or current outcome as of an authenticated cutoff.

The proof does not itself establish substantive policy truth, legal sufficiency, institutional competence beyond the supplied authority evidence and configured policy, or the safety/completeness of content beyond the INT-R8 interface.

## 3. Claim classes

The claim class is signed, not inferred from a page heading.

### 3.1 `procedural_custody_claim`

A binding, falsifiable statement carrying no probability, as required by `INT-K06`. It may attest bounded propositions such as:

- prospective sealing occurred before a named event;
- this was the first admitted candidate under a named protocol;
- prohibited substitution did not occur within the recorded history;
- every allowed deviation was declared and appended;
- chronology and adjudication steps occurred in the committed order;
- dissent and negative/refusal terminals were published under the same history policy.

Its truth is about a history. Trusted chronology and anti-backdating are therefore part of the core proof, not optional metadata.

### 3.2 `honest_refusal`

A signed negative terminal stating that the system did not make the stronger governed claim and naming the bounded reason/profile/epoch. The refusal must be as visible and append-only as a positive terminal; omission of refusals from the public history would defeat `INT-K06`.

### 3.3 `bounded_delta_claim`

A later claim carrying `delta`. Under `INT-K02`, the signature must bind atomically:

- the numeric value;
- declared obligation-set commitment;
- maintained-assumptions commitment;
- relative-basis rider;
- proof/evaluation profile and revision;
- relevant environment/evaluator identity where required by `S0-K16`.

A bare `delta` is a different and false claim. Verifying a signature over the number alone is not partial success.

### 3.4 Other claim classes

Additional claim classes require separate ratified semantics before they may use this profile. An unknown claim class fails closed; it is not treated as procedural or informational by default.

## 4. Canonical semantic statement

The statement is a versioned semantic object whose final encoding remains open. Every conforming encoding must produce unambiguous canonical bytes and preserve the following semantic commitments.

### 4.1 Domain and profile binding

Bind:

- PolicyOS public-proof domain separator;
- `PublicVerificationProfile` semantic version;
- claim-class profile/version;
- canonicalization identity/version;
- commitment/hash algorithm identities and parameters;
- signature policy identity/version;
- algorithm-policy identity/version.

A signature valid under another domain or profile is not reusable.

### 4.2 Record identity and commitments

Bind:

- high-entropy public record identifier or hiding-commitment identifier;
- canonical semantic record commitment;
- original governed-record commitment where public and governed objects differ;
- human-rendering/accessibility representation commitments or a verified transformation relation;
- proof/evidence-set commitment sufficient to identify the issuance closure;
- predecessor/successor/supersession references when applicable.

A public URL, database row number, filename, or low-entropy case number is not by itself an authenticated record identity.

### 4.3 INT-R8 projection interface

Bind exactly the interface supplied by INT-R8:

- retained-claim-set commitment;
- projection/redaction policy identity/version;
- deterministic projection relation or proof reference;
- typed INT-R8 outcome;
- successor relation when a new public projection supersedes an earlier one.

INT-R7 does not define which claims are retained, what omission is material, what `lossy_but_safe` means, what `blocked_material_omission` means, or how disclosure budgets compose. If INT-R8 cannot produce its required pass relation, public proof issuance is blocked even when signature predicates would otherwise pass.

### 4.4 Claim semantics

Bind:

- claim class;
- exact proposition identifier/version;
- bounded natural-language label or semantic description commitment;
- declared authority effect: historical custody statement, current authority statement, refusal, or another ratified effect;
- explicit statement that cryptographic verification does not establish legal compliance or substantive policy truth.

### 4.5 Procedural history binding

For `procedural_custody_claim`, bind the profile-required history commitments, including as applicable:

- prospective seal event and trusted-time evidence reference;
- firstness population/ordering commitment;
- chronology graph or event-chain commitment;
- prohibited-substitution rule identity;
- admitted deviation/substitution events;
- evaluator/adjudicator identities or role evidence and version;
- dissent commitment;
- negative/refusal terminal set commitment;
- outcome-informed repair/deviation disclosure;
- statement that no sequence-level probability is claimed where the ratified protocol withdrew it.

The statement need not expose restricted details; it must bind whatever evidence the claim profile requires and allow a verifier to detect contradiction or absence.

### 4.6 `delta` basis binding

For `bounded_delta_claim`, bind:

- exact `delta` representation;
- declared-obligation-set identity and collision-resistant commitment;
- maintained-assumptions identity and commitment;
- relative-basis rider;
- proof-scope/evaluation-family identity;
- allocation/composition policy identity when applicable;
- evaluation revision/environment/evaluator version required by `S0-K16`;
- explicit non-transfer statement beyond the declared set and assumptions.

Changing any basis element requires a new signed record/epoch. The old statement remains historically reproducible.

### 4.7 Audience and jurisdiction binding

Bind:

- intended audience class or set;
- relying-purpose identifier;
- jurisdiction/recognition-policy identifier;
- language/locale semantic version where human labels carry meaning;
- any cross-agency or cross-border policy profile relied on.

A valid signature replayed under a different audience or jurisdiction fails the corresponding binding predicate unless an authenticated policy explicitly permits that transfer.

### 4.8 Authority-boundary binding

Bind:

- issuing organization identity at issuance;
- issuing authority role, not merely a person's name;
- authority/mandate/delegation evidence identifier and commitment;
- permitted claim class/purpose;
- authority validity interval or event reference;
- separation-of-duty/threshold policy identity if required;
- custody role identity where distinct from issuing authority;
- predecessor/successor institutional relation evidence when later appended.

Possession of a key, workforce account, certificate, archive, or domain name is not authority by itself.

### 4.9 Epoch and currentness binding

Bind:

- GY-N12 epoch identity;
- semantic/model revision commitment;
- closure cutoff or relevant revision-trigger references;
- status/current-head reference format defined by the canonical owner;
- challenge/invalidation/reissue/supersession/withdrawal links as later append-only events.

The signature does not create or own GY-N12 status. It authenticates the epoch/status references it consumes.

### 4.10 Temporal binding

Bind or reference under authenticated commitments:

- signer authorization interval;
- key/credential authorization interval;
- trusted issuance-time token/evidence;
- transparency inclusion/checkpoint time or order evidence;
- effective revocation/retirement/compromise events when later appended;
- `not_before`/`not_after` semantics for **new issuance authority**, if the authority profile uses them;
- verification/status snapshot `as_of` cutoff;
- preservation-renewal event times and policy deadlines.

A signer-controlled `signed_at` display field is informative only unless covered by independently trusted time.

### 4.11 Privacy-safe public addressing

Bind:

- a high-entropy random public locator, or a hiding commitment with retained opening material;
- commitment-domain separation from other PolicyOS identifiers;
- batching/tree position evidence where a public root is used;
- locator policy/version.

Do not require publication of:

- raw PII;
- predictable citizen/case/application identifiers;
- unsalted hashes of low-entropy record attributes;
- live per-record status queries that disclose the citizen's interest when stapled/offline evidence can serve the predicate.

The content disclosed at the public boundary remains an INT-R8 decision.

## 5. Issuing and preservation roles

## 5.1 Issuing authority role

The issuing signature is made by a role that is independently evidenced as authorized for the exact claim class, jurisdiction, audience, authority boundary, and interval. A person may operate the role, but the public statement binds the institutional role and authority evidence, not merely a personal label.

Acceptable construction classes may include:

- long-lived institutional credential under strong custody;
- short-lived/keyless credential bound to a separately evidenced institutional authorization event;
- threshold signature or multi-signature authorization;
- independent co-authorization.

No construction is sufficient if its credential proves identity but not competence/purpose.

## 5.2 Preservation custody role

The Public Verification Custody Owner role preserves and renews evidence. It does not become the original issuer and cannot silently make a substantive successor claim.

A preservation attestation states only that the role:

- validated a named prior proof closure under a named policy and time;
- committed to the complete prior evidence;
- added new trusted time/algorithm evidence;
- preserved originals and the renewal lineage.

UI and machine reports must label preservation signers separately from issuing authority.

## 5.3 Witness role

A witness attests the exact proposition named by its policy, such as:

- observed checkpoint `h_n` no later than a time;
- confirmed consistency between checkpoints;
- cross-published a checkpoint;
- retained a legal-deposit/archive copy.

A witness does not approve the policy record merely by witnessing a checkpoint.

## 6. Algorithm policy

## 6.1 Policy dimensions

The profile does not freeze Ed25519, P-256, ML-DSA, SLH-DSA, SHA-256, or any other suite for 30 years. The authenticated algorithm policy distinguishes:

- permitted for new issuance;
- permitted for historical verification;
- permitted only as part of a timely preservation chain;
- deprecated pending migration;
- prohibited/unsupported;
- emergency-compromised.

Each primitive has a purpose-specific policy: record commitment, signature, credential, timestamp, transparency tree, witness, and preservation renewal may have different horizons.

## 6.2 Suite declaration

For every cryptographic operation, bind:

- algorithm identifier and parameters;
- key/credential identifier;
- policy version;
- operation purpose/domain;
- effective policy interval;
- validation implementation/profile/test-vector identity where required.

Unknown or ambiguous algorithms fail closed. Verifiers must not infer Ed25519 from key length or a default constant.

## 6.3 Migration rule

Migration never replaces the original signature. It appends a preservation event that:

- validates the complete prior closure while prior algorithms are still acceptable;
- binds old and new commitments over the same preserved object;
- obtains new trusted time and transparency/witness evidence;
- preserves original bytes, signature, policies, and status evidence;
- labels the new signer as preservation custodian, not original issuer.

If the old primitive was already broken before renewal, later re-signing cannot restore historical authenticity absent independent earlier evidence.

## 7. Key generation, custody, rotation, and recovery semantics

The profile requires evidence of outcomes, not a selected HSM/vendor/ceremony.

### 7.1 Generation and activation

Before activation, evidence must establish:

- generation/share ceremony under the configured policy;
- public-key/credential commitment;
- custody and authorization controls;
- signer role/mandate binding;
- activation interval;
- transparency/witness publication of the credential/policy checkpoint;
- recovery/compromise exercise passage for the named profile revision.

### 7.2 Rotation

Normal rotation:

- activates a successor key/credential under a new authenticated event;
- permits a controlled overlap only under declared policy;
- closes the predecessor to new signing at an authenticated cutoff;
- preserves predecessor verification material;
- does not imply compromise;
- does not change record currentness by itself.

### 7.3 Compromise

A compromise event records:

- detection/notice time;
- earliest supported compromise time or interval;
- affected keys, roles, claim classes, jurisdictions, and records;
- freeze/revocation effective time;
- evidence/adjudication basis;
- replacement activation;
- append-only public status and witnessed checkpoint;
- uncertainty for records whose issuance time overlaps the compromise interval.

### 7.4 Recovery

Recovery must not create unlogged replacement signing authority or rewrite key history. OPS-R14 supplies storage/restore/resilience mechanics. INT-R7 requires the recovered system to reproduce:

- original keys' public/status evidence;
- authorization intervals;
- record/proof closures;
- transparency/witness checkpoints;
- preservation lineage;
- exact bounded outcomes in the recovery drill.

## 8. Revocation and temporal validity profile

| Situation | Required evidence | Historical result | Current/new-signing result |
| --- | --- | --- | --- |
| normal retirement after trusted issuance | trusted `t_s < t_ret`; no applicable compromise | may be authentic | key unauthorized for new signing after `t_ret`; record currentness separate |
| prospective revocation after trusted issuance | trusted `t_s < t_r`; authenticated revocation policy/event | may be authentic | key unauthorized after `t_r`; record may remain current only if GY-N12 says so |
| signature at/after revocation | trusted `t_s >= t_r` | issuance unauthorized | never current |
| known compromise after trusted issuance | trusted `t_s < t_c` and policy permits pre-cutoff reliance | may be authentic, with compromise disclosure | currentness separately evaluated |
| signature at/after known compromise | trusted `t_s >= t_c` | historical authenticity fails | never current |
| issuance overlaps uncertain compromise interval | evidence cannot order events | temporal validity indeterminate | never render current |
| current status unavailable but historical status preserved | retained issuance-time evidence valid | historical result possible | current authority not established beyond snapshot |
| neither historical nor current status evidence available | signature math only | incomplete | never current |

The current repository's timeless local revoked-key directory cannot express these rows (`policy-engine/src/polisyos/core/artifacts/signing.py:469-517, 583-610 @ 02c5b8d`).

## 9. Transparency and anti-equivocation profile

## 9.1 Log evidence

For each issuance/status/preservation event, retain:

- leaf/event commitment;
- tree/log identity and policy;
- tree size/checkpoint;
- inclusion proof;
- required consistency proof chain;
- log signing credential and status evidence;
- timestamp/order evidence as defined by policy.

## 9.2 Common-view evidence

A single log is insufficient against split view. `CommonViewEstablished` requires:

- one or more independently obtained checkpoints;
- witness signatures/cross-publication/gossip evidence;
- a declared quorum and independence policy;
- checkpoint consistency comparison;
- typed failure if witnesses disagree, are unavailable, or are not independent under policy.

The profile does not select a witness count or operator. The non-collusion assumption must appear in the verification report.

## 9.3 Logged event classes

At minimum:

- signer credential/policy activation;
- record issuance;
- honest refusal/negative terminal;
- challenge;
- invalidation;
- withdrawal;
- supersession/new epoch/reissue;
- key retirement/revocation/compromise interval;
- algorithm-policy change;
- preservation renewal;
- custody/succession statement;
- detected equivocation or witness disagreement.

## 10. Offline verification closure

An offline verifier with no live connection to PolicyOS must possess:

1. original signed semantic statement and relevant public projection;
2. canonicalization/profile specifications;
3. issuing signature(s);
4. signer credential chain or equivalent authority credential evidence;
5. independently authenticated trust roots and institutional policy snapshot;
6. signing-time status/revocation/compromise evidence;
7. trusted timestamp and its validation material;
8. transparency inclusion/consistency proofs;
9. witnessed checkpoints and witness policy;
10. GY-N12 epoch and authenticated status snapshot with `as_of`;
11. INT-R8 projection relation proof;
12. challenge/withdrawal/supersession/successor events needed for the requested outcome;
13. algorithm policy applicable to issuance and historical verification;
14. complete preservation/migration chain;
15. verifier/profile implementation or independently specified evaluator and test vectors; and
16. reason-code semantics and human-report rules.

The package carrying these items cannot authenticate its own trust roots. At least one trust/checkpoint/policy anchor must be obtained or validated independently of the untrusted record package.

Offline currentness is bounded:

- report `current as of t_q`, never unqualified `current`;
- expose snapshot age and freshness policy;
- if freshness requirement is exceeded, report `status_snapshot_stale` even when historical predicates pass;
- do not silently connect to the network after the user selected offline verification.

## 11. Preservation profile reference

Before first issuance, the profile requires the retention and recovery commitments in `lifecycle-migration-preservation.md`, including:

- original bytes and renderings;
- canonicalization and profile versions;
- credential/trust/status/timestamp closure;
- transparency/witness evidence;
- GY-N12 status history;
- INT-R8 proof material;
- algorithm/format migration events;
- OAIS/PREMIS-class preservation metadata;
- verifier source/dependencies/test vectors;
- named custody-owner role and succession package;
- disconnected recovery drill.

This is a pre-publication gate, not a future archival enhancement.

## 12. Privacy profile

### 12.1 Addressing

A public record locator should be unlinkable to low-entropy private attributes without opening material. Suitable construction classes include:

- random high-entropy opaque identifiers;
- nonce/randomness-hardened commitments;
- batched Merkle roots with selective inclusion proofs;
- separately disclosed opening material for authorized/public verification.

A bare hash of a predictable name, benefit ID, case number, date, or small policy category is vulnerable to dictionary enumeration.

### 12.2 Status privacy

Prefer retained/stapled status evidence and public batched status/checkpoint feeds over per-record live queries. When a live query is required, the profile must disclose the privacy dependency and avoid claiming private offline verification.

### 12.3 Transparency privacy

Transparency leaves should commit to a privacy-safe record identifier and semantic commitment, not raw restricted content. Batching may hide individual issuance cadence, but the chosen construction must preserve auditable inclusion and migration.

### 12.4 INT-R8 boundary

INT-R7 specifies only addressing and proof-metadata privacy. INT-R8 decides the content retained or redacted in the public projection.

## 13. Verification outcomes

The machine result contains the full predicate vector. The human projection maps it to one of the following bounded outcome classes.

| Outcome code | Required condition | Forbidden implication |
| --- | --- | --- |
| `VERIFIED_CURRENT_AS_OF` | historical authenticity + common view + INT-R8 proof + GY-N12 current at authenticated `as_of` + freshness policy | not “true forever,” legally sufficient, or substantively correct |
| `AUTHENTIC_HISTORICAL_WITHDRAWN` | historical authenticity + authenticated withdrawal + current=false | not current |
| `AUTHENTIC_HISTORICAL_SUPERSEDED` | historical authenticity + valid successor link + current=false | not invalid or erased |
| `AUTHENTIC_HISTORICAL_STALE` | historical authenticity + stale/revalidation-required status | not current pending revalidation |
| `AUTHENTIC_HISTORICAL_AS_OF` | historical authenticity with offline/authenticated historical cutoff but current status unavailable/expired | not current now |
| `TEMPORAL_VALIDITY_INDETERMINATE` | signature math passes but issuance versus compromise/revocation cannot be ordered | not warning-only success |
| `COMMON_VIEW_NOT_ESTABLISHED` | record may be signed/log-included but independent checkpoint policy fails | not public consensus/common history |
| `AUTHORITY_NOT_ESTABLISHED` | signature may pass but credential/mandate/purpose/succession fails | not government-authorized |
| `PROJECTION_RELATION_NOT_ESTABLISHED` | INT-R8 proof absent/fails | cryptography does not cure content omission |
| `BASIS_INCOMPLETE` | `delta` not atomically bound to declared set/assumptions/rider | never show numeric claim as verified |
| `PROCEDURAL_HISTORY_NOT_ESTABLISHED` | chronology/seal/firstness requirements absent or contradicted | signature alone does not prove procedure |
| `PRESERVATION_CHAIN_BROKEN` | historical evidence cannot survive algorithm/format/status dependency failure | original visible document is insufficient |
| `TAMPERED_OR_SIGNATURE_INVALID` | content commitment or required signature fails | no historical/current authenticity |
| `PROFILE_OR_ALGORITHM_UNSUPPORTED` | profile/canonicalization/algorithm policy cannot be evaluated | no permissive fallback |
| `OFFLINE_CLOSURE_INCOMPLETE` | mandatory trust/status/log/witness/epoch/evidence missing | no hidden live fallback |

No unqualified `Verified` outcome exists.

## 14. Invariants

### PV-INV-01 — exact semantic binding

Changing record bytes, projection relation, claim class, basis, audience, jurisdiction, authority boundary, epoch, chronology, or profile version invalidates at least one signed commitment predicate.

### PV-INV-02 — trust is external to the untrusted package

Replacing a package's payload, signature, and bundled key cannot produce `VERIFIED_CURRENT_AS_OF` without an independently authenticated trust/authority/checkpoint path.

### PV-INV-03 — historical/current separation

Key retirement, record withdrawal, staleness, supersession, and historical signature validity are represented independently. A withdrawn record can be historically authentic; a valid signature can be non-current.

### PV-INV-04 — trusted time, not self-declared time

No signer-controlled timestamp can establish pre-revocation or prospective chronology.

### PV-INV-05 — common view is independently corroborated

Log inclusion and consistency without witness policy satisfaction cannot yield a common-view/current result.

### PV-INV-06 — append-only correction

Challenge, invalidation, new epoch, withdrawal, supersession, and preservation events append. Original bytes/signatures are never rewritten.

### PV-INV-07 — algorithm migration preserves lineage

Renewal covers complete prior evidence while it is still trustworthy and labels preservation authority separately.

### PV-INV-08 — offline boundedness

Offline verification never claims currentness beyond authenticated `as_of` and never silently contacts live services.

### PV-INV-09 — INT-R8 seam

INT-R7 binds and verifies the INT-R8 result; it never reclassifies content loss or material omission.

### PV-INV-10 — one lattice

Verification predicates feed existing authority/status semantics. They do not create a competing record-status lattice.

### PV-INV-11 — negative terminals are first-class

Honest refusal, dissent, challenge, and published negatives cannot be omitted from the declared public-history policy while a positive procedural claim passes.

### PV-INV-12 — bounded passage

A falsifier suite passage supports only the named implementation, revision, environment, evaluator, and tested predicates under `S0-K16`.

## 15. Pre-issuance gate

No first public signature may be emitted until authorized governance can provide evidence that:

- all mandatory statement semantics are representable and canonically bound;
- INT-R8 projection interface passes;
- GY-N12 epoch/currentness interface is available;
- issuing authority and custody roles are institutionally assigned;
- key generation/custody/rotation/compromise policy is active;
- trusted timestamp and signing-time status closure are available;
- transparency and independent witness policy are active;
- algorithm policy and migration triggers are active;
- 10–30 year preservation closure and succession commitments exist;
- disconnected recovery drill passes;
- citizen and machine verifier outcomes are behaviorally tested;
- the client-side FNV predecessor cannot emit a positive result;
- every frozen falsifier returns its exact expected outcome.

At the pinned commit, this gate is closed: the public projection producer exists, but public proof production, production bridge, temporal/public verification, transparency, preservation renewal, and semantic tests are missing at the classified links.

## 16. Dependency contract

### 16.1 INT-R8

INT-R7 requires stable retained-claim commitment, projection/redaction relation, policy/version, typed outcome, and successor relation. It does not own public content or compression/disclosure semantics.

### 16.2 GY-N12

INT-R7 requires epoch identity, status/current-head projection, authenticated `as_of`, stale/revalidation/withdrawal/supersession relations, and historical replay semantics. It does not own epoch computation or status adjudication.

### 16.3 OPS-R14

INT-R7 requires durable proof closure, recovery under unavailable/compromised primary systems, expiring-dependency monitoring, legal-hold/retention outcomes, custody transfer, and replay/drill evidence. It does not select storage or disaster-recovery mechanics.

### 16.4 Institutional governance

Governance must decide competent issuing/custody roles, recognized credential/timestamp/preservation policies, witness independence, retention/legal-deposit/FOI rules, funding, succession, compromise disclosure, and legal interpretation.

## 17. Profile conclusion

The profile is a composition of distinct evidence layers, not a choice of one signature algorithm. Exact signature binding proves who controlled a credential for the statement; trusted time and status establish when; witnessed transparency establishes the bounded public history; GY-N12 establishes currentness; INT-R8 establishes the public projection relation; and preservation renewal carries the evidence across cryptographic and organizational change. Only their typed conjunction can support `VERIFIED_CURRENT_AS_OF`, while the same profile keeps an old record authentically verifiable after it has become withdrawn, stale, superseded, or archive-only.
