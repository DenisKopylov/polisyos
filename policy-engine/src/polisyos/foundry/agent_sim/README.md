# Agent Simulation — симуляция гетерогенных агентов

JAX-based фреймворк для агентной симуляции экономики с RL-обучением, графовыми структурами, демографическими процессами и эволюционной оптимизацией. Полностью дифференцируем и JIT-компилируем.

**38 модулей** | **PPO/CMA-ES** | **Social graphs** | **Dynamic population**

## Архитектура

Четыре уровня исполнителей с нарастающей функциональностью:

```
PureExecutor → DistributionAwareExecutor → GraphAwareExecutor → PopulationAwareExecutor
  (механизмы)     + статистика неравенства    + социальные сети     + рождение/смерть
```

Четыре режима обучения (Learning Modes):
- **Mode A (Agent Adaptation)** — обучение агентной политики при фиксированной государственной
- **Mode B (Policy Optimization)** — оптимизация государственной политики при фиксированных агентах
- **Mode C (Calibration)** — калибровка параметров модели на эмпирических данных
- **Bilevel** — чередование Mode A/B для равновесия Штакельберга

## Слой данных

### AgentState (`state.py`)

Frozen chex-dataclass с 27 полями per agent: `active`, `agent_id`, `birth_step`, `parent_id`, `wealth`, `income`, `consumption`, `savings`, `debt`, `employed`, `retired`, `risk_aversion`, `discount_factor`, `skill_level`, `education_years`, `age`, `life_expectancy`, `fertility_rate`, `n_connections` и др.

### PolicyState, AggregateState, GlobalState

- **PolicyState** — скалярные параметры: `tax_rate`, `transfer_rate`, `interest_rate`
- **AggregateState** — `total_wealth`, `mean_consumption`, `gini_coefficient`
- **GlobalState** — композит всех state-компонентов + `time_step`, `simulation_horizon`, `rng_key`. Фабрика `empty()`, `compute_aggregates()` с Lorenz-curve Gini

## Слой механизмов

`Mechanism` ABC (`mechanism.py`): `MechanismSpec` (name, reads, writes, parameters, stochastic) + `apply(state, rng_key, fidelity)`.

### Экономические (`mechanisms.py`, `distribution_mechanisms.py`)

- **TaxationMechanism** — прогрессивное налогообложение: `base_rate + progressive_factor * log1p(income)`, clip [0, 0.6]
- **ConsumptionMechanism** — нейросетевое потребление через `SharedPolicy`
- **DistributionAwareTaxMechanism** — налоги с учетом income-rank из `DistributionState`
- **TargetedTransferMechanism** — перераспределение ниже target-percentile (uniform или inverse-rank)
- **RelativeConsumptionMechanism** — "keeping up with the Joneses" — utility adjustment от разрыва с пирами

### Графовые (`graph_mechanisms.py`)

- **SocialInfluenceMechanism** — `consumption_target` как средневзвешенное соседей
- **InformationDiffusionMechanism** — распространение информации через сеть (decay + noise)
- **NetworkLendingMechanism** — заимствования у богатых соседей с процентом
- **LaborNetworkMechanism** — трудоустройство через рефералы от занятых соседей

### Временные (`temporal_mechanisms.py`)

- **TemporalConsumptionMechanism** — RL-driven потребление через `ActorCritic`. Temporal observations включают lifecycle features (retirement distance, life stage), policy features, seasonal signals

### Демографические (`population_mechanisms.py`)

- **AgingMechanism** — инкремент возраста, обновление фертильности (bell-curve), выход на пенсию
- **BirthMechanism** — вероятностные рождения на основе fertility rate, наследование от родителей
- **DeathMechanism** — смертность, распределение наследства выжившим
- **MigrationMechanism** — иммиграция (новые агенты 20-50 лет) и эмиграция (по wealth/employment)
- **InheritanceMechanism** — наследование с налогом, распределение детям (max-per-heir cap)
- **GiftTransferMechanism** — inter-vivos трансферы от старших родителей к детям

## Слой нейронных сетей

### Actor-Critic (`actor_critic.py`)

Equinox-модули для RL:
- **NormalizedMLP** — LayerNorm между слоями, GELU activation, vmap для batch
- **ValueNetwork** — trunk + linear head → скаляр per agent
- **AdvantageNetwork** — dueling architecture (value + advantage heads)
- **ActorCritic** — shared trunk, separate actor/critic heads. Continuous (Gaussian) и discrete (Categorical) action spaces. `sample_actions()` (reparameterization trick), `compute_log_prob()`, `compute_entropy()`

