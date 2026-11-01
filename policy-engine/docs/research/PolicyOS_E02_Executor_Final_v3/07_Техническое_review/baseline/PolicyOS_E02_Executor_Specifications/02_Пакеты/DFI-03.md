# DFI-03 — Content-bound resume без аварии на повреждённом receipt

**LANE-08 · CP2 · LA-041 · fix + native qualification.**

**Практическая цель:** Повторное выполнение реально переиспользует только текущий полный результат, а off гарантирует fresh stage work.

Статус: исполнительское ТЗ; продукт не изменён. Все TEST — **NOT_RUN**.

## 1. Основание и пределы
[Аудит](../05_Основания/Аудит/02_Пакеты/DFI-03.md) · [остатки C98](../05_Основания/Аудит/01_Реестры/C98_остатки.json) · [полная исходная карточка](../05_Основания/Аудит/05_Источники/DFI-03_исходные_строки.txt). Commit `20d9009be21097bfbdc38a546a15cc60213b8ace`. Full probes находятся в отдельно доставленном phase1 ZIP. Два residual локальны; existing strict checkpoint design уже присутствует, повторный wholesale rewrite не нужен.

## 2. Сохранить работающий смысл
- Separate input/output basis
- Required source/hash/count denominator
- Encoder asset identity
- Typed empty generation
- Historical formatter and atomic writer
- Legacy reader without strict admission
- Explicit [] vs None
- Current profile coverage refusal

Защищённые различения: LK20. Не считать qualification-only поручением искусственно переписать исправленный продукт. Изменение кода в такой части требуется только при воспроизведённом несоответствии.

## 3. Полная disposition

- **C98-R01: fix** → REQ-DFI-03-01. Typed local count admission before equality comparisons; malformed receipt becomes miss.
- **C98-R02: fix** → REQ-DFI-03-02. Direct CLI uses the same existing resume policy as pipeline.
- **C98-G01: qualify** → REQ-DFI-03-03, REQ-DFI-03-04. Native content-bound chain and selected hashing cost evidence.

Original remaining и preservation inventory IDs полностью сопоставлены в companion JSON. Shared/historical obligations не исчезают из-за отсутствия нового R.

## 4. Атомарные требования и различающие проверки

### REQ-DFI-03-01
Malformed receipt counts должны давать typed cache miss, а не необработанный ValueError; полная denominator/hash/currentness проверка сохраняется. Допускаются только объявленные неотрицательные целые counts, не bool или произвольная coercion.

**TEST-DFI-03-01 — native unit / integration; NOT_RUN.**
- Setup: Current receipt с valid payload и отдельными повреждениями трёх count fields: string garbage, negative, bool, fractional; valid zero и positive control.
- Действие: Вызвать actual _harvest_stage_receipt и public resume route.
- Точный oracle: Повреждённый receipt не используется и запускается fresh acquisition; valid complete receipt остаётся reusable; source/hash/path mismatch по-прежнему отказ.
- Doubles/границы: Не catch-all вокруг всего pipeline; неизвестная runtime ошибка не становится cache miss.

### REQ-DFI-03-02
Direct harvest CLI обязан соблюдать resume_mode=off независимо от resume=True. Smart resume должен сохранять content-bound reuse; off не запрещает отдельно разрешённый transport cache.

**TEST-DFI-03-02 — native unit / integration; NOT_RUN.**
- Setup: Один current completed harvest с payload; CLI --resume --resume-mode off и smart; actual selected source.
- Действие: Вызвать _run_single_stage через parser/config и actual harvest owner с counted connector.
- Точный oracle: off выполняет stage work, smart использует только current valid receipt; output/receipt после fresh work пригодны fresh reader.
- Doubles/границы: Controlled endpoint допустим; не сравнивать только config fields без invocation.

### REQ-DFI-03-03
Native selected stage chain должна связать actual config/profile, harvest payloads, normalize DB, embedding generation и fresh reader с отдельными input basis и output inventory.

**TEST-DFI-03-03 — native unit / integration; NOT_RUN.**
- Setup: Tiny actual DB/NPZ/HNSW corpus; two selected sources, one lawful complete_empty; same-stat byte mutation, absent output, partial source receipt, unbound encoder.
- Действие: Run→smart resume→mutation→rerun→fresh consumer, совместно с EMB-01/02/03.
- Точный oracle: Stable admitted input/output допускает reuse; каждый invalid case его снимает; rebuilt current generation снова полезна. Hash/model label не заменяют current encoder admission.
- Doubles/границы: Лёгкий encoder допустим для compute, но bound encoder identity/current assets нужны для vector admission.

### REQ-DFI-03-04
Legacy checkpoint read и formatter compatibility сохраняются без ослабления strict current admission; explicit required_outputs=[] отличается от None. Core/QC live stages остаются non-cacheable.

