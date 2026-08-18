---
title: S0-GAP-02 — Hostile independent audit
status: draft_audit
kind: research-audit
verified_commit: a7c34cc40b649a10b6878228a8a57acc498f279a
pinned_repository_commit: 1a7a2d05ebba22fae80e9934329e4b880806588e
research_only: true
authoritative_for:
  - independent audit findings over S0-GAP-02 at the verified commit
  - audit disposition and required revision boundary
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

# S0-GAP-02 — Hostile independent audit

## 1. Executive verdict

**Audit disposition: `GO_WITH_REVISIONS`.** The research direction is substantially right: dual diverse evaluators, blocking disagreement, a diagnostic-only same-code rebuild, finite set-valued expectations, append-only oracle custody, and bounded passage are the correct architecture family. Its strongest feature is self-directed failure: `F-04` returns `ARCHITECTURE_FALSIFIED` when both independent channels accept a seeded wrong product result.

The package is not yet ready for unconditional consolidation. Four blocking defects remain: the allowed common substrate is not formally answer-neutral; discriminator adequacy is not constructed by merely naming one discriminator; specification-side shared faults have no executable outcome; and catch-all expectation invalidity is not decidable under the stated schema. These are technical defects, not only the acknowledged institutional dependency. The architect may preserve `accepted_narrow_scope`, but its rationale must include these required revisions.

No finding authorizes scoring, implementation, an owner appointment, or an `OPS-R15` unblock.

## 2. Count reconciliation

| Severity | Count |
|---|---:|
| blocking | **4** |
| material | **10** |
| minor | **1** |
| commendation | **16** |
| **Total** | **31** |

The prose agrees with the table: this audit records **31 findings: 4 blocking, 10 material, 1 minor, and 16 commendations**. Findings are adjudicated individually; commendations do not offset blocking findings.

## 3. Complete finding register

Unless otherwise stated, audited artifact paths are relative to `policy-engine/docs/research/policy-operations/`, and source paths are relative to the repository root at the pinned commit.

