# EMB-02 — согласованное индексное поколение

## 1. Решение

**Основной ремонт действительно присутствует:** оба domain builders используют общий staged publisher, обязательные NPZ/index/IDs/basis/inventory и один versioned selector. Empty corpus выбирает `empty_generation`; исключение до selection не заменяет прежний комплект. Actual readers повторно сверяют effective source text и index-to-matrix correspondence, а не только наличие файлов.

**5 MATCH, 9 unchanged existing test bodies / 14 cases PASS**, но это bounded исполнение с SQL/encoder/JSON-index fixtures. Полного закрытия LA-039 нет: **C96-R01** — semantic output admission выполняется после selection; **C96-G01** — native HNSW/DB и вся consumer цепочка не квалифицированы.

Срез `20d9009be21097bfbdc38a546a15cc60213b8ace`. [Карточка](../05_Источники/EMB-02_исходные_строки.txt) · [Pinned источники](../05_Источники/C96_источники.json).

## 2. Матрица исходных IDs

| ID | Подтверждено | Остаток |
|---|---|---|
| LA-039 / M, этап 2/2, accountable | Общий staged owner, complete/empty, selector, сохранение старого поколения при отказе, selected readers, mandatory inventory | R01 preselection semantic validation; G01 native joint corpus C95/C96 |
| LK20 | Hash/membership/currentness/native-index correspondence различаются; mismatches не принимаются reader | Не выдавать candidate artifact или manifest за эмпирическую состоятельность |
| A14 | Compute primitive отдельно от publication coordinator, domain projection отдельно от shared loop | Не объединять с иной legal incremental семантикой EMB-03 |

LA-039 учитывается **один раз**, а не повторно после C95. LA-041/content-bound resume — отдельная следующая карточка DFI-03, не автоматически закрытая этим пакетом.

## 3. Producer → consumer

Actual publisher создаёт staging directory, вызывает builder, сверяет matrix IDs/shape с canonical input, пишет IDs/basis и обязательный inventory. После validation он атомарно перемещает directory, затем заменяет единственный selector. Лишь **после** selection копируются legacy flat files. Отказ такой копии — отдельный `EmbeddingCompatibilityProjectionError` с generation ID/target: новый selected комплект остаётся полноценным, хотя compatibility pair может быть частично обновлена. Нельзя ошибочно требовать rollback уже выбранного корректного поколения (`S01:349–460`).

Resolver проверяет selector schema/hash, generation path, точный набор обязательных файлов, size/hash, matrix IDs/dimension, sidecars и basis digest. При имеющемся плохом selector нет fallback на прежнюю flat pair. Empty generation не содержит index и не считается старым complete. `embedding_generation_manifest` возвращает selector, inventory и все члены: шесть paths для complete, пять для empty (`S01:463–566,1239–1417`).

Academic и Catalog loaders перед использованием повторяют projection над текущими DB rows и сверяют полный ordered membership/effective text. Это происходит и при warm cache. Shared admission дополнительно требует float32 finite matrix нужной формы и совпадение всех labels/stored vectors индекса; в конце loaders повторно проверяют selected reference (`S06–S07`, `S01:1118–1180`). Catalog public read-session guard — ещё отдельный слой byte-identity custody, не заменённый этим алгоритмом.

Publish owners включают selected generation artifacts/metadata, а Catalog дополнительно требует current benchmark/QC basis и consumer readiness. Pipeline использует selected inventory и established encoder identity для resume. Эти пути прочитаны, но не объявлены выполненными. Полезная retrieval-механика не становится основанием причинного или policy-claim только из-за успешного index build (`S11–S13`).

## 4. Различающие исполнения

1. **P01 — 14 cases из 9 existing bodies.** Complete inventory; отказ index-save после NPZ с сохранением old selection; typed empty без старого index; новая model revision действительно пересчитывает fixture vectors; rows permutation сохраняет ID/vector correspondence; missing index и corrupt basis/IDs отказывают. Дополнительно четыре postpublication copy failure cases для двух domains/двух файлов и два selector failure cases. Все PASS с явно ограниченными dependencies, не native HNSW PASS.
2. **P02 — currentness и empty.** В обоих selected loader methods warm cache отвергается после изменения effective text. Изменение только за пределом truncation1200/500 не меняет actual projection и сохраняет admission. Empty rebuild меняет generation ID, reader отказывает `selected_generation_not_complete`, прежняя directory сохранена. Обязательные manifest paths проверены реально.
3. **P03 — hash не semantic integrity.** В JSON-index fixture изменён один stored vector и согласованно пересчитаны inventory/selector hashes. Resolver принимает coherent hashes, но actual index-to-matrix checker отказывает `selected_generation_index_mismatch` в обоих readers. Это не native corruption/security experiment.
4. **P04 — legacy boundary.** Kernel ещё умеет распознать старую flat pair без selector, но current domain readers явно требуют selected complete basis. Existing Catalog test отдельно ожидает text fallback без загрузки vector encoder (`S10`, прочитан, UNRUN). Поэтому отсутствие допуска unbound legacy vectors — намеренное ограничение, не повод восстановить небезусловный vector reuse. Плохой имеющийся selector не даёт fallback; восстановление корректного selector вновь допускает соответствующий комплект.
5. **P05 — preselection остаток.** Нормальный build/load положителен. Затем controlled index writer меняет один JSON fixture vector внутри `save_index`, но не бросает исключения. Actual wrapper возвращает успех, новый selector и manifest имеют `complete`; старое поколение существует, но уже не выбрано. Actual reader немедленно отказывает `selected_generation_index_mismatch`. Это воспроизводит более узкую границу, чем историческая смешанная NPZ/HNSW pair.

