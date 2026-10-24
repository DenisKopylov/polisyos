# R16: исполнимые работы по композиции и пересчёту

Проект после фактической приёмки E02; runtime UNRUN. [Архитектура](../architecture/06-composition-and-reexecution.md), [качество](../assurance/10-composition-reexecution-quality.md), [исследовательские основания](../research/composition-reexecution-r16.md). Нового DES-13 или scheduler не добавляется: ниже конкретные delivery slices существующих задач. Источник требований — additive `r16_extension` в tasks/preferred-solutions; прежние критерии сохраняются целиком.

## Исполнимый сценарий и границы

Один case сочетает rule calculation, behavioral method, service-capacity model, joint fiscal calculation и criterion evaluator. Требуется пройти: selected native inputs → typed composition → actual execution → CAS → fresh joint/search consumer → claim/currentness и разрешённая поверхность. Затем поступают отдельно новое наблюдение, новый механизм и hypothetical forcing; каждый идёт своим корректным revision path. Ни один этап не заменяется изготовленным receipt.

Начинать с поддержанных native models и малых независимых оракулов. FMI/HELICS/удалённый backend подключаются лишь при выбранной неподдержанной property. Authentic model validation остаётся отдельной обязанностью; mathematical control не устанавливает социальную применимость.

<a id="C1"></a>
## C1. Исполнимая композиция и полный coverage — GYD-30, GYD-32

1. Rebind ProgramGraph/ExecPlan, actual graph/method-chain dispatch, портовые contracts и все selected consumers. GYD-30 принимает изменение shared joint bridge; GYD-32 проверяет actual substrate/free-grow, но не становится вторым writer registry/compiler.
2. Native compiler формирует exact producer→adapter→consumer bindings из выбранных contract profiles. Проверить required construct/unit/stock-flow/support/time/executable facets; missing required semantics не достраиваются по slot names. Отдельно material/candidate/authority meanings. Requiredness recomputed из exact versioned native producer/consumer/profile contracts; adapter declaration не может сделать требование optional. Resolve/content-bind owner contract и сохранить required-set provenance; missing/conflicting contract ограничивает соответствующую guarantee.
3. Проверить actual order как полный допустимый порядок selected plan: нет неизвестных, пропущенных или дублированных required nodes, все dependencies удовлетворены, dynamic nodes регистрируются через owning extension. Empty order либо корректно пересчитывается и связывается, либо typed refusal; не raw list fallback. Optional pruning имеет проверенное основание и входит в receipt.
4. Для supported zero-lag SCC создать native coupling block с internal identity/ports и внешним acyclic order. Existing DAG cycle refusal остаётся для неподдержанного цикла. Compiler/runner связывает actual map invocation closure с native subplan: frozen upstream boundary → block iterations/final residual → downstream materialization. Текущий callback вызывает весь ExecPlan; пока он не разделён, denominator purity/reset/effects/resources равен всему вызванному plan, не нарисованному SCC. Whole-plan repeat допустим только при подтверждённой repeatability каждого member; иначе scoped refusal/limitation. Full participant purity/reset/replay и final materialization fence обязательны; один flag сходимости не покрывает их.
5. Native result связывает фактический denominator active methods, adapters, skips/failures и гарантии каждого. Fresh GYD-30 consumer проверяет actual joint artifact; distinct IR/PDC certificate meanings не cast-ятся по имени.
6. Включить method-chain binding adapters и registry bootstrap, installed/public readers, schema/version migration. Existing conforming component подключается без central per-model branch. Если source rebind уже даёт свойство, wire+verify, не переписывать его.

**Проверки:** Q01–Q04/Q12/Q15. **Writer:** exact shared compile/execute/schema paths за GYD-30 после rebind; temporal adapter за DES-11. Общее core/contracts/foundry.py редактирует один назначенный writer, остальные передают requirements. **Миграция:** старый order/certificate остаётся историческим; непрочитанные семантические facets не считаются validated.

<a id="C2"></a>
## C2. Temporal/cyclic boundaries и state recovery — DES-11, GYD-30

