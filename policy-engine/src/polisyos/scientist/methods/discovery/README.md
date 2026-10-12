# Discovery Methods (`polisyos.scientist.methods.discovery`)

Graph discovery methods own causal graph hypotheses, literature/data priors,
active disambiguation, portfolio discovery execution, stability analysis,
downstream utility judging, and bounded discovery workers.

GraphPriorBundle schema 1.2 preserves per-hypothesis identification status,
limitation reasons, and typed unknown/ranking-only scope for graph-derived
constraint diagnostics from the DownstreamUtilityReport. Exact schema 1.1
artifacts remain labeled 1.1 and are read as routing-only with unknown scope;
current source verification requires the 1.2 producer-consumer handshake. Its
selected CAS view links the selected report; the report links the selected graph-hypothesis set
and task profile, and the set links the same selected task profile plus each
selected hypothesis. Cross-graph compilation records the selected manifest
profiles and payload hashes and recomputes the identification projection on
the same selected graph used by UtilityJudge, preserving its warning context.
It replays EvidenceWeightedAggregator from the ordered selected hypotheses,
stability report, and utility report, then requires the persisted matrix to
match. It replays GraphPriorBuilder and compares its complete emitted edge
collections, weights, and summaries. This preserves producer support IDs that
span both orientations of a skeleton rather than requiring every contributor
to contain the dominant direction. If a supported hypothesis has different raw
and selected graph bases, the status remains not_established; no graph
equivalence or PAG/CPDAG completion is inferred. Missing or mismatched source
evidence remains review-required; STRICT governance emits a blocker.

The legacy `polisyos.scientist.discovery` import surface is retired; first-party
and benchmark code should use this canonical package.
