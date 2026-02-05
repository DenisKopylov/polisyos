# Runtime Module (runtime) (актуально на 2026-02-05)

Модуль `runtime` предоставляет низкоуровневые компоненты для исполнения программ и обеспечения воспроизводимости результатов. Включает чистые JAX функции и Environment Fingerprinting.

## Архитектура

### Core Runtime (`__init__.py`)
- **`step`** - Чистая JAX функция одного шага симуляции
- **`run_scan`** - Исполнение последовательности через `lax.scan`
- **`execute_program_batch`** - Batch исполнение для нескольких сценариев

### Environment Fingerprinting (`fingerprint.py`)
- **`EnvironmentFingerprint`** - Захват и валидация окружения для воспроизводимости
- **`DeterminismTier`** - Уровни гарантий детерминизма (STRICT_CPU, BEST_EFFORT_GPU, NONDETERMINISTIC)
- **`configure_determinism`** - Настройка JAX/XLA для детерминизма
- **Compatibility Scoring**: Оценка совместимости окружений

### NaN Guard (`nan_guard.py`)
- **`NaNGuard`** - Обнаружение NaN/Inf значений с диагностикой
- **`NaNDiagnostic`** - Детальная диагностика численных проблем
- **`NaNGuardReport`** - Полный отчёт о проверках с рекомендациями
- **`create_nan_guard_for_profile`** - Фабрика профилей валидации (strict/mvp/fast)
- **Performance Monitoring**: Баланс надёжности и производительности

## Core Runtime

### Основные функции исполнения

#### step (Чистая функция шага)

```python
def step(state, controls, root_key, t: int, static_bundle=None):
    """Чистая JAX функция одного шага симуляции"""
    return state, {"t": t, "controls": controls}
```

Принимает состояние, контролы и RNG ключ, возвращает новое состояние и трассировку. JIT-компилируема.

#### run_scan (Последовательное исполнение)

```python
def run_scan(initial_state, controls_seq, root_key, static_bundle=None):
    """Исполнение последовательности через lax.scan"""
    def _body(carry, control):
        state, key = carry
        key, sub = jax.random.split(key)
        next_state, trace = step(state, control, sub, t=0, static_bundle=static_bundle)
        return (next_state, key), trace

    (_, _), traces = jax.lax.scan(_body, (initial_state, root_key), controls_seq)
    return traces
```

Эффективное последовательное исполнение с автоматическим управлением RNG.

#### execute_program_batch (Batch исполнение)

```python
def execute_program_batch(initial_states, controls_seq, root_key, static_bundle=None):
    """Batch исполнение для нескольких сценариев"""
    batch_size = initial_states.shape[0]
    keys = jax.random.split(root_key, batch_size)
    return jax.vmap(_run_single)(initial_states, controls_seq, keys)
```

Параллельное исполнение нескольких сценариев с `jax.vmap`.

## Environment Fingerprinting

### DeterminismTier (Уровни детерминизма)

```python
class DeterminismTier(str, Enum):
    STRICT_CPU = "strict_cpu"        # Bit-for-bit на CPU (2-5x медленнее)
    BEST_EFFORT_GPU = "best_effort_gpu"  # Near-deterministic на GPU (~10% медленнее)
    NONDETERMINISTIC = "nondeterministic"  # Без гарантий (самый быстрый)
```

### EnvironmentFingerprint (Захват окружения)

```python
@dataclass(frozen=True, slots=True)
class EnvironmentFingerprint:
    python_version: str
    platform_system: str
    jax_version: str
    xla_flags: str
    determinism_tier: DeterminismTier
    random_seed: int
    captured_at: str
```

#### Основные возможности

```python
# Захват окружения (< 100ms)
fingerprint = EnvironmentFingerprint.capture(tier=DeterminismTier.BEST_EFFORT_GPU, seed=42)

# Оценка совместимости (1.0 = identical, 0.0 = incompatible)
compatibility_score = fingerprint.compatibility_score(other_fingerprint)

# Валидация для tier
warnings = fingerprint.validate_for_tier()
```

### configure_determinism

```python
def configure_determinism(tier: DeterminismTier) -> dict[str, str]:
    """Настройка JAX/XLA для детерминизма (вызывать ДО импорта JAX)"""
```

## NaN/Inf Guard (Защита от некорректных значений)

Runtime обнаружение NaN/Inf значений с понятными диагностиками. Включается только в STRICT профиле валидации.

### Основные компоненты

```python
from polisyos.foundry.runtime.nan_guard import NaNGuard, create_nan_guard_for_profile

# Создание guard
guard = NaNGuard(enabled=True, check_interval=1, max_diagnostics=100)

# Проверка состояния
is_valid = guard.check_state(state={"agents.income": income_array}, slot_id="agents.income",
                            mechanism_id="income_tax", time_step=42)

# Профили валидации
strict_guard = create_nan_guard_for_profile("strict")  # Каждый шаг
mvp_guard = create_nan_guard_for_profile("mvp")        # Каждые 10 шагов
fast_guard = create_nan_guard_for_profile("fast")      # Отключено
```

### Диагностика

```python
@dataclass(frozen=True)
class NaNDiagnostic:
    slot_id: str
    mechanism_id: str
    time_step: int
    nan_count: int
    inf_count: int
    possible_cause: str  # Эвристическая диагностика причин
```

### Отчёт

```python
report = guard.get_report()
if not report.ok:
    for diagnostic in report.diagnostics:
        print(f"NaN/Inf в {diagnostic.slot_id}: {diagnostic.possible_cause}")
```

### Производительность

- **Эффективность**: Быстрое обнаружение проблем с `jnp.any()`
- **Низкая нагрузка**: Диагностика без прерывания compute graph
- **Конфигурируемая частота**: Баланс надёжность/скорость

## Применение в Artifact System

```python
from polisyos.foundry.agent_sim.artifact import AgentPolicyArtifact

# Создание артефакта с fingerprint
artifact = AgentPolicyArtifact.from_trained_policy(
    policy=trained_policy,
    fingerprint=EnvironmentFingerprint.capture(tier=DeterminismTier.BEST_EFFORT_GPU, seed=42)
)

# Валидация совместимости перед загрузкой
is_valid, score, warnings = artifact.validate_environment(current_fingerprint)
```

## Производительность и оптимизации

- **JIT-компиляция**: Все функции автоматически компилируются
- **Векторизация**: `jax.vmap` для batch сценариев
- **Детерминированные RNG**: Стабильное распределение ключей
- **Минимальные зависимости**: Только чистые JAX функции

## Архитектурные принципы

1. **Чистота функций**: Без side effects
2. **Детерминизм**: Полный контроль недетерминизма
3. **Производительность**: JIT и векторизация
4. **Воспроизводимость**: Environment fingerprinting
5. **Надёжность**: NaN Guard для STRICT режима

## Связь с другими модулями

- **`agent_sim.artifact`**: Валидация политик через fingerprinting
- **`foundry.compiler`**: Компиляция программ для исполнения
- **`foundry.executor`**: Вызов runtime функций и валидации
- **`foundry.conflict_checker`**: Дополняет runtime валидацию
- **`foundry.cost_model`**: Оценка стоимости выполнения
- **`core.artifacts`**: Хранение артефактов с метаданными

---

Модуль `runtime` - фундамент для детерминированного исполнения программ с environment fingerprinting.