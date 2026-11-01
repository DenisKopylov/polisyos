# SIM-03 — контрасты, реплики, SMM и экономия одинаковых расчётов
## Проход C10 · выпуск v008 · 31 октября 2026 · B19 / B21 / B23 / B25 / B26

**Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Репозиторий только читался. [Исходное поручение](../05_Источники/SIM-03_исходные_строки.txt), [индекс точных источников](../05_Источники/C10_источники.json), [исполненные наблюдения](../04_Проверки/C10_SIM03/bounded_diagnostics.json).

## 1. Содержательный итог

Пакет нельзя описывать как пять всё ещё не выполненных первоначальных ремонтов. Уже есть явная база вычитания, отдельное evidence, реальный цикл по seeds, сохранение samples и вычисление SE, локальное переиспользование физически одинаковых ролей, фиксированный набор обязательных SMM-моментов и проверка остатка полного совместного воздействия. Это следует сохранять и квалифицировать, а не заказывать заново.

Два новых локальных остатка воспроизведены на исходных телах: **C10-R01** — парный Monte Carlo может вернуть NaN/inf со статусом стандартной ошибки `estimated`; **C10-R02** — SMM-адаптер теряет повторно названный момент при преждевременном превращении пар «имя–значение» в словарь. Незавершённая связанная база контраста **C10-G01** отделена от дефектов: текущий N5 честно не называет вычитание из caller-baseline подтверждённым model-bound comparator.

| ID | Уже реализовано / сохранять | Точный остаток | Уровень этого аудита |
|---|---|---|---|
| B19 | Missing baseline не равен 0; evidence `None` и `{}` различимы; эффект проверяется относительно фактически заданной базы | Связанный comparator для конкретного estimand/модели/времени; сейчас положительное основание не установлено | Source trace + локальная арифметика; полный N5/CAS не исполнен |
| B21 | Seeds доходят до отдельных вызовов; n=1 даёт неизвестный SE; samples и знаменатели сохранены | Finite-семантика парного helper/адаптера; native действительность повторов и сохранённая причина отказа | Изолированный цикл и NumPy; численный backend — fixture |
| B23 | Одинаковые individual/joint или pair/joint роли используют один результат внутри вызова | Native readback и привязка выбранного поддержанного профиля; не требовать глобального кэша для закрытия локальной задачи | Локальный контроль calls/events/hash boundary |
| B25 | Один required set; incomplete не выигрывает; optional counts остаются диагностическими и проходят адаптер | Уникальность идентичностей до `dict(zip(...))`, квалификация методов/данных | Реальная NumPy-арифметика, исходные тела SMM, контролируемый producer |
| B26 | Тройной joint residual; общие seeds; неполнота/вариация и 4+ aggregate не дают глобальную additive-метку | Поддержанный численный профиль, смысл допуска около нуля, реальный downstream/readback | Source + малые algebra/numeric проверки, не научное доказательство глобальной структуры |

**Полного закрытия ни одного исходного ID не объявлено.** Это не утверждение, что ранее не было успешных проектных тестов: их история не переаттестована данным проходом. 50 локальных наблюдений не являются 50 PASS продукта.

## 2. Исходная задача и её разумные пределы

E02 требует связать comparator и evidence, обеспечить фактическую кратность расчётов, не выбирать калибровку за счёт пропавшего трудного момента, экономить лишь действительно одинаковые расчёты и не выводить глобальную аддитивность из одних пар. Запрещены новый Monte Carlo/SMM ради ремонта, слияние независимых реплик, один универсальный baseline для всех estimands и экспоненциальный перебор комбинаций. [E02, строки 1288–1437]

Принятая установка пользователя сохранена: LLM может предложить гипотезу, сценарий сравнения, метрики и их предметную интерпретацию. Алгоритм предпочтителен там, где точно и масштабируемо исполняет договор. Но ни содержательная убедительность предложения LLM, ни форма DTO не доказывают, что был исполнен нужный comparator, что наблюдения независимы или что строковые имена не потеряли координаты.

