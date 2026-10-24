# R15: две новые задачи и точные дополнения

План на source `528ec2576393e8aa9a0238ae4172336ccf76a057`; runtime **UNRUN**. Статическое чтение не устанавливает отсутствие возможностей в текущем E02 candidate. Сначала accepted-source rebind; уже существующий механизм получает wiring/semantic proof, а не повторную реализацию. Original criteria и R14 requirements сохраняются. [Архитектурная связка](../architecture/05-adaptive-design-and-research.md), [полные технические профили](15-technical-method-lifecycle.md), [семантическая приёмка](../assurance/09-adaptive-research-and-method-quality.md).

<a id="DES-11"></a>
## DES-11 — производить и оценивать адаптивные траектории политики

**Остаток:** в DES-03/04/GYD-30 есть поиск, feedback и joint evaluation, но явно не назначен полный path-level producer→consumer witness: порядок мер, доступная тогда информация, signposts, incumbent commitments и необратимость должны влиять на результат. Это allocation/semantic-test gap плана; состояние конкретных runtime links пока not_established.

**Предпочтительное решение:** расширить существующий Scientist candidate/search → Foundry temporal/world → joint result → frontier/dossier путь. Представлять стратегию как typed conditional program на уже поддерживаемых операторах, с finite horizon/branch envelope и наблюдаемой историей. Статическая мера — допустимый частный случай, не обязательный новый wrapper. Не создавать «adaptive_policy_engine», автономный институт исполнения или второй lifecycle.

**Native anchors:** `src/polisyos/scientist/policy_design/search.py`; `src/polisyos/foundry/agent_sim/temporal_executor.py`; `src/polisyos/foundry/agent_sim/temporal.py`; `src/polisyos/foundry/execute/api.py`. GYD-30 остаётся owner joint witness, DES-03 — общего search coordinator. Конкретные writer/adapter/schema files назначить после scoped rebind. Источник исследования не является blanket write lease.

**Шаги реализации:**

1. Проследить actual representation и consumer всех выбранных policy operators, temporal transitions и observed history. Объявить supported strategy class, information set, horizon, reference policy, initial state, constraints/objective basis, terminal/residual treatment и applicable uncertainty profiles. Unknown имеет declared semantics, а не скрытый default.
2. Связать упорядоченные действия с transition/lag/carryover assumptions, доступной информацией и signpost measurement contract. Distinguish condition not observed, observed not satisfied, inconclusive/noisy и verified condition; использовать native status types, не новый глобальный enum. Candidate scenarios могут содержать hypothetical observations, но не выдаваться за actual branch activation.
3. В native temporal evaluation запретить доступ rule к future/latent truth. Runtime history учитывает не только event time, но receipt/verification/decision cutoff. Поздние corrections могут пересчитать нынешнее обоснование, не менять то, что было известно раньше. Политика может влиять на сам sensor/selection; observation process тогда часть основания.
4. Подключить selected incumbent policies, общие fiscal/service/staff capacities и declared strategic-response alternatives. Не считать planned capacity доступной сейчас. Неизвестный baseline даёт условный feasibility claim; внутренний wiring всё равно завершить.
5. Исполнить actual trajectories/conditional branches; сравнить no-op, delay, stop, alternative order и хотя бы один допустимый adaptive strategy. Search budgeting/pruning остаётся native. Указать omitted branches и unsupported regimes; policy equivalence сравнивать по grounded semantics, не по тексту или ID. Pruning не уничтожает material value/model alternatives без основания.
6. Сохранить owner-native program/input/model/rule/transition/result refs, branch decisions с observation cutoffs, uncertainty, compute cost и ограничения. Fresh DES-03/N6 consumer читает persisted result. Existing dossier/API/Atlas/DES-06 показывают what-if sequence, thresholds, residual commitments, alternatives и **recommendation**, не факт институционального действия.
7. LIF-02/07 связывают зависимость и affected-claim revalidation; права/retention остаются LIF-05. DES-04 принимает trajectory counterexample при выбранном feedback use; DES-12 может предложить discriminating study, но это не prerequisite самостоятельного trajectory producer.

