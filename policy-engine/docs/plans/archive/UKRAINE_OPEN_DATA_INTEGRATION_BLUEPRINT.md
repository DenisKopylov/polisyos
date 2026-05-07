> **Archived:** This document reflects plans as of 2026-03-28.
> See [current docs](../../explanation/index.md) for up-to-date information.

# Ukraine Open Data Integration Blueprint

**Версия:** 4.0
**Дата:** 2026-03-28
**Статус:** Revised Draft
**Целевая инфраструктура:** Hetzner Cloud `CPX62` (`16 vCPU`, `32 GB RAM`, `640 GB NVMe`, `20 TB traffic`)
**Режим:** one-time batch snapshot + calibration bundle, без регулярных обновлений на первом этапе

---

## 1. Executive Summary

Документ описывает, как превратить украинские открытые данные в **симуляционный и калибровочный слой** для `PolicyOS`.

### 1.1. Цель

Нужна система, которая сможет:

1. наблюдать реальную экономику Украины через открытые данные;
2. строить компактный, масштабируемый multiscale world model;
3. калибровать поведение агентов под реальные наблюдения через `JAX` и autodiff;
4. связывать нормы из `Lex` с явными simulation knobs;
5. делать backtesting, stress testing и counterfactual simulation;
6. использовать `firm fundamentals`, `household/labor microdata`, `spatial/raster exogenous layers` и `distress/logistics signals` как core inputs, а не как периферийные enrichments;
7. задействовать **полный стек каузальной идентификации** — interference, partial identification, transportability, measurement-error correction, dynamic treatment regimes — а не только point estimation;
8. использовать **все 23 governance passes** Scientist-а, adversarial testing и lesson registry для calibration governance;
9. маршрутизировать observation families не только в calibration targets, но и в **native typed method contracts** для econometrics, survival, optimization, sensitivity и causal surfaces.

### 1.2. Архитектурный контур

```text
open data
  -> normalized source layers
  -> measurement-aware observation plane
  -> identification-mode routing (point / bounds / proxy / DTR)
  -> multiscale agent world
  -> runtime artifacts
  -> calibration artifacts
  -> method-contract bundles (causal, econometric, survival, network, microsim)
  -> intervention mapping from Lex (singleton + temporal sequences)
  -> strategic response verification
  -> replay / backtesting / adversarial governance / policy simulation
```

Для каждого source family blueprint должен явно фиксировать:

1. какой артефакт строится;
2. какой тип state он инициализирует;
3. какой `Foundry / Scientist / Fabric` surface его потребляет;
4. остаётся ли он в runtime или живёт только в calibration bundle;
5. какой identification mode применим (`point_identified`, `partially_identified`, `bounds_only`, `proxy_identified`);
6. какие governance passes обязательны для данной observation family.

Украинский bundle должен быть нативным для уже существующих execution surfaces:

1. `Foundry` state initialization;
2. `survey` / `microsim` workflows;
3. `distributional` / `welfare` evaluation;
4. `network` / `multiplex` graph analysis;
5. `optimization` / `input-output` scenarios;
6. `Scientist` replay / backtesting / trust scoring;
7. `causal` identification / estimation / bounds / interference;
8. `econometrics` panel / selection / IV / factor surfaces;
9. `survival` / hazard analysis для firm exit и distress;
10. `sensitivity` / specification-curve diagnostics;
11. `strategic response` / performative equilibria verification;
12. `policy_design` hierarchical search (structure → parameter → narrative).

Документ также явно различает:

1. что уже поддерживается существующим кодом;
2. что можно использовать сразу через existing execution surfaces;
3. что требует реального изменения контрактов, а не только новых parquet-ов.

### 1.3. Почему это важно

Если оставить план только на уровне "собрать побольше данных", система будет:

1. тяжёлой для `CPX62`;
2. плохо идентифицируемой;
3. неустойчивой для calibration;
4. слабой как policy simulator.

Если же строить:

1. multiscale architecture,
2. explicit measurement model,
3. observation-plane first,
4. intervention model from `Lex`,
5. identification-mode routing per observation family,
6. full governance pass coverage,

тогда система становится не просто хранилищем данных, а **policy reasoning engine с наблюдаемой реальностью**.

Самый большой оставшийся резерв теперь лежит не в "ещё одном реестре", а в четырёх направлениях:

1. `household/labor microdata`;
2. `spatial/raster exogenous layers`;
3. `distress / logistics / legal-enforcement signals`;
4. **полное задействование уже существующих каузальных, governance, econometric и optimization surfaces**.

---

## 2. Code Grounding in PolicyOS

### 2.1. Existing strengths

`PolicyOS` уже имеет три мощных слоя:

1. `Lex`
   Корпус НПА, provision index, world facts, структурированные нормы и ссылки.
2. `Scientist / Academic / Causal`
   Каузальные графы, literature priors, observational reasoning, replay и governance.
3. `Fabric / Datasets`
   DataSnapshot path, source discovery, metadata graph, batch ingestion and normalization.

### 2.2. Missing observed-economy layer

Сейчас системе не хватает слоя:

```text
real observed economy -> agents -> flows -> regions -> sectors -> behaviors
```

Без него `PolicyOS` хорошо понимает:

1. что написано в нормах;
2. что говорит литература;
3. какие датасеты существуют.

Но система хуже понимает:

1. кто реальные адресаты политики;
2. какие реальные бюджетные и контрактные потоки их связывают;
3. как их состояние меняется по времени;
4. под какие наблюдения вообще калибровать поведение симуляции.

### 2.3. Relevant code surfaces

План опирается на существующие контуры:

- `src/polisyos/scientist/adapters/fabric_bridge.py`
- `src/polisyos/foundry/data_plane/bindings.py`
- `src/polisyos/fabric/data_plane/orchestrator.py`
- `src/polisyos/ir/kernel/slots.py`
- `src/polisyos/foundry/contracts/state.py`
- `src/polisyos/foundry/agent_sim/executor.py`
- `src/polisyos/foundry/agent_sim/jit_training.py`
- `src/polisyos/foundry/calibration/calibrator.py`
- `src/polisyos/foundry/calibration/preflight.py`
- `src/polisyos/foundry/calibration/loss.py`
- `src/polisyos/foundry/methods/catalog/causal/causal_engine.py`
- `src/polisyos/foundry/methods/catalog/causal/id_engine.py`
- `src/polisyos/foundry/methods/catalog/causal/measurement_error.py`
- `src/polisyos/foundry/methods/catalog/causal/strategic.py`
- `src/polisyos/foundry/methods/catalog/causal/dtr.py`
- `src/polisyos/foundry/methods/catalog/causal/policy_learning.py`
- `src/polisyos/foundry/methods/catalog/causal/discovery_pipeline.py`
- `src/polisyos/foundry/methods/catalog/causal/protocols.py`
- `src/polisyos/foundry/methods/catalog/network/protocols.py`
- `src/polisyos/foundry/methods/catalog/network/analysis.py`
- `src/polisyos/foundry/methods/catalog/microsim/protocols.py`
- `src/polisyos/foundry/methods/catalog/policy/evaluation.py`
- `src/polisyos/foundry/methods/catalog/simulation/dynamics.py`
- `src/polisyos/foundry/methods/catalog/econometrics/panel.py`
- `src/polisyos/foundry/methods/catalog/econometrics/selection.py`
- `src/polisyos/foundry/methods/catalog/econometrics/iv.py`
- `src/polisyos/foundry/methods/catalog/econometrics/factor.py`
- `src/polisyos/foundry/methods/catalog/ml/survival.py`
- `src/polisyos/foundry/methods/catalog/optimization/bilevel.py`
- `src/polisyos/foundry/methods/catalog/optimization/game_theory.py`
- `src/polisyos/foundry/methods/catalog/optimization/io_leontief.py`
- `src/polisyos/foundry/methods/catalog/optimization/chance_constrained.py`
- `src/polisyos/foundry/methods/catalog/sensitivity/sobol.py`
- `src/polisyos/foundry/methods/catalog/sensitivity/specification.py`
- `src/polisyos/foundry/methods/catalog/survey/weighting.py`
- `src/polisyos/foundry/methods/catalog/survey/imputation.py`
- `src/polisyos/foundry/methods/catalog/spatial/advanced.py`
- `src/polisyos/foundry/methods/catalog/forecasting/univariate.py`
- `src/polisyos/foundry/methods/catalog/bayesian/timeseries.py`
- `src/polisyos/foundry/methods/catalog/validation/diagnostics.py`
- `src/polisyos/foundry/methods/catalog/distributional/mobility.py`
- `src/polisyos/foundry/methods/catalog/distributional/poverty.py`
- `src/polisyos/foundry/methods/catalog/distributional/polarization.py`
- `src/polisyos/scientist/workflows/policy_design.py`
- `src/polisyos/scientist/backtesting/orchestrator.py`
- `src/polisyos/scientist/backtesting/adversarial.py`
- `src/polisyos/scientist/replay/verification.py`
- `src/polisyos/scientist/search/funnel/level5_refutation_governance.py`
- `src/polisyos/scientist/search/lessons.py`
- `src/polisyos/scientist/search/transfer_context.py`
- `src/polisyos/scientist/discovery/active.py`
- `src/polisyos/scientist/discovery/portfolio.py`
- `src/polisyos/scientist/governance/pipeline.py`
- `src/polisyos/scientist/policy_design/search.py`
- `src/polisyos/foundry/agent_sim/population.py`
- `src/polisyos/foundry/agent_sim/graph_aware.py`
- `src/polisyos/foundry/agent_sim/distribution_aware.py`

1. `Fabric` и `Scientist` нуждаются в compact observation-ready tables;
2. `Foundry` нуждается в компактном инициализационном state и structured targets;
3. `Lex` нуждается в code crosswalks и typed intervention mapping;
4. runtime должен почти ничего не считать "с нуля";
5. household/labor block уже естественно ложится на survey stack;
6. monthly panel calibration уже естественно ложится на forecasting / validation / governance stack;
7. новые артефакты выгоднее описывать как slot families, а не просто как таблицы;
8. каузальный стек имеет 12+ identification algorithms, каждый из которых применим к конкретной observation family;
9. econometrics family (15 файлов) имеет native contracts для panel, selection, IV, factor analysis — уже готовые для firm и labor panels;
10. optimization family имеет bilevel, game theory, Leontief, chance-constrained — прямые surfaces для policy design;
11. survival / hazard analysis — готовый execution path для distress / exit / bankruptcy targets;
12. agent_sim уже имеет population management, graph-aware и distribution-aware executors.

### 2.4. Main code findings

#### A. Есть явный архитектурный пробел

В текущем `slot registry` есть только:

1. `global`
2. `per_agent`
3. `per_firm`
4. `per_entity`

Но нет `per_cell`.

Следствия:

1. `region x sector cells` пока существуют как идея blueprint, но не как first-class runtime contract;
2. в `Foundry` нужен явный `CellState`, а не только агрегаты "где-то рядом";
3. multiscale design нужно поддержать изменением state contracts, а не только документацией.

#### B. Household/labor уже имеют natural execution path

В текущем коде уже есть branch для `survey_repeated_cross_section` и survey-aware bindings.

Следствия:

1. synthetic households не надо проектировать как sidecar heuristic;
2. household/labor microdata нужно считать native input family;
3. observation contracts для household block должны совпадать с survey/microsim workflows.

#### C. Внутренние методы богаче, чем current blueprint реально использует

В системе уже есть готовые surfaces:

1. `distributional / welfare / mobility`
2. `tax-benefit / behavioral / dynamic microsim`
3. `multiplex network / diffusion / input-output networks`
4. `Leontief / robust / stochastic optimization`
5. `policy budget impact / ex ante / social welfare`
6. `stock-flow / system dynamics`
7. `sensitivity / specification-curve`
8. `structural time series`
9. `Scientist backtesting / replay / trust-aware validation`

Украинский bundle нужно проектировать не просто как ETL output, а как **native source of execution-ready artifacts** для этих surfaces.

#### D. Каузальный стек имеет capabilities, которые blueprint должен задействовать напрямую

В `causal_engine.py` реализован Pearl-Bareinboim orchestrator с 12+ identification algorithms:

1. `id_algorithm` — standard Shpitser-Pearl identification;
2. `idc_algorithm` — conditional interventional distributions;
3. `id_star_algorithm` / `idc_star_algorithm` — **counterfactual query identification** (Layer-3);
4. `tr_algorithm` — **transportability** через SelectionDiagram и S-nodes;
5. `mz_id_algorithm` — **multi-source domain identification** (multi-environment);
6. `sid_algorithm` — stochastic/soft policy identification;
7. `dynamic_intervention_id` — **sequential treatment identification**;
8. `identify_with_proxy` — **Kuroki-Pearl measurement-error identification**;
9. `conditional_intervention_id` — stratified interventions;
10. fallback chain: bounds (Manski, Balke-Pearl) → monotonicity rescue → linearity rescue.

Следствия:

1. для каждой observation family нужен explicit **identification mode** — не все каналы point-identified;
2. для военного периода с censored data **partial identification через bounds** — primary strategy, не fallback;
3. `identify_with_proxy()` формально проверяет, хватает ли proxy variable — это прямое применение для tax debt как proxy distress, procurement revenue как proxy cashflow;
4. `tr_algorithm` нужен для formal transportability check при переносе estimates между Regime A/B/C;
5. counterfactual identification (`id_star`) даёт formal guarantees для policy counterfactuals.

#### E. Interference и spillover analysis уже имеют typed contract

`NetworkCausalData` в `protocols.py` принимает `adjacency_matrix`, `cluster_id`, `coordinates`, `bipartite_edges` — готовый контракт для **interference-aware causal estimation** (Aronow & Samii, Hudgens & Halloran).

Следствия:

1. multiplex graph artifacts (budget, procurement, trade, distress) должны компилироваться не только в `NetworkData`, но и в `NetworkCausalData`;
2. procurement shock spillover через граф поставщиков — прямое применение interference analysis;
3. budget cascade через распорядителей — ещё одно прямое применение;
4. SUTVA violation — не edge case, а **expected condition** для украинского графа.

#### F. Strategic response solving уже реализован

`strategic.py` имеет Stackelberg/Nash solver с `StrategicSolveResult`, `performative_shift` quantification и `evaluate_strategic_hook()`.

Следствия:

1. для top policy channels (procurement thresholds, tax rates, subsidy rules) нужен explicit **strategic response check**;
2. участники Prozorro явно адаптируются к правилам — это textbook performative prediction;
3. `evaluate_strategic_hook()` можно вызывать из policy_learning и DTR surfaces для верификации.

#### G. Econometrics, survival и optimization — неиспользованные native surfaces

В `methods/catalog/` есть:

1. **Econometrics** (15 файлов): panel data, selection models (Heckman), factor models, IV, count data, discrete choice, semiparametric — прямые surfaces для firm panels и labor panels;
2. **ML / survival** (10 файлов): survival / hazard analysis — natural execution path для firm exit, bankruptcy, wage arrears, employment transitions;
3. **Optimization** (12 файлов): bilevel (government vs firms), chance-constrained (budget uncertainty), game theory (Nash в procurement), Leontief with stochastic extension — прямые surfaces для policy design;
4. **Sensitivity** (5 файлов): Sobol indices, specification curves — calibration diagnostics для robustness assessment.

Следствия:

1. firm exit из ЄДР — textbook selection problem для Heckman correction;
2. firm panels — natural target для panel econometrics с fixed effects;
3. distress/enforcement/bankruptcy — survival targets с censored observations;
4. bilevel optimization: government sets procurement rules, firms optimize response;
5. specification curves покажут robustness of calibration fit при вариации source combination.

#### H. Agent sim уже имеет population, graph и distribution executors

В `agent_sim/` уже есть:

1. `PopulationAwareExecutor`: aging, births, deaths, inheritance, migration;
2. `GraphAwareExecutor`: labor network, lending, information diffusion;
3. `DistributionAwareExecutor`: Gini, Palma, quantile tracking;
4. Mechanisms: `DistributionAwareTaxMechanism`, `TargetedTransferMechanism`, `RelativeConsumptionMechanism`;
5. `PopulationManager`: slot allocation, dynamic resizing, batch operations.

Следствия:

1. household block (births, aging, migration) имеет **готовый runtime executor path**;
2. firm block (entry, exit, inheritance) — тоже;
3. graph-aware execution (procurement supply chain diffusion) — native;
4. distribution-aware taxation и targeted transfers — уже mechanisms в runtime;
5. blueprint должен использовать эти executors напрямую, а не описывать их как "future work".

#### I. Scientist governance и discovery богаче, чем blueprint задействует

В `Scientist` уже есть:

1. **23 governance passes** в `governance/pipeline.py`: Confidence, Equity, Budget, Privacy, Legal, Refutation, SUTVA Check, Transportability Required, Cross-Graph Evidence, Freshness, Human Review, Normative Arbitration и другие;
2. **Adversarial testing** в `backtesting/adversarial.py`: `STRATEGIC_GAMING`, `MULTIPLICITY_DISCLOSURE`, `ABSTRACTION_LEAKAGE`;
3. **Lesson registry** в `search/lessons.py`: `LessonCard` (FAILURE/SUCCESS), `LessonRegistry` с transfer-aware weighting;
4. **Active disambiguation** в `discovery/active.py`: `ActiveDisambiguationPlanner` планирует, какие данные собрать для disambiguate PAG edges;
5. **Hierarchical policy search** в `policy_design/search.py`: `STRUCTURE → PARAMETER → NARRATIVE` с Pareto tracking.

Следствия:

