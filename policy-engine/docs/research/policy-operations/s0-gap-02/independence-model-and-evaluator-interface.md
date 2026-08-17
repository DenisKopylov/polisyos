---
title: S0-GAP-02 — Formal independence model and evaluator interface
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
  - research definition of implementation independence for the custody benchmark
  - evaluator comparison and selected architecture
  - research-only interface and enforcement requirements
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

# Formal independence model and evaluator interface

## 1. The boundary question answered first

An independent evaluator may share only the **problem boundary and neutral exchange substrate** with the implementation. It may not share the implementation’s answer-producing semantics or anything derived from them.

### 1.1 Legitimately shared only after answer-neutrality is constructed

The following material may be common because it identifies the question or permits representation-level exchange without deciding the answer:

- the ratified observable-semantic requirements and the public benchmark specification;
- input-only fixture bytes and a public fixture manifest;
- opaque identifiers, declared units, syntactic types, version identifiers, and time representations;
- an observable-output transport grammar that contains raw facts/events and no product verdict mapping;
- generic language runtimes, operating systems, cryptographic primitives, JSON/YAML parsers, canonicalization algorithms, and public conformance vectors;
- run environment descriptions, seeds, hashes, signatures, and nonsemantic ordering rules;
- public authority-scenario axioms, including their contestability and provenance, provided those axioms were not generated from implementation behavior.

Membership in that list is not enough. For a common artifact `z` and failure family `f`, define `AnswerNeutral(z,f)` only when all of the following are evidenced:

1. **representation-only function:** `z` parses, validates syntax, canonicalizes, transports, hashes, signs, or identifies declared inputs without selecting an admissible alternative or benchmark verdict;
2. **no semantic decision:** `z` contains no admission, transition-reduction, dependency/affected-set, status/authority projection, ambiguity-collapse, expected-answer, or discriminator-satisfaction logic for `f`;
3. **information preservation:** accepted inputs have a public, deterministic representation relation and every rejected or normalized construct is covered by conformance vectors, so a semantic distinction cannot disappear silently;
4. **transitive provenance closure:** source, generated files, SBOM dependencies, build inputs, runtime module loads, and network services are all within the admitted answer-neutral allowlist;
5. **behavioral falsification:** a poisoned helper carrying each prohibited semantic family is rejected even when its package name, declaration, signatures, and allowlist entry remain unchanged; and
6. **independent review:** a reviewer outside the common artifact's producing function signs the scope-specific answer-neutrality record.

Let `A_f = {z in (N union B) | AnswerNeutral(z,f)}`. Only `A_f`, not all of `N union B`, is permitted common semantic provenance. A helper ceases to be neutral the moment any one of these predicates is false. This construction implements `P37`: the gate may not turn on merely because the producer declared the helper neutral. (`policy-engine/docs/reference/policy-design-case-failure-patterns.md:70-95@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`, findings `P35`-`P37`.)

### 1.2 Never shared for a verification claim

The following may not be imported, linked, copied, generated from, invoked over a network, or reconstructed from implementation-visible outputs by either independent evaluator:

- admission or re-admission logic;
- custody transition reducers or state machines;
- dependency traversal, affected-set, closure, or propagation logic;
- status/posture/authority projection and label mappings;
- implementation test fixtures carrying expected actions, states, labels, mechanisms, or scores;
- expected traces supplied by OPS-R15 in implementation-visible prose;
- product “gold” labels, adjudication code, or semantic fixture helpers;
- generated code, schemas, lookup tables, snapshots, serialized objects, model weights, or caches derived from any prohibited semantic source;
- the product’s same-code incremental/clean-build path as evidence of correctness;
- authoring notes or challenge answers that disclose sealed expectations before an implementation submission is frozen.

This line is the direct consequence of `S0-K14`: a same-code rebuild may prove consistency but not correctness, and no scoring oracle may share admission, reducers, dependency traversal, or status projection. (`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:143-199@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`, finding `S0-K14`.) The existing `grounding_benchmark.py` is an example of what an independent evaluator must not become: it imports product admission/relation/phrasing logic and contains visible expected fields. (`policy-engine/src/polisyos/runtime/quality/grounding_benchmark.py:1-140@1a7a2d05ebba22fae80e9934329e4b880806588e`.)

## 2. Components and notation

Let:

