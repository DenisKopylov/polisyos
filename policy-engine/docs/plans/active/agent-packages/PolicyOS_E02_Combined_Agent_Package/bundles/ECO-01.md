# ECO-01 — Два economic профиля и предметный baseline objective

**E02 · окно CP4 · локальная проверка N · начальный статус planned.**

**B:** Нет; пакет миграции LA. **LA:** LA-004 (M), LA-035 (R).

**Предшественники:** [FRY-03](../bundles/FRY-03.md). **Совместная очередь:** LANE-04.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

Составить конечную таблицу GlobalState/PatchMap и EconomicState: units, timestep, tax base, RNG, balances. Сохранить неэквивалентные модели под явными профилями, выделять только доказанно общий primitive. Перенести старый normalized-income/budget policy_loss_fn в economic baseline owner без смены формулы и держать unsupported substitutions явными.

**Различающие тесты и сохраняемое поведение.** Threshold employment не выдаётся за transition employment; wealth tax не за income tax. Старый loss positive/scaled/zero/negative/breach/nonfinite и JIT/grad сохраняет свой определённый профиль. Constant -1 в positive regime документируется, не исправляется скрыто новым welfare objective. Native guard остаётся настоящим.

**Не считать исправлением.** Не считать более богатый plugin готовой заменой, не сливать по class name и не вводить новый objective/version без отдельного решения.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Границы участия в LA

**LA-004:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **ECO-01**; необходимые пакеты: ECO-01.

**LA-035:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **ECO-01**; необходимые пакеты: ECO-01.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/src/polisyos/foundry/execute/mechanisms/fiscal.py
policy-engine/src/polisyos/foundry/execute/mechanisms/labor.py
policy-engine/src/polisyos/foundry/methods/_internal/loss.py
policy-engine/src/polisyos/foundry/methods/loss.py
policy-engine/src/polisyos/foundry/plugins/economics/baselines.py
policy-engine/src/polisyos/foundry/plugins/economics/mechanisms.py
policy-engine/src/polisyos/foundry/plugins/economics/objectives.py
```

**Читать как соседние контракты:**

```text
policy-engine/src/polisyos/foundry/runtime/numeric.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_eco_01.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** FRY-03. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Path-map записи:** MOVE-04, MOVE-20. После принятого move работать по actual target/commit, не по историческому имени файла. Source и target move одновременно зарезервированы владельцем.

**Ресурс:** N/C — I1 broker drains L and admits one exclusive native/numerical/build or checkpoint job using the full seven-unit budget; no other resource-bearing job runs concurrently. Общий fan-out — 15 direct leaf workers; чтение/код/review продолжаются без permit. Immutable argv/cwd/worktree/SHA/selectors/timeout/output root and named resources are fixed at admission; builds/installs через I1.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное решение LA-004

Источник LA_r09, строки 167–197; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-004 -->
## LA-004. Две экономические реализации: согласовать, но не подменять

**Слияние / разделение ответственности**

**Статус.** Пересечение предмета подтверждено; эквивалентность опровергается кодом.

**Точная область:**

`src/polisyos/foundry/mechanisms/fiscal.py`

`src/polisyos/foundry/mechanisms/labor.py`

`src/polisyos/foundry/plugins/economics/mechanisms.py`

**Что установлено и почему это legacy-кандидат.** Одинаковый класс LaborMarketMechanism означает разные модели: threshold-пересэмплирование с фирмами против find/separation transitions, wage shocks и EconomicState. Налоговая реализация plugin прогрессивная и меняет wealth; IncomeTax использует reported_income, меняет income и government.balance. Более богатая модель не является drop-in replacement.

**Что сохранить.** Обе явно определённые модельные гипотезы, полезные численные операции и проверки законов сохранения. Уникальные fields и state contracts должны сохраниться до доказанной миграции.

