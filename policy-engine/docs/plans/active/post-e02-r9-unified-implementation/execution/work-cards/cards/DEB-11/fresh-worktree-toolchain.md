# DEB-11.fresh-worktree-toolchain — Воспроизвести fresh-worktree toolchain baseline

Группа: [G09 — Развёртывание, исполнители, хранилища и ресурсы](../../groups/G09.md). Родитель: [DEB-11](../../parents/DEB-11.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Documented fresh-checkout command uses intended editable source, lock, package links and toolchain; setup non-receipt stays distinct from product defect.

**Предпочтительное решение.** Reuse tools/devx/workspace commands and pinned lock/toolchain semantics; reproduce only the original DS19-style baseline after accepted-source rebind.

**Граница владельца.** Workspace/tooling owner owns setup check; no broad install or background process unless original task authorizes it. Native exact-path lease family; paths unresolved until E02.

**Входы.** Recovered DS19 fresh-worktree criterion, exact source/lock/package-link identities and owner command.

**Выход и consumer.** Source-qualified setup receipt with explicit tooling versus product finding.

**Что можно готовить независимо.** После разрешённого исходным stage contract source/lease rebind выполнить первые действия ниже; до разрешённой стадии — только назначенное read-only discovery. Actual supplier outputs нужны при их потреблении, а не для всей независимой подготовки. Карточка не добавляет start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh workspace doctor/check consumer under tools/devx/workspace.; composition is limited to this property and the exact original scope.

**Positive.** Receipt exact owner command связывает intended editable checkout и source revision с pinned lock, package links и toolchain; consumer видит, что import/package resolution направлены в этот checkout. Это подтверждает setup только в заявленном baseline scope.

**Distinguishing negative.** Неверный editable checkout или отсутствующие package links дают setup non-receipt; это не product pass и само по себе не product defect.

**Matched removal.** Reconciliation probe (existing workspace doctor/check invocation remains intact): produce the setup receipt with a wrong editable-checkout or package-link destination while the observed checkout/link target is unchanged, preserving `workspace ready`. Compare the receipt to those observed identities; the existing setup assertion must report mismatch and reject the baseline receipt.

**Граница контекста.** This checks environment identity only, not overall verification and not aiohttp handler behavior.

## Первые действия и передача

1. Выписать из original DS19 criterion точную fresh-checkout команду, ожидаемый source/lock/package-link набор и зафиксированные toolchain semantics.
2. Создать read-only identity sheet текущего целевого worktree: editable source root, lock path/hash, package-link destinations и доступные версии инструментов; отсутствующую setup часть отметить как non-receipt.

**Ответственность и handoff.** Fresh-worktree/toolchain baseline — внутренняя engineering/setup обязанность. Отсутствие настройки не является внешним permission/input и не закрывает исходную DS1/DS19 обязанность.

Порядок действий внутри назначения не добавляет dependency edges. Примеры проверок дополняют полный назначенный criterion; actual commands/paths закрепляются в [packet](../../../task-decomposition/work-packet.md) после source rebind.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-11 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-11`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — These fragments bind the exact fresh-worktree, lock/package-link and toolchain baseline and setup-vs-product distinction.
  `solution.implementation_steps[2]`; `solution.composition_contracts[2]`; `solution.acceptance_discriminators[1]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
