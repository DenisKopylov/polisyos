---
title: S0-GAP-02 — Independent Custody-Benchmark Oracle and Evaluator Architecture
status: research
kind: research-report
research_task: S0-GAP-02
research_only: true
source_repository: https://github.com/DenisKopylov/polisyos
repository_pin: 109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee
source_tree_equivalent_pin: 1a7a2d05ebba22fae80e9934329e4b880806588e
audited_commit: a7c34cc40b649a10b6878228a8a57acc498f279a
audit_commit: 3abbaf8c2808e31fd7d8f9929b696e78dc91b3d4
amendment_branch: research/s0-gap-02-amendment
amendment_status: audit_amended
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

**`accepted_narrow_scope`, amended after independent audit.**

The architecture family survives: two complementary evaluator channels `R_v` and `P_v` must both pass; disagreement blocks and is never majority-voted away; the same-code rebuild `C` remains outside verification everywhere; expectations remain finite and set-valued; dissent and prior oracle versions remain append-only; `F-04` can still return `ARCHITECTURE_FALSIFIED` against the verifier design itself; and every positive claim remains bounded by `S0-K16`.

The hostile independent audit returned `GO_WITH_REVISIONS` and correctly rejected the original statement that only an institution was missing. This amendment answers the four technical blockers at the **research-contract level**:

1. a shared bad `B` or `O_v` is gated by specification assurance `S_v` and attack `A-14`;
2. common provenance is limited to artifacts for which `AnswerNeutral(z,f)` is constructed, not merely declared;
3. sealed predicates use a finite trace domain and total decidable DSL with proof-producing catch-all checks;
4. every seeded failure is bound to an adequate discriminator witness with liveness, removal and neutralization probes.

It also incorporates the remaining audit revisions: the P37 predicate-provenance register; `M_v`/`J_v`/`R_v`/`P_v` separation; reviewer proficiency; independently reconciled access evidence; role-matrix closure; and a blocking-challenge claim gate.

The amendment does **not** provide the executable evaluators, allowlist gate, compiler, executed probes, proficiency results, independently reconciled logs, accepted role assignment, challenge-closure record, or the second competent independently governed function. Those technical execution premises and the institutional premise remain `not_established`. Architecture delivery is not implementation acceptance, authorizes no scoring, and does not unblock `OPS-R15`.

## 2. Commission, scope and precedence

`S0-GAP-02` is a ratified obligation, not a new proposal. `S0-K14` blocks an independent verification/scoring claim until an oracle and rebuild path are independent of the product’s admission, reducers, dependency traversal, and status projection; the same finding permits a same-code rebuild to establish consistency only. `S0-K13` and `S0-K15` leave observable-semantic benchmark design active, which is why `OPS-R15` can be delivered and audited yet remain unscored. (`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:96-112@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`, findings `S0-K13`–`S0-K16`; `policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:143-202@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`, finding `S0-K14` and commissioning action.)

The full register entry is authoritative on detail. It requires a public schema and input-only corpus, sealed set-valued expectations, independent evaluator interface, clean-rebuild/equivalence policy, authority axioms and human adjudication, oracle custody/challenge/supersession, adjacent/metamorphic generation, and bounded reproducibility receipts, while expressly denying production authorization or scoring effect. (`policy-engine/docs/research/policy-operations/consolidation/stage0/stage0-additional-research-register.md:123-199@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`, entry `S0-GAP-02`.) The present brief adds compatible specificity: a formal independence model, exact falsifiers plus additional attacks, prerequisite-safe integration vocabulary, typed open questions, and an external transfer ledger. No substantive conflict was found; the register wins if one is later discovered.

The architecture is also bounded by:

- `S0-K13`: assess observable custody semantics rather than mandate product internals;
- `S0-K15`: resist memorization and preserve challenge, dissent, and abstention;
- `S0-K16`: any passage is bounded to named artifacts and carries no authority;
- `INT-K05`: do not create a second product confidence/authority ledger;
- `INT-K08`: negative completion is a valid governed result; benchmark-local non-establishment terminals do not create a fourth project outcome-vocabulary element;
- `P37`: every load-bearing gate predicate is classified and frozen at admission, and a declared premise cannot masquerade as machine proof;
- `PV-K06`: an unproved approximation, timeout, empty result, unsupported theory, or incomplete history cannot inherit an acceptable verdict. (`policy-engine/docs/system-design-decisions/int-wave-claim-semantics-ratification.md:157-170@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`, finding `INT-K05`; `policy-engine/docs/system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md:164-182@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`, finding `PV-K06`.)

## 3. Direct answer to the commissioned question

> How can an implementation-independent, machine-readable and challengeable oracle establish acceptable custody semantics while keeping expected results sealed, preserving ambiguity and dissent, preventing shared-code circularity, and resisting fixture memorization?

Use a **dual diverse evaluator architecture with a separate specification-assurance gate**:

1. Freeze public problem definition `B`, a finite trace-domain profile, total decidable predicate DSL, input-only corpus, and public relation catalogue. No expected product actions or labels are visible.
2. Admit common artifacts only through `AnswerNeutral(z,f)`: they may parse, canonicalize, transport, or identify declared inputs, but cannot decide admission, reduction, dependencies/affected sets, status/authority, ambiguity collapse, or expected answers. A machine allowlist, transitive source/SBOM/network evidence, poisoned helpers for every semantic family, and independent review construct—not declare—this property.
3. Commit and seal `O_v`, containing finite explicit alternatives, mandatory positive/negative predicates, exclusions, bounded nonsemantic variability, reviewer records, and unresolved dissent. The PDL-1 compiler proves satisfiability/non-tautology and rejects catch-all alternatives; unknown proof status blocks under `PV-K06`.
4. Evaluate the frozen product trace through two answer-producing channels:
   - `R_v`, an independently authored declarative reducer/reference semantics;
   - `P_v`, an independently authored predicate/invariant/metamorphic evaluator.
   Both must pass. Disagreement blocks; it is never a vote.
