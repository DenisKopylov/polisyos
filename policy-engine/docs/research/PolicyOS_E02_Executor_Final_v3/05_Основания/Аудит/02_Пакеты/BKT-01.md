# BKT-01 — исторический вход, смысл прогноза и сохранённые реплики
## C32 · 31 октября 2026 года

**Исходные IDs:** B166, B169, B170. **Порядок:** 32/127. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Аудит без изменения продукта.

## Решение

**Основной разрыв target mask→Scientist input уже исправлен:** префикс материализуется в snapshot, а actual Foundry adapter проверяет именно этот snapshot в input bindings. Date/pre-period cutoff разрешается по time_index; неоднозначность и противоречие отвергаются. Scalar больше не становится прогнозом без producer-bound constant profile; длинная trajectory не обрезается молча.

**Повторы теперь действительно различают запрошенный план:** отдельные run IDs, seeds и физические requests, сохранённый cohort с completed/failed и ссылками. Multi-run projection пока unsupported, но индивидуальные результаты не выброшены. PROVIDED не запускается повторно.

Остались три ограниченно подтверждённых разрыва: нецелевые future-derived поля остаются внутри masked snapshot (**C32-R01**); invalid prediction fallback теряет уже сохранённый cohort ref (**C32-R02**); scalar admission читает default metrics manifest вместо выбранного profile (**C32-R03**). Смысл и временная ось обычной list trajectory ещё не связываются полностью (**C32-G01**).

**24 MATCH, 0 ERROR.** Настоящие definitions и request DTO bodies исполнены, но workflow/Foundry/CAS — явные fixtures. Native тесты остановлены до collection из-за отсутствия pytest. Это не native runtime PASS и не полное закрытие пакета.

## 1. Матрица исходных задач

| ID | Проверенный ремонт | Содержательный остаток |
|---|---|---|
| B166 | Immutable target prefix, синхронная time axis, date/pre-period checks, persisted snapshot, проверка actual input binding до delegate | C32-R01: доступность нецелевых post-cutoff/derived значений; C32-G02: native данные и feature pipeline |
| B169 | Explicit typed constant profile и producer identity; exact list length; canonical uncertainty source admission; scalar ATE без profile отказан | C32-R03: выбранный metrics profile теряется; C32-G01: estimand/unit/baseline/time semantics; C32-R02: downstream lineage после отказа |
| B170 | n=1/n=7 дают разные requests/seeds; failed replica остаётся в requested denominator; PROVIDED без лишних исполнений | C32-R02: cohort ref теряется в одном fallback; C32-G02: полезная multi-run projection, native cost/budget и независимость draws |

[Полная карточка](../05_Источники/BKT-01_исходные_строки.txt), строки3974–4083. Предложенный `test_bkt_01.py` не найден; актуальные проверки уже живут в `test_backtesting.py` и `test_masking.py`. Отсутствие предложенного имени не считается отсутствием реализации.

## 2. Producer → persisted view → фактический request

