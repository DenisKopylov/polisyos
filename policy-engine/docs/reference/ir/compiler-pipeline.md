# Compiler Pipeline
Related explanation: [IR — Intermediate Representation](index.md).

> Execution-free pass layer for registry composition, Trinity linking, estimand normalization, lineage analysis, and dead-artifact diagnostics.

`polisyos.ir.passes` turns the IR layer into a compiler-style pipeline:

- `PassContext` carries named surfaces such as `registry_compose_request`, `trinity_bundle`, `estimand_ast`, `artifact_store`, and `causal_execution_bundle`.
- `IRAnalysis` is read-only and cacheable by deterministic content fingerprints.
- `IRPass` is the generic base for transforms and analyses.
- `PassPipeline` runs passes in declared order and reuses cached analysis results when the dependency fingerprint set is unchanged.
- `InvalidationSet` exists for explicit cache flushes, but the default invalidation story is content-addressed and therefore deterministic.

## Core Passes

| Pass | Kind | Inputs | Outputs |
|------|------|--------|---------|
| `RegistryDependencyPass` | transform | `registry_compose_request` | `registry_compose_result`, `registry_bundle` |
| `TrinityLinkAnalysisPass` | analysis | `trinity_bundle`, `registry_bundle` | `linked_trinity_bundle`, `link_report` |
| `CrossModelTypeCheckPass` | analysis | artifact store plus execution/link surfaces | `cross_model_type_check` |
| `EstimandNormalizationPass` | analysis | `estimand_ast` | `normalized_estimand_ast`, `estimand_content_hash` |
| `SlotMechanismReachabilityPass` | analysis | `linked_trinity_bundle`, `registry_bundle` | `slot_mechanism_reachability` |
| `UnusedArtifactAnalysisPass` | analysis | `artifact_store`, lineage roots/bindings | `artifact_lineage_graph`, `unused_artifact_analysis` |

## Lineage Model

`polisyos.ir.artifacts.lineage` normalizes artifact provenance into explicit nodes and edges:

- `produced_by`: artifact -> task
- `consumed_by`: artifact -> task
- `derived_from`: artifact -> upstream artifact
- `invalidated_by`: artifact -> task

`CausalExecutionBundle.root_artifact_ids()` and `CausalExecutionBundle.artifact_task_bindings()` provide the observation/execution bridge into this graph, which makes dead-artifact diagnostics possible without runtime execution.

## Estimand Dedupe

`polisyos.ir.analytics.estimand` now exposes semantic normalization and CAS helpers:

- commutative `ProductNode` factors are canonically ordered
- single-factor products collapse to the factor
- tuple-like fields such as `conditioning`, `variables`, `intervention_set`, and side-condition variable lists are de-duplicated and sorted
- `EstimandAST.content_hash()` hashes the normalized semantic payload, not the author-facing `query_str`

This means two semantically identical estimands can persist to the same artifact id even if their payload order or descriptive label differs.

## Numeric Policy

Uncertainty envelopes use an explicit bounded-float policy by default:

- `numeric_policy.mode = float_round_12`
- `decimal_places = 12`
- optional `hybrid` mode zeroes values within `absolute_tolerance`

That policy is part of the IR payload and therefore part of schema evolution and reproducibility, rather than hidden consumer behavior.
