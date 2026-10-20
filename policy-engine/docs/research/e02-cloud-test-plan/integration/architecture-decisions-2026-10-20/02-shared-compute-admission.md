# AD-E02-02 — один общий compute owner, serial folds

Disposition: **selected for implementation**. Источники — snapshot `11ff2421e04223fc961dd5a520768fd75bafe1e2`; source acceptance/closure отсутствуют.

## Решение и исходный критерий

Сохраняем D03: money ledger, lifecycle lease и compute permit имеют разные назначения. Existing process-wide `_SharedExecutor` в `common/async_tools/__init__.py` — единственный slot owner. `scientist/compute/runner.py` передаёт dispatch через `run_shared_executor_sync`; TMLE folds исполняются serial внутри admitted work. **Inner-fold fanout не нужен для E02.** Отдельный TMLE pool/scheduler и deployment Ray/Dask не вводятся.

Оригинальный B56: `docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md:1409–1424` в исследованном commit; selected D03 — `docs/research/e02-cloud-test-plan/integration/connected-closeout-plan-2026-10-08/02-decisions.md`. Требуются общий configured resource bound для competing admitted work, lossless waiting, одинаковый полный model/fold/repeat/seed roster, согласованные результаты/provenance и wall/RSS/active/wait observations. Критерий предлагает parallelism на одном уровне. Полный настроенный локальный workload допустим; production-only workload и public HTTP не являются добавочными условиями B56. Authentic production claim и AD03 HTTP claim проверяются отдельно.

Это не сужает B56 до config field: cap должен реально охватывать **весь объявленный competing workload** в выбранной boundary. Если workload использует несколько Runtime процессов или иные executors, локальный singleton не доказывает общий deployment cap. Такой профиль либо явно ограничивает admitted execution одним процессом, либо уже требует отдельной обоснованной extension того же admission owner. Нельзя исключить конкурента из roster ради зелёного результата.

## Точный ресурсный контракт

Существующий `SharedExecutorProfile` сохраняет positive capacity/revision и candidate authority. Новая semantics revision профиля описывает:

- `owner_scope`: конкретный Runtime process instance и executor instance; process start identity, а не только переиспользуемый PID.
- `cap_unit`: **один executor worker slot**. Lease покрывает input materialization/validation, fingerprint, dispatch, тяжёлую сериализацию/CAS persistence и освобождение принадлежащих callable buffers. Наружу возвращаются bounded refs/outcome. Текущий dispatch-only receipt не переименовывается задним числом в расширенный lease.
- `capacity`: positive integer; одна работа занимает один slot. Не вводим guessed CPU/GPU/RAM weights без измеренной модели.
- `pending_policy`: finite configured number/metadata budget, FIFO arrival order, cancel semantics; persistent job ownership сохраняется при backpressure.
- `nested_policy`: same-worker synchronous inline допустим без нового concurrent slot; насыщенный nested submit — typed refusal. Fanout/hold-and-wait запрещены в этом профиле.
- native threading settings, effective serial-fold policy и допустимый input size/depth/element policy pin-ятся как execution configuration, но не маскируются под физический memory cap.

Для каждого момента `t`: число реально занятых workers в этой boundary ≤ capacity. Running work, чей caller уже cancelled/timed out, **продолжает занимать slot** до окончания callable и cleanup. Конкретный queue item / attempt владеет unique lease; double release не освобождает чужую работу.

Такой cap **не означает** CPU cores ≤ capacity или RSS ≤ budget: BLAS/native libraries могут запускать потоки и выделять память внутри одного worker. RAM/OOM safety требует отдельного measured envelope или реального process/platform enforcement. Наблюдённый peak RSS — измерение данного workload, не математический общий bound. Никакая монетарная квота этого не исправляет.

## Конкретный недостающий bridge

В текущем `scientist/compute/runner.py:285–329` **fingerprint уже находится внутри** `dispatch_with_observation`, переданного `run_shared_executor_sync`. Прежнее описание fingerprint как pre-permit работы было ошибочным. Реальные разрывы: caller передаёт уже materialized `input_state`, а `to_python_data(method_result.output)` и `store.put_json` исполняются **после** возврата из executor (`:331–354`). Поэтому массивы могут удерживаться ожидающими callers и completed results вне dispatch boundary. ThreadPoolExecutor также имеет unbounded pending queue, а synchronous bridge не отдаёт lifecycle caller cancellable handle.

