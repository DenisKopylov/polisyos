# RUN-02 — Доставка результата через процессную границу

## 1. Паспорт и результат

**LANE-06 · CP2 · основание 20d9009be21097bfbdc38a546a15cc60213b8ace · статус: ТЗ, не выполнено.** Технический исполнитель и reviewer назначаются проектом. Исходные ID: B24. Тип: EOF diagnostic fix + native platform qualification.

Готовый большой result доставляется до join; crash, compute expiry и delivery failure имеют точную причину и не дают ложного receipt.

Основания: [аудит](../05_Основания/Аудит/02_Пакеты/RUN-02.md), [все остатки](../05_Основания/Аудит/01_Реестры/C69_остатки.json), [неизменная исходная карточка](../05_Основания/Аудит/05_Источники/RUN-02_исходные_строки.txt), исходный объединённый план §RUN-02 (исторические строки 8152–8220).

## 2. Уже работает — сохранить

- Framed nonblocking Pipe, drain-before-join и exact typed codec.
- Completion mark отдельно от конечного delivery grace, окно не продлевается кусками.
- Send/serialization/corrupt receipt fail closed.
- Only verified own non-parent process groups cleaned; closed spawn tasks и parent-issued binding.

## 3. Полнота обязательств и disposition

| Основание | Решение | Требования |
|---|---|---|
| C69-R01 | fix: EOF до elapsed deadline не compute timeout; актуальный exit status/transport reason. | REQ-RUN-02-01 |
| C69-G01 | qualify: Core-bound Linux supervisor/receipt/descendants, не только direct child. | REQ-RUN-02-02, REQ-RUN-02-03 |
| C69-G02 | qualify: Native macOS spawn/allowlist/context, Linux spawn не замена. | REQ-RUN-02-03 |

### Исходные обязанности, не только новые R

- B24 → REQ-RUN-02-01…-03: already fixed transport сохранить; early EOF уточнить; real supervisor/descendants и native Darwin квалифицировать отдельно.

## 4. Нормативный контракт

### REQ-RUN-02-01
Sync/async drain при EOF до completion и до compute deadline выдаёт crash/transport diagnostic с актуальным известным exitcode либо unknown exit status; не compute-timeout только из-за EOF. При одном повторном наблюдении приоритет: timely completion mark → delivery failure; иначе подтверждённо exited worker → _WorkerProcessExited, даже если monotonic deadline к этому наблюдению уже истёк; иначе alive/unconfirmed exit и elapsed budget → compute-timeout; иначе early EOF → transport diagnostic. Этот порядок сохраняет текущий post-loop exit precedence и не утверждает неизвестное время смерти. Ни одна ветка не ждёт остаток compute budget ради EOF.

Источник: B24; аудит: C69-R01; проверки: TEST-RUN-02-01.

### REQ-RUN-02-02
Actual Core-bound wrapper доставляет small/1MiB typed outcomes до join в sync/async. Completion receipt, digest/run/attempt/owner binding проверяются до принятия; partial/corrupt/send failure не success. Delivery window фиксирован actual completion mark.

Источник: B24; аудит: C69-G01; проверки: TEST-RUN-02-02.

### REQ-RUN-02-03
Native Linux supervisor очищает подтверждённо принадлежащих descendants или явно сообщает cleanup incomplete; не сигналит parent/foreign group. Native macOS supported canonical nodes используют closed spawn task/context и exact attempt binding, unsupported node/context явно отказывается без silent fallback. Linux numerical-timeout qualification отдельно называет actual start method и состояние parent после JAX/BLAS/thread-pool initialization. Cold callable не доказывает warm numerical support: выбранный supported route должен завершить meaningful bounded calculation, либо именно эта topology явно остаётся unsupported/NOT_RUN без broad numerical PASS. Это не утверждение уже воспроизведённого deadlock и не блокер независимого EOF repair.

Источник: B24; аудит: C69-G01, C69-G02; проверки: TEST-RUN-02-03.

## 5. Техническое решение и producer → consumer

В обоих _drain_result_* вынести EOF classification в общий private helper: перечитать completion mark, monotonic deadline и process exitcode/is_alive; timely mark → existing delivery failure; иначе уже exited → existing _WorkerProcessExited(exitcode), в том числе при одновременно истёкшем deadline; иначе elapsed deadline → compute timeout; иначе отдельный existing transport-error boundary (или минимальный private EOF error, переведённый текущим wrapper в typed diagnostic). Нельзя считать unknown exitcode числом0. Не blocking join внутри helper; actual cleanup делает нынешний wrapper.

Node worker→framed pipe→drain→parent-issued receipt validation→typed outcome→durable consumer. Положительный large-result путь оставить неизменным, не заменить все bytes искусственным ref без необходимости.

