# BKT-02 — Устойчивый численный диапазон без потери полноты, nominal/type и micro/macro

**Исполнительская спецификация; финальная QA комплекта ещё ожидается.**
**LANE-03 · CP3 · B167, B168, B171.** Основание `20d9009be21097bfbdc38a546a15cc60213b8ace`. Реализация документом не выполнена; все будущие проверки **NOT_RUN**. Именных исполнителя/reviewer назначает проект.

## 1. Практическая цель и область

Сохранить уже работающие completeness/coverage/micro контракты и устранить исключение от конечных extreme inputs. Пригодные измеренные строки должны доходить до свежего reader даже когда отдельная ячейка или достаточная статистика непредставима. Не смягчать trust ради нового PASS.

**Тип работы:** Один bounded numerical-range repair; maintenance устаревших fixtures; native producer→reader qualification; явная comparability policy для aggregate.

[Аудит](../05_Основания/Аудит/02_Пакеты/BKT-02.md) · [остатки](../05_Основания/Аудит/01_Реестры/C33_остатки.json) · [исходная карточка](../05_Основания/Аудит/05_Источники/BKT-02_исходные_строки.txt) · [источники](../05_Основания/Аудит/05_Источники/C33_источники.json) · [трассировка](../04_Трассировка/BKT-02.json). Полные диагностические scripts/logs остаются в отдельно доставленном ZIP фазы 1. Действуют [общие правила](../00_Общее/Правила_исполнения_и_приёмки.md).

## 2. Исходные обязанности и сохранение

B167 уже сохраняет requested/compared/missing/invalid и не допускает empty trust; B168 уже разделяет unknown CI, availability и conditional hit с nominal/type; B171 уже считает micro из pooled statistics и отдельно equal-scenario macro. Эти repairs не заказываются заново. C33-R01 касается overflow и сохранения partial work. LK01/LK29/LK30 не разрешают смешивать predictive coverage, causal/parameter calibration и production admission.

- `preserve:0416`: Requested/missing/invalid cells → REQ-BKT-02-01, REQ-BKT-02-03; TEST-BKT-02-01, TEST-BKT-02-03.
- `preserve:0417`: Partial useful rows → REQ-BKT-02-01, REQ-BKT-02-02, REQ-BKT-02-03; TEST-BKT-02-01, TEST-BKT-02-02, TEST-BKT-02-03, TEST-BKT-02-07.
- `preserve:0418`: No empty trust → REQ-BKT-02-03, REQ-BKT-02-08; TEST-BKT-02-03, TEST-BKT-02-08.
- `preserve:0419`: Exact-fit positive control → REQ-BKT-02-03; TEST-BKT-02-03, TEST-BKT-02-07.
- `preserve:0420`: Unknown CI → REQ-BKT-02-04; TEST-BKT-02-04.
- `preserve:0421`: Availability versus hit → REQ-BKT-02-04; TEST-BKT-02-04.
- `preserve:0422`: Nominal normalization → REQ-BKT-02-04; TEST-BKT-02-04.
- `preserve:0423`: Typed readback → REQ-BKT-02-04, REQ-BKT-02-08; TEST-BKT-02-04, TEST-BKT-02-07, TEST-BKT-02-08.
- `preserve:0430`: SSE/n → REQ-BKT-02-02, REQ-BKT-02-05; TEST-BKT-02-02, TEST-BKT-02-05.
- `preserve:0431`: Absolute/percentage denominators → REQ-BKT-02-02, REQ-BKT-02-05; TEST-BKT-02-02, TEST-BKT-02-05.
- `preserve:0432`: Explicit macro → REQ-BKT-02-05, REQ-BKT-02-06; TEST-BKT-02-05, TEST-BKT-02-06.
- `preserve:0433`: Report reconciliation → REQ-BKT-02-02, REQ-BKT-02-08; TEST-BKT-02-02, TEST-BKT-02-07, TEST-BKT-02-08.

## 3. Disposition полного остатка

