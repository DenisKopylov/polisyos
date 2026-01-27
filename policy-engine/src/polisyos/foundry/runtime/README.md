# Runtime Module (runtime)

## Обзор

Модуль `runtime` предоставляет низкоуровневые компоненты для исполнения скомпилированных программ и обеспечения воспроизводимости результатов. Модуль включает чистые JAX функции для исполнения и систему Environment Fingerprinting для валидации окружения.

## Архитектура

Модуль состоит из следующих компонентов:

### 1. Core Runtime (`__init__.py`)
- **`step`** - Чистая JAX функция для одного шага симуляции
- **`run_scan`** - Исполнение последовательности через `lax.scan`
- **`execute_program_batch`** - Batch исполнение для нескольких сценариев

### 2. Environment Fingerprinting (`fingerprint.py`)
- **`EnvironmentFingerprint`** - Захват и валидация окружения
- **`DeterminismTier`** - Уровни гарантий детерминизма
- **`configure_determinism`** - Настройка JAX для детерминизма

### 3. NaN Guard (`nan_guard.py`)
- **`NaNGuard`** - Обнаружение NaN/Inf значений во время исполнения
- **`NaNDiagnostic`** - Диагностическая информация о численных проблемах
- **`NaNGuardReport`** - Полный отчёт о проверках
- **`create_nan_guard_for_profile`** - Фабричная функция для разных профилей валидации

## Core Runtime

### Основные функции исполнения

#### step (Чистая функция шага)

```python
def step(state, controls, root_key, t: int, static_bundle=None):
    """Placeholder pure JAX step; returns state unchanged and empty trace."""
    return state, {"t": t, "controls": controls}
```

Функция `step` представляет собой чистую JAX функцию, которая:
- Принимает текущее состояние, контролы и RNG ключ
- Возвращает новое состояние и трассировку исполнения
- Может быть JIT-компилирована для максимальной производительности

#### run_scan (Последовательное исполнение)

```python
def run_scan(initial_state, controls_seq, root_key, static_bundle=None):
    """Run a lax.scan over controls_seq using pure step function."""

    def _body(carry, control):
        state, key = carry
        key, sub = jax.random.split(key)
        next_state, trace = step(state, control, sub, t=0, static_bundle=static_bundle)
        return (next_state, key), trace

    (_, _), traces = jax.lax.scan(_body, (initial_state, root_key), controls_seq)
    return traces
```

Функция `run_scan` использует `jax.lax.scan` для эффективного последовательного исполнения:
- Автоматически управляет RNG ключами
- Собирает трассировку для каждого шага
- Оптимизирована для последовательных вычислений

#### execute_program_batch (Batch исполнение)

```python
def execute_program_batch(initial_states, controls_seq, root_key, static_bundle=None):
    """
    Execute batched programs deterministically.

    Layout of keys: root_key -> split into [batch] subkeys (no extra leading split),
    so shape is [batch, 2] and stable for reproducibility.
    """
    batch_size = initial_states.shape[0]
    keys = jax.random.split(root_key, batch_size)

    def _run_single(state, controls, key):
        return run_scan(state, controls, key, static_bundle=static_bundle)

    return jax.vmap(_run_single)(initial_states, controls_seq, keys)
```

Функция `execute_program_batch` позволяет исполнять несколько сценариев параллельно:
- Использует `jax.vmap` для векторизации
- Детерминированное распределение RNG ключей
- Поддержка batch_size сценариев

## Environment Fingerprinting

### DeterminismTier (Уровни детерминизма)

```python
class DeterminismTier(str, Enum):
    """
    Determinism guarantee levels for simulation runs.

    STRICT_CPU: Bit-for-bit reproducibility on same CPU architecture.
                Uses deterministic ops, disables parallelism, fixed XLA flags.
                Trade-off: 2-5x slower training.

    BEST_EFFORT_GPU: Near-deterministic on same GPU model.
                     Uses cudnn deterministic algorithms where available.
                     May vary across different GPU models or CUDA versions.
                     Trade-off: ~10% slower than non-deterministic GPU.

    NONDETERMINISTIC: No determinism guarantees.
                      Fastest mode for hyperparameter search / exploration.
                      Results may vary between identical runs.
    """

    STRICT_CPU = "strict_cpu"
    BEST_EFFORT_GPU = "best_effort_gpu"
    NONDETERMINISTIC = "nondeterministic"
```

### EnvironmentFingerprint (Захват окружения)

```python
@dataclass(frozen=True, slots=True)
class EnvironmentFingerprint:
    """
    Lightweight environment capture for agent policy reproducibility.

    Captures only the fields that materially affect neural network
    computation results. Designed to be:
    - Fast to capture (<100ms)
    - Compact to serialize (<1KB JSON)
    - Sufficient for compatibility checking
    """

    python_version: str
    platform_system: str
    platform_machine: str

    jax_version: str
    jaxlib_version: str
    xla_flags: str
    x64_enabled: bool
    deterministic_ops: bool

    cpu_count: int
    cuda_version: str | None
    cudnn_version: str | None
    device_name: str | None

    determinism_tier: DeterminismTier
    random_seed: int

    captured_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
```

