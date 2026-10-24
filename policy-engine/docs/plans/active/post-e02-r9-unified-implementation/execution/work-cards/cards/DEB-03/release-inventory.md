# DEB-03.release-inventory — Связать release-fragment API review

Группа: [G08 — Документы, интерфейсы и понятные человеку результаты](../../groups/G08.md). Родитель: [DEB-03](../../parents/DEB-03.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** For each originally named release fragment, public-break inventory matches current generated API/source delta and a content-bound competent owner review.

**Предпочтительное решение.** Reuse architecture/public_surface/contract.toml and generated public inventory; require current symbol delta plus review receipt at promotion.

**Граница владельца.** Public-surface/release owner owns API inventory and review. Native exact-path lease family; exact paths unresolved until E02.

**Входы.** Each original release fragment; regenerated public API inventory; source/API delta; competent owner review.

**Выход и consumer.** Versioned per-fragment break inventory and bound review receipt consumed at release admission.

**Что можно готовить независимо.** После разрешённого исходным stage contract source/lease rebind выполнить первые действия ниже; до разрешённой стадии — только назначенное read-only discovery. Actual supplier outputs нужны при их потреблении, а не для всей независимой подготовки. Карточка не добавляет start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh release promotion/public-surface review consumer.; composition is limited to this property and the exact original scope.

**Positive.** Для каждого named fragment полный symbol delta совпадает с актуальным generated inventory, а promotion читает привязанный к этим bytes owner review и принимает именно эту версию.

**Distinguishing negative.** Один `reviewed` marker, stale inventory или неполный symbol diff без content-bound review не допускает promotion.

**Matched removal.** Отключить resolve/content-binding review receipt, оставив `reviewed=true`; неизменённый promotion test с изменённым public symbol должен упасть, если marker один допускает promotion.

**Граница контекста.** The named fragments and API promotion consumer are distinct from the complete private-name reach census.

## Первые действия и передача

1. Для каждого исходно названного release fragment вычислить актуальный source/API delta относительно regenerated public inventory и выписать затронутые symbols.
2. Сохранить на каждый fragment отдельный content-bound review receipt с inventory version/hash и competent owner.
3. Подать в существующий promotion consumer три записи: свежую, устаревшую и одну только с `reviewed` marker; сохранить решения.

**Ответственность и handoff.** Public-surface/release owner выпускает inventory и review receipt; release promotion consumer проверяет их. Importability сама по себе не означает public API membership.

Порядок действий внутри назначения не добавляет dependency edges. Примеры проверок дополняют полный назначенный criterion; actual commands/paths закрепляются в [packet](../../../task-decomposition/work-packet.md) после source rebind.

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
