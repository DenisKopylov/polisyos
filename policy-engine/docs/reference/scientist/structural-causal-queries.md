# Structural causal query execution and result custody

`RunCausalQueriesNode` resolves `params.structural_causal_model_ref` or the
structural model artifact in the experiment state, validates the requested
`params.causal_query`, and runs the existing
`causal.structural.gcm_query@1.0.0` Foundry method job. The job records its original
SCM reference as an input. Selected source-bound models are reopened and validated
through the public `polisyos.foundry` facade before numerical consumption.
Historical/manual models remain usable for bounded model calculations without
supplying a new backend or policy-authority witness.

## Immutable job result and original request

The node requires a real `method_result_ref`, verifies its CAS identity, method
result schema and original SCM input binding, and opens the complete persisted
method payload. It compares the complete JSON projection of the in-memory job
output with those canonical bytes, including draws, both result aliases,
metadata, envelopes and ancillary outputs. Matching backend or source markers
alone do not establish result custody.

The canonical `causal_query_result` and historical `query_result` aliases must
decode to the same complete typed result. The result's query must match the
original requested query, including its factual condition, treatment,
target/comparator arms and draw count. A coherent job for a different arm is
refused. Missing artifacts, changed peer summaries or draws, divergent aliases
and inconsistent requests return a failed node outcome before result persistence.

The node persists causal query schema 1.2 and derives its uncertainty envelope
from that reconciled typed result. A method's peer envelope cannot independently
change its contrast or gating semantics. Persisted result/envelope input lineage
includes the SCM, actual method result and execution evidence when present.

## Distribution and separate estimator inference

Fixed-fit outcome and paired ITE quantiles describe model distributions. Supported
Gaussian factual abduction produces a conditional model posterior, including
compatible singular evidence. These projections remain non-gating. Increasing
the number of draws does not create an estimator confidence interval.

For a source explicitly declaring `metadata.sampling_unit="iid_observation_row"`,
`params.causal_estimator_bootstrap_replicates` can request 20–500 complete row
resamples and genuine refits through the selected worker, within its message and
timeout bounds. The separate `CausalEstimatorInterval` is validated against the
resolved source, original requested estimand and complete fitted replicate
outputs. It describes approximate iid percentile inference conditional on the
fixed identified graph; it remains non-gating. Conditional individual
counterfactuals and unsupported sampling/mechanism profiles are refused for this
estimator interval.

The selected backend is Python 3.12 / DoWhy 0.14, invoked by the Python 3.14
application. Excluded in-process DoWhy/EconML markers are not positive backend
evidence. Known synthetic DGP and analytic graph controls establish their bounded
properties; real-data identification, graph admission, sampling law and domain
authority require their own evidence. See
[structural causal models](../foundry/structural-causal-models.md) for the supported
model profile and historical wire compatibility.