1. для каждой observation family нужен explicit **governance pass mapping** — какие passes обязательны;
2. adversarial testing нужно включить в calibration governance, а не только в policy evaluation;
3. каждый calibration run должен публиковать `LessonCard`, чтобы следующие итерации не повторяли ошибки;
4. active disambiguation может генерировать **target data collection priorities** на основе graph ambiguity;
5. policy simulation может быть не одиночный knob turn, а **hierarchical search** по структуре, параметрам и формулировке политики.

### 2.5. Code-grounded execution contours

#### A. Fabric snapshot and binding contour

Текущий `Fabric`-контур уже умеет:

1. превращать `DataViewRequest` в `DataSnapshot`;
2. привязывать snapshot к quality report, warnings и evidence;
3. строить `Foundry` input bindings поверх snapshot payload.

1. украинский bundle нужно публиковать как `DataSnapshot`-friendly structured artifacts;
2. runtime не должен зависеть от raw JSON/XML dumps;
3. observation-plane должен быть совместим с snapshot / binding surface, а не жить отдельно.

#### B. Foundry calibration contour

Текущий calibration stack уже умеет:

1. делать preflight fetch / align / resample time-series targets;
2. компилировать `ProgramGraph` в pure execution plan;
3. гонять `jax`-совместимый scan и оптимизацию через `optax`;
4. считать identifiability and Hessian-based uncertainty summaries.

1. не нужен новый calibration engine с нуля;
2. нужен observation-to-target compiler и measurement-aware loss adapter поверх уже существующего calibration stack.

#### C. JAX simulation contour

Текущий `agent_sim`-контур уже умеет:

1. выполнять mechanism pipeline через `jax.lax.scan`;
2. работать с typed executor layers;
3. запускать PPO-style training и temporal observation loops;
4. поддерживать graph-aware execution.

Но важная оговорка:

1. `agent_sim` — это low-level research / custom executor contour;
2. канонический catalog-facing execution surface для этой зоны шире и живёт через `simulation.*` и `Foundry` compile/execute path.

1. `JAX` нужен для compact state transition, differentiable calibration и learned priors;
2. blueprint не должен предполагать, что весь policy reasoning stack уже живёт внутри одного giant JAX graph.

#### D. Causal and policy contour

Текущий causal stack уже умеет:

1. `identify -> compile -> estimate -> audit`;
2. transportability / selection-bias / regime-aware reasoning;
3. dynamic treatment regimes and temporal intervention trajectories;
4. policy learning and governance-aware output;
5. **interference analysis** через `NetworkCausalData` контракт;
6. **partial identification** через bounds engine (Manski, Balke-Pearl, monotonicity/linearity rescue);
7. **measurement-error identification** через Kuroki-Pearl proxy (identify_with_proxy);
8. **strategic response verification** через Stackelberg/Nash solver;
9. **counterfactual query identification** через id_star/idc_star algorithms.

Плюс `Scientist` уже имеет workflow, где встречаются:

1. `build_data_snapshot`
2. `compile_foundry`
3. `run_simulation`
4. `run_causal_evaluation`
5. `run_governance`
6. `build_decision_packet`

1. `Lex -> intervention map` должен feed-ить и simulation knobs, и causal query surfaces;
2. observation-plane должен уметь выпускать не только calibration bundles, но и causal-ready panels;
3. multiplex graph artifacts должны компилироваться и в `NetworkData`, и в `NetworkCausalData` для interference analysis;
4. partial identification через bounds — primary strategy для censored wartime observations.

#### E. Network, microsim and policy-evaluation contour

Текущие method families уже имеют typed contracts:

1. `NetworkData` / `MultiplexNetworkData`
2. `SurveyMicroData`
3. `MicrosimResult` / `TaxBenefitResult` / `DynamicMicrosimResult`
4. compact vector-based policy evaluation inputs

1. украинские артефакты надо проектировать как источники для этих контрактов;
2. "таблица есть" недостаточно — нужен compiler into method-native contract.

#### F. Dense-contract caveat

Код показывает ещё одно важное ограничение:

1. текущие `NetworkData` и `MultiplexNetworkData` ожидают dense `numpy`-массивы;
2. это плохо совместимо с full-country multiplex graphs на `CPX62`.

1. runtime должен хранить sparse / low-rank / embedded graph artifacts;
2. dense network contracts нужно materialize-ить только для selected subgraphs, strategic cohorts или cell-level slices.

#### G. Econometrics and survival contour

Текущие method families уже имеют native contracts для:

1. **Panel econometrics**: fixed/random effects, GMM, dynamic panels — natural execution path для firm annual panels и labor quarterly panels;
2. **Selection models** (Heckman): firm exit из ЄДР — textbook selection problem, где exit is non-random;
3. **IV estimation**: instrumental variables для endogenous policy channels;
4. **Factor models**: latent factor extraction из firm fundamentals для dimension reduction;
5. **Survival / hazard**: firm bankruptcy, wage arrears, enforcement events — time-to-event targets с right-censoring;
6. **Count data**: procurement contract counts, licensing events — discrete outcome models.

1. observation families должны компилироваться не только в calibration targets, но и в **econometric-ready и survival-ready contracts**;
2. firm exit selection bias нужно корректировать через Heckman, а не игнорировать;
3. survival targets — natural companion to distress / enforcement observation families.

#### H. Optimization and game-theory contour

Текущие optimization methods уже поддерживают:

1. **Bilevel optimization**: government sets procurement rules (upper), firms optimize response (lower) — прямая модель public procurement;
2. **Chance-constrained optimization**: budget allocation under revenue uncertainty — natural для wartime fiscal planning;
3. **Game theory (Nash)**: equilibrium в procurement markets с множеством участников;
4. **Leontief IO с stochastic extension**: regional input-output under wartime disruption;
5. **Multi-objective (NSGA2)**: Pareto-optimal policy search.

1. `Lex -> intervention map` должен feed-ить не только simulation knobs, но и **optimization problem specs**;
2. bilevel formulation — natural companion для strategic response verification.

#### I. Agent sim population and lifecycle contour

Текущий `agent_sim` уже имеет:

1. `PopulationAwareExecutor`: births, deaths, aging, migration, inheritance — natural для household lifecycle;
2. `GraphAwareExecutor`: labor market networks, lending chains, information diffusion — natural для procurement supply chains;
3. `DistributionAwareExecutor`: real-time Gini/Palma tracking, quantile group assignment — natural для welfare monitoring;
4. Ready mechanisms: `DistributionAwareTaxMechanism`, `TargetedTransferMechanism`, `RelativeConsumptionMechanism`.

1. household block lifecycle (births, aging, migration) должен использовать `PopulationAwareExecutor` напрямую;
2. procurement chain diffusion — через `GraphAwareExecutor`;
3. welfare monitoring — через `DistributionAwareExecutor` с Gini/Palma;
4. targeted transfers и progressive taxation — через готовые mechanisms.

#### J. Scientist governance and discovery contour

Текущий `Scientist` уже имеет:

1. **23 governance passes** с cost-aware ordering и short-circuit policy;
2. **Adversarial testing**: `STRATEGIC_GAMING`, `MULTIPLICITY_DISCLOSURE`, `ABSTRACTION_LEAKAGE` suites;
3. **Lesson registry**: `LessonCard` (FAILURE/SUCCESS) с transfer-aware weighting и cross-domain reuse;
4. **Active disambiguation**: `ActiveDisambiguationPlanner` с utility-ranked targets;
5. **Hierarchical policy search**: `STRUCTURE → PARAMETER → NARRATIVE` с Pareto tracking;
6. **Trust scoring**: A-F grading с weighted coverage + MAPE + bias;
7. **Policy translator**: compliance translation с `TranslatorCompliancePass`.

1. calibration governance должна использовать explicit pass mapping, а не generic validation;
2. adversarial suites должны быть частью calibration quality gate;
3. lesson registry должна аккумулировать calibration run outcomes;
4. active disambiguation может приоритизировать data collection.

### 2.6. Honest support matrix

#### Already supported natively

1. `DataViewRequest -> DataSnapshot -> Foundry input bindings`
2. alignment / resampling monthly and annual targets
3. pure-scan calibration over compiled execution graphs
4. survey-aware and microsim-aware input path
5. trust-aware historical backtesting and replay verification
6. symbolic causal identification, transportability and governance
7. **interference analysis** through `NetworkCausalData` contract
8. **partial identification** through bounds engine (Manski, Balke-Pearl, monotonicity rescue)
9. **measurement-error identification** through Kuroki-Pearl proxy
10. **dynamic treatment regimes** through Q-learning, A-learning, OWL, doubly-robust DTR
11. **strategic response verification** through Stackelberg/Nash solver
12. **counterfactual query identification** through id_star/idc_star
13. **panel econometrics** through fixed/random effects, GMM, dynamic panels
14. **selection models** (Heckman) for endogenous exit correction
15. **survival / hazard analysis** for time-to-event targets
16. **bilevel and game-theoretic optimization** for policy design
17. **Sobol indices and specification curves** for sensitivity diagnostics
18. **23 governance passes** with cost-aware ordering
19. **adversarial testing suites** for robustness verification
20. **lesson registry** for cross-run learning
21. **active disambiguation** for discovery-guided data priorities
22. **population-aware executor** for household/firm lifecycle
23. **graph-aware executor** for network diffusion
24. **distribution-aware executor** for welfare tracking
25. **hierarchical policy search** (structure → parameter → narrative)

#### Requires explicit code additions

1. `SlotScope.PER_CELL`
2. first-class `CellState`
3. `GlobalState` / input-binding support for cell-level state
4. observation-record -> target / microsim / network / causal / backtest / **econometric / survival / interference** compilers
5. measurement-aware loss adapter over current `loss.py`
6. sparse-to-dense / low-rank bridge for `network` contracts
7. domain-typed multiplex graph layer conventions
8. explicit `Lex` intervention compiler into simulation and causal surfaces
9. **interference-aware loss component** for graph-level calibration targets
10. **identification-mode router** that dispatches observation families to correct causal strategy
11. **governance pass mapping registry** per observation family
12. **temporal intervention sequence compiler** for DTR surfaces

#### Should stay outside the inner JAX loop

1. symbolic identification and transportability
2. replay verification and trust scoring
3. scorecard / budget-impact / governance diagnostics
4. raw ETL and heavy event-level joins
5. **strategic response equilibrium solving**
6. **adversarial testing suites**
7. **active disambiguation planning**
8. **Heckman selection correction** (pre-calibration adjustment)

---

## 3. Design Principles

### 3.1. Artifact-first, not connector-first

На первом этапе дизайн должен строиться вокруг конечных артефактов, а не вокруг максимального числа production connector-ов.

### 3.2. Observation-first, not raw-data-first

Калибровка нуждается не в максимуме сырья, а в измеримых наблюдениях:

1. с привязкой к времени;
2. с привязкой к агенту, cell или макро-узлу;
3. с известным доверием и покрытием.

### 3.3. Multiscale, not flat-agent simulation

Нельзя симулировать всех агентов одинаково.
Нужно держать минимум три уровня:

1. `macro state`
2. `region x sector cells`
3. `strategic micro-agents`

### 3.4. Measurement-aware, not naive-observed-reality

Украинские открытые данные военного времени не равны "идеальной реальности".
Нужно явно моделировать:

1. censored data;
2. incomplete coverage;
3. reporting lags;
4. regime shifts;
5. administrative noise.

### 3.5. Intervention-first policy simulation

Связь `Lex -> simulation` должна быть не концептуальной, а явной:

1. норма;
2. rule interpretation;
3. intervention knob;
4. target population;
5. expected transmission channel.

### 3.6. CPX62 realism

План должен оставаться жизнеспособным на `CPX62`:

1. без dense matrices;
2. без full population micro-sim на всех фирмах;
3. без постоянных тяжёлых joins в runtime;
4. без огромного persistent raw lake.

### 3.7. Slot-family first, not table-first

Новые артефакты нужно проектировать не только как `parquet`-таблицы, но и как slot families:

1. `stock`
2. `flow`
3. `parameter`
4. `per_agent`
5. `per_firm`
6. `per_cell`
7. `global`

Это делает `static / slow / fast` split совместимым с существующим `slot registry` и упрощает `Foundry input bindings`.

`PER_CELL` при этом должен считаться не optional extension, а обязательным architecture change для `v1+`.

### 3.8. Dual execution contour, not one monolithic differentiable stack

Blueprint должен явно разделять два связанных, но разных контура.

#### Differentiable contour

Сюда входят:

1. compact runtime state;
2. `JAX` state transitions;
3. pure-scan calibration;
4. learned embeddings and low-rank priors;
5. measurement-aware differentiable losses.

#### Symbolic / governance contour

Сюда входят:

1. causal identification;
2. transportability checks;
3. replay and backtesting;
4. normative / policy governance;
5. scorecard and decision-packet assembly.

Они должны обмениваться typed artifacts, а не пытаться стать одним computational graph.

### 3.9. Identification-mode routing, not one-size-fits-all estimation

Каждая observation family имеет свой identification context:

1. **point-identified channels**: macro indicators с high coverage и low censoring → standard calibration;
2. **partially-identified channels**: wartime censored data → bounds engine (Manski, Balke-Pearl);
3. **proxy-identified channels**: tax debt как proxy distress, procurement revenue как proxy cashflow → Kuroki-Pearl identification;
4. **interference-aware channels**: procurement и budget graphs с spillover → NetworkCausalData + SUTVA Check Pass;
5. **sequential channels**: temporal intervention sequences → DTR identification.

Blueprint должен явно маршрутизировать каждую observation family в правильный identification mode, а не предполагать, что все каналы point-identified.

### 3.10. Full governance coverage, not ad-hoc validation

Для каждой observation family и calibration run нужен explicit mapping к governance passes:

1. **SUTVA Check Pass** — для всех graph-based observation families (procurement, budget, trade);
2. **Transportability Required Pass** — при переносе estimates между Regime A/B/C;
3. **Equity Pass** — для household distributional analysis;
4. **Freshness Pass** — для источников с разным lag;
5. **Refutation Pass** — для negative controls и falsification targets;
6. **Cross-Graph Evidence Pass** — для multi-source consistency;
7. **Confidence Pass** — для uncertainty envelope validation.

### 3.11. Strategic response awareness, not static agent assumption

Для top policy channels нужна explicit проверка strategic adaptation:

1. procurement participants адаптируются к threshold changes;
2. firms restructure in response to tax regime changes;
3. public entities optimize budget allocation under new rules.

`evaluate_strategic_hook()` из `strategic.py` должен быть standard step для major policy channels.

---

## 4. Multiscale World Architecture

### 4.1. Почему multiscale

Если пытаться симулировать всех экономических агентов Украины на одном уровне детализации, система быстро упирается в:

1. память;
2. нестабильность калибровки;
3. слабую идентифицируемость;
4. слишком дорогой runtime.

Поэтому мир должен быть иерархическим.

### 4.2. Layer A — Macro State

Macro state описывает экономику страны и крупные режимные параметры.

Примеры:

- CPI / inflation
- exchange rate
- NBU policy rate
- national wage dynamics
- national employment / unemployment
- government balance proxy
- macro demand / credit / output factors

Назначение:

1. exogenous and semi-endogenous anchors;
2. верхний уровень constraints;
3. calibration backbone.

### 4.3. Layer B — Meso Cells (`region x sector`)

Это основной "массовый" слой симуляции.

Cell определяется как:

```text
region x sector x public/private subtype x optional firm-size bucket
```

Примеры:

- `Kyiv x IT x private`
- `Lviv x healthcare x public provider`
- `Dnipro x manufacturing x exporters`

Для каждой cell хранятся агрегаты:

- active firm count
- labor demand
- wage pressure
- procurement exposure
- budget dependency
- trade dependency
- distress pressure
- productivity proxy

Назначение:

1. масштабировать симуляцию;
2. поглощать "обычных" агентов;
3. делать policy propagation tractable.

#### Required runtime contract change

Для этого слоя нужен first-class `CellState`, а не только `parquet` с агрегатами.

Минимальные изменения архитектуры:

1. добавить `PER_CELL` в `SlotScope`;
2. завести `CellState` в `Foundry` contracts;
3. добавить `cell`-level input bindings;
4. разрешить `GlobalState` содержать macro + cell + strategic-agent + household blocks.

### 4.4. Layer C — Strategic Micro-Agents

На micro-level попадают только агенты, которые реально критичны:

1. крупные фирмы;
2. стратегические поставщики;
3. крупнейшие получатели бюджетных средств;
4. крупные экспортеры / импортеры;
5. муниципальные utilities;
6. крупные hospitals / schools / authorities;
7. entities с высокой network centrality;
8. агенты с высоким distress or compliance relevance.

Назначение:

1. сохранить реализм там, где важна индивидуальность;
2. не тратить память на всё остальное;
3. делать fine-grained counterfactuals.

#### Strategic response verification for micro-agents

Strategic micro-agents — primary candidates для `evaluate_strategic_hook()`:

1. крупные procurement participants — Stackelberg response to threshold changes;
2. крупные бюджетные получатели — budget allocation optimization;
3. крупные экспортеры — trade policy adaptation.

Для этих агентов policy simulation должна включать explicit strategic response check через существующий solver в `strategic.py`.

### 4.5. Layer D — Synthetic Households

Households не должны быть просто side note.

Даже без персональных данных можно построить отдельный household block:

1. `region x decile x household_type`
2. labor-force participation
3. wage income dependence
4. transfer dependence
5. consumption basket structure
6. housing cost pressure
7. child / elderly composition

Назначение:

1. welfare analysis;
2. distributional effects;
3. labor supply feedback;
4. household demand response.

#### Runtime executor fit

Household block напрямую ложится на существующие agent_sim executors:

1. `PopulationAwareExecutor` — births, aging, migration для household lifecycle;
2. `DistributionAwareExecutor` — real-time Gini/Palma tracking для welfare monitoring;
3. `TargetedTransferMechanism` — targeted social transfers по region x decile;
4. `DistributionAwareTaxMechanism` — progressive taxation effects;
5. `RelativeConsumptionMechanism` — relative consumption dynamics.

