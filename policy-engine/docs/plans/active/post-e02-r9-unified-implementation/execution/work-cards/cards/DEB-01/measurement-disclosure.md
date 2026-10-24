# DEB-01.measurement-disclosure — Раскрыть входы измерительных приборов

Группа: [G10 — Независимые проверки и качество свидетельств](../../groups/G10.md). Родитель: [DEB-01](../../parents/DEB-01.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** An absence result is eligible only when declared roots, file types, selectors, exclusions, observed reads, read failures and unresolved selectors reconcile over the complete accepted-source denominator.

**Предпочтительное решение.** Extend the existing FileReadMeasurement/reporting path additively; separate declared sources from observed reads/errors, derive census membership from the accepted tree, and preserve historical receipt meaning.

**Граница владельца.** Existing measurement/instrument owners write their canonical receipts and consumers; no syscall/network reader is introduced. Use native exact-path lease family; exact paths unresolved until E02, not presumed disjoint.

**Входы.** P0-ACCEPT tree; complete current instrument/caller set; owner-confirmed exclusions and named trust-posture sites.

**Выход и consumer.** Versioned source-qualified measurement receipts, migrated instrument census, disclosed roots/predicates/read errors and unknown/limited outcomes.

**Что можно готовить независимо.** После разрешённого исходным stage contract source/lease rebind выполнить первые действия ниже; до разрешённой стадии — только назначенное read-only discovery. Actual supplier outputs нужны при их потреблении, а не для всей независимой подготовки. Карточка не добавляет start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh debt-ledger/trust-posture validators: tools/quality/validation/check_debt_ledger.py and check_trust_claim_posture.py.; composition is limited to this property and the exact original scope.

**Positive.** В принятом дереве полный census находит founding instrument вне прежних roots; при полностью разрешённых roots/selectors и успешных reads повторный запуск даёт тот же site set/checksum, а отсутствие признаётся только если matching evidence нет во всём измеренном наборе.

**Distinguishing negative.** Если root пропущен, файл unreadable или selector не разрешился, measurement возвращает unknown/limited и не выдаёт зелёный absence, даже когда headline и прежние count-маркеры совпадают.

**Matched removal.** Отключить binding observed-read/error/unresolved-selector набора, сохранив declared roots, denominator и report-маркеры; тот же semantic test на пропущенном или unreadable source запускается без изменений и должен упасть, если marker-only путь всё ещё заявляет absence.

**Граница контекста.** One FileReadMeasurement family coherently owns instrument disclosure; runner executable integrity is separate and routed to runner-residual.

## Первые действия и передача

1. В принятом source tree составить полный реестр diagnostics/instruments: путь, file type, root, selector, exclusion и результат; записать denominator, владельцев/текущих callers 303/319 diagnostics и найденный founding instrument вне прежних roots.
2. Для одного реального инструмента выпустить `FileReadMeasurement` с раздельными declared roots и observed reads/errors/unresolved selectors, привязав прочитанное содержимое; повторить на тех же inputs и сохранить сравнение site set/checksum.
3. Назвать два изменившихся trust-posture sites и их выведенные из полного набора identities; сохранить буквальный singleton census predicate.

**Ответственность и handoff.** Канонический FileReadMeasurement/reporting owner пишет receipt; свежие debt-ledger и trust-posture validators читают его. Receipt доказывает факт чтения, не авторитет источника; runner integrity остаётся в отдельной карточке.

Порядок действий внутри назначения не добавляет dependency edges. Примеры проверок дополняют полный назначенный criterion; actual commands/paths закрепляются в [packet](../../../task-decomposition/work-packet.md) после source rebind.

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
