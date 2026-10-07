# Search checkpoint profile compatibility

Owner: `team-policyos-runtime`.

The search checkpoint and Pareto child modules are internal under the current
public-surface contract. Their persisted profiles still require explicit consumer
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
