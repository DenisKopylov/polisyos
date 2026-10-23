# R15: технические методы в полном цикле PolicyOS

Это implementation guidance, а не список обязательных библиотек. Каждая строка активируется заявленным свойством выбранного case; действующий метод переиспользуется, если он обеспечивает свойство. Новая зависимость допускается после owner census, оценки точности/ресурсов/лицензии и проверки более простого решения. Версии ниже — проверенные исследовательские ориентиры; исполнителю нужен свой exact executable/dependency pin на accepted source. Код не исполнялся.

## Общее правило интеграции

Native registry выбирает capability по задаче и предпосылкам → owner разрешает входы/units/population/time/rights → method dispatcher исполняет реальный метод → CAS/manifest сохраняет его связанный результат и diagnostics → existing joint/uncertainty/admission owner ограничивает claim → fresh N6/API/Atlas/document consumer показывает результат и существенные ограничения → lineage/currentness owner реагирует на изменения. Algorithm success, schema validity, content hash и method ABI сами по себе не подтверждают применимость или causal truth.

Для каждого выбранного профиля в task journal закрепить: вопрос и **зачем именно этот метод**, native writer, точные producer/consumer interfaces, метод/версию/assumptions, фактический input и executable identity, retained result versus recomputable scratch, бюджет/termination/fallback, uncertainty meaning, публичный смысл и distinguishing oracle. Это содержание существующих native records, не новый универсальный DTO. Приёмка содержит полезный positive, отрицательный case, matched removal и fresh consumer. Метод может вернуть bounded unknown без подмены этого состояния zero/false/UNSAT.

<a id="TP01"></a>
## TP01. Адаптивные пути и робастное сравнение — DES-11, DES-03/04, GYD-30/31

Предпочтение: finite conditional strategies поверх native temporal/world execution; signposts и adaptation thresholds связываются с наблюдаемыми величинами и допустимыми decision cutoffs. Scenario discovery объясняет области отказа; robust/regret/Pareto сравнение показывает зависимость от множества моделей/ценностей. Вероятности сценариев, единый minimax и discount rate не назначаются молча. Receding-horizon пересчёт учитывает выполненные обязательства, terminal effects и возможность неизвестного continuation; результат не разрешает внешнее действие.

Хранить policy rule, observation/transition assumptions, исходное состояние, кандидатные и фактические branches отдельно, chosen solver/profile и результаты по модельным предпосылкам. Не материализовать все длинные trajectories, если для claims достаточно проверяемых sufficient summaries и выборочного provenance; retention определяется воспроизводимостью, правами и требуемой диагностикой. Screening/beam search показывает отсечения; exhaustive optimum заявляется только на действительно проверенном конечном пространстве.

