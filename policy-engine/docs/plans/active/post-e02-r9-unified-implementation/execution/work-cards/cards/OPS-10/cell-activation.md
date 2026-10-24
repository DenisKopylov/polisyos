# OPS-10.cell-activation — Включать multi-cell только по обоснованной цели

Группа: [G09 — Развёртывание, исполнители, хранилища и ресурсы](../../groups/G09.md). Родитель: [OPS-10](../../parents/OPS-10.md). Роль: `coordination`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** The original applicability decision controls the tier. A genuinely unselected conditional tier is recorded with its trigger and no parity claim; a selected or mandatory tier whose objective/evidence is missing remains limited or blocked pending resolution and cannot be deselected to avoid its inputs.

**Предпочтительное решение.** Reuse deployment-topology, OPS-03 readiness, OPS-04 worker profile and OPS-08 measured envelope. Compare the simplest suitable local/remote alternative; do not require universal cloud or local vertical exhaustion for a custody/failure-domain need.

**Граница владельца.** This is activation coordination under parent scope only; any topology/profile edit remains with its existing release/deployment owner and the parent canonical lease is resolved after E02. It does not own CAS adapter paths, scheduler or provider identity.

**Входы.** Original source-bound applicability/selection decision, trigger and named service/custody/topology/availability/scale/cost objective with owner approval; OPS-03 observed selected cell readiness; OPS-04 supported worker/API profile; OPS-08 measured resource envelope; OPS-10 exact adapter evidence if remote storage is selected

**Выход и consumer.** For an actually selected tier, a qualified activation decision and measured target receipt for the deployment owner and readiness surface; for a genuinely unselected conditional tier, its original trigger and no-parity limitation. A selected/mandatory tier missing objective or evidence stays limited/blocked, not unselected.

**Что можно готовить независимо.** Objective comparison and profile contract can be prepared without unrelated capacity exhaustion. Activation requires the source-bound selected-tier decision, an owner-approved objective and all exact activated-consumer evidence; missing selected-tier inputs remain a hold.

**Где результат соединяется с другими.** A remote adapter can be tested independently; actual multi-cell readiness composes adapter + worker + profile + capacity only if chosen. The original applicability decision controls: an unselected conditional tier is not PASS or obligation closure, and a selected/mandatory tier cannot be made unselected to bypass missing evidence.

**Positive.** A source-bound selection with a named objective chooses the simplest qualifying topology and measured replica/worker profile; exact route works in the fresh cell consumer. A genuinely unselected conditional tier retains its trigger and makes no parity claim.

**Distinguishing negative.** Missing objective/evidence for a selected or mandatory tier is limited/blocked pending resolution; re-labeling it unselected does not clear the hold. Replica count or backend label without objective, operator, supported resource envelope or fresh readiness does not activate; local completion never implies cloud parity.

**Matched removal.** Remove the original selection/applicability, objective and actual-readiness checks while keeping deployment replicas/backend labels; selected activation must remain limited/blocked, while an originally unselected tier retains its trigger and no-parity limitation.

**Граница контекста.** Remote activation remains conditional under OPS-10 override. No global cloud barrier, compulsory vertical-exhaustion rule or new scheduler; final owner resolves original applicability.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted-source rebind and selected-tier stage remain parent rules; do not require cloud profile for local scopes.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-03.profile-readiness](../../cards/OPS-03/profile-readiness.md) | `direct:owner_readiness`: Consume actual selected backend/cell readiness only for activated operation.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-04.external-runner](../../cards/OPS-04/external-runner.md) | `direct:owner_readiness`: Consume the selected supported worker/API profile for replica activation.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-08](../../parents/OPS-08.md) | `direct:owner_readiness`: Use measured remote request and host/replica capacity for the selected class only.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [OPS-10.remote-cas](../../cards/OPS-10/remote-cas.md) | Only for the selected same-scope composition described by this card: A remote adapter can be tested independently; actual multi-cell readiness composes adapter + worker + profile + capacity only if chosen. The original applicability decision controls: an unselected conditional tier is not PASS or obligation closure, and a selected/mandatory tier cannot be made unselected to bypass missing evidence. Independent output production/preparation remains allowed; the original parent join reconciles all required outcomes without making this list an all-of. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `OPS-10`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **binding** — Binding scope, authority, migration, time, input, or lifecycle constraint for cell-activation; selectors solution.deviation_triggers[0], solution.inputs_to_resolve[1] remain load-bearing.
  `solution.deviation_triggers[0]`; `solution.inputs_to_resolve[1]`
- **execute** — Direct result/preferred path for cell-activation; selectors solution.implementation_steps[0] name the work and native owner seam.
  `solution.implementation_steps[0]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
