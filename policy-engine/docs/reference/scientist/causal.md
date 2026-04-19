# Scientist Causal Runners
Related explanation: [Causal Engine](../../explanation/causal-engine.md).
Additional reference: [Causal validity bundle](causal-validity.md), [WS-3A acceptance report](causal-validity-acceptance.md).

Owner: `@scientist-owners`
Source of truth: `src/polisyos/scientist/causal/**`, `src/polisyos/scientist/nodes/builtins/causal/**`, and the linked causal-validity acceptance evidence

The `polisyos.scientist.causal` package provides pure runner-style APIs used by builtin nodes to transform observation-plane bundles into readiness entries, transportability artifacts, and bounded-execution outputs.

## Runner Catalog

| API | Input IR | Output IR / entries | Role |
|-----|----------|---------------------|------|
| `BoundsEstimationRunner` | `BoundsEstimationTask` | bounds-estimation entries and bundle refs | Execute bounded-identification tasks and persist bundle artifacts |
| `ProxyIdentificationRunner` | `ProxyIdentificationBundle` | proxy readiness entries | Score proxy validity against the reconciled graph |
| `TransportabilityChecker` | `TransportabilityCheckBundle` | transportability readiness entries and result refs | Compile transportability checks against calendars and regime metadata |
| `StrategicResponseRunner` | `StrategicResponseSpecsBundle` | strategic readiness entries and strategic-response bundle refs | Evaluate adaptation channels and strategic closure readiness |
| `CounterfactualQueryRunner` | `CounterfactualCheckBundle` | counterfactual readiness entries | Determine whether required counterfactual queries are identified |
| `build_interference_readiness_entries()` | `InterferenceLossSpecBundle` | interference readiness entries | Normalize interference-loss requirements into readiness metadata |

## Default-Path Validity Surface

The builtin causal execution path now also persists a `scientist.causal_validity_bundle`
artifact. This is the operator-facing validity surface that aggregates:

- sensitivity metrics and robustness summaries
- ICP invariance when domain labels are available
- proximal bridge diagnostics when proxy variables are available
- recoverability checks for M-graphs
- PAG refinement lineage for CPDAG/PAG inputs

See [causal-validity.md](causal-validity.md) for the contract and
[causal-validity-acceptance.md](causal-validity-acceptance.md) for the current
acceptance evidence.

## D1 Causal Claim Discipline

Phase 3 causal claims map to persisted artifacts or explicit tests. If a method
is implemented but lacks validation and benchmark evidence, it remains
experimental or offline-gated and must not be described as a default-path SOTA
capability.

| Claim | Required artifact or status | Evidence |
|-------|-----------------------------|----------|
| Default-path causal estimate is confidence-visible | `scientist.causal_validity_bundle.confidence` and decision-packet `causal_validity` section | `tests/scientist/test_causal_evaluation_node.py`, `tests/scientist/test_decision_packet_node_v3.py` |
| Sensitivity and robustness are auditable | `checks.sensitivity`, sensitivity result ref, robustness summary | `tests/foundry/methods/catalog/causal/test_validity_eval_pack.py` |
| Transportability, proxy, strategic, interference, and counterfactual readiness are explicit | Readiness entries and `run_causal_readiness` outputs, including blocker summaries where required | `tests/scientist/nodes/builtins/causal/test_run_causal_readiness.py`, `tests/scientist/nodes/builtins/causal/test_counterfactual_identification_gate.py` |
| Frontier causal methods are not default-on | `FrontierRuntimeReport.capabilities[*].status` plus `offline_validation_ref` and `benchmark_pack_ref` before offline availability | `tests/scientist/test_frontier_runtime.py`, [frontier-runtime.md](frontier-runtime.md) |

## Validation Commands

```bash
uv run pytest tests/scientist/nodes/builtins/causal -q
uv run pytest tests/scientist/test_causal_evaluation_node.py tests/scientist/test_decision_packet_node_v3.py -q
uv run pytest tests/foundry/methods/catalog/causal/test_validity_eval_pack.py -q
```

## Execution API

::: polisyos.scientist.causal

::: polisyos.scientist.causal.execution

::: polisyos.scientist.causal.readiness
