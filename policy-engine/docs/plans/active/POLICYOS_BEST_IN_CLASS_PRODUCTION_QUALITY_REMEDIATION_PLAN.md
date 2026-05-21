---
title: PolicyOS Best-In-Class Production System Remediation Plan
status: completed
owner: team-polisyos
created: 2026-05-12
last_verified: 2026-05-13
stability: closed
related:
  - ./POLICYOS_PRODUCTION_E2E_TESTING_AND_DEBUGGING_PLAN.md
  - ./REPOSITORY_BEST_IN_CLASS_LAST_MILE_REMEDIATION_PLAN.md
  - ../backlog/production-run-backlog.md
  - ../../reference/scientist/index.md
  - ../../reference/scientist/best-in-class-maturity.md
  - ../../../tools/ops_runners/runtime/canary_evidence.py
  - ../../../tools/ops_runners/runtime/golden_quality_scenarios.json
  - ../../../src/polisyos/runtime/quality/scorecard.py
  - ../../../src/polisyos/lex/normpack/applicability_report.py
  - ../../../src/polisyos/fabric/catalog/source_selection_audit.py
  - ../../../src/polisyos/foundry/validation/method_quality.py
  - ../../../src/polisyos/scientist/validation/policy_grounding.py
  - ../../../src/polisyos/lex/normpack/conflict_check.py
---

# PolicyOS Best-In-Class Production System Remediation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` for parallel phase execution or
> `superpowers:executing-plans` for inline execution. Execute waves
> sequentially; execute phases inside a wave in parallel unless a phase is
> explicitly moved to a later wave.

**Goal:** make PolicyOS able to prove end-to-end production quality, safety,
governance, and operator readiness for every serious policy run.

**Architecture:** reuse the existing runtime quality scorecard, canary evidence
bundle, Lex/Fabric/Foundry/Scientist validators, control-plane API, and
dashboard surfaces. Add missing runtime-owned evidence producers, independent
system-assurance reports, and one final readiness aggregator instead of
embedding cross-cutting logic into individual workflow steps.

**Tech Stack:** Python runtime services, FastAPI control contracts, CAS-backed
artifacts, pytest quality gates, deterministic simulated LLM lanes,
quarantined live-provider lanes, Playwright/dashboard journey tests, and
Markdown/MkDocs runbooks.

This plan turns PolicyOS production/staging canaries from "the workflow
completed and produced artifacts" into a best-in-class production-quality
system that can prove, inspect, and govern the quality of each serious policy
run.

The current system has strong foundations: deterministic simulated LLM runs,
real provider preflight, production-data materialization, canary evidence
bundles, failure envelopes, quality scorecards, golden quality scenarios, and
domain validators for Lex, Fabric, Foundry, final policy grounding, and corpus
conflict checks. The first remaining gap is that several quality reports are
still accepted and scored as evidence inputs rather than automatically emitted
by the owning runtime layers during real production runs. The second remaining
gap is broader: a best-in-class PolicyOS production system must also prove data
quality, causal/statistical validity, security, privacy, reproducibility,
resilience, human-review quality, provider drift control, and decision-artifact
quality.

The target is not a minimal green path. The target is an evidence-producing
system where every production approval can answer:

- which provider, model, data, norms, methods, and policy claims were used;
- why each selected source and method was appropriate;
- whether each material final policy claim is supported by data, method output,
  and applicable normative facts;
- whether the policy conflicts with the active corpus;
- whether quality failed independently of execution;
- whether performance, tenant isolation, and continuous governance remain
  within production expectations;
- whether data, causal methods, security, privacy, replay, load, and human
  oversight checks are production-ready;
- what an operator should do next when any gate fails.

## Scope

This plan covers:

- automatic runtime emission of Lex, Fabric, Foundry, Scientist grounding, and
  conflict quality reports;
- production metric taxonomy and pre-Trinity objective canonicalization;
- claim-level grounding and semantic faithfulness checks for final policy
  artifacts;
- benchmark authority for golden, adversarial, hidden, rotating, and regression
  quality scenarios;
- cross-surface canary performance budget evidence;
- tenant-scoped CAS ownership for governed/production artifact access;
- production data quality diagnostics: missingness, outliers, temporal leakage,
  cohort leakage, unit drift, schema drift, construct validity, and label
  quality;
- causal/statistical validation: known-answer synthetic benchmarks, placebo
  tests, negative controls, power/sample adequacy, and sensitivity batteries;
- security and abuse resistance for LLM/tool/data/artifact paths, including
  prompt injection, tool-call injection, malicious source content, provider
  response poisoning, secret exfiltration, and unsafe rendering;
- privacy, licensing, and compliance evidence for production data and public
  policy artifacts;
- deterministic replay and drift explanation for serious runs;
- load, soak, retry-storm, provider-brownout, CAS-pressure, and dashboard
  degradation tests;
- human-review quality, reviewer calibration, override correctness, reviewer
  burden, and escalation threshold evidence;
- model/provider quality monitoring across schema failure rate, grounding
  failure rate, disagreement rate, cost, latency, and quality;
- compiler-grade final decision artifacts: uncertainty language, tradeoffs,
  distributional impacts, feasibility, budget constraints, stakeholder impacts,
  implementation risks, and residual uncertainty;
- production approval, override, reissue, and withdrawal governance;
- real canary matrix execution with deterministic CI, quarantined live-provider
  lanes, and reproducible evidence bundles;
- API/dashboard/operator surfaces needed to inspect quality failures and
  approval readiness.

Out of scope:

- replacing the existing evidence bundle or quality scorecard schema with a
  different external service;
- requiring live LLM calls in deterministic CI gates;
- changing public Runtime API fields in a non-additive way;
- making hidden benchmark answers visible to public artifacts, reusable memory,
  or dashboard exports;
- using heuristic semantic scores as production-blocking evidence before they
  have a documented benchmark proxy, uncertainty, and false-pass analysis.
- replacing human accountability with automated approval for legally or
  politically sensitive production policy decisions.

## Program Control Ledger

The plan follows the repository last-mile remediation structure: every finding
has one severity, one owning layer, one target wave, and at least one
executable acceptance gate. Waves are sequential. Phases inside the same wave
are parallel by definition. If two phases contend for the same shared file,
they prepare independently and merge through the matching shared queue.

### Severity Labels

| Severity | Definition |
| --- | --- |
| PQ-Critical | A completed production run can produce unsupported, legally unsafe, method-weak, or misleading policy output. |
| PQ-High | Production quality evidence, operator inspection, or governance can be incomplete or hard to reproduce. |
| PQ-Medium | Important reliability, performance, benchmark, or lifecycle gap that affects confidence over time. |
| PQ-Low | Cleanup, ergonomics, or documentation gap with low direct production risk. |

### Branch Naming Patterns

| Pattern | Intended fence | Typical phases |
| --- | --- | --- |
| `codex/pq-inventory-*` | inventories, baselines, red tests | 0.1, 0.2, 0.3 |
| `codex/pq-lex-*` | Lex applicability and corpus emission | 1.1, 2.3 |
| `codex/pq-fabric-*` | Fabric source-selection and materialization traces | 1.2 |
| `codex/pq-foundry-*` | Foundry method-quality report emission | 1.3 |
| `codex/pq-scientist-*` | Scientist final claims, grounding, faithfulness | 1.4, 2.2, 3.2 |
| `codex/pq-metrics-*` | production metric taxonomy and canonicalization | 1.5 |
| `codex/pq-scorecard-*` | scorecard schema, gates, API projection | 2.1 |
| `codex/pq-approval-*` | approval, overrides, reviewer trails | 2.4 |
| `codex/pq-dashboard-*` | dashboard operator surfaces | 2.5 |
| `codex/pq-benchmark-*` | scenario packs, hidden/rotating tests | 3.1 |
| `codex/pq-faithfulness-*` | citation support and semantic faithfulness | 3.2, 3.3 |
| `codex/pq-source-quality-*` | source quality, freshness, conflict calibration | 3.4 |
| `codex/pq-adjudication-*` | multi-model disagreement and adjudication | 3.5 |
| `codex/pq-performance-*` | canary performance budget report | 4.1 |
| `codex/pq-cas-*` | tenant-scoped CAS ownership | 4.2 |
| `codex/pq-canary-matrix-*` | real and simulated canary matrix | 4.3 |
| `codex/pq-continuous-gov-*` | reissue, stale, withdrawal governance | 4.4 |
| `codex/pq-data-quality-*` | data quality and leakage diagnostics | 5.1 |
| `codex/pq-causal-validity-*` | causal/statistical benchmark validation | 5.2 |
| `codex/pq-security-*` | LLM/tool/data/artifact abuse resistance | 5.3 |
| `codex/pq-privacy-*` | privacy, licensing, and compliance evidence | 5.4 |
| `codex/pq-replay-*` | deterministic replay and drift explanation | 5.5 |
| `codex/pq-load-soak-*` | load, soak, retry storm, and brownout resilience | 5.6 |
| `codex/pq-human-review-*` | reviewer calibration and override quality | 5.7 |
| `codex/pq-provider-quality-*` | provider/model quality drift monitoring | 5.8 |
| `codex/pq-decision-compiler-*` | decision artifact quality compiler | 5.9 |
| `codex/pq-closeout-*` | final gates, docs, readiness evidence | 6.1, 6.2, 6.3 |

Branch rule: no long-running branch may own generated OpenAPI/client files,
dashboard generated API types, quality scorecard schema, golden scenario
catalog, or shared runtime contracts as its primary work. Those files merge via
short integration queue patches after owning-layer changes are green.

## Remediation Dashboard