| ID | Действие / причина | REQ / общий владелец |
|---|---|---|
| `C33-R01` | fix: Stable arithmetic либо explicit range limitation с сохранением useful rows; согласовать writer/reader. | REQ-BKT-02-01, REQ-BKT-02-02 |
| `C33-G01` | qualify: Native ownership chain и fixture maintenance без raw-envelope bypass. | REQ-BKT-02-03, REQ-BKT-02-04, REQ-BKT-02-07, REQ-BKT-02-08 |
| `C33-G02` | capability: Comparable strata/weights и точный смысл interval; scientific authority отдельно. | REQ-BKT-02-04, REQ-BKT-02-05, REQ-BKT-02-06, REQ-BKT-02-08 |

Все source-registry remaining также связаны: `remaining:0285`, `remaining:0286`, `remaining:0287`. Подробная причина и REQ для каждой строки — в companion JSON; повторная запись не считается новым независимым дефектом.

## 4. Нормативный контракт

### REQ-BKT-02-01
Finite extreme input не прерывает весь scenario до численной проверки. Непредставимый residual/square получает адресную numerical-range limitation/invalid-cell по объявленной политике; ранее пригодные rows сохраняются. Никакие NaN/inf/overflow не заменяются0 и не допускаются в finite DTO. Requested denominator не уменьшается из-за диапазона.
Источник: B167, B171; C33-R01. Проверки: TEST-BKT-02-01, TEST-BKT-02-02.

### REQ-BKT-02-02
RMSE/MAE и достаточные statistics вычисляются устойчиво там, где результат представим; aggregate и fresh IR reconciliation используют одинаково объявленный numerical-range контракт, но независимо пересчитывают его из rows. Непредставимая сумма обозначается недоступной с точной причиной, не silently clamped и не подставлена0. Полезные rows и finite metrics остаются доступны; неподдержанный range не получает trust.
Источник: B171; C33-R01. Проверки: TEST-BKT-02-02, TEST-BKT-02-05, TEST-BKT-02-07.

### REQ-BKT-02-03
Requested set метрика×координата сохраняется: wrong-key/zero comparisons не дают gradeA/eligible; partial rows полезны с missing/invalid addresses и completeness. Полный точный point forecast сохраняет supported positive result; общий WeightedScorer не переписывается из-за local backtest policy.
Источник: B167; C33-G01. Проверки: TEST-BKT-02-03, TEST-BKT-02-07.

### REQ-BKT-02-04
Отсутствующий/непригодный CI остаётся within_ci=None и не считается miss. Availability=valid intervals/requested interval cells, conditional hit=hits/evaluated intervals; nominal confidence и interval type сохраняются producer→scenario→aggregate→JSON/CAS→reader. Nominal не заменяет observed hit. Уровень/объект интервала подтверждает actual producer, не label в dict.
Источник: B168; C33-G01, C33-G02. Проверки: TEST-BKT-02-04, TEST-BKT-02-07.

### REQ-BKT-02-05
Техническое sharding тех же сравнимых rows не меняет micro RMSE/MAE/MAPE/coverage и denominator; equal-scenario macro остаётся отдельной явно названной мерой со стабильной смысловой идентичностью сценариев. Нельзя усреднять per-scenario RMSE и называть это micro либо запрещать обоснованную macro weighting.
Источник: B171; C33-G02. Проверки: TEST-BKT-02-05, TEST-BKT-02-06.

### REQ-BKT-02-06
До pooling разных metrics/jurisdictions фиксируются comparable quantity/units и weighting policy. Несовместимые величины остаются отдельными strata/summary с причиной; допустимое приведение единиц выполняется declared преобразованием до statistics и сохраняется в provenance. Нельзя подбирать стандартизацию/веса после просмотра результата.
Источник: B168, B171; C33-G02. Проверки: TEST-BKT-02-06.

