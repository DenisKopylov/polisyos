# Core / Common / Runtime Audit Remediation Plan

> Консолидированный план улучшения и исправления `polisyos.common`,
> `polisyos.core` и `polisyos.runtime` по итогам пакета аудитов:
> `SOTA Gap Analysis: core / common / runtime`,
> `Potential Bugs / Antipatterns / Cross-Module Problems`,
> `Security / Race / Leak / Correctness follow-up`.
> Created: 2026-04-11

---

## Цель

Довести `common`, `core` и `runtime` до состояния, в котором:

- закрыты все известные P0/P1 security, tenant-isolation и correctness defects;
- write-path runtime выдерживает повторные запросы, деградацию зависимостей и
  корректно завершает фоновые ресурсы;

- storage, serialization и signing больше не допускают silent corruption,
  data leaks и неопределенное поведение при race / crash / malformed input;

- статический анализ, тесты, observability и API contracts дают доказуемую
  эксплуатационную зрелость, а не только хорошую архитектурную основу;

- архитектурные решения и операционные процедуры закреплены в ADR, runbook и
  CI-ratchet, чтобы те же классы проблем не возвращались.

## Область действия

План покрывает:

- `src/polisyos/common/**`
- `src/polisyos/core/**`
- `src/polisyos/runtime/**`
- `src/polisyos/runtime/http/**`
- `tests/unit/common`, `tests/unit/core`, `tests/unit/runtime`, `tests/integration`,
  `tests/performance`

- `pyproject.toml`, runtime bootstrap и dependency wiring
- `ops/observability/prometheus`, `ops/observability/grafana`, `ops/policy`, runtime deployment scripts
- `docs/adr`, `docs/runbooks`, `docs/reference/operations`, migration guidance

## Ключевой вывод

База у системы сильная: protocol-driven архитектура, CAS, RFC 7807, OTel,
multi-layer auth, tenant routing, OPA и зрелый контрактный слой уже дают
редкую для Python-систем комбинацию breadth и дисциплины.

Но текущий потолок ограничивают не новые фичи, а четыре системных дефицита:

1. **Fail-open security paths**: WebSocket без auth, `/auth/me` с fixture
   fallback, `scope=None` как implicit allow, слабая tenant isolation в debug и
   отсутствие rate limiting / idempotency / mutation audit trail.
2. **Correctness under concurrency**: lazy-init races, async/SQLite locking,
   TOCTOU в WebSocket hub, глобальные singleton / cache races, неатомарные
   write paths и незавершенный lifecycle background-resources.
3. **Verification depth**: строгий `mypy` уже есть, но не хватает `py.typed`,
   dual checker, полноценного rule-set для Ruff, mutation/property/fuzz suites
   и целевых regression/benchmark gates на hot paths.
4. **Operational maturity**: нет SLI/SLO histograms, alert-ready metrics,
   полноценного access/mutation audit trail, ADR-пояснений для ключевых
   архитектурных решений, runbooks и ratchet-политики на новые изменения.

Главное следствие: **до закрытия Phase 0 и существенной части Phase 1 не
нужно расширять surface area новыми feature-флагами, endpoint-ами или
экспериментальными runtime-сценариями.**

---

## Принципы исполнения

1. **Fail closed by default**. Отсутствие identity, scope, redaction result,
   integrity proof или verified claims всегда трактуется как deny/error, а не
   как "временно пропустим".
2. **Каждый фикс получает regression test**. Для каждой гонки, утечки,
   serialization bug, auth bypass и corruption-path нужен воспроизводимый тест.
3. **Никаких silent degradations**. `except Exception: pass`, broad fallback и
   "warn и идем дальше" заменяются либо typed degraded outcome, либо hard fail
   с traceable event.
4. **Сначала контракты, потом рефакторинг**. Перед декомпозицией CAS, DI и
   runtime wiring нужно закрепить интерфейсы, startup/shutdown lifecycle и
   compatibility tests.
5. **Hot-path работа только с benchmark loop**. Любой change в RunIndex,
   timeline, lineage, CAS, serialization и metrics-пути проходит замер
   latency/memory до и после.
6. **Docs ship with code**. Rate limiting, idempotency, versioning, rotation,
   circuit breaker и storage refactor не считаются завершенными без ADR,
   runbook и operator-facing reference.
7. **Новые ratchets важнее локального удобства**. После исправлений должны
   появиться CI-барьеры, которые не дадут вернуть blanket `ignore`,
   `except Exception: pass` и undocumented runtime drift.

---

## Фазовый roadmap

