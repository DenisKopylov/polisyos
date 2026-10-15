# Scientist Capability Inventory

Related references: [Scientist](index.md), [Best-in-class readiness](best-in-class-readiness.md), [Wave 2 runtime contracts](wave2-runtime-contracts.md), [Remediation status](remediation-status.md), [Workflows](workflows.md), [Nodes](nodes.md).

Owner: `@scientist-owners`
Backup owner: `@platform-owners`
Source of truth: `src/polisyos/scientist/**`, `tests/unit/scientist/**`, `docs/reference/scientist/**`, `docs/plans/active/SCIENTIST_AUDIT_REMEDIATION_PLAN.md`, `docs/plans/archive/SCIENTIST_SOTA_ROADMAP.md`, `docs/plans/archive/SCIENTIST_AGENT_SOTA_ROADMAP.md`, `docs/plans/archive/SCIENTIST_SOTA_AUTORESEARCH_BLUEPRINT.md`, `tools/ci/check_scientist_best_in_class_phase1_0.py`, `tools/ci/check_scientist_best_in_class_phase1_1.py`, `tools/ci/check_scientist_best_in_class_phase1_2.py`, `tools/ci/check_scientist_best_in_class_phase1_3.py`, `tools/ci/check_scientist_best_in_class_phase1_4.py`, `tools/ci/check_scientist_benchmark_authority.py`, `tools/ci/check_scientist_best_in_class_phase1_6.py`, `tools/ci/check_scientist_best_in_class_wave1.py`, `tools/ci/check_scientist_best_in_class_phase2_0.py`, `tools/ci/check_scientist_best_in_class_phase2_1.py`, `tools/ci/check_scientist_best_in_class_phase2_2.py`, `tools/ci/check_scientist_best_in_class_phase2_3.py`, `tools/ci/check_scientist_best_in_class_phase2_4.py`, `tools/ci/check_scientist_best_in_class_phase2_5.py`, `tools/ci/check_scientist_best_in_class_phase2_6.py`, `tools/ci/check_scientist_best_in_class_phase2_7.py`, and `tools/ci/check_scientist_best_in_class_wave2.py`
Source pin: `codex/docs-refresh-e02-20261014` at `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`.
Evidence level: package layout, selected import-test assertions, current workflow map, and listed reference paths were inspected at this pin; tests and gates were not executed.

This inventory is the Phase 1.0 reconciliation layer for the Scientist
best-in-class plan. It records what exists now, which tests and references own
each surface, and how the historical Scientist plans map to the current source
of truth. It intentionally does not add new runtime implementation.

## Source Inventory

The layout declaration is `architecture/packages/scientist.toml`. At this source
pin it marks the package contract `draft` and `gate_mode = "report_only"`; its
root list is a declaration, not evidence that all listed capabilities are
wired or that the layout gate enforces it.

| Declared canonical root | Current semantic home |
| --- | --- |
| `src/polisyos/scientist/_adapters/` | Private adapters from Scientist vocabulary to shared interfaces. |
| `src/polisyos/scientist/_internal/` | Private shared helpers; not a compatibility API. |
| `src/polisyos/scientist/adapters/` | Foundry and Fabric adapters. |
| `src/polisyos/scientist/agent/` | Agent runtime, tool contracts, reasoning and promotion reports. |
| `src/polisyos/scientist/artifacts/` | Decision artifact compilation. |
| `src/polisyos/scientist/compute/` | Scientist compute helpers. |
| `src/polisyos/scientist/cross_graph/` | Cross-graph collection, conflicts, budgets and transfer context. |
| `src/polisyos/scientist/evals/` | Benchmark authority, challenge and rotation contracts. |
| `src/polisyos/scientist/evidence/` | Evidence, claims, provenance, source quality and claim support. |
| `src/polisyos/scientist/extensions/` | Extension registration boundary. |
| `src/polisyos/scientist/feedback/` | Feedback and replay/evidence support. |
| `src/polisyos/scientist/governance/` | Governance passes, accountability, continuous governance and `human_review/`. |
| `src/polisyos/scientist/methods/` | `autotune/`, `backtesting/`, `causal/`, `doe/`, `discovery/`, `search/`, and `research_dag/` implementations. |
| `src/polisyos/scientist/nodes/` | Builtin node registry and implementations. |
| `src/polisyos/scientist/orchestration/` | `engine/`, `workflows/`, `orchestrator/`, `memory/`, and `llm/`. |
| `src/polisyos/scientist/policy_design/` | Policy candidate, search, translation and output helpers. |
| `src/polisyos/scientist/publishing/` | Decision-grade publishing implementation and facade. |
| `src/polisyos/scientist/replay/` | Replay and comparison support. |
| `src/polisyos/scientist/validation/` | Validation, `policy_verified/`, and `verification/`. |

