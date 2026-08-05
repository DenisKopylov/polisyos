---
title: INT-R7 — Formal Argument Audit
verified_commit: f5671253b51554dde2dd22a6aef2ef827c5bd9dd
pinned_repository_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
authoritative_for:
  - independent Pass III audit of the verification-predicate vector
  - independent Pass IV audit of the ten-element composite profile
  - independent Pass V audit of all eighteen frozen falsifiers and constructed attacks
  - independent Pass VI audit of preservation and the first-signature gate
  - findings INT-R7-III-001 through INT-R7-VI-004
may_not_use_for:
  - production implementation authorization
  - final schema, wire, package, serialization, database, or API contract
  - canonical owner, operator, vendor, trust service, witness, archive, or key-custodian appointment
  - legal sufficiency or jurisdictional compliance conclusion
  - claim that the proposed verifier, dependencies, or falsifier suite exist or have passed
research_only: true
---

# INT-R7 formal argument audit

## 1. Required separation

The audited work correctly rejects one green `Verified` Boolean, but its aggregate formulas
partly recombine distinct propositions. The audit keeps five facts separate:

1. **issuer issuance authenticity** — exact statement, competent issuer, authorized interval,
   trusted chronology and signing-time status;
2. **projection faithfulness** — the INT-R8-defined relation between retained claim and public
   object;
3. **public-history establishment** — log inclusion/extension and bounded common-view evidence;
4. **durable verifiability at `t_v`** — original and renewed evidence remains evaluable; and
5. **current authority as of `t_q`** — authenticated GY-N12 status at a bounded cutoff.

A public-current result may require a conjunction. Failure of a later projection, log,
availability, or archive layer must not rewrite whether the issuer issued the statement.

## 2. Threat model

The twelve adversaries are materially complete and usually specify control, assumption and
residual limit:

| Adversary | Audit result |
| --- | --- |
| A-01 statement substitution | sound under hash resistance and unambiguous canonicalization; parser differentials are not frozen |
| A-02 compromised signer | sound; EUF-CMA is not treated as post-compromise chronology |
| A-03 authority impersonation/overreach | sound; key identity is not administrative mandate and disputed law returns not established |
| A-04 replay/context substitution | sound; F-10 must split jurisdiction replay from statement mutation |
| A-05 projection attacker | clean INT-R8 dependency; no positive result is currently satisfiable |
| A-06 time/status attacker | sound; signer+TSA collusion is acknowledged but untested |
| A-07 split-view log | strong distinction between one-view proof and common view |
| A-08 archive/storage attacker | sound; stale authentic snapshot and correlated custody failure need tests |
| A-09 successor organization | strong predecessor-attribution rule; positive and conflicting-succession cases are missing |
| A-10 administrative suppression | honest limit; evidence obtainability needs its own result |
| A-11 verifier environment | sound; trust/status anti-rollback remains open |
| A-12 privacy observer | sound and properly leaves disclosed content to INT-R8 |

The research does not commit the classic error of treating a signature as proof that a policy
fact is true, lawful, wise, or within institutional competence.

## 3. Pass III — eleven dimensions

“Independent predicates” is defensible only as “failures remain separately visible.” Several
dimensions are logically dependent or derived.

| # | Dimension | Inputs/checker | Independence and pinned-state verdict |
| ---: | --- | --- | --- |
| 1 | integrity | exact bytes, canonicalization/profile, commitments, algorithm and signature | distinct from authority/currentness; only a narrow artifact-signing subset exists |
| 2 | authority | authenticated credential, mandate/delegation, purpose, jurisdiction, role and interval policy | not reducible to key identity; institutional producer absent |
| 3 | trusted time | committed datum, timestamp/equivalent, TSA trust/status/policy | distinct from signer metadata and log order; producer absent |
| 4 | signing-time status | chain, historical CRL/OCSP/equivalent, effective revocation/compromise interval and trusted time | depends on time but does not collapse into it; current repository cannot express it |
| 5 | claim basis/history | claim-class profile, `delta` basis or procedural chronology/negative-terminal commitments | semantic completeness distinct from signature math; evaluator absent |
| 6 | INT-R8 relation | retained commitment, projection, policy/version and proof/result | public-content question; absent and wrongly nested inside issuer completeness |
| 7 | log inclusion | leaf, log identity, checkpoint and proof | one-view membership, not common view; producer absent |
| 8 | common view | consistency, independently obtained checkpoints, witness identity/status/policy | derived from log/witness evidence; satisfiable only under declared non-collusion scope |
| 9 | epoch | signed GY-N12 epoch and historic closure | distinct from currentness; planned, not delivered |
| 10 | currentness | authenticated GY-N12 snapshot, cutoff and lifecycle links | depends on owner status evidence; planned, not delivered |
| 11 | preservation | originals, validation material, policies, renewals, trusted time, checkpoints and verifier closure | durability at `t_v`, not issuance at `t_s`; no operated lifecycle |

