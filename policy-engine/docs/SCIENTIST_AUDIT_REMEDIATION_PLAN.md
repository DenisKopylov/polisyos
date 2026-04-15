# Scientist Audit Remediation Plan

> Консолидированный план улучшения и исправления `polisyos.scientist` и
> смежных подсистем по итогам трех аудитов:
> `Deep SOTA Gap Assessment`,
> `Deep Code Audit: Antipatterns, Bugs & Optimizations`,
> `Deep Code Audit: Uncovered Areas`.
> Created: 2026-04-10

---

## Цель

Довести Scientist до состояния, в котором:

- отсутствуют известные correctness-баги, гонки, утечки и silent-failure
  pathways;
- SOTA-claims опираются на реализованные методы, метрики, fairness/calibration
  артефакты и воспроизводимые тесты;
- hot paths не деградируют из-за `model_copy(deep=True)`, квадратичных
  алгоритмов и неограниченного накопления памяти;
- orchestration, governance, search и causal-layer развиваются в правильном
  порядке: сначала надежность, затем доказуемая научная и operational зрелость,
  потом frontier research.

## Область действия

План покрывает не только `src/polisyos/scientist/**`, но и все смежные
поверхности, от которых зависит Scientist-runtime:

- `agent/`, `llm/`, `search/`, `governance/`, `backtesting/`, `discovery/`,
  `compute/`, `policy_verified/`, `replay/`;
- workflow engine, locks, retry, checkpoint, pool execution и trace plumbing;
- fairness, calibration, decision validity и post-deployment monitoring;
- тестовую, benchmark и observability-инфраструктуру для Scientist.

## Ключевой вывод

Система уже сильная по архитектуре и breadth:

- do-calculus / identification / transportability surface уже необычно широкая;
- workflow DAG engine, checkpoint/resume и governance-pass architecture зрелые;
- cross-graph evidence, multi-fidelity search и temporal effects уже дают
  заметное преимущество над типичным open-source baseline.

Но текущий верхний потолок ограничивают не новые research-фичи, а четыре
базовых дефицита:

1. **Корректность исполнения**: `asyncio.gather()` без `return_exceptions`,
   семафоры/локи с race conditions, idempotency defects, budget accounting bugs,
   silent state corruption и resource leaks.
2. **Наблюдаемость и тестируемость**: для части критичных модулей аудиты
   зафиксировали недостаточное direct coverage, почти нет end-to-end workflow
   тестов и нет обязательной benchmark-дисциплины по hot paths.
3. **Научная валидность claims**: отсутствуют E-values, proper calibration
   scoring, intersectional/counterfactual fairness, honest CATE inference и
   единый sensitivity framework.
4. **Производительность и поддерживаемость**: глубокие копии состояния,
   квадратичные алгоритмы, god modules/classes, циклические зависимости, `Any`
   и concrete coupling мешают безопасно масштабировать систему дальше.

Из этого следует главное правило выполнения: **Phase 0-1 обязательны до любых
новых SOTA-claims и до любого frontier research work.**

---

## Принципы исполнения

1. **Correctness before capability**. Ни одна новая agentic, fairness или
   causal-фича не идет в default path, пока не закрыты P0/P1-баги и не появились
   regression tests.
2. **Никаких silent degradations**. Любой fallback должен быть либо typed
   degraded outcome, либо явной ошибкой с traceable причиной.
3. **Каждое исправление получает тест**. Для race condition, leak, budget drift
   и statistical bug нужен воспроизводимый regression test, а не только patch.
4. **Каждый научный claim должен выпускать артефакт**. Calibration, fairness,
   sensitivity и causal robustness должны быть видимы в decision/governance
   artifacts, а не оставаться внутренней логикой.
5. **Hot-path refactor только с benchmark loop**. Замены state-copy semantics,
   merge semantics и scheduling policies делаются только с измерением latency,
   memory и correctness до/после.
