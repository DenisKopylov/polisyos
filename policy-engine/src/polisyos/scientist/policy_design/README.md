# Scientist Policy Design

This package contains Scientist-side policy design helpers for formulation,
critique, search, translation, and adversarial review. Runtime authority remains
outside this package: outputs here are candidate or analytic material until
they are bound by governed runtime-quality producers and closeout gates.
The `polisyos.scientist.policy_design` package facade is the supported import path for policy candidate schemas, builders, and `derive_phase2_parameter_bounds()`. The latter is the same owner function defined in `search.py`. LLM-authored values remain candidate-grade until grounded and separately admitted.

## Explicit Option-to-Program Relation

The internal `option_program` owner persists a versioned relation between an
exact request, option set, selected option, final candidate and final Trinity.
Its fresh reader recomputes the relation from those selected sources, including
their profiles and source roles; a stored status or producer action map is not
evidence of correspondence. Callers must pass their actual final champion and
reissue after search changes it.

The first interpretation profile accepts one explicitly structured
`ExplicitPolicyProgramIntent` as the option's whole `intervention_outline`.
It reconciles the complete declared IR program, target population, target
jurisdiction/time and hard/soft constraints. Equivalent inclusive schedule
spellings have the same meaning. Unsupported prose obligations, multi-option
composition and legacy requests with implicit target scope remain
`not_established`. A correctly rebound ban intent still mismatches a subsidy
program; matching identities alone cannot satisfy this check.

`declared_program_match` is candidate-grade correspondence to declared IR,
not proof of an implemented mechanism's behavior, effects, legal validity or
publication eligibility. `execution_correspondence` remains
`not_established`; actual compiler/registry semantics and final workflow
consumers are separate integration work. Until that integration is present,
staged reports retain `option_program_correspondence_not_established`.

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
## Completed Graph-Method Metric Observations

The Scientist runtime candidate can consume a completed, Runtime-owner-selected
graph-method execution as bounded metric observations. It rechecks the selected
SimulationResult, execution bundle, binding set, current sparse pre-dispatch
input snapshot, output, and compiled objective/unit contract through selected
Core artifact profiles. The registered Ex-Ante mean-change path is specific to
`policy.evaluation.ex_ante_simulation@1.0.0`; it recomputes the paired
scenario-minus-baseline quantity from the captured current inputs. Direct HTE
method results, unverified or stale projections, legacy vector schemas, missing
owner selection, and incomplete bindings do not become graph observations by
label or shape alone.

An admitted observation is candidate evidence for the configured objective
scorer. It does not establish population representativeness, causal validity,
empirical calibration, legal meaning, permission, or publication authority.
Those predicates remain separate and must retain their own typed limitations.
The source proposal's selected producer/consumer tests and native lint receipt
do not replace the composed Runtime integration replay; that replay remains
required before this candidate is treated as verified.


For the completed method-metric follow-up, an omitted
`method_metric_source_run_id` remains the explicit absence that selects the
legacy route. Runtime emits projection identity, projection basis, required
flag, and request status as one capsule: the consumer checks their consistency
before scoring, and a missing status or partial/unknown family cannot become a
legacy request. Total erasure of all four protocol keys remains indistinguishable
from a historical empty context; a removal test records this bounded residual.
A present malformed selector remains invalid through the funnel
and cannot fall back to a default score. The concrete Runtime owner and protected
read surface are still required for the composed capability.
