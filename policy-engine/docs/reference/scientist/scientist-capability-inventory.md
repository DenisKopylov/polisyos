# Scientist Capability Inventory

Related references: [Scientist](index.md), [Best-in-class readiness](best-in-class-readiness.md), [Wave 2 runtime contracts](wave2-runtime-contracts.md), [Remediation status](remediation-status.md), [Workflows](workflows.md), [Nodes](nodes.md).

Owner: `@scientist-owners`
Backup owner: `@platform-owners`
Source of truth: `src/polisyos/scientist/**`, `tests/unit/scientist/**`, `docs/reference/scientist/**`, `docs/plans/active/SCIENTIST_AUDIT_REMEDIATION_PLAN.md`, `docs/plans/archive/SCIENTIST_SOTA_ROADMAP.md`, `docs/plans/archive/SCIENTIST_AGENT_SOTA_ROADMAP.md`, `docs/plans/archive/SCIENTIST_SOTA_AUTORESEARCH_BLUEPRINT.md`, `tools/ci/check_scientist_best_in_class_phase1_0.py`, `tools/ci/check_scientist_best_in_class_phase1_1.py`, `tools/ci/check_scientist_best_in_class_phase1_2.py`, `tools/ci/check_scientist_best_in_class_phase1_3.py`, `tools/ci/check_scientist_best_in_class_phase1_4.py`, `tools/ci/check_scientist_benchmark_authority.py`, `tools/ci/check_scientist_best_in_class_phase1_6.py`, `tools/ci/check_scientist_best_in_class_wave1.py`, `tools/ci/check_scientist_best_in_class_phase2_0.py`, `tools/ci/check_scientist_best_in_class_phase2_1.py`, `tools/ci/check_scientist_best_in_class_phase2_2.py`, `tools/ci/check_scientist_best_in_class_phase2_3.py`, `tools/ci/check_scientist_best_in_class_phase2_4.py`, `tools/ci/check_scientist_best_in_class_phase2_5.py`, `tools/ci/check_scientist_best_in_class_phase2_6.py`, `tools/ci/check_scientist_best_in_class_phase2_7.py`, and `tools/ci/check_scientist_best_in_class_wave2.py`

This inventory is the Phase 1.0 reconciliation layer for the Scientist
best-in-class plan. It records what exists now, which tests and references own
each surface, and how the historical Scientist plans map to the current source
of truth. It intentionally does not add new runtime implementation.

## Source Inventory

