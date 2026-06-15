---
title: Parallel Deep Research Backlog
status: active
owner: team-policyos-research
created: 2026-06-14
last_verified: 2026-06-14
stability: draft
parallel_execution: required
implementation_scope: research_only
source_scope:
  - docs/plans/active/SCIENTIST_BEST_IN_CLASS_PLAN.md#8-wave-r---research-first-companion-agenda
  - docs/plans/active/FABRIC_BEST_IN_CLASS_PLAN.md#9-wave-r--fabric-research-agenda
  - docs/plans/archive/FOUNDRY_METHODS_RESEARCH_AGENDA.md#phase-6
  - brainstormed-cross-cutting-public-authority-gaps-2026-06-14
context_scope:
  - docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
  - docs/system-design-decisions/universal-policy-design-target-architecture-and-gap.md
  - docs/system-design-decisions/policy-design-best-in-class-operating-model.md
  - docs/system-design-decisions/honest-diagnostics-substrate.md
---

# Parallel Deep Research Backlog

This document is the dispatch packet for the next fully parallel deep-research
batch. Every task below must be executable by a different researcher without
waiting for any other task. This intentionally accepts overlap, duplicate local
abstractions, and temporary producer/consumer mismatch. Consolidation, conflict
resolution, best-solution selection, and engineering implementation happen
later.

No task in this file creates runtime authority, code contracts, or repository
implementation work. Pseudocode, typed artifact sketches, reference algorithms,
mathematical derivations, benchmark protocols, and fixture proposals are allowed
inside the research artifact. Direct edits to product code are out of scope for
this batch.

## Project Context For Every Researcher

PolicyOS is not a chat assistant that writes attractive policy memos. It is a
runtime for public-policy design authority: the system must prove why a
recommendation, limitation, abstention, warning, or publication state is
`admissible`, `limited`, `contested`, `blocked`, or `publishable`. Fluency,
plausibility, or a generated answer is never authority. LLM output, generated
search frontiers, synthesized literature notes, and exploratory engine runs are
candidates until grounded by typed producers, evidence contracts, adapters,
verification, and authority boundaries.

The Universal Policy Design architecture is B-on-A. A is the grounding and
authority backbone: verification, firewalls, evidence binding, calibration,
certified operation envelopes, replay, accountability, and release gates. B is
the generative designer: grammar-derived candidates, search, composition, LLM
proposals, and exploratory Foundry/Fabric/Scientist runs. A leads B. Search
discovers, adapters discipline, and the authority gate admits. Any research that
increases B's power must also name the additional obligation it creates for A.

The core architectural invariant is the narrow waist. `src/polisyos/pdc` carries
the small set of typed authority contracts. `src/polisyos/runtime/quality` is
the adapter and grounding ring allowed to import engines and downgrade their
outputs into port-conformant authority records. Engines such as `foundry`,
`fabric`, and `scientist` remain engines; their raw outputs never satisfy an
authority slot. A safe research result should therefore describe how a later
implementation would enter through a typed port, carry an `AuthorityBoundary`,
fail closed when grounding is absent, and remain out-of-envelope when untested.

The serious-run product is a Policy Design Case: a runtime-owned, CAS-addressed
assurance case connecting policy intent, concept spine, legal authority, data
sources, academic and grey-literature evidence, method selection, assumptions,
uncertainty, options, tradeoffs, final claims, governance, publication,
contestability, lifecycle, ex-post outcomes, and calibration. A claim is not
supported because it lists references. It is supported only when the case can
explain why the evidence supports the claim, under which assumptions, against
which rebuttals, with which residual deficits, and with which authority
boundary.

The honest diagnostics substrate is the closeout authority. Every serious
evidence chain must answer: who owned the evidence, what runtime event produced
it, which CAS artifact stores it, what mode/fallback/input/schema/tenant/time
context shaped it, and which downstream gate consumed it. Dashboards,
readiness views, exports, and bundles may project authority; they may not mint
it. Unknown provenance, fallback, stale evidence, schema mismatch, projection
substitution, fixture-only evidence, or missing same-input closure must become a
typed blocker, limitation, or non-production exception rather than a silent pass.

Research must respect the reuse-first operating model. Much of the advanced
machinery already exists in `src/polisyos`: Scientist evidence and governance,
Fabric data and provenance, Foundry methods and uncertainty, IR analytics,
runtime quality, DDM monitoring, core audit, Scholar, Lex, and Data Forge. The
default posture is `wire-existing`, then `extend-existing`, then
`consolidate-existing`, and only then `build-new`. A good research report starts
by finding what already exists and naming the missing capability link precisely.

## Scope Assumptions

- Scientist Wave R is included because no Scientist research pass has been
  performed yet.
- Fabric Wave R is included because no Fabric research pass has been performed
  yet.
- Foundry starts at Phase 6 inclusive because Phases 0-5 were researched and
  partially implemented, while Phase 6 was not started.
- Foundry Phase 6 source text says "15 concurrent" but lists `P6.01` through
  `P6.17`. This backlog preserves the listed IDs, so Foundry contributes 90
  tasks across Phase 6 through Phase 11.
- Cross-Cutting Public Authority tasks are newly added research directions. They
  cover the public-sector authority wrapper around PolicyOS: mandate,
  participation, implementation capacity, procurement, transparency, incidents,
  redress, agentic oversight, living evidence, construct validity, and
  regulatory obligation grammar.

Task counts:

| Area | Included IDs | Count |
| --- | --- | ---: |
| Cross-Cutting Public Authority | `CPA-R1` through `CPA-R28` | 28 |
| Scientist | `SCI-R0` through `SCI-R10` | 11 |
| Fabric | `FAB-R1` through `FAB-R10` | 10 |
| Foundry | `P6.01` through `P11.15` | 90 |
| Total | - | 139 |

## Parallel Execution Protocol

Every task below is a standalone prompt. Treat your task as if every other task
is being researched at the same time by someone who cannot coordinate with you.
Do not depend on another task's future result. If your design needs a producer,
consumer, schema, benchmark, or authority rule that another task might also
define, create a local candidate and mark it as `external_dependency_assumption`
or `candidate_for_consolidation`, not as canonical project truth.

Duplicate invention is acceptable. Silent coupling is not. If you propose a
producer and also need a consumer, name both, but do not claim the full
capability is implemented or solved. If your result would be better with a
smarter upstream producer or downstream consumer, describe the interface you
would want, then provide a conservative fallback that remains honest without it.

Each report must be mergeable later. Prefer small named concepts, explicit
status lattices, artifact shapes, proof obligations, and fixture packs over
large narrative frameworks. When alternatives are plausible, present the tradeoff
and choose a recommended narrow default, but keep the rejected options and their
failure modes visible.

## Mandatory Repo Baseline Study

Before doing external research or proposing a new abstraction, each researcher
must inspect the existing repository context and cite the files they inspected.
At minimum:

- Read the project operating rules: `AGENTS.md`,
  `policy-engine/CONTRIBUTING.md`, and the relevant source plan named in the
  task section.
- Read the architectural context:
  `docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md`,
  `docs/system-design-decisions/universal-policy-design-target-architecture-and-gap.md`,
  `docs/system-design-decisions/policy-design-best-in-class-operating-model.md`,
  and `docs/system-design-decisions/honest-diagnostics-substrate.md`.
- Read the failure-pattern register:
  `docs/reference/policy-design-case-failure-patterns.md`.
- Inspect the relevant `docs/reference/<area>/` directory, `src/polisyos/<area>/`
  modules, and related `tests/` fixtures before claiming that something is
  absent.
- Use repository search (`rg`) to find existing names, artifacts, tests, and
  docs. If the repo has no relevant owner, say so explicitly and name the
  missing capability label.

