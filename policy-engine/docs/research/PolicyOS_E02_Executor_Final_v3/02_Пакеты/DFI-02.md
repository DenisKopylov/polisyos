# DFI-02 — Полные counters и безопасный facade save/restore

**LANE-08 · CP2 · LA-038 · fix + native migration closure.**

**Практическая цель:** Canonical ingest сохраняет точную empty/delivery диагностику, а finite compatibility surface остаётся пригодной для поддержанных test/caller substitutions.

Статус: исполнительское ТЗ; продукт не изменён. Все TEST — **NOT_RUN**.

## 1. Основание и пределы
[Аудит](../05_Основания/Аудит/02_Пакеты/DFI-02.md) · [остатки C94](../05_Основания/Аудит/01_Реестры/C94_остатки.json) · [полная исходная карточка](../05_Основания/Аудит/05_Источники/DFI-02_исходные_строки.txt). Commit `20d9009be21097bfbdc38a546a15cc60213b8ace`. Full probes находятся в отдельно доставленном phase1 ZIP. R02 узкий save/restore lifecycle, не любой monkeypatch и не canonical production failure.

## 2. Сохранить работающий смысл
- Canonical API pipeline caller
- Finite remaining-leaf owners
- Scoped concurrent overrides
- Actual sync context bridge
- Existing Fabric contracts
- Source filters
- Warning for missing output receipt

Защищённые различения: LK19. Не считать qualification-only поручением искусственно переписать исправленный продукт. Изменение кода в такой части требуется только при воспроизведённом несоответствии.

## 3. Полная disposition

- **C94-R01: fix** → REQ-DFI-02-01. Carry existing empty counter through aggregate/manifest.
- **C94-R02: fix** → REQ-DFI-02-02. Stable self-wrapper recognition and current owner dispatch.
- **C94-G01: qualify** → REQ-DFI-02-03, REQ-DFI-02-04. JointnativeLA038/DFK profile/DB/receipt qualification.

Original remaining и preservation inventory IDs полностью сопоставлены в companion JSON. Shared/historical obligations не исчезают из-за отсутствия нового R.

## 4. Атомарные требования и различающие проверки

### REQ-DFI-02-01
Outer core-source API должен переносить existing empty_shards вместе с completed/failed/deferred/observations counters в returned stats и persisted stage manifest. Complete_empty не даёт publication authority без current receipt.

**TEST-DFI-02-01 — native unit / integration; NOT_RUN.**
- Setup: Inner stats empty 4/completed 5/observations 6 и nonzero failed/deferred; actual outerAPI/stage writer; missing receipt control.
- Действие: Execute merge→return→manifest→fresh reader.
- Точный oracle: Все counters совпадают с inner defined aggregation, empty 4 не 0; missing receipt warning сохраняется. Old merge fail oracle exact.
- Doubles/границы: Inner controlled result allowed для unit; real inner producer+DB в shared native TEST03.

### REQ-DFI-02-02
Facade должен распознавать все собственные live generated delegates независимо от последнего lookup и не принять restored old wrapper за self-override. Current owner lookup и legitimate custom developer overrides сохраняются.

**TEST-DFI-02-02 — native unit / integration; NOT_RUN.**
- Setup: saved d1→lookup d2→restore attribute=d1; current restore, custom function, owner replacement, async wrapper.
- Действие: Call actual facade/scope; cleanup attribute и повтор canonical.
- Точный oracle: Нет recursion; restored own wrapper выбирает current owner, custom override действует только в scope; no global broadcast, cancellation cleanup.
- Doubles/границы: Не unconditional cache устаревшего owner; exact wrapper identity, не arbitrary name heuristic.

### REQ-DFI-02-03
Native canonical pipeline должен без legacy import пройти оба leaf groups, actual config/profile/DB/lease/budget и current output receipt до fresh consumer, сохраняя source filters и все 7 counter metrics.

**TEST-DFI-02-03 — native unit / integration; NOT_RUN.**
- Setup: DFK custom rich registry и actual DatasetBatchConfig; tiny DB; success/empty/error sources, resumed lease, missing receipt.
- Действие: Canonical pipeline→core_sources.api→real writes→receipt→fresh reader; scopes A/B и sync bridge.
- Точный oracle: Source/provenance/filters intact; no duplicate resumed lease submission; budgets учитывают failed attempt; counters/manifest согласованы; current valid receipt yields useful consumer, missing receipt warning.
- Doubles/границы: Controlled connector allowed; actual config/profile/DB/checkpoint receipts, не synthetic neighbors.

### REQ-DFI-02-04
Final LA-038 closure сохраняет finite remaining-leaf bindings, архитектурные/no-growth checks и DFI-01 qualified trace; facade aliases retires только по caller qualification.

