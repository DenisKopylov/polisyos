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

Precision-weighted and Bayesian aggregation require a resolved relation basis before they can
narrow distinct inputs. In-memory IDs, composition labels, and metadata such as
`dependency="independent"` or `independence=true` cannot establish source identity or statistical
independence; those inputs retain a conservative non-gating hull and an unestablished
effective-information count. The artifact-aware selected-view API verifies kind, media, schema,
content bytes, and the exact manifest profile before collapsing a repeated CAS view. Equal bytes
under distinct selected profiles remain distinct views. The selected-view API does not establish a
common estimand, subject, unit, or dependence law, so distinct views remain non-gating.

## Artifact-aware selected-view aggregation

Both public entrypoints share one input-context admission before arithmetic or selected-view
deduplication. Conflicting overlapping explicit metadata (including currency, unit, subject, and
estimand context), malformed context values, or unequal typed `NumericPolicySpec` values refuse.
Matching context labels are only a consistency check; they do not establish a common estimand,
subject, unit, or dependence law. The exact compatible numeric policy is preserved through widest,
precision-weighted, and Bayesian result construction. Caller-authored origin IDs and relation labels
still cannot authorize deduplication or statistical narrowing.

`aggregate_persisted_envelope_views()` accepts only the existing typed
`UncertaintyEnvelopeRef`. It resolves the selected manifest profile, verifies the JSON kind/schema
and content-addressed bytes, admits context across every loaded source before deduplicating only a
repeated `(artifact_id, kind, media_type, manifest_profile_sha256)` view. The persisted and fresh-read
helpers preserve ordered source InputRef edges and recompute the result on read. Equal payload bytes
with different selected profiles remain different views. Missing or partial context stays
`not_established`; distinct unresolved views produce a declared conditional candidate-only hull and
cannot gate downstream decisions. No output is promoted to authority-grade evidence.

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

## Numerical input admission

Empirical coordinates and weights must be finite real values that retain their
numeric support in the float64 consumer representation. Raw copied carriers
cannot discard complex parts, parse numeric strings or round away integer,
extended-precision or rational support. The existing common input
preparation refuses these laws before evaluating the response function.

Covariance construction validates marginal variances in float64 before choosing
the existing float32 storage profile. Overflow and nonzero storage underflow
refuse. On the actual JAX CPU device, nonzero subnormal covariance operands also
refuse because arithmetic flushes them even when storage retains their bits;
that CPU restriction is not imposed on another selected device. Delta admits
this covariance before its nominal callback. Exact zero variance remains a
point mass in random, Sobol and Halton sampling rather than receiving an
artificial minimum spread.

These checks preserve numerical input laws; they do not establish a source
population, dependence provenance, calibration or downstream authority.

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
| `aggregate_envelopes()`         | Conservatively combines in-memory envelopes without trusting identity labels. |
| `aggregate_persisted_envelope_views()` | Resolves exact selected CAS views and returns a conservative aggregate. |
| `persist_aggregated_envelope()` | Persists an aggregate with ordered selected source-view edges. |
| `load_aggregated_envelope_fresh()` | Fresh-reads and recomputes an aggregate from its exact source-view edges. |
| `compute_first_order_indices()` | Sensitivity helper for variance attribution.              |
| `extract_std()`                 | Extracts scale from a typed parametric fit or legacy interval. |
| Covariance reconciliation constants and builders | Lazy exact-owner exports for covariance construction, reconciliation, and singular-matrix handling. |
| `EvaluationFailureClassification` and classifier | Bounded exception-graph classification and existing node/edge limits. |

## Envelope aggregation boundaries

The Foundry owner uses one versioned internal `AggregationSemanticContextV1` projection before
both in-memory arithmetic and selected-CAS view deduplication. It validates only the established
legacy `unit`, `currency`, `subject`, and `estimand` string axes plus the envelope's typed
`NumericPolicySpec`. Those supplied values are checked for malformed or conflicting declarations;
matching values remain caller claims and do not establish a common estimand, unit binding, subject,
or statistical relation. Unrecognized metadata, including Monte Carlo seeds, sampling methods,
tail-risk summaries, and sensitivity diagnostics, remains attached to each source envelope and is
not compared as shared context.