The package contract also allows the root facade files described by
`layout.root_facade_policy`, including `__init__.py` and `api.py`. The canonical
publisher is `src/polisyos/scientist/publishing/publisher.py`; the focused
publisher test checks facade/implementation function identity. The former
`src/polisyos/scientist/remediation_status.py` implementation path is retired;
the inspected implementation is
`src/polisyos/scientist/governance/remediation_status.py`.

### Compatibility declaration discrepancy

The source declaration and selected import assertions disagree:

| Name | Package declaration | Inspected import-test assertions | Documentation treatment |
| --- | --- | --- | --- |
| `backtesting`, `discovery` | Listed in `layout.compatibility_shim_roots`; also named by `phase2_2_active_root_rule`. | `tests/unit/scientist/methods/test_import_shims.py` asserts `find_spec(...) is None` for both first-level imports. | Report as a source-declaration mismatch; do not call either an active shim. |
| `claims`, `search` | Omitted from `canonical_first_level_roots` and `compatibility_shim_roots`, but named as compatibility roots in `phase2_2_active_root_rule`. | The selected test asserts both first-level imports are absent and neither is registered in `architecture/shims.toml`. | Report as a source-declaration mismatch; their implementations live below `evidence/` and `methods/`. |
| `engine`, `workflows`, `provenance`, `research_dag`, `human_review` | Not canonical first-level roots; package prose says these legacy roots were retired. | The selected import test includes their absence cases. | Keep the path map at `orchestration/`, `evidence/`, and `governance/` semantic homes. |

`tests/unit/scientist/methods/test_import_shims.py` also checks a positive
publisher facade identity. Its assertions are selected removal/identity checks,
not an all-root import-shim smoke test. The source declaration has
`gate_mode = "report_only"`; this inventory does not claim the declaration and
runtime imports have been reconciled.

## Test Inventory

The test tree retains some historical naming at its test-directory level. A
test path such as `tests/unit/scientist/search/` or
`tests/unit/scientist/discovery/` is not a source-package root and does not
establish an import shim or end-to-end workflow integration.

