---
title: PolicyOS Universal Policy Design Case Implementation Plan
status: active-draft
owner: team-policyos-runtime
created: 2026-05-22
source_research_plan: ./POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_RESEARCH_PLAN.md
source_synthesis: ../../backlog/universal-policy-design-case-research-results-consolidation.md
raw_research_ledger: ../../research/universal-policy-design/deep-research-reports-105-146-combined.md
failure_patterns: ../../reference/policy-design-case-failure-patterns.md
source_ownership: ../../reference/policy-design-case-source-ownership.md
evidence_paths: ../../reference/policy-design-case-evidence-paths.md
operator_guide: ../../reference/policy-design-case-operator-guide.md
rollout_runbook: ../../runbooks/policy-design-case-rollout-rollback.md
adr_index: ../../adr/index.md
docs_index: ../../reference/index.md
scope:
  - universal-policy-design-case
  - implementation-plan
  - evidence-spine
  - claim-registry
  - closeout-substrate
  - typed-pdc-projection
  - producer-adapters
  - semantic-evaluation
  - public-export-truthfulness
  - longitudinal-calibration
  - governed-tuned-config
---

# PolicyOS Universal Policy Design Case Implementation Plan

This is the best-in-class engineering execution plan for the universal Policy
Design Case program. It implements the conceptual and theoretical work captured
in:

- `docs/backlog/universal-policy-design-case-research-results-consolidation.md`
- `docs/research/universal-policy-design/deep-research-reports-105-146-combined.md`
- `docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_RESEARCH_PLAN.md`
- `docs/reference/policy-design-case-failure-patterns.md`

The plan is deliberately exhaustive. Its job is not to be short; its job is to
make implementation hard to misinterpret. The central engineering target is a
runtime-compiled Policy Design Case whose public output is a projection of a
claim-bound evidence graph, not a free-text policy memo with detached quality
reports.

## Implementation Thesis

The research stream converged on this architecture:

```text
request and authority profile
  -> universal policy grammar
  -> governed candidate obligations
  -> concept, legal, time, and geography spine
  -> producer handshake
  -> claim-bound evidence registry
  -> argument, warrant, conflict, independence, and portfolio graph
  -> unified closeout substrate
  -> typed multi-audience projection
  -> lifecycle revalidation, calibration, and memory
```

The implementation must close the recurring PolicyOS failure mode:

```text
strong internal components
  + weak orchestration bridges
  + shallow external surfaces
  + structural-only validation
  = local passes that cannot justify public authority
```

Therefore this plan prioritizes bridge-first engineering:

- authority-preserving runtime carriers before producer-specific features;
- claim-bound registries before public prose;
- closeout reader before dashboard/export promotion;
- semantic tests before declaration of "implemented";
- feature flags and governed config before final thresholds.

## Execution Model

Implementation proceeds through sequential waves. Inside each wave, phases are
parallel by definition.

Rules:

- every phase in a wave consumes only artifacts available before the wave
  starts;
- sibling phases in the same wave must not require each other's implementation;
- a phase may publish an interface, fixture, or record for later waves;
- if two phases need producer-consumer coupling, the producer belongs in an
  earlier wave or the consumer belongs in a later wave;
- wave exits are the integration barriers;
- every wave exit leaves persisted artifacts, tests, docs, and capability
  reality labels that the next wave can trust.

## Non-Negotiable Conditions

The transition from research to implementation is honest only if these
conditions remain true.

1. The six fast-track decision ADRs land in Wave 0. Gated implementation may be
   prepared in parallel, but cannot merge before the relevant ADR is accepted.
2. Every ADR and threshold-bearing implementation separates structural
   commitment from tuned parameter. Thresholds that need empirical evidence are
   provisional governed config, never hardcoded truth.
3. Effective-independence weights, calibration blocking, complexity budgets,
   participation thresholds, run budgets, and rare-domain scarcity thresholds
   ship behind feature flags, advisory mode, governed config, or a documented
   combination.
4. Research sources, ADRs, plans, command evidence, and validation artifacts
   remain under repo-owned paths. No critical implementation path may point
   only to a local Downloads file.

## Wave 0-5 Completion Status And Wave 6+ Restart Rationale

Wave 0 is complete as the decision and source-ownership foundation for later waves. ADR-0166 through ADR-0171 are accepted in `docs/adr/`, W0.G source ownership is published at `docs/reference/policy-design-case-source-ownership.md`, and W0.H structural ADR coverage is published at `docs/reference/policy-design-case-structural-adr-registry.md`.

Waves 1 through 5 are also complete as their substrate, adapter, orchestration, projection, and external-surface foundations. Their exit gates were honoured; their capability ratchet entries graduated to `implemented` or carried documented holds.

The original Wave 6 ("End-To-End Revalidation And Rollout") was started and surfaced a conceptual gap rather than a wiring defect: the local validation ladder regressed on production data source families because the system had no universal compilation layer translating policy intent into typed `DataRequirementSpec` (and the analogous Legal / Method / Scholar / Participation requirements). The hardcoded `admissible_data_source_families` list in the public golden scenario was acting as a substitute for that missing compilation. Adding the missing source families would have closed the ladder but would not have built the universal capability the program is committed to.

The original Wave 6 is therefore suspended and the plan is restructured to insert six new waves (Wave 6 Universal Compilation Kernel, Wave 7 Requirement Compilation + Adapter Refactor, Wave 8 PDC Graph Compilation + Argument Building, Wave 9 Advanced Lifecycle + Drift Detection + Replay, Wave 10 Temporal/Liveness + Run-Cost + Self-FMEA Depth, Wave 11 Universal Outcome Corpus + Truthfulness Tools) between the completed Wave 5 and a renamed Wave 12 (End-To-End Revalidation And Rollout). Wave 12 re-executes the original W6.A local validation ladder on top of the new universal compilation path; the regression on production data source families is replaced by compiled-requirement assertion in Wave 7.A.

Downstream waves may rely on Wave 0-5 decisions and artifacts for gated implementation work, provided they preserve the ADR authority boundaries, governed tuned parameter posture, negative laundering tests, and capability reality labels. The Wave 6-12 capability claims still must each prove their own producer, artifact, orchestration bridge, consumer, surface, verification, and semantic-test chain — the completion status of Wave 0-5 does not imply universal-capability achievement, only that the substrate-and-adapter foundation that the universal compilation layer will build on is in place.

## External Engineering Practice Crosswalk

This plan deliberately maps PolicyOS-specific research decisions onto
well-established engineering practices instead of inventing process vocabulary
where mature practice already exists.

