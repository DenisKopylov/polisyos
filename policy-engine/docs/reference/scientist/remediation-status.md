# Scientist Remediation Status

Related reference: [Scientist](index.md).

Owner: `@scientist-owners`
Source of truth: `src/polisyos/scientist/remediation_status.py`, `tests/unit/scientist/facade/test_remediation_status.py`, and the linked Scientist acceptance pages

This page is the human-readable view of the machine source of truth in
`polisyos.scientist.remediation_status`. The closure posture is strict:
workstreams are `done` only when code, direct regressions, docs, observable
evidence, and CI barriers all agree.

## Policy

- A workstream is not considered done because some code landed.
- Acceptance requires repo-tracked evidence and an explicit CI barrier.
- The machine-readable source of truth lives in `polisyos.scientist.remediation_status`.
- `scientist-phase0-gate` and `scientist-phase1-gate` are the acceptance barriers for the reopened early phases.

## Current Closure Report

| Workstream | Status | Closure basis                                                                                                                                                                                                                            |
| ---------- | ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `WS-0A`    | `done` | Async, locking, and lifecycle containment is closed through direct retry/worker-pool/lock regressions and the `scientist-phase0-gate` acceptance barrier.                                                                                |
| `WS-0B`    | `done` | Gateway idempotency, budget reconciliation, masking fail-closed behavior, Foundry env hardening, and default-path statistical hotfixes are closed through the dedicated Phase 0 gate.                                                    |
| `WS-1A`    | `done` | Critical governance, executor, agent, cross-graph, autotune, and funnel error-semantics slices now emit typed failures or structured degraded envelopes, and the Phase 1 gate ratchets the accepted broad-handler slice.                 |
| `WS-1B`    | `done` | Branch-local copy-on-write mutation, staged fan-out merge semantics, checkpoint reconciliation, distributed resume, workflow entrypoint isolation, and translation/autotune branch-state contracts are regression-covered and ratcheted. |
| `WS-1C`    | `done` | Exporters, cross-runner trace correlation, DLQ replay, checkpoint GC retention, and monitoring hooks ship with direct operational evidence plus CI scorecard artifacts.                                                                  |
| `WS-1D`    | `done` | Reliability scenarios, benchmark proofs, benchmark artifacts, and the machine-readable scorecard are wired into CI.                                                                                                                      |
| `WS-2A`    | `done` | Hot-path state branching stays copy-on-write across nested payloads, prompt-cache entries are stable snapshots, and runtime-path benchmarks cover the closure budget.                                                                    |
| `WS-2B`    | `done` | Targeted helper seams are extracted and a CI ratchet blocks new `Any`, unsafe `cast()`, and raw `dict[...]` growth on the Phase 2 slice.                                                                                                 |
| `WS-3A`    | `done` | Default-path causal-validity artifacts now ship shared confidence and sensitivity sections plus explicit capability statuses for frontier methods.                                                                                       |
| `WS-3B`    | `done` | Calibration validation emits a unified accountability artifact with fairness, calibration, threshold, tail-risk, model-card, datasheet, and escalation evidence.                                                                         |
| `WS-3C`    | `done` | Advanced reasoning and search policies remain explicitly offline-gated until comparative reports and rollout statuses approve them.                                                                                                      |
| `WS-4A`    | `done` | Incremental checkpointing, rollback compensation hooks, shared-ledger provenance, and multi-runner replay/resume all agree on one recovery contract.                                                                                     |
| `WS-4B`    | `done` | Frontier rollout posture and benchmark/eval registry contracts remain machine-readable and non-default by design.                                                                                                                        |

## Phase Rollup

| Phase     | Status | Gate meaning                                                                                                                                     |
| --------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `Phase 0` | `done` | Containment fixes, direct regressions, acceptance ledger, and CI barrier now agree on one accepted closure contract.                             |
| `Phase 1` | `done` | Error semantics, deterministic mutation, operational evidence, and benchmark proof are enforced together by the dedicated Phase 1 gate.          |
| `Phase 2` | `done` | Performance and maintainability criteria have code, regression tests, benchmark coverage, modular decomposition evidence, and a CI debt ratchet. |
| `Phase 3` | `done` | Default-path scientific, governance, and reasoning claims ship first-class artifacts, comparative eval evidence, and explicit rollout statuses.  |
| `Phase 4` | `done` | Distributed replay/recovery safety and frontier offline-gated rollout contracts are backed by direct code and regression evidence.               |