Это не future extension, а **уже готовый execution path**.

### 4.6. Cross-scale consistency

Нужно обеспечить явную согласованность:

```text
strategic micro-agents aggregate into meso cells
meso cells aggregate into macro state
synthetic households interact with labor market and transfers
```

Если micro-level и macro-level расходятся, симуляция должна это явно фиксировать как calibration failure.

---

## 5. Typed Agent Ontology

### 5.1. Economic agent types

Нужна явная типизация, а не один тип `economic_agent`.

Минимум:

1. `private_firm`
2. `sole_proprietor`
3. `public_budget_manager`
4. `public_budget_recipient`
5. `public_procurer`
6. `public_service_provider`
7. `municipal_utility`
8. `school`
9. `hospital`
10. `authority`
11. `nonprofit`
12. `external_node`

### 5.2. Why public ontology matters

Сейчас public-side agents легко смешиваются между собой.

Но для interpretation и simulation это критично:

1. budget manager не то же самое, что recipient;
2. procurer не то же самое, что service provider;
3. municipal utility ведёт себя не как private supplier;
4. hospital или school получают и тратят деньги по другим rules.

### 5.3. Ontology outputs

Артефакты:

- `public_entity_registry.parquet`
- `agent_type_dictionary.json`
- `entity_role_flags.parquet`

### 5.4. Public Service Domains

Public-side слой нужно вынести в отдельный domain block, а не размазывать по нескольким разделам.

Минимум пять domain families:

1. `health`
2. `education`
3. `roads / infrastructure`
4. `construction / capital formation`
5. `treasury / public buyers / budget execution`

Почему это важно:

1. эти domains имеют разные transmission channels;
2. для них нужны разные ontology roles;
3. они дают разные public-service observables;
4. именно здесь `Lex` часто превращается в concrete intervention knobs.

### 5.5. Agent lifecycle and population dynamics

Agent ontology должна учитывать, что агенты не статичны:

1. **firm entry/exit**: ЄДР фиксирует registration и liquidation — это survival targets;
2. **firm type transitions**: sole_proprietor → private_firm, mergers, splits;
3. **public entity reorganization**: ministry restructuring, authority mergers.

Эти transitions native для `PopulationAwareExecutor` (births, deaths, migration) и должны корректироваться через **Heckman selection models** из econometrics family, потому что exit из ЄДР — non-random.

---

## 6. Source Priority Stack

### 6.1. P0 — обязательно для первого snapshot

| Источник | Зачем нужен |
|---|---|
| ЄДР current | identity layer |
| Spending.gov.ua | бюджетные потоки |
| Prozorro | procurement graph |
| НБУ + Держстат | макро и regional panels |
| ДПС: фінансова звітність | firm fundamentals для `size / leverage / fragility / retained earnings` |

### 6.2. P1 — simulation-critical enrichments

| Источник | Что даёт |
|---|---|
| ДПС: ПДВ / tax debt / risk | compliance + distress |
| customs export/import | trade exposure |
| customs foreign commercial vehicles | logistics friction proxy |
| служба занятості | labor market signals |
| реєстр ліцензій | regulated activity |
| реєстр розпорядників / одержувачів | public ontology |
| NSZU payments | domain-specific public-service flows |
| ЄДЕБО / education registry | schools, colleges, universities, education governance |
| ЄДЕССБ / construction registry | permits, commissioning, geography of capital formation |
| road characteristics datasets | accessibility / cost-to-serve proxies |
| OSM exact | cheap geo enrichment |
| validated raster / exogenous open layers | `damage / activity / accessibility / climate stress` for `region x sector` cells |

### 6.3. P2 — calibration-critical enrichments

| Источник | Что даёт |
|---|---|
| household microdata | distributional household targets |
| labor-force microdata | labor participation structure |
| ПФУ debt | arrears and stress |
| wage arrears datasets | household / firm distress |
| enforcement / debtor / bankruptcy / court layers | default hazard |
| logistics / mobility / displacement layers | transport and relocation pressure |
| land cadastre | land-use / agriculture / real-estate spatial proxies |

### 6.4. P3 — investigation backlog и research-heavy layers

| Источник | Почему откладывается |
|---|---|
| НАЗК | высокая сложность и sensitivity |
| Open Budget | полезно, но не блокирует v1 |
| Prozorro.Sale | отдельный рынок |
| historical pre-2022 ЄДР | большой ops overhead |
| OSM fuzzy matching | research-heavy и RAM-heavy |
| local mobility and relocation datasets | сильный сигнал, но высокий drift / coverage risk |
| deep domain registries по секторам | могут быть очень полезны, но требуют отдельной ontology story |

### 6.5. Priority interpretation

Приоритет читается так:

1. `P0` формирует runtime and calibration backbone;
2. `P1` добавляет critical transmission channels и typed state families;
3. `P2` усиливает identifiability, welfare realism и hazard modeling;
4. `P3` остаётся backlog до появления отдельной transportability and validation story.

### 6.6. Source Confidence Tiers

Помимо приоритета нужен второй orthogonal dimension: confidence tier.

#### `core`

Источники, которые можно использовать как backbone без дополнительного research layer:

1. `ЄДР`
2. `Spending`
3. `Prozorro`
4. `НБУ`
5. `Держстат`
6. `DPS financial statements`

#### `validated`

Источники, которые полезны и уже имеют явный fit to execution surfaces, но требуют domain-specific QA:

1. household/labor microdata
2. distress layers
3. customs trade
4. customs vehicle/logistics layers
5. NSZU domain flows
6. education registries
7. road/accessibility layers
8. raster/exogenous cell observables

#### `exploratory`

Источники с высоким потенциалом, но требующие отдельной transportability/coverage story:

1. cadastre
2. displacement / mobility layers
3. local infrastructure datasets
4. deep sector-specific registries

---

## 7. Observation Horizon and Regimes

### 7.1. Spending

Официальный портал указывает запуск **15 сентября 2015 года**.
Это даёт примерно `127` monthly points с `2015-09` по `2026-03`.

### 7.2. Prozorro

Официальная страница `Prozorro` указывает:

1. **1 апреля 2016 года** — обязательность для ряда заказчиков;
2. **1 августа 2016 года** — обязательность для остальных заказчиков.

Это даёт:

1. до `120` monthly periods от `2016-04`;
2. около `116` "полных" periods от `2016-08`.

### 7.3. Temporal regimes

Нельзя считать весь период одним однородным процессом.

Нужно явно ввести:

```text
Regime A: 2015-09 / 2016-04 -> 2022-02
Regime B: 2022-03 -> 2023-12
Regime C: 2024-01 -> 2026-03
```

#### Formal transportability between regimes

Перенос estimates между режимами не должен быть implicit.

Каузальный движок уже имеет `tr_algorithm` (Bareinboim & Pearl 2012) и `mz_id_algorithm` для formal transportability через SelectionDiagram и S-nodes.

Для украинского bundle:

1. estimate calibrated on Regime A, applied to Regime C → нужен formal `tr_algorithm` check;
2. multi-regime estimation → `mz_id_algorithm` для multi-source identification;
3. regime boundary → автоматический **Transportability Required Pass** в governance.

Без этого calibration run рискует молча переносить pre-war relationships в post-war context.

### 7.4. Hidden holdouts

Для calibration governance план должен сразу резервировать:

1. `holdout_2025`
2. либо `last_12_months`
3. и optional hidden stress windows внутри военного периода

Без этого будет слишком легко переобучиться на исторический трек.

---

## 8. Measurement Model

### 8.1. Почему measurement model обязателен

Украинские открытые данные нельзя интерпретировать как идеальную ground truth.

Проблемы:

1. wartime redactions;
2. неполное покрытие;
3. reporting lag;
4. административный шум;
5. режимные изменения публикации;
6. censoring by design.

Если этого не моделировать, `JAX` будет подгонять поведение под артефакты публикации, а не под экономику.

### 8.2. Canonical observation record

Каждое наблюдение в observation plane должно иметь минимум:

```sql
observed_value
coverage_estimate
measurement_bias_flag
censoring_mask
trust_weight
source_id
source_version
regime_id
schema_regime_id
```

### 8.3. Extended observation schema

```sql
observation_id
time_grain
period_start
period_end
entity_scope
entity_id NULLABLE
cell_id NULLABLE
region_code NULLABLE
sector_id NULLABLE
metric_id
observed_value
unit
coverage_estimate
measurement_bias_flag
censoring_mask
trust_weight
lag_days_estimate
source_id
source_version
regime_id
shock_mask
schema_regime_id
identification_mode
proxy_source_id NULLABLE
notes_json
```

Новые поля:

1. `identification_mode` — `point_identified | partially_identified | bounds_only | proxy_identified | interference_aware | sequential` — определяет, какой каузальный identification algorithm применим;
2. `proxy_source_id` — для proxy-identified observations, ссылка на source, через который идёт proxy identification.

### 8.4. Trust tiers

Пример trust hierarchy:

1. `authoritative_high_coverage`
2. `authoritative_partial_coverage`
3. `administrative_noisy`
4. `derived_proxy`
5. `weak_anchor`

### 8.5. Measurement-aware loss

Любая calibration loss должна уметь использовать:

```text
weighted_error = trust_weight * coverage_estimate * error
```

и optionally downweight:

1. censored observations;
2. lagged observations;
3. regime-boundary observations.

### 8.6. Schema-regime versioning and changepoints

Для украинских open data нужно явно хранить:

1. `schema_regime_id`
2. `source_version`
3. detected `changepoints`
4. publication-regime notes

Иначе тихое изменение структуры или coverage будет ошибочно интерпретировано как экономический сигнал.

### 8.7. Measurement-error and censoring are part of the model, not just metadata

`Measurement-error / censoring models` должны существовать не только на уровне описаний в manifest, но и в самих objective functions:

1. доверие к наблюдению должно влиять на loss;
2. partially censored data должны иметь отдельные masks;
3. regime boundaries должны автоматически повышать uncertainty;
4. weak-anchor metrics не должны доминировать при calibration.

### 8.8. Current code fit and required extension

Текущий `Foundry` calibration code уже умеет:

1. target-level weights;
2. relative scaling;
3. Huber / MSE losses;
4. aligned time axes after preflight.

Но текущий `loss.py` пока не умеет first-class:

1. `trust_weight`
2. `coverage_estimate`
3. `censoring_mask`
4. `schema_regime_id`-aware downweighting

1. measurement model нельзя считать "уже реализованным";
2. для `v1+` нужен отдельный measurement-aware adapter, который компилирует observation records в arrays `targets + masks + weights + trust`.

### 8.9. Formal measurement-error identification through Kuroki-Pearl

Помимо measurement-aware loss, для ряда observation families нужна **formal measurement-error identification**.

Каузальный движок уже имеет `identify_with_proxy()` в `measurement_error.py`, который:

1. проверяет proxy validity: C* ⊥ Y | (C, X) в графе;
2. проверяет non-degeneracy: P(C*|C) has full rank;
3. при success — выпускает `ProxyAdjustmentNode` AST;
4. при failure — возвращает `ORACLE_NEEDED` для research gating.

Плюс три estimation modes:

1. `regression_calibration` (Carroll et al. 2006);
2. `SIMEX` extrapolation (Cook & Stefanski 1994);
3. `bounds_with_measurement_error` (Manski + error correction).

Для украинского bundle:

1. **tax debt как proxy distress** → `identify_with_proxy(proxy_map={"distress": "tax_debt"})`;
2. **procurement revenue как proxy firm cashflow** → proxy identification;
3. **administrative employment как proxy true employment** → proxy identification;
4. для каждого proxy channel нужен формальный identification check, а не просто downweight.

Это не adds computation cost — identification check symbolic и дешёвый.

---

## 9. Observation Plane

### 9.1. Observation-plane first-class citizen

Observation plane должен стать отдельным основным архитектурным слоем, а не appendix.

### 9.2. Основные компоненты

Observation plane включает:

1. observation contracts
2. observation operators
3. measurement model
4. regime masks
5. train/validation/test splits
6. hidden holdout periods
7. leaderboard-ready evaluation bundles
8. **identification-mode routing per family**
9. **governance pass mapping per family**
10. **method-contract compilation targets**

### 9.3. Observation families

Нужно минимум тринадцать семейств наблюдений:

1. `budget flows`
2. `procurement flows`
3. `macro state`
4. `firm fundamentals`
5. `trade exposure`
6. `labor market`
7. `household distribution`
8. `distress / enforcement`
9. `spatial / raster exogenous`
10. `public service domain flows`
11. `education and human-capital supply`
12. `construction / capital formation`
13. `logistics friction`

### 9.4. Observation family identification-mode and governance mapping

Для каждой observation family нужен explicit identification mode и governance mapping:

| Family | Primary ID mode | Fallback ID mode | Mandatory governance passes |
|---|---|---|---|
| budget flows | point_identified | bounds (wartime censoring) | SUTVA Check, Freshness, Equity |
| procurement flows | interference_aware | bounds (wartime) | SUTVA Check, Transportability Required, Strategic Gaming adversarial |
| macro state | point_identified | — | Confidence, Freshness |
| firm fundamentals | point_identified (annual) | selection_corrected (exit bias) | Refutation, Freshness |
| trade exposure | point_identified | bounds (sanctions regime) | Transportability Required |
| labor market | proxy_identified | bounds (informal sector) | Equity, SUTVA Check |
| household distribution | proxy_identified | bounds (coverage gaps) | Equity, Confidence, Refutation |
| distress / enforcement | partially_identified | survival_censored | Refutation, Confidence |
| spatial / raster exogenous | point_identified | — | Freshness |
| public service domain flows | point_identified | bounds (wartime) | SUTVA Check, Equity |
| education | point_identified | — | Freshness |
| construction / capital formation | point_identified | bounds (permit delays) | Freshness |
| logistics friction | proxy_identified | bounds | Transportability Required |

Identification mode определяет:

1. какой causal identification algorithm применяется;
2. какой loss component используется в calibration;
3. какие governance passes обязательны;
4. нужен ли proxy identification check через `identify_with_proxy()`.

### 9.5. Observation operators

Калибровка должна опираться не на raw events, а на наблюдаемые проекции состояния:

```text
O_budget(state, t)
O_proc(state, t)
O_macro(state, t)
O_firm(state, y)
O_trade(state, t)
O_labor(state, t)
O_household(state, y)
O_distress(state, t)
O_spatial(state, t)
O_public_service(state, t)
O_education(state, t)
O_construction(state, t)
O_logistics(state, t)
```

### 9.6. Train / validation / test

Обязательная разбивка:

1. `train_pre_2024`
2. `validation_2024`
3. `test_2025_or_last12m`

Плюс optional:

4. `hidden_holdout_blackout_window`
5. `hidden_holdout_policy_change_window`

### 9.7. Calibration leaderboard

Нужен отдельный evaluation artifact:

- `calibration_leaderboard.json`

С метриками:

1. macro fit
2. meso fit
3. micro fit
4. household fit
5. distress fit
6. regime robustness
7. holdout robustness
8. **specification-curve robustness** (Sobol indices по source combination)
9. **transportability score** (Regime A → C transfer quality)
10. **interference fit** (graph-level prediction accuracy)
11. **strategic response plausibility** (performative shift bounds)

### 9.8. Execution-surface fit with existing PolicyOS

Blueprint должен явно использовать уже существующие surfaces:

1. household/labor microdata -> `survey.weighting`, `survey.imputation`, `survey repeated cross-section` bindings;
2. spatial/raster layers -> `spatial.advanced` methods и `cell`-level latent fields;
3. monthly panels -> `forecasting.univariate`, `bayesian.timeseries`, `validation.diagnostics`;
4. calibration bundles -> `Scientist` replay, hidden holdout, refutation governance;
5. runtime state exports -> `slot registry`, `foundry.input_bindings`, `GlobalState` initialization.

Дополнительно:

6. household and labor targets -> `microsim`, `reweighting`, `tax-benefit` surfaces;
7. budget/procurement/trade/distress graphs -> `network` and `multiplex` surfaces;
8. `region x sector` panels -> `input-output`, `system dynamics`, `budget impact`, `ex ante` surfaces;
9. rich welfare targets -> `distributional` and `social welfare` surfaces;
10. holdout bundles -> `Scientist` trust-aware backtesting.

Новые surfaces, ранее не задействованные:

11. **firm panels** -> `econometrics.panel` (fixed/random effects, GMM, dynamic panels);
12. **firm exit / bankruptcy** -> `econometrics.selection` (Heckman correction для exit bias) + `ml.survival` (hazard models);
13. **procurement / budget graphs** -> `causal.protocols.NetworkCausalData` (interference analysis);
14. **wartime censored data** -> `causal.bounds_engine` (Manski, Balke-Pearl partial identification);
15. **proxy indicators** -> `causal.measurement_error` (Kuroki-Pearl identification + SIMEX/regression_calibration);
16. **temporal intervention sequences** -> `causal.dtr` (Q-learning, A-learning, OWL, doubly-robust DTR);
17. **policy channels with strategic agents** -> `causal.strategic` (Stackelberg/Nash equilibrium verification);
18. **counterfactual policy questions** -> `causal.id_engine.id_star_algorithm` (formal counterfactual identification);
19. **calibration robustness** -> `sensitivity.sobol` (Sobol indices) + `sensitivity.specification` (specification curves);
20. **procurement / budget optimization** -> `optimization.bilevel` + `optimization.game_theory` + `optimization.chance_constrained`;
21. **household lifecycle** -> `agent_sim.population` (PopulationAwareExecutor);
22. **welfare monitoring** -> `agent_sim.distribution_aware` (DistributionAwareExecutor + Gini/Palma);
23. **network diffusion** -> `agent_sim.graph_aware` (GraphAwareExecutor).