## 5. Сохранить и завершить

**Сохранить:** общий staged owner; разные domain texts/filenames; canonical ID/vector binding; typed empty; обязательный inventory; один selector; old directory до успешной selection; отказ при malformed selector; postcommit compatibility-copy distinction; source membership и semantic reader checks; явное unbound encoder ограничение. Никакого нового универсального framework для этого не требуется.

**C96-R01, низкая тяжесть — admission до selection неполон.** `_validate_generation_directory` вызывает `_build_selected_reference`, который проверяет file hashes/size, matrix IDs/shape и basis, но не загружает index для сравнения его vectors/labels. Такой checker уже существует, однако вызывается только consumer после выбора (`S01:1118–1180,1272–1380`). P05 показывает actual orchestration consequence при контролируемом output fault: `complete` становится выбранным до того, как выясняется его непригодность reader.

Остаток — использовать/расширить существующую staged admission до selection либо явно различать candidate и admitted status; сохранить повторный reader check против последующих изменений. При отказе staged semantic check прежний selector должен оставаться выбранным. Это **не** заявление, что реальный hnswlib нормально портит данные; частота/production occurrence не установлены. Не доказаны неверные поисковые результаты, обход custody или уничтожение прежнего поколения. Проверка соответствия output не делает embeddings научным источником сама по себе.

**C96-G01 — native и полная цепочка.** Нужен малый реальный HNSW/DuckDB corpus в supported Python environment: оба public readers, реальное index load/query, полная projection/currentness, empty/nonempty/model revision/permutation и failures. Encoder может оставаться малой fixture, без скачивания большой модели. Existing final search, Catalog readiness refusal и Academic publish tests должны быть исполнены в реальном graph окружении, а не заменены очередным synthetic success. Совместный lane witness должен связать C95 compute и C96 publication/consumer, сохранив отдельный LA-041 resume scope DFI-03.

## 6. Воспроизводимость и пределы

[Команды / exits / logs](../04_Проверки/C96_EMB02/commands.json) · [Диагностика](../04_Проверки/C96_EMB02/bounded_diagnostics.json) · [P05 trace](../04_Проверки/C96_EMB02/run03/preselection_output_admission.json) · [Currentness/empty](../04_Проверки/C96_EMB02/run03/currentness_empty_manifest.json) · [Semantic binding](../04_Проверки/C96_EMB02/run03/semantic_output_binding.json) · [Native status](../04_Проверки/C96_EMB02/native_verification.json) · [Fixture границы](../04_Проверки/C96_EMB02/fixture_authority_limits.json) · [Чтение](../04_Проверки/C96_EMB02/Чтение_и_границы.md) · [Остатки](../01_Реестры/C96_остатки.json).

Run03 exit0:5 MATCH/14 PASS. Run02 те же cases и4 MATCH, не удваиваются. Run01 — наша syntax typo до исполнения; exact failure сохранён. Whole kernel/build wrappers, NumPy/NPZ, files/hashes реальны. `.hnsw` — **JSON, не native binary**. Academic selected methods unchanged; Catalog два except parenthesized для Python3.12, guard удалён, constructor fixture. Original/adapted slices сохранены: это не полное native исполнение Catalog store.

Whole native reader imports BLOCKED на транзитивном Python3.14 syntax; native kernel import PASS только на уровне импорта. HNSW, DuckDB, pytest отсутствуют. Model quality, ANN recall, native binary compatibility, real guarded DB session, final readiness/publish и power-loss durability — UNRUN. Репозиторий, зависимости и внешние сервисы не менялись.

**96/127 рассмотрены ограниченно. Следующий — EMB-03. Фаза заданий исполнителю ещё не начата.**
