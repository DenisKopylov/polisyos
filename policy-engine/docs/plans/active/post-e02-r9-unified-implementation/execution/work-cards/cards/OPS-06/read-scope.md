# OPS-06.read-scope — Авторизовать объект до чтения и проекции

Группа: [G06 — Допустимость, полномочия и квалифицированные решения](../../groups/G06.md). Родитель: [OPS-06](../../parents/OPS-06.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Before content fetch or serialization, authenticated actor, target owner, tenant/cell, action and exact current grant authorize the specific job/artifact read and audience projection.

**Предпочтительное решение.** Route all actual job/control/artifact readers through existing authz middleware and target-owner decision/audit owner. Preserve equal not-found projection for foreign/absent IDs when existence is protected.

**Граница владельца.** Writes only the OPS-06 access decision/read-consumer family under `write:exact-path/{canonical_repo_path}`; exact direct/indirect readers and lease intersections are established after E02 rebind. NetworkPolicy, tenant labels and connector credentials are evidence inputs, never permission.

**Входы.** Authenticated actor and tenant/cell identity issuer; Resolved target owner/object and existence-disclosure rule; Current grant with issuer, content binding, purpose, recipient, audience and interval; OPS-03 selected-route readiness

**Выход и consumer.** Allowed/denied/limited read result plus authorized access receipt with exact decision, consumed before API projection; identity/raw paths stay out of metrics.

**Что можно готовить независимо.** Enumerate direct and indirect readers after source rebind; agree the grant/read interface and concealment rule. Actual returned bytes and projection require the owner-resolved decision before serialization.

**Где результат соединяется с другими.** Same-cell delegation is allowed only when grant says so. Source-effect release remains in `effect-release`; denied audit audience is separately controlled. Telemetry/cardinality overflow cannot prove a read was allowed.

**Positive.** Exact-grant same-cell sharing returns useful permitted content; authorized foreign and absent ids get the same protected existence projection.

**Distinguishing negative.** Cross-cell/object owner mismatch, missing/revoked grant, wrong audience, or sampled/overflowed telemetry cannot expose content or turn deny into allow.

**Matched removal.** Remove target-owner/scope resolution while keeping middleware/network markers; the forbidden fresh reader canary must fail.

**Граница контекста.** A read decision protects information emission. G06 is the home because the deciding property is authority; G08 is a downstream projection surface, not a second grant owner. P05/P31/P32/P37/P38 require actual content-bound consumer resolution.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Both planes rebind against actual E02 accepted readers and source/effect sinks; inherited parent stage and leases apply.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-01.commissioning](../../cards/OPS-01/commissioning.md) | `direct:owner_readiness`: Consume the selected source/use scope and commissioned audience/purpose boundaries.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-03.profile-readiness](../../cards/OPS-03/profile-readiness.md) | `direct:owner_readiness`: Consume only the readiness result for the selected route/profile, not source permission.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `OPS-06`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Direct result/preferred path for read-scope; selectors solution.implementation_steps[3] name the work and native owner seam.
  `solution.implementation_steps[3]`
- **join** — Distinguishing behavior, consumer surface, or acceptance evidence for read-scope; selectors solution.acceptance_discriminators[2] are checked at its actual reader/sink.
  `solution.acceptance_discriminators[2]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
