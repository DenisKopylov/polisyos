# CAP-03.root-admission — Admit and promote an exact root once

Группа: [G06 — Допустимость, полномочия и квалифицированные решения](../../groups/G06.md). Родитель: [CAP-03](../../parents/CAP-03.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Only resolved content plus verifier-provenance and current use evidence can create a reusable library receipt.

**Предпочтительное решение.** Connect the CAP-02 persisted root to existing build_admission_passport/admit_acquisition_with_semantic_epoch/revalidate_admission_passport, then make CanonicalAcquisitionAuthority resolve the exact ArtifactRef with current admission trace. Bind content, source/profile/schema, purpose, audience, verifier provenance and time; a hash or source contract alone is not admission. Anchors: runtime/quality/acquisition_executor.py; data_forge/domains/catalog/knowledge/acquisition_authority.py; core/artifacts/manifest.py.

**Граница владельца.** CAP-03 acquisition/library consumer, native passport, LIF-01 relation/use owner. Parent native lease family: `write:acquisition-action`, `write:acquisition-passport`. Exact post-E02 paths/overlap are unresolved; do not infer sibling disjointness or create a child lease. Root binds the actual path/lease before writes; cards sharing a native family serialize there.

**Входы.** CAP-02 root/receipt, source/use evidence, purpose/audience, tenant, profile/schema and rule version.

**Выход и consumer.** Persisted append-only admission receipt and ArtifactRef resolution with current trace.

**Что можно готовить независимо.** CAP-02 root and actual source grant/verifier must exist.

**Где результат соединяется с другими.** Join LIF-01 claim/use admission and LIF-05 materialization rights before promotion.

**Positive.** Admitted root promotes once and a fresh allowed use resolves the same bytes under a new purpose trace.

**Distinguishing negative.** Missing/revoked grant, substituted root, stale verifier, wrong purpose/audience, or changed generation refuses.

**Matched removal.** Remove content resolution/verifier provenance but keep admitted/hash labels; promotion and reader fail.

**Граница контекста.** Root admission is distinct from current rights at sinks, method-specific replay identity, and binding verification to bytes actually read. The preferred-solutions card carries method/stream acceptance beyond the core library property; keep those native owners and compose them rather than giving CAP-03 a new universal mechanism. This is one bounded property view; parent source pins, stage/dispatch, conditional acceptance and mandatory companions remain inherited.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted source/path rebind where used; original stage gate stays inherited.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-02](../../parents/CAP-02.md) | `direct:owner_readiness`: Consume exact root/read; cost-basis consumes planner artifact.<br>Source: `task.depends_on[1]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-01](../../parents/LIF-01.md) | `direct:owner_readiness`: Consume source/use relation at admission and selected use.<br>Source: `task.depends_on[2]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-05](../../parents/LIF-05.md) | `direct:owner_readiness`: Consume shared rights/reservation at relevant effect; no local counter.<br>Source: `task.depends_on[3]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `CAP-03`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Bind exact root/content/source relation, verifier provenance, source generation/use trace; D03-Q02 source independence and D09-Q05 set completeness stay source evidence.
  `task.migration`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[4]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[2]`; `solution.inputs_to_resolve[0]`
- **join** — Reuse may avoid repeating immutable assessment, while fresh purpose/right/generation is still resolved; method realization is separate.
  `task.acceptance_steps[4]`
- **binding** — Bind audience to admitted artifact; actual sink gate remains fresh-sink-rights.
  `task.surface_delivery.audiences`
- **execute** — this owns exact content-root admission and binds only source-supported protocol/cohort lineage for CNT-08 to consume; CAP-03 supplies the roots and does not decide statistical independence.
  `task.r19_extension.question_slices[0]` (`R18-D03-Q02`); `task.r19_extension.question_ids[0]` (`R18-D03-Q02`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
