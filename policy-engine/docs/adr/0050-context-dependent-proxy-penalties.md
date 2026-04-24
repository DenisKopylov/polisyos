# ADR-0050: Context-Dependent Proxy Penalties

## Status

Proposed

## Date

2026-02-28

## Context

When a variable required for transportability adjustment is not directly available in the
target context, a proxy variable may be substituted. A fixed proxy penalty (e.g., always
multiply confidence by 0.8) ignores the reality that proxy quality varies dramatically by
institutional context. GDP-per-capita is a reasonable proxy for economic development in OECD
countries but far less reliable in conflict-affected states.

## Decision

1. Proxy penalties are computed by `proxy_reliability(variable, context)` rather than using a
   fixed discount factor.
2. The function uses World Governance Indicators (WGI) and World Values Survey (WVS) data as
   institutional quality signals to adjust the penalty.
3. The penalty formula is: `penalty = base_penalty * (1 - institutional_quality_factor)`,
   where `institutional_quality_factor` is in [0, 1] derived from WGI/WVS indicators
   relevant to the variable domain.
4. Base penalties are defined per proxy type in the `proxy_resolver.py` registry.
5. When no institutional quality data is available for a context, the maximum penalty
   (base_penalty \* 1.0) is applied as a conservative default.

## Consequences

### Positive

- Proxy-based transport in high-quality institutional contexts receives appropriately higher
  confidence than in low-quality contexts.

- Leverages existing WGI and WVS data already ingested through the datasets module.
- Conservative default (max penalty when data missing) prevents overconfident transport claims.

### Negative

- Adds dependency on WGI/WVS data availability, which may lag behind real-world institutional
  changes.

- The institutional quality factor mapping is domain-specific and requires expert calibration
  for new variable types.

- Computational overhead increases as each proxy substitution now requires a context lookup.
