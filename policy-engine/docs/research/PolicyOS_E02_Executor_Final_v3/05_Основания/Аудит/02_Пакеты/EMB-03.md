# EMB-03 — Legal incremental reuse и старый backend entrypoint

## 1. Решение

**Оба исходных механизма существенно исправлены.** Current Legal builder повторно использует запись только по actual projected text и совместимому model/device/dimension/assets/tokenizer/projection profile; актуальный membership исключает withdrawal. Старый NPZ не становится подтверждённым cache задним числом. Wrapper `build_embeddings_and_index` теперь отвергает любой `backend != None`, а default вызов делегирует canonical builder с явным profile.

**5 MATCH, 11 unchanged existing test bodies / 15 cases PASS. Новых R не установлено.** Это не full native closure: весь builder исполнен с двумя документированными синтаксическими adaptations, SQL/encoder/index — fixtures. **C97-G01** сохраняет native/owned serving qualification, **C97-G02** — точную границу compatibility lifecycle. Shared publisher **C96-R01** не дублируется.

Срез `20d9009be21097bfbdc38a546a15cc60213b8ace`. [Полная карточка](../05_Источники/EMB-03_исходные_строки.txt) · [Источники](../05_Источники/C97_источники.json).

## 2. Матрица исходных IDs

| ID | Текущий результат | Остаток |
|---|---|---|
| LA-040 / M | Content-bound reuse, assets/tokenizer/rule invalidation, current membership, historical rebuild, shared publisher | G01 native producer/reader/owned serving; общий C96-R01 |
| LA-042 / C | Unsupported backend явно отказан; canonical default profile, chunk/result/exception identity сохранены | G01 native; G02 внешний/lifecycle scope, если заявляется retirement |
| LK20 | Generic content/assets identity не заменяет executable runtime binding и claim-to-source verification | Не выдавать fixture candidate за legal authority |
| A14 | Legal precomputed vectors идут в existing common publisher | Не создавать третий publication framework и не смешивать reuse с output admission |

## 3. Actual owner → producer → consumer

`_embed_table` читает каждую таблицу внутри transaction, по ordered ID/LIMIT/OFFSET, формирует actual texts до32000 символов и проверяет полный count/unique IDs. Три разные projections сохранены: entities с aliases, facts с legal condition/exception/procedure/threshold/quote и provisions. Per-record basis получает именно эти UTF-8 bytes (`S01–S02`).

`_load_reusable_vectors` требует selected complete generation, совпадение model/device/dimension и точного generator rule с identity encoder assets. Далее сопоставляет content identity каждого **текущего** члена и его finite vector. Историческая flat pair без selected basis не используется как cache. Незатронутые записи могут быть reused, удалённые не копируются в текущий комплект. Same dimension сама по себе ничего не разрешает (`S01:75–168`).

Encode идёт только для rows без доказанного reuse; проверяются shape/finite values. Перед публикацией заново измеряется encoder identity; изменение assets во время encode отказывает. Current ordered matrix передаётся уже существующему `_build_embedding_generation_from_vectors`: собственный третий Legal publisher не создан. Общая preselection semantic output граница остаётся описанной в [C96](EMB-02.md), а не засчитывается ещё раз (`S01:171–340`, `S03:252–346`).

Actual Legal reader сверяет selected matrix/index с полным current projected membership; query intent — immutable snapshot inventory и generation ID. Затем нужен отдельный owned runtime material. Generic encoder с подходящими assets остаётся candidate и не даёт автоматически право на query encode. Controlled owner действительно существует: source-pinned multilingual-e5 revision, CPU/1024, SentenceTransformer2.7.0, local-only assets, runtime/source/callable binding и pre/post lease checks. Это **узкий declared profile**, не доказательство универсального backend и не причина удалить generic candidate producer (`S09–S10`).

Public hybrid/HTTP source сохраняет text fallback с typed vector refusal, выбирает `search_candidate` и возвращает отдельное `legal_source_relation_verification_not_established`. Нахождение близкой строки или ownership модели не доказывает, что нормативный SPO вывод следует из источника. Эти public paths прочитаны, не исполнены в C97 (`S11,S13,S14`).

## 4. Различающие проверки