| Metric | Owner | Source report or contract | Current baseline | Target gate |
| --- | --- | --- | --- | --- |
| Automatic Lex applicability report refs | team-lex | control job progress, run params, evidence bundle | validator exists; runtime emission partial | Every serious run persists `normative_applicability_report_ref`. |
| Automatic Fabric retrieval trace refs | team-fabric | materialization trace, evidence bundle | validator exists; runtime emission partial | Every serious run persists selected/rejected source trace. |
| Automatic Foundry method report refs | team-foundry | workflow report, evidence bundle | validator exists; runtime emission partial | Every serious run persists method-quality report from executed methods. |
| Automatic policy grounding matrix refs | team-scientist | final artifact, Claim Ledger, evidence bundle | structured validator exists; real artifact extraction partial | Every serious final policy artifact has claim-level grounding matrix. |
| Automatic conflict check refs | team-lex/team-scientist | active corpus, policy claims, evidence bundle | validator exists; runtime emission partial | Every serious run persists conflict check against active corpus. |
| Production metric taxonomy drift | team-runtime/team-ir | metric registry, production data catalog | PRB-010 partially resolved | Unknown metrics fail before Trinity with suggestions. |
| Golden scenario breadth | team-quality | scenario catalog, benchmark packs | 5 public scenarios | Public, hidden, adversarial, rotating, and regression packs exist. |
| Semantic faithfulness false-pass risk | team-scientist | citation faithfulness benchmark | no calibrated production blocker | Faithfulness checker has benchmark proxy and production thresholds. |
| Canary performance budget coverage | team-ops/team-runtime | `canary_performance_budget.json` | PRB-023 open | Each canary records budget status for control, CAS, API, and dashboard. |
| Tenant-scoped CAS enforcement | team-core/team-runtime | CAS ownership index or tenant-local roots | PRB-011 partially resolved | Cross-tenant property tests and evidence bundle ownership refs pass. |
| Approval and override governance | team-governance/team-dashboard | approval packet, dashboard, bundle | scorecard visible; approval policy not complete | Production approval requires pass or signed override trail. |
| Continuous governance lifecycle | team-scientist/team-lex | invalidation/reissue/withdrawal events | primitives exist; production policy path partial | Norm/data/model drift can stale, reissue, supersede, or withdraw decisions. |
| Real canary matrix | team-ops | nightly/quarantined reports | ad hoc live canaries | Matrix covers simulated, live-provider, and real production-data lanes. |
| Production data quality | team-fabric/team-data-forge | data quality report, production data contracts | source/materialization refs exist; deep data diagnostics incomplete | Every serious data-backed run has missingness, drift, leakage, unit, and construct-validity diagnostics. |
| Causal/statistical validity | team-foundry/team-scientist | method benchmark report, known-answer fixtures | method-quality report exists; synthetic causal validation incomplete | Representative methods pass known-answer, placebo, negative-control, power, and sensitivity gates. |
| Security and abuse resistance | team-security/team-runtime | security quality report, injection fixture pack | no production quality gate for prompt/tool/data abuse | Prompt injection, tool-call injection, malicious source content, provider poisoning, and secret exfiltration fail closed. |
| Privacy and licensing compliance | team-governance/team-data-forge | compliance evidence report | production-data context exists; compliance evidence incomplete | PII, license, retention, jurisdiction, and public-export constraints are checked before approval. |
| Replay and drift explanation | team-runtime/team-scientist | replay manifest, Research DAG diff | bundles exist; deterministic replay contract incomplete | Same refs and code produce comparable scorecards or a typed drift explanation. |
| Load and resilience | team-ops/team-runtime | load/soak report, brownout fixture pack | hot-path tests exist; production resilience matrix incomplete | Queue saturation, retry storms, provider brownout, CAS pressure, and dashboard degradation are tested. |
| Human review quality | team-governance/team-dashboard | reviewer calibration report | override packet planned; reviewer quality not measured | Reviewer agreement, override correctness, reviewer burden, and escalation thresholds are measured. |
| Provider/model quality drift | team-scientist/team-ops | provider quality ledger | provider preflight exists; quality drift monitoring incomplete | Schema, grounding, disagreement, cost, latency, and quality drift are tracked per model/provider. |
| Decision artifact quality | team-scientist/team-dashboard | decision compiler report | grounding exists; full artifact quality incomplete | Final artifacts include uncertainty, tradeoffs, distributional impacts, feasibility, budget, stakeholders, and residual risk. |

Dashboard publication rule: every implementation wave updates the metric row it
changes with a measured value, evidence path, or dated exception.

## Review Baseline

Accepted strengths that must not regress:

| Area | Baseline to preserve |
| --- | --- |
| Deterministic debugging | `POLISYOS_LLM_SIMULATION_MODE=1` exercises NL logic without live LLM calls. |
| Provider safety | Serious real-LLM runs use provider preflight and fail fast on red checks. |
| Production data | Local production-data materialization can produce snapshot, bindings, registry, quality, lineage, and evidence context refs. |
| Evidence bundle | Canary runs write sanitized request/env/job/run/timeline/lineage/artifacts/preflight/failure/performance/quality evidence. |
| Failure envelope | Runtime API and dashboard expose operational failures with code, layer, phase, retryability, model/provider, and next action. |
| Quality status | Runtime API and dashboard expose quality status independently from execution status. |
| Quality validators | Lex, Fabric, Foundry, policy grounding, and conflict validators fail closed on missing or weak evidence. |
| Generated clients | Runtime OpenAPI, runtime API client, and dashboard API types remain regenerated after public contract changes. |

## Finding Ledger

| ID | Severity | Finding | Owning layer | Target wave |
| --- | --- | --- | --- | --- |
| PQL-001 | PQ-Critical | Real runtime does not yet automatically emit all quality subreport refs from owning layers. | Lex/Fabric/Foundry/Scientist | 1 |
| PQL-002 | PQ-Critical | Final policy artifacts can be fluent without automatic claim extraction and grounding matrix emission. | Scientist final artifact generation | 1, 2 |
| PQL-003 | PQ-Critical | Plausible but unknown production metrics can still fail late or be healed ad hoc. | runtime, IR metric registry, Trinity linker | 1 |
| PQL-004 | PQ-Critical | Conflict checks are validated but not yet mandatory runtime output from active corpus plus final claims. | Lex, Scientist, governance | 2 |
| PQL-005 | PQ-High | Quality scorecard gates are strong but need runtime-owned refs, provenance, and approval readiness semantics. | runtime quality, control API | 2 |
| PQL-006 | PQ-High | Operators can see failures but do not yet have a production approval/override packet with reviewer trail. | dashboard, governance | 2 |
| PQL-007 | PQ-Critical | Golden scenarios are versioned but not yet benchmark-authority grade with hidden, rotating, and adversarial splits. | quality, evals | 3 |
| PQL-008 | PQ-Critical | Ref presence does not prove semantic support, citation faithfulness, scope fit, or legal exception handling. | Scientist evidence, Lex | 3 |
| PQL-009 | PQ-High | Source quality, freshness, and source conflict signals are deterministic but not calibrated as production decision signals. | Scientist evidence, Fabric | 3 |
| PQL-010 | PQ-High | Multi-model disagreement is detectable in fixtures but needs runtime adjudication and selected-variant rationale. | Scientist, LLM orchestration | 3 |
| PQL-011 | PQ-Medium | Canary performance evidence is not normalized across control jobs, CAS, runtime API, and dashboard route render. | ops, runtime, dashboard | 4 |
| PQL-012 | PQ-High | Governed/production CAS isolation still lacks durable tenant-scoped ownership enforcement. | core artifacts, runtime | 4 |
| PQL-013 | PQ-High | Real canary coverage is not yet a stable matrix across scenario, profile, provider, model, and data lanes. | ops runners | 4 |
| PQL-014 | PQ-High | Completed policy decisions do not yet have full stale/reissue/withdraw lifecycle tied to norm/data/model drift. | continuous governance | 4 |
| PQL-015 | PQ-Critical | Data-backed production decisions lack deep data-quality diagnostics beyond source selection and materialization refs. | Fabric, Data Forge | 5 |
| PQL-016 | PQ-Critical | Causal/statistical methods lack production benchmark proof through known-answer, placebo, negative-control, and sensitivity gates. | Foundry, Scientist | 5 |
| PQL-017 | PQ-Critical | LLM/tool/data/artifact paths lack production gates for prompt injection, tool-call injection, malicious sources, provider poisoning, and secret exfiltration. | security, runtime, Scientist | 5 |
| PQL-018 | PQ-Critical | Production-data and public-artifact compliance lacks mandatory PII, license, retention, jurisdiction, and export checks. | governance, Data Forge | 5 |
| PQL-019 | PQ-High | Serious runs lack deterministic replay and typed drift explanations across code, refs, data, provider, and model changes. | runtime, Scientist | 5 |
| PQL-020 | PQ-High | Load, soak, retry storm, provider brownout, CAS pressure, and dashboard degradation are not covered as production-quality gates. | ops, runtime, dashboard | 5 |
| PQL-021 | PQ-High | Human review and override decisions lack calibration, reviewer agreement, reviewer burden, and correctness evidence. | governance, dashboard | 5 |
| PQL-022 | PQ-High | Provider/model quality drift is not monitored across schema failure, grounding failure, disagreement, latency, cost, and quality. | LLM orchestration, ops | 5 |
| PQL-023 | PQ-Critical | Final decision artifacts are grounded but not yet compiler-grade for uncertainty, tradeoffs, distributional impacts, feasibility, budget, stakeholders, and residual risk. | Scientist, dashboard | 5 |
| PQL-024 | PQ-Medium | Best-in-class readiness needs an aggregate CI/readiness gate and closeout evidence pack. | team-polisyos | 6 |

## Target State

### Production Evidence

