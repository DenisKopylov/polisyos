# Agent Simulation Module (agent_sim)

## Обзор

Модуль `agent_sim` предоставляет высокоуровневый фреймворк для симуляции поведенчески-гетерогенных агентов в экономических моделях. Модуль реализует современные подходы к моделированию агентов с использованием глубокого обучения, графовых структур и эволюционных алгоритмов.

## Архитектура (актуально на 2026-02-05)

Модуль состоит из 32 модулей, организованных в следующие слои:

### 1. Состояние системы (State Layer)
- **`state.py`** - Определение состояний агентов, политики и глобального состояния
- **`population.py`** - Управление популяцией агентов (рождение, смерть, миграция)

### 2. Нейронные сети и RL (RL Layer)
- **`actor_critic.py`** - Actor-Critic архитектуры для обучения политик
- **`rl.py`** - PPO и другие алгоритмы reinforcement learning
- **`training.py`** - JIT-компиляция обучения

### 3. Механизмы симуляции (Mechanism Layer)
- **`mechanisms.py`** - Базовые экономические механизмы
- **`population_mechanisms.py`** - Демографические механизмы (рождение, смерть, старение)
- **`graph_mechanisms.py`** - Социальные механизмы через графовые сети
- **`distribution_mechanisms.py`** - Механизмы перераспределения
- **`temporal_mechanisms.py`** - Временные механизмы

### 4. Графовые структуры (Graph Layer)
- **`graphs.py`** - Создание и управление графами (scale-free, spatial, random)
- **`graph_executor.py`** - Исполнение на графовых структурах
- **`graph_observations.py`** - Наблюдения на графах

### 5. Распределения и метрики (Analysis Layer)
- **`distributions.py`** - Вычисление неравенства (Gini, Palma ratio)
- **`demographics.py`** - Демографические метрики и анализ
- **`metrics.py`** - Сбор и анализ метрик обучения
- **`analysis.py`** - Анализ поведения агентов
- **`dashboard.py`** - Дашборд для мониторинга
- **`visualization.py`** - Визуализация результатов

### 6. Эволюционные алгоритмы (Evolution Layer)
- **`evolution.py`** - CMA-ES и эволюционные стратегии
- **`modes.py`** - Разные режимы обучения (bilevel, MPC)
- **`mpc.py`** - Model Predictive Control

### 7. Временные аспекты (Temporal Layer)
- **`temporal.py`** - Временные наблюдения и маски
- **`temporal_executor.py`** - Исполнение с учётом времени

### 8. Исполнение и обучение (Execution Layer)
- **`executor.py`** - Исполнитель для симуляции агентов
- **`distribution_executor.py`** - Исполнение распределений
- **`population_executor.py`** - Исполнитель для популяции
- **`experiment.py`** - Настройка экспериментов
- **`jit_training.py`** - JIT-компиляция обучения
- **`training.py`** - Обучение моделей

### 9. Политики и правительство (Policy Layer)
- **`policy.py`** - Политики агентов
- **`government_policy.py`** - Политики правительства

### 10. Случайность и кредиты (Utility Layer)
- **`prng.py`** - Генерация псевдослучайных чисел
- **`credit_assignment.py`** - Назначение кредитов в обучении
- **`mechanism.py`** - Базовые механизмы симуляции

### 11. Artifact System (Artifact Layer)
- **`artifact.py`** - Хранение и загрузка обученных политик агентов с проверкой совместимости окружения
- **Environment Fingerprinting**: Захват окружения для воспроизводимости
- **Policy Compatibility**: Валидация совместимости политик между окружениями
- **Deterministic Artifacts**: Стабильные артефакты для reproducible ML

### 12. Value Function Iteration (VFI Layer)
- **`vfi.py`** - Value Function Iteration для решения динамических задач

### 8. Визуализация и анализ (Analysis Layer)
- **`analysis.py`** - Анализ поведения агентов
- **`dashboard.py`** - Дашборд для мониторинга
- **`visualization.py`** - Визуализация результатов

## Основные концепции

### Agent State (Состояние агента)

