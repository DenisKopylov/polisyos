# Решения по общим механизмам

Ниже — рекомендуемый инженерный путь для продолжения. Внешняя law, permission, welfare choice или эмпирическая предпосылка не ратифицируются этим планом. Для каждой такой части назван необходимый источник; соседняя механическая работа может продолжаться. Уже принятые semantic choices не открываются заново.

## D01. Identity означает consumed basis, а не locator

**Затрагивает:** C LA-041/LA-028/LA-038/039/040; B CAS/view/tenant, B61/B67/68; D resume/cache/transfer; E model/draw/calibration; A context/reentry.

Выбор: compose existing `ArtifactRef`/manifest/CAS ownership, `GenerationBasis`, source-profile resolver и canonical owner receipt. Не создавать ещё один global registry/hash/schema для всех подсистем. Каждый reuse/currentness/admission consumer сравнивает собственный полный material basis: content + exact manifest view; schema/rule; effective non-secret profile/policy; consumed selection/model/evaluator; scope/tenant/purpose; релевантные time roles; required output inventory. Идентичные bytes не делают одинаковыми два tenant views; одинаковый profile ID не делает одинаковыми две effective policies.

**Первое исправление:** DFI resume должен инвалидировать skip/benchmark, если под тем же ID изменились effective source profile или execution policy. Ближайший существующий pattern — acquisition authority повторно resolves profile и сравнивает content SHA. Не сохранять credentials в receipt: использовать non-secret revision/ref либо explicit owner invalidation.

**Discriminator:** unchanged basis допускает reuse; mutation underlying resolved profile/policy при неизменных ID/markers инвалидирует до skip; fresh checkpoint/benchmark reader видит limited/stale до нового producer. Затем применять этот pattern к реальному потребителю, а не добавлять поля повсюду.

## D02. Producer state/copy должен иметь один допустимый value domain

**Затрагивает:** B59, producer scope, ordinary/async/worker/completion; B87/C stream cleanup.

Prepared B1e имеет source review и retained-SKG candidate mechanism, но native/removal ещё UNRUN. Статический B59 риск: arbitrary leaf проходит preflight, затем `deepcopy` может выполнить пользовательский hook. Выбор — сначала сформулировать admissible producer-state domain по существующим runtime types и контролировать его в общем admission/copy/completion path. Не добавлять отдельные запреты на каждый найденный класс.

Исследование ограничено одним вопросом: какие реальные допустимые leaves и strict DTOs требуются существующим callers? После полного sibling census выбрать generic safe projection либо explicit unsupported refusal. Проверить ordinary model fields, extras, nested containers, assignment, copy и завершение; present-but-hostile `__deepcopy__`/model hooks не должны исполняться до отказа. Статический escape сам по себе не является выполненным FAIL.

Для B87/C stream отдельно договориться о lifecycle ownership: logical timeout/cancel, physical finalization и closed-resource evidence — разные события. Отмена coroutine не доказывает закрытие connector/process. Общий task graph не требует общего mutable scratch.

## D03. Деньги, ledger и compute permit — разные величины

**Затрагивает:** A B10/B11; B64–68/B66; D B120–123; F B56; D B108.

Сохранять существующие producer origins `reported|estimated|reuse|unknown`, settlement acknowledgements и pending completion obligations. Exact stored money остаётся Decimal; actual zero отличается от unknown и estimate. Local durable ledger доказывает локальный accounting transition, а не provider invoice. D projection обязан сохранять origin и отдельно reported subset; имя/сумма не должны превращать estimated input в measured expenditure.

Выбор: wire existing `LLMProducerEvent` → configured `BudgetMiddleware`/ledger → A/D persisted consumer. Перед изменением сперва проверить latest selected B/D code: поздние decoder/projection fixes уже существуют. Дополнительная estimate price-basis identity нужна, если criterion требует replay estimate; FX, новая currency law или billing subsystem не являются автоматическим продолжением E02.

**B11 не блокировать B66:** bounded VOI/controller positive и реальное fixture middleware exhaustion достаточны для его соответствующего scheduler свойства; invoice reconciliation ему не приписывается. B66 отдельно проверяет один actual provider miss + reuse hits, expiry, retry/reopen/cancel и сохранение unknown.

**B56:** reuse existing outer Runtime/study permit и synchronous stable folds. Сначала измерить полный admitted competing-job/fold/repeat/model workload через этот owner. Если cap действительно не покрывает дочерние fits, extend тот же owner и делегировать permit, а не создавать scheduler. Выбрать explicit configured budget по реальному Runtime profile; денежный ledger не заменяет CPU/worker admission. Без указанного profile не выдумывать универсальную квоту.

