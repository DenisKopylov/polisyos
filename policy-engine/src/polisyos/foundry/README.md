# Polisyos Foundry: Policy Execution Engine

**Foundry** - высокопроизводительный execution engine для дифференцируемого исполнения экономических политик в Policy Engine. Предоставляет компилятор политик, patch-based runtime, калибровку параметров и математическую основу для моделирования экономических механизмов.

## Роль в архитектуре

Foundry - **policy execution backend** Policy Engine, отвечающий за компиляцию, калибровку и исполнение политик:

```
NL → LLM → IR (AST) → Foundry Compiler → Foundry Calibration → Foundry Runtime → Artifacts
```

Работает исключительно с JAX-технологиями:
- ✅ Дифференцируемые вычисления и JIT-компиляция
- ✅ Экономические механизмы (налоги, субсидии, рынок труда, очереди)
- ✅ Multi-fidelity симуляции
- ✅ Slot-based state management и patch operations
- ✅ Program graphs и execution plans
- ✅ Калибровка параметров на реальных данных
- ✅ Constraints engine для валидации ограничений
- ❌ Никаких БД, LLM или сетевых вызовов

## Технологический стек

- **JAX/JAXlib**: Основа всех вычислений и JIT-компиляции
- **Equinox**: OOP-обертка для JAX-модулей
- **Jaxtyping**: Статическая проверка размерностей тензоров
- **Chex**: Дополнительные проверки типов и форм
- **Pydantic**: Валидация конфигураций и схем

## Agent Simulation (Симуляция агентов)

Модуль `agent_sim` (32 модуля) предоставляет комплексный фреймворк для симуляции поведенчески-гетерогенных агентов с использованием ML, графовых структур и эволюционных алгоритмов.

### Ключевые возможности

- **Гетерогенные агенты**: Различные предпочтения, демография и поведение
- **Нейронные сети**: Actor-Critic архитектуры для обучения политик
- **Графовые структуры**: Социальные сети и взаимодействия агентов
- **Демографические процессы**: Рождение, старение, миграция
- **Метрики неравенства**: Gini, Palma ratio для анализа распределений
- **Эволюционные алгоритмы**: CMA-ES для оптимизации параметров
- **Временные аспекты**: Обработка последовательных данных
- **Artifact system**: Хранение политик с проверкой совместимости окружения

### Основные компоненты

```python
# Agent State с демографией и финансами
@chex.dataclass(frozen=True)
class AgentState:
    active: Bool[Array, "n_agents"]
    wealth: Float[Array, "n_agents"]
    income: Float[Array, "n_agents"]
    employed: Bool[Array, "n_agents"]
    age: Int[Array, "n_agents"]
    skill_level: Float[Array, "n_agents"]
    risk_aversion: Float[Array, "n_agents"]

# Actor-Critic обучение агентов
from polisyos.foundry.agent_sim import ActorCritic, train_actor_critic
model = ActorCritic(obs_dim=10, action_dim=5, hidden_dims=[64, 32])

# Метрики неравенства
from polisyos.foundry.agent_sim import compute_gini, compute_palma_ratio
```

### Artifact System
```python
from polisyos.foundry.agent_sim.artifact import AgentPolicyArtifact

# Создание артефакта с fingerprint окружения
artifact = AgentPolicyArtifact.from_trained_policy(
    policy=trained_policy,
    fingerprint=EnvironmentFingerprint.capture(tier=DeterminismTier.BEST_EFFORT_GPU, seed=42)
)

# Валидация совместимости перед загрузкой
ok, score, warnings = artifact.validate_environment(current_fingerprint)
```

## Архитектура (актуально на 2026-01-29)

Foundry состоит из следующих основных слоев:

### Core Layer (Ядро)
```
__init__.py         # Пустой инициализатор
base.py             # Абстрактный класс Mechanism и ComplexMechanism
types.py            # FidelityLevel enum (уровни точности)
utils.py            # Дифференцируемые утилиты (soft_step, soft_clamp, gradient_health)
loss.py             # Функции потерь для оптимизации политик
agent_metrics.py    # Метрики для анализа агентов
```

### Compiler Layer (Компилятор)
```
compiler.py         # Компиляция политик в ProgramGraph
layout.py           # Slot layout для state management
treasury.py         # Deterministic RNG management
conflict_checker.py # Compile-time проверка конфликтов
cost_model.py       # Модель оценки стоимости выполнения
```