The completed research artifact must include a `current_repo_baseline` section
with:

- inspected paths and important existing primitives;
- current capability state using one of the missing-state labels;
- likely producer, artifact/event, orchestration bridge, consumer, verification,
  and surface;
- existing tests/fixtures that can be reused;
- repo gaps that are research blockers versus engineering blockers.

## Research Quality Bar

The standard is highest-quality research, not implementation planning. A report
should be strong enough that a later engineering plan can decide whether to
prototype, govern, block, or defer the capability without redoing the research.

Required quality properties:

- Prefer primary sources, formal definitions, public standards, canonical
  papers, benchmark suites, or well-established libraries. Use secondary sources
  only to orient, not as final authority.
- Separate theorem, empirical rule, design pattern, benchmark protocol,
  impossibility result, and engineering convenience. Do not present a convenient
  contract as a proven method.
- Include at least one counterexample or adversarial case that would falsify an
  unsafe implementation.
- Include a benchmark proxy, fixture design, sealed/hidden eval plan, replay
  scenario, or human-review packet that could later become a semantic test.
- Preserve authority boundaries: every candidate result must declare
  `authoritative_for` and `may_not_use_for` or explain why it remains
  `research_only`.
- Treat time, provenance, status, rule/schema version, audience, uncertainty,
  and scope as load-bearing fields.
- Report negative findings. A valid result can be `confirmed`, `accepted_narrow_scope`,
  `refuted`, `blocked`, or `deferred_open_problem`.
- Do not turn unresolved research questions into code contracts.

## Unified Deliverable Form

Each deep research task should produce one self-contained research bundle using
this structure:

```text
# <Task ID> - <Short Title>

## 1. Task And Project Fit
Source task, exact research question, why this is research-first, and what false
production claim the research prevents.

## 2. Current Repo Baseline
Files inspected, existing primitives, existing docs/tests/fixtures, current
capability label, and the smallest reuse-first integration path visible today.

## 3. External Research Baseline
Primary sources, canonical papers/standards/libraries, competing approaches,
known limitations, and relevance to public-policy settings.

## 4. Result
The theorem, rulebook, protocol, benchmark, impossibility result, accepted
narrow-scope design, or refutation. Include assumptions and unsupported scope.

## 5. Counterexamples And Failure Modes
At least one adversarial or boundary case; include what an unsafe implementation
would incorrectly conclude.

## 6. Benchmark Or Fixture Proposal
Synthetic data, frozen fixtures, hidden eval, replay scenario, human-review
packet, or parity test that can later become a semantic/e2e test.

## 7. Artifact Contract Sketch
Typed artifact shape, status lattice, authority boundary, provenance, time
semantics, version/rule refs, and pseudocode/reference implementation if useful.

## 8. Later Integration Handoff
Producer, persisted artifact/event, bridge, consumer, verification, and
audit/API/dashboard/public surface a later implementation would wire.

## 9. Promotion And Kill Rules
Conditions for `research_only`, `prototype_allowed`, `governed_allowed`,
`production_candidate`, `blocked`, or `out_of_scope`.

## 10. Open Questions For Consolidation
Conflicts with likely parallel tasks, duplicate abstractions, unresolved
dependencies, and recommended consolidation owner.
```

Suggested file naming for completed research artifacts:

```text
docs/research/<area>/<task-id>-<short-slug>.md
```

For larger results, use the handoff structure in
`docs/reference/research-track-handoff-template.md`.

## Area Inspection Anchors

| Area | Required repo anchors before research |
| --- | --- |
| Shared authority / PDC | `src/polisyos/pdc`, `src/polisyos/runtime/quality`, `src/polisyos/core/audit`, `src/polisyos/ir`, `tests/fixtures/policy_design_case`, `tests/fixtures/runtime_quality`, `docs/reference/public-surface.md`, `docs/reference/generated-artifacts.md`. |
| Cross-Cutting Public Authority | `src/polisyos/pdc`, `src/polisyos/runtime/quality`, `src/polisyos/core/audit`, `src/polisyos/lex`, `src/polisyos/participation_requirement`, `src/polisyos/obligation_graph`, `src/polisyos/obligation_rules`, `src/polisyos/ddm`, `docs/system-design-decisions`, `docs/reference/policy-design-case-*`, `tests/fixtures/policy_design_case`, `tests/fixtures/runtime_quality`. |
| Scientist | `docs/reference/scientist`, `src/polisyos/scientist`, `src/polisyos/evidence`, `src/polisyos/scholar`, `src/polisyos/ddm`, `tests/unit/scientist`, `tests/integration/scientist`, `tests/property/scientist`, `tests/_data/scientist`, `tests/_golden/quality/citation_faithfulness`. |
| Fabric | `docs/reference/fabric`, `src/polisyos/fabric`, `src/polisyos/data_forge`, `src/polisyos/core/discovery`, `tests/unit/fabric`, `tests/property/fabric`, `tests/integration/fabric_ir`, `tests/_data/fabric`, `tests/_data/data_forge`. |
| Foundry | `docs/reference/foundry`, `src/polisyos/foundry`, `src/polisyos/calibration`, `src/polisyos/ir/analytics`, `tests/unit/foundry`, `tests/property/foundry`, `tests/integration/foundry_calibration`, `tests/integration/foundry_scientist`, `tests/_golden/foundry`. |

## Pattern Pass

Relevant failure-pattern IDs: `P01`, `P02`, `P03`, `P04`, `P05`, `P07`, `P08`,
`P09`, `P10`, `P13`, `P14`, `P15`, plus `P16-P26` where a task touches
universal policy-design authority.

Known anti-pattern risk:

- `P01`: producing a research note or typed contract without producer, consumer,
  verification, and surface.
- `P05` / `P15`: letting LLM or research candidate content become authority.
- `P10`: accepting structural completeness instead of semantic adequacy.
- `P13`: growing a governance ritual that is not proportional to the decision.
- `P14`: inflating evidence strength by raw source count.

Target correct pattern:

- Every research task produces a research-only bundle with explicit assumptions,
  counterexamples, benchmark proxy, integration target, promotion conditions,
  and authority boundary.
- Research artifacts are `proof_only` / `research_only` until a later
  implementation plan wires the capability chain.
- Pseudocode, reference implementations, mathematical sketches, and fixture
  specs are allowed inside the research artifact. Direct repository code
  changes are out of scope for this research batch.

Missing capability labels before implementation:

- Default: `implemented_but_not_orchestrated` if a local primitive exists but
  needs promotion semantics.
- Default: `verification_missing` when the research result lacks a deterministic
  benchmark proxy or counterexample pack.
- Default: `semantic_test_missing` when only schema/field shape is tested.
- Default: `surface_missing` when no API, audit, dashboard, docs, or Trust View
  surface can inspect the result.

Acceptance signal for a completed research task:

- The completed research artifact can answer: "What would be safe to implement,
  what remains research-only, what should be blocked, and what fixture would
  falsify an overclaim?"

## Priority Heuristic

This is not a binding schedule, but it is a useful first ordering:

1. Fabric `FAB-R3`, because it is explicitly `blocked_by_research` for temporal
   graph reasoning.
2. Scientist `SCI-R0`, `SCI-R1`, `SCI-R2`, because later Scientist research
   needs track cards, support semantics, and citation faithfulness.
3. Foundry Phase 6, because it is the first unstarted Foundry phase and feeds
   Phase 7 privacy/federation and later online/adaptive work.
4. Fabric `FAB-R1`, `FAB-R2`, `FAB-R7`, because they affect trust,
   uncertainty, and semantic schema governance.
