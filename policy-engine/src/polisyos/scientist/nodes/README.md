# Nodes Layer (`polisyos.scientist.nodes`)

`nodes` содержит исполняемые бизнес-ноды Scientist, которые `engine` запускает через `NodeRegistry`.

## Группы builtin-нод

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
- `causal/`
  - `BuildLiteraturePriorNode`
  - `ReconcileCausalGraphNode`
  - `ResolveParametersNode`
  - `RunCausalQueriesNode`
  - `RunCausalEnsembleNode`
  - `RunABMConsistencyCheckNode`
  - `RunTransportabilityNode`
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

`builtin_nodes()` агрегирует весь встроенный набор для регистрации.

## Что исполняется в `scientist_default`

В default-DAG используются:
- data: `build_data_snapshot`, `bind_foundry_inputs`, `run_data_plane_gate`;
- planning: `build_execution_plan`, `build_method_catalog_snapshot`, `run_preflight`, `ready_to_run`;
- execute: `link_trinity`, `compile_foundry`, `resolve_parameters`, `run_simulation`;
- analysis/governance: `run_distributional_analysis`, `propagate_uncertainty`, `run_causal_evaluation`, `run_governance`, `run_evaluator`;
- finalize: `build_decision_packet`.

## Что добавляется в `scientist_causal_full`

Дополнительно подключаются:
- `build_literature_prior`
- `reconcile_causal_graph`
- `run_causal_queries`
- `run_causal_ensemble`
- `run_abm_consistency`
- `run_transportability`

## Ключевые контракты

- интерфейс ноды: `engine.protocol.Node` (`spec` + `execute`);
- метаданные и state-контракт: `NodeSpec` (`state_reads/state_writes/produces`);
- коды ошибок: `nodes/builtins/errors.py`;
- канонические ключи state/artifacts/reports: `nodes/builtins/state_keys.py`.

## Важные детали реализации

- `BuildDataSnapshotNode` вызывает `FabricPort.snapshot()` только при `data_view_request_ref`; иначе использует уже предоставленный snapshot.
- `RunPreflightNode` валидирует `ExecutionPlan` против live method catalog и возвращает `fail`, если `ready_to_run=False`.
- `ReadyToRunNode` — hard gate перед compile-стадией.
- `RunSimulationNode` пишет derived artifacts (`metrics`, `state_delta`, `environment_manifest`, `tee_attestation`, `sbom`) в `artifacts_index`.
- `RunGovernanceNode` поддерживает typed human-gate lifecycle (`GateRequest`/`GateDecision`) и runtime subset governance passes.

## Связи

- `adapters/` — bridge к `foundry` и `fabric`;
- `compute/` — method jobs в causal-контурах;
- `governance/` + `kernel/` — pass pipeline и human gate protocol;
- контракты `ir`/`foundry`/`fabric`/`lex`/`scholar`.