### Runtime Layer (Исполнение)
```
patch_vm.py         # Patch-based виртуальная машина и merge rules
executor.py         # Исполнение программ с constraints и state management
constraints_engine.py # Движок ограничений и валидации
trace.py            # Система трассировки исполнения
merge_engine.py     # Движок для слияния патчей и состояний
runtime/            # Runtime модули для исполнения программ
├── __init__.py     # Чистые JAX функции (step, run_scan, execute_program_batch)
├── fingerprint.py  # Environment fingerprinting для воспроизводимости
└── nan_guard.py    # Защита от NaN/Inf значений во время исполнения
```

### Domain Layer (Модель предметной области)
```
domain/
├── __init__.py     # Инициализатор домена
├── state.py        # GlobalState, AgentState, FirmState, MarketState
└── schema.py       # Pydantic схемы конфигурации
```

### Mechanisms Layer (Механизмы)
```
agents.py           # Адаптивные агенты с нейронными сетями
fiscal.py           # Налоговые механизмы (IncomeTax, TaxSubsidy)
labor.py            # Механизм рынка труда
queue.py            # Механизм очередей с multi-fidelity
registry.py         # Регистрация и фабрика механизмов
specs.py            # Спецификации механизмов с валидацией
```

### Agent Simulation Layer (Симуляция агентов)
```
agent_sim/          # Комплексная симуляция агентов с ML (32 модуля)
├── __init__.py
├── actor_critic.py # Actor-Critic архитектуры для RL
├── analysis.py     # Анализ поведения агентов
├── artifact.py     # Artifact system для политик агентов
├── credit_assignment.py # Назначение кредитов в обучении
├── dashboard.py    # Дашборд для мониторинга
├── demographics.py # Демографические метрики
├── distribution_executor.py # Исполнение распределений
├── distributions.py # Метрики неравенства (Gini, Palma ratio)
├── evolution.py    # Эволюционные алгоритмы (CMA-ES)
├── executor.py     # Исполнитель для симуляции агентов
├── experiment.py   # Настройка экспериментов
├── government_policy.py # Политики правительства
├── graph_executor.py # Исполнение на графах
├── graph_mechanisms.py # Механизмы для графов
├── graphs.py       # Графовые структуры социальных связей
├── jit_training.py # JIT-компиляция обучения
├── mechanism.py    # Базовые механизмы симуляции
├── mechanisms.py   # Специфические механизмы
├── metrics.py      # Сбор метрик обучения
├── modes.py        # Режимы обучения (bilevel, MPC)
├── mpc.py          # Model Predictive Control
├── policy.py       # Политики агентов
├── population.py   # Управление популяцией
├── prng.py         # Генерация псевдослучайных чисел
├── rewards.py      # Функции вознаграждения
├── rl.py           # PPO и другие алгоритмы обучения
├── state.py        # Расширенные состояния агентов
├── temporal.py     # Временные аспекты
├── training.py     # Обучение моделей
└── visualization.py # Визуализация результатов
```

### Calibration Layer (Калибровка моделей)
```
calibration/        # Автоматическая калибровка параметров (7 модулей)
├── __init__.py     # Инициализатор калибровки
├── bijectors.py    # Биекции для ограничения параметров
├── calibrator.py   # Основной класс Calibrator для оптимизации
├── loss.py         # Функции потерь (MSE, Huber, weighted loss)
├── preflight.py    # Подготовка данных и конфигурации
├── pure_executor.py # Чистый JAX executor без side effects
├── report.py       # Отчёты калибровки (метрики качества, неопределённости)
└── README.md       # Подробная документация калибровки
```

### Plugins Layer (Плагины доменов)
```
plugins/            # Расширяемая система плагинов (12 модулей)
├── __init__.py     # Инициализатор плагинов
├── api.py          # High-level PolisySimulator API
├── cli.py          # Command-line interface
├── composite.py    # Мульти-доменные симуляции
├── core.py         # Протоколы плагинов и реестр
├── discovery.py    # Автообнаружение плагинов
├── economics/      # Экономический домен
│   ├── __init__.py
│   ├── mechanisms.py # Экономические механизмы
│   ├── objectives.py # Целевые функции (GDP, Gini, etc.)
│   ├── plugin.py   # EconomicsPlugin с механизмами
│   ├── rewards.py  # Функции вознаграждения
│   └── state.py    # Состояние экономического домена
└── README.md       # Документация плагинов
```

## Calibration (Калибровка моделей)

Модуль `calibration` (7 модулей) предоставляет инструменты для автоматической калибровки параметров экономических моделей на реальных данных с использованием градиентной оптимизации.

### Основные компоненты

