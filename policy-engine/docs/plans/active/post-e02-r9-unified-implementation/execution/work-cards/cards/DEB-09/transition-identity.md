# DEB-09.transition-identity — Проверить transition signer и producer identity

Группа: [G06 — Допустимость, полномочия и квалифицированные решения](../../groups/G06.md). Родитель: [DEB-09](../../parents/DEB-09.md). Роль: `input`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Transition-signing authority and producer identity bind to their intended claim role and remain distinct from policy signer and history holder.

**Предпочтительное решение.** Reuse LIF-01 intake/verification and existing epoch origin fields; bind each evidence object to the exact role.

**Граница владельца.** External act/identity evidence is supplied by its source institution; PolicyOS verifies but does not appoint. Native exact-path lease family; exact paths unresolved until E02.

**Входы.** Authentic transition-signing identity, producer identity and GY-DEF23 slot as precisely rebound; LIF-01 verifier.

**Выход и consumer.** Role-bound transition/producer admission or explicit typed-empty status.

**Что можно готовить независимо.** После разрешённого исходным stage contract source/lease rebind выполнить первые действия ниже; до разрешённой стадии — только назначенное read-only discovery. Actual supplier outputs нужны при их потреблении, а не для всей независимой подготовки. Карточка не добавляет start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh protected transition/current-decision consumer through scientist/validation/decision_validity.py.; composition is limited to this property and the exact original scope.

**Positive.** Transition signer evidence связывается с конкретным epoch transition, а producer identity — с соответствующим producer claim; свежий consumer различает обе роли от predicate-policy signer и history holder. GY-DEF23 учитывается только если rebind подтверждает именно эту роль.

**Distinguishing negative.** Candidate ID, локальный default signer или policy-signer evidence, предъявленный как transition authority/producer identity, остаётся refused.

**Matched removal.** Reconciliation probe (существующий role verifier остаётся включён): поменять местами claim-role references для transition signer и producer identity, оставив обе подписи и `verified` markers. Сверка role-to-claim должна обнаружить подмену и отклонить оба неверно привязанных назначения; GY-DEF23 участвует только если source rebind подтверждает эту роль.

**Граница контекста.** Keep GY-DEF23 here only for its source-confirmed role; never absorb DEB-04 GY-DEF22 or sibling slots.

## Первые действия и передача

1. Сделать role matrix с отдельными строками для predicate-policy signer, transition signer, producer identity и independent history holder, привязав каждую к своему claim ID и source artifact.
2. Перепривязать GY-DEF23 к оригинальному source row и включать его здесь только если этот row действительно описывает transition/producer identity; сохранить решение в crosswalk.
3. Для реально предоставленных артефактов записать outcome существующего LIF-01 verifier по каждой роли, не переиспользуя роль другого slot.

**Ответственность и handoff.** Подлинность transition signer и producer identity даёт соответствующая внешняя институция; раздельная роль-связка и verifier-приёмка — внутренняя инженерная работа. Не поглощать DEB-04 GY-DEF22.

Порядок действий внутри назначения не добавляет dependency edges. Примеры проверок дополняют полный назначенный criterion; actual commands/paths закрепляются в [packet](../../../task-decomposition/work-packet.md) после source rebind.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-09 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-01](../../parents/LIF-01.md) | `direct:owner_readiness`: Consume this supplier’s actual accepted output as required by the canonical DEB-09 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[1]`.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [DEB-09.w5-crosswalk](../../cards/DEB-09/w5-crosswalk.md) | Consume only for the exact composition described here: Read the named output through Fresh protected transition/current-decision consumer through scientist/validation/decision_validity.py.; composition is limited to this property and the exact original scope. This link is not an unconditional all-of or preparation gate. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-09`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — These fragments bind transition signer and producer identity, including the source-rebound GY-DEF23 role only where confirmed.
  `solution.implementation_steps[4]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
