# DFI-02 — Core sources: API cutover без обратной синхронизации globals

**E02 · окно CP2 · локальная проверка N · начальный статус planned.**

**B:** Нет; пакет миграции LA. **LA:** LA-038 (M).

**Предшественники:** [DFI-01](../bundles/DFI-01.md). **Совместная очередь:** LANE-08.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

После DFI-01 отвязать registry/transformers/api с тем же конечным dependency inventory, затем направить batch pipeline к самостоятельному API. Старый facade сохраняет лишь explicit supported bindings/delegates на реальное окно, без _sync_implementation_globals. Согласовать существующую no-growth/monkeypatch запись и тесты; не удалить тестируемость вместе с совместимостью.

**Различающие тесты и сохраняемое поведение.** Один настоящий batch consumer без предварительного legacy import; sync/async, budget/lease/profile handoff, ошибок и counters parity. Добавленный атрибут фасада не попадает в leaves; изменение leaf dependency не стирается следующим вызовом. Два контролируемых вызова с разными зависимостями изолированы. Source-selection DFK-02 не теряет filters при совместной приёмке.

**Не считать исправлением.** Не строить второй acquisition transport и не сливать Fabric с доменной orchestration. Не считать explicit __all__ достаточным, пока broadcast ещё работает.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Границы участия в LA

**LA-038:** Этап 2/2 и accountable closure: остальные листья, фактический caller и снятие broadcast; обе группы обязательны. Accountable closure: **DFI-02**; необходимые пакеты: DFI-01, DFI-02.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/architecture/module_size_budget.toml
policy-engine/src/polisyos/data_forge/domains/catalog/batch/core_sources/api.py
policy-engine/src/polisyos/data_forge/domains/catalog/batch/core_sources/registry.py
policy-engine/src/polisyos/data_forge/domains/catalog/batch/core_sources/transformers.py
policy-engine/src/polisyos/data_forge/domains/catalog/batch/core_sources_ingest.py
policy-engine/src/polisyos/data_forge/domains/catalog/batch/pipeline.py
```

**Читать как соседние контракты:**

```text
policy-engine/src/polisyos/data_forge/domains/catalog/registry.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_dfi_02.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** DFI-01, DFI-03, EMB-02. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Ресурс:** N/C — I1 broker drains L and admits one exclusive native/numerical/build or checkpoint job using the full seven-unit budget; no other resource-bearing job runs concurrently. Общий fan-out — 15 direct leaf workers; чтение/код/review продолжаются без permit. Immutable argv/cwd/worktree/SHA/selectors/timeout/output root and named resources are fixed at admission; builds/installs через I1.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное решение LA-038

Источник LA_r09, строки 2482–2514; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-038 -->
## LA-038. core_sources_ingest: после разделения файлов фасад остаётся владельцем общего изменяемого окружения

**M — завершение разделения реализации и compatibility-состояния**

**Точная область:**

`src/polisyos/data_forge/domains/catalog/batch/core_sources_ingest.py`

Зависимые модули: `core_sources/{writers,validators,loaders,registry,transformers,api}.py`; контракты — `_core_sources_ingest_contracts.py`; подтверждённый production-source caller — `batch/pipeline.py`.

**Статус.** Полный фасад прочитан и локально воспроизведён. Шесть implementation-модулей не прочитаны целиком и не объявлены взаимозаменяемыми. Проблема — механизм общего окружения, а не доказательство ошибочности всех результатов ingestion.

**Что установлено.** При импорте фасад последовательно обходит globals шести модулей, создаёт delegates для функций и сохраняет остальные значения у себя. Перед каждым делегированным sync/async вызовом `_sync_implementation_globals()` записывает получившееся пространство имён **обратно во все шесть модулей**. Исключён небольшой набор инфраструктурных имён и double-underscore имена; обычные imports, single-underscore helpers и добавленные атрибуты в общем случае участвуют. Поэтому два публичных имени в `__all__` не означают узкий внутренний контракт. [E136]

Это не просто временный второй import-path: состояние старого монолита продолжает определять окружение новых файлов. В `architecture/module_size_budget.toml` такое поведение прямо отмечено как поддержка legacy monkeypatch globals; там же фасад описан как no-growth compatibility. Значит, тестовая совместимость — известная причина существования механизма, а не новая догадка аудита. Pipeline всё ещё вызывает `run_core_sources_ingest_async` через этот адрес. [E138–E139]