```python
@chex.dataclass(frozen=True)
class AgentState:
    active: Bool[Array, "n_agents"]           # Активен ли агент
    agent_id: Int[Array, "n_agents"]          # Уникальный ID
    birth_step: Int[Array, "n_agents"]        # Шаг рождения
    parent_id: Int[Array, "n_agents"]         # ID родителя
    wealth: Float[Array, "n_agents"]          # Богатство
    income: Float[Array, "n_agents"]          # Доход
    consumption: Float[Array, "n_agents"]     # Потребление
    savings: Float[Array, "n_agents"]         # Сбережения
    employed: Bool[Array, "n_agents"]         # Занят ли
    retired: Bool[Array, "n_agents"]          # На пенсии
    age: Int[Array, "n_agents"]               # Возраст
    skill_level: Float[Array, "n_agents"]     # Уровень навыков
    risk_aversion: Float[Array, "n_agents"]   # Отношение к риску
    n_connections: Int[Array, "n_agents"]     # Количество связей
```

### Global State (Глобальное состояние)

```python
@chex.dataclass(frozen=True)
class GlobalState:
    agents: AgentState                    # Состояние всех агентов
    policy: PolicyState                  # Глобальные параметры политики
    aggregates: AggregateState           # Агрегированные метрики
    distributions: DistributionState     # Распределения доходов/богатства
    graph: GraphState                    # Граф социальных связей
    population_manager: PopulationManager # Управление популяцией
    time_step: Int[Array, ""]            # Текущий временной шаг
    rng_key: chex.PRNGKey               # Ключ для RNG
```

### Mechanisms (Механизмы)

Механизмы определяют правила взаимодействия агентов и изменения состояния экономики:

#### Демографические механизмы
- **`AgingMechanism`** - Старение и выход на пенсию
- **`BirthMechanism`** - Рождение новых агентов
- **`DeathMechanism`** - Смерть агентов
- **`MigrationMechanism`** - Миграция между регионами

#### Экономические механизмы
- **`ConsumptionMechanism`** - Потребление и сбережения
- **`TaxationMechanism`** - Налогообложение
- **`LaborMarketMechanism`** - Рынок труда

#### Социальные механизмы
- **`InformationDiffusionMechanism`** - Распространение информации
- **`SocialInfluenceMechanism`** - Социальное влияние
- **`NetworkLendingMechanism`** - Кредитование через сеть

## Actor-Critic обучение

### Архитектура сетей

```python
class ActorCritic(eqx.Module):
    actor: ActorNetwork      # Политика (действия)
    critic: CriticNetwork    # Функция ценности (V-функция)
    advantage_net: AdvantageNetwork  # Преимущества (A-функция)
```

### Обучение PPO

```python
from polisyos.foundry.agent_sim.rl import ppo_loss

# Вычисление PPO loss
loss = ppo_loss(
    log_probs=log_probs,
    old_log_probs=old_log_probs,
    advantages=advantages,
    clip_ratio=0.2,
    value_loss_coef=0.5,
    entropy_coef=0.01
)
```

### Артефакты политики (AgentPolicyArtifact)

Артефакт политики фиксирует веса, метрики обучения и `EnvironmentFingerprint`,
чтобы можно было проверять совместимость окружения перед загрузкой и безопасно
делать hot-swap политик с одинаковыми I/O.

```python
from pathlib import Path

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.agent_sim.training import train_actor_critic_with_artifact
from polisyos.foundry.runtime.fingerprint import DeterminismTier

cas = FileSystemCAS(Path("./cas"))

trained, metrics, artifact = train_actor_critic_with_artifact(
    actor_critic=model,
    initial_state=state,
    config=training_config,
    make_executor=make_executor,
    run_id="run_20240127_001",
    tier=DeterminismTier.BEST_EFFORT_GPU,
    seed=42,
    cas=cas,
)

# Проверка совместимости перед загрузкой
from polisyos.foundry.runtime.fingerprint import EnvironmentFingerprint

current = EnvironmentFingerprint.capture(
    tier=DeterminismTier.BEST_EFFORT_GPU,
    seed=42
)
ok, score, warnings = artifact.validate_environment(current)
```

