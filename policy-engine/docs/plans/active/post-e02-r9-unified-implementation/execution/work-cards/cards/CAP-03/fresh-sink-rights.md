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
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted source/path rebind where used; original stage gate stays inherited.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-02](../../parents/CAP-02.md) | `direct:owner_readiness`: Consume exact root/read; cost-basis consumes planner artifact.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-01](../../parents/LIF-01.md) | `direct:owner_readiness`: Consume source/use relation at admission and selected use.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-05](../../parents/LIF-05.md) | `direct:owner_readiness`: Consume shared rights/reservation at relevant effect; no local counter.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [CAP-03.root-admission](../../cards/CAP-03/root-admission.md) | Consume only for the exact composition described here: Join before fetch/resume/cache/derive/export/restore; share LIF-05's AP07 reservation/outcome. This link is not an unconditional all-of or preparation gate. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `CAP-03`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Recheck distinct use/action/recipient/generation and actual sinks through shared LIF-05; D05/D09/D14 cover permission conflicts, conduct, cumulative disclosure and consent/revocation.
  `task.r17_extension.requirement`; `task.r17_extension.positive`; `task.r17_extension.adversarial`; `task.r17_extension.removal`; `task.r19_extension.question_slices[1]`; `task.r19_extension.question_slices[2]`; `task.r19_extension.question_slices[3]`; `task.r19_extension.question_slices[4]`; `task.r19_extension.question_slices[5]`; `task.r19_extension.question_ids[1]`; `task.r19_extension.question_ids[2]`; `task.r19_extension.question_ids[4]`; `task.r19_extension.question_ids[5]`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`; `solution.free_grow.extension_boundary`; `solution.composition_contracts[1]`; `solution.composition_contracts[2]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[3]`; `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[1]`; `solution.inputs_to_resolve[2]`
- **join** — Foreign purpose/tenant/stale-generation probe consumes root admission and current shared rights.
  `task.surface_delivery.negative`
- **binding** — R17 D6 constrains exact source-use, recipient and output-release decisions at actual sinks; reuse existing authz/LIF-05 rather than creating a new IAM or provider owner.
  `task.r17_extension.delivery_slices[0]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
