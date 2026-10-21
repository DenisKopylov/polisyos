# Поставка, commissioning и критический разбор

Часть [проекта](../12-acquisition-storage-and-deployment.md). Implementation outline; не новая E02 приёмка. Связанные lifecycle [W0–W6/T01–T20](../lifecycle/06-delivery-and-review.md) и [E01–E15](../lifecycle/10-adversarial-review-and-delivery.md) сохраняются. Ниже детализация acquisition/deployment. Все runtime acceptance signals — **UNRUN**.

## 1. Очередь по механизмам

| Slice | Canonical owner и scope | Минимальная законченная поставка | Gate для следующего шага |
|---|---|---|---|
| A0 Exact-source reconciliation | Runtime/Fabric/Core + release owner | Delta pinned C→implementation candidate; actual source/API/store/worker contract map, выбрать первый supported route и deploy profile | Не повторять уже исправленный E02 дефект и не считать old receipt новым PASS |
| A1 Capture и повторное использование | Fabric connector/ingestion/cache + Core manifest + acquisition loop | Сначала exact bounded WDI single-response route после A0: task gap → permitted live capture → durable selected root → native admission → второй run reuse с новым use admission | Crash между capture/receipt/admission; more-pages refusal; wrong profile; denied second purpose; fresh reader. Pagination/HTTP304 — только при соответствующем новом contract |
| A2 Web/document route | Existing source connector + Doc/Scholar/Legal owners | Source-specific metadata/identifier lookup → permitted original → span-bound candidate → owner verifier, без authority от LLM | Injection/source substitution/summary-only/failed search не дают verified support |
| A3 Official legal source | DataForge Legal + Lex + custody | Exact act + amendment; historical/current `as_of`; publication/expression/rule binding; source change→fresh affected consumer | Future-effective/partial repeal/bad original/translation loss/completeness unknown |
| A4 Controlled/private data | Existing credential/security owners + Fabric + Runtime | Scoped query at custodian, permitted output/receipt, replay limits, one actual processor/region | Wrong audience/purpose, repeated query budget, lease/credential expiry и unknown remote effect |
| A5 Server composition | Existing Runtime ControlWorker/control store + release/ops | External runner bootstrap/handler lifecycle, durable postgres state, FS storage first, API/auth/fresh readback | Restart/duplicate/foreign-job read/backup restore/cancellation/bounded admission |
| A6 Backend parity и capacity | Core backend/ownership + storage/resource owners | Один выбранный remote backend: scoped write/read/cache/restore, bounded reads, migration; затем bounded pool scaling | No scope deletion workaround; pressure/revoke/cross-tenant leak/cold recovery negatives |
| A7 Institutional/participation intake | Native act/participation/claim owners | Реальный разрешённый external response или honest pending; original evidence, issuer/scope, protected projection | Draft/signature/response count не подменяют act/competence/representation |

A2/A3 могут исследоваться и реализовываться параллельно по разным source-specific owners после согласования capture contract A1. A4 как source-supported query через существующий worker может идти параллельно A5; A4 как новый remote site executor зависит от durable dispatch/receipt/cancel части A5 и не получает end-to-end acceptance до неё. Shared contracts, generated API, credential schema, manifest и store semantics имеют одного writer; reviewers отдельны. A6 не должен заставлять ждать весь содержательный acquisition; локальная разрешённая цепочка полезна раньше cloud parity. A7 не требует universal institutional subsystem: расширить конкретный существующий integrate-contract.

Remote SQL, CDC, STAC и новые compute engines вводятся при реальной потребности отдельными adapters, не как обязательные зависимости A1. Новый unknown family не блокируется этим списком. Release promotion проводится для выбранного supported scope; отсутствие всех возможных connectors не означает отсутствие полезного deployment.

A0 назначает **одного accountable integrator первого vertical у existing Runtime acquisition route/action boundary** (`acquisition_action_service.py` / `acquisition_route_loop.py`). Он отвечает за gap→decision→effect→receipt→admission→fresh use, не становится новым owner смысла. Fabric сохраняет connector/capture, Core — storage, соответствующие security/rights/domain owners — permission и semantic predicates. Для первого WDI path проверить actual bounded authority producer/decision refs, затем отдельно native admission/world-growth; не превращать terms ref в универсальный grant.

