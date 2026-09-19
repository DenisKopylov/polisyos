# UDF-02 — Ukraine common: доменный I/O, binding diagnostics и явные exports

**E02 · окно CP2 · локальная проверка N · начальный статус planned.**

**B:** Нет; пакет миграции LA. **LA:** LA-031 (M).

**Предшественники:** [UDF-01](../bundles/UDF-01.md), [OBS-01](../bundles/OBS-01.md). **Совместная очередь:** LANE-07.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

На основе извлечённых contracts/time helpers выделить связные I/O и bindings-validation группы, а не файл на функцию. Сохранить старый serializer и использовать kernel atomic_text/bytes. Перевести sources и прочих подтверждённых consumers на явные imports; убрать global wildcard facade только после local characterization всех используемых имён.

**Различающие тесты и сохраняемое поведение.** JSON/NPZ/Parquet output profile не меняется от relocation, ошибки atomic write и прежние диагностические warnings сохранены. Synthetic validation payload остаётся явно тестовым, не observation. Canonical builders работают без common wildcard bootstrap; sequential memory scheduler сохраняется. Deferred native Parquet означает непроверенный профиль, не успешный тест.

**Не считать исправлением.** Не удалить common.py целиком по чтению начала/конца; не делать домен зависимым от tools; не переписать serializer другой JSON функцией.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Границы участия в LA

**LA-031:** Завершающий этап и accountable closure: IO, bindings diagnostics, остальные explicit imports. UDF-01 и OBS-01 — отдельные обязательные части. Accountable closure: **UDF-02**; необходимые пакеты: OBS-01, UDF-01, UDF-02.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/src/polisyos/data_forge/domains/ukraine/builders/__init__.py
policy-engine/src/polisyos/data_forge/domains/ukraine/builders/bindings_validation.py
policy-engine/src/polisyos/data_forge/domains/ukraine/builders/common.py
policy-engine/src/polisyos/data_forge/domains/ukraine/builders/io.py
policy-engine/src/polisyos/data_forge/domains/ukraine/builders/sources.py
```

**Читать как соседние контракты:**

```text
policy-engine/src/polisyos/data_forge/kernel/io/atomic.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_udf_02.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** OBS-01, OBS-02, UDF-01. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Path-map записи:** MOVE-07, MOVE-08, MOVE-09, MOVE-19. После принятого move работать по actual target/commit, не по историческому имени файла. Source и target move одновременно зарезервированы владельцем.

**Ресурс:** N — один tiny native/numerical job, без других тестовых jobs. Общий агентный fan-out остаётся12–16; ожидание test slot не останавливает написание/review. Для загрузки зависимостей и широких builds обращаться к I1, не запускать их самостоятельно.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное решение LA-031

Источник LA_r09, строки 1616–1667; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-031 -->
## LA-031. builders/common.py: разделённые файлы всё ещё живут в namespace старого монолита

**Объединение / разделение ответственности**

**Точная область:**

`src/polisyos/data_forge/domains/ukraine/builders/common.py`

`src/polisyos/data_forge/domains/ukraine/builders/__init__.py`

`src/polisyos/data_forge/domains/ukraine/builders/calibration.py`

`src/polisyos/data_forge/domains/ukraine/builders/sources.py#bindings-validation caller`



**Статус.** Смешение обязанностей и неявный импортный контракт подтверждены; не все функции файла изучены.



**Что установлено и почему это legacy-кандидат.** В common.py соседствуют StageBuildResult, планировщик памяти, JSON/Parquet/NPZ I/O, преобразования наблюдений, synthetic multiscale fixture и validation-subsetting. Импортируются NumPy, pandas, CAS, IR и внутренний словарь большого adapters.py. В конце __all__ включает всё, кроме double-underscore имён, в том числе imports и private helpers. D4 делает from .common import *, а builders/__init__.py аналогично собирает несколько модулей. Файловое разделение сохранило общую неявную среду старого большого builder.