| Phase | Цель                                                | Горизонт         | Выходной критерий                                                            |
| ----- | --------------------------------------------------- | ---------------- | ---------------------------------------------------------------------------- |
| 0     | Закрыть security/correctness blockers               | 5-7 рабочих дней | Нет открытых P0; все фиксы покрыты regression tests                          |
| 1     | Построить baseline надежности и проверки            | 1 спринт         | Есть fail-closed error model, test depth, static gates, SLI metrics          |
| 2     | Снять bottleneck-и производительности и архитектуры | 1-2 спринта      | Runtime hot paths ускорены, CAS/serialization safer, wiring упрощен          |
| 3     | Закрыть operational maturity и DX gaps              | 1 спринт         | Есть ADR, runbooks, diagrams, rotation/migration guidance, CI ratchets       |
| 4     | Долгосрочные refactor/optimization эпики            | после Phase 3    | Async CAS, полная DI, deeper batching и bulk APIs внедряются без regressions |

---

## Phase 0 — Security and correctness blockers

### WS-0A. Fail-Closed AuthN/AuthZ and Tenant Isolation

**Цель:** убрать все known fail-open paths на runtime perimeter.

**Основные поверхности:**

- `runtime/http/routes/review.py`
- `runtime/http/routes/auth.py`
- `runtime/http/routes/debug.py`
- `runtime/http/dependencies.py`
- `runtime/http/app.py`
- `runtime/http/authz_middleware.py`

**Задачи:**

1. Закрыть `SEC-1`: WebSocket `/live` обязан требовать verified identity и
   tenant scope на handshake; авторизация должна перепроверяться не только на
   connect, но и на message/subscription-level.
2. Закрыть `SEC-2`: `/auth/me` при отсутствии валидных claims должен возвращать
   `401` или `403`; fixture identity разрешается только под явным dev flag и не
   может быть runtime default.
3. Закрыть `SEC-3`: debug/run comparison обязан либо запрещать cross-tenant
   сравнение, либо требовать отдельный explicit capability вроде
   `runs.compare.cross_tenant`.
4. Закрыть `SEC-4`: `enforce_*_access()` и все downstream access guards должны
   переходить в fail-closed mode при `scope is None` или отсутствии identity.
5. Закрыть `G`: порядок middleware (`JWT -> CellRouter -> Authz`) фиксируется
   явной startup assertion; deny path не должен оставлять в `request.state`
   данные, которые downstream может принять за авторизованный контекст.
6. Добавить integration suite для цепочки `JWT -> CellRouter -> Authz -> route`
   и contract tests для WebSocket auth/per-message authorization.

**Критерии приемки:**

- анонимный `WebSocket` connect и HTTP доступ без claims отклоняются;
- `scope=None` больше не приводит к implicit allow;
- cross-tenant debug comparison без отдельного scope возвращает `403`;
- middleware-order test падает при любой случайной перестановке слоя auth.

### WS-0B. Runtime Write-Path Hardening

**Цель:** сделать mutation-path runtime безопасным при retry, деградации
зависимостей и остановке процесса.

**Основные поверхности:**

- `runtime/http/routes/control.py`
- `runtime/http/routes/runs.py`
- `runtime/http/services/control_plane_store.py`
- `runtime/http/services/task_runner.py`
- `runtime/http/services/control_worker.py`
- `runtime/http/services/review_collaboration.py`
- `runtime/http/app.py`
- `runtime/api.py`

**Задачи:**

1. Реализовать P0 gap по `rate limiting`: минимум per-tenant и per-endpoint
   лимиты для `POST` control/runs/feedback/evaluate и для дорогих live-stream
   endpoints.
2. Реализовать P0 gap по `idempotency`: поддержка `X-Idempotency-Key` для всех
   `POST` endpoints, создающих run/job/artifact side effects.
3. Реализовать P0 gap по `audit trail for mutations`: логировать actor, tenant,
   request_id, endpoint, resource id, operation, outcome и hash/version before /
   after там, где это применимо.
4. Реализовать P0 gap по `circuit breaker`: обернуть CAS, OPA и control-plane
   store в timeout + circuit-breaker policy, чтобы деградация одной зависимости
   не подвешивала весь API.
5. Исправить `B2`: синхронизировать lazy init `_get_control_service()` или
   перенести инициализацию в startup lifecycle.
6. Исправить `B3`: убрать небезопасную смесь `threading.Lock` и SQLite с
   `check_same_thread=False` в async-контексте; использовать async-safe
   serialization доступа или выделенный executor/worker.
7. Исправить `B8`: ограничить lifetime SSE-циклов, добавить heartbeat/timeout
   budget и корректный disconnect cleanup.
8. Исправить `F` и `B-NEW-12`: shared executors, background threads, review hub
   и `runtime/api.py` должны корректно завершаться и писать audit/manifest
   атомарно либо в рамках транзакции, либо через журнал/append-only log.

**Критерии приемки:**

- повтор одного и того же `POST` с тем же idempotency key не создает duplicate
  run/job/artifact;

- slow CAS/OPA/SQLite path перестает блокировать весь runtime и дает
  предсказуемый `503`/`504` problem response;

- при штатном shutdown не остаются orphan thread, live WebSocket connections и
  незавершенные background executors;

- mutation audit trail присутствует для control/runs/feedback/evaluate и
  доступен для compliance review.

### WS-0C. Crypto, Integrity, Redaction and Time Semantics

