# Связанные очереди миграции — E02

Пакет остаётся единицей выдачи. Lane не становится гигантским заданием/lock и не создаёт новых hard dependencies.

## LANE-01 — Пользовательский цикл и явное N7 требование

B12 и уточнённая LA-046 делят реальный N7 handoff. Уже работающие typed gap/explicit specs не заменяются новым lexical planner.

**Последовательность:** REQ-01 → ACQ-01; CYC-03 → ACQ-01. Остальной цикл идёт по собственным prerequisites, не ждёт общего завершения legacy.

**Пакеты:** [CYC-01](bundles/CYC-01.md), [REQ-01](bundles/REQ-01.md), [CYC-03](bundles/CYC-03.md), [ACQ-01](bundles/ACQ-01.md), [CYC-04](bundles/CYC-04.md), [CYC-02](bundles/CYC-02.md), [CYC-05](bundles/CYC-05.md), [SIM-01](bundles/SIM-01.md), [SIM-02](bundles/SIM-02.md), [SIM-03](bundles/SIM-03.md), [SEL-01](bundles/SEL-01.md).

## LANE-02 — Search state → adapters → actual autotune consumer

LA-014/015 и B118–127 не создают две реализации исправленного loop. В том же цикле планируется native cutover, не cleanup после всех B.

**Последовательность:** CTL-01 → CTL-03 → SRV-01 → SRV-03. OPT/RNG/funnel пакеты поставляют исправленные contracts; совместная приёмка не требует одинакового старого ошибочного результата.

**Пакеты:** [CTL-01](bundles/CTL-01.md), [CTL-03](bundles/CTL-03.md), [SRV-01](bundles/SRV-01.md), [SRV-03](bundles/SRV-03.md), [CTL-02](bundles/CTL-02.md), [STP-01](bundles/STP-01.md), [OPT-01](bundles/OPT-01.md), [OPT-02](bundles/OPT-02.md), [OPT-03](bundles/OPT-03.md), [OPT-04](bundles/OPT-04.md), [FUN-01](bundles/FUN-01.md), [FUN-02](bundles/FUN-02.md), [FUN-03](bundles/FUN-03.md), [TRN-01](bundles/TRN-01.md), [TRN-02](bundles/TRN-02.md), [TRN-03](bundles/TRN-03.md).

## LANE-03 — Empirical scope, calibration и S10 — без смешения ролей

Одна временная правка не создаёт calibration evidence. Nominal CI, observed coverage, Foundry fit и DDM FP имеют разные предметы.

**Последовательность:** B32+LA-051 в FRC-01; затем FRC-02 после PCL-01/EMP-01. LA-052/053 в одном test/owner пакете; backtesting не переносится целиком.

**Пакеты:** [EMP-01](bundles/EMP-01.md), [FRC-01](bundles/FRC-01.md), [PCL-01](bundles/PCL-01.md), [FRC-02](bundles/FRC-02.md), [BKT-01](bundles/BKT-01.md), [BKT-02](bundles/BKT-02.md), [BKT-03](bundles/BKT-03.md), [BKT-04](bundles/BKT-04.md).

## LANE-04 — Compile/runtime владельцы, baseline-модели и executable plans

Randomization/catalog/layout переезжают с consumers. Baseline laws не меняются в relocation, а новые критерии и настоящий trainer не появляются из переименования.

**Последовательность:** FRY-01 → FRY-03 → ECO-01; PLG-02 → PLG-03. CMP/JIT правятся независимо, но после принятого move читают актуальный path map.

**Пакеты:** [FRY-01](bundles/FRY-01.md), [FRY-03](bundles/FRY-03.md), [ECO-01](bundles/ECO-01.md), [PLG-01](bundles/PLG-01.md), [PLG-02](bundles/PLG-02.md), [PLG-03](bundles/PLG-03.md), [CMP-01](bundles/CMP-01.md), [CMP-02](bundles/CMP-02.md), [CMP-03](bundles/CMP-03.md), [JIT-01](bundles/JIT-01.md), [RES-04](bundles/RES-04.md), [CAL-05](bundles/CAL-05.md).

## LANE-05 — Causal shared helpers, wrappers и model/query

Dedicated DiD ещё использует те же numerical helpers. Полезные одноимённые causal packages защищены; facade migration не свидетельствует математической корректности.

**Последовательность:** GRF-01 включает только три пустых sibling .py вместе с примитивами B216/217. CAU-01 metadata-detachment → общие estimator fixes → CAU-05 dedicated cutover.

**Пакеты:** [GRF-01](bundles/GRF-01.md), [GRF-02](bundles/GRF-02.md), [GRF-03](bundles/GRF-03.md), [API-01](bundles/API-01.md), [CAU-01](bundles/CAU-01.md), [CAU-02](bundles/CAU-02.md), [CAU-03](bundles/CAU-03.md), [CAU-04](bundles/CAU-04.md), [CAU-05](bundles/CAU-05.md), [SCM-01](bundles/SCM-01.md), [SCM-02](bundles/SCM-02.md), [SCM-03](bundles/SCM-03.md), [FIT-01](bundles/FIT-01.md).

## LANE-06 — Состояние, deadlines, replay, канон и persisted migrations

LA-057 затрагивает тот же async_tools, что B14/40/69/95. Replay alias не равно checkpoint format. Strict canon и runtime Decimal transport имеют разные обязательства.

**Последовательность:** RUN-01 сначала exact TypeVar cleanup, затем deadline/context fix отдельным commit. MIG-01 единый CLI/Trinity; MIG-02/MIG-04 исправляют его разные режимы. CAN/WIRE не сливаются.