5. Scientist `SCI-R3`, `SCI-R4`, `SCI-R6`, because evidence quality, VOI, and
   leakage determine whether agentic research can be trusted.
6. Cross-Cutting Public Authority `CPA-R1`, `CPA-R6`, `CPA-R10`, `CPA-R14`,
   `CPA-R18`, `CPA-R22`, and `CPA-R28`, because these decide whether technical
   authority can survive contact with public-sector mandate, delivery,
   procurement, transparency, incidents, agents, and regulation.

## Task Formulation Adequacy Review

Reviewed for parallel dispatch on 2026-06-14.

Adequacy rubric: a task is detailed enough when an independent researcher can
identify the unsafe production claim being prevented, the technical object being
studied, the authority or readiness effect, the minimum research artifact, a
falsifier or benchmark proxy, and the later integration boundary without asking
for sequencing context from another task.

Overall result:

- Scientist tasks are sufficiently specific for parallel dispatch. They have a
  clear evidence/governance object, expected output, falsifier, and integration
  target.
- Fabric tasks are sufficiently specific for parallel dispatch. They separate
  data quality, source trust, lineage, temporal semantics, entity resolution,
  processing guarantees, schema drift, adversarial ingestion, privacy, and
  replay.
- Cross-Cutting Public Authority tasks are intentionally governance-heavy, but
  each row names a concrete authority object, public-sector failure mode,
  benchmark proxy, and later integration target.
- Foundry Phase 6 through Phase 10 tasks are mostly sufficient as method-family
  research prompts. Their main risk is not ambiguity of problem, but insufficient
  task-specific benchmark detail; the deliverable form therefore requires each
  researcher to add a benchmark or falsifier even when the row does not name one.
- Foundry Phase 11 contains several intentionally composite tasks. They must be
  read as dispatch/composition research, not as "build one giant method"; the
  task rows below state the required narrow interpretation directly.

Minimum interpretation rule for every row:

- The research question defines the problem, not the solution.
- The minimum required output defines the smallest acceptable artifact; richer
  results are allowed only if they preserve the same authority boundary.
- The later integration target is a handoff hint, not permission to implement or
  to treat the result as runtime authority.
- If a row admits two plausible interpretations, the report must include both,
  choose a narrow primary interpretation, and mark the other as
  `candidate_for_consolidation`.

## Cross-Cutting Public Authority Tasks

Source: 2026-06-14 public-authority gap brainstorm, informed by PolicyOS system
design decisions and external public-sector AI governance anchors such as NIST
AI RMF, EU AI Act, OMB M-25-21, UK Algorithmic Transparency Recording Standard,
OECD Governing with AI, OECD AI Incidents Monitor, and the AI Incident Database.

Execution clause for every `CPA-*` row:

- Treat the row as an independent public-authority research prompt that may
  consume Scientist, Fabric, Foundry, Lex, Scholar, runtime quality, or PDC
  outputs only as local assumptions.
- Before answering, inspect `docs/system-design-decisions`,
  `docs/reference/policy-design-case-failure-patterns.md`,
  `src/polisyos/pdc`, `src/polisyos/runtime/quality`,
  `src/polisyos/core/audit`, `src/polisyos/lex`,
  `src/polisyos/participation_requirement`, `src/polisyos/obligation_graph`,
  `src/polisyos/obligation_rules`, and relevant runtime/PDC fixtures.
- Separate legal authority, democratic legitimacy, organizational authority,
  operational capacity, public transparency, contestability, and technical
  evidence. Do not collapse them into one governance score.
- If a task needs jurisdiction-specific law or institutional practice, produce
  a jurisdiction-neutral contract plus one example mapping, not a universal
  legal conclusion.
- The later handoff should describe how the result would enter the Policy Design
  Case without letting governance prose become runtime authority.