| ID | Severity | Finding | Evidence | Audit verdict |
|---|---|---|---|---|
| `S0-GAP-02-I-001` | **material** | The complete source-token census remains unresolved in this audit | `s0-gap-02/orientation-ledger.md:35-78`; audit orientation ledger §2-§3. | The inherited 183/80/44 figures are neither confirmed nor contradicted. The exact fixed-string command must run from a complete checkout; this audit does not substitute ranked search. |
| `S0-GAP-02-I-002` | **commendation** | The researcher correctly refused to manufacture the census | `s0-gap-02/orientation-ledger.md:35-78,114-119`. | `not_established` is the correct P35 verdict for that environment, with a reproducible command supplied. |
| `S0-GAP-02-I-003` | **commendation** | The bounded three-owner concept sample is accurately characterized | `policy_benchmarking.py`, `grounding_benchmark.py`, and `semantic_fixtures.py`; main report `:91-119`. | 3/3 were read and 3/3 are unsuitable as independent custody verifiers; `grounding_benchmark.py` exhibits both product-logic imports and answer-visible fields. |
| `S0-GAP-02-I-004` | **commendation** | OPS-R15 prior art was not selectively sampled | `s0-gap-02/orientation-ledger.md:101-110`. | The report plus seven audit artifacts form an 8/8 denominator and the package extends rather than repeats them. |
| `S0-GAP-02-I-005` | **material** | Whole-tree absence language exceeds the bounded evidence | Main report `:91-106`; handoff `:27-31`; audit orientation ledger §4. | “No eligible independent custody oracle was established” is supportable. “No independent oracle at all” is a universal repository claim not proved by the incomplete census and three-owner sample. |
| `S0-GAP-02-II-001` | **commendation** | External regimes are transferred with honest limits | `s0-gap-02/external-source-and-transfer-ledger.md:34-88`; ISO/IEC 17043:2023, 17025:2017, 17011:2017; ILAC P9/P10; JCGM 200:2012; GAO-24-106786; NIST AC-5; Ofqual G4; RFCs 8785/9162; NIST SP 800-57. | No accreditation, metrological traceability, government-audit opinion, examination validity, or legal standing is borrowed. |
| `S0-GAP-02-II-002` | **minor** | The metamorphic-testing link is a later arXiv republication, not the primary institutional report | `s0-gap-02/external-source-and-transfer-ledger.md:76`; stable identifier HKUST-CS98-01. | Use the HKUST institutional report as the primary link and keep the arXiv copy as a convenience mirror. |
| `S0-GAP-02-III-001` | **blocking** | The allowed overlap `N ∪ B` is not formally constrained to answer-neutral semantics | `s0-gap-02/independence-model-and-evaluator-interface.md:77-113`, especially conditions 1-4. | Condition 4 prevents fitting to product behavior, but it does not prevent `B` or `N` from embedding an executable admission/status rule shared by both evaluators and the product. Proposition 1 is valid only for defects outside `N ∪ B`; the headline non-circularity needs an explicit answer-neutrality predicate and gate for allowed common artifacts. |
| `S0-GAP-02-III-002` | **material** | Condition 9 overstates machine-checkability | `s0-gap-02/independence-model-and-evaluator-interface.md:101-111`; main report `:168-176`. | Authorship influence, competence, undeclared shared design inputs, and non-collusion cannot all be established by machine evidence. Split conditions into recomputable, attested, and institutionally accepted classes; absence of the latter must remain `not_established`. |
| `S0-GAP-02-III-003` | **blocking** | One named discriminator per failure family does not prove discriminator adequacy | `s0-gap-02/independence-model-and-evaluator-interface.md:110,310-317`. | A precommitted but irrelevant or tautological discriminator satisfies the text and lets the seeded fault pass. Require a mutation-to-discriminator witness, a broken-channel liveness probe, and a negative control that fails when the relevant discriminator is removed. |
| `S0-GAP-02-III-004` | **blocking** | The suite lacks a specification-side seeded-fault gate while the standing calls the remaining gap institutional | `s0-gap-02/independence-model-and-evaluator-interface.md:113,127-137,338`; `integration-handoff-and-open-questions.md:178`; main report `:34-39,678`. | A defect seeded in shared `B` or `O_v` may be accepted by both diverse evaluators without violating implementation provenance. The text concedes this, but no executable falsifier determines the resulting claim status. Add the case and narrow the standing until specification assurance is explicit. |
| `S0-GAP-02-III-005` | **commendation** | Shared inputs are correctly distinguished from shared answer-producing provenance | `s0-gap-02/independence-model-and-evaluator-interface.md:77-80,113`. | This is a sound and unusually explicit distinction. The package does not claim statistical independence of human errors. |
| `S0-GAP-02-III-006` | **commendation** | Passage is a conjunction, not a vote | `s0-gap-02/independence-model-and-evaluator-interface.md:318-320`; main report `:185-197`. | Knight-Leveson is used as a reason not to trust simple majority voting; no numerical reliability gain is claimed. |
| `S0-GAP-02-IV-001` | **commendation** | All four commissioned models are honestly evaluated and the clean rebuild stays diagnostic | `s0-gap-02/independence-model-and-evaluator-interface.md:139-148`; `oracle-custody-and-adjudication-protocol.md:109-120`; `mutation-and-reproducibility.md:196-269`. | `C` never enters the verification conjunction, receipt claim, or handoff as independent evidence. |
| `S0-GAP-02-V-001` | **commendation** | F-04 is self-directed and reaches `ARCHITECTURE_FALSIFIED` | `s0-gap-02/falsifier-suite.md:156-201,456-462`. | The wrong product result may pass incremental and clean-build parity; if both independent channels accept it, the architecture—not the product—fails. |
| `S0-GAP-02-V-002` | **material** | The mutation generator is not separated from evaluator semantic provenance | `s0-gap-02/mutation-and-reproducibility.md:111-146`; `integration-handoff-and-open-questions.md:71-76`. | The text blocks product and `R_v` answer-path imports but does not prohibit `M_v` from sharing a private semantic ancestor with `P_v` or its relation validator. Add a three-way provenance rule and attack. |
| `S0-GAP-02-V-003` | **material** | Competent but uniformly mistaken reviewers are outside the falsifier suite | `s0-gap-02/oracle-custody-and-adjudication-protocol.md:211-275`; `s0-gap-02/falsifier-suite.md:438-462`. | Preserving unanimous positions does not detect a shared misconception. Add blinded proficiency anchors and an expected `SPECIFICATION_ASSURANCE_NOT_ESTABLISHED` outcome when all reviewers miss a seeded premise defect. |
| `S0-GAP-02-V-004` | **material** | A-13 depends on truthful provenance disclosure | `s0-gap-02/falsifier-suite.md:416-436`. | Two languages with one private semantic ancestor are caught only when that ancestor is declared or independently discovered. Add a forensic provenance-omission attack and require independent source/build/network evidence rather than self-attestation alone. |
| `S0-GAP-02-VI-001` | **blocking** | `Compatible(x,y)` and the anti-catch-all rule are not executable without a decidable language and bounded trace domain | `s0-gap-02/public-schema-and-sealed-expectations.md:245-312`. | A bundle can use a tautological positive predicate (`event_count >= 0`) and an unsatisfiable negative predicate while satisfying every syntactic rule. Detecting that every possible trace matches requires a finite/enumerable trace universe or a terminating decision procedure. Define that boundary; otherwise validation is aspirational. |
| `S0-GAP-02-VI-002` | **commendation** | Finite alternatives, explicit exclusions, and blocking indeterminacy are the right ambiguity model | `s0-gap-02/public-schema-and-sealed-expectations.md:225-312`. | The format does not use wildcard alternatives, does not majority-vote ambiguity away, and prevents timeout/unsupported predicate results from inheriting acceptance. |
| `S0-GAP-02-VII-001` | **material** | The role matrix permits one semantic origin to author both `B` and `O_v` | `s0-gap-02/oracle-custody-and-adjudication-protocol.md:86-103`. | Scenario author and expectation author are not mutually incompatible. That is precisely the specification-side common-cause channel. Require independent derivation/review or an explicit dual-control rule. |
| `S0-GAP-02-VII-002` | **material** | The conceded access-log incompleteness is not bound to run invalidation | `s0-gap-02/oracle-custody-and-adjudication-protocol.md:140-175`; `mutation-and-reproducibility.md:196-269`. | The receipt binds an access-log head, but not an independently reconciled storage/network/key-service completeness verdict. A missing event is acknowledged as non-exculpatory, yet the run gate does not say what fails. Bind the external audit evidence and its disposition. |
| `S0-GAP-02-VII-003` | **commendation** | Oracle correction and supersession are append-only | `s0-gap-02/oracle-custody-and-adjudication-protocol.md:311-343`. | An old receipt cannot silently inherit a corrected expectation. Historical bytes, challenges, and scope effects remain visible. |
| `S0-GAP-02-VII-004` | **commendation** | The silent-change falsifier is genuinely detectable under its stated integrity assumptions | `s0-gap-02/oracle-custody-and-adjudication-protocol.md:313-343`. | Digest mismatch produces `RUN_INVALID` and `ORACLE_HISTORY_VIOLATION`; the claim is conditional on retained receipt/key/log evidence and does not overstate semantic correctness. |
| `S0-GAP-02-VIII-001` | **commendation** | The package conforms to the ratified kernel boundary | Main report `:40-90`; `mutation-and-reproducibility.md:275-303`; findings `S0-K13`-`S0-K16`, `INT-K05`, `PV-K06`. | It tests observable semantics, keeps same-code rebuild outside verification, preserves dissent/hidden mutations, and bounds passage to named artifacts without authority. |
| `S0-GAP-02-VIII-002` | **commendation** | The P27/P28 exception is split by function rather than used as a general duplication licence | `s0-gap-02/independence-model-and-evaluator-interface.md:326-334`; `integration-handoff-and-open-questions.md:60-94`. | Product facts and diagnostic rebuild extend canonical owners; answer-producing verification remains outside by explicit S0-K14 exception. |
| `S0-GAP-02-IX-001` | **commendation** | Declining downstream capability labels is disciplined, not evasive | `s0-gap-02/integration-handoff-and-open-questions.md:22-58`. | The work supplies prerequisite tests and a safe transition order. It does not misuse `producer_missing`, `bridge_missing`, or `verification_missing` without their required endpoints/chain. |
| `S0-GAP-02-IX-002` | **material** | The bounded claim template does not explicitly bar a positive claim while blocking challenges remain open | `s0-gap-02/mutation-and-reproducibility.md:196-289`, especially `open_challenge_digests`. | The receipt can record open challenges, but the human-readable claim omits the required no-unresolved-blocking-challenge condition. Add it to `h` and the rendered claim. |
| `S0-GAP-02-X-001` | **commendation** | Wave isolation and hard prohibitions hold over the complete ten-file delivery | Audited commit `a7c34...`: 10 added Markdown files, 3153 lines; all ten frontmatters contain `may_not_use_for`; no OPS-R14, PAO-R36, or PAO-R4 file is touched. | Dependencies are named without appropriating their mechanics or semantics; no score, owner appointment, status lattice, or unblock is issued. |
| `S0-GAP-02-X-002` | **material** | The stated reason for `accepted_narrow_scope` is incomplete | `integration-handoff-and-open-questions.md:178`; `independence-model-and-evaluator-interface.md:338`; `delivery-readback.md:91`. | The institutional dependency is real, but the delivered architecture also has technical closure gaps in allowed common semantics, discriminator adequacy, specification-side faults, and expectation decidability. Standing may remain `accepted_narrow_scope` only after those are named as required revisions. |
| `S0-GAP-02-X-003` | **commendation** | Audited bytes and provenance are reconstructable | `s0-gap-02/delivery-readback.md:50-64`; audited commit `a7c34...`. | All nine content SHA-256 values match; the receipt is the tenth file; independent git-blob comparison matched 10/10 remote blobs to the local package. |

## 4. What must survive consolidation

The following strengths are load-bearing and should not be weakened while correcting the defects:

1. `C` remains outside verification everywhere.
2. `R_v` and `P_v` must both pass; disagreement blocks and is never majority-voted away.
3. Finite alternatives preserve genuine ambiguity without wildcard acceptance.
4. Raw reviewer dissent, abstention, recusal, and evaluator disagreement remain append-only.
5. Oracle corrections supersede; prior receipts are not silently rescored.
6. Every passage claim remains bounded exactly as `S0-K16` requires.
7. `ARCHITECTURE_FALSIFIED` remains reachable against the verifier design itself.

## 5. Standing recommendation

Keep the research artifact’s substantive standing as **`accepted_narrow_scope` with required technical revisions**, not `GO`. The second competent independent function remains an institutional prerequisite, but it is not the only unresolved premise. Consolidation should require execution of `R1`-`R11` in the recommended-revision register before treating the formal construction as closed.