5. Retain product same-code control `C` only as a diagnostic consistency channel. It has zero weight in every verification or specification-assurance conjunction.
6. Generate hidden post-freeze cases through `M_v`, and validate mutation certificates through separately governed `J_v`; neither may share a private semantic ancestor with the evaluators that decide the relation.
7. Bind every seeded mutation to a `DiscriminatorWitness`: expected semantic delta, named discriminator, liveness result, removal probe, and neutralization probe. Removing the relevant discriminator makes acceptance fail closed as `EVALUATOR_COVERAGE_NOT_ESTABLISHED`.
8. Maintain `S_v` over public axioms and expectations: independent derivation or dual control, reviewer proficiency/drift evidence, preserved dissent and challenges. A shared bad axiom accepted by both evaluators yields `SPECIFICATION_ASSURANCE_NOT_ESTABLISHED`; the stronger claim is withheld.
9. Freeze every load-bearing premise in a P37 register as `recomputed`, `machine_observed`, `independently_reconciled`, `attested`, `institutionally_accepted`, or `not_established`. A decisive predicate in the last three classes cannot be rendered as machine proof or turn a positive gate green by itself.
10. Bind commitments, storage/network/key-service access heads and reconciliation, roles, challenges, corrections and supersessions into an append-only receipt. A blocking challenge prevents claim rendering.
11. Emit two different statements:
    - when implementation-side evidence passes but `S_v` is not established: **“not refuted under the committed specification”**;
    - only when `S_v` is established as well: the bounded `S0-K16` custody-semantics passage sentence.

`SPECIFICATION_ASSURANCE_NOT_ESTABLISHED`, `INDEPENDENCE_NOT_ESTABLISHED`, and `EVALUATOR_COVERAGE_NOT_ESTABLISHED` are benchmark-local negative-completion/evidence dispositions under `INT-K08`. They are not product statuses and do not add a fourth element to the project outcome vocabulary.

## 4. Pass-I orientation audit

The amended [orientation ledger](s0-gap-02/orientation-ledger.md) records the architect-supplied complete tree walk at the source-equivalent pin.

### 4.1 Denominators and reconciled counts

Path denominator: `policy-engine/src`; case-sensitive fixed-string content matching; path-name matches excluded; binary files excluded. The inherited counts were Python-only matching-file counts whose file-type denominator was unstated.

| Token | Python-only files | All-source files | All-source matching lines | All-source occurrences |
|---|---:|---:|---:|---:|
| `benchmark` | **183** | **197** | **2,000** | **2,319** |
| `evaluator` | **80** | **85** | **444** | **512** |
| `oracle` | **44** | **44** | **323** | **386** |

The original refusal to manufacture these figures from ranked search remains correct under `P35`; the supplied complete walk closes that evidence gap. An index establishes neither a zero nor a positive.

### 4.2 Bounded semantic conclusion

The token census establishes extensive vocabulary, not semantic ownership. The supportable statement is: **no eligible independent custody oracle was established by the complete OPS-R15 evidence chain and the bounded three-owner sample**. It is not a universal proof that no independently implemented oracle exists anywhere under another name.

The concept sample remains denominator 3/3 named runtime-quality owners, 3/3 read, 3/3 unsuitable as the independent verifier. In particular, `grounding_benchmark.py` imports product admission/relation/phrasing/hash logic and exposes expected-answer fields. The OPS-R15 report plus all seven audit artifacts were read—8/8 prior-art artifacts—and already establish visible expected traces and the same-code fault trap.

## 5. What may be shared—and what must never be shared

The full amended boundary is in [the formal independence model](s0-gap-02/independence-model-and-evaluator-interface.md).

### 5.1 `AnswerNeutral(z,f)`

For common artifact `z` and failure family `f`, `AnswerNeutral(z,f)` holds only when committed evidence establishes all of the following:

- `z` only parses, canonicalizes, transports, or identifies declared inputs;
- changing `z` cannot by itself select an expected alternative or decide admission, transition reduction, dependency/affected-set closure, status/authority projection, ambiguity collapse, or expected answer;
- source/generated-file/SBOM/container/service/network provenance is fully enumerated and contains no prohibited semantic ancestor;
- public conformance vectors and a poisoned helper for the named semantic family demonstrate the boundary behavior;
- runtime load/network observations show no undeclared semantic call; and
- an independent review reconciles the declaration with source and behavioral evidence.

Let `A_f = {z in (N union B) | AnswerNeutral(z,f)}`. Only `A_f`, not the whole of `N union B`, may overlap between product and evaluator answer-producing provenance. This is `P37` applied to the neutrality gate.

### 5.2 Legitimately shared inputs

Subject to the gate above, the product and evaluators may share the public problem definition, input-only fixture bytes, opaque identifiers, declared units/types/version IDs, raw trace bytes, scoped expectation bytes after authorized reveal, generic language/OS/cryptographic primitives, deterministic canonicalization and public conformance vectors. Shared bytes are declared inputs, not proof that their semantics are correct.

### 5.3 Never shared for an independent verification claim

`R_v`, `P_v`, `M_v`, and `J_v` may not import, call, generate from, deserialize, fit to, or derive answer logic from product admission/re-admission, reducers, dependency traversal, affected-set computation, status/authority projection, answer-visible fixtures, product gold/adjudication helpers, implementation-visible OPS-R15 expected traces, product-generated semantic tables/models/services, or the same-code control `C`. `M_v` and `J_v` must also be separate from each other and from the evaluator that judges their relation except for the public relation definition and admitted `A_f` substrate.

The prohibition is transitive and behavioral, covering source, generated artifacts, builds, services, network calls, authorship/review derivations and data access. A role label, repository boundary or language difference is not enough.

## 6. Formal independence model and proof

### 6.1 Components

Let `I` be the frozen implementation, `C` its same-code diagnostic, `B` the public specification/finite domain, `O_v` the sealed expectations, `R_v` and `P_v` the two evaluator channels, `M_v` the hidden generator, `J_v` the separate relation validator, `S_v` the specification-assurance record, `H_v` the human/challenge record, `L` the append-only custody log, `N` the candidate neutral substrate, and `A_f` the answer-neutral subset constructed for failure family `f`.

