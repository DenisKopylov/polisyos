# DFK-02 — Canonical catalog predicate и завершение compatibility projection

**LANE-08 · CP2 · LA-028 · fix + migration cleanup + native qualification.**

**Практическая цель:** Полный source policy имеет один текущий owner, а metadata-only catalog вопрос не требует отсутствующего executable connector.

Статус: исполнительское ТЗ; продукт не изменён. Все TEST — **NOT_RUN**.

## 1. Основание и пределы
[Аудит](../05_Основания/Аудит/02_Пакеты/DFK-02.md) · [остатки C92](../05_Основания/Аудит/01_Реестры/C92_остатки.json) · [полная исходная карточка](../05_Основания/Аудит/05_Источники/DFK-02_исходные_строки.txt). Commit `20d9009be21097bfbdc38a546a15cc60213b8ace`. Full probes находятся в отдельно доставленном phase1 ZIP. R01 только catalog-only predicate;35 штатных values уже согласованы. Scaffolding cleanup — не доказательство второй действующей policy.

## 2. Сохранить работающий смысл
- 35-row ordered full-field projection
- Shared fail-closed seed selection
- Strict YAML/bool/identity admission
- Explicit empty/default
- Existing asset/stage IDs
- Fresh full-registry comparison/connector join
- LK19/LK20 boundaries

Защищённые различения: LK19, LK20. Не считать qualification-only поручением искусственно переписать исправленный продукт. Изменение кода в такой части требуется только при воспроизведённом несоответствии.

## 3. Полная disposition

- **C92-R01: fix** → REQ-DFK-02-01. Predicate отделён от executable projection, connector guard сохранён.
- **C92-G01: qualify** → REQ-DFK-02-03, REQ-DFK-02-04. Native current published producer/consumer, shared lane witness.
- **C92-G02: lifecycle** → REQ-DFK-02-02. Убрать redundant literals при сохранённой effective canonical policy, не объявлять второй active authority.

Original remaining и preservation inventory IDs полностью сопоставлены в companion JSON. Shared/historical obligations не исчезают из-за отсутствия нового R.

## 4. Атомарные требования и различающие проверки

### REQ-DFK-02-01
Catalog entry profile predicate должен непосредственно использовать shared source_included_in_run_profile, не executable projection. Catalog-only запись без connector допускается там, где общая policy её выбирает; to_module_spec и actual execution по-прежнему требуют connector.

**TEST-DFK-02-01 — native unit / integration; NOT_RUN.**
- Setup: Custom YAML catalog-only omitted connector, disabled entry, unknown profile; штатный full catalog.
- Действие: Сравнить entry/batch/shared selector; отдельно execution projection.
- Точный oracle: prod_full/catalog_refresh parity=True для enabled catalog entry; unknown profile typed refusal; disabled=False; to_module_spec без connector продолжает connector_identity_missing.
- Doubles/границы: Не fake projection или изменение field defaults ради parity.

### REQ-DFK-02-02
Named compatibility catalog exports должны вычисляться из canonical source-ID views без создания ручных duplicate literals, сохраняя ordered full fields, asset/stage IDs, default/empty distinction и strict YAML admission.

**TEST-DFK-02-02 — native unit / integration; NOT_RUN.**
- Setup: Штатные 35 records и custom rich filters; duplicate keys/IDs, string bool, alias conflicts; None/().
- Действие: Reload family modules, compare all model_dump fields и assets; contract-only import в fresh process.
- Точный oracle: Все поля/порядок/IDs прежние; нет 35 redundant constructors; strict invalid отказ; explicit empty не default; contract-only import нечитает YAML до explicit view access.
- Doubles/границы: Настоящий YAML/Pydantic/loader; не golden только lossy ModuleSpec.

### REQ-DFK-02-03
Mandatory seed closure должно использовать registered rows и сохранять enabled/present/acyclic policy с cross-wave dependencies; disabled/missing/cyclic seed не включается молча и не оставляет исполняемый dependent без seed.

**TEST-DFK-02-03 — native unit / integration; NOT_RUN.**
- Setup: 6 profiles×waves, missing/disabled/cycle, selected counterfeit copy sameID; explicit empty и unknown profile.
- Действие: Actual registry/module/batch selection.
- Точный oracle: Одинаковый ordered resolved set, обязательный enabled seed может пересечь wave filter; typed reasons; подложенные selected fields не заменяют registered owner.
- Doubles/границы: Не удалять реальные Fabric connectors или переписывать source family transport.

