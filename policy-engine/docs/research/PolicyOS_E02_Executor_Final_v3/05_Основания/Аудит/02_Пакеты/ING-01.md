# ING-01 — request cursor, подтверждённый прогресс и replay
## C99 · LANE-08 · B79, B80, B88

**Решение: частично подтверждено, не закрыто.** B79/B80 больше не разъединены: cursor допускается через actual source-owner witness, передаётся поддержанным request transform и продвигается только после per-source persisted evidence/provenance checks. B88 больше не вызывает ordinary ingestion после replay failure. Найден один ограниченный остаток: session с двумя connector/dataset fixture namespaces воспроизводится только в namespace первого источника.

Срез `20d9009be21097bfbdc38a546a15cc60213b8ace`. **4 MATCH; 6 неизменённых existing bodies / 8 cases PASS.** Проверена bounded finite-file цепочка и actual replay simulator/aiohttp; CAS custody и ingestion delegate — fixtures. MATCH включает воспроизведение остатка. 99/127 рассмотрены; следующий ING-02.

## 1. Две оси

**Исходный ремонт.** Mapping и typed ConnectorManifestSpec идут через общий intake. Incremental version входит в FetchRequest через существующий поддержанный callback, не неизвестный keyword. Aggregate datasets_fetched и local now не разрешают source progress. Replay исключения распространяются без live fallback.

**Содержательная способность.** Независимый reader действительно читает весь конкретный source-owned файл, bind-ит physical transport и пересчитывает membership; producer читает тот же файл, а consumer получает полный materialized source state даже при пустой delta. Но область — **finite_source_fixture**, не production completeness/currentness. Это полезная existing integrate boundary с честными ограничениями, а не доказанная универсальная инкрементальность всех API. Missing live owner — G, не повод убрать fail-closed или написать новый registry.

## 2. Матрица исходных IDs

| ID | Actual owner / проверки | Решение и остаток |
|---|---|---|
| B79 | S01:792–941, S03, S05; P02/P04 | Request versions None→a8→a9 реально доходят до finite source fetch; typed/dict intake эквивалентен. Legacy cursor без resolved proof не hint. Native/live I/O qualification G01 |
| B80 | S01:540–789,942–997; S02–S03; P01/P02/P04 | Только A a8→a9, B без подтверждения не продвинут; partial без snapshot. Source time не fetched/local now; CAS-before-index и predecessor conflict сохранены. Native store chain G01 |
| B88 | S01:1124–1204, S06–S07; P03 | Missing/corrupt replay не вызывает ordinary/native transport. Single-source recorded bytes успешны. Multi-namespace completeness R01, full persisted success provenance G01 |

[Исходная карточка целиком](../05_Источники/ING-01_исходные_строки.txt) · [Pinned source index](../05_Источники/C99_источники.json).

## 3. Owner → producer → persisted artifact → consumer

`SourceProgressContract` bind-ит active SourceContract, конкретный schema hash, source/dataset, event/version roles, strategy и partition. `FiniteSourceProgressReader` читает полный bounded файл (8 MiB), отвергает duplicate keys, неоднозначные versions/event keys, non-append-only history и ложный current header. Transport должен быть тем же actual local file; отдельная fixture не может разрешить arbitrary live connector. Frozen frame проверяет изменение bytes/inode/path (`S03`, `S08`).

Перед запросом `_cursor_version` требует capability **и** frame/store. `admit_cursor` перечитывает retained witness, payload, exact request и provenance; valid-looking ETAG/revision/time без этого остаётся full-fetch-only. Proxy передаёт approved request в actual file replay, сверяет delta со всей history и возвращает полный current source state. Это не фильтрация произвольного live response по caller-supplied expected IDs (`S01:299–449,482–511`, `S03:238–374,495–575`).

`run_orchestrated_ingestion` действительно имеет request_transform/raw/persisted sinks. Actual lower producer применяет transform до fetch, сохраняет raw result отдельно от transform/PII/sanitized result и вызывает persisted sink лишь после source payload, graph и EvidenceBundle. Эта часть прослежена по полному body, но **исполнялся explicit delegate**, не native ingestion (`S04:573–696`, `S05:1044–1521`).

Cursor promotion сопоставляет exact captured object/request, selected evidence identity, resolved graph/stable ID, source membership, payload bytes, source boundary и graph attributes/edge. Предыдущий legacy cursor без admission не превращается молча в committed authority после нового fetch. CursorStore compare-and-advance под file lock не даёт медленному run перезаписать новый predecessor; artifact write предшествует index publication. Local now остаётся created_at записи, не watermark. При missing per-source progress result становится partial/failed, snapshot не создаётся; partial scope записывается в отдельную проекцию evidence (`S01:586–997`, `S02`).

Replay owner материализует RecordSession через ReplayStore и входит в actual REPLAY simulator; exception не перехватывается для ordinary retry. Current record sibling также отказывает от unrecorded retry, но в C99 source-only: live RECORD не включался (`S01:1010–1204`).

## 4. Различающие результаты

