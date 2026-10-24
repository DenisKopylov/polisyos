# UI-02.private-egress — Фильтровать private data до persistence и egress

Группа: [G09 — Развёртывание, исполнители, хранилища и ресурсы](../../groups/G09.md). Родитель: [UI-02](../../parents/UI-02.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Private fields/identifiers не выходят через public request, telemetry, beacon, fetch failure или error; classification/redaction происходит до signed persistence.

**Предпочтительное решение.** Переиспользовать actual public route, privacy policy и все selected egress builders: route/query/tags/breadcrumbs/extras/beacon/fetch/error.

**Граница владельца.** UI-02 владеет selected egress classification; telemetry policy/destination и rights facts остаются у native owners; no new subsystem.  Parent native canonical leases: write:exact-path/{canonical_repo_path}; write:runtime-api-generated-family if changed; resource:browser/{profile} if executed. Bind exact paths and overlap at P0; unresolved paths are not presumed disjoint before E02 rebind.

**Входы.** Owner-approved self-hosted/scrubbed/absent telemetry policy, полный selected builder denominator, nested/encoded canary.

**Выход и consumer.** Egress/persistence witness показывает allowed scrubbed/absent telemetry и отсутствие private canary во всех selected sinks.

**Что можно готовить независимо.** Можно перечислить builders и подготовить canary до complete source binding; bind exact paths and policy at P0.

**Где результат соединяется с другими.** Свести реальный built route с public-record output; allowlisted destination не доказывает content eligibility.

**Positive.** Разрешённая telemetry следует принятой policy; private canary не достигает sink/persistence.

**Distinguishing negative.** Nested/encoded private value выходит в разрешённый destination или signed record.

**Matched removal.** Убрать classification/projection при сохранённых markers: actual egress canary ловит leak.

**Граница контекста.** Все transport exits остаются одним pre-persistence property; census строится от actual emitters.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source identity/commit and source-bound acceptance record used when rebinding this card; original parent dispatch/stage remains authoritative.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [UI-02.public-record](../../cards/UI-02/public-record.md) | Consume only for the exact composition described here: Свести реальный built route с public-record output; allowlisted destination не доказывает content eligibility. This link is not an unconditional all-of or preparation gate. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `UI-02`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Names all actual request/telemetry/beacon/fetch/error exits and requires private classification before persistence. Source selectors: solution.implementation_steps[3].
  `solution.implementation_steps[3]`
- **binding** — P38 case is private telemetry escape despite intact signature/badge; bind the real egress property. Source selectors: solution.composition_contracts[2].
  `solution.composition_contracts[2]`
- **binding** — A new exporter changes complete pre-persistence egress denominator. Source selectors: solution.deviation_triggers[2].
  `solution.deviation_triggers[2]`
- **binding** — Records a real owner input or its conditional use; it appoints no missing producer. Source selectors: solution.inputs_to_resolve[2].
  `solution.inputs_to_resolve[2]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
