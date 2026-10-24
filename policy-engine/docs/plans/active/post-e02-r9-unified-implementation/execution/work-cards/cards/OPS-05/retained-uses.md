# OPS-05.retained-uses — Разрешать использование по сохранённой репрезентации

Группа: [G09 — Развёртывание, исполнители, хранилища и ресурсы](../../groups/G09.md). Родитель: [OPS-05](../../parents/OPS-05.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** For a selected use, only the exact required retained payload or qualified retained result with current rights and sufficient basis is available; lawfully erased raw dependencies stay unavailable.

**Предпочтительное решение.** Reuse LIF-05 representation/retention/current-use decisions and LIF-07 derivative influence semantics. Recover or verify the use-required native representation; do not demand prohibited raw input, invent re-fetch rights, rehabilitate an old head or treat a receipt/hash/number as sufficient basis.

**Граница владельца.** This card consumes LIF-05/LIF-07 and the OPS-05 quarantine path; it does not write their rights, deletion or derivative ledgers. Any restore-side write remains under `resource:control/{cell}/backup-restore`; exact paths and owner overlaps are resolved after E02 rebind.

**Входы.** OPS-05 restored/quarantined selected representation and exact source identities; LIF-05 retained/deleted representation and current-use rights; LIF-07 actual dependency/derivative relation and sufficient verification basis; Fresh selected reader with the requested purpose/audience

**Выход и consumer.** Per-use retained representation/use outcome with explicit replay limitation, consumed by the existing fresh reader; erased raw input remains an explicit unavailable dependency.

**Что можно готовить независимо.** Representation classification and interface can be prepared after scope agreement. Actual restored-use admission waits for the selected retained bytes/result and rights/dependency evidence; this need not wait on unrelated corpus rows.

**Где результат соединяется с другими.** Consumes `restore-cut` output plus LIF-05/07. A query-only result or lawful derivative may serve its qualified scope, while any raw-dependent recomputation or new purpose remains unavailable; the two results are not generalized.

**Positive.** Mixed lawful archive admits the retained payload and query-only result only for their qualified uses and records the erased dependency; a valid permitted derivative can still support its scoped historical use.

**Distinguishing negative.** Unexpected loss of a required retained object, use of erased raw input, missing dependency/current-use proof, or an unpermitted purpose is refused/limited; a genuinely independent scope remains eligible.

**Matched removal.** Remove representation/retention/current-use qualification but keep erase/result markers; both false blanket refusal and unsupported admission probes fail.

**Граница контекста.** A use-based consumer contract, not archive enumeration or rights writer. Lazy per-object verification is bounded to the selected protected use and does not assert whole-archive integrity. P10/P32/P35 guard the discriminator and denominator.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Each child consumes the accepted E02 source/rebound owner and actual supported boundary; this is the parent dispatch contract, not a new peer dependency.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-05](../../parents/LIF-05.md) | `direct:owner_readiness; conditional_acceptance_requirements:composition`: Consume current rights, retention/deletion classification and sink-use decisions; OPS-05 does not write those decisions.<br>Source: `task.depends_on[3]`; `task.conditional_acceptance_requirements[0]`.<br>Условия: original direct relation; source stage rules govern; Restore enables current/protected claim or publication reads |
| Supplier [LIF-07](../../parents/LIF-07.md) | `interface_reference:reference_only_no_new_gate`: For a selected retained representation/use, consume the actual dependency/derivative relation and sufficient verification basis; no requirement to finish unrelated LIF-07 work.<br>Source: `solution.composition_contracts[2]`.<br>Условия: Only the selected native output/interface is consumed; no new preparation prerequisite or authority grant.<br>No new preparation or task-completion gate. The selected existing contract still requires its real output at the actual use described in need; absence blocks that use/claim only. An interface document is not a substituted producer receipt. |
| Composition output (не start gate) [OPS-05.restore-cut](../../cards/OPS-05/restore-cut.md) | Consume only for the exact composition described here: Consumes `restore-cut` output plus LIF-05/07. A query-only result or lawful derivative may serve its qualified scope, while any raw-dependent recomputation or new purpose remains unavailable; the two results are not generalized. This link is not an unconditional all-of or preparation gate. |
| Composition output (не start gate) [OPS-05.byte-release](../../cards/OPS-05/byte-release.md) | Consume only for the exact composition described here: Consumes `restore-cut` output plus LIF-05/07. A query-only result or lawful derivative may serve its qualified scope, while any raw-dependent recomputation or new purpose remains unavailable; the two results are not generalized. This link is not an unconditional all-of or preparation gate. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `OPS-05`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **binding** — Binding scope, authority, migration, time, input, or lifecycle constraint for retained-uses; selectors task.r17_extension.delivery_slices[2], solution.composition_contracts[2], solution.composition_contracts[3] remain load-bearing.
  `task.r17_extension.delivery_slices[2]`; `solution.composition_contracts[2]`; `solution.composition_contracts[3]`
- **execute** — Direct result/preferred path for retained-uses; selectors solution.implementation_steps[2] name the work and native owner seam.
  `solution.implementation_steps[2]`
- **join** — Distinguishing behavior, consumer surface, or acceptance evidence for retained-uses; selectors task.acceptance_steps[4], solution.acceptance_discriminators[3], solution.acceptance_discriminators[4] are checked at its actual reader/sink.
  `task.acceptance_steps[4]`; `solution.acceptance_discriminators[3]`; `solution.acceptance_discriminators[4]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
