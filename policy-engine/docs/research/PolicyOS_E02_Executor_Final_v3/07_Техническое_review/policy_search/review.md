# Финальное техническое ревью LANE-01 и LANE-02

**2026-11-01 · 27/27 пакетов · 134 REQ / 132 TEST прочитаны · продуктовые тесты NOT_RUN.**

## Краткий результат

Предложенная архитектура в основном разумна: существующие owners, реальные positive paths, независимые численные oracles, сохранение полезного partial result и отделение model result от полномочия. Не требуется новый «универсальный движок» или массовая замена библиотек. Но принимать весь lane по готовым receipts, одному synthetic case либо числу тестов нельзя.

**Обязательные точечные уточнения:** FUN-03 — значение calibration metrics, sampling/qualification и нулевой score; OPT-02 — честная причина bounded proposal exhaustion; SIM-03 — дополнительный native seed-sensitive witness для stochastic claim и deterministic normal quantile без100000 global draws на каждый call. **Отдельная capability-развилка:** strategy-neutral reuse измерений без требования fitted GP у proposer; действующий fitted-native guard и локальный DoD не ослаблять.

Сняты как новые defects: OPT-01 уже требует proxy/exact distinction, fixed reference и actual ranking consumer; TRN-02 уже требует cost measurement snapshot-per-add. Для них ниже только обоснованные optional library/performance решения.

## Область и доказательная сила

- Immutable baseline ZIP SHA `e08baa70c8acf92f8f2e5afd8ced38c94213355dea07c4b33b14a417aefdebf3`; repository HEAD `20d9009be21097bfbdc38a546a15cc60213b8ace`.

- Прочитаны полные solutions/tests всех27 MD и companion JSON, lane summaries/integration contracts, concrete bindings I01-A/B/C и I02-A/B/C/D, relevant X03/X04 и архитектурные capability/free-grow sections. Exact hashes/ranges: [coverage.json](coverage.json). Selected repository code/tests изучены, но не импортировались и не исполнялись; весь repository test suite не объявляется прочитанным.

- Независимо выполнена только stdlib арифметика контрпримеров: [script](independent_arithmetic.py), [results](independent_arithmetic.json). Это не product tests и не numerical backend qualification.

- Рекомендации по библиотекам проверены по current primary sources с предпочтением pinned release docs/source; availability в lock не означает установленный/работающий backend. Нет installs, внешних mutations, платных providers или credential access.

- Verdict **retain** означает «сохранить решение и исполнить его приёмку», не PASS. **Bounded qualification** означает полезную ограниченную способность с недоказанным пока end-to-end witness. **Targeted revision** — конкретное изменение спецификации. **Separate redesign decision** не превращается в mandatory scope creep.

## 1. Находки и точные изменения

### PS-F01 — Калибровка смешивает три conditional rates, не определяет sampling estimand и допускает статистически неподтверждённый PASS

**HIGH · confirmed_specification_defect_and_capability_qualification_gap**. Пакеты: FUN-03. REQ: REQ-FUN-03-02, REQ-FUN-03-03. TEST: TEST-FUN-03-02, TEST-FUN-03-03. Сценарии: E02-I02-C.

**Что блокирует:** Блокирует acceptance FUN-03-03 как калибровочной гарантии и соответствующий promotion qualification в I02-C; не запрещает сбор данных, exploratory search, descriptive observed counts или отдельный проверенный writer.

**Неточная/ошибочная постановка:** Решение допускает observed0 при любом ненулевом rejected denominator как PASS, называя величину false_negative_rate. При этом фактические false_positive_rate, true_positive_rate и false_negative_rate используют predicted-class denominators, а не стандартные actual-class denominators; operational purpose и population scope не зафиксированы.

**Доказательства:**

- [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/FUN-03.md:47–56](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/FUN-03.md) — Typed availability исправляет empty/constant, но не semantics/power; observed0 может PASS

- [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/FUN-03.md:85–89](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/FUN-03.md) — Пять rejected-A без ошибок — положительный criterion fixture

- [policy-engine/src/polisyos/scientist/methods/search/stages.py:398–408](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/stages.py) — Метод false_negative_rate возвращает FN/(FN+TN), то есть FOR

- [policy-engine/src/polisyos/scientist/methods/search/stages.py:682–714](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/stages.py) — FP/(TP+FP)=FDR; TP/(TP+FP)=precision; FN/(FN+TN)=FOR

- [policy-engine/src/polisyos/scientist/methods/search/stages.py:502–545](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/stages.py) — FP/TP full corpus и FN rolling corpus — разные окна под одной metrics projection

- [policy-engine/src/polisyos/scientist/methods/search/calibration_report.py:112–171](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/calibration_report.py) — Порог <0.02 и routing_health читают старый смысл

- [policy-engine/src/polisyos/scientist/methods/search/cold_start.py:190–276](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/cold_start.py) — Burn-in calibration/lesson corpus и тот же <2% criterion

- [policy-engine/src/polisyos/scientist/methods/search/funnel/correlation.py:83–97](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/funnel/correlation.py) — Compatibility wrapper экспортирует те же имена

- [policy-engine/src/polisyos/scientist/methods/search/funnel/orchestrator.py:781–804](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/funnel/orchestrator.py) — Burn-in действительно продолжает rejected levels1–3; отсутствие механизма rejected labels НЕ утверждается

- [policy-engine/src/polisyos/scientist/methods/search/funnel/orchestrator.py:2096–2134](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/funnel/orchestrator.py) — Обычный record появляется лишь при обеих доступных labels; sampling cohort/inclusion не являются обязательными полями

**Различающие контрпримеры:**

- Пусть actual qualified positives=10, все 10 отклонены A; ещё 990 actual negatives тоже отклонены. TP=0,FN=10,TN=990,FP=0. В явно выбранном окне 1000, не default20, текущий FOR=1% проходит <2%, хотя FNR=100%: система теряет все полезные случаи. Это не ошибка FOR как operational metric — это ошибка его названия/использования как FNR.

- Если ошибок 0 из 5, observed rate действительно 0; для иллюстративного one-sided95% exact iid interval верхняя граница 1-0.05**(1/5)=45.07%, а не <2%. Уровень95% здесь демонстрация, не навязанный policy threshold.

- Корпус из обычных surviving candidates, выбранных burn-in lessons и специальных sentinel cases может улучшать наблюдаемую rate без улучшения target traffic. Интервал iid для такого смешанного/adaptive корпуса сам по себе неправомерен.

**Реалистичные альтернативы:**

- **Сохранить FOR как показатель вероятности полезного результата среди rejected** — Может быть именно полезной метрикой для стоимости пропущенной дорогостоящей оценки; соответствует существующему знаменателю. Цена/ограничение: Нужно переименовать claim, согласовать operational tolerance, cohort и qualification; не обещать recall.

- **Выбрать FNR/recall как protection от пропуска полезных случаев** — Измеряет долю потерянных actual positives. Цена/ограничение: Нужны source-bound labels accepted и representative audited rejected с известным inclusion/selection design; простой swap denominator недостаточен.

- **Только descriptive rates и typed insufficient_evidence** — Немедленно полезно без ложной гарантии. Цена/ограничение: Не закрывает population-level calibration acceptance.

**Предпочтительное решение:** Один versioned confusion-metric contract у CorrelationTracker; counts TP/FP/FN/TN, определение gate/truth, target population, eligibility, missing-label count, cohort/audit selection, window и metric definition. Ограниченный DEC выбирает FOR или FNR и назначение порога. Existing burn-in используется для бюджетного audit, а не новый registry. Descriptive observed zero сохраняется, qualification требует обоснованного интервала/дизайна и мощности под выбранную operational tolerance. Исторические bytes не переписывать; reader выдаёт legacy semantic projection и новую явную версию. Миграция охватывает прямой tracker, wrappers, calibration report Markdown/JSON, cold-start acceptance, routing/drift и snapshots.

**Цена и компромиссы:** Audit расходует реальную stage-B работу и может не набрать evidence в доступном budget: это insufficient_evidence, не автоматический PASS и не бесконечный burn-in. Ни confidence bound, ни metric PASS не заменяют permit authority. Для адаптивных/коррелированных данных выбрать соответствующий дизайн либо ограничить вывод наблюдаемым корпусом; не назначать произвольный n.

**Точный текст требования:**

> Заменить уточнением REQ-FUN-03-02/03: «Каждая публикуемая calibration rate содержит versioned metric_name/definition, numerator/denominator counts, target population, window/cohort и label-availability/selection scope. FOR, FDR, precision не называются FNR, FPR, TPR. До DEC operational metric/tolerance observed value является descriptive; acceptance qualification не выводится из одного условия denominator>0. Для выбранного confidence/power criterion предъявляются sampling assumptions и интервальная оценка либо honest insufficient_evidence. Legacy snapshots сохраняют исходный смысл; все consumers используют одну явную metric projection».

**Дополнение к проверкам:**

- Добавить к TEST-FUN-03-03 независимую таблицу всех четырёх confusion cells и counterexample TP0,FN10,TN990,FP0; проверять count/window во всех public projections. При FNR добавление TN не меняет значение; при FOR меняет по объявленной формуле. Добавление TP различает оба estimands.

- 0/5 → observed0 допустим, но qualification GAP/insufficient_evidence для tolerance2% при illustrative95% iid profile. Положительный qualified case берётся из заранее обоснованного sampling design; размер определяется power/tolerance/budget, не magic fixture.

- Разделить обычный поток, independent audit, lesson seeds и sentinels; изменить доли cohort, скрыть часть labels и проверить запрет population claim без correction/ограничения scope.

- Actual stage-A/B record → persisted JSON/CAS snapshot → fresh compatible reader → report/routing; historical legacy payload остаётся читаемым без silent denominator migration. Source-bound labels, costs и все rejected/accepted counts сохраняются.

**Единый владелец:** FUN-03 / existing CorrelationTracker; cold_start/calibration_report/funnel compatibility consumers. FUN-01/02 только поставщики attempt/cost/source; отдельный статистический registry не нужен.

**Что нельзя сломать:** Не превратить true observed0 в missing; различать value и qualification; Не выключить exploration из-за недоказанной population guarantee; Не переписать исторические именованные значения молча; Не считать sentinel targeted controls representative traffic; Не заменить protected-writer authority статистическим PASS.

**Валидация:** Сначала согласовать DEC и полный consumer census, затем локальные независимые arithmetic matrices и actual producer/snapshot/fresh-reader chain; отдельно бюджетный audit design. Product execution требует отдельной авторизации и поддержанного runtime.

**Предел уверенности:** Оригинальный B163 требует честной empty/routing calibration, но не определяет однозначно FNR против FOR. Поэтому требование обязательного FNR было бы необоснованным. Наблюдаемая ошибка формул/названий и слабость n>0 PASS подтверждены чтением; реальные production rates не измерялись.