6. **Frontier work behind flags**. Proximal causal inference, neural discovery,
   LATS/MCTS и похожие направления сначала живут за feature flag и проходят
   offline evaluation.

---

## Фазовый roadmap

| Phase | Цель | Горизонт | Выходной критерий |
|---|---|---|---|
| 0 | Остановить correctness leaks и security/reliability bugs | 5-7 рабочих дней | Нет открытых P0-багов из аудитов; есть regression tests на каждый фикс |
| 1 | Построить baseline надежности: state safety, observability, tests | 1-2 спринта | Метрики реально экспортируются; есть E2E suite и benchmark suite |
| 2 | Убрать performance и maintainability bottlenecks | 1-2 спринта | Hot paths ускорены, API упрощены, архитектурный долг уменьшается без regressions |
| 3 | Закрыть SOTA gaps по causal, governance и agent/search | 2-3 спринта | SOTA-claims подтверждаются методами, отчетами и eval artifacts |
| 4 | Frontier runtime and research backlog | после Phase 3 | Новые методы изолированы, воспроизводимы и не снижают надежность core-path |

---

## Phase 0 — Containment and correctness blockers

### WS-0A. Async, locking and lifecycle correctness

**Цель:** убрать баги, которые приводят к отмене sibling tasks, нарушению
лимитов параллелизма, stale locks и утечкам процессов/потоков.

**Основные поверхности:**

- `agent/tools/tool_loop.py`
- `agent/router.py`
- `policy_verified/service.py`
- `engine/runner/temporal_runner.py`
- `engine/runner/ray_runner.py`
- `engine/local_pool.py`
- `llm/fallback_router.py`
- `engine/locks/dynamodb_lock.py`
- `engine/locks/redis_lock.py`
- `engine/retry.py`
- `agent/code_verifier.py`
- `agent/persistent_memory.py`
- `compute/runner.py`

**Задачи:**

1. Проставить `return_exceptions=True` на всех критичных `asyncio.gather()`
   call sites и явно разбирать outcomes каждого дочернего task.
2. Переделать `LocalWorkerPool.scale_to()` так, чтобы in-flight tasks не
   "освобождали" старый semaphore мимо нового лимита.
3. Перевести health-state transitions `FallbackRouter` под общий lock и убрать
   мутацию состояния из read-like методов.
4. Закрыть semaphore/queue invariants в pool/fan-out execution:
   не полагаться на compensating hacks для `_queue_depth`, не терять permits при
   partial failure/cancellation.
5. Починить lifecycle фоновых heartbeat/worker ресурсов:
   DynamoDB heartbeat должен останавливаться при backend failure,
   timed-out verifier process должен получать `kill()` fallback,
   timed-out retry worker не должен оставлять orphan thread без owner.
6. Сделать lock metadata атомарной с lock acquisition и запретить `force=True`
   без валидной проверки ownership/token provenance.
7. Защитить от dedup races `PersistentMemoryStore` и от concurrent bootstrap
   races registry/advanced method initialization.

**Критерии приемки:**

- fault-injection tests доказывают, что один failing task больше не ломает
  sibling results и не создает `KeyError`;
- shrink/expand worker pool выдерживает concurrency stress test без permit drift;
- lock-acquisition tests проверяют ownership, metadata atomicity и teardown;
- timeout tests не оставляют живых процессов/потоков после завершения кейса.

### WS-0B. Budget, request correctness, security and scientific hotfixes

**Цель:** убрать баги, из-за которых система теряет идемпотентность, неверно
считает бюджет, silently leaks data или публикует статистически некорректные
результаты на default path.

**Основные поверхности:**

- `llm/gateway_client.py`
- `llm/budget_enforcer.py`
- `llm/token_estimator.py`
- `replay/diff.py`
- `engine/sub_workflow.py`
- `backtesting/masking.py`
- `engine/iteration_state_machine.py`
- `engine/convergence.py`
- `adapters/foundry_bridge.py`
- `autotune/cheap_stage.py`
- `backtesting/bootstrap.py`

