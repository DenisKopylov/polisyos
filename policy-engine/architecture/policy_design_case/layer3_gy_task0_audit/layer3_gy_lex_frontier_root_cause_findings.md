# GY Task 0 Lex Root Cause And Frontier Semantics Audit

Date: 2026-06-14

Scope: diagnose why `run_hierarchical_policy_search` fails on the pinned GY policy-design route, and separate the actual root cause from adjacent risks: thin input, synthetic scaffold, bad bounds, and frontier/objective laundering.

## Short Result

Primary root cause: `implementation_bug_optional_bounds_none_normalized_to_zero`.

The failing persisted Trinity bundle does **not** contain bad equal bounds. It contains:

- `param_id=verified_policy_option_rate`
- `default_value="0.1"`
- `min_value=null`
- `max_value=null`
- `tunable=true`

The failure is introduced in `HierarchicalSearchCoordinator.build_parameter_search_spec`: `parameter.min_value` and `parameter.max_value` are passed through `_normalize_value_like(...)` before `None` is preserved. `_normalize_value_like(None)` returns `0.0`, so an absent optional bound becomes an explicit lower/upper pair of `0.0..0.0`. `ParameterBounds` then correctly raises:

`Invalid bounds for 'verified_policy_option_rate': lower >= upper`

This is a search-spec optional-bound bug, not a Lex adapter absence, not a bad upstream bounds artifact, and not a frontier laundering event observed in the current run.

## Reproduction Evidence

Saved DAG snapshot:

- `_build/.tmp/gy0-census/dag_node_census3.json`
- workflow status: `fail`
- node counts: `14 ok / 1 fail / 22 skip`
- failing node: `run_hierarchical_policy_search`
- error code: `node.invalid_state`
- error message: `Hierarchical policy search failed: Invalid bounds for 'verified_policy_option_rate': lower >= upper`
- `policy_frontier_report_ref`: absent

Persisted Trinity bundle:

- artifact: `sha256:9497cb4c5c629e004a322836112ad361f44618132346b019433620a6e58333cf`
- path: `_build/.tmp/gy0-census/dag_cas/artifacts/sha256/94/97/9497cb4c5c629e004a322836112ad361f44618132346b019433620a6e58333cf.blob`
- kind: `ir.trinity_bundle`
- intervention: `verified_policy_option`, `tax_subsidy`, `params.rate="0.1"`
- parameter: `verified_policy_option_rate`, no explicit min/max

Direct reproducer:

- `normalized_default=0.1`
- `normalized_min=0.0`
- `normalized_max=0.0`
- `_derive_bounds(0.1, 0.0, 0.0) -> (0.0, 0.0)`
- `ParameterBounds(...) -> ValueError`

Control probe:

- the generated `parameter_schedule` for the same value derives a valid range when `None` is preserved:
- `_derive_bounds(0.1, None, None) -> (0.08, 0.12000000000000001)`

## Route Trace

The real route is wired and invoked:

- `src/polisyos/scientist/orchestration/workflows/policy_design.py:110` declares the `run_hierarchical_policy_search` DAG node.
- `src/polisyos/scientist/nodes/builtins/planning/run_hierarchical_policy_search.py:201` instantiates `HierarchicalPolicySearchAdapter`.
- `src/polisyos/scientist/nodes/builtins/planning/run_hierarchical_policy_search.py:207` calls `adapter.run_search(...)`.
- `src/polisyos/lex/interventions.py:1024` calls `coordinator.build_parameter_search_spec(...)`.
- `src/polisyos/scientist/policy_design/search.py:282` normalizes default.
- `src/polisyos/scientist/policy_design/search.py:283` and `:284` normalize optional min/max before preserving `None`.
- `src/polisyos/scientist/methods/search/strategies/types.py:63` correctly rejects `lower >= upper`.
- `src/polisyos/scientist/nodes/builtins/planning/run_hierarchical_policy_search.py:220` catches the `ValueError` and returns a node fail.

## Classification

`bug`: primary. The bug is in optional-bound handling in Scientist policy-design search spec construction.

`thin input`: not primary. The input has a tunable numeric default; it is enough to derive a range if optional bounds remain optional.

`synthetic scaffold`: contributing but not causal. `formalize_policy_option_set` builds a generic verified option with `parameters: {"rate": "0.1"}`, and `MockFormalizerAgent` turns it into a generic `tax_subsidy`/`avg_income` Trinity bundle. That is a semantic-quality problem for future frontier authority, but it did not create bad equal bounds.

`bad bounds`: not observed upstream. The real persisted bundle has absent min/max; the bad equality is synthesized by the search builder.

`frontier/objective laundering`: not observed in the failed run. No frontier report is persisted because the node fails first. There is still a post-repair P25 risk: the existing `PolicyFrontierReport` metadata is too thin to prove search incompleteness, objective provenance, bound derivation, candidate/seed origin, and non-authority semantics.

## Frontier Semantics Risk

Current run:

- no `policy_frontier_report_ref`
- no `scientist.policy_frontier_report` from the failing node
- downstream nodes are `blocked_upstream`, not independently broken

Post-repair risks:

- `_persist_frontier_report` records only metadata `{"source": "c6c_hierarchical_policy_search"}`.
- `PolicyFrontierReport` is routing/cross-run-learning, but does not require typed search-space provenance or objective-source refs.
- `_iter_candidate_records` can fall back to `feasible=True` and `objective_value=0.0` for accepted structures when no evaluation records exist.
- `ObjectiveStack` has useful typed channels, but also has fallback/default objective surfaces; those defaults must not become evidence authority.

Repair acceptance should therefore include P25, not only the bounds fix:

- missing min/max stays `None` until bound derivation or an equivalent typed optional-bound path;
- explicit bad equal bounds still fail closed or are typed as fixed/non-tunable before search;
- frontier report carries search space source, bound derivation, candidate/seed source, objective source refs, stage-B blockers, stopping budget, and non-authority purpose;
- unevaluated candidates are not persisted as feasible frontier members;
- downstream governance remains blocked until there is either a valid search result or a typed `search_blocker` artifact.

## GY Plan Implication

The lex row should stay `wired_but_rotten`, but the repair target should be narrowed:

`repair_search_spec_optional_bound_handling_then_add_p25_frontier_ledger_acceptance_before_gy2_governance`

This is stronger than "fix Lex" and safer than widening bounds ad hoc. The minimum repair is not to silence the exception; it is to preserve optional-bound semantics, then prove the repaired node cannot launder a thin/generic frontier into downstream governance authority.
