# CAP-02.single-response-root — Capture and resolve one exact bounded representation

Группа: [G01 — Поиск, получение и точная фиксация источников](../../groups/G01.md). Родитель: [CAP-02](../../parents/CAP-02.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** A complete retained response has one immutable root; a later reader returns the same verified bytes or unavailable.

**Предпочтительное решение.** Use RawHTTPResponseObserver through execute_live_catalog_acquisition to persist one bounded immutable body-plus-request/response witness only when the exact sink is allowed, then return ArtifactManifest/ArtifactRef to fresh readers. A 304 reuses only the matching readable body/Vary/profile/source root; otherwise unavailable. Anchors: fabric/connectors/sources/http_base.py; runtime/quality/acquisition_executor.py:execute_live_catalog_acquisition; core/artifacts/manifest.py:ArtifactManifest/ArtifactRef.

**Граница владельца.** Selected connector/runtime producer plus ArtifactManifest/FileSystemCAS; no backend-parity claim. Parent native lease family: `write:capture-protocol`, `resource:source/{source_profile}/fetch`. Exact post-E02 paths/overlap are unresolved; do not infer sibling disjointness or create a child lease. Root binds the actual path/lease before writes; cards sharing a native family serialize there.

**Входы.** Bounded response, exact request/profile/Vary/version, size limits, current LIF-05 permission for each sink.

**Выход и consumer.** Persisted body/root receipt and fresh exact reader result; query-only yields only its permitted output receipt.

**Что можно готовить независимо.** Reuse the selected capture connector and root reader after accepted-source rebind.

**Где результат соединяется с другими.** Per-hop transport proof precedes capture; CAP-03/LIF-01 and LIF-05 govern later use/materialization.

**Positive.** Allowed response resolves on second use without refetch and verifies exact content/profile.

**Distinguishing negative.** 304 without readable prior body, partial/oversize response, changed validator, or Vary mismatch stays unavailable/partial.

**Matched removal.** Remove body-to-root binding while retaining status/hash markers; fresh reader cannot establish the input.

**Граница контекста.** The preferred solution combines four independently reviewable contexts: per-hop network policy, retained representation and reader, conditional continuation/fencing, and a selected second-source adapter. R19 adds exact-content binding; it does not make these transport/protocol properties one mechanism. This is one bounded property view; parent source pins, stage/dispatch, conditional acceptance and mandatory companions remain inherited.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted source/path owner is consumed where selected; no blanket barrier.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-01.candidate-resolution](../../cards/CAP-01/candidate-resolution.md) | `direct:owner_readiness; acceptance:composition`: Exact persisted source/profile/selector receipt from candidate-resolution; query-disclosure authorization additionally applies only when the selected route actually emits a query. A selected CNT-02 profile/version is bound upstream through CAP-01; it is not a blanket extra CAP-02 dependency.<br>Source: `task.depends_on[1]`; `task.acceptance_dependencies[0]`.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Supplier [LIF-05](../../parents/LIF-05.md) | `conditional_acceptance_requirements:composition`: Only when the selected profile materializes body/temp/log/cache or another covered sink: consume the exact resolved source/profile/purpose/audience/sink and current-generation decision immediately before that write; persist a durable capture receipt only after an allowed complete write. No-fetch discovery and contract probes remain preparable; query-only retains only permitted output/receipt.<br>Source: `task.conditional_acceptance_requirements[1]`.<br>Условия: Selected CAP-02 profile performs body, temporary, log, cache or other staged/durable materialization |
| Composition output (не start gate) [CAP-02.transport-boundary](../../cards/CAP-02/transport-boundary.md) | Consume only for the exact composition described here: Per-hop transport proof precedes capture; CAP-03/LIF-01 and LIF-05 govern later use/materialization. This link is not an unconditional all-of or preparation gate. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `CAP-02`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Persist one permitted bounded body/root and fresh exact reader; HTTP validators apply only to that protocol, and every raw/temp/log/cache write needs LIF-05.
  `task.positive`; `solution.preferred_solution`; `solution.implementation_steps[1]`; `solution.free_grow.data_or_config_growth`; `solution.composition_contracts[4]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[4]`; `solution.inputs_to_resolve[2]`
- **join** — LIF-05 placement decision and CAP-01 query permission are separate; body write consumes only its sink decision.
  `solution.composition_contracts[3]`
- **binding** — 304 requires a matching readable root; the range/gap subclause is separately routed to continuation.
  `solution.implementation_steps[2]`
- **execute** — capture bounded response content and receipt for one response; use a source-native cut only when the source supplies it.
  `task.r19_extension.question_slices[0]` (`R18-D15-Q02`); `task.r19_extension.question_ids[0]` (`R18-D15-Q02`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
