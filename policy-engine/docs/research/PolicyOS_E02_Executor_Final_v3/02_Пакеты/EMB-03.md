# EMB-03 — Полезный Legal incremental и поддержанный served query

**LANE-08 · CP2 · LA-040, LA-042 · native qualification + compatibility lifecycle.**

**Практическая цель:** Неизменённые legal records действительно переиспользуются; текущий supported owner даёт полезный поиск без ложной authority для нормативных выводов.

Статус: исполнительское ТЗ; продукт не изменён. Все TEST — **NOT_RUN**.

## 1. Основание и пределы
[Аудит](../05_Основания/Аудит/02_Пакеты/EMB-03.md) · [остатки C97](../05_Основания/Аудит/01_Реестры/C97_остатки.json) · [полная исходная карточка](../05_Основания/Аудит/05_Источники/EMB-03_исходные_строки.txt). Commit `20d9009be21097bfbdc38a546a15cc60213b8ace`. Full probes находятся в отдельно доставленном phase1 ZIP. Новых R нет. Positive owned serving qualification обязательна, но не новый универсальный backend и не legal authority proof.

## 2. Сохранить работающий смысл
- Per-record text/assets/tokenizer/rule identity
- Current membership/withdrawal
- Three projections/chunks/stats
- Historical bytes without cache authority
- Common publisher
- Explicit unsupported backend refusal
- Separate intent/runtime/source-relation gates

Защищённые различения: LK20. Не считать qualification-only поручением искусственно переписать исправленный продукт. Изменение кода в такой части требуется только при воспроизведённом несоответствии.

## 3. Полная disposition

- **C97-G01: qualify** → REQ-EMB-03-01, REQ-EMB-03-02, REQ-EMB-03-04. Native incremental plus actual owned positive served path; qualification must not stop at refusal.
- **C97-G02: lifecycle** → REQ-EMB-03-03. Retained honest wrapper is valid closure within declared scope, removal conditional on caller evidence.

Original remaining и preservation inventory IDs полностью сопоставлены в companion JSON. Shared/historical obligations не исчезают из-за отсутствия нового R.

## 4. Атомарные требования и различающие проверки

### REQ-EMB-03-01
Incremental reuse сохраняет per-record actual text/assets/tokenizer/projection identity и current membership; неизменённые записи не encode, withdrawal не попадает в current generation.

**TEST-EMB-03-01 — native unit / integration; NOT_RUN.**
- Setup: Real tiny DuckDB/HNSW для entities/facts/provisions; append, changed same-ID text, withdrawal, same-dimension assets/tokenizer/rule change, malformed basis, incremental=False.
- Действие: Actual build_local_embeddings_and_indexes→fresh selected reader; capture только encoder call counts.
- Точный oracle: Точные reused/recomputed IDs и embedded/skipped stats; current ID/vector membership; missing selector/history не cache; invalidator пересчитывает нужный совместимый комплект.
- Doubles/границы: Не подменять transaction SQL recorder; лёгкий encoder только compute witness.

### REQ-EMB-03-02
Supported owned runtime material должен дать положительный producer→fresh public served query path, сохраняя current intent/runtime checks и drift refusal.

**TEST-EMB-03-02 — native unit / integration; NOT_RUN.**
- Setup: Existing LegalRuntimeMaterialOwner declared pinned model/revision CPU1024/ST2.7.0 с заранее предоставленными local-only assets; current generation; altered asset/runtime/current text controls. Owned native профиль отдельно включает rag-local/ST2.7.0 и actual locked runtime; research/all extra не считается автоматическим наличием модели. Для stronger retrieval utility claim заранее зафиксировать finite relevance-labelled corpus≥3 с distractors, compatible new resource и held-out queries; k/ef/criterion выбрать до holdout.
- Действие: Resolve owner→build with runtime_material_owner→fresh Legal public search/HTTP; затем drift before/during lease. При отдельной utility qualification выполнить actual public queries до/после normal reissue с новым compatible resource без case-specific code; сравнить finite relevance labels, measured recall@k/false abstention и current generation refs.
- Точный oracle: Поддержанный material выполняет query encode и возвращает полезные search_candidate results; drift отказывает до недопустимого use, text fallback остаётся пригодным; generic candidate assets не обходят runtime gate. Owned serving correctness и semantic retrieval utility отчитать раздельно: одна self-query/непустой список не доказывают relevance. Для stronger utility claim finite predeclared criterion и holdout обязательны; без него utility NOT_QUALIFIED, а исправление publisher/механическая serving qualification не отменяются. Miss known-groundable seed — search ceiling, не legal/domain no-ground.
- Doubles/границы: Не mock admission/lease ради PASS; model download/deployment требуют отдельного разрешения. Fixture native compute не закрывает этот owner path. Не требовать universal exact ANN equality или all-domain legal understanding. Native owned serving не подменяется deterministic encoder; semantic labels и exact cosine topology — разные oracles.

### REQ-EMB-03-03
Retained compatibility wrapper сохраняет default canonical profile, chunk forwarding, exact result/exception identity и отказ любого non-None backend. Retirement заявляется только в конкретном caller/release scope.

**TEST-EMB-03-03 — native unit / integration; NOT_RUN.**
- Setup: Default calls, BackendTrap, canonical explicit model/device, saved caller inventory.
- Действие: Actual build_embeddings_and_index и canonical target; scoped external/generated API census если removal предлагается.
- Точный oracle: Default profile остаётся multilingual-e5-large/mps/chunk; BackendTrap не читается и target не вызывается; exceptions/results не оборачиваются. Без scope wrapper retained, не invented sunset.
- Doubles/границы: Historical ab441 wheel evidence не current native PASS.