- Every serious run emits quality subreports from the owning layer, not only
  from fixtures or manually supplied bundle input.
- Every subreport has a stable ref in run params, control progress, artifacts,
  timeline or lineage, and canary evidence.
- Quality scorecards include `execution_status`, `quality_status`,
  `overall_score`, `stage_scores`, stable gates, blocking failures, and
  evidence refs.
- Quality can fail even when execution completed.

### Policy Quality

- Every major final policy claim is typed and grounded.
- Empirical/data claims reference Fabric data or materialization refs.
- Causal/numerical claims reference Foundry method output and pass tolerance
  checks.
- Normative/legal claims reference Lex applicability evidence.
- Unsupported major recommendations block production approval.
- Direct conflicts block; indirect/reviewable conflicts warn or escalate.

### Data And Method Validity

- Data-backed claims carry data-quality diagnostics for missingness, outliers,
  temporal leakage, cohort leakage, label quality, unit drift, schema drift, and
  construct validity.
- Causal/numerical conclusions are backed by method-specific known-answer
  benchmarks, placebo tests, negative controls, sensitivity checks, power or
  sample adequacy, and uncertainty reporting.
- Data and method quality failures are first-class production blockers when
  they affect a major recommendation.

### Security, Privacy, And Compliance

- Prompt injection, tool-call injection, malicious source content, provider
  response poisoning, unsafe artifact rendering, and secret exfiltration have
  deterministic negative tests and production gates.
- Production-data usage records license, retention, PII, jurisdiction,
  disclosure, and public-export constraints.
- Security or compliance blockers cannot be overridden without an explicit
  governance packet and reviewer attribution.

### Operability

- Operators see the difference between operational failure, quality failure,
  performance budget warning, and approval override.
- Every failure names an owning layer, phase, evidence ref, and next action.
- Every canary writes a sanitized bundle that can be shared without secrets.
- Real LLM provider runs are quarantined or scheduled separately from fast CI.
- Serious runs can be replayed from request, code SHA, data refs, provider/model
  metadata, and artifact refs; replay drift is either bounded or explained by a
  typed drift report.
- Load, soak, retry-storm, provider-brownout, CAS-pressure, and dashboard
  degradation tests are part of production readiness.

### Governance

- Production approval requires `execution_status=completed`,
  `quality_status=pass`, and no blocking failures, unless a signed override
  packet exists.
- Overrides are rare, typed, reviewer-attributed, and included in the evidence
  bundle.
- Human review has calibration evidence: agreement rate, override correctness,
  reviewer burden, escalation thresholds, and unresolved disagreement handling.
- Published decisions can become stale, superseded, reissued, or withdrawn when
  source, norm, data, metric, model, or conflict evidence changes.

### Decision Artifact Quality

- Final public decision artifacts are compiler-grade: they include uncertainty
  language, policy tradeoffs, distributional impacts, feasibility constraints,
  budget implications, stakeholder impacts, implementation risks, and residual
  uncertainty.
- Decision artifacts do not overstate benchmark, data, method, legal, or model
  certainty.
- Provider/model quality drift is visible by model and provider before a model
  can remain a default production option.

## Wave Execution Rule

The plan is wave-first. Waves are sequential. Phases inside the same wave are
parallel by default. A phase may not depend on another phase in the same wave.
If a dependency appears, move the dependent work to the next wave.

Shared files are handled by queues. Owning branches prepare local changes and
tests independently. Queue patches then merge shared artifacts such as OpenAPI,
generated clients, scorecard schema, dashboard API types, golden scenario
catalogs, and CI gates.

Shared integration files such as `src/polisyos/runtime/http/services/control/nl_pipeline.py`
are queue-owned integration surfaces. Same-wave phases may define local helpers,
domain emitters, tests, and adapter contracts in parallel, but the final wiring
into shared integration files happens through short queue patches after all
same-wave owning-layer contracts are green. Queue wiring must not introduce a
new dependency between phases inside the wave; if it does, the dependent part
moves to the next wave.

### Same-Wave Independence Test

A phase is valid only if all of the following are true:

- it can start from the repository state at the beginning of its wave;
- it consumes only previous-wave contracts, fixtures, feature flags, and public
  APIs;
- it does not require another phase in the same wave to merge first;
- it writes a disjoint module/report/test surface or uses a shared queue patch;
- any same-wave shared queue patch is additive, feature-flagged, and does not
  make another same-wave phase fail to compile or test;
- if a phase needs behavior created by another same-wave phase, that dependent
  behavior is moved to the next wave.

This rule is stricter than "can be merged in any order." It means phases inside
one wave can be implemented, tested, reviewed, and parked independently. Only
the wave-level integration queue is allowed to aggregate outputs.

## Parallel Safety Model

| Class | Work type | Parallel rule | Examples |
| --- | --- | --- | --- |
| Q0 | inventories, docs, tests, fixtures | always parallel | evidence map, benchmark pack inventory |
| Q1 | owning-layer emitters with stable refs | parallel by package owner | Lex report emission, Fabric trace emission |
| Q2 | runtime/API/dashboard projections | parallel preparation, serialized queue merge | scorecard refs, generated clients |
| Q3 | benchmark and research protocols | parallel by benchmark pack | hidden scenario pack, faithfulness rubric |
| Q4 | production hardening systems | parallel by subsystem | CAS ownership, performance budgets, canary matrix |
| Q5 | system assurance checks | parallel by risk class | data quality, security, replay, human review |
| Q6 | closeout aggregation and publication | parallel preparation, one additive final publication queue | production approval gate, best-in-class aggregator |

## Shared Registry Queues

| Queue | Files | Owner | Rule |
| --- | --- | --- | --- |
| quality schema queue | `src/polisyos/runtime/quality/**`, scorecard tests | team-runtime | Additive schema changes only; version remains compatible unless explicitly bumped. |
| runtime API queue | `src/polisyos/core/contracts/control.py`, OpenAPI, runtime client, dashboard types | team-runtime | Regenerate generated files once per API patch. |
| canary evidence queue | `tools/ops_runners/runtime/canary_evidence.py`, bundle tests | team-ops | Bundle fields must be sanitized and backward compatible. |
| golden scenario queue | `tools/ops_runners/runtime/golden_quality_scenarios.json` | team-quality | Public scenarios merge separately from hidden/quarantined packs. |
| dashboard queue | `apps/runtime-dashboard/src/**`, journey tests | team-dashboard | UI renders stable public API fields, not private progress internals. |
| metric taxonomy queue | `src/polisyos/ir/kernel/metrics.py`, production-data metric maps | team-ir | New canonical metrics include aliases, owners, and drift tests. |
| CAS ownership queue | `src/polisyos/core/artifacts/**`, runtime artifact authorization | team-core | Artifact IDs remain canonical content hashes. |
| data quality queue | `src/polisyos/data_forge/**`, `src/polisyos/fabric/**`, production-data contracts | team-data-forge | Data diagnostics merge separately from source-selection changes. |
| causal validity queue | `src/polisyos/foundry/**`, method benchmark fixtures | team-foundry | Method benchmark gates do not change method defaults until green. |
| security assurance queue | security fixtures, runtime guards, artifact rendering checks | team-security | Negative tests merge before any production-blocking security gate is enabled. |
| privacy compliance queue | production-data compliance reports, export constraints | team-governance | Compliance evidence is additive and must not expose sensitive records. |
| replay and load queue | replay manifests, load/soak runners, resilience reports | team-ops | Deterministic replay and load evidence stay separate from live-provider lanes. |
| human review queue | approval packet, reviewer calibration, dashboard review surfaces | team-governance | Reviewer metrics merge separately from policy approval semantics. |
| provider quality queue | LLM provider ledger, model quality drift reports | team-scientist | Provider quality gates do not require live calls in deterministic CI. |
| decision compiler queue | final artifact compiler, report templates, dashboard rendering | team-scientist | Compiler output must cite scorecard and claim-support refs. |
| CI/canary queue | `tools/ci/**`, `tools/quality/testing/**`, ops runner scripts | team-devx | Live-provider lanes stay quarantined from deterministic CI. |
| docs/runbook queue | `docs/plans/**`, `docs/reference/**`, `docs/runbooks/**` | team-docs | Docs reflect implemented gates and include verification commands. |

## Phase Fence Matrix

