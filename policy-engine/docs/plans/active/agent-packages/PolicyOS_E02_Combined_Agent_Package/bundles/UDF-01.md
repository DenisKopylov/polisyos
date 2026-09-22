# UDF-01 — Ukraine builders: D4 handoff и малые явные contracts

**E02 · окно CP2 · локальная проверка L · начальный статус planned.**

**B:** Нет; пакет миграции LA. **LA:** LA-030 (R), LA-031 (M).

**Предшественники:** Нет. **Совместная очередь:** LANE-07.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

Первым извлечь StageBuildResult/необходимые служебные DTO в builders/contracts.py без изменения классов/полей. Перенести build_d4_stage из calibration.py в governance_handoff.py, заменить star-import семью реально нужными именами и обновить STAGE_BUILDERS. Сохранить узкий старый alias только по реальным consumers.

**Различающие тесты и сохраняемое поведение.** D4 bytes, schema_version, output filename, required stages и четыре may_not_use_for совпадают. Contract-only import не поднимает все builders. Новый incidental common symbol не появляется в handoff namespace. Полезный producer_handoff_ready не становится governance permission.

**Не считать исправлением.** Не добавлять калибровку в D4 ради названия и не переносить все common helpers сразу. Не менять Formatter или source artifact IDs.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Границы участия в LA

**LA-030:** Полный эквивалентный D4 перенос и его callers. Accountable closure: **UDF-01**; необходимые пакеты: UDF-01.

**LA-031:** Этап contracts + узкий D4 namespace; observation helpers — OBS-01, оставшееся IO/bindings/facade — UDF-02. Accountable closure: **UDF-02**; необходимые пакеты: OBS-01, UDF-01, UDF-02.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/src/polisyos/data_forge/domains/ukraine/builders/__init__.py
policy-engine/src/polisyos/data_forge/domains/ukraine/builders/calibration.py
policy-engine/src/polisyos/data_forge/domains/ukraine/builders/common.py
policy-engine/src/polisyos/data_forge/domains/ukraine/builders/contracts.py
policy-engine/src/polisyos/data_forge/domains/ukraine/builders/governance_handoff.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_udf_01.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** OBS-01, UDF-02. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Path-map записи:** MOVE-07, MOVE-19. После принятого move работать по actual target/commit, не по историческому имени файла. Source и target move одновременно зарезервированы владельцем.

**Ресурс:** L — I1 broker admits requests against a shared seven-unit L-equivalent budget and at most seven resource-bearing process groups across all worktrees; resource cost is micro=0.5, standard=1, measured medium=2–3. Permit is released after process-group cleanup and receipt; review does not hold it. Общий fan-out — 15 direct leaf workers; чтение/код/review продолжаются без compute permit. Named shared resources and immutable request fields remain enforced; builds/installs через I1.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное решение LA-030

Источник LA_r09, строки 1568–1615; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-030 -->
## LA-030. calibration.py: имя прежней ответственности после правильного D4-разделения

**Перемещение по смысловой роли**

**Точная область:**

`src/polisyos/data_forge/domains/ukraine/builders/calibration.py`

`src/polisyos/data_forge/domains/ukraine/builders/__init__.py#STAGE_BUILDERS`



**Статус.** Реальная роль уже исправлена в коде; остался семантически устаревший адрес.



**Что установлено и почему это legacy-кандидат.** Полный calibration.py не калибрует модель. build_d4_stage записывает d4_governance_request.json с перечнем required stage manifests и возвращает producer_handoff_ready. Он прямо запрещает считать запрос governance-admissibility, release-acceptance, legal-intervention-compilation или method-validity. Поэтому имя calibration шире и историчнее действительной функции, но это не забытая пустышка: STAGE_BUILDERS по-прежнему назначает её для D4.



**Что сохранить.** Весь producer handoff: stage D4, имя функции и выходного файла, schema_version, required-stage mapping, четыре may_not_use_for и ограничения authority. Не переносить сюда Foundry calibrator или Scientist governance, чтобы название снова выглядело правдоподобным.



**Куда перенести / с чем объединить.** Предлагаемый новый builders/governance_handoff.py в том же домене. STAGE_BUILDERS импортирует build_d4_stage оттуда; статистические методы остаются у Foundry, решения — у действующего владельца Scientist. При необходимости старый Python-путь временно делегирует без второй реализации.



**Порядок миграции.** Перенести тело без изменения payload и обновить точные imports/tests. Сохранять сериализованные IDs и имена артефактов: перенос Python-файла не требует миграции уже выпущенных CAS-bytes. Одновременно заменить star-import на необходимый небольшой набор, не втягивая полную перепись common.py.



**Фактическая проверка и приёмка.** P10 исполняет точный blob с фиктивными StageBuildResult/ArtifactRecord и настоящей файловой записью: handoff и все запреты сохранены. P12 подтверждает тот же payload при семи необходимых импортных символах. Нативный CAS, verified read_api, governance и весь D4 не запускались.



**Приоритет.** Дешёвый содержательный перенос; полезнее косметического объединения всех небольших builders в один файл.



**Граница вывода.** Эта карточка признаёт уже достигнутое правильное разделение полномочий. Она не утверждает, что D4 сейчас ошибочно выполняет калибровку или что handoff можно удалить.



**Основания:** E84, E92, E87. Локальные проверки: P01, P10, P12.


<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-030 -->

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

<!-- SOURCE_BEGIN LK:LK12 -->
## K12. read_api содержит проверки, а не только forwarding

В Ukraine read_api кроме ленивых экспортов есть проверка и сохранение точных bytes, размеров и hashes и явные ограничения назначения receipts. Это не лишняя оболочка, которую можно обойти прямым открытием файлов. В то же время D5 receipt не является готовым сертификатом любого демографического каталога. LA-032 использует этот подход как существующий материал для адаптера, а не автоматически расширяет его область. Чистый build_static_aging_state также остаётся полезной отдельной операцией. [E87, E88]

<!-- SOURCE_END LK:LK12 -->

