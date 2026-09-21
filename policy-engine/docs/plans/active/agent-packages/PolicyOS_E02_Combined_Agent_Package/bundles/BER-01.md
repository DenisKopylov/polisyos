# BER-01 — BERL: schema profile и действительная identity объяснителя

**E02 · окно CP3 · локальная проверка N · начальный статус planned.**

**B:** Нет; пакет миграции LA. **LA:** LA-034 (M), LA-036 (M).

**Предшественники:** Нет. **Совместная очередь:** LANE-11.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

Первый commit согласует construction-input/persisted-output profiles, version policy и воспроизводимую generated JSON-schema вместо независимого skeleton. Второй различает requested method и executed implementation/fallback, сохраняя исторические IDs. Совместимые aliases одного effective request используют один raw calculation; неподдержанный conditional/tree режим получает существующий diagnostic либо явный fallback. Disagreement не считает aliases независимыми методами.

**Различающие тесты и сохраняемое поведение.** Full bundle, empty nested objects, extra fields, version9.9.9 и omitted defaults по обоим объявленным profiles; content drift test, не только $id. На двухпризнаковой модели: два alias, changed background/model/parameters, unsupported request и explicit fallback; число реальных model calls и effective identity. Feature-count/empty-background guards сохранены, source raw data не меняются.

**Не считать исправлением.** Не считать generated schema полным semantic validator, не менять confidence-budget law из дедупликации имен и не обещать появившийся TreeSHAP от новой метки. Не удалять BERL kernels/benchmarks.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Границы участия в LA

**LA-034:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **BER-01**; необходимые пакеты: BER-01.

**LA-036:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **BER-01**; необходимые пакеты: BER-01.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/src/polisyos/berl/adapters/protocol.py
policy-engine/src/polisyos/berl/adapters/shap_kernel.py
policy-engine/src/polisyos/berl/adapters/shap_tree.py
policy-engine/src/polisyos/berl/contracts/explanation_bundle.py
policy-engine/src/polisyos/berl/contracts/explanation_bundle.schema.json
policy-engine/src/polisyos/berl/contracts/schema.py
policy-engine/src/polisyos/berl/service.py
```

**Читать как соседние контракты:**

```text
policy-engine/src/polisyos/berl/adapters/_utils.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_ber_01.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** Нет по статической карте. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Ресурс:** N/C — I1 broker drains L and admits one exclusive native/numerical/build or checkpoint job using the full seven-unit budget; no other resource-bearing job runs concurrently. Общий fan-out — 15 direct leaf workers; чтение/код/review продолжаются без permit. Immutable argv/cwd/worktree/SHA/selectors/timeout/output root and named resources are fixed at admission; builds/installs через I1.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное решение LA-034

Источник LA_r09, строки 2029–2065; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-034 -->
## LA-034. BERL ExplanationBundle: схема-каркас и генерируемый контракт разошлись

**M — объединение формата при сохранении различий input и persisted output**

**Точная область:**

`src/polisyos/berl/contracts/explanation_bundle.schema.json`

`src/polisyos/berl/contracts/explanation_bundle.py`

`src/polisyos/berl/contracts/schema.py`

**Статус.** Две разные области принятия данных при одной schema identity воспроизведены на полных исходниках. Фактический внешний consumer сохранённого JSON пока не установлен.

**Что установлено.** Сохранённая JSON-схема задаёт верхние ключи, но `model`, `prediction`, `feature_context`, `assumptions`, `audit` описывает только как `object`. Действующие Pydantic-модели требуют содержательные поля и запрещают undeclared fields во вложенных объектах. Рядом уже есть `generated_explanation_bundle_schema()` и writer; генератор назначает тот же `$id` для версии `1.0.0`. Существующий тест проверяет наличие схемы и ID, но не сравнивает её с сохранённым JSON. [E102–E105]

На локальном корпусе получены **обе направленности расхождения**. Каркас принимает payload с пустыми model/prediction/assumptions/audit, который отклоняют DTO и generated schema. Но сохранённая схема требует `schema_version == "1.0.0"`, тогда как DTO и generated schema принимают `"9.9.9"`, соответствующую общему шаблону номера. Также DTO допускает отсутствие полей с defaults, которые каркас делает обязательными. Поэтому «заменить файл результатом генератора» без решения об input/output profile не является достаточной миграцией.

**Что сохранить.** Строгие вложенные DTO, stable metadata, историческую версию опубликованного формата, удобство загрузки с defaults там, где это действительно поддержанный input-контракт. Содержательная проверка reliability/display policy остаётся отдельной: успешная schema validation не означает достаточный infidelity bound, установленную применимость или разрешение analyst display.

