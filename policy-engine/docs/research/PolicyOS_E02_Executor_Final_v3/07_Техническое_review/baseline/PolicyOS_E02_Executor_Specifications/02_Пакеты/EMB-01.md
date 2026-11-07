# EMB-01 — Native общий encode/index без потери subject profiles

**LANE-08 · CP2 · LA-039 · preserve + native qualification.**

**Практическая цель:** Academic и Catalog строят полезные совместимые индексы одной механикой, не теряя смысл собственных текстов и результатов.

Статус: исполнительское ТЗ; продукт не изменён. Все TEST — **NOT_RUN**.

## 1. Основание и пределы
[Аудит](../05_Основания/Аудит/02_Пакеты/EMB-01.md) · [остатки C95](../05_Основания/Аудит/01_Реестры/C95_остатки.json) · [полная исходная карточка](../05_Основания/Аудит/05_Источники/EMB-01_исходные_строки.txt). Commit `20d9009be21097bfbdc38a546a15cc60213b8ace`. Full probes находятся в отдельно доставленном phase1 ZIP. Новых R нет; extraction уже выполнен. Native dependencies должны быть заранее разрешены supported profile, не установлены произвольно исполнителем.

## 2. Сохранить работающий смысл
- Separate SQL/text projections
- Actual float32/normalization/labels/M/ef
- ID/vector correspondence
- Actual dimensions and domain results
- Thermal/device/batching
- Explicit unbound candidate status
- Versioned ordering distinct from legacy

Защищённые различения: LK20. Не считать qualification-only поручением искусственно переписать исправленный продукт. Изменение кода в такой части требуется только при воспроизведённом несоответствии.

## 3. Полная disposition

- **C95-G01: qualify** → REQ-EMB-01-01, REQ-EMB-01-02, REQ-EMB-01-03. Native compute profile corpus вместо JSON index fixture.
- **C95-G02: shared** → REQ-EMB-01-04. Accountable generation publication/reader closure. Shared owner: EMB-02.

Original remaining и preservation inventory IDs полностью сопоставлены в companion JSON. Shared/historical obligations не исчезают из-за отсутствия нового R.

## 4. Атомарные требования и различающие проверки

### REQ-EMB-01-01
Общий encode/index owner сохраняет разные SQL и effective text profiles Academic/Catalog, actual float32, normalize_embeddings=True, cosine labels arange(n), M=16 и ef_construction=200.

**TEST-EMB-01-01 — native unit / integration; NOT_RUN.**
- Setup: Real tiny DuckDB с Academic title/abstract1200 и Catalog description500/keywords20/variables20; лёгкий encoder; real NumPy/HNSW.
- Действие: Оба actual public build wrappers → binary index load/query; сопоставить prepared texts, matrix rows и labels.
- Точный oracle: Правильные разные truncations и равные vectors при равных prepared texts; actual dtype/settings/labels; native binary читается.
- Doubles/границы: Encoder fixture допустим для wiring, но SQL/HNSW не recorder; model quality/ANN recall не заявлять.

### REQ-EMB-01-02
Dimension/result/device/batching/thermal semantics остаются domain-owned; common kernel не импортирует domain SQL.

**TEST-EMB-01-02 — native unit / integration; NOT_RUN.**
- Setup: Encoder dimension4 при configured fallback99, batches2/1, thermal hook0.25, Academic supplied device и Catalog resolved device.
- Действие: Вызвать build и run wrappers, прочитать actual stage manifests.
- Точный oracle: Academic возвращает count/dimension4, Catalog count; hooks после каждого batch включая последний; model/device/thermal fields правильные.
- Doubles/границы: Не менять device defaults или принудительно pad vectors до configured dimension.

### REQ-EMB-01-03
Legacy input ordering/empty retention и versioned selected generation — разные контракты. Canonical membership отвергает empty/duplicate/string-collision IDs до selection; unknown encoder identity остаётся unbound.

**TEST-EMB-01-03 — native unit / integration; NOT_RUN.**
- Setup: z/a и a/z, IDs1/"1", пустой corpus, fake encoder без identity.
- Действие: Legacy primitive и current generation wrapper; затем actual encoder-match consumer.
- Точный oracle: Legacy order прежний; selected order a/z в обеих перестановках с ID/vector correspondence; invalid IDs не заменяют selector; unbound candidate не получает reuse authority.
- Doubles/границы: Flat empty bytes не доказывают selected admission; model label не identity.

