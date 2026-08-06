---
title: S0-GAP-02 — Repository integration handoff and typed open questions
status: research
research_only: true
repository_pin: 1a7a2d05ebba22fae80e9934329e4b880806588e
result_standing: accepted_narrow_scope
authoritative_for:
  - research-only integration boundary for a future independent custody benchmark
  - prerequisite-safe use of the repository missing-state vocabulary
  - typed open questions for consolidation
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

# Repository integration handoff and typed open questions

## 1. Handoff standing

This handoff describes where a future implementation would attach and where it must remain separate. It does not authorize that implementation. At commit `1a7a2d05ebba22fae80e9934329e4b880806588e`, no implementation-independent custody-verification chain was established by the exact-ref evidence gathered for S0-GAP-02. The repository has substantial in-tree benchmark machinery, but the three named runtime-quality owners are product-coupled or answer-visible, and the inspected import policy constructs no independently governed evaluator root. (`policy-engine/src/polisyos/runtime/quality/policy_benchmarking.py:1-70@1a7a2d05ebba22fae80e9934329e4b880806588e`; `policy-engine/src/polisyos/runtime/quality/grounding_benchmark.py:1-140@1a7a2d05ebba22fae80e9934329e4b880806588e`; `policy-engine/src/polisyos/runtime/quality/semantic_fixtures.py:1-150@1a7a2d05ebba22fae80e9934329e4b880806588e`; `policy-engine/architecture/imports/policy.toml:1-132@1a7a2d05ebba22fae80e9934329e4b880806588e`.)

The correct present-tense result is therefore **`not_established`**, used here as an evidentiary conclusion rather than as a new repository status. It is deliberately not replaced by `producer_missing`, `bridge_missing`, or `verification_missing`, because the prerequisites for those labels are not yet evidenced.

## 2. Missing-state vocabulary: prerequisites before labels

The repository defines a full capability as contract/artifact, producer, persisted artifact/event, bridge, consumer, verification, surface or explicit out-of-scope rationale, and negative end-to-end semantic test. It defines each missing-state label by the part of that already-existing chain that is absent. (`AGENTS.md:13-37@1a7a2d05ebba22fae80e9934329e4b880806588e`; `policy-engine/docs/reference/policy-design-case-failure-patterns.md:15-45@1a7a2d05ebba22fae80e9934329e4b880806588e`, capability reality check.)

| Repository label | Prerequisite that must already be evidenced | Evidence required before using the label | S0-GAP-02 present use |
|---|---|---|---|
| `contract_only` | A real type/schema/status exists in the implementation surface, while producer, consumer, and workflow do not use it. | Exact contract path plus absence or non-use evidence for producer, consumer, and workflow. | **Not used.** These Markdown sketches are research interfaces, not implementation contracts. |
| `producer_missing` | A named, existing consumer expects a specific event or artifact. | Consumer path and its expected input contract, plus complete producer census showing none emits it. | **Not used.** No accepted independent evaluator consumer was evidenced at the pin. |
| `artifact_missing` | Producer logic exists for a defined artifact/event. | Producer path and execution evidence, plus persistence/query/replay absence. | **Not used.** No future oracle producer is claimed to exist. |
| `bridge_missing` | Both named endpoints already exist: a producer emits and a consumer reads the same bounded artifact. | Producer, artifact, consumer, and missing orchestration evidence. | **Not used.** The independent evaluator endpoints do not yet exist as accepted implementations. |
| `consumer_missing` | An artifact/event is already produced and persisted. | Producer and persistence/readback evidence plus complete consumer census. | **Not used.** No sealed oracle artifact chain is claimed. |
| `verification_missing` | The complete producer-artifact-bridge-consumer chain is wired. | Executed chain evidence plus absence of automated end-to-end verification. | **Not used.** Calling the current condition `verification_missing` would falsely presuppose a wired independent chain. |
| `implemented_but_not_orchestrated` | A component actually works in isolation. | Executable component evidence and absence from runtime orchestration. | **Not used for S0-GAP-02 components.** Research design is not isolated implementation. |
| `surface_missing` | Internal capability exists and works. | Internal chain evidence plus absent API/dashboard/audit/export/public surface. | **Not used.** No internal independent capability is established. |
| `surface_out_of_scope` | Internal capability exists, and omission of an external surface is intentional. | Internal chain evidence, rationale, and accountable owner. | **Not used.** Neither capability nor owner is appointed here. |
| `semantic_test_missing` | Structural tests exist and pass over an implemented chain. | Structural-test evidence plus absence of content-level semantic negative tests. | **Not used presently.** The future chain must include the seeded-shared-fault and mutation tests before any implemented claim. |

