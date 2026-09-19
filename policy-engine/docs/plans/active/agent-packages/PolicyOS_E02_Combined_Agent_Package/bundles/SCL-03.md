# SCL-03 — Search→enrich: точный raw snapshot, не повторный URL-fetch

**E02 · окно CP2 · локальная проверка N · начальный статус planned.**

**B:** Нет; пакет миграции LA. **LA:** LA-025 (M).

**Предшественники:** [SCL-01](../bundles/SCL-01.md). **Совместная очередь:** LANE-09.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

Провести raw ArtifactRef/digest/fetch profile из search cache и SourceMetadata через API к enrich. Читать тот же разрешённый snapshot; отсутствие full bytes или запрещённое reuse даёт gap либо явно выбранный refresh с новой lineage. Переиспользовать существующие CAS/AcquireResult, не создавать новый store.

**Различающие тесты и сохраняемое поведение.** Search v1, URL уже v2: enrich использует v1 без сети либо явно получает v2 с новыми refs. Cache hit/miss, утраченный blob, denied access, MIME/size/document limits и no-snippet reconstruction. Связь между fragments и исходными raw bytes проверена.

**Не считать исправлением.** Общий HTTP helper не означает устранение повторного fetch. Public-web не даёт автоматическое право на любое использование.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Границы участия в LA

**LA-025:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **SCL-03**; необходимые пакеты: SCL-03.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/src/polisyos/scholar/api.py
policy-engine/src/polisyos/scholar/orchestrator/enrich.py
policy-engine/src/polisyos/scholar/search/cache.py
policy-engine/src/polisyos/scholar/search/models.py
```

**Читать как соседние контракты:**

```text
policy-engine/src/polisyos/core/artifacts/store.py
policy-engine/src/polisyos/scholar/discover/transport.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_scl_03.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** Нет по статической карте. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Path-map записи:** MOVE-12. После принятого move работать по actual target/commit, не по историческому имени файла. Source и target move одновременно зарезервированы владельцем.

**Ресурс:** N — один tiny native/numerical job, без других тестовых jobs. Общий агентный fan-out остаётся12–16; ожидание test slot не останавливает написание/review. Для загрузки зависимостей и широких builds обращаться к I1, не запускать их самостоятельно.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное решение LA-025

Источник LA_r09, строки 1114–1149; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-025 -->
## LA-025. Найденный snapshot снова превращается в URL для новой загрузки

Слияние / разделение ответственности

**Статус.** Старая URL-only граница между search и enrichment подтверждена.

**Точная область:**

`src/polisyos/scholar/api.py#_seed_sources_from_web_bundle`

`src/polisyos/scholar/api.py#enrich_topic`

`src/polisyos/scholar/orchestrator/enrich.py`

`src/polisyos/scholar/search/cache.py`

`src/polisyos/scholar/search/models.py#SourceMetadata`

**Что установлено и почему это legacy.** При поисковом bootstrap без seed_sources уже полученные источники переводятся в SourceSpec(kind=url). Сохраняются URL, некоторые metadata и web_evidence_source_id, но не привязка к bytes/digest/fetch context. Cache умеет сохранять raw bytes в CAS; SourceMetadata содержит content_sha256, но не raw artifact ref, а seed-конвертер не переносит и digest. Затем enrich снова вызывает fetch_url. Один документ может быть скачан второй раз в другой версии, а связь с прежними фрагментами остаётся только идентификатором источника.

**Что сохранить.** Обе функции: широкий поиск и дальнейшую полную обработку документа/claims. Сохранить точную версию содержимого, лицензию и происхождение, effective constraints и разделение search-evidence от нового knowledge bundle. Сам source_id не является доказательством идентичности повторно полученных bytes.

**Куда перенести / с чем объединить.** Использовать существующие ArtifactStore/CAS и AcquireResult как основу для version-bound acquisition handle между scholar/search и scholar/orchestrator. Добавление raw ref и его binding — предлагаемое расширение контракта, не уже готовый путь. Для live user-seed остаётся нормальный HTTP-adapter из LA-024.

**Порядок миграции.** Сначала провести сохранённый raw ref/digest и условия допустимого использования; enrichment читает и проверяет именно эти bytes. Если полного snapshot нет или он не разрешён к использованию, вернуть локальный gap либо явно выполнить refresh с новой lineage. Не восстанавливать документ из обрезанных snippets и не считать public-web достаточным разрешением на любое использование.

**Приёмка.** Версия v1 в поиске, изменённая v2 по тому же URL, cache-hit/miss, утраченный raw blob, отказ доступа и ограничения числа/размера документов. Проверить повторное использование v1 без нового network call либо явное создание v2. В локальной композиции конвертер сохранил source_id, потерял hash binding, а fixture downstream fetch вернул v2.

**Приоритет.** Высокая отдача по воспроизводимости и повторной работе; средняя цена. Исправлять вместе с LA-024, но различать: общий HTTP helper сам по себе не убирает второй fetch.

**Граница вывода.** Полные deep_search/enrich, настоящий CAS и сеть не запускались. Повторная загрузка может быть намеренным refresh, но такой режим должен быть явным. Не утверждается, что любой Scholar-вызов всегда удваивает трафик: проблема относится к указанному bootstrap-маршруту.

**Основания.** E58, E59, E60, E61. P17–P18; выбранный seed-converter и downstream seed-fetch, явные fixtures.

<!-- PAGEBREAK -->

<!-- SOURCE_END LA:LA-025 -->

## Защищённые различения исходного legacy-аудита

LK — активный идентификатор защиты; внутри сохранены исходные K-заголовки.

<!-- SOURCE_BEGIN LK:LK09 -->
## K09. Поиск, seed acquisition и enrichment не являются тремя копиями поиска

Discover принимает URL/files/bytes, search находит и ранжирует источники и фрагменты, orchestrator выполняет документный и claim-процесс. Объединению подлежат транспорт и граница повторного использования snapshot, не все три поддерева. [E56, E57, E58, E59, E60]

Ни техническое совершенство соседнего кода, ни слово canonical не являются доказательством взаимозаменяемости. Новый адрес функций должен уменьшать число конкурирующих исполнителей; простое перемещение старого алгоритма без смены зависимостей и контрактов не завершает смысловую миграцию.

<!-- PAGEBREAK -->

<!-- SOURCE_END LK:LK09 -->

<!-- SOURCE_BEGIN LK:LK20 -->
## K20. Content identity и контрольная сумма не являются сами по себе разрешением на reuse или closeout

Generation basis действительно строится из переданных bytes и версии правила; локально проверены current, changed content/model/rule, malformed digest и missing record. Но он не может самостоятельно установить полноту перечня, который передал caller. Generic manifest checker, в свою очередь, сохраняет поддержку пустого expected hash и не удостоверяет обязательность состава. Эти модули — полезные узкие primitives, **не obsolete helpers и не готовая полная replacement policy**. [E144, E146; r05-P34–P42]

В LA-039/LA-040/LA-041 их объединение должно сохранить различие: истинность hash, текущая принадлежность к поколению, эквивалентность запроса, целостность выходов и допустимость использования — разные утверждения. Ни одно из них не заменяется названием `current`, одним файлом manifest или удачным return code.

<!-- SOURCE_END LK:LK20 -->

