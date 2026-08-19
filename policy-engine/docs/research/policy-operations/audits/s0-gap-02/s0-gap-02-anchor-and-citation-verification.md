---
title: S0-GAP-02 — Anchor and citation verification
status: draft_audit
kind: research-audit
verified_commit: a7c34cc40b649a10b6878228a8a57acc498f279a
pinned_repository_commit: 1a7a2d05ebba22fae80e9934329e4b880806588e
research_only: true
authoritative_for:
  - Pass-II external-source verification
  - internal ratified-anchor verification by finding ID
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization or API contract
  - canonical owner, evaluator, custodian, reviewer panel or vendor appointment
  - authority grant
  - capability claim
  - benchmark passage
  - permission to score OPS-R15
  - claim that OPS-R15 is unblocked or scorable
  - legal-sufficiency conclusion
  - automatic amendment of any plan, backlog or system-design decision
---

# S0-GAP-02 anchor and citation verification

## 1. Internal anchors

| Finding ID | Pinned owner | Audit use | Verdict |
|---|---|---|---|
| `S0-K13` | `stage0-custody-kernel-ratification.md` | Benchmark observable semantics, not internal product architecture. | correctly applied |
| `S0-K14` | same | Independence binds verification claims; same-code rebuild proves consistency only. | correctly applied and not broadened to production rebuilds |
| `S0-K15` | same | Anti-memorization and preserved dissent. | correctly applied |
| `S0-K16` | same | Passage is bounded and carries no authority. | correctly applied; challenge rider revision required |
| `INT-K05` | `int-wave-claim-semantics-ratification.md` | One product confidence owner; no second ledger. | benchmark log correctly scoped outside product authority |
| `PV-K06` | `int-r7-r8-public-verification-and-disclosure-ratification.md` | Unproved approximation cannot inherit safe verdict. | correctly operationalized in mandatory predicate handling |
| `P27` / `P28` | `policy-design-case-failure-patterns.md` | Extend canonical owner and strangle predecessor. | principled S0-K14 exception by function |
| `P35` / `P36` | same | Complete denominators and finding-ID authority. | researcher’s refusal correct; this audit’s exact token census remains not established |

No internal claim is taken from adjacent motivational prose where a finding ID controls.

## 2. External primary-source verification

| Stable identifier | Existence and cited proposition | Transfer limit audit | Verdict |
|---|---|---|---|
| ISO/IEC 17043:2023, ISO 80864 | Proficiency-testing provider competence, impartiality, consistent operation and scheme discipline. | Does not make software outputs measurands or appoint an accredited provider. | confirmed |
| ISO/IEC 17025:2017, ISO 66912 | Laboratory competence, impartiality and consistent operation. | No laboratory/accreditation standing transferred. | confirmed |
| ISO/IEC 17011:2017, ISO 67198 | Competence/impartiality for bodies assessing conformity-assessment bodies. | No benchmark-governance body is appointed or accredited. | confirmed |
| ILAC P9:01/2024 | Participation/proficiency-testing policy in accredited contexts. | Operational analogy only; no ILAC scope claimed. | confirmed |
| ILAC P10:07/2020 | Metrological traceability policy. | Provenance analogy is explicitly not SI traceability. | confirmed |
| JCGM 200:2012, DOI `10.59161/JCGM200-2012` | VIM traceability vocabulary and documented chain. | Normative custody semantics are not physical quantities. | confirmed |
| GAO-24-106786 | Independence, objectivity, competence and quality management in government audit. | No Yellow Book audit opinion or mandate follows. | confirmed |
| NIST SP 800-53 Rev.5, DOI `10.6028/NIST.SP.800-53r5`, AC-5 | Separation of duties as a control pattern. | Not evidence that duties are actually separated or a security authorization. | confirmed |
| Ofqual Condition G4 | Confidential assessment material and conflict-free competent breach investigation. | Secrecy is not validity and software is not an examinee. | confirmed |
| Avizienis, DOI `10.1109/TSE.1985.231893` | N-version diversity as a fault-tolerance architecture. | Diversity is not proof of independent failure. | confirmed |
| Knight & Leveson, DOI `10.1109/TSE.1986.6312924` | Experimental evidence of correlated multiversion failures above an independence model. | No numeric reliability factor imported. | confirmed |
| CMU/SEI-96-TR-022, DOI `10.1184/R1/6572228.v1` | Cleanroom process separation and formal/statistical discipline. | Does not prove correctness or independence by itself. | confirmed |
| HKUST-CS98-01 | Metamorphic relations for oracle-limited testing. | Relations may themselves be wrong; not a full oracle. | confirmed; replace arXiv-only link with institutional primary source |
| RFC 8785, DOI `10.17487/RFC8785` | Deterministic JSON canonicalization. | Canonical bytes do not prove semantic correctness. | confirmed |
| RFC 9162, DOI `10.17487/RFC9162` | Append-only Merkle history, inclusion/consistency evidence and split-view threat. | CT is experimental and domain-specific; logs do not prevent semantic misissue. | confirmed |
| NIST SP 800-57 Pt.1 Rev.5, DOI `10.6028/NIST.SP.800-57pt1r5` | Key generation, protection, rotation, recovery, compromise and destruction lifecycle. | Does not choose custodian/topology or prove semantic correctness. | confirmed |

## 3. Domain conclusion

The source use is unusually disciplined. Conformity assessment, metrology, audit, examination, N-version, cleanroom, metamorphic testing, canonicalization, transparency logs and key management are used as transferable control patterns with explicit limits. No source is used to confer standing. The only citation defect is bibliographic: HKUST-CS98-01 should point first to the HKUST institutional record rather than only to a later arXiv republication.
