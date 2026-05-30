---
title: PolicyOS Universal Policy Design Case Research Plan
status: active
owner: team-policy-design-research
created: 2026-05-21
stability: draft
raw_research_ledger: ../../research/universal-policy-design/deep-research-reports-105-146-combined.md
source_synthesis: ../../backlog/universal-policy-design-case-research-results-consolidation.md
implementation_plan: ./POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md
source_ownership: ../../reference/policy-design-case-source-ownership.md
related:
  - ../../system-design-decisions/policy-design-best-in-class-operating-model.md
  - ../../system-design-decisions/policy-design-case-decision-log.md
  - ../../backlog/production-data-e2e-diagnostic-backlog.md
  - ../../backlog/cloud-wave11-root-cause-diagnostic-backlog.md
  - ../../backlog/universal-policy-design-case-research-results-consolidation.md
  - ../../research/universal-policy-design/deep-research-reports-105-146-combined.md
  - ./POLICYOS_BEST_IN_CLASS_EVIDENCE_BINDING_AND_SCENARIO_AUTHORITY_PLAN.md
  - ./POLICYOS_EVIDENCE_SPINE_CONNECTIVITY_REMEDIATION_PLAN.md
scope:
  - policy-design-case
  - universal-policy-grammar
  - capability-baseline
  - admissibility
  - authority-levels
  - claim-taxonomy
  - concept-spine
  - evidence-independence
  - argument-structure
  - evaluation-methodology
  - llm-boundaries
  - contestability
  - lifecycle
  - calibration
  - evidence-acquisition
  - self-fmea
  - honest-diagnostics-substrate
  - proof-carrying-analytics
  - policy-design-case-api
  - drift-detection
  - data-forge-provenance
  - run-cost-governance
  - welfare-transparency
  - participation-provenance
  - tradeoffs
---

# PolicyOS Universal Policy Design Case Research Plan

Source ownership: this research plan is part of the repo-owned Policy Design
Case source chain governed by
`docs/reference/policy-design-case-source-ownership.md`. The raw research
ledger lives at
`docs/research/universal-policy-design/deep-research-reports-105-146-combined.md`,
the normalized synthesis lives at
`docs/backlog/universal-policy-design-case-research-results-consolidation.md`,
and the engineering handoff lives at
`docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md`.

> **For agentic researchers:** REQUIRED WORKFLOW: use this document as a
> research plan, not an implementation plan. Each wave should produce a
> written research artifact, testable formal claim, annotated corpus slice, or
> implementation-ready ADR. Do not turn unresolved research questions into code
> contracts until the acceptance criteria in that wave are met.

**Goal:** Determine the formal kernel needed for PolicyOS to generate a
Policy Design Case for any policy domain without relying on hundreds of
hand-written domain adapters.

**Architecture hypothesis:** PolicyOS should use a universal policy grammar:
typed fields, facets, admissibility rules, claim-method matching, provenance,
contestability, lifecycle dependencies, and evaluation loops. LLMs should act
as policy formulators and critics that generate candidate hypotheses, risks,
facets, obligations, and missing-question prompts; runtime contracts decide
whether those candidates become admissible evidence, typed blockers,
limitations, or rejected speculation.

**Research stance:** The research task is not "what feature should we build?"
The research task is "what must be formally solved so the feature can be built
without duct tape?" The plan therefore targets theory, empirical validation,
corpus design, evaluator design, and implementation-ready design decisions.

---

## Dense Context For Researchers

PolicyOS is being pushed toward a best-in-class policy-design operating model:
not a chat assistant that writes plausible policy memos, but a runtime that can
prove why a serious recommendation is admissible, limited, contested, blocked,
or ready for publication.

The current architecture already contains several important runtime-quality
pieces:

- `scenario_evidence_contract`: expresses what a serious scenario requires.
- `evidence_spine`: carries scenario contract ids and requirement ids through
  producers, bundles, inspection, readiness, and closeout.
- `evidence_spine_handoff`: records async handoffs between request creation,
  control-plane jobs, workflow persistence, CAS writes, bundle assembly,
  replay, inspection, readiness, and exports.
- `production_data_contract_index`: maps manifests, curated contracts, source
  bindings, facets, freshness, lineage, quality, and scenario source families.
- Fabric source-selection audit: separates broad context inventory from
  claim-admissible selected contract bindings.
- Lex query normalization and applicability reports: retrieve candidate legal
  norms and attempt to anchor them per recommendation.
- Foundry method-quality validation: prevents generic method labels from
  satisfying serious method obligations.
- Runtime claim registry and semantic binding: require major claims to bind to
  scenario requirements, data refs, norm refs, method outputs, arguments,
  warrants, rebuttals, counter-evidence, limitations, and blockers.
- Policy Design Case record-family compilation: blocks profile-only `pass`
  states when runtime-owned records are absent.
- Authority envelope checks: distinguish missing provenance, spoofed
  provenance, packaging-only projection, borrowed authority envelope, and
  runtime-owned domain failure.
- Closeout compatibility checks: verify deployed producer, reader, authority,
  scenario contract, and code-revision compatibility.

The operating model requires **reuse-first** research and implementation:
`wire-existing`, then `extend-existing`, then `consolidate-existing`, and only
then `build-new`. This matters because PolicyOS already contains many
load-bearing modules that partially formalize the research questions in this
plan. Researchers must treat these modules as empirical baseline behavior, not
as incidental code to ignore.

| Capability surface | Existing anchors | Research implication |
| --- | --- | --- |
| Runtime assurance case, authority, and closeout | `src/polisyos/runtime/quality/assurance_case.py`, `authority.py`, `authority_reconciliation.py`, `semantic_binding.py`, `prompt_tool_ledger.py`, `human_review.py`, `phase_barriers.py`, `invariants.py`, `scorecard.py`, `replay.py` | Admissibility and argument-structure research must map current runtime semantics before proposing new schemas. |
| Scientist policy-design workflow | `src/polisyos/scientist/policy_design/schema.py`, `objectives.py`, `critic.py`, `adversary.py`, `search.py`, `output.py` | LLM formulation and critic research should evaluate and extend this workflow, not invent a parallel formulator. |
| Claim registry lifecycle | `src/polisyos/scientist/evidence/claims/models.py`, `ledger.py`, `lifecycle.py`, `audit.py`, `diff.py`, `export.py`, `readiness.py` | Claim taxonomy, lifecycle, export truthfulness, and revalidation research should project over this registry. |
| Research DAG and invalidation | `src/polisyos/scientist/methods/research_dag/replay.py`, `invalidation.py`, `comparison.py`, `builder.py` | Reproducibility under taxonomy evolution must reuse DAG replay and invalidation semantics. |
| Claim validation and reliability | `src/polisyos/scientist/validation/claim_support.py`, `citation_faithfulness.py`, `reliability_scorecard.py` | Admissibility and evidence quality research should baseline existing support and faithfulness checks. |
| Value of Information and acquisition scheduling | `src/polisyos/scientist/methods/search/voi_models.py`, `voi_scheduler.py`, `voi_calibration.py` | Evidence acquisition planning should become an inverse-problem layer over VOI, not a new scheduler. |
| Consensus, equivalence, and effective independence | `src/polisyos/foundry/methods/consensus.py`, `src/polisyos/foundry/methods/equivalence/*` | Evidence convergence and effective independent evidence count should extend consensus/equivalence machinery. |
| DOE, multiverse, and specification curves | `src/polisyos/scientist/methods/doe/*` | Method-claim and portfolio research should reuse DOE/specification exploration where the claim needs robustness evidence. |
| Trinity why/what/how layer | `src/polisyos/ir/governance/problem_frame.py`, `policy_spec.py`, `temporal_logic.py`, `policy_composition.py` | Universal policy grammar should map to the IR distinction between problem frame, policy specification, temporal semantics, and composition. |
| Calibration and post-market monitoring | `src/polisyos/calibration/*`, `src/polisyos/scientist/governance/calibration*.py`, `src/polisyos/ddm/*` | Backtesting is not enough; longitudinal calibration and DDM must become record-family evidence. |
| Concrete DDM detectors and invalidation bridge | `src/polisyos/ddm/detectors/*`, `src/polisyos/ddm/integration/monitor.py`, `src/polisyos/scientist/governance/continuous/invalidation.py` | Data-quality, performance, realized-performance, shift, readiness, and source-invalidation paths exist; C20/E15 should add universal-policy and PDC bridges, not claim all detectors are absent. |
| Bounded explanation reliability | `src/polisyos/berl/*`, `src/polisyos/runtime/quality/explanation_reliability.py` | Explanation bundles, validation gates, and warrant reliability bridges exist; claims using model explanations need universal-case integration and longitudinal BERL thresholds, not a new BERL schema. |
| Audit and external verifier | `src/polisyos/core/audit/*`, `src/polisyos/core/security/slsa/*` | Publication and external-governance research must reuse deterministic audit package assembly, offline verification, PROV graphs, signatures, and SLSA/in-toto surfaces. |
| Data Forge artifact and release provenance | `src/polisyos/data_forge/kernel/artifacts.py`, `kernel/snapshot/*`, `domains/ukraine/manifests.py`, `read_api/*` | Artifact refs, snapshot transactions, release manifests, and read APIs exist; C20/C22/E16-E17 should define official closeout-grade scenario and claim binding over these surfaces. |
| Fabric contracted source platform | `src/polisyos/fabric/connectors/contracts/source_contract.py`, `validation_middleware.py`, `family_contracts.py`, `governance_checks.py` | SourceContract v2 already covers schema, quality, replay, lineage, field access, security, SLA, terms, retention, and deprecation; C2/C22/E10-E17 should use this platform for scenario admissibility instead of inventing a new source contract. |
| Domain evidence producers | `src/polisyos/lex/`, `src/polisyos/fabric/`, `src/polisyos/scholar/`, `src/polisyos/foundry/` | Data, legal, academic, and method obligations should be emitted by existing producers unless C0 proves a gap. |
| Formal substrate invariants | `src/polisyos/runtime/quality/formal_invariants.py` | Five model-checked closeout invariants already exist; C24 should extend them to temporal/liveness and integrate them, not rebuild them. |
| Honest diagnostics fragments | `src/polisyos/runtime/quality/event_log.py`, `attestation.py`, `source_truth.py`, `metamorphic_controls.py`, `closeout_compatibility.py`, `performance_budget.py` | The substrate is fragmented across modules; research must define a unified closeout decision authority over these fragments. |
| Prompt/tool and source-truth integrity | `src/polisyos/runtime/quality/prompt_tool_ledger.py`, `source_truth.py` | Prompt fingerprints, repair decisions, attestation boundaries, and semantic preservation rules are existing evidence-integrity anchors. |
| Adversarial challenge factory | `src/polisyos/scientist/evals/challenge_factory.py` | Many red-team classes are already defined; C26/E22 should add missing probes rather than rebuild challenge infrastructure. |
| Reflexive memory and continuous governance | `src/polisyos/scientist/orchestration/memory/failure_lessons.py`, `src/polisyos/scientist/governance/continuous/monitors.py`, `reissue.py` | Lifecycle research should add memory decay, universal-policy detector bridges, and partial-scope reissue over existing event and packet contracts. |
| Runtime projection and public export semantics | `src/polisyos/runtime/quality/projection_semantics.py`, `public_export.py`, `runtime/http/services/control/response_shapes.py` | Projection-only and public-export guardrails already prevent minted authority; C16/E4-E5 should enrich and type the PDC projection rather than rebuild export truthfulness from scratch. |
| Publishing and external audiences | `src/polisyos/scientist/publishing/publisher.py`, `src/polisyos/scientist/orchestration/orchestrator/decision_card.py`, `src/polisyos/runtime/http/routes/runs.py` | Decision-grade audience exports already derive from claim ledger and research DAG; C16/E4-E5 must bridge this compiler to a typed universal Policy Design Case projection. |
| Proof-carrying IR analytics | `src/polisyos/ir/analytics/partial_identification.py`, `recoverability.py`, `path_specific_identification.py`, `transportability.py`, `negative_certificate.py`, `dual_certificate.py`, `certified_tightening.py`, `proof_composability.py`, `fairness.py`, `strategic.py`, `causal_ensemble.py` | C9/C13/E8/E13 should bind existing certificates/statuses to claim records and portfolios instead of inventing method authority from scratch. |
| Scholar web evidence bundle | `src/polisyos/scholar/search/models.py`, `scoring.py`, `spine.py` | Search budgets, safety traces, source quality, snippets, claim support links, and duplicate heuristics exist; C13/E13 should extend source-family independence and claim-bound quality, not build basic Scholar evidence contracts. |
| Agent simulation and synthetic worlds | `src/polisyos/foundry/agent_sim/world/*`, `src/polisyos/foundry/agent_sim/wiring/contracts.py` | Typed DGPs, truth manifests, evaluation runs, and intervention mechanism configs exist; C13/E12-E13 should add claim-bound assumptions, calibration refs, and simulation-family independence. |
| Welfare and social weights | `src/polisyos/foundry/welfare/*`, `src/polisyos/foundry/welfare/social_weights.py` | Welfare bound reports and social-weight schedules exist; C18 should add provenance for value choices, Pareto/frontier publication, and claim binding. |
| Human-review escalation | `src/polisyos/scientist/governance/human_review/voi_escalation.py` | C24 should measure review effectiveness and bias over existing escalation requirements. |
| Run performance, cost, and degradation | `src/polisyos/runtime/quality/performance_budget.py`, `degradation.py` | Performance budgets exist; run-cost and degradation-SLA gates remain research/build gaps. |

A second deep code pass changes the center of gravity. PolicyOS internals are
stronger than a clean-room research plan would assume: IR analytics already
emits proof-carrying certificates; formal closeout invariants already exist;
challenge classes already cover many adversarial probes. The recurring weak
pattern is different:

```text
sophisticated component
  -> thin orchestration bridge
  -> weak external/API projection
  -> reader or closeout cannot see the proof the producer already had
```

The research plan must therefore focus less on inventing isolated schemas and
more on **binding existing proof-bearing artifacts into ClaimRecord, semantic
binding, Policy Design Case records, API projections, and closeout**.
The second recurring pattern is the **contracts-versus-implementations gap**:
some typed surfaces have concrete implementations, while others stop at
contracts. DDM already implements several data/performance/shift/readiness
detectors, but universal-policy detector bridges, cost gates, partial-scope
reissue, and unified substrate decisions are still missing.

The 2026-05-20 and 2026-05-21 cloud diagnostics showed that these gates are
useful, but they also exposed a deeper system-design question:

> How does PolicyOS generate the right obligations for a new policy problem
> before it can validate them?

