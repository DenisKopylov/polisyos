# Расширение без переделки ядра

Уточнение после повторного review: [implementation protocols](05-implementation-protocols.md) и [delivery/probes](06-delivery-and-review.md) конкретизируют capture, enrollment, current-read, rights/restore и retirement. Они сохраняют standing исследовательского проекта; новые runtime проверки не выполнены.

Исследовательское предложение в составе [жизненного цикла](../11-foundation-lifecycle.md). Оно не вводит новый plugin ABI, product enum или deployment requirement. Переиспользуемые символы приведены в [карте кода](01-reuse-map.md); будущие проверки — в [сценариях](04-stewardship-and-probes.md).

## 1. Общие механизмы и независимые предметные расширения

Устойчивое ядро должно выполнять ограниченный набор обязанностей: связать exact inputs/outputs, обеспечить допустимый доступ, ограниченное исполнение, replay в заявленной границе, наблюдаемые переходы и передачу результата владельцу смысла. Правила расчёта бедности, legal applicability и полноты sensor stream не следует размещать внутри этого ядра.

| Изменение | Нормальный способ подключения | Когда этого недостаточно |
|---|---|---|
| Новый URL/dataset поддержанного API | Versioned source declaration + выбранный connector/profile | У API другие consistency/authentication/side-effect semantics |
| Новый язык или документ | Reader/extractor profile + проверка на соответствующем материале | Требуется новый parser или новый вид meaning verification |
| Новая классификация, correspondence, набор единиц | Content-bound rule resources с предметным owner | Mapping меняет construct или скрывает many-to-many/неполноту |
| Новый метод оценки | Уже поддерживаемая method signature и registered implementation | Новые uncertainty/causal guarantees требуют отдельного inference contract |
| Больше данных | Partitioned/streamed physical plan с сохранённым результатом и границей | Алгоритм требует полного state; нужен spill/distributed plan либо честный budget refusal |
| Новый retention/access режим | Профиль для уже реализованных permission/storage operations | Нет механизма enforce/remove/reconcile; строка policy не реализует его |
| Новый публичный claim | Композиция существующих admissibility predicates и projection | Новый вид authority/подписи требует contract decision и semantic checks |

Развитие descriptors не должно опережать исполнительную способность. Descriptor с `supports_retractions=true` является заявлением о возможностях; его пригодность устанавливает проверка реального пути. Пустое или неизвестное свойство не превращается в default positive. При этом discovery может сохранить новые facets, не принимая их в protected execution.

## 2. Descriptor — ссылка на возможности, а не исполняемый закон

Рекомендуемый descriptor находится у владельца расширения и связывает native source/protocol/schema/profile, зарегистрированную реализацию, resource envelope, supported operations, temporal/correction semantics, restrictions и необходимые verification resources. Это логическая спецификация; не все facets обязательны каждому источнику, а missing facet влияет только на действие, для которого она нужна.