**Выбранная extension:** один lazy/ref-based submission bridge у existing SharedExecutor/MethodBackend owner. Queue не становится вторым slot authority; она выдаёт работу тем же physical workers и учитывает тот же lease lifecycle.

1. Runtime сохраняет durable job + immutable **requested** source/method intent и refs. В ожидании compute держатся bounded metadata и selected refs, не decoded arrays/полные copies. Effective envelope/admitted intent до normalization ещё не существуют и не подставляются по догадке.
2. Submission возвращает cancellable owner handle с stable job/attempt ID. Finite FIFO pending queue принадлежит тому же owner; underlying executor не используется как безграничный второй backlog.
3. Только получив worker slot, callable разрешает выбранные CAS views, читает bounded bytes, декодирует input, проверяет semantic/resource policy, выполняет normalization и сохраняет **admitted intent** с effective ref до fingerprint/dispatch. Тот же resolved input передаётся методу без повторной полной materialization. Upstream node не должен заранее создавать по массиву на каждого waiter.
4. Тот же callable сохраняет необходимые output payloads/evidence, выполняет bounded serialization и cleanup, затем возвращает **только небольшие refs/outcome**. Во Future/очереди/callback closure не удерживаются arrays или `MethodResult`. Ошибку persistence нельзя выдать за успешный persisted результат. Failure handle сохраняет bounded structured diagnostic и ref на полный разрешённый diagnostic output; live exception traceback с frame locals и большими input/output buffers не передаётся в долгоживущий handle. Это не обещание мгновенного возврата RSS allocator-ом.
5. Если queue admission временно невозможен, durable job остаётся у Runtime; typed retryable backpressure/запланированный retry, stable identity и отсутствие duplicate accepted execution. Existing durable dispatcher повторяет admission oldest-eligible по первоначальному enqueue ticket; backpressure не обновляет ticket и не позволяет бесконечно обгонять старый job новыми. Это ordering у существующего dispatcher, не второй slot counter. Не молча выбросить work и не объявлять его finished. Pending metadata тоже ограничивается policy.
6. Guarded control publication после завершения callable использует refs и fence. Worker не ждёт control-plane completion или дочернюю задачу того же pool, удерживая slot. Owner handle различает queued, running, physically finished и publication eligibility через existing lifecycle states. Heavy metric verification после сохранения исходного результата — отдельная работа у **того же** owner либо продолжение внутри текущего callable без nested submit; не вычисление в GET.

**Callback boundary:** `common/async_tools/__init__.py:63–91` допускает late callback на registering thread; `_outstanding_jobs` не равен числу physical workers. Поэтому «все callbacks ограничены cap» — неверное обещание. В новом admitted пути notification callbacks делают только bounded metadata/control work. Любая materialization, derivation или persistence из callback обязана пройти тот же compute bridge; direct heavy callback запрещён контрактом пути и проверяется caller census/removal. Synchronous callback, реально выполняемый внутри worker, входит в его занятость. Не менять стандартную Future callback semantics глобально и не вводить второй semaphore для маскировки этого различия.

Этот выбор соответствует documented [Future callback/cancellation semantics](https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.Future.add_done_callback): callback уже завершённого Future может исполняться немедленно, running work не отменяется обычным `cancel()`. Source PolicyOS задаёт более точную локальную границу.

Compatibility: existing callers с готовым `input_state` могут временно использовать dispatch-slot API с **явной retained-input/output-memory limitation**. Для полной новой refs-only capability ordinary observational route обязан применять весь bridge prepare→dispatch→persist. Честная compatibility boundary не является доказательством раннего admission на всех старых callers. Полный caller census следует из actual submit APIs, post-result consumers и callbacks; не фиксировать вручную один HTTP endpoint. Полный B56 roster нельзя сузить исключением реально участвующего legacy caller.

## Cancellation, retries, leases и reconfiguration

| Ситуация | Обязательное поведение |
|---|---|
| Cancel queued item | Атомарно удалить/mark-cancel единожды; не materialize и не запускать. Durable run получает соответствующий outcome |
| Cancel между dequeue и start | Согласовать с owner handle: либо не запускать и вернуть slot, либо уже running и удерживать до реального конца |
| Timeout/ControlWorker stop при running native callable | Не считать освобождённым compute. Cooperative cancel допустим; thread нельзя объявить умершим только по lifecycle timeout |
| Retry пока предыдущая попытка физически работает | Две физические работы занимают две capacity units; cap может заставить retry ждать. Old attempt не может publish по новому fence |
| Stale attempt успел записать CAS | Bytes сохраняются diagnostic/unselected; guarded commit AD01/AD03 не меняет current result |
| Exception в method/callback | Release после cleanup в owner finalization; сохранить полный failure, не success из exit path |
| Повторное release/commit | Idempotent только для того же lease/tuple; чужой slot/result не освобождается/не заменяется |
| Изменение capacity/profile live singleton | **Выбрано refuse**, как уже делает existing configure после initialization. Для другого cap — fresh process/profile; не silent resize |
| Hung native work | Slot остаётся занят. Нет обещания bounded completion/fairness без worker-progress assumption. Process isolation/kill — отдельное платформенное решение |

