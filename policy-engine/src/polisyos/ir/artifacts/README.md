# Artifacts (`polisyos.ir.artifacts`)

`polisyos.ir.artifacts` задает минимальный CAS I/O protocol для всего IR слоя.
Здесь нет доменной логики конкретных артефактов: пакет описывает `ArtifactID`,
store contract, schema metadata и helpers, через которые `analytics`,
`observation` и typed refs сохраняют и загружают canonical payloads.

## Роль в системе

- **Зависит от:** `polisyos.ir.canon`
- **Используется в:** `polisyos.ir.analytics`, `polisyos.ir.observation`, `polisyos.ir.refs`, `polisyos.core`, `polisyos.fabric`
- Этот пакет является тонкой границей между domain models и реальными CAS backends.

## Ключевые концепции

- **Artifact identity** — `ArtifactID` фиксирует canonical `sha256:<hex>` identifier.
- **Store protocol** — `ArtifactStore` определяет минимальный JSON/bytes contract для persistence.
- **Schema metadata** — `SchemaInfo`, `CanonInfo` и `PutOptions` описывают сохраненный payload.
- **Lineage normalization** — input refs и artifact refs нормализуются до записи.
- **Shared helpers** — analytics и observation bundles используют один и тот же `put_json_artifact()` / `get_json_artifact()` surface.

## Public API

| Type/Function                                        | Description                                                             |
| ---------------------------------------------------- | ----------------------------------------------------------------------- |
| `ArtifactID`                                         | Валидируемый canonical artifact identifier                              |
| `ArtifactStore`                                      | Protocol для CAS backends                                               |
| `PutOptions`, `StorePutOptions`                      | Метаданные записи, schema info и lineage inputs                         |
| `normalize_artifact_ref()`, `normalize_input_refs()` | Нормализуют typed refs перед persistence                                |
| `put_json_artifact()`                                | Сохраняет canonical JSON artifact и возвращает standardized ref payload |
| `get_json_artifact()`                                | Загружает artifact bytes и декодирует их в JSON object                  |

Full reference: [docs/reference/ir/](../../../../docs/reference/ir/index.md)

## Текущее состояние

- Последнее обновление: 2026-04-03
- Files: 4 Python files
- Exports: 12 public names in `__init__.py`
- Current usage: общий I/O слой для analytics artifacts, observation bundles и typed `ir.refs`
