# Search checkpoint profile compatibility

Owner: `team-policyos-runtime`.

The search checkpoint and Pareto child modules are internal under the current
public-surface contract. Their persisted profiles still require explicit consumer
action when a version or numerical basis is unsupported. These instructions do
not appoint an evidence issuer or authorize production observations.

## Restore and refusal

Use the existing `StrategyState` artifact codec and the receiving strategy's
`set_state` entry point. GP continuation requires `gp_state_version=3`, the saved
fitted model and transforms, complete warm-row content, corpus identity, numerical
target and supported backend fingerprint. RL continuation requires its supported
wrapper version, `linear_decay.v1` schedule and nested base state. Incomplete older
profiles are refused; there is no lossless automatic migration for missing fitted
parameters or RNG state.

Retain the original artifact and the complete refusal. If exact continuation is
required, use the originally recorded supported implementation and backend. If
starting a new search is acceptable, create a fresh run and re-admit any retained
observations through the existing configured numerical basis or CAS admission
reader. Treat that operation as a new run, not a continuation or a recovered RNG
stream. Do not edit version, basis or backend markers to force restoration.

Pareto readers accept declared front/snapshot versions `1.0` and `2.0`; unknown
versions refuse. Version `2.0` carries explicit input assessment and nullable
hypervolume with its unavailable assessment. Consumers must distinguish a
computed zero from an unavailable indicator, preserve coordinate IDs/schema and
retain unassessed rows. Historical finite `1.0` reads remain supported; do not
erase a version `2.0` assessment to serialize it as historical `1.0`.

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
