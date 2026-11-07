# GRF-02 — Lossless mixed-edge transport и одна canonical preparation внутри query

**Исполнительская спецификация; финальная QA комплекта ещё ожидается.**
**LANE-05 · CP5 · B219, B220.** Основание `20d9009be21097bfbdc38a546a15cc60213b8ace`. Реализация документом не выполнена; все будущие проверки **NOT_RUN**. Именных исполнителя/reviewer назначает проект.

## 1. Практическая цель и область

Закрыть direct Kuzu endpoint-only identity contract и повторную внутреннюю preparation, не ломая правильные immutable snapshots, selected profiles и внешнюю revalidation. Native backend roundtrip должен сравнивать полный multiset, а не количество Python calls.

**Тип работы:** C49-R01 conditional public adapter repair; C49-R02 bounded performance repair; native backend/CAS qualification. Масштаб production loss/latency не установлен.

[Аудит](../05_Основания/Аудит/02_Пакеты/GRF-02.md) · [остатки](../05_Основания/Аудит/01_Реестры/C49_остатки.json) · [исходная карточка](../05_Основания/Аудит/05_Источники/GRF-02_исходные_строки.txt) · [источники](../05_Основания/Аудит/05_Источники/C49_источники.json) · [трассировка](../04_Трассировка/GRF-02.json). Полные диагностические scripts/logs остаются в отдельно доставленном ZIP фазы 1. Действуют [общие правила](../00_Общее/Правила_исполнения_и_приёмки.md).

## 2. Исходные обязанности и сохранение

B219 NetworkX MultiDiGraph уже сохраняет directed/bidirected/lag/duplicate occurrences с deterministic ordinals; Rustworkx/bulk Kuzu отдельные boundaries. B220 deep ordinary mutation refusal, detached rows, model_copy cache reset и content-keyed boundedLRU уже реализованы. Историческое weakref требование — не удерживать caller/unbounded state, а не обязанность вернуть unsafe object-id cache. A07 и static profile admission сохраняются.

- `preserve:0558`: Typed MultiDiGraph keys и multiplicity ordinals → REQ-GRF-02-02; TEST-GRF-02-03.
- `preserve:0559`: Deep ordinary mutation refusal и copy cache reset → REQ-GRF-02-04; TEST-GRF-02-05, TEST-GRF-02-06.
- `preserve:0560`: Detached returned rows и actual bulk CSV route → REQ-GRF-02-02, REQ-GRF-02-04; TEST-GRF-02-02, TEST-GRF-02-06.
- `preserve:0561`: Canonical caller admission, metadata identity и bounded cache capacity → REQ-GRF-02-03, REQ-GRF-02-04; TEST-GRF-02-04, TEST-GRF-02-05, TEST-GRF-02-06.
- `preserve:0562`: Existing native CAS/NetworkX permutation and loss controls → REQ-GRF-02-02, REQ-GRF-02-05; TEST-GRF-02-03, TEST-GRF-02-07.

## 3. Disposition полного остатка

| ID | Действие / причина | REQ / общий владелец |
|---|---|---|
| `C49-R01` | fix: Предварительный simple-only отказ и полезный existing bulk route; direct occurrence mode требует собственного native контракта. | REQ-GRF-02-01, REQ-GRF-02-02 |
| `C49-R02` | fix: Одна подготовка внутри query при сохранении внешней проверки. | REQ-GRF-02-03, REQ-GRF-02-06 |
| `C49-G01` | qualify: Каждый backend/CAS/profile проверяется native отдельно; recorder не доказывает backend. | REQ-GRF-02-02, REQ-GRF-02-04, REQ-GRF-02-05, REQ-GRF-02-06 |

Все source-registry remaining также связаны: `remaining:0347`, `remaining:0348`, `remaining:0349`. Подробная причина и REQ для каждой строки — в companion JSON; повторная запись не считается новым независимым дефектом.

## 4. Нормативный контракт

