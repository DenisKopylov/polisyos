# TC-01: request TimeContext — выбранный cursor, не bundle всех времён

## 1. Выбор и owner

Reuse `core/contracts/runtime.py::TemporalScope` в `NaturalLanguageRunRequest.temporal_scope`. Он содержит **пять** компонентов: `valid_at`, `tx_at`, `branch`, `snapshot_id`, `scenario_id`. Все сохраняются; не сократить контракт до пары timestamp. Контекст NL запроса принадлежит runtime control/intake/lifecycle; underlying temporal query остаётся у существующего TemporalService и конкретного data owner. Не создавать новый temporal engine.

Смысл: что именно caller попросил использовать как temporal/scenario view. `valid_at` — valid-time cursor; `tx_at` — transaction/system-time cursor выбранного data owner. Они не являются временем policy intervention, периодом measurement или юридическим effective date. Transaction times разных независимых систем не объявляются одним глобальным commit clock: каждый provider связывает запрос со своей read snapshot/resolution, если поддерживает такую семантику.

Shared `TemporalScope` сейчас shape-typed, `extra="forbid"`, с optional fields. Строгие правила нового NL входа применяются **на NL boundary**, без глобального изменения dashboard/compare APIs. Python annotation может быть optional для legacy omission; explicit null проверяется по field presence, не теряется в default.

OpenAPI нового NL request описывает `temporal_scope` как **необязательное, но non-null при наличии** свойство; inner optional fields могут содержать null по таблице ниже. Runtime-validator и generated clients не должны расходиться из-за Python `Optional`. In-process API принимает typed aware datetime; HTTP принимает только объявленную wire форму, без permissive numeric coercion.

## 2. Request law v1

| Вход ordinary `POST /api/v1/control/runs/nl` | Решение |
|---|---|
| `temporal_scope` отсутствует | Старый request wire/snapshot сохраняется. Нет выбранного request cursor, нельзя объявить эту binding установленной. Candidate работа допустима с существующей limitation. |
| Top-level `temporal_scope:null` | Typed 422 refusal: explicit-null selection не определена в v1. Не маскировать как omission. |
| `{}` или только null-компоненты | Typed 422 empty-selection refusal. Не превращать в current/latest. |
| Непустой partial scope | Допустить точный выбор. Отсутствующие оси остаются неизвестными; конкретный consumer решает, достаточен ли имеющийся cursor для его операции. |
| Например `{"valid_at":"2026-01-01T00:00:00Z","tx_at":null}` | Допустить explicit unknown `tx_at`; сохранить присутствие ключа. Это не запрос “выбери tx_at автоматически”. |
| Snapshot/branch/scenario без timestamp | Допустить meaningful selection; проверить идентичность, доступ и поддержку у фактического consumer. Не выдумывать timestamps из имени, `created_at` или publication time. |
| Extra fields, wrong types, пустые/whitespace-only selectors | Typed 422. Не выполнять coercion объекта/числа в selector. Не делать silent trimming, меняющий непустой identifier. |

Timestamp wire — RFC 3339 instant с явно указанным offset, в реально поддерживаемой точности (текущий Python datetime — microseconds). Принимаемые instants normalize в UTC без потери точности. Naive/date-only/numeric epoch coercion, leap second или недоступная точность отказывают, не округляются. Offset `-00:00` может задавать известный UTC instant с неизвестным local offset; нормализация instant допустима, но не даёт права утверждать local timezone. Сохранение original lexical bytes — отдельный raw request audit, не обещание этого normalized cursor.

Нет глобального правила `valid_at <= tx_at`, запрета future valid time или обязательной пары времён. Будущий valid cursor может выбирать уже известный scheduled fact; это само по себе не прогноз. Civil/legal dates и timezone rules не переводятся автоматически в midnight UTC. `now/latest/current` не вводятся как timestamp shortcuts. Если позже понадобится convenience selection, она получает explicit owner/version, одноразовую persisted resolution и declared policy; это не default нынешнего контракта.

