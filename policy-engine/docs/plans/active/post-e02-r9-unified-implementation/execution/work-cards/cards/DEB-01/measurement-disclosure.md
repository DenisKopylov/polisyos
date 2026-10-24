# DEB-01.measurement-disclosure — Раскрыть входы измерительных приборов

Группа: [G10 — Независимые проверки и качество свидетельств](../../groups/G10.md). Родитель: [DEB-01](../../parents/DEB-01.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** An absence result is eligible only when declared roots, file types, selectors, exclusions, observed reads, read failures and unresolved selectors reconcile over the complete accepted-source denominator.

**Предпочтительное решение.** Extend the existing FileReadMeasurement/reporting path additively; separate declared sources from observed reads/errors, derive census membership from the accepted tree, and preserve historical receipt meaning.

**Граница владельца.** Existing measurement/instrument owners write their canonical receipts and consumers; no syscall/network reader is introduced. Use native exact-path lease family; exact paths unresolved until E02, not presumed disjoint.

**Входы.** P0-ACCEPT tree; complete current instrument/caller set; owner-confirmed exclusions and named trust-posture sites.

**Выход и consumer.** Versioned source-qualified measurement receipts, migrated instrument census, disclosed roots/predicates/read errors and unknown/limited outcomes.

**Что можно готовить независимо.** Rebind source, owner, consumer and exact lease after P0-ACCEPT where applicable; any earlier census/preparation is only what the original parent stage permits. This card neither adds nor removes a start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh debt-ledger/trust-posture validators: tools/quality/validation/check_debt_ledger.py and check_trust_claim_posture.py.; composition is limited to this property and the exact original scope.

**Positive.** The accepted inputs produce the bounded result and the fresh consumer accepts the scoped property: An absence result is eligible only when declared roots, file types, selectors, exclusions, observed reads, read failures and unresolved selectors reconcile over the complete accepted-source denominator.

**Distinguishing negative.** Dropping a root, hiding unreadable input or keeping only markers cannot produce green absence; measured reads do not establish source authority.

**Matched removal.** Remove the decisive binding for this property while retaining declarations/markers; the named consumer must fail or return its typed unknown/refusal: An absence result is eligible only when declared roots, file types, selectors, exclusions, observed reads, read failures and unresolved selectors reconcile over the complete accepted-source denominator.

**Граница контекста.** One FileReadMeasurement family coherently owns instrument disclosure; runner executable integrity is separate and routed to runner-residual.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-01 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-01`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — These fragments bind FileReadMeasurement, full source denominator, instrument roots/selectors, read outcomes and absence validity.
  `solution.preferred_solution`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`; `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
