# RUN-01 — Deadline, contextvars и безопасные sync/async-мосты

## 1. Паспорт и результат

**LANE-06 · CP2 · основание 20d9009be21097bfbdc38a546a15cc60213b8ace · статус: ТЗ, не выполнено.** Технический исполнитель и reviewer назначаются проектом. Исходные ID: B14, B40, B69, B95, LA-057. Тип: pre-admission cleanup fix + existing bridge qualification.

Один invocation deadline и настоящий request context сохраняются через допустимые bridges; неподдержанная вложенность явно отказывается без утечки fresh coroutine.

Основания: [аудит](../05_Основания/Аудит/02_Пакеты/RUN-01.md), [все остатки](../05_Основания/Аудит/01_Реестры/C68_остатки.json), [неизменная исходная карточка](../05_Основания/Аудит/05_Источники/RUN-01_исходные_строки.txt), исходный объединённый план §RUN-01 (исторические строки 7957–8151).

## 2. Уже работает — сохранить

- Single deadline/minimum remaining и explicit unbounded только от owner без deadline.
- copy_context A→B→neutral без leakage; context не создаёт прав.
- Unknown external outcome и revoked late-write authority; finite physical-capacity guards.
- LK36: working bridge/cleanup/cancellation, не hard real-time preemption. LA-057 четыре function-local generics уже сохранены.

## 3. Полнота обязательств и disposition

| Основание | Решение | Требования |
|---|---|---|
| C68-R01 | fix: Закрыть только owned fresh coroutine при доказанном pre-submit refusal. | REQ-RUN-01-01 |
| C68-G01 | qualify: Actual context/CAS/claim/deadline/retry/native nesting. | REQ-RUN-01-02 |
| C68-G02 | qualify: Supported typecheck/installed consumers, finite census не произвольные внешние plugins. | REQ-RUN-01-03 |

### Исходные обязанности, не только новые R

- B14/B40 → REQ-RUN-01-02: deadline/unknown completion/late write, не обещать убийство потока.
- B69 → REQ-RUN-01-01/-02: clean refusal и existing async ingress вместо saturated nesting.
- B95 → REQ-RUN-01-02: actual context capture и отсутствие request leakage.
- LA-057/LK36 → REQ-RUN-01-03: cleanup уже сделан, supported imports/types/package квалифицировать без повторного удаления bridge.

## 4. Нормативный контракт

### REQ-RUN-01-01
Если run_coro_sync получил fresh coroutine и shared submit отказал до admission, coroutine закрывается без запуска body и исходный typed backpressure/reentrancy propagates. Уже running/suspended Task/Future или чужая admitted работа не закрывается этим cleanup.

Источник: B14, B69; аудит: C68-R01; проверки: TEST-RUN-01-01.

### REQ-RUN-01-02
Direct sync, genuine async и permitted thread fallback используют единый invocation deadline, учитывая queue/backoff/publication. Owner без deadline не получает скрытый helper-default. A/B contexts не протекают; noncooperative timeout возвращает unknown и отзывает поздние protected writes, не утверждает hard stop. Nested unavailable capacity явно отказывает либо использует существующий async ingress без deadlock.

Источник: B14, B40, B69, B95; аудит: C68-G01; проверки: TEST-RUN-01-02.

### REQ-RUN-01-03
В supported installed Common сохраняются четыре независимых function-local generic parameters и корректный get_type_hints; incidental module T/TypeVar не возвращается без поддержанного consumer. Existing bridge functions, ContextVar, exceptions, cancellation/finally и shutdown остаются рабочими.

Источник: LA-057; аудит: C68-G02; проверки: TEST-RUN-01-03.

## 5. Техническое решение и producer → consumer

В run_coro_sync охватить именно submit вызов try/except admission errors. Если inspect.iscoroutine(coro) и inspect.getcoroutinestate(coro)==CORO_CREATED, bridge до передачи ownership вызывает close(), затем bare raise сохраняет typed error. Не закрывать Awaitable вообще по duck-typed close и не catch arbitrary post-admission runtime errors. Учесть queued cancel до worker-start тем же ownership состоянием только если явно доказан never-started transition. Existing _run_coro_in_fresh_loop остаётся владельцем принятых корутин.

Deadline/context source→retry→Common bridge→actual attempt authority→CAS/run/claim consumer. EXE-01 отдельно исправляет late callback; RUN-01 не дублирует его. Real data-plane nesting сначала вызвать через существующий async owner, saturated sync path допускает explicit unsupported refusal.

### Проверенные owners на срезе
- policy-engine/src/polisyos/common/async_tools/__init__.py: run_coro_sync, _run_coro_in_fresh_loop, _SharedExecutor
- policy-engine/src/polisyos/scientist/orchestration/engine/retry.py: _submit_thread_attempt, _AttemptAuthority, deadline helpers
- policy-engine/src/polisyos/fabric/data_plane/orchestrator.py: sync/async ingress

