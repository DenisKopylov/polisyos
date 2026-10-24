# OPS-01.commissioning — Сверить профиль и выдать commissioning receipt

Группа: [G09 — Развёртывание, исполнители, хранилища и ресурсы](../../groups/G09.md). Родитель: [OPS-01](../../parents/OPS-01.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Свежий runtime reader связывает exact build/config digest с фактическим effective profile и независимо назначенным trust generation; разрешение на выбранный source/use подтверждено или protected input удержан.

**Предпочтительное решение.** Расширить существующий deployment topology/release dossier и RuntimeExecutionPolicyResolver. Receipt ссылается на grants, source/claim owners, trust provision, secret/store records; не становится authority issuer или второй configuration service.

**Граница владельца.** Пишет только release/commissioning owner в семейство canonical lease `write:exact-path/{canonical_repo_path}`; точный путь и пересечение с общей trust-generation записью устанавливаются после E02 rebind. Source/rightsholder, institution trust authority и service owner поставляют решения как typed evidence, не как новые PolicyOS owners.

**Входы.** Accepted E02 source and exact selected build/lock/config digest (P0-ACCEPT parent contract); OPS-03 fresh effective-profile and live-instance readback; CAP-03 source/use evidence and its current purpose, audience, time and recipient; Independent initial trust provision and named service-owner decisions; not self-supplied package authority

**Выход и consumer.** Versioned commissioning receipt in the existing release dossier, with fresh operator/profile and source-use readers; unresolved institution premises remain typed limitations and prevent only affected protected use.

**Что можно готовить независимо.** Profile inventory and receipt schema can be prepared against the agreed release contract; issuing or relying on the receipt waits for accepted-source rebind, actual profile readback, independent trust provision and source/use grant. Emergency child receipt is limited to the exact predelegated scope.

**Где результат соединяется с другими.** OPS-02 local candidate run and any protected consumer read the emitted receipt; CAP-03 owns source evidence, OPS-03 owns readiness, and the external trust authority owns appointment. The receipt joins those results; no environment label or signature marker carries authority.

**Positive.** Fresh reader observes the exact selected process/profile and independently provisioned trust generation, and the selected source-use grant covers the action.

**Distinguishing negative.** Production env label with a weaker profile, absent grant, or a self-signed replacement root leaves protected input held; a same-version change to purpose/recipient/root exceeds delegation.

**Matched removal.** Delete effective-profile, grant, or independent-root resolution while retaining env, digest and manifest markers; the fresh protected reader refuses.

**Граница контекста.** One commissioning receipt remains one capability with ordered checkpoints (profile readback → source/trust → scoped change → commission). The supplied grant, issuer, operations targets and trust-root succession remain separate native/external owners. P05/P32/P37/P38: bind and verify substance, classify decisive premises, and test the actual consumer.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Actual E02 acceptance and task-scoped source rebind are inherited dispatch conditions; the receipt consumes the accepted source identity, without adding a new scheduler edge.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-03](../../parents/CAP-03.md) | `acceptance:composition`: At composition consume the actual source/use evidence and its purpose, audience, time and recipient; CAP-03 remains the evidence owner and the commissioning receipt is not an authority substitute.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: selected parent composed claim; not a new preparation dependency |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `OPS-01`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **binding** — Binding scope, authority, migration, time, input, or lifecycle constraint for commissioning; selectors task.rollback, task.migration, task.rollback_precedence, task.r19_extension.status, task.r19_extension.product_verification, task.r19_extension.composition_contract_ref, task.r19_extension.question_ids[0], task.r19_extension.question_ids[1], task.r19_extension.question_ids[2], task.r19_extension.writer_rule, task.r19_extension.acceptance_ref, solution.free_grow.data_or_config_growth, solution.free_grow.extension_boundary, solution.free_grow.resource_behavior, solution.migration_and_rollback, solution.composition_contracts[0], solution.composition_contracts[1], solution.deviation_triggers[0], solution.deviation_triggers[1], solution.inputs_to_resolve[0], solution.inputs_to_resolve[1], solution.inputs_to_resolve[2], solution.input_resolution_rule remain load-bearing.
  `task.rollback`; `task.migration`; `task.rollback_precedence`; `task.r19_extension.status`; `task.r19_extension.product_verification`; `task.r19_extension.composition_contract_ref`; `task.r19_extension.question_ids[0]`; `task.r19_extension.question_ids[1]`; `task.r19_extension.question_ids[2]`; `task.r19_extension.writer_rule`; `task.r19_extension.acceptance_ref`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`; `solution.inputs_to_resolve[2]`; `solution.input_resolution_rule`
- **execute** — Direct result/preferred path for commissioning; selectors task.deliverable, solution.preferred_solution, solution.implementation_steps[0], solution.implementation_steps[1], solution.implementation_steps[2], solution.implementation_steps[3] name the work and native owner seam.
  `task.deliverable`; `solution.preferred_solution`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`
- **join** — Distinguishing behavior, consumer surface, or acceptance evidence for commissioning; selectors task.positive, task.adversarial, task.removal, task.surface, task.acceptance_steps[0], task.acceptance_steps[1], task.acceptance_steps[2], task.acceptance_steps[3], task.acceptance_steps[4], task.mandatory_companions[0], task.mandatory_companions[1], task.mandatory_companions[2], task.mandatory_companions[3], task.mandatory_companions[4], task.r19_extension.question_slices[0], task.r19_extension.question_slices[1], task.r19_extension.question_slices[2], solution.acceptance_discriminators[0], solution.acceptance_discriminators[1] are checked at its actual reader/sink. Bundled subclauses: U022:{"question_id":"R18-D17-Q03","solution_ref":"solutions/lifecycle-r19/S17.md#r18-d17-q03","mechanism_ids":["S17-M2","S17-M1"],"role":"primary writer"}; U023:{"question_id":"R18-D17-Q05","solution_ref":"solutions/lifecycle-r19/S17.md#r18-d17-q05","mechanism_ids":["S17-M5","S17-M4","S17-M2"],"role":"input collection"}; U024:{"question_id":"R18-D17-Q07","solution_ref":"solutions/lifecycle-r19/S17.md#r18-d17-q07","mechanism_ids":["S17-M5","S17-M2","S17-M1"],"role":"primary writer"}.
  `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[4]`; `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`; `task.r19_extension.question_slices[0]`; `task.r19_extension.question_slices[1]`; `task.r19_extension.question_slices[2]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