**Цель:** закрыть security/corruption классы багов в `common` и `core`.

**Основные поверхности:**

- `common/timestamps.py`
- `core/security/tee.py`
- `core/security/slsa/fulcio.py`
- `core/security/quota_enforcer.py`
- `core/artifacts/store.py`
- `core/artifacts/backends/s3_store.py`
- `runtime/http/services/artifact_inspector.py`

**Задачи:**

1. Исправить `SEC-5`: nonce verification в TEE attestation должен использовать
   equality, а не `startswith()`.
2. Исправить `SEC-6`: OIDC claims для Fulcio/SLSA должны читаться только после
   верификации подписи, issuer, audience и expiration.
3. Исправить `B-NEW-1`: redaction hook failure должен приводить к fail-closed
   outcome: либо полностью redacted preview, либо error без возврата сырого
   содержимого.
4. Исправить `B-NEW-2`: `record_storage_delta()` валидирует, что delta не
   позволяет искусственно уменьшать quota accounting без отдельного trusted
   release path.
5. Реализовать P1 gap по `integrity verification at read time`: CAS read path
   re-hash-ит blob и сверяет manifest/integrity перед возвратом данных.
6. Исправить P0/P1 gaps по `sign_on_put_policy="warn"` и broad catch в
   `s3_store`: signing/network/credentials errors не должны маскироваться как
   успешная запись нового manifest.
7. Реализовать input sanitization для artifact/CAS path inputs и manifest-origin
   data, чтобы исключить path traversal / unexpected file resolution.
8. Исправить `B1` и `B-NEW-8`: `ensure_utc()` и default factories во всех
   контрактах должны работать с aware UTC datetime и не подменять silently
   timezone semantics.

**Критерии приемки:**

- invalid nonce, forged OIDC token и redaction failure больше не пропускают
  данные в success path;

- corrupted blob детектируется на read-time и переводится в typed integrity
  error;

- quota accounting не допускает отрицательный delta bypass;
- naive datetime не трактуется молча как UTC.

### WS-0D. Common/Core Race, Cache and Lifecycle Hotfixes

**Цель:** убрать гонки, TOCTOU и зависания, уже подтвержденные аудитами.

**Основные поверхности:**

- `common/logger.py`
- `common/async_tools.py`
- `core/pipeline/dag.py`
- `core/governance/legal/backends/expr_ast.py`
- `core/trace/sink.py`
- `core/observability/tracer.py`
- `core/observability/metrics_parts.py`
- `runtime/http/services/review_collaboration.py`
- `core/artifacts/safe_tar.py`

**Задачи:**

1. Исправить `B4`: отправка WebSocket broadcast не должна работать по stale
   recipient list без защиты от TOCTOU; закрытые сокеты очищаются deterministically.
2. Исправить `B6`, `C6`, `B-NEW-11`: конфигурация logger trace context, JWKS
   cache и `get_tracer()/get_metrics()` перестают быть unsynchronized globals.
3. Исправить `B7`: `run_coro_sync()` получает timeout, shared executor и
   корректную cancellation/cleanup semantics.
4. Исправить `B-NEW-3`, `B-NEW-4`, `B-NEW-5`: убрать race на `_tail`, сделать
   AST cache bounded + synchronized и исправить comparison-chain logic.
5. Исправить `B-NEW-6`, `B-NEW-7`: file trace sink синхронизируется, а
   `CompositeTraceSink` изолирует сбой одного sink от остальных.
6. Исправить `safe_tar` / temp-dir / partial-key write cleanup issues из `F` и
   `R-NEW-*`, чтобы exceptions не оставляли leaked handles или half-written
   crypto material.

**Критерии приемки:**

- stress tests воспроизводят прошлые race conditions и подтверждают их закрытие;
- `run_coro_sync()` больше не зависает навсегда при hung coroutine;
- trace/metrics singletons создаются deterministically даже при конкурентном
  старте;

- temp dirs, tar handles и key files не остаются в partial state после failure.

---

## Phase 1 — Reliability baseline

### WS-1A. Error Semantics, Exception Translation and Resilience Policy

**Цель:** убрать raw 500, broad catch и silent failure classes на границе
`core -> runtime`.

**Основные поверхности:**

- `runtime/http/errors.py`
- `runtime/http/routes/control.py`
- `core/security/authz.py`
- `common/serialization.py`
- `core/artifacts/caching_store.py`
- `core/observability/_metrics_registry_base.py`
- `runtime/http/services/control_plane_store.py`
- CLI modules under `core/components/**`

**Задачи:**

1. Закрыть `C2` и `C3`: все `PolicyOSError`, `CrossTenantAccessError`,
   `TenantIsolationError`, `ExecutionProfileError`,
   `PolicyFlagForbiddenError` и соседние core-ошибки должны переводиться в
   typed RFC 7807 responses, а не утекать как raw `500`.
2. Реализовать structured error context propagation через service boundaries:
   request_id, tenant, run_id, artifact_id, dependency name и retry state
   должны сохраняться в exception/report envelope.
