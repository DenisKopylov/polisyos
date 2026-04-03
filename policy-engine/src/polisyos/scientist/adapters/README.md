# Adapters (`polisyos.scientist.adapters`)

`adapters` реализует bridge-слой между Scientist workflow runtime и внешними
execution/data системами, не протаскивая прямые вызовы Foundry/Fabric в ноды.

## Роль в системе

- **Зависит от:** `core.contracts`, `core.security`, `foundry`, `fabric`
- **Используется в:** `scientist.workflows`, builtin data/compile/simulate nodes
- Пакет изолирует compile/execute и snapshot/materialization протоколы за typed портами.

## Ключевые концепции

- **DefaultFoundryPort** — compile/execute bridge к Foundry API.
- **DefaultFabricPort** — превращает `DataViewRequest` в snapshot/artifact surface.
- **Derived security artifacts** — TEE attestation и SBOM могут публиковаться через adapter path.
- **Workflow injection** — адаптеры подставляются в `ExecutionContext`, а не хардкодятся в нодах.

## Public API

- `DefaultFoundryPort`
- `DefaultFabricPort`

Подробности: [Reference →](../../../../docs/reference/scientist/index.md)

## Текущее состояние

- Последнее обновление: 2026-04-03
- Python modules: 3
- Exports: 2
- README приведён к общему шаблону; API surface остается компактным и стабильным