### REQ-GRF-02-01
Публичный direct to_kuzu не принимает graph, который endpoint-only MERGE не может представить без потери occurrences. Предпочтительный минимальный ремонт: до первого DB write отказать parallel/mixed/lag relation collisions и направить actual callers требуемого lossless export к существующему bulk materializer. Simple supported graph direct path остаётся полезен. Если выбран occurrence-aware direct mode, он сохраняет полный multiset и явно определённую repeat/idempotence semantics.
Источник: B219; C49-R01. Проверки: TEST-GRF-02-01, TEST-GRF-02-02.

### REQ-GRF-02-02
Lossless route сохраняет все relation payload fields и multiplicity: endpoints, marks, lag, confidence, sources/evidence refs/metadata. Перестановка input edges не меняет multiset; identical duplicates не deduplicate. Native NetworkX/Rustworkx/Kuzu квалифицируются отдельно, no inferred correctness другого backend.
Источник: B219; C49-G01, C49-R01. Проверки: TEST-GRF-02-02, TEST-GRF-02-03.

### REQ-GRF-02-03
Каждый public graph query сохраняет full canonical caller admission/current-content hash до cache lookup. Внутри одного admitted conditioned m_separation используется один detached prepared adjacency для traversal и ancestors(Z), без повторных full rebuild/hash. Private prepared helpers недоступны как caller-supplied bypass token/flag.
Источник: B220; C49-R02. Проверки: TEST-GRF-02-04, TEST-GRF-02-05.

### REQ-GRF-02-04
Frozen topology/nested metadata запрещают обычную mutation, model_copy(update) refreezes и сбрасывает все derived rows, public export rows detached. Content-equivalent objects могут reuse adjacency; изменённые metadata/profile/lag/marks проходят новый admission. Cache остаётся bounded128 entries и не удерживает исходный caller object.
Источник: B220; C49-G01, C49-R02. Проверки: TEST-GRF-02-05, TEST-GRF-02-06.

### REQ-GRF-02-05
Actual graph persist/fresh CAS load сохраняет exact selected profile/schema/metadata и full edge multiset. Historical inspection ref без выбранного profile не выдаётся за evidence-carrying selection. Mixed transport не превращает generic directed-path algorithm в causal separator; GRF-01 endpoint rules остаются принимаемым owner.
Источник: B219, B220; C49-G01. Проверки: TEST-GRF-02-03, TEST-GRF-02-05, TEST-GRF-02-07.

### REQ-GRF-02-06
Performance evidence отдельно измеряет preparation count и end-to-end runtime/RSS на объявленном конечном graph/query workload. Не обещать системный speedup из уменьшения3→1 hash calls и не отключать guards/cache ради benchmark. Fresh valid/invalid controls обязательны на warm и cold.
Источник: B220; C49-R02, C49-G01. Проверки: TEST-GRF-02-04, TEST-GRF-02-05, TEST-GRF-02-07.

## 5. Конкретное техническое решение

**Прямой экспорт Kuzu.** Текущий connection-only API выполняет MERGE связи по endpoints, а затем записывает marks/lag. До первого execute проверить весь граф: если одна упорядоченная пара endpoints содержит несколько occurrences, адресно отказать в direct-профиле. Простой граф продолжает работать; семантику повторного экспорта явно закрепить. Реальные callers смешанного графа направить в существующий `materialize_causal_kuzu_from_graph` с его владением database/path и проверками COPY/count. Не извлекать путь из произвольного connection и не очищать чужую БД молча. Это ограниченный ремонт без нового graph store. Если finite census подтвердит обязательный connection-only incremental multigraph, DEC-KUZU задаёт occurrence ID, учитывающий relation class, payload ordinal и graph scope, плюс транзакционную/versioned миграцию. Одних marks/lag недостаточно: одинаковые дубликаты всё ещё схлопнутся.

**Подготовка кэша.** `_get_cached_adjacency` остаётся полной внешней границей проверки. `m_separation` получает `CachedAdjacency` один раз и вычисляет traversal/ancestors из подготовленного объекта через private helpers, не вызывая повторно public `ancestors`. Public `ancestors(graph,...)` продолжает полную проверку. Предлагаемый private `_ancestors_from_prepared` принимает только созданную owner detached adjacency, не произвольный graph с skip-флагом. Существующие content key, profile и LRU сохраняются; глобальный prepared-session registry не нужен.

