# Scientist Best-in-Class Readiness

Related references: [Scientist](index.md), [Capability inventory](scientist-capability-inventory.md), [Wave 1 acceptance](best-in-class-wave1-acceptance.md), [Remediation status](remediation-status.md), [Frontier runtime](frontier-runtime.md).

Owner: `@scientist-owners`
Backup owner: `@platform-owners`
Source of truth: `docs/plans/active/SCIENTIST_BEST_IN_CLASS_PLAN.md`, `docs/reference/scientist/scientist-capability-inventory.md`, `docs/reference/scientist/best-in-class-wave1-acceptance.md`, `docs/reference/scientist/best-in-class-wave2-acceptance.md`, `docs/reference/scientist/best-in-class-maturity.md`, `docs/reference/scientist/wave2-migration-notes.md`, `docs/plans/active/SCIENTIST_AUDIT_REMEDIATION_PLAN.md`, `src/polisyos/scientist/**`, `tests/unit/scientist/**`, `docs/reference/scientist/**`, `tools/ci/check_scientist_best_in_class_phase1_0.py`, `tools/ci/check_scientist_best_in_class_phase1_1.py`, `tools/ci/check_scientist_best_in_class_phase1_2.py`, `tools/ci/check_scientist_best_in_class_phase1_3.py`, `tools/ci/check_scientist_best_in_class_phase1_4.py`, `tools/ci/check_scientist_benchmark_authority.py`, `tools/ci/check_scientist_best_in_class_phase1_6.py`, `tools/ci/check_scientist_best_in_class_wave1.py`, `tools/ci/check_scientist_best_in_class_phase2_1.py`, `tools/ci/check_scientist_best_in_class_phase2_2.py`, `tools/ci/check_scientist_best_in_class_phase2_3.py`, `tools/ci/check_scientist_best_in_class_phase2_4.py`, `tools/ci/check_scientist_best_in_class_phase2_5.py`, `tools/ci/check_scientist_best_in_class_phase2_6.py`, `tools/ci/check_scientist_best_in_class_phase2_7.py`, and `tools/ci/check_scientist_best_in_class_wave2.py`

This page is the canonical Phase 1.0 status reconciliation record for the
Scientist best-in-class plan. It does not introduce runtime behavior. It fixes
the map between current code, current tests, reference pages, archived roadmap
claims, and the active best-in-class phases.

## Status Vocabulary

| Status | Meaning |
| --- | --- |
| `closed` | The current intended surface has code, direct tests or gates, and reference docs. |
| `superseded` | The historical item was replaced by a newer contract or merged into another surface. |
| `still_gated` | Code or design exists, but default/public use remains blocked by explicit gates, missing evals, or a later best-in-class phase. |
| `research_first` | The next step is research, metrics, or benchmark design before implementation should be expanded. |
| `not_in_scope` | The item is outside the Scientist best-in-class plan boundary. |

## Current Capability Readiness