**Куда перенести / с чем объединить.** У нынешнего BERL contracts-владельца оставить одну исходную модель структуры и существующую механику генерации. Сохранённый JSON должен стать воспроизводимой проекцией **явно выбранного профиля**, а не независимо редактируемым каркасом. Различить при необходимости permissive construction input и полную сериализованную запись. Для wire-профиля отдельно определить поддерживаемую версию; новый scope/ID нужен, если это разные контракты, а не две реализации одной версии.

**Порядок миграции.** Зафиксировать двухсторонний corpus: корректный полный bundle, пустые вложенные объекты, nested extra, неизвестная версия и отсутствие defaults. Установить фактических читателей схемы — resource loader, packaging, generated docs/API tooling и внешних валидаторов. Затем согласовать версионную политику и генерировать согласованную проекцию существующим helper. Добавить drift-test **содержимого**, не только `$id`. Историческую схему при необходимости оставить version-pinned reader; не переписывать старые артефакты и не считать их автоматически прошедшими новый validator.

Если конечный census подтвердит, что JSON вообще не является поддержанной resource-поверхностью, его можно удалить после переноса навигации на генератор. Пока это условная ветвь M, а не новый безусловный D-кандидат.

**Фактическая проверка.** r04-P06–P12: полный DTO и helper с настоящим Pydantic 2.13.4, Draft 2020-12 validator и format checker, повторная запись во временный файл. Структурно корректный контроль проходит все три проверки; skeleton и nested extra принимает только каркас; неизвестную версию и default omission — только DTO/generated. Writer даёт одинаковые bytes при двух локальных вызовах. Ни product validation gate, ни действующий HTTP endpoint не запускались.

**Приёмка.** Детерминированная генерация на закреплённой версии tooling, выбранный schema mode, equal-content check, старые fixtures, явный отказ неизвестной версии в том профиле, где он обязателен. Проверять отдельно структурный parse и содержательную eligibility/display validation.

**Приоритет.** Высокая ясность расхождения; умеренная цена при найденных consumers. Переиспользовать существующий генератор, не создавать ещё одну schema-библиотеку.

**Граница вывода.** Адресный поиск точного filename не вернул consumers; это не доказывает отсутствие загрузки через package resources или внешнее чтение. Не показано, что существующий Runtime endpoint проверяет вход именно слабым JSON-файлом. Вывод касается расхождения поддерживаемых артефактов, не доказанного обхода допуска.

**Основания:** E102–E105. Локальные проверки: r04-P06–P12.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-034 -->

## Исходное решение LA-036

Источник LA_r09, строки 2103–2145; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-036 -->
## LA-036. BERL: разные method IDs всё ещё обозначают один fallback-вычислитель

**M — консолидация идентичности реализации и явная миграция неподдержанных режимов**

**Точная область:**

`src/polisyos/berl/service.py#default_adapters`

`src/polisyos/berl/service.py#ExplanationOrchestrator.explain/_build_disagreement`

`src/polisyos/berl/adapters/shap_kernel.py`

`src/polisyos/berl/adapters/shap_tree.py`

**Статус.** Тождество численного пути и несовпадение некоторых имён с исполнением подтверждены кодом и точными локальными kernels. Полный orchestrator и его confidence gate в r04 не исполнены.

**Что установлено.** Built-in registry создаёт `KernelSHAPAdapter` для `kernel_shap`, `kernel_shap_conditional` и `kernel_shap_marginal`, меняя только `method_id`. `TreeSHAPAdapter` наследует тот же класс без override вычисления; меняется опять `method_id`. Полный kernel перебирает коалиции, подставляет выбранные значения `x` в каждую background row и усредняет результат. `feature_dependence_policy` переносится в metadata, но не переключает этот algorithm; helper чтения background тоже не создаёт conditional/marginal ветвей. [E111–E115]

У `TreeSHAPAdapter` есть честное docstring-предупреждение: это empirical-enumeration fallback, не path-dependent TreeSHAP exactness. Это важное ограничение вывода. Проблема не в отсутствии уникального tree-кода как таковом, а в том, что действующий service продолжает выдавать отдельные method IDs в `MethodExplanation` и передаёт полученные vectors в cross-method comparison без проверки общей реализации. Число API-имён не равно числу разных вычислительных свидетельств.