## Графовые структуры

### Типы графов

```python
from polisyos.foundry.agent_sim.graphs import (
    create_random_graph,
    create_scale_free_graph,
    create_spatial_graph,
    create_watts_strogatz_graph
)

# Создание scale-free графа (Барабаши-Альберт)
graph = create_scale_free_graph(n_nodes=1000, m=3)

# Создание пространственного графа
spatial_graph = create_spatial_graph(
    n_nodes=1000,
    positions=positions,  # [n_nodes, 2]
    threshold=0.1
)
```

### Graph State

```python
@chex.dataclass(frozen=True)
class GraphState:
    edges: EdgeList                    # Список рёбер
    node_features: Float[Array, "n_nodes d"]  # Признаки узлов
    edge_features: Float[Array, "n_edges d"]  # Признаки рёбер
    adjacency: SparseMatrix            # Матрица смежности
```

## Распределения и неравенство

### Метрики неравенства

```python
from polisyos.foundry.agent_sim.distributions import (
    compute_gini,
    compute_palma_ratio,
    compute_top_share,
    compute_bottom_share
)

# Коэффициент Джини
gini = compute_gini(incomes)

# Соотношение Палма (топ 10% / bottom 40%)
palma = compute_palma_ratio(incomes)

# Доля топ 1%
top_1_percent = compute_top_share(incomes, percentile=99)
```

### Distribution State

```python
@chex.dataclass(frozen=True)
class DistributionState:
    quantiles: Float[Array, "n_quantiles"]     # Квантили
    quantile_values: Float[Array, "n_quantiles"]  # Значения квантилей
    gini_coefficient: Float[Array, ""]         # Коэффициент Джини
    palma_ratio: Float[Array, ""]              # Соотношение Палма
    compressed_state: CompactDistributionState # Сжатое представление
```

## Эволюционные алгоритмы

### CMA-ES оптимизация

```python
from polisyos.foundry.agent_sim.evolution import run_cma_es

# Оптимизация параметров политики
result = run_cma_es(
    objective_fn=lambda params: evaluate_policy(params),
    initial_mean=jnp.zeros(10),
    initial_sigma=0.1,
    population_size=50,
    max_generations=100
)
```

## Демографические механизмы

### Жизненный цикл агента

```python
# Старение агентов
aging_mech = AgingMechanism(
    steps_per_year=12,
    retirement_age=65,
    fertility_start=20,
    fertility_end=45
)

# Рождение новых агентов
birth_mech = BirthMechanism(
    max_births_per_step=50,
    inheritance_config=InheritanceConfig(
        wealth_inheritance_rate=0.3,
        skill_inheritance_rate=0.5
    )
)
```

### Наследование

```python
@dataclass(frozen=True)
class InheritanceConfig:
    wealth_inheritance_rate: float = 0.3    # Доля наследуемого богатства
    skill_inheritance_rate: float = 0.5     # Доля наследуемых навыков
    minimum_inheritance: float = 1000.0     # Минимальное наследство
```

## Многоагентное обучение

### Режимы обучения

```python
from polisyos.foundry.agent_sim.modes import (
    run_mode_a,      # Одноуровневое обучение
    run_bilevel,     # Двухуровневое (правительство + агенты)
    run_mode_c       # Кооперативное обучение
)

# Двухуровневое обучение
bilevel_result = run_bilevel(
    config=BilevelConfig(
        agent_population=1000,
        government_lr=0.01,
        agent_lr=0.001,
        n_gov_steps=10,
        n_agent_steps=50
    )
)
```

## Временные аспекты

### Temporal Observations

```python
from polisyos.foundry.agent_sim.temporal import build_temporal_observations

# Создание временных наблюдений
temporal_obs = build_temporal_observations(
    current_state=current_state,
    history_states=history_buffer,  # [time_steps, batch_size, ...]
    time_window=12,
    include_differences=True,
    include_momentum=True
)
```

## Анализ и визуализация

### Behavior Analysis

