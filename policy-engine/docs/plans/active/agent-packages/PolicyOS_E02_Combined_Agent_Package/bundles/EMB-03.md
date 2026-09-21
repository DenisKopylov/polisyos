# EMB-03 — Legal embeddings: content-bound incremental и честный старый backend API

**E02 · окно CP2 · локальная проверка N · начальный статус planned.**

**B:** Нет; пакет миграции LA. **LA:** LA-040 (M), LA-042 (C).

**Предшественники:** [EMB-02](../bundles/EMB-02.md). **Совместная очередь:** LANE-08.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

Сохранить append-only legacy profile лишь с его установленными предпосылками. Новый reuse связывает actual projected text, encoder revision/profile и current membership; changed content/model/withdrawal дают точные обновления. Использовать общий publisher EMB-02. Отдельный compatibility commit мигрирует build_embeddings_and_index: unsupported backend не игнорируется, default calls переходят на canonical builder по lifecycle.

**Различающие тесты и сохраняемое поведение.** Unchanged append; changed text same ID; withdrawal; model change same dimension и different dimension; projection-rule change; corrupt/missing sidecar; full rebuild и historical NPZ. Сохраняются три legal projections и chunking. Old backend trap получает явную несовместимость, не silent local default; canonical model/device/chunk forwarding и result identity проверены.

**Не считать исправлением.** Не маркировать старый NPZ проверенным cache задним числом и не удалять historical readers/полезные old vectors. Не создавать третий publisher и не считать одинаковую размерность совместимостью модели.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Границы участия в LA

**LA-040:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **EMB-03**; необходимые пакеты: EMB-03.

**LA-042:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **EMB-03**; необходимые пакеты: EMB-03.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/src/polisyos/data_forge/domains/legal/batch/cli.py
policy-engine/src/polisyos/data_forge/domains/legal/batch/embedder.py
policy-engine/src/polisyos/data_forge/kernel/embeddings.py
```

**Читать как соседние контракты:**

```text
policy-engine/src/polisyos/data_forge/kernel/io/generation_basis.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_emb_03.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** EMB-01, EMB-02. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Path-map записи:** MOVE-16. После принятого move работать по actual target/commit, не по историческому имени файла. Source и target move одновременно зарезервированы владельцем.

**Условия общего использования:**

**A14.** Общий encode не готовый atomic publisher; input identity не output integrity. Resume по новому generation принимается только с нужным inventory и reader.

**Ресурс:** N/C — I1 broker drains L and admits one exclusive native/numerical/build or checkpoint job using the full seven-unit budget; no other resource-bearing job runs concurrently. Общий fan-out — 15 direct leaf workers; чтение/код/review продолжаются без permit. Immutable argv/cwd/worktree/SHA/selectors/timeout/output root and named resources are fixed at admission; builds/installs через I1.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное решение LA-040

Источник LA_r09, строки 2556–2594; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-040 -->
## LA-040. Legal incremental embeddings: старый ID-cache не описывает эквивалентность вычисления

**M — миграция от ID-only reuse к version/content-bound reuse**

**Точная область:**

`src/polisyos/data_forge/domains/legal/batch/embedder.py#_load_existing_ids`

`src/polisyos/data_forge/domains/legal/batch/embedder.py#_embed_table`

`src/polisyos/data_forge/domains/legal/batch/embedder.py#build_local_embeddings_and_indexes`

**Статус.** Полный файл прочитан и сохранён с совпадающим Git blob SHA. Наличие канонического local-builder в CLI и unit-test подтверждено. Реальные пользовательские incremental-сценарии, контракты неизменности IDs и production-частота не установлены. [E142, E150–E151]

**Что установлено.** При `incremental=True` старый NPZ даёт множество `ids`, ordered ID list и vectors. Каждая текущая row с уже известным ID исключается из нового encode без сравнения text, projection version или model identity. Старые IDs заранее копируются в выход; финальный index собирается из старых и добавленных векторов. Запись, исчезнувшая из текущей непустой таблицы, сама по себе не исключается. В NPZ этого writer сохраняются только `ids` и `vectors`. [E142]

Такой режим может быть корректной оптимизацией **при явно подтверждённом append-only корпусе, неизменяемом содержимом IDs и неизменном encoder profile**. Эти предпосылки не проверяются рассматриваемым механизмом. Поэтому проблема — не существование incremental, а универсально выглядящий параметр, под которым продолжается прежняя более узкая модель «ID однажды вычислен навсегда».

