---
title: S0-GAP-02 — Independent Custody-Benchmark Oracle and Evaluator Architecture
status: research
kind: research-report
research_task: S0-GAP-02
research_only: true
source_repository: https://github.com/DenisKopylov/polisyos
repository_pin: 1a7a2d05ebba22fae80e9934329e4b880806588e
source_branch: main
delivery_branch: research/s0-gap-02-independent-benchmark-oracle
result_standing: accepted_narrow_scope
authoritative_for:
  - research architecture for a future implementation-independent custody benchmark oracle
  - formal code-independence boundary and evaluator comparison
  - research schemas, protocols, falsifiers, handoff and open questions linked below
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

# S0-GAP-02 — Independent Custody-Benchmark Oracle and Evaluator Architecture

## 1. Result standing

**`accepted_narrow_scope`.**

The architecture is sound as a research construction: it separates the product from two diverse answer-producing evaluator channels, keeps the same-code rebuild outside the verification claim, supports finite set-valued expectations, preserves dissent, seals answers, generates hidden adjacent cases, commits every version, and makes challenges and corrections append-only. Under the stated provenance, access, competence, non-collusion, coverage, and cryptographic assumptions, it establishes structural non-circularity for the named implementation-origin failure modes.

It is not `GO`. Its decisive institutional premise—a second competent and independently governed evaluator/oracle capability with enforceable authorship, access, proficiency, challenge, and continuity controls—is not established by this report or by the pinned repository. The project backlog also records that this wave does not advance the `INST-01`–`INST-05` institutional layer. (`policy-engine/docs/research/policy-operations-and-real-world-runtime-backlog.md:1-13@1a7a2d05ebba22fae80e9934329e4b880806588e`.) Architecture delivery is not implementation acceptance, does not authorize scoring, and does not unblock `OPS-R15`.

## 2. Commission, scope and precedence

`S0-GAP-02` is a ratified obligation, not a new proposal. `S0-K14` blocks an independent verification/scoring claim until an oracle and rebuild path are independent of the product’s admission, reducers, dependency traversal, and status projection; the same finding permits a same-code rebuild to establish consistency only. `S0-K13` and `S0-K15` leave observable-semantic benchmark design active, which is why `OPS-R15` can be delivered and audited yet remain unscored. (`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:96-112@1a7a2d05ebba22fae80e9934329e4b880806588e`, findings `S0-K13`–`S0-K16`; `policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:143-202@1a7a2d05ebba22fae80e9934329e4b880806588e`, finding `S0-K14` and commissioning action.)

The full register entry is authoritative on detail. It requires a public schema and input-only corpus, sealed set-valued expectations, independent evaluator interface, clean-rebuild/equivalence policy, authority axioms and human adjudication, oracle custody/challenge/supersession, adjacent/metamorphic generation, and bounded reproducibility receipts, while expressly denying production authorization or scoring effect. (`policy-engine/docs/research/policy-operations/consolidation/stage0/stage0-additional-research-register.md:123-199@1a7a2d05ebba22fae80e9934329e4b880806588e`, entry `S0-GAP-02`.) The present brief adds compatible specificity: a formal independence model, exact falsifiers plus additional attacks, prerequisite-safe integration vocabulary, typed open questions, and an external transfer ledger. No substantive conflict was found; the register wins if one is later discovered.

The architecture is also bounded by:

- `S0-K13`: assess observable custody semantics rather than mandate product internals;
- `S0-K15`: resist memorization and preserve challenge, dissent, and abstention;
- `S0-K16`: any passage is bounded to named artifacts and carries no authority;
- `INT-K05`: do not create a second product confidence/authority ledger;
- `PV-K06`: an unproved approximation, timeout, empty result, unsupported theory, or incomplete history cannot inherit an acceptable verdict. (`policy-engine/docs/system-design-decisions/int-wave-claim-semantics-ratification.md:157-170@1a7a2d05ebba22fae80e9934329e4b880806588e`, finding `INT-K05`; `policy-engine/docs/system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md:164-182@1a7a2d05ebba22fae80e9934329e4b880806588e`, finding `PV-K06`.)

## 3. Direct answer to the commissioned question

> How can an implementation-independent, machine-readable and challengeable oracle establish acceptable custody semantics while keeping expected results sealed, preserving ambiguity and dissent, preventing shared-code circularity, and resisting fixture memorization?

Use a **dual diverse evaluator architecture** over a public observable-semantic specification and an input-only corpus:

1. Freeze a public problem definition `B`: fixture/input grammar, raw observable-trace grammar, authority-scenario axioms, and explicit equivalence/metamorphic relations. It contains no expected product actions or labels.
2. Commit and seal a versioned expectation bundle `O_v` that contains finite admissible alternatives, mandatory predicates, exclusions, bounded nonsemantic variability, reviewer records, and unresolved dissent.
3. Evaluate the frozen product output through two answer-producing channels that are disjoint from the product and from each other beyond `B` and a tightly bounded neutral substrate:
   - `R_v`, an independently authored declarative reducer/reference semantics;
   - `P_v`, an independently authored predicate, invariant, and metamorphic evaluator.
4. Retain the product’s same-code incremental/clean rebuild `C` only as a diagnostic consistency control. It has zero weight in the verification conjunction.
5. Generate hidden post-freeze adjacent cases and metamorphic variants through independent `M_v`, with committed mutation certificates and a fixed denominator.
6. Require a signed, append-only evidence chain for package commitments, access, hidden-seed generation, run inputs, both evaluator results, reviewer conflicts/dissent/abstention, challenges, corrections, and supersessions.
7. Accept no result unless both independent channels, integrity/provenance controls, and human-record completeness agree. Disagreement blocks; it is not majority-voted away.
8. Emit only the bounded `S0-K16` claim that the named implementation revision, environment, fixture population, evaluator versions, expectation version, and tested predicates satisfied the recorded conditions.

This design makes expected answers secret but their commitments public; makes ambiguity explicit but finite; makes dissent durable rather than averaged; makes product-code circularity mechanically detectable; and makes memorization resistance an ongoing hidden-population property rather than a static fixture claim.

## 4. Pass-I orientation audit