**Primary sources:** [Recall = TP/(TP+FN)](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.recall_score.html); [binomtest: число успехов k в n Bernoulli trials](https://docs.scipy.org/doc/scipy-1.16.0/reference/generated/scipy.stats.binomtest.html); [exact / wilson / wilsoncc interval methods](https://docs.scipy.org/doc/scipy-1.16.1/reference/generated/scipy.stats._result_classes.BinomTestResult.proportion_ci.html).

### PS-F02 — Переиспользуемое измерение ошибочно связано с наличием fitted GP у предлагающей стратегии

**MEDIUM · deliberate_scope_limitation_with_redesign_recommendation**. Пакеты: OPT-03, TRN-01, OPT-02. REQ: REQ-OPT-03-04, REQ-TRN-01-03, REQ-OPT-02-04. TEST: TEST-OPT-03-04, TEST-TRN-01-03, TEST-OPT-02-04. Сценарии: E02-I02-B, E02-I02-D, E02-X03.

**Что блокирует:** Не блокирует локальный OPT-03 repair или существующий узкий fitted-GP profile. Ограничивает claim reusable search/free-grow и требует отдельного bounded observation-reuse profile, если заявляется reuse настоящих измерений независимо от proposer.

**Неточная/ошибочная постановка:** TEST-OPT-03-04 закрепляет cold initial rows не fitted sources. Сохранённый actual MethodJob outcome может быть отклонён target training только потому, что source proposer ещё не обучил GP, хотя такой же cold measured row участвует в training внутри текущего run.

**Доказательства:**

- [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/OPT-03.md:52–55](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/OPT-03.md) — Source reuse требует replay source fit basis

- [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/OPT-03.md:86–90](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/OPT-03.md) — Явно сохранён запрет cold initial rows как fitted source

- [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/TRN-01.md:56–59](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/TRN-01.md) — Native source и candidate-only варианты без независимого measurement reuse profile

- [policy-engine/src/polisyos/scientist/methods/autotune/bayesian_generator.py:430–507](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/autotune/bayesian_generator.py) — Warm start проверяет warm_start_eligible и source-fit verifier

- [policy-engine/src/polisyos/scientist/methods/search/strategies/bayesian.py:249–312](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/strategies/bayesian.py) — Historical admission зависит от fitted native GP profile

- [policy-engine/src/polisyos/scientist/methods/search/strategies/bayesian.py:1209–1266](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/strategies/bayesian.py) — Current-run cold configured rows допускаются как наблюдения

- [policy-engine/src/polisyos/scientist/methods/autotune/runtime.py:1938–2167](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/autotune/runtime.py) — Actual MethodJob receipt/history создаётся отдельно; non-fitted outcome получает warm_start_eligible=False

- [policy-engine/tests/unit/scientist/methods/autotune/test_v5_search_pipeline.py:2063–2104](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scientist/methods/autotune/test_v5_search_pipeline.py) — Native source four-row run ожидает accepted1/rejected3

**Различающие контрпримеры:**

- Одинаковый source-bound measurement y(x), единицы, split, tenant и input/data refs: до перезапуска это current observation, после fresh warm import — rejected как cold proposer. Семантика измерения не изменилась, изменилось место в run и готовность модели, которая выбрала x.

- Random/Sobol proposer может заказать валидный expensive MethodJob и получить полезную observation. Принудительно повторять тот же MethodJob лишь для смены producer strategy — лишняя стоимость, не улучшение measurement validity.

**Реалистичные альтернативы:**

- **Оставить только fitted-native-GP continuation** — Минимальный scope; строгий существующий guard. Цена/ограничение: Честно ограничить reuse claim и признать потерю cold measurements.

- **Отдельный measured_observation reuse profile и отдельно model/prediction continuation** — Generic reuse actual evidence; не требует повторять source hyperparameter fit. Цена/ограничение: Новый versioned admission profile и migration; нельзя просто ослабить существующий guard.

- **Всегда target reevaluation** — Полезно при несовместимых units/data/split. Цена/ограничение: Избыточно для точно совместимых измерений.

**Предпочтительное решение:** Разделить три сущности: verified measurement (actual selected MethodJob outcome), source prediction/uncertainty и surrogate state continuation. Для первой проверять existing source resolver, objective/units/direction/data/split/tenant/space/replica; proposer strategy не admission condition. Target GP строится по собственному declared profile. Для model continuation оставить fit lineage/full-refit replay OPT-03. Для incompatible measurement оставить candidate-only reevaluation TRN-01.

**Цена и компромиссы:** Это bounded capability expansion, не скрытый дефект нынешнего intentionally narrow profile. Не нужно переносить произвольный старый score; source-backed measured result остаётся обязательным. Полезный reuse экономит source evaluation, но GP fit/conditioning costs учитываются отдельно.

**Точный текст требования:**

> Только при отдельном выборе расширения DEC-OPT-03-02 добавить bounded profile: «Допуск actual measured observation не зависит от стратегии, предложившей её параметры, при совпадающем declared measurement basis и проверенном selected source. Source GP predictions и continuation state имеют отдельный более сильный fit-basis contract. До отдельной квалификации нового profile существующий fitted-native guard, cold rows≠fitted sources и локальный repair DoD сохраняются; extension не является обязательным условием их приёмки».

**Дополнение к проверкам:**

- Actual source Sobol/random и fitted-GP proposals заказывают одинаково квалифицированные MethodJobs; fresh CAS target принимает measured outcomes по одному measurement profile, при этом cold rows не получают fitted-state status.

- Whole/current corpus против split/persist/reload/warm corpus: одинаковый eligible observation multiset, canonical coordinates и source refs; повтор origin один раз, independent replicate отдельно.

- Мутации units/split/data/tenant/objective rules и forged raw score отклоняются; prediction mean/std без actual measurement не входят как y.

- Сравнить реальную evaluation/fit/IO work warm и cold без обещания universally better regret.

**Единый владелец:** OPT-03 fit verifier + OPT-02 actual observation admission + TRN-01 WarmStartBridge. Один versioned source-profile union, не новый GP registry.

**Что нельзя сломать:** Нельзя снять unitless/closed-holdout/tenant guards; Не смешивать posterior uncertainty с измеренной variance; Не переносить source model_state как target truth; Не активировать unused benchmark converter.

**Валидация:** Сначала source-profile DEC; затем existing native MethodJob source fixture с дополнительным cold-row bridge, independent selected receipt verification и fresh target process. Native optional backend profile обязателен.

**Предел уверенности:** Intentional rejection подтверждён кодом/ожиданиями; экономия зависит от reusable workload и измеряется отдельно. Не утверждается, что нынешний test ошибается в своём узком контракте.

**Primary sources:** [SingleTaskGP(train_X, train_Y, train_Yvar), condition_on_observations, MixedSingleTaskGP](https://botorch.readthedocs.io/en/v0.16.1/models.html).

### PS-F03 — Ограниченное число неудачных proposals не доказывает исчерпание конечного пространства

**MEDIUM · specification_ambiguity_and_discriminating_test_gap**. Пакеты: OPT-02, CTL-01. REQ: REQ-OPT-02-01. TEST: TEST-OPT-02-01. Сценарии: E02-I02-A, E02-I02-B.

**Что блокирует:** Уточнение REQ/TEST-OPT-02-01 до приёмки exhaustion semantics; не требует полного перебора больших пространств.

**Неточная/ошибочная постановка:** Спецификация направляет все branches в существующий _is_duplicate и после bounded search предлагает exhausted. Текущий owner проверяет pending, а bounded random failure не является доказанным finite-domain exhaustion; тест только tiny binary batch не различает эти случаи.

**Доказательства:**

- [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/OPT-02.md:39–42](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/OPT-02.md) — Bounded search → exhausted/repeat-intent без различения причин

- [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/OPT-02.md:67–71](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/OPT-02.md) — Binary pending/batch fixture

- [policy-engine/src/polisyos/scientist/methods/search/strategies/bayesian.py:1601–1652](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/strategies/bayesian.py) — 20 random trials, затем random; duplicate только pending, effective coordinate/replica predicates

**Различающие контрпримеры:**

- В равномерном пространстве100 действий уже99 seen. За20 независимых draws вероятность не найти единственное новое равна0.99**20≈81.79%. Возвращать finite_domain_exhausted — ложный claim.

- После tell pending опустел: копирование существующего pending-only guard во все branches само по себе позволяет заново выдать completed deterministic action как новый. Автоматически изменённый optimizer seed не всегда означает независимый stochastic MethodJob replicate.

**Реалистичные альтернативы:**

- **Bounded resampling и honest proposal_search_budget_exhausted** — Простой универсальный bounded behavior. Цена/ограничение: Может не находить существующие новые actions.

- **Enumeration для маленького finite domain + existing optimize_acqf_discrete(unique,X_avoid)** — Даёт проверяемое finite-domain exhaustion и использует уже locked dependency. Цена/ограничение: Только в заранее ограниченной cardinality/constraint-cost области.

- **Полный перебор любого mixed/continuous domain** — Нет реалистического общего преимущества. Цена/ограничение: Отвергнуть: неограниченная стоимость, неверная цель.

**Предпочтительное решение:** Единый effective-action owner учитывает pending+completed в declared evaluation basis; replicas разрешаются отдельной явной политикой. Разделить proposal_search_budget_exhausted, finite_domain_exhausted и explicit_replica. Exact finite exhaustion только при доказанном census/enumeration; большие/mixed domains сохраняют bounded attempt limit.

**Цена и компромиссы:** Повторные measurements бывают ценны: не вводить глобальный forever-dedup. Ключ включает модель/evaluation basis, действительные params и declared replica, но не cosmetic ID. Continuous values не округлять без принятого tolerances contract.

**Точный текст требования:**

> Уточнить REQ-OPT-02-01: «Все branches применяют общий effective identity к pending и completed в текущем measurement scope. Неудача bounded proposal search сообщает только budget-exhausted unless complete finite-domain census доказал отсутствие нового feasible action. Repetition имеет explicit measurement/seed provenance и не маркируется новым действием. API service сохраняет причину».

**Дополнение к проверкам:**

- Сохранить binary batch; дополнительно completed binary history после tell, constrained100-point domain с99seen, controlled20 duplicate proposals при реально свободном action.

- В последнем случае ожидать proposal_search_budget_exhausted, не finite_domain_exhausted; exact tiny enumerator обязан найти последний point и лишь затем доказать exhaustion.

- Relaxed integer aliases и category aliases дедуплицируются по actual execution; continuous distinct остаются distinct; настоящая stochastic replica допускается, cosmetic newID/optimizer RNG change не получает бесплатное исключение.

**Единый владелец:** OPT-02 existing SearchSpace/effective identity и BayesianOptimizer; CTL-01 только lifecycle projection, SRV-01 pending/tell owner.

**Что нельзя сломать:** Не превратить отказ proposal в научное утверждение о convergence; Не лишить stochastic evaluator законных повторов; Не увеличить attempt/evaluator budget скрыто.

**Валидация:** Local exact finite-domain oracle, source-level controlled proposal stream через actual suggest/service, then actual completed/tell lifecycle; optional BoTorch discrete profile тестируется отдельно.

**Предел уверенности:** Слово exhausted в delivered packet можно понимать как attempt exhaustion; finding требует убрать неоднозначность, а не обвиняет уже реализованную новую спецификацию. Product patch ещё не выполнен.

**Primary sources:** [optimize_acqf_discrete: choices, unique, X_avoid](https://botorch.readthedocs.io/en/v0.16.1/optim.html).

### PS-F04 — Детерминированный NCM comparator не различает испорченное native seed propagation

**MEDIUM · capability_test_gap_not_existing_comparator_error**. Пакеты: SIM-03. REQ: REQ-SIM-03-02, REQ-SIM-03-03, REQ-SIM-03-06. TEST: TEST-SIM-03-02, TEST-SIM-03-03, TEST-SIM-03-06. Сценарии: E02-I01-A, E02-X04.

**Что блокирует:** Блокирует расширенный claim native stochastic paired Monte Carlo; deterministic model-bound comparator и integer interaction tests сохранить и принимать в их области.

**Неточная/ошибочная постановка:** Actual NCM fixture y=u+2a+3b+4ab с evidence, фиксирующим u, доказывает контраст и interactions, но не является численным свидетельством того, что различные native seeds реально дают различные stochastic samples. Call count и seed labels отдельно не закрывают это.

**Доказательства:**

- [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/SIM-03.md:103–115](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/SIM-03.md) — Evidence фиксирует u; outcomes/effects по seeds не меняются, хотя calls считаются

- [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/SIM-03.md:135–139](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/SIM-03.md) — Joint integer fixture и positive-SE unsupported scope

- [policy-engine/src/polisyos/foundry/methods/catalog/causal/ncm_engine.py:101–147](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/ncm_engine.py) — Existing noise_expression context имеет u/noise и actual equation evaluation

- [policy-engine/src/polisyos/foundry/methods/catalog/causal/ncm_engine.py:862–890](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/ncm_engine.py) — Fresh noise sampled, но evidence overrides observed nodes

- [policy-engine/tests/unit/remediation/test_sim_03.py:201–327](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_sim_03.py) — Handwritten helper outcomes / replaced pure_step проверяют plumbing/aggregation, не native noise

- [policy-engine/tests/unit/remediation/test_sim_03.py:618–733](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_sim_03.py) — Seed-varying mocked results полезны как локальная paired-summary проверка

**Различающие контрпримеры:**

- Мутант передаёт в native engine один и тот же seed, но сохраняет запрошенные labels и вызывает backend нужное число раз. При evidence-fixed u integer fixture даёт ожидаемые2/3/9 и counts; mocked per-seed unit outputs тоже не проверяют эту native границу.

- Если effects различны, непарное вычитание может сохранять mean, но менять SE. Для baseline[-1,0,1], policy[0,2,4] правильные differences[1,2,3], SE=1/sqrt(3); reversed baseline даёт[-1,2,5], SE=sqrt(3).

**Реалистичные альтернативы:**

- **Оставить current fixture только deterministic conditional capability** — Очень сильный точный независимый oracle без arbitrary tolerance. Цена/ограничение: Не заявлять stochastic seed execution qualification.

- **Добавить tiny actual seed-sensitive model и raw draw trace** — Различает native seed propagation и pairing без нового simulator. Цена/ограничение: Нужен bounded noise/evidence profile и независимая проверка trace.

- **Только mocked varied endpoints** — Дёшево для helper boundary. Цена/ограничение: Не закрывает engine boundary; оставить как дополнение.

**Предпочтительное решение:** Добавить actual NCM noise_expression y=u+(2+u)*a при a baseline0/policy1 и явно unobserved outcome noise (evidence={} либо declared partial evidence). Через настоящий existing engine выполнить заранее заданные несколько seeds; наблюдающая wrapper только делегирует и фиксирует generated noise/roles. Независимая подстановка по сохранённым draws даёт baseline u, policy2+2u, paired effect2+u; expected mean/SE вычислить вне product helper. Проверить, что fixture действительно имеет ненулевую variation, а not fixed law from seed label. При необходимости отдельный controlled evidence heterogeneous helper witness полезен, но не заменяет same-request native stochastic test.

**Цена и компромиссы:** Малое число draws — software discrimination, не оценка population coverage/power. Нельзя ослаблять positive-SE interaction unsupported ради green. Полная empirical calibration stochastic inference требует другого evidence profile.

**Точный текст требования:**

> Дополнить REQ-SIM-03-03: «Native replication qualification содержит хотя бы один поддержанный model/evidence profile, где разные seed realizations влияют на actual endpoints и paired effects. Сохранённые raw role outcomes и seed-to-noise association проверяются независимым oracle; совпадение counts/labels без различающей numerical variation недостаточно. Deterministic comparator сохраняет свой отдельный qualification scope».

**Дополнение к проверкам:**

- Добавить к TEST-SIM-03-03 actual noise-sensitive model y=u+(2+u)*a, empty/partial evidence, bounded declared seeds, source-persisted per-role samples и fresh consumer.

- Mutation: seed argument всегда первый; replay first trajectory с изменёнными labels; permute baseline pairing; cachekey без seed. Каждая mutation ломает distinct native trace или numerical SE oracle.

- Сохранить exact integer A2/B3/joint9/no-op0/additive5/third-order1 controls; не переносить stochastic positive-SE classification в point-estimate scope.

**Единый владелец:** SIM-03 paired adapter + existing NCM noise producer; SIM-02 retains failure cause, CYC-02 exposes conditional consumer; не новый Monte Carlo framework.

**Что нельзя сломать:** Не смешать conditional abduction и population sampling; Не объявлять случайные Gaussian draws равными выбранным целым u; Не подменять actual method заранее готовыми numerical endpoints.

**Валидация:** Сначала fixture declaration и независимая formula/trace oracle; в поддержанном native runtime выполнить actual NCM→coupled adapter→CAS→fresh conditional reader плюс mutation controls. Продуктовые тесты пока NOT_RUN.

**Предел уверенности:** Чтение доказывает недостаточную различимость конкретного fixture. Не утверждается, что native engine сейчас игнорирует seed; это контрпример неправильной реализации, способной пройти текущую приёмку.

**Primary sources:** [fsum, frexp/ldexp, isfinite](https://docs.python.org/3.14/library/math.html#math.fsum).

### PS-F07 — Валидный нулевой calibration score теряется через truthiness fallback

**MEDIUM · confirmed_code_defect_omitted_by_spec_tests**. Пакеты: FUN-03. REQ: REQ-FUN-03-02. TEST: TEST-FUN-03-02. Сценарии: E02-I02-C.

**Что блокирует:** Точечное дополнение FUN-03-02 до приёмки calibration correctness; не требует redesign statistical engine.

**Неточная/ошибочная постановка:** Текущий record выбирает predicted_score or objective_value и actual_score or objective_value. Ноль — валидный score, но заменяется fallback. Новые aligned1..5/constant/ties fixtures не обязаны различать carrier fields.

**Доказательства:**

- [policy-engine/src/polisyos/scientist/methods/search/stages.py:370–393](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/stages.py) — Две or-ветви заменяют0 на objective_value до record append

- [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/FUN-03.md:47–50](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/FUN-03.md) — Typed availability не исправляет выбор численного carrier

- [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/FUN-03.md:77–81](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/FUN-03.md) — Нет explicit zero-versus-distinct-fallback witness

- [policy-engine/src/polisyos/scientist/methods/search/stage_contracts.py:23–61](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/stage_contracts.py) — StageResult score carriers float|None; admission/state rules remain mandatory

- [policy-engine/src/polisyos/scientist/methods/search/objective.py:1146–1158](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/objective.py) — Unbound diagnostic objective rejects bool/nonfinite; generic numeric type has no nonnegative lower bound

**Различающие контрпримеры:**

- Actual pairs predicted=[0,1,2], truth=[0,1,2], но первый fallback objective_value=3. Правильный Spearman=1; record превращает prediction в[3,1,2] и rho=-0.5. Нулевой actual_score имеет симметричную проблему.

**Реалистичные альтернативы:**

- **Explicit is not None plus typed finite value admission** — Минимальное исправление exact root cause. Цена/ограничение: Нужны tests обоих carriers и явная compatibility policy.

- **Всегда objective_value** — Просто. Цена/ограничение: Неправильный source, скрывает intended predicted/actual score.

- **Новая metrics library** — Не решает input selection. Цена/ограничение: Лишняя зависимость.

**Предпочтительное решение:** В существующем CorrelationTracker.record выбирать named score при is not None, не truthiness; затем validate numeric type/finite и declared score basis до append. Ноль/negative остаются значениями; None — availability. Если objective_value имеет иной units/direction basis, не fallback без declared conversion/admission. Не расширять domain: negative допускается только там, где это разрешено существующим concrete score profile; status/source-admission validation сохраняется. Более широкие malformed-carrier guards — согласованное typed boundary hardening, не причина менять domain law.

**Цена и компромиссы:** Старые ошибочно записанные records нельзя исправить без source evidence; legacy snapshots помечать старой metric extraction version, не выдумывать true historical values.

**Точный текст требования:**

> Добавить REQ-FUN-03-02: «record сохраняет explicit finite predicted_score/actual_score, включая +0.0/-0.0 и уже допустимые конкретным score profile negative values; domain/admission guards не ослабляются. Fallback применяется только при None и при совместимом score basis. Malformed/nonfinite pair не изменяет corpus; reason source-bound. Extraction version сохраняется в snapshot».

**Дополнение к проверкам:**

- Предъявить distinct carriers: predicted0/fallback3, actual0/fallback3; independent rank oracle даёт expected1 вместо-0.5.

- Проверить None fallback, finite negative, ±0, malformed bool/string/NaN/Inf и atomic no-append; граница bool определяется strict metric schema.

- Actual tracker→snapshot→fresh report/routing сохраняет0 и согласованный extraction version; прежние aligned/inverse/ties/constant controls остаются.

**Единый владелец:** FUN-03 CorrelationTracker.record; единый extraction contract для compute/routing/report, не второй converter.

**Что нельзя сломать:** Не спутать missing и0; Не перемешать разные units/directions carrier fields; Не мигрировать ошибочные historical observations без source reconstruction.

**Валидация:** Independent arithmetic уже выполнена только stdlib; product regression NOT_RUN. Потом exact local record fixture и native pipeline readback.

**Предел уверенности:** Code defect непосредственно подтверждён. Масштаб влияния на реальные отчёты неизвестен; actual snapshot corpus не исполнялся/не анализировался.

**Primary sources:** [fsum, frexp/ldexp, isfinite](https://docs.python.org/3.14/library/math.html#math.fsum).

### PS-F08 — Native NCM тратит100000 global random draws на normal quantile каждого вызова и делает CI зависимым от ambient RNG

**MEDIUM · confirmed_native_numerical_reproducibility_and_unnecessary_work_defect**. REQ-SIM-03-01 / TEST-SIM-03-01 / I01-A.

**Что блокирует:** Адресный supporting numerical-owner repair SIM-03-01; не блокирует сам correct paired endpoint mean и не превращает normal quantile fix в универсальный inference framework.

**Ошибка:** Статический normal quantile вычисляется как percentile100000 случайных normal draws через global np.random, хотя actual model simulation использует request-local seeded RNG. Delivered finite/paired tests не проверяют это supporting native work и replay CI.

**Source evidence:**

- [policy-engine/src/polisyos/foundry/methods/catalog/causal/ncm_engine.py:1050–1097](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/ncm_engine.py) — Model worlds связаны с request seed через np.random.default_rng

- [policy-engine/src/polisyos/foundry/methods/catalog/causal/ncm_engine.py:1099–1119](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/ncm_engine.py) — Unconditional100000 global draws, percentile, std ddof0 и CI bounds

- [policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py:2880–2907](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py) — Каждая N5 replication вызывает native NCM с n_samples1 и своим seed

- [policy-engine/tests/unit/foundry/methods/catalog/causal/test_ncm_engine.py:524–559](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/methods/catalog/causal/test_ncm_engine.py) — Existing pure_step tests проверяют keys/counts/finite mean/serialization, не ambient RNG или CI reproducibility

- [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/SIM-03.md:55–58](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/SIM-03.md) — Finite paired-helper solution не охватывает лишний random quantile computation

**Контрпримеры:**

- Один и тот же request seed при n_samples>1 и ненулевой variation воспроизводит model worlds, но разные ambient global NumPy RNG states меняют z и ci_lower/ci_upper. Время выполнения исключается из replay comparison как diagnostic, CI — нет.

- В N5 n_samples1 даёт std0: quantile вообще не влияет на mean/endpoint, но каждый physical call всё равно создаёт100000 unrelated draws. Для3/6/9 физических calls это300000/600000/900000 лишних quantile draws, не requested model samples. Это source-derived work count, не измеренное ускорение.

**Альтернативы:**

- stdlib statistics.NormalDist.inv_cdf: Детерминированный normal quantile без новой зависимости и MC work; Требуется bounded confidence domain и numerical profile

- existing SciPy norm.ppf/isf: Та же семантика в уже locked numerical stack; Для scalar quantile более тяжёлый import; можно переиспользовать уже загруженный module

- Оставить Monte Carlo z, но seed его отдельно: Улучшит replay; Лишняя работа и approximation остаются; не предпочтительно

**Решение:** Заменить случайную аппроксимацию normal quantile детерминированным existing stdlib/SciPy inverse-normal. После finite0<confidence<1 validation использовать stable lower-tail expression -NormalDist().inv_cdf((1-confidence)/2) либо norm.isf((1-confidence)/2), а не upper probability, округляющуюся к1. Не менять request-local model RNG и результаты world simulation. Отдельно явно определить estimand/qualification interval: нынешние ddof0 и n1 zero-width не доказывают measured certainty; bounded compatibility DEC сохраняет paired endpoint path и legacy history, не вводит новый inference engine. Для confidence0.50/0.80/0.95/0.99 и nextafter(1,0) independent CDF/erfc oracle должен отвергать constant z=1.96. Tiny positive confidence, чья float tail projection схлопнулась к0.5, не получает fabricated qualified zero-width CI. По actual DTO сохранять mean/trajectory/n, ограничивая interval; если unavailable interval не представим в legacy schema, DEC выбирает explicit compatibility/versioned projection, не unconditional отказ всей paired simulation.

**Компромисс:** Исправление убирает гарантированную source-level лишнюю работу и ambient RNG mutation; wall-clock benefit не измерен. Детерминированный z не исправляет sampling bias, малый n, неизвестную variance или causal identification. Глобальная стандартизация CI всех методов не нужна.

**Точное требование:**

> Дополнить REQ-SIM-03-01: «Supporting NCM normal quantile детерминирован при объявленном confidence, не вызывает auxiliary global RNG и не добавляет simulated draws сверх модели. Legitimate world-noise request-owned RNG сохраняется. Confidence finite и строго между0 и1; stable lower-tail inversion и declared numerical profile определяют supported interval. Несколько confidence levels и near1/tiny boundaries проверяются независимо. Numerical mean/trajectory/n и paired endpoints сохраняются, где это позволяет actual result contract; interval estimand, singleton/ddof policy и legacy compatibility ограничены DEC-SIM-03-02. Tiny-level unrepresentability/n1 zero-width не qualifies uncertainty и не создаёт blanket отказ полезной simulation».

**Проверки:**

- Actual NCM variable-noise profile с n_samples>1: same request seed при разных ambient global RNG states даёт одинаковые numerical world summaries/CI; global RNG state до/после actual call неизменен. Timing diagnostic исключить явно.

- Spy/trap global np.random.standard_normal обнаруживает прежние100000 quantile draws, не подменяя request-local rng.normal numerical producer. n_samples1 не запускает этот лишний MC; actual requested model draws сохраняются.

- Confidence0.50/0.80/0.95/0.99 плюс nextafter(1,0): независимый normal-CDF/erfc residual или high-precision reference с заранее выбранной float64 bound проверяет quantile; hardcoded1.96 и upper-tail rounding-to1 проваливают oracle. Invalid0/1/out-of-range/NaN/Inf не дают qualified interval. Tiny positive=nextafter(0,1) выявляет collapse tail0.5 и должен получить explicit unsupported interval/profile, не ложную certainty. Mean/paired samples сохраняются по совместимому contract.

- Singleton, ddof0 legacy и tiny-level boundary ограничивают только interval claim, где actual DTO это позволяет; mean/trajectory/n и paired endpoint продолжают быть полезными. При недостаточной legacy schema DEC-SIM-03-02 выбирает explicit compatibility/versioned projection. Исторические intervals не переписываются и не становятся автоматически empirical uncertainty.

**Owner:** SIM-03 existing NCMEngineMethod.pure_step numerical summary; existing statistics/SciPy API. DEC-SIM-03-02 только interval semantic/compatibility boundary, не новый statistical registry.

**Сохранить:** Не менять seeded model draws и N5 paired means ради supporting quantile; Не присвоить confidence coverage guarantee после замены одной функции; Не переписать old CI bytes под прежней version; Не ослабить finite checks и positive-SE interaction guard

**Валидация:** Источник и arithmetic рассмотрены; product NOT_RUN. Native actual method replay/RNG-isolation/work-counter controls плюс fresh persisted consumer и interval compatibility decision; поддержанный dtype/backend явно фиксируются.

**Ограничение:** Сам100000/global-RNG path подтверждён чтением и root review; реальные latency и downstream CI consumer prevalence не измерялись. Статистическая корректность всех NCM intervals отдельно не объявляется установленной.

**Primary sources:** [NormalDist.inv_cdf: deterministic inverse normal CDF](https://docs.python.org/3.14/library/statistics.html#statistics.NormalDist.inv_cdf); [norm.ppf/isf deterministic inverse CDF/survival function](https://docs.scipy.org/doc/scipy-1.16.0/reference/generated/scipy.stats.norm.html).

## 2. Все 27 пакетных решений — содержательные verdicts

### CYC-01 · LANE-01 · bounded qualification

**Техника и root cause:** Правильная точка ремонта — ordinary HTTP/job→postcompile leaf context→existing generation cycle/N5. Нельзя заполнять producer-required context caller constants или проходить только preconfigured test entry. Сохранять existing compiler/gateway, не вводить universal request engine.

**Полезная способность/free-grow:** Полезность — один фактический модельный расчёт обычного запроса и сохранённые ограничения. Второй materially different profile должен изменить variable/outcome/time/model resource, а не UUID. Подготовка fixtures раскрывается; compatible resource через общий путь, не case dispatch.

**Достоверность проверки:** Served fixture сейчас наблюдает настоящий producer, но selected candidate-only path имеет N8/N9 traps: это полезный N5 witness, не full N8/N9 acceptance. Проверить ordinary request без специального safety_attempt_context, then fresh N5/N8 reader на разрешённом conditional path. Always-refuse не проходит positive.

**Стоимость и библиотека:** Переиспользовать HTTP/compiler/N5 tests; lightweight transport/LLM double допустим, numeric/source owner — нет. Не запускать весь CI на каждую ветвь.

**Сохранить и ограничить:** Loaded model и request basis связаны; synthetic K_sim не empirical forecast и не authority. Actual actor/tenant prerequisites нельзя обойти ради green.

Полный исходный packet: [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/CYC-01.md](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/CYC-01.md). Actual owner read ranges: [coverage](coverage.json), [извлечённые диапазоны](owners_CYC-01.txt).

### REQ-01 · LANE-01 · retain

**Техника и root cause:** Общий normalizer вместо локальных alias tables — верно. Unknown domain сохраняется CUSTOM/raw, а не education_policy→fiscal default. Compiler-bound requirement set требует census top-level constructs и DEC, не произвольного счётчика user syntax.

**Полезная способность/free-grow:** Способность — принять новый смысл без переименования в известный домен, сохранить unresolved и позволить resolver получить ресурс. Это open-world input representation, не обещание универсального метода для любого текста.

**Достоверность проверки:** Тестировать absent/custom/explicit-domain, эквивалентные aliases, unknown_construct и raw spec unbound. Неправильный normalizer, всегда выдающий CUSTOM, проходит unknown-negative, но ломает supported positive; обе ветви нужны. Independent intent fixture должен отличать label от semantic denominator.

**Стоимость и библиотека:** Existing compiler/types/resolver достаточно; NLP framework/library swap не решает ontology/denominator. Normalize once на ownership boundary.

**Сохранить и ограничить:** Не превращать unresolved в silent empty requirements; не запретить useful partial interpretation. Source/status counts и pre-existing compiler semantics сохранять.

Полный исходный packet: [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/REQ-01.md](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/REQ-01.md). Actual owner read ranges: [coverage](coverage.json), [извлечённые диапазоны](owners_REQ-01.txt).

### CYC-03 · LANE-01 · retain

**Техника и root cause:** Сильный contract: full semantic basis для numerical reuse, current cheap gates для каждого re-entry. Grammar hints — не semantic basis; current occurrence должен обновляться даже при worsening, immutable historical result остаётся доступным.

**Полезная способность/free-grow:** A→B→B→B→C демонстрирует развитие знания без лишнего вычисления на равном B и без stale reuse по C. Переносимая replica требует собственных source refs, не same hash as proof.

**Достоверность проверки:** Содержательный oracle — measured producer-call counts плюс unchanged raw result и changed current decision. Wrong whole-ticket cache может пройти numerical equality, поэтому повторить budget/access/epoch gate при unchanged B; perturb one true basis field triggers actual reexecution.

**Стоимость и библиотека:** Один existing basis/cache owner дешевле второго planner cache. Counter дорогой работы отделён от current validation calls.

**Сохранить и ограничить:** Нельзя history overwrite или объявить latest=best ever. Authority unknown ограничивает dependent act, не читабельность истории.

Полный исходный packet: [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/CYC-03.md](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/CYC-03.md). Actual owner read ranges: [coverage](coverage.json), [извлечённые диапазоны](owners_CYC-03.txt).

### ACQ-01 · LANE-01 · bounded qualification

**Техника и root cause:** Actual requirement/planner refs→selected source reread/admission→DataForge/Fabric/Foundry WMR→N5 — правильная producer chain. Multirow source требует units/time/population/aggregation; брать первую строку или mean arbitrary vector недопустимо.

**Полезная способность/free-grow:** Новый compatible resource должен изменить исполняемую модель/оценку через contract. Второй domain LA-046 нужен для transfer; нельзя считать новый source label при прежнем hardcoded coefficient свободным ростом.

**Достоверность проверки:** Сохранять actual CAS/owner read, сравнить values/model lineage before/after acquisition. Concurrent stale completion не publish current; malformed source не уничтожает независимый useful branch. Oracle formula следует из fixture rows и law, не product adapter.

**Стоимость и библиотека:** Bound acquisition calls/bytes/rows; no paid provider required. Existing bridges лучше нового data bus. Изначально согласованный cost budget общий, retry не бесплатен.

**Сохранить и ограничить:** Источник доступен только authorised test tenant; source admission не автоматически empirical transportability. Missing aggregation — explicit unresolved.

Полный исходный packet: [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/ACQ-01.md](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/ACQ-01.md). Actual owner read ranges: [coverage](coverage.json), [извлечённые диапазоны](owners_ACQ-01.txt).

### CYC-04 · LANE-01 · retain

**Техника и root cause:** Правильно различены late candidate-local failure с bounded next viable candidate и global resource/authority failure. SIM01 alternate engine — иной уровень fallback, дублировать queue owner не надо. Value of information должен учитывать реальные cost/origin и declared reserve.

**Полезная способность/free-grow:** Полезность — система продолжает подходящий следующий шаг вместо stale winner или тотального отказа. Рабочая alternative и информативный probe под ресурсом показывают инициативу, но не научную optimality произвольного ROI.

**Достоверность проверки:** Positive late-failure→second candidate, negative global cap→zero extra work; mutate both later N5/N8 eligibility и value-proxy. Always choose first/always explore/always stop должны различаться. Cost source отсутствует — не выдумывать0USD.

**Стоимость и библиотека:** Bounded queue/candidate scan, explicit exploration reserve only if configured. Не привлекать reinforcement-learning planner для локального selection repair.

**Сохранить и ограничить:** Нет automatic cap bypass; уже произведённый useful result и continuation reason сохраняются; measured wall time и monetary estimate не взаимозаменяемы.

Полный исходный packet: [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/CYC-04.md](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/CYC-04.md). Actual owner read ranges: [coverage](coverage.json), [извлечённые диапазоны](owners_CYC-04.txt).

### CYC-02 · LANE-01 · bounded qualification

**Техника и root cause:** Legacy N5 v1–3 read и fresh conditional N8 view заслуживают отдельной acceptance, а не переписывания legacy serializer. Unsupported interaction marker и selected-view signature repair сохраняют честную ограниченность.

**Полезная способность/free-grow:** Полезный conditional result должен доходить до пользователя даже без empirical/authority upgrade. Same-data fresh consumer доказывает custody+presentation, но не causality модели.

**Достоверность проверки:** Пройти actual persisted current/legacy result и процесс без shared in-memory objects. Wrong view deriving all values from latest caller context не поймается roundtrip одного объекта; менять context/selected ref и перечитывать old snapshot.

**Стоимость и библиотека:** Existing projection/reader reuse; нет причины мигрировать все artifacts или numerical engine.

**Сохранить и ограничить:** No empirical/N9 inference из K_sim. Missing/unsupported поле остаётся structured limitation, не fabricated0.

Полный исходный packet: [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/CYC-02.md](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/CYC-02.md). Actual owner read ranges: [coverage](coverage.json), [извлечённые диапазоны](owners_CYC-02.txt).

### CYC-05 · LANE-01 · bounded qualification

**Техника и root cause:** Child-denominator/cost/frontier stop contracts и actual build readiness issuer — правильное разделение. Authored compound требует joint SIM03, alternatives не compound. Existing confidence_ledger назначает evidence; self-manifest/PASS constant не issuer.

**Полезная способность/free-grow:** Способность — сохранить полезный partial frontier, объяснить ресурсную остановку и иметь действительный технический readiness route. Это не mandatory policy enactment и не institutional authority.

**Достоверность проверки:** Положительный loaded-build issuer→current verifier, negative stale/unappointed/changed baseline; budget refusal сохраняет child result, не success empty frontier. Joint authored alternatives различить по model result, не двум merged JSONs. Базовый dependency LANE12 сохраняется.

**Стоимость и библиотека:** Exact small child census, actual calls/time resource. Не превращать каждую tiny change в distributed attestation service.

**Сохранить и ограничить:** Budget stop vs abstain vs scientific exhaustion различны; readiness permit не FUN03 promotion permit.

Полный исходный packet: [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/CYC-05.md](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/CYC-05.md). Actual owner read ranges: [coverage](coverage.json), [извлечённые диапазоны](owners_CYC-05.txt).

### SIM-01 · LANE-01 · retain

**Техника и root cause:** Engine-owned required input validation до selection и exact supported plan identity — точный repair. Optional defaults должны оставаться optional; missing required vector нельзя прятать generated0 или exception broad fallback.

**Полезная способность/free-grow:** Fallback полезен только если alternate actual producer вычисляет тот же declared estimand, а не выдаёт произвольную finite scalar. Модель/units/horizon obligations должны пережить смену engine.

**Достоверность проверки:** Primary unavailable + actual supported alternate positive; missing required input before expensive call; wrong alternate estimand rejected. Реальный registry/plan resolver и producer не stub. Cases with valid optional omission не должны отказываться.

**Стоимость и библиотека:** Cheap validation экономит expensive native work; existing engine registry достаточен. Не делать universal vector-default framework.

**Сохранить и ограничить:** No engine choice based on fixture ID. Caller supplied ref не proof numerical compatibility; unsupported path остаётся addressable.

Полный исходный packet: [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/SIM-01.md](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/SIM-01.md). Actual owner read ranges: [coverage](coverage.json), [извлечённые диапазоны](owners_SIM-01.txt).

### SIM-02 · LANE-01 · retain

**Техника и root cause:** Typed resolved path tokens устраняют смешение listindex и mappingkey. .0/.00/+0 aliases и negative list index нуждаются в canonical resolution, но dictionary string keys сохраняются. Temporal coordinates и aggregation law — input semantics, не scalar fallback.

**Полезная способность/free-grow:** Общая path/temporal семантика позволяет новым compatible models работать без ручных case branches; actual selected simulation plan исполняется единожды, cause/result сохраняются.

**Достоверность проверки:** Mutation equivalent alias conflicting writes, list negative alias, dictionary key0, horizon mismatch, sparse time без hold-last. Actual engine exception/cause through retained result. Wrong deep copy / last-write implementation различить shared alias and original snapshot invariance.

**Стоимость и библиотека:** Typed narrow updates лучше deepcopy entire runtime object. Stable finite checks до/после numerical operations; no generic temporal imputation library needed.

**Сохранить и ограничить:** Не превращать failed model в estimated0; нет arbitrary mean of vector. Existing legitimate scalar mapping и optional defaults сохранять.

Полный исходный packet: [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/SIM-02.md](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/SIM-02.md). Actual owner read ranges: [coverage](coverage.json), [извлечённые диапазоны](owners_SIM-02.txt).

### SIM-03 · LANE-01 · targeted revision

**Техника и root cause:** Delivered finite paired endpoint/mean/SE boundaries, SMM uniqueness before dict, local physical cache и full joint residual — сильные решения. Детерминированный integer NCM independent oracle точен, но actual seed-sensitive numeric witness отсутствует в конкретном positive fixture (PS-F04).

**Полезная способность/free-grow:** Доказуемая capability: supported model-bound conditional contrast, actual compound effect и typed uncertainty, не universal causal truth. Seed-sensitive extension делает replicated numerical path переносимее; arbitrary nonzero-SE inference пока unsupported.

**Достоверность проверки:** Сохранить exact no-op0/A2/B3/joint9/residual4, additive5, third-order1; helper differences[1,3]→mean2/SE1. Добавить actual varied noise and pairing trace, first-seed replay и baseline permutation mutations; counts alone недостаточны.

**Стоимость и библиотека:** Existing NCM/paired helper/SMM owners, no new simulator. Bound sample work, distinguish physical cache reuse vs independent samples. float64 verified, general tolerance DEC predeclared.

**Сохранить и ограничить:** Positive SE не magically additive; 4+ aggregate residual не полная interaction decomposition. n1 SE=None и incomplete planned/completed denominator сохранить.

Связанные выводы: PS-F04, PS-F08. Native NCM supporting quantile/RNG/interval qualification дополнительно разобраны в PS-F08.

Полный исходный packet: [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/SIM-03.md](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/SIM-03.md). Actual owner read ranges: [coverage](coverage.json), [извлечённые диапазоны](owners_SIM-03.txt).

### SEL-01 · LANE-01 · retain

**Техника и root cause:** Lexical category/technical ID не должны становиться hard modality filter. Правильно объяснять первый реально различающий lexicographic rank key и сохранять full excluded denominator до topk.

**Полезная способность/free-grow:** Новые compatible methods/resources допускаются по contracts, не красивому name. Singleton допустим; absence alternatives — limitation, не automatic refusal.

**Достоверность проверки:** Полезны actual singleton и скрытый eligible member за topk controls. Wrong reason от последнего score-key поймать ties-prefix example; wrong prefilter lexicalcategory поймать semanticallycompatible differentlynamed method. Downstream actual value consumer обязателен.

**Стоимость и библиотека:** Existing registry/ranker cheap; no recommender/embedding framework. Full census bounded registered catalog, не весь мир.

**Сохранить и ограничить:** Не создавать generic unit converter под selection; units/admission остаются owners. Excluded reasons source-bound, rank не epistemic proof.

Полный исходный packet: [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/SEL-01.md](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/SEL-01.md). Actual owner read ranges: [coverage](coverage.json), [извлечённые диапазоны](owners_SEL-01.txt).

### CTL-01 · LANE-02 · retain

**Техника и root cause:** Привязка к run/generation и финализация после error/cancel принадлежат существующему lifecycle owner. Уже полученная работа, её стоимость и исходная ошибка должны сохраняться. Ограниченное число пустых proposals означает остановку генератора, а не научную сходимость.

**Полезная способность/free-grow:** Способность — завершить одно исследование и начать другое без попадания позднего tell в чужое состояние. Положительный допустимый ответ своего run также должен приниматься: изоляцию нельзя реализовать отбрасыванием всех ответов.

**Достоверность проверки:** Нужны синхронизированные controls: старый pending tell после нового run, отмена после evaluation, ошибка при cleanup и повторные пустые proposals. Проверять actual history, incurred cost и исходную exception, а не только terminal status.

**Стоимость и библиотека:** Небольшие owned snapshots, подготовка вне lock и короткий commit достаточны. Model-based Hypothesis sequences дополняют, но не заменяют race barriers и actual consumer.

**Сохранить и ограничить:** Не терять затраченную работу при сбое финализации; не зацикливать idle loop. Термин exhaustion согласовать с PS-F03.

Полный исходный packet: [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/CTL-01.md](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/CTL-01.md). Actual owner read ranges: [coverage](coverage.json), [извлечённые диапазоны](owners_CTL-01.txt).

### CTL-03 · LANE-02 · retain

**Техника и root cause:** Разделение sentinel quota, stage-B denominator и обычных optimization iterations корректно. Общий work cap учитывает все исполненные оценки. Invalid typed assessment нельзя превращать в legacy missing и принимать удобный scalar.

**Полезная способность/free-grow:** Поиск расходует бюджет на новую работу, а не считает warm history новыми evaluations. Sentinel остаётся полезным контрольным примером, но не обучающей строкой или автоматически promotable candidate.

**Достоверность проверки:** Через настоящий dispatcher проверить warm rows, sentinel work, invalid typed finite scalar и допустимый legacy fallback. Oracle считает фактические вызовы и training rows; общий cap запрещает скрытый дополнительный dispatch.

**Стоимость и библиотека:** Один existing budget owner и строгая validation до дорогого evaluator достаточны. Новый scheduler не нужен; boolean не следует принимать за числовой budget.

**Сохранить и ограничить:** Нельзя сделать sentinel бесплатным через обычный iteration counter. Калибровочная гарантия пропуска полезных кандидатов относится к FUN-03, а не к счётчику работы.

Полный исходный packet: [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/CTL-03.md](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/CTL-03.md). Actual owner read ranges: [coverage](coverage.json), [извлечённые диапазоны](owners_CTL-03.txt).

### SRV-01 · LANE-02 · retain

**Техника и root cause:** Переход pending→applying→completed с prepare/commit на одном owner устраняет double tell. Immutable delta готовится вне lock; проверка current state и commit выполняются вместе. Внешние callbacks под lock не нужны.

**Полезная способность/free-grow:** Goal и SearchSpace реального request должны дойти до поиска. Повтор tell идемпотентен, foreign-run ответ не применяется, допустимый поздний ответ своего run не теряется.

**Достоверность проверки:** Положительный service/evaluator путь, competing tells, prepare failure и reentrant callback проверять по history, objective и cost exactly once. Одного pending_count=0 недостаточно: он допускает двойное применение результата.

**Стоимость и библиотека:** Leaf contracts, lazy imports и сохранённые aliases лучше нового transaction framework. Lightweight facade не должен загружать тяжёлый GP stack без необходимости.

**Сохранить и ограничить:** Сохранить исторические import/module addresses и смысл входной цели. Pending reservation сама по себе не является external-effect transaction или authority.

Полный исходный packet: [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/SRV-01.md](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/SRV-01.md). Actual owner read ranges: [coverage](coverage.json), [извлечённые диапазоны](owners_SRV-01.txt).

### SRV-03 · LANE-02 · bounded qualification

**Техника и root cause:** Role metadata должна пройти codec→BenchmarkEvaluation→history. Actual SearchLoopRunner partial persistence/resume закрывает LA-015 содержательно, не новым именем DTO. Reserved semantic field удалять только по конкретному codec contract.

**Полезная способность/free-grow:** Обычный candidate и sentinel проходят настоящего producer, но sentinel не получает promotion eligibility. Сохранённая история должна быть полезна после restart, а не только живому объекту.

**Достоверность проверки:** Нужны actual MethodJob/codec positive, подмена роли sentinel, ошибка посреди run после оплаченной evaluation и fresh resume. Самостоятельно выданный warm label не заменяет selected source qualification; перед cutover нужен caller census.

**Стоимость и библиотека:** Использовать текущие runner, persistence и role envelope. Второй lifecycle registry лишь увеличит риск рассогласования; дорогой partial result производится один раз.

**Сохранить и ограничить:** CTL-01 не закрывает LA-015 целиком. Сохранить исходную ошибку и различие eligible/noneligible history.

Полный исходный packet: [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/SRV-03.md](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/SRV-03.md). Actual owner read ranges: [coverage](coverage.json), [извлечённые диапазоны](owners_SRV-03.txt).

### CTL-02 · LANE-02 · retain

**Техника и root cause:** Raw subject identity не должна терять предметные date/timestamp поля под видом volatile metadata. Исключения принадлежат явному envelope contract. Staged RNG/Sobol/base-state validation до commit сохраняет живое состояние при отказе.

**Полезная способность/free-grow:** Whole/split replay позволяет действительно продолжить вычисление. Изменение семантической даты должно менять identity; неизвестная schema не становится current-compatible лишь потому, что JSON удалось прочитать.

**Достоверность проверки:** Проверить RNG cursor625, finite Gaussian cache, malformed snapshot поверх действующего state, equality следующего proposal и subject-date mutation. Только fresh empty owner не обнаруживает уничтожение прежнего состояния при неудачном restore.

**Стоимость и библиотека:** Сохранить stdlib RNG и SciPy Sobol; incremental generation/fast_forward не повторяют весь prefix на каждом шаге. Arbitrary prefix не получает автоматически power-of-two QMC balance guarantee.

**Сохранить и ограничить:** Unknown fields не удалять молча из identity. CTL-02 владеет base restore, OPT-03 — GP staging поверх него, без второго RNG codec.

Полный исходный packet: [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/CTL-02.md](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/CTL-02.md). Actual owner read ranges: [coverage](coverage.json), [извлечённые диапазоны](owners_CTL-02.txt).

### STP-01 · LANE-02 · retain

**Техника и root cause:** Атомарное принятие metric+embedding и численно устойчивые plateau/cosine проверки соответствуют root cause. Drafter использует current admitted observation; отвергнутый embedding не должен влиять на будущую остановку.

**Полезная способность/free-grow:** Полезная остановка по эвристической стабильности или ресурсу сохраняется, но не объявляется доказательством глобального оптимума. Недоступная метрика ограничивает конкретный вывод, а не обязательно всё исследование.

**Достоверность проверки:** Проверить extreme magnitudes, zero vector, NaN, stale/current drafter и деление на малый scale. Always-stop должен провалить улучшающийся positive case, always-continue — обязательный resource stop.

**Стоимость и библиотека:** Масштабно-устойчивая algebra из stdlib/NumPy достаточна; отдельная stopping library не нужна. Property cases полезны как дополнение маленьким exact counterexamples.

**Сохранить и ограничить:** Threshold и heuristic profile версионировать; budget, heuristic stop и producer unavailability имеют разные причины.

Полный исходный packet: [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/STP-01.md](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/STP-01.md). Actual owner read ranges: [coverage](coverage.json), [извлечённые диапазоны](owners_STP-01.txt).

### OPT-01 · LANE-02 · retain

**Техника и root cause:** Полная неизменяемая coordinate schema (metric/split/unit/direction) до dominance и реальный registry после round-trip — правильное решение. Исправленный strict skyline следует квалифицировать независимым slow oracle, не переписывать. Fiscal stock/flow DEC не должен объявлять разные quantities конфликтом.

**Полезная способность/free-grow:** Из измерений получается полезный partial Pareto front, а не claim «все политики рассмотрены». Новые objectives входят через явный measurement law/resource, не через совпадение ключей.

**Достоверность проверки:** Сетка, permutations, ties, partial inputs и caller alias mutations хорошо различают неверный comparator. Delivered TEST06 уже содержит 3D exact28 против bbox1000 и actual ranking consumer; повторная находка снята. Источник split/units должен быть настоящим.

**Стоимость и библиотека:** Сохранить быстрый skyline и точный 2D union. Если consumer действительно требует higher-dimensional exact HV, использовать уже locked pymoo/BoTorch (PS-L06), не новый алгоритм. Обязательного unit-library rewrite нет.

**Сохранить и ограничить:** Frozen DTO не делает вложенные dict неизменяемыми: копировать только маленький contract. Reference входит в comparison basis; динамический reference не даёт сравнимого cross-run improvement.

Полный исходный packet: [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/OPT-01.md](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/OPT-01.md). Actual owner read ranges: [coverage](coverage.json), [извлечённые диапазоны](owners_OPT-01.txt).

### OPT-02 · LANE-02 · targeted revision

**Техника и root cause:** Canonical actual params до training, typed fallback и source-bound MethodJob route корректны. Дополнить pending-only identity denominator и различить bounded proposal failure от доказанного finite-domain exhaustion (PS-F03).

**Полезная способность/free-grow:** Поиск должен выдавать реальные различные typed actions, сохраняя оправданные независимые stochastic replications. Отсутствующий GP backend не должен выключать exploration.

**Достоверность проверки:** Binary batch необходим, но case99/100 и completed history обнаруживают ложный exhausted. Нужны actual mixed/log/category SearchSpace и method source; syntactic artifact ID сам по себе не measurement.

**Стоимость и библиотека:** Для маленького finite domain доступен existing BoTorch discrete optimizer. Полный перебор большого mixed domain не требуется. LogEI experiment из PS-L02 — optional, не prerequisite этого repair.

**Сохранить и ограничить:** Continuous не округлять без принятого tolerance. Unitless candidate остаётся exploratory без GP admission; unit/closed-holdout guards сохраняются.

Связанные выводы: PS-F03.

Полный исходный packet: [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/OPT-02.md](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/OPT-02.md). Actual owner read ranges: [coverage](coverage.json), [извлечённые диапазоны](owners_OPT-02.txt).

### OPT-03 · LANE-02 · retain with separate bounded redesign decision

**Техника и root cause:** Исправление cap1/recent_n=0 и atomic GP staging точны. Уже существующая learned-state проверка сильна: настоящий RBF/ConstantMean, независимый NumPy Cholesky и removal mutations для model/transform. Conditioned-fit lineage/full-refit DEC необходим.

**Полезная способность/free-grow:** Нынешний fitted-native profile квалифицируется самостоятельно. Strategy-neutral measured-observation reuse PS-F02 — отдельная opt-in capability; она не ослабляет guard и не блокирует текущий local DoD. Измерение и surrogate prediction — разные сущности.

**Достоверность проверки:** Сохранить 8→9→12 append, modified-prefix refit, scheduled boundary, failed restore поверх live state и actual posterior. Fresh source verifier принимает только воспроизводимый continuation profile либо явно ограниченный full refit.

**Стоимость и библиотека:** Стоимость dense GP ограничена cap и измеряется. Новый GP framework не нужен. Replay исходного fit может быть дорогим; отдельный measurement profile при выборе способен избежать ненужного source-fit replay, но target fit учитывается.

**Сохранить и ограничить:** Cold rows не переименовываются в fitted sources. Валидность model state не заменяет валидность source measurement.

Связанные выводы: PS-F02.

Полный исходный packet: [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/OPT-03.md](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/OPT-03.md). Actual owner read ranges: [coverage](coverage.json), [извлечённые диапазоны](owners_OPT-03.txt).

### OPT-04 · LANE-02 · retain

**Техника и root cause:** Сравнение objective basis до incumbent number, настоящее измерение initial baseline и multiprocess stable flock + atomic pointer соответствуют проблеме. Permissive source stub не квалифицирует действительную оценку.

**Полезная способность/free-grow:** Champion выбирается по одному понятному comparison contract. Цель может измениться через явный transition/reevaluation; stale incumbent не переносится молча. Это технический результат, не institutional policy act.

**Достоверность проверки:** Нужны competing-process barrier, stale basis, finite actual score positive и fresh pointer reader. Missing baseline вызывает measurement, не invented zero. Atomic rename без serialization проходит single-process case, но не lost-update control.

**Стоимость и библиотека:** Local POSIX file owner достаточен для заявленного профиля. Distributed DB/lock нужен только при иной архитектурной потребности; fsync требуется отдельно, если заявлена crash durability.

**Сохранить и ограничить:** Стабильный lock inode отделён от заменяемого pointer; same-filesystem replace. Windows/NFS не считаются квалифицированными. FUN-03 permit не равен champion lock.

Полный исходный packet: [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/OPT-04.md](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/OPT-04.md). Actual owner read ranges: [coverage](coverage.json), [извлечённые диапазоны](owners_OPT-04.txt).

### FUN-01 · LANE-02 · retain

**Техника и root cause:** Immutable numerical source cache и fresh gate каждого attempt разделены правильно. Изменение basis создаёт linked successor; terminal old attempt не открывается заново. Полная lineage предотвращает подмену истории.

**Полезная способность/free-grow:** Система экономит фактические same-basis computations и продолжает работу после нового evidence/access/budget. Cached number не отменяет current policy.

**Достоверность проверки:** Full-versus-bound A/B проверяется по actual work/cost. Изменить gate при том же numerical basis, создать successor после terminal и испортить source ref. Whole-ticket cache может сохранить число, но обязан провалить fresh-gate control.

**Стоимость и библиотека:** Переиспользовать exact immutable refs; численные вычисления считать отдельно от cheap gate reads. Второй attempt ledger не нужен.

**Сохранить и ограничить:** Оплаченная partial work сохраняется в accounting. Reuse не является новым независимым наблюдением; исторический результат остаётся читаемым.

Полный исходный packet: [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/FUN-01.md](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/FUN-01.md). Actual owner read ranges: [coverage](coverage.json), [извлечённые диапазоны](owners_FUN-01.txt).

### FUN-02 · LANE-02 · retain

**Техника и root cause:** Изоляция маленьких config mappings без deepcopy services, реальные reduced/full executions и различение interval origin — разумное решение. Empty, partial и настоящий zero сохраняют разные значения; ratio устойчив к крайним масштабам.

**Полезная способность/free-grow:** Более дешёвая оценка полезна, но reduced не автоматически эквивалентна full quality. Method-issued interval и heuristic proxy должны иметь разные semantic labels.

**Достоверность проверки:** Проверить native reduced/full work counters, caller config mutation, zero denominator/observed zero, max/subnormal ratio0.5 и настоящую method CI. Success-shaped stub не доказывает уменьшение работы.

**Стоимость и библиотека:** Existing math.frexp/ldexp достаточно для нужного ratio. Новая bootstrap library не требуется без inference contract. Cost должен иметь фактический источник, не фиксированный USD label.

**Сохранить и ограничить:** Нельзя выдавать сгенерированный interval за empirical uncertainty без sampling assumptions. Ownership config не требует копировать datasets.

Полный исходный packet: [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/FUN-02.md](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/FUN-02.md). Actual owner read ranges: [coverage](coverage.json), [извлечённые диапазоны](owners_FUN-02.txt).

### FUN-03 · LANE-02 · targeted revision

**Техника и root cause:** Same-basis method source→current knowledge и appointed permit→protected writer архитектурно верны. Но calibration metric definitions/populations и explicit-zero carrier selection пропущены (PS-F01/07). Нужен единый versioned contract и согласованная migration.

**Полезная способность/free-grow:** Exploration остаётся полезной при insufficient calibration. Разрешённый normal route действительно даёт один effect; unknown/revoked permit — ни одного. Statistical PASS не authority, а permission не evidence качества.

**Достоверность проверки:** Сохранить first assessment, contested/late history и normal/revoke race. Добавить четыре confusion cells, selective-label controls, observed0 отдельно от qualified n=5 и zero с отличающимся fallback. Одних ranks x=1..5 недостаточно.

**Стоимость и библиотека:** Existing tracker и SciPy подходят при заявленных assumptions. Audit stage-B work входит в общий budget. Новый truth registry/issuer и произвольный минимум samples не нужны.

**Сохранить и ограничить:** FOR может быть намеренной operational metric: сначала DEC purpose, затем definition/threshold. Historical semantics, wrappers, burn-in, report и drift мигрируют вместе; negative values разрешаются только существующим concrete profile.

Связанные выводы: PS-F01, PS-F07.

Полный исходный packet: [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/FUN-03.md](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/FUN-03.md). Actual owner read ranges: [coverage](coverage.json), [извлечённые диапазоны](owners_FUN-03.txt).

### TRN-01 · LANE-02 · retain with separate bounded redesign decision

**Техника и root cause:** Восстановление timestamp/strict boolean, отдельные diagnostic/admitted quotas и actual source bridge корректны. Неиспользуемый benchmark converter не нужно активировать ради coverage; raw objective/split/profile нельзя фабриковать.

**Полезная способность/free-grow:** Совместимая численная история reusable; несовместимая идея полезна через новую target evaluation. Более широкий measured-observation reuse PS-F02 — отдельный профиль, не отмена текущего fitted-native guard.

**Достоверность проверки:** Actual register→CAS→fresh bridge, время2001, false против string false, MIN/MAX round-robin, valid row после invalid и изменения target units/tenant/split. Hint не переносит старый score: новая evaluation имеет новый source ref.

**Стоимость и библиотека:** Bounded refill сохраняет обе quotas; diagnostic cache не training corpus. Непригодные строки видимы с причиной, но не считаются numeric observations.

**Сохранить и ограничить:** Сохранить diversity; не отбирать только лучшие строки. Совпавший fingerprint не позволяет обойти source admission.

Связанные выводы: PS-F02.

Полный исходный packet: [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/TRN-01.md](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/TRN-01.md). Actual owner read ranges: [coverage](coverage.json), [извлечённые диапазоны](owners_TRN-01.txt).

### TRN-02 · LANE-02 · retain

**Техника и root cause:** Bounded compatible ANN refill, exact-selected-ref cache custody и atomic native generation образуют разумную систему. Candidate generation строится до publish; external native graph loading по умолчанию закрыт.

**Полезная способность/free-grow:** Полезный hit должен происходить из actual portable source artifact. Третий compatible record за двумя incompatible находится при достаточном scan budget; это не обещание exhaustive ANN recall.

**Достоверность проверки:** Настоящий HNSW add частично изменяет native state перед injected failure; rollback/poison проверяются после этого. Fresh portable process и actual target consumer обязательны. Old/new/old selected refs и current access checks не заменяются cache hit.

**Стоимость и библиотека:** 32MiB означает retained payload, не RSS. Snapshot-per-add measurement уже есть в baseline; batch optimization только условное продолжение PS-L07. HNSW0.8 sdist/Python3.14 native availability не квалифицирована.

**Сохранить и ограничить:** Обычный query не rebuild. Reserved metadata/cycles guards и default graph trust не ослабляются. Exact history ref читается напрямую, не новым ANN lookup.

Полный исходный packet: [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/TRN-02.md](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/TRN-02.md). Actual owner read ranges: [coverage](coverage.json), [извлечённые диапазоны](owners_TRN-02.txt).

### TRN-03 · LANE-02 · retain

**Техника и root cause:** Aware-UTC boundary, одинаковый effective grade в query/report и evidence age вместо access age — точный repair. Naive time нельзя угадывать как UTC; отсутствующее historical time остаётся unknown.

**Полезная способность/free-grow:** Lesson переносится по context/tenant/source filters и не омолаживается чтением. Evidence clock меняет настоящее новое assessment, не cache hit.

**Достоверность проверки:** Fresh restart с контролируемым clock на границе TTL; старое event time при новом access time; query/report equality; повторное чтение без reassessment. Now-on-restore мутант должен провалить fixture2001.

**Стоимость и библиотека:** Существующих time/filter/lesson owners достаточно. TTL — versioned heuristic, не ML probability; filter до materialization экономит IO и сохраняет admission boundaries.

**Сохранить и ограничить:** Grade/age не является калиброванной вероятностью истины. Историю не удалять автоматически; incompatible idea может пройти разрешённую target reevaluation.

Полный исходный packet: [e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/TRN-03.md](../baseline/PolicyOS_E02_Executor_Specifications/02_Пакеты/TRN-03.md). Actual owner read ranges: [coverage](coverage.json), [извлечённые диапазоны](owners_TRN-03.txt).

## 3. End-to-end способность lane: не membership, а реальные границы

### LANE-01 — BOUNDARY-QUALIFIED DESIGN; targeted SIM-03 witness revision; no executed capability PASS

**Заявление:** Обычный запрос создаёт полезный условный результат на реальном model-bound пути, сохраняет его и продолжает исследование при новом совместимом основании; новое подходящее resource не требует case-specific кода.

**Фактическая цепочка:** HTTP/job ingress → actual compiler/DesignProblem + data requirements → candidate/method selection → selected grounded model/WMR + admitted source → N5 native simulation/comparator → persisted request/input/result refs → fresh conditional N8/public consumer; re-entry читает это основание, повторяет current gates и либо reuse numerical result, либо исполняет изменённый model/source.

**Сильные стороны существующей приёмки:**

- Полные packet solutions не ограничиваются запретами: есть actual supported alternate engine, singleton, source acquisition, exact conditional joint model, positive issuer/readiness и retained useful partial result.

- I01-A/B/C разнесены по capability, concrete bindings точнее membership. Existing served test наблюдает actual compiler/N5 delegate, не готовый числовой result.

- SIM-03 integer equation и OPT-style независимый arithmetic подход дают настоящие expected values; CYC-03 A→B→B→B→C отличает экономию от stale context.

**Оставшиеся qualification gaps:**

- Existing served candidate-only fixture с N8/N9 traps не доказывает полный ordinary request→saved conditional N8. Нужен отдельный допустимый consumer route, не снятие traps/authority ради green.

- SIM-03 deterministic evidence-fixed fixture не квалифицирует native seed-sensitive stochastic pairing (PS-F04).

- Один synthetic model не доказывает generality даже при полной lineage. Второй случай должен иметь materially different contract content и frozen no-case-code boundary; X03/X04 уже требуют transfer, это надо исполнить, не объявить новым missing REQ.

- Readiness LANE12/appointed issuer и real source admission — внешние prerequisites; если owner unavailable, зависимая capability BLOCKED, но unrelated conditional computation остаётся полезной.

**Улучшенный bounded end-to-end план:**

#### L1-0 — predeclare profile/holdout

До запуска сохранить build/lock/backend/dtype, model expressions, units/time/outcomes, source schema, expected formulas, allowed doubles и resource budget. Отдельный reviewer фиксирует второй совместимый model/source profile после freeze общего кода. Изменение fixtures/config/resources разрешено; case-ID branch запрещён. Любая необходимая общая semantics implementation раскрывается и перезапускает freeze.

**Независимый oracle / различимость:** Список разрешённых generic extension surfaces; diff/caller census; input hashes и независимые algebraic formulas. Не просто count changed files.

#### L1-1 — positive ordinary request and fresh consumer

Через actual served ingress без заранее вложенного prepared leaf context пройти compile→ground→method→native N5. Persist actual source/model/comparator/request/result. Новый процесс и current selected ref выводят conditional value/units/horizon/limitations. На supported alternate profile первый method несовместим, второй действительно исполняется.

**Независимый oracle / различимость:** Малый independent expression/data-law oracle, exact source refs, actual call count и fresh-read value. Always-refuse/constant fixture output/input-ref-only mutant обязан провалиться. Claims ограничены conditional model.

#### L1-2 — acquisition and re-entry

Исходное A имеет declared unresolved requirement; source rows B проходят настоящий admission и строят новый WMR. Выполнить A→B→B→B→C: одинаковое B reuse physical result, C меняет substantive row/model/time basis. На одном B отдельно поменять current access/budget/epoch gate. Multirow aggregation explicit; stale concurrent acquisition completion history-only.

**Независимый oracle / различимость:** Независимо пересчитать B/C из source rows; producer-work counters различают1 computation и повторный replay. Current gate control меняет только зависимую eligibility, не historical bytes. Один hash/receipt без re-evaluated consumer не PASS.

#### L1-3 — numerical/local adversarial controls

Провести required-input absence, canonical path aliases, temporal mismatch, finite overflow, duplicate SMM moment before dictionary, paired interruption and missing sample, authored joint vs alternatives. Сохранить fixed-evidence integer comparator; добавить PS-F04 actual varying noise trace и seed/pair permutation mutants.

**Независимый oracle / различимость:** Независимая формула и per-role outcomes, planned/completed denominators. No success-shaped numerical stub. Positive-SE interaction остаётся unsupported до отдельного inference profile.

#### L1-4 — useful next step, readiness and stop

Late candidate-local failure выбирает следующий grounded viable candidate в том же remaining budget; global cap не обходит. Actual loaded build evidence проходит appointed existing confidence_ledger issuer/verifier. Budget stop сохраняет partial frontier и concrete next action; revoke/stale readiness ограничивает dependent transition.

**Независимый oracle / различимость:** Measured operations/spend, all child statuses, useful retained result; normal readiness positive и stale/unappointed negative в одной supported fixture. Technical readiness не institutional enactment.

#### L1-5 — materially different held-out compatible case

Поменять минимум semantic problem content: variable/outcome mapping, time profile и source values/measurement law в пределах уже supported semantics; например второй actual model с heterogeneous intervention effect и другой required source layout, а не тот же коэффициент под UUID. Пройти тот же ordinary ingress→persist→fresh consumer без product edit после reveal.

**Независимый oracle / различимость:** Заранее заданный независимый expected result и omission/unknown behavior; стоимость first/second case, ручная подготовка, changed resources/code раскрыты. Это evidence bounded transfer envelope, не утверждение «любой домен решён».

**Ресурсы:** Использовать существующие packet request/sample/child/byte limits; tiny deterministic fixture bounds выводятся из declared model/replicate count, не выдуманного SLO. Считать отдельно acquisition rows/bytes, physical native calls, cache hits и current gate reads, rebuild/IO и elapsed/peak memory если заявляется. Один shared heavy run не несколько независимых подтверждений. Не добавлять обязательный live provider.

**Что PASS не доказывает:** Synthetic pipeline PASS не empirical calibration, causal identification в реальном мире, universal NLP coverage, оптимальность всех политик, N9 permission или уже назначенный issuer. Новые общие semantics могут требовать кода; запрет только fixture/case-specific подгонки.

**Ownership:** REQ01 requirement meaning; CYC03 numerical basis/current gates; ACQ01 source bridge; SIM01 method eligibility, SIM02 typed path/cause/time, SIM03 numerical contrast; CYC05 authored relationships/readiness, SEL01 rank; LANE06 persistence и LANE12 build evidence owners не дублируются.

### LANE-02 — USEFUL COMPOSABLE DESIGN; revise FUN-03 and OPT-02; stronger measurement reuse is separate opt-in capability

**Заявление:** Поиск исполняет допустимые различные actions, сохраняет partial work и воспроизводимый state, использует совместимое source evidence, расходует реальный budget и делает только разрешённый promotion; смена совместимой задачи/ресурса не case-specific workflow.

**Фактическая цепочка:** SearchService/lifecycle ask→pending → typed proposal/codec → actual SearchLoopRunner MethodJob/selected metric source → tell preparation/current commit → persisted history + RNG/Sobol/GP snapshot → fresh target source verifier/corpus → GP/Pareto/champion; funnel uses actual current evidence and independent protected writer; transfer discovers candidate source via ANN but exact ref/source custody decides reuse.

**Сильные стороны существующей приёмки:**

- Native GP witness действительно сравнивает learned posterior mean/covariance/UCB с независимым NumPy Cholesky и содержит destructive load/transform mutations; это стоит сохранить, не переписать.

- TRN02 native mutation failure test вызывает original add перед exception, проверяя rollback реально изменённого индекса. Portable source→fresh runtime handoff и refusal untrusted graph разумно разделены.

- Delivered specs хорошо отделяют sentinel от training, actual attempt work от iterations/warm rows, current gates от immutable numerical reuse, comparison champion от institutional permit.

**Оставшиеся qualification gaps:**

- FUN03 observed rate threshold без definition/cohort/power не квалифицирует population-level calibration; неправильные labels FOR/FDR/precision и zero fallback могут менять routing/report (PS-F01/07).

- OPT02 binary batch не различает proposal budget exhaustion и finite-domain exhaustion и не закрывает completed-scope duplicate guard (PS-F03).

- Current source profile deliberately требует fitted native GP. Это честный узкий scope, но не strategy-neutral reuse уже оплаченных actual measurements (PS-F02 separate DEC, не local repair blocker).

- Один posterior test не доказывает search benefit, как один retrieval hit не доказывает recall. Native libraries optional; skips по отсутствию backend не green.

**Улучшенный bounded end-to-end план:**

#### L2-0 — fixture and budget declaration

Выбрать supported locked P-SEARCH: explicit search_bo/search_mo и отдельно vector-search, actual OS/arch/Python3.14; tiny CPU native workloads, один heavy slot. Объявить source objective/unit/direction/split/data/tenant, measurement law, allowed replicates, random state, total/evaluator/sentinel/audit limits. Predeclare independent finite-domain objective oracle и holdout profile.

**Независимый oracle / различимость:** Build/lock/input binding; нет объявления «all extras» вместо доказанного backend. Numeric tolerances вывoдятся из specific algorithm/dtype; отсутствующий stack→точный NOT_RUN/BLOCKED.

#### L2-1 — actual search and lifecycle

Actual service/codec/runner заказывает реальные tiny MethodJobs в конечном mixed typed space. Пройти обычный candidate, sentinel, valid tell, competing duplicate tells, delayed previous-run tell, cancel/error после оплаченной evaluation; persist partial state и fresh resume. Не подменять evaluator источником готовых receipts.

**Независимый oracle / различимость:** Independent finite action enumeration/measurement function, counts attempts/evaluations/observations/replicas/sentinels и spent work. Correct exactly-once commit; useful partial result survives; malformed invalid typed result не successful0.

#### L2-2 — state/numerical consumers

Whole vs split save/load сравнить next RNG/Sobol proposal; malformed snapshot against live model leaves unchanged state. Fit/condition actual GP on admitted rows and compare NumPy posterior; Pareto computes exact known grid membership; actual champion compare/write under multiprocess barrier and fresh pointer reader.

**Независимый oracle / различимость:** Не один cross-call same-library equality: independent coordinate/score table, Cholesky math and weak-all/strict-one dominance. Mutation removed model_state/transform restore, changed source split/unit, old normalized vector, double publish должны различаться.

#### L2-3 — honest exhaustion and cost

Tiny fully enumerated space действительно исчерпать; отдельно99/100seen с controlled20 duplicate proposals и non-exhaustive mixed space. Расходовать общий work budget включая sentinel/audit, но не warm history как новую evaluation. Не переплачивать за exact duplicate без explicit replica.

**Независимый oracle / различимость:** finite_domain_exhausted только при census; bounded failure→proposal_search_budget_exhausted. Search regret/quality сравнивается с exact finite oracle только в declared finite fixture, не гарантия global optimum любого continuous BO.

#### L2-4 — funnel calibration and authority

Full vs bound staged attempts используют одинаковые immutable sources, но текущие gates перечитываются. Reduced/full actual work, zero/empty/partial/interval origin. Выбрать FUN03 operational FOR или FNR, source labels/cohorts и bounded audit design; persist tracker→fresh report. Отдельно appointed permit→actual protected writer normal/revoke-before-commit/idempotent retry.

**Независимый oracle / различимость:** Independent confusion matrix/rank and zero-carrier oracle, observed value отдельно от qualified claim; exact source counts/cost. Permission positive даёт1 effect, revoke0; statistical PASS не grants permit и permit не manufactures calibration.

#### L2-5 — transfer and fresh target

Actual source history→portable rows artifact→fresh HNSW generation→bounded discovery с несовместимыми near hits→exact selected ref→current custody/source verifier→target. Source time не now-on-load. Compatible fitted profile и incompatible candidate-only reevaluation оба полезны. PS-F02 measured profile только если отдельно выбран/квалифицирован.

**Независимый oracle / различимость:** Target corpus exact source identities/units/split/direction, no duplicate origin; independent actual replica отдельно. Changed tenant/data/closed split исключаются до numerical reuse; candidate hint получает новое measured target ref. Native partial mutation/rollback и cache old/new selectedref controls.

#### L2-6 — transfer holdout and benefit qualification

Freeze механизм и budget, затем раскрыть второй compatible objective/parameter layout/resource profile с иными optimum/constraints и source history. Без case-ID code пройти тот же loop. Для benefit сравнить warm/cold at equal real evaluator+fit budgets на заранее выбранном наборе seeds/profiles; tuning objective не совпадает со скрытым evaluation criterion.

**Независимый oracle / различимость:** Ремонт accepts correctness независимо от stochastic better score. Benefit report содержит все runs, uncertainty и actual costs, не один удачный seed; размеры/мощность определяются задачей, не arbitrary SLA. Не объявлять universal superiority BO/transfer.

**Ресурсы:** Total work учитывает failed/partial evaluations, audit rejected stage-B labels, sentinels, GP fits/conditioning, HNSW snapshots/rebuild и portable reads; proposed iterations не proxy расходов. Source evaluation reuse не бесплатный GP fit. Existing max counts и byte caps сохраняются; peak native RSS измеряется отдельно. Local concurrency barriers без sleep timing guesses.

**Что PASS не доказывает:** Нельзя вывести из fake receipt или native posterior correctness: empirical truth objective, calibrated missed-positive bound, open-domain optimality, ANN exhaustive recall, distributed durability или authority. Population-level calibration требует отдельного sampling design. Empty/unsupported route не закрывает positive capability.

**Ownership:** SRV01 atomic tell, CTL01 lifecycle failure, SRV03 actual runner/resume, CTL03 budgets/sentinel; CTL02 RNG/base restore and OPT03 GP state sequential owner; OPT02 params/replicas, OPT01 coordinate schema; FUN01 attempts, FUN02 reduced/full, FUN03 metrics+promotion adapter; TRN02 discovery/custody, TRN01 source admission, TRN03 evidence age.

## 4. Библиотеки и технологии: решения, а не список модных названий

Actual baseline: Python `>=3.14,<3.15`; NumPy2.3.5, SciPy1.16.3, JAX/jaxlib0.8.2, Torch2.10.0, GPyTorch1.15.1, BoTorch0.16.1, linear-operator0.6, pymoo0.6.1.6, Pydantic2.12.5, pytest9.0.2, Hypothesis6.151.2, hnswlib0.8.0 optional. Node22/pnpm10.33.2/frontend dependencies не требуют изменения для reviewed mechanisms. `research`/`all` не автоматически включают `search_bo`/`search_mo`; P-SEARCH должен назвать необходимые extras. HNSW lock имеет sdist, не доказанный cp314 wheel; native build/run NOT_RUN.

### PS-L01 — GP posterior и continuation

**Решение:** RETAIN existing GP stack; отдельно измерения/модель по PS-F02

**Сейчас:** Existing BayesianOptimizer + BoTorch0.16.1/GPyTorch1.15.1/Torch2.10.0, NumPy2.3.5 oracle

**Сравнены:** Собственный GP solver; Full refit каждого шага; Existing condition_on_observations с periodic declared refit.

**Почему:** Нынешний реальный witness проверяет learned RBF/ConstantMean, transforms, latent posterior и UCB независимо через NumPy Cholesky. Это существенно сильнее сравнения двух calls одного backend. Сохранять state_dict/transform replay и atomic staged restore; fit fingerprint не приравнивать measurement validity.

**Стоимость:** Exact GP dense factorization обычно O(n^3) time/O(n^2) memory; cap512 — уже declared ограничение, не научная достаточность. Conditioning снижает некоторые повторные затраты, не означает бесплатное обучение hyperparameters. Считать fit/condition отдельно.

**Совместимость:** search_bo/search_mo optional; research/all не включают их автоматически. Torch native cp314 wheels в lock для отдельных OS/arch; actual install/runtime не проверен. GPU не обязателен tiny CPU witness.

**Квалификация:** Сохранить actual 8→9→12 и removal mutations; posterior tolerance profile explicit. Свежий процесс, не только новый объект; exception fallback bounded и source truthful.

**Первичные источники (проверены 2026-11-01):** [SingleTaskGP(train_X, train_Y, train_Yvar), condition_on_observations, MixedSingleTaskGP](https://botorch.readthedocs.io/en/v0.16.1/models.html).

### PS-L02 — Acquisition numerics и шумовая модель

**Решение:** TARGETED EXPERIMENT: предложить versioned LogEI/qLogEI profile; не молчаливую замену и не обещание universal speedup

**Сейчас:** bayesian.py1014 qExpectedImprovement,1548 ExpectedImprovement; existing dependency уже содержит log variants

**Сравнены:** Retain EI для backward replay; LogEI/qLogEI из pinned BoTorch; qLogNEI только для обоснованного noisy objective profile.

**Почему:** Документация pinned release рекомендует log formulations из-за numerical behavior. Текущий defaultEI может давать плоские/underflow acquisition gradients на некоторых landscapes; это риск, не измеренный здесь production failure. qNEI имеет другой baseline-noise смысл, поэтому его нельзя выбирать только как «более новый».

**Стоимость:** Одинаковые evaluation/optimizer restarts/raw-sample budgets сравнить на заранее заданном tiny suite, включая finite mixed domain и small-variance tail. log acquisition value не сопоставим со старым EI value; rank/metadata version обязателен.

**Совместимость:** Новых dependencies не требуется; imports через existing _deps optional owner. Старые serialized acquisition identifiers replay по старому profile, не переинтерпретировать.

**Квалификация:** Independent analytical tail/rank cases; actual proposal validity и duplicate controls; held-out objective families без tuning after reveal; finite outputs/gradients и spend, не одно better-best score. Noise variance source должен быть измеренный/declared, не fabricated.

**Первичные источники (проверены 2026-11-01):** [ExpectedImprovement/qExpectedImprovement рекомендуют Log-варианты](https://botorch.readthedocs.io/en/v0.16.1/acquisition.html); [Ament et al., Unexpected Improvements to Expected Improvement for Bayesian Optimization](https://arxiv.org/abs/2310.20708).

### PS-L03 — Finite/mixed search и duplicate avoidance

**Решение:** RETAIN SearchSpace; use pinned optimize_acqf_discrete only within bounded finite profile

**Сейчас:** SearchSpace normalization/denormalization owner + existing random/Sobol/BoTorch

**Сравнены:** Bounded random resampling; Small exact enumeration + existing discrete acquisition; Mixed optimization for typed categories/integers.

**Почему:** Domain identity остаётся приложением: solver X_pending/unique не знают model basis, alias semantics и independent replicas. Tiny enumeration даёт genuine exhaustion; large continuous enumeration невозможно. MixedSingleTaskGP может быть полезен при доказанной categorical geometry, но необязателен для duplicate repair.

**Стоимость:** O(cardinality) feasible choices допустим только до заранее заданного resource cap; X_avoid materialization bounded. После20 unsuccessful draws сообщать search-budget limit, не математическую пустоту.

**Совместимость:** Pinned BoTorch0.16.1 supports unique/X_avoid; random/Sobol path остаётся полезным без backend. Ни one-hot aliases, ни relaxed rounded proposal не являются final execution coordinate.

**Квалификация:** PS-F03 exact/near-exhaustion matrices, all branches and completed/pending history; explicit replica basis. Изменить размер finite domain без case-ID code.

**Первичные источники (проверены 2026-11-01):** [optimize_acqf_discrete: choices, unique, X_avoid](https://botorch.readthedocs.io/en/v0.16.1/optim.html); [SingleTaskGP(train_X, train_Y, train_Yvar), condition_on_observations, MixedSingleTaskGP](https://botorch.readthedocs.io/en/v0.16.1/models.html).

### PS-L04 — Sobol continuation без квадратичного prefix replay

**Решение:** RETAIN SciPy; incremental owner/cursor и bounded restore

**Сейчас:** SciPy1.16.3 qmc.Sobol through existing SearchSpace

**Сравнены:** Заново вычислять prefix до cursor каждый suggest; Сохранять versioned seed/cursor и fast_forward/rebuild once; Собственный QMC generator.

**Почему:** Выбранное исправление CTL-02 правильно: не менять deterministic sequence при восстановлении и не повторять весь prefix на каждом шаге. SciPy покрывает direction numbers/scrambling; свой generator не оправдан. random_base2 полезен только для совместимого batch profile.

**Стоимость:** Repeated prefix1+…+N даёт quadratic generated points; incremental generation linear в количестве новых точек, restore cost отдельно. Cursor и work bounds валидировать до allocation.

**Совместимость:** SciPy1.16 minor уже содержит rng migration; не смешивать seed/rng profiles в старом snapshot. Arbitrary n, skip/thinning не имеют того же balance guarantee, что power-of-two construction.

**Квалификация:** Exact next-point whole/split/fresh-reader equality и malformed state no-mutation; не проверять «QMC quality» лишь по конечным0..1 bounds.

**Первичные источники (проверены 2026-11-01):** [random_base2, random, fast_forward, предупреждение о balance при произвольном n/skip/thinning](https://docs.scipy.org/doc/scipy-1.16.0/reference/generated/scipy.stats.qmc.Sobol.html).

### PS-L05 — Калибровочная статистика: определения прежде библиотеки

**Решение:** REVISE metric/sampling contract; existing SciPy binomtest/proportion_ci only for suitable declared design

**Сейчас:** CorrelationTracker + существующий Spearman average ties, SciPy1.16.3 already locked

**Сравнены:** Сохранить owner Spearman с independent oracle; Использовать scipy.stats для проверяемой interval/rank calculation; Добавить sklearn только ради confusion ratios.

**Почему:** Основные ошибки PS-F01/07 — selection и denominator semantics, а не отсутствие библиотеки. Для четырёх confusion counts stdlib проще. SciPy exact interval полезен при валидном Bernoulli sampling; сам API не доказывает representative corpus. sklearn можно использовать как secondary oracle в optional profile, не увеличивать core dependency ради деления.

**Стоимость:** Window processing O(n), bounded corpus. Audit label cost обычно важнее CPU статистики; уже существующий burn-in включить в total stage-B budget. Power выводится из tolerance/risk/design, не magic minimum5.

**Совместимость:** SciPy1.16.3 соответствует1.16 docs; sklearn1.8 optional, current docs нужны только для определения recall. No network/live traffic required for software fixture.

**Квалификация:** Zero/constant/ties, all confusion cells, mixed cohorts, snapshot migration и both score carriers. Population guarantee только при объявленных assumptions; writer permission отдельно.

**Первичные источники (проверены 2026-11-01):** [binomtest: число успехов k в n Bernoulli trials](https://docs.scipy.org/doc/scipy-1.16.0/reference/generated/scipy.stats.binomtest.html); [exact / wilson / wilsoncc interval methods](https://docs.scipy.org/doc/scipy-1.16.1/reference/generated/scipy.stats._result_classes.BinomTestResult.proportion_ci.html); [Recall = TP/(TP+FN)](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.recall_score.html).

### PS-L06 — Pareto и hypervolume

**Решение:** RETAIN delivered OPT-01 design; exact>2D only if consumer needs it

**Сейчас:** Existing fast skyline/2D union + locked pymoo0.6.1.6; BoTorch multiobjective owner already exists

**Сравнены:** Labelled bounding-box upper-bound diagnostic; pymoo.indicators.hv.HV/moocore for bounded dimensions; Existing BoTorch partitioner; Собственный general exact algorithm.

**Почему:** Исходное ТЗ уже даёт proxy≠exact counterexample и actual ranking consumer: это не новая находка. Для нового exact3D capability библиотека уже есть. Не менять работающий skyline или2D ради унификации; independent slow oracle остаётся правильным test tool.

**Стоимость:** Dominance/skyline и HV — разные задачи. HV complexity быстро растёт с dimension/frontsize; bound input envelope. Fixed reference часть objective schema; dynamic reference не даёт comparable progress.

**Совместимость:** pymoo0.6.1.6 base locked, cp314 wheel entries присутствуют. Pinned HV source delegates moocore; actual installed native compatibility не исполнена. Explicit max/min sign mapping.

**Квалификация:** Сохранить delivered3D1000≠28, добавить A/B rank reversal28<64 при желании; duplicates/dominated points/ref changes/unit scale; actual registry consumer, не только helper.

**Первичные источники (проверены 2026-11-01):** [Hypervolume delegates to moocore](https://raw.githubusercontent.com/anyoptimization/pymoo/0.6.1.6/pymoo/indicators/hv/__init__.py).

### PS-L07 — HNSW concurrency, portable source и native rebuild

**Решение:** RETAIN; не заменять сервисом и не снимать locks ради latency

**Сейчас:** hnswlib0.8.0 + vector_memory RLock/_Generation, portable JSON+NPZ

**Сравнены:** Existing native HNSW bounded profile; Exact vector scan как tiny independent test oracle; Remote vector DB или другой native ANN backend без workload evidence.

**Почему:** Pinned README согласуется с single mutation/publication owner: add/query нельзя считать одновременно safe. Approximate retrieval не admission: совместимость, tenant и exact selected ref проверяет текущий owner. Default отказ external native graph остаётся правильным; переносимые rows позволяют rebuild.

**Стоимость:** Filter refill bounded, не exhaustive recall. Python callbacks/GIL могут менять throughput; tiny test не stress. Cache32MiB — payload retention, не общий RSS. Snapshot-per-add уже измеряется по ТЗ; batch generation только после доказанной потребности (рассмотренный PS-F06).

**Совместимость:** Lock имеет hnswlib0.8 только sdist: не заявлять Python3.14 wheel или runtime qualification. save/load ef требуется profile restore; cosine get_items normalized, не байт-в-байт исходные vectors.

**Квалификация:** Actual native partial mutation then fail + rollback/poison, fresh portable process, top2 incompatible/third compatible within sufficient scan budget; record native build/runtime. Нет installs в этом review.

**Первичные источники (проверены 2026-11-01):** [Python API thread safety, save/load ef, filter GIL, cosine get_items normalization](https://github.com/nmslib/hnswlib/blob/v0.8.0/README.md).

### PS-L08 — Малые owned snapshots и atomic restore

**Решение:** RETAIN staged validation and one commit; validate after parsing raw subject

**Сейчас:** Dataclass/Pydantic2.12.5, stdlib copies/locks; existing owner transactions

**Сравнены:** Selective deep copy immutable contract leaves; Whole-service deepcopy; Frozen DTO/model_copy как единственная защита; Новый generic transaction framework.

**Почему:** Pydantic model_copy(update=...) не проверяет update; frozen не делает вложенный mutable dict immutable. Поэтому snapshot config/schema мал, отделён от live services и валидируется owner. Полный deepcopy datasets/services дорогостоящ и семантически неверен. Existing prepared delta лучше нового framework.

**Стоимость:** Копировать bounded config/DTO, не datasets; staging nativeGP/index memory учитывать отдельно. Callbacks/preparation outside lock, final current-state commit under one serialization predicate.

**Совместимость:** Точно pinned Pydantic2.12.5 source; Python3.14 semantics. Snapshot compatibility и unknown fields отдельно: permissive parse не означает признанный current schema.

**Квалификация:** Caller alias mutation, failed validation/backend restore, retained old snapshot; одновременно model/RNG/counters не меняются при failure. Fresh reader required, not only frozen marker.

**Первичные источники (проверены 2026-11-01):** [model_copy update не валидируется, deep=False по умолчанию](https://raw.githubusercontent.com/pydantic/pydantic/v2.12.5/pydantic/main.py).

### PS-L09 — Local champion publication и locking

**Решение:** RETAIN local POSIX profile; no distributed coordinator for this patch

**Сейчас:** Existing POSIX flock stable lockfile + atomic pointer replacement

**Сравнены:** Stable lock + same-filesystem replace; Versioned CAS DB compare-and-swap для будущего distributed scope; Thread-only lock или replace без read-modify-write serialization.

**Почему:** Один lock вокруг basis/check/compare/publish устраняет lost update в local multiprocess profile; thread lock недостаточен. os.replace даёт atomic visibility, но не весь transaction/durability. Новый distributed lock нужен только при реальном multi-host writer scope.

**Стоимость:** Малый pointer/write critical section, expensive evaluation outside lock. Утилита filelock transitive не автоматически даёт нужный fence/durability contract. Stable lock inode, не заменяемый pointer inode.

**Совместимость:** Python3.14 fcntl Unix-only; локальный FS в заявленном profile. Windows/NFS/SMB не обещать; если crash durability заявлена, fsync file+directory и crash fixture отдельно.

**Квалификация:** Two-process barriers, stale basis, revoke/permit не смешивать с champion policy act, fresh pointer reader, finite objective/source bound.

**Первичные источники (проверены 2026-11-01):** [os.replace atomic successful rename on POSIX](https://docs.python.org/3.14/library/os.html#os.replace); [flock LOCK_EX / LOCK_UN, Unix availability](https://docs.python.org/3.14/library/fcntl.html).

### PS-L10 — Непрерывная численная семантика и dtype

**Решение:** RETAIN existing kernels with finite-aware boundaries; no generic arbitrary precision engine

**Сейчас:** NumPy/SciPy/JAX existing numerical owners, Python math

**Сравнены:** math.frexp/ldexp/fsum and scale-safe reductions; Naive float sum/products; Decimal/Fraction только small independent oracle; Поменять весь simulator на новый backend.

**Почему:** Typed metric endpoint/units/horizon checks важнее blanket numerical library swap. Integer NCM oracle хорош и exact в float64; scale cases нуждаются в derived numerical tolerance, не удобном epsilon. frexp ratio может избегать intermediate overflow, но настоящий unrepresentable result остаётся unavailable.

**Стоимость:** Не копировать целые runtime trees; owned path/token update лучше deepcopy wholemodel. NaN/Inf checks O(n) неизбежны на admitted arrays. Small independent Fraction/Decimal oracle не production engine.

**Совместимость:** Python3.14 math; NumPy2.3.5; JAX0.8.2 defaultdtype нельзя принимать за64. x64 profile задавать до native computation, фактический dtype assert. Torch double profile отдельно.

**Квалификация:** Finite endpoints/diffs/mean/SE, n1/constant/overflow, negative list indices vs dictionary keys, temporal aggregation contract. PS-F04 actual noise variation; numerical precision не causal evidence.

**Первичные источники (проверены 2026-11-01):** [fsum, frexp/ldexp, isfinite](https://docs.python.org/3.14/library/math.html#math.fsum); [JAX default 32-bit](https://docs.jax.dev/en/latest/101/arrays.html).

### PS-L11 — State-machine/property tests как дополнение actual lane witness

**Решение:** USE existing Hypothesis for short model-based sequences; retain native integration tests

**Сейчас:** pytest9.0.2 + hypothesis6.151.2 already locked

**Сравнены:** Handwritten scenario only; RuleBasedStateMachine against simple independent reference; Mock all producers and assert DTO shape.

**Почему:** lifecycle/attempt/pending/restore/expiry имеют комбинаторные interleavings. State machine полезна для последовательностей ask→tell→cancel→snapshot→restore; oracle должен быть простой отдельной моделью, не вызывать проверяемый owner для expected result. Она не заменяет native numerical/source/authority bridge.

**Стоимость:** Bound examples/steps fixture-work budget; seeds/repro artifacts сохранять. Concurrency race требует deterministic barriers, не flaky sleep. Shrinking помогает диагностике, но покрытие не универсальная гарантия.

**Совместимость:** Current primary docs newer than lock, используется longstanding API, no upgrade required. NativeGP/HNSW jobs координируются по одному heavy slot.

**Квалификация:** Mutants always-refuse, stale acceptance, double tell, callbacks under lock, history edits, restored clock rejuvenation должны различаться. Не всё превращать в giant e2e; shared test covers only explicit claims.

**Первичные источники (проверены 2026-11-01):** [RuleBasedStateMachine generated sequences](https://hypothesis.readthedocs.io/en/latest/stateful.html).

### PS-L12 — Generic policy contracts вместо нового orchestration/NLP engine

**Решение:** RETAIN composable existing owners; do not add framework for this repair

**Сейчас:** Existing compiler→requirements→planner→model producer→N5/CAS→consumer owners

**Сравнены:** Targeted normalizer/resolver/census and source bridge; Case-ID branches for accepted fixtures; One universal workflow/model engine.

**Почему:** Прочитанный код и пакетные solutions правильно локализуют alias normalization, context wiring, missing required vector, budget fallback и reusable basis. Здесь библиотека не решает measurement semantics или authority. Growth означает новый совместимый ресурс через contract, не запрет любого нового semantics code.

**Стоимость:** One shared mechanism per concern снижает duplicated validation и stale projections; caches numerical immutable, gates current. Cost counts actual acquisition/evaluator/native work, не synthetic dollar values.

**Совместимость:** Repo Python3.14/Node22/pnpm10.33.2 baseline не требует frontend или orchestration migration. Dependency upgrade без observed issue не предлагается.

**Квалификация:** Materially different frozen holdout resource; no case-ID branching; raw construct ambiguity addressed DEC; actual positive producer/readback and fresh gates. Architecture source and exact code ranges in coverage; external library source не нужен для вывода retain-domain-API.

### PS-L13 — Детерминированный normal quantile вместо вспомогательного Monte Carlo

**Решение:** REPLACE narrow quantile implementation with qualified stdlib NormalDist.inv_cdf or existing SciPy norm.isf

**Сейчас:** NCMEngineMethod.pure_step1099–1118; NumPy global100000 draws на каждый вызов

**Альтернативы:** Current random percentile approximation; stdlib inverse normal lower tail; existing SciPy inverse survival function

Стандартный normal quantile не требует Monte Carlo. Seeded model draws и summary quantile — разные задачи; supporting quantile не должен мутировать ambient RNG или добавлять100000 draws. Интервал при этом не становится автоматически статистически квалифицированным.

**Стоимость:** Вместо O(100000) auxiliary sample allocation/generation/percentile на каждый call — scalar deterministic quantile. Source-level saved work доказуем, latency/memory benefit измеряется отдельно. При N5 n_samples1 overhead особенно бессмыслен.

**Совместимость:** Python3.14 stdlib доступен; SciPy1.16.3 уже locked. Stable lower-tail -inv_cdf((1-c)/2) либо isf((1-c)/2); finite0<c<1 до model execution. Не применять новое backend/runtime installation.

**Квалификация:** PS-F08 actual native method, ambient RNG unchanged, same-seed numerical CI replay, no extra quantile draws и near1 boundary. Singleton/ddof0 contract отдельно ограничить DEC-SIM-03-02, paired endpoint сохранить. Проверить несколько confidence levels против constant1.96, near1/tiny boundaries и сохранение mean/trajectory/n при interval-unavailable.

**Primary sources:** [NormalDist.inv_cdf: deterministic inverse normal CDF](https://docs.python.org/3.14/library/statistics.html#statistics.NormalDist.inv_cdf); [norm.ppf/isf deterministic inverse CDF/survival function](https://docs.scipy.org/doc/scipy-1.16.0/reference/generated/scipy.stats.norm.html).

## 5. Совместная реализация и последовательность приёмки

1. Сначала минимальные семантические поправки FUN-03/OPT-02 и дополнительный SIM-03 witness; source/domain guards, budgets и authority boundaries не ослаблять.

2. Зафиксировать FUN-03 DEC operational metric/sampling/tolerance/migration; не молча заменить FOR на FNR. Положительный writer route квалифицировать отдельно от statistical criterion. SIM-03 interval compatibility по DEC-SIM-03-02 не подменяет paired endpoint и не превращается в новый inference framework.

3. Согласовать один writer для shared `bayesian.py`, funnel и transfer code; CTL-02 base restore + OPT-03 GP restore — одна staged transaction, не параллельные frameworks. SRV-01 atomic tell и CTL-01 failure finalization имеют разные обязанности.

4. Исполнить локальные discriminating matrices и затем применимые I01/I02 variants. Shared run переиспользуется по precise claim/input/backend binding, а не считается несколькими независимыми опытами. Native GP/HNSW jobs — по одному согласованному heavy slot; здесь они не запускались.

5. F02 measured-observation reuse — только отдельный bounded capability DEC/profile после сохранения текущего fitted-native path. Optional LogEI, exact>2D HV и bulk HNSW — по workload/consumer evidence, не обязательные dependencies для исправления.

6. Freeze code и показать materially different compatible holdout через ресурсы/contracts; раскрыть ручную подготовку, добавленный общий код и фактическую стоимость. Новый semantics code допустим, case-ID branches и oracle leakage — нет.

## 6. Артефакты и честный статус

- [findings.json](findings.json): шесть основных выводов и два рассмотренных, но не признанных новыми defects кандидата.

- [library_decisions.json](library_decisions.json): 13 сравнений с applicability, cost, pinned/current distinction и primary URLs.

- [coverage.json](coverage.json): все27 packet verdicts, hashes, exact selected ranges и ограничения.

- [lane_reviews.json](lane_reviews.json), [packet_reviews.json](packet_reviews.json): структурированные подробности.

- **Product tests: NOT_RUN. Native library/profile qualification: NOT_RUN.** Ни текущий source review, ни proposed-v2 спецификация не являются выполненным ремонтом.

- Нет unresolved permission blockers. Несуществовавшие guessed file paths исправлены чтением реального checkout; недоступный Pydantic docs URL заменён exact pinned maintainer source. Никаких запрещённых reads/эскалаций/установок не выполнялось.

## 7. Подготовленные предложения review-v2

В предлагаемой редакции подготовлены пять изменённых пакетных MD/JSON пар и обзоры LANE-01/02: [manifest с old/new hashes](proposed_changes.json), [proposed_v2](../../README.md). Новых REQ/TEST нет; новые DEC-FUN-03-03, optional DEC-OPT-03-02 и DEC-SIM-03-02. Существующие IDs, preservation/residual bindings и NOT_RUN статусы сохранены. Общие03/aggregate04 остаются координатору; baseline и продукт не изменялись. Проверка согласованности документов — не продуктовая приёмка.

Независимый peer readback proposed-v2: **ACCEPT спецификации, открытых находок нет**;12 staging files/22 REQ/22 TEST, исправление native seed schedule и PS-F08 подтверждены. [Peer report](../fabric_acquisition/review_policy_v2.md). Это проверка документов/source grounding, все product TEST по-прежнему NOT_RUN.
