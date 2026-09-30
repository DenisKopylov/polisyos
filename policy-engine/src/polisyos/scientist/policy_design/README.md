# Scientist Policy Design

This package contains Scientist-side policy design helpers for formulation,
critique, search, translation, and adversarial review. Runtime authority remains
outside this package: outputs here are candidate or analytic material until
they are bound by governed runtime-quality producers and closeout gates.

## Persisted Frontier Artifacts

`PolicyFrontierReport` and `RejectedAlternativesSummary` support schema v1 and
v3. Ordinary new producers write v3; schema v2 was unissued and is rejected.
Bounded compatibility tests round-trip synthetic v1 golden payloads
byte-exactly through the version-specific projection. An authentic committed
historical v1 fixture corpus is `not_established`, and complete historical
1.0 snapshot replay remains UNRUN. The v3 report DTO validator compares the
supplied source set with projected eligible identities, checks for duplicates
within the source and unknown sets and overlap between those sets, and
requires the projection assessment status to be `denominator_limited` when
the supplied source set differs from projected eligible identities or the
supplied unknown set is nonempty. It does not authenticate or independently
reconcile unknown identities. The ordinary
`PolicyArtifactBuilder._build_frontier_report` path does not receive an
independent source or unknown-eligibility input: it copies the projection's
eligible identities into the source field and leaves
the unknown set empty. That validation is self-derived on the ordinary path;
it cannot detect candidates omitted before registry projection and does not
establish a complete upstream universe. A missing registry remains
`basis_limited` and unranked. The summary has its own v3 `view_projection`,
not the report-level source/unknown fields. These artifacts remain candidate
material and do not confer runtime authority. See the
[artifact migration and rollout guidance](../../../../ops/migrations/ir/README.md#scientist-frontier-artifact-v3).
