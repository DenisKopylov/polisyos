# CAL-05 — Неактивный механизм не вычисляется как активный

## 1. Паспорт и результат

**LANE-04 · CP-4 · основание 20d9009be21097bfbdc38a546a15cc60213b8ace · статус: ТЗ, не выполнено.** Технический исполнитель и reviewer назначаются проектом. Исходные ID: B185. Тип: квалификация текущего conditional execution, без доказанного нового R.

Настоящий JAX runtime не исполняет inactive emitter и не портит derivative, сохраняя полезный active/scalar-batch calibration путь и явные ограничения producer contracts.

Основания: [аудит](../05_Основания/Аудит/02_Пакеты/CAL-05.md), [все остатки](../05_Основания/Аудит/01_Реестры/C47_остатки.json), [неизменная исходная карточка](../05_Основания/Аудит/05_Источники/CAL-05_исходные_строки.txt), исходный объединённый план §CAL-05 (исторические строки 5772–5839).

## 2. Уже работает — сохранить

- Concrete inactive branch не вызывает runtime selector/emitter и сохраняет key; structural selector admission остаётся compile-time.
- Tracer-safe lax.cond сохраняет active refusal и neutral patch structure; Python bool(tracer) запрещён.
- Mapped schedule predicate честно отвергается даже при одинаковых mapped steps; shared scalar schedule со state-vmap и per-row scalar lax.map поддержаны.
- Dependency flush и merge SUM/OVERRIDE/PRIORITY/ERROR, deterministic node rank и PRNG streams сохранены; независимые writers не становятся случайно последовательными.

Изменение продукта требуется только при воспроизведённом несоответствии ниже; отсутствие native проверки само по себе не дефект. Не создавать искусственный рефакторинг для отчёта.

## 3. Полнота обязательств и disposition

| Основание | Решение | Требования |
|---|---|---|
| C47-G01 | qualify: NumPy/scripted-key MATCH не JIT/grad/Hessian/vmap свидетельство; выполнить существующую native semantics suite. | REQ-CAL-05-01 |
| C47-G02 | qualify: Конкретного mismatch нет; конечный census actual admitted producers и receiving states, abstract structure controls без inactive numerical emission. | REQ-CAL-05-02 |
| C47-G03 | qualify: Общий настоящий calibration consumer и persisted input/report basis отдельно от synthetic schedule correctness; reuse LANE-10 lifecycle evidence. | REQ-CAL-05-03 |

### Исходные обязанности, не только новые R

- B185: отделить подготовку структуры от численного исполнения, доказать inactive derivative1/active1.5 реальными JAX transforms и runtime callbacks; no fake future input, no nan_to_num, no finiteguard bypass (REQ01).
- Полнота current producer patch contract и реальный calibration target-loss/report consumer — квалификация REQ02–03, не изобретение универсальной модели.

## 4. Нормативный контракт

### REQ-CAL-05-01
На P-JAX inactive x=0 до start и после end сохраняет state/key, numerical emitter/selector count0, gradient1 и Hessian0. Active x2 для delta log(x) даёт x+log(x), derivative1.5 и Hessian−0.25; active invalid x0 не санитизируется, существующий refusal/nonfinite guard остаётся. Eager/JIT/AD различают branch tracing и numerical execution. Mapped schedule predicate отказывает до numerical emission; shared scalar schedule state-vmap допускается, mixed row times обслуживает scalar lax.map с правильными row keys/order.

Источник: B185; аудит: C47-G01; проверки: TEST-CAL-05-01.

### REQ-CAL-05-02
Для каждого фактически допускаемого compile_program producer contract в выбранном native профиле active и neutral branches согласованы по output slots/pytree/record count/keys/shapes/dtypes. Составить конечный список из текущего registry и явно записать tested/excluded contracts, включая multiple-record/dtype-transition cases если они admitted; при mismatch исправить общий declared patch template/admission, не вызывать inactive emitter численно. Structural unknown selector отвергается при compile; SUM/OVERRIDE/PRIORITY/ERROR inactive records не writer, dependency reader видит flush, independent writers читают прежний общий base.

