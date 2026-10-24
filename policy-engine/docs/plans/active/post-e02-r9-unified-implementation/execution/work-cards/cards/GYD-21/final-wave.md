# GYD-21.final-wave — Один frozen final validation wave

Группа: [G10 — Независимые проверки и качество свидетельств](../../groups/G10.md). Родитель: [GYD-21](../../parents/GYD-21.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Each unique native validator runs once against actual mapped artifact inputs; its semantic property is recomputed and deciding output/public companion is read back.

**Предпочтительное решение.** Wire or extend the existing Actual owner commands across existing validator families; preserve its typed contract and status/time/provenance semantics.

**Граница владельца.** Within GYD-21's native canonical lease family write:exact-path/{canonical_repo_path}. Exact paths and overlap remain unresolved until accepted E02 lease resolution; do not presume disjointness. Actual owner commands across existing validator families.

**Входы.** artifact-validator-map; frozen artifact bytes; owner commands and results

**Выход и consumer.** One final wave receipt with red/unknown rows and exact capability labels

**Что можно готовить независимо.** Preparation may proceed before freeze; final execution follows the parent’s canonical stage and conditional acceptance. No new gate is introduced; resolve accepted E02 source and exact lease before writes.

**Где результат соединяется с другими.** Fresh consumer: fresh public/generated consumer. Re-run only a materially changed deciding gate; historical outputs remain immutable.

**Positive.** Every required pair has a property-valid owner result.

**Distinguishing negative.** Corrupt field, missing consumer or consumer-asserted gate premise fails or stays not_established.

**Matched removal.** Remove protected property while keeping validator/matrix markers; actual owner verifier fails.

**Граница контекста.** Re-run only a materially changed deciding gate; historical outputs remain immutable.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [FINAL-REVIEW.independent-review](../../cards/FINAL-REVIEW/independent-review.md) | `acceptance:composition`: FINAL-REVIEW consumes the fully composed outputs at the canonical composition acceptance stage. It does not block independent preparation or add a leaf/preparation gate.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: selected parent composed claim; not a new preparation dependency |
| Composition output (не start gate) [GYD-21.artifact-validator-map](../../cards/GYD-21/artifact-validator-map.md) | Consume only for the exact composition described here: Fresh consumer: fresh public/generated consumer. Re-run only a materially changed deciding gate; historical outputs remain immutable. This link is not an unconditional all-of or preparation gate. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `GYD-21`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Identify each real input/property; run each owner once; join artifacts to validators and probe omission/corruption/removal; read public/generated outputs.
  `solution.implementation_steps[2]`; `solution.implementation_steps[3]`; `solution.implementation_steps[4]`
- **binding** — One consolidated wave, bounded probes and immutable historical/red artifacts.
  `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`
- **binding** — Freeze each P37 gate-predicate provenance and fail closed on consumer-asserted/not-established basis.
  `solution.composition_contracts[1]`
- **execute** — Positive whole-family result, corrupt/omitted artifact, marker-preserving property removal and a missing required edge while another covers the artifact are direct wave probes.
  `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`; `solution.acceptance_discriminators[3]`
- **binding** — Late review reprices only affected deciding gates.
  `solution.deviation_triggers[1]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