| Direct unit-test directory | Observed coverage role |
| --- | --- |
| `tests/unit/scientist/adapters/` | Adapter contracts. |
| `tests/unit/scientist/agent/` | Agent, tool, reasoning and promotion behavior. |
| `tests/unit/scientist/artifacts/` | Decision artifact compilation. |
| `tests/unit/scientist/compute/` | Compute helpers. |
| `tests/unit/scientist/cross_graph/` | Cross-graph evidence and conflict behavior. |
| `tests/unit/scientist/discovery/` | Discovery-focused tests; the source implementation lives under `src/polisyos/scientist/methods/discovery/`. |
| `tests/unit/scientist/evals/` | Benchmark authority and challenge lifecycle. |
| `tests/unit/scientist/evidence/` | Evidence and Claim Ledger behavior. |
| `tests/unit/scientist/facade/` | Public facade and remediation-report tests. |
| `tests/unit/scientist/feedback/` | Feedback behavior. |
| `tests/unit/scientist/governance/` | Governance passes, accountability, human review and continuous governance. |
| `tests/unit/scientist/methods/` | Canonical method tests and the selected import-contract assertions. |
| `tests/unit/scientist/mirror_contracts/` | Repository mirror contracts. |
| `tests/unit/scientist/nodes/` | Builtin nodes and workflow consumers. |
| `tests/unit/scientist/orchestration/` | Engine, workflows, memory and orchestrator. |
| `tests/unit/scientist/orchestrator_v2/` | Wave 2 compatibility contracts. |
| `tests/unit/scientist/policy_design/` | Policy workflow, guard and output behavior. |
| `tests/unit/scientist/replay/` | Replay behavior. |
| `tests/unit/scientist/search/` | Search-focused tests; the source implementation lives under `src/polisyos/scientist/methods/search/`. |
| `tests/unit/scientist/validation/` | Validation and grounding reports. |

The source test contract in `architecture/packages/scientist.toml` marks
integration and property coverage required, with
`tests/integration/scientist/` as an integration root and
`tests/property/scientist/` as a property root. The inspected direct integration
tree includes `governance/`, `methods/`, `orchestration/`, and root-level
checkpoint, simulation-route, workflow-reliability, workflow-tracing, and
transportability tests. These facts describe test sources; this documentation
update did not execute them.

To reproduce the direct unit-test directory listing:

```bash
cd policy-engine
python3 - <<'PY'
from pathlib import Path

root = Path("tests/unit/scientist")
for path in sorted(root.iterdir()):
    if path.is_dir():
        print(path.as_posix())
PY
```

## Reference Inventory

The linked entries below are the full Markdown-page set observed under
`docs/reference/scientist/`. Reproduce that path set with a recursive walk over
the Markdown-file denominator:

```bash
cd policy-engine
python3 - <<'PY'
from pathlib import Path

root = Path("docs/reference/scientist")
for path in sorted(item for item in root.rglob("*.md") if item.is_file()):
    print(path.relative_to(root).as_posix())
PY
```