The orientation audit was completed before architecture selection and is retained in [the orientation ledger](s0-gap-02/orientation-ledger.md).

### 4.1 Access and denominator discipline

Ordinary `git clone` and archive access failed because the execution environment could not resolve `github.com`. The connected GitHub interface supported exact-ref file reads at `1a7a2d05ebba22fae80e9934329e4b880806588e` but not a recursive raw tree/occurrence stream or write action. Under `P35`, search results were not promoted to a complete census; under `P36`, governing repository propositions are cited by finding ID. (`policy-engine/docs/reference/policy-design-case-failure-patterns.md:71-80@1a7a2d05ebba22fae80e9934329e4b880806588e`, findings `P35`, `P36`.)

The commission’s six source-tree figures were therefore separated into three denominators: distinct files, matching source lines, and raw occurrences.

| Token | Brief’s distinct-file figure | Independent result in this run | Lines | Occurrences | Verdict |
|---|---:|---|---|---|---|
| `benchmark` | 183 | Exact complete-tree figure not established; dense vocabulary and named owners verified. | `not_established` | `not_established` | Do not repeat 183 as independently reproduced. |
| `evaluator` | 80 | Exact complete-tree figure not established; connected search exceeded/altered relevant semantics. | `not_established` | `not_established` | Do not repeat 80 as independently reproduced. |
| `oracle` | 44 | Exact lowercase complete-tree figure not established; connected case-insensitive search returned a different file result. | `not_established` | `not_established` | Query-semantic disagreement, not a repository contradiction. |
| `metamorphic` | 3 | 3 matching files by connected search. | `not_established` | `not_established` | Agreement at file-search denominator only. |
| `fixture_corpus` | 1 | 1 matching file by connected search. | `not_established` | `not_established` | Agreement at file-search denominator only. |
| `sealed_expect` | 0 | 0 matching files by connected search under `policy-engine/src`. | 0 under that search | 0 under that search | Agreement within the connected-search boundary. |

The ledger supplies a fixed-string, case-sensitive `git grep` command that a hostile audit can run over a complete checkout to reproduce all three denominators. “Not established” records the blocked complete-set check; it is not used to avoid a feasible sample inspection.

### 4.2 Concept sample and the dangerous configuration

The bounded concept denominator was the **three named runtime-quality benchmark owners; 3/3 were read; 3/3 are unsuitable as independent custody verifiers**:

- `policy_benchmarking.py` is product runtime-quality machinery with implementation-facing metrics/criteria. (`policy-engine/src/polisyos/runtime/quality/policy_benchmarking.py:1-70@1a7a2d05ebba22fae80e9934329e4b880806588e`.)
- `grounding_benchmark.py` imports product admission/relation/phrasing/hash logic and carries visible expected fields. (`policy-engine/src/polisyos/runtime/quality/grounding_benchmark.py:1-140@1a7a2d05ebba22fae80e9934329e4b880806588e`.)
- `semantic_fixtures.py` contains product semantic fixtures, visible signals, and adjudication/gold-card behavior. (`policy-engine/src/polisyos/runtime/quality/semantic_fixtures.py:1-150@1a7a2d05ebba22fae80e9934329e4b880806588e`.)

The repository import policy exposes broad in-tree package relationships but no separately governed independent evaluator root at the pin. (`policy-engine/architecture/imports/policy.toml:1-132@1a7a2d05ebba22fae80e9934329e4b880806588e`.) This establishes the architectural trap qualitatively: existing benchmark machinery cannot simply be renamed or extended into the `S0-K14` oracle.

### 4.3 OPS-R15 prior art

The OPS-R15 report and all seven audit artifacts were read. Prior art already identifies a 117-row corpus with implementation-visible expected answers, set-valued outcome needs, hidden-mutation needs, and the same-code rebuild trap. Its probe showed a deliberately faulty reducer producing the same wrong answer in incremental and rebuild paths while an independent calculation differed. (`policy-engine/docs/research/policy-operations/stage0/ops-r15-custody-capstone-semantic-kernel-and-benchmark-architecture.md:326-470@1a7a2d05ebba22fae80e9934329e4b880806588e`, especially `CK-11`; `policy-engine/docs/research/policy-operations/audits/ops-r15/ops-r15-test-and-probe-verification.md:80-160@1a7a2d05ebba22fae80e9934329e4b880806588e`.)

S0-GAP-02 extends that prior art with an enforceable provenance boundary, dual evaluator selection, sealed-answer/custody protocol, exact falsifiers, and institutional conditions. It does not relabel OPS-R15’s visible expected traces as an oracle.

## 5. What may be shared—and what must never be shared

This boundary is logically prior to the component design. The full formal treatment is in [the independence model and evaluator interface](s0-gap-02/independence-model-and-evaluator-interface.md).

### 5.1 Legitimately shared neutral substrate

The product and independent evaluators may share only material that identifies the public question or permits deterministic byte exchange without deciding the answer:

- ratified observable-semantic requirements and the public benchmark specification;
- input-only fixture bytes, opaque identifiers, declared units, syntactic types, version identifiers, and public authority-scenario axioms;
- a raw observable-output grammar that contains facts/events/receipts but no product verdict mapping;
- generic language runtimes, operating systems, cryptographic primitives, JSON/YAML parsers, canonicalization algorithms, and public conformance vectors;
- hashes, signatures, seeds, environment descriptions, and explicitly nonsemantic ordering rules.

A helper is not neutral because of its name. If it admits evidence, reduces custody state, traverses dependencies, computes affected sets, orders by product priority, maps statuses/authority, or collapses ambiguity, it is semantic and prohibited.

### 5.2 Never shared for an independent verification claim

Neither `R_v` nor `P_v` may import, link, copy, generate from, call remotely, deserialize, fit to, or derive from:

- product admission or re-admission logic;
- custody transition reducers/state machines;
- dependency traversal, closure, affected-set, or propagation logic;
- status, posture, limitation, or authority projection/mapping;
- implementation fixtures carrying expected actions, states, labels, mechanisms, or scores;
- OPS-R15 implementation-visible expected traces;
- product gold labels, semantic adjudication helpers, or test-oracle code;
- generated schemas, lookup tables, snapshots, compiled rules, model artifacts, caches, services, or binary layers derived from prohibited product semantics;
- the product same-code rebuild as evidence of correctness;
- hidden expectation or challenge-answer material before the product submission is frozen.

