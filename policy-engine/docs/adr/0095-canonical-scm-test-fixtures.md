# ADR-0095: Canonical SCM Test Fixtures

## Status

Proposed

## Date

2026-02-28

## Context

Causal inference modules (discovery, estimation, refutation, transportability) each
maintain ad-hoc test graphs, leading to duplicated setup code, inconsistent edge
definitions, and tests that pass on one synthetic graph but fail on structurally
equivalent variants. A shared library of canonical structural causal models (SCMs)
with known analytical ground truth enables consistent, comparable testing across
all foundry methods and governance passes. This is a cross-cutting testing
infrastructure decision.

## Decision

1. Define seven canonical SCM fixtures, each with full structural specification
   (nodes, edges, functional forms) and analytical ground-truth effects:

   - **FORK**: common cause (X <- Z -> Y), ATE analytically zero after conditioning.
   - **CHAIN**: mediation (X -> M -> Y), direct effect zero, total effect nonzero.
   - **COLLIDER**: collider bias (X -> Z <- Y), unconditional ATE zero.
   - **IV**: instrumental variable (Z -> X -> Y, Z -/-> Y), IV estimate recoverable.
   - **BACKDOOR_TRANSPORT**: backdoor-admissible graph with an S-node for
     transportability testing.
   - **FRONT_DOOR**: front-door criterion applicable (X -> M -> Y, U -> X, U -> Y).
   - **DIAMOND**: diamond structure (X -> A, X -> B, A -> Y, B -> Y) for
     multi-path effect decomposition.
2. Implement fixtures in `tests/_helpers/causal_scm_fixtures.py` as shared helper
   functions exposing canonical graph data, fixture registry entries, and
   ground-truth ATE values.
3. All foundry method tests and governance pass tests must use these fixtures
   instead of defining local graphs, enforced by the `lint_foundry` tool.
4. Each fixture includes a `generate_data(n, seed)` method that produces a
   pandas DataFrame from the analytical SCM with configurable sample size and
   reproducible randomness.
5. Ground-truth values are computed symbolically and hard-coded; tests assert
   estimator output within a tolerance of the analytical value.

## Consequences

### Positive

- Eliminates duplicated and inconsistent test graph definitions across modules.
- Analytical ground truth enables precise regression detection for estimators.
- The `generate_data` method provides reproducible synthetic datasets, removing
  reliance on external test data files.

### Negative

- Seven fixtures may not cover all edge cases (e.g., cycles, selection bias,
  measurement error); the set will need to grow over time.

- Hard-coded ground truth must be re-verified if fixture definitions change,
  creating a maintenance coupling.

- Enforcing fixture usage via linting adds friction for developers writing
  exploratory or one-off tests.