**Область проявления.** Штатный `ExplanationRequest.methods` содержит `kernel_shap`, `lime`, `ale_local_bin`; он **не включает все четыре alias одновременно**. Повтор вычисления возникает в явном multi-method запросе с такими именами. На локальном двухпризнаковом input четыре class configurations вернули одинаковые attribution values и одинаковые последовательности обращений к модели: восемь вызовов каждый, 32 суммарно. Это не замер production-нагрузки и не доказательство независимости или зависимостей любых произвольных объяснителей.

**Что сохранить.** Рабочий exact empirical kernel, background semantics, feature-count guard, воспроизводимость, реальные assumption declarations, и доступность честно обозначенного fallback. Сохранить historical requested IDs, если они встречаются в артефактах; не переписывать их задним числом в якобы выполненный другой estimator.

**Куда перенести / с чем объединить.** Один фактический backend у текущего BERL adapters-владельца; registry должен различать **requested method**, **executed implementation/profile** и fallback/unsupported disposition. Эти поля — предлагаемое уточнение существующего explanation contract, не уже реализованный интерфейс. Обычный alias допустим, когда сохраняет тот же контракт. Название, обещающее другой conditional или tree-specific режим, не должно молча менять только подпись результата.

Для неподдержанного режима уже существует `UnavailableAdapter` / `AdapterUnavailableError` и service-путь diagnostic result. Это материал для честного отказа, **не готовая реализация conditional или tree backend**. Новый estimator нельзя считать появившимся от изменения registry label. [E113, E115]

**Порядок миграции.** Зафиксировать текущие request → implementation bindings. Определить, какие имена являются совместимыми aliases одного profile, а какие требуют иной математики. Первые разрешать в одну фактическую идентичность; вторые — явно отказывать или исполнять согласованный fallback с раскрытием его реальной роли. Для repeated effective request вычислять общий raw result один раз только при совпадении модели, input, background, parameters и обязательств adapter; не вводить общий cache по одному `method_id`.

Отдельно обновить disagreement presentation: совпадение aliases может быть проверкой воспроизводимости/маршрутизации, но не evidence разнообразия реализованных методов. Не менять автоматически confidence-budget law: дедупликация вычислений и число защищаемых статистических claims — разные вопросы, требующие проверки действующего bound/validation owner.

**Фактическая проверка.** r04-P13–P17 исполняют четыре точных BERL-файла: protocol, `_utils`, kernel и tree wrapper. Реальны весь `explain` и arithmetic. Импортируемая, но не используемая здесь `additive_reconstruct_delta` заменена trap, вызовов ноль. Изменение одной policy-label не изменяет attributions, изменение реального background изменяет их. Guards для 11 признаков и пустого background сохранены. Dataset и scalar model — явные диагностические fixtures.

**Приёмка.** Requested/effective method identity; один и два совместимых alias; unsupported conditional/tree requests; explicit fallback; зависимый background; влияющие parameters; одинаковые и разные model snapshots; старые records и UI reports. Сравнить исходные bytes там, где relocation обещает их неизменность. До схемного расширения согласовать LA-034, но не приписывать generated schema способность проверить истинность algorithm label.

**Приоритет.** Высокая семантическая отдача. Первый небольшой шаг — явный execution profile и запрет ложного различения; подключение новых алгоритмов не обязательно для снятия misleading labels.

**Граница вывода.** Не утверждается, что любой запрос BERL повторяет вычисления или что текущая система автоматически делает институциональный вывод из alias-agreement. Не проверены сторонние переданные adapters: пользовательский mapping может содержать действительно другие реализации. Не доказана полная численная/статистическая корректность kernel; проверен конкретный механизм консолидации.

**Основания:** E111–E115. Локальные проверки: r04-P13–P17.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-036 -->

## Защищённые различения исходного legacy-аудита

LK — активный идентификатор защиты; внутри сохранены исходные K-заголовки.

<!-- SOURCE_BEGIN LK:LK13 -->
## K13. BERL — не целиком legacy; раскрытый fallback может быть полезен

README закрепляет роль действующей Scientist support infrastructure. Полностью прочитанные kernels выполняют реальное вычисление, а controls показывают зависимость результата от входного background и действующие отказы. Synthetic eligibility rows прямо названы fixtures для smoke/release tests; прочитанный release-report formatter лишь выводит переданные ограничения validation. Это не даёт основания удалить BERL, его benchmarks или весь adapter layer. LA-034 и LA-036 относятся к точным format/identity поверхностям, а не к бесполезности explainability-функции. Сам факт существования narrow fallback допустим; он должен оставаться различимым с запрошенным специализированным методом. [E111–E115, E123, E134–E135]

<!-- SOURCE_END LK:LK13 -->