- `I` be the implementation under test at a frozen revision;
- `C` be the product's same-code incremental/clean-rebuild consistency control;
- `B` be the public benchmark specification: input grammar, observable trace grammar, scenario axioms, declared semantic equivalences, and the finite trace-domain profile;
- `O_v` be sealed expectation bundle version `v`;
- `R_v` be a separately authored declarative reference reducer version `v`;
- `P_v` be a property, predicate, and metamorphic evaluator version `v`;
- `M_v` be the hidden adjacent-case and mutation generator version `v`;
- `J_v` be the separately authored mutation-certificate/relation validator version `v`;
- `S_v` be the specification-assurance record set for `B` and `O_v`, including dual-control derivation, reviewer proficiency, dissent, challenges, and scope-specific institutional acceptance or non-establishment;
- `H_v` be the human challenge/adjudication record set version `v`;
- `L` be the append-only commitment, access, run, challenge, correction, and supersession log;
- `N` be the candidate neutral substrate described in §1.1; and
- `A_f` be the subset of `N union B` for which `AnswerNeutral(z,f)` is actually constructed.

For a component `X` and failure mode `f`, let `SemProv_f(X)` be the transitive **answer-producing semantic provenance** that can influence `X`'s determination for `f`: source files, generated code/tables/models, semantic services, dependencies, authorship and review inputs used to derive logic, build inputs, and runtime calls. Let `Input_f(X)` be the complete set of declared immutable run data supplied to `X`. Undeclared data access is treated as a `SemProv_f` violation rather than silently excluded.

For every load-bearing gate predicate `g`, let `PredClass(g)` be exactly one of the **five registered
`P37` classes**:

```text
recomputed
independently_reconciled
consumer_asserted
institutionally_supplied
not_established
```

The class is frozen at admission. `consumer_asserted`, `institutionally_supplied`, and
`not_established` may preserve a premise or support a bounded limitation, but they cannot be rendered
as machine proof or, by themselves, turn a positive verification gate green.

**Corrected under ratified `W4-K02`**
(`docs/system-design-decisions/wave4-decision-evidence-ratification.md`). This package originally
defined a six-way vocabulary adding `machine_observed`, `attested` and `institutionally_accepted`.
The independent conformance verification established that the refinement does **not** widen the
non-positive set and commended the three distinctions as genuine — and they are retained here, as
**required sub-annotations recorded beside the registered class**, never as labels:

| Sub-annotation | Registered class | What the sub-annotation adds |
| --- | --- | --- |
| `machine_observed` | `recomputed` when deterministically re-derived from controlled artifacts; `independently_reconciled` when the observation is retained by a **second non-producing observer** | bounded direct machine observation as distinct from deterministic recomputation, always carrying an explicit observed-envelope limitation. **Bare producer-retained telemetry is `not_established`**, never eligible. |
| `attested` | `consumer_asserted` | a signed declaration by any constrained role, not only the consumer — authorship, conflict, competence statements. Non-positive. |
| `institutionally_accepted` | `institutionally_supplied` | the supplied premise has additionally been accepted for a **named scope** after proficiency, dissent and challenge review. Still non-machine evidence; non-positive. |

The reason the refinement is not adoptable as labels is lookup shape, not substance:
`machine_observed` is positive-eligible only *conditionally*, and a gate must answer
positive-eligibility by fixed lookup rather than by evaluating a declared condition — which would
reproduce `P37` one level below itself (ratified `W4-K03`). A sub-annotation qualifies the evidence
and **never alters positive-eligibility**.

The shared-input/shared-provenance split remains essential. `R_v` and `P_v` may consume the same committed fixture, raw trace, and scoped expectation version because they must judge the same run. Those declared bytes are common **inputs**, not common answer-producing code. Mutual evaluator independence concerns `SemProv_f`; correctness of shared `B` or `O_v` is governed separately by `S_v`, and failure to establish it withholds the stronger custody-semantics claim.

## 3. Independence is conditional structural independence, not a role label

### 3.1 Formal condition

For implementation-origin failure modes `f` in

```text
F_impl = {
  admission,
  transition_reduction,
  dependency_traversal,
  affected_set,
  status_projection,
  authority_projection,
  ambiguity_collapse,
  identifier_branching,
  temporal_ordering
}
```

the architecture claims **constructed implementation independence** only when all of the following hold:

1. `SemProv_f(I union C) intersect SemProv_f(R_v) subseteq A_f`;
2. `SemProv_f(I union C) intersect SemProv_f(P_v) subseteq A_f`;
3. `SemProv_f(R_v) intersect SemProv_f(P_v) subseteq A_f`;
4. for every mutation family `m`, the transformation semantics in `M_v`, the relation-validation semantics in `J_v`, and the deciding relation semantics in `R_v`/`P_v` have no private common ancestor outside the public relation definition and answer-neutral substrate; generated tables, prompts, models, and services are included in this test;
5. no element of `B`, `N`, `A_f`, or the public relation catalogue used to derive evaluator or generator logic is generated from, fitted to, or selected by observing `I`, `C`, implementation-visible expectations, prior hidden-run results, or product-authored private semantic notes;
6. `Input_f(I union C)` is limited to the public specification, public fixture bytes, frozen product configuration/state, and declared answer-neutral data; it excludes plaintext `O_v`, hidden seeds/variants before authorized reveal, evaluator internals, and adjudication answers;
7. every common evaluator run input is enumerated and committed: `Input_f(R_v) intersect Input_f(P_v)` may contain only `B`, the committed fixture population, immutable raw trace, scoped `O_v`, and admitted answer-neutral conformance data;
8. operational identities able to write `I` or `C` cannot write `R_v`, `P_v`, `M_v`, `J_v`, `O_v`, or their build attestations for the same evaluation window; scenario-to-expectation derivation uses independent derivation or dual control; pre-freeze plaintext `O_v` access is incompatible with implementation authorship or submission authority;
9. every claimed failure family has a precommitted `DiscriminatorWitness` binding the seed/mutation digest, expected semantic delta, named `R_v`/`P_v` discriminator, baseline and mutated results, liveness probe, removal probe, and neutralization probe; a missing, removed, or neutralized discriminator yields `EVALUATOR_COVERAGE_NOT_ESTABLISHED`, never acceptance;
10. every load-bearing gate predicate appears in the frozen predicate-provenance register in §3.1.1, with its exact `PredClass`, evidence digest, scope, and claim effect;
11. `S_v` records whether specification assurance for `B` and `O_v` is independently reconciled, institutionally accepted within a named scope, or not established; a shared bad premise that both evaluators implement correctly cannot satisfy the stronger custody-semantics claim; and
12. the run receipt carries the evidence and classifications for conditions 1-11, including transitive provenance, declared inputs, answer-neutrality probes, discriminator witnesses, role assignment, access reconciliation, reviewer proficiency, and unresolved blocking challenges.

The conditions permit only `A_f` as common answer-producing provenance. Shared committed `O_v` and trace bytes remain declared inputs rather than semantic-code ancestry. This does not claim that `B` or `O_v` is infallible. A shared defect in those artifacts is a **specification/oracle failure**, and `A-14` requires the exact negative completion `SPECIFICATION_ASSURANCE_NOT_ESTABLISHED` with the final bounded passage claim withheld.

#### 3.1.1 Frozen predicate-provenance register (`P37`)

The table below is part of the architecture, not optional commentary. Each row has exactly one provenance class at admission.

| Load-bearing predicate | Class frozen at admission | Evidence that settles the predicate | Positive-gate effect |
|---|---|---|---|
| artifact digest equals committed bytes | `recomputed` | canonical bytes and digest recomputation | eligible |
| expectation and public-spec commitments bind the exact admitted versions | `recomputed` | canonicalization, inclusion proof, and commitment recomputation | eligible |
| finite trace-domain members and bounds are fully enumerated | `recomputed` | complete domain walk and domain-profile digest | eligible |
| the predicate AST uses only total admitted `S0-GAP-02-PDL-1` operators | `recomputed` | normalized AST validation against the closed operator registry | eligible |
| each alternative is satisfiable and the union of alternatives is not catch-all | `recomputed` | proof-producing SAT/UNSAT/TAUT/NOT_TAUT certificates | eligible; indeterminate blocks |
| trace canonicalization preserves duplicates, order, time, scope, and semantic atoms | `recomputed` | round-trip and adversarial conformance vectors | eligible |
| raw trace bytes equal the implementation output frozen for the run | `independently_reconciled` | product output digest compared with evaluator intake and immutable run manifest | eligible |
| static source/import/generated-file/SBOM closure contains no prohibited ancestor | `recomputed` | full transitive graph and allow/deny evaluation | eligible |
| runtime modules and network destinations match the declared execution envelope | `independently_reconciled` · sub-annotation `machine_observed` | independently retained load/network telemetry | eligible within the observed envelope, **because the telemetry is retained by a second non-producing observer**; producer-retained telemetry is `not_established` |
| storage, network, and key-service records agree with the oracle access log | `independently_reconciled` | signed heads plus reconciliation witness | eligible |
| a common helper satisfies representation-only conformance vectors | `recomputed` | conformance and poisoned-helper results for every `F_impl` family | eligible |
| a common helper performed no undeclared runtime semantic call | `independently_reconciled` · sub-annotation `machine_observed` **only when the trace is independently retained**, otherwise `not_established` | runtime trace and network evidence | eligible within the observed envelope **only** under independent retention; a producer-retained trace cannot make this predicate positive |
| answer-neutrality scope was independently reviewed | `independently_reconciled` | signed review that independently repeats source and behavioral checks | eligible |
| implementation/submission freeze preceded hidden mutation generation | `independently_reconciled` | signed chronology from independent commitment and run logs | eligible |
| hidden seed, exposure budget, and diagnostic-query budget remained within the committed window | `independently_reconciled` | seed commitment, access evidence, query ledger, and reconciliation result | eligible |
| role assignment satisfies the incompatibility matrix for the evaluation window | `recomputed` | role-window validator over identity and authority records | eligible subject to truthful input limitations |
| authorship and role declarations are truthful | `consumer_asserted` · sub-annotation `attested` | signed declarations and conflict records | cannot independently turn gate green |
| declared evaluator competence exists for the named scope | `institutionally_supplied` · sub-annotation `institutionally_accepted` | mandate and proficiency acceptance record | claim remains institutionally bounded; absence degrades/blocks |
| non-collusion is true | `not_established` | no complete technical proof exists | no positive independence claim may rely on it as machine fact |
| each discriminator detects its bound semantic delta | `recomputed` | liveness, removal, and neutralization witnesses | eligible |
| mutation relation is independently validated without shared private semantics | `independently_reconciled` | `M_v`/`J_v`/`R_v`/`P_v` provenance and relation witnesses | eligible |
| reviewer records preserve every assigned position, abstention, recusal, dissent, and correction | `recomputed` | assignment roster, signed position set, completeness walk, and append-only history | eligible |
| reviewer proficiency anchors were passed for the claimed domain | `independently_reconciled` | blinded seed results and drift record | eligible |
| the `B` to `O_v` derivation used independent derivation or dual control | `independently_reconciled` | derivation record, role-window validation, and independent source comparison | eligible |
| scope-specific competent acceptance of the public axiom/expectation premise exists | `institutionally_supplied` · sub-annotation `institutionally_accepted` | `S_v`, dissent, challenges, mandate evidence, and the named scope acceptance record | never rendered as machine proof; missing acceptance yields `SPECIFICATION_ASSURANCE_NOT_ESTABLISHED` |
| no undiscovered substantive error remains in the shared specification | `not_established` | no finite technical or institutional procedure proves universal absence | cannot support a universal-correctness claim; bounded claim only |
| fixture population and denominators equal the committed plan | `recomputed` | population digest and complete member walk | eligible |
| correction and supersession history is append-only and the receipt remains bound to the historical bundle | `recomputed` | consistency proofs, prior receipt digest, and supersession links | eligible |
| no unresolved blocking challenge exists | `recomputed` | challenge register over the bound receipt and artifacts | eligible only when true |

