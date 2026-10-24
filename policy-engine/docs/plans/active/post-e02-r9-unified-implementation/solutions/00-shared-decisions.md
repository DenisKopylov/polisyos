# Согласованные инженерные решения

Актуальная карточка задачи = исходная карточка + **все присутствующие `*_extension`** в [tasks.json](../tasks.json) и mirrored solution manifest, а также текущие acceptance/stage requirements. Имена R14/R15/R16/R17/R19 обозначают происхождение дополнений, не закрытый список для reader. Чтение только старой prose-карточки не даёт полного assignment. [R15 implementation guidance](14-adaptive-trajectories-and-studies.md) и [method profiles](15-technical-method-lifecycle.md) раскрывают новые обязанности; ссылки на профили не означают обязательное внедрение всех технологий.

Эти рекомендации выбирают общий механизм для нескольких задач. Они конкретизируют [уже распределённых владельцев](../architecture/01-integration-boundaries.md), не создавая новый центральный subsystem. Ратифицированные AD-E02-01–06, Fabric N818 и SDD сохраняются. Задачи используют соответствующую строку, а затем доказывают свой фактический consumer path.

## S01. Расширяемость через native contracts, а не центральный список возможностей

CAP-01 и CNT-02 используют существующий корпус, индексы и Fabric/native registry. Discovery возвращает candidates; executable conformance и purpose-bound use admission проверяются отдельно. Версионированное описание расширения содержит необходимые owner semantics, поддерживаемый transport/operation, inputs/outputs и правила совместимости. Центральный policy-design runtime потребляет общий контракт, не получает `if provider == ...` для каждого нового источника. Произвольные плагины не становятся trusted verifier по самодекларации.

