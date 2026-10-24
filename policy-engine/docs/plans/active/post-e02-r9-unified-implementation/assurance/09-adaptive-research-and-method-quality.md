# R15: проверять полезные свойства полного пути

План будущих проверок, **все продуктовые исполнения UNRUN**. Полный delta denominator — [r15-capability-obligations.json](r15-capability-obligations.json); additive task requirements — `tasks.json:r15_extension`. Оракулы/cases готовятся до freeze; дорогие композиции исполняются в единственной FINAL-REPLAY после FINAL-REVIEW. Native bounded checks при реализации остаются частью owner readiness. Исторические R13/R14 receipts не проверяют этот delta.

## DES-11: адаптивная стратегия

**Определяющий positive.** Независимо заданный finite world: A создаёт capacity с declared lag/cost; B расходует capacity и имеет необратимое окно действия; порядок A→B и B→A даёт разные outcomes. Это synthetic oracle, не социально-экономическая оценка реального эффекта. Реальные native operators/temporal executor, persistence и fresh frontier/dossier должны воспроизвести различие. Второй case требует дождаться доступного measurement, затем выбрать условный branch; сравнить с relevant fixed/no-op/delay strategies при общем initial state и declared objectives.

**Обязательные различения:**

- Nonanticipativity: два разных мира имеют одинаковую policy-visible history до t. При фиксированном policy randomization seed recommendation совпадает до t; позже может различаться. Scoring oracle с future truth не используется как доступный policy input.
- Backdated event получено/проверено после t: новая current recommendation может измениться, историческое knowledge state не переписывается. Positive gate по одному event_time недостаточен.
- Смена observation process, ложноположительный/noisy signpost, задержка measurement и hysteresis/необходимая устойчивость сигнала проверяются в выбранном profile; не назначать universal threshold или число подтверждений.
- Same new policy, different grounded incumbent load: изменяется feasibility/effect или имеется independent stability evidence. Неизвестный roster не превращается в «весь портфель проверен».
- Stop/replan сохраняет sunk cost, residual impact и external commitments; terminal horizon не скрывает material tail. Solver rollback не меняет actual act history.

Удаления по одному: temporal/history use, observation cutoff, incumbent binding, persisted-result consumer. Labels, counts и renderer сохраняются. Gate обязан заметить потерю соответствующего свойства; нельзя лишь проверять наличие «adaptive» в JSON.

## DES-12: различающее исследование

**Малый независимый оракул.** U — Bernoulli(1/2). M1: X=U, Y=X. M2: X=U, Y=U. В обоих наблюдаемых распределениях X=Y, но при do(X=1) среднее Y равно соответственно 1 и 1/2. При явной synthetic цене действия между 0 и 1/2 выбор действия относительно baseline может различаться. Producer получает сопоставимые model refs и разрешённое synthetic design space; он должен предложить различающее вмешательство/эквивалентное допустимое measurement с корректной analysis relation, либо объяснить отсутствие feasible discriminating design. Повторять исходные observational rows бессмысленно для различения этой пары. Конкретные две модели — проверочный case, не закрытый продуктовый каталог.

Result return проверяется отдельным owner-produced fixture через настоящий intake, protocol/analysis binding и fresh consumer. Отсутствие требуемой WP activation запрещает operative effect-posterior mutation и соответствующую routine assimilation; candidate conclusion может измениться. Structural assessment идёт отдельно через CNT-06 → единственный GYD-12 writer и его actual applicable structural-write rule: отсутствие WP не заменяет этот predicate. При отсутствии structural rule результат остаётся candidate/conditional; при его наличии qualified structural update проверяется своим fresh reader, без автоматической активации effect path. Повторить на варианте, где rival models расходятся, но все ведут к одному допустимому действию: высокий entropy reduction не обязан иметь positive decision value. Опциональная исследовательская цель может оставаться полезной сама по себе, но её нельзя подписать как пользу конкретному policy choice.