Distinct views with unresolved relations remain a non-gating outer hull with effective information
`not_established`. Repeating one exact selected CAS view reuses its existing envelope and preserves
its point, bounds, confidence level, interval semantics, and gate flag. The selected-view APIs have
controlled producer-to-CAS-to-fresh-reader tests, but no current production orchestration caller
invokes the aggregate API; that bridge remains `bridge_missing` until a real consumer route is owned.
No HTTP or dashboard publication is claimed.

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

- Last updated: 2026-10-20
- Files: 13 Python files in this package
- Exports: 30 names declared in `__all__`


### Source-derived posterior consumption

The explicit profile-1.1 posterior path recomputes a detached source snapshot
before executing any evaluator and consumes only its source-derived numerical
point and rows. Equality of a caller's shallow-frozen DTO is not a value source.
The public joint-row reader uses the same source admission. Complete source
bytes are frozen once, and the same bytes are hashed and decoded; later caller
mutations cannot change an admitted invocation. Unknown source-format fields
now refuse this unweighted typed law profile instead of being ignored as
unweighted data; generic artifact inspection is unchanged. This is candidate
computation, not source validity, mixing, calibration or policy authority.

Selected evidence provenance has a separate boundary. The fresh
`load_persisted_posterior_summary` adapter resolves the actual store/ref and
requested evidence view (the explicitly selected profile when supplied, otherwise
the default view), the corresponding result edge and credible-mass diagnostic
**at read time**.
The standalone Monte Carlo API has no store; its copied
`source_method_evidence_ref`/profile and linkage of credible mass to that evidence
remain `consumer_asserted` for a direct input or one mutated after that read.
Numerical source reconstruction does not independently verify those linkages.

The remaining provenance boundary is assigned to the existing S3 selected-store/ref
reader-to-consumer wrapper route, using an independently selected ref/context. Its
concrete falsifiers are UNRUN: change an already-read model's well-formed evidence
ref/profile before consumption; or change credible mass from 0.9 to 0.8 for source rows
`(0, 1, 2, 3)`, whose finite bounds remain `[0,3]`, without changing the selected
evidence diagnostic. The wrapper must refuse or re-resolve those changes before
any effect and consume only that independently revalidated selection. This route
has not established S3/B31, E-M1, G acceptance or closure.


### One prepared legacy numerical invocation

Legacy MC and dispatcher now share a private preparation built by the existing
empirical and Gaussian law owners. Unknown, incompatible or unsupported sampling
laws return their existing typed refusal before an irrelevant evaluator binding.
An executable law still binds complete effective inputs before any evaluator call
or evaluator-driven automatic delta probe. Explicit delta/analytical moment routes
keep their existing mixed-family covariance semantics.

The preparation captures the nominal mapping associations, output IDs, route
weights, numerical carrier/fit data and load-bearing input/provenance meanings.
The actual dependency string interpretation is resolved at preparation, including
custom Enum strings; it is not replaced by an Enum's wire value. Every numerical
consumer and finalizer uses that same interpretation. The private views carry
owner-resolved categorical predicates, not replicas of
the original source payload; the separate original digest retains wire identity.
Fixed Fraction, Decimal and other existing supported scalar arguments keep their
callback-visible type/value;
there is no new global `Real` precheck or silent float coercion of fixed arguments.
Analytical weights are resolved through that owner's existing `float(weight)`
interpretation before signature effects; invalid values keep the existing
post-binding analytical-to-delta fallback. Unconsumed MC weights are not resolved.
Covariance-only metadata conversions/errors are consumed only on moment routes;
an ordinary MC fallback keeps the prior ability to ignore unused std metadata.

