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