**Перенос и сохранение.** MultiDiGraph relation key/ordinal уже корректны; multiplicity Rustworkx проверяется отдельно. Export payload и detached rows сохраняются без потерь; native readback сравнивает полный multiset и selected profile, не только count. Текущий bounded content LRU допустимо отличается от прежней weakref-схемы: сохранить освобождение caller и предел ёмкости, не восстанавливать устаревшую реализацию. Frozen containers не обещают защиты от произвольной Python reflection, поэтому outer canonical rebuild обязателен.

### Текущие owners и источники

- [policy-engine/src/polisyos/ir/analytics/causal_graph.py:768–870](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/causal_graph.py#L768-L870)
- [policy-engine/src/polisyos/ir/analytics/causal_graph.py:956–1057](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/causal_graph.py#L956-L1057)
- [policy-engine/src/polisyos/ir/analytics/causal_graph_kuzu.py:94–203](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/causal_graph_kuzu.py#L94-L203)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/admg_ops.py:135–278](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/admg_ops.py#L135-L278)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/admg_ops.py:418–451](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/admg_ops.py#L418-L451)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/admg_ops.py:699–777](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/admg_ops.py#L699-L777)
- [policy-engine/tests/unit/ir/test_causal_graph_networkx_roundtrip.py:1–92](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/ir/test_causal_graph_networkx_roundtrip.py#L1-L92)

## 6. Проверки: setup → действие → oracle

TEST-ID обозначает требуемую проверку, не существующий одноимённый pytest test. Расширять указанные действительные места, не дублировать suites.

### TEST-GRF-02-01 · native direct export refusal before side effects
**NOT_RUN. REQ:** REQ-GRF-02-01.
**Setup:** Пять occurrences с одинаковыми endpoints: directed, bidirected, lag1, lag2 и одинаковый дубликат. Положительный простой directed graph; пустая test DB с действующей schema.
**Действие:** Вызвать actual to_kuzu в выбранном simple-only профиле; прочитать состояние БД до и после.
**Oracle:** Неподдержанный collision отклонён до записи nodes/edges; простой граф сохраняет exact payload и объявленную repeat/idempotence семантику. Нет last-write-wins. Для выбранного lossless direct варианта вместо отказа обязателен multiset/repeat oracle TEST-02.
**Место:** `tests/unit/ir/test_causal_graph_kuzu.py; causal_graph.py::to_kuzu`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-GRF-02-02 · native Kuzu lossless route/permutation
**NOT_RUN. REQ:** REQ-GRF-02-01, REQ-GRF-02-02.
**Setup:** Те же 5 occurrences во всех 120 permutations, isolated temp database, real selected Kuzu version/schema; bulk clear_on_start=True. Отдельно existing-data/incremental mode если поддержан.
**Действие:** Выполнить actual materialize_causal_kuzu_from_graph COPY→native query readback; сравнить полный нормализованный multiset rows, не только count.
**Oracle:** Ровно пять occurrences с правильными marks/lag/metadata/evidence; duplicates и permutation invariance сохранены. Count guard остаётся. Неподдержанная incremental policy отказывает до записи; production DB не используется. Callers смешанного графа действительно используют этот полезный путь, не получают только ошибку.
**Место:** `tests/unit/ir/test_causal_graph_kuzu.py; causal_graph_kuzu.py::materialize_causal_kuzu_from_graph`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-GRF-02-03 · native NetworkX/Rustworkx+CAS transport
**NOT_RUN. REQ:** REQ-GRF-02-02, REQ-GRF-02-05.
**Setup:** Existing CAS→fresh store→NetworkX multiset suite с 5 edges / 120 permutations; same finite graph to actual Rustworkx; selected profile variant.
**Действие:** Сохранить и загрузить canonical graph; actual adapters экспортируют полный payload. Отдельный removal control заменяет MultiDiGraph на DiGraph.
**Oracle:** Полный multiset, включая multiplicity duplicates, сохраняется; removal control обнаруживает потерю relation. Rustworkx отдельно сохраняет каждое add_edge occurrence/payload. Изменение копии metadata не меняет source. Отсутствующий backend — BLOCKED, не PASS по другому backend.
**Место:** `tests/unit/ir/test_causal_graph_networkx_roundtrip.py; tests/unit/ir/mirror_contracts/test_causal_graph.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-GRF-02-04 · native preparation-count regression
**NOT_RUN. REQ:** REQ-GRF-02-03, REQ-GRF-02-06.
**Setup:** Warm static ADMG, conditioned queryX,Y|Z; delegating counters around canonical snapshot and full content hash.
**Действие:** Один m_separation; repeated отдельных public ancestors calls; compare cold/warm answers with GRF-01 oracle.
**Oracle:** Один outer canonical rebuild/hash на public query; внутренние adjacency/An(Z) не повторяют его. Десять отдельных public calls каждый раз проверяют input. Ответы неизменны; unsafe skip_validation не появляется. Instrumentation вызывает настоящие методы.
**Место:** `tests/unit/foundry/methods/catalog/causal/test_admg_profile_consumers.py; admg_ops.py::m_separation`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-GRF-02-05 · native warm cache adversarial preservation
**NOT_RUN. REQ:** REQ-GRF-02-03, REQ-GRF-02-04, REQ-GRF-02-05, REQ-GRF-02-06.
**Setup:** Warm valid graph; controlled content corruption/serializer override/subclass/lag/PAG/endpoint/metadata change; cold new object same content; graph copy с пустыми edges.
**Действие:** Actual public query/admission, dump/export and fresh consumer.
**Oracle:** Невалидный current content отклонён даже при warm cache; допустимая новая metadata получает правильную identity. Одинаковый content может переиспользовать detached adjacency, не caller object. Empty copy не сохраняет старые ancestors/export; input и metadata неизменны. GRF-01 oracle сохраняется.
**Место:** `tests/unit/foundry/methods/catalog/causal/test_admg_profile_consumers.py::test_adjacency_cache_revalidates_full_content_before_reuse; existing selector verify before run`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-GRF-02-06 · native frozen/detached/cache capacity
**NOT_RUN. REQ:** REQ-GRF-02-04.
**Setup:** Nested graph/edge metadata,list/set containers; warm kuzu rows; mutate returned dict; create140 distinct valid contents then drop original caller weakrefs.
**Действие:** Existing cache-row tests plus GC/cache observation.
**Oracle:** Обычные mutations запрещены, возвращённые rows независимы, deepcopy/copy сбрасывают derived state согласованно. Обе bounded maps содержат не более128 entries; caller освобождается GC, хотя detached cache content может оставаться. Это не утечка и не причина возвращать старую weakref architecture.
**Место:** `tests/unit/ir/test_causal_graph_cache_rows.py; admg_ops.py::_ADJ_CACHE/_CC_CACHE`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-GRF-02-07 · native shared graph-consumer/measurement E02-I05-A
**NOT_RUN. REQ:** REQ-GRF-02-05, REQ-GRF-02-06.
**Setup:** Selected graph artifact, finite small/medium graph sizes и fixed query set, cold/warm phases; real static inference consumer.
**Действие:** Graph→CAS→fresh loader→query, считать preparation, record wall/RSS/backend/profile and correctness.
**Oracle:** Правильный structural answer/proof получен из exact selected graph; измерения показывают preparation reduction без универсального обещания latency. Default inspection ref не повышается до evidence profile. Корректная serialization не доказывает empirical causal structure.
**Место:** `E02-I05-A; test_causal_graph_networkx_roundtrip.py; actual CausalEngine route`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### Запуск: адаптируемый шаблон, не выполненная команда

Из `policy-engine/` в поддержанной Python3.14 среде с закреплёнными зависимостями. Этот документ не разрешает автоматические installs; отсутствующая dependency означает BLOCKED конкретной проверки.

```bash
python -V
python -m pytest -q tests/unit/ir/test_causal_graph_networkx_roundtrip.py tests/unit/ir/test_causal_graph_cache_rows.py tests/unit/ir/test_causal_graph_kuzu.py
python -m pytest -q tests/unit/foundry/methods/catalog/causal/test_admg_profile_consumers.py
# Optionalbackend BLOCKED не означает product defect; no dependency installs automatically.
```

Фиксировать профиль/backend, inputs/seed/hash, deciding output и exit. Ruff и затронутые architecture/import checks выбирать по фактическому patch; native slot согласовать, полный suite на каждый пакет не копировать.

## 7. Общая интеграция и ownership

Переиспользовать **E02-I05-A**: [канонический контракт LANE-05](../03_Интеграция/LANE-05.md). Одно свидетельство связывается с конкретными вариантами и REQ; не считается многими независимыми подтверждениями.

GRF-02 владеет direct export в causal_graph.py и private prepared-query helpers в admg_ops.py. Bulk owner causal_graph_kuzu участвует только при необходимости изменить фактический маршрут/schema. Semantic oracle GRF-01 общий, DAG normalization GRF-03 отдельно. Один writer на общий module; optional backend jobs выполняются раздельно в подготовленном профиле, никогда на production DB.

- **GRF-01:** Endpoint-aware semantics и outer canonical admission сохраняются, finite oracle общий.
- **GRF-03:** DAG export использует validated topology, отдельно от lossless mixed transport.
- **LANE-06 CAS owners:** Переиспользовать exact profile/native CAS, не новый graph store.

## 8. Совместимость, миграция и возврат

Ограничение simple-only намеренно отклоняет ранее неоднозначный parallel direct export до записи; существующий bulk route сохраняет полезный mixed graph export. Public signature не обязана меняться. Occurrence-aware direct mode требует явных schema/migration/repeat/rollback правил; старая БД не очищается молча. Cache refactor сохраняет public answers/types и historical graph bytes. Rollback сохраняет полную проверку и явное ограничение вместо тихой потери.

## 9. Free-grow и обоснованные границы

- [universal-policy-design-target-architecture-and-gap.md — D0 and reusable typed representations](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md): Typed relation occurrences сохраняют новые совместимые графы без специальных веток; общий prepared-query механизм уменьшает повторную работу.
- [policyos-identity-and-custody-boundary.md — Identity/profile and custody boundaries](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md): Одинаковый content blob/default manifest не заменяет exact selected profile; canonical content validation сохраняется до cache reuse.

## 10. Конечные решения и сдача

### DEC-GRF-02-KUZU
**Вопрос:** Есть ли реальный supported connection-only lossless incremental caller?
**Кто решает:** Graphadapter/Kuzu schema owner.
**Конечное действие/выход:** Конечный census actual callers/contracts. По умолчанию simple-only preflight и existing bulk route. Если подтверждён caller incremental multigraph, определить occurrence identity, graph scope, transaction/idempotence и schema migration; TEST-01/02 обязательно native.
**До решения:** Отказывать ambiguous direct export до первой записи; mixed export остаётся полезным через existing bulk.

### DEC-GRF-02-SCALE
**Вопрос:** Какой реальный query workload требует performancequalification?
**Кто решает:** Static causal query owner.
**Конечное действие/выход:** Выбрать finite representative sizes/query count/backend, cold/warm benchmark с output equivalence и peak RSS. Сдать числа и границы, не вводить произвольную цель ускорения.
**До решения:** Принять устранение лишней внутренней подготовки отдельно от неизмеренного системного ускорения.

Сдать base/head и patch, exact REQ→TEST→shared variant, исходные входы и их идентичности, actual команды/exit/log, независимые численные/семантические oracles, positive/negative/removal controls, сохранённые инварианты и открытые решения. Source-only, fixture, native и scientific qualification отражать отдельно. Не повышать partial/NOT_RUN до PASS; квалифицированный локальный механизм не является автоматической готовностью всей политики.
