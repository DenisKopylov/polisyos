# Ресурсы, производительность и восстановление

Проект для реализации, 2026-10-21; продолжение [протоколов](05-implementation-protocols.md). Не benchmark, runtime acceptance или новое принятое SDD. Численные настройки выбираются по измеренному workload/backend; здесь нет обещаний throughput/RSS/RTO. [Инциденты](08-incidents-and-edge-cases.md) мотивируют механизмы, [атаки и поставка](10-adversarial-review-and-delivery.md) задают будущие различающие проверки.

## 1. Цель и архитектурный выбор

Оптимизировать стоимость **допустимого результата в нужной границе**, а не число обработанных строк. Считать отдельно CPU, resident memory, temporary/retained storage, I/O, сетевые запросы, очередь, денежный spend и обязанности сопровождения. Быстрый результат с потерянной отрицательной записью, иной population или просроченным permission — другой результат, а не ускорение.

Выбор для реализации: расширить native Runtime control store/worker и Fabric execution/admission seams до координации фактически общего resource pool; Core CAS отвечает за проверенное чтение/запись, предметные owners — за допустимую эквивалентность и approximation, Claim/DV — за invalidation/use. Существование общего cross-process CPU/RAM/disk permit в прочитанной карте не установлено: connector-local permit, bounded active concurrency и job lease не доказывают этот контракт. Generic общий permit пока не установлен; state его конкретной цепочки определяется наличием producer/consumer/bridge, а не только отсутствием проверки. До allocation/admitted chain это `absent/unallocated`; existing endpoints без связи — `bridge_missing`. Уточнение расширяет существующих owners, не вводит второй scheduler или universal budget-token authority. Денежный ledger не становится compute permit; priority задачи не становится правом её исполнить.

### Статические опоры и границы

C = `635413bcd1bd1d7e7b829d9123765e28e6bf23d6`, пути относительно `policy-engine/src/polisyos/`. Перед реализацией перечитать delta текущей ветки; это не measured OOM или claim о всём runtime.

| Path@C / символ | Что действительно видно | Следствие для slice |
|---|---|---|
| `fabric/data_plane/orchestrator.py`, `LocalAsyncExecutionBackend.execute`, `run_partitioned_ingestion` | Jobs, gather wrappers и results представлены списками; semaphore ограничивает активное выполнение | Bounded active concurrency не ограничивает общий queue/result state. Нужны paged intent traversal, bounded in-flight window и persisted result refs с affected callers |
| `core/artifacts/store.py`, `ArtifactStore.open_member` | Под read lease хешируется весь selected member, даже при prefix read | Bounded RSS не равно sublinear I/O. Учесть полную verification cost; не заменить hash-проверку чтением первых bytes |
| `runtime/http/services/control_plane_store.py`, job transaction / outbox; `control_worker.py` | Есть canonical execution/state seams; [карта](01-reuse-map.md) не устанавливает полный resource-aware scheduler | Сначала extend существующую admission/execution границу, не создавать автономный lifecycle daemon |
| `fabric/connectors/sources/http_base.py`, `HTTPResilienceProfile`; `fabric/data_plane/evidence_journal.py`, live permit | Connector-local retry и process-local permit имеют собственные границы | Общий provider quota/retry budget должен охватывать реально разделяемый scope; после restart новый resolve, не сериализованный allow |

## 2. Ресурсный контракт стадии

До допуска дорогой стадии owner связывает selected input/root/profile, physical operator и exact engine/config, ожидаемый диапазон cardinality/width/skew, фактически поддержанные spill/cancel/checkpoint, потребляемые ресурсы и результат при превышении. Это поля существующего plan/intent или узкое расширение у owner, не обязательный новый public DTO.

Различать **estimate**, **reservation** и **enforced limit**. Sample или descriptor помогает выбрать plan, но не доказывает upper bound. Если decoder/engine нельзя ограничить, его unknown nonspillable state учитывается при выборе изолированного runner/меньшей допустимой задачи; нельзя обещать hard memory cap одной настройкой engine.

Логика admission для одного shared host/pool:

`fixed/shared resident + Σ admitted private peak reservations + safety/completion reserve ≤ effective process/host allowance`.