## D1 Docs Impact Table

| Source plan phase | Docs impact                                                                                                                                                                                                                                                     | Validation command or gate                                                                                                                                                                                                                                                  |
| ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Phase 0           | [phase0-acceptance.md](phase0-acceptance.md), [workflows.md](workflows.md), and [nodes.md](nodes.md) document containment prerequisites before any higher-level Scientist claim.                                                                                | `uv run python tools/ci/check_scientist_phase0_gate.py --junit-xml _build/.tmp/test-reports/scientist-phase0.xml --output _build/.tmp/test-reports/scientist-phase0-gate.json --output-format json --require-passing`                                                                     |
| Phase 1           | [phase1-acceptance.md](phase1-acceptance.md) and [reliability-scorecard.md](reliability-scorecard.md) document error semantics, deterministic mutation, operational signals, and benchmark evidence.                                                            | `uv run python tools/ci/check_scientist_phase1_gate.py --benchmark-json _build/.tmp/test-reports/scientist-phase1-benchmarks.json --junit-xml _build/.tmp/test-reports/scientist-phase1.xml --output _build/.tmp/test-reports/scientist-phase1-gate.json --output-format json --require-passing` |
| Phase 2           | [reliability-scorecard.md](reliability-scorecard.md), [nodes.md](nodes.md), and [workflows.md](workflows.md) document hot-path and maintainability guardrails until a dedicated Phase 2 page is added.                                                          | `uv run python tools/ci/check_scientist_phase2_ratchet.py`                                                                                                                                                                                                                  |
| Phase 3           | [causal.md](causal.md), [calibration-governance.md](calibration-governance.md), [governance-passes.md](governance-passes.md), and [phase3-acceptance.md](phase3-acceptance.md) document causal, governance, fairness, calibration, and reasoning claim closure. | `uv run pytest tests/unit/scientist/causal/test_causal_evaluation_node.py tests/unit/scientist/governance/test_accountability.py tests/unit/scientist/governance/test_calibration_validation.py tests/unit/scientist/agent/test_eval_harness.py -q`                                                    |
| Phase 4           | [frontier-runtime.md](frontier-runtime.md) and [phase4-acceptance.md](phase4-acceptance.md) document distributed safety and feature-gated frontier research.                                                                                                    | `uv run pytest tests/unit/scientist/search/test_frontier_runtime.py tests/unit/scientist/search/test_benchmark_registry.py -q`                                                                                                                                                               |

## Acceptance Barriers

| Barrier                             | Purpose                                                                                                                                                                          |
| ----------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `scientist-phase0-gate`             | Enforces async/lifecycle, idempotency, budget, masking, env-hardening, and statistical Phase 0 evidence.                                                                         |
| `scientist-phase1-gate`             | Enforces reliability scorecard evidence, critical error-semantics regressions, deterministic mutation regressions, runtime benchmarks, and the broad-handler/deep-copy ratchets. |
| `check_scientist_phase2_ratchet.py` | Prevents new maintainability debt growth on the targeted Phase 2 slice.                                                                                                          |
| `check_scientist_reliability.py`    | Builds the machine-readable Gate 2 reliability scorecard from scenario, benchmark, and operational evidence.                                                                     |

## Source Of Truth

- Machine-readable report: `src/polisyos/scientist/remediation_status.py`
- Phase 0 acceptance: [phase0-acceptance.md](phase0-acceptance.md)
- Phase 1 acceptance: [phase1-acceptance.md](phase1-acceptance.md)
- Reliability gate: [reliability-scorecard.md](reliability-scorecard.md)
- Phase 3 acceptance: [phase3-acceptance.md](phase3-acceptance.md)
- Phase 4 acceptance: [phase4-acceptance.md](phase4-acceptance.md)
