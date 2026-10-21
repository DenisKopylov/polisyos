# Конкретные маршруты получения

Часть [проекта](../12-acquisition-storage-and-deployment.md). Все ниже предлагаемые составные маршруты требуют реализации и проверки. Existing code seams закреплены в [reuse map @C](../lifecycle/01-reuse-map.md); названия маршрутов — исследовательская навигация, не новый runtime enum.

## 1. Когда получать

| Инициатор | Что выполнять | Что ограничивает |
|---|---|---|
| Подготовка installation/cell | Подключить разрешённые catalogs, source modules, methods/profiles; минимальный reference corpus и release metadata; проверить транспорт без зеркалирования всего мира | Purpose, languages/jurisdictions, storage rights, chosen capability. Source card не admission. |
| Background prefetch | Приобретать часто требуемые, долго доступные или общие immutable releases и строить разрешённые read models | Expected reuse/VOI, acquisition и maintenance cost; отдельный бюджет exploration, отсутствие вечной priority starvation |
| Runtime demand | Из gap конкретного task получить exact missing input/relationship/act; начать с уже имеющейся подходящей версии | Реальный query purpose, deadline, допустимый scope и достаточность для выбранного claim |
| Контрпоиск/discovery | Искать альтернативные методики, несогласующиеся наблюдения, неизвестные категории и перспективы | Не только keyword/top-k; фиксировать declared search scope, selection bias и missing coverage |
| Custody watch | Наблюдать changes/corrections/expiry/withdrawal, выполнять conditional fetch/reconciliation и reissue зависимых uses | Обязательство по уже подписанным claims; freshness policy источник-/claim-specific, не единый TTL |
| Обучение после run | Обновлять permitted search/cost priors и проверяемые causal/model hypotheses | Retrieval learning отдельно от нового empirical evidence и confirmatory inference |

Preseed и runtime обязаны сохранять одинаковые receipt/permission/lineage/use semantics. Source-specific batch и runtime producers могут различаться; использовать один producer там, где actual owner это поддерживает. Не объединять все DataForge batch pipelines ради одинакового имени entrypoint. Ночной «ручной» скрипт без lineage/permission/receipt не становится доверенным источником потому, что сработал раньше run. С другой стороны, неизвестная схема/правило не запрещает разрешённое candidate исследование: ограничивается конкретное authority use.

## 2. Общая последовательность

1. Existing acquisition planner получает gap с purpose, требуемым property и scope; выбирает reuse/discovery/fetch/remote compute/institutional request. Eligibility до ranking. Если нет обоснованного scalar priority, сохранять несколько критериев/альтернатив, не скрытый денежный score.
2. Resolver проверяет existing catalog + source-specific owner. Discovery request может быть неполным; execution request фиксирует endpoint/selector, immutable version или честно ограниченный observation cut, request semantics, profile/schema/codec, permitted processing location, credential handle, budgets и deadline. Это binding между существующими contracts, не новый всеобъемлющий DTO.
3. Runtime создаёт durable intent; Fabric/соответствующий producer получает scoped permit. Credentials используются adapter-ом; LLM видит только дозволенную проекцию. Нужное внешнее согласие не выводится из наличия ключа API.
4. Producer получает bounded pages/partitions/result, проверяет native completion/checkpoint и пишет разрешённые capture bytes + receipt. Durable materialization предшествует cursor acknowledgement. Ошибка на странице не оставляет complete release.
5. Parser/normalizer производит derived artifact с input refs, codec/schema/rule version, потерями и time roles. Перевод/OCR/unit conversion/linkage — substantive transforms, а не безусловный clean-up.
6. Native owner проверяет нужное отношение: document→proposition, data→measurement, method→metric, act→authority. Транспортный успех не заменяет эту проверку.
7. Existing acquisition route loop доставляет receipt обратно исходному task; новый world/catalog release и run binding фиксируются owner-ом. Переоценить gap: могла появиться только информация о невозможности, а не требуемое основание.
8. Fresh consumer читает exact selection и свою admission decision; catalog visibility и повторное использование регулируются [storage design](03-storage-and-reuse.md). Возврат в новый процесс после crash обязателен для будущего acceptance.

## 3. Матрица транспортов