**Adversarial set:** assignment≠receipt и ITT≠receipt effect; cluster spillover; missing support/attrition; wrong population; off-target intervention; unlogged interim looks; post-outcome target switch; failed/null results omitted; study result после decision deadline; self-attested permission; конкурирующие модели не исчерпывают мир. Если метод не требует numeric propensity/power, отсутствие такого поля само по себе не является ошибкой. Если требует — оно не подставляется default.

Дополнительные обязательные cases: действительная permission для protocol v1/site A предъявлена для v2/sites A+B; revoke после planning до protected dispatch/resume. Native owner блокирует именно affected action/claim. В already-returned evidence разграничиваются правомерность current use и доказанность authorized conduct. Другой case удаляет substantive budget/prior/noise/assignment basis при сохранённых method-generated numeric fields: метод не получает grounded feasibility/power/EVSI от своих defaults. Явно declared hypothetical scenario остаётся разрешённым candidate; numerical solver defaults не запрещаются как класс.

Authorization checks выводятся из **всех load-bearing required facets actual native operation/authorization contract**, а не из перечня примеров выше. При неизменных valid grant/markers менять один required facet вне grant coverage; проверить также новый required facet у conforming extension. Recipient/population/intervention — примеры, не закрытый whitelist. Missing/unknown required scope не получает default. Это один generic owner coverage predicate; не лестница новых per-field gates. Отдельный evidence-use admission может допустить законно полученное evidence без утверждения authorized study conduct.

Remove discrimination calculation, leave model count/entropy; remove actual design→analysis→result binding; remove actual acquisition/fresh-consumer bridge. Соответствующий endpoint должен перестать удовлетворять property. Удалить optional EVSI при сохраняющемся обоснованном nonnumeric route — route остаётся работоспособным. Study permissions проверяются только перед соответствующим protected action; design generation не требует реальной организации для каждого synthetic case.

<a id="method"></a>
## R15-METHOD: гарантия каждого выбранного метода

Отдельно фиксировать (а) реальное исполнение, (б) математическую/численную корректность, (в) adequacy модели/измерения, (г) causal identification/transport, (д) decision/authority scope. Передавать в consumer именно допустимую гарантию.

| Выбранная технология | Positive / independent comparator | Атака при сохранённых markers |
|---|---|---|
| PPC/SBC/PPL | Малый аналитический posterior и заранее заданные диагностируемые искажения | SBC passes under wrong DGP, PPC misses untested discrepancy, narrow posterior чужой population; ни один не становится identified effect |
| MIP/CP/SMT | Исчерпывающий малый feasible/unsat case и recompute исходных constraints | Удалить constraint; неверный Big-M/scale; timeout≠UNSAT; hidden lexicographic public values |
| Multi-fidelity | Paired target/cheap evaluations, selected-case error and useful-search comparison | Boundary ranking reversal, low-fidelity-only validation, неучтённое pruning; high-fidelity numerical result≠world truth |
| Robust/partial ID | Known bounded model and assumption sensitivity | Empty/incompatible assumption sets; invented model weights; data narrows empirical uncertainty but does not settle normative conflict |

Эти строки — профильные обязанности при заявленном использовании, не требование установить все пакеты. Choice/deviation записывается в existing task journal. Новый guarantee без capable native consumer — capability incomplete.

<a id="measure"></a>
## R15-MEASURE: измерение, response и действующая среда

Для selected cases связать CNT-05/06/07, GYD-01/30/32 и actual value/frontier reader. Проверить совместные MNAR+linkage errors; scale/instrument/language invariance; границы geography и aggregation support; population composition и denominator; selection/gaming/behavioral change после политики. Не только warning: material case должен менять допустимый range/feasibility/choice либо иметь independent evidence устойчивости. Existing authentic near-miss и S6 obligations остаются отдельными, не закрываются synthetic test.

