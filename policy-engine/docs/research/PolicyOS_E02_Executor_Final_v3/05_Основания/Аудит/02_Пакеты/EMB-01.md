# EMB-01 — общий encode/index primitive, разные subject profiles

## 1. Решение

**Ограниченно оценён, не закрыт.** Общая механика действительно находится у existing kernel owner; Academic и Catalog сохраняют собственные SQL-проекции, effective texts, default device и форму результата. Получены **5 MATCH; 4 unchanged existing bodies / 4 cases PASS** с настоящими NumPy/NPZ и файловой системой. **Новых подтверждённых локальных дефектов R в этой фазе не найдено.** Native HNSW/DB и полная publication/reader цепочка не подтверждены.

Срез `20d9009be21097bfbdc38a546a15cc60213b8ace`. [Полная карточка](../05_Источники/EMB-01_исходные_строки.txt) · [Pinned источники](../05_Источники/C95_источники.json).

## 2. Матрица исходных IDs

| ID | Подтверждено | Остаток |
|---|---|---|
| LA-039 / M, этап 1/2 | Общий actual encode/index owner; отдельные SQL/text/result profiles; effective text, IDs/vectors, batching, dtype, normalization и параметры индекса | C95-G01 native boundary; C95-G02 публикация/reader в EMB-02 |
| A14 | `build_embedding_index` сам не является generation publisher; versioned publication — отдельный existing coordinator | Compute success не закрывает selected-reader contract |
| LK20 | Corpus/hash/model metadata не выданы за admissible reuse; fake encoder остаётся unbound | Full currentness/output integrity/native index admission — отдельные свойства |

Accountable closure LA-039 — EMB-02. Legal chunking/incremental path этим пакетом не объединяется с full rebuild.

## 3. Actual producer → consumer

Academic читает `(id,title,abstract)` из ac_works и формирует `title + '. ' + abstract[:1200]`; Catalog читает `(id,title,description,keywords,variables)` и сохраняет description[:500], keywords[:20], variables[:20]. Проекции имеют собственные versioned rule/basis kind. Common kernel не импортирует domain SQL обратно (`S01–S05`).

Shared encode helper получает уже подготовленные пары, вызывает encoder по batch с `normalize_embeddings=True`, `show_progress_bar=False`, приводит векторы в **float32**, строит **cosine HNSW, M=16, ef_construction=200**, labels=`arange(n)` и пишет NPZ/index. Actual dimension берётся из результата encoder, а не принудительно из конфигурации. Thermal pause hook вызывается после каждого batch, включая последний (`S05:87–165`).

Нужно различать две поверхности: legacy primitive сохраняет порядок входа и при empty rows не трогает прежние flat bytes. Current wrappers уже используют `build_embedding_generation`: membership string-normalized, duplicate/empty IDs запрещены, rows сортируются по ID, staging/selector принадлежат отдельному publisher. Это **намеренная versioned ordering/publication delta**, не доказанная потеря ID correspondence и не обещание прежнего byte order (`S05:168–599`).

Academic build возвращает `(count, actual_dimension)`, Catalog — count; run wrappers пишут свои metrics и generation metadata. Catalog использует resolved device, Academic — supplied device. Missing real model identity даёт явное `encoder=unbound`; это candidate artifact, не автоматическое право на vector reuse. В опыте actual encoder-match отвергает такой объект (`S05:632–705`).

## 4. Свежие различающие проверки

