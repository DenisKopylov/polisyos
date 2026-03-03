# normpack

`polisyos.lex.normpack` собирает `NormPack` для `jurisdiction + as_of (+ domain)` и возвращает `NormPackBuildResult` с детальным provenance и предупреждениями.

## Роль

Подсистема переводит provisions/claims в `NormRule` с:
- применимостью (`NormApplicability`);
- ссылками на источники (`NormRef`/citations);
- backend metadata (predicate/operator/unit/conflict/trust/extractor traces).

## Режимы сборки

### Provider path

Используется, если найден `NormPackProvider` и нет локально выбранных `doc_source_ids`.

Provider может вернуть:
- `NormPack`
- `ArtifactRef`
- `artifact_id`

### Pipeline path

Если provider не выбран или не отработал:

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
- нормализует request (`casefold`, ISO date, ID checks, budgets);
- bootstrap-ит providers и extractors через component registry;
- применяет ограничения `max_docs/max_provisions/max_claims`;
- строит детерминированный `pack_id`;
- сохраняет `lex.norm_pack` и provenance event;
- возвращает `NormPackBuildResult` с `built_by` и `warnings`.

### `select_sources.py`

`select_doc_sources`:
- берет `request.doc_source_ids`, если заданы;
- иначе выбирает `doc.source` из fact log и фильтрует до документов `lex.corpus`.

`select_active_doc_versions`:
- primary path: `resolve_active_version(...)`;
- fallback path: temporal выбор напрямую из фактов, если index/pointer не готов;
- фильтрует документы по юрисдикции.

### `extract_norm_claims.py`

- Извлекает claims по выбранным provisions.
- Дедуплицирует claims и пишет `lex.norms.claim_set`.
- Поддерживает ограничение `max_claims` и добавляет warning-метки при деградации.

### `applicability.py`

- Строит `NormApplicability` из validity окна claim.
- Проверяет применимость нормы на заданную дату.

### `provider_registry.py`

- Реестр `NormPackProvider` с ранжированием по `domain/jurisdiction/version`.
- Bootstrap через `polisyos.norm_pack_providers`.

### `policies.py`

- Константы pipeline и policy ids.
- Default extractor: `lex.norm_extractor.regex_v1@1.0.0`.
- Default provisions: `article`, `point`, `subpoint`.

## Важные особенности

- Domain filter работает по keywords в `citation_label` и текстовом preview.
- Конфликты claims проходят через `fabric.claims.resolve_conflicts`.
- В отсутствие данных pipeline не всегда падает сразу, а фиксирует `warning:*` в результате.

## Связи

- Upstream: `policy-engine/src/polisyos/lex/corpus`.
- Зависимости: `polisyos.fabric.claims`, `polisyos.core.components`, `polisyos.ir.norm_pack`.
- Downstream: `policy-engine/src/polisyos/lex/legal_evaluation`, `policy-engine/src/polisyos/lex/simulator`.