### REQ-BKT-02-07
Existing stale persisted-envelope fixtures заменяются current workflow/physical-request/selected SimulationResult/PropagationReport основанием. Один native shared путь подтверждает interval producer→evaluator→report→fresh trust verifier→decision packet. Никакой raw envelope bypass или прежний lambda _state ради старого expected score не возвращается.
Источник: B167, B168, B171; C33-G01. Проверки: TEST-BKT-02-07, TEST-BKT-02-08.

### REQ-BKT-02-08
Source rows, sufficient statistics, overall metrics, counts, hits и diagnostic/profile bindings повторно сверяются при загрузке. Forged summary/trust marker, candidate diagnostic и неверный compute hash не создают trust. Legacy useful rows остаются читаемыми без несвязанной positive qualification; exact point fit не объявляется empirical calibration или population transport.
Источник: B167, B168, B171; C33-G01, C33-G02. Проверки: TEST-BKT-02-07, TEST-BKT-02-08.

## 5. Конкретное техническое решение

**Не лечить только строку `abs_err**2`.** Сначала проверить finite residual/absolute error, вычислять square безопасно и обрабатывать overflow до append. Нынешний DTO хранит float SSE: для individual unrepresentable square допустим адресный range-invalid cell с сохранением других rows. Для finite individual squares, переполняющих sum, использовать scaled sum-of-squares: scale=max|residual|, ssq=sum((residual/scale)^2), RMSE=scale*sqrt(ssq/n); MAE вычислять через scaled/compensated sum с делением до опасного умножения. Не cast через float больших целых ради суммы. Percentage denominator остаётся только у вычислимых relative errors.

**Сумма может не помещаться, когда среднее помещается.** SSE2e308 невозможно честно записать finite float, хотя RMSE1e154 представим. Предпочтительный минимальный контракт: сохранить comparisons и finite metrics, выставить явную numerical-range limitation для недоступной sufficient statistic, не выдавать trust; extended scaled statistics вводить только если действительно нужны incremental aggregation. В этом случае versioned `(scale, scaled_sum, n)` must reconcile from rows и объединяться rescaling, не просто храниться как доверенная metadata. DEC-RANGE выбирает один вариант, обязательно закрывая TEST02; нельзя исправить evaluator и оставить IR validator повторно overflow. Writer/aggregate/IR reader/governance должны одинаково различать unavailable-range и tampering, но reader независимо вычисляет oracle.

**Существующий ремонт сохранить:** цикл ожидаемых cells, None для unknownCI, counts availability/hits, explicit nominal/type и micro/macro уже правильны. Не менять общий WeightedScorer; local completeness prerequisite важнее cosmetic grade. Затронутый BacktestReport уже перепроверяет rows и diagnostics — расширять его range contract адресно, не отключать `_assert_metric_diagnostics_match_scenarios`.

**Смысл pooling:** у existing plan/aggregation owner закрепить quantity/unit/transform/weight policy до запуска. Совместимые unit conversions применяются к input coordinates и записываются; incompatible quantity группируются отдельно. Если нынешний публичный report не выражает strata, минимальное typed grouping расширение лучше, чем автоматическая стандартизация по увиденному результату. Equal-scenario macro остаётся полезной при стабильных scenario identities.

**Fixtures:** old `lambda _state` с artifacts_index больше не является текущим execution контрактом. Переиспользовать current BKT-01 native fixture с actual workflow report, physical request, selected simulation и propagation; это maintenance, не требование вернуть старый обход.

### Текущие owners и источники