```python
from polisyos.foundry.calibration import Calibrator, CalibratorInputs

# Конфигурация и запуск калибровки
inputs = CalibratorInputs(
    config=calibration_config,
    program_graph=program_graph,
    exec_plan=exec_plan,
    base_state=initial_state,
    raw_targets=real_data_targets
)

calibrator = Calibrator()
report = calibrator.calibrate(inputs)
```

### Функционал

- **Функции потерь**: MSE, Huber, weighted loss для разных целей
- **Биекции параметров**: Ограничение параметров (sigmoid, softplus для [0,1] и [0,∞))
- **Оптимизаторы**: Adam, L-BFGS, SLSQP
- **Отчёты**: Метрики качества (R², RMSE, MAE), временные ряды, неопределённости
- **Валидация**: Проверка ограничений и физической корректности

### Процесс калибровки

1. **Preflight**: Валидация конфигурации и подготовка данных
2. **Компиляция**: Создание оптимизируемой функции с автодифференцированием
3. **Оптимизация**: Градиентный спуск с биекциями для ограниченных параметров
4. **Анализ**: Метрики качества и оценки неопределённости
5. **Отчёт**: Сохранение результатов в artifact store

## Compile-time Conflict Detection

Модуль `conflict_checker` предоставляет статический анализатор для обнаружения конфликтов записи в слоты перед JAX-компиляцией. Работает на чистом Python и интегрируется с MergeEngine.

### Основные возможности

```python
from polisyos.foundry.conflict_checker import CompileTimeConflictChecker

# Создание анализатора и проверка ProgramGraph
checker = CompileTimeConflictChecker(slot_registry, merge_registry, strict_mode=True)
report = checker.check(program_graph)

if report.has_blockers():
    for conflict in report.conflicts:
        print(f"Конфликт в {conflict.slot_id}: {conflict.suggestion}")
```

### Типы конфликтов

- **MULTIPLE_WRITERS**: Несколько механизмов пишут в слот с правилом ERROR
- **UNSUPPORTED_RULE**: Неподдерживаемое правило слияния
- **MISSING_VALUE**: Слот не зарегистрирован в SlotRegistry

## Cost Model (Модель стоимости)

Модуль `cost_model` предоставляет эвристическую модель оценки стоимости выполнения программ с самокалибровкой на основе телеметрии.

### Основные возможности

```python
from polisyos.foundry.cost_model import CostModel, CostEstimate, CostBudget

# Оценка стоимости выполнения
cost_model = CostModel()
estimate = cost_model.estimate(
    program_graph=program_graph,
    n_agents=1000,
    time_steps=100,
    budget=CostBudget(max_total_ms=60000, max_memory_mb=8192)
)

print(f"Время: {estimate.estimated_total_ms}ms, Уверенность: {estimate.confidence}")
```

### Самокалибровка

```python
# Обновление на основе реальных измерений
cost_model.update_from_telemetry(mechanism_type="income_tax", actual_ms=25.0, n_agents=1000)
status = cost_model.get_calibration_status()
```

## Компилятор политик

### CompileArtifacts

Результат компиляции политики включает несколько артефактов:

```python
from polisyos.foundry.compiler import compile_surface_policy, CompileArtifacts

artifacts = compile_surface_policy(
    store=store,
    policy=policy_ir,
    mechanism_registry=mechanism_registry,
    slot_registry=slot_registry,
    merge_registry=merge_registry,
    strict_conflict_check=True,      # Проверка конфликтов
    cost_budget=CostBudget(),        # Бюджет стоимости
    n_agents=1000,                   # Размер симуляции для оценки
    time_steps=100                   # Длительность симуляции
)

# Доступные артефакты
policy_ref = artifacts.policy_ref           # Ссылка на исходную политику
program_ref = artifacts.program_ref         # Скомпилированный ProgramGraph
exec_plan_ref = artifacts.exec_plan_ref     # План исполнения с топологической сортировкой
slot_layout_ref = artifacts.slot_layout_ref # Layout слотов состояния (опционально)
treasury_plan_ref = artifacts.treasury_plan_ref  # План детерминированного RNG (опционально)
conflict_report = artifacts.conflict_report # Отчёт о конфликтах (опционально)
cost_estimate = artifacts.cost_estimate     # Оценка стоимости (опционально)
```

### Program Graph

Foundry компилирует политики из IR в **ProgramGraph** - ориентированный граф выполнения:

```python
from polisyos.core.contracts.foundry import ProgramGraph, ProgramNode, ProgramEdge

# Загрузка ProgramGraph из artifact store
program_graph = store.get_json(artifacts.program_ref)

# Структура графа
for node in program_graph.nodes:
    print(f"Node {node.node_id}: {node.op}")  # Узел с операцией

for edge in program_graph.edges:
    print(f"{edge.source} -> {edge.target}")  # Зависимости
```

