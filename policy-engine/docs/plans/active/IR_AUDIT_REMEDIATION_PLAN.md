# План исправления и SOTA-улучшения IR

> Консолидированный remediation plan для `src/polisyos/ir` по итогам трех
> пакетов аудитов:
> `SOTA Gap Analysis: polisyos.ir`,
> `Code-Level Audit: Anti-patterns, Bugs, and Optimization Opportunities`,
> `Новый аудит polisyos.ir: верифіковані знахідки`.
> Created: 2026-04-12

---

## Цель

Довести `polisyos.ir` до состояния, в котором:

- закрыты все известные correctness, CAS-stability и schema-evolution дефекты;
- IR становится не просто набором Pydantic-моделей, а compiler-grade
  contract layer с pass infrastructure, cross-model type checking и
  deterministic normalization;

- linker, registry composition, canon, analytics contracts и world IDs больше
  не допускают silent corruption, silent downgrade и semantically ambiguous
  behavior;

- публичная поверхность IR остается компактной, предсказуемой и
  backward-compatible под явной compatibility policy;

- SOTA-claims по causal, governance и policy expressiveness опираются на
  реализованные контракты, тесты, schema catalog и interoperability bridges, а
  не на roadmap-only декларации.

## Область действия

Основная область:

- `src/polisyos/ir/**`
- `tests/unit/ir/**`, `tests/unit/foundry/**`, `tests/unit/scientist/**` там, где тесты
  закрепляют IR invariants;

- `docs/reference/ir/**`, `docs/explanation/trinity.md`,
  `docs/explanation/ir-design.md`, `docs/contracts/**`, `docs/adr/**`, если
  исправления меняют публичный контракт или compatibility policy.

Подсистемы:

- canon, content addressing, migration helpers и schema versioning;
- kernel registries: slots, mechanisms, merge rules, constraints, units,
  selector fields, trust and time semantics;

- linker / trinity linking / registry fragment composition;
- governance AST and policy composition;
- analytics contracts, uncertainty, estimands, transportability, HTE,
  discovery, mediation, actual causality;

- observation bundles, compilers, readiness and execution manifests;
- world IDs, fact log, predicates, provenance-aligned world contracts;
- artifacts and connector-facing IR surfaces.

Вне области этого документа:

- непосредственная реализация всех frontier методов;
- рефакторинг Foundry/Scientist/Fabric вне узких shared utilities;
- полный повтор аудитов без изменения входных данных;
- изменение продуктовой стратегии вокруг policy/runtime surfaces вне влияния на
  IR contracts.

## Входные аудиты

План консолидирует три уровня находок:

- **SOTA gaps**: отсутствие pass infrastructure, cross-model type checking,
  estimand normalization, lineage/use-def model, uncertainty algebra, schema
  governance, property/fuzz testing, interoperability bridges и ряда causal /
  governance frontier contracts.

- **Code-level audit**: asserts в runtime validation, silent exception
  swallowing, unknown `_type` downgrade в canon, mutable validators, eager
  wildcard imports, god objects/functions, O(n²) loops, Kuzu batching gaps,
  copy-paste validation logic и inconsistent ID/reference API.

- **Verified findings audit**: конкретные correctness defects в
  `registry_fragments`, linker schedule conflict accounting, dataclass
  canonicalization, `exclude_none=True`, hash algorithm policy, recursion depth,
  mutable/non-frozen analytics models, duplicated uniqueness checks, selector
  validation gaps, migration semantics и import-time registry costs.

## Главный вывод

`polisyos.ir` уже сильный по breadth:

- покрывает governance, kernel registries, analytics, observation, world graph,
  linker, artifacts и migration surfaces;

- уже является фактическим contract backbone для Foundry, Scientist, Fabric,
  Lex и runtime;

- имеет хорошую основу в виде Pydantic validation, canonical JSON, typed refs,
  registries и ABI snapshots.

Но качество IR сейчас ограничивают не новые типы, а шесть системных дефицитов:

1. **Canon и CAS не полностью безопасны.** Unknown `_type`, `asdict()`
   behavior, `exclude_none=True`, `sha1`, отсутствие recursion limits и
   неявная time/float policy создают риск silent corruption и unstable hashes.
2. **Registry/linker correctness неполная.** Unsatisfied dependencies,
   dependency cycles, unknown mechanisms, ambiguous interval semantics и
   пропущенные conflict surfaces ломают determinism и diagnostic quality.
3. **IR не оформлен как компиляторный слой.** Нет pass manager, analysis cache,
   type-check phase, canonical normalization, lineage/use-def и dead-artifact
   analysis.
4. **Validation и mutability непоследовательны.** Часть моделей frozen, часть
   mutable; business logic прячется в validators; cross-field invariants
   выражены фрагментарно; duplicated uniqueness checks расходятся по смыслу.
