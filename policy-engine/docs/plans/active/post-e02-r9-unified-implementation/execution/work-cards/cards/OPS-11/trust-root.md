# OPS-11.trust-root — Принимать техническое trust-root succession

Группа: [G07 — Долгая custody: актуальность, права и переиздание](../../groups/G07.md). Родитель: [OPS-11](../../parents/OPS-11.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** A current PolicyOS technical trust generation and successor are independently authorized, strictly monotonic and historically verifiable; a compromised root cannot appoint its own replacement.

**Предпочтительное решение.** Reuse existing PolicyOS issuer/identity/release owner and ratified custody boundary. Initial trust is provisioned out-of-band; routine succession requires verified next generation and successor acceptance; compromised-root recovery uses institution’s separate independent channel.

**Граница владельца.** Technical signature/generation evidence stays in existing trust/release family under OPS-11 `write:exact-path/{canonical_repo_path}`; institution retains its authority/appointment act. Resolve actual trust-file overlap with OPS-01 commissioning after E02; do not treat external staff changes as PolicyOS root events.

**Входы.** OPS-01 initial commissioning receipt and independent trust provision; Independent authorized recovery/appointment evidence and prior/successor generations; Current revocation/anti-rollback history and time validity; Fresh verifier and selected source-use consumer

**Выход и consumer.** Content-bound succession/generation receipt and affected-scope freeze/limited state, consumed by OPS-01 commissioning and fresh CAP-03 source-use reader.

**Что можно готовить независимо.** Protocol and verifier can be prepared against the agreed institutional evidence interface. Root-generation change, promotion or protected use waits for independent appointment/currentness; a prototype root labels only prototype scope.

**Где результат соединяется с другими.** Technical signer succession is distinct from subject matter evidence, reviewer mandate, institution authority and currentness duty. Historical signature validity is preserved even if current use is limited.

**Positive.** Independently authorized successor is admitted; exact generation/scope is consumed by a fresh source-use reader and historical signatures remain verifiable.

**Distinguishing negative.** Self-signed replacement, same-key self-appointment, compromised-root-only recovery, old-root rollback or missing revocation history freezes affected signing/promotion/current use.

**Matched removal.** Remove independent recovery/admission and anti-rollback but retain signatures/generation markers; fresh reader rejects.

**Граница контекста.** G07 home is succession/custody. No new institutional succession service. P05/P32/P37/P38 require independent provenance and measured verifier behavior.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Each owner/read path rebinds to the accepted source; preserve parent acceptance stage and external-input classification.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-01.commissioning](../../cards/OPS-01/commissioning.md) | `direct:owner_readiness`: Consume initial commissioning/effective profile and independently appointed technical trust generation or selected duty scope.<br>Source: `task.depends_on[1]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-03.profile-readiness](../../cards/OPS-03/profile-readiness.md) | `direct:owner_readiness`: Consume selected effective runtime profile/readiness only for affected protected use; not as trust authority.<br>Source: `task.depends_on[2]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-03](../../parents/CAP-03.md) | `acceptance:composition`: Acceptance dependency: fresh source-use reader consumes trust and selected source event evidence; composition only.<br>Source: `task.acceptance_dependencies[0]`.<br>Условия: selected parent composed claim; not a new preparation dependency |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `OPS-11`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **binding** — Binding scope, authority, migration, time, input, or lifecycle constraint for trust-root; selectors task.r17_extension.delivery_slices[1], task.r19_extension.question_ids[0], task.r19_extension.question_ids[3], task.r19_extension.question_ids[4], task.r19_extension.question_ids[7], solution.free_grow.data_or_config_growth, solution.free_grow.extension_boundary, solution.composition_contracts[1], solution.deviation_triggers[0], solution.inputs_to_resolve[0] remain load-bearing.
  `task.r17_extension.delivery_slices[1]`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.composition_contracts[1]`; `solution.deviation_triggers[0]`; `solution.inputs_to_resolve[0]`
- **execute** — Direct result/preferred path for trust-root; selectors task.r17_extension.requirement, solution.preferred_solution, solution.implementation_steps[0], solution.implementation_steps[1] name the work and native owner seam.
  `task.r17_extension.requirement`; `solution.preferred_solution`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`
