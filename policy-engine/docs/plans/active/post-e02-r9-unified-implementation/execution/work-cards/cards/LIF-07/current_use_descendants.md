# LIF-07.current_use_descendants — Проверить current use и descendants

Группа: [G07 — Долгая custody: актуальность, права и переиздание](../../groups/G07.md). Родитель: [LIF-07](../../parents/LIF-07.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Derived use checks LIF01 use, LIF02 source cut, LIF05 rights and actual descendant path.

**Предпочтительное решение.** LIF07 supplies influence; other owners keep currentness/rights/use.

**Граница владельца.** LIF07 owns lineage/influence only; LIF01 semantic use, LIF02 source currentness, LIF05 rights and selected readers keep their canonical owners.

**Входы.** Persisted LIF07 role-qualified lineage/cache identity; exact per-use LIF01 decision; LIF02 source cut; LIF05 current rights; actual descendant path and selected reader.

**Выход и consumer.** Fresh per-use descendant eligibility/result at the selected claim/cache reader; changed influence, currentness or rights limits only affected use.

**Что можно готовить независимо.** Prepare the reader against agreed owner interfaces; unknown required lineage, use, source or rights inputs remain bounded. Actual outputs join at the consumer.

**Где результат соединяется с другими.** At the fresh claim/cache reader, compose exact LIF07 influence with LIF01 use, LIF02 current source cut and LIF05 rights; grant-only rotation changes use without needless recompute, while revocation blocks.

**Positive.** Grant-only rotation changes admission without needless recompute; revocation blocks affected use.

**Distinguishing negative.** A cache bypasses current rights/source use or an affected descendant is omitted while its reader remains green.

**Matched removal.** Remove live-use/descendant validation but retain lineage and grant markers; the fresh reader must fail or limit the affected use.

**Граница контекста.** LIF07 does not write claim status, currentness, rights or archive. Exact reader paths and descendant closure are rebound after E02.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Root stage.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-01](../../parents/LIF-01.md) | `direct:owner_readiness`: Consume use semantics.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-02](../../parents/LIF-02.md) | `direct:owner_readiness`: Consume current/as-of source cut.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-05](../../parents/LIF-05.md) | `direct:owner_readiness`: Consume rights/placement; graph grants nothing.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [LIF-07.computational_influence](../../cards/LIF-07/computational_influence.md) | For the selected derived/cache descendant only: role-qualified influence supplies the path, while LIF-01 use, LIF-02 currentness and LIF-05 rights decide the actual use. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `LIF-07`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Remove live rights check.
  `task.removal[1]`
- **execute** — R18 exact current-use.
  `task.r19_extension.question_slices[7]`
- **execute** — R18 withdrawal/hold reaches descendants; LIF05 rights.
  `task.r19_extension.question_slices[10]`; `task.r19_extension.question_slices[11]`
- **binding** — IDs mirror U074/U077/U078 current-use slices.
  `task.r19_extension.question_ids[7]`; `task.r19_extension.question_ids[10]`; `task.r19_extension.question_ids[11]`
- **execute** — Cache not permission.
  `solution.composition_contracts[1]`
- **execute** — Historical/current cut, LIF01 semantics, LIF05 retention.
  `solution.composition_contracts[5]`; `solution.composition_contracts[6]`
- **execute** — Lagging source feed and grant/redaction behavior.
  `solution.acceptance_discriminators[4]`; `solution.acceptance_discriminators[5]`
- **binding** — Consume rights and claim composition.
  `solution.inputs_to_resolve[2]`; `solution.inputs_to_resolve[3]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
