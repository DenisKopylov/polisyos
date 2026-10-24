# CAP-02.second-source-adapter — Qualify the selected second-source producer

Группа: [G01 — Поиск, получение и точная фиксация источников](../../groups/G01.md). Родитель: [CAP-02](../../parents/CAP-02.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** A second source's actual protocol/parser has its own complete receipt and cannot borrow WDI or another route's proof.

**Предпочтительное решение.** Allocate the selected second source to its existing registered Fabric connector/protocol/parser path, bind its own complete representation receipt and fresh reader to ArtifactManifest/ArtifactRef, then check LIF-08 compatibility before claiming coverage. Do not borrow WDI evidence or add a second global transport/cursor owner. Anchors: fabric/connectors/reference/static_csv.py:StaticCSVConnector.fetch; core/artifacts/manifest.py:ArtifactManifest/ArtifactRef.

**Граница владельца.** Selected native source/connector owner; composed with LIF-08. Parent native lease family: `write:capture-protocol`, `resource:source/{source_profile}/fetch`. Exact post-E02 paths/overlap are unresolved; do not infer sibling disjointness or create a child lease. Root binds the actual path/lease before writes; cards sharing a native family serialize there.

**Входы.** Accepted source identity, protocol class, adapter/parser, exact representation and declared completeness.

**Выход и consumer.** Persisted source-specific root receipt consumed by a fresh reader.

**Что можно готовить независимо.** Agree the root/receipt interface; source-specific conformance can proceed alongside the first route.

**Где результат соединяется с другими.** Join CAP-02 root semantics and LIF-08 compatibility lifecycle before claiming second-source coverage.

**Positive.** Selected non-WDI source completes capture through a fresh consumer.

**Distinguishing negative.** Unsupported parser/continuation cannot inherit WDI's single-response result.

**Matched removal.** Remove this adapter's completeness binding but retain WDI receipt; second-source consumer refuses.

**Граница контекста.** The preferred solution combines four independently reviewable contexts: per-hop network policy, retained representation and reader, conditional continuation/fencing, and a selected second-source adapter. R19 adds exact-content binding; it does not make these transport/protocol properties one mechanism. This is one bounded property view; parent source pins, stage/dispatch, conditional acceptance and mandatory companions remain inherited.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted source/path owner is consumed where selected; no blanket barrier.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-01](../../parents/CAP-01.md) | `direct:owner_readiness; acceptance:composition`: Consume exact selected source/profile; query permission is not body placement or cursor completeness.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Composition output (не start gate) [CAP-02.single-response-root](../../cards/CAP-02/single-response-root.md) | Consume only for the exact composition described here: Join CAP-02 root semantics and LIF-08 compatibility lifecycle before claiming second-source coverage. This link is not an unconditional all-of or preparation gate. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `CAP-02`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Selected non-WDI source requires its own protocol/receipt/fresh reader and LIF-08 result.
  `solution.acceptance_discriminators[5]`
- **binding — subclause:** Allocate the actual second-source capture/parser/protocol sub-slice required by LIF-08; first-route completion cannot substitute.; source `solution.implementation_steps[4]`. Primary fragment route stays unchanged; this identifies the owned sub-result.

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
