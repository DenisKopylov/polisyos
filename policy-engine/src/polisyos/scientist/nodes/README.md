# Nodes Layer (`polisyos.scientist.nodes`)

`nodes` содержит бизнес-ноды Scientist, которые исполняются `engine` через `NodeRegistry`.

## Built-in ноды

- `data/`
  - `BuildDataSnapshotNode`
  - `BindFoundryInputsNode`
  - `EnrichKnowledgeNode` (опциональный scholar-контур)
- `planning/`
  - `BuildExecutionPlanNode`
  - `BuildMethodCatalogSnapshotNode`
  - `RunPreflightNode`
  - `ReadyToRunNode`
  - `RunEvaluatorNode`
- `compile/`
  - `LinkTrinityNode`
  - `CompileFoundryNode`
- `simulate/`
  - `RunSimulationNode`
  - `RunDistributionalAnalysisNode`
  - `RunCausalEvaluationNode`
  - `PropagateUncertaintyNode`
- `governance/`
  - `DataPlaneGateNode`
  - `LegalCheckNode`
  - `RunGovernanceNode`
- `decide/`
  - `BuildDecisionPacketNode`

`builtin_nodes()` собирает весь встроенный набор для регистрации в workflow.

## Что идет в default DAG

Используются:
- `build_data_snapshot`, `bind_foundry_inputs`, `run_data_plane_gate`;
- `build_execution_plan`, `build_method_catalog_snapshot`, `run_preflight`, `ready_to_run`, `run_evaluator`;
- `link_trinity`, `compile_foundry`;
- `run_simulation`, `run_distributional_analysis`, `run_causal_evaluation`, `propagate_uncertainty`;
- `run_governance`, `build_decision_packet`.

Не используются автоматически:
- `enrich_knowledge`, `legal_check`.

## Ключевые контракты

- интерфейс ноды: `engine.protocol.Node` (`spec` + `execute`);
- execution metadata: `NodeSpec` (`state_reads/state_writes/produces`);
- ошибки/коды: `nodes/builtins/errors.py`;
- canonical ключи state/artifacts/reports: `nodes/builtins/state_keys.py`.

## Важные особенности

- `BuildDataSnapshotNode` строит snapshot через `FabricPort` только если есть `data_view_request_ref`; иначе ожидает готовый `data_snapshot_ref`.
- `RunPreflightNode` валидирует execution plan против live method catalog и блокирует downstream execute при ошибках.
- `ReadyToRunNode` — hard gate перед compile stage.
- `RunSimulationNode` сохраняет derived refs (`metrics`, `state_delta`, `environment_manifest`, `tee_attestation`, `sbom`) в `artifacts_index`.
- `RunGovernanceNode` поддерживает typed human-gate lifecycle (`gate_request`/`gate_decision`).

## Связи

- `adapters/foundry_bridge.py` и `adapters/fabric_bridge.py`.
- `governance` passes и `kernel` human-gate protocol.
- `compute` (method jobs для causal/evaluator контуров).
- контракты `ir`/`foundry`/`fabric`/`lex`/`scholar`.