Полезная аналогия — версии custom facets OpenLineage: они позволяют расширять metadata без превращения каждого расширения в core schema. При этом обновление facet может заменять предыдущее значение; это не доказательство append-only истории или admissibility. Нужные история и admission остаются у PolicyOS owners. [OpenLineage facets](https://github.com/OpenLineage/OpenLineage/blob/main/website/docs/spec/facets/facets.md).

Предпочтительны небольшие типизированные extensions существующего owner. Отдельный plugin framework допустим только при доказанном отсутствии нужной extension boundary; тогда предъявляются isolation, conformance и retirement дублирующего пути. Free-grow проверяется новым корректно реализованным ресурсом, который не требует central-code diff, и фактическим consumer использованием; число записей в registry этого не доказывает.

## S02. Сначала минимальная допустимая representation, затем условная публикация head

CAP-02 владеет capture/representation, LIF-03 — fencing frontier. Рабочая форма: immutable permitted artifact либо минимизированный lawful receipt → semantic validation → conditional head/frontier commit в существующем owner. Для paged/resumable источника фиксируется завершённость именно выбранного протокола; offset сам по себе не доказывает полноту. Ошибка после внешнего эффекта не равна отсутствию эффекта. Нельзя продвинуть frontier до сохранения необходимого результата.

Iceberg показывает применимость immutable metadata, atomic pointer swap и повторной проверки предпосылок при конфликте. Заимствуем этот принцип, не делаем Iceberg обязательным и не переносим его table-level guarantee на несколько PolicyOS stores. [Iceberg reliability](https://iceberg.apache.org/docs/1.9.2/reliability/).

Если native транзакция охватывает все нужные local effects, использовать её. Если нет — явные durable intent/reconcile и безопасное состояние неизвестного исхода; не обещать глобальную ACID/«exactly once». Выбор atomicity зависит от свойства: linearizable single head не доказывает сериализуемость multi-object transition. [Jepsen consistency models](https://jepsen.io/consistency/models).

## S03. Admission связывает содержание, правило и конкретное использование

LIF-01 расширяет существующий semantic evidence/legal/scientific owner; CAP-03 передаёт ему exact selected content и use context. Проверяются реальные subject/population/estimand/unit/jurisdiction/purpose, provenance verifier и версии правил, насколько они обязательны для данного claim type. Один universal mega-DTO и один общий boolean `verified` не предлагаются. У разных native artifacts остаются разные правила, а bridge переносит необходимые semantics без потерь.

Отделить schema validation от runtime authorization полезно и в policy engines: Cedar документирует отдельный validation API и зависимость проверки от schema/application contract. Это аргумент за различение проверок, не за замену существующего OPA/native owner на Cedar. [Cedar validation](https://docs.cedarpolicy.com/policies/validation.html).

Неизвестный context допускает честно ограниченный candidate, если это разрешено соответствующим native contract. Защищённое использование не получает неизвестное значение через default. Подпись подтверждает атрибуцию подписанному утверждению, но не компетенцию подписанта, истинность модели или полноту основания автоматически.

## S04. Currentness — локальная проверка relevant generation, а не глобальная остановка

LIF-02 использует существующие Claim Ledger, Decision Validity и публикационный owner; CAP-04 поставляет source-specific events либо явно ограниченные observation-cut receipts. Enrollment включает selected source cut и устранение окна event-before-enrollment. Publication/use сверяет relevant generations и зависимости; stale reverse index не становится разрешением на старое green. Новое событие делает affected conclusions требующими reconciliation, сохраняя историю и точную временную границу.

Разные times — событие, действие нормы, наблюдение, admission, публикация — не объединяются в один timestamp. Нельзя округлять expiry/legal time ради batching. Индекс, reverse map и cache ускоряют поиск, но не определяют authority. Если полного change feed нет, заявляется измеренная bounded freshness и соответствующий cutoff; polling не выдаётся за отсутствие неизвестных изменений.

## S05. Длительный внешний эффект — intent, attempt, effect и outcome

LIF-04 сохраняет один ControlPlaneStore/worker owner. Durable intent и attempt token записываются до внешнего эффекта; external idempotency/reconciliation используется только в той гарантии, которую реально поддерживает provider. Retry узнаёт об уже выполненном эффекте, а не создаёт второй. Lease expiry и cancel-request не доказывают остановку процесса или remote action. Состояние неизвестного исхода требует reconciliation или честного refusal, а не произвольного success/failure.

Outbox, если он нужен для существующей transactional boundary, — часть этого owner; не новый брокер обязательный для всех. Доставка может быть повторной, а effective state transition должен дедуплицироваться по семантическому operation identity. Один и тот же URL или совпавшее payload не обязательно означают ту же операцию.

## S06. Rights следуют за use, copy и restore

LIF-05 определяет управляемую границу копирования, материализации, readers, spill, cache и restore; CAP-06 и OPS используют её. Сохранение raw content — отдельное право, не следствие успешного fetch или наличия hash. Для query-only paths сохраняется только допустимый receipt; невозможность повторить вычисление без запрещённых bytes остаётся точным ограничением replay. Источники могут требовать запрета на раскрытие даже самого locator/hash — минимизация применяется и к receipts.

Rollback к старому бинарнику не возвращает отозванные права. Recovery должен прочитать актуальные revocations до допуска восстановленных данных. Удаление head/unlink не доказывает physical erasure; уже раскрытые bytes нельзя «отозвать» сменой статуса. Unknown provider custody не превращается в доказанную deletion. Состав actual sinks проверяется по выбранной topology, не только по предположению API клиента.

## S07. Bounded processing и backpressure вместо фиксированного «быстрого стека»

LIF-06/OPS-08 используют принятый resource owner; compute permits E02 не объявляются автоматически RSS/spill budget. Бюджет учитывает native allocation, сериализацию, fan-in, одновременное завершение, provider-principal quotas и reserve для custody/control. Admission отвечает за фактически ограничиваемый ресурс; нельзя выдавать конфигурационное число за enforced property. Parent, удерживающий permit и ожидающий children, должен иметь доказанное правило reentrancy/release, иначе serial inner execution безопаснее второго scheduler.

Первый выбор — projection/filter pushdown, streaming/chunking и bounded fan-in в уже используемых readers. Materialize прямо связывает раннее удаление ненужных columns/rows с экономией maintained state; одновременно maintained indexes занимают память. Это поддерживает сравнение точных затрат, а не обязательное внедрение incremental engine. [Materialize optimization](https://materialize.com/docs/transform-data/optimization/).

Новый paged representation, columnar backend, incremental view или distributed engine рассматривается после измерения реального floor/crossover на допустимом workload. Сравнить peak RSS/native buffers/spill, p95 latency, throughput, amplification и recovery cost; здесь численные обещания не выданы. Semantics completeness/hash/time/order сохраняются либо различие явно квалифицируется.

## S08. Lineage не заменяет независимость и смысл

LIF-07 хранит actual computational/semantic/model/selection/right dependencies, включая set-valued и negative dependencies, если они влияют на claim. Два reports с одним underlying cohort не становятся двумя независимыми основаниями. Uncertain influence остаётся uncertain. Caches ключуются необходимой semantic dependency identity; неизменный payload не гарантирует неизменных right/profile/rule.

Incremental invalidation допустим, когда владелец может доказать полноту affected set и consumer действительно сверяет его generation. При неизвестной полноте — консервативный affected scope, а не глобальная остановка всего корпуса по умолчанию и не silent stale reuse. Operational lineage graph не является отдельной SCM и не создаёт причинное знание из порядка вычислений.

## S09. Одна world-model система, несколько обоснованных моделей и guarantees

GY O1/O2/O3 и CNT-05/06/08 сохраняют разделение подтверждения, exploratory hypotheses, нормативного выбора и допустимого действия. Ратифицированный B01 допускает конкурирующие/неопределённые causal completions. C01 допускает validated exact joint witness для конкретного свойства наряду с simulation; сумма pairwise эффектов им не является. C02 допускает обоснованные inference profiles, сохраняя их разные guarantees. Native O1 Bayesian updater — целевой профиль, а не разрешение активировать его. WP-01/WP-02 сейчас запрещают operative posterior mutation: live producers и concrete activation packet готовятся внутри, actual scoped activation выдаёт компетентный principal. C02 не снимает этот запрет. Подробнее — [границы решений](decision-clarifications.md).

Существующие AD-E02 method-output/unit и inference решения используются как contracts. Unit consistency не даёт empirical calibration; posterior не даёт политического мандата. Политическое предпочтение и метод измерения показываются вместе с alternatives/sensitivity, без скрытого scalar collapse. O2 hypotheses проходят claim-type-qualified intake: effect-posterior route сохраняет O1/AS3/WP, structural route — [CNT-06/native method → единственный GYD-12 writer](18-structural-world-learning.md). O3 write-back требует собственного действующего правила и чтения следующим циклом; слово confirmatory не заставляет structural evidence принимать форму O1 posterior.

## S10. Atlas проецирует native смысл и реальные ограничения

UI owners используют canonical DTO/OpenAPI/client family и существующую grammar. Отдельный frontend authority calculation запрещён. DS16 показывает exact/set-valued/unknown/incomparable значения согласно всем исходным algebra cases; сортировка или badge не может делать их сравнимыми сама. History, audience, translation, accessibility и MACHINE/export входят в тот же complete surface footprint.

Выделенный владелец меняет generated family одной согласованной партией. Независимые UI consumers могут готовиться по exact interface agreement, но production claim требует реального provider и fresh reader. Migration estate завершается actual successor use и доказанным retirement legacy пути, не обновлением registry status.

## S11. Наблюдаемость отдельно от deciding evidence

OPS и native audit owners разделяют малокардинальные операционные метрики, диагностические traces и обязательные deciding receipts. OpenTelemetry ограничивает cardinality, агрегируя overflow; общая сумма сохраняется, но измерения теряют детализацию атрибутов. Поэтому такой aggregate не подходит для доказательства полного per-tenant/per-claim predicate. [OpenTelemetry metrics](https://opentelemetry.io/docs/concepts/signals/metrics/).

Неограниченные source IDs, user IDs и секреты не становятся metric labels. Sampling диагностики разрешён только при сохранении обязательного evidence path и честном раскрытии потерь. Deciding receipt содержит то, что нельзя вывести заново из retained refs; source copies и несколько derived dumps не хранятся рядом без причины.

## S12. Deployment profiles расширяют существующие owners

OPS-02 начинает с bounded local profile; private hybrid, remote/distributed и air-gapped profiles активируются по собственным условиям. Общий code path остаётся тем же, где его гарантия переносится; права, storage atomicity, authentication, clocks, recovery и resource constraints проверяются на фактической topology. Бренд filesystem, облака или Kubernetes не является readiness.

Kubernetes различает extension configuration и executable controllers, а также предупреждает против использования custom resources как application data storage. Это полезная граница control/data planes; Kubernetes не становится обязательной платформой PolicyOS, и foundation corpus не помещается в его API. [Kubernetes custom resources](https://kubernetes.io/docs/concepts/extend-kubernetes/api-extension/custom-resources/).

После source freeze независимые review и одна composed wave проверяют выбранные profiles. Task-local evidence не переносится на другой backend без обоснования. Новый enterprise deployment не нужен для исправления локального owner defect.

## S13. Проверка свойства и допустимое отклонение

Each task доказывает свой predicate через настоящий producer, допустимый retained artifact/receipt и fresh consumer. S0-K14 требует независимости там, где заявлена независимая correctness verification; same-code replay даёт consistency и не маскируется под независимый oracle. Это не требование отдельной команды для каждого повтора детерминированного reducer.

Механизм считается предпочтительным пока подтверждаются его предпосылки. Неизвестное измерение не даёт права объявить альтернативу быстрее. Обоснованное отклонение описывается по [процедуре](README.md#обоснованное-отклонение), сохраняет один owner и проходит affected review. Этот набор решений не добавляет blanket gates: scoped rebind, interface-stage preparation, conditional suppliers и final completion joins остаются определяющими правилами параллельности.

Pattern pass: P01/P02/P04/P05/P07/P08/P10/P13/P14/P15/P27/P29/P31–P41. Цель — замкнутая source-bound цепь без центрального списка возможностей, второго owner, неограниченного materialization или authority из metadata. Все product discriminators ещё предстоит выполнить после приёмки E02.

## S14. Кандидатная постановка и общий охват

Sponsor задаёт вопрос, purpose, decision boundary и ограничения; система может предложить candidate atom/estimand, measure/weights и сравнить условные результаты. Protected use требует выбранного и допустимого основания. Это не право системе присвоить principal политический выбор. Общие grammar/routes/limits для полного набора семейств из текущего source inventory остаются программным обязательством (26 на исходном срезе R13, не runtime enum); каждый case приобретает только нужные ему источники. Все 197 source cards не становятся обязательным corpus.

## S15. Внутренняя работа и реальные внешние входы

Во всех текущих карточках `inputs_to_resolve` — перечень для классификации, не список внешних стопов; полный denominator берётся из task manifest, а не исторического числа R13. Отсутствующий parser, bridge, validator, producer, allocation или migration назначается и строится. Уже pinned criterion читается, а не повторно запрашивается. External hold требует конкретного недостающего факта/акта/permission, supplier investigation, допустимых альтернатив и точно заблокированного claim. Каждая рекомендация содержит [root review](root-review.md) этого различия.

Ни одна capacity charge не снимается только от expiry lease или terminal attempt: нужна проверенная release соответствующей allocation либо reconciled transfer её живому owner. Остановка процесса сама по себе не освобождает shared/provider allocations. Сторонний scheduler, SDK, CRD или provenance framework служит примером механизма, не основанием заменить существующего owner. Источники исследования и пределы переноса собраны в [sources](sources.md).

## S16. Free-grow без ошибочных физических и проверочных барьеров

[R21 самостоятельное review](../assurance/r21-self-review.md) уточняет восемь
engineering boundaries в существующих tasks. Новый профиль того же класса использует
существующий adapter плюс собственное conformance; новый смысл требует native-owner
extension. Первый WDI witness не задаёт порядок готовности всех протоколов.

Один semantic owner — единый контракт и invariant, а не обязательный singleton
process/global mutex. Atomic/fencing key выводится из реального job/head/partition/
budget scope. Disjoint scopes допускают отдельные workers и transactions; общие
provider/disclosure/cap invariants нельзя разделить tenant labels. Это не изменение
source write leases: один writer по-прежнему владеет каждым shared source file.

Fresh-use check переиспользует immutable content-bound assessment, но заново
разрешает relevant purpose/rights/generation/currentness. Он не обязан повторять
полный научный verifier или читать весь payload при каждом доступе. Неполный
invalidation/dependency closure исключает такой cache hit; TTL не заменяет fence.

Новый resource class можно измерить в заранее проверенном, разрешённом конечном
изоляционном envelope без нового custody commitment. Это не разрешение запускать
неограниченную работу с unknown cost. Production qualification потребляет actual
measurement; перенос reservation никогда не скрывает живые allocations.

Append-only означает порядок сохранённых разрешённых фактов. Это не исключение из
LIF-05 для хранения raw data, identifiers, hashes и provenance. Утрата lawful replay
показывается явно, а история не используется для восстановления отозванных прав.

## S17. R22: границы фактов, lifetime и сквозной приёмки

[R22 redteam](../assurance/r22-redteam.md) закрывает несовпадения между выбранными
механизмами и их потребителями. Новых owners, глобальных start barriers или
обязательных технологий не вводится.

- CAP-04 local observation cut и source-native cut — разные evidence bases.
  LIF-02 закрывает race наших наблюдений/enrollment, но не выдумывает внешнюю
  continuity; fresh projections показывают bounded observation/as-of semantics.
- LIF-07 хранит роли зависимостей: computational/semantic, fresh-use и retention.
  Admission-only изменение прав не обязано повторять научный расчёт; изменение
  permission-driven selection/redaction обязано менять соответствующую основу.
  LIF-01 reuse proof потребляет реальный emitted closure и fresh reader при
  composition, не требует завершённого LIF-07 для выпуска своего интерфейса.
- Данные внешнего института и проверенный predicate их применимости не одно и
  то же. P37 basis вычисляется на каждом required predicate, а не по имени поля.
- LIF-06/OPS-08 учитывают lifetime actual allocations, включая surviving shared
  buffers/cache после terminal attempt. LIF-04 применяет выбранную queue policy:
  service opportunity либо bounded terminal/review disposition, а не бесконечный
  defer с красивой queue-age метрикой. Custody duties не исчезают по TTL.
- UI-02/04 потребляют LIF-05 для retention/deletion своих исторических surfaces.
  Общие слова «preserve prior artifacts/history» во всех карточках означают
  **только разрешённое сохранение**, включая identifiers/hashes/lineage; они не
  отменяют этот owner. Это не право переписать сохранившееся историческое значение
  или удалить сведения по неподтверждённому запросу.
- OPS-05 восстанавливает material Claim/public histories вместе с rights/control
  state. Witness должен переживать выбранный rollback closure; второй откатившийся
  журнал не служит независимым подтверждением. LIF-02/publisher fencing защищает
  промежуток до fresh-read enablement. При утрате lawful evidence — scoped
  quarantine/limitation, а не восстановленная false-current подпись.
- Effect-posterior WP activation и structural-write rule остаются отдельными
  predicates. DES-12 assurance теперь проверяет оба, сохраняя одного GYD-12 writer.

Original criteria и поддержанные native contracts остаются определяющими; эти
уточнения не принимают код, не устанавливают внешние факты и не меняют SDD.

## S18. R23: гарантия определяется смыслом use, а не удобным proxy

[Самостоятельное review](../assurance/r23-self-review.md) уточняет S16/S17 без
новых owners или start prerequisites:

- **Reuse:** LIF-01/07 и CAP-03 отделяют повтор сохранённого assessment/realization
  от нового stochastic invocation. Cache-off проверяет ту же выбранную гарантию
  на том же basis/use cut; bitwise или exact sample-path equality не навязывается
  всем методам. Distributional similarity не заменяет exact referenced artifact;
  cached draw не становится новым независимым наблюдением.
- **Наблюдение:** CAP-04 сохраняет actual attempt и observation interval; LIF-02
  проверяет scoped expected head и основание порядка. Поздний старый ответ не
  отменяет известную invalidation. Receipt order не становится source succession;
  независимые опросы остаются параллельными. Reconciliation может вернуть лишь
  подтверждённый observation/as-of use, не непрерывную внешнюю актуальность.
- **Recovery:** OPS-05 классифицирует required retained bytes, lawful result-only
  receipts и verified-erased dependencies через native contracts/LIF-05. Законное
  отсутствие raw input не ошибка backup; пропажа обещанного retained object —
  ошибка. Холодный объект проверяется до его protected use, если профиль допускает
  scoped recovery; это не corpus-wide integrity. Старую подпись нельзя оживить
  новым кандидатным расчётом или реконструкцией запрещённых данных.
- **Очередь:** LIF-04/06 и OPS-08 различают service promise, best-effort disposition
  и unresolved review. Повтор review/retry не обнуляет возраст и не подтверждает
  service. Пропущенный custody interval получает truthful claim/coverage reaction
  через LIF-02; реальная новая bounded continuation не переписывает прошлый lapse.

Каждая selected guarantee получает свой positive, adversarial и removal signal.
Неподдержанная гарантия ограничивает соответствующий use, а не все native methods,
все архивы или все источники. Это плановые engineering corrections, не acceptance.

## S19. R24: сохранять обязательство и основание через сбой/смену версии

[Редтим R23](../assurance/r24-redteam.md) уточняет существующих owners:

- stochastic retry сохраняет native evidence unit и accepted-result binding;
  qualified pure retry/replacement разрешён с failure/selection accounting;
- duty хранит admission commitment и durable trigger; новые safety/rights/caps
  применяются сразу без переписывания старого lapse;
- scoped duty→claim witness является completion join, не start barrier;
- erased raw parent не запрещает все independently qualified retained uses;
  raw-required use и historical/current authority остаются различными;
- verification связывается с actual consumed bytes, допускает native bounded
  streaming без нового archive/ledger;
- rollback использует фактическую directional compatibility, не универсальную
  API/worker lockstep пару. UI history подчиняется actual retention rights.

Ни новых SDD решений, ни product acceptance это дополнение не создаёт.
Conservative source scopes остаются допустимы без доказанной независимости;
free-grow не требует выдумывать precision, которого native source не даёт.
