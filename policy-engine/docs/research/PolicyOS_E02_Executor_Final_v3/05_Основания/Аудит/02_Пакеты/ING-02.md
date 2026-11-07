# ING-02 — окно, подтверждённая позиция и полная lineage
## C100 · LANE-08 · B81, B82, B85

**Решение: частично подтверждено, не закрыто.** Основные ремонты реально связаны: observed position отделена от committed frontier; pending rows, ordinal, event-time и contributor refs сохраняются и восстанавливаются; окно получает фактические inputs, а не только закрывающий chunk. Найден узкий recovery остаток: обычная ошибка до первого commit оставляет диагностический checkpoint, который текущий owner не может возобновить.

Срез `20d9009be21097bfbdc38a546a15cc60213b8ace`. **4 MATCH; 8 неизменённых existing test bodies / 20 cases PASS**, bounded, не native pytest. MATCH включает воспроизведение дефекта. Whole streaming/session/registry/pool/local JSONL producer/CursorStore реальны; CAS custody — fixture. **100/127**, следующий ING-03; полного закрытия и фазы заданий исполнителю пока нет.

## 1. Две оси оценки

**Исходный ремонт.** Handler больше не выдаёт last polled chunk за committed frontier. Пустая граница обозначена явно, fallback rewind повторяет chunk0. State checkpoint содержит версию, window policy, pending rows/refs, ordinal, next-slide и максимальное event time. Paired cursor/checkpoint intent проходит prepared→commit→readback→committed; это полезный existing owner, а не новые декларации рядом с прежним consumer.

**Содержательная способность.** Actual JSONL producer читает реальные bytes; независимый finite source reader проверяет весь набор event/version identities и physical transport. Эти данные поступают в actual processor и повторно открываемые cursor files. Writer окна переносит все фактические contributor refs и policy. Однако такая synthetic/replay цепочка не утверждает внешнюю истинность, production currentness, права, универсальный exactly-once или исполненную downstream revalidation. Native CAS и whole served consumer не заменены авторитетом fixture.

## 2. Исходные IDs

| ID | Что сохранено и проверено | Остаток |
|---|---|---|
| B81 | Actual checkpoint(use_observed_chunk=False), empty frontier marker, rollback к прежним metadata/dedupe и whole fallback rewind. Existing crash/reopen cases читают JSONL, сохраняют raw/window, повторно открывают store и сопоставляют bytes/rows. | C100-R01: first ordinary error создаёт невосстановимый diagnostic latest. Глобальная native commit/rewind атомарность не доказана. |
| B82 | Versioned accumulator/order state, policy binding, exact ordinal и refs. COUNT/SESSION/SLIDING/TUMBLING crash/restart; четыре mismatch cases отказывают до rewind/poll без новых артефактов. | B81/B82 принимать совместно; native long-running/late-event and physical crash qualification остаётся G. Не закрывать окно искусственно при restart. |
| B85 | Actual window writer получает union refs из concrete row identity; final flush и новый bucket trigger не теряют/не выдумывают contributor. Проверены payload rows, manifest inputs и declaration lineage. | Native отзыв A и зависимое окно через штатный consumer/revalidation не исполнялись: G, не доказанный defect. |

## 3. Producer → state → consumer

1. `EventStreamConnector.fetch_stream` читает ограниченный локальный файл и реально формирует chunks, а не возвращает expected array из probe [S05:117–146; S06:121–145]. Registry выбирает зарегистрированную factory/runtime identity, session владеет настоящим private pool [S15–S16; S01:501–934].
2. Owner reader связывает весь physical JSONL, partition и schema event/version; stream admission не принимает отдельный matching fixture за live-source authority [S13:147–237,393–494]. Witness содержит deciding bytes и честно limited scope. CAS selected-view проверка в этом запуске fixture, отдельно от actual owner parsing.
3. Processor отделяет pending и committed; сериализует operator state вместе с dedupe horizon/clock/source witness. Actual CursorStore пишет blob раньше atomic mutable index и читает пару заново [S01:1497–1984; S02:176–505]. Это не распределённая транзакция со внешним источником.
4. При restart identity/clock/schema/policy/capacity проверяются до rewind. Accumulator восстанавливает pending state, а не делает принудительный flush. Прочитанный без source owner legacy/default test не заменяет эту admission boundary [S01:2485–2600].
5. Actual async window writer пишет `InputRef(role="stream_chunk")` для всех участников, а witness — отдельным role. Selected mode далее собирает refs в manifest/evidence/snapshot и явно оставляет `production_currentness=not_established` [S01:3180–3243; S07:1391–1586]. Последний consumer прочитан, не исполнялся целиком.

## 4. Исполненные наблюдения