| Capability id | Readiness | Current source of truth | Evidence | Next best-in-class phase |
| --- | --- | --- | --- | --- |
| `workflow_runtime` | `closed` | `src/polisyos/scientist/workflows/**`, `src/polisyos/scientist/api.py` | [workflows.md](workflows.md), `tests/unit/scientist/workflows/**`, `tests/unit/scientist/workflows/test_workflow_selection.py` | Keep stable while Phase 1.1 and Phase 1.2 add sidecars. |
| `builtin_nodes` | `closed` | `src/polisyos/scientist/nodes/**`, `src/polisyos/scientist/orchestration/engine/protocol.py` | [nodes.md](nodes.md), `tests/unit/scientist/nodes/**`, node-specific regressions | Add claim/DAG projections without changing node contracts abruptly. |
| `governance_pipeline` | `closed` | `src/polisyos/scientist/governance/**` | [governance-passes.md](governance-passes.md), [governance-accountability.md](governance-accountability.md), governance tests | Phase 1.1 claim validation, Phase 1.6 human review packets. |
| `causal_validity` | `closed` | `src/polisyos/scientist/causal/validity.py`, causal builtin nodes | [causal-validity.md](causal-validity.md), [causal.md](causal.md), causal tests | Phase 1.1 claim projection and Phase 1.5 benchmark authority. |
| `policy_design` | `closed` | `src/polisyos/scientist/policy_design/**`, `workflows/policy_design.py` | [workflows.md](workflows.md), policy-design tests, output-bundle tests | Phase 1.1 claim spine, Phase 1.2 research DAG. |
| `policy_verified` | `closed` | `src/polisyos/scientist/validation/policy_verified/**`, `workflows/policy_verified.py` | [workflows.md](workflows.md), verified-policy tests | Phase 1.1 claim spine and Phase 1.3 evidence grounding. |
| `discovery_runtime` | `closed` | `src/polisyos/scientist/discovery/**`, `nodes/builtins/planning/run_discovery_blueprint_runtime.py` | discovery tests, [latent-discovery-producers.md](latent-discovery-producers.md) | Phase 2.7 if discovery needs adversarial challenge packs. |
| `search_funnel` | `closed` | `src/polisyos/scientist/search/funnel/**`, `src/polisyos/scientist/search/controller.py` | search funnel tests, [calibration-governance.md](calibration-governance.md) | Phase 1.5 benchmark authority, Phase 2.3 VOI scheduler. |
| `benchmark_frontier_runtime` | `closed` | `src/polisyos/scientist/orchestration/engine/frontier_runtime.py`, shim: `src/polisyos/scientist/frontier_runtime.py`, `src/polisyos/scientist/search/benchmark_registry.py`, `src/polisyos/scientist/evals/**` | [frontier-runtime.md](frontier-runtime.md), [benchmark-authority.md](benchmark-authority.md), [adversarial-challenge-factory.md](adversarial-challenge-factory.md), [phase4-acceptance.md](phase4-acceptance.md), `tests/unit/scientist/search/test_frontier_runtime.py`, `tests/unit/scientist/search/test_benchmark_registry.py`, `tests/unit/scientist/evals/**` | Benchmark authority is read-only/shadow; near-frontier checks can require fresh rotating challenge lineage. |
| `agent_tool_runtime` | `closed` | `src/polisyos/scientist/agent/**`, `src/polisyos/scientist/agent/tools/**`, `src/polisyos/scientist/agent/promotion.py` | [agent-search-reasoning.md](agent-search-reasoning.md), [agent-capability-promotion.md](agent-capability-promotion.md), agent/tool tests, `tools/ci/check_scientist_best_in_class_phase1_4.py` | Default enablement remains gated by typed offline eval and benchmark refs. |
| `deep_research_evidence` | `closed` | `src/polisyos/scholar/search/models.py`, `src/polisyos/scientist/evidence/**`, `src/polisyos/scientist/agent/tools/scholar_search_tools.py`, `src/polisyos/scientist/agent/knowledge_tools.py` | [deep-research-evidence.md](deep-research-evidence.md), `tests/unit/scientist/evidence/**`, `tests/unit/scientist/agent/test_knowledge_tools_web_evidence.py`, `tools/ci/check_scientist_best_in_class_phase1_3.py` | Keep production fail-closed rollout gated by flags; source quality remains heuristic. |
| `replay_provenance` | `closed` | `src/polisyos/scientist/evidence/provenance/**`, shim: `src/polisyos/scientist/provenance/**`, `src/polisyos/scientist/replay/**`, `src/polisyos/scientist/orchestration/engine/checkpoint.py`, `src/polisyos/scientist/methods/research_dag/**` | [proof-trace-composability.md](proof-trace-composability.md), [research-dag.md](research-dag.md), replay/provenance/checkpoint/research DAG tests | Phase 2.2 expands replay/diff after the Phase 1.2 sidecar. |
| `validation_fairness_calibration` | `closed` | `src/polisyos/scientist/validation/**`, calibration and governance surfaces | [calibration-governance.md](calibration-governance.md), validation tests | Phase 1.5 eval family registration and Phase 1.6 review packets. |
| `autotune_search` | `closed` | `src/polisyos/scientist/autotune/**`, `src/polisyos/scientist/search/strategies/**` | autotune/search strategy tests, [agent-search-reasoning.md](agent-search-reasoning.md), [reflexive-memory.md](reflexive-memory.md) | Phase 2.3 VOI scheduler closed; Phase 2.4 reflexive memory is warning-only/shadow. |
| `cross_graph_evidence` | `closed` | `src/polisyos/scientist/cross_graph/**` | cross-graph tests, [causal.md](causal.md) | Phase 1.1 claim projection and Phase 1.3 evidence links. |
| `llm_gateway` | `closed` | `src/polisyos/scientist/llm/**` | LLM/provider tests, [agent-search-reasoning.md](agent-search-reasoning.md) | Phase 1.4 tool/provider promotion report; context governance remains later work. |
| `human_oversight` | `closed` | `src/polisyos/scientist/governance/human_review/**`, governance report review links, decision packet review gate | [human-oversight.md](human-oversight.md), `tests/unit/scientist/governance/human_review/**`, `tests/unit/scientist/governance/test_human_review_pass.py` | Wave 1 closeout checks agreement with claims, benchmark authority and governance. |
| `claim_evidence_readiness_spine` | `closed` | `src/polisyos/scientist/evidence/claims/**`, shim: `src/polisyos/scientist/claims/**`, `DecisionReadinessContract`, `claims_ref` integrations | [claims.md](claims.md), [frontier-runtime.md](frontier-runtime.md), [remediation-status.md](remediation-status.md), `tests/unit/scientist/evidence/claims/**` | Keep sidecar additive; Wave 2 Claim Ledger expands lifecycle history. |
| `research_dag` | `closed` | `src/polisyos/scientist/methods/research_dag/**`, shim: `src/polisyos/scientist/research_dag/**`, workflow/provenance/tool-loop integrations, `research_dag_ref` sidecar | [research-dag.md](research-dag.md), `tests/unit/scientist/methods/research_dag/**`, `tools/ci/check_scientist_best_in_class_phase1_2.py` | Keep sidecar shadow-capable; Phase 2.2 deepens replay/comparison. |
| `wave1_acceptance` | `closed` | `docs/reference/scientist/best-in-class-wave1-acceptance.md`, `tools/ci/check_scientist_best_in_class_wave1.py` | [best-in-class-wave1-acceptance.md](best-in-class-wave1-acceptance.md), `tests/repo_quality/tools/test_scientist_best_in_class_wave1.py` | Wave 2 begins from this closure gate. |
| `voi_reflexive_memory_challenge_factory` | `closed` | `src/polisyos/scientist/search/voi_models.py`, `search/voi_scheduler.py`, `search/voi_calibration.py`, `human_review/voi_escalation.py`, source-verification VOI in `evidence/claim_support.py`, `src/polisyos/scientist/memory/**`, Research DAG memory projection, `src/polisyos/scientist/evals/challenge_factory.py`, `evals/sentinels.py`, `evals/red_team.py`, `evals/rotation.py` | [voi-scheduler.md](voi-scheduler.md), [reflexive-memory.md](reflexive-memory.md), [adversarial-challenge-factory.md](adversarial-challenge-factory.md), VOI/search/evidence/human-review/memory/evals tests, `tools/ci/check_scientist_best_in_class_phase2_3.py`, `tools/ci/check_scientist_best_in_class_phase2_4.py`, `tools/ci/check_scientist_best_in_class_phase2_5.py` | VOI, reflexive memory and challenge generation are shadow/read-only; near-frontier rotating evidence is opt-in through benchmark authority. |
| `continuous_governance_reissue` | `closed` | `src/polisyos/scientist/governance/continuous/**`, Research DAG invalidation bridge, Claim Ledger lifecycle stale/invalidated events, governance/decision-packet validity links | [continuous-governance.md](continuous-governance.md), `tests/unit/scientist/governance/continuous/**`, `tools/ci/check_scientist_best_in_class_phase2_6.py` | Validity reports are additive/shadow; reissue and withdrawal require explicit governance/human-review action. |
| `decision_grade_compiler` | `closed` | `src/polisyos/scientist/publisher.py`, `src/polisyos/scientist/orchestration/orchestrator/decision_card.py`, `src/polisyos/scientist/evidence/claims/export.py` | [decision-grade-compiler.md](decision-grade-compiler.md), `tests/unit/scientist/orchestration/orchestrator/test_decision_grade_compiler.py`, `tools/ci/check_scientist_best_in_class_phase2_7.py` | Public/reviewer/expert/machine tiers derive from the same Claim Ledger and Research DAG; compiler rollout stays additive/shadow. |
| `wave2_acceptance` | `closed` | `docs/reference/scientist/best-in-class-wave2-acceptance.md`, `docs/reference/scientist/best-in-class-maturity.md`, `docs/reference/scientist/wave2-migration-notes.md`, `tools/ci/check_scientist_best_in_class_wave2.py` | [best-in-class-wave2-acceptance.md](best-in-class-wave2-acceptance.md), [best-in-class-maturity.md](best-in-class-maturity.md), [wave2-migration-notes.md](wave2-migration-notes.md), `tests/repo_quality/tools/test_scientist_best_in_class_wave2.py` | Wave 2 remains read-only/shadow after closeout; production promotion is still per-feature and rollbackable by flag. |
| `active_plan_governance` | `closed` | `docs/plans/active/SCIENTIST_BEST_IN_CLASS_PLAN.md` and this page | `tools/ci/check_scientist_best_in_class_phase1_0.py` | Keep this page synchronized whenever Phase 1+ surfaces land. |

