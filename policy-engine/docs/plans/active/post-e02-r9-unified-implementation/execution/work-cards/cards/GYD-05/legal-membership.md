# GYD-05.legal-membership — Юридическое членство по источнику и ruling

Группа: [G02 — Смысл оснований: право, метрики, ценности и участники](../../groups/G02.md). Родитель: [GYD-05](../../parents/GYD-05.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Purpose-, subject-, jurisdiction-, context- and time-scoped legal membership is recomputed from an independent CORR-B1 source, while authority changes only after a competent ruling is admitted.

**Предпочтительное решение.** Reuse LegalSubjectMembershipSource, LegalCorrespondenceRequest and LegalCorrespondenceResult in foundry/validation/legal_correspondence.py.

**Граница владельца.** PolicyOS owns the source-bound comparison and its typed refusal, not the institution’s membership act or acceptance ruling. Keep source membership and ruling as distinct evidence; no separate legal authority subsystem or signer around a proposal map.

**Входы.** Independent CORR-B1 legal-subject membership source and version.; Competent acceptance/succession ruling with authority, jurisdiction and date.; Requested subject/context/period and existing legal-correspondence consumer.

**Выход и consumer.** Persisted source-bound membership comparison/result with the ruling identity and scope, consumed by LegalCorrespondenceResult reader.

**Что можно готовить независимо.** Rebind CORR-B1 and the ruling interface, scope and time fields.; Ingest membership and ruling separately.; Recompute only for a matching source/version; preserve candidate status if authority is unresolved.

**Где результат соединяется с другими.** Fresh legal-correspondence readback joins scoped source membership to the institutional act; absent or disputed competence leaves authority not_established.

**Positive.** In-scope source membership permits a recomputed comparison; only an admitted ruling changes the authority status.

**Distinguishing negative.** Proposal-supplied map, wrong jurisdiction/time, legal ID used as causal-cohort proof, or unruled match remains blocked.

**Matched removal.** Remove source content binding or ruling; the comparison cannot support an authority-bearing result.

**Граница контекста.** Membership is a G02 foundation. Legal meaning and authority remain source/ruling-bound (P05/P07/P08/P19); keep the candidate relation visible without upgrading it.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source and task-scoped source rebind are the source/version basis consumed by this card; original P0-ACCEPT and parent dispatch semantics remain authoritative.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `GYD-05`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — The legal-membership card owns this source-specific result or constraint and consumes other owners only through the named interface; no sibling rewrites that native owner.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.rollback`; `task.migration`; `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[4]`; `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`; `task.r19_extension.status`; `task.r19_extension.product_verification`; `task.r19_extension.composition_contract_ref`; `task.r19_extension.question_slices[0]`; `task.r19_extension.question_slices[1]`; `task.r19_extension.question_ids[0]`; `task.r19_extension.question_ids[1]`; `task.r19_extension.writer_rule`; `task.r19_extension.acceptance_ref`; `solution.preferred_solution`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.deviation_triggers[0]`; `solution.inputs_to_resolve[0]`; `solution.input_resolution_rule`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
