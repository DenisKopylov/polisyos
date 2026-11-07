# GRF-02 — immutable graph, mixed-edge export и cache identity
## C49 · 1 ноября 2026 года

**Порядок:** 49/127, LANE-05. **Исходные IDs:** B219, B220. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Свежий аудит после внешнего сохранения восстановленного C48; потерянный прежний C49 не является доказательством.

## Решение

Основные ремонты полезны: NetworkX owner создаёт **MultiDiGraph с typed relation keys и deterministic occurrence ordinals**; graph containers запрещают обычную вложенную мутацию; copy сбрасывает derived rows; readers получают detached dictionaries; cache связан с canonical content и ограничен 128 entries.

Остались два ограниченных остатка:

1. **C49-R01:** прямой `to_kuzu` выдаёт endpoint-only MERGE без различения mixed/lag/duplicate relation occurrences. Подтверждён emitted contract; фактическое слияние в native Kuzu здесь **не наблюдалось**.
2. **C49-R02:** один conditioned `m_separation` даже на прогретом cache выполняет **3 canonical rebuilds и 3 full snapshot hashes**, включая повторную внутреннюю подготовку уже допущенного снимка. Внешний admission необходим и не должен удаляться.

**16 bounded MATCH; 12 неизменённых существующих test bodies / 27 cases исполнены изолированно.** MATCH включает воспроизведение R, не product PASS. Native pytest, NetworkX, Rustworkx и Kuzu отсутствуют; CAS/backend round-trip не исполнен. Полного закрытия нет.

## 1. Матрица исходных ID

| ID | Исходный механизм | Уже сделано и сохраняется | Остаток |
|---|---|---|---|
| B219 | DiGraph перезаписывал X→Y/X↔Y и разные lag records; порядок менял surviving payload | MultiDiGraph grouping по src/dst/marks/lag и sorted full payload + ordinal сохраняет distinct и identical duplicate occurrences. Actual emitter: 5 records во всех 120 permutations | R01: direct Kuzu contract; G01: native backend/CAS round-trip |
| B220 | Nested mutation расходилась с cached ancestors/export; copy переносила старые derived properties | Frozen nested standard containers; cache rows внутри tuple[str], снаружи detached dict; model_copy refreeze + сброс cache; canonical content admission и bounded LRU | R02: повторная подготовка внутри query; G01: поддержанная среда и scale qualification |

Исходная карточка 6035–6128 прочитана целиком. Предписание сохранить weakref-cleanup трактуется содержательно: не удерживать caller object и не вводить неограниченную память. Возвращать старый identity-only cache ради буквального совпадения механизма не требуется.

## 2. Producer → transport → consumer

