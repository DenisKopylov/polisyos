# LIF-09.final_join_receipt — Сверить review и final replay identity

Группа: [G10 — Независимые проверки и качество свидетельств](../../groups/G10.md). Родитель: [LIF-09](../../parents/LIF-09.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Only exact identity-bound evidence closes activated requirements; refusal/UNRUN does not meet required positive.

**Предпочтительное решение.** Use existing journal, exact candidate, independent review and one measured wave.

**Граница владельца.** Join only; no lifecycle writer/service.

**Входы.** Frozen denominator, vertical outputs, LIF01-08 receipts, CAP/OPS cuts, reviewer, resource denominator.

**Выход и consumer.** Final disposition/limitations at exact replay identity.

**Что можно готовить независимо.** Historical output remains rights-bounded.

**Где результат соединяется с другими.** After canonical FINAL-FREEZE and FINAL-REVIEW, close only the exact reviewed replay identity; post-freeze changes reprice through bounded delta review.

**Positive.** Rows/reviewer/output pins match identity.

**Distinguishing negative.** Refusal/UNRUN mistaken closure or changed input transfers old green.

**Matched removal.** Remove supplier/bridge/replace reader with fields; final fails.

**Граница контекста.** One observable property; other owners remain suppliers/consumers.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Root preserves canonical accepted-source stage.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-01](../../parents/LIF-01.md) | `direct:owner_readiness`: Freeze use scope, exercise relation, bind result.<br>Source: `task.depends_on[1]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-02](../../parents/LIF-02.md) | `direct:owner_readiness`: Exercise currentness/duty reader, bind receipt.<br>Source: `task.depends_on[2]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-03.conditional_frontier_commit](../../cards/LIF-03/conditional_frontier_commit.md) | `direct:owner_readiness`: Exercise cursor receipt and bind.<br>Source: `task.depends_on[3]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-04](../../parents/LIF-04.md) | `direct:owner_readiness`: Exercise selected effect/duty.<br>Source: `task.depends_on[4]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-05](../../parents/LIF-05.md) | `direct:owner_readiness`: Exercise rights/sink/placement.<br>Source: `task.depends_on[5]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-06](../../parents/LIF-06.md) | `direct:owner_readiness`: Freeze and exercise measured profile.<br>Source: `task.depends_on[6]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-07](../../parents/LIF-07.md) | `direct:owner_readiness`: Exercise selected lineage/current-use.<br>Source: `task.depends_on[7]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-08](../../parents/LIF-08.md) | `direct:owner_readiness`: Freeze source/reader matrix and exercise second source.<br>Source: `task.depends_on[8]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-05](../../parents/CAP-05.md) | `direct:owner_readiness`: Actual CAP05 only where selected vertical activates.<br>Source: `task.depends_on[9]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-06](../../parents/CAP-06.md) | `direct:owner_readiness`: Actual CAP06 only where selected; LIF05 remains rights owner.<br>Source: `task.depends_on[10]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [FINAL-REVIEW.independent-review](../../cards/FINAL-REVIEW/independent-review.md) | `direct:final_reviewed_replay_identity`: Freeze reviewer/candidate; consume review on final identity and preserve `final_reviewed_replay_identity`.<br>Source: `task.depends_on[11]`.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [LIF-09.vertical_witnesses](../../cards/LIF-09/vertical_witnesses.md) | Only selected active rows with producer/persisted artifact/event/bridge/fresh-reader/removal outcomes; refusal or UNRUN cannot satisfy a required positive. |
| Composition output (не start gate) [LIF-09.freeze_and_readiness](../../cards/LIF-09/freeze_and_readiness.md) | The exact source/tree, reviewer, selected profile/use and denominator must match; later changes require a bounded delta/replay, with FINAL-REVIEW at `final_reviewed_replay_identity`. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `LIF-09`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Disposition per active row.
  `task.positive[1]`
- **execute** — Changed sibling/source invalidates green.
  `task.removal[1]`
- **execute** — Rights-aware history and E02 rebind.
  `task.rollback`; `task.migration`
- **execute** — Exact review, companions, journal/precedence.
  `task.acceptance_steps[4]`; `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`; `task.rollback_precedence`
- **execute** — Independent reviewer, final wave, readback.
  `solution.implementation_steps[4]`
- **execute** — Post-freeze change invalidates; delta review.
  `solution.migration_and_rollback`
- **execute** — Disposition, authority, refusal-not-closure, completion.
  `solution.composition_contracts[2]`; `solution.composition_contracts[3]`; `solution.composition_contracts[4]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`; `solution.acceptance_discriminators[3]`
- **execute** — External unavailability and precise verification labels.
  `solution.deviation_triggers[1]`; `solution.deviation_triggers[2]`
- **binding** — Reviewer identity/pins/denominator.
  `solution.inputs_to_resolve[3]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