**Локальное различение.** Полная исходная `_embed_table` на append-only контрольном корпусе корректно добавила одну запись и сохранила две прежние. При изменённом тексте того же ID encode не вызван; при удалении одного ID он остался в индексируемом списке. При смене модели на другую **той же размерности** сохранились два старых вектора и добавился один новый. При смене размерности NumPy уже отказал в stacking; это важный отрицательный контроль, а не доказательство безопасности same-dimension случая. `incremental=False` пересобрал текущий состав и пересчитал изменённый текст. [r05-P17–P23]

**Что сохранить.** Дешёвый reuse действительно эквивалентных вычислений, chunked чтение, thermal pauses, три отдельные текстовые проекции entities/facts/provisions, счётчики embedded/skipped, порядок ID-to-label и старые полезные векторы. Не нужно заново скачивать исходный документ или пересчитывать неизменившуюся запись лишь потому, что изменился соседний объект.

**Куда перенести / с чем объединить.** Существующий `kernel/io/generation_basis.py` — подходящий владелец общей content/rule identity; он уже отличает current/missing/malformed/incompatible и проверяет recorded digest. Для embedding reuse требуется небольшой adapter: content identity реально поданного текста, версия projection/encoder profile и привязка к проверенной модели. Одного свободного имени модели недостаточно для неизменного revision. Список текущих IDs и membership/withdrawal semantics должны входить в описание нового index generation. Общая индексная публикация — из LA-039, без третьего отдельного HNSW writer. [E144]

**Порядок миграции.** Сначала назвать прежний режим как ограниченный append-only legacy profile и определить, где его предпосылки действительно обеспечены. Новому пути дать per-record reuse keys и целый generation inventory. Старый NPZ без оснований не маркировать задним числом как проверенный cache; допускаются declared historical use, проверяемое дообогащение из сохранившихся оснований или контролируемый rebuild. Для удалений различить текущую проекцию и архивную историю: сохранение старой записи может быть нужно истории, но не должно неявно включать её в текущий поиск.

Смена content или модели пересчитывает только затронутые записи, когда совместимость остальных доказана; смена пространства encoder обычно требует нового совместимого комплекта. Модель, normalization и projection profile нельзя маскировать лишь одинаковым числом колонок vectors. Генератор основания получает действительные bytes; сам по себе пересчитанный digest не устанавливает, что caller перечислил весь необходимый состав.

**Фактическая проверка и границы.** SQL и модель — фикстуры, векторные операции/NPZ/файлы — реальные; не проводилось измерение реальных semantic distances. Полный native CLI, DuckDB и SentenceTransformer не запускались. Прочитанный repository-test использует fake SentenceTransformer и проверяет обычную сборку трёх таблиц/наличие файлов; он здесь **прочитан, не запущен**, и его наличие не закрывает incremental migration. [E150]

**Приёмка.** Unchanged append, changed text same ID, deletion/withdrawal, same-dimension model revision, dimension mismatch, changed projection rule, missing/corrupt sidecar, полный rebuild и исторический индекс. Проверить не только counts, но и точное соответствие текущей записи вычисленному vector profile. Старые lexical data/readers целиком не удаляются.

**Приоритет.** Высокая семантическая отдача; средняя цена при наличии сохранившихся источников и model revision. Более развитый local-builder не объявляется безопасной универсальной заменой Academic/Catalog до этой миграции.

**Разграничение с LA-039.** Там — общая механика и публикация комплекта при полном build; здесь — критерий эквивалентности отдельной повторно используемой записи и текущего состава. Общий publisher поможет обеим карточкам, но сам не исправит ID-only cache. Объёмы работ с общими файлами не суммировать дважды.

**Основания:** E142, E144, E150–E151. **Проверки:** r05-P17–P23, r05-P36–P42.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-040 -->

## Исходное решение LA-042

Источник LA_r09, строки 2632–2660; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-042 -->
## LA-042. Старый embedding entrypoint: исчезнувший backend-контракт остался в сигнатуре

**C — завершение compatibility-поверхности без удаления действующего builder**

**Точная область:**

`src/polisyos/data_forge/domains/legal/batch/embedder.py#build_embeddings_and_index`