**Positive:** на controlled known-solvable case A→B и B→A при одном intervention set расходятся вследствие carryover; adaptive policy реагирует лишь после доступного signpost и показывает полезный результат относительно relevant fixed/no-op comparator в declared model envelope. Fresh consumer воспроизводит различие. Authentic benefits этим не устанавливаются.

**Adversarial:** одинаковая доступная history, разные latent futures; backdated observation, полученное позже; noisy threshold/chattering; horizon hides tail loss; stop игнорирует sunk commitments; incumbent нагрузка превышает cap; модель поведения изменилась после объявления меры; неверное cost discounting. Expected result — содержательная поправка, bounded uncertainty/stability result или scoped refusal, не обязательная смена winner.

**Removal:** убрать real history/transition consumption, оставив sequence labels, — order-sensitive oracle и fresh result не проходят. Удалить cutoff enforcement — paired histories расходятся до наблюдаемого различия. Удалить incumbent binding — контроль feasibility ловит ошибку. Каждый removal сопоставим с exact positive source/input.

**Migration:** terminal-only artifacts читаются как terminal-only; отсутствие path history не восстанавливается по names. Новые схемы/version relations additive по правилам владельца; старые public claims не повышаются. Forward repair создаёт новую версию; numerical reset, откат рекомендации и отмена реального воздействия — три разных события.

**Alternatives:** отдельный optimizer/MDP engine не нужен без unmet semantics/resource evidence; flat exhaustive scenarios не масштабируются; model-predictive/robust methods — выбранные profiles, не universal doctrine; pure LLM trajectory не заменяет исполнение. Новые supported operators подключаются registry data/config; новый temporal meaning требует owning extension.

**Stage dependencies:** actual E02 + scoped rebind; DES-03, GYD-30, CNT-06/07 и LIF-02 — interface agreement для подготовки, реальные selected suppliers для composed acceptance. Не ждать все исследования, все модели и все внешние акты. Один writer общего search, отдельные temporal adapters, cases и projections готовятся параллельно.

<a id="DES-12"></a>
## DES-12 — производить проекты исследований, которые разрешают существенную неопределённость

**Остаток:** acquisition/VOI и causal adequacy уже существуют, но оценка готового evidence не равна выбору будущего discriminating study. Нужна actual producer→persisted design→acquisition/reviewer consumer→returned evidence chain. Нельзя закрыть задачу текстовым советом «нужно больше данных».

**Предпочтительное решение:** расширить существующий Foundry `CausalExperimentDesigner` / `ExperimentPlan` и связать его с Scientist hypothesis/search и runtime acquisition planner. Design generation связывает decision alternatives, competing causal/measurement/implementation explanations и допустимые каналы получения информации. Foundry оценивает anticipated outcomes/power/precision только при обоснованных assumptions. PolicyOS выдаёт исполнимое **предложение исследования** и interpretable analysis plan; external institution владеет людьми, assignment и execution.

**Native anchors:** `src/polisyos/foundry/methods/catalog/causal/optimal_design.py::CausalExperimentDesigner`; его `protocols.py::ExperimentDesignData`; `src/polisyos/ir/analytics/experiment_plan.py::ExperimentPlan`; `src/polisyos/runtime/quality/acquisition_planner.py`; `src/polisyos/scientist/orchestration/workflows/causal_full.py`. На исследованном source primitive работает с одним graph: stage count, nonempty intervention list и variance proxy не доказывают различение конкурирующих объяснений. DES-04 владеет acquisition/feedback bridge; DEB-13 — commissioned VOI meaning; CNT-06 — causal/measurement qualification, не исследовательский scheduler. Compute ranking в `scientist/methods/search/voi_scheduler.py` нельзя переименовать в scientific EVSI.

**Шаги реализации:**