Источник: B185; аудит: C47-G02; проверки: TEST-CAL-05-02.

### REQ-CAL-05-03
Calibrator._build_bundle→run_pure_scan либо evaluate_ordered_batch_objective→target loss должен реально потреблять conditional schedule результаты. Tiny canonical IncomeTax case сохраняет selector, state/time/key row alignment и finite validity. Сохранённый calibration report/config/input basis через существующий lifecycle прочитывается новым consumer с теми же schedule/observed-target bindings; synthetic traces не маркируются независимыми наблюдениями, finite gradient не подтверждает empirical/causal authority.

Источник: B185; аудит: C47-G03; проверки: TEST-CAL-05-03.

## 5. Техническое решение и producer → consumer

Текущий owner уже реализует правильное разделение: _concrete_bool для eager, lax.cond для tracer, _admit_schedule_predicate custom batching guard и apply_nodes_batch через scalar lax.map. Основная работа — native qualification, не rewrite. G02 требует ограниченного compile-contract census: извлечь actual admitted mechanism outputs, их record schemas и receiving dtypes; использовать declared shape/template либо abstract evaluation совместимых pure producers. Текущее _neutral_patch_map предполагает один record на output и dtype receiving state; если admitted producer нарушает это, general template хранится в PreparedNode/compile metadata и обе ветви используют его, либо конкретный неподдержанный контракт честно отказывает до исполнения. Нельзя скрыто вызвать emitter на future inputs. В G03 проследить реальные функции Calibrator, а не отдельно тестировать маску. Для persisted lifecycle взять существующий report writer/reader и shared LANE-10 свидетельство, связывая именно этот schedule/input; full optimizer scientific performance не выводится из tiny test.

### Проверенные owners на срезе
- policy-engine/src/polisyos/foundry/calibration/pure_executor.py: compile_program, _neutral_patch_map, apply_nodes, apply_nodes_batch
- policy-engine/src/polisyos/foundry/calibration/calibrator.py: Calibrator._build_bundle, evaluate_ordered_batch_objective, calibration report lifecycle
- policy-engine/src/polisyos/foundry/methods/components/merge_engine.py: existing merge rules

Если весь admitted catalog согласован, no-code accepted с native evidence. Новую общую patch-template способность вводить только на различающем admitted mismatch; blanket запрет vmap, all inactive evaluation или отключение finiteguards недопустимы.

## 6. Локальная приёмка — все будущие проверки NOT_RUN

### TEST-CAL-05-01
- Уровень: P-JAX native transforms + runtime callback.
- Setup: Existing instrumented log mechanism with jax.debug.callback + effects_barrier, keyPRNGKey(11), schedule[1,1], inactive0 and active2; shared schedule and per-row[0,1].
- Действие: Run eager,jit,grad,hessian,vmap(jit); then apply_nodes_batch/lax.map; remove mapped-predicate admission as diagnostic negative control.
- Точный oracle: Inactive value0/gradient1/Hessian0, unchanged key, runtime callbacks0 even when tracing occurred; active2+log2/1.5/−.25 and actual derived key. Mapped schedules including equal array refuse numerical emissions0; scalar map returns aligned inactive/active rows. Removed guard must expose unwanted emissions even if numbers finite.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-CAL-05-02
- Уровень: unit + targeted native integration.
- Setup: Current registry census with actual receiving states and compile templates; canonical IncomeTax float32, selector age>=30; four mergekinds, dependency and independentwriters, multiple-record/dtype candidates from catalog.
- Действие: Native eval_shape/cond structure controls and active/inactive execution; unknown selector compile; branch contract mismatch negative fixture.
- Точный oracle: Tax gradient[1,.9]; patch signatures exactly agree for admitted cases or explicit current admission refusal with supported positive alternatives. Inactive four mergekinds identity; dependent sees[5,5], independent base2 yields9. Unknown selector refuses at compile despite inactive schedule. Census gaps remain named, not universal PASS.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-CAL-05-03
- Уровень: native tiny calibration + shared persistence.
- Setup: Tiny actual Calibrator inputs using same tax program income[100,200], rate.1, selected secondagent, taxactive t1; independentreader active t0/t1; explicit observed targets and actual store lifecycle reused with LANE-10.
- Действие: Build bundle, execute forward/loss; ordered-row variant; persist report+input/config refs and fresh read; change schedule or target binding negative.
- Точный oracle: t0 incomes[100,200]/revenue0; t1[100,180]/20; t2[100,200]/0 for independent reset-row setup (not cumulative scan). Ordered loss equals direct MSE of aligned scalar predictions with recorded weights; invalid dynamic target→inf/validFalse. Report retains exact input/schedule basis, changed binding not treated same evidence; synthetic output role explicit.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

