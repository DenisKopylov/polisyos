---
title: S0-GAP-02 — External primary-source and transfer ledger
status: research
research_only: true
repository_pin: 109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee
source_tree_equivalent_pin: 1a7a2d05ebba22fae80e9934329e4b880806588e
audited_commit: a7c34cc40b649a10b6878228a8a57acc498f279a
audit_commit: 3abbaf8c2808e31fd7d8f9929b696e78dc91b3d4
amendment_branch: research/s0-gap-02-amendment
amendment_status: audit_amended
result_standing: accepted_narrow_scope
authoritative_for:
  - external primary sources used by S0-GAP-02
  - explicit transfer and non-transfer limits from assurance, metrology, audit, assessment and software-verification regimes
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization or API contract
  - canonical owner, evaluator, custodian or vendor appointment
  - reviewer panel or evaluator-team appointment
  - authority grant
  - capability claim
  - benchmark passage
  - legal-sufficiency conclusion
  - permission to score OPS-R15
  - claim that OPS-R15 is unblocked
  - automatic amendment of any plan, backlog or system-design decision
---

# External primary-source and transfer ledger

## 1. Method and standing

Stable standard numbers, report numbers, RFCs and DOIs identify the primary sources. The transfer column states the design discipline used; the non-transfer column prevents analogy from borrowing authority. No source establishes that PolicyOS, an evaluator, an oracle custodian, a reviewer, or a benchmark institution is accredited, competent, independent, legally sufficient, or appointed.

## 2. Conformity assessment, proficiency and metrology

