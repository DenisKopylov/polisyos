# BKT-01 — Допустимый historical view, точный forecast profile и сохранённый replica cohort

**Исполнительская спецификация; финальная QA комплекта ещё ожидается.**
**LANE-03 · CP3 · B166, B169, B170.** Основание `20d9009be21097bfbdc38a546a15cc60213b8ace`. Реализация документом не выполнена; все будущие проверки **NOT_RUN**. Именных исполнителя/reviewer назначает проект.

## 1. Практическая цель и область

Закрыть три реальные потери на существующем backtesting пути, сохранить уже исправленную привязку prefix→Foundry request и довести смысл trajectory/replicas до полезного consumer. Не считать правильное число элементов или уникальные seeds доказательством прогноза либо независимого Monte Carlo.

**Тип работы:** Три локальных ремонта; capability для semantic trajectory и multi-run projection; native/cost qualification существующих owners.

[Аудит](../05_Основания/Аудит/02_Пакеты/BKT-01.md) · [остатки](../05_Основания/Аудит/01_Реестры/C32_остатки.json) · [исходная карточка](../05_Основания/Аудит/05_Источники/BKT-01_исходные_строки.txt) · [источники](../05_Основания/Аудит/05_Источники/C32_источники.json) · [трассировка](../04_Трассировка/BKT-01.json). Полные диагностические scripts/logs остаются в отдельно доставленном ZIP фазы 1. Действуют [общие правила](../00_Общее/Правила_исполнения_и_приёмки.md).

## 2. Исходные обязанности и сохранение

B166: immutable prefix и exact snapshot request binding уже реализованы, но весь доступный feature view должен быть допустимым as-of. B169: raw scalar ATE и неверная длина уже отвергаются, typed constant profile сохранён; исправить selected metrics profile и связать предмет/координаты. B170: физические replica requests/seeds/cohort уже есть; не запускать их заново при semantic fallback, сохранить denominator и сделать один честный поддержанный multi-run summary. PROVIDED — отдельный контракт без повторной симуляции.

- `preserve:0413`: Immutable mask → REQ-BKT-01-01, REQ-BKT-01-02; TEST-BKT-01-01, TEST-BKT-01-02.
- `preserve:0414`: Date/preperiod resolution → REQ-BKT-01-02; TEST-BKT-01-02.
- `preserve:0415`: Snapshot identity guard → REQ-BKT-01-01, REQ-BKT-01-02, REQ-BKT-01-04; TEST-BKT-01-02, TEST-BKT-01-04.
- `preserve:0424`: Typed constant profile → REQ-BKT-01-04, REQ-BKT-01-05; TEST-BKT-01-04, TEST-BKT-01-05.
- `preserve:0425`: Exact list length → REQ-BKT-01-05; TEST-BKT-01-05.
- `preserve:0426`: Canonical uncertainty admission → REQ-BKT-01-04, REQ-BKT-01-06; TEST-BKT-01-06.
- `preserve:0427`: Per-replica seeds/requests → REQ-BKT-01-07; TEST-BKT-01-07.
- `preserve:0428`: Requested/failed denominator → REQ-BKT-01-07, REQ-BKT-01-08; TEST-BKT-01-07, TEST-BKT-01-08.
- `preserve:0429`: PROVIDED no rerun → REQ-BKT-01-07; TEST-BKT-01-07.

## 3. Disposition полного остатка

| ID | Действие / причина | REQ / общий владелец |
|---|---|---|
| `C32-R01` | fix: Проверить весь admitted feature view и recompute derived features из допустимых inputs. | REQ-BKT-01-01, REQ-BKT-01-02 |
| `C32-R02` | fix: Существующий _naive_with_cohort сохраняет выполненную работу во всех fallbacks. | REQ-BKT-01-03 |
| `C32-R03` | fix: Не терять selected MetricsRef/profile на повторном чтении. | REQ-BKT-01-04 |
| `C32-G01` | capability: Trajectory semantics и coordinates требуют полноценного producer contract, не только native запуска. | REQ-BKT-01-05, REQ-BKT-01-06 |
| `C32-G02` | capability: Native chain/cost квалификация и один полезный existing-owner ensemble projection. | REQ-BKT-01-07, REQ-BKT-01-08, REQ-BKT-01-09 |

