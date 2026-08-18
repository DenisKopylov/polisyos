---
title: S0-GAP-02 — Formal argument, falsifier, ambiguity and custody audit
status: draft_audit
kind: research-audit
verified_commit: a7c34cc40b649a10b6878228a8a57acc498f279a
pinned_repository_commit: 1a7a2d05ebba22fae80e9934329e4b880806588e
research_only: true
authoritative_for:
  - Passes III-VII formal and adversarial analysis
  - constructed attacks and specification-side fault case
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

# S0-GAP-02 formal argument audit

## 1. Independence conditions

| Condition | Checkability | Audit |
|---:|---|---|
| 1-3 | partly machine-checkable | Dependency/source/SBOM/network graphs can witness overlap, but completeness of `SemProv` still needs attestations and forensic review. |
| 4 | institutional/forensic | “Not generated, fitted or selected from product results” is not derivable from bytes alone. |
| 5-6 | machine-checkable if sandbox complete | Declared inputs can be hashed; undeclared side channels remain an environmental assumption. |
| 7 | mixed | Account/ACL separation is checkable; beneficial ownership, collusion and hidden authorship are not. |
| 8 | not adequate as written | Registration is checkable; relevance and detection power are not proved by existence. |
| 9 | overstated | A receipt can bind evidence but cannot transform attestations/competence/non-collusion into machine facts. |

### Required formal repair

Define an explicit predicate `AnswerNeutral(z,f)` for every common `z ∈ N ∪ B`. It must mean that `z` may parse/canonicalize/transport the declared problem but cannot decide admission, transition reduction, dependencies, affected sets, authority/status projection, ambiguity collapse or the expected result for failure family `f`. Conditions 1-3 then permit overlap only where `AnswerNeutral` is established by negative tests and independent review.

## 2. Proposition audit

### Proposition 1

The proposition is valid only in its own narrow domain: for a defect artifact `δ ∈ SemProv_f(I ∪ C) \ (N ∪ B)`, conditions 1-2 exclude that artifact from `R_v` and `P_v` provenance. It does **not** prove that all common B/N logic is neutral. The main architectural conclusion needs the additional answer-neutrality premise above.

### Proposition 2

The self-directed consequence is right, but condition 8 is too weak. “At least one discriminator exists” does not imply that it detects the seeded reducer defect. Adequacy requires:

```text
seeded_fault_witness
+ expected semantic delta
+ named discriminator dependency
+ broken-channel liveness result
+ removal/neutralization probe
```

Without that witness, `ARCHITECTURE_FALSIFIED` is a declared outcome but the acceptance gate can still accept a decorative discriminator.

### Proposition 3

Confirmed. `V = r ∧ p ∧ i ∧ h` prevents either evaluator, the same-code control, or a majority vote from creating passage alone. No independence probability is inferred.

### Proposition 4

Confirmed as a mathematical statement for a finite explicit alternative set and decidable predicate language. Its implementation premise is missing from the schema, which is why `S0-GAP-02-VI-001` blocks executable validation.

## 3. Specification-side seeded-fault case

### Attack `A-14 — shared axiom/expectation defect`

```yaml
setup:
  B: "an expired delegation remains valid for publication"
  O_v: finite alternatives all derived from that premise
  I: implements the same premise
  R_v: independently implements B
  P_v: independently checks predicates derived from B/O_v
observed:
  product_trace: matches O_v
  evaluator_r: accept
  evaluator_p: accept
  provenance_conditions: pass
```

This does not violate implementation-code independence. It demonstrates that the architecture can be non-circular and still semantically wrong because the commissioned premise is wrong. Required outcome:

```yaml
implementation_verification: not_refuted_under_committed_specification
custody_semantics_claim: SPECIFICATION_ASSURANCE_NOT_ESTABLISHED
benchmark_passage: prohibited
challenge_required: true
```

The current package concedes the possibility but supplies no executable falsifier/outcome. It must not call the remaining dependency purely institutional until this case is integrated.

## 4. Additional uncovered attacks

### `A-15 — generator/evaluator common semantic ancestor`

`M_v` and `P_v` are written in different packages but both import a private transformation library that reverses the tenant relation. The generator produces a wrong “semantics-preserving” case and the evaluator confirms its own relation. Current product/R/P separation does not forbid this edge. Expected outcome: `MUTATION_PROVENANCE_VIOLATION`, `RUN_INVALID`.

### `A-16 — competent unanimous misconception`

Every reviewer is competent and conflict-free but shares the same incorrect doctrinal premise; all sign `supports`. Dissent preservation is vacuously satisfied. A blinded proficiency seed should expose the common error. Expected outcome without a passed proficiency anchor: `SPECIFICATION_ASSURANCE_NOT_ESTABLISHED`, not acceptance.

