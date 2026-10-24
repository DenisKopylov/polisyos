# LIF-01.relation_use — Связать отношение с use

Группа: [G06 — Допустимость, полномочия и квалифицированные решения](../../groups/G06.md). Родитель: [LIF-01](../../parents/LIF-01.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Exact content/verifier-bound relation supports only its claim, purpose, audience and time.

**Предпочтительное решение.** Extend existing domain verifier + Claim Ledger; resolve CAP02 receipt/lawful query and persist assessment/use.

**Граница владельца.** One native `write:semantic-use/{owner}`; verifier is evidence only; E02 path unresolved.

**Входы.** CAP02 receipt/profile or lawful query; domain verifier/rule; Claim Ledger use/audience; API/audit.

**Выход и consumer.** Persisted relation/assessment/use read by fresh claim consumer.

**Что можно готовить независимо.** Domain, rights, currentness and trial owners stay distinct.

**Где результат соединяется с другими.** Fresh claim/evaluation read; changed purpose rechecks.

**Positive.** Scoped supported use passes.

**Distinguishing negative.** Wrong scope/polarity, no-hit as absence, invented identity or repeated cohort as independent.

**Matched removal.** Remove content/use verification but retain refs/labels; fresh reader refuses.

**Граница контекста.** One observable property; other owners remain suppliers/consumers.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Root preserves accepted E02 stage/rebind.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-02](../../parents/CAP-02.md) | `acceptance:composition`: Actual selected output is consumed by the local composition reader; acceptance is composition-only, not a preparation prerequisite.<br>Source: `task.acceptance_dependencies[0]`.<br>Условия: selected parent composed claim; not a new preparation dependency |
| Supplier [LIF-09](../../parents/LIF-09.md) | `acceptance:composition`: Actual selected output is consumed by the local composition reader; acceptance is composition-only, not a preparation prerequisite.<br>Source: `task.acceptance_dependencies[1]`.<br>Условия: selected parent composed claim; not a new preparation dependency |
| Composition output (не start gate) [LIF-01.cache_current_use](../../cards/LIF-01/cache_current_use.md) | Only when this selected use takes the cache-eligible reuse path; an uncached or fresh-evaluation use does not require cache identity. |
| Composition output (не start gate) [LIF-01.trial_realization](../../cards/LIF-01/trial_realization.md) | Only for a selected stochastic/replay/fresh-replicate claim; ordinary scoped relation/use does not require trial realization. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `LIF-01`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Relation/use delivery and scoped positive.
  `task.deliverable`; `task.positive[0]`
- **execute** — Relation negative/removal, API, lawful suspension and rebind.
  `task.adversarial[0]`; `task.removal[0]`; `task.removal[1]`; `task.surface`; `task.rollback`; `task.migration`
- **execute** — Legal applicability predicates must be recomputed or independently reconciled.
  `task.acceptance_steps[5]`
- **execute** — CAP receipt and R17 relation/use positive/adversarial/removal.
  `task.acceptance_evidence_requirements[0]`; `task.r17_extension.requirement`; `task.r17_extension.positive`; `task.r17_extension.adversarial`; `task.r17_extension.removal`
- **execute** — Resolve representation, emit verifier, bind use, no auto-upgrade.
  `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`
- **binding** — Profile/owner/resource/migration and CAP/domain/Claim contracts.
  `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.composition_contracts[2]`
- **execute** — General positive/adversarial/removal.
  `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`
- **execute** — Actual applicability recomputation/reconciliation.
  `solution.acceptance_discriminators[4]`
- **binding** — Deviation, authority extension and actual CAP/domain/claim inputs.
  `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`; `solution.deviation_triggers[2]`; `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`; `solution.inputs_to_resolve[2]`
- **binding** — task.r19_extension.question_slices[0] crosswalks by actual value to question_ids[6]. Defines relation identity, role, source, scope, time, purpose and distinct episodes; relation_use owns this binding.
  `task.r19_extension.question_slices[0]` (`R18-D15-Q01`); `task.r19_extension.question_ids[6]` (`R18-D15-Q01`)
- **execute** — task.r19_extension.question_slices[1] crosswalks by actual value to question_ids[0]. Limits applicability to one claim, action, population, purpose and audience; this is the relation-to-use contract.
  `task.r19_extension.question_slices[1]` (`R18-D04-Q01`); `task.r19_extension.question_ids[0]` (`R18-D04-Q01`)
- **execute** — task.r19_extension.question_slices[2] crosswalks by actual value to question_ids[1]. Requires resolved, content-bound interpretation for the exact local use; the use consumer belongs here.
  `task.r19_extension.question_slices[2]` (`R18-D04-Q02`); `task.r19_extension.question_ids[1]` (`R18-D04-Q02`)
- **execute** — task.r19_extension.question_slices[3] crosswalks by actual value to question_ids[2]. Binds the qualified proceeding/order and resolved facts to this claim-use, not to a global case status.
  `task.r19_extension.question_slices[3]` (`R18-D04-Q03`); `task.r19_extension.question_ids[2]` (`R18-D04-Q03`)
- **execute** — task.r19_extension.question_slices[4] crosswalks by actual value to question_ids[3]. Checks each procedural item against the exact claim requirement and resolved evidence, rather than trusting a checklist.
  `task.r19_extension.question_slices[4]` (`R18-D04-Q04`); `task.r19_extension.question_ids[3]` (`R18-D04-Q04`)
- **execute** — task.r19_extension.question_slices[5] crosswalks by actual value to question_ids[4]. Freezes the legal basis to the claim dependency; currentness reaction to later change remains LIF-02 work.
  `task.r19_extension.question_slices[5]` (`R18-D04-Q06`); `task.r19_extension.question_ids[4]` (`R18-D04-Q06`)
- **binding** — task.r19_extension.question_slices[6] crosswalks by actual value to question_ids[5]. Supplies the relation and scoped action-right context; LIF-05 remains the action-specific rights decision owner.
  `task.r19_extension.question_slices[6]` (`R18-D09-Q01`); `task.r19_extension.question_ids[5]` (`R18-D09-Q01`)
- **execute** — task.r19_extension.question_slices[8] crosswalks by actual value to question_ids[8]. Binds resolved foreign content to one local use/audience; directional compatibility is a separate LIF-08 consumer.
  `task.r19_extension.question_slices[8]` (`R18-D18-Q04`); `task.r19_extension.question_ids[8]` (`R18-D18-Q04`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
