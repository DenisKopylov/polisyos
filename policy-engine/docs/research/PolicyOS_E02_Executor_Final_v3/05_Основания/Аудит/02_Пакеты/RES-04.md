# RES-04 — точный request/history и граница атомарной публикации
## C46 · 31 октября 2026 года

**Исходные IDs:** B74, B75, B76. **Порядок:** 46/127. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Только аудит.

## Решение

Текущий checkpoint действительно связывает effective request, сверяет occurrence-prefix и восстанавливает отдельные исходные results. Исходные flat/nested sidecar collision и порча старого поколения **до** publication исправлены. Это полезная реализация, а не только новые DTOs.

**Подтверждены три ограниченных остатка:** cleanup после уже состоявшегося JSON rename; общий namespace state/history sidecars; потеря нового поля `restricted_invocation` при заявленной complete history. **21 итоговый bounded MATCH; native pytest BLOCKED.** Не заявляется production-порча или неверная authoritative публикация.

## 1. Матрица исходных IDs

| ID | Подтверждённая механика | Остаток |
|---|---|---|
| B74 | Plan/params/input/seed identity, occurrence-prefix, live validation replay; точный suffix resume | G01 native; G02 partial reuse/portable scope |
| B75 | Отдельные 6/7, исходный seed 7 и metadata, warnings/artifact arrays/typed bound | R03 текущий result field; G01/G02 |
| B76 | Разные flat/nested refs, generations, per-path writer lock, content/shape/dtype/path guards | R01 post-publication cleanup; R02 state/history namespace; G01 |

[Полная карточка](../05_Источники/RES-04_исходные_строки.txt), строки 5649–5771.

## 2. B74 — проверяется effective request, не один список FQN

