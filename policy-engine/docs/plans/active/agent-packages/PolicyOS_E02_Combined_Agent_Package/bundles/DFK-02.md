# DFK-02 — Source catalog: одно определение и единая seed-selection policy

**E02 · окно CP2 · локальная проверка L · начальный статус planned.**

**B:** Нет; пакет миграции LA. **LA:** LA-028 (M).

**Предшественники:** Нет. **Совместная очередь:** LANE-08.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

Зафиксировать ordered catalog/filter/asset corpus и разрешить disabled/missing seed policy до замены источника деклараций. YAML с полной записью становится исходным versioned registry; Python view вычисляется/генерируется из него без ручной копии. None/default и явный empty различны. Сохранить profiles/waves/agency/format/keywords filters, IDs и contracts; общая selection не делает lossy ModuleSpec полной execution policy.

**Различающие тесты и сохраняемое поведение.** Enabled seed, disabled mandatory seed, missing/cyclic dependencies, empty tuple против None, custom registry, порядок и 35 штатных записей существующего equality-test. Нельзя молча включить disabled или запустить exec без обязательного seed. Contract-only import не выполняет тяжёлый I/O; реальные Fabric consumers читают ту же разрешённую проекцию.

**Не считать исправлением.** Не объявлять автоматически верной любую из двух прежних disabled-ветвей. Не удалять connectors или переносить весь catalog в Fabric. Equality тест сохранить для generated projection.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Границы участия в LA

**LA-028:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **DFK-02**; необходимые пакеты: DFK-02.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/src/polisyos/data_forge/domains/catalog/registry.py
policy-engine/src/polisyos/data_forge/domains/catalog/selection.py
policy-engine/src/polisyos/data_forge/domains/catalog/source_modules.py
policy-engine/src/polisyos/data_forge/domains/catalog/source_registry.yaml
policy-engine/src/polisyos/data_forge/domains/catalog/sources/__init__.py
policy-engine/src/polisyos/data_forge/domains/catalog/sources/core.py
```

**Читать как соседние контракты:**

```text
policy-engine/src/polisyos/fabric/retrieval/service.py
policy-engine/tests/unit/data_forge/test_phase3_catalog_completion.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_dfk_02.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** Нет по статической карте. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Ресурс:** L — максимум два таких jobs по всем worktree. Общий агентный fan-out остаётся12–16; ожидание test slot не останавливает написание/review. Для загрузки зависимостей и широких builds обращаться к I1, не запускать их самостоятельно.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное решение LA-028

Источник LA_r09, строки 1466–1517; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-028 -->
## LA-028. Каталог источников: миграционное зеркало стало второй поддерживаемой истиной

**Объединение / разделение ответственности**

**Точная область:**

`src/polisyos/data_forge/domains/catalog/source_registry.yaml`

`src/polisyos/data_forge/domains/catalog/source_modules.py`

`src/polisyos/data_forge/domains/catalog/registry.py`

`src/polisyos/data_forge/domains/catalog/sources/`



**Статус.** Две декларативные поверхности и расходящиеся функции выбора подтверждены; рассогласование всех штатных записей не утверждается.



**Что установлено и почему это legacy-кандидат.** YAML-реестр и статические Python-константы описывают одинаковый упорядоченный набор источников. source_modules создаёт asset/stage contracts, registry содержит более полные фильтры и переводит запись в сокращённый ModuleSpec. Действующий тест сравнивает 35 штатных записей по to_module_spec — это полезная защита, а не её отсутствие. Но seed-замыкание поддерживается дважды: module-path индексирует отключённые источники тоже, registry-path — только включённые. Для enabled exec с disabled seed первый возвращает оба, второй — только exec. Явная пустая tuple modules дополнительно заменяется default-каталогом через or. Это уже не два представления одной разрешённой политики выбора.



**Что сохранить.** Идентификаторы и порядок источников, профильные правила, asset keys, фильтры агентств/форматов/ключевых слов, зависимости seed и лёгкое декларативное представление. Не удалять реальные Fabric connectors; metadata источника и исполняемый connector — разные объекты.