**Статус.** Функция прямо помечена backward compatibility. Собственного алгоритма у неё нет. Адресный поиск старого имени вернул определение; полного отсутствия внешних/динамических callers он не устанавливает. [E142, E152]

**Что установлено.** Старый entrypoint принимает `db_path`, `output_dir`, `backend=None`, `chunk_size=2000`, но передаёт действующему `build_local_embeddings_and_indexes` только paths и `embedding_chunk_size`. `backend` не читается и не передаётся. Новый local-builder выбирает свой default SentenceTransformer/model/device, если они явно не заданы через его собственный API. Сигнатура старой функции поэтому сохраняет видимость выбора, которого исполнение уже не соблюдает. Канонический local-builder действительно используется в CLI и unit-test. [E142, E150–E151]

**Что сохранить.** Действующий local-builder, EmbeddingStats, chunk-size mapping и default-вызовы, на которые ещё распространяется compatibility. Не удалять весь embedder.py или новые параметры incremental/fp16 только потому, что последний wrapper устарел. Не трактовать этот wrapper как реальный альтернативный backend.

**Куда перенести / с чем объединить.** Существующий `build_local_embeddings_and_indexes` — явная точка нового local-вызова. Сначала мигрировать old callers на параметры этого API; затем удалить **только старую функцию** после необходимого окна. Временная обёртка должна явно сообщать об unsupported `backend`, а не принимать значение как будто оно применено. Действительная необходимость backend polymorphism проверяется отдельно: не создавать новый общий backend API лишь ради сохранения неисполняемого параметра.

**Порядок миграции.** Найти точный symbol/FQN, imports, generated API/docs, notebooks, configs и external clients; разделить вызовы без backend и с переданным backend. Для первых можно сохранить узкую delegation с объявленным сроком. Для вторых нужен явный выбор поддержанного executor либо диагностируемое прекращение неподдержанного запроса. Нельзя молча заменить пользовательскую модель локальным default и назвать это сохранением поведения. В audit не устанавливается произвольная sunset-date.

**Фактическая проверка.** Полный исходный module загружен; у wrapper локально заменён только target на recording fixture. BackendTrap, запрещающий любое чтение своих атрибутов, и `backend=None` дали одинаковые аргументы target и тот же result identity. Переданы только `db_path`, `output_dir`, `embedding_chunk_size=17`. Модель, GPU и реальный target в этом probe не запускались. [r05-P24]

**Приёмка.** Без backend, unsupported backend, явный canonical model/device, chunk-size forwarding, exceptions/result type и отсутствие старого имени после завершённого retirement. Перевод notebook не должен автоматически запускать загрузку модели или менять вычислительные затраты без явного параметра.

**Приоритет.** Низкая цена по коду, конечная адресная миграция. Удаление compatibility-функции не зависит от завершения всех LA-039/LA-040, но её поведение нельзя выдавать за поддержанный новый backend до их решения.

**Граница вывода.** Не подтверждён реальный caller, передающий backend, и не измерены вызванные этим затраты. Наличие молча игнорируемого параметра подтверждено; внешний ущерб не установлен. Это C, а не новое безусловное D-разрешение.

**Основания:** E142, E150–E152. **Проверка:** r05-P24.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-042 -->

## Защищённые различения исходного legacy-аудита

LK — активный идентификатор защиты; внутри сохранены исходные K-заголовки.

<!-- SOURCE_BEGIN LK:LK20 -->
## K20. Content identity и контрольная сумма не являются сами по себе разрешением на reuse или closeout

Generation basis действительно строится из переданных bytes и версии правила; локально проверены current, changed content/model/rule, malformed digest и missing record. Но он не может самостоятельно установить полноту перечня, который передал caller. Generic manifest checker, в свою очередь, сохраняет поддержку пустого expected hash и не удостоверяет обязательность состава. Эти модули — полезные узкие primitives, **не obsolete helpers и не готовая полная replacement policy**. [E144, E146; r05-P34–P42]

В LA-039/LA-040/LA-041 их объединение должно сохранить различие: истинность hash, текущая принадлежность к поколению, эквивалентность запроса, целостность выходов и допустимость использования — разные утверждения. Ни одно из них не заменяется названием `current`, одним файлом manifest или удачным return code.

<!-- SOURCE_END LK:LK20 -->

