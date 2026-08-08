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

## 1. Method

The ledger uses standards bodies, regulators, government audit/security publications, original technical reports, and original research papers. Stable standard numbers, report numbers, RFC numbers, or DOIs are supplied so a later audit does not depend on a mutable page title. The transfer column states the mechanism that earns a place in the custody-benchmark architecture. The non-transfer column prevents analogy from becoming borrowed authority.

No source below establishes that PolicyOS, an evaluator, an oracle custodian, a reviewer, or a benchmark institution is accredited, competent, independent, legally sufficient, or appointed. The sources inform design obligations only.

## 2. Conformity assessment, proficiency testing and metrology

| Stable source | Primary-source proposition used | Transfer to a custody benchmark | What does **not** transfer | Architecture consequence |
|---|---|---|---|---|
| [ISO/IEC 17043:2023, ISO standard 80864](https://www.iso.org/standard/80864.html) | Proficiency-testing providers require competence, impartiality, and consistent operation of proficiency-testing schemes. | Treat evaluator qualification as demonstrated competence over blind/seeded cases, not as a team label; define the scheme, scoring rules, confidentiality, records, and handling of anomalous/disputed results before use. | No laboratory accreditation, measurement competence, or conformity claim is inherited. Software semantic truth is not a certified reference material, and ISO/IEC 17043 does not define custody semantics. | Require pre-acceptance evaluator proficiency exercises, impartiality/conflict controls, stable scheme versions, and retained raw results. |
| [ILAC P9:01/2024](https://ilac.org/publications-and-resources/ilac-policy-series/) | ILAC policy uses proficiency testing and inter-laboratory comparison as evidence in accreditation processes. | Use inter-evaluator blind comparison and seeded-fault performance as evidence about evaluator competence and correlated failure. | ILAC policy does not accredit this benchmark, appoint an accreditation body, or make agreement evidence of correctness. | Dual evaluators must be compared on held-out cases; agreement is evidence only when the case has an independent discriminator. |
| [ISO/IEC 17025:2017, ISO standard 66912](https://www.iso.org/standard/66912.html) | Testing and calibration laboratories are governed by competence, impartiality, consistent operation, method control, records, and result validity. | Transfer method validation, controlled records, competence scope, equipment/software fitness, handling of nonconforming work, and reproducible reporting. | The evaluator is not thereby a laboratory; no SI measurement, calibration, or ISO/IEC 17025 conformity is claimed. | Evaluator releases need scoped competence evidence, method validation, nonconformance handling, and retained reproducibility artifacts. |
| [ISO/IEC 17011:2017, ISO standard 67198](https://www.iso.org/standard/67198.html) | Accreditation bodies themselves require competence, consistent operation, and impartiality. | Oversight must also be challengeable and independent; moving the same interests one organizational level upward is not enough. | The report does not create or appoint an accreditation body and does not claim conformity with ISO/IEC 17011. | The body accepting evaluator competence must have its own mandate, conflict controls, review records, and appeal path. |
| [JCGM 200:2012 (VIM), DOI 10.59161/JCGM200-2012](https://doi.org/10.59161/JCGM200-2012) | Metrological traceability is a property of a result related to a reference through a documented unbroken chain, with each link contributing to uncertainty. | Transfer the discipline of a declared reference chain: fixture bytes → public axioms → committed expectation version → evaluator version → raw trace → receipt, with uncertainty/ambiguity recorded at the relevant link. | A custody result is not an SI quantity; hashing artifacts is not metrological traceability, and no calibration hierarchy or uncertainty budget is automatically available. | Every result must identify its reference chain and where semantic uncertainty, human judgment, or unproved approximation enters. |
| [ILAC P10:07/2020](https://ilac.org/publications-and-resources/ilac-policy-series/) | ILAC policy specifies acceptable routes for metrological traceability of measurement results. | Transfer the requirement that a claimed reference path be explicit, acceptable for its purpose, and supported by evidence rather than by a bare assertion of traceability. | ILAC P10 does not define software-oracle provenance, and a content hash alone does not establish semantic correctness. | The receipt must name each reference artifact and acceptance basis; missing semantic links yield `not_established`, not inherited safety. |

### Transfer conclusion for this regime

The decisive transfer is **proficiency plus traceable evidence**, not “laboratory” branding. A competent evaluator must demonstrate performance on blind cases and preserve a versioned chain from public question to result. The regime does not solve specification error, institutional appointment, or correlated human interpretation.

## 3. Public audit, accreditation and separation of duties

| Stable source | Primary-source proposition used | Transfer to a custody benchmark | What does **not** transfer | Architecture consequence |
|---|---|---|---|---|
| [GAO-24-106786, Government Auditing Standards 2024 Revision](https://www.gao.gov/products/gao-24-106786) | Government audit standards emphasize independence, objective high-quality work, quality management, monitoring, engagement review, and peer review. | Transfer documented threats to independence, safeguards, quality management, independent review, evidence sufficiency, and retention of disagreements/findings. | The benchmark is not a GAGAS audit; no government-audit opinion, public-sector mandate, or compliance conclusion follows. | A run cannot rely on self-attested independence; threats, safeguards, reviewers, evidence, unresolved matters, and quality review belong in the receipt. |
| [NIST SP 800-53 Rev. 5, DOI 10.6028/NIST.SP.800-53r5, control AC-5](https://doi.org/10.6028/NIST.SP.800-53r5) | Separation of duties reduces abuse without collusion by dividing mission and support functions among roles. | Transfer incompatible-role rules among product author, submission freezer, expectation author, plaintext custodian, evaluator releaser, run operator, adjudicator, and challenge disposer. | This does not establish FISMA compliance, a complete security control baseline, or independence against collusion. | Enforce role incompatibilities in identities and access policy; record exceptions; add multi-party controls where collusion is in scope. |
| [ISO/IEC 17011:2017, ISO standard 67198](https://www.iso.org/standard/67198.html) | Oversight competence and impartiality are properties to be assessed, not assumed from organizational status. | Transfer the principle that the evaluator-acceptance body must itself be reviewable and scoped. | No body is designated or accredited by this report. | Institutional acceptance remains a separate prerequisite and is the main reason for `accepted_narrow_scope`. |

### Transfer conclusion for this regime

The decisive transfer is **independence as evidenced threats, safeguards, competence and review**, not organizational distance. Code separation without access, funding, authorship, review, and challenge separation is incomplete. These sources do not convert technical evidence into public or legal authority.

## 4. Sealed assessment and examination practice

| Stable source | Primary-source proposition used | Transfer to a custody benchmark | What does **not** transfer | Architecture consequence |
|---|---|---|---|---|
| [Ofqual General Conditions of Recognition, Condition G4](https://www.gov.uk/guidance/ofqual-handbook/section-g-setting-and-delivering-the-assessment) | Confidentiality must be maintained when disclosure would undermine assessment validity; conflicts and training leakage require controls; suspected breaches require rigorous, effective investigation by competent persons without a personal interest in the outcome. | Transfer input/answer separation, access minimization, conflict records, former-personnel obligations, monitoring, breach investigation, and invalidation/rotation after exposure. | A software benchmark is not a regulated qualification, implementers are not learners, and this report does not claim Ofqual recognition or examination-law compliance. | Publish input-only fixtures; seal expectations and hidden transforms; freeze submissions before hidden-seed generation; investigate leakage independently; bind any compromised run to a typed invalid outcome. |

### Transfer conclusion for this regime

The decisive transfer is **validity-sensitive confidentiality**, not secrecy for its own sake. Public inputs may be broad, but information whose advance disclosure would permit answer memorization must be controlled, logged, investigated, and rotated. Sealing does not make the answer correct; it protects the discriminating value of an independently authored answer.

## 5. N-version, clean-room and software-test-oracle research

| Stable source | Primary-source proposition used | Transfer to a custody benchmark | What does **not** transfer | Architecture consequence |
|---|---|---|---|---|
| [A. Avizienis, “The N-Version Approach to Fault-Tolerant Software,” DOI 10.1109/TSE.1985.231893](https://doi.org/10.1109/TSE.1985.231893) | Design diversity uses separately developed versions to reduce the chance that one design fault defeats all channels. | Transfer separately authored evaluator channels, deliberate representation/algorithm/toolchain diversity, and comparison of outputs. | Majority voting is not an oracle, independence is not guaranteed, and operational fault tolerance is not benchmark correctness. | Use two diverse evaluators as a blocking conjunction with adjudication, not as a correctness-by-vote mechanism. |
| [J. C. Knight and N. G. Leveson, “An Experimental Evaluation of the Assumption of Independence in Multi-Version Programming,” DOI 10.1109/TSE.1986.6312924](https://doi.org/10.1109/TSE.1986.6312924); [University of Virginia report DOI 10.18130/V3P499](https://doi.org/10.18130/V3P499) | Independently developed versions can exhibit correlated failures substantially above an independent-failure model because a common specification and problem induce similar mistakes. | Transfer skepticism: role labels, separate teams, or different languages do not prove statistical independence; shared axioms and human interpretations remain correlated-failure surfaces. | The experiment's measured rates do not estimate this project's reliability and do not prove these evaluators will fail dependently. | Claim structural provenance independence only; register shared-specification failure separately; require seeded correlated-fault and disagreement probes; never infer a numeric reliability multiplier. |
| [CMU/SEI-96-TR-022, Cleanroom Software Engineering Reference, DOI 10.1184/R1/6572228.v1](https://doi.org/10.1184/R1/6572228.v1) | Cleanroom engineering combines explicit specification, correctness-oriented development, disciplined process, and statistically informed certification. | Transfer specification-before-implementation, controlled verification/certification work products, and separation of development evidence from certification evidence. | No “zero failures,” statistical quality level, usage profile, or Cleanroom conformity is claimed; the same-code clean rebuild is not made independent by calling it certification. | Freeze the public semantics first; retain independent evaluator artifacts and certification evidence; keep product consistency diagnostics outside the verification conjunction. |
| [T. Y. Chen, S. C. Cheung, S. M. Yiu, “Metamorphic Testing: A New Approach for Generating Next Test Cases,” technical report HKUST-CS98-01, HKUST institutional publication record](https://cse.hkust.edu.hk/faculty/scc/publ/publ.html); [later arXiv mirror](https://arxiv.org/abs/2002.12543) | Metamorphic relations derive follow-up cases and expected relations when a complete point oracle is unavailable. | Transfer declared semantic-preserving and semantic-changing transformations, adjacent cases, ID permutations, duplicate/order relations, and relation-level expected outcomes. | A metamorphic relation can itself be wrong; it does not provide a full oracle, legal truth, or universal adequacy. | Each mutation carries an independently reviewed relation certificate, applicability preconditions, expected relation, and negative seed; mutations supplement rather than replace sealed expectations. |

### Transfer conclusion for this regime

The selected architecture uses N-version **diversity without voting**, clean-room **process separation without self-certification**, and metamorphic **relations without pretending they are a complete oracle**. The Knight–Leveson result is the key elimination property for a simple “two teams agree, therefore correct” design.

## 6. Cryptographic commitment, transparency and key custody

| Stable source | Primary-source proposition used | Transfer to a custody benchmark | What does **not** transfer | Architecture consequence |
|---|---|---|---|---|
| [RFC 8785, JSON Canonicalization Scheme, DOI 10.17487/RFC8785](https://doi.org/10.17487/RFC8785) | Repeatable hashing/signing of JSON requires a deterministic representation with explicit constraints. | Transfer a public canonicalization profile and cross-language vectors before commitments are made. | Canonicalization establishes byte identity, not semantic equivalence; RFC 8785 is informational and may not fit arbitrary number/time representations without a profile. | Commit to canonical bytes; preserve original bytes; reject duplicate keys/non-finite numbers; test canonicalizers independently; never sort arrays whose order is semantic. |
| [RFC 9162, Certificate Transparency Version 2.0, DOI 10.17487/RFC9162](https://doi.org/10.17487/RFC9162) | Append-only Merkle logs support inclusion and consistency proofs, while split-view/equivocation remains a threat requiring monitoring and shared observations. | Transfer content-addressed append-only entries, signed tree heads, inclusion/consistency proofs, external witnesses, and explicit split-view falsifiers. | This is not certificate transparency, a CA trust model, or proof that logged content is correct. One log operator can still equivocate without witnesses/gossip. | Log commitments, access, runs, challenges, corrections, and supersessions; witness tree heads across parties; bind corrections to new versions rather than mutate history. |
| [NIST SP 800-57 Part 1 Rev. 5, DOI 10.6028/NIST.SP.800-57pt1r5](https://doi.org/10.6028/NIST.SP.800-57pt1r5) | Cryptographic keying material requires lifecycle controls covering generation, protection, use, backup/recovery, rotation, compromise, archival, and destruction. | Transfer explicit key roles, cryptoperiod/rotation triggers, recovery, compromise handling, historical verification, and separation of encryption from signing keys. | No algorithm, KMS, cryptographic module, vendor, key length, or compliance profile is selected; key management cannot establish semantic correctness. | Every oracle version and receipt records algorithm/key identifiers; rotation does not rewrite prior commitments; compromise creates a signed incident/supersession path and preserves verification where safe. |

### Transfer conclusion for this regime

Cryptography can prove **which committed bytes and history** were used; it cannot prove the bytes are correct. The protocol therefore combines commitments with independent semantic review and combines an append-only log with witnesses against split views.

## 7. Cross-regime synthesis

| Required property | Strongest transferred disciplines | Residual limitation kept explicit |
|---|---|---|
| Code-independent verification | N-version diversity; Cleanroom process separation; audit independence; separation of duties | Shared specifications, reviewers, incentives, and coincident mistakes can correlate failures. |
| Evaluator competence | ISO/IEC 17043 proficiency testing; ILAC P9; ISO/IEC 17025 method/competence discipline | No competent team or accrediting institution is appointed or evidenced here. |
| Traceable result | JCGM VIM and ILAC P10 reference-chain discipline; reproducible receipt | This is semantic provenance, not metrological traceability to SI. |
| Sealed expectations | Ofqual G4 confidentiality/conflict/investigation practice | Secrecy protects validity but does not make an expectation correct. |
| Anti-memorization | Metamorphic relations; proficiency blind cases; examination exposure controls | Relations and sampling can be incomplete; repeated submissions consume secrecy. |
| Challengeable immutable history | GAO evidence/review discipline; RFC 9162 append-only proofs and witnesses | Logs prove inclusion/consistency, not truth; institutional response rights remain necessary. |
| Role and key custody | NIST SP 800-53 AC-5; NIST SP 800-57 | Controls reduce but do not eliminate collusion, coercion, or institutional failure. |
| Deterministic commitments | RFC 8785 | Byte canonicalization must not silently become semantic reduction. |

## 8. Architecture selection supported by the ledger

The external evidence supports the following selection:

- a separately authored declarative reducer supplies an explicit alternative semantic construction;
- a separate predicate/metamorphic evaluator supplies a diverse, non-runtime fault channel;
- their disagreement blocks and triggers preserved adjudication rather than majority voting;
- the same-code rebuild is retained only as a consistency diagnostic;
- blind proficiency cases, sealed expectations, traceable version chains, role separation, witnessed append-only history, and challenge rights are first-class components.

The rejected alternatives fail for a named reason:

1. **Declarative reducer alone:** one independent implementation can still be wrong; no second discriminator.
2. **Predicate evaluator alone:** invariants may be too weak to establish allowed transition semantics or complete affected sets.
3. **Dual evaluators with simple voting:** N-version correlated-failure evidence disqualifies agreement or majority as a correctness theorem.
4. **Same-code rebuild as verifier:** direct circularity; it proves only consistency and fails the seeded-shared-reducer test.

The selected design remains the dual diverse evaluator model with blocking disagreement and a diagnostic-only same-code control. The audit amendment adds answer-neutral common provenance, specification-side assurance, a decidable finite-domain predicate language, adequate discriminator witnesses, mutation/relation-validator separation, reviewer proficiency, reconciled access evidence, role validation and challenge gating. These controls are specified but not operationally evidenced, and the competent independent function remains institutionally absent; both technical execution and institutional premises bound the `accepted_narrow_scope` standing.
