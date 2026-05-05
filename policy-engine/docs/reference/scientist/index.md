# Scientist

Related explanation: [Governance Model](../../explanation/governance-model.md).

Owner: `@scientist-owners`
Backup owner: `@platform-owners`
Source of truth: `src/polisyos/scientist/__init__.py`, `src/polisyos/scientist/api.py`, `src/polisyos/scientist/workflows/**`, `src/polisyos/scientist/nodes/**`, `src/polisyos/scientist/governance/**`, `src/polisyos/scientist/human_review/**`, `src/polisyos/scientist/claims/**`, `src/polisyos/scientist/research_dag/**`, `src/polisyos/scientist/evidence/**`, `src/polisyos/scientist/evals/**`, `src/polisyos/scientist/memory/**`, `src/polisyos/scientist/continuous_governance/**`, `src/polisyos/scientist/causal/validity.py`, `src/polisyos/scientist/agent/**`, `src/polisyos/scientist/search/**`, `src/polisyos/scientist/reliability_scorecard.py`, `docs/reference/scientist/best-in-class-readiness.md`, `docs/reference/scientist/scientist-capability-inventory.md`, `docs/reference/scientist/best-in-class-wave1-acceptance.md`, `docs/reference/scientist/best-in-class-wave2-acceptance.md`, `docs/reference/scientist/best-in-class-maturity.md`, `docs/reference/scientist/wave2-migration-notes.md`, `docs/reference/scientist/wave2-runtime-contracts.md`, `docs/reference/scientist/research-dag-replay.md`, `docs/reference/scientist/voi-scheduler.md`, `docs/reference/scientist/reflexive-memory.md`, `docs/reference/scientist/adversarial-challenge-factory.md`, `docs/reference/scientist/continuous-governance.md`, `docs/reference/scientist/decision-grade-compiler.md`, and the linked tests/tools on each page

> Owner lane: `L6 Scientist`  
> Type: Manual reference (not generated).  
> Source of truth: `src/polisyos/scientist/__init__.py`, `src/polisyos/scientist/api.py`, `src/polisyos/scientist/workflows/**`, `src/polisyos/scientist/nodes/**`, `src/polisyos/scientist/governance/**`, `src/polisyos/scientist/human_review/**`, `src/polisyos/scientist/claims/**`, `src/polisyos/scientist/research_dag/**`, `src/polisyos/scientist/evidence/**`, `src/polisyos/scientist/evals/**`, `src/polisyos/scientist/memory/**`, `src/polisyos/scientist/continuous_governance/**`, `src/polisyos/scientist/causal/validity.py`, `src/polisyos/scientist/agent/**`, `src/polisyos/scientist/search/**`, `src/polisyos/scientist/reliability_scorecard.py`, `docs/reference/scientist/best-in-class-readiness.md`, `docs/reference/scientist/scientist-capability-inventory.md`, `docs/reference/scientist/best-in-class-wave1-acceptance.md`, `docs/reference/scientist/best-in-class-wave2-acceptance.md`, `docs/reference/scientist/best-in-class-maturity.md`, `docs/reference/scientist/wave2-migration-notes.md`, `docs/reference/scientist/wave2-runtime-contracts.md`, `docs/reference/scientist/research-dag-replay.md`, `docs/reference/scientist/voi-scheduler.md`, `docs/reference/scientist/reflexive-memory.md`, `docs/reference/scientist/adversarial-challenge-factory.md`, `docs/reference/scientist/continuous-governance.md`, `docs/reference/scientist/decision-grade-compiler.md`, and the linked tests/tools on each page.

`polisyos.scientist` is the orchestration layer that turns an `ExperimentState`
into a routed workflow run, executes builtin nodes against a CAS-backed
execution context, applies governance, and publishes replayable decision
artifacts.

## Stable Facade