3. Закрыть gaps по silent serialization failures, dead-letter queue для failed
   control jobs и explicit degraded-mode policy для cache/metrics exporter.
4. Убрать `except Exception: pass` и слишком broad `except (...)` из authz,
   caching, CLI discovery/compliance paths и metric bootstrap.
5. Перевести suspicious `assert`-narrowing из production paths в explicit
   validation/typed errors.
6. Дочистить confirmed dead code/unreachable branches и сделать warn-ветки
   реально логирующими, а не молчаливыми.
7. Санитизировать error payloads от storage/backend SDK, чтобы диагностические
   сообщения не светили bucket names, regions, credential details и другие
   инфраструктурные подробности наружу.

**Критерии приемки:**

- runtime problem responses покрывают весь известный набор core exception types;
- нет новых silent failure branches без logging и explicit degraded contract;
- permanently failed jobs либо уходят в DLQ/escalation queue, либо требуют
  ручного подтверждения через documented operator flow.

### WS-1B. Static Analysis, Typing and Packaging Ratchet

**Цель:** поднять static analysis surface до dual-checker уровня без blanket
глушения ошибок.

**Основные поверхности:**

- `pyproject.toml`
- package roots under `src/polisyos`
- `runtime/http/**`

**Задачи:**

1. Реализовать `py.typed` marker для пакетов, которые должны быть typed при
   внешнем импорте.
2. Добавить `pyright` или `basedpyright` в CI как второй checker наряду с
   `mypy --strict`.
3. Убрать blanket `ignore_missing_imports = true`; оставить только точечные
   per-module overrides для реально нетипизированных зависимостей.
4. Закрыть 58 `type: ignore` в `runtime/http/**` через Protocol, TypedDict,
   narrowing helper functions, generics или обертки над внешними API.
5. Расширить Ruff rule-set минимум на `UP`, `S`, `PT`, `SIM`, `RUF`, `ANN`,
   `C4`, `TCH`, а также зафиксировать policy на новые ignores/noqa.
6. Вытащить на поверхность runtime/private-attribute coupling и concrete
   import-leaks, которые сейчас проходят только за счет typing escapes.

**Критерии приемки:**

- package type info виден внешним потребителям;
- dual checker работает в CI на целевом наборе пакетов;
- новые blanket ignore/`type: ignore` не проходят review без ADR-style
  justification;

- runtime/http имеет typed API surface без массового подавления ошибок.

### WS-1C. Verification Depth: Property, Mutation, Fuzz and Integration

**Цель:** сделать качество проверок соразмерным критичности модулей.

**Основные поверхности:**

- `tests/unit/common`
- `tests/unit/core`
- `tests/unit/runtime`
- `tests/integration`
- `tests/performance`

**Задачи:**

1. Поднять coverage для `common` с текущего baseline уровня до meaningful
   инженерного минимума: конфиг, logger, migrations, serialization, async tools.
2. Добавить property-based tests для CAS, registry, pipeline/DAG, migration
   purity и tenant access invariants.
3. Добавить fuzz/property tests для serialization и artifact inspection:
   циклические структуры, malformed JSON, большие вложенные объекты,
   redaction-hook failures.
4. Ввести mutation testing для приоритетных пакетов `common/core/runtime`,
   начиная с auth, artifact integrity, serialization и runtime dependencies.
5. Добавить integration tests для middleware chain, control-plane write paths,
   audit trail, rate limiting, circuit breaker, shutdown lifecycle и
   cross-tenant isolation.
6. Добавить WebSocket contract tests/snapshot tests для state transitions в
   `review_collaboration.py`.
7. Перенести benchmark discipline ближе к CI: hot-path pytest/performance suite
   для `CAS put/get`, `registry lookup`, `pipeline dispatch`, `RunIndex rebuild`,
   `timeline query`, `lineage traversal`.

**Критерии приемки:**

- каждый P0/P1 fix имеет regression test;
- есть отдельный suite для mutation/property/fuzz cases;
- performance regressions на hot paths становятся видимыми до merge;
- middleware и WebSocket стек проверяются как целая система, а не только по
  изолированным unit tests.

### WS-1D. Observability, SLI/SLO and Auditability

**Цель:** довести telemetry до operator-ready уровня.

**Основные поверхности:**

- `core/observability/**`
- `runtime/http/**`
- `ops/observability/prometheus/**`
- `ops/observability/grafana/**`
- cache/index services in runtime

**Задачи:**

1. Реализовать end-to-end distributed tracing across async/service boundaries,
   включая background tasks и control jobs.
2. Добавить endpoint histograms и service histograms с bucket strategy для
   `P50/P95/P99`, а также error-rate / saturation / queue-depth signals.
3. Добавить audit trail не только для мутаций, но и для data access: кто,
   когда и какой artifact/read path запросил.
4. Добавить cache effectiveness metrics: hit rate, staleness, rebuild duration,
   item count, eviction count для `RunIndexService` и related caches.