### REQ-EMB-01-04
LA-039 closure передаёт общий native compute witness EMB-02, включая actual publication/selected reader, а не засчитывает encode success как завершённый search.

**TEST-EMB-01-04 — native unit / integration; NOT_RUN.**
- Setup: Общий E02-I08-B corpus с current generation и обеими domain reader surfaces.
- Действие: Связать TEST01–03 с EMB-02 preselection/fresh-reader evidence.
- Точный oracle: Одна LA-039 closure после обеих фаз; compute checks не заменяют required inventory/readiness/currentness.
- Doubles/границы: Не строить третий writer и не объединять Legal incremental с full rebuild.

## 5. Конкретное решение / producer→consumer
Все пути ниже от `policy-engine/`; не выполнять повторный move по историческому имени.

Existing `src/polisyos/data_forge/kernel/embeddings.py::_build_embedding_index_with_encoder` уже владеет encode loop и native index construction. Domain `src/polisyos/data_forge/domains/academic/batch/embedder.py::build_hnsw_index` и Catalog peer подают prepared rows через собственные `src/polisyos/data_forge/domains/academic/embedding_projection.py` и `src/polisyos/data_forge/domains/catalog/embedding_projection.py`. Не повторять исторический extraction.

Добавить native qualification в existing kernel test owner, использовать лёгкий deterministic encoder только как test double, настоящие DuckDB и HNSW. Выбранные model assets для admitted consumer проверяются отдельно; fixture identity не подменяет owner resolution. При обнаруженном mismatch менять binding/параметр у существующего owner, не копировать SQL в kernel.

Current wrappers используют build_embedding_generation. EMB-02 owns preselection validation; EMB-01 сохраняет compute primitive и field-level trace. Shared E02-I08-B связывает один корпус от SQL до fresh reader.

## 6. Общая интеграция и порядок
**E02-I08-B**, [канонический LANE-08](../03_Интеграция/LANE-08.md). Один общий evidence set, не одинаковая тяжёлая suite на каждый пакет.

- EMB-02 accountable LA-039; EMB-03 shared kernel mutex
- E02-I08-B uses one native binary corpus

Owners/callers: `src/polisyos/data_forge/kernel/embeddings.py`; `src/polisyos/data_forge/domains/academic/batch/embedder.py`; `src/polisyos/data_forge/domains/catalog/batch/embedder.py`. Shared files — один writer с последовательными commits и review потребителей; CP не отдельный runtime registry.

## 7. Совместимость / история / rollback
Намеренная canonical sorting/versioned publication не обещает historical byte order. Legacy flat readers остаются только в реально поддержанном scope. Historical bytes не становятся current vectors автоматически; rollback не смешивает generations.

## 8. Free-grow и разумные отступления
[Vision §3, §6–§7, §11](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md) — существующий owner, реально подключённый consumer, совместимые новые ресурсы через общий контракт; не бесконечный реестр вместо работы. [Target Architecture D2.5](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md) — candidate/conditional вычисление не равно эмпирической или институциональной authority.

Новые subject profiles расширяют prepared-row contract, не создают новый HNSW writer. Разные corpus semantics сохраняются; deterministic test vectors не доказательство научной валидности модели.

## 9. Приёмка и запреты PASS
Показать base/patch/write map, requirements/test matrix, failing-before/fixed-after либо controlled-removal witness, actual commands/runtime/exit/logs, selected hashes/refs и declared doubles. Реальные test owners: `tests/unit/data_forge/kernel/test_embeddings.py`, `tests/unit/remediation/test_emb_02.py`. Адаптируемый шаблон `<supported-python> -m pytest <verified paths>` из `policy-engine/`; будущие TEST IDs не названы существующими pytest functions.

Нельзя выдавать source inspection/fixture/AST/import-only за native цепочку; marker/hash/exit0 — за current admission или scientific truth; отказ всех inputs — за положительную способность; написанное ТЗ — за выполненную реализацию. Сохранять полезные независимые результаты и явные ограничения неподтверждённых claims. Install/deployment/external mutation не разрешаются документом автоматически.
