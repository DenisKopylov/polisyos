# LIF-07.archive_consumers — Сохранить archive reader

Группа: [G07 — Долгая custody: актуальность, права и переиздание](../../groups/G07.md). Родитель: [LIF-07](../../parents/LIF-07.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Archived history needs actual retained representation/rights; current claim checks currentness.

**Предпочтительное решение.** Consume DES06 archive, LIF05 rights, LIF02 cut and LIF07 lineage.

**Граница владельца.** DES06/LIF05/LIF02 keep archive/rights/currentness owners.

**Входы.** Archive root/representation, rights/placement, historical/current cut.

**Выход и consumer.** Fresh reader returns exact as-of or bounded unavailable.

**Что можно готовить независимо.** No archive owner created.

**Где результат соединяется с другими.** Fresh archive readers return the exact retained/as-of representation or bounded unavailable; currentness and rights are checked only when the selected claim is projected as current or protected.

**Positive.** Lawful history remains as-of.

**Distinguishing negative.** Missing bytes inferred or old history projected current.

**Matched removal.** Remove representation/rights check; reader refuses.

**Граница контекста.** One observable property; other owners remain suppliers/consumers.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Root stage.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-02](../../parents/LIF-02.md) | `direct:owner_readiness`: Consume current/as-of source cut.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-05](../../parents/LIF-05.md) | `direct:owner_readiness`: Consume rights/placement; graph grants nothing.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [LIF-07.computational_influence](../../cards/LIF-07/computational_influence.md) | When the selected archived design needs its actual dependency/read set or source/exposure influence; representation availability is a separate archive result. |
| Composition output (не start gate) [LIF-07.current_use_descendants](../../cards/LIF-07/current_use_descendants.md) | Only when the selected archive is presented as current or used by an affected current descendant; lawful historical/as-of access does not prove currentness. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `LIF-07`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **secondary_execution — subclause:** Historical/as-of archive retention remains rights bounded; older derivatives become stale or contested for current use.; source `task.rollback`. Primary fragment route stays unchanged; this identifies the owned sub-result.
- **secondary_execution — subclause:** Distinguish retained bytes, permitted rendition, external/query reference, and unavailable representation.; source `task.r17_extension.requirement`. Primary fragment route stays unchanged; this identifies the owned sub-result.
- **secondary_execution — subclause:** A fresh archived-design reader derives the actual dependency set and observes cumulative source/exposure change at the affected use.; source `task.r17_extension.positive`. Primary fragment route stays unchanged; this identifies the owned sub-result.
- **secondary_execution — subclause:** Unauthorized cross-case cache reuse cannot pass the fresh archive/use reader.; source `task.r17_extension.adversarial`. Primary fragment route stays unchanged; this identifies the owned sub-result.
- **secondary_execution — subclause:** Source and retained-representation binding remains necessary for the independent read-set consumer.; source `task.r17_extension.removal`. Primary fragment route stays unchanged; this identifies the owned sub-result.
- **secondary_execution — subclause:** Older derivatives may remain historical evidence; current use is stale/contested and rebuild is under current rights/generations.; source `solution.migration_and_rollback`. Primary fragment route stays unchanged; this identifies the owned sub-result.

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
