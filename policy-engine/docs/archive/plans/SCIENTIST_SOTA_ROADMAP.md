> **Archived:** This document reflects plans as of 2026-03-23.
> See [current docs](../../explanation/index.md) for up-to-date information.

# Scientist Module: SOTA Roadmap (9/10+ по каждой подсистеме)

> **Дата**: 2026-03-22
> **Статус**: Фазы 1-4 завершены. Общая оценка: **7.1/10**. Цель: **9.0+/10**.
> **Масштаб модуля**: 264 файла, ~55 500 LOC, 18 подсистем, 955 тестов.

---

## Содержание

1. [Текущее состояние после фаз 1-4](#1-текущее-состояние-после-фаз-1-4)
2. [Матрица зрелости: текущее vs целевое](#2-матрица-зрелости-текущее-vs-целевое)
3. [Phase 5 — Engine Hardening (9/10)](#3-phase-5-engine-hardening)
4. [Phase 6 — Agent & Search SOTA (9/10)](#4-phase-6-agent-search-sota)
5. [Phase 7 — Governance & Compliance (9/10)](#5-phase-7-governance-compliance)
6. [Phase 8 — Observability & Provenance (9/10)](#6-phase-8-observability-provenance)
7. [Phase 9 — Testing & Reliability (9/10)](#7-phase-9-testing-reliability)
8. [Phase 10 — Scale & Multi-Tenancy (9/10)](#8-phase-10-scale-multi-tenancy)
9. [Phase 11 — Remaining Subsystems (9/10)](#9-phase-11-remaining-subsystems)
10. [Сводная таблица всех workstreams](#10-сводная-таблица-всех-workstreams)
11. [Зависимости между фазами](#11-зависимости-между-фазами)
12. [Критерии приёмки 9/10](#12-критерии-прие-мки-9-10)

---

## 1. Текущее состояние после фаз 1-4

### Что реализовано

| Фаза | Ключевые результаты |
|------|-------------------|
| **Phase 1** | AsyncWorkflowExecutor (TaskGroup + tiered DAG), per-node retry/timeout, kernel tests (94), agent internal tests (134), metrics protocol + OTel |
| **Phase 2** | Pluggable CAS (S3/GCS/Caching), distributed run-lock (Redis+fcntl), audit trail protocol, LLM budget enforcement, tool-use protocol |
| **Phase 3** | Conditional nodes, sub-workflow nesting, fan-out/fan-in, convergence detection, persistent agent memory |
| **Phase 4** | Runner backends (local/Ray/Temporal), trace attributes, provenance DAG, replay/diff, neural search + transfer learning, vector memory, multi-tenancy structure |

### Архитектурные сильные стороны

1. **Protocol-driven** — все абстракции (Node, WorkflowEngine, PIAgent, ArtifactStore, RunLockBackend, WorkflowRunnerBackend) — `typing.Protocol`
2. **Immutable state** — `ExperimentState` с `ConfigDict(extra="forbid")`, deep-copy, idempotent keys
3. **Checkpoint/resume** — CAS, atomic writes, run-lock, три policy
4. **Governance pipeline** — 17 validation passes, три профиля, chain-of-responsibility
5. **Lazy imports** — `__getattr__()` для тяжёлых модулей
6. **Tiered DAG** — topological sort по тирам, параллельное выполнение внутри тира

---

## 2. Матрица зрелости: текущее vs целевое

| Подсистема | Сейчас | Цель | Дельта | Фаза |
|-----------|--------|------|--------|------|
| Engine core (DAG, state, retry, timeout) | 7.5 | 9.0 | +1.5 | Phase 5 |
| Checkpoint/Resume | 9.0 | 9.5 | +0.5 | Phase 5 |
| Workflow composition | 8.0 | 9.0 | +1.0 | Phase 5 |
| Agent hierarchy | 7.5 | 9.0 | +1.5 | Phase 6 |
| Search/HPO | 8.0 | 9.0 | +1.0 | Phase 6 |
| Governance pipeline | 7.5 | 9.0 | +1.5 | Phase 7 |
| Security/Compliance | 5.5 | 9.0 | +3.5 | Phase 7 |
| Observability | 7.0 | 9.0 | +2.0 | Phase 8 |
| Reproducibility/Lineage | 7.0 | 9.0 | +2.0 | Phase 8 |
| Testing | 6.0 | 9.0 | +3.0 | Phase 9 |
| Distributed execution | 6.0 | 9.0 | +3.0 | Phase 10 |
| Multi-tenancy | 4.0 | 9.0 | +5.0 | Phase 10 |
| Autotune | 6.0 | 9.0 | +3.0 | Phase 11 |
| Cross-graph evidence | 6.5 | 9.0 | +2.5 | Phase 11 |
| Backtesting | 7.5 | 9.0 | +1.5 | Phase 11 |
| Nodes (builtins) | 7.0 | 9.0 | +2.0 | Phase 11 |
| LLM integration | 8.0 | 9.0 | +1.0 | Phase 11 |
| DOE | 7.5 | 9.0 | +1.5 | Phase 11 |
| Policy Verified | 7.0 | 9.0 | +2.0 | Phase 11 |

**Средневзвешенная**: 7.1 → 9.0

---

## 3. Phase 5 — Engine Hardening

**Цель**: Engine core 7.5→9.0, Checkpoint 9.0→9.5, Workflow composition 8.0→9.0
**Оценка**: 2-3 недели

### WS5.1 — Circuit Breaker + Jitter в retry.py

**Проблема**: Retry без jitter создаёт thundering herd. Нет circuit breaker — при каскадном сбое все ноды ретраятся одновременно.

**Файлы**: `engine/retry.py`

**Задачи**:

1. **Jitter** — добавить randomized jitter к exponential backoff:
   ```python
   delay = base_delay * (backoff_factor ** attempt) * (1 + random.uniform(0, 0.25))
   ```

2. **Circuit breaker** — новый класс `CircuitBreaker`:
   - Состояния: CLOSED → OPEN → HALF_OPEN
   - Параметры: `failure_threshold=5`, `recovery_timeout_s=30`, `half_open_max_calls=1`
   - При OPEN — мгновенный `CircuitOpenError` без попытки выполнения
   - Интеграция: `RetryPolicy.circuit_breaker: CircuitBreaker | None`

3. **Async cancellation** — обработка `asyncio.CancelledError` в `execute_with_retry_async()`:
   - Не ретраить cancelled — пробрасывать вверх
   - Cleanup хук для освобождения ресурсов

4. **Dead-letter artifact** — при исчерпании retry сохранять serialized outcome в DLQ artifact:
   ```
   artifacts_index["dlq.<node_id>"] = ArtifactRef(...)
   ```

**Тесты**: ~20 тестов (jitter distribution, CB state transitions, cancellation, DLQ)

### WS5.2 — Async Executor Hardening

**Проблема**: TaskGroup не обрабатывает explicit cancellation. Shared state reference в параллельных ветках. Semaphore без timeout.

**Файлы**: `engine/async_executor.py`

**Задачи**:

1. **Per-task state snapshots** — вместо shared `state` передавать `state.model_copy(deep=True)` каждой параллельной ноде

2. **Semaphore timeout** — `asyncio.wait_for(semaphore.acquire(), timeout=tier_timeout_s)`

3. **Explicit cancellation** — при TaskGroup exception:
   ```python
   for task in running_tasks:
       task.cancel()
   await asyncio.gather(*running_tasks, return_exceptions=True)
   ```

4. **State rollback savepoints** — перед каждым тиром сохранять snapshot; при tier failure — откат к savepoint

5. **Backpressure metrics** — эмитить `scientist_tier_queue_depth` gauge из semaphore counter

6. **Workflow-level timeout** — `asyncio.wait_for(self._execute_tiers(...), timeout=workflow_timeout_s)`

**Тесты**: ~15 тестов (parallel isolation, semaphore timeout, cancellation, savepoints)

### WS5.3 — Checkpoint Garbage Collection + Schema Evolution

**Проблема**: Checkpoint-ы растут бесконечно. Нет schema version check при resume.

**Файлы**: `engine/checkpoint.py`

**Задачи**:

1. **GC policy** — `CheckpointGCPolicy(max_checkpoints=10, max_age_hours=168)`:
   - `gc_checkpoints()` вызывается после каждого нового checkpoint
   - Удаляет по FIFO, сохраняя latest + N

2. **Schema version validation** — при `resume_from_checkpoint()`:
   ```python
   if checkpoint.schema_version != CURRENT_SCHEMA_VERSION:
       raise CheckpointSchemaError(f"Expected {CURRENT_SCHEMA_VERSION}, got {checkpoint.schema_version}")
   ```

3. **Lock retry loop** — вместо мгновенного fail при LOCK_NB:
   ```python
   for attempt in range(max_lock_retries):
       try:
           acquire()
           break
       except BlockingIOError:
           await asyncio.sleep(backoff)
   ```

4. **Distributed checkpoint store** — использовать `ArtifactStore` protocol вместо filesystem-only

**Тесты**: ~12 тестов (GC, schema mismatch, lock retry, distributed store)

### WS5.4 — Budget Enforcement Middleware

**Проблема**: `BudgetState` считается, но нигде не проверяется перед выполнением ноды.

**Файлы**: `engine/budget.py`, `engine/executor.py`, `engine/async_executor.py`

**Задачи**:

1. **Pre-execution check** в executor loop:
   ```python
   if state.budget and state.budget.would_exceed(estimated_node_cost):
       raise BudgetExhaustedError(node_id, state.budget)
   ```

2. **Per-provider tracking** — расширить `BudgetState`:
   ```python
   provider_spent: dict[str, float]  # {"openai": 12.50, "anthropic": 8.30}
   ```

3. **Threshold alerts** — при 80% и 90% бюджета эмитить warning event + metric

4. **Allocation/deallocation** — `reserve(amount) → token`, `release(token, actual)` для точного учёта

5. **Thread-safe** — `threading.Lock()` вокруг budget mutations

**Тесты**: ~15 тестов (pre-check, per-provider, alerts, allocation, thread-safety)

### WS5.5 — Fan-Out Async + Condition Enhancements

**Проблема**: Fan-out выполняется последовательно. Condition DSL не поддерживает AND/OR.

**Файлы**: `engine/fan_out.py`, `engine/condition.py`

**Задачи**:

1. **Async fan-out** — `AsyncFanOutNode` с `asyncio.TaskGroup`:
   ```python
   async with asyncio.TaskGroup() as tg:
       for item in items[:max_parallelism]:
           tg.create_task(execute_item(item))
   ```

2. **Streaming merge** — yield partial results вместо накопления всех в памяти

3. **Merge conflict resolution** — enum `MergeConflictPolicy`: FIRST_WINS, LAST_WINS, ERROR, MERGE_LISTS

4. **Compound conditions** — поддержка `AND` / `OR`:
   ```
   "params.method == 'did' AND artifacts.causal_graph IS NOT NONE"
   ```

5. **Aggregate operators** — `length()`, `count()`, `empty()`:
   ```
   "artifacts.length > 5"
   ```

**Тесты**: ~15 тестов (async fan-out, streaming, conflicts, compound conditions)

---

## 4. Phase 6 — Agent & Search SOTA

**Цель**: Agent 7.5→9.0, Search 8.0→9.0
**Оценка**: 3-4 недели

### WS6.1 — Tool Loop Hardening

**Проблема**: Фиксированный max_iterations=10, нет timeout per tool call, нет circuit breaker для failing tools.

**Файлы**: `agent/tools/tool_loop.py`

**Задачи**:

1. **Per-tool timeout** — `ToolDefinition.timeout_s: float = 30.0` + `asyncio.wait_for` wrapper

2. **Tool circuit breaker** — если tool fails 3 раза подряд, skip на оставшиеся итерации:
   ```python
   tool_failures: dict[str, int]  # track per-tool failure count
   if tool_failures[name] >= circuit_threshold:
       return ToolCallResult(success=False, error="circuit open")
   ```

3. **Adaptive max iterations** — вместо fixed 10:
   ```python
   max_iter = min(base_max, budget_remaining // estimated_cost_per_iter)
   ```

4. **Exponential backoff** на transient tool failures

5. **Tool dependency graph** — optional ordering constraints между tools

**Тесты**: ~18 тестов

### WS6.2 — Semantic Convergence Detection

**Проблема**: Convergence tracking только по tool call count, не по семантическому прогрессу.

**Файлы**: `engine/convergence.py`, `agent/_drafter_orchestrator.py`

**Задачи**:

1. **Embedding-based convergence** — сравнивать embedding distance между consecutive draft outputs:
   ```python
   similarity = cosine_similarity(embed(draft_n), embed(draft_n_minus_1))
   if similarity > convergence_threshold:
       return ConvergenceResult(converged=True, metric=similarity)
   ```

2. **Statistical significance** — t-test для plateau detection вместо simple window min:
   ```python
   from scipy.stats import ttest_1samp
   # H0: mean improvement == 0
   _, p_value = ttest_1samp(improvements[-window:], 0)
   converged = p_value > significance_level
   ```

3. **Budget-aware projection** — экстраполировать improvement trajectory:
   ```python
   projected_gain = linear_extrapolation(improvements, remaining_budget)
   if projected_gain < min_worthwhile_gain:
       return early_stop
   ```

4. **Multi-signal composite** — взвешенная комбинация: semantic + numeric + budget:
   ```python
   score = w_semantic * sem_conv + w_numeric * num_conv + w_budget * budget_pressure
   ```

**Тесты**: ~15 тестов

### WS6.3 — Dynamic Agent Routing

**Проблема**: Фиксированная иерархия PI→Drafter→Formalizer→Critic. Нет runtime re-routing.

**Файлы**: `agent/protocols.py`, новый `agent/router.py`

**Задачи**:

1. **AgentRouter protocol**:
   ```python
   class AgentRouter(Protocol):
       def select_next_agent(self, state: ExperimentState, history: list[AgentAction]) -> AgentRole: ...
       def should_escalate(self, state: ExperimentState, failures: int) -> bool: ...
   ```

2. **Rule-based router** (default) — текущая фиксированная иерархия как fallback

3. **Adaptive router** — выбор агента по state signals:
   - Если `error_count > threshold` → переключить на Critic
   - Если `confidence < min_confidence` → вернуть к Drafter
   - Если `budget_remaining < 20%` → skip optional agents

4. **Agent composition** — параллельный запуск Drafter + Critic для co-optimization

5. **Fallback chain** с degradation levels:
   ```
   LLMDrafter → MockDrafter → CachedDrafter → FailSafe
   ```

**Тесты**: ~20 тестов

### WS6.4 — Persistent Memory Enhancement

**Проблема**: Lexical-only search (Jaccard), нет deduplication, нет cross-run consolidation.

**Файлы**: `agent/persistent_memory.py`, `agent/vector_memory.py`

**Задачи**:

1. **Semantic search** — использовать `VectorMemoryStore` вместо Jaccard:
   ```python
   def recall(self, query: str, top_k: int = 5) -> list[MemoryEntry]:
       embedding = self.embedder.embed(query)
       return self.vector_store.search(embedding, top_k)
   ```

2. **Deduplication** — content-hash based:
   ```python
   content_hash = hashlib.sha256(entry.content.encode()).hexdigest()
   if content_hash in self._seen_hashes:
       return  # skip duplicate
   ```

3. **Memory consolidation** — периодическое объединение похожих memories:
   ```python
   clusters = cluster_by_similarity(entries, threshold=0.85)
   for cluster in clusters:
       consolidated = summarize(cluster)
       replace(cluster, consolidated)
   ```

4. **TTL auto-pruning** — background cleanup expired entries

5. **Confidence-weighted ranking** — boost high-confidence memories в recall

**Тесты**: ~15 тестов

### WS6.5 — Search Controller Warm-Start + Cost-Aware Stopping

**Проблема**: Controller не принимает warm-start данные от TransferLearningManager. Stopping criteria не учитывают cost.

**Файлы**: `search/controller.py`, `search/stopping.py`

**Задачи**:

1. **Warm-start injection** — `SearchConfig.initial_evaluations: list[Evaluation]` для seed от transfer manager

2. **Cost-aware stopping** — `CostBudgetStopping(max_cost_usd: float)`:
   ```python
   def should_stop(self, state: SearchState) -> bool:
       return state.total_cost_usd >= self.max_cost_usd
   ```

3. **AND-logic composite** — `AllStoppingCriteria` (все должны сработать) в дополнение к `AnyStoppingCriteria`

4. **Batch parallelization** — `asyncio.gather()` для параллельной evaluation нескольких candidates

5. **Adaptive batch sizing** — увеличивать batch size если evaluation дешёвая:
   ```python
   batch_size = min(max_batch, budget_remaining // avg_eval_cost)
   ```

6. **Pareto tracking** — `SearchResult.pareto_front: list[Evaluation]` для multi-objective

**Тесты**: ~18 тестов

### WS6.6 — Bayesian Search Enhancements

**Проблема**: Фиксированная acquisition function, нет adaptive switching, warm-start не взвешивается.

**Файлы**: `search/strategies/bayesian.py`, `search/strategies/neural.py`

**Задачи**:

1. **Adaptive acquisition** — автоматический выбор EI vs UCB vs PI:
   ```python
   if exploration_ratio > 0.5:
       acq = UCB(beta=2.0)  # explore more
   else:
       acq = EI()  # exploit
   ```

2. **Weighted warm-start** — оценки из transfer learning взвешиваются по similarity:
   ```python
   weights = [similarity_score(current_run, hist_run) for hist_run in warm_data]
   ```

3. **Online hyperparameter tuning** — периодический re-fit GP hyperparameters

4. **Ensemble surrogate** — GP + Random Forest + Neural Network для robustness

5. **Uncertainty propagation** — передавать posterior uncertainty в acquisition function

**Тесты**: ~12 тестов

---

## 5. Phase 7 — Governance & Compliance

**Цель**: Governance 7.5→9.0, Security 5.5→9.0
**Оценка**: 3-4 недели

### WS7.1 — Governance Pass Dependencies + Caching

**Проблема**: Пассы не имеют явных зависимостей. Дорогие пассы (literature, causal) не кэшируются.

**Файлы**: `governance/pipeline.py`, `governance/passes/base.py`

**Задачи**:

1. **Pass dependency graph** — `GovernancePass.depends_on: list[str]`:
   ```python
   class RefutationPass(GovernancePass):
       depends_on = ["schema_pass", "quality_gate_pass"]
   ```
   Pipeline сортирует пассы топологически с учётом зависимостей.

2. **Cross-pass context** — `PassContext` shared dict между пассами:
   ```python
   class PassContext:
       results: dict[str, PassResult]
       shared_data: dict[str, Any]
   ```
   Пример: PII pass записывает найденные поля → equity pass знает какие поля маскировать.

3. **Pass result caching** — для idempotent passes (schema, budget):
   ```python
   cache_key = hash(pass_id + state_fingerprint)
   if cache_key in cache:
       return cache[cache_key]
   ```

4. **Async governance execution** — параллельный запуск независимых пассов:
   ```python
   independent_groups = topological_tiers(pass_graph)
   for tier in independent_groups:
       results = await asyncio.gather(*[p.run(state) for p in tier])
   ```

5. **Adaptive thresholds** — пороги зависят от domain:
   ```python
   if domain == "health":
       confidence_threshold = 0.99  # stricter
   elif domain == "fiscal":
       confidence_threshold = 0.95
   ```

**Тесты**: ~25 тестов

### WS7.2 — Governance Decision Persistence

**Проблема**: Governance decisions transient — после run теряются.

**Файлы**: новый `governance/decision_store.py`

**Задачи**:

1. **GovernanceDecisionRecord** model:
   ```python
   class GovernanceDecisionRecord(BaseModel):
       run_id: str
       pass_id: str
       decision: Literal["pass", "warn", "block"]
       severity: str
       reason: str
       timestamp: datetime
       evidence_refs: list[ArtifactRef]
   ```

2. **Persistence** через ArtifactStore: `governance.decisions.<run_id>` artifact

3. **Query API** — `get_decisions(run_id)`, `get_blocked_runs(since: datetime)`

4. **Audit integration** — каждый decision эмитит audit event

**Тесты**: ~10 тестов

### WS7.3 — Immutable Audit Trail

**Проблема**: Audit protocol есть, но нет гарантий immutability. Нет chain verification.

**Файлы**: `core/security/audit_protocol.py`, `core/security/audit_log_adapter.py`

**Задачи**:

1. **Hash chain** — каждый event содержит hash предыдущего:
   ```python
   event.prev_hash = sha256(previous_event.serialize())
   event.hash = sha256(event.serialize_without_hash())
   ```

2. **Chain verification** — `verify_audit_chain(events) -> bool`

3. **Append-only backend** — `AppendOnlyAuditStore`:
   - В памяти: append-only list
   - На диске: append-only file с fsync
   - Distributed: append-only topic (Kafka/Kinesis)

4. **Event versioning** — `AuditEvent.schema_version: str`

5. **Structured action parameters** — типизированные metadata вместо `dict[str, Any]`

6. **Replay/forensic** — `query_audit(run_id=..., event_type=..., since=...)` с index

**Тесты**: ~20 тестов (chain integrity, tamper detection, query, versioning)

### WS7.4 — Data Masking Pipeline

**Проблема**: PII check pass обнаруживает PII, но не маскирует.

**Файлы**: новый `core/security/data_masking.py`

**Задачи**:

1. **MaskingStrategy** protocol:
   ```python
   class MaskingStrategy(Protocol):
       def mask(self, value: str, field_type: str) -> str: ...
   ```

2. **Builtin strategies**:
   - `RedactMasking` — замена на `[REDACTED]`
   - `HashMasking` — SHA256 with salt (reversible с ключом)
   - `GeneralizeMasking` — "John Smith, 35" → "Person, 30-40"
   - `DifferentialPrivacyMasking` — Laplace noise для numeric

3. **MaskingPipeline** — apply masks по результатам PII pass:
   ```python
   pipeline = MaskingPipeline(strategy=HashMasking(salt=secret))
   masked_state = pipeline.apply(state, pii_findings)
   ```

4. **Integration** с governance pipeline — автоматическое маскирование после PII pass

**Тесты**: ~15 тестов

### WS7.5 — Quota Hardening

**Проблема**: Soft limits только предупреждают, не блокируют. Нет rate limiting.

**Файлы**: `core/security/quota_enforcer.py`, `core/security/tenant_quota.py`

**Задачи**:

1. **Soft limit enforcement modes** — `SoftLimitAction`: WARN, THROTTLE, BLOCK:
   ```python
   if usage > soft_limit:
       if action == THROTTLE:
           delay = (usage - soft_limit) / soft_limit * base_delay
           await asyncio.sleep(delay)
       elif action == BLOCK:
           raise QuotaSoftLimitError(...)
   ```

2. **Rate limiting** — token bucket per tenant:
   ```python
   class TokenBucketRateLimiter:
       def __init__(self, rate: float, burst: int): ...
       def acquire(self) -> bool: ...
   ```

3. **Quota reservation** — pre-allocate before expensive operations:
   ```python
   reservation = quota.reserve(estimated_cost)
   try:
       result = execute(...)
       reservation.commit(actual_cost)
   except:
       reservation.release()
   ```

4. **Hot-reload** — `QuotaRegistry.reload_config()` без перезапуска

**Тесты**: ~15 тестов

---

## 6. Phase 8 — Observability & Provenance

**Цель**: Observability 7.0→9.0, Reproducibility/Lineage 7.0→9.0
**Оценка**: 2-3 недели

### WS8.1 — SLO Metrics + Alerting

**Проблема**: Базовые метрики есть, но нет SLO, percentiles, alerting rules.

**Файлы**: `engine/metrics_protocol.py`, `engine/metrics_otel.py`

**Задачи**:

1. **Per-node histogram metrics**:
   ```
   scientist_node_duration_seconds{node_id, status, tier_index}  # histogram
   scientist_node_retry_count{node_id}                           # histogram
   scientist_cache_hit_ratio{node_id}                            # gauge
   ```

2. **Workflow state histogram**:
   ```
   scientist_workflow_state{run_id, state}  # PENDING, RUNNING, COMPLETED, FAILED
   ```

3. **Backpressure metrics**:
   ```
   scientist_tier_queue_depth{tier_index}   # gauge
   scientist_semaphore_wait_seconds         # histogram
   ```

4. **Resource metrics**:
   ```
   scientist_node_memory_bytes{node_id}     # gauge (via tracemalloc)
   ```

5. **Alerting rules** (Prometheus format):
   ```yaml
   - alert: ScientistNodeLatencyHigh
     expr: histogram_quantile(0.99, scientist_node_duration_seconds) > 300
     for: 5m
   - alert: ScientistBudgetExhaustion
     expr: scientist_budget_spent_usd / scientist_budget_limit_usd > 0.9
   ```

**Тесты**: ~12 тестов

### WS8.2 — Distributed Tracing (W3C TraceContext)

**Проблема**: Trace context не пропагируется в distributed runners (Ray/Temporal). `# TODO` в ray_runner.py.

**Файлы**: `engine/runner/ray_runner.py`, `engine/runner/temporal_runner.py`, `engine/trace_attributes.py`

**Задачи**:

1. **Trace context serialization** — inject/extract W3C TraceContext:
   ```python
   carrier = {}
   TraceContextTextMapPropagator().inject(carrier)
   # Send carrier with task payload
   ```

2. **Ray trace propagation**:
   ```python
   @ray.remote
   def execute_node(payload: bytes, trace_carrier: dict):
       ctx = TraceContextTextMapPropagator().extract(trace_carrier)
       with tracer.start_as_current_span("node.execute", context=ctx):
           ...
   ```

3. **Temporal trace propagation** — через activity headers

4. **Cross-service correlation** — единый trace_id от HTTP request → workflow → node → LLM call

5. **Span links** — связь parallel node spans с parent tier span

**Тесты**: ~10 тестов

### WS8.3 — LLM Cost Dashboard Metrics

**Проблема**: LLM cost tracking в `BudgetEnforcer`, но нет real-time export.

**Файлы**: `llm/budget_enforcer.py`, `engine/metrics_otel.py`

**Задачи**:

1. **Per-call cost metrics**:
   ```
   scientist_llm_cost_usd{model_id, provider, node_id}     # counter
   scientist_llm_tokens_total{model_id, direction}          # counter (input/output)
   scientist_llm_latency_seconds{model_id}                  # histogram
   ```

2. **Budget utilization gauge**:
   ```
   scientist_llm_budget_utilization{run_id}  # spent / limit
   ```

3. **Cost anomaly detection** — если один call > 3σ от mean cost, эмитить warning

4. **Real-time dashboard** — Grafana dashboard JSON template

**Тесты**: ~8 тестов

### WS8.4 — Provenance DAG Completeness

**Проблема**: Нет error activities, decision provenance, checkpoint tracking, data lineage.

**Файлы**: `provenance/run_dag.py`, `provenance/prov_json.py`

**Задачи**:

1. **Error activities** — `record_node_failure(node_id, error, traceback)`:
   ```python
   activity = Activity(id=f"fail:{node_id}", type=FAILURE, error_code=..., traceback=...)
   ```

2. **Governance decision provenance**:
   ```python
   record_governance_decision(pass_id, decision, evidence_refs)
   ```

3. **Checkpoint provenance** — link checkpoint artifacts в DAG

4. **Data lineage** — track какие state keys модифицировались какой нодой:
   ```python
   record_state_mutation(node_id, keys_added=["causal_graph"], keys_modified=["params"])
   ```

5. **Experiment metadata** — problem statement, hypothesis, research question в root entity

6. **Sync executor provenance** — добавить provenance DAG в `executor.py` (сейчас только в async)

**Тесты**: ~15 тестов

### WS8.5 — Replay Semantic Diff

**Проблема**: Replay diff — бинарное сравнение с tolerance. Нет structural similarity, distribution comparison.

**Файлы**: `replay/diff.py`

**Задачи**:

1. **Distribution comparison** — KS-test, Anderson-Darling для probabilistic outputs:
   ```python
   ks_stat, p_value = ks_2samp(original_dist, replayed_dist)
   ```

2. **Nested structure alignment** — recursive diff с reordered list matching

3. **Custom comparators** — registry per field type:
   ```python
   comparators = {
       "causal_graph": CausalGraphComparator(edge_tolerance=0.01),
       "distribution": DistributionComparator(ks_threshold=0.05),
   }
   ```

4. **Causality analysis** — какой diff на input вызвал diff на output

5. **Diff report artifact** — сохранять в CAS для audit

**Тесты**: ~12 тестов

---

## 7. Phase 9 — Testing & Reliability

**Цель**: Testing 6.0→9.0
**Оценка**: 3-4 недели

### WS9.1 — Node Unit Tests (CRITICAL)

**Проблема**: 35 builtin нод — 0 unit tests. Regression невозможно локализовать.

**Файлы**: `tests/unit/scientist/nodes/` (новая директория)

**Задачи**: Покрыть все категории нод:

1. **Data nodes** (3 ноды, ~15 тестов):
   - `test_build_data_snapshot.py` — happy path, missing fabric, empty data
   - `test_bind_foundry_inputs.py` — strict match, partial match, no match
   - `test_enrich_knowledge.py` — SKG available, SKG unavailable

2. **Planning nodes** (6+ нод, ~30 тестов):
   - `test_plan_policy_request.py` — complete state, missing fields, fallbacks
   - `test_build_execution_plan.py` — plan generation, method selection
   - `test_draft_policy_options.py` — drafter integration, mock agents
   - `test_run_preflight.py` — governance integration

3. **Causal nodes** (7 нод, ~35 тестов):
   - `test_build_literature_prior.py` — foundry available, foundry unavailable
   - `test_reconcile_causal_graph.py` — graph reconciliation
   - `test_run_causal_queries.py` — query execution, error handling
   - `test_run_causal_ensemble.py` — ensemble aggregation

4. **Simulate nodes** (4 ноды, ~20 тестов):
   - `test_run_simulation.py` — NaN detection, TEE attestation
   - `test_propagate_uncertainty.py` — uncertainty propagation
   - `test_run_distributional_analysis.py` — distribution analysis

5. **Governance nodes** (4 ноды, ~20 тестов):
   - `test_run_governance.py` — governance pass integration
   - `test_legal_check.py` — legal compliance
   - `test_data_plane_gate.py` — gate request/decision lifecycle

6. **Decide nodes** (2 ноды, ~10 тестов):
   - `test_build_decision_packet.py` — 20+ section aggregation, missing sections
   - `test_build_verified_policy_report.py` — report assembly

**Всего**: ~130 тестов

### WS9.2 — Governance Pass Isolated Tests

**Проблема**: 17 пассов без изолированных тестов.

**Файлы**: `tests/unit/scientist/governance/passes/` (новая директория)

**Задачи**: Для каждого pass:

1. **Happy path** — pass succeeds
2. **Blocker case** — pass blocks
3. **Warning case** — pass warns
4. **Missing data** — graceful handling
5. **Edge cases** — boundary values

Пассы: `confidence`, `cross_graph_evidence`, `equity`, `human_review`, `legal`, `literature_gate`, `normative_arbitration`, `pii_check`, `privacy`, `quality_gate`, `refutation`, `safety`, `schema`, `sutva_check`, `transportability_required`, `budget`

**Всего**: ~85 тестов (5 на pass × 17 пассов)

### WS9.3 — Workflow Integration Tests

**Проблема**: Workflow specs (default, causal_full, policy_verified) не тестируются изолированно.

**Файлы**: `tests/unit/scientist/workflows/`

**Задачи**:

1. **Default workflow** — end-to-end с mock nodes, verify DAG order
2. **Causal full workflow** — verify causal branch execution
3. **Policy verified** — verify legal verification flow
4. **Workflow selection** — test `select_workflow()` heuristics
5. **Builder** — test `build_execution_context()` с разными конфигурациями
6. **Error scenarios** — missing ports, invalid specs, timeout

**Всего**: ~30 тестов

### WS9.4 — Property-Based Tests (Hypothesis)

**Проблема**: Нет property-based tests для state serialization, condition parsing, governance.

**Файлы**: `tests/unit/scientist/property/` (новая директория)

**Задачи**:

1. **State roundtrip** — `∀ state: deserialize(serialize(state)) == state`
2. **Condition parsing** — `∀ expr: parse(unparse(parse(expr))) == parse(expr)`
3. **Checkpoint fingerprint** — `∀ spec: fingerprint(spec) == fingerprint(deepcopy(spec))`
4. **Governance ordering** — `∀ passes: sorted_by_deps(passes) satisfies all dependencies`
5. **Budget arithmetic** — `∀ ops: budget.spent + budget.remaining == budget.limit`
6. **Idempotency keys** — `∀ (state, params): compute_key(state, params) is deterministic`

**Всего**: ~25 тестов

### WS9.5 — API + Adapter Tests

**Проблема**: `api.py`, `adapters/foundry_bridge.py`, `adapters/fabric_bridge.py` — 0 тестов.

**Файлы**: `tests/unit/scientist/`

**Задачи**:

1. **api.py tests** (~10 тестов):
   - `run_experiment()` — happy path с mock context
   - Error handling — missing state, invalid params
   - Workflow selection integration

2. **Foundry bridge tests** (~10 тестов):
   - Port protocol compliance
   - Method invocation with mock foundry
   - Error handling — unavailable foundry

3. **Fabric bridge tests** (~10 тестов):
   - Data snapshot retrieval
   - Missing data graceful handling

**Всего**: ~30 тестов

### WS9.6 — Mutation Testing

**Проблема**: Нет mutation testing для governance passes — тесты могут быть слабыми.

**Задачи**:

1. Настроить `mutmut` или `cosmic-ray` для:
   - `governance/passes/` — все 17 пассов
   - `engine/retry.py` — retry logic
   - `engine/condition.py` — condition evaluation

2. **Target mutation score**: >80%

3. Усилить тесты по результатам mutation testing

---

## 8. Phase 10 — Scale & Multi-Tenancy

**Цель**: Distributed 6.0→9.0, Multi-tenancy 4.0→9.0
**Оценка**: 4-6 недель

### WS10.1 — Runner Backend Completion

**Проблема**: Ray/Temporal runners — структура есть, production-readiness — нет.

**Файлы**: `engine/runner/ray_runner.py`, `engine/runner/temporal_runner.py`

**Задачи**:

1. **Error handling strategy**:
   - Retryable errors (timeout, network) → retry with backoff
   - Fatal errors (bad input, OOM) → fail fast
   - Unknown errors → retry once, then fail

2. **Timeout propagation** — `NodeInvocation.timeout_s` → Ray timeout / Temporal activity timeout

3. **Result aggregation** — merge remote node outcomes back into state

4. **Health check** — ping runner backend before workflow start:
   ```python
   async def health_check(self) -> RunnerHealth:
       ...
   ```

5. **Graceful degradation** — если Ray/Temporal unavailable, fallback to local:
   ```python
   try:
       return await ray_runner.execute(...)
   except RunnerUnavailableError:
       logger.warning("Falling back to local execution")
       return await local_runner.execute(...)
   ```

6. **Serialization robustness** — version negotiation, error handling для deserialization failures

**Тесты**: ~25 тестов

### WS10.2 — Distributed Lock Production-Ready

**Проблема**: Redis lock есть, но нет Zookeeper/DynamoDB, нет health monitoring.

**Файлы**: `engine/locks/`

**Задачи**:

1. **DynamoDB lock backend** — для AWS deployments

2. **Lock health monitoring** — heartbeat thread для long-running locks:
   ```python
   class HeartbeatLockHandle:
       def __init__(self, lock: RunLockHandle, interval: float):
           self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
   ```

3. **Lock contention metrics**:
   ```
   scientist_lock_acquire_duration_seconds  # histogram
   scientist_lock_contention_total          # counter
   ```

4. **Stale lock detection** — автоматическое освобождение если heartbeat timeout:
   ```python
   if time_since_last_heartbeat > heartbeat_timeout * 3:
       force_release(lock_key)
   ```

**Тесты**: ~15 тестов

### WS10.3 — Multi-Tenant Isolation Verification

**Проблема**: Namespace + quota структура есть, но нет e2e verification.

**Файлы**: `core/security/namespace.py`, `core/security/quota_enforcer.py`

**Задачи**:

1. **Cross-tenant isolation tests** — два tenant-а не видят артефакты друг друга:
   ```python
   def test_tenant_isolation():
       store_a = NamespacedArtifactStore(base_store, "tenant_a")
       store_b = NamespacedArtifactStore(base_store, "tenant_b")
       ref = store_a.put(data)
       with pytest.raises(ArtifactNotFoundError):
           store_b.get(ref)
   ```

2. **Quota enforcement e2e** — tenant exceeds quota → workflow blocked

3. **Namespace collision prevention** — validate no colon injection:
   ```python
   def validate_tenant_id(tid: str):
       if ":" in tid:
           raise ValueError("Tenant ID must not contain ':'")
   ```

4. **Cell-level isolation** — within tenant, cells are isolated

5. **Concurrent tenant stress test** — 10 tenants × 5 concurrent runs → no cross-contamination

**Тесты**: ~20 тестов

### WS10.4 — Horizontal Scaling Infrastructure

**Задачи**:

1. **Worker pool** — `WorkerPool` protocol:
   ```python
   class WorkerPool(Protocol):
       async def submit(self, task: NodeTask) -> Future[NodeOutcome]: ...
       async def scale_to(self, workers: int) -> None: ...
       def current_capacity(self) -> int: ...
   ```

2. **Task routing** — по node type, resource requirements:
   ```python
   if node.requires_gpu:
       pool = gpu_pool
   else:
       pool = cpu_pool
   ```

3. **Auto-scaling signals** — queue depth → scale up/down

4. **Load balancing** — round-robin, least-connections, resource-aware

**Тесты**: ~15 тестов

---

## 9. Phase 11 — Remaining Subsystems

**Цель**: Autotune 6→9, Cross-graph 6.5→9, Backtesting 7.5→9, Nodes 7→9, LLM 8→9, DOE 7.5→9, PolicyVerified 7→9
**Оценка**: 4-6 недель

### WS11.1 — Autotune: Bayesian + Multi-Objective

**Файлы**: `autotune/calibration.py`, `autotune/claim_adjudication.py`

**Задачи**:

1. **Bayesian calibration** — интегрировать GP surrogate из search strategies:
   ```python
   from ..search.strategies.bayesian import BayesianSearchStrategy
   calibration_strategy = BayesianSearchStrategy(search_space)
   ```

2. **Multi-objective promotion** — Pareto-dominance вместо single metric:
   ```python
   class ParetoPromotionPolicy:
       def should_promote(self, candidate, champion) -> bool:
           return pareto_dominates(candidate.metrics, champion.metrics)
   ```

3. **Hyperband integration** — successive halving для resource-efficient tuning

4. **Trial deduplication** — content-hash based skipping

5. **Sensitivity analysis** — Sobol indices для meta-parameter importance

6. **Warm-start от historical configs**

**Тесты**: ~25 тестов

### WS11.2 — Cross-Graph Refactoring

**Проблема**: Monolithic compiler.py (1652 LOC), no caching, no fallback chains.

**Файлы**: `cross_graph/compiler.py`, `cross_graph/feedback.py`

**Задачи**:

1. **Extract adapters** — 4 pluggable gatherers:
   ```python
   class AcademicEvidenceGatherer(Protocol):
       async def gather(self, need: EvidenceNeed) -> list[EvidenceResult]: ...

   class DatasetEvidenceGatherer(Protocol): ...
   class LegalEvidenceGatherer(Protocol): ...
   class TransportEvidenceGatherer(Protocol): ...
   ```

2. **LRU caching** — `@functools.lru_cache` для SKGQuery и LegalKnowledgeGraph calls

3. **Fallback chains** — academic → dataset → proxy → manual:
   ```python
   for gatherer in [academic, dataset, proxy]:
       result = await gatherer.gather(need)
       if result.is_sufficient():
           break
   ```

4. **Conflict detection** — `ConflictReport` когда academic contradicts dataset

5. **Evidence synthesis** — consensus rules: "3+ sources agree → confidence += 0.1"

6. **Structured blocking reasons** — enum вместо strings

7. **Budget awareness** — max_queries, max_wall_time_sec

8. **Parallel assessment** — `asyncio.gather()` для независимых evidence needs

**Тесты**: ~20 тестов

### WS11.3 — Backtesting Enhancements

**Файлы**: `backtesting/evaluator.py`, `backtesting/trust_scorer.py`, `backtesting/orchestrator.py`

**Задачи**:

1. **Bootstrap confidence intervals** — CI для trust_score:
   ```python
   scores = [trust_scorer.score(resample(data)) for _ in range(1000)]
   ci_lower, ci_upper = np.percentile(scores, [2.5, 97.5])
   ```

2. **Calibration curves** — predicted probability vs actual frequency

3. **Forward-chaining CV** — time-series cross-validation:
   ```python
   for train_end in time_splits:
       train = data[:train_end]
       test = data[train_end:train_end+horizon]
       evaluate(model.fit(train), test)
   ```

4. **Distributional tests** — KS, Anderson-Darling goodness-of-fit

5. **Adversarial scenario discovery** — search для worst-case parameters

6. **IPW adjustment** — inverse probability weighting для selection bias

**Тесты**: ~20 тестов

### WS11.4 — Node Hardening

**Файлы**: `nodes/builtins/` (все 35 нод)

**Задачи**:

1. **Consistent parameter handling** — все ноды используют typed getters:
   ```python
   method = state.params.get("method", "default")
   ```

2. **Distributed tracing** — correlation ID в каждый NodeEvent:
   ```python
   event.attrs["trace_id"] = get_current_trace_id()
   ```

3. **Graceful degradation** — если optional dependency unavailable, degrade не fail:
   ```python
   try:
       result = ctx.foundry.execute(...)
   except FoundryUnavailableError:
       result = fallback_result()
       events.append(NodeEvent(level="warning", message="Foundry unavailable, using fallback"))
   ```

4. **State mutation guards** — pre/post assertions:
   ```python
   pre_keys = set(state.artifacts_index.keys())
   # ... execute ...
   assert new_keys.issuperset(pre_keys), "Node must not remove existing artifacts"
   ```

5. **Checkpoint markers** — опциональные intermediate checkpoints для длительных нод

**Тесты**: covered by WS9.1

### WS11.5 — LLM Subsystem Enhancement

**Файлы**: `llm/gateway_client.py`, `llm/factory.py`

**Задачи**:

1. **Full streaming** — SSE parsing для streaming responses:
   ```python
   async def stream_chat(self, messages, **kwargs) -> AsyncIterator[str]:
       async with session.post(url, json=payload) as resp:
           async for line in resp.content:
               if line.startswith(b"data: "):
                   yield parse_delta(line)
   ```

2. **Prompt caching** — semantic hash для system + user prefix:
   ```python
   cache_key = sha256(system_prompt + user_messages[:N])
   if cache_key in prompt_cache:
       return prompt_cache[cache_key]
   ```

3. **Function calling validation** — validate tool schemas against OpenAPI:
   ```python
   def validate_tools(tools: list[dict]) -> list[ValidationError]:
       ...
   ```

4. **Intelligent retry** — distinguish retryable (429, 5xx) from fatal (4xx)

5. **Fallback routing** — primary → secondary → tertiary model:
   ```python
   for client in [primary, secondary, fallback]:
       try:
           return await client.chat(messages)
       except (RateLimitError, ServiceUnavailableError):
           continue
   ```

6. **Connection pooling** — reuse aiohttp ClientSession

7. **Pre-request token estimation** — tiktoken-based

**Тесты**: ~20 тестов

### WS11.6 — DOE Enhancement

**Файлы**: `doe/designs.py`, `doe/analysis.py`

**Задачи**:

1. **Adaptive sampling** — sequential design с convergence checking

2. **Multi-output sensitivity** — PCA-based dimension reduction для vector outputs

3. **S2 interaction ranking** — визуализация 2nd-order Sobol indices

4. **Failure mode taxonomy** — `FailureType` enum: TIMEOUT, CONSTRAINT_VIOLATION, NUMERICAL_ERROR

5. **Parameter ranking stability** — leave-one-out importance assessment

**Тесты**: ~12 тестов

### WS11.7 — Policy Verified Enhancement

**Файлы**: `policy_verified/models.py`, `policy_verified/service.py`

**Задачи**:

1. **Real LLM integration** — replace MockFormalizerAgent/MockVerifierAgent с LLM-backed

2. **Incremental verification** — checkpoint markers для resumable adjudication

3. **Citation offset validation** — автоматическая проверка quote_offsets

4. **Source freshness tracking** — `last_verified_at`, `next_verification_due`

5. **Verifier disagreement escalation** — если rate > threshold → expert review queue

6. **Rate limiting** на LLM calls + timeout enforcement

**Тесты**: ~15 тестов

---

## 10. Сводная таблица всех workstreams

| WS | Название | Фаза | Подсистема | Новых тестов | Оценка усилий |
|----|---------|------|-----------|-------------|--------------|
| 5.1 | Circuit Breaker + Jitter | 5 | Engine | ~20 | 1д |
| 5.2 | Async Executor Hardening | 5 | Engine | ~15 | 2д |
| 5.3 | Checkpoint GC + Schema | 5 | Engine | ~12 | 1.5д |
| 5.4 | Budget Enforcement Middleware | 5 | Engine | ~15 | 2д |
| 5.5 | Fan-Out Async + Conditions | 5 | Engine | ~15 | 2д |
| 6.1 | Tool Loop Hardening | 6 | Agent | ~18 | 1.5д |
| 6.2 | Semantic Convergence | 6 | Agent | ~15 | 2д |
| 6.3 | Dynamic Agent Routing | 6 | Agent | ~20 | 3д |
| 6.4 | Persistent Memory Enhancement | 6 | Agent | ~15 | 2д |
| 6.5 | Search Warm-Start + Cost Stop | 6 | Search | ~18 | 2д |
| 6.6 | Bayesian Enhancements | 6 | Search | ~12 | 2д |
| 7.1 | Governance Dependencies + Cache | 7 | Governance | ~25 | 3д |
| 7.2 | Decision Persistence | 7 | Governance | ~10 | 1д |
| 7.3 | Immutable Audit Trail | 7 | Security | ~20 | 2.5д |
| 7.4 | Data Masking Pipeline | 7 | Security | ~15 | 2д |
| 7.5 | Quota Hardening | 7 | Security | ~15 | 2д |
| 8.1 | SLO Metrics + Alerting | 8 | Observability | ~12 | 2д |
| 8.2 | Distributed Tracing | 8 | Observability | ~10 | 2д |
| 8.3 | LLM Cost Dashboard | 8 | Observability | ~8 | 1д |
| 8.4 | Provenance Completeness | 8 | Provenance | ~15 | 2д |
| 8.5 | Replay Semantic Diff | 8 | Provenance | ~12 | 2д |
| 9.1 | Node Unit Tests | 9 | Testing | ~130 | 5д |
| 9.2 | Governance Pass Tests | 9 | Testing | ~85 | 3д |
| 9.3 | Workflow Integration Tests | 9 | Testing | ~30 | 2д |
| 9.4 | Property-Based Tests | 9 | Testing | ~25 | 2д |
| 9.5 | API + Adapter Tests | 9 | Testing | ~30 | 2д |
| 9.6 | Mutation Testing | 9 | Testing | — | 2д |
| 10.1 | Runner Completion | 10 | Distributed | ~25 | 3д |
| 10.2 | Distributed Lock Hardening | 10 | Distributed | ~15 | 2д |
| 10.3 | Tenant Isolation Verification | 10 | Multi-tenancy | ~20 | 2д |
| 10.4 | Horizontal Scaling | 10 | Distributed | ~15 | 3д |
| 11.1 | Autotune Bayesian+MO | 11 | Autotune | ~25 | 3д |
| 11.2 | Cross-Graph Refactoring | 11 | Cross-graph | ~20 | 3д |
| 11.3 | Backtesting Enhancements | 11 | Backtesting | ~20 | 2д |
| 11.4 | Node Hardening | 11 | Nodes | — | 2д |
| 11.5 | LLM Enhancement | 11 | LLM | ~20 | 2.5д |
| 11.6 | DOE Enhancement | 11 | DOE | ~12 | 1.5д |
| 11.7 | Policy Verified Enhancement | 11 | PolicyVerified | ~15 | 2д |

**Итого**: 37 workstreams, ~830+ новых тестов, ~80 человеко-дней

---

## 11. Зависимости между фазами

```
Phase 5 (Engine)
  ├── WS5.1 Circuit Breaker ← нет зависимостей (можно начинать первым)
  ├── WS5.2 Async Hardening ← нет зависимостей
  ├── WS5.3 Checkpoint GC ← нет зависимостей
  ├── WS5.4 Budget Middleware ← нет зависимостей
  └── WS5.5 Fan-Out Async ← WS5.2 (reuse async patterns)

Phase 6 (Agent + Search) ← Phase 5 (retry/budget infrastructure)
  ├── WS6.1 Tool Loop ← WS5.1 (circuit breaker)
  ├── WS6.2 Convergence ← нет зависимостей
  ├── WS6.3 Agent Routing ← WS6.1 (tool loop stability)
  ├── WS6.4 Memory ← нет зависимостей
  ├── WS6.5 Search Controller ← WS5.4 (budget)
  └── WS6.6 Bayesian ← WS6.5 (warm-start)

Phase 7 (Governance + Security) ← Phase 5 (audit infrastructure)
  ├── WS7.1 Pass Dependencies ← нет зависимостей
  ├── WS7.2 Decision Persistence ← WS7.1 (pass context)
  ├── WS7.3 Audit Immutability ← нет зависимостей
  ├── WS7.4 Data Masking ← WS7.1 (PII pass integration)
  └── WS7.5 Quota Hardening ← нет зависимостей

Phase 8 (Observability + Provenance) ← Phase 5 (metrics protocol)
  ├── WS8.1 SLO Metrics ← WS5.2 (backpressure signals)
  ├── WS8.2 Distributed Tracing ← Phase 10 WS10.1 (runner backends)
  ├── WS8.3 LLM Cost ← WS5.4 (budget)
  ├── WS8.4 Provenance ← WS7.2 (decision persistence)
  └── WS8.5 Replay Diff ← нет зависимостей

Phase 9 (Testing) ← Phase 5-8 (code to test)
  - Может идти параллельно с Phase 6-8
  - WS9.1-9.2 можно начинать сразу (тестируют существующий код)

Phase 10 (Scale) ← Phase 5 (engine), Phase 7 (security)
  ├── WS10.1 Runners ← WS5.1, WS5.2 (retry, async)
  ├── WS10.2 Locks ← нет зависимостей
  ├── WS10.3 Tenant Verification ← WS7.5 (quotas)
  └── WS10.4 Scaling ← WS10.1 (runners)

Phase 11 (Subsystems) ← Phase 5-8 (infrastructure)
  - Может идти параллельно после Phase 5
```

### Рекомендуемый порядок исполнения

```
Неделя 1-2:   Phase 5 (WS5.1-5.5) + WS9.1-9.2 параллельно
Неделя 3-5:   Phase 6 (WS6.1-6.6) + Phase 7 (WS7.1-7.5) параллельно
Неделя 6-7:   Phase 8 (WS8.1-8.5) + WS9.3-9.6 параллельно
Неделя 8-10:  Phase 10 (WS10.1-10.4)
Неделя 10-14: Phase 11 (WS11.1-11.7)
```

---

## 12. Критерии приёмки 9/10

### Engine Core (9/10)
- [ ] Circuit breaker с state machine (CLOSED/OPEN/HALF_OPEN) + тесты
- [ ] Jitter в exponential backoff + uniform distribution test
- [ ] Async cancellation handling (CancelledError не ретраится)
- [ ] Per-task state snapshots в parallel execution
- [ ] Semaphore timeout + workflow-level timeout
- [ ] State rollback savepoints per tier
- [ ] Budget enforcement middleware blocking over-budget nodes
- [ ] Threshold alerts at 80%/90%

### Checkpoint (9.5/10)
- [ ] GC policy удаляет старые checkpoints (max_checkpoints + max_age)
- [ ] Schema version validation при resume
- [ ] Lock retry loop с backoff
- [ ] Distributed checkpoint store через ArtifactStore protocol

### Workflow Composition (9/10)
- [ ] Async fan-out с TaskGroup
- [ ] Merge conflict resolution policy (FIRST_WINS/LAST_WINS/ERROR)
- [ ] Compound conditions (AND/OR)
- [ ] Aggregate operators (length, count, empty)

### Agent (9/10)
- [ ] Per-tool timeout + circuit breaker
- [ ] Adaptive max iterations (budget-aware)
- [ ] Embedding-based convergence detection
- [ ] Statistical significance для plateau (t-test)
- [ ] AgentRouter protocol с adaptive routing
- [ ] Fallback chain (LLM → Mock → Cached → FailSafe)
- [ ] Semantic search в persistent memory
- [ ] Memory deduplication + consolidation

### Search (9/10)
- [ ] Warm-start injection через SearchConfig.initial_evaluations
- [ ] Cost-aware stopping criterion
- [ ] AND-logic composite stopping
- [ ] Batch parallelization в controller
- [ ] Adaptive acquisition function switching
- [ ] Weighted warm-start по similarity
- [ ] Pareto front tracking в SearchResult

### Governance (9/10)
- [ ] Pass dependency graph с topological sort
- [ ] Cross-pass context sharing (PassContext)
- [ ] Pass result caching для idempotent passes
- [ ] Async parallel execution independent passes
- [ ] Decision persistence через ArtifactStore
- [ ] Adaptive thresholds по domain

### Security (9/10)
- [ ] Hash chain audit trail с verification
- [ ] Append-only audit backend
- [ ] Data masking pipeline (redact, hash, generalize, DP)
- [ ] Quota soft limit enforcement (WARN/THROTTLE/BLOCK)
- [ ] Token bucket rate limiting
- [ ] Quota reservation/release lifecycle
- [ ] Quota hot-reload

### Observability (9/10)
- [ ] Per-node histogram metrics (duration, retries, cache hit)
- [ ] Workflow state gauge
- [ ] Backpressure metrics (queue depth, semaphore wait)
- [ ] W3C TraceContext propagation в Ray/Temporal
- [ ] LLM cost counter/histogram per model
- [ ] Alerting rule definitions

### Provenance (9/10)
- [ ] Error activities в provenance DAG
- [ ] Governance decision provenance
- [ ] Checkpoint provenance links
- [ ] Data lineage (state key mutations per node)
- [ ] Sync executor provenance
- [ ] Distribution comparison в replay diff
- [ ] Custom comparators per field type

### Testing (9/10)
- [ ] 35 node unit test files (~130 тестов)
- [ ] 17 governance pass isolated test files (~85 тестов)
- [ ] Workflow integration tests (~30 тестов)
- [ ] Property-based tests (Hypothesis) (~25 тестов)
- [ ] API + adapter tests (~30 тестов)
- [ ] Mutation testing score >80% для governance passes
- [ ] Общее количество тестов: 1700+

### Distributed (9/10)
- [ ] Ray/Temporal runners с production error handling
- [ ] Timeout propagation node → runner activity
- [ ] Graceful degradation (fallback to local)
- [ ] Health check protocol
- [ ] DynamoDB lock backend
- [ ] Lock heartbeat monitoring
- [ ] Worker pool protocol с task routing

### Multi-Tenancy (9/10)
- [ ] Cross-tenant isolation verified (e2e тест)
- [ ] Namespace collision prevention (colon injection)
- [ ] Cell-level isolation within tenant
- [ ] Concurrent tenant stress test (10 tenants × 5 runs)
- [ ] Quota enforcement e2e (exceed → blocked)

### Autotune (9/10)
- [ ] Bayesian calibration через GP surrogate
- [ ] Multi-objective Pareto promotion
- [ ] Hyperband successive halving
- [ ] Trial deduplication
- [ ] Sensitivity analysis (Sobol indices)

### Cross-Graph (9/10)
- [ ] 4 pluggable evidence gatherer adapters
- [ ] LRU caching для external queries
- [ ] Fallback chains (academic → dataset → proxy)
- [ ] Evidence conflict detection
- [ ] Evidence synthesis rules
- [ ] Budget-aware querying

### Backtesting (9/10)
- [ ] Bootstrap CI для trust_score
- [ ] Calibration curves
- [ ] Forward-chaining time-series CV
- [ ] Distributional goodness-of-fit tests

### Nodes (9/10)
- [ ] Consistent typed parameter handling
- [ ] Distributed tracing в NodeEvent
- [ ] Graceful degradation для optional dependencies
- [ ] State mutation guards (pre/post assertions)

### LLM (9/10)
- [ ] Full SSE streaming
- [ ] Prompt caching (semantic hash)
- [ ] Fallback routing (primary → secondary)
- [ ] Intelligent retry (429/5xx vs 4xx)
- [ ] Connection pooling

### DOE (9/10)
- [ ] Adaptive sampling с convergence checking
- [ ] Multi-output sensitivity (PCA)
- [ ] Failure mode taxonomy

### Policy Verified (9/10)
- [ ] Real LLM integration (not mocks)
- [ ] Incremental verification with checkpoints
- [ ] Citation offset validation
- [ ] Source freshness tracking

---

> **При достижении всех критериев**: 264+ файлов, ~65K LOC, 1700+ тестов, 9.0+/10 по каждой из 19 подсистем.
