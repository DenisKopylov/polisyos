# normpack

`polisyos.lex.normpack` собирает `NormPack` для `jurisdiction + as_of (+ domain)` и возвращает детальный `NormPackBuildResult`.

## Назначение

Подсистема переводит корпусные provisions и извлеченные claims в `NormRule` с:
- применимостью (`NormApplicability`);
- ссылками на источники (`NormRef`/citations);
- backend metadata (predicate/operator/unit, conflict/trust/extractor traces).

## Режимы сборки

### 1) Provider path

Используется, когда:
- найден `NormPackProvider` для `jurisdiction/domain`;
- локальные `doc_source_ids` не выбраны.

Provider может вернуть `NormPack`, `ArtifactRef` или `artifact_id`.

### 2) Pipeline path

Если provider не выбран/не сработал, запускается pipeline:

```text
select_doc_sources
  -> select_active_doc_versions
  -> select_provisions
  -> extract_norm_claims
  -> resolve_conflicts
  -> claims_to_norm_rules
  -> persist lex.norm_pack + ASSEMBLE_NORM_PACK event
```

## Ключевые модули

### `assemble_pack.py`

Главный оркестратор:
- нормализует request (`casefold`, ISO date, ID pattern checks);
- bootstrap-ит providers и extractors через component registry;
- применяет бюджеты (`max_docs`, `max_provisions`, `max_claims`);
- строит детерминированный `pack_id` через `stable_world_id_from_canon`;
- сохраняет `lex.norm_pack` и provenance event;
- возвращает `NormPackBuildResult` с `warnings`.

### `select_sources.py`

- `select_doc_sources`:
  - берет `request.doc_source_ids`, если заданы;
  - иначе находит `doc.source` в fact log и фильтрует до документов `lex.corpus`.
- `select_active_doc_versions`:
  - primary path: `resolve_active_version(...)`;
  - fallback path: прямой temporal выбор из фактов, если index еще не готов;
  - фильтрация по юрисдикции.

### `extract_norm_claims.py`

- Берет selected provisions и extractor.
- Создает norm-claims, дедуплицирует, пишет `lex.norms.claim_set`.
- По умолчанию запускает `normalize_claims`.

### `applicability.py`

- Строит `NormApplicability` из claim validity window.
- Проверяет применимость нормы на дату (`applies_to_context`).

### `provider_registry.py`

- Реестр `NormPackProvider` с ранжированием по domain/jurisdiction/version.
- Bootstrap через entry point group `polisyos.norm_pack_providers`.

### `policies.py`

Константы pipeline:
- default policy ids;
- default extractor id (`lex.norm_extractor.regex_v1@1.0.0`);
- артефактные kind'ы и domain keywords.

## Важные особенности

- По умолчанию выбираются provisions: `article`, `point`, `subpoint`.
- Domain filter работает по keywords в `citation_label` и text preview.
- Конфликтные claims проходят через `fabric.claims.resolve_conflicts`.
- Деградации маршрута фиксируются в `warnings` вместо немедленного hard-fail.

## Связи с другими директориями

- Upstream: `policy-engine/src/polisyos/lex/corpus`.
- Зависимости: `polisyos.fabric.claims`, `polisyos.core.components`, `polisyos.ir.norm_pack`.
- Downstream:
  - `policy-engine/src/polisyos/lex/legal_evaluation`
  - `policy-engine/src/polisyos/lex/simulator`