ProgramGraph состоит из:
- **Nodes**: Узлы операций (механизмы, merge, constraints, data sources)
- **Edges**: Зависимости между узлами с указанием портов
- **Entrypoints**: Точки входа для исполнения (обычно "root")

### Execution Plan

После компиляции создается **ExecutionPlan** с топологическим порядком исполнения:

```python
from polisyos.core.contracts.foundry import ExecPlan

exec_plan = store.get_json(artifacts.exec_plan_ref)
print(f"Execution order: {exec_plan.order}")  # ['node1', 'node2', 'merge1', ...]
```

## Executor (Исполнитель программ)

Executor предоставляет высокоуровневый API для исполнения скомпилированных ProgramGraph'ов с поддержкой constraints, state management и логирования.

### Основные функции

```python
from polisyos.foundry.executor import execute_with_constraints, execute_single_step, execute_batch

# Исполнение с constraints
result = execute_with_constraints(
    program_graph=program_graph,
    initial_state=initial_state,
    exec_plan=exec_plan,
    store=store,
    constraint_registry=constraint_registry,
    slot_registry=slot_registry,
    mechanism_registry=mechanism_registry,
    merge_registry=merge_registry
)

# Step-by-step исполнение
step_result = execute_single_step(
    node_id="tax_mechanism_1",
    program_graph=program_graph,
    current_state=current_state,
    store=store,
    mechanism_registry=mechanism_registry
)

# Batch исполнение для нескольких сценариев
batch_result = execute_batch(
    program_graph=program_graph,
    initial_states=[state1, state2, state3],
    exec_plan=exec_plan,
    store=store
)
```

### State Management

Управляет state transitions через StateDelta и StateSnapshot, отслеживает метрики исполнения (время, память, patches applied).

## Patch-based Execution

Foundry использует slot-based архитектуру с patch-based изменениями состояния.

### Slot System

Механизмы записывают в слоты вместо прямого изменения state:

```python
slots_written = ["agents.income", "government.balance"]
slots_read = ["agents.income", "market.unemployment_rate"]
```

### Patch Operations

Механизмы генерируют патчи вместо прямых изменений:

```python
from polisyos.core.contracts.foundry import PatchOp

patches = [
    PatchOp(slot_id="agents.income", op="add", value_ref=tax_amount_ref)
]
```

### Merge Rules

При конфликтах применяются merge rules из patch_vm:

```python
from polisyos.foundry.patch_vm import merge_patch_records
from polisyos.ir.kernel import MergeRuleKind

# SUM, OVERRIDE, PRIORITY, ERROR
merged_patches = merge_patch_records(store, patch_records, slot_registry, merge_registry)
```

### Artifact-based патчи

Значения патчей сохраняются как артефакты в store для воспроизводимости.

## Runtime Execution

Runtime модуль предоставляет низкоуровневые компоненты для исполнения программ и обеспечения воспроизводимости.

### Environment Fingerprinting

```python
from polisyos.foundry.runtime.fingerprint import EnvironmentFingerprint, DeterminismTier

# Захват окружения для воспроизводимости
fingerprint = EnvironmentFingerprint.capture(tier=DeterminismTier.BEST_EFFORT_GPU, seed=42)

# Проверка совместимости окружений
compatibility_score = fingerprint.compatibility_score(other_fingerprint)
warnings = fingerprint.validate_for_tier()
```

### NaN/Inf Guard

Система обнаружения NaN/Inf значений с диагностиками:

```python
from polisyos.foundry.runtime.nan_guard import create_nan_guard_for_profile

# Создание guard для STRICT профиля
guard = create_nan_guard_for_profile("strict")

# Проверка состояния
for mechanism_id, patches in mechanism_outputs.items():
    for slot_id, value in patches.items():
        guard.check_array(value, slot_id, mechanism_id, time_step)

# Отчёт о проблемах
report = guard.get_report()
if not report.ok:
    for diagnostic in report.diagnostics:
        print(f"NaN/Inf в {diagnostic.slot_id}: {diagnostic.possible_cause}")
```

### Execution Flow

1. **Load Program**: ProgramGraph из artifact store
2. **Initialize State**: Начальное состояние экономики
3. **Execute Nodes**: Узлы в топологическом порядке
4. **NaN Guard Check**: Проверка на NaN/Inf (STRICT режим)
5. **Merge Patches**: Применение патчей с merge rules
6. **Check Constraints**: Валидация ограничений

