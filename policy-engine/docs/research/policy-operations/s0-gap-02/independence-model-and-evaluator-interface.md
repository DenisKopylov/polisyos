---
title: S0-GAP-02 — Formal independence model and evaluator interface
status: research
research_only: true
repository_pin: 1a7a2d05ebba22fae80e9934329e4b880806588e
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

### 1.1 Legitimately shared

The following may be common because they identify the question or permit byte-level exchange without deciding the answer:

- the ratified observable-semantic requirements and the public benchmark specification;
- input-only fixture bytes and a public fixture manifest;
- opaque identifiers, declared units, syntactic types, version identifiers, and time representations;
- an observable-output transport grammar that contains raw facts/events and no product verdict mapping;
- generic language runtimes, operating systems, cryptographic primitives, JSON/YAML parsers, canonicalization algorithms, and public conformance vectors;
- run environment descriptions, seeds, hashes, signatures, and nonsemantic ordering rules;
- public authority-scenario axioms, including their contestability and provenance, provided those axioms were not generated from implementation behavior.

Even this sharing is conditional. A “neutral” helper ceases to be neutral if it normalizes admission, traverses dependencies, maps product statuses, or folds ambiguity. Such a helper moves to the prohibited set regardless of package name.

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

This line is the direct consequence of `S0-K14`: a same-code rebuild may prove consistency but not correctness, and no scoring oracle may share admission, reducers, dependency traversal, or status projection. (`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:143-199@1a7a2d05ebba22fae80e9934329e4b880806588e`, finding `S0-K14`.) The existing `grounding_benchmark.py` is an example of what an independent evaluator must not become: it imports product admission/relation/phrasing logic and contains visible expected fields. (`policy-engine/src/polisyos/runtime/quality/grounding_benchmark.py:1-140@1a7a2d05ebba22fae80e9934329e4b880806588e`.)

## 2. Components and notation

Let:

- `I` be the implementation under test at a frozen revision;
- `C` be the product’s same-code incremental/clean-rebuild consistency control;
- `B` be the public benchmark specification: input grammar, observable trace grammar, scenario axioms, and declared semantic equivalences;
- `O_v` be sealed expectation bundle version `v`;
- `R_v` be a separately authored declarative reference reducer version `v`;
- `P_v` be a property, predicate, and metamorphic evaluator version `v`;
- `M_v` be the hidden adjacent-case and mutation generator version `v`;
- `H_v` be the human challenge/adjudication record set version `v`;
- `L` be the append-only commitment, access, run, challenge, correction, and supersession log;
- `N` be the allowed neutral substrate described in §1.1.

For a component `X` and failure mode `f`, let `SemProv_f(X)` be the transitive **answer-producing semantic provenance** that can influence `X`’s determination for `f`: source files, generated code/tables/models, semantic services, dependencies, authorship and review inputs used to derive logic, build inputs, and runtime calls. Let `Input_f(X)` be the complete set of declared immutable run data supplied to `X`. Undeclared data access is treated as a `SemProv_f` violation rather than silently excluded.

The split matters. `R_v` and `P_v` may both consume the same committed fixture, raw trace, and scoped expectation version because they must judge the same run. Those declared bytes are common **inputs**, not common answer-producing code. Mutual evaluator independence concerns `SemProv_f`; the correctness of shared `B` or `O_v` remains a separate specification/oracle assumption governed by dissent, challenge, and supersession.

## 3. Independence is conditional structural independence, not a role label

### 3.1 Formal condition

For implementation-origin failure modes `f` in

