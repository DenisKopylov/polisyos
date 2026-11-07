# DUR-01 — атомарный бюджетный snapshot и граница durable acknowledgment
## C71 · 1 ноября 2026 года

**Порядок:** 71/127, LANE-06. **Исходный ID:** B37. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Свежая проверка после внешнего сохранения C70.

## Решение

**Исходная гонка blank=no-limits устранена в проверенных локальных случаях.** Reader и writer используют стабильный lockfile; target не обнуляется in-place; complete temporary payload проходит fsync, replace и directory sync. Existing empty/sparse/corrupt snapshot больше не становится новым безлимитным BudgetState.

**Найден C71-R01:** после failed directory fsync уже видимые bytes могут дать преждевременный `committed`/`durability=ledger` acknowledgment. Повторный sync отсутствует на spend/producer replay; actual traced acknowledgment reader повышает visible readback до durable метки. Это не воспроизведённая потеря данных при питании.

**8 bounded MATCH; 19 unchanged existing test bodies / 62 cases исполнены с настоящими product modules и child imports.** Native pytest и supported toolchain не выполнены. Полного закрытия нет.

## 1. Матрица B37

| Требование | Свежий результат | Ограничение |
|---|---|---|
| Reader не видит промежуточную пустоту | P03/P06: real concurrency и pause перед replace; reader ждёт stable lock, затем видит полный новый snapshot | Local POSIX filesystem, не multi-host qualification |
| Existing corruption не отменяет лимиты | P01: empty/truncated/sparse/typed-invalid records отвергаются без изменения bytes | Восстановление из достоверного backup не исполнялось |
| Crash между стадиями публикации | P02: десять cold/warm file-sync/replace/dir-sync/own-SIGKILL controls дают old/new или явное отсутствие | Process crash не равен power loss |
| Exact operation retry не дублирует charge | P04/P05: exact receipt переживает restart и eviction bounded journal; concurrent same event списан однажды | Это contract settle-event, не idempotency всякого record_spend |
| Durable acknowledgment честен | P07/P08 подтверждают R01 при persistent directory-sync failure | Реальная потеря bytes/денег не заявлена |

## 2. Сохранён существующий владелец, а не создана вторая бюджетная система