| Канал | Конкретный путь | Persist/replay граница | Дефект, который обязан различать consumer |
|---|---|---|---|
| Web search/LLM research | Search provider → candidate URL/citation → authorized HTTP/browser capture → DocMeta/DocFragment → claim extraction → Scholar/Legal/other owner | Query/provider/time/selection bounds, exact permitted source representation/spans; search snippets отдельно | Summary найден, оригинал недоступен; citation реальна, но statement не следует из source |
| Publisher/open metadata API | DOI/identifier resolver, scholarly update API, official publication feed → exact work/release → content where licensed | Metadata version не full text; retraction/correction relation и scope | Два DOI относятся к одному исследованию; correction меняет только одну таблицу |
| HTTP/REST dataset | Fabric SourceContract + registered connector → bounded query/pages → terminal capture root → normalization/read model | Source release/snapshot/page contract; 304 ссылается на уже durable exact representation | Empty not-modified response принят за empty dataset; unstable pagination пропускает/дублирует rows |
| SQL/warehouse | Read-only identity → parameterized bounded query или owner-prepared view → source snapshot → streamed result/aggregate | Query AST/params semantics, schema, timezone/collation/null rules, source transaction/snapshot, output bytes если разрешено | Pages из разных snapshots; aggregate изменил denominator или disclosure threshold |
| Columnar files/object storage | Source manifest/version → selected objects/partitions → content-bound reader; range projection только с доказуемой выбранной identity | Object generation/hash, partition membership и required completeness | Отсутствующая partition объявлена нулём; HEAD size заменил content verification |
| Streaming/CDC/webhook | Authenticated event/feed → durable intake/dedupe → native frontier/window → source relation → impact/revalidation | Source incarnation, partition offsets, event/observation/receipt time, correction/retraction semantics | Webhook не пришёл, значит ничего не изменилось; offset gap или replay source reset замаскированы |
| Local/user import | Explicit selected file/DB snapshot/package → admitted importer → quarantine/capture → native parser | Copy or controlled immutable snapshot; mutable external path не durable identity | Пользователь заменил файл по тому же path, parser продолжил с прежним receipt |
| Remote computation/federation | PolicyOS permitted request → custodian/approved executor → selected query/method → permitted result + verifiable receipt | Input cut/recipe/executable/output binding и limitations; raw может не покидать custodial cell | Signed aggregate выдаётся за independently verified raw или exact replay без доступных inputs |
| Human/institutional input | Request dossier → authorized external channel → actual response/act → identity/competence/scope verification | Original act/response, issuer verification, time/expiry, dissent/representation | Agent draft/self-attestation подменил mandate/consent/court ruling |
| New observation/study | Gap/VOI → approved study/measurement design → external operator → observations/design receipts → DataForge/Scientist | Protocol, sampling/assignment, instrument, population/time and actual execution | Simulated/generated data обозначены как collected; stopping/selection changes скрыты |
| Licensed/private portal | Authorized session/service account → provider-supported export/query → scoped adapter | Session identity не authority; bounded evidence о selected bytes и permitted reuse | Login/terms обходятся автоматизацией; cookies/signed links попали в shared artifact |

Все каналы требуют своего фактического adapter. MCP/HTTP/Arrow/SQL — формы транспорта, не доказательства одинаковой семантики. Browser automation использовать как scoped fallback, если нет подходящего API/export и такой доступ допустим; DOM/rendered text, язык, navigation state и выбранная версия сохраняются в permitted provenance. Screenshot не подменяет структурный table/act parser.

## 4. Web и LLM: discovery не должен теряться и не должен командовать

LLM получает задачу поиска, разрешённые tools и ограниченный context. Внешние страницы, PDF, tool responses и извлечённые instructions — **данные**, не команды расширить scope, раскрыть secrets или публиковать claim. Fetch redirect и вложенный URL проходят тот же outbound policy; parser по умолчанию без ambient network/credentials. Отдельный admitted subrequest нужен для новых external dependencies.

Решение о допустимом получении основывается на применимом праве/договоре/разрешении, включая доступные исключения и ограничения; не требуется выдумывать индивидуальную лицензию на каждое обычное разрешённое действие. Для rights discovery сначала используется дозволенный metadata/terms route. Если даже он требует неизвестного доступа, остаются иной открытый источник или запрос хранителю — bootstrap не обходит protected boundary.

Source occurrence хранится до candidate assertions. Для каждого assertion: точный span/table/cell, original language, extractor/model/prompt version в допустимой форме, uncertain parse и связь к original. Interpreter может предложить translation/entailment, но authority consumer проверяет нужное свойство. Если оригинал недоступен, допустим context-only discovery с named limitation; не надо фабриковать полный capture ради заполнения схемы.

Search trace должен позволять отличить deliberately excluded results, provider truncation, quota failure и no-hit. Сохранение raw query и всех результатов зависит от чувствительности и прав; minimization не должно превращаться в ложную полноту поиска. Допустимы protected query binding и permitted coarse public explanation. Retrieval corpus меняется: selection/index/model generation входит в существенный use dependency.

## 5. Dataset запросы и вычисление рядом с данными

Сначала выяснить наличие source-native immutable release/snapshot или стабильного extraction protocol. Stable key ordering/keyset pagination решает часть pagination, но **не делает меняющуюся таблицу snapshot**. Read-only repeatable snapshot, source release manifest, export job или declared observed sequence дают разные guarantees. Cross-database join не получает общий snapshot от двух успешных connectors.

