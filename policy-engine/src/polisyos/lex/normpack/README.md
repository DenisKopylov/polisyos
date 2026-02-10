# normpack

`lex.normpack` собирает `NormPack` для конкретных `jurisdiction + as_of (+ domain)`.

## Назначение

Подсистема превращает структурированные положения документов (`ProvisionIndex`) в машиночитаемые нормы (`NormRule`) с применимостью, ссылками на источники и metadata для последующей legal evaluation.

## Режимы сборки

### 1) Provider path

Если зарегистрирован `NormPackProvider` и локальные `doc_source` не выбраны, берется статический пакет через provider.

### 2) Pipeline path

Если provider недоступен/неприменим, запускается полный pipeline:

```text
select_doc_sources
  -> select_active_doc_versions
  -> select_provisions
  -> extract_norm_claims
  -> resolve_conflicts
  -> claims_to_norm_rules
  -> persist NormPack + world event
```

## Ключевые модули

### `assemble_pack.py`

Главный оркестратор. Делает:
- нормализацию и валидацию запроса (`jurisdiction`, `as_of`, бюджеты, policy ids);
- bootstrap providers/extractors через component registry;
- выбор документов и provisions;
- извлечение claims и conflict resolution;
- построение детерминированного `pack_id` (`stable_world_id_from_canon`);
- запись `NormPackBuildResult` с предупреждениями.

### `select_sources.py`

- `select_doc_sources`: берет явно переданные doc_source_ids или автонаходит источники `lex.corpus` в fact log;
- `select_active_doc_versions`: пытается резолвить через `corpus.versioning.resolve_active_version`, при неготовности индекса использует fallback по фактам.

### `extract_norm_claims.py`

Извлекает `Claim` из выбранных provisions через extractor backend, дедуплицирует и опционально нормализует claim sets.

### `applicability.py`

Строит `NormApplicability` (юрисдикция + окно валидности) и функции проверки применимости на дату.

### `provider_registry.py`

Регистрирует и ранжирует `NormPackProvider` (по юрисдикции, домену, версии компонента).

### `policies.py`

Константы pipeline: policy IDs, extractor ID, kinds артефактов, domain keywords, дефолтные ограничения.

## Важные особенности

- По умолчанию в selection идут `article`, `point`, `subpoint` (части/параграфы выключены по флагам в `policies.py`).
- Domain-фильтрация основана на keyword matching (`citation_label` + текстовый preview).
- Все отклонения и деградации маршрута собираются в `warnings` вместо немедленного падения pipeline.

## Связь с другими директориями

- Зависит от `policy-engine/src/polisyos/lex/corpus` (version/provision индексы).
- Использует `polisyos.fabric.claims` для extraction/normalization/conflict resolution.
- Производит `NormPack`, который потребляют:
  - `policy-engine/src/polisyos/lex/legal_evaluation`
  - `policy-engine/src/polisyos/lex/simulator`
