# CNT-04.law-version — Зафиксировать версию закона и временные события

Группа: [G02 — Смысл оснований: право, метрики, ценности и участники](../../groups/G02.md). Родитель: [CNT-04](../../parents/CNT-04.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Точная official representation/amendment chain resolves to jurisdiction-qualified source version; publication, commencement, effective, expiry, repeal, exception, transition and notice times stay distinct.

**Предпочтительное решение.** Extend canonical legal corpus/source-version route; preserve original text and each amendment/correction. Source events and parser results support, but do not decide legal effect.

**Граница владельца.** Existing legal-source/corpus owner writes under the native canonical legal-source lease family; official publisher supplies legal content/events, not mechanism code. E02 must resolve exact paths/semantic overlap; unknown paths remain shared.

**Входы.** Sponsor selects jurisdiction/period; official publisher supplies exact governing text and point-in-time version/event history. Reference cards are not governing law.

**Выход и consumer.** Versioned source record/event graph with explicit unknowns; consumed by applicability and legal resolver.

**Что можно готовить независимо.** Read-only source/version census may start; legal effect waits on accepted E02 source and exact owner, verifier, lease and permit.

**Где результат соединяется с другими.** Applicability consumes this version; fresh legal reader resolves as-of provision without confusing text, time roles, competence or PolicyOS knowledge time.

**Positive.** Historical/future/partial/repeal branches follow actual source event record.

**Distinguishing negative.** Draft, unofficial translation, no-hit or missing version history establishes applicable law.

**Matched removal.** Remove event/version binding but retain bytes/hash: fresh reader cannot establish as-of version.

**Граница контекста.** Publisher is content supplier; corpus owner is mechanism owner.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Inherited accepted E02 readiness and scoped source rebind apply to each listed card; no extra start gate is added, and canonical parent stage/dispatch remains authoritative.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CNT-02.source-profile](../../cards/CNT-02/source-profile.md) | `direct:interface_agreement; acceptance:composition`: Resolvable official resource/version metadata; discovery record is not law content/effect.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Supplier [CNT-03.capture-reuse](../../cards/CNT-03/capture-reuse.md) | `acceptance:composition`: CNT-03 persisted capture/admission receipt and selected legal source profile are composed with the exact native method/permission verifier output at CNT-04 acceptance; source intake does not decide legal effect or appoint the legal owner.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: selected parent composed claim; not a new preparation dependency |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `CNT-04`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Exact official text/version/event-history, selected-jurisdiction indexing and publisher's unresolved version are source-version work; publisher supplies content.
  `solution.implementation_steps[0]`
- **execute** — Exact official text/version/event-history, selected-jurisdiction indexing and publisher's unresolved version are source-version work; publisher supplies content.
  `solution.free_grow.resource_behavior`
- **execute** — Exact official text/version/event-history, selected-jurisdiction indexing and publisher's unresolved version are source-version work; publisher supplies content.
  `solution.deviation_triggers[0]`
- **execute** — Exact official text/version/event-history, selected-jurisdiction indexing and publisher's unresolved version are source-version work; publisher supplies content.
  `solution.inputs_to_resolve[0]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