Read-only SQL identity, разрешённый statement/function set, query budget и безопасная parameter binding нужны вместе. Одно имя `SELECT` или parameterization не доказывает отсутствие side effects через функции/расширения и не ограничивает cost. Не открывать arbitrary SQL header как публичную команду.

Pushdown фильтров/проекций/агрегатов уменьшает transfer/RAM только при сохранении нужной семантики: exact population, unit/convention, weights, null handling, time/calendar, coding system и разрешённого disclosure. Predicate capability и execution identity записываются; unsupported pushdown выполняется корректным owner-ом локально/у custodian или ограничивается, не заменяется похожим запросом.

Для запрета raw export предпочтителен approved compute near data. Передавать recipe/versioned method/allowed projection, возвращать permitted sufficient output и result-binding receipt. Для privacy-limited repeated queries нужен общий accounting owner на реальный requester/dataset scope: несколько runs не создают новый budget. TEE/подпись/secure transport могут доказывать отдельное execution property, но не causal validity, representation или legal competence. Расчёт с secret raw остаётся ограниченным по независимой reproducibility, если reviewer не имеет разрешённого verification route.

## 6. Updates и режимы ожидания

Source release schedules, push notifications и conditional polling используются вместе по supported source class. Webhook ускоряет реакцию; periodic reconciliation необходим там, где delivery/coverage не гарантированы. Источник может перестать существовать, сменить идентификатор, удалить запись или менять текст без version ID: сохранять наблюдённые версии, uncertainty и native correction relations.

Ожидание внешнего акта, quota cooldown, exhausted disk/RAM, review или source outage становится durable deferred work в существующем Runtime с named prerequisite. Не держать HTTP request, worker lease или child resource reservation на неопределённый срок. До resume повторить sensitive permission/currentness resolution. Порядок retry/cancellation/commit, aggregate budgets и completion reserve определены [resource protocol](../lifecycle/09-resource-execution-design.md), а не вторым scheduler в acquisition layer.

## 7. Concrete adapters: reuse и следующий delta

В inspected source C видны REST/SDMX, local SQL, file/object и finite-event readers, но их guarantees различаются. `fabric/connectors/sources/sql_query.py` поддерживает local SQLite/DuckDB; generic remote transaction/pushdown не следует из названия SQL. `sdmx_source.py` chunks уже полученный DataFrame; `file_tabular.py`/`object_storage.py` читают payload до row limit. `event_stream.py` читает JSONL, что не равнозначно broker CDC. `connectors/federation/composer.py` соединяет уже materialized frames; общий source cut этим не создаётся. Это чтение перечисленных paths @C, не absence census всего репозитория.

Для remote SQL первым adapter выбрать один реально поддержанный server/isolation contract, parameterized query plan и bounded batch transfer. [Arrow Flight SQL](https://arrow.apache.org/docs/format/FlightSql.html) даёт protocol для SQL и Arrow results, но transaction support конкретного server требуется проверить; ticket сам не snapshot. Для SDMX bind API/dataflow/DSD versions и component semantics. Для геоданных [STAC API](https://docs.ogc.org/cs/25-005/25-005.html) помогает Item Search/asset selection; next link не означает frozen multi-page result. PostgreSQL consistent snapshot применим в своей transaction boundary, а не автоматически к federated queries. [PostgreSQL isolation](https://www.postgresql.org/docs/current/transaction-iso.html).

Для scholarly discovery [Crossref REST](https://www.crossref.org/documentation/retrieve-metadata/rest-api/) — конкретный metadata/DOI route; publisher/full text и права разрешаются отдельно. Для общего web search выбрать provider/contract, разрешающий необходимые transient lookup, retention, display, extraction и audit uses. Если выбранный plan не разрешает durable results, использовать разрешённые transient leads и отдельно permitted original capture; не сохранять запрещённые snippets в trace, corpus или embeddings. Условия зависят от сервиса/плана/договора и требуют actual contract review; эта работа не выдаёт общего юридического разрешения или запрета для всех search providers.

HTTP validation связывает 304 с подходящей сохранённой representation; это protocol guidance, не подтверждение реализации PolicyOS. [RFC9111 §§4.3.3–4.3.4](https://www.rfc-editor.org/rfc/rfc9111.html#section-4.3.3). Catalog discovery может описываться DCAT-compatible metadata, но DCAT не заменяет source/use admission: переиспользовать semantic catalog вместо второго metadata service. [DCAT3](https://www.w3.org/TR/vocab-dcat-3/).

Pattern pass: P01/P02/P12/P15/P25/P27/P29/P31/P32/P35/P37/P38. Minimum acceptance: ordinary task вызывает реальный connector, оставляет exact durable receipt, возвращается после restart к fresh consumer; malformed/partial/wrong-source/refused-route не дают admitted result. Tests UNRUN.