### 9.9. Observation-to-contract compilers

Observation plane должен уметь выпускать не только unified panels, но и typed method contracts.

Расширенный набор compiler outputs:

1. `observation_panel -> calibration_target_bundle`
2. `observation_panel + household sources -> SurveyMicroData`
3. `graph artifacts -> NetworkData / MultiplexNetworkData`
4. `observation_panel -> causal-ready panel bundles`
5. `observation_panel -> HistoricalValidationPlan bundles`
6. `graph artifacts -> NetworkCausalData` (interference-aware causal contracts)
7. `censored observation panel -> BoundsEstimationInput` (partial identification contracts)
8. `proxy-identified observations -> ProxyIdentificationInput` (measurement-error contracts)
9. `firm panels -> PanelEconometricData` (panel econometrics contracts)
10. `firm exit / bankruptcy events -> SurvivalData` (time-to-event contracts)
11. `temporal intervention sequences -> DynamicTreatmentData` (DTR contracts)
12. `policy channel panels -> SpecificationCurveInput` (sensitivity contracts)
13. `region x sector panels -> LeontiefIOInput` (input-output contracts)

Это нужно потому что текущий код ожидает не "любую таблицу", а конкретные контрактные формы.

### 9.10. Dense method contracts vs sparse runtime reality

Blueprint должен честно учитывать кодовое ограничение:

1. network and multiplex method contracts сейчас dense;
2. runtime and storage strategy в украинском bundle должны быть sparse / low-rank;
3. full-country dense materialization нельзя делать default path на `CPX62`.

Поэтому strategy должна быть такой:

1. хранить sparse / embedded graph artifacts;
2. materialize-ить dense contracts только on demand;
3. предпочитать cell slices, strategic-agent subgraphs и learned prototypes.

---

## 10. Agent State Model

### 10.1. Static / Slow / Fast split

Состояние агента должно быть разделено на три группы.

#### Static variables

Меняются редко или почти не меняются.

Примеры:

- org_form
- sector
- region
- public/private type
- license flags
- export/import class
- ontology role

#### Slow variables

Меняются, но не каждый месяц.

Примеры:

- productivity class
- compliance propensity
- leverage class
- trade orientation
- logistics dependence
- wage policy regime
- budget dependency class
- procurement specialization
- enforcement susceptibility

#### Fast variables

Меняются на monthly step.

Примеры:

- monthly cashflow
- procurement revenue
- budget inflow
- hiring pressure
- distress score
- short-term liquidity stress
- inventory / demand proxy
- wage arrears pressure
- legal enforcement pressure

### 10.2. Why this matters

Этот split даёт:

1. меньшую память;
2. меньше неидентифицируемых параметров;
3. лучшее conditioning для autodiff;
4. более стабильный runtime.

### 10.3. Cell state model

Для `region x sector cells` нужен отдельный state:

```sql
cell_id
region_code
sector_id
firm_count
employment_proxy
wage_pressure
budget_dependency
procurement_dependency
trade_dependency
distress_pressure
productivity_index
accessibility_index
damage_proxy
energy_reliability_proxy
```

Это не просто logical schema.
Для `v1+` нужен реальный runtime contract:

```python
class CellState:
    cell_id
    region_code
    sector_id
    public_private_subtype
    size_bucket
    firm_count
    employment_proxy
    wage_pressure
    budget_dependency
    procurement_dependency
    trade_dependency
    distress_pressure
    accessibility_index
    damage_proxy
```

Именно через него `region x sector` слой станет first-class частью `Foundry`, а не только промежуточной таблицей.

### 10.4. Strategic micro-agent state

Для strategic agents хранить richer state:

```sql
agent_id
sector_id
region_code
size_class
public_role_flags
budget_dependency
procurement_dependency
trade_dependency
liquidity_proxy
distress_score
compliance_propensity
network_centrality_proxy
trade_orientation_class
hazard_state
```

### 10.5. Multiplex graph family

Графовая часть украинского bundle должна описываться не как один adjacency export, а как multiplex family.

Минимальные слои:

1. `budget_flow_graph`
2. `procurement_graph`
3. `trade_graph`
4. `distress_graph`
5. `public_service_graph`

Это важно потому что:

1. разные каналы распространяют policy shocks по-разному;
2. `network` methods уже умеют работать с multiplex structure;
3. это даёт better compression и better priors, чем попытка хранить всё в одном универсальном графе.

#### Dual compilation: NetworkData + NetworkCausalData

Каждый graph layer должен компилироваться в **два контрактных формата**:

1. `NetworkData` / `MultiplexNetworkData` — для network analysis (centrality, diffusion, community detection);
2. `NetworkCausalData` — для interference-aware causal estimation (spillover, SUTVA violation detection).

`NetworkCausalData` принимает `adjacency_matrix`, `cluster_id`, `coordinates`, `bipartite_edges` — это уже готовый контракт.

Для procurement graph это прямое применение: procurement shock к одному заказчику spillover-ит через граф поставщиков. Interference analysis через `NetworkCausalData` даёт formal estimation of spillover effects.

### 10.6. Current runtime contract reality

Текущий код показывает, что `v1` нельзя описывать так, будто multiscale runtime уже существует.

Сейчас:

1. `foundry/contracts/state.py` описывает `agents + firms + market`;
2. `foundry/agent_sim/state.py` описывает `agents + policy + aggregates + distributions + graph`;
3. `foundry/data_plane/bindings.py` умеет автоматически infer only `n_agents` and `n_firms`.

То есть:

1. `CellState` ещё не first-class;
2. public-service domains ещё не являются native runtime block;
3. cell-aware binding logic реально нужно добавить.

Но agent_sim уже имеет:

4. `PopulationAwareExecutor` для births/deaths/migration — ready для firm entry/exit и household lifecycle;
5. `GraphAwareExecutor` для labor/lending/information diffusion — ready для procurement supply chain propagation;
6. `DistributionAwareExecutor` для Gini/Palma — ready для welfare tracking;
7. ready mechanisms: `TargetedTransferMechanism`, `DistributionAwareTaxMechanism`, `RelativeConsumptionMechanism`.

### 10.7. JAX simulation logic for this blueprint

Для украинского bundle `JAX` нужно использовать прежде всего для:

1. compact state transitions over macro / cells / strategic micro-agents;
2. differentiable calibration against aligned observation bundles;
3. learned priors and graph compression;
4. selective policy-gradient / behavioral training for compact agent cohorts.

Не нужно пытаться делать внутри одного JAX graph:

1. full-country dense multiplex graph evaluation;
2. symbolic causal identification;
3. raw event-level supervision;
4. governance and replay logic;
5. **strategic response equilibrium solving** (symbolic, stays outside JAX);
6. **Heckman selection correction** (pre-calibration adjustment);
7. **active disambiguation planning** (symbolic graph analysis).

---

## 11. Learned Agent Embeddings

### 11.1. Зачем embeddings

Из `ЄДР + Spending + Prozorro + financials + trade + distress` можно собрать compact learned embeddings:

- `agent_embedding_32d`
- `agent_embedding_64d`

### 11.2. Что это даёт

1. compresses rich information;
2. уменьшает память;
3. даёт хороший prior для `JAX`;
4. помогает кластеризовать обычных агентов в meso cells;
5. делает nearest-neighbor retrieval для simulation easier.

### 11.3. Recommended artifacts

- `agent_embedding_32d.npz`
- `agent_embedding_dictionary.json`
- `cell_prototype_embeddings.npz`

### 11.4. Recommended use

Embeddings не должны заменять interpretable features.
Они должны дополнять:

1. static/slow/fast state;
2. clustering;
3. initialization priors;
4. similarity search.

### 11.5. Factor models for embedding construction

Embeddings можно строить не только через neural approaches, но и через **factor models** из econometrics family.

`econometrics.factor` уже поддерживает latent factor extraction — natural method для dimension reduction из firm fundamentals + trade + procurement features.

Преимущества factor models:

1. interpretable factors (в отличие от neural embeddings);
2. identifiable rotation (с constraints);
3. cheap computation на CPX62;
4. natural companion для specification-curve analysis.

---

## 12. Synthetic Households

### 12.1. Почему это отдельный слой

Households нужны не только ради social policy.
Они делают симуляцию экономически замкнутой:

1. labor supply
2. consumption demand
3. transfer dependence
4. welfare distribution
5. inflation and energy burden transmission

### 12.2. Household representation

Нужно моделировать не raw households, а cells:

```text
region x income_decile x household_type
```

Где `household_type` минимум:

1. single working-age
2. couple no children
3. couple with children
4. single parent
5. pensioner household
6. mixed multigenerational

### 12.3. Household state

Примеры:

- labor participation
- wage income dependence
- transfer dependence
- consumption basket shares
- housing burden
- energy vulnerability
- child and elderly share

### 12.4. Construction methods for synthetic households

Blueprint должен явно фиксировать, что household layer строится через:

1. `raking / IPF`
2. `survey weighting`
3. `multiple imputation`
4. `optimal transport` between survey marginals and regional anchors
5. `negative-control checks` against impossible demographic or income configurations

То есть synthetic households должны быть не sidecar heuristic, а полноценным calibration artifact.

### 12.5. Household-source mapping

Household block калибруется через:

1. household microdata
2. labor-force microdata
3. wage / unemployment macro panels
4. transfer and public spending layers

### 12.6. Household runtime executor path

Household block напрямую использует существующие agent_sim capabilities:

1. `PopulationAwareExecutor` — births, aging, death, migration для lifecycle dynamics;
2. `DistributionAwareExecutor` — real-time Gini, Palma ratio, quantile tracking;
3. `TargetedTransferMechanism` — social transfers по region x decile;
4. `DistributionAwareTaxMechanism` — progressive tax burden;
5. `RelativeConsumptionMechanism` — consumption dynamics with reference group effects.

Это не future work — это **existing runtime executor path**, который нужно задействовать.

### 12.7. Household welfare evaluation surfaces

Household block также напрямую ложится на Foundry method families:

1. `distributional.poverty` — poverty headcount, gap, severity;
2. `distributional.mobility` — income mobility matrices;
3. `distributional.polarization` — Esteban-Ray polarization;
4. `policy.evaluation` — budget impact, ex ante welfare evaluation;
5. `microsim` — tax-benefit microsimulation с behavioral response.

---

## 13. Lex -> Intervention Model

### 13.1. Почему нужно formal policy actuation layer

Сейчас связь `Lex -> simulation` может остаться слишком абстрактной:

```text
норма есть
но неясно, какой именно knob она крутит
```

Это надо исправить.

### 13.2. Canonical intervention knobs

Минимальный набор:

1. `tax_rate_change`
2. `procurement_threshold_change`
3. `license_constraint_change`
4. `reimbursement_tariff_change`
5. `targeted_subsidy_rule`
6. `transfer_rule_change`
7. `public_wage_rule_change`
8. `capital_spending_reallocation`

### 13.3. Intervention contract

Каждая policy norm должна map-иться в:

```sql
intervention_id
lex_provision_ref
intervention_type
target_population_type
target_sector_ids
target_region_ids
activation_date
deactivation_date NULLABLE
parameter_json
confidence_score
measurement_expectations_json
identification_mode
strategic_response_expected
```

Новые поля:

1. `identification_mode` — какой causal identification mode применим для оценки effect этой intervention;
2. `strategic_response_expected` — boolean flag, нужен ли `evaluate_strategic_hook()` check.

### 13.4. Expected transmission channels

Для каждой intervention должна быть явная связь с каналами:

1. `budget_channel`
2. `procurement_channel`
3. `labor_channel`
4. `trade_channel`
5. `household_income_channel`
6. `compliance_channel`

### 13.5. Lex artifacts

Нужны:

- `lex_intervention_map.json`
- `intervention_knob_dictionary.json`
- `provision_to_program_crosswalk.parquet`

### 13.6. Temporal intervention sequences and DTR

Украинская policy reality — это не singleton knob turns, а **последовательности изменений**:

```text
2022-03: procurement emergency rules activated
2022-06: simplified tax regime for affected regions
2023-01: NSZU tariff adjustments
2023-06: procurement threshold changes
2024-01: tax regime normalization begins
```

Каузальный движок уже имеет полный DTR стек:

1. `DynamicTreatmentData` контракт — `treatment_sequence (n_units, n_periods)` + `covariate_sequence`;
2. `QLearningDTR` — backward induction для optimal sequential policy;
3. `ALearningDTR` — advantage/contrast learning;
4. `OutcomeWeightedLearning` — outcome-weighted classification;
5. `DoublyRobustDTR` — augmented IPW для robustness.

Blueprint должен явно ввести:

1. **temporal intervention sequences** в intervention model — не только singleton knobs;
2. **DTR-ready observation bundles** — observation panels с temporal treatment indicators;
3. `dynamic_intervention_id` из causal engine — для sequential treatment identification.

### 13.7. Strategic response verification for major channels

Для top policy channels нужен explicit strategic response check через `strategic.py`:

1. **procurement_threshold_change** → Stackelberg response (procurers as leaders, suppliers as followers);
2. **tax_rate_change** → firm restructuring response (compliance vs evasion trade-off);
3. **targeted_subsidy_rule** → strategic eligibility manipulation;
4. **reimbursement_tariff_change** → provider service mix optimization.

`evaluate_strategic_hook()` уже существует и может быть вызван из policy simulation node.

Результат — `StrategicSolveResult` с:

1. `performative_shift` — quantified shift from naive to strategic equilibrium;
2. `bounds` — worst-case / best-case envelope;
3. `equilibrium_profiles` — profiles of agent adaptations.

Если `performative_shift` значительный, policy evaluation должна использовать strategic-aware estimates, а не naive.

### 13.8. Hierarchical policy search

Policy simulation может быть не только "крутим один knob", а **полноценный hierarchical search** через `policy_design/search.py`:

1. `STRUCTURE` level — draft policy families (tax reform, procurement reform, subsidy redesign);
2. `PARAMETER` level — fine-tune numeric knobs через Bayesian optimization;
3. `NARRATIVE` level — wording/justification refinement.

Для украинского bundle это означает, что Lex → intervention map → simulation → evaluation pipeline может автоматически **искать оптимальную policy structure**, а не только оценивать заданную.

### 13.9. Counterfactual identification for policy evaluation

Для formal policy evaluation ("what would employment be if procurement threshold hadn't changed?") каузальный движок имеет:

1. `id_star_algorithm` — Layer-3 counterfactual identification;
2. `idc_star_algorithm` — counterfactual + evidence;
3. `conditional_intervention_id` — conditional do-operators.

Это даёт **formal identification guarantees** для counterfactual queries, а не только simulation-based answers.

Blueprint должен зафиксировать, что для major policy channels counterfactual queries проходят через formal identification check перед simulation.

---

## 14. Exogenous Shock Calendar

### 14.1. Почему shock calendar нужен отдельно

Regime masks недостаточно.

Нужен явный календарь шоков:

1. война;
2. blackout periods;
3. FX regime changes;
4. procurement rule changes;
5. reimbursement rule changes;
6. major administrative publication shifts.

### 14.2. Canonical shock schema

```sql
shock_id
shock_type
start_date
end_date
affected_regions
affected_sectors
affected_channels
severity_weight
description
```

### 14.3. Use cases

Shock calendar нужен для:

1. regime-aware losses;
2. backtesting;
3. counterfactual isolation;
4. stress scenarios;
5. **formal transportability checks** — shocks определяют regime boundaries для `tr_algorithm`.

### 14.4. Minimum shock list

На первом этапе явно закодировать:

1. `full_scale_invasion_2022`
2. `blackout_wave_2022_2023`
3. `major_fx_regime_changes`
4. `prozorro_rule_change_events`
5. `nszu_tariff_change_events`

---

## 15. Runtime and Calibration Artifacts

### 15.1. Runtime artifacts

| Артефакт | Формат | Назначение |
|---|---|---|
| `agent_registry_full.parquet` | Parquet | full reference registry |
| `agent_registry_runtime.parquet` | Parquet | runtime cohort |
| `public_entity_registry.parquet` | Parquet | typed public ontology |
| `cell_registry_region_sector.parquet` | Parquet | meso-cell definitions |
| `budget_flows_monthly_sparse.parquet` | Parquet | budget graph |
| `procurement_contracts_monthly.parquet` | Parquet | procurement graph |
| `trade_exposure_monthly.parquet` | Parquet | trade graph |
| `labor_market_panel_monthly.parquet` | Parquet | labor observations |
| `distress_events_panel_monthly.parquet` | Parquet | distress observations |
| `spatial_cell_exogenous_monthly.parquet` | Parquet | raster/exogenous cell observations |
| `education_entity_registry.parquet` | Parquet | education domain ontology |
| `construction_activity_panel_monthly.parquet` | Parquet | capital formation and permit activity |
| `road_accessibility_cell_panel.parquet` | Parquet | accessibility and infrastructure quality |
| `logistics_friction_monthly.parquet` | Parquet | border/logistics pressure |
| `cell_state_seed_v1.npz` | NPZ | compact meso-state initialization |
| `macro_panel_monthly.parquet` | Parquet | macro state |
| `geo_index_runtime.parquet` | Parquet | coarse geo |
| `lex_crosswalks.parquet` | Parquet/JSON | legal and code crosswalks |
| `foundry_seed_state_v1.npz` | NPZ | compact seed state |
| `slot_family_manifest.json` | JSON | slot-oriented mapping for runtime bindings |
| `runtime_bundle_manifest.json` | JSON | hashes, lineage, versions |

### 15.2. Calibration artifacts