1. Pin question, competing explanations, material decision alternatives, estimand/target/support, уже известные наблюдения и отличающее предсказание. Проверить, нельзя ли выбрать ту же допустимую политику при всех объяснениях; тогда разрешение полного causal graph не является обязанностью case.
2. Найти через native registry доступные designs: reuse dataset, дополнительное measurement, audit/validation subset, natural/quasi-experimental observation, external trial proposal. Feasibility включает сроки, observation lag, burden, costs, capacity, rights/consent/competence и риск. Синтетический design-space контрпример не создаёт настоящего разрешения.
3. Сформировать distinguishing contrast и design→analysis binding: sampling/assignment unit, exposure/receipt, interference/cluster structure, missingness/linkage, target estimate или decision criterion, analysis/stopping/multiplicity regime, и результат, который поддержит/опровергнет каждую гипотезу. Measurement-only design не обязан иметь treatment propensity; randomized design не гарантирует compliance.
4. Сравнить expected decision value, precision/power или robust bounds под явно указанным probability/loss basis. Если probabilities/priors/effect sizes не обоснованы — scenario/bounds, partial order или nonnumeric ranking. Информация, разделяющая модели, не обязательно имеет decision value; uncertainty in preferences/mandate не лечится statistical acquisition. Cost/ethics не прячутся в произвольном scalar score.
5. Исполнить native method evaluation для выбранных designs и сохранить candidate design/analysis version, predicted distinguishing observations, assumptions, required external inputs, expected cost/duration и refusal/alternative route. Fresh N7/acquisition/UI consumer получает конкретный request/plan; protected external action разрешает только его actual owner по существующим правилам.
6. Return path связывает фактический source, execution deviations, participant/site/time/support и полный result denominator с analysis version. Amendments не стирают preregistered history; selective reporting и substituted targets выявляются. Unanticipated analyses могут быть полезными exploratory candidates, но не становятся planned confirmation.
7. CNT-06 → O1/O2/O3 принимает полученное evidence с нужным inference profile. Existing selection/stopping controls и WP-01/02 activation сохраняются. Новый design/result сам по себе не пишет causal world. DES-04 получает решение «изменить candidate / приобрести другое evidence / остановить acquisition / сохранить неразрешённость».

**Два обязательных fences при reuse.** Первый: current authorization для соответствующей protected operation связывает точную версию protocol/design, purpose, site/population, intervention/measurement, recipient и relevant validity/revocation state. Применимое разрешение заново проверяется owner перед dispatch/resume, не переносится автоматически с v1/site A на v2/sites A+B. Mismatch блокирует эту операцию и claims об authorized conduct; факт незаконного/непроверенного исполнения при законном получении данных может оставаться отдельно квалифицированным evidence, а не автоматически удаляться. Иных разрешений для незащищённого внутреннего расчёта этот контракт не требует.

Перечень facets выше не исчерпывающий: native owner recomputes coverage **всех required facets actual operation/authorization contract**, включая будущие conforming extensions; unresolved required scope блокирует affected action и authorized-conduct claim. Current use уже возвращённого evidence требует **отдельного admission** в своём purpose/rights scope. Проверяется этот generic predicate, а не последовательность per-field allowlists.

Второй: native designer имеет численные defaults, которые нельзя принять за case facts. На исследованном source есть default budget/prior variance/stage count и режимы simulated allocation. Decision-bearing budget, effect/noise/prior/assignment basis должны быть explicit и source-qualified либо явно hypothetical в scenario. Omitted basis → bounded/nonnumeric или scenario-only результат; отсутствие — не разрешение выводить numeric feasibility/power/EVSI из default. Технические solver defaults допустимы в recorded execution profile, если не подменяют substantive inputs. Simulated/equal-stage allocation не выдаётся за outcome-adaptive study без actual history→allocation→analysis chain.

**Positive:** два объяснения согласуются с исходным наблюдаемым распределением, но различаются на разрешённом candidate measurement/intervention. Producer предлагает именно distinguishing study; small exact oracle подтверждает anticipated contrast. Через controlled actual owner route пришедший результат меняет допустимое множество объяснений/решений в fresh consumer. Отдельный control: дорогой study не нужен, когда все рассматриваемые модели дают один admissible choice.