### 3.1 Missing anti-rollback result

A complete authentic pre-withdrawal snapshot can be replayed after a newer authentic
withdrawal exists. The profile's `as_of` wording is necessary but does not establish latest
selection. Revision must either add a monotonic/latest-snapshot result under a declared
distribution policy or explicitly state that only the supplied snapshot is proved.

### 3.2 Missing evidence-obtainability result

A proof available only to its issuer is not operationally public. Add a separate
public-administration result for public availability, records-process availability, competent
restriction, or not established. Do not fold this into signature authenticity.

### 3.3 Aggregate defect

`StatementComplete` includes `ProjectionRelationValid`, and `HistoricalAuthenticity` requires
public history, original retention, preservation and algorithm policy
(`threat-model-and-verification-predicates.md:541-604`). This lets INT-R8 absence, witness
loss, or archive failure erase issuer issuance. The semantic correction is to report:

```text
IssuerIssuanceAuthentic
ProjectionFaithful
PublicHistoryEstablished
DurablyVerifiableAt(t_v)
CurrentAuthorityAsOf(t_q)
```

The withdrawn/superseded/current formulas themselves are sound once those components remain
separate.

## 4. Pass IV — ten-element profile

| # | Element | Guarantee, cost, and unavailable result |
| ---: | --- | --- |
| 1 | domain-separated full-statement signature | prevents cross-domain/content substitution under EUF-CMA/hash/canonicalization assumptions; needs signing/canonicalization governance; otherwise integrity not established |
| 2 | authority/jurisdiction/audience/boundary evidence | constrains who may issue what/where/when under authentic institutional policy; costs mandate/delegation/succession governance; otherwise authority not established |
| 3 | trusted time plus signing-time status | orders issuance against retirement/revocation/compromise; costs TSA/status retention and adjudication; otherwise temporal validity incomplete/indeterminate |
| 4 | append-only Merkle history | proves inclusion/extension relative to checkpoints; costs operated log/retention/monitoring; otherwise log history not established |
| 5 | independent checkpoint witnesses | bounds split-view risk under declared independence/non-collusion; costs witness governance/continuity; otherwise common view not established |
| 6 | GY-N12 epoch/currentness | supplies canonical status without a second lattice; planned but absent; otherwise historical-only result |
| 7 | INT-R8 retained-claim/projection relation | supplies content relation without INT-R7 defining content; absent; otherwise public projection not established |
| 8 | LTA/ERS preservation and timely re-anchoring | preserves evaluation if renewal occurs before trust loss; costs long-term custody/monitoring; late repair is forbidden |
| 9 | independently authenticated offline closure | permits disconnected verification without package-self-key trust; costs trust distribution and preserved verifier; otherwise offline closure incomplete |
| 10 | separate historical/current outcomes | prevents withdrawal erasing history or old signatures masquerading as current; costs vector UX/evaluator/status inputs; otherwise no unqualified positive |

No direct circularity was found: INT-R7 binds GY-N12 and INT-R8 outputs but does not create
them. Both are load-bearing absences, so positive baseline B0/B1 is hypothetical.

## 5. Pass V — frozen suite

The suite is a semantic specification, not a runnable repository suite. The canonical evaluator
and authority/time/log/witness/GY/INT-R8/preservation inputs do not exist end-to-end.

