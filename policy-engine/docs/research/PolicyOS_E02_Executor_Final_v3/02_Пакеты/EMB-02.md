# EMB-02 — Semantic admission индексного поколения до selection

**LANE-08 · CP2 · LA-039 · fix + native publication qualification.**

**Практическая цель:** Новый complete индекс становится выбранным только когда тот же consumer действительно может прочитать согласованные IDs, matrix и binary index.

Статус: исполнительское ТЗ; продукт не изменён. Все TEST — **NOT_RUN**.

## 1. Основание и пределы
[Аудит](../05_Основания/Аудит/02_Пакеты/EMB-02.md) · [остатки C96](../05_Основания/Аудит/01_Реестры/C96_остатки.json) · [полная исходная карточка](../05_Основания/Аудит/05_Источники/EMB-02_исходные_строки.txt). Commit `20d9009be21097bfbdc38a546a15cc60213b8ace`. Full probes находятся в отдельно доставленном phase1 ZIP. Контролируемый output fault подтверждён; частота native corruption/production ущерб не установлены.

## 2. Сохранить работающий смысл
- Single selector/staging
- Mandatory inventory/typed empty
- Old generation preservation
- Separate postcommit copy failure
- Current source membership
- Semantic matrix/index reader admission
- Intentional legacy refusal/text fallback

Защищённые различения: LK20. Не считать qualification-only поручением искусственно переписать исправленный продукт. Изменение кода в такой части требуется только при воспроизведённом несоответствии.

## 3. Полная disposition

- **C96-R01: fix** → REQ-EMB-02-01, REQ-EMB-02-02. Existing semantic checker moved/shared at preselection boundary, reader recheck remains.
- **C96-G01: qualify** → REQ-EMB-02-02, REQ-EMB-02-03, REQ-EMB-02-04. Real HNSW/DuckDB full guarded reader chain.

Original remaining и preservation inventory IDs полностью сопоставлены в companion JSON. Shared/historical obligations не исчезают из-за отсутствия нового R.

## 4. Атомарные требования и различающие проверки

### REQ-EMB-02-01
До замены selector complete generation должна пройти existing semantic matrix/index admission, включая finite float32 matrix, полный label set и stored vector correspondence. Failed staged admission сохраняет прежний selector.

**TEST-EMB-02-01 — native unit / integration; NOT_RUN.**
- Setup: Old valid generation; controlled writer сохраняет index с одним altered vector без exception и coherent new hashes; native binary variant с mismatched index.
- Действие: Actual domain wrapper → staged validation → selector/readback.
- Точный oracle: Old implementation выбирает unusable complete; fixed path отказывает до selection и old reader остаётся полезным. Valid new complete выбирается и читается.
- Doubles/границы: Не только hash corruption; semantic fault должен пережить coherent inventory hashing.

### REQ-EMB-02-02
Single selector, mandatory inventory, typed empty и failure phases сохраняются. Postcommit compatibility copy failure не откатывает уже admitted selected generation.

**TEST-EMB-02-02 — native unit / integration; NOT_RUN.**
- Setup: Complete/empty, NPZ/index/selector write failures; copy failure каждого legacy file в обоих domains.
- Действие: Run actual publisher и fresh resolver после каждого fault.
- Точный oracle: До selection старый selector неизменён; empty не содержит index и не выбирает старый complete; после selection typed EmbeddingCompatibilityProjectionError с generation/target, current selected комплект пригоден.
- Doubles/границы: Не обещать power-loss durability без отдельного испытания; два atomic file writes не atomic pair.

### REQ-EMB-02-03
Оба actual readers повторяют current effective membership/text и semantic output check на warm/fresh read; malformed selector не fallback на flat pair.

**TEST-EMB-02-03 — native unit / integration; NOT_RUN.**
- Setup: Real DB/HNSW, same-ID effective text mutation и beyond-truncation control, missing member, coherent hash vector mismatch, legacy-only corpus.
- Действие: Public Academic/Catalog search/load, rebuild, fresh reader и current read-session guard.
- Точный oracle: Current valid vectors дают useful search; effective change отказ, beyond-truncation сохраняет admission; bad selector отказ; legacy unsupported vectors дают declared text fallback без скрытой query model load.
- Doubles/границы: Не удалять DB custody guard как в bounded audit fixture.

### REQ-EMB-02-04
Полная native публикация проходит existing readiness/publish и resume consumers с explicit encoder identity; encode/manifest success сам по себе не consumer readiness.