В данном пакете не требуется эмпирическая идентификация любого эффекта до первого условного расчёта. Достаточно честного конкретного model-conditional результата со своими допущениями; неустановленные основания нельзя объявлять установленными только ради снятия ограничения.

## 3. B19 — база сравнения и фактическое evidence

### 3.1. Первоначальные подмены устранены в проверенном механизме

`_baseline_value` отказывает при отсутствующем выбранном исходе и non-finite базе. `_effect_for_outcome` вычитает именно заданную величину. В P01 no-op `Y(A)=Y(B)=Y(AB)=100`, baseline=100 дал три нулевых эффекта; P02/P03 отдельно сохранили missing/nonfinite отказ. Переход к нулю по `get(...,0)` здесь не обнаружен. [C10-S08]

`_effective_evidence_state` использует baseline лишь при `evidence_state is None`, явно помечая `legacy_baseline_state_compat`. Пустой словарь остаётся **явно пустым evidence**, а не включает truthiness-fallback. P04 проверил оба состояния. Legacy-режим не следует удалять без рассмотрения callers; новые запросы желательно формировать с самостоятельным evidence. [C10-S07]

При явном неизменном evidence изменение baseline может не менять физическую спецификацию raw-расчёта, но обязано менять вычисленную разность и результирующее основание. P05 различил это: при исходе 107 базы 100/102 дают эффекты 7/5; физический ref при том же evidence совпал. Это не ошибка отсутствующего baseline в ключе: invocation-local cache не переносит готовый старый effect между разными запросами. В существующем тесте `test_fixed_evidence_changed_baseline_rebinds_effect_on_fresh_cas` также сравниваются разные result refs и отказ чтения первой проекции как второй. Он прочитан, не выполнен. [C10-S07, S13]

### 3.2. C10-G01 — реальный контракт comparator ещё не завершён

В `run` `comparator_refs_status` и `effect_basis_status` устанавливаются в `not_established`; арифметика названа `outcome_minus_request_baseline_state`. Наличие caller-supplied строки в `comparator_refs` не открывает положительную ветвь, а при численных траекториях сохраняется `simulation_effect_basis_not_established`. Это честное ограничение, не неисправный финальный статус. [C10-S05]

Но исходный B19 требует не только честного отказа: для выбранного контраста должна существовать проверяемая связь с той же моделью, областью и временной постановкой. Скаляр baseline для каждого outcome не представляет автоматически временную baseline-trajectory или случайный парный comparator. Нынешний ограниченный путь полезен как исследовательская арифметика, но **полная способность сформировать и исполнить нужный контраст этим не доказана**.

Минимальное продолжение: выбрать один действительно поддержанный вид сравнения и связать его основание через существующих владельцев. Для парного моделирования уже есть `paired_monte_carlo_effect` и его coupled-adapter; для уровня исхода или контрфактуала при evidence не надо насильно требовать тот же популяционный baseline-run. Нужны единицы, предметная координата, модель, данные/время и идентичность парной реплики — ровно те поля, от которых зависит этот estimand, без нового универсального registry.

Не менять `not_established` на `established` по одному наличию ref или успешному вычитанию. Локальное подтверждение арифметики не является подтверждением правильности выбранного baseline в предметной задаче.

## 4. B21 — фактические реплики и численная неопределённость

### 4.1. Реальный цикл, а не только поле replications

`_replication_seeds` образует отдельный seed на каждый requested repeat. `_run_cached_replicates` действительно вызывает callback по этому расписанию для каждого ещё не исполненного физического поднабора. Результат сохраняет физические события, completed/failed, current-budget basis при наличии владельца и список seeds; повторное представление роли не создаёт новую работу. [C10-S07; сохранённое тело C08/C09, сверенное с тем же SHA]

В P29–P34 callback исполнялся с настоящим NumPy RNG, а не только увеличивал число в отчёте. Это **не модель PolicyOS**, а различающий дешёвый producer. Для двух реплик получены:

| Атомов | Ролей результата | Физических вызовов |
|---:|---:|---:|
| 1 | 2 | 2 |
| 2 | 4 | 6 |
| 3 | 7 | 14 |
| 4 | 11 | 22 |

