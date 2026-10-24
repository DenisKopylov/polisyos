# CAP-03.fresh-sink-rights — Recheck the exact operation at every selected sink

Группа: [G07 — Долгая custody: актуальность, права и переиздание](../../groups/G07.md). Родитель: [CAP-03](../../parents/CAP-03.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Read permission does not grant analyze, derive, cache, resume, export, restore, or publish permission.

**Предпочтительное решение.** Use the same LIF-01 source-use passport and LIF-05 rights-generation decision at the selected reader, resume, cache, export and materialization effect; recheck at resume/commit rather than treating first-fetch permission as permanent. Preserve the exact root and refuse unauthorized sinks. Anchors: runtime/quality/acquisition_executor.py:revalidate_admission_passport; data_forge/domains/catalog/knowledge/acquisition_authority.py:resolve_live_source_execution.

**Граница владельца.** LIF-05 and actual storage/security owners; CAP-03 wires selected consumers and owns no rights ledger. Parent native lease family: `write:acquisition-action`, `write:acquisition-passport`. Exact post-E02 paths/overlap are unresolved; do not infer sibling disjointness or create a child lease. Root binds the actual path/lease before writes; cards sharing a native family serialize there.

**Входы.** Exact root/output, action, purpose, recipient, current rights generation, and selected sink inventory.

**Выход и consumer.** Fresh allow/refusal/indeterminate result at the effect point; permitted derivative remains usable when raw bytes are barred.

**Что можно готовить независимо.** Resolve source/custodian rights and backend copy/control evidence for the selected profile.

**Где результат соединяется с другими.** Join before fetch/resume/cache/derive/export/restore; share LIF-05's AP07 reservation/outcome.

**Positive.** Allowed derivative is consumed while forbidden raw canaries remain absent from every selected sink.

**Distinguishing negative.** Revocation, audience/purpose shift, new recipient, or overlapping release blocks the affected effect.

**Matched removal.** Drop sink/current-rights check but keep labels; controlled canary or revoke-before-resume probe exposes the bypass.

**Граница контекста.** Root admission is distinct from current rights at sinks, method-specific replay identity, and binding verification to bytes actually read. The preferred-solutions card carries method/stream acceptance beyond the core library property; keep those native owners and compose them rather than giving CAP-03 a new universal mechanism. This is one bounded property view; parent source pins, stage/dispatch, conditional acceptance and mandatory companions remain inherited.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted source/path rebind where used; original stage gate stays inherited.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-02](../../parents/CAP-02.md) | `direct:owner_readiness`: Consume exact root/read; cost-basis consumes planner artifact.<br>Source: `task.depends_on[1]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-01](../../parents/LIF-01.md) | `direct:owner_readiness`: Consume source/use relation at admission and selected use.<br>Source: `task.depends_on[2]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-05](../../parents/LIF-05.md) | `direct:owner_readiness`: Consume shared rights/reservation at relevant effect; no local counter.<br>Source: `task.depends_on[3]`.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [CAP-03.root-admission](../../cards/CAP-03/root-admission.md) | Consume only for the exact composition described here: Join before fetch/resume/cache/derive/export/restore; share LIF-05's AP07 reservation/outcome. This link is not an unconditional all-of or preparation gate. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `CAP-03`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Recheck distinct use/action/recipient/generation and actual sinks through shared LIF-05; D05/D09/D14 cover permission conflicts, conduct, cumulative disclosure and consent/revocation.
  `task.r17_extension.requirement`; `task.r17_extension.positive`; `task.r17_extension.adversarial`; `task.r17_extension.removal`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`; `solution.free_grow.extension_boundary`; `solution.composition_contracts[1]`; `solution.composition_contracts[2]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[3]`; `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[1]`; `solution.inputs_to_resolve[2]`
- **join** — Foreign purpose/tenant/stale-generation probe consumes root admission and current shared rights.
  `task.surface_delivery.negative`
- **binding** — R17 D6 constrains exact source-use, recipient and output-release decisions at actual sinks; reuse existing authz/LIF-05 rather than creating a new IAM or provider owner.
  `task.r17_extension.delivery_slices[0]`
- **execute** — re-resolve current LIF-05 outcome at derive/cache/export; a permitted derivative does not release restricted raw data.
  `task.r19_extension.question_slices[1]` (`R18-D05-Q05`); `task.r19_extension.question_ids[1]` (`R18-D05-Q05`)
- **execute** — read, analyze, derive, and public export are distinct actions requiring current action/purpose/recipient grants at the sink.
  `task.r19_extension.question_slices[2]` (`R18-D09-Q01`); `task.r19_extension.question_ids[2]` (`R18-D09-Q01`)
- **execute** — bind the separate current read/analyze/derive/export/publish grants and recipient; a public URL/hash is not an IPD grant.
  `task.r19_extension.question_slices[3]` (`R18-D09-Q05`); `task.r19_extension.question_ids[3]` (`R18-D09-Q05`)
- **execute** — cached/resumed use must resolve current LIF-05 policy version and preserve the original reservation/outcome.
  `task.r19_extension.question_slices[4]` (`R18-D14-Q03`); `task.r19_extension.question_ids[4]` (`R18-D14-Q03`)
- **execute** — grant to read does not authorize analysis, training, reuse, or publication; recheck rights at the later use.
  `task.r19_extension.question_slices[5]` (`R18-D14-Q04`); `task.r19_extension.question_ids[5]` (`R18-D14-Q04`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
