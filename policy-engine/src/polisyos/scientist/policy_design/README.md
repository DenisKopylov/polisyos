# Scientist Policy Design

This package contains Scientist-side policy design helpers for formulation,
critique, search, translation, and adversarial review. Runtime authority remains
outside this package: outputs here are candidate or analytic material until
they are bound by governed runtime-quality producers and closeout gates.

## Persisted Frontier Artifacts

`PolicyFrontierReport` and `RejectedAlternativesSummary` support schema v1 and
v3. Ordinary new producers write v3; v1 is retained for byte-exact historical
replay, while schema v2 was unissued and is rejected. The v3 report DTO
validator checks explicitly supplied source-feasible and eligibility-unknown
identities against its global registry projection, and requires
`denominator_limited` when those supplied values show a mismatch or unknown
eligibility. The ordinary `PolicyArtifactBuilder._build_frontier_report`
path does not receive an independent source or unknown-eligibility input: it
copies the projection's eligible identities into the source field and leaves
the unknown set empty. That validation is self-derived on the ordinary path;
it cannot detect candidates omitted before registry projection and does not
establish a complete upstream universe. A missing registry remains
`basis_limited` and unranked. The summary has its own v3 `view_projection`,
not the report-level source/unknown fields. These artifacts remain candidate
material and do not confer runtime authority. See the
[artifact migration and rollout guidance](../../../../ops/migrations/ir/README.md#scientist-frontier-artifact-v3).