Все source-registry remaining также связаны: `remaining:0283`, `remaining:0284`, `remaining:0288`, `remaining:0289`, `remaining:0290`. Подробная причина и REQ для каждой строки — в companion JSON; повторная запись не считается новым независимым дефектом.

## 4. Нормативный контракт

### REQ-BKT-01-01
Исторический Scientist replay получает проверенный as-of view всех доступных полей, а не только усечённый target. Outcome-derived features строятся из допустимого prefix; неизвестные post-cutoff поля не включаются молча. Заранее известные exogenous поля допускаются по объявленному temporal/availability контракту, не слепой обрезкой всех списков. Source payload неизменён, actual input_bindings ссылается на exact persisted snapshot этого view.
Источник: B166; C32-R01, C32-G02. Проверки: TEST-BKT-01-01, TEST-BKT-01-02.

### REQ-BKT-01-02
Cutoff date/step/pre-periods разрешаются по единой оси с адресным отказом неоднозначности/противоречия; отсутствие cutoff не означает автоматически нулевое обучение либо разрешение полного future view. Для already-truncated режима требуется проверяемое происхождение/temporal boundary. Исходный state/request не мутируется.
Источник: B166; C32-G02. Проверки: TEST-BKT-01-01, TEST-BKT-01-02.

### REQ-BKT-01-03
Любая ветка semantic prediction fallback после созданного cohort сохраняет replica_cohort_ref в scenario metadata и final report manifest input edge. Невалидный scalar/trajectory не принимается ради lineage; уже выполненные replicas не запускаются повторно и persisted artifacts не удаляются.
Источник: B169, B170; C32-R02. Проверки: TEST-BKT-01-03.

### REQ-BKT-01-04
Selected MetricsRef, включая manifest_profile_sha256, проходит без потери через payload load и producer check constant forecast. Ни valid selected/foreign default, ни foreign selected/valid default не меняют решение в пользу default. То же правило применить к затронутому selected uncertainty consumer, сохранив canonical admission.
Источник: B169; C32-R03. Проверки: TEST-BKT-01-04, TEST-BKT-01-06.

### REQ-BKT-01-05
Каждая Scientist trajectory и разрешённая constant projection связываются с quantity/estimand, units, baseline, origin/cutoff, exact requested coordinates и replica identity. Shape-only список с mean_ate либо чужими dates не становится outcome trajectory. Constant модель разрешена при корректном producer-bound контракте и совпадающих координатах; срез большего horizon допустим только по явным matching coordinates с provenance, не тихим truncation.
Источник: B169; C32-G01. Проверки: TEST-BKT-01-05.

### REQ-BKT-01-06
Prediction interval принимается только через existing canonical SimulationResult/PropagationReport/uncertainty admission с правильными interval semantics, confidence level и координатами. CI среднего эффекта не копируется во все будущие наблюдения. Годный point forecast сохраняется с limitation при отсутствующем interval; reuse уже полученных draws/summary предпочтителен повторному запуску.
Источник: B169; C32-G01, C32-G02. Проверки: TEST-BKT-01-05, TEST-BKT-01-06.

### REQ-BKT-01-07
n_simulation_runs считает явно заявленные физические stochastic replicas; n1/n7 создают соответствующий допустимый план с отдельными requests, run IDs, seeds и requested/started/completed/failed. Failed replica остаётся в denominator; exact cache-hit одного execution не считается новым независимым draw. Budget admission действует до дорогого dispatch через existing runtime owner, actual known costs/unknown statuses сохраняются. PROVIDED не вызывает Scientist ради общего поля n.
Источник: B170; C32-G02. Проверки: TEST-BKT-01-07, TEST-BKT-01-08.

### REQ-BKT-01-08
Для одного поддержанного multi-run trajectory контракта existing numerical owner строит полезную coordinate-wise summary либо сохраняемый ensemble, привязанный ко всем exact replica refs; failed/несовместимые replicas отражены отдельно, не подставлены нулями. Scalar averaging с последующим размножением запрещено. Без совместимой projection сохраняется честный unsupported/degraded result и полный cohort.
Источник: B170; C32-G02. Проверки: TEST-BKT-01-08, TEST-BKT-01-09.

