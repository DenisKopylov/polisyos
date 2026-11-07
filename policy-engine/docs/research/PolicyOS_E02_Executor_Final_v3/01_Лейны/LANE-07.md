# LANE-07 — Ukraine intake, composition и calibration observations

**Статус: исполнительское ТЗ, NOT_IMPLEMENTED; все будущие TEST — NOT_RUN.**

## Точный состав

- [UDF-01](../02_Пакеты/UDF-01.md) · [JSON](../04_Трассировка/UDF-01.json)
- [OBS-01](../02_Пакеты/OBS-01.md) · [JSON](../04_Трассировка/OBS-01.json)
- [UDF-02](../02_Пакеты/UDF-02.md) · [JSON](../04_Трассировка/UDF-02.json)
- [OBS-02](../02_Пакеты/OBS-02.md) · [JSON](../04_Трассировка/OBS-02.json)
- [UDF-04](../02_Пакеты/UDF-04.md) · [JSON](../04_Трассировка/UDF-04.json)
- [UDF-05](../02_Пакеты/UDF-05.md) · [JSON](../04_Трассировка/UDF-05.json)
- [FED-01](../02_Пакеты/FED-01.md) · [JSON](../04_Трассировка/FED-01.json)
- [FED-02](../02_Пакеты/FED-02.md) · [JSON](../04_Трассировка/FED-02.json)
- [CAL-01](../02_Пакеты/CAL-01.md) · [JSON](../04_Трассировка/CAL-01.json)

## Порядок и единые owners

1. UDF-01 contracts/import isolation → OBS-01 calendar interpretation → UDF-02 native formats/Foundry intake; OBS-02 snapshot/retry qualification и UDF-04 public operational gate сохраняют independent responsibilities. Общие Ukraine builders/contracts/sources files — последовательные commits, не повторный move.
2. UDF-05 допускает конечные demographic artifacts, затем FED-01 исправляет finite reductions/scalar MEDIAN, FED-02 — empty schema contract. Один writer federation composer: сначала FED-01, затем FED-02 с shared regressions.
3. CAL-01 исправляет measurement axis/paired sorting/units до CAL-02 и общей calibration приёмки LANE-10. CAL-01 — CP4; остальные восемь пакетов — CP2. LANE не меняет исходные CP.
4. Новый proposed `src/polisyos/common/numeric_reductions.py` — FED-01 implementation owner; UQS-01 потребитель. Это не existing helper и не arithmetic framework. Предпочтительный первый candidate — narrow finite-binary64 wrapper над CPython3.14 `statistics.mean` и mean двух central values для midpoint; independent rational oracle, subnormal/cancellation и measured group cost обязательны. Custom algorithm только по документированной correctness/performance причине. UDF-05 exact index validation выполняется до общего inferred float dtype, включая mixed big-int/integral-float controls.

## Связанная содержательная приёмка

- **E02-I07-A:** actual Ukraine source/stage → native selected formats/CAS → real Foundry binding/consumer; корректные period projections, failure/retry и gate provenance. Synthetic data честно synthetic, но реальный полезный conditional result обязателен.
- **E02-I07-B:** validated demographic input → composition with source-owned cell lineage → selected artifact/replay/consumer. Включает finite mean/midpoint, strict scalar MEDIAN и typed empty union, не только refusal.
- **E02-I07-C:** observation identity/units/calendar → paired aligned targets → LANE-10 calibration consumer. Missing/ambiguous observations не подменяются zero или автоматически усреднёнными дубликатами.

Канонический [integration contract LANE-07](../03_Интеграция/LANE-07.md) задаёт exact E02-I IDs и общий evidence set. Локальные regressions сохраняют свои exact oracles; shared success не заменяет failing-before/removal controls.

## Положительная способность и пределы

UDF-02 native positive intake и UDF-05 useful demographic route не закрываются одним schema guard. OBS-01 historical inventory ограничивается реально найденными artifacts без выдуманных дат; UDF-04 deployment не разрешён документом автоматически. Federation candidate data сохраняет полезность при неизвестной empirical/source independence, но stronger claim остаётся ограниченным.

## Qualification и передача

Supported Python >=3.14,<3.15 и фактически resolved dependencies/lock. Передать commit/write map, requirements→tests, actual commands/exits/logs, native/fixture distinction, selected input/output hashes и fresh-reader assertions. Изолированные inputs/provider doubles разрешены согласно пакетам; product CAS/DB/HNSW/ledger/consumer не подменять при native claim. Historical audit passes и independent arithmetic calculators не становятся current native suite PASS. Установки, deployment и внешние mutations требуют отдельного разрешения.

Design alignment: [Vision §3, §6–§7, §11](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md) и [Target Architecture D2.5](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md). Совместимые новые inputs идут через общий contract; новая семантика может требовать нового обоснованного кода. Guards и evidence не подменяют полезную работу, LLM semantic proposal не подменяет executable truth.
