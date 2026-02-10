# Nodes Layer (`polisyos.scientist.nodes`)

`nodes` содержит бизнес-ноды Scientist, которые выполняются `engine`-ом через `NodeRegistry`.

## Built-in ноды

- `data/`
  - `BuildDataSnapshotNode`
  - `BindFoundryInputsNode`
  - `EnrichKnowledgeNode` (опциональный scholar-контур)
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

`builtin_nodes()` собирает все встроенные ноды для регистрации.

## Что идет в default DAG

Используются: `build_data_snapshot`, `bind_foundry_inputs`, `run_data_plane_gate`, `link_trinity`, `compile_foundry`, `run_simulation`, `run_distributional_analysis`, `run_causal_evaluation`, `propagate_uncertainty`, `run_governance`, `build_decision_packet`.

Не используются автоматически: `enrich_knowledge`, `legal_check`.

## Контракты и ключи

- интерфейс ноды: `engine.protocol.Node` (`spec` + `execute`).
- ошибки: `nodes/builtins/errors.py`.
- canonical keys для `inputs/artifacts/reports`: `nodes/builtins/state_keys.py`.

## Связи

- `adapters/foundry_bridge.py` и `adapters/fabric_bridge.py`.
- `governance` passes и `kernel` human-gate.
- `ir/foundry/fabric/lex/scholar` артефакты и контракты.