5. Убрать singleton-only tracer pattern в пользу provider/injected factory,
   удобной для unit tests.
6. Сделать metric exporter failures видимыми: logging, health endpoint,
   startup check и documented remediation.
7. Подготовить alert-ready dashboards/rules на circuit breaker open state,
   queue lag, cache rebuild storm, auth failures, integrity errors и rate-limit
   saturation.
8. Исправить context propagation helpers так, чтобы `contextvars` снимались в
   момент вызова, а не в момент декорирования; stale trace context не должен
   переиспользоваться между независимыми запросами.

**Критерии приемки:**

- для каждого runtime endpoint есть latency/error metrics;
- degraded dependency state и cache anomalies видны без чтения сырых логов;
- operator может ответить на вопросы "кто изменил", "кто читал", "почему
  запрос деградировал" из стандартного telemetry stack.

---

## Phase 2 — Performance, storage and architecture

### WS-2A. Storage, Serialization and Immutability Hardening

**Цель:** снизить риск corruption и упростить дальнейшую эволюцию CAS.

**Основные поверхности:**

- `core/artifacts/store.py`
- `core/artifacts/backends/**`
- `common/serialization.py`
- `common/migrations/**`
- `runtime/api.py`

**Задачи:**

1. Разбить `FileSystemCAS` (`A1`) на отдельные ответственности:
   blob storage, manifest lifecycle, signing/integrity, bulk import/export,
   observability/metrics.
2. Закрыть `C1`: runtime должен зависеть не от `FileSystemCAS` и `PutOptions`,
   а от узкого storage Protocol / service boundary.
3. Сделать serialization cycle-safe и предсказуемой: visitor/registry вместо
   mega-function, явная политика для unsupported types, bounded recursion depth.
4. Сделать migrations pure by contract: no input mutation, explicit copy
   semantics, idempotent tests на версии.
5. Убрать duplicate manifest creation window (`B5`) и неатомарные audit/manifest
   операции через lock/journal/transaction abstraction.
6. Исправить manifest reload/write amplification в `runtime/api.py`, чтобы bulk
   artifact logging не делал `N` полных reread/rewrite циклов.
7. Для SQLite-backed control store включить WAL/journaling и crash-consistency
   policy с documented recovery path.
8. Закрыть `C5`: единый serialization pathway для runtime responses и artifact
   metadata; `model_dump()`, `fast_json_dumps()` и related helpers должны
   подчиняться одному canonical contract.

**Критерии приемки:**

- storage read/write paths проходят crash-consistency и corruption tests;
- runtime перестает знать про конкретный CAS backend;
- migrations и serialization имеют явный immutability contract и property tests.

### WS-2B. Runtime Scalability and Hot-Path Performance

**Цель:** убрать алгоритмические bottleneck-и на росте нагрузки.

**Основные поверхности:**

- `runtime` index/timeline services
- lineage traversal surfaces
- `common/async_tools.py`
- `core/governance/legal/backends/expr_ast.py`
- metrics helper hot paths

**Задачи:**

1. Перевести `RunIndexService` с полного `O(n)` rebuild scan на incremental
   update / append-only index / event-driven refresh.
2. Добавить индекс или secondary structure для timeline вместо полного JSONL
   scan на каждый запрос.
3. В lineage traversal реализовать timeout budget, batching и bounded memory use.
4. Убрать pattern "new ThreadPoolExecutor per call" из `async_tools.py`;
   использовать shared executor policy.
5. Ввести bounded caches / memory limits для run cache, AST cache, lineage
   graph, telemetry aggregation caches.
6. Подготовить staged roadmap для async I/O в CAS: сначала адаптерный слой и
   shared executor, потом selective async rewrite hot paths.
7. Убрать micro-bottleneck-и из аудита: повторный `ast.parse`, сортировки в
   metric hot path, лишние list/set conversions, дорогие `repr()`-based sorts.

**Критерии приемки:**

- benchmark suite подтверждает снижение CPU/I/O overhead на индексации и
  timeline paths;

- memory use на long-running runtime instance ограничен и наблюдаем;
- shared executor/caching strategy не создает starvation и не растет без границ.

### WS-2C. Dependency Injection, Configuration and Lifecycle Architecture

**Цель:** убрать ручное wiring и import-time side effects, мешающие тестам и
замене backend-ов.

**Основные поверхности:**

- `runtime/http/app.py`
- `common/config.py`
- singleton/global registries under `common` and `core`
- governance and policy backends

**Задачи:**

1. Ввести минимальный typed DI/lifecycle container для runtime services:
   startup, shutdown, health state, dependency graph, test overrides.
2. Убрать `common/config.py` import-time side effects: env mutation, logging
   bootstrap и глобальные toggles должны происходить в явном bootstrap step.
3. Закрыть `C4`: единый registry env vars с ownership, defaults, validation,
   conflict detection и reference docs.
4. Свести singleton anti-patterns к provider/factory pattern с тестовыми
   override points.