**Задачи:**

1. Генерировать `x-idempotency-key` один раз на всю request-attempt group, а не
   заново на каждый retry.
2. Исправить reservation accounting в budget enforcement:
   release работает только на реально зарезервированный остаток и не
   over-credit budget после post-record adjustment.
3. Убрать `except BaseException` из budget path; cleanup делать в `finally`,
   cancellation/system-exit не маскировать.
4. Сделать fallback token estimation консервативным и provider-aware, чтобы
   budget gate не пропускал заведомо недооцененный input.
5. Добавить guards на пустые входы / нулевые лимиты / invalid depth:
   `replay/diff`, `sub_workflow`, `convergence`, `iteration_state_machine`.
6. Перевести masking bypass в hard validation error, чтобы не было leakage
   post-intervention ground truth.
7. Санитизировать environment writes через foundry bridge.
8. Срочно исправить statistical correctness defects на default path:
   правильные ties для Spearman; валидный RMSE CI; при необходимости временно
   пометить спорные методы как experimental до полного Phase 3 validation.

**Критерии приемки:**

- retry одного и того же запроса использует стабильный idempotency key;
- budget ledger остается консистентным при ошибках до и после `_post_record`;
- invalid depth / zero budget / empty input дают typed error, а не silent drift;
- security tests подтверждают, что foundry bridge не инжектит опасные env values;
- statistical regression suite воспроизводит и закрывает выявленные ошибки.

---

## Phase 1 — Reliability baseline

### WS-1A. Error semantics and degraded-mode policy

**Цель:** убрать бесконтрольное swallowing exceptions и сделать failure surface
диагностируемой.

**Основные поверхности:**

- `llm/budget_enforcer.py`
- `engine/async_executor.py`
- `llm/token_estimator.py`
- `search/controller.py`
- `llm/gateway_client.py`
- `agent/formalizer.py`
- `governance/passes/**`
- `causal/readiness.py`
- `nodes/builtins/**`
- `llm/streaming.py`
- `compute/runner.py`

**Задачи:**

1. Провести аудит всех broad `except Exception` / `# noqa: BLE001` блоков и
   заменить их на:
   - typed exception handling;
   - structured degraded result;
   - warning artifact/metric, если деградация допустима.
2. Вернуть exception chaining в retry loops и final raises.
3. Удалить duplicate handlers с одинаковым телом и собрать общие helper paths.
4. Ввести единый error envelope для tool calls, cache bypass, artifact loading и
   JSON/stream parsing.
5. Запретить debug-only swallowing для governance-critical и budget-critical
   модулей.

**Критерии приемки:**

- у всех известных swallowing sites есть либо typed error, либо explicit
  degraded result с логом/метрикой;
- повторяемые retry failures сохраняют root cause chain;
- observability показывает count degraded paths по типам.

### WS-1B. Atomic state mutation, merge semantics and deterministic execution

**Цель:** сделать параллельные и частичные state updates предсказуемыми.

**Основные поверхности:**

- `engine/async_executor.py`
- `engine/fan_out.py`
- `nodes/builtins/**`
- `engine/checkpoint.py`
- `engine/iteration_state_machine.py`
- `discovery/active.py`
- `discovery/portfolio.py`
- `causal/execution.py`

**Задачи:**

1. Заменить pattern "mutate state as we go" на staged mutation plan:
   сначала собрать и провалидировать все изменения, потом применить атомарно.
2. Убрать silent conflict drop при merge parallel branches:
   конфликт либо resolve-ится по явной policy, либо execution останавливается с
   artifact-ом конфликта.
3. Ввести configurable merge strategies для fan-out/checkpoint resume вместо
   current all-or-nothing / undefined behavior.
4. Добавить `math.isfinite()` guards перед clamp/score normalization, чтобы NaN
   не протекал через discovery/causal/governance.
