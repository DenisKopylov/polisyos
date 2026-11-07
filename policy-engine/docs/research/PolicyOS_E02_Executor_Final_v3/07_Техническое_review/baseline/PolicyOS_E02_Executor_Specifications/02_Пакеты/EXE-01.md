# EXE-01 — Допуск cache read, неблокирующий I/O и fail-fast

## 1. Паспорт и результат

**LANE-06 · CP2 · основание 20d9009be21097bfbdc38a546a15cc60213b8ace · статус: ТЗ, не выполнено.** Технический исполнитель и reviewer назначаются проектом. Исходные ID: B51, B52, B55. Тип: исправление callback bridge + native qualification.

Разрешённый cache hit остаётся доступен без нового compute; медленный I/O и поздняя доставка результата не останавливают event loop.

Основания: [аудит](../05_Основания/Аудит/02_Пакеты/EXE-01.md), [все остатки](../05_Основания/Аудит/01_Реестры/C63_остатки.json), [неизменная исходная карточка](../05_Основания/Аудит/05_Источники/EXE-01_исходные_строки.txt), исходный объединённый план §EXE-01 (исторические строки 7480–7596).

## 2. Уже работает — сохранить

- Action-specific read/run budgets и hard workflow deadline до read.
- Bounded Common executor, finite FIFO queue, physical slot ownership до фактического завершения.
- Current-state journal replay и fence отменённого cache index; immutable bytes могут существовать без current admission.
- Post-acquire fail-fast, release в finally, continue policy. LK/S специальных нет.

## 3. Полнота обязательств и disposition

| Основание | Решение | Требования |
|---|---|---|
| C63-R01 | fix: Разделить bounded user callback и внутренний nonblocking asyncio delivery. | REQ-EXE-01-01 |
| C63-G01 | qualify: Read rights/current applicability/CAS/fresh recovery через actual owners. | REQ-EXE-01-02, REQ-EXE-01-03, REQ-EXE-01-04 |
| C63-G02 | qualify: Измерить latency/capacity; completed result preservation совместно с RES. | REQ-EXE-01-01, REQ-EXE-01-03, REQ-EXE-01-04 |

### Исходные обязанности, не только новые R

- B51 → REQ-EXE-01-02: read permitted/compute denied, no double charge, права и deadline не обходятся.
- B52 → REQ-EXE-01-01/-03: delivery без синхронного ожидания event loop, real persistence и measured latency.
- B55 → REQ-EXE-01-04: waiting versus running cancellation, сохранённые independent results.

## 4. Нормативный контракт

### REQ-EXE-01-01
run_blocking_async при completed-before-wrap и saturated owner не должен ждать capacity или future.result синхронно на event-loop thread. Delivery существующего timely receipt выполняется без повторного callable; arbitrary user callbacks остаются bounded и reentrancy guards сохраняются.

Источник: B52; аудит: C63-R01, C63-G02; проверки: TEST-EXE-01-01.

### REQ-EXE-01-02
При run_budget=0/read_budget>0 valid admitted hit возвращается без producer и нового compute charge. Read denial/expired hard deadline предотвращают cache I/O; miss при run_budget=0 не запускает producer. Corrupt/cross-scope hit не становится success.

Источник: B51; аудит: C63-G01; проверки: TEST-EXE-01-02.

### REQ-EXE-01-03
Cache get/put/recovery остаются off-loop с effective owner deadline. После timeout/cancel late write не восстанавливает current index; полностью допустимый published artifact читается fresh reader. Immutable bytes и acknowledged current entry различаются; provider thread-affinity соблюдена.

Источник: B52; аудит: C63-G01, C63-G02; проверки: TEST-EXE-01-03.

### REQ-EXE-01-04
При fail_fast waiting node перепроверяет сигнал после semaphore acquire и не начинает substantive work; continue выполняет independent nodes. Ошибка optional metrics и cancellation освобождают slot, но running underlying job удерживает физическую capacity до завершения; already completed independent results сохраняются.

Источник: B55; аудит: C63-G01, C63-G02; проверки: TEST-EXE-01-04.

## 5. Техническое решение и producer → consumer

У _SharedFuture.add_done_callback сейчас любой callback идёт в run_callback_sync; asyncio.wrap_future регистрирует внутренний delivery callback и при already-completed future блокирует loop. Предпочтительно добавить private transport-only registration у _SharedFuture, вызывающий base Future.add_done_callback для крошечного проверенного delivery adapter; adapter только делает loop.call_soon_threadsafe и не исполняет arbitrary user callback. run_blocking_async связывает отдельный asyncio.Future через этот adapter; cancellation передаётся worker_future, completion проверяет done/cancelled и receipt. Альтернатива — отдельный неблокирующий внутренний completion signal в уже существующем receipt; выбрать меньшую поверхность после полного чтения cancellation code. Обычный add_done_callback contract не делать unbounded. Deadline должен охватывать setup/delivery с сохранением timely-completion receipt semantics.

Caller→shared invoke→receipt→nonblocking loop delivery→cache consumer; actual worker reservation и shutdown остаются у _SharedExecutor, не у waiter.

### Проверенные owners на срезе
- policy-engine/src/polisyos/common/async_tools/__init__.py: _SharedFuture.add_done_callback, _SharedExecutor.run_callback_sync, run_blocking_async
- policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py: _execute_node, _put_cache_entry, _run_parallel_tier
- policy-engine/src/polisyos/core/artifacts/async_store.py: AsyncArtifactStoreAdapter
- policy-engine/src/polisyos/scientist/orchestration/engine/idempotency.py: cache I/O/token/entry admission

