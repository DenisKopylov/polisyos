# Runtime Module (`polisyos.runtime`)

## Обзор

Модуль `polisyos.runtime` предоставляет **сквозную инфраструктуру управления жизненным циклом запусков** в системе симуляции политик. Это тонкий слой инфраструктуры, который обеспечивает:

- **Воспроизводимость**: Каждый прогон имеет уникальный `run_id` и полную трассировку
- **Аудит**: Полный лог всех операций и решений в формате JSON Lines
- **Артефакты**: Структурированное хранение результатов, IR, метрик симуляции
- **Бюджеты**: Отслеживание использования ресурсов (compute, memory, time)

Согласно **Закону D архитектуры** ("Любой прогон — воспроизводим и аудируем"), runtime является единственной точкой входа для создания и управления запусками.

## Архитектурная роль

### В контексте компиляторной трубы

```
NL → LLM → IR → Compilation → Runtime (UDF + Foundry) → Artifacts / DecisionPacket
```

Runtime стоит в конце трубы, собирая все артефакты в **"золотые артефакты"** — структурированные результаты прогона в директории `runs/<run_id>/`.

### Границы ответственности

- ✅ **Владеет**: run registry, артефакты, audit trail, кэш, логирование, сериализация
- ❌ **Не владеет**: бизнес-логика, JAX вычисления, БД, LLM, workflow orchestration

Runtime — это **чистая инфраструктура** без зависимостей от scientist/fabric/foundry.

## Структура артефактов

### Стандартная директория запуска

```
runs/<run_id>/
├── manifest.json              # RunManifest (паспорт прогона)
├── artifacts/                 # Структурированные результаты
│   ├── policy_ir/            # IR политики (YAML/JSON)
│   ├── simulation_results/   # Метрики симуляции
│   ├── compiled_model/       # Скомпилированная модель
│   └── data_views/           # Результаты UDF запросов
├── audit.jsonl               # Аудит-лог всех операций
└── [decision_packet.json]    # Финальный артефакт (опционально)
```

### RunManifest (паспорт прогона)

```python
class RunManifest(BaseModel):
    schema_version: str = "1.0"
    run_id: str                    # Уникальный идентификатор
    parent_run_id: Optional[str]   # Для иерархических прогонов
    status: str = "running"        # "running" | "completed" | "failed" | "pruned"
    started_at: str               # ISO timestamp
    finished_at: Optional[str]    # ISO timestamp при завершении
    generator: Dict[str, str]     # Кто создал (scientist.workflow, etc.)
    budgets: Dict[str, float]     # Исходные лимиты ресурсов
    budget_usage: Dict[str, float] # Фактическое использование
    pruning_reason: Optional[Dict[str, Any]]  # Причина досрочного завершения
    artifacts: List[ArtifactRef]  # Ссылки на все артефакты
```

## API Reference

### Управление жизненным циклом

#### `start_run()`
Инициализирует новый запуск с автоматической генерацией `run_id`.

```python
from polisyos.runtime import start_run

# Минимальный запуск
manifest = start_run()

# Запуск с метаданными и бюджетами
manifest = start_run(
    run_id="policy_sim_001",                    # Опционально, генерируется автоматически
    parent_run_id="draft_123",                  # Для иерархических прогонов
    generator={"component": "scientist.workflow", "version": "1.0"},
    budgets={"compute": 1000.0, "memory": 2048.0, "time": 3600.0}
)
```

#### `finalize_run()`
Завершает запуск с финальным статусом.

```python
from polisyos.runtime import finalize_run

# Успешное завершение
finalize_run(run_id="policy_sim_001", status="completed")

# Завершение с причиной pruning
finalize_run(
    run_id="policy_sim_001",
    status="pruned",
    pruning_reason={
        "type": "budget_exceeded",
        "limit": 1000.0,
        "actual": 1200.0,
        "resource": "compute"
    }
)
```

### Логирование артефактов

#### `log_artifact()`
Сохраняет артефакт прогона с автоматической категоризацией.

```python
from polisyos.runtime import log_artifact

# Логирование Policy IR
policy_ir = {"policies": [...], "objectives": [...]}
log_artifact(
    run_id="policy_sim_001",
    artifact_type="policy_ir",
    payload=policy_ir,
    step="draft",
    filename="policy_draft_v1.yaml"
)

# Логирование результатов симуляции
simulation_results = {
    "metrics": {"efficiency": 0.85, "fairness": 0.72},
    "timesteps": 100,
    "convergence": True
}
log_artifact(
    run_id="policy_sim_001",
    artifact_type="simulation_results",
    payload=simulation_results,
    step="simulate",
    schema_version="1.0"
)

# Логирование data view результатов
panel_data = pd.DataFrame(...)  # Результат UDF запроса
log_artifact(
    run_id="policy_sim_001",
    artifact_type="data_views",
    payload=panel_data.to_dict('records'),
    media_type="application/json",
    step="compile_data"
)
```