| Export            | Source                            | Role                                               |
| ----------------- | --------------------------------- | -------------------------------------------------- |
| `run_experiment`  | `polisyos.scientist.api`          | Top-level execution entrypoint.                    |
| `ExperimentState` | `polisyos.scientist.engine.state` | Workflow state contract passed across nodes.       |
| `get_metrics`     | `polisyos.core.observability`     | Shared metrics factory exposed through the facade. |
| `get_tracer`      | `polisyos.core.observability`     | Shared tracer factory exposed through the facade.  |

`run_experiment()` rejects unknown top-level state keys, resolves observability,
selects a workflow id through `resolve_workflow_id()`, and delegates execution
to the workflow builder/runtime.

## Workflow Surface

The current routed workflow surface consists of five builtin workflow ids:

| `workflow_id`               | Primary module                 | Current role                                                                                                                      |
| --------------------------- | ------------------------------ | --------------------------------------------------------------------------------------------------------------------------------- |
| `scientist_default`         | `workflows/default.py`         | Baseline governed simulation path.                                                                                                |
| `scientist_discovery`       | `workflows/discovery.py`       | Discovery-only blueprint runtime without Foundry/governance execution.                                                            |
| `scientist_causal_full`     | `workflows/causal_full.py`     | Serious/governed causal path with literature prior, graph reconciliation, readiness, transportability, and downstream governance. |
| `scientist_policy_verified` | `workflows/policy_verified.py` | Verified-policy path without hierarchical search.                                                                                 |
| `scientist_policy_design`   | `workflows/policy_design.py`   | Policy-design path with verified sourcing, hierarchical search, readiness, and translation/output bundle stages.                  |

## Reference Map