#### Захват окружения

```python
@classmethod
def capture(cls, tier: DeterminismTier, seed: int) -> "EnvironmentFingerprint":
    """
    Capture current environment for artifact storage.

    Performance target: < 100ms (no subprocess calls for fast path).
    """
    # Автоматически захватывает:
    # - Версии Python, JAX, JAXlib
    # - Архитектуру CPU/GPU
    # - XLA флаги и настройки детерминизма
    # - Время захвата
```

#### Compatibility Scoring (Оценка совместимости)

```python
def compatibility_score(self, other: "EnvironmentFingerprint") -> float:
    """
    Calculate compatibility score with another environment.

    Returns:
        1.0: Identical environments (bit-exact reproducibility expected)
        0.8-0.99: Minor differences (likely reproducible with warnings)
        0.5-0.79: Moderate differences (results may vary)
        0.0-0.49: Critical differences (reproducibility not guaranteed)
    """
```

#### Валидация для tier

```python
def validate_for_tier(self) -> list[str]:
    """Validate that environment matches claimed determinism tier."""
    warnings: list[str] = []

    if self.determinism_tier == DeterminismTier.STRICT_CPU:
        if self.device_name and "gpu" in self.device_name.lower():
            warnings.append("STRICT_CPU tier claimed but running on GPU device")

        if not self.deterministic_ops:
            warnings.append("STRICT_CPU tier requires XLA_FLAGS=--xla_gpu_deterministic_ops=true")

    elif self.determinism_tier == DeterminismTier.BEST_EFFORT_GPU:
        if not self.cuda_version:
            warnings.append("BEST_EFFORT_GPU tier claimed but no CUDA detected")
```

### configure_determinism (Настройка детерминизма)

```python
def configure_determinism(tier: DeterminismTier) -> dict[str, str]:
    """
    Configure JAX/XLA for the specified determinism tier.

    Returns dict of environment variables that should be set.

    WARNING: Must be called BEFORE importing JAX for flags to take effect.
    """
    env_vars: dict[str, str] = {}

    if tier == DeterminismTier.STRICT_CPU:
        env_vars["JAX_PLATFORMS"] = "cpu"
        env_vars["XLA_FLAGS"] = "--xla_gpu_deterministic_ops=true"
        env_vars["XLA_FLAGS"] += " --xla_cpu_multi_thread_eigen=false"
        env_vars["OMP_NUM_THREADS"] = "1"
        env_vars["MKL_NUM_THREADS"] = "1"

    elif tier == DeterminismTier.BEST_EFFORT_GPU:
        env_vars["XLA_FLAGS"] = "--xla_gpu_deterministic_ops=true"
        env_vars["TF_CUDNN_DETERMINISTIC"] = "1"

    return env_vars
```

## NaN/Inf Guard (Защита от некорректных значений)

### Обзор

NaN Guard предоставляет runtime обнаружение NaN и Inf значений с понятными диагностиками вместо криптичных JAX traceback'ов. Включается только в STRICT профиле валидации для отладки.

### Основные компоненты

#### NaNGuard (Основной класс)

```python
from polisyos.foundry.runtime.nan_guard import NaNGuard

# Создание guard
guard = NaNGuard(
    enabled=True,        # Включить проверки
    check_interval=1,    # Проверять каждый шаг
    max_diagnostics=100  # Максимум диагностик
)

# Проверка состояния
is_valid = guard.check_state(
    state={"agents.income": income_array},
    slot_id="agents.income",
    mechanism_id="income_tax",
    time_step=42
)

if not is_valid:
    print("Обнаружены NaN/Inf значения")
```

#### NaNDiagnostic (Диагностика)

```python
@dataclass(frozen=True)
class NaNDiagnostic:
    slot_id: str = ...           # Затронутый слот
    mechanism_id: str = ...      # Механизм-источник
    time_step: int = ...         # Шаг симуляции
    nan_count: int = ...         # Количество NaN
    inf_count: int = ...         # Количество Inf
    sample_indices: list[int] = ...  # Примеры проблемных индексов
    possible_cause: str = ...    # Возможная причина
    value_stats: dict[str, float] = ...  # Статистика валидных значений
```

#### NaNGuardReport (Отчёт)

```python
report = guard.get_report()

print(f"Всего проверок: {report.checks_performed}")
print(f"Проблем не найдено: {report.ok}")
if not report.ok:
    print(f"Первая ошибка на шаге: {report.first_failure_step}")
    for diagnostic in report.diagnostics:
        print(f"- {diagnostic.slot_id}: {diagnostic.possible_cause}")
```