| Phase | Primary fence | Owner | Branch pattern |
| --- | --- | --- | --- |
| 0.1 Evidence emission inventory | runtime quality | team-runtime | `codex/pq-inventory-*` |
| 0.2 Red tests for missing runtime quality refs | tests | team-quality | `codex/pq-inventory-red-tests-*` |
| 0.3 Scorecard readiness contract | runtime quality | team-runtime | `codex/pq-scorecard-contract-*` |
| 0.4 Canary matrix baseline | ops runners | team-ops | `codex/pq-canary-matrix-baseline-*` |
| 1.1 Lex applicability emitter | Lex | team-lex | `codex/pq-lex-applicability-*` |
| 1.2 Fabric source-selection emitter | Fabric | team-fabric | `codex/pq-fabric-source-trace-*` |
| 1.3 Foundry method-quality emitter | Foundry | team-foundry | `codex/pq-foundry-method-report-*` |
| 1.4 Scientist structured final claims | Scientist | team-scientist | `codex/pq-scientist-claims-*` |
| 1.5 Production metric taxonomy | IR/runtime | team-ir/team-runtime | `codex/pq-metrics-taxonomy-*` |
| 1.6 Quality ref resolver | runtime artifacts | team-runtime | `codex/pq-quality-ref-resolver-*` |
| 2.1 Runtime scorecard from persisted refs | runtime quality | team-runtime | `codex/pq-scorecard-runtime-*` |
| 2.2 Automatic grounding matrix enforcement | Scientist | team-scientist | `codex/pq-grounding-enforcement-*` |
| 2.3 Automatic conflict corpus check | Lex/Scientist | team-lex/team-scientist | `codex/pq-conflict-runtime-*` |
| 2.4 Production approval and override packet | governance | team-governance | `codex/pq-approval-packet-*` |
| 2.5 Dashboard quality approval panel | dashboard | team-dashboard | `codex/pq-dashboard-approval-*` |
| 3.1 Benchmark authority scenario packs | quality/evals | team-quality | `codex/pq-benchmark-authority-*` |
| 3.2 Claim support semantics | Scientist evidence | team-scientist | `codex/pq-claim-support-*` |
| 3.3 Citation faithfulness checker | Scientist evidence/Lex | team-scientist | `codex/pq-faithfulness-*` |
| 3.4 Source quality and freshness calibration | Fabric/Scientist | team-fabric/team-scientist | `codex/pq-source-quality-*` |
| 3.5 Multi-model adjudication | LLM orchestration | team-scientist | `codex/pq-adjudication-*` |
| 4.1 Canary performance budget report | ops/runtime/dashboard | team-ops | `codex/pq-performance-budget-*` |
| 4.2 Tenant-scoped CAS ownership | core/runtime | team-core | `codex/pq-cas-ownership-*` |
| 4.3 Real canary matrix runner | ops runners | team-ops | `codex/pq-canary-matrix-*` |
| 4.4 Continuous governance lifecycle | Scientist/Lex/runtime | team-governance | `codex/pq-continuous-governance-*` |
| 5.1 Production data quality gates | Fabric/Data Forge | team-data-forge | `codex/pq-data-quality-*` |
| 5.2 Causal/statistical validity benchmarks | Foundry/Scientist | team-foundry | `codex/pq-causal-validity-*` |
| 5.3 Security and abuse-resistance gates | security/runtime | team-security | `codex/pq-security-*` |
| 5.4 Privacy and licensing compliance evidence | governance/Data Forge | team-governance | `codex/pq-privacy-*` |
| 5.5 Deterministic replay and drift explanation | runtime/Scientist | team-runtime | `codex/pq-replay-*` |
| 5.6 Load, soak, and resilience matrix | ops/runtime/dashboard | team-ops | `codex/pq-load-soak-*` |
| 5.7 Human-review calibration | governance/dashboard | team-governance | `codex/pq-human-review-*` |
| 5.8 Provider/model quality drift ledger | LLM orchestration/ops | team-scientist | `codex/pq-provider-quality-*` |
| 5.9 Decision artifact quality compiler | Scientist/dashboard | team-scientist | `codex/pq-decision-compiler-*` |
| 6.1 Best-in-class readiness aggregator | CI/devx | team-devx | `codex/pq-readiness-aggregator-*` |
| 6.2 Operator runbook and docs closeout | docs/ops | team-docs | `codex/pq-runbook-closeout-*` |
| 6.3 Burn-in and acceptance evidence | team-polisyos | team-polisyos | `codex/pq-closeout-*` |

## Detailed Workstreams

### Wave 0 - Evidence Inventory And Red Gates

Purpose: make the remaining best-in-class gaps executable before adding new
runtime behavior. All phases are Q0/Q1 and can run in parallel.

#### Phase 0.1 - Evidence Emission Inventory

Scope:

- Inventory every current quality artifact field, ref, and producer.
- Mark each quality report as `manual_input`, `fixture_input`,
  `runtime_emitted`, or `missing`.
- Map every existing validator to its owning runtime layer and expected ref.

Files:

- Create: `tools/quality/validation/production_quality_evidence_inventory.py`
- Create: `architecture/baselines/production_quality/evidence_inventory.json`
- Test: `tests/repo_quality/tools/test_production_quality_evidence_inventory.py`

Acceptance:

- Inventory reports Lex, Fabric, Foundry, grounding, conflict, performance,
  metric taxonomy, provider preflight, production-data context, and CAS
  ownership evidence.
- Inventory names the first missing producer for every required serious-profile
  quality ref.
- Inventory output is stable JSON usable by the readiness aggregator.

Verification:

```bash
uv run python tools/quality/validation/production_quality_evidence_inventory.py --json-output _build/.tmp/production-quality/evidence_inventory.json
uv run pytest tests/repo_quality/tools/test_production_quality_evidence_inventory.py -q
```

#### Phase 0.2 - Red Tests For Missing Runtime Quality Refs

Scope:

- Add failing tests that prove serious completed jobs fail quality when runtime
  does not emit required refs.
- Add synthetic completed jobs with missing Lex/Fabric/Foundry/grounding/conflict
  refs.
- Add positive fixture proving completed execution can still be quality-failed.

Files:

- Modify: `tests/unit/runtime/quality/test_scorecard.py`
- Modify: `tests/unit/runtime/http/test_control_plane_store.py`
- Modify: `tests/unit/tools/test_canary_evidence.py`

Acceptance:

- Missing runtime-owned refs fail with stable gate names and next actions.
- Dev profile can warn for missing optional evidence where explicitly allowed.
- Research/governed/production fail closed.

Verification:

```bash
uv run pytest tests/unit/runtime/quality/test_scorecard.py tests/unit/runtime/http/test_control_plane_store.py tests/unit/tools/test_canary_evidence.py -q
```

#### Phase 0.3 - Scorecard Readiness Contract

Scope:

- Define production approval states derived from execution, quality, performance,
  and override evidence.
- Keep `policyos.quality_scorecard.v1` backward compatible.
- Add a non-generated reference contract describing stage scores, blocking
  gates, warnings, refs, and approval eligibility.

Files:

- Modify: `src/polisyos/runtime/quality/scorecard.py`
- Create: `docs/reference/runtime/quality-scorecard.md`
- Test: `tests/unit/runtime/quality/test_scorecard.py`

Acceptance:

- Scorecard can distinguish `execution_failed`, `quality_failed`,
  `quality_warn`, `approval_ready`, and `override_required`.
- Existing canary evidence remains readable.
- New fields are additive and sanitized.

Verification:

```bash
uv run pytest tests/unit/runtime/quality/test_scorecard.py -q
uv run ruff check --select F,I,E501 src/polisyos/runtime/quality/scorecard.py
```

#### Phase 0.4 - Canary Matrix Baseline

Scope:

- Define the canary matrix dimensions:
  - profile: dev, research, governed, production;
  - provider: simulated, live Gonka-compatible proxy;
  - data: fixture, canonical production data;
  - scenario: public golden, negative, adversarial, hidden/quarantined;
  - UI: API-only, dashboard smoke.
- Record the current coverage and missing lanes.

Files:

- Create: `tools/ops_runners/runtime/canary_matrix.py`
- Create: `docs/reference/runtime/production-canary-matrix.md`
- Test: `tests/repo_quality/tools/test_canary_matrix.py`

Acceptance:

- Matrix has deterministic lanes safe for CI and quarantined lanes for live LLM.
- Each lane declares required evidence bundle files.
- Missing lanes are visible as skipped/deferred, not silently absent.

Verification:

```bash
uv run python tools/ops_runners/runtime/canary_matrix.py --list --json-output _build/.tmp/production-quality/canary_matrix.json
uv run pytest tests/repo_quality/tools/test_canary_matrix.py -q
```

### Wave 1 - Runtime Evidence Producers

Purpose: make the owning layers emit real quality evidence automatically. All
phases are parallel by package owner; shared evidence-bundle integration merges
through the canary evidence queue after local tests pass.

#### Phase 1.1 - Lex Applicability Report Emitter

Scope:

- Wire Lex retrieval/runtime to build and persist
  `normative_applicability_report_ref`.
- Include applied norms, jurisdiction, effective dates, authority metadata,
  recommendation coverage, and issue codes.
- Link the ref into run params, timeline/lineage, and canary evidence.

Files:

- Modify: `src/polisyos/lex/normpack/applicability_report.py`
- Modify: `src/polisyos/runtime/http/services/control/nl_pipeline.py`
- Modify: `src/polisyos/runtime/http/services/control/artifacts.py`
- Test: `tests/unit/lex/test_normative_applicability_report.py`
- Test: `tests/unit/runtime/http/test_nl_pipeline_materialization.py`

Acceptance:

- Research/governed/production NL runs persist applicability report refs.
- Wrong jurisdiction, expired norms, missing authority, and unanchored major
  recommendations fail quality.
- The evidence bundle writes `quality_evidence/normative_evidence.json` from
  runtime output, not only supplied test input.

Verification:

```bash
uv run pytest tests/unit/lex/test_normative_applicability_report.py tests/unit/runtime/http/test_nl_pipeline_materialization.py -q
```

#### Phase 1.2 - Fabric Source-Selection Trace Emitter

Scope:

- Capture Fabric candidates, selected sources, rejected sources, and reasons.
- Persist `fabric_retrieval_trace_ref` with freshness, coverage, schema
  compatibility, relevance rationale, source family, and fixture/mock flags.
- Link trace refs to materialization refs and production-data evidence context.

Files:

- Modify: `src/polisyos/fabric/catalog/source_selection_audit.py`
- Modify: `src/polisyos/runtime/http/services/control/production_data.py`
- Modify: `src/polisyos/runtime/http/services/control/nl_pipeline.py`
- Test: `tests/unit/fabric/test_source_selection_audit.py`
- Test: `tests/unit/runtime/http/test_run_evidence_context_promotions.py`

Acceptance:

- Every selected production source has diagnostics and rationale.
- Every rejected plausible source has a reason code.
- Fixture/mock source selection fails serious quality.
- Lineage/timeline mention selected source and materialization refs.

Verification:

```bash
uv run pytest tests/unit/fabric/test_source_selection_audit.py tests/unit/runtime/http/test_run_evidence_context_promotions.py -q
```