## Canonical Active Plan Index

The active Scientist best-in-class plan is
`docs/plans/active/SCIENTIST_BEST_IN_CLASS_PLAN.md`. Its canonical phase index
is:

| Phase | Current status | Acceptance surface |
| --- | --- | --- |
| Phase 1.0 - Status reconciliation | `closed` | This page, [scientist-capability-inventory.md](scientist-capability-inventory.md), and `tools/ci/check_scientist_best_in_class_phase1_0.py`. |
| Phase 1.1 - Claim/Evidence/Readiness spine | `closed` | [claims.md](claims.md), `src/polisyos/scientist/evidence/claims/**`, shim: `src/polisyos/scientist/claims/**`, `claims_ref` packet/bundle/governance/causal integrations, and `tools/ci/check_scientist_best_in_class_phase1_1.py`. |
| Phase 1.2 - Research DAG | `closed` | [research-dag.md](research-dag.md), `src/polisyos/scientist/methods/research_dag/**`, shim: `src/polisyos/scientist/research_dag/**`, selected-workflow `research_dag_ref` sidecar, replay/diff tests, and `tools/ci/check_scientist_best_in_class_phase1_2.py`. |
| Phase 1.3 - Deep research evidence | `closed` | [deep-research-evidence.md](deep-research-evidence.md), additive `WebEvidenceBundle` safety/quality extensions, `src/polisyos/scientist/evidence/**`, safe Scholar tool wrappers, evidence-to-DAG projection, and `tools/ci/check_scientist_best_in_class_phase1_3.py`. |
| Phase 1.4 - Agent/tool promotion gates | `closed` | [agent-capability-promotion.md](agent-capability-promotion.md), `src/polisyos/scientist/agent/runtime_capabilities.py`, `src/polisyos/scientist/agent/promotion.py`, `src/polisyos/scientist/agent/tool_contracts.py`, `src/polisyos/scientist/agent/supervisor_eval.py`, frontier projection, and `tools/ci/check_scientist_best_in_class_phase1_4.py`. |
| Phase 1.5 - Benchmark authority | `closed` | [benchmark-authority.md](benchmark-authority.md), `src/polisyos/scientist/evals/**`, `BenchmarkAuthority` over `BenchmarkRegistry`, leakage/staleness/frozen-web/policy-case tests, and `tools/ci/check_scientist_benchmark_authority.py`. |
| Phase 1.6 - Human oversight packets | `closed` | [human-oversight.md](human-oversight.md), `src/polisyos/scientist/governance/human_review/**`, CAS-persisted review packets/decisions/queue, governance report links, decision-packet human-review validation, `tests/unit/scientist/governance/human_review/**`, and `tools/ci/check_scientist_best_in_class_phase1_6.py`. |
| Phase 1.7 - Wave 1 closeout | `closed` | [best-in-class-wave1-acceptance.md](best-in-class-wave1-acceptance.md), `tools/ci/check_scientist_best_in_class_wave1.py`, and `tests/repo_quality/tools/test_scientist_best_in_class_wave1.py`. |
| Phase 2.0 - Scientist OS foundation | `closed` | [wave2-runtime-contracts.md](wave2-runtime-contracts.md), accepted ADRs 0129-0132, `tests/unit/scientist/orchestrator_v2/test_compatibility_contracts.py`, and `tools/ci/check_scientist_best_in_class_phase2_0.py`. |
| Phase 2.1 - Claim Ledger | `closed` | [claim-ledger.md](claim-ledger.md), `src/polisyos/scientist/evidence/claims/lifecycle.py`, `src/polisyos/scientist/evidence/claims/audit.py`, `src/polisyos/scientist/evidence/claims/diff.py`, `src/polisyos/scientist/evidence/claims/export.py`, packet/bundle summaries, and `tools/ci/check_scientist_best_in_class_phase2_1.py`. |
| Phase 2.2 - Research DAG replay and comparison | `closed` | [research-dag-replay.md](research-dag-replay.md), `src/polisyos/scientist/methods/research_dag/replay.py`, `comparison.py`, `invalidation.py`, extended `diff.py`, Claim Ledger `marked_stale` lifecycle integration, and `tools/ci/check_scientist_best_in_class_phase2_2.py`. |
| Phase 2.3 - VOI scheduler | `closed` | [voi-scheduler.md](voi-scheduler.md), `src/polisyos/scientist/search/voi_models.py`, `search/voi_scheduler.py`, `search/voi_calibration.py`, `human_review/voi_escalation.py`, source-verification VOI in `evidence/claim_support.py`, CAS-persisted `VOIRunReport`, `voi_run_report_ref` sidecars in major policy-runtime runs, and `tools/ci/check_scientist_best_in_class_phase2_3.py`. |
| Phase 2.4 - Reflexive memory and failure intelligence | `closed` | [reflexive-memory.md](reflexive-memory.md), `src/polisyos/scientist/memory/**`, Research DAG memory projection, hidden-eval/canary contamination guards, applicability/retrieval/revocation tests, and `tools/ci/check_scientist_best_in_class_phase2_4.py`. |
| Phase 2.5 - Adversarial challenge factory | `closed` | [adversarial-challenge-factory.md](adversarial-challenge-factory.md), `src/polisyos/scientist/evals/challenge_factory.py`, `sentinels.py`, `red_team.py`, `rotation.py`, benchmark authority lineage/fresh-rotation checks, review-before-hidden tests, and `tools/ci/check_scientist_best_in_class_phase2_5.py`. |
| Phase 2.6 - Continuous governance and reissue loop | `closed` | [continuous-governance.md](continuous-governance.md), `src/polisyos/scientist/governance/continuous/**`, source invalidation to Claim Ledger bridge, governance/packet validity links, and `tools/ci/check_scientist_best_in_class_phase2_6.py`. |
| Phase 2.7 - Decision-grade research compiler | `closed` | [decision-grade-compiler.md](decision-grade-compiler.md), `DecisionGradeExport`, public/reviewer/expert/machine compiler tiers, machine `frontend_trust_view`, decision-card bridge, and `tools/ci/check_scientist_best_in_class_phase2_7.py`. |
| Phase 2.8 - System closeout | `closed` | [best-in-class-wave2-acceptance.md](best-in-class-wave2-acceptance.md), [best-in-class-maturity.md](best-in-class-maturity.md), [wave2-migration-notes.md](wave2-migration-notes.md), `tools/ci/check_scientist_best_in_class_wave2.py`, and `tests/repo_quality/tools/test_scientist_best_in_class_wave2.py`. |