| Stable source | Proposition used | Transfer | Non-transfer limit |
|---|---|---|---|
| [ISO/IEC 17043:2023, ISO 80864](https://www.iso.org/standard/80864.html) | Proficiency-testing providers require competence, impartiality and consistent operation. | Blind/seeded qualification, scheme/version control, anomalous-result handling and retained raw results. | No laboratory accreditation, measurement competence or custody-semantic truth follows. |
| [ILAC P9:01/2024](https://ilac.org/publications-and-resources/ilac-policy-series/) | Proficiency testing and inter-laboratory comparison supply evidence in accredited contexts. | Compare diverse evaluator performance on held-out seeds and preserve correlated failures. | Agreement is not correctness and this benchmark is not ILAC-accredited. |
| [ISO/IEC 17025:2017, ISO 66912](https://www.iso.org/standard/66912.html) | Laboratories govern competence, impartiality, methods, records and result validity. | Scoped competence, method validation, nonconformance handling and reproducible reporting. | An evaluator is not thereby a laboratory and no SI/calibration claim is made. |
| [ISO/IEC 17011:2017, ISO 67198](https://www.iso.org/standard/67198.html) | Bodies assessing conformity-assessment bodies require competence and impartiality. | The function accepting evaluator competence must itself be scoped and challengeable. | No accreditation body is created or designated. Institutional acceptance and unexecuted technical gates both bound `accepted_narrow_scope`. |
| [JCGM 200:2012, DOI 10.59161/JCGM200-2012](https://doi.org/10.59161/JCGM200-2012) | Traceability is a documented chain to a stated reference, with uncertainty visible at each link. | Record fixture → axiom → expectation → evaluator → trace → receipt and where semantic uncertainty enters. | This is semantic provenance, not metrological traceability to SI. |
| [ILAC P10:07/2020](https://ilac.org/publications-and-resources/ilac-policy-series/) | A claimed traceability route must be explicit and evidenced. | Every reference link and acceptance basis is named; missing links remain `not_established`. | A hash alone does not establish semantic correctness. |

## 3. Public audit, separation of duties and sealed assessment

| Stable source | Proposition used | Transfer | Non-transfer limit |
|---|---|---|---|
| [GAO-24-106786, Government Auditing Standards 2024](https://www.gao.gov/products/gao-24-106786) | Independence, objectivity, competence, quality management, engagement review and peer review. | Record threats/safeguards, evidence sufficiency, independent review and unresolved findings. | No GAGAS opinion, public mandate or compliance conclusion follows. |
| [NIST SP 800-53 Rev.5, DOI 10.6028/NIST.SP.800-53r5, AC-5](https://doi.org/10.6028/NIST.SP.800-53r5) | Separation of duties reduces abuse without collusion. | Enforce incompatible product, expectation, evaluator, generator, custodian, operator and adjudicator roles. | AC-5 does not prove non-collusion or confer security authorization. |
| [Ofqual General Conditions, Condition G4](https://www.gov.uk/guidance/ofqual-handbook/section-g-setting-and-delivering-the-assessment) | Confidential assessment material and breaches require controlled access and competent conflict-free investigation. | Input/answer separation, access minimization, exposure response, rotation and invalidation. | Software is not an examinee; secrecy protects validity but does not make an answer correct. |

## 4. N-version, clean-room and metamorphic testing

| Stable source | Proposition used | Transfer | Non-transfer limit |
|---|---|---|---|
| [Avizienis, DOI 10.1109/TSE.1985.231893](https://doi.org/10.1109/TSE.1985.231893) | Design diversity uses separately developed versions to reduce common implementation faults. | Separately authored constructive (`R_v`) and relational (`P_v`) channels. | Diversity is not statistical independence and voting is not an oracle. |
| [Knight–Leveson, DOI 10.1109/TSE.1986.6312924](https://doi.org/10.1109/TSE.1986.6312924); [UVA report DOI 10.18130/V3P499](https://doi.org/10.18130/V3P499) | Nominally independent versions exhibit correlated failures because shared problems/specifications induce similar errors. | Reject agreement/majority as a correctness theorem; separately gate shared `B`/`O_v` and human interpretation. | Their measured rates do not estimate PolicyOS reliability; no numeric multiplier is imported. |
| [CMU/SEI-96-TR-022, DOI 10.1184/R1/6572228.v1](https://doi.org/10.1184/R1/6572228.v1) | Cleanroom practice emphasizes explicit specification, disciplined development and separate verification/certification evidence. | Freeze specification first and keep evaluator/certification evidence separate from product diagnostics. | No Cleanroom conformity, zero-failure or statistical quality claim; `C` remains non-verifying. |
| [Chen, Cheung, Yiu, HKUST-CS98-01, HKUST institutional record](https://cse.hkust.edu.hk/faculty/scc/publ/publ.html); [later arXiv mirror](https://arxiv.org/abs/2002.12543) | Metamorphic relations generate follow-up cases when a complete point oracle is unavailable. | Public preconditions/transforms/relations, adjacent cases and independent relation certificates. | A metamorphic relation may itself be wrong and is not a complete oracle or legal truth. |

The HKUST institutional publication record is primary; the arXiv item is retained only as a later mirror, closing audit improvement R14.

## 5. Commitments, logs and key custody

| Stable source | Proposition used | Transfer | Non-transfer limit |
|---|---|---|---|
| [RFC 8785, DOI 10.17487/RFC8785](https://doi.org/10.17487/RFC8785) | Deterministic JSON representation is needed for repeatable hashing/signing. | Public canonicalization profile, duplicate-key rejection and cross-language vectors. | Canonical bytes do not prove semantic equivalence or correctness. |
| [RFC 9162, DOI 10.17487/RFC9162](https://doi.org/10.17487/RFC9162) | Append-only Merkle logs support inclusion/consistency proofs; split views require witnesses/monitoring. | Log commitments, reads, runs, challenges, corrections and supersessions with witnessed heads. | A transparency log proves history consistency, not truth; one operator may equivocate without witnesses. |
| [NIST SP 800-57 Pt.1 Rev.5, DOI 10.6028/NIST.SP.800-57pt1r5](https://doi.org/10.6028/NIST.SP.800-57pt1r5) | Key material requires generation, protection, use, rotation, recovery, compromise and destruction controls. | Version key roles, rotation/compromise/recovery and preserve historical verification. | No algorithm, KMS, module, vendor or compliance profile is selected; keys cannot prove semantics. |

## 6. Transfer synthesis and architecture consequence

| Required property | Transferred discipline | Residual limitation |
|---|---|---|
| Code-independent verification | N-version diversity, Cleanroom separation, audit independence, AC-5 | Shared specification, reviewers, incentives and coincident errors remain correlated surfaces. |
| Evaluator competence | ISO/IEC 17043/17025 and ILAC P9 proficiency | No competent team or accepting institution is established here. |
| Traceable result | JCGM 200 and ILAC P10 reference-chain discipline | Provenance does not establish normative truth. |
| Sealed expectations | Ofqual G4 confidentiality and breach investigation | Secrecy is necessary for some validity claims but never sufficient. |
| Anti-memorization | Metamorphic relations and blind proficiency | Relations and sampling can be incomplete; repeated submissions consume secrecy. |
| Challengeable immutable history | GAO evidence discipline and RFC 9162 | Inclusion/consistency does not prove semantic correctness. |
| Key/role custody | NIST AC-5 and SP 800-57 | Controls reduce, not eliminate, collusion/coercion/institutional failure. |

The source ledger supports the selected architecture: a separately authored declarative reducer plus a separate predicate/metamorphic evaluator, blocking disagreement rather than voting, same-code `C` diagnostic only, blind proficiency, sealed expectations, explicit provenance, witnessed history and challenge rights. The audit amendment adds `AnswerNeutral`, `S_v`, finite-domain PDL-1, adequate discriminator witnesses, M/J/R/P separation, reviewer proficiency, reconciled access, role validation and challenge gating.

These transfers remain research design constraints. Their technical execution evidence is absent, and the competent independent function remains institutionally absent; both premises bound `accepted_narrow_scope`. No source confers benchmark passage, legal sufficiency, authority, implementation permission, or an OPS-R15 unblock.
