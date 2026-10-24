# CAP-03.method-realization-reuse — Preserve method-specific realization and retry meaning

Группа: [G05 — Совместные расчёты, траектории и исследования](../../groups/G05.md). Родитель: [CAP-03](../../parents/CAP-03.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Reusing a realization is not a new independent observation; late/duplicate attempts cannot silently replace a referenced result.

**Предпочтительное решение.** Carry the admitted CatalogFetchBinding/CatalogFetchResolution and exact source root into the selected native method consumer; preserve intent/trial/attempt and method-version lineage so cache reuse avoids repeating the same immutable assessment without becoming an independent observation. Re-resolve current purpose, audience and source-right generation at reuse. Anchors: data_forge/domains/catalog/knowledge/types.py:CatalogFetchBinding/CatalogFetchResolution; core/artifacts/manifest.py:ArtifactRef.

**Граница владельца.** Existing GY/method trial, attempt, and lineage owner; CAP-03 resolves its exact input root only. Parent native lease family: `write:acquisition-action`, `write:acquisition-passport`. Exact post-E02 paths/overlap are unresolved; do not infer sibling disjointness or create a child lease. Root binds the actual path/lease before writes; cards sharing a native family serialize there.

**Входы.** Exact root, declared method guarantee, native intent/trial/attempt, backend/state and draw provenance when required.

**Выход и consumer.** Persisted accepted realization relation consumed by a fresh scientific/statistical consumer.

**Что можно готовить независимо.** Select the actual method and pin deterministic replay versus fresh-draw guarantee.

**Где результат соединяется с другими.** Join CAP-03's exact admitted root and native result owner; do not add an RNG schema or global ledger.

**Positive.** Qualified replay preserves the same realization; a true new replicate has a distinct basis and correct dependence accounting.

**Distinguishing negative.** Cache hit counted as a replicate, retry-until-favorable selection, or late result substitution is refused/limited.

**Matched removal.** Remove intent-to-realization binding while retaining seed/retry markers; downstream consumer detects double count/substitution.

**Граница контекста.** Root admission is distinct from current rights at sinks, method-specific replay identity, and binding verification to bytes actually read. The preferred-solutions card carries method/stream acceptance beyond the core library property; keep those native owners and compose them rather than giving CAP-03 a new universal mechanism. This is one bounded property view; parent source pins, stage/dispatch, conditional acceptance and mandatory companions remain inherited.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted source/path rebind where used; original stage gate stays inherited.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-02](../../parents/CAP-02.md) | `direct:owner_readiness`: Consume exact root/read; cost-basis consumes planner artifact.<br>Source: `task.depends_on[1]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-05](../../parents/LIF-05.md) | `direct:owner_readiness`: Consume shared rights/reservation at relevant effect; no local counter.<br>Source: `task.depends_on[3]`.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [CAP-03.root-admission](../../cards/CAP-03/root-admission.md) | Consume only for the exact composition described here: Join CAP-03's exact admitted root and native result owner; do not add an RNG schema or global ledger. This link is not an unconditional all-of or preparation gate. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `CAP-03`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Preserve native method guarantee and intent/trial/attempt lineage; cache reuse is not an independent observation.
  `task.acceptance_steps[5]`; `task.acceptance_steps[6]`; `solution.composition_contracts[5]`; `solution.composition_contracts[6]`; `solution.acceptance_discriminators[4]`; `solution.acceptance_discriminators[5]`; `solution.acceptance_discriminators[6]`
- **binding** — Method/reuse quality references constrain exact realization relation and replication accounting.
  `task.r17_extension.quality_cases[1]`; `task.r17_extension.quality_cases[2]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
