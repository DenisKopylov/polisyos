---
title: S0-GAP-02 — Repository integration handoff and typed open questions
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

This handoff describes where a future implementation would attach and where it must remain separate. It does not authorize that implementation. At documentation pin `109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`, whose `policy-engine/src` tree is byte-identical to the original source pin, **no eligible implementation-independent custody oracle was established by the complete OPS-R15 evidence chain or by the bounded three-owner concept sample**. That is an evidentiary finding, not a universal theorem that no independently implemented evaluator exists anywhere under an unrelated name.

The complete fixed-string census has now been supplied by the architect over path denominator `policy-engine/src`, with case-sensitive content matches and binary files excluded. It confirms extensive in-tree vocabulary: `benchmark` occurs in 197 all-source files (183 Python files), `evaluator` in 85 all-source files (80 Python files), and `oracle` in 44 all-source files (44 Python files). Token density does not establish semantic ownership or independence. The bounded sample remains the semantic evidence: 3/3 named runtime-quality owners are product-coupled or answer-visible, and `grounding_benchmark.py` imports product admission/relation/phrasing logic while carrying expected-answer fields. See [the amended orientation ledger](orientation-ledger.md).

The correct present-tense capability conclusion remains **`not_established`**, used as evidence rather than as a new repository status. It is deliberately not replaced by `producer_missing`, `bridge_missing`, or `verification_missing`, because the prerequisites for those labels are not yet evidenced.

The audit also identified technical admission conditions that this amendment now specifies but does not operationally prove: answer-neutrality of the common substrate; specification-side assurance; finite-domain predicate decidability; discriminator adequacy; mutation/evaluator provenance separation; reviewer proficiency; independently reconciled access evidence; role compatibility; and challenge closure. Those conditions remain `not_established` until the committed execution evidence named below exists.

## 2. Missing-state vocabulary: prerequisites before labels

The repository defines a full capability as contract/artifact, producer, persisted artifact/event, bridge, consumer, verification, surface or explicit out-of-scope rationale, and negative end-to-end semantic test. It defines each missing-state label by the part of that already-existing chain that is absent. (`AGENTS.md:13-37@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`; `policy-engine/docs/reference/policy-design-case-failure-patterns.md:15-45@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`, capability reality check.)

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

`P27` ordinarily requires owner-first placement and `P28` requires strangling the superseded path. `S0-K14` is the explicit verification exception: correctness evaluation may not share the product's answer-producing admission, reducers, dependency traversal, affected-set logic, or status projection, while a same-code rebuild remains a consistency control only. (`policy-engine/docs/reference/policy-design-case-failure-patterns.md`, findings `P27`, `P28`; `policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md`, finding `S0-K14`, all at `109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`.) The handoff therefore separates product observation ownership from verifier-semantic ownership and applies `P37` to every gate predicate.