**Falsify-the-declaration probe.** Keep an allowlist entry and signed declaration saying `neutral_normalizer` is answer-neutral, then replace its implementation with a status projection, dependency closure, or ambiguity-collapse function. The poisoned behavioral vector must change while the declaration remains unchanged. The required result is `AnswerNeutral=false`, provenance/integrity failure, and `RUN_INVALID`. If the gate remains green, it is testing the declaration and the architecture is falsified under `P37`.

### 3.2 Failure modes the construction addresses

| Failure family | Construction | Claim strength |
|---|---|---|
| Product shares faulty admission/reducer/traversal/projection with the oracle | `A_f`-bounded provenance, denylisted imports, isolated builds, two diverse evaluators | Structural circularity is prevented only for admitted answer-neutral overlap. |
| A helper is merely declared neutral | `AnswerNeutral`, poisoned helper probes for every semantic family, independent review, P37 register | Declaration alone cannot turn the gate green. |
| One independent evaluator has an implementation defect | Dual diverse evaluator channels and mandatory disagreement blocking | A single evaluator cannot create passage. |
| Same-code clean build repeats a wrong answer | `C` is excluded from every verification conjunction and claim | Consistency may be recorded; correctness is not inferred. |
| Discriminator is decorative | Expected-delta binding plus liveness/removal/neutralization probes | Missing or ineffective coverage fails closed as `EVALUATOR_COVERAGE_NOT_ESTABLISHED`. |
| Fixture memorization or ID branching | Hidden mutations, adjacent cases, semantic-equivalence relations, implementation freeze before seed generation | Bounded resistance, not proof against all adaptive behavior. |
| Generator/evaluator share a private relation ancestor | `M_v`/`J_v`/`R_v`/`P_v` provenance separation and `A-15` | Shared relation semantics invalidate the run before product scoring. |
| Expected-answer leakage | Input-only public corpus, sealed `O_v`, incompatible roles, independently reconciled access evidence | Leakage becomes detectable and challengeable if the evidence chain holds. |
| Dissent/abstention erased | Signed append-only reviewer records and challenge gate | Erasure invalidates the run rather than resolving disagreement. |
| Reviewers are uniformly mistaken | Blinded proficiency anchors, drift checks, specification-assurance gate, `A-16` | Unanimity is insufficient; the stronger claim is withheld. |
| Shared public axiom or expectation is wrong | `S_v`, dual-control derivation, challenges, `A-14` | Implementation may be “not refuted under the committed specification”; acceptable custody semantics are not established. |
| Oracle correction rewrites history | Content commitments and immutable version binding | Prior receipt remains bound to prior expectation hash. |

