# SIM-03 — Связанный контраст и честная численная неопределённость

> Предложение review-v2: только спецификация; product implementation и все TEST остаются NOT_RUN. Основание: PS-F04, PS-F08.

**LANE-01 · B19, B21, B23, B25, B26 · ТЗ исполнителю; все TEST — NOT_RUN.**
База `20d9009be21097bfbdc38a546a15cc60213b8ace`; [неизменённый аудит](../05_Основания/Аудит/02_Пакеты/SIM-03.md), [исходная карточка](../05_Основания/Аудит/05_Источники/SIM-03_исходные_строки.txt), строки 1289–1443.
**Практический результат:** Пользователь получает действительно выполненное модельное сравнение и проверяемые samples/ошибку; SMM не выигрывает потерей момента, а joint interaction не объявляется свойством всего мира.
Типы работы разделены ниже. Уже существующий механизм не переписывать только ради diff; qualify означает реальный запуск/потребление, capability — построение недостающего положительного пути.

## 1. Сохраняемые свойства

- Missing baseline не равен нулю
- None/empty evidence различимы
- Projection effect проверяется отдельно от raw identity
- Реальный цикл по seeds и сохранённые samples
- n=1 даёт None/standard_error_not_estimated
- Неполная группа не маскируется меньшим знаменателем
- Один физический набор на несколько ролей
- Seed/plan/evidence участвуют в физической идентичности
- Нет слияния разных запросов в текущем invocation-local кэше
- Required set неизменен в сравнении
- Отсутствующий repeat-момент не выбирается победителем
- Optional counts/status передаются caller
- Тройной residual не теряется за парами
- Zero mean при variation не объявлен additive
- Для 4+ только aggregate residual, без глобальной additive гарантии
- Защищённые различения: релевантные candidate/authority, input/result, historical/current различия из отчёта. S08: новую совместимую конфигурацию проверять на том же механизме, а не ветке по ID кейса.

## 2. Полнота исходных обязательств и остатков

| Основание | REQ | Disposition / решение |
|---|---|---|
| audit-residual:C10_остатки:0 | REQ-SIM-03-01 | fix: Finite helper/adapter and consumer guard. |
| audit-residual:C10_остатки:1 | REQ-SIM-03-05 | fix: Уникальность effective IDs до lossy dict. |
| audit-residual:C10_остатки:2 | REQ-SIM-03-02 | capability: Реальное model-bound положительное сравнение. |
| audit-residual:C10_остатки:3 | REQ-SIM-03-06 | capability: Конечный numerical/inference profile; не снятие variation guards. |
| audit-residual:C10_остатки:4 | REQ-SIM-03-03 | qualify: Retained interruption и specific SIM-02 reason. |
| B19 | REQ-SIM-03-02 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B21 | REQ-SIM-03-01, REQ-SIM-03-03 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B23 | REQ-SIM-03-04 | qualify: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B25 | REQ-SIM-03-05 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B26 | REQ-SIM-03-06 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| remaining:0048 | REQ-SIM-03-02 | capability: Положительный model-bound comparator, не просто status test. |
| remaining:0049 | REQ-SIM-03-02, REQ-SIM-03-06 | qualify: Actual CAS/conditional consumer без authority upgrade. |
| remaining:0052 | REQ-SIM-03-01 | fix: Finite на всех численных этапах. |
| remaining:0053 | REQ-SIM-03-03 | shared: SIM-02 exact cause; current retained test expectation. |
| remaining:0054 | REQ-SIM-03-01, REQ-SIM-03-03 | qualify: Native adapter/replication/readback. |
| remaining:0057 | REQ-SIM-03-04 | qualify: Selected ref и changed projection. |
| remaining:0058 | REQ-SIM-03-04 | qualify: Invocation-local scope, не global cache. |
| remaining:0062 | REQ-SIM-03-05 | fix: Moment uniqueness до dict. |
| remaining:0063 | REQ-SIM-03-05 | qualify: Native adapter и optional diagnostics. |
| remaining:0064 | REQ-SIM-03-06 | qualify: Actual model/consumer. |
| remaining:0065 | REQ-SIM-03-06 | capability: Declared tolerance/units/inference, no weakened guard. |