### REQ-BKT-01-09
Native Scientist workflow→Foundry→CAS→backtest report→fresh reader квалифицируется на малом реальном вычислительном пути, включая положительный uncertainty case. Различие seeds/requests не объявляется statistical independence без отдельного RNG/модельного основания. Содержательный conditional result доступен даже при неполной uncertainty/scientific qualification.
Источник: B166, B169, B170; C32-G02. Проверки: TEST-BKT-01-02, TEST-BKT-01-06, TEST-BKT-01-07, TEST-BKT-01-08, TEST-BKT-01-09.

## 5. Конкретное техническое решение

**View:** нынешний masker deep-copies весь dict и меняет только targets/time_index. До `_persist_masked_view` существующий data/feature owner должен построить разрешённую projection: target/observed features только as-of, derived вычисляются после selection допустимых parents, known-ahead exogenous сохраняются по declared availability. Не выводить роль из Python list shape или имени future. Если текущий source profile не несёт availability/dependencies, минимально расширить его typed contract после DEC-VIEW; missing classification ограничивает только такой replay input. Нужен тот же persisted snapshot в actual input bindings; готовый independently prepared state допускается после identity/provenance проверки. Не копировать всю базу по каждому сценарию.

**Два маленьких ремонта:** ветку `set(predictions)!=set(target_metrics)` вернуть через уже существующий `_naive_with_cohort(reason)`, сохранив warnings/interval limitations. Для metrics сохранить `MetricsRef.model_validate` вместо `ArtifactID`, передать полный ref в `load_core_json_artifact` и canonical selected-profile resolver producer manifest. Использовать уже проверенный ref из SimulationResult; не угадывать profile по default. Аналогично selected uncertainty reference не должен теряться на константной projection.

**Trajectory:** нынешний ForecastProfileContract проверяет только constant/outcome_trajectory/horizon/unique labels. Связать существующий producer output contract с target quantity/units/baseline/origin/coordinates и typed plan. List и scalar имеют один смысловой admission; list shape не обход. Constant7 разрешён для declared stationary forecast с exact target coordinates; mean_ate7 остаётся эффектом, не forecast. Если selected producer уже имеет usable draws, делать явную coordinate projection и сохранять source refs, не rerun. Интервалы проходят existing canonical uncertainty_source_projection, без второй локальной интерпретации envelope.

**Replicas:** уже реализованные physical requests и cohort сохраняются. Для ограниченного нового multi-run case выбрать existing numerical aggregation owner, передать aligned trajectories/draws и exact refs; summary должен быть coordinate-wise со своим estimand и requested/completed denominator. Это не request-count bug заново. Бюджет и стоимость проверяются на actual existing runtime gate; не изобретать в backtester ещё одну ledger. Совместимость RNG/потоков квалифицируется отдельно, unique seed сам по себе не сертификат независимости.

### Текущие owners и источники