The immediate cloud failure named three absent source families:
`production_msme_panel`, `credit_program_registry`, and
`regional_displacement_indicators`. That is not the universal problem. The
universal problem is that a system asked to design any policy must first infer:

- what kind of policy instrument is being proposed;
- who is targeted and who is indirectly affected;
- what legal authority is required;
- what data families are admissible for each claim;
- what methods can support each claim type;
- what implementation, fiscal, operational, equity, rights, fraud, safety,
  privacy, and political risks must be considered;
- what monitoring signals and revalidation triggers are needed;
- what participation provenance is required before claiming affected-person
  preferences or legitimacy;
- what tradeoffs are computable and what value choices must remain explicit.

The initial instinct might be to build domain adapters for health, housing,
taxation, education, climate, labor, security, MSME, migration, and so on.
That path is risky. It may create hundreds of brittle templates and reintroduce
manual domain curation as the hidden authority source.

The research hypothesis here is different:

1. Define a universal set of policy-design fields and facets.
2. Let LLMs formulate rich candidate content for those fields in a specific
   problem, including dozens or hundreds of candidate risks and obligations.
3. Compile LLM-generated candidates into typed obligations.
4. Validate obligations through formal admissibility, evidence retrieval,
   claim-method matching, provenance, and closeout.
5. Preserve unsupported LLM content as `candidate_unverified`,
   `rejected_speculation`, `typed_blocker`, or `limitation`, never as
   authority.

This does **not** mean PolicyOS can avoid curated knowledge entirely. The
elegant target is not zero rules. The target is replacing `N` brittle domain
templates with `M` governed obligation rules, where `M << N` but `M != 0`.
Those rules must be evidence-backed, versioned, statused, and reproducible.
LLMs may propose rule candidates; they may not silently become the rulebook.

This creates a clean separation:

| Layer | Role | May mint authority? |
| --- | --- | --- |
| LLM policy formulator | proposes candidate fields, risks, claims, obligations, and missing questions | No |
| LLM critics | search for omissions, contradictions, unsupported risks, stakeholder gaps, and method gaps | No |
| Obligation compiler | turns structured candidates into required evidence obligations | No by itself |
| Evidence producers | retrieve and bind data, legal, method, scholar, participation, and implementation evidence | Yes, if authority envelope passes |
| Admissibility calculus | decides whether evidence can support a claim in scope | Yes, as a reader/gate |
| Policy Design Case compiler | projects bound evidence into records and public artifacts | No new authority; projection only |
| Closeout | verifies deployed producer/reader/authority/code compatibility | Yes, for release readiness |

The central design target is therefore:

```text
policy request
  -> universal policy grammar
  -> LLM candidate formulation
  -> facet and claim decomposition
  -> obligation graph
  -> evidence acquisition plan
  -> admissibility decisions
  -> claim-bound design graph
  -> Policy Design Case records
  -> lifecycle monitoring and revalidation
```

The research questions below define what must be solved before this can become
an implementation plan.

## Non-Goals

- Do not build a catalog of domain-specific templates as the primary solution.
- Do not let LLM output count as legal, data, stakeholder, or scientific
  authority.
- Do not optimize for one golden scenario.
- Do not reduce policy quality to a scalar score.
- Do not force aggregation of normative tradeoffs into a fake single optimum.
- Do not conflate evidence absence, contested evidence, and implementation
  infeasibility.

## Core Research Outputs

Each conceptual research task should produce at least one of these artifacts:

- a formal definition or typed algebra;
- an annotated policy-case corpus slice;
- an evaluation protocol;
- a reproducibility protocol;
- an implementation-ready ADR;
- a minimum viable schema;
- a red-team/adversarial test pack;
- a decision memo that explicitly rejects a tempting but weak design.

The final output of this research plan should be a second document:

`docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md`

That implementation plan should only be written after the load-bearing
research questions have enough evidence to avoid encoding speculation as
architecture.

## Task Workstream Classes

The tasks now use `C` for conceptual research and `E` for engineering
translation. They require different skills and acceptance evidence.

| Class | Primary tasks | Primary method | Main risk |
| --- | --- | --- | --- |
| Runtime baseline and reuse mapping | C0, E0 | code inspection, capability mapping, behavior extraction | Rebuilding modules that already exist or anchoring on shims. |
| Formal semantics | C1-C3, C6-C7, C9-C11, C13-C18 | typed models, decision tables, negative controls | Elegant theory that cannot classify real cases. |
| Knowledge engineering | C4-C5, C19, C22 | corpus annotation, rule lifecycle, schema design | Hidden prompt curation or ungoverned rules. |
| Empirical LLM evaluation | C12, E22 | annotated benchmarks, ablations, critic comparison | Mistaking fluent coverage for grounded authority. |
| Lifecycle and operations | C20-C25, E14-E21 | replay, calibration, FMEA, monitoring, governance policy | Ignoring non-adversarial machinery failures. |
| Evaluation and benchmark governance | C26, E1, E22 | historical backtesting, adversarial probes, expert panels | Overfitting to the first corpus or golden scenario. |
| Implementation handoff | C27, E23-E24 | ADRs, runbooks, validation ladder, capability chains | Starting engineering before conceptual gates are stable. |

## Code-Pass Corrections To Task Focus

The deep code passes changed task sizing and focus. Several areas that looked
like open research choices are already partially decided in code; several areas
that looked like small extensions are actually missing bridges or new
coordination surfaces. These corrections are expressed in the current C/E task
coordinates.

| Area | Earlier framing | Code-grounded finding | Current task focus |
| --- | --- | --- | --- |
| Admissibility and status | Design from scratch. | `claim_support.py`, `citation_faithfulness.py`, `authority.py`, scorecard, approval, semantic binding, and phase barriers already define local decision logic. | C1-C3 define composition, authority levels, legal degradation, and closeout substrate over existing behavior; E2-E3 implement only after those semantics stabilize. |
| Facets and obligations | Design broad domain templates and rule language. | IR governance, policy spec, critics, challenge classes, and temporal logic already cover much of the shape/language. | C4-C5 enumerate open vocabularies and governed obligation rules instead of inventing domain packs; E17 uses those rules for acquisition paths. |
| Concept spine | Thin view over existing entity/cross-graph modules. | Existing modules solve pairwise matching, SCM composition, evidence conflict, or semantic binding, but not shared cross-producer concept authority. | C6-C8 define concept identity, legal competence, and producer handshake; E6-E7 wire the protocol. |
| Claims and methods | Design claim taxonomy and method matrix from scratch. | Claim registry and support predicates exist; IR analytics already emit proof-carrying certificates and statuses. | C9-C10 define compatibility, baselines, and comparison semantics; E8 and E12 bind existing proofs and methods to claims. |
| Time/numeric/geography | Treat as a small data-quality appendix. | Runtime, Fabric, Lex, Scholar, Data Forge, DDM, and replay each have local time semantics. | C11 defines a full time-role and mismatch algebra; E9-E16 must preserve it through producers and closeout. |
| LLM boundary | Evaluate critic personas. | Deterministic critic and LLM+fallback patterns already exist. | C12 evaluates marginal coverage and formalizes the candidate-to-authority firewall; E22 tests speculation laundering. |
| Effective independence | Extend consensus/equivalence only. | Consensus/equivalence measure agreement, not lineage independence; Scholar and agent simulation have rich metadata but no universal collapse model. | C13-C14 define independence and conflict semantics; E13 wires portfolio aggregation. |
| Argument and external surface | Choose SACM/CAE/GSN and build exports. | `assurance_case.py` already maps SACM/CAE/GSN; projection/public-export guardrails exist but PDC API remains shallow. | C15-C16 refine warrant/profile and multi-audience surface semantics; E4-E5 build typed projection surfaces. |
| Contestability, tradeoffs, participation | Mostly theoretical. | Normative arbitration, frontier reports, welfare bounds, and social weights exist; participation provenance is mostly missing. | C17-C19 split disagreement, tradeoff/welfare, and participation into separate conceptual tasks; E4/E8/E11/E22 consume them. |
| Lifecycle and replay | Define lifecycle from scratch. | Claim lifecycle, DDM paths, reissue packets, schema compatibility, and shims exist. | C20-C21 define revalidation, rule evolution, and legacy retirement; E14-E16 implement the bridges. |
| Acquisition and cost | Extend VOI and performance budgets. | VOI ranks actions, not acquisition orchestration; performance budgets are not cost/SLA governance. | C22-C23 define acquisition and cost/SLA policies; E17-E18 implement action records and gates. |
| Self-FMEA and calibration | Build new quality machinery. | Formal invariants, audit verifier, attestation, source truth, calibration, and memory foundations exist. | C24-C25 focus on integration, soft gates, complexity, review effectiveness, longitudinal calibration, and balanced memory; E19-E21 implement stable parts. |
| Evaluation | Build all probes from scratch. | Challenge factory and authority spoofing tests cover many probes already. | C26 maps existing coverage, adds semantic completeness and anti-laundering probes; E22 implements only missing packs. |

The largest genuinely build-new or bridge-new surfaces are:

- concept spine as namespaced cross-producer authority (C6-C8, E6-E7);
- lineage-aware effective independence and conflict-to-claim semantics (C13-C14, E13);
- evidence acquisition strategy planning above VOI (C22, E17);
- longitudinal calibration and balanced memory above point-in-time evaluators (C25, E20-E21);
- unified honest-diagnostics `can_i_closeout` substrate (C3, E3);
- analytics-to-ClaimRecord bridge (C9-C10, E8);
- typed multi-audience `PolicyDesignCaseProjection` (C16, E4-E5);
- rule-semantics evolution and partial reissue (C20-C21, E14-E15);
- run-cost and degradation-SLA governance (C23, E18);
- participation provenance (C19, E11/E22).

The largest "stop reopening this" surfaces are:

- SACM/CAE/GSN mapping in `assurance_case.py` (C15 starts from it);
- projection-only and public-export guardrails (C16/E4-E5 extend them);
- audience-tiered `DecisionGradeExport` publishing (C16 bridges it);
- claim-family predicates and authority classifications (C1-C2 baseline them);
- temporal logic as obligation language (C5 maps to it);
- IR analytics proof certificates (C9/E8 bind them);
- Data Forge artifact/snapshot/release/read-API provenance (C20/E16 bind it);
- DDM data-quality/performance/shift/readiness/source-invalidation paths (C20/E15 extend coverage);
- Fabric SourceContract schema, quality, replay, lineage, access, SLA, retention, and fetch-time validation (C22/E10 reuse it);
- BERL explanation bundle and warrant reliability gates (C15 starts there);
- deterministic audit package assembly, PROV, and SLSA/in-toto surfaces (C3/C16/E3-E5 ingest them);
- finite-state closeout invariants in `formal_invariants.py` (C24 extends them).

## Corpus Budget And Reviewer Topology

The plan uses one shared corpus, but different conceptual tasks consume
different slices. This avoids silently asking the same reviewers to annotate
everything.

| Corpus slice | Size target | Used by | Reviewer profile |
| --- | --- | --- | --- |
| Deep pilot | 10 cases, two reviewers each | C0-C3, C9-C12 | policy generalist plus domain-aware reviewer |
| Admissibility pair set | 30-50 cases, 20-40 claim-evidence pairs per case | C1-C3, C9-C11, C15 | evidence/method reviewer plus legal or governance reviewer |
| Facet saturation corpus | about 200 policies | C4-C5 | policy analyst annotators with sampling audit |
| Historical failure corpus | 30-60 failures/audits | C5, C22-C24, C26 | implementation/audit reviewers |
| Contested/tradeoff/participation corpus | 20-40 contested cases | C17-C19 | governance, legal, stakeholder/participation reviewers |
| Longitudinal calibration corpus | cross-run closed cases as they accumulate | C20-C25, C26 | calibration and runtime-quality reviewers |

Reviewer topology:

- Use overlapping reviewers for the deep pilot so disagreement can calibrate
  the annotation guide.
- Use partially disjoint reviewers for later tasks to reduce carryover bias.
- Record reviewer role, expertise basis, conflicts, and disagreement category.
- Never collapse expert disagreement into one hidden gold label when the
  disagreement is substantive.

## Operating Model Open-Question Coverage

The operating model currently lists 29 open questions. This plan maps each one
to the conceptual task that should resolve it or make it implementation-ready.

| Open question | Primary task | Secondary tasks |
| --- | --- | --- |
| 1. Concept spine physical registry vs reconciled view | C6 | C20, E6-E7 |
| 2. Default option comparison by authority level | C10 | C17-C18, C22 |
| 3. Mandatory distributional-effect categories | C4 | C5, C18 |
| 4. Institutional competence model | C7 | C2, C5, C22 |
| 5. Raw prompts vs hashes in provenance | C24 | C12, C20 |
| 6. External dependency rights blockers | C2 | C24, C26 |
| 7. Public contestability contract | C17 | C16, E4-E5 |
| 8. Ex-post observation window | C25 | C20 |
| 9. Calibration metrics blocking high-authority runs | C25 | C2, C26 |
| 10. Structured expert judgement protocols | C17 | C2, C24 |
| 11. Multi-jurisdiction norm conflicts | C7 | C2, C17 |
| 12. Human-team benchmark tasks | C26 | C25 |
| 13. SACM/CAE/GSN profile semantics and exporters | C15 | C0, C16, E4-E5 |
| 14. Acceptable assurance deficits by mode | C2 | C20, C27 |
| 15. Human-review telemetry | C24 | C17 |
| 16. Requester-capture challenge blockers | C24 | C12, C17 |
| 17. Formal substrate invariants and unified closeout substrate | C3, C24 | E3, E19 |
| 18. Portfolio maturity by authority level | C2 | C13, C25 |
| 19. Effective independent evidence collapse | C13 | C5, C26 |
| 20. Information saturation stopping rules | C22 | C13, C26 |
| 21. Evidence-synthesis certainty framework | C13 | C2, C26 |
| 22. Scholar evidence requirements by authority level | C2 | C13, C26 |
| 23. Authoritative module owners | C0 | C27, E23 |
| 24. Agent-simulation independence | C13 | C26, E12-E13 |
| 25. `assurance_case.py` canonical field split | C0, C15 | C16, E4 |
| 26. Authority levels to governance/execution profiles | C2 | C0 |
| 27. DDM mandatory post-publication events and detectors | C20 | C25, E15 |
| 28. BERL reviewer/blocking thresholds | C2, C15 | C9, C25 |
| 29. Data Forge snapshot provenance and read-API contracts | C20 | C0, C11, C22, E16 |

## Minimum Record-Family Coverage Map

The operating model has more record families than the first draft covered. The
current conceptual and engineering tasks intentionally cover every family.