5. **Public API и hot paths перегружены.** `analytics.__init__` eagerly тянет
   десятки модулей, есть quadratic loops, repeated hashing, per-edge DB calls,
   import-time registry construction и раздутая namespace surface.
6. **SOTA completeness и interoperability отстают.** Нет formal uncertainty
   algebra, temporal logic, hierarchy-aware policy composition, many causal
   frontier contracts, standard mappings и binary/streaming transport story.

Главное правило выполнения: **Phase 0-2 обязательны до любых новых
frontier-type additions и до расширения public IR surface.**

---

## Принципы исполнения

1. **Correctness before surface growth.** Сначала исправляются canon,
   linker/registry, validation и schema governance, потом добавляются новые
   методы и типы.
2. **CAS stability is a product requirement.** Любая неоднозначность
   canonicalization, float/time/None policy или hash policy рассматривается как
   correctness bug, а не как style issue.
3. **No silent degradation.** Unknown type, malformed artifact, parse failure,
   migration mismatch или compatibility violation должны превращаться в typed
   error или structured warning, а не в `None` или plain `dict`.
4. **Каждый фикс получает тест и policy decision.** Для каждого изменения
   должен быть regression/property/fuzz/compatibility test и документированная
   семантика, если меняется публичный контракт.
5. **Cross-model invariants живут в pass layer.** Pydantic validators остаются
   для local shape checks; referential integrity, reachability, type alignment и
   lineage проверяются отдельными IR passes.
6. **Mutable normalization не должна жить в `@model_validator`.** Derived fields
   должны появляться через factory methods, computed fields или explicit
   normalization passes.
7. **Performance fixes идут только с benchmark loop.** Любой hot-path refactor
   в canon, linker, registry composition, imports и graph materialization должен
   сопровождаться замером latency/memory.
8. **Schema evolution — rule-based.** `schema_version` больше не просто строка;
   нужна compatibility matrix, migration contract tests и forward/backward
   behavior для canonical payloads.
9. **Frontier work behind stable abstractions.** ICP/IRM, causal RL, temporal
   logic, mechanism design и interoperability bridges строятся на уже
   стабилизированном core IR.

---

## Приоритетная матрица

| Cluster                                 | Severity | Effort | Почему первым                                                                   |
| --------------------------------------- | -------- | -----: | ------------------------------------------------------------------------------- |
| Canon / CAS correctness                 | Critical | Medium | Влияет на content addressing, deduplication, migration safety и reproducibility |
| Registry / linker correctness           | Critical | Medium | Ошибки здесь ломают весь Trinity pipeline и diagnostic trustworthiness          |
| Silent failure removal                  | Critical | Low    | Иначе malformed artifacts и parse errors маскируются под "все нормально"        |
| Cross-model type checking               | Critical | Medium | IR не гарантирует referential integrity across pipeline                         |
| Estimand / uncertainty normalization    | High     | Medium | Без этого нет semantic dedupe и decision-grade confidence semantics             |
| Mutable validator cleanup               | High     | Medium | Скрытые side effects в моделях мешают determinism и safe evolution              |
| Public API + import/perf cleanup        | High     | Medium | Ускоряет startup и делает surface manageable                                    |
| Schema governance + compatibility gates | High     | Medium | Нужны до роста public contract surface                                          |
| Property / fuzz / algebra verification  | High     | Low    | Дает confidence, что invariants реально соблюдаются                             |
| Frontier causal / governance extensions | Medium   | High   | Важны, но только после стабилизации core                                        |

## Фазовый roadmap

| Phase | Тема                                          | Горизонт         | Exit criteria                                                                                     |
| ----- | --------------------------------------------- | ---------------: | ------------------------------------------------------------------------------------------------- |
| 0     | Canon, registry и silent-failure containment  | 5-7 рабочих дней | Нет открытых P0 по canon/linker/registry; все silent fallbacks переведены в typed errors/warnings |
| 1     | Validation, mutability и schema foundation    | 1 спринт         | Есть invariant helpers, compatibility policy, mutable validators вынесены из default path         |
| 2     | Compiler-grade IR infrastructure              | 1-2 спринта      | Pass manager, analysis cache, type-check pass и normalization pipeline работают на core bundles   |
| 3     | Performance, API hygiene и verification depth | 1-2 спринта      | Hot paths ускорены, public surface очищен, property/fuzz/benchmark gates добавлены                |
| 4     | Interoperability, scale and transport         | 1-2 спринта      | Schema catalog, bridges, incremental/binary story и compatibility tooling готовы                  |
| 5     | Frontier causal and policy expressiveness     | после Phase 4    | Новые contracts gated, documented и не ломают stabilized core IR                                  |

---

## Phase 0 — Canon, Registry and Silent-Failure Containment