| Practice | External anchor | How this plan uses it |
| --- | --- | --- |
| Walking skeleton and tracer bullet | [Tracer bullets and skeleton application](https://www.artima.com/articles/tracer-bullets-and-prototypes) | A minimal vertical policy path must run through request, spine, producer, claim registry, closeout, and projection before broad producer work expands. |
| Architecture decision records | [Microsoft ADR guidance](https://learn.microsoft.com/en-ie/azure/well-architected/architect-role/architecture-decision-record) | ADRs are append-only, standalone, superseded by new records, and separate structural commitments from tuned parameters. |
| Systems engineering traceability | [NASA systems engineering fundamentals](https://www.nasa.gov/reference/2-0-fundamentals-of-systems-engineering/) | Every capability keeps bidirectional traceability from research question to ADR, code artifact, producer, consumer, test, surface, and rollout evidence. |
| Machine-readable API contracts | [OpenAPI Specification](https://spec.openapis.org/oas/v3.0.4.html) | The typed PDC projection is not complete until OpenAPI, generated clients, and API schema compatibility checks exist. |
| Consumer/provider contract verification | [Pact provider verification](https://docs.pact.io/provider) | Public, dashboard, reviewer, expert, and machine consumers get contract tests that verify provider behavior before deployment. |
| Provenance interchange | [W3C PROV](https://www.w3.org/TR/prov-overview/) | Runtime evidence records distinguish entities, activities, agents, roles, generated artifacts, and derivations. |
| Data lineage facets | [OpenLineage specification](https://github.com/OpenLineage/OpenLineage/blob/main/spec/OpenLineage.md) | Data Forge, Fabric, and production-data contracts use explicit facets for schema, input/output, partitions, quality, and lineage rather than broad labels. |
| Assurance-case interchange | [OMG SACM](https://www.omg.org/spec/SACM/) | The PDC assurance graph remains compatible with SACM/CAE/GSN profiles already present in PolicyOS. |
| Release and canary safety | [Google SRE canarying](https://sre.google/workbook/canarying-releases/) and [release engineering](https://sre.google/sre-book/release-engineering/) | Wave 12 freezes revision/config, uses local then cloud canary evidence, and records rollout, rollback, and build/config identity. |
| Supply-chain attestation | [SLSA artifact verification](https://slsa.dev/spec/v1.2/verifying-artifacts) | Serious bundles preserve build, command, artifact, and verification provenance; packaging projections cannot substitute for authority. |

## Capability Definition Of Done

This plan uses the capability reality formula from the failure-pattern
register:

```text
Capability =
  typed contract/artifact
  + producer
  + persisted artifact/event
  + orchestration bridge
  + consumer
  + verification
  + external/audit/API/dashboard surface or explicit out_of_scope
  + negative/e2e semantic test
```

A phase cannot claim "implemented" while any of these labels still apply:

- `contract_only`
- `producer_missing`
- `artifact_missing`
- `bridge_missing`
- `consumer_missing`
- `verification_missing`
- `implemented_but_not_orchestrated`
- `surface_missing`
- `semantic_test_missing`

`surface_out_of_scope` is valid only with owner, rationale, review date, and
inspection path.

Every implemented capability must also have a traceability row containing:

- research refs: `C*`, `E*`, and relevant `P*` pattern ids;
- decision refs: ADR ids or an explicit `no_adr_required` rationale;
- reuse classification: `wire_existing`, `extend_existing`,
  `consolidate_existing`, or `build_new`;
- rejected-reuse evidence when `build_new` is selected;
- artifact refs: schema, runtime artifact, CAS/event ref, or generated contract;
- producer refs and consumer refs;
- verification refs: unit, integration, semantic, replay, and external contract
  tests where applicable;
- surface refs: API, dashboard, public export, audit, machine contract, or
  `surface_out_of_scope`;
- rollout refs: feature flag, tuned config version, canary command evidence,
  and rollback path.

## Reuse-First Gate

Every implementation task starts with a reuse classification:

| Classification | Meaning | Required evidence |
| --- | --- | --- |
| `wire_existing` | Existing producer, schema, reader, or validator already has the needed behavior but is not connected. | Code anchor, missing bridge, failing e2e test. |
| `extend_existing` | Existing owner is correct, but fields, statuses, tests, or readers are incomplete. | Code anchor, extension points, compatibility impact. |
| `consolidate_existing` | Multiple partial implementations exist and need one canonical owner. | Candidate owners, selected owner, shim/sunset plan. |
| `build_new` | No existing module can safely own the capability. | Rejected-reuse finding, owner, migration/surface plan, anti-pattern review. |

`build_new` is not forbidden, but it is expensive in governance terms. It must
name which existing modules were considered and why they were rejected. This
keeps the plan aligned with the research finding that many PolicyOS capabilities
are already sophisticated internally but thinly wired.

## Anti-Pattern Closure Map

Every wave must explicitly close or avoid these patterns from
`docs/reference/policy-design-case-failure-patterns.md`.

| Pattern | Primary closure in this plan | Guardrail |
| --- | --- | --- |
| P01 Contract-only capability | Wave 1 capability ratchet; Wave 3 producer adapters; Wave 6 universal-compilation kernel producer chain; Wave 7 RequirementSpec producers; Wave 8 PDC graph compiler producer; Wave 9 drift detector implementations; Wave 12 validation | No capability graduates without producer, consumer, persisted artifact, and semantic test. New compilation/requirement/graph/detector capabilities introduced by W6-W10 must ship with full chain or stay labelled `producer_missing`/`bridge_missing`. |
| P02 Thin orchestration | Waves 2-4 carriers/handoffs/claim registry/closeout; Wave 6 grammar+obligation+claim-decomposition compilers as the missing intent→producer bridge; Wave 7 staged producer pipeline orchestrator; Wave 8 PDC graph compilation as the missing claim→graph bridge | Producer outputs must bind to claim refs and reader surfaces. After W6-W8, the intent→graph chain has named owners at every step. |
| P03 Poor external surface | Waves 4-5 typed PDC projection and public/export/audit surfaces; Wave 8 argument/warrant graph surface; Wave 12 three-metric outcome reporting | Public/reviewer/expert/machine views expose the same truth. Argument graph and effective-independence graph become inspectable, not buried internals. |
| P04 Status proliferation | Wave 1 status envelope and deficit crosswalk; Wave 7 RequirementSpec status fields compose through envelope rather than new enums; Wave 9 drift event statuses compose through reissue lifecycle envelope | Local statuses remain local; cross-system effects compose through envelope axes. No W6-W10 phase may introduce a new top-level status enum without composition rules. |
| P05 Authority dilution | Waves 0, 1, 4, 5 authority boundaries and projection tests; Wave 6 LLM formulator and critic ensemble carry authority envelope (formulator may never mint); Wave 8 PDC graph distinct from projection prevents graph-becomes-projection-becomes-authority drift; Wave 10 review-effectiveness telemetry is advisory-only by construction | Projection, package, dashboard, and audit cannot mint missing authority. Hypothesis ledger candidates remain `candidate_unverified` until producer admission. |
| P06 Shim drift | Wave 0 source ownership; Wave 2 rule/shim evolution; Wave 5 docs; Wave 7 producer adapter refactor declares shim/sunset for legacy adapter behaviour; Wave 9 rule replay engine retires shim ambiguity for closed cases | Canonical paths and sunset behavior are visible. Refactor-introduced shims have explicit sunset and dual-read evidence. |
| P07 Rule versioning gap | Wave 2 rule registry; Wave 4 lifecycle; Wave 5 public revision state; Wave 9.F rule evolution replay engine (executes replay, not just registers refs) | Closed PDCs replay under original rule/taxonomy semantics. W9.F closes the producer side of E14. |
| P08 Time fragmentation | Waves 2-3 concept/legal/data adapters preserve time roles; Wave 7 RequirementSpec compilers enforce time-role admissibility per requirement family; Wave 9.C Data Forge provenance manifest preserves snapshot time semantics | Transform, limit, split, or block time mismatches. Time-role mismatches now blocked at compile time, not only at producer time. |
| P09 Soft-gate ambiguity | Waves 1-2 status/soft-gate lifecycle and telemetry; Wave 10.E complexity budget governance pruning; Wave 10.D run-cost enforcement gates carry owner/TTL | Warnings have owners, TTL, escalation, and publication/closeout effects. |
| P10 Structural-only validation | Waves 1 and 5 semantic fixtures and gold cards; Wave 10.C three missing R14 adversarial probes; Wave 11.E compilation truthfulness audit; Wave 12 three-metric ladder with compilation truthfulness | Structural pass is necessary but insufficient. Compilation truthfulness measures whether obligations were honestly derived. |
| P11 Failure-only memory | Wave 2 memory schema; Wave 5 balanced memory behavior; Wave 9.D memory decay + TTL + contamination controls | Success and opportunity patterns are captured with scope and TTL. Memory cannot accumulate forever. |
| P12 Producer fragmentation | Waves 2-4 producer handshake and orchestration; Wave 6.E LLM formulator + critic ensemble declares its coordination with deterministic producers; Wave 7.F 8-stage staged producer pipeline orchestrator implements the C40 producer state machine end-to-end | Producers coordinate through shared spine and emitted blockers. The staged pipeline forbids ad hoc producer ordering. |
| P13 Contract gravity well | Waves 2 and 5 complexity telemetry and governance pruning; Wave 10.E complexity budget governance pruning gates new controls by Net-MAV; new W6-W11 controls must declare Net-MAV in their phase ADRs | New controls declare expected Net-MAV and telemetry. W6-W11 are themselves subject to the ratchet: a new compiler/detector/tool that does not change a decision must be retired. |
| P14 Raw count inflation | Waves 3-5 effective independence and semantic evaluation; Wave 6.C obligation graph compiler creates an honest denominator (number of obligations actually required); Wave 8.F effective independence graph annotator with C29 graded calculus and `scarcity_structural`/`scarcity_remediable` split | Evidence strength reports effective support and collapse reasons. Raw count is meaningless without the obligation denominator. |
| P15 LLM speculation laundering | Waves 1, 3, 5 candidate firewall and semantic packs; Wave 6.E LLM formulator + critic ensemble routes all candidates through structured channels; Wave 6.F hypothesis ledger + candidate-to-authority firewall enforces source classification (`llm_candidate` / `llm_critic` / `llm_critic_consensus` / `llm_drafter` / `deterministic_producer`) at every read; Wave 10.C participation_speculation and fake critic-consensus adversarial probes | LLM content cannot satisfy evidence or authority slots. The firewall now has a structured input channel (formulator) and a structured probe surface (W10.C). |

## E-Task Coverage Map

This plan covers every engineering translation task from the research plan.

| E task | Primary wave | Supporting waves | Completion surface |
| --- | --- | --- | --- |
| E0 Capability Ratchet | Wave 1 | Wave 11 (new compilation/critic/detector capabilities), Wave 12 | Capability report and debt bands |
| E1 Corpus/Fixtures | Wave 1 | Wave 5, Wave 11 (universal outcome corpus) | Semantic false-pass fixture pack + repo-owned universal outcome corpus |
| E2 Status Lattice | Wave 1 | Wave 4, Wave 7 (RequirementSpec status composition) | Status envelope and deficit readers |
| E3 `can_i_closeout` | Wave 1, Wave 4 | Wave 10.A (temporal/liveness extension) | Closeout reader and CLI/API verdict |
| E4 Typed PDC Projection | Wave 4 | Wave 5, Wave 8 (re-validate projection over compiled PDC graph) | Pydantic/OpenAPI projection of `RuntimePolicyDesignCase` graph |
| E5 Client/Dashboard/Export | Wave 5 | Wave 8 (argument graph + Pareto/welfare surfaces), Wave 12 | Public/reviewer/expert/machine surfaces |
| E6 Concept Spine Kernel | Wave 2 | Waves 3-4, Wave 6 (universal grammar consumes spine) | Carrier, handshake, bridge records |
| E7 NL/Replay Integration | Wave 4 | Wave 7.F staged producer pipeline orchestrator carries the spine, Wave 12 | Request/job/replay/bundle continuity over universal compilation + staged pipeline |
| E8 IR to ClaimRecord | Wave 3 | Wave 4, Wave 7.C (method requirement compiler feeds IR bridge), Wave 8 | Claim-bound proof/certificate refs |
| E9 Lex Adapter | Wave 3 | Wave 4, Wave 7.B (Legal Authority Requirement Compiler + Lex refactor as consumer) | Claim-level legal anchors/blockers |
| E10 Fabric Adapter | Wave 3 | Wave 4, Wave 7.A (Data Requirement Compiler + Fabric refactor as consumer) | SourceContract selected/rejected/blocked bindings against compiled DataRequirementSpec |
| E11 Scholar Adapter | Wave 3 | Wave 5, Wave 7.D (Scholar Support Requirement Compiler + adapter refactor) | Claim-bound academic support/conflict refs |
| E12 Foundry Adapter | Wave 3 | Wave 4, Wave 7.C (Method Validity Requirement Compiler + Foundry refactor) | Method/assumption/uncertainty refs |
| E13 Portfolio Aggregation | Wave 4 | Wave 5, Wave 8.F (effective independence graph annotator with C29 graded calculus) | Effective independence report |
| E14 Rule Evolution | Wave 2 | Wave 4, Wave 9.F (rule replay engine — actual execution) | Rule/taxonomy refs and replay semantics |
| E15 Lifecycle/Reissue | Wave 4 | Wave 9.B (partial-scope reissue mechanics), Wave 9.E (continuous governance → lifecycle bridge) | Partial reissue and public revision state |
| E16 Data Forge Binding | Wave 3 | Wave 4, Wave 9.C (Data Forge provenance manifest with full lineage/quality fields) | Official snapshot/release closeout refs |
| E17 Acquisition Planner | Wave 3 | Wave 5, Wave 7.G (refactor to consume RequirementSpec gaps, not producer-output gaps) | Eligible strategy records and next actions |
| E18 Cost/SLA Gates | Wave 2 | Wave 4, Wave 10.D (run-cost enforcement gates with authority-level blocking) | Budget/degradation telemetry and closeout-blocking gates |
| E19 Self-FMEA | Wave 2 | Wave 5, Wave 10.B (review effectiveness pipeline), Wave 10.E (complexity governance pruning), Wave 10.F (repair-decision FMEA annotation) | Soft-gate, review, complexity telemetry + per-repair FMEA |
| E20 Calibration Ledger | Wave 2 | Wave 5 | Longitudinal influence records |
| E21 Balanced Memory | Wave 2 | Wave 5, Wave 9.D (memory decay/TTL/contamination controls) | Success/failure/opportunity influence records with finite lifetime |
| E22 Semantic Evaluation | Wave 5 | Wave 10.C (three missing R14 probes: authority spoofing, prompt injection, participation speculation), Wave 11 (universal outcome corpus expert adjudication), Wave 12 | Adversarial and semantic gold-card packs plus universal outcome adjudication |
| E23 Docs/ADRs/Runbooks | Waves 0, 1, 5 | Wave 12 (release docs + three-metric reporting) | Canonical evidence paths and ADR index |
| E24 Final Plan/Ladder | This plan | Wave 12 | Validation and rollout decision |

## Research Coverage Map

The implementation plan must also preserve coverage of every conceptual task
from the research plan and synthesis, not only the engineering `E` tasks.

| Research task | Primary implementation surface | Wave(s) |
| --- | --- | --- |
| C0 Capability baseline and canonical paths | capability ratchet, source ownership, docs paths | Waves 0-1 |
| C1 Status algebra | status envelope and mixed-status tests | Waves 1, 4 |
| C2 Admissibility and authority levels | status/deficit policy, producer adapters, closeout, RequirementSpec authority parameterisation | Waves 1, 3-4, 7 |
| C3 Unified closeout substrate | closeout reader and `can_i_closeout` verdict | Waves 1, 4, 10 (temporal extension), 12 |
| C4 Universal facet grammar | universal policy grammar compiler (W6.A) + facet-based RequirementSpecs (W7) | Waves 6-7 |
| C5 Obligation rule lifecycle | governed obligation rule catalog (W6.B) + obligation graph compiler (W6.C) + rule evolution registry/replay (W2.B / W9.F) | Waves 2, 6, 9 |
| C6 Concept identity | concept spine kernel and producer handshake; universal grammar consumes spine refs | Waves 2-4, 6 |
| C7 Legal authority and competence | Lex adapter + ADR-0168; Legal Authority Requirement Compiler refactor (W7.B) | Waves 0, 3-4, 7 |
| C8 Producer handshake protocol | spine, handoff, request/job/replay propagation; 8-stage staged producer pipeline (W7.F) | Waves 2, 4, 7 |
| C9 Claim taxonomy and method compatibility | IR/Foundry to ClaimRecord bindings; claim decomposition compiler (W6.D); method validity requirement compiler (W7.C) | Waves 3-4, 6, 7 |
| C10 Baselines and alternatives | claim decomposition seed (W6.D) + baseline+alternative compiler (W8.C); first-class baseline/alternative records bind into PDC graph | Waves 3-4, 6, 8 |
| C11 Numeric/time/geography semantics | Lex/Fabric/Data Forge/Foundry adapters; RequirementSpec compilers enforce time-role admissibility per claim | Waves 2-4, 7 |
| C12 LLM boundary | LLM formulator + multi-critic ensemble producer (W6.E); hypothesis ledger + candidate-to-authority firewall (W6.F); semantic laundering tests | Waves 1, 3, 5, 6 |
| C13 Effective independence | portfolio aggregation; effective independence graph annotator with C29 graded calculus (W8.F) | Waves 3-5, 8 |
| C14 Conflict and counterevidence | claim registry, portfolio, semantic packs; conflict-to-portfolio materializer as first-class fact (W8.E) | Waves 3-5, 8 |
| C15 Argument and warrant semantics | PDC assurance graph; argument/warrant graph builder over `assurance_case.py` (W8.B) | Waves 4-5, 8 |
| C16 Multi-audience PDC surface | typed projection, OpenAPI, generated clients; projection consumes compiled `RuntimePolicyDesignCase` graph (W8.A) | Waves 4-5, 8 |
| C17 Contestability | contested records and disagreement surfaces | Waves 0, 4-5 |
| C18 Tradeoffs and welfare | frontier/value-choice projection; Pareto frontier + social-weight provenance emitter (W8.D) | Waves 3-5, 8 |
| C19 Participation provenance | participation matrix; participation provenance requirement compiler (W7.E); participation speculation R14 probe (W10.C) | Waves 0, 3, 5, 7, 10 |
| C20 Lifecycle dependency | DDM/source/legal/context events to claim reissue; continuous governance → lifecycle bridge (W9.E); partial-scope reissue (W9.B); drift detector implementations (W9.A); Data Forge provenance manifest (W9.C) | Waves 4, 9, 12 |
| C21 Rule evolution and replay | rule registry; rule evolution replay engine (W9.F) | Waves 2, 4, 9 |
| C22 Evidence acquisition | acquisition decision ADR; acquisition planner; refactor to consume RequirementSpec gaps (W7.G) | Waves 0, 3, 5, 7 |
| C23 Run cost and degradation SLA | cost/degradation telemetry; run-cost enforcement gates with authority-level blocking (W10.D) | Waves 2, 4, 10, 12 |
| C24 Self-FMEA and liveness | bounded liveness; review telemetry; complexity budget; temporal/liveness invariant extension (W10.A); review effectiveness pipeline (W10.B); complexity governance pruning (W10.E); repair-decision FMEA annotation (W10.F) | Waves 0, 2, 5, 10 |
| C25 Calibration and memory | longitudinal calibration; balanced memory ledgers; memory decay + TTL + contamination controls (W9.D) | Waves 2, 5, 9 |
| C26 Evaluation methodology | semantic gold cards; adversarial packs; three missing R14 probes (W10.C); universal outcome corpus expert adjudication (W11); compilation truthfulness audit (W11.E) | Waves 1, 5, 10, 11, 12 |
| C27 Implementation readiness | this plan; ADR index; validation ladder | Waves 0, 12 |
| C28 Concept spine physical form | hybrid governed namespaces plus per-run artifact; universal grammar compiler consumes spine | Waves 2-4, 6 |
| C29 Effective independence function | strict collapse; graded weights behind config; effective independence graph annotator (W8.F) | Waves 4-5, 8 |
| C30 Semantic benchmark rubric | false-pass fixtures; adjudication metadata; expert adjudication labels on universal outcome corpus (W11.C); rotating fixtures (W11.D) | Waves 1, 5, 11 |
| C31 Deficits by authority level | deficit dispositions; closeout/public effects; RequirementSpec deficit propagation (W7.A-E) | Waves 1, 4, 7 |
| C32 Complexity budget | telemetry-derived advisory complexity report; complexity governance pruning (W10.E) | Waves 2, 5, 10 |
| C33 Rule evolution public policy | public annotation; revalidation triggers; rule replay engine over change classes (W9.F) | Waves 2, 4-5, 9 |
| C34 Participation legitimacy | claim-use downgrade; representativeness config; participation requirement compiler (W7.E) | Waves 0, 3, 5, 7 |
| C35 Calibration blocking thresholds | warning/review first; blocking only after mature data | Waves 2, 5 |
| C36 Capability debt algebra | debt labels; severity; readiness bands | Waves 1, 12 |
| C37 Bridge authority | boundary-scoped closeout input, not producer evidence; staged pipeline orchestrator preserves bridge authority (W7.F) | Waves 2, 4, 7 |
| C38 Obligation explosion control | candidate/bundle/blocking frontier ledger in obligation graph compiler (W6.C) | Waves 6 |
| C39a Projection structure | typed audience projection; external contracts; new graph surface (W8.A → W4.E/W5.A) | Waves 4-5, 8 |
| C39b Recourse mechanics | contested record; recourse pointer; ingestion hook | Waves 0, 4-5 |
| C40 Producer coordination liveness | bounded handshake states and deadlines; 10 producer states fully implemented in staged pipeline orchestrator (W7.F); bounded-liveness deadline-consistency invariants (W10.A) | Waves 2, 4, 7, 10 |
| C41 Historical priors firewall | influence records only; no current evidence slot; memory decay + contamination controls (W9.D) | Waves 2, 5, 9 |

## Artifact Classes

The implementation must persist these artifact classes where applicable:

| Artifact | Purpose | Authority boundary |
| --- | --- | --- |
| Fast-track ADR | Ratify structural decisions before engineering | Design authority, not runtime evidence |
| Capability reality report | Track implementation maturity | Release/readiness signal |
| Semantic gold card | Explain structural false pass | Evaluation authority |
| Status envelope | Compose local statuses | Reader/closeout input |
| Deficit record | Preserve accepted, limited, review, reissue, or blocking gaps | Claim/readiness input |
| Concept spine artifact | Reconcile concepts for this run | Semantic closeout input |
| Producer handshake record | Show consumed/emitted/rejected/blocked bindings | Boundary/provenance input |
| Bridge/handoff record | Prove boundary continuity | Closeout input only for boundary facts |
| Claim registry entry | Bind claim to evidence, counterevidence, limits, deficits | Claim authority surface |
| Producer adapter report | Data/legal/scholar/method/source binding | Producer authority if enveloped |
| Acquisition action record | Show eligible strategies and next action | Governance/routing input |
| Effective independence report | Collapse dependent evidence | Portfolio authority input |
| Rule evolution record | Preserve rule/taxonomy meaning over time | Replay/revalidation input |
| Closeout verdict | Single answer for can-this-run-close-out | Closeout authority only |
| PDC projection | Public/reviewer/expert/machine view | Projection only |
| API/consumer contract verification | Prove external consumers receive truth-preserving shapes | Surface compatibility input |
| PROV/lineage projection | Interchangeable provenance and data-lineage view | Audit/lineage input, not domain evidence |
| Canary/rollout record | Freeze revision/config and rollout result | Release decision input |
| Calibration/memory influence record | Affect future routing and review | Never current-run evidence |

## Wave Summary

| Wave | Purpose | Parallel phases | Exit gate |
| --- | --- | ---: | --- |
| Wave 0 | Ratify decisions and freeze source ownership | 8 | ADRs accepted; raw source repo-owned; no gated engineering ambiguity |
| Wave 1 | Build capability, status, closeout, and semantic-test foundations | 5 | Shared substrate contracts and fixtures exist |
| Wave 2 | Build reusable spines, registries, ledgers, and telemetry primitives | 6 | Producers can target stable runtime carriers and governed configs |
| Wave 3 | Wire producer adapters and claim-bound evidence surfaces | 7 | Lex/Fabric/Scholar/Foundry/Data Forge/IR emit claim-bound refs or blockers |
| Wave 4 | Integrate orchestration, portfolio, closeout, lifecycle, and projection | 5 | Runtime can compile a typed claim-bound PDC graph and closeout verdict |
| Wave 5 | Expose external surfaces, semantic evaluation, calibration, and memory | 5 | Auditors and users see truth-preserving surfaces; evaluation catches false pass |
| Wave 6 | Universal compilation kernel: grammar, obligations, claim decomposition, LLM formulator/critics, hypothesis ledger | 6 | Any policy intent compiles into typed `UniversalPolicyDesignCase` + `ObligationGraph` + `ClaimFamilyAssignment` + `CandidateLedger` with firewall, without any producer adapter call |
| Wave 7 | Requirement compilation + producer adapter refactor + staged producer pipeline | 7 | Each producer adapter consumes a typed RequirementSpec; 8-stage staged execution orchestrator drives producers; acquisition planner consumes requirement gaps |
| Wave 8 | PDC graph compilation + argument/warrant building + Pareto/conflict/effective-independence emission | 6 | Runtime emits a typed `RuntimePolicyDesignCase` graph separate from projection; argument/warrant graph; baseline/alternative records; Pareto frontier with social-weight provenance; first-class conflict records; graded effective independence graph |
| Wave 9 | Advanced lifecycle: drift detector implementations, partial-scope reissue, Data Forge provenance manifest, memory decay, lifecycle bridge, rule replay engine | 6 | Drift events fire detectors; reissue can affect only scoped claims; snapshot manifests carry full provenance; memory decays under TTL; closed cases replay under original rules |
| Wave 10 | Temporal/liveness invariants + run-cost enforcement + review-effectiveness + missing R14 probes + complexity-budget governance + repair-decision FMEA | 6 | Bounded-liveness extends finite-state invariants; cost/SLA breaches enforce per authority level; review-effectiveness telemetry is measured (advisory); 3 missing adversarial probes (authority spoofing / prompt injection / participation speculation) land; complexity budget gates new controls by Net-MAV; prompt/tool repair decisions carry FMEA refs |
| Wave 11 | Universal outcome corpus (12+ real cases, 6+ domains, 3 authority levels) + compilation truthfulness + domain coverage breadth + critic ensemble diversity tools | 6 | Corpus is repo-owned, expert-adjudicated, fixture-loadable; truthfulness/breadth/diversity tools run against W6-W10 outputs |
| Wave 12 | End-to-end revalidation + universal outcome run + rollout decision | 7 | Local validation ladder re-run over real compiled PDC; three-metric reporting (closeout honesty + useful design + compilation truthfulness); universal outcome corpus run; cloud one-lane revalidation; rollout decision with frozen revision/config |

## Mandatory Integration Slices

Integration is scheduled work, not a passive wave-transition hope. Each slice
has an owner, effort budget, fixtures, and command evidence. A wave cannot exit
if its required integration slice is missing; the wave can only exit with a
typed blocker or accepted hold.

| Slice | Earliest point | Size | Purpose | Required proof |
| --- | --- | ---: | --- | --- |
| I0 ADR/source traceability | Wave 0 exit | S | Prove the decision/source graph is repo-owned and queryable. | ADR index links raw source, synthesis, C/E/P ids, and gated tasks. |
| I1 Closeout skeleton smoke | Wave 1 exit | M | Prove closeout is a separate reader over real fixture artifacts, not projection truth. | One incomplete fixture emits typed closeout blocker and cannot be overridden by projection/readiness. |
| I2 Walking skeleton | Wave 2 exit | L | Prove the thinnest vertical PDC path before broad producer adapters. | One trivial policy request, one claim, one minimal deterministic producer fixture, one concept spine record, one claim registry entry, one closeout verdict, one typed projection, one semantic negative. |
| I3 Producer adapter mid-wave checkpoint | Wave 3 midpoint | L | De-risk Wave 3 breadth before all producers are complete. | At least Lex plus Fabric, or Fabric plus Foundry, emit real selected/rejected/blocked bindings into the same ClaimRecord and closeout reader. |
| I4 First real PDC graph | Wave 4 midpoint | L | De-stub portfolio, lifecycle, closeout, and projection on real producer outputs. | A real multi-producer fixture builds PDC graph, effective portfolio, closeout verdict, and typed projection without stubbed sibling outputs. |
| I5 External consumer truth check | Wave 5 midpoint | M | Prove external surfaces preserve closeout truth. | Public, reviewer, expert, and machine fixtures pass schema contracts and semantic omission/blocker checks. |
| I7 Universal compilation smoke | Wave 6 midpoint | L | Prove universal compilation kernel works without any producer adapter call. | One toy policy intent compiles into facets, ObligationGraph, ClaimFamilyAssignment, candidate ledger entries, critic verdicts, firewall-enforced authority envelope, and a typed compilation-only PDC stub without invoking Lex/Fabric/Foundry/Scholar. |
| I7-bis Universal compilation integration realism check | Wave 6 exit; revalidated before Wave 12 | L | Catch "components exist but runtime skips them" before the outcome corpus. | One toy policy intent runs grammar -> governed rules + LLM formulator + critic ensemble -> obligation graph -> hypothesis ledger artifact -> claim decomposition -> RequirementSpecs with hardcoded data-family fallback disabled where possible -> producer pipeline in real or corpus-stub mode -> RuntimePolicyDesignCase graph -> typed projection/audit surface. The runner must prove each W6/W7 component was invoked and emit typed blockers for missing producer bindings, graph edges, or warrant structures. |
| I8 Compiled PDC graph end-to-end | Wave 7+8 join | XL | Prove the new universal path (intent → compiler → requirement specs → refactored adapters → staged pipeline → PDC graph → argument graph → projection) works as one continuous chain. | One real-ish multi-producer fixture compiles requirement specs, drives the 8-stage pipeline, emits selected/rejected/blocked bindings against compiled requirements, builds a `RuntimePolicyDesignCase` graph distinct from projection, and renders the typed projection without scenario-family hardcoding. |
| I9 Lifecycle drift smoke | Wave 9 exit | L | Prove drift detector → partial reissue → graph revision chain works. | One closed PDC fixture experiences a calibration/source/legal/policy-context drift event; the matching detector fires; a partial-scope reissue affects only the named claim ids; the public revision state updates without whole-case rewrite; replay under original rule logic still reproduces the closed semantics. |
| I10 Cost gate + FMEA smoke | Wave 10 exit | M | Prove cost/SLA gates fire as authority-level blockers and the FMEA pipeline annotates repair decisions. | One fixture exhausts cost budget under a production-authority profile and fails with a typed cost blocker; another fixture triggers a prompt/tool repair and records a FMEA annotation that surfaces in closeout and projection; one of the three new R14 probes fires against a structurally-complete fixture and forces semantic-fail. |
| I11 Outcome corpus first pass | Wave 11 midpoint | L | Prove that the universal outcome corpus is well-formed and exercise the truthfulness/breadth/diversity tools end-to-end. | First 3 corpus cases are compiled via the universal path, expert adjudication labels exist, fixture loaders work, compilation truthfulness tool runs and reports per-case truthfulness scores, domain-coverage and critic-diversity tools emit baseline metric values. |
| I12 Three-metric validation ladder | Wave 12 midpoint | XL | Prove the universal outcome track passes (or fails honestly) with all three outcome metrics reported separately. | Local validation ladder produces closeout honesty rate, useful design rate, and compilation truthfulness rate over the full universal outcome corpus; per-domain useful-design floor is visible; no typed blocker is counted as useful design; rollout posture decision can cite all three numbers. |
| I6 Local/cloud release rehearsal | Wave 12 midpoint | L | Prove rollout evidence is complete before final canary. | Frozen revision/config, feature flags, command evidence, bundle inspection, and rollback path exist before cloud one-lane run. |

The walking skeleton is intentionally narrow. It may use deterministic fixture
producers and a toy policy, but it must traverse the real runtime seam:

```text
request
  -> authority profile
  -> concept spine
  -> producer handshake
  -> claim registry
  -> closeout reader
  -> typed PDC projection
  -> semantic negative test
```

It is not allowed to prove only schemas, constructor validity, or mocked API
responses. Its purpose is to fail early when the orchestration contract itself
is wrong.

## Sizing, Critical Path, And Team Model

Sizes are relative planning buckets, not commitments:

- **S:** one bounded module or doc/ADR artifact;
- **M:** one small subsystem plus tests and docs;
- **L:** cross-subsystem bridge or adapter with integration tests;
- **XL:** multiple subsystems, external surface, or high-uncertainty producer
  remediation.

If the team has fewer than five effective parallel workstreams, phases should
be scheduled by the critical path below rather than treated as simultaneously
available.

**Critical path:**

```text
Wave 0 ADRs
  -> W1.C status/deficit + W1.D closeout skeleton
  -> I1 closeout smoke
  -> W2.A concept spine + W2.B rule evolution
  -> I2 walking skeleton
  -> W3.A IR bridge + W3.B Lex + W3.C Fabric + W3.E Foundry minimum paths
  -> I3 producer adapter checkpoint
  -> W4.B portfolio + W4.D closeout + W4.E projection
  -> I4 first real PDC graph
  -> W5.A external surfaces + W5.B semantic evaluation
  -> I5 consumer truth check
  -> W6.A grammar compiler + W6.B obligation rule catalog + W6.C obligation graph + W6.D claim decomposition + W6.E LLM formulator/critics + W6.F hypothesis firewall
  -> I7 universal compilation smoke
  -> W7.A-E requirement compilers + adapter refactors + W7.F staged pipeline + W7.G acquisition refactor
  -> W8.A PDC graph compiler + W8.B argument graph + W8.C baselines + W8.D Pareto/welfare + W8.E conflict + W8.F effective independence
  -> I8 compiled PDC graph end-to-end
  -> W9.A drift detectors + W9.B partial reissue + W9.C Data Forge provenance + W9.D memory decay + W9.E lifecycle bridge + W9.F rule replay
  -> I9 lifecycle drift smoke
  -> W10.A temporal/liveness + W10.B review effectiveness + W10.C missing R14 probes + W10.D cost gates + W10.E complexity governance + W10.F repair FMEA
  -> I10 cost gate + FMEA smoke
  -> W11.A-D corpus build + W11.E-F truthfulness/breadth/diversity tools
  -> I11 outcome corpus first pass
  -> Wave 12 three-metric local + cloud validation
  -> I12 three-metric validation ladder
  -> I6 release rehearsal
  -> W12.G rollout decision
```

**Recommended workstream model:**

| Workstream | Primary ownership | Notes |
| --- | --- | --- |
| Integration spine | closeout, claim registry, concept spine, walking skeleton, universal-compilation kernel, PDC graph compiler, staged pipeline | Must stay small and senior; owns I1-I12. Centre of gravity shifts from "wiring existing producers" to "owning the universal compilation pathway" once Wave 6 begins. |
| Producer adapters | Lex, Fabric, Scholar, Foundry, Data Forge, IR bridges, plus per-producer Requirement Compilers | Producer owners work to shared Wave 2 + Wave 7 interfaces. After Wave 7 they own both the RequirementSpec compiler and the refactored adapter for their family. |
| External surface | PDC projection, OpenAPI, generated clients, public/export/dashboard/audit, argument graph projection | Owns consumer contract verification. After Wave 8 also owns the projection of the new `RuntimePolicyDesignCase` graph and argument/warrant structure. |
| Evaluation and corpus | semantic fixtures, real policy corpus, adversarial packs, universal outcome corpus, compilation truthfulness / domain coverage / critic ensemble diversity tooling | Owns outcome metrics and false-pass discovery. Wave 11 is its primary delivery wave. |
| Governance operations | ADRs, tuned config, feature flags, runbooks, risk register, complexity governance pruning, repair-decision FMEA, drift detector ownership | Prevents thresholds and source ownership from drifting. Waves 9 and 10 expand its surface significantly. |
| LLM formulation and critics | LLM formulator producer, multi-critic ensemble, hypothesis ledger, candidate-to-authority firewall | New workstream introduced in Wave 6. Must keep critics on substantively different bases (legal/fiscal/equity/data/implementation/affected-person/adversarial/monitoring), not just different personas. Owns C12/P15 closure. |

**Phase size briefs:**

#### W0 ADRs And Source Ownership - S/M, High

Wave 0 phases are individually small to medium, but their leverage is high
because conceptual ambiguity compounds downstream. These are decision and
ownership artifacts, not runtime code. Their success condition is that later
engineering can cite an accepted ADR, source path, or explicit hold rather than
re-opening the same conceptual boundary in code review.

#### W1.A Capability Ratchet - M, High

This phase defines whether work is allowed to graduate. The size is medium
because it mostly builds reporting, labels, templates, and validation hooks over
existing quality tools. It is high criticality because every later capability
inherits its definition of `implemented`, `held`, or still incomplete.

#### W1.B Semantic Fixtures - M, High

This phase creates the first content-level false-pass fixtures. It is medium
because the first fixture set is intentionally small, but high criticality
because structural tests without semantic negatives would recreate the core
failure mode. The work should favor a few sharp examples over a large but weak
fixture collection.

#### W1.C Status And Deficits - L, Critical

This phase is large because it crosses support, readiness, publication,
warnings, deficit disposition, and closeout semantics. It is critical because
mixed-status behavior determines whether the system blocks, limits, reviews,
reissues, or publishes. Mistakes here propagate into every producer and external
surface.

#### W1.D Closeout Skeleton - L, Critical

This phase builds the first closeout seam. It is large because even a skeleton
must preserve authority boundaries, read fixture artifacts, and fail closed
when projection/readiness tries to stand in for evidence. It is critical because
it proves closeout is a runtime reader, not a summary flag.

#### W1.E Documentation Paths - S, Medium

This phase is small and keeps source ownership durable. It matters because a
research source, runbook, ADR, or command evidence path outside the repository
turns into P06-style ownership ambiguity. It should stay lightweight and
mechanical.

#### W2.A Concept Spine And Handshake - XL, Critical

This is one of the hardest phases. It creates the shared semantic carrier for
policy terms, data columns, legal concepts, method requirements, populations,
geographies, units, and time roles. It is critical because producer
coordination, effective independence, and per-claim evidence binding all depend
on this spine being real rather than an after-the-fact reconciliation note.

#### W2.B Rule Evolution - L, High

This phase protects replay and public revision truth. It is large because it
has to distinguish schema migration from semantic rule change, preserve old
logic, and record public revalidation effects. It is high criticality because a
closed PDC must remain historically interpretable even when rules improve.

#### W2.C Cost And Degradation - M, Medium

This phase starts with telemetry rather than hard gates. It is medium because
provider calls, tokens, retries, search cost, compute, and wall-clock behavior
need a shared shape, but most consequences stay advisory at first. It should not
delay the critical integration spine unless cost data reveals a hard production
blocker.

#### W2.D Self-FMEA And Soft Gates - L, High

This phase prevents warning and complexity drift. It is large because it links
bounded liveness, warning ownership, review telemetry, repair-decision FMEA,
and complexity budget signals. It is high criticality because unowned warnings
and ceremonial gates silently erode both capability and trust.

#### W2.E Calibration Ledger - M, Medium

This phase defines a future-influence surface, not current-run evidence. It is
medium because the schema and influence boundaries are important, but most
blocking thresholds remain governed config until longitudinal data exists. It
must be especially strict about not laundering historical priors into current
claim closure.

#### W2.F Balanced Memory - M, Medium

This phase avoids failure-only learning and prior laundering. It is medium
because memory schema, scope, TTL, revocation, and influence records can reuse
existing memory foundations. It is medium criticality at first because it
affects future routing, not immediate closeout.

#### W3.A IR Bridge - XL, Critical

This phase connects proof-carrying analytics to ClaimRecord. It is extra large
because IR certificates, negative certificates, proof composability,
uncertainty, baselines, and conflicts all need claim-bound runtime refs. It is
critical because the existing analytics strength does not become policy
authority until it is bridged.

#### W3.B Lex Adapter - XL, Critical

This phase turns legal retrieval into claim-level legal authority. It is extra
large because it changes binary/global legal behavior into graded,
competence-aware, time-windowed anchors with selected, rejected, and no-anchor
outcomes. It is critical because legal competence is a production blocker.

#### W3.C Fabric Adapter - XL, Critical

This phase makes data admissibility source-contract based. It is extra large
because broad bundles must be demoted, OpenLineage-like facets must be exposed,
and scenario source families must bind to claims. It is critical because data
availability is not the same as admissible data evidence.

#### W3.D Scholar Adapter - L, High

This phase binds academic evidence to claims with source quality, snippets,
freshness, support/conflict links, and dependence records. It is large but
smaller than Lex/Fabric/Foundry because it can reuse existing Scholar search
models and scoring. It is high criticality for evidence synthesis, but less
often a hard production gate than legal or data authority.

#### W3.E Foundry Adapter - XL, Critical

This phase records method authority before claims depend on method outputs. It
is extra large because selected/rejected methods, runtime assumption gates,
uncertainty envelopes, simulation assumptions, sensitivity, and limitations
must all bind to ClaimRecord. It is critical because generic execution cannot
support serious policy method claims.

#### W3.F Data Forge Binding - L, High

This phase makes snapshots, releases, read APIs, merkle/data hashes, lineage,
and quality gates closeout-grade. It is large because it crosses storage,
release manifests, quality reports, and claim requirements. It is high
criticality because file availability alone must not satisfy data authority.

#### W3.G Acquisition Planner - XL, High

This phase turns evidence gaps into honest next actions. It is extra large
because strategy eligibility, mandatory-gate dominance, VOI ranking, proxy
limitations, accepted deficits, and human/governed commit all interact. It is
high criticality because universal design needs to say how to proceed, not only
how to block.

#### W4.A NL/Replay Orchestration - L, Critical

This phase carries the spine through request context, workflow state, job
progress, replay, bundle, inspection, readiness, and export paths. It is large
because it touches runtime control surfaces, but it should not invent new
evidence semantics. It is critical because orchestration loss is the recurring
system failure.

#### W4.B Portfolio Aggregation - XL, Critical

This phase makes evidence strength truthful. It is extra large because raw
count, dependence, conflict, counterevidence, rarity, and limitations must
compose without inflating authority. It is critical because a portfolio that
counts echoes as independent evidence is worse than no portfolio.

#### W4.C Lifecycle And Partial Reissue - L, High

This phase prevents stale closed cases. It is large because source, legal,
participation, calibration, DDM, and context events need to map to affected
claims rather than whole-case rewrites. It is high criticality because
universal policy design is a living case, not a frozen PDF.

#### W4.D Closeout Integration - XL, Critical

This phase produces one can-closeout verdict over real reports. It is extra
large because it integrates invariants, source truth, attestation,
compatibility, semantic closure, claim registry, PDC records, projection, and
complexity. It is critical because local pass flags are not closeout authority.

#### W4.E PDC Projection Backend - XL, Critical

This phase builds the typed external truth surface. It is extra large because
OpenAPI, generated clients, projection gaps, contested records, recourse
pointers, deficit registers, invariant summaries, and non-authority projection
semantics all need to hold together. It is critical because legitimacy depends
on what external audiences can inspect.

#### W5.A External Surfaces - L, High

This phase makes public, reviewer, expert, machine, dashboard, export, and
audit surfaces consume the same projection truth. It is large because each
audience needs different detail and redaction while preserving the same
blockers and omissions. It is high criticality because external visibility is
part of policy legitimacy.

#### W5.B Semantic Evaluation - L, Critical

This phase finds false pass. It is large because adversarial packs, gold cards,
hidden/public/rotating fixtures, and expert labels must detect real content
failure, not schema failure. It is critical because universal capability cannot
be inferred from structural completeness.

#### W5.C Calibration Behavior - M, Medium

This phase connects calibration history to future posture. It is medium because
the initial behavior is warning/review and feature-flagged gates, not mature
blocking. It remains medium criticality until enough longitudinal data exists
to justify harder consequences.

#### W5.D Balanced Memory Behavior - M, Medium

This phase makes success, failure, and opportunity memory retrievable with
scope, TTL, revocation, and contamination controls. It is medium because it
should influence routing and review, not current-run evidence. It prevents the
system from becoming defensively biased by remembering only failures.

#### W5.E Docs And Runbooks - M, Medium

This phase gives operators durable command paths, ADR indexes, tuned-parameter
owners, validation ladders, and capability evidence. It is medium because the
documentation is operational, not decorative. It is medium criticality because
bad docs can hide source ownership and rollout drift.

#### W6 Universal Compilation Kernel - XL, Critical

This wave is the missing L2 universal-grammar/obligation-graph/claim-decomposition/LLM-formulator layer that lets the system compile any policy intent into a typed PDC kernel without scenario-family hardcoding. It is extra large because it introduces six new producer families (grammar compiler, obligation rule catalog, obligation graph compiler, claim decomposition compiler, LLM formulator + multi-critic ensemble, hypothesis ledger + firewall) that all must ship with full capability chain. It is critical because Wave 7's requirement compilers cannot start without W6 interface schemas, and the entire downstream universal capability claim rests on this kernel.

#### W6.A Universal Policy Grammar Compiler - XL, Critical

This phase introduces the canonical `UniversalPolicyDesignCase` schema and the compiler that turns a free-text/structured policy intent plus authority profile and concept-spine refs into typed facets (instrument, targeting, delivery, funding, authority types, outcome channels, risk facets, method needs, population/geography/time scope). It is extra large because it must reconcile with existing `ProblemFrame`, `PolicySpec`, `PolicyCandidateSchema`, `ConstraintCritic` failure classes, `challenge_factory` classes, and IR governance enums without duplicating them. It is critical because every later compilation step consumes its facet output.

#### W6.B Governed Obligation Rule Catalog - L, Critical

This phase establishes the typed rule catalog (rule family, rule version, logic hash, owner, scope, authority level, evidence basis, deprecation policy, public revalidation effect) and seeds the initial taxonomy from temporal logic patterns, deterministic critic outputs, and historical-failure mining. It is large because the schema must accommodate per-jurisdiction governed config, multi-authority facets, and replay refs from day one. It is critical because Wave 6.C cannot compile obligations without governed rules; LLM rule candidates may not become rulebook by default.

**Track B reopened exit criterion:** catalog closure now requires at least 20 vertical case-specific obligation rules with structured `logic.facet_match_all` patterns, owner, evidence basis, deterministic `logic_hash`, and seed provenance from W11.B annotations. Horizontal cross-cutting rules remain governed rules, but W12.B truthfulness is scored against the vertical case-annotation slice when present.

#### W6.C Obligation Graph Compiler With Candidate/Bundle/Frontier Ledger - XL, Critical

This phase implements C38's three-tier ledger (candidate ledger / bundle ledger / blocking frontier) and the compiler that turns facets + governed rules + producer/critic/LLM candidate sources into typed obligations with source classification, priority class, dominance rules, deduplication, lineage collapse, and lexicographic promotion (authority allowance, legal/privacy admissibility, current-run evidence relevance, material public risk, VOI, cost/burden, complexity budget). It is extra large because obligation explosion control is a load-bearing firewall and must work at hundreds of candidates per case. It is critical because raw count inflation (P14) cannot be measured without the honest denominator the graph provides.

#### W6.D Claim Decomposition Compiler With Baseline/Alternative Seed Records - L, Critical

This phase turns policy intent + obligations + scope into typed `ClaimFamilyAssignment` records (preference/lived-experience/acceptability/legitimacy/procedural-fairness/feasibility/objection/context, plus causal/distributional/welfare/forecast/implementation claim types). It seeds baseline (no-action, status-quo, business-as-usual, named alternatives) and rejected-alternative records so superiority claims can later require comparison evidence. It is large because the decomposer reconciles claim taxonomies across Scientist, IR analytics, Foundry methods, and Lex norms. It is critical because all Wave 7 RequirementSpec compilers are claim-bound at the per-claim level.

#### W6.E LLM Formulator + Multi-Critic Ensemble Producer - XL, Critical

This phase introduces the LLM formulator as a structured producer that emits typed candidate fields/risks/obligations into the hypothesis ledger, plus a multi-critic ensemble (legal, fiscal, equity, data, implementation, affected-person, adversarial, monitoring) where each critic carries a substantively different basis (deterministic rule set, statistical pattern, historical failure corpus, legal corpus probe, simulation probe, participation provenance check, etc.) — not just different LLM personas. It is extra large because LLM/critic source classification, prompt fingerprinting, repair-decision lineage, and authority-envelope enforcement all flow through this phase. It is critical because C12 LLM boundary closure depends on the formulator existing as a real input channel, not as an implicit text-blob.

**Track A/B reopened exit criterion:** the formulator and multi-critic ensemble must be invoked from the runtime universal-compilation path (`run_universal_outcome_corpus.py` or an equivalent runner), and a hypothesis-ledger artifact must be persisted per case. Critic consensus may enter the obligation graph only through `LLM_CRITIC_CONSENSUS` at `REVIEW_REQUIRED`; it is review signal, not authority.

#### W6.F Hypothesis Ledger + Candidate-To-Authority Firewall - L, Critical

This phase persists every formulator/critic candidate with provenance, source class (`llm_candidate` / `llm_critic` / `llm_critic_consensus` / `llm_drafter` / `deterministic_producer`), authority envelope, and admission state, and implements the firewall that forbids candidate content from entering legal/data/method/participation/closeout authority slots without producer/reader validation. It is large because it must integrate with prompt_tool_ledger, semantic binding, and projection paths to ensure no laundering surface remains. It is critical because P15 LLM speculation laundering is closeable only when the firewall has a real input to gate.

#### W7 Requirement Compilation + Producer Adapter Refactor + Pipeline Orchestrator - XL, Critical

This wave moves the W3 producer adapters from "selectors over their internal pools" to "consumers of typed RequirementSpec produced by per-family compilers" and implements the 8-stage staged producer pipeline orchestrator from synthesis. It is extra large because every existing W3 adapter is touched plus five new requirement compilers and a new orchestrator. It is critical because the W6.A regression on production data source families exists exactly because this wave is missing.

#### W7.A Data Requirement Compiler + Fabric Adapter Refactor - XL, Critical

This phase introduces typed `DataRequirementSpec` (per claim: required data families, scope, recency, lineage strictness, quality minima, admissibility predicates, transformation tolerance) and refactors W3.C Fabric adapter to consume it: SourceContract selection now binds to compiled requirements rather than a hardcoded `scenario_evidence_contract.admissible_data_source_families` list. It is extra large because it touches both the compiler module and the entire Fabric source-selection path. It is critical because data-evidence admissibility for any new domain depends on it.

**Track A/B reopened exit criterion:** `DataRequirementCompiler` must derive required data families from `obligation_graph.blocking_frontier` when data-family obligations provide `evidence_family` / `data_family`; the hardcoded heuristic remains only as a feature-flagged fallback and is sunset once the vertical data rules are seeded.

#### W7.B Legal Authority Requirement Compiler + Lex Adapter Refactor - XL, Critical

This phase introduces typed `LegalAuthorityRequirementSpec` (per claim: jurisdiction hierarchy, temporal competence window, authority-type facets — implementing/delegating/enabling/funding/oversight/appeal — required instrument classes, scope/population/time predicates) and refactors W3.B Lex adapter to consume it. It is extra large because Lex must move from set-membership matches to graded admissibility under compiled requirements. It is critical because legal competence is a production blocker for any non-trivial policy.

#### W7.C Method Validity Requirement Compiler + Foundry Adapter Refactor - XL, Critical

This phase introduces typed `MethodValidityRequirementSpec` (per claim: identification class, transportability requirement, uncertainty class, fairness decomposition need, strategic-response sensitivity, simulation DGP requirements) and refactors W3.E Foundry adapter and W3.A IR bridge to consume it. It is extra large because method-claim compatibility is a research-heavy area and the compiler must reuse IR analytics certificates rather than rebuild them. It is critical because generic method labels can no longer satisfy serious method obligations.

#### W7.D Scholar Support Requirement Compiler + Scholar Adapter Refactor - L, High

This phase introduces typed `ScholarSupportRequirementSpec` (per claim: required publication tier, recency, replication count, independence breadth, citation-network depth, dependent-corpus collapse rules) and refactors W3.D Scholar adapter to consume it. It is large but smaller than data/legal/method because Scholar reuse is broad and the requirement schema is comparatively simple. It is high criticality for evidence synthesis depth.

#### W7.E Participation Provenance Requirement Compiler + Participation Surfaces Refactor - L, Critical

This phase introduces typed `ParticipationProvenanceRequirementSpec` (per claim use: required mode — survey, deliberative panel, hearing, complaint, testimony, expert interview — required sampling frame, representativeness class, consent/redaction, dissent handling, sponsor disclosure) under FT-ADR-02 and refactors participation surfaces to consume it. It is large because participation crosses Scholar, Scientist policy_design, and external surfaces. It is critical because LLM/analyst speculation laundering as affected-person preference is the most politically dangerous failure mode.

#### W7.F 8-Stage Producer Pipeline Orchestrator - XL, Critical

This phase implements the C40 10-state producer machine and the 8-stage staged execution (run contract → spine bootstrap → parallel preflight → first-pass context/blocker emission → provisional claim registry → second-pass authoritative binding → semantic closure → closeout/projection). It is extra large because it owns producer liveness, deadline consistency, peer-wait naming, and the context-only-vs-binding distinction across all producer families. It is critical because without it, requirement compilers and refactored adapters drift back to ad hoc ordering.

#### W7.G Acquisition Planner Refactor As Requirement Gap Consumer - L, High

This phase refactors W3.G acquisition planner to consume gaps in compiled RequirementSpecs (not gaps in producer outputs), under ADR-0166. It is large because eligibility-precedes-ranking and three-terminal-state semantics now apply at the compiled-requirement level. It is high criticality because acquisition is how the system says "what to do next" when compilation produces unmet requirements.

#### W8 PDC Graph Compilation + Argument Building + Welfare/Conflict Emission - XL, Critical

This wave delivers the L7 PDC graph compiler distinct from projection plus the argument/warrant graph, baseline+alternative comparison, Pareto frontier with social-weight provenance, first-class conflict records, and graded effective-independence graph. It is extra large because six distinct emitters must agree on a single graph schema. It is critical because the current plan implicitly conflates graph compilation with projection inside W4.E.

#### W8.A RuntimePolicyDesignCase Graph Compiler - XL, Critical

This phase introduces the typed `RuntimePolicyDesignCase` graph (claim graph, warrant structures, obligation refs, producer binding refs, baseline/alternative refs, conflict refs, effective-independence refs, closeout refs) as a runtime-owned artifact distinct from projection. It is extra large because every downstream emitter (W8.B-F) binds into it. It is critical because projection truthfulness now means "preserves graph truth" rather than "renders fields from whatever was in W4.E".

#### W8.B Argument/Warrant Graph Builder - L, Critical

This phase extends `assurance_case.py` SACM/CAE/GSN baseline into a runtime-emitted argument/warrant graph (claim → argument → warrant with typed assumptions/applicability/BERL refs → evidence → authority → readiness). It is large but bounded because the formal substrate already exists; the work is to bind it to the new PDC graph rather than to rebuild SACM. It is critical because external legitimacy without inspectable warrants is performative.

#### W8.C Baseline + Alternative Comparison Compiler - L, High

This phase implements C10 fully: superiority claims now require records for no-action, status-quo, business-as-usual, named alternatives, and (where operationally meaningful) fragility/scenario baselines. Rejected alternatives carry typed reasons. It is large because comparison evidence touches Foundry method outputs, IR causal analytics, Scholar evidence, and Fabric data. It is high criticality because policy memos that show only the chosen option are the canonical structural-but-semantically-wrong artifact.

#### W8.D Pareto Frontier + Social-Weight Provenance Emitter - L, High

This phase emits Pareto frontier records, value-choice decision points, and social-weight provenance (who chose, mandate, time, affected groups, dissent, review status) over Foundry welfare bounds and social-weight schedules. It is large because welfare crosses Foundry, normative arbitration, and projection. It is high criticality because scalar welfare aggregation that hides social-weight provenance is a known authority-laundering path.

#### W8.E Conflict-To-Portfolio Materializer - L, High

This phase makes conflict a first-class record in claim registry and portfolio (empirical, methodological, legal, scope, normative, participation, implementation, authority/provenance) with typed resolution routes. It is large because conflict semantics touch ConflictDetector, cross-graph compiler, semantic binding, readiness, and public surfaces. It is high criticality because conflicts hidden in post-hoc detection mean cases close while they are silently broken.

#### W8.F Effective Independence Graph Annotator - L, Critical

This phase implements C29 graded calculus (hard-collapse plus partial-collapse bands) over evidence-line identity (claim ids, strand, polarity, source refs, primary source, retrieval path, legal authority, author/institution/sponsor, dataset/corpus/snapshot/subject pool, preprocessing, transformation lineage, method family, identification strategy, assumptions, proof-reuse status, LLM generation path, simulation DGP, participation sample frame, concept spine, jurisdiction, time roles). It annotates the PDC graph and surfaces `scarcity_structural` versus `scarcity_remediable` paths. It is large because it consumes lineage from every producer family. It is critical because raw count inflation is closeable only when the graph reports effective independent mass.

#### W9 Advanced Lifecycle + Drift Detection + Replay Engine - L, High

This wave closes the contracts-vs-implementations gap that the second-pass code audit found: contracts exist (ReissuePacket, monitor events, schema_compat) but detector code and replay execution are missing. It is large because six related but distinct gaps need closure. It is high criticality because closed PDCs that silently go stale are a P07/P08/P09 trifecta.

#### W9.A Drift Detector Implementations - L, High

This phase implements four detectors (calibration drift, fairness drift, policy-context drift, source-invalidation) on top of existing monitor event types. It is large because each detector needs its own signal definition, sparse-history policy, and lifecycle event emission. It is high criticality because drift contracts exist but produce no events today.

#### W9.B Partial-Scope Reissue Mechanics - M, High

This phase extends `ReissuePacket` with `scope_to_revise: list[claim_id]`, unchanged-records refs, superseded refs, public-diff refs, and partial-publication state. It is medium because the work mostly extends an existing typed packet, but high criticality because whole-case rewrites destroy historical replay.

#### W9.C Data Forge Snapshot Provenance Manifest - M, High

This phase adds the durable `(corpus_id, data_hash, creation_time, lineage_refs, quality_gates)` ledger on top of Data Forge snapshot transactions and merkle roots. It is medium because the storage substrate already exists. It is high criticality because closeout cannot prove "this is the official snapshot" without it.

#### W9.D Memory Decay + TTL + Contamination Controls - M, High

This phase adds TTL/decay/contamination policy to reflexive memory (failure_lessons and success patterns from W2.F/W5.D). It is medium because the schemas exist; behaviour is the work. It is high criticality because indefinite memory accumulation slowly biases the entire system toward fear (failures) or overconfidence (successes).

#### W9.E Continuous Governance Event → Claim Lifecycle Bridge - L, High

This phase maps DDM/source/legal/participation/context events into claim lifecycle transitions (stale, blocked, invalidated, superseded, review-required, reissued, withdrawn) using W9.A detectors and W9.B partial-reissue mechanics. It is large because it crosses governance/continuous, claim registry, and public revision state. It is high criticality because C20 lifecycle semantics are how the PDC stays a living object.

#### W9.F Rule Evolution Replay Engine - L, High

This phase implements the actual replay execution (W2.B registered refs and logic hashes; W9.F runs the closed case under the original rule/taxonomy semantics) and the public revalidation triggers from C33 change-class table. It is large because replay touches research-DAG, claim lifecycle, and public revision state. It is high criticality because rule changes that silently re-interpret past PDCs erode replay authority.

#### W10 Temporal/Liveness + Cost Gates + FMEA Depth - L, High

This wave extends formal_invariants beyond finite-state, adds the missing three R14 adversarial probes, completes E18 cost enforcement, and closes the soft-gate/complexity-budget/review-effectiveness loop. It is large because six independent improvements with their own ownership. It is high criticality because each item closes a distinct firewall gap.

#### W10.A Temporal/Liveness Invariant Extensions - L, High

This phase extends the five model-checked invariants in `formal_invariants.py` with bounded-liveness deadline consistency (`eventually X` becomes `X within deadline D, else escalate`) under FT-ADR-05. It is large because the deadline algebra crosses producer pipeline states, retry/lease state, and escalation paths. It is high criticality because finite-state-only invariants miss the most common failure mode in async systems.

#### W10.B Review Effectiveness Measurement Pipeline - M, Medium

This phase measures override rate, time-spent distributions, dissent, no-delta reviews, and separation-of-duty failures over existing VOI escalation/human-review metadata, advisory-only under FT-ADR-06. It is medium because measurement is well-scoped. It is medium criticality because consequences remain advisory until longitudinal data supports gates.

#### W10.C Missing R14 Adversarial Probes - M, High

This phase adds the three probes the second-pass audit found missing: authority spoofing, prompt injection (beyond ambiguous instruction), and participation speculation. It is medium because the existing 10 challenge classes are reusable. It is high criticality because these are exactly the classes that the new W6.E LLM formulator + W7.E participation compiler introduce risk for.

#### W10.D Run-Cost Enforcement Gates - L, High

This phase completes E18 by adding authority-level-blocking gates on top of W2.C cost telemetry (compute-dollar, provider API calls, tokens, embeddings/searches, wall-clock, retry, acquisition). It is large because gates touch closeout, acquisition, local prod-debug, canary matrix, and operator surfaces. It is high criticality because cost-without-enforcement is observability, not governance.

#### W10.E Complexity Budget Governance Pruning - M, High

This phase implements Net-MAV gating of new controls (new control must declare expected decision gain, falsification value, authority gain, auditability gain minus human time/latency/rerun/false-block penalties) and periodic prune review using existing telemetry. It is medium because the formula is bounded. It is high criticality because without it, the W6-W11 controls themselves risk becoming ceremony (P13 self-application).

#### W10.F Repair-Decision FMEA Annotation - M, Medium

This phase extends `prompt_tool_ledger` repair decisions with FMEA refs (failure mode, severity, cause, recommended mitigation, residual risk) so prompt/tool repair decisions surface as machinery failures rather than disappear into producer status. It is medium because the ledger is the natural home. It is medium criticality because it is most useful as audit/operator surface, not as a gating layer.

#### W11 Universal Outcome Corpus + Truthfulness Tools - L, Critical

This wave builds the real-policy outcome corpus and the three new metric tools (compilation truthfulness, domain coverage breadth, critic ensemble diversity) that Wave 12 needs. It is large because corpus build is methodological work (sourcing, decomposition, expert adjudication). It is critical because Wave 12 cannot make a universal-capability claim without this corpus.

#### W11.A Universal Outcome Corpus Sourcing - L, Critical

This phase sources at least 12 real policy cases across at least 6 domains (e.g., MSME credit, health intervention, housing subsidy, education access, climate adaptation, migration assistance) and 3 authority levels (research, governed, production). It is large because corpus sourcing requires domain access, IP/redaction discipline, and reviewer coordination. It is critical because synthetic fixtures cannot prove universality.

#### W11.B Claim/Evidence Decomposition Annotations - L, High

This phase produces structured annotations per case (claims, evidence refs, method refs, legal refs, participation refs, risks, tradeoffs, admissibility labels, limitations, contestability status) using the annotation protocol from the research plan. It is large because each case needs reviewer time. It is high criticality because Wave 12 audits compare compiler output against annotations.

#### W11.C Expert Adjudication Labels - L, Critical

This phase produces semantic adjudication labels (semantic_pass, limitation_required, contested, unsupported, false_pass, fabricated_unverifiable, reviewer_disagreement) per case and per claim using the C30 rubric. It is large because expert reviewers from multiple disciplines are required. It is critical because expert disagreement that goes unrecorded becomes silent monoculture.

#### W11.D Fixture Generation + Corpus Loaders + Rotating Fixtures - M, High

This phase produces machine-loadable fixtures, rotation policy (public/hidden/rotating splits) and corpus loaders so the universal outcome corpus is runnable from CI. It is medium because the tooling is bounded. It is high criticality because corpus stays useful only when consumable.

#### W11.E Compilation Truthfulness Audit Tool - M, Critical

This phase delivers `tools/quality/validation/check_compilation_truthfulness.py` that compares each compiled `ObligationGraph` and `ClaimFamilyAssignment` against the W11.B annotations and reports per-case truthfulness scores (true-positive obligations, missed obligations, hallucinated obligations, scope drift, authority drift). It is medium because it consumes existing artifacts. It is critical because compilation truthfulness is the new metric that separates ceremonial honesty from real universal capability.

#### W11.F Domain Coverage Breadth + Critic Ensemble Diversity Tools - M, Medium

This phase delivers two more measurement tools: domain coverage breadth (does the system actually produce non-trivial graphs in every committed domain?) and critic ensemble diversity (are the eight critics catching different failure modes, or collapsing into one persona?). It is medium because both consume existing artifacts. It is medium criticality because they refine the rollout decision but do not themselves block.

#### W12 Validation And Rollout Decision - XL, Critical

This phase replaces the original Wave 6. It proves or honestly blocks the production path by re-running the local validation ladder over the real compiled PDC, running the full universal outcome corpus, executing the cloud one-lane revalidation, and reporting all three outcome metrics (closeout honesty + useful design + compilation truthfulness) separately. It ranges to extra large because the ladder grows by the universal outcome corpus and the three-metric reporting. It is critical because it decides whether PolicyOS is production-capable, governed-only, research-only, or held for next-plan remediation.

## Real Policy Corpus And Baseline Track

Synthetic fixtures prove mechanics; they do not prove universality. The
implementation must maintain a real-policy corpus track alongside code work.

| Corpus deliverable | Latest wave | Minimum content | Purpose |
| --- | --- | --- | --- |
| Baseline smoke set | Wave 1 | 3-5 real policy requests from different domains | Measure current system behavior before implementation claims progress. |
| Deep pilot set | Wave 2 | 10 real cases, claim/evidence decomposition, reviewer notes | Drive semantic fixtures and walking skeleton edge cases. |
| Producer adapter set | Wave 3 | 12 cases covering legal, data, method, scholar, and participation needs | Prevent adapters from passing only golden/toy cases. |
| Semantic benchmark set | Wave 5 | 30-50 claim-evidence pairs with expert adjudication labels | Detect structural false pass and laundering. |
| Universal compilation kernel fixture set | Wave 6 | 3 diverse policy intents (different domains) with expected facets, obligation graphs, claim decompositions | Prove the universal compiler emits non-trivial typed outputs for diverse domains without producer adapter calls. |
| Producer pipeline + RequirementSpec fixture set | Wave 7 | 5-8 fixtures covering all five producer families with compiled RequirementSpecs and expected selected/rejected/blocked bindings | Prove the staged pipeline drives refactored adapters under compiled requirements. |
| Compiled PDC graph fixture set | Wave 8 | 3-5 fixtures with expected `RuntimePolicyDesignCase` graphs, argument graphs, baselines, frontiers, conflict records, effective-independence graphs | Prove graph compilation is distinct from projection and binds all W8 emitters. |
| Lifecycle/drift/replay fixture set | Wave 9 | 4-6 fixtures covering each detector family + partial reissue + rule replay scenarios | Prove the contracts-vs-implementations gap is closed. |
| Invariant/cost/probe fixture set | Wave 10 | Per-phase smoke fixtures for liveness, cost gate, three R14 probes, complexity governance, repair FMEA | Prove every W10 firewall fires on its synthetic target. |
| Universal outcome corpus | Wave 11 | At least 12 real cases across at least 6 domains and 3 authority levels, with claim/evidence decomposition annotations and expert adjudication labels | Decide whether the universal PDC path exists beyond process hygiene; this is the canonical evidence for the universal-capability claim. |
| Rolling outcome corpus snapshots | Wave 12 | Re-runs of Wave 11 corpus under frozen revision/config plus cloud one-lane | Capture release-time outcome metrics for rollout decision. |

The corpus must preserve:

- domain, jurisdiction, authority level, policy instrument, population, time
  scope, and expected evidence families;
- expert adjudication where available;
- known failure/limitation labels;
- raw source refs or redacted source hashes;
- fixture generation scripts or transformation notes.

Outcome metrics are separate from plan hygiene. The plan must never collapse
honesty into capability. A system that returns 100% typed blockers may be
truthful, but it has not achieved universal policy-design capability.

| Metric | Meaning |
| --- | --- |
| Closeout honesty rate | Real cases whose outcome is pass, publish-with-limitation, accepted deficit, or typed blocker without authority laundering. This is the safety floor. |
| runtime_useful_design_rate | W12.D runtime cases producing pass or publish-with-limitation. This is the actual capability floor. Typed blockers and accepted deficits do not count. |
| expert_useful_design_ceiling | W11.F expert-adjudicated ceiling: cases experts say should be achievable as useful design on this corpus. This measures corpus adequacy, not runtime output. |
| useful_design_alignment_rate | W12.D runtime useful-design count divided by expert useful-design ceiling count over the same case set. This measures how much of the expert-achievable ceiling the runtime captured. |
| Compilation truthfulness rate | Per-case W11.E score: weighted aggregate of true_positive_obligations, missed_obligations, hallucinated_obligations, scope_drift_obligations, authority_drift_obligations against W11.B annotations and W11.C adjudication. Required from Wave 11 onward. |
| Domain useful coverage | Each committed domain slice has at least one useful design outcome, unless the rollout decision explicitly marks that domain research-only or held. |
| Domain coverage breadth (W11.F) | Number of committed domains where W6.C produces a non-trivial obligation graph. Required from Wave 11 onward. |
| Critic ensemble diversity (W11.F) | Per-case Jaccard of unique failure-modes flagged by each of the eight critics; warns when the ensemble collapses into a single persona. Required from Wave 11 onward. |
| per_authority_expert_useful_design_ceiling (W11.F) | Expert ceiling stratified by research / governed / production authority level. Runtime per-authority useful design is reported by W12.D. |
| Blocker/deficit rate | Real cases ending in accepted deficit or typed blocker. This is useful diagnostic evidence, but it counts against capability. |
| Semantic false-pass rate | Cases where structural pass disagrees with expert semantic adjudication. |
| Bridge-complete rate | Claims with producer, bridge, consumer, surface, and semantic test present. |
| Projection truth rate | External surfaces preserve blocked/limited/contested/omitted states. |
| Reuse-first rate | Capabilities implemented through wire/extend/consolidate rather than build-new. |
| Median capability debt | Authority-weighted open capability labels per case. |

**Capability achieved** requires corpus evidence and a useful-design floor.
**Plan executed** can end with typed blockers, but that is a rollout hold, not
proof that the universal system exists.

Initial useful-design floors are provisional governed config, but they cannot
be zero:

| Rollout posture | Minimum runtime useful-design expectation | Minimum expert ceiling / alignment expectation | Minimum compilation truthfulness expectation | Minimum domain breadth / critic diversity |
| --- | --- | --- | --- | --- |
| Research-only | No runtime useful-design floor; typed blockers are acceptable if they are specific and actionable. | No minimum; low ceiling means corpus inadequacy, not system failure. | No minimum (kernel may emit nothing). | No minimum. |
| Governed pilot | At least one runtime useful design outcome in every committed domain slice and at least 50% `runtime_useful_design_rate` over the universal outcome set. | `expert_useful_design_ceiling` must be non-zero and `useful_design_alignment_rate` must be at least 50%. | At least 60% compilation truthfulness rate aggregate; no committed domain below 50%. | At least 4 committed domains with non-trivial obligation graph; critic ensemble diversity Jaccard above governed floor. |
| Production-capable | At least one runtime useful design outcome in every committed domain slice, at least 70% `runtime_useful_design_rate` overall, and no domain slice below 40% unless explicitly held out of production scope. | `expert_useful_design_ceiling` must be high enough for the committed scope and `useful_design_alignment_rate` must be at least 70%. | At least 80% compilation truthfulness rate aggregate; no committed domain below 70%. | At least 6 committed domains with non-trivial obligation graph; critic ensemble diversity Jaccard above governed floor on every committed domain. |

These percentages are provisional tuned parameters. The structural commitments are:

- useful-design capability is measured separately from closeout honesty, and typed blockers cannot satisfy the capability floor;
- compilation truthfulness is measured separately from useful design, so a case that passes structurally with hallucinated or scope-shifted obligations cannot pretend to be capable;
- domain coverage breadth and critic ensemble diversity are reported per domain and per authority level, so a high aggregate metric cannot mask a collapsed domain or a monoculture critic ensemble.

## Program Risk Register

The implementation must maintain a live risk register. At minimum it starts
with these risks:

| Risk | Likelihood | Impact | Owner | Mitigation / trigger |
| --- | --- | --- | --- | --- |
| Integration remains back-loaded | High | High | integration spine | I1-I12 required; no wave may exit without its required integration slice. |
| Wave 3 adapter overrun | High | High | producer adapter lead | XL sizing, mid-wave checkpoint, minimum adapter path before breadth. |
| Corpus stays synthetic | Medium | High | evaluation lead | Corpus deliverables gate Wave 3, Wave 5, Wave 11, and outcome claims. |
| Honesty hides lack of capability | Medium | High | program owner | Track useful-design rate separately from closeout honesty; from Wave 11 onward also track compilation truthfulness rate; typed blockers do not count as capability. |
| Closeout substrate too brittle | Medium | High | closeout owner | Walking skeleton, typed holds, staged strictness, defect examples. |
| Concept spine cannot reconcile producers | Medium | High | semantic spine owner | I2 and I3 focus on Lex/Fabric/Foundry alignment early; Wave 6 universal grammar reuses spine refs rather than inventing concepts. |
| Thresholds hardcoded too early | Medium | High | governance operations | Tuned-config policy, feature flags, ADR structural/tuned split. |
| Cross-plan file contention | Medium | Medium | release manager | Cross-plan write ledger and wave-start ownership review. |
| External surface drifts from runtime truth | Medium | High | external surface lead | Consumer contract and semantic projection tests; from Wave 8, projection consumer contracts verify projection-from-W8.A-graph. |
| Complexity budget becomes ceremonial | Medium | Medium | self-FMEA owner | Telemetry-derived only; must trigger prune/merge decisions; W10.E complexity governance is itself on the retire list if it stops causing prune decisions. |
| Team capacity makes parallelism fictional | High if under-staffed | High | program owner | Critical path schedule replaces parallel assumption when workstreams are unavailable. |
| Universal compilation kernel inflates ceremony | Medium | High | integration spine + governance operations | Wave 10.E complexity governance gates new W6-W11 controls by Net-MAV; each new compiler/detector/tool must declare expected decision gain and is subject to retirement if it stops affecting decisions. |
| Requirement compilers accidentally recreate domain templates | Medium | High | producer adapter lead | RequirementSpec compilers must derive admissibility from compiled facets + governed rules, never from hardcoded family lists; W7 negative tests assert this; W11.B annotations cross-check against compiler output. |
| LLM formulator / critic ensemble collapses into monoculture | Medium | High | LLM formulation and critics workstream | Eight critics carry substantively different bases (deterministic rule, statistical pattern, historical failure, legal probe, simulation probe, participation provenance check, adversarial generator, monitoring drift simulator) — not just different personas; W11.F critic diversity tool measures and W12 gates on it. |
| Universal outcome corpus delayed | Medium | High | evaluation lead | Corpus build runs as informal track from Wave 5 exit; formalises in Wave 11; W12 gates on corpus completeness with named hold otherwise. |
| Three-metric reporting itself becomes ceremonial | Low | Medium | evaluation lead | Each metric must trigger a documented decision (pause / proceed / adjust posture / retire) at every wave exit; metric that has not changed a decision after two windows is reviewed for retirement. |
| Hypothesis ledger firewall has no real input | Medium | High | LLM formulation and critics workstream | W6.E formulator + critic ensemble produces structured candidates as W6.F firewall input; W10.C participation_speculation probe verifies the firewall has work to do. |
| Drift detectors block on sparse history | Medium | Medium | governance operations | W9.A detectors respect sparse-history bands; blocking consequences only after `Forming` or `Mature adverse` thresholds. |
| Rule replay engine cannot reproduce closed PDC | Medium | High | rule replay owner | W9.F includes negative test that closed PDC under original rules reproduces exact semantic outputs; failure triggers immediate replay-engine remediation, not silent acceptance. |
| Compilation truthfulness floor set too high too early | Medium | Medium | governance operations | Initial floor is provisional governed default; first three corpus windows inform calibration; floor never enters blocking before W11 corpus is mature. |
| W6.A regression guard removed prematurely | Medium | High | integration spine | Sunset of the MSME scenario-family hardcode is recorded in `architecture/shims.toml` with a named replacement (compiled-requirement assertion in W7.A negative test); removal cannot happen before W7 exit. |

Risk entries must include status, next review date, trigger, and closure
condition in the wave transition manifest.

## Wave 0 - Decision ADRs And Source Ownership

**Purpose:** remove conceptual ambiguity before code starts to harden it.

**Entry gate:** research synthesis exists, raw research ledger is available
under repo-owned path, and this implementation plan is active.

**Parallel phases:**

#### W0.A FT-ADR-01 Acquisition

This phase is ratified by
[ADR-0166 Evidence Acquisition Decision Boundaries](../../adr/0166-evidence-acquisition-decision-boundaries.md).
It commits that eligibility precedes ranking, mandatory gates dominate VOI,
and `accepted_deficit`, `publish_with_limitation`, and `closeout_block` are
distinct terminal states. It also defines when governed or production authority
requires human/governed commit rather than automatic strategy selection.

This phase blocks E17 and acquisition paths in E10/E16 until accepted. The ADR
must name the eligible strategy matrix, decision owner, tuned parameters, and
negative test showing VOI cannot rank around a non-overridable blocker.

#### W0.B FT-ADR-02 Participation

This phase is ratified by
[ADR-0167 Participation Legitimacy Matrix](../../adr/0167-participation-legitimacy-matrix.md).

This phase ratifies the participation legitimacy matrix. It commits the
`claim_use x authority_level x population_scope` structure, the fail-safe
downgrade posture, and the distinction between prevalence, existence,
qualitative, role-feasibility, dissent, and context-only claims.

This phase blocks participation surfaces in E4/E5, E11, and E22 until accepted.
The ADR must keep representativeness thresholds as governed tuned parameters
and must include a negative laundering test where thin consultation cannot
support affected-population prevalence.

#### W0.C FT-ADR-03 Contestability And Recourse

This phase is ratified by
[ADR-0170 Contestability And Recourse Boundaries](../../adr/0170-contestability-and-recourse-boundaries.md).
It ratifies the boundary between PolicyOS-owned contestability records and
deployment-owned recourse processes. PolicyOS owns contested records, public
visibility, reopening triggers, `recourse_pointer`, and recourse-outcome
ingestion. PolicyOS does not claim to own universal appeal intake,
adjudication, or SLA authority.

This phase blocks C39b-dependent parts of E4/E5 and lifecycle ingestion in E15.
The ADR must define what a verified-reachable recourse pointer means and must
include a negative test where high-stakes contested production publication
fails when that pointer is absent or unreachable.

#### W0.D FT-ADR-04 Legal Competence

This phase is ratified by
[ADR-0168 Legal Hierarchy And Competence Boundaries](../../adr/0168-legal-hierarchy-and-competence.md).
It commits that jurisdiction fallback is governed per-jurisdiction config, that
a single norm may carry multiple authority types, and that competence changes
split claims by legal window.

This phase blocks E9. The ADR must name how Lex distinguishes generic
jurisdiction/topic matches from serious legal authority and how competence,
time, instrument, implementation, and fiscal authority are represented.

#### W0.E FT-ADR-05 Bounded Liveness

This phase is ratified by
[ADR-0169 Bounded Liveness And Runtime Escalation](../../adr/0169-bounded-liveness-and-runtime-escalation.md).
It commits bounded liveness semantics by turning `eventually X` into
`X within deadline D, else escalate`, so liveness can be checked with
finite-state deadline consistency and runtime escalation rather than an
unbounded temporal proof.

This phase unblocks E3, E6, E7, and E19 liveness-sensitive work. The ADR keeps
deadlines and retry ceilings as governed runtime config and the implementation
includes negative coverage where a Scholar producer wait cannot hang
indefinitely.

#### W0.F FT-ADR-06 Review Telemetry

This phase is ratified by
[ADR-0171 Review Effectiveness Telemetry Advisory First](../../adr/0171-review-effectiveness-telemetry-advisory-first.md).
It ratifies advisory-first review-effectiveness telemetry. It defines review
time, override rate, dissent, no-delta reviews, and separation-of-duty failures
as measured signals, while deferring blocking consequences until longitudinal
evidence supports them.

This phase blocks E19 review-effectiveness consequences. The ADR must specify
that early telemetry is advisory and must include a negative test where review
telemetry cannot block without a mature governed policy.

#### W0.G Source Ownership

This phase makes the research source chain repo-owned. The raw research ledger,
normalized synthesis, research plan, implementation plan, ADRs, and docs index
must point to repository paths rather than local Downloads paths or ephemeral
workspace notes.

This phase supports every later wave. Its deliverable is not just a copied
file; it is durable source traceability from raw research to synthesis to C/E/P
ids and implementation gates.

Delivered source-ownership surface:
`docs/reference/policy-design-case-source-ownership.md`. That page is the W0.G
bridge from raw ledger to normalized synthesis, research plan, implementation
plan, failure-pattern register, ADR index, docs index, and I0 source
traceability. Its regression coverage is
`tests/repo_quality/tools/test_policy_design_case_source_ownership.py`.

Pattern pass: W0.G closes the immediate `surface_missing` and
`verification_missing` risk for P06 source ownership. It does not claim runtime
PDC capabilities are implemented; later waves still need their own producer,
consumer, surface, and semantic-test proofs.

#### W0.H Structural ADR Registry

This phase creates a registry that maps every structural decision in C0-C41 to
an existing ADR, a fast-track ADR, a new ADR to write, or an explicit
`no_adr_required` rationale. Its job is to prevent architectural decisions from
being silently baked into implementation tables.

This phase blocks structural implementation that cannot cite a decision source.
It should also identify decisions that are implementation-local, tuned-config
only, deployment-owned, or still blocked by research/empirical evidence.

Delivered structural ADR registry surface:
`docs/reference/policy-design-case-structural-adr-registry.md`. That page is
the W0.H bridge from C0-C41 research decisions to accepted ADRs, Wave 0
fast-track ADRs, named future ADR blockers, or explicit `no_adr_required`
rationales. Its regression coverage is
`tests/repo_quality/tools/test_policy_design_case_structural_adr_registry.py`.

Pattern pass: W0.H closes the immediate `contract_only`,
`surface_missing`, and `verification_missing` risk for structural decision
traceability. It prevents P05/P15 authority commitments from entering
implementation tables without an ADR source, and it keeps tuned-config,
deployment-owned, and empirical-threshold decisions out of structural
contracts until their evidence exists.

**ADR minimum template:**

- `Context`
- `Decision`
- `Structural commitment`
- `Tuned parameter`
- `Authority boundary`
- `Negative laundering test`
- `Feature flag/advisory posture`
- `Revision path`
- `Affected E tasks`
- `Validation`

**Structural commitments:**

- ADRs define schema/ownership/transition boundaries, not just prose intent.
- ADRs identify the exact authority the resulting artifact can and cannot
  carry.
- ADRs name consumer-side enforcement, not only producer-side shape.

**Tuned parameters:**

- VOI weights, participation thresholds, jurisdiction fallback tables,
  liveness deadlines, review-effectiveness cutoffs, and appeal SLAs remain
  governed defaults or deployment config.
- No tuned value may ship as final unless the ADR cites corpus/calibration
  evidence and an owner.

**Negative tests:**

- acquisition planner cannot rank around a mandatory gate;
- participation prevalence cannot be inferred from thin consultation;
- missing or unreachable `recourse_pointer` blocks high-stakes contested
  production publication;
- generic jurisdiction match cannot satisfy legal competence;
- liveness wait cannot hang indefinitely;
- review telemetry cannot block without mature policy.

**Exit gate:**

- six ADRs exist under `docs/system-design-decisions/` or another canonical ADR
  location;
- structural ADR registry exists and names which C0-C41 decisions are already
  ratified, fast-tracked, implementation-local, or still blocked;
- each ADR contains all template sections;
- gated tasks identify the ADR id they rely on;
- raw research source is repo-owned and linked from synthesis/research plan;
- W0.G source ownership is published in
  `docs/reference/policy-design-case-source-ownership.md` and indexed from the
  docs reference surface;
- docs gates pass.

**Validation:**

```bash
uv run pytest tests/repo_quality/tools/test_docs_lifecycle.py tests/repo_quality/tools/test_docs_gate.py -q
```

## Wave 1 - Runtime Quality Foundation

**Purpose:** provide the shared quality language all later producers and
readers will use.

**Entry gate:** Wave 0 complete.

**Parallel phases:**

#### W1.A Capability Ratchet

This phase implements E0 and C36 against P01-P03, P10, and P13. Its write
surface is the production-quality validation tooling, reference docs, and
capability reporting outputs. The deliverable is a capability reality report
with debt points, purpose multipliers, readiness bands, and ratchet templates.

The phase should make incomplete capability states visible rather than
embarrassing. A path can be `contract_only`, `bridge_missing`, or
`semantic_test_missing` and still be useful evidence, as long as it is not
called implemented. The output becomes the release/readiness vocabulary for all
later work.

#### W1.B Semantic Fixtures

This phase implements E1 and C30 against P10 and P15. Its write surface is the
production-quality fixture area, repo-quality tests, and a dedicated semantic
fixture path if cross-producer behavior needs one. The deliverable is the first
gold-card schema plus false-pass fixtures for projection laundering,
participation laundering, raw-count inflation, method mismatch, stale legal or
data evidence, and LLM speculation.

The phase must prove that structural completeness can still fail. It should
prefer a small number of sharp, explainable cases over a broad fixture pile
that only checks field presence.

#### W1.C Status And Deficits

This phase implements E2, C1, and C31 against P04 and P09. Its write surface is
runtime quality status, scorecard, and deficit behavior plus unit tests around
mixed statuses. The deliverable is a status envelope and deficit crosswalk that
preserves local producer statuses while adding shared severity, blockingness,
owner, TTL, publication effect, review action, and closeout effect.

The phase must keep `accepted_deficit`, `publish_with_limitation`, review,
reissue, and hard block distinct. It should not collapse them into pass/fail or
invent a new universal enum that erases local meaning.

#### W1.D Closeout Reader Skeleton

This phase implements the first E3/C3 closeout substrate surface while guarding
against P01, P05, and P10. Its write surface is the closeout runtime quality
module and `check_can_i_closeout.py`. The deliverable is a separate closeout
reader interface with stubbed module readers, authority-only-for-closeout
envelope semantics, and negative tests for projection-only authority.

The skeleton is intentionally incomplete but must already fail closed. It may
read stubs, but it cannot let readiness, dashboard projection, packaging, or
public export substitute for closeout evidence.

#### W1.E Documentation Paths

This phase implements E23 against P03, P06, and P13. Its write surface is
runbooks, reference docs, active plans, and command-evidence conventions. The
deliverable is a canonical set of evidence paths for raw sources, synthesis,
ADRs, validation commands, and closeout notes.

This is a small phase, but it is the repository ownership lock. It keeps the
program from depending on local files, hidden notebooks, or social memory.

W1.E publishes the canonical path ledger at
`docs/reference/policy-design-case-evidence-paths.md`. That ledger is the
durable route for raw source paths, synthesis paths, ADR authority paths,
validation-command references, transient command-output conventions, and phase
closeout note placement. The operator triage runbook links to it so serious
closeout incidents can cite repo-owned evidence instead of terminal history.

**Parallelism contract:** W1 phases may share conceptual language from Wave 0
but may not consume sibling implementations. W1.D can define reader stubs but
must not require W1.C runtime implementation until Wave 2.

**Capability closures:**

- W1.A closes `contract_only` for capability maturity reporting.
- W1.B closes `semantic_test_missing` for future PDC features.
- W1.C closes `status_enum_proliferation` risk through crosswalk tests.
- W1.D closes `projection_only_closeout` risk by making closeout a separate
  runtime reader.
- W1.E closes P06 documentation-path drift for raw sources, ADRs, validation
  command evidence, and closeout notes.

**Negative tests:**

- a typed artifact with no producer remains `contract_only`;
- a structural PDC with unsupported claim fails semantic fixture;
- a warning without owner/TTL cannot be silently ignored;
- dashboard/public/export projection cannot satisfy closeout;
- `accepted_deficit`, `publish_with_limitation`, and `hard_blocking` stay
  distinct.
- a documentation path contract that lacks raw source, synthesis, ADR,
  validation-command, or closeout-note paths is rejected.

**Exit gate:**

- every Wave 1 capability claim has a capability reality state, and any open
  label has an owner, hold reason, and next wave target;
- baseline smoke corpus behavior is recorded for the pre-implementation path;
- semantic fixtures can fail a structural pass;
- status/deficit crosswalk has mixed-status tests;
- closeout reader can emit a typed incomplete verdict without minting domain
  authority;
- W1.E evidence paths are indexed from reference docs, docs inventory, MkDocs
  nav, the source-ownership ledger, and the PDC operator runbook;
- I1 closeout skeleton smoke passes or emits a typed blocker;
- docs gates pass.

**Validation:**

```bash
uv run pytest tests/unit/runtime/quality -q
uv run pytest tests/repo_quality/tools/test_docs_lifecycle.py tests/repo_quality/tools/test_docs_gate.py -q
uv run pytest tests/repo_quality/tools/test_policy_design_case_documentation_paths.py -q
```

## Wave 2 - Shared Carriers, Registries, And Telemetry

**Purpose:** create reusable runtime surfaces that later producer adapters can
target without direct peer dependencies.

**Entry gate:** Wave 1 exit artifacts accepted.

**Parallel phases:**

#### W2.A Concept Spine And Handshake Kernel

This phase implements E6, C28, C37, and C40 while guarding against P02, P08,
and P12. Its write surface is the runtime quality concept spine, evidence
spine, producer-spine helpers, and handshake record models. The deliverable is
a hybrid concept-spine carrier with governed namespace refs, per-run
reconciled concepts, producer handshake records, boundary-scoped bridge
authority, context-only labels, and unresolved/conflicting concept blockers.

The phase must treat concept spine as shared semantic infrastructure, not as a
post-hoc reconciliation report. It is the substrate that lets Lex, Fabric,
Scholar, Foundry, Data Forge, and Scientist talk about the same claim scope
without silently substituting meanings.

#### W2.B Rule Evolution Registry

This phase implements E14, C21, and C33 while guarding against P06-P08. Its
write surface is a runtime quality rule-evolution module and replay helpers.
The deliverable is a registry of rule/taxonomy refs, logic hashes, alias remap
rules, semantic-change detection, old-logic replay behavior, public
annotation, and revalidation state.

The phase must distinguish lossless schema migration from semantic rule change.
If a requirement id changes but the logic hash changes too, the system treats
that as a new requirement or semantic tightening, not a silent compatible
rename.

#### W2.C Cost And Degradation Primitives

This phase implements E18 and C23 against P09 and P13. Its write surface is
runtime quality budget modules and local production-debug outputs. The
deliverable is governed telemetry for provider calls, tokens, search, compute,
retry, wall-clock, acquisition, and degradation states.

The phase is telemetry-first. It should expose cost and degradation without
prematurely creating blockers unless the authority-level policy already
requires them. This keeps cost governance useful without turning budget
observability into ceremony.

#### W2.D Self-FMEA And Soft-Gate Telemetry

This phase implements E19, C24, and C32 while guarding against P04, P09, and
P13. Its write surface is runtime quality FMEA-like modules, prompt/tool ledger
integration, warning lifecycle fields, and bounded-liveness hooks. The
deliverable is soft-gate owner/TTL tracking, bounded-liveness hooks,
repair-decision FMEA annotation, advisory review telemetry, and
complexity-budget telemetry reads.

The phase must keep complexity measurement derived from existing telemetry
rather than adding human forms about ceremony. It also ensures warnings age,
escalate, or expire under named ownership.

#### W2.E Calibration Ledger Schema

This phase implements E20, C25, C35, and C41 while guarding against P07, P10,
and P15. Its write surface is calibration and runtime-quality modules. The
deliverable is a longitudinal calibration ledger schema with sparse-history
policy and an explicit boundary that historical calibration influences future
routing, review, and authority caps but never current-run evidence closure.

The phase must make sparse history non-blocking and transparent. Mature
blocking thresholds remain governed config until real longitudinal data exists.

#### W2.F Balanced Memory Schema

This phase implements E21, C25, and C41 while guarding against P11 and P15. Its
write surface is Scientist orchestration memory and runtime quality influence
records. The deliverable is a success/failure/opportunity memory schema with
scope, expiry, revocation, contamination controls, and influence-record
boundaries.

The phase must correct failure-only memory without laundering prior cases into
current evidence. Success memories can guide search and review, but they cannot
close or refute a claim.

**Parallelism contract:** every phase publishes a stable artifact or schema for
Wave 3. No Wave 2 phase consumes another Wave 2 implementation.

**Capability closures:**

- W2.A closes `bridge_missing` for producer-spine boundaries.
- W2.B closes semantic replay risk for future PDC closure.
- W2.C closes cost/degradation observability gaps without creating blockers.
- W2.D closes soft-gate owner/TTL gaps and creates machinery telemetry.
- W2.E/W2.F close historical-prior laundering through typed influence records.

**Negative tests:**

- bridge/handoff without envelope is diagnostic only;
- requirement id remap with changed logic hash is not compatible migration;
- historical prior cannot enter claim evidence slots;
- cost telemetry cannot silently downgrade evidence quality;
- review-effectiveness telemetry cannot block before ADR-governed maturity.

**Exit gate:**

- concept spine and handoff records validate redaction and boundary authority;
- rule evolution registry can distinguish alias remap from semantic change;
- cost/degradation telemetry is observable but not silently blocking;
- review telemetry is advisory only;
- historical priors cannot enter claim-evidence slots.
- I2 walking skeleton passes end-to-end or produces a typed architecture
  blocker before Wave 3 broad adapter work proceeds.

**Validation:**

```bash
uv run pytest tests/unit/runtime/quality -q
uv run pytest tests/unit/scientist/orchestration -q
```

## Wave 3 - Producer Adapters And Claim-Bound Evidence

**Purpose:** make each producer emit selected, rejected, blocked, limited, or
context-only evidence into claim-bound runtime surfaces.

**Entry gate:** Wave 2 carriers, registries, and telemetry surfaces accepted.
I2 walking skeleton must be passing or blocked with an accepted architecture
decision before broad producer adapter work starts.

**Parallel phases:**

#### W3.A IR Analytics Bridge

This phase implements E8 over C9, C10, C13, and C14 while guarding against P02,
P10, and P14. Its write surface is IR analytics integration, runtime claim
registry, and Scientist validation. The deliverable is a bridge that binds IR
certificates, proof statuses, conflicts, uncertainty envelopes, negative
certificates, and proof-composability refs to ClaimRecord entries.

The phase should reuse the existing proof-carrying analytics rather than
rebuilding method logic. Its job is to make those proofs claim-addressable,
reader-visible, and closeout-relevant.

#### W3.B Lex Legal Adapter

This phase implements E9 over C7 and C11 under FT-ADR-04 while guarding against
P01, P05, P08, and P12. Its write surface is Lex normpack evaluation and
runtime legal surfaces. The deliverable is graded legal admissibility,
per-claim selected and rejected norm anchors, jurisdiction-config fallback,
multiple authority types, competence-window splitting, and no-anchor rationale.

The phase must prevent global legal retrieval from masquerading as
recommendation-level authority. A generic Ukrainian or jurisdiction/topic match
can be context, but it cannot satisfy legal competence without the claim-level
facets.

#### W3.C Fabric Data Adapter

This phase implements E10 over C2, C6, C11, and C22 while guarding against P01,
P02, P08, and P14. Its write surface is Fabric source selection, production
data contract index, and source-contract validation. The deliverable is
SourceContract-backed scenario families, OpenLineage-like facets,
selected/rejected/blocked contract bindings, broad-bundle rejection, and
missing-facet findings.

The phase must demote broad context inventory. `datasets` or other generic
bundle labels can help navigation, but only claim-admissible contract bindings
can satisfy source-family obligations.

#### W3.D Scholar Adapter

This phase implements E11 over C13, C14, and C26 under the participation
constraints from FT-ADR-02. Its write surface is Scholar search, source
scoring, spine, and claim-support links. The deliverable is query graph,
source scoring, snippets, freshness, corpus lineage, support/conflict links,
duplicate and polarity markers, dependence records, and participation-like
downgrade preservation.

The phase must distinguish academic support from affected-person preference or
participation legitimacy. It also needs source-family independence signals so
multiple publications from the same underlying study do not inflate support.

#### W3.E Foundry Method Adapter

This phase implements E12 over C9-C11 and C13 while guarding against P01, P10,
and P14. Its write surface is Foundry methods, method validation, and Scientist
workflow builder integration. The deliverable is selected and rejected methods,
runtime assumption gates, method output refs, uncertainty envelopes,
limitations, simulation assumption lineage, and explicit rejection reasons.

The phase must move generic execution out of authority-bearing selected method
slots under serious method obligations. Claims should not depend on method
outputs until the relevant method assumptions and uncertainty surfaces are
recorded.

#### W3.F Data Forge Closeout Binding

This phase implements E16 over C9, C11, C20, and C22 while guarding against
P01, P08, and P10. Its write surface is Data Forge snapshots, release
manifests, read APIs, and runtime quality records. The deliverable is official
snapshot/release/read-API identity, merkle and data hashes, quality gates,
PROV/OpenLineage lineage, and claim requirement bindings.

The phase must prevent file availability from satisfying closeout-grade data
authority. The system needs to know which official snapshot was used, how it
was produced, what quality gates it passed, and which claim requirements it
supports.

#### W3.G Acquisition Planner

This phase implements E17 over C22 under
[ADR-0166](../../adr/0166-evidence-acquisition-decision-boundaries.md) while
guarding against P01, P09, and P10. Its write surface is
VOI/search/acquisition integration and runtime blockers. The deliverable is a
planner using
`gap_type x authority_level x mandatory_gate_state` eligibility, strategy
records, next actions, and distinct deficit, limitation, and block states.

The phase must make ranking subordinate to eligibility and mandatory gates. It
should help the system choose acquire, proxy-with-limitation, accept deficit,
rerun, or block, but it must never rank around a non-overridable blocker.

**Parallelism contract:** adapters consume Wave 2 interfaces only. They must not
wait for sibling adapters. Cross-producer conflicts are emitted as records for
Wave 4, not resolved through direct calls.

**Capability closures:**

- each producer closes one concrete `producer_missing` or `bridge_missing`
  surface;
- every adapter emits at least one authority-bearing path and one typed blocker
  path;
- context-only output is explicitly non-authoritative;
- acquisition produces next actions but never bypasses mandatory gates.

**Negative tests:**

- generic legal jurisdiction/topic match cannot support a major claim;
- generic `datasets` bundle cannot satisfy scenario source family;
- Scholar publication cannot imply affected-person representativeness;
- generic `foundry.execute` cannot satisfy method obligations;
- Data Forge file availability without official snapshot/read surface fails;
- VOI cannot choose proxy around a non-overridable gate;
- detached IR certificate cannot change claim support until bridged.
- lineage/schema/quality facets cannot be replaced by a broad dataset label.

**Exit gate:**

- every producer has passing and laundering/blocked fixtures;
- producer adapter set corpus coverage is recorded for the cases each producer
  claims to support;
- I3 producer adapter mid-wave checkpoint has passed before remaining adapter
  breadth is accepted;
- broad context-only output cannot satisfy claim authority;
- missing producer evidence creates typed blockers, accepted deficits, or
  acquisition next actions;
- all producer reports carry capability reality status and authority envelope.

**Validation:**

```bash
uv run pytest tests/unit/lex tests/unit/fabric tests/unit/foundry tests/unit/scientist -q
uv run pytest tests/unit/runtime/quality -q
```

## Wave 4 - Runtime Orchestration, Portfolio, Closeout, And Projection

**Purpose:** integrate producer outputs into a runtime Policy Design Case graph
without collapsing authority boundaries.

**Entry gate:** Wave 3 producer adapters accepted.
I3 producer adapter checkpoint must have passed with real, not stubbed, producer
outputs.

**Parallel phases:**

#### W4.A NL/Replay Orchestration

This phase implements E7 over C8 and C40 while guarding against P02 and P12.
Its write surface is runtime control services, replay tools, bundle assembly,
inspection, readiness, and export handoff paths. The deliverable is propagation
of request context, workflow state, job progress, replay, bundle, inspection,
readiness, and export through the same producer-handshake and spine continuity
model.

The phase must prove that runtime orchestration carries the carrier, not just
request-local metadata. Replay and inspection should see the same spine,
handoff, claim registry, and producer binding refs that the live path saw.

#### W4.B Portfolio Aggregation

This phase implements E13 and C29 while guarding against P14. Its write surface
is evidence portfolio and synthesis modules. The deliverable is strict
hard-collapse, graded independence behind feature flags, counterevidence
preservation, rare-domain scarcity classification, and effective mass reports.

The phase must make evidence strength truthful. Raw count can be displayed only
beside effective support and collapse reasons. Rare-domain scarcity can produce
limitations or monitored designs, but it cannot inflate independent evidence.

#### W4.C Lifecycle And Partial Reissue

This phase implements E15 over C20, C21, and C33 while guarding against P07-P09.
Its write surface is continuous governance, claim lifecycle, DDM bridges, and
public revision state. The deliverable is a map from DDM, legal, source,
participation, and policy-context events to affected claims, public diffs,
partial reissue, supersede, withdraw, and review-required state.

The phase must avoid whole-case rewrites when only a subset of claims is
affected. It should preserve closed-case historical meaning while making
current validity and public revalidation status explicit.

#### W4.D Closeout Integration

This phase implements the real E3 closeout integration over C3, C24, and C31
while guarding against P01, P04, P05, and P10. Its write surface is the closeout
reader, readiness, scorecard, audit-verifier ingestion, and runtime quality
closeout records. The deliverable is one `can_i_closeout` verdict over
invariants, source truth, attestation, compatibility, semantic closure, claim
registry, PDC records, projection, and complexity.

The phase must de-stub through I4. Local pass flags are not closeout. The
closeout reader can testify only to closeout verdict, and it must preserve
which upstream reader or producer created each blocker, limitation, or accepted
deficit.

#### W4.E Typed PDC Projection Backend

This phase implements E4 over C16, C17, C19, C39a, and C39b while guarding
against P03, P05, and P15. Its write surface is runtime response shapes,
OpenAPI, generated clients, PDC compiler, and consumer contract fixtures. The
deliverable is a typed `PolicyDesignCaseProjection` with projection gaps,
contested records, `recourse_pointer`, deficit register, invariant summary,
non-authority projection semantics, and contract verification fixtures.

The phase must expose truth without minting authority. Public/reviewer/expert
and machine consumers may see different redactions and depth, but they must see
the same closeout truth, blockers, limitations, omissions, and contested state.

**Parallelism contract:** W4 phases consume Wave 3 normalized artifacts. W4.D
may use predeclared stubs only before I4. I4 is the explicit de-stubbing task:
real W4.B/W4.C/W4.E outputs must flow through W4.D before Wave 4 exits.

**Capability closures:**

- global evidence pools become claim-bound refs or non-authoritative context;
- portfolio evidence strength is effective, not raw;
- lifecycle updates can affect only scoped claims;
- closeout is a separate runtime reader;
- projection is typed and visible but not authority-minting.

**Negative tests:**

- claim with global Lex refs but no per-claim legal anchor fails;
- raw count rises while effective support stays flat;
- lifecycle event affects only selected claims, not whole-case rewrite;
- readiness pass cannot override semantic binding failure;
- public projection cannot hide blocked claim or missing record family;
- `recourse_pointer` missing/unreachable blocks high-stakes contested
  production publication.
- OpenAPI shape can be generated while semantic consumer contracts still fail,
  which keeps the surface `verification_missing`.

**Exit gate:**

- runtime can build a PDC graph for a fixture case;
- global evidence pools no longer support claims without claim-bound refs;
- effective support differs from raw count where dependence exists;
- closeout and projection cannot promote failed or projection-only authority;
- generated clients and API consumers pass contract checks against the runtime
  provider shape;
- I4 first real PDC graph passes or produces a typed integration blocker;
- C39a projection is usable while C39b recourse remains deployment-bounded.

**Validation:**

```bash
uv run pytest tests/unit/runtime/quality tests/unit/scientist/validation -q
uv run pytest tests/repo_quality/tools/test_evidence_bundle_inspection.py -q
```

## Wave 5 - External Surfaces, Evaluation, Calibration, And Memory

**Purpose:** make the system observable, contestable, and self-correcting
without letting external surfaces or historical signals mint current evidence.

**Entry gate:** Wave 4 typed PDC graph and closeout substrate accepted.

**Parallel phases:**

#### W5.A Client, Dashboard, Export, And Audit

This phase implements E5 and C39a while guarding against P03, P05, and P10. Its
write surface is generated clients, dashboard validators, public export, and
audit surfaces. The deliverable is a set of PUBLIC, REVIEWER, EXPERT, and
MACHINE surfaces that consume the typed projection and show redactions,
omissions, blockers, limitations, contested records, audit refs, and contract
verification status.

The phase must preserve closeout truth across audience tiers. A dashboard can
summarize, but it cannot convert `None`, missing refs, blocked claims, omitted
fields, or projection gaps into apparent success.

#### W5.B Semantic Evaluation Packs

This phase implements E22 and C30 while guarding against P10, P14, and P15. Its
write surface is semantic fixtures, adversarial packs, and benchmark metadata.
The deliverable is a false-pass evaluation pack covering participation
prevalence negatives, projection laundering, unreachable recourse pointers,
tuned-threshold hardcoding, raw-count inflation, LLM speculation laundering,
and other content-level failures.

The phase must make semantic adequacy reviewable and reproducible. It should
separate public fixtures, hidden fixtures, and rotating fixtures so the system
cannot simply overfit the first benchmark set.

#### W5.C Calibration Behavior

This phase implements E20 over C35 and C41 while guarding against P07, P09, and
P10. Its write surface is calibration ledger consumers, provider quality, and
readiness caps. The deliverable is sparse-history warning/review behavior,
mature-history feature-flagged gates, and explicit calibration influence
records.

The phase must keep calibration as future posture until mature data exists.
Calibration may adjust routing, review intensity, provider/model choice,
uncertainty posture, or authority cap, but it cannot become current-run
evidence.

#### W5.D Balanced Memory Behavior

This phase implements E21 over C25 and C41 while guarding against P11 and P15.
Its write surface is reflexive memory and Research DAG influence records. The
deliverable is success, failure, and opportunity memory retrieval with scope,
TTL, revocation, contamination controls, and no evidence-slot admission.

The phase must prevent both failure-only conservatism and success-story
laundering. Memory should guide future search and review, not close current
claims.

#### W5.E Docs, Runbooks, And ADR Index

This phase implements E23 while guarding against P03, P06, and P13. Its write
surface is runbooks, reference docs, system-design-decision indexes, active
plans, and operator command paths. The deliverable is discoverable operator
guidance for ADRs, public evidence paths, tuned-parameter owners, validation
ladders, capability evidence, and rollout/rollback procedures.

The phase must make the system operable by someone who did not participate in
the research thread. If the evidence path exists only in memory, chat, or a
temporary build directory, it is not operationally durable.

W5.E publishes the durable operator lookup surface at
`docs/reference/policy-design-case-operator-guide.md` and the concrete
promotion/hold/rollback procedure at
`docs/runbooks/policy-design-case-rollout-rollback.md`. These pages are
operator bridges: they route to accepted ADRs, system-design decision logs,
repo-owned evidence paths, capability reports, validation commands, feature
flag/tuned-config owners, and closeout notes. They do not create runtime
authority and cannot substitute for producer evidence, closeout readers,
consumer contract verification, or semantic tests.

**Parallelism contract:** W5.A exposes Wave 4 truth; W5.B tests it. W5.C and
W5.D influence future routing only. They do not feed current-run claim closure
within the same wave.

**Capability closures:**

- external surfaces become inspectable, typed, and truth-preserving;
- semantic benchmark catches content-level failure;
- calibration and memory become influence surfaces, not evidence;
- docs make ownership and evidence paths durable.

**Negative tests:**

- public export omits blocked claim without omission manifest;
- dashboard turns `None` into apparent success;
- machine consumer cannot reconstruct refs/schema versions;
- consumer contract verification passes while semantic omission manifests fail;
- historical prior enters claim evidence slot;
- success memory overgeneralizes outside scope;
- tuned threshold appears as final in output without ADR evidence.

**Exit gate:**

- public/dashboard/API/export surfaces preserve closeout truth;
- semantic benchmark contains the committed public/hidden/rotating fixture
  classes for this wave, with any missing class marked as explicit hold;
- calibration and memory are visible as influence, never evidence;
- external contract verification covers at least one public, reviewer, expert,
  and machine projection fixture;
- I5 external consumer truth check passes or produces a typed surface blocker;
- all ADRs and runbooks are discoverable from repo-owned paths.

**Validation:**

```bash
uv run pytest tests/repo_quality/tools/test_policy_design_case_public_export.py -q
uv run pytest tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py -q
uv run pytest tests/repo_quality/tools/test_policy_design_case_w5e_docs_runbooks.py tests/repo_quality/tools/test_docs_lifecycle.py tests/repo_quality/tools/test_docs_gate.py -q
```

## Wave 6 - Universal Compilation Kernel

**Purpose:** introduce the missing universal-grammar / obligation / claim-decomposition / LLM-formulator / hypothesis-ledger layer so any policy intent can compile into a typed `UniversalPolicyDesignCase` + `ObligationGraph` + `ClaimFamilyAssignment` + `CandidateLedger` without invoking any producer adapter and without scenario-family hardcoding.

**Entry gate:** Wave 5 external surfaces and semantic tests accepted; the existing scenario-family regression in the W6.A local validation ladder is acknowledged as the symptom that motivated this wave; rollout decision for the original Wave 6 is suspended until the new universal compilation path completes Wave 12.

**Wave-level scope:** Wave 6 is producer engineering, not orchestration: every phase ships a typed contract, a producer, a persisted artifact, a consumer for downstream waves, semantic and laundering tests, and a capability reality label. The 8-stage producer pipeline that drives W3 adapters under compiled requirements is owned by Wave 7, not Wave 6.

**Parallel phases:**

#### W6.A Universal Policy Grammar Compiler

This phase implements C4 and L2 over C6, C11, and C28 while guarding against P02, P05, and P15. Its write surface is `src/polisyos/policy_grammar/` (new module with grammar schema, facet derivation, intent normaliser, authority-profile binder) plus extensions to `src/polisyos/core/contracts/runtime.py` to expose the `UniversalPolicyDesignCase` type. The deliverable is a compiler that turns intent + authority profile + concept-spine refs into typed facets (instrument_type, targeting_type, delivery_channel, funding_channel, authority_type, outcome_channel, risk_facet, method_need, population_predicate, geography_predicate, time_predicate) without inventing free-text fields and without duplicating existing IR governance enums.

The phase must reconcile with `ProblemFrame`, `PolicySpec`, `PolicyCandidateSchema`, `ConstraintCritic`, `challenge_factory`, and `temporal_logic` patterns. New facets allowed only when saturation evidence shows existing enums are insufficient. Facet outputs carry concept-spine refs from W2.A so downstream compilers can reuse semantic grounding rather than guess at meanings.

#### W6.B Governed Obligation Rule Catalog

This phase implements C5 against P06, P07, and P15. Its write surface is `src/polisyos/obligation_rules/` (new module with rule schema, initial governed taxonomy, version/owner/scope/authority/evidence-basis fields, deprecation policy, public-revalidation effect) plus integration with W2.B rule evolution registry. The deliverable is a catalog with seed rules mined from temporal logic patterns, deterministic critic outputs, historical-failure corpus, and policy_design `objectives`/`critic`/`adversary` modules.

The phase must distinguish governed rule from LLM rule candidate. LLMs may propose rule candidates; they may not silently become the rulebook. Every rule carries `rule_family`, `rule_version`, `logic_hash`, `owner`, `scope`, `authority_level`, `evidence_basis`, `status` (`proposed`/`governed`/`deprecated`/`withdrawn`), and `public_revalidation_effect`. Rule changes flow through W2.B.

#### W6.C Obligation Graph Compiler With Candidate/Bundle/Frontier Ledger

This phase implements C38 over C4, C5, C12, and C22 while guarding against P02, P13, and P14. Its write surface is `src/polisyos/obligation_graph/` (new module with three-tier ledger, dominance/dedup/lineage-collapse logic, lexicographic promotion engine, deadline/escalation bindings). The deliverable is a compiler that turns facets (W6.A) plus governed rules (W6.B) plus producer/critic/LLM candidate sources into a typed `ObligationGraph` with:

- **Candidate ledger** (unbounded; never blocks; raw source_class on every entry);
- **Bundle ledger** (bounded by family/scope/authority/temporal-window/remedy-path; canonicalised and deduplicated; one active bundle per key);
- **Blocking frontier** (bounded by complexity budget; only authority-allowance-passing, admissibility-passing, current-run-relevance-passing, material-public-risk-passing items make it here).

Lexicographic promotion follows synthesis order (authority allowance → legal/privacy admissibility → current-run evidence relevance → material public risk → VOI / marginal assurance value → cost, degradation, reviewer burden → complexity budget). Deferred/rejected obligations remain visible with reason, owner, time, and reopen trigger.

Source ceilings follow C38 defaults: `governed_rule` → `mandatory` or `authority_level_mandatory`; `legal_requirement` → `authority_level_mandatory` after competence/time/scope proof; `deterministic_critic` → `conditional`; `producer_blocker` → `mandatory` in affected scope; `historical_failure` → `review_required`; `llm_candidate` → `candidate`; `human_reviewer` → `review_required` unless envelope-backed; `public_contestation` → `review_required` unless material and claim-linked.

#### W6.D Claim Decomposition Compiler With Baseline And Alternative Seed Records

This phase implements C9 and C10 (decomposition side) over C2, C7, and C18 while guarding against P02 and P15. Its write surface is `src/polisyos/scientist/policy_design/claim_decomposition.py` (new file alongside existing schema/objectives/critic) plus extensions to `src/polisyos/scientist/evidence/claims/models.py` to carry `ClaimFamilyAssignment`, `BaselineRecord`, and `AlternativeRecord` types. The deliverable is a compiler that turns intent + facets + obligations into typed claim records:

- claim families: preference, lived experience, acceptability, legitimacy, procedural fairness, implementation feasibility, objection/dissent, context-only, plus causal/distributional/welfare/forecast/implementation claim types from IR analytics;
- baseline records: no-action, status quo, business-as-usual, named alternatives, fragility/scenario baselines where operationally meaningful;
- rejected-alternative records with typed reasons (inferior evidence, dominated frontier, legal blocker, implementation infeasibility, value choice, accepted deficit).

Each claim carries facet refs, obligation refs, concept-spine refs, authority-profile refs, and `claim_use` (per C34). Method needs per claim type are emitted as preconditions for W7.C method validity requirement compilation, not as final method choices.

#### W6.E LLM Formulator + Multi-Critic Ensemble Producer

This phase implements C12 (formulator side) over C4, C5, C9, C19, and C26 while guarding against P05, P10, and P15. Its write surface is `src/polisyos/scientist/policy_design/formulator.py` and `critic_ensemble.py` (new files) plus eight critic implementations (legal, fiscal, equity, data, implementation, affected-person, adversarial, monitoring) under `src/polisyos/scientist/policy_design/critics/`. The deliverable is:

- **Formulator producer:** consumes intent + facets + obligations + claim decomposition; emits typed candidate fields/risks/obligations/missing-question prompts/method-needs into the hypothesis ledger (W6.F);
- **Multi-critic ensemble:** each critic carries a substantively different basis (deterministic rule set, statistical pattern, historical-failure corpus, legal corpus probe, simulation probe, participation-provenance check, adversarial scenario generator, monitoring/lifecycle drift simulator) — not just a different LLM persona;
- **Critic-output schema:** typed verdicts (`agree`, `contest`, `add_candidate_obligation`, `flag_missing_evidence`, `flag_speculation`, `flag_scope_drift`) with envelope marking critic role and substantive basis.

The phase enforces that formulator output is never authoritative on its own. Every candidate entering the hypothesis ledger is marked `candidate_unverified` and routed to W6.F firewall before any downstream wave can read it as evidence or authority. Critic ensemble diversity is measured in W11.F.

#### W6.F Hypothesis Ledger + Candidate-To-Authority Firewall

This phase implements C12 (firewall side) and P15 closure over C2, C5, C9, C17, C19, and C41. Its write surface is `src/polisyos/runtime/quality/hypothesis_ledger.py` and `candidate_firewall.py` (new files) plus integration with `prompt_tool_ledger.py`, `authority.py`, `semantic_binding.py`, `projection_semantics.py`, and `public_export.py`. The deliverable is:

- **Hypothesis ledger:** append-only persistence of every formulator/critic candidate with provenance, source class (`llm_candidate` / `llm_critic` / `llm_critic_consensus` / `llm_drafter` / `deterministic_producer` / `historical_failure` / `human_reviewer` / `public_contestation`), prompt fingerprint, tool refs, repair-decision lineage, authority envelope, admission state (`candidate_unverified` / `rejected_speculation` / `typed_blocker` / `limitation` / `admitted_to_obligation` / `admitted_to_claim`);
- **Firewall enforcement:** consumer-side checks that forbid candidate content from filling legal/data/method/participation/closeout/projection authority slots without producer/reader validation; integration with existing authority envelope semantics so the firewall is a structural guarantee, not a flag.

The phase must run on every read surface that currently consumes formulator output (claim registry, semantic binding, public projection, dashboard). Existing P15 closure points in W1/W3/W5 are reused; W6.F gives them a real input channel to gate.

**Parallelism contract:** all six phases publish their interface schemas (facet schema, rule schema, obligation schema, claim family schema, candidate schema, ledger schema) at wave start so implementations land in parallel. No phase consumes another phase's runtime implementation; consumers wait for Wave 7.

**Capability closures:**

- W6.A closes `producer_missing` for the universal grammar compiler (previously `contract_only` under C4 mapping).
- W6.B closes `producer_missing` for the governed obligation rule catalog (previously absent).
- W6.C closes `producer_missing` for the obligation graph and the candidate/bundle/blocking frontier ledger (previously `contract_only` under C38).
- W6.D closes `producer_missing` for typed claim decomposition and baseline/alternative seed records.
- W6.E closes `producer_missing` for LLM formulator and multi-critic ensemble (previously `implemented_but_not_orchestrated` for `policy_design/critic.py` and `adversary.py`).
- W6.F closes `bridge_missing` for the candidate-to-authority firewall (previously the firewall had no structured input channel).

**Negative tests:**

- intent without facet derivation cannot produce an `ObligationGraph` (W6.A);
- a rule without `logic_hash`, `owner`, `authority_level`, and `evidence_basis` cannot become governed (W6.B);
- the bundle ledger cannot contain two active bundles for the same `(family, scope, authority_profile, temporal_window, remedy_path)` key (W6.C);
- the blocking frontier cannot contain an item whose source is `llm_candidate` without producer validation (W6.C);
- a superiority claim without baseline and at least one named alternative cannot be admitted to the claim registry (W6.D);
- a critic verdict that all eight critics agree on with identical substantive output triggers a diversity warning (W6.E);
- a candidate marked `candidate_unverified` cannot satisfy any authority slot at any read site (W6.F);
- a hypothesis ledger entry without prompt fingerprint, tool refs, and repair-decision lineage cannot be admitted to any downstream consumer (W6.F).

**Exit gate:**

- universal grammar compiler produces typed facets for at least three diverse policy intents (one each from MSME credit / health intervention / housing subsidy, mined from W11.A corpus seeds);
- governed obligation rule catalog has at least 50 governed rules across legal/fiscal/equity/data/implementation/method/participation families, each with provenance and version;
- obligation graph compiler emits non-trivial graphs (candidate / bundle / blocking frontier all non-empty) for the same three intents;
- claim decomposition compiler emits typed `ClaimFamilyAssignment` with baseline and alternative seeds for the same three intents;
- LLM formulator + critic ensemble produces structured candidates for the same three intents; ensemble diversity baseline metric is recorded;
- hypothesis ledger persists candidates and the firewall blocks at least one synthetic laundering case in test fixtures;
- I7 universal compilation smoke passes or emits a typed compilation blocker;
- I7-bis integration realism check runs the runtime path and either passes or emits typed blockers for missing producer bindings, graph edges, or warrant structures;
- capability ratchet labels six new compilation capabilities as `implemented` (no `producer_missing` / `consumer_missing` / `semantic_test_missing` remaining for these specific capabilities).

**Validation:**

```bash
uv run pytest tests/unit/policy_grammar tests/unit/obligation_rules tests/unit/obligation_graph -q
uv run pytest tests/unit/scientist/policy_design/test_claim_decomposition.py tests/unit/scientist/policy_design/test_formulator.py tests/unit/scientist/policy_design/test_critic_ensemble.py -q
uv run pytest tests/unit/runtime/quality/test_hypothesis_ledger.py tests/unit/runtime/quality/test_candidate_firewall.py -q
uv run pytest tests/repo_quality/tools/test_universal_compilation_smoke.py -q
uv run python tools/quality/validation/run_universal_compilation_integration_realism_check.py --repo-root . --allow-typed-blockers --output _build/.tmp/production-quality/i7bis_integration_realism_check.json
```

## Wave 7 - Requirement Compilation, Producer Adapter Refactor, And Staged Producer Pipeline

**Purpose:** move the W3 producer adapters from "selectors over their own internal pools" to "consumers of typed RequirementSpec produced by per-family compilers", implement the C40 8-stage staged producer pipeline orchestrator, and refactor the acquisition planner to consume gaps in compiled requirements rather than gaps in producer outputs.

**Entry gate:** Wave 6 interface schemas accepted; I7 universal compilation smoke and I7-bis integration realism check passing or blocked with typed compilation blockers; no new W6 capability remaining at `producer_missing`.

**Parallel phases:**

#### W7.A Data Requirement Compiler And Fabric Adapter Refactor

This phase implements E10 (refactored) over C2, C6, C11, and C22 under FT-ADR-01 while guarding against P02, P05, P08, P12, and P14. Its write surface is `src/polisyos/data_requirement/` (new compiler module) plus refactor of `src/polisyos/fabric/` selectors. The deliverable is:

- typed `DataRequirementSpec` per claim with required data families, scope (population/geography/time), recency horizon, lineage strictness, quality minima, missingness tolerance, transformation tolerance, admissibility predicates, mandatory facets;
- Fabric adapter that consumes `DataRequirementSpec` and emits SourceContract `selected` / `rejected` / `blocked` / `context_only` bindings against compiled requirements rather than against `scenario_evidence_contract.admissible_data_source_families`;
- legacy regression bridge: `scenario_evidence_contract` remains as a closeout-grade pre-existing scenario contract surface, but its `admissible_data_source_families` list becomes derived from compiled requirements (not hardcoded), with a sunset plan recorded in `architecture/shims.toml`.

The phase retires the W6.A regression-guard for scenario source families: production-data-static checks now verify that compiled `DataRequirementSpec` for the public golden case yields the admissible families, not that those families are hardcoded.

#### W7.B Legal Authority Requirement Compiler And Lex Adapter Refactor

This phase implements E9 (refactored) over C2, C7, C8, and C11 under FT-ADR-04 while guarding against P01, P05, P08, and P12. Its write surface is `src/polisyos/legal_requirement/` (new compiler) plus refactor of `src/polisyos/lex/` evaluation. The deliverable is:

- typed `LegalAuthorityRequirementSpec` per claim with required hierarchy depth, temporal competence window, authority-type facets (`implementing` / `delegating` / `enabling` / `funding` / `oversight` / `appeal_or_contestability`), required instrument classes, scope/population/time predicates, fallback policy;
- Lex adapter that consumes `LegalAuthorityRequirementSpec` and emits graded legal admissibility (`admissible` / `context_only` / `proxy_with_limitation` / `contested` / `blocked` / `out_of_scope`), per-claim selected/rejected/no-anchor refs, jurisdiction-config fallback, competence-window splitting;
- norms can carry multiple authority types in a single record (C7 mini-decision 2).

Generic Ukrainian / jurisdiction-topic matches without claim-level competence are explicitly `context_only`, not `admissible`.

#### W7.C Method Validity Requirement Compiler And Foundry Adapter Refactor

This phase implements E12 (refactored) over C9, C10, C11, and C13 while guarding against P01, P02, P10, and P14. Its write surface is `src/polisyos/method_requirement/` (new compiler) plus refactor of `src/polisyos/foundry/` method selection and `src/polisyos/scientist/methods/` workflow integration plus extension of W3.A IR analytics bridge to consume requirements. The deliverable is:

- typed `MethodValidityRequirementSpec` per claim with identification class (`point` / `partial` / `bounds` / `negative_certificate`), transportability requirement, uncertainty class, fairness decomposition need, strategic-response sensitivity, simulation DGP requirements, assumption-validation needs;
- Foundry adapter and IR bridge that consume `MethodValidityRequirementSpec` and emit selected/rejected methods with reasons, runtime assumption gates, method output refs, uncertainty envelopes, limitations, simulation lineage;
- generic `foundry.execute` and offline-only validity cannot satisfy serious method obligations; selection emits explicit `RejectedMethodCandidate` records with rejection codes.

#### W7.D Scholar Support Requirement Compiler And Scholar Adapter Refactor

This phase implements E11 (refactored) over C13, C14, and C26 under FT-ADR-02 while guarding against P01, P02, P10, and P14. Its write surface is `src/polisyos/scholar_requirement/` (new compiler) plus refactor of `src/polisyos/scholar/` search/scoring/spine. The deliverable is:

- typed `ScholarSupportRequirementSpec` per claim with required publication tier, recency, replication count, independence breadth, citation-network depth, dependent-corpus collapse rules, participation-like claim distinction;
- Scholar adapter that consumes the spec and emits typed support/conflict/independence refs with collapse reasons;
- Scholar publications cannot imply affected-person representativeness (preserves FT-ADR-02 firewall).

#### W7.E Participation Provenance Requirement Compiler And Participation Surface Refactor

This phase implements E11 (participation side) and C19/C34 under FT-ADR-02 while guarding against P05, P10, P14, and P15. Its write surface is `src/polisyos/participation_requirement/` (new compiler) plus refactor of participation surfaces in `src/polisyos/scientist/policy_design/`, public projection, and dashboard validators. The deliverable is:

- typed `ParticipationProvenanceRequirementSpec` per claim use with required mode (survey / deliberative panel / hearing / complaint / testimony / expert interview), required sampling frame, representativeness class, consent/redaction, dissent handling, sponsor disclosure;
- consumer-side enforcement that LLM/analyst speculation cannot satisfy preference/legitimacy claims, and that imperfect representativeness downgrades the claim use rather than blocks the case;
- public/redacted projection obligations and privacy constraints; representativeness thresholds remain governed config under named methodology/governance owner.

#### W7.F Eight-Stage Producer Pipeline Orchestrator

This phase implements C8 and C40 against P02, P12, and P37 (bridge authority discipline) while guarding against P05 and P15. Its write surface is `src/polisyos/runtime/quality/producer_pipeline.py` (new orchestrator) plus integration with control-plane workflows, replay, bundle assembly, inspection, and readiness paths. The deliverable is a runtime orchestrator that drives producers through eight bounded-liveness stages:

1. **Run contract and carrier** — request, authority profile, scenario refs, concept-spine boot.
2. **Spine bootstrap** — universal grammar compilation (W6.A), obligation graph compilation (W6.C), claim decomposition (W6.D).
3. **Parallel preflight** — producers (W7.A-E) declare consumed concepts/requirements, expected output families, deadlines.
4. **First-pass context/blocker emission** — context-only or typed-blocker first results; never authority.
5. **Provisional claim registry** — claims bound to facets, requirements, baseline/alternative refs.
6. **Second-pass authoritative binding** — refactored adapters produce `selected` / `rejected` / `blocked` bindings against compiled RequirementSpecs.
7. **Semantic closure** — semantic binding + portfolio + effective independence + argument graph (W8) assembly.
8. **Closeout and projection** — unified closeout substrate (W4.D) and typed PDC projection (W4.E / W8.A graph).

Producer states implement the C40 ten-state machine: `requested`, `preflighted`, `waiting_on_spine`, `waiting_on_peer`, `emitted_context_only`, `emitted_binding`, `blocked`, `timed_out`, `degraded`, `rerun_required`, `abandoned`. `waiting_on_peer` must name producer, artifact family, required fields, and deadline. `waiting_on_spine` is only for shared run-level inputs.

#### W7.G Acquisition Planner Refactor As Requirement Gap Consumer

This phase implements E17 (refactored) over C22 under FT-ADR-01 while guarding against P01, P09, and P10. Its write surface is refactor of `src/polisyos/scientist/methods/search/voi*.py` and `src/polisyos/runtime/quality/acquisition/`. The deliverable is:

- planner consumes typed gaps in compiled `DataRequirementSpec` / `LegalAuthorityRequirementSpec` / `MethodValidityRequirementSpec` / `ScholarSupportRequirementSpec` / `ParticipationProvenanceRequirementSpec` instead of post-hoc gaps in producer outputs;
- eligibility (`gap_type × authority_level × mandatory_gate_state`) precedes ranking; VOI ranks eligible strategies only;
- next-action records distinguish `accepted_deficit`, `publish_with_limitation`, `closeout_block`, `acquire`, `proxy_with_limitation`, `rerun`.

**Parallelism contract:** A-E refactor independent producer families and write per-family compiler modules; F orchestrator consumes A-E published interfaces; G consumes A-E published interfaces. No phase modifies sibling phase's compiler logic. Shared producer pipeline orchestrator schema published at wave start.

**Capability closures:**

- W7.A closes `bridge_missing` between obligation graph and Fabric source selection (was the canonical instance of the W6.A regression).
- W7.B closes `bridge_missing` between obligation graph and Lex norm matching.
- W7.C closes `bridge_missing` between obligation graph and Foundry method selection plus IR analytics binding.
- W7.D closes `bridge_missing` between obligation graph and Scholar evidence binding.
- W7.E closes `bridge_missing` between obligation graph and participation surfaces (was the entire participation-laundering risk surface).
- W7.F closes `implemented_but_not_orchestrated` for staged producer execution; producers no longer race or wait silently.
- W7.G closes `bridge_missing` between compiled requirement gaps and acquisition next actions.

**Negative tests:**

- a Fabric `selected` binding without matching `DataRequirementSpec` admissibility is rejected (W7.A);
- a Lex `admissible` ruling without `LegalAuthorityRequirementSpec` competence-window match is downgraded to `context_only` (W7.B);
- a Foundry method without runtime assumption-validation against `MethodValidityRequirementSpec` is `rejected` with reason (W7.C);
- a Scholar publication without independence refs against `ScholarSupportRequirementSpec` cannot inflate support (W7.D);
- thin consultation cannot satisfy `ParticipationProvenanceRequirementSpec` for prevalence claims (W7.E);
- a producer in `waiting_on_peer` without named producer/artifact/field/deadline emits a typed liveness blocker (W7.F);
- acquisition planner cannot rank a strategy around a non-overridable gate (W7.G).

**Exit gate:**

- five per-family RequirementSpec compilers emit non-trivial specs for the same three diverse policy intents from W6 exit;
- five refactored adapters consume RequirementSpec output and emit selected/rejected/blocked bindings;
- producer pipeline orchestrator drives at least one full eight-stage run end-to-end on a real-ish fixture;
- acquisition planner emits eligibility-bound next actions for at least one synthetic gap per requirement family;
- I8 compiled PDC graph end-to-end smoke passes or emits typed integration blocker;
- W6.A regression on production_msme_panel / credit_program_registry / regional_displacement_indicators is replaced by compiled-requirement assertion.

**Validation:**

```bash
uv run pytest tests/unit/data_requirement tests/unit/legal_requirement tests/unit/method_requirement tests/unit/scholar_requirement tests/unit/participation_requirement -q
uv run pytest tests/unit/lex tests/unit/fabric tests/unit/foundry tests/unit/scholar -q
uv run pytest tests/unit/runtime/quality/test_producer_pipeline.py -q
uv run pytest tests/unit/scientist/methods/search -q
uv run pytest tests/repo_quality/tools/test_compiled_pdc_graph_smoke.py -q
```

## Wave 8 - PDC Graph Compilation, Argument Building, Welfare And Conflict Emission

**Purpose:** introduce the runtime `RuntimePolicyDesignCase` graph distinct from projection; build argument/warrant graph; compile baseline/alternative comparison; emit Pareto frontier with social-weight provenance; materialise conflict records as first-class facts; annotate the graph with graded effective independence.

**Entry gate:** Wave 7 staged pipeline and RequirementSpec compilers accepted; I8 compiled PDC graph end-to-end smoke passing or blocked.

**Parallel phases:**

#### W8.A RuntimePolicyDesignCase Graph Compiler

This phase implements L7 from synthesis over C16 while guarding against P03, P05, P14, and P15. Its write surface is `src/polisyos/pdc/compiler.py` (new module) plus integration with claim registry, semantic binding, closeout substrate, and projection backend. The deliverable is the typed `RuntimePolicyDesignCase` graph object with claim graph, warrant structures, obligation refs, producer binding refs, baseline/alternative refs, conflict refs, effective-independence refs, closeout refs, contested-record refs, deficit register refs, and authority envelope (`authoritative_for=["pdc_graph_structure"]`, `may_not_use_for=["projection_authority", "claim_authority"]`).

The graph is runtime-owned, not projection-owned. W4.E projection backend is refactored to consume this graph as its source of truth rather than to build projection from scattered fields.

#### W8.B Argument/Warrant Graph Builder

This phase implements C15 over existing `assurance_case.py` SACM/CAE/GSN mapping while guarding against P02 and P03. Its write surface is `src/polisyos/runtime/quality/argument_graph.py` (new file extending `assurance_case.py`). The deliverable is a runtime-emitted argument graph (claim → argument → warrant → evidence → authority → readiness) with typed warrant semantics (assumptions, applicability predicates, confidence/reliability refs, BERL refs, limits), exporter to SACM/CAE/GSN profiles, and machine-readable warrant inspection surface.

#### W8.C Baseline + Alternative Comparison Compiler

This phase completes C10 over W6.D seed records while guarding against P10 and P14. Its write surface is `src/polisyos/scientist/policy_design/baseline_compiler.py` (new file) plus integration with Foundry methods, IR causal analytics, and Scholar/Fabric producers. The deliverable is a compiler that turns W6.D baseline/alternative seeds into full comparison records: evidence for selected option, evidence for alternatives, comparison method refs, comparison limitations, rejected-option reasons, dominated-frontier records.

Superiority claims cannot pass without comparison records.

#### W8.D Pareto Frontier And Social-Weight Provenance Emitter

This phase implements C18 over Foundry welfare bounds and social-weight schedules while guarding against P05 and P15. Its write surface is `src/polisyos/foundry/welfare/frontier_emitter.py` and `social_weight_provenance.py` (new files). The deliverable is:

- typed Pareto frontier records over multi-objective tradeoffs (no forced aggregation);
- value-choice decision points distinct from frontier facts;
- social-weight provenance: who chose weights, mandate, time, affected groups, dissent, review status, sponsor disclosure;
- welfare audit trail bound to claim refs;
- public/reviewer surface that exposes frontier and value choice rather than scalar aggregate.

#### W8.E Conflict-To-Portfolio Materializer

This phase implements C14 over existing `ConflictDetector` and cross-graph compiler while guarding against P02 and P14. Its write surface is `src/polisyos/evidence/portfolio/conflict_records.py` and `src/polisyos/scientist/cross_graph/conflict_materializer.py` (new files). The deliverable is first-class typed conflict records in claim registry and portfolio: empirical, methodological, legal, scope, normative, participation, implementation, authority/provenance conflicts, each with typed resolution route (new evidence / method arbitration / legal hierarchy / scope narrowing / governance decision / persistent contested state).

Post-hoc conflict detection becomes a backstop only; pre-emission producer handshake (W7.F) catches conflicts earlier.

#### W8.F Effective Independence Graph Annotator With Scarcity Path

This phase implements C13 and C29 over W4.B portfolio aggregation while guarding against P14. Its write surface is `src/polisyos/evidence/portfolio/effective_independence_graph.py` (new file) and feature-flagged graded-calculus extension to W4.B. The deliverable is:

- evidence-line identity over (claim ids, strand, polarity, source refs, primary source, retrieval path, legal authority, author/institution/sponsor, dataset/corpus/snapshot/subject pool, preprocessing, transformation lineage, method family, identification strategy, assumptions, proof-reuse status, LLM generation path, simulation DGP, participation sample frame, concept spine, jurisdiction, time roles);
- hard-collapse cases (same primary source, same snapshot/preprocessing/identification, same controlling legal instrument, same DGP/calibration/assumption family, same LLM model/prompt/retrieval, same study reported multiple times);
- partial-collapse pairwise model `D(a,b) = min(0.95, sum(weight_c × overlap_c))`, `I(a,b) = 1 - D(a,b)`;
- aggregation with `quality(a) × novelty(a | S)` mass formula;
- `scarcity_structural` vs `scarcity_remediable` separation: structural scarcity may lead to lower-authority closeout or production with reviewed single-line deficit, never to support inflation;
- counterevidence preserved separately from support, never collapsed away.

**Parallelism contract:** A publishes graph schema at wave start; B-F annotate the graph via separate writer modules; no two phases own the same graph field.

**Capability closures:**

- W8.A closes `producer_missing` for `RuntimePolicyDesignCase` graph compiler.
- W8.B closes `consumer_missing` for SACM/CAE/GSN argument graph; warrant semantics now externally inspectable.
- W8.C closes `producer_missing` for baseline/alternative comparison compiler.
- W8.D closes `producer_missing` for Pareto frontier and social-weight provenance.
- W8.E closes `bridge_missing` between ConflictDetector and claim registry / portfolio / public projection.
- W8.F closes `bridge_missing` for graded effective independence and `scarcity_structural` path.

**Negative tests:**

- W4.E projection cannot read a field that does not appear in the W8.A graph;
- a superiority claim without W8.C comparison records fails semantic binding;
- a scalar welfare aggregate without W8.D frontier and social-weight provenance is blocked from production publication;
- a portfolio with multiple Scholar publications from the same study reports the same effective independent mass as one publication (W8.F);
- rare-domain scarce evidence is reported as `scarcity_structural`, never inflated to multiple independent lines (W8.F);
- a conflict found by ConflictDetector that does not appear as a W8.E record blocks closeout.

**Exit gate:**

- W8.A graph compiler emits typed graphs for at least three diverse policy intents (W6 exit fixtures);
- W8.B argument graph builder produces inspectable SACM/CAE/GSN export for the same three;
- W8.C baseline compiler emits comparison records for at least one superiority claim per fixture;
- W8.D Pareto frontier and social-weight records exist for at least one welfare-bearing claim per fixture;
- W8.E conflict materializer emits at least one first-class conflict record for one fixture;
- W8.F effective independence graph reports collapse for at least one fixture with duplicate evidence lines;
- W4.E projection backend refactored to consume W8.A graph; consumer contract verification passes.

**Validation:**

```bash
uv run pytest tests/unit/pdc tests/unit/runtime/quality/test_argument_graph.py -q
uv run pytest tests/unit/scientist/policy_design/test_baseline_compiler.py -q
uv run pytest tests/unit/foundry/welfare/test_frontier_emitter.py tests/unit/foundry/welfare/test_social_weight_provenance.py -q
uv run pytest tests/unit/evidence/portfolio/test_conflict_records.py tests/unit/evidence/portfolio/test_effective_independence_graph.py -q
uv run pytest tests/repo_quality/tools/test_pdc_graph_consumer_contract.py -q
```

## Wave 9 - Advanced Lifecycle, Drift Detection, And Rule Replay

**Purpose:** close the contracts-vs-implementations gap that the second-pass code audit found — drift detectors, partial-scope reissue mechanics, Data Forge snapshot provenance manifest, memory decay, continuous-governance → lifecycle bridge, rule evolution replay engine — so closed PDCs do not silently go stale and rule changes do not silently re-interpret past meaning.

**Entry gate:** Wave 8 PDC graph and effective independence graph accepted; existing W4.C lifecycle and W2.B rule evolution registry available.

**Parallel phases:**

#### W9.A Drift Detector Implementations

This phase implements detector code for monitor event types that currently exist as contracts only: `calibration_drift`, `fairness_drift`, `policy_context_drift`, `source_invalidation`. Its write surface is `src/polisyos/scientist/governance/continuous/detectors/` (new directory with one detector per family). The deliverable is four detectors that consume W2.E calibration ledger, W2.F balanced memory, monitor event streams, and Data Forge snapshot manifests, emit typed monitor events with severity/scope/affected-claim-ids, and respect sparse-history policy (`Insufficient` / `Thin` / `Forming` / `Mature adverse`).

#### W9.B Partial-Scope Reissue Mechanics

This phase extends `ReissuePacket` in `src/polisyos/scientist/governance/continuous/reissue.py` with `scope_to_revise: list[claim_id]`, `unchanged_records: list[ref]`, `superseded_refs: list[ref]`, `public_diff_refs: list[ref]`, `partial_publication_state`. The deliverable is partial-scope reissue flow: detector fires, lifecycle bridge maps event to affected claims, reissue affects only those claim ids, the closed PDC preserves historical semantics for unaffected claims.

#### W9.C Data Forge Snapshot Provenance Manifest

This phase adds `src/polisyos/data_forge/provenance_manifest.py` (new) plus extensions to `kernel/snapshot/`. The deliverable is a durable `(corpus_id, data_hash, creation_time, lineage_refs, quality_gates, builder_revision, transform_lineage)` ledger on every snapshot transaction; closeout can ask "which official snapshot satisfied this claim?" and receive a typed answer.

#### W9.D Memory Decay, TTL, And Contamination Controls

This phase extends `src/polisyos/scientist/orchestration/memory/failure_lessons.py` and W2.F balanced memory schemas with TTL, decay function, contamination policy, scope-revocation triggers, and success/failure balance metrics. The deliverable is a memory subsystem that forgets stale lessons, decays low-value patterns, revokes scope on rule changes, and tracks conservative-bias metrics (risk overprediction, opportunity suppression, excessive blocker rate).

#### W9.E Continuous Governance Event → Claim Lifecycle Bridge

This phase implements C20 lifecycle dependency over W9.A detectors and W9.B partial-reissue mechanics. Its write surface is `src/polisyos/scientist/governance/continuous/lifecycle_bridge.py` (new). The deliverable is a typed bridge that maps detector events into claim lifecycle transitions (`stale`, `blocked`, `invalidated`, `superseded`, `review_required`, `reissued`, `withdrawn`) and updates public revision state.

#### W9.F Rule Evolution Replay Engine

This phase implements actual replay execution over W2.B registry. Its write surface is `src/polisyos/runtime/quality/rule_replay_engine.py` (new) plus integration with research-DAG replay and claim lifecycle. The deliverable is an engine that, given a closed PDC and a rule/taxonomy change record, can replay the PDC under the original rule logic (`replay_under_original_rules`), under the new logic for comparison (`replay_under_new_rules`), emit a comparison report, and trigger mandatory revalidation per C33 change-class table.

**Parallelism contract:** A publishes detector event schema; B publishes extended ReissuePacket schema; C, D, F write to disjoint modules; E depends on A and B published schemas.

**Capability closures:**

- W9.A closes `producer_missing` for four drift detectors (contracts existed; detectors did not).
- W9.B closes `producer_missing` for partial-scope reissue (whole-case reissue existed; partial did not).
- W9.C closes `artifact_missing` for Data Forge snapshot provenance manifest.
- W9.D closes `producer_missing` for memory decay and contamination controls.
- W9.E closes `bridge_missing` between continuous-governance events and claim lifecycle.
- W9.F closes `producer_missing` for rule evolution replay execution.

**Negative tests:**

- a calibration drift signal in W2.E that does not produce a W9.A monitor event indicates detector regression;
- a `ReissuePacket` without `scope_to_revise` cannot be created when only some claims are affected (W9.B);
- a Data Forge snapshot without provenance manifest cannot satisfy closeout-grade data authority (W9.C);
- a reflexive memory entry older than its TTL cannot influence current run (W9.D);
- a detector event without lifecycle bridge produces an `event_missing_lifecycle_bridge` blocker (W9.E);
- a rule change marked as `stricter_admissibility` that does not trigger mandatory revalidation for closed PDCs that relied on the old rule fails W9.F replay coverage.

**Exit gate:**

- four drift detectors emit at least one event each on synthetic fixtures;
- partial reissue affects only named claim ids on at least one fixture;
- Data Forge snapshot provenance manifest is present on every snapshot in the universal-corpus fixtures;
- memory decay reduces stale entries below TTL threshold;
- lifecycle bridge maps at least one detector event per family to claim transitions;
- rule replay engine reproduces at least one closed PDC under original rules and at least one rule-change comparison report;
- I9 lifecycle drift smoke passes or emits typed lifecycle blocker.

**Validation:**

```bash
uv run pytest tests/unit/scientist/governance/continuous/detectors -q
uv run pytest tests/unit/scientist/governance/continuous/test_reissue_partial_scope.py -q
uv run pytest tests/unit/data_forge/test_provenance_manifest.py -q
uv run pytest tests/unit/scientist/orchestration/memory/test_decay_and_contamination.py -q
uv run pytest tests/unit/scientist/governance/continuous/test_lifecycle_bridge.py -q
uv run pytest tests/unit/runtime/quality/test_rule_replay_engine.py -q
uv run pytest tests/repo_quality/tools/test_lifecycle_drift_smoke.py -q
```

## Wave 10 - Temporal/Liveness Invariants, Run-Cost Enforcement, And Self-FMEA Depth

**Purpose:** extend formal_invariants beyond finite-state with bounded-liveness deadline consistency; add the three missing R14 adversarial probes (authority spoofing, prompt injection, participation speculation); complete E18 run-cost enforcement with authority-level-blocking gates; measure review effectiveness in advisory mode; implement complexity-budget governance pruning under Net-MAV; annotate prompt/tool repair decisions with FMEA refs.

**Entry gate:** Wave 9 lifecycle/drift/replay accepted; existing `formal_invariants.py`, `performance_budget.py`, `challenge_factory.py`, `prompt_tool_ledger.py` available.

**Parallel phases:**

#### W10.A Temporal/Liveness Invariant Extensions

This phase implements C24 temporal/liveness over `formal_invariants.py` under FT-ADR-05. Its write surface extends `src/polisyos/runtime/quality/formal_invariants.py` with deadline-consistency invariants. The deliverable is bounded-liveness checks (`eventually X` becomes `X within deadline D, else escalate`) across producer pipeline states (W7.F), retry/lease state, escalation paths, and reissue flows. Deadline algebra integrates with C40 producer state machine.

#### W10.B Review Effectiveness Measurement Pipeline

This phase implements C24 review effectiveness under FT-ADR-06. Its write surface is `src/polisyos/scientist/governance/human_review/effectiveness.py` (new). The deliverable is advisory-only measurement of override rate, time-spent distributions, dissent, no-delta reviews, separation-of-duty failures over existing VOI escalation metadata. Blocking thresholds remain governed config until longitudinal evidence supports them.

#### W10.C Missing R14 Adversarial Probes

This phase implements C26 missing probes over existing `challenge_factory.py`. Its write surface extends `src/polisyos/scientist/evals/challenge_factory.py` with three new probe classes plus per-probe test fixtures. The deliverable is:

- **authority_spoofing**: fixtures that present LLM/projection/bridge content with fake authority envelope; firewall must reject;
- **prompt_injection** (beyond ambiguous instruction): fixtures with embedded instructions that try to bypass critic ensemble; ledger must persist + firewall must block;
- **participation_speculation**: fixtures where LLM speculates affected-person preferences without provenance; W7.E requirement compiler + firewall must downgrade or block.

#### W10.D Run-Cost Enforcement Gates

This phase completes E18 over C23 and W2.C telemetry. Its write surface is `src/polisyos/runtime/quality/cost_gate.py` (new) plus extensions to `performance_budget.py`. The deliverable is authority-level-blocking gates on compute-dollar, provider API calls, tokens, embeddings/searches, wall-clock, retry, acquisition budgets. Production-authority runs may fail with typed cost blocker; research-authority runs may emit limitation only.

#### W10.E Complexity Budget Governance Pruning

This phase implements C32 over W2.D self-FMEA telemetry. Its write surface is `src/polisyos/runtime/quality/complexity_governance.py` (new). The deliverable is:

- Net-MAV computation `decision_gain + falsification_value + authority_gain + auditability_gain - human_time_cost - latency_penalty - rerun_penalty - false_block_penalty`;
- Net-MAV gating: new control may not enter blocking frontier without expected Net-MAV and telemetry refs;
- periodic prune review: controls that never affect a decision after a measurement window become retire/merge candidates;
- self-application: complexity governance itself is subject to retirement if it stops causing prune decisions.

#### W10.F Repair-Decision FMEA Annotation

This phase implements C24 repair-decision FMEA over existing `prompt_tool_ledger.py`. Its write surface extends `src/polisyos/runtime/quality/prompt_tool_ledger.py` with FMEA refs (`failure_mode`, `severity`, `cause`, `recommended_mitigation`, `residual_risk`) on every repair decision. The deliverable is repair decisions that surface as machinery failures in closeout, dashboard, and operator surfaces rather than disappearing into producer status.

**Parallelism contract:** all six phases write to disjoint files or extend existing single-purpose files with no overlap.

**Capability closures:**

- W10.A closes `producer_missing` for bounded-liveness deadline-consistency invariants.
- W10.B closes `producer_missing` for review-effectiveness measurement (advisory).
- W10.C closes `semantic_test_missing` for three previously-uncovered R14 categories.
- W10.D closes `producer_missing` for authority-level cost enforcement.
- W10.E closes `producer_missing` for Net-MAV-gated complexity governance.
- W10.F closes `consumer_missing` for repair-decision FMEA surface.

**Negative tests:**

- a producer that waits past deadline without escalation triggers W10.A liveness violation;
- a review with override rate above governed warning threshold emits an advisory note, never a block (W10.B);
- a fixture with fake authority envelope or embedded prompt injection passes existing structural checks but fails W10.C probes;
- a production-authority run that exceeds cost budget without authority-level override emits W10.D blocker;
- a new control proposed without expected Net-MAV cannot enter blocking frontier (W10.E);
- a prompt/tool repair decision without FMEA refs cannot exit W10.F.

**Exit gate:**

- bounded-liveness invariants cover producer pipeline, retry/lease, escalation, reissue flows;
- review-effectiveness pipeline emits at least one advisory note on universal-corpus fixtures;
- three new R14 probes catch their synthetic targets;
- cost enforcement blocks at least one synthetic over-budget fixture;
- complexity governance prunes or retains at least one control based on Net-MAV;
- repair-decision FMEA annotation visible on at least one prompt/tool repair fixture;
- I10 cost gate + FMEA smoke passes or emits typed blocker.

**Validation:**

```bash
uv run pytest tests/unit/runtime/quality/test_formal_invariants.py tests/unit/runtime/quality/test_cost_gate.py tests/unit/runtime/quality/test_complexity_governance.py tests/unit/runtime/quality/test_prompt_tool_ledger_fmea.py -q
uv run pytest tests/unit/scientist/governance/human_review/test_effectiveness.py -q
uv run pytest tests/unit/scientist/evals/test_challenge_factory_extensions.py -q
uv run pytest tests/repo_quality/tools/test_cost_gate_and_fmea_smoke.py -q
```

## Wave 11 - Universal Outcome Corpus And Compilation Truthfulness Tools

**Purpose:** build the repo-owned universal outcome corpus (12+ real cases across 6+ domains and 3 authority levels) with claim/evidence decomposition annotations and expert adjudication labels; deliver three new metric tools (compilation truthfulness, domain coverage breadth, critic ensemble diversity) that Wave 12 needs for honest universal-capability claim.

**Entry gate:** Wave 10 invariants/cost/FMEA accepted; outcome corpus deliverable from Real Policy Corpus And Baseline Track promoted from informal track to formal wave-owned deliverable.

**Parallel phases:**

#### W11.A Universal Outcome Corpus Sourcing

This phase sources at least 12 real policy cases across at least 6 domains and 3 authority levels. Its write surface is `docs/research/universal-policy-design/outcome-corpus/` (new directory with one Markdown file per case carrying YAML frontmatter per Annotation Protocol Draft from research plan). The deliverable is repo-owned case files with jurisdiction, policy time, instrument type, targeting, beneficiary classes, expected evidence families, raw source refs or redacted source hashes, known failure/limitation labels.

Domain coverage targets (illustrative): MSME credit / grant; public health intervention; housing subsidy or rent control; tax relief or enforcement; education access; climate adaptation; labour activation; migration/displacement; public safety; digital public service; infrastructure prioritisation; social protection targeting.

#### W11.B Claim And Evidence Decomposition Annotations

This phase produces per-case annotations following the Annotation Protocol Draft (claim records with text_ref, scope, evidence_refs, method_refs, legal_refs, participation_refs, risks, tradeoffs, admissibility_label, limitation_refs, contestability_status; obligations with generated_from_facets, required_evidence_family, status, reviewer_notes; known outcomes or failures with finding_id, source_ref, would_prior_obligation_have_flagged).

#### W11.C Expert Adjudication Labels

This phase produces expert adjudication labels under the C30 rubric (`semantic_pass`, `limitation_required`, `contested`, `unsupported`, `false_pass`, `fabricated_unverifiable`, `reviewer_disagreement`) per case and per claim, with gold-card fields (claim_id, dimension_id, evidence_ref, context_ref, failure_mode, why_structural_checks_missed_it, status_should_have_been, required_surface_change) for every rejected structural pass.

Reviewer topology follows the Corpus Budget And Reviewer Topology in the research plan: deep-pilot overlap to calibrate annotation guide, partial disjoint thereafter; reviewer role, expertise basis, conflicts, disagreement category recorded; substantive disagreement preserved, never collapsed into a single hidden gold label.

#### W11.D Fixture Generation, Loaders, And Rotating Fixtures

This phase produces machine-loadable fixtures plus rotation policy. Its write surface is `tests/fixtures/universal-corpus/` and `src/polisyos/corpus/loaders.py` (new). The deliverable is per-case fixture files (input intent, expected facet outputs, expected obligation graph slice, expected claim families, expected RequirementSpecs, expected adapter selected/rejected/blocked bindings, expected closeout state per authority level, expected projection truthfulness), plus public/hidden/rotating splits to prevent overfitting.

#### W11.E Compilation Truthfulness Audit Tool

This phase delivers `tools/quality/validation/check_compilation_truthfulness.py` (new). The deliverable is a tool that runs the universal compilation kernel (W6) and producer pipeline (W7) on each case, then compares output against W11.B annotations and W11.C adjudication. Reports per case:

- **true_positive_obligations**: obligations compiled and matching annotation;
- **missed_obligations**: obligations in annotation but absent from compiled graph;
- **hallucinated_obligations**: obligations compiled but absent from annotation;
- **scope_drift_obligations**: obligations whose scope differs from annotation;
- **authority_drift_obligations**: obligations whose authority level differs from annotation;
- **per_case_truthfulness_score**: weighted aggregate, with weights from C36 capability debt purpose multipliers.

#### W11.F Domain Coverage Breadth And Critic Ensemble Diversity Tools

This phase delivers `tools/quality/validation/check_domain_coverage_breadth.py` and `check_critic_ensemble_diversity.py` (new). Reports:

- **domain_coverage_breadth**: number of committed domains where W6.C produced a non-trivial graph (≥ N candidates per family layer × M layers);
- **critic_ensemble_diversity**: per-case Jaccard of unique failure-modes flagged by each critic; warns when ensemble collapses into single persona;
- **expert_useful_design_ceiling** and **per_authority_expert_useful_design_ceiling**: expert-adjudicated ceiling stratified by research / governed / production authority level. Runtime actuals are reported by W12.D as `runtime_useful_design_rate` and `useful_design_alignment_rate`.

#### W11.G Corpus-Stub Producer Layer

This phase builds the corpus-grounded producer stub layer used only by W12.D validation mode. Its write surface is `tests/fixtures/universal-corpus/producer_stubs/*.producer_stubs.json` plus `src/polisyos/runtime/quality/corpus_fixture_producer_reports.py`. Each case fixture is derived from W11.C expert adjudication and returns selected, limited, or blocked adapter-shaped responses so the universal compilation path can prove useful design when admissible evidence is present. The stub boundary is `surface_out_of_scope` for production authority: it is authoritative for corpus validation and compiler-path probing only, and may not satisfy production closeout, producer domain truth, claim evidence authority, or public projection authority.

**Parallelism contract:** A-C are methodological; D-G are tools/fixtures; both tracks can proceed independently after wave start. A publishes the case index at wave start so D-G can run incrementally.

**Capability closures:**

- W11.A closes `artifact_missing` for repo-owned universal outcome corpus.
- W11.B closes `artifact_missing` for per-case decomposition annotations.
- W11.C closes `artifact_missing` for expert adjudication labels.
- W11.D closes `consumer_missing` for fixture loaders and rotating fixtures.
- W11.E closes `verification_missing` for compilation truthfulness measurement.
- W11.F closes `verification_missing` for domain coverage breadth and critic ensemble diversity measurement.
- W11.G closes `producer_missing` for corpus-mode W12.D validation while explicitly marking the stub producer surface `surface_out_of_scope` for production authority.

**Negative tests:**

- a case file without raw source ref or redacted source hash cannot enter the corpus (W11.A);
- a case without claim decomposition annotation cannot be loaded by fixtures (W11.B);
- a structurally-complete case without expert adjudication label cannot count toward useful design (W11.C);
- a rotating fixture that appears in two consecutive evaluation rounds without rotation policy ack is rejected (W11.D);
- a compilation truthfulness report that does not separate true_positive / missed / hallucinated / scope_drift / authority_drift is invalid (W11.E);
- a critic ensemble diversity Jaccard below threshold triggers a warning that the ensemble has collapsed (W11.F).
- corpus-stub responses cannot be loaded as corpus cases and cannot authorize production closeout (W11.G).

**Exit gate:**

- corpus has at least 12 cases across at least 6 domains and 3 authority levels, repo-owned;
- annotations and adjudication labels exist for every case;
- fixture loaders and rotation policy exist;
- compilation truthfulness tool runs against W6/W7 outputs and reports per-case scores;
- domain coverage and critic diversity tools emit baseline metric values;
- corpus-stub responses exist for all universal outcome corpus cases with an explicit authority boundary;
- I11 outcome corpus first pass passes for at least three cases.

**Validation:**

```bash
uv run pytest tests/unit/corpus -q
uv run pytest tools/quality/validation/check_compilation_truthfulness.py --self-test
uv run pytest tools/quality/validation/check_domain_coverage_breadth.py --self-test
uv run pytest tools/quality/validation/check_critic_ensemble_diversity.py --self-test
uv run pytest tests/repo_quality/tools/test_outcome_corpus_first_pass.py -q
```

## Wave 12 - End-To-End Revalidation And Rollout

**Purpose:** prove that the compiled universal PDC path works locally and then
under the same one-lane cloud/debug conditions used by prior evidence-spine
work.

**Entry gate:** Wave 5 external surfaces and semantic tests accepted; Waves 6-11 capability gates passed; the original W6.A local validation ladder is re-executed in this wave because the gap it surfaced was conceptual, not local; rollout decision considers the three outcome metrics (closeout honesty + useful design + compilation truthfulness) separately.

**Parallel phases:**

#### W12.A Local Validation Ladder (Re-Execution Over Universal Compilation)

This phase re-executes the original W6.A local validation ladder over the new compiled universal PDC. The phase exists in Wave 12, not Wave 6, because the failure that surfaced during the original W6.A execution was conceptual (missing universal compilation layer), not local; therefore the ladder must run again against the post-W6-W11 system.

The phase owns local unit, repo-quality, semantic, local production-debug, and now universal-compilation-smoke commands. The deliverable is a green local quick path or narrow typed blockers with owners, command evidence, and next actions.

The phase reports the three outcome metrics separately: closeout honesty rate, useful design rate, and compilation truthfulness rate (the new metric from W11.E). Typed blockers and accepted deficits count toward honesty but never toward useful design; compilation truthfulness measures whether compiled obligations match expert-adjudicated annotations on the universal outcome corpus.

The executable owner remains `tools/quality/validation/run_policy_design_case_local_validation_ladder.py`, extended to also call W11.E/W11.F tools. The checked-in command contract lives at `architecture/policy_design_case/wave6_local_validation_ladder_manifest.json` (path preserved for shim compatibility; sunset date recorded once the universal capability is production-capable). Use `--profile quick` for a bounded smoke pass and `--profile full` for the phase closeout ladder.

#### W12.B Compilation Truthfulness Audit Run

This phase executes the W11.E compilation truthfulness tool against the universal outcome corpus (W11.A-C). The deliverable is a per-case truthfulness report (true_positive_obligations, missed_obligations, hallucinated_obligations, scope_drift_obligations, authority_drift_obligations, per_case_truthfulness_score) plus an aggregate compilation truthfulness rate.

A case scoring below the rollout-posture truthfulness floor is reported as a typed compilation blocker (not as useful design and not as a closeout-honesty failure).

#### W12.C Domain Coverage And Critic Diversity Audit Run

This phase executes the W11.F tools (domain coverage breadth, critic ensemble diversity, per-authority useful-design rate). The deliverable is a domain × authority-level matrix of useful-design outcomes and a critic-diversity Jaccard summary.

A committed domain slice with zero useful-design outcomes is reported as a typed domain-coverage blocker. A critic ensemble diversity below threshold is reported as a `critic_monoculture` warning that caps rollout at governed pilot or below.

#### W12.D Universal Outcome Corpus Run

This phase runs the universal compilation kernel (W6) and the producer pipeline (W7) on every case in the universal outcome corpus (W11.A) and records per-case outcome (pass / publish-with-limitation / accepted deficit / typed blocker), evidence-bound PDC graph (W8.A), expert adjudication delta (W11.C vs runtime output), and authority-level metric stratification.

This is the canonical evidence that the universal capability claim is real or honestly blocked. Real-producer mode remains the production-adjacent path and may block in synthetic environments when source infrastructure is absent. Corpus-stub mode is a governed-pilot validation mode only: it uses W11.G expert-derived stub responses to prove the compiler and producer bridge can produce useful design when admissible evidence is present, but it may not satisfy production closeout, claim-evidence authority, producer domain truth, or public projection authority.

#### W12.E Bundle, Replay, And Inspection

This phase owns canary evidence, replay, evidence-spine validation, handoff validation, closeout validators, and bundle inspection — same as the original W6.B. The deliverable is a bundle containing spine, handoff, claim registry, PDC graph (W8.A), argument graph (W8.B), conflict records (W8.E), effective-independence graph (W8.F), PDC projection, closeout, compatibility, rule refs, tuned config refs, source provenance, hypothesis ledger excerpts, and inspected artifact refs.

The phase must prove replay sees the same evidence graph as the live path. It also proves that bundle assembly, inspection, and readiness do not launder packaging summaries into producer authority.

Executable owner: `tools/quality/validation/run_policy_design_case_bundle_replay_inspection.py`; checked-in command contract: `architecture/policy_design_case/wave12e_bundle_replay_inspection_manifest.json`.

#### W12.F Cloud One-Lane Revalidation

This phase owns the canary matrix and cloud production-debug lane — same as the original W6.C. The deliverable is a cloud lane that passes or fails with typed blockers, no unknown-provenance collapse, and frozen revision/config evidence. It is the live proof that the universal architecture behaves under the deployment path used by prior evidence-spine work.

The phase must preserve all three outcome metrics. A cloud lane with high closeout honesty but low useful design rate or low compilation truthfulness rate cannot justify production-capable rollout.

Executable owner: `tools/quality/validation/run_policy_design_case_cloud_one_lane_revalidation.py`; checked-in command contract: `architecture/policy_design_case/wave12f_cloud_one_lane_revalidation_manifest.json`.

#### W12.G Rollout Decision

This phase owns feature flags, tuned configs, ADR amendments, backlog updates, and release notes. The deliverable is a promotion, partial rollout, hold, or next remediation plan with frozen revision/config and evidence. The decision must state whether PolicyOS is production-capable, governed-only, research-only, or held for next-plan remediation, and must cite all three outcome metric values per domain and per authority level.

The phase must name rollback and kill-switch behavior, useful-design floor results, compilation truthfulness floor results, domain coverage breadth, critic ensemble diversity, unresolved blockers, accepted tuned-parameter holds, and any domain slice deliberately excluded from production scope.

Executable owner: `tools/quality/validation/run_policy_design_case_rollout_decision.py`; checked-in command contract: `architecture/policy_design_case/wave12g_rollout_decision_manifest.json`.

**Parallelism contract:** W12.A-F can run in parallel over the same frozen revision, scenario inputs, feature flags, and tuned config. W12.G consumes their outputs only at the wave exit.

**Required validation ladder:**

Canonical W12.A runner (kept as `W6.A runner` path for shim compatibility; sunset recorded in `architecture/shims.toml`):

```bash
uv run python tools/quality/validation/run_policy_design_case_local_validation_ladder.py \
  --repo-root . \
  --profile full \
  --output _build/.tmp/production-quality/universal_pdc_local_validation_ladder.json
```

The runner owns the command evidence and typed-blocker classification. The raw
commands below remain listed for transparency and targeted reruns:

```bash
uv run pytest tests/unit/runtime/quality tests/unit/scientist tests/unit/lex tests/unit/fabric tests/unit/foundry -q
uv run pytest tests/repo_quality/tools/test_evidence_bundle_inspection.py tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py -q
uv run pytest tests/repo_quality/tools/test_policy_design_case_public_export.py tests/repo_quality/tools/test_docs_lifecycle.py tests/repo_quality/tools/test_docs_gate.py -q
```

Local production-debug path:

```bash
uv run --extra runtime --extra multi-tenant --extra ml python tools/quality/testing/local_prod_debug_probe.py \
  --repo-root . \
  --checks quick,production-data-static,docs-repro \
  --output _build/.tmp/production-quality/universal_pdc_local_quick.json
```

Cloud one-lane path:

```bash
uv run python tools/ops_runners/runtime/run_canary_matrix.py \
  --deterministic \
  --only-lane profile-research__provider-live_gonka_proxy__data-canonical_production__scenario-public_golden__ui-api_only \
  --json-output _build/.tmp/production-quality/universal_pdc_final_live_research_lane.json \
  --timeout-s 1200
```

Inspection and readiness:

```bash
uv run python tools/quality/validation/inspect_evidence_bundles.py \
  --repo-root . \
  --matrix-run-json _build/.tmp/production-quality/universal_pdc_final_live_research_lane.json \
  --json-output _build/.tmp/production-quality/universal_pdc_final_evidence_bundle_inspection.json

uv run python tools/ci/check_policyos_production_quality_best_in_class.py \
  --repo-root . \
  --matrix-run-json _build/.tmp/production-quality/universal_pdc_final_live_research_lane.json \
  --output _build/.tmp/production-quality/universal_pdc_final_readiness.json \
  --output-format json
```

**Exit gate:**

- every remaining failure is classified as remediated, typed blocker, accepted next-plan item, or false alarm;
- universal outcome corpus results are recorded separately from plan-hygiene completion;
- all three outcome metrics are reported separately: closeout honesty rate (typed blockers and accepted deficits count toward honesty but not capability); useful design rate (only pass and publish-with-limitation count); compilation truthfulness rate (per-case W11.E score and aggregate);
- rollout posture is capped at research-only or governed pilot if any of these floors are not met: useful design floor per declared posture; compilation truthfulness floor per declared posture; per-domain useful design floor; per-authority-level useful design floor; critic ensemble diversity floor;
- release evidence records the exact git revision, build/config identity, feature flags, tuned config versions, command set, and artifacts inspected;
- canary promotion has explicit accept/abort criteria and rollback/kill-switch path;
- no public/dashboard/API projection promotes failed claims, missing record families, packaging-only authority, LLM speculation, hypothesis ledger candidates marked `candidate_unverified`, or historical priors;
- feature flags and tuned configs have named owners and rollback paths;
- rollout decision is captured as an ADR or release note and cites all three metrics, per-domain and per-authority-level stratification, critic ensemble diversity, and any domain slice deliberately excluded from production scope.

## Feature Flags And Tuned Config

The exact names should follow existing runtime conventions. The plan requires
these rollout controls.

| Control | Applies to | Initial posture |
| --- | --- | --- |
| Universal PDC projection | E4/E5, W8.A graph | Feature flag until public/export truth tests pass and projection consumes W8.A graph. |
| Effective-independence graded weights | E13, W8.F | Feature flag plus governed config; strict hard-collapse can ship first. |
| Acquisition planner commit | E17, W7.G | Advisory/recommendation mode until ADR-0166 and human/governed commit path land. |
| Review-effectiveness consequences | E19, W10.B | Advisory only until longitudinal evidence supports gates. |
| Calibration blocking | E20 | Warning/review mode until mature-history thresholds are met. |
| Complexity budget closeout effect | E19, W10.E | Advisory for existing runs; gate only growth of new controls at first; complexity governance itself is on the retire list if it stops causing prune decisions. |
| Participation thresholds | E4/E11/E22, W7.E | Governed config; matrix structure is fixed, numeric thresholds are provisional. |
| Rare-domain scarcity path | E13/E22, W8.F | Explicit deficit and public limitation; no support inflation; `scarcity_structural` vs `scarcity_remediable` split is structural commitment, never tuned. |
| Run-cost and degradation thresholds | E18, W10.D | Warning/limitation first; hard block only by authority-level policy. |
| Legal fallback tables | E9, W7.B | Governed namespace config; no universal hardcoded fallback. |
| DataRequirement family fallback from hardcoded heuristics | W7.A | Feature flag `data_requirement_family_fallback_from_hardcoded`; initial value true only as a sunset shim. Disable once W6.B vertical data-family rules cover the corpus-derived families. |
| Universal grammar facet vocabulary | W6.A | Governed; new facets allowed only with saturation evidence from W11.B annotations. |
| Governed obligation rule catalog | W6.B | Governed; rule promotion requires owner, version, scope, authority level, evidence basis, and W11.B annotation alignment. |
| Obligation candidate ledger ceilings | W6.C | Governed; source ceilings per C38 default (`governed_rule` -> mandatory; `llm_candidate` -> candidate; `LLM_CRITIC_CONSENSUS` -> `REVIEW_REQUIRED`). |
| Obligation blocking frontier complexity budget | W6.C, W10.E | Net-MAV-gated; new control entering frontier must declare expected Net-MAV. |
| LLM formulator + critic ensemble enabled | W6.E | Feature flag for formulator; critic ensemble starts advisory; promotion gated by W11.F critic diversity floor. |
| Hypothesis ledger firewall enforcement | W6.F | Always-on for production authority; advisory for research authority until W12 corpus run baseline. |
| RequirementSpec compilers (data/legal/method/scholar/participation) | W7.A-E | Feature flag per compiler family until refactored adapter consumer contract verification passes. |
| Producer pipeline 8-stage execution | W7.F | Feature flag until C40 producer-state liveness invariants in W10.A cover all transitions. |
| Drift detector activation per family | W9.A | Feature flag per detector; sparse-history policy applies before any gating consequence. |
| Memory decay TTL and contamination policy | W9.D | Governed config; default TTL and decay shape provisional, validated through W11 corpus. |
| Rule replay engine mandatory revalidation triggers | W9.F | Governed per change class per C33; advisory until W12 corpus exercises every change class. |
| Compilation truthfulness floor per rollout posture | W11.E, W12.B | Provisional governed default; e.g. production-capable requires ≥ 70 truthfulness on every committed domain slice and ≥ 80 aggregate. |
| Domain coverage breadth floor | W11.F, W12.C | Provisional governed default; production-capable requires ≥ 1 useful-design case in each committed domain. |
| Critic ensemble diversity floor | W11.F, W12.C | Provisional governed default; below floor caps rollout posture at governed pilot. |

Every tuned config must carry:

- owner;
- version;
- default source;
- status: `provisional`, `validated`, `deprecated`, or `withdrawn`;
- feature/advisory posture;
- evidence required for promotion;
- rollback path;
- kill-switch or safe-disable behavior where runtime-facing;
- telemetry used to evaluate rollout health;
- sunset, cleanup, or revalidation condition;
- public notice/revalidation effect if applicable.

## Cross-Wave Validation Rules

These checks apply after every wave.

- No artifact produced for projection, dashboard, public export, replay, inspection, or diagnostics may satisfy producer authority.
- No LLM output may enter legal, data, method, participation, or closeout authority slots without producer/reader validation. After Wave 6, this means every LLM candidate must be persisted in the hypothesis ledger with source classification, prompt fingerprint, tool refs, and repair-decision lineage, and must remain `candidate_unverified` until producer admission.
- No historical prior may close or refute current-run claims. After Wave 9, memory entries past TTL cannot influence current run; revoked-scope entries cannot influence current run.
- No raw evidence count may be reported without effective-independence status. After Wave 8, effective independence reports the C29 graded calculus output (hard collapse + partial bands); `scarcity_structural` cases never inflate.
- No `status=pass` may hide missing records, missing record families, missing claim axes, unresolved concepts, or reader-visible blockers. After Wave 6, `status=pass` cannot exist while the obligation graph blocking frontier is non-empty.
- No tuned parameter may be represented as final unless the ADR names the corpus, calibration evidence, owner, and revision rule. After Wave 10, complexity governance pruning enforces this for any new control entering the blocking frontier.
- No bridge record may serve as producer evidence; it can testify only to the boundary it owns. After Wave 7, the producer pipeline orchestrator enforces this through the C40 ten-state machine and bridge-class table (transport carrier / handoff ledger / binding assertion / producer attestation / reader attestation / diagnostic projection / closeout evidence).
- No capability can move to `implemented` while `semantic_test_missing` remains. After Wave 11, semantic-test sufficiency means expert-adjudication coverage on at least one universal outcome corpus case per capability claim.
- No public/API contract may be considered complete until at least one consumer verification path checks both schema compatibility and semantic preservation. After Wave 8, projection consumer contracts must verify projection-from-W8.A-graph rather than from scattered runtime fields.
- No feature flag may ship without owner, telemetry, rollback, and cleanup or revalidation condition.
- No release/canary evidence may omit git revision, config versions, feature flag states, command evidence, or inspected artifact refs.
- No requirement compiler (W7.A-E) may emit selected/rejected/blocked bindings that exceed the obligation graph blocking frontier (W6.C) — the bridge between producer and obligation budget must hold.
- No detector (W9.A) may emit blocking consequences during sparse-history sparse-history bands (`Insufficient` / `Thin`) — only warning, uncertainty widening, or extra evidence.
- No PDC graph (W8.A) emitted by Wave 8 onward may serve as projection without going through W4.E/W5.A projection backend; graph authority and projection authority remain distinct.
- No compilation truthfulness, domain coverage, or critic diversity metric may be reported without per-domain and per-authority-level stratification after Wave 11.

Validation commands in this plan may reference tests or tools that are created
by the wave itself. Until they exist, the phase must record them as
`to_be_created` with owner and expected path. A wave cannot exit by silently
dropping a planned test; it must either create it, replace it with a stronger
existing check, or record an explicit hold.

## Wave Transition Manifests

At every wave exit, produce a short manifest with:

- wave id and git revision;
- research coverage rows closed or still open;
- completed phases and owners;
- artifacts produced;
- capability states closed and remaining;
- anti-patterns closed and risks introduced;
- tuned configs added or changed;
- feature flags added or changed;
- tests run and command evidence;
- external contract checks run and consumer surfaces covered;
- blockers deferred to next wave;
- rollback notes.

The manifest may live in `_build/.tmp/` during work, but the accepted summary
must be linked from the relevant backlog, ADR, or implementation closeout note.

## Replanning Cadence And Cross-Plan Coordination

The plan is intentionally sequenced, but it is not immutable. Every wave exit
includes an explicit replanning checkpoint:

- update the critical path and phase sizes from actual work;
- promote, split, merge, or retire phases based on integration findings;
- update the risk register and capability debt snapshot;
- update feature-flag and tuned-config posture;
- mark planned tests as created, replaced, or held;
- confirm that all future waves still consume real artifacts, not obsolete
  assumptions from the original plan.

Cross-plan coordination is mandatory before touching shared producer areas:

| Shared area | Coordination requirement |
| --- | --- |
| `src/polisyos/lex/*` | Check active Lex/legal authority plans and agree on normpack/schema ownership. W7.B refactor must coordinate with any existing Lex initiative. |
| `src/polisyos/fabric/*` | Check Fabric source-contract plans and avoid competing contract models. W7.A refactor must coordinate with any existing Fabric initiative. |
| `src/polisyos/foundry/*` | Check Foundry method/uncertainty plans before changing method selection or validity gates. W7.C refactor must coordinate. W8.D Pareto frontier emitter must coordinate with Foundry welfare modules. |
| `src/polisyos/scientist/*` | Check Scientist claim, workflow, memory, and publication plans before changing claim lifecycle or exports. W6.D, W6.E, W7.G, W8.C, W9.D all write under this tree and must coordinate. |
| `src/polisyos/runtime/quality/*` | Maintain a shared runtime-quality interface note before parallel phase writes. W6.F, W7.F, W8.B, W9.F, W10.A, W10.D, W10.E, W10.F all write under this tree. |
| `src/polisyos/policy_grammar/`, `src/polisyos/obligation_rules/`, `src/polisyos/obligation_graph/` | New modules introduced in Wave 6; coordinate with future plans that propose alternative grammar/rule/obligation models. |
| `src/polisyos/data_requirement/`, `src/polisyos/legal_requirement/`, `src/polisyos/method_requirement/`, `src/polisyos/scholar_requirement/`, `src/polisyos/participation_requirement/` | New per-family requirement compiler modules introduced in Wave 7; coordinate with producer-adapter plans. |
| `src/polisyos/pdc/` | New module introduced in Wave 8 for `RuntimePolicyDesignCase` graph compiler; coordinate with any future PDC reorganisation. |
| `src/polisyos/evidence/portfolio/` | Wave 8 conflict materializer and effective independence graph annotator extend this tree; coordinate with existing portfolio plans. |
| `src/polisyos/scientist/governance/continuous/detectors/` | New subtree introduced in Wave 9; coordinate with continuous governance plans. |
| `src/polisyos/data_forge/` | Wave 9 provenance manifest extends snapshot/release surfaces; coordinate with Data Forge initiatives. |
| `src/polisyos/foundry/welfare/` | Wave 8 frontier emitter and social-weight provenance extend this tree. |
| `src/polisyos/scientist/evals/` | Wave 10 adversarial probes extend challenge_factory; coordinate with evaluation plan. |
| `src/polisyos/corpus/`, `docs/research/universal-policy-design/outcome-corpus/`, `tests/fixtures/universal-corpus/` | New corpus surfaces introduced in Wave 11; coordinate with research plan corpus track. |
| `tools/quality/*`, `tools/ci/*`, `tools/ops_runners/*` | Coordinate validation output paths and schema expectations. W11.E/W11.F new tools must align with existing validation tooling. |

Each wave transition manifest must record cross-plan conflicts discovered,
resolved, or deferred. This is part of P06 and P13 control, not paperwork.

## Ownership And Write-Scope Discipline

Parallel phases should avoid overlapping write ownership where possible:

- runtime quality substrate: `src/polisyos/runtime/quality/*`;
- runtime orchestration: `src/polisyos/runtime/http/services/control/*`;
- Lex adapter: `src/polisyos/lex/*`;
- Fabric adapter: `src/polisyos/fabric/*`;
- Scholar adapter: `src/polisyos/scholar/*`;
- Foundry adapter: `src/polisyos/foundry/*`;
- Scientist validation/claims: `src/polisyos/scientist/*`;
- Data Forge binding: `src/polisyos/data_forge/*`;
- repo-quality tools: `tools/quality/*`, `tools/ci/*`,
  `tools/ops_runners/runtime/*`;
- docs and ADRs: `docs/system-design-decisions/*`, `docs/runbooks/*`,
  `docs/reference/*`, `docs/plans/active/*`.

If two phases need the same file family in the same wave, they must define a
shared interface at wave start or move one side to the next wave.

## Rollback And Failure Handling

Each wave may fail in three acceptable ways:

- **Typed blocker:** implementation proves a necessary upstream artifact is
  absent or semantically wrong. The blocker is recorded with owner and next
  action.
- **Accepted hold:** tuned thresholds or external institution-owned decisions
  are not mature enough. Feature remains advisory or behind flag.
- **Remediation plan:** a real engineering gap is found and assigned to the
  next wave or a new bounded remediation plan.

Unacceptable failures:

- silently treating projection, LLM output, bridge record, or historical prior
  as authority;
- changing public truth without a typed projection gap or omission manifest;
- adding gates without owner, telemetry, and marginal value statement;
- declaring capability complete while a capability reality label is still open.

## Completion Definition

The plan distinguishes **plan execution complete** from **universal capability
achieved**.

Plan execution is complete when:

- Wave 0 ADRs are ratified and linked from this plan;
- every C0-C41 research decision has either an implemented traceability row, an accepted tuned-parameter hold, or an explicit deployment/institution-owned boundary;
- every E0-E24 task is implemented, explicitly held behind feature/advisory mode, or replaced by a documented superior reuse path;
- every P01-P15 anti-pattern has either a closure test or a documented residual risk owner;
- every L0-L11 layer from synthesis has at least one Wave 6-12 phase owning it (no layer remains as concept-only after the plan is executed);
- the six new compilation capabilities (universal grammar compiler, governed obligation rule catalog, obligation graph compiler with three-tier ledger, claim decomposition compiler with baselines, LLM formulator + critic ensemble, hypothesis ledger + firewall) are `implemented` per the capability reality formula;
- the five RequirementSpec compilers and refactored adapters (data, legal, method, scholar, participation) are `implemented`;
- the 8-stage producer pipeline orchestrator covers the C40 ten-state machine for every producer family;
- the PDC graph compiler emits typed `RuntimePolicyDesignCase` graphs distinct from projection, and projection backends consume the graph as source of truth;
- argument/warrant graph, baseline/alternative comparison, Pareto frontier with social-weight provenance, first-class conflict records, and graded effective-independence graph are all `implemented`;
- drift detectors, partial-scope reissue, Data Forge provenance manifest, memory decay, lifecycle bridge, and rule replay engine are all `implemented`;
- temporal/liveness invariants, review-effectiveness pipeline, three missing R14 probes, cost enforcement gates, complexity governance pruning, and repair-decision FMEA are all `implemented`;
- universal outcome corpus exists repo-owned with annotations and expert adjudication, plus compilation truthfulness, domain coverage, and critic diversity tools;
- feature flags and tuned parameters have owners, versions, rollback paths, and validation evidence;
- local and cloud validation produce either a passing universal PDC path or narrow typed blockers, with three outcome metrics reported separately;
- public, reviewer, expert, machine, dashboard, and audit surfaces preserve the same closeout truth and consume the W8.A graph;
- the final rollout decision is recorded with command evidence and cites all three outcome metrics stratified per domain and per authority level.

Universal capability is achieved only when:

- the universal outcome corpus has been run and published under repo-owned command evidence;
- each committed domain slice has at least one useful design outcome: pass or publish-with-limitation;
- the universal outcome corpus meets the useful-design floor for the declared rollout posture;
- the universal outcome corpus meets the compilation truthfulness floor for the declared rollout posture (per W11.E aggregate score and per-domain stratification);
- the universal outcome corpus meets the domain coverage breadth and critic ensemble diversity floors for the declared rollout posture (per W11.F);
- no case in the outcome corpus passes through projection, LLM, bridge, packaging, historical-prior, raw-count, hypothesis-ledger-unverified, or scarcity-inflation laundering;
- typed blockers and accepted deficits are reported as honest non-capability outcomes, not counted as useful design;
- semantic false-pass findings are either remediated, converted into typed blockers/limitations, or accepted as hidden benchmark items with owners;
- the universal grammar compiler emits non-trivial typed facets, the obligation graph compiler emits non-empty bundles and blocking frontier, the claim decomposition compiler emits typed claim families with baselines, the LLM formulator + critic ensemble produces structured candidates with diversity above floor, and the hypothesis ledger firewall blocks every synthetic laundering case — across every committed domain;
- the rollout decision states whether PolicyOS is production-capable, governed-only, research-only, or held for next-plan remediation, and cites all three outcome metrics per domain and per authority level.

Typed blockers are valuable evidence, but they do not by themselves prove the universal system exists. They prove that the system can fail honestly. Compilation truthfulness above floor across diverse domains is what proves the universal system actually compiles policy design from any intent into a typed claim-bound evidence graph.
