# schemas — ABI Schema Gate

Автоматизированная система контроля обратной совместимости публичных моделей данных.
Отслеживает JSON Schema снапшоты Pydantic-моделей из `ir` и `fabric`, детектирует breaking changes
и блокирует merge через CI при нарушении версионирования.

## Роль в системе

`schemas` реализует **Architectural Law C** — «контракты как источник правды».
Все компоненты, потребляющие IR-артефакты (Foundry, Lex, Scientist, Runtime),
полагаются на стабильность схем. Данная подсистема гарантирует, что изменения
в структуре моделей не сломают downstream-потребителей без явного версионного бампа.

```
Pydantic-модели (src/polisyos/ir/*, fabric/world/abi)
        │
        ▼
  gen_schema.py ──► schemas/snapshots/{ir,fabric}/*.schema.json
        │                       │
        │                  git commit
        │                       │
        ▼                       ▼
  pre-commit --check       CI: abi.yml
                                │
                           abi_diff.py
                           (baseline vs current)
                                │
                      ┌─────────┴─────────┐
                      │                   │
                  PASS/WARN            FAIL
                  (merge ok)     (блокирует merge)
```

## Структура

```
schemas/
├── abi_models.py                    # Реестр отслеживаемых моделей (single source of truth)
├── __init__.py
└── snapshots/
    ├── ir/                          # 31 JSON Schema снапшот IR-моделей
    │   ├── _manifest.json           # Метаданные: хеши, версии, приоритеты
    │   ├── trinity_bundle.schema.json
    │   ├── policy_spec.schema.json
    │   └── ...
    └── fabric/                      # 2 JSON Schema снапшота fabric-перечислений
        ├── _manifest.json
        ├── edge_kind.schema.json
        └── node_kind.schema.json
```

## Ключевые компоненты

### abi_models.py — реестр

Единственный файл, который нужно редактировать при добавлении/удалении отслеживаемой модели.
Определяет `ABIModelEntry` для каждой модели:

| Поле | Назначение |
|------|-----------|
| `abi_key` | Уникальный идентификатор модели |
| `fqn` | Полный Python-путь к классу (`polisyos.ir.policy_spec.PolicySpec`) |
| `module` | Целевая директория снапшотов: `ir` или `fabric` |
| `priority` | Уровень строгости: P0 / P1 / P2 |
| `compat_mode` | `strict` — любые добавления breaking; `tolerant` — optional-поля допустимы |
| `version_field` | Поле для отслеживания версии (по умолчанию `schema_version`) |
| `lifecycle` | `active` / `deprecated` |
| `aliases` | Альтернативные имена для детекции переименований |

Вспомогательные функции:
- `iter_abi_entries()` — все активные записи
- `select_abi_entries(filters)` — фильтрация по abi_key, module, priority, FQN

### snapshots/ — коммитные снапшоты

Генерируются автоматически из Pydantic-моделей. **Не редактируются вручную.**

Каждый `_manifest.json` содержит для каждой модели:
- `sha256_full` — хеш полной схемы (включая метаданные)
- `sha256_semantic` — хеш без title/description/$comment (для семантического сравнения)
- `schema_version`, `priority`, `compat_mode`, `lifecycle`

## Каталог моделей

### P0 — критические (breaking changes блокируют CI)

| Модель | Источник | Домен |
|--------|----------|-------|
| `trinity_bundle` | `ir.trinity.TrinityBundle` | Канонический бандл (ProblemFrame + PolicySpec + ModelSpec) |
| `problem_frame` | `ir.problem_frame.ProblemFrame` | Формулировка проблемы («Зачем?») |
| `policy_spec` | `ir.policy_spec.PolicySpec` | Спецификация политики («Что?») |
| `model_spec` | `ir.model_spec.ModelSpec` | Спецификация модели («Как?») |
| `norm_pack` | `ir.norm_pack.NormPack` | Пакет нормативных правил |
| `norm_rule` | `ir.norm_pack.NormRule` | Отдельное нормативное правило |
| `norm_ref` | `ir.norm_pack.NormRef` | Ссылка на норму |
| `claim` | `ir.world.claim.Claim` | Утверждение в мировой модели |
| `fact` / `fact_segment_manifest` | `ir.fact_log.*` | Факты и сегментные манифесты |
| `conflict_set` / `conflict_resolution` / `conflict_set_resolution` | `ir.world.conflict.*` | Конфликты и резолюции |
| `world_event` / `prov_activity` | `ir.world.event.*` | События и provenance |
| `edge_kind` / `node_kind` | `ir.world.abi.*` | Fabric-перечисления графа (модуль `fabric`) |

