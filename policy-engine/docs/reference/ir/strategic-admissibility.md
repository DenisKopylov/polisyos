# Strategic Admissibility

Related reference: [Analytics IR](analytics.md), [IR Schema Catalog](schema-catalog.md).

Owner: `@ir-owners`
Source of truth: `src/polisyos/ir/analytics/strategic.py`, `src/polisyos/foundry/methods/catalog/causal/strategic.py`, `tests/unit/ir/analytics/test_phase_d_contracts.py`, `tests/unit/foundry/methods/catalog/causal/test_strategic.py`

> Stage 6.1 contract lift for strategic causality. PolicyOS no longer treats
> generic equilibrium names as sufficient strategic metadata; strategic
> requests are classified by game class, solution concept, tractability, and
> default fallback semantics.

Freshness: 2026-04-19

## Why This Exists

The reduced-scope D.2 runtime still solves only tiny finite games exactly:

- single-follower optimistic `stackelberg`
- small finite `best_response_fixed_point`

That implementation limit is narrower than the policy question. For realistic
strategic environments, the important contract question is not only "can we run
a solver" but also:

- does the requested equilibrium notion exist under declared assumptions
- is the equilibrium set typically unique or selection-sensitive
- should PolicyOS return a point, bounds, a macro abstraction, or block

`StrategicSCM` now carries this classification explicitly through
`equilibrium_descriptor`.

## Registry

The admissibility registry currently ships these policy-facing classes.

| Game class                    | Solution concept                                     | Existence anchor                                          | Tractability   | Default fallback    | Current runtime posture |
| ----------------------------- | ---------------------------------------------------- | --------------------------------------------------------- | -------------- | ------------------- | ----------------------- |
| `zero_sum`                    | `minimax`                                            | minimax / zero-sum value exists                           | `P`            | `exact_equilibrium` | `blocked_unsupported`   |
| `normal_form_general_sum`     | `mixed_nash`                                         | finite mixed Nash exists                                  | `PPAD`         | `strategic_bounds`  | `blocked_research`      |
| `stackelberg_single_follower` | `stackelberg_optimistic`                             | single-follower commitment equilibrium                    | `P`            | `exact_equilibrium` | `supported`             |
| `stackelberg_single_follower` | `stackelberg_pessimistic`                            | single-follower commitment equilibrium                    | `P`            | `exact_equilibrium` | `blocked_unsupported`   |
| `stackelberg_complex`         | `stackelberg_optimistic` / `stackelberg_pessimistic` | requires explicit follower-selection semantics            | `NP_HARD`      | `blocked`           | `blocked_research`      |
| `potential_congestion`        | `pure_nash`                                          | Rosenthal / potential-game pure equilibrium               | `PLS`          | `strategic_bounds`  | `blocked_research`      |
| `concave_vi`                  | `variational_equilibrium`                            | concave-game existence                                    | `POLY_EPSILON` | `strategic_bounds`  | `blocked_unsupported`   |
| `gne_jointly_convex`          | `variational_equilibrium`                            | jointly-convex GNE existence                              | `POLY_EPSILON` | `strategic_bounds`  | `blocked_unsupported`   |
| `gne_nonconvex`               | `variational_equilibrium`                            | nonconvex GNE needs global optimization / convexification | `GLOBAL_OPT`   | `blocked`           | `blocked_research`      |
| `anonymous_aggregative`       | `epsilon_nash`                                       | anonymous-game PTAS / macro limit                         | `POLY_EPSILON` | `macro_abstracted`  | `blocked_unsupported`   |
| `small_finite_best_response`  | `best_response_fixed_point`                          | explicit finite-profile enumeration                       | `P`            | `exact_equilibrium` | `supported`             |

## Existence Rules

- `zero_sum` + `minimax`: use the minimax existence/value theorem as the
  policy anchor; this is the clean allowlist case for exact reporting once a
  dedicated solver lands.

- `normal_form_general_sum` + `mixed_nash`: finite mixed Nash exists, but
  existence alone is not enough to justify a point recommendation because
  computation is hard and equilibrium selection is often policy-sensitive.

