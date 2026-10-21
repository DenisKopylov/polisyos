# Повторный разбор: решения, поставки и проверка свойств

2026-10-21. Вход — lifecycle proposal на G `bfcdbda0dd1181b8b854180efbd5cffe6a8a6a2b`; static code frame — `635413bcd1bd1d7e7b829d9123765e28e6bf23d6`. [Протоколы для реализации](05-implementation-protocols.md), [первичные прецеденты](07-primary-design-references.md), [неприменённое предложение SDD](../sdd-proposals/lifecycle-c03-20261021.md). Все runtime probes ниже **UNRUN**. Это план реализации и review проекта, не acceptance E02 или formal closure.

## 1. Результат критики

Базовая организация верна: разные основания сохраняют native смысл и authority; CAS, DataForge/Fabric, Scientist, Claim Ledger и security остаются владельцами. Слабость находилась в описании переходов: правильное слово «проверить» ещё не определяло, кто и в какой момент делает свойство устойчивым после crash, обновления и восстановления.

Ниже полный набор **12 тематических результатов этого review**. Это denominator таблицы R01–R12, не 12 новых багов runtime и не новый реестр Pxx. Столбец «решение» означает исправление проекта; поведенческое подтверждение появится только при реализации.

| ID | Контрпример/слабое место | Решение и точная граница |
|---|---|---|
| R01 | Late snapshot-read возвращает строку после CDC delete; max offset скрывает gap | §2 протокола: adapter-defined cut/overlap, incarnation, schema и continuity witness; sparse offsets не считать ошибкой по арифметике |
| R02 | Новый запрет/исследование меняет «ничего нет», хотя все прежние refs прежние | §4.1: set/negative dependency с selector/rule/coverage; coarse scope generation прежде точного predicate index |
| R03 | Change записан как deduped до enrollment; поздний subscriber его не получает | §4.2: input C→enrollment W→retained replay after W, atomic journal/generation, replay-floor check; marker связан с committed effect |
| R04 | Head не меняется, но source/permission устарели; scheduler выключен | §4.2–4.3: writer-participating commit/read cut и expiry; optimistic snapshot не защищает последующий action; local-known cutoff явно ограничен |
| R05 | Непустые refs и scope strings проходят как semantic support | §3.1: предметный producer assertion/assessment/use, content-bound predicate; presence остаётся diagnostic, не достаточным основанием |
| R06 | Несколько публикаций одного cohort увеличивают «independent count»; память скрыто выбирает удобные studies | §3.2–3.3: метод зависимости и denominator; trace selection influence вне evidence slots; неизвестность не превращать в independence |
| R07 | Source меняет license, и runtime автоматически отменяет старые права | §5.1: competent applicability/precedence/effect-time decision до изменения rights fence; irrevocable/alternative grant отдельны |
| R08 | После purge появляется поздний index write; restore возвращает удалённый payload | §5.2–5.3: enrolled write intent + commit fence + restore quarantine с post-backup decisions; неполная inventory не all-copy deletion |
| R09 | Удалена ссылка общего CAS, объявлено physical erasure; WORM/backup остаются | §5.3: logical membership vs physical placement, совместимый deletion domain, scope outcomes; unavailable replay явно |
| R10 | Lease истёк, внешний запрос исполнился; retry после upgrade повторяет эффект | §6: duty/intent/attempt/effect, provider-window reconciliation, pinned protocol или explicit migration; job state не authority |
| R11 | Plugin не меняет dispatcher, но теряет semantics/budget; GC удаляет blob после нового root | §7: actual second-source witness, directional features, state budget; root publication и final delete разделяют реальный fence |
| R12 | Каждый parser/hash требует независимого verifier; рисунок требует всех стадий от каждого ресурса | §§1,3: S0-K14 consistency vs correctness; sparse owner handoffs, candidate exploration и audience-scoped projection |

R03/R05 имеют конкретные static witnesses в C: `scientist/validation/decision_validity.py::record_dependency_event` сохраняет dedupe и пропускает отсутствующие dependency rows; duplicate branch переоценивает имеющиеся, но не применяет прежний event. `scientist/validation/claim_support.py::_satisfied_predicates` использует presence/строковые checks. Root перечитал эти участки. Это **не воспроизведённые runtime FAIL** и не вывод о всех surrounding callers: current source и composed protections должен проверить исполнитель.

