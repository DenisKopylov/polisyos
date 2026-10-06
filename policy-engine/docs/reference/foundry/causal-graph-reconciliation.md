# Causal graph reconciliation profiles

`causal.prior.reconcile_causal_graph@1.0.0` merges an existing `GraphReconciliationData` request using the declared literature/data/LLM confidence rules. The method is STRICT_CPU; it does not fit an SCM, infer a PAG equivalence family or establish real-data causal identification. The separate `ComposeSCMFragments` contract remains unchanged.

## Directed candidate profile

The standalone default `static_intake=False` retains the existing candidate reconciliation of known directed data, including compact temporal edges and lag-first cycle handling. A stored arrow–tail edge is known to point from the stored destination to source: the method swaps those nodes and records `data_endpoint_origin` with the original nodes, marks and effective lag. It never converts an unresolved endpoint to a chosen direction. Circle, tail–tail and arrow–arrow inputs raise a typed ValueError before merging or materializing a DAG.

This intentional correction affects callers that previously supplied partially oriented or bidirected inputs to this directed merge. Keep the original partial/mixed graph and use an appropriate supported consumer or carry a limitation. The confidence merge remains a candidate rule; LLM-only edges retain `unsupported_by_evidence`. No authority is acquired by a confidence, warning, graph label or metadata field.

## Static intake profile

`static_intake=True` requires a declared DAG with known forward directed endpoints and no positive lag. PAG, CPDAG and ADMG types refuse on this route. The merged current graph must be contemporaneously acyclic before cycle repair: this profile refuses instead of obtaining a DAG by lagging or dropping an inconvenient edge. Output structural validation runs again before return, and the Scientist node validates the output before persistence.

The Scientist reconciliation node always selects this static profile for its data/prior/hint route. It resolves actual current inputs, verifies selected cached/source artifacts and recomputes rather than reusing an old output based on reference presence. Its persisted full request snapshot supports a fresh reader recomputing actual edges and diagnostics; see [Scientist graph intake](../scientist/causal-graph-intake.md) for input precedence, lineage and lifecycle.

## Verification boundaries

Dedicated native tests use real registered method jobs, genuine CAS method-result references, node execution and a fresh FileSystemCAS reader. They vary current data, prior, configuration, hints and seed; reject absent/wrongly typed cached bytes and malformed current inputs; preserve known reverse direction; and distinguish readable lagged candidates from a supported static route. The static profile does not supply a temporal unfolding or causal law for unresolved endpoints. Known synthetic structure is distinct from admitted real-data evidence and protected policy publication authority.

Existing persisted graph models remain readable. Cached-only node callers must retain or reacquire current source inputs, including source fragments for query-preservation/composition replay. The scientific change is recorded as a breaking Python public API correction; no IR schema, global policy gate or other graph writer changes in this slice.