Реализационный handoff A1 обязан назвать issuer/permission evidence и его resolver, exact operation/purpose/profile binding, worker enforcement, durable receipt и второй use consumer. Generic private-source purpose/secret handoff остаётся `bridge_missing`, пока эти endpoints и predicates не замкнуты. Никакой новый универсальный permission service/DTO из этого требования не следует.

**First route не маскирует pagination gap.** @C `acquisition_executor.py` принимает narrow `worldbank.wdi` и проверяет `page == pages == 1`, отсутствие `has_more`/next token. Для первого A1 использовать эту declared single-response границу, не выдать её за checkpointed harvester. Ответ с продолжением должен отказать, а не усечь corpus. Следующий действительно paginated source выбирается именованным A1 extension: producer и durable page/cursor bridge пока `producer_missing`/`bridge_missing` в этой generic границе; тогда обязательны AP04 и crash/restart с missing/repeated pages. Preseed и runtime могут иметь разных native producers при едином capture/use contract.

**A4 rights before effect:** external issuer/controller/custodian предоставляет actual evidence; existing Legal/Lex/custody owner разрешает применимость source-specific основания, Runtime action owner связывает его с exact operation, security/secret owner исполняет, Fabric source owner проверяет до вызова. Это распределение ответственности, не утверждение, что generic resolver уже реализован. A0/A4 обязаны назвать существующие symbols или узкое owner extension; без producer→verifier→effect binding protected route не запускается. Credentials/terms shape не доказательство. Для query-only случая проверить разрешённый result и отсутствие запрещённых raw во всех временных и downstream копиях.

## 2. Что должен получить исполнитель

Для slice передать точный branch/tree, source contract/profile/version и permitted inputs; native owner/callers; требуемый consumer property; full code/test/public/generated companions; declared source-cut/rights/replay boundaries; actual deployment/config; deciding command outputs и negative/removal evidence. Правила и источники версии закрепить до проверки; historic `G_acceptance=false` не переписать при появлении нового consumer.

Исполнитель сначала пытается получить собственными средствами exact missing input: documented API, разрешённый export, existing controlled source, owner package или достаточную альтернативу. Если не может, объясняет какую способность/внешний акт недостаёт, какие каналы проверены и что продолжено без него. Не ждать research approval для исправления codec/pagination/wiring по существующему контракту; новую семантику или предел custody передавать G как конкретный выбор с миграцией и falsifier.

## 3. Deployment commissioning dossier

Перед реальным rollout заполнить в existing release/runbook owners:

- Named deployment unit/cell, actors/audiences и authoritative vs candidate scope; exact build, method/parser/rule/API/schema versions.
- Source profiles и actual grants: URL/driver/queries, schema/cut/continuity, authentication secret reference, allowed recipient/region/operations, quotas, rights/currentness watch, verified unsupported modes.
- Storage inventory всех durable/rebuildable/transient/copy placements: root/DSN/bucket/index/cache/spill/provider/export/backup, access/retention/deletion/restore owner. Не включать значения secrets.
- Workload mix и SLO с измерениями wall/RSS/bytes/IO/native threads/queue age; actual limits/quota/spill/recovery reserve. Все numeric settings — вывод для конкретного профиля, не универсальные defaults.
- Actual ingress/API/client, authn/authz/cell/step-up/delegation chain и отрицательные tests на каждую protected surface, включая metadata и failed-job readback.
- Capture→receipt→admission→fresh use, второй reuse-run, correction/revoke, crash/cancel и source/DB/CAS outage. Неподдержанные inputs/backends отдельны от failed product checks.
- Restore на quarantine, post-backup rights/history witness вне rollback closure, migration/cutover/rollback strategy и public currentness projection. Owner DB backup alone не общий restore.

Это будущий actual dossier, не требование построить универсальный commissioning service. Его нельзя заменить «kubectl apply succeeded», healthcheck, empty tests или карточками atlas.

## 4. Опровержимые свойства

