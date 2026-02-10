# Lex

Модуль юридического анализа policy engine. Обеспечивает полный цикл работы с нормативными документами: от загрузки и структурирования до оценки соответствия и симуляции изменений.

## Архитектура

```
lex/
  api.py              Фасад: делегирует вызовы в подсистемы
  types.py            Все value-объекты модуля (dataclass / Pydantic)
  errors.py           Иерархия исключений LexError

  corpus/             Корпус документов: ingest → structure → version index
  normpack/           Сборка нормативных пакетов из корпуса
  legal_evaluation/   Оценка легальности и генерация change proposals
  simulator/          What-if анализ: мутации NormPack, diff, impact-отчёты
```

Модуль построен как pipeline, где каждая подсистема трансформирует артефакты предыдущей:

```
raw bytes ──▶ corpus.ingest ──▶ corpus.structure ──▶ corpus.versioning
                                                          │
                   normpack.assemble_norm_pack  ◀──────────┘
                           │
              legal_evaluation.evaluate_legality
                    │               │
           LegalReportRef    ChangeProposalRef

             simulator (отдельный путь)
  old NormPack ──▶ mutator ──▶ diff ──▶ engine ──▶ NormImpactReport
```

## Публичный API

Весь публичный интерфейс экспортируется через `lex/__init__.py` и `lex/api.py`.

### Функции

| Функция | Назначение |
|---|---|
| `ingest_legal_doc_bytes()` | Загрузка документа: raw bytes → нормализация → опц. структурирование/чанкинг |
| `build_legal_structure()` | Парсинг нормализованного текста в иерархию статей/пунктов (ProvisionIndex) |
| `build_version_index()` | Построение временного индекса версий для doc_source |
| `resolve_active_version()` | Определение актуальной версии документа на заданную дату |
| `assemble_norm_pack()` | Полная сборка NormPack для юрисдикции/даты/домена |
| `evaluate_legality()` | Оценка соответствия с автоматическим bootstrap оценщиков |
| `propose_changes()` | Генерация предложений по изменениям на основе отчёта |

Все функции принимают `cas: FileSystemCAS` и `fact_log_root: Path` как обязательные параметры, что обеспечивает полную воспроизводимость через CAS и провенанс через fact log.

### Типы (types.py)

**Источники и результаты:**
- `LegalDocSource` — метаданные источника (URL/official_id, юрисдикция, даты действия, лицензия)
- `LexIngestResult` — результат загрузки: ссылки на артефакты всех этапов + мировые события
- `LexStructureResult` — результат структурирования: fragment_ids + provision_index

**Версионирование:**
- `LexVersionIndexResult` — результат построения индекса версий
- `ActiveVersionStrategy` — стратегия выбора версии (mode, tie-breaker, semantics)
- `ActiveVersionResult` — выбранная версия с объяснением логики выбора

**NormPack:**
- `NormPackBuildRequest` — запрос сборки (юрисдикция, дата, домен, политики, бюджеты)
- `NormPackBuildResult` — полный результат сборки с трассировкой всех промежуточных артефактов
- `NormPackBudgets` — ограничения: max_docs, max_provisions, max_claims

**Simulator:**
- `MutationIntent` — описание цели мутации (сценарий, причина)
- `NormPackMutator` — fluent builder для детерминистичных мутаций NormPack
- `NormDiff`, `NormChange`, `NormChangeType` — структурный diff двух NormPack
- `NormImpactReport` — отчёт о влиянии: compliance deltas, affected KPIs, blockers/warnings

## Подсистемы

### corpus

Управление корпусом юридических документов. Три этапа обработки:

1. **ingest** — загрузка raw bytes через `fabric.docs`, обогащение DocMeta свойствами `lex.*` (effective_from, jurisdiction, published_at), запись мировых событий
2. **structure** — парсинг нормализованного текста в иерархию правовых элементов. Поддерживает юрисдикции UA/RU/EN с правилами для статей, частей, пунктов, подпунктов и параграфов. Генерирует `DocFragment` артефакты и `ProvisionIndex`
3. **versioning** — построение `VersionIndex` по фактам из fact log (связи DOC_HAS_VERSION), резолюция активной версии с трёхуровневым fallback: effective_range → published_at → deterministic id

Хранение индексов (`index.py`): `ProvisionIndexV1`, `VersionIndexV1`, `DocSourcePropsV1` — Pydantic-модели с persist/load через CAS.

Подробнее: [corpus/README.md](corpus/README.md)

### normpack

Сборка нормативных пакетов — ключевой pipeline модуля. Этапы `assemble_norm_pack()`:

1. **select_sources** — выбор doc_source'ов из fact log, разрешение активных версий, фильтрация по юрисдикции
2. **select_provisions** — загрузка ProvisionIndex, фильтрация по домену (keyword matching), дедупликация, применение бюджетов
3. **extract_norm_claims** — извлечение нормативных claims через `fabric.claims` extractors, конвертация в `Claim` с привязкой к цитатам
4. **resolve_conflicts** — через `fabric.claims.resolve_conflicts()`: обнаружение противоречий, оценка доверия (TrustAssessment), выбор победителей
5. **claims_to_norm_rules** — преобразование canonical claims в `NormRule` с applicability, backend_metadata, provision_refs

