# ADR-0070: Bidirectional edge (U-node) implies backdoor invalid, needs_advanced_tr

## Status
Proposed

## Date
2026-02-28

## Context
When a PAG contains a bidirectional edge X <-> Y, the U-dummy node projection
(ADR-0066) introduces an unobserved confounder U_{XY}. If this latent
confounder lies on a backdoor path between treatment and outcome, the standard
backdoor adjustment is invalid because U_{XY} is unobserved and cannot be
conditioned on. In such cases, advanced identification strategies (instrumental
variables, frontdoor criterion, or generalised transport formulae) are required.
The system must detect this situation automatically and route the analysis
accordingly.

## Decision
1. After U-node projection, run a backdoor path analysis: if any U-dummy node
   lies on a backdoor path between treatment and outcome, mark the query with
   `needs_advanced_tr=True`.
2. When `needs_advanced_tr` is set, the identification step bypasses simple
   backdoor adjustment and delegates to the advanced transport/identification
   module (frontdoor, IV, or do-calculus completeness algorithm).
3. The `needs_advanced_tr` flag is recorded in the `CausalQueryResult` IR
   object for downstream governance inspection.
4. If no advanced identification strategy succeeds, the query is marked as
   non-identifiable and surfaced as a governance finding.

## Consequences
### Positive
- Automatic detection of backdoor invalidity prevents the system from silently
  applying an incorrect identification strategy when latent confounders are
  present.
- Routing to advanced strategies expands the set of identifiable queries
  beyond what simple backdoor adjustment can handle.
- Recording the flag in IR ensures full transparency about which
  identification strategy was used and why.

### Negative
- Advanced identification strategies are computationally more expensive and
  may not always find a valid estimand, increasing the rate of non-identifiable
  queries.
- The logic coupling U-node projection (ADR-0066) to backdoor analysis creates
  an ordering dependency between graph transformation steps that must be
  carefully maintained.