`CausalGraphModel` и `CausalEdge` остаются владельцами typed graph content, endpoint marks, lag, metadata и evidence refs. `to_networkx` и `to_rustworkx` — экспортные представления, не новые causal inference engines. В static inference `CachedAdjacency` разделяет directed и bidirected множества; обычный directed-path algorithm поверх mixed multigraph не становится корректным m-separator автоматически. [S01:485–718](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/causal_graph.py#L485-L718) [S02:73–133](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/admg_ops.py#L73-L133)

Persist/load functions существуют: graph JSON проходит owned artifact route с version/profile selection, возвращается `CausalGraphModelRef`, а load использует exact owner admission. Default persist сохраняет historical inspection ref без selected profile; evidence-carrying caller должен запросить selected profile явно. Эти функции **прочитаны**, но настоящий FileSystemCAS/manifest/readback не запускался. [S01:956–1057](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/causal_graph.py#L956-L1057)

Найден существующий native test: CAS persist → fresh store reload → настоящий NetworkX 3.6.1 → сравнение **полного multiset payload**, включая duplicate multiplicity, для всех 120 permutations. Отдельный removal control заменяет MultiDiGraph на DiGraph и требует обнаружить потерю, а не просто сохранить marker. Сейчас этот файл только прочитан; его assertions не выданы за свежий PASS. [S08:1–92](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/ir/test_causal_graph_networkx_roundtrip.py#L1-L92)

## 3. Сохраняемый mixed-edge ремонт

NetworkX export группирует полную relation class `(src,dst,mark_src,mark_dst,lag)`, сортирует serialized payload и выдаёт ключ `(mark_src,mark_dst,lag,ordinal)`. Поэтому одинаковый payload не схлопывается: одинаковые records различаются ordinal, а перестановка исходных edges не меняет отображение ключа в payload. [S01:768–812](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/causal_graph.py#L768-L812)

**P01/P02:** actual `to_networkx` выдаёт те же 5 records в 120 permutations (directed, bidirected, lag1, lag2 и duplicate); изменение returned metadata не меняет graph. Backend здесь **MultiRecorder**, реализующий только нужные методы приёма и чтения: проверен producer key/payload contract, а не настоящая NetworkX implementation. Дополнительно исполнены 11 случаев из трёх существующих mixed/single export test bodies; полный payload oracle в настоящем NetworkX остаётся G01.

Rustworkx owner передаёт отдельный `add_edge` для каждой IR occurrence и полный payload без src/dst. Его source проверен, но backend не запускался: сохранение multiplicity в настоящей версии Rustworkx отдельно не аттестовано. [S01:745–766](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/causal_graph.py#L745-L766)

## 4. C49-R01 — direct Kuzu и bulk route различаются

Actual `to_kuzu` для каждого edge сначала выбирает source/destination и отправляет один и тот же pattern:

```text
MERGE (s)-[r:CausalEdge]->(d)
SET r.mark_src = ..., r.mark_dst = ..., r.lag = ..., ...
```

Relation type, lag и occurrence ordinal не участвуют в identity pattern. **P08:** QueryRecorder получил пять distinct payload calls, но один и тот же endpoint-only pattern. Это локально подтверждённый недостаток emitted contract для mixed/duplicate export. Возможное слияние/перезапись при исполнении этого MERGE — вывод из контракта, **не измеренный native DB результат**. По lexical search прямые calls найдены только в двух tests; production use не установлен. Приоритет средний условный для пользователей публичного adapter, не утверждение о повреждённой production базе. [S01:837–870](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/causal_graph.py#L837-L870)

Соседний **bulk materializer** нельзя смешивать с этим дефектом. Actual CSV helpers сохраняют по строке на occurrence; P07 получил все пять rows, marks и lag. Materializer по source использует COPY, затем сравнивает node/edge counts с IR и имеет cleanup. DDL и весь owner прочитаны; настоящий COPY/count path не запускался. [S04:94–203](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/causal_graph_kuzu.py#L94-L203) [S05](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/ddl/kuzu_causal.cypher)

Минимальное направление — согласовать существующую direct boundary с occurrence-aware/lossless route либо явно ограничить её простым графом. Не создавать второй graph store. Приёмка должна различать duplicate multiplicity и lag/marks на реальном backend, а не только число Python calls.

## 5. Frozen topology, copy и cache: что действительно исправлено

**P03–P06** и existing row tests подтверждают:

- Обычные `clear`, `append` и nested mutations для graph/edge metadata отклоняются.
- После прогрева `model_copy(update={'edges': []})` не наследует старые Kuzu rows; dump, cold graph и ancestors(Y) согласованы, исходный graph сохранён.
- Внутренний row cache — tuple serialized strings; публичные readers каждый раз возвращают отдельные plain dictionaries. Даже очистка returned row потребителем не портит следующий export.
- Recursive deepcopy controls существующих frozen containers исполнены отдельно.

Это не обещание защиты от любого Python reflection/base-class bypass: caller content всё равно должен проходить canonical admission. [S01:401–484](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/causal_graph.py#L401-L484) [S01:690–715](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/causal_graph.py#L690-L715) [S01:814–835](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/causal_graph.py#L814-L835)

**P11–P14:** content-equivalent object переиспользует adjacency; изменённая metadata получает новый key; вмешательство в lag после прогрева не обходит guard. После 140 distinct contents обе cache maps имеют 128 entries, исходный caller собран GC, detached cached content может остаться. Это ограниченная content retention, не old weakref lifecycle и не установленная утечка. Existing complete cache revalidation test дополнительно выполнен unchanged, включая endpoint/lag/graph-type/metadata изменения и GC. [S02:135–278](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/admg_ops.py#L135-L278) [S09:1186–1281](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/methods/catalog/causal/test_admg_profile_consumers.py#L1186-L1281)

## 6. C49-R02 — не удалять guard ради ускорения

При каждом публичном `ancestors` выполняется полноценная проверка текущего caller content и hash. P10 насчитал 10 rebuild/hash для 10 warm calls при reused adjacency. **Сам этот внешний guard оправдан** защитой от stale/forged input; его наличие не объявляется ошибкой.

Различающий **P15** относится к **одному** conditioned query: outer `_validate_static_admg` уже получает canonical cached graph, затем `_m_separation_adjacency` и `ancestors(Z)` снова проходят full reconstruction/hash. Счётчики-обёртки делегируют настоящим functions без изменения результата: **3 rebuilds + 3 hashes**, корректный separator result. Именно дополнительная внутренняя подготовка оставляет невыполненной исходную цель «подготовить одну реальную версию, не хэшировать её при каждом внутреннем BFS». [S02:209–278](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/admg_ops.py#L209-L278) [S02:699–777](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/admg_ops.py#L699-L777)

Это низкоприоритетный bounded performance residual: production latency, memory bytes и большой ID workload не измерялись. Исправление должно переиспользовать уже допущенный detached snapshot **внутри** query, сохраняя полный внешний admission, cache limits и negative controls. Нельзя вернуть trust по object-id или считать любой caller immutable лишь по frozen marker.

## 7. Проверки и пределы

Полностью прочитан `test_causal_graph_cache_rows.py`; 7 bodies / 14 cases исполнены. Из graph contract suite выполнены 4 bodies / 12 cases; из profile-consumers — 1 cache body. Итого **12 / 27** через AST с удалёнными decorators, actual product functions, minimal `pytest.raises` fixture и явным MultiRecorder. Native NetworkX+CAS suite только прочитан. Python 3.12/Pydantic 2.13.4 не соответствуют declared project profile; native pytest и optional imports завершились exit 1 до execution.

Один расширенный probe сначала ожидал 2 hash calls, но увидел 3: исходник подтвердил, что outer admission тоже хэширует. Не продукт менялся под ожидание, а исправлено неверное число в harness; прежний failure сохранён. **C49-G01** требует supported native backend/CAS replay и отдельного измерения масштаба. Graph serialization correctness не устанавливает достоверность causal structure или empirical authority.

[Результаты](../04_Проверки/C49_GRF02/bounded_diagnostics.json) · [Команды](../04_Проверки/C49_GRF02/commands.json) · [Native-границы](../04_Проверки/C49_GRF02/native_verification.json) · [Источники](../05_Источники/C49_источники.json) · [Остатки](../01_Реестры/C49_остатки.json).

**49/127 пакетов рассмотрены ограниченно; 118 уникальных B/LA частично оценены. Следующий — GRF-03. Полного закрытия нет.**
