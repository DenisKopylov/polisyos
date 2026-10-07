# Search checkpoint profile compatibility

Owner: `team-policyos-runtime`.

The search checkpoint and Pareto child modules are internal under the current
public-surface contract. The existing `NativeSearchService`, `SearchServiceCheckpoint`
and `SearchLoopRunner` aliases at `polisyos.scientist` are stable public exports.
Their persisted profiles still require explicit consumer
action when a version or numerical basis is unsupported. These instructions do
not appoint an evidence issuer or authorize production observations.

## Restore and refusal

Use the existing `StrategyState` artifact codec and the receiving strategy's
`set_state` entry point. The current GP continuation profile requires
`gp_state_version=4`, the saved fitted model and transforms, original fitted
evaluation payloads with ordered IDs and raw X/Y, complete warm-row content,
numerical target and supported backend fingerprint. Restore re-admits transferred
fitted and warm rows through the configured CAS reader and checks their numeric
association before constructing the model. The initial published GP26 witness
measured the historical profile 3; it does not establish profile 4 execution.
Profiles 1 through 3 are refused by the current receiver. RL continuation requires its supported
wrapper version, `linear_decay.v1` schedule and nested base state. Incomplete older
profiles are refused; there is no lossless automatic migration for missing fitted
parameters or RNG state.

Retain the original artifact and the complete refusal. If exact continuation is
required, use the originally recorded supported implementation and backend. If
starting a new search is acceptable, create a fresh run and re-admit any retained
observations through the existing configured numerical basis or CAS admission
reader. Treat that operation as a new run, not a continuation or a recovered RNG
stream. Do not edit version, basis or backend markers to force restoration.

The internal generator wrapper `bayesian_candidate_generator.v2` also retains
indexed converted current-history rows and their full transfer references.
Historical wrapper v1 lacks that custody and is refused. Configure the paired
transfer bridge and target before activity, retain the converted history prefix,
and use its ordinary `get_state`/`set_state` boundary. A local digest or a fitted
row ID without the matching original numeric row does not supply source custody.

Pareto readers accept declared front/snapshot versions `1.0` and `2.0`; unknown
versions refuse. Version `2.0` carries explicit input assessment and nullable
hypervolume with its unavailable assessment. Consumers must distinguish a
computed zero from an unavailable indicator, preserve coordinate IDs/schema and
retain unassessed rows. Historical finite `1.0` reads remain supported; do not
erase a version `2.0` assessment to serialize it as historical `1.0`.

## Native service and sequential proposals

`SequenceCandidateGenerator` implements the scalar candidate contract and
requires a nonempty corpus. An empty corpus refuses with
`sequence_generator_requires_nonempty_corpus` before native service activation.
Removing a live corpus also refuses at the scalar generation boundary; it never
invents a subject or uses `IndexError` as an exhaustion signal. Nonempty streams
retain one proposal per scalar ask and their repeated terminal proposal.

An empty sequence is an unsupported configuration, not a successful exhausted
search. The existing batch-generator contract remains the supported empty-result
path: the native service records bounded empty attempts and truthful partial or
`generation_exhausted` state. Unit-batch/scalar routing is unchanged.

Topology selection dependencies load when the existing topology-suggestion
consumer activates. Ordinary scalar proposals do not initialize the selection
advisor. If selection is unavailable at that boundary, generation keeps the
existing `execution_plan_context_unavailable` degraded result; this does not
establish a successful topology suggestion.

Native `search-service.v2` replay binds the factory build and evaluator/model
profile. Retain old artifacts; changed factory builds refuse old checkpoints.
For exact continuation use the recorded source and its admitted profile, or
start an explicitly new run. The nonempty sequence corpus/cursor wire format
stays `sequence-generator.v1`; markers do not authorize cross-build resume.

## Base sampler checkpoint numeric fields

