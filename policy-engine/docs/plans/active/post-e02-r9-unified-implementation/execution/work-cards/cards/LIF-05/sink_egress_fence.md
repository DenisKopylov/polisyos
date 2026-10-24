# LIF-05.sink_egress_fence — Заблокировать egress на реальном sink

Группа: [G08 — Документы, интерфейсы и понятные человеку результаты](../../groups/G08.md). Родитель: [LIF-05](../../parents/LIF-05.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Actual CAP03/06 sink reserves/commits under current decision; uncertain disclosure is held.

**Предпочтительное решение.** Wire actual sinks to decision; no second ledger/recall promise.

**Граница владельца.** CAP03/06 own sinks; LIF05 decision; CAS storage.

**Входы.** Decision, output/recipient/unit, overlap, attempt/receipt and currentness.

**Выход и consumer.** Per-sink commit/indeterminate result at API/export.

**Что можно готовить независимо.** Consumer enforcement only.

**Где результат соединяется с другими.** At each actual CAP-03/06 sink commit/hold, consume the current LIF-05 decision/generation for the selected recipient and output.

**Positive.** Permitted output passes; reuse differs from new draw/audience.

**Distinguishing negative.** Overlap/revoke race/timeout refund.

**Matched removal.** Remove commit/hold, keep grant markers; fresh sink fails.

**Граница контекста.** One observable property; other owners remain suppliers/consumers.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Root stage.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-02](../../parents/LIF-02.md) | `direct:owner_readiness`: Fresh currentness at sinks/restore; inventory independent.<br>Source: `task.depends_on[2]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-03](../../parents/CAP-03.md) | `acceptance:composition`: Actual selected output is consumed by the local composition reader; acceptance is composition-only, not a preparation prerequisite.<br>Source: `task.acceptance_dependencies[0]`.<br>Условия: selected parent composed claim; not a new preparation dependency |
| Supplier [CAP-06](../../parents/CAP-06.md) | `acceptance:composition`: Actual selected output is consumed by the local composition reader; acceptance is composition-only, not a preparation prerequisite.<br>Source: `task.acceptance_dependencies[1]`.<br>Условия: selected parent composed claim; not a new preparation dependency |
| Composition output (не start gate) [LIF-05.rights_decision](../../cards/LIF-05/rights_decision.md) | For the exact output/recipient/unit whose sink commit or hold is being decided; sink enforcement remains with CAP-03/06. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `LIF-05`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Release overlap/reuse/new audience.
  `task.positive[2]`
- **execute** — Overlap, sink and matching removal clauses.
  `task.adversarial[1]`; `task.removal[0]`; `task.removal[1]`; `task.removal[2]`; `task.removal[3]`
- **execute** — R15 disclosure/overlap/removal.
  `task.r15_extension.requirement`; `task.r15_extension.positive`; `task.r15_extension.adversarial`; `task.r15_extension.removal`
- **execute** — Pre-reserve/stage/recheck.
  `solution.implementation_steps[1]`
- **binding** — CAP03/06 outputs and recipients.
  `solution.inputs_to_resolve[2]`
- **execute** — task.r19_extension.question_slices[2] crosswalks by actual value to question_ids[2]. At each real sink, composes current policy with unit/overlap/recipient exposure reservation and commit.
  `task.r19_extension.question_slices[2]` (`R18-D14-Q03`); `task.r19_extension.question_ids[2]` (`R18-D14-Q03`)
- **execute** — task.r19_extension.question_slices[3] crosswalks by actual value to question_ids[3]. Fences actual disclosure/restore under current rights and release decision, carrying uncertainty after possible remote release.
  `task.r19_extension.question_slices[3]` (`R18-D14-Q04`); `task.r19_extension.question_ids[3]` (`R18-D14-Q04`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
