# План исправления и SOTA-улучшения Fabric

> Консолидированный remediation plan для `src/polisyos/fabric` по итогам
> SOTA gap analysis, code-level audit, unexplored-area audit и дополнительного
> concurrency/schema/cache review.
> Created: 2026-04-11

---

## Цель

Довести `polisyos.fabric` до уровня production-grade SOTA data fabric без
потери качества данных, воспроизводимости, provenance и downstream-надежности
для `scientist`, `scholar`, `lex` и world/materialization слоев.

План не является повтором аудитов. Это порядок исполнения, который:

- закрывает известные security, correctness, concurrency, lifecycle и
  data-integrity дефекты до расширения функциональности;

- превращает существующие находки в workstream-ы с acceptance criteria;
- задает технический фундамент для observability, lineage, schema governance,
  access governance, streaming, time travel, distributed execution и
  AI-augmented discovery;

- фиксирует, какие группы находок покрываются каждой фазой.

## Область действия

Основная область:

- `src/polisyos/fabric/**`
- `tests/unit/fabric/**`
- Fabric-facing документация в `docs/explanation/`, `docs/reference/`,
  `docs/contracts/`, `docs/quality/`, `docs/connectors/`

Подсистемы:

- connectors, registry, discovery, profiles, capabilities, connection pools;
- resilience: retry, circuit breaker, rate limiter, fallback;
- cache: CAS store, SQLite index, eviction, invalidation, prefetch;
- contracts, schema inference, schema evolution, validation middleware;
- transform, quality, type coercion, unit registries;
- federation planner/ranker/composer/resolver/evidence aggregation;
- data plane: cursor store, replay store, semantic diff, regression harness,
  streaming modes, watermarks;

- docs pipeline, claims pipeline, extraction, normalization, conflict handling;
- provenance export, evidence bundles, fact writer, world events;
- world store, DuckDB materialization, Kuzu export, projections, query API;
- storage adapters, retrieval service, catalog, PII/security masking.

Вне области этого документа:

- непосредственное исправление кода;
- повторный полный аудит всех 228 файлов;
- изменение архитектурных границ вне Fabric, кроме узких shared utilities в
  `polisyos.common` или `polisyos.core`, если они нужны для безопасного fix-а.

## Входные аудиты

План учитывает следующие группы находок:

- SOTA gaps: observability, lineage, governance, streaming, data quality,
  connector ecosystem, AI discovery, distributed execution, time travel,
  advanced testing, materialization intelligence.

- Code-level review: resource leaks, non-atomic writes, races, unbounded memory,
  Unicode destruction, silent failures, blocking async paths, fragile SQL/filter
  construction.

- Unexplored-area review: SPARQL/SQL/SoQL/ODSQL injections, timezone corruption,
  frozen dataclasses with mutable state, mutable transform state, report
  corruption, resilience bypasses, singleton races, ZIP bomb risk, Kuzu/DuckDB
  leaks, schema evolution mistakes, unsafe dynamic imports, URL/path issues.

- New critical/high/medium clusters: circuit-breaker/rate-limiter contention,
  prefetch heap mutation, cache eviction defects, schema merge data loss,
  NaN/Inf validation gaps, cache metrics corruption, clock-skew propagation,
  shared mutable connector state, silent exception pathways.

## Главный вывод

Fabric уже сильный архитектурно:

- 228 Python-файлов и чистый public facade;
- 14 HTTP/open-data connectors и profile-driven execution policy;
- CAS-backed cache, provenance, claims pipeline, world store;
- retry/circuit-breaker/rate-limiter/fallback primitives;
- federation strategies, DuckDB materialization, Kuzu export, replay и semantic
  diff.

Но потолок качества сейчас ограничен не количеством фич, а базовой
операционной надежностью:

1. **Security/data-integrity holes**: raw query interpolation, unsafe path/data
   traversal, unbounded decompression/read, unsafe transform loading.
2. **Inconsistent concurrency model**: async + threads + SQLite + singleton
   registries + mutable state используются без единого ownership/locking
   правила.
3. **Unbounded state**: resolver caches, audit logs, queues, prefetch jobs,
   circuit/rate-limiter maps и cache structures не всегда имеют TTL/LRU/maxsize.
4. **Temporal/numeric drift**: naive datetimes, local time, clock skew, NaN/Inf
   и non-finite quality values могут тихо портить результаты.
5. **Observability/lineage отстают от архитектуры**: provenance есть, но нет
   достаточных метрик, spans, column/value lineage и impact analysis.

Главное правило выполнения: **Phase 0 и Phase 1 обязательны до любых новых
SOTA-фич в default Fabric paths.**

---

## Принципы исполнения

1. **Stop-ship сначала.** Injection, data corruption, resource leaks,
   non-atomic persistence и permanent resilience failures имеют приоритет над
   новыми connectors/AI/streaming возможностями.
2. **Каждая находка получает судьбу.** Fix, accepted risk, explicit non-goal или
   отдельный follow-up с owner-ом и test coverage.
3. **No silent degradation.** `except Exception: pass`, debug-only swallow и
   hidden fallbacks должны стать typed degraded outcome, structured warning,
   retryable error или hard failure.
4. **UTC-aware time only.** Все persisted/compared datetimes в Fabric должны
   быть timezone-aware UTC.
5. **Finite values at trust boundaries.** Scores, TTLs, bounds, timestamps,
   quality metrics и resolver values должны reject/quarantine NaN/Inf.
6. **Shared state immutable or locked.** Singleton registries, connection
   handles, transform contexts, queue jobs, contract histories и catalog
   candidates не должны отдавать mutable snapshots без lock/owner semantics.
7. **Bounded by default.** Любая runtime map/queue/cache/log имеет TTL, LRU,
   maxsize, reservoir sampling или streaming sink.
8. **Fix includes test.** Race fixes требуют stress tests, injection fixes -
   malicious fixtures, data fixes - round-trip tests, performance fixes -
   benchmark/load evidence.
9. **SOTA строится поверх hardened primitives.** Observability, lineage,
   governance, streaming, time travel и distributed execution не должны обходить
   connector/cache/world foundation.

---

## Фазовый roadmap

| Phase | Тема                                               | Горизонт      | Exit criteria                                                                                                  |
| ----- | -------------------------------------------------- | ------------: | -------------------------------------------------------------------------------------------------------------- |
| 0     | Security и data-integrity containment              | 3-5 дней      | Нет открытых critical injection, unsafe query, timezone, serialization/export corruption findings              |
| 1     | Concurrency, lifecycle, bounded-state hardening    | 1-2 недели    | Pools, registries, cache, resilience, cursor/segment writes и background jobs проходят stress/regression tests |
| 2     | Schema, validation, semantic correctness           | 1-2 недели    | Schema merge/evolution, coercion, units, temporal/numeric validation и transforms deterministic/finite-safe    |
| 3     | Observability, lineage, governance baseline        | 2-3 недели    | Метрики/spans, column lineage, schema gates, access audit и classification hooks существуют                    |
| 4     | Quality, materialization, time travel intelligence | 2-3 недели    | Profiling/anomaly/drift, incremental materialization и point-in-time APIs готовы за стабильными contracts      |
| 5     | Connector ecosystem, streaming, scale-out          | 3-6 недель    | File/DB/GIS connectors, DLQ, event streaming, CDC, partitioned execution интегрированы                         |
| 6     | AI-augmented discovery и frontier UX               | после Phase 5 | Semantic search, metadata enrichment, entity resolution и KG reasoning gated/evaluated/observable              |

