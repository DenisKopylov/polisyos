# Scientist
Related explanation: [Governance Model](../../explanation/governance-model.md).

> Orchestration layer for workflow DAGs, governance passes, causal readiness, and policy-design search.

`polisyos.scientist` coordinates the end-to-end runtime around Foundry and IR artifacts. It assembles workflow specs, executes builtin nodes, persists experiment state, and applies governance before a decision packet is emitted.

## Surface Map

| Area | What it covers | Reference |
|------|----------------|-----------|
| Root facade | `run_experiment`, `ExperimentState`, observability accessors | This page |
| Workflows | `causal_full` and `policy_design` DAG specs | [workflows.md](workflows.md) |
| Governance passes | 20+ builtin and shim validators, runtime filtering | [governance-passes.md](governance-passes.md) |
| Builtin nodes | Causal node protocol, state reads/writes, planning nodes | [nodes.md](nodes.md) |
| Causal runners | Bounds, proxy identification, transportability, strategic response | [causal.md](causal.md) |
| Calibration governance | Backtests, leaderboards, stress scenarios, validation bundles | [calibration-governance.md](calibration-governance.md) |

## Public API

| Export | Role |
|--------|------|
| `run_experiment` | Execute a workflow spec against an `ExperimentState` |
| `ExperimentState` | Immutable-ish workflow state passed across nodes |
| `get_metrics` | Fetch Scientist / platform metrics emitters |
| `get_tracer` | Fetch the OpenTelemetry tracer used during execution |

## Workflow Shape

```mermaid
flowchart LR
    A["Inputs / Trinity"] --> B["Workflow Spec"]
    B --> C["Builtin Nodes"]
    C --> D["Foundry / IR Artifacts"]
    C --> E["Causal Readiness"]
    D --> F["Governance Passes"]
    E --> F
    F --> G["Decision Packet / Reports"]
```

## Key Subsystems

| Submodule | Responsibility |
|-----------|----------------|
| `polisyos.scientist.workflows` | Declarative DAG specs and required binds |
| `polisyos.scientist.governance` | Pass registry, validation pipeline, calibration review |
| `polisyos.scientist.causal` | Readiness and execution runners over observation-plane bundles |
| `polisyos.scientist.nodes.builtins` | Production node implementations used by workflow DAGs |
| `polisyos.scientist.compute.advanced_methods` | C7 advanced artifact suite for factor, survival, sensitivity, and bilevel bundles |

## Advanced Compute

| API | Output artifacts |
|-----|------------------|
| `run_c7_advanced_suite()` | Factor embeddings, cell prototypes, bilevel bundle, Heckman correction, survival hazards, Sobol diagnostics, specification-curve diagnostics |

## API Reference

::: polisyos.scientist

::: polisyos.scientist.api

::: polisyos.scientist.engine.state
