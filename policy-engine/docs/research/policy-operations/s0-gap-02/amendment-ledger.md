---
title: S0-GAP-02 — Amendment ledger after independent audit
status: research_amendment
kind: research-amendment-ledger
research_task: S0-GAP-02
research_only: true
repository_pin: 109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee
source_tree_equivalent_pin: 1a7a2d05ebba22fae80e9934329e4b880806588e
audited_commit: a7c34cc40b649a10b6878228a8a57acc498f279a
audit_commit: 3abbaf8c2808e31fd7d8f9929b696e78dc91b3d4
amendment_branch: research/s0-gap-02-amendment
result_standing: accepted_narrow_scope
authoritative_for:
  - disposition of every independent-audit finding against the amended research package
  - mapping of audit revisions R1 through R15 to exact amended artifacts
  - evidence boundary for later independent conformance verification
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization or API contract
  - canonical owner, evaluator, custodian, reviewer panel or vendor appointment
  - authority grant
  - capability claim
  - benchmark passage
  - legal-sufficiency conclusion
  - permission to score OPS-R15
  - claim that OPS-R15 is unblocked or scorable
  - new project outcome-vocabulary element
  - automatic amendment of any plan, backlog or system-design decision
---

# S0-GAP-02 amendment ledger

## 1. Amendment standing and scope

The hostile independent audit returned `GO_WITH_REVISIONS`. This amendment accepts all four blocking findings and every standing-critical revision. The architecture family and its seven load-bearing strengths are preserved: `C` stays outside verification; `R_v` and `P_v` both pass or the run blocks; finite alternatives remain; raw dissent remains append-only; corrections supersede without silent rescoring; claims remain bounded under `S0-K16`; and `F-04` can still return `ARCHITECTURE_FALSIFIED` against the verifier design itself.

The amended research remains **`accepted_narrow_scope`**. Technical closure is specified at the research-contract level but has not been operationally evidenced, and the second competent independently governed function remains absent. No audit finding is treated as authority to score or implement.

## 2. Complete audit-finding disposition

The denominator is the complete independent-audit register: **31 findings**. Dispositions use exactly `accepted`, `accepted_with_variation`, or `declined_with_reason`.

