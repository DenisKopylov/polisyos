# Uncertainty (`polisyos.foundry.uncertainty`)

`uncertainty` - propagation layer for mapping input uncertainty envelopes to
output metric uncertainty in Foundry simulations.

## Role in System

- **Depends on:** `polisyos.ir.analytics.uncertainty`, JAX
- **Used by:** Scientist uncertainty propagation nodes and calibration post-fit analysis
- Sits after execution and before downstream reporting/aggregation.

## Key Concepts

- **Dispatcher** - selects delta, Monte Carlo or auto propagation strategy.
- **Delta method** - Jacobian-based propagation for differentiable simulations.
- **Monte Carlo** - sampling-based propagation when analytic assumptions fail.
- **Versioned posterior pushforward** - explicitly consumes an IR posterior-summary 1.1 candidate
  and evaluates its named point functional and exact ordered source rows.
- **Aggregation** - envelope merging for multi-strategy or multi-run outputs.
- **Config-driven fallback** - strategy choice is explicit and inspectable.

Precision-weighted and Bayesian aggregation require resolved independence evidence for distinct
inputs. Distinct content-bound origin IDs establish identity, not statistical independence; envelope
metadata labels such as `dependency="independent"` or `independence=true` do not establish that
relation. Until a source-bound relation resolver is wired, multi-origin inputs retain a conservative
non-gating hull and an unestablished effective-information count. Exact duplicate origins are still
collapsed before aggregation.

## Evaluation failure boundaries

Monte Carlo evaluates exception cause, context, and exception-group links through a bounded shared
classifier. A visible `OSError`, Pydantic validation error, fatal or validation `PolicyOSError`, or
adapter-declared global error is not converted into a missing draw. A cyclic or truncated graph also
fails closed. A root typed transient failure gets one retry with the same evaluator inputs in nominal,
sampled, and posterior evaluation paths; exhausting that retry fails closed. Physical evaluator calls
and retries are recorded separately from the logical draw denominator in the persisted Monte Carlo
ledger. Sampling errors and all other failure classes are not retried. The legacy Monte Carlo
candidate behavior is retained only for an unchained built-in `RuntimeError` raised by an individual
draw. Other errors propagate instead of producing a conditional partial distribution.

## Public API

| Type/Function                   | Description                                               |
| ------------------------------- | --------------------------------------------------------- |
| `PropagationConfig`             | Configures confidence and propagation strategy.           |
| `PropagationDispatcher`         | Selects and executes propagation strategies.              |
| `PropagationResult`             | Output record for a propagated metric envelope.           |
| `PropagationStrategy`           | Protocol for propagation implementations.                 |
| `MonteCarloPropagator`           | Monte Carlo implementation with the versioned posterior consumer. |
| `PosteriorJointInputMatrix`      | Content-bound selected parameter names and source draw rows. |
| `PosteriorPushforwardFailure`    | Typed failure record retaining an unavailable output row. |
| `PosteriorPushforwardOutcomeCode` | Outcome category for one posterior evaluator row. |
| `PosteriorPushforwardOutputSummary` | Separate evaluated point, output functionals and equal-tail bounds. |
| `PosteriorPushforwardResult`     | Candidate-only v1.1 result retaining point, rows and bounds separately. |
| `QuasiMCSampler`                | Quasi-Monte-Carlo sampler for sampling-based propagation. |
| `aggregate_envelopes()`         | Combines multiple envelopes into one.                     |
| `compute_first_order_indices()` | Sensitivity helper for variance attribution.              |
| `extract_std()`                 | Extracts scale from a typed parametric fit or legacy interval. |

→ Full reference: [docs/reference/foundry/index.md](../../../../docs/reference/foundry/index.md)

## Versioned posterior-summary consumer

`MonteCarloPropagator.propagate_posterior_summary()` is an explicit v1.1 candidate path. It
recomputes the selected summary from the content-bound draw payload, requires the caller to name
the same `posterior_mean` or `posterior_median` role, and hashes the exact selected parameter names,
draw order, and joint rows before running the evaluator. The returned `PosteriorPushforwardResult`
retains one logical output per source row, records failures by row, and recomputes posterior output
mean, median, and equal-tail bounds independently from the evaluator value at the selected point.
A root typed transient can cause one additional physical call on that same input; new results report
`simulation_attempt_count` and `retry_attempt_count` separately from row count. Zero-retry results
retain `one_evaluator_call_per_source_draw`; retried results use the additive
`one_logical_result_per_source_draw_with_one_bounded_typed_transient_retry` value. Both attempt
counters are required by the current result parser, including for zero-retry results; the old
semantics value is valid only with an explicit zero retry count and the matching physical count. A
legacy-shaped payload without those counters is rejected by the current DTO instead of being
normalized to zero retries. There is no in-repository persisted reader for this DTO. A future
compatibility reader, if required, must be explicitly named and return a limited result with
physical-attempt provenance `not_established`; it must not return a current
`PosteriorPushforwardResult` or infer one-call history from the old literal. `profile_version` remains
1.1 because it names the source posterior-summary profile, not this output DTO schema.

The Bayesian HMC producer currently emits draw rows without explicit weights or parameter units.
The candidate therefore reports `source_weights=None`, `unit_binding_status="not_established"`,
and `gate_eligible=False`. It is not coerced into the existing `UncertaintyEnvelope` schema and does
not enter default envelope dispatch, calibration admission, or causal-effect evaluation. A bounded
real NumPy HMC → persisted method evidence → persisted summary → fresh summary reader → Monte Carlo
consumer path (one chain, 32 warmup steps, 32 retained draws) is exercised in
[`tests/integration/foundry/uncertainty/test_posterior_summary_persistence.py`](../../../../tests/integration/foundry/uncertainty/test_posterior_summary_persistence.py).

The legacy calibration adapter now carries each representable single-parameter posterior in the
existing `PosteriorSamplesCarrier`. A persisted envelope is fresh-read before the legacy Monte
Carlo consumer samples its exact values; because these caller-supplied draws have no source-bound
law ref, the resulting envelope remains non-gating. The adapter also retains the complete
caller-provided row matrix in a typed candidate context when parameter columns have equal lengths.
That context records the positional rows without establishing their joint-sampling relation. The
legacy consumer refuses these multi-parameter carriers when no shared identity is supplied. A
caller-provided `joint_sample_id` remains a declaration in the generic legacy consumer, not a
content-bound proof of row law; this older path is not used by the source-bound v1.1 candidate.

When a legacy posterior mean lies outside its equal-tail interval, the adapter preserves the mean,
interval, and draws in its returned summary, omits the incompatible `UncertaintyEnvelope`, and
returns the typed `point_outside_credible_interval` limitation. The existing envelope validator
still enforces point-in-interval for representable envelope artifacts; no clipping or median
substitution is applied.

## Current State

- Last updated: 2026-10-10
- Files: 13 Python files in this package
- Exports: 18 names declared in `__all__`