The prohibition is transitive and behavioral, not filename-based. It covers source, generated artifacts, dependencies, builds, network services, authorship inputs, review inputs, and data access.

## 6. Formal independence model and proof

### 6.1 Components

Let:

- `I` = implementation under test at a frozen revision;
- `C` = product same-code incremental/clean-build consistency control;
- `B` = public benchmark specification and axioms;
- `O_v` = sealed expectation bundle version `v`;
- `R_v` = independently authored declarative reducer/reference semantics;
- `P_v` = independently authored predicate/metamorphic evaluator;
- `M_v` = hidden adjacent-case/mutation generator;
- `H_v` = human review, conflict, dissent, abstention, and adjudication records;
- `L` = append-only commitment/access/run/challenge/correction/supersession log;
- `N` = allowed neutral substrate.

For component `X` and failure mode `f`, `SemProv_f(X)` is every transitive answer-producing semantic source, generated code/table/model, service, dependency, derivation/review input, build input, and runtime call that can influence `X`’s result. `Input_f(X)` is the complete set of declared immutable run data. Any undeclared data access is a semantic-provenance violation.

This distinction permits two evaluators to judge the same committed fixture, trace, and expectation bytes without pretending those shared inputs are shared code. Their mutual independence is about semantic provenance. Correctness of shared `B` or `O_v` remains a separate, challengeable specification/oracle premise.

### 6.2 Constructed independence conditions

For the named implementation-origin failure families—admission, transition reduction, dependency traversal, affected-set computation, status/authority projection, ambiguity collapse, identifier branching, and temporal ordering—the architecture claims structural implementation independence only when:

1. `SemProv_f(I ∪ C) ∩ SemProv_f(R_v) ⊆ N ∪ B`;
2. `SemProv_f(I ∪ C) ∩ SemProv_f(P_v) ⊆ N ∪ B`;
3. `SemProv_f(R_v) ∩ SemProv_f(P_v) ⊆ N ∪ B`;
4. no allowed shared semantic derivation artifact is generated from, fitted to, or selected by observing product behavior, visible expected traces, or prior hidden-run results;
5. product/control declared inputs exclude plaintext `O_v`, hidden seeds before authorized reveal, evaluator internals, and adjudication answers;
6. evaluator common inputs are exhaustively enumerated and committed and may contain only `B`, the committed population, immutable raw trace, scoped `O_v`, and neutral conformance data;
7. identities able to write `I` or `C` cannot write `R_v`, `P_v`, `M_v`, `O_v`, or their attestations for the same evaluation window, and pre-freeze plaintext expectation access is incompatible with implementation authorship/submission authority for that window;
8. every failure family claimed has a precommitted independently derived discriminator and a blind or seeded acceptance challenge; unregistered families are outside the claim;
9. the receipt contains machine-checkable evidence for conditions 1–8, including declared inputs and discriminator results.

The architecture does **not** assert unconditional probabilistic independence. `B` and committed `O_v` are shared question/reference inputs; bad public axioms or expectations can therefore induce correlated specification/oracle failure. Competence, collusion, coercion, funding incentives, and coverage remain institutional or threat-model assumptions.

### 6.3 Verification rule

For fixture population `X`, define:

```text
r = R_v accepts every required fixture/alternative/predicate relation
p = P_v accepts every required predicate and metamorphic relation
i = provenance, commitment, access, population and log integrity all hold
h = required human records are complete and no unresolved blocking disagreement is erased

V(I, X, v) = r ∧ p ∧ i ∧ h
```

`C` is intentionally absent. A same-code consistency pass may be attached to the receipt as diagnostic evidence but cannot turn any zero in `V` into one.

### 6.4 Proof sketch

**Non-circularity.** Let defect `δ` originate in a product semantic artifact outside `N ∪ B`. Conditions 1 and 2 exclude that artifact from both independent evaluator semantic provenances. Neither evaluator can reproduce `δ` by executing, importing, linking, generating from, or calling the defective product artifact. A coincident human mistake or shared-specification defect remains possible, but the claim is not circular with product code.

**Single-evaluator containment.** Because `V` is a conjunction, a defect in either `R_v` or `P_v` blocks verification or creates a preserved disagreement. One channel cannot outvote the other.

**Same-code fault discrimination.** Seed a reducer defect into the code shared by product incremental and clean-build paths. `C` may show perfect parity on the wrong result. For the registered seeded failure class, condition 8 requires at least one independent discriminator in `R_v` or `P_v` to fail, so `V=0`. If both independent channels accept the valid seeded wrong result, the architecture outputs `ARCHITECTURE_FALSIFIED`; it does not pass.

**Bounded ambiguity.** Each fixture’s sealed answer is a finite nonempty set of explicit alternatives plus mandatory predicates and exclusions. Wildcards, “any reasonable outcome,” or semantic fields marked unconstrained invalidate the bundle. More than one outcome can be acceptable without making every outcome acceptable.

The proof establishes conditional structural separation. It does not establish legal correctness, evaluator competence not yet demonstrated, or a reliability probability.

## 7. Comparative models: breadth before selection

| Required model | What it contributes | Eliminating property when used alone | Disposition |
|---|---|---|---|
| Separately implemented declarative reducer | Re-expresses custody semantics through a different representation/algorithm/authoring path and can produce complete alternative traces/affected sets. | A single reference implementation can contain its own defect or shared-specification error; no independent predicate channel detects it. | **Selected as `R_v`, but not alone.** |
| Property/predicate evaluator without full reference runtime | Tests invariants, authority boundaries, conservation/cardinality, append-only history, monotonic limitations, metamorphic relations, and forbidden effects without cloning the runtime. | Predicates can be incomplete or too weak to determine allowed transition/affected-set semantics; a system can satisfy invariants while still producing the wrong acceptable trace. | **Selected as `P_v`, but not alone.** |
| Dual independent evaluators with disagreement adjudication | Contains single-evaluator defects, exposes correlated interpretation, and preserves challenge/dissent. | Simple voting or agreement-as-truth is disqualified by N-version correlated-failure evidence and shared-specification risk. | **Selected with blocking conjunction and preserved adjudication, never voting.** |
| Same-code rebuild diagnostic | Detects incremental/rebuild drift and supports consistency diagnosis. | Shared reducer defects can pass both paths; direct circularity violates `S0-K14`. | **Retained only as `C`; prohibited from verification.** |