5. Пересмотреть convergence window semantics: no decision on insufficient sample.
6. Подготовить deterministic savepoint/rollback contract для tier execution.

**Критерии приемки:**

- partial mutation failures не оставляют наполовину измененный state;
- конфликтующие parallel writes детектируются и видимы пользователю;
- NaN regression tests покрывают priority/scoring/clamp paths;
- convergence tests не триггерят ранний успех на пустой или короткой истории.

### WS-1C. Observability, metrics exporter and operational hygiene

**Цель:** перевести Scientist observability из протоколов и stubs в рабочую
операционную систему.

**Основные поверхности:**

- `engine/metrics.py` / `NoopEngineMetrics` и смежные adapters
- trace propagation между runners
- checkpoint/DLQ storage flows
- runtime monitoring hooks

**Задачи:**

1. Реализовать реальный Prometheus/OTel exporter вместо protocol-only surface.
2. Автоматизировать trace correlation между local, Ray и Temporal runners.
3. Доделать checkpoint GC и DLQ replay/retrieval API.
4. Ввести bounded retention для in-memory accumulators:
   provenance DAG, correlation trackers, provider verification notes и пр.
5. Добавить post-deployment monitoring skeleton:
   drift, calibration degradation, fairness regression и budget anomaly alerts.

**Критерии приемки:**

- ключевые Scientist метрики экспортируются и доступны в runtime;
- run traces коррелируются между runners без ручной передачи headers;
- есть documented replay path для DLQ;
- long-running tests показывают bounded memory growth.

### WS-1D. Test and benchmark program

**Цель:** закрыть главный доверительный пробел между сильной архитектурой и
реальной production-готовностью.

**Приоритетные поверхности:**

- `src/polisyos/scientist/decision_validity.py`
- `src/polisyos/scientist/feedback.py`
- `src/polisyos/scientist/llm_cycle.py`
- `src/polisyos/scientist/replay_backend.py`
- `src/polisyos/scientist/evidence_sources.py`
- workflow chain: `agent -> search -> simulation -> governance -> decision`

**Задачи:**

1. Ввести unit + property + concurrency coverage для критичных core modules,
   которые аудиты отметили как недостаточно покрытые direct tests.
2. Добавить минимум 5 end-to-end workflow scenarios:
   - happy path;
   - tool failure with retry;
   - checkpoint resume;
   - governance rejection/escalation;
   - fairness/calibration regression.
3. Запустить `pytest-benchmark` suite на:
   - node latency;
   - checkpoint I/O;
   - state serialization/copy path;
   - fan-out merge;
   - Pareto / failure-index / search hot paths.
4. Для каждого P0/P1 bugfix добавить regression test по исходному reproducer.

**Критерии приемки:**

- core-path покрыт не только API-level tests, но и module-level behavior tests;
- benchmark suite встроен в CI tiers;
- появляется один официальный Scientist reliability scorecard.

---

## Phase 2 — Performance and maintainability

### WS-2A. Hot-path memory, algorithmic complexity and cache efficiency

**Цель:** убрать самые дорогие performance bottlenecks без потери
детерминизма и воспроизводимости.

**Основные поверхности:**

- `engine/async_executor.py`
- `engine/fan_out.py`
- `autotune/pareto.py`
- `discovery/aggregator.py`
- `agent/failure_index.py`
- `discovery/portfolio.py`
- `discovery/priors.py`
- `simulation/inference.py`
- `llm/prompt_cache.py`

**Задачи:**

1. Уйти от безусловного `model_copy(deep=True)` в hot paths:
   перейти к shallow copy + copy-on-write / staged overlay semantics с явным
   mutation journal.
2. Заменить O(n^2) Pareto dominance на алгоритм с лучшей асимптотикой для
   2-3 objectives.
3. Кэшировать hypothesis-edge keys и token sets там, где сейчас каждый запрос
   пересчитывает их заново.
4. Оптимизировать cycle detection, prior dedup, permutation tests и cache keys,
   исключив nondeterministic metadata из кэша.