Cached Sobol coordinates require finite, float-representable values in `[0, 1]`.
The Python Gaussian cache accepts a finite, float-representable numeric value or
`null`. Boolean and string values refuse at their existing typed boundaries.
An unrepresentable integer refuses with a controlled `ValueError`; it does not
escape as `OverflowError` or become zero. These Base sampler fields and the
effective sampler validate before the Base live RNG, iteration or cursor changes.

The existing Python/Sobol codec versions and valid finite state remain supported.
The Gaussian cache retains its admitted integer/float representation; this
change widens refusal for unsupported state without silently migrating it.
Retain the refused artifact for diagnosis and restore a supported checkpoint.

## Grid continuation profile

Grid continuation requires `grid_state_version=1`, the original search-space
basis, `points_per_dim`, `max_candidates`, actual grid size and a strict integer
cursor from zero through that size. A cursor equal to the size restores an
exhausted grid and the next scalar request keeps `StrategyExhaustedError`.
Boolean, fractional, string, negative, missing and out-of-range cursors refuse;
changed grid density or cutoff refuses instead of silently selecting a different
next subject. Grid admission completes before Base RNG or iteration changes.

A Grid batch request returns the actual remaining subjects when fewer than the
requested count remain, then returns an empty batch at exhaustion. It does not
advance and discard the last subject by asking past the finite grid. A zero
integer count retains the existing empty/no-advance behavior; Boolean, negative,
fractional, string and missing counts refuse. Scalar exhaustion continues to
raise `StrategyExhaustedError`; other strategies and scalar acquisition routing
keep their existing policies.

Historical unversioned Grid checkpoints lack the cutoff/profile binding. They
are refused by this receiver. Retain the original artifact and use its recorded
implementation for exact continuation, or start an explicitly new grid run with
the owner-selected configuration. Do not fill in missing fields or change
markers to force a resume. Supported profile 1 uses the existing
`strategy_state.v2` artifact; no new storage or optimizer is introduced.

## Embedding convergence measurement profiles

`ConvergenceDetector.check_with_text` requires an explicitly declared nonblank
string model identity and revision before admitting an embedding measurement.
`model_id` and `model_version` are the primary fields; `model_name` and `version`
are supported aliases when their primary fields are absent. A malformed-present
primary field refuses instead of falling back to its alias. `unknown`, blank
values, nonstrings and implicit class names cannot establish this basis. Opaque
owner revisions remain supported; no semantic-version format is imposed.

The measured vector must have a positive dimension and finite, float-representable
real coordinates. Integer, float and NumPy real scalars remain supported; Boolean,
string, nonfinite and overflowing coordinates are unavailable measurements. The
existing common numeric admission boundary validates the whole vector before a
measurement is recorded.

Only two adjacent current measurements with matching declared identity/revision
and vector dimension can contribute embedding similarity. Missing provenance, an
empty vector or a refused coordinate records
`text_embedding_unavailable`; prior vectors cannot stand in for that failed
measurement. Recovery requires two fresh supported measurements.

Previously anonymous or unversioned embedders are an unsupported measurement
profile. Their owner must supply the actual identity/revision before enabling
semantic convergence; a default revision or module/class name is not a migration.
Numeric convergence and configured hard-stop reasons retain their existing
behavior. Deterministic fixture profiles prove the bounded cosine/freshness
mechanism and do not validate a scientific embedding model or threshold.

## Multi-objective continuation profile

`MOBayesianOptimizer` requires `mo_state_version=1`. The supported numerical
profile `mo.single_task_gp.cpu.refit_each_ask.v1` records the exact installed
Torch/BoTorch/GPyTorch versions and Torch runtime flavor, objective names and
directions, configuration, search-space identity, original seed, reference,
raw direction-normalized training corpus and fitted-model content bindings.
The reference must agree with the existing configured or fitted-corpus policy.

Restore recreates the existing `ModelListGP` of `SingleTaskGP` components and
loads their fitted mean/kernel/likelihood/noise parameters and ordinary
`Normalize` / corpus-derived `Standardize` buffers. It reconciles the actual
training coordinates and transformed targets without MLL fitting. The next
normal ask retains the existing MO policy of one fit per ask; this is distinct
from the single-objective optimizer's same-basis conditioning profile.

