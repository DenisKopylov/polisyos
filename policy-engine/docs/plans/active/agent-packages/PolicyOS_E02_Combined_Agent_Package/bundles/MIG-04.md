# MIG-04 — DatasetManifest: converter у schema owner, явная registration

**E02 · окно CP2 · локальная проверка L · начальный статус planned.**

**B:** Нет; пакет миграции LA. **LA:** LA-050 (R).

**Предшественники:** [MIG-01](../bundles/MIG-01.md). **Совместная очередь:** LANE-06.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

Установить historical DatasetManifest profile относительно обнаруженного Fabric DTO. Перенести конкретный rename/version converter из Common в предложенный Fabric identity/migrations.py, сохранив исходные semantics отдельным relocation commit. Registration выполняет composition/ops owner; Common не импортирует Fabric обратно. Затем отдельно согласовать target validation, равные/конфликтующие aliases и missing fields. Старый адрес выводится после реальных callers.

**Различающие тесты и сохраняемое поведение.** Legacy-only/current fields, equal/conflicting aliases, unknown/absent fields, historical fixture, JSON/YAML, no-op/default target, caller isolation, exception types и native Fabric DTO. Версия 1.0 не подставляет raw_hash или created_at. Generic Common import не загружает весь Fabric; CLI binding указывает реального converter.

**Не считать исправлением.** Не объявлять любой старый manifest эквивалентным нынешнему DTO без mapping. Не удалять работающий rename из-за слова Placeholder; не создавать provenance из shape validation.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Границы участия в LA

**LA-050:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **MIG-04**; необходимые пакеты: MIG-04.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/ops/migrations/migration-contracts.toml
policy-engine/src/polisyos/common/migrations/__init__.py
policy-engine/src/polisyos/common/migrations/manifest.py
policy-engine/src/polisyos/fabric/identity/migrations.py
policy-engine/tools/ops_runners/migrations/migrate.py
```

**Читать как соседние контракты:**

```text
policy-engine/src/polisyos/common/migrations/base.py
policy-engine/src/polisyos/fabric/identity/manifest.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_mig_04.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** MIG-01, MIG-02. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Path-map записи:** MOVE-14, MOVE-15. После принятого move работать по actual target/commit, не по историческому имени файла. Source и target move одновременно зарезервированы владельцем.

**Условия общего использования:**

**A18.** Изменение import-пути не меняет historical bytes/format/ошибки автоматически. Relocation, исправление поведения и прекращение поддержки получают раздельные результаты.

**Ресурс:** L — I1 broker admits requests against a shared seven-unit L-equivalent budget and at most seven resource-bearing process groups across all worktrees; resource cost is micro=0.5, standard=1, measured medium=2–3. Permit is released after process-group cleanup and receipt; review does not hold it. Общий fan-out — 15 direct leaf workers; чтение/код/review продолжаются без compute permit. Named shared resources and immutable request fields remain enforced; builds/installs через I1.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное решение LA-050

Источник LA_r09, строки 3397–3431; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-050 -->
## LA-050. DatasetManifest migration: предметный converter остался в Common отдельно от schema owner

**R — перемещение конкретного преобразования к ближайшему владельцу формата**

**Точная область:**

`src/polisyos/common/migrations/manifest.py`

`src/polisyos/common/migrations/__init__.py` — регистрация и экспорт текущей версии.

Сопоставленный владелец модели: `src/polisyos/fabric/identity/manifest.py#DatasetManifest`. Действующий CLI и operational bindings — E184–E186.

**Статус.** Конкретное переименование `datasetName → dataset_name`, `rawHash → raw_hash` является настоящей функцией, несмотря на комментарий `Placeholder`. Common initializer импортирует этот module; CLI вызывает Common runner именно для `dataset_manifest`, и operational contract закрепляет этот binding. Поэтому **прямое удаление не обосновано**. [E181–E186]

**Что установлено.** Нейтральный Common здесь хранит правила имён одного предметного persisted формата и `MANIFEST_CURRENT_VERSION="1.0"`. Обнаруженная действующая `DatasetManifest` находится у Fabric identity, требует эти snake_case fields и запрещает extra keys. Между converter и validator нет связи в рассматриваемом CLI: Common runner выполняет renames и stamps version, но не проверяет target model. Само совпадение имён/полей не устанавливает, что *все* поддерживаемые исторические manifests 0.9 точно эквивалентны текущему Fabric DTO; это обязательная граница перед переносом.