| Артефакт | Формат | Назначение |
|---|---|---|
| `firm_fundamentals_annual.parquet` | Parquet | annual firm targets |
| `household_synthetic_targets.parquet` | Parquet | household targets |
| `labor_force_micro_targets.parquet` | Parquet | labor-force structure targets |
| `observation_panel_monthly.parquet` | Parquet | unified monthly observations |
| `observation_panel_annual.parquet` | Parquet | unified annual observations |
| `measurement_registry.json` | JSON | trust tiers, coverage rules |
| `schema_regime_registry.json` | JSON | schema versions and regime boundaries |
| `regime_calendar.json` | JSON | macro regimes |
| `shock_calendar.json` | JSON | exogenous shocks |
| `changepoint_registry.json` | JSON | detected structural breaks and schema drifts |
| `calibration_splits.json` | JSON | train/val/test/holdouts |
| `negative_control_panel.parquet` | Parquet | placebo and falsification targets |
| `public_service_observation_panel_monthly.parquet` | Parquet | health / education / treasury / infrastructure observations |
| `jax_calibration_bundle_v1.npz` | NPZ | tensors, masks, targets |
| `calibration_dictionary.json` | JSON | ids and dictionaries |
| `calibration_leaderboard.json` | JSON | benchmark results |
| `identification_mode_registry.json` | JSON | per-family identification modes and proxy mappings |

### 15.3. Embedding artifacts

| Артефакт | Формат | Назначение |
|---|---|---|
| `agent_embedding_32d.npz` | NPZ | compact learned representation |
| `agent_embedding_dictionary.json` | JSON | id alignment |
| `cell_prototype_embeddings.npz` | NPZ | meso-cell prototypes |

### 15.4. Intervention artifacts

| Артефакт | Формат | Назначение |
|---|---|---|
| `lex_intervention_map.json` | JSON | provision -> intervention |
| `intervention_knob_dictionary.json` | JSON | knob definitions |
| `policy_scenario_templates.json` | JSON | reusable scenario specs |
| `temporal_intervention_sequences.json` | JSON | sequential policy change timelines for DTR |

### 15.5. Source -> Artifact -> Method Family -> Runtime Consumer Map

| Source family | Primary artifact | Main method family | Main runtime / governance consumer |
|---|---|---|---|
| Spending | `budget_flows_monthly_sparse.parquet` | network, policy, structural time series, **interference (NetworkCausalData)** | `Foundry` budget channel, `Scientist` observation panels |
| Prozorro | `procurement_contracts_monthly.parquet` | network, policy, validation, **interference, strategic response** | procurement channel, holdout/backtest, **SUTVA Check Pass** |
| DPS financials | `firm_fundamentals_annual.parquet` | firm initialization, annual calibration, **econometrics.panel, econometrics.factor** | strategic-agent and cell priors |
| labor service + labor microdata | `labor_market_panel_monthly.parquet`, `labor_force_micro_targets.parquet` | survey, microsim, forecasting, **econometrics.panel** | labor block and synthetic households |
| household microdata | `household_synthetic_targets.parquet` | distributional, welfare, microsim, **distributional.poverty, distributional.mobility** | welfare evaluation and household initialization |
| distress / enforcement | `distress_events_panel_monthly.parquet` | hazard, survival, sensitivity, **ml.survival, econometrics.selection** | distress fit, stress testing, **Heckman exit correction** |
| trade + customs | `trade_exposure_monthly.parquet`, `logistics_friction_monthly.parquet` | multiplex network, IO, state-space, **optimization.io_leontief** | trade and logistics channels |
| education registry | `education_entity_registry.parquet` | public-service domain modeling | education ontology and human-capital supply |
| construction registry | `construction_activity_panel_monthly.parquet` | investment / capital formation panels | capital formation and infrastructure demand |
| roads/accessibility | `road_accessibility_cell_panel.parquet` | spatial, kriging, cell latent fields | accessibility and cost-to-serve state |
| raster / exogenous open layers | `spatial_cell_exogenous_monthly.parquet` | spatial, structural time series | `region x sector` latent fields |
| Lex crosswalks | `lex_intervention_map.json` | scenario compiler, policy evaluation, **DTR, strategic response, bilevel optimization** | intervention knobs and replay governance |
| ЄДР (firm entry/exit) | `agent_registry_full.parquet` | **econometrics.selection (Heckman), ml.survival (hazard)** | firm lifecycle, **PopulationAwareExecutor** |

### 15.6. Multiplex graph artifacts

Нужно явно публиковать:

1. `budget_graph_sparse.npz`
2. `procurement_graph_sparse.npz`
3. `trade_graph_sparse.npz`
4. `distress_graph_sparse.npz`
5. `public_service_graph_sparse.npz`
6. `multiplex_graph_manifest.json`

Эти артефакты должны быть согласованы по `agent_id / cell_id / period_id`, чтобы их можно было использовать и в `JAX`, и в `Foundry network methods`, и в `Scientist` governance.

Каждый graph artifact компилируется в **два контрактных формата**:

1. `NetworkData` / `MultiplexNetworkData` — для network analysis;
2. `NetworkCausalData` — для interference-aware causal estimation.

### 15.7. Method-contract bundle family

Помимо runtime and calibration artifacts нужен ещё один explicit слой:

| Артефакт | Формат | Назначение |
|---|---|---|
| `calibration_target_bundle_v1.npz` | NPZ | aligned targets, masks, weights, trust arrays |
| `microsim_survey_contract_v1.json` | JSON | household/labor inputs in `SurveyMicroData`-compatible form |
| `network_contract_bundle_v1.json` | JSON | dense-on-demand slice metadata for `NetworkData` / `MultiplexNetworkData` |
| `network_causal_contract_bundle_v1.json` | JSON | interference-ready contracts for `NetworkCausalData` |
| `causal_panel_bundle_monthly.parquet` | Parquet | causal-ready monthly panels and regime annotations |
| `backtest_plan_bundle.json` | JSON | `HistoricalValidationPlan` inputs and holdout windows |
| `observation_to_contract_manifest.json` | JSON | lineage from observation family to method contract |
| `bounds_estimation_bundle_v1.json` | JSON | partially-identified channels with Manski/Balke-Pearl specs |
| `proxy_identification_bundle_v1.json` | JSON | proxy-identified channels with Kuroki-Pearl verification results |
| `dtr_treatment_sequence_bundle_v1.npz` | NPZ | `DynamicTreatmentData`-compatible temporal sequences |
| `panel_econometric_bundle_v1.parquet` | Parquet | firm/labor panel data for econometric estimation |
| `survival_data_bundle_v1.parquet` | Parquet | time-to-event data for hazard models (censored) |
| `specification_curve_input_v1.json` | JSON | source-combination specs for sensitivity analysis |
| `leontief_io_bundle_v1.json` | JSON | regional input-output tables for optimization |
| `strategic_response_specs_v1.json` | JSON | channels requiring `evaluate_strategic_hook()` |
| `governance_pass_mapping_v1.json` | JSON | per-family mandatory governance pass lists |
| `lesson_registry_seed_v1.json` | JSON | initial `LessonCard` entries for calibration learning |

Этот слой нужен, чтобы украинский bundle был нативным для существующего кода, а не просто "богатым набором parquet-ов".

---

## 16. Source Processing Strategy

### 16.1. ЄДР

Использовать:

1. current official dump;
2. normalized org/status/sector/region fields;
3. no historical deep recovery in v1;
4. **firm entry/exit events** → `ml.survival` (hazard targets) + `econometrics.selection` (Heckman correction);
5. `PopulationAwareExecutor` для firm birth/death lifecycle в runtime.

### 16.2. Spending.gov.ua

Использовать:

1. full clean horizon from `2015-09`;
2. monthly aggregation;
3. purpose classification;
4. sparse edge export;
5. **dual compilation**: `NetworkData` (network analysis) + `NetworkCausalData` (interference/spillover estimation);
6. **SUTVA Check Pass** обязателен — budget cascades нарушают no-interference assumption.

### 16.3. Prozorro

Использовать:

1. full clean horizon from `2016-04` / `2016-08`;
2. compact award/contract layer;
3. supplier/procurer panel;
4. no full co-bid graph in v1;
5. **dual compilation**: `NetworkData` + `NetworkCausalData`;
6. **strategic response check** через `evaluate_strategic_hook()` — procurement participants адаптируются к threshold changes;
7. **SUTVA Check Pass** обязателен;
8. **DTR-ready panels** для temporal procurement rule sequences.

### 16.4. НБУ + Держстат

Использовать:

1. macro state;
2. region x sector anchor panels;
3. household and labor calibration anchors;
4. **econometrics.panel** для structural panel estimation.

### 16.5. DPS tax layer

Использовать:

1. tax system;
2. tax debt;
3. risk flags;
4. compliance stress;
5. **tax debt как proxy distress** → `identify_with_proxy(proxy_map={"distress": "tax_debt"})` для formal measurement-error identification.

### 16.6. DPS financial statements

Использовать как annual firm-fundamental layer:

1. revenue
2. assets
3. liabilities
4. equity
5. profit/loss
6. retained earnings proxy
7. leverage and fragility classes

Это не просто enrichment, а отдельная state family для richer firm initialization.

Execution surfaces:

8. **econometrics.panel** — fixed/random effects estimation;
9. **econometrics.factor** — latent factor extraction для embeddings;
10. **econometrics.selection** — Heckman correction для firms, которые не подали отчётность (non-random missingness).

### 16.7. Customs export/import

Использовать для:

1. export/import intensity;
2. product diversity;
3. external exposure;
4. FX sensitivity proxy.

Trade exposure должно считаться отдельным state family, а не просто дополнительной фичей фирмы.

Execution surfaces:

5. **optimization.io_leontief** — regional input-output under trade disruption;
6. **Transportability Required Pass** — sanctions regime creates non-transportable trade patterns.

### 16.8. Customs commercial-vehicle and logistics signals

Использовать для:

1. border friction proxy;
2. country-specific logistics pressure;
3. import corridor intensity;
4. monthly transport disruption signals.

### 16.9. Employment service

Использовать для:

1. vacancy pressure;
2. wage offers;
3. labor tightness;
4. unemployment benefits;
5. **proxy identification**: administrative employment как proxy true employment → `identify_with_proxy()`.

### 16.10. Household microdata

Использовать как:

1. household distribution anchor;
2. consumption and welfare calibration layer;
3. **distributional.poverty** targets;
4. **distributional.mobility** targets;
5. **Equity Pass** input для governance.

### 16.11. Labor-force microdata

Использовать как:

1. participation structure anchor;
2. occupation heterogeneity anchor;
3. synthetic household labor block anchor;
4. **econometrics.panel** targets (if repeated cross-section treated as pseudo-panel).

### 16.12. Distress / judicial layers

Использовать как:

1. default hazard targets;
2. enforcement pressure targets;
3. exit-risk signals;
4. **ml.survival** — time-to-event hazard models с right-censoring;
5. **econometrics.selection** — Heckman correction для non-random exit;
6. **sensitivity.specification** — specification curves для robustness of distress fit.

Именно этот слой даёт самые прямые наблюдения риска поведения агентов во времени.

### 16.13. Public / treasury / NSZU layers

Использовать как:

1. public ontology layer;
2. domain-specific policy channels;
3. **NetworkCausalData** targets для public-service spillover analysis;
4. **DTR-ready panels** для temporal tariff change sequences.

Этот слой нужен не только для data enrichment, но и для typed interpretation public-side actors внутри бюджетного и procurement графов.

### 16.14. Education registries

Использовать для:

1. registry of schools, vocational institutions, colleges, universities;
2. public-service coverage;
3. regional human-capital supply proxies;
4. typed public-agent ontology for education sector.

### 16.15. Construction registries

Использовать для:

1. permits and commissioning flows;
2. construction activity and delays;
3. geography of capital formation;
4. infrastructure investment observables.

### 16.16. Roads and accessibility layers

Использовать для:

1. road-quality and road-density cell baselines;
2. accessibility proxies;
3. cost-to-serve adjustments;
4. transport resilience and disruption proxies.

### 16.17. Land cadastre

Использовать осторожно как:

1. land-use baseline;
2. agriculture and real-estate spatial typing;
3. cell-level land-intensity proxy.

Кадастр должен оставаться `validated` или `exploratory` source, а не unconditional backbone.

### 16.18. Spatial / raster / exogenous layers

Использовать для:

1. `region x sector` latent field construction;
2. accessibility and disruption proxies;
3. activity / luminosity / density anchors;
4. climate and seasonality adjustments;
5. coarse damage and resilience proxies.

На первом этапе эти слои должны оставаться calibration-first, а не runtime-heavy.

### 16.19. Distress / logistics / mobility investigation track

Отдельный research track нужен для:

1. border and trade corridor pressure;
2. relocation and displacement pressure;
3. transport disruption proxies;
4. mobility shocks;
5. firm-level logistics dependence classes.

Эти данные не должны тормозить `v1`, но архитектурно для них уже нужен place in the blueprint.

---

## 17. CPX62 Feasibility

### 17.1. Why plan is still feasible

Даже с расширением документа план остаётся feasible на `CPX62`, потому что:

1. вся тяжёлая работа batch-only;
2. runtime использует compact artifacts;
3. ordinary agents сжимаются в cells;
4. strategic micro-agents ограничены по количеству;
5. embeddings и static/slow/fast split снижают размер state;
6. **новые каузальные, econometric и governance capabilities не добавляют runtime cost** — они symbolic/batch и работают offline.

Но это верно только если:

1. `cell`-слой становится first-class runtime object;
2. multiplex graphs публикуются в compressed form;
3. most observables остаются в calibration bundle, а не в runtime;
4. dense network contracts строятся только для selected slices, а не для полного мира;
5. **identification checks, governance passes и strategic response solving** работают offline в batch.

### 17.2. Memory rules

Нужно придерживаться правил:

1. no dense adjacency;
2. no full microstate for all firms;
3. no raw text in runtime;
4. no exact coordinates in runtime unless required;
5. use integer ids and dictionary encoding everywhere;
6. no default dense `MultiplexNetworkData` for country-scale graphs;
7. **symbolic causal identification, Heckman correction, bounds computation, transportability checks — все batch-only**.

### 17.3. Storage budget

```text
Transient raw landing:        160-280 GB
Normalized parquet layers:     60-120 GB
Runtime artifacts:             10-25 GB
Calibration artifacts:          8-20 GB
Method-contract bundles:        2-5 GB
DuckDB work db + manifests:    15-35 GB
Safety reserve:               150+ GB
```

---

## 18. Calibration Governance and Backtesting

### 18.1. Governance must be first-class

Хорошая симуляция не та, что красиво инициализирована, а та, что выдерживает:

1. holdouts;
2. regime changes;
3. stress tests;
4. replay;
5. **adversarial challenges**;
6. **formal transportability checks**;
7. **SUTVA violation detection**.

### 18.2. Required governance components

Нужно включить:

1. `holdout_2025` или `last_12_months`;
2. regime-specific backtests;
3. stress scenarios;
4. calibration leaderboard;
5. replayable calibration manifests;
6. **governance pass coverage per observation family**;
7. **adversarial testing suite coverage**;
8. **lesson registry with cross-run learning**.

### 18.3. Backtest matrix

Минимум:

1. macro backtest
2. cell-level backtest
3. strategic-agent backtest
4. household-distribution backtest
5. distress-hazard backtest

### 18.4. Stress scenarios

Минимум:

1. budget contraction
2. procurement rule shock
3. wage subsidy policy
4. FX shock
5. trade disruption
6. reimbursement tariff shock

### 18.5. Replay artifacts

Каждая calibration run должна публиковать:

- `calibration_run_manifest.json`
- `loss_breakdown.json`
- `holdout_scores.json`
- `shock_scenario_scores.json`

### 18.6. Negative controls and placebo targets

Calibration governance должна включать не только fit-to-target, но и falsification:

1. placebo targets по каналам, где эффект не должен появляться;
2. negative controls для household and firm outcomes;
3. impossible-transition guards;
4. non-transportable regime warnings.

Это особенно важно для Украины, где часть apparent effects может быть артефактом coverage or regime shifts.

### 18.7. Explicit model families to support

Blueprint должен прямо фиксировать, что observation and calibration stack поддерживает:

1. hierarchical partial pooling по `region x sector x firm_type`;
2. regime-switching and state-space models;
3. survival / hazard models для exit, distress, employment transitions, procurement wins;
4. low-rank factorization для sparse budget and procurement graphs;
5. graph embeddings и compressed priors для `JAX`;
6. optimal transport / IPF / raking для synthetic households;
7. change-point detection и schema-regime versioning;
8. measurement-aware losses с `trust_weight` и `coverage_estimate`.

И отдельно — что эти model families уже имеют естественные execution surfaces в текущем коде:

1. `distributional / welfare / mobility`
2. `microsim / tax-benefit / behavioral response`
3. `multiplex network / diffusion / input-output networks`
4. `Leontief / robust / stochastic optimization`
5. `policy ex-ante / budget impact / scorecard`
6. `stock-flow / system dynamics`
7. `sensitivity / specification curve`
8. `structural time series`
9. `Scientist` trust-aware historical validation

Плюс ранее не задействованные:

10. `econometrics.panel` — fixed/random effects, GMM, dynamic panels;
11. `econometrics.selection` — Heckman correction для non-random exit;
12. `econometrics.iv` — instrumental variable estimation;
13. `econometrics.factor` — latent factor extraction;
14. `ml.survival` — hazard models для time-to-event targets;
15. `optimization.bilevel` — government-firm bilevel problems;
16. `optimization.game_theory` — Nash equilibria в procurement;
17. `optimization.chance_constrained` — budget allocation under uncertainty;
18. `sensitivity.sobol` — Sobol indices для calibration robustness;
19. `sensitivity.specification` — specification curves для source-combination robustness;
20. `causal.interference (NetworkCausalData)` — spillover estimation;
21. `causal.bounds` — partial identification under censoring;
22. `causal.measurement_error` — Kuroki-Pearl proxy identification;
23. `causal.dtr` — dynamic treatment regimes;
24. `causal.strategic` — performative equilibria.

