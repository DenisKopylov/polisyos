# DFI-01 — Самостоятельные core-sources leaves: native trace parity

**LANE-08 · CP2 · LA-038 · preserve + native qualification.**

**Практическая цель:** Writer/validator/loader используют явных владельцев и дают тот же полезный ingest результат без bootstrap старого фасада.

Статус: исполнительское ТЗ; продукт не изменён. Все TEST — **NOT_RUN**.

## 1. Основание и пределы
[Аудит](../05_Основания/Аудит/02_Пакеты/DFI-01.md) · [остатки C93](../05_Основания/Аудит/01_Реестры/C93_остатки.json) · [полная исходная карточка](../05_Основания/Аудит/05_Источники/DFI-01_исходные_строки.txt). Commit `20d9009be21097bfbdc38a546a15cc60213b8ace`. Full probes находятся в отдельно доставленном phase1 ZIP. Нового R нет: product change только при воспроизведённом несоответствии native qualification.

## 2. Сохранить работающий смысл
- Existing contracts/DTO
- Finite owner bindings
- Request-scoped immutable context
- No global broadcast
- Actual request/ID/provenance/chunk/count behavior
- Existing Fabric boundary

Защищённые различения: LK19. Не считать qualification-only поручением искусственно переписать исправленный продукт. Изменение кода в такой части требуется только при воспроизведённом несоответствии.

## 3. Полная disposition

- **C93-G01: qualify** → REQ-DFI-01-01, REQ-DFI-01-02, REQ-DFI-01-03. Native trace parity с actualDB, не AST/SQL capture alone.
- **C93-G02: shared** → REQ-DFI-01-04. Accountablephase2 owner; current canonical cutover preserve. Shared owner: DFI-02.

Original remaining и preservation inventory IDs полностью сопоставлены в companion JSON. Shared/historical obligations не исчезают из-за отсутствия нового R.

## 4. Атомарные требования и различающие проверки

### REQ-DFI-01-01
Canonical writers/validators/loaders должны работать до legacy facade import, разрешать dependencies через конечные owner bindings и не менять globals соседнего leaf. DTO owners и signature/substitution contracts сохраняются.

**TEST-DFI-01-01 — native unit / integration; NOT_RUN.**
- Setup: Fresh subprocess, canonical leaf tests; two actual owners с одноимённой dependency; unknown facade attribute.
- Действие: Вызвать writer/validator/loader напрямую, затем facade и повторить canonical call.
- Точный oracle: Actual owner используется; no arbitrary broadcast; unknown attribute не появился в leaves; current owner substitution не overwritten соседним вызовом.
- Doubles/границы: Не synthetic соседние modules для native independence claim; actual three leaves required.

### REQ-DFI-01-02
Request-scoped compatibility context должен copy/freeze mapping и гарантировать nested reset, async/thread isolation и cleanup cancellation без снятия bindings живого sibling.

**TEST-DFI-01-02 — native unit / integration; NOT_RUN.**
- Setup: Две concurrent invocations A/B с разными permitted overrides, nested scope, sync bridge worker thread и cancelA.
- Действие: Actual bind_core_sources_compatibility_context и facade/canonical consumers.
- Точный oracle: A/B получают собственные expected dependencies; outer restored после nested; B жив после cancelA; original mapping mutation не меняет scope.
- Doubles/границы: Developer override не authority predicate; не добавлять service container.

### REQ-DFI-01-03
Native writer/validator/loader trace parity должна сохранять source profiles, filters/dates, bytes/error/empty semantics, condition-aware IDs, provenance, SQL writes/chunks и attempted/inserted/replaced counts.

**TEST-DFI-01-03 — native unit / integration; NOT_RUN.**
- Setup: Tiny real DB, пять different condition rows, chunk2, known existing row; successful/empty/error controlled connector.
- Действие: Actual ObservationPlan→normalize→ID→lookup→writer transaction→fresh DB read, validator FetchRequest.
- Точный oracle: Distinct IDs/provenance retained, chunks2/2/1 где chosen config, exact 13-field payload; duplicate existing handling reflected counts; real commit/readback agrees. Filters/date window и budgets unchanged.
- Doubles/границы: Connector fake allowed; DB/actual writer/normalizer не capture-only для acceptance.