The existing `strategy_state.v2` artifact and optimizer signatures stay in use.
Slots configuration now serializes through its dataclass fields. Incomplete,
unversioned, unknown or foreign MO state refuses before Base RNG, iteration,
corpus or fitted model changes. Retain the original artifact and use the
recorded supported implementation/backend for exact continuation, or start an
explicitly new run from the original evaluated inputs. Do not add or edit
markers to manufacture a compatible continuation.

The actual backend-absent profile `mo.random_or_sobol.no_botorch.v1` can retain
its baseline state; it is not a fitted numerical checkpoint and cannot silently
cross into the numerical profile. Numerical verification remains `UNRUN` when
the optional backend is missing. Non-CPU checkpoint export/import refuses
explicitly; no GPU, custom-transform or cross-version equivalence is established.
Sequential CPU calls preserve the ambient Torch stream and separately seeded
replicas; process-global `fork_rng` does not establish concurrent-thread isolation.

The defining witness is
`tests/unit/scientist/methods/search/strategies/test_mo_checkpoint.py`: actual
CAS/fresh reader, eight distinct synthetic utility/cost measurements, independent
NumPy mean and full covariance for both fitted components, restored next EHVI,
fit cadence and marker-preserving corruption controls. These are bounded
numerical fixtures, not production evaluation history or source/tenant authority.

## Persisted JSON numeric tokens

Native service checkpoints and nested `strategy_state.v2` artifacts share one
internal JSON float-token admission rule. Actual `0`, `0.0` and `-0.0` retain
zero; representable finite floats retain their ordinary float values. A nonzero
wire token such as `1e-1000` or `-1e-1000` refuses before conversion can make it
zero. Overflow, nonfinite JSON constants and exponents outside the supported
Decimal token range produce a controlled `ValueError` before live restoration.
Integer and Boolean tokens retain their types for the existing schema validators.

The generic JSON/LLM parsers keep their own contracts; this rule is limited to
persisted search checkpoints. No state markers, inner JSON strings or schema
labels authorize normalization of an unsupported value. Keep original bytes and
refusal output; this receiver does not repair or manufacture the lost lexeme of
an already normalized historical artifact.

## Native StrategyAdapter continuation

`strategy_adapter.v1` wraps the existing `StrategyState` artifact for the
canonical `SearchSpace`, exact `ScalarParameterCodec` and default
`SearchIteration.objective_details` extractor. It binds codec configuration,
strategy type/configuration, implementation content, space and the complete
synchronized evaluation-history prefix. Each numerical strategy still owns its
supported backend/model/RNG admission; the adapter does not create a posterior
or replace that owner's checkpoint law.

Fresh service restoration validates the actual persisted history prefix before
restoring live strategy or run state. The next ordinary generate rebuilds the
adapter cache from that prefix without repeating previously applied strategy
updates, then applies only new evaluations. Existing scalar versus batch
acquisition routing stays in use. The actual native factory projects the existing
technical proposal envelope into its strict mutation codec and retains the
proposal identity in native history/checkpoint state.

Custom codecs or objective callbacks, noncanonical spaces, generators without
an underlying state API and implementations without an available source file
remain usable by their existing live-only callers. Their adapter state discovery
returns `None`, and persisted public resume explicitly refuses that unsupported
profile. A module/class label or a callback digest alone does not supply the
custom context contract. Historical adapter checkpoints with `generator_state`
missing or null cannot be silently reconstructed; retain the artifact and use
its recorded supported implementation, or start an explicitly new run with the
owner-selected context and original evaluated inputs.

## Budget admission and unavailable recorded spend

A configured search budget owner admits the declared budget key through its
existing `pre_check` API before proposal or recorded-state consumption. Pending
canonical settlement and owner failures remain unavailable and produce no next
proposal. Known exhaustion retains the owner's known recorded spend. A successful
admission of an initialized owner with no events retains genuine recorded zero.
A trace cost or estimate does not substitute for the owner's durable transition.

