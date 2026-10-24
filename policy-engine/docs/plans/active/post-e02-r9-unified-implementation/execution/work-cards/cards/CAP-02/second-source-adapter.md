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
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted source/path owner is consumed where selected; no blanket barrier.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-01.candidate-resolution](../../cards/CAP-01/candidate-resolution.md) | `direct:owner_readiness; acceptance:composition`: Exact persisted source/profile/selector receipt from candidate-resolution; query-disclosure authorization additionally applies only when the selected route actually emits a query. A selected CNT-02 profile/version is bound upstream through CAP-01; it is not a blanket extra CAP-02 dependency.<br>Source: `task.depends_on[1]`; `task.acceptance_dependencies[0]`.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Composition output (не start gate) [CAP-02.single-response-root](../../cards/CAP-02/single-response-root.md) | Consume only for the exact composition described here: Join CAP-02 root semantics and LIF-08 compatibility lifecycle before claiming second-source coverage. This link is not an unconditional all-of or preparation gate. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `CAP-02`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Selected non-WDI source requires its own protocol/receipt/fresh reader and LIF-08 result.
  `solution.acceptance_discriminators[5]`

### Обязанности внутри составных fragments

- `solution.implementation_steps[4]` — Allocate the actual second-source capture/parser/protocol sub-slice required by LIF-08; first-route completion cannot substitute. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
