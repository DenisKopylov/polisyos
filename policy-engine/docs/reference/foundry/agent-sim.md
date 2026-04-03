# Foundry Agent Sim
Related explanation: [Causal Engine](../../explanation/causal-engine.md).

The agent-simulation wiring layer bridges intervention contracts into runtime
updates over population, firm networks, and distribution-aware policy
mechanisms.

## Public Surface

| API | Role |
|-----|------|
| `FirmLifecycleEventBatch` | Vectorized firm entry/exit/type-transition input |
| `ProcurementShockBatch` | Vectorized procurement shock input |
| `InterventionMechanismConfig` | Normalized mechanism parameters for tax/transfer wiring |
| `ContractsPopulationAwareExecutor` | Population and firm-lifecycle updates |
| `ContractsGraphAwareExecutor` | Procurement shock propagation |
| `ContractsDistributionAwareExecutor` | Combined tax, transfer, population, and graph execution |

## Reference

::: polisyos.foundry.agent_sim.wiring

::: polisyos.foundry.agent_sim.wiring.contracts

::: polisyos.foundry.agent_sim.wiring.executors