| Record family | Conceptual tasks | Engineering translation |
| --- | --- | --- |
| `intent_authoring_and_capture_risk.v1` | C12, C24 | E22 |
| `capability_mode_and_fallback_selection.v1` | C0, C2 | E0, E2-E3 |
| `concept_and_jurisdiction_spine.v1` | C6-C8 | E6-E7, E9 |
| `legal_authority_and_competence.v1` | C2, C7 | E9 |
| `data_source_semantic_lineage.v1` | C2, C6, C11, C22 | E10, E16-E17 |
| `scholar_academic_evidence.v1` | C2, C13, C26 | E11, E13, E22 |
| `numeric_time_and_geography_semantics.v1` | C11 | E9-E16 as applicable |
| `method_selection_and_validity.v1` | C9 | E12 |
| `evidence_portfolio_and_synthesis.v1` | C13-C14 | E8, E13 |
| `structured_judgement_and_consultation.v1` | C17, C19 | E4-E5, E11, E22 |
| `options_objectives_and_tradeoffs.v1` | C10, C18 | E8, E4-E5 |
| `claim_argument_evidence_case.v1` | C9-C10, C15 | E8, E12, E4-E5 |
| `implementation_monitoring_and_evaluation.v1` | C20, C22-C25 | E15, E17-E21 |
| `human_oversight_independence_and_review.v1` | C24 | E19 |
| `integrity_self_fmea_and_maturity.v1` | C24 | E19, E22 |
| `lifecycle_ex_post_and_calibration.v1` | C20-C21, C25 | E14-E16, E20-E21 |
| `publication_trust_and_external_governance.v1` | C3, C16-C17, C24 | E3-E5, E19, E23 |
| `best_in_class_benchmarking.v1` | C25-C26 | E20, E22 |
| `formal_substrate_invariant_spec.v1` | C3, C24 | E3, E19 |

## Load-Bearing Research Kernels

The plan is intentionally broad, but three conceptual kernels carry most of the
architectural weight. They should receive the earliest and deepest review.

1. **Admissibility, authority, status, and closeout:** C1-C3 decide whether a
   claim can be supported, published, degraded, contested, blocked, or closed
   out. Without this kernel, all later schemas become box-ticking.
2. **Claim-bound evidence and producer coordination:** C6-C14 decide how Lex,
   Fabric, Scholar, Foundry, Scientist, and IR analytics speak the same
   concept language and bind their outputs into claims, portfolios, conflicts,
   methods, and limitations. Without this kernel, strong components remain
   detached sidecars.
3. **Evaluation, lifecycle, and self-correction:** C20-C26 decide how cases are
   revalidated, how rule changes affect past closeout, how warnings escalate,
   how memory/calibration shape future runs, and how semantic adequacy is
   measured. Without this kernel, the system cannot learn or remain honest.

Engineering should not start broad implementation until these kernels have
corpus-backed decisions or explicitly scoped experimental boundaries.

## Proposed Research Corpus

The research corpus should be intentionally diverse and adversarial. It should
not be optimized around current PolicyOS strengths.

Minimum corpus slices:

- emergency MSME credit or grant support;
- public health intervention;
- housing subsidy or rent control;
- tax relief or tax enforcement;
- school funding or education access policy;
- climate adaptation or emissions regulation;
- labor market activation or wage subsidy;
- migration or displacement assistance;
- public safety or security regulation;
- digital public service or identity policy;
- infrastructure prioritization;
- social protection targeting.

For each case, record:

- jurisdiction and policy time;
- instrument type;
- target and affected populations;
- legal authority claims;
- data sources;
- method claims;
- implementation pathway;
- participation or consultation evidence;
- monitoring and lifecycle rules;
- observed outcome or known failure where available;
- controversy or contested evidence;
- public artifact refs.

---

## Annotation Protocol Draft

Each annotated policy case should include:

```yaml
case_id: string
jurisdiction: string
policy_time: string
policy_instrument:
  instrument_type: string
  delivery_channel: string
  funding_channel: string | null
targeting:
  targeting_type: string
  beneficiary_classes: [string]
  affected_populations: [string]
claims:
  - claim_id: string
    claim_type: string
    text_ref: string
    scope:
      population: [string]
      geography: [string]
      time_period: string
      institution: [string]
    evidence_refs: [string]
    method_refs: [string]
    legal_refs: [string]
    participation_refs: [string]
    risks: [string]
    tradeoffs: [string]
    admissibility_label: string
    limitation_refs: [string]
    contestability_status: string
obligations:
  - obligation_id: string
    generated_from_facets: [string]
    required_evidence_family: string
    status: string
    reviewer_notes: string
known_outcomes_or_failures:
  - finding_id: string
    source_ref: string
    would_prior_obligation_have_flagged: boolean | null
```

This schema is only a research annotation draft. It should not be promoted to
runtime code until C1, C2, C9, C11, and C26 validate it against real cases.

---

## Research And Engineering Execution Plan

This plan now has two first-class task families.

1. **Conceptual research tasks (`C`)** decide the semantics: what PolicyOS
   should mean by admissible, authoritative, independent, contested, stale,
   publishable, complete, proportional, or externally accountable. These tasks
   produce formal definitions, decision tables, corpus-backed memos, ADR drafts,
   benchmark protocols, and negative controls. They are deeply informed by the
   codebase, but they do not implement unsettled theory.
2. **Engineering translation tasks (`E`)** turn stable research decisions into
   PolicyOS capability chains: typed artifact, producer, persisted event or
   artifact, orchestration bridge, consumer, verification, external/audit/API/
   dashboard surface or explicit out-of-scope, and negative/e2e semantic test.

Use this rule:

| If the task asks... | Treat it as... | Output |
| --- | --- | --- |
| What should a status, claim, time role, authority, concept, or evidence relation mean? | Conceptual research | Formal model, decision table, ADR draft, corpus-backed memo |
| Which existing module already encodes part of the answer? | Code-informed research baseline | Capability map, behavior extraction, reuse classification |
| How should producers coordinate before evidence is emitted? | Conceptual protocol first | Producer-handshake and concept-spine protocol |
| Can this behavior be demonstrated with a failing and passing runtime path today? | Engineering translation | Code, persisted artifact, consumer, surface, negative/e2e test |
| Is a task mostly wiring stable contracts through known modules? | Engineering translation | Producer-consumer bridge and verification |
| Is a task deciding public semantics for different audiences? | Conceptual surface design first | Audience contract before DTO/client/dashboard work |

### Conceptual Research Tasks

Each conceptual task is standalone. The numbering is intentionally global and
sequential rather than nested. A researcher should start from the code anchors
listed here and in the dense context section; no task is allowed to proceed as
if PolicyOS were a blank slate.

#### C0 - Capability Baseline, Canonical Paths, And Corpus Frame

**Purpose:** establish what is real, partial, typed-only, projection-only,
shimmed, or greenfield before any new theory or implementation is proposed.

**Code-informed starting point:** `runtime/quality/*`,
`scientist/policy_design/*`, `scientist/evidence/claims/*`, research DAG,
VOI, Foundry consensus/equivalence, DOE, IR governance, calibration, DDM, BERL,
core audit, Lex, Fabric, Scholar, Foundry, and `architecture/shims.toml`.

**Research work:**

- Inventory existing modules against every conceptual and engineering task.
- Extract current schemas, statuses, validator decisions, failure codes,
  authority levels, record shapes, and public/export shapes.
- Classify each surface as `implemented`, `partially implemented`,
  `implemented_but_not_orchestrated`, `typed_only`, `projection_only`,
  `compatibility_shim`, or `greenfield`.
- Record canonical modules versus compatibility shims and behavioral legacy
  modes. Later tasks must cite canonical paths unless they explicitly study a
  shim or legacy behavior.
- Record existing schema/evolution dialects: runtime `schema_compat`, Fabric
  connector evolution, Data Forge schema evolution/migrations, IR migrations,
  research DAG replay, and claim lifecycle.
- Record local time semantics: runtime `TemporalScope`, Fabric bitemporal
  valid/transaction time, Lex/legal `as_of`, policy effective dates, Scholar
  freshness, Data Forge snapshot/release time, DDM detection time, claim
  registry time, model time, and replay time.
- Record external/public surfaces and type depth: runtime
  `policy_design_case_projection`, generated API client types, dashboard
  validators, public export, audit verifier, and `DecisionGradeExport`.
- Build the corpus map: deep pilot, admissibility pairs, facet saturation,
  historical failures, contested/tradeoff/participation cases, and
  longitudinal calibration cases.

**Output:** `docs/research/universal-policy-design/capability-baseline-map.md`
and annotation/corpus guide.

**Acceptance:** no later task may introduce a canonical object without naming
what it reuses, extends, consolidates, or replaces.

#### C1 - Status Algebra And Soft-Gate Semantics

**Purpose:** define how local statuses compose without creating a single brittle
"god enum".

**Code-informed starting point:** `scorecard.py`, `approval.py`,
`authority.py`, `semantic_binding.py`, `phase_barriers.py`, `run_state.py`,
`claim_support.py`, `citation_faithfulness.py`, `decision_validity.py`,
`transportability.py`, and `proof_composability.py`.

**Research work:**

- Baseline existing local status algebras: scorecard pass/warn/fail,
  approval readiness, authority blocking/non-overridable roles, semantic
  binding pass/blocked/fail, phase barrier pass/blocked/skipped,
  claim support/publishability, citation labels, decision-validity states,
  transportability status, proof-composability status, and readiness ranks.
- Define a composed status lattice over severity, blockingness,
  overridability, authority role, evidence class, publication scope,
  readiness cap, degradation/proxy status, review action, and closeout effect.
- Reconcile duplicated readiness and validity vocabularies across Scientist,
  claim validation, runtime quality, and continuous governance.
- Define warning/soft-gate lifecycle rules: owner, age, escalation, acceptable
  deficit policy, review action, publication effect, closeout effect, and
  aggregation behavior.
- Build decision tables for mixed outcomes such as `SUPPORTED` plus
  `partially_supports`, degraded transport plus strong data evidence,
  warning validity plus publication request, and semantic binding fail plus
  dashboard projection.

**Output:** status lattice ADR draft and mixed-status decision table.

**Acceptance:** current local behavior can be reproduced before stricter rules
are proposed, and every warning-like state has an owner and escalation policy.

#### C2 - Admissibility And Authority-Level Calculus

**Purpose:** decide when evidence is admissible for a claim under research,
governed, or production authority.

**Code-informed starting point:** `claim_support.py`,
`citation_faithfulness.py`, `authority.py`, BERL explanation reliability,
Fabric `SourceContract`, Data Forge artifacts/snapshots, audit verifier,
Lex applicability reports, semantic binding, and scorecard gates.

**Research work:**

- Treat existing support predicates and family rules as the empirical baseline.
- Define what turns a present predicate into authority-bearing evidence:
  freshness, lineage, quality tier, legal competence, scope match, numeric/time
  semantics, same-input closure, source truth, and independence.
- Define claim-type by authority-level portfolio shapes.
- Define acceptable, reviewable, and non-overridable deficits by mode.
- Define graded legal admissibility states for Lex and downstream readers:
  `admissible`, `context_only`, `proxy_with_limitation`, `contested`,
  `blocked`, and `out_of_scope`.
- Define composition semantics: when several weak evidence lines support,
  remain weak, conflict, or collapse through dependence.
- Test the model against the first 10 annotated cases and at least 20
  additional claim-evidence pairs.

**Output:** admissibility decision table and authority-level ADR draft.

**Acceptance:** direct, proxy, context-only, contested, blocked, and
out-of-scope evidence can be classified without domain-specific hacks.

#### C3 - Unified Closeout Substrate Semantics

**Purpose:** define the single closeout answer that integrates fragmented
honest-diagnostics modules.

**Code-informed starting point:** `formal_invariants.py`, `event_log.py`,
`attestation.py`, `source_truth.py`, `metamorphic_controls.py`,
`performance_budget.py`, `closeout_compatibility.py`, `approval.py`, audit
verifier reports, scorecard, semantic binding, and public export guards.

**Research work:**

- Treat `closeout_compatibility` and `check_can_i_closeout.py` as inputs, not
  the whole closeout answer.
- Define the conceptual decision:
  `can_i_closeout(run_id) = invariants + event reconciliation + attestation +
  source truth + metamorphic controls + performance/cost budget + schema/git/
  reader compatibility + semantic binding + approval/publication state`.
- Define which module owns each sub-decision, which failure codes are terminal,
  and which can be accepted only as typed deficits.
- Define how audit verifier outputs become publication-trust and closeout
  inputs without replacing runtime authority envelopes.
- Define how root-cause class, first failing producer, replay refs, code
  revision, reader-gate version, and public projection state appear in one
  answer.

**Output:** closeout substrate ADR and operator-facing decision model.

**Acceptance:** a researcher can answer "can this run close out?" from one
conceptual surface without losing module-specific detail.

#### C4 - Universal Facet Grammar

**Purpose:** define the universal policy-design fields that replace brittle
handwritten domain adapters.

**Code-informed starting point:** `ProblemFrame`, `PolicySpec`,
`PolicyCandidateSchema`, `objectives.py`, `critic.py`, `search.py`, temporal
logic, and IR governance enums.

**Research work:**

- Enumerate facet-like enums and typed fields already present in code.
- Align canonical facet names with `ProblemDomain`, `NormativeOutcomeChannel`,
  `ConstraintType`, `FidelityLevel`, `PolicyLayerLevel`, and temporal
  evaluation scopes.
- Identify open-string fields requiring controlled vocabularies:
  `instrument_type`, `delivery_channel`, `funding_channel`, `authority_type`,
  and canonical `risk_type`.
- Reconcile risk facets with deterministic `ConstraintCritic` failure classes
  and `challenge_factory.py` challenge classes.
- Run saturation analysis over the facet corpus after code-enum baseline is
  complete.

**Output:** facet taxonomy memo and saturation report.

**Acceptance:** the taxonomy represents policies across at least 8 domains
without introducing domain adapters or duplicating existing enums.

#### C5 - Obligation Rule Lifecycle And Governance

**Purpose:** replace domain templates with fewer governed obligation rules.

**Code-informed starting point:** `ir/governance/temporal_logic.py`,
`ConstraintCritic`, `challenge_factory.py`, policy-design critics, and
historical failure corpora.

**Research work:**

- Treat LTL/CTL/MTL temporal logic as the default formal language unless it
  proves insufficient.
- Map obligation classes to temporal patterns: `do_X`, `dont_X`, `X_before_Y`,
  `eventually_Z`, `always_P`, `until_condition`, branching forecast condition,
  and bounded-window monitoring.
- Seed rules from expert reading and prior art, then mine candidate rules from
  historical failures.
- Compare LLM-generated obligations against deterministic critic outputs,
  expert rules, and historical failure rules.
