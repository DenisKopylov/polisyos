# RUN-01 — единый deadline, перенос контекста и честная граница остановки
## C68 · 1 ноября 2026 года

**Порядок:** 68/127, LANE-06. **Исходные IDs:** B14, B40, B69, B95, LA-057; **защита:** LK36. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Свежий аудит после внешнего сохранения C67.

## Решение

**11 bounded MATCH, 12 unchanged existing Common test bodies исполнены изолированно.** Основные изменения присутствуют: unconfigured retry owner явно выбирает unbounded bridge; единый deadline передаётся вниз; thread fallback копирует contextvars; насыщенный shared pool явно отказывает re-entrancy, а не ждёт собственной недоступной ёмкости. LA-057 выполнена в текущем package owner без удаления работающего bridge.

**C68-R01 — низкий остаточный дефект cleanup:** отказ до admission оставляет переданную fresh coroutine незакрытой. Это не активный runaway compute и не обход полномочий. Native workflow/CAS/claim integration и supported toolchain qualification остаются открытыми; полного закрытия нет.

## 1. Матрица исходных обязательств

| ID | Подтверждённое поведение | Остаток |
|---|---|---|
| B14 | P06: thread может продолжать работу, но возвращается unknown outcome и late guarded write отвергается. P07: blocking coroutine не hard-stopped, поздний результат отвергнут | G01 native write owners; R01 pre-admission cleanup |
| B40 | P03: direct sync, sync-via-async и actual async с отсутствующим deadline не режутся скрытым helper default. P05: earlier budget уменьшается и ограничивает backoff | G01 полный workflow budget/publication |
| B69 | P01: capacity saturation и callback occupancy дают explicit re-entrancy refusal без inner compute | R01 fresh coroutine; G01 реальный ingestion path |
| B95 | P04: A, затем B на одном worker; следующий neutral submit видит None | G01 actual authority/context façade и OS route |
| LA-057 | P01/P02: четыре function-local T и get_type_hints; нет module T/TypeVar; finite consumer census | G02 supported package/typecheck/external dynamic consumers |