`SemProv_f(X)` includes every transitive answer-producing source, generated table/model, semantic service, dependency, authoring/review derivation, build input and runtime call influencing `X`. `Input_f(X)` is every declared immutable run input. Undeclared access is a provenance violation.

### 6.2 Amended constructed-independence conditions

For named implementation-origin failure families, structural independence requires:

1. product/control intersections with `R_v` and `P_v`, and the R/P intersection, are subsets of `A_f`—not merely `N ∪ B`;
2. `M_v`, `J_v`, `R_v`, and `P_v` share no private semantic relation ancestor outside the public relation definition and `A_f`;
3. no common/public artifact is generated, fitted or selected by observing product behavior, visible expected traces, prior hidden results or private product semantic notes;
4. product/control declared inputs exclude plaintext expectations, hidden seeds before reveal, evaluator internals and adjudication answers;
5. common evaluator inputs are exhaustively enumerated and committed;
6. role assignments enforce product/evaluator/generator/validator/expectation incompatibilities, with independent derivation or dual control for `B`→`O_v`;
7. each failure family has an adequate `DiscriminatorWitness` with semantic delta, liveness, removal and neutralization probes;
8. every load-bearing predicate is frozen in the six-way P37 register with evidence and claim effect;
9. `S_v` separately records whether shared specification/expectation assurance is established for the claimed scope;
10. the receipt binds all provenance, answer-neutrality, access reconciliation, role, proficiency, discriminator, challenge and population evidence.

Conditions involving competence, authorship influence and non-collusion are not mislabelled machine proof. They are `attested`, `institutionally_accepted`, or `not_established` and can only have the predeclared bounded/degrading effect.

### 6.3 Verification and claim rules

For trace `y` on fixture `x`:

```text
W(x,y;v) = r and p and a and d and i and h
V_custody(x,y;v) = W(x,y;v) and s
```

- `r` and `p`: R and P both accept all mandatory explicit relations; no vote;
- `a`: every common artifact satisfies `AnswerNeutral`;
- `d`: every claimed family has a live discriminator witness and removal/neutralization fail closed;
- `i`: provenance, commitment, independently reconciled access, role, population and run integrity hold;
- `h`: raw dissent/conflict/abstention/disagreement is complete and no unresolved blocking challenge exists;
- `s`: `S_v` establishes the scope-specific shared-specification assurance premise;
- `C`: deliberately absent.

If `W=1` but `s` is not established, the only positive evidence sentence is “not refuted under the committed specification.” A shared bad `B`/`O_v` accepted by both evaluators yields `SPECIFICATION_ASSURANCE_NOT_ESTABLISHED` and withholds the stronger passage sentence.

### 6.4 Proof obligations

**Proposition 1—actual scope.** If a product defect's causal artifact lies in `SemProv_f(I union C) minus A_f`, the amended intersection conditions exclude that artifact from both evaluator answer paths. For an artifact inside `A_f`, non-circularity depends on the independently constructed `AnswerNeutral` evidence. The proposition does not prove shared public axioms correct.

**Proposition 2—discriminator adequacy.** A seeded shared product reducer may make `C` agree on the wrong answer. A valid witness makes at least one independent channel fail. Missing/removed/neutralized coverage yields `EVALUATOR_COVERAGE_NOT_ESTABLISHED`, never passage. If both channels accept an intact valid seeded wrong product result, the exact outcome remains `ARCHITECTURE_FALSIFIED`.

**Proposition 3—no voting.** Both conjunctions require R and P. Disagreement blocks and is preserved. Knight–Leveson supports rejection of independence-by-voting; no numeric reliability gain is claimed.

**Proposition 4—bounded ambiguity.** Within the finite enumerated trace domain and total decidable PDL-1 language, the compiler can prove alternative satisfiability, discriminator non-tautology and non-catch-all coverage. Unknown proof status blocks under `PV-K06`.

**Proposition 5—specification-side fault.** `A-14` supplies a false shared axiom correctly implemented by I, R and P. Implementation-side `W` may pass, but `S_v` fails; `V_custody=0`, the stronger claim is withheld, and the negative completion is `SPECIFICATION_ASSURANCE_NOT_ESTABLISHED`.

These propositions establish conditional structural separation and claim discipline. They do not establish legal correctness, evaluator competence, non-collusion or a reliability probability.

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

 B + finite domain + PDL-1 + public relations
                  |
 public inputs --> frozen product I --> raw trace T --> C same-code control
                  |                                  (diagnostic only)
                  |
       AnswerNeutral / P37 admission boundary
                  |
 ---------------- commitment / access boundary ----------------
                  |
        O_v sealed finite alternatives and dissent
        M_v hidden mutations --> J_v relation validation
                  |                    |
             +----+--------------------+----+
             |                              |
      R_v declarative reducer        P_v predicates/metamorphic
      separate provenance            separate provenance
             |                              |
             +--------------+---------------+
                            |
                  W = r ∧ p ∧ a ∧ d ∧ i ∧ h
                            |
                  S_v specification assurance
                            |
                  V_custody = W ∧ s
                            |
                bounded receipt / claim gate
                            |
 L: commitments, reconciled access heads, roles, proficiency, raw dissent,
    blocking challenges, corrections, supersessions and witnesses