1. **P01 — 8 cases из 6 unchanged bodies.** Actual complete source vs omitted row/wrong dataset; изменение contract/schema/source binding; duplicate readers; stale predecessor conflict; owner bytes movement; current header, скрывающий следующий snapshot. Все PASS. Cursor test использует file-backed CAS fixture, а не native FileSystemCAS.
2. **P02 — finite producer → cursor → fresh intake.** Первый source A a8 проходит без hint; после append A a9 запрос получает a8, A продвигается до a9, failed B остаётся без cursor. Итог partial, snapshot=None. Следующий request получает a9; actual raw delta содержит0 rows, reconciled consumer state —2 rows. Удаление каждого из пяти proof members отвергает retained cursor. Все WatermarkType без proof остаются неавторитетными. Actual contracts, whole reader, serializer, selected mode и cursor file/index owners реальны; orchestration/persistence producer и profile verification fixtures явно отделены.
3. **P03 — actual replay transport.** Missing fixture даёт MissingFixtureError, corrupt body — JSONDecodeError; ordinary calls=0 и guarded native aiohttp calls=0. Записанные value7 и value9 воспроизводятся по отдельности. В одном session с двумя правильными namespaces второй request ищется под первым и отказывает, хотя его fixture присутствует.
4. **P04 — boundary и отказ сохранения.** Source timestamp2024-01-09 остаётся watermark при fetched_at2026-01-01. Missing/disagreeing source timestamp, has_more, next token, incomplete fraction и несогласованная version epoch отвергаются; revision policy не смешивается с timestamp. Typed/dict intake даёт одинаковые pairs/spec. Controlled put_json failure до cursor index change сохраняет старый committed cursor8.

## 5. Остатки и сохраняемое поведение

**C99-R01, low — namespace replay session.** [run_replay_mode](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/fabric/data_plane/modes.py#L1164-L1175) задаёт simulator первым dataset; [ReplayStore](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/fabric/data_plane/replay_store.py#L97-L114) пишет layout каждого fixture отдельно. Actual simulator использует только заданную пару. Поддержать declared per-source session layout на existing request boundary либо явно отказать unsupported input до частичного исполнения; не сканировать всё в поиске «подходящего» ответа и не возвращать live fallback.

**Точная граница R01:** current `run_record_mode` тоже помечает весь capture первым namespace. Поэтому не установлено, что любая текущая record→replay пара ломается. Воспроизведена ограниченная несовместимость корректного per-source RecordSession layout, который текущий ReplayStore принимает; два individual controls успешны. Никакого реального сетевого запроса или ложного mode=live/replay успеха не было.

**C99-G01 — native/end-to-end и реальный source scope.** Нужен supported Python run с настоящими CAS/profile/tenant boundaries, whole ingestion cache/transform/PII и produced graph, mixed partial sources, cursor reopen/removal controls и downstream source collection/snapshot. Replay success здесь возвращает evidence ref fixture: full persisted provenance и served HTTP outcome не подтверждены. Native real-source I/O savings, source rights, currentness и scientific validity не измерялись. Расширять existing owner-reader contract для конкретного source с реальными основаниями; не признавать version/header/completeness self-report достаточным и не требовать отсутствующего универсального deterministic inventor как «исправления».

**Сохранить:** совместное B79+B80 admission; pair identity и explicit default partition scope; conservative legacy refusal; actual request binding; independent whole finite source denominator; append-only event/version rules; empty delta → whole consumer state; source-time boundary, per-source persisted callbacks, CAS-before-index и conditional predecessor; partial evidence без completed snapshot; replay error propagation без ordinary/live delegate. Global exactly-once не заявлять; stream guarantees отдельно ING-02/03.

## 6. Воспроизводимость

[Команды](../04_Проверки/C99_ING01/commands.json) · [Диагностика](../04_Проверки/C99_ING01/bounded_diagnostics.json) · [Source nodes](../04_Проверки/C99_ING01/run04/selected_source_identity.json) · [Compatibility adaptation](../04_Проверки/C99_ING01/run04/units_compatibility.json) · [Batch trace](../04_Проверки/C99_ING01/run04/batch_trace.json) · [Replay trace](../04_Проверки/C99_ING01/run04/replay_trace.json) · [Native status](../04_Проверки/C99_ING01/native_verification.json) · [Fixtures](../04_Проверки/C99_ING01/fixture_authority_limits.json) · [Чтение](../04_Проверки/C99_ING01/Чтение_и_границы.md) · [Остатки](../01_Реестры/C99_остатки.json).

Run01/02 exit1 из-за явно сохранённых harness setup ошибок; run03 exit0,3 MATCH/8 PASS; final run04 exit0,4 MATCH/8 PASS. Они не суммируются. Selected mode/ingestion AST nodes unchanged, без syntax rewrites. Одна зависимость units импортирует TypeVar из установленного typing_extensions вместо typing для Python3.12; package shells и fixture provider/CAS/delegate обозначены. PEP695 поддерживается3.12 — это не причина данного отказа.

Native IR и cursor DTO imports PASS. Native modes/source-contract/simulator graph BLOCKED на TypeVar(default=...) baseline mismatch; source-progress graph также BLOCKED на CAS Python3.14 except syntax. pytest отсутствует. Actual aiohttp3.14.4 работает только через REPLAY interceptor с guarded egress; другие transports и whole process network sandbox не квалифицированы. Checkout/зависимости не менялись, live requests/модели не запускались.

**99/127 — промежуточный аудит; следующий ING-02. Фаза заданий исполнителю не начата.**