| ID | Independent research task | Minimum required output | Benchmark proxy / falsifier | Later integration target |
| --- | --- | --- | --- | --- |
| `CPA-R1` | What evidence is required to show that a policy goal, intervention authority, and decision forum have a valid mandate before PolicyOS may treat a design objective as admissible? | `MandateLegitimacyRecord` taxonomy, mandate-source hierarchy, authority-boundary rules, and blockers for missing or contested mandate. | Cases with clear statutory mandate, delegated mandate, expired mandate, conflicting mandate, and no mandate. | PDC intent envelope, Lex authority binding, approval gates, public export. |
| `CPA-R2` | When is affected-community participation sufficient to support a policy value choice, and when should absent or biased participation downgrade a claim to `limited`, `contested`, or `blocked`? | Participation adequacy rubric, representativeness limits, consultation-quality status lattice, and escalation rules. | Synthetic consultation packets with tokenistic, captured, representative, late, conflicting, and excluded-group feedback. | Participation evidence, value-choice provenance, human review, Trust View. |
| `CPA-R3` | How should PolicyOS record who authorized objectives, social weights, distributional priorities, and acceptable tradeoffs without silently making normative choices itself? | `ValueChoiceProvenance` contract, source taxonomy, conflict rules, and `may_not_use_for` boundary. | Multi-objective policy cases with principal-provided weights, inferred weights, conflicting weights, and missing weights. | PDC objective model, welfare modules, design recommendation gate. |
| `CPA-R4` | How should multi-principal conflicts be represented when ministries, agencies, courts, funders, municipalities, or affected groups authorize incompatible objectives? | Multi-principal incompatibility model, conflict status lattice, non-resolution rule, and projection requirements. | Cases where two principals disagree on objective, budget, legal competence, target population, or acceptable harm. | Governance decision records, public limitation labels, reviewer packet. |
| `CPA-R5` | What contestability evidence must exist before a public-facing PolicyOS recommendation is publishable for affected citizens or institutions? | Contestability readiness rubric, notice requirements, accessible explanation fields, evidence-disclosure tiers, and appeal-route refs. | Public decision packets with no appeal route, unreadable explanation, missing evidence, redacted evidence, and valid contestability path. | Public export, Trust View, case publication gate, audit bundle. |
| `CPA-R6` | How should implementation capacity and state capacity constrain whether a technically valid policy design is deliverable, limited, or blocked? | `ImplementationCapacityEnvelope`, capacity dimensions, evidence requirements, readiness caps, and capacity-building fallback. | Cases with absent delivery channel, weak enforcement, fiscal shortfall, trained staff gap, and strong administrative capacity. | PDC feasibility layer, readiness, approval, Foundry scenario assumptions. |
| `CPA-R7` | What delivery-failure modes should be modeled before PolicyOS can claim that a design is operationally feasible? | Delivery FMEA taxonomy, severity/likelihood rubric, ownership model, mitigation sufficiency rules. | Historical or synthetic failures involving procurement delay, data-sharing failure, field-office overload, fraud, and beneficiary exclusion. | Governance report, implementation plan evidence, risk register. |
| `CPA-R8` | How should skills, staffing, institutional memory, and maintenance burden become first-class evidence rather than narrative caveats? | Operational capability ledger, skills-gap status, maintenance-cost model, and staffing-risk blockers. | Agency profiles with temporary consultants, missing data stewards, overloaded reviewers, high turnover, and trained teams. | Capacity envelope, run-cost proportionality ledger, approval packet. |
| `CPA-R9` | How should PolicyOS measure public value, service quality, cost, trust, and return on investment after deployment without optimizing for misleading ROI? | Public-value measurement framework, anti-Goodhart metrics, ex-post outcome ledger, and limitation labels. | Deployment traces where cost falls but exclusion rises, speed improves but trust falls, or ROI is positive only under hidden externalities. | Ex-post learning, DDM, calibration, public accountability report. |
| `CPA-R10` | What third-party AI or data-supplier evidence is required before vendor-provided artifacts can enter a serious Policy Design Case? | `ThirdPartyAISupplyChainContract`, supplier evidence checklist, audit-rights model, subcontractor lineage, and risk tiers. | Vendor packets with missing model docs, hidden subcontractors, unverifiable data provenance, expired audit rights, and complete evidence. | Core audit, runtime quality authority, procurement gate, public export. |
| `CPA-R11` | How should vendor evidence escrow, independent audit access, and reproducibility obligations be specified for proprietary models or data? | Evidence escrow protocol, independent-audit interface, reproducibility minimums, and refusal/black-box blockers. | Proprietary vendor scenarios with accessible logs, black-box-only outputs, escrowed test sets, and denied audit. | Procurement artifacts, audit bundle, runtime verification, Trust View redactions. |
| `CPA-R12` | How should license, IP, data-use, and contractual restrictions limit downstream publication, replay, and model reuse? | Rights-and-restrictions contract, downstream-use matrix, replay/publication blockers, and retention obligations. | Cases with open data, commercial API terms, research-only data, PII restrictions, trade-secret claims, and incompatible licenses. | Fabric provenance, core audit archive, public export, replay bundle. |
| `CPA-R13` | What contingency, exit, and decommissioning evidence is needed when a vendor model, external API, or data supplier fails, changes terms, or becomes noncompliant? | Third-party contingency protocol, exit-readiness rubric, replacement evidence requirements, and decommissioning event shape. | Supplier outage, price shock, model behavior change, terms-of-service change, audit failure, and insolvency scenarios. | Runtime degradation ledger, dependency risk register, lifecycle events. |
| `CPA-R14` | How should a Policy Design Case project into a public algorithmic transparency record without leaking restricted evidence or overstating authority? | Transparency-record mapping, required fields, redaction policy, authority labels, and update lifecycle. | Mappings to public records with over-disclosure, under-disclosure, missing purpose, missing human role, and correct disclosure. | Public surface, Trust View, generated artifacts, core audit export. |
| `CPA-R15` | Which facts must be disclosed to public, reviewer, expert, and machine audiences, and which facts must remain redacted for privacy, security, legal, or procurement reasons? | Audience disclosure matrix, redaction semantics, residual-risk labels, and noninterference-style checks. | Same case rendered for citizen, journalist, regulator, internal reviewer, and machine auditor. | Projection semantics, public export, restricted Trust View. |
| `CPA-R16` | How can PolicyOS test whether public explanations improve understanding and contestability instead of creating false confidence? | Public explanation comprehension benchmark, trust-calibration metric, misunderstanding taxonomy, and failure thresholds. | User-study packet with hidden blockers, uncertainty, misleading simplification, and correct limited explanation. | Trust View, public export, human review packet, Scientist export research. |
| `CPA-R17` | When a published transparency record becomes stale, superseded, corrected, or legally restricted, what update and notice semantics are required? | Transparency lifecycle state machine, notice triggers, correction/supersession rules, and archival semantics. | Published record scenarios with source correction, model update, legal change, security takedown, and policy withdrawal. | Public registry export, PDC lifecycle, DDM reissue workflow. |
| `CPA-R18` | What counts as a PolicyOS-related AI/policy incident, hazard, near miss, or public harm, and what minimum reporting fields are required? | Incident taxonomy, severity model, reporting template, uncertainty labels, and relation to OECD AIM/AIID-style categories. | Incident packets for bias harm, privacy leak, wrong eligibility advice, failed oversight, integration harm, and near miss. | Incident ledger, DDM, public accountability report, audit export. |
| `CPA-R19` | How should citizen appeal, institutional challenge, correction request, and reviewer escalation reopen or limit a Policy Design Case? | Redress lifecycle model, appeal evidence packet, reopen criteria, responsible-owner rules, and response-time states. | Appeals with valid new evidence, unsupported complaint, procedural error, discriminatory impact, and expired window. | Case lifecycle, human decision records, public contestability surface. |
| `CPA-R20` | What remediation, correction, notification, compensation, or public apology evidence is needed after a PolicyOS-supported decision causes harm? | Harm repair protocol, remediation taxonomy, moral-repair record, effectiveness follow-up, and unresolved-harm labels. | Harm cases with silent fix, individual notice, public correction, compensation, and inadequate remediation. | Incident closeout, public report, governance decision, ex-post learning. |
| `CPA-R21` | How should incidents, appeals, retractions, legal changes, or discovered bias cascade into claim invalidation, reissue, supersession, or withdrawal? | Invalidation cascade graph, trigger taxonomy, dependency traversal rule, and false-alarm budget. | Downstream cases where one source, vendor, model, law, metric, or claim changes after publication. | Claim lifecycle, Research DAG invalidation, DDM, public update notice. |
| `CPA-R22` | What identity, permission, delegation, and accountability record is required before an AI agent can search, call tools, draft, request data, or interact with external systems? | `AgentDelegationAuthorityRecord`, permission tiers, tool-scope boundaries, human active-choice triggers, and revocation rules. | Agent traces with overbroad permissions, missing principal, external action, safe read-only search, and revoked access. | Scientist agents, runtime quality, core security, human decision records. |
| `CPA-R23` | How should agent orchestration choices be logged so evidence selection, tool choice, framing, and compression do not leak authority invisibly? | Agent choice ledger, replay requirements, framing-bias taxonomy, compression-loss metric, and audit queries. | Multi-agent traces with omitted counterevidence, selective tool use, lossy synthesis, and replayable neutral search. | Search ledger, Scientist orchestration, prompt/tool ledger, Trust View. |
| `CPA-R24` | What security and privacy threat model is needed for autonomous or semi-autonomous agents operating inside public-sector evidence workflows? | Agent threat model, credential boundary, prompt/tool injection scenarios, data exfiltration controls, and incident triggers. | Tool-call traces with prompt injection, malicious document, credential misuse, cross-tenant leak, and safe containment. | Core security, runtime quality, incident ledger, agent promotion gate. |
| `CPA-R25` | How should cross-department or cross-agency agent handoffs preserve responsibility, context, evidence boundaries, and auditability? | Agent handoff protocol, responsibility-transfer record, context-minimization rule, and broken-handoff blockers. | Handoffs across legal, data, finance, policy, and service-delivery teams with missing or valid authority transfer. | Workflow orchestration, human review, case audit trail, governance report. |
| `CPA-R26` | How should retractions, corrections, errata, living-review updates, hallucinated citations, or source withdrawals propagate through evidence and published policy claims? | Living evidence invalidation protocol, retraction/correction taxonomy, stale-claim status, and update/review triggers. | Evidence packs with retracted paper, corrected dataset, updated systematic review, fake citation, and unchanged robust claim. | Scientist evidence, Scholar bundles, claim lifecycle, public update notice. |
| `CPA-R27` | What construct-validity evidence is required before a metric, proxy, text variable, remote-sensing signal, or administrative field can stand for a policy construct? | `ConstructValidityEnvelope`, proxy-validity rubric, construct drift tests, measurement limitation labels, and blocker rules. | Cases where proxy is valid, stale, manipulable, group-biased, aggregation-mismatched, or semantically shifted. | Concept spine, Fabric schema/quality, Foundry method assumptions, claim support. |
| `CPA-R28` | What minimal obligation grammar maps external AI/public-sector governance regimes into PolicyOS artifacts without turning compliance text into authority? | Regulatory obligation grammar, crosswalk protocol, rule-version refs, obligation-to-artifact mapping, and conflict/unknown-law blockers. | Mappings for EU AI Act high-risk duties, NIST AI RMF controls, OMB AI governance, UK transparency records, and missing-jurisdiction cases. | Lex, obligation graph/rules, PDC closeout gates, public/audit export. |

