# Structural causal models and query intervals

`causal.structural.gcm_fit@1.0.0` selects the pinned DoWhy GCM worker by default.
The Python 3.14 application invokes the Python 3.12 / DoWhy 0.14 worker inside its
existing Foundry method job. The parent owns CAS and validates the source bytes,
aligned rows, graph, request, installed versions, worker code and lock identity.
The worker constructs a `StructuralCausalModel`, assigns the declared mechanisms,
and calls `dowhy.gcm.fit`. It exports empirical root samples and fitted linear
coefficients, intercepts and actual residual samples as JSON.

This selected profile supports a fully observed, declared static DAG with
empirical roots and linear additive-noise conditionals. It does not claim
automatic graph or mechanism assignment. An unavailable worker, unbound source,
unsupported graph or literature-prior fit returns a failure. Direct research
callers can explicitly request `fit_backend="native_hybrid"`; this separate
native profile makes no DoWhy fit claim. Python 3.14 dependency markers excluding
DoWhy/EconML do not establish backend success.

## Persisted model and source custody

Selected GCM outputs use `StructuralCausalModelSpec` schema 1.1. `SCMTrainingRows`
retains the original complete fit input and source artifact reference, matrix,
column order, row identities and content hashes. `SCMFitProvenance` retains the
observed worker reply and the parent request/code/lock binding. Root carriers
share the same aligned source rows. Fresh Scientist readers resolve the actual
source artifact and rederive the consumed mechanisms from that fitted reply;
matching provenance strings alone cannot admit different values or coefficients.

Historical/manual schema 1.0 remains readable. Its historical `fit_method="gcm"`
label supplies no new backend witness or gating authority. Static consumers
refuse lagged graphs until a temporal method or explicit expansion is supplied.

## Distribution, posterior and estimator inference

Causal query result schema 1.2 and twin result schema 1.1 carry an explicit
`result_kind`. Their historical `result_ci` and `ite_ci` fields are central
quantile spans of fixed-model draws:

- `outcome_distribution` describes simulated outcomes under the fitted model.
- `ite_distribution` describes paired potential-outcome differences with shared
  structural noise.
- `posterior_credible_interval` describes a supported conditional Gaussian model
  posterior after factual abduction.

Increasing the number of fixed-fit draws does not create an estimator confidence
interval. Exact Gaussian abduction conditions the joint structural noise mean
and covariance, including compatible singular systems. Incompatible singular
factual evidence is refused. Empirical fitted residual laws are not relabeled as
Gaussian posteriors; unsupported partial evidence remains explicitly limited.

The current shared uncertainty schema represents ordinary distribution spans as
non-gating heuristic ranges and model posterior spans as non-gating credible
intervals. These local causal wire versions do not ratify a new global uncertainty
contract. Historical causal schemas 1.0/1.1 and twin schema 1.0 decode as limited
non-gating distributions; historical CI or eligibility markers are not renewed.

## Optional iid row bootstrap with complete refits

Set the source fit input's `metadata.sampling_unit` to `iid_observation_row` only
when that sampling law describes the admitted basis. Request
`params.causal_estimator_bootstrap_replicates` on `RunCausalQueriesNode`, or
`bootstrap_replicates` on the causal method. The supported range is 20–500
replicates, subject to the worker's message and timeout bounds.

The method resamples complete rows with replacement, constructs and genuinely
fits a fresh GCM for every replicate, and evaluates the same atomic intervention
mean or target/comparator contrast on each refit. It preserves the original graph
and declared mechanism families. Conditional individual counterfactual estimands,
non-iid units and other mechanism profiles do not receive this interval.

The optional `CausalEstimatorInterval` is separate from the outcome/ITE summary.
It records the iid unit, source/row/graph/target and resampling hashes, seed,
replicate count and estimates, refit scope and actual fitted worker reply. Fresh
consumers reconcile its complete refit outputs against the resolved source and
recompute the reported interval. Its percentile interval describes approximate
sampling inference conditional on the fixed identified graph and declared iid
law; a finite synthetic example does not prove nominal population coverage.
Its separate uncertainty projection remains non-gating until causal graph,
sampling law and domain authority are independently admitted.

## Supported static intervention laws

The sampler supports `Normal(mean, std)`, `Uniform(lo, hi)` and
`TruncNorm(mean, std, lo, hi)`. Unknown laws and nonpositive normal scales are
refused. Truncated-normal draws use the normalized conditional law, including
extreme tails, rather than clipping ordinary normal draws to endpoints. Perfect
interventions replace the treatment mechanism and cut its incoming causes;
unrelated graph nodes and node ordering do not change logical random streams.
These checks establish the declared finite synthetic model behavior, not causal
identification or authority on real data.