`FileBudgetLedger` остаётся canonical owner с revisions, writer identity, recent mutations, receipts и producer records. `BudgetMiddleware` reload перед `pre_check`/read не берёт stale memory вместо current ledger. `BudgetState.remaining` сохраняет смысл explicit unlimited при отсутствии limit; такое состояние разрешено только через явный bootstrap, не из повреждённого файла. [S01:704–779](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/budget_ledger.py#L704-L779) [S02:44–67](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/budget.py#L44-L67) [S03:44–88](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/budget_middleware.py#L44-L88)

Reader берёт shared lock, writer exclusive — на `.lock`, не на заменяемом inode snapshot. `_persist_snapshot` сначала проверяет полный wire тем же strict decoder, пишет temporary file в том же каталоге, обрабатывает short writes, fsync файла, replace и fsync каталога. Старого `ftruncate(target, 0)` нет. [S01:1427–1441](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/budget_ledger.py#L1427-L1441) [S01:1505–1543](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/budget_ledger.py#L1505-L1543)

Соседний CAS atomic helper прочитан, но не приписан ledger как исполненный путь. Его explicit directory-durability contracts полезны при дальнейшей консолидации; новый SQLite/service для этой карточки не нужен. [S04:13–49](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/core/artifacts/_atomic_write.py#L13-L49)

## 3. Полный wire отделён от конструктора с defaults

`_decode_snapshot` не принимает пустой existing файл, неизвестную schema, другой canonical contract/coordination mode, sparse writer record и invalid accounting values. Required-field проверка выполняется до constructor defaults; nullable/legacy fields учитывают version. Receipt identities/revisions, aggregate costs, compute reservations и reuse origin graph сверяются с snapshot. [S01:428–600](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/budget_ledger.py#L428-L600)

**P01:** исполнены existing cold/bootstrap, explicit unlimited, malformed JSON, schema-derived required-field deletion и 13 typed-invalid variants. Через реальные child imports проверены ledger methods и live middleware; все relevant refusals сохранили повреждённые bytes. Разрешённые nullable omissions читаются. Ни missing ledger, ни sparse existing не превращены в случайный unlimited бюджет.

Это полезный repair, но не автоматическое восстановление storage corruption. При недостоверном existing snapshot система отказывает; operational restore остаётся G01. Нельзя объявлять такой отказ достаточным восстановлением работоспособности, но нельзя и «чинить» его обнулением расходов.

## 4. Реальные локальные crash/concurrency controls

**P02:** существующий test исполнил десять cold/warm комбинаций: file fsync refusal, failure до replace, directory fsync failure после replace, собственный child SIGKILL до/после replace. После reopening наблюдается полный old/new snapshot; при неудавшейся первой публикации target отсутствует, а не пуст. Cold middleware снова использует явно заданный exhausted limit, не unlimited default. [S05:313–358](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scientist/orchestration/engine/test_budget_ledger_process.py#L313-L358)

**P03:** четыре actual middleware writer процесса по 25 единичных расходов плюс reader. После завершения spend и provider_spend равны 100, exhausted cap отвергнут. **P06:** controlled pause writer перед replace; raw target остаётся полным старым, отдельный ledger reader блокируется на том же lockfile. После release читает spend 3 вместо 2; lock inode неизменён. Все собственные потоки завершились.

Эти результаты относятся к реальному локальному POSIX file I/O. Они не измеряют частоту аварий, не моделируют hardware power loss и не подтверждают semantics произвольного NFS/shared filesystem. Canonical string `multi_host` сам по себе такой гарантии не даёт.

## 5. Event identity сохраняет ровно один charge

`settle_spend` сохраняет receipt отдельно от bounded recent journal. Exact retry сравнивает event ID, payload digest, key, amount и provider; конфликт отказывает. Producer settlement дополнительно сохраняет intent/run binding/attempt attribution и unknown amount, не переименовывает их по текущему ambient context. [S01:1053–1143](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/budget_ledger.py#L1053-L1143) [S01:1213–1385](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/budget_ledger.py#L1213-L1385) [S03:216–285](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/budget_middleware.py#L216-L285)

**P04:** actual event пережил restart и eviction journal, повторное чтение/settlement не меняет bytes и не списывает ещё раз. Conflicting amount/key/provider/digest, missing receipt fields и inconsistent wire отвергнуты. **P05:** четыре actual concurrent middleware producers одного event возвращают один receipt/revision; aggregate cost равен 2, не 8. Memory-only middleware не может выдать durable ack или выдумать owner identity.

Legacy `record_spend` остаётся намеренно additive операцией без event ID. Поэтому доказательство exact-event idempotency не распространяется на произвольное повторение legacy mutation. Сохранить этот контрактный разрез, а не обещать универсальную exactly-once семантику.

## 6. C71-R01: readable не равен durable после failed directory sync

Первый publication path корректно сообщает `BudgetLedgerSettlementOutcomeUnknownError`, если directory fsync не состоялся. Но exact spend replay возвращает существующий receipt сразу; producer replay аналогично возвращает existing record. Resolve читает bytes без повторного durability confirmation. Для compute reservation в этом же owner уже есть более строгий `_confirm_compute_durability`: sync каталога и exact readback под lock. [S01:1032–1051](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/budget_ledger.py#L1032-L1051) [S01:1084–1099](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/budget_ledger.py#L1084-L1099) [S01:1269–1306](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/budget_ledger.py#L1269-L1306) [S01:1387–1424](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/budget_ledger.py#L1387-L1424)

**P07, постоянный fault:** после первой операции directory-sync отказ остаётся включённым. Spend и producer сначала дают unknown, затем exact replay принимается без новой попытки sync: счётчик остаётся 1. Compute positive comparison снова пытается sync, счётчик 2, и остаётся unknown. Costs не дублируются; видимые bytes полны. Это отличается от existing lost-ack tests, которые убирают injected fault в reopened process. [S06:151–186](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scientist/orchestration/engine/test_budget_ledger_settlement.py#L151-L186)

Downstream важен: actual `TracedLLMClient._persist_producer_event` при exception пытается resolve и, если identity/payload совпали, ставит `committed` и `durability="ledger"`. Exact identity полезна, но не подтверждает недостающий flush. [S07:1043–1160](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/core/llm/traced_client.py#L1043-L1160)

**P08:** два complete unchanged acknowledgment methods над настоящим middleware/ledger, actual typed event/ack и fixture client state. После единственного failed directory fsync fallback readback вернул `ack.status=committed`, `ack.durability=ledger`, receipt того же event. Provider calls = 0. Здесь подтверждён преждевременный уровень гарантии, а не live billing или реальный power-loss ущерб.

**Минимальное направление:** отделить visible exact receipt от confirmed durable publication, согласовать spend/producer replay/resolve с existing confirmation owner и не повышать unknown только из readable bytes. При восстановившемся sync тот же event должен подтвердиться без повторного charge; при persistent fault сохранять unknown. Не нужен новый journal или другой budget store.

## 7. Что ещё не квалифицировано

**G01:** supported filesystem crash/durability, lifecycle новых директорий, реальное shared multi-host locking и operational restoration corrupted snapshot. Новый storage service не назначается; сначала использовать существующие owners и явно назвать поддерживаемую область.

**G02:** supported Python 3.14/Pydantic native pytest и единый authorized producer → intent → settlement → durable ack → current budget consumer. Current real file pipeline уже работает в bounded cases; отсутствующий pytest не означает отсутствующую реализацию. Но synthetic local charge не является внешним billing authority, а событие LLM не доказывает научную состоятельность ответа. Typed unknown/reuse различия должны сохраниться. [S07:617–673](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/core/llm/traced_client.py#L617-L673) [S08:37–122](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/core/llm/settlement.py#L37-L122)

Вместо дублирования тяжёлых сценариев общий LANE-06 integration должен соединить known/unknown cost, RUN retry/cancellation, current attempt identity и durable consumer. Phase 2 ещё не начата: здесь только оставшиеся требования аудита.

## 8. Исполнение и артефакты

Whole native ledger/middleware import успешен без package shells. Final main probe: exit 0, 7 MATCH; отдельный ack probe: exit 0, P08 MATCH. **19 unchanged bodies / 62 cases**, но **native pytest bodies = 0**: marks/raises helpers предоставлены harness. 35 actual import identities сверены с Git; full human review всех imports не заявлен.

В fixture directories намеренно сохранены corrupted JSON и orphan temporary files после собственных SIGKILL. Это negative evidence, не нарушение ZIP integrity; не использовать их как рабочие бюджеты. Все child процессы принадлежат probe, cleanup завершён. Python 3.12/Pydantic 2.13 вне supported baseline. Checkout/dependencies не менялись, external services не вызывались.

[Диагностика](../04_Проверки/C71_DUR01/bounded_diagnostics.json) · [Команды](../04_Проверки/C71_DUR01/commands.json) · [Границы](../04_Проверки/C71_DUR01/native_verification.json) · [Источники](../05_Источники/C71_источники.json) · [Остатки](../01_Реестры/C71_остатки.json).

**71/127 пакетов рассмотрены ограниченно. Следующий — DUR-02. Полного закрытия нет; фаза 2 не начата.**