| Audit finding | Severity | Disposition | Exact amended change | Where it landed |
|---|---|---|---|---|
| `S0-GAP-02-I-001` | material | `accepted` | Replaced incomplete ranked-search census with architect-supplied complete fixed-string tree walk; stated path, Python-only, all-source, line and occurrence denominators. | `orientation-ledger.md` §3; main report §4. |
| `S0-GAP-02-I-002` | commendation | `accepted` | Preserved the finding that refusing to manufacture 183/80/44 was correct in the original environment; distinguished correct numbers from unstated file-type denominator. | `orientation-ledger.md` §§1, 3, 6. |
| `S0-GAP-02-I-003` | commendation | `accepted` | Preserved denominator 3/3 named owners and the exact `grounding_benchmark.py` product-import/expected-field evidence. | `orientation-ledger.md` §4; main report §4.2. |
| `S0-GAP-02-I-004` | commendation | `accepted` | Preserved 8/8 OPS-R15 prior-art inventory and described S0-GAP-02 as an extension rather than invention. | `orientation-ledger.md` §5. |
| `S0-GAP-02-I-005` | material | `accepted` | Replaced universal absence language with “no eligible independent custody oracle was established by the OPS-R15 chain and bounded three-owner sample”; token census is not semantic classification. | `orientation-ledger.md` §§4, 6; `integration-handoff-and-open-questions.md` §1; main report §§4.2, 17.1. |
| `S0-GAP-02-II-001` | commendation | `accepted` | Preserved every external regime’s explicit non-transfer limit; no accreditation, metrological or audit standing is borrowed. | `external-source-and-transfer-ledger.md`; main report §§7, 19. |
| `S0-GAP-02-II-002` | minor | `accepted` | Made the HKUST institutional publication record the primary HKUST-CS98-01 link and retained arXiv only as a later mirror. | `external-source-and-transfer-ledger.md` §5. |
| `S0-GAP-02-III-001` | blocking | `accepted` | Defined `AnswerNeutral(z,f)` and `A_f`; common overlap is restricted to artifacts proved representation-only by allowlist, transitive source/SBOM/network evidence, family-specific poisoned helpers and independent review. Restated Proposition 1 with actual scope. | `independence-model-and-evaluator-interface.md` §§1.1, 3.1, 7.1, 8; main report §§5, 6, 8. |
| `S0-GAP-02-III-002` | material | `accepted_with_variation` | Replaced “machine-checkable evidence for conditions 1–8” with a six-way P37 register: `recomputed`, `machine_observed`, `independently_reconciled`, `attested`, `institutionally_accepted`, `not_established`; added falsify-the-declaration probe. | `independence-model-and-evaluator-interface.md` §§2, 3.1.1; `integration-handoff-and-open-questions.md` §3.1; main report §§3, 6.2.  **Superseded 2026-08-17 by ratified `W4-K02`:** the six-way register is reduced to the five registered `P37` classes and the three distinctions are carried as required sub-annotations. The amendment's substance stands; only the vocabulary shape is corrected. |
| `S0-GAP-02-III-003` | blocking | `accepted` | Added `DiscriminatorWitness` binding mutation, expected semantic delta, named discriminator, liveness, removal and neutralization probes; removal/neutralization fails closed as `EVALUATOR_COVERAGE_NOT_ESTABLISHED`. | `independence-model-and-evaluator-interface.md` conditions 9 and Proposition 2; `falsifier-suite.md` F-04; main report §§6.2, 16. |
| `S0-GAP-02-III-004` | blocking | `accepted` | Added specification-assurance channel `S_v`, attack A-14 and claim split. A bad shared `B`/`O_v` accepted by both evaluators yields exact `SPECIFICATION_ASSURANCE_NOT_ESTABLISHED`; stronger claim is withheld. | `independence-model-and-evaluator-interface.md` §§2, 3.1, 6.3, Proposition 5; `falsifier-suite.md` A-14; `mutation-and-reproducibility.md` §9; main report §§3, 6, 15–16. |
| `S0-GAP-02-III-005` | commendation | `accepted` | Preserved shared-input/shared-answer-provenance distinction and explicitly routed shared-specification correctness through `S_v`. | `independence-model-and-evaluator-interface.md` §2; main report §§5–6. |
| `S0-GAP-02-III-006` | commendation | `accepted` | Preserved blocking conjunction; Knight–Leveson remains a qualitative reason to reject voting, with no numeric reliability claim. | `independence-model-and-evaluator-interface.md` §§4, 6.3, Proposition 3; main report §7. |
| `S0-GAP-02-IV-001` | commendation | `accepted` | Preserved all four comparative models and kept `C` absent from every verification/specification-assurance conjunction, receipt claim and handoff. | `independence-model-and-evaluator-interface.md` §§4–5; main report §§7–8, 11, 15, 17. |
| `S0-GAP-02-V-001` | commendation | `accepted` | Preserved exact self-directed `ARCHITECTURE_FALSIFIED` outcome when both independent channels accept an intact valid seeded wrong product result. | `falsifier-suite.md` F-04; `independence-model-and-evaluator-interface.md` Proposition 2; main report §16. |
| `S0-GAP-02-V-002` | material | `accepted` | Added separate relation validator `J_v`; required M/J/R/P private semantic-provenance separation and A-15 rejection before product scoring. | `independence-model-and-evaluator-interface.md` conditions 4; `mutation-and-reproducibility.md` §§3–5; `falsifier-suite.md` A-15; main report §§8, 14, 16. |
| `S0-GAP-02-V-003` | material | `accepted` | Required blinded reviewer proficiency anchors and drift checks; competent unanimity cannot establish assurance without them; added A-16. | `oracle-custody-and-adjudication-protocol.md` reviewer qualification sections; `falsifier-suite.md` A-16; main report §12.2. |
| `S0-GAP-02-V-004` | material | `accepted` | Added A-17 for undeclared private ancestry, independent source/build/network forensics and poisoned generated-table probe. | `falsifier-suite.md` A-17; `independence-model-and-evaluator-interface.md` §7; main report §16. |
| `S0-GAP-02-VI-001` | blocking | `accepted` | Chose finite enumerated trace domain plus total decidable `S0-GAP-02-PDL-1`; added proof-producing SAT/UNSAT/TAUT certificates and mandatory catch-all rejection; unknown/timeout blocks under PV-K06. | `public-schema-and-sealed-expectations.md` §§4–6; `falsifier-suite.md` A-18; main report §10. |
| `S0-GAP-02-VI-002` | commendation | `accepted` | Preserved finite alternatives, explicit exclusions, bounded variation and blocking indeterminacy; no wildcard or majority-resolution escape was introduced. | `public-schema-and-sealed-expectations.md` §§4–6; main report §10. |
| `S0-GAP-02-VII-001` | material | `accepted` | Closed scenario/expectation common origin through independent derivation or dual control; expanded role incompatibilities across M/J/R/P and added role-window validator/A-20. | `oracle-custody-and-adjudication-protocol.md` role matrix; `falsifier-suite.md` A-20; main report §§12–13. |
| `S0-GAP-02-VII-002` | material | `accepted` | Bound oracle, storage, network and key-service audit heads plus independent reconciliation. Inconsistency is `RUN_INVALID`; unresolved completeness is `INDEPENDENCE_NOT_ESTABLISHED`. | `oracle-custody-and-adjudication-protocol.md` access sections; `mutation-and-reproducibility.md` receipt; `falsifier-suite.md` A-19; main report §13.3. |
| `S0-GAP-02-VII-003` | commendation | `accepted` | Preserved append-only correction/supersession and historical receipt binding. | `oracle-custody-and-adjudication-protocol.md` correction sections; main report §13.5. |
| `S0-GAP-02-VII-004` | commendation | `accepted` | Preserved silent-change detectability under retained digest/key/log evidence; no semantic-correctness overclaim added. | `oracle-custody-and-adjudication-protocol.md` silent-change falsifier; main report §13.5. |
| `S0-GAP-02-VIII-001` | commendation | `accepted_with_variation` | Preserved S0-K13–K16, INT-K05 and PV-K06 conformance; added INT-K08 negative completion and explicit no-blocking-challenge rider. | Main report §§2–3, 15, 17; `mutation-and-reproducibility.md` §9. |
| `S0-GAP-02-VIII-002` | commendation | `accepted` | Preserved function-based P27/P28 exception; product facts/diagnostics extend canonical owners while answer-producing verification remains separate under S0-K14. | `independence-model-and-evaluator-interface.md` §9; `integration-handoff-and-open-questions.md` §3; main report §17.2. |
| `S0-GAP-02-IX-001` | commendation | `accepted` | Preserved prerequisite-safe missing-state vocabulary and safe transition ordering; no downstream label is borrowed. | `integration-handoff-and-open-questions.md` §2; main report §17.1. |
| `S0-GAP-02-IX-002` | material | `accepted` | Defined blocking challenge classes; required `no_unresolved_blocking_challenge` in `h`, receipt and rendered stronger claim; added A-21. | `oracle-custody-and-adjudication-protocol.md` challenge section; `mutation-and-reproducibility.md` §9; `falsifier-suite.md` A-21; main report §§13.5, 15–16. |
| `S0-GAP-02-X-001` | commendation | `accepted` | Preserved wave-4 isolation and every prohibition; amendment touches only S0-GAP-02 Markdown. | Main report §21; `integration-handoff-and-open-questions.md` §5; every frontmatter. |
| `S0-GAP-02-X-002` | material | `accepted` | Corrected every standing passage: narrow scope reflects unexecuted technical gates **and** absent institutional function, not institution only. | Main report §§1, 22; `independence-model-and-evaluator-interface.md` §10; `integration-handoff-and-open-questions.md` §8; all support conclusions; `delivery-readback.md` §5. |
| `S0-GAP-02-X-003` | commendation | `accepted` | Preserved historical 9/9 content-digest verification and architect-side provenance; separately records amended branch readback. | `delivery-readback.md` §§1–4. |