#### Phase 1.3 - Foundry Method-Quality Report Emitter

Scope:

- Build `foundry_method_report_ref` from actual method execution outputs.
- Include selected method id, method family, input refs, assumptions,
  uncertainty, sensitivity, missingness, sample-size diagnostics, degradation,
  and result summary.
- Persist one method-quality report per serious policy run.

Files:

- Modify: `src/polisyos/foundry/validation/method_quality.py`
- Modify: `src/polisyos/scientist/orchestration/workflows/builder.py`
- Modify: `src/polisyos/runtime/http/services/control/nl_pipeline.py`
- Test: `tests/unit/foundry/validation/test_method_quality.py`
- Test: `tests/unit/runtime/http/test_nl_pipeline_materialization.py`

Acceptance:

- Point estimates without uncertainty cannot pass quality.
- Insufficient sample size requires explicit degrade/fail.
- Method report references the same data snapshot and input bindings used by
  Foundry.

Verification:

```bash
uv run pytest tests/unit/foundry/validation/test_method_quality.py tests/unit/runtime/http/test_nl_pipeline_materialization.py -q
```

#### Phase 1.4 - Scientist Structured Final Claims

Scope:

- Emit structured final policy claims alongside the human-readable artifact.
- Classify claim family: recommendation, empirical, numerical, causal,
  normative, forecast, distributional, implementation, or caveat.
- Preserve major/minor status and explicit no-grounding rationale when allowed.

Files:

- Modify: `src/polisyos/scientist/agent/formalizer.py`
- Modify: `src/polisyos/scientist/validation/policy_grounding.py`
- Modify: `src/polisyos/runtime/http/services/control/nl_pipeline.py`
- Test: `tests/unit/scientist/validation/test_policy_grounding_matrix.py`
- Test: `tests/unit/scientist/agent/test_response_healing.py`

Acceptance:

- Final policy artifacts have machine-readable major claims.
- Claim extraction failures fail serious quality or require review.
- Structured claims are stored in CAS and linked from run params.

Verification:

```bash
uv run pytest tests/unit/scientist/validation/test_policy_grounding_matrix.py tests/unit/scientist/agent/test_response_healing.py -q
```

#### Phase 1.5 - Production Metric Taxonomy And Pre-Trinity Validation

Scope:

- Build a versioned production metric taxonomy from metric registry,
  production-data contracts, aliases, benchmark metrics, and scenario expected
  outputs.
- Add pre-Trinity metric canonicalization with suggestions for unknown metrics.
- Fail unknown serious metrics before long workflow execution.

Files:

- Modify: `src/polisyos/ir/kernel/metrics.py`
- Modify: `src/polisyos/scientist/agent/formalizer.py`
- Modify: `src/polisyos/runtime/http/services/control/nl_pipeline.py`
- Test: `tests/unit/core/phase0/test_metrics.py`
- Test: `tests/unit/runtime/http/test_nl_pipeline_materialization.py`

Acceptance:

- Unknown metrics fail fast with suggestions before `link_trinity`.
- Known aliases are canonicalized with diagnostics in evidence.
- Canary evidence records taxonomy version, metric count, canonicalizer, and
  fingerprint.

Verification:

```bash
uv run pytest tests/unit/core/phase0/test_metrics.py tests/unit/runtime/http/test_nl_pipeline_materialization.py -q
```

#### Phase 1.6 - Quality Ref Resolver

Scope:

- Add a runtime helper that discovers quality refs from run params, artifacts,
  timeline, lineage, and control progress.
- Use the resolver in canary evidence so owning layers can emit refs without
  duplicating bundle logic.

Files:

- Create: `src/polisyos/runtime/quality/refs.py`
- Modify: `tools/ops_runners/runtime/canary_evidence.py`
- Test: `tests/unit/runtime/quality/test_quality_refs.py`
- Test: `tests/unit/tools/test_canary_evidence.py`

Acceptance:

- Resolver finds all required refs from realistic run payloads.
- Missing refs produce stable missing-evidence diagnostics.
- Sanitization still applies to loaded quality reports.

Verification:

```bash
uv run pytest tests/unit/runtime/quality/test_quality_refs.py tests/unit/tools/test_canary_evidence.py -q
```

### Wave 2 - Production Approval Semantics

Purpose: turn emitted evidence into production approval readiness. All phases
are parallel by surface; shared API/dashboard/generated artifacts merge through
queues.

#### Phase 2.1 - Runtime Scorecard From Persisted Refs

Scope:

- Build scorecards from persisted refs, not only in-memory bundle input.
- Store scorecard refs in control progress and evidence bundle.
- Keep job execution status separate from quality and approval status.

Files:

- Modify: `src/polisyos/runtime/quality/scorecard.py`
- Modify: `src/polisyos/runtime/http/services/control_plane_store.py`
- Modify: `tools/ops_runners/runtime/canary_evidence.py`
- Test: `tests/unit/runtime/quality/test_scorecard.py`
- Test: `tests/unit/runtime/http/test_control_plane_store.py`

Acceptance:

- Completed jobs with bad evidence return `execution_status=completed` and
  `quality_status=fail`.
- Scorecard includes stage scores and evidence refs loaded from runtime output.
- API and evidence bundle agree on gate names and blocking failures.

Verification:

```bash
uv run pytest tests/unit/runtime/quality/test_scorecard.py tests/unit/runtime/http/test_control_plane_store.py tests/unit/tools/test_canary_evidence.py -q
```

#### Phase 2.2 - Automatic Grounding Matrix Enforcement

Scope:

- Build `policy_grounding_matrix_ref` from final structured claims and
  Lex/Fabric/Foundry reports.
- Enforce support by claim family.
- Apply numerical tolerance checks against Foundry outputs.

Files:

- Modify: `src/polisyos/scientist/validation/policy_grounding.py`
- Modify: `src/polisyos/runtime/http/services/control/nl_pipeline.py`
- Test: `tests/unit/scientist/validation/test_policy_grounding_matrix.py`

Acceptance:

- Unsupported major recommendations block production approval.
- Numerical claims outside tolerance fail with metric, expected, observed, and
  evidence ref.
- Minor ungrounded claims require documented rationale and do not hide major
  unsupported claims.

Verification:

```bash
uv run pytest tests/unit/scientist/validation/test_policy_grounding_matrix.py -q
```

#### Phase 2.3 - Automatic Conflict Corpus Check

Scope:

- Build `conflict_check_ref` from final structured claims and active corpus
  constraints.
- Classify direct blocking conflicts, indirect reviewable conflicts, and
  informational overlaps.

Files:

- Modify: `src/polisyos/lex/normpack/conflict_check.py`
- Modify: `src/polisyos/runtime/http/services/control/nl_pipeline.py`
- Test: `tests/unit/lex/test_conflict_check_report.py`

Acceptance:

- Direct prohibition, eligibility mismatch, budget-rule mismatch, and
  equity/access conflicts are detected.
- Direct/high severity conflicts fail quality.
- Reviewable indirect conflicts warn and require operator action.

Verification:

```bash
uv run pytest tests/unit/lex/test_conflict_check_report.py tests/unit/runtime/http/test_nl_pipeline_materialization.py -q
```

#### Phase 2.4 - Production Approval And Override Packet

Scope:

- Define approval eligibility from execution, quality, performance, and
  conflict status.
- Add signed/attributed override packet for exceptional cases.
- Persist approval packet in CAS and evidence bundle.

Files:

- Create: `src/polisyos/runtime/quality/approval.py`
- Modify: `src/polisyos/core/contracts/control.py`
- Modify: `src/polisyos/runtime/http/routes/runs.py`
- Test: `tests/unit/runtime/quality/test_approval.py`
- Test: `tests/unit/runtime/http/test_control_api.py`

Acceptance:

- Production approval requires completed execution, passing quality, no blocking
  failures, and no blocking performance budgets.
- Override requires reviewer identity, reason, scope, expiry, and evidence refs.
- Override never mutates the original scorecard.

Verification:

```bash
uv run pytest tests/unit/runtime/quality/test_approval.py tests/unit/runtime/http/test_control_api.py -q
```

#### Phase 2.5 - Dashboard Quality Approval Panel

Scope:

- Render approval readiness separately from execution and quality.
- Group failed/warn gates by layer.
- Show scorecard, bundle, approval packet, and override refs.

Files:

- Modify: `apps/runtime-dashboard/src/features/clerk/components/ControlFailurePanel.tsx`
- Add or modify: `apps/runtime-dashboard/e2e/journeys/control-quality.spec.ts`
- Test: `apps/runtime-dashboard/src/features/clerk/components/ControlFailurePanel.test.tsx`

Acceptance:

- Operator can see why a completed run is not approval-ready.
- Dashboard shows next action and evidence refs without exposing secrets.
- Existing route-mocked recovery journeys remain green.

Verification:

```bash
corepack pnpm --dir apps/runtime-dashboard exec vitest run src/features/clerk/components/ControlFailurePanel.test.tsx
corepack pnpm --dir apps/runtime-dashboard run test:journeys:smoke
```

### Wave 3 - Benchmark Authority And Semantic Quality

Purpose: move from structural evidence completeness to calibrated quality
judgment. All phases are parallel because they create independent benchmark
packs, protocols, and research-backed gates.

#### Phase 3.1 - Benchmark Authority Scenario Packs

Scope:

- Split quality scenarios into public, regression, adversarial, hidden, and
  rotating packs.
- Add contamination rules so hidden answers and sentinel strings cannot enter
  public exports, reusable memory, or dashboard fixtures.

Files:

- Modify: `tools/ops_runners/runtime/golden_quality_scenarios.json`
- Create: `tools/ops_runners/runtime/quality_benchmark_authority.py`
- Test: `tests/repo_quality/tools/test_quality_benchmark_authority.py`