External disciplines support the selection but do not confer authority:

- proficiency testing/inter-laboratory comparison: competence through blind performance, not self-description;
- metrological traceability: explicit reference chains and uncertainty, not a claim that software results are SI measurements;
- public audit/accreditation: evidenced independence, quality review, and challenge, not a GAGAS/ISO certification;
- sealed examination: validity-sensitive confidentiality and independent breach investigation, not qualification regulation;
- N-version research: design diversity plus known correlated-failure limits, not majority correctness;
- clean-room practice: specification/verification discipline and certification separation, not promotion of the same-code rebuild;
- metamorphic testing: necessary relations and follow-up cases when point oracles are incomplete, not a complete oracle;
- transparency logs/canonicalization/key management: immutable byte/history evidence, not semantic truth.

The complete source-by-source transfer and non-transfer analysis is in [the external primary-source ledger](s0-gap-02/external-source-and-transfer-ledger.md).

## 8. Selected architecture

```text
                         PUBLIC / IMPLEMENTATION-VISIBLE

  B: observable semantic spec + authority axioms + equivalence relations
                         |
  X_public: input-only fixtures -----> frozen product I -----> raw trace T
                         |                                  |
                         |                                  +--> C: same-code
                         |                                       rebuild control
                         |                                       (diagnostic only)
                         |
  ---------------------- commitment / access boundary ----------------------
                         |
       O_v: sealed finite alternatives, predicates, exclusions, dissent
       M_v: hidden post-freeze mutations and adjacent cases
                         |
                 +-------+----------------+
                 |                        |
          R_v declarative reducer    P_v predicates/metamorphic
          separate provenance        separate provenance from I and R
                 |                        |
                 +-----------+------------+
                             |
                   conjunction + integrity
                             |
                H_v preserved review/adjudication
                             |
               bounded reproducibility receipt Q_v
                             |
      L: append-only commitments, access, runs, challenges, corrections,
         supersessions, inclusion/consistency proofs and external witnesses
```

### 8.1 Component import rules

| Component | May import/read | Must not import/read |
|---|---|---|
| Product `I` | Public `B`, public inputs, product code | Plaintext `O_v`, hidden seed/variants, evaluator source, adjudication answers |
| Product control `C` | Product code and raw inputs | Any role in `V`; no independent-verification label |
| Trace adapter | Product raw observations and neutral DTO/canonicalization | Acceptance logic, expected labels, dependency/status/authority mappings created for evaluation |
| `R_v` | `B`, public/hidden input, raw trace, neutral substrate | Product semantics, product fixtures/gold labels, `P_v` internals, answer-derived generated artifacts |
| `P_v` | `B`, public/hidden input, raw trace, neutral substrate | Product semantics, `R_v` answer path/private derivation, product fixtures/gold labels |
| `M_v` | Public mutation grammar and axioms | Product code/behavior-derived variant selection, evaluator answer code, implementation-visible seed |
| `O_v` compiler/custody | Approved public axioms, signed reviewer records, canonicalization/crypto | Product output-driven answer edits after freeze, unlogged plaintext export |
| Receipt/log verifier | Committed artifacts, raw results, proofs, identities | Authority inference, product status mutation, silent correction |

### 8.2 Enforcement—not promises

A future implementation must demonstrate:

- separate repositories/build identities/service accounts for `R_v`, `P_v`, `M_v`, and `O_v`;
- source and binary dependency allowlists plus semantic-family denylists;
- transitive provenance graphs covering generated files, containers, model artifacts, network services, build inputs, and authorship/review sources;
- no product repository in evaluator build context and no evaluator/expectation plaintext in product build context;
- isolated networks with recorded egress, reproducible builds, signed source/SBOM/build attestations, and cross-language public vectors;
- identity-enforced role incompatibilities and plaintext access logs;
- acceptance probes for direct import, transitive import, generated-artifact laundering, poisoned neutral helpers, common private derivation, and runtime remote calls;
- the full architecture falsifier suite before an evaluator version is accepted.

Organizational separation without these controls is not independence.

## 9. Machine-readable public schema and input-only corpus

The research schema is specified in [public schema and sealed expectations](s0-gap-02/public-schema-and-sealed-expectations.md). It is deliberately a semantics research contract, not a final production wire/schema/API decision.

### 9.1 Public package

A public package binds:

```yaml
benchmark_spec:
  spec_id: stable identifier
  spec_version: immutable version
  authority_axiom_set_digest: digest
  observable_trace_profile: version
  equivalence_relation_catalog: version
  canonicalization_profile: version
fixture_manifest:
  corpus_id: stable identifier
  corpus_version: immutable version
  fixture_digests: [digest]
  declared_strata_and_denominators: {...}
  no_expectation_fields_attestation: signed reference
fixture:
  fixture_id: opaque nonsemantic identifier
  scenario_profile: jurisdiction/period/institutional assumptions by stable reference
  initial_observations: [...]
  external_events: [...]
  declared_subjects_and_relationships: [...]
  uncertainty_and_contestation: [...]
  permitted_nondeterminism_dimensions: [public relation references]
```

The public corpus may express facts, events, uncertainty, contestation, temporal relationships, and fixture-local authority assumptions. It may not expose expected actions, statuses, mechanisms, impact sets, labels, scores, alternative IDs that disclose the answer, or a resolvable pointer to plaintext expectations.

### 9.2 Corpus population

The corpus is stratified by declared semantic dimensions rather than selected after seeing results: temporal order/concurrency, duplicate delivery, authority change, dependency topology, ambiguity/dissent, correction/supersession, recovery asymmetry, tenant/scope isolation, and external-act boundaries. Every published stratum has a committed denominator. Hidden cases are generated only after the implementation is frozen.

A leakage scanner combines exact field denylists, semantic text/provenance review, lookup/entropy probes, build-context inspection, and human review. A leak discovered after exposure challenges every affected run; redacting the file later does not restore independence.