Поддерживает плагинируемые NormPack providers через `provider_registry` (entry points `polisyos.norm_pack_providers`), которые могут предоставлять статические пакеты в обход полного pipeline.

Подробнее: [normpack/README.md](normpack/README.md)

### legal_evaluation

Оценка соответствия действий юридическим нормам. Архитектура:

- **evaluator_registry** — глобальный реестр оценщиков (`LexEvaluatorRegistry`). Встроенный `lex.eval.simple_v1@1.0.0` + плагины через entry points `polisyos.lex_evaluators`. Резолюция по component_id или base_id (latest version)
- **context_builder** (`LegalContextBuilder`) — загрузка PolicySpec, SimulationResult, Metrics, NormPack из CAS; маппинг наблюдаемых значений к правилам через: metrics → parameter_spec → direct_key fallback
- **backends/simple_v1** — rule evaluator: числовые сравнения (< <= = >= >), булевые и текстовые проверки, конвертация единиц (percent↔ratio, km↔m), severity levels (info/warning/blocker)
- **change_proposals** — на основе FAIL findings генерирует `policy_patch` (JSON Patch к PolicySpec) и `add_metric` actions

Подробнее: [legal_evaluation/README.md](legal_evaluation/README.md)

### simulator

What-if анализ изменений нормативного поля. Позволяет моделировать последствия изменений NormPack до их применения.

| Модуль | Назначение |
|---|---|
| `mutator.py` | `NormPackMutator` — fluent API для детерминистичных мутаций: add/remove/replace/modify norm, set effective date. Генерирует стабильный pack_id через `stable_world_id_from_canon` |
| `diff.py` | `diff_norm_packs()` — структурный diff двух NormPack: added/removed/modified/unchanged с field-level deltas |
| `engine.py` | `NormImpactAnalyzer` — оркестратор: diff → compliance passes (LegalPass, SafetyPass) → delta computation → KPI inference. Персистит NormDiff и NormImpactReport в CAS |
| `report.py` | Модели отчёта: `NormImpactReport`, `ComplianceDelta`, `ComplianceTransition`, `AffectedKPI` |
| `cli.py` | Утилиты: `load_norm_pack()` (из CAS или файла), `render_impact_markdown()` |

Интегрируется с `polisyos.core.governance` (LegalPass, SafetyPass, ValidationProfile) для запуска compliance-проверок на обеих версиях NormPack.

## Ошибки (errors.py)

Все исключения наследуют `LexError` и несут контекст: `stage`, `doc_source_id`, `doc_version_id`, `details`.

```
LexError
  ├── LexValidationError   — невалидные входные данные
  ├── LexIngestError       — ошибки загрузки документов
  ├── LexStructureError    — ошибки парсинга структуры
  ├── LexVersioningError   — ошибки версионирования
  ├── LexIndexError        — ошибки чтения/записи индексов
  └── LexNotReadyError     — отсутствует предварительный шаг (напр. не запущен build_legal_structure)
```

## Зависимости

### Внутренние (polisyos)

| Модуль | Что используется |
|---|---|
| `core.artifacts` | FileSystemCAS, ArtifactID, PutOptions, SchemaInfo |
| `core.canon` | Каноническая сериализация/десериализация |
| `core.contracts.lex` | LegalEvaluationRequest, LegalReportRef, ChangeProposalRef |
| `core.contracts.foundry` | SimulationResult, Metrics |
| `core.contracts.trinity` | TrinityBundle, PolicySpecRef, ModelSpecRef |
| `core.components` | ComponentRegistry, entry point discovery, HostAbi |
| `fabric.docs` | ingest_doc_bytes, normalize_doc, structure_doc, chunk_doc |
| `fabric.world` | Мировые факты, события, провенанс, fact segments |
| `fabric.claims` | Извлечение claims, нормализация, разрешение конфликтов |
| `fabric.io.db` | SimulationDB (опционально, для normpack assembly) |
| `ir.world` | DocMeta, DocFragment, WorldEvent, Claim, ConflictSet, TrustAssessment |
| `ir.norm_pack` | NormPack, NormRule, NormRef, RuleType |
| `ir.policy_spec` | PolicySpec, ParameterSpec |
| `ir.applicability` | NormApplicability, IdSelector, TimeWindow |
| `ir.citations` | AnchorKind, FragmentLocator |
| `core.governance` | LegalPass, SafetyPass, ValidationProfile (только simulator) |

### Внешние

| Библиотека | Где используется |
|---|---|
| `pydantic` | types.py, index.py, simulator models |
| `pandas` | versioning.py, select_sources.py — чтение fact log (parquet) |

## Юрисдикции

Модуль structure поддерживает правила парсинга для трёх юрисдикций:

| Код | Паттерн статей | Паттерн частей |
|---|---|---|
| UA | `Стаття N` | `Частина N` |
| RU | `Статья N` | `Часть N` |
| EN | `Article N` | `Part N` |

Юрисдикция определяется в порядке приоритета: `LexStructureOptions.jurisdiction` → `DocMeta.jurisdiction` → `DocMeta.props.lex.jurisdiction`.