Acceptance:

- Public scenarios are inspectable; hidden/rotating scenarios are quarantined.
- Scenario packs declare expected evidence contracts and pass/fail thresholds.
- Contamination tests fail if hidden answers leak into public artifacts.

Verification:

```bash
uv run pytest tests/repo_quality/tools/test_quality_benchmark_authority.py -q
```

#### Phase 3.2 - Claim Support Semantics

Scope:

- Define support predicates by claim family.
- Separate support strength from publishability.
- Define counterevidence and lifecycle transitions.

Files:

- Create: `docs/reference/scientist/claim-support-semantics.md`
- Create: `src/polisyos/scientist/validation/claim_support.py`
- Test: `tests/unit/scientist/validation/test_claim_support.py`

Acceptance:

- Claim support rules cover factual, legal, causal, numerical, forecast,
  distributional, welfare, and implementation claims.
- Counterevidence can block, warn, lower readiness, or require review.
- Rules map to final policy grounding matrix checks.

Verification:

```bash
uv run pytest tests/unit/scientist/validation/test_claim_support.py -q
```

#### Phase 3.3 - Citation Faithfulness Checker

Scope:

- Add an offline checker that labels cited evidence as supports, partially
  supports, scope-limited, contradicts, irrelevant, fabricated, or
  unverifiable.
- Keep live LLM faithfulness judging out of deterministic CI.

Files:

- Create: `src/polisyos/scientist/validation/citation_faithfulness.py`
- Create: `tests/_golden/quality/citation_faithfulness/`
- Test: `tests/unit/scientist/validation/test_citation_faithfulness.py`

Acceptance:

- Legal scope, jurisdiction, date, population, and exception mismatches are
  represented in fixtures.
- Public factual/legal claims cannot pass if cited refs are irrelevant or
  contradictory.
- Checker reports residual risk and false-pass limits.

Verification:

```bash
uv run pytest tests/unit/scientist/validation/test_citation_faithfulness.py -q
```

#### Phase 3.4 - Source Quality And Freshness Calibration

Scope:

- Calibrate source authority, primary-source status, freshness TTL, duplicate
  handling, and source conflict behavior.
- Define source invalidation mapping to stale/review/withdraw states.

Files:

- Create or modify: `src/polisyos/scientist/evidence/source_quality.py`
- Create: `docs/reference/scientist/source-quality-calibration.md`
- Test: `tests/unit/scientist/evidence/test_source_quality.py`

Acceptance:

- Source quality scores are calibrated or explicitly advisory.
- Withdrawn primary sources cannot remain publishable.
- TTL differs by claim family and source class.

Verification:

```bash
uv run pytest tests/unit/scientist/evidence/test_source_quality.py -q
```

#### Phase 3.5 - Multi-Model Adjudication And Variant Rationale

Scope:

- Persist model variant claims, disagreements, selected variant rationale, and
  adjudication decision.
- Fail quality when materially different major recommendations lack
  adjudication.

Files:

- Modify: `src/polisyos/scientist/orchestration/llm/**`
- Modify: `src/polisyos/scientist/validation/policy_grounding.py`
- Test: `tests/unit/runtime/http/test_nl_pipeline_materialization.py`

Acceptance:

- Multi-model disagreement has stable code, variant refs, and next action.
- Selected variant includes rationale and evidence refs.
- Adjudication cannot hide unsupported claims.

Verification:

```bash
POLISYOS_LLM_SIMULATION_MODE=1 uv run pytest tests/unit/runtime/http/test_nl_pipeline_materialization.py -q
```

### Wave 4 - Production Hardening And Runtime Operations

Purpose: ensure quality remains trustworthy in production operations,
multi-tenant artifact access, live-provider canaries, and lifecycle drift.
Phases are parallel by subsystem.

#### Phase 4.1 - Canary Performance Budget Report

Scope:

- Build `canary_performance_budget.json` from control timestamps, CAS samples,
  run-index refresh/list, timeline/lineage APIs, evidence collection, and
  dashboard route render timings.

Files:

- Create: `src/polisyos/runtime/quality/performance_budget.py`
- Modify: `tools/ops_runners/runtime/canary_evidence.py`
- Modify: `tools/quality/testing/local_integration_stack.py`
- Test: `tests/performance/test_runtime_hot_paths.py`
- Test: `tests/unit/tools/test_canary_evidence.py`

Acceptance:

- Each budget row has observed duration, budget, status, layer, retryability,
  and next action.
- Production-blocking budgets can fail approval without being confused with
  operational failure.
- Dashboard smoke route timing is included when available.

Verification:

```bash
uv run pytest tests/performance/test_runtime_hot_paths.py tests/unit/tools/test_canary_evidence.py -q
```

#### Phase 4.2 - Tenant-Scoped CAS Ownership

Scope:

- Implement tenant-local CAS roots or shared immutable CAS plus signed ownership
  index.
- Enforce artifact reads/writes through ownership checks without mutating sha256
  IDs.

Files:

- Modify: `src/polisyos/core/artifacts/**`
- Modify: `src/polisyos/runtime/http/services/debug.py`
- Test: `tests/unit/core/artifacts/test_artifact_id_serialization_contract.py`
- Test: `tests/unit/runtime/http/test_control_api.py`

Acceptance:

- Cross-tenant artifact read/write/property tests pass.
- Artifact IDs remain canonical content hashes across tenants.
- Evidence bundle includes ownership index or tenant CAS root.

Verification:

```bash
uv run pytest tests/unit/core/artifacts/test_artifact_id_serialization_contract.py tests/unit/runtime/http/test_control_api.py -q
```

#### Phase 4.3 - Real Canary Matrix Runner

Scope:

- Execute deterministic matrix lanes in CI and live-provider lanes in
  quarantined/nightly jobs.
- Emit one evidence bundle and scorecard per lane.

Files:

- Modify: `tools/ops_runners/runtime/local_production_canary.py`
- Modify: `tools/ops_runners/experiments/run_policyos_real_e2e_cloud.py`
- Create: `tools/ops_runners/runtime/run_canary_matrix.py`
- Test: `tests/repo_quality/tools/test_canary_matrix.py`

Acceptance:

- Matrix can run one lane, one scenario, or the full deterministic subset.
- Live-provider lane runs only when credentials and explicit flag are present.
- Matrix summary names lane status, bundle path, scorecard status, and failure
  envelope.

Verification:

```bash
uv run python tools/ops_runners/runtime/run_canary_matrix.py --deterministic --json-output _build/.tmp/production-quality/canary_matrix_result.json
uv run pytest tests/repo_quality/tools/test_canary_matrix.py -q
```

#### Phase 4.4 - Continuous Governance Lifecycle

Scope:

- Tie policy decision status to norm, data, source, metric, model, and conflict
  invalidation events.
- Support stale, review-required, superseded, reissued, and withdrawn states.

Files:

- Modify: `src/polisyos/core/contracts/control.py`
- Modify: `src/polisyos/scientist/**/continuous_governance/**`
- Test: `tests/unit/runtime/http/test_control_api.py`

Acceptance:

- A norm/data/source invalidation can mark a published decision stale or
  withdrawn.
- Reissue packet includes original scorecard, new evidence refs, and change
  reason.
- Dashboard/API expose lifecycle status.

Verification:

```bash
uv run pytest tests/unit/runtime/http/test_control_api.py -q
```

### Wave 5 - Production System Assurance

Purpose: close the gap from production-quality evidence to best-in-class
production system assurance. All phases are parallel by risk class. Each phase
consumes artifacts and contracts produced by Waves 1-4, writes its own report
ref, and may be implemented without waiting for any other Wave 5 phase. The
Wave 6 readiness aggregator is the first place these phase outputs are joined
into one production approval decision.

Parallel contract:

- 5.1 writes data-quality evidence only.
- 5.2 writes causal/statistical validity evidence only.
- 5.3 writes security and abuse-resistance evidence only.
- 5.4 writes privacy, licensing, and compliance evidence only.
- 5.5 writes replay and drift evidence only.
- 5.6 writes load, soak, and resilience evidence only.
- 5.7 writes human-review calibration evidence only.
- 5.8 writes provider/model quality drift evidence only.
- 5.9 writes decision-artifact quality evidence only.
- No Wave 5 phase may require another Wave 5 phase as a prerequisite. Any join,
  comparison, or production-blocking aggregate rule belongs in Wave 6.

#### Phase 5.1 - Production Data Quality Gates

Scope:

- Build `production_data_quality_report_ref` from the real materialized
  production data used by a serious run.
- Diagnose schema drift, missingness, outliers, duplicate/entity collisions,
  unit drift, temporal leakage, cohort leakage, label quality, construct
  validity, geographic/time/population coverage, recency TTL, and data
  dictionary completeness.
- Attach diagnostics to data-backed claims without changing Foundry method
  behavior in this phase.

Files:

- Create: `src/polisyos/runtime/quality/data_quality.py`
- Modify: `src/polisyos/runtime/http/services/control/production_data.py`
- Create: `docs/reference/runtime/production-data-quality.md`
- Test: `tests/unit/runtime/quality/test_data_quality.py`
- Test: `tests/unit/runtime/http/test_nl_pipeline_materialization.py`

Acceptance:

- Every serious data-backed run emits `production_data_quality_report_ref`.
- The report names source bundle versions, manifest checksum, data snapshot ref,
  input bindings ref, registry bundle ref, row/entity counts, and diagnostics.
- Missing or fixture-like production evidence in research/governed/production
  fails with `production_data_quality_missing`.
- Data-quality failures that affect a major data-backed recommendation block
  production approval or require an explicit degrade reason.