## 3. Нормативные REQ и конкретное решение

### REQ-SIM-03-01 — fix
Парный Monte Carlo не возвращает nonfinite endpoint/difference/mean/SE как estimated; singleton сохраняет SE=None. Supporting NCM normal quantile детерминирован и не расходует auxiliary global RNG, interval claim имеет явный bounded scope.

**Решение на существующих владельцах.** В existing paired_monte_carlo_effect проверить каждый requested metric endpoint до subtraction, разность после операции, mean и sampleSE после aggregation. Использовать finite-aware stable arithmetic где применимо, но overflow не обрезать и не превращать в0. Ошибка имеет metric/seed/stage и проходит existing coupled adapter/retained cause contract SIM-02. Dataclass/output должен отвергать forged estimated nonfinite при входе consumer, не рассчитывать на JSON failure. В NCMEngineMethod.pure_step заменить percentile от100000 global normal draws на deterministic floating-point inverse-normal из stdlib statistics.NormalDist либо already-locked SciPy. Проверить finite0<confidence<1 и поддержанный numerical profile; использовать stable lower-tail -NormalDist().inv_cdf((1-confidence)/2) или norm.isf((1-confidence)/2), не upper probability с округлением к1. Legitimate world-noise draws остаются в request-owned RNG; auxiliary quantile sampling не выполняется и ambient RNG не меняется. По DEC-SIM-03-02 явно ограничить interval estimand, ddof0/singleton и tiny-level boundary: deterministic quantile не автоматически calibrated CI. Если positive tiny confidence при float projection даёт tail0.5/неразличимый z, не выдумывать qualified zero-width interval. Где actual result contract позволяет, сохранить useful mean/trajectory/n и paired endpoints, ограничив interval; иначе выбрать explicit compatibility/versioned projection, не blanket отказ всей simulation. Old interval bytes не переинтерпретировать.
**Приёмка:** TEST-SIM-03-01.

### REQ-SIM-03-02 — capability
Один supported estimand должен иметь фактически исполненный model-bound comparator с согласованными scope/horizon/units/evidence и paired identity; caller ref или вычитание scalar не establishes basis.

**Решение на существующих владельцах.** Расширить existing request/result comparator projection у N5: для выбранного paired conditional contrast использовать existing paired_monte_carlo_effect и same-model baseline/policy calls с общими seeds, отдельным explicit evidence. Persist comparator request/input/result refs и declared estimand, model/WMR/time/outcome/units и версии; consumer перечитывает и сравнивает. Только покрытый profile повышает effect_basis/comparator status. Остальные caller-baseline arithmetic остаются not_established. Уровень outcome и counterfactual при evidence не принуждать к популяционному baseline-run.
**Приёмка:** TEST-SIM-03-02.

### REQ-SIM-03-03 — qualify
Requested replications совпадают с actual seed work/samples; native stochastic qualification содержит различающую seed-sensitive numerical variation, interruption сохраняет выполненные роли без ложного полного aggregate.

**Решение на существующих владельцах.** Сохранить _replication_seeds/_run_cached_replicates/aggregate DTO checks. Исправить test_replication_failure_aborts_before_an_aggregate_result_exists на retained-result contract, не generic no_run. Specific failure producer единый SIM-02; planned/completed/failed seeds и paired alignment остаются в result. Наблюдающая wrapper делегирует actual backend. Fixed-evidence integer model в TEST-SIM-03-02/06 остаётся точным deterministic comparator/joint oracle, но не самостоятельным свидетельством stochastic seed propagation. Добавить поддержанный actual NCM noise-sensitive profile через existing noise_expression и unobserved outcome noise; сохранить per-role raw samples и seed-to-draw association. Observer wrapper делегирует настоящий numerical owner, не возвращает готовые effects. Независимый oracle вычисляет paired differences/mean/SE по actual draws. Distinct labels/call counts без численной различимости не закрывают stochastic claim; малое число draws — software witness, не population coverage/power.
**Приёмка:** TEST-SIM-03-03.