Профиль состоит из связанных ресурсов — human specification, schema, mapping, validator, examples — с разными ролями. [W3C PROF, Note 2019-12-18](https://www.w3.org/TR/2019/NOTE-dx-prof-20191218/) полезен именно для описания этих связей, а не как доказательство conformance или обязательный формат PolicyOS. Его standing — Working Group Note.

Config не может сам назначить trusted issuer, заменить verifier, разрешить shell/network execution или сменить целевую unit law. Реализации устанавливаются через существующую controlled registration; resource content не становится import path. После регистрации capability negotiation проверяет фактическую совместимость producer, artifact reader и consumer, включая unknown/malformed cases. Декларативное добавление источника безопасно только внутри проверенного класса поведения.

Сравним варианты:

- **Рекомендуется:** расширять существующие owner registries и bridges; выделять общую библиотеку лишь для реально повторённого invariant. Преимущество — смысл и ответственность остаются там, где уже проверяются.
- **Единый GroundService с одной схемой:** легче показать единый API, но он забирает authority, time и status у предметных owners и быстро растёт в новый центр управления. Не рекомендуется.
- **Произвольные plugins с JSON и LLM dispatch:** даёт быстрое подключение, но скрывает semantics и privileges в конфигурации. Допустимо как изолированная candidate exploration, не как путь к protected claim.
- **Отдельный pipeline на каждый источник:** сохраняет локальный контроль, но размножает retry, retention, logging и admission bypass. Рефакторить повторяющийся механизм к одному владельцу, сохраняя source-specific contract.

## 3. Эволюция и retirement

Source version, payload schema, canonical codec, parser/model, method law, permission basis и projection rule version меняются независимо. Нельзя использовать один SemVer как доказательство их совместимости. Consumer выбирает exact profile и явно различает: understood as-is; supported transformation; candidate/raw only; unavailable. Это смысловые случаи, а не предложение очередного универсального enum.

Migration создаёт новый derived artifact и relation к старому, сохраняя allowed original и известные потери. Автоматическое обновление всех пользователей на `latest` запрещает корректный replay и смешивает case baselines. Новые задачи могут предпочитать новую версию по выбранной policy; прежние переходят через owner revalidation, если изменение materially affects use.

Retirement требует denominator активных consumers/retained uses и их обязательств. Отсутствие обращений в sampled telemetry не доказывает отсутствие исторических replay duties. План withdrawal содержит дату/условие, replacement, сравнение результатов, известные incompatibilities и последствия для unreplayable uses. Старый adapter не нужно держать доступным для произвольного исполнения: исторический replay запускается в подходящей ограниченной среде или честно отмечается недоступным.

## 4. Объём: разделить хранение, чтение и алгоритм

Для больших ресурсов предпочтительны immutable partitions/chunks и иерархические manifests. Root описывает selected snapshot, схему partitioning, completeness scope и child identities. Индекс membership/coverage нужен для запроса, но не должен заставлять каждый reader загружать всю коллекцию в память. Изменение granularity не меняет unit, temporal interval, row identity или порядок там, где он семантически значим.

Есть три разные проверки: целостность прочитанного member; принадлежность выбранных members согласованному snapshot; полнота denominator для обещанного результата. Проверка одного chunk не доказывает полную таблицу; проверка полного root manifest не требует повторно читать все bytes при каждом subset query, если membership и coverage действительно проверены и query scope это допускает. Эти гарантии и их origin должны быть видимы consumer.

Streaming parser не гарантирует bounded memory estimator. Joins, global sort, graph closure, дедупликация, training и некоторые exact statistics имеют собственную потребность в state. Physical plan должен объявить, где используется external sort/spill, bounded approximation, sufficient statistics или полная materialization. Approximation меняет метод и требует error contract; OOM нельзя «исправить» незаметным sampling.

Объём хранилища растёт вместе с нужными source versions и derivatives; dedup разрешён только при совместимых access/retention boundaries. Content hash не должен становиться межтенантным existence oracle. Tiering и eviction опираются на реальные retained uses и custody obligations, а не на возраст файла. Дорогие verification receipts переиспользуются лишь для того же проверенного predicate/input/profile; актуальность прав и public standing проверяется отдельно.

Новый table/object backend допустим как физический adapter, когда существующий путь не выполняет измеренное требование. В этой работе производительность не измерялась; выбор конкретного backend, paging representation или distributed engine остаётся implementation investigation. Не вводить инфраструктуру ради предполагаемого будущего объёма.

## 5. Исполнение и backpressure

Нужны разные бюджеты, а не один счётчик «стоимости»: remote requests/rate, CPU/memory, bytes/download/storage, concurrency, money, privacy exposure и human review. Единицы и owner каждого budget явны. Денежный ledger не подменяет compute permit; queue length не доказывает capacity внешнего учреждения.

Переиспользуется существующий runtime/control-store и family orchestration. Приоритизация различает custody-critical revalidation, работу текущей задачи, обновление discovery и optional enrichment. Это не фиксированный вечный порядок: policy учитывает срок обещания, stakes, время и стоимость; низкоприоритетные источники не должны незаметно голодать. Если система не способна поддержать обещанную refresh/currentness duty, это ограничивает публичное обещание.

Admission сначала резервирует разрешённый объём работы; worker проверяет budget/cancellation/permission перед защищённой операцией. Вложенные задачи получают ресурс через того же owner, освобождая permit при завершении и после подтверждённого termination. Не держать родительский scarce permit, ожидая дочерний из того же исчерпанного пула. Retry не создаёт новый независимый spend или новое право.

Срок и backoff зависят от source protocol: throttling, temporary network failure, invalid credentials, unsupported schema и invalid content требуют разных действий. Dead-letter запись — средство разбора, не terminal proof of absence. Reconciliation job пересматривает pending attempts, незавершённые releases, outbound events и consumer acknowledgments. Exactly-once external act не обещается, если источник не поддерживает подходящий idempotency/transaction contract.

Конкретный первый путь — extend `ControlPlaneStore`/`ControlWorker`, сохранив уже существующую транзакцию job/progress/event/outbox. Нужны durable ready-at/cooldown, ограниченный retry budget и fair selection по установленным provider/tenant scopes. Долгий backoff освобождает worker lease; короткие безопасные transient retries остаются в connector. Общие credentials требуют общего quota accounting, даже когда endpoints и tenants разные. Повтор attempt сохраняет logical intent, но новый live ответ становится новым наблюдением. Process-local one-use permit после restart заново разрешается у owner, а не восстанавливается из сериализованного токена.

Существуют три разные границы commit: внешний source effect; immutable artifact/page; наши SQL cursor/job/event/head. Нельзя объявлять их атомарными из-за SQL-транзакции одного владельца. Перед неоднозначным export/query effect сохраняется operation intent; после crash reconciliation проверяет доступные source operation ID, exact artifacts и consumer outcome. `mark-published` не доказывает ack или применение результата. Outbox допускает redelivery с idempotent consumer; orphan artifact без подтверждённой связи не становится admitted input. Автоматическая обработка ограничена известными producer manifests и их namespace, а не глобальным сканированием CAS.

Внешний durable workflow engine стоит рассматривать лишь при измеренном недостатке текущего owner: long-lived timers, multi-region recovery или неприемлемой сложности сопровождения. Это вариант физического исполнения, не новый владелец authority. В исследованном snapshot таких измерений нет; начинать с замены scheduler преждевременно.

## 6. Наблюдаемость без скрытого второго архива

Нужно три различимых слоя:

| Слой | Что хранится | Зачем и какая граница |
|---|---|---|
| Operational telemetry | timings, sizes, retry/rate/resource outcomes, opaque correlation | Диагностика; sampling допустим, это не полная evidence history |
| Durable lifecycle/audit records | commit/receipt refs, rule/version, protected action, transition, outcome, reconciliation | Восстановление и accountability; сохраняются по scoped retention, не зависят от trace sampling |
| Scientific/justification lineage | exact used inputs, transformations, warrants, alternatives, uncertainty, admissions | Ответ «почему этот вывод» и materially affected recomputation |

Логи по умолчанию не содержат payload, credentials, полные SQL/query text с персональными признаками или локаторы restricted sources. Public projection не раскрывает скрытый источник через hash/graph degree/error message. Metric labels имеют bounded cardinality; per-resource details идут в authorized records. Logging failure не должен давать ложный receipt успешного защищённого действия: сохраняется owner-native indeterminate outcome и выполняется reconciliation.

Полезные измерения: возраст последнего успешного **получения** и отдельно verification/admission; lag от source event до claim reaction; pending/partial releases; failed renewal of access; proportion unknown coverage для конкретного поиска; число affected uses с неподтверждённой реакцией; resource cost на единицу работы; покрытие deletion targets. Из этих метрик не строится универсальный trust score. Порог/SLO выбирается под обещание задачи, не назначается этим исследованием.

## 7. Когда оправдан рефакторинг или новый модуль

Рефакторинг оправдан, если два реальных пути независимо реализуют один invariant и расходятся: например, один проверяет chosen manifest view, другой берёт default; один повторно проверяет permission после retry, другой нет. Тогда consolidating owner устраняет класс bypass, а не только конкретный источник.

Новый узкий модуль оправдан после source census: нет подходящего владельца; обязанность лежит внутри PolicyOS signature boundary; она повторяется в разных семьях; можно дать ограниченный typed interface и доказать композицию. Возможные предметы такого исследования — transactional progress/commit bridge и source change→claim dependency reconciliation. Это **не утверждение об отсутствии** этих механизмов в репозитории и не разрешение создавать новый универсальный сервис.

Нужная единица поставки — working slice: declared input→реальный adapter→persisted artifact/receipt→consumer→реакция→API/audit view, с failure/removal witness. Scope включает mandatory generated/API/browser companions. Сначала один путь и adversarial siblings; затем новый источник того же класса добавляется без правки central orchestrator. Именно этот второй независимый источник проверяет free-grow свойство лучше, чем количество абстрактных интерфейсов.