- Define rule status, provenance, owner, scope, authority level, evidence
  basis, versioning, deprecation, and closeout effect.

**Output:** obligation rule lifecycle ADR and first governed rule taxonomy.

**Acceptance:** no obligation can become closeout-blocking without status,
provenance, version, scope, owner, and evidence basis.

#### C6 - Concept Identity And Spine Semantics

**Purpose:** define the missing abstraction that reconciles meaning across
producers.

**Code-informed starting point:** Fabric entity resolution, Scientist
cross-graph, IR cross-graph analytics, IR linker, normative arbitration, Lex,
Foundry, Scholar, and runtime semantic binding.

**Research work:**

- State what existing primitives solve and do not solve: pairwise matching,
  SCM fragment composition, option-outcome arbitration, evidence conflict, and
  semantic closure.
- Define same concept, related concept, conflicting concept, unresolved
  concept, scope-shifted concept, and authority-shifted concept.
- Test reconciliation across policy terms, metric ids, dataset columns, legal
  concepts, method requirements, population predicates, geography predicates,
  and time predicates.
- Define namespaced concept authority across policy term, metric, column, norm,
  method, population, geography, and time.
- Decide whether the concept spine is one physical registry or a per-run
  reconciled authority artifact over existing registries.

**Output:** concept-spine semantics model.

**Acceptance:** unresolved or conflicting concepts become first-class blockers
before PDC closeout.

#### C7 - Legal Authority, Jurisdiction, And Institutional Competence

**Purpose:** formalize legal authority beyond set-membership jurisdiction.

**Code-informed starting point:** Lex normpack applicability reports,
query normalization, policy composition, legal Data Forge temporal extraction,
Lex `as_of`, and `PolicyCompositionPlan`.

**Research work:**

- Define hierarchical jurisdiction fallback and blockers.
- Define temporal jurisdiction changes and legal effective-time semantics.
- Define authority hierarchy across federal/state/local/institutional layers.
- Define legal authority-type facets: `implementing`, `delegating`, `enabling`,
  `funding`, `oversight`, and `appeals_or_contestability`.
- Define multi-jurisdiction legal-concept conflict separately from generic
  evidence conflict.
- Decide how PolicyCompositionPlan constraints should be enforced inside Lex
  and PDC legal authority records.

**Output:** legal authority and jurisdiction ADR.

**Acceptance:** Lex cannot satisfy serious legal authority through generic
jurisdiction membership when hierarchy, temporal competence, or implementing
authority is unresolved.

#### C8 - Producer Handshake Protocol

**Purpose:** make producers coordinate before post-hoc conflict detection.

**Code-informed starting point:** runtime producer-spine hooks, semantic
binding ledger, `nl_pipeline.py`, Lex/Fabric/Foundry/Scientist spine records,
Scholar spine, and cross-graph conflict utilities.

**Research work:**

- Treat existing runtime producer-spine and semantic-binding hooks as a
  read-context and closeout substrate, not the full protocol.
- Define what each producer must declare before emission: consumed concept ids,
  consumed requirement ids, emitted refs, selected/rejected/blocked bindings,
  conflict checks, authority role, and scope/time/geography assumptions.
- Define when pre-emission coordination is required versus when post-hoc
  conflict detection is enough.
- Define how producer handshake records feed semantic binding, claim registry,
  readiness, replay, inspection, and public projection.

**Output:** producer-handshake protocol spec.

**Acceptance:** producer coordination does not depend on one service-local NL
pipeline assembly path.

#### C9 - Claim Taxonomy And Method Compatibility

**Purpose:** decide which methods and proof surfaces can support each claim
type.

**Code-informed starting point:** `ClaimType`, `ClaimSupportStatus`,
`ClaimPublishability`, `DecisionReadiness`, `AppendOnlyClaimLedger`,
`claim_support.py`, and IR analytics certificates.

**Research work:**

- Treat existing claim records and support predicates as anchors, not blank
  slate taxonomy.
- Treat IR analytics outputs as the method-authority baseline: partial
  identification, recoverability, path-specific effects, transportability,
  negative certificates, dual certificates, certified tightening, proof
  composability, fairness decomposition, strategic equilibrium, and causal
  ensembles.
- Define claim-type to method compatibility using existing support predicates
  and IR statuses as seeds.
- Define how generic method labels are rejected under serious expectations.
- Define runtime assumption-validation needs for methods currently checked
  offline.
- Define claim uncertainty refs for forecasts, causal claims, distributional
  claims, welfare claims, and simulation-backed implementation claims.

**Output:** claim-method compatibility matrix.

**Acceptance:** method-claim mismatch can be blocked before final policy
drafting.

#### C10 - Counterfactual Baselines And Alternative Comparison

**Purpose:** make baselines and rejected alternatives first-class policy claims.

**Code-informed starting point:** Claim records, `HarmEnvelope`, adversarial
scenario proposals, IR causal analytics, policy-design output, and normative
arbitration.

**Research work:**

- Define no-action, status quo, business-as-usual, and named alternative
  baselines.
- Define when a shift/noise/outlier/missing/targeting-fragility scenario can
  act as a counterfactual or fragility baseline.
- Define evidence requirements for claims that selected option X is superior
  to alternative Y.
- Define rejected-option records and reasons: inferior evidence, dominated
  frontier, legal blocker, implementation infeasibility, value choice, or
  accepted deficit.

**Output:** baseline and alternative-comparison model.

**Acceptance:** a policy recommendation cannot claim superiority by presenting
only evidence for the selected option.

#### C11 - Numeric, Time-Role, And Geographic Semantics

**Purpose:** make unit, currency, time, geography, and freshness mismatches
visible and authority-aware.

**Code-informed starting point:** production-data contract metadata, IR
temporal logic, runtime `TemporalScope`, Fabric bitemporal fields, Lex `as_of`,
Scholar freshness, Data Forge snapshot/release time, DDM detection time,
metric registry semantics, and Foundry equivalence tolerance budgets.

**Research work:**

- Inventory unit, currency, price-base, exchange-rate, inflation, calendar,
  geography, freshness, retention, and coverage semantics.
- Define canonical time roles: legal as-of, legal effective, data observation,
  data valid, transaction, ingestion, publication, policy effective, forecast,
  model, detection, claim registry, replay, freshness deadline, and retention
  deadline.
- Define mismatch outcomes: `admissible`, `transform_required`,
  `projection_required`, `limitation_required`, and `blocked`.
- Define authority-level thresholds for transformable versus blocking mismatch.
- Define how transformations create new lineage and authority refs.

**Output:** numeric/time/geography semantics ADR.

**Acceptance:** time, unit, currency, calendar, geography, and freshness
mismatches cannot silently pass as generic scope matches.

#### C12 - LLM Boundary And Candidate-To-Authority Firewall

**Purpose:** decide what LLMs may propose and what they may never authorize.

**Code-informed starting point:** `scientist/policy_design/*`,
`ConstraintCritic`, `ScenarioAdversaryWorker`, `LLMBudgetEnforcer`,
`prompt_tool_ledger.py`, publishing, and claim validation.

**Research work:**

- Canonicalize the LLM-plus-deterministic-fallback pattern.
- Use deterministic `ConstraintCritic` outputs as baseline risk/constraint
  coverage.
- Evaluate LLM formulator and critic variants on annotated cases.
- Measure omissions, false positives, hallucinated authority, and severity
  calibration.
- Define source classifications such as `llm_candidate`, `llm_critic`,
  `llm_drafter`, and `deterministic_producer`.
- Define which LLM outputs may become candidate obligations, review prompts,
  typed blockers, limitations, or rejected speculation.

**Output:** LLM boundary evaluation protocol and speculation-firewall ADR.

**Acceptance:** LLM content cannot become law, data, stakeholder preference,
method authority, or closeout authority without producer validation.

#### C13 - Effective Independence And Evidence-Line Collapse

**Purpose:** make evidence strength depend on independence, not raw count.

**Code-informed starting point:** Foundry consensus/equivalence,
`proof_composability.py`, `causal_ensemble.py`, Scholar bundles, Fabric
lineage, agent-simulation truth manifests, legal source refs, and prompt/model
paths.

**Research work:**

- Define evidence-line identity.
- Define collapse causes: shared primary source, transformation lineage,
  author pool, institutional pool, identification strategy, method family,
  preprocessing, prompt/model path, legal source, and shared assumptions.
- Reuse proof composability statuses `REUSABLE`, `REVALIDATE`, `REDERIVE`, and
  `UNKNOWN` as certificate replay anchors.
- Extend Scholar independence over shared authors, institutions, datasets,
  replication lineage, review status, and citation-network dependence.
- Define agent-simulation independence requirements: mechanism parameter
  assumption refs, calibration source, sensitivity bounds, and simulation
  lineage.
- Define ensemble-member independence so clustered model families do not
  inflate support.
- Define `effective_independence(line_a, line_b) -> [0, 1]` and portfolio
  aggregation rules.

**Output:** effective-independence algebra and collapse examples.

**Acceptance:** examples exist where raw source count rises but effective
independent support does not.

#### C14 - Evidence Conflict And Counterevidence Semantics

**Purpose:** make conflicts first-class claim and portfolio facts.

**Code-informed starting point:** `ConflictDetector`, cross-graph compiler,
semantic binding, claim argument, evidence portfolio, citation faithfulness,
and readiness gates.

**Research work:**

- Define conflict types: empirical, legal, academic, methodological,
  jurisdictional, scope, time, authority, participation, and implementation.
- Define how conflict affects independence, support strength,
  counterevidence, rebuttal requirements, limitations, and readiness caps.
- Define when conflict is resolvable by new evidence, method arbitration,
  legal hierarchy, scope narrowing, or human/governance decision.
- Define how post-hoc conflict detection and pre-emission producer handshakes
  interact.

**Output:** conflict-to-claim semantics memo.

**Acceptance:** conflict findings can be projected into claim registry,
portfolio, semantic binding, readiness, and public PDC surfaces.

#### C15 - Argument, Warrant, And Assurance Profile Semantics

**Purpose:** refine argument quality over the existing SACM/CAE/GSN mapping.

**Code-informed starting point:** `assurance_case.py`, `claim_argument.py`,
BERL explanation bundles, `explanation_reliability.py`, evidence portfolio,
and semantic binding.

**Research work:**

- Treat the multi-formalism mapping in `assurance_case.py` as the baseline.
- Validate completeness against SACM, GSN, and CAE concepts.
- Formalize warrant semantics beyond free text: typed assumptions,
  applicability predicates, confidence/reliability refs, BERL refs, and
  limits.
- Define minimum argument graph shape for major claims.
- Identify exporter gaps, including SACM XML or another interchange artifact
  if needed.

**Output:** argument-profile ADR and warrant semantics model.

**Acceptance:** every major claim can be represented as claim -> argument ->
warrant -> evidence -> authority -> readiness, or fails with a typed gap.

#### C16 - Multi-Audience Policy Design Case Surface Semantics

**Purpose:** decide what PUBLIC, REVIEWER, EXPERT, and MACHINE consumers should
see.

**Code-informed starting point:** runtime `policy_design_case_projection`,
`projection_semantics.py`, `public_export.py`, `DecisionGradeExport`, runtime
API contracts, generated TypeScript client, dashboard validators, audit
package/verifier, and public run/export surfaces.

**Research work:**

- Define a typed `PolicyDesignCaseProjection` contract with claim graph,
  warrant structures, authority summary, readiness gates, approval decision,
  publication status, contested records, deficit register, invariants, and
  machine-readable authority gaps.
- Define per-audience fields, redactions, limitations, evidence refs, source
  truth conflicts, audit-verifier results, and machine schema commitments.
- Define typed projection failure records for projection exceptions, missing
  projection, missing audit-verifier ingestion, dashboard/API drift, and public
  export bypass attempts.
- Define how generic run/artifact endpoints link to typed projection without
  minting authority.

**Output:** multi-audience PDC surface contract.

**Acceptance:** external accountability does not require traversing raw
artifact blobs or trusting generic dict payloads.

#### C17 - Contestability And Disagreement Formalism

**Purpose:** preserve disagreement without pretending it is missing evidence or
final failure.

**Code-informed starting point:** claim support states, argument graphs,
`ConflictDetector`, normative arbitration, residual dissent, and readiness.

**Research work:**

- Define disagreement categories: empirical, methodological, normative, scope,
  authority, participation, and implementation.
- Define closeout states for contested but publishable cases.
- Define reconciliation strategies and when disagreement requires research,
  governance choice, scope split, legal hierarchy, or public contestability.
- Map contested records to argument graph, claim registry, public projection,
  and lifecycle monitoring.

**Output:** contestability model.

**Acceptance:** admissible disagreement can remain contested without being
collapsed into pass, fail, or missing data.

#### C18 - Tradeoff, Welfare, And Value-Choice Representation

**Purpose:** separate computed frontier facts from governance/value choices.

**Code-informed starting point:** `normative_arbitration.py`,
`PolicyFrontierReport`, option-outcome matrices, rights audit entries, Foundry
welfare bounds, and social-weight schedules/manifests.

**Research work:**

- Define multi-objective tradeoff representation without forced aggregation.
- Define Pareto/frontier facts and value-choice decision points.
- Define social-weight provenance: who chose weights, under which mandate, at
  what time, with which affected groups, dissent, and review status.
- Define welfare audit trail and claim linkage.
- Define when scalar welfare aggregates are insufficient.

**Output:** welfare/tradeoff provenance ADR.

**Acceptance:** welfare aggregation cannot hide social-weight provenance,
Pareto-dominated alternatives, or explicit normative decisions.

#### C19 - Participation Provenance And Attribution

**Purpose:** prevent speculation about affected-person preferences or
legitimacy.

**Code-informed starting point:** claim provenance, publishing tiers,
participation gaps in PDC records, public export, and governance review.

**Research work:**

- Define consultation mode, representativeness, affected group mapping,
  verification, aggregation, dissent, and claim linkage.
- Distinguish survey, deliberative panel, testimony, consultation summary,
  agency record, individual quote, and LLM speculation.
- Define minimum provenance for preference, legitimacy, implementation
  feasibility, contestability, and harms claims.
- Define public/redacted projection obligations and privacy constraints.

**Output:** participation provenance schema.

**Acceptance:** affected-person claims require participation provenance or a
typed limitation/blocker.

#### C20 - Lifecycle Dependency And Revalidation Semantics

**Purpose:** make Policy Design Case a living object instead of a frozen memo.

**Code-informed starting point:** `AppendOnlyClaimLedger`, claim lifecycle
actions, DDM events/detectors, continuous governance monitors/reissue,
research-DAG replay/invalidation/comparison, and source invalidation bridges.

**Research work:**