Для двух атомов запросы 1/2/3 повторов дали 3/6/9 вызовов. Общие seeds между ролями позволяют парное сопоставление; это не три независимых наблюдения одного мира только потому, что роли различны. Указание `n_samples=1` в одном внутреннем вызове само по себе уже не доказывает игнорирование outer replications.

`_aggregate_replicated_trajectory` и `_replication_summary_for_points` сохраняют отдельные draws, согласованные outcome keys, seeds и средние. В штатном DTO есть finite, nonnegative, count и recomputation-проверки SE. Эти DTO прочитаны, но в harness заменены контейнерами, поэтому проверка всего валидатора не заявлена. [C10-S06/S07]

P20/P21/P22: один draw даёт SE=None; два парных эффекта 1 и 3 дают mean=2, SE=1; три одинаковых **реально посчитанных** разности 2 дают sample SE=0. Последнее не является доказательством отсутствия мировой/модельной неопределённости. K_sim не становится K_world.

### 4.2. Сбой реплики не уменьшает знаменатель незаметно

P35 остановил второй draw: готового n=1 aggregate для требовавшего n=2 результата не возникло, сохранены два события работы. P36 сделал отказ позже: полностью завершённая первая роль сохранена с обоими seeds, незавершённая следующая не представлена как полная. Это полезная реализация retention и должна остаться.

Исходная конкретная причина в долгоживущей проекции всё ещё требует проверки/ремонта, описанного в C09-R02. В этом проходе она не пересчитана как новая независимая находка. Существующий SIM-03-тест `test_replication_failure_aborts_before_an_aggregate_result_exists` ожидает RuntimeError из `controller.run`; текущая обёртка перехватывает физическую ошибку и возвращает retained interruption. Это source-level рассогласование ожидания, не новый запуск pytest и не утверждение о красном полном suite. [C10-S05/S10]

### 4.3. C10-R01 — отдельный парный helper допускает нечисловой оценённый результат

**Серьёзность:** средняя, локальная численная граница. **Уверенность:** высокая в исполненных исходных телах; native end-to-end и публикация не проверены.

`paired_monte_carlo_effect` проверяет непустые seeds/metrics, уникальность seeds и наличие всех метрик в паре. Для n=1 уже исправлено прежнее SE=0: возвращается None с `standard_error_not_estimated`. Но конечность baseline, policy, их разности, mean и SE в этом helper не проверяется. Результат — dataclass без численного валидатора. [C10-S02]

| Вход парных разностей / причина | Наблюдение |
|---|---|
| `[NaN,1]` | mean=NaN, SE=NaN, `standard_error_status='estimated'` |
| `[+inf,1]` | mean=+inf, SE=NaN, `estimated` |
| Конечные endpoints policy=1e308, baseline=-1e308 | subtraction переполняется; mean=+inf при `estimated` |
| Те же невалидные значения через тело coupled paired-adapter | Поля переданы дальше без изменения статуса |

P25–P28 исполнили NumPy и действительные по логике тела helper/adapter; `_run_coupled_policy` в adapter был явно контролируемым численным ответом. Это не утверждение, что текущая настоящая DES-модель на штатном запросе уже вернула NaN. Тем более не установлен обход strict JSON/CAS или окончательного допуска: следующий слой может отвергнуть payload. Дефект — **собственный публичный результат уже заявляет оценённую ошибку, не имея пригодного численного значения**.

Соседний N5 sampling-owner уже отвергает nonfinite, что сохранено P37. Не нужно заново писать весь Monte Carlo. Проверка должна охватывать реальные значения обеих сторон, разность после вычитания и агрегаты после mean/std, с адресной причиной. Полезные конечные исходы и n=1-неоценённость сохраняются; invalid нельзя заменить 0, неизвестностью SE без причины либо удалить из знаменателя молча. Возможна общая finite-проверка у существующего numerical owner, согласованная с `_observed_series`/другими реальными reducers.

Различающая приёмка: singleton, два finite draws, настоящий sample SE=0, отсутствующий ключ, NaN/inf, overflow разности при finite endpoints и фактический adapter/readback. Проверять причину и статус, не только факт исключения.

