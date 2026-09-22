# EMB-01 — Academic/Catalog: общий encode/index primitive, разные text profiles

**E02 · окно CP2 · локальная проверка N · начальный статус planned.**

**B:** Нет; пакет миграции LA. **LA:** LA-039 (M).

**Предшественники:** Нет. **Совместная очередь:** LANE-08.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

Снять точные ID/text/projection/model/device corpus обоих доменов; выделить общую механику над подготовленными (id,text) в предложенный kernel/embeddings.py. Domain wrappers сохраняют SQL, title/abstract/description truncation и собственные result fields. Этот этап сохраняет существующий формат; согласованную generation-публикацию выполняет EMB-02.

**Различающие тесты и сохраняемое поведение.** Одинаковые effective texts дают тот же input модели, normalization/dtype/labels/M/ef settings; Catalog500 и Academic1200 остаются разными. Малый реальный NumPy/HNSW path без загрузки большой SentenceTransformer; fake encoder допустим для wiring, но не объявляется тестом модели. Counts/profile/device/thermal pause hooks сохранены.

**Не считать исправлением.** Не перемещать Academic в Catalog, не сливать legal chunking с полным rebuild и не копировать третий HNSW writer. Не запускать полное построение корпусных индексов на Mac.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Границы участия в LA

**LA-039:** Этап 1/2: общий вычислительный primitive при сохранённых subject profiles; публикация/reader и closure — EMB-02. Accountable closure: **EMB-02**; необходимые пакеты: EMB-01, EMB-02.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/src/polisyos/data_forge/domains/academic/batch/embedder.py
policy-engine/src/polisyos/data_forge/domains/catalog/batch/embedder.py
policy-engine/src/polisyos/data_forge/kernel/embeddings.py
```

**Читать как соседние контракты:**

```text
policy-engine/src/polisyos/data_forge/kernel/io/atomic.py
policy-engine/src/polisyos/data_forge/kernel/pipeline/manifests.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_emb_01.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** EMB-02, EMB-03. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Path-map записи:** MOVE-16. После принятого move работать по actual target/commit, не по историческому имени файла. Source и target move одновременно зарезервированы владельцем.

**Условия общего использования:**

**A14.** Общий encode не готовый atomic publisher; input identity не output integrity. Resume по новому generation принимается только с нужным inventory и reader.

**Ресурс:** N/C — I1 broker drains L and admits one exclusive native/numerical/build or checkpoint job using the full seven-unit budget; no other resource-bearing job runs concurrently. Общий fan-out — 15 direct leaf workers; чтение/код/review продолжаются без permit. Immutable argv/cwd/worktree/SHA/selectors/timeout/output root and named resources are fixed at admission; builds/installs через I1.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное решение LA-039

Источник LA_r09, строки 2515–2555; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-039 -->
## LA-039. Academic/Catalog embeddings: повтор механики и незавершённая публикация поколения

**M — общий вычислительный и публикационный primitive, отдельные доменные профили**

**Точная область:**

`src/polisyos/data_forge/domains/catalog/batch/embedder.py`

`src/polisyos/data_forge/domains/academic/batch/embedder.py`

Зависимые поверхности: `catalog/batch/pipeline.py`, `catalog/knowledge/store.py` и действующие потребители `ac_work_*` / `ds_dataset_*`.

**Статус.** Оба builder прочитаны целиком. Повтор общей механики и поведение публикации подтверждены точными исходниками. Не утверждается, что два доменных корпуса или их смысловые индексы одинаковы.

**Что установлено.** Оба файла читают rows из DuckDB, собирают texts, создают SentenceTransformer, пакетно вызывают `encode(..., normalize_embeddings=True)`, приводят векторы к float32, строят cosine HNSW с `ef_construction=200, M=16`, назначают последовательные числовые labels и сохраняют NPZ/HNSW. Различаются SQL-проекция, текстовый шаблон, filenames, default-device и форма результата. Academic возвращает фактическую размерность и записывает model/dimension/device в stage metrics; Catalog — только число и thermal-флаг. [E140–E141]

В обоих builders пустые rows приводят к возврату **до обновления индексных файлов**. Внешний `run_embed` затем всё равно записывает stage manifest со `status="ok"` и прежними фиксированными именами. В существующем каталоге это может заново связать manifest с прежним индексом, а в новом — указать отсутствующие файлы. Catalog pipeline записывает completion после возврата `run_embed`; его resume-путь рассматривается отдельно в LA-041. [E139–E141]

Также NPZ и HNSW публикуются последовательно. В локальной инъекции отказа второго сохранения NPZ уже относился к новым rows, а HNSW-файл остался прежним. Атомарность каждого отдельного файла сама по себе не делает атомарной **пару**, её IDs и основание генерации.

