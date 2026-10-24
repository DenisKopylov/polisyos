# OPS-08.class-envelope — Квалифицировать измеренный класс и полный знаменатель

Группа: [G09 — Развёртывание, исполнители, хранилища и ресурсы](../../groups/G09.md). Родитель: [OPS-08](../../parents/OPS-08.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Production or duty eligibility is asserted only for selected resource classes measured on the actual host with complete supported concurrency/terminal and shared-load denominator; unknown classes remain unqualified.

**Предпочтительное решение.** Extend the existing versioned workload/profile configuration and measured OPS-08 resource results. Include CPU/RSS/native threads, I/O, scratch, bytes, queue/retry/drain, replicas/copies and material reserved support load only where the selected policy claims them; estimates/SLO seed files are not measurements.

**Граница владельца.** OPS-08 workload/profile data stays under the parent’s exact selected profile write scope; `resource:host/{host}/memory-disk` is the active qualification lease. Host and service owners supply physical limits/targets; OPS-08 does not invent them. Exact output paths are set after E02 rebind.

**Входы.** Actual host/platform controls and physical capacity; Complete selected workload/process-class and simultaneous-terminal denominator; Owner-approved resource/reserve/age/error targets; Actual replica/copy/invoice and reserved energy evidence only for claims that include those dimensions

**Выход и consumer.** Versioned measured class envelope with explicit measured/unmeasured/limited boundary and actual utilization/overflow receipt; consumed by LIF-06 admission and by selected profile/service owners.

**Что можно готовить независимо.** Finite class measurement can run inside an existing isolated enforceable envelope and may proceed concurrently with disjoint measurement. Interacting class/cap changes require matched joint-load evidence before production eligibility.

**Где результат соединяется с другими.** A measured envelope is an input to admission and LIF-04 duty selection, not an admission/scheduling owner itself. It reports only its measured denominator; provider spend remains OPS-07 and remote CAS billing/copies remain OPS-10 when selected.

**Positive.** Selected class stays inside measured limits under cold/warm, skewed, concurrent, slow-provider, restart and restore profiles with semantic outcome recorded.

**Distinguishing negative.** Unknown class with no enforceable envelope, omitted active/reserved process, hidden copy/spill, energy support, cardinality loss or isolated-only measurement for an interacting cap cannot establish production/duty eligibility.

**Matched removal.** Remove actual-work denominator or supported-class measurements while retaining timing/SLO markers; the matched-capacity discriminator fails and class eligibility stays unavailable.

**Граница контекста.** This is measurement/qualification evidence, not a universal numeric SLA or cloud parity statement. It keeps complete input operations and denominators visible (P35/P38) and sends only measured outputs to LIF-06/LIF-04.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: All writers/consumers use the accepted source and task-scoped rebind; preserve parent dispatch, not a new all-task edge.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-04.external-runner](../../cards/OPS-04/external-runner.md) | `direct:owner_readiness`: Consume the actual runtime process/worker classes, not agent/reviewer concurrency or a guessed process census.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-06](../../parents/LIF-06.md) | `direct:owner_readiness`: Use the single native aggregate admission/eligibility owner and actual usage receipt; no second shared ledger.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [OPS-08.aggregate-cap](../../cards/OPS-08/aggregate-cap.md) | Only for the selected same-scope composition described by this card: A measured envelope is an input to admission and LIF-04 duty selection, not an admission/scheduling owner itself. It reports only its measured denominator; provider spend remains OPS-07 and remote CAS billing/copies remain OPS-10 when selected. Independent output production/preparation remains allowed; the original parent join reconciles all required outcomes without making this list an all-of. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `OPS-08`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **binding** — Binding scope, authority, migration, time, input, or lifecycle constraint for class-envelope; selectors task.r19_extension.question_ids[4], task.r19_extension.question_ids[5], task.r19_extension.question_ids[6], solution.free_grow.data_or_config_growth, solution.free_grow.resource_behavior, solution.composition_contracts[2], solution.deviation_triggers[0], solution.inputs_to_resolve[0], solution.inputs_to_resolve[1] remain load-bearing.
  `task.r19_extension.question_ids[4]`; `task.r19_extension.question_ids[5]`; `task.r19_extension.question_ids[6]`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.resource_behavior`; `solution.composition_contracts[2]`; `solution.deviation_triggers[0]`; `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`
- **execute** — Direct result/preferred path for class-envelope; selectors solution.implementation_steps[0], solution.implementation_steps[1] name the work and native owner seam.
  `solution.implementation_steps[0]`; `solution.implementation_steps[1]`
- **join** — Distinguishing behavior, consumer surface, or acceptance evidence for class-envelope; selectors task.positive, task.surface, task.acceptance_steps[4], task.r19_extension.question_slices[4], task.r19_extension.question_slices[5], task.r19_extension.question_slices[6], solution.acceptance_discriminators[2], solution.acceptance_discriminators[3] are checked at its actual reader/sink. Bundled subclauses: U053:{"question_id":"R18-D19-Q02","solution_ref":"solutions/lifecycle-r19/S19.md#r18-d19-q02","mechanism_ids":["S19-M1","S19-M2"],"role":"primary writer"}; U054:{"question_id":"R18-D19-Q04","solution_ref":"solutions/lifecycle-r19/S19.md#r18-d19-q04","mechanism_ids":["S19-M1","S19-M2"],"role":"input collection"}; U055:{"question_id":"R18-D19-Q05","solution_ref":"solutions/lifecycle-r19/S19.md#r18-d19-q05","mechanism_ids":["S19-M1","S19-M3"],"role":"input collection"}.
  `task.positive`; `task.surface`; `task.acceptance_steps[4]`; `task.r19_extension.question_slices[4]`; `task.r19_extension.question_slices[5]`; `task.r19_extension.question_slices[6]`; `solution.acceptance_discriminators[2]`; `solution.acceptance_discriminators[3]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