Повторно использовать/расширить реальные места, а не создавать 127 harness: `policy-engine/tests/unit/foundry/calibration/test_pure_executor_semantics.py`; `policy-engine/tests/unit/foundry/calibration/test_ordered_batch_calibration.py`; `policy-engine/tests/unit/foundry/calibration/test_calibration_lifecycle.py`. До выбора selector прочитать полный test/fixture. Это проверенные пути, не утверждение о наличии всех предложенных assertions.

Допустимые doubles: tiny instrumented mechanism наблюдает runtime callback; explicit independent-row states. Запрещено: NumPy/JAX shim в numerical acceptance; Python counter как единственный numerical non-execution oracle; synthetic observations как empirical truth.

## 7. Общая интеграция и порядок

CAL-05 принадлежит LANE-04, numerical/lifecycle evidence координировать с LANE-10. Один native semantics job и один shared tiny calibration consumer; не копировать большой optimizer harness на пакет.

Точные общие сценарии: E02-I04-D из [контракта интеграции](../03_Интеграция/LANE-04.md); одно свидетельство переиспользуется по неизменным input/backend bindings. Зависимости: нет обязательного нового предшественника; исходный DAG — ориентир, работающий контракт может удовлетворять ребру без нового ремонта. Общие файлы из §5 интегрировать последовательно с затронутыми owners; lane не новый runtime-реестр и не требование полного CI после каждого пакета.

## 8. Совместимость, история, rollback

Существующий mapped-schedule refusal — ограничение поддержанного профиля, не permanent ban на будущую доказанную batching implementation. Рабочий shared-scalar vmap и scalar-map positive route обязателен. Schedule boundaries inclusive start/end, structural validation не исчезает при inactivity.

## 9. Free-grow и design direction

- Условно полезный simulation/calibration output допустим без scientific authority; target basis сохраняется отдельно.
- Общее declared producer contract позволяет новые совместимые механизмы без ветки по названию, а несовместимость требует общего обоснованного расширения.

Архитектурные источники: [policyos-identity-and-custody-boundary.md §1, §3–6](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md); [policy-design-custody-time-model.md §2–5](../05_Основания/Архитектура/policy-design-custody-time-model.md). Историческая подлинность и текущая пригодность раздельны; физический layout design-docs не догма.

## 10. Нерешённые решения и передача

Новых блокирующих продуктовых решений не требуется. Реальную доступность supported runtime установить до native проверки; недоступность оформлять NOT_RUN, не PASS.

Предъявить patch/base SHA (либо обоснованный no-code результат), актуальную карту callers, REQ→TEST→evidence, фактические команды/логи, различающий контроль и сохранённые инварианты. Поддержанный native профиль: P-CORE (Python >=3.14,<3.15 и project lock); для native численных/JIT/train проверок P-JAX (тот же lock, JAX/jaxlib/optax, deterministic tiny CPU); для процессов P-PROCESS, для поставки P-PACKAGING. Не устанавливать зависимости без отдельного разрешения. Fixture/source-only, исторические PASS и отсутствие ошибки при импорте не закрывают свежий producer→persistence→fresh-reader. Успешная сериализация/конверсия/подпись не доказывает научной истины или полномочия policy result. Никакое требование/тест этой карточки ещё не исполнены.


Полные probes исходного аудита доставлены отдельно в phase1 ZIP; ссылки аудита на них не означают включение тяжёлой evidence в этот исполнительский комплект.