```
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

1. `SemProv_f(I ∪ C) ∩ SemProv_f(R_v) ⊆ N ∪ B`;
2. `SemProv_f(I ∪ C) ∩ SemProv_f(P_v) ⊆ N ∪ B`;
3. `SemProv_f(R_v) ∩ SemProv_f(P_v) ⊆ N ∪ B`;
4. no element of `B` or `N` used to derive evaluator logic is generated from, fitted to, or selected by observing `I`, `C`, implementation-visible expectations, or prior hidden-run results;
5. `Input_f(I ∪ C)` is limited to the public specification, public fixture bytes, frozen product configuration/state, and declared neutral data; it excludes plaintext `O_v`, hidden seeds/variants before authorized reveal, evaluator internals, and adjudication answers;
6. every common evaluator run input is enumerated and committed: `Input_f(R_v) ∩ Input_f(P_v)` may contain only `B`, the committed fixture population, immutable raw trace, scoped `O_v`, and neutral conformance data;
7. the operational identities able to write `I` or `C` cannot write `R_v`, `P_v`, `M_v`, `O_v`, or their build attestations for the same evaluation window, and pre-freeze plaintext `O_v` access is incompatible with implementation authorship or submission authority for that window;
8. for every failure family included in a verification claim, a precommitted discriminator register names at least one independently derived `R_v` result or `P_v` predicate/metamorphic relation and a blind or seeded challenge that the accepted evaluator release must detect; unregistered failure families are outside the claim;
9. the run receipt carries machine-checkable evidence for conditions 1–8, including the complete declared-input sets and discriminator results.

The intersections permit `B` because independent implementations must answer the same public problem. Shared committed `O_v` and trace bytes appear only in the declared-input relation, not in semantic-code provenance. This is not a claim that either `B` or `O_v` is infallible. A shared defect in the commissioned axioms or expectation bundle is a **specification/oracle failure**, not an implementation-circularity failure, and must remain challengeable.

### 3.2 Failure modes the construction addresses

| Failure family | Construction | Claim strength |
|---|---|---|
| Product shares its faulty admission/reducer/traversal/projection with the oracle | Provenance disjointness, denylisted imports, isolated builds, two diverse evaluators | Structural circularity is prevented if controls hold. Coincidentally similar human mistakes remain possible. |
| One independent evaluator has an implementation defect | Dual diverse evaluator channels and mandatory disagreement blocking | A single evaluator cannot create passage. |
| Same-code clean build repeats a wrong answer | `C` is excluded from the verification conjunction | Consistency may be recorded; correctness is not inferred. |
| Fixture memorization or ID branching | Hidden mutations, adjacent cases, semantic-equivalence relations, implementation freeze before seed generation | Bounded resistance, not proof against all adaptive behavior. |
| Expected-answer leakage | Input-only public corpus, sealed `O_v`, access incompatibilities and logs | Leakage becomes detectable and challengeable if logging and custody assumptions hold. |
| Dissent/abstention erased | Signed append-only reviewer records are receipt prerequisites | Erasure invalidates the run rather than resolving disagreement. |
| Oracle correction rewrites history | Content commitments and immutable version binding | Prior receipt remains bound to prior expectation hash. |

### 3.3 Failure modes not eliminated by code diversity

| Failure family | Why independence alone is insufficient | Required response |
|---|---|---|
| Defect in shared public scenario axioms `B` | Both evaluators correctly implement the same bad premise. | Preserve provenance, dissent, challenge, and supersession; do not claim legal truth. |
| Correlated interpretation by nominally separate teams | Common training, organizational pressure, copied design notes, or a common misconception can correlate failures. | Authorship provenance, independent derivation records, competence review, inter-laboratory comparison, and seeded probes. |
| Collusion | Separation of accounts does not defeat collusion. | Institutional controls, auditability, sanctions, rotation, and independent challenge. No cryptographic proof of non-collusion is claimed. |
| Inadequate predicate or mutation coverage | A wrong result may satisfy weak properties. | Coverage obligations linked to each axiom/failure family and adversarial review. |
| Cryptographic compromise | Commitments and logs depend on keys and algorithms. | Versioned algorithms, key lifecycle, rotation, compromise response, and supersession. |

The resulting claim is therefore conditional: **given a competent, non-colluding independent function; adequate public axioms and discriminator coverage; sound cryptographic primitives; and enforced provenance/access controls, the verification result is not circular with the implementation for the named failure modes.** It is not a probabilistic assertion that failures are statistically independent.

## 4. Required comparative models

| Model | Honest value | Eliminating property / disposition |
|---|---|---|
| 1. Separately implemented declarative reducer | Can produce reference observable traces from the public axioms and expose transition disagreements. Different representation and authoring can break direct code inheritance. | **Not sufficient alone.** A complete reducer may reproduce a specification misconception, overfit trace details, or become a second monolithic runtime. Retained as evaluator `R_v`, not selected as the sole oracle. |
| 2. Predicate evaluator without a full runtime | Checks invariants, forbidden states, conservation/monotonicity relations, authority limits, and metamorphic relations without replaying every internal transition. | **Not sufficient alone.** An incomplete predicate set can accept a wrong trace that happens to satisfy all tested properties. Retained as evaluator `P_v`, not selected as the sole oracle. |
| 3. Dual independent evaluators with disagreement adjudication | Makes divergent reasoning observable and prevents one evaluator from silently defining truth. It permits architectural diversity: `R_v` is constructive, `P_v` is relational. | **Selected.** Passage requires both channels, sealed expectation compatibility, and no unresolved integrity/adjudication defect. Disagreement is preserved and blocks the bounded verification claim. |
| 4. Same-code rebuild retained only as a diagnostic control | Detects nondeterminism, stale caches, incremental/clean-build divergence, and replay inconsistency. | **Rejected as a verifier by `S0-K14`.** It remains `C`, a diagnostic control whose agreement can never satisfy an independent verification predicate. (`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:143-154@1a7a2d05ebba22fae80e9934329e4b880806588e`, finding `S0-K14`.) |

The selected architecture is therefore model 3 composed of model 1 and model 2, with model 4 explicitly outside the verification conjunction.

## 5. Evaluator architecture

```text
                         public, input-only
                  B + corpus manifest + fixture bytes
                                  |
                    +-------------+-------------+
                    |                           |
           frozen implementation I       hidden generator M_v
                    |                           |
             raw observable trace       mutated input population
                    |                           |
                    +-------------+-------------+
                                  |
                     neutral trace exchange layer
                                  |
                    +-------------+-------------+
                    |                           |
          declarative reducer R_v      predicate evaluator P_v
                    |                           |
                    +-------------+-------------+
                                  |
             sealed expectation compatibility O_v
                                  |
               disagreement / challenge protocol H_v
                                  |
                  immutable bounded receipt in L

    same-code control C ----------------> diagnostic appendix only