Не создавать второй pool или thread per callback; не запускать произвольные callbacks прямо на loop; не убирать finite queue или физическое удержание slot ради responsiveness.

## 6. Локальная приёмка — все будущие проверки NOT_RUN

### TEST-EXE-01-01
- Уровень: unit + targeted native integration.
- Setup: Actual shared owner capacity1; first callable completed, second held barrier before wrap; event-loop heartbeat.
- Действие: Register delivery через actual bridge до освобождения second worker; затем release. Повтор cancellation/shutdown race.
- Точный oracle: Heartbeat/event marker продвигается до release; регистрация не ждёт worker. Receipt42 delivered once без повторного invoke; queue/workers bounded; timely result не объявлен ошибочным только из-за delivery delay.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-EXE-01-02
- Уровень: unit + targeted native integration.
- Setup: Real budget middleware/cache scoped store, read1/run0; denial, miss, corrupt and changed-scope variants.
- Действие: Execute actual local runner node.
- Точный oracle: Hit: read1 producer0 previous cost not charged; read denial/expired deadline get0; miss producer0 with compute reason; invalid artifact not success.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-EXE-01-03
- Уровень: native integration + measurement.
- Setup: Temporary real CAS и current index; delay/fault только вокруг реального I/O; fresh reader.
- Действие: Cancel/timeout put before and after publication; allow valid put; измерить neighbor wait p95/p99 и serialization/RAM на declared workload.
- Точный oracle: Cancelled index remains absent после worker completion/restart; valid bytes readable exact; no claim underlying thread killed/no bytes existed; measured values не SLA.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-EXE-01-04
- Уровень: unit + targeted native integration.
- Setup: Four producers, parallelism1, first failure after others waiting; separate continue and metric-error/cancel cases.
- Действие: Run tier and read persisted records/results.
- Точный oracle: Fail-fast calls=[a], statuses fail/skip/skip/skip; continue all four; semaphore restored; physical slot retained while running. Independent completed result bytes доступны, terminal failure не изменён.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

Повторно использовать/расширить реальные места, а не создавать 127 harness: `policy-engine/tests/unit/common/test_async_tools.py`; `policy-engine/tests/unit/remediation/test_exe_02.py`. До выбора selector прочитать полный test/fixture. Это проверенные пути, не утверждение о наличии всех предложенных assertions.

Допустимые doubles: barriers/slow wrapper для scheduling; small producer и optional metric fault. Запрещено: mock shared future/delivery owner, fake CAS for persistence, снятие owner access/deadline.

## 7. Общая интеграция и порядок

EXE-01 owns delivery fix; RUN-01 consumes same helper и не переписывает callback mechanism. RES-02/03 own retained outcome semantics. После local race test один actual CAS workflow witness связывает budget/read/cancel/persistence.

Точные общие сценарии: E02-I06-A, E02-I06-B, E02-I06-C из [контракта интеграции](../03_Интеграция/LANE-06.md); одно свидетельство переиспользуется по неизменным input/backend bindings. Зависимости: STA-01; RUN-01; исходный DAG — ориентир, работающий контракт может удовлетворять ребру без нового ремонта. Общие файлы из §5 интегрировать последовательно с затронутыми owners; lane не новый runtime-реестр и не требование полного CI после каждого пакета.

## 8. Совместимость, история, rollback

Public arbitrary callback semantics сохранить; private transport registration не публичное обещание unbounded callbacks. Изменение не требует CAS schema. Не возвращать obsolete full state при hit. Rollback helper допустим лишь с отключением affected async fast delivery, не потерей fences.

## 9. Free-grow и design direction

- design_direction.md §2.1, §2.6: полезное чтение полученного результата не блокируется compute exhaustion; write cancellation не выдумывает rollback.
- policy-design-execution-topology.md §3–6: artifact/control loop с реальным потреблением; один shared owner вместо нового pool на вызов.

Архитектурные источники: [policyos-identity-and-custody-boundary.md §1, §3–6](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md); [policy-design-custody-time-model.md §2–5](../05_Основания/Архитектура/policy-design-custody-time-model.md). История и текущая пригодность раздельны; физическая раскладка не догма.

Полные исторические probes/commands/logs остаются в отдельно доставленном phase1 ZIP; ссылки внутри копий аудита на `04_Проверки` относятся к нему, не к новым исполненным проверкам этого комплекта.

## 10. Нерешённые решения и передача

- DEC-EXE-01-01: выбрать transport callback adapter либо receipt signal по меньшей изменяемой поверхности после чтения полного helper. Обязательный выход одинаков: no wait before release в controlled race, bounded arbitrary callbacks, cancellation/shutdown invariants.

Предъявить patch/base SHA (либо обоснованный no-code результат), актуальную карту callers, REQ→TEST→evidence, фактические команды/логи, различающий контроль и сохранённые инварианты. Поддержанный native профиль: P-CORE (Python >=3.14,<3.15 и project lock); для процессов P-PROCESS, для поставки P-PACKAGING. Не устанавливать зависимости без отдельного разрешения. Fixture/source-only, исторические PASS и отсутствие ошибки при импорте не закрывают свежий producer→persistence→fresh-reader. Успешная сериализация/конверсия/подпись не доказывает научной истины или полномочия policy result. Никакое требование/тест этой карточки ещё не исполнены.

