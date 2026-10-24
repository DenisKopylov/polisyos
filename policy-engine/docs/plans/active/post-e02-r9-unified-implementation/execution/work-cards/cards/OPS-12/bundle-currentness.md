# OPS-12.bundle-currentness — Подтверждать локальный bundle generation и as_of

Группа: [G07 — Долгая custody: актуальность, права и переиздание](../../groups/G07.md). Родитель: [OPS-12](../../parents/OPS-12.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** A selected offline protected read is current only for the exact locally imported signed bundle, monotonic verified generation and independently supported as-of/freshness basis read by a fresh local consumer.

**Предпочтительное решение.** Extend existing release manifest/import path and fresh local reader. Consume OPS-11/OPS-01 trust evidence, actual import/readback and owner-approved offline cutoff; preserve explicit stale/historical/limited status when clock or revocation basis is unsupported.

**Граница владельца.** Bundle/profile path remains under OPS-12 canonical `write:exact-path/{canonical_repo_path}` lease; trust root and institutional clock source retain their own owners. Resolve exact file/generation overlap after accepted-source rebind; cloud desired state is read only and cannot prove local import.

**Входы.** Named institution-selected offline profile and commissioning receipt; OPS-11 independently authorized root generation; Exact signed bundle/manifest/schema/rule/source refs and local import event; Independent clock/freshness evidence and owner-approved cutoff; OPS-06 local source-use grant and fresh local reader

**Выход и consumer.** Local import/readback receipt with monotonic generation and as-of basis; fresh protected reader returns current, stale, historical or limited per-operation outcome.

**Что можно готовить независимо.** Bundle format and local-reader interface can be prepared after agreement. Import/current use is enabled only if tier is selected and exact local generation/readback, trust and freshness are proven.

**Где результат соединяется с другими.** Local generation/currentness is separate from cloud/API state, no-egress, OPS-05 recovery and institutional source-use rights. Unselected offline tier remains explicit scope/trigger without parity claim.

**Positive.** Authorized local import supports declared historical/current use within cutoff, after exact generation is observed by the local reader.

**Distinguishing negative.** Old VM/clock/bundle, self-signed or stale generation, expired grant, missing method/model or absent successor cannot inherit cloud currentness; unsupported time yields limited/historical output.

**Matched removal.** Remove local import/as-of/current-reader/anti-rollback check while retaining bundle digest and cloud-ready markers; local protected read does not turn green.

**Граница контекста.** G07 home because the property is continuing currentness/cutoff over an offline policy bundle. No implication of remote freshness or source-current truth; P04/P05/P07/P08/P37/P38 carry explicit time/status/provenance.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted-source rebind and conditional profile choice remain parent stage conditions; local profile can proceed without cloud-profile completion.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-06](../../parents/OPS-06.md) | `direct:owner_readiness`: Consume current source-use rights at local protected read; no-egress or signature does not grant use.<br>Source: `task.depends_on[2]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-11](../../parents/OPS-11.md) | `direct:owner_readiness`: Consume independently authorized technical trust generation/succession only for selected offline operation.<br>Source: `task.depends_on[3]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-01](../../parents/OPS-01.md) | `interface_reference:reference_only_no_new_gate`: Selected offline tier consumes its commissioning receipt. Unselected offline tiers do not gate local/cloud work.<br>Source: `solution.implementation_steps[0]`.<br>Условия: Only the selected native output/interface is consumed; no new preparation prerequisite or authority grant.<br>No new preparation or task-completion gate. The selected existing contract still requires its real output at the actual use described in need; absence blocks that use/claim only. An interface document is not a substituted producer receipt. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `OPS-12`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **binding** — Binding scope, authority, migration, time, input, or lifecycle constraint for bundle-currentness; selectors task.r17_extension.delivery_slices[0], task.r19_extension.question_ids[0], task.r19_extension.question_ids[1], task.r19_extension.question_ids[2], task.r19_extension.question_ids[3], task.r19_extension.question_ids[4], task.r19_extension.question_ids[5], solution.free_grow.data_or_config_growth, solution.free_grow.resource_behavior, solution.deviation_triggers[0], solution.deviation_triggers[1], solution.inputs_to_resolve[1] remain load-bearing.
  `task.r17_extension.delivery_slices[0]`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.resource_behavior`; `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[1]`
- **execute** — Direct result/preferred path for bundle-currentness; selectors task.r17_extension.requirement, solution.implementation_steps[0], solution.implementation_steps[1], solution.implementation_steps[3] name the work and native owner seam.
  `task.r17_extension.requirement`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[3]`