### Runtime API

```python
from polisyos.foundry.runtime import step, run_scan, execute_program_batch

# Чистые JAX функции для исполнения
def step(state, controls, root_key, t: int, static_bundle=None, nan_guard=None):
    # Один шаг симуляции
    return state, {"t": t, "controls": controls}

# Batch исполнение
batch_results = execute_program_batch(initial_states, controls_seq, root_key, static_bundle)
```

## Основные понятия

### Fidelity Levels

Три уровня точности симуляции:

```python
from polisyos.foundry.types import FidelityLevel

class FidelityLevel(str, Enum):
    SURROGATE_FLUID = "fluid"      # Непрерывные потоки (уравнения)
    RELAXED_DISCRETE = "relaxed"   # Сглаженные события (Softmax/Sigmoid)
    HARD_DISCRETE = "hard"         # Честная дискретная симуляция
```

### Mechanism (Механизм)

Базовый класс для экономических механизмов с patch-first архитектурой:

```python
from polisyos.foundry.base import Mechanism

class Mechanism(eqx.Module):
    fidelity: FidelityLevel = FidelityLevel.SURROGATE_FLUID

    def emit_patches(self, state, key, *, target_mask=None):
        """Генерирует патчи вместо прямых изменений состояния"""
        return patches, key
```

### GlobalState

Экономическая модель с агентами, фирмами и рынком:

```python
@chex.dataclass(frozen=True)
class GlobalState:
    step: Int[Array, ""]                     # Текущий шаг
    agents: AgentState                       # Агенты (демография, финансы, занятость)
    firms: FirmState                         # Фирмы (производство, финансы, рынок)
    market: MarketState                      # Рынок (цены, занятость, ставки)
    government_balance: Float[Array, ""]     # Баланс правительства
    gdp: Float[Array, ""]                    # ВВП
```

## Доступные механизмы

### Основные механизмы

- **IncomeTax**: Подоходный налог на reported_income
- **TaxSubsidy**: Налоговые субсидии
- **LaborMarketMechanism**: Рынок труда с вероятностным распределением занятости
- **AdaptiveAgentMechanism**: Агенты с ML (нейронные сети, гибкие наблюдения/действия)
- **QueueMechanism**: Многоуровневые очереди с разными fidelity

```python
from polisyos.foundry.fiscal import IncomeTax
from polisyos.foundry.labor import LaborMarketMechanism
from polisyos.foundry.agents import AdaptiveAgentMechanism

# Примеры использования
tax = IncomeTax(rate=0.2, n_agents=1000)
labor = LaborMarketMechanism(employment_threshold=0.5)
agent = AdaptiveAgentMechanism(observation_space=["agents.income"], action_space={"type": "continuous"})
```

## Движок симуляции

### Patch-based Execution (Современный подход)

Foundry использует patch-based модель исполнения, где механизмы генерируют патчи изменений вместо прямых модификаций состояния. Это обеспечивает:

- **Идемпотентность**: одни и те же патчи всегда дают одинаковый результат
- **Детерминизм**: результаты воспроизводимы при одинаковых входах
- **Аудит**: все изменения логируются и могут быть проверены
- **Составляемость**: патчи можно комбинировать и трансформировать

#### Patch Generation (Генерация патчей)

Механизмы генерируют патчи через метод `emit_patches()`:

```python
from polisyos.foundry.base import Mechanism
from polisyos.core.contracts.foundry import UpdateOp

class ModernTax(Mechanism):
    def emit_patches(self, state, key, *, target_mask=None):
        # Вычисляем изменения
        tax_amounts = state.agents.income * self.tax_rate

        # Генерируем патчи вместо прямых изменений
        patches = {
            "agents.income": [
                UpdateOp(delta=-tax_amounts, mask=target_mask)
            ],
            "government.balance": [
                UpdateOp(delta=jnp.sum(tax_amounts), mask=None)
            ]
        }
        return patches, key
```

#### Merge Rules (Правила слияния)

При конфликтах патчей применяются правила слияния из slot registry:

```python
from polisyos.ir.kernel import MergeRuleKind

# Поддерживаемые виды merge rules
merge_kinds = [
    MergeRuleKind.SUM,        # Складывать изменения (для балансов)
    MergeRuleKind.OVERRIDE,   # Перезаписывать по приоритету
    MergeRuleKind.PRIORITY,   # Выбирать по явному приоритету
    MergeRuleKind.ERROR       # Запрещать конфликты
]
```

#### Constraints Engine (Движок ограничений)

Валидация ограничений после применения патчей:

```python
from polisyos.foundry.constraints_engine import check_constraints

result = check_constraints(
    constraint_registry=constraint_registry,
    slot_registry=slot_registry,
    merged_ops=patch_ops,
    state_before=state
)

if result.violations:
    print(f"Найдено нарушений: {len(result.violations)}")
    for violation in result.violations:
        print(f"- {violation}")
```

## Функции потерь и оптимизация

### Policy Loss Function

Функция потерь для градиентной оптимизации политик:

```python
import jax.numpy as jnp
from polisyos.foundry.domain.state import GlobalState

def policy_loss_fn(final_state: GlobalState, min_balance: float = -1000.0) -> float:
    # Максимизация дохода (минимизация отрицательного дохода)
    avg_income = jnp.mean(final_state.agents.income)
    objective_loss = -avg_income / 1000.0

    # Штраф за нарушение бюджетных ограничений
    balance = final_state.government_balance
    violation = min_balance - balance
    penalty = jnp.maximum(0.0, violation) ** 2

    return objective_loss + 1000.0 * penalty
```

## Регистр механизмов

### Создание механизма через Intervention

```python
from polisyos.ir.contract import Intervention
from polisyos.foundry.registry import create_mechanism

# IR контракт из scientist
intervention = Intervention(
    mechanism_type="income_tax",
    parameters={"rate": 0.15}
)

# Создание механизма
mechanism = create_mechanism(intervention, n_agents=1000, n_firms=100)
```

### Доступные механизмы

```python
from polisyos.foundry.registry import MECHANISM_REGISTRY

# Доступные механизмы в registry
mechanisms = {
    "adaptive_agent": "AdaptiveAgentMechanism", # Адаптивные агенты с ML
    "tax_subsidy": "TaxSubsidy",           # Налоговые субсидии
    "income_tax": "IncomeTax",             # Подоходный налог
    "labor_market": "LaborMarketMechanism", # Рынок труда
    "queue": "QueueMechanism"              # Механизм очередей
}
```

## Спецификации механизмов

### Валидация параметров

```python
from polisyos.foundry.specs import validate_mechanism_params

# Проверка параметров перед созданием
try:
    validate_mechanism_params("income_tax", {"rate": 0.15})
    print("Параметры валидны")
except ValueError as e:
    print(f"Ошибка валидации: {e}")
```

### Структура спецификации

```python
MECHANISM_SPECS = {
    "income_tax": MechanismSpec(
        name="income_tax",
        required_params={"rate"},
        param_ranges={"rate": (0.0, 1.0)},
        param_units={"rate": "ratio"},
        description="Подоходный налог"
    )
}
```

## Утилиты

### Дифференцируемые функции

```python
from polisyos.foundry.utils import soft_step, soft_clamp

# Дифференцируемая ступенька
smooth_threshold = soft_step(x, k=10.0)

# Дифференцируемое ограничение
clamped_value = soft_clamp(x, 0.0, 1.0)
```

### Анализ градиентов

```python
from polisyos.foundry.utils import gradient_health

# Проверка здоровья градиентов
health_report = gradient_health(gradients)
if health_report.vanishing:
    print("Градиенты затухают - проблема с learning!")
```

### Trace System (Система трассировки)

Отслеживание исполнения программ для отладки и анализа:

```python
from polisyos.foundry.trace import TraceEvent, TraceSlice

# Создание события трассировки
event = TraceEvent(
    phase="execution",
    event="node_executed",
    payload={
        "node_id": "tax_mechanism_1",
        "execution_time": 0.023,
        "patches_generated": 42
    }
)

# Срез трассировки для анализа
trace_slice = TraceSlice(events=[event])
```

## Примеры использования

### Компиляция и исполнение политики

```python
from polisyos.foundry.compiler import compile_surface_policy
from polisyos.foundry.runtime import execute_program
from polisyos.core.artifacts.store import FileSystemCAS

# Компиляция политики
store = FileSystemCAS("/tmp/artifacts")
artifacts = compile_surface_policy(
    store=store,
    policy=policy_surface_ir,
    mechanism_registry=mechanism_registry,
    slot_registry=slot_registry,
    merge_registry=merge_registry
)

# Исполнение программы
initial_state = GlobalState.empty(n_agents=1000, n_firms=100)
result = execute_program(
    program_graph=artifacts.program_ref,
    exec_plan=artifacts.exec_plan_ref,
    initial_state=initial_state,
    store=store,
    treasury_plan=artifacts.treasury_plan_ref
)

print(f"Финальный GDP: {result.final_state.gdp:.2f}")
```