Несколько selectors проверяются совместно. Branch+snapshot/scenario contradiction — typed refusal/limitation фактического owner, без silent precedence. Неподдержанный `scenario_id` сохраняется в requested intent, но scenario-dependent execution не выдаётся за honoured: current query mapping не прокидывает его в world query. Можно продолжить независимую candidate работу, явно ограничив непокрытую часть.

## 3. Artifact, request binding и time roles

Выбран новый artifact contract **в существующем runtime owner**, не новая подсистема:

- kind `runtime.temporal_scope`;
- schema `polisyos.runtime.TemporalScope`, version `1.0`;
- media type `application/json`;
- payload — normalized `TemporalScope` JSON mapping, сохранённый с field presence: omit unset, **не** omit explicit null. Никакого field `authority=true`;
- canonical profile — explicit уже поддержанный Core spec; `.3` не требуется. ArtifactRef содержит exact selected manifest profile;
- producer/contract/reader регистрации принадлежат Runtime. Наличие schema label в prototype не считается их регистрацией.

Artifact admission повторно проверяет эту **NL selection law**, включая meaningful nonempty scope, aware timestamps и сохранность presence; одной shared `TemporalScope.model_validate({})` недостаточно. Payload/schema conformance, authorized snapshot binding и actual execution — разные проверки.

Provenance связывает artifact с авторизованным request snapshot/intent, job/run/tenant/cell и реальным producer event через существующие manifest/control-store механизмы. Если snapshot хранится в control store, использовать его typed record identity + verified content hash/version; не изобретать CAS ref для не-CAS record. Не копировать полный prompt/context в temporal payload ради provenance. Same cursor payload может дедуплицироваться; его использование в конкретном run всё равно проверяет owner binding и scope.

Различать **requested cursor** и **resolved read basis**. Artifact выше фиксирует запрос. Каждый temporal data consumer фиксирует реально выбранный snapshot/view и interpretation rule в своих существующих receipts/input edges. Snapshot может дать фактически проверенную effective read basis, но не дописывает задним числом неизвестное поле caller intent. Mere recording scope не доказывает, что query его использовал.

Mutable selector (например branch name) разрешается owner в immutable read basis **до её первого потребления**. Retry использует сохранённую resolution, не новый head этого branch. Если provider не умеет зафиксировать такой read, replay/authority claim остаётся limited; наличие валидного имени branch не доказывает reproducibility. У нескольких providers нет выдуманного общего transaction clock: каждый сохраняет свою фактическую resolution и несогласованность между ними, если она существенна для claim.

| Сущность | Семантика / источник | Что не подменяет |
|---|---|---|
| Request `TemporalScope` | Caller-selected view; request values — `consumer_asserted` intent | World truth, policy time, legal admissibility |
| Runtime materialization + request binding | Проверенное совпадение с авторизованным snapshot — `recomputed` | Истинность caller assumptions |
| Resolved data view | Owner-resolved exact input, actual query semantics и availability | Все остальные temporal domains |
| `PolicyIntentEnvelope.policy_time` | Intended policy period | Transaction cursor |
| `DataRequirementScope.time/time_role` | Claim-bound measurement/requirement | Legal effective date |
| Legal snapshot / valid time | Lex-owned evidence и собственный admission | Request preference |
| Source/observed/recorded/publication times | Существующие отдельные роли | “Доказанный current world” по одному timestamp |

`context.as_of`, LLM-extracted dates и `as_of_time/generated_at` публикации не заполняют request scope. Legacy `context.as_of` может продолжать свою **прежнюю** роль; противоречие между разными ролями не лечится автоматическим overwrite. Любая смена role требует явного authorized intent и owner interpretation.

## 4. Полная цепочка и snapshot migration