### WS-0A. Canon / CAS hardening

**Цель:** убрать все канонизационные пути, которые могут давать different bytes
for semantically equivalent data или silent downgrade при schema evolution.

Поверхности:

- `src/polisyos/ir/canon.py`
- `src/polisyos/ir/world/ids.py`
- `src/polisyos/ir/fact_log.py`
- `src/polisyos/ir/kernel/base.py`
- `src/polisyos/ir/migrations/base.py`

Задачи:

1. Перевести unknown canonical `_type` из silent passthrough в
   `CanonViolation` или structured compatibility error.
2. Переписать dataclass canonicalization без `dataclasses.asdict()` для полей,
   содержащих `BaseModel`; canonicalizer должен рекурсивно обходить поля сам.
3. Явно зафиксировать policy для `None`:
   либо оставить `exclude_none=True` как часть ABI,
   либо сделать это opt-in через `CanonSpec`.
4. Ввести recursion depth limits в `_canonicalize_obj()` и
   `_normalize_payload_value()`, чтобы закрыть DoS/stack overflow path.
5. Удалить `sha1` из default hash policy; если нужен legacy mode, вынести его в
   explicit deprecated branch с warning.
6. Определить и задокументировать policy для timezone normalization, string vs
   bytes hashing, float canonicalization в analytics contracts и `tx_time`.
7. Перевести `Fact` на явную time policy:
   либо mandatory `tx_time`, либо factory-only creation с documented invariant.
8. Закрепить migration semantics: migration function не должна silently терять
   собственный `schema_version` без явного правила.

Критерии приемки:

- round-trip tests покрывают unknown `_type`, nested dataclass + BaseModel,
  deep recursion, timezone normalization и `None` semantics;

- CAS hashes стабильны между платформами и Python runtimes на agreed fixture
  corpus;

- `sha1` не используется в default execution path;
- есть ADR или reference note, фиксирующая canonical policy.

Покрывает:

- K4, K5, K6, H4, H5, H8, H9, M15, M17, L5, L6, L13;
- SOTA gaps: 3.1, 5.1, 6.1.

### WS-0B. Registry composition and linker correctness

**Цель:** сделать Trinity composition/linking детерминированным и
диагностируемым даже при missing dependencies, cycles и partial invalid input.

Поверхности:

- `src/polisyos/ir/registry_fragments.py`
- `src/polisyos/ir/linker/_trinity_linker.py`
- `src/polisyos/ir/linker/_trinity_mechanisms.py`
- `src/polisyos/ir/linker/_trinity_params.py`
- `src/polisyos/ir/linker/reports.py`

Задачи:

1. Разделить dependency validation и fragment application на две фазы:
   fragment с незакрытыми зависимостями не должен попадать в `applied`.
2. Заменить лексикографический порядок на топологическую сортировку с явной
   cycle detection и отдельным diagnostic code для dependency cycles.
3. Сохранить unknown-mechanism interventions в schedule/conflict accounting,
   чтобы отчет показывал весь набор проблем за один проход.
4. Зафиксировать interval convention для schedules
   (`[start, end]` или `[start, end)`) и синхронизировать ее с overlap checks.
5. Перевести внутренние warning accumulators с list-membership на ordered-set
   семантику.
6. Добавить detection для unused registries / slots / mechanisms / constraints
   как отдельный diagnostic phase, а не post-hoc пожелание.
7. Ограничить глубину/path semantics в param traversal и явно решить, допускаем
   ли `.` в field names.

Критерии приемки:

- missing dependency, cyclic dependency и unknown mechanism fixtures выдают
  полный и детерминированный diagnostic set;

- repeated runs дают одинаковый `LinkReport` и одинаковый composed bundle;
- schedule overlap semantics задокументирована и покрыта boundary tests;
- регрессионные тесты подтверждают, что invalid fragment больше не влияет на
  merged registry state.

Покрывает:

- K1, K2, K3, H2, H3, H6, M6, M9;
- SOTA gaps: 1.2, 1.3, 5.2.

### WS-0C. Silent failure removal and validation containment

**Цель:** устранить paths, где malformed input silently превращается в `None`,
empty fallback или partially normalized object.

Поверхности:

- `src/polisyos/ir/observation/contract_compilers.py`
- `src/polisyos/ir/governance/problem_frame.py`
- `src/polisyos/ir/analytics/context.py`
- `src/polisyos/ir/analytics/diagnostic_dashboard.py`
- `src/polisyos/ir/analytics/evidence_bundle.py`
- `src/polisyos/ir/analytics/causal.py`
- `src/polisyos/ir/analytics/causal_run_snapshot.py`
- `src/polisyos/ir/analytics/alignment_certification.py`
- `src/polisyos/ir/migrations/trinity_migration.py`
- `src/polisyos/ir/portfolio.py`