**Куда перенести / с чем объединить.** Общий доменный владелец может оставаться foundry/plugins/economics; shared pure kernels размещать там или в нижнем execution-слое только после выявления действительно одинаковой операции. Два adapter-слоя сохраняют PatchMap и EconomicState. Имена моделей/профилей следует развести.

**Порядок миграции.** Сначала таблица соответствия состояния, единиц, временного шага, tax base, RNG и учета бюджета. Извлекать общий алгоритм лишь там, где контракты совпали. Остальные отличия оформить версиями модели. Старый профиль выводить после миграции сценариев, а не после механического переименования импортов.

**Приёмочная проверка.** Сравнить специально заданные одинаковые regimes; отдельно проверить, что различающиеся regimes не стали считаться эквивалентными. Проверить бухгалтерские равенства, использование seed и сохранение наблюдаемых выходов.

**Приоритет.** Средняя/высокая цена; полезнее локального объединения имён.

**Граница вывода.** Не доказано, что plugin лучше откалиброван или подходит всем пользователям базового ABI. Полная миграция двух исполнителей в этом проходе не проектировалась.

**Основания:** E04, E05, E07.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-004 -->

## Обязательное позднее уточнение LA-004

<!-- SOURCE_BEGIN AM:AM02 -->
## LA-004 — уточнение r02

Уточнение: наличие более богатого economics-plugin не доказывает работающее обучение его high-level API. LA-023 показывает, что прежний train собирает rollouts без обновления actor. Это не отменяет полезность самих экономических переходов и не делает объединение с базовыми PatchMap kernels автоматически корректным. [E53, E54, E55]

<!-- SOURCE_END AM:AM02 -->

## Исходное решение LA-035

Источник LA_r09, строки 2066–2102; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-035 -->
## LA-035. policy_loss_fn: ранний экономический baseline у общего method-владельца

**R — перемещение по смысловой роли с отдельной идентичностью objective**

**Точная область:**

`src/polisyos/foundry/methods/_internal/loss.py`

`src/polisyos/foundry/methods/loss.py`

**Статус.** Конкретная экономическая функция и её legacy facade подтверждены; найден consumer-test. Готовая эквивалентная замена современным economic objective не установлена.

**Что установлено.** За общим именем `policy_loss_fn` находится критерий по `GlobalState.agents.income` и `government_balance`, с default `min_balance=-1000` и коэффициентом штрафа `10`. Это не функция потерь arbitrary method и не общий интерфейс политического предпочтения. Физическое помещение в `methods/_internal` сохранило старую предметную обязанность. Старый публичный `methods/loss.py` только открывает её через reexport-helper. [E106–E109]

Characterization уточняет смысл самого критерия. До бюджетного штрафа он равен `-mean(income) / max(mean(abs(income)), 1)`. При неотрицательных доходах и среднем не меньше единицы это `-1`, независимо от абсолютного уровня дохода. На `[1000,2000,3000]`, десятикратном наборе и `[2,2,2]` получен тот же результат; локальный градиент в первом случае нулевой в пределах float32 tolerance. Это **математическое свойство нормализации**, не доказательство, что любой пользователь хотел максимизировать ненормированный доход. Но оно не позволяет безоговорочно называть функцию общим доходным optimization objective.

Бюджетный штраф и invalid-input checks действительно работают в проверенных локальных случаях: при balance `-2000` и min `-1000` итог `9`, при NaN-входе — infinity. Существующий repository-test проверяет finiteness и non-finite case, не сохранение ранжирования положительных доходов.

**Что сохранить.** Определённый baseline-критерий, его sign/scale regimes, бюджетный штраф, numeric guardrails, поддержанные callers. Сохранить тесты численной защиты: переезд предметного loss не означает удаление общего `finite_loss_or_inf` или его публичного runtime facade.