| Capability | Future placement rule | Extend existing owner or independent by construction | Reason and admission guard |
|---|---|---|---|
| Public benchmark specification `B` | Separately versioned public specification; product teams may read but may not author sealed answers for their own run. | **Independent by construction, with specification assurance.** | Shared input is allowed only after every common artifact is classified under `AnswerNeutral(z,f)` and admitted through the frozen P37 predicate register. A bad shared axiom yields `SPECIFICATION_ASSURANCE_NOT_ESTABLISHED`, not a custody-semantics claim. |
| Input-only fixture corpus | Public, content-addressed package with no expected actions, labels, statuses, impact sets, or oracle references. | **Independent by construction.** | A scanner rejects answer-bearing fields, generated leakage, and low-entropy answer encodings. |
| Product observable-trace adapter | Thin adapter beside each canonical producer of raw observations; no evaluator verdict logic. | **Extend existing product owner narrowly.** | Product owners own emitted facts. The adapter may serialize raw receipts/effects only. Admission, reduction, affected-set, authority/status and ambiguity-collapse mappings are prohibited. |
| Common grammar/canonicalization `N` | Public exchange specification with cross-language vectors. | **Shared only when `AnswerNeutral(z,f)` is constructed.** | A machine allowlist, transitive source/SBOM/network evidence, poisoned-helper probes for every semantic family, and independent review must show that it only parses, canonicalizes, transports or identifies declared inputs. Declaration alone fails `P37`. |
| Declarative reference reducer `R_v` | Separate repository/build identity, authoring process, dependency lock and service account. | **Independent by construction.** | Reusing production reducers violates `S0-K14`. Provenance is checked transitively, including generated files and runtime calls. |
| Predicate/metamorphic evaluator `P_v` | Separate implementation from product and `R_v`, with independent authoring and preferably a distinct language/toolchain. | **Independent by construction.** | It supplies a different answer-producing channel. Both `R_v` and `P_v` must pass; disagreement blocks and is never voted away. |
| Same-code incremental/clean-build control `C` | Existing product/runtime-quality surface. | **Extend existing owner; diagnostic only.** | It establishes consistency and aids diagnosis. It is absent from every verification/specification-assurance conjunction, receipt claim and handoff gate. |
| Sealed expectation bundle `O_v` | Separately access-controlled oracle-custody surface derived from `B` under independent review or dual control. | **Independent by construction, but not self-validating.** | Finite alternatives are evaluated in the total decidable finite-domain DSL. Shared bad `B`/`O_v` is gated by `S_v`; no specification-side agreement is promoted to semantic truth. |
| Mutation generator `M_v` | Separate post-freeze hidden-seed package. | **Independent from product, `R_v`, `P_v`, and relation validator `J_v`.** | `M_v` may not share a private semantic transform/table with the evaluator that judges its relations. A-15 rejects the release before product scoring. |
| Mutation relation validator `J_v` | Separate proof/checker identity from `M_v` and both evaluators. | **Independent by construction.** | It checks mutation certificates using the admitted public relation language, not a generator-private table or product implementation. |
| Specification-assurance record `S_v` | Evidence channel over public axioms, expectation derivation, reviewer proficiency and challenges. | **Independent review input; no institution appointed here.** | It supports the stronger custody-semantics claim only when every required premise is recomputed, machine-observed, independently reconciled, or validly institutionally accepted. Otherwise the result is a governed negative completion. |
| Authority-scenario axiom records | Versioned fixture-local evidence with jurisdiction, period, source, reviewer scope, dissent and uncertainty. | **Independent derivation/review; no appointment here.** | They are scenario assumptions, not universal legal truth. Scenario author and expectation author cannot be the sole common semantic origin in one window. |
| Commitment/access/challenge/supersession log `L` | Append-only benchmark evidence channel. | **Independent by construction; not a product ledger.** | `INT-K05` forbids a second product confidence ledger. `L` records benchmark custody only. Access admission binds storage, network and key-service heads plus an independent reconciliation disposition. |
| Human review/adjudication `H_v` | Signed raw records, conflicts, abstentions, rationales, evaluator disagreement, proficiency and drift evidence. | **Institutionally independent; no panel appointed here.** | Unanimity does not prove correctness. Missing or failed proficiency yields `SPECIFICATION_ASSURANCE_NOT_ESTABLISHED`; raw dissent remains append-only. |
| Reproducibility/run receipt | Emitted from live committed artifacts and independently verifiable. | **Evaluator-side evidence.** | It binds implementation/environment/population, R/P/M/J/S versions, P37 predicate classes, access reconciliation, challenges and raw outcomes. It cannot render the `S0-K16` passage sentence while a blocking challenge remains open. |
| Challenge publication surface | Existing accepted documentation/audit/publication owner only after consolidation. | **Extend accepted surface; no new product status lattice.** | Benchmark commitments/challenges/supersessions must not pre-empt product correction or publication semantics. |

### 3.1 P37 predicate-admission handoff

Every load-bearing gate predicate is frozen at admission as exactly one of:

`recomputed` · `machine_observed` · `independently_reconciled` · `attested` · `institutionally_accepted` · `not_established`.

The richer six-way split is deliberate: an authorship or non-collusion attestation is not the same as an institutionally accepted competence premise, and neither is machine proof. A positive verification gate may depend decisively only on `recomputed`, `machine_observed`, or `independently_reconciled` predicates. An `attested`, `institutionally_accepted`, or `not_established` decisive premise must fail closed or degrade the claim according to its predeclared rule. A missing institutional premise renders `INDEPENDENCE_NOT_ESTABLISHED`; it is never displayed as machine-proved.

