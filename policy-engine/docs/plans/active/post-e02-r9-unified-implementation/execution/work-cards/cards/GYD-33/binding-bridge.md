# GYD-33.binding-bridge — Связать L2/L3 в N4, N8, N1 и N2

Группа: [G06 — Допустимость, полномочия и квалифицированные решения](../../groups/G06.md). Родитель: [GYD-33](../../parents/GYD-33.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** One bridge resolves/binds/verifies both source-specific packages and propagates contested/transport/as-of status at real consumers; unrelated grounded result remains usable.

**Предпочтительное решение.** Wire or extend the existing One existing typed L2/L3 binding bridge and actual downstream consumers; preserve its typed contract and status/time/provenance semantics.

**Граница владельца.** Within GYD-33's native canonical lease family write:exact-path/{canonical_repo_path}. Exact paths and overlap remain unresolved until accepted E02 lease resolution; do not presume disjointness. One existing typed L2/L3 binding bridge and actual downstream consumers.

**Входы.** scholar-l2 output; lex-l3 output; N4/N8/N1/N2 contract and rule/time version

**Выход и consumer.** Persisted verified bridge result and consumer readbacks

**Что можно готовить независимо.** Preparation may proceed before freeze; final execution follows the parent’s canonical stage and conditional acceptance. No new gate is introduced; resolve accepted E02 source and exact lease before writes.

**Где результат соединяется с другими.** Fresh consumer: fresh N4/N8/N1/N2 readers. Bridge owns no upstream source writer, GY-K adjudication or GY-G composition.

**Positive.** Only disputed output is limited; independently grounded result can pass.

**Distinguishing negative.** Fake source, missing denominator, wrong date or presence-only graph row cannot pass.

**Matched removal.** Remove bridge binding but keep source/graph markers; real consumers refuse/downgrade.

**Граница контекста.** Bridge owns no upstream source writer, GY-K adjudication or GY-G composition.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Composition output (не start gate) [GYD-33.scholar-l2](../../cards/GYD-33/scholar-l2.md) | Only for the selected same-scope composition described by this card: Fresh consumer: fresh N4/N8/N1/N2 readers. Bridge owns no upstream source writer, GY-K adjudication or GY-G composition. Independent output production/preparation remains allowed; the original parent join reconciles all required outcomes without making this list an all-of. |
| Composition output (не start gate) [GYD-33.lex-l3](../../cards/GYD-33/lex-l3.md) | Only for the selected same-scope composition described by this card: Fresh consumer: fresh N4/N8/N1/N2 readers. Bridge owns no upstream source writer, GY-K adjudication or GY-G composition. Independent output production/preparation remains allowed; the original parent join reconciles all required outcomes without making this list an all-of. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `GYD-33`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Parent criteria and fresh N-reader surface close only when the single actual bridge resolves source-specific L2/L3 outputs; GY-K appointment stays separate.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.rollback`; `task.migration`
- **join** — Bundled question slices require Scholar/Lex source-owner/time evidence, fresh amendment-as-of readback, contested/threshold propagation and an unaffected grounded result.
  `task.r19_extension.question_slices[0]`; `task.r19_extension.question_slices[1]`; `task.r19_extension.question_ids[0]`; `task.r19_extension.question_ids[1]`
- **execute** — Keep writers separate, bind typed artifacts with source/rule/time, read N4/N8/N1/N2, propagate statuses and exercise fake/missing/wrong-date/removed-bridge probes.
  `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`
- **binding** — New protocol uses one typed bridge; incomplete required subgraph/as-of threshold widens or refuses.
  `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`
- **execute** — Bridge verifies provenance/as-of, propagates contested/transport limits and fails at real reader for fake item, missing denominator, wrong date or removed binding.
  `solution.composition_contracts[1]`; `solution.composition_contracts[2]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`
- **binding** — Missing owner/time semantics stays limited; partial graph cannot infer support.
  `solution.deviation_triggers[0]`
- **secondary_bridge_consumer — subclause:** One typed bridge consumes both outputs and fresh N4/N8/N1/N2 readbacks.; source `solution.preferred_solution`. Primary fragment route stays unchanged; this identifies the owned sub-result.
- **secondary_bridge_rebind — subclause:** Bridge binds and reads back the separately versioned L2/L3 facts under source/rule/time identity.; source `solution.implementation_steps[0]`. Primary fragment route stays unchanged; this identifies the owned sub-result.

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
