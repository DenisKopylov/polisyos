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

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source identity/commit and source-bound acceptance record used when rebinding this card; original parent dispatch/stage remains authoritative.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-02](../../parents/LIF-02.md) | `direct:owner_readiness`: Selected currentness reaction/as-of for the affected claim/use.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-05](../../parents/LIF-05.md) | `conditional_acceptance_requirements:composition`: Conditional only for selected rights-governed placements: actual LIF-05 current generation and permitted receipt/existence decision are consumed by the managed readers; bind before the protected display/retention/erasure/restore effect at composition. Reader preparation remains independent.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: The selected history/publication path retains, discloses, deletes or restores rights-governed content or identifying metadata |
| Composition output (не start gate) [UI-02.public-record](../../cards/UI-02/public-record.md) | Consume only for the exact composition described here: Conditional только для реально затронутых placements; совместить с UI-04 history и LIF-02 currentness. A fresh selected reader consumes LIF-02 currentness, including the selected-duty consequence when a standing-duty guarantee applies; OPS-11 accepted-duty evidence joins only inside LIF-02 at composition, with no UI→OPS-11 gate. For a selected restored protected read, compose LIF-02 material replay/currentness with LIF-05 per-placement rights/retention and the existing OPS-05 restore-cut receipt; OPS-05 owns restore enablement, so this is one reader decision rather than a second admission bit. This link is not an unconditional all-of or preparation gate. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `UI-02`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **binding** — Preserves history/rollback/lifecycle semantics consumed by the existing owner. Source selectors: solution.migration_and_rollback, task.migration, task.rollback.
  `task.rollback`; `task.migration`; `solution.migration_and_rollback`
- **binding** — Routes extension by its property into the existing currentness/rights/time/audience/evidence owner. Source selectors: task.r17_extension.adversarial, task.r17_extension.delivery_slices[0], task.r17_extension.positive, task.r17_extension.product_verification, task.r17_extension.quality_cases[0], task.r17_extension.quality_cases[1], task.r17_extension.quality_cases[2], task.r17_extension.quality_cases[3], task.r17_extension.quality_cases[4], task.r17_extension.removal, task.r17_extension.requirement.
  `task.r17_extension.requirement`; `task.r17_extension.positive`; `task.r17_extension.adversarial`; `task.r17_extension.removal`; `task.r17_extension.delivery_slices[0]`; `task.r17_extension.quality_cases[0]`; `task.r17_extension.quality_cases[1]`; `task.r17_extension.quality_cases[2]`; `task.r17_extension.quality_cases[3]`; `task.r17_extension.quality_cases[4]`; `task.r17_extension.product_verification`
- **binding** — Q05 consumes actual LIF-02 scoped reaction/as-of; historical signature cannot render current. Source selectors: task.r19_extension.question_ids[1], task.r19_extension.question_slices[1].
  `task.r19_extension.question_slices[1]`; `task.r19_extension.question_ids[1]`
- **binding** — Q06 requires the complete selected emission/index/search/count/link/error/cache set and paired denied/absent behavior; generic 404 alone is insufficient. Source selectors: task.r19_extension.question_ids[2], task.r19_extension.question_slices[2].
  `task.r19_extension.question_slices[2]`; `task.r19_extension.question_ids[2]`
- **binding** — Q03 appends correction/reply to exact parent and separates informal evidence, formal act and PolicyOS reaction. Source selectors: task.r19_extension.question_ids[4], task.r19_extension.question_slices[3].
  `task.r19_extension.question_slices[3]`; `task.r19_extension.question_ids[4]`
- **binding** — R18-D14-Q04 is routed to the card consuming its named owner output and preserving status/authority/time. Source selectors: task.r19_extension.question_ids[3], task.r19_extension.question_slices[4].
  `task.r19_extension.question_slices[4]`; `task.r19_extension.question_ids[3]`
- **execute** — Consumes owner-qualified LIF-05 placement retention/erasure/restore and allowed existence disclosure. Source selectors: solution.implementation_steps[7].
  `solution.implementation_steps[7]`
- **binding** — Composes LIF-05 placement-specific display, retention, erasure, restore and existence disclosure. Source selectors: solution.composition_contracts[5].
  `solution.composition_contracts[5]`
- **join** — Tests authorized history and owner-qualified erasure across selected readers/caches/restores. Source selectors: solution.acceptance_discriminators[8].
  `solution.acceptance_discriminators[8]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
