---
title: S0-GAP-02 — Recommended revision register
status: draft_audit
kind: research-audit
verified_commit: a7c34cc40b649a10b6878228a8a57acc498f279a
pinned_repository_commit: 1a7a2d05ebba22fae80e9934329e4b880806588e
research_only: true
authoritative_for:
  - executable revision requirements for the audited research
  - separation of standing-critical corrections from improvements
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

# S0-GAP-02 recommended revision

This register does not rewrite the research. It states the exact defect, required change and evidence of execution.

## A. Required for standing

### R1 — Constrain the common substrate

**Defect:** conditions 1-3 permit all of `N ∪ B` without proving answer-neutrality.

**Required change:** define `AnswerNeutral(z,f)` and restrict common provenance to artifacts that only parse, canonicalize, transport or identify declared inputs. Explicitly forbid admission, reduction, dependency/affected-set, status/authority, ambiguity-collapse and expected-answer logic in common artifacts.

**Evidence of execution:** a machine-enforced allowlist; transitive source/SBOM/network checks; poisoned “neutral helper” probes for every semantic family; independent review record.

### R2 — Split evidence classes

**Defect:** condition 9 calls evidence for conditions 1-8 machine-checkable although competence, authorship influence and non-collusion are not.

**Required change:** classify each premise as `recomputed`, `machine_observed`, `attested`, or `institutionally_accepted`; no absent institutional premise may be rendered as machine-proved.

**Evidence of execution:** receipt schema and example whose missing competence/non-collusion evidence yields `INDEPENDENCE_NOT_ESTABLISHED`.

### R3 — Prove discriminator adequacy

**Defect:** one precommitted discriminator may be irrelevant or tautological.

**Required change:** bind each seeded mutation to its expected semantic delta and named discriminator; add liveness, removal and neutralization probes.

**Evidence of execution:** F-04 run where control parity passes, relevant independent discriminator fails, and removing that discriminator makes evaluator acceptance fail closed as `EVALUATOR_COVERAGE_NOT_ESTABLISHED`.

### R4 — Add specification-side fault falsifier

**Defect:** shared bad `B` or `O_v` may be accepted by both evaluators.

**Required change:** add A-14 with exact outcome `SPECIFICATION_ASSURANCE_NOT_ESTABLISHED`; distinguish “not refuted under the committed specification” from “acceptable custody semantics established.”

**Evidence of execution:** committed fixture in which both evaluators agree on a seeded bad axiom and the final bounded claim is withheld.

### R5 — Make compatibility decidable

**Defect:** universal/catch-all alternatives cannot be mechanically rejected over an unbounded trace/predicate language.

**Required change:** define a finite trace model, a total decidable predicate DSL, or a proved-conservative checker whose unknown result blocks.

**Evidence of execution:** the tautological-positive/unsatisfiable-negative bundle in this audit is rejected; timeout/unsupported theory produces a blocking PV-K06 outcome.

### R6 — Separate `M_v` from evaluator semantics

**Defect:** generator and evaluator may share a private semantic transformation ancestor.

**Required change:** extend SemProv conditions and role incompatibilities across `M_v`, relation validators, `R_v` and `P_v`.

**Evidence of execution:** A-15 imports a shared bad relation table and is rejected before product scoring.

### R7 — Add reviewer common-mode assurance

**Defect:** competent unanimous reviewers may share one misconception.

**Required change:** require blinded proficiency anchors and drift checks; unanimous support is not enough without passed assurance for the claimed domain.

**Evidence of execution:** A-16 yields `SPECIFICATION_ASSURANCE_NOT_ESTABLISHED` when every reviewer misses a seeded premise defect.

### R8 — Bind independent access evidence

**Defect:** access-log head alone cannot prove no unlogged read.

**Required change:** bind storage, network and key-service audit heads plus reconciliation result into the receipt; unresolved gaps invalidate or withhold the claim.

**Evidence of execution:** missing/tampered access event with inconsistent external logs produces `RUN_INVALID`.

### R9 — Close role-matrix common origin

**Defect:** scenario author may also author expectations; generator/relation-validator conflicts are incomplete.

**Required change:** add dual-control/independent-review requirements for B-to-O derivation and explicit M/P/R conflict rules.

**Evidence of execution:** role assignment validator rejects the forbidden combinations for one evaluation window.

### R10 — Bind challenges to the claim gate

**Defect:** receipt may list open challenges while the rendered claim omits their effect.

**Required change:** define blocking challenge classes and require `no_unresolved_blocking_challenge` in `h` and the human-readable claim.

**Evidence of execution:** a receipt with one unresolved blocking challenge cannot render the S0-K16 passage sentence.

### R11 — Correct the standing rationale

**Defect:** the package says the remaining reason for narrow standing is institutional and calls the architecture technically coherent.

**Required change:** retain `accepted_narrow_scope` only with explicit technical dependencies R1-R10 plus the institutional dependency.

**Evidence of execution:** all standing passages use the same bounded rationale and no file claims technical closure before the revision evidence exists.

## B. Improvements, not standing blockers

### R12 — Reproduce the full source census

Run the audited fixed-string command from a complete checkout and record files, matching lines and occurrences for all six tokens with the exact denominator. Do not derive it from ranked search.

### R13 — Correct delivery provenance

Amend the receipt to say clone/push were unavailable but connected write actions existed; preserve the architect-side digest and commit-chain facts.

### R14 — Prefer the primary HKUST source

Link HKUST-CS98-01 to its institutional report record first; retain the arXiv republication only as a mirror.

### R15 — Add provenance-omission attack

Add A-17, including independent forensic source/build/network evidence and a poisoned generated-table probe.

## C. Revision closure

A revision is ready for re-audit only when R1-R11 each has a committed evidence reference and the falsifier suite’s expected outcomes are reproduced from the revised artifact. Prose saying “enforced” is not evidence of execution.
