# DEB-09.policy-signer — Проверить predicate-policy signer

Группа: [G06 — Допустимость, полномочия и квалифицированные решения](../../groups/G06.md). Родитель: [DEB-09](../../parents/DEB-09.md). Роль: `input`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Current purpose/scope/time-bound signer evidence authorizes only the intended epoch predicate-policy claim.

**Предпочтительное решение.** Reuse existing epoch-transition origin/institutional provenance and LIF-01 intake/verifier; verify source, content, purpose, scope and time.

**Граница владельца.** External institution supplies act; PolicyOS verifies/admit only. No appointment/default signer service. Native exact-path lease family; exact paths unresolved until E02.

**Входы.** Authentic predicate-policy signer evidence and existing LIF-01 verification interface.

**Выход и consumer.** Role-specific source-qualified signer admission or typed-empty/refusal.

**Что можно готовить независимо.** Rebind source, owner, consumer and exact lease after P0-ACCEPT where applicable; any earlier census/preparation is only what the original parent stage permits. This card neither adds nor removes a start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh scientist/validation/decision_validity protected claim consumer.; composition is limited to this property and the exact original scope.

**Positive.** The accepted inputs produce the bounded result and the fresh consumer accepts the scoped property: Current purpose/scope/time-bound signer evidence authorizes only the intended epoch predicate-policy claim.

**Distinguishing negative.** Self-issued, expired, wrong-purpose or signature-only evidence cannot authorize the claim.

**Matched removal.** Remove the decisive binding for this property while retaining declarations/markers; the named consumer must fail or return its typed unknown/refusal: Current purpose/scope/time-bound signer evidence authorizes only the intended epoch predicate-policy claim.

**Граница контекста.** Non-substitutable external role; does not substitute for transition signer or history holder.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-09 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-01](../../parents/LIF-01.md) | `direct:owner_readiness`: Consume this supplier’s actual accepted output as required by the canonical DEB-09 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[1]`.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [DEB-09.w5-crosswalk](../../cards/DEB-09/w5-crosswalk.md) | Consume only for the exact composition described here: Read the named output through Fresh scientist/validation/decision_validity protected claim consumer.; composition is limited to this property and the exact original scope. This link is not an unconditional all-of or preparation gate. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-09`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — This mixed preferred-solution fragment begins with the predicate-policy signer slot and is accountable here; its other explicitly named non-substitutable role subclauses remain on their dedicated cards and are reconciled by w5-crosswalk.
  `solution.preferred_solution`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