| ID | Сценарий и distinguishing signal |
|---|---|
| AP01 | Preseed и runtime одного source дают одинаковый capture/use contract. Удалить runtime terminal receipt, оставить catalog label: fresh use отказывает, а candidate discovery остаётся честным. |
| AP02 | Вторая задача использует разрешённый saved source без повторного fetch; смена purpose/rights/profile не получает прежний allow из cache. |
| AP03 | HTTP304 без сохранившегося exact prior body не создаёт zero-row dataset; full refetch либо explicit unavailable. |
| AP04 | Для paginated source: mutation между page reads, crash/resume, missing/repeated page; stable snapshot сохраняется/отказывает по expiry, observed-sequence не проходит snapshot-required consumer. Single-page WDI вместо этого обязан отказать на more-pages response. |
| AP05 | LLM page injection/forged citation/неверный span не меняет tools/rights и не даёт source verification; source-domain query privacy проверяется отдельно. |
| AP06 | Закон меняется: historical `as_of`, future applicability, repeal exception и translation loss дают разные outcomes. Для notification-triggered act публикация без verified notification не устанавливает effect; wrong act/recipient receipt отказывает, later verified notice меняет только proper scope/time. No-hit в consolidated-text search не absence law, включая никогда не consolidated акт. |
| AP07 | Valid credential с absent/fake/expired/слишком узким grant даёт zero protected source calls. Query-only: запрещённые raw не появляются в CAS/logs/browser/provider temp; permitted output/receipt ограничивает replay; revoke до resume блокирует fetch/cache/export. |
| AP08 | Custodian computation: wrong snapshot/executable/recipient receipt не принимается; upstream unavailable сохраняет unknown effect и не вызывает blind repeated side effect. |
| AP09 | API/worker/store/cache/index/export не раскрывают чужую cell. Конкретный `GET /api/v1/control/jobs/{job_id}` с известным чужим ID не выдаёт progress/failure/artifact refs; foreign и nonexistent получают одну not-found projection. Изменить только target ownership, сохранив markers: caller tenant/opaque ID не заменяют owner check. |
| AP10 | Memory/disk/provider quota contention вызывает bounded defer/compatible plan; old worker/parent-held memory не исчезает по lease expiry. |
| AP11 | Backend migration/restore не возвращает revoked or obsolete generation как current; objects+owner heads+post-backup histories согласованы до serving. |
| AP12 | Новая definition/metric/source/profile поддержанного класса подключается через existing registries; неизвестная семантика остаётся candidate и требует owner extension, не generic `trusted=true`. |
| AP13 | Реальное institutional response получает original/source binding; draft, decorative signature и self-reported mandate не заменяют act/competence. |
| AP14 | Shared-source reuse и mixed-source derivative требуют verified full parent/output permission binding; отдельные occurrences/permissions сохраняются; replica/mirror study не удваивает independence; shared cache не раскрывает existence другому tenant. |
| AP15 | Cold/expired/unavailable derivative не возвращается как empty result. Rebuild применяет actual rights/model/source generation; lost raw не заменяется новым source без нового binding. |

AP — **условные gates для заявленных возможностей**, не 15 обязательных prerequisites первого A1. Первый single-response A1: AP01/02 и capture→receipt crash/refusal, AP09/14/15 на используемых surfaces и relevant resource envelope AP10; AP03 при HTTP revalidation, paginated AP04 при paginated extension, more-pages refusal сразу. A2: AP05; A3: AP06; A4: AP07/08; A5: AP09/10 и restore portion AP11, если заявлен restore; A6: backend/migration/scaling AP09–11/15; A7: AP13. AP12 проверяет расширяемость соответствующего source class, а AP14 включает mixed-source derived permission при появлении composition. Cross-cutting security/rights нельзя отложить, если соответствующая surface уже входит в выбранный slice. Остальные capability claims остаются out of supported scope до своей проверки.

Проверки должны вызывать настоящий owner path и fresh consumer; removal меняет property, оставляя markers. Первый реальный workload ограничен объявленным scope; второй отличается важным transport/semantic свойством и проверяет расширяемость без central family switch. Нагрузочные проверки — отдельный будущий этап с ресурсным admission; в данной работе они не запускались.