| Case | Audit of expected result |
| --- | --- |
| F-01 | excellent constructive FNV negative |
| F-02 | `false_or_not_applicable...` is not exact; separate value from short-circuit status |
| F-03 | `true_under_attacker_key_only` is prose; separate local math from trusted credential |
| F-04 | contradictory terminal: signature is true, failure is temporal authorization, not tamper/signature invalid |
| F-05 | excellent pre-revocation positive preserving current record authority |
| F-06 | strong uncertain-compromise non-positive |
| F-07 | strong stale-epoch historical/current split |
| F-08 | common view correctly fails, but issuer issuance must remain separately reportable |
| F-09 | `false_for_requested_use` is not exact; separate issuance from relying-use acceptance |
| F-10 | combines jurisdiction replay and authority-boundary mutation; split |
| F-11 | combines stripped basis and newly signed incomplete claim; split |
| F-12 | alternative chronology/firstness mutations need exact subfixtures |
| F-13 | conflates local cryptographic validity and threshold-policy satisfaction |
| F-14 | historical-policy/preservation prose must become exact component values |
| F-15 | excellent rejection of late cryptographic laundering |
| F-16 | strong disconnected/as-of case; add old-authentic-snapshot rollback |
| F-17 | excellent withdrawn-but-verifiable case |
| F-18 | excellent successor-substitution negative; add positive/conflicting succession |

At least **7/18** cases contain explicit conditional/disjunctive predicate values: F-02,
F-03, F-08, F-09, F-10, F-11, F-14. F-12, F-13 and F-18 also need typed decomposition.
The exact-equality harness cannot execute these expectations without inventing semantics.

### 5.1 Constructed attacks not caught

- **A-X1 signer+TSA collusion:** compromised signer and time service backdate a new object;
  trusted issuance time must be unestablished or explicitly assumption-weakened.
- **A-X2 authentic snapshot rollback:** old authentic pre-withdrawal snapshot is selectively
  replayed; latest selection must fail or result remain historical-as-of only.
- **A-X3 conflicting succession:** two authentic incompatible successors; original issuance
  may stand, current succession is disputed/not established.
- **A-X4 parser/canonicalization differential:** duplicate keys, Unicode or numeric ambiguity
  gives machine/human different semantics; canonical statement must fail.
- **A-X5 withheld negative terminal:** required procedural refusal/negative exists elsewhere
  but is omitted; procedural/public-history completeness must fail.

The suite is strong but not complete against these attacks.

## 6. Pass VI — preservation and first signature

The gate is correct when scoped to the first **public authority-bearing** signature, not
candidate experiments or test keys. “Real disconnected drill before first record” is
operationally ambiguous: use a representative non-authoritative/ceremonial corpus through the
real path before live issuance, then require a bounded first-live follow-up. A paper runbook is
not enough.

The gate is under-strict unless restoration detects authentic-but-stale trust/status snapshots
and survives an unavailable or compromised primary custody domain through independent or
cross-custody evidence. OPS-R14 may own topology/RPO/RTO; INT-R7 still owns the proof outcome.

The preservation claim is correct: a preservation event does not replace the original, make the
archivist/successor the original issuer, or repair evidence only after prior trust is lost.

## 7. Findings from Passes III–VI

### INT-R7-III-001 — commendation — the vector rejects “signature equals fact”

**Evidence:** `threat-model-and-verification-predicates.md:410-519, 697-730`.

### INT-R7-III-002 — material — `HistoricalAuthenticity` conflates issuance, projection, public history and preservation

**Evidence:** formal definitions at `:541-604`. Split the component facts.

### INT-R7-III-003 — minor — “independent predicates” is logically overstated

Use “separately reportable dimensions” while retaining failure visibility.

### INT-R7-III-004 — material — authentic-snapshot selection/rollback is absent

Add a result/policy or explicitly limit the claim to the supplied authentic snapshot.

### INT-R7-IV-001 — commendation — all ten elements are real constructions with named failure semantics

### INT-R7-IV-002 — commendation — GY-N12 and INT-R8 ownership is declared, not duplicated

### INT-R7-IV-003 — material — INT-R8 absence makes the positive public profile unsatisfied

### INT-R7-IV-004 — material — GY-N12 currentness is planned, not delivered

### INT-R7-V-001 — material — exact-equality is contradicted by the suite's expected values

### INT-R7-V-002 — material — F-04 uses the wrong top-level failure class

### INT-R7-V-003 — material — F-08 exposes the overbroad historical-authenticity aggregate

### INT-R7-V-004 — commendation — F-05, F-17 and F-18 protect hard public-record semantics

### INT-R7-V-005 — material — five distinct attacks are missing

### INT-R7-VI-001 — commendation — the gate respects authority and candidate bands

### INT-R7-VI-002 — material — the pre-first-signature drill is operationally ambiguous

### INT-R7-VI-003 — material — anti-rollback and cross-custody restore outcomes are missing

### INT-R7-VI-004 — commendation — preservation does not launder issuer identity or late trust loss