### Создание механизма с патчами

```python
from polisyos.foundry.base import Mechanism
from polisyos.core.contracts.foundry import UpdateOp
import jax.numpy as jnp

class ModernIncomeTax(Mechanism):
    tax_rate: float

    def emit_patches(self, state, key, *, target_mask=None):
        # Вычисляем налог
        incomes = state.agents.income
        tax_amounts = incomes * self.tax_rate

        # Генерируем патчи вместо прямых изменений
        patches = {
            "agents.income": [
                UpdateOp(delta=-tax_amounts, mask=target_mask)
            ],
            "government.balance": [
                UpdateOp(delta=jnp.sum(tax_amounts), mask=None)
            ]
        }
        return patches, key
```

### Создание адаптивного агента

```python
from polisyos.foundry.agents import AdaptiveAgentMechanism

# Агент, который оптимизирует декларируемый доход (уклонение от налогов)
tax_evasion_agent = AdaptiveAgentMechanism(
    observation_space=[
        "agents.income",           # Фактический доход
        "global.tax_rate",         # Ставка налога
        "market.unemployment_rate" # Риск безработицы
    ],
    action_space={
        "type": "continuous",
        "affects": ["agents.reported_income"],
        "dim": 1,
        "range": [0.5, 1.0]  # Декларировать 50-100% дохода
    },
    utility="risk_adjusted_income",  # Максимизировать доход с учётом риска
    learning_rate=0.01,
    stochastic=False
)

# Агент принимает решение на основе наблюдений
patches, key = tax_evasion_agent.emit_patches(state, key)
```

### Legacy симуляция (устаревшее)

```python
from polisyos.foundry.basic_simulation import simple_policy_simulation, analyze_simulation_results

# Запуск простой симуляции
time_steps, populations = simple_policy_simulation(
    population_size=1000,
    time_steps=50,
    policy_effect=0.05
)

# Анализ результатов
analysis = analyze_simulation_results(time_steps, populations)
print(f"Средний рост: {analysis['total_growth_percent']:.1f}%")
```

## Разработка новых механизмов

### 1. Создание класса механизма

```python
from polisyos.foundry.base import Mechanism
from polisyos.foundry.types import FidelityLevel

class UnemploymentBenefit(Mechanism):
    benefit_amount: jnp.ndarray
    eligibility_threshold: jnp.ndarray

    def __init__(self, benefit_amount: float, eligibility_threshold: float, **kwargs):
        self.benefit_amount = jnp.array(benefit_amount)
        self.eligibility_threshold = jnp.array(eligibility_threshold)
        self.fidelity = FidelityLevel.SURROGATE_FLUID

    def init_state(self, state: GlobalState, key: jax.Array) -> tuple[GlobalState, jax.Array]:
        return state, key

    def step(self, state: GlobalState, key: jax.Array) -> tuple[GlobalState, jax.Array]:
        # Логика пособия по безработице
        unemployed = ~state.agents.is_employed
        eligible = state.agents.income < self.eligibility_threshold

        benefit_mask = unemployed & eligible
        additional_income = benefit_mask * self.benefit_amount

        new_income = state.agents.income + additional_income
        new_balance = state.government_balance - jnp.sum(additional_income)

        new_agents = state.agents.replace(income=new_income)

        return state.replace(agents=new_agents, government_balance=new_balance), key
```

### 2. Добавление спецификации

```python
from polisyos.foundry.specs import MECHANISM_SPECS, MechanismSpec

MECHANISM_SPECS["unemployment_benefit"] = MechanismSpec(
    name="unemployment_benefit",
    required_params={"benefit_amount", "eligibility_threshold"},
    param_ranges={
        "benefit_amount": (0.0, 1000.0),
        "eligibility_threshold": (0.0, 10000.0)
    },
    param_units={
        "benefit_amount": "currency",
        "eligibility_threshold": "currency"
    },
    description="Пособие по безработице"
)
```

### 3. Регистрация в registry

```python
from polisyos.foundry.registry import MECHANISM_REGISTRY
from polisyos.foundry.unemployment import UnemploymentBenefit

MECHANISM_REGISTRY["unemployment_benefit"] = UnemploymentBenefit
```

## Тестирование

Foundry включает comprehensive тесты:

### Compiler Tests
- **Program Graph compilation**: Корректность построения графа
- **Execution Plan**: Топологическая сортировка и валидность
- **Merge Rules**: Разрешение конфликтов патчей

### Runtime Tests
- **Patch execution**: Корректность применения патчей
- **Slot management**: Чтение/запись в правильные слоты
- **Treasury determinism**: Воспроизводимость результатов