Отдельное qualification-решение: retry._timeout_worker_start_method явно выбирает Linux fork. [Python3.14 start methods](https://docs.python.org/3.14/library/multiprocessing.html#contexts-and-start-methods) предупреждает о многопоточном fork; [locked JAX0.8.2 source _at_fork](https://raw.githubusercontent.com/jax-ml/jax/jax-v0.8.2/jax/_src/xla_bridge.py) содержит соответствующий deadlock warning (проверено 2026-11-01). Это основание warm-parent test, не product FAIL. Не предписывать смену одной строки: reuse existing closed task/context/parent receipt boundary и сохранить Linux supervisor/subreaper/group cleanup; forkserver preload также требует проверки отсутствия numerical threads.

### Проверенные owners на срезе
- policy-engine/src/polisyos/scientist/orchestration/engine/retry.py: _WorkerResultChannel, _drain_result_sync/_async, _WorkerProcessExited, _owned_process_group_id
- policy-engine/src/polisyos/scientist/orchestration/engine/runner/serialization.py: typed timeout task/context/receipt codecs

Увеличение timeout не исправляет EOF reason. Linux fork evidence не сертифицирует Darwin; смена одного слова spawn без bindings запрещена.

## 6. Локальная приёмка — все будущие проверки NOT_RUN

### TEST-RUN-02-01
- Уровень: unit + targeted native integration.
- Setup: Controlled alive→EOF→exit23 и exit23→EOF, no mark/near-future deadline; timely mark и elapsed variants.
- Действие: Оба drain owners, затем actual wrapper error projection.
- Точный oracle: Early EOF crash/transport с23 или unknown, не timeout; no-mark+exited+elapsed даёт process-exited, no-mark+alive+elapsed — compute-timeout, timely-mark+exited+elapsed — delivery failure. Полная таблица одинакова sync/async; no success и немедленный bounded отказ.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-RUN-02-02
- Уровень: native process integration.
- Setup: Real Core CAS/context/current attempt, small64B и1MiB outcomes, actual worker/supervisor/codec.
- Действие: Sync/async execute→drain→join→receipt accept→fresh read; partial frame/malformed/wrong nonce negatives.
- Точный oracle: Exact all bytes/type/run/selector retained; no join deadlock; mismatch/corrupt no accepted receipt; finite delivery grace not reset.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-RUN-02-03
- Уровень: native Linux + native macOS separately.
- Setup: Owned process subtree only; Linux descendants fixture and supported Darwin canonical node/context. Отдельный Linux Python3.14/locked-JAX profile: parent выполняет реальную маленькую JAX operation до timeout invocation, с recorded start method/backend/env; внешний bounded watchdog не зависит от child.
- Действие: Timeout/worker exit/cancel; new request after cleanup; unsupported context negative. На выбранном warm-parent route выполнить actual bounded child numerical calculation→typed delivery; отдельно stalled-child control и cleanup. При unsafe/unsupported topology выбрать и обосновать existing closed spawn route либо controlled clean forkserver/profile limitation, не менять global start method молча.
- Точный oracle: Own subtree reaped or explicit incomplete; foreign/parent never signalled. Darwin exact allowed bindings succeed; unsupported rejects before execution. Warm Linux поддержка принимается только при actual expected numerical value, typed run/attempt binding и deadline/cleanup; cold-only success её не закрывает. Если warm topology незаквалифицирована, ограничение named и numerical claim не повышен. Each platform/profile labelled independently; unavailable platform NOT_RUN. Startup/RSS costs — measured characterization, не выдуманный SLO.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

Повторно использовать/расширить реальные места, а не создавать 127 harness: `policy-engine/tests/unit/scientist/orchestration/engine/test_retry.py`; `policy-engine/tests/unit/scientist/orchestration/engine/runner/test_timeout_transport_attempt_binding.py`. До выбора selector прочитать полный test/fixture. Это проверенные пути, не утверждение о наличии всех предложенных assertions.

Допустимые doubles: controlled liveness/channel interleaving для EOF unit; own descendant fixture. Запрещено: fake parent capability/receipt for native claim, Linux spawn branded macOS, arbitrary process-group kill.

## 7. Общая интеграция и порядок

One native process wave with RUN-01 deadline, WIRE-01 codec and DUR-02 current authority. Physical cleanup and durable publication have distinct oracle.

Точные общие сценарии: E02-I06-C из [контракта интеграции](../03_Интеграция/LANE-06.md); одно свидетельство переиспользуется по неизменным input/backend bindings. Зависимости: RUN-01; исходный DAG — ориентир, работающий контракт может удовлетворять ребру без нового ремонта. Общие файлы из §5 интегрировать последовательно с затронутыми owners; lane не новый runtime-реестр и не требование полного CI после каждого пакета.

## 8. Совместимость, история, rollback

Private diagnostic refinement may change error reason but never turn failure into success. Preserve public typed envelope/error mapping; unknown external outcome remains non-replayable until reconciled. Historical logs not relabelled.

## 9. Free-grow и design direction

- policy-design-execution-topology.md §6: observed receipt != deterministic execution claim.
- design_direction.md §4.7: completion/delivery/admission отдельны; полезный timely result не теряется из-за join ordering.

Архитектурные источники: [policyos-identity-and-custody-boundary.md §1, §3–6](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md); [policy-design-custody-time-model.md §2–5](../05_Основания/Архитектура/policy-design-custody-time-model.md). История и текущая пригодность раздельны; физическая раскладка не догма.

Полные исторические probes/commands/logs остаются в отдельно доставленном phase1 ZIP; ссылки внутри копий аудита на `04_Проверки` относятся к нему, не к новым исполненным проверкам этого комплекта.

## 10. Нерешённые решения и передача

Новых блокирующих продуктовых решений не требуется. Реальную доступность supported runtime установить до native проверки; недоступность оформлять NOT_RUN, не PASS.

Предъявить patch/base SHA (либо обоснованный no-code результат), актуальную карту callers, REQ→TEST→evidence, фактические команды/логи, различающий контроль и сохранённые инварианты. Поддержанный native профиль: P-CORE (Python >=3.14,<3.15 и project lock); для процессов P-PROCESS, для поставки P-PACKAGING. Не устанавливать зависимости без отдельного разрешения. Fixture/source-only, исторические PASS и отсутствие ошибки при импорте не закрывают свежий producer→persistence→fresh-reader. Успешная сериализация/конверсия/подпись не доказывает научной истины или полномочия policy result. Никакое требование/тест этой карточки ещё не исполнены.

