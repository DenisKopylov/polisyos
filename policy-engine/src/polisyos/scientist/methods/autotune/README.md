# Autotune MethodJob evaluation

`MethodJobBenchmarkEvaluator` connects `SearchLoopRunner` to the canonical
Foundry MethodJob runner. Configure a method FQN, a mapping from method input
slots to candidate fields, and a `PromotionPolicy`. Each evaluation runs the
method against the persisted candidate and suite refs, then stores the method
result and execution evidence refs in the `BenchmarkEvaluation` lineage.

The evaluator admits only the configured primary metric. If the policy declares
a unit, the method output must return the same unit in `metric_units`. Missing,
non-finite, boolean, or unit-mismatched values remain unavailable; the search
objective does not replace them with zero. Sample counts and guardrails affect
promotion only when the method itself returns those fields. MethodJob execution
evidence proves execution reproducibility, not governance admissibility or
method validity.

`BayesianSourceProfile` records the actual optimizer class and configuration,
proposal source, search-space fingerprint, the caller context frozen at
`SearchLoopRunner` entry, objective identity, effective fitted training corpus,
and effective model profile. Transform-family fields describe the configured
normalization/standardization/likelihood semantics; separate state fingerprints
bind the actual learned normalization bounds, outcome statistics, and likelihood
noise. The native optimizer and injected optimizers have distinct profile kinds.
A profile is warm-start eligible only after a successful native GP acquisition
with an observed fitted basis, supported transform families, captured transform
and noise states, and a nonempty corpus bound to the actual fitted input and
target matrices. Same-run history only needs to match its immutable space,
context, objective, and configured native optimizer header so cold Sobol rows
can reach the first fit. External warm history must pass the full fitted-profile
gate against the receiving context, objective, and search space. An initial
Sobol proposal does not qualify as fitted GP history. Missing optimizer
introspection leaves the corpus unknown rather than substituting the input
history.

The transfer bridge persists search histories through CAS and reads canonical
numeric values back into typed records. Warm-start history remains candidate
evidence; it does not establish an external source's authority or eligibility.

An opt-in diagnostic MethodJob can bind method slots directly from a persisted
`fabric.data_snapshot` and its source data artifact. The causal DR/R bootstrap
loop can emit `BootstrapExecutionWork` only when capture is enabled; the
MethodJob observer checks those loop counts against its fresh-read result,
effective draw configuration, source sample, result/evidence refs, and MethodJob
key before persisting a diagnostic-only packet. The search runner reads that
packet again, binds it to the candidate/evaluation/attempt, and carries its ref
in the benchmark evaluation. This is candidate-grade engineering observation;
it does not admit a policy-effect mapping or alter promotion authority.

The packet reader also verifies what the method actually received. Execution
evidence records every dispatched input's full `ArtifactRef` selector and
selected manifest schema, plus a canonical dtype, shape, and content fingerprint
for each method-state slot. A fresh reader rebuilds those slot values from the
persisted candidate and DataSnapshot sources and rejects changed values even
when their row counts match. It also checks that packet, result, evidence, and
source-manifest lineage retains selected manifest profiles. The work packet is
schema 1.2; prior 1.1 diagnostic packets lack this dispatch binding and are not
admitted by the stricter reader.

The default policy-runtime L3/L4 backend still does not execute that causal
MethodJob or a scientific draw loop. Its invocation packet remains separate
from bootstrap counts and its fixed CI proxy remains non-authoritative. The
controlled direct-L4 versus L3→L4 witness runs the actual bootstrap loop over
the same bound source, but patches the nuisance and tau fit layers. An
env-gated native witness is prepared: it runs direct L4 (80 draws) and L3→L4
(40 then 80 draws) through the real estimator, MethodJob, and CAS path, then
compares the same-source full-L4 result/config/profile and fresh-read counts.
That native fit remains unrun pending the serialized numerical slot. B157
therefore remains held for the default policy-runtime consumer and native-fit
confirmation. No count is inferred from requested configuration or from the
fixed CI proxy.

This runtime path does not establish B108 fiscal source law. It requires an
exact metric name and, when configured, an exact unit; owner-declared aliases,
sign, measurement time, and conflict policy still need the real fiscal source.
See the local
[V5 search receipt](../../../../../docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/v5-search/receipt.md)
for the selected criteria, tests, and remaining producer boundary.
