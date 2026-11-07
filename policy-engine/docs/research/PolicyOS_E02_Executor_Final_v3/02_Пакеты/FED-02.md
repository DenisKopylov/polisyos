# FED-02 — Полная typed-empty схема и ограниченная стоимость audit

**LANE-07 · CP2 · B139, B142, B143, B144 · fix + preserve + native/performance qualification.**

**Практическая цель:** Законный нулевой результат остаётся пригодным для downstream SQL, а bounded audit не удерживает скрытую полную историю и не меняет данные.

Статус: исполнительское ТЗ; продукт не изменён. Все TEST — **NOT_RUN**.

## 1. Основание и пределы
[Аудит](../05_Основания/Аудит/02_Пакеты/FED-02.md) · [остатки C90](../05_Основания/Аудит/01_Реестры/C90_остатки.json) · [полная исходная карточка](../05_Основания/Аудит/05_Источники/FED-02_исходные_строки.txt). Commit `20d9009be21097bfbdc38a546a15cc60213b8ace`. Full probes находятся в отдельно доставленном phase1 ZIP. R01 теряет columns пустыхтаблиц, не фактические observations; audit mode NONE не обещает enabled counts.

## 2. Сохранить работающий смысл
- Stable heap ordinal
- Bounded collector и enabled counters
- Lazy per-composition indexing
- NONE без detail payload
- Typed empty/no-source distinction

Защищённые различения: исходные positive/negative boundaries выше. Не считать qualification-only поручением искусственно переписать исправленный продукт. Изменение кода в такой части требуется только при воспроизведённом несоответствии.

## 3. Полная disposition

- **C90-R01: fix** → REQ-FED-02-01. Согласованный empty schema union до output restoration.
- **C90-G01: qualify** → REQ-FED-02-01, REQ-FED-02-04. Native typed schema/cold SQL и service delivery.
- **C90-G02: qualify** → REQ-FED-02-02, REQ-FED-02-03, REQ-FED-02-04. Измерить actual performance; existing bounded repairs preserve.

Original remaining и preservation inventory IDs полностью сопоставлены в companion JSON. Shared/historical obligations не исчезают из-за отсутствия нового R.

## 4. Атомарные требования и различающие проверки

### REQ-FED-02-01
Empty UNION должен иметь согласованную схему всех admitted inputs либо explicit request schema, а не только первого frame. Compatible additional columns/dtypes сохраняются независимо от source permutation; no sources/failed delivery не становятся successful empty. Schema-only nullable columns допускаются с declared dtype; explicit dtype разрешается до inference, поэтому отсутствие source templates не вызывает pd.concat([]). Unsupported dtype даёт typed schema refusal.

**TEST-FED-02-01 — native unit / integration; NOT_RUN.**
- Setup: Zero-row id:int64,x:float64 + id:int64,y:float64; reverse order, nullable/mixed compatible dtypes, explicit schema, empty+nonempty. Explicit schema добавляет nullable z:Int64, которого нет ни в одном source; отдельный unsupported dtype control.
- Действие: Actual compose→persist→fresh reader→registered SQL query.
- Точный oracle: Empty содержит id,x,y и declared compatible types в обоих порядках; explicit schema honored; query returns0rows без KeyError. No sources отказ, failed delivery отдельный status; no fake row. z сохраняет declared nullable dtype/order; никаких pd.concat([])/ValueError; unsupported dtype даёт typed refusal до publication, не object fallback.
- Doubles/границы: Настоящие DataSchema/profile/artifact/SQL owner; нельзя вручную сконструировать final empty.

### REQ-FED-02-02
Collector должен сохранять полный enabled count при bounded details и stable heap tie-breaker, включая повтор того же event object. FULL/SUMMARY/NONE не меняют численный результат; NONE не создаёт detail payload.

**TEST-FED-02-02 — native unit / integration; NOT_RUN.**
- Setup: 80 conflicts cap/sample1, repeated same-key values и same-object; три audit levels.
- Действие: Actual UNION/JOIN, weakref/GC retained-object witness и summary.
- Точный oracle: Enabledtotal80, retained<=declared cap плюс кратковременный call-local record; dropped79 при FULLcap1. No TypeError payload comparison; fixed stream sample stable. NONE0details, disabled count не объявлен полным.
- Doubles/границы: Observer не удерживает объекты; не ограничиться len(returned log) и не dedupe повторные события.

### REQ-FED-02-03
OVERLAY должен готовить index каждого реально используемого source один раз в composition и сохранять primary precedence, masks, keys и lineage. Global mutable-frame cache запрещён.

**TEST-FED-02-03 — native unit / integration; NOT_RUN.**
- Setup: Primary999 и вторичный источник для 3/8 value columns, неиспользуемый secondary, все audit modes.
- Действие: Count actual set_index/construction calls и сравнить values/masks/basis.
- Точный oracle: 1primary+1usedsecondary preparation, unusedsecondary0; primary999 retained; audit mode не меняет result; NONE0entries.
- Doubles/границы: Spy calls допустим, не mocked indexing; count ratio не speedup.

### REQ-FED-02-04
Native cold selected-artifact/SQL/service delivery и representative performance должны квалифицироваться при фиксированных inputs/backend и одинаковом numerical oracle. Total RSS/latency не выводятся из числа log/index calls.

