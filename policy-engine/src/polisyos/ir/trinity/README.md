# Trinity (`polisyos.ir.trinity`)

`polisyos.ir.trinity` определяет канонический policy payload `TrinityBundle`.
Именно эта структура является официальной точкой входа для policy ingestion:
`ProblemFrame` описывает why, `PolicySpec` задает what, а `ModelSpec` описывает
how. Все downstream compile, governance и migration flows стартуют отсюда.

## Роль в системе

- **Зависит от:** `polisyos.ir.governance`, `polisyos.ir.model_spec`
- **Используется в:** `polisyos.ir.loaders`, `polisyos.ir.migrations`, `polisyos.ir.linker`, `polisyos.foundry`, `polisyos.scientist`
- Trinity служит canonical boundary между authoring/import и runtime validation.

## Ключевые концепции

- **Three-part payload** — `ProblemFrame`, `PolicySpec`, `ModelSpec`.
- **Versioned bundle** — `TRINITY_BUNDLE_SCHEMA_VERSION` фиксирует текущий schema contract.
- **Strict loaders** — submodule loaders принимают `dict`, `str`, `bytes` и валидируют schema version.
- **No legacy auto-upgrade** — non-Trinity payloads не мигрируются автоматически.
- **Link-before-execute** — Trinity bundle должен пройти через registry linker перед compile/runtime.

## Public API

| Type/Function | Description |
|---|---|
| `TrinityBundle` | Канонический контейнер policy IR |
| `ProblemFrame` | Why-layer governance contract |
| `PolicySpec` | What-layer intervention contract |
| `ModelSpec` | How-layer execution/model contract |
| `TRINITY_BUNDLE_SCHEMA_VERSION` | Текущая версия bundle schema |
| `load_trinity_bundle()` | Strict loader для Trinity payloads |

Full reference: [docs/reference/ir/](../../../../docs/reference/ir/index.md)

See also: [docs/explanation/trinity.md](../../../../docs/explanation/trinity.md)

## Текущее состояние

- Последнее обновление: 2026-04-03
- Files: 3 Python files
- Exports: 5 public names in `__init__.py`
- Current version: `TrinityBundle` schema остается `1.0`; новые temporal and observation-aware policy fields живут внутри составляющих contracts, а не в отдельной bundle версии
