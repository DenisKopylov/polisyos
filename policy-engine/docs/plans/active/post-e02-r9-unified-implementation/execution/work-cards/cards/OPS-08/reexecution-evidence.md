# OPS-08.reexecution-evidence — Сравнить повторное исполнение с честным baseline

Группа: [G05 — Совместные расчёты, траектории и исследования](../../groups/G05.md). Родитель: [OPS-08](../../parents/OPS-08.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** A selected composition/reexecution efficiency claim is supported only by a matched fresh-recompute comparison with equivalent usefulness/guarantee and the complete actual-work denominator.

**Предпочтительное решение.** Reuse the existing G05 composition/revision evaluation surface and OPS-08/LIF-06 usage records. Count omitted members, failures, memory, reads, spills, persisted work and repeated solver evaluations; timing alone or all-abstain is not a success.

**Граница владельца.** G05 comparison producer and consumer retain their native owner paths; OPS-08 contributes only measured host/resource facts via the parent resource lease family. No generic benchmark service or parallel usage ledger is allocated here.

**Входы.** Selected composition/reexecution output and fresh recompute baseline on matched inputs/profile/usefulness controls; LIF-06/OPS-08 actual resource usage receipts; Method owner’s selected guarantee and accepted environment

**Выход и consumer.** Matched comparison evidence consumed by the selected composition/method owner; reports useful result and full work/resource denominator or leaves performance unclaimed.

**Что можно готовить независимо.** Baseline design and denominator can be prepared after interface agreement. A positive efficiency claim waits for actual matched runs and fresh outputs; current tasks remain UNRUN until accepted-source implementation.

**Где результат соединяется с другими.** Consumes `research-meter` and `class-envelope`; does not authorize selection or assert policy quality. Any benefit claim belongs to the actual G05 consumer and must survive equivalent selected guarantee.

**Positive.** Selective execution reduces measured work while preserving the selected guarantee and a useful fresh result on the commissioned environment.

**Distinguishing negative.** Faster all-abstain, wrong-basis comparison, hidden spill/provider work, omitted members or unjustified complexity/memory claim is not evidence of improvement.

**Matched removal.** Remove actual work/denominator consumer but keep timing markers; the matched comparison no longer supports the efficiency claim.

**Граница контекста.** A distinct G05 verification result, not an OPS-08 runtime mechanism. R16 quality cases constrain the selected comparison only; no full product/performance claim is inferred from a fixture.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: All writers/consumers use the accepted source and task-scoped rebind; preserve parent dispatch, not a new all-task edge.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-06](../../parents/LIF-06.md) | `direct:owner_readiness`: Use the single native aggregate admission/eligibility owner and actual usage receipt; no second shared ledger.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [OPS-08.research-meter](../../cards/OPS-08/research-meter.md) | Only for the selected same-scope composition described by this card: Consumes `research-meter` and `class-envelope`; does not authorize selection or assert policy quality. Any benefit claim belongs to the actual G05 consumer and must survive equivalent selected guarantee. Independent output production/preparation remains allowed; the original parent join reconciles all required outcomes without making this list an all-of. |
| Composition output (не start gate) [OPS-08.class-envelope](../../cards/OPS-08/class-envelope.md) | Only for the selected same-scope composition described by this card: Consumes `research-meter` and `class-envelope`; does not authorize selection or assert policy quality. Any benefit claim belongs to the actual G05 consumer and must survive equivalent selected guarantee. Independent output production/preparation remains allowed; the original parent join reconciles all required outcomes without making this list an all-of. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `OPS-08`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **binding** — Binding scope, authority, migration, time, input, or lifecycle constraint for reexecution-evidence; selectors task.r16_extension.delivery_slices[0], task.r16_extension.delivery_slices[1], task.r16_extension.product_verification remain load-bearing.
  `task.r16_extension.delivery_slices[0]`; `task.r16_extension.delivery_slices[1]`; `task.r16_extension.product_verification`
- **execute** — Direct result/preferred path for reexecution-evidence; selectors task.r16_extension.requirement name the work and native owner seam.
  `task.r16_extension.requirement`
- **join** — Distinguishing behavior, consumer surface, or acceptance evidence for reexecution-evidence; selectors task.r16_extension.positive, task.r16_extension.adversarial, task.r16_extension.removal, task.r16_extension.quality_cases[0], task.r16_extension.quality_cases[1], task.r16_extension.quality_cases[2], task.r16_extension.quality_cases[3], task.r16_extension.quality_cases[4] are checked at its actual reader/sink.
  `task.r16_extension.positive`; `task.r16_extension.adversarial`; `task.r16_extension.removal`; `task.r16_extension.quality_cases[0]`; `task.r16_extension.quality_cases[1]`; `task.r16_extension.quality_cases[2]`; `task.r16_extension.quality_cases[3]`; `task.r16_extension.quality_cases[4]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
