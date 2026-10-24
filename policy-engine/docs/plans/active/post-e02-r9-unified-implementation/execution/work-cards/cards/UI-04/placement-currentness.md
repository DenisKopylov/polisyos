# UI-04.placement-currentness — Согласовать history с LIF-02 и LIF-05

Группа: [G07 — Долгая custody: актуальность, права и переиздание](../../groups/G07.md). Родитель: [UI-04](../../parents/UI-04.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Selected history readers показывают scoped LIF-02 reaction и применяют LIF-05 retention/withdrawal/erasure/existence limits перед serving/restore.

**Предпочтительное решение.** Переиспользовать LIF-02 currentness и LIF-05 placement decisions; не менять event ledger, не обещать recall external copies.

**Граница владельца.** UI-04 владеет reader join; LIF-02 owns currentness; LIF-05 owns rights/deletion/restore.  Parent native canonical leases: write:exact-path/{canonical_repo_path}; write:runtime-api-generated-family if changed; resource:browser/{profile} if executed. Bind exact paths and overlap at P0; unresolved paths are not presumed disjoint before E02 rebind.

**Входы.** LIF-02 reaction; conditional LIF-05 generation/outcome; persisted event/parent identity.

**Выход и consumer.** Managed reader показывает permitted historical view/current reaction либо только permitted minimal receipt после erasure.

**Что можно готовить независимо.** Подготовить join independently; actual protected serve/delete/restore waits только на relevant owner output.

**Где результат соединяется с другими.** Compose event source and feed with per-placement rights result; unrelated history остаётся доступным если permitted. The fresh selected feed/history reader consumes LIF-02 currentness, including its conditional selected-duty consequence where a standing-duty guarantee applies; OPS-11 evidence is joined inside LIF-02 at composition, with no UI→OPS-11 gate. For a selected restored protected read, compose LIF-02 material replay/currentness with LIF-05 per-placement rights/retention and the existing OPS-05 restore-cut receipt; OPS-05 owns restore enablement, so this is one reader decision rather than a second admission bit.

**Positive.** Byte-identical allowed history и owner-qualified erasure без recoverable prohibited canary.

**Distinguishing negative.** Caller request не erases; selected cache/export/restore не раскрывает protected content/existence.

**Matched removal.** Убрать LIF-05 join с одного placement: fresh canary read detects disclosure.

**Граница контекста.** Condition placement-specific, не global DS13 start gate.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source identity/commit and source-bound acceptance record used when rebinding this card; original parent dispatch/stage remains authoritative.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-02](../../parents/LIF-02.md) | `direct:interface_agreement; acceptance:composition`: Scoped currentness reaction for exact claim/edition.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Supplier [LIF-05](../../parents/LIF-05.md) | `conditional_acceptance_requirements:composition`: Conditional only where selected persisted event/history placements retain, disclose, delete or restore governed content/identifiers: event persistence and fresh managed readers consume the actual owner-qualified placement generation and permitted receipt/existence decision before the protected effect at composition. Reader preparation remains independent.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: The selected history/publication path retains, discloses, deletes or restores rights-governed content or identifying metadata |
| Composition output (не start gate) [UI-04.event-history](../../cards/UI-04/event-history.md) | Consume only for the exact composition described here: Compose event source and feed with per-placement rights result; unrelated history остаётся доступным если permitted. The fresh selected feed/history reader consumes LIF-02 currentness, including its conditional selected-duty consequence where a standing-duty guarantee applies; OPS-11 evidence is joined inside LIF-02 at composition, with no UI→OPS-11 gate. For a selected restored protected read, compose LIF-02 material replay/currentness with LIF-05 per-placement rights/retention and the existing OPS-05 restore-cut receipt; OPS-05 owns restore enablement, so this is one reader decision rather than a second admission bit. This link is not an unconditional all-of or preparation gate. |
| Composition output (не start gate) [UI-04.feed-projection](../../cards/UI-04/feed-projection.md) | Consume only for the exact composition described here: Compose event source and feed with per-placement rights result; unrelated history остаётся доступным если permitted. The fresh selected feed/history reader consumes LIF-02 currentness, including its conditional selected-duty consequence where a standing-duty guarantee applies; OPS-11 evidence is joined inside LIF-02 at composition, with no UI→OPS-11 gate. For a selected restored protected read, compose LIF-02 material replay/currentness with LIF-05 per-placement rights/retention and the existing OPS-05 restore-cut receipt; OPS-05 owns restore enablement, so this is one reader decision rather than a second admission bit. This link is not an unconditional all-of or preparation gate. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `UI-04`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **binding** — Preserves history/rollback/lifecycle semantics consumed by the existing owner. Source selectors: solution.migration_and_rollback, task.migration, task.rollback.
  `task.rollback`; `task.migration`; `solution.migration_and_rollback`
- **join** — Binds source/oracle/owner behavior or fresh consumer required by the card; parent stage remains canonical. Source selectors: task.acceptance_steps[4].
  `task.acceptance_steps[4]`
- **binding** — Routes extension by its property into the existing currentness/rights/time/audience/evidence owner. Source selectors: task.r17_extension.adversarial, task.r17_extension.delivery_slices[0], task.r17_extension.positive, task.r17_extension.product_verification, task.r17_extension.quality_cases[0], task.r17_extension.quality_cases[1], task.r17_extension.quality_cases[2], task.r17_extension.quality_cases[3], task.r17_extension.quality_cases[4], task.r17_extension.removal, task.r17_extension.requirement.
  `task.r17_extension.requirement`; `task.r17_extension.positive`; `task.r17_extension.adversarial`; `task.r17_extension.removal`; `task.r17_extension.delivery_slices[0]`; `task.r17_extension.quality_cases[0]`; `task.r17_extension.quality_cases[1]`; `task.r17_extension.quality_cases[2]`; `task.r17_extension.quality_cases[3]`; `task.r17_extension.quality_cases[4]`; `task.r17_extension.product_verification`
- **binding** — Q06 requires the complete selected emission/index/search/count/link/error/cache set and paired denied/absent behavior; generic 404 alone is insufficient. Source selectors: task.r19_extension.question_ids[2], task.r19_extension.question_slices[2].
  `task.r19_extension.question_slices[2]`; `task.r19_extension.question_ids[2]`
- **execute** — Applies LIF-05 placement decisions and distinguishes withdrawal/erasure/hold/external-copy scope. Source selectors: solution.implementation_steps[6].
  `solution.implementation_steps[6]`
- **binding** — Binds the card's actual input/status/authority/time predicate and consumer behavior. Source selectors: solution.composition_contracts[4].
  `solution.composition_contracts[4]`
- **join** — This signal exercises the actual card property at a fresh consumer; labels/shape cannot substitute. Source selectors: solution.acceptance_discriminators[6].
  `solution.acceptance_discriminators[6]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
