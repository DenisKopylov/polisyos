# Техническое review решений и проверок PolicyOS E02

## Главный вывод

**Архитектурный каркас следует сохранить, но исходную редакцию нельзя считать технически оптимальной и достаточной для всех заявленных способностей без адресных уточнений.** Массовая смена стека, новый orchestration framework или универсальный validator не обоснованы. Главные улучшения находятся в математическом смысле отдельных контрактов, порядке обработки данных, полноте общего механизма и независимости тестовых свидетельств.

Рассмотрены все 127 пакетных решений и проверок, 12 лейнов, 38 общих сценариев и четыре сквозные истории. Получено 35 исходных замечаний, объединённых в **34 самостоятельных наблюдения**: предложение использовать `statistics.mean` для FED/UQS посчитано один раз. Это **не 34 доказанных продуктовых бага**. Здесь есть ошибки предложенного решения, подтверждённые ограничения текущего кода, пробелы приёмки, непрогнанные runtime-гипотезы, необязательные оптимизации и конкретизация уже честно записанных ограничений.

Основание: исходный комплект от 1 ноября 2026 года, SHA-256 `e08baa70c8acf92f8f2e5afd8ced38c94213355dea07c4b33b14a417aefdebf3`, код `20d9009be21097bfbdc38a546a15cc60213b8ace`. Исходный комплект и продукт не менялись. Предлагаемая редакция v2 находится в отдельном архиве. Она уточняет будущую работу; **продуктовые тесты остаются NOT_RUN**.

## Что исправить в постановке прежде соответствующей реализации

### Граница применимости должна действовать до потери информации

- **CAL-02:** умножение уже вычисленной loss на fit mask не исключает переполнение на holdout из обучения. Нужна безопасная подготовка исключённых operands до нелинейной операции, при сохранении отдельного nonfinite-model guard. Проверка должна сравнивать не только loss, но gradient, Hessian и настоящий optimizer update
- **UDF-05:** проверять большой integer ID после общего `np.asarray` поздно: смешанный int/float input уже мог потерять точность. Admission выполняется на исходных scalar values
- **FIT-01:** outcome scaler, обученный до разделения folds, может передать информацию test-fold Y в regularized nuisance fit. Нужен fold-owned preprocessing; final targeting законно использует heldout outcomes и не должен искусственно замораживаться
- **PLG-03:** отдельно квалифицируется native путь с разрешёнными неактивными padding rows. Возможное прохождение NaN через actor/loss до маски — гипотеза по source, не объявленный исполненный runtime FAIL

### Статистическое имя должно соответствовать вычисляемому свойству

- **FUN-03:** FDR/precision/FOR нельзя выдавать за FPR/TPR/FNR. Нулевое число ошибок при малом или смещённом корпусе — полезное наблюдение, но не population guarantee. Сначала определить operational estimand, cohort, label availability и смысл порога. При недостаточном evidence сохранить descriptive результат
- **CAU-03:** kernel localization weights не становятся inverse-variance weights автоматически. Conventional kernel-RDD covariance требует подходящей variance model; историческая формула сохраняется только с честной compatibility интерпретацией
- **DDM-02:** название moving-block bootstrap должно отражать действительно исполненный producer. Calibration source нельзя повторно назвать независимым holdout. Совпадение числовых значений само по себе не означает совпадение наблюдений; нужны source artifact и observation/time coordinates
- **BKT-02:** непредставимый квадрат ошибки не всегда делает непригодной саму comparison row. Представимые MAE/RMSE и полезный residual сохраняются, availability SSE и trust рассматриваются отдельно

### Общий механизм шире одного исправленного вызова

- **EXE-01:** transport-only исправление нужно проверить на всех фактических sibling await routes над shared future, сохраняя bounded user callbacks и physical slot ownership
- **CLI-01:** JSON-quoted object key `__proto__` остаётся особым JavaScript setter. Нужны computed data keys/entries и корректная собственная optional presence. Отдельный тест должен возвращать настоящий service response обратно в generated client, а не соединять fake fetch с независимым Python GET
- **DFI-03:** существующая синхронная content-stage обёртка не принимает harvest. Direct smart/off route должен использовать действительный async admission и receipt owner, включая изменившийся input basis при прежнем имени источника
- **SCL-01:** законное offline cache reuse не должно сначала требовать live DNS. При этом current offline policy и live fetch security остаются отдельными обязательными границами

## Где усиливаются проверки, а не объявляется новый дефект алгоритма

- Statsmodels comparison с DoWhy linear regression — полезная adapter parity, но обе стороны используют один backend. Добавлен отдельный аналитический finite-design oracle и сохранена самостоятельная coverage campaign
- Ненулевой PPO gradient и изменение действия не исключают неверный знак loss. Нужны независимые sign/clipping/value/entropy/GAE controls, не обещание welfare improvement после двух updates
- Детерминированный NCM с фиксированным evidence хорошо проверяет joint contrast, но не actual seed propagation. Его сохраняют и дополняют отдельным native seed-sensitive witness
- NCM summary не должен оценивать обычный normal quantile дополнительными100000 global random draws на каждый вызов. Deterministic library inversion устраняет ненужную работу и случайность CI; она не доказывает scientific coverage или определённость interval при одном sample
- Маленькие PCA fixtures не включают stochastic branch `auto`. Приёмка full-request RNG должна охватить реально выбранный solver и его локальный stream на соответствующей shape, без требования всегда применять дорогой full SVD
- Refit count и shrink interval не доказывают правильность replica target. Добавлен независимый contrast/quantile oracle по фактическим выбранным source rows
- Непредставленный warm JAX parent не считается проверенным холодным process smoke. Launch topology квалифицируется отдельно; fork не объявлен неизбежно сломанным, а spawn — автоматической заменой