- [policy-engine/src/polisyos/scientist/methods/backtesting/masking.py:24–158](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/masking.py#L24-L158)
- [policy-engine/src/polisyos/scientist/methods/backtesting/plan.py:26–124](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/plan.py#L26-L124)
- [policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py:205–241](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py#L205-L241)
- [policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py:703–880](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py#L703-L880)
- [policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py:933–1024](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py#L933-L1024)
- [policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py:1215–1235](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py#L1215-L1235)
- [policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py:1261–1310](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py#L1261-L1310)
- [policy-engine/src/polisyos/scientist/nodes/builtins/simulate/uncertainty_source_projection.py:377–473](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/simulate/uncertainty_source_projection.py#L377-L473)

## 6. Проверки: setup → действие → oracle

TEST-ID обозначает требуемую проверку, не существующий одноимённый pytest test. Расширять указанные действительные места, не дублировать suites.

### TEST-BKT-01-01 · native masker/feature lineage regression
**NOT_RUN. REQ:** REQ-BKT-01-01, REQ-BKT-01-02.
**Setup:** Target[1,2,900,901], cutoff2; future_derived_outcome[1,2,90000,90100]; derived prefix, рассчитанный с full-series mean; отдельно genuinely known-ahead calendar feature и immutable source copy.
**Действие:** Existing historical data owner строит admitted view; OutcomeMasker/derived transform применяются до snapshot persist.
**Oracle:** Future outcome values недоступны ни в target, ни через derived/full-source feature path. Уже contaminated derived prefix не проходит простым truncation: пересчитан по[1,2] либо адресно отвергнут. Known-ahead calendar доступен по явному контракту. Source SHA/content неизменён; missing/unknown feature role даёт конкретный gap, не silent exposure.
**Место:** `tests/unit/scientist/methods/backtesting/test_masking.py; masking.py::OutcomeMasker`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-BKT-01-02 · native request binding E02-I03-C
**NOT_RUN. REQ:** REQ-BKT-01-01, REQ-BKT-01-02, REQ-BKT-01-09.
**Setup:** Действительный tiny Scientist/Foundry scenario и native CAS с историческим/маскированным snapshot; date-only/pre-periods/exact-step variants, duplicate date/contradiction, already-truncated attested variant.
**Действие:** Наблюдающая обёртка читает actual ExecuteRequest.input_bindings_ref, actual consumer загружает bound snapshot; foreign original snapshot — negative.
**Oracle:** Consumed target[1,2], admitted features из TEST01; exact profile совпадает с masked snapshot. Foreign snapshot отказан до execute; date-only совпадает с step2, ambiguous/contradictory refused. Valid already-truncated path явно обоснован; caller state/request unchanged.
**Место:** `tests/unit/scientist/methods/backtesting/test_backtesting.py; orchestrator.py::_BacktestReplicaFoundryPort`.
**Doubles:** Тестовые inputs допустимы. Native workflow/Foundry/CAS и actual data consumer не подменяются; spy только записывает запрос.

### TEST-BKT-01-03 · native fallback provenance regression
**NOT_RUN. REQ:** REQ-BKT-01-03.
**Setup:** Одна успешно выполненная replica с persisted cohort; metrics scalar mean_ate=7 без constant contract, затем list неправильной длины.
**Действие:** Выполнить _run_single_scenario и final report persist; fresh load scenario/manifest/cohort.
**Oracle:** Prediction остаётся degraded naive с scientist_predictions_missing; cohort exact ref есть в scenario и report input edge, completed1/failed0 и actual request доступны. Foundry execution count1, не2. Удаление cohort forwarding делает regression красным.
**Место:** `tests/unit/scientist/methods/backtesting/test_backtesting.py; orchestrator.py::_naive_with_cohort`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-BKT-01-04 · native multi-profile selector regression
**NOT_RUN. REQ:** REQ-BKT-01-04.
**Setup:** Одинаковые metrics bytes с двумя native CAS profiles: selected valid producer/default foreign; затем selected missing/foreign producer/default valid. Точный MetricsRef в actual SimulationResult.
**Действие:** Запустить constant forecast admission после сохранения replica и повторного чтения; сменить только default selection.
**Oracle:** Valid selected constant остаётся доступен независимо от default; invalid selected не получает admission от valid default. Artifact identity/profile передаются без сворачивания в ArtifactID; sibling profile не влияет на результат.
**Место:** `tests/unit/scientist/methods/backtesting/test_backtesting.py; orchestrator.py::_is_constant_forecast`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-BKT-01-05 · native trajectory semantic matrix
**NOT_RUN. REQ:** REQ-BKT-01-05, REQ-BKT-01-06.
**Setup:** Holdout coordinates t2,t3; valid outcome trajectory/unit/baseline/cutoff; same-length mean_ate list, ancient-A/B constant labels, wrong units/baseline/origin, extra coordinate; valid stationary constant7.
**Действие:** Producer contract validation и actual trajectory projection, report persistence/readback.
**Oracle:** Valid[7,7] проходит только с producer+matching semantics. Mean_ate/foreign coordinates не интерпретируются как прогноз; point output сохраняется как иной ограниченный artifact где применимо. Explicit coordinate subset сохраняет выбранные labels и provenance; нет безусловного list[:horizon].
**Место:** `plan.py::ForecastProfileContract; tests/unit/scientist/methods/backtesting/test_backtesting.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-BKT-01-06 · native positive uncertainty and counterexamples
**NOT_RUN. REQ:** REQ-BKT-01-04, REQ-BKT-01-06, REQ-BKT-01-09.
**Setup:** Настоящие selected SimulationResult/PropagationReport refs и admitted horizon draws/summary; отдельно mean-effect CI, mismatched confidence/coordinates/profile и missing envelope.
**Действие:** Existing uncertainty_source_projection resolves/admit→orchestrator→evaluator→fresh report.
**Oracle:** Correct per-coordinate predictive interval достигает evaluator с declared nominal. Mean-effect CI не размножен; missing interval не уничтожает годный point forecast. Sibling profile cannot substitute selected source. Existing interval availability/limitations сохранены.
**Место:** `scientist/nodes/builtins/simulate/uncertainty_source_projection.py; tests/unit/scientist/methods/backtesting/test_backtesting.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-BKT-01-07 · native replica scheduling and budget
**NOT_RUN. REQ:** REQ-BKT-01-07, REQ-BKT-01-09.
**Setup:** Tiny stochastic model поддержанного backend; n1 и n7 base seed12; одна deliberate replica failure; согласованный low budget; PROVIDED n7 с готовыми predictions.
**Действие:** Actual requests/outputs/runtime cost capture, повторить same seed plan, затем бюджетный отказ до следующей дорогой работы.
**Oracle:** Физические requests1/7 с seed12/12..18, reproducible same plan; failed остаётся requested denominator. Budget limit не запускает запрещённый dispatch; known cost+unknown split видимы. PROVIDED execute count0. Exact cached execution не объявлен независимой новой replica.
**Место:** `orchestrator.py::_predict_with_scientist/_BacktestReplicaFoundryPort; tests/unit/scientist/methods/backtesting/test_backtesting.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-BKT-01-08 · native supported ensemble projection
**NOT_RUN. REQ:** REQ-BKT-01-07, REQ-BKT-01-08, REQ-BKT-01-09.
**Setup:** Три совместимые trajectories по t2,t3: [1,3],[3,5],[5,7], exact refs/units/baseline и distinct execution records; вариант failed replica и другой estimand одной replica.
**Действие:** Existing numerical projection строит coordinate-wise mean/ensemble, persists linked summary, fresh reader.
**Oracle:** Full mean[3,5], ensemble сохраняет3×2 значения или эквивалентные достаточные statistics с declared смыслом; не[4,4]. Failed/foreign replica не исчезает из requested3 и не превращается в0; incomplete summary clearly scoped либо unsupported. No extra Foundry call для уже имеющихся draws.
**Место:** `tests/unit/scientist/methods/backtesting/test_backtesting.py; existing numerical summary owner, выбрать в DEC-PROJECTION`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-BKT-01-09 · shared fresh downstream packet
**NOT_RUN. REQ:** REQ-BKT-01-08, REQ-BKT-01-09.
**Setup:** Один accepted single-run и один supported ensemble с native persisted backtest report; incomplete/unsupported cohort positive fallback.
**Действие:** Fresh downstream report consumer читает predictions, interval availability, all cohort edges, warnings и effective mode.
**Oracle:** Numeric result, coordinates, source refs и ограничения совпадают с producer; complete/partial/unsupported не сливаются в одинаковый PASS. Corpus fixture доказывает wiring, не независимость произвольных Monte Carlo streams и не внешнюю predictive validity.
**Место:** `E02-I03-C; ir/analytics/backtest.py canonical loader`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### Запуск: адаптируемый шаблон, не выполненная команда

Из `policy-engine/` в поддержанной Python3.14 среде с закреплёнными зависимостями. Этот документ не разрешает автоматические installs; отсутствующая dependency означает BLOCKED конкретной проверки.

```bash
python -V
python -m pytest -q tests/unit/scientist/methods/backtesting/test_masking.py tests/unit/scientist/methods/backtesting/test_backtesting.py
# Новый native E02-I03-C variant расширяет actual owner suite; точный selector/extra согласовать по выбранному backend.
```

Фиксировать профиль/backend, inputs/seed/hash, deciding output и exit. Ruff и затронутые architecture/import checks выбирать по фактическому patch; native slot согласовать, полный suite на каждый пакет не копировать.

## 7. Общая интеграция и ownership

Переиспользовать **E02-I03-C**: [канонический контракт LANE-03](../03_Интеграция/LANE-03.md). Одно свидетельство связывается с конкретными вариантами и REQ; не считается многими независимыми подтверждениями.

BKT-01 владеет masker/plan/replica adapter, exact selected forecast refs и semantic projection. Fabric/source feature owner подтверждает availability/dependency projection. BKT-02/03 владеют численной оценкой/aggregate report; BKT-04 — generic CV selection before materialization и bootstrap selector before RNG. В orchestrator один writer: local cohort/profile repairs сначала, затем semantic/view capability, затем shared native scenario.

- **BKT-02 / BKT-03:** Один orchestrator/report writer: numeric empty/overflow and aggregate repairs согласовать, не дублировать report projections.
- **BKT-04:** Выбранные CV train/test boundaries согласованы с temporal view; expanding-window selection не заменяет feature availability.
- **FRC-02:** Переиспользовать forecast/source semantics и existing uncertainty owner; predictive experiment не causal CI.
- **LANE-06:** Существующие runtime budget/cost/admission и exact artifacts; не создавать собственную параллельную execution ledger.

## 8. Совместимость, миграция и возврат

Сохранить legacy results как historical unqualified, не повышать их по новой trajectory schema. При typed contract extension дать явную versioned read/limited old path; default old list не объявлять admitted trajectory без semantics. PROVIDED remains no-rerun; n1 остаётся минимально полезным supported режимом. Rollback нового ensemble/view extension возвращает адресный unsupported/limited с сохранёнными raw artifacts, не reinstates target-only exposure или scalar repetition. Exact refs и cohort lineage не откатывать к default.

## 9. Free-grow и обоснованные границы

- [universal-policy-design-target-architecture-and-gap.md — D0, universal typed capabilities](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md): Один temporal feature/trajectory contract работает с новым совместимым источником и моделью; новые case-name branches не нужны. Unknown semantics остаётся явной, полезный output не уничтожается.
- [wave5-evidence-substitution-ratification.md — K01 и K07–K08](../05_Основания/Архитектура/wave5-evidence-substitution-ratification.md): Snapshot identity не доказывает availability содержимого; scalar/list shape и distinct seed не заменяют scientific meaning/independence.

## 10. Конечные решения и сдача

### DEC-BKT-01-VIEW
**Вопрос:** Какой existing source/feature profile несёт availability и derived parents?
**Кто решает:** Fabric/source и Scientist backtesting owners.
**Конечное действие/выход:** Census только actual input-binding/source/profile/feature routes; выбрать имеющийся contract либо минимальное typed расширение. Сдать field-role/dependency map и TEST01–02 с known-ahead positive и leaked-derived negative.
**До решения:** Неклассифицированные post-cutoff outcome-derived данные не доступны admitted replay; допустимый known-prefix остаётся полезен.

### DEC-BKT-01-PROJECTION
**Вопрос:** Какой существующий numerical owner агрегирует совместимые replica trajectories?
**Кто решает:** Foundry numerical и Scientist owners.
**Конечное действие/выход:** Найти актуальный trajectory/draw summary контракт и выбрать один поддержанный aligned outcome case; реализовать coordinate-wise projection с original refs, TEST08–09. Если compatible owner отсутствует, добавить минимальную общую projection функцию у numerical owner, не новый runtime service.
**До решения:** Честный unsupported плюс полный cohort; n1 supported. Не считать это завершением requested useful multi-run capability.

### DEC-BKT-01-BUDGET
**Вопрос:** Где actual replica route проходит существующее budget admission и accounting?
**Кто решает:** Runtime execution owner.
**Конечное действие/выход:** Проследить native request до actual budget gate, предъявить pre-dispatch refusal и known/unknown cost projection. Если gate отсутствует на этом route, подключить существующий owner, не вводить локальную имитацию счётчика.
**До решения:** Не обещать budget compliance по числу requests; явно ограничить unattended multi-run до принятого admission.

Сдать base/head и patch, exact REQ→TEST→shared variant, исходные входы и их идентичности, actual команды/exit/log, независимые численные/семантические oracles, positive/negative/removal controls, сохранённые инварианты и открытые решения. Source-only, fixture, native и scientific qualification отражать отдельно. Не повышать partial/NOT_RUN до PASS; квалифицированный локальный механизм не является автоматической готовностью всей политики.
