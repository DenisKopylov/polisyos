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
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Root preserves accepted E02 stage/rebind.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-02](../../parents/CAP-02.md) | `acceptance:composition`: Actual selected output is consumed by the local composition reader; acceptance is composition-only, not a preparation prerequisite.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: selected parent composed claim; not a new preparation dependency |
| Supplier [LIF-09](../../parents/LIF-09.md) | `acceptance:composition`: Actual selected output is consumed by the local composition reader; acceptance is composition-only, not a preparation prerequisite.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: selected parent composed claim; not a new preparation dependency |
| Composition output (не start gate) [LIF-01.cache_current_use](../../cards/LIF-01/cache_current_use.md) | Only when this selected use takes the cache-eligible reuse path; an uncached or fresh-evaluation use does not require cache identity. |
| Composition output (не start gate) [LIF-01.trial_realization](../../cards/LIF-01/trial_realization.md) | Only for a selected stochastic/replay/fresh-replicate claim; ordinary scoped relation/use does not require trial realization. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `LIF-01`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Relation/use delivery and scoped positive.
  `task.deliverable`; `task.positive[0]`
- **execute** — Relation negative/removal, API, lawful suspension and rebind.
  `task.adversarial[0]`; `task.removal[0]`; `task.removal[1]`; `task.surface`; `task.rollback`; `task.migration`
- **execute** — Legal applicability predicates must be recomputed or independently reconciled.
  `task.acceptance_steps[5]`
- **execute** — CAP receipt and R17 relation/use positive/adversarial/removal.
  `task.acceptance_evidence_requirements[0]`; `task.r17_extension.requirement`; `task.r17_extension.positive`; `task.r17_extension.adversarial`; `task.r17_extension.removal`
- **binding** — R18-D04-Q01 identity/source/scope/time/purpose; episodes/successors.
  `task.r19_extension.question_slices[0]`; `task.r19_extension.question_ids[0]`
- **execute** — R18-D04-Q02 applicability exact claim/action/population/audience.
  `task.r19_extension.question_slices[1]`; `task.r19_extension.question_ids[1]`
- **execute** — R18-D04-Q03 content-bound interpretation and verifier removal.
  `task.r19_extension.question_slices[2]`; `task.r19_extension.question_ids[2]`
- **execute** — R18-D04-Q04 qualified procedural order/facts.
  `task.r19_extension.question_slices[3]`; `task.r19_extension.question_ids[3]`
- **execute** — R18-D04-Q06 exact required procedural evidence.
  `task.r19_extension.question_slices[4]`; `task.r19_extension.question_ids[4]`
- **execute** — R18-D09-Q01 exact legal basis/dependency.
  `task.r19_extension.question_slices[5]`; `task.r19_extension.question_ids[5]`
- **binding** — R18-D15-Q01 LIF01 relation; LIF05 sink rights.
  `task.r19_extension.question_slices[6]`; `task.r19_extension.question_ids[6]`
- **execute** — R18-D18-Q04 foreign content to local use.
  `task.r19_extension.question_slices[8]`; `task.r19_extension.question_ids[8]`
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

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