```

`C` is deliberately outside `W` and `V_custody`. `M_v` and `J_v` are not part of either evaluator's private answer path. `S_v` is not a third evaluator vote; it gates the stronger claim against shared public-axiom/expectation failure.

### 8.1 Component import and provenance rules

| Component | May import/read | Must not import/read/share |
|---|---|---|
| Product `I` | Public `B`, public inputs, product code and admitted `A_f` substrate | Plaintext `O_v`, hidden seed before reveal, evaluator/generator/validator source, adjudication answers |
| Product control `C` | Product code and raw inputs | Any role in `W`/`V_custody`; any independent-verification label |
| Trace adapter | Product raw observations and admitted answer-neutral DTO/canonicalization | Acceptance logic, expected labels, dependency/status/authority mappings or ambiguity collapse |
| `R_v` | `B`, committed inputs, raw trace, scoped `O_v`, admitted `A_f` | Product answer semantics, product gold/adjudication logic, `P_v` private derivation, M/J private semantic tables |
| `P_v` | Same declared run bytes and admitted `A_f` | Product answer semantics, `R_v` private derivation, M/J private semantic tables, product gold labels |
| `M_v` | Public mutation grammar, finite domain, public relation definitions, hidden seed | Product behavior-derived selection, R/P answer code, private relation table shared with `J_v` or deciding evaluator |
| `J_v` | Public relation definition, mutation certificate, admitted `A_f` | Generator-private relation implementation, product semantics, R/P private answer path |
| `O_v` compiler/custody | Approved `B`, PDL-1 compiler, independent/dual-control reviewer records | Product-output-driven edits after freeze, general predicate execution, unlogged plaintext export |
| `S_v` | Specification derivation, proficiency, dissent, challenge and scope evidence | Product passage inference, majority-vote substitution, self-attested machine-proof labels |
| Receipt/log verifier | Committed artifacts, raw results, role/access/proficiency/challenge evidence | Authority inference, product status mutation, silent correction or challenge suppression |

### 8.2 Enforcement—not promises

A later implementation must produce committed evidence for:

- a machine-enforced allowlist whose common members each carry `AnswerNeutral(z,f)` evidence;
- transitive source/generated-file/SBOM/container/model/service/network provenance;
- poisoned “neutral helper” probes for every semantic family and the falsify-the-declaration probe;
- isolated identities/build roots for `R_v`, `P_v`, `M_v`, and `J_v`, with role-window validation and `B`→`O_v` independent derivation or dual control;
- `DiscriminatorWitness` records and successful liveness/removal/neutralization probes for every claimed family;
- a proof-producing finite-domain PDL-1 compiler that rejects the audit catch-all and blocks on unknown/timeout/unsupported theory;
- blinded reviewer proficiency and drift evidence, including A-16;
- storage/network/key-service heads and an independently reconciled access disposition;
- challenge classification and `no_unresolved_blocking_challenge=true` before passage rendering;
- all attacks `F-01`–`F-06` and `A-07`–`A-21`, including A-14 specification-side failure and A-15 private relation ancestry.

Organizational separation or prose saying “enforced” is not execution evidence.

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

The complete amended format and decision procedure are in [public schema and sealed expectations](s0-gap-02/public-schema-and-sealed-expectations.md).

### 10.1 Chosen executable model

This amendment chooses a **finite enumerated trace domain plus total decidable predicate DSL**, `S0-GAP-02-PDL-1`. General code, regex engines with unbounded behavior, external calls, reflection, user-defined recursion and unsupported theories are forbidden in expectation predicates. Every variable ranges over an enumerated finite domain, bounded integer interval, finite set, finite event/edge collection or explicitly bounded partial order.

For each bundle version, a proof-producing compiler records:

- domain and predicate-language versions/digests;
- parse/type/totality results;
- SAT/UNSAT and TAUT/NOT_TAUT certificates for each predicate;
- satisfiability of every alternative;
- non-tautology of every mandatory positive discriminator;
- satisfiable, non-tautological forbidden boundaries;
- an exhaustive or symbolically complete proof that the union of alternatives does not cover the entire admitted trace domain;
- resource bounds and exact unknown/timeout/unsupported disposition.

Unknown, timeout or unsupported theory blocks under `PV-K06`; it never inherits acceptance.

### 10.2 Bundle shape and acceptance

```yaml
SealedExpectation:
  fixture_digest: digest
  finite_trace_domain_version: version
  predicate_language: S0-GAP-02-PDL-1
  predicate_compiler_digest: digest
  predicate_proof_bundle_digest: digest
  specification_assurance_digest: digest
  alternatives:
    - alternative_id: opaque
      mandatory_positive_predicates: [predicate]
      mandatory_negative_predicates: [predicate]
      allowed_partial_order: [constraint]
      required_effect_set_relation: relation
      required_authority_limitations: [limitation]
      may_vary: [named bounded nonsemantic dimension]
  cross_alternative_predicates: [predicate]
  exclusions: [predicate]
  ambiguity_basis: genuine_semantic_ambiguity | unresolved_dissent | bounded_nondeterminism
  reviewer_records_root: digest
  unresolved_positions: [digest]
  expectation_version: immutable version
```

```text
Compatible(x,y) =
  y is a member of the admitted finite trace domain
  and exactly the PDL-1 decision procedure terminates
  and some explicit satisfiable alternative matches y
  and all cross-alternative predicates hold
  and no exclusion holds
  and every varied field is authorized by a named bounded rule
```

### 10.3 Catch-all rejection fixture

The audit's bundle is a committed negative validator case:

```yaml
alternatives:
  - alternative_id: universal
    mandatory_positive_predicates:
      - "event_count >= 0"
    mandatory_negative_predicates:
      - "event_type == 'x' and event_type != 'x'"
    may_vary: []