## 5. B23 — экономия одинаковой работы без склеивания независимых повторов

Текущий cache создаётся внутри `_run_cached_replicates`. Полная физическая ref включает модель/ref, метод, план, горизонт, исходы, seeds/replications, evidence с режимом его получения, runtime refs и сами атомы. Она не включает роль individual/pair/joint: одинаковая физическая работа может законно иметь несколько ролей. [C10-S07]

P33 подтвердил общий список физических событий для pair/joint при двух атомах; P05 различил смену seed, параметра плана и evidence. Отдельные запросы выполняются заново: это **не готовый межзапусковой persistent cache**, и E02 не требует создавать его ради устранения дубля ролей. Поэтому отсутствие глобального reuse не добавлено как дефект.

В текущем тесте `test_physical_run_identity_binds_seed_and_plan_and_reexecutes_each_request` исходный NCM producer обёрнут счётчиком, не заменён числовой константой. Есть removal-профиль, убирающий seed или plan из физического ключа. Тест является полезным существующим свидетельством дизайна проверки, но не свежим результатом исполнения в этом аудите. [C10-S11]

Граница: наш canonical encoder — fixture с детерминированным JSON/SHA, а объекты плана — fixture. Он устанавливает участие выбранных полей в ключе, но не квалифицирует настоящий канон, packaging backend или immutable execution-context. Проверять реальный CAS следует существующим тестом на актуальном окружении. Переносить текущий invocation-local ключ в глобальный кэш без отдельной проверки существенного исполняемого окружения нельзя.

## 6. B25 — честная сопоставимость калибровок

### 6.1. Исходный дефект и потеря знаменателей исправлены

`summary_distance` использует заранее заданный required set, по умолчанию весь observed. Пустой явный набор и дубликаты в прямом API отвергаются. `calibrate_coupled_smm` считает присутствие каждого момента по repeats; отсутствие хотя бы одной обязательной реализации делает данного кандидата несопоставимым. Если подходящего нет, `best_params=None`, `comparison_status='no_comparable'`, `status='blocked'`, а не первый элемент grid. [C10-S01]

P09: incomplete `{easy:0}` не победил полный `{easy:0, hard:99}` при observed hard=100. P11: наличие hard только в одном из двух repeats тоже не проходит. P10 сохранил отсутствие победителя при полностью непригодном наборе.

Optional mean по доступным повторам допускается, но именно как diagnostic-only. P12 сохранил одинаковое среднее 1 с различающимися counts 1/3 и 3/3; ранжирование зависело только от обязательного required, а P13 показал инвариантность перестановки seeds. Counts, repeat denominator, comparison basis и optional status передаются через **реальный по логике SMM-adapter**, не остаются исключительно внутри helper. Это существенная уже выполненная связка. [C10-S01/S03/S14]

Инфинитный loss здесь — технический sentinel непригодности с отдельным статусом, а не наблюдаемая бесконечная ошибка политики. Не предлагать произвольный конечный штраф и не заставлять optional-метрики стать обязательными после просмотра результатов.

### 6.2. C10-R02 — SMM-adapter преждевременно уничтожает идентичность момента

**Серьёзность:** средняя для malformed/неоднозначного входа указанного API. **Уверенность:** высокая в adapter/helper контрпримере; upstream нормальный пользовательский путь и native DES не исполнены.

`CoupledSMMEstimator.pure_step` проверяет соответствие длины массива и списка имён, затем выполняет `observed = dict(zip(moment_names, observed_values, strict=True))`. Проверки уникальности до этого перехода нет. `_metric_names` также не устанавливает уникальность. Последующая защита `required_moment_names must be unique` уже видит сокращённые ключи словаря и не может восстановить утрату. [C10-S03]

P17: два именных входа `('completed_count','completed_count')` и значения `[0,100]` превратились в `{'completed_count':100}`. На контролируемом producer калибровка вернула `ready`, loss=0 и grid-point 100. P18 поменял только порядок значений: сохранилось 0, и победил другой grid-point 0. Два противоречащих наблюдаемых значения не вызвали адресной диагностики.