**B108:** fiscal balance/deficit aliases имеют собственную sign/unit law. Exact money decoder не даёт права выбрать fiscal semantics. Канонический objective consumer должен получить минимальный versioned fiscal profile либо оставить unavailable; не подменять отсутствие favorable zero.

## D04. Общий subject join, раздельные uncertainty channels

**Затрагивает:** A B31/B21/B33; E B190/B194/B197/B200/B201/B202; D B161; F causal reports.

Reuse `EstimandAST`, contrast, `ValueOuterSet`, `UncertaintyEnvelope` v1.1 и persisted refs. Для B31 сначала проверить, выражают ли existing refs/metadata точный subject; если нет — smallest versioned canonical relation. Связать estimand/outcome/contrast/population/unit/scale и применимые time/source/model roles. Generic metadata или caller-built `NativeValueEstimandBinding` не становятся authority. A остаётся owner своего criterion/consumer; IR writer выполняет только необходимый contract delta.

Для B31 конкретный deliverable — producer-owned persisted relation в существующем A output/receipt boundary, связывающий два exact artifact refs с resolved canonical estimand/contrast/population и typed unit/scale. Текущие carriers не имеют достаточной first-class связи; caller-constructible nonproduction binding не подходит. Consumer resolves оба artifacts и subject, recomputes content/subject/unit equality и использует verifier provenance; флаг `eligible` или совпадение metadata strings не открывает join. Если existing receipt нельзя типизировать без extension, canonical owner делает smallest versioned relation schema с backward-compatible reader; Envelope v1.1 и identification/math channels остаются неизменными. Это выбранный bridge task, а не ожидание новой статистической теории.

Acceptance: настоящий producer → persisted refs/relation → fresh A consumer сохраняет point identification `[4,4]` одновременно с asymmetric native interval `[1,10]`; equivalent typed unit conversion проходит. Mutation estimand, contrast, population, unit, applicable time/source либо fake/unresolved relation при сохранённых markers отказывает в combined claim. Нельзя получить positive, вручную назначив contract-only binding authoritative.

Identification set, estimator CI, model/posterior uncertainty, Monte Carlo error и simulation-only distribution остаются разными каналами. `[x,x]` identification не означает нулевую sampling/model uncertainty. Unit conversion должна сохранять quantity; изменение estimand не является просто численным transform.

**E201/B202 уже решены:** сохранить v1.1 weighted-median compatibility; отдельно weighted mean и named inverse-CDF equal-tail interval; ordered joint rows/axes/draw IDs/weights/content; Profile2 exact finite law, а не новое универсальное Envelope v2. Multi-envelope unsupported join отказывает. Не ждать повторного semantic appointment.

**B161 — отдельный relation:** same subject/input/rule/time refinement не равен global min/last-value. Сначала выбрать допустимый scientific refinement profile и consumer reaction на independent risk/changed basis; затем wire existing uncertainty owner. Нельзя реализовать общий overwrite до такой семантики.

## D05. Partial graph: типизированное ограничение до query-specific идентификации

**Затрагивает:** F B214/B218, A graph/value/transport, C attribution/identification, E causal envelope.

Выбор сейчас: supported static DAG/ADMG path + сохранение uncertainty/typed refusal для неподдержанного PAG/temporal profile. Accepted F852 исправляет contradiction/no-op и persisted limitation; новый общий PAG engine сейчас не требуется.

Исследование: одна минимальная pair of admitted completions, для которой один и тот же query имеет разные результаты; один случай, где все допустимые completions дают одинаковый результат. Определить graph family, edge marks, temporal role, query, доступную completeness и projection. Only if existing identification path может проверить **все релевантные completions** допускается stronger identified result. Иначе result conditional/partial/refused с сохранённым графом. Невыполненная completeness не становится authority от совпадения sampled completions.

**LA-036 не закрывается E posterior corpus:** conditional Shapley требует observed-feature conditional law/sampler. Marginal replacement не является conditional attribution. До admitted law fail closed/typed unsupported; после — подключить law и sampler к обоим actual consumers, с dependent-feature oracle. Это конкретная capability, не расширение graph852.

## D06. Authority: наша проверка и реакция; чужой issuer остаётся внешним

**Затрагивает:** D B131/B137/B164; C rights/Legal; B configured permissions/CAS import; E DDM/R2; A N9/currentness.

