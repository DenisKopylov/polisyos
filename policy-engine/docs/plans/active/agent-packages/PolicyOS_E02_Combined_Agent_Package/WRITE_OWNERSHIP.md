# Write leases и hot spots — E02

151 пар статических конфликтов; это не dependency edges. Tests и source/target moves входят в lease. Read-contract impact — отдельные записи в dependency_graph.json. Полные неизвестные current consumers не объявлены покрытыми.

## Самые пересекающиеся файлы

| Путь | Потенциальные последовательные writers |
|---|---|
| `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` | CYC-01, CYC-03, ACQ-01, CYC-04, CYC-02, CYC-05, SIM-01, EMP-01, FRC-01, FRC-02, RES-03 |
| `policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py` | CYC-01, ACQ-01, CYC-04, CYC-05, RES-03 |
| `policy-engine/src/polisyos/runtime/quality/recursive_generation_cycle.py` | CYC-01, CYC-03, CYC-02, CYC-05, SIM-01 |
| `policy-engine/src/polisyos/foundry/calibration/calibrator.py` | CAL-02, CAL-03, CAL-04, CAL-06 |
| `policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py` | GRF-03, SCM-01, SCM-02, SCM-03 |
| `policy-engine/src/polisyos/scientist/methods/search/controller.py` | CTL-01, CTL-03, SRV-01, SRV-03 |
| `policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py` | EXE-01, EXE-02, RES-01, RES-02 |
| `policy-engine/src/polisyos/data_forge/domains/catalog/batch/pipeline.py` | DFI-02, EMB-02, DFI-03 |
| `policy-engine/src/polisyos/data_forge/domains/ukraine/builders/common.py` | UDF-01, OBS-01, UDF-02 |
| `policy-engine/src/polisyos/data_forge/domains/ukraine/builders/sources.py` | OBS-01, UDF-02, OBS-02 |
| `policy-engine/src/polisyos/data_forge/kernel/embeddings.py` | EMB-01, EMB-02, EMB-03 |
| `policy-engine/src/polisyos/fabric/data_plane/streaming.py` | ING-02, ING-03, NET-01 |
| `policy-engine/src/polisyos/foundry/methods/backends/async_chain_executor.py` | CMP-01, CMP-02, RES-03 |
| `policy-engine/src/polisyos/foundry/methods/backends/chain_executor.py` | CMP-01, CMP-02, RES-04 |
| `policy-engine/src/polisyos/foundry/methods/catalog/causal/admg_ops.py` | GRF-01, GRF-02, GRF-03 |
| `policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py` | CAU-01, CAU-02, CAU-05 |
| `policy-engine/src/polisyos/foundry/uncertainty/monte_carlo.py` | UQP-01, UQP-02, UQP-03 |
| `policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py` | SIM-01, SIM-02, SIM-03 |
| `policy-engine/src/polisyos/scientist/methods/autotune/runtime.py` | SRV-03, OPT-02, OPT-04 |
| `policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py` | BKT-01, BKT-02, BKT-03 |
| `policy-engine/src/polisyos/scientist/methods/search/funnel/orchestrator.py` | FUN-01, FUN-02, FUN-03 |
| `policy-engine/src/polisyos/scientist/methods/search/run_state.py` | CTL-01, CTL-03, SRV-01 |
| `policy-engine/src/polisyos/scientist/methods/search/stopping.py` | CTL-01, CTL-03, STP-01 |
| `policy-engine/src/polisyos/scientist/orchestration/engine/idempotency.py` | STA-01, STA-02, RES-01 |
| `policy-engine/src/polisyos/scientist/orchestration/engine/retry.py` | RUN-01, RUN-02, RUN-03 |
| `policy-engine/tools/ops_runners/migrations/migrate.py` | MIG-01, MIG-02, MIG-04 |
| `policy-engine/ops/migrations/migration-contracts.toml` | MIG-02, MIG-04 |
| `policy-engine/src/polisyos/data_forge/domains/academic/batch/embedder.py` | EMB-01, EMB-02 |
| `policy-engine/src/polisyos/data_forge/domains/catalog/batch/core_sources_ingest.py` | DFI-01, DFI-02 |
| `policy-engine/src/polisyos/data_forge/domains/catalog/batch/embedder.py` | EMB-01, EMB-02 |
| `policy-engine/src/polisyos/data_forge/domains/ukraine/builders/__init__.py` | UDF-01, UDF-02 |
| `policy-engine/src/polisyos/data_forge/domains/ukraine/builders/io.py` | UDF-02, OBS-02 |
| `policy-engine/src/polisyos/ddm/calibration/audit.py` | DDM-01, DDM-02 |
| `policy-engine/src/polisyos/ddm/contracts/events.py` | DDM-01, DDM-02 |
| `policy-engine/src/polisyos/ddm/contracts/metric_budget.py` | DDM-01, DDM-02 |
| `policy-engine/src/polisyos/ddm/integration/model_registry.py` | DDM-01, DDM-02 |
| `policy-engine/src/polisyos/ddm/integration/monitor.py` | DDM-01, DDM-02 |
| `policy-engine/src/polisyos/ddm/readiness/readiness_mapper.py` | DDM-01, DDM-02 |
| `policy-engine/src/polisyos/fabric/connectors/federation/composer.py` | FED-01, FED-02 |
| `policy-engine/src/polisyos/fabric/connectors/federation/types.py` | FED-01, FED-02 |
| `policy-engine/src/polisyos/fabric/data_plane/cursor_store.py` | ING-01, ING-02 |
| `policy-engine/src/polisyos/fabric/data_plane/modes.py` | ING-01, ING-03 |
| `policy-engine/src/polisyos/foundry/calibration/measurement.py` | CAL-01, CAL-02 |
| `policy-engine/src/polisyos/foundry/calibration/uncertainty_adapter.py` | CAL-06, UQS-01 |
| `policy-engine/src/polisyos/foundry/execute/mechanisms/fiscal.py` | FRY-03, ECO-01 |
| `policy-engine/src/polisyos/foundry/execute/mechanisms/labor.py` | FRY-03, ECO-01 |
| `policy-engine/src/polisyos/foundry/methods/catalog/causal/_common.py` | CAU-01, CAU-04 |
| `policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_fit.py` | GRF-03, SCM-01 |
| `policy-engine/src/polisyos/foundry/methods/catalog/causal/rdd.py` | CAU-01, CAU-03 |
| `policy-engine/src/polisyos/foundry/methods/catalog/causal/twin_network_query.py` | SCM-01, SCM-02 |
| `policy-engine/src/polisyos/foundry/methods/components/composer.py` | CMP-01, CMP-02 |
| `policy-engine/src/polisyos/foundry/methods/components/semantic_validator.py` | CMP-02, CMP-03 |
| `policy-engine/src/polisyos/foundry/plugins/api.py` | PLG-02, PLG-03 |
| `policy-engine/src/polisyos/foundry/plugins/cli.py` | PLG-02, PLG-03 |
| `policy-engine/src/polisyos/foundry/uncertainty/covariance.py` | CAL-06, UQP-02 |
| `policy-engine/src/polisyos/foundry/uncertainty/delta.py` | UQP-01, UQP-02 |
| `policy-engine/src/polisyos/foundry/uncertainty/dispatcher.py` | UQP-01, UQP-02 |
| `policy-engine/src/polisyos/ir/analytics/calibration.py` | CAL-01, CAL-06 |
| `policy-engine/src/polisyos/ir/analytics/causal_graph.py` | GRF-02, GRF-03 |
| `policy-engine/src/polisyos/ir/analytics/causal_queries.py` | SCM-02, SCM-03 |
| `policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py` | CYC-01, CYC-05 |
| `policy-engine/src/polisyos/runtime/quality/design_axes/outcome_prediction.py` | FRC-01, FRC-02 |
| `policy-engine/src/polisyos/scientist/methods/autotune/models.py` | OPT-01, OPT-02 |
| `policy-engine/src/polisyos/scientist/methods/doe/analysis.py` | DOE-02, DOE-03 |
| `policy-engine/src/polisyos/scientist/methods/doe/designs.py` | DOE-01, DOE-02 |
| `policy-engine/src/polisyos/scientist/methods/doe/sampling.py` | DOE-01, DOE-02 |
| `policy-engine/src/polisyos/scientist/methods/search/adapters.py` | SRV-01, SRV-03 |
| `policy-engine/src/polisyos/scientist/methods/search/strategies/base.py` | CTL-02, OPT-03 |
| `policy-engine/src/polisyos/scientist/methods/search/strategies/space.py` | CTL-02, OPT-02 |
| `policy-engine/src/polisyos/scientist/methods/search/strategies/transfer.py` | TRN-01, TRN-02 |
| `policy-engine/src/polisyos/scientist/orchestration/engine/checkpoint.py` | RES-01, RES-02 |
| `policy-engine/src/polisyos/scientist/orchestration/engine/executor.py` | STA-01, RES-01 |
| `policy-engine/src/polisyos/scientist/orchestration/llm/factory.py` | LLM-01, LLM-02 |
| `policy-engine/src/polisyos/scientist/orchestration/llm/prompt_cache.py` | LLM-01, LLM-02 |

