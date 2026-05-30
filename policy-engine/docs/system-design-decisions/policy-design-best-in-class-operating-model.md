---
title: PolicyOS Best-In-Class Policy Design Operating Model
status: draft design decision
owner: team-architecture
created: 2026-05-16
related_diagnostics:
  pass_1a:
    - PDD-001
    - PDD-002
    - PDD-003
    - PDD-004
    - PDD-005
    - PDD-006
    - PDD-007
    - PDD-008
    - PDD-010
    - PDD-011
    - PDD-014
    - PDD-042
    - PDD-043
    - PDD-047
    - PDD-049
    - PDD-052
    - PDD-062
    - PDD-074
  pass_1b:
    - PDD-017
    - PDD-018
    - PDD-019
    - PDD-022
    - PDD-023
    - PDD-024
    - PDD-025
    - PDD-028
    - PDD-029
    - PDD-030
    - PDD-031
    - PDD-032
    - PDD-033
    - PDD-039
    - PDD-040
    - PDD-041
    - PDD-045
    - PDD-058
    - PDD-067
    - PDD-071
    - PDD-072
    - PDD-073
    - PDD-075
    - PDD-076
    - PDD-079
    - PDD-080
    - PDD-081
    - PDD-082
    - PDD-084
    - PDD-085
    - PDD-086
    - PDD-089
    - PDD-091
    - PDD-092
    - PDD-093
    - PDD-094
    - PDD-095
    - PDD-096
    - PDD-102
---

# PolicyOS Best-In-Class Policy Design Operating Model

## Status

Draft system design decision.

This document is not an implementation plan. It chooses the system shape that
the next domain and hardening plans should implement if PolicyOS is to become a
real best-in-class policy-design system rather than a strong diagnostic shell
around a weak policy pipeline.

Concrete work should be derived later in `docs/plans/`. Stable irreversible
choices should be promoted to ADRs after the first implementation slice proves
the contracts.

Accepted ADRs now carry the execution-grade decisions extracted from this
umbrella:

- [ADR-0156: Policy Design Case Runtime Quality Assurance Profile](../adr/0156-policy-design-case-runtime-quality-assurance-profile.md)
- [ADR-0157: Policy Intent Envelope, Capability Ledger, And Authority Profile Mapping](../adr/0157-policy-intent-capability-ledger-authority-profile.md)
- [ADR-0158: Concept Spine And Multi-Jurisdiction Reconciliation](../adr/0158-concept-spine-multi-jurisdiction-reconciliation.md)
- [ADR-0159: Production Evidence Producer Contracts For Lex, Fabric, Scholar, And Data Forge](../adr/0159-production-evidence-producer-contracts.md)
- [ADR-0160: Evidence Portfolio, Independence Map, Multiverse, And Synthesis](../adr/0160-evidence-portfolio-independence-multiverse-synthesis.md)
- [ADR-0161: Claim Argument, Warrant Reliability, And Compiler Closeout Gate](../adr/0161-claim-argument-warrant-compiler-closeout-gate.md)
- [ADR-0162: Human Oversight, Publication, And External Audit Authority](../adr/0162-human-oversight-publication-external-audit-authority.md)
- [ADR-0163: Lifecycle, DDM, Ex-Post Outcomes, And Calibration](../adr/0163-lifecycle-ddm-ex-post-calibration.md)
- [ADR-0164: Run Cost, Proportionality, And Evidence Budget Governance](../adr/0164-run-cost-proportionality-evidence-budget-governance.md)
- [ADR-0165: Formal Policy Case And Substrate Invariant Specs](../adr/0165-formal-policy-case-substrate-invariant-specs.md)

## Problem

Pass 1A and Pass 1B diagnostics show that the honest diagnostics substrate now
has enough authority to expose the real problem: PolicyOS can prove that a run
is not production-quality, but the domain policy-design pipeline still does not
yet build a policy decision as a connected, evidence-native public-policy case.

The strongest Pass 1A findings are structural:

- intent is carried as request text and nested params, not as a canonical
  policy-intent envelope;
- router and capability selection are not ledgered, so Lex, Fabric, Scholar,
  Foundry, Scientist, and compiler duties are implicit;
- concepts fragment across request payloads, metric catalogs, dataset catalogs,
  legal stores, method contracts, semantic binding ledgers, and final claims;
- Lex has a populated legal corpus, but runtime normative reports do not query
  and bind authoritative candidate norms;
- production data contains relevant Ukraine artifacts, but runtime Fabric sees
  broad manifest roles and generic metrics;
- Scholar can already build CAS-first, freshness-aware knowledge bundles, but
  the policy operating model did not treat academic evidence retrieval,
  scoring, freshness, and claim-support links as a first-class producer duty;
- method expectations exist, but execution plans can proceed with an empty
  method DAG and later classify the method as generic simulation;
- final major claims can be minted without `data_refs`, `method_refs`,
  `norm_refs`, objective refs, numerical semantics, or typed blockers.

The strongest Pass 1B findings show the same pattern around governance and
delivery:

- tenant, CAS, approval, human review, signing, release, dependency, client,
  and public-export controls exist in pieces but do not form one closeout
  contract per policy decision;
- runtime topology, config, release, schema migration, generated surfaces,
  external dependencies, retention, deletion, replay, and local browser state
  are not all bound into the same policy evidence graph;
- dashboard, collaboration, offline queues, bureaucratic rendering, and public
  decision surfaces can present or mutate policy-relevant state without a
  single runtime-owned authority ledger.

The defect is not lack of validators. The defect is that the system has not yet
chosen the policy design object that every validator, producer, UI, and
governance surface must serve.

A second design review adds a further constraint: the policy design object must
not be one-shot. A world-class policy system must know whether earlier policy
claims later held up, how a case was revised, whether it was superseded or
withdrawn, and how the system's own forecasts calibrated over time.

A third implementation-readiness review adds one practical constraint: much of
the advanced machinery already exists in `src/polisyos`. The operating model
must therefore be reuse-first. It should wire and expose existing Scientist,
Foundry, Fabric, Lex, Scholar, calibration, continuous-governance, and memory
capabilities as case records before any plan builds replacement engines.

A fourth repository-realization review tightens that constraint: the central
assurance-case and honest-diagnostics surfaces already have physical owners in
`src/polisyos/runtime/quality`, external audit packaging already has an owner
in `src/polisyos/core/audit`, post-publication drift and degradation monitoring
already has an owner in `src/polisyos/ddm`, bounded explanation reliability
already has an owner in `src/polisyos/berl`, and production corpus snapshots
already have an owner in `src/polisyos/data_forge`. The design posture for
those capabilities is wire or extend, not build-new.

## Non-Goals

This decision does not prescribe:

- exact class names or module boundaries;
- implementation order;
- score weights or threshold values;
- one jurisdiction's policy process as universal law;
- one causal method family as universally preferred;
- one UI layout for the dashboard, Clerk, Composer, or public viewer;
- formal ADR acceptance for every proposed contract.

The goal is to choose the operating model and authority boundaries. Plans and
ADRs can then instantiate them.

## Core Decision

PolicyOS will be shaped as an evidence-native policy design system whose
primary case object is an assurance case profile, not a bespoke report graph.

In the current repository this is not a greenfield object. The runtime already
contains `src/polisyos/runtime/quality/assurance_case.py` and adjacent quality
modules for authority, semantic binding, prompt/tool ledgers, performance
budgets, approval, human review, attestation, degradation, public export,
metamorphic controls, schema compatibility, effective mode, source-of-truth,
event logging, scorecards, replay, and phase barriers. The Policy Design Case
should profile and extend that runtime assurance-case substrate with policy
semantics; it must not create a parallel serious-run case authority.

The primary product of a serious run is not a chat answer, dashboard state,
scorecard, public document, or bundle. The primary product is a Policy Design
Case: a typed, runtime-owned, CAS-addressed assurance case that connects:

1. policy intent and problem definition;
2. canonical policy concepts and target context;
3. legal authority and institutional competence;
4. data sources, variables, quality, lineage, and numerical semantics;
5. academic and grey-literature evidence, retrieval scoring, freshness, and
   claim-support links;
6. method selection, assumptions, uncertainty, and validity limits;
7. policy options, baseline, tradeoffs, distributional effects, and risks;
8. final claims and recommendations;
9. implementation, monitoring, review, publication, contestability, and archive
   authority;
10. case lifecycle, supersession, retraction, and recall authority;
11. ex-post outcomes, evaluation results, and claim re-assessment;
12. system calibration and track-record evidence by domain, method,
    jurisdiction, data class, and evidence mode.

The Policy Design Case must be compatible with assurance-case discipline:
claims, arguments, warrants, assumptions, contexts, evidence, rebuttals,
counter-evidence, and assurance deficits are distinct objects. A claim is not
supported merely because it lists refs. The case must explain why those refs
support the claim, under which assumptions, against which rebuttals, and with
which residual deficits.

Every downstream surface reads from that Policy Design Case. No downstream
surface may silently create production authority.

In practical terms, PolicyOS should move from:

`text request -> orchestration -> domain artifacts -> scorecard`

to:

`intent envelope -> concept spine -> evidence contracts -> producer execution -> claim case -> governed publication -> ex-post learning`

The honest diagnostics substrate remains the closeout authority. This decision
defines what the domain policy case must contain before the substrate can
honestly close it.

## Design Review Disposition

A second design review raised seven material design risks. This document accepts
the core of that review:

- align the Policy Design Case with established assurance-case standards rather
  than inventing a private graph vocabulary;
- add explicit argument/warrant, rebuttal, counter-evidence, and
  assurance-deficit nodes;
