# LIF-09.freeze_and_readiness — Зафиксировать source и denominator

Группа: [G10 — Независимые проверки и качество свидетельств](../../groups/G10.md). Родитель: [LIF-09](../../parents/LIF-09.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Freeze accepted source/tree, owner closure, selected profile/use, reviewer and active/conditional denominator.

**Предпочтительное решение.** Use existing program journal and E02 acceptance; no new receipt service/verifier.

**Граница владельца.** Parent exact-path lease, resolved by root.

**Входы.** Accepted source/tree, dispositions, owner closure, selected rows and reviewer candidate.

**Выход и consumer.** Frozen identity/denominator in journal.

**Что можно готовить независимо.** UID coverage is structural only.

**Где результат соединяется с другими.** After E02 rebind; changes reprice.

**Positive.** Each row names exact owner/property/input/consumer/surface/activation.

**Distinguishing negative.** Incomplete manifest or changed sibling transfers green.

**Matched removal.** Remove required consumer but retain marker; readiness fails.

**Граница контекста.** One observable property; other owners remain suppliers/consumers.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Root preserves canonical accepted-source stage.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-01](../../parents/LIF-01.md) | `direct:owner_readiness`: Freeze use scope, exercise relation, bind result.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-06](../../parents/LIF-06.md) | `direct:owner_readiness`: Freeze and exercise measured profile.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-08](../../parents/LIF-08.md) | `direct:owner_readiness`: Freeze source/reader matrix and exercise second source.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [FINAL-REVIEW.independent-review](../../cards/FINAL-REVIEW/independent-review.md) | `direct:final_reviewed_replay_identity`: Freeze reviewer/candidate; consume review on final identity and preserve `final_reviewed_replay_identity`.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `LIF-09`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Pin source/oracle/owner denominator.
  `task.acceptance_steps[0]`; `task.acceptance_steps[1]`
- **execute** — Freeze chain/denominator/P37 classification.
  `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`
- **binding** — Versioned profiles and extension boundary.
  `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`
- **execute** — E02 and exact identity.
  `solution.composition_contracts[0]`; `solution.composition_contracts[1]`
- **execute** — Before E02 only candidate diagnostics.
  `solution.deviation_triggers[0]`
- **binding** — Accepted source/owner/CAP/OPS inputs; no supplier appointment.
  `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