## Scientist Tasks

Source: `docs/plans/active/SCIENTIST_BEST_IN_CLASS_PLAN.md`, Wave R.

Execution clause for every `SCI-*` row:

- Treat the row as an independent Scientist research prompt, not as a
  subtask of another Scientist item.
- Before answering, inspect the source plan, `docs/reference/scientist`,
  `src/polisyos/scientist`, `src/polisyos/evidence`, `src/polisyos/scholar`,
  `src/polisyos/ddm`, and relevant Scientist/quality tests.
- In the report, name the current Scientist artifact or workflow that is closest
  to the target. If no real producer, consumer, or verifier exists, use the
  missing-state labels rather than inventing a completed capability.
- If the task needs evidence from Fabric, Foundry, Scholar, Lex, or runtime
  quality, define the needed interface as a local assumption and keep the
  Scientist result honest without depending on that other research finishing.
- The later handoff should explain how the result would affect claim support,
  readiness, governance, human review, public export, or Trust View without
  giving research-only content production authority.

| ID | Independent research task | Minimum required output | Benchmark proxy / falsifier | Later integration target |
| --- | --- | --- | --- | --- |
| `SCI-R0` | What must a Scientist research track produce before affecting readiness, default enablement, governance, human review, or public export? | Track-card template, fixture index, readiness cap rules, kill-rule policy. | Each track names a benchmark proxy or is downgraded to recorded open problem. | Wave R research handoff, fixture index, research substrate CI gate. |
| `SCI-R1` | What is a sufficient computable support relation between evidence, counterevidence, and typed policy claims? | Claim-family support taxonomy, support matrix, counterexample catalog, readiness integration spec. | Hand-labeled factual, legal, policy, causal, contested, and invalid-support cases. | `ClaimRecord`, `ClaimSupportLink`, `ClaimLifecycleEvent`, `DecisionReadiness`. |
| `SCI-R2` | How can Scientist detect whether a cited source supports a paraphrased or synthesized claim? | Citation-faithfulness rubric, paraphrase fixture, scope-mismatch catalog, export thresholds. | Frozen snippets, paraphrases, expected labels, and hidden adversarial variants. | Snippet ledger, verifier, source-quality model, public export blocking rules. |
| `SCI-R3` | How should source authority, recency, primary-source status, duplicates, and conflict become decision-relevant quality? | Source-quality calibration model or rulebook, TTL matrix, conflict taxonomy, status mapping. | Dated, conflicting, stale, withdrawn-source cases. | Source quality, evidence cache, Research DAG invalidation, continuous governance. |
| `SCI-R4` | How should Scientist estimate value of more evidence, evaluation, challenge, causal computation, or human review when mandatory gates cannot be waived? | Multi-objective VOI definition, calibration protocol, regret report schema, default-enable checklist. | Offline scheduling traces with late evidence, near-frontier candidates, review traps. | VOI scheduler, human-review VOI escalation, authority evals. |
| `SCI-R5` | When should human review be required, what should reviewers see, and how should review effectiveness be measured? | Risk-tier threshold matrix, reviewer-packet ordering rules, false-pass/false-block protocol. | Human-review simulation pack with known blockers and automation-bias traps. | Human review, governance passes, reissue workflows. |
| `SCI-R6` | How can hidden eval content, canaries, prior traces, and generated challenge answers avoid contaminating memory or public artifacts? | Contamination taxonomy, canary strategy, leakage detector evaluation, redaction checklist. | Leakage stress suite with direct and paraphrased hidden facts. | Benchmark authority, memory contamination guards, challenge factory, public export. |
| `SCI-R7` | Which generated challenges are valid, non-leaky, and predictive of real failures? | Challenge validity rubric, mutation-preservation test, predictive-validity report, rotation policy. | Challenge lineage pack: generated, mutated, reviewed, rejected, duplicate, expired. | Challenge factory, rotation, sentinels, red-team, failure cards. |
| `SCI-R8` | When does changed evidence, drift, law/context change, or incident stale, reissue, supersede, or withdraw a decision? | Decision-validity semantics, drift threshold matrix, reissue explanation rubric, false-alarm budget. | Reissue simulation pack with changed sources, drift events, counterevidence, incidents. | Continuous governance, Research DAG invalidation, claim lifecycle, governance report. |
| `SCI-R9` | When does subagent fan-out improve evidence coverage and synthesis quality rather than amplify noise or citation errors? | Fan-out evaluation protocol, compression-loss metric, cost/coverage frontier, eligibility checklist. | Multi-hop policy research pack with known sources, distractors, contradictions, synthesis traps. | Agent promotion, supervisor eval, Research DAG projections, deep research subgraph. |
| `SCI-R10` | Which public, reviewer, expert, and machine exports improve trust calibration without overclaiming certainty? | Trust-calibration metric spec, export comprehension benchmark, omission taxonomy, Trust View requirements. | Explanation comprehension pack with known blockers, uncertainty, and hidden omissions. | Publisher, decision card, claim export, future Trust View. |

## Fabric Tasks

Source: `docs/plans/active/FABRIC_BEST_IN_CLASS_PLAN.md`, Wave R.

Execution clause for every `FAB-*` row:

- Treat the row as an independent Fabric research prompt, even when another
  Fabric task may define adjacent trust, lineage, schema, entity, or replay
  semantics.
- Before answering, inspect the source plan, `docs/reference/fabric`,
  `src/polisyos/fabric`, `src/polisyos/data_forge`,
  `src/polisyos/core/discovery`, and relevant Fabric/Data Forge tests and
  fixtures.
- Identify the current data-plane, provenance, quality, trust, entity,
  connector, or world-state primitive closest to the task. If it is only
  internal, not orchestrated, or not surfaced, say so precisely.
- If the task would feed Scientist readiness, Foundry uncertainty, IR analytics,
  or runtime quality, sketch the downstream contract as a candidate interface
  and preserve a conservative fallback where that consumer is absent.
- The later handoff should separate data truth, source trust, lineage,
  temporal semantics, privacy/access policy, and replay guarantees. Do not
  collapse them into a single score.