### `A-17 — undeclared private ancestor`

R and P report disjoint source graphs, but generated tables from a private repository were copied before the audit window and omitted from attestations. A-13 fires only if the ancestor is known. Require independent forensic source/build/network comparison and a poisoned-table probe. Expected outcome on unresolved provenance gap: `RUN_INVALID` or `INDEPENDENCE_NOT_ESTABLISHED`.

## 5. Comparative models

All four commissioned models are genuinely compared. The eliminating properties are real:

- reducer alone: correlated specification misconception/monolithic second runtime;
- predicate evaluator alone: incomplete predicates can accept a wrong trace;
- dual evaluators: selected, but disagreement blocks rather than votes;
- same-code rebuild: useful consistency control, categorically not verification.

The last line is preserved in the model table, run sequence, receipt schema, claim template and handoff.

## 6. Falsifier suite audit

All 13 supplied cases state setup, expected observations and forbidden observations. The complete denominator is audited below.

| Case | Executable-spec verdict | Exact audit conclusion |
|---|---|---|
| `F-01` | clear | Prohibited semantic import/call/generation yields independence failure, not passage. |
| `F-02` | clear | Implementation-visible answer fields invalidate the run; this matches the observed `grounding_benchmark.py` anti-pattern. |
| `F-03` | clear | ID renumbering/adjacent semantic invariance is observable; unexplained change blocks. |
| `F-04` | dispositive | Control may pass wrong parity; independent rejection blocks; dual acceptance yields exactly `ARCHITECTURE_FALSIFIED`. |
| `F-05` | clear, conditional | Old receipt/new expectation substitution fails digest binding if retained verification material is available. |
| `F-06` | clear | Dropped conflict, dissent or abstention invalidates record completeness. |
| `A-07` | clear | A helper named neutral is rejected by semantic behavior/provenance, not filename. |
| `A-08` | clear | Leakage through build/output/query channels invalidates the evaluation window. |
| `A-09` | clear | Parser/canonicalization split view is blocked rather than treated as semantic equality. |
| `A-10` | partial | Bad mutation/relation is challenged, but M-to-P/R shared semantic provenance is not forbidden; see A-15. |
| `A-11` | clear | Adaptive hidden-set probing/exposure budget breach invalidates the governed run. |
| `A-12` | clear, institutional | Inconsistent log views are detectable when independent witnesses compare signed heads. |
| `A-13` | partial | Two-language common ancestry is caught when provenance is declared/discovered; omission remains uncovered; see A-17. |

`F-01`-`F-06` cover the commissioned failures; `A-07`-`A-13` add leakage, comparator, generator, adaptive, log and private-ancestor attacks. Coverage is incomplete for A-14-A-17 above. These are not cosmetic variants: they attack shared specification truth, generator provenance, reviewer common-mode failure and provenance omission.

## 7. Sealed expectations and bounded ambiguity

The finite alternative model is strong, but the invalidity list is not executable until the predicate language and trace universe are bounded. A syntactically valid universal bundle can be constructed:

```yaml
alternatives:
  - alternative_id: universal
    mandatory_positive_predicates:
      - "event_count >= 0"
    mandatory_negative_predicates:
      - "event_type == 'x' and event_type != 'x'"
    may_vary: []
```

It has a positive and a negative predicate, no wildcard and no semantic `may_vary`, yet accepts every trace. The prose rule rejects it, but a validator cannot prove that rejection over an unbounded/general predicate language. Require one of:

1. a finite enumerated trace model with exhaustive evaluation;
2. a decidable total predicate DSL with proof-producing tautology/satisfiability checks; or
3. a conservative static analysis whose unknown result blocks under `PV-K06`.

## 8. Oracle custody and adjudication

### Role matrix

The matrix is materially incomplete because scenario author and expectation author may be the same semantic origin. Require independent expectation derivation or dual control, and add incompatibilities between `M_v` author/relation validator and the evaluator that judges the generated relation.

### Access evidence

The text correctly says a missing access event is not proof of no access. The receipt must therefore bind independently reconciled storage, network and key-service audit heads plus a completeness disposition. Any gap affecting secrecy/provenance yields `RUN_INVALID` or `INDEPENDENCE_NOT_ESTABLISHED`.

### Rotation, correction and silent change

Key lifecycle, compromise scope and append-only supersession are coherent. `§10.3` is detectable under retained integrity evidence: substituting `O_v+1` into `Q_old` changes the bound digest and yields `RUN_INVALID` plus `ORACLE_HISTORY_VIOLATION`. This does not claim the old semantic answer was correct.