Согласовать clock/step/event relations, initial state, sample-hold/interpolation и valid coupling profile. Distinguish solver iteration, virtual model time и реально доступную observation history. Step rejection/restoration охватывает всех затронутых participants; pure map не обязан иметь mutable checkpoint. Для opaque stateful member без reset/replay поддерживается только та one-shot/temporal граница, которую он действительно может выполнить.

Checkpoint eligibility включает state schema, participant closure, exact inputs, code/backend, RNG/frontier и mapping. Native chain checkpoint с matching digest не объявляется incremental evidence-update algorithm. Changed initial state/structural mechanism запускает verified migration или новый replay; warm start — только guess. После late observation пересчитать affected suffix от совместимого checkpoint, сохранив прежний as-of result.

**Проверки:** Q03/Q04/Q05/Q10/Q14. Для expected-response profile single sampled residual/`noise_sd` не stopping proof: использовать validated stochastic rule или typed limitation. Варьировать timestep вокруг ненулевого flow; не выдавать уменьшение шага или сходство h/h2 за universal error bound. **Параллельно:** stateless DAG и independent temporal adapters; сериализуется именно shared state/master/write path, не все models. Multi-clock adapter расширяется только под конкретный clock/event/recovery claim.

<a id="C3"></a>
## C3. Exact influence, cache и conservative fallback — LIF-07, DES-03

1. Расширить existing manifest/lineage и actual executor input resolver. Различать declared possible inputs, actual reads и negative/membership dependencies: отсутствующий FX key, каталог источников, результат query/no-result, selection/pruning basis, model law/code/config.
2. Bind cache entry к computational basis и producer/profile; отдельно проверить current-use rights/purpose/audience/semantic admissibility. Run-ID-local retry cache не расширять до cross-run cache удалением run_id без нового identity proof. Не объявлять ABI executable identity.
3. Change plan выбирает affected closure + demanded outputs, source-derived coverage. Если completeness read-set не установлена, exact selective hit недоступен; clean recompute в охваченном scope допустим. Не подменять unknown dependencies пустым множеством.
4. Два native пути: unaffected exact reuse и fresh evaluation. Owner-specific delta update — отдельная условная оптимизация с insert/correct/retract semantics. Для SCC по умолчанию единица пересчёта весь coupled block; для temporal chain — affected suffix.
5. Проверить pruning по полной consumer-facing semantics, включая support/selection/guarantee/provenance. Равенство числа не отсеивает rights/currentness cascade. Approximate pruning только при contract-bound downstream error bound; иначе fresh calculation.
6. Сохранить permitted dependency/read receipt и причину reuse/recompute/miss; публичная проекция не раскрывает private membership/hash. Fresh result соответствует независимому clean recompute при той же selected guarantee.

**Проверки:** Q06/Q07/Q08/Q11/Q16. **Граница записи:** LIF-07 владеет общей influence/reuse relation; actual Foundry cache reader — GYD-30, Scientist search reader — DES-03. Один adapter contract не создаёт второго графа lineage. DES-03 получает LIF-07 `interface_agreement` для подготовки; actual supplier output обязателен для composed cache acceptance.

<a id="C4"></a>
## C4. Source change, semantic epoch и immediate claim reaction — CAP-04, LIF-02

Использовать actual semantic-epoch producer/registries и native claim owner. Semantic epoch не выполняет graphs. Incomparable semantic heads сохраняют contested boundary; нельзя разрешить их выбором последнего wall-clock timestamp. New observation cut, structural candidate, scenario branch и authority/purpose context связываются раздельно.

CAP-04 доставляет typed events/positions; LIF-02 выполняет enrollment/replay-floor/currentness и publication fence. Между cut C и enrollment high-water W нужен фактический replay; если history ниже replay floor, current claim не получается от пустого replay. Native source incarnation отличает reset offset от прежнего. Source cut vector допускает независимые generations только при проверенном выбранном consistency scope; нельзя считать несколько snapshots одной транзакцией.

