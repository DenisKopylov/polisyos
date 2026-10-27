# Реализация: порядок, responsibility и deciding checks

Все проверки ниже — **план acceptance, UNRUN в этой архитектурной работе**. Не смешивать с прежними prototype receipts. Исполнитель начинает с delta относительно source `7a4c713186188f5795da3a8745e42843443dcd88`, а затем фиксирует свой exact candidate/tree и actual read/write denominator. Уже завершённые unrelated E02 работы не переоткрываются.

## CAN workstream

| Шаг | Canonical writer / первые действия | Done signal |
|---|---|---|
| C-A — grammar и selected-version readers | Common codec + Core/IR facades/profile adapters. Зафиксировать `.2` golden behavior; реализовать отдельную `.3` branch, escape, descriptor types и explicit version dispatch. | C01–C06. Public exception identities сохранены; unknown profile не угадывается. |
| C-B — state persistence cohort | Scientist execution-state/executor/checkpoint/context owners. Перечислить все writers и direct readers конкретных state/outcome schemas; переводить на exact profile read до writer enable. | C07–C09; sync/async, resume и fresh process действительно читают `.3`. |
| C-C — cache cohort | Foundry specialization и existing compiler-cache owner; NodeResultCache owner для его отдельной law. Устранить preconversion alias, domain-version keys, проверить single-flight/generation и durable retry semantics. | C10–C13. Старый warm cache не пересекается с новой law; typed refusal не уходит в fallback. |
| C-D — release contract | Existing package/public-surface owners. Reader compatibility, installed/no-checkout checks, docs и versioned examples. | C14. New writers включаются только для готовых cohorts; rollback сохраняет readers. |

C-B/C-C preparation и tests можно проектировать параллельно с C-A; actual composed PASS зависит от C-A source freeze. Разные files не требуют глобального lock, но shared codec/manifest contracts имеют одного writer. Не создавать общий ожидательный барьер для всего E02.

### CAN acceptance

| ID | Реальная проверка / противоположный сигнал |
|---|---|
| C01 | Root/nested/list-contained raw mappings с `_type` round-trip как mappings. Cases выводятся из owner type policies плюс future/unknown/nonstring/null `_type`, не только из исторических семи имён. |
| C02 | Raw map с точным shape нового escape; глубоко вложенный escape-shaped raw value; nested **native** Decimal рядом с raw decimal map. Типы не смешиваются, root не redispatch. |
| C03 | Dataclass/Pydantic projection `_type` — data; carrier — typed representation. Removal общей projection policy при сохранённых marker names делает тест FAIL. |
| C04 | Core native и descriptor decode/re-encode exact; IR принимает structural maps, но отказывает на unescaped Core-only descriptors. `.2` bytes/IDs/return behavior неизменны. |
| C05 | Reversed insertion order → одинаковые `.3` bytes. Duplicate JSON names, duplicate/nonstring/unsorted entries, extra wrapper field, broken pair, wrapper без `_type` в реконструируемой map → typed refusal. Unknown/malformed tag внутри escaped data сохраняется. |
| C06 | Explicit cohort resource-policy/version → actual budget vector; Core `CoreJsonReadLimits` lexical bounds и отдельный `CanonSpec` logical depth. На лимите/сверх него для escaped map, реальный overhead, typed refusal **до** cache/persistence effects. Missing budget binding не включает writer; unsupported version не fallback. Нет unbounded expansion или смены смысла существующих limits. |
| C07 | Реальный admitted ExperimentState → sync executor persistence → fresh selected-profile read сохраняет raw map и native value раздельно. |
| C08 | Отдельно async executor и реальные outcome readers; не переносить результат sync на async по сходству кода. Удаление selected-version wiring ломает fresh read. |
| C09 | Checkpoint snapshot/delta → новый процесс/resume; смешанная история `.2` и `.3` использует собственные profiles. Unknown/stripped/substituted profile не даёт trusted replay. |
| C10 | Foundry `_convert_value_for_canonical` → static hash → specialization/cache lookup различает raw decimal map/native Decimal, raw descriptor/actual array, float carrier/raw float-shaped map. Signed zero остаётся различимым по выбранной Foundry law. |
| C11 | Preload old colliding entry; new law не возвращает его, включая случай неизменных native bytes. Старый in-flight producer не публикуется в new generation. Не проверять лишь различие hash strings без cache consumer. |
| C12 | Real NodeResultCache key/write/read/journal proof/reuse: version disagreement обнаруживается. Retry/restart не выполняет повторный external effect из-за произвольного нового key. Старый journal проверяется старой law. |
| C13 | Вызванная через настоящий hash path canonical/profile/resource refusal достигает caller. Удаление refusal propagation при сохранённом `CanonSpec.version` делает negative FAIL; JSON fallback не выдаёт key. |
| C14 | Installed package без source checkout: declared `.2` и `.3`, state и cache cohort, writer-disabled rollback reader. Public API docs и generated consumers соответствуют actual signature/profile. |