- Define claim-to-evidence back-pointers.
- Define staleness and revalidation triggers for new evidence, legal changes,
  source invalidation, calibration drift, fairness drift, participation drift,
  implementation incidents, policy context drift, and DDM root causes.
- Define DDM event to claim-lifecycle transitions: stale, blocked, invalidated,
  superseded, review-required, reissued, or withdrawn.
- Define partial-scope reissue: affected claim ids, unchanged records,
  superseded refs, public diff refs, and publication state.
- Define runtime-owned lifecycle records.

**Output:** lifecycle dependency and revalidation graph.

**Acceptance:** new evidence or drift can be mapped to affected claims,
records, exports, and public status.

#### C21 - Rule Evolution, Replay, And Legacy Retirement

**Purpose:** preserve past-case meaning when schemas, rules, taxonomies, or
legacy behavior change.

**Code-informed starting point:** `schema_compat.py`, schema compatibility TOML,
Fabric connector evolution, Data Forge schema evolution/migrations, IR
migrations, research-DAG replay, claim lifecycle, and `architecture/shims.toml`.

**Research work:**

- Distinguish ABI/schema versioning from rule-semantics evolution.
- Define rule family, rule version, logic hash, code revision, owner,
  authority level, migration policy, replay mode, and stricter-rule detection.
- Define `rule_version_ref` and `taxonomy_version_ref` on closed cases, claim
  records, evidence portfolios, obligation rules, admissibility decisions,
  method-claim matrices, and PDC gates.
- Define old-logic replay, migrated replay, grandfathering, partial migration,
  and mandatory public revalidation.
- Define retirement criteria for import-path shims and behavioral legacy modes.

**Output:** rule-evolution and legacy-retirement policy.

**Acceptance:** rule changes cannot silently reinterpret a past PDC.

#### C22 - Evidence Acquisition Decision Theory And VOI

**Purpose:** decide the next best action after evidence is missing or blocked.

**Code-informed starting point:** VOI scheduler/calibration, Fabric
`SourceContract`, Lex corpus expansion, Scholar retrieval, Data Forge snapshot
builds, Foundry methods, performance budgets, and degradation module.

**Research work:**

- Treat VOI as ranker/decision ledger, not acquisition orchestrator.
- Define acquisition strategies: public registry, agency request, survey,
  consultation, legal corpus expansion, academic retrieval, production
  snapshot build, proxy with degraded authority, accepted deficit, rerun, and
  closeout block.
- Define cost, authority, feasibility, time, privacy/legal, and degradation
  profiles for each strategy.
- Define when to block, degrade, acquire, accept deficit, rerun, or publish
  with limitation.
- Define how strategy outcomes feed VOI calibration and future priors.

**Output:** acquisition strategy taxonomy and VOI decision policy.

**Acceptance:** a blocker can produce an explicit next action, not only a
failed status.

#### C23 - Run Cost, Budget, And Degradation-SLA Semantics

**Purpose:** distinguish latency observability from production cost and SLA
governance.

**Code-informed starting point:** `performance_budget.py`, `degradation.py`,
provider preflight, local prod-debug probe, VOI economics, runtime canary
matrix, and workflow retry/timeout paths.

**Research work:**

- Define compute-dollar, provider API call, token, embedding/search, wall-clock,
  retry, and acquisition budgets.
- Define when provider degradation, source unavailability, workflow slowdown,
  or budget exhaustion becomes warning, limitation, acquisition action, rerun,
  or closeout blocker.
- Define authority-level-dependent thresholds.
- Define how cost/SLA signals enter acquisition, closeout, public projection,
  and operator dashboards.

**Output:** run-cost and degradation-SLA policy.

**Acceptance:** cost and degradation cannot be confused with ordinary latency
observability.

#### C24 - Self-FMEA, Soft-Gate Policy, Review Effectiveness, And Complexity Budget

**Purpose:** model the failure modes of the case machinery itself.

**Code-informed starting point:** `formal_invariants.py`, `invariants.py`,
phase barriers, SameInputClosure, source truth, attestation, metamorphic
controls, prompt/tool ledger, human-review VOI escalation, audit verifier, and
scorecard.

**Research work:**

- Baseline the five model-checked invariants: `authority_ordering`,
  `phase_barriers`, `same_input_closure`, `cas_event_reconciliation`, and
  `terminal_readiness`.
- Identify temporal/liveness properties not covered by current finite-state
  checks.
- Model adversarial failures: prompt injection, requester capture, schema
  gaming, authority spoofing, proxy laundering, scope inflation, false
  convergence, and critic sandbagging.
- Model non-adversarial failures: schema migration breakage, partial-case
  contradictions, stale generated surfaces, lifecycle drift, missing handoffs,
  box-ticking, and maturity inflation.
- Define soft-gate lifecycle for warning-like states across runtime quality,
  Scientist validation, decision validity, transport/proof, prompt/tool ledger,
  public projection, and dashboard validation.
- Define repair-decision FMEA annotations and review-effectiveness telemetry:
  override rate, time spent, dissent, change requests, separation-of-duty
  failures, and reviewer bias.
- Define complexity-audit metrics: required record count, gate count, closeout
  cost, marginal value, reviewer load, false-block rate, ceremonial-compliance
  risk, and authority-level optionality.

**Output:** self-FMEA model, soft-gate lifecycle, review-effectiveness plan,
and complexity budget.

**Acceptance:** case-machinery failures cannot be hidden as domain evidence
failures, and the assurance system can identify when it is too costly or
ceremonial for the requested authority level.

#### C25 - Longitudinal Calibration And Balanced Memory

**Purpose:** make learning across runs reliable without contaminating current
run evidence or biasing the system toward fear.

**Code-informed starting point:** `calibration/*`, governance calibration, DDM
calibration audit, adversarial challenge results, `failure_lessons.py`, and
search lessons.

**Research work:**

- Separate historical backtesting from calibration.
- Design a longitudinal ledger keyed by domain, method, jurisdiction,
  data class, evidence mode, and authority level.
- Define interval coverage, bias, reversal rate, retraction rate, blocker
  precision/recall, evidence-class reliability, and calibration by group.
- Define balanced reflexive memory: failures, successes, opportunity patterns,
  lift-and-shift constraints, applicability scope, expiry/decay, revocation,
  contamination policy, and recovery/success evaluation.
- Define conservative-bias metrics: risk overprediction, opportunity
  suppression, excessive blocker rate, under-selection of ambitious policies,
  and domain imbalance.
- Define when positive or negative track record updates future priors without
  becoming current-run evidence.

**Output:** longitudinal calibration ledger and balanced memory policy.

**Acceptance:** future authority decisions can use calibration and memory
without laundering historical priors into current evidence.

#### C26 - Evaluation Methodology And Semantic Completeness

**Purpose:** evaluate whether the universal policy-design engine works, not
whether it writes plausible memos.

**Code-informed starting point:** `challenge_factory.py`, adversarial suites,
adversarial generators, temporal drift checks, benchmark registry, audit
verifier, citation faithfulness, semantic fixtures, authority-spoofing tests,
and production-quality replay fixtures.

**Research work:**

- Baseline existing challenge classes and avoid duplicate probes.
- Define public, hidden, regression, adversarial, historical-backtest, and
  semantic-completeness packs.
- Define metrics for omission, overgeneration, evidence closure, authority
  truthfulness, participation provenance, calibration, independence,
  acquisition quality, and closeout truthfulness.
- Design ablations for critic, rule, facet, and producer families.
- Add missing probes: authority spoofing, prompt injection, participation
  speculation, redaction completeness, public-export promotion, projection
  laundering, inferred-ledger box ticking, legacy warning publication,
  degraded transport becoming supported claim, and citation false-pass limits.
- Add semantic-completeness probes where structural validators, scorecards,
  CAS, signatures, or citation snippets pass but expert review rejects the
  interpretation, scope, causal support, legal authority, participation claim,
  or time alignment.

**Output:** benchmark governance policy and semantic test pack design.

**Acceptance:** the evaluation plan detects structural completeness that is
semantically wrong or insufficient for the requested authority level.

#### C27 - Research Synthesis And Implementation Readiness

**Purpose:** decide what is implementable, experimental, optional, or still
research-only.

**Code-informed starting point:** all conceptual outputs, capability baseline,
P01-P15 failure-pattern register, operating-model record families, and cloud
root-cause diagnostics.

**Research work:**

- Produce a consolidated research report.
- Convert stable findings into ADRs.
- Mark unresolved questions that must not become hard runtime rules.
- Mark which minimum record families are ready for implementation, which need
  more research, and which should be optional or authority-level-gated.
- Attach reuse-first classification to every proposed implementation task:
  `wire_existing`, `extend_existing`, `consolidate_existing`, or `build_new`.

**Output:** consolidated research report and inputs to the final implementation
plan.

**Acceptance:** engineering can begin with stable kernels, known limitations,
anti-pattern reasoning, and evaluation loops rather than speculative domain
templates.

#### C28 - Concept Spine Physical Form

**Purpose:** decide whether the universal concept spine should be a global
registry, a per-run reconciled artifact, or a hybrid.

**Code-informed starting point:** `fabric/entity_resolution/*`,
`scientist/cross_graph/*`, `ir/linker/*`, `ir/analytics/cross_graph.py`,
`runtime/quality/semantic_binding.py`, Lex norm concepts, Fabric source
contracts, Data Forge column/schema refs, and the C6/C7/C11 synthesis.

**Research work:**

- Compare three candidate physical forms:
  - global governed concept registry;
  - per-run reconciled spine artifact;
  - hybrid model with governed namespaces plus per-run reconciliation records.
- Define which concept classes must be globally governed versus resolved per
  run: policy term, metric, data column, norm, method requirement, population,
  geography, time, unit, and legal authority type.
- Define identity, equivalence, broader/narrower, scope-shifted, conflicting,
  deprecated, and unresolved relations.
- Define how concept authority is scoped by jurisdiction, time, population,
  data source, method, and authority profile.
- Define how producer handshakes consume, emit, reject, and block concept ids.
- Define lifecycle semantics: supersede, split, merge, invalidate, migrate,
  replay under old concept semantics, and public notice.
- Test examples where the same label is not the same concept because population,
  geography, time, unit, legal instrument, or aggregation differs.

**Output:** concept-spine physical-form decision memo, relation taxonomy, and
fixture set. This is a research artifact, not a runtime schema commitment yet.

**Acceptance:** the chosen form can represent legal, data, method, population,
geography, and time examples without forcing global consensus where only
per-run reconciliation is justified.

#### C29 - Effective Independence Function

**Purpose:** define how raw evidence lines collapse into effective independent
support by claim type and authority level.

**Code-informed starting point:** Foundry consensus/equivalence,
Scholar source scoring and duplicate heuristics, Fabric lineage/source
contracts, IR proof composability, Data Forge snapshots, claim registry,
portfolio/synthesis modules, and C13/C14/C25/C26 synthesis.

**Research work:**

- Define evidence-line identity: source, author/institution, dataset,
  transformation lineage, retrieval path, method family, assumptions, sponsor,
  model, snapshot, legal authority, and concept spine refs.
- Define collapse channels: shared primary source, shared corpus, shared data
  pipeline, shared method family, shared assumptions, shared author pool,
  shared sponsor/institution, shared LLM generation, shared legal authority, and
  shared simulation DGP.
- Define an `effective_independence(line_a, line_b) -> [0, 1]` model with
  hard-collapse, partial-collapse, and no-collapse cases.
- Define aggregation rules that prevent raw count inflation and preserve
  counterevidence.
- Define minimum effective independent evidence counts by claim family and
  authority level, with explicit deficits where the count cannot be met.
- Test examples where raw evidence count rises but effective support does not.

**Output:** effective-independence calculus, decision table, and fixture pack.

**Acceptance:** the function can classify at least data, legal, scholar,
method, simulation, and participation evidence lines and explain why two lines
remain independent or collapse.

#### C30 - Semantic Benchmark Rubric

**Purpose:** define how expert panels distinguish structural pass from semantic
false pass.

**Code-informed starting point:** `challenge_factory.py`, citation
faithfulness, claim support, audit verifier, semantic fixtures, authority
spoofing tests, production-quality replay fixtures, P01-P15 pattern register,
and C26 synthesis.

**Research work:**

- Define what expert reviewers must judge beyond structural validity:
  interpretation, scope, legal competence, causal support, method fit,
  time-role alignment, participation attribution, independence, and public
  truthfulness.
- Define adjudication labels for semantic pass, limitation required, contested,
  unsupported, false pass, fabricated/unverifiable, and reviewer disagreement.
- Define reviewer topology: domain reviewer, method/evidence reviewer,
  legal/governance reviewer, public-surface reviewer, and tie-break protocol.
- Define gold semantic adjudication sheet fields and review evidence required
  for every rejected structural pass.
- Define benchmark governance: hidden/public splits, versioning, leakage
  controls, reviewer calibration, disagreement tracking, and anti-overfitting.
- Include probes for faithful snippets that do not support the claim, authentic
  but legally incompetent sources, stale but structurally valid data, and
  audit-valid packages that still do not reconstruct a trustworthy case.

**Output:** semantic benchmark rubric and reviewer protocol.

**Acceptance:** the rubric can fail a structurally complete PDC for semantic
reasons and produce a reproducible explanation of the failure.

#### C31 - Acceptable Deficits By Authority Level

**Purpose:** decide which deficits can be published with limitation, accepted
internally, escalated to review, or blocked by authority level.

**Code-informed starting point:** authority envelopes, claim support, scorecard,
readiness, semantic binding, approval, public export guards, C1/C2/C3/C24, and
current deficit/limitation records.

**Research work:**

- Define deficit families: missing evidence, stale evidence, proxy evidence,
  weak independence, unresolved concept, contested evidence, legal uncertainty,
  method limitation, participation gap, cost/degradation limit, and lifecycle
  staleness.
- Define authority levels and publication scopes where each deficit is:
  allowed with limitation, internal-only, human-review-required, expert-review
  required, accepted deficit, reissue-required, or hard-blocking.
- Distinguish accepted deficit from publish-with-limitation and closeout block.
- Define how deficits cap support strength, readiness, publication audience,
  and closeout.
- Define non-overridable deficits for governed and production modes.
- Test mixed cases: strong data plus weak legal authority, strong method plus
  stale source, contested evidence plus public recommendation, and proxy data
  plus production claim.

**Output:** authority-level deficit matrix and case fixtures.

**Acceptance:** the same missing evidence cannot be silently treated as a
limitation in one reader and a blocker in another without an explicit matrix
rule.

#### C32 - Complexity Budget And Ceremony Boundary

**Purpose:** decide when PDC record families, gates, reviews, and controls
become disproportionate, ceremonial, or economically impossible.

