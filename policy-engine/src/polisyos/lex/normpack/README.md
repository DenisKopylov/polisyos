# normpack

Сборка нормативных пакетов (`NormPack`) — структурированных коллекций юридических норм для конкретной юрисдикции, даты и домена.

## Pipeline

`assemble_norm_pack()` выполняет полный pipeline:

```
select_sources → select_provisions → extract_norm_claims → resolve_conflicts → claims_to_norm_rules → NormPack
```

Альтернативный путь: если зарегистрирован `NormPackProvider` для юрисдикции/домена, он может предоставить готовый NormPack, минуя полный pipeline.

## Модули

### assemble_pack.py

Оркестратор pipeline. Ключевые этапы:

1. Нормализация запроса: валидация юрисдикции, домена, policy_id по паттерну `ID_PATTERN`
2. Bootstrap providers и extractors (через entry points)
3. Попытка получить NormPack от provider'а; при неудаче — полный pipeline
4. Выбор provisions, извлечение claims, разрешение конфликтов
5. Преобразование claims в `NormRule` с applicability и backend_metadata
6. Персистенция NormPack в CAS, запись мирового события `ASSEMBLE_NORM_PACK`

`claims_to_norm_rules()` — маппинг Claim → NormRule: определяет rule_type (OBLIGATION/PROHIBITION), строит provision_refs из citations, применяет applicability (юрисдикция + time window).

### select_sources.py

Выбор документов и их актуальных версий:

- `select_doc_sources()` — фильтрация doc_source по наличию `lex.corpus` в props; или использование явного списка `doc_source_ids`
- `select_active_doc_versions()` — резолюция через `corpus.versioning.resolve_active_version()` с fallback на прямой анализ фактов, фильтрация по юрисдикции
- `normalize_as_of()` — нормализация ISO-даты

### extract_norm_claims.py

Извлечение нормативных claims из текста provisions:

- Использует extractor из `fabric.claims.backends` (default: `lex.norm_extractor.regex_v1@1.0.0`)
- Конвертирует `ClaimCandidate` → `Claim` с полными цитатами, юрисдикцией, temporal validity
- Дедупликация по claim_id, применение max_claims бюджета
- Опциональная нормализация через `fabric.claims.normalize_claims()`

### policies.py

Константы и конфигурация:

- Политики: `DEFAULT_SELECTION_POLICY_ID`, `DEFAULT_CONFLICT_POLICY_ID`, `DEFAULT_TRUST_POLICY_ID`
- Pipeline IDs: `ASSEMBLY_PIPELINE_ID`, `NORM_CLAIM_EXTRACT_PIPELINE_ID`
- `DOMAIN_KEYWORDS` — словарь ключевых слов для фильтрации по доменам (roads, tax, labor)
- `DEFAULT_INCLUDED_PROVISION_KINDS` — {article, point, subpoint} (part и paragraph опционально)

### applicability.py

Определение применимости норм к контексту:

- `build_norm_applicability()` — создаёт `NormApplicability` из Claim (юрисдикция + time window)
- `applies_to_context()` — проверка: юрисдикция ∈ any_of И as_of ∈ [valid_from, valid_to]
- `applicability_key()` — sha256-хеш для сортировки и дедупликации

### provider_registry.py

Плагинируемая система NormPack providers:

- `NormPackProvider` (Protocol): `get_static_norm_pack(cas, jurisdiction, domain, as_of) → NormPack | ArtifactRef | str`
- `NormPackProviderRegistry` — глобальный реестр, резолюция по scoring (jurisdiction match + domain match + semver)
- Bootstrap через entry points `polisyos.norm_pack_providers`

## Зависимости

- `corpus` — ProvisionIndex, VersionIndex для выбора provisions
- `fabric.claims` — extractors, normalize_claims, resolve_conflicts
- `fabric.world` — мировые факты и события
- `ir.norm_pack` — NormPack, NormRule, NormRef
- `ir.world.claim` — Claim, ClaimSourceKind
- `core.components` — ComponentRegistry, entry points discovery
