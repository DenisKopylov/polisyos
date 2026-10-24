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
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted provider/source rebind where relevant; parent stage remains.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-03](../../parents/CAP-03.md) | `direct:interface_agreement; acceptance:composition`: Consume exact admitted roots/current-use identity at input, dispatch, call and output admission.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Supplier [LIF-05](../../parents/LIF-05.md) | `direct:interface_agreement; acceptance:composition`: Consume shared rights/AP07 outcome at input, dispatch, calls, resume and sinks.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `CAP-06`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — LIF-05 governs use/copy/transfer/resume/cache/export/restore/output sinks; completion, encryption or attestation does not grant release.
  `task.r17_extension.requirement`; `task.r17_extension.positive`; `task.r17_extension.adversarial`; `task.r17_extension.removal`; `task.r19_extension.question_slices[2]`; `task.r19_extension.question_ids[2]`; `solution.implementation_steps[3]`; `solution.composition_contracts[1]`; `solution.composition_contracts[2]`; `solution.acceptance_discriminators[2]`; `solution.acceptance_discriminators[3]`; `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[2]`
- **binding** — R17 Q15/Q17 probes check actual recipient/sink/canaries and preserve allowed derived output while unrelated transfer is refused.
  `task.r17_extension.quality_cases[0]`; `task.r17_extension.quality_cases[1]`; `task.r17_extension.quality_cases[2]`
- **binding — subclause:** Quarantine/restored copies under LIF-05 and never return an uncertain disclosure reservation or old authority after revoke.; source `solution.migration_and_rollback`. Primary fragment route stays unchanged; this identifies the owned sub-result.

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