### REQ-SIM-03-04 — qualify
Одинаковая physical specification внутри одного invocation может обслуживать несколько roles, но иной seed/plan/evidence не cache-hit; effect projection проверяется отдельно от raw identity.

**Решение на существующих владельцах.** Сохранить local cache, полный key модели/plan/runtime refs/horizon/outcomes/evidence/seed/atoms; role не включать, когда физика одинакова. Использовать existing test_physical_run_identity_binds_seed_and_plan_and_reexecutes_each_request и fixed_evidence_changed_baseline_rebinds_effect_on_fresh_cas. Не делать persistent cross-run cache ради B23.
**Приёмка:** TEST-SIM-03-04.

### REQ-SIM-03-05 — fix
Effective moment IDs должны быть уникальны до dict(zip) и producer; SMM сравнивает все candidates на заранее объявленном required set с полными repeat denominators.

**Решение на существующих владельцах.** В CoupledSMMEstimator.pure_step проверить normalized moment identities/length/finite observations до словаря и _run_coupled_policy; использовать existing required-moment validation, не новый SMM. Разные координаты одноимённого display label требуют distinct full IDs; repeated observations нуждаются в declared aggregation, last-write не правило. Сохранить optional diagnostics counts и no_comparable/best_paramsNone.
**Приёмка:** TEST-SIM-03-05.

### REQ-SIM-03-06 — capability
Joint classification должен учитывать фактический полный joint residual, общий seed denominator, scale/units/tolerance и заявленную область inference; authored compound требует actual совместного расчёта.

**Решение на существующих владельцах.** Сохранить _higher_order_residuals_from_fields/_paired_replication_summary и bounded finite_checked_model_point_estimate_only. Явно версионировать tolerance policy для выбранных units/scale; deterministic numerical tolerance не stochastic significance. Если нужен stochastic decision, выбрать обоснованный existing estimator/inference profile и тест coverage; до этого positiveSE остаётся unsupported, не arbitrary cutoff. CYC-05 поставляет authored relationships, здесь actual combined intervention/model comparator и independent joint oracle. Для4+ aggregate_order_three_plus не global additive.
**Приёмка:** TEST-SIM-03-06.

## 4. Локальные различающие тесты

Все номера TEST ниже — проектируемые проверки, не вымышленные имена существующих pytest-функций. Существующие файлы использовать/расширить; старый mutation или контролируемое удаление проверяемого механизма должен давать отличающийся исход.