- [policy-engine/src/polisyos/scientist/methods/backtesting/evaluator.py:72–205](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/evaluator.py#L72-L205)
- [policy-engine/src/polisyos/scientist/methods/backtesting/trust_scorer.py:43–106](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/trust_scorer.py#L43-L106)
- [policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py:1378–1474](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py#L1378-L1474)
- [policy-engine/src/polisyos/ir/analytics/backtest.py:368–578](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/backtest.py#L368-L578)
- [policy-engine/src/polisyos/scientist/governance/backtest_matrix.py:172–363](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/governance/backtest_matrix.py#L172-L363)
- [policy-engine/tests/unit/remediation/test_bkt_02.py:331–495](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_bkt_02.py#L331-L495)
- [policy-engine/src/polisyos/scientist/nodes/builtins/decide/decision_packet/outcome_sections.py:255–349](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/decide/decision_packet/outcome_sections.py#L255-L349)

## 6. Проверки: setup → действие → oracle

TEST-ID обозначает требуемую проверку, не существующий одноимённый pytest test. Расширять указанные действительные места, не дублировать suites.

### TEST-BKT-02-01 · native overflow-before-guard regression
**NOT_RUN. REQ:** REQ-BKT-02-01.
**Setup:** y_true=[1,1e308], y_pred=[1,0]; отдельно finite values с subtraction overflow и normal1e150 residual.
**Действие:** Actual PredictionEvaluator.evaluate→scenario serialization→fresh load.
**Oracle:** Нет uncaught OverflowError. Первая exact row сохранена; requested2 и адрес второй range-limited/invalid согласованы, report не full eligible. Normal1e150 путь даёт finite RMSE1e150. NaN/inf input по-прежнему invalid, не0.
**Место:** `tests/unit/remediation/test_bkt_02.py; scientist/methods/backtesting/evaluator.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-BKT-02-02 · native accumulated-range regression
**NOT_RUN. REQ:** REQ-BKT-02-01, REQ-BKT-02-02.
**Setup:** Два residual1e154, каждый square1e308; extreme abs/percentage sums; варианты permutation/sharding. Высокоточная Decimal oracle только в тесте.
**Действие:** Evaluate→aggregate→persist→fresh reconciliation; проверить chosen finite/range outcome.
**Oracle:** RMSE representable1e154 не превращается в inf/exception. Непредставимый SSE2e308 явно unavailable/range-limited; rows не теряются и не помечаются fabricated zero. Если контракт выбирает ограничение вместо extended statistics, точная причина воспроизводится reader и trust unavailable; finite supported subset имеет правильные counts.
**Место:** `tests/unit/remediation/test_bkt_02.py; tests/unit/ir/analytics/test_backtest.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-BKT-02-03 · native completeness positive/negative
**NOT_RUN. REQ:** REQ-BKT-02-03.
**Setup:** Expected y=[1,100]; wrong key, empty, prediction[1], full[1,90], full exact; mixed nonnumeric/NaN/inf с одной valid row.
**Действие:** Evaluator/scorer→aggregate→DTO roundtrip.
**Oracle:** Wrong key requested2/compared0/missing2, no A/eligible. Partial сохраняет first row и completeness не улучшается из-за удаления трудной точки; report ineligible. Full exact retains positive score1/A по текущему допустимому point-fit profile, не empirical coverage. Invalid addresses/counts точны.
**Место:** `tests/unit/remediation/test_bkt_02.py; trust_scorer.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-BKT-02-04 · native interval semantics matrix
**NOT_RUN. REQ:** REQ-BKT-02-04.
**Setup:** Два точных point forecasts: noCI, один valid hit, один real miss, invalid bounds; identical observed hit.8 при nominal.8 и.95.
**Действие:** Actual evaluator→aggregate→canonical serialization/readback с admitted producer interval contract из BKT-01.
**Oracle:** NoCI coverageNone/within_ciNone; one of2 gives availability.5, conditional hit1; invalid interval не miss. Observed.8 unchanged при nominal revision, score сравнивается со своим nominal; nominal/type/counts сохраняются. Mean-effect CI не становится predictive interval от label.
**Место:** `tests/unit/remediation/test_bkt_02.py; BKT-01 TEST06`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-BKT-02-05 · native partition invariant numerical test
**NOT_RUN. REQ:** REQ-BKT-02-02, REQ-BKT-02-05.
**Setup:** Residuals[0,10,10] как один scenario и [0]+[10,10]; второй corpus6rows, четыре partitions; negative forged overall value.
**Действие:** Aggregate и fresh IR validator; independent Decimal/hand oracle.
**Oracle:** Micro sqrt(200/3)=8.16496580927726, MAE20/3 неизменны; macro одного8.1649 vs двух5 явно отличается policy. Pooled hits1/4 не macro.5. Counts и percentage denominator сохраняются; forged overall rejected. Extreme variants из TEST02 не обходят declared range policy.
**Место:** `tests/unit/remediation/test_bkt_02.py; ir/analytics/backtest.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-BKT-02-06 · native comparability and weighting contract
**NOT_RUN. REQ:** REQ-BKT-02-05, REQ-BKT-02-06.
**Setup:** Два одного quantity сценария в метрах/сантиметрах с declared conversion; затем несопоставимые деньги/температура; fixed meaningful scenario weights.
**Действие:** Existing plan/report aggregation owner validates policy до численного pooling; persist/readback.
**Oracle:** Метр/см после declared conversion дают один правильный micro с сохранённым conversion provenance; несовместимые quantity не дают бессмысленный общий RMSE, но per-stratum результаты доступны. Technical shard сохраняет micro; intentional macro reweighting отражается в policy. Неизвестная comparability — explicit limitation, не автоматическая posthoc standardization.
**Место:** `backtesting/plan.py; orchestrator.py::_aggregate; BacktestReport metadata/typed contract owner`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-BKT-02-07 · native E02-I03-C positive chain
**NOT_RUN. REQ:** REQ-BKT-02-02, REQ-BKT-02-03, REQ-BKT-02-04, REQ-BKT-02-07, REQ-BKT-02-08.
**Setup:** Existing tiny Scientist/Foundry calculation с actual selected SimulationResult и admitted propagation; native CAS. Full exact point case и genuine supported predictive interval case, отдельно range-limited partial.
**Действие:** Evaluator→aggregate/pre-persist guard→CAS→fresh matrix/calibration/decision packet consumer.
**Oracle:** Positive numeric result и поддержанная role доходят с exact refs/profile; noCI не выдаёт measured coverage. Partial/range-limited сохраняет rows/reasons без trust. Packet публикует recomputed score либо explicit unavailable, не raw stored trust_score.
**Место:** `tests/unit/scientist/methods/backtesting/test_backtesting.py; scientist/governance/backtest_matrix.py; decide/decision_packet/outcome_sections.py`.
**Doubles:** Controlled model/data допустимы; evaluator/serializer/CAS/uncertainty admission/fresh verifier не заменяются. Один shared run покрывает variants, не три независимых empirical studies.

### TEST-BKT-02-08 · native test-maintenance and tamper controls
**NOT_RUN. REQ:** REQ-BKT-02-07, REQ-BKT-02-08.
**Setup:** Stale test_bkt_02 persisted-envelope fixtures331–495; genuine report and retained legacy report; altered counts/SSE/hits/no bounds/diagnostic hash/scorer profile/positive marker.
**Действие:** Сначала actual supported test collection/run, сохранить исходный failure если есть; обновить fixture на current owner contract и прогнать positive/tamper/legacy controls.
**Oracle:** Fixture использует store/foundry и required physical execution provenance; не снимаются guards ради старых expectations. Tampered reports refused/unavailable; legacy rows readable but unbound trust снят. Native observed result не подменяется прежним source-only prediction о failing tests.
**Место:** `tests/unit/remediation/test_bkt_02.py; tests/unit/ir/analytics/test_backtest.py; backtest_matrix.py::verified_report_trust_projection`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### Запуск: адаптируемый шаблон, не выполненная команда

Из `policy-engine/` в поддержанной Python3.14 среде с закреплёнными зависимостями. Этот документ не разрешает автоматические installs; отсутствующая dependency означает BLOCKED конкретной проверки.

```bash
python -V
python -m pytest -q tests/unit/remediation/test_bkt_02.py tests/unit/ir/analytics/test_backtest.py
python -m pytest -q tests/unit/scientist/methods/backtesting/test_backtesting.py
# Native shared consumer variant/selector уточнить по actual patch; старый source-only fixture diagnosis не считать выполненным test failure.
```

Фиксировать профиль/backend, inputs/seed/hash, deciding output и exit. Ruff и затронутые architecture/import checks выбирать по фактическому patch; native slot согласовать, полный suite на каждый пакет не копировать.

## 7. Общая интеграция и ownership

Переиспользовать **E02-I03-C**: [канонический контракт LANE-03](../03_Интеграция/LANE-03.md). Одно свидетельство связывается с конкретными вариантами и REQ; не считается многими независимыми подтверждениями.

BKT-02 владеет evaluator sufficient statistics, aggregate micro/interval counts и IR row reconciliation; BKT-03 использует согласованный numeric contract для bias mean/diagnostics. Один writer orchestrator/backtest.py. Native scenario общий с BKT-01, внешние packet readers квалифицируются вариантами, не отдельной инфраструктурой.

- **BKT-01:** Actual trajectory/uncertainty semantics и native source path; не принимать произвольный envelope.
- **BKT-03:** Общий stable arithmetic/reconciliation writer: mean cancellation и numerical-range policy согласованы, не два расходящихся helper.
- **FRC-02:** Predictive experiment/coverage scientific scope, не general authority от point score.

## 8. Совместимость, миграция и возврат

Обычные finite-range отчёты/значения сохраняются. Новый range limitation — deliberate graceful degradation вместо исключения; сохранённые старые trust markers не переаттестовывать. Если schema расширяется scaled statistics/strata, явная version/read compatibility и exact source row recomputation обязательны. Rollback сохраняет raw comparisons/reasons и отключает только неподдержанный aggregate claim; не заменяет metrics0/inf и не отключает finite validators.

## 9. Free-grow и обоснованные границы

- [universal-policy-design-target-architecture-and-gap.md — D0 и typed result/constraint contracts](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md): Общий quantity/unit/aggregation contract позволяет новый совместимый metric без case-specific формул. Частичная полезная работа имеет адресные ограничения.
- [wave5-evidence-substitution-ratification.md — K01 и K07–K08](../05_Основания/Архитектура/wave5-evidence-substitution-ratification.md): Arithmetic consistency/point-fit grade не заменяет independent predictive calibration, population transport или institutional decision authority.

## 10. Конечные решения и сдача

### DEC-BKT-02-RANGE
**Вопрос:** Достаточно ли explicit unavailable sufficient statistic или нужен scaled-statistics schema?
**Кто решает:** Evaluator/IR report owners и numerical reviewer.
**Конечное действие/выход:** Сравнить actual aggregate consumers и existing schema. Выбрать minimal limitation+retained rows как default; если нужен incremental extreme-range micro, добавить versioned scaled statistics и независимую reconciliation. Оба варианта обязаны пройти TEST01–02 без data loss/false trust.
**До решения:** Не обещать полный numeric support там, где float summary непредставима; useful rows и finite metrics сохраняются.

### DEC-BKT-02-POOL
**Вопрос:** Какая existing metadata/typed contract задаёт сравнимые quantities и веса?
**Кто решает:** Backtest plan/domain owner.
**Конечное действие/выход:** Проследить target definitions/units из BKT-01 до report, выбрать grouping/conversion policy; сдать один same-quantity converted positive и incompatible negative. Не требовать универсальной онтологии всех измерений.
**До решения:** Необоснованное cross-quantity pooling ограничено, per-scenario/per-quantity numerical results доступны.

Сдать base/head и patch, exact REQ→TEST→shared variant, исходные входы и их идентичности, actual команды/exit/log, независимые численные/семантические oracles, positive/negative/removal controls, сохранённые инварианты и открытые решения. Source-only, fixture, native и scientific qualification отражать отдельно. Не повышать partial/NOT_RUN до PASS; квалифицированный локальный механизм не является автоматической готовностью всей политики.
