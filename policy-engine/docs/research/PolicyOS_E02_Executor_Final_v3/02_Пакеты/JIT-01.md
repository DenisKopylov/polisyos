# JIT-01 — Правильный warm kernel, single-flight и дешёвая подготовка

## 1. Паспорт и результат

**LANE-04 · CP-1 · основание 20d9009be21097bfbdc38a546a15cc60213b8ace · статус: ТЗ, не выполнено.** Технический исполнитель и reviewer назначаются проектом. Исходные ID: B49, B50, B53. Тип: miss→claim race repair + native JAX qualification.

Одна полезная wrapper construction на cache identity/generation/specialization при управляемой гонке; текущие dynamic defaults и no-evaluation preparation сохраняются.

Основания: [аудит](../05_Основания/Аудит/02_Пакеты/JIT-01.md), [все остатки](../05_Основания/Аудит/01_Реестры/C45_остатки.json), [неизменная исходная карточка](../05_Основания/Аудит/05_Источники/JIT-01_исходные_строки.txt), исходный объединённый план §JIT-01 (исторические строки 5530–5648).

## 2. Уже работает — сохранить

- Неизменяемый общий _CompiledKernel и отдельная текущая dynamic binding; ранее выданный handle не меняется.
- Static/shape/dtype/backend/execution flags и selected executable identity различают specialization, dynamic values не раздувают key.
- Flights принадлежат общему CompilationCache; terminal result/error/invalidation публикуется до event, followers имеют deadline/cancel.
- Generation invalidation не позволяет старому put загрязнить новый cache.
- Declared shapes не вызывают pure_step; unknown shape отказывает и удаляет stale placeholder; explicit warmup разрешён и учитывается отдельно.
- CompiledChainExecutor повторно сверяет live plan/context; поддержанный whole-state route не равен portable executable или full slot routing.

## 3. Полнота обязательств и disposition

| Основание | Решение | Требования |
|---|---|---|
| C45-R01 | fix: Повторно проверить допустимый cache result после leader claim с terminal publication для уже joined followers. | REQ-JIT-01-02 |
| C45-G01 | qualify: Real tiny JAX/JIT P-JAX и timing stages отдельно; wrapper count не XLA count. | REQ-JIT-01-01, REQ-JIT-01-02, REQ-JIT-01-03 |
| C45-G02 | qualify: Измерить dtype-changing producer и shape allocation в поддержанном whole-state route; bounded decision, без скрытого pure_step. | REQ-JIT-01-03 |

### Исходные обязанности, не только новые R

- B49: cold/warm current3→30, old2→20, один kernel с разными immutable handles, array defaults и актуальный runner payload (REQ01).
- B50: terminal-before-notify и cache-owned coordinator уже исправлены; закрыть именно miss→claim повторную сборку, сохранить cancel/error/generation (REQ02).
- B53: preparation не выполняет оценивание; native shape/dtype квалификация и explicit warmup измеряются отдельно, без выдуманного full portable compiler (REQ03).

## 4. Нормативный контракт

### REQ-JIT-01-01
MethodCompiler.compile сохраняет current dynamic defaults при reuse kernel: x10, old2→20, warm3 и cold3→30 без override; old handle остаётся20. Array defaults корректно сравниваются; override4→40, unknown/static override отвергается. Selected implementation identity, static/shape/dtype/backend changes не используют неподходящий kernel. Native dispatcher→JaxRunner→_compile_resolved получает current params/seed, а dynamic-only request не создаёт новую jit closure.

Источник: B49, B50, B53; аудит: C45-G01; проверки: TEST-JIT-01-01.

### REQ-JIT-01-02
После исходного cache miss и получения leader claim повторно согласовать наличие подходящего результата до _compile_method. Если прежний flight уже опубликовал результат той же generation/identity, новый flight завершается им, будит всех присоединившихся followers и возвращает их собственные bindings без второй wrapper construction. Cache/result publication предшествует notification; invalidation, build/publication error, BaseException, follower timeout/cancel завершают существующие terminal paths без вечных wait и без stale-generation result.