На полном нормальном legacy-подобном fixture converter корректно переименовал поля, сохранил исходный object через Common runner, и **настоящий DatasetManifest с Pydantic** принял результат. Если одновременно были `datasetName` и `dataset_name`, старый ключ оставался — как при равных, так и при различных значениях. Runner назначал `1.0`, а реальная DTO отвергала extra key. Неполный payload также переименовывался и получал версию, но не приобретал отсутствующие обязательные поля. Это characterization того, что converter делает и чего не делает; не доказанная необходимость автоматически принимать конфликтующие aliases. [r07-P27–P29]

**Почему это смысловой перенос.** Общая механика цепочки и конкретные правила схемы имеют разных владельцев. Существование kernel Data Forge рядом не является причиной переносить этот converter именно туда: ближайшая обнаруженная модель — Fabric DatasetManifest, не StageManifest/DataForge snapshot. Common migration engine сохраняет общую функцию, а предметная версия и rename-политика должны развиваться рядом с проверяемым форматом.

**Что сохранить.** Legacy aliases, поддержанные поля и caller isolation, существующий default target, типы ошибок и запись JSON/YAML. Переименование полей не подтверждает достоверность raw_hash, права на источник, полноту данных или новую provenance; converter не должен выдумывать эти сведения. Сохранять исторический reader лучше, чем молча наполнять обязательные поля фиктивными defaults ради успешного parse.

**Куда перенести.** После подтверждения historical format mapping — предлагаемый `src/polisyos/fabric/identity/migrations.py`, рядом с существующей моделью. Это **новый возможный файл**, не обнаруженный готовый successor. Common оставляет engine и нейтральные types, не импортирует Fabric обратно. Registration нужного converter выполняет composition/ops-слой либо минимальный доменный entrypoint. Не перенести в Common весь Fabric DTO ради возможности сохранить прежний decorator import.

**Порядок миграции.** Зафиксировать реальные версии формата и caller corpus, включая два aliases, неизвестные поля, missing fields и JSON/YAML inputs. Сначала перенос без изменения преобразования, с контролируемой явной регистрацией у нового владельца и при необходимости узким старым export adapter. Затем отдельно согласовать target validation и disposition conflict: совпадение значений, несовпадение и неполнота — разные случаи. Не выбирать одну из двух противоречащих строк без решения о формате. Если исторический формат отличается от нынешнего DatasetManifest, оставить явно именованный historical-profile converter вместо принудительного слияния DTO.

Изменить operational `implementation` binding, version export, CLI import, tests и release notes в одной миграционной связке. Проверить стоимость импорта: маленький Common helper не должен внезапно требовать тяжёлой Fabric инициализации для любого generic `migrate_artifact`. Удаление старого файла допустимо только после отвязки Common initializer и всех поддержанных callers, не на основании устаревшего комментария.

**Приёмка.** Native CLI с legacy-only и current fields, совпадающими/конфликтующими aliases, unknown/absent fields, поддержанными версиями и реальным historical artifact. Сравнить преобразованные данные, исходный input, тип ошибки, default target и import registration. Целевая структурная проверка отдельно от provenance/admission: успешный model parse не даёт артефакту новых оснований использования.

**Граница вывода.** Реальный persisted historical corpus и complete caller scan не получены. В тестах исполнялась полная настоящая Fabric DTO; только imported clock заменён неиспользуемой trap, поскольку `created_at` передавался явно. Full Fabric runtime и проверка raw content не выполнялись. Категория R — рекомендуемый semantic owner при подтверждении формата; она не объявляет новый владельческий контракт уже принятым.

**Приоритет:** малый по объёму перенос; средняя интеграционная цена из-за registration side effects и version ownership. **Основания:** E178, E181–E186; r07-P27–P29.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-050 -->

## Защищённые различения исходного legacy-аудита

LK — активный идентификатор защиты; внутри сохранены исходные K-заголовки.

<!-- SOURCE_BEGIN LK:LK28 -->
## K28. Маленький manifest converter не является пустым placeholder

В отличие от LA-026 с неисполняемым codegen descriptor, здесь функция реально меняет ключи и включена в опубликованный migration CLI. Слово `Placeholder` — не доказательство отсутствия ценности. Полный контрольный payload после преобразования принят действующим DatasetManifest. **Переносить конкретную обязанность и регистрацию, а не удалять Common migration API или все manifest readers.** [E181–E186; r07-P27–P29]

<!-- SOURCE_END LK:LK28 -->