### 2.1 Safe future transition examples

The labels become legitimate only in this order:

1. Once a separately accepted evaluator executable exists and declares a machine input, but no product trace producer emits that input, the trace export could be called `producer_missing`—because the consumer would then be named and real.
2. Once both a product trace producer and evaluator consumer exist and their artifacts bind, but no runner transports the frozen trace, the link could be called `bridge_missing`.
3. Once that chain runs end to end but no automated test detects a corrupted trace, seeded shared reducer, expectation leak, or silent oracle supersession, it could be called `verification_missing` and/or `semantic_test_missing` according to the exact missing proof.
4. Only after the whole capability reality check is satisfied may any implementation claim be considered; this report does not make one.

This ordering addresses the blocking misuse seen in prior audits: a more downstream label cannot be borrowed to make upstream endpoints appear to exist.

## 3. Capability-by-capability placement

`P27` ordinarily requires owner-first placement and `P28` requires strangling the superseded path. (`policy-engine/docs/reference/policy-design-case-failure-patterns.md:71-72@1a7a2d05ebba22fae80e9934329e4b880806588e`, findings `P27`, `P28`.) `S0-K14` is the explicit verification exception: correctness evaluation may not share the product's admission, reducers, dependency traversal, or status projection, while a same-code rebuild remains a consistency control only. (`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:143-154@1a7a2d05ebba22fae80e9934329e4b880806588e`, finding `S0-K14`.) The handoff therefore separates product observation ownership from verifier-semantic ownership.

| Capability | Future placement rule | Extend existing owner or independent by construction | Reason and guard |
|---|---|---|---|
| Public benchmark specification | Separately versioned benchmark-specification package or repository; no product runtime import. | **Independent by construction.** | It defines observable questions and equivalence, not product behavior. Product teams may read it; they may not write sealed case answers for their own run. |
| Input-only fixture corpus | Public, content-addressed package with no expected actions, labels, statuses, impact sets, or oracle references. | **Independent by construction.** | It is publishable test input, not a production fixture owner. A scanner rejects answer-bearing fields and generated leakage. |
| Product observable-trace adapter | Thin adapter beside the canonical producer of each raw observation; no evaluator verdict logic. | **Extend existing product owner narrowly.** | Product owners own emitted facts. The adapter may serialize raw receipts/effects only; semantic mappings, acceptance, and hidden expectations are denylisted. |
| Observable trace grammar and canonicalization | Public neutral exchange specification with cross-language vectors. | **Shared neutral substrate only.** | It may normalize syntax and set ordering but may not map admission, dependency, authority, or status semantics. Canonicalization is itself tested for semantic erasure and split-view behavior. |
| Declarative reference reducer `R_v` | Separate repository/build identity, authoring process, dependency lock, and service account. | **Independent by construction.** | Reusing production reducers would violate `S0-K14`. Its provenance is checked transitively, including generated files and network calls. |
| Predicate/metamorphic evaluator `P_v` | Separate implementation from both product and `R_v`; preferably a different language/toolchain and different authoring team. | **Independent by construction.** | It supplies a diverse fault channel and blocks a single reference-runtime defect from creating passage. |
| Same-code incremental/clean-build control `C` | Existing product/runtime-quality surface. | **Extend an existing owner, diagnostic only.** | It may establish parity/consistency and aid diagnosis. It is absent from the verification conjunction and cannot satisfy a missing independent result. |
| Sealed expectation bundle `O_v` | Separately access-controlled oracle custody surface. | **Independent by construction.** | Expected alternatives and exclusions must never enter product history, build context, logs, caches, or implementation-visible fixtures. |
| Adjacent-case/metamorphic generator `M_v` | Separate evaluator-side package, with post-freeze hidden seed and mutation certificates. | **Independent by construction.** | Product reuse would reveal families or reproduce ID-specific behavior. The generator must not import the product or `R_v` answer path. |
| Authority-scenario axiom records | Versioned benchmark-governance evidence; explicit jurisdiction, period, source, reviewer scope, dissent, and uncertainty. | **Independent review input; no appointment here.** | These are fixture-local assumptions, not universal legal truth and not a production authority owner. |
| Commitment/access/challenge/supersession log `L` | Append-only benchmark evidence channel, content-bound to packages and run receipts. | **Independent by construction; not a product ledger.** | `INT-K05` forbids manufacturing a second product confidence ledger. `L` records benchmark custody only and grants no runtime authority. (`policy-engine/docs/system-design-decisions/int-wave-claim-semantics-ratification.md:157-170@1a7a2d05ebba22fae80e9934329e4b880806588e`, finding `INT-K05`.) |
| Human review/adjudication records `H_v` | Signed raw records, conflicts, abstentions, rationales, disagreements, and typed disposition. | **Institutionally independent; no panel appointed here.** | Majority voting cannot create semantic or legal authority. Unresolved disagreement blocks the affected predicate; it is not averaged away. |
| Reproducibility/run receipt | Emitted by the evaluator runner from live committed artifacts; independently verifiable. | **Evaluator-side evidence, independent by construction.** | It binds implementation revision/environment/population/evaluator/oracle versions and raw outcomes. It is not a production release state or authority claim. |
| Challenge publication surface | Existing accepted documentation/audit/publication owner only after consolidation. | **Extend an accepted surface; no new public status lattice.** | The benchmark record may expose commitments, challenges, and supersessions but must not pre-empt product public-correction or publication semantics. |