**Пакеты:** [STA-01](bundles/STA-01.md), [STA-02](bundles/STA-02.md), [EXE-01](bundles/EXE-01.md), [EXE-02](bundles/EXE-02.md), [RES-01](bundles/RES-01.md), [RES-02](bundles/RES-02.md), [RES-03](bundles/RES-03.md), [RUN-01](bundles/RUN-01.md), [RUN-02](bundles/RUN-02.md), [RUN-03](bundles/RUN-03.md), [DUR-01](bundles/DUR-01.md), [DUR-02](bundles/DUR-02.md), [WIRE-01](bundles/WIRE-01.md), [CAS-01](bundles/CAS-01.md), [CAS-02](bundles/CAS-02.md), [CAS-03](bundles/CAS-03.md), [REP-01](bundles/REP-01.md), [CAN-01](bundles/CAN-01.md), [MIG-01](bundles/MIG-01.md), [MIG-02](bundles/MIG-02.md), [MIG-04](bundles/MIG-04.md), [MIG-05](bundles/MIG-05.md).

## LANE-07 — Ukraine builders: перенос helpers сразу с ремонтом наблюдений

LA-031 не отделяется от B146/147: period и iterator исправляются в согласованных новых владельцах. D4 остаётся producer handoff, не calibration admission.

**Последовательность:** UDF-01 contracts/D4 → OBS-01 observation-time+B146 → UDF-02 IO/bindings → OBS-02 B147. UDF-04/05 независимы при свободных write leases.

**Пакеты:** [UDF-01](bundles/UDF-01.md), [OBS-01](bundles/OBS-01.md), [UDF-02](bundles/UDF-02.md), [OBS-02](bundles/OBS-02.md), [UDF-04](bundles/UDF-04.md), [UDF-05](bundles/UDF-05.md), [FED-01](bundles/FED-01.md), [FED-02](bundles/FED-02.md), [CAL-01](bundles/CAL-01.md).

## LANE-08 — Catalog ingestion, generation-bound embeddings и resume

LA-038–042 соединяют existing Fabric acquisition, batch transformation, общий publisher и reader; их нельзя объединить в один новый transport или считать B134 той же индексной реализацией.

**Последовательность:** DFI-01 → DFI-02 для broadcast; EMB-01 → EMB-02 → EMB-03/DFI-03 для index generation/reuse. Соседние B ingestion/network сохраняют свои owners.

**Пакеты:** [DFK-02](bundles/DFK-02.md), [DFI-01](bundles/DFI-01.md), [DFI-02](bundles/DFI-02.md), [EMB-01](bundles/EMB-01.md), [EMB-02](bundles/EMB-02.md), [EMB-03](bundles/EMB-03.md), [DFI-03](bundles/DFI-03.md), [ING-01](bundles/ING-01.md), [ING-02](bundles/ING-02.md), [ING-03](bundles/ING-03.md), [NET-01](bundles/NET-01.md), [NET-02](bundles/NET-02.md).

## LANE-09 — Scholar raw acquisition и snapshot handoff

Один HTTP helper, вызванный дважды, не устраняет потерю версии. Поиск, acquisition и enrichment сохраняют самостоятельную полезную работу.

**Последовательность:** SCL-01 B17+LA-024 → SCL-03 LA-025. LLM cache/planning остаётся отдельным контрактом с общей snapshot приёмкой.

**Пакеты:** [SCL-01](bundles/SCL-01.md), [SCL-03](bundles/SCL-03.md), [LLM-01](bundles/LLM-01.md), [LLM-02](bundles/LLM-02.md).

## LANE-10 — Калибровка модели и закон неопределённости

Миграция baseline/inputs не должна вернуть потерянные fixed params, неправильно связанный covariance или фиктивные independent samples.

**Последовательность:** Существующие B цепочки; учесть upstream changes FRY/OBS и downstream PCL/FRC без объединения разных calibration APIs.

**Пакеты:** [CAL-02](bundles/CAL-02.md), [CAL-03](bundles/CAL-03.md), [CAL-04](bundles/CAL-04.md), [CAL-06](bundles/CAL-06.md), [UQS-01](bundles/UQS-01.md), [UQP-01](bundles/UQP-01.md), [UQP-02](bundles/UQP-02.md), [UQP-03](bundles/UQP-03.md), [DOE-01](bundles/DOE-01.md), [DOE-02](bundles/DOE-02.md), [DOE-03](bundles/DOE-03.md), [STR-01](bundles/STR-01.md).

## LANE-11 — Explainability и monitoring: явный profile и актуальный decision

LA-034/036 — structural/algorithm identity; LA-054/055 — report application/precedence. R2 override и handwritten schema channel guards защищены.

**Последовательность:** DDM-01 → DDM-02; BERL и Lex независимы. Общая проверка ограничений, но нет общего нового authority engine.

**Пакеты:** [BER-01](bundles/BER-01.md), [DDM-01](bundles/DDM-01.md), [DDM-02](bundles/DDM-02.md), [LEX-01](bundles/LEX-01.md).

## LANE-12 — Точные retirement и generated client поставка

D/C — конечная проверка конкретной функции/адреса, не разрешение удалять корни. Raw client удаляется лишь после scratch handoff и смены retaining tests/checker.

**Последовательность:** Готовые небольшие cleanup задачи выдаются между связанными fixes. Generated-family build и distribution объединяются в CP6; нет обязательной cleanup-фазы после B.

**Пакеты:** [DFK-01](bundles/DFK-01.md), [HYG-02](bundles/HYG-02.md), [HYG-04](bundles/HYG-04.md), [CLI-01](bundles/CLI-01.md).