### 3.3 Failure modes not eliminated by code diversity

| Failure family | Why independence alone is insufficient | Required response |
|---|---|---|
| Defect in shared public scenario axioms `B` or sealed bundle `O_v` | Both evaluators may correctly implement the same bad premise. | `A-14`; preserve provenance/dissent/challenge; emit `SPECIFICATION_ASSURANCE_NOT_ESTABLISHED`; withhold the stronger claim. |
| Correlated interpretation by nominally separate teams | Common training, organizational pressure, copied notes, or a common misconception can correlate failures. | Authorship provenance, independent derivation, proficiency anchors, drift checks, and seeded probes. |
| Collusion | Account separation does not prove non-collusion. | Record `not_established`; institutional controls, auditability, sanctions, rotation, and independent challenge. No cryptographic proof is claimed. |
| Undeclared private semantic ancestor | Attestations can omit copied tables, prompts, or services. | `A-17`; forensic source/build/network evidence and poisoned generated-table probe. |
| Cryptographic compromise | Commitments and logs depend on keys and algorithms. | Versioned algorithms, key lifecycle, rotation, compromise response, and supersession. |

The architecture therefore supports two distinct statements:

1. **Implementation statement:** when the technical gates hold, the named implementation was **not refuted under the committed specification** for the named artifacts and population.
2. **Custody-semantics statement:** “acceptable custody semantics established” additionally requires `S_v` for the named scope, including independently reconciled proficiency/derivation evidence, preserved dissent/challenges, and scope-specific institutional acceptance. It is withheld whenever that assurance is not established.

`SPECIFICATION_ASSURANCE_NOT_ESTABLISHED`, `INDEPENDENCE_NOT_ESTABLISHED`, and `EVALUATOR_COVERAGE_NOT_ESTABLISHED` are local negative-completion/evidence dispositions. They do not create a fourth constitutional outcome-vocabulary element. `INT-K08` already establishes that a negative completion is a valid governed result; it does not turn non-establishment into permission to weaken the gate. (`policy-engine/docs/system-design-decisions/int-wave-claim-semantics-ratification.md:190-235@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`, finding `INT-K08`.)

## 4. Required comparative models

| Model | Honest value | Eliminating property / disposition |
|---|---|---|
| 1. Separately implemented declarative reducer | Can produce reference observable traces from the public axioms and expose transition disagreements. Different representation and authoring can break direct code inheritance. | **Not sufficient alone.** A complete reducer may reproduce a specification misconception, overfit trace details, or become a second monolithic runtime. Retained as evaluator `R_v`, not selected as the sole oracle. |
| 2. Predicate evaluator without a full runtime | Checks invariants, forbidden states, conservation/monotonicity relations, authority limits, and metamorphic relations without replaying every internal transition. | **Not sufficient alone.** An incomplete predicate set can accept a wrong trace that happens to satisfy all tested properties. Retained as evaluator `P_v`, not selected as the sole oracle. |
| 3. Dual independent evaluators with disagreement adjudication | Makes divergent reasoning observable and prevents one evaluator from silently defining truth. It permits architectural diversity: `R_v` is constructive, `P_v` is relational. | **Selected.** Passage requires both channels, sealed expectation compatibility, and no unresolved integrity/adjudication defect. Disagreement is preserved and blocks the bounded verification claim. |
| 4. Same-code rebuild retained only as a diagnostic control | Detects nondeterminism, stale caches, incremental/clean-build divergence, and replay inconsistency. | **Rejected as a verifier by `S0-K14`.** It remains `C`, a diagnostic control whose agreement can never satisfy an independent verification predicate. (`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:143-154@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`, finding `S0-K14`.) |

The selected architecture is therefore model 3 composed of model 1 and model 2, with model 4 explicitly outside the verification conjunction.

## 5. Evaluator architecture

```text
                         public, input-only
        B + finite trace domain + corpus manifest + fixture bytes
                                  |
                    +-------------+-------------+
                    |                           |
           frozen implementation I       hidden generator M_v
                    |                           |
             raw observable trace       mutated input population
                    |                           |
                    |                  relation validator J_v
                    +-------------+-------------+
                                  |
                     answer-neutral trace exchange
                                  |
                    +-------------+-------------+
                    |                           |
          declarative reducer R_v      predicate evaluator P_v
                    |                           |
                    +-------------+-------------+
                                  |
          decidable sealed compatibility O_v + specification record S_v
                                  |
               disagreement / challenge protocol H_v
                                  |
                  immutable bounded receipt in L

    same-code control C ----------------> diagnostic appendix only
```

