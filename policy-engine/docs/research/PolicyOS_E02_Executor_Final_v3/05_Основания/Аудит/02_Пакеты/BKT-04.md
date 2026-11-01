# BKT-04 — выбранные CV folds и разрешённая bootstrap-статистика
## C35 · 31 октября 2026 года

**Исходные IDs:** B174, B175. **Порядок:** 35/127. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Только аудит.

## Решение

**Оба исходных локальных ремонта подтверждены bounded execution.** CV выбирает границы до materialization и отказывает неверным параметрам прогресса до loop. Bootstrap отказывает неизвестной статистике до RNG, требует finite1D observations и finite scalar result, сохраняет выполненный selector отдельно от display label. Callable declaration честно остаётся consumer_asserted, а не доказанной семантикой.

**25 MATCH, 0 ERROR.** Новая конкретная R-находка в этих двух ремонтах не установлена. Остались qualification gaps: native tests/activation, качество generic CV evaluator metrics, научная допустимость resampling и downstream interpretation. Это не полное закрытие пакета и не утверждение, что generic CVResult уже является доверенным empirical artifact.

## 1. Матрица исходных задач

| ID | Что действительно работает | Что ещё квалифицировать |
|---|---|---|
| B174 | Discrete/positive progress checks, только selected folds, сохранение прежней valid grid, изоляция callback arrays | C35-G01: native/activation; C35-G02: shape/finite/missing/weight policy выбранного evaluator |
| B175 | Unknown statistic отказан до RNG, finite1D inputs/results, named identity и honest callable basis, seed reproducibility | C35-G01: native consumer; C35-G03: exchangeability, effective n, population/coverage и callable meaning |

[Полная карточка](../05_Источники/BKT-04_исходные_строки.txt), строки4309–4396. Предложенный `test_bkt_04.py` не найден; настоящие tests находятся в `test_cv.py` и `test_bootstrap.py`. Имена из плана не использованы как механический критерий реализации.

## 2. Лимит ограничивает подготовку, а не только финальный список

