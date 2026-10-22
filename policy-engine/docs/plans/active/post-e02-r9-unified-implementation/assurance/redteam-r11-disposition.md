# R11: повторный глубокий red-team объединённой программы

**Статус:** исправления проекта исполнения; не G code acceptance и не closure. `G_acceptance=false`, `closure_ids=[]`; вся продуктовая проверка остаётся `UNRUN`. Реализация разрешена только после фактической приёмки E02. SDD, продуктовый код, canonical GY/Atlas/debt статусы этим изменением не редактируются.

Объект review — опубликованный пакет на `413c120e73c0323294997e767abbd1a1a7a5a226`, затем его документарный delta. Исторические входы G `d40bca270ef5c456e8233196e4d8d65e099777a7` и непринятый наблюдаемый код C `dccea950845cda5b38f026e7770c07819d31f4d9` сохраняются в source register. Публикационный HEAD не заменяет исходную code/evidence identity.

Десять прямых reviewers независимо проверили GY, Atlas, debt, R9, DAG, ownership, future delegation, assurance, deployment и executability. Root сопоставил выводы с исходными критериями и единолично изменил tracked документы. Пять направлений получили delta review; GY, Atlas, R9 и DAG — ещё узкий финальный проход по оставшимся замечаниям. Ни один помощник не создавал детей. Будущая схема `root → lead → leaf` записана как условно разрешённая runtime процедура; лимит 100 включает всех помощников обоих уровней, root дополнителен.

## Что изменено и почему

| Разрез / finding IDs | Дефект прежнего плана | Исправление и проверяемая граница |
|---|---|---|
| Debt RT-01, RT-05 | Scope-only DS8 вопросы подменялись publication build; Trust/Docs route одновременно назначен и не решён | P0 сначала разрешает исходный scope/signal; затронутый writer не получает lease до решения. Остальная работа идёт независимо. |
| Debt RT-02 | Численная VOI granularity ошибочно закрывалась acquisition cost/ceiling vocabulary | DEB-13: исследование measure/population/horizon/estimand и owner decision/ranking, затем одобренный native producer → UI-17. Нет права выдумать law/число. |
| Debt RT-03 | Candidate scope-record не имел полного authority-band supplier/ruling/lifecycle | DEB-14 строит producer/adapter по уже ратифицированному four-way/one-plane правилу; общий head пишет LIF-02, surface UI-19. Внутренний механизм не ждёт вымышленного внешнего appointment. |
| Debt RT-04 | Единственный оставшийся DS5→DS15 union/private-issuer predicate терялся между tasks | UI-20 — один точный generated/presentation контракт с фактическим promotion evidence и каноническим generator writer. Private TS issuer не институциональное полномочие. |
| Debt RT-06–07 | Старые missing labels выдавались за current residual; transitive-runner требование было двусмысленно | Исторические labels явно source-extracted. DEB-01 сохраняет intake-only residual и existing falsifier на changed transitive bytes, не заказывает новую attestation infrastructure и не выдаёт closure. |
| GY-R11-1–3 | Ложная O3 prerequisite; PR1a/PR1b/near-miss смешивались; FA1 проверял декларацию cutoff | O3/DS21 — downstream witness; milestones раздельны. FA1 меняет фактический cutoff basis при сохранённой декларации. |
| GY-R11-4–6, 11 | V2 packet неполон, V4 допускал неподтверждённое applicable исключение, DEF22 и V5 теряли точный predicate | Полный V2 artifact set, полный a–v disposition, шесть DEF22 owner claims отдельно от P41, replay input/parameter/seed/container/output identity. |
| GY-R11-7–10 | B/H, D2/E, manifest authority и per-row compliance были сокращены до похожего результата | Exact Slice0 BIND/ESTIMATE/VERIFY, Estimate-only measurement-rooted `grounded_partial_admissible`, полный facet/connector set, фактический manifest.authority, полный source-bound row tuple. |
| GY-R11-12–13 | Реальный substrate/Ukraine контракты можно было заменить fixtures или соседним receipt | GYD-32 actual L4 panels/world и identification effect; GYD-30 все исходные 13 contracts до фактического workflow consumer, отдельно от GY-G/S2. |
| Atlas A-R11-1–3 | DS19 проверял только 261 entries; два stale-open supplemental противоречили поздним closures | Отдельно перечислены 2 subunits, 60 supplemental, 23 negative records. Late-owner reconciliation отмечена; source register не переписан и новый runtime PASS не приписан. |
| Atlas A-R11-4–5 | DS7 closed/refusal подменял реальную value witness; неполная AQ1 grammar | UI-06 подготовка может идти раньше, composed acceptance требует actual capstone либо принятого эквивалента; все 8 source-defined algebras и mixed cases. |
| Atlas A-R11-6–9 | Потеряны public telemetry/redaction negatives, consultation scope, PA2 и точные learning causes | UI-02 N020/N023; UI-04 privacy/consent/consultation versus authority, конкретные large-text/screen-reader/plain-language проверки и приоритет позднего D4-A1 над старым locale текстом; UI-05 conditional PA2; UI-08 четыре cause classes и same-world provenance, learning только prediction_error. |
| R9 AP05 | Allowed hostname и caller permitted могли заменить query-disclosure authority | CAP-01 проверяет owner-bound query/provider/purpose/retention premise; неизвестная sensitivity/permission не public. Controlled egress/log sink negative. |
| R9 AP07 | Per-use permission не учитывал пересекающиеся outputs; query-only raw retention не проверялся | Один LIF-05 source-defined composition owner, atomic reserve/commit, uncertain hold и replay/new-audience distinction. CAP-03/06 проверяют реальные sinks и revoke-before-resume; недоказанная provider custody не объявляется выполненной. |
| R9 AP16 | Self-consistent trust package мог сам себя назначить | OPS-01 independent bootstrap, OPS-11 recovery после compromise, old-root rollback negative и fresh CAP-03 use. Историческая подпись ≠ current permission. |
| DAG phase class / executability E1–E3 | Completion смешивал owner readiness, внешние witness и original closure; selected case edges терялись | Новый stage contract; selected law/testimony/second-source producer outputs разворачиваются до dispatch. FINAL-FREEZE не ждёт fabricated facts; FINAL-USE требует полного исходного disposition. |
| Ownership | Path references ошибочно читались как независимые write sets; неполная generated family |22 conflict groups, два доказанных file collisions, отдельно semantic/mixed/generated groups. Один schema + четыре output companions. Неизвестные write sets не считаются независимыми. |
| Ops O-1–2 | Local rehearsal без явно enforced resource prerequisite; filesystem CAS без точного mount contract | OPS-02 execution permits LIF-06/OPS-01, OPS-08 при shared host; OPS-05 выбранный mount/topology/atomicity/durability/concurrency/restore proof. |
| Assurance / delegation | Replay tree после repair и глобальные nested leases были неявны | Финальный replay identity после blocking fixes + independent delta review; глобальные agent/resource leases, parent failure fencing, review вне author subtree, direct-only fallback. |