**Что сохранить.** Catalog текст `title + description[:500] + keywords[:20] + variables[:20]` и Academic `title + abstract[:1200]` — разные поддержанные проекции. Сохранить row-ID correspondence, truncation, batching, normalization, выбранные параметры модели и устройства, тепловые паузы, filenames и читаемость старых результатов. Нельзя заменить dataset description абстрактом публикации ради единой функции.

**Куда перенести / с чем объединить.** Предлагаемый небольшой `data_forge/kernel/embeddings.py` либо связный модуль того же kernel-владельца: общая операция над **уже подготовленными** `(id, text)`, выбранной моделью и явно заданным output profile. Это новый предлагаемый coordinator, не найденная готовая реализация. Domain wrappers отвечают за запрос, текстовую проекцию и смысл результата. Общая публикация использует существующие `atomic_write_*` / `atomic_commit_path`, generation basis и manifest primitives. Kernel не импортирует доменные SQL/builders обратно. [E144, E146–E149, E155]

Не переносить Academic целиком в Catalog и не заменять их legal `_embed_table` целиком: последний несёт иной chunking/incremental контракт и пока имеет ограничение LA-040. Совпадение HNSW-параметров — основание выделить общую операцию, не признать разные datasets одной задачей.

**Порядок миграции.** Сначала зафиксировать доменные effective-text fixtures и ID ordering. Выделить общий encode/index primitive без изменения этих проекций. Затем публиковать version-bound комплект через staging и одну точку выбора поколения; прежний комплект остаётся доступным, пока новый не завершён. Пустой corpus требует явного результата «текущее поколение пусто» или отказа/недоступности, согласованного с reader, а не повторного обозначения старого индекса. Нельзя уничтожать пригодный старый snapshot до успешной фиксации нового.

Обновить loader-contract: полное соответствие NPZ IDs, vectors, HNSW и basis должно проверяться до выбора поколения. В прочитанном `DatasetCatalogStore` индексный путь проверяет наличие двух filenames и загружает их; это **не отменяет** уже существующей отдельной content-binding логики catalog fetch/database. [E143]

**Фактическая проверка.** r05-P08–P16 исполняют оба полных файла и настоящий kernel manifest writer. При одинаковых эффективных texts получились одинаковые fixture-vectors, labels и параметры construction. Два пустых повторных запуска сохранили прежние bytes; контрольные суммы в заново записанном manifest совпали с ними. Academic при этом записал новое имя модели `fake-B`, не пересчитав старые векторы. Свежий пустой запуск оставил отсутствующие файлы и пустые hashes. Инъекция ошибки index-save воспроизвела смешанную пару. Различие 500/1200 символов сохранено.

**Ограничения испытания.** SQL rows, модель и HNSW — явные фикстуры. `.hnsw` в тесте — JSON-запись вызовов, не настоящий бинарный индекс. Реальны исходная orchestration, NumPy/NPZ, manifests, SHA-256 и файловая система. Не измерены ANN recall, качество модели, native HNSW failure behavior или сквозной поисковый результат.

**Приёмка.** Оба профиля, пустой/непустой corpus, повтор с новой моделью, отказ между сохранениями, перестановка rows, отсутствие одного файла, старый поддержанный комплект и reader, который не смешивает поколения. Для простого выделения общего primitive сравнивать данные/параметры; изменение формата публикации версионировать отдельно. Не обещать побайтовой воспроизводимости native ANN без отдельной проверки её условий.

**Приоритет.** Высокая полезность: убрать две поддерживаемые копии и один общий класс незавершённой публикации. Существенная доля работы — в reader/handoff, не в сокращении тела encode-loop.

**Основания:** E139–E144, E146–E149, E155. **Проверки:** r05-P08–P16, r05-P36–P42.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-039 -->

## Защищённые различения исходного legacy-аудита

LK — активный идентификатор защиты; внутри сохранены исходные K-заголовки.

<!-- SOURCE_BEGIN LK:LK20 -->
## K20. Content identity и контрольная сумма не являются сами по себе разрешением на reuse или closeout

Generation basis действительно строится из переданных bytes и версии правила; локально проверены current, changed content/model/rule, malformed digest и missing record. Но он не может самостоятельно установить полноту перечня, который передал caller. Generic manifest checker, в свою очередь, сохраняет поддержку пустого expected hash и не удостоверяет обязательность состава. Эти модули — полезные узкие primitives, **не obsolete helpers и не готовая полная replacement policy**. [E144, E146; r05-P34–P42]

В LA-039/LA-040/LA-041 их объединение должно сохранить различие: истинность hash, текущая принадлежность к поколению, эквивалентность запроса, целостность выходов и допустимость использования — разные утверждения. Ни одно из них не заменяется названием `current`, одним файлом manifest или удачным return code.

<!-- SOURCE_END LK:LK20 -->