- treat the EU AI Act as a mandatory legal anchor for high-risk public-sector
  AI uses, alongside NIST AI RMF as a voluntary risk-management framework;
- measure effective human oversight rather than recording review as a nominal
  gate;
- add requester-capture and policy-based-evidence-making controls;
- require triangulation or an explicit single-line-evidence deficit for major
  claims;
- add self-FMEA, case maturity, and formal substrate invariant specification so
  the case machinery itself does not become a brittle box-ticking system.

A third implementation-readiness review found that several target capabilities
are already present as reusable modules rather than absent future work. This
document accepts that review too:

- evidence portfolios, multiverse/specification curves, sensitivity, stress,
  stability, and discovery aggregation should wire Scientist DOE and discovery
  modules before any new portfolio engine is designed;
- adversarial challenge should expose existing Scientist policy-design and
  backtesting adversarial results as assurance-case nodes;
- effective oversight should extend existing human-review packets, queues,
  decisions, and value-of-information escalation with effectiveness telemetry;
- calibration, ex-post validation, lifecycle, and learning should project over
  existing calibration, backtesting, continuous-governance, and memory modules;
- Scholar must become a first-class academic evidence producer in the operating
  model;
- Foundry agent simulation and synthetic worlds are independent evidence-line
  families for complex policy portfolios;
- cost/proportionality is not absent, but the existing Foundry and Scientist
  budget surfaces need a consolidated run-level proportionality ledger.

A fourth repository-realization review found additional reuse-critical owners.
This document accepts those findings:

- the Policy Design Case should extend `runtime/quality/assurance_case.py` and
  related runtime quality ledgers instead of creating a second case object;
- drift, degradation, readiness, incident, shift, calibration, and root-cause
  monitoring should project over `src/polisyos/ddm`;
- assurance warrants and reviewer-facing explanations should carry bounded
  reliability evidence from `src/polisyos/berl` where explanation reliability
  affects trust;
- IR analytics already owns large parts of falsification, identification,
  transportability, distributional, welfare, fairness, strategic, and
  certificate/proof evidence;
- Foundry method consensus and equivalence modules should feed convergence,
  independence collapse, and effective independent evidence count;
- research/governed/production authority levels should be mapped to existing
  core governance, execution-profile, and effective-mode surfaces;
- external audit, PROV export, SLSA attestation, standalone verification, and
  safe archive handling should wire `src/polisyos/core/audit`;
- Data Forge owns offline corpus build, snapshot, manifest, provenance, and
  read-API bindings for production legal, catalog, academic, and domain data.

## External Design Anchors

This operating model combines public-policy guidance with software and AI
assurance patterns.

