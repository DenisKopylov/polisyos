# E02 — окончательные архитектурные решения для реализации

Редакция после самостоятельного критического прохода G, 20 октября 2026. Новые субагенты не использовались. Проверялись документы, конкретные source paths и последовательности исполнения; тесты, imports, builds и нагрузка не запускались. Это выбранные инженерные контракты, **не приёмка реализации**: `G_acceptance=false`, `source_acceptance=false`, `closure_ids=[]`.

Исследованный snapshot: `11ff2421e04223fc961dd5a520768fd75bafe1e2`. Авторский runtime candidate в очереди вопросов: `fe046fefbb06fc3dcaf259766f048a6defed58ea`. Более новый coding source требует delta reconciliation. Этот документ и обновлённые AD01–03 заменяют предыдущие формулировки пакета в перечисленных ниже местах. Исторические reviews сохранены с их прежней границей.

## Что изменил самостоятельный анализ

Основной выбор выдержал критику: existing owners, compiled output binding, один compute owner с serial folds, versioned observational envelope. Но прежний текст оставлял следующие реальные неопределённости.

| Найденная проблема | Конкретный контрпример | Окончательное исправление |
|---|---|---|
| Неточно описана граница compute | Fingerprint уже выполняется под executor, но input создан caller-ом, а output сериализуется после release | Исправлена source attribution. Новый admitted callable охватывает prepare→fingerprint→dispatch→serialize/persist→cleanup; возвращает refs |
| Future callback ошибочно можно принять за worker | Late callback запускается на registering thread, его reservation counter не делает этот thread physical worker | Heavy callback work только через общий owner; обычные notifications bounded. Не менять Future semantics глобально |
| In-memory projection cache недостаточен | Первый GET после restart заново загружает большие outputs для law computation | Persisted typed projection у существующего evaluation owner; cold GET только bounded admission/read, heavy verification отдельная admitted работа |
| Method pin слишком поздний | POST принят при defaults V1, очередь ждёт, registry обновлён до V2 | Resolved method/defaults/runtime intent сохраняется до acceptance; worker проверяет pin, не выбирает заново |
| Четыре sibling request fields создают лишние неоднозначные состояния | Ref есть, method нет; duplicated selection в params и state; serializers подставляют null | Один strict `observational_input` с обязательным protocol/source/method; отсутствие всего объекта сохраняет прежний workflow |
| Reuse может незаметно изменить старый смысл | Generic metric помещается в fiscal-only SourceMetricObservation; target.version добавляется в старый envelope | Старый fiscal contract остаётся неизменным; новый typed nested observation в versioned evaluation vector; target version остаётся в существующем contract ID |

Это проверки класса проблемы: стоимость и identity должны сохраняться **на всей границе передачи**, а не только внутри `dispatch`. Дополнительные provenance engines, schedulers, permanent compatibility carriers и eager replay на чтении эту границу не исправляют.

## AD-E02-01: compiled binding и сохранённая проверенная metric

**Выбран B: extend существующий путь.** Разделить execution origin, metric meaning и unit representation. Их успешная проверка не означает scientific adequacy или publication authority.

1. Compiler/IR фиксирует выбранный objective/metric, точный graph node/slot, method version/ABI, semantic definition, population/axes/denominator/time/quantity role, output contract и закон преобразования.
2. Graph executor захватывает actual selected output bytes, actual implementation/backend/RNG и полный occurrence inventory. Повтор node имеет отдельный occurrence ID; duplicate IDs и неявный last-write-wins запрещены. Необязательные большие outputs могут быть `not_retained`, но не доступны как доказанная metric.
3. CAS хранит acyclic graph: binding set → plan basis → captured outputs → execution bundle → SimulationResult selected manifest. Binding set ссылается на graph, не на содержащий его plan. Старый SimulationResult 1.4 JSON остаётся неизменным; новые manifest edges не разрешают скрыто менять payload schema.
4. Existing Runtime owner атомарно выбирает attempt/fence/result/bundle. Это establishes accepted origin в доверенной runtime boundary. Hash и caller run_id отдельно origin не доказывают.
5. Fresh admission worker разрешает source, исполняет registered law/adapter и сохраняет typed observations через existing PolicyEvaluationVector **1.2** и writer. Existing SourceMetricObservation 1.0 сохраняет government-balance-only meaning.
6. Existing owned run/evaluation record привязывает projection к exact source tuple и verifier revision. Raw result может существовать до verification; пока association нет, metric-qualified read остаётся `verification_missing`. Поздняя verification не заменяет history и не перепривязывается к новой winning attempt.
7. L3/L4/GET используют один admitted reader. Он читает bounded persisted projection и проверяет owned selection, small CAS objects, current access/purpose и verifier compatibility. Cold GET не материализует arrays, не исполняет law и не запускает simulation.

