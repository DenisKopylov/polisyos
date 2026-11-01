# EXE-01 — read admission, async cache и fail-fast
## C63 · 1 ноября 2026 года

**Порядок:** 63/127, LANE-06. **Исходные ID:** B51, B52, B55. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Свежий проход после внешнего сохранения C62.

## Решение

Исходные repairs действуют в проверенных owners: read-budget отделён от нового compute, cache get/put вынесены через существующий Common shared executor, fail-fast повторно проверяется после semaphore acquire. Полезные completed/cancelled work различаются, slot не считается свободным только потому, что await отменён.

**8 bounded MATCH;14 unchanged Common test bodies PASS. C63-R01:** поздняя регистрация callback уже завершённого shared Future может синхронно ждать занятого owner прямо из event loop. В контролируемом interleaving actual `asyncio.wrap_future` блокируется80.4мс, соседняя coroutine получает0ticks. Это узкий scheduling residual, не доказанный bypass hard workflow deadline. Native CAS/full workflow — UNRUN.

## 1. Матрица исходных ID

| ID | Требование | Свежая проверка | Остаток |
|---|---|---|---|
| B51 | Разрешённое чтение hit отдельно от новой работы | P02 actual full execute_node + budget/journal: hit run0/read1, denied read0gets, miss run refusal | G01 custody/native chain |
| B52 | Неблокирующее bounded I/O, honest deadline/cancellation | P03 slow read56ticks; P04 hard deadline; P07 late put index fence; P01 bounded pool corpus | R01 late callback; G01 CAS; G02 cost profile |
| B55 | Повторный fail-fast после acquire и обязательный release | P05 fail_fast1из4 vs continue4из4; P06 metrics/cancellation slots | G01 native chain; G02 completed-result persistence |

Карточка7480–7596 прочитана полностью. Proposed filename не считается доказательством реализации; изучены actual existing regression owners.

## 2. B51: допуск по действию, не blanket budget bypass