### 18.8. Why this matters for CPX62

Эти методы нужны не ради sophistication itself, а потому что они:

1. уменьшают размер runtime state;
2. повышают identifiability на шумных украинских open data;
3. позволяют не хранить full micro-history в памяти;
4. дают better priors and compression for `JAX`;
5. **формально обосновывают, когда estimation возможна, а когда нужны bounds** — это снижает false confidence;
6. **дают explicit governance gates** вместо ad-hoc validation.

### 18.9. Code-grounded governance path

Текущий `Scientist` код уже умеет:

1. запускать historical backtests с explicit degraded modes;
2. различать `provided`, `scientist` и `naive` prediction sources;
3. публиковать replay verification artifacts;
4. собирать policy-design workflow, где simulation, causal evaluation и governance уже встречаются в одном graph.

1. calibration runs должны сразу публиковать backtest-ready and replay-ready bundles;
2. blueprint должен считать backtesting and replay частью normal build output, а не optional later add-on.

### 18.10. Explicit governance pass mapping

Для каждой observation family и каждого calibration run нужно explicit mapping к governance passes.

#### Mandatory passes per family

| Observation family | Mandatory passes |
|---|---|
| budget flows | SUTVA Check, Freshness, Equity, Cross-Graph Evidence |
| procurement flows | SUTVA Check, Transportability Required, Confidence, Strategic Gaming adversarial |
| macro state | Confidence, Freshness |
| firm fundamentals | Refutation, Freshness, Cross-Graph Evidence |
| trade exposure | Transportability Required, Confidence |
| labor market | Equity, SUTVA Check, Confidence |
| household distribution | Equity, Confidence, Refutation, Privacy |
| distress / enforcement | Refutation, Confidence |
| spatial / raster exogenous | Freshness |
| public service domain flows | SUTVA Check, Equity |
| education | Freshness |
| construction / capital formation | Freshness |
| logistics friction | Transportability Required |

#### Global passes (all calibration runs)

1. **Confidence Pass** — uncertainty envelope must cover holdout;
2. **Budget Pass** — computation stays within CPX62 limits;
3. **Freshness Pass** — data recency check;
4. **Checkpoint Pass** — milestone validation.

### 18.11. Adversarial testing suites

Calibration governance должна включать adversarial testing через уже существующие suites в `backtesting/adversarial.py`:

1. **STRATEGIC_GAMING** — проверяет, что модель устойчива к strategic agent adaptation (procurement participants, tax optimization);
2. **MULTIPLICITY_DISCLOSURE** — проверяет, что calibration result stable across model specification choices;
3. **ABSTRACTION_LEAKAGE** — проверяет, что cell-level abstraction не маскирует micro-level dynamics.

Для украинского bundle adversarial testing особенно критично:

1. procurement agents **точно** gaming the system — STRATEGIC_GAMING обязателен;
2. wartime regime shifts дают specification multiplicity — MULTIPLICITY_DISCLOSURE обязателен;
3. cell aggregation скрывает individual firm distress — ABSTRACTION_LEAKAGE обязателен.

### 18.12. Lesson registry и cross-run learning

Каждый calibration run должен публиковать `LessonCard` в `LessonRegistry`:

1. `LessonKind.FAILURE` — если holdout score ниже threshold, конкретно: что не сработало, какой source/channel, какие hyperparameters;
2. `LessonKind.SUCCESS` — если подход validated, конкретно: что сработало, при каких conditions;
3. `LessonTrustLevel.LOCAL` для first-time results, `TRANSFERRED` при reuse из другого regime/domain.

Это даёт:

1. cumulative learning across calibration iterations;
2. transfer-aware weighting для cross-regime reuse;
3. explicit failure memory — следующий run не повторяет ошибки.

### 18.13. Active disambiguation для data collection priorities

`ActiveDisambiguationPlanner` в `discovery/active.py` может генерировать **target data collection priorities** на основе текущей graph ambiguity:

1. какие edges в causal graph ambiguous (PAG с CIRCLE marks);
2. какие дополнительные данные disambiguate эти edges;
3. ranked list of most-valuable-to-collect data по utility для policy questions.

Для украинского bundle это мощный инструмент:

1. вместо passive "собрали что есть" → active "вот что нужно собрать в следующей итерации";
2. priority P2/P3 sources можно ранжировать по disambiguation utility, а не только по a priori assessment;
3. active disambiguation может показать, что дешёвый P1 source disambiguates critical edge, который дорогой P2 source не disambiguates.

### 18.14. Required code additions to make the blueprint real

Минимальный список обязательных изменений в коде:

1. добавить `SlotScope.PER_CELL`;
2. завести `CellState` и cell-aware `GlobalState` extension;
3. расширить `Foundry` input bindings и size inference beyond `n_agents / n_firms`;
4. добавить observation-to-contract compiler layer;
5. добавить measurement-aware loss adapter поверх текущего calibration loss;
6. добавить sparse / low-rank bridge into `NetworkData` and `MultiplexNetworkData`;
7. формализовать typed multiplex layer ids для `budget / procurement / trade / distress / public_service`;
8. добавить `Lex` intervention compiler into `simulation` and `causal` surfaces;
9. добавить **identification-mode router** per observation family;
10. добавить **governance pass mapping registry** per observation family;
11. добавить **interference-aware loss component** для graph-level targets;
12. добавить **temporal intervention sequence compiler** для DTR surfaces;
13. добавить **NetworkCausalData compilation** из multiplex graph artifacts;
14. добавить **strategic response spec registry** для channels requiring `evaluate_strategic_hook()`.

---

## 19. Delivery Plan

Delivery plan разделён на две части:

1. **Part A (Code)** — фазы C0–C7: весь код пишется, тестируется и интегрируется **локально** на dev-машине с synthetic / fixture data. Никаких production downloads, никаких тяжёлых datasets. Каждая фаза завершается passing test suite.
2. **Part B (Data)** — фазы D0–D5: production-quality data ingestion, обработка и калибровка запускаются **на сервере** (`CPX62`). К этому моменту весь код уже протестирован и интегрирован.

Граница между Part A и Part B жёсткая: **Part B не начинается, пока Part A не прошла полный integration test на synthetic data.**

---

### Part A — Code (local dev, synthetic data)

After C0, work splits into **four parallel waves**. Items within one wave can be developed simultaneously because they don't depend on each other — only on outputs of previous waves.

```text
C0  Architecture Freeze (sequential — everything depends on this)
 │
 ├─── Wave 1 (all parallel after C0) ──────────────────────────────────────────
 │     │                │                 │                    │
 │    C1               C2               C5a                  C6a
 │  Foundry State    Observation      Governance           Lex Intervention
 │  & Bindings       Plane &          Wiring               Compiler &
 │                   Measurement      (pass registry,      Temporal
 │                   Model            lesson card,         Sequencer
 │                                    adversarial,
 │                                    active disambig)
 │     │                │                 │                    │
 ├─── Wave 2 (after C1 + C2 complete) ────────────────────────────────────────
 │     │                       │                    │
 │    C3                     C4a                  C6b
 │  Observation-to-         Causal &             Agent Sim
 │  Contract Compilers      Identification       Executors
 │  (all 13)               (proxy ID,            (population,
 │                          transportability,     graph-aware,
 │                          interference loss,    distribution)
 │                          counterfactual)
 │     │                       │                    │
 ├─── Wave 3 (after C3 + C4a) ────────────────────────────────────────────────
 │     │                       │                    │
 │    C4b                    C5b                  C6c
 │  Bounds Estimation       Backtest Matrix,     Strategic Response
 │  Runner                  Stress Scenarios,    Hook, Counterfactual
 │  (needs C3 compiler)     Leaderboard          Gate, Policy Search
 │                          (needs calibration    (needs C4a runner)
 │                           infra from C2)
 │     │                       │                    │
 ├─── Wave 4 (after all waves) ────────────────────────────────────────────────
 │
 │    C7  Embeddings, Advanced Methods, Full Integration Test
 │
```

---

#### C0 — Architecture Freeze and Contract Design

**Sequential prerequisite для всего остального.**

Цель: утвердить все контракты и схемы до написания первой строки кода.

Артефакты:

1. finalized observation schema (Section 8.3) — `ObservationRecord` dataclass;
2. finalized `CellState` contract;
3. `SlotScope.PER_CELL` enum value;
4. `GlobalState` extension с cell + household blocks;
5. identification-mode enum: `POINT_IDENTIFIED`, `PARTIALLY_IDENTIFIED`, `BOUNDS_ONLY`, `PROXY_IDENTIFIED`, `INTERFERENCE_AWARE`, `SEQUENTIAL`;
6. governance pass mapping schema: observation_family → list of mandatory passes;
7. intervention contract schema (Section 13.3) с `identification_mode` и `strategic_response_expected`;
8. temporal intervention sequence schema для DTR;
9. method-contract bundle schemas (Section 15.7) — JSON schemas for each bundle type;
10. strategic response channel list;
11. multiplex graph layer id conventions (`budget / procurement / trade / distress / public_service`);
12. source confidence tier definitions (`core / validated / exploratory`);
13. measurement-aware loss adapter interface spec.

Тесты:

- schema validation tests для всех dataclasses;
- contract compatibility tests (new contracts vs existing Foundry/Scientist interfaces);
- `pytest` pass.

---

#### Wave 1 — четыре параллельных трека сразу после C0

##### C1 — Foundry State and Binding Extensions

**Зависит от:** C0 (CellState contract, SlotScope enum).
**Не зависит от:** C2, C5a, C6a.

Цель: расширить Foundry runtime contracts для multiscale world.

Код:

1. `SlotScope.PER_CELL` в `ir/kernel/slots.py`;
2. `CellState` frozen JAX dataclass в `foundry/contracts/state.py`;
3. `HouseholdCellState` frozen JAX dataclass;
4. `GlobalState` extension: `cells: CellState`, `household_cells: HouseholdCellState`;
5. `data_plane/bindings.py`: cell-aware `_infer_entity_sizes()` — infer `n_cells`, `n_household_cells` from data;
6. `data_plane/bindings.py`: cell-aware `_auto_rules_from_payload()` — discover cell-level bindings;
7. slot family manifest writer — `slot_family_manifest.json` generator.

Тесты (всё на synthetic fixtures):

- unit: `CellState` creation, serialization, JAX compatibility;
- unit: `GlobalState` с cells + households — scan step doesn't crash;
- unit: `_infer_entity_sizes()` correctly infers `n_cells` from synthetic payload;
- unit: `_auto_rules_from_payload()` discovers cell-level slots;
- integration: `build_input_bindings()` end-to-end с synthetic cell data → valid `GlobalState`.

##### C2 — Observation Plane and Measurement Model

**Зависит от:** C0 (ObservationRecord schema, identification-mode enum, loss interface spec).
**Не зависит от:** C1, C5a, C6a.

Цель: построить observation plane infrastructure — schema, compilers, measurement-aware loss.

Код:

1. `ObservationRecord` Pydantic model + `ObservationPanel` container;
2. `MeasurementRegistry` — trust tiers, coverage rules, proxy mappings;
3. `IdentificationModeRouter` — dispatches observation family → identification strategy;
4. `SchemaRegimeRegistry` — schema versions, regime boundaries, changepoint tracking;
5. observation-to-calibration-target compiler: `ObservationPanel → CalibrationTargetBundle` (aligned arrays + masks + weights + trust);
6. measurement-aware loss adapter over `calibration/loss.py`: `trust_weight`, `coverage_estimate`, `censoring_mask`, `schema_regime_id`-aware downweighting;
7. `RegimeCalendar` и `ShockCalendar` models;
8. `CalibrationSplitter` — train/val/test/holdout split logic;
9. `NegativeControlGenerator` — placebo target construction.

Тесты (synthetic panels):

- unit: `ObservationRecord` validation, edge cases (nulls, extreme trust);
- unit: `IdentificationModeRouter` correctly routes families;
- unit: measurement-aware loss с synthetic targets — coverage=0 → zero weight, censoring_mask → downweight;
- unit: `CalibrationSplitter` — correct regime-aware splits;
- unit: `NegativeControlGenerator` — placebo targets non-overlapping with real;
- integration: synthetic observation panel → compiler → calibration target bundle → loss computation → gradient exists.

##### C5a — Governance Wiring (early part of C5)

**Зависит от:** C0 (governance pass mapping schema, observation family enum).
**Не зависит от:** C1, C2, C6a.

Цель: wiring governance и lesson infrastructure, которое зависит только от схем, а не от observation data.

Код:

1. `GovernancePassMappingRegistry` — observation_family → mandatory passes (Section 18.10 table);
2. `CalibrationGovernanceRunner` — orchestrates pass execution per family per calibration run;
3. adversarial suite integration: `STRATEGIC_GAMING`, `MULTIPLICITY_DISCLOSURE`, `ABSTRACTION_LEAKAGE` wired into calibration quality gate;
4. `LessonCardPublisher` — каждый calibration run → `LessonCard` (FAILURE/SUCCESS) в `LessonRegistry`;
5. `ActiveDisambiguationIntegration` — `ActiveDisambiguationPlanner` → ranked data collection priorities from PAG ambiguity.

Тесты (synthetic, без калибровки):

- unit: `GovernancePassMappingRegistry` — correct passes per family, no missing families;
- unit: `CalibrationGovernanceRunner` — short-circuits on blocker, cost-aware ordering;
- unit: adversarial suite — `STRATEGIC_GAMING` detects gaming in synthetic scenario;
- unit: `LessonCardPublisher` — writes valid `LessonCard`, registry lookup works;
- unit: `ActiveDisambiguationIntegration` — returns ranked target list from synthetic PAG.

##### C6a — Lex Intervention Compiler (early part of C6)

**Зависит от:** C0 (intervention contract schema, DTR schema, strategic response channel list).
**Не зависит от:** C1, C2, C5a.

Цель: intervention model infrastructure, которое зависит только от Lex и schema contracts.

Код:

1. `LexInterventionCompiler` — Lex provision → intervention knob → simulation parameter;
2. `TemporalInterventionSequencer` — Lex temporal sequences → DTR-ready treatment sequences;
3. `StrategicResponseSpec` registry — channels + expected response type + hook config;
4. `HierarchicalPolicySearchAdapter` — Ukrainian bundle inputs → `policy_design/search.py` (STRUCTURE → PARAMETER → NARRATIVE) — config layer, не wiring к simulation.

Тесты:

- unit: `LexInterventionCompiler` — provision ref → knob → valid simulation parameter;
- unit: `TemporalInterventionSequencer` — sequence of 3 interventions → valid `DynamicTreatmentData`;
- unit: `StrategicResponseSpec` registry — correct channel lookup;
- unit: `HierarchicalPolicySearchAdapter` — config validates against policy_design API.

---

#### Wave 2 — три параллельных трека после Wave 1

Стартует, когда **C1 и C2 оба завершены**. C5a и C6a не блокируют Wave 2.

##### C3 — Observation-to-Contract Compilers

**Зависит от:** C2 (`ObservationPanel` as input), C1 (entity id conventions from state contracts для graph compilers).
**Не зависит от:** C4a, C5a, C5b, C6a, C6b.

Цель: компиляторы из observation plane в typed method contracts.

Код:

1. `ObservationPanel → SurveyMicroData` compiler (household/labor families);
2. `GraphArtifacts → NetworkData / MultiplexNetworkData` compiler (sparse → dense-on-demand);
3. `GraphArtifacts → NetworkCausalData` compiler (interference-ready contracts);
4. `ObservationPanel → PanelObservationalData` compiler (causal-ready panels с regime annotations);
5. `ObservationPanel → DynamicTreatmentData` compiler (temporal intervention sequences);
6. `FirmEvents → SurvivalData` compiler (time-to-event с right-censoring);
7. `FirmPanels → PanelEconometricData` compiler (for panel econometrics);
8. `ObservationPanel → BoundsEstimationInput` compiler (partially-identified channels);
9. `ObservationPanel + ProxyMap → ProxyIdentificationInput` compiler (Kuroki-Pearl ready);
10. `ObservationPanel → HistoricalValidationPlan` compiler (backtest-plan bundles);
11. `ObservationPanel → SpecificationCurveInput` compiler (source-combination specs);
12. `RegionSectorPanels → LeontiefIOInput` compiler (input-output tables);
13. sparse-to-dense / low-rank bridge для `NetworkData` and `MultiplexNetworkData`.

Тесты (synthetic data):

- unit: каждый compiler — valid input → valid output contract, round-trip consistency;
- unit: `NetworkCausalData` compiler — adjacency_matrix, cluster_id shapes correct;
- unit: `SurvivalData` compiler — censoring flags correct;
- unit: sparse→dense bridge — materialization для small subgraph, OOM guard для large;
- integration: synthetic observation panel → all 13 compilers → valid method contracts → method `.pure_step()` accepts them.

##### C4a — Causal and Identification Infrastructure (main part)

**Зависит от:** C2 (observation families, regime info, loss adapter для interference component).
**Не зависит от:** C3, C5a, C5b, C6a, C6b.

Цель: wiring между observation plane и каузальным стеком — всё, что не требует C3 compiler outputs.

Код:

1. `ProxyIdentificationRunner` — batch `identify_with_proxy()` для all proxy-identified families, stores `ProxyAdjustmentNode` AST or `ORACLE_NEEDED` per family;
2. `TransportabilityChecker` — formal `tr_algorithm` check при cross-regime estimation;
3. `InterferenceLossComponent` — graph-level loss term для procurement/budget spillover;
4. `StrategicResponseRunner` — batch `evaluate_strategic_hook()` для channels with `strategic_response_expected=True`;
5. `CounterfactualQueryRunner` — `id_star_algorithm` check для major policy counterfactuals.