- `potential_congestion` + `pure_nash`: pure equilibrium exists in potential /
  congestion subclasses, but that does not make pure-equilibrium selection a
  safe default output.

- `concave_vi` + `variational_equilibrium`: existence is weaker than
  uniqueness; the registry therefore defaults to bounds unless the descriptor
  carries a uniqueness certificate such as `strong_monotonicity`,
  `diagonal_strict_concavity`, or `unique_equilibrium`.

- `gne_jointly_convex` + `variational_equilibrium`: jointly-convex shared
  constraint games stay in bounds mode by default; exact mode is unlocked only
  by a uniqueness/monotonicity certificate.

- `anonymous_aggregative` + `epsilon_nash`: the contract treats large-population
  strategic classes as approximation-first and macro-friendly rather than
  point-equilibrium first.

## Contract Surface

`polisyos.ir.analytics.strategic.StrategicSCM` now supports two layers:

- `equilibrium_concept`: legacy shorthand kept for compatibility with existing
  `"stackelberg"`, `"nash"`, and `"best_response_fixed_point"` payloads

- `equilibrium_descriptor`: the normalized contract surface containing
  `game_class`, `solution_concept`, `tractability_class`,
  `existence_assumptions`, `uniqueness_assumptions`,
  `approximation_epsilon`, `tie_breaking_rule`, and `default_fallback_mode`

Legacy payloads are auto-expanded into descriptors:

- `"stackelberg"` -> single-follower optimistic Stackelberg
- `"nash"` -> finite general-sum mixed Nash
- `"best_response_fixed_point"` -> explicit small finite fixed-point search

Descriptor-only payloads are allowed for research-first classes that have no
legacy shorthand.

## Fallback Semantics

The solver now consults the descriptor registry before degrading:

- classes with default `blocked` skip the generic payoff-envelope bounds path
- classes with default `macro_abstracted` try macro abstraction before the
  normal bounds path when macro tables are present

- classes with default `strategic_bounds` keep the existing bounds-first
  behavior

For `anonymous_aggregative`, the contract also widens acceptable abstraction
preservation types to:

- `exact`
- `approximate`
- `policy_value_only`

Non-exact macro abstractions must carry `error_bound`.
For `approximate`, the linked `AbstractionCertificate` must also carry a
bounded query family in `preserved_queries`, per-query bounds in
`metadata.estimand_error_bounds`, explicit `non_preserved_queries`, and an
machine-verified intervention family (`metadata.intervention_family_verified =
true`). If only a single scalar welfare query is
certified, use `policy_value_only` instead.

## Result Artifacts

`StrategicClosureSummary` now stores the normalized descriptor alongside the
legacy shorthand when available. This keeps the bundle surface compatible while
making admissibility decisions auditable downstream.

## Decomposition Guard

Stage `T5.3` adds a second gate that is intentionally separate from equilibrium
solving itself.

- `fallback_mode` answers whether PolicyOS solved or bounded the strategic game.
- `decomposition_status` answers whether PolicyOS may honestly expose a
  point-valued split between `causal_component_ref` and
  `strategic_closure_ref`.

The bundle now distinguishes four decomposition states:

- `exact`: point decomposition is licensed by an explicit certificate plus an
  anchor equilibrium.

- `selector_invariant`: multiple equilibria may exist, but all admissible
  selectors induce the same component pair.

- `bounded`: only interval-valued component disclosure is allowed.
- `blocked`: total post-adaptation value may still be known, but the two-number
  decomposition is not licensed.

Current runtime helpers default conservatively to `blocked` unless an explicit
decomposition certificate is attached. This is deliberate: exact equilibrium
computation alone does not prove the frozen-baseline counterfactual
`Y(a1, s0)` is well-defined or selector-invariant.

## Validation

```bash
uv run pytest tests/unit/ir/analytics/test_phase_d_contracts.py tests/unit/foundry/methods/catalog/causal/test_strategic.py -q
uv run --extra ml python tools/quality/diagnostics/gen_schema.py --check
```