5. Разорвать concrete/private coupling (`A2`, `A-NEW-3`) и зафиксировать
   официальные service APIs вместо доступа к private attributes.
6. Разобрать circular dependency risk и inconsistent contract optionality
   (`A-NEW-7`) через ADR + targeted refactor.
7. Убрать hardcoded magic numbers и глобальные mutable registries (`A5`,
   `A-NEW-4`) в конфигурируемые, документированные и синхронизированные
   структуры bootstrap/config layer.

**Критерии приемки:**

- runtime стартует и останавливается через явный lifecycle graph;
- config/load/logging поведение контролируется bootstrap layer, а не side-effect
  импортом модулей;

- backend substitution и test doubles не требуют monkeypatch глобальных singletons.

### WS-2D. API Maturity and Client Ergonomics

**Цель:** сделать HTTP surface зрелым для внешних клиентов и фронтенда.

**Основные поверхности:**

- `runtime/http/routes/**`
- OpenAPI generation and docs
- artifact download endpoints

**Задачи:**

1. Добавить `ETag`, `Cache-Control`, `Last-Modified` на immutable or
   cache-friendly resources.
2. Добавить content negotiation для artifact download/read endpoints, включая
   binary payloads.
3. Зафиксировать policy для versioning/deprecation: `Sunset`, deprecation docs,
   compatibility window и migration guide.
4. Добавить bulk endpoints для artifact/run retrieval, чтобы убрать N+1 со
   стороны фронтенда и ops clients.
5. Реализовать SSE backpressure/flow-control strategy вместо бесконечного
   hard-coded polling loop.
6. Дополнить OpenAPI response examples и lightweight link relations там, где это
   реально улучшает DX.

**Критерии приемки:**

- immutable endpoints используют cache headers;
- фронтенд и интеграционные клиенты могут работать через batch APIs;
- OpenAPI становится пригодным для client generation и contract review без
  ручного чтения кода.

---

## Phase 3 — Operational maturity, docs and ratchets

### WS-3A. ADR, Diagrams and Runbooks

**Цель:** закрепить решения, которые после исправлений станут частью platform
contract.

**Задачи:**

1. Написать ADR минимум по темам:
   rate limiting/idempotency,
   CAS abstraction boundary,
   runtime lifecycle/DI,
   versioning/deprecation policy,
   audit trail model,
   key rotation policy,
   async CAS roadmap.
2. Добавить архитектурные диаграммы:
   C4 container view, runtime request path, control-plane lifecycle,
   CAS/signing/integrity flow, observability topology.
3. Добавить или обновить runbooks:
   CAS/OPA outage,
   idempotency incident,
   mutation audit investigation,
   cache rebuild storm,
   key rotation,
   runtime graceful shutdown / stuck background worker,
   artifact corruption recovery.
4. Закрыть DX gaps: changelog, migration guide, logger docstrings / public
   operator-facing documentation.

**Критерии приемки:**

- operator и новый инженер могут понять архитектуру и аварийные процедуры без
  чтения исходников;

- новые platform decisions объяснены и привязаны к конкретным компромиссам.

### WS-3B. Security and Compliance Maturity

**Цель:** довести защитные механизмы до production-уровня beyond hotfixes.

**Задачи:**

1. Реализовать secret rotation для JWT signing keys, Ed25519 signing keys и
   смежных trust anchors.
2. Зафиксировать CSRF policy для режима, если/когда runtime использует cookies,
   а не только bearer tokens.
3. Подготовить retention/export policy для access и mutation audit trails.
4. Добавить compliance-oriented queries/reports для "кто читал / кто менял /
   когда / в каком tenant".

**Критерии приемки:**

- rotation и audit trail обслуживаются documented operational workflow;
- security posture не зависит от ручных ad-hoc действий отдельных инженеров.

### WS-3C. CI Ratchets and Release Gates

**Цель:** сделать улучшения самоподдерживающимися.

**Задачи:**

1. Ввести merge gates на:
   `mypy`, `pyright/basedpyright`, расширенный `ruff`, targeted `pytest`,
   mutation subset, performance smoke benchmarks, docs/link checks.
2. Добавить ratchet на новые `type: ignore`, `noqa`, `except Exception: pass`,
   undocumented public APIs и unbounded caches без eviction policy.
3. Привязать SLI/SLO и benchmark baselines к release review.
4. Добавить architecture-boundary tests на запрет runtime -> concrete CAS
   coupling и на bootstrap/lifecycle invariants.

**Критерии приемки:**

- новые изменения не могут тихо вернуть classes проблем из аудитов;
- release review использует те же gates, что и ежедневная разработка.

---

## Рекомендуемая последовательность PR-ов

1. `auth-fail-closed`
   WebSocket auth, `/auth/me`, `scope=None`, cross-tenant compare, middleware
   order assertions, exception translation foundation.
2. `write-path-hardening`
   rate limiting, idempotency keys, mutation audit trail, circuit breaker,
   graceful shutdown, control service/store fixes.