```python
from polisyos.foundry.agent_sim.analysis import BehaviorAnalyzer

analyzer = BehaviorAnalyzer()
clusters = analyzer.cluster_agents(
    agent_states=states,
    n_clusters=5,
    features=['income', 'savings', 'consumption', 'risk_aversion']
)

# Анализ кластеров поведения
for i, cluster in enumerate(clusters):
    print(f"Cluster {i}: {len(cluster.agents)} agents")
    print(f"  Avg income: {cluster.avg_income}")
    print(f"  Consumption pattern: {cluster.consumption_pattern}")
```

### Dashboard

```python
from polisyos.foundry.agent_sim.dashboard import DashboardGenerator

dashboard = DashboardGenerator()
dashboard.add_metric("gdp", lambda state: state.gdp)
dashboard.add_metric("unemployment", lambda state: state.unemployment_rate)
dashboard.add_chart("income_distribution", plot_income_dist)

# Генерация отчёта
report = dashboard.generate_report(simulation_results)
```

## Производительность и оптимизации

### JIT-компиляция

```python
from polisyos.foundry.agent_sim.jit_training import create_jit_trainer

# JIT-компиляция обучения
jit_trainer = create_jit_trainer(
    model=actor_critic,
    optimizer=optax.adam(1e-3),
    loss_fn=ppo_loss,
    batch_size=64
)

# Быстрое обучение
loss = jit_trainer.step(params, batch)
```

### Параллельное исполнение

```python
from polisyos.foundry.agent_sim.population_executor import PopulationAwareExecutor

executor = PopulationAwareExecutor()
batch_results = executor.execute_batch(
    mechanisms=[consumption_mech, labor_mech],
    initial_states=batch_states,  # [batch_size, ...]
    n_steps=100
)
```

## Примеры использования

### Базовая симуляция с обучением

```python
from polisyos.foundry.agent_sim import (
    GlobalState, ActorCritic, train_actor_critic,
    AgingMechanism, ConsumptionMechanism, LaborMarketMechanism
)

# Инициализация состояния
state = GlobalState.empty(n_agents=1000, seed=42)

# Создание механизмов
mechanisms = [
    AgingMechanism(),
    ConsumptionMechanism(),
    LaborMarketMechanism()
]

# Создание модели RL
model = ActorCritic(
    obs_dim=10,      # Размерность наблюдений
    action_dim=5,    # Размерность действий
    hidden_dims=[64, 32]
)

# Обучение модели
trained_model = train_actor_critic(
    model=model,
    mechanisms=mechanisms,
    initial_state=state,
    n_episodes=1000,
    episode_length=50
)
```

### Симуляция с графовыми связями

```python
from polisyos.foundry.agent_sim import (
    create_spatial_graph, InformationDiffusionMechanism,
    SocialInfluenceMechanism
)

# Создание пространственного графа
graph = create_spatial_graph(
    n_nodes=1000,
    positions=agent_positions,
    threshold=0.05  # Максимальное расстояние для связи
)

# Добавление социальных механизмов
social_mechanisms = [
    InformationDiffusionMechanism(graph=graph),
    SocialInfluenceMechanism(graph=graph, influence_strength=0.1)
]

# Симуляция с социальными взаимодействиями
results = run_simulation(
    mechanisms=mechanisms + social_mechanisms,
    initial_state=state,
    n_steps=200
)
```

## Архитектурные принципы

1. **Масштабируемость**: Поддержка тысяч агентов через векторизацию
2. **Гибкость**: Плагинная архитектура для добавления новых механизмов
3. **Производительность**: JIT-компиляция и оптимизации для GPU
4. **Модульность**: Чёткое разделение между RL, механизмами и анализом
5. **Расширяемость**: Простое добавление новых типов агентов и взаимодействий

## Связь с другими модулями

- **`foundry.compiler`**: Компиляция политик в исполняемые графы
- **`foundry.runtime`**: Исполнение скомпилированных политик
- **`foundry.calibration`**: Калибровка параметров модели
- **`foundry.plugins`**: Интеграция в мульти-доменные симуляции

---

Модуль `agent_sim` предоставляет полный фреймворк для создания сложных симуляций поведенчески-гетерогенных агентов с современными методами машинного обучения и графового моделирования.