No arrow from `I` or `C` enters `R_v`, `P_v`, `M_v`, `J_v`, or `O_v`. `M_v` and `J_v` do not share private transformation semantics, and neither may share a private semantic ancestor with the evaluator that judges the relation. No evaluator writes a product status, authority state, or canonical confidence record. The specification-assurance gate is separate from implementation-code independence: agreement under a bad `B` or `O_v` is not passage.

## 6. Research-only evaluator interface

This is an interface requirement, not a final API or serialization contract.

### 6.1 Inputs common to both independent evaluators

```yaml
EvaluationInput:
  benchmark_spec:
    version: string
    digest: digest
  fixture_population:
    public_manifest_digest: digest
    sealed_population_commitment: digest
    population_id: opaque_string
  implementation:
    revision: string
    artifact_digest: digest
    sbom_digest: digest
  environment:
    image_digest: digest
    runtime_versions: map<string, string>
    configuration_digest: digest
  observation:
    raw_trace_digest: digest
    raw_trace_location: opaque_handle
  evaluator:
    source_revision: string
    artifact_digest: digest
    sbom_digest: digest
    provenance_attestation_digest: digest
  oracle_handle:
    expectation_version: string
    commitment_digest: digest
    plaintext_access: evaluator_scoped_handle
  run_nonce: bytes
```

The raw trace grammar may carry observable facts such as received events, attempted actions, persisted receipts, dependency edges actually traversed, and emitted public artifacts. It may not carry a product-provided field whose value is already “acceptable,” “blocked,” “correct,” or another expected benchmark answer.

### 6.2 Evaluator-local output

```yaml
EvaluatorObservation:
  run_id: opaque_string
  evaluator_kind: declarative_reducer | predicate_metamorphic
  evaluator_version: string
  fixture_id: opaque_string
  observed_claims:
    - claim_id: opaque_string
      value: typed_value
      evidence_digest: digest
  predicate_results:
    - predicate_id: stable_identifier
      result: satisfied | violated | indeterminate
      witness_digest: digest | null
  expectation_compatibility:
    alternative_ids_matched: [opaque_string]
    exclusions_triggered: [stable_identifier]
  integrity_findings: [stable_identifier]
  abstention_record: opaque_handle | null
  signed_digest: digest
```

The terms `satisfied`, `violated`, and `indeterminate` are evaluator-local observations. They are not a new product status lattice and carry no authority.

### 6.3 Combined decision and claim-level rule

For fixture `x`, output trace `y`, expectation bundle `O_v`, and evaluator versions `R_v`, `P_v`, define:

- `r(x,y)=1` only if `R_v` finds `y` compatible with at least one explicit admissible alternative and no exclusion;
- `p(x,y)=1` only if all mandatory predicates/metamorphic relations are satisfied and none is indeterminate;
- `a=1` only if every common artifact used for the named failure families satisfies `AnswerNeutral` with the required recomputed, observed, reconciled, and review evidence;
- `d=1` only if every claimed failure family has a live `DiscriminatorWitness` and its removal/neutralization probes fail closed;
- `i=1` only if all provenance, commitment, access-reconciliation, role-assignment, population, and run-integrity checks hold;
- `h=1` only if no required conflict, dissent, abstention, challenge, or evaluator disagreement has been discarded or prematurely resolved **and** `no_unresolved_blocking_challenge=true`;
- `s=1` only if `S_v` establishes the scope-specific specification-assurance premises; `s=0` or `not_established` withholds the stronger claim;
- `c` is the result of the same-code control and is deliberately absent below.

The implementation-side conjunction is:

```text
W(x,y; v) = r(x,y) and p(x,y) and a and d and i and h
```

If `W=1` while `s` is not established, the only permitted positive evidence statement is:

> The named implementation was not refuted under the committed specification for the named artifacts, population, environment, evaluator releases, and tested predicates.

The stronger custody-semantics conjunction is:

```text
V_custody(x,y; v) = W(x,y; v) and s
```

If a valid `A-14` shared-specification seed is accepted by both evaluators, `s` is not established, the final bounded passage sentence is withheld, and the exact local negative completion is `SPECIFICATION_ASSURANCE_NOT_ESTABLISHED`. This is an `INT-K08` terminal, not a new product or constitutional outcome type.

A population-level claim additionally requires every mandatory fixture and mutation relation in the committed population to satisfy the relevant conjunction under the predeclared aggregation rule. No majority vote may convert a failed or indeterminate mandatory predicate into passage. `PV-K06` applies: an unproved approximation, unsupported theory, timeout, or unknown compiler result cannot inherit acceptance. (`policy-engine/docs/system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md:164-182@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`, finding `PV-K06`.)

