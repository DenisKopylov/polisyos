# Artifacts (`polisyos.ir.artifacts`)

`polisyos.ir.artifacts` задает минимальный CAS I/O protocol для всего IR слоя.
Здесь нет доменной логики конкретных артефактов: пакет описывает `ArtifactID`,
store contract, schema metadata и helpers, через которые `analytics`,
`observation` и typed refs сохраняют и загружают canonical payloads.

## Роль в системе

- **Зависит от:** `polisyos.ir.model_layer.canon`
- **Используется в:** `polisyos.ir.analytics`, `polisyos.ir.observation`, `polisyos.ir.registry.refs`, `polisyos.core`, `polisyos.fabric`
- Этот пакет является тонкой границей между domain models и реальными CAS backends.

## Ключевые концепции

- **Artifact identity** — `ArtifactID` фиксирует canonical `sha256:<hex>` identifier.
- **Store protocol** — `ArtifactStore` определяет минимальный JSON/bytes contract для persistence.
- **Schema metadata** — `SchemaInfo`, `CanonInfo` и `PutOptions` описывают сохраненный payload.
- **Lineage normalization** — input refs и artifact refs нормализуются до записи.
- **Profile-aware reads** — `get_json_artifact()` requires the store's raw
  `get_manifest_bytes()` capability. It parses the exact selected sidecar before any IR
  profile model can fill defaults, requires every current `CanonInfo` field, then reads
  the payload through that same artifact selector. It decodes and re-encodes under the
  declared formatting options and existing IR tag family; only an exact byte match is
  accepted. A typed manifest Mapping alone is not raw-profile evidence. Profile-less
  historical artifacts remain unsupported and require a separate compatibility decision.
  The check proves the declared profile reproduces these bytes, not which producer chose
  it. Byte-only reads cannot recover input properties that leave no byte witness—for
  example, whether `exclude_none=True` was intended when no null value appears.
- **Core/IR compatibility** — the current default Core `put_json` producer emits a
  complete profile and shared tags such as `decimal` can be read by a fresh IR reader.
  Supported stored formatting options are verified by a decode/re-encode equality check;
  reads do not rewrite payload bytes. The Core adapter and write-through cache preserve
  exact typed artifact-view selectors for raw manifest and payload reads.
  The Core-to-IR writer adapter accepts typed options or a `Mapping` and projects the
  complete declared Core write-option set, including tenant context, same-input closure,
  authority, and warnings; malformed values and unknown fields fail before persistence.
  IR artifact-ref normalization validates against the shared strict ref model. Unknown
  mapping keys, model fields (including excluded fields), and declared structural fields
  fail before a selected manifest or payload read; supported scalar IDs remain ID-only
  selectors and do not stand in for a selected-view ref.
  Core-only `float_hex`, `bytes_hex`, and `array_digest` tags remain unsupported by IR,
  even though Core and IR currently use the same canon name/version. A complete profile
  is a decoding input, not proof of an IR producer or authority. Raw Core writes and
  historical profile migration remain separate C02/G compatibility decisions.
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