Здесь не утверждается, что одна метрика не может иметь несколько наблюдений или популяций. Если это разные координаты, нужны их разные полные идентичности; если это повторные наблюдения одной величины, требуется объявленная агрегация. **Последняя запись в словаре не является таким правилом.** Не запрещать все повторяющиеся display-labels во всей платформе.

Самый малый ремонт — проверить уникальность именно эффективных moment IDs и полноту пары «имя–значение» до dict/producers. Нормальный уникальный input и разрешённые defaults должны сохраниться (P16/P19). Использовать существующий контракт moment-set, не заводить новый SMM.

Приёмка: malformed duplicates отвергаются до дорогого `_run_coupled_policy`; два разных законных момента проходят; равнозначное переставление уникальных пар не меняет fit; два разных среза одноимённой метрики не теряются при наличии настоящих distinct IDs.

## 7. B26 — парное равенство больше не становится глобальной аддитивностью

`_higher_order_residuals_from_fields` использует полный joint-run и вычитает одиночные эффекты и сумму парных interaction terms. P40 для `y=x1*x2*x3` сохранил residual=1 при нулевых singles/pairs; P42 классифицировал его как non_additive. Сумма независимых эффектов дала residual=0 и разрешённый additive в проверенном finite-model профиле (P41/P43). [C10-S09]

`_paired_replication_summary` требует общий полный набор seeds по областям. Случай +1/−1 не исчезает из-за mean=0: P45 сохранил SE=1 и unsupported; отсутствие одного seed не уменьшило знаменатель (P46). Для четырёх атомов может взаимно погаситься residual третьего и четвёртого порядка. P44 воспроизвёл нулевой совокупный остаток, но current classifier оставил unsupported при `aggregate_order_three_plus=True`, а не глобально additive. Полный экспоненциальный перебор не нужен для такой честной границы.

В DTO result предусмотрено повторное вычисление interaction/residual summaries из сохранённых samples; labels связаны с `finite_checked_model_point_estimate_only`, не с эмпирической идентификацией. Старые схемы и их доступность уже разобраны в CYC-02: их статус нельзя автоматически повысить до новой sampling-гарантии. [C10-S06/S09; прежний CYC-02]

**C10-G02 — численный допуск и профиль вывода.** Ненулевость сейчас сравнивается с абсолютным 1e-12; любая наблюдаемая положительная SE делает классификацию unsupported. P48 показал, что residual 1e-13 и тот же масштабированный residual 1 получают разные метки. Это записано как предел профиля, не как доказанная неверная публикация: у результата остаются ограничения, а допуск может быть намеренной numerical policy. До предметного прочтения метки нужен смысл масштаба/единиц; для стохастического вывода можно позже применить обоснованный конкретный метод с неопределённостью. Просто убрать проверки вариации или поставить произвольный «достаточно малый SE» было бы ослаблением, не ремонтом.

## 8. Тестовая база и качество доказательства

Прочитаны адресные части `test_sim_03.py`, полный доступный `test_estimation.py` и реальные consumers. Некоторые ответы connector были усечены; это не объявлено полным census всех тестов файла/репозитория. Найдены уже существующие meaningful counters по baseline/evidence, reissued physical identity, one-draw SE, optional counts, cancellation и запрету false additive. Ряд тестов подменяет численный producer; другие вызывают исходный NCM. Эти категории различены, свежий native результат ни одной не приписан.

Фокус следующей штатной волны — не переписать весь suite. Исполнить существующие адресные tests на project Python/lock, поправить устаревшие ожидания interruption только по действующему контракту и добавить различающие R01/R02. Для B19 нужен один настоящий comparator-профиль; для B23 — прочитанный тест смены baseline/evidence и сохранённого selected-ref; для B26 — реальный consumer полной/неполной sampling-семантики. A01 CYC-02 не снят.

## 9. Что исполнено в этом выпуске

50 ограниченных наблюдений: **41 сохранённое свойство, 6 строк двух контрпримеров, 1 контрактная граница, 2 removal controls**. Все финальные наблюдения совпали с ожидаемыми. Это не знаменатель продуктовой приёмки.

