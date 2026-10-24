# GYD-16.chain-matrix — Проверить всю producer-to-surface цепочку

Группа: [G10 — Независимые проверки и качество свидетельств](../../groups/G10.md). Родитель: [GYD-16](../../parents/GYD-16.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Every moved row resolves to actual producer, persisted artifact/event, bridge, consumer, verifier, surface and behavioral semantic test.

**Предпочтительное решение.** Wire or extend the existing native capability owners plus their current coverage checker; preserve its typed contract and status/time/provenance semantics.

**Граница владельца.** Within GYD-16's native canonical lease family write:exact-path/{canonical_repo_path}. Exact paths and overlap remain unresolved until accepted E02 lease resolution; do not presume disjointness. Existing native capability owners plus their current coverage checker.

**Входы.** moved-denominator receipt; owner-resolved artifacts/events and actual consumer outputs

**Выход и consumer.** Recomputed row-chain matrix and generated/public readback

**Что можно готовить независимо.** Preparation may proceed before freeze; final execution follows the parent’s canonical stage and conditional acceptance. No new gate is introduced; resolve accepted E02 source and exact lease before writes.

**Где результат соединяется с другими.** Fresh consumer: fresh coverage receipt consumer and affected public/generated family. Matrix is a projection of owner evidence; red rows remain visible.

**Positive.** Every row has an exercised chain and an owner-bound semantic test.

**Distinguishing negative.** Missing consumer, presence-only artifact or unresolved row remains red/limited/not_established.

**Matched removal.** Remove real consumer/property but keep matrix markers; chain and behavioral result fail.

**Граница контекста.** Matrix is a projection of owner evidence; red rows remain visible.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [FINAL-REVIEW.independent-review](../../cards/FINAL-REVIEW/independent-review.md) | `acceptance:composition`: FINAL-REVIEW consumes the fully composed outputs at the canonical composition acceptance stage. It does not block independent preparation or add a leaf/preparation gate.<br>Source: `task.acceptance_dependencies[0]`.<br>Условия: selected parent composed claim; not a new preparation dependency |
| Composition output (не start gate) [GYD-16.moved-denominator](../../cards/GYD-16/moved-denominator.md) | Consume only for the exact composition described here: Fresh consumer: fresh coverage receipt consumer and affected public/generated family. Matrix is a projection of owner evidence; red rows remain visible. This link is not an unconditional all-of or preparation gate. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `GYD-16`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Task deliverable, positive, adversary, removal, surface, rollback and migration all describe the final recomputed chain matrix; keep red rows and historical source statuses.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.rollback`; `task.migration`
- **join** — Native schema/rule, consumers/generated family, migration, journal and deciding review are mandatory companions to this matrix receipt.
  `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`
- **execute** — This is the final denominator plus chain-and-semantic-test recomputation.
  `task.final_execution_property`
- **execute** — Preferred checker joins each canonical source row with its actual typed producer-to-surface evidence.
  `solution.preferred_solution`
- **execute** — Bind each row to owner artifact and real consumer, run omitted-row/removal falsifiers, and read the fresh matrix/public family.
  `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`
- **binding** — New evidence kinds or edges require typed owner resolution and behavioral verification.
  `solution.free_grow.extension_boundary`
- **binding** — Historical matrix/status is preserved; rollback is scoped to checker extension only.
  `solution.migration_and_rollback`
- **binding** — These composition clauses name source-derived denominator, full producer-through-surface plus semantic evidence, and conditional need for independent oracle.
  `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.composition_contracts[2]`
- **execute** — Positive complete chain, omitted source row and remove-property/keep-marker are the three matrix falsifiers.
  `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`
- **binding** — Unbound rows remain not_established and new consumer/surface gaps expand only the authorized closure.
  `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