| ID | Independent research task | Minimum required output | Benchmark proxy / falsifier | Later integration target |
| --- | --- | --- | --- | --- |
| `FAB-R1` | How should data-quality defects map to uncertainty widening, readiness caps, hard blockers, or no decision impact? | `QualityImpactEnvelope` algebra, empirical rulebook or theorem, counterexample library. | Misleading scalar-quality cases: stale-stable, fresh-poisoned, complete-shifted, sparse-irrelevant. | Fabric quality/trust metadata, Scientist readiness caps, Foundry uncertainty propagation. |
| `FAB-R2` | How should source trust be calibrated without reducing it to institutional prestige? | Source-family calibration protocol, source-trust model card, scorecard contract extension. | Correction-history and schema-stability benchmark from replay fixtures. | SourceContract v2 `source_trust`, Trust View weighting, source selection policy. |
| `FAB-R3` | What are safe bitemporal property-graph traversal semantics for valid-time and tx-time facts? | Formal temporal graph model, query catalog, unsafe-pattern catalog, Kuzu capability matrix. | Counterexamples for false origin, false conflict, false downstream impact; DuckDB/Kuzu parity fixtures. | `world.kuzu_temporal_scope_capability`, temporal graph reasoning, impact analysis. |
| `FAB-R4` | How can lineage be compressed and redacted without losing audit-critical edges? | Loss-bounded summarization algorithm, redaction policy, privacy tests, compact/full parity fixtures. | Origin, transform, quality, dispute, restriction, and replay parity fixtures. | Compact/full lineage APIs, Trust View, audit bundles, OpenLineage/PROV exports. |
| `FAB-R5` | How should probabilistic entity resolution be calibrated under unstable policy data? | Evaluation protocol, false-merge/false-split cost model, confidence bands, override governance. | Longitudinal fixtures for renamed jurisdictions, split/merged units, multilingual labels, code reuse. | Entity candidate store, merge governance, graph helpers, conflict detection. |
| `FAB-R6` | Which distributed paths can honestly claim exactly-once or effectively-once processing? | Processing-guarantee taxonomy, proof obligations, crash/retry fixtures, dedupe-window rules. | Crash matrix across input progress, state update, output write, replay, sidecars. | Processing guarantees, CDC, streaming, distributed trust gates, source SLOs. |
| `FAB-R7` | How can semantic schema drift be detected beyond structural schema diffs? | Semantic diff taxonomy, metadata requirements, counterexample library, governance gate extension. | Denominator, geography, seasonality, imputation, unit display, methodology revision cases. | Schema evolution, semantic IDs, units, normalization, governance gates. |
| `FAB-R8` | What adversarial fixtures are needed for robust public-data ingestion? | Source-family threat model, adversarial fixture corpus, bounded-failure checklist. | Poisoning, spoofing, hostile metadata, hostile endpoint, Unicode, redirect, rate-limit cases. | Source scorecards, connector hardening, quarantine/rejection/degraded-fetch policy. |
| `FAB-R9` | How can provenance stay auditable without leaking values, source identities, query intent, or restricted relationships? | Access-aware provenance semantics, redacted placeholders, noninterference-style tests. | Restricted Trust View fixtures for public, internal, confidential, PII, sensitive legal/policy signals. | Field policies, runtime access refs, masking, PII staging, restricted Trust View. |
| `FAB-R10` | What is the minimal artifact set needed for policy-world replay by source family and pipeline type? | Replay-minimality theorem or empirical certificate, bundle schema, reproduction tests, retention note. | Replay classes across public data, confidential data, legal hold, source-terms-bound artifacts. | Portable audit bundles, retained snapshots, replay fixtures, long-term reproducibility. |

## Foundry Tasks

Source: `docs/plans/archive/FOUNDRY_METHODS_RESEARCH_AGENDA.md`, Phase 6
through Phase 11.

Execution clause for every `P*` row:

- Treat the row as an independent Foundry methods research prompt. Do not assume
  Phase 6, 7, 8, 9, 10, or 11 neighbors have already solved shared certificate,
  uncertainty, calibration, or benchmark semantics.
- Before answering, inspect the source agenda, `docs/reference/foundry`,
  `src/polisyos/foundry`, `src/polisyos/calibration`,
  `src/polisyos/ir/analytics`, and relevant Foundry property/unit/integration
  tests and golden fixtures.
- Identify the current method-family, result contract, calibration, uncertainty,
  validation, agent-simulation, welfare, compile/execute, or runtime primitive
  closest to the task. If the repo has a seed but no authority bridge, mark it
  `implemented_but_not_orchestrated` or `bridge_missing`.
- If the task needs Fabric data quality, Scientist evidence support, runtime
  quality admission, or PDC publication, define the interface as a local
  candidate and include kill rules for absent or weak upstream evidence.
- The later handoff should preserve method authority boundaries: estimation
  output, proof/certificate, calibration evidence, uncertainty envelope,
  reproducibility evidence, and policy admissibility are different claims.

### Foundry Phase 6 - Streaming, Online, Runtime Reliability, Calibration

| ID | Independent research task | Minimum required output | Later integration target |
| --- | --- | --- | --- |
| `P6.01` | How should human advisor overrides work without silently changing method authority? | Structured override protocol, audit semantics, rate-limit and rollback rules. | `MethodAdvisorResult.override_audit_ref`; human-in-the-loop advisor protocol. |
| `P6.02` | What deterministic recovery semantics are required after circuit-breaker trips? | Recovery-state taxonomy, replay proof, failure-mode counterexamples. | Circuit-breaker audit log with deterministic recovery plan. |
| `P6.03` | How can distributed execution remain deterministic under non-associative reductions? | Reduction-order protocol, tolerance budget, cross-run equivalence tests. | Distributed execution fingerprint and replay contract. |
| `P6.04` | How should cost uncertainty be represented as a distribution rather than a point estimate? | Cost uncertainty model, calibration method, counterexamples for point-cost routing. | `CostEstimate.distribution_ref`. |
| `P6.05` | How should precision budgets trade off against error bounds? | Precision-mode taxonomy, error-bound derivation, failure cases. | `PrecisionModeBound`; `MethodResult.precision_mode_and_bound`. |
| `P6.06` | How should plan selection optimize robustly under cost uncertainty? | Robust optimization protocol and regret analysis under cost uncertainty. | DRO plan selection certificate. |
| `P6.07` | When should delta-method versus Monte Carlo uncertainty be used under policy loss? | Dispatcher rule, loss-sensitive adequacy criteria, adversarial examples. | Delta/MC dispatcher certificate. |
| `P6.08` | How should importance sampling and adaptive allocation improve UQ without biasing decisions? | Adaptive allocation protocol, variance/bias diagnostics, stopping rules. | `MonteCarloConfig.importance_schedule`. |
| `P6.09` | How should coherent risk measures compose across uncertainty envelopes? | CVaR/ES composition rule, envelope algebra extension, counterexamples. | `CoherentRiskReport` on composed pipelines. |
| `P6.10` | When is calibration identifiable enough to be decision-relevant? | Identifiability-constrained calibration rule, sloppiness/failure diagnostics. | `CalibrationResult.identifiability_status`. |
| `P6.11` | How should multi-start local minima be characterized instead of hidden? | Multi-optimum reporting protocol, degeneracy diagnostics. | Calibration multi-optimum reporting. |
| `P6.12` | How should target alignment work under missing data and index mismatch? | Alignment diagnostic, mismatch taxonomy, target-validity rule. | Calibration target-alignment diagnostic. |
| `P6.13` | How should measurement error enter calibration? | Measurement-error model reference, calibration adjustment rule, sensitivity checks. | `CalibrationResult.measurement_model_ref`. |
| `P6.14` | What coverage guarantees are needed for sequential Bayesian updating? | Streaming posterior coverage protocol and replayable state rule. | `PosteriorResult.streaming_state`. |
| `P6.15` | How should bounded-memory estimators disclose approximation and memory limits? | Memory-bound certificate, approximation error rule, administrative-scale fixtures. | `StreamingStateCertificate`. |
| `P6.16` | How should online calibration monitoring produce early warnings? | Drift/early-warning protocol, false alarm budget, rolling calibration fixtures. | Online drift signal and warning lifecycle. |
| `P6.17` | What is a valid streaming / rolling cross-validation protocol? | Rolling-CV protocol, leakage controls, temporal split counterexamples. | Streaming validation and rolling CV. |

### Foundry Phase 7 - Privacy, Federation, Verified Numerics, Benchmark Infra, LLM Lifecycle

