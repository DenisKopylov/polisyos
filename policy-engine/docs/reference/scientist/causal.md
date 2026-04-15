# Scientist Causal Runners
Related explanation: [Causal Engine](../../explanation/causal-engine.md).
Additional reference: [Causal validity bundle](causal-validity.md), [WS-3A acceptance report](causal-validity-acceptance.md).

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

## Execution API

::: polisyos.scientist.causal

::: polisyos.scientist.causal.execution

::: polisyos.scientist.causal.readiness
