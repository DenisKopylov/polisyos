# DFI-03 — Batch resume: input basis и обязательный output inventory

**E02 · окно CP2 · локальная проверка L · начальный статус planned.**

**B:** Нет; пакет миграции LA. **LA:** LA-041 (M).

**Предшественники:** [EMB-02](../bundles/EMB-02.md). **Совместная очередь:** LANE-08.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

Начать с конкретной embed-stage после EMB-02: связать inputs/config/rule identity и output generation, проверять обе стороны перед skip. Затем применить тот же контракт к реально используемым harvest/normalize stages без универсального сканирования всего диска. Старый stat fingerprint — hint, checksum-free manifest — historical профиль, не strict success. Сохранить прежний JSON formatter и переиспользовать kernel atomic_write_text.

**Различающие тесты и сохраняемое поведение.** Same stat/changed bytes, mtime-only change, corrupted output, empty directory, missing required member/hash, malformed old state, interrupted stage, changed config и allowed empty-generation. all([]) не означает complete; explicit [] против None трактуется объявленно. Неизменный snapshot действительно skip без нового encode, неподтверждённый — rerun/historical-only с причиной.

**Не считать исправлением.** Не хешировать большие DB при каждом шаге, когда есть проверенный immutable receipt. Не заменять formatter другим JSON writer молча и не считать input digest проверкой outputs.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Границы участия в LA

**LA-041:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **DFI-03**; необходимые пакеты: DFI-03.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/src/polisyos/data_forge/domains/catalog/batch/checkpoints.py
policy-engine/src/polisyos/data_forge/domains/catalog/batch/pipeline.py
```

**Читать как соседние контракты:**

```text
policy-engine/src/polisyos/data_forge/kernel/io/atomic.py
policy-engine/src/polisyos/data_forge/kernel/io/generation_basis.py
policy-engine/src/polisyos/data_forge/kernel/pipeline/manifests.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_dfi_03.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** DFI-02, EMB-02. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Path-map записи:** MOVE-16. После принятого move работать по actual target/commit, не по историческому имени файла. Source и target move одновременно зарезервированы владельцем.

**Условия общего использования:**

**A14.** Общий encode не готовый atomic publisher; input identity не output integrity. Resume по новому generation принимается только с нужным inventory и reader.

**Ресурс:** L — I1 broker admits requests against a shared seven-unit L-equivalent budget and at most seven resource-bearing process groups across all worktrees; resource cost is micro=0.5, standard=1, measured medium=2–3. Permit is released after process-group cleanup and receipt; review does not hold it. Общий fan-out — 15 direct leaf workers; чтение/код/review продолжаются без compute permit. Named shared resources and immutable request fields remain enforced; builds/installs через I1.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное решение LA-041

Источник LA_r09, строки 2595–2631; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-041 -->
## LA-041. Batch checkpoint: прежняя «стадия уже выполнена» живёт отдельно от content-bound результата

**M — консолидация resume-состояния с существующими механизмами основания и проверки**

**Точная область:**

`src/polisyos/data_forge/domains/catalog/batch/checkpoints.py`

`src/polisyos/data_forge/domains/catalog/batch/pipeline.py#_stage_input_fingerprint/_should_skip_stage/_record_stage_completion`

**Статус.** Checkpoint-файл прочитан целиком; pipeline — диапазон 1–265, включая построение fingerprints, outputs и embed-вызов. Resume-check исполнялся локально как точный helper, не весь pipeline.

**Что установлено.** `fingerprint_paths` хеширует список абсолютных paths, existence, size и mtime_ns, **не содержимое файлов**. `stage_can_skip` требует status `complete`, совпавший input fingerprint и существующие outputs. Их hashes, содержимое directory и связь с прежней output generation этот predicate не проверяет. В pipeline для harvest/normalize outputs могут быть директориями; для embed — пара фиксированных filenames. Стадии объявляются complete отдельным state-файлом после возврата соответствующей функции. [E139, E145]

Между тем kernel уже умеет записывать и проверять artifact hashes, а также строить content-bound generation basis с версией правила. Поэтому старый checkpoint — не неизбежная единственная инфраструктура возобновления; это самостоятельная прежняя политика принятия результата рядом с более точными механизмами. **Наличие этих механизмов ещё не означает, что текущий resume их применяет.** [E144, E146]

**Локальное различение.** После замены output bytes старый `stage_can_skip` сохранил True, а checker ранее записанного manifest отверг hash mismatch. Изменение входа при сохранении size и восстановленном mtime сохранило старый fingerprint; generation basis из реальных новых bytes стал incompatible. Смена только mtime дала обратную картину: прежний fingerprint изменился, content basis — нет. Опустевшая output-directory продолжила удовлетворять `.exists()`. Это ограниченные файловые witnesses, не заявления о частоте такого состояния в production. [r05-P25–P30]