| Source | Lesson for PolicyOS |
| --- | --- |
| [ISO/IEC/IEEE 15026-2 assurance case](https://www.iso.org/standard/80625.html) | A serious Policy Design Case should align with assurance-case practice: explicit claims, arguments, evidence, context, assumptions, and reviewable justification. |
| [OMG Structured Assurance Case Metamodel](https://www.omg.org/spec/SACM/) | The case graph should be exportable or mappable to a standard assurance-case metamodel so external auditors are not forced to learn a private PolicyOS-only structure. |
| [GSN community standard resources](https://scsc.uk/gsn) and [CAE](https://www.adelard.com/asce/cae/) | Claims need argument strategies and warrants, not only evidence refs. Rebuttals, counter-evidence, and assurance deficits should be inspectable nodes. |
| [HM Treasury Green Book](https://www.gov.uk/government/publications/the-green-book-appraisal-and-evaluation-in-central-government/) | Appraisal is about objectives, options, costs, benefits, and risks. PolicyOS must represent alternatives and the baseline, not only one generated recommendation. |
| [HM Treasury Magenta Book](https://www.gov.uk/government/publications/the-magenta-book/magenta-book-central-government-guidance-on-evaluation-html) | Evaluation should be planned early and support policy design, delivery, accountability, and learning. PolicyOS monitoring/evaluation evidence must be designed before publication. |
| [HM Treasury AQuA Book](https://www.gov.uk/guidance/the-aqua-book) | Analytical quality assurance belongs throughout the cycle, with records of assumptions, data, decisions, checks, limitations, and changes. PolicyOS must make those records machine-checkable. |
| [OMB Circular A-4](https://www.whitehouse.gov/wp-content/uploads/2023/11/CircularA-4.pdf) | Regulatory analysis needs a problem/need statement, alternatives, benefits, costs, distributional effects, uncertainty, transparency, and reproducibility. PolicyOS should make these first-class claim families. |
| [Specification curve analysis](https://www.nature.com/articles/s41562-020-0912-z) | Empirical results can depend on defensible but arbitrary analytical choices. Major empirical claims should report the distribution of results across justified, valid, non-redundant specifications. |
| [Multiverse analysis](https://journals.sagepub.com/doi/10.1177/1745691616658637) | Data construction and analytical degrees of freedom can create many reasonable result worlds. PolicyOS should make those worlds visible instead of selecting one path silently. |
| [Severe testing](https://www.cambridge.org/core/books/statistical-inference-as-severe-testing/statistical-inference-as-severe-testing/5EE1100C9188141FC49723DF124B0EC9) | A claim is stronger when it survives tests that had a high chance of revealing its flaw. Evidence portfolios should include disconfirming lines, not only friendly confirmations. |
| [Cochrane GRADE evidence certainty](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-14) | Certainty belongs to a body of evidence and should consider risk of bias, inconsistency, indirectness, imprecision, and publication bias. PolicyOS synthesis should grade evidence bodies, not isolated refs. |
| [OECD Regulatory Impact Assessment principles](https://www.oecd.org/en/publications/regulatory-impact-assessment_7a9638cb-en) | RIA should be part of the policy cycle, paired with consultation, monitoring, ex post evaluation, and review of existing rules. PolicyOS should treat policy design as lifecycle governance. |
| [OECD Public Policy Monitoring and Evaluation](https://www.oecd.org/en/topics/sub-issues/public-policy-monitoring-and-evaluation.html) | Monitoring and evaluation help define goals, identify promising practices, detect weaknesses, and improve policy use. PolicyOS should emit monitoring and evaluation contracts, not afterthought text. |
| [OECD Regulatory Policy Outlook 2021 on stakeholder engagement](https://www.oecd.org/en/publications/oecd-regulatory-policy-outlook-2021_38b0fdb1-en/full-report/evidence-based-policy-making-and-stakeholder-engagement_b78456cc.html) | Affected stakeholders should be engaged to test assumptions, improve alternatives, identify impacts, and build trust. PolicyOS consultation evidence must be first-class. |
| [OECD Reviewing the Stock of Regulation](https://www.oecd.org/content/dam/oecd/en/publications/reports/2020/12/reviewing-the-stock-of-regulation_c6a98487/1a8f33bc-en.pdf) | Ex-post review should assess actual outcomes against objectives, extract lessons, and recommend corrections. PolicyOS needs outcome ledgers, reassessment, and case supersession. |
| [European Commission Better Regulation Toolbox](https://commission.europa.eu/law/law-making-process/better-regulation/better-regulation-guidelines-and-toolbox/better-regulation-toolbox_en) | Better regulation links evidence-informed policymaking, legal basis, subsidiarity/proportionality, impact assessment, risk, monitoring, and evaluation. PolicyOS needs the same cross-cutting case structure. |
| [EU AI Act](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai) | High-risk AI obligations include risk management, data quality, logging/traceability, documentation, deployer information, human oversight, robustness, cybersecurity, accuracy, and post-market monitoring. PolicyOS should treat these as baseline compliance anchors for public-sector high-risk use. |
| [EDPS TechDispatch on human oversight](https://www.edps.europa.eu/data-protection/our-work/publications/techdispatch/2025-09-23-techdispatch-22025-human-oversight-automated-making_fr) | Human oversight is meaningful only when humans are empowered, trained, positioned to intervene, and protected from automation bias. Review effectiveness must be measured. |
| [NIST AI RMF 1.0](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-ai-rmf-10) | AI-enabled systems should manage risk across govern, map, measure, and manage functions. PolicyOS should align serious runs with explicit risk, accountability, and monitoring functions. |
| [NIST AI RMF resource center](https://www.nist.gov/itl/ai-risk-management-framework) | Trustworthiness must be incorporated into design, development, use, and evaluation, with risk actions aligned to goals and context. PolicyOS should threat-model its evidence graph. |
| [W3C PROV](https://www.w3.org/TR/prov-overview/) | Provenance should use common concepts for entities, activities, agents, derivation, attribution, and validation. PolicyOS evidence contracts should remain PROV-shaped even when stored as CAS JSON. |
| [EFSA Expert Knowledge Elicitation guidance](https://www.efsa.europa.eu/en/efsajournal/pub/3734) | When empirical evidence is limited, structured expert judgement can inform risk assessment if its method, uncertainty, and provenance are explicit. PolicyOS should support judgement as judgement, not fake data. |
| [ISO 31000 risk management](https://www.iso.org/standard/65694.html) | Risk management should identify, analyse, evaluate, treat, monitor, and communicate risks across governance and decision-making. PolicyOS run cost, proportionality, and integrity risks need explicit records. |
| [TLA+](https://lamport.org/tla/tla.html) | Closeout authority depends on concurrent state-machine invariants. Key substrate invariants should have lightweight formal specifications or model checks, not tests alone. |

These are anchors, not external masters. PolicyOS should synthesize them into a
runtime-verifiable operating model.

## Design Principles

### Policy Meaning Before Component Execution

Lex, Fabric, Foundry, Scientist, and compiler execution must be downstream of a
canonical policy-intent envelope and concept spine. If the policy meaning is
ambiguous, missing, or fragmented, the system should emit typed blockers before
domain components invent incompatible local interpretations.

### Concepts Are Shared Infrastructure

Policy concepts are not metric labels. The system needs a canonical concept
registry that bridges policy terms, metrics, datasets, legal concepts, method
requirements, geographies, populations, time periods, objectives, and claims.

The registry does not need to be a monolith, but the reconciliation result must
be one authority-bearing concept spine per run.

### Evidence Contracts Precede Evidence Production

A serious run should know what evidence is required before producers execute.
The runtime should derive evidence contracts from the intent envelope, scenario
contract, concept spine, jurisdiction, time context, target population,
available data, and candidate methods.

Post-hoc validators remain useful, but they should verify evidence against a
known contract rather than discover after the fact that no contract existed.

### Alternatives And Baselines Are First-Class

Best-in-class policy design compares options against a baseline. A final
recommendation without alternatives, baseline, tradeoff rationale,
distributional effects, and uncertainty is not a production policy decision.

The Policy Design Case must represent rejected options and the reason they were
rejected, not only the selected answer.

### Legal Authority Is Retrieval Plus Competence

Legal evidence is not present because a report has legal-shaped fields. It is
present when the system queries authoritative legal stores, binds candidate
norms to jurisdiction and policy time, records conflicts, and proves the
recommended action is within implementing authority.

### Data Evidence Is Field-Level And Semantically Bound

Dataset-level refs are insufficient for final policy claims. The system must
bind claims to source family, dataset, column, unit, currency, geography,
calendar, dictionary, quality report, transform, lineage, and freshness
semantics.

### Method Fitness Is A Selection Decision

Method quality cannot be inferred from a generic execution result. Foundry must
choose method families before execution, record candidate and rejected methods,
prove compatibility with the claim, and emit assumptions, uncertainty,
sensitivity, missingness, and external-validity boundaries.

### Claims Are Compiled From Evidence, Not Decorated Later

Final claims must be minted with required evidence refs or typed blockers.
Downstream grounding validators should not have to reconstruct missing refs
from selected datasets or methods.

### Governance Is Part Of Policy Design

Tenant scope, CAS ownership, approval, human review, signing, release,
dependency rights, privacy/security, retention, public export, client-local
state, and archive reproducibility are not outer wrappers. They are part of the
Policy Design Case because they determine whether the policy decision can be
trusted, shared, published, contested, and replayed.

### Projections Must Stay Honest

Dashboard, Composer, Clerk, collaboration, offline queue, bureaucratic export,
and public viewer surfaces may guide humans, but they must label whether a
state is authoritative, queued, local, draft, projection-only, redacted,
externally reviewed, signed, stale, or contested.

### Policy Cases Have Lifecycles

A published case can be amended, superseded, withdrawn, retracted, appealed,
or archived. The system must model those lifecycle events as authority-bearing
records, not as labels on a static document.

### Arguments Are First-Class

Every major claim needs an explicit argument strategy and warrant. Evidence
refs say what was observed; arguments say why those observations support the
claim. Rebuttals, counter-evidence, assumptions, and assurance deficits must be
visible and challengeable.

### Learning Is Evidence

PolicyOS must compare predicted claims against implemented outcomes. Ex-post
evaluation, monitoring results, reversal events, and case re-assessments must
feed back into future method selection, uncertainty, and domain trust records.

### Calibration Is A Product Feature

The system should know its own track record. It must measure historical
forecast error, interval coverage, bias, reversal rates, blocker precision,
and evidence-class reliability by domain, jurisdiction, method, data source,
and evidence mode.

### Structured Judgement Is Not Fake Data

When empirical data is missing or insufficient, the system may use structured
expert judgement only when it is explicitly labelled, method-bound,
provenance-rich, uncertainty-bearing, and separated from observed data.

### Consultation Is Evidence

Stakeholder engagement, public comment, objections, affected-party feedback,
and response-to-comment reasoning are part of policy legitimacy. They should be
first-class evidence records, not postponed narrative appendices.

### Producers Need Independence

The same producer should not silently define the claim, select the method, run
the method, and compile the final claim without independence evidence. Serious
runs need separation-of-duty attestations and conflict records.

### Human Oversight Must Be Effective

Human review is not effective merely because an approval button exists. The
case must measure review timing, reviewer independence, dissent, overrides,
changes requested, time spent, exposure order, failure-drill training, and the
rate of approve-without-change decisions.

### Requester Capture Is A Threat

A requester may provide a desired outcome or proposed intervention. That input
is useful context, but it must not become the conclusion. The case must
separate requester preference from independent analysis and challenge whether
the selected recommendation merely confirms a prior.

### Major Claims Need Triangulation Or A Deficit

A major claim supported by one dataset and one method may be valid, but it is
not strong by default. The case must look for independent lines of support,
convergence, divergence, and counter-evidence, or record a
single-line-evidence assurance deficit.

### Evidence Strength Is Independence, Not Count

PolicyOS has many methods, datasets, legal facts, and academic records. That
scale is valuable only when it increases independent failure-mode coverage. A
thousand evidence lines that share the same primary source, lineage,
identification strategy, author pool, legal interpretation, or preprocessing
assumption may collapse to one effective line. The case must report both raw
evidence-line count and effective independent evidence count.

### Portfolios Are Designed Before Execution

For every major claim, evidence is a predeclared portfolio per strand, not a
post-hoc list of successful runs. The portfolio contract must state which data
families, method families, specifications, disconfirming tests, synthesis
rules, and stopping rules will be used before producers execute. Selecting only
agreeing lines after execution is machine-assisted p-hacking and must fail
closeout.

### Disagreement Is Evidence

When evidence lines disagree, the system should not average the disagreement
away. It must cluster and explain divergence by source family, time period,
jurisdiction, method assumption, specification choice, data quality,
measurement semantics, and publication or selection bias. If convergence is
not adequate for the requested authority level, the output is a typed blocker
or wider uncertainty, not a polished mean.

### Synthesis Is A Method

Evidence synthesis has assumptions too: weighting, heterogeneity model,
publication-bias correction, certainty grading, and inclusion/exclusion rules.
The synthesis rule must be a runtime-owned method with refs and sensitivity
checks. A claim that changes sign or decision recommendation under reasonable
synthesis rules is fragile.

### N Is Earned, Not Assigned

The number of evidence lines is a function of authority level, observed
heterogeneity, effective independence, run budget, and stopping rule. Simple
claims may converge with a small portfolio. Complex policies may require
hundreds of raw lines, but closeout should reason over effective independent
lines and information saturation, not catalog size.

### Evidence Graphs Have Adversaries

Threats against the evidence graph include prompt injection, poisoned datasets,
stale indexes, malicious tenants, forged provenance, compromised plugins,
conflicting legal snapshots, local-client leakage, and insider mutation. The
Policy Design Case must carry integrity risk records and blockers for those
attacks.

### Jurisdiction Is A Graph

Many policy questions span national, regional, local, and supranational norms.
The legal layer must reconcile multi-jurisdiction authority, competence,
pre-emption, conflicts, and temporal validity instead of assuming one corpus.

### Proportionality Applies To The System Itself

High-authority analysis has a cost. The case should record compute cost,
elapsed time, human-review burden, external-provider cost, evidence depth, and
why the run budget is proportionate to the decision's public impact and risk.

### Complexity Is A Failure Mode

The case machinery itself can fail through schema migration errors, partial
case graphs, contradictory records, stale generated surfaces, operator
workarounds, or box-ticking. Each serious record family should expose maturity,
not only presence, and the system should maintain a self-FMEA for non-adversarial
failure modes.

### Core Invariants Need Formal Specs

CAS/event reconciliation, phase barriers, authority ordering, readiness
terminality, and same-input closure are concurrent state-machine properties.
They should be specified with lightweight formal methods where practical, such
as TLA+, PlusCal, or equivalent model checking.

### Reuse Existing Capability Before Building New Engines

Implementation plans derived from this decision must begin from the existing
capability map. A new portfolio engine, sensitivity framework, adversary,
calibration store, lifecycle loop, memory layer, Scholar retrieval path, or
agent-simulation abstraction is allowed only after the owner proves that the
existing module cannot emit the required case record with a scoped extension.

The default implementation posture is:

- `wire-existing` when a module already owns the runtime behavior and only
  needs a case-record projection;
- `extend-existing` when the runtime behavior exists but misses telemetry,
  metadata, closeout refs, or authority envelopes;
- `consolidate-existing` when several budget, cost, conflict, or calibration
  surfaces exist and the missing artifact is a unified ledger;
- `build-new` only when no credible owner exists.

## Capability Realization Map

This map is normative for implementation planning. It does not freeze module
boundaries, but it does identify the first owner that a plan must try to wire
before inventing a replacement.

| Target capability | Existing owner or surface | Status | Design implication |
| --- | --- | --- | --- |
| Runtime assurance-case and substrate quality authority | `src/polisyos/runtime/quality/assurance_case.py`, `authority*.py`, `semantic_binding.py`, `prompt_tool_ledger.py`, `performance_budget.py`, `human_review.py`, `approval.py`, `attestation.py`, `degradation.py`, `public_export.py`, `metamorphic_controls.py`, `phase_barriers.py`, `invariants.py`, `scorecard.py`, `schema_compat.py`, `effective_mode.py`, `source_truth.py`, `event_log.py`, `replay.py` | wire-existing / extend-existing | The Policy Design Case profiles and extends runtime quality records; implementation must not create a parallel serious-run case object or authority ledger. |
| Core governance and execution profiles | `src/polisyos/core/governance/profiles.py`; `src/polisyos/core/contracts/control.py`; `src/polisyos/runtime/quality/effective_mode.py` | wire-existing | Map research/governed/production authority levels to existing validation profiles, execution profiles, and effective-mode checks instead of inventing a second profile system. |
| Intent, policy candidate, objective, and critique surfaces | `src/polisyos/scientist/policy_design/schema.py`, `objectives.py`, `critic.py`, `search.py`, `output.py`; `src/polisyos/ir/governance/problem_frame.py` | extend-existing | Add canonical intent/requester-capture case records and authority refs around existing policy-design payloads. |
| Capability selection, mode, fallback, and budget-aware orchestration | `src/polisyos/scientist/orchestration/engine/*`; Foundry method-selection advisor; runtime quality ledgers | extend-existing | Add serious-run capability ledger projections; do not build a second router until existing orchestration cannot expose the needed duties. |
| Concept spine and multi-jurisdiction reconciliation | `src/polisyos/fabric/entity_resolution/*`; `src/polisyos/scientist/cross_graph/*`; `src/polisyos/ir/linker/*`, `registry`, `world`; `src/polisyos/ir/analytics/cross_graph.py`, `normative_arbitration.py` | wire-existing | Emit a per-run concept/jurisdiction spine over existing entity-resolution, cross-graph, gatherer, and IR linking results. |
| Legal authority retrieval and norm binding | `src/polisyos/lex/knowledge/*`, `legal_evaluation/*`, `normpack/*`, `provenance.py`; Lex production data; IR loading norm packs; legal/normative analytics surfaces | extend-existing | Bind Lex retrieval outputs to jurisdiction/time/context records instead of treating legal-shaped payloads as authority. |
| Data Forge production corpus builds and read snapshots | `src/polisyos/data_forge/*`; `src/polisyos/data_forge/read_api/*`; Data Forge kernel manifests, snapshots, quality gates, legal/catalog/academic/domain pipelines | wire-existing | Legal, dataset, academic, and domain production evidence should bind to Data Forge snapshot and read-API contracts; runtime plans should not reimplement corpus build provenance. |
| Fabric source evidence, provenance, and data quality | `src/polisyos/fabric/connectors/*`, `contracts/*`, `quality/*`, `federation/*`, `provenance`, `entity_resolution` | wire-existing | Expose source families, rights, quality, lineage, and field-level bindings as case records. |
| Scholar academic and grey-literature evidence | `src/polisyos/scholar/discover/*`, `search/*`, `freshness.py`, `orchestrator/*`, `provenance.py`, `api.py` | wire-existing | Treat Scholar as a first-class producer for literature strands: retrieval plan, scoring, freshness, citations, conflict links, and claim support. |
| Method catalog, method selection, and analytical validity | `src/polisyos/foundry/methods/catalog/*`, `methods/selection/*`, `methods/cost_model.py`, Foundry uncertainty and welfare modules | wire-existing | Use the existing catalog/advisor/cost/uncertainty stack as the method authority surface. |
| IR analytical evidence and proof surface | `src/polisyos/ir/analytics/falsification_report.py`, `evidence_bundle.py`, `transportability.py`, `privacy_transportability.py`, `partial_identification.py`, `recoverability.py`, `path_specific_identification.py`, `causal_ensemble.py`, `distributional.py`, `fairness*.py`, `mobility.py`, `welfare.py`, `strategic.py`, `negative_certificate.py`, `dual_certificate.py`, `certified_tightening.py`, `proof_composability.py` | wire-existing | Severe testing, identification, transportability, distributional/fairness, strategic-behavior, and certificate/proof records should project over IR analytics before new analytical proof surfaces are built. |
| Foundry method consensus, equivalence, and independence collapse | `src/polisyos/foundry/methods/consensus.py`; `src/polisyos/foundry/methods/components/consensus.py`; `src/polisyos/foundry/methods/equivalence/*` | extend-existing | Evidence convergence and effective independent evidence count should reuse method consensus/equivalence machinery, then add lineage and assumption collapse where missing. |
| Evidence portfolio, multiverse, sensitivity, and specification curves | `src/polisyos/scientist/methods/doe/*`; `src/polisyos/scientist/methods/discovery/*`; Foundry sensitivity catalog; IR causal ensemble and falsification surfaces | wire-existing | `evidence_portfolio_and_synthesis.v1` is primarily a case-record projection over DOE, discovery, Foundry sensitivity, IR ensemble, and falsification outputs. |
| Evidence synthesis, stability, and utility judging | `src/polisyos/scientist/methods/discovery/aggregator.py`, `stability.py`, `utility_judge.py`, `priors.py`, `prior_miner.py`, `active.py`; backtesting trust scorer | extend-existing | Add portfolio-level independence, effective-count, synthesis-rule, and certainty projections over existing aggregation and stability outputs. |
| Pre-publication adversarial challenge | `src/polisyos/scientist/policy_design/adversary.py`, `critic.py`, `objectives.py`, `search.py`; `src/polisyos/scientist/methods/backtesting/adversarial.py` | wire-existing | Persist adversarial scenario bundles and challenge-suite outcomes as assurance rebuttal/counter-evidence nodes. |
| Bounded explanation reliability and warrant diagnostics | `src/polisyos/berl/*`; `ExplanationBundle`, validation thresholds, empirical reliability bounds, local infidelity diagnostics | wire-existing | Assurance warrants and reviewer-facing explanations should include BERL reliability bounds where explanation trust influences claim acceptance or human oversight. |
| Human oversight and value-of-information escalation | `src/polisyos/scientist/governance/human_review/*` | extend-existing | Add review-effectiveness telemetry, exposure-order controls, dissent/change metrics, and rubber-stamp risk over existing review packets and decisions. |
| Calibration, ex-post validation, and track record | `src/polisyos/calibration/*`; `src/polisyos/scientist/governance/calibration*.py`; `src/polisyos/scientist/methods/backtesting/*` | wire-existing | Project calibration leaderboard, validation bundles, backtest matrix, and diagnostics into case-level calibration and ex-post ledgers. |
| Case lifecycle, reissue, supersession, withdrawal, and recall | `src/polisyos/scientist/governance/continuous/*`; claim lifecycle evidence modules | wire-existing | Use existing monitors, incident reports, reissue packets, withdrawal records, and validity reports as lifecycle authority. |
| Drift, degradation, readiness, incidents, and root-cause monitoring | `src/polisyos/ddm/*`; `DriftAndDegradationMonitor`, shift/degradation events, incident payloads, model-registry readiness records, registry gate decisions | wire-existing | Post-market monitoring, shift/degradation detection, root-cause evidence, and registry readiness should project over DDM. |
| Learning without cross-run contamination | `src/polisyos/scientist/orchestration/memory/*`; search lessons/failure-card registry | wire-existing | Keep learning warning-only unless case records prove scope, applicability, revocation, and contamination checks. |
| Objectives, welfare, social weights, uncertainty, and distributional effects | `src/polisyos/foundry/welfare/*`; `src/polisyos/foundry/uncertainty/*`; `src/polisyos/scientist/policy_design/objectives.py`; IR welfare/distributional analytics | wire-existing | Reuse existing welfare and uncertainty outputs as option/tradeoff records and distributional strands. |
| Agent-based simulation and synthetic worlds | `src/polisyos/foundry/agent_sim/*`; `src/polisyos/foundry/agent_sim/world/*` | wire-existing | Make agent simulation a distinct evidence-line family with different failure modes from econometrics and legal/literature evidence. |
| Conflict checking and social-weight compatibility roots | `src/polisyos/foundry/conflict_checker` and `social_weights` compatibility shims, backed by `foundry.validation.conflict_checker` and `foundry.welfare.social_weights` | wire-existing | Treat root packages as public shims; implementation plans should target canonical backing modules. |
| Run-cost proportionality and evidence-depth budget | `src/polisyos/runtime/quality/performance_budget.py`; `src/polisyos/foundry/methods/cost_model.py`, `methods/selection/advisor.py`, `src/polisyos/scientist/orchestration/engine/budget*.py`, DOE/cross-graph/search budgets | consolidate-existing | Build a unified case-level proportionality ledger over runtime performance budgets and existing cost/budget records rather than starting from an empty cost model. |
| External audit, PROV/SLSA export, standalone verification, and safe archive | `src/polisyos/core/audit/prov_json.py`, `_assembler_slsa.py`, `verifier.py`, `standalone_verifier_template.py`, `safe_tar.py` | wire-existing | External audit pass-rate and replayability should use existing portable audit archives, PROV mapping, SLSA attestation, and standalone verifier machinery. |
| Formal substrate invariant specification | Honest diagnostics substrate tests and validation tools; no TLA+/PlusCal owner yet | build-new | Add lightweight model specs for a small set of closeout-critical state-machine invariants. |

Implementation plans must mark each work item with one of these statuses. A
`build-new` item that overlaps a `wire-existing` owner is a design-review
failure unless the plan records a specific capability gap and rejected reuse
attempt.

## Target Operating Model

### 1. Policy Intent Envelope

The runtime must materialize a canonical intent envelope before domain routing.

Required authority:

- policy problem;
- desired outcome;
- proposed treatment/intervention;
- requester-preferred conclusion, if any;
- declared separation between requester preference and independent analysis;
- target population;
- jurisdiction;
- policy time and data time;
- affected stakeholders;
- constraints and objectives;
- user-supplied assumptions;
- requested output authority level;
- evidence contract expectations;
- tenant and authoring provenance;
- requester-capture risk and required challenge depth.

Primary diagnostic pressure: `PDD-010`, `PDD-092`, `PDD-071`.

### 2. Capability Selection Ledger

The router must record which capabilities are required, selected, skipped, or
blocked for the intent envelope.

Required authority:

- Lex retrieval duty;
- Fabric source-selection duty;
- Scholar retrieval, scoring, freshness, and citation duty;
- Foundry method-selection duty;
- Scientist analytic duty;
- compiler and publication duty;
- skipped capability reason;
- required input;
- allowed fallback policy;
- downstream impact.

Primary diagnostic pressure: `PDD-062`, `PDD-017`, `PDD-018`, `PDD-019`.

Realization: extend existing Scientist orchestration and Foundry selection
surfaces into a serious-run capability ledger. Scholar must be selectable as a
producer with explicit skipped-duty blockers; academic evidence must not be
hidden inside generic Scientist work. Requested authority levels should map to
existing execution profiles, core governance validation profiles, and runtime
effective-mode checks rather than creating a parallel mode taxonomy.

### 3. Concept Spine

The run must reconcile concepts before evidence producers execute.

Required authority:

- canonical concept ids;
- aliases and source terms;
- metric bindings;
- dataset and column bindings;
- legal concept bindings;
- method requirement bindings;
- objective and tradeoff bindings;
- geography/time/population semantics;
- unresolved concept blockers.

Primary diagnostic pressure: `PDD-007`, `PDD-011`, `PDD-047`, `PDD-003`,
`PDD-042`, `PDD-074`.

Realization: wire Fabric entity resolution, Scientist cross-graph alignment and
conflict modules, and IR linker/registry/world surfaces. The new artifact is
the per-run authority spine, not another independent concept registry unless
the existing surfaces fail a concrete requirement.

### 4. Legal Authority Layer

Lex must retrieve and bind legal norms, not merely validate legal-shaped input.

Required authority:

- legal corpus version and snapshot;
- query terms and concept refs;
- jurisdiction graph and `as_of` time;
- supranational, national, regional, and local authority levels when relevant;
- pre-emption, hierarchy, delegation, and conflict-resolution rules;
- candidate norms;
- applied norms;
- conflicts;
- competence/implementing authority;
- non-retrieval blocker when a legal store is missing or incompatible.

Primary diagnostic pressure: `PDD-001`, `PDD-043`.

Realization: wire Lex and IR norm-loading outputs into the same concept spine
and jurisdiction graph. Multi-jurisdiction conflicts should reuse existing
cross-graph and normative-arbitration surfaces before any legal-conflict engine
is rebuilt.

### 5. Production Data, Scholar, And Source Layer

Fabric must expose scenario-relevant data as inspectable, typed source-family
evidence. Scholar must expose scenario-relevant academic and grey-literature
evidence as inspectable, typed literature-family evidence. Both producers must
expose candidate source families for portfolio design, not only one selected
bundle.

Required authority:

- source family;
- dataset artifact;
- dictionary and schema;
- row/coverage/time/geography metadata;
- quality and missingness profile;
- source contract and rights;
- freshness and retention semantics;
- lineaged transforms to claim-support features;
- source lineage and primary-source ancestry;
- data-family independence tags;
- candidate inclusion/exclusion reason for portfolio design;
- known shared assumptions with other data lines;
- literature corpus or web evidence bundle id;
- Scholar query graph, provider traces, source scoring, snippets, citations,
  freshness, and conflict/support links;
- academic source-family independence tags;
- publication, author, institution, and corpus-lineage ancestry where known.

Primary diagnostic pressure: `PDD-002`, `PDD-008`, `PDD-014`, `PDD-042`,
`PDD-052`, `PDD-073`, `PDD-102`, `PDD-045`, `PDD-082`.

Realization: wire Fabric source/provenance/quality modules and Scholar
discover/search/orchestrator/freshness/provenance modules. Bind production
corpus evidence to Data Forge snapshot manifests, quality gates, and read-API
surfaces for legal, catalog, academic, and domain data. Academic evidence is
not a note in a method result; it is a producer-owned strand that can support,
weaken, or rebut a claim.

### 6. Method Selection And Analytical Validity Layer

Foundry must turn method expectations into selected method DAG nodes before
execution. For major empirical claims, it must select candidate method families
for a portfolio, not only one method.

Required authority:

- candidate method families;
- selected method family;
- rejected method families and reasons;
- method-family independence tags;
- assumptions;
- identification requirements;
- uncertainty and sensitivity plan;
- missingness handling;
- external validity or transferability limits;
- defensible specification space;
- invalid or redundant specification exclusions;
- cheap screening versus confirmatory execution tier;
- method-result refs that final claims can consume.

Primary diagnostic pressure: `PDD-004`, `PDD-049`, `PDD-074`, plus deferred
Pass 2 diagnostics for transferability and uncertainty.

Realization: wire Foundry method catalog, selection advisor, cost model,
uncertainty, welfare, sensitivity, causal/econometrics/simulation catalog
families, agent-simulation world outputs, and IR analytics for identification,
transportability, causal ensembles, falsification, and certified proof
surfaces. For complex policy cases, agent-based simulation is a distinct method
family with independent failure modes, not a fallback label for weak empirical
evidence.

### 7. Evidence Portfolio And Synthesis Layer

The case must design and execute an evidence portfolio for each major claim and
strand before the claim can be production-grade.

Portfolio hierarchy:

`major claim -> evidence strand -> evidence portfolio -> evidence line`

An evidence strand is a dimension of support, such as legal authority,
causality, effect magnitude, distributional impact, implementation feasibility,
cost, robustness, academic consensus, contradiction, or monitoring feasibility.
An evidence line is a specific combination of method, dataset, assumptions,
specification, legal or academic source, producer, and execution context.

Required authority:

- strand definitions and required authority level;
- predeclared portfolio design;
- candidate data and method families;
- inclusion and exclusion criteria;
- defensible specification space;
- disconfirming evidence lines;
- evidence independence map;
- raw evidence-line count;
- effective independent evidence count;
- multiverse or specification-curve report;
- convergence, divergence, and cluster explanation;
- synthesis method and sensitivity to synthesis rules;
- heterogeneity and publication-bias diagnostics;
- GRADE-like certainty or equivalent evidence-body rating;
- stopping rule and information saturation result;
- run-cost proportionality for the portfolio.

Primary diagnostic pressure: `PDD-002`, `PDD-003`, `PDD-004`, `PDD-005`,
`PDD-042`, `PDD-049`, `PDD-052`, `PDD-073`, `PDD-074`, `PDD-102`, plus
deferred Pass 2 diagnostics for claim validity, extraction, measurement,
strategic behavior, and external validity.

Realization: wire Scientist DOE (`SensitivityPlan`, `ScenarioSweep`,
`AblationPlan`, `AdversarialPlan`, sampling, calibrated uncertainty, coverage
benchmarks, stress reports), Scientist discovery (portfolio execution,
priors, active disambiguation, aggregation, stability, utility judging), Foundry
sensitivity methods, Foundry consensus/equivalence, IR causal-ensemble and
falsification surfaces, Scholar evidence bundles, and backtesting trust
outputs. The missing product is the portfolio case record and
independence/synthesis projection, not a third sensitivity framework.

### 8. Option, Objective, And Tradeoff Layer

The Policy Design Case must represent policy options and their comparison
against a baseline.

Required authority:

- baseline/no-action case;
- candidate options;
- rejected options;
- objective function;
- tradeoff weights and source;
- budget and implementation constraints;
- distributional effects;
- qualitative non-monetized effects;
- risk and uncertainty records.

Primary diagnostic pressure: `PDD-049`, `PDD-010`, `PDD-047`, `PDD-074`.

Realization: wire Foundry welfare/social-weights, Foundry uncertainty,
optimization/policy-welfare catalog methods, and Scientist policy-design
objective channels. Distributional, fairness, mobility, endogenous-inequality,
and welfare strands should also project over IR analytics where those modules
already own the analytical form. Root compatibility shims should route to the
canonical Foundry backing modules.

### 9. Claim Compiler

The final claim compiler must produce evidence-bearing claims, not unsupported
recommendation prose.

Required authority per major claim:

- claim id and text;
- assurance-case node id;
- policy concept refs;
- legal norm refs;
- evidence portfolio refs by strand;
- Scholar academic evidence refs or literature-deficit refs when literature is
  in scope;
- evidence independence map refs;
- multiverse/specification-curve refs;
- disconfirming evidence ledger refs;
- evidence synthesis report refs;
- objective/tradeoff refs;
- uncertainty refs;
- numerical semantics refs;
- argument strategy;
- warrant explaining why evidence supports the claim;
- assumptions and applicability limits;
- independent support lines;
- convergence or divergence assessment;
- effective independent evidence count;
- rebuttal and counter-evidence refs;
- assurance-deficit refs;
- implementation and monitoring refs when in scope;
- blocker refs when evidence cannot support the claim.

Primary diagnostic pressure: `PDD-005`, `PDD-006`, `PDD-052`, `PDD-067`,
`PDD-093`.

Realization: final claims should consume portfolio, Scholar, Foundry,
Scientist, Lex, and Fabric refs already emitted by upstream producers. The
compiler may mint blockers and argument nodes; it must not synthesize missing
producer evidence from prose.

### 10. Assurance Argument And Challenge Layer

The case must make the reasoning between evidence and claims explicit and
challengeable.

Required authority:

- assurance-case profile version;
- mapping to SACM/CAE/GSN concepts;
- top claim, subclaim, context, assumption, argument, evidence, and deficit
  nodes;
- warrant text or structured warrant refs;
- bounded explanation reliability refs when a warrant or explanation is used
  to support reviewer trust or claim acceptance;
- rebuttal/counter-evidence nodes;
- triangulation and convergence matrix;
- portfolio adequacy assessment;
- single-line-evidence deficits;
- pre-publication adversarial challenge results;
- requester-capture challenge result;
- unresolved assurance deficit register.

Primary diagnostic pressure: `PDD-005`, `PDD-006`, `PDD-049`, `PDD-052`,
`PDD-058`, `PDD-081`, `PDD-084`, `PDD-095`, plus deferred Pass 2 diagnostics
for adversarial, legitimacy, strategic behavior, and overtrust controls.

Realization: wire existing policy-design adversary, critic, objectives, search,
backtesting adversarial suites, runtime assurance-case records, IR proof and
certificate surfaces, and BERL explanation bundles into assurance-case warrant,
rebuttal, counter-evidence, and challenge nodes. Pre-publication challenge
should be an evidence projection over these modules before any new red-team
subsystem is invented.

### 11. Legitimacy, Judgement, Independence, And Integrity Layer

The case must prove how non-data evidence, stakeholder input, independent
review, and integrity threats were handled before a recommendation is
publication-eligible.

Required authority:

- stakeholder map;
- consultation plan and evidence;
- public comment and objection records;
- response-to-comment reasoning;
- structured expert judgement records;
- elicitation method, expert provenance, conflicts, and uncertainty;
- producer independence and separation-of-duty attestation;
- effective human oversight ledger;
- reviewer exposure order, time spent, dissent, override, and change requests;
- approve-without-change rate and rubber-stamp risk;
- model/method/claim conflict records;
- evidence-graph threat model;
- self-FMEA and non-adversarial failure modes;
- record-family maturity profile;
- integrity probes and attack-specific blockers;
- run cost and proportionality rationale.

Primary diagnostic pressure: `PDD-028`, `PDD-029`, `PDD-033`, `PDD-039`,
`PDD-058`, `PDD-081`, `PDD-084`, `PDD-085`, `PDD-095`, `PDD-102`, plus
deferred Pass 2 diagnostics for legitimacy, overtrust, strategic behavior, and
appeals.

Realization: extend existing human-review packets, queues, decisions, audit
events, oversight policy, and value-of-information escalation with telemetry
that proves effectiveness. Integrity and self-FMEA records should attach to
the same review/governance graph, not to a separate quality checklist.

### 12. Case Lifecycle, Ex-Post Learning, And Calibration Layer

The published case must remain a living governed object after first release.

Required authority:

- stable case id and revision id;
- supersession, amendment, withdrawal, recall, and retraction events;
- implementation status and actual-outcome observations;
- claim-to-outcome mapping;
- evaluation design and ex-post evaluation result;
- drift, shift, degradation, incident, readiness, and root-cause monitoring
  evidence;
- realized-versus-predicted effect comparison;
- explanation of forecast error and missed assumptions;
- calibration ledger by method, domain, jurisdiction, data class, and evidence
  mode;
- reversal, appeal, and contested-decision outcomes;
- learning record that updates future method/uncertainty priors without
  contaminating unrelated runs.

Primary diagnostic pressure: `PDD-030`, `PDD-031`, `PDD-032`, `PDD-040`,
`PDD-045`, `PDD-067`, `PDD-082`, `PDD-086`, `PDD-096`, plus deferred Pass 2
diagnostics for monitoring, recovery, legitimacy, archive replay, and memory.

Realization: wire continuous governance monitors, incident reports, reissue
packets, withdrawal records, validity reports, calibration governance,
calibration validation, calibration leaderboard, shared calibration
diagnostics, backtesting, DDM shift/degradation/readiness/incident evidence,
and reflexive memory. Learning remains warning-only unless scope,
applicability, revocation, and contamination checks are recorded.

### 13. Governance And Publication Layer

Publication authority must be derived from the Policy Design Case and the
honest diagnostics substrate.

Required authority:

- tenant and full evidence-graph ownership;
- CAS manifests and producer metadata;
- approval and override packet identity;
- human review authority;
- privileged-action ledger;
- signing trust lifecycle;
- release and topology provenance;
- schema migration compatibility;
- dependency rights;
- privacy/security and local-client evidence controls;
- public export redaction and semantic-preservation proof;
- archive/replay/retention/deletion policy;
- case lifecycle state and publication authority;
- retraction/recall authority when a published case is later invalidated.

Primary diagnostic pressure: `PDD-022`, `PDD-023`, `PDD-024`, `PDD-025`,
`PDD-028`, `PDD-029`, `PDD-030`, `PDD-033`, `PDD-039`, `PDD-040`, `PDD-041`,
`PDD-058`, `PDD-071`, `PDD-072`, `PDD-075`, `PDD-076`, `PDD-079`, `PDD-080`,
`PDD-081`, `PDD-084`, `PDD-085`, `PDD-086`, `PDD-089`, `PDD-091`, `PDD-092`,
`PDD-093`, `PDD-094`, `PDD-095`, `PDD-096`, `PDD-102`.

Realization: the honest diagnostics substrate remains the closeout authority
for CAS/event reconciliation, mode, fallback, schema, phase, scorecard, and
readiness. Policy-domain governance should extend `runtime/quality` records
for publication, rights, review, lifecycle, public export, and performance
budget evidence, and should use `core/audit` for PROV/SLSA export, standalone
verification, and safe audit archives without weakening substrate invariants.

## Authority Boundaries

| Surface | Role | Boundary |
| --- | --- | --- |
| Policy Design Case | Primary serious-run product | Owns the connected policy argument and evidence graph. |
| Honest diagnostics substrate | Closeout authority | Enforces evidence identity, mode, fallback, schema, provenance, phase, and readiness. |
| Lex | Legal producer | Retrieves and binds legal authority; cannot publish policy decisions. |
| Fabric | Data producer | Selects and validates source evidence; cannot infer final policy claims. |
| Scholar | Academic evidence producer | Retrieves, scores, freshens, cites, and links literature evidence; cannot replace data, legal, or method authority. |
| Foundry | Method producer | Selects and runs analytical methods; cannot backfill legal or data authority. |
| Scientist | Analytic orchestrator | Integrates evidence and emits analytic artifacts; skipped duties must become blockers. |
| Claim compiler | Claim authority producer | Mints final claim refs or blockers; cannot silently omit support. |
| Assurance argument case | Reasoning authority | Explains why evidence supports claims; must expose warrants, assumptions, rebuttals, and deficits. |
| Adversarial challenge | Pre-publication challenge evidence | Tests selected claims, requester priors, and evidence convergence before publication. |
| Consultation and judgement records | Legitimacy evidence | Record stakeholder input and structured expert judgement; cannot masquerade as observed empirical data. |
| Independence attestation | Conflict-control evidence | Proves separation of duties and discloses producer conflicts. |
| Effective human oversight ledger | Review-quality evidence | Measures whether human review changed, challenged, delayed, or rubber-stamped the case. |
| Calibration ledger | System track-record evidence | Measures historical reliability; cannot excuse a weak current case. |
| Case lifecycle ledger | Post-publication authority | Records amendment, supersession, recall, withdrawal, retraction, and ex-post reassessment. |
| Self-FMEA and maturity profile | System reliability evidence | Records non-adversarial failure modes and maturity of each record family. |
| Scorecard/readiness | Gate readers | Enforce contracts; cannot produce missing domain evidence. |
| Approval/publication | Governance consumers | May approve only case-backed, non-overridable, signed authority. |
| Dashboard/clients | Projection and authoring surfaces | Must label local, queued, draft, redacted, projection-only, stale, or contested state. |

## Minimum Policy Design Case Record Families

The case should not become a checklist of files. The minimum unit is a record
family: a coherent authority surface with maturity, deficits, and subrecords.
Each family should be CAS-addressed, schema-versioned, tenant-scoped,
runtime-event-linked, substrate-readable, and exportable or mappable to
assurance-case concepts where relevant.

| Family | Required subrecords or facets |
| --- | --- |
| `intent_authoring_and_capture_risk.v1` | Intent envelope, authoring provenance, requester preference, requester-capture risk, challenge depth. |
| `capability_mode_and_fallback_selection.v1` | Capability ledger, mode ledger, fallback/degradation ledger, skipped-duty blockers. |
| `concept_and_jurisdiction_spine.v1` | Concept spine, ontology reconciliation, multi-jurisdiction hierarchy, conflict/pre-emption rules. |
| `legal_authority_and_competence.v1` | Legal retrieval report, normative applicability, institutional competence, unresolved legal blockers. |
| `data_source_semantic_lineage.v1` | Source selection, Data Forge snapshot/read-API binding, dataset binding, dictionary/schema, field/transform lineage, source rights. |
| `scholar_academic_evidence.v1` | Research intent, Scholar query graph, provider traces, source scoring, citations, snippets, freshness, conflict/support links, literature-family independence. |
| `numeric_time_and_geography_semantics.v1` | Unit, currency, price base, exchange, inflation, calendar, geography, freshness, retention. |
| `method_selection_and_validity.v1` | Candidate methods, selected/rejected methods, assumptions, uncertainty, sensitivity, identification, transportability, falsification, validity limits. |
| `evidence_portfolio_and_synthesis.v1` | Portfolio design, independence map, method-equivalence collapse, effective independent count, multiverse/specification curve, disconfirming ledger, convergence/consensus report, synthesis report, certainty rating, stopping rule. |
| `structured_judgement_and_consultation.v1` | Expert elicitation, judgement provenance, stakeholder map, consultation evidence, response-to-comment. |
| `options_objectives_and_tradeoffs.v1` | Baseline, alternatives, rejected options, objective function, distributional effects, proportionality. |
| `claim_argument_evidence_case.v1` | SACM/CAE/GSN profile, runtime assurance-case profile, claims, arguments, warrants, bounded explanation reliability where applicable, evidence refs, rebuttals, counter-evidence, deficits, triangulation. |
| `implementation_monitoring_and_evaluation.v1` | Implementation contract, monitoring plan, evaluation design, pre-publication challenge, DDM shift/degradation/root-cause/readiness evidence, post-market monitoring. |
| `human_oversight_independence_and_review.v1` | Producer independence, reviewer independence, review effectiveness, dissent, override, rubber-stamp risk. |
| `integrity_self_fmea_and_maturity.v1` | Evidence-graph threat model, non-adversarial self-FMEA, record-family maturity, partial-case contradictions. |
| `lifecycle_ex_post_and_calibration.v1` | Case lifecycle, supersession, recall/retraction, ex-post outcomes, reassessment, calibration track record. |
| `publication_trust_and_external_governance.v1` | Approval, override, signing, release, topology, dependency rights, public export, PROV/SLSA audit archive, standalone verifier, archive/replay, local-client compliance. |
| `best_in_class_benchmarking.v1` | External audit, human-team benchmark, reversal/retraction metrics, calibration metrics, claim substantiation, triangulation, operator time-to-root-cause, and cost/proportionality metrics. |
| `formal_substrate_invariant_spec.v1` | Formal or model-checked specs for authority ordering, phase barriers, same-input closure, CAS/event reconciliation, terminal readiness. |

Every family should expose a maturity level: `missing`, `stub`, `partial`,
`argument_complete`, `evidence_complete`, `independently_challenged`,
`externally_auditable`, or `validated_ex_post`. Serious closeout may accept a
lower maturity only when the family records an explicit assurance deficit and
the requested authority level permits that deficit.

## Diagnostic Synthesis

| Diagnostic pressure | Design consequence |
| --- | --- |
| `PDD-010`, `PDD-062`, `PDD-007`, `PDD-011`, `PDD-047` | Build the intent envelope, capability ledger, and concept spine before domain execution. |
| `PDD-001`, `PDD-043` | Legal evidence must be retrieval-backed and jurisdiction/time scoped. |
| `PDD-002`, `PDD-003`, `PDD-008`, `PDD-014`, `PDD-042`, `PDD-052`, `PDD-074` | Data evidence must be source-family, field, transform, numeric, claim-level, and portfolio-ready, not manifest-role level; academic evidence must flow through Scholar with retrieval/scoring/freshness authority. |
| `PDD-004`, `PDD-049` | Method and objective authority must be selected before execution and tied to alternatives, tradeoffs, and portfolio specifications. |
| `PDD-005`, `PDD-006` | Final claims must be compiled with portfolio refs, synthesis refs, argument-bearing refs, warrants, rebuttals, assurance deficits, or blockers; empty artifacts cannot pass. |
| `PDD-017`, `PDD-018`, `PDD-019`, `PDD-071`, `PDD-086` | Capability, mode, fallback, config, and evidence-mode boundaries need first-class ledgers. |
| `PDD-022`, `PDD-023`, `PDD-024`, `PDD-025`, `PDD-041` | Tenant/CAS ownership must cover the full evidence graph, not only root run-index artifacts. |
| `PDD-028`, `PDD-029`, `PDD-030`, `PDD-058`, `PDD-095`, `PDD-096` | Approval, override, effective human review, privileged action, signatures, and recall/retraction need one publication authority model. |
| `PDD-031`, `PDD-032`, `PDD-040`, `PDD-045`, `PDD-082` | Replay, resilience, partial state, freshness, retention, and deletion must be designed together. |
| `PDD-067`, `PDD-089`, `PDD-091`, `PDD-092`, `PDD-093`, `PDD-094` | Human-facing surfaces must preserve semantic truth and local evidence compliance. |
| `PDD-072`, `PDD-073`, `PDD-075`, `PDD-076`, `PDD-079`, `PDD-080`, `PDD-081`, `PDD-084`, `PDD-085`, `PDD-102` | Deployment, release, generated surfaces, manual gates, tools, plugins, and external dependencies must be closeout evidence. |
| Pass 2 legitimacy, monitoring, and archive diagnostics | Ex-post outcomes, consultation, contestability, calibration, recall, and archive replay must be first-class future evidence, not optional narrative. |
| Cross-cutting Pass 1B governance diagnostics | Producer independence, requester-capture controls, evidence-graph threat models, self-FMEA, and run proportionality should be closeout records because they affect trust in every domain claim. |
| Portfolio/multiverse design gap | A major empirical claim backed by one dataset and one method is not production-grade unless it records an accepted single-line-evidence deficit. |
| Repository capability map | Many target capabilities already exist; implementation plans should expose runtime quality, core audit, Data Forge, DDM, BERL, IR analytics, Foundry consensus/equivalence, core governance profiles, DOE, discovery, adversary, backtesting, calibration, continuous governance, memory, Scholar, welfare, uncertainty, and agent simulation as case records before building replacements. |

## Best-In-Class Success Criteria

The phrase "best-in-class" must be falsifiable. PolicyOS should measure itself
against external auditability, policy-quality outcomes, operational rigor, and
learning performance.

| Dimension | Candidate metric |
| --- | --- |
| Evidence completeness | Share of serious cases whose required records are complete, current, CAS-backed, and runtime-event-linked. |
| External audit pass rate | Share of sampled cases whose assurance argument, evidence refs, warrants, rebuttals, and deficits can be replayed and verified without private operator context. |
| Claim substantiation | Share of major claims with legal, data, method, objective, numerical, implementation, argument, triangulation, and deficit refs. |
| Argument challenge quality | Share of major claims that survived documented counter-evidence, rebuttal, requester-capture, and adversarial challenge steps. |
| Triangulation | Share of major claims with independent convergent support lines, or explicit accepted single-line-evidence deficits. |
| Effective independence | Ratio of effective independent evidence lines to raw evidence lines, after collapsing shared source lineage, assumptions, authorship, method family, and preprocessing. |
| Multiverse robustness | Share of major empirical claims whose direction and decision implication survive the predeclared defensible specification space and synthesis-rule sensitivity checks. |
| Disconfirming severity | Share of major claims that survived predeclared disconfirming evidence lines with enough power or probativeness to reveal meaningful failure. |
| Evidence synthesis certainty | Distribution of claim-level certainty ratings after heterogeneity, risk of bias, indirectness, imprecision, and publication-bias checks. |
| Effective oversight | Reviewer time, dissent/change rate, override rate, exposure-order bias checks, approve-without-change rate, and failure-drill performance. |
| Calibration | Prediction interval coverage, forecast bias, and realized-versus-predicted effect error by domain and method family. |
| Reversal and retraction | Rate, severity, time-to-detect, and cause of amended, superseded, withdrawn, recalled, or retracted cases. |
| Consultation quality | Share of affected-stakeholder groups represented, response-to-comment coverage, and unresolved objection severity. |
| Decision cycle proportionality | Run cost, elapsed time, human-review burden, and evidence depth relative to decision risk and public impact. |
| Case-system reliability | Self-FMEA coverage, partial-case contradiction rate, schema migration incident rate, maturity distribution, and box-ticking escape rate. |
| Formal invariant coverage | Share of substrate-critical invariants covered by lightweight formal specs or model checks and runtime trace conformance checks. |
| Operator explainability | Time from closeout failure to owner, missing input, upstream cause, downstream impact, and next command. |
| Replay and archive | Time-to-replay, replay determinism, long-horizon restore success, and dependency-rights availability. |
| Human-team benchmark | Quality, speed, error rate, and auditability compared with expert policy teams on matched tasks. |

These metrics should not become vanity targets. They should drive calibration,
process changes, domain remediation, and case lifecycle actions.

## Consequences

### Positive

- PolicyOS can explain why a policy recommendation is legally authorized,
  empirically supported, methodologically valid, implementable, monitorable,
  publishable, and contestable.
- PolicyOS can learn whether earlier claims were right, update its track
  record, and surface method/domain calibration limits in future cases.
- Domain remediation can be sequenced around durable records instead of
  component-local patches.
- External guidance on appraisal, evaluation, regulatory analysis, and
  analytical quality becomes machine-checkable rather than prose-only.
- The dashboard and public artifacts can become more trustworthy because they
  read a connected case instead of stitching together projections.
- Pass 2 behavioral diagnostics will have concrete evidence contracts to test.

### Tradeoffs

- More typed blockers will appear before the user sees a polished final answer.
- The system will need more schemas, migrations, compatibility gates, and
  generated-surface discipline.
- Some current convenience paths will lose authority until they emit proper
  ledgers.
- Policy design may become slower for high-authority runs, but faster to audit,
  replay, and improve.
- Teams must distinguish exploratory assistance from serious production policy
  design at the mode and evidence-contract level.
- Ex-post outcome ingestion creates governance duties after publication; the
  system must budget for long-lived monitoring and case maintenance.
- Calibration records may expose that some domains, methods, or data classes
  are weaker than current narratives imply. That is a feature, not a defect.

## Anti-Patterns Rejected

PolicyOS should explicitly reject these designs:

- treating a scorecard pass as a substitute for missing legal/data/method refs;
- allowing generic metrics to replace requested outcomes without a blocker;
- allowing manifest roles to count as scenario source families;
- choosing methods after execution by reading whatever artifact exists;
- compiling final claims first and grounding them later;
- using local browser state, collaboration locks, or optimistic queues as
  authority;
- labeling public packets as verified through frontend-only hashes;
- treating unsigned, stale, unknown-rights, or dependency-unknown evidence as
  acceptable in serious closeout;
- making public documents official-looking before template, jurisdiction,
  redaction, semantic, and signing authority are proven;
- treating a published case as immutable when later outcomes invalidate it;
- using expert judgement while presenting it as observed data;
- claiming uncertainty without measuring historical calibration;
- ignoring stakeholder objections because they are not data artifacts;
- allowing one producer to select methods, generate claims, and certify the
  result without independence evidence;
- treating a human approval click as effective oversight without measuring
  review quality;
- treating a requester-preferred intervention as a neutral analytical premise;
- reporting one dataset plus one method as a strong major claim without
  triangulation or a single-line-evidence deficit;
- treating raw evidence count as strength when the effective independent count
  collapses under shared lineage or assumptions;
- using Scholar-derived academic snippets as narrative color while omitting
  retrieval plan, freshness, source scoring, citation lineage, support/conflict
  links, and independence collapse;
- running a large multiverse and then selecting only agreeing specifications;
- averaging away divergent evidence clusters without explaining why they
  diverge;
- treating synthesis as neutral when the conclusion depends on weighting,
  heterogeneity, or publication-bias assumptions;
- adding record files until the case passes mechanically while the argument
  remains weak;
- building a parallel Policy Design Case, profile system, audit verifier,
  drift monitor, explanation-reliability layer, Data Forge provenance path, or
  method-independence engine when runtime quality, core governance, core audit,
  DDM, BERL, Data Forge, IR analytics, or Foundry consensus/equivalence already
  own the first implementation surface;
- rebuilding DOE, discovery, adversary, calibration, continuous governance,
  memory, cost, Scholar, or agent-simulation machinery without first proving
  the existing owner cannot emit the required case record;
- spending unbounded compute, provider, or analyst effort on a low-impact
  decision without proportionality evidence.

## Relationship To Honest Diagnostics Substrate

The honest diagnostics substrate answers whether serious evidence can close.
This decision answers what policy-design evidence must exist.

The substrate should remain domain-neutral:

- authority envelopes;
- CAS/event reconciliation;
- mode and fallback ledgers;
- phase barriers;
- schema compatibility;
- invariant ownership;
- scorecard/readiness semantics.

In this repository the substrate's physical policy-facing owner is primarily
`src/polisyos/runtime/quality`. Domain plans should first add projections,
schema facets, and authority refs to those runtime quality modules before
adding a separate Policy Design Case package.

The Policy Design Case should be domain-semantic:

- policy concepts;
- legal norms;
- source families;
- Scholar research evidence bundles;
- methods;
- evidence portfolios;
- specification curves;
- synthesis reports;
- options;
- tradeoffs;
- claims;
- implementation;
- monitoring;
- consultation;
- structured judgement;
- ex-post outcomes;
- calibration;
- case lifecycle;
- publication.

Domain evidence should also preserve its build and audit roots: production
corpora bind through Data Forge snapshots and read APIs; external auditability
binds through `core/audit` PROV/SLSA/verifier archives; post-publication
monitoring binds through DDM; warrant reliability binds through BERL when
explanations are used as decision support.

The two models meet at the evidence authority envelope. Every Policy Design
Case record must be substrate-readable, but the substrate should not embed
domain policy theory in generic closeout logic.

The capability realization map is the bridge between those layers and the
existing repository. It tells implementation plans which domain module should
emit or project each case record while preserving substrate-neutral closeout.

## Open Questions

1. Should the policy concept spine be implemented as one physical registry or
   as a reconciled view over multiple registries with one per-run authority
   artifact?
2. How much of the option comparison case should be generated by default for
   research runs versus required only for governed/production runs?
3. Which distributional-effect categories should be mandatory by policy domain,
   and which should be scenario-configured?
4. What is the minimum acceptable institutional competence model before
   recommendations can be public-facing?
5. Should authoring provenance include raw prompts in encrypted/private CAS, or
   only salted hashes plus sanitized summaries?
6. Which external dependency rights should be non-overridable blockers versus
   reviewable warnings in research profiles?
7. What public contestability contract belongs in the core case before Pass 2
   legitimacy diagnostics run?
8. What minimum ex-post observation window is required before a policy claim can
   be marked confirmed, refuted, superseded, or inconclusive?
9. Which calibration metrics should block future high-authority runs when a
   domain or method family has a weak historical track record?
10. Which structured expert judgement protocols are acceptable for governed
    runs, and who can qualify as an expert?
11. How should multi-jurisdiction norm conflicts be represented when legal
    authority is genuinely unresolved rather than merely missing?
12. Which best-in-class benchmark tasks should compare PolicyOS with expert
    human policy teams?
13. Should PolicyOS use SACM as its canonical interchange format and CAE/GSN as
    profiles, or keep an internal schema with required exporters?
14. Which assurance-deficit classes may be accepted in research, governed, and
    production modes?
15. What minimum human-review telemetry proves effective oversight without
    turning review into surveillance theater?
16. Which requester-capture challenge failures are non-overridable blockers?
17. Which substrate invariants deserve TLA+/PlusCal or equivalent model checks
    before implementation proceeds?
18. What minimum portfolio maturity is required for research, governed, and
    production major claims?
19. Which method/data/source-lineage features should collapse raw evidence
    lines into one effective independent line?
20. What stopping rules should govern information saturation for low, medium,
    and high-impact policy claims?
21. Which evidence-synthesis certainty framework should PolicyOS use as the
    default outside health-policy domains: GRADE-like, domain-specific, or a
    PolicyOS profile?
22. Which Scholar source classes, freshness policies, citation-quality scores,
    and conflict thresholds are mandatory for academic evidence strands in
    research, governed, and production modes?
23. Which existing module owners are sufficient as authoritative case-record
    producers, and which require explicit facade or projection packages?
24. Which agent-simulation and synthetic-world evidence lines are independent
    enough from observational and econometric evidence to raise effective
    evidence strength rather than only raw evidence count?
25. Which `runtime/quality/assurance_case.py` fields become canonical Policy
    Design Case fields, and which policy-specific records remain extensions?
26. How exactly do research/governed/production authority levels map to core
    governance profiles, execution profiles, and runtime effective-mode checks?
27. Which DDM shift, degradation, readiness, incident, and root-cause events
    are mandatory for post-publication monitoring by authority level?
28. Which BERL reliability bounds and local-infidelity thresholds should be
    shown to reviewers or block claim acceptance?
29. What Data Forge snapshot and read-API contracts are sufficient to prove
    corpus identity for legal, dataset, academic, and domain evidence?

## ADR Extraction Candidates

This design decision should be split into ADRs after the first remediation plan
confirms the record boundaries:

- Policy Intent Envelope And Capability Selection Ledger.
- Capability Realization Map And Reuse-First Wiring.
- Runtime Quality Assurance Case Profile And Policy Design Case Extension.
- Policy Concept Spine And Ontology Reconciliation.
- Legal Authority Retrieval And Institutional Competence.
- Production Data, Scholar Evidence, Semantic Binding, And Numeric Semantics.
- Foundry Method Selection And Validity Contract.
- Evidence Portfolio Design, Independence Map, Multiverse, And Synthesis.
- DDM Post-Market Monitoring, Drift, Degradation, And Incident Evidence.
- BERL Bounded Explanation Reliability For Assurance Warrants.
- Core Audit PROV/SLSA Archive And Standalone Verification.
- Core Governance Profile Mapping For Policy Authority Levels.
- Data Forge Snapshot Binding And Read-API Corpus Provenance.
- Policy Option, Objective, Tradeoff, And Distributional Case.
- Assurance-Case Profile, Argument Warrants, Rebuttals, And Deficits.
- Final Claim Evidence Contract And Decision Compiler.
- Structured Judgement, Consultation, And Legitimacy Evidence.
- Effective Human Oversight And Automation Bias Controls.
- Producer Independence, Requester Capture, And Evidence-Graph Threat Model.
- Triangulation, Counter-Evidence, And Pre-Publication Challenge.
- Self-FMEA, Case Maturity, And Formal Substrate Invariants.
- Case Lifecycle, Supersession, Retraction, And Recall.
- Ex-Post Outcome, Claim Reassessment, And Calibration Ledger.
- Publication, Signing, Client Evidence, And Public Export Authority.
- External Dependency Rights And Runtime Governance Ledger.
- Run Cost, Proportionality, And Best-In-Class Benchmarking.

## Promotion Criteria

Promote this document to accepted ADRs only when:

- each minimum Policy Design Case record has a schema owner;
- each minimum Policy Design Case record maps to an owning module or an
  accepted `build-new` gap in the capability realization map;
- implementation plans fail design review when they rebuild a `wire-existing`
  capability without a recorded rejected-reuse finding;
- the Policy Design Case extends or profiles `runtime/quality/assurance_case.py`
  and does not introduce a parallel serious-run case authority;
- authority-level mapping reuses core governance profiles, execution profiles,
  and runtime effective-mode checks;
- Data Forge snapshot/read-API bindings prove corpus identity for production
  legal, dataset, academic, and domain evidence;
- DDM, BERL, and core audit have explicit projections where post-market
  monitoring, warrant reliability, or external auditability are in scope;
- the claim argument case has a documented SACM/CAE/GSN mapping or an explicit
  reason for rejecting that mapping;
- at least one A1-A6 implementation slice emits runtime-owned records;
- readiness can fail when a required Policy Design Case record is missing;
- readiness can fail when a major claim has evidence refs but no argument,
  warrant, rebuttal/counter-evidence assessment, or accepted assurance deficit;
- readiness can fail when a major empirical claim lacks a predeclared evidence
  portfolio, independence map, specification curve or accepted waiver,
  disconfirming evidence ledger, synthesis report, and stopping-rule result;
- dashboard projections label the new authority states correctly;
- Pass 2 deferred diagnostics can reference concrete records and commands;
- the case can represent ex-post outcomes and supersession without rewriting
  historical authority;
- calibration and benchmark metrics are defined for at least one implemented
  policy domain;
- at least one substrate-critical invariant is specified or model-checked
  outside unit tests;
- no ADR weakens the existing honest diagnostics substrate invariants.