The run-owned unavailable amount is `budget_spent=None`, with an empty budget
snapshot, `budget_available=false` and an explicit unavailable reason. New owner
evidence may carry `admission` as exactly `admitted`, `exhausted` or `unavailable`.
An unavailable admission cannot carry a numeric amount, snapshot, provider
aggregate or claimed spend-key presence. Existing finite recorded checkpoints
without this additive evidence field remain readable; malformed-present evidence
and contradictory zero/available markers refuse on fresh checkpoint readback.

Older strict readers may reject nullable spend or the new evidence field. Retain
the original artifact and use its recorded reader/build and matching canonical
budget owner, or start an explicitly new run after resolving the actual owner
obligation. Do not change `None` to zero, drop admission evidence or edit build
markers to force continuation. B owns the ledger schema/version and any ledger
migration. D does not assign a second ledger schema. Admission and snapshot are
separate existing owner calls; their local fence does not promise an atomic
concurrent read pair or distributed settlement.

## Operator checks

Before restoration, record the source SHA, checkpoint profile and actual backend
versions. Keep the original artifact immutable and restore into a fresh strategy.
On refusal, keep the existing consumer state unchanged and choose the explicit
supported continuation or fresh-run path above. On a supported restore, verify
the next proposal and persisted readback under that exact profile.

The numerical witness is
`tests/unit/scientist/methods/search/strategies/test_gp_analytic_continuation.py`;
the actual CAS-to-GP consumer is
`tests/unit/scientist/methods/autotune/test_transfer_workflow.py`. The published
GP26 receipt records their executed supported profile. Missing optional numerical
backends mean `UNRUN`, not a successful numerical verification. The checkpoint
tests and `tests/unit/scientist/methods/search/test_hypervolume_limitations.py`
cover refusal and nullable-indicator readers. These are verification recipes,
not a claim that every recipe was rerun by this documentation change.

The supported acquisition policy `sobol_ranked_restarts.v1` changes restart
selection. Replay requires its recorded local RNG and policy; ambient process RNG
or a seed-only reconstruction does not substitute for the saved stream.

## Configured canonical owner in the public runner

`SearchLoopRunner` accepts optional constructor keywords `budget_middleware`,
`budget_key="run"` and `cost_budget_usd=None`. Supply the actual canonical
`BudgetMiddleware` owner selected by the caller. A declared cost limit requires
that owner and the existing finite, strictly positive `CostBudgetStopping` USD
law; booleans, nonfinite values, underflow and unrepresentable amounts refuse.
A key must be a nonblank string. The runner passes this same configuration into
`run`, `create_service` and fresh public `resume`; callers do not modify private
controller configuration to install the owner. Defaults without an owner remain
the previous iteration-limited profile. A declared cost rule is combined with
`MaxIterations` using the existing OR stopping contract.

The `create_service` return annotation now names its existing `NativeSearchService`
class instead of `Any`; the returned class and factory defaults are unchanged.
Configured sensitivity must retain the exact resolved analysis reference, and
artifact-producing evaluation uses the existing verified-snapshot owner port.

The resource owner admits the declared key before proposals. After a proposal
failure, native rollback restores generator/history/pending ownership, then reads
the current canonical accounting again. An unresolved charge stays unavailable
with `budget_spent=None`; external durable accounting is not rolled back with
local proposals. An exhausted recorded budget retains its known amount. An
admitted literal recorded zero remains available and does not claim a provider
invoice. The original proposal refusal remains the caller's failure. This
preflight and later recheck do not promise atomicity between separate owner
reads and a future producer write.

Retain the exact service checkpoint reference and reopen the original artifact
store with the same actual owner identity, declared key and positive cost limit.
Changed configuration refuses before state admission. New source-bound factory
builds also refuse checkpoints from other builds: use their recorded supported
reader for exact continuation or start a new run after resolving outstanding
work with the canonical owner. The owner retains ledger schema/migration and
completion-resolution authority; this port neither replaces that owner nor
appoints a served production caller.
