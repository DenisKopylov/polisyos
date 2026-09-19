# HYG-02 — Evidence/governance/factlog: точные адресные retirement

**E02 · окно CP2 · локальная проверка L · начальный статус planned.**

**B:** Нет; пакет миграции LA. **LA:** LA-008 (D), LA-009 (C), LA-018 (C).

**Предшественники:** Нет. **Совместная очередь:** LANE-12.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

Конечный scan трёх shim helper symbols, трёх governance aliases и Lex factlog. Перевести подтверждённых source/config/generated consumers к existing Core/Fabric owners; снять только ненужные старые surfaces по фактическому lifecycle. Для поддержанного facade оставить минимальное forwarding с конкретным условием завершения, не новый framework.

**Различающие тесты и сохраняемое поведение.** Public Scientist/evidence imports; Core type identity, Lex facts read result/access/provenance; config/string/relative/monkeypatch consumers и negative retired roots. Не восстанавливаются evidence_sources/provenance/claims старые корни. Selected native import tests сейчас, distribution inventory CP6; неизвестные external obligations явно перечислены.

**Не считать исправлением.** Не удалять scientist/governance/passes или evidence целиком, root polisyos.evidence, Fabric reader. Нулевой indexed search не является полным census.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Границы участия в LA

**LA-008:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **HYG-02**; необходимые пакеты: HYG-02.

**LA-009:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **HYG-02**; необходимые пакеты: HYG-02.

**LA-018:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **HYG-02**; необходимые пакеты: HYG-02.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/src/polisyos/lex/factlog.py
policy-engine/src/polisyos/scientist/evidence/_shim.py
policy-engine/src/polisyos/scientist/governance/passes/base.py
policy-engine/src/polisyos/scientist/governance/passes/legal_pass.py
policy-engine/src/polisyos/scientist/governance/passes/safety_pass.py
```

**Читать как соседние контракты:**

```text
policy-engine/src/polisyos/core/governance/passes/base.py
policy-engine/src/polisyos/fabric/world/__init__.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_hyg_02.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** Нет по статической карте. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Path-map записи:** MOVE-21. После принятого move работать по actual target/commit, не по историческому имени файла. Source и target move одновременно зарезервированы владельцем.

**Ресурс:** L — максимум два таких jobs по всем worktree. Общий агентный fan-out остаётся12–16; ожидание test slot не останавливает написание/review. Для загрузки зависимостей и широких builds обращаться к I1, не запускать их самостоятельно.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное решение LA-008

Источник LA_r09, строки 281–307; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-008 -->
## LA-008. Evidence _shim: helper для уже выведенных пространств имён

**Прямая очистка: перенос логики не нужен**

**Статус.** Функция helper установлена; наличие всех клиентов требует конечного scan.

**Точная область:**

`src/polisyos/scientist/evidence/_shim.py`

**Что установлено и почему это legacy-кандидат.** install_module_shim/shim_getattr/shim_dir лишь создают старые import-поверхности, переносят metadata sunset и reexport names. Evidence README запрещает восстанавливать retired evidence_sources/provenance/claims roots. Адресный поиск install_module_shim вернул только этот файл.

**Что сохранить.** Никакой claim/evidence/provenance-логики из helper переносить не требуется. Живые evidence/claims и evidence/provenance остаются.

**Куда перенести / с чем объединить.** При подтверждении отсутствия клиентов — удалить файл. Не создавать взамен новый общий shim-framework; в репозитории уже есть независимые совместимые обёртки там, где они нужны.

**Порядок миграции.** Проверить относительные импорты, вызовы shim_getattr/shim_dir, string paths, codegen и tests. Если обнаружен ещё живой клиент, мигрировать только его или оставить минимальную временную связь с датой прекращения.

**Приёмочная проверка.** Публичный Scientist import и evidence tests, отсутствие восстановленных retired roots. Scope проверки должен включать tools/config, а не только src imports.

**Приоритет.** Низкая цена; первая волна после полного scan.

**Граница вывода.** Отсутствие результатов индексного поиска не равнозначно доказанному отсутствию всех динамических клиентов.

**Основания:** E13, E14.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-008 -->

## Исходное решение LA-009

Источник LA_r09, строки 308–338; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-009 -->
## LA-009. Scientist governance aliases: завершить перенос к Core

**Вывод compatibility после миграции**

**Статус.** Deprecated aliases подтверждены; директория passes/ в целом живая.

**Точная область:**

`src/polisyos/scientist/governance/passes/base.py`

`src/polisyos/scientist/governance/passes/legal_pass.py`

`src/polisyos/scientist/governance/passes/safety_pass.py`