### 3.1 Import and provenance enforcement handoff

A future implementation must enforce, not merely document, the following:

- evaluator repositories are absent from the product source tree and product build context;
- product packages are absent from evaluator dependency manifests, lockfiles, generated artifacts, network allowlists, container layers, and runtime import graphs;
- a denylist covers semantic symbol families, not only exact filenames: admission, reducer, dependency/affected-set traversal, status/authority projection, product fixture labels, and generated lookup tables;
- allowlists are minimal: public schemas, canonicalization, cryptographic primitives, standard libraries, and raw trace DTOs only;
- source and binary bills of materials, source attestations, build identities, review identities, and network transcripts are attached to each evaluator release;
- a deliberately poisoned “neutral helper” and a generated-artifact laundering attack must fail acceptance;
- a seeded shared product-reducer fault must pass `C` but fail at least one of `R_v` or `P_v`; if it passes both, the evaluator release is architecture-falsified.

The exact tooling is an engineering choice for consolidation. This document does not select a package manager, CI service, identity provider, cryptographic vendor, or deployment topology.

## 4. Integration sequence without implementation authorization

The sequence below is a dependency order, not a plan amendment:

1. Freeze the public observable-semantic specification and explicit equivalence relations under `S0-K13`, without prescribing product internals.
2. Define a raw trace contract and demonstrate that it contains observations rather than product verdict mappings.
3. Establish separate evaluator repositories, identities, build roots, and provenance policy before either evaluator is authored.
4. Independently author `R_v` and `P_v`; run blind proficiency cases and the full architecture falsifier suite.
5. Establish `O_v`, `M_v`, authority-axiom review, access logging, commitment, challenge, rotation, and supersession procedures.
6. Freeze product revision, environment, input population, evaluator versions, oracle commitment, and hidden mutation seed in the required order.
7. Conduct a non-scoring dry run whose result cannot alter expectations, thresholds, exclusions, or denominators in place.
8. Independently audit readback of every committed artifact and every prior version.
9. Only a later acceptance decision may determine whether the implementation and institutional prerequisites for scoring are met. This research architecture alone does not.

`PV-K06` applies directly: timeout, unsupported theory, empty consistency set, incomplete history, heuristic, sampling-only result, or unproved approximation receives a blocking/not-established outcome and cannot inherit an acceptable verdict. (`policy-engine/docs/system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md:164-182@1a7a2d05ebba22fae80e9934329e4b880806588e`, finding `PV-K06`.)

## 5. Wave-4 isolation

