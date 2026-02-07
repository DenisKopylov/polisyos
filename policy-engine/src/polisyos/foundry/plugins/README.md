# Plugins — расширяемая доменная архитектура

Модульная plugin-система для доменно-специфичных симуляций (экономика, здравоохранение, климат). Определяет протоколы, реестр плагинов и high-level API для мульти-доменных симуляций.

**12 модулей** | **Protocol-based** | **Multi-domain composition** | **CLI**

## Архитектура

```
DomainPlugin protocol → PluginRegistry → CompositeState/Executor → PolisySimulator
      ↓                      ↓                    ↓                       ↓
   core.py             discovery.py          composite.py              api.py
   (protocols)      (auto-discovery)     (multi-domain merge)     (high-level API)
```

## Core Protocols (`core.py`)

### DomainPlugin[StateT]

ABC, определяющий полный доменный интерфейс:
- `metadata: PluginMetadata` — name, version, capabilities, dependencies, tags
- `create_initial_state(config) → StateT`
- `get_mechanisms() → list[MechanismProtocol]`
- `get_reward_function() → RewardProtocol`
- `get_objectives() → dict[str, ObjectiveProtocol]`
- `get_observation_builder() → callable`
- `get_visualizations() → dict[str, callable]`
- `validate_config()`, `on_load()` / `on_unload()`

### Вспомогательные протоколы

- **DomainState** — `empty()`, `validate()`
- **DomainAgentState** — `active: jnp.ndarray`, `get_observations()`
- **MechanismProtocol[StateT]** — `apply(state, **kwargs) → StateT`, `name: str`
- **RewardProtocol[StateT]** — `compute(state, next_state, agent_actions) → jnp.ndarray`
- **ObjectiveProtocol[StateT]** — `evaluate(state) → jnp.ndarray`, `maximize: bool`

### PluginRegistry

Singleton-реестр с lazy `on_load()`:
- `register()` / `unregister()` / `get()` / `list_plugins()`
- `with_capability(PluginCapability)` / `with_tag(str)` — фильтрация

`PluginCapability` enum: AGENTS, MECHANISMS, REWARDS, OBJECTIVES, OBSERVATIONS, VISUALIZATION, CALIBRATION.

`DomainConfig` — общая конфигурация: n_agents, max_agents, seed, time_horizon, parameters, enabled_mechanisms, agent_learning, policy_learning.

## Composite — мульти-доменные симуляции (`composite.py`)

Equinox-модули для композиции нескольких доменов:

- **CompositeState** — `domain_states` dict + `time_step`. `create()`, `get_domain()`, `update_domain()`, `apply_interactions()`, `increment_time()`
- **CrossDomainInteraction** — маппинг source_domain.field → target_domain.field с transform и weight
- **CompositeExecutor** — `step()`: все механизмы per domain в execution order → interactions. `run()` loop
- **CompositeReward** — weighted aggregation доменных rewards
- **CompositeObjective** — multi-objective weighted evaluation

## High-Level API (`api.py`)

`PolisySimulator` — builder pattern:

```python
sim = PolisySimulator()
sim.add_domain("economics", EconomicsPlugin(), config)
sim.add_interaction(CrossDomainInteraction(...))
sim.initialize()

# Запуск симуляции
result = sim.run(n_steps=100)  # → SimulationResult

# RL-обучение
training_result = sim.train(n_episodes=50)  # → TrainingResult

# Обновление политики
sim.set_policy("economics", {"tax_rate": 0.25})
```

- `SimulationResult` — final_state, trajectory, objectives, `get_metric()`
- `TrainingResult` — trained_policy, loss_history, final_state, `plot_losses()`

## Discovery (`discovery.py`)

Три источника автообнаружения:

1. **Builtin** — `polisyos.foundry.plugins.economics`
2. **Entry points** — `polisyos.plugins` group + `polisyos_plugin_*` package prefix
3. **Directory scan** — поиск `plugin.py` в указанных директориях

`auto_register_plugins()` — discover + register все найденные.
`create_simple_plugin()` — фабрика для быстрого создания плагинов из компонентов.

## CLI (`cli.py`)

```bash
polisy list [--verbose]                    # Список плагинов
polisy run --config config.json --domains economics --n-agents 1000
polisy train --config config.json --n-episodes 100
polisy analyze results.json
```

## Economics Plugin (`economics/`)

Референсная реализация доменного плагина (v1.0.0).

### State (`economics/state.py`)

- **EconomicAgentState** — 13 полей: active, age, skill_level, wealth, income, consumption, savings, employed, wage, hours_worked, discount_rate, risk_aversion, consumption_preference. `get_observations()` → 6-dim tensor
- **EconomicPolicyState** — tax_rate, transfer_rate, interest_rate, unemployment_benefit, minimum_wage
- **EconomicDistributions** — gini_wealth, gini_income, top_10_share, bottom_50_share, median_wealth, median_income
- **EconomicAggregates** — gdp, total_consumption, total_investment, unemployment_rate, inflation_rate, mean_wealth, mean_income
- **EconomicState** — composite state с `validate()` и `update_aggregates()`

### Mechanisms (`economics/mechanisms.py`)

Equinox-модули, реализующие `MechanismProtocol`:
- **TaxationMechanism** — прогрессивные 7-bracket налоги
- **TransferMechanism** — welfare + unemployment benefits, means-tested
- **LaborMarketMechanism** — job finding/separation dynamics, stochastic wage growth
- **ConsumptionMechanism** — income/wealth-based consumption, bounded
- **SavingsMechanism** — savings + interest accumulation

### Objectives (`economics/objectives.py`)

`ObjectiveProtocol` реализации:
- **GDPObjective** (maximize), **GiniObjective** (minimize), **UnemploymentObjective** (minimize)
- **SocialWelfareObjective** — weighted composite (GDP + neg_gini + neg_unemployment + bottom_50_share)
- **UtilitarianWelfare** — sum of log-utilities (Bentham)
- **RawlsianWelfare** — maximin (maximize minimum utility)

### Rewards (`economics/rewards.py`)

`EconomicReward` — CRRA utility-based: consumption utility + wealth change (tanh-scaled) + employment bonus.

## Зависимости

- **foundry/agent_sim** — ActorCritic (для training), distributions (для EconomicState)
- **JAX/Equinox** — composite state management, mechanisms
- **Chex** — frozen dataclasses

## Структура

```
plugins/
├── __init__.py        # Public API
├── core.py            # DomainPlugin ABC, protocols, PluginRegistry
├── api.py             # PolisySimulator, SimulationResult, TrainingResult
├── composite.py       # CompositeState/Executor/Reward/Objective
├── discovery.py       # Auto-discovery (builtin, entry points, filesystem)
├── cli.py             # Command-line interface
└── economics/
    ├── __init__.py    # Public API
    ├── plugin.py      # EconomicsPlugin (v1.0.0)
    ├── state.py       # EconomicAgentState, PolicyState, Aggregates
    ├── mechanisms.py  # Taxation, Transfer, Labor, Consumption, Savings
    ├── objectives.py  # GDP, Gini, Unemployment, SocialWelfare, Rawlsian
    └── rewards.py     # CRRA utility-based agent reward
```
