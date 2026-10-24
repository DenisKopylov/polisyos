# OPS-12.no-egress — Доказывать no-egress на реальной границе

Группа: [G09 — Развёртывание, исполнители, хранилища и ресурсы](../../groups/G09.md). Родитель: [OPS-12](../../parents/OPS-12.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** For a selected offline cell, no unapproved network route transmits source data, secrets or telemetry beyond the declared host boundary; application setting alone never establishes this.

**Предпочтительное решение.** Use the institution’s actual host/network firewall and independent observed traffic on all interfaces, DNS, update, telemetry, crash, maintenance and provider routes. PolicyOS consumes the evidence contract; it does not own the institution’s perimeter controls.

**Граница владельца.** Any product-side configuration stays with existing deployment/network owner under its own exact path lease; this OPS-12 card is a verification result under parent `write:exact-path/{canonical_repo_path}` only if that owned path is changed. Exact overlap is re-resolved after E02, not assumed.

**Входы.** Selected offline host/network interface inventory; Institution security owner’s deny-by-default configuration and network observer; Actual update, DNS, telemetry, crash and maintenance traffic during selected profile

**Выход и consumer.** Observed no-egress verification result with boundary, test window and unresolved routes, consumed by offline commissioning/operator surface.

**Что можно готовить независимо.** The observer and profile can be prepared before code; no-egress claim remains unavailable until actual selected host traffic is observed under the full route inventory.

**Где результат соединяется с другими.** Network boundary evidence composes with but is not replaced by bundle signature, application egress flag, source grant or remote provider selection.

**Positive.** No unapproved route emits bytes during measured selected operations and all declared interfaces/maintenance paths are covered.

**Distinguishing negative.** Any covert egress, untested interface or hidden update/crash route means no-egress is not established and affected offline claim is limited.

**Matched removal.** Remove physical deny/traffic observation but retain app setting and profile markers; network discriminator detects the route.

**Граница контекста.** No-egress is an external boundary fact under institution security ownership; this verification card appoints no supplier. P37/P38 require independent observation and a divergent-route falsifier.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted-source rebind and conditional profile choice remain parent stage conditions; local profile can proceed without cloud-profile completion.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `OPS-12`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **binding** — Binding scope, authority, migration, time, input, or lifecycle constraint for no-egress; selectors solution.composition_contracts[1], solution.inputs_to_resolve[2] remain load-bearing.
  `solution.composition_contracts[1]`; `solution.inputs_to_resolve[2]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