| Reference page | Role |
| --- | --- |
| [adversarial-challenge-factory.md](adversarial-challenge-factory.md) | Candidate challenge generation and review-before-hidden contract. |
| [agent-capability-promotion.md](agent-capability-promotion.md) | Typed, read-only agent capability promotion. |
| [agent-search-reasoning.md](agent-search-reasoning.md) | Reasoning and advanced-search rollout gates. |
| [benchmark-authority.md](benchmark-authority.md) | Benchmark authority, leakage, staleness and promotion evidence. |
| [best-in-class-maturity.md](best-in-class-maturity.md) | Wave 2 maturity vocabulary and per-feature promotion scope. |
| [best-in-class-readiness.md](best-in-class-readiness.md) | Plan/gate-scope readiness reconciliation. |
| [best-in-class-wave1-acceptance.md](best-in-class-wave1-acceptance.md) | Historical Wave 1 acceptance receipt. |
| [best-in-class-wave2-acceptance.md](best-in-class-wave2-acceptance.md) | Historical Wave 2 acceptance receipt. |
| [calibration-governance.md](calibration-governance.md) | Calibration, fairness and governance validation. |
| [causal-confidence-issue-preservation.md](causal-confidence-issue-preservation.md) | Bounded causal-confidence issue preservation repair. |
| [causal-graph-intake.md](causal-graph-intake.md) | Current graph-content admission and typed projection boundaries. |
| [causal-selected-consumers.md](causal-selected-consumers.md) | Selected causal consumer/input/output reconciliation. |
| [causal-validity-acceptance.md](causal-validity-acceptance.md) | Historical WS-3A acceptance receipt. |
| [causal-validity.md](causal-validity.md) | Causal-validity diagnostics and artifact surface. |
| [causal.md](causal.md) | Causal runner and bounded execution contracts. |
| [citation-faithfulness.md](citation-faithfulness.md) | Citation-fidelity assessment and runtime-NL integration scope. |
| [claim-ledger.md](claim-ledger.md) | Claim lifecycle sidecar, export and currentness boundary. |
| [claim-support-semantics.md](claim-support-semantics.md) | Claim-support predicates and runtime-NL integration scope. |
| [claims.md](claims.md) | Claim/readiness spine, default-off enforcement and owner currentness. |
| [continuous-governance.md](continuous-governance.md) | Optional validity sidecars and explicit reissue/withdrawal semantics. |
| [current-workflows.md](current-workflows.md) | Current routing, state machines, evidence handshakes and integration gaps. |
| [decision-artifact-quality.md](decision-artifact-quality.md) | Decision artifact compiler/quality contract and runtime-NL scope. |
| [decision-grade-compiler.md](decision-grade-compiler.md) | Audience projections, omissions and optional compiler rollout. |
| [deep-research-evidence.md](deep-research-evidence.md) | Deep-research evidence contract and proposed schema boundary. |
| [frontier-runtime.md](frontier-runtime.md) | Offline-gated frontier runtime contract. |
| [governance-accountability.md](governance-accountability.md) | Accountability artifacts and consumer gaps. |
| [governance-passes.md](governance-passes.md) | Governance registry, status semantics and selected consumers. |
| [human-oversight.md](human-oversight.md) | Human-review packet, decision and selected release-validation rules. |
| [index.md](index.md) | Scientist reference entrypoint and package layout. |
| [latent-discovery-producers.md](latent-discovery-producers.md) | Narrow latent producer claims and explicit trust limits. |
| [nodes.md](nodes.md) | Builtin node protocol and registry. |
| [phase0-acceptance.md](phase0-acceptance.md) | Historical Phase 0 acceptance receipt. |
| [phase1-acceptance.md](phase1-acceptance.md) | Historical Phase 1 acceptance receipt. |
| [phase3-acceptance.md](phase3-acceptance.md) | Historical Phase 3 acceptance receipt. |
| [phase4-acceptance.md](phase4-acceptance.md) | Historical Phase 4 acceptance receipt. |
| [proof-trace-composability.md](proof-trace-composability.md) | Proof-trace and provenance composition constraints. |
| [reflexive-memory.md](reflexive-memory.md) | Warning-only memory retrieval and contamination boundaries. |
| [reliability-scorecard.md](reliability-scorecard.md) | Reliability scorecard and gate artifact definitions. |
| [remediation-status.md](remediation-status.md) | Historical remediation workstream/gate status with current-scope qualification. |
| [research-dag-replay.md](research-dag-replay.md) | Replay plans, comparison, invalidation and bounded exports. |
| [research-dag.md](research-dag.md) | Optional Research DAG sidecar and replay contract. |
| [scientist-capability-inventory.md](scientist-capability-inventory.md) | This source/test/reference and historical-plan reconciliation. |
| [source-quality-calibration.md](source-quality-calibration.md) | Advisory source quality signals and invalidation mappings. |
| [structural-causal-queries.md](structural-causal-queries.md) | Structural query method handoff and result-custody limits. |
| [system-pipeline-architecture.md](system-pipeline-architecture.md) | Dated architecture snapshot; current workflow status is in `current-workflows.md`. |
| [voi-scheduler.md](voi-scheduler.md) | VOI decision/report contracts and explicit non-waivable gates. |
| [wave2-migration-notes.md](wave2-migration-notes.md) | Wave 2 compatibility and rollback notes. |
| [wave2-runtime-contracts.md](wave2-runtime-contracts.md) | Wave 2 artifact, boundary and feature-flag contracts. |
| [workflows.md](workflows.md) | Workflow routing and builtin DAG specifications. |

## Current Workflow And Node Surface