Новые предлагаемые schema IDs:

| Носитель | Выбранная версия/owner |
|---|---|
| Compiled binding set | `policyos.foundry.method_metric_binding_set.v1`, existing compiler/IR |
| Execution bundle | `policyos.foundry.method_execution_bundle.v1`, existing graph execution |
| Verified observations | Typed `method_metric_observations` в existing `polisyos.scientist.policy_design.PolicyEvaluationVector`, proposed version 1.2 |
| Winning result / verified projection association | Extension existing Runtime owned record и его native transaction/version discipline; отдельного ledger нет |

**Unit rule:** identity только для того же установленного quantity kind/role и exact selected representation. Ratio↔percent — только зарегистрированная exact rational пара с declared numeric rounding/error. Reduction, weighted mean, difference, calendar, FX/deflator и stock↔flow требуют compiled typed law и необходимых context inputs. Одинаковые dimension/name/scale не создают такой закон. Никакой universal Pint/QuantityValue migration сейчас.

**Authority/time:** значения — candidate. Source observation epoch, execution time, verification time и read time различаются. Permission/currentness/publishability не становятся вечными от cached verification. Unsupported historical build сохраняет provenance и limitation; same-code replay не выдаётся за independent science.

**Migration:** readers → capture/writers → admission/persistence → consumers. Numeric-only historical artifacts читаются как limited/unit-unknown. Absent edge и present-invalid edge различаются: во втором случае qualified fallback запрещён. Для нового qualified пути legacy alias/default score не заменяет unavailable bound metric.

**Минимальный решающий сигнал:** настоящий ProgramGraph→method→CAS→fresh admission worker→persisted projection→fresh L3/L4/GET; независимый arithmetic oracle; removal binding/owner association; forged-but-rehashed artifact; retry/fence swap; semantically different equal-shape input; cold GET с запрещёнными heavy calls.

Подробный contract, footprint и отрицательные случаи: [AD01](01-method-output-metric-unit.md).

## AD-E02-02: общий admission до и после dispatch

**Выбран existing process-wide SharedExecutor и serial folds.** Вложенный fold fanout не нужен для исходного B56. Это не разрешает уменьшить configured workload: полный model/fold/repeat/seed roster и все его competing callers должны остаться в witness.

Resource unit — **physical worker slot данного process instance/profile**. Capacity фиксируется при запуске; live resize отказ. CPU threads, BLAS threads, RSS и deployment-wide capacity — отдельные свойства. Их не приписывать slot cap.

Новый route:

`durable job + frozen refs/intent → finite owner queue → physical worker → bounded decode/normalize → fingerprint → method → serialize/persist → cleanup → small refs/outcome → fenced publication`.

- В очереди нет arrays и full input copies. Переполнение сохраняет durable job с первоначальным FIFO ticket; existing dispatcher повторяет oldest-eligible admission. Никакого второго scheduler/counter.
- Completed handles содержат refs/diagnostics, не MethodResult, arrays или retained exception frames. Slow persistence занимает worker до завершения: cap не освобождает тяжёлую работу в unbounded caller layer.
- Cancel queued действительно предотвращает start. Cancel/timeout running не освобождает физическую ёмкость. Retry ждёт capacity; old attempt теряет право публикации, даже если физически ещё работает.
- Синхронная работа внутри того же physical worker может выполняться inline. Нельзя держать slot и ждать queued child того же pool. Serial folds не создают child submissions.
- Late callbacks получают только bounded notifications/control tasks. Heavy processing отправляется тем же owner. `_outstanding_jobs` не использовать как доказательство physical concurrency.
- Control publication и ожидание lifecycle выполняются с маленькими refs вне heavy callable. Подготовка projection может идти в том же callable без nested submit либо отдельной работой у того же owner.
- Неперенесённый legacy input_state caller сохраняет честную dispatch-only limitation. Если он входит в declared B56 roster, его нельзя исключить из проверки. Direct graph dispatch, callbacks и post-result consumers входят в census.

