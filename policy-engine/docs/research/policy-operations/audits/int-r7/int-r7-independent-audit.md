---
title: INT-R7 — Hostile Independent Audit
verified_commit: f5671253b51554dde2dd22a6aef2ef827c5bd9dd
pinned_repository_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
authoritative_for:
  - independent audit verdict and complete finding register for INT-R7
  - reconciliation of engineering, cryptographic, public-administration, source, seam, prohibition, and capability-honesty findings
  - revision standing of the audited research at the verified commit
may_not_use_for:
  - adoption, amendment, or ratification of INT-R7
  - production implementation authorization
  - final schema, wire, package, serialization, database, or API contract
  - canonical owner, vendor, operator, trust service, log, witness, archive, or key-custodian appointment
  - legal sufficiency or jurisdictional compliance conclusion
  - permission to publish a governed record
research_only: true
---

# INT-R7 hostile independent audit

## 1. Executive verdict

**Verdict: `GO_WITH_REVISIONS`.**

The headline result is correct: a valid signature establishes a bounded relation among bytes,
a key and a policy; it is not by itself a governed public-administration `Verified` state.
INT-R7's strongest contributions should survive:

- historical issuance and current authority are separate;
- withdrawal/supersession append without erasing reproducible history;
- the `INT-K06` procedural first claim is a history, so chronology and anti-backdating are
  security semantics;
- a `delta` without its `INT-K02` obligation set and assumptions is incomplete;
- Merkle inclusion in one view is not common view;
- a successor or preservation custodian does not become the original issuer; and
- INT-R7 owns proof while GY-N12 owns currentness and INT-R8 owns content/projection semantics.

The reported source defect is **confirmed**. In `core/artifacts/signing.py`, `signed_at` and
`signer_identity` are outside the signed `SignatureStatement`; revocation is a timeless key-ID
set with no effective time, reason, normal-retirement distinction or compromise interval. The
verifier can validate Ed25519 math but cannot establish whether issuance preceded compromise or
was forged later and backdated through mutable metadata.

Stronger standing is blocked by one maturity-accounting defect and fifteen material gaps:

1. `HistoricalAuthenticity` conflates issuer issuance with projection, public history and
   later evidence preservation;
2. INT-R8 is not delivered and GY-N12 is planned, so positive end-to-end results are
   hypothetical;
3. the frozen suite is not exact or complete enough to execute as written;
4. preservation lacks explicit authentic-snapshot anti-rollback and compromised-primary
   recovery outcomes;
5. NARA/Federal PKI source limits need correction; and
6. new capabilities are assigned downstream missing-state labels without the vocabulary's
   prerequisite consumers, endpoints or wired chains.

The last item is the single `blocking` finding. It does not justify `NO_GO`: it is a correctable
classification defect, not a refutation of the architecture.

## 2. Scope and delivery method

Exact comparison from baseline to audited head establishes **10 commits ahead, 0 behind, 10
added Markdown files, 5,250 additions, 0 deletions, and no modified/renamed files**. The merge
base is the pinned baseline. All 10/10 artifacts and all 30/30 external source identifiers were
checked.

Ordinary clone/codeload access failed because outbound GitHub DNS/egress was denied. Exact-ref
reads and ordinary branch/file commits used the connected GitHub interface. No workflow,
upload fragment, base64 payload, or self-executing repository mechanism was added. Exact global
lexical counts that could not be rerun are marked `not_established`.

## 3. Competence verdicts

### Engineering

The constructions are real and named—domain-separated signatures, trusted time/status,
Merkle transparency, witnesses, PAdES/XAdES/CAdES/ERS-class preservation, offline closure and
renewal—and failures are usually specified. The end-to-end profile is not implemented: INT-R8,
GY-N12, authority/succession evidence, time/status, log/witness, preservation renewal,
independent trust distribution and canonical evaluator are absent.

### Mathematical/cryptographic

The threat model states assumptions and avoids “signature proves a worldly fact.” The material
error is aggregate composition: issuer issuance, projection faithfulness, public history,
durable verifiability and current authority must remain separately reportable. “Independent
predicates” should mean failure-visible dimensions, not logical independence.

### Public administration

The work unusually covers succession, decades-long custody, contest, public access,
cross-agency/cross-border limits, archival/FOI dependencies, restricted evidence and a citizen
or journalist without an institutional trust anchor. NARA US-01 is officially superseded;
Federal PKI US-02 is nonbinding and Federal Register-specific. The broader non-substitution
claim remains sound.

