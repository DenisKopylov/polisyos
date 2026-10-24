# CAP-02.transport-boundary — Enforce destination policy at each network hop

Группа: [G09 — Развёртывание, исполнители, хранилища и ресурсы](../../groups/G09.md). Родитель: [CAP-02](../../parents/CAP-02.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Only an authorized exact target/attempt can be reached, including redirects, DNS resolution, credentials, and controlled proxies.

**Предпочтительное решение.** Extend the selected Fabric HTTP connector at RawHTTPResponseObserver to validate and bind scheme/host/port, resolved IPv4/IPv6 target, redirects, origin-scoped credentials and deployment egress at every hop; verify request-bound controlled-proxy enforcement at the actual boundary. Ask LIF-05 for exact placement permission before any covered write. Anchor: fabric/connectors/sources/http_base.py:RawHTTPResponseObserver.

**Граница владельца.** Existing Fabric HTTP transport/security seam and selected connector owner. Parent native lease family: `write:capture-protocol`, `resource:source/{source_profile}/fetch`. Exact post-E02 paths/overlap are unresolved; do not infer sibling disjointness or create a child lease. Root binds the actual path/lease before writes; cards sharing a native family serialize there.

**Входы.** Source contract/profile, exact request, per-hop target, credential audience, proxy enforcement evidence.

**Выход и consumer.** Allowed request or refusal with request-bound destination evidence.

**Что можно готовить независимо.** A0 selects source/caller and the profile's egress policy.

**Где результат соединяется с другими.** Enforce before every socket/effect; a permitted request proceeds to capture only after LIF-05 placement permission.

**Positive.** Authorized target with matching request-bound proxy evidence reaches the selected capture route.

**Distinguishing negative.** DNS rebinding, redirect to private metadata, credential hop, mismatched proxy receipt, or forwarding header is refused.

**Matched removal.** Remove target-result verification but keep proxy labels; forbidden-target probe must fail.

**Граница контекста.** The preferred solution combines four independently reviewable contexts: per-hop network policy, retained representation and reader, conditional continuation/fencing, and a selected second-source adapter. R19 adds exact-content binding; it does not make these transport/protocol properties one mechanism. This is one bounded property view; parent source pins, stage/dispatch, conditional acceptance and mandatory companions remain inherited.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted source/path owner is consumed where selected; no blanket barrier.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-01](../../parents/CAP-01.md) | `direct:owner_readiness; acceptance:composition`: Consume exact selected source/profile; query permission is not body placement or cursor completeness.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `CAP-02`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Enforce every hop at actual egress and bind request/attempt, resolved target, redirect, credential and authenticated proxy decision.
  `task.acceptance_steps[5]`; `solution.implementation_steps[0]`; `solution.implementation_steps[5]`; `solution.acceptance_discriminators[2]`; `solution.acceptance_discriminators[6]`
- **execute** — Verify the selected controlled-proxy decision is authenticated and request/attempt-bound to the resolved target, policy identity, redirects and credential audience at actual egress; proxy configuration or a proxy peer alone is not proof.
  `solution.composition_contracts[5]`
- **binding — subclause:** Resolve accepted source/endpoint, permitted proxy egress, credential audience and the actual DNS/socket enforcement point at E02.; source `solution.inputs_to_resolve[0]`. Primary fragment route stays unchanged; this identifies the owned sub-result.

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