**TEST-EMB-02-04 — native unit / integration; NOT_RUN.**
- Setup: Tiny native common corpus, two revisions, row permutation, bound and unbound encoders, current catalog QC/benchmark basis.
- Действие: EMB-01 compute→generation→Academic publish/Catalog readiness→DFI-03 content receipt→fresh consumer.
- Точный oracle: Нужные selected paths и status согласованы; valid producer полезен; unbound/currentness/readiness mismatch типизированы.
- Doubles/границы: Не выдавать admission за causal/model authority; не запускать full corpus rebuild. Для stronger масштабного claim отдельно снять cold/warm bytes read, hash/SQL projection/NPZ/load/encode/knn cost и RSS на bounded N ladder. Это measurement-first, не требование внедрить новый lease/cache и не gate локального preselection repair.

## 5. Конкретное решение / producer→consumer
Все пути ниже от `policy-engine/`; не выполнять повторный move по историческому имени.

В existing `src/polisyos/data_forge/kernel/embeddings.py::_publish_embedding_generation` validation выполняется до atomic_commit_path/selector. Расширить `_validate_generation_directory`: reuse существующую matrix/index admission логику `_load_selected_embedding_index` / `hnsw_index_matches_vectors`, вынеся лишь небольшой общий validator над validated generation reference/paths, если selected-only precondition мешает staged вызову. Не утверждать selection ради обхода guard; staging reference остаётся staging.

Для complete загрузить настоящий staged cosine index, проверить finite float32 matrix/IDs/dimension и labels/stored vectors тем же tolerance contract, что reader. Empty проверяет свой inventory без загрузки несуществующего index. После проверки остаётся прежний atomic directory commit и один selector. Reader checks не удалять: они защищают от последующей порчи/currentness changes. Compatibility copy находится после selection и имеет собственную typed error, это не failed publication.

EMB-02 — единственный writer общего publisher. Legal precomputed vectors EMB-03 проходят ту же admission. Catalog `src/polisyos/data_forge/domains/catalog/batch/pipeline.py` потребляет selected inventory и current encoder identity; coordinated edits с DFI-02/03, без второго receipt owner.

Стоимость warm reader квалифицировать отдельно от correctness. Existing catalog currentness читает full effective text projection и selected generation content; cached HNSW object не доказывает sublinear end-to-end query. Сначала bounded cold/warm breakdown и явная workload цель. Никакого automatic rewrite/lease implementation mandate: content hashes нельзя заменить mtime/size-only trust. Возможная амортизация через уже доказанный immutable opened-generation/read-session lifetime — отдельное measured design decision с in-place/replace/withdrawal invalidation controls; без него сохранить полную проверку.

## 6. Общая интеграция и порядок
**E02-I08-B**, [канонический LANE-08](../03_Интеграция/LANE-08.md). Один общий evidence set, не одинаковая тяжёлая suite на каждый пакет.

- EMB-01 prerequisite and shared native witness; LA-039 accountable here
- EMB-03 consumes shared C96-R01; DFI-03 separate LA-041 resume
- E02-I08-B; pipeline writes serialized with DFI-02/03

Owners/callers: `src/polisyos/data_forge/kernel/embeddings.py`; `src/polisyos/data_forge/domains/catalog/batch/pipeline.py`; `src/polisyos/data_forge/domains/catalog/knowledge/store.py`; `src/polisyos/data_forge/domains/academic/knowledge/store.py`. Shared files — один writer с последовательными commits и review потребителей; CP не отдельный runtime registry.

## 7. Совместимость / история / rollback
Версия текущего format сохраняется, если wire shape не меняется; дополнительная admission не меняет meaning complete. Old generation directory не удалять при failed stage. Legacy flat compatibility не становится current authority; допускается useful text fallback. Исторические pair-mixing дефекты superseded текущим staged publisher; исправляется только preselection semantic gap.

## 8. Free-grow и разумные отступления
[Vision §3, §6–§7, §11](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md) — существующий owner, реально подключённый consumer, совместимые новые ресурсы через общий контракт; не бесконечный реестр вместо работы. [Target Architecture D2.5](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md) — candidate/conditional вычисление не равно эмпирической или институциональной authority.

Небольшой общий validator лучше нового publication framework. Новые profiles пользуются тем же producer/consumer contract; representation integrity не обещает scientific truth.

## 9. Приёмка и запреты PASS
Показать base/patch/write map, requirements/test matrix, failing-before/fixed-after либо controlled-removal witness, actual commands/runtime/exit/logs, selected hashes/refs и declared doubles. Реальные test owners: `tests/unit/remediation/test_emb_02.py`, `tests/unit/data_forge/kernel/test_embeddings.py`. Адаптируемый шаблон `<supported-python> -m pytest <verified paths>` из `policy-engine/`; будущие TEST IDs не названы существующими pytest functions.

Нельзя выдавать source inspection/fixture/AST/import-only за native цепочку; marker/hash/exit0 — за current admission или scientific truth; отказ всех inputs — за положительную способность; написанное ТЗ — за выполненную реализацию. Сохранять полезные независимые результаты и явные ограничения неподтверждённых claims. Install/deployment/external mutation не разрешаются документом автоматически.
