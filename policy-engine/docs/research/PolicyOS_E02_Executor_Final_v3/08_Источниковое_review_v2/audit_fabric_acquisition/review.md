# Source-led review: Fabric, acquisition и native boundaries (LANE-07/08/09)

## Итог

Проверены **25 текущих v2 пакетов**, 112 REQ и 115 TEST, по каждому — все **70 критериев** frozen catalog: **1750 dispositions**. Прочитаны полные packet MD, семантические поля и уникальная metadata JSON, применимые общие правила/owners и shared bindings. Исторические v1 snapshots внутри `07` не подменяли цель.

**Два узких уточнения контракта/приёмки:** FAC-01 (UDF-02, фаза atomic failure) и FAC-02 (CAL-01↔I07-C-B01, source/target predicate). Это не два доказанных runtime bug. Остальные 23 пакета не получили новых findings после проверки shared/general правил. Их оценки не означают, что implementation выполнена или native квалификация уже прошла.

Статусы ledger: 631 addressed, 428 bounded, 683 not_applicable, 8 gap, 0 unresolved. Восемь gap-dispositions ссылаются на **два**, а не восемь дефектов. `addressed` означает достаточную постановку будущего evidence; `bounded` — законный предел claim; N/A обоснован конкретной owned boundary. **Все native/product TEST: NOT_RUN.**

## Метод и источники

Каталог `catalog/criteria_catalog.json`, SHA-256 `8c8c77e13d9151349b7410b441f97f0f94fbfb7d097150f32c9872fe35a3cb59`, заморожен до этого аудита. Все70 нормализованных критериев рассмотрены; source URL/version/locator и ограничения доступны в coverage/catalog. Полноценное исследование источников выполнено source-phase командой; здесь использован frozen record, без заявления о повторном открытии всех внешних страниц.