Вместе с этим требуется disk budget на текущие outputs + spill + checkpoint + одновременно живые old/new generations + допустимый recovery запас. Shared buffers учитываются один раз по фактическому владению, IPC copies — отдельно. Это бухгалтерская модель, не измеренная формула RSS и не замена runtime enforcement. Page cache, allocator overhead, Python objects и native libraries не исчезают из потребления от отсутствия в счётчике конкретной библиотеки.

**Резерв завершения** нужен для bounded checkpoint/abort outcome, durable invalidation и корректного release. Его размер выводится из maximum supported transition и проверяется для deployment. Резерв не бесконечен и не позволяет обещать запись при физической потере носителя. Если решающий journal/store недоступен, protected positive прекращается; cached green не становится emergency fallback. Не строить второй неучтённый журнал в свободном temp directory.

Maximum здесь охватывает **все одновременно допущенные terminal transitions**, а не одну обычную квитанцию. Либо зарезервировать их worst supported fan-in, либо bounded terminalization lane с очередью и учётом всё ещё живой памяти ожидающих stages. Admission запрещает overcommit этой границы. Reserve реально enforced в используемых pools, а не только строка accounting. Fault при превышении ordinary capacity должен оставить доступным именно этот measured terminal path; physical loss/control-store outage остаётся явно неподдержанной гарантией записи.

Вложения получают ресурсы у того же реального capacity owner. Проверяется **транзитивная wait/resource dependency**, не только захват всех permits: parent с 60 из 100 units уже блокирует awaited child, которому нужно 50. До parent start резервируется supported parent+descendant peak либо parent checkpoint/park реально освобождает overlapping capacity перед ожиданием. Нельзя synchronously ждать durably deferred child, удерживая ресурс, необходимый ему для прогресса. Dynamic nesting допускается лишь в bounded плане; неизвестный descendant расход не выдумывается. Суммировать outer workers × внутренние threads/processes и native state; один outer permit не ограничивает внутренний BLAS/engine fanout. Не освобождать reservation по lease timeout, пока старое исполнение может реально продолжаться; fencing защищает запись, но не останавливает расход RAM/CPU.

### 2.1. Admission handshake и восстановление reservation

Existing control store выбирает due intent и **следующую bounded stage**, а resource owners подтверждают собственные ограничения. До дорогой работы: try-reserve в стабильном порядке → при любом отказе release уже полученных transient claims → durable defer с due/reason. Не ждать другой scarce resource, удерживая предыдущие. Intent/attempt identity связывает reservations и outcome; crash после частичной reservation требует owner reconciliation/fence, прежде чем ёмкость считается свободной. Нельзя вывести cross-process cap из process-local semaphore.

Remote quota, которую нельзя резервировать, проверяется при вызове; denied call освобождает тяжёлые local claims и оставляет due retry. Долгий remote job получает stable step/effect ID, затем локальный worker освобождается; remote consumption остаётся учтённым до подтверждённого результата/cancel. Это не distributed transaction с provider и не гарантия его доступности. Неизвестный исход не повторяется вслепую.

У stage различаются `not_before`, useful-until/freshness, attempt wall deadline, provider timeout, permit lease и retention. Использовать owner clock/monotonic elapsed time для длительности; persisted civil/effective time не заменяет duration clock. Clock uncertainty не разрешает продлить permission. Completion reserve не выдаётся обычной работе, если его нельзя гарантированно вернуть; cooperative cancel без подтверждённой остановки такую гарантию не даёт.

Hard-cap promise требует действительного enforcement, включая native/out-of-engine allocations. Где это невозможно, не обещать такой envelope: использовать уже поддержанный изолированный bounded probe/другой plan либо остановить именно эту execution с причиной. Это operational boundary, не доказательство математической/эмпирической правильности результата. Resource unknown не останавливает unrelated exploration; candidate label тоже не разрешает неограниченный расход shared host.

## 3. Порции, обратное давление и spill

### 3.1. Bounded execution window

Предпочтительный путь: paged intents → получить порцию лишь под доступную reservation → bounded decode/transform → durable result/member receipt → продвинуть acknowledged cursor → отпустить ресурсы. Очередь в памяти содержит ограниченные descriptors/refs, не весь corpus и не все closures/futures. Result stream передаёт persisted refs, не собирает весь output list в coordinator.

Backpressure проходит до source polling/fetch. Очередь ограничивается и item count, и bytes/work estimate; один record может быть больше целой нормальной batch. Отдельные пределы нужны на сжатый input, распакованный output, nesting, словари, column width, отдельный record и CPU разбора. Не доверять Content-Length или remote declared size. При невозможности безопасного продолжения — exact quarantined/partial outcome; нельзя молча пропустить «плохие» observations и сохранить прежний completeness/estimand.