**Что сохранить.** Действительное resume, stage dependencies, восстановление после частичного исполнения, чтение поддержанных старых state-файлов, текущие правила missing/malformed state как cache miss и корректный отказ при отсутствующем обязательном output. Старый stat-fingerprint может остаться дешёвым hint для оптимизации, но не эквивалентом подтверждённого содержательного основания. Не обязательно пересчитывать каждый большой DB целиком на каждый вызов: допустимы проверенные immutable snapshots/receipts, действительно связанные с его содержимым.

**Куда перенести / с чем объединить.** Stage-specific input/output description остаётся у catalog pipeline. Общие функции hashing, запись и representation reuse связываются с существующими `generation_basis`, manifest и atomic owners. Если потребуется отдельный небольшой resume adapter в kernel, это предлагаемое расширение **поверх них**, не ещё один независимый registry. `batch/checkpoints.py` может временно стать адаптером исторического state format; прямого drop-in нового `stage_can_skip` пока не установлено.

**Два обязательных различения.** Во-первых, input basis не является output integrity: нужны обе проверки. Во-вторых, generic manifest validator намеренно поддерживает старые записи: существующий файл без expected hash даёт passed, а пустой inventory возвращает пустой tuple. Следовательно, `all(validate_manifest_artifacts(...))` без проверки обязательного состава и hashes **не является** строгой новой политикой resume. Следует связать проверенный список обязательных outputs со стадией и явно определить режим legacy-записи. [E146; r05-P34–P35]

**Порядок миграции.** Для выбранной стадии определить эффективные inputs, конфигурацию/версию преобразования и output inventory. При completion сохранить эти основания и фактическую проверку результата. При resume разрешать skip лишь для поддержанного совпадающего основания и сохранившихся outputs; несовместимое или недоказанное reuse даёт адресную причину пересчёта, не молчаливый success. Не переносить все completion-поля в один новый файл до проверки rollback/recovery. В процессе удаления старой реализации сохранить исторический reader и явный converter там, где format ещё используется.

**Небольшое конкретное слияние I/O.** Checkpoints повторяет temp-file/write/fsync/replace. Kernel atomic writer уже существует и дополнительно выполняет directory fsync. Но старый checkpoint JSON сортирует keys, а `atomic_write_json` kernel их не сортирует. В тесте прямая замена изменила bytes; прежний formatter плюс существующий `atomic_write_text` их сохранил. Поэтому сначала объединяется транспорт публикации, а изменение сериализованного формата — отдельное решение. [E145, E147; r05-P33]

**Приёмка.** Повтор без изменений, changed input with same stat, changed output, пустой directory, отсутствующий файл, незавершённая запись, malformed legacy state, changed rule/config, checksum-free old manifest и восстановление после прерванной стадии. Для каждого сценария различать skip, rerun, historical-only и unavailable. Корректные пустые результаты описываются явно; отсутствие элементов в `all()` не доказывает полноту.

**Приоритет.** Высокая практическая отдача: сократить и необоснованный reuse, и ненужное повторение вычислений. Начать с одной стадии с конечным набором входов/выходов, затем переносить остальные. Строгие content-bound receipts не создают полномочий на научный или governance-вывод.

**Граница вывода.** Не проверены все stage predicates, publish/closeout validators и существующие пользователи старых state-файлов. Не утверждается, что слабый local checkpoint уже позволяет обойти final admission. Полный resume-run и project CI не исполнены. Отдельные явные пустые `required_outputs=[]` сейчас означают fallback к записанным outputs; изменение этого API-смысла также не должно произойти случайно. [r05-P31–P32]

**Основания:** E139, E144–E149. **Проверки:** r05-P25–P42.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-041 -->

## Защищённые различения исходного legacy-аудита

LK — активный идентификатор защиты; внутри сохранены исходные K-заголовки.

<!-- SOURCE_BEGIN LK:LK20 -->
## K20. Content identity и контрольная сумма не являются сами по себе разрешением на reuse или closeout

Generation basis действительно строится из переданных bytes и версии правила; локально проверены current, changed content/model/rule, malformed digest и missing record. Но он не может самостоятельно установить полноту перечня, который передал caller. Generic manifest checker, в свою очередь, сохраняет поддержку пустого expected hash и не удостоверяет обязательность состава. Эти модули — полезные узкие primitives, **не obsolete helpers и не готовая полная replacement policy**. [E144, E146; r05-P34–P42]

В LA-039/LA-040/LA-041 их объединение должно сохранить различие: истинность hash, текущая принадлежность к поколению, эквивалентность запроса, целостность выходов и допустимость использования — разные утверждения. Ни одно из них не заменяется названием `current`, одним файлом manifest или удачным return code.

<!-- SOURCE_END LK:LK20 -->

