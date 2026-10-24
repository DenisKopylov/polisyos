# OPS-05.schema-directions — Сверить направления миграции и чтения

Группа: [G09 — Развёртывание, исполнители, хранилища и ресурсы](../../groups/G09.md). Родитель: [OPS-05](../../parents/OPS-05.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Every selected reader/writer/schema/rule direction can consume the actual persisted representation before rollout or rollback; an unsupported direction is refused.

**Предпочтительное решение.** Extend ControlPlaneStore versioned expand/dual-compatible/backfill/contract chain; keep tenant/RLS order and runtime-state/CAS schema owners separate. N-1 is one possible direction, not the complete matrix.

**Граница владельца.** The writable owner is the existing control-schema migration family `write:control-schema-migration`; runtime-state and CAS owners are consumed only. Resolve exact migration paths and all overlapping owner leases after E02 rebind; do not claim cross-store transactionality.

**Входы.** Actual selected API/worker/handler readers and writers (OPS-04); Persisted schema/rule versions and exact state dialect; Selected remote/offline reader versions only if OPS-10/12 is activated

**Выход и consumer.** Versioned migration status and direction-specific compatibility decision consumed by rollout/restore admission.

**Что можно готовить независимо.** Enumerate the selected supported reader/writer directions and tenant/RLS order after accepted-source rebind. Migration work can prepare against the agreed contract; actual rollout/restore acceptance requires the real reader on the actual bytes.

**Где результат соединяется с другими.** OPS-04 runner and OPS-10/12 readers join only for selected direction/profile; migration support does not prove recovery, rights replay or actual-byte integrity.

**Positive.** Supported old/new reader consumes real persisted state through the selected direction.

**Distinguishing negative.** New state is readable only by new code, an undeclared older reader remains, or the selected offline/remote reader cannot parse; affected direction refuses.

**Matched removal.** Remove actual round-trip/read checks but keep version/N-1 labels; the incompatible-pair probe must fail.

**Граница контекста.** A discrete compatibility property and native migration owner. N-1 is not a proxy for all supported directions; P28/P29/P38 require real readback and matched directional failure.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Each child consumes the accepted E02 source/rebound owner and actual supported boundary; this is the parent dispatch contract, not a new peer dependency.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-04.external-runner](../../cards/OPS-04/external-runner.md) | `direct:owner_readiness`: Use actual worker/API reader directions and selected durable control-store state.<br>Source: `task.depends_on[2]`.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [OPS-05.restore-cut](../../cards/OPS-05/restore-cut.md) | Consume only for the exact composition described here: OPS-04 runner and OPS-10/12 readers join only for selected direction/profile; migration support does not prove recovery, rights replay or actual-byte integrity. This link is not an unconditional all-of or preparation gate. |
| Composition output (не start gate) [OPS-05.retained-uses](../../cards/OPS-05/retained-uses.md) | Consume only for the exact composition described here: OPS-04 runner and OPS-10/12 readers join only for selected direction/profile; migration support does not prove recovery, rights replay or actual-byte integrity. This link is not an unconditional all-of or preparation gate. |
| Composition output (не start gate) [OPS-05.byte-release](../../cards/OPS-05/byte-release.md) | Consume only for the exact composition described here: OPS-04 runner and OPS-10/12 readers join only for selected direction/profile; migration support does not prove recovery, rights replay or actual-byte integrity. This link is not an unconditional all-of or preparation gate. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `OPS-05`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **binding** — Binding scope, authority, migration, time, input, or lifecycle constraint for schema-directions; selectors task.r17_extension.delivery_slices[0], task.r19_extension.question_ids[0], task.r19_extension.question_ids[1], task.r19_extension.question_ids[2], solution.deviation_triggers[0] remain load-bearing.
  `task.r17_extension.delivery_slices[0]`; `solution.deviation_triggers[0]`
- **execute** — Direct result/preferred path for schema-directions; selectors solution.implementation_steps[0] name the work and native owner seam.
  `solution.implementation_steps[0]`
- **join** — Distinguishing behavior, consumer surface, or acceptance evidence for schema-directions; selectors task.r17_extension.quality_cases[0], task.r19_extension.question_slices[0], task.r19_extension.question_slices[1] are checked at its actual reader/sink. Bundled subclauses: U038:{"question_id":"R18-D17-Q01","solution_ref":"solutions/lifecycle-r19/S17.md#r18-d17-q01","mechanism_ids":["S17-M1","S17-M2","S17-M4"],"role":"primary writer"}; U039:{"question_id":"R18-D17-Q02","solution_ref":"solutions/lifecycle-r19/S17.md#r18-d17-q02","mechanism_ids":["S17-M1","S17-M2","S17-M4"],"role":"primary writer"}.
  `task.r17_extension.quality_cases[0]`
- **join** — This slice is the migration owner's direction-specific compatibility decision over actual persisted dialects/readers; N-1 is only one possible direction.
  `task.r19_extension.question_slices[0]` (`R18-D17-Q01`); `task.r19_extension.question_ids[0]` (`R18-D17-Q01`)
- **join** — Schema-directions owns actual selected read/write/migration/rollback compatibility; a version marker cannot prove a qualified rollback pair.
  `task.r19_extension.question_slices[1]` (`R18-D17-Q02`); `task.r19_extension.question_ids[1]` (`R18-D17-Q02`)

### Обязанности внутри составных fragments

- `task.r19_extension.question_slices[2]` — Check the selected reader/migration/rollback direction for the patch; do not treat compatibility as restore-history proof. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