### SharedPolicy (`policy.py`)

Простая MLP без LayerNorm для Mode A. `build_observations()`: 6 agent features + 4 global features (tax_rate, interest_rate, sin/cos seasonal).

### GovernmentPolicy (`government_policy.py`)

Equinox-модуль для Mode B: 12-dim global observations → bounded policy parameters (tax_rate ∈ [0, 0.5], transfer_rate ∈ [0, 0.3], interest_rate ∈ [0, 0.2]) через sigmoid.

## Слой обучения

### RL Core (`rl.py`)

- `Transition`, `Trajectory` — структуры данных
- `compute_returns_and_advantages()` — GAE через `jax.lax.scan` в обратном порядке, с учетом active masks
- `ppo_loss()` — clipped surrogate + value loss + entropy bonus. Диагностика: clip_fraction, mean_ratio

### Training (`training.py`, `jit_training.py`)

- `train_actor_critic()` — Python-loop: episodes × steps → trajectory → PPO update
- `train_actor_critic_jit()` — полностью JIT-compiled через nested `jax.lax.scan`
- `JITTrainingConfig` — hyperparams + credit_config + metrics collection
- `train_actor_critic_with_artifact()` — обучение → `AgentPolicyArtifact` → CAS

### Credit Assignment (`credit_assignment.py`)

Multi-agent credit для shared-policy MARL:
- `CreditMode`: INDIVIDUAL, SHARED, COUNTERFACTUAL, MEAN_FIELD, SHAPLEY_APPROX
- `CentralizedCritic` — 12-dim global observations (population stats)

### Rewards (`rewards.py`)

- `UtilityFunction`: CRRA (`(c^(1-γ)-1)/(1-γ)`), CARA (`-exp(-γc)/γ`), Epstein-Zin (recursive, separation of risk aversion и IES)
- `compute_agent_reward()`: utility(consumption) + 0.01·log(wealth) - 10·(bankruptcy) + utility_adjustment
- `apply_discounting()` — reverse-scan discounted returns

### Альтернативная оптимизация

- **Evolution** (`evolution.py`) — Natural ES + CMA-ES (diagonal). Fitness через simulation rollouts
- **VFI** (`vfi.py`) — Value Function Iteration на дискретных сетках (Bellman + convergence)
- **MPC** (`mpc.py`) — Model Predictive Control: Monte Carlo forward rollouts → action selection
- **HybridPlanner** — actor-critic (fast) + MPC (accurate), переключение по uncertainty

## Графовая инфраструктура (`graphs.py`)

Мультиплексные графы с 6 типами связей: SOCIAL_FRIEND, SOCIAL_FAMILY, ECONOMIC_EMPLOYER, ECONOMIC_LENDER, SPATIAL_NEIGHBOR, INFO_INFLUENCE.

- `FixedSizeEdgeList` — JIT-compatible с active mask
- Генераторы: Erdos-Renyi, Barabasi-Albert, Watts-Strogatz, spatial, scale-free
- Message passing: `aggregate_messages()` (sum/mean/max), `scatter_messages()`, `segment_softmax()`, `apply_edge_attention()`, `multi_hop_aggregation()`
- Analytics: `compute_degree_centrality()`, `compute_pagerank()` (iterative), `compute_graph_metrics()`
- `DynamicGraphUpdater` — эволюция структуры с wealth-based homophily

Обогащенные observations (`graph_observations.py`): +5 network features (neighbor wealth/consumption, degree, PageRank, wealth rank).

## Динамическая популяция (`population.py`)

Slot-allocator для JIT-compatible динамического количества агентов:

- `PopulationManager` — free-stack аллокатор (`free_stack`, `free_top`, `n_active`)
- `allocate_slot()` / `free_slot()` / `batch_create_agents()` / `batch_remove_agents()` — всё через `jax.lax.scan/cond`
- `compute_death_mask()` — модель смертности: base hazard + age-exponential + wealth-protective + life-expectancy
- `sync_graph_with_population()` — обновление графа при рождении/смерти

## Распределения и неравенство (`distributions.py`)

Крупнейший модуль (~710 строк) с дифференцируемыми и hard-реализациями:

