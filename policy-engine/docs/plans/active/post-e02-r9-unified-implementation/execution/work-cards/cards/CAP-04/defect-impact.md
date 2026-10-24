# CAP-04.defect-impact — Квалифицировать pinned repro и затронутые claims

Группа: [G10 — Независимые проверки и качество свидетельств](../../groups/G10.md). Родитель: [CAP-04](../../parents/CAP-04.md). Роль: `input`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** A versioned defect/compromise changes only claims whose exact dependency on a pinned reproducible failure is established; an incident label alone proves no impact.

**Предпочтительное решение.** Reuse the existing producer/security/quality path and R19 S14-M2/R18-D14-Q02: bind a versioned pinned-build/input reproduction, resolve enrolled execution/descendant links through existing LIF-07, and apply scoped currentness through LIF-02; DEB-06 participates only for a material signed-claim change. This card maps the current producer, repro oracle and actual impact reader now; E02 rebinds paths/lease but does not defer discovery.

**Граница владельца.** Producer/security/quality owners supply and classify the defect; CAP-04 binds provenance, version and reproducibility and owns internal discovery of the native repro/impact consumer chain. E02 confirms accepted paths/lease before writes, not before repo discovery. If no chain exists, report precise absent/unallocated or consumer_missing. Parent lease: `write:source-event-adapter/{owner}`; exact paths/overlap stay unresolved and no child lease is inferred.

**Входы.** Versioned defect/compromise report, pinned build/input reproduction, affected execution/dependency and relevant time roles; internal anchors S14-M0/M2 and R18-D14-Q02 for repro/impact path discovery.

**Выход и consumer.** Typed candidate impact receipt with pinned repro and candidate affected dependencies, plus internal producer/oracle→dependency reader/currentness map or a precise missing-chain state.

**Что можно готовить независимо.** Now trace the existing producer/security/quality owner, independent pinned-repro oracle, enrolled execution/descendant links and LIF-02/LIF-07 fresh impact reader using S14-M2 and R18-D14-Q02; record exact repo anchors and affected property.; Use E02 to rebind accepted paths and parent lease before writes; do not defer internal owner/reader discovery.; Keep source event, local reproducible defect, reported cause/interval and signed-claim reissue as separate evidence; DEB-06 is needed only for a material signed-claim change.

**Где результат соединяется с другими.** Only verified source/relation changes become LIF-02 source events; local defect impact follows existing quality/dependency owner.

**Positive.** Pinned repro scopes impact to claims bound to the affected version.

**Distinguishing negative.** Incident prose/version/adjacency without repro and dependency cannot alter a claim.

**Matched removal.** Keep markers but remove pinned repro/dependency binding; fresh reader refuses scope.

**Граница контекста.** Internal discovery of the existing producer, pinned-repro oracle and impact reader is assigned here; CAP-04 does not appoint a producer/security authority or adjudicate incident. E02 resolves accepted path/lease after discovery; absent chain remains named, not silently awaited.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted selected owner/path consumed when resolved; original stage gate remains.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `CAP-04`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Current route matches: a pinned exact repro qualifies only the local defect; a supplied interval cannot widen impact without enrolled supporting records.
  `task.r19_extension.question_slices[5]` (`R18-D14-Q02`); `task.r19_extension.question_ids[1]` (`R18-D14-Q02`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
