# Claims

`polisyos.fabric.claims` — конвейер извлечения, нормализации и конфликт-резолюции claims поверх документных фрагментов.

## Сквозной поток

```text
DocMeta + normalized/chunks refs
   -> extract_claims_from_doc
   -> normalize_claims
   -> detect_conflicts
   -> resolve_conflicts
   -> world events + fact segments + trust/quality artifacts
```

## Основные модули

- `extraction.py` — извлечение `ClaimCandidate` и сборка канонических `Claim`.
- `normalize.py` — канонизация predicate/unit/value, дедупликация, `derived_from` связи.
- `conflicts/detect.py` — построение `ConflictSet` на основе `conflict_key_v1`/`compare_v1`.
- `conflicts/resolve.py` — ранжирование кандидатов, выбор победителя, генерация trust/uncertainty/quality артефактов.
- `extractor_registry.py` — единый реестр экстракторов (legacy + component-based bootstrap).
- `persist.py` — CAS helpers для claim set, evidence bundle и world segment.
- `world_events.py` — детерминированные world events для стадий claims pipeline.
- `backends/` — встроенные extractors (`explicit_lines_v1`, `lex_norm_regex_v1`, `regex_numeric_v1`).

## Входы/выходы API

### `extract_claims_from_doc(...)`

- Вход: `doc_meta_artifact_id` + extractor selection (`extractor_id` или auto-select).
- Выход: `ClaimExtractResult` с `claim_set_artifact_id`, `claim_ids`, `evidence_ref`, `world_event_*`, `world_segment_manifest`.

### `normalize_claims(...)`

- Вход: `claim_set_artifact_id`.
- Выход: `ClaimNormalizeResult` с новым `claim_set_artifact_id`, `derived_edges`, `world_event_*`, `world_segment_manifest`.

### `detect_conflicts(...)` и `resolve_conflicts(...)`

- `detect_conflicts(...)` формирует `ConflictSet` + связи `claim -> conflict_set`.
- `resolve_conflicts(...)` применяет policy, выбирает winner и сохраняет `ConflictResolution`, trust assessments, quality report, uncertainty envelopes.

Обе стадии поддерживают исполнение через `SimulationDB` или `StoragePort`.

## Особенности extractor-слоя

`ClaimExtractorRegistry.select(...)` поддерживает:

- явный `preferred_id`,
- авторанжирование component extractors по domain/jurisdiction/language/mime,
- fallback на встроенные legacy extractors.

Компонентные экстракторы загружаются через `discover_and_bootstrap_extractors(...)` и registry `polisyos.core.components`.

## Связи

- `fabric.docs` — upstream документные артефакты (`normalized_ref`, `chunks_ref`).
- `fabric.world` — эмиссия/персист world-фактов и событий.
- `fabric.evidence`, `fabric.provenance` — трассируемость стадий.
- `polisyos.ir.world.*` — канонические модели claims/conflicts/trust/quality/events.