Основы двух новых выводов: согласованность/проверяемость из [NASA Appendix C](https://www.nasa.gov/reference/appendix-c-how-to-write-a-good-requirement/), явный смысл/authority интерфейса из [NASA Appendix L](https://www.nasa.gov/reference/appendix-l-interface-requirements-document-outline/) и управление изменениями из [NASA 6.3](https://www.nasa.gov/reference/6-3-interface-management/). Это guidance, не обязательный для E02 стандарт. [PostgreSQL 18 async commit](https://www.postgresql.org/docs/18/wal-async-commit.html) поддерживает общий критерий различения logical success/durability, но не описывает Python filesystem owner: решающее свидетельство FAC-01 — actual `atomic.py` и current common/CAS-02 contract.

Общие E02-GREQ-01…10, atomic owner row, qualification/free-grow/freeze/resource rules прочитаны до признания omission. Shared scenarios не заменяют локальные controls и не считаются независимым повтором одного evidence. Не назначались новый SLA, all-platform support, глобальный exactly-once, universal framework, новый legal ledger или безусловный custom numeric accumulator.

## Подтвержденные уточнения

### FAC-01 — UDF-02: failed atomic write не всегда оставляет prior file

`TEST-UDF-02-01` включает fsync/replace controlled failures, но oracle без фазы требует «failed atomic write сохраняет prior file». Actual `atomic_write_bytes` делает file fsync→replace→directory fsync (`atomic.py:25–27`), и последний fsync может выбросить ошибку уже после видимой замены (`55–63`). Common atomic row и CAS-02 уже верно запрещают обещать rollback после replace. Поэтому проблема в несогласованном локальном acceptance oracle, а не в доказанной поломке kernel.

**Минимальная замена:** до успешного replace — prior file неизменен и own temp очищен; после successful replace — новые bytes видимы, при directory-fsync error durability не установлена и old-file rollback не обещан; фазу/исход выразить existing error/reporting contract. Exact legacy JSON/NPZ/Parquet профили, existing atomic owner и fresh reader сохранить. Будущие tests отдельно inject pre-replace и post-replace failures. Полный текст замены и evidence — `findings.json`.

### FAC-02 — CAL-01↔I07-C-B01: уникальность source не равна уникальности target

Local REQ-CAL-01-01 требует finite source/target и rejects duplicate source без declared policy; §5 сохраняет explicit target coordinate semantics/order. Binding `E02-I07-C-B01` сжимает это до «finite unique source/target axes». Existing interpolation вычисляет каждый target query и сохраняет report axis. Для declared interpolation-query profile pairs(0,0),(1,10),(2,20), target[.5,.5,1.5] дают[5,5,15] без неоднозначного source. Это объясняющий арифметический пример, не выполненный NumPy/JAX test и не утверждение допустимости repeated model-time для любой модели.

**Минимальная замена binding:** finite source/target; duplicate source reject absent declared meaningful policy; explicit target admission по declared coordinate/model contract, без скрытых sort/dedup. Если конкретная модель требует strictly increasing/unique target, это согласованное local/profile precondition с отдельным negative, не общий shorthand. Paired ordering, units/support, endpoint fill, immutable history и CAL02/06 one-writer сохранить. Cross-check CAL02/CAL05/actual downstream предоставлен foundry reviewer, не посчитан отдельным runtime witness.

## Важные корректные решения v2, которые не переоткрыты

- UDF-05 проверяет **raw indices до np.asarray**, включая mixed large-int/float и int64 edges; прежняя loss-before-check ошибка не повторена как новое finding.

- DFI-03 direct **harvest остается async pipeline**, синхронный receipt wrapper его не объявляет своим supported stage; smart/off/current basis различены.

- SCL-01 допустимый offline cache hit имеет **network0/DNS0** и current pure-policy проверку; принудительная DNS revalidation не добавлена.

- FED-01 предлагает **statistics.mean CPython3.14**, не fmean/overflow-prone median, с Fraction/Decimal independent oracle и finite qualification DEC; bespoke accumulator не навязан.

- EMB-01/03 отделяют конечный non-tied HNSW topology профиль и stronger heldout retrieval utility; >=3, k<N, declared ef, actual local asset/runtime и withdrawal/fresh controls уже есть.

- ING recovery/dedup ограничены stated horizon/profile; NET physical ownership не сводится к counters; LLM optional telemetry не отменяет mandatory accounting, а reuse не подменяет current authorization.

## По каждому пакету

### LANE-07

#### UDF-01

**Вердикт:** новых обоснованных пробелов не выявлено в заявленном scope; это не implementation PASS.

- **Способность/условия:** Lazy facade, D4 producer→CAS→Scientist и materialize/DAG closure остаются у canonical owners. Contract-only import не активирует builder siblings; explicit facade access активирует их; пять positional DTO полей и post-builder validation сохраняются.

- **Реальная граница и oracle:** Exact D4 bytes/path/schema и required stage denials передаются actual readAPI/Scientist parser; mutated input-list не меняет saved contract. Fresh real Python loader без package shells; alias function identity; actual D4 CAS read→Scientist positive и четыре stage negative.

- **Отказы/история:** Missing/cyclic DAG, invalid после builder, mutated list и disjoint output paths различены. Narrow aliases и first-five positional constructor ABI сохраняются; historical callers квалифицируются до retirement.

- **Предел доказательства/стоимость:** Полезная synthetic/D4 цепочка не равна governance admission или эмпирическому доказательству; все native TEST NOT_RUN. Не обещана latency/import-time экономия: проверяется activation set; общий resource policy не является SLA.

- **Точная трасса:** `02_Пакеты/UDF-01.md` §4–§9; REQ-UDF-01-01; REQ-UDF-01-02; REQ-UDF-01-03; REQ-UDF-01-04; TEST-UDF-01-01; TEST-UDF-01-02; TEST-UDF-01-03; TEST-UDF-01-04; companion `04_Трассировка/UDF-01.json`. Полные70 отдельных обоснований/ссылок — `assessments.json`.

#### OBS-01

**Вердикт:** новых обоснованных пробелов не выявлено в заявленном scope; это не implementation PASS.

- **Способность/условия:** Calendar semantics проходят producer, native Parquet/CAS и fresh observations consumer. Inclusive M/Q/Y periods; invalid/missing evidence не заменяется текущим годом; historical derived date допустима только при достаточных period IDs.

- **Реальная граница и oracle:** 1900/2000/2024/2100 leap boundaries, duplicate labels при unique parser calls; stored period/version должен совпасть с recomputation. Native Parquet→CAS fresh reader→actual observation dates; forged and unknown version controls; original bytes/hash неизменны.

- **Отказы/история:** Invalid calendar и unverifiable history остаются unknown/refused, а valid leap/period и aliases продолжают работать. Finite inventory различает new derived outputs и unchanged old bytes; shared UDF-02 phase closure не удаляет aliases.

- **Предел доказательства/стоимость:** Не восстанавливаются отсутствующие исторические факты догадкой; immutable provenance не объявляется current authority. Parser-call dedup — точный счетчик работы, не доказательство wall/RSS или произвольной скорости.

- **Точная трасса:** `02_Пакеты/OBS-01.md` §4–§9; REQ-OBS-01-01; REQ-OBS-01-02; REQ-OBS-01-03; REQ-OBS-01-04; TEST-OBS-01-01; TEST-OBS-01-02; TEST-OBS-01-03; TEST-OBS-01-04; companion `04_Трассировка/OBS-01.json`. Полные70 отдельных обоснований/ссылок — `assessments.json`.

#### UDF-02

**Вердикт:** уточнить FAC-01; остальная постановка сохраняется.

- **Способность/условия:** Existing IO и synthetic bindings получают native/consumer qualification без смены serializer или empirical authority. Selected native stage profile и selected snapshot; synthetic fallback различает absent/empty/nonempty, subset и identity warnings.

- **Реальная граница и oracle:** Legacy JSON exact bytes, NPZ arrays/metadata и Parquet schema/index=False; snapshot→load intake→prepare/build bindings→actual consumer. Native formats/CAS/atomic owner; actual bindings receipt с input basis; synthetic payload не содержит observation IDs.

- **Отказы/история:** Missing required validation/contract, empty proxy/fallback и source nonmutation; atomic fault phases требуют FAC-01. Sequential scheduler, materialize, academic read-only, aliases и historical bytes сохраняются; no repeat move.

- **Предел доказательства/стоимость:** consumer_required не validation; qualified synthetic mechanism не empirical observations; native TEST NOT_RUN. Существующий sequential memory scheduler/order/budget сохраняется; новое performance обещание не вводится.

- **Точная трасса:** `02_Пакеты/UDF-02.md` §4–§9; REQ-UDF-02-01; REQ-UDF-02-02; REQ-UDF-02-03; REQ-UDF-02-04; TEST-UDF-02-01; TEST-UDF-02-02; TEST-UDF-02-03; TEST-UDF-02-04; companion `04_Трассировка/UDF-02.json`. Полные70 отдельных обоснований/ссылок — `assessments.json`.

#### OBS-02

**Вердикт:** новых обоснованных пробелов не выявлено в заявленном scope; это не implementation PASS.

- **Способность/условия:** Captured Parquet snapshot обрабатывается checkpointed bounded export→DuckDB merge→fresh CAS manifest. Retry только reader-phase, с confirmed cursor; mapper/conversion/permission failures не повторяются как reader error.

- **Реальная граница и oracle:** Один captured snapshot; rebatching 2+2/3+1/1+3/4 дает exact rows, counters, immutable shards и фактический merged output. Native stream/Parquet/DuckDB/CAS; intermetric failure и fresh reader проверяют no partial publication; reader handle действительно закрывается.

- **Отказы/история:** Incomplete outputs=[]; failed reader после progress не теряет/дублирует rows; cancellation cleanup, disk/hash failure и rerun generation isolation. Новая generation не смешивает old diagnostics/shards; сохранены пригодные diagnostic artifacts без ложного complete.

- **Предел доказательства/стоимость:** Process/reader failure profile ограничен; не заявлена OS/power-loss atomicity или global exactly-once. Declared batch/disk/size bounds и physical counters; нет произвольного throughput SLA.

- **Точная трасса:** `02_Пакеты/OBS-02.md` §4–§9; REQ-OBS-02-01; REQ-OBS-02-02; REQ-OBS-02-03; REQ-OBS-02-04; TEST-OBS-02-01; TEST-OBS-02-02; TEST-OBS-02-03; TEST-OBS-02-04; companion `04_Трассировка/OBS-02.json`. Полные70 отдельных обоснований/ссылок — `assessments.json`.

#### UDF-04

**Вердикт:** новых обоснованных пробелов не выявлено в заявленном scope; это не implementation PASS.

- **Способность/условия:** Workspace/bootstrap guard и installed console связываются с фактическим pytest subprocess receipt. No usable checkout→typed unavailable до server policy и 0 subprocess; usable checkout→server guard до execution.

- **Реальная граница и oracle:** Workspace/build-root aliases, paths with spaces; receipt collection/setup/call/teardown из одного actual child и attempt/source. Installed console запускает native selected pytest; missing phase/wrong source/attempt receipt не считается completion.

- **Отказы/история:** Unavailable checkout, guard refusal и incomplete subprocess evidence проверяются отдельно от успешного локального run. Alias conflict и workspace/buildroot behavior сохранены; deployment остается отдельным разрешенным действием.

- **Предел доказательства/стоимость:** Spec не разрешает install/deployment; runner receipt не production deploy и не runtime/scientific authority. Subprocess count=0 на guard failures — observable bound, не SLA test suite.

- **Точная трасса:** `02_Пакеты/UDF-04.md` §4–§9; REQ-UDF-04-01; REQ-UDF-04-02; REQ-UDF-04-03; REQ-UDF-04-04; REQ-UDF-04-05; TEST-UDF-04-01; TEST-UDF-04-02; TEST-UDF-04-03; TEST-UDF-04-04; TEST-UDF-04-05; companion `04_Трассировка/UDF-04.json`. Полные70 отдельных обоснований/ссылок — `assessments.json`.

#### UDF-05

**Вердикт:** новых обоснованных пробелов не выявлено в заявленном scope; это не implementation PASS.

- **Способность/условия:** Целостный role-owned demographic bundle сохраняет вычислительные значения, metadata и exact integer identity. Whole-layout new/legacy admission до fallback; invalid new не трактуется как legacy; raw index validity до np.asarray.

- **Реальная граница и oracle:** targets/priors/donor owners; reserved owner metadata last; exact int64 including mixed 2**53+1/1.0, bool/fractional/range rejection, signed record IDs. Actual inventory→builder→selected CAS→fresh reader→pure aging/Foundry; exact values/metadata/index controls, source/export nonaliasing.

- **Отказы/история:** Role conflicts reject, exact duplicates allowed; optional donor допустим, candidate entrants missing reject, legacy zero явно qualified. Нельзя отбрасывать legacy metadata/role fields, молча coercion индексов или мутировать source; supported legacy layout остается.

- **Предел доказательства/стоимость:** Source facts unknown не превращаются в authority; no scientific suitability claim от fixture. Index and shape validation ограничены конкретным DTO/layout; нет требования универсального data framework.

- **Точная трасса:** `02_Пакеты/UDF-05.md` §4–§9; REQ-UDF-05-01; REQ-UDF-05-02; REQ-UDF-05-03; REQ-UDF-05-04; REQ-UDF-05-05; REQ-UDF-05-06; TEST-UDF-05-01; TEST-UDF-05-02; TEST-UDF-05-03; TEST-UDF-05-04; TEST-UDF-05-05; TEST-UDF-05-06; companion `04_Трассировка/UDF-05.json`. Полные70 отдельных обоснований/ссылок — `assessments.json`.

#### FED-01

**Вердикт:** новых обоснованных пробелов не выявлено в заявленном scope; это не implementation PASS.

- **Способность/условия:** Finite binary64 aggregation и cell-specific lineage квалифицируются отдельно от empirical reliability. Scalar MEDIAN валидирует даже singleton; midpoint двух центральных только; nearest source vs aggregate различаются; null-key multiplicity bounded.

- **Реальная граница и oracle:** Finite mean/midpoint CPython3.14 statistics.mean profile; Fraction exact oracle/Decimal crosscheck; extreme/subnormal/cancellation and per-cell trust/source lineage. Independent rational result, target rounding/ULP=0 profile, actual federated fetch→artifact→cold SQL reader; cells 10/200 не выбираются row-wide trust.

- **Отказы/история:** Nonfinite, overflow-prone inputs, repeated null keys/m:m amplification и invented source IDs запрещены; ordinary policies сохранены. Один lower-common helper FED-01→UQS; existing policies/lineage names preserved; wrapper qualification DEC-FED01-01, не bespoke numeric rewrite.

- **Предел доказательства/стоимость:** CPython3.14 helper qualification pending bounded DEC; arithmetic correctness не независимость источников и не quality of evidence. Замер cost выбранной helper/workload и ordinary baseline; custom implementation только при измеренном/совместимом основании, не произвольный SLA.

- **Точная трасса:** `02_Пакеты/FED-01.md` §4–§9; REQ-FED-01-01; REQ-FED-01-02; REQ-FED-01-03; REQ-FED-01-04; REQ-FED-01-05; TEST-FED-01-01; TEST-FED-01-02; TEST-FED-01-03; TEST-FED-01-04; TEST-FED-01-05; companion `04_Трассировка/FED-01.json`. Полные70 отдельных обоснований/ссылок — `assessments.json`.

#### FED-02

**Вердикт:** новых обоснованных пробелов не выявлено в заявленном scope; это не implementation PASS.

- **Способность/условия:** Typed empty UNION и scoped join audit сохраняют output while bounding retained diagnostics/work. No sources failure отличается от valid empty; declared nullable z type известен даже когда поле отсутствует во всех source rows.

- **Реальная граница и oracle:** Full schema empty output; FULL/SUMMARY/NONE одинаковые result rows; cap1 сохраняет total80/dropped79, local source indexes не global cache. Native DataFrame/SQL consumers и schema; weakref/GC controls фактического retained audit; cold/warm workload cost.

- **Отказы/история:** concat([]), unknown type guessed default, result-only cap и global mutable index не проходят oracle. FED-01 common numeric owner/lineage сохраняется; audit mode/cap не меняет query result или error.

- **Предел доказательства/стоимость:** Retention bound не только размер returned log; zero sources не становится success; performance claim только measured workload. Construction frequency, wall/peak RSS и cardinality входят qualification; local index не обоснован одним op-count.

- **Точная трасса:** `02_Пакеты/FED-02.md` §4–§9; REQ-FED-02-01; REQ-FED-02-02; REQ-FED-02-03; REQ-FED-02-04; REQ-FED-02-05; TEST-FED-02-01; TEST-FED-02-02; TEST-FED-02-03; TEST-FED-02-04; TEST-FED-02-05; companion `04_Трассировка/FED-02.json`. Полные70 отдельных обоснований/ссылок — `assessments.json`.

#### CAL-01

**Вердикт:** уточнить FAC-02; остальная постановка сохраняется.

- **Способность/условия:** Один temporal/unit/support смысл передается observation→target→native optimizer/report. Finite source/target, unique source absent explicit duplicate policy; positional only when selected; explicit target follows declared coordinates/order.

- **Реальная граница и oracle:** Paired time/value/mask/metadata sort до inferred grid; whole-series units/intervals; zero/fill/no support различены. Independent steps2 axis[0,2] values[0,20], explicit [.5,1.5]→[5,15]; actual compiler/preflight/JAX optimizer→persisted report.

- **Отказы/история:** Duplicate source/nonfinite/missing column, mixed share/percent without declared conversion, same-period ambiguity и empty support refused. Historical reports immutable; semantic delta input/version bound, no ID/trust winner; CAL02/06 shared preflight writer.

- **Предел доказательства/стоимость:** Native tiny model proves route not empirical scientific adequacy; target admissibility не универсальный physical-units framework. Нативный optimizer один shared lane10 witness; не отдельный heavy run для каждого local TEST и не throughput обещание.

- **Точная трасса:** `02_Пакеты/CAL-01.md` §4–§9; REQ-CAL-01-01; REQ-CAL-01-02; REQ-CAL-01-03; REQ-CAL-01-04; REQ-CAL-01-05; TEST-CAL-01-01; TEST-CAL-01-02; TEST-CAL-01-03; TEST-CAL-01-04; TEST-CAL-01-05; companion `04_Трассировка/CAL-01.json`. Полные70 отдельных обоснований/ссылок — `assessments.json`.

### LANE-08

#### DFK-02

**Вердикт:** новых обоснованных пробелов не выявлено в заявленном scope; это не implementation PASS.

- **Способность/условия:** Registry/catalog projection имеет один predicate и actual ModuleSpec consumers, а не duplicated constructors. Strict YAML duplicate keys/IDs/bool aliases; None vs explicit () distinguish; only enabled present acyclic stages admitted.

- **Реальная граница и oracle:** 35 ordered full-field exports, canonical YAML refs, actual connector→ModuleSpec; seed registered и dependency closure реальны. Native registry load/export/consumer plus same-stat byte mutation with warm/fresh clients and reissued receipt.

- **Отказы/история:** Missing/cyclic/disabled stages and stale receipt reject; counterfeit placeholder seed не проходит positive closure. Public ordered export ABI сохранен; YAML owner один, no hardcoded construction duplicate; bytes change invalidates old basis.

- **Предел доказательства/стоимость:** Included profile predicate не обещает executable projection without actual connector; unrelated historical variants не guessed. Small immutable registry scan допустим; optimization только measured workload, не индекс любой ценой.

- **Точная трасса:** `02_Пакеты/DFK-02.md` §4–§9; REQ-DFK-02-01; REQ-DFK-02-02; REQ-DFK-02-03; REQ-DFK-02-04; TEST-DFK-02-01; TEST-DFK-02-02; TEST-DFK-02-03; TEST-DFK-02-04; companion `04_Трассировка/DFK-02.json`. Полные70 отдельных обоснований/ссылок — `assessments.json`.

#### DFI-01

**Вердикт:** новых обоснованных пробелов не выявлено в заявленном scope; это не implementation PASS.

- **Способность/условия:** Data Fabric core owners, bindings context и durable DB payload доходят до actual pipeline consumer. Finite binding values without broadcast; ContextVar scopes reset nested/async/thread/cancel; phase1 LA038 не все6leaves.

- **Реальная граница и oracle:** Native DB 13-field payload, condition-aware IDs/chunks2/2/1; attempt/insert/replace counts, source filters/budgets per existing Fabric boundary. Actual canonical writers/validators/loaders и DB profile; simultaneous contexts A/B plus cancellation, input immutability.

- **Отказы/история:** Legacy facade не заменяет canonical consumer; scope leaks, coercion/broadcast, incorrect attempts vs inserted count are discriminated. Existing sources/callers retain behavior; wrappers do not duplicate HTTP implementation, one owner shared with DFI02.

- **Предел доказательства/стоимость:** Phase1 evidence не closure всех pipeline leaves; native/provider transport scope отдельно. Budget/physical-write counters tested; whole-system throughput and cost mix not inferred.

- **Точная трасса:** `02_Пакеты/DFI-01.md` §4–§9; REQ-DFI-01-01; REQ-DFI-01-02; REQ-DFI-01-03; REQ-DFI-01-04; TEST-DFI-01-01; TEST-DFI-01-02; TEST-DFI-01-03; TEST-DFI-01-04; companion `04_Трассировка/DFI-01.json`. Полные70 отдельных обоснований/ссылок — `assessments.json`.

#### DFI-02

**Вердикт:** новых обоснованных пробелов не выявлено в заявленном scope; это не implementation PASS.

- **Способность/условия:** Canonical all-six-leaf pipeline closure и wrapper identity дают реальные resumed lease/budget receipts. Direct saved wrapper d1 survives lookup d2 then restoration; custom overrides scope-local, no global broadcast/recursion.

- **Реальная граница и oracle:** empty_shards exact stats/manifest with absent-receipt warning; all7metrics, source filters/budgets and existing DB/lease profile. Actual 6 leaf consumers + architecture checker; bounded weakmap or stable delegate; resume does not duplicate budget/effects.

- **Отказы/история:** Wrapper recursion/stale owner/global override, absent receipt silently good, duplicate failed-attempt spending discriminated. One canonical pipeline and caller census, DFI01 prerequisite closure; legacy wrappers retain signature/ownership.

- **Предел доказательства/стоимость:** No requirement of global exactly-once; lease and evidence claims only declared native profile; checker alone not whole capability. Bound wrapper retention and actual budgets; no fabricated RSS/latency gain from interface refactor.

- **Точная трасса:** `02_Пакеты/DFI-02.md` §4–§9; REQ-DFI-02-01; REQ-DFI-02-02; REQ-DFI-02-03; REQ-DFI-02-04; TEST-DFI-02-01; TEST-DFI-02-02; TEST-DFI-02-03; TEST-DFI-02-04; companion `04_Трассировка/DFI-02.json`. Полные70 отдельных обоснований/ссылок — `assessments.json`.

#### EMB-01

**Вердикт:** новых обоснованных пробелов не выявлено в заявленном scope; это не implementation PASS.

- **Способность/условия:** Academic/Catalog preparation сохраняет native HNSW topology и declared semantic profile. Selected dimension follows actual domain dim4 not fallback99; batch/thermal hooks; empty output explicitly unbound.

- **Реальная граница и oracle:** Academic title/abstract1200, catalog description500/keywords20/variables20; float32 normalized cosine, labels arange, M16/efconstruction200. Actual DuckDB→HNSW0.8 writer→native query; >=3 non-tied vectors, k<N, declared ef and independent cosine ranking; wrong label/vector controls.

- **Отказы/история:** Canonical selected IDs collision 1/"1" reject; legacy ordering preserved; fake encoder not model-quality proof. Common EMB02 publisher reused; actual build/OS/ABI pinned, no GPU prerequisite; thermal/batch behavior kept.

- **Предел доказательства/стоимость:** Finite non-tied topology profile, not universal ANN recall or real model semantic usefulness; independent native route required. Declared k/ef/dimension/batch/profile and bounded thermal handling, no unmeasured retrieval SLA.

- **Точная трасса:** `02_Пакеты/EMB-01.md` §4–§9; REQ-EMB-01-01; REQ-EMB-01-02; REQ-EMB-01-03; REQ-EMB-01-04; TEST-EMB-01-01; TEST-EMB-01-02; TEST-EMB-01-03; TEST-EMB-01-04; companion `04_Трассировка/EMB-01.json`. Полные70 отдельных обоснований/ссылок — `assessments.json`.

#### EMB-02

**Вердикт:** новых обоснованных пробелов не выявлено в заявленном scope; это не implementation PASS.

- **Способность/условия:** Coherent semantic snapshot is staged/validated before selector, with distinct compatibility projections and actual reader admission. Native float32 matrix/index label+vector correspondence before selector; selector corruption never falls back to flat old files.

- **Реальная граница и oracle:** Selector→member/text/currentness guard→HNSW query; cold/warm fresh readers bind current encoder/DFI03 receipt and selected content. Coherent hashes with wrong vector fail native semantic validation; old selector precommit; empty typed output and postcommit copy error separately tested.

- **Отказы/история:** Preselection failure keeps old generation; postcommit compatibility-copy failure reported distinctly without rollback; changed membership/current inputs reject. Legacy flat projection remains derivative; canonical selector no silent old fallback; empty selection does not retain old HNSW.

- **Предел доказательства/стоимость:** Logical publication and profile-specific qualification, not power-loss durable multi-file transaction; raw hashes alone not semantics. Cold/warm full-projection hashing cost measured; no mandatory cache lease framework or new SLA.

- **Точная трасса:** `02_Пакеты/EMB-02.md` §4–§9; REQ-EMB-02-01; REQ-EMB-02-02; REQ-EMB-02-03; REQ-EMB-02-04; TEST-EMB-02-01; TEST-EMB-02-02; TEST-EMB-02-03; TEST-EMB-02-04; companion `04_Трассировка/EMB-02.json`. Полные70 отдельных обоснований/ссылок — `assessments.json`.

#### EMB-03

**Вердикт:** новых обоснованных пробелов не выявлено в заявленном scope; это не implementation PASS.

- **Способность/условия:** Legal runtime owns actual local model assets/query material, with fresh membership and optional separately qualified retrieval utility. LegalRuntimeMaterialOwner CPU1024, ST2.7.0 local asset profile; unsupported nonNone backend trap is not called; default multilingual-e5-large/mps remains.

- **Реальная граница и oracle:** Per-record legal text/assets/tokenizer/projection versions, incremental native DB/HNSW labels; current query intent/lease and withdrawal guard. Native positive fresh served query plus drift/withdrawal; optional preadjudicated >=3 corpus/distractors, frozen mechanism/criteria/k/ef and heldout.

- **Отказы/история:** Wrong asset/dimension/current-member or revoked lease cannot remain served; publisher fix not blocked by absent empirical utility claim. Three projections/chunks/thermal typed empty retained; existing wrapper defaults preserved; no new compulsory legal ledger.

- **Предел доказательства/стоимость:** Candidate retrieval does not imply source_relation verified or model/legal adequacy; optional utility claim explicitly separate. CPU local finite profile, retrieval utility/cost settings declared; no new dependency install or production SLA assumed.

- **Точная трасса:** `02_Пакеты/EMB-03.md` §4–§9; REQ-EMB-03-01; REQ-EMB-03-02; REQ-EMB-03-03; REQ-EMB-03-04; TEST-EMB-03-01; TEST-EMB-03-02; TEST-EMB-03-03; TEST-EMB-03-04; companion `04_Трассировка/EMB-03.json`. Полные70 отдельных обоснований/ссылок — `assessments.json`.

#### DFI-03

**Вердикт:** новых обоснованных пробелов не выявлено в заявленном scope; это не implementation PASS.

- **Способность/условия:** Strict content-stage receipt currentness distinguishes actual async harvest from synchronous stage wrapper. Strict nonnegative integers not bool/coercion; invalid receipt is scoped cache miss; [] vs None preserved; core QC live/noncacheable.

- **Реальная граница и oracle:** Actual async harvest pipeline stages={harvest} calls current _should_skip basis; sync run_content_stage_with_receipt covers benchmark/qcPublish, NOT harvest. Smart hit current input/output basis gives network0; off/miss inner resumeFalse but HTTP cache allowed; endpoint/config/registry mutations invalidate.

- **Отказы/история:** Same-name coherent stale payload and malformed count rejected; no broad except hiding owner failure; legacy diagnostics not strict admission. Existing async owner and sync supported surface maintained; no invented sync harvest; actual DB/NPZ/HNSW selected-stage chain.

- **Предел доказательства/стоимость:** Receipt/legacy output existence not current capability; cache-only physical-call guarantee scoped separately from retained HTTP caches. network0 exact chosen hit behavior, not universal throughput claim; cost qualification from common resource rules.

- **Точная трасса:** `02_Пакеты/DFI-03.md` §4–§9; REQ-DFI-03-01; REQ-DFI-03-02; REQ-DFI-03-03; REQ-DFI-03-04; TEST-DFI-03-01; TEST-DFI-03-02; TEST-DFI-03-03; TEST-DFI-03-04; companion `04_Трассировка/DFI-03.json`. Полные70 отдельных обоснований/ссылок — `assessments.json`.

#### ING-01

**Вердикт:** новых обоснованных пробелов не выявлено в заявленном scope; это не implementation PASS.

- **Способность/условия:** Selected preadmitted request namespace and incremental frontier move only after actual source→CAS/evidence consumer. Exact requesthash→unique connector/dataset namespace before admission; ambiguous hash across namespaces refuses before partial work/no heuristic fetch.

- **Реальная граница и oracle:** Version/source/schema/partition/time proof, raw/transformed PII and graph evidence; CAS before conditional predecessor/index advance. Actual approved cursor A8→A9 with B failure leaves B unchanged; empty delta keeps whole-source scope; fresh consumer resolves refs.

- **Отказы/история:** Stale predecessor rejects; observed now not source time; missing namespace/proof no live fallback or invented rights. Single namespace compatible; selected raw/derived versions immutable; useful successful A remains despite independent B failure.

- **Предел доказательства/стоимость:** Actual source owner/production rights finite qualification; conditional increment not global transaction/exactly-once claim. No implicit extra provider lookup; authorized source budgets only; full production capacity not inferred from fixtures.

- **Точная трасса:** `02_Пакеты/ING-01.md` §4–§9; REQ-ING-01-01; REQ-ING-01-02; REQ-ING-01-03; REQ-ING-01-04; TEST-ING-01-01; TEST-ING-01-02; TEST-ING-01-03; TEST-ING-01-04; companion `04_Трассировка/ING-01.json`. Полные70 отдельных обоснований/ссылок — `assessments.json`.

#### ING-02

**Вердикт:** новых обоснованных пробелов не выявлено в заявленном scope; это не implementation PASS.

- **Способность/условия:** Replayable stream windows recover exact rows/frontier and preserve contributor-specific evidence through faults. Initial empty frontier error; checkpoint admitted clock/source witness stable; each of four window types and 41 rows interrupt19.

- **Реальная граница и oracle:** Chunk0 first-poll/dedupe/raw/window fault; pending version/state policy/ordinal; conditional compensation after readback commit failures. Native stream/CAS/fresh consumer restart exact rows/windows/refs, not BaseException-only OS-crash proof.

- **Отказы/история:** A+B contributors with C triggering close exclude C as input; withdrawal A invalidates affected windows, independent D remains; restart does not lose/duplicate. Existing versioned window profile and source refs retained; compensation conditioned on actual current state, not blind rewind.

- **Предел доказательства/стоимость:** Recovery limited declared process/native failure profile; no global exactly-once or universal power-loss guarantee. Bounded window/pending state and selected replay workload; no invented RTO/RPO or unbounded storage claim.

- **Точная трасса:** `02_Пакеты/ING-02.md` §4–§9; REQ-ING-02-01; REQ-ING-02-02; REQ-ING-02-03; REQ-ING-02-04; TEST-ING-02-01; TEST-ING-02-02; TEST-ING-02-03; TEST-ING-02-04; companion `04_Трассировка/ING-02.json`. Полные70 отдельных обоснований/ссылок — `assessments.json`.

#### ING-03

**Вердикт:** новых обоснованных пробелов не выявлено в заявленном scope; это не implementation PASS.

- **Способность/условия:** Streaming memory/time/idempotency boundaries are exact semantic admission rules, not approximate object counts. CATEGORY None vs empty set, caller-owned presence/quarantine; dedup first accepted UTC horizon 86399 suppressed/86400 admitted; cap refuses, never evicts live keys.

- **Реальная граница и oracle:** Exact serialized-byte incremental accounting vs full-scan every transition; immutable/bounded copied rows count occurrences, not object id; four window/backpressure caps. Independent reference counters and preview/restore/expiry/flush histories; actual CAS fresh consumer; cap2 a/b/c refusal→cap3 retry preserves state.

- **Отказы/история:** Disabled dedup explicitly at-least-once; source/event/version exact key; forced closing and unsupported spill not silently accepted; no fallback time. Legacy semantic behaviors preserved where permitted; valid window closing stays positive; original source/quarantine ownership retained.

- **Предел доказательства/стоимость:** Clock/horizon/profile finite, not eternal global dedup/exactly-once; byte charge not RSS claim. Exact serialized budget with bounded accounting work, workload-aware transition tests; real RSS/wall only separate qualification.

- **Точная трасса:** `02_Пакеты/ING-03.md` §4–§9; REQ-ING-03-01; REQ-ING-03-02; REQ-ING-03-03; REQ-ING-03-04; TEST-ING-03-01; TEST-ING-03-02; TEST-ING-03-03; TEST-ING-03-04; companion `04_Трассировка/ING-03.json`. Полные70 отдельных обоснований/ссылок — `assessments.json`.

#### NET-01

**Вердикт:** новых обоснованных пробелов не выявлено в заявленном scope; это не implementation PASS.

- **Способность/условия:** Connection lifecycle assigns permit, handle and generation to real physical ownership across cancellation and deadlines. Terminal cancellation cleanup settles cleaned=False/pending owner; permit retained until physical close; caller cancellation shields active cleanup.

- **Реальная граница и oracle:** Actual FD fstat/EBADF, same-key blocking vs independent partition progress, clone/foreign owner/gen fence; one absolute deadline across permit/lock/connect/health. Real handle close and late-handle generation rejection; provider timeout identity and network outside lock; stale-finalizer profiles not weakened.

- **Отказы/история:** Shield spin, phantom release, cancelled/late provider, wrong owner clone, old generation publication fail targeted controls. Current lifecycle fixtures fixed instead of weakening gate; shared NET owner reused; no server-wide pool rewrite.

- **Предел доказательства/стоимость:** Physical-close qualification on declared native profile, not arbitrary platform guarantee or remote-operation rollback. Absolute remaining deadline + independent partition progress, not fabricated global fairness/SLO across arbitrary workloads.

- **Точная трасса:** `02_Пакеты/NET-01.md` §4–§9; REQ-NET-01-01; REQ-NET-01-02; REQ-NET-01-03; REQ-NET-01-04; TEST-NET-01-01; TEST-NET-01-02; TEST-NET-01-03; TEST-NET-01-04; companion `04_Трассировка/NET-01.json`. Полные70 отдельных обоснований/ссылок — `assessments.json`.

#### NET-02

**Вердикт:** новых обоснованных пробелов не выявлено в заявленном scope; это не implementation PASS.

- **Способность/условия:** Rate/circuit feedback observes actual provider completion exactly once without double votes from stale owners. Both adaptive wrappers record success once before lease release; plain limiter need not callback; failure/cancel no recovery vote.

- **Реальная граница и oracle:** Fractional rates .1/.2 capacity1, weighted request validity, pagination key 1/1.0 same vs domain different; circuit generation+TTL/balance invariants. 429 1→.5 then100success .55 then800→1; exact fake-clock pace plus actual wrapper/provider path; stale/double/foreign completion controls.

- **Отказы/история:** Old generation returns original outcome but no circuit vote; local overload not provider failure; expired entries not reclaimed while referenced. Existing callback surface and wrappers preserved; optional telemetry failures limited; no distributed global quota promise.

- **Предел доказательства/стоимость:** Local adaptive limiter/circuit profile, not multi-host fairness or provider guarantee; timeout not fabricated upstream failure. RPS capacity semantics explicit incl fractional/weights; no claim equal RPS equals equal resource cost for heterogeneous tenants.

- **Точная трасса:** `02_Пакеты/NET-02.md` §4–§9; REQ-NET-02-01; REQ-NET-02-02; REQ-NET-02-03; REQ-NET-02-04; TEST-NET-02-01; TEST-NET-02-02; TEST-NET-02-03; TEST-NET-02-04; companion `04_Трассировка/NET-02.json`. Полные70 отдельных обоснований/ссылок — `assessments.json`.

### LANE-09

#### SCL-01

**Вердикт:** новых обоснованных пробелов не выявлено в заявленном scope; это не implementation PASS.

- **Способность/условия:** Offline cache admission and live SSRF-protected acquisition use distinct current-policy paths and one deadline. Eligible cached facts pass current pure URL/literal/domain policy with network0/DNS0; only miss/authorized refresh performs live DNS/pin/peer/SNI checks.

- **Реальная граница и oracle:** Initial/final/all redirect URLs, MIME/raw byte_size and profile; deadline remaining across attempts/providers; []/error/unusable normalized fallback reasons. Native controlled HTTP/TLS profile and cache hit with unavailable DNS; last batch expiry partial result and zero new provider calls.

- **Отказы/история:** Legacy missing profile unknown not defaults; content text length not raw size; private opt-in not implicit authority; redirect/pin change controls. Shared raw transport/local bytes retained; candidate1.1 compatibility qualified finite profile; no forced online revalidation of eligible offline cache.

- **Предел доказательства/стоимость:** Read capability not source rights or institutional approval; offline currentness restricted to captured facts/current pure policy, not new DNS observation. Monotonic absolute deadline and max bytes compose across provider fallback; no invented latency target.

- **Точная трасса:** `02_Пакеты/SCL-01.md` §4–§9; REQ-SCL-01-01; REQ-SCL-01-02; REQ-SCL-01-03; REQ-SCL-01-04; REQ-SCL-01-05; TEST-SCL-01-01; TEST-SCL-01-02; TEST-SCL-01-03; TEST-SCL-01-04; TEST-SCL-01-05; TEST-SCL-01-06; companion `04_Трассировка/SCL-01.json`. Полные70 отдельных обоснований/ссылок — `assessments.json`.

#### SCL-03

**Вердикт:** новых обоснованных пробелов не выявлено в заявленном scope; это не implementation PASS.

- **Способность/условия:** Manual/raw acquisition preserves exact selected bytes/profile through native evidence consumer, never reconstructs from snippet. Acquire rechecks selected manifest/digest/size after preflight; foreign/missing raw refuses before docs, no URL fallback.

- **Реальная граница и oracle:** Typed raw ref + license/properties; actual fetch_profile(normalized constraints,maxbytes,timeout,UA,transport version) before cache, even nocache. Native CAS docs/fragments/claims fresh consumer binds raw version+span; enrich v1 twice0fetch, explicit v2 new lineage old immutable.

- **Отказы/история:** Manifest/raw bytes mutation, oversized raw not text size, forged/foreign selected refs, snippet overflow and substitution reject. Manual normalization keeps canonical bytes hash and historical immutable refs; compatible raw/profile owner shared SCL01.

- **Предел доказательства/стоимость:** Public web reachability is not reuse rights; no arbitrary legal/institutional source authority from retrieval. Max bytes/timeout actual fetch-profile are real limits; no all-web search/recall or latency guarantee.

- **Точная трасса:** `02_Пакеты/SCL-03.md` §4–§9; REQ-SCL-03-01; REQ-SCL-03-02; REQ-SCL-03-03; REQ-SCL-03-04; TEST-SCL-03-01; TEST-SCL-03-02; TEST-SCL-03-03; TEST-SCL-03-04; TEST-SCL-03-05; companion `04_Трассировка/SCL-03.json`. Полные70 отдельных обоснований/ссылок — `assessments.json`.

#### LLM-01

**Вердикт:** новых обоснованных пробелов не выявлено в заявленном scope; это не implementation PASS.

- **Способность/условия:** Optional observability cannot erase provider outcome or mandatory accounting; unknown spend remains reserved until reconciliation. Histogram/span failures at enter/body/attrs/status/exit must not suppress response/provider/LLMAccountingError; mandatory ledger not optional.

- **Реальная граница и oracle:** Runtime reservation and durable charge exactly once; prompt ABI sanitizer; cached2hits produce3 unique events and cost .02/0/0, expiry .04. Actual owner provider result→local spent→durable ledger; forced ledger uncertainty holds admission then real reconcile releases once; fallback telemetry API equivalence.

- **Отказы/история:** Missing usage unknown, forged reuse proof no charge/reuse, duplicate record, optional telemetry throwing, prompt conflict0provider all discriminated. Existing factory/provider/wrapper behavior and positional/named ABI retained; one shared OTel fallback no per-packet shim.

- **Предел доказательства/стоимость:** Accounting correctness and synthetic provider wiring not actual model usefulness/price estimate; uncertain outcome is not success or zero spend. Exact provider/charge/event counts measure scoped costs; no universal financial or latency SLA.

- **Точная трасса:** `02_Пакеты/LLM-01.md` §4–§9; REQ-LLM-01-01; REQ-LLM-01-02; REQ-LLM-01-03; REQ-LLM-01-04; REQ-LLM-01-05; REQ-LLM-01-06; TEST-LLM-01-01; TEST-LLM-01-02; TEST-LLM-01-03; TEST-LLM-01-04; TEST-LLM-01-05; TEST-LLM-01-06; companion `04_Трассировка/LLM-01.json`. Полные70 отдельных обоснований/ссылок — `assessments.json`.

#### LLM-02

**Вердикт:** новых обоснованных пробелов не выявлено в заявленном scope; это не implementation PASS.

- **Способность/условия:** Singleflight reuse operates only over closed materialized intent and current principal authorization, preserving physical-only opaque calls. Revision between miss/flight claim triggers one fresh complete guard+auth lookup; current tenant/principal/epoch/purpose on every reuse and follower after wait.

- **Реальная граница и oracle:** Six finite PolicyTranslator material roles, exact serialized prompt/provider config/modelroute/CAS versions with explicit absence; unknown live remains physical-only. Two wrappers/two loops/four misses→one authorized producer; detached responses, separate consumer receipts; actual PolicyTranslatorWorker→PolicyBrief with no fallback.

- **Отказы/история:** Revoked follower denied, bounded revision race re-admission, follower cancellation isolated; opaque Python objects/NaN preserved physical-only vs JSON nonfinite0transport separate. Default T=.1 retained; deterministic explicit T=0 profile only for reuse; tools/stream/seed/independent repeats not conflated; original provider kwargs retained.

- **Предел доказательства/стоимость:** Synthetic provider proves route/coalescing not model quality; no caller cacheable flag/URL regex authority and no universal canonicalization. Finite bounded retry and actual physical-call count; lock/cleanup bounded within deadline, not guaranteed arbitrary tenant fairness.

- **Точная трасса:** `02_Пакеты/LLM-02.md` §4–§9; REQ-LLM-02-01; REQ-LLM-02-02; REQ-LLM-02-03; REQ-LLM-02-04; REQ-LLM-02-05; REQ-LLM-02-06; REQ-LLM-02-07; TEST-LLM-02-01; TEST-LLM-02-02; TEST-LLM-02-03; TEST-LLM-02-04; TEST-LLM-02-05; TEST-LLM-02-06; TEST-LLM-02-07; TEST-LLM-02-08; companion `04_Трассировка/LLM-02.json`. Полные70 отдельных обоснований/ссылок — `assessments.json`.

## Shared joins и отрицательные границы

I07-A/B/C, I08-A/B/C, I09-A/B прочитаны с конкретными bindings. Cross-story X02-B03 (ING contributors/withdrawal), X02-B04 (rawv1→docs), X03-B02 (catalog/current Fabric) и X03-B04 (frozen finite-corpus discovery) рассмотрены условно по activation. Их наличие закрывает общие discovery/consumer требования, но не расширяет локальную приемку до всех modes/profiles. Единственное найденное binding противоречие — FAC-02; lane reviewer ссылается на тот же ID, без дубликата.

Критерии broker ACK/replica quorum/jitter fleet/canary/backup не превращены в обязательные подсистемы там, где их owned trigger отсутствует. Для реальных retries/cancellation/currentness/conditional commits/tenant reuse/byte budgets даны отдельные предметные dispositions, а не blanket N/A. Declared synthetic/finite fixtures не объявлены доказательством качества модели, corpus полноты, source independence, source rights или scientific adequacy.

## Проверка и ограничения

- Выполнена read-only inspection actual atomic IO, selected embedding publisher и calibration interpolation/config owner для ограниченных counterexamples. Список точных ranges/SHA — `coverage.json`; прочий product source не сканировался без границы.

- Semantic compare REQ.text и TEST.setup/action/oracle/doubles с current MD (whitespace-normalized):25/25; unique JSON open_decisions/obligation_dispositions/preservation_bindings и UDF05 title прочитаны отдельно. Это supplementary consistency check, не замена чтению.

- JSON artifacts проверены readback:25 unique packets; каждый70 ID ровно один раз; finding IDs/references/statuses и target hashes согласованы. Native tests, dependencies/install/deployment, network writes и product/spec edits не выполнялись.

- Не требуется подтвердить работоспособность продукта в этом аудите спецификаций. Недоступная native/empirical qualification остается будущей NOT_RUN/ограничением evidence, а не автоматически новым defect или PASS. Denied/pending/uncertain tool action: нет.

## Файлы

`assessments.json` — полный criterion ledger; `findings.json` —2 точных finding/replacement; `coverage.json` — inputs/hashes/read ranges/source citations; `companion_consistency.json` —25 semantic comparisons; `validation.json` —readback checks; `progress.json` —terminal status. `build_audit.py`/`write_findings.py` только собирают audit artifacts, не импортируют/исполняют продукт.