Filename-compatible chain digest сохранён, но persisted execution digest дополнительно включает occurrences, effective params/overrides, static params, signature/cache identity, bindings, predecessors, initial_state, seed и validation diagnostics. Перед resume проверяются actual prefix, context/warnings и execution identity. [S01:388–443](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/checkpointing.py#L388-L443) [S01:633–759](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/checkpointing.py#L633-L759)

P01 проходит actual composer → explicit typed binding → IO → checkpoint executor → atomic JSON/NPY → fresh load → новый executor: cold/resume **7**, история **6/7**, исходные seeds **7/7**, fresh resume делает **0 dispatches**. P02 восстанавливает первый узел и исполняет только Add — один dispatch, итог 7.

P03 factor 3 отказывает по старой точке; cold **10**. P04 input 4 отказывает; cold **9**. P05 seed 99 отказывает, а не переписывает исторические metadata. P06 прежние FQN с другими UUID отказывают по prefix. P07–P09 испорченный prefix, legacy без execution identity, incomplete/count-mismatched history и erased context отвергаются до dispatch.

Это exact-request reuse с консервативным отказом изменённому запросу, не доказанный selective ancestor recomputation. Useful existing exact path сохраняется; отсутствие отдельного универсального механизма частичного scientific reuse не объявляется автоматическим дефектом.

## 3. B75 — реальные поля истории и оставшаяся потеря

Snapshot сохраняет output, timing, исходные reproducibility fields, equivalence ref, slot outputs, artifacts, warnings и validated bound; restore строит отдельный MethodResult для каждого occurrence. [S01:762–849](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/checkpointing.py#L762-L849)

P10 дополнительно переносит actual typed DTOs: timing 1/.25/.1, solver status UNKNOWN, fixture runtime/fingerprint, warnings, NPY artifact и **INDETERMINATE** bound с исходным lower tuple. Мы не подставляли final_state вместо 6 и не выдавали current reader runtime за исходное исполнение. Aggregate reproducibility builder при этом остаётся явной границей fixture, не native attestation.

### C46-R03 — `restricted_invocation` отсутствует в snapshot/restore

Current `MethodResult` содержит typed `restricted_invocation`; NumpyRunner переносит его, dispatcher связывает selected runner identity. Но checkpoint snapshot и восстановление этого поля не имеют. [S13:176–230](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/protocol.py#L176-L230) [S10:158–195](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/numpy_runner.py#L158-L195) [S18:1018–1029](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/dispatch.py#L1018-L1029)

P20 проходит actual typed result → automatic checkpoint → fresh load → resume. Исходный field имеет **status=unavailable** и явную audit-fixture limitation; после восстановления **None**, хотя `history_complete=True`. Это доказанная потеря current result data, не воспроизведение потери настоящего verified receipt или повышения полномочий. Минимальное продолжение — перенести поле через существующий snapshot owner либо честно обозначить соответствующую неполноту, не создавать его заново как новое наблюдение.

## 4. B76 — сохранённые защиты

Generation prefix при повторном path не перезаписывает прежние arrays. Однозначное encoded path используется при collision/новом поколении. Manifest refs связывают dtype, shape и content digest; readback проверяет их и безопасный путь. Writers одного manifest сериализованы реальным `fcntl` lock. [S01:882–990](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/checkpointing.py#L882-L990) [S01:993–1055](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/checkpointing.py#L993-L1055)

- P11/P12: `a_b=[1]` и `a→b=[2]` остаются разными при обеих очередностях ключей.
- P13: failure до manifest publish оставляет прежние JSON bytes и массив [1] полностью читаемыми.
- P15: два настоящих concurrent writers завершаются coherent final generation, массив и scalar marker совпадают.
- P16: missing/unreadable/wrong shape/dtype/content sidecars отвергаются fresh reader.
- P17: relative/absolute escape и symlink отвергаются до admission; всё создано только внутри audit directory.
- P19: unsupported value и object-array нового save не портят old snapshot.
- P21: explicit `fail_on_checkpoint_error=False` сохраняет вычисление 7 и два bounded save issues, не притворяется успешным checkpoint.

## 5. C46-R01 — ошибка после commit-point удаляет опубликованные данные

`_atomic_write_bytes` делает `replace(final_path)`, затем directory fsync. Если последний шаг поднимает OSError, внешний save попадает в общий cleanup и удаляет весь `published_sidecars`, хотя новый manifest уже видим. [S01:227–244](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/checkpointing.py#L227-L244) [S01:1072–1079](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/checkpointing.py#L1072-L1079)

P14 сначала сохраняет old [1]. Новый save записывает отдельный generation [2]; fault observer ждёт **реального изменения JSON bytes после rename**, затем поднимает controlled fsync error. Save отказывает, но active JSON уже новый, его sidecar удалён, fresh load сообщает **missing sidecar**. Old JSON по этому path больше нет. Это не прежний pre-publication сценарий: P13 рядом показывает, что тот исправен.

Нужно различать публикацию и durability-confirmation в существующем owner, чтобы cleanup не уничтожил уже referenced data. Добавлять ещё один manifest/transaction subsystem без необходимости не предлагается; existing generation/lock/fsync primitives полезны.

## 6. C46-R02 — state/history имеют общий encoded namespace

State и `{"node_results": ...}` сериализуются отдельно с одинаковым stem, затем `sidecars.update(history_sidecars)` без collision guard. При reused generation оба используют encoded path. [S01:196–211](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/checkpointing.py#L196-L211)

P18 создаёт supported state с собственным ключом `node_results`, а history получает настоящий `_snapshot_node_result` от actual typed MethodResult; completed prefix и history оба размера 1. Первое поколение читается. При повторном save state path `node_results/0/output/arr` и history path с тем же именем получают **один ref** для разных массивов. Save возвращает success, но fresh load отказывает по **content mismatch**.

Следовательно, content guard сохраняет fail-closed поведение, **не** принимает молча неверный массив. Остаток — producer может публиковать нечитаемый snapshot. Узкий ремонт: разделить root namespace либо сериализовать единое envelope существующим encoder, без нового канонизатора.

## 7. Границы проверки

Полный `test_res_04.py` (501 строк) прочитан. Native pytest не дошёл до collection: module отсутствует. Итог — **21 MATCH / 0 ERROR**. Initial 9/12 — ошибка synthetic root method: actual root fallback имеет mapping, а fixture ожидал scalar; это исправлено только вне checkout. Следующий fresh run 21/0; финальный fresh run дополнительно усилил namespace witness actual DTO snapshot, снова 21/0. Scripts/logs и negative filesystem fixtures сохранены.

DTO definitions реальные, runtime values всё равно synthetic; registry/dispatcher, neutral semantic lookup, hash/import и aggregate reproducibility seams раскрыты. Core ArtifactStore соседние writers прочитаны, но filesystem checkpoint не выдаётся за CAS-backed custody. Связь с реальным policy/scientific authority, производственная частота сбоев и portable executable reconstruction не установлены.

[Диагностика](../04_Проверки/C46_RES04/bounded_diagnostics.json) · [Команды](../04_Проверки/C46_RES04/commands.json) · [Границы](../04_Проверки/C46_RES04/native_verification.json) · [Источники](../05_Источники/C46_источники.json) · [Остатки](../01_Реестры/C46_остатки.json).

**46/127 пакетов рассмотрены ограниченно; 111 уникальных B/LA частично оценены. Следующий — CAL-05. Полного закрытия нет.**
