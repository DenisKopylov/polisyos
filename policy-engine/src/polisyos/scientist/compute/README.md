# Compute Layer: Спецификации задач и execution backends

**Интерфейсы для запуска симуляций и распределенных вычислений**

Compute Layer определяет интерфейсы и спецификации для запуска симуляций и распределенных вычислений, обеспечивая reproducible execution через детальные job specifications.

## Обзор

Папка `compute/` содержит компоненты для структурированного выполнения вычислительных задач. Реализует паттерн Job Specification с поддержкой различных execution backends (local, distributed).

## Архитектура

```
compute/
├── __init__.py           # Экспорт основных компонентов
├── job_spec.py          # Спецификации задач (JobSpec, JobKey, JobResult)
└── runner.py            # Execution backends (LocalBackend, RayBackend skeleton)
```

## Компоненты

### 📋 Job Specifications (job_spec.py)

Детальные спецификации для reproducible выполнения задач:

#### JobSpec
Основная спецификация задачи симуляции:
```python
class JobSpec(BaseModel):
    program_ref: ArtifactRef                    # Скомпилированная программа
    exec_plan_ref: ArtifactRef | None = None   # План выполнения
    state_snapshot_ref: ArtifactRef | None = None  # Начальное состояние
    seed: int = 0                             # Deterministic seed
    mode: str = "dev"                         # Режим выполнения
    required_metrics: list[str] = Field(default_factory=list)  # Требуемые метрики
    notes: list[str] = Field(default_factory=list)  # Комментарии
```

#### JobKey
Уникальный идентификатор задачи на основе content hash:
```python
class JobKey(BaseModel):
    value: str  # SHA256 hash от спецификации

    @staticmethod
    def from_spec(spec: JobSpec) -> "JobKey":
        """Генерация ключа из спецификации."""
        payload = json.dumps(spec.model_dump(mode="json", exclude_none=True), sort_keys=True)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return JobKey(value=f"job:{digest}")
```

#### JobResult
Результат выполнения задачи:
```python
class JobResult(BaseModel):
    job_key: JobKey
    state_delta_ref: ArtifactRef | None = None        # Изменения состояния
    metrics_ref: ArtifactRef | None = None            # Метрики
    environment_ref: ArtifactRef | None = None        # Окружение выполнения
    environment_fingerprint: str | None = None        # Fingerprint окружения
    state_snapshot_ref: ArtifactRef | None = None     # Финальное состояние
    simulation_results_ref: ArtifactRef | None = None # Суммарные результаты
    final_state: Any | None = None                    # Объект состояния
    issues: list[dict[str, Any]] = Field(default_factory=list)  # Проблемы
    warnings: list[str] = Field(default_factory=list)  # Предупреждения
```

### ⚙️ Execution Backends (runner.py)

Абстрактный интерфейс для различных сред выполнения:

#### RunnerBackend
Базовый интерфейс backend'а:
```python
class RunnerBackend:
    def run(
        self,
        *,
        cas_root: Path,
        program_ref: ArtifactRef,
        exec_plan_ref: ArtifactRef,
        base_state: Any,
        registry_content: Any,
        seed: int,
    ) -> ExecutionResult:
        """Запуск задачи в конкретном backend'е."""
        raise NotImplementedError
```

#### LocalBackend
Локальное выполнение через Foundry executor:
```python
class LocalBackend(RunnerBackend):
    def run(self, *, cas_root, program_ref, exec_plan_ref, base_state, registry_content, seed):
        store = FileSystemCAS(cas_root)

        # Выполнение через Foundry executor
        exec_artifacts = execute_program_graph(
            store,
            program_ref=program_ref,
            exec_plan_ref=exec_plan_ref,
            base_state=base_state,
            mechanism_registry=registry_content.mechanism_registry,
            # ... другие параметры
        )

        # Применение результатов
        final_state, applied = apply_state_delta_and_snapshot(...)

        return ExecutionResult(
            exec_artifacts=exec_artifacts,
            applied=applied,
            final_state=final_state
        )
```

#### RayBackend
Skeleton для распределенного выполнения:
```python
class RayBackend(RunnerBackend):
    """Подготовка к кластерному запуску симуляций."""

    def run(self, *, cas_root, program_ref, exec_plan_ref, base_state, registry_content, seed):
        raise NotImplementedError("RayBackend is not implemented yet.")
```