| Surface | Source roots | Current role | Reference and tests |
| --- | --- | --- | --- |
| `root_facade` | `src/polisyos/scientist/api.py`, `src/polisyos/scientist/__init__.py`, shim: `src/polisyos/scientist/publisher.py`, `src/polisyos/scientist/publishing/publisher.py`, `src/polisyos/scientist/remediation_status.py`, `src/polisyos/scientist/validation/reliability_scorecard.py` | Stable public facade, publishing, remediation report, scorecard and Phase 2.7 decision-grade compiler. | [index.md](index.md), [decision-grade-compiler.md](decision-grade-compiler.md), [remediation-status.md](remediation-status.md), `tests/unit/scientist/facade/test_api.py`, `tests/unit/scientist/orchestration/orchestrator/test_decision_grade_compiler.py`, `tests/unit/scientist/facade/test_remediation_status.py`, `tests/unit/scientist/governance/test_reliability_scorecard.py`, `tools/ci/check_scientist_best_in_class_phase2_7.py` |
| `wave2_closeout` | `tools/ci/check_scientist_best_in_class_wave2.py`, `docs/reference/scientist/best-in-class-wave2-acceptance.md`, `docs/reference/scientist/best-in-class-maturity.md`, `docs/reference/scientist/wave2-migration-notes.md` | Phase 2.8 gate aggregator, cross-phase invariant fixture, migration notes, maturity model and measured shadow evidence closeout. | [best-in-class-wave2-acceptance.md](best-in-class-wave2-acceptance.md), [best-in-class-maturity.md](best-in-class-maturity.md), [wave2-migration-notes.md](wave2-migration-notes.md), `tests/repo_quality/tools/test_scientist_best_in_class_wave2.py`, `tools/ci/check_scientist_best_in_class_wave2.py` |
| `_adapters` | `src/polisyos/scientist/_adapters/**` | Private adapters from Scientist runtime vocabulary to canonical cross-cutting interfaces such as core observability. | `tests/unit/scientist/orchestration/engine/test_error_semantics.py`, package import gates |
| `_internal` | `src/polisyos/scientist/_internal/**` | Shared Scientist compatibility-shim helpers and private taxonomy glue. | shim/facade tests and package-boundary gates |
| `adapters` | `src/polisyos/scientist/adapters/**` | Bridges to Foundry and Fabric surfaces. | `tests/unit/scientist/adapters/**` |
| `agent` | `src/polisyos/scientist/agent/**`, `src/polisyos/scientist/agent/tools/**` | Drafter, supervisor, reasoning, tool loop, knowledge tools, persistent memory. | [agent-search-reasoning.md](agent-search-reasoning.md), `tests/unit/scientist/agent/**` |
| `autotune` | `src/polisyos/scientist/autotune/**` | Candidate execution, calibration, warm start, Pareto and Hyperband support. | `tests/unit/scientist/autotune/**`, search strategy tests |
| `backtesting` | `src/polisyos/scientist/backtesting/**` | Backtesting helpers, temporal checks, bootstrap, calibration and adversarial tests. | `tests/unit/scientist/backtesting/**` |
| `causal` | `src/polisyos/scientist/causal/**` | Causal execution/readiness/validity helpers. | [causal.md](causal.md), [causal-validity.md](causal-validity.md), `tests/unit/scientist/causal/**` |
| `claims` | canonical: `src/polisyos/scientist/evidence/claims/**`, shim: `src/polisyos/scientist/claims/**` | Phase 1.1 claim/evidence/readiness spine plus Phase 2.1 Claim Ledger lifecycle, append-only audit, diff, export and packet summaries; Phase 2.7 adds expert claim export for decision-grade tiers. | [claims.md](claims.md), [claim-ledger.md](claim-ledger.md), [decision-grade-compiler.md](decision-grade-compiler.md), `tests/unit/scientist/evidence/claims/**`, `tests/unit/scientist/orchestration/orchestrator/test_decision_grade_compiler.py`, `tools/ci/check_scientist_best_in_class_phase1_1.py`, `tools/ci/check_scientist_best_in_class_phase2_1.py`, `tools/ci/check_scientist_best_in_class_phase2_7.py` |
| `continuous_governance` | `src/polisyos/scientist/continuous_governance/**`, canonical: `src/polisyos/scientist/governance/continuous/**` | Phase 2.6 living-decision monitor events, source invalidation bridge, reissue packets, incidents, withdrawal records and public/internal validity reports. | [continuous-governance.md](continuous-governance.md), `tests/unit/scientist/governance/continuous/**`, `tools/ci/check_scientist_best_in_class_phase2_6.py` |
| `compute` | `src/polisyos/scientist/compute/**` | Compute-facing Scientist helpers. | `tests/unit/scientist/compute/**` |
| `cross_graph` | `src/polisyos/scientist/cross_graph/**`, `src/polisyos/scientist/cross_graph/gatherers/**` | Cross-graph evidence gathering, conflict detection, budget and transfer context. | `tests/unit/scientist/cross_graph/**`, `tests/unit/scientist/cross_graph/test_cross_graph_evidence.py` |
| `discovery` | `src/polisyos/scientist/methods/discovery/**`, shim: `src/polisyos/scientist/discovery/**` | Discovery schemas, priors, portfolios, workers, stability and utility judging. | [latent-discovery-producers.md](latent-discovery-producers.md), `tests/unit/scientist/methods/**`, compatibility-era discovery tests |
| `doe` | `src/polisyos/scientist/doe/**` | Design-of-experiments helpers. | `tests/unit/scientist/doe/**` |
| `engine` | canonical: `src/polisyos/scientist/orchestration/engine/**`, shim: `src/polisyos/scientist/engine/**` | Workflow execution, async execution, budgets, checkpoints, runners, telemetry, retry, locks and state merge. | [workflows.md](workflows.md), [phase4-acceptance.md](phase4-acceptance.md), `tests/unit/scientist/orchestration/engine/**`, checkpoint tests |
| `evals` | `src/polisyos/scientist/evals/**` | Phase 1.5 benchmark authority facade, split taxonomy, staleness, leakage, grader metadata, frozen-web/policy-case contracts, plus Phase 2.5 adversarial challenge factory, sentinel/red-team metadata, rotation lineage and near-frontier fresh rotating challenge checks. | [benchmark-authority.md](benchmark-authority.md), [adversarial-challenge-factory.md](adversarial-challenge-factory.md), `tests/unit/scientist/evals/**`, `tools/ci/check_scientist_benchmark_authority.py`, `tools/ci/check_scientist_best_in_class_phase2_5.py` |
| `evidence` | `src/polisyos/scientist/evidence/**`, `src/polisyos/scholar/search/models.py`, `src/polisyos/scientist/agent/tools/scholar_search_tools.py` | Phase 1.3 deep-research evidence stack plus Phase 2.3 source verification VOI for unsupported/contested claims. | [deep-research-evidence.md](deep-research-evidence.md), [voi-scheduler.md](voi-scheduler.md), `tests/unit/scientist/evidence/**`, `tools/ci/check_scientist_best_in_class_phase1_3.py`, `tools/ci/check_scientist_best_in_class_phase2_3.py` |
| `extensions` | `src/polisyos/scientist/extensions/**` | External extension registration boundary for Scientist capabilities. | extension examples and package-boundary gates |
| `feedback` | `src/polisyos/scientist/feedback/**` | Feedback compatibility boundary for replay/evidence lanes. | `tests/unit/scientist/feedback/**` |
| `governance` | `src/polisyos/scientist/governance/**`, `src/polisyos/scientist/governance/passes/**`, `src/polisyos/scientist/governance/legal/**` | Governance pass pipeline, accountability, legal and human-review gates. | [governance-passes.md](governance-passes.md), [governance-accountability.md](governance-accountability.md), governance tests |
| `human_review` | `src/polisyos/scientist/human_review/**`, canonical: `src/polisyos/scientist/governance/human_review/**` | Phase 1.6 human oversight control plane plus Phase 2.3 auditable human escalation VOI. | [human-oversight.md](human-oversight.md), [voi-scheduler.md](voi-scheduler.md), `tests/unit/scientist/governance/human_review/**`, `tools/ci/check_scientist_best_in_class_phase1_6.py`, `tools/ci/check_scientist_best_in_class_phase2_3.py` |
| `kernel` | `src/polisyos/scientist/kernel/**` | Gate protocol, guards, budget and finite-state-machine helpers. | `tests/unit/scientist/kernel/**` |
| `llm` | `src/polisyos/scientist/llm/**`, `src/polisyos/scientist/llm/profiles/**` | LLM gateway, routing, provider profiles and budget-facing helpers. | `tests/unit/scientist/llm/**`, [agent-search-reasoning.md](agent-search-reasoning.md) |
| `memory` | `src/polisyos/scientist/memory/**`, `src/polisyos/scientist/methods/search/failure_cards.py`, `src/polisyos/scientist/methods/search/lessons.py`, `src/polisyos/scientist/methods/research_dag/projections.py` | Phase 2.4 reflexive memory wraps existing failure lessons with applicability scope, contamination guards, warning-only retrieval, revocation and Research DAG attribution. | [reflexive-memory.md](reflexive-memory.md), `tests/unit/scientist/memory/**`, `tools/ci/check_scientist_best_in_class_phase2_4.py` |
| `methods` | `src/polisyos/scientist/methods/**` | Canonical methods home for search, discovery, autotune and Research DAG implementations. | `tests/unit/scientist/methods/**`, research DAG/search/discovery gates |
| `nodes` | `src/polisyos/scientist/nodes/**`, `src/polisyos/scientist/nodes/builtins/**` | Builtin node catalog for planning, data, compile, causal, simulate, governance and decide stages. | [nodes.md](nodes.md), `tests/unit/scientist/nodes/**`, root node tests |
| `orchestration` | `src/polisyos/scientist/orchestration/**` | Canonical workflow, engine, orchestrator and memory implementation namespace. | `tests/unit/scientist/orchestration/**`, [workflows.md](workflows.md), [decision-grade-compiler.md](decision-grade-compiler.md) |
| `orchestrator` | `src/polisyos/scientist/orchestrator/**`, canonical: `src/polisyos/scientist/orchestration/orchestrator/**` | Decision-card and orchestration support, including Phase 2.7 compiler-backed `TrustProvenanceSummary` bridge. | [decision-grade-compiler.md](decision-grade-compiler.md), `tests/unit/scientist/orchestration/orchestrator/test_decision_card.py`, `tests/unit/scientist/orchestration/orchestrator/test_decision_card_uncertainty_render.py`, `tests/unit/scientist/orchestration/orchestrator/test_decision_grade_compiler.py` |
| `policy_design` | `src/polisyos/scientist/policy_design/**` | Policy candidate schema, search, translation, critique, output bundles and Phase 3 certificates. | `tests/unit/scientist/policy_design/**`, decision/output-bundle tests |
| `policy_verified` | `src/polisyos/scientist/policy_verified/**`, canonical: `src/polisyos/scientist/validation/policy_verified/**` | Verified-policy service and models. | `tests/unit/scientist/policy_design/test_policy_verified_nodes.py`, `tests/unit/scientist/policy_design/test_policy_verified_workflow_guard.py`, `tests/unit/scientist/policy_design/test_policy_verified_workflow_e2e.py` |
| `publishing` | `src/polisyos/scientist/publishing/**` | Publishing compatibility boundary for decision-grade outputs. | [decision-grade-compiler.md](decision-grade-compiler.md), compiler tests |
| `provenance` | canonical: `src/polisyos/scientist/evidence/provenance/**`, shim: `src/polisyos/scientist/provenance/**` | Run DAG/provenance JSON support. | [proof-trace-composability.md](proof-trace-composability.md), `tests/unit/scientist/evidence/provenance/**` |
| `research_dag` | `src/polisyos/scientist/methods/research_dag/**`, shim: `src/polisyos/scientist/research_dag/**` | Phase 1.2 typed research DAG sidecar plus Phase 2.2 replay plans, trajectory comparison and source invalidation propagation. | [research-dag.md](research-dag.md), [research-dag-replay.md](research-dag-replay.md), `tests/unit/scientist/methods/research_dag/**`, `tools/ci/check_scientist_best_in_class_phase1_2.py`, `tools/ci/check_scientist_best_in_class_phase2_2.py` |
| `replay` | `src/polisyos/scientist/replay/**`, `src/polisyos/scientist/replay_backend.py` | Replay comparison, verification and backend support. | replay tests, [phase4-acceptance.md](phase4-acceptance.md) |
| `search` | `src/polisyos/scientist/methods/search/**`, shim: `src/polisyos/scientist/search/**` | Multi-fidelity search, benchmark registry, frontier gates, strategies, Phase 2.3 VOI decision/report contracts, `voi_run_report_ref` sidecars, calibration/regret and promotion support. | [frontier-runtime.md](frontier-runtime.md), [calibration-governance.md](calibration-governance.md), [voi-scheduler.md](voi-scheduler.md), `tests/unit/scientist/search/**`, `tests/unit/scientist/methods/**`, `tools/ci/check_scientist_best_in_class_phase2_3.py` |
| `validation` | `src/polisyos/scientist/validation/**` | Fairness, metric validation, benchmark and preflight validation surfaces. | validation tests, [calibration-governance.md](calibration-governance.md) |
| `verification` | `src/polisyos/scientist/verification/**`, canonical: `src/polisyos/scientist/validation/verification/**`, `src/polisyos/scientist/validation/verification/ic/**` | Exact implementation-conformance verification. | `tests/unit/scientist/governance/test_ic_verification.py`, `tests/unit/scientist/governance/test_ic_conformance.py` |
| `workflows` | `src/polisyos/scientist/orchestration/workflows/**`, shim: `src/polisyos/scientist/workflows/**` | Five builtin workflow specs, routing and workflow builder/runtime dispatch. | [workflows.md](workflows.md), workflow selection tests |