## 7. Enforceable controls

### 7.1 Source, dependency, and answer-neutrality controls

1. Independent evaluators reside in independently controlled source roots and build identities. A directory name inside the product repository is not sufficient separation.
2. Evaluator, generator, and relation-validator builds receive no product source checkout and have network egress disabled except to an allowlisted answer-neutral artifact mirror.
3. The allowlist is machine-enforced and version-bound. It contains only admitted `A_f` artifacts, public inputs, generic runtimes, canonicalization, cryptography, and approved conformance data.
4. The denylist covers product package names and content-derived signatures for admission, reducers, traversal, projection, gold labels, fixture helpers, mutation transformations, and relation tables.
5. Static import analysis, dynamic module-load tracing, SBOM comparison, source-origin scanning, generated-file provenance, and runtime network-call capture are all required. Passing one check does not waive the others.
6. Every common artifact is tested with poisoned variants for **each** semantic family in `F_impl`: admission, transition reduction, dependency traversal, affected-set calculation, status projection, authority projection, ambiguity collapse, identifier branching, and temporal ordering.
7. A poisoned variant keeps the declaration, package identity, allowlist entry, and signatures unchanged while adding one prohibited semantic behavior. Any green answer-neutrality gate is `ARCHITECTURE_FALSIFIED` under the falsify-the-declaration probe.
8. The independent answer-neutrality review record binds source, SBOM, runtime telemetry, conformance probes, reviewer identity/conflict declaration, scope, and expiration.
9. Any common dependency that performs semantic normalization is reclassified as prohibited and causes the affected build/run to be rejected.

The repository's production import policy does not construct an independent evaluator root. (`policy-engine/architecture/imports/policy.toml:1-132@1a7a2d05ebba22fae80e9934329e4b880806588e`.) S0-GAP-02 therefore requires a separate enforcement plane rather than another allowed `runtime` import.

### 7.2 Authorship, derivation, and clean-room controls

- Evaluator authors receive `B`, input-only fixtures, and independently prepared conformance vectors, not product source or visible expected traces.
- The derivation record states how each transition or predicate follows from a public axiom, with no “matched current output” rationale.
- `B` to `O_v` derivation requires an expectation author independent of the scenario author or a documented dual-control derivation with separate approval; one semantic origin may not unilaterally author both sides.
- `R_v` and `P_v` have separate primary authors and separate reviewers for the same release window.
- `M_v` transformation authors, `J_v` relation validators, and the evaluator that judges the relation have explicit incompatibility rules; no shared private table, prompt, model, or service is permitted.
- Product authors may answer public-spec clarification questions only through an append-only, equally visible clarification channel; private hints invalidate the affected release.
- A person with plaintext expectation access may not prepare or approve the frozen implementation submission for that window.
- Authorship and conflict declarations remain `attested`; they are independently reconciled against repository, build, document, and access evidence and are never labeled machine-proved.
- These are abstract role incompatibilities. This research appoints no team or individual.

### 7.3 Build and execution controls

- Reproducible build recipes, compiler/interpreter versions, dependencies, SBOMs, and artifact digests are committed before a scored run.
- Clean builds occur in independent base images. Diversity of language/runtime is preferred where it changes failure provenance; cosmetic diversity is not credited.
- The implementation, each evaluator, generator, and expectation bundle are separately content-addressed.
- Evaluators consume immutable traces. They cannot query product internals or request adaptive reruns after seeing expectation details.
- Hidden cases are selected or generated after the implementation revision and submission digest are frozen.

### 7.4 Institutional, proficiency, and challenge controls

- Conflict declarations, abstentions, access grants/revocations, key operations, challenges, and corrections are signed log entries.
- Role rotation must preserve continuity and must not permit a product author to become expectation custodian for the same evaluation window.
- Competence is `institutionally_accepted`, not machine-proved, and must be evidenced against a declared scope.
- Before an evaluator or reviewer release is admitted, blinded proficiency exercises use seeded product faults **and** seeded specification-premise faults; raw results and missed seeds are retained.
- Drift checks recur under a predeclared schedule. Unanimity without a passed scope-relevant proficiency record cannot satisfy `S_v`.
- Blocking challenge classes are fixed before the run. `h=1` requires `no_unresolved_blocking_challenge=true`; an open challenge to provenance, access, specification, expectation, population, evaluator, or history withholds the claim.
- Non-collusion remains `not_established`; organizational separation is evidence of control design, not proof of the premise.

## 8. Proof obligations

### Proposition 1 — same-code circularity is excluded only outside admitted common artifacts