Actual masker делает deep copy, проверяет target shape, cutoff и согласованность time_index, затем сохраняет prefix либо replace_nan. P01/P02: `[1,2,900,901]` и cutoff2 дают `[1,2]`, исходник не меняется. P03/P04: duplicate date и противоречащие pre-periods отвергнуты. [S02:24–110](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/masking.py#L24-L110) [S02:112–158](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/masking.py#L112-L158)

Orchestrator сохраняет masked payload и DataSnapshot. Каждый replica state получает этот snapshot; `_BacktestReplicaFoundryPort` разрешает **реальные input_bindings request**, сравнивает полную identity с ожидаемым snapshot и только затем вызывает delegate. P07: чужой snapshot не дошёл до delegate. Это сильнее, чем записать префикс в произвольное поле state. Настоящий native simulation node также вызывает `ctx.foundry.execute` с типовым ExecuteRequest; этот node только прочитан. [S03:703–730](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py#L703-L730) [S03:205–241](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py#L205-L241) [S03:1261–1310](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py#L1261-L1310) [S11:301–375](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/simulate/run_simulation.py#L301-L375)

### C32-R01 — маска target не очищает весь допустимый view

В P06 вход дополнен `future_derived_outcome=[1,2,90000,90100]`. Masker режет только `target_metrics` и time_index; весь словарь сохраняется. Fixture delegate, получивший **правильно связанный** snapshot через actual adapter, читает target `[1,2]`, но также все future-derived values. Доказана доступность будущих значений в данном view, **не доказано использование этого поля настоящей production моделью**. [S02:36–100](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/masking.py#L36-L100) [S03:1267–1274](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py#L1267-L1274)

Нельзя механически обрезать всякий список: известные заранее экзогенные признаки могут быть допустимы. Нужна существующая owner-проекция с объявленными temporal/availability roles и отказом для неквалифицированных future outcome-derived полей. Производные признаки должны вычисляться из допустимого источника; обрезка уже протёкшего derived prefix недостаточна.

## 3. Реплики и реальное различие requests

Actual loop создаёт уникальный run_id, seed=`base+index`, `n_simulation_runs=1` в каждом дочернем запросе. Adapter копирует настоящий ExecuteRequest и обновляет FoundryExecConfig.seed; исходный request остаётся seed0. Сверяются workflow run_id, successful execution, exec_plan, runtime seed-source note, metrics и SimulationResult refs. Cohort сохраняет requested/started/foundry_execute/completed/failed, физический request и ссылки каждого результата. [S03:712–880](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py#L712-L880) [S03:881–930](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py#L881-L930)

P08: n1/n7 вызвали controlled delegate1/7 раз, seeds12 и12…18; caller state/request не мутировали. P09: ошибка второй из3 дала requested3/completed2/failed1 и конкретную причину. P10: чужой workflow report не принят. **Это исполнение exact orchestration/adapter с fixtures, не настоящие Foundry simulations и не доказательство независимости MC draws.**

При n>1 сохраняется cohort, а итоговая projection честно становится degraded naive с `scientist_replica_projection_unsupported`. Не следует стирать уже полученные распределённые результаты или усреднять их в scalar ради nominal success. P11: PROVIDED даже при n7 не dispatches Scientist. [S03:639–658](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py#L639-L658) [S03:933–956](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py#L933-L956)

### C32-R02 — semantic fallback отрывает сделанное исполнение от результата

После сохранения completed cohort ветка отсутствующих/непригодных predictions строит naive payload, но забывает `replica_cohort_ref`. P13 выполняет actual `_run_single_scenario`: scalar mean_ate правильно отвергнут, cohort с completed1 сохранён, **в scenario metadata ссылки уже нет**. P14 воспроизводит то же на неправильной длине list. Общая persist-ветка добавляет cohort edge только при наличии ссылки в scenario metadata. [S03:1005–1021](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py#L1005-L1021) [S03:592–603](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py#L592-L603) [S03:537–551](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py#L537-L551)

Минимальное продолжение — использовать уже существующий `_naive_with_cohort` либо сохранить equivalent reference projection. Не запускать заново симуляцию и не восстанавливать неверное scalar-as-trajectory поведение. Native report persistence не исполнялся; downstream потеря report edge установлена чтением consumer.

## 4. Что теперь означает forecast profile

Actual `ForecastProfileContract` требует `constant_forecast`, `outcome_trajectory`, producer/version, horizon и уникальный time_index нужной длины. P13/P14 отказывают raw scalar и list другой длины; P15 сохраняет explicit constant `[7,7]`; P16 отвергает profile без producer. Однако отсутствие admitted uncertainty остаётся отдельным ограничением: полезный point forecast не превращается автоматически в допустимый prediction interval. [S01:26–52](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/plan.py#L26-L52) [S03:960–1024](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py#L960-L1024) [S03:1032–1150](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py#L1032-L1150)

### C32-R03 — exact selected metrics view теряется перед producer check

Сначала metrics_ref проверяется против actual SimulationResult с полной identity. Затем `_predict_with_scientist` оставляет только ArtifactID и повторно читает payload; `_is_constant_forecast` берёт default manifest по этому ID. P17: выбранный profile с верным producer, но foreign default — прогноз ошибочно теряется. P18: выбранный profile без producer, но matching default — scalar принимается. Bytes одинаковы; меняется только выбранный manifest. [S03:816–834](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py#L816-L834) [S03:960–975](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py#L960-L975) [S03:1215–1235](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py#L1215-L1235)

Это actual selector-loss control flow в multi-profile fixture store, не native CAS execution. Нужно донести первоначальный selected MetricsRef до read/producer check, а не создавать новую схему authority. Полезный exact-profile guard физических input bindings уже существует и сохраняется; его нельзя обобщать на ещё не проверенный metrics consumer.

### C32-G01 — trajectory shape всё ещё не определяет её предмет

P19: constant profile с чужими `ancient-A/B` labels принимается для ряда с holdout `t2/t3`: проверяется уникальность/длина, но нет сравнения координат. P20: list нужной длины с metadata `estimand=mean_ate` и чужими dates остаётся Scientist prediction; ограничение возникает по отсутствующим envelope refs, не по смыслу trajectory. P21 показывает, что **typed constant contract** сам mean_ate отвергает. Эти факты не противоречат ремонту raw scalar: один путь усилен, общий trajectory binding ещё не доведён.

Остаток — связать quantity/units/baseline/origin/coordinates и допустимую projection выбранного producer с историческим запросом. LLM может выбрать гипотезу и метод; не нужен универсальный deterministic model inventor. Нужен проверяемый transport именно выбранного смысла и готового результата без бессмысленного повторного расчёта.

## 5. Границы и полезное продолжение

**C32-G02:** существующие tests проверяют masking, scalar/length, exact input profile, replica requests/readback и failed denominator. Они прочитаны, не исполнены. Native attempt на полном masking test дал exit1 до collection: pytest отсутствует. Не установлены native CAS/Science/Foundry chain, положительная uncertainty source admission, реальные cost/budget и независимые stochastic replicas.

Canonical uncertainty reader разрешает выбранные SimulationResult и PropagationReport, затем existing owner admission; простой raw envelope не подменяет это основание. В C32 эта положительная цепочка не исполнялась. [S10:377–473](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/simulate/uncertainty_source_projection.py#L377-L473)

Сохранить prefix binding, honest unsupported result, индивидуальные refs/denominators, numeric point forecasts и все запрещающие interval checks. Сначала закрыть три локальных разрыва существующих owners; затем выполнить найденные tests в поддерживаемой среде и квалифицировать один полезный forecast/replica projection. Без нового глобального replay service или реестра.

[Диагностика](../04_Проверки/C32_BKT01/bounded_diagnostics.json) · [Команды](../04_Проверки/C32_BKT01/commands.json) · [Native границы](../04_Проверки/C32_BKT01/native_verification.json) · [Источники](../05_Источники/C32_источники.json) · [Остатки](../01_Реестры/C32_остатки.json).

**32/127 пакетов ограниченно рассмотрены; 83 уникальных B/LA частично оценены. Следующий — BKT-02.**
