# Simulation nodes

`RunSimulationNode` executes the configured Foundry request through the existing
Foundry port. Normal simulation keeps its configured execution settings.

For an admitted internal backtest native request, the node binds the requested
integer replay seed into `FoundryExecConfig` and executes the declared future
steps through the same port and CAS. Its typed predictive trajectory reads
registered state slots from actual post-execution snapshots, with explicit
units, target, times and horizon. It does not treat metrics counters, effects or
uncertainty summaries as future observations. A native request failure remains
an explicit node failure; there is no forecast fallback at this boundary.

Profile admission, immutable source/Trinity binding, persistence and consumer
readback are owned by the [backtest adapter](../../../methods/backtesting/README.md).
These predictive results do not grant causal or policy authority.

`PropagateWelfareNode` admits supported uncertainty laws before evaluating the
nominal response or drawing inputs. A one-parameter `PosteriorSamplesCarrier`
uses its existing ordered atoms and weights through the shared finite-machine
CDF admission. Its CAS receipt binds each drawn row to the original carrier;
unsupported carriers fail with typed unknown, non-gating law status. Empirical
joint inputs still require an admitted joint law and are not made independent.

The native GE evaluator preserves every requested draw outcome, including a
singular `I-A`. Successful outputs remain available as conditional diagnostics,
while an incomplete support withholds the unconditional credible interval.
This numerical diagnostic does not establish a served evaluator, production
source law, retry profile or causal authority.