### 🔧 Runner Utilities

Вспомогательные функции для работы с job'ами:

#### run_job()
Основная функция выполнения задач:
```python
def run_job(
    spec: JobSpec,
    *,
    backend: RunnerBackend | None = None,
    registry_content: Any = None,
    base_state: Any = None,
    cas_root: Path | None = None,
) -> JobResult:
    """Execute a compiled job spec via the provided backend."""
```

#### resolve_backend()
Автоматическое разрешение backend'а:
```python
def resolve_backend(kind: str | None) -> RunnerBackend:
    backend_kind = (kind or os.getenv("POLISYOS_RUNNER_BACKEND") or "local").lower()
    if backend_kind == "ray":
        return RayBackend()
    return LocalBackend()
```

#### _summarize_state()
Извлечение summary метрик из состояния:
```python
def _summarize_state(state: Any) -> dict[str, Any]:
    """Извлечение ключевых метрик из JAX состояния."""
    if state is None:
        return {}

    summary = {}
    try:
        summary["avg_income"] = float(jnp.mean(state.agents.income))
        summary["n_agents"] = int(state.agents.income.shape[0])
    except Exception:
        pass

    try:
        summary["gov_balance"] = float(state.government_balance)
    except Exception:
        pass

    return summary
```

## API Использование

### Создание и выполнение задач

```python
from polisyos.scientist.compute.job_spec import JobSpec, JobKey
from polisyos.scientist.compute.runner import run_job, resolve_backend
from polisyos.core.artifacts.manifest import ArtifactRef

# Создание спецификации задачи
job_spec = JobSpec(
    program_ref=ArtifactRef(
        id="sha256:abcd1234...",
        media_type="application/octet-stream",
        size=1024
    ),
    exec_plan_ref=exec_plan_artifact,
    state_snapshot_ref=initial_state_artifact,
    seed=42,
    mode="production",
    required_metrics=["gdp", "unemployment", "income_inequality"],
    notes=["Эксперимент с прогрессивным налогообложением"]
)

# Получение уникального ключа
job_key = JobKey.from_spec(job_spec)
print(f"Job Key: {job_key.value}")

# Выполнение задачи
result = run_job(
    spec=job_spec,
    backend=resolve_backend("local"),  # или "ray"
    registry_content=loaded_registry,
    base_state=initial_economic_state,
    cas_root=Path("artifacts")
)

# Обработка результата
if result.issues:
    print(f"Issues: {result.issues}")
else:
    print(f"Job completed: {result.job_key.value}")
    print(f"Metrics available: {result.metrics_ref is not None}")
    print(f"State delta: {result.state_delta_ref is not None}")
```

### Работа с ExecutionResult

```python
from polisyos.scientist.compute.runner import ExecutionResult

# Результат выполнения содержит:
result = ExecutionResult(
    exec_artifacts=foundry_exec_artifacts,  # State delta, metrics, etc.
    applied=state_application_result,      # Applied snapshot
    final_state=jax_global_state           # Final JAX state object
)

# Сохранение summary в CAS
if result.final_state:
    summary = _summarize_state(result.final_state)
    summary_ref = store.put_json(summary, PutOptions(...))
```

### Интеграция с workflow

```python
from polisyos.scientist.orchestrator.flow_nodes import run_sim_node
from polisyos.scientist.orchestrator.state import ExperimentState

def run_sim_node(state: ExperimentState) -> ExperimentState:
    """Узел workflow для запуска симуляции."""

    # Создание job spec из state
    job_spec = JobSpec(
        program_ref=state["compiled_model"]["program_graph_ref"],
        exec_plan_ref=state["exec_plan_ref"],
        state_snapshot_ref=state["state_snapshot_ref"],
        seed=state.get("random_seed", 42),
        required_metrics=["gdp", "unemployment"]
    )

    # Выполнение
    job_result = run_job(job_spec, ...)

    # Обновление state
    return {
        **state,
        "simulation_results": job_result.final_state,
        "simulation_results_ref": job_result.simulation_results_ref,
        "job_result": job_result
    }
```

## Backend Types

### LocalBackend
- **Использование**: Development, testing, small-scale experiments
- **Преимущества**: Простота, отсутствие зависимостей, fast iteration
- **Ограничения**: Single machine, limited parallelism