| Parallel task | Ownership boundary | S0-GAP-02 treatment |
|---|---|---|
| `OPS-R14` | Durability and expiring rights. | No OPS-R14 artifact is edited or specified. Oracle package retention, commitment continuity, and version supersession are benchmark-custody requirements only; no production durability, RPO/RTO, rights, or storage design is claimed. A future implementation using a shared durability service must declare `OPS-R14` as a dependency rather than importing its semantics into the evaluator. |
| `PAO-R36` | Public correction. | No public-correction state, feed, vocabulary, or owner is specified. Oracle correction/supersession is a benchmark-governance history, not the product's public-correction design. A future public benchmark surface must consume the accepted `PAO-R36` interface by name and must not create a rival status lattice. |
| `PAO-R4` | Individual-decision boundary. | No individual eligibility, remedy, or decision semantics are added. The evaluator only checks benchmark-local observable predicates and makes no individual decision. Any future individual-decision fixture belongs to `PAO-R4`, not this corpus. |

No file owned by these tasks is part of this delivery.

## 6. Typed open questions for consolidation

### 6.1 Engineering

| ID | Question | Why it remains open | Closure evidence required |
|---|---|---|---|
| `ENG-01` | What is the smallest raw trace grammar that is expressive enough for all kernel predicates but cannot encode a hidden product verdict? | Too little trace makes evaluation impossible; too much semantic normalization recreates the product inside the adapter. | Cross-owner field census, negative examples, two independent parsers, and a remove-the-product-mapping probe. |
| `ENG-02` | How will transitive provenance be enforced across source, generated files, containers, services, model artifacts, and runtime network calls? | Import linting alone cannot detect generated-code or remote-service laundering. | Reproducible build attestations, dependency/SBOM checks, network-denial evidence, and poisoned-helper falsifiers. |
| `ENG-03` | Which evaluator diversity dimensions are mandatory: language, algorithm, data representation, authorship, compiler, or runtime? | Diversity costs are real, but superficial diversity does not address correlated failure. | Threat-model-to-diversity mapping and seeded-fault proficiency results. |
| `ENG-04` | How are large unordered trace sets canonicalized without erasing duplicate, order, time, or scope semantics? | Canonicalization can silently become a reducer. | Public vectors, collision/erasure tests, semantic-order certificates, and cross-language equivalence. |
| `ENG-05` | How are hidden mutation seeds generated, committed, recovered, and rotated without leaking variants or permitting post-result selection? | Seed custody is part of oracle custody. | Auditable entropy source, pre-run commitment, access log, recovery drill, and exposure-budget policy. |
| `ENG-06` | How will evaluator disagreement be localized to fixture, axiom, expectation, parser, reducer, predicate, or product output? | “Evaluators disagree” is not a diagnosis and must not trigger ad hoc answer edits. | Typed disagreement receipt, deterministic replay, minimal counterexample, and supersession linkage. |
| `ENG-07` | What exact public commitment construction balances reproducibility, confidentiality, and resistance to dictionary attacks on small answer spaces? | A bare hash may leak low-entropy answers; encryption introduces key custody. | Cryptographic review, threat model, domain separation, salt/key custody, and public verification vectors. |
| `ENG-08` | What bounded resource policy distinguishes a real semantic failure from evaluator timeout or infrastructure failure? | `PV-K06` forbids promoting an unproved approximation. | Pre-registered limits and typed invalid/blocking outcomes with reproducible retry rules. |

### 6.2 Institutional

| ID | Question | Why it remains open | Closure evidence required |
|---|---|---|---|
| `INST-Q01` | Does a second competent team exist with the authority, funding, time, and technical/domain expertise to author and maintain `R_v` and `P_v`? | The architecture is not independent merely because boxes have different names. | Named mandates, competence evidence, conflict disclosures, staffing continuity, and proficiency results. |
| `INST-Q02` | Who may author public axioms, sealed alternatives, mutation families, and adjudication records, and which combinations are incompatible in one evaluation window? | Separation of duties must be operational rather than aspirational. | Approved role matrix, identity controls, access tests, exceptions policy, and audit evidence. |
| `INST-Q03` | What competence standard applies to jurisdictional, institutional, temporal, and custody-semantic review? | Technical correctness cannot manufacture institutional or legal competence. | Scope-specific qualifications, calibration/proficiency exercises, renewal, and abstention rules. |
| `INST-Q04` | What process protects challengers and dissenting reviewers from having their records removed, relabeled, or resolved by organizational pressure? | `S0-K15` requires preserved dissent; cryptographic append-only storage does not itself create procedural fairness. | Challenge rights, response deadlines, independent escalation, reasoned dispositions, and public unresolved-state policy. |
| `INST-Q05` | Who carries key and evidence continuity through role rotation, absence, compromise, or organizational dissolution? | The oracle is itself a custody subject. | Succession plan, threshold recovery, compromise drill, archived verification path, and independent witness evidence. |
| `INST-Q06` | What organizational and economic conflicts arise when evaluator, implementation sponsor, benchmark funder, or scoring beneficiary overlap? | Legal separation alone may not remove incentives for correlated failure or suppression. | Funding disclosure, conflict taxonomy, recusal/abstention records, and external review. |
| `INST-Q07` | Which body accepts an evaluator release for scoring use, and on what appealable evidence? | This research may not appoint that body or silently convert technical acceptance into authority. | Ratified mandate, acceptance criteria, challenge path, and bounded decision record. |

