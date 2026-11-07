# RUN-02 — результат читается до join, а доставка отделена от вычисления
## C69 · 1 ноября 2026 года

**Порядок:** 69/127, LANE-06. **Исходный ID:** B24. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Свежая проверка после внешнего сохранения C68.

## Решение

**7 bounded MATCH; пять unchanged existing test bodies, шесть случаев, исполнены изолированно.** Actual framed pipe, worker и typed codec доставили 64 байта и 1 MiB по sync/async drain без старого join-before-drain цикла. Partial frame ограничен отдельным delivery grace, compute timeout завершает подтверждённый принадлежащий probe direct-child process group. Success из повреждённого/неотправленного результата не получен.

**C69-R01 — low diagnostic residual:** ранний EOF до completion mark может называться compute timeout, хотя срок ещё не истёк. Полный Core-bound supervisor/descendant cleanup и native macOS spawn не исполнены; **полного закрытия нет**.

## 1. Матрица B24

| Критерий | Фактическая проверка | Граница |
|---|---|---|
| Малый и 1 MiB результаты | P01: четыре реальных Linux fork передачи через actual worker/channel/codec, затем join | Fixture process launch, не actual supervisor/receipt admission |
| Compute отдельно от delivery | P02: partial frame → delivery timeout; P03: нет completion → compute timeout и own direct-child cleanup | R01: ранний EOF diagnostic |
| Ошибка отправки не success | P05: malformed frame/send failure/serialization failure/late completion отказаны; P06: corrupted codec payload отказан | Ошибочный sender не превращён в successful receipt |
| Ownership и native platforms | Actual parent bindings/closed context source прочитан, own direct groups закрыты | G01 Core/subreaper/descendants; G02 native macOS |

Предложенного `test_run_02.py` нет; actual tests найдены в существующих retry и timeout-transport suites. Это не дефект реализации по имени файла.

## 2. Старый join-before-drain механизм действительно заменён