### Breadth and selection

All nine mandated models are evaluated by eliminating property rather than repository
convenience. The composite choice is justified.

## 4. Highest-value determinations

### INT-R8 seam

Repository searches found plans/backlog/context but no delivered INT-R8 result. The brief's
more specific failed-upload mechanics were not readable from an exact ref and remain
`not_established`; the missing content contract is established. INT-R7's interface survives,
but every projection-dependent positive is unsatisfied. Its formal aggregate must stop an
INT-R8 failure from erasing issuer-side issuance.

### Frozen suite

F-05, F-17 and F-18 are strong. F-04 uses a tamper/signature-invalid terminal even though
signature math is true. At least 7/18 cases use conditional/disjunctive values despite exact
equality. Missing attacks include signer+TSA collusion, authentic-snapshot rollback,
conflicting succession, parser/canonicalization differential and withheld negative terminals.

### First-signature gate

The 10–30 year custody gate is correct for the first **public authority-bearing** signature,
not candidate/test activity. A real pre-live disconnected drill can use a representative
non-authoritative/ceremonial corpus. Recovery must detect stale authentic snapshots and survive
an unavailable/compromised primary custody domain.

## 5. Pass IX — prohibitions and standing

A complete 10/10 frontmatter census found `research_only: true` and `may_not_use_for` in every
artifact. No owner/vendor/service/key custodian is appointed; no legal sufficiency, present
publication capability, final wire/schema/API, or second GY/INT-R8 ledger is declared. The only
residual risk is that code-like state/result names and `verify_public_record(...)` may be copied
as a closed implementation contract.

### INT-R7-IX-001 — commendation — all ten artifacts carry effective prohibitions

### INT-R7-IX-002 — minor — semantic lists can be misread as a wire/status contract

### INT-R7-IX-003 — commendation — `GO_WITH_REVISIONS` is the correct standing

## 6. Pass X — capability honesty

The vocabulary owner requires: a consumer for `producer_missing`; both endpoints for
`bridge_missing`; and a wired chain for `verification_missing`.

| Audited label | Verdict |
| --- | --- |
| public projection producer plus production `bridge_missing` | high-level classification survives; producer component is implemented but not production-orchestrated |
| public proof producer `producer_missing` | mislabelled: no admitted consumer/typed contract evidenced |
| public temporal/authority verifier `verification_missing` | mislabelled: no wired authority/time/log/epoch/projection/preservation chain |
| `semantic_test_missing` | a real test gap, but not evidence that the capability otherwise exists |
| N-01 `producer_missing` | mislabelled: no named consumer |
| N-02 `producer_missing`/`verification_missing` | prerequisites absent |
| N-03 `producer_missing`/`bridge_missing`/`verification_missing` | producer, consumer and wired chain absent |
| N-04 `producer_missing` | no named consumer |
| N-05 `producer_missing` | no named consumer; OPS-R14 dependency is not a consumer |
| N-06 `producer_missing`/`verification_missing` | standalone substrate exists, admitted independent bundle/chain does not |
| N-07 `verification_missing`/`semantic_test_missing` | legacy surface exists, proposed evidence chain does not; capability is absent/unallocated |

### INT-R7-X-001 — blocking — capability labels upgrade sketches into downstream maturity states

Recompute N-01 through N-07 and the public proof/verifier handoff from pinned evidence. Retain
the narrower production `bridge_missing` conclusion for the real export producer/surface.

### INT-R7-X-002 — commendation — the existing public-export producer is not erased

## 7. Complete finding register