Источник: B49, B50, B53; аудит: C45-R01, C45-G01; проверки: TEST-JIT-01-02.

### REQ-JIT-01-03
Preparation declared-shape chain не вызывает содержательные pure_steps; реальное исполнение делает ровно по одному обязательному шагу. Unknown data-dependent shape и inconsistent symbolic dimensions честно отвергаются без stale sample substitution. На P-JAX отдельно проверить dtype-changing producer→consumer: result6 с фактическим dtype, реальное retracing/specialization и память shape placeholders. Если placeholder dtype не соответствует заявленной specialization, выбрать существующий abstract shape/dtype или lazy specialization boundary и поправить metadata/owner; запрещено скрыто численно выполнить pure_step ради dtype. Warmup3 остаётся3 явными вызовами; wrapper/tracing/lowering/first-execution/warm timings отчётно раздельны.

Источник: B49, B50, B53; аудит: C45-G01, C45-G02; проверки: TEST-JIT-01-03.

## 5. Техническое решение и producer → consumer

Предпочтителен минимальный repair в compile после successful leader claim и внутри try/terminal error envelope: повторный cache.get(spec, token, identity); если hit, вызвать существующий generation-guarded publish_flight для этого нового flight с уже готовым объектом, затем применить тот же current-default binding/invalidated retry путь. Это освобождает followers, присоединившихся между claim и recheck. Проверка current_token перед return и лимит retry сохраняются. Альтернатива — атомарный get-or-claim в cache с единым порядком locks (_lock затем _flight_lock, как publish_flight); не держать locks при _compile_method. Не чинить только return cached: это оставит новый flight hanging. Shape/dtype работа ограничена read/measure/decision: текущий _update_output_shapes использует np.empty и guessed existing/input dtype. На tiny changing-dtype witness определить supported actual profile; где доступен abstract declaration — хранить shape/dtype без больших allocations, иначе lazy prepare на реальном upstream output. Не требовать нового graph executor и не превращать tracing arbitrary impure code в safe evaluation.

### Проверенные owners на срезе
- policy-engine/src/polisyos/foundry/methods/compiler/__init__.py: CompilationCache.claim_flight/publish_flight, MethodCompiler.compile/compile_chain/_update_output_shapes
- policy-engine/src/polisyos/foundry/methods/compiler/specialization.py: build_specialization
- policy-engine/src/polisyos/foundry/methods/backends/jax_runner.py: JaxRunner.execute
- policy-engine/src/polisyos/foundry/methods/_internal/executable_identity.py: _ExecutableIdentity

Не добавлять dynamic values в key, не мутировать shared defaults и не создавать новый distributed lock. Dtype mismatch пока qualification gap, не заранее доказанный неверный JIT result.

## 6. Локальная приёмка — все будущие проверки NOT_RUN

### TEST-JIT-01-01
- Уровень: P-JAX native tiny.
- Setup: Real tiny JAX method x*coefficient, supported pinned P-JAX; old2/warm3/cold3, vector defaults, selected implementation same FQN variant; delegated wrapper-build observer.
- Действие: Call handles without override and through native JaxRunner; change dynamic then static/input dtype/shape/backend; inspect kernel identity and synchronized outputs.
- Точный oracle: 20/30/30, old20, explicit40; vector[20,30] then[40,50]; one shared kernel dynamic-only; changed identities don't alias. block_until_ready timings separate, no speedup claim from wrapper count.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-JIT-01-02
- Уровень: deterministic concurrency + native tiny reuse.
- Setup: Events: leader1 paused build; request2 records cache miss then pauses immediately before actual claim; leader1 publishes/removes flight; request2 resumes. Add actual joined follower and two compiler instances sharing cache.
- Действие: Release precise event order; inject build error, publish error, controlled BaseException, generation invalidation, timeout/cancel independently.
- Точный oracle: One wrapper construction on same generation/identity, all successful callers correct own defaults; result/cache available before event. Old-generation publication rejected; followers released/errors propagated; flights empty after terminal paths. Invalid timeout0/negative/NaN/inf refused before build. Old implementation produces2 wrappers on race.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-JIT-01-03
- Уровень: unit + targeted native integration.
- Setup: Actual composer whole-state producer/consumer with declared scalar shape, stale vector sample; unknown shape and inconsistent symbols; integer producer vs float32 placeholder; explicit warmup3.
- Действие: Prepare cold+warm, execute; measure actual P-JAX dtype and trace/lower/first/warm separately; remove validation context control.
- Точный oracle: Prepare0+0 numerical steps, execute1+1 with supported witness0.5; dtype case actual6 and accurate declared support/metadata or bounded owner fix; unknown refuses0+0; warmup exactly3; missingcontext refuses before pure_step. Evidence states remaining dtype/profile limits, not blanket compiler closure.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