Root дополнительно отклонил четыре опасных упрощения из исследовательских вариантов: generic dense offsets; blanket revocation от новой license; универсальные `CapabilityDeclaration/Request/Resolution` как обязательные классы; обязательный новый SDD перед каждым queue/restore extension. Также rejected re-read-before-write как достаточный distributed fence. Финальный текст задаёт property и ограничение backend, а не выдаёт последовательность несвязанных reads за атомарность.

## 2. Что можно реализовывать без нового архитектурного круга

CTM/S0/identity/PV уже задают sparse temporal roles, native reaction owner, candidate band, authority boundary и disclosure. Поэтому capture receipts, enrollment/replay, purposeful access, bounded attempts, conservative migration и truthful surfaces — engineering work под существующими решениями. Нового sovereign lifecycle owner не требуется.

**Первый вертикальный путь:** существующий разрешённый source с bounded capture → selected immutable result → одна конкретная предметная relation → claim use → change → fresh owner/API projection. Выбрать реальный caller из карты кода, а не строить параллельный demo service. Для механики полезен управляемый adapter fixture с fault injection; он не заменяет authentic input и не присваивает внешнюю authority.

Где ещё нужен выбор исполнителя, правило выбора уже определено:

| Вопрос | Default и условие изменения |
|---|---|
| SQL или новый workflow engine? | Extend existing control store/worker; внешний engine только после измеренного требования к recovery/history/topology |
| Общий semantic DTO? | Native relation/use records; narrow artifact лишь после caller/consumer census; shared ABI отдельно обсуждать при доказанной необходимости |
| Snapshot protocol? | Простой consistent cut, если source даёт его; иначе verified overlap; иначе honest interval/partial |
| Точный predicate index? | Сначала coarse scope invalidation, затем оптимизация при измеренном fanout cost |
| Global distributed transaction? | Нет как default; owner-local atomicity + prepared/reconcile + restricted projection. Stronger promise требует реального participating backend protocol |
| Unknown facet/profile? | Preserve inert candidate при разрешённом хранении; unsupported required behavior ограничивает конкретную operation |
| Full-copy purge неизвестен? | Scoped quarantine/reconcile/retention outcome; no false erasure. Никакого автоматического удаления в этой исследовательской работе |
| Чего нет у внешнего поставщика? | Искать альтернативный route/данные/метод; conditional result или costed refusal. Не подделывать missing permission, law, custody или completeness |

## 3. Последовательность реализации и параллельность

Один интегратор, один canonical writer на механизм, отдельный reviewer. Можно одновременно проектировать/реализовывать независимые owner seams после фиксации small cross-owner binding; **нельзя двум агентам независимо вводить разные semantics для того же frontier/permit/use**. Тесты — будущая стадия в вычислительном окне исполнителя, не работа этого review.

### W0. Source freeze для выбранного slice и договорённость owners

Сверить named paths C с текущей веткой, пройти реальные callers/sibling readers, выбрать один действующий путь. Зафиксировать producer/artifact/bridge/consumer/public scope и предикаты; отделить available source behavior от заявлений descriptor. Не запускать полный replay ради census. Перечислить реальные commit domains и crash windows; нельзя объявить их SQL-атомарными по наличию одной транзакции.

Назначить owner каждого generation и области: capture incarnation; source scope change; rights decision; claim basis/head; index build. Shared wire shape ввести лишь по реальной границе, с owner schema version. Не резервировать «v2» для всех существующих типов заранее. Existing strict public/generated contracts меняются вместе с affected clients.

**Выбор протокола первого slice фиксируется до code change:** canonical Claim Ledger/Decision Validity owner; выбранный source-owner journal/scope; security owner конкретного operation grant; named store и участвующие writer/finalizer. Default — transactional compare/enrollment/head/outbox, если все нужные owner rows действительно в одной существующей transaction boundary. Иначе выбрать prepared/reconcile и разрешённую cutoff-qualified claim projection; не добавлять distributed guards без их собственного recovery/fencing протокола. Protected access/допуск проверяется отдельно и не ослабляется cutoff. Для rights producer назвать accepted grant/change evidence, issuer competence check, applicability/precedence rule, effect-time semantics и unresolved outcome. Эти пункты — slice-local implementation inputs, не новое ожидание общего решения G.