## Reconciliation Rules

- Historical Scientist plans are evidence inputs, not active plans.
- A historical item can be `closed` only when the current repo has a reference
  page or direct test/gate evidence for the accepted scope.
- A historical item can be `still_gated` when code exists but default use is
  blocked by explicit rollout, benchmark, or human-review gates.
- A historical item can be `research_first` when Phase 1.0 cannot honestly name
  a stable implementation contract yet.
- Any new Scientist reference page must be added to
  [scientist-capability-inventory.md](scientist-capability-inventory.md).

## Phase 1.0 Acceptance

Phase 1.0 is accepted when:

- this page lists active Scientist capability families and their current
  readiness;
- [scientist-capability-inventory.md](scientist-capability-inventory.md)
  inventories `src/polisyos/scientist/**`, `tests/unit/scientist/**`, and
  `docs/reference/scientist/**`;
- every historical Scientist roadmap item from the Scientist historical plans is
  mapped to `closed`, `superseded`, `still_gated`, `research_first`, or
  `not_in_scope`;
- the CI gate below passes without requiring runtime implementation changes.

## Validation

```bash
uv run python tools/ci/check_scientist_best_in_class_phase1_0.py --repo-root . --output-format json --require-passing
uv run python tools/ci/check_scientist_best_in_class_phase1_1.py --repo-root . --output-format json --require-passing
uv run python tools/ci/check_scientist_best_in_class_phase1_2.py --repo-root . --output-format json --require-passing
uv run python tools/ci/check_scientist_best_in_class_wave1.py --repo-root . --output-format json --require-passing
uv run python tools/ci/check_scientist_best_in_class_phase2_3.py --repo-root . --output-format json --require-passing
uv run python tools/ci/check_scientist_best_in_class_phase2_5.py --repo-root . --output-format json --require-passing
uv run python tools/ci/check_scientist_best_in_class_phase2_6.py --repo-root . --output-format json --require-passing
uv run python tools/ci/check_scientist_best_in_class_phase2_7.py --repo-root . --output-format json --require-passing
uv run python tools/ci/check_scientist_best_in_class_wave2.py --repo-root . --output-format json --require-passing
uv run pytest tests/repo_quality/tools/test_scientist_best_in_class_phase1_0.py -q
uv run pytest tests/repo_quality/tools/test_scientist_best_in_class_phase1_1.py -q
uv run pytest tests/repo_quality/tools/test_scientist_best_in_class_phase1_2.py -q
uv run pytest tests/repo_quality/tools/test_scientist_best_in_class_wave1.py -q
```