### REQ-DFK-02-04
Native published catalog→warm/fresh Fabric consumer должен замечать same-ID policy byte change при неизменном stat, требовать current producer reissue и сохранять index при denied seed/connector.

**TEST-DFK-02-04 — native unit / integration; NOT_RUN.**
- Setup: Actual config/registry/source profile, tiny published catalog DB/receipt; same-size/mtime policy modification и valid reissue.
- Действие: Existing public/Fabric full-pipeline route; warm reader затем fresh reader.
- Точный oracle: Оба reader видят effective changed policy; old receipt не stale authoritative; после valid reissue useful resolve. Disabled seed/wrong connector отказ без index mutation.
- Doubles/границы: Controlled source endpoints; real DB/receipts/currentness, не selected-method state fixture.

## 5. Конкретное решение / producer→consumer
Все пути ниже от `policy-engine/`; не выполнять повторный move по историческому имени.

`src/polisyos/data_forge/domains/catalog/registry.py::CatalogSourceRegistryEntry.included_in_run_profile` заменить вызов self.to_module_spec() на `src/polisyos/data_forge/domains/catalog/selection.py::source_included_in_run_profile` (self, profile). Execution projection оставить строгой. Этот узкий fix не меняет defaults или enabled policy.

В `catalog/sources/` family surfaces заменить старые literal constructions+overwrite на конечные source-ID references к существующему canonical loader/view. Public names/order и lazy semantics сохраняются; YAML — полное исходное описание, а ModuleSpec не становится lossy execution policy. Existing `src/polisyos/data_forge/domains/catalog/selection.py::select_catalog_sources/resolve_catalog_source_dependencies` уже реализуют общий fail-closed closure: preserve.

`src/polisyos/fabric/retrieval/service.py` current registry comparison и connector join квалифицировать вместе с DFI-02/03 native pipeline. Нет необходимости нового catalog service или удаления Fabric acquisition.

## 6. Общая интеграция и порядок
**E02-I08-A**, [канонический LANE-08](../03_Интеграция/LANE-08.md). Один общий evidence set, не одинаковая тяжёлая suite на каждый пакет.

- DFI-01/02 actual ingest consumers; общий E02-I08-A
- LK19/LK20; source registry writer freeze before integration

Owners/callers: `src/polisyos/data_forge/domains/catalog/registry.py`; `src/polisyos/data_forge/domains/catalog/selection.py`; `src/polisyos/data_forge/domains/catalog/source_modules.py`; `src/polisyos/fabric/retrieval/service.py`. Shared files — один writer с последовательными commits и review потребителей; CP не отдельный runtime registry.

## 7. Совместимость / история / rollback
Historical defaults/schema читаются как прежде; future version не означает поддержку arbitrary новой semantics. Не мигрировать IDs/CASbytes ради cleanup. Rollback сохраняет canonical values и запрещает silent disabled seed; redundant literals могут временно остаться только явно scaffolding, не источник edit policy.

## 8. Free-grow и разумные отступления
[Vision §3, §6–§7, §11](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md) — существующий owner, реально подключённый consumer, совместимые новые ресурсы через общий контракт; не бесконечный реестр вместо работы. [Target Architecture D2.5](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md) — candidate/conditional вычисление не равно эмпирической или институциональной authority.

Новый совместимый source подключается полным registry record и existing connector contract, не orchestration branch. Unknown source authority не отменяет полезный catalog discovery; отдельный executable request требует своего connector/admission.

## 9. Приёмка и запреты PASS
Показать base/patch/write map, requirements/test matrix, failing-before/fixed-after либо controlled-removal witness, actual commands/runtime/exit/logs, selected hashes/refs и declared doubles. Реальные test owners: `tests/unit/remediation/test_dfk_02.py`, `tests/unit/data_forge/test_phase3_catalog_completion.py`. Адаптируемый шаблон `<supported-python> -m pytest <verified paths>` из `policy-engine/`; будущие TEST IDs не названы существующими pytest functions.

Нельзя выдавать source inspection/fixture/AST/import-only за native цепочку; marker/hash/exit0 — за current admission или scientific truth; отказ всех inputs — за положительную способность; написанное ТЗ — за выполненную реализацию. Сохранять полезные независимые результаты и явные ограничения неподтверждённых claims. Install/deployment/external mutation не разрешаются документом автоматически.
