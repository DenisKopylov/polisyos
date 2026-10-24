# GYD-21.artifact-validator-map — Вывести полный artifact×validator denominator

Группа: [G10 — Независимые проверки и качество свидетельств](../../groups/G10.md). Родитель: [GYD-21](../../parents/GYD-21.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Complete frozen GY artifact set is joined to every applicable native validator from original requirements/property contracts before invocation records are read.

**Предпочтительное решение.** Wire or extend the existing GX hardening, Task-0, 16 audit and GY-V validator owners; preserve its typed contract and status/time/provenance semantics.

**Граница владельца.** Within GYD-21's native canonical lease family write:exact-path/{canonical_repo_path}. Exact paths and overlap remain unresolved until accepted E02 lease resolution; do not presume disjointness. Existing GX hardening, Task-0, 16 audit and GY-V validator owners.

**Входы.** accepted artifact family and native schemas; validator owners/versions/commands

**Выход и consumer.** Source-derived artifact×validator applicability map

**Что можно готовить независимо.** Preparation may proceed before freeze; final execution follows the parent’s canonical stage and conditional acceptance. No new gate is introduced; resolve accepted E02 source and exact lease before writes.

**Где результат соединяется с другими.** Fresh consumer: owner-wave runner. Map is not substitute registry or global barrier.

**Positive.** Every required artifact-validator pair has an actual owner and resolved input.

**Distinguishing negative.** Omitted artifact/edge cannot disappear because another validator covers same artifact.

**Matched removal.** Remove one required pair while retaining another validator row; pair coverage detects it.

**Граница контекста.** Map is not substitute registry or global barrier.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted source defines the frozen artifact and validator family from which applicability is derived.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [FINAL-REVIEW.independent-review](../../cards/FINAL-REVIEW/independent-review.md) | `acceptance:composition`: FINAL-REVIEW consumes the fully composed outputs at the canonical composition acceptance stage. It does not block independent preparation or add a leaf/preparation gate.<br>Source: `task.acceptance_dependencies[0]`.<br>Условия: selected parent composed claim; not a new preparation dependency |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `GYD-21`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Inventory canonical artifacts/validators, then derive applicability pairs independently from source/property contracts.
  `solution.implementation_steps[0]`; `solution.implementation_steps[1]`
- **binding** — Artifact growth and new semantics follow native owners; no substitute registry/plugin.
  `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`
- **binding** — No uncatalogued drift requires complete source denominator joined to real consumer/verifier coverage.
  `solution.composition_contracts[0]`
- **binding** — Incomplete applicability reports exact affected missing consumer/verification/surface state.
  `solution.deviation_triggers[0]`
- **binding** — Accepted artifact family, exact validator versions/commands, Task-0, 16-audit and input classification define the map.
  `solution.inputs_to_resolve[0]`; `solution.input_resolution_rule`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