FIFO внутри owner означает порядок принятых ожидающих работ; overflow backlog получает oldest-eligible retry по правилу выше. Для конечного eligible declared roster, прогрессирующего durable dispatcher и завершающихся workers проверяется eventual admission всех jobs, включая backpressured. Это не weighted root fairness и не гарантированный wall deadline. Serial folds не enqueue-ятся как дети. Не добавлять root-round-robin или DRF ради гипотетической очереди. Если будущий measured use case потребует nested fanout, отдельная extension **того же** owner должна атомарно делить parent reservation/выдавать уникальные child loans; parent-held resources не исчезают при ожидании. Это не обязательная часть текущего E02.

## Telemetry, результат и source truth

Сохранять bounded deciding trace для выбранного replay: owner/process/profile revision, capacity/unit, run/attempt/lease IDs, enqueue/dequeue/start/actual-finish/release/cancel/retry sequence, monotonic local order и wall times, requested/effective worker settings, complete scientific task roster, output refs и failure/skip reasons. Times разных процессов без синхронизации не сравниваются как глобальная строгая шкала.

Независимый execution-boundary observer фиксирует фактический старт/конец callable; эти события и lease events получают согласованный process-local monotonic sequence в точках перехода, checker сопоставляет их причинно, а не сортирует приблизительные wall timestamps. Одного `active_count`, requested workers или metadata `parallel_folds=true` недостаточно. Actual serial folds честно показывают `effective_fold_workers=1`, независимо от `parallel_folds=true,max_parallel_folds=0` (последний — request sentinel, не допустимый `capacity=0`). Обязательно wall, wait, active peak и peak memory для полного declared workload, без арифметического превращения 15/60 configured workers в observed CPU demand.

Нынешний пакет: **56 случаев = 52 PASS / 3 FAIL / 1 intentional SKIP**, соседний TMLE module 49 PASS / 3 FAIL. Retry-view defect не признан inherited. Manual `_enqueue_job`/disabled safety fixture — ограниченный внутренний witness, не новый ordinary HTTP positive. Архитектурное решение не меняет эти результаты.

## Acceptance и миграция

Сначала существующий runtime dispatch baseline и полный caller denominator; затем refs-only bridge + cancellable finite queue; затем normal producer/consumer route. Old dispatch API можно forward-disable для новых resource-qualified routes, сохранив честное legacy чтение. No profile mutation during replay: cap 1 и 2 — отдельные свежие процессы либо доказанный lifecycle restart.

Future acceptance: полный competing roster через реальный общий owner с сохранёнными safety/admission checks, cap 1/2, serial folds, все outputs/provenance после fresh CAS/control reader, независимый overlap checker. При shared-owner removal сохранить outer worker limits и организовать достаточно независимых callers, чтобы реальный over-cap стал возможен; иначе зелёный mutation ничего не доказывает. Для shared-cap property HTTP optional; для объединённого E02 ordinary POST/GET нужен по AD03.

Adversarial cases: queued и running cancellation; timeout+retry; stale publication; exception/callback; nested cap-1 и saturated cap-2 refusal без deadlock/spin; double release; invalid capacity; queue-full backpressure без потери job; concurrent reconfiguration refusal; size-valid JSON с чрезмерным array expansion; bypass через sibling caller; native threads больше logical cap с честной CPU limitation. Сравнить полный fold/repeat/seed roster и scientific outputs между capacity profiles. Проверки здесь **не запускались**.

Minimum footprint: `common/async_tools`, Runtime container/profile injection, MethodBackend/compute runner, source loader/materializer, ControlWorker cancellation/run fencing, TMLE serial/effective settings, existing run audit/fresh result surface и matched tests. Не заменять неиспользуемым `LocalWorkerPool` или его неработающими resource labels. Capability refs-only admission до wiring — `bridge_missing`; verification/surface остаются missing до реального fresh-reader witness.