---

## Phase 0 - Security and Data-Integrity Containment

### WS-0A. Query/filter injection hardening

**Цель:** убрать все raw interpolation paths и централизовать безопасное
построение identifiers, literals, filters и URL path segments.

Поверхности:

- `connectors/sources/sparql.py`
- `connectors/sources/socrata.py`
- `connectors/sources/opendatasoft.py`
- `quality.py`
- `connectors/transform/filter.py`
- `connectors/sources/eurostat.py`
- `connectors/sources/world_bank.py`
- `connectors/sources/rest_json.py`

Задачи:

1. Создать Fabric safety module с helpers:
   `validate_sql_identifier()`, `quote_sql_identifier()`,
   `escape_sparql_literal()`, `escape_soql_literal()`,
   `escape_odsql_literal()`, `safe_path_segment()`, bounded `data_path`
   traversal.
2. Заменить `query.replace()` в SPARQL templates на allowlisted variables и
   escaped literals или endpoint-supported bindings.
3. Экранировать SoQL/ODSQL values и валидировать filter keys против schema или
   capability metadata.
4. Защитить `compute_quality_from_duckdb()` тем же identifier policy, который
   уже используется в `world_query.py`.
5. Заменить denylist для `DataFrame.eval()` на allowlisted AST evaluator или
   полностью запретить eval-style filters для untrusted inputs.