| Finding ID | Severity | Pass | Finding |
| --- | --- | --- | --- |
| INT-R7-I-001 | commendation | I | Branch geometry and scope are exact. |
| INT-R7-I-002 | commendation | I | Signing-time/revocation defect is real and precisely bounded. |
| INT-R7-I-003 | commendation | I | O-09 corrects the briefing and preserves production `bridge_missing`. |
| INT-R7-I-004 | commendation | I | O-02/O-08 use `not_established` honestly. |
| INT-R7-I-005 | material | I | Ledger missed the false “four days before” claim; dates are 2026-08-04. |
| INT-R7-I-006 | minor | I | O-05's exact 14/14 denominator lacks an independently retained rerun. |
| INT-R7-II-001 | commendation | II | The 30-source corpus is primary-source heavy and transfer-limited. |
| INT-R7-II-002 | minor | II | PAdES ETSI-05 edition date is 2024-01, not 2024-06. |
| INT-R7-II-003 | material | II | NARA US-01 is officially superseded and historical-only. |
| INT-R7-II-004 | material | II | Federal PKI US-02 is nonbinding and Federal Register-specific. |
| INT-R7-II-005 | minor | II | RFC 9162 does not standardize INT-R7's witness quorum. |
| INT-R7-II-006 | minor | II | Exact Sigstore fields need the Bundle Format anchor. |
| INT-R7-III-001 | commendation | III | The vector rejects “signature equals fact.” |
| INT-R7-III-002 | material | III | `HistoricalAuthenticity` conflates issuance, projection, history and preservation. |
| INT-R7-III-003 | minor | III | “Independent predicates” is logically overstated. |
| INT-R7-III-004 | material | III | Authentic old snapshot selection/rollback is absent. |
| INT-R7-IV-001 | commendation | IV | Ten elements are real constructions with named failure semantics. |
| INT-R7-IV-002 | commendation | IV | GY-N12 and INT-R8 ownership is declared, not duplicated. |
| INT-R7-IV-003 | material | IV | INT-R8 absence makes positive public-profile results unsatisfied. |
| INT-R7-IV-004 | material | IV | GY-N12 currentness is planned and undelivered. |
| INT-R7-V-001 | material | V | Exact-equality conflicts with conditional/disjunctive expectations. |
| INT-R7-V-002 | material | V | F-04 uses a signature-invalid terminal while signature math is true. |
| INT-R7-V-003 | material | V | F-08 lets split-view failure erase issuer issuance. |
| INT-R7-V-004 | commendation | V | F-05/F-17/F-18 protect history, withdrawal and succession. |
| INT-R7-V-005 | material | V | Five distinct attacks are missing. |
| INT-R7-VI-001 | commendation | VI | First-signature gate respects authority/candidate bands. |
| INT-R7-VI-002 | material | VI | Pre-first-signature disconnected drill is ambiguous/circular. |
| INT-R7-VI-003 | material | VI | Anti-rollback and cross-custody restore outcomes are absent. |
| INT-R7-VI-004 | commendation | VI | Preservation does not launder issuer identity or late trust loss. |
| INT-R7-VII-001 | commendation | VII | `INT-K06` is primary and chronology is security-critical. |
| INT-R7-VII-002 | commendation | VII | `INT-K02` basis completeness is statement integrity. |
| INT-R7-VII-003 | commendation | VII | Withdrawn-but-verifiable conforms to `INT-K01`/`S0-K08`. |
| INT-R7-VII-004 | commendation | VII | Suite claims remain bounded by `S0-K16`. |
| INT-R7-VII-005 | commendation | VII | No second authority ledger or projection owner is created. |
| INT-R7-VIII-001 | commendation | VIII | Proof/content seam is explicit and disciplined. |
| INT-R7-VIII-002 | material | VIII | No delivered INT-R8 result; dependent positives are unsatisfied. |
| INT-R7-VIII-003 | material | VIII | INT-R8 failure can incorrectly erase issuer authenticity. |
| INT-R7-IX-001 | commendation | IX | All ten artifacts carry effective prohibitions. |
| INT-R7-IX-002 | minor | IX | Code-like lists can be mistaken for a wire/status contract. |
| INT-R7-IX-003 | commendation | IX | `GO_WITH_REVISIONS` is correct. |
| INT-R7-X-001 | blocking | X | New capability labels violate prerequisite vocabulary. |
| INT-R7-X-002 | commendation | X | Existing export producer/production bridge gap is not erased. |

## 8. Count reconciliation

The register contains **42 rows**:

| Severity | Rows |
| --- | ---: |
| blocking | 1 |
| material | 15 |
| minor | 6 |
| commendation | 20 |
| **total** | **42** |

The prose uses the same counts: **1 blocking, 15 material, 6 minor, 20 commendations**.

## 9. Adoption boundary

This verdict ratifies nothing and authorizes no public signature. Until revision:

- Ed25519/FNV paths are not a public-verification lifecycle;
- no INT-R8 public-positive or GY-N12 current-positive result exists;
- the 18/18 suite has not run and is not executable as written;
- no jurisdictional legal sufficiency is established; and
- no present publication capability may be inferred.