**Adversarial:** больше данных без identification; off-target/noncompliance; невозможное измерение; target/population подменён; treatment как-observed принят за randomized assignment; adaptive selection/stopping игнорируется; incomplete negative outcomes; prior-dominated VOI; study позднее decision deadline; «consent=true» без authority; valid grant для другой версии/site или revoke между planning и dispatch; omitted decision basis при наличии убедительного default-generated plan. Bound/refusal не должен обнулять всю candidate work.

**Removal:** разорвать связь hypothesis→distinguishing observable, сохранив красивые study fields, — discriminating oracle не проходит; удалить analysis version/result binding или actual acquisition consumer — fresh evidence не влияет законно на дальнейший вывод. Удаление permission guard обнаруживается отказом protected action, а не marker scan.

**Migration/free-grow:** старые acquisition requests остаются исходными requests, не ретроактивными preregistrations. Новые conforming study methods выбираются registry, без списка социальных доменов. Новый inference family требует owner-specific validation. Повторный run может reuse qualified design/results при совпадении смысла и прав, но не создаёт новый independent experiment.

**Alternatives:** общий autonomous laboratory controller выходит за границу; единственный hardcoded RCT исключит полезные observation/audit/quasi designs; требование полного causal discovery до каждого решения создаёт лишнюю работу; LLM-scored informativeness не заменяет метод/сценарии. Bayesian experimental design/CBO применяется только под соответствующими предпосылками, не как универсальная обязанность.

**R22 — отдельные effect/structural predicates:** Return a qualified structural result with no effect-posterior WP activation: under an actual applicable structural-write rule it can reach the sole GYD-12 writer and fresh next-cycle reader. Remove that structural rule and it remains candidate/conditional. Separately, the O1 effect-posterior route without its required activation refuses operative mutation. One route’s receipt cannot close the other; no new write authority is granted by this plan.

**Stage dependencies:** DES-04, CNT-06 и CAP-01 interfaces для подготовки, реальные selected outputs для composition. DEB-13 требуется только если выбран numeric scientific EVSI claim; отсутствие его probability/loss basis не блокирует обоснованный nonnumeric design. DES-11 не prerequisite. Actual external experiment/approval нужен только affected action/claim, не owner readiness на controlled data. Full programme FINAL-USE не получает скрытых waivers по прежним обязательствам.

<a id="extensions"></a>
## Additive изменения существующих задач

Машинный источник — поля `r15_extension` в [tasks.json](../tasks.json) и [preferred-solutions.json](preferred-solutions.json). Каждое содержит конкретное требование, expected positive/adversarial/removal и ссылку на технический профиль. Старые acceptance fields не заменяются. Ключевые группы:

- DES-03/04/06/10: conditional strategies, study-design feedback, читаемый adaptive/research section, полный quality denominator.
- GYD-01/30/31/32: actual strategic/capacity producer, incumbent interference, joint/uncertainty semantics и scoped model execution.
- CNT-05/06/07/08: construct/MNAR/linkage/spatial/measurement, causal design and returned evidence, values/capacity и dependence.
- GYD-08/09/10/12: selection/stopping, exposure support и policy regime без изменения activation authority.
- CAP-06/LIF-05/LIF-07/OPS-08/OPS-09: conditional private/federated inference, disclosure composition, derived-artifact influence и bounded compute.
- UI-06/UI-08: uncertainties, trajectories, research and learning limitations в actual owner projections.
- FINAL-FREEZE/REPLAY/USE: готовность новых native mechanisms и verification preparation, одна composed wave, явная disposition нового scope.

Pattern pass: P01/P02/P03/P05/P07/P08/P10/P13–P27/P29/P31/P32/P35/P37/P38. Plan-level allocation завершает постановку; runtime claims остаются **UNRUN**, missing-link labels после accepted-source rebind. Две новые задачи не являются разрешением добавить два новых движка.
