# OBS-01 — Календарные observation helpers: перенос и корректные периоды

**E02 · окно CP2 · локальная проверка L · начальный статус planned.**

**B:** B146. **LA:** LA-031 (M).

**Предшественники:** [UDF-01](../bundles/UDF-01.md). **Совместная очередь:** LANE-07.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

Взять контракты после UDF-01. Выделить согласованную группу преобразования period/observation-time из builders/common в предметный builders/observation.py с явными импортами. Отдельным следующим коммитом исправить B146: календарные границы, неизвестный период, invalid month без January-2025 и clamp. Изменение форматирования старых артефактов не смешивать с переносом.

**Различающие тесты и сохраняемое поведение.** Relocation: valid month/quarter/year дают прежние bytes/поля. Bugfix: 2024-02 заканчивается 29-м; invalid и missing не становятся датами. Сохраняется уникальный-period precompute; native sources caller читает новый helper. B147 — отдельный OBS-02.

**Не считать исправлением.** Не заменять дату now и не перечитывать весь файл после yield без учёта эффекта. Spy не является проверкой настоящего Parquet reader.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Границы участия в LA

**LA-031:** Этап observation/time helpers и их реальных callers; исправление B146 выполняется уже у нового владельца. Оставшиеся IO/bindings/facade части — UDF-02. Accountable closure: **UDF-02**; необходимые пакеты: OBS-01, UDF-01, UDF-02.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/src/polisyos/data_forge/domains/ukraine/builders/common.py
policy-engine/src/polisyos/data_forge/domains/ukraine/builders/observation.py
policy-engine/src/polisyos/data_forge/domains/ukraine/builders/sources.py
```

**Читать как соседние контракты:**

```text
policy-engine/src/polisyos/ir/observation/contracts.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_obs_01.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** OBS-02, UDF-01, UDF-02. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Path-map записи:** MOVE-07, MOVE-08. После принятого move работать по actual target/commit, не по историческому имени файла. Source и target move одновременно зарезервированы владельцем.

**Ресурс:** L — I1 broker admits requests against a shared seven-unit L-equivalent budget and at most seven resource-bearing process groups across all worktrees; resource cost is micro=0.5, standard=1, measured medium=2–3. Permit is released after process-group cleanup and receipt; review does not hold it. Общий fan-out — 15 direct leaf workers; чтение/код/review продолжаются без compute permit. Named shared resources and immutable request fields remain enforced; builds/installs через I1.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное основание B146

Источник B_r19, строки 3778–3791; полный неизменённый текст.

<!-- SOURCE_BEGIN B:B146 -->
## B146. Неизвестный период становится январём 2025 года, а февраль теряет високосный день

**Основание и область:** `_period_to_dates` в common и `_period_series_to_iso_bounds`/вызывающий observation-builder в sources. Статическая цепочка доведена до полей `period_start/period_end` observation dataframe. [C13.R04, C13.R05]

**Проблема.** До разбора задаются year=2025, month=1. Нераспознанная строка сохраняет эти значения, а месяц вне диапазона обрезается к 1–12. Series-helper ещё раньше заменяет missing на `2025-01`. Таблица конца месяца фиксирует февраль как 28 дней. Отсутствие или повреждение времени превращается в конкретное наблюдение другого периода.

**Локальное свидетельство P29–P33.** `2024-02` получило конец `2024-02-28` вместо 29-го; `not-a-period` — январь 2025-го; `2024-13` — декабрь 2024-го. Series с None также выдала январь 2025-го. Валидный `2024Q2` правильно преобразовался в 1 апреля — 30 июня. Контроль календарного конца месяца дал 29 дней в феврале 2024 года.

**Рекомендуемое исправление.** Разрешать объявленный формат и частоту источника явным парсером; проверять настоящий диапазон и календарные границы. Сохранять различие неизвестного периода и некорректного значения. Для понятного monthly-контракта достаточно стандартного календарного расчёта или соответствующего Period, без собственной глобальной календарной платформы. Существующая оптимизация преобразования только уникальных строк периода полезна и должна сохраниться.

**Приёмка.** Високосный/обычный февраль, квартал, год, разные разрешённые форматы, missing и ошибочный месяц. Проверить принятую включительность `period_end` и принадлежность границы следующему периоду. Версионировать исправленную проекцию и адресно переоценить зависимые наблюдения; не переписывать происхождение старого артефакта.

**Не делать и границы.** Не заменять фиксированный 2025 текущим годом. Не обрезать invalid month, не заполнять дату последней известной без предметного разрешения. Реальная доля таких входов и прохождение вышележащих нормализаторов не измерялись; валидный источник с заранее проверенными периодами может не проявить часть механизма.

<!-- SOURCE_END B:B146 -->

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

<!-- SOURCE_BEGIN LK:LK12 -->
## K12. read_api содержит проверки, а не только forwarding

В Ukraine read_api кроме ленивых экспортов есть проверка и сохранение точных bytes, размеров и hashes и явные ограничения назначения receipts. Это не лишняя оболочка, которую можно обойти прямым открытием файлов. В то же время D5 receipt не является готовым сертификатом любого демографического каталога. LA-032 использует этот подход как существующий материал для адаптера, а не автоматически расширяет его область. Чистый build_static_aging_state также остаётся полезной отдельной операцией. [E87, E88]

<!-- SOURCE_END LK:LK12 -->