The project backlog itself records that the wave does not advance the `INST-01`–`INST-05` institutional layer and warns that a fully specified system could still lack anyone able to sign. (`policy-engine/docs/research/policy-operations-and-real-world-runtime-backlog.md:1-13@1a7a2d05ebba22fae80e9934329e4b880806588e`.) This is a repository-level reason, in addition to the architecture's own assumptions, for the narrow standing.

### 6.3 Additional research

| ID | Question | Research need | Candidate method |
|---|---|---|---|
| `RES-01` | How much correlated semantic error remains when two evaluators share the same public specification and domain reviewers? | Structural code independence does not imply independent human mistakes. | Blind N-version studies, seeded ambiguous axioms, error taxonomy, and disagreement analysis; no unsupported probability claim. |
| `RES-02` | What mutation-adequacy criterion predicts detection of real custody faults rather than merely known probes? | Counting mutations can reward superficial operators. | Fault-model coverage, subsumption analysis, held-out fault families, and prospective registration. |
| `RES-03` | How should set-valued acceptable outcomes be specified when alternatives have partially ordered authority boundaries or incomparable limitations? | Flat alternatives may hide meaningful dominance or over-permission. | Formal partial-order semantics and adversarial examples, without creating a product status lattice. |
| `RES-04` | How quickly do hidden fixtures lose discriminating power under repeated submissions and public challenges? | Exposure creates adaptive overfitting even without source leakage. | Exposure-budget experiments, rotation simulations, and held-out adjacent-family studies. |
| `RES-05` | Can proof-carrying mutation certificates demonstrate that a transform is semantics-preserving or intentionally semantics-changing without importing product code? | Incorrect metamorphic relations can falsely reject good systems or bless bad ones. | Small formal models, dual proof checkers, and negative relation seeds. |
| `RES-06` | What challenge statistics or qualitative signals detect oracle drift without collapsing dissent into one score? | Agreement measures can obscure systematic minority expertise. | Longitudinal raw-label analysis, stratified proficiency cases, and reason-coded drift reviews. |
| `RES-07` | Which commitment/log design best resists equivocation across implementer, auditor, challenger, and public views? | One honest local log is insufficient against split-view attacks. | Witnessed transparency-log prototypes and gossip/consistency-proof evaluation. |
| `RES-08` | What evidence is sufficient to distinguish coincidentally identical independent errors from prohibited provenance sharing? | An identical mistake is suspicious but not proof of code sharing. | Provenance forensics, counterfactual seeds, reviewer interviews, and reproducible build comparison. |

## 7. Consolidation decision points

Consolidation must decide, rather than infer:

- whether the public schema and equivalence relation are acceptable research contracts;
- whether two competent and genuinely separate evaluator teams can be constituted;
- whether the code/provenance/access separation controls are enforceable in the selected infrastructure;
- whether authority-scenario review has sufficient scoped competence;
- whether challenge, abstention, dissent, correction, and supersession procedures have institutional standing;
- whether the full falsifier suite, especially the seeded shared reducer, has been passed by the architecture itself;
- whether a later implementation acceptance has occurred. Research delivery alone is not that acceptance.

## 8. Result standing

**`accepted_narrow_scope`.** The architecture is technically coherent and constructs non-circular verification for named implementation-origin failure modes under explicit assumptions. It cannot receive `GO` because its decisive premise—a second competent, independently governed evaluator and oracle institution with enforceable separation, custody, and challenge rights—is not established by this delivery or by the pinned repository. No scoring permission, owner appointment, capability claim, or OPS-R15 unblock follows.