```

It must be rejected before a product run because the positive predicate is tautological, the negative boundary is unsatisfiable, and the alternative covers the admitted domain. Exact validator findings are `POSITIVE_DISCRIMINATOR_TAUTOLOGY`, `NEGATIVE_BOUNDARY_UNSATISFIABLE`, and `CATCH_ALL_ALTERNATIVE`.

Finite alternatives, explicit exclusions and bounded `may_vary` therefore remain; the fix does not trade away genuine ambiguity. Unresolved dissent remains an explicit blocking record and is never resolved merely to create a score.

## 11. Clean rebuild, reference semantics and equivalence policy

Two “clean” concepts must remain distinct:

1. **Independent reference reconstruction (`R_v`).** `R_v` starts from public/hidden fixture inputs, public axioms, and raw observations in an isolated clean environment. It recomputes the expected semantic relations through a separately authored declarative model. It may establish an independent verification predicate when all provenance conditions hold.
2. **Product same-code clean rebuild (`C`).** `C` reruns the product’s own semantic code from a clean store/build. It may establish internal consistency or diagnose incremental drift. It cannot establish independent correctness, cannot replace `R_v` or `P_v`, and cannot contribute to `W` or `V_custody`.

The equivalence policy is explicit per field/relation:

- canonical byte equality for immutable deterministic scalar fields;
- set equality for declared unordered collections, while separately checking duplicates/cardinality;
- graph isomorphism only for declared opaque identifier renaming, with semantic labels/edges preserved;
- partial-order equivalence where concurrency is genuinely permitted;
- finite alternative membership for genuine semantic ambiguity;
- monotonic or relational predicates for authority limitation, append-only history, affected-set conservation, and metamorphic transforms;
- no tolerance band or approximate match unless predeclared, justified, bounded, and incapable of weakening authority/status semantics.

An equivalence relation is public, versioned, independently tested, and cannot be invented after a failure. An unproved approximation receives a blocking/not-established result under `PV-K06`.

## 12. Authority-scenario axioms, specification assurance and human adjudication

The full amended protocol is in [oracle custody and adjudication](s0-gap-02/oracle-custody-and-adjudication-protocol.md).

### 12.1 Axiom and expectation derivation

Each fixture-local axiom records stable identity/version/digest, jurisdiction/institution/role/period/scope, source and limitations, machine form where feasible, contestability/uncertainty, authors/reviewers/competence/conflicts/abstentions/dissent/signatures, and supersession links. These are benchmark assumptions, not universal legal truth or an authority grant.

The `B`→`O_v` step requires independent derivation or dual control. A scenario author cannot be the sole expectation author and sole reviewer for the same semantic premise in one evaluation window. The role validator rejects forbidden combinations before access to product output.

### 12.2 Specification assurance `S_v`

`S_v` binds:

- public axiom and expectation versions;
- derivation/review independence or dual-control receipts;
- scope-specific competence/mandate evidence, correctly classified as institutional rather than machine proof;
- blinded reviewer proficiency anchors and drift checks;
- all raw positions, minority rationales, abstentions, recusals and challenges;
- the claim scope and exact effect when assurance is not established.

Unanimity is not sufficient. Attack `A-16` seeds a premise defect that every otherwise competent reviewer misses; without a passed scoped proficiency anchor the exact negative completion is `SPECIFICATION_ASSURANCE_NOT_ESTABLISHED` and the stronger claim is withheld.

### 12.3 Adjudication protocol

1. Reviewers submit signed support, dissent, abstention, conflict/recusal or out-of-scope positions independently.
2. Raw positions and proficiency status are committed before aggregation; no record is overwritten.
3. `R_v`/`P_v` or reviewer disagreement is localized to fixture, axiom, expectation, compiler/domain, parser/canonicalization, reducer, predicate, mutation relation, product trace, access/integrity or challenge state.
4. A minimal counterexample and every affected version/run are recorded.
5. Adjudication may affirm a version, challenge a run or propose a new superseding fixture/axiom/expectation/evaluator version. It may not mutate an old version.
6. Abstention is not support; recusal is not absence; dissent is not averaged away; unresolved material disagreement blocks the affected claim.
7. Blocking challenge classes are predeclared. `no_unresolved_blocking_challenge` is part of `h` and of the human-readable claim gate.
8. Every rationale, minority view, evidence link, conflict and appeal remains retrievable.

No reviewer panel, competence authority or institution is appointed by this report.

## 13. Commitment, custody, access, rotation, challenge and supersession

The oracle is itself a custody subject. The full protocol is in [oracle custody and adjudication](s0-gap-02/oracle-custody-and-adjudication-protocol.md).

### 13.1 Amended run order

1. publish/freeze `B`, the finite domain, PDL-1, public relation catalogue and corpus commitments;
2. freeze the P37 predicate-provenance register;
3. accept `AnswerNeutral`, provenance, role-window and discriminator-adequacy evidence;
4. accept and commit `R_v`, `P_v`, `M_v`, `J_v`, compiler and `S_v` versions;
5. commit sealed `O_v`, reviewer/proficiency roots and independent/dual-control derivation evidence;
6. freeze product revision/environment/submission/trace adapter;
7. generate/commit hidden seed and full population manifest;
8. execute product and diagnostic-only `C`;
9. evaluate through R/P and validate mutation relations through J;
10. reconcile oracle log with storage, network and key-service heads;
11. commit raw evaluator/human/specification-assurance results and challenge state;
12. render the evidence-only or stronger bounded claim according to `W`, `s`, and blocking-challenge status;
13. append challenges, corrections and supersessions without rewriting any prior entry.

### 13.2 Role separation and common-origin closure

Roles include specification/scenario author, public corpus curator, expectation author, specification reviewer, plaintext custodian, R/P authors and releasers, M author, J validator, proficiency administrator, product author, submission freezer, run operator, adjudicator, challenge receiver and log witness. A `RoleAssignmentWindow` validator rejects incompatible combinations before output access. The `B`→`O_v` step uses independent derivation or dual control; M/J/P/R private semantic ancestry is separately checked. Exceptions are signed and independently reviewed but cannot override a prohibited same-window combination.

### 13.3 Access evidence and reconciliation

Each access event records actor, role, purpose, object digest/version, operation, time, authorization, result and prior/current log heads. A log's silence is not proof of no access. The receipt therefore binds:

- oracle access-log head;
- storage audit head;
- network/egress audit head;
- key-service audit head; and
- an independent reconciliation record with coverage, gaps and disposition.

Inconsistent/tampered heads produce `RUN_INVALID`. An unresolved completeness gap affecting secrecy/provenance produces `INDEPENDENCE_NOT_ESTABLISHED`; no positive claim may treat the absent event as exculpatory.

### 13.4 Commitments, rotation and compromise

Canonical bytes use a public profile and cross-language vectors; originals are retained. Domain-separated commitments bind object kind/version, digest/canonicalization, salt/key ID and ciphertext/content digest. Inclusion/consistency proofs are externally witnessed. Rotation preserves historical verification and cannot reset access history. Compromise creates a signed incident, scope assessment, affected-run challenges, replacement keys and supersession links. No vendor, KMS or final algorithm suite is selected.

### 13.5 Challenge, correction and supersession

Challenges identify artifact/run, grounds, evidence, requested remedy, standing/disclosure and conflicts. Blocking classes include independence/provenance, expectation leakage, specification assurance, population/denominator integrity, evaluator coverage, access reconciliation, oracle-history substitution and discarded dissent. A receipt with any unresolved blocking challenge cannot render the `S0-K16` passage sentence.

A correction creates a new immutable version and supersession edge. A prior receipt remains bound to the exact expectation/evaluator/fixture/specification-assurance versions used. Displays may show later challenge/supersession but never silently rescore history. Digest mismatch against a prior receipt remains a detectable `RUN_INVALID` and oracle-history violation under retained verification evidence.

## 14. Adjacent-case and metamorphic anti-memorization layer

The amended generator, relation validator and receipt are specified in [mutation and reproducibility](s0-gap-02/mutation-and-reproducibility.md).

A mutation family binds:

```text
MR = (precondition, finite-domain input transform tau, expected output relation rho,
      expected semantic delta, exclusions, public relation version, reviewer records)
