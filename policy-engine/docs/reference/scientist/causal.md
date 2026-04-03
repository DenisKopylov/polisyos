# Scientist Causal Runners
Related explanation: [Causal Engine](../../explanation/causal-engine.md).

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

## Execution API

::: polisyos.scientist.causal.execution

::: polisyos.scientist.causal.readiness