### P1 — важные (breaking changes → warning)

| Модель | Источник | Домен |
|--------|----------|-------|
| `causal_effect_report` | `ir.causal` | Каузальный анализ |
| `distributional_report` | `ir.distributional` | Дистрибуционный анализ |
| `hte_result` / `policy_recommendation` | `ir.hte` | Гетерогенные эффекты и рекомендации |
| `backtest_report` | `ir.backtest` | Бэктестинг политик |
| `uncertainty_envelope` | `ir.uncertainty` | Конверты неопределённости |
| `gate_context` / `gate_request` / `gate_decision` / `gate_event` | `ir.gate` | Governance gates |
| `doc_fragment` / `doc_meta` | `ir.world.doc` | Документные фрагменты |
| `trust_assessment` | `ir.world.trust` | Оценка доверия |
| `quality_report` | `ir.world.quality` | Отчёты качества |

### P2 — информационные

| Модель | Источник |
|--------|----------|
| `calibration_config` | `ir.calibration` |
| `data_view_request` | `ir.data_views` |

## Рабочий процесс

### Добавление новой модели

1. Создать Pydantic-модель в `src/polisyos/ir/` с полем `schema_version`
2. Добавить `ABIModelEntry` в `abi_models.py` (выбрать priority и compat_mode)
3. Запустить `python3 tools/gen_schema.py`
4. Закоммитить сгенерированные файлы в `snapshots/`

### Изменение существующей модели

1. Внести изменения в Pydantic-модель
2. Запустить `python3 tools/gen_schema.py` — увидеть diff в снапшотах
3. Если изменение breaking и модель P0 — поднять major-версию (`1.0` → `2.0`)
4. Закоммитить обновлённые снапшоты

### Команды

```bash
# Регенерация всех снапшотов
python3 tools/gen_schema.py

# Проверка актуальности (pre-commit / CI)
python3 tools/gen_schema.py --check

# Генерация для конкретных моделей
python3 tools/gen_schema.py --models policy_spec trinity_bundle

# Семантический diff с baseline
python3 tools/abi_diff.py --baseline schemas/snapshots --current /tmp/new_schemas
```

## CI-интеграция

**Pre-commit hook** (`abi-schema-check`): запускает `gen_schema.py --check` при изменениях
в `src/polisyos/{ir,fabric/world,core/canon,core/artifacts}/**/*.py`.

**GitHub workflow** (`.github/workflows/abi.yml`):
1. Генерирует текущие снапшоты
2. Извлекает baseline из target-ветки
3. Запускает `abi_diff.py` — строит отчёт с классификацией 27 типов изменений
4. Публикует sticky-комментарий в PR
5. Блокирует merge при вердикте `FAIL` (P0 breaking без version bump)

## Правила совместимости

| Изменение | strict | tolerant |
|-----------|--------|----------|
| Удаление поля | breaking | breaking |
| Добавление required-поля | breaking | breaking |
| Добавление optional-поля | breaking | compatible |
| Изменение типа поля | breaking | breaking |
| Ужесточение constraint (minLength↑, maxLength↓) | breaking | breaking |
| Удаление enum-значения | breaking | breaking |
| Добавление enum-значения | compatible | compatible |
| Изменение metadata (title, description) | compatible | compatible |

## Связи с другими модулями

| Модуль | Характер связи |
|--------|---------------|
| `ir` | **Источник** — Pydantic-модели, из которых генерируются схемы |
| `fabric/world` | **Источник** — ABI-перечисления (EdgeKind, NodeKind) |
| `tools/gen_schema.py` | **Генератор** — создаёт снапшоты из реестра |
| `tools/abi_diff.py` | **Валидатор** — семантический diff и breaking change detection |
| `foundry` | **Потребитель** — компиляция и исполнение Trinity-артефактов |
| `lex` | **Потребитель** — правовая оценка через PolicySpec |
| `scientist` | **Потребитель** — LLM-дизайн политик через TrinityBundle |
| `runtime` | **Потребитель** — исполнение политик |