`_WorkerResultChannel` использует framed Pipe с nonblocking reader, а не Queue feeder. Reader накапливает куски и возвращает только полный envelope; partial frame не заставляет безусловно блокироваться. Compute completion записывается отдельно. Actual process wrappers вызывают drain **до** join/cleanup и только затем декодируют результат. [S01:165–243](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/retry.py#L165-L243) [S01:2688–2811](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/retry.py#L2688-L2811) [S01:3407–3442](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/retry.py#L3407-L3442)

**P01:** внутри настоящего Linux fork child исполнен unchanged `_node_execute_worker`, producer возвращает actual `NodeOutcome`, actual serializer создаёт bytes. Parent читает actual channel через sync/async drain, затем actual join helper и actual decoder. Для payload в 64 символа wire имеет 1102 байта; для 1 MiB — 1 049 614 байт. Во всех четырёх случаях status ok, run_id и весь payload совпали; direct children завершились с exit 0.

Наблюдаемое время приблизительно 0,20–0,45 с — только bounded fixture run, не performance claim PolicyOS. Scientific producer здесь отсутствует: это transport test, не валидность модели или политики. Full supervisor и worker receipt binding не подменены названием «native end-to-end».

## 3. Доставка имеет конечный срок; incomplete bytes не дают успеха

Delivery window отсчитывается от actual completion mark и не обновляется на каждом куске. **P02:** собственный child отметил completion, отправил length header на 1 000 000 байт и один байт payload, затем остановился на ожидании. Оба drain пути вернули `_WorkerDeliveryTimeout` примерно через установленную 1 с; parent не завис в чтении partial frame. Own child затем остановлен и joined. [S01:2544–2561](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/retry.py#L2544-L2561) [S01:2722–2738](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/retry.py#L2722-L2738) [S01:2774–2790](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/retry.py#L2774-L2790)

**P03:** другой собственный child не ставит completion mark и продолжает работать. При 0,03 с compute budget оба пути дают `_WorkerComputeTimeout`. Actual `_owned_process_group_id` принимает только handshake group, равный child PID и отличный от parent group; actual cleanup завершает этот direct child. Во всех случаях group принадлежит probe, worker больше не жив. Descendants не создавались: это не проверка Linux subreaper для escaped grandchildren. [S01:2564–2596](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/retry.py#L2564-L2596) [S01:2634–2675](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/retry.py#L2634-L2675)

**P05:** пять существующих unchanged bodies / шесть cases проверили malformed envelope, failed send, failed serialization, late/no-mark completion в sync/async и отказ объявлять cleanup полным без process group. Они исполнены с минимальным raises fixture и явно отмеченными completion/error metadata seams. **P06:** actual codec отверг truncated JSON, untyped «status ok» и invalid bytes через DeserializationError. Actual worker не заменяет failure пустым success. [S03:2040–2223](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scientist/orchestration/engine/test_retry.py#L2040-L2223) [S01:3770–3924](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/retry.py#L3770-L3924) [S02:1199–1310](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/runner/serialization.py#L1199-L1310)

## 4. C69-R01: ранний EOF иногда назван истёкшим compute deadline

В compute-phase `except EOFError` сразу поднимает `_WorkerComputeTimeout`. Отдельная `_WorkerProcessExited(exitcode)` доступна, если exit уже виден до входа в этот цикл. После timely completion тот же EOF классифицируется delivery timeout. [S01:2696–2720](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/retry.py#L2696-L2720) [S01:2751–2772](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/retry.py#L2751-L2772)

**P04:** controlled process/channel views воспроизводят все три порядка наблюдения для обоих drain owners. При последнем `is_alive=True`, no completion и EOF результат — compute timeout при почти 10 с оставшегося бюджета. При already-exited view — ProcessExited с exitcode 23. При completion mark — DeliveryTimeout. Это устойчивый bounded diagnostic mismatch, не измерение частоты реальных crash races.

**Тяжесть низкая:** все controls fail closed; ложного success, повреждения или обхода cleanup не показано. Нужна точная crash/transport причина на раннем EOF с актуальным exit status, без ожидания всего compute budget. Сохранить отказ и drain-before-join; не увеличивать grace и не превращать неизвестный результат в готовый.

## 5. Владение результатом больше, чем доставка bytes

Linux supervisor создаёт собственную session/subreaper, принимает payload от node child, пытается reap принадлежащих потомков и выдаёт cleanup-incomplete отдельно. Parent-issued binding связывает node/spec/params/state/timeout/nonce с живым Core owner. Actual receipt reader проверяет invocation/digest/owner/run и принимает staged events через parent capability; только после этого возвращается typed outcome. Эти source paths прочитаны, но **не исполнены как единая цепь** в P01. [S01:245–427](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/retry.py#L245-L427) [S01:2983–3077](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/retry.py#L2983-L3077) [S01:3144–3214](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/retry.py#L3144-L3214)

**G01:** выполнить существующий native small/1MiB regression через current Core-bound wrapper, затем descendant cleanup после timeout/worker exit и interrupted-job/receipt controls. Прочитаны existing descendant tests, но не запускались. Из P07 следует только отсутствие новых direct children нашего fixture wave; не доказан весь subsystem cleanup.

Это общий LANE-06 integration с RUN-01/RES execution boundaries, а не повод создать новый журнал доставки или повторить один тяжёлый сценарий на каждом пакете.

## 6. macOS не заменён словом spawn

Current selector оставляет Linux fork supervisor, а на Darwin выбирает spawn. Spawn task builder допускает ограниченные canonical builtin IDs, exact registered instance, bound dispatch params и закрытый context wire. Timeout context требует actual filesystem CAS/RunContext, owner/tenant/current attempt consistency; arbitrary optional ports не молча теряются. Это полезная существующая реализация, а не универсальная сериализуемость любого node. [S01:2507–2530](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/retry.py#L2507-L2530) [S01:2831–2941](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/retry.py#L2831-L2941) [S02:1732–1902](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/runner/serialization.py#L1732-L1902)

Полностью прочитаны current transport-attempt fixture, identity/revalidation test и Darwin-only native execution test. **G02:** native macOS run остаётся UNRUN. Linux умеет spawn, но запуск Linux spawn не доказал бы macOS semantics; здесь его не выдавали за такую проверку. Ray/Temporal также вне аттестации. [S04:1–312](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scientist/orchestration/engine/runner/test_timeout_transport_attempt_binding.py#L1-L312)

## 7. Честность диагностики

Attempt01 остановился на синтаксической опечатке нового harness до исполнения. Attempt02/03 показали недостающий export настоящего ArtifactID в initializer shell; child codec import отказал. В03 добавлен traceback, затем export исправлен **только в harness**. Исходники/логи этих попыток сохранены; они не записаны как product failures. Final использует actual ArtifactID и actual codec без подмены алгоритма.

Final run: exit 0, **7 MATCH**. Completion-before-deadline predicate над finite shared double — явно fixture, поскольку original helper использует Python 3.14 except syntax; body не транспилировался. Job interruption/context/spend/error metadata также fixtures. 45 импортированных repository module identities сверены с pinned Git, но полный human review всех imports не заявлен.

Full retry import blocked на258; pytest отсутствует. Native supervisor/parent custody/macOS не выполнены. Checkout чист; dependencies, repo и external services не менялись. Все собственные processes освобождены, никаких чужих process groups не сигналили.

[Диагностика](../04_Проверки/C69_RUN02/bounded_diagnostics.json) · [Команды и попытки](../04_Проверки/C69_RUN02/commands.json) · [Границы](../04_Проверки/C69_RUN02/native_verification.json) · [Источники](../05_Источники/C69_источники.json) · [Остатки](../01_Реестры/C69_остатки.json).

**69/127 пакетов рассмотрены ограниченно. Следующий — RUN-03. Полного закрытия нет; фаза 2 не начата.**