## Test Inventory

| Test surface | Coverage role |
| --- | --- |
| `tests/unit/scientist/{facade,nodes,causal,policy_design,replay,governance}/**` | Local hubs for facade, node, decision packet, causal, policy, replay and governance regressions. |
| `tests/unit/scientist/orchestration/orchestrator/test_decision_grade_compiler.py` | Phase 2.7 public/reviewer/expert/machine compiler tiers, public redaction, omission rules, machine trust fields and decision-card bridge. |
| `tests/unit/scientist/adapters/**` | Foundry/Fabric adapter contract tests. |
| `tests/unit/scientist/agent/**`, `tests/unit/scientist/agent/tools/**` | Agent runtime, supervisor, reasoning, tool loop and knowledge-tool tests. |
| `tests/unit/scientist/autotune/**` | Autotune, Pareto, calibration, Hyperband and warm-start tests. |
| `tests/unit/scientist/backtesting/**` | Backtesting, masking, bootstrap, temporal and adversarial tests. |
| `tests/unit/scientist/causal/**` | Causal readiness and execution tests. |
| canonical: `tests/unit/scientist/evidence/claims/**`, shim-era path: `tests/unit/scientist/claims/**` | Claim model, readiness, ledger persistence, projection, validator, lifecycle, audit, diff and export tests. |
| `tests/unit/scientist/continuous_governance/**` | Compatibility-era continuous-governance tests that delegate into governance/continuous coverage. |
| `tests/unit/scientist/governance/continuous/**` | Continuous governance monitors, source invalidation bridge, reissue packets, incidents, reports and governance-link tests. |
| `tests/unit/scientist/compute/**` | Compute helper tests. |
| `tests/unit/scientist/cross_graph/**` | Cross-graph protocols, cache, budget, conflict and gatherer tests. |
| `tests/unit/scientist/methods/**` | Canonical methods import and compatibility shim tests for search, discovery, research DAG, and workflow selection. |
| `tests/unit/scientist/mirror_contracts/**` | Repository mirror-contract tests for Scientist split-module coverage. |
| `tests/unit/scientist/discovery/**` | Compatibility-era discovery schema, active learning, workers, stability and utility tests. |
| `tests/unit/scientist/doe/**` | DOE tests. |
| `tests/unit/scientist/engine/**` | Engine, async executor, runner, lock, budget, telemetry, state and checkpoint tests. |
| `tests/unit/scientist/evals/**` | Benchmark authority, split staleness, leakage redaction, grader metadata, frozen-web and policy-case tests. |
| `tests/unit/scientist/evidence/**` | Deep-research evidence stack tests for safety events, source quality, snippets, claim support, source verification VOI, cache, verifier, tools and DAG projection. |
| `tests/unit/scientist/facade/**` | Public Scientist facade and compatibility-surface regressions. |
| `tests/unit/scientist/feedback/**` | Feedback compatibility and replay/evidence lane tests. |
| `tests/unit/scientist/governance/**` | Governance pass, accountability, legal, human-review and quality gate tests. |
| `tests/unit/scientist/governance/human_review/**` | Human-review packet, decision, queue, governance, VOI escalation and decision-packet integration tests. |
| `tests/unit/scientist/human_review/**` | Human-review compatibility tests that pin legacy import paths. |
| `tests/integration/scientist/**` | Checkpoint resume, workflow tracing and reliability scenario tests. |
| `tests/unit/scientist/kernel/**` | Kernel FSM, guards, budgets and gate protocol tests. |
| `tests/unit/scientist/llm/**` | LLM gateway, provider, budget and routing tests. |
| `tests/unit/scientist/nodes/**` | Builtin node tests. |
| `tests/unit/scientist/orchestration/**` | Canonical orchestration engine, workflow, memory and decision-card tests. |
| `tests/unit/scientist/policy_design/**` | Policy design, hierarchical search, phase certificates and output tests. |
| `tests/unit/scientist/evidence/provenance/**` | Provenance DAG and JSON tests. |
| `tests/unit/scientist/methods/research_dag/**` | Research DAG model, builder, CAS persistence, replay, replay planning, trajectory comparison, source invalidation, diff, projection and workflow sidecar tests. |
| `tests/unit/scientist/replay/**` | Replay and comparison tests. |
| `tests/unit/scientist/search/**`, `tests/unit/scientist/search/funnel/**`, `tests/unit/scientist/search/strategies/**` | Compatibility-era search controller, funnel, strategy, benchmark, VOI models/reports/calibration and promotion tests. |
| `tests/unit/scientist/validation/**` | Validation, fairness and metric tests. |
| `tests/unit/scientist/orchestrator_v2/**` | Wave 2 runtime compatibility, additive packet and feature-flag contract tests. |
| `tests/repo_quality/tools/test_scientist_best_in_class_wave2.py` | Phase 2.8 Wave 2 gate regression, missing phase-gate failure path, migration-token check, public hidden-ref export block, VOI human-review suppression block, memory canary block, reissue-link block and unexplained-claim-change invariant. |
| `tests/unit/scientist/workflows/**` | Workflow specs and builder pinning tests. |