| ID | Independent research task | Minimum required output | Later integration target |
| --- | --- | --- | --- |
| `P7.01` | How can an external or internal probabilistic-program representation lower into existing Foundry method/result contracts with verifiable semantics, without requiring a full new PPL unless the repo has no usable front-end seam? | Verified-lowering theorem/protocol, supported and unsupported pattern catalog, semantic-preservation checks, and non-goals for full-language design. | `VerifiedLoweringCertificate`. |
| `P7.02` | What should count as a proof-carrying estimate certificate? | Certificate semantics, checker interface, falsification fixtures. | `MethodResult.verification_certificate`. |
| `P7.03` | What reproducibility guarantee is realistic across hardware? | Bit-exact or tolerance-bounded protocol, x86/ARM counterexamples. | Cross-architecture reproducibility protocol. |
| `P7.04` | How should DP budget compose across a full estimation pipeline? | DP accountant algebra, allocation policy, privacy-loss fixtures. | `PrivacyBudgetCertificate`. |
| `P7.05` | When is synthetic microdata utility-preserving enough for policy use? | Utility/privacy evaluation protocol and failure taxonomy. | `SyntheticDatasetCertificate`. |
| `P7.06` | How can record linkage preserve privacy while staying useful? | Leakage certificate, matching protocol, adversarial linkage tests. | Privacy-preserving record-linkage certificate. |
| `P7.07` | What correctness evidence is required for federated estimation? | Federated estimator correctness proof/protocol, heterogeneity fixtures. | `FederatedEstimatorCorrectnessCertificate`. |
| `P7.08` | How should hidden holdouts be managed for the six-judge stack? | Sealed-holdout protocol, leakage controls, admission/rotation policy. | `SealedHoldoutProtocol`. |
| `P7.09` | How should benchmarks be stratified by regime? | Leaderboard schema, regime taxonomy, anti-ranking-abuse rules. | `RegimeLeaderboardEntry`. |
| `P7.10` | What adversarial/pathological cases are required for method promotion? | Pathological-case registry, admission criteria, kill rules. | `PathologicalCaseRegistry`. |
| `P7.11` | How can LLM-assisted theorem drafting be machine-verified? | Theorem verification workflow, proof checker boundary, rejected-speculation rules. | `TheoremVerificationCertificate`. |
| `P7.12` | How can LLM-scaffolded estimator synthesis stay testable and bounded? | Scaffold audit protocol, unit-level verifier, non-authority rule. | Scaffolded-estimator audit. |
| `P7.13` | How should LLM literature synthesis preserve provenance? | Literature synthesis provenance model, source audit, citation faithfulness checks. | `LiteratureSynthesisReport`. |
| `P7.14` | How can hallucination in policy-text reasoning be detected? | Hallucination detection benchmark and certificate semantics. | `HallucinationDetectionCertificate`. |

### Foundry Phase 8 - Text, Earth Observation, RL / Adaptive Experimentation

| ID | Independent research task | Minimum required output | Later integration target |
| --- | --- | --- | --- |
| `P8.01` | How should regulatory information extraction prove citation correctness? | Extraction/citation certificate, span/table-cell rules, adversarial legal fixtures. | `TextExtractionBundle.citation_certificate`. |
| `P8.02` | What makes a topic model identified for policy corpora? | Identification test, topic stability/interpretability rule. | Identified topic model protocol. |
| `P8.03` | When can text-derived variables serve as policy treatment or outcome measures without laundering measurement error, construct drift, annotator/model bias, post-treatment leakage, or prompt artifacts into causal authority? | Text-causal identification framework, measurement-error tests, leakage controls, construct-validity limits, and unsafe-use blockers. | Text-as-treatment/text-as-outcome identification. |
| `P8.04` | How should RAG policy reasoning provide calibrated citations? | RAG citation calibration protocol, unsupported-answer blockers. | `RAGResponseCertificate`. |
| `P8.05` | What proof certificate is required for statutory/legal reasoning? | Statutory proof model, jurisdiction/scope counterexamples. | `StatutoryReasoningCertificate`. |
| `P8.06` | When are remote-sensing proxies bias-corrected enough for policy use? | Proxy bias-correction certificate and validation fixtures. | `RemoteSensingProxyBundle`. |
| `P8.07` | What authority contract is needed to fuse imagery, administrative data, and text on a common unit of analysis while preserving time/geography alignment, uncertainty propagation, lineage, and explicit disagreement labels? | Multimodal fusion protocol, modality-alignment rules, uncertainty and lineage semantics, disagreement/failure taxonomy. | `MultimodalIndicatorBundle`. |
| `P8.08` | How should geospatial privacy handle aggregation-level risks? | Geo-privacy protocol, MAUP/privacy counterexamples. | `GeoPrivacyCertificate`. |
| `P8.09` | How can change detection carry causal semantics? | Attribution-aware change detector, causal limitation labels. | Causal change-detection bundle. |
| `P8.10` | How should OPE work under partial identification? | OPE bounds estimator, policy-loss adequacy rule. | `OPEBoundsBundle`. |
| `P8.11` | How should contextual bandits satisfy fairness/equity constraints? | Fairness-constrained bandit protocol and certificate. | `FairnessConstrainedBanditCertificate`. |
| `P8.12` | How can adaptive RCTs preserve valid post-experiment inference? | Adaptive trial inference protocol, stopping/adaptation audit. | `AdaptiveTrialResult`. |
| `P8.13` | What safe-RL constraint-violation bounds are required? | Safe-RL violation-bound certificate and failure cases. | `SafeRLViolationBoundCertificate`. |
| `P8.14` | How should dynamic treatment regimes handle partial observability? | DTR fallback estimator and partial-observability limitation policy. | Dynamic treatment regime estimator. |

### Foundry Phase 9 - Structural Macro, Evidence Synthesis, Matching Markets

| ID | Independent research task | Minimum required output | Later integration target |
| --- | --- | --- | --- |
| `P9.01` | How should energy/carbon be represented as first-class estimation cost? | Energy/carbon accounting protocol and uncertainty model. | `CarbonCertificate`; cost model integration. |
| `P9.02` | What TEE evidence is sufficient for confidential computing claims? | TEE attestation semantics, trust boundary, failure cases. | `TEEAttestationCertificate`. |
| `P9.03` | What identification evidence is required for HANK estimation? | HANK identification certificate and benchmark regime. | `HANKIdentificationCertificate`. |
| `P9.04` | How should DSGE robust priors and structural breaks be reported? | DSGE break reporting format, prior robustness protocol. | `DSGEBreakReport`. |
| `P9.05` | How should mixed-frequency nowcasting handle ragged-edge data? | Nowcasting estimator contract, freshness and revision rules. | `NowcastingBundle`. |
| `P9.06` | How should structural model averaging weight identification strength? | Identification-weighted averaging rule and sensitivity fixtures. | `StructuralModelAveragingWeights`. |
| `P9.07` | How should Bayesian network meta-analysis include transportability? | NMA + transportability contract, site-shift diagnostics. | `NetworkMetaAnalysisBundle`. |
| `P9.08` | How should publication bias be corrected with calibrated power? | Publication-bias readiness policy, power calibration fixtures. | `PublicationBiasReadinessPolicy`. |
| `P9.09` | What makes living-review updates safe for evidence pipelines? | Evidence-update protocol, invalidation/reissue semantics. | `LivingReviewUpdateRecord`. |
| `P9.10` | How should meta-transportability across K sites be estimated? | K-site transport estimator and heterogeneity diagnostics. | `MetaTransportabilityCertificate`. |
| `P9.11` | How should deferred acceptance expose strategy-proofness? | Assignment mechanism certificate and preference truthfulness tests. | `AssignmentMechanismCertificate`. |
| `P9.12` | How should two-sided matching elicit policy-data preferences? | Preference-identification contract, manipulation counterexamples. | Two-sided matching preference contract. |
| `P9.13` | How should public-sector combinatorial auctions bound welfare loss? | Auction welfare-loss bound and tractability protocol. | `CombinatorialAuctionWelfareLossBound`. |
| `P9.14` | What bounded mechanism-design contract is adequate for platform-regulation scenarios, including actors, incentives, constraints, observables, intervention levers, equilibrium/response assumptions, and governance limits? | Three-layer platform mechanism contract, assumption ledger, observability requirements, and governance constraints. | `PlatformMechanismBundle`. |