Тесты (synthetic graphs and panels):

- unit: `ProxyIdentificationRunner` — valid proxy → IDENTIFIED, invalid proxy → ORACLE_NEEDED;
- unit: `TransportabilityChecker` — same regime → pass, cross-regime with S-node → transportable or blocked;
- unit: `InterferenceLossComponent` — gradient flows through graph structure;
- unit: `StrategicResponseRunner` — returns `StrategicSolveResult` with `performative_shift`;
- unit: `CounterfactualQueryRunner` — Layer-3 query identified or not.

##### C6b — Agent Sim Executor Wiring

**Зависит от:** C1 (`CellState`, `GlobalState` для executor dispatch).
**Не зависит от:** C2, C3, C4a, C5a.

Цель: wiring существующих agent_sim executors к новым cell и household state contracts.

Код:

1. `PopulationAwareExecutor` wiring для household lifecycle (births, aging, migration) с `CellState`-aware dispatch;
2. `PopulationAwareExecutor` wiring для firm lifecycle (entry, exit, type transitions) из ЄДР events;
3. `GraphAwareExecutor` wiring для procurement supply chain diffusion через multiplex graph;
4. `DistributionAwareExecutor` wiring для household welfare tracking (Gini, Palma, quantiles);
5. `TargetedTransferMechanism` / `DistributionAwareTaxMechanism` parameterization от intervention knobs.

Тесты (synthetic agents, cells):

- unit: `PopulationAwareExecutor` — synthetic firm births/deaths update `CellState.firm_count`;
- unit: `GraphAwareExecutor` — procurement shock propagates через synthetic supply chain;
- unit: `DistributionAwareExecutor` — Gini/Palma update after synthetic transfer;
- unit: mechanisms — knob parameterization → correct transfer/tax amounts.

---

#### Wave 3 — три параллельных трека после Wave 2

Стартует, когда **C3 и C4a оба завершены**.

##### C4b — Bounds Estimation and Remaining Causal Runners

**Зависит от:** C3 (compiler 8: `BoundsEstimationInput`), C4a (identification infrastructure).
**Не зависит от:** C5b, C6c.

Цель: final causal runners, которые зависят от typed contract bundles из C3.

Код:

1. `BoundsEstimationRunner` — batch partial identification для censored channels через bounds engine (needs `BoundsEstimationInput` from C3);
2. `TemporalInterventionSequenceCompiler` — end-to-end Lex temporal sequences → `DynamicTreatmentData` → DTR estimation (needs `DynamicTreatmentData` from C3).

Тесты:

- unit: `BoundsEstimationRunner` — returns valid bounds interval, width reflects censoring degree;
- unit: `TemporalInterventionSequenceCompiler` — 3-step intervention → valid DTR result;
- integration: synthetic censored observation panel → C3 compiler → bounds runner → interval output.

##### C5b — Backtest Matrix, Stress Scenarios, Leaderboard

**Зависит от:** C2 (measurement-aware loss, calibration infrastructure), C5a (governance runner, lesson card).
**Не зависит от:** C3, C4b, C6c.

Цель: calibration-aware governance infrastructure, которое зависит от observation plane.

Код:

1. `CalibrationLeaderboard` — extended с specification-curve robustness, transportability score, interference fit, strategic response plausibility;
2. `BacktestMatrixRunner` — orchestrates 5 backtest types (macro, cell, strategic-agent, household, distress);
3. `StressScenarioRunner` — orchestrates 6 stress scenarios (budget contraction, procurement shock, wage subsidy, FX, trade disruption, reimbursement tariff).

Тесты:

- unit: `CalibrationLeaderboard` — all metric slots populated from synthetic results;
- unit: `BacktestMatrixRunner` — runs 5 backtests, each produces valid score;
- unit: `StressScenarioRunner` — runs 6 scenarios, each produces valid comparison;
- integration: synthetic calibration run → C5a governance passes → adversarial → backtest → stress → leaderboard entry → lesson card.

##### C6c — Strategic Response Hook, Counterfactual Gate, Policy Search Wiring

**Зависит от:** C4a (`StrategicResponseRunner`, `CounterfactualQueryRunner`), C6a (intervention compiler), C6b (executor wiring).
**Не зависит от:** C3, C4b, C5b.

Цель: final intervention-to-simulation wiring, которое зависит от causal и executor infrastructure.

Код:

1. `StrategicResponseHook` wiring — `evaluate_strategic_hook()` в policy simulation node;
2. `CounterfactualIdentificationGate` — formal `id_star` check перед simulation-based policy evaluation;
3. `HierarchicalPolicySearchAdapter` completion — full wiring Ukrainian bundle inputs → simulation → evaluation → policy_design search;
4. end-to-end intervention pipeline: Lex provision → compiler → knob → simulation step → population update → welfare tracking → strategic check → governance.

Тесты:

- unit: `StrategicResponseHook` — hook returns `StrategicSolveResult` для synthetic procurement channel;
- unit: `CounterfactualIdentificationGate` — blocks simulation when query not identified, passes when identified;
- integration: synthetic Lex provisions → intervention compiler → simulation step → population update → welfare tracking → strategic response → governance check.

---

#### Wave 4 — integration (after all waves)

##### C7 — Embeddings, Advanced Methods and Full Integration Test

**Зависит от:** C1 + C2 + C3 + C4a + C4b + C5a + C5b + C6a + C6b + C6c (всё).

Цель: advanced method integrations + end-to-end integration test на synthetic data.

Код:

1. `FactorModelEmbeddingBuilder` — `econometrics.factor` → agent embeddings;
2. `CellPrototypeBuilder` — clustering → cell prototype embeddings;
3. `BilevelOptimizationAdapter` — intervention knobs → bilevel problem spec → `optimization.bilevel`;
4. `HeckmanCorrectionAdapter` — firm exit events → `econometrics.selection` → corrected panels;
5. `SurvivalModelAdapter` — distress events → `ml.survival` → hazard estimates;
6. `SobolDiagnosticsAdapter` — calibration targets × source combinations → `sensitivity.sobol`;
7. `SpecificationCurveAdapter` — calibration fit × model specs → `sensitivity.specification`.

End-to-end integration test (**synthetic data, полный pipeline**):

```text
synthetic sources (5 fake parquet files, ~1000 agents, ~50 cells)
  → Fabric DataSnapshot
  → observation plane (ObservationPanel, MeasurementRegistry)
  → identification-mode routing
  → observation-to-contract compilers (all 13)
  → Foundry input bindings (CellState, HouseholdCellState, GlobalState)
  → JAX calibration (measurement-aware loss, 10 steps)
  → causal pipeline (proxy identification, bounds, transportability)
  → strategic response check
  → agent sim step (population, graph diffusion, distribution tracking)
  → governance passes (all mandatory per family)
  → adversarial suites (all 3)
  → backtest matrix (all 5 types)
  → leaderboard update
  → lesson card publication
  → replay artifacts
```

Тесты:

- integration: full pipeline end-to-end на synthetic data — no crashes, valid output at every stage;
- contract: every method-contract bundle accepted by its target method;
- regression: runtime artifact bundle size within budget on synthetic data;
- smoke: `foundry_seed_state_v1.npz` export and re-import roundtrip.

---

#### Parallel execution summary

| Wave | Tracks | Calendar weeks (estimate) | What can run in parallel |
|---|---|---|---|
| C0 | 1 | 1 | — (sequential) |
| Wave 1 | 4 | 2–3 | C1, C2, C5a, C6a — all independent |
| Wave 2 | 3 | 2–3 | C3, C4a, C6b — all independent (need Wave 1) |
| Wave 3 | 3 | 1–2 | C4b, C5b, C6c — all independent (need Wave 2) |
| Wave 4 | 1 | 1–2 | C7 — integration (needs everything) |
| **Total** | | **7–11 weeks** | vs 14–18 weeks sequential |

Параллелизм сокращает critical path примерно вдвое.

#### Критерий завершения Part A

1. все unit tests pass;
2. full integration test pass на synthetic data;
3. каждый compiler выпускает valid method contract;
4. governance passes execute без errors;
5. adversarial suites run и produce reports;
6. leaderboard и lesson registry populated;
7. `foundry_seed_state_v1.npz` export/import roundtrip succeeds;
8. no production data touched.

---

### Part B — Data (server production, CPX62)

**Part B начинается только после полного прохождения Part A integration test.**

#### D0 — Server Setup and P0 Core Data Ingestion

Цель: поднять production environment и загрузить backbone данные.

Инфраструктура:

1. CPX62 provisioning, SSH, firewall;
2. DuckDB work database setup;
3. Python environment + PolicyOS install;
4. storage layout: `raw/`, `normalized/`, `runtime/`, `calibration/`, `bundles/`, `manifests/`;
5. monitoring: disk space, RAM, build time tracking.

P0 Data ingestion:

1. ЄДР current dump → normalized `agent_registry_full.parquet`;
2. Spending.gov.ua full horizon (2015-09 → now) → `budget_flows_monthly_sparse.parquet`;
3. Prozorro full horizon (2016-04 → now) → `procurement_contracts_monthly.parquet`;
4. НБУ + Держстат macro panels → `macro_panel_monthly.parquet`;
5. DPS financial statements → `firm_fundamentals_annual.parquet`.

Первичные артефакты:

6. `agent_registry_runtime.parquet` — runtime cohort selection;
7. `public_entity_registry.parquet` — typed public ontology;
8. `cell_registry_region_sector.parquet` — meso-cell definitions;
9. `cell_state_seed_v1.npz` — initial cell state from P0 data;
10. `budget_graph_sparse.npz`, `procurement_graph_sparse.npz` — sparse graph exports;
11. `geo_index_runtime.parquet` — coarse geo;
12. `slot_family_manifest.json`, `runtime_bundle_manifest.json`.

Валидация:

- runtime cohort coverage of Spending/Prozorro participants `>95%`;
- cell count и agent count в ожидаемых диапазонах;
- graph artifacts consistent по `agent_id / cell_id / period_id`;
- `build_input_bindings()` на real data → valid `GlobalState`;
- P0 build time < 4 часа, peak RAM < 24 GB.

#### D1 — P1 Enrichment Ingestion

Цель: добавить simulation-critical enrichments.

Data ingestion:

1. DPS tax/risk layer → compliance + distress signals;
2. customs export/import → `trade_exposure_monthly.parquet`;
3. customs commercial vehicles → `logistics_friction_monthly.parquet`;
4. employment service → `labor_market_panel_monthly.parquet`;
5. license registry → regulated activity flags;
6. budget managers/recipients registry → public ontology enrichment;
7. NSZU payments → `public_service_observation_panel_monthly.parquet` (health);
8. ЄДЕБО / education → `education_entity_registry.parquet`;
9. ЄДЕССБ / construction → `construction_activity_panel_monthly.parquet`;
10. road characteristics → `road_accessibility_cell_panel.parquet`;
11. OSM exact → geo enrichment;
12. raster/exogenous layers (VIIRS, WorldPop, ERA5 baseline) → `spatial_cell_exogenous_monthly.parquet`.

Derived артефакты:

13. `trade_graph_sparse.npz`, `distress_graph_sparse.npz`, `public_service_graph_sparse.npz`;
14. dual compilation: `NetworkData` + `NetworkCausalData` для всех graph layers;
15. `multiplex_graph_manifest.json`;
16. proxy identification checks: tax debt → distress, procurement revenue → cashflow, administrative employment → true employment → `proxy_identification_bundle_v1.json`.

Валидация:

- all P1 source connectors produce valid normalized parquet;
- dual graph compilation produces consistent `NetworkData` + `NetworkCausalData`;
- proxy identification checks: at least 3 channels pass Kuroki-Pearl verification;
- P1 build time < 8 часов incremental, peak RAM < 28 GB.

#### D2 — Calibration Plane Build

Цель: построить observation plane, measurement model и calibration bundles из real data.

Артефакты:

1. `observation_panel_monthly.parquet` — unified monthly observations (all 13 families);
2. `observation_panel_annual.parquet` — unified annual observations;
3. `measurement_registry.json` — trust tiers и coverage rules из real source analysis;
4. `schema_regime_registry.json` — detected schema versions и regime boundaries;
5. `identification_mode_registry.json` — per-family identification modes;
6. `regime_calendar.json` — Regime A/B/C boundaries;
7. `shock_calendar.json` — minimum 5 shocks;
8. `changepoint_registry.json` — detected structural breaks;
9. `calibration_splits.json` — train_pre_2024, validation_2024, test_2025;
10. `negative_control_panel.parquet` — placebo targets;
11. `jax_calibration_bundle_v1.npz` — tensors, masks, targets, trust arrays;
12. `calibration_dictionary.json`.

Method-contract bundles (compiled from real data):

13. `calibration_target_bundle_v1.npz`;
14. `network_contract_bundle_v1.json` + `network_causal_contract_bundle_v1.json`;
15. `bounds_estimation_bundle_v1.json` — partially-identified channels;
16. `causal_panel_bundle_monthly.parquet`;
17. `panel_econometric_bundle_v1.parquet`;
18. `survival_data_bundle_v1.parquet`;
19. `dtr_treatment_sequence_bundle_v1.npz`;
20. `specification_curve_input_v1.json`;
21. `leontief_io_bundle_v1.json`;
22. `backtest_plan_bundle.json`;
23. `observation_to_contract_manifest.json`;
24. `governance_pass_mapping_v1.json`;
25. `strategic_response_specs_v1.json`.

Валидация:

- all 13 observation families present с `>=95%` measurement-aware observations;
- all 13 observation-to-contract compilers produce valid bundles;
- every bundle accepted by its target method (contract compatibility);
- identification-mode routing: all families have explicit assignment;
- governance pass mapping: all families have explicit pass list;
- calibration splits: non-overlapping, regime-aware;
- negative controls: `>=1 per major channel`.

#### D3 — P2 Calibration Enrichments

Цель: добавить calibration-critical household, labor и distress данные.

Data ingestion:

1. household microdata (Укрстат, 2018) → `household_synthetic_targets.parquet`;
2. labor-force microdata (Укрстат, 2018–2021) → `labor_force_micro_targets.parquet`;
3. ПФУ debt → arrears panel;
4. wage arrears datasets → household/firm distress panel;
5. enforcement/debtor/bankruptcy/court layers → `distress_events_panel_monthly.parquet` enrichment;
6. logistics/mobility/displacement layers (if available) → transport pressure;
7. land cadastre baseline (exploratory) → land-use proxy.

Derived артефакты:

8. `microsim_survey_contract_v1.json` — household/labor inputs в `SurveyMicroData`-compatible form;
9. Heckman correction для firm exit bias → corrected firm panels;
10. survival models для firm exit и distress hazard → hazard estimates;
11. synthetic household construction via raking/IPF/survey weighting → calibrated household cells;
12. `lesson_registry_seed_v1.json` — initial lesson cards from data quality findings.

Валидация:

- household synthetic targets: demographic consistency, no impossible configurations;
- labor-force targets: participation rates within plausible bounds;
- survival models: concordance index > baseline;
- Heckman correction: selection term significant for relevant panels;
- household cells: aggregate to regional anchors within tolerance.

#### D4 — Calibration, Backtesting and Governance Runs

Цель: запустить полный цикл калибровки, governance и backtesting на real data.

Runs:

1. **First calibration run** — full JAX calibration с measurement-aware loss, multi-start optimization;
2. **Bounds estimation** — partial identification для censored/wartime channels;
3. **Transportability check** — formal `tr_algorithm` между Regime A/B/C;
4. **Strategic response verification** — `evaluate_strategic_hook()` для procurement, tax, subsidy channels;
5. **Counterfactual identification** — `id_star` для major policy questions;
6. **Backtest matrix** — all 5 types (macro, cell, strategic-agent, household, distress);
7. **Stress scenarios** — all 6 scenarios (budget contraction, procurement shock, wage subsidy, FX, trade, reimbursement);
8. **Governance passes** — full pass execution per family per run;
9. **Adversarial testing** — all 3 suites (STRATEGIC_GAMING, MULTIPLICITY_DISCLOSURE, ABSTRACTION_LEAKAGE);
10. **Specification-curve analysis** — robustness по source combination.

Output артефакты:

11. `calibration_run_manifest.json`;
12. `loss_breakdown.json`;
13. `holdout_scores.json`;
14. `shock_scenario_scores.json`;
15. `calibration_leaderboard.json` — full leaderboard с all extended metrics;
16. `foundry_seed_state_v1.npz` — calibrated seed state;
17. replay artifacts;
18. lesson cards (FAILURE/SUCCESS) в lesson registry.

Валидация:

- holdout score > minimum threshold;
- all mandatory governance passes: pass or documented exception;
- adversarial suites: no critical failures;
- specification-curve: main result robust across `>70%` of specifications;
- transportability: at least 3 channels pass cross-regime check;
- strategic response: performative shift quantified для `>=3` channels;
- calibration run time < 2 часа, peak RAM < 28 GB.

#### D5 — Embeddings, Compression, Intervention Layer and Release Bundle

Цель: advanced artifacts, intervention layer и финальный release bundle.

Embeddings и compression:

1. agent embeddings (`agent_embedding_32d.npz`) — factor models или neural;
2. cell prototype embeddings (`cell_prototype_embeddings.npz`);
3. multiplex graph compression и graph embeddings;
4. sparse-to-dense bridge verification для selected subgraphs.

Intervention layer:

5. `lex_intervention_map.json` — production mapping Lex provisions → intervention knobs;
6. `intervention_knob_dictionary.json`;
7. `temporal_intervention_sequences.json` — DTR-ready sequential policy timelines;
8. `policy_scenario_templates.json` — reusable scenario specs;
9. `provision_to_program_crosswalk.parquet`.

