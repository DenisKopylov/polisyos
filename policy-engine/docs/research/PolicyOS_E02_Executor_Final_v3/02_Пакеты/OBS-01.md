# OBS-01 — Календарные периоды: native consumer и адресная переоценка

**LANE-07 · CP2 · B146, LA-031 · preserve + native/historical qualification.**

**Практическая цель:** Наблюдения сохраняют точное время/неопределённость до реального consumer, а старые ошибочные проекции не исправляются выдуманной историей.

Статус: исполнительское ТЗ; продукт не изменён. Все TEST — **NOT_RUN**.

## 1. Основание и пределы
[Аудит](../05_Основания/Аудит/02_Пакеты/OBS-01.md) · [остатки C84](../05_Основания/Аудит/01_Реестры/C84_остатки.json) · [полная исходная карточка](../05_Основания/Аудит/05_Источники/OBS-01_исходные_строки.txt). Commit `20d9009be21097bfbdc38a546a15cc60213b8ace`. Full probes находятся в отдельно доставленном phase1 ZIP. Новый product defect не установлен; native/historical work не заменить 720syntheticcalendarinputs.

## 2. Сохранить работающий смысл
- Inclusive calendar bounds
- Typed missing/invalid/limited
- Unique precompute и positional rows
- Versioned projection и actual consumer recomputation
- Read API purpose limits

Защищённые различения: LK12. Не считать qualification-only поручением искусственно переписать исправленный продукт. Изменение кода в такой части требуется только при воспроизведённом несоответствии.

## 3. Полная disposition

- **C84-G01: qualify** → REQ-OBS-01-01, REQ-OBS-01-02. Native period producer/read/reconcile evidence, current repair preserve.
- **C84-G02: lifecycle** → REQ-OBS-01-03. Actual bounded historical inventory и derived reevaluation без original rewrite.
- **C84-G03: shared** → REQ-OBS-01-04. Остальные LA031phases у UDF02; alias compatibility здесь. Shared owner: UDF-02.

Original remaining и preservation inventory IDs полностью сопоставлены в companion JSON. Shared/historical obligations не исчезают из-за отсутствия нового R.

## 4. Атомарные требования и различающие проверки

### REQ-OBS-01-01
Canonical period projection должна сохранять inclusive calendar bounds, missing/invalid/limited distinctions и unique-key precompute; duplicate/reordered row labels не меняют позиционную связь. Missing/invalid не становится 2025/now/clamped date.

**TEST-OBS-01-01 — native unit / integration; NOT_RUN.**
- Setup: Years1900/2000/2024/2100, supported formats M/Q/Y, badmonth, missing/coarse, duplicate labels.
- Действие: Actual observation.project_ukraine_observation_periods и actual source/household producers.
- Точный oracle: Leap end29 для 2024; end+1=next period start, invalid/missing/limited absent bounds с разными reason. DistinctnonmissingIDs определяют число parser calls; порядок/повторы сохранены.
- Doubles/границы: Независимый calendar oracle, не тот же monthrange; synthetic calendar не empirical data.

### REQ-OBS-01-02
Native source/household→Parquet→verified CAS→Scientist reconcile/gate должен повторно вычислять projection из period IDs, отвергать forged bounds/unknown version и сохранять original source version; unresolved families не exact signoff.

**TEST-OBS-01-02 — native unit / integration; NOT_RUN.**
- Setup: Tiny real Parquet с valid/unresolved rows, real read API/CAS; version tamper и reordered duplicates.
- Действие: Actual _reconcile_ukraine_period_projection и family gate после selected reader.
- Точный oracle: Consumer valid dates совпадают; forged projection refused; unresolved tier diagnostic/exact_signoff_eligible=False; исходный frame/bytes/source version неизменны.
- Doubles/границы: Нет JSON renamed Parquet/AST/fakeCAS; native3.14/PyArrow обязательны.

### REQ-OBS-01-03
Historical reevaluation должна опираться на конечный actual inventory доступных затронутых outputs/dependent evaluations. Новые derived artifacts строятся existing reconcile owner только при reconstructable period facts; без periodID сохраняется not_established, не догадка о дате.

**TEST-OBS-01-03 — native unit / integration; NOT_RUN.**
- Setup: Declared accessible artifact roots, old version/marker inventory; sample old artifact с ID и без ID.
- Действие: Зафиксировать hashes/consumers/affected reason, получить forward derived view и compare.
- Точный oracle: Original hashes unchanged; withID derived corrected view+provenance; noID legacy_unavailable. Пустой inventory имеет roots/query scope и не выдается доказательством отсутствия всего исторического corpus.
- Doubles/границы: Не invent historical dataset, не массово rewrite; внешние данные/мутации только с отдельным доступом.