**Куда перенести / с чем объединить.** Один версионированный исходный реестр под нынешним catalog-владельцем; существующий YAML содержит наиболее полную запись. Статическое представление должно вычисляться или генерироваться из него с проверкой эквивалентности. Общий выбор/замыкание остаётся рядом в source_modules либо отдельном selection.py только при оправданном размере. Не сводить богатую execution policy к lossy ModuleSpec.



**Порядок миграции.** Сначала зафиксировать ordered golden corpus и единую политику disabled/missing seed. Не объявлять автоматически правильным один из нынешних результатов: возвращать отключённый seed молча нельзя, но exec без обязательного seed тоже требует объяснения. Далее убрать ручное редактирование копии и дублирующий selection. Разорвать импортный цикл contracts→sources→contracts при необходимости узким выделением DTO, не создавая нового верхнего пакета. Сохранить отсутствие тяжёлого I/O при contract-only импорте.



**Фактическая проверка и приёмка.** P04: enabled seed даёт одинаковые результаты. P05: disabled seed различает два маршрута. P06: пустой явный список отличается от None/default. P07: локальная иллюстрация общей проверки выдаёт dependency_disabled, сохраняет допустимый случай и пустой запрос. Это не внедрённый алгоритм и не полный native registry test. Приёмка дополнительно охватывает custom registry, циклы, отсутствующие seed, waves, профили и сохранность фильтров.



**Приоритет.** Высокая отдача при средней цене: убирается двойная поддержка определения работы, не только несколько строк.



**Граница вывода.** Полные 35 Python-деклараций и весь YAML в этом проходе не перечитаны. Существующий equality-test прочитан, не запущен. Число 35 относится к его проверяемому корпусу; фактический production-трафик не измерен.



**Основания:** E73, E74, E75, E76, E77, E78, E79. Локальные проверки: P04, P05, P06, P07.


<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-028 -->

## Защищённые различения исходного legacy-аудита

LK — активный идентификатор защиты; внутри сохранены исходные K-заголовки.

<!-- SOURCE_BEGIN LK:LK19 -->
## K19. Catalog ingestion уже переиспользует Fabric — не всякая дополнительная стадия является вторым acquisition

В начале `core_sources/api.py` используются Fabric `AsyncFetchLease`, `FetchRequest`, connection/source-execution profiles и специализированные connectors. Это поддерживает разделение между исполнителем приобретения и batch orchestration/преобразованием/записью данных. **LA-038 не предполагает удаления Fabric connectors или переноса всей batch orchestration в Fabric.** [E137]

У source-specific `harvester.py` в r05 прочитано только начало с imports и приоритетами; его сетевые функции не сравнивались целиком с Fabric. Полная equivalence или наличие вторых HTTP-реализаций по каждой source family **не установлены**. Эта часть следующей очереди остаётся открытой, а не подменяется новой общей карточкой «все harvesters — legacy».

<!-- SOURCE_END LK:LK19 -->

<!-- SOURCE_BEGIN LK:LK20 -->
## K20. Content identity и контрольная сумма не являются сами по себе разрешением на reuse или closeout

Generation basis действительно строится из переданных bytes и версии правила; локально проверены current, changed content/model/rule, malformed digest и missing record. Но он не может самостоятельно установить полноту перечня, который передал caller. Generic manifest checker, в свою очередь, сохраняет поддержку пустого expected hash и не удостоверяет обязательность состава. Эти модули — полезные узкие primitives, **не obsolete helpers и не готовая полная replacement policy**. [E144, E146; r05-P34–P42]

В LA-039/LA-040/LA-041 их объединение должно сохранить различие: истинность hash, текущая принадлежность к поколению, эквивалентность запроса, целостность выходов и допустимость использования — разные утверждения. Ни одно из них не заменяется названием `current`, одним файлом manifest или удачным return code.

<!-- SOURCE_END LK:LK20 -->