**TEST-DFI-02-04 — native unit / integration; NOT_RUN.**
- Setup: Actual registry/transformers/api tables и architecture checks на new commit.
- Действие: Run existing checks и caller inventory; verify no wildcard/domain transport duplication.
- Точный oracle: Canonical caller remains canonical, no arbitrary globals; reported module budget по реальной семантике check, не literal physical-line count guess.
- Doubles/границы: Не требовать rewrite all source algorithms или delete tests ради small facade.

## 5. Конкретное решение / producer→consumer
Все пути ниже от `policy-engine/`; не выполнять повторный move по историческому имени.

`src/polisyos/data_forge/domains/catalog/batch/core_sources/api.py` outer `_run_core_sources_ingest_async` aggregate добавить stats.empty_shards += ingest_stats.empty_shards рядом с другими shard counters. Проверить все counter fields на этом boundary, не менять complete_empty meaning или receipt guard.

`src/polisyos/data_forge/domains/catalog/batch/core_sources_ingest.py::_temporary_compatibility_overrides/__getattr__/_compatibility_delegate`: текущая _COMPATIBILITY_DELEGATE_DEFAULTS помнит только latest wrapper. Вместо recency identity использовать bounded weak identity map generated wrapper→binding (или один stable delegate per binding, который динамически разрешает current owner без captured stale implementation). Предпочтение weak map, если сохраняется existing new-wrapper lookup ABI. Все собственные live wrappers excluded from developer overrides; явный чужой callable остаётся scoped override. Invocation fallback должен брать актуальный getattr(owner,name), не старый captured target; __wrapped__/coroutine/signature совместимость проверить. Не public flag/name-based trust и не strong set растущий навсегда.

`src/polisyos/data_forge/domains/catalog/batch/pipeline.py` уже импортирует canonical API: сохранить. DFI01+DFI02 native trace общий с real DB/current profile/receipt; отсутствие receipt warning не превращать в success ради tests. Existing architecture/module_size_budget.toml проверить actual runner, не обновлять лимит вслепую по 197 lines.

## 6. Общая интеграция и порядок
**E02-I08-A**, [канонический LANE-08](../03_Интеграция/LANE-08.md). Один общий evidence set, не одинаковая тяжёлая suite на каждый пакет.

- DFI-01 predecessor/accountable LA-038 includes phase1
- DFI-03/EMB-02 shared pipeline writer; E02-I08-A

Owners/callers: `src/polisyos/data_forge/domains/catalog/batch/core_sources/api.py`; `src/polisyos/data_forge/domains/catalog/batch/core_sources_ingest.py`; `src/polisyos/data_forge/domains/catalog/batch/pipeline.py`. Shared files — один writer с последовательными commits и review потребителей; CP не отдельный runtime registry.

## 7. Совместимость / история / rollback
Stats field уже существует — wire format не новый; теперь правильное value. Delegates developer compatibility, не security authority. Retained wrappers живут только пока есть caller refs. Historical manifests не пересчитываются под старыми hashes; rollback не broadcast.

## 8. Free-grow и разумные отступления
[Vision §3, §6–§7, §11](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md) — существующий owner, реально подключённый consumer, совместимые новые ресурсы через общий контракт; не бесконечный реестр вместо работы. [Target Architecture D2.5](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md) — candidate/conditional вычисление не равно эмпирической или институциональной authority.

Freegrow — конечные per-owner bindings, а не особый global patch каждому случаю. Lawful empty полезен; accurate counter не scientific absence claim.

## 9. Приёмка и запреты PASS
Показать base/patch/write map, requirements/test matrix, failing-before/fixed-after либо controlled-removal witness, actual commands/runtime/exit/logs, selected hashes/refs и declared doubles. Реальные test owners: `tests/unit/remediation/test_dfi_02.py`, `tests/unit/data_forge/domains/catalog/batch/core_sources/test_api.py`, `tests/unit/data_forge/domains/catalog/batch/core_sources/test_registry.py`, `tests/unit/data_forge/domains/catalog/batch/core_sources/test_transformers.py`. Адаптируемый шаблон `<supported-python> -m pytest <verified paths>` из `policy-engine/`; будущие TEST IDs не названы существующими pytest functions.

Нельзя выдавать source inspection/fixture/AST/import-only за native цепочку; marker/hash/exit0 — за current admission или scientific truth; отказ всех inputs — за положительную способность; написанное ТЗ — за выполненную реализацию. Сохранять полезные независимые результаты и явные ограничения неподтверждённых claims. Install/deployment/external mutation не разрешаются документом автоматически.