Batch size подбирается по bytes и operator state, а не только row count. Адаптация не меняет logical ordering/duplicate/null semantics. Для source без возможности pause/resume сохраняется фактическая граница capture loss/partial; локальное давление не создаёт replayability внешнего API.

### 3.2. Physical plan и трудные operators

| Механизм | Предпочтительная оптимизация | Существенный крайний случай |
|---|---|---|
| Scan/parse | Projection/filter pushdown, bounded columnar batches, поздняя materialization | Фильтр меняет population/negative-query coverage или раскрывает restricted existence |
| Hash join/group | Partitioning, bounded hash state, spill; plan по skew/width | Один hot key/огромная группа не дробится обычным hash partitioning; join multiplicity взрывает output |
| Sort/window | External sort с ограниченным merge fan-in и измеренным temp budget | Stable ordering/collation/NULL/tie semantics load-bearing; нельзя снять ORDER BY ради экономии |
| Large document/archive | Потоковый decode с limits и bounded parse unit | Compression bomb, один огромный token/field, recursive expansion, hostile external references |
| Graph traversal | Disk-backed frontier/visited state, scoped query, versioned partial frontier | Cycles/dense join/closure не получают bounded complexity от streaming input |
| Model/global estimator | Explicit physical method plan; sufficient state только при доказанной достаточности | Выборки/скетчи/обрезанные covariates меняют вопрос или uncertainty |