## Полная таблица конфликтов

| Пакет A | Пакет B | Общие paths/leases |
|---|---|---|
| CYC-01 | CYC-03 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py`<br>`policy-engine/src/polisyos/runtime/quality/recursive_generation_cycle.py` |
| CYC-01 | ACQ-01 | `policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py`<br>`policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| CYC-01 | CYC-04 | `policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py`<br>`policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| CYC-01 | CYC-02 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py`<br>`policy-engine/src/polisyos/runtime/quality/recursive_generation_cycle.py` |
| CYC-01 | CYC-05 | `policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py`<br>`policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py`<br>`policy-engine/src/polisyos/runtime/quality/generation_cycle.py`<br>`policy-engine/src/polisyos/runtime/quality/recursive_generation_cycle.py` |
| CYC-01 | SIM-01 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py`<br>`policy-engine/src/polisyos/runtime/quality/recursive_generation_cycle.py` |
| CYC-01 | EMP-01 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| CYC-01 | FRC-01 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| CYC-01 | FRC-02 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| CYC-01 | RES-03 | `policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py`<br>`policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| CYC-03 | ACQ-01 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| CYC-03 | CYC-04 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| CYC-03 | CYC-02 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py`<br>`policy-engine/src/polisyos/runtime/quality/recursive_generation_cycle.py` |
| CYC-03 | CYC-05 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py`<br>`policy-engine/src/polisyos/runtime/quality/recursive_generation_cycle.py` |
| CYC-03 | SIM-01 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py`<br>`policy-engine/src/polisyos/runtime/quality/recursive_generation_cycle.py` |
| CYC-03 | EMP-01 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| CYC-03 | FRC-01 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| CYC-03 | FRC-02 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| CYC-03 | RES-03 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| ACQ-01 | CYC-04 | `policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py`<br>`policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| ACQ-01 | CYC-02 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| ACQ-01 | CYC-05 | `policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py`<br>`policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| ACQ-01 | SIM-01 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| ACQ-01 | EMP-01 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| ACQ-01 | FRC-01 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| ACQ-01 | FRC-02 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| ACQ-01 | RES-03 | `policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py`<br>`policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| CYC-04 | CYC-02 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| CYC-04 | CYC-05 | `policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py`<br>`policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| CYC-04 | SIM-01 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| CYC-04 | EMP-01 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| CYC-04 | FRC-01 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| CYC-04 | FRC-02 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| CYC-04 | RES-03 | `policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py`<br>`policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| CYC-02 | CYC-05 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py`<br>`policy-engine/src/polisyos/runtime/quality/recursive_generation_cycle.py` |
| CYC-02 | SIM-01 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py`<br>`policy-engine/src/polisyos/runtime/quality/recursive_generation_cycle.py` |
| CYC-02 | EMP-01 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| CYC-02 | FRC-01 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| CYC-02 | FRC-02 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| CYC-02 | RES-03 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| CYC-05 | SIM-01 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py`<br>`policy-engine/src/polisyos/runtime/quality/recursive_generation_cycle.py` |
| CYC-05 | EMP-01 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| CYC-05 | FRC-01 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| CYC-05 | FRC-02 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| CYC-05 | RES-03 | `policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py`<br>`policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| SIM-01 | SIM-02 | `policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py` |
| SIM-01 | SIM-03 | `policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py` |
| SIM-01 | EMP-01 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| SIM-01 | FRC-01 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| SIM-01 | FRC-02 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| SIM-01 | RES-03 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| SIM-02 | SIM-03 | `policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py` |
| CTL-01 | CTL-03 | `policy-engine/src/polisyos/scientist/methods/search/controller.py`<br>`policy-engine/src/polisyos/scientist/methods/search/run_state.py`<br>`policy-engine/src/polisyos/scientist/methods/search/stopping.py` |
| CTL-01 | SRV-01 | `policy-engine/src/polisyos/scientist/methods/search/controller.py`<br>`policy-engine/src/polisyos/scientist/methods/search/run_state.py` |
| CTL-01 | SRV-03 | `policy-engine/src/polisyos/scientist/methods/search/controller.py` |
| CTL-01 | STP-01 | `policy-engine/src/polisyos/scientist/methods/search/stopping.py` |
| CTL-03 | SRV-01 | `policy-engine/src/polisyos/scientist/methods/search/controller.py`<br>`policy-engine/src/polisyos/scientist/methods/search/run_state.py` |
| CTL-03 | SRV-03 | `policy-engine/src/polisyos/scientist/methods/search/controller.py` |
| CTL-03 | STP-01 | `policy-engine/src/polisyos/scientist/methods/search/stopping.py` |
| SRV-01 | SRV-03 | `policy-engine/src/polisyos/scientist/methods/search/adapters.py`<br>`policy-engine/src/polisyos/scientist/methods/search/controller.py` |
| SRV-03 | OPT-02 | `policy-engine/src/polisyos/scientist/methods/autotune/runtime.py` |
| SRV-03 | OPT-04 | `policy-engine/src/polisyos/scientist/methods/autotune/runtime.py` |
| CTL-02 | OPT-02 | `policy-engine/src/polisyos/scientist/methods/search/strategies/space.py` |
| CTL-02 | OPT-03 | `policy-engine/src/polisyos/scientist/methods/search/strategies/base.py` |
| OPT-01 | OPT-02 | `policy-engine/src/polisyos/scientist/methods/autotune/models.py` |
| OPT-02 | OPT-04 | `policy-engine/src/polisyos/scientist/methods/autotune/runtime.py` |
| FUN-01 | FUN-02 | `policy-engine/src/polisyos/scientist/methods/search/funnel/orchestrator.py` |
| FUN-01 | FUN-03 | `policy-engine/src/polisyos/scientist/methods/search/funnel/orchestrator.py` |
| FUN-02 | FUN-03 | `policy-engine/src/polisyos/scientist/methods/search/funnel/orchestrator.py` |
| TRN-01 | TRN-02 | `policy-engine/src/polisyos/scientist/methods/search/strategies/transfer.py` |
| EMP-01 | FRC-01 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| EMP-01 | FRC-02 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| EMP-01 | RES-03 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| FRC-01 | FRC-02 | `policy-engine/src/polisyos/runtime/quality/design_axes/outcome_prediction.py`<br>`policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| FRC-01 | RES-03 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| FRC-02 | RES-03 | `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` |
| BKT-01 | BKT-02 | `policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py` |
| BKT-01 | BKT-03 | `policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py` |
| BKT-02 | BKT-03 | `policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py` |
| FRY-03 | ECO-01 | `policy-engine/src/polisyos/foundry/execute/mechanisms/fiscal.py`<br>`policy-engine/src/polisyos/foundry/execute/mechanisms/labor.py` |
| PLG-02 | PLG-03 | `policy-engine/src/polisyos/foundry/plugins/api.py`<br>`policy-engine/src/polisyos/foundry/plugins/cli.py` |
| CMP-01 | CMP-02 | `policy-engine/src/polisyos/foundry/methods/backends/async_chain_executor.py`<br>`policy-engine/src/polisyos/foundry/methods/backends/chain_executor.py`<br>`policy-engine/src/polisyos/foundry/methods/components/composer.py` |
| CMP-01 | RES-04 | `policy-engine/src/polisyos/foundry/methods/backends/chain_executor.py` |
| CMP-01 | RES-03 | `policy-engine/src/polisyos/foundry/methods/backends/async_chain_executor.py` |
| CMP-02 | CMP-03 | `policy-engine/src/polisyos/foundry/methods/components/semantic_validator.py` |
| CMP-02 | RES-04 | `policy-engine/src/polisyos/foundry/methods/backends/chain_executor.py` |
| CMP-02 | RES-03 | `policy-engine/src/polisyos/foundry/methods/backends/async_chain_executor.py` |
| GRF-01 | GRF-02 | `policy-engine/src/polisyos/foundry/methods/catalog/causal/admg_ops.py` |
| GRF-01 | GRF-03 | `policy-engine/src/polisyos/foundry/methods/catalog/causal/admg_ops.py` |
| GRF-02 | GRF-03 | `policy-engine/src/polisyos/foundry/methods/catalog/causal/admg_ops.py`<br>`policy-engine/src/polisyos/ir/analytics/causal_graph.py` |
| GRF-03 | SCM-01 | `policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_fit.py`<br>`policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py` |
| GRF-03 | SCM-02 | `policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py` |
| GRF-03 | SCM-03 | `policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py` |
| CAU-01 | CAU-02 | `policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py` |
| CAU-01 | CAU-03 | `policy-engine/src/polisyos/foundry/methods/catalog/causal/rdd.py` |
| CAU-01 | CAU-04 | `policy-engine/src/polisyos/foundry/methods/catalog/causal/_common.py` |
| CAU-01 | CAU-05 | `policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py` |
| CAU-02 | CAU-05 | `policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py` |
| SCM-01 | SCM-02 | `policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py`<br>`policy-engine/src/polisyos/foundry/methods/catalog/causal/twin_network_query.py` |
| SCM-01 | SCM-03 | `policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py` |
| SCM-02 | SCM-03 | `policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py`<br>`policy-engine/src/polisyos/ir/analytics/causal_queries.py` |
| STA-01 | STA-02 | `policy-engine/src/polisyos/scientist/orchestration/engine/idempotency.py` |
| STA-01 | RES-01 | `policy-engine/src/polisyos/scientist/orchestration/engine/executor.py`<br>`policy-engine/src/polisyos/scientist/orchestration/engine/idempotency.py` |
| STA-02 | RES-01 | `policy-engine/src/polisyos/scientist/orchestration/engine/idempotency.py` |
| EXE-01 | EXE-02 | `policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py` |
| EXE-01 | RES-01 | `policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py` |
| EXE-01 | RES-02 | `policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py` |
| EXE-02 | RES-01 | `policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py` |
| EXE-02 | RES-02 | `policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py` |
| RES-01 | RES-02 | `policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py`<br>`policy-engine/src/polisyos/scientist/orchestration/engine/checkpoint.py` |
| RUN-01 | RUN-02 | `policy-engine/src/polisyos/scientist/orchestration/engine/retry.py` |
| RUN-01 | RUN-03 | `policy-engine/src/polisyos/scientist/orchestration/engine/retry.py` |
| RUN-02 | RUN-03 | `policy-engine/src/polisyos/scientist/orchestration/engine/retry.py` |
| MIG-01 | MIG-02 | `policy-engine/tools/ops_runners/migrations/migrate.py` |
| MIG-01 | MIG-04 | `policy-engine/tools/ops_runners/migrations/migrate.py` |
| MIG-02 | MIG-04 | `policy-engine/ops/migrations/migration-contracts.toml`<br>`policy-engine/tools/ops_runners/migrations/migrate.py` |
| UDF-01 | OBS-01 | `policy-engine/src/polisyos/data_forge/domains/ukraine/builders/common.py` |
| UDF-01 | UDF-02 | `policy-engine/src/polisyos/data_forge/domains/ukraine/builders/__init__.py`<br>`policy-engine/src/polisyos/data_forge/domains/ukraine/builders/common.py` |
| OBS-01 | UDF-02 | `policy-engine/src/polisyos/data_forge/domains/ukraine/builders/common.py`<br>`policy-engine/src/polisyos/data_forge/domains/ukraine/builders/sources.py` |
| OBS-01 | OBS-02 | `policy-engine/src/polisyos/data_forge/domains/ukraine/builders/sources.py` |
| UDF-02 | OBS-02 | `policy-engine/src/polisyos/data_forge/domains/ukraine/builders/io.py`<br>`policy-engine/src/polisyos/data_forge/domains/ukraine/builders/sources.py` |
| FED-01 | FED-02 | `policy-engine/src/polisyos/fabric/connectors/federation/composer.py`<br>`policy-engine/src/polisyos/fabric/connectors/federation/types.py` |
| CAL-01 | CAL-02 | `policy-engine/src/polisyos/foundry/calibration/measurement.py` |
| CAL-01 | CAL-06 | `policy-engine/src/polisyos/ir/analytics/calibration.py` |
| DFI-01 | DFI-02 | `policy-engine/src/polisyos/data_forge/domains/catalog/batch/core_sources_ingest.py` |
| DFI-02 | EMB-02 | `policy-engine/src/polisyos/data_forge/domains/catalog/batch/pipeline.py` |
| DFI-02 | DFI-03 | `policy-engine/src/polisyos/data_forge/domains/catalog/batch/pipeline.py` |
| EMB-01 | EMB-02 | `policy-engine/src/polisyos/data_forge/domains/academic/batch/embedder.py`<br>`policy-engine/src/polisyos/data_forge/domains/catalog/batch/embedder.py`<br>`policy-engine/src/polisyos/data_forge/kernel/embeddings.py` |
| EMB-01 | EMB-03 | `policy-engine/src/polisyos/data_forge/kernel/embeddings.py` |
| EMB-02 | EMB-03 | `policy-engine/src/polisyos/data_forge/kernel/embeddings.py` |
| EMB-02 | DFI-03 | `policy-engine/src/polisyos/data_forge/domains/catalog/batch/pipeline.py` |
| ING-01 | ING-02 | `policy-engine/src/polisyos/fabric/data_plane/cursor_store.py` |
| ING-01 | ING-03 | `policy-engine/src/polisyos/fabric/data_plane/modes.py` |
| ING-02 | ING-03 | `policy-engine/src/polisyos/fabric/data_plane/streaming.py` |
| ING-02 | NET-01 | `policy-engine/src/polisyos/fabric/data_plane/streaming.py` |
| ING-03 | NET-01 | `policy-engine/src/polisyos/fabric/data_plane/streaming.py` |
| LLM-01 | LLM-02 | `policy-engine/src/polisyos/scientist/orchestration/llm/factory.py`<br>`policy-engine/src/polisyos/scientist/orchestration/llm/prompt_cache.py` |
| CAL-02 | CAL-03 | `policy-engine/src/polisyos/foundry/calibration/calibrator.py` |
| CAL-02 | CAL-04 | `policy-engine/src/polisyos/foundry/calibration/calibrator.py` |
| CAL-02 | CAL-06 | `policy-engine/src/polisyos/foundry/calibration/calibrator.py` |
| CAL-03 | CAL-04 | `policy-engine/src/polisyos/foundry/calibration/calibrator.py` |
| CAL-03 | CAL-06 | `policy-engine/src/polisyos/foundry/calibration/calibrator.py` |
| CAL-04 | CAL-06 | `policy-engine/src/polisyos/foundry/calibration/calibrator.py` |
| CAL-06 | UQS-01 | `policy-engine/src/polisyos/foundry/calibration/uncertainty_adapter.py` |
| CAL-06 | UQP-02 | `policy-engine/src/polisyos/foundry/uncertainty/covariance.py` |
| UQP-01 | UQP-02 | `policy-engine/src/polisyos/foundry/uncertainty/delta.py`<br>`policy-engine/src/polisyos/foundry/uncertainty/dispatcher.py`<br>`policy-engine/src/polisyos/foundry/uncertainty/monte_carlo.py` |
| UQP-01 | UQP-03 | `policy-engine/src/polisyos/foundry/uncertainty/monte_carlo.py` |
| UQP-02 | UQP-03 | `policy-engine/src/polisyos/foundry/uncertainty/monte_carlo.py` |
| DOE-01 | DOE-02 | `policy-engine/src/polisyos/scientist/methods/doe/designs.py`<br>`policy-engine/src/polisyos/scientist/methods/doe/sampling.py` |
| DOE-02 | DOE-03 | `policy-engine/src/polisyos/scientist/methods/doe/analysis.py` |
| DDM-01 | DDM-02 | `policy-engine/src/polisyos/ddm/calibration/audit.py`<br>`policy-engine/src/polisyos/ddm/contracts/events.py`<br>`policy-engine/src/polisyos/ddm/contracts/metric_budget.py`<br>`policy-engine/src/polisyos/ddm/integration/model_registry.py`<br>`policy-engine/src/polisyos/ddm/integration/monitor.py`<br>`policy-engine/src/polisyos/ddm/readiness/readiness_mapper.py` |

Один active writer на файл. Изменившееся фактическое местоположение обновляет lease до dispatch; поле special lease не разрешает неизвестный lockfile без уточнения path. Чтение независимого worktree можно делать заранее; перед integration проверять затронутые consumer contracts на новом SHA.