Assume conditions 1-12 in §3.1 hold. Let `delta` be a defect whose causal artifact lies in `SemProv_f(I union C) minus A_f`. By conditions 1 and 2, that artifact is not in `SemProv_f(R_v)` or `SemProv_f(P_v)`. Therefore neither independent evaluator can reproduce `delta` **by executing, importing, linking, generating from, or calling that defective product artifact**. For an artifact inside `A_f`, the proposition depends on the separately constructed `AnswerNeutral` proof; it does not follow merely from membership in `N` or `B`. Coincidentally matching errors and shared-specification defects remain possible. The proved claim is structural non-circularity with product answer-producing provenance for the named failure families, not semantic truth in general.

### Proposition 2 — the seeded shared-reducer fault is discriminating only with an adequate witness

Let `delta*` be a seeded reducer mutation used by incremental execution and `C`. A valid `DiscriminatorWitness` binds the fault patch, expected semantic delta, named discriminator, baseline and mutated observations, and three probes:

1. **liveness:** the intact discriminator detects the seeded delta;
2. **removal:** a release missing the discriminator is rejected before evaluator acceptance as `EVALUATOR_COVERAGE_NOT_ESTABLISHED`; and
3. **neutralization:** replacing the discriminator with a tautology or constant-success result makes the adequacy gate red.

When the witness is valid, at least one of `r` or `p` is `0`, and `C` remains absent from `W` and `V_custody`. If both independent channels accept the wrong value under an intact valid setup, the exact result remains **`ARCHITECTURE_FALSIFIED`**. If the discriminator is absent or ineffective, the result is not passage; it is coverage non-establishment.

### Proposition 3 — dual-channel disagreement cannot be laundered by voting

`W` and `V_custody` are conjunctions, not majority votes. If `R_v` and `P_v` disagree, either `r=0`, `p=0`, or `h=0` until the signed record determines whether the fixture, axiom, expectation, implementation, or evaluator needs supersession. One channel cannot outvote the other. Knight-Leveson is used only to reject an independence-by-voting inference; no numerical reliability gain is claimed.

### Proposition 4 — ambiguity remains falsifiable within the admitted decidable domain

For each fixture `x`, `O_v` contains a finite, nonempty family of explicit alternatives, mandatory predicates, exclusions, and enumerated nonsemantic variability. The predicate DSL and trace-domain profile in `public-schema-and-sealed-expectations.md` are finite and total. The bundle compiler proves each alternative satisfiable, each positive discriminator non-tautological, each negative boundary satisfiable, and the union of alternatives non-universal. An unsupported construct, timeout, or unknown proof result blocks admission under `PV-K06`. Thus multiple outcomes may be preserved without admitting every trace.

### Proposition 5 — implementation independence does not establish specification correctness

Construct `A-14` with a false shared axiom in `B`, an `O_v` derived from it, and independently authored `R_v` and `P_v` that both agree with the false premise. Conditions 1-10 may hold and `W` may be `1`. Because the seeded premise fails `S_v`, `V_custody=0`; the passage sentence is withheld and `SPECIFICATION_ASSURANCE_NOT_ESTABLISHED` is recorded. Therefore the architecture no longer infers acceptable custody semantics from implementation-code independence alone.

## 9. The P27/P28 tension resolved

`P27` and `P28` normally require extension of the canonical owner rather than shadow architecture. (`policy-engine/docs/reference/policy-design-case-failure-patterns.md:71-72@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`, findings `P27`, `P28`.) `S0-K14` is an express verification exception: the evaluator’s semantic implementation must not share the canonical product owner’s answer-producing code. The resolution is split ownership by function, not duplication by accident:

- product owners continue to own production semantics and raw observable outputs;
- a product-side trace adapter may expose observations but may not decide benchmark acceptability;
- `C` may extend existing runtime-quality machinery as a consistency diagnostic;
- `R_v`, `P_v`, `M_v`, and `O_v` must be independent by construction for verification;
- their receipts do not become a second product confidence or authority ledger, preserving `INT-K05`.

## 10. Bounded conclusion

The amended model specifies structural non-circularity for named implementation-origin failure modes only when answer-neutral common artifacts, adequate discriminators, transitive provenance, access reconciliation, and challenge gates are actually evidenced. It separately gates specification-side assurance: agreement under a committed but wrong `B` or `O_v` supports at most “not refuted under the committed specification,” never the stronger custody-semantics claim.

The research standing remains `accepted_narrow_scope`. The audit's four technical defects are now answered at the architecture/specification level by `AnswerNeutral`, the finite decidable predicate domain, adequate discriminator witnesses, and `A-14`; however, no operational gate, evaluator release, proficiency record, independent access reconciliation, or specification-assurance institution is established by this Markdown amendment. The second competent independent function also remains absent. No scoring permission, capability claim, or `OPS-R15` unblock follows.