## Reference Inventory

| Reference page | Current role |
| --- | --- |
| [agent-search-reasoning.md](agent-search-reasoning.md) | Optional agent/search rollout and reasoning gates. |
| [benchmark-authority.md](benchmark-authority.md) | Benchmark authority, hidden eval packs, leakage, staleness and promotion evidence policy. |
| [best-in-class-readiness.md](best-in-class-readiness.md) | Canonical best-in-class readiness and active phase index. |
| [best-in-class-wave1-acceptance.md](best-in-class-wave1-acceptance.md) | Wave 1 acceptance gate over phases 1.0-1.6, claim/DAG refs, benchmark authority and high-risk human review. |
| [best-in-class-wave2-acceptance.md](best-in-class-wave2-acceptance.md) | Wave 2 acceptance gate over phases 2.0-2.7, cross-phase invariants and measured shadow evidence. |
| [best-in-class-maturity.md](best-in-class-maturity.md) | Best-in-class maturity levels after Wave 2 closeout. |
| [calibration-governance.md](calibration-governance.md) | Calibration, fairness and governance validation posture. |
| [causal-validity-acceptance.md](causal-validity-acceptance.md) | Causal-validity acceptance surface. |
| [causal-validity.md](causal-validity.md) | Causal-validity diagnostics and source of truth. |
| [causal.md](causal.md) | Causal Scientist reference. |
| [claim-ledger.md](claim-ledger.md) | Claim Ledger lifecycle, append-only audit, claim-level diff, export and packet blocked-claim summaries. |
| [claims.md](claims.md) | Claim/evidence/readiness spine, `claims_ref` integrations and naked-claim validators. |
| [continuous-governance.md](continuous-governance.md) | Continuous governance monitor events, source invalidation bridge, reissue/withdrawal semantics and validity report redaction. |
| [decision-grade-compiler.md](decision-grade-compiler.md) | Decision-grade compiler output tiers, omissions, public redaction and frontend trust/provenance hooks. |
| [deep-research-evidence.md](deep-research-evidence.md) | Deep-research evidence stack, safe fetch, source quality, snippets and claim-support mapping. |
| [frontier-runtime.md](frontier-runtime.md) | Frontier capability rollout contract. |
| [governance-accountability.md](governance-accountability.md) | Governance accountability artifacts. |
| [governance-passes.md](governance-passes.md) | Governance pass registry and runtime pipeline. |
| [human-oversight.md](human-oversight.md) | Human oversight packets, review decisions, queue, rights checklist and release-gate semantics. |
| [index.md](index.md) | Scientist reference entrypoint. |
| [latent-discovery-producers.md](latent-discovery-producers.md) | Latent discovery producers. |
| [nodes.md](nodes.md) | Builtin node contract and registry. |
| [phase0-acceptance.md](phase0-acceptance.md) | Phase 0 acceptance evidence. |
| [phase1-acceptance.md](phase1-acceptance.md) | Phase 1 acceptance evidence. |
| [phase3-acceptance.md](phase3-acceptance.md) | Phase 3 acceptance evidence. |
| [phase4-acceptance.md](phase4-acceptance.md) | Phase 4 distributed/frontier acceptance evidence. |
| [proof-trace-composability.md](proof-trace-composability.md) | Proof trace and provenance composability. |
| [research-dag.md](research-dag.md) | Research DAG sidecar, `research_dag_ref`, replay/diff and redaction guarantees. |
| [research-dag-replay.md](research-dag-replay.md) | Research DAG replay plans, trajectory comparison, source invalidation and audit-safe replay exports. |
| [voi-scheduler.md](voi-scheduler.md) | VOI decision/report contracts, scheduler report emission, source verification, human escalation, calibration/regret and mandatory-gate rules. |
| [reflexive-memory.md](reflexive-memory.md) | Reflexive-memory failure lessons, applicability, contamination guards, warning-only retrieval, revocation and Research DAG memory attribution. |
| [adversarial-challenge-factory.md](adversarial-challenge-factory.md) | Phase 2.5 challenge generation from failure cards, review-before-hidden, sentinel/red-team metadata, rotating pack lineage and benchmark-authority near-frontier checks. |
| [reliability-scorecard.md](reliability-scorecard.md) | Reliability scorecard and gates. |
| [remediation-status.md](remediation-status.md) | Machine-readable remediation closure report. |
| [scientist-capability-inventory.md](scientist-capability-inventory.md) | This Phase 1.0 source/test/reference/historical inventory. |
| [system-pipeline-architecture.md](system-pipeline-architecture.md) | End-to-end Scientist system pipeline topology and architecture narrative. |
| [wave2-runtime-contracts.md](wave2-runtime-contracts.md) | Phase 2.0 Scientist OS foundation: ADRs, package boundaries, additive artifact versioning, feature-flag defaults and compatibility gate. |
| [wave2-migration-notes.md](wave2-migration-notes.md) | Wave 2 public fields, flags, dual-read migration rules and rollback notes. |
| [workflows.md](workflows.md) | Workflow surface, routing and builtin DAGs. |