Измерять также ошибочный отказ: missing optional facet не должен блокировать несвязанную допустимую claim. Нельзя требовать causal model всего общества для локального statement, но нельзя расширять statement за проверенную границу.

<a id="learn"></a>
## R15-LEARN: adaptive exposure и возврат evidence

Native O1/O2/O3, sealed-data и lineage owners получают real assignment/exposure/receipt/measurement/protocol/policy version. Подставить старый label при новом regime; selective site/dropout; reused cohort; repeated peeking; outcome-driven metric selection. Подходящий selective/sequential inference может использовать те же данные в разрешённом scope — не требовать всегда новую выборку. Обычный interval при нарушенной схеме не получает прежнюю гарантию. Scope of actual WP activation проверяется отдельно; no-mutation refusal сохраняется до него.

<a id="private"></a>
## R15-PRIVATE: распределённое вычисление и disclosure

Когда selected profile требует federated/private/DP: source roster/support, duplicate sites, неодинаковое measurement, nonrandom dropout, wrong aggregate, current grants, shared disclosure composition, derived artifacts и uncertainty от privacy mechanism доходят до настоящего consumer. Положительный numerical case обязан оставаться полезным при разрешённых данных; negative запрещённого disclosure не исчерпывает функциональность. Secure aggregation не подтверждает representativeness/causal law. Ноль найденных extraction attacks не есть нулевая privacy leakage guarantee.

Нет universal privacy unit/epsilon; владелец источника и применимая выбранная law задают scope, mechanism owner проверяет гарантию. Неизвестное возможное раскрытие не возвращает reservation. Privacy/data-locality задача может завершить внутренний механизм на controlled profile, но authentic institution/site claims остаются явно unverified.

<a id="surface"></a>
## R15-SURFACE: что действительно видит пользователь

Fresh API/Atlas/document reader различает proposed conditional strategy, observed branch, future assumption, historical cutoff, currentness limitation, исследовательское предложение, внешнее разрешение и реальный результат. Он видит material alternatives, сопоставимые outcomes, неподдерживаемый scope и последствия остановки. Reader проверка не сводится к наличию вкладки или красивой временной линии; semantic questions задаются против exact artifact/version. Private evidence раскрывается только разрешённой аудитории.

<a id="quality"></a>
## R15-QUALITY: complete denominator и одна волна

DES-10 готовит controlled solvable/ambiguous/unsupported cases, independent oracle и genuine variants до final freeze. Назвать complete selected cases/branches/arms/seeds/models/sites/results, retries/errors/exclusions и criteria. Случайный seed не является independent empirical replication. Equal ceilings не требуют бессмысленно тратить остаток бюджета. No-op/removal arms не обязаны дать useful policy: это отрицательные comparators, а all-abstain implementation не проходит designated positive.

Количество задач/проверок не равно capacity. R15 добавляет задачи DES-11/12 и укрепляет 28 existing task objects; точный полный пересчёт и документарный validation receipt отделены от runtime результата. Product cases пока UNRUN. No implementation, tests, installations, builds or production reads during this documentation work.

Pattern pass: P01/P02/P03/P05/P07/P08/P10/P13/P14/P15/P17–P27/P29/P32/P35/P37/P38. Defining signal — полезный истинный native path вместе с содержательным falsifier; independence и authority никогда не следуют из авторского pass marker.

## Heterogeneous-model research delta

Для selected fixed-point composition добавить GYD-30 probes: whole-participant reset/replay eligibility и observed final-materialization residual/certificate binding; hidden state changes only on final run must not retain prior convergence authority. Scenario-conditional equilibrium не является expected-map equilibrium; diagnostic noise_sd не заменяет selected noise-aware method. OPS-08 считает полный map/Jacobian/multi-start/retry/final/CAS denominator. [Полный research dossier](../research/heterogeneous-model-execution.md) сохраняет static observations отдельно от future verification.