- Lineage and timeline mention the production data quality report ref.

Verification:

```bash
uv run pytest tests/unit/runtime/quality/test_data_quality.py tests/unit/runtime/http/test_nl_pipeline_materialization.py -q
```

#### Phase 5.2 - Causal And Statistical Validity Benchmarks

Scope:

- Build `causal_statistical_validity_report_ref` for representative Foundry
  method families.
- Add known-answer synthetic fixtures, placebo tests, negative controls,
  sensitivity batteries, power/sample adequacy checks, missingness stress
  tests, and uncertainty calibration fixtures.
- Keep method defaults unchanged until benchmarks are green.

Files:

- Create: `src/polisyos/foundry/validation/causal_validity.py`
- Create: `tests/_golden/foundry/causal_validity/`
- Create: `docs/reference/foundry/causal-statistical-validity.md`
- Test: `tests/unit/foundry/validation/test_causal_validity.py`
- Test: `tests/unit/scientist/validation/test_policy_grounding_matrix.py`

Acceptance:

- Each covered method family declares expected assumptions, input shape,
  estimand, uncertainty type, minimum sample diagnostics, and failure modes.
- Known-answer fixtures pass within declared tolerance.
- Placebo and negative-control scenarios fail or degrade rather than producing
  confident causal recommendations.
- Sensitivity or power failures become blocking quality failures when the final
  policy relies on a major causal/numerical claim.
- The report can be generated offline with deterministic fixtures.

Verification:

```bash
uv run pytest tests/unit/foundry/validation/test_causal_validity.py tests/unit/scientist/validation/test_policy_grounding_matrix.py -q
```

#### Phase 5.3 - Security And Abuse-Resistance Gates

Scope:

- Build `security_assurance_report_ref` for LLM, tool, data, artifact, runtime
  API, and dashboard paths.
- Add deterministic negative fixtures for prompt injection, tool-call
  injection, malicious source content, provider response poisoning, unsafe
  artifact rendering, SSRF-like URL attempts, path traversal attempts, and
  secret exfiltration.
- Ensure failures are fail-closed and produce operator-actionable envelopes.

Files:

- Create: `src/polisyos/runtime/security/quality_gates.py`
- Create: `tests/security/fixtures/policyos_abuse_cases/`
- Test: `tests/security/test_policyos_runtime_abuse_gates.py`
- Test: `tests/unit/tools/test_canary_evidence.py`
- Test: `apps/runtime-dashboard/e2e/journeys/control-quality-security.spec.ts`

Acceptance:

- Secrets, bearer tokens, API keys, provider credentials, and environment
  values are never copied into prompts, artifacts, bundles, logs, or dashboard
  payloads.
- Malicious retrieved source text cannot override system instructions, tool
  schemas, approval status, conflict status, or scorecard output.
- Unsafe rendered artifact content is escaped or blocked before dashboard
  display.
- Security blockers set layer `security`, a stable code, retryability, evidence
  refs, and next action.
- Deterministic CI can run all security gates without live LLM calls.

Verification:

```bash
uv run pytest tests/security/test_policyos_runtime_abuse_gates.py tests/unit/tools/test_canary_evidence.py -q
corepack pnpm --dir apps/runtime-dashboard run test:journeys:smoke
```

#### Phase 5.4 - Privacy, Licensing, And Compliance Evidence

Scope:

- Build `privacy_compliance_report_ref` for production data inputs and public
  policy artifacts.
- Check PII/PHI-like fields, minimization, retention class, jurisdiction,
  license terms, public-export constraints, source attribution, consent or
  authority basis where applicable, and redaction status.
- Keep compliance evidence separate from source quality so it can be audited by
  governance without rerunning Fabric.

Files:

- Create: `src/polisyos/runtime/quality/compliance.py`
- Create: `src/polisyos/data_forge/compliance.py`
- Create: `docs/reference/runtime/privacy-compliance-evidence.md`
- Test: `tests/unit/runtime/quality/test_compliance.py`
- Test: `tests/unit/tools/test_canary_evidence.py`

Acceptance:

- Serious runs emit compliance evidence for every production data source and
  public artifact family.
- PII-like fields either have an approved basis, redaction, or a blocking
  compliance failure.
- License or public-export conflicts block production approval before artifact
  publication.
- Evidence bundles include compliance status without exposing raw sensitive
  records.
- Override requires reviewer identity, reason, scope, expiry, and evidence refs.

Verification:

```bash
uv run pytest tests/unit/runtime/quality/test_compliance.py tests/unit/tools/test_canary_evidence.py -q
```

#### Phase 5.5 - Deterministic Replay And Drift Explanation

Scope:

- Build `replay_manifest_ref` and `drift_explanation_ref`.
- Record request fingerprint, git SHA, dependency fingerprints, feature flags,
  provider/model metadata, prompt/template fingerprints, data refs, CAS refs,
  random seeds, run params, and quality scorecard ref.
- Classify replay differences by drift source: code, data, source, norm,
  provider, model, config, prompt, CAS, dependency, or nondeterminism.

Files:

- Create: `src/polisyos/runtime/quality/replay.py`
- Create: `tools/ops_runners/runtime/replay_canary_bundle.py`
- Create: `docs/reference/runtime/deterministic-replay.md`
- Test: `tests/unit/runtime/quality/test_replay.py`
- Test: `tests/repo_quality/tools/test_replay_canary_bundle.py`

Acceptance:

- A serious canary can be replayed from bundle refs without reusing secrets.
- Identical deterministic refs produce matching execution and quality
  summaries.
- Accepted differences have typed drift causes and bounded impact.
- Unexplained drift fails production readiness.
- Replay output is sanitized and linkable from the evidence bundle.

Verification:

```bash
uv run pytest tests/unit/runtime/quality/test_replay.py tests/repo_quality/tools/test_replay_canary_bundle.py -q
```

#### Phase 5.6 - Load, Soak, And Resilience Matrix

Scope:

- Build `resilience_report_ref` from load, soak, retry-storm, provider-brownout,
  CAS-pressure, queue-saturation, run-index-pressure, and dashboard degradation
  scenarios.
- Define SLO budgets for control job lease/heartbeat, materialization, CAS
  put/get, run-index refresh/list, timeline/lineage build, provider preflight,
  evidence bundle assembly, API job detail, and dashboard first meaningful
  route render.
- Ensure degraded modes remain observable and fail closed when evidence becomes
  incomplete.

Files:

- Create: `tools/quality/testing/runtime_resilience_matrix.py`
- Modify: `tests/performance/test_runtime_hot_paths.py`
- Create: `docs/reference/runtime/production-resilience-matrix.md`
- Test: `tests/repo_quality/tools/test_runtime_resilience_matrix.py`
- Test: `apps/runtime-dashboard/e2e/journeys/control-quality-resilience.spec.ts`

Acceptance:

- Deterministic local matrix covers overload, retry storm, CAS pressure, and
  dashboard degraded rendering.
- Live-provider brownout lanes are quarantined and require an explicit flag.
- Performance budget warnings are distinct from operational failures and
  quality failures.
- Incomplete evidence under load blocks approval instead of silently passing.
- Operators see the bottleneck layer, phase, observed value, budget, and next
  action.

Verification:

```bash
uv run python tools/quality/testing/runtime_resilience_matrix.py --deterministic --json-output _build/.tmp/production-quality/resilience_matrix.json
uv run pytest tests/repo_quality/tools/test_runtime_resilience_matrix.py tests/performance/test_runtime_hot_paths.py -q
corepack pnpm --dir apps/runtime-dashboard run test:journeys:smoke
```

#### Phase 5.7 - Human-Review Calibration

Scope:

- Build `human_review_calibration_report_ref` for approval, override,
  escalation, and withdrawal review flows.
- Track reviewer agreement, disagreement reason codes, override correctness,
  reviewer burden, escalation thresholds, unresolved disagreements, and
  reviewer-attributed decisions.
- Provide deterministic review fixtures so the calibration layer does not
  require live human reviewers in CI.

Files:

- Create: `src/polisyos/runtime/quality/human_review.py`
- Modify: `src/polisyos/runtime/quality/approval.py`
- Create: `docs/reference/runtime/human-review-calibration.md`
- Test: `tests/unit/runtime/quality/test_human_review.py`
- Test: `apps/runtime-dashboard/e2e/journeys/control-quality-review.spec.ts`

Acceptance:

- Approval and override packets can be evaluated for reviewer attribution,
  completeness, expiry, scope, and rationale quality.
- Low agreement or high override rate produces warn/fail quality signals.
- Blocking quality failures cannot be silently overridden without a signed,
  scoped, expiring packet.
- Review fixtures cover approve, reject, escalate, override, reissue, and
  withdraw outcomes.
- Dashboard shows reviewer burden and unresolved disagreement without exposing
  private reviewer notes to public exports.

Verification:

```bash
uv run pytest tests/unit/runtime/quality/test_human_review.py tests/unit/runtime/quality/test_approval.py -q
corepack pnpm --dir apps/runtime-dashboard run test:journeys:smoke
```

#### Phase 5.8 - Provider And Model Quality Drift Ledger

Scope:

- Build `provider_model_quality_ledger_ref` from simulated and quarantined live
  lanes.
- Track schema failure rate, healing count, JSON/tool-call validity, grounding
  failure rate, citation faithfulness failure rate, disagreement rate, latency,
  cost, context pressure, provider errors, and selected-variant quality.
- Require default production model choices to have recent quality evidence.

Files:

- Create: `src/polisyos/scientist/orchestration/llm/provider_quality.py`
- Create: `tools/ops_runners/runtime/provider_quality_ledger.py`
- Create: `docs/reference/runtime/provider-model-quality.md`
- Test: `tests/unit/scientist/orchestration/llm/test_provider_quality.py`
- Test: `tests/repo_quality/tools/test_provider_quality_ledger.py`

