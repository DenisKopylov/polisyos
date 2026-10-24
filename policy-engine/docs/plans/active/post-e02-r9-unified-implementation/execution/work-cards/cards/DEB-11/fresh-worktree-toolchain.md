# DEB-11.fresh-worktree-toolchain — Воспроизвести fresh-worktree toolchain baseline

Группа: [G09 — Развёртывание, исполнители, хранилища и ресурсы](../../groups/G09.md). Родитель: [DEB-11](../../parents/DEB-11.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Documented fresh-checkout command uses intended editable source, lock, package links and toolchain; setup non-receipt stays distinct from product defect.

**Предпочтительное решение.** Reuse tools/devx/workspace commands and pinned lock/toolchain semantics; reproduce only the original DS19-style baseline after accepted-source rebind.

**Граница владельца.** Workspace/tooling owner owns setup check; no broad install or background process unless original task authorizes it. Native exact-path lease family; paths unresolved until E02.

**Входы.** Recovered DS19 fresh-worktree criterion, exact source/lock/package-link identities and owner command.

**Выход и consumer.** Source-qualified setup receipt with explicit tooling versus product finding.

**Что можно готовить независимо.** Rebind source, owner, consumer and exact lease after P0-ACCEPT where applicable; any earlier census/preparation is only what the original parent stage permits. This card neither adds nor removes a start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh workspace doctor/check consumer under tools/devx/workspace.; composition is limited to this property and the exact original scope.

**Positive.** The accepted inputs produce the bounded result and the fresh consumer accepts the scoped property: Documented fresh-checkout command uses intended editable source, lock, package links and toolchain; setup non-receipt stays distinct from product defect.

**Distinguishing negative.** Wrong editable checkout or missing package links is a setup non-receipt, not a product pass or unrelated product defect.

**Matched removal.** Remove the decisive binding for this property while retaining declarations/markers; the named consumer must fail or return its typed unknown/refusal: Documented fresh-checkout command uses intended editable source, lock, package links and toolchain; setup non-receipt stays distinct from product defect.

**Граница контекста.** This checks environment identity only, not overall verification and not aiohttp handler behavior.

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