Не увеличивать pool/timeout и не считать Future.cancel убийством потока. Module TypeVar residue уже удалён; новый types.py не нужен.

## 6. Локальная приёмка — все будущие проверки NOT_RUN

### TEST-RUN-01-01
- Уровень: unit + targeted native integration.
- Setup: Running loop, actual pool1/queue0 occupied; fresh coroutine with observable body; separate admitted Task/Future.
- Действие: run_coro_sync→submit refusal; inspect coroutine state/warnings. Repeat nested reentrancy and already-owned controls.
- Точный oracle: Fresh CORO_CLOSED/frame=None, body calls0, original typed refusal. Running Task/Future remains owned by original loop; no forced close. Positive admitted coroutine result/finally unchanged.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-RUN-01-02
- Уровень: native owner integration.
- Setup: Actual context façade/CAS/claim, deterministic barriers; A then B same worker; short owner deadline/long helper default and no-deadline inverse.
- Действие: Execute queue→retry/backoff→publication; release noncooperative worker after timeout; actual ingestion async path.
- Точный oracle: One nonextended deadline; unknown not success/hard-stop; late current writes refused; no duplicate attempt on unknown. A/B/neutral exact context, unrelated new request proceeds.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-RUN-01-03
- Уровень: native typing/installed.
- Setup: P-CORE package and supported consumer list, direct/star/reflection imports.
- Действие: get_type_hints with proper namespaces + existing Common tests + separate before/inside-loop process.
- Точный oracle: Four distinct local T identities; no module residue; same values/errors/context/cleanup; supported imports succeed, unknown external consumers explicitly scoped.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

Повторно использовать/расширить реальные места, а не создавать 127 harness: `policy-engine/tests/unit/common/test_async_tools.py`; `policy-engine/tests/unit/scientist/orchestration/engine/test_retry.py`. До выбора selector прочитать полный test/fixture. Это проверенные пути, не утверждение о наличии всех предложенных assertions.

Допустимые doubles: controlled producer barriers/clock and finite saturation setup. Запрещено: fake owner write façade for native acceptance, arbitrary tenant/actor injection, transpiled unsupported runtime.

## 7. Общая интеграция и порядок

RUN-01 owns helper deadline/context/cleanup; RUN-02 native process delivery, RUN-03 cost/baseline. One E02-I06-C wave uses real bindings; Common file conflict coordinate EXE-01.

Точные общие сценарии: E02-I06-C из [контракта интеграции](../03_Интеграция/LANE-06.md); одно свидетельство переиспользуется по неизменным input/backend bindings. Зависимости: нет обязательного нового предшественника; исходный DAG — ориентир, работающий контракт может удовлетворять ребру без нового ремонта. Общие файлы из §5 интегрировать последовательно с затронутыми owners; lane не новый runtime-реестр и не требование полного CI после каждого пакета.

## 8. Совместимость, история, rollback

Current package path replaces historical async_tools.py; public helper imports unchanged. Cleanup changes only never-admitted owned coroutine. External dynamic consumer census bounded by supported package; history not rewritten. Rollback may preserve explicit refusal, never re-enable late writes.

## 9. Free-grow и design direction

- policy-design-execution-topology.md §3–6: actual execution outcome и continuation раздельны.
- design_direction.md §4.4/§4.7; LK36: cancellation semantics scoped, not hard real-time or authority by context copy.

Архитектурные источники: [policyos-identity-and-custody-boundary.md §1, §3–6](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md); [policy-design-custody-time-model.md §2–5](../05_Основания/Архитектура/policy-design-custody-time-model.md). История и текущая пригодность раздельны; физическая раскладка не догма.

Полные исторические probes/commands/logs остаются в отдельно доставленном phase1 ZIP; ссылки внутри копий аудита на `04_Проверки` относятся к нему, не к новым исполненным проверкам этого комплекта.

## 10. Нерешённые решения и передача

Новых блокирующих продуктовых решений не требуется. Реальную доступность supported runtime установить до native проверки; недоступность оформлять NOT_RUN, не PASS.

Предъявить patch/base SHA (либо обоснованный no-code результат), актуальную карту callers, REQ→TEST→evidence, фактические команды/логи, различающий контроль и сохранённые инварианты. Поддержанный native профиль: P-CORE (Python >=3.14,<3.15 и project lock); для процессов P-PROCESS, для поставки P-PACKAGING. Не устанавливать зависимости без отдельного разрешения. Fixture/source-only, исторические PASS и отсутствие ошибки при импорте не закрывают свежий producer→persistence→fresh-reader. Успешная сериализация/конверсия/подпись не доказывает научной истины или полномочия policy result. Никакое требование/тест этой карточки ещё не исполнены.