**TEST-DFI-03-04 — native unit / integration; NOT_RUN.**
- Setup: Historical state without content fields, explicit []/None, excluded private profile coverage, complete_empty и complete_nonempty.
- Действие: Actual stage_can_skip/current_content_stage_receipt и JSON write/read.
- Точный oracle: Legacy state читается для diagnostics, strict reuse отказ; [] отказ, None следует recorded paths; JSON indent2/sorted/atomic сохраняется. Private profile coverage mismatch отказ.
- Doubles/границы: Не признавать all([]) evidence полного inventory. Benchmark selected DB hash cost и bounded optimization только при доказанной immutable receipt guarantee.

## 5. Конкретное решение / producer→consumer
Все пути ниже от `policy-engine/`; не выполнять повторный move по историческому имени.

В `src/polisyos/data_forge/domains/catalog/batch/pipeline.py::_harvest_stage_receipt` заменить три незащищённых int(...) при сравнении raw manifest/entry/outcome counts на локальное строгое admission. Вернуть существующий miss result None с диагностируемой причиной; не перехватывать исключения внешних IO/producer как якобы корректный cache miss. Path confinement, selected source denominator, payload checksum и checkpoint binding оставить.

`src/polisyos/data_forge/domains/catalog/batch/cli.py::_run_single_stage` сейчас напрямую передаёт config в harvest_sources. Провести этот путь через existing `run_content_stage_with_receipt` и его policy либо передать `_uncached_content_stage_config` при off в единственной существующей dispatch точке. Выбор должен сохранить single-stage result/CLI semantics и не дублировать resume policy. Actual `src/polisyos/data_forge/domains/catalog/batch/harvester.py` checks config.resume; исправление только внешнего full-pipeline miss недостаточно.

`src/polisyos/data_forge/domains/catalog/batch/checkpoints.py::stage_can_skip` уже различает strict basis/inventory и []/None: preserve. В shared `src/polisyos/data_forge/domains/catalog/batch/pipeline.py` DFI-02 owns counters, EMB-02 owns embedding basis; DFI-03 owns harvest receipt/CLI resume. Изменения в одном файле применять последовательно с review соседних owners.

## 6. Общая интеграция и порядок
**E02-I08-A**, [канонический LANE-08](../03_Интеграция/LANE-08.md). Один общий evidence set, не одинаковая тяжёлая suite на каждый пакет.

- EMB-02 predecessor and shared C96-R01 owner
- DFI-02 shared pipeline writer; E02-I08-A plus native EMB consumer witness

Owners/callers: `src/polisyos/data_forge/domains/catalog/batch/pipeline.py`; `src/polisyos/data_forge/domains/catalog/batch/checkpoints.py`; `src/polisyos/data_forge/domains/catalog/batch/cli.py`; `src/polisyos/data_forge/domains/catalog/batch/harvester.py`. Shared files — один writer с последовательными commits и review потребителей; CP не отдельный runtime registry.

## 7. Совместимость / история / rollback
Старые JSON читаются для диагностики, но не получают current reuse authority задним числом. Не переписывать байты под прежним hash. Rollback не должен вновь разрешить stat-only resume; можно временно отключить affected stage reuse, сохраняя fresh execution. Trusted-input callback без найденного caller не объявлять active production bypass.

## 8. Free-grow и разумные отступления
[Vision §3, §6–§7, §11](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md) — существующий owner, реально подключённый consumer, совместимые новые ресурсы через общий контракт; не бесконечный реестр вместо работы. [Target Architecture D2.5](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md) — candidate/conditional вычисление не равно эмпирической или институциональной authority.

Новый stage интегрируется existing basis/inventory/receipt contract. Новый тип содержимого может потребовать adapter, но не отдельный cache протокол. Exact hashing cost измерить; оптимизация допустима только при доказанной immutable selected artifact identity.

## 9. Приёмка и запреты PASS
Показать base/patch/write map, requirements/test matrix, failing-before/fixed-after либо controlled-removal witness, actual commands/runtime/exit/logs, selected hashes/refs и declared doubles. Реальные test owners: `tests/unit/remediation/test_dfi_03.py`. Адаптируемый шаблон `<supported-python> -m pytest <verified paths>` из `policy-engine/`; будущие TEST IDs не названы существующими pytest functions.

Нельзя выдавать source inspection/fixture/AST/import-only за native цепочку; marker/hash/exit0 — за current admission или scientific truth; отказ всех inputs — за положительную способность; написанное ТЗ — за выполненную реализацию. Сохранять полезные независимые результаты и явные ограничения неподтверждённых claims. Install/deployment/external mutation не разрешаются документом автоматически.