## Зависимости и реальная параллельность

[Stage rules](../execution/05-stage-and-release-contracts.md) отделяют четыре отношения: готовность owner output, фактический composition witness, разрешение исполнения на выбранном ресурсе и original disposition. Встречные consumer witnesses хранятся отдельно от native evidence requirements и не должны механически объединяться с build edges: иначе возникает ложный цикл. Но selected witness нельзя удалить ради ацикличности — перед dispatch root материализует staged edge и проверяет его.

Обновлённый manifest содержит 109 задач и 321 hard edge; DAG ацикличен,14 логических уровней, наибольший 57. Это верхняя логическая ширина готовности, **не фактическая исполнимая ширина**. Последняя `not_established` до принятого E02 дерева, точных write/read/generated leases, выбранных case/profile ветвей, бюджета памяти и пропускной способности review/integration. [Conflict registry](../execution/conflict-groups.json) и [dispatch procedure](../execution/06-conflicts-and-dispatch.md) показывают, что именно сериализовать, не блокируя всё семейство работ.

Near-miss означает подлинный отказ реальному attempted field-pilot request **до исполнения**, не опасный эксперимент ради evidence. Подготовка запроса/механизма и честная фиксация отсутствия могут завершить внутреннюю стадию; исходное эмпирическое обязательство остаётся открытым, пока его не выполнит или не разрешит компетентный owner. Аналогично correct refusal не становится authentic positive.

## Отклонённые расширения и остатки

- Не переносим исторический G input pin на publication HEAD; фиксируем отдельно объект review и его исходники.
- Не считаем root одним из 100 разрешённых subagents; lead и любой child входят в общий лимит, root дополнителен.
- Не строим новый runner-attestation subsystem ради уже явно bounded intake residual; существующий falsifier и non-claim сохраняются.
- Не превращаем private TypeScript constructor/issuer или внутреннее применение scope rules во внешнее назначение власти.
- Не редактируем canonical Atlas ledger для stale-open строк без его owning process; текущая карта требует правильной сверки и не заказывает повторный build исправленного механизма.
- Не утверждаем полный closure по нулю документарных замечаний. Source freeze, настоящие входы, actual backend/resource conformance и продуктовые negatives остаются будущей работой после E02.

Дополнительно root запросил сверку оставшихся reference-массивов DS19:60 unbound DS2 IDs разрешаются в ранее adjudicated ledger,10 census ссылаются на существующие entries/subunits. Они не потерянные implementation tasks; точные revisit predicates остаются у DS2 owners. Эта граница сохранена в auxiliary inventory.

## Доказательства обзора и границы

Полные короткие reports сохранены в `reviews/r11-*.txt`; исторические исходные замечания не переписаны задним числом. Delta reports показывают исправления только соответствующих классов. [Validation receipt](document-validation.json) фиксирует полный документарный пересчёт, JSON/links/DAG и PDF readback. Его PASS относится к структуре документации; тексты predicates независимо проверены reviewers и root, но ни один продуктовый behavioral gate здесь не запускался.

Pattern pass: P01/P02/P03/P04/P05/P07/P08/P10/P13/P14/P15/P27/P29/P31–P41. Главный repair — восстановить исходный predicate, назначить один native writer и весь producer→artifact→consumer→surface, отделить подготовку от authority/closure и испытать ровно то свойство, которое обещается. Новых product enums, services или самостоятельных permission ledgers этот пакет не вводит.