Разложить каждую смешанную строку: institutional act → emitted evidence → наш resolve/bind/verify → наша scoped reaction → public projection. Reuse custody, existing CAS/ownership/preflight и commit-time check. Не создавать permission service, подписывающий чужую tenant/law authority. Вместе с тем отсутствие готового issuer не отменяет проектирование и проверку нашего fail-closed contract.

Сначала найти actual existing issuer/verifier/owner API и определить, это internal PolicyOS owner act или external institutional evidence. B prepared packets уже содержат уточнённые owner contracts: нельзя повторно запросить старый «неизвестный owner» без readback. Если consumer принимает declared boolean/string вместо content-bound verified fact, repair belongs inside PolicyOS. Если недостаёт факта конкретного tenant/purpose/revalidation/law, нужен минимальный источник.

Revalidation freshness не обновляется от LRU access. Permission связывается с bytes/view, subject/purpose, rule/epoch, validity/revocation и проверяется перед защищённым эффектом. Проверки: legitimate positive; missing, present-but-fake, foreign, stale, revoked → zero protected effects. Candidate work может иметь declared unknown/limited; public signature не повышается.

## D07. Реальный served producer важнее нового контроллера

**Затрагивает:** A B01–03/B09/B12/B15/B27–30/LA-046; E forecast/S10; D configured Search/Node; C source/profile.

Reuse existing N4, generation controller, recursive graph, CAS/Core GET, E forecast owner и D runtime. Текущий ordinary recursive compiler создаёт root-only graph; вручную переданные две child refs доказывают controller, но не meaningful decomposition producer. Следующая task — N4 emits содержательно разные source-bound child DesignProblems, existing lifecycle запускает их и сохраняет frontier/history; не поднимать recursion budget и не строить второй controller.

Аналогично same-candidate WMR revision уже имеет bounded algorithm: wire actual admitted source change → обычный reentry trigger → persisted old/new N5 refs/history → fresh GET. UUID/timestamp churn не меняет basis. Configured HTTP candidate path существует и полезен; criterion-specific authentic L6 acceptance остаётся отдельно до matching manifest inputs.

ETS predictive coverage не выдавать за causal-effect calibration. E predictive producer и A evidence resolver должны соблюдать совместимый method/estimand/purpose/time profile; выбрать настоящий compatible empirical producer либо явный predictive-only scope. Profile name и конечный CI не заменяют наблюдения.

## D08. Generated surfaces и migration closure

OpenAPI, schema manifest, public inventory/reference и clients генерируются canonical owners на выбранном composed source. A8b DTO и E Profile2 changes требуют fresh family, не hand-edited snapshots. Type/Zod/readers должны потреблять partial status и leaf reasons; backend field без клиента — `consumer_missing`, а не complete API capability.

DFK retirement, CAN adapter, package install, raw Core emission и external FQN history имеют отдельные scopes. Сначала исправить обязательный DFK census и выбрать Core byte/profile contract; затем один installed wheel/sdist test соответствующего scope. Поддерживаемое alias нельзя удалять на основании static zero, когда computed/external denominator unresolved. Compatibility window — явное product decision, не бесконечный внешний blocker.

## Математика и внешние библиотеки

| Область | Решение сейчас | Что потребовало бы нового исследования |
|---|---|---|
| GP/search | Использовать существующий BoTorch/GPyTorch owner и analytic oracle; не писать GP повторно. | Новый backend/profile, численный counterexample или недостающий warm/corpus consumer. |
| RDD/DiD/TMLE | Сохранить доказанные объявленные profiles и независимые algebra/reference controls. RDD уже имеет development differential oracle; custom code не признан ошибочным только потому, что он custom. | Реальная потребность fuzzy/cluster/selectors/finite-sample или counterexample исходного criterion; сравнить поддерживаемые библиотечные semantics до миграции. |
| Profile2 law | Сохранить exact finite-ratio law и versioned reader; law authority отдельно. | Новый nonlinear composition/joint admission, которого текущий refusal профиль не обещает. |
| Partial graphs | Reuse current ID paths; strongest sound typed result, без arbitrary PAG→DAG. | General query/completion algorithm только после D05 cases и выбранной supported family. |
| Money/cache/profile | Decimal + existing ledger/basis/ownership; structural identity repair. | Новый экономический или accounting law не следует из code consolidation. |

Ни одно из этих решений не разрешает сменить исходный criterion на более лёгкий. Каждый bounded residual отмечается при G adjudication; где criterion действительно шире, limited/held остаётся честным итогом.