Задачи:

1. Заменить `assert` в validation flow на explicit `ValueError` /
   domain-specific validation errors.
2. Убрать `type: ignore` там, где скрывается реальная nullability проблема;
   сделать тип явным или изменить flow.
3. Narrow all broad `except Exception` blocks:
   expected parse failure -> typed degraded outcome,
   unexpected failure -> warning/error with provenance.
4. Поднять imports из циклов и hot properties на module level.
5. Перевести stringly-typed enums (`interaction_mode`, similar fields) в
   `Enum`/`Literal` contract.

Критерии приемки:

- malformed artifact parse больше не indistinguishable from "artifact absent";
- production и `python -O` ведут себя одинаково в validation paths;
- warning/error telemetry показывает parse and migration failures;
- no blanket swallow remains in IR without documented justification.

Покрывает:

- A1, A2, A3, A4, A5, B, D3;
- verified echoes of silent schema/version handling.

---

## Phase 1 — Validation, Mutability and Schema Foundation

### WS-1A. Cross-model invariants and shared validation toolkit

**Цель:** перестать полагаться на локальные validators там, где требуется
межмодульная referential integrity и единые invariant helpers.

Поверхности:

- `src/polisyos/ir/governance/**`
- `src/polisyos/ir/kernel/**`
- `src/polisyos/ir/observation/**`
- `src/polisyos/ir/analytics/**`
- `src/polisyos/ir/_validation.py` или аналогичный shared module

Задачи:

1. Вынести duplicated uniqueness checks в общий helper:
   `ensure_unique_ids(items, key_fn, label)`.
2. Добавить shared helpers для:
   finite numeric validation, CI bounds, interval monotonicity,
   pairwise disjointness/intersection checks, non-empty path validation.
3. Закрыть selector gaps:
   operator/value shape checks, depth limits, collection guardrails.
4. Добавить missing cross-field invariants в analytics contracts:
   PN/PS/PNS bounds, mediation decomposition identities, path overlaps,
   strategic/proxy uniqueness rules.
5. Исправить `reject_floats_deep()` так, чтобы он заходил в nested BaseModel
   instances, а не только в `dict`/`list`.
6. Явно задокументировать различия `ID_PATTERN` vs `SLOT_ID_PATTERN` и решить,
   где нужен pattern tightening или domain-specific exception.

Критерии приемки:

- одинаковые invariant categories используют один и тот же helper и message
  policy;

- selector, mediation, actual causality и readiness fixtures валятся рано и
  детерминированно;

- float-rejection работает одинаково на raw payload и nested models;
- duplicated local uniqueness code существенно сокращена.

Покрывает:

- H12, H13, H14, M1, M2, M3, M4, M5, M10, M11, M13, M14, M16, L2, L3, L7, L8,
  L9, L10, L11, L12;

- SOTA gaps: 1.2, 3.1, 4.4.

### WS-1B. Mutable validator cleanup and model normalization discipline

**Цель:** убрать бизнес-логику и mutating side effects из `@model_validator`
там, где они нарушают frozen-by-default discipline и мешают predictability.

Поверхности:

- `src/polisyos/ir/analytics/transportability.py`
- `src/polisyos/ir/analytics/hte.py`
- `src/polisyos/ir/analytics/literature.py`
- `src/polisyos/ir/analytics/actual_causality.py`
- `src/polisyos/ir/analytics/mediation_effects.py`

Задачи:

1. Перевести derived-field normalization из mutating validators в factory
   constructors, explicit normalizers или `@computed_field`.
2. Согласовать policy по frozen vs non-frozen для analytics:
   default — frozen; mutable model допускается только с documented reason.
3. Убрать side-effect validators, которые меняют сразу много полей `self`.
4. Развести input contract и derived/report contract там, где одно сейчас
   маскируется другим.

Критерии приемки:

- `TransportabilityResult`, `HTEResult`-related contracts и похожие модели не
  полагаются на hidden mutation during validation;

- equality/hash/serialization semantics предсказуемы;
- derived fields появляются одинаково при construction, cloning и re-parse.

Покрывает:

- E3, H10, H11, часть M1-M4;
- SOTA gaps: 1.4, 3.2.

### WS-1C. Schema evolution and compatibility policy

**Цель:** превратить `schema_version: str = "1.0"` из декоративного поля в
реальную compatibility contract surface.

Поверхности:

- `src/polisyos/ir/migrations/**`
- `src/polisyos/ir/canon.py`
- `schemas/snapshots/ir/**`
- `docs/how-to/manage-schemas.md`
- `docs/reference/schemas.md`
- `docs/adr/**`

Задачи:

1. Ввести schema registry с explicit compatibility modes:
   `FULL`, `BACKWARD`, `FORWARD`, `NONE`.