**Code-informed starting point:** C24 self-FMEA, scorecard gates, phase
barriers, record-family registry, performance budget, run-cost/degradation
research, human-review escalation, and P01-P15 failure patterns.

**Research work:**

- Define complexity metrics: required record count, gate count, reviewer load,
  run cost, wall-clock time, artifact size, rerun cost, warning backlog,
  false-block rate, and marginal assurance value.
- Define authority-level complexity budgets for research, governed, and
  production runs.
- Define when a record family may be sampled, deferred, scoped down,
  authority-level-gated, or declared out of scope.
- Define ceremony signals: repeated empty records, warnings with no owner,
  controls that never affect decisions, reviews with no deltas, and gates that
  are always waived.
- Define how complexity risk becomes a self-FMEA finding and how it affects
  closeout.
- Compare complexity budget against the risk of under-assurance.

**Output:** complexity-budget policy and ceremony-detection rubric.

**Acceptance:** a complete PDC can be judged too heavy, too ceremonial, or
proportionate for its requested authority level using explicit criteria.

#### C33 - Rule Evolution Public Policy

**Purpose:** decide which rule or taxonomy changes force replay, migration,
grandfathering, mandatory revalidation, or public notice for past cases.

**Code-informed starting point:** `schema_compat.py`, research DAG replay and
invalidation, claim lifecycle, case lifecycle, rule/obligation governance,
Data Forge migrations, Fabric evolution, shim governance, and C20/C21 synthesis.

**Research work:**

- Classify rule changes: editorial, schema-compatible, threshold change,
  stricter admissibility, weaker admissibility, new blocker, retired blocker,
  taxonomy split/merge, and authority-profile change.
- Define public effects: no notice, internal migration, public annotation,
  reissue review, supersede, withdrawal review, and mandatory revalidation.
- Define old-logic replay, new-logic evaluation, comparison report, and
  grandfathering policy.
- Define when a past closed PDC remains historically valid but no longer
  publishable as current guidance.
- Define rule-version and logic-hash evidence required in every closed PDC.
- Test examples where a causal claim closed under V1 becomes inadmissible under
  V2 and where a taxonomy split changes affected claim scope.

**Output:** rule-evolution public policy and replay/revalidation decision
table.

**Acceptance:** past cases can be audited under their original logic while
stricter future logic can still trigger public revalidation where required.

#### C34 - Participation Legitimacy Semantics

**Purpose:** decide when participation evidence can support preference,
acceptability, legitimacy, contestability, implementation feasibility, or only
context claims.

**Code-informed starting point:** C19 participation provenance synthesis,
claim registry, public projection, Scholar evidence, human review, stakeholder
fields in policy design, and P15 LLM speculation firewall.

**Research work:**

- Define participation claim types: preference, lived experience, acceptability,
  legitimacy, procedural fairness, implementation feasibility, objection,
  dissent, and context.
- Define source kinds: survey, consultation, deliberative panel, hearing,
  administrative complaint, civil-society submission, expert interview,
  affected-person testimony, and LLM/analyst speculation.
- Define minimum provenance for each claim use: who was asked, how, when,
  sampling frame, representativeness, consent/redaction, facilitation, dissent,
  sponsor, and limitations.
- Define representativeness and attribution thresholds that distinguish
  affected-person preference from context-only evidence.
- Define how unresolved dissent appears in public projection without forced
  aggregation.
- Define when lack of participation is accepted deficit, blocker, or public
  limitation by authority level and policy impact.

**Output:** participation legitimacy matrix and provenance rubric.

**Acceptance:** LLM or analyst speculation cannot support affected-person
preference or legitimacy claims, and real participation evidence is limited to
the claim uses its provenance can justify.

#### C35 - Calibration Blocking Thresholds

**Purpose:** define interim policy for when calibration and model track record
warn, require review, cap readiness, or block high-authority runs.

**Code-informed starting point:** calibration modules, DDM calibration audit,
governance calibration reports, provider quality, challenge results, reflexive
memory, C25 synthesis, and C26 evaluation.

**Research work:**

- Define calibration metrics that may matter for authority: interval coverage,
  Brier/reliability, bias, reversal rate, retraction rate, blocker precision,
  false-block rate, false-pass rate, and group/domain calibration.
- Define which metrics require longitudinal evidence before becoming blockers.
- Define interim non-blocking posture for sparse history: warn, review,
  widen uncertainty, require additional evidence, reduce publication scope, or
  mark insufficient calibration history.
- Define when weak track record blocks only specific claim families, methods,
  domains, jurisdictions, providers, or authority levels.
- Define how calibration affects VOI, evidence budgets, uncertainty envelopes,
  model/provider selection, and review depth without becoming current evidence.
- Define data sufficiency thresholds before calibration metrics can block a
  production run.

**Output:** calibration blocking-threshold policy and interim sparse-history
decision table.

**Acceptance:** PolicyOS can use poor calibration history to constrain future
runs without pretending that history closes or refutes the current claim.

#### C36 - Capability Debt Algebra

**Purpose:** define how incomplete capability states aggregate into release,
readiness, and closeout risk.

**Code-informed starting point:** C0 capability reality labels, P01-P15 pattern
register, scorecard/readiness, closeout compatibility, docs gates, runtime
inspection tools, and C27 readiness synthesis.

**Research work:**

- Define capability debt units: `contract_only`, `producer_missing`,
  `artifact_missing`, `bridge_missing`, `consumer_missing`,
  `verification_missing`, `implemented_but_not_orchestrated`,
  `surface_missing`, `surface_out_of_scope`, `semantic_test_missing`,
  `compatibility_shim`, and `projection_only`.
- Define severity by capability purpose: evidence producer, authority gate,
  closeout input, public surface, lifecycle trigger, diagnostic-only, or
  internal helper.
- Define aggregation rules: max severity, count thresholds, authority-weighted
  debt, release blocker, accepted debt, and planned debt.
- Define when a missing external surface is allowed as `surface_out_of_scope`
  versus a release blocker.
- Define debt burn-down signals and ratchet policy for future implementation
  plans.
- Test examples where several low-level debts combine into a high release risk.

**Output:** capability debt algebra and release/readiness risk matrix.

**Acceptance:** incomplete capability claims can be compared and prioritized
without collapsing every gap into generic "not done."

#### C37 - Bridge Authority Semantics

**Purpose:** decide when an orchestration bridge is authority-bearing evidence
and when it is only transport or diagnostic metadata.

**Code-informed starting point:** evidence spine, evidence spine handoff,
producer handshake, semantic binding, claim registry, authority envelopes,
CAS writes, canary bundle assembly, replay, inspection, readiness, and public
export surfaces.

**Research work:**

- Classify bridge artifacts: transport carrier, handoff ledger, binding
  assertion, producer attestation, reader attestation, diagnostic projection,
  and closeout evidence.
- Define when a bridge may testify that a producer consumed a requirement,
  emitted a binding, preserved identity, or lost/drop-shifted authority.
- Define authority envelope requirements for bridge records that become
  closeout inputs.
- Define what bridge facts can support: causality, provenance, same-input
  closure, requirement propagation, or only debugging.
- Define failure modes: bridge missing, bridge contradicts producer artifact,
  bridge has stale ids, bridge leaks raw content, bridge borrows authority, and
  bridge masks producer failure.
- Test async handoff examples across NL request, job lease, workflow state,
  CAS write, bundle assembly, replay, inspection, readiness, and export.

**Output:** bridge authority decision table and handoff evidence taxonomy.

**Acceptance:** orchestration records can be used for closeout only where their
authority role is explicit and cannot be confused with producer evidence.

#### C38 - Obligation Explosion Control

**Purpose:** prevent universal grammar and LLM-generated candidates from
creating unbounded obligation lists that make every policy impossible to close.

**Code-informed starting point:** universal facet grammar, obligation rule
lifecycle, temporal logic, policy critic, challenge factory, VOI scheduler,
evidence acquisition, complexity budget, and LLM firewall.

**Research work:**

- Define obligation source classes: governed rule, deterministic critic,
  historical failure, legal requirement, producer blocker, LLM candidate,
  human reviewer, and public contestation.
- Define obligation priority classes: mandatory, authority-level mandatory,
  conditional, review-required, candidate, optional, deferred, and rejected.
- Define dominance, subsumption, deduplication, and grouping rules.
- Define stop rules using authority level, policy impact, VOI, marginal
  assurance value, cost, privacy, urgency, and public risk.
- Define escalation for too many candidate obligations: bundle, sample, defer,
  narrow scope, or request human triage.
- Define how rejected or deferred obligations remain visible without blocking
  closeout.
- Test cases with dozens or hundreds of candidate risks and obligations.

**Output:** obligation explosion control policy and prioritization matrix.

**Acceptance:** LLMs can generate rich candidate obligations without causing
unbounded mandatory gates or hidden deletion of inconvenient obligations.

#### C39 - External Legitimacy Surface

**Purpose:** decide what public, reviewer, expert, and machine audiences must
see for contestability and accountability to be real.

**Engineering split:** C39 has two execution surfaces. `C39a` is projection
structure and audience entitlement; it is ready for E4/E5. `C39b` is recourse
mechanics; PolicyOS owns contested records, `recourse_pointer`, reopening
triggers, and recourse-outcome ingestion, while appeal intake/adjudication/SLA
remain deployment-owned unless explicitly configured.

**Code-informed starting point:** PDC projection, public export guards,
DecisionGradeExport, dashboard validators, audit verifier, assurance case,
claim registry, participation provenance, contestability, tradeoff/welfare,
and C16/C17/C18/C19 synthesis.

**Research work:**

- Define audience-specific obligations for public, reviewer, expert, machine,
  dashboard, and audit consumers.
- Define which fields each audience must see: claim graph, legal authority,
  data basis, method basis, uncertainty, tradeoff frontier, value choice,
  participation provenance, deficits, dissent, redactions, and audit refs.
- Define what can be redacted without destroying contestability.
- Define how public users can see "why not" for blocked, limited, contested,
  or out-of-scope claims.
- Define machine-readable commitments needed for external auditors to verify
  projection truthfulness.
- Define failure modes: public surface hides blocker, reviewer surface cannot
  reconstruct claim, machine surface lacks refs, redaction masks dissent, or
  dashboard promotes a projection as authority.
- Define the minimum `recourse_pointer` contract for high-stakes contested
  production PDCs without making PolicyOS a universal appeal tribunal.

**Output:** external legitimacy surface taxonomy and audience requirement
matrix.

**Acceptance:** every audience gets enough typed information to contest or
audit what it is entitled to see, without turning projections into authority.

#### C40 - Producer Coordination Liveness

**Purpose:** define how Lex, Fabric, Scholar, Foundry, Data Forge, Scientist,
and runtime quality coordinate through shared spine requirements without
deadlock or circular waiting.

**Code-informed starting point:** evidence spine, producer handshake,
control worker/store, NL pipeline, Fabric source selection, Lex applicability,
Foundry method selection, Scholar search, Data Forge snapshots, semantic
binding, and canary evidence assembly.

**Research work:**

- Identify dependency cycles where producers wait for each other's concepts,
  legal anchors, data scope, method obligations, or claim decomposition.
- Define handshake states: requested, preflighted, waiting_on_spine,
  waiting_on_peer, emitted_context_only, emitted_binding, blocked, timed_out,
  degraded, rerun_required, and abandoned.
- Define liveness rules: timeouts, fallback paths, partial emission, typed
  blockers, retry limits, and escalation to human review.
- Define topological or staged ordering where possible, and explicit cycles
  where not possible.
- Define how producer liveness interacts with VOI, acquisition, cost budget,
  closeout, and public projection.
- Test examples where Lex needs claim decomposition while claim decomposition
  needs legal scope, or Foundry needs data scope while Fabric needs method
  requirements.

**Output:** producer coordination liveness model and cycle-resolution decision
table.

**Acceptance:** producer coordination can fail with narrow typed blockers
instead of deadlocking, silently dropping requirements, or producing generic
context-only artifacts as if they were bindings.

#### C41 - Historical Priors Firewall

**Purpose:** define how calibration and memory influence VOI, uncertainty,
model choice, and review depth without becoming current-run evidence.

**Code-informed starting point:** calibration ledger, reflexive memory,
failure lessons, success patterns, VOI scheduler/calibration, provider quality,
claim registry, evidence acquisition, and C25/C35 synthesis.

**Research work:**

- Define historical prior sources: calibration metrics, failure lessons,
  success patterns, provider quality history, method performance history,
  reviewer outcomes, and acquisition success rates.
- Define permitted effects: search ranking, VOI estimate, evidence budget,
  uncertainty widening, review escalation, provider/model selection, default
  enablement, and benchmark priority.
- Define forbidden effects: satisfying claim evidence, refuting current
  evidence, minting legal/data/method/participation authority, or hiding
  current-run deficits.
- Define provenance fields that mark historical-prior influence in the current
  Research DAG and PDC.
- Define decay, scope, revocation, contamination, and success/failure balance.
- Test cases where memory correctly increases review depth but does not close
  or block the current claim by itself.

**Output:** historical priors firewall policy and influence-record schema.

**Acceptance:** future runs can be smarter because of past runs while every
current claim still closes only through current-run admissible evidence or
explicit typed deficits.

### Engineering Translation Tasks

Engineering tasks should be planned in detail only after their conceptual gates
are satisfied. Each task below represents a future capability chain, not merely
a code module.

The transition to engineering is now allowed, but not unconditional. The
normalized synthesis in
`docs/backlog/universal-policy-design-case-research-results-consolidation.md`
is the controlling summary; the raw research ledger is archived in
`docs/research/universal-policy-design/deep-research-reports-105-146-combined.md`
for detail checks. Engineering planning must honor four conditions:

1. Six fast-track decision ADRs must land early. Work may plan in parallel, but
   dependent implementation stays gated until the relevant ADR is ratified.
2. Every ADR must distinguish structural commitments from tuned parameters.
3. Threshold items must use governed configuration, provisional defaults,
   feature flags or advisory mode, and explicit owners; early defaults are not
   validated truth.
4. Research sources used by the plan must live in the repo, not only in a local
   Downloads folder.

#### Fast-Track Decision ADRs

These are not new research waves. They ratify decisions already present in the
consolidation so engineering does not inherit conceptual ambiguity.