## TC / closure workstream

| Шаг | Canonical writer / первые действия | Done signal |
|---|---|---|
| T-A — intent wire | Runtime control DTO/intake/snapshot/lifecycle. Новое optional поле с presence law, snapshot v3, old v1/v2 exact replay, authorized queue bridge. | T01–T05. Поле нельзя потерять или заменить после authorization. |
| T-B — typed closure | Runtime-quality owner, один согласованный Core manifest companion. V2 identities, registry-derived inventory, real resolver, digest projection, seals, actual scorecard/authority consumers. | I01–I12. Pure equality нигде не заменяет protected admission. |
| T-C — persisted request и execution | Runtime lifecycle/NL producer + existing temporal/data owners. Artifact/schema/producer registration, request linkage, requested vs actually resolved view, recovery. | T06–T12. Intent не объявлен executed только по наличию artifact. |
| T-D — ordinary surfaces | Existing control/artifact HTTP, OpenAPI/clients/browser. Scope and exact refs в fresh GET, actor/tenant isolation, status explanations. | T13–T16. HTTP chain и independent legal barrier проверены. |

T-A и T-B независимы до wiring; T-C зависит от обоих для authority-grade closure. Нет зависимости TC→CAN `.3`, нет зависимости generic bridge→authentic production inputs. Конкретные authentic legal/data checks остаются отдельными bounded tasks.

### TC acceptance

| ID | Реальная проверка / противоположный сигнал |
|---|---|
| T01 | Ordinary POST: omission остаётся legacy/unbound; top null, empty/all-null, wrong types/extra fields отказывают. Generated OpenAPI/client contract допускает отсутствие и исключает top-level null; inner null/presence согласованы с DTO. Empty/all-null отдельно проверяются server-side. |
| T02 | Aware timestamp normalization без утраты точности; naive/date-only/epoch/неподдержанный leap second/precision отказ; нет implicit now. Future valid и независимый tx допустимы согласно owner, без forecast claim. |
| T03 | Old v1/v2 snapshot bytes/hash/authorization replay после DTO extension неизменны. New scope выбирает v3; nested unset и explicit null сохраняются в snapshot. Scope mutation, removal, field injection или presence drift между signed snapshot и queued payload отказывают. |
| T04 | POST idempotency/retry сохраняет исходный authorized request/view. Изменение scope при попытке повторно использовать тот же authorized intent обнаруживается, не становится silent retry. |
| T05 | Удалить DTO→queue передачу, оставив поле в schema/OpenAPI: testcase FAIL. Отдельно удалить queue→worker read: testcase FAIL. |
| T06 | Runtime producer сохраняет scope под exact profile с nested unset/null, реальным registered producer/schema и binding к authorized snapshot. Empty artifact не проходит простым shared-model parse. Forged ref/producer/tenant/ref-role отказывают. |
| T07 | Сбой после artifact write до control linkage, затем recovery: нет duplicate semantic intent, неправильного “closed” или выбора нового cursor. |
| T08 | Same valid_at / early vs late tx_at на контролируемом late-correction dataset меняет именно фактический read/result; простого echo request недостаточно. |
| T09 | Snapshot-only и one-axis scope: selector реально honoured, неизвестная ось не придумывается. Consumer, которому её не хватает, даёт точную limitation. |
| T10 | Branch+snapshot contradiction, unavailable branch и unsupported scenario не молча заменяются default world. Mutable branch разрешён в immutable basis до consume; retry после движения branch head не выбирает новую. При поддержанном scenario его изменение влияет на выбранный read basis. |
| T11 | Historical retention loss/offline/permission denial отличаются от verified empty dataset. Runtime не подменяет данные current view. |
| T12 | `context.as_of`/LLM date без typed scope не создают time binding; отличающиеся publication/measurement/legal time roles не переписывают request. |
| T13 | Ordinary POST → authorization snapshot → queue/worker → temporal producer → actual consumer → closure → **fresh process** job GET → artifact GET exact profile. Проверяется input/result identity, не только response field presence. |
| T14 | Browse GET filter меняет лишь проекцию запроса чтения; persisted request cursor и авторизованная execution basis не меняются. |
| T15 | Cross-tenant/branch ref и expired permission отказывают по current access law, даже при прошлом tx_at. ACL epoch не считается частью неизменных payload bytes. |
| T16 | Partial/absent legal evidence: input identity может быть verified, но Lex-dependent authority остаётся blocked. Заполнение time ref или forged `closed` marker не повышает authority role. |