## Active Workflow And Node Surface

| Runtime surface | Current inventory |
| --- | --- |
| Builtin workflows | `scientist_default`, `scientist_discovery`, `scientist_causal_full`, `scientist_policy_verified`, `scientist_policy_design`. |
| Builtin node families | `planning`, `data`, `compile`, `causal`, `simulate`, `governance`, `decide`, plus engine builtins. |
| Decision-bearing hot paths | `scientist_policy_design`, `scientist_policy_verified`, `scientist_causal_full`, and default governed simulation decision packets. |
| Explicitly gated surfaces | Frontier causal/search methods, advanced agent reasoning/search policies, deep research evidence hardening, Claim Ledger v2 production enforcement, Research DAG publication/replay requirement, source invalidation reissue triggers, VOI default-enable, challenge factory hidden admission/default use, continuous-governance withdrawal and Wave 2 closeout production promotion. |

## Historical Roadmap Reconciliation

Allowed statuses are `closed`, `superseded`, `still_gated`, `research_first`,
and `not_in_scope`.

### Audit Remediation Plan

Source: `docs/plans/active/SCIENTIST_AUDIT_REMEDIATION_PLAN.md`.

The audit remediation plan is not archived, but Phase 1.0 treats it as
historical closure input because its workstreams are already represented by
`src/polisyos/scientist/remediation_status.py`, [remediation-status.md](remediation-status.md),
and the existing Scientist phase gates.