**Что установлено и почему это legacy-кандидат.** Эти три файла только реэкспортируют Core governance и предупреждают о deprecated import. Lex simulator уже импортирует Core напрямую. Они не являются тремя отдельными policy implementations. Остальные Scientist passes имеют собственные роли и не подпадают под удаление по соседству.

**Что сохранить.** Canonical classes в core/governance, их точную идентичность, contracts и всю настоящую Scientist pipeline.

**Куда перенести / с чем объединить.** Действующие src/polisyos/core/governance/passes/{base,legal_pass,safety_pass}.py. Перенос реализации уже сделан; требуется миграция оставшихся import/config paths.

**Порядок миграции.** Сверить legacy entrypoints в plugins, TOML/YAML и generated docs, а также test_shared_shims. После изменения соглашения обновить alias-tests на запрет старых путей. Не приписывать этим файлам неподтверждённую индивидуальную sunset-date.

**Приёмочная проверка.** Identity публичных типов, загрузка governance по конфигурации, Lex imports и отрицательные compatibility tests. Одна строка замены импорта не доказывает полное закрытие внешних клиентов.

**Приоритет.** Низкая/средняя цена; отдельный короткий retirement-пакет.

**Граница вывода.** Тестовые consumers известны из корпуса; всех внешних конфигураций нет. Не удалять scientist/governance/passes целиком.

**Основания:** E15, E16, E17, E30, E22.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-009 -->

## Исходное решение LA-018

Источник LA_r09, строки 571–597; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-018 -->
## LA-018. Lex factlog: alias читателя фактов у другого владельца

**Вывод compatibility после миграции**

**Статус.** Перенос владельца уже выражен в коде.

**Точная область:**

`src/polisyos/lex/factlog.py`

**Что установлено и почему это legacy-кандидат.** Файл лишь реэкспортирует load_world_facts из polisyos.fabric.world. Это не отдельный legal fact store и не второй reader; старый Lex-адрес скрывает фактическое владение данными.

**Что сохранить.** Работающий Fabric world reader и доступные публичные semantics чтения. Исторические world/fact артефакты не мигрируют от изменения Python import.

**Куда перенести / с чем объединить.** Существующий публичный polisyos.fabric.world.load_world_facts. Дополнительная реализация или перенос в общий core не нужны.

**Порядок миграции.** Установить, объявлен ли Lex-путь внешним поддержанным facade. Если да — совместимый период и release note; если нет и внутренние callers переключены — удалить alias. Не назначать произвольный sunset без текущей policy.

**Приёмочная проверка.** Эквивалентность объекта/read result, отсутствие changes в authorization/provenance и обновление docs, import/config strings. Проверить root Lex exports, прежде чем снимать alias.

**Приоритет.** Низкая цена; не срочнее реальных semantic duplicates.

**Граница вывода.** Полный caller census и внешний API-статус этого имени не установлены. Наличие compatibility alias само по себе не ошибка.

**Основания:** E31.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-018 -->

## Защищённые различения исходного legacy-аудита

LK — активный идентификатор защиты; внутри сохранены исходные K-заголовки.

<!-- SOURCE_BEGIN LK:LK17 -->
## K17. Явно публичный OPA facade не обязан исчезать вместе со всеми aliases

`runtime/http/opa_input.py` — четыре явных reexports sealed runtime authorization objects у того же владельца. Собственной OPA-evaluation логики там нет, но narrow public import может быть нужной границей для consumers. Не установлены ни retirement-решение, ни эквивалентный обязательный публичный заменитель. Поэтому файл не добавлен в delete/retire manifest. Существование compatibility-фасада — сигнал выяснить его договор, не автоматическое доказательство legacy. Полные authorization/middleware implementations и их consumers здесь не аудированы. [E133]

<!-- SOURCE_END LK:LK17 -->

<!-- SOURCE_BEGIN LK:LK18 -->
## K18. Корневой evidence — не доказанный дубль Scientist evidence

README описывает `polisyos.evidence` как внутреннего владельца cross-producer evidence-graph records. Полный initializer явно экспортирует claim-registry normalization, conflict records и effective-independence graph operations. Это положительное основание существования отдельной роли, не ещё один случай восстановленного retired Scientist namespace из LA-008. Документ требует downstream binding и не разрешает превращать conflict materialization в положительную поддержку. **Не удалять этот корень по совпадению слова evidence.** [E153–E154]

Ограничение контроля: реализации portfolio и все runtime bridges здесь не прочитаны. README и exports не являются доказательством end-to-end корректности или полномочий этих записей. Новые функции/owners в этом аудите не назначаются.

<!-- SOURCE_END LK:LK18 -->