- **join** — Distinguishing behavior, consumer surface, or acceptance evidence for trust-root; selectors task.r17_extension.positive, task.r17_extension.removal, task.r17_extension.quality_cases[0], task.r17_extension.quality_cases[1], task.r17_extension.quality_cases[2], task.r17_extension.quality_cases[3], task.r19_extension.question_slices[0], task.r19_extension.question_slices[1], task.r19_extension.question_slices[2], task.r19_extension.question_slices[5], task.r19_extension.question_slices[6], solution.acceptance_discriminators[0] are checked at its actual reader/sink. Bundled subclauses: U034:{"question_id":"R18-D22-Q04","solution_ref":"solutions/lifecycle-r19/S13.md#r18-d22-q04","mechanism_ids":["S13-M1"],"role":"consumer"}; U035:{"question_id":"R18-D14-Q01","solution_ref":"solutions/lifecycle-r19/S14.md#r18-d14-q01","mechanism_ids":["S14-M0","S14-M1"],"role":"input collection"}; U036:{"question_id":"R18-D18-Q03","solution_ref":"solutions/lifecycle-r19/S15.md#r18-d18-q03","mechanism_ids":["S15-M3"],"role":"consumer"}; U039:{"question_id":"R18-D17-Q05","solution_ref":"solutions/lifecycle-r19/S17.md#r18-d17-q05","mechanism_ids":["S17-M5","S17-M4","S17-M2"],"role":"input collection"}; U040:{"question_id":"R18-D23-Q02","solution_ref":"solutions/lifecycle-r19/S18.md#r18-d23-q02","mechanism_ids":["S18-M2"],"role":"consumer"}.
  `task.r17_extension.positive`; `task.r17_extension.removal`; `task.r17_extension.quality_cases[0]`; `task.r17_extension.quality_cases[1]`; `task.r17_extension.quality_cases[2]`; `task.r17_extension.quality_cases[3]`; `solution.acceptance_discriminators[0]`
- **join** — This occurrence concerns PolicyOS's own technical trust generation and our signature/custody duties; external staff changes remain typed institutional evidence, not our trust event. Parent composition: Compose the distinction between internal responsibility changes and external institution authority; do not imply PolicyOS grants the latter.
  `task.r19_extension.question_slices[0]` (`R18-D22-Q04`); `task.r19_extension.question_ids[6]` (`R18-D22-Q04`)
- **join** — The technical trust-root card admits identity/generation provenance from an independent basis; artifact identity alone cannot establish source truth or evaluator independence.
  `task.r19_extension.question_slices[1]` (`R18-D14-Q01`); `task.r19_extension.question_ids[0]` (`R18-D14-Q01`)
- **join** — The slice checks root succession/currentness while explicitly separating external author semantics, reviewer mandate, jurisdiction and delegation; trust-root owns only PolicyOS technical succession.
  `task.r19_extension.question_slices[2]` (`R18-D18-Q03`); `task.r19_extension.question_ids[4]` (`R18-D18-Q03`)
- **join** — This slice is only independent recovery of a compromised PolicyOS technical root; it expressly does not authorize an institution's emergency policy action.
  `task.r19_extension.question_slices[5]` (`R18-D17-Q05`); `task.r19_extension.question_ids[3]` (`R18-D17-Q05`)
- **join** — The slice's admitted scope is technical issuer/root succession only; a technical successor receipt must not be read as authority to change SDD/constitution. Parent composition: Leave human-principal/SDD amendment authority to its separate ratified governance owner; OPS-11 records no such delegation.
  `task.r19_extension.question_slices[6]` (`R18-D23-Q02`); `task.r19_extension.question_ids[7]` (`R18-D23-Q02`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