Исходный `common/async_tools.py` перемещён в `common/async_tools/__init__.py`. Это реальный owner, не отсутствие реализации по старому имени. В нём сохранены executor, context propagation, cancellation и shutdown. [S01:1–24](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/common/async_tools/__init__.py#L1-L24) [S07:1–55](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/common/__init__.py#L1-L55)

## 2. Deadline принадлежит invocation, а не случайному helper

Retry resolves `min(configured timeout, incoming deadline)` один раз; `_remaining_deadline` не продлевает срок. Те же deadline передаются timed helpers, проверяются перед попыткой, backoff и публикацией. Async workflow caller передаёт existing cache_deadline в retry, затем снова проверяет workflow admission. [S02:2091–2127](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/retry.py#L2091-L2127) [S02:2130–2159](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/retry.py#L2130-L2159) [S02:3927–4010](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/retry.py#L3927-L4010) [S06:2111–2127](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py#L2111-L2127)

При отсутствии deadline sync-node в async wrapper вызывает `run_blocking_async(..., unbounded=True)`. Это явный owner contract: helper default по-прежнему действует для других вызовов и не был глобально удалён. Несовместимое сочетание unbounded и float timeout отвергается до admission. [S02:3997–4010](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/retry.py#L3997-L4010) [S01:795–824](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/common/async_tools/__init__.py#L795-L824)

**P03:** с намеренно уменьшенным helper default 0,005 с producer длительностью 0,025 с завершился во всех трёх формах: direct sync, sync-via-async, actual async. Во всех формах правильный ContextVar. Исполнены полные unchanged retry wrapper definitions; context façade и accounting — fixtures, liveness config отсутствует. Это не измерение production latency.

**P05:** earlier deadline выбран вместо более длинного собственного timeout; после ожидания остаток уменьшился. Уже истёкший срок даёт `not_admitted`, backoff не получает новый бюджет и заканчивается `retry_not_admitted`. Реальный workflow/retry/cost lifecycle пока G01, а не подтверждён только этим малым helper опытом.

## 3. Контекст не теряется, но не создаёт новые права

`_submit_thread_attempt` делает deep copy state, строит gated context, захватывает `copy_context()` и подаёт именно `context.run`. **P04:** принудительно выбран permitted non-Darwin thread fallback, один физический worker: запрос A видит A, B видит B, neutral worker invocation видит None. Никакой tenant/actor не синтезирован из слов агента. [S02:2397–2414](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/retry.py#L2397-L2414)

Actual `_AttemptAuthority` проверяет deadline и revoke под общим lock; persistence получает typed `attempt_write_revoked`, best-effort writes после revoke — no-op. Native context owner оборачивает store/run/audit/claim и запрещает rebinding façades; он прочитан, но в probe заменён явно обозначенным малым context fixture. Поэтому наличие actual authority algorithm не выдано за доказательство всего native CAS security contract. [S02:609–676](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/retry.py#L609-L676) [S02:1509–1586](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/retry.py#L1509-L1586)

## 4. Таймаут ожидания не выдан за убийство вычислителя

**P06:** actual timed thread helper запускает управляемый producer. После 0,03 с он ещё ждёт event; caller получает `external_outcome_unknown`, а не ложное «остановлен». Затем harness отпускает producer: worker заканчивает, initial state остаётся пустым, попытка поздней fixture persistence через actual authority даёт `attempt_write_revoked`. Запущена ровно одна попытка. Это не проверка реального store/claim façade и не sandbox для произвольных внешних side effects. [S02:2417–2476](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/retry.py#L2417-L2476)

**P07:** coroutine синхронно блокирует event loop примерно 0,03 с при запросе 0,005 с. Она физически заканчивает позже, и actual timeout helper отвергает результат как `completed_after_deadline`. Этот результат защищает LK36: cooperative await timeout не гарантирует hard real-time preemption. [S02:3725–3767](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/retry.py#L3725-L3767)

**P08:** для cooperative coroutine fresh-loop timeout выполняет finally родителя и отменяет/дожидается дочерней task. Оба finally наблюдались. Helper cleanup полезен и не должен удаляться вместе с типовым residue. [S01:664–693](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/common/async_tools/__init__.py#L664-L693)

## 5. Saturation исправлена явным отказом; маленький cleanup остаток есть

Actual shared executor учитывает physical slots и reservations до завершения wrapper/callback. Nested submit при полной ёмкости даёт `SharedExecutorReentrancyError`. **P01:** unchanged existing tests насыщают четыре workers управляемыми barriers, отдельно внутри body и done callbacks; ни одного inner callable не исполнено, все попытки явно отказаны. Capacity не повышалась «для ремонта». [S01:379–400](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/common/async_tools/__init__.py#L379-L400) [S03:904–976](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/common/test_async_tools.py#L904-L976)

**C68-R01 / P09:** running event loop, canonical pool capacity 1, queue 0, единственный worker удерживается event. `run_coro_sync(asyncio.sleep(...))` получает `SharedExecutorBackpressureError` на submit. Переданная fresh coroutine после отказа имеет `CORO_CREATED` и attached frame: body не начиналось, но helper её не закрыл. Harness затем закрыл её явно и освободил worker. В исходнике submit находится до `try`, а fresh-loop cleanup ещё не начал владеть coroutine. [S01:696–720](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/common/async_tools/__init__.py#L696-L720)

Последствие ограничено диагностикой и ресурсным владением: fresh inline coroutine может дать unawaited warning, frame удерживается до освобождения ссылок. Это **не** доказательство выполняющейся поздней работы. Экономное направление — cleanup только принадлежащей bridge, ещё не принятой fresh coroutine на отказе admission; сохранить guard и не закрывать чужие уже запущенные Task/Future. Не повышать timeout/pool и не превращать отказ в success.

В data-plane остаются sync entry → async backend и inner blocking/snapshot boundaries. Они прочитаны, но наличие импортов не доказывает обязательный deadlock в production. Текущий guard уже обеспечивает explicit refusal; достижимость и удобство real nesting требуют общего сценария, а не нового пула по умолчанию. [S05:151–197](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/fabric/data_plane/orchestrator.py#L151-L197) [S05:558–570](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/fabric/data_plane/orchestrator.py#L558-L570) [S05:667–680](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/fabric/data_plane/orchestrator.py#L667-L680)

## 6. LA-057 и конечный consumer census

На whole imported module все четыре исходных helpers имеют разные собственные `__type_params__[0]`; actual `get_type_hints` с правильными namespaces разрешает return в соответствующий параметр. Module attributes `T` и `TypeVar` отсутствуют; direct/star/reflection imports сохраняют нужные helpers. Ничего не переписано или транспилировано ради Python 3.12. [S03:25–48](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/common/test_async_tools.py#L25-L48)

Token-level scan **8231 Git-tracked Python files**, включая multiline imports, закончился без ошибок: нет literal direct imports прежних T/TypeVar или star import из async_tools. Единственные known-alias reflection candidates — две negative hasattr assertions самого теста. Это конечный static census, **не** доказательство отсутствия произвольного computed alias или внешних consumers. Отдельный малый процесс импортировал настоящий Common и получил 1 до loop, 2 внутри loop; stderr пуст. P10 и consumer_scan.json сохраняют точные результаты.

Исторический порядок отдельных cleanup/behavior commits по одному текущему HEAD не аттестован. Supported Python 3.14 typecheck/packaging и внешний контракт — G02; возвращать incidental T без найденного потребителя не предлагается.

## 7. Исполнение и остатки

- Bounded run: exit 0, **11 MATCH**, 12 existing Common bodies исполнены изолированно. Full Common module настоящий, не AST algorithm stub.
- Отдельный Common import: exit 0. Native pytest: exit 1, pytest отсутствует. Full retry import: exit 1 на `retry.py:258`, Python 3.14 syntax в среде 3.12; источник не переписывался.
- Context façade, cost/reporting, fixed producer и forced thread route — явные seams. Native CAS/audit/claim, tenant admission, full workflow и OS process routes не исполнены. macOS/process матрица относится к RUN-02.
- Все workers освобождены и joined, тестовая fresh coroutine закрыта после наблюдения. 15 реально импортированных repository module identities и exact extracted definitions сверены с Git; полный human review всех imports не заявлен.

**G01:** общий LANE-06 native deadline/cancellation/retry/write-admission сценарий. **G02:** supported typecheck/package/consumer qualification LA-057. Сохранить existing timeout authority, context copying, finite queue, explicit re-entrancy и рабочий bridge; расширять владельцев, не строить вторую систему исполнения.

[Диагностика](../04_Проверки/C68_RUN01/bounded_diagnostics.json) · [Команды](../04_Проверки/C68_RUN01/commands.json) · [Consumer scan](../04_Проверки/C68_RUN01/consumer_scan.json) · [Границы](../04_Проверки/C68_RUN01/native_verification.json) · [Источники](../05_Источники/C68_источники.json) · [Остатки](../01_Реестры/C68_остатки.json).

**68/127 пакетов рассмотрены ограниченно. Следующий — RUN-02. Полного закрытия нет; фаза 2 не начата.**