| Topic                                                | Reference                                              | Source of truth                                                                                                                                            |
| ---------------------------------------------------- | ------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Workflow engine, routing, and builtin DAGs           | [workflows.md](workflows.md)                           | `src/polisyos/scientist/workflows/**`, `src/polisyos/scientist/api.py`, `tests/unit/scientist/workflows/**`, `tests/unit/scientist/workflows/test_workflow_selection.py`       |
| Builtin node contract and registry                   | [nodes.md](nodes.md)                                   | `src/polisyos/scientist/nodes/**`, `src/polisyos/scientist/engine/protocol.py`, `tests/unit/scientist/nodes/**`                                                 |
| Governance registry and runtime pipeline             | [governance-passes.md](governance-passes.md)           | `src/polisyos/scientist/governance/**`, `pyproject.toml`, `tests/unit/scientist/governance/**`                                                                  |
| Claim/evidence/readiness spine                       | [claims.md](claims.md)                                 | `src/polisyos/scientist/claims/**`, decision/governance/causal integration targets, `tests/unit/scientist/claims/**`, Phase 1.1 gate                            |
| Claim Ledger lifecycle                               | [claim-ledger.md](claim-ledger.md)                     | `src/polisyos/scientist/claims/lifecycle.py`, `claims/audit.py`, `claims/diff.py`, `claims/export.py`, packet and policy-output summaries, Phase 2.1 gate |
| Research DAG sidecar                                 | [research-dag.md](research-dag.md)                     | `src/polisyos/scientist/research_dag/**`, workflow/provenance/tool-loop integrations, `tests/unit/scientist/research_dag/**`, Phase 1.2 gate                    |
| Research DAG replay                                  | [research-dag-replay.md](research-dag-replay.md)       | `src/polisyos/scientist/research_dag/replay.py`, `comparison.py`, `invalidation.py`, extended `diff.py`, `tests/unit/scientist/research_dag/test_replay_plan.py`, `test_comparison.py`, `test_invalidation.py`, Phase 2.2 gate |
| VOI scheduler                                        | [voi-scheduler.md](voi-scheduler.md)                   | `src/polisyos/scientist/search/voi_models.py`, `search/voi_scheduler.py`, `search/voi_calibration.py`, `human_review/voi_escalation.py`, source-verification VOI in `evidence/claim_support.py`, `voi_run_report_ref` sidecar, Phase 2.3 gate |
| Reflexive memory                                     | [reflexive-memory.md](reflexive-memory.md)             | `src/polisyos/scientist/memory/**`, existing `search/failure_cards.py` and `search/lessons.py`, memory-to-DAG projection, hidden-eval/canary guards, Phase 2.4 gate |
| Adversarial challenge factory                       | [adversarial-challenge-factory.md](adversarial-challenge-factory.md) | `src/polisyos/scientist/evals/challenge_factory.py`, `sentinels.py`, `red_team.py`, `rotation.py`, benchmark authority challenge lineage and Phase 2.5 gate |
| Continuous governance and reissue                   | [continuous-governance.md](continuous-governance.md) | `src/polisyos/scientist/continuous_governance/**`, Claim Ledger lifecycle invalidation, Research DAG invalidation bridge, governance report/decision packet links and Phase 2.6 gate |
| Decision-grade research compiler                   | [decision-grade-compiler.md](decision-grade-compiler.md) | `src/polisyos/scientist/publisher.py`, `src/polisyos/scientist/orchestrator/decision_card.py`, `src/polisyos/scientist/claims/export.py`, public/reviewer/expert/machine output tiers and Phase 2.7 gate |
| Deep research evidence stack                         | [deep-research-evidence.md](deep-research-evidence.md) | `src/polisyos/scholar/search/models.py`, `src/polisyos/scientist/evidence/**`, Scholar search tools, `tests/unit/scientist/evidence/**`, Phase 1.3 gate         |
| Agent capability promotion                           | [agent-capability-promotion.md](agent-capability-promotion.md) | `src/polisyos/scientist/agent/runtime_capabilities.py`, `src/polisyos/scientist/agent/promotion.py`, `src/polisyos/scientist/agent/tool_contracts.py`, `src/polisyos/scientist/agent/supervisor_eval.py`, Phase 1.4 gate |
| Benchmark authority                                  | [benchmark-authority.md](benchmark-authority.md)       | `src/polisyos/scientist/search/benchmark_registry.py`, `src/polisyos/scientist/evals/**`, benchmark registry tests, Phase 1.5 gate                     |
| Human oversight                                      | [human-oversight.md](human-oversight.md)               | `src/polisyos/scientist/human_review/**`, governance report links, decision-packet human-review validation, `tests/unit/scientist/human_review/**`, Phase 1.6 gate |
| Exact IC verification and implementation conformance | [governance-passes.md](governance-passes.md)           | `src/polisyos/scientist/verification/ic/**`, `tests/unit/scientist/governance/test_ic_verification.py`, `tests/unit/scientist/governance/test_ic_conformance.py`                           |
| Default-path causal-validity diagnostics             | [causal-validity.md](causal-validity.md)               | `src/polisyos/scientist/causal/validity.py`, `src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py`, decision-packet tests              |
| Agent reasoning and advanced search rollout gates    | [agent-search-reasoning.md](agent-search-reasoning.md) | `src/polisyos/scientist/agent/reasoning.py`, `src/polisyos/scientist/agent/eval_harness.py`, `src/polisyos/scientist/search/strategies/advanced_policy.py` |
| Reliability scorecard and phase gates                | [reliability-scorecard.md](reliability-scorecard.md)   | `src/polisyos/scientist/reliability_scorecard.py`, `tools/ci/check_scientist_*.py`, `tests/unit/scientist/governance/test_reliability_scorecard.py`                        |
| Best-in-class readiness and active plan index        | [best-in-class-readiness.md](best-in-class-readiness.md) | `docs/plans/active/SCIENTIST_BEST_IN_CLASS_PLAN.md`, `tools/ci/check_scientist_best_in_class_phase1_0.py`, `tests/tools/test_scientist_best_in_class_phase1_0.py` |
| Capability inventory and historical plan mapping     | [scientist-capability-inventory.md](scientist-capability-inventory.md) | `src/polisyos/scientist/**`, `tests/unit/scientist/**`, `docs/reference/scientist/**`, historical Scientist plans |
| Wave 1 acceptance                                    | [best-in-class-wave1-acceptance.md](best-in-class-wave1-acceptance.md) | Phase 1.0-1.6 gates, claim/DAG refs, benchmark-authority default-enable checks, human-review checks, `tools/ci/check_scientist_best_in_class_wave1.py` |
| Wave 2 runtime contracts                             | [wave2-runtime-contracts.md](wave2-runtime-contracts.md) | Accepted ADRs 0129-0132, package boundaries, additive artifact versioning, feature-flag defaults, `tools/ci/check_scientist_best_in_class_phase2_0.py` |
| Wave 2 acceptance                                    | [best-in-class-wave2-acceptance.md](best-in-class-wave2-acceptance.md) | Phase 2.0-2.7 gates, cross-phase invariants, measured shadow evidence and `tools/ci/check_scientist_best_in_class_wave2.py` |
| Wave 2 migration notes                               | [wave2-migration-notes.md](wave2-migration-notes.md) | Public fields, flags, dual-read semantics and rollback notes for Wave 2 sidecars. |
| Best-in-class maturity                               | [best-in-class-maturity.md](best-in-class-maturity.md) | Maturity levels for claim ledger, research DAG, benchmark authority, human review, continuous governance and decision-grade compiler. |