```

No arrow from `I` or `C` enters `R_v`, `P_v`, `M_v`, or `O_v`. No evaluator writes a product status, authority state, or canonical confidence record.

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

### 6.3 Combined decision rule

For fixture `x`, output trace `y`, expectation bundle `O_v`, and evaluator versions `R_v`, `P_v`, define:

- `r(x,y)=1` only if `R_v` finds `y` compatible with at least one explicit admissible alternative and no exclusion;
- `p(x,y)=1` only if all mandatory predicates/metamorphic relations are satisfied and none is indeterminate;
- `i=1` only if all provenance, commitment, access, and run-integrity checks hold;
- `h=1` only if no required conflict, dissent, abstention, challenge, or evaluator disagreement has been discarded or prematurely resolved;
- `c` is the result of the same-code control and is deliberately absent below.

The bounded verification conjunction is:

```text
V(x,y; v) = r(x,y) ∧ p(x,y) ∧ i ∧ h
```

A population-level claim additionally requires every mandatory fixture and mutation relation in the committed population to satisfy `V`, subject to a predeclared aggregation rule. No majority vote may convert a failed or indeterminate mandatory predicate into passage. `PV-K06` supplies the analogy: an unproved approximation may not inherit a safe verdict. (`policy-engine/docs/system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md:164-182@1a7a2d05ebba22fae80e9934329e4b880806588e`, finding `PV-K06`.)

## 7. Enforceable controls

### 7.1 Source and dependency controls

1. Independent evaluators reside in independently controlled source roots and build identities. A directory name inside the product repository is not sufficient separation.
2. Evaluator builds receive no product source checkout and have network egress disabled except to an allowlisted neutral artifact mirror.
3. An allowlist contains only `B`, input/trace parsers, generic runtimes, canonicalization, cryptography, and approved neutral libraries.
4. A denylist covers product package names and content-derived signatures for admission, reducers, traversal, projection, gold labels, and fixture helpers.
5. Static import analysis, dynamic module-load tracing, SBOM comparison, source-origin scanning, generated-file provenance, and runtime network-call capture are all required. Passing one check does not waive the others.
6. Any common dependency that performs semantic normalization is reclassified as prohibited and causes the build to be rejected.

The repository’s current import policy lists the production roots and wide runtime dependencies but does not construct an independent evaluator root. (`policy-engine/architecture/imports/policy.toml:1-132@1a7a2d05ebba22fae80e9934329e4b880806588e`.) S0-GAP-02 therefore requires a separate enforcement plane rather than another allowed `runtime` import.

### 7.2 Authorship and clean-room controls

- Evaluator authors receive `B`, input-only fixtures, and independently prepared conformance vectors, not product source or visible expected traces.
- The derivation record states how each transition or predicate follows from a public axiom, with no “matched current output” rationale.
- The declarative reducer and predicate evaluator have separate primary authors and separate reviewers for the same release window.
- Product authors may answer public-spec clarification questions only through an append-only, equally visible clarification channel; private hints invalidate the affected evaluator version.
- A person with plaintext expectation access may not prepare or approve the frozen implementation submission for that window.
- These are abstract role incompatibilities. This research appoints no team or individual.

### 7.3 Build and execution controls

- Reproducible build recipes, compiler/interpreter versions, dependencies, SBOMs, and artifact digests are committed before a scored run.
- Clean builds occur in independent base images. Diversity of language/runtime is preferred where it changes failure provenance; cosmetic diversity is not credited.
- The implementation, each evaluator, generator, and expectation bundle are separately content-addressed.
- Evaluators consume immutable traces. They cannot query product internals or request adaptive reruns after seeing expectation details.
- Hidden cases are selected or generated after the implementation revision and submission digest are frozen.

### 7.4 Institutional controls

- Conflict declarations, abstentions, access grants, access revocations, key operations, challenges, and corrections are signed log entries.
- Role rotation must preserve continuity and must not permit a product author to become expectation custodian for the same evaluation window.
- Competence must be evidenced against a declared scope; organizational separation alone is not competence.
- Independent proficiency exercises use seeded faults and blind cases before an evaluator version is accepted for a real run.

## 8. Proof obligations

### Proposition 1 — same-code circularity is excluded

Assume conditions 1–9 in §3.1 hold. Let `δ` be a defect whose causal artifact lies in `SemProv_f(I ∪ C) \ (N ∪ B)`. By conditions 1 and 2, that artifact is not in `SemProv_f(R_v)` or `SemProv_f(P_v)`. Therefore neither independent evaluator can reproduce `δ` **by executing, importing, linking, generating from, or calling the defective implementation artifact**. A matching error remains possible by coincidence or shared-spec defect, but the verification claim is not circular with product code. This is the exact property role labels alone cannot establish.

### Proposition 2 — the seeded shared-reducer fault is discriminating

Let `δ*` be a seeded reducer mutation used by both incremental execution and the clean-rebuild control `C`. Suppose it causes the same wrong observable value in both paths, as prior OPS-R15 probing demonstrated can happen. (`policy-engine/docs/research/policy-operations/audits/ops-r15/ops-r15-test-and-probe-verification.md:80-160@1a7a2d05ebba22fae80e9934329e4b880806588e`.) Condition 8 requires the precommitted seed registration, before evaluator acceptance, to identify at least one independent discriminator: either a transition result in `R_v`, a mandatory predicate/metamorphic relation in `P_v`, or both.

Because `δ*` is outside both evaluators’ allowed semantic provenance, and because acceptance requires the valid seed to violate and be detected by a registered discriminator, at least one of `r` or `p` is `0`. Since `C` is absent from `V`, agreement between incremental and clean-build paths cannot repair the failure. Thus `V=0` and the verification claim is blocked.

Conversely, if the seeded fault passes both independent channels and all integrity checks, the architecture has failed its own coverage or independence premise. The expected outcome is **`ARCHITECTURE_FALSIFIED`**, not passage. This makes the probe a test of the architecture rather than a ceremonial product test.

### Proposition 3 — dual-channel disagreement cannot be laundered by voting

`V` is a conjunction, not a majority vote. If `R_v` and `P_v` disagree, either `r=0`, `p=0`, or `h=0` until the signed adjudication record establishes whether the fixture, axiom, expectation, implementation, or evaluator needs supersession. Therefore one channel cannot outvote the other. This is deliberately stricter than classic N-version voting because correlated failures make majority correctness unsafe as an assumption.

### Proposition 4 — ambiguity remains falsifiable

For each fixture `x`, `O_v` contains a finite, nonempty family of explicit alternatives `A_x={a_1,...,a_n}`, mandatory predicates, exclusions, and enumerated nonsemantic variability. `r(x,y)=1` only when `y` matches at least one `a_i` and violates no exclusion. A wildcard alternative, an unbounded “any reasonable outcome,” or a `may_vary` field that carries authority/status semantics makes `O_v` invalid. Multiple acceptable outcomes are therefore preserved without making every output acceptable.

## 9. The P27/P28 tension resolved

`P27` and `P28` normally require extension of the canonical owner rather than shadow architecture. (`policy-engine/docs/reference/policy-design-case-failure-patterns.md:71-72@1a7a2d05ebba22fae80e9934329e4b880806588e`, findings `P27`, `P28`.) `S0-K14` is an express verification exception: the evaluator’s semantic implementation must not share the canonical product owner’s answer-producing code. The resolution is split ownership by function, not duplication by accident:

- product owners continue to own production semantics and raw observable outputs;
- a product-side trace adapter may expose observations but may not decide benchmark acceptability;
- `C` may extend existing runtime-quality machinery as a consistency diagnostic;
- `R_v`, `P_v`, `M_v`, and `O_v` must be independent by construction for verification;
- their receipts do not become a second product confidence or authority ledger, preserving `INT-K05`.

## 10. Bounded conclusion

This model proves structural non-circularity for named implementation-origin failure modes under explicit provenance, access, competence, non-collusion, coverage, and cryptographic assumptions. It does not prove legal correctness, institutional independence that has not been staffed, or statistical independence of human mistakes. Those limitations are why the overall standing is `accepted_narrow_scope`, not `GO`.