5. Починить shared-reference mutation risk в prompt cache clone path.

**Критерии приемки:**

- benchmark suite показывает заметное ускорение fan-out/executor/search paths;
- memory profile не растет квадратично при увеличении parallel work;
- cache hit rate растет за счет детерминированного keying.

### WS-2B. API simplification, module decomposition and type safety

**Цель:** уменьшить архитектурную хрупкость и стоимость изменений.

**Основные поверхности:**

- `search/judge_stack.py`
- `build_decision_packet.py`
- `run_policy_blueprint_runtime.py`
- `cross_graph/compiler.py`
- `feedback.py`
- `engine/checkpoint.py`
- `search/controller.py`

**Задачи:**

1. Убрать passthrough API с десятками параметров и перейти к value objects /
   direct constructor usage.
2. Разбить god modules и god classes на bounded submodules с понятными портами.
3. Разорвать circular imports через protocols / service interfaces, а не через
   function-local imports как постоянную практику.
4. Заменить concrete service coupling на protocols в Scientist core.
5. Ввести ratchet на `Any`, unsafe `cast()` и небезопасный `dict[]` access.
6. Вынести common governance helpers и shared threshold/scoring utilities.
7. Убрать дублирование SIR/SEIR и похожие copy-paste участки.

**Критерии приемки:**

- самые тяжелые модули перестают быть change magnets;
- количество `Any` и unsafe casts снижается по согласованному ratchet;
- import cycles сокращаются до допустимого минимума;
- interface contracts становятся проще тестировать через fakes/stubs.

---

## Phase 3 — SOTA claim closure

### WS-3A. Causal inference and statistical validity

**Цель:** закрыть те gaps, без которых Scientist не должен заявляться как
безкомпромиссный SOTA causal/governance stack.

**Порядок внедрения:**

1. **Low-effort / high-impact first**
   - E-values;
   - proper sensitivity reporting surface;
   - honest causal forests with valid CI;
   - fixes для IPW / Ljung-Box / bootstrap validity.
2. **Strong SOTA next**
   - universal sensitivity analysis;
   - ICP + anchor regression;
   - Bayesian causal discovery;
   - recoverability under selection bias;
   - PAG d-separation refinement.
3. **Frontier after baseline**
   - proximal causal inference;
   - neural causal discovery;
   - causal representation learning.

**Deliverables:**

- новые causal runners / artifacts / docs;
- benchmark/eval pack на synthetic и semi-synthetic datasets;
- явные confidence/sensitivity sections в decision packet;
- acceptance notebook or report, сравнивающий старый и новый pipeline.

### WS-3B. Governance, fairness, calibration and accountability

**Цель:** сделать governance claims измеримыми, explainable и пригодными для
внешнего аудита.

**Порядок внедрения:**

1. **Сначала доказуемая calibration layer**
   - Brier score, log score, reliability diagrams, ENCE;
   - calibration-by-group и fairness-aware calibration reporting.
2. **Потом fairness**
   - intersectional fairness;
   - equalized odds / calibration by group;
   - counterfactual fairness.
3. **Потом accountability and decision policy**
   - unified model card / datasheet artifact;
   - adaptive thresholds;
   - risk-weighted verdicts;
   - fairness-accuracy Pareto frontier;
   - CVaR / tail-risk reporting.
4. **И только затем advanced governance search**
   - adversarial scenario discovery;
   - continuous post-deployment drift and degradation monitoring.

**Deliverables:**

- единый governance accountability artifact;
- новые pass outputs и dashboards;
- threshold registry с rationale вместо magic numbers;
- documented escalation policy для probabilistic verdicts.

### WS-3C. Search, optimization and agent reasoning

**Цель:** поднять Scientist agent/search слой от сильной линейной orchestration к
современному search-and-reason framework.

**Порядок внедрения:**

1. Укрепить существующий supervisor/worker контур на базе текущего DAG executor,
   а не ad hoc `asyncio.gather()`.
