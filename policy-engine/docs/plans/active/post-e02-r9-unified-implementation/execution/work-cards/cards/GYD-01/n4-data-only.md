# GYD-01.n4-data-only — Каноническая data-only квитанция N4

Группа: [G01 — Поиск, получение и точная фиксация источников](../../groups/G01.md). Родитель: [GYD-01](../../parents/GYD-01.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** A real source-bound data-only result resolves at N4 under N9 v8 without claiming protected field-pilot eligibility.

**Предпочтительное решение.** Reuse CanonicalN9PromotionPort, its v8 intake/epoch and the existing data-only producer path; emit a purpose-scoped receipt, not another promotion service.

**Граница владельца.** Only the existing N9 port persists this receipt. Consume existing data-producer evidence and the competent original-owner disposition; do not write protected-mode authority or a field-pilot result. The N9 path is shared with protected admission and must use one canonical lease, serialized after E02 path rebind.

**Входы.** Accepted E02 source and epoch; authentic data-only producer output; N4 obligation; exact source/version hashes.

**Выход и consumer.** Persisted PR1a N4-bound receipt with source hashes, plus exact readback by the existing N9 receipt consumer.

**Что можно готовить независимо.** Rebind the accepted source and N9 owner; trace the actual intake and fresh receipt consumer.; Resolve authentic data-only input and its original owner disposition.

**Где результат соединяется с другими.** This receipt closes PR1a only. It is neither a prerequisite for nor evidence of PR1b or the authentic O0 near-miss; the parent joins the two distinct N9 outcomes and the separate O0 disposition.

**Positive.** A fresh N9 consumer resolves the authentic data-only receipt at the bound source, epoch and ancestry.

**Distinguishing negative.** Wrong source, epoch, ancestry, missing input or a synthetic substitute produces no admissible PR1a receipt.

**Matched removal.** Keep receipt markers while removing source/atom binding; the fresh N9 consumer refuses.

**Граница контекста.** R25 correctly splits PR1a from protected admission because their purpose and evidence differ. They still share one N9 writer/lease. Do not delay PR1a on PR1b or treat it as a pilot eligibility decision.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source and task-scoped source rebind are the source/version basis consumed by this card; original P0-ACCEPT and parent dispatch semantics remain authoritative.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `GYD-01`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — The n4-data-only card owns this source-specific result or constraint and consumes other owners only through the named interface; no sibling rewrites that native owner.
  `task.milestone_predicates.PR1a`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
