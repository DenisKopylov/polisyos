# UI-02.placement-rights — Применить LIF-05 к размещённым readers

Группа: [G07 — Долгая custody: актуальность, права и переиздание](../../groups/G07.md). Родитель: [UI-02](../../parents/UI-02.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** History/index/feed/API/browser/MACHINE/audit/export/cache/restore readers применяют LIF-05 placement-specific display, retention, withdrawal, erasure и permitted-existence outcome.

**Предпочтительное решение.** Переиспользовать LIF-05 owner decision в существующих readers; без второго retention engine и без обещания recall downloaded copies.

**Граница владельца.** UI-02 владеет только join в selected readers; LIF-05 владеет rights/deletion/restore decision и generation.  Parent native canonical leases: write:exact-path/{canonical_repo_path}; write:runtime-api-generated-family if changed; resource:browser/{profile} if executed. Bind exact paths and overlap at P0; unresolved paths are not presumed disjoint before E02 rebind.

**Входы.** LIF-05 current per-placement output, exact record/identifiers/lineage и допустимые disclosure limits.

**Выход и consumer.** Fresh managed reader возвращает permitted history, corrected status/link, withheld view или erased payload/identifiers с законным receipt.

**Что можно готовить независимо.** Bind placement/canary по agreed interface; отсутствие owner output не закрывает protected serve/delete/restore.

**Где результат соединяется с другими.** Conditional только для реально затронутых placements; совместить с UI-04 history и LIF-02 currentness. A fresh selected reader consumes LIF-02 currentness, including the selected-duty consequence when a standing-duty guarantee applies; OPS-11 accepted-duty evidence joins only inside LIF-02 at composition, with no UI→OPS-11 gate. For a selected restored protected read, compose LIF-02 material replay/currentness with LIF-05 per-placement rights/retention and the existing OPS-05 restore-cut receipt; OPS-05 owns restore enablement, so this is one reader decision rather than a second admission bit.

**Positive.** Valid basis сохраняет разрешённый historical read; qualified erasure не даёт recover запрещённый canary.

**Distinguishing negative.** Caller request сам не стирает; скрытые link/count/cache/restore не раскрывают запрещённые данные; external copies вне recall claim.

**Matched removal.** Убрать LIF-05 join в selected reader: fresh canary обнаруживает запрещённый payload.

**Граница контекста.** Placement-specific condition не блокирует самостоятельную PR1a подготовку.

## Первые действия и передача

1. На E02/source rebind перечислить выбранные managed placements и фактические readers, attached metadata/cache/export paths; root закрепляет exact paths/leases, перечень не становится фиксированным списком всех transport типов.
2. Проследить LIF-05 owner-qualified rights/retention result до каждого выбранного egress, а LIF-02 currentness — до exact issued view. Для restore consume OPS-05 cut; UI-02 не создаёт новое restore admission.
3. Использовать permitted-history positive и protected canary, включая identifier/link/count/cache. При тех же inputs отключить один rights join: независимая no-egress assertion должна FAIL на фактическом sink.
4. Передать fresh-reader evidence и незавершённые selected joins root; UI-04 пишет history event, UI-02 связывает issued view и correction/current status. Не обещать recall downloaded или unknown copies.

Первые действия не добавляют start edges; actual commands и selected input/consumer denominator задаются при source rebind.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source identity/commit and source-bound acceptance record used when rebinding this card; original parent dispatch/stage remains authoritative.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-02](../../parents/LIF-02.md) | `direct:owner_readiness`: Selected currentness reaction/as-of for the affected claim/use.<br>Source: `task.depends_on[1]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-05](../../parents/LIF-05.md) | `conditional_acceptance_requirements:composition`: Conditional only for selected rights-governed placements: actual LIF-05 current generation and permitted receipt/existence decision are consumed by the managed readers; bind before the protected display/retention/erasure/restore effect at composition. Reader preparation remains independent.<br>Source: `task.conditional_acceptance_requirements[0]`.<br>Условия: The selected history/publication path retains, discloses, deletes or restores rights-governed content or identifying metadata |
| Composition output (не start gate) [UI-02.public-record](../../cards/UI-02/public-record.md) | Consume only for the exact composition described here: Conditional только для реально затронутых placements; совместить с UI-04 history и LIF-02 currentness. A fresh selected reader consumes LIF-02 currentness, including the selected-duty consequence when a standing-duty guarantee applies; OPS-11 accepted-duty evidence joins only inside LIF-02 at composition, with no UI→OPS-11 gate. For a selected restored protected read, compose LIF-02 material replay/currentness with LIF-05 per-placement rights/retention and the existing OPS-05 restore-cut receipt; OPS-05 owns restore enablement, so this is one reader decision rather than a second admission bit. This link is not an unconditional all-of or preparation gate. |
| Composition output (не start gate) [UI-19.claim-currentness](../../cards/UI-19/claim-currentness.md) | Only for the selected managed derivative/current-status projection, consume exact fresh LIF-02 status plus derivative mapping: a caveat-dropped derivative is changed/unbound while signed parent bytes stay historical. No PR1a/refusal preparation gate and no status writer in UI-02. |
| Composition output (не start gate) [UI-04.event-history](../../cards/UI-04/event-history.md) | Only for the selected managed correction, consume the exact attributed persisted event. UI-04 remains event writer; this is not mandatory for an unrelated public-record/refusal route. |
| Composition output (не start gate) [UI-04.feed-projection](../../cards/UI-04/feed-projection.md) | Selected correction/current-status reader consumes the actual event/feed output with current audience/rights; event history alone does not prove derivative fidelity, which comes from the selected UI-19 mapping. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `UI-02`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **binding** — Preserves history/rollback/lifecycle semantics consumed by the existing owner. Source selectors: solution.migration_and_rollback, task.migration, task.rollback.
  `task.rollback`; `task.migration`; `solution.migration_and_rollback`
- **binding** — Routes extension by its property into the existing currentness/rights/time/audience/evidence owner. Source selectors: task.r17_extension.adversarial, task.r17_extension.delivery_slices[0], task.r17_extension.positive, task.r17_extension.product_verification, task.r17_extension.quality_cases[0], task.r17_extension.quality_cases[1], task.r17_extension.quality_cases[2], task.r17_extension.quality_cases[3], task.r17_extension.quality_cases[4], task.r17_extension.removal, task.r17_extension.requirement.
  `task.r17_extension.requirement`; `task.r17_extension.positive`; `task.r17_extension.adversarial`; `task.r17_extension.removal`; `task.r17_extension.delivery_slices[0]`; `task.r17_extension.quality_cases[0]`; `task.r17_extension.quality_cases[1]`; `task.r17_extension.quality_cases[2]`; `task.r17_extension.quality_cases[3]`; `task.r17_extension.quality_cases[4]`; `task.r17_extension.product_verification`
- **execute** — Consumes owner-qualified LIF-05 placement retention/erasure/restore and allowed existence disclosure. Source selectors: solution.implementation_steps[7].
  `solution.implementation_steps[7]`
- **binding** — Composes LIF-05 placement-specific display, retention, erasure, restore and existence disclosure. Source selectors: solution.composition_contracts[5].
  `solution.composition_contracts[5]`
- **join** — Tests authorized history and owner-qualified erasure across selected readers/caches/restores. Source selectors: solution.acceptance_discriminators[8].
  `solution.acceptance_discriminators[8]`
- **binding** — tasks.json#UI-02.task.r19_extension.question_slices[1] value-matches question_ids[1]. Placement-rights is the selected managed-reader join; existing implementation step 7 covers placement effects; bind the LIF-02 currentness/correction-lineage requirement there, without treating old issued bytes as current or promising recall.
  `task.r19_extension.question_slices[1]` (`R18-D12-Q05`); `task.r19_extension.question_ids[1]` (`R18-D12-Q05`)
- **binding** — tasks.json#UI-02.task.r19_extension.question_slices[2] value-matches question_ids[2]. Bind selected public/MACHINE export readers to the owner-qualified LIF-05 rights result before egress, including audience-bound caches and export/index metadata. Absent or denied inputs emit no value; removing the rights join from one selected path must expose the canary.
  `task.r19_extension.question_slices[2]` (`R18-D12-Q06`); `task.r19_extension.question_ids[2]` (`R18-D12-Q06`)
- **binding** — tasks.json#UI-02.task.r19_extension.question_slices[3] value-matches question_ids[4] (not question_ids[3]). The managed selected-reader links the exact issued view to its current correction/status projection for evidenced placements, distinguishing the historical signed original, changed derivative, and current correction without claiming recall of unknown or downloaded copies.
  `task.r19_extension.question_slices[3]` (`R18-D22-Q03`); `task.r19_extension.question_ids[4]` (`R18-D22-Q03`)
- **binding** — tasks.json#UI-02.task.r19_extension.question_slices[4] value-matches question_ids[3] (not question_ids[4]). Consume authorized correction/history and owner-qualified per-placement disclosure/retention outcomes. Claim copy-control only where evidenced; make no universal-erasure claim.
  `task.r19_extension.question_slices[4]` (`R18-D14-Q04`); `task.r19_extension.question_ids[3]` (`R18-D14-Q04`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