Повторно использовать/расширить реальные места, а не создавать 127 harness: `policy-engine/tests/unit/remediation/test_jit_01.py`. До выбора selector прочитать полный test/fixture. Это проверенные пути, не утверждение о наличии всех предложенных assertions.

Допустимые doubles: Events и delegating counters, injected failure/clock для узких unit cases. Запрещено: NumPy/shim вместо native JAX result, fakejit identity для machine reuse claim, sleep-based вероятностный race.

## 7. Общая интеграция и порядок

Single tiny native job P-JAX; common warm compile witness передаётся RES-04 checkpoint consumer, но process-local cache identity не объявлять persisted provenance.

Точные общие сценарии: E02-I04-B из [контракта интеграции](../03_Интеграция/LANE-04.md); одно свидетельство переиспользуется по неизменным input/backend bindings. Зависимости: нет обязательного нового предшественника; исходный DAG — ориентир, работающий контракт может удовлетворять ребру без нового ремонта. Общие файлы из §5 интегрировать последовательно с затронутыми owners; lane не новый runtime-реестр и не требование полного CI после каждого пакета.

## 8. Совместимость, история, rollback

Public compile defaults/handles остаются совместимыми; no-code qualification допустима для B49/B53 при соблюдении контрактов. Current whole-state/raw-state compiled executor scope явно сохранён, без обещания missing full DAG routing.

## 9. Free-grow и design direction

- Reuse относится к стабильной specialization, текущее значение запроса связывается отдельно.
- Подготовка не должна скрыто расходовать вычислительную работу; unknown shape не превращается в вымышленное знание.

Архитектурные источники: [policyos-identity-and-custody-boundary.md §1, §3–6](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md); [policy-design-custody-time-model.md §2–5](../05_Основания/Архитектура/policy-design-custody-time-model.md). Историческая подлинность и текущая пригодность раздельны; физический layout design-docs не догма.

## 10. Нерешённые решения и передача

- G02 bounded decision: предъявить actual downstream dtype/trace/allocation observations и выбрать no-code documented supported profile либо existing abstract/lazy boundary repair; нельзя закрыть gap лишь source чтением.

Предъявить patch/base SHA (либо обоснованный no-code результат), актуальную карту callers, REQ→TEST→evidence, фактические команды/логи, различающий контроль и сохранённые инварианты. Поддержанный native профиль: P-CORE (Python >=3.14,<3.15 и project lock); для native численных/JIT/train проверок P-JAX (тот же lock, JAX/jaxlib/optax, deterministic tiny CPU); для процессов P-PROCESS, для поставки P-PACKAGING. Не устанавливать зависимости без отдельного разрешения. Fixture/source-only, исторические PASS и отсутствие ошибки при импорте не закрывают свежий producer→persistence→fresh-reader. Успешная сериализация/конверсия/подпись не доказывает научной истины или полномочия policy result. Никакое требование/тест этой карточки ещё не исполнены.


Полные probes исходного аудита доставлены отдельно в phase1 ZIP; ссылки аудита на них не означают включение тяжёлой evidence в этот исполнительский комплект.