Actual CV проверяет `operator.index`, отдельно отвергая bool/np.bool, и требует допустимые train/step/max_folds. Количество границ вычисляется арифметически; только выбранные positions переходят в list(range). [S01:32–94](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/cv.py#L32-L94)

P01 n1000/max_folds3 создаёт **6 списков, 1504 элемента**, train sizes `[2,500,999]`, tests `[2],[500],[999]`. Namespace-local observer считает actual list materialization; не используется приблизительная оценка по итоговому размеру. P02 одиннадцать invalid parameter cases отказаны до первого range, включая step0/negative/fraction/bool и неверные train/cap. Бесконечный цикл не запускался.

P03 сравнивает **3040** малых комбинаций с явно ограниченным reference прежней full-grid/linspace policy: selected splits совпадают. P04 сохраняет NumPy integer inputs. P05 train=n возвращает zero folds. Экономия не достигнута незаметной сменой научной сетки.

P06 actual runner передаёт только три выбранных train/test arrays в evaluator и возвращает CVResult; P07 попытки callback изменить train/test не изменяют original array или соседний fold, поскольку fancy indexing даёт отдельные arrays. [S01:119–160](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/cv.py#L119-L160)

Это измерение объёма подготовки, **не коэффициент ускорения всей системы**. Публичный helper может быть полезен самостоятельно; обязательный вызов на каждом GY/runtime пути не установлен.

## 3. Статистика разрешается до sampling

P08 `[0,0,9]`, display `median`, selector `medain`, budget1000: actual typed error `unknown_statistic`, **0 RNG constructions**. Unknown explicit selector не заменяется default mean. P09 при одинаковом display label named mean/median/std дают соответственно3/0/√27, каждый с собственным resolved selector и basisrecomputed. P10 ordinary JSON dataclass readback сохраняет именно mean3 и median0. [S02:78–118](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/bootstrap.py#L78-L118) [S02:208–217](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/bootstrap.py#L208-L217)

P11 оба bootstrap entrypoints отвергают2D observations до callback/RNG, не flattening sampling unit. P12 NaN/±inf observations отвергнуты до RNG. P13 invalid point result не расходует draws; P14 invalid first sampled result прекращает цикл после point+одного draw и не выдаёт normal CI. Ранее полезные empty/count/confidence guards сохранены P22. [S02:172–205](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/bootstrap.py#L172-L205) [S02:220–235](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/bootstrap.py#L220-L235)

P19 caller-owned exception сохраняет исходный TypeError, а не превращается в успешный mean или нерелевантный validation default. Это полезная граница: функция не должна маскировать ошибку пользовательского метода.

## 4. Callable identity, seed и реальный RMSE

P15 две closures с одинаковым function name, но quantiles0.5/1, дают0/9 и разные declared IDs; обе помечены **consumer_asserted**. P16 anonymous callable сохраняет полезный maximum9, но statisticNone/basisnot_established. P17 пустая/нестроковая identity отвергается до callback, P18 builtin mean нельзя переименовать statistic_idmedian. [S02:25–42](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/bootstrap.py#L25-L42) [S02:92–102](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/bootstrap.py#L92-L102) [S02:120–135](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/bootstrap.py#L120-L135)

Нельзя объявлять декларацию произвольного callable проверкой его математики, но нельзя и запрещать полезный callback только из-за отсутствия универсального semantic verifier. Текущий контракт явно удерживает различие.

P20 одинаковый seed воспроизводит bounds. P21 `bootstrap_scenario_metrics` считает RMSE **на каждом resample**: отдельная bounded reference последовательность настоящего RNG и percentile даёт точно те же bounds. Это не square-root уже агрегированного интервала другой статистики. MAE остаётся mean абсолютных ошибок; internal RMSE declaration `root_mean_square` имеет consumer_asserted basis. [S02:138–169](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/bootstrap.py#L138-L169) [S02:238–246](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/bootstrap.py#L238-L246)

P25 singleton std использует существующую convention0, не утверждая научную small-sample определённость или population coverage.

## 5. Что не следует смешивать с доказанным ремонтом

**C35-G02 — generic CV output ещё не квалифицированный measurement.** P23 evaluator возвращает NaN metric в одном из двух folds и отсутствующий metric в другом: ordinary CVResult содержит n_folds2, один metric-bearing fold и meanNaN. P24 CV передаёт2D arrays callback, хотя docstring называет data1D; bootstrap, напротив, явно запрещает2D. [S01:97–160](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/cv.py#L97-L160)

Это executable предел generic helper, **не доказанный production admission defect**. Не установлен authoritative consumer, который принимает такой CVResult как валидное измерение. У выбранного evaluator/caller нужно определить shape, finite/missing policy, per-metric denominator и веса. Если multivariate callback намеренный, его следует сохранить явно; нельзя молча flatten, подставлять0 или стирать полезные partial metrics.

**C35-G03 — независимость и смысл bootstrap не возникают из seed.** Helper ресэмплирует элементы как exchangeable observations. Временная/cluster зависимость требует выбранного подходящего метода, а не запрета функции для действительно независимой выборки. Confidence level, finite checks и dataclass JSON не доказывают empirical coverage, causal relation или переносимость на population. Обоснование observation unit и effective n остаётся предметным.

**C35-G01 — runtime activation/native tests.** Exact-symbol search по src показал собственные helper calls и описание в README; одно совпадение DOE — имя параметра, не вызов этой функции. Полные facade и orchestrator run прочитаны. Не заявлено отсутствие всех dynamic callers или обязательность helper на всём runtime. Для связанного результата нужен конкретный intended caller, а не новый глобальный scheduler/реестр. [S07:1–106](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/__init__.py#L1-L106) [S09:428–562](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py#L428-L562)

## 6. Исполнение и продолжение

Полностью прочитаны actual CV/bootstrap tests. Native команда на обоих файлах завершилась до collection: `No module named pytest`; repository tests не исполнены. Один bounded probe дал25 MATCH/0 ERROR с настоящим NumPy и actual helper/error definitions. Синтетические data/callbacks, isolated imports и локальные counters раскрыты; native package import, CAS/authority consumer, scientific coverage campaign и end-to-end performance не проверены.

Сохранить оба локальных ремонта. Следующий практический шаг — выполнить найденные focused tests в поддерживаемой среде и квалифицировать выбранный caller/evaluator с его sampling/metric policy. Новые R-находки не добавлены искусственно ради одинакового шаблона; остаются конкретные G-границы, а не заявление о полной готовности.

[Диагностика](../04_Проверки/C35_BKT04/bounded_diagnostics.json) · [Команды](../04_Проверки/C35_BKT04/commands.json) · [Native границы](../04_Проверки/C35_BKT04/native_verification.json) · [Источники](../05_Источники/C35_источники.json) · [Остатки](../01_Реестры/C35_остатки.json).

**35/127 пакетов рассмотрены ограниченно; 90 уникальных B/LA частично оценены. LANE-03 пройдена в этом ограниченном смысле. Следующий — FRY-01.**
