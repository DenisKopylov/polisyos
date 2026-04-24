# ADR-0083: Resolution Loop proxy-depth guard: proxy variables don't generate new S-nodes

## Status

Proposed

## Date

2026-02-28

## Context

The resolution loop (Phase 9) handles unobserved variables by substituting proxy
variables from the dataset catalog. Each substitution can introduce new domain-shift
assumptions, which are represented as S-nodes in the transportability diagram. In
pathological cases, a proxy for variable U1 introduces a new unobserved confounder U2,
whose proxy introduces U3, and so on, leading to unbounded graph growth and infinite
loops. The current implementation has no depth limit, and a real-world run on a
governance-quality dataset produced 47 proxy substitution rounds before being manually
killed.

## Decision

1. Introduce a `max_proxy_depth` parameter on the resolution loop (default: 3),
   representing the maximum number of chained proxy substitutions for any single
   original unobserved variable.
2. When `max_proxy_depth` is reached for a variable, the resolution loop marks that
   variable as `UNRESOLVABLE` and proceeds with partial identification (bounding the
   effect rather than point-identifying it).
3. Proxy variables do not generate new S-nodes in the transportability diagram. Only
   original domain-shift variables (those present in the initial Phase 8A annotation)
   carry S-nodes. This prevents proxy chains from inflating the transportability
   problem.
4. The `ResolutionLoopTrace` audit artifact records each substitution step, the
   depth counter, and whether the depth guard fired.
5. `max_proxy_depth` is configurable via the `ProblemFrame` to allow domain experts
   to increase it for studies where deep proxy chains are theoretically justified.

## Consequences

### Positive

- Guarantees termination of the resolution loop in bounded time.
- Prevents artificial inflation of the transportability diagram with proxy-induced
  S-nodes.

- Partial identification fallback preserves useful (bounded) causal conclusions even
  when full point identification fails.

### Negative

- The default depth of 3 may be too conservative for some domains (e.g., social
  science with many latent constructs); requires tuning.

- Partial identification bounds can be wide and uninformative when key confounders
  remain unresolved.

- Adds complexity to the resolution loop's state machine.