### RayBackend (Future)
- **Использование**: Production, large-scale experiments, distributed simulation
- **Преимущества**: Cluster execution, horizontal scaling, fault tolerance
- **Статус**: Skeleton готов, implementation pending

### Custom Backends
Возможно добавление кастомных backend'ов:
```python
class KubernetesBackend(RunnerBackend):
    """Kubernetes-native execution."""

class CloudBackend(RunnerBackend):
    """Cloud provider execution (AWS Batch, GCP Cloud Run)."""
```

## Тестирование

### Unit тесты

```bash
# Тестирование compute layer
pytest tests/scientist/test_compute_*.py -v

# Job specifications
pytest tests/scientist/test_compute_job_spec.py -v

# Runner backends
pytest tests/scientist/test_compute_runner.py -v
```

### Mock execution

```python
def test_job_execution_mock():
    """Тестирование без реального выполнения."""
    spec = JobSpec(
        program_ref=mock_artifact_ref,
        seed=12345
    )

    # Mock backend для тестирования
    class MockBackend(RunnerBackend):
        def run(self, **kwargs):
            return ExecutionResult(
                exec_artifacts=None,
                applied=None,
                final_state={"mock": "state"}
            )

    result = run_job(spec, backend=MockBackend())
    assert result.job_key.value.startswith("job:")
```

### Integration тесты

```python
def test_full_job_lifecycle():
    """Тестирование полного цикла job execution."""
    # Создание спецификации
    spec = create_test_job_spec()

    # Выполнение через local backend
    result = run_job(spec, backend=LocalBackend(), ...)

    # Валидация результата
    assert result.state_delta_ref is not None
    assert result.metrics_ref is not None
    assert not result.issues
```

## Расширение

### Добавление нового backend'а

```python
from polisyos.scientist.compute.runner import RunnerBackend

class DockerBackend(RunnerBackend):
    """Выполнение в Docker контейнерах."""

    def run(self, *, cas_root, program_ref, exec_plan_ref, base_state, registry_content, seed):
        # 1. Создание Docker образа
        # 2. Mount CAS volumes
        # 3. Запуск контейнера
        # 4. Сбор результатов
        pass
```

### Расширение JobSpec

```python
class ExtendedJobSpec(JobSpec):
    """JobSpec с дополнительными параметрами."""

    timeout_seconds: int = Field(default=3600)          # Timeout выполнения
    priority: int = Field(default=0, ge=-10, le=10)     # Приоритет (для scheduling)
    resource_requirements: dict = Field(default_factory=dict)  # CPU, memory, GPU
    retry_policy: RetryPolicy = Field(default_factory=lambda: RetryPolicy())  # Повторы при failure
```

### Кастомные метрики

```python
def extract_custom_metrics(state: Any, requested_metrics: list[str]) -> dict:
    """Извлечение специфических метрик из состояния."""
    metrics = {}

    if "gdp" in requested_metrics:
        metrics["gdp"] = calculate_gdp(state)

    if "inequality" in requested_metrics:
        metrics["gini_coefficient"] = calculate_gini(state.agents.income)

    return metrics
```

## Связанные компоненты

- **Foundry**: `execute_program_graph`, `load_state_snapshot` для выполнения JAX программ
- **Core**: `FileSystemCAS`, `ArtifactRef` для управления артефактами
- **IR**: `ExecPlan`, `ProgramGraph` как входные артефакты
- **Orchestrator**: `run_sim_node` для интеграции в workflow

## Troubleshooting

### Job key collision

```
AssertionError: Job key already exists
```

**Решение**: Проверить уникальность параметров в JobSpec (seed влияет на key)

### Backend not available

```
NotImplementedError: RayBackend is not implemented yet
```

**Решение**: Использовать LocalBackend или реализовать RayBackend

### CAS access denied

```
PermissionError: Cannot access CAS root
```

**Решение**: Проверить права доступа к `cas_root` directory

### State loading failed

```
Exception: Failed to load snapshot: invalid artifact reference
```

**Решение**: Убедиться, что `state_snapshot_ref` существует в CAS

### Memory exhaustion

**Решение**: Уменьшить размер симуляции или добавить resource limits в JobSpec

### Execution timeout

**Решение**: Увеличить timeout в backend или оптимизировать программу