### REQ-DFI-01-04
LA-038 phase1 closure должна передать DFI-02 реальные bindings/caller contracts и shared evidence; не объявлять все 6leaves независимыми по первым 3.

**TEST-DFI-01-04 — native unit / integration; NOT_RUN.**
- Setup: Общий native E02-I08-A corpus и confirmed caller inventory.
- Действие: Сопоставить phase evidence с DFI-02 remaining group/pipeline.
- Точный oracle: Actual Fabric lease/profile boundaries preserved, no second HTTP; finalLA038status только после обеих групп и DFI02 residuals.
- Doubles/границы: Source-only callsite не native pipeline PASS.

## 5. Конкретное решение / producer→consumer
Все пути ниже от `policy-engine/`; не выполнять повторный move по историческому имени.

Current `src/polisyos/data_forge/domains/catalog/batch/core_sources/{writers,validators,loaders}.py` уже содержат finite dependency declarations и scoped resolver; не повторять move. Existing `src/polisyos/data_forge/domains/catalog/batch/_core_sources_ingest_contracts.py::CoreSourcesCompatibilityContext` копирует MappingProxyType и ContextVar token reset в finally. Test refs developer substitution — не новая runtime authority.

Qualification подключает настоящие leaves, `_insert_generic_observations`/current writer chain, actual DuckDB и existing observation index/schema owner. Сопоставить trace до и после migration по текущему accepted contract; не использовать historical lossy behavior как golden если оно исправлено отдельно. При mismatch исправить только owner binding/wiring, а не source-specific transformation под видом эквивалентности. Shared state mutation проверять no-broadcast negative. Full pipeline current caller у DFI02 уже canonical, не переключать его назад ради старой карточки.

## 6. Общая интеграция и порядок
**E02-I08-A**, [канонический LANE-08](../03_Интеграция/LANE-08.md). Один общий evidence set, не одинаковая тяжёлая suite на каждый пакет.

- DFI-02 accountable LA-038/shared facade mutex
- DFK-02 rich filters; E02-I08-A один actual ingest witness

Owners/callers: `src/polisyos/data_forge/domains/catalog/batch/core_sources/writers.py`; `src/polisyos/data_forge/domains/catalog/batch/core_sources/validators.py`; `src/polisyos/data_forge/domains/catalog/batch/core_sources/loaders.py`; `src/polisyos/data_forge/domains/catalog/batch/_core_sources_ingest_contracts.py`. Shared files — один writer с последовательными commits и review потребителей; CP не отдельный runtime registry.

## 7. Совместимость / история / rollback
Preserve supported aliases/signatures и scoped test seams; external callers census до retirement. Historical observation IDs/bytes не rewrite. Rollback не возвращает broadcast; affected dependency остаётся explicit error, остальные leaves работают.

## 8. Free-grow и разумные отступления
[Vision §3, §6–§7, §11](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md) — существующий owner, реально подключённый consumer, совместимые новые ресурсы через общий контракт; не бесконечный реестр вместо работы. [Target Architecture D2.5](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md) — candidate/conditional вычисление не равно эмпирической или институциональной authority.

Один contract owner с конечными bindings расширяем без глобального контейнера. Новая source semantics допускаетновый adapter, но reusable transport/profile boundary Fabric неподменяется.

## 9. Приёмка и запреты PASS
Показать base/patch/write map, requirements/test matrix, failing-before/fixed-after либо controlled-removal witness, actual commands/runtime/exit/logs, selected hashes/refs и declared doubles. Реальные test owners: `tests/unit/data_forge/domains/catalog/batch/core_sources/test_writers.py`, `tests/unit/data_forge/domains/catalog/batch/core_sources/test_validators.py`, `tests/unit/data_forge/domains/catalog/batch/core_sources/test_loaders.py`, `tests/unit/data_forge/domains/catalog/batch/test__core_sources_ingest_contracts.py`. Адаптируемый шаблон `<supported-python> -m pytest <verified paths>` из `policy-engine/`; будущие TEST IDs не названы существующими pytest functions.

Нельзя выдавать source inspection/fixture/AST/import-only за native цепочку; marker/hash/exit0 — за current admission или scientific truth; отказ всех inputs — за положительную способность; написанное ТЗ — за выполненную реализацию. Сохранять полезные независимые результаты и явные ограничения неподтверждённых claims. Install/deployment/external mutation не разрешаются документом автоматически.
