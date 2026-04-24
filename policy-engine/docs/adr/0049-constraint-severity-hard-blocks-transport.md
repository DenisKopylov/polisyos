# ADR-0049: Constraint Severity -- HARD Blocks Transportability

## Status

Proposed

## Date

2026-02-28

## Context

Legal constraints on causal transportability have varying severity. Some constraints
absolutely prevent transport of a causal effect (e.g., a retroactive law that eliminates the
intervention mechanism entirely), while others merely modify the effect or require additional
adjustment. Without a severity classification, the system cannot distinguish between fatal
and manageable legal barriers.

## Decision

1. Legal constraints are classified into two severity levels: `HARD` and `SOFT`.
2. A `HARD` constraint sets `feasible = False` on the `TransportabilityResult` immediately,
   with no further resolution attempted for that transport path.
3. A `SOFT` constraint adds S-nodes to the causal graph representing the legal modification,
   which can then be addressed through the standard resolution loop (ADR-0048).
4. Severity classification is determined by the `transport_constraints.py` module in the lex
   package, based on constraint type and jurisdiction analysis.
5. All HARD blocks require a `justification` field explaining why transport is infeasible,
   for governance audit purposes.

## Consequences

### Positive

- Clear binary distinction prevents the system from attempting impossible transport paths,
  saving computation and avoiding misleading partial results.

- SOFT constraints are integrated into the existing S-node resolution machinery, reusing
  infrastructure from ADR-0048.

- Governance audit trail includes explicit justification for every transport block.

### Negative

- The HARD/SOFT binary may be too coarse; some constraints are contextually hard or soft
  depending on jurisdiction-specific interpretation.

- Misclassification of a SOFT constraint as HARD could unnecessarily block valid transport
  paths.

- Legal expertise is required to validate severity classifications, adding human-in-the-loop
  overhead.