## 5. Root review и remaining decisions

Общий проект допускает несколько физических топологий, но выбирает одну logical custody/use модель. Rejected: global mirror по умолчанию; runtime data всегда ephemeral; metadata licence как licence всего content; universal law crawler; одинаковая semantic guarantee для всех connectors; cross-tenant hash cache; blind autoscaling; новый GroundService/общий scheduler; customer API token как upstream credential; сведение внешнего act к agent-generated документу.

Нужно решить при commissioning конкретного deployment: principal/cell, initial jurisdictions/source set, allowed processors/regions, available grants, SLO/RPO/RTO и бюджет. Это контекстные входы, не основания откладывать общие capture/store/consumer механизмы. Внешние акты, permission, source availability и institutional mandate система не может установить собственным декларативным выбором; она может проверить, запросить разрешённым способом либо найти достаточную альтернативу.

Нет новой обязательной правки system-design-decisions: проект детализирует existing custody/time/open-grammar позицию. [Ранее предложенный C03](../sdd-proposals/lifecycle-c03-20261021.md) всё ещё ожидает согласования. Если реализация потребует изменять authority/time semantics или иметь собственную sovereign institutional function, сначала представить конкретное новое решение G, не расширять scope исподволь.

## 6. Что изменено после независимых атак

Семь исследовательских разрезов и четыре независимых review направления: acquisition/legal, storage/reuse, deployment/access, skeptical integration. Root повторно проверил ключевые source snippets и official legal source, исправил проект и запросил bounded delta review. Provenance и точные ограничения проверок — в [receipt](../research-receipt-r8.json); это review документации, не runtime acceptance.

| Класс и атака | Ответ проекта | Что ещё должен доказать код |
|---|---|---|
| P05/P32: два допустимых inputs дают недопустимый join/output | Полная material-parent связь и admission именно transform/output/purpose/recipient; без универсального пересечения licence strings | AP14 для mixed-source result, индекса/embedding/model с явной границей unknown influence |
| P08/P10: authentic publication ошибочно подменяет notification | Act-specific rule→event→recipient→use, effect unknown без нужного факта; отдельная private custody notice | AP06, включая неверный адресат и historical/current distinction |
| P27/P31: single-page WDI выдан за paginated acquisition | Exact first-route scope, more-pages refusal; отдельный paginated producer/bridge; batch/runtime producers не обязаны совпадать | A1 и paginated extension раздельно |
| P05/P32: credentials/terms подменяют разрешение до source effect | Named institutional evidence→native legal/custody resolver→Runtime action→Fabric call; protected generic private route пока `bridge_missing` | AP07/08; реальный issuer/trust root, source-purpose и permitted output |
| P05/P38: caller tenant вместо target job owner | Статический finding на exact @C; owner-scoped read до serialization, не утверждение о проверенном live leak | Delta текущего candidate и AP09 |
| P01/P02/P37: external env/backend/HPA названы готовым deployment | Runner, common resource admission, remote tenant parity, secret resolution и air-gap обозначены как отдельные недоказанные цепочки | A5/A6 и selected profile commissioning |
| P13/P27: неопределённый integrator и все gates сразу | Один accountable Runtime integrator, native owners сохранены; gates по заявленному scope; remote A4 зависит от нужной части A5 | Complete first vertical и его callers/companions |

Composite-output reviewer выделил как отдельный новый класс этого review: composition-level rights не сводятся к direct cross-tenant read. Root сохраняет эту границу и закрывает её общим parent/output invariant внутри существующих P05/P32 owners. Остальные уточнения — ранее именованные классы на конкретных границах. Ни одно не требует нового универсального subsystem или бесконечной ladder repair. Ни один документальный ответ не закрывает product finding; недостающие bridges и execution evidence остаются явными.

Pattern pass: P01/P02/P03/P05/P07/P08/P10/P13/P14/P15/P25/P27/P29/P31/P32/P35/P37/P38/P40/P41. Source-presence findings — bounded static observations; ни один legacy gate FAIL не назван inherited без replay. Runtime acceptance, backend conformance, production inputs и deployment readiness остаются UNRUN/not established в границах этой работы.