Arbitrary mutable fixed objects retain their legacy borrowed callback behavior.
They are not represented as owned numerical scalar data. More generally, the
schema-1.0 sampling recipe does not bind *any* fixed invocation value, so a
fixed argument keeps `input_identity_status="not_established"` and every
dispatcher backend is non-gating even when the callback-compatible value is an
immutable scalar. No undeclared ledger field is emitted. This qualification is
not source authenticity, scientific validity or policy authority.

When the prepared Gaussian joint sampler actually runs, its draw ledger 1.1
records the ordered input names and the assumption of a multivariate normal
law with the declared covariance. The assumption is non-authoritative: input
source, joint-law provenance and parameter units are not established by these
fields. A fallback envelope with insufficient valid draws retains that same
limitation and the attempted sampling assumption. Other sampling routes do not
invent a Gaussian declaration. The Science report carrying that ledger uses
version 1.2; its version 1.1 reader remains available for historical reports
and does not infer the absent assumption. Readers must support 1.2 before the
new producer is deployed. The recipe records input envelope hashes, the actual
mean and factor rows, validation tolerances, library versions, and per-batch
backend, device, dtype and seed context. It also records the QMC uniform clip
when used. The rows make the declared transform reconstructible in the recorded
environment; they do not verify source authenticity or successful-draw identity,
or promise identical results on a different numerical stack. JAX draw precision
depends on its runtime profile, while the output summary uses float32.

Original envelope JSON identity is captured separately, before callbacks, as the
existing digest or `None`. Metadata is copied before interpretation through a
closed, exact JSON-value domain: string-keyed dictionaries, lists, primitive
strings, numbers, booleans and null. The owned snapshot must match metadata in
the exact original digest serialization. Behavioral values, tuples, container
subclasses, enums, datetimes and opaque sidecars are retained for candidate
computation where supported, but do not establish context identity or a gate;
results disclose `metadata_context_status="not_established"`. This conservative
qualification also covers inert extensions and future metadata consumers without
assuming that a serializable custom object has the same meaning as its JSON wire.
The existing dependency owner still consumes its established `str(raw)` meaning;
the cap prevents a divergent Enum wire value from authorizing it. The preparation walks
the actual `CompositionProvenance` and `CompositionStep` fields, recursively
owning exact built-in lists, tuples and string-keyed dictionaries and exact
primitive values. Exact datetimes retain their Python type; an aware datetime's
wire offset is fixed without retaining the caller's timezone object. The three
IR composition enum classes are trusted as product-defined constants. Other
values (including arbitrary Enum values, container subclasses and datetime.time)
are borrowed, not silently coerced: all actual routes set
`provenance_context_status="not_established"`, make invocation identity
`not_established`, and return non-gating results. Existing non-gating results
also disclose the limitation. The output omits unowned inherited provenance
history and origin IDs, records `input_provenance_history="withheld_unowned"`,
and retains its own producer step and source references. This permits a truthful
canonical persistence without serializing borrowed behavior as authority. A
comparison with the provenance embedded in the
original digest catches changes while the view is being prepared. Unsupported
cycles or values that the existing model cannot serialize or validate may still
refuse rather than produce a result; neither path grants authority.

Owned nested containers are separate from caller inputs, but remain mutable to a
recipient of the output itself. This boundary assumes ordinary product enum class
definitions and no process-wide monkeypatching. It does not freeze consumer-held
outputs or provide an atomic snapshot under concurrent mutation; persist and
revalidate as required by the consuming authority boundary.

This is numerical-data ownership, not a generic Python graph copier or a sandbox.
Callable defaults/closures, external world state, private owner mutation and
simultaneous caller mutation during preparation remain execution boundaries.
There is no new wire schema, public method, carrier, CAN.3 dependency, issuer or
source-quality/authority claim. The separate profile-1.1 posterior-summary route,
its selected-read versus standalone provenance limits, historical E profile 1.0,
S3/B31, E-M1 and G acceptance retain their existing boundaries.

The accompanying refusal, mutation, sidecar, scalar and consumer tests are source
companions. Runtime and semantic removal evidence must be bound to the composed
source and actual profile; the older C90 Cloud source mismatch and incomplete
removal witnesses do not qualify this preparation.
