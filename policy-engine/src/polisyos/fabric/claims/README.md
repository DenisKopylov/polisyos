# Claims

`polisyos.fabric.claims` — пайплайн извлечения и нормализации claims из документных фрагментов с последующим обнаружением и разрешением конфликтов.

## Поток

```text
DocMeta + normalized/chunks refs
   -> extract_claims_from_doc
   -> normalize_claims
   -> detect_conflicts
   -> resolve_conflicts
   -> world facts + events + segment manifests
```

## Основные модули

- `extraction.py` — извлечение кандидатов через pluggable extractor backends, построение `Claim`
- `normalize.py` — канонизация predicate/unit/value, дедупликация, `derived_from` связи
- `conflicts/detect.py` — группировка claim'ов по conflict key и формирование `ConflictSet`
- `conflicts/resolve.py` — ранжирование кандидатов, выбор победителя, trust/quality side-effects
- `persist.py` — CAS helpers (claim-set payloads, evidence bundle, world segment)
- `extractor_registry.py` — реестр и bootstrap extractors
- `backends/` — встроенные extractors (`explicit_lines_v1`, `lex_norm_regex_v1`, `regex_numeric_v1`)

## Входы и выходы

### Extraction

`extract_claims_from_doc(...)` принимает `DocMeta`-артефакт и extractor id.

Возвращает `ClaimExtractResult`:

- `claim_set_artifact_id`, `claim_ids`
- `world_event_id` и `world_event_artifact_id`
- `world_segment_manifest`
- `evidence_ref` (если включено)

### Normalization

`normalize_claims(...)` принимает `claim_set_artifact_id`.

Возвращает `ClaimNormalizeResult`:

- новый `claim_set_artifact_id`
- `derived_edges` при смене `claim_id` после нормализации
- world event + segment manifest

### Conflict processing

- `detect_conflicts(...)` формирует conflict sets и world edges `claim -> conflict_set`
- `resolve_conflicts(...)` применяет policy, сохраняет resolution artifacts, trust/quality records

Оба шага могут работать через `db` (`SimulationDB`) или `storage` (`StoragePort`), в зависимости от сценария.

## Связи

- `docs/` — upstream источник нормализованного текста и chunk refs
- `world/` — эмиссия/персист world-фактов и событий
- `evidence.py`, `provenance/` — трассируемость pipeline
- `polisyos.ir.world.*` — канонические модели claim/conflict/trust/quality/event