1. **P01 — 15 cases, 11 existing bodies.** Unchanged append, changed text same ID, withdrawal, model/dimension revision, same-dimension asset change при неизменном configured label, projection rule, corrupt selector rebuild; backend refusal/default forwarding; три exact projection positives и три wrong-shape negatives. Все PASS, но не native suite.
2. **P02 — усиленные reuse controls.** Полностью unchanged corpus не вызывает encode; изменение tokenizer пересчитывает. Удаление selector оставляет historical flat bytes, но вызывает rebuild; missing/corrupt basis также не reuse. `incremental=False` пересчитывает. Удаление всех records выбирает typed empty, embedded/skipped=0 и сохраняет old generation directory. Flat historical bytes не объявлены current.
3. **P03 — три populated projections и CLI body.** Entities3/fact1/provision1; chunk_size2, quote400, text32000; четыре thermal hooks0.25. BEGIN/COMMIT каждого чтения реально проходят через source orchestration, но fake SQL не доказывает transaction isolation. Полный actual `_cmd_embed_local` повторно использует все пять records и пишет настоящий stage JSON с тремя complete generation metadata; parser/process и owned profile branch не запускались.
4. **P04 — actual selected reader/query gate.** Selected entity index загружается и сопоставляется с current row. Даже fresh intent и совпадающие generic encoder assets дают `query_encoder_runtime_material_not_established` **до encode**. Warm cache после изменения text отвергается; после rebuild старый query intent отвергается отдельно. Fixture constructor не подменяет сами проверенные методы, но full public ANN search/HTTP не исполнялись.
5. **P05 — отказ вместо ложного обновления.** Изменение tokenizer assets внутри encode приводит к ValueError и сохраняет прежний selector. BackendTrap не читается и не вызывает canonical target. Default wrapper передаёт тот же exception object, что target; result identity/profile/chunk_size17 проверены existing body.

## 5. Сохранить и завершить

**Сохранить:** дешёвый reuse действительно неизменённых членов; text/asset/tokenizer/rule binding; current withdrawal semantics; три projections; ordered IDs; chunked SQL/encode, normalization и thermal hooks; embedded/skipped stats; legacy bytes как историю без cache authority; один common publisher; honest wrapper refusal; separate query intent/runtime/source-relation gates и text fallback.

**C97-G01 — native и полная capability цепочка.** В supported environment нужен малый real DuckDB/HNSW corpus и весь public reader path. Current tests с fake encoder полезны, но JSON индекс не удостоверяет binary HNSW, native label/vector behavior или ANN recall. Отдельно требуется positive supported owner-resolved material → producer → fresh served query с текущим intent, а также отказ при drift. Не обходить gate ради зелёного search; не скачивать большую модель в рамках этого аудита. Generalization к иным моделям/устройствам — расширение existing owner contract по реальной потребности, не автоматическое признание текущего profile универсальным. Source-relation verification остаётся отдельным substantive gap и не чинится ещё одной контрольной суммой.

**C97-G02 — compatibility не равно retirement.** Tracked search показывает current definition, два test callsites и historical docs/baseline; действующего source caller, передающего backend, не найдено. Это не доказательство отсутствия внешних/dynamic callers. Retained default wrapper уже честен: unsupported backend не превращается молча в local default. Если требуется заявить завершённую миграцию/удаление, нужна конкретная owner/release/caller область; произвольный sunset или новый polymorphic API не нужны. В текущем запросе source ничего не удаляется.

**Исторические native claims не переносить.** Repository review `full-id-C-assessment.json` описывает старый ab441 installed profile с supplied supported encoder/readback и отдельно оговаривает непереносимость старого wheel. Текущий wrapper отвергает **все** non-None backend; P01/P05 проверяют именно это. Старое свидетельство сохранено в исходном профиле, но не становится current native PASS (`S18–S19`).

## 6. Воспроизводимость и границы

[Команды](../04_Проверки/C97_EMB03/commands.json) · [Диагностика](../04_Проверки/C97_EMB03/bounded_diagnostics.json) · [Syntax adaptations](../04_Проверки/C97_EMB03/run01/syntax_adaptations.json) · [Three-projection trace](../04_Проверки/C97_EMB03/run01/three_projection_trace.json) · [Reader/query boundary](../04_Проверки/C97_EMB03/run01/reader_query_boundary.json) · [Native status](../04_Проверки/C97_EMB03/native_verification.json) · [Fixture границы](../04_Проверки/C97_EMB03/fixture_authority_limits.json) · [Чтение](../04_Проверки/C97_EMB03/Чтение_и_границы.md) · [Остатки](../01_Реестры/C97_остатки.json).

Run01 exit0,5 MATCH/15 PASS. Whole builder имеет **две** parenthesizations except для Python3.12 вне checkout; original/adapted SHA сохранены. Actual kernel, NumPy/NPZ, asset/tokenizer hashing, files, selected reader methods и CLI stage writer реальны. Parent shells, SQL/encoder/HNSW и reader constructor fixtures обозначены. `.hnsw` — JSON, не binary. Test bodies unchanged не означают native import неизменённого builder.

Native builder BLOCKED на source line111, native Legal store — line415 из-за supported3.14 syntax в3.12. Native runtime-material module import PASS, но resolution/model/lease не выполнялись. HNSW/DuckDB/pytest отсутствуют. Real models, native query/HTTP, scientific/Legal authority и native transaction/crash semantics — UNRUN. Checkout и зависимости неизменны.

**97/127 рассмотрены ограниченно; следующий DFI-03. Фаза заданий исполнителю ещё не начата.**
