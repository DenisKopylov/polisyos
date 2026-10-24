# DEB-03.release-inventory — Связать release-fragment API review

Группа: [G08 — Документы, интерфейсы и понятные человеку результаты](../../groups/G08.md). Родитель: [DEB-03](../../parents/DEB-03.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** For each originally named release fragment, public-break inventory matches current generated API/source delta and a content-bound competent owner review.

**Предпочтительное решение.** Reuse architecture/public_surface/contract.toml and generated public inventory; require current symbol delta plus review receipt at promotion.

**Граница владельца.** Public-surface/release owner owns API inventory and review. Native exact-path lease family; exact paths unresolved until E02.

**Входы.** Each original release fragment; regenerated public API inventory; source/API delta; competent owner review.

**Выход и consumer.** Versioned per-fragment break inventory and bound review receipt consumed at release admission.

**Что можно готовить независимо.** Rebind source, owner, consumer and exact lease after P0-ACCEPT where applicable; any earlier census/preparation is only what the original parent stage permits. This card neither adds nor removes a start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh release promotion/public-surface review consumer.; composition is limited to this property and the exact original scope.

**Positive.** The accepted inputs produce the bounded result and the fresh consumer accepts the scoped property: For each originally named release fragment, public-break inventory matches current generated API/source delta and a content-bound competent owner review.

**Distinguishing negative.** Bare marker, stale inventory, incomplete symbol diff, or importability cannot stand in for content-bound review.

**Matched removal.** Remove the decisive binding for this property while retaining declarations/markers; the named consumer must fail or return its typed unknown/refusal: For each originally named release fragment, public-break inventory matches current generated API/source delta and a content-bound competent owner review.

**Граница контекста.** The named fragments and API promotion consumer are distinct from the complete private-name reach census.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-03 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-03`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — These fragments require per-fragment generated public API/source delta and content-bound release review.
  `task.acceptance_evidence_requirements[1]`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`; `solution.free_grow.data_or_config_growth`; `solution.composition_contracts[1]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`; `solution.inputs_to_resolve[0]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
