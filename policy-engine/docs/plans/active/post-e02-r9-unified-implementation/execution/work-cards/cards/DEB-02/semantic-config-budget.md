# DEB-02.semantic-config-budget — Считать семантическую конфигурацию

Группа: [G10 — Независимые проверки и качество свидетельств](../../groups/G10.md). Родитель: [DEB-02](../../parents/DEB-02.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Relocating unchanged packaging settings between declared files does not reduce the semantic configuration measure; a real effective setting changes it.

**Предпочтительное решение.** Extend repository_structure_phase0.py::gate_pyproject_size to enumerate complete owner-declared packaging configuration and normalized effective settings, preserving file/key provenance.

**Граница владельца.** Existing repository-structure gate owner; no budget threshold changes without owner decision. Native exact-path lease family; exact paths unresolved until E02.

**Входы.** Owner-approved budget meaning/threshold; accepted tree and full packaging-config set including relocated Hatch settings.

**Выход и consumer.** Complete semantic-configuration inventory/measure with source file and key provenance and gate result.

**Что можно готовить независимо.** Rebind source, owner, consumer and exact lease after P0-ACCEPT where applicable; any earlier census/preparation is only what the original parent stage permits. This card neither adds nor removes a start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh repository_structure_phase0.py::gate_pyproject_size consumer.; composition is limited to this property and the exact original scope.

**Positive.** The accepted inputs produce the bounded result and the fresh consumer accepts the scoped property: Relocating unchanged packaging settings between declared files does not reduce the semantic configuration measure; a real effective setting changes it.

**Distinguishing negative.** Moving an unchanged key cannot lower the measure; formatting/line count is not semantic size.

**Matched removal.** Remove the decisive binding for this property while retaining declarations/markers; the named consumer must fail or return its typed unknown/refusal: Relocating unchanged packaging settings between declared files does not reduce the semantic configuration measure; a real effective setting changes it.

**Граница контекста.** Keep the packaging-budget predicate separate from OpenAPI export identity and reference resolution.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-02 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-02`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — These fragments concern effective packaging settings, relocation invariance, threshold and packaging parser scope.
  `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.composition_contracts[0]`; `solution.acceptance_discriminators[0]`; `solution.deviation_triggers[0]`; `solution.inputs_to_resolve[0]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