Первый запуск дал 47 совпадений и три ошибки нашей интерфейсной фикстуры `_InteractionCoverage`: сохранённая транскрипция вызывала позиционный dataclass-конструктор, а новая fixture принимала лишь kwargs. Исправлен только constructor fixture, не код PolicyOS и не алгоритм residual. Первый лог/JSON и исходная fixture сохранены рядом с `harness_correction.json`; после исправления полный ограниченный запуск повторён. Эти три исходных ошибки не классифицированы как дефект продукта.

Исполнены реальные Python/NumPy, арифметика SMM/paired SE, seed/callback loop и исходные предикаты. **Не исполнены** проектные imports/DTO/WMR, настоящий registry и канон, JAX DES/NCM, CAS, HTTP, N8 и native pytest. Все вычисления — в облачном контейнере, без изменений компьютера пользователя; dependencies не устанавливались. Прямое получение raw-source из контейнера завершилось DNS-ошибкой, использованы разрешённые pinned GitHub reads и явно обозначенные транскрипции. Полный checkout на поддержанном Python 3.14 здесь не создан.

## 10. Остаток в порядке практической пользы

| Приоритет | Работа у существующего владельца | Что различает завершение |
|---|---|---|
| 1 | Finite-проверка парных входов/разностей/SE и текущего adapter | NaN/inf/overflow не получают `estimated`; реальные finite и singleton режимы сохранены |
| 2 | Уникальность moment IDs до потери информации в dict | Противоречивые duplicates отказывают до producer, уникальные парные координаты сохраняются |
| 3 | Один model-bound comparator-профиль | Фактически исполненное сравнение совпадает с предложенным estimand; ref не заменяет расчёт |
| 4 | Native приёмка existing replicas/reuse/SMM/interactions | Полный controller и сохранённый результат подтверждают ровно заявленную область |

Не требуется новый Monte Carlo, новый оптимизатор гипотез, новый глобальный кэш, новая система SMM или blanket-запрет кандидатных вычислений. Девять предыдущих отчётов и supporting evidence сохранены без новой переаттестации.

**Следующий пакет исходного порядка — SEL-01: B34/B35/B36.**

## Точные источники

**C10-S01** — [SMMResult, PairedMonteCarloResult, finite observations, required moments, SMM loss and denominators](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/coupling/estimation.py#L1-L390)

**C10-S02** — [paired_monte_carlo_effect and _average_summaries, actual end of file](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/coupling/estimation.py#L390-L530)

**C10-S03** — [CoupledSMMEstimator params → observed dict → SMM → output](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/simulation/coupled.py#L332-L479)

**C10-S04** — [SMM output and CoupledPairedMonteCarloEstimator caller](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/simulation/coupled.py#L400-L690)

**C10-S05** — [run: effect basis not established, replication and physical-work diagnostics, numerical consumers](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py#L1760-L2175)

**C10-S06** — [sampling error finite guards and recomputation; raw replication summaries](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py#L540-L710)

**C10-S07** — [effective evidence, physical identity, actual replicate aggregation](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py#L885-L1035)

**C10-S08** — [explicit baseline; seed-paired derived sampling](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py#L4265-L4350)

**C10-S09** — [pair effects, higher residuals, classification and bounded labels](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py#L4350-L4880)

**C10-S10** — [selected existing tests: required moments, replicas, failure expectations, evidence distinction (response truncated)](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_sim_03.py#L1-L600)

**C10-S11** — [selected tests: physical identity, triple interaction, cancellation and order (response truncated)](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_sim_03.py#L400-L850)

**C10-S12** — [selected tests: four-atom cancellation, missing comparator, physical reuse (response truncated)](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_sim_03.py#L820-L1400)

**C10-S13** — [baseline change with fixed evidence, projected artifact/readback checks, actual file end](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_sim_03.py#L1160-L1650)

**C10-S14** — [required/optional SMM moment denominators and actual producer contracts](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/coupling/test_estimation.py#L1-L700)

**C10-S15** — [repository boundaries, evidence rules, supported runtime](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/AGENTS.md#L1-L130)