**Минимальный решающий сигнал:** complete workload на cap 1/2; independent execution-boundary observation; original-roster→outcome join; overflow/cancel/timeout/retry; no-drop; slow output persistence и failed serialization; removal раннего/позднего bridge; late callback. Eventual admission требует finite eligible roster и прогресса dispatcher/workers. Для hung native call deadline guarantee не обещается.

**Сохраняем честный текущий результат:** 52 PASS / 3 FAIL / 1 intentional SKIP исходной whole command не становится новым green. Retry-view defect — engineering repair. Production-qualified утверждение требует настоящего production roster; обычный HTTP positive проверяется отдельно в AD03.

Подробности: [AD02](02-shared-compute-admission.md).

## AD-E02-03: атомарный request и неизменное намерение исполнения

**Выбран B как основной versioned path; A — только явный migration protocol.**

Новый публичный carrier — один объект `WorkflowRunRequest.observational_input`, optional по отсутствию и запрещающий explicit null:

```text
observational_input:
  protocol: method_input_envelope_v1 | legacy_hte_json_v1
  source_ref: exact ArtifactRef with selected manifest profile
  method:
    fqn: exact registered method
    version: optional exact version; absence resolved once before acceptance
    params: optional object; absence resolved once before acceptance
```

Это schema outline, не runnable request. Все required fields и все присутствующие optional fields non-null; extra keys запрещены на каждом уровне. Payload данных внутри HTE envelope имеет свои отдельные optional/null semantics.

**До POST acceptance:** syntax/access/metadata checks; exact registry resolution; freeze submitted selection плюс effective method version/defaults/seed и ожидаемую runtime/profile boundary; durable persistence job/intent. Никаких heavy backend imports и array decoding в handler.

**После получения slot:** resolve один guarded immutable selected view → bounded Core decode → real typed HTE parser/producer → content-admitted intent → real method → output persistence → refs. Worker проверяет prequeue pins. Если поддерживаемая pinned boundary недоступна, typed refused/unavailable attempt; silent latest запрещён. Смена policy может отозвать permission, но не подменить input/method.

**Envelope/producer:** reuse `policyos.ir.observation.method_input_envelope.v1`; новый настоящий target `foundry.causal.hte_observational_data.v1` с existing HTEObservationalData FQN. Outer manifest schema и inner target contract — разные вещи. Existing target ID уже несёт version; не добавлять поле version в старую target shape.

HTE producer реализует реальные текущие ограничения DTO: n≥40, binary treatment, finite aligned arrays, согласованные optional covariates/confounders/names/sample IDs. Это ограниченный поддерживаемый HTE input, не универсальный научный закон. General HTTP selection может расширяться следующими зарегистрированными target contracts; Ukraine/panel не переименовывается в HTE.

- B: проверенный canonical envelope можно переиспользовать. Допустимая representation normalization создаёт новый envelope с lineage, не переписывает original view.
- A: exact raw HTE view, включая selected profile, → **новый** versioned envelope. `artifact_schema=null` старого payload не исправляется новым label. Legacy limitation сохраняется.
- Method/protocol/source mismatch, malformed envelope, missing body version или wrong profile — refusal, без raw sniff/fallback.
- Derived artifacts наследуют governance; default public запрещён. Selected intent, actual consumed input и result связываются persisted edges + owned selection. Fresh GET показывает authorized refs/outcome/limitations, не данные массива.

**Migration:** отсутствие нового объекта сохраняет старый workflow. Новая форма не дублирует selection в top-level sibling fields или general params. Если на более новом source предыдущая форма уже опубликована, её actual clients определяют один explicit adapter/version window; не вводить вечные aliases на всякий случай. A retirement — после полного caller census, writer migration и parity/removal, с versioned policy; historical readers сохраняются.

**Минимальный решающий сигнал:** ordinary authenticated POST→ControlWorker→RunLifecycle→real Scientist/TMLE→CAS→fresh HTTP GET для B; отдельный A migration positive; absence/null/partial/conflict; update registry/defaults **до первого dequeue**; unsupported pinned runtime; revoked access; backing alias replacement; mapping removal; fresh process read без normalizer/dispatch.