## D1 To D2 Evidence Map

| D1 phase | Current D2 reference anchor                                                                                                                    | Primary evidence                                                                                                                                             |
| -------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Phase 0  | [reliability-scorecard.md](reliability-scorecard.md), [workflows.md](workflows.md), [nodes.md](nodes.md)                                       | `tools/ci/check_scientist_phase0_gate.py`, `tests/tools/test_scientist_phase0_gate.py`                                                                       |
| Phase 1  | [workflows.md](workflows.md), [nodes.md](nodes.md), [reliability-scorecard.md](reliability-scorecard.md)                                       | `tools/ci/check_scientist_phase1_gate.py`, `tests/tools/test_scientist_phase1_gate.py`, `tests/integration/scientist/test_workflow_reliability_scenarios.py` |
| Phase 2  | [workflows.md](workflows.md), [nodes.md](nodes.md), [reliability-scorecard.md](reliability-scorecard.md)                                       | `tools/ci/check_scientist_phase2_ratchet.py`, `tests/tools/test_scientist_phase2_ratchet.py`, `tests/performance/test_scientist_runtime_paths.py`            |
| Phase 3  | [governance-passes.md](governance-passes.md), [causal-validity.md](causal-validity.md), [agent-search-reasoning.md](agent-search-reasoning.md) | governance, causal-evaluation, eval-harness, and advanced-policy tests cited on each page                                                                    |
| Phase 4  | [causal-validity.md](causal-validity.md), [agent-search-reasoning.md](agent-search-reasoning.md)                                               | `frontier_runtime.py`, `tests/unit/scientist/search/test_frontier_runtime.py`, `tests/unit/scientist/search/test_benchmark_registry.py`                                       |

Historical planning material is reconciled in
[scientist-capability-inventory.md](scientist-capability-inventory.md). It
includes `docs/plans/active/SCIENTIST_AUDIT_REMEDIATION_PLAN.md` plus the archived Scientist
roadmaps under `docs/archive/plans/`; those plans are evidence inputs, not the
published factual reference surface.

## Validation

```bash
uv run pytest tests/unit/scientist/workflows/test_workflow_specs.py tests/unit/scientist/workflows/test_workflow_selection.py -q
uv run pytest tests/unit/scientist/governance/test_pass_registry.py tests/unit/scientist/governance/test_reliability_scorecard.py -q
uv run pytest tests/unit/scientist/governance/test_ic_verification.py tests/unit/scientist/governance/test_ic_conformance.py tests/unit/scientist/governance/test_incentive_compatibility_pass.py -q
uv run pytest tests/unit/scientist/agent/test_reasoning.py tests/unit/scientist/agent/test_eval_harness.py tests/unit/scientist/search/strategies/test_advanced_policy.py -q
```

## API Reference

::: polisyos.scientist

::: polisyos.scientist.api

::: polisyos.scientist.engine.state