Доступная [документация DuckDB](https://duckdb.org/docs/current/guides/performance/how_to_tune_workloads), разделы Larger-than-Memory и Limitations, предупреждает: несколько blocking operators и некоторые aggregate states могут исчерпать память даже при поддержке spill. Это основание проверять **actual operator/backend version**, не отказ от out-of-core и не обещание о PolicyOS.

Spill — managed derivative с разрешённым namespace, правами, ключами и retention, а не произвольный plaintext temp. Reserve disk до начала stage; при pressure уменьшить concurrency/порцию, выбрать совместимый plan или остановиться с checkpoint. Нельзя продолжать write до ENOSPC, надеясь затем сохранить receipt. Нельзя удалять pinned roots, чужие outputs или ценные данные для продолжения. Из этого проекта не следует разрешение на локальную уборку.

Zero-copy — свойство конкретной пары representation/consumer и lifetime, не название формата. Retained view может удерживать большой parent buffer; IPC/strides/dtype conversion создают copies; лишний zero-copy pin иногда дороже компактной разрешённой копии. Release следует actual buffer ownership, не завершению Python-функции.

[Arrow C Data Interface 18.1](https://arrow.apache.org/docs/18.1/format/CDataInterface.html) прямо задаёт sharing внутри процесса и release callbacks; это не протокол persistence/межпроцессной custody. [Spark 4.0.2 AQE](https://spark.apache.org/docs/4.0.2/sql-performance-tuning.html) показывает split/replicate для skewed join; он перераспределяет работу, но не уменьшает истинную many-to-many cardinality. [Velox memory/spill design](https://facebookincubator.github.io/velox/develop/memory.html) — пример native pool/arbitration, не выбранная зависимость PolicyOS или обещание поддержки любого operator.

## 4. Сокращать повторную работу без ослабления доказательства

| Уровень повторного использования | Binding и безопасная граница |
|---|---|
| Raw bytes / decode | Exact immutable generation, codec и relevant parser profile; permission решается заново для use |
| Physical fragments | Partition/member identities и selector; manifest/profile/visibility сохраняются, foreign prefix proof не whole-member proof |
| Semantic assessment | Exact proposition/relation, selected inputs, method/law/version и context; common bytes недостаточны |
| Search/index result | Corpus generation, visibility, query/profile, coverage и ranking configuration; cached no-hit не universal absence |
| Claim projection | Head, materially enrolled generations, audience, current-read cut и expiry; workflow success не cache validity |

Verification cache полезен только при установленных immutability/custody assumptions и именованном predicate. mtime/path/ETag не заменяют content identity по умолчанию. Для repeated prefix reads сначала переиспользовать допустимый bounded representation/partition layout; если нужен новый range/Merkle proof, это отдельный Core contract с producer/consumer/migration, а не отключённый full hash. Не менять прежние artifact IDs или считать перекладку файлов доказательством равенства output.

Рецепт cache key выводится из **полных фактических аргументов переиспользуемой owner-функции**, включая её build/verifier/rule, а не из вручную подобранных удобных полей. Ambient environment, model alias, locale, clock, mutable registry и remote lookup сначала становятся bound input либо делают результат непригодным для exact cache. Рецепт тоже versioned. Gate фиксирует provenance решающего predicate по P37; recomputed estimate остаётся estimate, не доказанным upper bound. Cache hit не создаёт недостающее основание.

Для alias binding сохраняется **resolved immutable target**, а не строка `current/latest`; для learned selector — использованная memory/search generation и policy/profile. Изменение неиспользованной модели не invalidates этот cache. Если dependency нельзя bound, exact reuse выключен для данного результата либо результат остаётся привязан к своему исходному frontier. Не требуется повторно хешировать весь corpus при каждом hit.

Single-flight объединяет только одинаковую работу внутри совместимого access/purpose/visibility domain. Каждый waiter повторно проверяет свой допуск и scope перед выдачей. Отмена одного waiter не уничтожает нужный другим результат; owner отменяет общий producer, когда больше нет допустимых uses/обязательств и termination реально установлен. Отзыв доступа не делает запрещённый результат доступным из already-completed future.

Negative membership filters допустимы как ускоритель только при свойстве no-false-negative для выбранного exact поколения/предиката; approximate search без такого свойства даёт candidate frontier. Позитив filter требует exact resolution. Индекс, не включивший новый запрет, не может поддерживать зелёный current claim даже при отличной средней recall.

Это правило относится только к доказанно полному **контролируемому набору** и поддержанному membership predicate. Отсутствие элемента в таком наборе не доказывает отсутствие нормы/исследования во внешнем мире. Bloom-like механизм с неустановленным rebuild/update protocol не обладает нужным свойством лишь по имени алгоритма. Visibility filtering и authorised no-hit surface остаются обязанностью reader.

Incremental computation выбирается по **фактически принятому change class** и доказанной update law: supported append может обновлять summary без reread всей истории, даже если метод не умеет retract. Неожиданная correction/retraction/backdate сначала invalidates affected use и идёт по exact recomputation/reconciliation; не оставляет current green. Иначе пересчитать affected partition/целый метод либо ограничить вывод. Min/max, joins, quantiles и nonmonotonic reasoning не получают inverse update универсальной формулой. Счётчик изменений/совпадение schema не доказывают достаточность incremental state.

## 5. Metadata и каскады — тоже нагрузка

Нужно учитывать descriptors, manifests, relation edges, negative dependency scopes, journal offsets, dedupe entries, pending receipts, leases, warnings и метрики. Миллион маленьких members способен перегрузить metadata path раньше payload store. Paged manifests/indexes и bounded fan-in применяются с exact coverage/order/hash semantics; pagination не должна скрыть members или заменить complete denominator sampled page.

Два шага реакции: **durable coarse invalidation относящегося scope**, затем bounded precise re-evaluation. При событии не запускать немедленно по job на каждый dependent и на каждого sibling. Сохранить dirty scope/frontier, дедуплицировать одинаковую работу и выдавать bounded slices. Coalescing разрешён для повторного вычисления конечного состояния, но не стирает source/action history и transient forbidden interval.

Generation granularity выбирается по реальной материальной зависимости. Coarse scope даёт лишние rechecks внутри scope; несвязанные source scopes не должны блокировать всё. Пересмотр на generation g не очищает dirty marker для g+1. При непрерывных изменениях нельзя обещать безусловный fixed point: либо краткий source-owner cut, согласованный read snapshot/ограниченная view, либо объявленная currentness limitation. Historical доступ остаётся при actual rights; freshness не добывается бесконечным replay.

Журнал ограничен. Enrollment фиксирует replay floor и lag policy; lagging consumer не удерживает бесконечно все WAL/events. До legal/operational expiry он либо догоняет, либо owner устойчиво отмечает discontinuity и требует resnapshot/reconciliation. Advance floor не переписывает complete flag. Retention не продлевается сверх допустимого права ради удобства consumer; отсутствие нужной истории ограничивает replay/current claim. Control receipts тоже имеют разрешённый срок и bounded payload.

Это реальный trade-off: [PostgreSQL 17](https://www.postgresql.org/docs/17/runtime-config-replication.html#GUC-MAX-SLOT-WAL-KEEP-SIZE) допускает неограниченное удержание WAL slot либо cap, после которого lagging consumer может потерять продолжение. [etcd 3.6 recovery](https://etcd.io/docs/v3.6/op-guide/recovery/#revision-difference) описывает rollback revision и принудительное обновление watch-driven caches после restore. Использовать аналогичное различение gap/rebuild, не копировать чужой offset или revision-bump алгоритм как универсальную semantics.

## 6. Рабочий режим, перегрузка и recovery

Отделить bulk acquisition/rebuild/search от коротких обязательных control transitions: invalidation, permission fence, cancel/reconcile, fresh limitation projection. Это resource classes у существующего owner, не новые product status/authority tiers. Для небольшого deployment достаточно bounded queues/reservations в одном процессе; независимые failure domains вводятся при доказанной потребности, не ради набора сервисов.

Overload policy именует приоритет, fairness/aging, admission threshold, queue expiry и terminal treatment. Нельзя незаметно выбросить pending revocation, incomplete capture или custody duty по общему TTL. Старую costly exploratory query можно отменить по её task policy; обязанность сопровождать подписанный claim остаётся и должна получить truthful surface. Background repair не имеет права обнулить ресурсы интерактивного/служебного читателя.

Retry budget общий для logical operation и цепочки слоёв: connector+worker+caller не умножают attempts бесконтрольно. Error class определяет retryability; credential/schema/semantic refusal не transient timeout. Cooldown относится к реальному shared provider scope, retry uses jitter; новый credential/endpoint не обход quota. Failure diagnostics bounded/deduplicated; не сохранять payload/core dump на каждую повторную ошибку. Полный deciding receipt нужен для выбранной проверки/операции, а не бесконечный лог каждого однотипного retry.

Диагностика: низкокардинальные counters/histograms по owner/reason/resource class, отдельные разрешённые trace refs; не metric label на каждый artifact/selector/человека. Отслеживать oldest first-attempt age отдельно от retry age, due lag, dirty-scope age, retained-generation count и control-store pressure. «Queue empty» не полнота, «queue durable» не своевременность. [Google SRE](https://sre.google/sre-book/handling-overload/) разбирает изменчивую стоимость запросов и retry budgets; [AWS queue guidance](https://d1.awsstatic.com/builderslibrary/pdfs/avoiding-insurmountable-queue-backlogs.pdf) — age/backlog/fairness. Это operating guidance, не sizing или PolicyOS SLO.

При снятии ограничения очередь не стартует целиком: reconciliation → controlled ramp → backlog drain под оставшейся ёмкостью. Общий signal «здоров» не означает свободный DB/metadata/write budget. Autoscaling вычислителей ограничивается downstream admission; дополнительные workers могут усилить перегрузку. Нельзя считать container started или lease выданной единицей продуктивной capacity.

**Cold recovery включает весь путь:** получить backup → проверить exact content/decoder → распаковать/перестроить → reconcile post-backup control history → переключить допустимый root → догнать зависимые очереди/replicas и проверить fresh consumer. Backup-job success не доказывает этот путь. Назвать retained root и реально проверенный масштаб, RPO/RTO лишь если измерены в требуемой границе. Recovery требует CPU/I/O/disk/memory вместе с serving; «основной store вернулся» не закрывает истёкшие/потерянные задания.

Recovery access и truthful limitation surface не должны без проверки зависеть от той же сломанной очереди/credentials/catalog. Не вводить privileged bypass: использовать уже разрешённый защищённый recovery path и действующие owners. Если его нет, фиксировать конкретный dependency cycle и ограничить promise; PolicyOS не становится аварийным администратором внешнего provider.

При total control-store loss возможен только ordinary unavailable, если API вообще достижим; durable reason-specific projection не обещается до восстановления. Anti-rollback witness проверяется относительно **всего реально откатываемого closure**, включая Claim/public action histories, а не только другого имени database. Если все локальные markers вернулись из старого backup и свежесть вне этого closure не установлена, restore остаётся quarantined. Current rights после regrant не воскрешают старый withdrawn claim head.

## 7. Эквивалентность и исследовательская свобода

Нужно различать: bitwise replay; эквивалентность по объявленному numerical tolerance; один statistical estimand при новом approximation error; новый candidate question. Reduction order, parallel execution и dtype могут менять numeric output без смены mathematical expression. Выбранная guarantee закрепляется method/backend owner, а не правилом «прошло с epsilon». Не менять sign/unit/population/coverage под видом physical optimization.

Approximation, ANN, sampling или сокращение frontier могут быть полезны в exploration/VOI. Они сохраняют actual sampling/selection mechanism, seed где применимо, covered domain, uncertainty/error contract и основание stop. Performance-driven missingness не объявляется случайной. Дешёвый first stage может находить кандидатов; дальнейший authority-bearing consumer проверяет свой полный predicate. Если задача требует полного denominator/отрицательного вывода, нельзя заменить его top-k и общим disclaimer.

**Некалиброванный candidate-only поиск разрешён:** recall/error могут быть `not_established`; достаточно прав, supported resource limits, actual selector/index/model, searched scope/frontier и stop/budget trace. Выдача candidate для следующего исследования не требует inference-grade calibration. Количественная uncertainty/error guarantee нужна там, где на ней основан inferential/coverage/threshold claim. Диагностическое «этот запрос ничего не вернул» допустимо, обобщённое отсутствие — нет. Условие неизвестной recall передаётся дальше, а не превращается в запрет поиска или в нулевую ошибку.

Если разрешённый numerical/error interval пересекает policy threshold, бинарный verdict не устойчив: exact/stronger refinement либо scoped unresolved result. Sampling требует своего frame/selection model; sketch — update/merge/error contract; adaptive selection — корректной для выбранной inference процедуры. Ноль, missing, censored, suppressed и unobserved не подменяются ради sparse representation. Это допускает более дешёвые исследования с честной границей, а не требует exact computation для любого candidate.

Учить стоимость, selectivity, skew и успешность physical plans можно через существующую memory/search influence. Модель стоимости даёт estimate и candidate plan, не authority и не право превысить limit. Ошибка модели ведёт к bounded replan/stop; feedback должен отличать cheap success от failed/partial/skipped expensive cases, чтобы learning не оптимизировал только «удобные» источники.

Если learned generation материально определяет selection для admitted use, use enrolls именно её и соответствующий procedure/profile как dependency, даже если training source отсутствует среди selected evidence refs. Применимость source restriction к derivatives решает rights owner; при установленном material effect memory owner ограничивает/переоценивает generation, Claim/DV реагирует на affected uses. При неизвестной partitionable influence допустима coarse invalidation. Удалённый source нельзя бессрочно удерживать ради trace; отсутствие доказанного unlearning/replay отражается как ограничение, не как автоматическое «модель очищена» и не как автоматический отзыв всех независимых фактов.

## 8. Что измерять при будущей реализации

Один controlled wave после freeze/reviews, не здесь. Выбрать representative strata: ширина строк и rare huge row, skew, число partitions/artifacts/dependencies, churn/retractions, remote latency/429, concurrent duties, warm/cold cache, old/new generations, cold restore. Показать точные input/source/backend/limits и полный denominator профиля; synthetic mechanics не authentic adequacy.

Измерять actual stage RSS/peak, вне-engine allocation, CPU/wall, I/O/hash amplification, bytes in-flight/spilled, temp high-water, queue/age/lag, retries per logical operation, cancellation drain, invalidation-to-reader latency и remaining unknown effects. Разделять successful useful output, partial, refusal и ERROR. Peak процесса и сумма непересекающихся stage peaks — разные величины. Exit 137/−9 без диагностики не доказанный OOM.

Сравнение планов требует одинаковой semantic задачи и admissible inputs, не только одинакового filename. Проверить worst supported boundary и свойство отказа за ним; цифры чужой платформы не переносить как sizing PolicyOS. После measurements выбрать operator batch/window/parallelism/reserve и документировать достигнутый envelope, деградацию и стоимость контроля. Free grow проверяется вторым реальным источником поддержанного класса, включая pressure/change/recovery.

Pattern pass: P01/P02/P27 — existing-owner execution; P05/P10/P14/P25 — оптимизация не повышает scope/authority; P07/P08 — pin/cut/replay; P13/P31 — bounded единый механизм; P29/P35/P37/P38/P40 — actual denominator и distinguishing probe. Runtime signals UNRUN. [Статус реализации](../12-acquisition-storage-and-deployment.md#как-читать-итоговую-версию) назначать точной цепочке; отсутствие исполнения не доказывает наличие producer/bridge.