## 10. Sealed expectations that admit alternatives without becoming unfalsifiable

For fixture `x`, the sealed bundle contains:

```yaml
SealedExpectation:
  fixture_digest: digest
  alternatives:
    - alternative_id: opaque
      required_observable_predicates: [predicate]
      allowed_partial_order: [constraint]
      required_effect_set_relation: relation
      required_authority_limitations: [limitation]
      permitted_nonsemantic_variation: [named public dimension]
  mandatory_cross_alternative_predicates: [predicate]
  exclusions: [forbidden observable/predicate]
  ambiguity_basis:
    kind: genuine_semantic_ambiguity | unresolved_dissent | bounded_nondeterminism
    authority_and_source_records: [digest]
  reviewer_records_root: digest
  unresolved_positions: [digest]
  expectation_version: immutable version
```

Acceptance is:

```text
Accept(x, y) =
  (there exists explicit alternative a in A_x such that Match(y, a))
  AND all mandatory predicates hold
  AND no exclusion holds
  AND every varied field is authorized by a named bounded variability rule
```

Bundle validation rejects:

- empty or wildcard alternative sets;
- “any reasonable outcome” or equivalent escape hatches;
- unconstrained status, authority, affected-set, external-act, or history fields;
- alternatives added after observing a frozen submission without a new version/challenge;
- discarded dissent/abstention/conflict records;
- expectation references visible to the implementation.

Genuine ambiguity is preserved as explicit alternatives or a blocking unresolved record. It is never resolved merely to create a score.

## 11. Clean rebuild, reference semantics and equivalence policy

Two “clean” concepts must remain distinct:

1. **Independent reference reconstruction (`R_v`).** `R_v` starts from public/hidden fixture inputs, public axioms, and raw observations in an isolated clean environment. It recomputes the expected semantic relations through a separately authored declarative model. It may establish an independent verification predicate when all provenance conditions hold.
2. **Product same-code clean rebuild (`C`).** `C` reruns the product’s own semantic code from a clean store/build. It may establish internal consistency or diagnose incremental drift. It cannot establish independent correctness, cannot replace `R_v` or `P_v`, and cannot contribute to `V`.

The equivalence policy is explicit per field/relation:

- canonical byte equality for immutable deterministic scalar fields;
- set equality for declared unordered collections, while separately checking duplicates/cardinality;
- graph isomorphism only for declared opaque identifier renaming, with semantic labels/edges preserved;
- partial-order equivalence where concurrency is genuinely permitted;
- finite alternative membership for genuine semantic ambiguity;
- monotonic or relational predicates for authority limitation, append-only history, affected-set conservation, and metamorphic transforms;
- no tolerance band or approximate match unless predeclared, justified, bounded, and incapable of weakening authority/status semantics.

An equivalence relation is public, versioned, independently tested, and cannot be invented after a failure. An unproved approximation receives a blocking/not-established result under `PV-K06`.

## 12. Authority-scenario axioms and human adjudication

The full protocol is in [oracle custody and adjudication](s0-gap-02/oracle-custody-and-adjudication-protocol.md).

### 12.1 Axiom record

Each fixture-local authority axiom states:

- stable axiom ID/version and content digest;
- jurisdiction, institution, role, temporal validity, and scenario scope;
- source/authority references and known limitations;
- proposition in machine-checkable form where feasible;
- contestability class and uncertainty;
- authors/reviewers, competence scope, conflicts, abstentions, dissents, and signatures;
- supersedes/superseded-by links.

Required axiom families cover at least evidence admissibility for the scenario, actor/claim/scope authority, temporal validity and reproof triggers, prohibited external acts, scope/tenant/cell boundaries, correction/supersession effects, and conditions that must remain unresolved.

These axioms are benchmark assumptions, not universal legal truth or an authority grant.

### 12.2 Adjudication protocol

1. Reviewers submit signed positions independently: support, dissent, abstain, conflict/recusal, or out-of-scope.
2. Raw positions are committed before any aggregation; no position is overwritten.
3. `R_v`/`P_v` disagreement or reviewer disagreement is classified by possible locus: fixture, public axiom, sealed expectation, parser/canonicalization, reducer, predicate, product trace, or access/integrity.
4. A minimal counterexample and all affected versions/runs are recorded.
5. Adjudication may affirm an existing version, challenge a run, or propose a new superseding fixture/axiom/expectation/evaluator version. It may not mutate an old version.
6. Abstention is not support; recusal is not absence; dissent is not averaged away; unresolved material disagreement blocks the affected claim.
7. Every rationale, minority view, evidence link, conflict, and appeal remains retrievable.

No reviewer panel is appointed by this report.

## 13. Commitment, custody, access, rotation, challenge and supersession

The oracle is itself a custody subject.

### 13.1 Commitment and run order

A valid run follows this order:

1. publish/freeze `B` and public corpus commitments;
2. accept and commit evaluator releases/provenance;
3. commit sealed `O_v` and reviewer-record root without exposing plaintext;
4. freeze product revision, environment, submission, and trace-adapter version;
5. generate/commit hidden mutation seed and resulting population manifest;
6. execute product and same-code diagnostic;
7. evaluate through `R_v` and `P_v`;
8. commit raw results and human records;
9. emit receipt bound to all prior digests;
10. append challenge/correction/supersession events without rewriting any prior entry.

### 13.2 Access and role separation

Abstract roles include specification author, public corpus curator, expectation author, plaintext custodian, evaluator-R author/releaser, evaluator-P author/releaser, mutation custodian, product author, submission freezer, run operator, reviewer/adjudicator, challenge receiver, and log witness. Incompatible roles are enforced per evaluation window; exceptions are signed and independently reviewed. Access events carry actor, role, purpose, object digest/version, operation, time, authorization, result, and prior/current log heads.

### 13.3 Commitments and logs

- Canonical bytes use a public profile with cross-language vectors; original bytes are retained.
- Domain-separated commitments bind object kind, version, digest algorithm, canonicalization profile, salt/key identifier, and ciphertext or content digest as applicable.
- The append-only log records package commitments, access, key operations, freezes, seeds, runs, results, conflicts, challenges, corrections, and supersessions.
- Inclusion and consistency proofs are witnessed by more than the log operator; equal-size inconsistent roots or missing consistency proofs trigger the split-view falsifier.
- A hash proves byte binding, not semantic correctness.