### W1. Получение и durable resume

Owner: Fabric capture/ingestion, stream/cursor и Core artifact seams из карты §1. Wire intent→page receipt→verified progress→sealed root→fresh selected reader. Completion/coverage protocol обязателен уже на первом source. Существующий batch cursor no-op нельзя снять полем `verified=true`; подключить actual resolver/property.

Предпосылка: W0. Может идти параллельно W2 и W4 в отдельных source areas. Внешние права реального source нужны для actual read; синтетический protocol fixture проверяет механизм без их имитации. Deliverable включает исходный gap, receipt producer, recovery, exact root reader, partial/error API и probes T01–T04.

### W2. Семантический use и источник изменений

Owner: конкретный Scholar/Lex/Foundry/DataForge relation producer плюс Scientist support/dependency consumers. Первый bounded case — correction одного результата в документе с несколькими результатами, либо уже существующая exact relation с настоящим consumer. Не ограничивать будущие grounds данным case.

Сохранить assertion отдельно от assessment; content-bound relation, выбранный rule, original/translated occurrences и ограничения. Явно выразить set/negative dependencies там, где утверждается отсутствие/полнота. Independent support и selection trace подключать к реальному потребляющему методу, а не добавлять decorative fields. Deliverable: T05/T08/T09/T10 и surface о basis/альтернативах. Schema/topology не выдают method validity.

### W3. Enrollment, change admission и fresh projection

Owner: Claim Ledger/Decision Validity + participating source owner + publisher. Сначала закрыть event-before-enrollment и dup-before-effect, затем publish/read race с named serialization protocol. Source journal and generation становятся видимыми до asynchronous fanout. Registry-derived path denominator сохраняется, но не называется полной semantic dependency universe.

Зависимости: binding из W0, реальные root/relation outputs W1/W2 для composed проверки. Проектировать можно параллельно, принимать отдельно до композиции нельзя. Deliverable: scheduler-down reads, late events, scope additions, ambiguous commit; T05–T07/T18. Изменения claim — append-only, historical bytes не переписываются.

### W4. Purpose, copy enrollment и restore

Owner: existing security/authz, storage/retention, index/provider/backup owners. Начать с actual rights-applicability decision и shared access/write barrier. До расширения sensitive materialization закрыть late writer и учесть все write paths выбранного scope. Restore gate — часть same-copy lifecycle, не отдельный optional runbook после purge.

Зависимости: W0; можно параллельно W1/W2. W3 потребляет permission dependencies, поэтому схему binding согласовать заранее. Deliverable: T11–T14, current permission vs factual truth, минимизированный audit, scope of deletion/replay. Provider ack и backup expiry не превращать в full purge. Настоящие provider/records/rights inputs проверяются отдельно.

### W5. Длительная duty и исполнение следующего шага

Owner: runtime control-plane/worker; semantic duty остаётся у native owner. Reuse существующую транзакцию job/progress/event/outbox. Добавить потребляемый outcome/inbox, durable due/cooldown, operation-class retry, cooperative cancellation и recovery effects. Actor identity и разрешение на side effect перепроверяются; serialized process permit не воскресает.

Зависимости: W0; может разрабатываться рядом с W1–W4, composed acceptance использует их. Deliverable: T15–T17/T20 и поведение при overload. Не требовать многолетнего wall-clock теста: управляемые time transitions/crash/version replays проверяют контракт; реальные долгие operational SLO остаются отдельными наблюдениями.

### W6. Второй источник, rollout и retirement

После first-slice freeze и независимых reviews — второй source того же executable/semantic класса с другим layout/страничностью и actual fresh consumer. Проверить cross-source cut limitation, directional compatibility, old-version reader, profile/model migration и GC roots. Один bounded resource wave измеряет реальный denominator/peak state. **Не переносить большой production payload в cloud ради проверки механики.**

Deliverable: T18–T20, second-source end-to-end, installed/API companions по scope. Если требуется новый adapter, реализовать локально; если materially новое meaning — отдельный owner vertical с new acceptance, без central registry redesign. Full integrated replay выполняется после принятого source/input/backend freeze, а не после каждой записки.

## 4. Behavioral acceptance — проект проверок