| Наблюдение | Результат и различающий контроль |
|---|---|
| P01 |13 existing cases PASS:4 window strategies ×2 BaseException boundaries after raw/window write; final checkpoint ref совпадает с latest committed после fresh reopen;4 source schema/window policy/key/horizon mismatch отказывают до poll/rewind. Actual source bytes и persisted rows/lineage сравниваются, не только counters. |
| P02 |5 existing bodies /7 cases PASS: pending roundtrip COUNT/SESSION/SLIDING; concrete row identity без stale dict-id; empty refs отвергаются. |
| P03 |3 ordinary first-frontier failures воспроизводят R01. BaseException до raw повторяет все3 строки; ordinary failure после первого commit повторяет2 оставшиеся. Во всех трёх проблемных случаях cursor не продвинут. |
| P04 |41 строка ×4 стратегии; interruption после19, JSON roundtrip state. Rows, ordinal, logical window ID, time bounds и exact contributor refs равны непрерывному проходу. |

Результаты и код: [диагностика](../04_Проверки/C100_ING02/bounded_diagnostics.json), [команды](../04_Проверки/C100_ING02/commands.json), [probe](../04_Проверки/C100_ING02/probe_ing02.py), [first-frontier traces](../04_Проверки/C100_ING02/run05/first_frontier_failures.json). Ранее неудачные harness runs сохранены, не суммированы с final run05.

## 5. C100-R01 — ошибка до первой границы блокирует повтор

В свежем admitted finite-owner потоке инъецирован RuntimeError после poll/dedupe: перед raw write, сразу после raw write и сразу после window write. Handler сохраняет PAUSED checkpoint с `frontier_committed=False`, пустым operator state/dedupe и observed diagnostic fields, но без `ingestion_clock_profile` и `source_progress_witness_ref`. Новый CursorStore действительно читает этот latest. Тот же source/config затем получает **«ingestion clock profile changed across restart»** до replay.

Это не наблюдённая потеря строк и не false success: cursor отсутствует, source bytes сохранены, отказ явный. Но transient processing failure превращается в persistent recovery refusal без фактической смены clock/owner. Positive controls отделяют этот путь от общей неработоспособности: BaseException до первого raw не создаёт такого diagnostic checkpoint и успешно повторяется; ошибка после уже committed frontier сохраняет нужные metadata и тоже повторяется.

Источник: [recovery admission2490–2507](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/fabric/data_plane/streaming.py#L2490-L2507) против [first-frontier error writer3049–3109](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/fabric/data_plane/streaming.py#L3049-L3109). Missing witness — второй видимый source omission, но следующий отказ после ручного исправления clock **не исполнялся**.

Остаток: согласовать существующие writer/admission границы пустого frontier. Не удалять guards, не продвигать offset, не переносить pending keys как committed и не создавать новый storage engine. Native CAS impact/frequency не измерены. Severity medium относится к bounded невозможности штатного повторного запуска, не к безопасности или необратимой потере.

## 6. Сохранить и квалифицировать отдельно

Сохранить useful partial work: explicit empty frontier; committed metadata copy; full operator state; paired intent/readback; conditional compensation; owner/schema/clock admission; exact row refs; policy snapshot; отсутствие global exactly-once обещания.

**C100-G01:** native Python3.14/pytest, настоящий CAS selected-profile/tenant/input closure, физический kill/power-loss, межпроцессные index failures, внешние connector commit/rewind tokens и withdrawal A→dependent window через штатную revalidation не исполнены. Captured inputs A+B доказаны, но не приравнены к native отзыву. Synthetic finite identities не эмпирическая, правовая или научная authority. LLM остаётся semantic proposer; отсутствие универсального deterministic inventor не объявлено дефектом.

## 7. Дополнение к сохранённому C99, без переаттестации

В ходе текущего чтения обнаружены и прочитаны дополнительные actual integration tests в `test_e02_c_streaming_oracle.py`: B79 finite-file typed/dict request→cursor→fresh snapshot и отказ live endpoint363–542; B80 partial A/B→fresh Foundry collection и removal/wrong-row negatives543–750; B88 owned catalog→served HTTP→replay→persisted evidence2008–2134. Actual served dispatcher `run_data_ingestion` также прочитан [S17]. Они **существуют**, но здесь не запускались; C99-G01 не означает отсутствие этих tests и не превращается задним числом в native PASS. Сохранённый C99 не изменён. Его multi-namespace R01 этим single-source integration не опровергается.

## 8. Границы и следующий шаг

Native streaming/CursorStore imports BLOCKED на Python3.14 except syntax в CAS под доступным Python3.12; pytest отсутствует. Bounded graph использует package shells и одну dependency TypeVar import adaptation; production streaming code целиком неизменён. CAS fixture сохраняет actual canonical bytes и inputs, но его profile/verify/load semantics не native. Existing valid-row sanitizer не заменяет проверку quarantine/PII. Dependencies не устанавливались; live services/модели не вызывались; tracked checkout чист.

[Исходная карточка](../05_Источники/ING-02_исходные_строки.txt) · [18 pinned sources](../05_Источники/C100_источники.json) · [остатки](../01_Реестры/C100_остатки.json) · [границы](../04_Проверки/C100_ING02/Чтение_и_границы.md).

**100/127 — промежуточный аудит. Далее ING-03 в исходном порядке; фаза заданий исполнителю ещё не начата.**