### 13.4 Key rotation and compromise

Rotation creates a new key/version record and preserves historical verification. It cannot reset access history or re-sign an old artifact as though unchanged. Compromise triggers a signed incident, scope assessment, challenges to affected runs, replacement keys, and supersession links. No KMS, algorithm suite, vendor, or final cryptographic profile is selected here.

### 13.5 Challenge, correction and supersession

A challenge names the challenged artifact/run, grounds, evidence, requested remedy, standing/bounded disclosure, and conflict record. It receives a signed acknowledgement and reasoned disposition. A correction always creates a new immutable version and a supersession edge. A prior receipt remains bound to the expectation/evaluator/fixture versions actually used; displays may show that it was later challenged or superseded, but cannot silently recompute it.

## 14. Adjacent-case and metamorphic anti-memorization layer

The generator and receipt are specified in [mutation and reproducibility](s0-gap-02/mutation-and-reproducibility.md).

A metamorphic relation is a versioned statement:

```text
MR = (precondition, input transform τ, expected output relation ρ,
      semantic-dimension change certificate, exclusions, reviewer records)
```

The generator produces source/follow-up pairs only when the precondition holds and emits a mutation certificate. Required families include:

- bijective renaming/permutation of opaque IDs;
- irrelevant metadata and presentation perturbation;
- input/map ordering changes where order is declared nonsemantic;
- duplicate delivery/retry/idempotency;
- equivalent event interleavings under a declared partial order;
- boundary-adjacent time/value cases on both sides of a semantic threshold;
- authority narrowing/revocation with payload held constant;
- dependency-edge addition/removal with predicted affected-set relation;
- correction/supersession versus historical replay;
- tenant/scope relabeling with isolation-preserving relation;
- controlled ambiguity/dissent alternatives;
- asymmetric store/recovery cases;
- prohibited external-act substitutions;
- missing-edge and hidden-dependency perturbations;
- Unicode/canonicalization/serialization equivalents that must not change semantics.

### 14.1 Adjacent case definition

A case is adjacent only when a certificate identifies exactly one intended semantic dimension change (or an explicitly semantic-preserving transform), holds all others invariant, states the expected relation rather than a hidden point answer, and records why the transformed case remains in scope. An invalid certificate yields `TEST_SETUP_INVALID`, not a product failure.

### 14.2 Population and exposure controls

- Product revision/submission freezes before hidden seed generation.
- Seeds and full population manifests are committed before execution.
- Invalid generated cases are retained with reasons; failed valid cases cannot be silently dropped.
- The receipt binds planned/generated/valid/executed/reported denominators and every omitted digest.
- Submission/query budgets and diagnostic granularity are predeclared; adaptive probing compromises the population.
- Exposed families are retired or reweighted only through a new prospective version, never after inspecting a run.

Static visible fixture success is insufficient. The anti-memorization claim is bounded to the named hidden population and mutation families.

## 15. Reproducibility receipt and bounded claim

A receipt binds at minimum:

- source repository/revision and dirty-state digest;
- product artifact/container/build attestations;
- environment, dependencies, configuration, clocks/time profile, and resource limits;
- public specification/corpus/fixture digests and complete population denominator;
- trace adapter and raw trace digests;
- same-code diagnostic version/result, labeled control-only;
- `R_v`, `P_v`, `M_v`, `O_v`, canonicalization, and provenance-policy versions/digests;
- expectation commitment, log heads, inclusion/consistency proofs, witnesses, access summary, and key identifiers;
- per-fixture/per-predicate raw outcomes from both evaluators;
- disagreement, conflict, dissent, abstention, recusal, challenge, and adjudication roots;
- invalid/unsupported/timeout/approximation records;
- exact harness/falsifier suite version and results;
- signatures and reproduction instructions.

The only allowed passage language is bounded:

> For implementation artifact `<digest>` at repository revision `<revision>`, executed in environment `<environment-digest>` against committed fixture population `<population-digest>` containing `<valid-count>` valid cases, evaluator releases `<R-digest>` and `<P-digest>`, expectation version `<O-digest>`, mutation generator `<M-digest>`, and predicate catalog `<catalog-version>` produced the recorded compatible results; provenance, commitment, access, population, reviewer-record and log-integrity predicates named in receipt `<receipt-digest>` were satisfied. This statement applies only to those artifacts, cases, relations and conditions. It carries no authority, legal sufficiency, production capability, future-behavior, completeness, OPS-R15 score, or unblocking claim.

Any missing bound changes the claim to invalid/not-established; it cannot inherit an acceptable result.

## 16. Falsifier suite

[The executable research specification](s0-gap-02/falsifier-suite.md) contains the six commissioned cases and seven additional attacks. Harness outcomes are local assertions, not product statuses.