The workflow selectors and builtin specs are mapped in
[workflows.md](workflows.md); the observed lifecycle consequences, typed
handoffs and incomplete capabilities are in [current-workflows.md](current-workflows.md).
The node registry in `src/polisyos/scientist/nodes/__init__.py` and its
implementations describe available components, not end-to-end capability
readiness. The current path includes `producer_missing` for the request/options
to Trinity bridge, `implemented_but_not_orchestrated` plus `surface_missing`
for the policy-grounding matrix in the builtin Scientist DAG, and
`not_established` current-head authority with an `absent/unallocated`
production Claim-owner appointment. These are bounded observations at the
source pin, not claims that every deployment has the same configuration.

## Historical Roadmap Reconciliation

The rows below preserve historical plan and gate statuses at their accepted
scope. `closed` in these rows is not a current end-to-end system status; use
[Current Scientist Workflows and Evidence Handoffs](current-workflows.md) for
the source-pinned current gaps and their capability labels. Historical receipts
and archived plans are retained as recorded rather than rewritten as new test
results.

Some implementation identifiers in the historical rows below (for example,
`engine/...`) retain the plan's former path vocabulary. They are not current
package paths; use the Source Inventory above for canonical locations.

Allowed statuses are `closed`, `superseded`, `still_gated`, `research_first`,
and `not_in_scope`.

### Audit Remediation Plan

Source: `docs/plans/active/SCIENTIST_AUDIT_REMEDIATION_PLAN.md`.

The audit remediation plan is not archived, but Phase 1.0 treats it as
historical closure input because its workstreams are already represented by
`src/polisyos/scientist/governance/remediation_status.py`, [remediation-status.md](remediation-status.md),
and the existing Scientist phase gates.

| Historical item | Status | Plan evidence reference or gate | Reconciliation note |
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

| Historical item | Status | Plan evidence reference or gate | Reconciliation note |
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
| `SCIENTIST_SOTA_ROADMAP:WS9.4` | `closed` | property tests under `tests/unit/scientist/orchestration/engine/**` and evidence source tests | Property-based checks are represented on accepted hot paths. |
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

| Historical item | Status | Plan evidence reference or gate | Reconciliation note |
| --- | --- | --- | --- |
| `SCIENTIST_AGENT_SOTA_ROADMAP:PHASE0` | `closed` | Phase 0/1 gates, LLM/budget tests | Correctness and budget bugs are covered by existing remediation gates. |
| `SCIENTIST_AGENT_SOTA_ROADMAP:PHASE1` | `closed` | [deep-research-evidence.md](deep-research-evidence.md), `src/polisyos/scientist/evidence/**`, `tests/unit/scientist/evidence/**`, `tools/ci/check_scientist_best_in_class_phase1_3.py` | First-party deep research evidence hardening is now Phase 1.3; production fail-closed rollout remains feature-flagged. |
| `SCIENTIST_AGENT_SOTA_ROADMAP:PHASE2` | `closed` | `agent/supervisor.py`, [agent-search-reasoning.md](agent-search-reasoning.md), [agent-capability-promotion.md](agent-capability-promotion.md), `tools/ci/check_scientist_best_in_class_phase1_4.py` | Supervisor pieces now feed the unified Phase 1.4 agent promotion surface; default enablement still requires typed offline and benchmark evidence. |
| `SCIENTIST_AGENT_SOTA_ROADMAP:PHASE3` | `research_first` | reflexion and memory tests | Reflexive evaluator-optimizer memory needs Wave 2 contamination and measurement rules. |
| `SCIENTIST_AGENT_SOTA_ROADMAP:PHASE4` | `still_gated` | `llm/profiles/**`, context references | Provider/context optimization exists in pieces but is not yet governed as a Context OS. |

### Archived Autoresearch Blueprint

Source: `docs/plans/archive/SCIENTIST_SOTA_AUTORESEARCH_BLUEPRINT.md`.

| Historical item | Status | Plan evidence reference or gate | Reconciliation note |
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