```

`M_v` produces source/follow-up pairs only when the precondition holds. `J_v`, separately governed from `M_v`, validates the certificate against the public relation language. The deciding evaluator cannot share a private relation table, prompt, generated transform, model or service with either M or J. `A-15` seeds a shared bad relation table and requires rejection before product scoring.

Required families retain the original anti-memorization coverage: opaque-ID renaming, irrelevant metadata, declared-nonsemantic ordering, duplicate/retry, partial-order interleavings, adjacent threshold cases, authority-only invalidation with stable payload, dependency changes, correction/replay, tenant/scope isolation, ambiguity/dissent, asymmetric recovery, external-act substitutions, hidden dependencies and canonicalization variants.

Every mutation certificate also identifies its bound `DiscriminatorWitness`: expected semantic delta, named R/P discriminator, liveness result, removal result and neutralization result. An invalid certificate is `TEST_SETUP_INVALID`; missing or ineffective coverage is `EVALUATOR_COVERAGE_NOT_ESTABLISHED`; neither is a product failure or passage.

Population controls remain prospective: product freeze before hidden-seed generation; seed/population commitments before execution; retained invalid/omitted cases and denominators; predeclared submission/query budgets; and versioned retirement after exposure. Static visible-fixture success is never enough.

## 15. Reproducibility receipt and bounded claim

The receipt binds at minimum:

- product repository/revision/build/environment/configuration/resource limits;
- public `B`, finite-domain and PDL-1/compiler/proof-bundle digests;
- public and hidden population manifests, denominators and raw trace;
- `R_v`, `P_v`, `M_v`, `J_v`, `O_v`, `S_v` and canonicalization/provenance-policy versions;
- same-code `C` result labelled diagnostic/control-only;
- P37 predicate-provenance register and evidence digests;
- `AnswerNeutral` allowlist, transitive source/SBOM/network evidence and poisoned-helper results;
- all `DiscriminatorWitness` liveness/removal/neutralization results;
- role-assignment-window validation and `B`→`O_v` derivation/dual-control evidence;
- reviewer proficiency/drift, raw dissent/conflict/abstention/recusal and evaluator disagreement;
- oracle/storage/network/key-service heads plus independent access reconciliation;
- blocking/nonblocking challenges and `no_unresolved_blocking_challenge`;
- correction/supersession links, compiler unknown/timeout/unsupported records and all falsifier results.

`C` is absent from every claim predicate.

### 15.1 Evidence-only statement when specification assurance is not established

When `W=1` but `S_v` is not established, the receipt may say only:

> For the named implementation artifact, repository revision, environment, committed population, evaluator releases and tested predicates, the implementation was **not refuted under the committed specification** by the recorded implementation-side evidence. Specification assurance for the shared public axioms/expectations was not established; no custody-semantics passage claim is made.

### 15.2 Stronger bounded `S0-K16` claim

The stronger sentence may render only when `V_custody=1` and `no_unresolved_blocking_challenge=true`:

> For implementation artifact `<digest>` at repository revision `<revision>`, executed in environment `<environment-digest>` against committed population `<population-digest>` containing `<valid-count>` valid cases, evaluator releases `<R-digest>` and `<P-digest>`, expectation `<O-digest>`, generator/validator `<M-digest>/<J-digest>`, specification-assurance record `<S-digest>`, and predicate/domain/compiler versions `<catalog-digest>` produced the recorded compatible results; the answer-neutrality, discriminator-adequacy, provenance, commitment, access-reconciliation, population, role, proficiency, dissent, blocking-challenge and log-integrity predicates bound by receipt `<receipt-digest>` were satisfied. This statement applies only to those artifacts, cases, relations and conditions. It carries no authority, legal sufficiency, production capability, future-behavior, completeness, OPS-R15 score or unblocking claim.

Any missing or indeterminate bound withholds the stronger sentence. `SPECIFICATION_ASSURANCE_NOT_ESTABLISHED`, `INDEPENDENCE_NOT_ESTABLISHED`, and `EVALUATOR_COVERAGE_NOT_ESTABLISHED` are valid negative completions under `INT-K08`, not new project outcome-vocabulary elements.

## 16. Falsifier suite

[The amended executable research specification](s0-gap-02/falsifier-suite.md) contains the six commissioned cases plus `A-07`–`A-21`. Harness outcomes are benchmark-local evidence assertions, not product statuses or a new outcome vocabulary.

| ID/family | Attack | Required result |
|---|---|---|
| `F-01` | Product admission/reducer/dependency/status semantics enter R or P directly/transitively. | Provenance violation; `RUN_INVALID`; no semantic aggregation. |
| `F-02` | Implementation-visible answers/labels leak. | Leak channels named; affected runs invalid/challenged. |
| `F-03` | ID-renumbered/adjacent case changes without certified semantic reason. | Relation violation; verification blocked. |
| `F-04` | Product incremental and clean rebuild share a wrong reducer. | `C=CONTROL_ONLY_PASS`; independent discriminator fails. If both R/P accept an intact valid seeded wrong result, exactly `ARCHITECTURE_FALSIFIED`. Removing/neutralizing coverage yields `EVALUATOR_COVERAGE_NOT_ESTABLISHED`, never passage. |
| `F-05` | Corrected expectation silently substitutes into a prior receipt. | Digest/history violation; old receipt remains bound; `RUN_INVALID`. |
| `F-06` | Conflict, dissent, abstention, recusal or evaluator disagreement is discarded. | Record-completeness failure; claim blocked/invalid. |
| `A-07`–`A-13` | Generated-artifact laundering, poisoned neutral helper, parser split, denominator selection, adaptive probing, log split view, declared private ancestor. | Exact provenance/population/log invalidation; no voting or post-hoc repair. |
| `A-14` | False shared public axiom/expectation correctly implemented by I, R and P. | Implementation may be not-refuted; stronger claim withheld; exact `SPECIFICATION_ASSURANCE_NOT_ESTABLISHED`. |
| `A-15` | M/J/P/R share a private bad relation table. | `MUTATION_PROVENANCE_VIOLATION`; rejected before product scoring. |
| `A-16` | Competent unanimous reviewers share one seeded misconception. | Failed/missing proficiency; `SPECIFICATION_ASSURANCE_NOT_ESTABLISHED`. |
| `A-17` | Private common ancestor omitted from declarations. | Independent source/build/network forensics and poisoned-table probe; unresolved gap invalidates/withholds independence. |
| `A-18` | Tautological-positive/unsatisfiable-negative catch-all bundle. | Compiler rejects before run with the three named PDL-1 findings. |
| `A-19` | Oracle access log omits a read while external heads disagree or are incomplete. | Inconsistency `RUN_INVALID`; unresolved completeness `INDEPENDENCE_NOT_ESTABLISHED`. |
| `A-20` | Forbidden scenario/expectation/M/J/R/P role combination. | Role-window validator rejects before output access. |
| `A-21` | Receipt has an unresolved blocking challenge. | `h=0`; `S0-K16` passage sentence cannot render. |

`F-04` remains the dispositive self-directed product-side test. `A-14` is the separate specification-side test and prevents implementation-code independence from being misreported as acceptable custody semantics.

## 17. Repository integration handoff

The full amended handoff is in [integration handoff](s0-gap-02/integration-handoff-and-open-questions.md).

### 17.1 Capability honesty

The current implementation state remains **`not_established`** as an evidence verdict. It is not `producer_missing`, `bridge_missing`, or `verification_missing`, because no accepted independent consumer, both endpoints, or wired chain is evidenced. The handoff records the exact prerequisite and safe transition order for each repository label.

The complete token census supports only vocabulary density. The bounded repository statement is: no eligible independent custody oracle was established by the OPS-R15 evidence chain and 3/3 named-owner sample. No universal source-tree absence is claimed.

### 17.2 P27/P28, S0-K14 and P37

- product owners retain product facts, raw observations and diagnostic `C`;
- a thin raw-trace adapter extends the canonical producer but contains no verdict mapping;
- answer-producing `R_v` and `P_v`, sealed `O_v`, generator `M_v`, relation validator `J_v`, specification assurance `S_v` and evaluator receipts remain independent by the explicit S0-K14 verification exception;
- the exception does not authorize a second product ledger, runtime state machine, domain semantic owner or status lattice;
- every common artifact and every adequacy/competence/access/challenge premise is admitted through the frozen P37 predicate-provenance register rather than by declaration;
- the benchmark log remains benchmark custody evidence only and cannot become a product confidence/authority ledger under `INT-K05`.

### 17.3 Placement summary

| Capability | Placement rule |
|---|---|
| Public `B`, finite domain, PDL-1, input-only corpus | Independent benchmark artifact; product-readable; no product answer generation. |
| Raw trace producer | Narrow extension of canonical product observation owner. |
| Common `N` | Shared only after `AnswerNeutral(z,f)` construction and P37 admission. |
| `R_v`, `P_v`, `M_v`, `J_v`, `O_v` | Separate source/build/access/authoring and private semantic provenance by construction. |
| `S_v` / proficiency / role validation | Independently governed evidence; no institution appointed. |
| `C` | Existing product quality owner; diagnostic only and absent from claims. |
| Access/challenge/supersession log | Independent benchmark evidence with external reconciliation; not a product ledger/status system. |
| Receipt | Bounded evidence and claim gate; no authority or release mutation. |
| Public challenge display | Later accepted publication surface; must not pre-empt PAO-R36 or create a rival correction lattice. |

## 18. Open questions for consolidation

### Engineering

- Execution and maintenance of the machine-enforced `AnswerNeutral` allowlist across source, generated files, SBOMs, containers, services and runtime calls.
- Proof-producing implementation and resource bounds of the finite-domain PDL-1 compiler.
- Prospective discriminator-adequacy maintenance and remove/neutralize behavior as failure families evolve.
- Independent `M_v`/`J_v` relation validation and detection of undeclared private semantic ancestry.
- Smallest raw trace grammar that is expressive enough yet cannot carry a hidden verdict.
- Storage/network/key-service audit-head reconciliation and exact invalid/not-established boundary.
- Hidden-seed generation, commitment, recovery, rotation and exposure/query budgets.
- Typed disagreement localization and minimal counterexample production.

### Institutional

- Existence, mandate, competence, funding and continuity of the second competent independent function.
- Independent derivation or dual control for `B`→`O_v` and enforceable same-window role incompatibilities.
- Administration of blinded reviewer proficiency/drift cases without leaking them.
- Scope-specific institutional/jurisdictional competence and the effect of non-establishment.
- Procedural protection of dissent, abstention, challenge, appeal and minority expertise.
- Key/evidence succession and economic/funding conflicts.
- The body, if any, authorized later to accept an evaluator release; this report appoints none.

### Additional research

- Bounded assurance over shared public axioms/expectations and correlated semantic error despite separate code.
- Mutation adequacy against held-out real custody-fault families.
- Set-valued outcomes over partially ordered authority/limitation semantics.
- Hidden-fixture discriminating half-life under repeated submissions/challenges.
- Proof-carrying metamorphic relation certificates with diverse checkers.
- Drift signals preserving minority expertise rather than collapsing it to agreement.
- Transparency-log witnessing/gossip and provenance forensics for omitted private ancestors.

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
| 2 | Sealed expectation format admitting alternatives | [public-schema-and-sealed-expectations.md](s0-gap-02/public-schema-and-sealed-expectations.md) | Finite alternatives plus finite domain, total decidable PDL-1, proof certificates and catch-all rejection. |
| 3 | Independent evaluator interface and code-independence rules | [independence-model-and-evaluator-interface.md](s0-gap-02/independence-model-and-evaluator-interface.md) | `AnswerNeutral`, P37 register, R/P/M/J separation, discriminator witnesses and claim rules. |
| 4 | Clean-rebuild reference semantics and equivalence policy | [independence-model-and-evaluator-interface.md](s0-gap-02/independence-model-and-evaluator-interface.md); [public-schema-and-sealed-expectations.md](s0-gap-02/public-schema-and-sealed-expectations.md) | Independent `R_v`; explicit equivalence; same-code `C` diagnostic-only line. |
| 5 | Authority-scenario axioms and human adjudication | [oracle-custody-and-adjudication-protocol.md](s0-gap-02/oracle-custody-and-adjudication-protocol.md) | Scoped axioms, `S_v`, independent/dual-control derivation, proficiency, dissent and role validation. |
| 6 | Oracle commitment/custody/access-log/rotation/challenge/supersession | [oracle-custody-and-adjudication-protocol.md](s0-gap-02/oracle-custody-and-adjudication-protocol.md) | Ordered protocol, externally reconciled audit heads, key lifecycle, blocking challenges and append-only supersession. |
| 7 | Adjacent-case/metamorphic generator | [mutation-and-reproducibility.md](s0-gap-02/mutation-and-reproducibility.md) | `M_v`/`J_v` separation, mutation certificates, discriminator witnesses and hidden-population controls. |
| 8 | Reproducibility receipt and bounded claim | [mutation-and-reproducibility.md](s0-gap-02/mutation-and-reproducibility.md) | Evidence-only not-refuted sentence, stronger `S0-K16` gate, access/proficiency/role/challenge bindings. |
| 9 | Formal independence model | [independence-model-and-evaluator-interface.md](s0-gap-02/independence-model-and-evaluator-interface.md) | Allowed/prohibited sharing, provenance conditions, assumptions and proofs. |
| 10 | Falsifier suite with six named plus additional attacks | [falsifier-suite.md](s0-gap-02/falsifier-suite.md) | Six commissioned + fifteen attacks (`A-07`–`A-21`), including specification, generator, reviewer, access, role and challenge cases. |
| 11 | Repository integration handoff with prerequisite-evidenced labels | [integration-handoff-and-open-questions.md](s0-gap-02/integration-handoff-and-open-questions.md) | Vocabulary prerequisite table, capability placement, sequence, isolation. |
| 12 | Typed open questions | [integration-handoff-and-open-questions.md](s0-gap-02/integration-handoff-and-open-questions.md) | Engineering, institutional, additional research. |
| 13 | External primary-source and transfer ledger | [external-source-and-transfer-ledger.md](s0-gap-02/external-source-and-transfer-ledger.md) | Stable IDs across five regimes, transfers and non-transfers. |
| Pass I | Orientation and source census ledger | [orientation-ledger.md](s0-gap-02/orientation-ledger.md) | Reconciled Python/all-source/line/occurrence denominators, bounded concept sample and prior art. |
| Amendment | Audit-finding disposition and execution ledger | [amendment-ledger.md](s0-gap-02/amendment-ledger.md) | All audit findings, R1–R15 changes and committed evidence locations. |

## 21. Wave-4 isolation

This delivery edits only the primary S0-GAP-02 report and its supporting directory.

- `OPS-R14` retains durability and expiring-rights ownership. Oracle commitment/version continuity here is benchmark evidence custody, not production durability, RPO/RTO, or expiring-rights design.
- `PAO-R36` retains public-correction ownership. Oracle challenge/correction is a benchmark-governance history and does not define a product public-correction feed or status lattice. A later public integration must consume PAO-R36 by name.
- `PAO-R4` retains the individual-decision boundary. This corpus/evaluator makes no individual decision and adds no individual eligibility/remedy semantics.

No artifact owned by those tasks is modified.

## 22. Non-effect and final conclusion

This report authorizes no implementation, owner, evaluator, custodian, panel, vendor, wire/schema/package/database/API contract, authority grant, capability, legal conclusion, benchmark passage, score or plan amendment. It does not declare `OPS-R15` unblocked or scorable. A future implementation must separately provide and reproduce every R1–R11 evidence item and must still establish the second competent independent function.

The research answer is now more precise. Product-code circularity cannot be cured by extending current benchmark machinery or by comparing the product with its own clean rebuild. It requires `R_v` and `P_v` as blocking diverse channels, `C` outside verification, hidden certified mutations, append-only oracle custody, preserved dissent and bounded receipts. But implementation independence alone also cannot establish acceptable custody semantics when `B` or `O_v` is wrong. The stronger claim additionally requires answer-neutral common provenance, a decidable expectation language, adequate discriminators, `S_v` specification assurance, reviewer proficiency, independently reconciled access evidence, compatible roles and no unresolved blocking challenge.

Those fixes are specified here but not operationally evidenced. The institution required to operate them also remains absent. Therefore the exact standing remains **`accepted_narrow_scope`**, with technical execution dependencies and an institutional dependency—not an “institution only” rationale.
