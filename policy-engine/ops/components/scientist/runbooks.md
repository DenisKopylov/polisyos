# Scientist Runbooks

Escalation: `team-scientist` primary; `team-runtime` joins for worker
starvation, and `team-platform` joins for provider or budget incidents.

| Alert or symptom | Runbook |
| --- | --- |
| `SLO_DagSuccessRateBreach`, `SLO_DagSuccessRateCritical` | [Runtime Graceful Shutdown or Stuck Background Worker](../../../docs/runbooks/runtime-graceful-shutdown-and-stuck-worker.md) |
| `SLO_DagLatencyP99High`, `GovernancePassSlowdown`, `ScientistNodeP95LatencyHigh` | [Benchmark Regression Triage](../../../docs/runbooks/benchmark-regression-triage.md) |
| `HighLLMCost`, `HighLLMCostCritical`, `AgentErrorSpike`, `AgentErrorSpikeCritical` | [Runtime Graceful Shutdown or Stuck Background Worker](../../../docs/runbooks/runtime-graceful-shutdown-and-stuck-worker.md) |
| `ScientistWorkflowFailRate`, `ScientistBudgetNearExhaustion`, `ScientistTierQueueDepthHigh`, `ScientistSemaphoreWaitHigh` | [Runtime Graceful Shutdown or Stuck Background Worker](../../../docs/runbooks/runtime-graceful-shutdown-and-stuck-worker.md) |
| Idempotency replay mismatch | [Idempotency Incident](../../../docs/runbooks/idempotency-incident.md) |