### Foundry Phase 10 - Specialised Families

| ID | Independent research task | Minimum required output | Later integration target |
| --- | --- | --- | --- |
| `P10.01` | For three-plus-level public-policy optimization problems, when is exact solve, relaxation, decomposition, bilevel reduction, robust bounding, or abstention justified by problem class? | Multi-level optimization tractability map, solver/fallback decision rule, impossibility or hardness notes, and abstention policy. | Hierarchical optimization contract. |
| `P10.02` | What finite-N corrections are needed for mean-field convergence? | MFG convergence-rate analysis and correction fixtures. | Mean-field finite-N correction. |
| `P10.03` | What certificate semantics are required for coupled mechanisms and correlated equilibria, including existence, non-existence, multiplicity, ambiguity, verification evidence, and policy-use blockers? | Equilibrium certificate taxonomy, non-existence/ambiguity blockers, verification evidence requirements, and unsafe-use cases. | Coupled mechanism/correlated equilibrium support. |
| `P10.04` | How should Hawkes/self-exciting processes represent policy events? | Point-process result contract and calibration tests. | `PointProcessResult`. |
| `P10.05` | How should competing risks and recurrent events be estimated? | Competing-risks estimator protocol and censoring diagnostics. | `CompetingRisksResult`. |
| `P10.06` | How should marked point processes handle spatio-temporal events? | Marked point-process contract and spatial-temporal fixtures. | Marked point-process result. |
| `P10.07` | How should deep survival models expose calibrated intervals? | Deep-survival wrapper, calibration checks, failure cases. | Deep survival result. |
| `P10.08` | How should functional data represent longitudinal policy outcomes? | Functional outcome contract and smoothing/measurement rules. | `FunctionalResult`. |
| `P10.09` | How should persistent homology describe policy data shape? | TDA persistence contract, stability metrics, false-pattern cases. | `PersistenceDiagramResult`. |
| `P10.10` | When is manifold learning causally faithful enough to use? | Manifold faithfulness diagnostic and non-identifiability blockers. | `ManifoldFaithfulnessDiagnostic`. |
| `P10.11` | How should geometric deep learning be used on administrative graphs? | Geometric-DL estimator contract and graph-shift diagnostics. | Geometric administrative graph estimator. |
| `P10.12` | How should benefit-abuse detection balance causal fairness? | Fraud/fairness Pareto frontier and fairness failure cases. | `FraudFairnessFrontierCertificate`. |
| `P10.13` | How should adaptive audit sampling expose detection bounds? | Adaptive audit protocol and detection-bound fixtures. | `AdaptiveAuditProtocol`. |
| `P10.14` | How should anomaly detection update under drift? | Detector update rule, drift coupling, false alarm budget. | `DetectorUpdateRule`. |
| `P10.15` | How should multivariate EVT represent policy tail risk? | Tail-risk bundle, tail-dependence diagnostics, stress fixtures. | `TailRiskBundle`. |
| `P10.16` | What VFI error bounds are needed under policy-function iteration? | VFI error-bound derivation and uncertainty pipeline shell. | `ValueFunctionResult`. |

### Foundry Phase 11 - Cross-Family Extensions, Meta-Evaluation, Replication

| ID | Independent research task | Minimum required output | Later integration target |
| --- | --- | --- | --- |
| `P11.01` | How should geostatistical extremes work under spatial dependence? | Extreme-value spatial envelope and dependence diagnostics. | Spatial EVT extension. |
| `P11.02` | What governance is needed for whistleblower-safe reporting infrastructure? | Reporting governance protocol and threat model. | Whistleblower-safe reporting infra. |
| `P11.03` | How should copula tail dependence support policy scenarios? | Tail-dependence estimator and bias-correction fixtures. | Copula tail-dependence extension. |
| `P11.04` | How should scenario generation prove coverage? | Scenario coverage certificate and adversarial gaps. | `ScenarioCoverageCertificate`. |
| `P11.05` | How should worst-case fiscal scenarios compose EVT, DRO, and GE feedback? | Compound fiscal stress certificate and tractability policy. | `WorstCaseFiscalScenarioCertificate`. |
| `P11.06` | How should dynamic games be identified? | Dynamic-game equilibrium format and identification blockers. | Dynamic game result. |
| `P11.07` | How should uncertainty propagate through VFI chains? | Envelope-VFI integration rule and replay fixtures. | VFI uncertainty propagation. |
| `P11.08` | How should discrete-continuous choice be estimated? | Discrete-continuous estimator contract and identification diagnostics. | DC-choice estimator. |
| `P11.09` | How should Bayesian model-selection diagnostics for already-fit models and Bayesian-optimization regret/safety protocols for active search share one calibrated authority surface, and when can either be used without the other? | WAIC/LOO/stacking diagnostic, BO regret/safety protocol, shared calibration status, and separability rules. | `PosteriorResult.selection_diagnostic`; BO active-learning result. |
| `P11.10` | How should ordinal regression, probabilistic forecasts, and forecast combinations compose into coherent forecast authority with ordinal scoring, quantile/interval representation, calibration checks, no-arbitrage constraints, and failure cases? | Ordinal forecast contract, probabilistic calibration protocol, quantile curve representation, no-arbitrage combination rule. | Ordinal forecast contract; `ForecastingUncertaintyBundle.quantile_curves`. |
| `P11.11` | How should an econometric dispatcher choose between local projections and VAR for dynamic macro response while separately applying MHT correction, top-coded wealth handling, and group deflator rules for valid distributional measurement? | LP/VAR dispatcher, MHT correction rule, top-code protocol, group-deflator protocol, and rule preventing collapse into one estimator. | `EconometricResult.mht_correction_applied`; `DistributionalBundle.group_deflator`. |
| `P11.12` | How should sequential public-decision problems compose real-options value, multi-period welfare, integer-programming allocation, fair facility-location frontiers, and dynamic-mechanism incentive constraints as typed sub-results with composition and abstention rules? | Real-options estimator, sequential welfare rule, branch-and-cut/fairness frontier, dynamic BIC contract, composition/abstention rule. | `OptimizationResult.fairness_frontier`; `DynamicMechanismBundle`. |
| `P11.13` | What separate certificates are required for validated SDE/ODE trajectory enclosures and network motif-count uncertainty, and what common validation rule lets both enter Foundry method authority without merging the method families? | Validated trajectory bound, SDE/ODE error-envelope protocol, motif-count CI contract, shared validation and failure rule. | `ValidatedSDEResult`; `NetworkMotifCensus`. |
| `P11.14` | How should the six-judge stack itself be meta-evaluated? | Judge-readiness certificate, hidden-ground-truth benchmark, false-pass/false-block metrics. | Meta-evaluation protocol for the six-judge stack. |
| `P11.15` | How should Foundry replicate across R/Stata/Python toolchains? | Cross-toolchain tolerance library and replication registry. | Replication registry coupled to tolerance and verified numerics tracks. |

## Completion Ledger Template

Use this table as tasks are researched.

| ID | Status | Research artifact | Result type | Benchmark proxy | Promotion disposition | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| - | `not_started` | - | - | - | - | - |

Allowed `status` values:

- `not_started`
- `in_research`
- `accepted_narrow_scope`
- `confirmed`
- `refuted`
- `deferred_open_problem`
- `ready_for_engineering_handoff`

Allowed `promotion_disposition` values:

- `research_only`
- `prototype_allowed`
- `governed_allowed`
- `production_candidate`
- `blocked`
- `out_of_scope`
