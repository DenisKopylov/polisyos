# OPS-05.restore-cut — Допускать восстановленный срез после сверки истории

Группа: [G09 — Развёртывание, исполнители, хранилища и ресурсы](../../groups/G09.md). Родитель: [OPS-05](../../parents/OPS-05.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** A selected restored scope reaches fresh protected read only after DB/control/CAS state, required history, rights and the continuity witness outside the actual rollback closure reconcile, with a fence against intervening changes.

**Предпочтительное решение.** Extend the existing replay-or-restore and ControlPlaneStore owners. Restore DB/CAS to quarantine, bind exact snapshot/root/mount/object versions, consume LIF-02 claim/publication replay and LIF-05 rights/retention decisions, then enable the fresh reader. No new archive, backup authority or restore service.

**Граница владельца.** Restore work is within OPS-05 `resource:control/{cell}/backup-restore` and migration coordination; existing database/CAS/LIF owners retain their canonical write leases. Exact resource keys and overlap are resolved after E02 rebind and are not assumed disjoint by labels.

**Входы.** Exact DB snapshot/WAL/timeline and selected filesystem mount or remote bucket/prefix plus CAS manifest/object versions; LIF-02 actual material claim/public-history replay and continuity witness outside the rollback closure; LIF-05 post-snapshot rights, revocation, retention and copy decisions; OPS-03/04 actual selected reader and worker state; OPS-10/12 adapter/bundle result only if selected

**Выход и consumer.** Quarantine restore receipt binds selected cut, history/readiness evidence and fresh-read enablement or a scoped historical/limited refusal; consumer is the existing claim/publication owner and restored-scope reader.

**Что можно готовить независимо.** Migration/quarantine setup may prepare on agreed interfaces. Composition waits only for the selected restored scope’s actual history/right witness and consumer; no whole-claim-domain wait, mandatory new checkpoint service or global P0 inventory replacement.

**Где результат соединяется с другими.** Fresh-read fence joins schema directions, exact database/CAS cut, LIF-02 replay, LIF-05 rights and a fresh authorized reader. A truthful unaffected scope can proceed independently; this retains the parent conditional acceptance requirement for current/protected publication reads.

**Positive.** Backup containing prior signed state plus later withdrawal/reissue yields the correct fresh head after a witness outside rollback closure is reconciled; selected RPO/RTO is measured to the first permitted fresh read.

**Distinguishing negative.** Missing witness/history, stale rights, missing required WAL/object, withdrawal between reconcile and enablement, unsupported reader or changed mount leaves only affected scope quarantined/historical; never reconstruct forbidden data.

**Matched removal.** Remove claim-history witness or the enablement fence but keep hashes/restore markers; a false-current read is refused. Unaffected proven scopes need not wait.

**Граница контекста.** This card joins the physical restore cut and current claim frontier; it does not own rights or claim history. Restore scope is derived from selected native representation and retention decision, not every historical URI. P05/P07/P08/P37/P38/P41 remain decisive.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Each child consumes the accepted E02 source/rebound owner and actual supported boundary; this is the parent dispatch contract, not a new peer dependency.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-03.profile-readiness](../../cards/OPS-03/profile-readiness.md) | `direct:owner_readiness`: Use selected DB/CAS/profile readiness where the protected restore/read path requires it.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-04.external-runner](../../cards/OPS-04/external-runner.md) | `direct:owner_readiness`: Use actual worker/API reader directions and selected durable control-store state.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-05](../../parents/LIF-05.md) | `direct:owner_readiness; conditional_acceptance_requirements:composition`: Consume current rights, retention/deletion classification and sink-use decisions; OPS-05 does not write those decisions.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern; Restore enables current/protected claim or publication reads |
| Supplier [LIF-02](../../parents/LIF-02.md) | `conditional_acceptance_requirements:composition`: Only when restored scope enables current/protected claim or publication reads: join emitted material claim/public-history replay and continuity witness at composition; preserve source conditional acceptance contract.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: Restore enables current/protected claim or publication reads |
| Supplier [LIF-05](../../parents/LIF-05.md) | `direct:owner_readiness; conditional_acceptance_requirements:composition`: Conditional current/protected restore acceptance joins the same rights/history output; no unrelated claim domain or global wait.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern; Restore enables current/protected claim or publication reads |
| Composition output (не start gate) [OPS-05.schema-directions](../../cards/OPS-05/schema-directions.md) | Consume only for the exact composition described here: Fresh-read fence joins schema directions, exact database/CAS cut, LIF-02 replay, LIF-05 rights and a fresh authorized reader. A truthful unaffected scope can proceed independently; this retains the parent conditional acceptance requirement for current/protected publication reads. This link is not an unconditional all-of or preparation gate. |
| Composition output (не start gate) [OPS-05.retained-uses](../../cards/OPS-05/retained-uses.md) | Consume only for the exact composition described here: Fresh-read fence joins schema directions, exact database/CAS cut, LIF-02 replay, LIF-05 rights and a fresh authorized reader. A truthful unaffected scope can proceed independently; this retains the parent conditional acceptance requirement for current/protected publication reads. This link is not an unconditional all-of or preparation gate. |
| Composition output (не start gate) [OPS-05.byte-release](../../cards/OPS-05/byte-release.md) | Consume only for the exact composition described here: Fresh-read fence joins schema directions, exact database/CAS cut, LIF-02 replay, LIF-05 rights and a fresh authorized reader. A truthful unaffected scope can proceed independently; this retains the parent conditional acceptance requirement for current/protected publication reads. This link is not an unconditional all-of or preparation gate. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `OPS-05`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **binding** — Binding scope, authority, migration, time, input, or lifecycle constraint for restore-cut; selectors task.r17_extension.delivery_slices[1], solution.free_grow.extension_boundary, solution.free_grow.resource_behavior, solution.composition_contracts[0], solution.composition_contracts[1], solution.deviation_triggers[1], solution.inputs_to_resolve[0], solution.inputs_to_resolve[1], solution.inputs_to_resolve[2] remain load-bearing.
  `task.r17_extension.delivery_slices[1]`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`; `solution.inputs_to_resolve[2]`
- **execute** — Direct result/preferred path for restore-cut; selectors solution.implementation_steps[1], solution.implementation_steps[3], solution.implementation_steps[4] name the work and native owner seam.
  `solution.implementation_steps[1]`; `solution.implementation_steps[3]`; `solution.implementation_steps[4]`
- **join** — Distinguishing behavior, consumer surface, or acceptance evidence for restore-cut; selectors task.acceptance_steps[5], task.acceptance_steps[6], task.r17_extension.quality_cases[1], task.r17_extension.quality_cases[2], task.r19_extension.question_slices[2], solution.acceptance_discriminators[1], solution.acceptance_discriminators[2] are checked at its actual reader/sink. Bundled subclauses: U040:{"question_id":"R18-D17-Q05","solution_ref":"solutions/lifecycle-r19/S17.md#r18-d17-q05","mechanism_ids":["S17-M5","S17-M4","S17-M2"],"role":"assurance"}.
  `task.acceptance_steps[5]`; `task.acceptance_steps[6]`; `task.r17_extension.quality_cases[1]`; `task.r17_extension.quality_cases[2]`; `task.r19_extension.question_slices[2]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