Advanced runs:

10. Hierarchical policy search trial — STRUCTURE → PARAMETER → NARRATIVE для 1-2 pilot policy questions;
11. Active disambiguation — ranked data collection priorities для next iteration;
12. Bilevel optimization trial — government-firm formulation для procurement channel;
13. Interference-aware calibration — graph-level loss component для budget/procurement.

Release bundle:

14. `runtime_bundle_v1/` — все runtime artifacts, manifests, hashes;
15. `calibration_bundle_v1/` — все calibration artifacts;
16. `method_contract_bundle_v1/` — все typed contract bundles;
17. `governance_report_v1/` — all pass results, adversarial reports, leaderboard;
18. `intervention_bundle_v1/` — all intervention artifacts;
19. `embedding_bundle_v1/` — all embeddings and prototypes;
20. `release_manifest_v1.json` — full lineage, versions, hashes, metrics.

Финальная валидация:

- all success metrics from Section 20 met;
- release bundle internally consistent (manifest hashes match files);
- bundle sizes within budget (runtime < 25 GB, calibration < 20 GB, contracts < 5 GB);
- `PolicyOS` integration test: load release bundle → `build_input_bindings()` → valid `GlobalState` → simulation step → governance → replay roundtrip.

---

### Dependency Graph

```text
Part A (local dev, ~7-11 weeks with parallelism):

  C0  Architecture Freeze
  │
  ├── Wave 1 ─────────────────────────────────────────────
  │   C1 Foundry State ─────────────────────┐
  │   C2 Observation Plane ─────────────────┤
  │   C5a Governance Wiring ────────────────┤ (all 4 parallel)
  │   C6a Lex Intervention Compiler ────────┘
  │
  ├── Wave 2 (needs C1 + C2) ────────────────────────────
  │   C3 Contract Compilers ────────────────┐
  │   C4a Causal Infrastructure ────────────┤ (all 3 parallel)
  │   C6b Agent Sim Executors ──────────────┘
  │
  ├── Wave 3 (needs C3 + C4a) ──────────────────────────
  │   C4b Bounds Estimation ────────────────┐
  │   C5b Backtest & Leaderboard ───────────┤ (all 3 parallel)
  │   C6c Strategic Hook & Policy Search ───┘
  │
  └── Wave 4 (needs everything) ────────────────────────
      C7 Embeddings + Full Integration Test

  ════════════════════════════════════════════════════════

Part B (server, CPX62):

  D0 ──→ D1 ──→ D2 ──→ D3 ──→ D4 ──→ D5
  P0      P1     calibr   P2     runs    release
  core    enrich plane    enrich  govern  bundle
```

### Risk mitigation

| Risk | Mitigation |
|---|---|
| Real data structure diverges from synthetic fixtures | C7 integration test includes schema validation; D0 includes structural smoke tests before full build |
| CPX62 RAM overflow during data build | Each D-phase has peak RAM checkpoint; fallback: DuckDB streaming, chunk-based processing |
| Proxy identification fails on real data | `identify_with_proxy()` returns `ORACLE_NEEDED` — fallback to bounds or downweighted calibration |
| Strategic response solver diverges | `StrategicFallbackMode.STRATEGIC_BOUNDS` — fallback to envelope, not exact equilibrium |
| Governance pass blocks calibration | Documented exception path — blocker logged, not silently skipped |
| P2/P3 sources unavailable | Blueprint is designed to work with P0+P1 only; P2/P3 are enrichments, not dependencies |

---

## 20. Success Metrics

| Метрика | Целевое значение |
|---|---|
| Runtime cohort coverage of Spending/Prozorro participants | `>95%` |
| Share of ordinary agents compressed into meso cells | `>90%` |
| Strategic micro-agent share of total agents | `<10%` |
| Runtime artifact bundle size | `<25 GB` |
| Calibration artifact bundle size | `<20 GB` |
| Method-contract bundle size | `<5 GB` |
| Peak RAM during build | `<28 GB` |
| Observation families in calibration bundle | `>=13` |
| Observation families in calibration bundle with explicit execution surface | `100%` |
| Observation families in calibration bundle with explicit method-family mapping | `100%` |
| Observation families compiled into at least one native method contract bundle | `100%` |
| Observation families with explicit identification-mode assignment | `100%` |
| Observation families with explicit governance pass mapping | `100%` |
| Measurement-aware observations share | `>95%` |
| Runtime contracts supporting first-class `cell` state | `100%` |
| Holdout backtest availability | `100%` of calibration runs |
| Calibration runs publishing replay-ready and backtest-ready artifacts | `100%` |
| Calibration runs publishing LessonCard to lesson registry | `100%` |
| Negative-control / placebo coverage for major policy channels | `>=1 per channel` |
| Lex provisions mapped to explicit intervention knobs for top policy domains | `>80%` |
| Cell and strategic-agent consistency gap | `<5%` |
| Foundry seed export build time | `<30 min` |
| Adversarial suite coverage | `3/3 suites` (STRATEGIC_GAMING, MULTIPLICITY_DISCLOSURE, ABSTRACTION_LEAKAGE) |
| Governance passes with explicit observation-family mapping | `>=7 passes` |
| Channels with formal transportability check (cross-regime) | `>=3 channels` |
| Channels with formal interference/spillover analysis | `>=2 channels` (budget, procurement) |
| Channels with strategic response verification | `>=3 channels` |
| Channels with partial identification (bounds) for censored data | `>=3 channels` |
| Channels with proxy identification (Kuroki-Pearl) verification | `>=3 channels` |
| Policy channels with DTR-ready temporal sequences | `>=2 channels` |
| Specification-curve robustness coverage | `>=1 per major calibration target` |

---

## 21. Explicit Non-Goals

Этот план всё ещё не пытается:

1. построить полный micro-digital twin всех агентов Украины;
2. получить точную геолокацию для большинства ФОП;
3. хранить полные raw histories в production;
4. симулировать все household records как реальные домохозяйства;
5. строить dense graph of all relationships;
6. делать recurring production ETL на первом этапе;
7. forcing symbolic causal identification and governance into one end-to-end differentiable `JAX` graph;
8. **running strategic equilibrium solving or bounds computation inside JAX loop** — these stay symbolic/batch;
9. **replacing domain expertise with automated identification** — `identify_with_proxy()` and `tr_algorithm` verify, not substitute, domain knowledge.

---

## 22. Appendix: Official Source Notes (as of 2026-03-28)

### 22.1. Time coverage notes

- `Spending.gov.ua`: официальный раздел "Про портал" указывает запуск **15 сентября 2015 года**.
- `Prozorro`: официальный раздел "Про систему" указывает обязательность с **1 апреля 2016 года** и **1 августа 2016 года**.

### 22.2. Household and labor microdata notes

- На странице Укрстата по мікроданих умов життя домогосподарств указано, что подготовлены анонимные микроданные по домохозяйствам и лицам за **2018** год.
- На странице Укрстата по мікроданих щодо робочої сили перечислены анонимные микроданные за **2018, 2019, 2020, 2021** годы.

### 22.3. Simulation-enrichment source notes

- На `data.gov.ua` есть набор по фінансовій звітності, поданій як додаток до податкової декларації.
- На `data.gov.ua` есть набор по знеособленій інформації щодо конкретних експортно-імпортних операцій.
- На `data.gov.ua` есть организация Державної служби зайнятості с labor-related наборами.
- На `data.gov.ua` есть открытые наборы по боргам до ПФУ, зарплатной задолженности, банкротствам и другим distress signals.
- На `data.gov.ua` есть реестр распорядителей и получателей бюджетных средств.
- В activity stream НСЗУ видны обновления payment datasets **9 января 2026 года**.
- На `registry.edbo.gov.ua` и `info.edbo.gov.ua` на **28 марта 2026 года** доступны актуальные образовательные registry surfaces.
- На `e-construction.gov.ua` доступен реестр будівельної діяльності и документы по construction activity.
- В метаданных набора таможни по иностранным коммерческим ТС указано обновление **6 января 2026 года**.
- В road dataset на `data.gov.ua` указано состояние road characteristics на **1 января 2024 года**.
- На `data.gov.ua` есть открытые кадастровые наборы, но они требуют отдельной validation story.

### 22.4. External open investigation backlog

Эти источники стоит рассматривать как отдельный track для `region x sector` exogenous layers:

- `VIIRS nighttime lights`
- `WorldPop`
- `ERA5 / Copernicus climate and weather reanalysis`
- displacement / mobility open layers

Плюс отдельный domestic validation backlog:

- education-service observables;
- construction and permit observables;
- logistics friction and border-flow proxies;
- roads/accessibility layers;
- land-use baselines.

Их ценность высокая, но они требуют отдельной методологии transportability и cell-level validation.

### 22.5. Reference URLs

- [Spending.gov.ua: Про портал](https://spending.gov.ua/new/about-portal)
- [Prozorro: Про систему](https://prozorro.gov.ua/about)
- [Укрстат: мікродані умов життя домогосподарств](https://ukrstat.gov.ua/operativ/micro_dani/korystuvahcam.htm)
- [Укрстат: мікродані щодо робочої сили](https://ukrstat.gov.ua/operativ/micro_dani/menu/pr_.htm)
- [Data.gov.ua: фінансова звітність ДПС](https://data.gov.ua/dataset/24069422-5825-41f6-81f7-89567e5e2ac9)
- [Data.gov.ua: знеособлені експортно-імпортні операції](https://data.gov.ua/dataset/scsu-register-export-import-declarations-source)
- [Data.gov.ua: Державна служба зайнятості](https://data.gov.ua/organization/derzhavna-sluzhba-zainiatosti)
- [Data.gov.ua: безробітні, які отримували допомогу](https://data.gov.ua/en/dataset/ceb9a872-95a0-4be1-906e-2509cc02a7a6)
- [Data.gov.ua: реєстр платників ПДВ](https://data.gov.ua/dataset/db391c93-1e68-43c9-bd85-7c6a8427b114)
- [Data.gov.ua: борг до ПФУ](https://data.gov.ua/dataset/48068edb-ab53-4d90-8ed9-027f46f6355e)
- [Data.gov.ua: заборгованість із зарплати](https://data.gov.ua/dataset/eb4cba1e-6cab-4df7-8613-4fbdb03473eb)
- [Data.gov.ua: група наборів АСВП](https://data.gov.ua/dataset/groups/6c0eb6c0-d19a-4bb0-869b-3280df46800a)
- [Data.gov.ua: банкрутства](https://data.gov.ua/dataset/198f87cd-f9de-48a0-a24f-fc5b19604ef4)
- [Data.gov.ua: судові рішення за 2025 рік](https://data.gov.ua/dataset/ediniy-derzhavniy-reestr-sudovih-rishen-za-2025-rik_879)
- [Data.gov.ua: реєстр розпорядників та одержувачів бюджетних коштів](https://data.gov.ua/dataset/8df43bdf-4417-42b4-bc50-bd296af4058e)
- [Data.gov.ua: НСЗУ payments](https://data.gov.ua/en/dataset/25a46db9-2f15-4302-9b59-9bd761c80f46)
- [Registry EDBO](https://registry.edbo.gov.ua/)
- [Info EDBO](https://info.edbo.gov.ua/)
- [ЄДЕССБ / e-Construction](https://e-construction.gov.ua/)
- [Data.gov.ua: іноземні комерційні ТЗ, що в'їхали на митну територію України](https://data.gov.ua/dataset/c831e34e-973e-4d73-a82d-c9bc514d7285/resource/884d2c01-7027-4523-898f-291047356c87)
- [Data.gov.ua: характеристики автомобільних доріг державного значення](https://data.gov.ua/dataset/72dc7da4-a015-4117-9614-d72ba2c3a6a9/resource/9dde340d-adc2-4089-b239-688fd31c00b0/revision/405274/download)
- [Data.gov.ua: інформація з ведення Державного земельного кадастру](https://data.gov.ua/dataset/e6315367-e7a5-4197-a7c4-1e8fa6d984f2/resource/94d92461-18ec-4e51-9b03-a1424f08ddef)
- [WorldPop](https://www.worldpop.org/)
- [Copernicus ERA5 Monthly Means](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels-monthly-means?tab=overview)
- [VIIRS Nighttime Lights](https://eogdata.mines.edu/products/vnl/)
- [IOM DTM Ukraine](https://dtm.iom.int/ukraine)

---

## 23. Final Recommendation

На текущем этапе лучший путь для `PolicyOS` такой:

1. строить не flat-agent simulator, а multiscale world;
2. считать observation plane и measurement model core architecture, а не вспомогательным разделом;
3. держать `firm fundamentals`, `household/labor`, `distress` и `cell-level exogenous` как state-critical families;
4. явно map-ить `Lex` в intervention knobs;
5. встроить backtesting, holdouts и shock calendar с самого начала;
6. использовать embeddings и cell prototypes для компрессии богатой информации;
7. отделить runtime bundle от calibration bundle;
8. описывать артефакты как slot families и execution surfaces, а не только как parquet tables;
9. формализовать `PER_CELL` и `CellState` как обязательное изменение runtime contracts;
10. описывать public-service domains как отдельный слой мира;
11. публиковать multiplex graph family, а не только разрозненные adjacency exports;
12. ввести `core / validated / exploratory` source confidence tiers;
13. оставить runtime лёгким, а всю тяжёлую подготовку и калибровку сделать offline;
14. **маршрутизировать каждую observation family через formal identification mode** — point, bounds, proxy, interference, sequential;
15. **задействовать полный стек каузальной идентификации** — не только point estimation, но и partial identification, transportability, measurement-error correction, interference analysis, counterfactual queries;
16. **покрыть все calibration runs governance passes** — SUTVA Check, Transportability Required, Equity, Refutation, Freshness — с explicit mapping per family;
17. **включить adversarial testing** (STRATEGIC_GAMING, MULTIPLICITY_DISCLOSURE, ABSTRACTION_LEAKAGE) как обязательную часть calibration governance;
18. **использовать lesson registry** для cross-run cumulative learning;
19. **задействовать econometrics** (panel, selection/Heckman, IV, factor), **survival** (hazard), **optimization** (bilevel, game theory, Leontief, chance-constrained) и **sensitivity** (Sobol, specification curves) surfaces;
20. **использовать ready agent_sim executors** — PopulationAwareExecutor, GraphAwareExecutor, DistributionAwareExecutor — для household/firm lifecycle, network diffusion и welfare tracking;
21. **включить strategic response verification** для major policy channels через evaluate_strategic_hook();
22. **использовать hierarchical policy search** (structure → parameter → narrative) для automated policy design;
23. **использовать active disambiguation** для data collection priority ranking.

Именно эта конфигурация даёт лучшее соотношение:

```text
simulation realism / calibration identifiability / CPX62 feasibility / runtime simplicity / causal rigor / governance coverage
```

## 24. Short Data Compromise Log (server execution, 2026-04-08)

Ниже зафиксированы pragmatic data-compromises, на которые пришлось пойти в реальном server execution `Part B`, чтобы продвинуть pipeline без ложного ощущения полноты данных.

- **D0 coverage gate был ослаблен только на сервере:** pragmatic acceptance threshold для `D0` был временно снижен с `0.95` до `0.88` в server config. Repo default `0.95` не менялся. Причина: residual gap оказался обусловлен не форматными ошибками, а длинным хвостом `missing_in_edr_numeric` identifiers, отсутствующих в текущем `ЄДР`.
- **`Prozorro` не использовался как основной procurement backbone:** вместо full historical detail hydration был принят `Spending contracts`-based procurement proxy. `Prozorro` feed сохраняется как auxiliary/enrichment layer, но не как blocking source для `D0`.
- **`procurement_contracts_monthly.parquet` собирается из official proxy, а не из exact OCDS details:** это даёт usable monthly buyer-supplier-amount layer за часы, а не за недели, но не покрывает full procurement lifecycle, amendments, bid-level competition и полную tender/process историю.
- **`DPS financial statements` были заменены provisional official substitute:** вместо полноценного `DPS`-native bulk для `firm_fundamentals_annual.parquet` используется официальный substitute layer из `Держстату`, пока не будет получен устойчивый direct `DPS` source.
- **`ЄДР`-linkage остаётся неполным и признан ограничением данных, а не багом пайплайна:** unresolved `Spending target` и `procurement supplier` identities в основном представлены реальными numeric ids, которых нет в текущем normalized `ЄДР`; это зафиксировано как data quality / registry coverage limitation.
- **`Spending contracts` harvest считается incrementally sufficient до полного завершения:** в production decision-making использован принцип economic-mass sufficiency: ранний harvest покрывал основную долю денежного объёма, даже если ещё не покрывал полный длинный хвост payers/disposers.
- **Часть D1/D3 слоёв остаётся proxy/partial, а не exact canonical sources:** где public exact source отсутствовал или был operationally unstable, использовались public proxies, manual imports или partial public layers; это допустимо для continuation of build pipeline, но не считается окончательным закрытием source gap.
- **Для текущего D4 exact-signoff цикла `PROCUREMENT_FLOWS` и `DISTRESS_ENFORCEMENT` временно выведены из hard blocking set:** текущий procurement proxy coverage и proxy distress layer признаны достаточными для diagnostic/useful release path, но не трактуются как fully exact research-grade closure этих семейств.
- **Оставшийся data-uplift фокус смещён на `ЄДР identity bridge` и `labor market` exactness/bias validation:** именно эти два направления считаются следующими приоритетными источниками подъёма качества для усиления final signoff path без лишнего расширения scope.

Эти компромиссы являются допустимыми только как pragmatic server-execution decisions для текущей итерации и не отменяют целевую архитектуру полного `Part B`, описанную выше.