2. Определить policy для additive optional fields, field removal, rename,
   unknown `_type` и canonical defaults.
3. Добавить compatibility tests на old payload fixtures и canonical payloads.
4. Зафиксировать negotiation story для producer/consumer version mismatch.
5. Привязать migration code к declared compatibility rules, а не только к
   snapshot tests.

Критерии приемки:

- есть rule-based answer на вопрос "можно ли читать старый payload новым кодом и
  наоборот";

- old canonical fixtures не деградируют silently;
- docs и ADR фиксируют schema evolution policy.

Покрывает:

- 5.1, K5, K6, M17;
- часть 6.1 и 7.3, где schema evolution влияет на bridges.

---

## Phase 2 — Compiler-Grade IR Infrastructure

### WS-2A. Pass manager, analyses and invalidation model

**Цель:** оформить IR как execution-free compiler layer с composable passes,
analysis cache и четким ordering.

Поверхности:

- новый пакет уровня `src/polisyos/ir/passes/**` или аналогичный namespace;
- `src/polisyos/ir/linker/**`
- `src/polisyos/ir/observation/**`
- `src/polisyos/ir/analytics/estimand.py`

Задачи:

1. Ввести `IRPass`, `IRAnalysis`, `PassResult`, `PassContext`,
   `InvalidationSet`, `PassPipeline`.
2. Разделить read-only analyses и transforms.
3. Сделать initial core passes:
   registry dependency pass, cross-model type check, estimand normalization,
   slot/mechanism reachability, unused artifact analysis.
4. Обеспечить composition между Trinity, analytics, observation и world-level
   surfaces, а не только внутри linker.

Критерии приемки:

- linker и registry validation могут запускаться через общий pass pipeline;
- analyses кэшируются и invalidated only when needed;
- pipeline ordering и emitted diagnostics детерминированы.

Покрывает:

- 1.1, 1.2;
- усиливает K1-K3, H12 и Phase 1 workstreams.

### WS-2B. Estimand normalization and lineage graph

**Цель:** добиться semantic dedupe, artifact lineage visibility и basis для
dead-artifact detection.

Поверхности:

- `src/polisyos/ir/analytics/estimand.py`
- `src/polisyos/ir/refs.py`
- `src/polisyos/ir/observation/causal_execution.py`
- `src/polisyos/ir/artifacts/**`

Задачи:

1. Добавить canonical algebraic simplification для estimand AST:
   collapse single-element nodes, commutative ordering, identity elimination.
2. Ввести normalized artifact lineage graph:
   `produced_by`, `consumed_by`, `derived_from`, `invalidated_by`.
3. Подготовить basis для common subexpression elimination и dead-artifact
   detection на IR уровне.
4. Привязать normalized estimands к CAS so that semantically identical queries
   dedupe consistently.

Критерии приемки:

- два семантически одинаковых estimand payloads canonicalize одинаково;
- lineage/ref graph позволяет ответить, какой artifact produced какой task;
- unused artifact diagnostics доступны как analysis result.

Покрывает:

- 1.3, 1.4, часть M6;
- indirectly снижает noise в observation/execution bundles.

### WS-2C. Uncertainty algebra and numeric policy

**Цель:** сделать uncertainty contract compositional и reproducible across
analytics outputs.

Поверхности:

- `src/polisyos/ir/analytics/uncertainty.py`
- `src/polisyos/ir/analytics/transportability.py`
- `src/polisyos/ir/analytics/hte.py`
- `src/polisyos/ir/analytics/causal.py`
- `src/polisyos/ir/kernel/trust.py`

Задачи:

1. Определить policy: full `Decimal`, bounded float canonicalization или hybrid
   model with explicit tolerance semantics.
2. Добавить `combine_envelopes()` semantics и compatibility rules для interval
   kinds (`confidence`, `credible`, etc.).
3. Ввести richer distribution carrier:
   posterior samples, quantiles, parametric fit, mixtures.
4. Синхронизировать uncertainty semantics с trust/confidence fields в kernel and
   analytics.

Критерии приемки:

- uncertainty composition определяется одним contract layer, а не ad-hoc
  consumer logic;

- float/tolerance policy документирована и тестируется на canonical fixtures;
- richer posterior/distribution payload имеет schema, docs и compatibility plan.

Покрывает:

- 3.1, 3.2, 3.3, M16, L10;
- частично закрывает Numeric tension из обоих code audits.

---

## Phase 3 — Performance, API Hygiene and Verification Depth

### WS-3A. Public surface cleanup and import discipline

**Цель:** уменьшить startup cost и сделать IR facade предсказуемым для tooling и
consumers.

Поверхности:

- `src/polisyos/ir/__init__.py`
- `src/polisyos/ir/analytics/__init__.py`
- `src/polisyos/ir/observation/__init__.py`
- `src/polisyos/ir/kernel/__init__.py`
- `src/polisyos/ir/world/__init__.py`
- `docs/reference/ir/**`

Задачи:

1. Убрать wildcard re-exports из `analytics.__init__`, ввести explicit
   `__all__` и lazy facade policy.
2. Добавить export audit: public symbol manifest должен совпадать с docs и
   declared facade.
3. Зафиксировать naming convention для `_id`, `_ref`, `*_key`,
   `ArtifactRef`, `RegistryItemId`.
4. Разбить god objects (`FetchResult`, `ConnectorMetadataSpec`) на sub-models и
   зафиксировать boundary semantics.
5. Превратить stateless utility classes в functions там, где класс не дает
   state nor polymorphism.
6. Проверить длинные import chains и убрать circular-dependency hotspots в
   `world/**`, `connectors.py` и фасадах пакетов.

Критерии приемки:

- `import polisyos.ir.analytics` больше не тянет весь analytics tree eagerly;
- public exports documented и проверяются test/CI gate;
- naming conventions отражены в style/reference docs.

Покрывает:

- E1, E2, E4, F1, F2, D4, 5.4;
- создаёт базу для docs/reflection tooling.

### WS-3B. Hot-path optimization and batching

**Цель:** убрать очевидные quadratic / repeated work paths без изменения
семантики.

Поверхности:

- `src/polisyos/ir/registry_fragments.py`
- `src/polisyos/ir/portfolio.py`
- `src/polisyos/ir/analytics/causal_graph.py`
- `src/polisyos/ir/analytics/causal_graph_kuzu.py`
- `src/polisyos/ir/analytics/causal_run_snapshot.py`
- `src/polisyos/ir/connectors.py`
- `src/polisyos/ir/kernel/slots.py`
- `src/polisyos/ir/kernel/merge_rules.py`
- `src/polisyos/ir/data/harmonizer.py`

Задачи:

1. Убрать repeated `model_copy()`/single-item apply patterns в registry
   composition; делать batched updates и single bundle construction.
2. Заменить O(n²) warning accumulation и pairwise checks там, где возможен
   set/sweep-line/precomputation.
3. Бэтчить Kuzu inserts и вынести repeated `json.dumps()` из per-edge loops.
4. Кешировать `query_key`/`request_key` и canonical bytes для frozen models.
5. Сделать default registries lazy-loaded.
6. Перевести import-in-loop/property paths на module imports.
7. Оценить hash implementation:
   full SHA-256, Blake2b-128 или другой explicitly chosen algorithm без
   accidental truncation semantics.

Критерии приемки:

- benchmark suite показывает measurable startup / linking / graph export gains;
- public semantics не меняются;
- hot paths покрыты regression + performance tests.

Покрывает:

- A1, C1, C2, C3, D1, D2, D3, H1, H2, H3, M7, M8, M12, O1-O8.

### WS-3C. Property-based, fuzz and algebra verification

**Цель:** перейти от mostly example-based tests к invariant-driven confidence.

Поверхности:

- `tests/unit/ir/**`
- `tests/unit/foundry/**` где валидируются merge/slot/uncertainty contracts
- `src/polisyos/ir/kernel/merge_rules.py`
- `src/polisyos/ir/canon.py`
- `src/polisyos/ir/linker/**`

Задачи:

1. Добавить property-based tests для canonical roundtrip, content hash
   stability, linker idempotency, registry composition determinism.
2. Добавить schema-aware fuzzing на canonical/object deserialization,
   selector AST, world IDs, migration inputs.
3. Верифицировать merge algebra against executable semantics, а не только
   against declared property tables.
4. Добавить benchmark gates для key hot paths из WS-3B.

Критерии приемки:

- canonical and linker invariants выражены Hypothesis/property suites;
- deep nesting and malformed payload fuzz cases не приводят к silent corruption;
- merge rules имеют executable proof-by-test, а не только declarative metadata.

Покрывает:

- 6.1, 6.2, 6.3, H7;
- усиливает все предыдущие phases.

---

## Phase 4 — Interoperability, Scale and Transport

### WS-4A. IR introspection, schema catalog and reflection API

**Цель:** дать tooling-слою программный способ понимать весь IR surface.

Поверхности:

- `src/polisyos/ir/**`
- `docs/reference/ir/**`
- `docs/reference/schemas.md`

Задачи:

1. Построить unified schema catalog:
   type name, version, module, public status, fields, refs, docs link.
2. Добавить reflection API для export enumeration и schema inspection.
3. Автоматизировать docs/reference generation из schema catalog.

Критерии приемки:

- tooling может перечислить все IR types и их поля без manual grep;
- docs/reference/ir и schema snapshots синхронизированы одной сборкой.

