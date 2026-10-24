# OPS-11.currentness-duty — Закреплять currentness duty за принявшим owner

Группа: [G07 — Долгая custody: актуальность, права и переиздание](../../groups/G07.md). Родитель: [OPS-11](../../parents/OPS-11.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Each currentness-bearing claim has a real accepted owner/deputy, due/source/time/cadence basis, bounded coverage and reaction/transfer/cutoff; a missed duty limits only the enrolled claim.

**Предпочтительное решение.** OPS-11 binds owner/scope/trust evidence to LIF-04’s existing durable duty/next-trigger owner. LIF-06/OPS-08 provide measured eligibility; LIF-02 consumes actual claim-currentness consequence. No OPS-11 scheduler, notification service or freshness status flag.

**Граница владельца.** OPS-11 writes only accepted-duty/cutoff evidence under parent `write:exact-path/{canonical_repo_path}`; LIF-04 owns due-intent persistence/scheduler, LIF-02 owns claim reaction, and institutional owner accepts/terminates its duty. Exact path overlaps resolve after E02 rebind.

**Входы.** Claim owner/deputy and accepted transfer or authorized cutoff; LIF-04 durable duty identity, admission policy, due/trigger and retry age; LIF-06/OPS-08 bounded capacity and measured coverage; Authoritative correction/revocation source, due-time interpretation/zone and uncertainty; LIF-02 enrolled claim relation and fresh projection

**Выход и consumer.** Typed accepted-duty or signed bounded-cutoff evidence consumed by LIF-04 and the fresh LIF-02 claim-currentness reader; absent/missed duty becomes scoped stale/limited status.

**Что можно готовить независимо.** Duty schema and agreed due/source interface can be prepared before supplier implementation. No protected currentness promise until owner acceptance, bounded capacity and actual LIF-04/LIF-02 composed reader are present.

**Где результат соединяется с другими.** Owner/coverage evidence joins existing durable due-intent; wakeup is a hint, process heartbeat is not proof, and unrelated claims can remain eligible. OPS-08 measures; LIF-04 persists; LIF-02 reacts.

**Positive.** Accepted successor takes future duty with history preserved; a covered duty uses its declared due basis and selected bound; missed duty surfaces promptly on its enrolled claim.

**Distinguishing negative.** Role name without accepted duty, heartbeat without capacity, wrong time zone/lease-time conflation, unaccepted transfer, late timestamp or stale old snapshot cannot retain current status.

**Matched removal.** Remove accepted-duty/coverage binding while keeping owner/deadline labels; LIF-04 cannot admit a covered duty and LIF-02 remains limited.

**Граница контекста.** Currentness input and claim reaction have different owners. P04/P07/P08/P09/P37/P38 govern statuses, rule/time basis and truthful deadline/coverage. No new obligation manager.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Each owner/read path rebinds to the accepted source; preserve parent acceptance stage and external-input classification.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-01.commissioning](../../cards/OPS-01/commissioning.md) | `direct:owner_readiness`: Consume initial commissioning/effective profile and independently appointed technical trust generation or selected duty scope.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-06](../../parents/OPS-06.md) | `direct:owner_readiness`: Consume the exact source-use right when duty coverage gates a selected claim; grant and duty remain separate.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-04](../../parents/LIF-04.md) | `direct:owner_readiness`: LIF-04 remains durable duty/trigger owner; OPS-11 supplies accepted owner/scope evidence only.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-02](../../parents/LIF-02.md) | `direct:owner_readiness`: LIF-02 is the actual enrolled claim-currentness consumer; its status is not OPS-11 output.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-03](../../parents/CAP-03.md) | `acceptance:composition`: Acceptance dependency: fresh source-use reader consumes trust and selected source event evidence; composition only.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: selected parent composed claim; not a new preparation dependency |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `OPS-11`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **binding** — Binding scope, authority, migration, time, input, or lifecycle constraint for currentness-duty; selectors task.r19_extension.question_ids[1], task.r19_extension.question_ids[2], task.r19_extension.question_ids[5], solution.free_grow.resource_behavior, solution.inputs_to_resolve[1], solution.inputs_to_resolve[2] remain load-bearing.
  `task.r19_extension.question_ids[1]`; `task.r19_extension.question_ids[2]`; `task.r19_extension.question_ids[5]`; `solution.free_grow.resource_behavior`; `solution.inputs_to_resolve[1]`; `solution.inputs_to_resolve[2]`
- **execute** — Direct result/preferred path for currentness-duty; selectors solution.implementation_steps[2] name the work and native owner seam.
  `solution.implementation_steps[2]`
- **join** — Distinguishing behavior, consumer surface, or acceptance evidence for currentness-duty; selectors task.r19_extension.question_slices[3], task.r19_extension.question_slices[4], task.r19_extension.question_slices[7], solution.acceptance_discriminators[1] are checked at its actual reader/sink. Bundled subclauses: U037:{"question_id":"R18-D16-Q01","solution_ref":"solutions/lifecycle-r19/S16.md#r18-d16-q01","mechanism_ids":["S16-M1"],"role":"input collection"}; U038:{"question_id":"R18-D16-Q02","solution_ref":"solutions/lifecycle-r19/S16.md#r18-d16-q02","mechanism_ids":["S16-M2"],"role":"input collection"}; U041:{"question_id":"R18-D19-Q04","solution_ref":"solutions/lifecycle-r19/S19.md#r18-d19-q04","mechanism_ids":["S19-M1","S19-M2"],"role":"consumer"}.
  `task.r19_extension.question_slices[3]`; `task.r19_extension.question_slices[4]`; `task.r19_extension.question_slices[7]`; `solution.acceptance_discriminators[1]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