### REQ-EMB-03-04
Legal producer использует единственный EMB-02 publisher и сохраняет три projections/chunking/thermal/empty semantics. Search candidate не становится verified legal claim только из-за semantic proximity.

**TEST-EMB-03-04 — native unit / integration; NOT_RUN.**
- Setup: Three populated tables и full withdrawal, quote400/text32000, chunks2; current generic/owned query outputs.
- Действие: Actual CLI embed stage manifest→common publisher→public candidate payload; authority request negative control.
- Точный oracle: Три generation metadata и counters корректны; empty typed; source_relation status verification_missing явно отделён от полезного candidate search. Authority projection не получает fabricated receipt.
- Doubles/границы: Отдельная verification capability не реализуется checksum или универсальным deterministic verifier; future support требует bounded claim class/evidence/validation contract.

## 5. Конкретное решение / producer→consumer
Все пути ниже от `policy-engine/`; не выполнять повторный move по историческому имени.

`src/polisyos/data_forge/domains/legal/batch/embedder.py::_load_reusable_vectors/_embed_table/build_local_embeddings_and_indexes` уже реализуют content-bound reuse и повторную encoder identity после encode. Не переписывать их в ID-only cache и не переносить Legal в full-rebuild Academic/Catalog semantics. Native tests соединяют actual transaction/chunk reads, real index и reader.

Положительный serving witness использует existing `src/polisyos/data_forge/domains/legal/runtime_material.py::LegalRuntimeMaterialOwner`, переданный в canonical builder. Затем fresh `src/polisyos/lex/knowledge/store.py` получает current query intent и owner-resolved handle. Если реальная текущая wiring не соединяет producer с public consumer, исправить этот ограниченный существующий путь и добавить regression; не объявить отсутствие результата допустимой финальной capability. Нет требования поддержать все модели/устройства: новый профиль добавляется только через bounded existing owner contract по реальной потребности.

`src/polisyos/data_forge/domains/legal/source_relation.py` сейчас честно candidate-only. Сохраняется полезный public hybrid/text/vector candidate поиск и отдельный отказ legal authority. Закрытие LA-040/042 не выдавать за завершение independent source-relation verification. Wrapper default сохраняется; unsupported backend уже исправлен. Shared publisher change принадлежит EMB-02.

Для native owned witness заранее объявить P-LEGAL-OWNED: Python3.14, actual HNSW0.8 build, rag-local/ST2.7.0, torch/transformers по lock и проверенные local CPU1024 model assets. Tiny corpus не делает модель маленькой; missing prerequisite → NOT_QUALIFIED без download/install или mocked lease. Более сильная retrieval utility проверяется конечным relevance/holdout планом TEST-02 отдельно от publisher repair. Existing GL/G5 known-seed/freshness pattern (`runtime/quality/proving_ground/legal_mandate_search.py::build_gl_search_recall_freshness`) можно переиспользовать как принцип evidence/currentness join с E02-X03/X04 там, где contract подходит; не подставлять embedding outputs в legal ledger schema и не создавать новый retrieval framework.

## 6. Общая интеграция и порядок
**E02-I08-B**, [канонический LANE-08](../03_Интеграция/LANE-08.md). Один общий evidence set, не одинаковая тяжёлая suite на каждый пакет.

- EMB-02 prerequisite and shared publisher owner
- E02-I08-B real producer→served query; no duplicate heavy model run

Owners/callers: `src/polisyos/data_forge/domains/legal/batch/embedder.py`; `src/polisyos/data_forge/domains/legal/batch/cli.py`; `src/polisyos/data_forge/domains/legal/runtime_material.py`; `src/polisyos/data_forge/domains/legal/source_relation.py`; `src/polisyos/lex/knowledge/store.py`; `src/polisyos/data_forge/kernel/embeddings.py`. Shared files — один writer с последовательными commits и review потребителей; CP не отдельный runtime registry.

## 7. Совместимость / история / rollback
Старые NPZ остаются историей, не backfilled authority. Legacy wrapper retained без arbitrary sunset; удаление лишь после scoped owner/caller approval. Historical native profile evidence хранится со своей версией и не переносится. Rollback не должен вернуть ID-only reuse или silent backend ignore.

## 8. Free-grow и разумные отступления
[Vision §3, §6–§7, §11](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md) — существующий owner, реально подключённый consumer, совместимые новые ресурсы через общий контракт; не бесконечный реестр вместо работы. [Target Architecture D2.5](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md) — candidate/conditional вычисление не равно эмпирической или институциональной authority.

Узкий admitted serving profile — начальная рабочая способность, не вечный hardcoded универсум. Generic producers сохраняют candidate output. Дальнейшие profiles и bounded source-relation verification расширяют existing contracts, но не требуют всеобщего детерминированного понимания нормативных текстов.

## 9. Приёмка и запреты PASS
Показать base/patch/write map, requirements/test matrix, failing-before/fixed-after либо controlled-removal witness, actual commands/runtime/exit/logs, selected hashes/refs и declared doubles. Реальные test owners: `tests/unit/remediation/test_emb_03.py`, `tests/unit/data_forge/legal_batch/test_embed_local.py`, `tests/unit/data_forge/legal_batch/test_embed_local_runtime_material.py`. Адаптируемый шаблон `<supported-python> -m pytest <verified paths>` из `policy-engine/`; будущие TEST IDs не названы существующими pytest functions.

Нельзя выдавать source inspection/fixture/AST/import-only за native цепочку; marker/hash/exit0 — за current admission или scientific truth; отказ всех inputs — за положительную способность; написанное ТЗ — за выполненную реализацию. Сохранять полезные независимые результаты и явные ограничения неподтверждённых claims. Install/deployment/external mutation не разрешаются документом автоматически.