Подробности: [AD03](03-observational-http-input.md).

## Как завершить реализацию без нового цикла абстрактных вопросов

1. Исправить existing defects, от которых зависят пути: Core tagged-value decoder, selected-profile preservation, worker retry-view composition. Не ждать нового архитектурного выбора для них.
2. Назначить одного writer Runtime intent/run-record/public DTO и согласовать маленькие interfaces с Foundry/IR owners. Input producer, compute bridge и compiled binding можно реализовывать параллельно при раздельных writers.
3. Собрать **два** полных vertical slices: ProgramGraph→qualified metric и HTTP→observational method. Общие carriers переиспользуются; успешность одного не доказывает другой.
4. Проверить настоящие consumers и generated/public companions. Никакого stop на constructor/dispatcher-only positive.
5. Source freeze и independent review **реализации**, затем affected checks и один общий replay. Эта архитектурная работа не предоставляет runtime PASS и не разрешает сейчас запускать проверки в G research session.

[Полный delivery plan и acceptance matrix](04-implementation-and-verification.md) задают последовательность. Существующий source и новые документы должны reconciled append-only, без сброса чужой работы. `main` не публиковать без отдельного разрешения.

Исполнитель сам решает обычные engineering вопросы: codec, registered handler, schema inventory, strict DTO, compiler wiring, storage association, cancellation, reader, generated companions. Новый вопрос G обоснован только конкретным конфликтом с уже ratified boundary или отсутствующей expressiveness, для которой проверены existing owners и предложен минимальный extension с falsifier.

Настоящие внешние inputs сохраняются внешними: fiscal sign/alias/FX/deflator law, scientific identification/calibration, issuer/permission/custody/currentness, production workload. Они ограничивают соответствующий claim; не останавливают unrelated candidate mechanism. Missing external authority нельзя заменить своим документом, но и missing bridge нельзя выдавать за external dependency.

`paged K_ref` по-прежнему не выбран. Сначала existing streaming + composed parity/removal/source-replacement и измерение реального retained floor при разрешённых ресурсах. Новый OOM сам по себе не доказывает ни необходимость pagination, ни её достаточность.

## Основания и предел проверки

Лично повторно прочитаны deciding fragments source в указанном snapshot:

- `policy-engine/src/polisyos/scientist/compute/runner.py:285–354`: fingerprint внутри executor; serialization/persistence после него.
- `policy-engine/src/polisyos/common/async_tools/__init__.py:63–159`: late callbacks, physical-worker distinction и nested bridge.
- `policy-engine/src/polisyos/scientist/nodes/builtins/decide/policy_runtime_artifacts.py:178–206`: существующий vector writer и source edges.
- `policy-engine/src/polisyos/scientist/methods/search/objective.py:25–88`: узкий fiscal SourceMetricObservation.
- `policy-engine/src/polisyos/foundry/methods/catalog/causal/protocols.py:207–285`: actual HTE shape/validation.
- `policy-engine/src/polisyos/core/contracts/control.py:395–450`, `runtime/http/services/control/run_lifecycle.py:4120–4210`, `scientist/nodes/builtins/simulate/run_causal_evaluation.py:670–810`, `ir/observation/bundles.py:35–88`: current request, launch, loader и envelope boundaries.

Внешняя проверка правил: [Python Future](https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.Future.add_done_callback) различает running cancellation и callbacks; [JSON Schema object](https://json-schema.org/understanding-json-schema/reference/object) различает required/absent/null и strict object constraints; [AIP-180](https://google.aip.dev/180) отдельно рассматривает wire/source/semantic compatibility. Это основания дизайна, не доказательство состояния PolicyOS. Предыдущая сравнительная SOTA работа сохранена в [research record](05-research-and-red-team.md).

Pattern pass: P01/P02 — два настоящих producer→artifact→bridge→consumer пути; P04/P05 — raw/candidate/verified/authority не сливаются; P07/P08 — selection/replay/time roles; P10/P32/P37/P38 — проверяется исходная величина и owned admission, а не labels; P27/P31 — existing owners; P29 — behavioral/removal signals; P40 — исправлена граница класса; P41 — прежняя краснота не переименована. Нереализованные связи остаются `bridge_missing`/`artifact_missing`/`consumer_missing`/`verification_missing`/`surface_missing`/`semantic_test_missing` в своих границах.