2. Добавить tree-based reasoning:
   - Tree of Thought;
   - LATS / MCTS over agent actions.
3. Улучшить search/optimization policy:
   - BOHB / ASHA;
   - evolutionary / CMA-ES exploration;
   - learned VOI;
   - learned routing;
   - GP surrogates for cheap stage;
   - explicit constraint propagation;
   - population-based training.

**Deliverables:**

- evaluation harness для agent trajectories;
- comparative reports against current Reflexion-only baseline;
- configurable routing/search policies with offline gating before default enable.

---

## Phase 4 — Frontier runtime and distributed hardening

### WS-4A. Runtime scalability and distributed safety

**Цель:** перевести engine в состояние, где large-scale distributed execution не
ломает correctness и observability.

**Основные направления:**

- incremental checkpointing вместо full-state snapshots;
- saga compensation hooks для resume/rollback flows;
- distributed budget ledger вместо in-memory only accounting;
- priority scheduling / weighted queuing;
- finalized checkpoint GC and retention policy;
- stronger state-merge policies для resume and multi-runner execution.

**Правило:** этот phase запускается только после того, как Phase 1 metrics,
tests и trace correlation уже работают в production-like режиме.

### WS-4B. Frontier research backlog

**Основные направления:**

- proximal causal inference;
- neural DAG learners (DECI, AVICI и аналоги);
- causal representation learning;
- adversarial scenario discovery вместо fixed stress multipliers;
- continuous governance loop с drift + calibration + fairness retraining hooks.

Все эти элементы должны идти за feature flag, с отдельным benchmark/eval pack и
без замены baseline path до завершения offline validation.

---

## Зависимости между фазами

1. `WS-0A` и `WS-0B` блокируют все остальные workstreams.
2. `WS-1D` обязателен до крупных refactor из `WS-2A` и `WS-2B`, иначе мы не
   сможем безопасно мерить regressions.
3. `WS-1C` обязателен до `WS-4A`, иначе distributed hardening останется слепым.
4. `WS-2A` должен быть завершен до включения тяжелых search/agent методов из
   `WS-3C`, иначе стоимость reasoning резко вырастет.
5. `WS-3A` и `WS-3B` обязательны до публичных claims о SOTA governance/causal
   validity.

---

## Definition of done по уровням

### Done for Phase 0

- закрыты все известные подтвержденные bugs, влияющие на correctness,
  idempotency, resource lifecycle, locking и budget accounting;
- на каждый фикс есть regression test;
- нет silent leakage path в masking / env injection / depth guards.

### Done for Phase 1

- есть реальный metrics exporter и working trace correlation;
- есть DLQ replay path и checkpoint hygiene;
- есть unit, integration и benchmark suite для Scientist core;
- parallel execution и merge semantics детерминированы и задокументированы.

### Done for Phase 2

- hot paths больше не зависят от бесконтрольных deep-copy;
- ключевые алгоритмические bottlenecks устранены;
- API/core modules проще в сопровождении и лучше типизированы.

### Done for Phase 3

- causal/gov/search SOTA gaps закрыты в коде, документации и eval artifacts;
- fairness/calibration/model card outputs доступны как first-class artifacts;
- новые методы сравниваются с baseline на reproducible benchmark suite.

### Done for Phase 4

- distributed runtime доказуемо корректен при resume/failure/replay;
- frontier methods не снижают reliability baseline и имеют feature-gated rollout.

---

## Audit coverage map

Легенда:

- **SOTA** — `Deep SOTA Gap Assessment`
- **DCA** — `Deep Code Audit: Antipatterns, Bugs & Optimizations`
- **UA** — `Deep Code Audit: Uncovered Areas`

