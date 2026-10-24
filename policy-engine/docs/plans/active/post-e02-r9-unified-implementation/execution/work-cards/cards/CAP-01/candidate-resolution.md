# CAP-01.candidate-resolution — Resolve candidate to exact source/profile

Группа: [G01 — Поиск, получение и точная фиксация источников](../../groups/G01.md). Родитель: [CAP-01](../../parents/CAP-01.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Ambiguity, stale identity, and candidate ranking never become admitted source authority.

**Предпочтительное решение.** After inherited A0 selects the caller, route candidate search through the existing SemanticDatasetCatalog.refresh/search/resolve and SourceContract/connector registry; persist candidate/ambiguous/unavailable against exact contract revision, profile, selector and requested time, and forward only the selected profile to its registered producer. Anchors: fabric/catalog/discovery.py:SemanticDatasetCatalog; fabric/connectors/contracts/source_contract.py:SourceContract; runtime/quality/acquisition_planner.py:plan_evidence_acquisition.

**Граница владельца.** Existing SemanticDatasetCatalog, SourceContract, and located acquisition caller; no new registry. Parent native lease family: `write:acquisition-action`, `write:source-catalog`. Exact post-E02 paths/overlap are unresolved; do not infer sibling disjointness or create a child lease. Root binds the actual path/lease before writes; cards sharing a native family serialize there.

**Входы.** A0 source denominator, selector, profile, requested scope/time.

**Выход и consumer.** Persisted candidate/ambiguous/unavailable receipt and exact registered-producer handoff.

**Что можно готовить независимо.** A0 selects the actual caller and binds existing catalog/connector owners.

**Где результат соединяется с другими.** Join query-egress approval only when the selected discovery route sends a query; join normal source-use admission before use.

**Positive.** Preseed and runtime paths for one source resolve to the same receipt and fresh acquisition consumer.

**Distinguishing negative.** Ambiguous selector, stale contract, fake ID, or injected URL causes no source fetch/admission.

**Matched removal.** Remove source/profile binding while keeping status fields; resolver and route consumer refuse.

**Граница контекста.** Three distinct predicates share a route but need separate contexts: candidate resolution, pre-egress query authority, and claim-scoped coverage/no-hit. The R19 coverage questions are a measurement artifact, not extra prose around discovery. This is one bounded property view; parent source pins, stage/dispatch, conditional acceptance and mandatory companions remain inherited.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source/caller and source denominator are consumed for rebind; preparation may precede and original P0 remains stage gate.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [CAP-01.query-disclosure](../../cards/CAP-01/query-disclosure.md) | Only when this candidate actually requires sending a query to a provider; local candidate construction does not wait. |
| Composition output (не start gate) [CAP-01.bounded-coverage](../../cards/CAP-01/bounded-coverage.md) | Only when the selected output makes a bounded absence/no-hit or search-coverage claim; candidate listing alone does not require that outcome. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `CAP-01`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Bind exact source/profile and existing catalog/connector, keep candidate separate from source-use, preserve typed extension/resource limits and legacy re-resolution; U052 consumes query output in the positive path.
  `task.migration`; `solution.preferred_solution`; `solution.implementation_steps[1]`; `solution.implementation_steps[3]`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.composition_contracts[1]`; `solution.composition_contracts[2]`; `solution.acceptance_discriminators[0]`; `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[2]`
- **execute** — bind the resolved exact source receipt; discovery is not a right, and stale mirrors/self-license fail admission.
  `task.r19_extension.question_slices[1]` (`R18-D09-Q01`); `task.r19_extension.question_ids[1]` (`R18-D09-Q01`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