- **join** — Distinguishing behavior, consumer surface, or acceptance evidence for bundle-currentness; selectors task.removal, task.r17_extension.positive, task.r17_extension.adversarial, task.r17_extension.removal, task.r17_extension.quality_cases[0], task.r19_extension.question_slices[0], task.r19_extension.question_slices[2], task.r19_extension.question_slices[3], task.r19_extension.question_slices[4], task.r19_extension.question_slices[5], solution.acceptance_discriminators[0], solution.acceptance_discriminators[1] are checked at its actual reader/sink. Bundled subclauses: U031:{"question_id":"R18-D18-Q04","solution_ref":"solutions/lifecycle-r19/S15.md#r18-d18-q04","mechanism_ids":["S15-M2","S15-M3"],"role":"consumer"}; U033:{"question_id":"R18-D17-Q01","solution_ref":"solutions/lifecycle-r19/S17.md#r18-d17-q01","mechanism_ids":["S17-M1","S17-M2","S17-M4"],"role":"consumer"}; U034:{"question_id":"R18-D17-Q02","solution_ref":"solutions/lifecycle-r19/S17.md#r18-d17-q02","mechanism_ids":["S17-M1","S17-M2","S17-M4"],"role":"consumer"}; U035:{"question_id":"R18-D17-Q05","solution_ref":"solutions/lifecycle-r19/S17.md#r18-d17-q05","mechanism_ids":["S17-M5","S17-M4","S17-M2"],"role":"consumer"}; U036:{"question_id":"R18-D17-Q07","solution_ref":"solutions/lifecycle-r19/S17.md#r18-d17-q07","mechanism_ids":["S17-M5","S17-M2","S17-M1"],"role":"consumer"}.
  `task.removal`; `task.r17_extension.positive`; `task.r17_extension.adversarial`; `task.r17_extension.removal`; `task.r17_extension.quality_cases[0]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`
- **join** — For a selected offline profile this slice verifies imported versions/cutoff/freshness and only declared as-of use; it cannot establish semantic equivalence between jurisdictions or versions. Parent composition: If no semantic relation is established, retain partial/unknown transfer status rather than inferring equivalence from local bundle currency.
  `task.r19_extension.question_slices[0]` (`R18-D18-Q04`); `task.r19_extension.question_ids[5]` (`R18-D18-Q04`)
- **join** — For a selected offline tier, prove the imported local generation and explicit as-of/anti-rollback basis at the local reader; cloud currentness is separate.
  `task.r19_extension.question_slices[2]` (`R18-D17-Q01`); `task.r19_extension.question_ids[1]` (`R18-D17-Q01`)
- **join** — The selected offline operation's actual local import generation/as-of and fresh reader determine support; API/cloud state is not a substitute.
  `task.r19_extension.question_slices[3]` (`R18-D17-Q02`); `task.r19_extension.question_ids[2]` (`R18-D17-Q02`)
- **join** — This slice verifies that the exact signed emergency patch actually reached the selected offline cell and fresh local reader; a cloud patch-ready marker cannot satisfy it.
  `task.r19_extension.question_slices[4]` (`R18-D17-Q05`); `task.r19_extension.question_ids[3]` (`R18-D17-Q05`)
- **join** — The selected offline cell needs a signed monotonic local bundle/as-of and operator receipt before the protected reader becomes current.
  `task.r19_extension.question_slices[5]` (`R18-D17-Q07`); `task.r19_extension.question_ids[4]` (`R18-D17-Q07`)

### Обязанности внутри составных fragments

- `task.r19_extension.question_slices[1]` — Supply local imported generation/as-of and anti-rollback evidence, not a runtime lease fence. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