### Аудит и бюджеты

#### `append_audit()`
Добавляет запись в audit trail прогона.

```python
from polisyos.runtime import append_audit

# Логирование этапа workflow
append_audit("policy_sim_001", {
    "timestamp": "2024-01-01T10:00:00Z",
    "event": "workflow_step_started",
    "step": "validate_ir",
    "details": {"ir_size": 1500, "entities_count": 25}
})

# Логирование решения governor
append_audit("policy_sim_001", {
    "timestamp": "2024-01-01T10:05:00Z",
    "event": "governor_decision",
    "decision": "needs_revision",
    "issues": [
        {
            "issue_id": "INVALID_OBJECTIVE",
            "severity": "error",
            "loc": "objectives.0",
            "message": "Objective function not measurable"
        }
    ]
})
```

#### `update_budget_usage()`
Обновляет текущее использование ресурсов.

```python
from polisyos.runtime import update_budget_usage

# Обновление после симуляции
update_budget_usage("policy_sim_001", {
    "compute": 750.5,
    "memory": 1024.0,
    "time": 1800.0
})
```

## Типы артефактов

### Стандартные категории

- **`policy_ir`**: Policy Request IR в YAML/JSON формате
- **`simulation_results`**: Метрики и результаты симуляции
- **`compiled_model`**: Скомпилированная JAX модель
- **`data_views`**: Результаты UDF запросов (панели, сети)
- **`validation_report`**: Отчеты валидации IR
- **`gradient_health`**: Метрики здоровья градиентов
- **`audit_trail`**: Автоматически создается из audit.jsonl

### ArtifactRef модель

```python
class ArtifactRef(BaseModel):
    artifact_type: str              # Категория артефакта
    path: str                      # Путь к файлу относительно runs/
    media_type: str = "application/json"
    schema_version: Optional[str]  # Версия схемы для структурированных данных
    step: Optional[str]           # Этап workflow, на котором создан
    created_at: str               # ISO timestamp создания
```

## Аудит-лог

### Формат JSON Lines

```jsonl
{"timestamp": "2024-01-01T10:00:00Z", "event": "run_started", "run_id": "policy_sim_001"}
{"timestamp": "2024-01-01T10:00:05Z", "event": "ir_drafted", "tokens_used": 1250}
{"timestamp": "2024-01-01T10:01:00Z", "event": "validation_passed", "checks": ["schema", "limits", "cycles"]}
{"timestamp": "2024-01-01T10:02:00Z", "event": "simulation_started", "backend": "jax_cpu"}
{"timestamp": "2024-01-01T10:15:00Z", "event": "simulation_completed", "timesteps": 100, "converged": true}
{"timestamp": "2024-01-01T10:15:05Z", "event": "governor_decision", "verdict": "approve"}
```

### Автоматические события

- `run_started`: Создание RunManifest
- `artifact_logged`: Логирование каждого артефакта
- `budget_updated`: Изменение использования ресурсов
- `run_finalized`: Завершение с финальным статусом

## Интеграция с компонентами

### Scientist/Orchestrator

Runtime используется для структурированного хранения артефактов workflow:

```python
# В workflow узлах вместо прямой записи в logs/
from polisyos.runtime import start_run, log_artifact, finalize_run

def draft_ir_node(state):
    run_id = state.get("run_id")
    # ... генерация IR ...
    log_artifact(run_id, "policy_ir", ir_payload, step="draft")
    return state

def governor_node(state):
    run_id = state.get("run_id")
    decision = analyze_policy(state)
    append_audit(run_id, {"event": "governor_decision", "verdict": decision})
    return state
```

### Fabric/UDF

UDF результаты логируются как артефакты для трассировки:

```python
# В DataViewCompiler
def compile_panel(request: DataViewRequest) -> DataViewResult:
    run_id = request.run_id  # IR теперь включает run_id контекст
    # ... компиляция и исполнение ...
    log_artifact(run_id, "data_views", result_payload, step="compile_data")
    return result
```

### Foundry

Результаты симуляции и метрики здоровья градиентов:

```python
# В SimulationKernel
def run_simulation(model, state, run_id):
    # ... симуляция ...
    log_artifact(run_id, "simulation_results", metrics, step="simulate")

    # Логирование здоровья градиентов
    grad_health = compute_gradient_health(loss_fn, params)
    log_artifact(run_id, "gradient_health", grad_health, step="simulate")
```

## Воспроизводимость и трассировка

### Детерминированные прогоны

Каждый RunManifest включает:
- `seed`: Для детерминированных вычислений
- `backend`: JAX backend (cpu, gpu, tpu)
- `generator`: Версия и компонент, создавший прогон
- `library_versions`: Все версии зависимостей

### Миграции

Артефакты версионированы через `schema_version`:
- `v1.0`: Базовая схема
- `v1.1`: Добавление gradient_health
- `v2.0`: Изменение структуры simulation_results

## Производительность и надежность

### Оптимизации

- **Ленивая загрузка**: Manifest читается только при обновлении
- **JSON Lines streaming**: Аудит-лог поддерживает потоковое чтение
- **Автоматическое создание директорий**: Нет ошибок на отсутствующие пути

### Обработка ошибок

```python
# Runtime операции идемпотентны и безопасны
try:
    log_artifact(run_id, "policy_ir", payload)
except FileNotFoundError:
    # Создание директорий автоматически
    pass
except ValidationError:
    # Pydantic валидация на всех моделях
    append_audit(run_id, {"event": "artifact_validation_failed", "error": str(e)})
```

## Миграция с legacy подхода

### As-is проблемы

До runtime API компоненты писали артефакты "куда попало":
- Scientist: `logs/run_records/` + `logs/decision_packets/`
- Foundry: Прямые print statements или локальные файлы
- Fabric: Результаты в `integration.duckdb` без трассировки

### To-be преимущества

- **Единая структура**: Все артефакты в `runs/<run_id>/`
- **Ссылка на всё**: RunManifest как "паспорт прогона"
- **Воспроизводимость**: Полная трассировка для повторения
- **Аудит**: JSON Lines лог всех операций

## Примеры использования

### Полный цикл эксперимента

```python
from polisyos.runtime import start_run, log_artifact, append_audit, finalize_run

# 1. Инициализация
manifest = start_run(
    generator={"workflow": "policy_optimization", "version": "1.0"},
    budgets={"compute": 1000.0, "time": 3600.0}
)
run_id = manifest.run_id

# 2. Этап черновика IR
append_audit(run_id, {"step": "draft_started"})
policy_ir = generate_policy_draft()
log_artifact(run_id, "policy_ir", policy_ir, step="draft")

# 3. Валидация
validation_result = validate_ir(policy_ir)
log_artifact(run_id, "validation_report", validation_result, step="validate")

# 4. Компиляция данных
data_views = compile_data_views(policy_ir)
log_artifact(run_id, "data_views", data_views, step="compile_data")

# 5. Симуляция
simulation_result = run_simulation(policy_ir, data_views)
log_artifact(run_id, "simulation_results", simulation_result, step="simulate")

# 6. Решение governor
decision = governor_analyze(simulation_result)
append_audit(run_id, {"event": "final_decision", "verdict": decision})

# 7. Финализация
finalize_run(run_id, "completed")
```

### Прогоны с pruning

```python
# Превышение бюджета
update_budget_usage(run_id, {"compute": 1200.0})
finalize_run(run_id, "pruned", {
    "type": "budget_exceeded",
    "resource": "compute",
    "limit": 1000.0,
    "actual": 1200.0
})

# Валидация не пройдена
finalize_run(run_id, "pruned", {
    "type": "validation_failed",
    "issues": ["INVALID_IR_SCHEMA", "OBJECTIVE_NOT_MEASURABLE"]
})
```

## Тестирование

### Unit тесты

```bash
# Тестирование API
pytest tests/runtime/test_api.py

# Тестирование моделей
pytest tests/runtime/test_manifest.py
```

### Integration тесты

```bash
# Полный цикл с файловой системой
pytest tests/integration/test_runtime_workflow.py
```

### Контрактные тесты

```bash
# Валидация схем артефактов
pytest tests/contract/test_runtime_contracts.py
```

## Архитектурные гарантии

Runtime обеспечивает соблюдение **Закона D**:

- ✅ **Воспроизводимость**: Каждый прогон имеет run_id, seed, версии
- ✅ **Аудит**: Полный лог всех операций в JSON Lines
- ✅ **Артефакты**: Структурированное хранение всех результатов
- ✅ **Бюджеты**: Отслеживание и enforcement лимитов ресурсов

Runtime — это **инфраструктурный фундамент** для надежной, трассируемой и воспроизводимой системы симуляции политик.