### REQ-OBS-01-04
Calendar phase LA-031 сохраняет compatibility symbols и actual callers до квалификации; shared import fix C83-R01 выполняется UDF-01, remaining IO/bindings/facade closure UDF-02.

**TEST-OBS-01-04 — native unit / integration; NOT_RUN.**
- Setup: Existing common/facade aliases, canonical calendar callers и shared fresh import test.
- Действие: Проверить alias identity и source/household graph path; объединить phase evidence.
- Точный oracle: Новый calendar owner реально используется, graph unresolved period edges не получает default year; MONTHLY_END_MONTH оставлен compat constant безвлияния на parser.
- Doubles/границы: Не удалять constant/whole common толькоиз-за current parser.

## 5. Конкретное решение / producer→consumer
Все пути ниже от `policy-engine/`; не выполнять повторный move по историческому имени.

`src/polisyos/data_forge/domains/ukraine/builders/observation.py::_period_to_dates/project_ukraine_observation_periods` уже применяет calendar.monthrange, precision discrimination и positional reconstruction. Не переписывать исправленный алгоритм без failing native witness. `src/polisyos/data_forge/domains/ukraine/builders/sources.py` и `src/polisyos/data_forge/domains/ukraine/builders/demography.py` должны использовать этот owner, не собственную date fallback.

`src/polisyos/scientist/governance/blueprint_release.py::_reconcile_ukraine_period_projection` уже recomputes с original index restoration и проверяет declared fields/version. Historical qualification: существующие manifest/ref inventory → select affected projection version/period evidence → new derived view → зависимые consumer results. Сначала ограниченный actual inventory, затем адресная reevaluation; если corpus недоступен, сохранить precise coverage gap, не требовать фиктивного полного rerun мира. Original artifact content/source version не меняются. Shared E02-I07-A использует настоящий Parquet и selected CAS, OBS02 отдельно отвечает за resume.

## 6. Общая интеграция и порядок
**E02-I07-A**, [канонический LANE-07](../03_Интеграция/LANE-07.md). Один общий evidence set, не одинаковая тяжёлая suite на каждый пакет.

- UDF-01 predecessor/shared import owner; UDF-02 accountable LA-031
- OBS-02 reader qualification; один writer sources/common

Owners/callers: `src/polisyos/data_forge/domains/ukraine/builders/observation.py`; `src/polisyos/data_forge/domains/ukraine/builders/sources.py`; `src/polisyos/data_forge/domains/ukraine/builders/demography.py`; `src/polisyos/scientist/governance/blueprint_release.py::_reconcile_ukraine_period_projection`. Shared files — один writer с последовательными commits и review потребителей; CP не отдельный runtime registry.

## 7. Совместимость / история / rollback
Move и calendar behaviour fix различать. Alreadyfixedv1 не менять без причины. Новые derived artifacts получают actual input refs/version/provenance; old zero/2025 без ID не исправлять на guess. Rollback не возвращает clamp/invent date; affected claims остаются qualified.

## 8. Free-grow и разумные отступления
[Vision §3, §6–§7, §11](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md) — существующий owner, реально подключённый consumer, совместимые новые ресурсы через общий контракт; не бесконечный реестр вместо работы. [Target Architecture D2.5](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md) — candidate/conditional вычисление не равно эмпирической или институциональной authority.

Нужен небольшой calendar owner, не глобальная calendar platform и не deterministic model inventor. Unknown period ограничивает соответствующую научную опору, не уничтожает все остальные наблюдения.

## 9. Приёмка и запреты PASS
Показать base/patch/write map, requirements/test matrix, failing-before/fixed-after либо controlled-removal witness, actual commands/runtime/exit/logs, selected hashes/refs и declared doubles. Реальные test owners: `tests/unit/remediation/test_obs_01.py`, `tests/unit/data_forge/domains/ukraine/test_builders.py`, `tests/unit/scientist/governance/test_blueprint_release.py`. Адаптируемый шаблон `<supported-python> -m pytest <verified paths>` из `policy-engine/`; будущие TEST IDs не названы существующими pytest functions.

Нельзя выдавать source inspection/fixture/AST/import-only за native цепочку; marker/hash/exit0 — за current admission или scientific truth; отказ всех inputs — за положительную способность; написанное ТЗ — за выполненную реализацию. Сохранять полезные независимые результаты и явные ограничения неподтверждённых claims. Install/deployment/external mutation не разрешаются документом автоматически.