**TEST-FED-02-04 — native unit / integration; NOT_RUN.**
- Setup: Supported Python3.14, actual native typed-frame artifacts, bounded declared wide/large controlled dataset.
- Действие: Fresh process reopen/registered SQL; measure wall/peak separately FULL/SUMMARY/NONE после warmup/profile фиксации.
- Точный oracle: Schema/data/lineage одинаковы; lifecycle и budget limits выдержаны. Report измеряет настоящее workload scope и не заявляет O(1) для N-row dataframe. Если transient SUMMARY allocations доминируют — отдельный optimization preserving count/sample.
- Doubles/границы: No syntax/import seams; не заменять Parquet/SQL pandas query. Performance changes только по измеренному need.

### REQ-FED-02-05
Shared FED-01 numeric finite/singleton fixes должны потребляться без дублированного алгоритма и без изменения audit/empty semantics.

**TEST-FED-02-05 — native unit / integration; NOT_RUN.**
- Setup: Combined E02-I07-B numeric cases после общей composer revision.
- Действие: Выполнить selected replay/audit mode matrix с finite extreme и ordinary12.
- Точный oracle: FED01 finite result/participant oracles действуют во всех modes; empty schema repair не обходит numeric admission.
- Doubles/границы: Один shared owner численного helper; no copied fix.

## 5. Конкретное решение / producer→consumer
Все пути ниже от `policy-engine/`; не выполнять повторный move по историческому имени.

`src/polisyos/fabric/connectors/federation/composer.py::_union` empty branch заменить sources[0].iloc[:0] на typed empty template полного admitted column union. Порядок: explicit request schema, если задана; иначе стабильный documented union всех разрешённых column names, dtype по существующему profile reconciliation (не случайный first-source dtype). Несовместимый dtype/семантический mapping даёт конкретный gap/refusal, не object-cast с потерей смысла. `_restore_output_profile` уже получает request.schema.to_pandas_dtypes, но сейчас сначала выводит dtype через pd.concat(templates), а declared override применяет позже. Добавить недостающие declared columns до restoration и **сначала** разрешать declared_empty_union_dtypes[column]; только при отсутствии explicit dtype выводить его из непустых source templates. Для schema-only nullable z использовать declared dtype напрямую, никогда pd.concat([]). Неизвестный/неподдержанный declared dtype или отсутствие обоих оснований даёт typed schema refusal до publication. Сохранить существующий порядок declared columns и lossless casts, не приводить всё к object. Attach empty owned lineage и все source declarations штатным owner; не подделывать row origin при нуле строк.

`MergeLogCollector` уже heap(priority,sequence,payload), `_union` без hidden merge_log, resolver log default disabled/capped. `DataComposer._overlay` уже local lazy index. Сохранять, не переписывать ради количества изменений. G02 — реальные measurement и при необходимости bounded SUMMARY allocation optimization; не обещать full streaming/O(1). Existing artifact persist/replay и cold SQL tests должны увидеть полный schema contract, иначе replay честно воспроизводит ошибку.

## 6. Общая интеграция и порядок
**E02-I07-B**, [канонический LANE-07](../03_Интеграция/LANE-07.md). Один общий evidence set, не одинаковая тяжёлая suite на каждый пакет.

- FED-01 predecessor/shared composer writer
- Общий E02-I07-B; performance job scoped отдельно

Owners/callers: `src/polisyos/fabric/connectors/federation/composer.py::_union`; `src/polisyos/fabric/connectors/federation/composer.py::_restore_output_profile`; `src/polisyos/fabric/connectors/federation/composer.py::MergeLogCollector`; `src/polisyos/fabric/connectors/federation/artifact.py`. Shared files — один writer с последовательными commits и review потребителей; CP не отдельный runtime registry.

## 7. Совместимость / история / rollback
Old truncated-schema artifacts не «дополняются» несуществующими original columns. Forward new derivation schema/version фиксируется, historical outputs сохраняют qualification. Не удалять cache/source history ради benchmarks. Rollback affected empty output может быть withheld вместо silent schema loss, но valid empty/full inputs не запрещаются целиком.

## 8. Free-grow и разумные отступления
[Vision §3, §6–§7, §11](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md) — существующий owner, реально подключённый consumer, совместимые новые ресурсы через общий контракт; не бесконечный реестр вместо работы. [Target Architecture D2.5](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md) — candidate/conditional вычисление не равно эмпирической или институциональной authority.

Ноль строк — полезное успешное состояние данных, не отсутствие causal effect. Небольшой schema repair использует current DataSchema, не новую schema platform; разные sources тойже схемы не требуют bespoke branches.

## 9. Приёмка и запреты PASS
Показать base/patch/write map, requirements/test matrix, failing-before/fixed-after либо controlled-removal witness, actual commands/runtime/exit/logs, selected hashes/refs и declared doubles. Реальные test owners: `tests/unit/fabric/connectors/test_federation.py`, `tests/unit/fabric/connectors/test_federation_artifact.py`, `tests/unit/fabric/connectors/test_federation_cold_c93.py`. Адаптируемый шаблон `<supported-python> -m pytest <verified paths>` из `policy-engine/`; будущие TEST IDs не названы существующими pytest functions.

Нельзя выдавать source inspection/fixture/AST/import-only за native цепочку; marker/hash/exit0 — за current admission или scientific truth; отказ всех inputs — за положительную способность; написанное ТЗ — за выполненную реализацию. Сохранять полезные независимые результаты и явные ограничения неподтверждённых claims. Install/deployment/external mutation не разрешаются документом автоматически.
