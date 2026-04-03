# ADR-0029: E-Value ATE-to-Risk-Ratio Conversion Strategy

## Status
Accepted

## Date
2026-02-28

## Context
Phase 4 sensitivity analysis computes E-values to quantify the minimum strength of
unmeasured confounding that could explain away an observed causal effect. E-values
operate on the risk-ratio (RR) scale, but most policy-engine estimators produce
average treatment effects (ATE) on continuous outcomes.

Converting ATE to RR is not unique: log-linear approximation, square-root
transformation, and empirical CDF-based approaches each yield different E-values
for the same underlying estimate. Without recording which conversion was used,
sensitivity results are not reproducible across runs or auditable by governance
passes.

## Decision
1. Add a `conversion_method` field to `SensitivityResult` in the IR analytics
   contract (`polisyos.ir.analytics.sensitivity`).
2. Default conversion method is **log-linear approximation** (`log_linear`),
   which is the most widely cited in the epidemiological literature.
3. Callers may override the conversion method per invocation by passing
   `conversion_method` to the sensitivity metrics function.
4. Supported values: `log_linear`, `sqrt`, `empirical_cdf`.
5. The chosen method is persisted in the CAS artifact alongside the E-value
   so that downstream governance and audit passes can verify reproducibility.

## Consequences
### Positive
- E-value calculations are fully reproducible given the same input and
  conversion method.
- Governance passes can verify that sensitivity analysis used an approved
  conversion strategy.
- Enables cross-study comparison of robustness when conversion methods are
  held constant.

### Negative
- Adds an extra field to the `SensitivityResult` IR contract, increasing
  serialization surface.
- Users must be aware of conversion semantics; incorrect method choice can
  produce misleading E-values.