6. Percent-encode URL path segments для World Bank, Eurostat и похожих
   connectors; reject `..`, `/`, `\`, empty segments и control chars.
7. Ограничить глубину и ключи в REST JSON `data_path` traversal.

Acceptance criteria:

- malicious SPARQL/SQL/SoQL/ODSQL/URL/data_path fixtures покрыты тестами;
- unsafe identifiers дают typed validation errors;
- grep по `query.replace(`, raw `f"SELECT`, raw filter joins имеет только
  reviewed exceptions.

Покрывает:

- C1, C9, H1, H2, M2;
- URL/path/data_path cluster: World Bank, Eurostat, RestJson;
- часть source injection findings из C-NEW/M-NEW.

### WS-0B. Bounded input, decompression and unsafe dynamic loading

**Цель:** остановить OOM, ZIP bomb и manifest-driven RCE риски на входных
границах Fabric.

Поверхности:

- `connectors/sources/http_base.py`
- `connectors/sources/ckan_resource.py`
- `ingestion.py`
- `docs/backends/text_html.py`
- `connectors/sources/ckan_catalog.py`

Задачи:

1. Ввести `max_response_bytes`, `max_json_bytes`,
   `max_decompressed_bytes`, `max_rows` на уровне HTTP base и profiles.
2. Перевести большие HTTP bodies со слепого `await response.read()` на
   streaming/chunked read with limit.
3. Добавить ZIP guards: member count, decompression ratio, path traversal,
   total decompressed size.
4. Заменить arbitrary `transform_dag` Python loading на signed/allowlisted
   transform registry.
5. Если Python transform files остаются, требовать explicit local-trust flag и
   документировать RCE-risk.
6. Укрепить HTML parser, чтобы broken `<script>/<style>` не протекали в text.
7. Ограничить CKAN pagination max pages и repeated cursor detection.

Acceptance criteria:

- ZIP bomb fixtures fail fast до разархивации;
- oversized HTTP/JSON bodies rejected или streamed по профилю;
- untrusted manifests не могут импортировать произвольный Python by default;
- malformed HTML fixtures не протаскивают script/style payload.

Покрывает:

- H5, M21;
- `http_base` OOM risk, `rest_json` traversal, CKAN pagination issue;
- docs HTML parser findings.

### WS-0C. Serialization, provenance export and report round-trip

**Цель:** гарантировать, что persisted reports/provenance artifacts не
повреждаются и не дают hidden counter drift.

Поверхности:

- `fitness_report.py`
- `provenance/export_provo.py`
- `fabric/evidence.py`
- `claims/extraction.py`
- `claims/normalize.py`

Задачи:

1. Исправить `DataFitnessReport.from_dict()`: counters либо доверенно
   загружаются, либо recompute from metrics ровно один раз.
2. Перестать swallow metric deserialization failures на DEBUG; выдавать
   diagnostics/degraded metrics или strict failure.
3. Экранировать N-Quads literals: `"`, `\`, newline, carriage return, control
   chars.
4. Заменить `claim.citations[0]` на guarded primary citation selection,
   placeholder citation или per-claim quarantine.
5. Заменить прямой `payload["stable_id"]` на validated fields/typed errors.
6. Перевести русскую production docstring в `fabric/evidence.py` на английский
   для консистентности codebase.

Acceptance criteria:

- fitness report deserialize -> identical aggregate counters;
- corrupted metric entries visible в diagnostics;
- N-Quads проходит strict RDF parser на quote/newline fixtures;
- citation-less claim не валит весь batch.

Покрывает:

- C7, C8;
- original `claim.citations[0]` critical;
- M25, C-NEW-9, evidence `stable_id` finding.

### WS-0D. UTC-only temporal policy

**Цель:** убрать timezone-dependent corruption.

Поверхности:

- `connectors/types/_coercion_rules.py`
- `quality.py`
- `fitness_report.py`
- `connectors/federation/types.py`
- `connectors/contracts/validation_middleware.py`
- `connectors/quality/freshness.py`
- `fabric/manifest.py`

Задачи:

1. Добавить helper: `utc_now()`, `from_unix_timestamp_utc()`,
   `ensure_aware_utc()`, `parse_datetime_utc()`.
2. Заменить `datetime.utcnow()` и naive `datetime.fromtimestamp()`.
3. Нормализовать обе стороны freshness/staleness/quality comparisons.
4. Ввести clock-skew policy:
   future timestamps либо typed warning, либо validation failure, либо explicit
   safe clamp.
5. Обновить docs/contracts: Fabric timestamps are UTC-aware ISO strings.

Acceptance criteria:

- grep по `utcnow(` и `fromtimestamp(` в Fabric имеет только reviewed
  exceptions;

- UTC и non-UTC local env дают одинаковые coerced datetimes;
- tests покрывают naive, aware, future, skewed inputs.

Покрывает:

- C2, H11, M1;
- H-NEW-12, freshness clock-skew findings;
- CircuitOpenError clock-skew calculation.

---

## Phase 1 - Concurrency, Lifecycle and Bounded State

### WS-1A. Deterministic resource lifecycle

**Цель:** закрывать pools, sessions, DB handles и background jobs
детерминированно.

Поверхности:

- `connectors/_registry_lifecycle.py`
- `connectors/pool.py`
- `connectors/cache/_store_index.py`
- `connectors/cache/store.py`
- `io/db.py`
- `world/materialize/kuzu.py`
- `connectors/sources/http_base.py`
- `connectors/reference/rest_json.py`

Задачи:

1. Заменить fire-and-forget unregister cleanup на explicit async shutdown API и
   safe sync bridge для no-running-loop contexts.
2. В `ConnectionPool.close_all()` брать lock до изменения `_closed`; сделать
   close/release idempotent per handle.
3. Добавить context-manager/close ownership для `CacheIndex`,
   `ConnectorCacheStore`, `SimulationDB`, DuckDB/Kuzu wrappers.
4. Закрывать Kuzu `Database`/`Connection`, избегать двух simultaneous objects
   на один path.
5. Трекать prefetch requeue/background tasks и cancel/drain в `stop()`.
6. Убрать `_get_session()` race через lock per handle или session ownership в
   pool.
7. Убрать new `ClientSession` per request в reference connectors.

Acceptance criteria:

- tests не оставляют aiohttp sessions, DuckDB locks, Kuzu handles, pending
  tasks после unregister/shutdown;

- concurrent close/release stress без double-close;
- SimulationDB/Kuzu paths можно открыть, закрыть, удалить, переоткрыть.

Покрывает:

- original critical pool cleanup и CacheIndex leak;
- C3, H4, H16, H17, L10;
- C-NEW-6, H-NEW-6.

### WS-1B. Atomic persistence for cursors, segments and registries

**Цель:** сделать mutable on-disk indexes безопасными при concurrent writers и
crash recovery.

Поверхности:

- `data_plane/cursor_store.py`
- `world/store/segments.py`
- `connectors/contracts/registry.py`
- `connectors/cache/_store_index.py`
- `world/materialize/duckdb.py`
- `world/materialize/projections.py`

Задачи:

1. Защитить cursor store in-memory mutation lock-ом и atomic write protocol.
2. Заменить append-only segment index на lock-protected writer,
   transactional SQLite index или atomic manifest directory model.
3. Использовать temp file in same dir, `os.replace`, file fsync и parent dir
   fsync для registry JSON writes.
4. Убирать orphan tmp files при startup и round-trip validate schemas перед
   принятием.
5. `_load_applied_segments()` должен fail closed или mark materialization
   uncertain, а не возвращать empty dict на любую ошибку.
6. Public projection update APIs должны начинать transaction, если вызываются
   вне `apply_world_segment()`.

Acceptance criteria:

- multi-thread/multi-process tests не теряют cursor updates и не corrupt JSONL;
- crash-in-middle оставляет previous valid или next valid state;
- materializer не re-applies all segments silently после read failure.

Покрывает:

- original critical cursor/segment findings;
- M14, M15;
- registry atomic-write/corrupt-load findings.

### WS-1C. Resilience primitives under contention

**Цель:** сделать circuit breaker и rate limiter корректными при concurrent
probes, retry, backoff и cancellation.

Поверхности:

- `connectors/resilience/circuit_breaker.py`
- `connectors/resilience/rate_limiter.py`
- `connectors/resilience/fallback.py`
- `connectors/resilience/__init__.py`
- `connectors/sources/sdmx_source.py`

Задачи:

1. Сделать HALF_OPEN slot acquisition/release token-based и lock-protected.
2. Запретить underflow и release without ownership.
3. Убрать TOCTOU: `can_attempt()` должен возвращать lease или state must be
   rechecked at execution boundary.
4. Token-bucket deficit calculation и decrement должны быть одной atomic
   lock operation; negative tokens невозможны.
5. Разделить metrics: cumulative throttle sleep и wall-clock acquire duration.
6. Определить reset semantics для `_blocked_until` после successful recovery.
7. Ограничить per-wrapper CB/rate-limiter maps через LRU/TTL.
8. Все SDMX/HTTP calls должны идти через resilience layer, кроме documented
   tested bypasses.
9. Fallback должен сохранять original primary error, даже если last strategy
   тоже упала.

Acceptance criteria:

- half-open contention tests не могут permanently lock circuit;
- rate-limiter stress никогда не дает negative bucket или request avalanche;
- SDMX transient 500/502/503 retry behavior покрыт тестом;
- fallback diagnostics сохраняют primary + fallback errors.

Покрывает:

- C-NEW-1, C-NEW-2;
- H-NEW-1, H-NEW-2, H-NEW-3, H-NEW-4;
- original unbounded resilience dicts, H3, fallback masking.

### WS-1D. Shared mutable state and wrapper safety

**Цель:** убрать accidental shared mutation из frozen models, registries,
connector instances и wrappers.

Поверхности:

- `connectors/base.py`
- `connectors/transform/pipeline.py`
- `connectors/transform/aggregator.py`
- `connectors/discovery.py`
- `connectors/types/_units_registry.py`
- `connectors/contracts/validation_middleware.py`
- `connectors/_registry_lifecycle.py`
- `connectors/registry_core_parts.py`
- `connectors/components.py`
- `connectors/sources/wvs.py`
- `catalog/resolver_fast_lane.py`

Задачи:

1. Заменить mutable fields в frozen dataclasses на tuple,
   `MappingProxyType`, frozen pydantic models или explicit owner objects.
2. Если state должен быть mutable, снять `frozen=True` и документировать lock
   ownership.
3. `AggregationTransform` должен хранить inferred temporal context per
   execution или immutable after construction.
4. Добавить locks в `ConnectorDiscovery`, `UnitRegistry`, `DimensionRegistry`,
   `ContractValidatingProxy`.
5. Сделать wrapper application idempotent under lock.
6. На unregister чистить `_contract_wrappers`, `_cache_wrappers` и connector
   references.
7. Перевести eager `_BUILTIN_COMPONENTS` import на lazy discovery.
8. Убрать request-time мутацию shared WVS maps и catalog candidates.
9. Возвращать immutable snapshots из contract history и resolve paths.

Acceptance criteria:

- concurrent wrapper application не double-wrap;
- singleton construction thread-race stable;
- external callers не могут mutate TransformContext/ConnectionHandle state;
- unregister освобождает wrappers и connector refs.

Покрывает:

- C4, C5, C6;
- H6, H7, M7, M11;
- original wrapper TOCTOU/leak;
- WVS/catalog mutable state findings.

### WS-1E. Bounded memory for cache, prefetch, audit and resolver state

**Цель:** у любой runtime state structure должен быть retention limit.

Поверхности:

- `connectors/cache/prefetch.py`
- `connectors/cache/_store_core.py`
- `connectors/cache/policy.py`
- `connectors/cache/invalidation.py`
- `connectors/federation/composer.py`
- `connectors/contracts/validation_middleware.py`
- `retrieval/service.py`

Задачи:

1. `PrefetchJob` сделать frozen или перестать хранить mutable object внутри
   heap entry; retry создает новый job.
2. `_queue_keys` защищать lock-ом; `cache_key=None` должен иметь dedupe/limit
   semantics.
3. Починить size-bounded eviction: transactional recompute total size или batch
   delete candidates.
4. Исправить `SmartExpiryPolicy` для future `date_end` и streaming windows.
5. FULL federation audit mode должен stream to sink или иметь max entries +
   truncation metadata.
6. `_resolution_cache` и revision-keyed caches получают LRU/TTL.
7. Retrieval local indexes/promotion queues получают maxsize/eviction.
8. Invalidation scan должен реально использовать file-based branch и не leak
   handle при acquisition failure.

Acceptance criteria:

- cache max-size contract тестируется;
- prefetch stop не оставляет pending requeue tasks/duplicates;
- FULL audit mode не OOM на large conflict set;
- resolver/cache memory growth bounded tests есть.

Покрывает:

- C-NEW-3, C-NEW-4, C-NEW-5, C-NEW-6;
- H-NEW-5, H-NEW-6, H-NEW-8;
- original unbounded merge log, resilience dicts, H12.

---

## Phase 2 - Schema, Validation and Semantic Correctness

### WS-2A. Schema merge, bounds and contract validation

**Цель:** сделать schema merge/evolution математически корректными и
governance-safe.

Поверхности:

- `connectors/contracts/_schema_field.py`
- `connectors/contracts/evolution.py`
- `connectors/contracts/contract.py`
- `connectors/contracts/registry.py`
- `connectors/contracts/_inference_engine.py`
- `connectors/contracts/_inference_validation.py`
- `catalog/contract.py`
- `catalog/binding.py`

Задачи:

1. Исправить allowed-values merge: empty set является значением, а не missing.
2. Reject NaN/Inf и invalid min/max bounds.
3. Mixed bound changes должны фиксировать и relaxing, и breaking стороны.
4. Removing precision/scale constraints классифицировать как relaxation, если
   тип не narrowing в другом месте.
5. Ужесточить contract ID regex: no trailing dots, consecutive dots,
   ambiguous separators.
6. `expected_row_count_range` валидировать как exactly two ordered values.
7. Нормализовать units одинаково в catalog contracts и schema bindings.
8. Исправить semantic inference ordering: `[0,1]` ratio не percentage,
   years/postal codes/IDs не count by default.
9. Добавить round-trip validation для loaded schemas/registry records.

Acceptance criteria:

- property-based tests покрывают empty allowed sets, NaN/Inf, infinity, mixed
  bounds, precision removal, categorical constraints;

- schema evolution tests корректно marked major/minor/patch impact;
- invalid IDs/ranges fail at model construction.

Покрывает:

- C-NEW-7, C-NEW-8;
- H-NEW-10, H-NEW-11;
- M3, M4, M5, M6;
- catalog unit/version findings.

### WS-2B. Finite numeric and quality-score boundary

**Цель:** не пропускать non-finite values в quality, federation, transforms,
freshness, projections.

Поверхности:

- `connectors/federation/resolver.py`
- `connectors/federation/evidence_aggregation.py`
- `connectors/federation/ranker.py`
- `connectors/transform/harmonizer.py`
- `connectors/quality/freshness.py`
- `connectors/quality/completeness.py`
- `quality.py`
- `world/materialize/projections.py`

Задачи:

1. Добавить Fabric-local finite validators для scores, probabilities, TTLs,
   bounds, timestamps, resolver values.
2. Median/mean resolvers должны handle all-NaN/mixed-NaN через quarantine или
   typed no-resolution outcome.
3. Quality scores вне `[0,1]` reject/clamp по явной политике до aggregation.
4. Harmonizer должен сохранять pandas missing values, не превращать NaN в
   строку `"nan"`.
5. `retrieved_at is None` обрабатывать безопасно в projections.
6. Completeness no-field-match отличать как not-applicable, не 0% complete.
7. `confidence` в completeness/reporting сделать configurable.
8. All-NaN imputer cases выдавать validation outcome, не silent no-op.

Acceptance criteria:

- NaN/Inf fuzz tests покрывают federation, quality, transform, projection;
- все quality scores finite/range-checked на public boundary;
- null semantics сохраняются через harmonization.

Покрывает:

- C-NEW-10;
- H-NEW-13, H-NEW-14, H-NEW-15;
- H13, M19, L6, imputer finding.

### WS-2C. Type coercion, units, temporal and canonical IDs

**Цель:** сохранить multilingual identifiers, precision и locale semantics.

Поверхности:

- `claims/canonicalize.py`
- `connectors/types/_coercion_rules.py`
- `connectors/types/_units_base.py`
- `connectors/types/_units_registry.py`
- `connectors/types/temporal.py`
- `connectors/types/connector_types.py`
- `claims/backends/regex_numeric_v1.py`

Задачи:

1. Заменить ASCII-destructive canonicalization на Unicode-preserving NFKC,
   optional transliteration/confusable checks и collision detection.
2. Добавить locale-aware decimal parsing для `1.000,50`.
3. Empty string в boolean coercion трактовать как missing/invalid by policy,
   не automatic `False`.
4. Исправить affine unit inverse conversion.
5. Улучшить exchange-rate precision и lock coverage для forward/inverse rates.
6. Уточнить ounce conversion factor.
7. Уменьшить greedy temporal keyword matching.
8. Поддержать scientific notation в numeric claim regex.
9. Избегать public classes, shadowing Python builtins, где API позволяет.

Acceptance criteria:

- Unicode fixtures: accents, Cyrillic, non-Latin, collisions, stable round trip;
- locale decimal и scientific notation tests pass;
- unit round-trip tests покрывают affine и high-precision conversions.

Покрывает:

- original Unicode canonicalization;
- M9, M12, L1, L2, L4, L5;
- claims numeric/decimal parser findings.

### WS-2D. Transform pipeline and capability correctness

**Цель:** сделать pipeline execution, transforms и capability checks
детерминированными.

Поверхности:

- `connectors/transform/pipeline.py`
- `connectors/transform/normalizer.py`
- `connectors/transform/harmonizer.py`
- `connectors/transform/validator.py`
- `connectors/capabilities.py`
- `connectors/validation.py`

Задачи:

1. `CompiledPipeline.execute()` должен использовать topological
   `execution_order`, не insertion order.
2. `NormalizationTransform` должен сохранять deterministic column order при
   `drop_unmapped=True`.
3. Empty harmonizer mappings и empty validator rules валидировать по strictness
   mode.
4. Capability decorators должны реально прокидывать custom `error_message`.
5. `_is_protocol_stub` заменить на inspect-based или explicit marker logic.
6. `hasattr(validation, "valid")` заменить на `isinstance(ValidationResult)` или
   bounded protocol.

Acceptance criteria:

- DAG pipeline tests fail before/pass after topological execution;
- transform outputs имеют stable order across processes;
- capability tests assert custom messages и real implementation detection.

Покрывает:

- H8, H9, H10;
- M8 и transform no-op findings;
- original duck typing finding.

---

## Phase 3 - Observability, Lineage and Governance Baseline

### WS-3A. Fabric observability and SLO/SLI

**Цель:** перестать эксплуатировать Fabric вслепую.

Поверхности:

- `connectors/**`
- `connectors/resilience/**`
- `connectors/cache/**`
- `connectors/federation/**`
- `data_plane/**`
- `world/materialize/**`
- `retrieval/**`
- `quality.py`
- `core/observability/**`

Задачи:

1. Утвердить Fabric telemetry contract:
   trace names, metric names, labels, cardinality limits, error taxonomy.
2. Добавить OpenTelemetry spans для connector fetch, retry attempts, circuit
   transitions, rate limiter acquire, cache get/put/evict/invalidate, transform
   stages, federation planning/composition, data-plane execution, segment append,
   materialization, query.
3. Экспортировать counters/histograms/gauges:
   connector latency p50/p95/p99, rows/s, bytes/s, error rates, retry counts,
   circuit state, rate-limit wait, cache hit/miss/stale/evict, prefetch backlog,
   materialization lag, segment count, quality score, freshness age, lineage
   graph size, DLQ count.
4. Сначала исправить cache metrics: atomic hit/miss и no double-miss.
5. Собрать `HealthStatus` aggregation в Fabric health snapshot.
6. Ввести SLOs:
   dataset freshness, connector success rate, cache hit ratio, query latency,
   materialization lag, replay determinism, lineage completeness.
7. Добавить alert hooks без жесткой зависимости от конкретного backend.

Acceptance criteria:

- tests могут assert in-memory meter/tracer;
- cache hit ratio correct under concurrency;
- health report показывает connector/cache/world/data-plane состояние и reasons.

Покрывает:

- SOTA observability gap;
- original cache counter race;
- H-NEW-7 и cache metrics cluster.

### WS-3B. End-to-end lineage and impact analysis

**Цель:** расширить evidence-level provenance до column/value lineage от raw
source до query result.

Поверхности:

- `provenance/**`
- `connectors/transform/**`
- `data_plane/**`
- `world/store/**`
- `world/materialize/**`
- `claims/**`
- `retrieval/**`

Задачи:

1. Определить lineage model:
   source dataset, source field, transform stage, output field, materialized
   table/column, claim field, world fact, query result field.
2. Добавить lineage emitters для filter, normalizer, harmonizer, imputer,
   aggregator, validator.
3. Привязать lineage refs к evidence bundles, world events, fact segment
   manifests.
4. Добавить APIs:
   `trace_value_origin()`, `trace_claim_origin()`, `trace_column_lineage()`,
   `impact_analysis(source_schema_id, field)`.
5. Экспортировать OpenLineage-compatible JSON.
6. Добавить visualization-friendly graph export для Marquez/DataHub/Atlas-style
   tools без runtime dependency.
7. Починить missing PROV edge activity -> event и сохранить activity duration в
   deterministic world event.

Acceptance criteria:

- claim value traceable до connector/dataset/source field/transform/evidence;
- schema field change показывает downstream tables, claims, query surfaces;
- lineage export validates against documented schema.

Покрывает:

- SOTA lineage gap;
- H-NEW-18, H-NEW-19;
- provenance/world-event incompleteness.

### WS-3C. Schema registry and compatibility gates

**Цель:** превратить schema comparison в enforceable governance.

Поверхности:

- `connectors/contracts/**`
- `catalog/**`
- `schemas/snapshots/fabric/**`
- `tools/ci/**`
- `tools/quality/validation/**`

Задачи:

1. Создать versioned Fabric schema registry с semver:
   MAJOR breaking, MINOR compatible additions, PATCH metadata/non-breaking.
2. Runtime compatibility enforcement для connector payloads.
3. DDL migration plan generation из schema diffs для DuckDB/world projections,
   где safe.
4. CI gate: breaking schema change blocked без approved major bump и migration
   note.
5. Approval workflow metadata:
   owner, reviewer, risk level, migration status, downstream impact summary.
6. ADR conventions связать с executable checks.

Acceptance criteria:

- breaking schema diff fails CI с impacted downstream surfaces;
- compatible additions produce registry entries/migrations;
- connector validation uses same contract versions as CI.

Покрывает:

- SOTA schema evolution/governance gap;
- schema merge/evolution findings из Phase 2.

### WS-3D. Access control, classification, audit log and retention

**Цель:** перейти от column masking к полноценной data governance модели.

Поверхности:

- `security/column_mask.py`
- `world_query.py`
- `storage/**`
- `retrieval/**`
- `connectors/cache/**`
- `fabric/pii/**`
- `core/security/**`

Задачи:

1. Добавить classification model:
   public, internal, confidential, regulated PII, sensitive policy/legal signal.
2. Улучшить PII detection: Luhn для card candidates и снижение false positives.
3. Добавить RBAC/ABAC hooks для dataset, column, row predicate, tenant scope.
4. Column access checks case-normalized для case-insensitive backends.
5. Row-level security predicates: tenant, geography, source, purpose-of-use.
6. Access audit log:
   actor, tenant, query, dataset, columns, cardinality bucket, decision, masking,
   denied reason, trace ID.
7. Заменить no-op `tenant_scope()` на enforced adapter behavior или explicit
   unsupported error.
8. Retention/deletion policies для CAS artifacts, cache entries, evidence
   bundles, world projections.
9. Спланировать encryption at rest для CAS:
   envelope encryption per classification и optional field-level encryption.

Acceptance criteria:

- unauthorized column/row access fails closed и emits audit event;
- tenant isolation tests не обходятся через DuckDB/cache/world query;
- classification travels от connector metadata до cache/world/query outputs.

Покрывает:

- SOTA access-control/governance gap;
- original case-sensitive column guard;
- M18, PII credit-card regex finding.

---

## Phase 4 - Quality, Materialization and Time Travel

### WS-4A. Statistical quality, profiling, anomaly and drift detection

**Цель:** поднять quality subsystem от baseline checks до statistical monitoring.

Поверхности:

- `connectors/quality/**`
- `quality.py`
- `fitness_report.py`
- `data_plane/regression.py`
- `data_plane/semantic_diff.py`

Задачи:

1. Column profiling:
   null rate, distinct count, cardinality ratio, min/max, quantiles, histogram,
   top values, type stability.
2. Anomaly detectors:
   z-score, IQR, robust MAD, optional Isolation Forest behind dependency gate.
3. Drift detection:
   KS test для numeric, PSI для binned features, chi-squared для categoricals.
4. Declarative quality contracts в Great Expectations/Soda-like YAML.
5. Composite quality score с configurable dimension weights.
6. Quality trend history as time series keyed by dataset/schema/source.
7. Semantic diff duplicate keys: warning/model many-to-one, не silent last-row
   wins.
8. Regression exceptions categorization:
   transient I/O, fixture missing, comparison mismatch, internal error.

Acceptance criteria:

- quality reports содержат profiles, anomaly/drift, trend deltas;
- declarative quality contracts могут gate ingestion;
- semantic diff explicit reports duplicate keys.

Покрывает:

- SOTA data quality/anomaly gap;
- M17, H-NEW-16, quality threshold findings.

### WS-4B. Materialization intelligence and projection correctness

**Цель:** сделать DuckDB/Kuzu/world projections incremental, efficient,
explainable и semantically correct.

Поверхности:

- `world/materialize/duckdb.py`
- `world/materialize/projections.py`
- `world/materialize/sql.py`
- `world/materialize/kuzu.py`
- `world/store/**`

Задачи:

1. Materialization dependency graph:
   segments -> projections -> world tables -> Kuzu export.
2. Refresh policies:
   on segment arrival, scheduled, on demand, stale-if-error.
3. Projection pruning: rebuild only impacted projections.
4. Incremental projection maintenance where manifest supports it.
5. Fix ranked value ordering: non-null values preferred where intended.
6. Replace `MAX(object_value)` for `world.kind` by uniqueness validation or
   deterministic conflict handling.
7. `_apply_rows()` должен возвращать actual affected row count.
8. Kuzu incremental update или explicit rebuild-only contract with cost notes.
9. Segment compaction/vacuum/GC for accumulated world segments.

Acceptance criteria:

- unaffected projections are not rebuilt;
- materialization plans explainable/topologically sorted;
- world kind conflicts detected, not hidden by max aggregation.

Покрывает:

- SOTA materialization intelligence gap;
- world SQL/projection findings;
- Kuzu incremental/time travel gap.

### WS-4C. Time travel, branching and snapshot retention

**Цель:** сделать существующие CAS и tx/valid-time primitives queryable на
уровне API.

Поверхности:

- `world_query.py`
- `world/store/**`
- `world/materialize/**`
- `data_plane/**`
- `storage/**`

Задачи:

1. Point-in-time query API:
   `AS OF tx_time`, `AS OF valid_time`, combined bitemporal predicates.
2. Branch/fork support для scenario analysis:
   base snapshot, branch metadata, merge/conflict policy, provenance.
3. Snapshot retention/GC:
   keep latest N, keep time range, keep tagged audit snapshots, delete expired
   unreferenced artifacts.
4. Оценить ACID table format path:
   DuckDB-native snapshots first, Iceberg/Delta as future adapters.
5. Bitemporal tests для late-arriving facts и corrections.

Acceptance criteria:

- world state queryable at past date без manual rebuild;
- branch/fork не contaminates base world;
- GC не удаляет retained snapshot artifacts.

Покрывает:

- SOTA time travel/versioning gap.

---

## Phase 5 - Connectors, Streaming and Scale-Out

### WS-5A. Dead-letter queue and quarantine

**Цель:** изолировать poison rows/messages/claims без падения whole batch.

Поверхности:

- `data_plane/**`
- `connectors/sources/**`
- `claims/**`
- `connectors/transform/**`
- `world/store/**`

Задачи:

1. Ввести `QuarantineRecord`:
   reason, severity, source, raw payload ref, schema version, traceback class,
   trace ID, retry policy.
2. Использовать quarantine для per-record transform failures,
   citation-less claims, invalid schema rows, non-finite metrics,
   poison streaming messages.
3. DLQ storage adapter на CAS + query/report API.
4. Replay/reprocess command для quarantined records после deployment fix.

Acceptance criteria:

- one bad row/claim не теряет whole batch;
- DLQ metrics/lineage показывают failed source/downstream impact;
- quarantined records reprocessed deterministically.

Покрывает:

- SOTA DLQ/quarantine priority;
- citation, NaN/Inf, schema, streaming poison-message clusters.

### WS-5B. Connector ecosystem expansion

**Цель:** выйти за пределы HTTP open data, сохранив hardened contracts.

Новые connector families:

- file formats: local/remote CSV, Parquet, JSONL, Excel;
- cloud object storage: S3, GCS, Azure Blob;
- databases: PostgreSQL, BigQuery, Snowflake;
- API protocols: GraphQL, gRPC;
- GIS/spatial: GeoJSON, PostGIS, Overture Maps, geospatial profiles;
- streaming/event sources: Kafka, Pulsar, NATS, Kinesis.

Задачи:

1. До implementation определить capability contracts для files, databases,
   spatial и streams.
2. Добавить schema introspection для file/database/API connectors.
3. Reuse resilience, cache, lineage, governance, telemetry contract для всех
   connector classes.
4. Fixture-based contract tests per connector family.
5. Profile scaffolding и docs для new connector authors.

Acceptance criteria:

- у каждой family есть at least one implementation и contract tests;
- discovery lists capabilities без heavy eager imports;
- GIS connectors preserve CRS/spatial metadata и lineage.

Покрывает:

- SOTA connector ecosystem gap.

### WS-5C. Event-driven streaming, CDC and backpressure

**Цель:** перейти от sync pull-based streaming windows к event-driven data plane.

Поверхности:

- `data_plane/modes.py`
- `data_plane/watermark.py`
- `data_plane/cursor_store.py`
- `connectors/pool.py`
- future streaming connectors

Задачи:

1. Streaming source protocol:
   subscribe, poll, checkpoint, commit, rewind, pause, resume, close.
2. Window strategies:
   tumbling, sliding, session, count-based.
3. Exactly-once/effectively-once mode:
   idempotent segment IDs, offsets/checkpoints, dedupe keys, transactional
   materialization.
4. Backpressure propagation от materialization/cache/world-store к polling.
5. Large DataFrame `to_dict(orient="records")` вынести из event loop через
   chunking/worker execution.
6. CDC support для database connectors и schema-change events.
7. DLQ/quarantine для poison messages.

Acceptance criteria:

- streaming tests cover checkpoint recovery, duplicate replay, backpressure,
  poison messages;

- event loop remains responsive under large chunks;
- CDC schema changes produce lineage/impact-analysis events.

Покрывает:

- SOTA streaming/real-time gap;
- original blocking `to_dict()` finding;
- cursor/checkpoint atomicity findings.

### WS-5D. Distributed execution and storage scale-out

**Цель:** подготовить Fabric к большим datasets и multi-tenant workloads.

Поверхности:

- `data_plane/orchestrator.py`
- `connectors/pool.py`
- `connectors/cache/**`
- `world/store/**`
- `world/materialize/**`
- `storage/**`

Задачи:

1. Partitioned ingestion plan:
   partition key, bounds, source cursor, expected cardinality, merge policy.
2. Execution backends:
   local async first, then Dask/Ray/Celery adapter behind interface.
3. Multi-tenant CAS namespace/isolation и quotas.
4. World materialization sharding by tenant/dataset/time partition.
5. Segment compaction и garbage collection mandatory maintenance.
6. Load/stress benchmarks per connector/materialization path.

Acceptance criteria:

- partitioned ingestion resumes failed partitions independently;
- tenant A не видит tenant B через CAS/cache/world query/metrics;
- load tests publish throughput/memory baselines.

Покрывает:

- SOTA distributed execution/scalability gap;
- tenant isolation and segment accumulation findings.

---

## Phase 6 - AI-Augmented Discovery and Frontier UX

### WS-6A. Semantic catalog and natural-language discovery

**Цель:** перейти от string matching к semantic discovery с explainable
fallbacks.

Поверхности:

- `catalog/**`
- `retrieval/**`
- `connectors/bindings/**`
- `connectors/profiles/**`

Задачи:

1. Embedding-backed dataset/metric/metadata search + deterministic lexical
   fallback.
2. Vector metadata:
   source, schema version, embedding model, timestamp, invalidation policy.
3. Natural-language-to-dataset resolution как ranked explainable plan, не hidden
   direct selection.
4. Automated metadata enrichment from docs, capability snapshots, schema
   descriptions.
5. Evaluation set для discovery relevance, false positives, stale metadata.
6. Исправить retrieval `profile_id=str(None)` bug.
7. `_fallback_to_plan` должен корректно обновлять `metric_id` и analytics.

Acceptance criteria:

- semantic search returns explainable ranked candidates;
- stale embeddings invalidate on schema/metadata changes;
- analytics distinguish lexical, semantic, manual binding routes.

Покрывает:

- SOTA AI-augmented discovery gap;
- H14, retrieval fallback analytics finding.

### WS-6B. Entity resolution and graph reasoning

**Цель:** использовать Kuzu/world graph как reasoning surface, а не только
export target.

Поверхности:

- `world/materialize/kuzu.py`
- `provenance/**`
- `retrieval/**`
- `claims/conflicts/**`
- future entity-resolution package

Задачи:

1. Probabilistic entity resolution across World Bank, Eurostat, WVS, WHO, UNPD,
   UNESCO и other sources.
2. Candidate matches store:
   confidence, evidence, method, override provenance.
3. Kuzu traversal/query helpers:
   lineage, source conflict, entity neighborhood, policy-domain impact.
4. Graph-reasoning tests over small multi-source fixtures.

Acceptance criteria:

- entity matches explainable/reversible;
- graph queries answer source overlap, conflict neighborhood, downstream
  policy-impact questions.

Покрывает:

- SOTA entity resolution и knowledge graph reasoning gaps.

---

## Cross-Cutting Exception Hygiene

Многие находки имеют общий паттерн: `except Exception` скрывает transient,
permanent, validation, corruption и security failures в один debug-level шум.

Единая политика:

- Security violation: hard fail, audit event, no fallback.
- Data corruption suspicion: fail closed или quarantine.
- Transient network/storage issue: retryable typed error with backoff metadata.
- Optional capability unavailable: typed degraded outcome with trace.
- Test/regression mismatch: отдельный mismatch result, не generic failed.
- Cleanup failure: warning/error с resource identity, не silent debug.

Поверхности с приоритетом:

- federation planner;
- data-plane regression;
- cache invalidation;
- catalog probe;
- claims persist;
- fallback chains;
- extractor registry imports;
- `_load_applied_segments()`;
- metric/report deserialization.

Acceptance criteria:

- broad `except Exception` в Fabric имеет local justification или typed
  conversion;

- logs include structured reason, source id, trace id where available;
- CI can grep/report new broad-exception sites.

---

## Cross-Cutting Testing Strategy

Обязательные новые категории тестов:

1. **Security tests**
   SPARQL, SQL, SoQL, ODSQL, URL traversal, JSON path traversal,
   eval-expression injection, ZIP bomb, unsafe transform manifest.
2. **Concurrency stress tests**
   circuit breaker half-open probes, rate limiter contention, session creation,
   unregister, wrapper application, singleton construction, cursor writes,
   segment writes, cache metrics.
3. **Property-based tests**
   schema merge/evolution, contract IDs, row-count ranges, Unicode
   canonicalization, unit conversion, finite quality scores, bitemporal query,
   semantic diff duplicate keys.
4. **Lifecycle leak tests**
   aiohttp sessions, SQLite/DuckDB/Kuzu handles, background prefetch tasks,
   connection pool close/release, file locks.
5. **Golden artifact tests**
   PROV/N-Quads export, fitness report round trip, OpenLineage export, lineage
   graph snapshots, world segment manifests, quality report schemas.
6. **Load/benchmark tests**
   connector throughput, cache eviction pressure, high-conflict federation,
   materialization refresh, streaming chunks, memory ceilings.
7. **Chaos/mutation tests**
   conflict resolution, quality gates, fallback chains, network partition,
   latency injection, partial materialization failure, replay determinism.

Suggested phase gates:

```bash
cd policy-engine
python -m pytest tests/unit/fabric
python -m pytest tests/unit/fabric/connectors
python -m pytest tests/unit/core/security tests/unit/core/trace tests/unit/core/contracts
python -m pytest tests/performance -k "fabric or connector or materialization"
python -m ruff check src/polisyos/fabric tests/unit/fabric
python -m mypy src/polisyos/fabric
```

Для races/leaks:

```bash
cd policy-engine
python -m pytest tests/unit/fabric -k "race or concurrency or lifecycle" --count=50
python -m pytest tests/unit/fabric -k "leak or shutdown or close" --count=20
```

Если `pytest-count` не установлен, добавить маленький runner в `tools/quality/testing/`
и не полагаться на ручные перезапуски.

---

## Finding-to-Workstream Coverage Matrix

| Audit cluster                                                   | Workstream                      |
| --------------------------------------------------------------- | ------------------------------- |
| SPARQL/SQL/SoQL/ODSQL injection                                 | WS-0A                           |
| URL/path/data_path injection                                    | WS-0A, WS-0B                    |
| ZIP bomb, unbounded HTTP reads                                  | WS-0B                           |
| unsafe dynamic transform import                                 | WS-0B                           |
| N-Quads escaping, fitness report double-count                   | WS-0C                           |
| citation-less claims, evidence key assumptions                  | WS-0C, WS-5A                    |
| naive datetime, `utcnow`, clock skew                            | WS-0D                           |
| pool/session/DB/Kuzu resource leaks                             | WS-1A                           |
| non-atomic cursor/segment writes                                | WS-1B                           |
| registry atomic writes, corrupt schema load                     | WS-1B, WS-2A                    |
| circuit breaker slot leaks, underflow, TOCTOU                   | WS-1C                           |
| rate limiter negative tokens, blocked window, wait metrics      | WS-1C                           |
| SDMX resilience bypass, fallback masking                        | WS-1C                           |
| frozen dataclasses with mutable containers                      | WS-1D                           |
| singleton/registry/unit/dimension/proxy races                   | WS-1D                           |
| double wrapper application, wrapper leaks                       | WS-1D                           |
| eager connector imports                                         | WS-1D                           |
| mutable connector/catalog request state                         | WS-1D                           |
| unbounded cache/resolver/audit/prefetch state                   | WS-1E                           |
| cache eviction and SmartExpiryPolicy defects                    | WS-1E                           |
| prefetch heap mutation/requeue leaks                            | WS-1E                           |
| schema allowed-values loss, NaN/Inf bounds                      | WS-2A                           |
| schema evolution misclassification                              | WS-2A                           |
| contract ID/range validation                                    | WS-2A                           |
| semantic inference count/ratio/percentage issues                | WS-2A                           |
| NaN/Inf quality, resolver, projection issues                    | WS-2B                           |
| completeness edge cases, hardcoded confidence                   | WS-2B                           |
| Unicode canonicalization, locale decimals                       | WS-2C                           |
| affine units, precision, exchange-rate locking                  | WS-2C                           |
| pipeline DAG order, transform determinism                       | WS-2D                           |
| capability decorator/protocol-stub defects                      | WS-2D                           |
| observability, metrics, SLO gaps                                | WS-3A                           |
| cache metrics races/double misses                               | WS-3A                           |
| column/value lineage and impact analysis gaps                   | WS-3B                           |
| missing PROV edges, event duration collapse                     | WS-3B                           |
| schema registry and compatibility governance                    | WS-3C                           |
| RBAC/ABAC, RLS, audit log, retention                            | WS-3D                           |
| tenant isolation no-op, case-sensitive column guard             | WS-3D                           |
| profiling, anomaly, drift gaps                                  | WS-4A                           |
| semantic diff duplicate-key drop, regression swallowing         | WS-4A                           |
| materialization refresh/pruning/SQL semantics                   | WS-4B                           |
| Kuzu rebuild-only, segment GC                                   | WS-4B                           |
| point-in-time query, branching, retention                       | WS-4C                           |
| DLQ/quarantine                                                  | WS-5A                           |
| file/database/cloud/GIS/GraphQL/gRPC connectors                 | WS-5B                           |
| streaming, CDC, exactly-once, backpressure                      | WS-5C                           |
| blocking DataFrame conversion in async path                     | WS-5C                           |
| distributed execution, partitioning, sharding, multi-tenant CAS | WS-5D                           |
| semantic search, NL discovery, metadata enrichment              | WS-6A                           |
| probabilistic entity resolution, Kuzu reasoning                 | WS-6B                           |
| broad silent-exception hygiene                                  | Cross-cutting exception hygiene |

---

## Priority Backlog

### P0 - До expansion/default-path feature work

- SPARQL/SQL/SoQL/ODSQL/URL/data_path injection.
- ZIP bombs, oversized reads, unsafe dynamic transform imports.
- Naive datetimes and naive/aware comparison.
- Fitness report double-count, N-Quads escaping, citation-less batch abort.
- Circuit breaker half-open slot leak and rate limiter negative bucket.
- Cursor/segment atomicity, pool unregister, CacheIndex/session/DB/Kuzu leaks.
- Frozen-with-mutable and shared-state defects that can corrupt cross-request
  data.

### P1 - Для production trust

- Bounded memory for caches, audit logs, queues, resolver caches, resilience maps.
- Schema merge/evolution correctness and contract validation gates.
- NaN/Inf finite-value boundary enforcement.
- Trustworthy cache metrics and Fabric telemetry baseline.
- Column/value lineage and impact-analysis API.
- Access audit, tenant scope, RBAC/ABAC hooks, classification.
- DLQ/quarantine for poison records.

### P2 - Для SOTA completeness

- Statistical profiling, anomaly/drift detection, declarative quality contracts.
- Materialization dependency graph, incremental refresh, projection pruning.
- Time travel, branch/fork, snapshot retention.
- File/cloud/database/GIS/API connector families.
- Event-driven streaming, CDC, exactly-once/effectively-once, backpressure.

### P3 - Frontier differentiation

- Distributed execution adapters and partitioned ingestion.
- Semantic catalog search, NL dataset resolution, metadata enrichment.
- Probabilistic entity resolution across sources.
- Kuzu graph reasoning and visual lineage/impact exports.

---

## D1 Docs Impact Table

| D1 doc cluster                            | Exact files                                                                                                                                                                                               | Source of truth                                                                                                       | Validation command or evidence                                                                                                                            | Backlog / priority |
| ----------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------ |
| Fabric reference set                      | `docs/reference/fabric/index.md`, `docs/reference/fabric/connectors.md`, `docs/reference/fabric/profiles.md`, `docs/reference/fabric/data-plane.md`                                                       | connector registry, built-in profiles, data-plane/runtime schema snapshots, lineage and quality modules               | `uv run pytest tests/unit/fabric/connectors/test_registry.py tests/unit/fabric/connectors/test_contract_system.py tests/unit/fabric/connectors/test_schema_system.py -q` | none               |
| Authoring and generated-artifact guidance | `docs/connectors/CONTRIBUTING.md`, `docs/how-to/add-data-source.md`, `docs/how-to/manage-generated-artifacts.md`                                                                                          | connector scaffolding rules, profile/contracts registry, snapshot governance tooling                                  | `uv run python tools/ci/check_fabric_schema_registry.py --check --evidence-out _build/.tmp/fabric-schema-governance.json`                                 | none               |
| Recovery runbooks                         | `docs/runbooks/cache-rebuild-storm.md`, `docs/runbooks/retained-artifact-recovery.md`, `docs/runbooks/artifact-corruption-recovery.md`                                                                    | cache/index lifecycle, CAS-backed artifact retention and restore flows, corruption detection paths                    | `uv run pytest tests/unit/fabric/data_plane/test_quarantine.py tests/unit/fabric/data_plane/test_streaming_runtime.py tests/unit/fabric/test_lineage.py -q`              | none               |
| Package boundary READMEs                  | `src/polisyos/fabric/README.md`, `src/polisyos/fabric/connectors/README.md`, `src/polisyos/fabric/data_plane/README.md`, `src/polisyos/fabric/retrieval/README.md`, `src/polisyos/fabric/world/README.md` | package facades, connector families, data-plane modes, retrieval/catalog entry points, world materialization boundary | `uv run pytest tests/unit/fabric -q`                                                                                                                           | none               |

D1 closure note: all required D1-L2 pages are present. The standalone semantic
catalog reference remains a P2 D2 enhancement, not a D1 blocker.

## Definition of Done

Workstream считается завершенным, только если:

- fix/feature merged за правильным default behavior или feature flag;
- regression tests покрывают исходную audit finding;
- malicious/adversarial fixtures добавлены для security/data-boundary случаев;
- observability добавлена для нового behavior/failure mode;
- docs/contracts обновлены при public behavior change;
- failure semantics explicit:
  typed error, degraded result, quarantine, retryable transient или hard
  security rejection;

- memory/lifecycle/concurrency behavior имеет bounded-state или stress test.

Вся программа завершена, когда:

- все P0/P1 findings имеют direct test coverage или accepted-risk record;
- Fabric emits operational metrics/traces from ingestion to materialization/query;
- column/value lineage отвечает на origin и impact-analysis вопросы;
- schema compatibility enforced in CI and runtime validation;
- governance имеет classification, access audit, tenant isolation, retention;
- SOTA capabilities build on hardened primitives, not bypass them.

---

## Рекомендуемый порядок реализации

1. Добавить shared safety utilities:
   query escaping, identifier validation, URL segment validation, UTC datetime,
   finite numeric validation, bounded response/decompression helpers.
2. Пропатчить все P0 call sites на эти utilities.
3. Добавить lifecycle ownership и atomic-write primitives.
4. Починить resilience/cache concurrency clusters со stress tests.
5. Починить schema/contract merge semantics и property tests.
6. Добавить observability после исправления trustworthiness metrics.
7. Добавить lineage model и schema governance gates.
8. Добавить access governance и DLQ/quarantine.
9. Построить quality/materialization/time-travel intelligence.
10. Расширить connectors, streaming и scale-out.
11. Добавить AI-augmented discovery и graph reasoning после стабилизации
    deterministic baseline.

Такой порядок избегает главной ловушки из аудитов: строить впечатляющие SOTA
возможности поверх primitives, которые пока недостаточно безопасны,
наблюдаемы и корректны под concurrency.
