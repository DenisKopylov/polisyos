# Adapters Layer (`polisyos.scientist.adapters`)

`adapters` реализует порты `ExecutionContext` для интеграции Scientist с внешними execution/data подсистемами.

## Состав

- `foundry_bridge.py` — `DefaultFoundryPort`
  - `compile()` и `execute()` для Foundry API;
  - опциональная TEE-проверка через `TEEGatekeeper`;
  - добавление `security.tee_attestation` и `security.sbom` как derived artifacts.
- `fabric_bridge.py` — `DefaultFabricPort`
  - `DataViewRequestRef -> DataSnapshotRef`;
  - загрузка данных через `fabric_get_data()`;
  - запись `fabric.tabular_payload`, `fabric.data_schema`, `fabric.quality_report`, `fabric.warnings`, итогового `fabric.data_snapshot`.

## Как используется в workflow

- `run_default_workflow()` всегда подключает `DefaultFoundryPort`, если порт не передан снаружи.
- `DefaultFabricPort` подключается автоматически, когда в inputs есть `data_view_request_ref`.
- Ноды `build_data_snapshot`, `compile_foundry`, `run_simulation` работают через эти порты, а не напрямую с Foundry/Fabric.

## Связи

- `core.security.*` — настройки TEE/SBOM и middleware;
- `core.contracts.foundry` и `core.contracts.fabric` — типизированные контракты запросов/ответов;
- `nodes/builtins/*` — прямые потребители адаптеров в DAG.