**Disposition arithmetic:** 31 total = 29 `accepted` + 2 `accepted_with_variation` + 0 `declined_with_reason`. Commendations are preserved; they do not offset blockers.

## 3. Audit revision register R1–R15

| Revision | Standing | Amended contract | Required execution evidence for re-audit | Location |
|---|---|---|---|---|
| `R1` common substrate | required | `AnswerNeutral(z,f)` and `A_f`; semantic-family prohibition and P37 gate. | Machine allowlist; transitive source/SBOM/network closure; poisoned helper for every family; independent review. | Independence §§1, 3, 7; main §§5–8. |
| `R2` evidence classes | required, subsumed by P37 | Six exact classes frozen at admission; last three cannot masquerade as machine proof. | Committed predicate register and falsify-the-declaration run. | Independence §3.1.1; handoff §3.1. |
| `R3` discriminator adequacy | required | `DiscriminatorWitness` with expected delta, liveness, removal, neutralization. | F-04 evidence showing C parity, independent failure, and removal fail-closed. | Independence condition 9/Prop. 2; falsifier F-04. |
| `R4` specification-side fault | required | `S_v`, A-14, not-refuted/established claim split. | Committed bad-axiom fixture where R/P agree and stronger claim is withheld. | Independence §6.3/Prop. 5; falsifier A-14; receipt §9. |
| `R5` decidable compatibility | required | Finite domain + total PDL-1 + proof-producing catch-all checks. | Audit catch-all rejected; timeout/unsupported/unknown blocks. | Public schema §§4–6; falsifier A-18. |
| `R6` M/J separation | required | M/J/R/P private semantic-provenance separation. | A-15 shared table rejected before scoring. | Independence condition 4; mutation §§3–5; falsifier A-15. |
| `R7` reviewer common-mode | required | Blinded proficiency anchors and drift checks. | A-16 unanimous miss yields specification non-establishment. | Custody reviewer qualification; falsifier A-16. |
| `R8` access evidence | required | Four audit heads plus independent reconciliation disposition. | Missing/tampered read test yields exact invalid/non-establishment result. | Custody access sections; receipt; falsifier A-19. |
| `R9` role matrix | required | B→O independent derivation/dual control; M/J/R/P conflict rules. | Role-window validator rejects A-20 assignments. | Custody role matrix; falsifier A-20. |
| `R10` challenge gate | required | Blocking challenge classes and claim-gate predicate. | One open blocking challenge prevents passage rendering. | Custody challenge section; receipt §9; falsifier A-21. |
| `R11` standing rationale | required | Technical execution dependencies plus institutional dependency everywhere. | Claim grep shows no “institution only” or premature technical-closure statement. | Main §§1,22; independence §10; handoff §8; delivery §5. |
| `R12` census | closed by supplied data | Python/all-source/line/occurrence counts and denominators recorded. | Architect complete-walk record supplied in task; no ranked-search derivation. | Orientation §3; main §4. |
| `R13` delivery provenance | improvement accepted | Clone/push unavailable; connector writes existed; no remote state was originally claimed; architect digest delivery preserved. | Amended branch write/readback through connector. | Delivery §§1–4. |
| `R14` HKUST source | improvement accepted | Institutional HKUST record primary; arXiv mirror secondary. | Link read and retained stable report ID. | External ledger §5. |
| `R15` provenance omission | improvement accepted | A-17 with independent forensic and poisoned-table evidence. | Reproduced A-17 invalid/non-establishment result. | Falsifier A-17; independence controls. |

## 4. Outcome-vocabulary boundary

`SPECIFICATION_ASSURANCE_NOT_ESTABLISHED`, `INDEPENDENCE_NOT_ESTABLISHED`, and `EVALUATOR_COVERAGE_NOT_ESTABLISHED` are benchmark-local evidence dispositions that withhold a positive claim. They are negative completions under `INT-K08`. They are **not** a fourth product/constitutional outcome category, and this amendment does not activate the standing trigger for one.

## 5. Conformance-verification entry condition

The amendment is ready for independent conformance verification as a research artifact. Operational closure is not claimed. A later verifier must reproduce R1–R11 evidence from committed artifacts and rerun the exact expected outcomes. Prose saying “enforced,” a signed declaration, a role name or this ledger is not execution evidence.