| Workstream | SOTA gaps covered | DCA refs covered | UA refs covered | Что именно закрывается |
|---|---|---|---|---|
| `WS-0A` | — | `A1`, `A2`, `A4`, `B1`, `B3` | `B3`, `B4`, `B5`, `B8`, `B9`, `H3`, `H4`, `S7`, `S8` | gather/cancellation, semaphore correctness, lock lifecycle, thread/process leaks, registry races |
| `WS-0B` | — | `A3`, `B2` | `B1`, `B2`, `H2`, `H6`, `H7`, `H10` | idempotency, budget accounting, token estimation, guards, state-machine correctness, env injection |
| `WS-0B` + `WS-3A` | — | — | `B6`, `B7`, `B10`, `H8`, `H9` | statistical validity hotfixes, masking leakage fix, default-path scientific correctness |
| `WS-1A` | — | `C1`, `C2`, `C3` | `S3` | typed errors, preserved exception context, no silent swallowing |
| `WS-1B` | state merge strategies | `D1`, `F3` | `H5`, `S1`, `S2`, `O6` | atomic state writes, merge policy, NaN guards, convergence correctness |
| `WS-1C` | metrics exporter, DLQ retrieval, cross-runner trace correlation, checkpoint GC, post-deployment monitoring | — | `S5` | observability, bounded accumulators, replayability |
| `WS-1D` | zero tests for critical modules, low integration coverage, no benchmarks, no E2E workflows | — | — | direct module coverage, E2E suite, benchmark suite |
| `WS-2A` | — | `D2`, `D3`, `D4` | `H1`, `O1`, `O2`, `O4`, `O5` | algorithmic complexity, cache efficiency, shared-ref cache mutation |
| `WS-2B` | — | `E1`, `E2`, `E3`, `E4`, `E5`, `F1`, `F2` | `S4`, `O3` | API simplification, module splits, protocol boundaries, type-safety ratchet |
| `WS-3A` | E-values, proximal causal inference, universal sensitivity, honest causal forests + CI, neural causal discovery, ICP, causal representation learning, Bayesian causal discovery, recoverability, PAG d-separation refinement | — | — | causal completeness and scientific validity of effect claims |
| `WS-3B` | proper scoring rules, intersectional fairness, counterfactual fairness, model cards/datasheets, fairness-accuracy Pareto, adaptive thresholds, risk-weighted verdicts, adversarial scenario discovery, tail risk, post-deployment monitoring | — | `S6` | measurable governance, fairness artifacts, threshold rationale, accountable decisions |
| `WS-3C` | Tree of Thought, LATS/MCTS, learned VOI, BOHB/ASHA, CMA-ES, learned routing, GP surrogates, constraint handling, population-based training | — | — | agent/search/optimization modernization |
| `WS-4A` | incremental checkpointing, saga pattern, distributed budget ledger, priority scheduling | — | — | distributed runtime safety and scale |

Эта таблица задает простое правило: **каждый finding из аудитов должен быть
закрыт конкретным workstream, тестом и observable acceptance signal.**

---

## Рекомендуемый порядок исполнения по спринтам

### Sprint 1

- `WS-0A`
- `WS-0B`
- начать regression tests из `WS-1D`

### Sprint 2

- `WS-1A`
- `WS-1B`
- `WS-1C`
- расширить `WS-1D`

### Sprint 3

- `WS-2A`
- `WS-2B`
- закрыть все benchmark gates

### Sprint 4-5

- `WS-3A`
- `WS-3B`

### Sprint 6+

- `WS-3C`
- `WS-4A`
- `WS-4B`

---

## Что считать блокерами для любого SOTA-claim

До завершения как минимум `Phase 1` не стоит публично заявлять
"безкомпромиссный SOTA" по Scientist. Минимальный claim bar:

1. нет известных P0/P1 correctness bugs из аудитов;
2. есть real metrics exporter и reproducible test/benchmark evidence;
3. causal/fairness/calibration claims подтверждаются артефактами, а не только
   кодом;
4. parallel execution, retry и budget semantics детерминированы и наблюдаемы.

Иначе система может быть архитектурно сильной, но все еще слишком хрупкой для
жестких external claims.