The *falsify-the-declaration* probe is mandatory: make the declared premise false while preserving the declaration bytes. If the gate remains green, the release is rejected because it tests the declaration rather than the property.

### 3.2 Import, provenance and adequacy enforcement handoff

A future implementation must enforce, not merely document:

- common `N ∪ B` artifacts are admitted only through a machine allowlist and `AnswerNeutral(z,f)` evidence for each semantic family;
- source, generated files, SBOMs, containers, model artifacts, services and runtime network transcripts are checked transitively;
- a deliberately poisoned “neutral helper” for each of admission, reduction, dependency/affected-set, status/authority, ambiguity-collapse and expected-answer families makes the run red;
- product packages are absent from `R_v`, `P_v`, `M_v` and `J_v` answer paths;
- `M_v`, `J_v`, `R_v` and `P_v` do not share a private semantic transform, relation table or generated semantic ancestor;
- each seeded mutation is bound to its expected semantic delta, named discriminator and liveness/removal/neutralization witnesses;
- removing the relevant discriminator makes acceptance fail closed as `EVALUATOR_COVERAGE_NOT_ESTABLISHED`;
- a seeded shared product-reducer fault may pass `C` but must fail at least one independent channel; dual acceptance remains `ARCHITECTURE_FALSIFIED`;
- a seeded bad public axiom or expectation may be implemented correctly by both channels but withholds the stronger claim as `SPECIFICATION_ASSURANCE_NOT_ESTABLISHED`;
- the finite-domain predicate compiler rejects the audit's universal catch-all bundle and blocks on timeout, unsupported theory or unknown proof status under `PV-K06`;
- role assignment, access reconciliation, reviewer proficiency and blocking-challenge closure are independently evidenced before claim rendering.

These are research acceptance conditions, not a package-manager, CI, identity-provider, cryptographic-vendor or deployment-topology selection.

## 4. Integration sequence without implementation authorization

The sequence below is a dependency order, not a plan amendment:

1. Freeze the public observable-semantic specification, finite trace domain and total decidable predicate DSL under `S0-K13`, without prescribing product internals.
2. Freeze the P37 predicate-provenance register; no decisive premise may be relabelled after the evaluation window opens.
3. Define the raw trace contract and machine-enforced `AnswerNeutral(z,f)` allowlist; execute the poisoned-helper and falsify-the-declaration probes.
4. Establish separate identities/build roots for `R_v`, `P_v`, `M_v`, and `J_v`; validate the role-assignment window and transitive provenance before authoring case answers.
5. Independently author `R_v` and `P_v`; qualify every discriminator with semantic-delta, liveness, removal and neutralization evidence.
6. Establish `B`→`O_v` independent derivation or dual control, `S_v`, reviewer proficiency/drift checks, and the A-14/A-16 specification-side falsifiers.
7. Compile the finite alternatives; reject catch-all/tautological/unsatisfiable bundles and block all unknown proof results under `PV-K06`.
8. Establish commitment, hidden seed, access reconciliation, challenge, rotation and supersession procedures; bind all heads and dispositions into the receipt.
9. Freeze product revision, environment, input population, evaluator/generator/validator/specification-assurance versions and hidden seed in the declared order.
10. Conduct a non-scoring dry run. `C` is diagnostic only; R and P both pass or the run blocks. The stronger claim also requires `S_v` and no unresolved blocking challenge.
11. Read every artifact and receipt back from immutable storage; preserve negative completion, disagreement and prior versions.
12. Only a later acceptance decision may determine whether the implementation and institutional prerequisites for scoring are met. This amendment does not.