3. `crypto-integrity-hotfixes`
   nonce equality, verified OIDC claims, redaction fail-closed, quota delta,
   CAS read-time hash verification, S3 exception narrowing.
4. `race-cache-lifecycle`
   logger/JWKS/tracer races, DAG/AST fixes, trace sink sync, temp-dir/handle
   cleanup, shared executor/timeouts.
5. `static-gates-and-tests`
   `py.typed`, pyright, Ruff expansion, removal of `type: ignore`,
   property/fuzz/mutation/integration suites.
6. `observability-slo-audit`
   histograms, data access audit, cache metrics, alerting rules, exporter health.
7. `storage-and-runtime-architecture`
   CAS protocol boundary, FileSystemCAS decomposition, migration purity,
   WAL/journaling, bulk artifact logging fix.
8. `scaling-and-api-maturity`
   RunIndex/timeline optimization, bulk endpoints, cache headers, SSE
   backpressure, bounded caches, async CAS roadmap scaffolding.
9. `docs-adr-ratchets`
   ADR, diagrams, runbooks, changelog/migration guide, CI ratchet policies.

---

## Модульный фокус

| Модуль    | Немедленные действия                                                                          | Среднесрочные действия                                                       | Exit criteria                                                                       |
| --------- | --------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| `common`  | `ensure_utc`, `run_coro_sync`, logger race, serialization fail-closed, migration purity       | env registry, side-effect-free config bootstrap, visitor-based serialization | common перестает быть источником hidden globals и silent data drift                 |
| `core`    | TEE/Fulcio/quota fixes, integrity-at-read, AST/DAG races, trace sink safety                   | CAS decomposition, bounded caches, DI-friendly providers, rotation support   | storage/security/observability layer выдерживают crash/race/load without corruption |
| `runtime` | auth fail-closed, idempotency, rate limiting, audit trail, circuit breaker, lifecycle cleanup | bulk APIs, cache headers, SSE backpressure, incremental indexes, runtime DI  | API surface безопасен, предсказуем и operator-ready при росте нагрузки              |

---

## Матрица покрытия находок

| Группа находок                                                | Что закрываем                                                                                                                                                                     | Workstream                |
| ------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------- |
| Auth, tenant isolation, WebSocket auth                        | `SEC-1`, `SEC-2`, `SEC-3`, `SEC-4`, security gap по WebSocket auth, `G`, `C2`, `C3`                                                                                               | `WS-0A`, `WS-1A`          |
| Rate limiting, idempotency, mutation audit, graceful shutdown | P0 gaps по rate limiting / idempotency / audit trail / graceful shutdown, `B2`, `B3`, `B8`, `F`, `B-NEW-12`                                                                       | `WS-0B`, `WS-1C`, `WS-1D` |
| Crypto, integrity, redaction, quota                           | `SEC-5`, `SEC-6`, `B-NEW-1`, `B-NEW-2`, sign-on-put gap, integrity-at-read gap, CAS path sanitization gap, `B-NEW-9`                                                              | `WS-0C`, `WS-2A`, `WS-3B` |
| Time semantics and contract consistency                       | `B1`, `B-NEW-8`, `A-NEW-7`                                                                                                                                                        | `WS-0C`, `WS-2C`          |
| Serialization and migrations                                  | silent serialization failures gap, no circular-ref detection, `A4`, `O1`-`O5`, `B-NEW-10`, `A-NEW-1`                                                                              | `WS-1A`, `WS-2A`          |
| Static analysis and packaging                                 | no `py.typed`, 58 `type: ignore`, blanket `ignore_missing_imports`, no pyright, missing Ruff rules                                                                                | `WS-1B`, `WS-3C`          |
| Test depth                                                    | no mutation/property/fuzz/perf tests, common coverage gap, no middleware integration, no WS contract tests                                                                        | `WS-1C`, `WS-3C`          |
| Races, caches and globals                                     | `B4`, `B5`, `B6`, `B7`, `C6`, `B-NEW-3`, `B-NEW-4`, `B-NEW-6`, `B-NEW-7`, `B-NEW-11`, `R-NEW-*`                                                                                   | `WS-0D`, `WS-2B`, `WS-2C` |
| Error handling and dead code                                  | `A6`, `D`, `D-NEW-1`, `D-NEW-2`, `D-NEW-3`, `D-NEW-4`, `A-NEW-2`, `A-NEW-5`, `A-NEW-8`, `O-NEW-4`                                                                                 | `WS-1A`, `WS-3C`          |
| Storage and architecture coupling                             | `A1`, `C1`, no WAL, no connection pooling, no async CAS I/O, no lifecycle management                                                                                              | `WS-2A`, `WS-2B`, `WS-2C` |
| Observability gaps                                            | no distributed tracing E2E, no SLI/SLO metrics, no alert linkage, no cache effectiveness metrics, tracer singleton, `A-NEW-5`, `A-NEW-6`, `O-NEW-2`                               | `WS-1D`, `WS-2B`, `WS-3C` |
| Runtime scalability                                           | RunIndex full scan, timeline full scan, lineage no batching, unbounded caches, `O-NEW-1`, `O-NEW-3`                                                                               | `WS-2B`                   |
| API maturity                                                  | no cache headers, no content negotiation, no versioning/sunset, SSE backpressure gap, no bulk endpoints, no response examples, no HATEOAS                                         | `WS-2D`, `WS-3A`          |
| DI, config, docs and DX                                       | no DI container, singleton anti-patterns, `A2`, `A3`, `A-NEW-3`, `A5`, `A-NEW-4`, `C4`, `C5`, no ADR, no diagrams, no runbooks, no changelog/migration guide, undocumented logger | `WS-2C`, `WS-3A`, `WS-3B` |