Полный набор этой таблицы: **20 protocol probes T01–T20**; это не число выполненных tests. Каждый применимый probe должен иметь positive, distinguishing negative, exact source/input/profile, persisted receipt и fresh consumer. Removal сохраняет fields/markers и убирает реальное свойство; результат должен измениться. Не нужны constructor-only tests, проверяющие ту же декларацию, что производит код.

| Probe | Действие/falsifier | Наблюдаемый результат |
|---|---|---|
| T01 | Snapshot read после concurrent update/delete, включая boundary equality | Нет resurrection/двойного эффекта; remove overlap logic нарушает результат |
| T02 | Dense protocol с пропуском; отдельно valid sparse log и filter | Первый не complete, второй не ошибочно rejected; проверяется native continuity, не `max(offset)` |
| T03 | Source reset, schema/selector change, log expiry | Старый checkpoint не продолжает новый источник; partial/new generation явно |
| T04 | Crash page-before-cursor и cursor с unreadable child; `304` без retained representation | Resume reconcile или точное unavailable; не empty dataset/full complete |
| T05 | Change до enrollment и между W/live attach; C ниже replay floor; crash marker-before-effect | Retained journal доставляет event либо current basis отказана; marker не скрывает gap; remove journal/generation coupling ломает positive |
| T06 | Material enrolled source/rights dependency меняется между check и public commit; отдельно меняется unrelated generation | Backend witness доказывает выбранный порядок или только cutoff-qualified outcome; double-read без fence не positive; unrelated change не блокирует незатронутый claim |
| T07 | Scheduler выключен; material enrolled dependency generation меняется между head read и projection; отдельно unrelated generation; expiry наступил; terminal refusal удалён | Named read-cut/fence либо scoped limitation; unrelated change не закрывает незатронутый claim; нет cached current green; PV-K01 различён, PV-K04/PV-K05 omission блокирует governed positive, историческая authenticity сохраняется |
| T08 | Добавлен matching record, старые positive refs прежние | Negative/set dependency invalidated; partial corpus не выдаёт universal absence |
| T09 | Те же refs, но инвертированы polarity/unit/population/legal effective scope | Semantic support не сохраняется по непустым полям |
| T10 | Две публикации общего cohort; memory меняет selection frontier; no-hit vs equivalence | Нет ложной independence; bounded exploration разрешён, но не поддерживает полный all/best claim; trace и отрицательные утверждения различены |
| T11 | License revision без права отзыва старого grant; затем applicable revocation | Первый случай не blanket deny; второй закрывает затронутую operation в её temporal scope |
| T12 | Revoke после check, перед derivative/index commit, и во время stream | Late visible write не проходит; bounded disclosure semantics и уже переданные bytes различены |
| T13 | Restore pre-delete backup; post-backup decisions сначала недоступны | Quarantine остаётся; затем разрешённая reconciliation без resurrection; истёкший tombstone не разрешает опасный restore |
| T14 | Shared CAS memberships, retained WORM/provider/backup, raw удалён | Нет ложного all-copy erase и чужой потери; actual replay limitation показана |
| T15 | Provider выполнил запрос, ответ потерян; idempotency window истёк | Lookup/reconcile либо indeterminate; нет blind duplicate; простая метка key недостаточна |
| T16 | Cancellation до/после remote accept; local lease потерян | Не объявлять remote stopped по local flag; consumption/repair учитываются до known outcome |
| T17 | Due duty через два build release, checkpoint migration и history compaction | Intent/rule/basis не переинтерпретированы; старый audit/replay scope честно сохранён |
| T18 | Независимые cuts, late backdated event, event storm, lagging reverse index | Нет выдуманного global snapshot; history append order, coarse invalidation и bounded pending |
| T19 | Unknown optional/required facet; прежний schema, новое meaning; source меняется во время index build | Optional inert preserved, required unsupported, no semantic fallback или hidden mixed generation |
| T20 | 429 по shared credential, рост global method state; новый/restore root между последним GC scan и unlink; expired writer lease | Quota/pools и overload явно; root/delete сериализованы либо delete запрещён; stale writer не публикует root после fencing. Это отдельные случаи одного resource/retirement probe, не один aggregate PASS |

### Surface и observability как часть того же результата