1. Intake валидирует новый scope; existing authorization оценивает действие и selectors в текущем tenant/cell. Past `tx_at` не даёт исторических прав доступа.
2. `job_attempt_publication.py` включает поле в **новый** `polisyos.runtime.control_nl_request_snapshot.v3`, request-content hash, execution-intent/authorization binding и replay validation. Если поле отсутствует, schema selection и serialized fields v1/v2 остаются побайтно прежними. Поле нельзя автоматически добавить как `null` в legacy `model_dump`.
3. Existing digest profile `polisyos.runtime.authorization.nl_request_snapshot.canonical_json.v1` сохраняется, если сами canonicalization rules не меняются. Snapshot schema v3 меняет signed content, не объявляет новый hash алгоритм. Replays старых версий используют свои field projections; v3 использует собственную полную projection, не “V2 плюс всё неизвестное”.
4. `run_lifecycle.py` переносит scope с presence semantics в persisted queued payload. Authorization snapshot↔payload comparison включает его полностью. Worker revalidates exact authorized request; не принимает changed/re-dumped scope из mutable context.
5. Runtime producer материализует artifact, selected profile, binding/provenance; CAS write и control-store linkage используют существующий idempotent publication/recovery. Сбой между ними не делает частично опубликованный closure authoritative. Retry восстанавливает тот же selected request/view; новые now/profile/latest не выбираются.
6. NL pipeline передаёт его в `RunIntentBinding` и новый [SameInputClosure](03-exact-view-closure.md), плюс связывает actual consumed read basis. Удаление DTO→queue или queue→consumer bridge должно ломать acceptance.
7. Fresh `/api/v1/control/jobs/{job_id}` отдаёт typed `runtime_quality_artifact_refs` и binding/limitation. Отдельный fresh `/api/v1/artifacts/{artifact_id}` с `manifest_profile_sha256` читает **ту же** view. `/runs/...` temporal browse projection и GET filters сами по себе не доказывают исходный request cursor и не меняют persisted execution intent.

OpenAPI/generated clients/browser form и error/status projection — companions нового поля; существующие clients без поля остаются valid legacy requests. UI не обязан вводить все temporal роли: нужен explicit optional selection, видимое отсутствие/partial scope и корректный roundtrip. Не генерировать default cursor от часов браузера.

## 5. Status, authority и недоступность

ADR-0148 требует записанный time context для соответствующей intent binding. Meaningful partial scope может доказывать **что именно выбрано**, но не достаточность всех осей. Нельзя объявить intent_bound на пустом artifact или string ref. Нельзя требовать legal snapshot только для доказательства равенства request/input identity; **Lex barrier отдельно блокирует legal-dependent claim**, если юридического основания нет.

Ни `status="closed"` в input closure, ни заполненный time ref не выбирают authority role автоматически. Role выбирается после existing independent producer/admission/purpose/adequacy checks. Состояние “input identity проверено, legal admissibility unavailable” корректно и должно быть видно на surface.

Историческая snapshot могла быть удалена retention, отсутствовать offline или оказаться недоступной по текущему ACL. Отличать unavailable/forbidden/unsupported от подтверждённого empty result. Не повторять запрос к “current” как fallback. Нет universal requirement хранить любую историю бесконечно; воспроизводимость конкретной подписи ограничивается declared retention/custody, а потеря требуемого основания вызывает существующий limitation/revalidation flow.

## 6. Что действительно зависит от внешних inputs

Wire/queue/producer/reader/closure tests выполняются на контролируемых temporal fixtures без production data. Authentic claims требуют реально доступных named snapshots, tenant access, provider time semantics, legal facts и owner evidence там, где это нужно для конкретного claim. Их нельзя создать выбором G. Отсутствие этих inputs не блокирует реализацию bridge и его independent falsifiers.

Capability gaps на pinned source: typed NL producer/artifact/bridge пока отсутствуют для этой цепочки; public exact-profile artifact reader уже есть и переиспользуется. Нужны `producer_missing`, `artifact_missing`, `bridge_missing`, `verification_missing`, `semantic_test_missing` repairs, а не новая временная онтология.