`_execute_node` проверяет workflow admission, создаёт bounded state branch, вычисляет key. Перед cache.get действует budget_key=read; только после miss применяется budget_key=run. Cache hit всё ещё проходит owner applicability, current-state replay и повторный workflow guard. Состояние не заменяется чужим старым snapshot. [S01:1780–2016](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py#L1780-L2016)

**P02:** real BudgetState/Middleware, ledger=None; read remaining1,run remaining0. Actual method принимает typed cached outcome, actual journal меняет result=7 и сохраняет unrelated=current. Прежние расходы run=1 не списываются повторно. При read remaining0 cache.get не вызывается; после miss единственное чтение завершается run-budget refusal до producer. Store/registry/run reporting явные fixtures; cold producer path не подменяется успешным fake result — он вообще не достигается.

**P04:** истёкший original workflow deadline отказывает до ready-hit read; get_calls=0. Relative cache timeout берётся из меньшего node/workflow deadline, expired remainder не заменяется новым положительным budget. Это не перестановка всех access/deadline checks за hit. [S01:1659–1718](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py#L1659-L1718) [S01:2594–2613](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py#L2594-L2613)

Native NodeResultCache дополнительно проверяет active tenant scope, manifest ownership, typed replay proof и current entry identity; provider operations сериализуются отдельным I/O lock с revocable tokens. Эти owners прочитаны, но fixture cache не доказывает access/custody или native artifact admission. [S06:380–453](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/idempotency.py#L380-L453) [S06:564–652](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/idempotency.py#L564-L652)

## 3. B52: reuse существующей async-границы и честная отмена

Cache.get/validator/recovery/put используют `run_blocking_async` с remaining timeout, либо explicit unbounded только при отсутствии owner deadline. Whole Common owner имеет finite FIFO queue, physical-slot accounting и typed backpressure; новый pool на каждый I/O не создаётся. Actual AsyncArtifactStoreAdapter делегирует в тот же helper. [S01:1601–1639](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py#L1601-L1639) [S01:1909–1942](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py#L1909-L1942) [S03:28–73](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/core/artifacts/async_store.py#L28-L73)

**P03:** slow synchronous cache fixture60мс в actual `_execute_node` оставляет независимой coroutine **56ticks**; actual AsyncArtifactStoreAdapter.get_bytes принимает slow fixture и возвращает bytes. Это responsiveness witness, не ускорение диска, p95/p99 benchmark или реальный CAS roundtrip.

**P01:**14 unchanged tests выполняются над whole actual Common module: bounded queue/FIFO, queued cancellation never starts, running timeout retains physical slot, async wait timeout, no traceback/large-array retention after failure, sync/async bridges и context propagation, ordinary responsiveness и preservation inner timeout message. Minimal raises runner не выдаётся за pytest.

**P07:** actual `_put_cache_entry` при timeout сразу discards key, а worker finally делает discard повторно после позднего fixture publication. При cancellation shield дожидается underlying writer и тоже не позволяет current index воскреснуть. Оба indices пусты, оба workers завершились. **Это не обещание отменить поток или удалить уже записанные immutable CAS bytes.** Native cache writer допускает index лишь после verification/deadline/current-token checks; долговечность и fresh recovery остаются G01. [S01:1720–1778](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py#L1720-L1778) [S06:770–863](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/idempotency.py#L770-L863) [S17:176–184](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/README.md#L176-L184)

## 4. C63-R01: completed Future → callback registration может ждать синхронно

`_SharedFuture.add_done_callback` оборачивает callback в `executor.run_callback_sync`. Для уже completed Future base registration вызывает wrapper немедленно в регистрирующем потоке. Если это event loop, `run_callback_sync` может ждать capacity, а после admission делает blocking `future.result()`. `run_blocking_async` вызывает asyncio.wrap_future до своего await. [S02:223–241](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/common/async_tools/__init__.py#L223-L241) [S02:299–353](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/common/async_tools/__init__.py#L299-L353) [S02:949–957](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/common/async_tools/__init__.py#L949-L957)

**P08 — контролируемый допустимый порядок:** actual invoke завершён; его physical reservation освобождена; второй actual job занимает единственный worker. Audit submit interposition возвращает уже completed actual SharedFuture в исходный helper. Actual wrap_future регистрирует delivery callback; controller thread освобождает занятой worker через80мс после начала регистрации.

Итог: **wrap_future80.4мс, helper80.8мс,0neighbor ticks во время block**, result42. Helper timeout задан10мс, но ожидание callback registration происходит до его await/deadline setup. Numeric result сам завершился вовремя; возврат42 соответствует documented receipt semantics и **не объявляется ошибочным результатом**. Нарушение — синхронный stall event loop, от которого исходный B52 требовал уйти. Workflow hard guard может затем отказать publication; его обход здесь не показан.

**Severity medium, confidence high bounded.** Это race interleaving, не утверждение о каждом вызове или измеренный production deadlock. Обёртка submit только фиксирует порядок, wrap wrapper только измеряет и вызывает original; actual callback machinery не переписана.

Минимальное направление — согласовать existing callback owner и asyncio delivery так, чтобы регистрация не ждала physical worker синхронно на event loop. Сохранить finite queue, physical-slot ownership, bounded cancellation и reentrancy refusal; не отменять guards ради быстрого green.

## 5. B55: waiting producer можно не запускать, running работу нельзя магически отменить

Повторный `cancel_event` check расположен после acquire внутри try/finally; release выполняется при раннем skip, исключении метрик и cancellation. Fail_fast signal выставляется после fail outcome; policy continue остаётся отдельной семантикой. [S01:1412–1517](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py#L1412-L1517)

**P05:** actual full tier method с parallelism1 и четырьмя aliases. Первый producer coroutine ждёт30мс, позволяя остальным ожидать semaphore, затем fail. Fail_fast запускает толькоa, records fail/skip/skip/skip; continue запускаетa,b,c,d. Producers/report DTO — explicit fixtures; actual semaphore/TaskGroup/merge остаются реальными.

**P06:** optional metric throwsRuntimeError после ожидания; оба producers всё равно выполняются, degraded event фиксируется. При cancellation actual taskgroup finally освобождает slot. Tracking subclass не меняет asyncio.Semaphore behavior; обе проверенные semaphore values после выхода равны1. Native integrated result/report/checkpoint retention не выводится из этих counters.

## 6. Активация и содержательная граница

LocalWorkflowRunner реально строит AsyncWorkflowExecutor, передаёт parallelism/checkpoint/cache seed refs и awaits execute; это не isolated unused class по одному имени. Однако native runner/wholeworkflow в текущем runtime не запущен. [S16:43–77](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/runner/local_runner.py#L43-L77)

Содержательная capability здесь — продолжить честную работу с уже полученными основаниями, не тратить новый compute на разрешённый hit и не блокировать независимый научный шаг из-за медленного store. Исправные keys или throughput не превращают cached artifact в научно истинную рекомендацию; current applicability/custody и policy admission остаются обязательными. Не требуется новый semantic/deterministic model inventor.

**G01:** pytest отсутствует, public executor import останавливается в Corestore2118 на Python3.14 syntax под3.12.14; Pydantic2.13.4 вне pinned<2.13. Standalone actual Common import exit0;8engine methods выполнены отдельно с8package shells. **G02:** нет representative p95/p99, serialization/RAM, provider thread-affinity и durable completed-result/recovery qualification. Последующие RES packets не считаются заранее закрытыми.

Первый bounded run exit0;14 existing bodies прошли изолированно. Исторический lost C63 не использован как evidence. Repo чист; нет installs, source edits или services. MATCH R01 — воспроизведение ограничения, не product PASS.

[Диагностика](../04_Проверки/C63_EXE01/bounded_diagnostics.json) · [Команды](../04_Проверки/C63_EXE01/commands.json) · [Границы](../04_Проверки/C63_EXE01/native_verification.json) · [Источники](../05_Источники/C63_источники.json) · [Остатки](../01_Реестры/C63_остатки.json).

**63/127 пакетов рассмотрены ограниченно;149 уникальных B/LA частично оценены. Следующий — EXE-02. Полного закрытия нет; фаза2 не начата.**