Покрывает:

- 5.4, часть E1/F2.

### WS-4B. Incremental / binary / streaming transport strategy

**Цель:** определить масштабируемый transport story для больших IR payloads.

Поверхности:

- `src/polisyos/ir/artifacts/**`
- `src/polisyos/ir/observation/**`
- `src/polisyos/ir/analytics/**`
- `docs/contracts/**`
- `docs/adr/**`

Задачи:

1. Спроектировать delta artifacts и incremental relinking model.
2. Оценить binary wire formats:
   protobuf, msgpack, Arrow IPC, FlatBuffers.
3. Определить, какие payload families остаются JSON-first, а какие получают
   optional binary transport.
4. Добавить streaming ingestion/update contracts для observation-heavy flows.

Критерии приемки:

- есть ADR по transport strategy и incremental update semantics;
- хотя бы один pilot artifact family имеет documented binary or delta path.

Покрывает:

- 5.2, 5.3;
- часть scale-oriented optimization backlog.

### WS-4C. Standards and ecosystem bridges

**Цель:** сделать IR понятным внешним системам и causal tooling ecosystem.

Поверхности:

- `src/polisyos/ir/world/**`
- `src/polisyos/ir/connectors.py`
- `src/polisyos/ir/analytics/**`
- `docs/reference/ir/**`

Задачи:

1. Добавить PROV-O aligned mapping для provenance/world contracts.
2. Спроектировать bridge contracts для SDMX, DDI, FHIR/CDISC там, где это
   релевантно observation and policy data.
3. Добавить causal ecosystem bridges:
   DoWhy, EconML, CausalNex/pgmpy, Tigramite PCMCI, discovery graph exchange.

Критерии приемки:

- bridge contracts documented и имеют conversion fixtures;
- provenance export можно интерпретировать через standard ontology mapping.

Покрывает:

- 7.1, 7.2, 7.3.

---

## Phase 5 — Frontier Causal and Policy Expressiveness

### WS-5A. Governance expressiveness roadmap

**Цель:** закрыть policy-language gaps после стабилизации core IR.

Задачи:

1. Добавить temporal logic layer для compliance and policy constraints
   (LTL/CTL/MTL subset with explicit execution semantics).
2. Спроектировать multi-level policy composition:
   federal/state/local overrides, compatibility constraints, policy versioning.
3. Расширить `SelectorExpr` quantifiers, aggregations и temporal predicates.
4. Добавить richer game/mechanism design contracts:
   extensive-form, Bayesian games, incentive compatibility,
   individual rationality, repeated-game metadata.

Покрывает:

- 4.1, 4.2, 4.3, 4.4.

### WS-5B. Causal frontier contracts roadmap

**Цель:** закрыть SOTA gaps в causal method surface без перегрузки core path.

Задачи:

1. Representation learning / latent confounder contracts:
   CEVAE-like, latent variable models, neural causal models, causal generative
   models.
2. Multi-environment / invariance contracts:
   ICP, IRM, anchor regression, environment-aware discovery.
3. Causal RL contracts:
   causal MDP/POMDP, counterfactual policy optimization, online graph learning.
4. Time-series and discovery outputs:
   PCMCI/Granger outputs, Hawkes/SDE/regime-switching SCM, PAG/MAG/CPDAG,
   edge confidence, equivalence classes, active experiment design.
5. Recourse and explanations:
   algorithmic recourse, counterfactual explanations, contrastive explanations.

Покрывает:

- 2.1, 2.2, 2.3, 2.4, 2.5, 2.6.

---

## Первые 10 практических изменений

Это не весь план, а рекомендуемый короткий execution slice, который дает
максимальный risk reduction за минимальное время:

1. Исправить `registry_fragments` так, чтобы invalid dependencies не попадали в
   `applied`.
2. Добавить topological sort + cycle detection для registry fragments.
3. Перевести unknown `_type` в `CanonViolation`.
4. Переписать dataclass canonicalization без `asdict()`.
5. Явно зафиксировать `exclude_none` policy в canon и tests.
6. Добавить recursion limits в `canon` и `world/ids`.
7. Убрать `assert` из validation paths и broad silent swallows из IR.
8. Ввести shared `ensure_unique_ids()` и перенести duplicated checks на него.
9. Вынести mutating normalization из `TransportabilityResult` и related models.
10. Добавить property-based tests для canon roundtrip, linker idempotency и
    registry composition determinism.

---

## Coverage appendix

Ниже — сводка, чтобы каждая группа находок из аудитов имела явный маршрут в
roadmap, а не оставалась "учтенной где-то в тексте".