| ID | Attack/fault | Exact architecture-level expected outcome |
|---|---|---|
| `F-01` | `R_v` or `P_v` imports product admission, reducer, dependency traversal, or status projection directly/transitively. | Offending provenance ancestors named; `ARCHITECTURE_DETECTED` + `RUN_INVALID`; no semantic aggregation. |
| `F-02` | Public/build-visible files expose expected actions/labels through fields, prose, or an opaque lookup. | Every leak channel detected; `ARCHITECTURE_DETECTED` + `RUN_INVALID`; all exposed runs challenged. |
| `F-03` | ID-renumbered or adjacent unseen case changes outcome without a certified semantic reason. | Valid relation violation localized; `VERIFICATION_BLOCKED`; no label-per-case escape. |
| `F-04` | Shared product reducer reports 103 instead of independently correct 3 in both incremental and clean rebuild. | `C=CONTROL_ONLY_PASS`; `R_v` derives 3; `P_v` fails cardinality/bound predicates; `VERIFICATION_BLOCKED`. If both independent channels accept, exactly `ARCHITECTURE_FALSIFIED`. |
| `F-05` | Expectation correction silently replaces the oracle behind a prior run. | Binding mismatch; `ARCHITECTURE_DETECTED` + `HISTORY_VIOLATION_DETECTED` + `RUN_INVALID`; old receipt remains bound to old oracle. |
| `F-06` | Conflict, abstention, dissent, recusal, or evaluator disagreement is discarded. | Omitted records/disagreement detected; `DISSENT_PRESERVED` + `VERIFICATION_BLOCKED` + `RUN_INVALID`. |
| `A-07` | Generated semantic artifact laundering. | Transitive product provenance detected; run invalid. |
| `A-08` | “Neutral” helper secretly maps statuses or traverses dependencies. | Helper reclassified semantic; shared-provenance violation; run invalid. |
| `A-09` | Commitment/evaluator canonicalization or parser split view. | Ambiguous documents rejected or one canonical digest; any split view invalidates run. |
| `A-10` | Failed mutations selectively omitted or denominator changed. | Population mismatch and omitted digests named; run invalid. |
| `A-11` | Adaptive repeated submissions infer hidden answers. | Query-budget violation/population compromise; affected runs invalid/challenged. |
| `A-12` | Append-only log split view or rotation truncates access history. | Equivocation/gap detected; history violation; affected runs blocked/invalid. |
| `A-13` | Two languages share one private semantic derivation/prompt/notes. | Shared private ancestor detected; diversity claim rejected; run invalid. |

`F-04` is dispositive. A design that merely shows product incremental/rebuild agreement fails the commission.

## 17. Repository integration handoff

The full handoff and typed open questions are in [integration handoff](s0-gap-02/integration-handoff-and-open-questions.md).

### 17.1 Missing-state vocabulary used only after prerequisites

The repository vocabulary defines downstream gaps only after upstream capability pieces exist. (`AGENTS.md:13-37@1a7a2d05ebba22fae80e9934329e4b880806588e`; `policy-engine/docs/reference/policy-design-case-failure-patterns.md:15-45@1a7a2d05ebba22fae80e9934329e4b880806588e`.) At the pin:

- **not `contract_only`:** these Markdown schemas are not implementation types/contracts;
- **not `producer_missing`:** no accepted executable independent consumer is evidenced;
- **not `bridge_missing`:** both independent endpoints are not evidenced;
- **not `verification_missing`:** no wired independent producer-artifact-bridge-consumer chain is evidenced;
- **not `implemented_but_not_orchestrated`:** research design is not an isolated working component;
- **not `semantic_test_missing`:** no implemented chain with structural tests is claimed.

The present finding is **`not_established`** as an evidence verdict, not a new status lattice. Once a real evaluator consumer exists, a missing product trace producer may legitimately be `producer_missing`; once both endpoints exist without orchestration, `bridge_missing`; once a wired chain exists without automated end-to-end proof, `verification_missing`.

### 17.2 Owner placement and the P27/P28 exception

`P27`/`P28` normally require extending a canonical owner and strangling a duplicate. (`policy-engine/docs/reference/policy-design-case-failure-patterns.md:71-72@1a7a2d05ebba22fae80e9934329e4b880806588e`, findings `P27`, `P28`.) `S0-K14` is a deliberate verification exception, not permission for arbitrary duplication:

- product owners retain production semantics and raw observable outputs;
- a thin raw-trace adapter extends the canonical product owner but contains no verdict logic;
- the same-code control `C` may extend existing runtime-quality machinery, diagnostic only;
- public benchmark semantics, `R_v`, `P_v`, `M_v`, `O_v`, and evaluator receipts remain independent by construction;
- the benchmark log records benchmark custody only and cannot become a second product confidence/authority ledger under `INT-K05`.

No final package/repository topology or owner is appointed.

### 17.3 Capability placement summary

| Capability | Placement rule |
|---|---|
| Public spec/input-only corpus | Independent benchmark artifact; product-readable, no product answer generation. |
| Raw trace producer | Narrow extension of canonical product observation owner. |
| `R_v`, `P_v`, `M_v`, `O_v` | Separate repositories/build/access/authoring by construction. |
| Same-code rebuild `C` | Existing product quality owner; diagnostic only. |
| Authority axioms/reviewer records | Independent benchmark-governance evidence; no institutional appointment. |
| Commitment/access/challenge log | Independent benchmark evidence, not a product ledger/status system. |
| Receipt | Evaluator-side bounded evidence, no authority or release mutation. |
| Public challenge display | Later accepted publication surface; must not pre-empt PAO-R36 or create a second correction lattice. |

## 18. Open questions for consolidation

### Engineering

- Smallest raw trace grammar that is expressive enough yet cannot carry a hidden product verdict.
- Transitive provenance enforcement across generated files, containers, services, models, and runtime network calls.
- Required diversity dimensions across `R_v` and `P_v` and evidence that they address the threat model.
- Canonicalization of large unordered/partially ordered traces without erasing duplicates, order, time, or scope semantics.
- Hidden-seed generation, commitment, recovery, rotation, exposure budget, and diagnostic query budget.
- Typed disagreement localization and minimal counterexample production.
- Commitment construction for low-entropy answer spaces and bounded resource/timeout policy under `PV-K06`.

### Institutional

- Existence, mandate, competence, funding, and continuity of a second independent evaluator team.
- Enforceable role incompatibilities among product, evaluator, expectation, custody, run, adjudication, and challenge functions.
- Scope-specific institutional/jurisdictional competence and proficiency renewal.
- Procedural protection of dissent, abstention, challenge, appeal, and minority expertise.
- Key/evidence succession through rotation, compromise, absence, or organizational dissolution.
- Economic/funding conflicts and the body authorized to accept an evaluator release for any later scoring use.

### Additional research

- Correlated semantic error despite separate code and teams.
- Mutation adequacy against held-out real custody-fault families.
- Set-valued outcomes over partially ordered authority/limitation semantics.
- Hidden-fixture discriminating half-life under repeated submissions/challenges.
- Proof-carrying metamorphic relation certificates.
- Drift signals that preserve minority expertise instead of collapsing it to agreement scores.
- Transparency-log witnessing/gossip against equivocation.
- Forensic distinction between coincident identical error and prohibited provenance sharing.

## 19. External primary-source transfer ledger

The architecture is grounded across five mature regimes, with stable identifiers and explicit non-transfer limits:

1. conformity assessment/proficiency testing: ISO/IEC 17043:2023, ILAC P9:01/2024, ISO/IEC 17025:2017, ISO/IEC 17011:2017;
2. metrology/traceability: JCGM 200:2012, DOI `10.59161/JCGM200-2012`, and ILAC P10:07/2020;
3. public audit/separation: GAO-24-106786 and NIST SP 800-53 Rev. 5 control AC-5;
4. sealed assessment: Ofqual General Conditions, Condition G4;
5. software/cryptographic assurance: Avizienis DOI `10.1109/TSE.1985.231893`, Knight–Leveson DOI `10.1109/TSE.1986.6312924`, CMU/SEI-96-TR-022, HKUST-CS98-01, RFC 8785, RFC 9162, and NIST SP 800-57 Part 1 Rev. 5.

The transfer ledger specifies what each contributes and what it cannot establish. In particular: proficiency evidence is not accreditation; byte commitments are not semantic truth; logs are not correctness; separation of duties is not non-collusion; sealed answers are not correct merely because they are secret; N-version diversity does not justify voting; and metrological traceability is an analogy for documented reference chains, not an SI claim.

## 20. Deliverable map

Each commissioned output is an artifact, not merely a heading:

| # | Deliverable | File | Disposition |
|---:|---|---|---|
| 1 | Machine-readable public schema and input-only fixture corpus | [public-schema-and-sealed-expectations.md](s0-gap-02/public-schema-and-sealed-expectations.md) | Research schemas, corpus strata, leakage prohibitions, validators, examples. |
| 2 | Sealed expectation format admitting alternatives | [public-schema-and-sealed-expectations.md](s0-gap-02/public-schema-and-sealed-expectations.md) | Finite set-valued alternatives, mandatory predicates, exclusions, bounded variability/dissent. |
| 3 | Independent evaluator interface and code-independence rules | [independence-model-and-evaluator-interface.md](s0-gap-02/independence-model-and-evaluator-interface.md) | Interfaces, import/provenance/access rules, enforcement gates. |
| 4 | Clean-rebuild reference semantics and equivalence policy | [independence-model-and-evaluator-interface.md](s0-gap-02/independence-model-and-evaluator-interface.md); [public-schema-and-sealed-expectations.md](s0-gap-02/public-schema-and-sealed-expectations.md) | Independent `R_v`; explicit equivalence; same-code `C` diagnostic-only line. |
| 5 | Authority-scenario axioms and human adjudication | [oracle-custody-and-adjudication-protocol.md](s0-gap-02/oracle-custody-and-adjudication-protocol.md) | Scoped axiom records; conflicts, abstention, dissent, disagreement, supersession. |
| 6 | Oracle commitment/custody/access-log/rotation/challenge/supersession | [oracle-custody-and-adjudication-protocol.md](s0-gap-02/oracle-custody-and-adjudication-protocol.md) | Ordered protocol, access schema, key lifecycle, append-only history, challenge. |
| 7 | Adjacent-case/metamorphic generator | [mutation-and-reproducibility.md](s0-gap-02/mutation-and-reproducibility.md) | Mutation families, certificates, hidden-seed/population controls, anti-memorization rules. |
| 8 | Reproducibility receipt and bounded claim | [mutation-and-reproducibility.md](s0-gap-02/mutation-and-reproducibility.md) | Machine-readable receipt and exact `S0-K16` bounded-claim template. |
| 9 | Formal independence model | [independence-model-and-evaluator-interface.md](s0-gap-02/independence-model-and-evaluator-interface.md) | Allowed/prohibited sharing, provenance conditions, assumptions and proofs. |
| 10 | Falsifier suite with six named plus additional attacks | [falsifier-suite.md](s0-gap-02/falsifier-suite.md) | Six commissioned + seven new attacks, exact expected/forbidden outcomes. |
| 11 | Repository integration handoff with prerequisite-evidenced labels | [integration-handoff-and-open-questions.md](s0-gap-02/integration-handoff-and-open-questions.md) | Vocabulary prerequisite table, capability placement, sequence, isolation. |
| 12 | Typed open questions | [integration-handoff-and-open-questions.md](s0-gap-02/integration-handoff-and-open-questions.md) | Engineering, institutional, additional research. |
| 13 | External primary-source and transfer ledger | [external-source-and-transfer-ledger.md](s0-gap-02/external-source-and-transfer-ledger.md) | Stable IDs across five regimes, transfers and non-transfers. |
| Pass I | Orientation and source census ledger | [orientation-ledger.md](s0-gap-02/orientation-ledger.md) | Pin/access method, files-vs-lines-vs-occurrences, concept sample, prior art. |

## 21. Wave-4 isolation

This delivery edits only the primary S0-GAP-02 report and its supporting directory.

- `OPS-R14` retains durability and expiring-rights ownership. Oracle commitment/version continuity here is benchmark evidence custody, not production durability, RPO/RTO, or expiring-rights design.
- `PAO-R36` retains public-correction ownership. Oracle challenge/correction is a benchmark-governance history and does not define a product public-correction feed or status lattice. A later public integration must consume PAO-R36 by name.
- `PAO-R4` retains the individual-decision boundary. This corpus/evaluator makes no individual decision and adds no individual eligibility/remedy semantics.

No artifact owned by those tasks is modified.

## 22. Non-effect and final conclusion

This report authorizes no implementation, owner, evaluator, custodian, panel, vendor, wire/schema/package/database/API contract, authority grant, capability, legal conclusion, benchmark passage, score, or plan amendment. It does not declare `OPS-R15` unblocked. A future implementation must be separately built, staffed, proficiency-tested, challenged, audited, accepted, and read back before any later scoring decision could even be considered.

The research answer is nevertheless decisive: **acceptable custody semantics cannot be established by extending the current product benchmark machinery or by comparing the product with its own clean rebuild.** They can be tested non-circularly only through a public observable-semantic problem definition, sealed finite alternatives, two provenance-diverse answer channels with blocking disagreement, hidden certified mutations, immutable oracle custody, preserved dissent, and a bounded receipt. The architecture constructs that line. The institution required to operate it remains open; therefore the exact result is `accepted_narrow_scope`.
