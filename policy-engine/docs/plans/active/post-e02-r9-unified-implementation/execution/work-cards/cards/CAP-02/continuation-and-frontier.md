# CAP-02.continuation-and-frontier — Activate a selected range or paginated protocol

Группа: [G01 — Поиск, получение и точная фиксация источников](../../groups/G01.md). Родитель: [CAP-02](../../parents/CAP-02.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Only source-supported complete coverage and a fenced expected-head commit advance resumable progress.

**Предпочтительное решение.** For a selected pagination/range route, persist each source-bound page/range receipt and commit the final cut through the existing CursorStore.save_partition_state expected-head/attempt fence after LIF-03 conformance. Keep byte assembly/source completeness distinct from cursor ownership; unsupported or stale progress remains partial/refused. Anchor: fabric/data_plane/cursor_store.py:CursorStore.save_partition_state.

**Граница владельца.** Source-specific adapter consumes LIF-03 cursor/frontier owner; CAP-02 adds no cursor writer. Parent native lease family: `write:capture-protocol`, `resource:source/{source_profile}/fetch`. Exact post-E02 paths/overlap are unresolved; do not infer sibling disjointness or create a child lease. Root binds the actual path/lease before writes; cards sharing a native family serialize there.

**Входы.** Qualified source/query/cut, validators, continuation/page receipts, current frontier and attempt.

**Выход и consumer.** Persisted page/range receipts and committed final cut or partial/refused result.

**Что можно готовить независимо.** Adapter conformance and source-native completeness/cut evidence; bounded single-response route remains independently usable.

**Где результат соединяется с другими.** Join LIF-03 expected-head/recovery proof before publishing any advanced cursor.

**Positive.** Gap-free pages/ranges assemble and only the current attempt commits the cut.

**Distinguishing negative.** Gap, overlap, conflicting duplicate, changed selector, missing cut, or stale writer stays partial/refused.

**Matched removal.** Remove actual expected-head fencing while markers remain; stale cursor publication must be caught.

**Граница контекста.** The preferred solution combines four independently reviewable contexts: per-hop network policy, retained representation and reader, conditional continuation/fencing, and a selected second-source adapter. R19 adds exact-content binding; it does not make these transport/protocol properties one mechanism. This is one bounded property view; parent source pins, stage/dispatch, conditional acceptance and mandatory companions remain inherited.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted source/path owner is consumed where selected; no blanket barrier.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-01](../../parents/CAP-01.md) | `direct:owner_readiness; acceptance:composition`: Consume exact selected source/profile; query permission is not body placement or cursor completeness.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Supplier [LIF-03.conditional_frontier_commit](../../cards/LIF-03/conditional_frontier_commit.md) | `conditional_acceptance_requirements:composition`: Only when the selected protocol claims pagination, resumable/range progress, partition frontier or competing progress writers: consume receipt-before-frontier plus expected-head/attempt recovery fence before enabling that protocol. This is not a blanket start gate; the bounded single-response path remains independent.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: The selected protocol claims pagination, resumable/range progress, partition frontier, or competing progress writers |
| Composition output (не start gate) [CAP-02.single-response-root](../../cards/CAP-02/single-response-root.md) | Consume only for the exact composition described here: Join LIF-03 expected-head/recovery proof before publishing any advanced cursor. This link is not an unconditional all-of or preparation gate. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `CAP-02`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Only source-supported continuation/range/cut and LIF-03 expected-head commit advance progress; no CAP cursor writer.
  `task.acceptance_steps[4]`; `solution.implementation_steps[3]`; `solution.implementation_steps[4]`; `solution.free_grow.extension_boundary`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.deviation_triggers[0]`; `solution.inputs_to_resolve[1]`
- **binding — subclause:** Strong If-Range, valid Content-Range, gap-free nonoverlapping assembly and whole-body digest; a 200 replaces the partial path.; source `solution.implementation_steps[2]`. Primary fragment route stays unchanged; this identifies the owned sub-result.
- **binding — subclause:** A backend lacking LIF-03 conditional-head or LIF-05 rights enforcement remains unsupported; no parallel cursor or permission owner.; source `solution.deviation_triggers[1]`. Primary fragment route stays unchanged; this identifies the owned sub-result.

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
