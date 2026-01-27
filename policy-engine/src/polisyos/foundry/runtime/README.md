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
5. **Модульность**: Чёткое разделение между исполнением и fingerprinting

## Связь с другими модулями

- **`agent_sim.artifact`**: Использует fingerprinting для валидации политик
- **`foundry.compiler`**: Компилирует программы для исполнения в runtime
- **`foundry.executor`**: Вызывает runtime функции для исполнения
- **`core.artifacts`**: Хранит артефакты с fingerprint метаданными

---

Модуль `runtime` предоставляет фундаментальные компоненты для детерминированного и воспроизводимого исполнения программ с поддержкой environment fingerprinting.