| Historical item | Status | Current reference or gate | Reconciliation note |
| --- | --- | --- | --- |
| `SCIENTIST_AUDIT_REMEDIATION_PLAN:WS-0A` | `closed` | [remediation-status.md](remediation-status.md), `tools/ci/check_scientist_phase0_gate.py` | Async, locking and lifecycle correctness are closed by the machine-readable remediation report. |
| `SCIENTIST_AUDIT_REMEDIATION_PLAN:WS-0B` | `closed` | [remediation-status.md](remediation-status.md), `tools/ci/check_scientist_phase0_gate.py` | Budget, request correctness, security and scientific hotfixes are closed by the Phase 0 gate. |
| `SCIENTIST_AUDIT_REMEDIATION_PLAN:WS-1A` | `closed` | [remediation-status.md](remediation-status.md), `tools/ci/check_scientist_phase1_gate.py` | Error semantics and degraded-mode policy are closed by the Phase 1 gate and scorecard. |
| `SCIENTIST_AUDIT_REMEDIATION_PLAN:WS-1B` | `closed` | [remediation-status.md](remediation-status.md), branch-state tests | Atomic mutation, merge semantics and deterministic execution are closed by branch-state and workflow regressions. |
| `SCIENTIST_AUDIT_REMEDIATION_PLAN:WS-1C` | `closed` | [reliability-scorecard.md](reliability-scorecard.md), [phase1-acceptance.md](phase1-acceptance.md) | Observability, metrics export and operational hygiene are represented by the reliability evidence surface. |
| `SCIENTIST_AUDIT_REMEDIATION_PLAN:WS-1D` | `closed` | [reliability-scorecard.md](reliability-scorecard.md), `tools/ci/check_scientist_reliability.py` | Test and benchmark program is closed for the accepted remediation scope. |
| `SCIENTIST_AUDIT_REMEDIATION_PLAN:WS-2A` | `closed` | [remediation-status.md](remediation-status.md), `tools/ci/check_scientist_phase2_ratchet.py` | Hot-path memory, complexity and cache efficiency are closed by Phase 2 evidence and ratchets. |
| `SCIENTIST_AUDIT_REMEDIATION_PLAN:WS-2B` | `closed` | [remediation-status.md](remediation-status.md), `tools/ci/check_scientist_phase2_ratchet.py` | API simplification, decomposition and type-safety debt are closed for the accepted Phase 2 slice. |
| `SCIENTIST_AUDIT_REMEDIATION_PLAN:WS-3A` | `closed` | [causal-validity.md](causal-validity.md), [phase3-acceptance.md](phase3-acceptance.md) | Causal inference and statistical validity claims are represented by Phase 3 artifacts. |
| `SCIENTIST_AUDIT_REMEDIATION_PLAN:WS-3B` | `closed` | [calibration-governance.md](calibration-governance.md), [governance-accountability.md](governance-accountability.md) | Governance, fairness, calibration and accountability are closed for the accepted remediation scope. |
| `SCIENTIST_AUDIT_REMEDIATION_PLAN:WS-3C` | `closed` | [agent-search-reasoning.md](agent-search-reasoning.md), [frontier-runtime.md](frontier-runtime.md) | Search, optimization and agent reasoning are implemented with explicit non-default gates where needed. |
| `SCIENTIST_AUDIT_REMEDIATION_PLAN:WS-4A` | `closed` | [phase4-acceptance.md](phase4-acceptance.md), replay/checkpoint/runner tests | Runtime scalability and distributed safety are closed by Phase 4 distributed evidence. |
| `SCIENTIST_AUDIT_REMEDIATION_PLAN:WS-4B` | `closed` | [frontier-runtime.md](frontier-runtime.md), benchmark registry tests | Frontier research backlog is represented as gated runtime capability posture. |

### Archived SOTA Roadmap

Source: `docs/plans/archive/SCIENTIST_SOTA_ROADMAP.md`.

