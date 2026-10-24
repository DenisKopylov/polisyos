# GYD-33.emission-coverage — Проверить actual S2 emitted-family coverage

Группа: [G10 — Независимые проверки и качество свидетельств](../../groups/G10.md). Родитель: [GYD-33](../../parents/GYD-33.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Actual selected bounded S2 emissions are compared with owner-defined available-family denominator; menu/name membership never substitutes for measured emitted output.

**Предпочтительное решение.** Wire or extend the existing S2 producer/output and coverage reader; preserve its typed contract and status/time/provenance semantics.

**Граница владельца.** Within GYD-33's native canonical lease family write:exact-path/{canonical_repo_path}. Exact paths and overlap remain unresolved until accepted E02 lease resolution; do not presume disjointness. Existing S2 producer/output and coverage reader.

**Входы.** actual selected S2 outputs; owner-defined available-family denominator/version

**Выход и consumer.** Persisted emitted-vs-available coverage receipt

**Что можно готовить независимо.** Preparation may proceed before freeze; final execution follows the parent’s canonical stage and conditional acceptance. No new gate is introduced; resolve accepted E02 source and exact lease before writes.

**Где результат соединяется с другими.** Fresh consumer: actual S2/N12 coverage reader. This R14 property has a distinct measured object/denominator from L2/L3 binding; no new producer.

**Positive.** Each counted emitted family resolves to actual output and full denominator.

**Distinguishing negative.** A menu entry, label or selected name without output cannot count.

**Matched removal.** Remove non-first emitted result or alter denominator while retaining names; readout changes or is not_established.

**Граница контекста.** This R14 property has a distinct measured object/denominator from L2/L3 binding; no new producer.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted source criteria consumed by distinct L2, L3 and selected S2-emission measurements; the bridge consumes the source-card outputs.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `GYD-33`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — R14 specifically measures emitted instrument_family_coverage from actual selected S2 outputs, not available menu/name membership.
  `task.r14_extension.requirement`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