Один fresh authorized reader должен различать capture/coverage, semantic assessment, use admission, active limitation, currentness cutoff, workflow pending и storage/replay restriction. UI не обязан показывать внутренние токены, topology или protected locators. Machine/audit projection связывает разрешённые exact refs; public — достаточное обоснование и границы без sensitive metadata.

Operational dashboards измеряют due lag, lost/indeterminate effects, outbox receipt lag, incomplete captures, pending impact scopes, denied stale permits и неполный deletion scope. Такие метрики помогают оператору; sampled telemetry не доказывает полный affected denominator. Schema/API generated companions не должны превратить unknown в default success или потерять limitation при roundtrip.

## 5. Миграция и остановки, которые допустимы

Старые receipts и claims остаются историей своей версии. Backfill только того, что доказуемо из exact retained records: refs, inputs, actual events. Не восстанавливать «независимость», source completeness, право, effect ack или causal validity из сегодняшнего успешного decode/tenant name. Unknown legacy binding не становится новым protected positive; разрешённая candidate/history работа продолжается.

Вводить новые authority-bearing writers/consumers на выбранной границе совместно; dual-write shadow не даёт authority до reconciliation. При rollback возвращать совместимый reader или ограниченную projection, а не восстанавливать старый bypass. Old decoder/code можно retire только после проверки retained uses, либо с явно принятой loss-of-replay реакцией. Права на хранение и исполнение старого кода/материала также остаются scoped.

| Недостаёт | Что исполнитель обязан сделать сам | Честный остаток после этого |
|---|---|---|
| Source snapshot/CDC semantics | Изучить actual adapter/provider; попробовать simpler snapshot/alternative route; проверить границу fixture | Provider не предоставляет нужную continuity/completeness; использовать bounded candidate или другой input |
| Rights/issuer/hold | Resolve конкретные permits и их applicability; исключить parser/bridge defect; назвать actor и минимальный packet | Настоящий акт/мандат не создаётся кодом; affected action ограничена |
| Semantic relation/equivalence/calibration | Реализовать owner check, сравнить plausible methods, сохранить falsifier и uncertainty | Empirical/external warrant действительно отсутствует; conditional analysis не маскирует adoption |
| Atomic backend guarantee | Назвать participants, commit point и crash interleavings; выбрать scoped protocol | Только cutoff-qualified view, пока stronger guarantee невозможно обеспечить |
| Provider cancel/delete/lookup | Проверить exact endpoint, operation IDs, retention scope и возможность reconcile | Uncontrolled copies/effect ambiguity; no false closure |
| Multi-year engine capacity | Сначала bounded local protocol и измерение representative load | Новый engine нужен лишь если измеренный envelope недостаточен; оформить конкретное сравнение |

Нельзя возвращать «ждём G» по вопросу, который решается этой таблицей или существующим owner contract. Новый действительно архитектурный вопрос содержит divergent case, investigated alternatives, preferred resolution, authority/time/migration/consumer footprint и minimum falsifier. Внешние inputs не заменяют внутреннюю engineering работу; внутренний workaround не создаёт внешнюю authority.

## 6. SDD и standing

Обязательной новой архитектурной развилки для описанных narrow implementations не выявлено. Предлагается **одно необязательное уточнение C03** к North Star: что именно означает free grow и как читать общий lifecycle. Оно подготовлено [отдельным точным текстом](../sdd-proposals/lifecycle-c03-20261021.md), но **не внесено** в `system-design-decisions`.

Отдельное согласование потребуется, если реализация действительно захочет изменить публичное обещание currentness/replay, ввести новый общесистемный status, universal evidence/permission ABI, внешнее sovereign ownership или безусловную deletion guarantee. Этот пакет такого изменения не предлагает и не разрешает. Backend-specific predicates и conservative bounds должны соответствовать уже ratified CTM/S0/PV, а не создавать новое значение слов `current`/`verified` по умолчанию.

Pattern pass: все R01–R12 отнесены к существующим классам, главным образом P01/P02/P04/P05/P07/P08/P09/P10/P13/P14/P25/P27/P29/P31/P32/P35/P37/P38/P40. Критика устраняет слабость проекта, не закрывает runtime findings. Точный source и документарные проверки — в [receipt](../research-receipt-r6.json).