### TEST-SIM-03-01 · NOT_RUN
- **Setup:** Actual paired helper и CoupledPairedMonteCarloEstimator; finite differences[1,3], singleton, constant[2,2,2], NaN/±inf, ±1e308 overflow, aggregate overflow. Дополнительно actual NCM variable-noise profile n_samples>1 и n_samples1; confidence0.50/0.80/0.95/0.99, near1=nextafter(1,0), tiny positive=nextafter(0,1), invalid0/1/out-of-range/NaN/Inf. Точный interval/compatibility profile фиксируется DEC-SIM-03-02 до приёмки; несколько levels нужны против constant z=1.96.
- **Действие:** Вызвать native helper/adapter, persist/read допустимый result. Boundary endpoint injection допустим локально; numerical native positive остаётся actual. Повторить один и тот же NCM request seed при разных ambient legacy NumPy RNG states; сохранить состояния до/после. Spy/trap запрещает только auxiliary global np.random.standard_normal для quantile, а request-owned rng.normal model simulation остаётся настоящей. Независимый normal CDF/erfc либо high-precision reference проверяет z по заранее объявленной dtype bound, не тем же inverse helper.
- **Oracle:** Finite[1,3]→mean2,SE1; n1→None/not_estimated в paired helper; invalid numerical этап адресно отказан, никогда estimated NaN/Inf. При поддержанных confidence levels quantile конечен, соответствует independent CDF/tail oracle и меняется с confidence; hardcoded1.96 не проходит. Near1 lower-tail остаётся finite, upper-probability rounding не выдаёт inf. Same request seed воспроизводит numerical world summaries/CI, исключая объявленный elapsed-time diagnostic; ambient RNG не изменяется,100000 auxiliary draws отсутствуют, legitimate world draws сохраняются. Invalid confidence не рождает qualified interval. Tiny-level unrepresentability и singleton ограничивают interval по DEC, а не объявляют ложную certainty и не уничтожают полезные mean/trajectory/n при совместимой projection.
- **Positive / negative / boundary:** Constant finite observedSE0 не мировая certainty; incomplete draws не уменьшают знаменатель. std ddof0 и n1 zero-width legacy summary не автоматически sample-error/coverage qualification; явный status/compatibility profile, не новый inference framework. Supporting quantile repair не меняет paired endpoint mean/samples и не ослабляет positive-SE interaction guard.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-SIM-03-02 · NOT_RUN
- **Setup:** Реальный зарегистрированный NCM через существующий structural_equations/noise_expression producer: y = u + 2*a + 3*b + k*a*b, k=4; a,b baseline 0, policy a=1 и/или b=1; horizon один step, y в declared outcome units, a/b dimensionless. Float64, Для каждого u∈{0,1,-1} передать actual evidence a=0,b=0,y=u через существующую evidence/abduction границу NCM: она устанавливает exogenous residual u; тот же exact evidence и paired seed использовать в baseline/intervention. В test проверить resolved evidence и abducted residual; один ExogenousSpec/seed сам по себе не фиксирует Gaussian draw этими целыми числами. No-op отдельный вызов с a=b=0. Не подставлять готовые effects в engine/result.
- **Действие:** Выполнить baseline/policy, сохранить оба основания, свежий N5→CAS→conditional consumer; заменить comparator model/time/seed/evidence.
- **Oracle:** Независимая подстановка даёт no-op=0, effect A=2, B=3, joint=9, interaction=9-2-3=4 для каждого u; при k=0 joint=5 и residual=0. Малые целочисленные +/* в float64 точны: expected integers сравниваются точно в этом контроле; rounding/stochastic/general model tolerance им не определяется. Mismatched comparator model/time/seed/evidence rejected либо basis not_established, не чужой established.
- **Positive / negative / boundary:** Missing baseline не0; None evidence и explicit{} различимы; changing baseline при fixed evidence меняет projection, не старую effect cache.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-SIM-03-03 · NOT_RUN
- **Setup:** tests/unit/remediation/test_sim_03.py, два atoms и1/2/3replicates; tiny actual NCM, controlled second-draw failure. Дополнительный registered native profile noise_expression y=u+(2+u)*a, a=0 baseline/a=1 policy, declared units, float64 и evidence={} либо допустимый partial evidence, не фиксирующий outcome noise. Заранее объявленные actual request seed=7, replications=3 и существующий native schedule seed+index → (7,8,9), без нового seed-list API; per-role raw draw trace через наблюдающую wrapper, которая делегирует original noise/engine call. Проверить действительную ненулевую variation fixture; это software discrimination, не статистическая гарантия.
- **Действие:** Посчитать physical calls, изменить seeds, прервать вторую реплику либо следующую роль; CAS/new reader. Для noise-sensitive profile сопоставить seed→actual draw u→baseline/policy endpoints. Повторить mutants: backend всегда получает первый seed; first trajectory replay под новыми labels; baseline sample pairing переставлен; cache key потерял seed.
- **Oracle:** Для two-atoms distinct physical subsets3 →3/6/9calls; samples/seeds и счёт совпадают; incomplete aggregate не completed; prior full role сохранена. В дополнительном actual noise profile independent formula baseline=u, policy=2+2u, paired effect=2+u задаёт mean/SE вне product paired helper и проверяется fresh consumer. Actual draw variation и association отличают repeated-first-seed/replay; pairing mutation меняет expected SE даже при сохранённом mean. Никакого утверждения, что seed задаёт выбранные целые Gaussian u. Для отдельного local pairing sanity baseline[-1,0,1], policy[0,2,4] дают effects[1,2,3], SE=1/sqrt(3), reversed baseline→[-1,2,5], SE=sqrt(3); этот local arithmetic не заменяет native draw witness.
- **Positive / negative / boundary:** Outer loop реально исполняется, n_samples1 внутри не ошибка; role reuse не independent sample. TEST02/06 integer conditional oracles сохраняются без ослабления. Positive-SE joint classification остаётся unsupported до отдельного inference profile; stochastic witness не empirical truth и не global causal proof.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-SIM-03-04 · NOT_RUN
- **Setup:** Один/two atoms с actual producer counter; same evidence и baseline100/102 при rawY107; altered seed/variable map.
- **Действие:** Дважды исполнить отдельные requests, проверить role refs и readback каждого result, затем подставить первую effect projection как вторую.
- **Oracle:** Внутри invocation one/two atoms имеют1/3physical subsets на seed; оба roles refs сохранены; separate request reruns; effects7/5 и разные result refs.
- **Positive / negative / boundary:** Нельзя сливать независимые повторения по atom IDs; hash не scientific correctness.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-SIM-03-05 · NOT_RUN
- **Setup:** Duplicates(completed_count,completed_count) values0/100, reversed order; distinct coordinates; required easy/hard с missing hard в одном repeat; optionalcounts1/3vs3/3.
- **Действие:** Пройти actual adapter/helper, наблюдать zero expensive calls для malformed IDs; unique permutation и real small grid.
- **Oracle:** Duplicates адресно rejected до потери данных; unique input invariant к перестановке пар; incomplete не выигрывает, optional не влияет тайно на required objective.
- **Positive / negative / boundary:** Не подставлять произвольный finite penalty вместо inf sentinel; не запретить законные повторные display labels с разными identities.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-SIM-03-06 · NOT_RUN
- **Setup:** Реальный зарегистрированный NCM через существующий structural_equations/noise_expression producer: y = u + 2*a + 3*b + k*a*b, k=4; a,b baseline 0, policy a=1 и/или b=1; horizon один step, y в declared outcome units, a/b dimensionless. Float64, Для каждого u∈{0,1,-1} передать actual evidence a=0,b=0,y=u через существующую evidence/abduction границу NCM: она устанавливает exogenous residual u; тот же exact evidence и paired seed использовать в baseline/intervention. В test проверить resolved evidence и abducted residual; один ExogenousSpec/seed сам по себе не фиксирует Gaussian draw этими целыми числами. No-op отдельный вызов с a=b=0. Не подставлять готовые effects в engine/result. Затем additive control k=0; отдельная существующая three-atom модель y=x1*x2*x3 при baseline all0 и intervention all1 даёт third-order residual1. Дополнительные zero-mean ±1, missing seed, 4+ cancellation и unit-rescaling cases выполняются по DEC-SIM-03-01.
- **Действие:** Выполнить joint/singles/pairs с общими seeds, persist/read via actual consumer и сравнить явный tolerance profile.
- **Oracle:** Независимая подстановка даёт no-op=0, effect A=2, B=3, joint=9, interaction=9-2-3=4 для каждого u; при k=0 joint=5 и residual=0. Малые целочисленные +/* в float64 точны: expected integers сравниваются точно в этом контроле; rounding/stochastic/general model tolerance им не определяется. Third-order residual1 не additive; missing samples/positive SE остаются unsupported; 4+ результат только aggregate_order_three_plus. Scale-equivalent oracle и допуск устанавливаются до запуска по DEC-SIM-03-01.
- **Positive / negative / boundary:** Не экспоненциальный перебор и не глобальная causal truth; authored compound не сумма independently evaluated alternatives.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

## 5. Общее испытание, зависимости и ownership

Общие сценарии: **E02-I01-A**, [определение LANE-01](../03_Интеграция/LANE-01.md). Исполнять только затронутый маршрут; CP — координационная приёмка, не новый runtime registry и не обязательный запуск всего CI.
- SIM-02 owns exact cause/temporal contract; SIM-03 does finite/statistics/comparator/interaction.
- CYC-05 owns authored relationships, SIM-03 owns actual joint numerical semantics; neither soleowner всего compound meaning.
- CYC-02 exposes conditional result; no empirical/N9 proof от этой приёмки.

## 6. Порядок и совместимость

Сначала воспроизвести на pinned baseline адресный контракт/дефект; затем один writer меняет общий owner, сохраняя callers и исторические readers. Поведенческий delta и перенос/cleanup описать раздельно. Не переписывать immutable старые artifacts: новая интерпретация получает явную version/basis. Rollback не переименовывает новые результаты как старые; reader обязан либо сохранить корректное чтение, либо дать точное unsupported/version ограничение. Команды и selectors проверить в checkout перед запуском, dependency install согласовать с общим исполнителем среды.

## 7. Design alignment и полезная способность

[System Vision, §6 Capability Reality Bar и §5 Rule12](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md): полный producer→persisted artifact→bridge→consumer; новый совместимый ресурс проходит общий механизм. Это не запрет нового общего кода для новой семантики. [D0 B-on-A](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md), раздел «D0 — Decision: B-on-A, Shadow-First»: полезная кандидатная работа допускается без автоматического полномочия. [Stage0 §4.3 K06](../05_Основания/Архитектура/stage0-custody-kernel-ratification.md): неизвестность ограничивает затронутое действие, не всё исследование.

Positive capability — один реальный правильный контраст и совместный эффект, а не только отказ сомнительным числам. Новая совместимая модель через общие estimand/plan contracts расширяет проверяемый envelope.

## 8. Ограниченные решения

**DEC-SIM-03-01**: Каков ограниченный numerical tolerance profile для noninteger/unit-rescaling fixtures и поддержанного NCM backend? Owner: SIM-03, согласование numerical owner. Варианты: analytic absolute bound из float dtype, числа операций и scale с отдельно заданными единицами; существующий model-specific numerical error contract, если его assumptions совпадают. Выбор по: До execution зафиксировать dtype, model expression, units, horizon, sample count и независимый high-precision/algebraic oracle; выбирать минимальную обоснованную bound, не cutoff по удобному observed output. Stochastic significance требует отдельного inference profile, не numerical tolerance. Обязательный выход: Таблица fixture→formula/input→exact expected→derived bound и различающий mutation. Пока profile не выбран, соответствующие scale cases BLOCKED/NOT_RUN, packet не принят; integer additive/interaction controls уже полностью определены.

- **DEC-SIM-03-02**: Каков bounded interval estimand и совместимая unavailable projection для native NCM summary после deterministic quantile repair? Owner: SIM-03 / existing NCM numerical-summary owner и actual interval consumers; согласование с общим CAU-01 confidence-domain правилом, без нового framework. Варианты: Сохранить legacy numeric summary только как явно неквалифицированную descriptive projection, добавив существующий limitation/status boundary; Versioned summary с nullable/unavailable interval и объявленным Monte Carlo error profile при достаточном основании; mean/trajectory/n сохраняются. Выбор по: Actual consumer/DTO census: где CI читается и где используется только mean; существующие n_samples1, std ddof0 и sampling assumptions; precision для confidence0.50/0.80/0.95/0.99, nextafter(1,0) и tiny positive levels; legacy reader/version migration и независимый CDF/erfc residual. Обязательный выход: Один bounded interval definition, sample-variance/singleton policy, поддержанный numerical confidence profile и versioned/legacy-unqualified projection. Для n1 или tiny confidence, когда float tail округляется к0.5 и positive quantile не различим, interval не квалифицирован, но где contract позволяет mean/trajectory/n и paired endpoint сохраняются. Если текущая schema не умеет unavailable interval, выбрать явную compatibility/versioned projection, не unconditional отказ всей simulation. Deterministic inverse-normal устраняет auxiliary random work, но сам не доказывает coverage; не менять весь inference framework.

## 9. Проверенные текущие пути

- [policy-engine/src/polisyos/foundry/coupling/estimation.py:438–470](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/coupling/estimation.py#L438-L470) — `def paired_monte_carlo_effect`.
- [policy-engine/src/polisyos/foundry/methods/catalog/simulation/coupled.py:353–385](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/simulation/coupled.py#L353-L385) — `class CoupledSMMEstimator`.
- [policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py:4438–4470](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py#L4438-L4470) — `def _higher_order_residuals_from_fields`.
- [policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py:908–940](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py#L908-L940) — `def _effective_evidence_state`.

- [policy-engine/src/polisyos/foundry/methods/catalog/causal/ncm_engine.py:1045–1138](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/ncm_engine.py#L1045-L1138) — NCMEngineMethod.pure_step local model RNG and global quantile sampling.

- [policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py:2880–2907](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py#L2880-L2907) — actual NCM per-replica dispatch.

- [policy-engine/tests/unit/foundry/methods/catalog/causal/test_ncm_engine.py:524–559](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/methods/catalog/causal/test_ncm_engine.py#L524-L559) — existing actual pure_step tests: keys/finite mean, no CI/RNG oracle.

## 10. Точная preservation-трассировка

| Inventory ID | REQ / TEST | Смысл |
|---|---|---|
| preserve:0062 | REQ-SIM-03-02, TEST-SIM-03-02 | Missing baseline не равен нулю |
| preserve:0063 | REQ-SIM-03-02, TEST-SIM-03-02 | None/empty evidence различимы |
| preserve:0064 | REQ-SIM-03-02, REQ-SIM-03-04, TEST-SIM-03-02, TEST-SIM-03-04 | Projection effect проверяется отдельно от raw identity |
| preserve:0067 | REQ-SIM-03-03, TEST-SIM-03-03 | Реальный цикл по seeds и сохранённые samples |
| preserve:0068 | REQ-SIM-03-01, REQ-SIM-03-03, TEST-SIM-03-01, TEST-SIM-03-03 | n=1 даёт None/standard_error_not_estimated |
| preserve:0069 | REQ-SIM-03-03, TEST-SIM-03-03 | Неполная группа не маскируется меньшим знаменателем |
| preserve:0072 | REQ-SIM-03-04, TEST-SIM-03-04 | Один физический набор на несколько ролей |
| preserve:0073 | REQ-SIM-03-04, TEST-SIM-03-04 | Seed/plan/evidence участвуют в физической идентичности |
| preserve:0074 | REQ-SIM-03-04, TEST-SIM-03-04 | Нет слияния разных запросов в текущем invocation-local кэше |
| preserve:0080 | REQ-SIM-03-05, TEST-SIM-03-05 | Required set неизменен в сравнении |
| preserve:0081 | REQ-SIM-03-05, TEST-SIM-03-05 | Отсутствующий repeat-момент не выбирается победителем |
| preserve:0082 | REQ-SIM-03-05, TEST-SIM-03-05 | Optional counts/status передаются caller |
| preserve:0083 | REQ-SIM-03-06, TEST-SIM-03-06 | Тройной residual не теряется за парами |
| preserve:0084 | REQ-SIM-03-06, TEST-SIM-03-06 | Zero mean при variation не объявлен additive |
| preserve:0085 | REQ-SIM-03-06, TEST-SIM-03-06 | Для 4+ только aggregate residual, без глобальной additive гарантии |

## 11. Что предъявить и что не считать PASS

Предъявить конкретные до/после assertions и actual affected consumer, сохранённые outputs/refs, failure controls, source identity и поддержанный runtime. Наличие кода, формы receipt, этого ТЗ либо старого зелёного теста не является выполнением. Local/source-excerpt observation не native acceptance; skipped/blocked остаётся видимым. Число или candidate output не повышается автоматически в empirical/decision authority. Согласовать полезный positive, не ограничиваться запретами. Полные исходные probes находятся в отдельно доставленном phase1 ZIP; текущая подготовка не создаёт нового product execution.

[Машинная трассировка](../04_Трассировка/SIM-03.json). Аудит охватил127/127; это не означает выполненных127 ремонтов.