**Что сохранить.** Реальные stage builders, типы результатов, сохраняемые артефакты, диагностический synthetic payload и его предупреждения, согласованное поведение малого последовательного scheduler. В найденном caller synthetic payload используется для bindings validation; он не объявлен здесь подменой реальных наблюдений.



**Куда перенести / с чем объединить.** Небольшой предлагаемый builders/contracts.py для результата/служебных типов; builders/io.py для доменной сериализации поверх существующего kernel/io; observation helpers по предмету; builders/bindings_validation.py для диагностических payload/subsets. Явные imports между модулями. Не переносить украинскую семантику в глобальный common и не создавать файл на каждую функцию.



**Порядок миграции.** Начать с D4: семь действительно используемых имён вместо широкого namespace. Затем по потребителям выделять связные группы без изменения математических и сериализационных правил. Для I/O не подменять текущие bytes вызовом другого JSON formatter: kernel atomic_write_text/bytes можно использовать после прежнего сериализатора. Ограничения private-symbol доступа проверять до снятия exports. Полный общесистемный cache/import framework не нужен.



**Фактическая проверка и приёмка.** P11 показывает, что дополнительный символ fixture common наследуется неизменённым D4-module. P12 удаляет его из предоставленной поверхности и получает тот же handoff через семь symbols. Это локальная проверка зависимости, не измерение времени импорта или памяти. Нужны native import-budget/characterization tests, registry mappings и сравнение output bytes выбранных stages.



**Приоритет.** Средняя цена, высокая архитектурная отдача: меняются зависимости, а не только папки. Возможно выполнять небольшими порциями.



**Граница вывода.** Прочитаны начало и конец common.py плюс конкретный потребитель; весь sources.py и все промежуточные функции не аудированы. Нельзя на этом основании удалить common.py целиком. Последовательный scheduler не считается legacy только из-за отсутствия параллельности.



**Основания:** E83, E84, E85, E92, E93. Локальные проверки: P11, P12.


<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-031 -->

## Защищённые различения исходного legacy-аудита

LK — активный идентификатор защиты; внутри сохранены исходные K-заголовки.

<!-- SOURCE_BEGIN LK:LK10 -->
## K10. Малый materialize.py выполняет настоящую функцию

Его AssetDefinition связывает спецификацию с callable; декоратор сохраняет связь; plan_asset_specs упорядочивает зависимости и отвергает отсутствующую зависимость и цикл. Три контрольных случая P20–P22 прошли на выбранной исходной функции с минимальными fixture-спецификациями. Это не полный materialization executor, но и не бессодержательный placeholder. **Сохранить реальные контракты и planner; не приписывать ему неисполненные возможности распределённой системы.** [E72]

<!-- SOURCE_END LK:LK10 -->

<!-- SOURCE_BEGIN LK:LK11 -->
## K11. Academic shadow — не обязательно остаток, который пора выбросить

В прочитанном loader проверяются schema generation, текущая materialized schema identity и согласованность готовности потребителя. Там же есть inventory и дифференциальный отчёт. В skg.py — реальная read-only DuckDB-инспекция. Название shadow и упоминание legacy-входов не отменяют текущую read-функцию после завершения cutover. **Не удалять на основании названия; отделять поддержку сохранённых данных от необязательного исторического сравнения только по найденным потребителям.** Нативный DuckDB здесь не запускался. [E90, E91]

<!-- SOURCE_END LK:LK11 -->

<!-- SOURCE_BEGIN LK:LK12 -->
## K12. read_api содержит проверки, а не только forwarding

В Ukraine read_api кроме ленивых экспортов есть проверка и сохранение точных bytes, размеров и hashes и явные ограничения назначения receipts. Это не лишняя оболочка, которую можно обойти прямым открытием файлов. В то же время D5 receipt не является готовым сертификатом любого демографического каталога. LA-032 использует этот подход как существующий материал для адаптера, а не автоматически расширяет его область. Чистый build_static_aging_state также остаётся полезной отдельной операцией. [E87, E88]

<!-- SOURCE_END LK:LK12 -->