| Audit cluster                          | Findings / topics                                          | Planned workstreams        |
| -------------------------------------- | ---------------------------------------------------------- | -------------------------- |
| Canon / CAS stability                  | K4-K6, H4-H9, M15, M17, L5-L6, L13, float/time/hash policy | WS-0A, WS-1C, WS-2C, WS-3C |
| Registry / linker correctness          | K1-K3, H2-H3, H6, M6, M9                                   | WS-0B, WS-2A, WS-3C        |
| Silent failures / runtime validation   | A1-A5, B, D3                                               | WS-0C, WS-3B               |
| Shared invariants / validation helpers | H12-H15, M1-M5, M10-M14, L1-L14                            | WS-1A, WS-1B               |
| Mutable analytics contracts            | E3, H10-H11, parts of M1-M4                                | WS-1B, WS-2C               |
| Pass infrastructure / type checking    | 1.1, 1.2                                                   | WS-2A, WS-1A               |
| Lineage / estimand normalization       | 1.3, 1.4                                                   | WS-2B                      |
| Uncertainty and numeric robustness     | 3.1, 3.2, 3.3, M16, L10                                    | WS-2C                      |
| API / import / architecture hygiene    | E1, E2, E4, F1-F3, D4, M12, L15                            | WS-3A, WS-3B               |
| Performance hot paths                  | C1-C3, D1-D2, H1-H3, M7-M8, O1-O8                          | WS-3B                      |
| Testing and verification               | 6.1, 6.2, 6.3, H7                                          | WS-3C                      |
| Introspection and schema catalog       | 5.4                                                        | WS-4A                      |
| Incremental / binary / streaming IR    | 5.2, 5.3                                                   | WS-4B                      |
| Standards / ecosystem bridges          | 7.1, 7.2, 7.3                                              | WS-4C                      |
| Governance expressiveness gaps         | 4.1, 4.2, 4.3, 4.4                                         | WS-5A                      |
| Frontier causal gaps                   | 2.1-2.6                                                    | WS-5B                      |

## D1 Docs Impact Table

| D1 doc cluster            | Exact files                                                                                                                                                                                                                                                                                                                                    | Source of truth                                                                                                   | Validation command or evidence                                                                                                                           | Backlog / priority |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------ |
| IR reference set          | `docs/reference/ir/index.md`, `docs/reference/ir/public-surface.md`, `docs/reference/ir/schema-catalog.md`, `docs/reference/ir/compiler-pipeline.md`, `docs/reference/ir/interoperability.md`, `docs/reference/ir/governance.md`, `docs/reference/ir/analytics.md`, `docs/reference/ir/observation.md`, `docs/reference/ir/problem-framing.md` | IR facades, schema catalog/reflection layer, pass pipeline, analytics and observation packages, governance models | `uv run pytest tests/unit/ir/test_public_surface.py tests/unit/ir/test_phase2_passes.py tests/unit/ir/test_uncertainty.py tests/unit/ir/test_interoperability_bridges.py -q` | none               |
| Shared reference surfaces | `docs/reference/schemas.md`, `docs/reference/public-surface.md`                                                                                                                                                                                                                                                                                | generated schema snapshots, public-surface manifests, architecture guardrails                                     | `uv run --extra ml polisyos-tools diagnostics gen-schema --check`                                                                                        | none               |
| Contract docs             | `docs/contracts/TRINITY.md`, `docs/contracts/MERGE_SEMANTICS.md`, `docs/contracts/E1_*.md`, `docs/contracts/E2_*.md`                                                                                                                                                                                                                           | Trinity/linker contracts, merge semantics, ABI/schema contracts, snapshot-linked tests                            | `uv run polisyos-tools diagnostics generate-ir-reference-catalog --check`                                                                                | none               |
| Package boundary READMEs  | `src/polisyos/ir/README.md`, `src/polisyos/ir/trinity/README.md`, `src/polisyos/ir/analytics/README.md`, `src/polisyos/ir/observation/README.md`, `src/polisyos/ir/governance/README.md`                                                                                                                                                       | package facades and subsystem boundaries                                                                          | `uv run pytest tests/contract/test_trinity_linker_contract.py tests/unit/ir/governance/test_phase5_governance_contracts.py -q`                                | none               |

D1 closure note: all required D1-L4 pages are present; further generator
consolidation belongs to D2 and does not block D1.

## Exit condition for the whole plan

План считается выполненным, когда одновременно выполнены все условия ниже:

- нет открытых critical/high findings из ваших аудитов без explicit accepted
  risk или отдельно утвержденного follow-up;

- `polisyos.ir` имеет documented pass pipeline, compatibility policy и schema
  catalog;

- canon/linker/registry/uncertainty invariants подтверждены regression,
  property и fuzz tests;

- public IR surface documented, import-safe и проверяется CI gate;
- дальнейшие SOTA extensions добавляются поверх stabilized contract layer, а не
  в обход него.
