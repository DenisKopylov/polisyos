# polisyos.runtime

Инфраструктура управления жизненным циклом экспериментов: запуск прогонов, хранение артефактов, аудит, бюджеты и replay-верификация результатов.

## Структура

```
runtime/
├── __init__.py      # Публичный API (17 экспортов)
├── api.py           # Lifecycle — start/finalize run, артефакты, аудит, бюджеты
├── http/            # HTTP middleware (cell router for tenant routing)
├── manifest.py      # Pydantic-модели RunManifest, ArtifactRef
└── replay.py        # Replay-планирование, completeness check, верификация
```

**849 строк кода в 4 модулях.** Плоский пакет без подпакетов.

## Роль в системе

Runtime находится в конце компиляторной трубы и собирает все артефакты эксперимента в единую структурированную директорию `runs/<run_id>/`:

```
NL → Scientist → IR → Compilation → Runtime (Foundry + Fabric) → runs/<run_id>/
```

Это чистая инфраструктура — без бизнес-логики, без JAX, без LLM. Обеспечивает воспроизводимость, аудит и переносимость согласно Закону D архитектуры.

## Два API-слоя

### Lifecycle API (`api.py`, 183 строки)

Управление жизненным циклом прогонов через файловую систему:

| Функция | Назначение |
|---------|-----------|
| `start_run()` | Инициализация прогона, генерация `run_id`, создание `manifest.json` |
| `log_artifact()` | Сохранение артефакта с переносимой ссылкой (`ArtifactRef`) |
| `append_audit()` | Запись в audit trail (`audit.jsonl`, формат JSON Lines) |
| `update_budget_usage()` | Обновление текущего потребления ресурсов |
| `finalize_run()` | Завершение прогона со статусом и (опционально) причиной pruning |
| `resolve_artifact_path()` | Разрешение абсолютного пути из `ArtifactRef` с учётом `run_root` |

Все операции идемпотентны и автоматически создают необходимые директории.

### Replay API (`replay.py`, 580 строк)

Подсистема воспроизводимости и верификации результатов:

| Функция / Тип | Назначение |
|---------------|-----------|
| `build_replay_plan()` | Построение плана replay: стратегия, seed, completeness |
| `completeness_check()` | Проверка полноты dependency graph через CAS-хранилище |
| `verify_replay()` | Верификация: `bit_exact` (побитовое совпадение) или `ci_bounded` (допуск по метрикам) |
| `ReplayStrategy` | Enum: `foundry` / `scientist` / `none` |
| `CompletenessLevel` | Enum: `complete` / `recoverable` / `incomplete` |
| `VerificationMode` | Enum: `bit_exact` / `ci_bounded` / `skip` |
| `CompletenessReport` | Детальный отчёт: missing/corrupted артефакты, reason codes, граф зависимостей |
| `VerificationResult` | Результат верификации с details и ссылками на original/replay |

Стратегия replay определяется автоматически по содержимому decision packet:
- **Foundry** — если есть `exec_plan_ref` + `registry_bundle_ref` + snapshot
- **Scientist** — если есть `trinity_bundle_ref` + `registry_bundle_ref` + snapshot

## Модели данных (`manifest.py`)

**`RunManifest`** — паспорт прогона (Pydantic, `extra="forbid"`):
- `run_id`, `parent_run_id` — идентификация и иерархия прогонов
- `status` — `running` → `completed` | `pruned`
- `started_at` / `finished_at` — временные метки (UTC ISO)
- `generator` — метаданные создателя (компонент, версия)
- `budgets` / `budget_usage` — лимиты и потребление ресурсов
- `artifacts` — список `ArtifactRef` со всеми артефактами прогона
- `environment_ref` / `environment_fingerprint` — захват окружения для воспроизводимости
- `pruning_reason` — причина pruning (если status = `pruned`)

**`ArtifactRef`** — переносимая ссылка на артефакт:
- `relative_path` (рекомендуемый) / `path` (legacy) — путь к файлу
- `artifact_type`, `media_type`, `schema_version`, `step`, `created_at`

## Структура директории прогона

```
runs/<run_id>/
├── manifest.json           # RunManifest
├── artifacts/
│   ├── policy_ir/          # Policy Surface IR
│   ├── simulation_results/ # Метрики симуляции
│   ├── compiled_model/     # Скомпилированная модель
│   ├── data_views/         # Результаты UDF-запросов (Fabric)
│   ├── environment_ref/    # Манифест окружения
│   └── registry_bundle_ref/# Registry bundle
├── audit.jsonl             # Audit trail (JSON Lines)
└── decision_packet.json    # Финальный артефакт (опционально)
```

## Зависимости

### Runtime зависит от

| Модуль | Что используется | Где |
|--------|-----------------|-----|
| `core.contracts.foundry` | `EnvironmentManifestRef`, `ExecPlan`, `Metrics`, `SimulationResult` | manifest.py, replay.py |
| `core.artifacts.environment` | `capture_environment`, `compare_environments`, `EnvironmentManifest` | replay.py |
| `core.artifacts.graph` | `DependencyGraph`, `resolve_dependency_graph`, `NodeStatus` | replay.py |
| `core.artifacts.ids` | `ArtifactID` | replay.py |
| `core.artifacts.store` | `FileSystemCAS` | replay.py |
| `core.canon` | `from_canonical_bytes` | replay.py |
| `pydantic` | `BaseModel`, `Field`, `ConfigDict` | manifest.py |

Зависимость идёт строго вниз — от `core.artifacts` и `core.contracts`. Нет зависимостей от `scientist`, `fabric`, `foundry`.

### Кто зависит от runtime

| Потребитель | Что импортирует |
|------------|----------------|
| `scientist.replay_backend` | Весь Replay API (`build_replay_plan`, `verify_replay`, `CompletenessLevel`, и др.) |
| `scientist.governance.preflight` | `log_artifact` |
| `core.audit.assembler` | `RunManifest` (как `LegacyRunManifest`) |

## Тесты

```
tests/runtime/
├── test_runtime_manifest_paths.py   # Относительные пути, resolve_artifact_path (57 строк)
└── test_replay_runtime.py           # completeness_check, verify_replay, стратегии (120 строк)

tests/scientist/
└── test_replay_backend.py           # Интеграция replay_backend + runtime.replay (92 строк)
```

## Особенности реализации

- **Переносимость**: `ArtifactRef.relative_path` + `RunManifest.run_root` позволяют перемещать `runs/` между машинами
- **Strict schema**: Pydantic с `extra="forbid"` на всех моделях — лишние поля вызывают ошибку
- **Файловая система**: Единственный backend хранения; нет поддержки S3/DB
- **Audit как append-only**: `audit.jsonl` пишется через `file.open("a")`, без индексации
- **Автовыбор стратегии replay**: `determine_replay_strategy()` анализирует payload и выбирает `foundry`/`scientist`/`none`
- **Граф зависимостей**: `completeness_check` строит полный граф через CAS и определяет missing/corrupted узлы
- **Seed resolution**: Каскадный поиск seed — `replay.effective_seed` → `run_record.seed` → `payload.seed` → `exec_plan.random_seed` → default