**Локальное различение.** На точном facade-blob и шести явно синтетических листьях обычный импорт ещё не изменил их значения. Первый вызов раздал всем значение последнего модуля; дополнительный атрибут фасада также появился во всех листьях. Изменение одного leaf-global было стёрто следующим compatibility-вызовом. Sync-wrapper при этом не является тем же function object, хотя сохраняет `__wrapped__`; async-маршрут сохранил контрольный результат. Это свидетельство механизма, **не найденная коллизия двух настоящих численных функций и не воспроизведённая конкурентная авария**. [r05-P02–P07]

**Что сохранить.** Все действительные ограничения источников, budgets, очереди, ошибки, типы результатов, операции записи, sync/async способы запуска и возможность подменять внешние зависимости в tests. В прочитанном начале `core_sources/api.py` уже используются настоящие Fabric connectors, leases и source profiles; их не следует заменять новым параллельным HTTP-fetch ради снятия фасада. [E137]

**Куда перенести / с чем объединить.** Реализации остаются у существующих `core_sources/*`. Зависимости каждого leaf должны стать явными: imports у фактического владельца либо переданный контекст только для действительно изменяемых зависимостей. DTO остаются у существующего contracts-файла, если его граница подходит. Старому фасаду оставить лишь конечный перечень поддержанных bindings/delegates; он не должен назначать окружение независимым модулям при каждом вызове. Новая глобальная service-container подсистема здесь не требуется.

**Порядок миграции.** Сначала инвентаризировать фактические cross-leaf имена и monkeypatch targets, затем переносить одну связанную группу зависимостей. Прямое переключение pipeline на `core_sources.api` до этого может удалить необходимую неявную инициализацию. После отвязки leaf-группы заменить относящийся к ней broadcast узким binding, сравнить traces и только затем снимать соответствующее compatibility-обязательство. Не заменять синхронизацию повторным wildcard import: это сохраняет тот же скрытый контракт в другой форме.

**Приёмка.** Canonical-вызов работает без предварительного импорта старого фасада; независимая зависимость leaf не меняется от соседнего вызова; старые тестовые substitutions получают явный адрес; одинаковые входы сохраняют requests, writes, errors и counts. Отдельно проверить coroutine identity/signature expectations и безопасную замену зависимостей при конкурентной работе. Существующий budget и characterization tests — спутники миграции, не повод удалить их ради малого файла.

**Приоритет.** Высокая архитектурная отдача, средняя/высокая цена из-за скрытых зависимостей. Исполнять по leaf-группам, не переписывать весь ingestion сразу.

**Граница вывода.** Полный граф зависимостей шести реализаций и native source-ingestion не построены. Карточка родственна LA-020/LA-031, но добавляет **обратную запись** в уже разделённые модули; обычная фиксация `__all__` этот механизм не устраняет. Все три карточки не суммируются как три одинаковых объёма очистки.

**Основания:** E136–E139. **Проверки:** r05-P01–P07.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-038 -->

## Защищённые различения исходного legacy-аудита

LK — активный идентификатор защиты; внутри сохранены исходные K-заголовки.

<!-- SOURCE_BEGIN LK:LK19 -->
## K19. Catalog ingestion уже переиспользует Fabric — не всякая дополнительная стадия является вторым acquisition

В начале `core_sources/api.py` используются Fabric `AsyncFetchLease`, `FetchRequest`, connection/source-execution profiles и специализированные connectors. Это поддерживает разделение между исполнителем приобретения и batch orchestration/преобразованием/записью данных. **LA-038 не предполагает удаления Fabric connectors или переноса всей batch orchestration в Fabric.** [E137]

У source-specific `harvester.py` в r05 прочитано только начало с imports и приоритетами; его сетевые функции не сравнивались целиком с Fabric. Полная equivalence или наличие вторых HTTP-реализаций по каждой source family **не установлены**. Эта часть следующей очереди остаётся открытой, а не подменяется новой общей карточкой «все harvesters — legacy».

<!-- SOURCE_END LK:LK19 -->