Обязательная первая реакция — честный affected-use status до окончания дорогого rerun. События не теряются при dedupe, crash или coalescing. Authority-only change может не менять расчёт: old numeric artifact остаётся историческим/переиспользуемым при законном use, но прежний admission не переносится. Public reaction не зависит от наличия compute slot.

**Проверки:** Q08/Q09/Q11/Q13. **Параллельность:** source adapters и claim readers после согласования interface; exact current-head writer один. Это не новая source cursor implementation: LIF-03 сохраняет свой owner.

<a id="C5"></a>
## C5. Реальный rerun, а не только invalidation — DES-04, DES-03, LIF-04

Preferred behavior: для активного case допускается зарегистрированная bounded reevaluation duty с exact candidate branches/output goals, change selectors, scope/rights и ресурсной политикой. Для выбранной duty material input change должен **фактически** привести к durable continuation intent и actual fresh trial. Отсутствие standing duty означает visible stale/next-action request; нельзя обещать automatic rerun по одному LIF event. Historical closed case не запускает неограниченную simulation по каждому событию.

1. DES-04 связывает admitted change/counterexample/study-return с существующим generation-cycle request. LIF-04 обеспечивает intent/attempt/recovery, DES-03 — trial, GYD-30 — execution result. Existing owners согласуют smallest native boundary; передача event самому себе не test.
2. Для duty определить допустимое coalescing, demanded output, new-basis relation, cancellation/finish strategy, max outstanding work, deadline/fairness и terminal partial/pending surface. Никакой фиксированный global timeout или вечное «ждём последний update».
3. Каждый новый scenario/mechanism имеет immutable branch identity; transport retry той же операции остаётся attempt. Changed provider reply — новый evidence artifact, не новая independent study автоматически.
4. Stale completion связывается с historical basis и не проходит expected desired revision/head fence своего case/branch. Не блокировать независимые branches одним global current-result lock. Cancel/lease expiry не освобождает реально занятую capacity без reconciliation.
5. Для unsupported automated producer сохранять typed pending/limitation и конкретный next action; исполнителю сначала проверить существующий native route, а не объявить внешнюю причину у отсутствующего bridge.

**Проверки:** Q06/Q09/Q13/Q16. Удалить dispatch bridge при сохранённом dirty event — positive обязан не пройти. **Dependency:** LIF-04/02/07 contracts можно готовить до полного upstream delivery; automatic execution допускается только при actual emitted suppliers и required permissions/resources. Нет второго scheduler и нет нового top-level task ради orchestration.

<a id="C6"></a>
## C6. Evidence update, alternative mechanism и scenario — CNT-06/08, GYD-09/10/12, DES-08/12

Native target/causal owner отличает observation, intervention, mechanism rewrite и scenario. Новое evidence обновляет выбранную модель через likelihood/estimator, а scenario создаёт conditional prediction. Для последовательного Bayesian update нужен `p(D2 | theta, D1)`; сокращение к `p(D2 | theta)` требует conditional independence. Повторная derivative публикация D1 не новый factor. Для иных методов — собственные sufficient-statistic/dependence правила, не forced Bayesian wrapper.

Correction/retraction пересобирает evidence basis и affected inference. Из posterior summary нельзя обещать вычитание старого likelihood; при отсутствии supported inverse/update применяется lawful refit или limitation. Filtering и retrospective smoothing имеют разные information sets. GYD-10 discovery остаётся candidate, GYD-09 confirmatory update и GYD-12 world write-back подчиняются исходным WP activation decisions. Model output, learned memory и calibrated surrogate не создают независимую observation.

Новый механизм меняет structural program и нужные calibration/transport/identification obligations. Same baseline predictions не доказывают interchangeability under intervention. Сценарий может менять driver distribution/paths или механизм как явную гипотезу; probabilities не назначаются по умолчанию. Multiple model completions сохраняются; averaging только с qualified weighting basis. DES-12 предлагает исследование, если оно различает material alternatives; независимое новое evidence может изменить choice, но uninformative duplicate не обязан.