---

## D1 Docs Impact Table

| D1 doc cluster               | Exact files                                                                                                                                                                                                       | Source of truth                                                                                                                                                        | Validation command or evidence                                                                                                                                                                                                                                                                          | Backlog / priority |
| ---------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------ |
| API contract reference       | `docs/reference/api/index.md`, `docs/reference/api/runs.md`, `docs/reference/api/control.md`, `docs/reference/api/artifacts.md`, `docs/reference/api/versioning.md`, `docs/reference/api/migration-guide.md`      | `schemas/runtime_api_v1.openapi.json`, `src/polisyos/runtime/http/routes/**`, `src/polisyos/runtime/http/services/**`, `src/polisyos/runtime/http/openapi_contract.py` | `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops/runtime/check_runtime_api_contract.py`                                                                                                                                                                                                 | none               |
| Operations and security docs | `docs/reference/operations/slo-error-budget.md`, `docs/reference/operations/observability-topology.md`, `docs/reference/security-compliance.md`, `docs/explanation/security-model.md`                             | `src/polisyos/core/security/**`, `src/polisyos/runtime/http/{fail_closed_middleware.py,security.py,dependencies.py,mutation_policy.py}`, `ops/observability/prometheus/**`           | `uv run pytest -q tests/unit/core/security/test_auth_middlewares.py tests/unit/core/security/test_router.py tests/unit/core/security/test_tenant_context.py tests/unit/runtime/http/test_runtime_api_authz.py tests/unit/runtime/http/test_access_invariants_properties.py tests/unit/runtime/http/test_runtime_api_observability.py` | none               |
| Runtime runbooks             | `docs/runbooks/runtime-api-outage.md`, `docs/runbooks/idempotency-incident.md`, `docs/runbooks/key-rotation.md`, `docs/runbooks/cas-opa-outage.md`, `docs/runbooks/runtime-graceful-shutdown-and-stuck-worker.md` | runtime/control lifecycle, authz/OPA fail-closed posture, key rotation flow, release closeout ledger                                                                   | `uv run polisyos-tools workspace acceptance-audit --summary docs/archive/reports/platform-acceptance.md --json-output docs/archive/reports/platform-acceptance.json`                                                                                                                                    | none               |
| Package boundary READMEs     | `src/polisyos/common/README.md`, `src/polisyos/core/README.md`, `src/polisyos/runtime/README.md`, `src/polisyos/runtime/http/README.md`                                                                           | package facades, module boundaries, code ownership, release-gate expectations                                                                                          | `uv run pytest -q tests/unit/common/test_serialization_properties.py tests/unit/common/test_timestamps.py tests/unit/core/artifacts/test_storage_protocol_boundaries.py tests/unit/runtime/http/test_runtime_api_contract_hardening.py`                                                                                     | none               |

D1 closure note: all required D1-L1 pages are present; no missing-page backlog
remains for the required output set.

## Definition of Done

Этот план считается выполненным, когда одновременно соблюдены все условия:

1. Нет открытых P0 и P1 из перечисленных аудитов.
2. Все Phase 0 изменения закрыты regression/integration tests.
3. `common/core/runtime` проходят `mypy`, `pyright/basedpyright`, расширенный
   `ruff` и целевой `pytest` suite без blanket suppressions.
4. Mutation/property/fuzz/performance suites существуют и встроены в review
   workflow хотя бы в target-срезах.
5. Runtime publish-ит SLI/SLO метрики, mutation/data access audit trail и
   dependency degradation signals.
6. CAS/storage/runtime lifecycle documented ADR + runbook + migration policy.
7. CI ratchets не дают вернуть fail-open, silent-pass и concrete-coupling paths.

---

## Исполнительская политика

Пока идет реализация этого плана:

- новые runtime endpoints не добавляются без явной проверки, что они не
  расширяют attack surface и не обходят idempotency/rate-limit/audit policy;

- изменения в `common` и `core`, влияющие на serialization, integrity, auth или
  observability, не merge-ятся без targeted tests;

- refactor уровня `FileSystemCAS`, DI container или async CAS не начинается,
  пока не зафиксированы контракты и baseline telemetry/benchmarks;

- каждый Phase 0/1 PR должен явно ссылаться на закрываемые finding IDs или
  gap families из этого документа.
