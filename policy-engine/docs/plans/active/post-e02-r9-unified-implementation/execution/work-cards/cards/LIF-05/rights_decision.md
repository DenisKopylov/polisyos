# LIF-05.rights_decision — Сформировать source-use/AP07 решение

Группа: [G06 — Допустимость, полномочия и квалифицированные решения](../../groups/G06.md). Родитель: [LIF-05](../../parents/LIF-05.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** One qualified decision binds authority/action/purpose/audience/unit/overlap/effective time; retention default is not grant.

**Предпочтительное решение.** LIF05 owns sole decision consumed by CAP03/06; bind `write:semantic-owner/source-disclosure` to real producer after E02, or allocate narrow owner if absent.

**Граница владельца.** Retain native `write:semantic-owner/source-disclosure`,`write:governed-copy`,`resource:cas/{tenant}/{cell}/{root}`; paths unresolved/no disjointness.

**Входы.** Competent act, LIF01 relation/use, AP07 unit/recipient and actual consumer needs; input does not appoint supplier.

**Выход и consumer.** Persisted decision/generation.

**Что можно готовить независимо.** One semantic decision owner.

**Где результат соединяется с другими.** Unknown authority blocks only affected use.

**Positive.** Exact authorized use and lawful sharing pass.

**Distinguishing negative.** Read becomes publish, overlap disjoint by assertion, signature/default treated current grant.

**Matched removal.** Remove actual decision while retaining fields; sink refuses.

**Граница контекста.** One observable property; other owners remain suppliers/consumers.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Root stage.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-01](../../parents/LIF-01.md) | `direct:owner_readiness`: Consume exact relation/use; LIF05 owns action decision.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-03](../../parents/CAP-03.md) | `acceptance:composition`: Actual selected output is consumed by the local composition reader; acceptance is composition-only, not a preparation prerequisite.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: selected parent composed claim; not a new preparation dependency |
| Supplier [CAP-06](../../parents/CAP-06.md) | `acceptance:composition`: Actual selected output is consumed by the local composition reader; acceptance is composition-only, not a preparation prerequisite.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: selected parent composed claim; not a new preparation dependency |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `LIF-05`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Grant and purpose.
  `task.positive[0]`
- **execute** — R18-D05-Q05 source rule and ID.
  `task.r19_extension.question_slices[0]`; `task.r19_extension.question_ids[0]`
- **execute** — R18-D09-Q01 relation vs action grant.
  `task.r19_extension.question_slices[1]`; `task.r19_extension.question_ids[1]`
- **execute** — Single decision owner and decision fields.
  `solution.preferred_solution`; `solution.implementation_steps[0]`
- **execute** — Decision API, profiles, boundary, budgets.
  `solution.implementation_steps[4]`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`
- **binding** — Canonical decision/generation.
  `solution.composition_contracts[0]`
- **execute** — Positive authorized use.
  `solution.acceptance_discriminators[0]`
- **execute** — Retention/access default not grant.
  `solution.acceptance_discriminators[3]`
- **binding** — Competent rights act input, not appointment.
  `solution.inputs_to_resolve[0]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
