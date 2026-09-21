# PLG-01 — DomainPlugin: общая discovery-механика без смены ABI

**E02 · окно CP4 · локальная проверка L · начальный статус planned.**

**B:** Нет; пакет миграции LA. **LA:** LA-022 (M).

**Предшественники:** Нет. **Совместная очередь:** LANE-04.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

Использовать existing Core entry-point/file loading primitives в доменном adapter. Сохранить DomainPlugin state/reward/objectives/lifecycle и group polisyos.plugins; prefix scanning выводить после явных declarations. Один loader path собирает errors/duplicates/order без импорта всего окружения.

**Различающие тесты и сохраняемое поведение.** Builtin/dev/entrypoint plugins, dependency/load/unload, duplicate IDs, import error и deterministic ordering. Выбранный economics plugin создаётся через прежний ABI; FoundryMethodPlugin не подменяется DomainPlugin. Малые временные plugin files вместо установки всех packages.

**Не считать исправлением.** Не переименовывать group в foundry_methods, не утверждать готовый Components bridge и не переписывать все registries.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Границы участия в LA

**LA-022:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **PLG-01**; необходимые пакеты: PLG-01.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/src/polisyos/foundry/plugins/core.py
policy-engine/src/polisyos/foundry/plugins/discovery.py
```

**Читать как соседние контракты:**

```text
policy-engine/src/polisyos/core/components/bootstrap.py
policy-engine/src/polisyos/core/components/discovery.py
policy-engine/src/polisyos/core/discovery/base.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_plg_01.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** Нет по статической карте. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Ресурс:** L — I1 broker admits requests against a shared seven-unit L-equivalent budget and at most seven resource-bearing process groups across all worktrees; resource cost is micro=0.5, standard=1, measured medium=2–3. Permit is released after process-group cleanup and receipt; review does not hold it. Общий fan-out — 15 direct leaf workers; чтение/код/review продолжаются без compute permit. Named shared resources and immutable request fields remain enforced; builds/installs через I1.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное решение LA-022

Источник LA_r09, строки 1022–1051; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-022 -->
## LA-022. Legacy DomainPlugin discovery дублирует общую инфраструктуру загрузки

Слияние / разделение ответственности

**Статус.** Старая discovery-реализация подтверждена; DomainPlugin сохраняет самостоятельный контракт.

**Точная область:**

`src/polisyos/foundry/plugins/discovery.py`

`src/polisyos/foundry/plugins/core.py`

**Что установлено и почему это legacy.** Загрузчик явно назван legacy domain-plugin layer. Он независимо обходит pkg_resources entry points, все установленные distribution по prefix и каталоги с plugin.py, затем регистрирует объекты в PluginRegistry. Между тем Core уже имеет list_entry_points, load_module_from_file и сбор items/errors, а components — индекс и отчёт источников. Дублируется инфраструктура обнаружения и обработки ошибок, но не обязательно сам смысл доменного registry.

**Что сохранить.** DomainPlugin предоставляет initial state, механизмы, reward, objectives, observation builder и lifecycle hooks. Это не FoundryMethodPlugin. Нельзя переименовать polisyos.plugins в polisyos.foundry_methods и ожидать эквивалентного запуска; старый include_legacy_group в components означает polisyos.components, не polisyos.plugins.

**Куда перенести / с чем объединить.** Самый дешёвый шаг — использовать существующие core/discovery/base.py primitives из доменного адаптера. Для последующей интеграции с core/components нужен явный bridge и поддержанный contract/kind; готовый drop-in bridge не установлен. DomainPlugin, его модели и runtime lookup пока остаются у Foundry. create_simple_plugin логичнее разместить рядом с domain factory, а не смешивать с обходом источников.

**Порядок миграции.** Сохранить прежнюю группу и нужные clients на переход; перечислить реальные entrypoints, builtins и dev paths. Перенести только общую механику загрузки, сохранив dependency/order/on_load semantics. После появления явных declarations вывести эвристический обход имён distributions. Не переносить произвольный импорт всего окружения в новый canonical scanner.

**Приёмка.** Установленный plugin, builtin, объявленный dev plugin, duplicate IDs, ошибка импорта, зависимость, unload и воспроизводимый порядок. Сравнить допустимые компоненты и ошибки до/после; проверить фактическую экономическую модель через её прежний ABI.

**Приоритет.** Средняя стоимость; хорошая отдача по сопровождению. Не требует полной консолидации всех registries.

**Граница вывода.** Discovery и установленные plugins в этом проходе не запускались. Отсутствие pkg_resources в целевом окружении не проверено. Общие Core helpers не аттестованы как полная security boundary; authority-проверки не снимаются.

**Основания.** E49, E50, E51, E52, E66, E67. Статическое сопоставление полного legacy loader и Core primitives; отдельного runtime-probe нет.

<!-- PAGEBREAK -->

<!-- SOURCE_END LA:LA-022 -->

## Защищённые различения исходного legacy-аудита

LK — активный идентификатор защиты; внутри сохранены исходные K-заголовки.

<!-- SOURCE_BEGIN LK:LK08 -->
## K08. DomainPlugin не равен FoundryMethodPlugin

State factory, rewards, objectives, lifecycle и observations доменного plugin не покрываются одним методом pure_step. Общая discovery-инфраструктура полезна, но смена entry-point group без bridge меняет ABI. Поддержанные runtime registries могут оставаться отдельными lookup-структурами. [E49, E50, E51, E52, E66]

<!-- SOURCE_END LK:LK08 -->