**Проверки:** Q02/Q10/Q11/Q12/Q17. Memory-off и held-out stress profile проверяют search utility отдельно от authority; comparison не подменяет исходный GY-AS2 contract. Реальное external trial/permission требуется только для такого утверждения, controlled internal chain выполняется независимо.

<a id="C7"></a>
## C7. Ограниченная стоимость и реальные adapters — LIF-06, OPS-08/09, CAP-06

Использовать existing aggregate resource owner и actual runner/provider contracts. Compile cost estimate одного graph не cap для всех multistarts/Jacobians/surrogate checks/restarts. Учитывать all actual calls, held permits, stored outputs/checkpoints, read/spill bytes и finalization/recovery reserve. Новые children получают долю общей capacity. Parent не ждёт child, удерживая недостающий ему ресурс: заранее резервируется feasible combined peak либо checkpoint/park действительно освобождает необходимую capacity. CPU yield не снимает RAM/disk charges; shared buffers считаются один раз по actual lifetime, copies — отдельно. Перенос reservation меняет владельца учёта, но не освобождает физическую память.

Новая native method family не требует нового scheduler. Remote/private adapter активируется только selected deployment profile; source rights, external side effects и returned participant denominator идут через CAP-06/LIF-04/05. State reset не отменяет charge/disclosure. Результат незавершённого обязательного member не заменяется default-zero или старым current value.

**Проверки:** Q04/Q13/Q14/Q15/Q16. Статус при exhaustion — incomplete/limited по native rules, не policy infeasible. Протокол измерения включает resident memory, work/CAS/read denominator и полезность результата; regression budget выводится из commissioned environment, а не числа из этой записки.

<a id="C8"></a>
## C8. Полный fresh consumer и производительность — DES-10, UI-06/08, DES-06

DES-10 координирует независимый oracle и matched controls всех selected slices в existing final wave. Individual owners сохраняют scoped positives/removal до freeze. UI-06 показывает comparison, uncertainty и basis deltas; UI-08 отображает actual learning/world revisions после owning emission; DES-06 формирует читаемое объяснение «что изменилось, что пересчитано, что reused, почему conclusion изменился/не изменился». Surface не вычисляет authority заново.

Сравнить selective execution с чистым native recompute **того же basis/profile**, не с result другого snapshot. Complete comparison denominator включает errors/timeouts/unsupported members и affected/unaffected nodes; не суммировать пересекающиеся test counts. Useful positive обязателен: система получает новый полезный conditional result или обоснованно сохраняет его, а не проходит всю suite сплошными отказами.

**Проверки:** Q01–Q17 по выбранным properties; optional methods активируют свои cases, не все libraries. API/generated/browser companions входят в native owner footprint. Historical artifacts не получают новые provenance задним числом. Отдельного широкого replay из-за R16 нет: readiness перед FINAL-FREEZE, reviewed identity перед существующим FINAL-REPLAY.

## Параллельный dispatch

C1 compiler/joint, C2 temporal adapter, C3 influence/cache, C4 event/currentness, C5 rerun request, C6 method/evidence, C7 resource/provider и C8 oracle/surface могут готовиться по согласованным interfaces. C1 и C2 сериализуют только пересекающиеся Foundry files; C3 и C5 не получают права переписывать LIF-02 head owner. Actual execution joins real outputs; ранняя подготовка на contract не является composed acceptance. [Conflict registry](../execution/conflict-groups.json) уточняется exact paths при rebind.

Original121 tasks сохраняются. Новые slices — единицы поставки внутри существующих tasks, а не 8 дополнительных engines или 8 независимых authorities. Все selected slice obligations должны попасть в readiness/final coverage; группировка не заменяет complete `r16_extension` denominator.

Pattern pass: P01/P02/P03/P05/P07/P08/P10/P13/P14/P17/P24/P25/P27/P29/P31/P32/P35/P37/P38/P40. Status/authority/currentness и scientific assumptions требуют настоящих owning consumers; marker-based completion не принимается.