| ADR | Scope | Structural commitment | Tuned parameter posture | Gates |
| --- | --- | --- | --- | --- |
| FT-ADR-01 | Evidence acquisition decision boundaries | Eligibility precedes ranking; mandatory gates dominate VOI; `accepted_deficit`, `publish_with_limitation`, and `closeout_block` are distinct; governed/production commit needs human or governed authority. | VOI weights, cost values, time estimates, and strategy-prior values remain config-governed. | E17, acquisition paths in E10/E16 |
| FT-ADR-02 | Participation legitimacy matrix | Commit `claim_use x authority_level x population_scope -> representativeness/provenance` structure and fail-safe downgrade posture. | Representativeness numeric thresholds remain governed config under methodology/governance owners. | Participation surfaces in E4/E5, E11, E22 |
| FT-ADR-03 | Contestability record vs recourse process | PolicyOS owns contested records, public visibility, reopening triggers, `recourse_pointer`, and recourse-outcome ingestion; it does not own universal appeal adjudication. | Deployment-specific appeal SLA/intake/adjudicator settings are external/institutional config. | C39b parts of E4/E5 and lifecycle ingestion in E15 |
| FT-ADR-04 | Legal hierarchy and competence mini-decisions | Jurisdiction fallback is per-jurisdiction config; multiple authority types are allowed per norm; competence changes split claims by legal window. | Jurisdiction-specific fallback tables are governed namespace config. | E9 |
| FT-ADR-05 | Bounded liveness invariants | `eventually X` becomes `X within deadline D, else escalate`, finite-state-checkable through deadline consistency. | Deadlines and retry ceilings are governed runtime config. | E3, E6, E7, E19 |
| FT-ADR-06 | Review-effectiveness telemetry | Start advisory-only; measure review time, override rate, dissent, no-delta reviews, and separation-of-duty failures from existing metadata. | Blocking consequences wait for longitudinal data. | E19 |

#### ADR Template Requirements

Every ADR produced from this plan must include:

- **Structural commitment:** schema, transition, invariant, authority boundary,
  ownership, and required negative tests.
- **Tuned parameter:** thresholds, weights, minimum counts, budgets, deadlines,
  reviewer cutoffs, or calibration cutoffs that are provisional and
  config-governed.
- **Feature flag or advisory posture:** required for effective-independence
  weights, calibration blocking, complexity budgets, participation thresholds,
  and other values that need real outcome data.
- **Anti-laundering test:** a concrete case where the new artifact must not
  mint data, legal, method, participation, closeout, or public authority.
- **Revision path:** owner, evidence required for changing tuned parameters,
  and whether public notice/revalidation is needed.

#### E0 - Capability Ratchet And Pattern Register Tooling

**Depends on:** C0, C27.

**Closes:** P01, P02, P03, P10, P13.

**Engineering work:**

- Add a capability matrix or checklist that records the states from
  `docs/reference/policy-design-case-failure-patterns.md`: `contract_only`,
  `producer_missing`, `artifact_missing`, `bridge_missing`, `consumer_missing`,
  `verification_missing`, `implemented_but_not_orchestrated`,
  `surface_missing`, `surface_out_of_scope`, and `semantic_test_missing`.
- Add a backlog or report template for capability claims and pattern IDs.
- Wire the ratchet into implementation plans and production-quality backlogs.

**Completion signal:** capability claims can be counted and moved toward
`implemented` or explicitly scoped out.

#### E1 - Corpus, Fixture, And Semantic Test Infrastructure

**Depends on:** C0, C26.

**Closes:** P10, P15.

**Engineering work:**

- Create research corpus folders and fixture conventions.
- Add regression fixtures for expert disagreement, semantic completeness,
  projection laundering, LLM speculation, participation provenance, and
  raw-count evidence inflation.
- Ensure semantic tests live next to the relevant unit/integration suite or in
  production-quality fixtures when spanning producers.

**Completion signal:** `semantic_test_missing` has a concrete closure path for
future tasks.

#### E2 - Status Lattice And Soft-Gate Crosswalk

**Depends on:** C1.

**Closes:** P04, P09.

**Engineering work:**

- Implement the status crosswalk over existing local statuses.
- Add mixed-status tests for claim support, citation faithfulness, semantic
  binding, approval, readiness, proof composability, transportability, and
  decision validity.
- Add warning lifecycle metadata and aging/escalation checks where stable.

**Completion signal:** a new status cannot be added without composition tests
and closeout/publication effects.

#### E3 - Unified `can_i_closeout` Substrate

**Depends on:** C1, C2, C3, C24, FT-ADR-05.

**Closes:** P01, P02, P04, P05, P09, P10.

**Engineering work:**

- Build a typed closeout decision object over formal invariants, event log,
  attestation, source truth, metamorphic controls, performance/cost budgets,
  closeout compatibility, semantic binding, approval, audit verifier, and
  publication state.
- Materialize the record through a separate closeout substrate reader, not
  readiness. Readiness is one conjunct; the closeout record is authoritative
  only for `closeout_verdict`.
- Add bounded-liveness deadline consistency checks where closeout depends on
  async repair, retry, producer wait, or escalation paths.
- Add CLI/API output and readiness integration.
- Add negative tests for missing provenance, incompatible reader schema,
  failed invariant, semantic closure failure, projection-only authority, and
  missing audit verifier ingestion.

**Completion signal:** operators can ask one API/CLI question and receive the
closeout state with first failing producer, root-cause class, and next action.

#### E4 - Typed Policy Design Case Projection Backend

**Depends on:** C15, C16, C17, C18, C19, C26, FT-ADR-02, FT-ADR-03.

**Closes:** P03, P05, P10, P15.

**Engineering work:**

- Replace shallow `dict[str, Any]` assumptions with strict Pydantic DTOs for
  Policy Design Case projection and typed projection gaps.
- Split `C39a` projection structure from `C39b` recourse mechanics. Projection
  structure is owned by PolicyOS; appeal intake/adjudication/SLA are
  deployment-owned unless separately configured.
- Include claim graph, warrant structures, authority summary, readiness gates,
  approval decision, publication status, contested records, deficit register,
  invariant summary, audit-verifier summary, limitations, and machine-readable
  authority gaps.
- Add `recourse_pointer` and recourse-outcome ingestion refs for high-stakes
  contested production PDCs, while keeping projection artifacts
  non-authoritative.
- Add OpenAPI contract and backend tests.

**Completion signal:** runtime can emit a typed projection or typed projection
failure without minting authority.

#### E5 - Generated Client, Dashboard, Public Export, And Audit Surface

**Depends on:** E4, FT-ADR-03 for high-stakes contested publication surfaces.

**Closes:** P03, P05, P10.

**Engineering work:**

- Regenerate TypeScript clients.
- Update dashboard/public/export renderers to consume typed projection.
- Wire public export and audit package references to typed projection truth.
- Render verified `recourse_pointer`, contested-record omissions, and
  deployment-owned recourse boundaries without implying PolicyOS adjudicates
  appeals.
- Add projection-laundering tests for dashboard/API mismatch, raw artifact used
  as public export, missing projection gap, and failed claim promotion.

**Completion signal:** PUBLIC/REVIEWER/EXPERT/MACHINE surfaces expose the same
truth with audience-appropriate redaction.

#### E6 - Concept Spine Carrier And Producer Handshake Kernel

**Depends on:** C6, C7, C8.

**Closes:** P02, P08, P12.

**Engineering work:**

- Implement reusable concept-spine carrier and producer handshake records.
- Persist consumed/emitted/rejected/blocked concept and requirement bindings.
- Add pre-emission consistency checks where required by the protocol.
- Expose handshake records to replay, inspection, semantic binding, readiness,
  and projection.

**Completion signal:** producer coordination no longer depends on NL-pipeline
local payload assembly.

#### E7 - NL Pipeline And Replay Integration For Producer Coordination

**Depends on:** E6.

**Closes:** P02, P12.

**Engineering work:**

- Thread the producer handshake kernel through request context, workflow state,
  job progress, replay, bundle assembly, inspection, readiness, and exports.
- Preserve existing semantic-binding behavior while replacing ad hoc payload
  glue with the reusable kernel.

**Completion signal:** live/replay bundles can show producer handshakes and
spine continuity across async handoffs.

#### E8 - IR And Cross-Graph Analytics To ClaimRecord Bridge

**Depends on:** C9, C10, C13, C14.

**Closes:** P02, P10, P14.

**Engineering work:**

- Project IR/cross-graph profiles, certificates, diagnostics, source statuses,
  bridges, conflicts, and proof-composability statuses into ClaimRecord refs,
  method output refs, uncertainty refs, blockers, limitations, counterevidence,
  and rebuttal requirements.
- Add tests showing a proof-carrying artifact changes claim support and
  readiness, and a missing bridge fails.

**Completion signal:** IR analytics outputs are no longer detached analytical
sidecars.

#### E9 - Lex Legal Authority Adapter

**Depends on:** C2, C7, C8, C11, FT-ADR-04.

**Closes:** P01, P02, P05, P08, P12.

**Engineering work:**

- Implement graded legal admissibility and per-claim legal anchors.
- Preserve query-normalization legal requirements when top-level requirement
  lists are absent.
- Add hierarchical jurisdiction, temporal competence, authority-type facets,
  selected/rejected/no-anchor refs, and typed blockers.
- Use governed per-jurisdiction fallback config rather than a universal
  hardcoded hierarchy rule.
- Allow one norm to carry multiple authority types and split claims when
  competence changes during the policy window.

**Completion signal:** legal authority cannot pass through global or generic
Ukrainian matches alone.

#### E10 - Fabric Data Source And Scenario Contract Adapter

**Depends on:** C2, C6, C8, C11, C22.

**Closes:** P01, P02, P08, P12, P14.

**Engineering work:**

- Use Fabric SourceContract as the admissible data-source substrate.
- Bind scenario source families and claim requirements to selected/rejected/
  blocked source contracts.
- Fail broad bundle labels such as generic `datasets` when claim-admissible
  source family contracts are absent.
- Export missing facets, lineage, freshness, quality, missingness, outlier,
  construct-validity, and claim-bindability findings.

**Completion signal:** data availability is no longer confused with admissible
scenario evidence.

#### E11 - Scholar Academic Evidence Adapter

**Depends on:** C8, C13, C14, C26, FT-ADR-02 for participation-like source claims.

**Closes:** P01, P02, P10, P14.

**Engineering work:**

- Bind Scholar query graphs, fetch traces, snippets, citations, freshness,
  source scoring, claim support links, duplicate/polarity signals, and corpus
  lineage to claims.
- Add author, institution, dataset, citation-network, replication, and review
  lineage for independence calculations.
- Add typed blocker when serious claims lack academic evidence or when Scholar
  evidence is context-only.
- For participation-like or affected-person claims surfaced through Scholar or
  grey literature, preserve claim-use downgrade and provenance limits rather
  than treating publication as representativeness.

**Completion signal:** academic evidence can support, limit, contest, or block
claim support with visible provenance.

#### E12 - Foundry Method, Assumption, And Simulation Adapter

**Depends on:** C9, C10, C11, C13.

**Closes:** P01, P02, P10, P14.

**Engineering work:**

- Emit selected and rejected methods with reasons.
- Enforce runtime assumption-validation gates where conceptually approved.
- Bind method output refs, uncertainty envelopes, limitations, and assumption
  refs to claims.
- Bind agent-simulation mechanism parameters to DGP/truth manifest/calibration
  source/sensitivity bounds and simulation-family lineage.

**Completion signal:** generic `foundry.execute` or offline-only validity cannot
support serious method obligations.

#### E13 - Effective Independence And Portfolio Aggregation

**Depends on:** C13, C14, E8-E12.

**Closes:** P14.

**Engineering work:**

- Implement evidence-line identity and collapse reason records.
- Downweight dependent evidence lines in portfolio aggregation.
- Put graded weights and authority-level minimum effective counts behind
  governed configuration and feature flags; initial defaults are provisional,
  not validated thresholds.
- Represent rare-domain `scarcity_structural` separately from
  `scarcity_remediable`; never inflate scarce evidence into independent
  support.
- Wire proof replay, Scholar dependence, Fabric lineage, legal source
  dependence, prompt/model paths, and simulation assumptions into effective
  independent evidence count.

**Completion signal:** portfolio strength reports effective independent support
instead of raw source count.

#### E14 - Rule Evolution Registry And Replay Semantics

**Depends on:** C21.

**Closes:** P06, P07, P08.

**Engineering work:**

- Implement rule/taxonomy version refs and logic hashes for admissibility,
  obligations, claim taxonomy, method matrix, and PDC gates.
- Integrate old-logic replay, migrated replay, grandfathering, stricter-rule
  detection, and mandatory revalidation.
- Add compatibility-shim and behavioral-legacy retirement checks.

**Completion signal:** a past PDC can prove which rule logic closed it and what
new logic would change.

#### E15 - Lifecycle, DDM, And Partial Reissue Bridge

**Depends on:** C20, C21.

**Closes:** P01, P02, P07, P08, P09.

**Engineering work:**

- Bridge DDM events, legal/source changes, calibration drift, fairness drift,
  participation drift, policy-context drift, and incidents into claim lifecycle.
- Implement partial-scope reissue records with affected claim ids, unchanged
  records, superseded refs, public diffs, and publication state.

**Completion signal:** lifecycle changes can revise only affected claims and
surfaces rather than wholesale reissuing the case.

#### E16 - Data Forge Closeout Binding

**Depends on:** C9, C11, C20, C22.

**Closes:** P01, P02, P08, P10.

**Engineering work:**

- Bind scenario and claim requirements to Data Forge artifact refs, snapshot
  transactions, merkle roots, release manifests, read APIs, lineage refs,
  quality gates, and data hashes.
- Expose official input identity to closeout, replay, projection, and public
  export.

**Completion signal:** closeout can prove which Data Forge snapshot/release was
the official input for each claim.

#### E17 - Evidence Acquisition Planner

**Depends on:** C22, FT-ADR-01.

**Closes:** P01, P02, P10.

**Engineering work:**

- Implement acquisition strategy records: registry, agency request, survey,
  consultation, legal corpus expansion, academic retrieval, production
  snapshot build, proxy/degrade, accepted deficit, rerun, and block.
- Implement `gap_type x authority_level x mandatory_gate_state` eligibility
  before VOI ranking. VOI ranks eligible strategies only; it cannot bypass a
  non-overridable gate.
- Keep `accepted_deficit`, `publish_with_limitation`, and `closeout_block`
  distinct in records, readers, and public surfaces.
- Feed acquisition outcomes into VOI calibration and future strategy priors.
- Add next-action output for blocked claims.

**Completion signal:** a missing portfolio obligation yields an actionable
strategy, not only a blocker.

#### E18 - Cost, Budget, And Degradation-SLA Gates

**Depends on:** C23.

**Closes:** P01, P09, P13.

**Engineering work:**

- Track provider calls, tokens, embeddings/searches, compute-dollar budget,
  wall-clock budget, retry budget, and acquisition budget.
- Define warning, limitation, rerun, acquisition, and closeout-blocking states
  by authority level.