### Профили валидации

```python
from polisyos.foundry.runtime.nan_guard import create_nan_guard_for_profile

# STRICT: полная проверка каждый шаг
strict_guard = create_nan_guard_for_profile("strict")

# MVP: проверка каждые 10 шагов, меньше диагностик
mvp_guard = create_nan_guard_for_profile("mvp")

# FAST: проверки отключены
fast_guard = create_nan_guard_for_profile("fast")
```

### Эвристическая диагностика причин

Guard использует паттерны для диагностики наиболее вероятных причин NaN/Inf:

```python
CAUSE_PATTERNS = {
    "income": "Division by zero or negative sqrt in income calculation",
    "utility": "Log of non-positive value in utility function",
    "tax": "Tax rate outside [0, 1] range or division by zero",
    "consumption": "Negative consumption leading to log(negative)",
    "wealth": "Wealth went negative, causing downstream NaN",
    "labor": "Labor supply outside valid bounds",
    "price": "Price went to zero or negative",
    "rate": "Interest/discount rate computation overflow",
    "policy": "Policy network output outside valid action space",
}
```

### Интеграция в Executor

```python
# В executor'е перед merge patches
for mechanism_output in mechanism_outputs:
    for slot_id, value in mechanism_output.patches.items():
        guard.check_array(value, slot_id, mechanism_output.id, time_step)

# После завершения симуляции
nan_report = guard.get_report()
if not nan_report.ok:
    # Сохранить отчёт в artifact store
    artifact = nan_report.to_artifact()
    store.put_json(artifact, ...)
```

### Производительность

- **Эффективность**: Использует `jnp.any()` для быстрого обнаружения проблем
- **Низкая нагрузка**: Диагностика накапливается без прерывания compute graph
- **Конфигурируемая частота**: `check_interval` позволяет балансировать между надёжностью и скоростью
- **Ограничение диагностик**: `max_diagnostics` предотвращает переполнение памяти

## Применение в Artifact System

### Валидация окружения для политик агентов

```python
from polisyos.foundry.agent_sim.artifact import AgentPolicyArtifact
from polisyos.foundry.runtime.fingerprint import EnvironmentFingerprint, DeterminismTier

# Создание артефакта с fingerprint окружения обучения
artifact = AgentPolicyArtifact.from_trained_policy(
    policy=trained_actor_critic,
    run_id="run_20240127_001",
    steps=10000,
    loss=0.023,
    fingerprint=EnvironmentFingerprint.capture(
        tier=DeterminismTier.BEST_EFFORT_GPU,
        seed=42
    ),
)

# Проверка совместимости перед загрузкой политики
current = EnvironmentFingerprint.capture(tier=DeterminismTier.BEST_EFFORT_GPU, seed=42)
is_valid, score, warnings = artifact.validate_environment(current)

if not is_valid:
    print(f"Environment compatibility: {score:.2f}")
    for warning in warnings:
        print(f"Warning: {warning}")
```

## Производительность и оптимизации

### JIT-компиляция

Все функции runtime автоматически JIT-компилируются:

```python
step_jit = jax.jit(step)  # JIT-компилированная версия step
```

### Оптимизации для batch исполнения

- **`jax.vmap`**: Векторизация по батчу сценариев
- **`jax.lax.scan`**: Эффективное последовательное исполнение
- **Детерминированные RNG**: Стабильное распределение ключей

### Минимальные зависимости

Runtime модуль спроектирован с минимальными зависимостями:
- Не зависит от artifact store
- Не требует доступа к файловой системе
- Работает исключительно с чистыми JAX функциями

## Архитектурные принципы

1. **Чистота функций**: Все функции - чистые JAX функции без side effects
2. **Детерминизм**: Полный контроль над источниками недетерминизма
3. **Производительность**: JIT-компиляция и векторизация
4. **Воспроизводимость**: Environment fingerprinting для проверки совместимости
5. **Надёжность**: NaN Guard для обнаружения численных проблем в STRICT режиме
6. **Модульность**: Чёткое разделение между исполнением, fingerprinting и валидацией

## Связь с другими модулями

- **`agent_sim.artifact`**: Использует fingerprinting для валидации политик
- **`foundry.compiler`**: Компилирует программы для исполнения в runtime
- **`foundry.executor`**: Вызывает runtime функции и NaN Guard для валидации
- **`foundry.conflict_checker`**: Compile-time проверка конфликтов дополняет runtime валидацию
- **`foundry.cost_model`**: Оценивает стоимость выполнения для оптимизации
- **`core.artifacts`**: Хранит артефакты с fingerprint и NaN Guard метаданными

---

Модуль `runtime` предоставляет фундаментальные компоненты для детерминированного и воспроизводимого исполнения программ с поддержкой environment fingerprinting.