1. **P01:** четыре unchanged existing тела: empty legacy pair retention, empty domain compatibility flat retention, оба text profiles и equal prepared texts/vectors. Все4 PASS, но fake SQL, encoder и JSON index обозначены явно. Имя existing test с `real_hnsw_path` **не** означает native HNSW в этом запуске.
2. **P02:** полный малый effective-text corpus: Academic1200, Catalog500/20/20; control одинакового текста `Title. A` через разные projections; None fields дают разные исторические строки (`.` и empty), wrong row shape отказывает. Проекции не слиты ради единой функции.
3. **P03:** input order z/a у legacy primitive сохраняется; selected generation даёт a/z при обеих перестановках. Matrices совпадают по соответствующим ID, dtype=float32. Encoder dimension4 сохраняется при configured fallback99. Шесть thermal-hook вызовов имеют значение0.25. Это equality fixture vectors, не ANN recall и не качество модели.
4. **P04:** оба настоящих run_embed сохраняют реальные JSON stage manifests: count2/thermal=True; Academic dimension4/device=mps, Catalog resolved device=cpu. Четыре pause hooks по0.5. Catalog model-loader — явная fixture seam; metadata содержит unbound и actual encoder-match=False, а не synthetic authority.
5. **P05:** empty ID, duplicate ID и collision `1`/`'1'` отвергаются до index construction; прежний selector не заменяется. Это полезный membership control, не полная fault-injection qualification публикации.

## 5. Сохранить и завершить

**Сохранить:** раздельные domain SQL/projections/filenames; truncation1200 и500/20/20; row-ID correspondence; real float32 conversion; normalization request; HNSW construction settings и labels; actual dimension/result fields; batching/device/thermal hooks; canonical membership refusal; explicit unbound limitation. Не переносить Academic в Catalog и не строить третий HNSW writer. Scientific/model quality не следует из deterministic fixture.

**C95-G01 — native compute boundary.** В supported environment исполнить existing малый NumPy/HNSW corpus с настоящими HNSW и DuckDB, но лёгким encoder fixture. Проверить бинарный индекс, labels/vector correspondence и оба профиля. Нативные зависимости сейчас отсутствуют: это qualification gap, не product defect. Большая SentenceTransformer, корпусный rebuild, model quality и performance не нужны для одного wiring proof и здесь не запускались.

**C95-G02 — EMB-02 closure.** Current code уже содержит versioned generation publisher. Следующий пакет должен отдельно проверить empty/nonempty selected state, failed second save/selector/copy, authoritative inventory, actual Academic/Catalog readers и mismatch refusal. Existing flat-empty test доказывает только сохранение compatibility bytes: его PASS не означает, что старый индекс снова выбран текущим. Ни input hash, ни manifest presence не заменяют output integrity/currentness/admission.

## 6. Воспроизводимость

[Команды / exit / logs](../04_Проверки/C95_EMB01/commands.json) · [Diagnostics](../04_Проверки/C95_EMB01/bounded_diagnostics.json) · [Effective text corpus](../04_Проверки/C95_EMB01/run02/effective_text_corpus.json) · [ID/vector trace](../04_Проверки/C95_EMB01/run02/order_vector_trace.json) · [SQL capture](../04_Проверки/C95_EMB01/run02/SQL_capture.json) · [Index capture](../04_Проверки/C95_EMB01/run02/index_capture.json) · [Native status](../04_Проверки/C95_EMB01/native_verification.json) · [Границы](../04_Проверки/C95_EMB01/Чтение_и_границы.md) · [Остатки](../01_Реестры/C95_остатки.json).

Run02 exit0,5MATCH/4PASS. Run01 имел ошибочное ожидание нашей оснастки None вместо actual `unbound`; сохранён, не классифицирован как дефект продукта. Повторные tests не удваиваются. .hnsw fixtures — **JSON, не native binary HNSW**. Реальны whole wrappers/kernel, NumPy/NPZ, hashes, generation files и atomic stage manifests. Parent shells, SQL/encoder/HNSW и Catalog loader seams перечислены.

Native kernel import PASS только на уровне импорта. HNSW, DuckDB, pytest и SentenceTransformer отсутствуют; catalog native import BLOCKED на транзитивном Python3.14 syntax. Native ANN/model quality, real DB/source pipeline и full selected-reader chain — UNRUN. Репозиторий, зависимости и внешние сервисы не менялись.

**95/127 рассмотрены ограниченно. Следующий — EMB-02; подготовка заданий исполнителю ещё не начата.**