- Wire budget/SLA outcomes into closeout, local prod-debug, canary matrix, and
  operator surfaces.

**Completion signal:** production quality can fail for cost/SLA reasons without
confusing them with ordinary performance telemetry.

#### E19 - Self-FMEA, Soft-Gate, Review, And Complexity Controls

**Depends on:** C24, FT-ADR-05, FT-ADR-06.

**Closes:** P04, P09, P10, P13.

**Engineering work:**

- Implement soft-gate registry and aging/escalation checks.
- Emit repair-decision FMEA records for prompt/tool repairs.
- Capture review-effectiveness telemetry in advisory mode first. Do not make
  review-effectiveness thresholds blocking until longitudinal evidence supports
  them.
- Capture complexity budget reports from existing telemetry. The budget may
  gate growth of new controls by requiring expected Net-MAV and measurement
  refs; it should not become a per-run ceremonial gate by default.
- Add tests for legacy warning publication, inferred-ledger box ticking,
  projection failure with no gap, and ceremonial gate overload.

**Completion signal:** case-machinery failures are visible as machinery
failures and cannot hide under domain evidence status.

#### E20 - Longitudinal Calibration Ledger

**Depends on:** C25.

**Closes:** P07, P09, P10.

**Engineering work:**

- Persist calibration ledger entries keyed by domain, method, jurisdiction,
  data class, evidence mode, and authority level.
- Track interval coverage, bias, reversal, retraction, blocker precision/recall,
  and evidence-class reliability.
- Wire longitudinal metrics into future authority warnings, review depth,
  uncertainty widening, provider/model routing, or later blockers without
  contaminating current-run evidence. Blocking thresholds start as
  feature-flagged governed config and require mature history.

**Completion signal:** weak track record can warn or block future high-authority
runs with explicit governance policy.

#### E21 - Balanced Reflexive Memory

**Depends on:** C25.

**Closes:** P11, P15.

**Engineering work:**

- Add success-pattern and opportunity-pattern capture/retrieval alongside
  failure lessons.
- Enforce scope, expiry/decay, revocation, contamination policy, and
  conservative-bias metrics.
- Add tests showing success memory changes future priors only where permitted.

**Completion signal:** memory no longer biases the system only toward avoiding
past failures.

#### E22 - Semantic Evaluation And Adversarial Packs

**Depends on:** C26, FT-ADR-02, FT-ADR-03, and stable producer/surface tasks.

**Closes:** P10, P14, P15.

**Engineering work:**

- Implement semantic-completeness fixtures, expert-disagreement tests,
  projection-laundering tests, LLM speculation tests, participation
  provenance tests, raw-count inflation tests, and citation false-pass probes.
- Add negative tests where participation prevalence is improperly inferred
  from thin consultation, `recourse_pointer` is missing or unreachable for a
  high-stakes contested PDC, and a tuned threshold is hardcoded as final.
- Map existing challenge classes before adding new ones.
- Add benchmark governance metadata and ablation hooks.

**Completion signal:** evaluation can distinguish fluent drafting and structural
validity from evidence-bound, authority-truthful policy design.

#### E23 - Documentation, ADRs, Runbooks, And Public Evidence Paths

**Depends on:** C27 and stable engineering tasks.

**Closes:** P03, P06, P13.

**Engineering work:**

- Publish ADRs for stable conceptual decisions.
- Update runbooks, reference docs, docs index, public-surface docs, and
  generated-artifact instructions.
- Keep raw research ledgers, normalized synthesis docs, ADRs, and engineering
  plans under repo-owned paths so future readers do not depend on local
  Downloads files.
- Record evidence paths and command evidence for each completed capability.

**Completion signal:** operators and future agents can find the canonical
owner, contract, evidence path, and validation commands.

#### E24 - Final Implementation Plan And Validation Ladder

**Depends on:** C27 and the six fast-track decision ADRs.

**Closes:** sequencing risk.

**Engineering work:**

- Write `POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md`.
- Include file ownership, dependencies, task order, test commands, validation
  ladder, rollout gates, and explicit unresolved research questions.
- Place the six fast-track ADRs at the front of the implementation sequence
  and mark E9, E17, E19, and C39b-dependent E4/E5 work as blocked until their
  relevant ADR lands.
- Require every task to name anti-pattern IDs closed or risked, capability
  state moved, and reuse path.
- Require every task with tuned parameters to identify config owner, feature
  flag/advisory mode, provisional default source, and validation path.

**Completion signal:** implementation can proceed without reintroducing the old
mix of conceptual ambiguity and engineering wiring debt.

### Conceptual-To-Engineering Gates

| Conceptual task | Unlocks | Gate before engineering starts |
| --- | --- | --- |
| C0 | E0, E1, E23 | Capability baseline names canonical owners, shims, and corpus slices. |
| C1 | E2, E19 | Local status behavior is reproduced and mixed-status decisions are explicit. |
| C2 | E2, E3, E9-E13 | Admissibility decision table handles direct, proxy, context-only, contested, blocked, and out-of-scope evidence. |
| C3 | E3 | Closeout substrate names every sub-decision owner and terminal/deficit behavior. |
| C4 | E10, E17 | Facet vocabulary avoids domain adapters and duplicates no existing enum. |
| C5 | E14, E17 | Obligation rules have status, provenance, version, scope, owner, and evidence basis. |
| C6 | E6, E7 | Concept spine examples cover legal, data, method, population, geography, and time. |
| C7 | E9 | Jurisdiction and competence model handles hierarchy, legal time, and authority type. |
| C8 | E6, E7, E9-E12 | Producer handshake protocol names consumed/emitted/rejected/blocked bindings. |
| C9 | E8, E12 | Claim-method matrix blocks plausible but inadmissible method support. |
| C10 | E8 | Baseline model requires comparison evidence for superiority claims. |
| C11 | E9, E10, E16 | Time/numeric/geography mismatch outcomes are authority-level-aware. |
| C12 | E9-E12, E22 | LLM boundary distinguishes candidate, critic, drafter, and deterministic producer sources. |
| C13 | E13, E22 | Effective-independence examples show raw count rising while effective support does not. |
| C14 | E8, E13, E22 | Conflict semantics map to counterevidence, rebuttal, limitation, and readiness caps. |
| C15 | E4, E5 | Warrant and argument profile maps to existing assurance case and names exporter gaps. |
| C16 | E4, E5 | Multi-audience projection contract names fields, redactions, and typed gaps. |
| C17 | E4, E8, E22 | Contestability states preserve disagreement without forced aggregation. |
| C18 | E4, E8 | Tradeoff model separates frontier facts from value choices. |
| C19 | E4, E11, E22 | Participation provenance schema blocks speculation as affected-person preference. |
| C20 | E15, E16 | Revalidation graph maps events to affected claims and public states. |
| C21 | E14, E15 | Rule evolution policy defines old-logic replay, migration, grandfathering, and mandatory revalidation. |
| C22 | E17 | Acquisition policy can choose block/degrade/acquire/proxy/deficit/rerun. |
| C23 | E18 | Cost/SLA policy distinguishes budget governance from latency observability. |
| C24 | E19 | Self-FMEA names soft-gate owners, review telemetry, and complexity budget. |
| C25 | E20, E21 | Calibration and memory policy separates current evidence from future priors. |
| C26 | E1, E22, E24 | Benchmark governance includes semantic negative controls and anti-laundering probes. |
| C27 | E23, E24 | Consolidated report marks decisions implementable, experimental, optional, or research-only. |
| C28 | E6, E7, E9-E13 | Hybrid concept spine is accepted: repo-governed namespaces by default plus per-run reconciled authority artifact. |
| C29 | E13, E22 | Effective-independence function has strict collapse and graded defaults; weights/minima are feature-flagged governed config. |
| C30 | E1, E22, E24 | Semantic benchmark rubric has labels, gold-card fields, and false-pass probes. |
| C31 | E2, E3, E4, E19 | Deficit dispositions distinguish accepted deficit, publish-with-limitation, review, reissue, and hard block. |
| C32 | E19 | Complexity budget is telemetry-derived and advisory by default; new controls declare expected Net-MAV. |
| C33 | E14, E15 | Rule evolution policy distinguishes schema migration from semantic/rule change and public revalidation. |
| C34 | E4, E11, E22 | Participation matrix structure and downgrade posture are decided; thresholds are tuned parameters. |
| C35 | E20, E21 | Sparse-history calibration policy is non-blocking until mature history supports governed thresholds. |
| C36 | E0, E24 | Capability debt algebra provides state labels, purpose multipliers, and readiness bands. |
| C37 | E3, E6, E7, E19 | Bridge authority uses boundary-scoped closeout input, not a bridge-specific top-level authority role. |
| C38 | E17, E19 | Obligation control uses candidate ledger, bundle ledger, and bounded blocking frontier. |
| C39a | E4, E5 | Projection structure and audience entitlement matrix are ready for typed surface engineering. |
| C39b | E4, E5, E15 | PolicyOS owns contestability records and `recourse_pointer`; appeal process is deployment-owned. |
| C40 | E6, E7, E9-E13, E19 | Producer liveness uses bounded states, deadlines, typed blockers, and context-only non-authority. |
| C41 | E20, E21, E22 | Historical priors influence routing, VOI, review, and uncertainty, never current-run evidence closure. |

---

## Decision Status After Synthesis

The broad research questions have converged enough to plan engineering. The
remaining work is not homogeneous; the plan must not treat every uncertainty as
"more research."

### Ratify Immediately

These are decided in the consolidation but must land as ADRs before their
dependent E-tasks proceed:

- evidence acquisition decision boundaries: eligibility before ranking,
  mandatory gates over VOI, three distinct terminal states, and governed commit
  authority;
- participation legitimacy matrix structure and fail-safe downgrade posture;
- contestability record vs deployment-owned recourse process, with verified
  `recourse_pointer` for high-stakes contested production PDCs;
- legal hierarchy/competence mini-decisions: jurisdiction-config fallback,
  multiple authority types, and competence-window splitting;
- bounded-liveness invariants as deadline consistency and escalation;
- advisory-first review-effectiveness telemetry.

### Structural Now, Tune Later

These structures should be implemented with provisional, governed defaults and
feature flags or advisory mode:

- effective-independence weights and authority-level minimum effective counts;
- calibration blocking thresholds and sparse-history promotion/demotion rules;
- complexity budgets, Net-MAV bands, and ceremony thresholds;
- participation representativeness numeric thresholds;
- rare-domain weak-evidence thresholds and single-line-deficit policy;
- run-cost, provider-call, budget, and degradation-SLA thresholds.

### Deployment Or Institution Owned

These are intentionally not universal PolicyOS research problems:

- appeal intake, adjudication, SLA, and outcome authority beyond the typed
  `recourse_pointer` and recourse-outcome ingestion hook;
- jurisdiction-specific legal fallback tables;
- named methodological and governance ownership for participation thresholds;
- external concept namespace service operation until promotion triggers fire.

### Still Empirical

These need corpus, telemetry, or longitudinal evidence while engineering
progresses:

- whether initial independence weights match expert portfolio judgements;
- how often semantic false passes appear after structural gates pass;
- reviewer-time, no-delta review, false-block, and ceremony rates;
- calibration drift and track-record thresholds after enough resolved cases;
- whether repo-governed concept dictionaries become operationally insufficient.

---

## Success Criteria For The Whole Research Plan

The research plan succeeds if it produces an implementation path where:

- PolicyOS can accept a new policy problem without a hand-built domain adapter.
- Every implementation proposal starts from a capability/code baseline and a
  reuse-first classification.
- LLMs can propose rich candidate structures but cannot mint authority.
- Universal facets compile into evidence obligations.
- Concept-spine reconciliation binds producer vocabularies across policy
  terms, metrics, data columns, legal concepts, methods, populations,
  geographies, and time.
- Admissibility decisions are typed, explainable, and reproducible.
- Existing subsystem statuses compose through one explicit status algebra
  rather than implicit local reader behavior.
- Admissibility is parameterized by research, governed, and production
  authority levels.
- Lex legality supports graded admissibility, hierarchical jurisdiction, and
  implementing/delegating/enabling authority distinctions.
- A unified honest-diagnostics closeout substrate integrates formal
  invariants, event logs, attestation, source truth, metamorphic controls,
  performance budgets, and compatibility records.
- Claim types determine required method and evidence support.
- Proof-carrying IR analytics artifacts bind to ClaimRecord, uncertainty refs,
  semantic binding, PDC records, API projections, and closeout.
- Counterfactual baselines and rejected alternatives are first-class policy
  design objects.
- Numeric, temporal, and geographic mismatches create transformations,
  limitations, or blockers instead of silently passing.
- Time-role mismatches across legal, data, policy, model, detection, replay,
  publication, freshness, and retention time are explicit and authority-aware.
- Evidence strength uses effective independent evidence count, not raw source
  count.
- Argument structure validates and exports the existing SACM/CAE/GSN mapping,
  with typed warrant semantics and documented profile limits.
- HTTP/API, dashboard, decision-grade export, and public-export surfaces expose
  one typed PolicyDesignCaseProjection over existing projection semantics and
  cannot reconstruct authority from generic artifacts.
- Contestability is preserved as a governance state.
- Affected-person claims require participation provenance.
- Tradeoffs expose value choices rather than hiding them in optimization.
- Welfare aggregation exposes Pareto frontier records and social-weight
  provenance.
- Lifecycle revalidation follows the claim-evidence graph.
- Taxonomy and rule evolution preserve past-case reproducibility and trigger
  mandatory revalidation when needed.
- Rule-semantics evolution is tracked separately from schema compatibility.
- Continuous-governance event contracts have detector implementations or
  bridges, partial-scope reissue, official Data Forge closeout binding over
  existing provenance surfaces, and memory decay.
- Reflexive memory learns from success patterns and failures without creating
  hidden overconfidence or defensive conservative bias.
- Evidence acquisition planning explains the next best action after a blocker.
- Cost, provider-call, wall-clock, and degradation-SLA limits are first-class
  acquisition and closeout considerations.
- Self-FMEA models both adversarial and non-adversarial failures of the case
  machinery.
- Self-FMEA includes soft-gate escalation, projection laundering, semantic
  completeness, and complexity/cost of the assurance machinery itself.
- Formal self-FMEA extends existing model-checked invariants with
  temporal/liveness properties and review-effectiveness measurement.
- Calibration is tracked longitudinally and can warn or block future
  high-authority runs.
- Evaluation measures evidence closure, omission, authority truthfulness, and
  historical risk anticipation, not just plausible drafting.

The research plan fails if the only viable implementation path is a large
catalog of domain templates whose authority depends on untestable expert
prompts, or if it rebuilds existing PolicyOS modules without first proving a
real capability gap.