Acceptance:

- Deterministic simulated lanes populate provider/model quality metrics without
  network calls.
- Live-provider metrics are optional in CI but attachable as quarantined
  evidence.
- Provider/model drift can demote a default model, require review, or block a
  production approval lane.
- Model comparisons use stable scenario pack IDs and do not leak hidden
  answers.
- Ledger entries are sanitized and keyed by provider/model/fingerprint, not raw
  credentials.

Verification:

```bash
uv run pytest tests/unit/scientist/orchestration/llm/test_provider_quality.py tests/repo_quality/tools/test_provider_quality_ledger.py -q
```

#### Phase 5.9 - Decision Artifact Quality Compiler

Scope:

- Build `decision_artifact_quality_report_ref` for final policy outputs.
- Compile a structured public decision artifact from final claims, grounding,
  scorecard, conflict status, approval state, performance warnings, and
  available assurance refs.
- Validate uncertainty language, policy tradeoffs, distributional impacts,
  feasibility, budget implications, stakeholder impacts, implementation risks,
  residual uncertainty, monitoring plan, and withdrawal/reissue triggers.

Files:

- Create: `src/polisyos/scientist/validation/decision_artifact_quality.py`
- Create: `src/polisyos/scientist/artifacts/decision_compiler.py`
- Create: `docs/reference/scientist/decision-artifact-quality.md`
- Test: `tests/unit/scientist/validation/test_decision_artifact_quality.py`
- Test: `tests/unit/scientist/artifacts/test_decision_compiler.py`

Acceptance:

- Final artifacts cannot overstate causal, legal, empirical, model, benchmark,
  or compliance certainty.
- Major recommendations include support summary, uncertainty, tradeoffs,
  distributional impact, implementation feasibility, budget implication,
  stakeholder impact, monitoring requirement, and residual risk.
- Missing required sections fail quality for serious profiles.
- Decision artifact quality is evaluated from existing Waves 1-4 refs and its
  own compiled output so it can run in parallel; Wave 6 joins all Wave 5 refs
  into the final aggregate gate.
- Public exports preserve citations and omit hidden benchmark answers,
  credentials, reviewer-private notes, and raw sensitive data.

Verification:

```bash
uv run pytest tests/unit/scientist/validation/test_decision_artifact_quality.py tests/unit/scientist/artifacts/test_decision_compiler.py -q
```

### Wave 6 - Best-In-Class Acceptance And Closeout

Purpose: make readiness measurable, documented, repeatable, and auditable after
all parallel assurance streams have produced independent evidence. Phases are
parallel in preparation and may be executed in any order; the final closeout
queue only publishes the aggregate result after their independent outputs
exist.

#### Phase 6.1 - Best-In-Class Readiness Aggregator

Scope:

- Add a machine-readable readiness gate that aggregates deterministic tests,
  quality evidence inventory, scorecard tests, benchmark authority checks,
  contract drift checks, system-assurance reports, and local stack smoke.

Files:

- Create: `tools/ci/check_policyos_production_quality_best_in_class.py`
- Test: `tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py`

Acceptance:

- Aggregator reports pass/fail/warn with finding IDs PQL-001 through PQL-024.
- Deterministic gate never requires live LLM calls.
- Live-provider evidence can be attached as optional external evidence.
- Aggregator distinguishes operational failure, quality failure, compliance
  failure, resilience failure, approval failure, and closeout evidence gaps.
- Missing any required serious-profile report ref fails with an owning layer,
  phase, next action, and expected verification command.

Verification:

```bash
uv run python tools/ci/check_policyos_production_quality_best_in_class.py --repo-root . --output-format json --require-passing
uv run pytest tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py -q
```

#### Phase 6.2 - Operator Runbook And Docs Closeout

Scope:

- Document how to run deterministic canaries, live-provider canaries, scenario
  matrix lanes, approval review, override review, and reissue/withdraw flows.
- Include failure triage by layer and phase.
- Document how to interpret data quality, causal validity, security, privacy,
  replay, resilience, human review, provider drift, and decision artifact
  reports.

Files:

- Create: `docs/runbooks/production-quality-canary.md`
- Create: `docs/reference/runtime/production-quality-approval.md`
- Create: `docs/runbooks/production-quality-triage.md`
- Modify: `mkdocs.yml`

Acceptance:

- A new operator can locate bundle, scorecard, failure envelope, approval
  packet, assurance reports, and next action.
- Runbook includes commands and expected outputs.
- Docs do not include secrets or live API keys.
- Runbook has a triage table for every PQL-001 through PQL-024 finding.

Verification:

```bash
uv run python tools/quality/validation/check_docs_gate.py --repo-root .
```

#### Phase 6.3 - Burn-In And Acceptance Evidence

Scope:

- Run deterministic matrix repeatedly.
- Run at least one quarantined live-provider canary with production data.
- Archive scorecard summaries and residual risks.
- Archive system-assurance summaries for data quality, causal validity,
  security, privacy, replay, resilience, human review, provider drift, and
  decision artifact quality.

Files:

- Create: `docs/archive/reports/POLICYOS_PRODUCTION_QUALITY_BEST_IN_CLASS_ACCEPTANCE.md`
- Create: `docs/reference/runtime/production-quality-maturity.md`

Acceptance:

- Deterministic matrix is green.
- Live-provider canary either passes or fails with a clear non-code provider or
  data reason and sanitized bundle.
- Residual risks are explicitly listed with owner and next review date.
- Acceptance evidence includes the readiness aggregator JSON, evidence bundle
  paths, scenario pack versions, quality scorecard summaries, approval packet
  samples, replay result, and resilience matrix output.

Verification:

```bash
uv run python tools/ops_runners/runtime/run_canary_matrix.py --deterministic
PYTHONPATH=src:. uv run --extra runtime --extra ml polisyos-tools runtime check-runtime-api-contract
corepack pnpm --dir apps/runtime-dashboard run test:journeys:smoke
uv run python tools/quality/testing/local_integration_stack.py smoke
```

## Minimum Closeout Gate

This plan can close only when all of the following are true:

- every serious canary emits Lex, Fabric, Foundry, grounding, and conflict refs;
- scorecard is built from persisted runtime refs and included in the evidence
  bundle;
- final policy major claims are grounded or blocked;
- unknown metrics fail before Trinity with suggestions;
- public and hidden benchmark authority packs exist and pass contamination
  guards;
- performance budget evidence is included in canary bundles;
- tenant-scoped artifact ownership is enforced for governed/production access;
- production approval requires pass-quality evidence or a signed override;
- continuous governance can stale/reissue/withdraw published decisions;
- production data quality reports cover missingness, drift, leakage, unit,
  coverage, recency, label, and construct-validity diagnostics;
- causal/statistical method reports pass known-answer, placebo,
  negative-control, sensitivity, uncertainty, and power/sample adequacy gates;
- security and abuse-resistance gates fail closed for prompt/tool/data/provider
  injection, malicious artifacts, unsafe rendering, path traversal, and secret
  exfiltration;
- privacy, licensing, retention, jurisdiction, minimization, redaction, and
  public-export compliance evidence is present for production data and public
  artifacts;
- deterministic replay can reproduce serious runs or produce a typed drift
  explanation with bounded impact;
- load, soak, retry-storm, provider-brownout, CAS-pressure, queue-saturation,
  and dashboard degradation lanes pass their readiness gates;
- human review has calibration evidence for agreement, override correctness,
  burden, escalation, unresolved disagreement, and reviewer attribution;
- provider/model quality drift is monitored across schema, grounding,
  faithfulness, disagreement, latency, cost, provider errors, and quality;
- final decision artifacts pass compiler-grade checks for uncertainty,
  tradeoffs, distributional impact, feasibility, budget, stakeholders,
  implementation risk, monitoring, and residual uncertainty;
- deterministic canary matrix, dashboard smoke, runtime API contract check, and
  local integration stack smoke pass.

Closeout evidence captured on 2026-05-13:

- readiness aggregator:
  `uv run python tools/ci/check_policyos_production_quality_best_in_class.py --repo-root . --output-format json --require-passing`
  returned `pass` with 24 pass, 0 warn, 0 fail;
- serious evidence bundle aggregator:
  `uv run python tools/ci/check_policyos_production_quality_best_in_class.py --repo-root . --serious-evidence-root .polisyos/canary_evidence/profile-research__provider-simulated__data-canonical_production__scenario-public_golden__ui-api_only/20260513T190341Z_45cd1fa85ede4518b5bec75bca2eece1 --output-format json --require-passing`
  returned `pass` with 0 required ref failures;
- deterministic canary matrix selected the research/canonical-production
  closeout lane and passed with scorecard `pass`;
- runtime API contract check, local integration stack smoke, and dashboard
  journey smoke all passed.

## Recommended Execution Order

1. Wave 0: make gaps measurable and red.
2. Wave 1: make owning layers emit real evidence refs.
3. Wave 2: make evidence drive approval readiness.
4. Wave 3: calibrate semantic quality and benchmark authority.
5. Wave 4: harden production operations, tenant isolation, and lifecycle.
6. Wave 5: add independent production-system assurance reports.
7. Wave 6: aggregate, document, burn in, and close out.

The highest return first implementation slice is Wave 1 plus Phase 2.1:
runtime-owned subreport refs and scorecard-from-persisted-refs. That is the
shortest path from "quality can be evaluated" to "PolicyOS proves quality during
real production runs." Wave 5 is the upgrade path from a strong production
quality loop to a best-in-class production system: it proves that the data,
methods, security posture, compliance posture, replayability, resilience,
human review, model governance, and final decision artifacts are worthy of
production trust.
