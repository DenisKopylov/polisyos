# LIF-02.bounded_observation_order — Сохранить observation без synthetic event

Группа: [G07 — Долгая custody: актуальность, права и переиздание](../../groups/G07.md). Родитель: [LIF-02](../../parents/LIF-02.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** No-feed basis binds CAP04 to CAP02 root/profile/coverage and ordered attempt/head; never fabricates event.

**Предпочтительное решение.** Use existing bounded observation receipt and same Claim owner; qualified own assessment needs no webhook.

**Граница владельца.** Same LIF02 lease; CAP owns observation receipt, LIF02 reaction/order.

**Входы.** CAP04 observation, CAP02 root, profile/coverage, attempt/head and qualified own assessment.

**Выход и consumer.** Persisted local observation/order read by currentness consumer.

**Что можно готовить независимо.** Observation is separate evidence basis.

**Где результат соединяется с другими.** Fresh currentness readers use this local observation/as-of path only when the qualified no-feed route is selected; it never establishes native event continuity.

**Positive.** Pre-enrollment observation replays; A/B/A or delayed A cannot clear B.

**Distinguishing negative.** Partial poll or missing local head is not event/no-change.

**Matched removal.** Remove attempt/order binding, retain labels; stale A-after-B fails.

**Граница контекста.** One observable property; other owners remain suppliers/consumers.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Root preserves stage.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-04](../../parents/CAP-04.md) | `acceptance:composition`: Actual selected output is consumed by the local composition reader; acceptance is composition-only, not a preparation prerequisite.<br>Source: `task.acceptance_dependencies[0]`.<br>Условия: selected parent composed claim; not a new preparation dependency |
| Supplier [LIF-09](../../parents/LIF-09.md) | `acceptance:composition`: Actual selected output is consumed by the local composition reader; acceptance is composition-only, not a preparation prerequisite.<br>Source: `task.acceptance_dependencies[1]`.<br>Условия: selected parent composed claim; not a new preparation dependency |
| Composition output (не start gate) [LIF-02.native_event_replay](../../cards/LIF-02/native_event_replay.md) | Only when a qualified native source-event route is selected; the observation path neither supplements nor repairs native replay continuity. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `LIF-02`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Pre-enrollment CAP04 observation and poll A/B ordering.
  `task.acceptance_steps[4]`; `task.acceptance_steps[5]`
- **execute** — No-feed receipt/root/order.
  `solution.implementation_steps[4]`; `solution.implementation_steps[5]`
- **binding** — CAP04 event or observation alternatives converge on same owner; only observation route here.
  `solution.composition_contracts[3]`
- **execute** — No-feed and poll ordering.
  `solution.acceptance_discriminators[3]`; `solution.acceptance_discriminators[4]`
- **execute** — task.r19_extension.question_slices[1] crosswalks by actual value to question_ids[0]. Qualified own-assessment drift without a webhook is an observation/currentness path; keep genuine CAP-04 event replay separate and do not synthesize events.
  `task.r19_extension.question_slices[1]` (`R18-D03-Q03`); `task.r19_extension.question_ids[0]` (`R18-D03-Q03`)
- **execute** — task.r19_extension.question_slices[9] crosswalks by actual value to question_ids[14]. Admitted source or qualified own-assessment changes are observed for enrolled premises; derivative-only variance is excluded from parent currentness.
  `task.r19_extension.question_slices[9]` (`R18-D22-Q03`); `task.r19_extension.question_ids[14]` (`R18-D22-Q03`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
