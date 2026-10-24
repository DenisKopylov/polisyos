# GYD-32.s0-substrate — S0: поднять реальный L4 substrate в WMR

Группа: [G01 — Поиск, получение и точная фиксация источников](../../groups/G01.md). Родитель: [GYD-32](../../parents/GYD-32.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Permitted populated L4 registry/panels traverse L1 DCAT/L5 into queryable content-addressed GlobalState/WMR; period/record/schema/snapshot IDs and trust/regime support survive actual query.

**Предпочтительное решение.** Wire or extend the existing Canonical Data Forge registry and Foundry/PDC ingestion bridge; preserve its typed contract and status/time/provenance semantics.

**Граница владельца.** Within GYD-32's native canonical lease family write:exact-path/{canonical_repo_path}. Exact paths and overlap remain unresolved until accepted E02 lease resolution; do not presume disjointness. Canonical Data Forge registry and Foundry/PDC ingestion bridge.

**Входы.** permitted real L4 source and panels; vintage/weights/strata/margins/auxiliaries; trust/identification/regime/calibration

**Выход и consumer.** Content-addressed GlobalState/WMR and real query receipt

**Что можно готовить независимо.** Preparation may proceed before freeze; final execution follows the parent’s canonical stage and conditional acceptance. No new gate is introduced; resolve accepted E02 source and exact lease before writes.

**Где результат соединяется с другими.** Fresh consumer: actual selected method reader. Read-only permitted input; no data copy and historical size is source-era.

**Positive.** Real same-slice/same-hash source preserves IDs and method support.

**Distinguishing negative.** Synthetic/sparse/wrong-world source label or trust/schema mismatch cannot support target claim.

**Matched removal.** Remove source/profile binding while keeping registry metadata; WMR reader loses support/refuses.

**Граница контекста.** Read-only permitted input; no data copy and historical size is source-era.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source/permit/profile criteria are consumed separately by real substrate, free-grow and conditional review-evidence work.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `GYD-32`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Registry/mode change, registry/WMR/value readback, no-copy rollback and source-fact ownership are S0 substrate behavior.
  `task.removal`; `task.surface`; `task.rollback`; `task.migration`
- **execute** — Actual method support, wrong-world/synthetic adversary and substrate/profile removal belong to S0.
  `task.r15_extension.positive`; `task.r15_extension.adversarial`; `task.r15_extension.removal`
- **execute** — Two input-collection subclauses separately require real vintage/weights/unmatched-mass crosswalk and real strata/margins/auxiliaries method rerun; synthetic labels/totals fail.
  `task.r19_extension.question_slices[0]`; `task.r19_extension.question_slices[1]`
- **binding** — Question IDs bind the two S0 source-collection requirements.
  `task.r19_extension.question_ids[0]`; `task.r19_extension.question_ids[1]`
- **execute** — Permitted denominator, full L4/panels→L1/L5→WMR path, query IDs and actual trust/identification/regime/calibration set changes are S0.
  `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`
- **execute** — Bounded read/no-copy, WMR history, separate DataForge/Foundry/PDC owners, same-slice/hash IDs and actual mode/trust/regime/calibration changes belong to S0.
  `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.composition_contracts[2]`
- **execute** — Real panels must query through L1/L5 to WMR with required fields.
  `solution.acceptance_discriminators[0]`
- **binding** — Permitted source, registry owners/access permit and corpus scope are S0 inputs.
  `solution.inputs_to_resolve[0]`
- **secondary_S0_clause — subclause:** Real populated Ukraine L4/panel source path through L1/L5 into content-addressed WMR with source identity and required fields.; source `task.positive`. Primary fragment route stays unchanged; this identifies the owned sub-result.
- **secondary_S0_negative — subclause:** Unknown trust/schema/regime/calibration changes the real bound source set or downgrades/refuses.; source `task.adversarial`. Primary fragment route stays unchanged; this identifies the owned sub-result.
- **secondary_S0_clause — subclause:** Evaluate selected method against the real permitted substrate.; source `task.r15_extension.requirement`. Primary fragment route stays unchanged; this identifies the owned sub-result.
- **secondary_S0_limitation — subclause:** No permitted source leaves the real S0 positive unresolved; unknown trust/schema widens or refuses.; source `solution.deviation_triggers[0]`. Primary fragment route stays unchanged; this identifies the owned sub-result.

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