`PV-K06` applies directly: timeout, unsupported theory, empty consistency set, incomplete history, heuristic, sampling-only result, or unproved approximation receives a blocking/not-established disposition and cannot inherit acceptance. `INT-K08` applies to negative completion: `SPECIFICATION_ASSURANCE_NOT_ESTABLISHED`, `INDEPENDENCE_NOT_ESTABLISHED`, and `EVALUATOR_COVERAGE_NOT_ESTABLISHED` are benchmark-local evidence dispositions that withhold a positive claim; they do **not** add a fourth element to the project outcome vocabulary.

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
| `ENG-09` | How is `AnswerNeutral(z,f)` enforced for every common artifact and semantic family? | Naming a helper neutral is the P37 failure mode. | Machine allowlist, transitive source/SBOM/network evidence, family-specific poisoned helpers and independent review record. |
| `ENG-10` | What finite trace-domain and PDL-1 compiler implementation produces terminating SAT/UNSAT/tautology certificates? | The anti-catch-all gate must be decidable rather than asserted. | Proof-producing compiler vectors, catch-all rejection fixture and timeout/unsupported blocking tests. |
| `ENG-11` | How is discriminator adequacy maintained as failure families evolve? | Existence does not establish liveness or coverage. | Mutation-to-delta registry, liveness/removal/neutralization probes and versioned coverage receipts. |
| `ENG-12` | How are independent access heads reconciled and how does an unresolved gap affect the run? | One log head cannot prove no unlogged read. | Storage/network/key-service heads, independent reconciliation and exact RUN_INVALID/INDEPENDENCE_NOT_ESTABLISHED tests. |

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
| `INST-Q08` | Who independently derives or dual-controls the `B`→`O_v` step? | One scenario/expectation origin is the specification-side common-cause channel. | Approved incompatibility matrix, independent review/dual-control receipts and role-validator evidence. |
| `INST-Q09` | Who administers blinded reviewer proficiency and drift cases without leaking them to reviewers or implementers? | Competent unanimity can still be uniformly wrong. | Scoped proficiency corpus, separation of roles, exposure controls, renewal criteria and A-16 result. |

The project backlog itself records that the wave does not advance the `INST-01`–`INST-05` institutional layer and warns that a fully specified system could still lack anyone able to sign. (`policy-engine/docs/research/policy-operations-and-real-world-runtime-backlog.md:1-13@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`.) This is a repository-level reason, in addition to the architecture's own assumptions, for the narrow standing.

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
| `RES-09` | What bounded assurance can be claimed about shared public axioms and sealed expectations? | Code independence cannot validate a shared wrong specification. | Seeded axiom faults, independent derivation studies, challenge outcomes and explicit distinction between not-refuted and established semantics. |

## 7. Consolidation decision points

Consolidation must decide, rather than infer:

- whether the finite trace domain, PDL-1 semantics and proof-producing compiler are acceptable research contracts;
- whether `AnswerNeutral(z,f)` is actually enforced for every common artifact and semantic family;
- whether discriminator liveness/removal/neutralization and the full A-14–A-21 suite are reproduced;
- whether `M_v`/`J_v`/`R_v`/`P_v` provenance separation, role compatibility and access reconciliation are evidenced;
- whether reviewer proficiency and specification assurance justify more than “not refuted under the committed specification”;
- whether two competent and genuinely separate evaluator functions can be constituted;
- whether challenge, abstention, dissent, correction and supersession procedures have institutional standing;
- whether every R1–R11 evidence reference exists in a committed re-audit packet;
- whether a later implementation acceptance has occurred. Research delivery alone is not that acceptance.

## 8. Result standing

**`accepted_narrow_scope`.** The amendment closes the four blocking defects at the **research-contract level** by specifying answer-neutral common provenance, a specification-side assurance gate, a decidable finite-domain predicate language, and discriminator-adequacy witnesses. It also incorporates the remaining R6–R10 controls. It does not provide the machine-enforced allowlist, executed probes, proof-producing compiler, evaluator releases, proficiency results, independently reconciled audit heads, role-validator run, challenge-closure evidence, or the second competent independently governed function. Those technical execution premises and the institutional premise are therefore still `not_established`.

The strongest available positive statement before those premises are accepted is “the named implementation was not refuted under the committed specification and recorded evidence.” The stronger statement that acceptable custody semantics were established is withheld unless `S_v` is established and every blocking challenge is closed. Negative completion under `INT-K08` is a valid governed result and does not create a fourth outcome-vocabulary element. No scoring permission, owner appointment, capability claim, or `OPS-R15` unblock follows.