| Historical item | Status | Current reference or gate | Reconciliation note |
| --- | --- | --- | --- |
| `SCIENTIST_SOTA_ROADMAP:WS5.1` | `closed` | `engine/circuit_breaker.py`, `engine/retry.py`, engine tests | Circuit breaking, retry and lifecycle containment are part of the accepted engine surface. |
| `SCIENTIST_SOTA_ROADMAP:WS5.2` | `closed` | `engine/async_executor.py`, [phase4-acceptance.md](phase4-acceptance.md) | Async rollback, tier execution and state handling are accepted through Phase 4 evidence. |
| `SCIENTIST_SOTA_ROADMAP:WS5.3` | `closed` | `engine/checkpoint.py`, checkpoint tests | Checkpoint GC, schema/version handling and resume evidence are covered. |
| `SCIENTIST_SOTA_ROADMAP:WS5.4` | `closed` | `engine/budget.py`, `engine/budget_middleware.py`, budget tests | Budget reservation, release and ledger mutation behavior are covered. |
| `SCIENTIST_SOTA_ROADMAP:WS5.5` | `closed` | `engine/fan_out.py`, `engine/condition.py`, `engine/state_merge.py` | Fan-out, condition and merge behavior are part of the current engine surface. |
| `SCIENTIST_SOTA_ROADMAP:WS6.1` | `closed` | `agent/tools/tool_loop.py`, `tests/unit/scientist/agent/tools/**` | Tool loop hardening exists; best-in-class promotion unification moves to Phase 1.4. |
| `SCIENTIST_SOTA_ROADMAP:WS6.2` | `closed` | `engine/convergence.py`, convergence tests | Convergence detection is implemented in the engine surface. |
| `SCIENTIST_SOTA_ROADMAP:WS6.3` | `closed` | `agent/router.py`, agent tests | Routing exists; stateful supervisor promotion remains gated by Phase 1.4. |
| `SCIENTIST_SOTA_ROADMAP:WS6.4` | `closed` | `agent/memory.py`, persistent memory tests | Persistent memory exists; reflexive memory contamination rules move to Wave 2. |
| `SCIENTIST_SOTA_ROADMAP:WS6.5` | `closed` | `autotune/warm_start.py`, `search/stopping.py`, search tests | Warm-start and cost-aware stopping surfaces exist. |
| `SCIENTIST_SOTA_ROADMAP:WS6.6` | `closed` | `search/strategies/bayesian.py`, `search/strategies/**` | Bayesian and advanced search policies exist behind explicit rollout posture. |
| `SCIENTIST_SOTA_ROADMAP:WS7.1` | `closed` | `governance/**`, [governance-passes.md](governance-passes.md) | Governance pass pipeline is documented and tested. |
| `SCIENTIST_SOTA_ROADMAP:WS7.2` | `closed` | `governance/accountability.py`, `governance/report.py` | Governance decisions and accountability artifacts are repo-tracked. |
| `SCIENTIST_SOTA_ROADMAP:WS7.3` | `closed` | `provenance/**`, `policy_design/output.py` | Audit bundles and provenance are part of current accepted output surfaces. |
| `SCIENTIST_SOTA_ROADMAP:WS7.4` | `closed` | masking, PII and data-plane tests | Masking and PII gates are represented in governance and backtesting tests. |
| `SCIENTIST_SOTA_ROADMAP:WS7.5` | `closed` | workflow builder quota hooks, budget tests | Quota and budget hardening are accepted for the current runtime scope. |
| `SCIENTIST_SOTA_ROADMAP:WS8.1` | `closed` | `engine/metrics_otel.py`, operational monitoring tests | SLO metrics and monitoring hooks exist. |
| `SCIENTIST_SOTA_ROADMAP:WS8.2` | `closed` | `engine/trace_attributes.py`, tracing tests | Distributed trace attributes and degradation tests are covered. |
| `SCIENTIST_SOTA_ROADMAP:WS8.3` | `closed` | LLM/budget metrics and scorecard surfaces | Cost and budget evidence is represented in runtime and gate tests. |
| `SCIENTIST_SOTA_ROADMAP:WS8.4` | `closed` | `provenance/run_dag.py`, provenance tests | Provenance DAG coverage exists. |
| `SCIENTIST_SOTA_ROADMAP:WS8.5` | `closed` | `replay/diff.py`, replay tests | Replay semantic diff exists for current replay scope. |
| `SCIENTIST_SOTA_ROADMAP:WS9.1` | `closed` | `tests/unit/scientist/nodes/**`, root node tests | Node unit test coverage exists across builtin families. |
| `SCIENTIST_SOTA_ROADMAP:WS9.2` | `closed` | `tests/unit/scientist/governance/**` | Governance pass isolated tests exist. |
| `SCIENTIST_SOTA_ROADMAP:WS9.3` | `closed` | `tests/integration/scientist/**`, workflow tests | Workflow integration and checkpoint-resume tests exist. |
| `SCIENTIST_SOTA_ROADMAP:WS9.4` | `closed` | property tests under `tests/unit/scientist/engine/**` and evidence source tests | Property-based checks are represented on accepted hot paths. |
| `SCIENTIST_SOTA_ROADMAP:WS9.5` | `closed` | API, adapter and workflow tests | API and adapter surfaces are covered. |
| `SCIENTIST_SOTA_ROADMAP:WS9.6` | `still_gated` | mutation tooling references in `tools/registry.py` | Mutation testing is not the Phase 1.0 acceptance barrier; keep as optional reliability hardening. |
| `SCIENTIST_SOTA_ROADMAP:WS10.1` | `closed` | `engine/runner/{local,ray,temporal}_runner.py`, runner tests | Runner backends are represented and covered. |
| `SCIENTIST_SOTA_ROADMAP:WS10.2` | `closed` | `engine/locks/**`, lock tests | Distributed lock surfaces are present and tested. |
| `SCIENTIST_SOTA_ROADMAP:WS10.3` | `closed` | tenant trace attributes, transfer context, tenant isolation tests | Multi-tenant isolation has direct tests for current runtime scope. |
| `SCIENTIST_SOTA_ROADMAP:WS10.4` | `still_gated` | runner autoscaler/distributed tier surfaces | Horizontal scaling exists as infrastructure surface, but production scale-out remains deployment-gated. |
| `SCIENTIST_SOTA_ROADMAP:WS11.1` | `closed` | `autotune/**`, `search/strategies/**` | Bayesian and multi-objective autotune/search are implemented. |
| `SCIENTIST_SOTA_ROADMAP:WS11.2` | `closed` | `cross_graph/**` | Cross-graph refactoring is represented by protocols, cache, budget, conflict and gatherers. |
| `SCIENTIST_SOTA_ROADMAP:WS11.3` | `closed` | `backtesting/**` | Backtesting enhancements are covered by backtesting tests. |
| `SCIENTIST_SOTA_ROADMAP:WS11.4` | `closed` | [nodes.md](nodes.md), node tests | Node hardening is accepted for current builtin node surface. |
| `SCIENTIST_SOTA_ROADMAP:WS11.5` | `closed` | `llm/**`, agent tests | LLM subsystem baseline is implemented; provider/context promotion remains gated elsewhere. |
| `SCIENTIST_SOTA_ROADMAP:WS11.6` | `closed` | `doe/**`, DOE tests | DOE package and tests exist. |
| `SCIENTIST_SOTA_ROADMAP:WS11.7` | `closed` | `policy_verified/**`, verified-policy tests | Policy Verified workflow and service are implemented and tested. |