**Проверки:** A→B против B→A при одинаковых мерах; одинаковые наблюдения при разных latent futures; поздний/noisy signpost; horizon truncation; неотменяемый sunk commitment; competing incumbent load. Удаление history/observation cutoff меняет oracle verdict, даже если labels «adaptive» сохранены. [Dynamic Adaptive Policy Pathways](https://doi.org/10.1016/j.gloenvcha.2012.12.006) — основание подхода к последовательностям/условиям смены, не гарантия эффектов; [EMA Workbench](https://emaworkbench.readthedocs.io/en/latest/) — пример exploratory model analysis, не обязательный новый runtime.

<a id="TP02"></a>
## TP02. Active causal / decision-focused study design — DES-12, CNT-06, DES-04

Сначала различить задачи: обнаружить структуру; оценить конкретный эффект; выбрать политику при нескольких допустимых структурах; проверить measurement/implementation explanation. Выбирать дизайн по способности изменить существенный вывод при допустимых предпосылках и реальных ресурсах. Малый исчерпываемый дизайн с известным oracle предпочтительнее непрозрачного acquisition score. Numeric expected utility требует обоснованного probability/loss basis; без него сохранять scenario/value bounds и ранжирование с несравнимостью.

Источники могут быть существующим датасетом, новым измерением, quasi-experiment или предложением внешнего randomized experiment. Для каждого нужны feasibility/permission boundary, target population, assignment versus receipt, analysis/stopping plan и связь результата с исходным вопросом. O1/O2/O3 правила действуют независимо от того, кто предложил исследование. [Causal Bayesian Optimization](https://proceedings.mlr.press/v108/aglietti20a.html) использует доступную causal graph information; это не готовый discovery неизвестного графа. [Off-target interventions](https://proceedings.mlr.press/v238/choo24a.html) показывают значимость различия attempted и фактического воздействия под предпосылками их модели; нельзя переносить гарантии статьи на произвольную политику.

**Проверки:** два observationally indistinguishable объяснения требуют разных измерений; неинформативное повторение исходного query не получает фиктивный VOI; нарушение uptake/interference меняет допустимый анализ; результат и target не совпадают — value set не сужается; adaptive stopping без подходящего inference не получает обычный fixed-sample interval. Study proposal без разрешения остаётся useful candidate, но не инициирует полевой эксперимент.

<a id="TP03"></a>
## TP03. Probabilistic programming и проверка вероятностной модели — CNT-05/06, GYD-31/32

Использовать при действительно необходимой latent/hierarchical measurement, missingness или иной совместной вероятностной модели. Сначала существующие Foundry Bayesian methods; Stan/PyMC — возможный adapter, не второй inferential authority. Prior/data/likelihood/measurement model и inference algorithm закрепляются раздельно. Posterior predictive checks проверяют выбранные расхождения модели с наблюдениями; simulation-based calibration проверяет inference на генерируемых самой моделью задачах; convergence diagnostics — численный inference. Ни одна из этих проверок отдельно не устанавливает causal identification, population transport или истинность likelihood.

Результат хранит estimand/support, posterior representation либо разрешённый summary, diagnostics, prior sensitivity и model misspecification limitations. Во fresh consumer нельзя показывать narrow posterior из wrong-target model как narrow policy effect. Если модель неидентифицируема, честный prior-dominated результат не превращается в data-grounded fact. Draws приватны при применимых правах; не сохранять их автоматически навсегда.

**Проверки:** simulator-calibrated, но неверный population/measurement law; convergence на неверной модели; изменение missingness/linkage premises при тех же наблюдаемых rows; плохое смешивание/дивергенции не скрыты одним ESS числом; independent simple conjugate/exact oracle для bounded профиля. [Stan PPC](https://mc-stan.org/docs/2_39/stan-users-guide/posterior-predictive-checks.html), [Stan SBC](https://mc-stan.org/docs/2_37/stan-users-guide/simulation-based-calibration.html) поддерживают это различение диагностических ролей.

<a id="TP04"></a>
## TP04. Exact constraints: MIP/CP/SMT — DES-03, GYD-30, CNT-07

Выбирать при дискретной совместимости, capacity allocation или проверяемой логической/арифметической feasibility, где native exact/enumerative method недостаточен по измеренному размеру. Clauses, bounds, units, numerical tolerances и цель происходят из actual selected semantics. Solver certificate относится к этой формализации; неполное кодирование не становится «невозможностью в мире». UNSAT/infeasible, UNKNOWN/timeout, feasible incumbent, bounded gap и доказанный optimum сохраняются отдельно. Проверять полученный candidate независимым recomputation исходных ограничений, а не только solver exit code.

Нельзя использовать default lexicographic ordering как публичный value mandate. [Z3 objective combination](https://microsoft.github.io/z3guide/docs/optimization/combiningobjectives/) показывает разные способы совмещения целей; [Pyomo GDP](https://pyomo.readthedocs.io/en/6.10.1/explanation/modeling/gdp/index.html) — соединение logical и numeric constraints. Выбор encoding/profile — инженерное решение, выбор общественных tradeoffs — отдельное основание.

**Проверки:** oracle enumeration для малого case, отсутствующий material constraint, неверный Big-M/scale/integrality tolerance, timeout при существующем решении, несколько Pareto-вариантов. Удаление constraint при сохранённом названном поле выявляется внешним evaluator. Не вводить solver prerequisite для GYD-23 Slice0 и не дублировать его native route.

<a id="TP05"></a>
## TP05. Multi-fidelity surrogate / numerical search — DES-03/10, GYD-30/31, OPS-08

Когда дорогой вызов симуляции подтверждён измерением, дешёвый surrogate выбирает перспективные trials, а declared validation profile проверяет выбранные решения. Native search/method owner хранит fidelity, training/exposure set, cost, approximation error и actual target evaluation отдельно. Смена surrogate не меняет normative objective; correlated ensemble не означает независимое свидетельство. Если screening исключает части пространства, это часть SearchLedger coverage, а не доказательство их непригодности.

[BoTorch multi-fidelity tutorial](https://botorch.org/docs/v0.17.0/tutorials/multi_fidelity_bo) иллюстрирует cost-aware acquisition и target fidelity. В PolicyOS адаптер допустим только при совпадении предпосылок; latent fantasy/BO posterior не является эмпирическим causal posterior. Факт target-fidelity computation не устраняет K_world. Exact joint witness может быть достаточным для своей математической claim без максимальной симуляции, согласно принятой C01.

**Проверки:** ranking reversal между fidelities, unseen regime, низкооценённый surrogate кандидат оказался лучшим, inflated low-fidelity certainty, timeout final evaluation. Финальный consumer сохраняет unvalidated состояние; matched surrogate-off/equal-ceiling comparisons измеряют пользу и потери без обещания universal superiority. Adaptive branch retries используют один compute owner; внешний side effect не повторяется ради Monte Carlo.

<a id="TP06"></a>
## TP06. Измерение, linkage, support и стратегический ответ — CNT-05/06/07, GYD-01/30/32

Варианты измерения — части модели: instrument/language invariance, MNAR mechanisms, linkage precision/recall, spatial boundary vintage/weights, population support и denominator. Metadata field не заменяет producer. Переиспользовать `ir/observation`, survey-quality/DR methods, Fabric entity resolution и spatial methods; конкретный writer уточняется на accepted source. Текущий synthetic MAUP пример нельзя выдать за проверку actual boundary mapping.

S6 уже требует capacity и strategic response. Усиление — действующий producer с конкурирующими обоснованными uptake/selection/gaming/supply responses; не новый S6. LLM может назвать возможность gaming, но response magnitude требует основания или scenario limitation. [Performative Prediction](https://proceedings.mlr.press/v119/perdomo20a.html) формализует изменение распределения вследствие решений при своих предпосылках, не доказывает универсальную сходимость политики.

**Проверки:** одинаковый score при другом instrument meaning; MNAR вместе с biased linkage; изменение границ при неизменных raw observations; одинаковый агрегат при вреде конкретной группе; pay-for-placement меняет selection и регистрацию, а не только реальный outcome. Consumer либо меняет range/feasibility/choice, либо имеет обоснованный stability result. Требование не предписывает всегда менять ranking и не навязывает все методы каждому case.

<a id="TP07"></a>
## TP07. Federated / private computation — CAP-06, LIF-05/07, OPS-09, CNT-06/08

Для выбранного private profile данные могут оставаться у custodians, а разрешённые агрегаты/updates проходят native permission, receipt и admission. Secure aggregation доказывает свой security property при своей threat model, не корректность оценки. Нужны site/population/support definitions, participation/dropout, alignment/measurement и допустимая weighting/heterogeneity model. Отсутствие site не означает случайную выборку. Проверка допускает partial outputs только с честным изменением target/claim, а не прежней global подписью.

Differential privacy применяется, если заявлена/требуется выбранным профилем: privacy unit, adjacency, clipping/sensitivity, randomness/mechanism и composition law связываются с существующим LIF-05 owner. Численные последствия noise/bias входят в inference. Нет universal epsilon и второго privacy ledger. Неизвестный outcome может уже раскрыть результат: shared reservation не возвращается автоматически. Exact replay разрешённого output и fresh randomized draw различаются. [OpenDP](https://docs.opendp.org/en/stable/api/user-guide/programming-framework/index.html) предлагает domain/metric/measure composition; [NIST SP 800-226](https://csrc.nist.gov/pubs/sp/800/226/final) обсуждает оценку заявленных DP guarantees.

Модель, embedding и synthetic data — derived artifacts с правами и influence lineage; отсутствие raw rows не доказывает отсутствие утечки. [Extraction study](https://www.usenix.org/system/files/sec21-carlini-extracting.pdf) — конкретное предупреждение об извлечении training data, не универсальная вероятность атаки. Discretionary attack test обнаруживает риск, но не сертифицирует нулевую утечку. Synthetic descendants не увеличивают independent evidence count.

**Проверки:** dropped nonrepresentative site, poisoned/misaligned aggregate, aliases overlapping releases, rollback после неизвестного раскрытия, DP noise забыто в effect interval, raw-free artifact с запрещённым content. Rights/egress fail closed; candidate analysis на synthetic lawful data может продолжаться. Ни федерация, ни DP не обязательны для каждого public/local case.

<a id="TP08"></a>
## TP08. Ценности, partial identification и learning support — CNT-05/06/07/08, GYD-09/10/12/31, DES-03/12

Раздельно хранить: фактическую неопределённость, неидентифицированность эффекта, неполный preference order, конфликт мандатов и отсутствие права выбора. Учёт новых фактов может сузить первую часть, но не создаёт мандат/социальные веса. Hard floor защищённой группы не становится штрафом, который можно компенсировать aggregate benefit. Necessary/possible ranking и Pareto/outer-set comparison — предпочтительнее выдуманного единственного winner при неполных основаниях.

Для learning связывать eligibility/exposure/assignment/receipt/outcome availability, policy version и measurement regime. Propensity нужен там, где его требует выбранный estimator, а не как универсальный атрибут каждой строки. Отсутствие overlap не лечится большим n или fit; подходящий bound/transport profile может дать ограниченный результат, но не выдуманный point identification. Exploratory selection и многократный просмотр требуют analysis, валидного для реальной схемы; новый dataset не универсально обязателен, если допустимый метод учитывает selection/stopping. O1 activation не возникает от положительного control test.

**Проверки:** смена exposure support при фиксированном label; same-data O2→O1 без подходящего analysis; точный estimate чужого target; два mandate-consistent разных preference orders; identical aggregate gain с разным subgroup harm; данные сужают statistical interval, но contested value choice остаётся contested. Native N6/Atlas/document показывает именно эту границу.

## Как принять техническое решение

Выбранная библиотека и схема не являются задачей сами по себе. Завершённая задача показывает, что её **конкретное решение** изменило полезный native result и дошло до fresh consumer; removal лишает эту цепь свойства. Если accepted source уже умеет нужное — добавить wiring/verification, не второй implementation. Если сложный метод не даёт оправданного преимущества — оставить простой native profile и записать основание отклонения. Если меняется ratified owner/authority/time/shared ABI — отдельный proposal, никакой молчаливой SDD amendment. Conditional technology не освобождает от исходных mandatory obligations и не расширяет их без основания.