## Библиотеки и технологии

**Предпочтение отдаётся подходящему готовому механизму, а не новизне названия.** В приложениях подробно сопоставлены технологические решения, включая вариант ничего не заменять. Эти сравнения не являются списком новых зависимостей для установки.

| Область | Предпочтение | Что не следует делать автоматически |
|---|---|---|
| Точный finite mean/midpoint | Тонкий общий wrapper над квалифицированным CPython `statistics.mean`, независимые Fraction/Decimal controls | Подменять его `fmean`/обычным sum/n, писать собственный accumulator без причины |
| Calibration, UQ, PCA | Сохранить NumPy/SciPy/JAX/sklearn; уточнить masks, covariance, solver, dtype и RNG | Менять backend вместо исправления семантики или навязывать float64 глобально |
| Bayesian search | Сохранить существующую проверенную GP fit/condition/load цепочку; различать measurement, prediction и surrogate state | Ослаблять fitted-source guard ради произвольного score; требовать новый optimizer |
| Causal worker | Явно квалифицировать отдельный worker и его lock; использовать независимые аналитические oracles | Считать parent environment свидетельством другого interpreter/backend |
| Runtime и persistence | Общие существующие owners, actual boundaries, стандартные примитивы с сохранением guarantees | Второй executor, новый distributed framework или смена БД без необходимости |
| Retrieval | Разделить index integrity, ANN recall, semantic usefulness и current admissibility | Считать один self-query доказательством поиска или менять vector DB из-за неизмеренного предположения |
| Graph storage | Сохранить работающие контракты; решение о новом backend принимать по callers и supported profile | Считать archive status Kuzu доказанным инцидентом либо игнорировать maintenance risk при новом расширении |
| Проверки | Использовать существующие pytest/Hypothesis и scoped mutation owner; поддержанные профили и независимые свойства | Новый тестовый framework, 100% mutation score как доказательство способности, retry-until-green |

Pinned versions и точные первоисточники приведены в библиотечных реестрах. Современная документация не считается гарантией наличия API в старом locked package. Техническая пригодность, совместимость и измеренная производительность — разные вопросы.

## Насколько это free-grow

У комплекта уже есть важные правильные ограничения: полезный positive path, запрет подмены принимаемого owner, разделение candidate/empirical/authority, actual producer→persist→fresh consumer, сохранение partial результата. Называть его просто системой отказов было бы неверно.

Но общий код без ветки `if case_id` ещё не доказывает переносимость. В существующем X03 уже запрещено выдавать вручную подготовленный второй profile за независимое обобщение. Уточнение v2 делает этот запрет проверяемым: фиксируется executable/schema boundary, после неё независимо выбирается ранее не использованный совместимый случай, отдельно учитываются разрешённые данные/model IR и новые исполняемые semantics. Python callback внутри YAML остаётся кодом. Если действительно нужен новый primitive, он допускается как развитие, после которого нужна новая проверка переноса.

Для заявленного discovery проверяется actual supported request→query→known-groundable resource→consumer. Прямой injected ref доказывает wiring, но не recall. Используются существующие G*/GL owners, а не новая платформа.

Два X04 ограничения уже были честно записаны. Их уточнение не объявляется новой находкой: pairwise feasibility не доказывает joint feasibility трёх действий; отдельные monitor tests не доказывают current/historical lifecycle того же результата. Предложены конечные fixtures через существующие owners. Если такого owner нет, соответствующая способность остаётся ограниченной, без выдуманного allocator или институционального разрешения.

## Не раздувать ремонт

- PS-F02 о переиспользовании actual measurements независимо от proposer GP — отдельное ограниченное расширение. Оно не отменяет существующий fitted-GP guard и не становится скрытым условием всех локальных repairs
- Warm-index validation и рост registry сначала измеряются. Для текущего fallback с тремя capabilities linear scan может быть лучшим решением
- Не требуется запускать все лейны, все backends и все платформы после каждого небольшого patch. Проверяются применимые зависимости и фактические границы
- Квалификация на synthetic oracle подтверждает механизм, но не причинную идентификацию, социальную полезность или полномочие реальной политики

## Что находится в подробных материалах

По каждому пакету дан вердикт с обоснованием. По замечаниям указаны исходная спорная формулировка, точные source locations, контрпример, альтернативы, предпочитаемое решение, replacement requirements/tests, совместимость и пределы доказательств. Отдельно приложены библиотечные решения, независимые арифметические проверки и review изменений предлагаемой v2.

Продукт не исполнялся. Небольшие независимые арифметические эксперименты и JavaScript language counterexample явно отделены от native product acceptance. Внедрение, сборка, runtime qualification и реальная предметная валидация остаются будущей работой.

[Обзор всех 127 пакетных вердиктов](Обзор_127_пакетов.md)

## Подробные обзоры

- [Лейны 01–02 — policy cycle и поиск](policy_search/review.md)
- [Лейны 03–04 и10 — Foundry, обучение и численные методы](foundry_numeric/review.md)
- [Лейны 05 и11 — causal inference и статистическая квалификация](causal_statistics/review.md)
- [Лейны 06 и12 — runtime, хранение и поставка](runtime_delivery/review.md)
- [Лейны 07–09 — данные, приобретение и retrieval](fabric_acquisition/review.md)
- [Общие способности, free-grow и сквозная приёмка](generalization/review.md)

[Единый реестр замечаний](consolidated_findings.json) сохраняет все первичные выводы и единственное объединение FED/UQS. Точные границы чтения и независимых экспериментов находятся в coverage и peer-review отчётах соответствующих групп. P в отчётах означает исходный комплект v1, R — закреплённый репозиторий. Изменения файлов в proposed_changes относятся к предлагаемой редакции, не к исполненным product patches.