### Archived Agent Roadmap

Source: `docs/plans/archive/SCIENTIST_AGENT_SOTA_ROADMAP.md`.

| Historical item | Status | Current reference or gate | Reconciliation note |
| --- | --- | --- | --- |
| `SCIENTIST_AGENT_SOTA_ROADMAP:PHASE0` | `closed` | Phase 0/1 gates, LLM/budget tests | Correctness and budget bugs are covered by existing remediation gates. |
| `SCIENTIST_AGENT_SOTA_ROADMAP:PHASE1` | `closed` | [deep-research-evidence.md](deep-research-evidence.md), `src/polisyos/scientist/evidence/**`, `tests/unit/scientist/evidence/**`, `tools/ci/check_scientist_best_in_class_phase1_3.py` | First-party deep research evidence hardening is now Phase 1.3; production fail-closed rollout remains feature-flagged. |
| `SCIENTIST_AGENT_SOTA_ROADMAP:PHASE2` | `closed` | `agent/supervisor.py`, [agent-search-reasoning.md](agent-search-reasoning.md), [agent-capability-promotion.md](agent-capability-promotion.md), `tools/ci/check_scientist_best_in_class_phase1_4.py` | Supervisor pieces now feed the unified Phase 1.4 agent promotion surface; default enablement still requires typed offline and benchmark evidence. |
| `SCIENTIST_AGENT_SOTA_ROADMAP:PHASE3` | `research_first` | reflexion and memory tests | Reflexive evaluator-optimizer memory needs Wave 2 contamination and measurement rules. |
| `SCIENTIST_AGENT_SOTA_ROADMAP:PHASE4` | `still_gated` | `llm/profiles/**`, context references | Provider/context optimization exists in pieces but is not yet governed as a Context OS. |

### Archived Autoresearch Blueprint

Source: `docs/plans/archive/SCIENTIST_SOTA_AUTORESEARCH_BLUEPRINT.md`.

| Historical item | Status | Current reference or gate | Reconciliation note |
| --- | --- | --- | --- |
| `SCIENTIST_SOTA_AUTORESEARCH_BLUEPRINT:PHASE_A` | `closed` | `search/funnel/**`, search funnel tests | Funnel foundation exists as the current search platform. |
| `SCIENTIST_SOTA_AUTORESEARCH_BLUEPRINT:PHASE_B` | `closed` | `policy_design/**`, policy-design workflow tests | Policy design on the funnel is implemented. |
| `SCIENTIST_SOTA_AUTORESEARCH_BLUEPRINT:PHASE_C` | `closed` | `discovery/**`, discovery tests | Discovery algorithm portfolio surfaces exist. |
| `SCIENTIST_SOTA_AUTORESEARCH_BLUEPRINT:PHASE_D` | `research_first` | Wave 2 plan, search/autotune/reflexion primitives | Self-improving loops need VOI, reflexive memory, challenge factory and contamination controls before broader rollout. |

## Phase 1.0 Validation Contract

The CI gate for this document checks:

- required Phase 1.0 docs exist;
- active capability ids are present in
  [best-in-class-readiness.md](best-in-class-readiness.md);
- every top-level `src/polisyos/scientist/**` package is mentioned here;
- every top-level `tests/unit/scientist/**` package is mentioned here;
- every `docs/reference/scientist/*.md` page is listed here, including
  [claims.md](claims.md), [research-dag.md](research-dag.md),
  [deep-research-evidence.md](deep-research-evidence.md), and
  [best-in-class-wave1-acceptance.md](best-in-class-wave1-acceptance.md);
- every historical Scientist roadmap heading extracted from historical Scientist
  plan docs has one allowed reconciliation status.

Run:

```bash
uv run python tools/ci/check_scientist_best_in_class_phase1_0.py --repo-root . --output-format json --require-passing
uv run python tools/ci/check_scientist_best_in_class_wave1.py --repo-root . --output-format json --require-passing
```