### Legacy Tests
- **JIT-стабильности**: Градиенты не ломаются при компиляции
- **Экономических инвариантов**: Сохранение законов экономики
- **Multi-fidelity**: Эквивалентность разных уровней точности

```bash
# Запуск всех тестов foundry
pytest tests/foundry/ -v

# Тесты компилятора
pytest tests/foundry/test_constraints_executor.py -v

# Legacy тесты симуляции
pytest tests/foundry/test_jit_stability.py -v
```

## Производительность

### JIT-компиляция

Все вычисления в Foundry JIT-компилируются для максимальной производительности:

```python
# Автоматическая JIT-компиляция
kernel = SimulationKernel()  # Компилируется при создании

# Ручная JIT-компиляция функций
@jax.jit
def simulate_policy(policy_params, initial_state):
    # Логика симуляции
    pass
```

### Профилирование

```python
import jax.profiler

# Профилирование выполнения
with jax.profiler.trace("/tmp/jax-trace"):
    result = jax.jit(my_function)(args)
```

## Ограничения и допущения

### Архитектурные ограничения

- **Patch-based execution**: Все изменения через патчи, нет прямого доступа к состоянию
- **Slot-based state**: Состояние доступно только через предопределенные слоты
- **Deterministic execution**: Все RNG через Treasury для воспроизводимости
- **Static compilation**: ProgramGraph фиксирован после компиляции

### Экономическая модель

- **Patch-based изменения**: все модификации состояния через патчи
- **Slot-based state**: доступ к состоянию только через предопределенные слоты
- **Многоуровневая точность**: три уровня fidelity (fluid/relaxed/hard)
- **Детерминированное исполнение**: RNG через Treasury для воспроизводимости

### Вычислительные ограничения

- **JAX immutable state**: Все изменения через патчи или `replace()`
- **Static shapes**: Размеры массивов фиксированы при компиляции
- **Limited Python**: Только JAX-совместимые операции в runtime
- **Artifact-based**: Все данные через artifact store

## Связанные модули

### Зависимости Foundry

- **`ir/`**: Policy Surface IR, контракты механизмов, registries (slot/merge/mechanism)
- **`core/artifacts`**: Artifact storage и CAS для компиляции/исполнения/калибровки
- **`core/contracts`**: Foundry-типы (PatchOp, ProgramGraph, ExecPlan, etc.)
- **`core/canon`**: Каноническая сериализация артефактов

### Потребители Foundry

- **`scientist/`**: Компилятор, калибратор, conflict checker, cost model
- **`runtime/`**: Хранение результатов, аудит, NaN guard
- **`ir/`**: Спецификации механизмов и calibration targets
- **`tools/`**: Миграция политик, cost estimates, conflict reports

### Pipeline интеграции

```
scientist/ → ir/ → foundry.compiler → foundry.calibration → foundry.runtime → artifacts
                     ↓                           ↓
               tools/ (migration)          foundry.executor (constraints)
                     ↓                           ↓
               core/artifacts (CAS)        core/contracts (types)
```

## Соглашения по коду

- **Строгая типизация**: все функции с type hints
- **Документация**: docstrings для всех публичных API
- **Именование**: snake_case для функций, PascalCase для классов
- **Импорты**: абсолютные импорты внутри polisyos
- **Логирование**: через loguru, без print statements

## Миграция и Roadmap

### Современная архитектура

Foundry полностью переведен на patch-based архитектуру:

- **emit_patches()**: Все механизмы используют патчи вместо прямых изменений
- **ProgramGraph execution**: Компиляция политик в графы выполнения
- **Constraints validation**: Валидация ограничений после каждого шага
- **Trace logging**: Полная трассировка исполнения для отладки

### Разработка новых механизмов

1. **Наследоваться от Mechanism**: Использовать абстрактный базовый класс
2. **Реализовать emit_patches()**: Генерировать патчи вместо прямых изменений
3. **Добавить в registry**: Зарегистрировать механизм для использования
4. **Добавить спецификации**: Определить параметры и ограничения

### Будущие улучшения

- **Distributed execution**: Масштабирование на кластеры
- **Advanced merge rules**: Более сложные стратегии разрешения конфликтов
- **Dynamic shapes**: Поддержка переменных размеров массивов
- **GPU acceleration**: Оптимизация для GPU-вычислений

---

Foundry представляет собой современный высокопроизводительный execution engine для дифференцируемого исполнения экономических политик, использующий patch-based архитектуру, ProgramGraph компиляцию и constraints validation для обеспечения надежности и эффективности моделирования.
