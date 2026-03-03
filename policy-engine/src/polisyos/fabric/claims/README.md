# Claims

`polisyos.fabric.claims` — pipeline извлечения и нормализации утверждений из документов с последующей детекцией/резолюцией конфликтов.

## Сквозной поток

```text
DocMeta + normalized/chunks artifacts
  -> extract_claims_from_doc
  -> normalize_claims
  -> detect_conflicts
  -> resolve_conflicts
  -> world facts/events + trust/quality/uncertainty artifacts
```

## Основные модули

- `extraction.py` — сбор `Claim` из chunk-контекста, дедуп, claim_set + evidence.
- `normalize.py` — canonicalization predicate/unit/value, `derived_from` связи.
- `conflicts/detect.py` — формирование `ConflictSet` и membership edges.
- `conflicts/resolve.py` — ranking кандидатов, выбор winner, trust/quality/uncertainty outputs.
- `extractor_registry.py` — registry legacy + component extractors, bootstrap/discovery.
- `persist.py` — helpers загрузки/персиста claim set, evidence bundle, world segment.
- `world_events.py` — детерминированные world events для стадий claims.

## API входы/выходы

- `extract_claims_from_doc(...)`
  Важно: на текущем API `extractor_id` обязателен (авто-выбор делается внешним кодом через `ClaimExtractorRegistry.select(...)`).
- `normalize_claims(...)`
  Возвращает новый `claim_set_artifact_id`, `derived_edges`, world event/meta refs.
- `detect_conflicts(...)`
  Может работать от `claim_ids`, `claim_set_artifact_ids` или `db`.
- `resolve_conflicts(...)`
  Применяет policy, пишет `ConflictResolution`, `TrustAssessment`, `QualityReport`, uncertainty envelope.

## Extractor layer

Поддерживаются:

- legacy extractors: `explicit_lines_v1`, `lex.norm_extractor.regex_v1`, `regex_numeric_v1`,
- component extractors (bootstrap из `polisyos.core.components`),
- version-aware resolve (`id@semver` и fallback на latest compatible).

## Связи

- upstream: `fabric.docs` (`normalized_ref`, `chunks_ref`, `DocMeta`).
- downstream: `fabric.world` (nodes/edges/events), `fabric.evidence`, `fabric.provenance`.
- модели: `polisyos.ir.world.*` и `polisyos.ir.analytics.uncertainty`.
