# UI-01.denied-absent — Сделать denied и absent неразличимыми

Группа: [G08 — Документы, интерфейсы и понятные человеку результаты](../../groups/G08.md). Родитель: [UI-01](../../parents/UI-01.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** На выбранных public verification путях denied/absent не раскрывают наличие через body/status/header/id/count/link/index/search/error/ETag/cache.

**Предпочтительное решение.** Перечислить actual selected readers/emission/cache paths на P0; paired canary проверяет фактическую permission/audience границу; generic 404 недостаточен.

**Граница владельца.** UI-01 выполняет disclosure closure только для selected consumer paths; permission/audit owners остаются владельцами фактов и правил.  Parent native canonical leases: write:exact-path/{canonical_repo_path}; write:runtime-api-generated-family if changed; resource:browser/{profile} if executed. Bind exact paths and overlap at P0; unresolved paths are not presumed disjoint before E02 rebind.

**Входы.** Complete selected path census, paired denied/absent records и действующие audience/permission outputs.

**Выход и consumer.** Evidence показывает indistinguishability для каждой фактической public path и разрешённый результат authorized reader.

**Что можно готовить независимо.** Готовить path census/canary по interfaces; неизвестный selected path не считать закрытым.

**Где результат соединяется с другими.** Parent join с auth-projection проверяет одновременно честную аутентификацию и ограниченный disclosure; Q06 действует по source selection.

**Positive.** Unauthorized client не отличает denied от absent; authorized reader видит корректное состояние.

**Distinguishing negative.** Generic body 404 с утечкой в headers/ids/counts/index/errors/cache раскрывает существование.

**Matched removal.** Убрать gate одного пути, оставив labels: matched canary обнаруживает leak.

**Граница контекста.** Полный selected emitter denominator обязателен; sampled path не доказывает отсутствие утечки.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source identity/commit and source-bound acceptance record used when rebinding this card; original parent dispatch/stage remains authoritative.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [UI-01.auth-projection](../../cards/UI-01/auth-projection.md) | Consume only for the exact composition described here: Parent join с auth-projection проверяет одновременно честную аутентификацию и ограниченный disclosure; Q06 действует по source selection. This link is not an unconditional all-of or preparation gate. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `UI-01`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — tasks.json#UI-01.task.r19_extension.question_slices[1] (R18-D12-Q06) value-matches question_ids[1]. Current coverage routes both selectors here as binding, while S12#R18-D12-Q06 assigns UI-01 as primary writer of the commissioned path census and matched disclosure closure; denied-absent owns that selected emitter/cache gate, so make its work executable. The exact selected path set is commissioned at P0, not a universal transport list.
  `task.r19_extension.question_slices[1]` (`R18-D12-Q06`); `task.r19_extension.question_ids[1]` (`R18-D12-Q06`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
