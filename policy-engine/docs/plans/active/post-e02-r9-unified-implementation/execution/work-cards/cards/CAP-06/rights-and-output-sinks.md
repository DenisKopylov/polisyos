# CAP-06.rights-and-output-sinks — Release only source-authorized outputs

Группа: [G07 — Долгая custody: актуальность, права и переиздание](../../groups/G07.md). Родитель: [CAP-06](../../parents/CAP-06.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Remote completion/encryption does not authorize storing, ingesting, transferring, or publishing an output.

**Предпочтительное решение.** Apply LIF-05 shared source rights/disclosure at the selected query, resume, cache, restore, export and output-admission sinks; enumerate actual selected CAS/log/browser/provider-temp sinks and bind output, protected-unit overlap, audience and recipient. Encryption or provider completion is not release permission. Anchors: runtime/http/services/control_plane_store.py; fabric/data_plane/orchestrator.py:PartitionedIngestionPlan/run_partitioned_ingestion; LIF-05 AP07 owner.

**Граница владельца.** LIF-05 owns copy/disclosure policy and sink inventory; CAP-06 consumes its selected decision. Parent native lease family: `write:exact-path/{canonical_repo_path}`. Exact post-E02 paths/overlap are unresolved; do not infer sibling disjointness or create a child lease. Root binds the actual path/lease before writes; cards sharing a native family serialize there.

**Входы.** Exact output/root, source rights, protected-unit overlap, purpose, audience/recipient, and actual sink state.

**Выход и consumer.** Admitted derived result or refusal plus the shared disclosure reservation/outcome.

**Что можно готовить независимо.** Verify source-side rights and provider temporary-storage/custody contract for each selected profile.

**Где результат соединяется с другими.** Apply LIF-05 at query, resume, cache, restore, export and result-admission effects; then qualify output meaning separately.

**Positive.** Allowed derived result reaches its audience while restricted raw canaries remain absent from all actual sinks.

**Distinguishing negative.** Revocation, alias/overlap, wrong audience, or unverifiable no-retention claim blocks affected output.

**Matched removal.** Drop sink/recipient/current-rights enforcement but keep transfer markers; controlled sink probe exposes the violation.

**Граница контекста.** The card combines private/federated evidence qualification, durable remote effects/retries, and output-rights/sink enforcement. R15/R16/R17/R19 explicitly assign these to separate native owners; a single implementer otherwise holds statistical, provider, and custody contexts at once. This is one bounded property view; parent source pins, stage/dispatch, conditional acceptance and mandatory companions remain inherited.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted provider/source rebind where relevant; parent stage remains.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-03](../../parents/CAP-03.md) | `direct:interface_agreement; acceptance:composition`: Consume exact admitted roots/current-use identity at input, dispatch, call and output admission.<br>Source: `task.depends_on[2]`; `task.acceptance_dependencies[1]`.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Supplier [LIF-05](../../parents/LIF-05.md) | `direct:interface_agreement; acceptance:composition`: Consume shared rights/AP07 outcome at input, dispatch, calls, resume and sinks.<br>Source: `task.depends_on[4]`; `task.acceptance_dependencies[3]`.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `CAP-06`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — LIF-05 governs use/copy/transfer/resume/cache/export/restore/output sinks; completion, encryption or attestation does not grant release.
  `task.r17_extension.requirement`; `task.r17_extension.positive`; `task.r17_extension.adversarial`; `task.r17_extension.removal`; `solution.implementation_steps[3]`; `solution.composition_contracts[1]`; `solution.composition_contracts[2]`; `solution.acceptance_discriminators[2]`; `solution.acceptance_discriminators[3]`; `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[2]`
- **binding** — R17 Q15/Q17 probes check actual recipient/sink/canaries and preserve allowed derived output while unrelated transfer is refused.
  `task.r17_extension.quality_cases[0]`; `task.r17_extension.quality_cases[1]`; `task.r17_extension.quality_cases[2]`
- **execute** — resume/cache/restore/export must resolve the current LIF-05 decision and policy version while preserving the original reservation/outcome.
  `task.r19_extension.question_slices[2]` (`R18-D14-Q03`); `task.r19_extension.question_ids[2]` (`R18-D14-Q03`)

### Обязанности внутри составных fragments

- `solution.migration_and_rollback` — Quarantine/restored copies under LIF-05 and never return an uncertain disclosure reservation or old authority after revoke. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[0]` — Authorize the aggregate output’s exact recipient/sink under current source rights; remote completion does not authorize release. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[3]` — Admit the persisted result only at the authorized recipient/sink under current rights; remote receipt alone is not output permission. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[4]` — Recheck the applicable permission and exact recipient/sink; an authorized operation receipt does not by itself authorize output release. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[5]` — Recheck permission and recipient under the current LIF-05 policy throughout the selected remote operation; preserve uncertainty after rights or recipient changes. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[6]` — At the selected result sink, enforce current rights for the actual recipient; a call marker or receipt cannot authorize protected use. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