### Shared closure acceptance

| ID | Реальная проверка / противоположный сигнал |
|---|---|
| I01 | Две verified views одного payload ID с разными manifest profiles → mismatch; при одинаковой view equality. Повторить для каждого schema-derived CAS member, не только time. |
| I02 | Same ID/profile с неверным declared kind/media/role/schema/producer → refusal по resolver, не string equality. |
| I03 | Одинаковый заявленный hash при изменённом `evidence_input_refs`, отсутствующем/лишнем decisive input или изменённом role → FAIL. Хэш пересчитывается независимо. |
| I04 | Непустой forged digest, заявленные predicate_class/closed markers и отсутствующий real resolver не проходят scorecard/authority consumer. Removal resolver при сохранённых markers ломает проверку. |
| I05 | Symbolic effective-mode owner value остаётся non-CAS. Unknown domain либо символическая строка в CAS role не отмывается prefix guess. |
| I06 | Actual consumed basis сверяется с producer input edges и trusted required inventory. Удаление потреблённого input из декларации обнаруживается; незарегистрированная decisive dependency не становится nondecisive caller flag. |
| I07 | Ordered refs сохраняют порядок/multiplicity; owner-set refs отвергают duplicate key. Same artifact под разными roles не склеивается. Изменение meaningful order обнаруживается. |
| I08 | Request/run/job/tenant/cell substitution обнаруживается. Разные locators и разные output-report producers одной verified basis не вызывают ложный semantic mismatch; linkage и provenance всё равно проверяются. |
| I09 | Digest не зависит от собственного hash/status/generated_at/output/seal. Production output не нужен, чтобы построить input basis; нет циклического hash. |
| I10 | Existing consumed-input seals/reuse используют новую verified identity. Повторная загрузка сериализованного `verified=true` или string resolved_identity не обходит admission. |
| I11 | Legacy readable, но не молча v2-authoritative; ambiguity/no retained view → explicit limitation. New envelope/report/manifest summaries согласованы с полной closure, stripped profile обнаруживается. |
| I12 | Actual scorecard, role-selection и sibling protected consumers проходят один verifier; memoization не переносит разрешение между tenant/purpose/revocation epochs. Removal у любого mapped consumer даёт негативный signal. |

## Обязательные companions, отчёт и stop rule

До включения writers перечислить actual consumers выбранных contract versions: native facades, direct decoders, artifact IO, runner/engine readers, replay/snapshot readers, cache keys/journal, runtime-quality registry/envelopes/seals/scorecard, public/generated surfaces и importer tests. Этот bounded census — engineering deliverable; в данной работе repo-wide completeness не заявлена.

Запускать affected native/installed и behavioral/removal checks после независимого source review. Сохранять полные deciding outputs ignored, tracked — compact receipts с exact source/tree/profile/input IDs. Не складывать test totals пересекающихся suites. Quality FAIL не называть inherited без P41 base replay и полного denominator; при отсутствии replay — `not_established`.

Общие source/profile/consumer companions нельзя выкинуть ради лимита paths. Но artifact publication, external data truth и formal G closure не присоединять к codec/request fix как недостижимый universal gate. Интеграционный отчёт отдельно показывает: implementation accepted; capabilities actually demonstrated; external inputs unavailable; known limitations; gates UNRUN/FAIL/SKIP; findings adjudication.

Новый контрпример классифицируется по свойству. Дубликат типа raw-map collision или selected-view underbinding — тот же класс, закрываемый shared mechanism. Если новый пример выходит из объявленного value/owner/authority domain, явно назвать residual и минимальную недостающую capability, а не начинать бесконечную repair ladder.
