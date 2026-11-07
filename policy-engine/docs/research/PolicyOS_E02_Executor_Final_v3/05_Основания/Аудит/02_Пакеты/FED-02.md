# FED-02 — bounded audit, typed-empty и подготовка OVERLAY

## 1. Решение

**Ограниченно оценён, не закрыт.** Heap больше не сравнивает payload при равном hash; hidden UNION merge_log удалён; OVERLAY кэширует secondary index в рамках одной composition и не создаёт disabled detail records. Single-schema typed-empty UNION работает, включая сохранение/повторное чтение. Найден **C90-R01, low:** несколько compatible empty inputs возвращают только колонки первого.

Свежий результат: **5 MATCH; 3 unchanged existing bodies/cases PASS**. Измерены реальные lifetimes подробных log objects и число actual set_index/constructor calls; общий peak memory или speedup не измерялись. Native Python3.14/pytest/SQL квалификация не подменена bounded run.

Срез `20d9009be21097bfbdc38a546a15cc60213b8ace`. [Карточка](../05_Источники/FED-02_исходные_строки.txt) · [Источники](../05_Источники/C90_источники.json).

## 2. Матрица исходных IDs

| ID | Подтверждённое поведение | Остаток |
|---|---|---|
| B139 | Heap(priority,sequence,payload); same object/repeated key не падают; fixed-stream sample воспроизводим | G01 native; permutation invariance не обещана |
| B142 | Один согласованный empty schema сохраняет columns/dtype и queryability; no sources отдельно refuses | R01 multiple-input empty columns; G01 SQL/explicit-schema/delivery |
| B143 | Collector — bounded owner; 80 conflicts дают1 retained detail и enabled total80, hidden list нет | G02 реальный peak memory/latency |
| B144 | Две подготовки index для primary+used secondary, не по числу колонок; NONE0entries | G02 performance, без global mutable cache |

C89 numeric findings не исправлены этим пакетом и не дублируются новыми R. Source code не менялся.

## 3. Реальная работа механизма

Collector добавляет monotonic sequence после priority, поэтому даже одинаковый event object не доходит до сравнения dataclass payload. FULL и SUMMARY имеют разные detail containers; полные counters обновляются до отбора. Счётчик appearance обеспечивает deterministic fixed input stream, а не invariance к произвольной перестановке (`S01:333–412`).

UNION передаёт записи collector без собственного дополнительного списка. Resolver internal storage выключен по умолчанию; если caller явно включает его, отдельный cap и dropped count ограничивают этот owner. Pandas rows, cell basis и выходной dataframe остаются материализованными: это не streaming/O(1) реализация (`S01`, `S02`).

OVERLAY создаёт primary index, а secondary index — лениво при первом реально нужном столбце и переиспользует в этой composition. Подробные MergeLogEntry создаются только при enabled audit. Existing selected artifact format сохраняет typed frame/request/basis и fresh reader повторяет тот же owner; поэтому успех replay подтверждает алгоритмическую воспроизводимость, но может повторить schema bug (`S01:1202–1364`, `S05`).

## 4. Свежие проверки

1. **P01:** existing resolver internal cap, FULL cap/truncation и durable typed-empty query —3 bodies PASS. No-source case отказывает; empty имеет int64/float64, реальные JSON files повторно прочитаны, pandas query остаётся пустым. Это не registered DuckDB execution.
2. **P02:** четыре events с одним conflict key, включая повтор того же самого объекта, при caps1/2/4 не падают; count4, sample bounded, два fixed-stream прогона совпадают. Actual JOIN с двумя left rows и одной right row даёт `[10,11]` одинаково при FULL/SUMMARY/NONE. Не требуется удалять реальные повторения.
3. **P03:** actual UNION80 conflicts, cap/sample1. FULL и SUMMARY создают80 transient records, но weakrefs показывают **2 живых на return _union и1 после compose/GC**. Возвращается1 detail, total80; FULL dropped79. Локального hidden merge_log нет. NONE создаёт0 records и не ведёт conflict count; disabled zero не объявлен полным audit counter. Payload не копировался observer и weakrefs не удерживали объекты.
4. **P04:** две строки, три value columns, пять заполнений и исходное primary999. Во всех режимах exact values совпали; **set_index2**, независимо от трёх колонок. FULL/SUMMARY создали5 detail objects, NONE —0. Кэш локален composition; фактическое ускорение из2calls не вычислялось.
5. **P05 / R01:** пустые frames `id:int64,x:float64` и `id:int64,y:float64` с одинаковым grain дают только `id,x`; обратный порядок — только `id,y`. Empty+nonempty control возвращает `id,x,y`. Actual JSON persist/readback/replay сохраняет урезанный empty schema. Это не потеря фактических наблюдений: обе таблицы пустые, но column contract зависит от порядка.

## 5. Сохранить и доработать

**Сохранить:** stable heap tie-breaker, полный enabled count, bounded samples/details, default disabled resolver log и explicit cap, lazy per-composition indexing, отсутствие NONE payload, legitimate typed emptiness и no-source refusal. Не добавлять фиктивные строки, не dedupe законные events и не обещать постоянную память для N-row result.

**C90-R01 — low/high confidence.** [Empty branch](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/fabric/connectors/federation/composer.py#L830-L833) берёт `sources[0]`, а output-profile restoration лишь приводит уже присутствующие columns. Нужно вернуть typed empty по согласованной схеме всех admitted inputs либо explicit request. Проверять compatible extra columns, обратный порядок, dtype resolution, empty+nonempty и persisted reread. Это small owner fix, не новая schema platform. Не смешивать failed delivery, отсутствие источников и успешно прочитанный нулевой результат.

**C90-G01 — native/caller scope.** Повторить existing corpus и cold selected-artifact/registered-SQL witness в supported среде без syntax/import seams. Полный DataSchema/SQL/service delivery corpus не исполнен. Native import сейчас BLOCKED на TypeVar(default) через connectors initializer при Python3.12; pytest/DuckDB/Parquet отсутствуют. Среда не превращена в product defect.

**C90-G02 — performance.** Retained log records и repeated indexing действительно ограничены на выбранном scenario; total RSS, latency и representative wide/large input ещё не измерены. FULL/SUMMARY всё ещё создают transient entries для каждого enabled event — это не скрытое неограниченное удержание. Дальнейшее векторное counting/sampling оценивать только по необходимости и с сохранением audit semantics. Нельзя выводить speedup из отношения старого и нового числа вызовов.

## 6. Воспроизводимость

[Commands/exit/logs](../04_Проверки/C90_FED02/commands.json) · [Diagnostics](../04_Проверки/C90_FED02/bounded_diagnostics.json) · [Native boundaries](../04_Проверки/C90_FED02/native_verification.json) · [Fixture/measurement limits](../04_Проверки/C90_FED02/fixture_authority_limits.json) · [Syntax-only adapter](../04_Проверки/C90_FED02/run01/syntax_adapter.json) · [Остатки](../01_Реестры/C90_остатки.json).

Run01 exit0:5 MATCH,3 existing bodies PASS. Composer copy имеет только три except-parentheses adaptations; original source untouched. Actual resolver/profile/artifact/IR DTOs и hashing, explicit parent shells/telemetry no-op/pytest helper. Real filesystem JSON, но не native installed process/SQL. C89 tests не добавлены к текущему счётчику как новые.

Scientific/institutional authority из empty результата, имени source или hash не следует. Репозиторий/зависимости не менялись; install/server/fetch не запускались. **90/127 рассмотрены ограниченно; следующий — CAL-01, последний по реестру в LANE-07. Фаза 2 не начата.**