**Куда перенести / с чем объединить.** Семантический адрес — действующий economic objective-владелец `foundry/plugins/economics`. Предлагаемый `baselines.py` с явно названным GlobalState-profile — новый файл, не существующая готовая замена. При малом объёме допустим отдельный явно типизированный baseline в существующем `objectives.py`, если это не смешивает ABI и не утяжеляет импорт. Не переносить функцию в глобальный Common.

Прочитанные `GDPObjective`, `SocialWelfareObjective`, `UtilitarianWelfare` и другие работают по **EconomicState** и выражают другие критерии. Они не drop-in successor старого normalized-income/budget loss. LA-004 сохраняет силу: соседство экономических моделей не доказывает их равенство. [E110]

**Порядок миграции.** Сначала назвать и зафиксировать текущую формулу как baseline, затем найти все source/config/FQN consumers и перенести тело без изменения численного поведения. Для подтверждённого требования максимизировать доход ввести отдельный objective/version; исправление ранжирования не маскировать под переименование файла. Если полный census покажет, что функция нужна исключительно numeric fixtures, поместить соответствующий пример у тестов или benchmark-владельца, сохранив проверяемую numeric обязанность. Сам факт двух тестов не разрешает уже сейчас удалить функцию.

**Фактическая проверка.** r04-P18–P22 исполняют точный loss-blob с настоящим JAX 0.9.0.1; state — простая fixture с нужными полями, `finite_loss_or_inf` — явно обозначенный identity helper. Поэтому проверены собственная формула и invalid-ветка loss, **не native GlobalState, JIT workflow или реальная реализация numeric guardrail**. Нативный autodiff использован только для выбранного локального input.

**Приёмка.** Положительные/нулевые/отрицательные и смешанные доходы, размер популяции, scales, min_balance, breach, NaN/Inf; native State и guardrail, JIT/grad там, где это обещано. Различать equivalent relocation и новый критерий выбора политик. Проверить import side effects выбранного economic package.

**Приоритет.** Умеренная цена, высокая семантическая ясность. Уточнение профиля и устранение misleading generic address можно отделить от содержательной переработки цели.

**Граница вывода.** Не установлен production optimizer, фактически использующий этот loss, и не доказана потеря дохода в реальном решении. Полный caller census не выполнялся. Нормализация не удаляется лишь потому, что найден более богатый objective API.

**Основания:** E106–E110. Локальные проверки: r04-P18–P22.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-035 -->

## Защищённые различения исходного legacy-аудита

LK — активный идентификатор защиты; внутри сохранены исходные K-заголовки.

<!-- SOURCE_BEGIN LK:LK04 -->
## K04. fabric/numerics/finite.py

Малый модуль выполняет реальные boundary-checks: finite, non-negative и probability. Небольшая чистая функция может быть правильным законченным компонентом.

**Решение:** Оставить, пока не найден семантически эквивалентный shared helper с теми же error/clamp/typing semantics. Из одного имени generic utility вывод о дублировании не следует. [E34]

<!-- SOURCE_END LK:LK04 -->

<!-- SOURCE_BEGIN LK:LK06 -->
## K06. foundry/_registry.py и catalog/mechanism/runtime.py

Registry уже является view над MethodRegistry, а runtime.py связывает method ABI с state-transition implementation. Наличие adapter и kernel оправдано разными ролями.

**Решение:** Не заменять view вторым реестром. Дороговизну повторного построения descriptor-view, если она проявится, исследовать отдельно от retirement. [E01, E06]

<!-- PAGEBREAK -->
<!-- SOURCE_END LK:LK06 -->

<!-- SOURCE_BEGIN LK:LK08 -->
## K08. DomainPlugin не равен FoundryMethodPlugin

State factory, rewards, objectives, lifecycle и observations доменного plugin не покрываются одним методом pure_step. Общая discovery-инфраструктура полезна, но смена entry-point group без bridge меняет ABI. Поддержанные runtime registries могут оставаться отдельными lookup-структурами. [E49, E50, E51, E52, E66]

<!-- SOURCE_END LK:LK08 -->