- `compute_gini()` / `compute_gini_soft()` / `compute_gini_proxy()` (MAD-based fast)
- `soft_sort()` (Sinkhorn), `soft_rank()` (sigmoid pairwise)
- Metrics: `compute_top_share()`, `compute_bottom_share()`, `compute_palma_ratio()`, `compute_percentile_ratios()`
- Mobility: `compute_rank_correlation()`, `compute_transition_matrix()`
- `DistributionState` — cached квантили, ранги, Gini, top-10/bottom-50 shares
- `AdaptiveUpdateStrategy` — адаптивная частота обновления по скорости изменения Gini
- `compute_distribution_aware_reward()` — reward с penalty за неравенство

## Инструментарий

### Analysis (`analysis.py`)

- `BehaviorAnalyzer`: action statistics, k-means clustering агентов, mobility matrix, policy sensitivity (finite differences), counterfactual analysis

### Experiment Tracking (`experiment.py`)

- `ExperimentTracker` — filesystem-based registry с JSON-индексом
- `ExperimentRun` — context manager, `log_metric()`, `log_artifact()` (Equinox/pickle), `get_rng_key()`

### Artifact System (`artifact.py`)

- `AgentPolicyArtifact` — immutable CAS-артефакт: serialized weights (SHA-256), training metrics, environment fingerprint, I/O spec
- `can_hot_swap()` — проверка совместимости для runtime-замены политики
- `validate_environment()` — проверка JAX/architecture/determinism tier

### Metrics (`metrics.py`)

JIT-compatible `MetricsCollector` с circular `MetricsBuffer`:
- Standard: mean_wealth, gini_wealth, gdp, mean_consumption, n_active_agents, wealth/income distributions
- Training: policy_loss, value_loss, entropy, mean_reward, mean_advantage

### Demographics (`demographics.py`)

`compute_demographic_metrics()`: age brackets, dependency ratio, life expectancy, fertility rate. `compute_intergenerational_mobility()`: parent-child wealth rank correlation.

### Visualization (`visualization.py`, `dashboard.py`)

- `TrainingVisualizer` — Matplotlib/Plotly: training curves, wealth distribution + Lorenz curve, agent trajectories, policy comparison, animated GIF
- `DashboardGenerator` — Plotly HTML dashboard (3×2 subplots), comparison dashboards, markdown reports

## Структура

```
agent_sim/
├── state.py                  # AgentState (27 fields), PolicyState, GlobalState
├── mechanism.py              # Mechanism ABC, MechanismSpec
├── mechanisms.py             # TaxationMechanism, ConsumptionMechanism
├── distribution_mechanisms.py # Distribution-aware tax, targeted transfers
├── graph_mechanisms.py       # Social influence, info diffusion, lending, labor network
├── temporal_mechanisms.py    # RL-driven temporal consumption
├── population_mechanisms.py  # Aging, birth, death, migration, inheritance
├── executor.py               # PureExecutor (topological sort, mechanism dispatch)
├── distribution_executor.py  # + distribution tracking
├── graph_executor.py         # + graph dynamics
├── population_executor.py    # + lifecycle simulation
├── temporal_executor.py      # Factory for temporal-aware executor
├── actor_critic.py           # NormalizedMLP, ActorCritic (continuous/discrete)
├── policy.py                 # SharedPolicy MLP, build_observations
├── government_policy.py      # GovernmentPolicy network, training loop
├── rl.py                     # Trajectory, GAE, PPO loss
├── training.py               # Python-loop training
├── jit_training.py           # JIT-compiled training via lax.scan
├── rewards.py                # CRRA/CARA/Epstein-Zin utilities
├── credit_assignment.py      # INDIVIDUAL/COUNTERFACTUAL/SHAPLEY credit modes
├── evolution.py              # Natural ES + CMA-ES
├── vfi.py                    # Value Function Iteration
├── mpc.py                    # Model Predictive Control + HybridPlanner
├── modes.py                  # Mode A/B/C/Bilevel orchestration
├── graphs.py                 # Multiplex graphs, message passing, analytics
├── graph_observations.py     # Network-enriched observations
├── distributions.py          # Gini, Palma, soft_sort, distribution tracking
├── population.py             # Slot allocator, birth/death, graph sync
├── demographics.py           # Demographic metrics, intergenerational mobility
├── temporal.py               # Temporal observation builder
├── prng.py                   # Deterministic per-mechanism PRNG
├── metrics.py                # JIT-compatible MetricsCollector
├── analysis.py               # BehaviorAnalyzer, clustering, counterfactuals
├── experiment.py             # ExperimentTracker, ExperimentRun
├── artifact.py               # AgentPolicyArtifact (CAS, hot-swap, env validation)
├── dashboard.py              # Plotly HTML dashboards
└── visualization.py          # Matplotlib/Plotly charts and animations
```
