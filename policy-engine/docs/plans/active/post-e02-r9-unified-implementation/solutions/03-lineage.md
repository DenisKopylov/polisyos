# Ресурсы, lineage и композиция: предпочтительные решения

Статус: engineering recommendations; product execution UNRUN. Реализация только после E02 acceptance и полного affected-scope rebind. Исходные критерии не сокращаются; [общие решения](00-shared-decisions.md) предотвращают второго owner. [Нормативные уточнения](decision-clarifications.md) остаются предложениями.

<a id="LIF-06"></a>

## LIF-06 — Bound lifecycle work and reserve custody/control capacity

Исходная запись: [tasks.json](../tasks.json), `tasks[id=LIF-06]`. Review: [root-review](root-review.md#LIF-06).

### Предпочтительное решение

Extend the existing resource-enforcement owner(s) with owner-local multidimensional admission and a separately protected custody/control reserve. Let new correctly implemented resource profiles be discovered and executed through the typed owner contract and generic accounting path; do not require a central capability allowlist or hardcoded fallback. Keep capacity estimates advisory until measured against the accepted OPS process profile and a complete accounting denominator. No cross-process enforcement is claimed as already implemented. LIF-06 owns the single shared admission contract and minimal native mechanism; at scoped rebind it first extends the accepted E02 owner. If that owner lacks the necessary seam, root allocates its smallest native extension to this task. OPS-08 implements/qualifies selected host enforcement adapters against that contract. Missing internal code is engineering work, not an institutional blocker. The priority rule is bounded defer/refusal under pressure, with a measured reserve for terminal state persistence, cancellation/reconciliation, and recovery; a semaphore or expired lease is not physical resource control.


### Что переиспользовать

- `policy-engine/src/polisyos/core/artifacts/store.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `FileSystemCAS.open_member`. Verified at the planning source pin: streams a selected CAS member with bounded memory and hashes the complete member before releasing its read lease. This does not establish sublinear I/O, governed spill, or a whole-process memory cap.
- `policy-engine/src/polisyos/runtime/http/services/control_plane_store.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `_job_transaction`. Verified at the planning source pin: canonical SQL transaction/admission seam for job state; it is not evidence of resource isolation or a cross-process reservation pool.
- `policy-engine/src/polisyos/runtime/quality/acquisition_executor.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `AdmissionPassport; execute_live_catalog_acquisition`. Existing acquisition route seam; rebind its accepted status and callers before deciding whether it can carry a resource permit. No physical quota semantics are inferred from the passport name.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.


### Последовательность реализации

1. At W0, inventory actual processes, native and IPC allocations, concurrent work, storage generations, spill/checkpoint paths, and current per-owner enforcement. For each resource, label the admission predicate `recomputed`, `independently_reconciled`, `institutionally_supplied`, `consumer_asserted`, or `not_established`; only the first two support a hard local bound.
2. At W0, identify the canonical resource-enforcement owner and its existing descriptor/registry seam. If the seam is absent, root allocates the smallest typed extension to LIF-06 and OPS-08 consumes its agreed interface; do not assume a registry or add a central capability list. Through the owner contract, interpret versioned dimension descriptors generically (dimension identity, unit, accounting source, enforcement binding and scope), so a correctly implemented resource profile is discovered and executed without a central per-capability branch. Dimension identifiers and schema/status vocabularies are data/types, not capability allowlists. An unmetered or unenforced dimension cannot support hard admission.
3. Represent each admitted operation by a versioned resource vector for resident/native/IPC memory, disk and spill, checkpoint and overlapping generations, CPU, I/O, network/provider allowance, queue slots, and control metadata. Bind the vector to the actual owner, operation class, process/cgroup or provider principal, expiry, and durable attempt identity.
4. Reserve capacity before work at one canonical owner boundary. Size the terminal reserve from the measured worst supported fan-in and recovery overlap. Maintain a non-overcommitted custody/control allowance; use weighted or dominant-share fairness only among otherwise eligible bulk work and only under an explicitly selected policy.
5. For nested work, preserve charges for every still-live parent allocation, shared buffer, child and overlapping generation. Transfer changes accounting ownership, never physical consumption; count shared allocation once and IPC/copies separately. Reserve a feasible combined peak, execute within an already reserved envelope, or checkpoint/park and verify the relevant capacity actually freed before admitting the child. An idle parent may release a CPU slot while retaining its RAM/disk charges. If neither fits, durably defer/refuse without synchronously waiting while holding the resource the child needs.
6. On saturation, persist the existing job/progress disposition with a bounded reason and due time; avoid unbounded retries. Exercise simultaneous terminal transitions, nested 60/100-plus-50/100-style deadlock shape, live worker after lease expiry, old/new root overlap, OOM/ENOSPC, shared-account 429, and terminal-lane behavior through the actual consumer. Thresholds remain unset until measured.
7. Use only resource dimensions materially consumed by the selected profile. Protect control/custody capacity through actual process-group/bulk limits and scratch quota that leave measured headroom; distinguish graceful shedding from OOM containment. A reservation ledger alone cannot protect memory.


### Рассмотренные альтернативы

- **Keep only task estimates, request counts, or per-process semaphores.** — SRE documents heterogeneous and drifting request cost; a semaphore does not account native allocations, disk generations, provider spend, or child-process lifetime. It can remain a pre-measurement advisory state, not a cap.
- **Create a new global PolicyOS scheduler or universal DRF service.** — The lifecycle plan explicitly rejects a global scheduler. DRF is a published fairness mechanism under a particular model, but it does not choose authority priorities or protect terminal duties; use it only if an existing owner has a measured fairness need and an authorized policy.
- **Treat cgroup or analytical-engine configuration as the whole bound.** — Kernel controls depend on deployment support and can throttle, overcommit, or invoke OOM behavior; DuckDB's memory limit covers its buffer manager and spill can exhaust disk. These are possible enforcement layers, not substitutes for complete owner accounting and a custody reserve.


### Free-grow и ресурсы

- **data or config growth:** Add versioned resource vectors, operation profiles, and per-owner limits within the accepted resource owner; generic owner interpretation discovers and executes correctly implemented profiles without a central capability allowlist or hardcoded fallback.
- **extension boundary:** LIF-06 defines/extends the one canonical accepted runtime admission owner and its material resource dimensions; OPS-08 implements host/process enforcement. Missing native admission is assigned implementation, not a reason to wait for OPS-08 to invent another scheduler. Unsupported dimensions remain explicit profile limitations.
- **resource behavior:** Per-operation accounting grows with active operations and declared resource dimensions. Bounded queues and finite reservations apply generically; dimensions without a bound meter/enforcement witness cannot be hard-admitted. No numerical capacity is claimed before a measured wave.


### Миграция и восстановление

Inventory current callers and live allocations first. Keep existing estimates advisory during a measured transition; enable hard admission only for dimensions whose enforcement and denominator were witnessed. On rollback, stop new bulk admission, preserve custody/control and due-work capacity, and reconcile live processes and reservations before release. Preserve outcome/history and rights-limited bytes; never treat lease expiry as worker termination or restore older authority over a later revocation.


### Композиция и owners

- An estimate or declared vector is not the enforced predicate; bind it to measured host/process state, actual storage quota, and actual provider account scope.
- Terminal transitions, recovery and currentness duties retain physically protected capacity under bulk saturation within the tested reserve; if the shared host cannot protect them, report the bounded limitation and deny new bulk work.
- Provider timeout/retry on a shared billable principal consumes or holds the same reconciled allowance; a rotated credential or second source does not imply a separate quota.
- Spill records carry purpose, source artifact, retention/right scope and owning storage reference; ENOSPC yields an explicit partial/unavailable/refused outcome rather than an empty result.
- Measurement and production admission are separate stages under this same owner. OPS-08 may qualify a new class inside an already enforced, explicitly permitted finite measurement envelope; unmeasured expected cost is never an admission guarantee and no protected claim duty is accepted from that run.
- Allocation identity/lifetime is authoritative for capacity accounting, not job status. At attempt completion transfer surviving shared/cache/IPC charges to their existing native owner without multiplying or erasing them; OPS-08 reconciles actual enforced headroom. A duplicate release/transfer is idempotent and cannot create capacity.
- Bind a versioned profile-specific queue/progress policy at LIF-04’s existing due-intent selector: eligibility and aggregate reservations come from LIF-06, measured headroom/age targets from OPS-08. Specify priority, fairness/aging or an explicitly limited best-effort class, queue admission/expiry and a bounded terminal/review disposition. Retry must preserve original admission age. No universal numeric deadline or mandatory DRF is imposed. An unbounded service/progress promise is forbidden; adverse load yields the declared defer/cancel/refusal/review result. Custody/revocation/reconciliation duties cannot disappear on queue TTL: retain their durable obligation and expose overdue/coverage loss through the existing owner.
- Accounting may use a conservative enforced process/pool envelope with verified shared-allocation ownership and reconciliation; no per-Python-object tracing or universal allocation ledger is required. Uncertain lifetime retains the relevant conservative charge/headroom bound rather than inventing free capacity. Partition or aggregate only when the physical bound remains valid.
- Treat review-required as an unresolved service/coverage state, not a terminal service success. The existing duty owner binds the actual review owner, triggering evidence, next wakeup/escalation or owner-permitted cutoff/transfer and original admission/due age; a callback, repeated review marker or fresh retry ID alone cannot discharge the duty or reset its clock. A class promising service/aging needs actual service progress within its commissioned bound; a class declaring best-effort may expire/refuse without that guarantee, with a visible outcome. For custody work, missed service changes the affected claim/coverage promptly through LIF-02 even if bulk compute or review is unavailable. A review result can authorize a new bounded plan but cannot rewrite the missed interval. This qualifies the selected policy, not a universal SLA or a new human-approval gate.
- LIF-04 persists the stable duty identity, admission-policy version and committed service class/terms, original age and durable due/next-trigger generation with its existing control-store intent. Normal policy updates govern new admissions. An active-duty change is an owner-qualified recorded successor/cutoff/transfer that preserves the original promise, missed intervals and affected coverage; automatic native transitions remain allowed. Current rights, safety restrictions and enforceable aggregate caps apply immediately even when they prevent the older service promise: expose the actual lapse/limitation, never freeze unsafe permission. A wakeup is a hint: restart/reconciliation recovers due duties from durable state and fences duplicate/old generations. Use persisted effective-time semantics plus elapsed-duration clock handling; process-local monotonic values are not durable deadlines. LIF-06 supplies current eligibility, OPS-08 the measured envelope; neither rewrites the admitted commitment or creates a second scheduler. Uncertain clock/order evidence limits the promised timing guarantee explicitly.


### Acceptance и различающие проверки

- Positive: the selected accepted workload completes within measured caps while all supported simultaneous terminal transitions and recovery retain their measured reserve.
- Extensibility: add a valid, owner-conforming resource profile with a new declared dimension; the generic path discovers and executes it without a central per-capability branch. A declared but unenforced dimension cannot pass hard admission.
- Adversarial: nested parent/child reservations, stalled native worker, old/new roots during recovery, spill failure, provider 429 and shared-account retry produce bounded defer/refusal without deadlock, false release, or lost custody work.
- Removal: remove terminal reserve but leave estimate constants; remove child transfer/release but retain the semaphore; remove physical cgroup/storage/provider enforcement but retain declared byte fields. Each real property removal must fail the behavioral gate.
- Surface: the existing job/progress consumer exposes defer, quota, partial, unavailable or refused with the bounded reason and retry time. No separate scheduler dashboard is introduced.
- Saturate native bulk allocation and spill while terminal writes/recovery run in the actual protected process groups; persisted outcomes and control reserve survive within the declared profile, or that hard-bound claim remains unavailable.
- A new profile using already supported resource semantics requires no central branch. A genuinely new physical resource dimension needs a native enforcement adapter/conformance before it can claim a hard cap; generic discovery alone is not enforcement.
- A parked parent retaining 60/100 RAM cannot admit a 50/100 child merely by yielding its CPU slot or moving a ledger entry. Actual release of sufficient memory permits progress; shared parent/child buffers count once, copies twice. Remove lifetime accounting but keep permit markers: the nested resource control must fail.
- Finish or cancel an attempt whose allocation remains shared by another reader/cache: its charge survives under one live allocation owner, while actual private releases can be reclaimed. Transfer/release replay cannot create capacity. Removing shared-lifetime accounting while preserving terminal markers causes a bounded overadmission probe to fail.
- Under sustained arrivals in one eligible class, an older competing job either receives its selected-policy service opportunity or reaches its declared bounded terminal/review disposition; it cannot silently defer forever. Retry preserves first-admission age, and a custody/revocation duty remains durable with a truthful overdue/limited surface. Remove aging/expiry/disposition behavior while preserving queue-age metrics: the selected progress-policy probe fails; do not claim successful execution when only expiry/refusal occurred.
- Replace real service by repeated review-required events and new retry IDs while preserving queue-age metrics: the declared service guarantee fails and the duty remains overdue/unresolved. A real review disposition either schedules an accountable continuation, makes an authorized cutoff/transfer or preserves explicit limited coverage with its next trigger; it is not counted as execution. Positive service-class work progresses under its stated load bound, while explicit best-effort refusal remains a different truthful result. Remove the overdue-to-claim reaction but retain review markers: the custody coverage probe fails.
- Admit a duty under service policy v1, switch new admissions to v2 best-effort, stop the worker across its due time, then restart with a lost/duplicate wakeup and clock movement. The old duty retains v1 or an explicit owner-qualified transition/lapse, a new duty uses v2, and current safety/cap restrictions still prevent unsafe dispatch. New retry IDs and late expired workers cannot downgrade, strand or reset the old duty. Remove admission-commitment persistence or durable trigger recovery while retaining age/current-version/wakeup markers: the downgrade/stranding probe fails.


### Входы и ответственность за их получение

- OPS accepted process/container profile, host accounting, and actual resource-control availability.
- Provider account principal, quota/rate semantics, billing receipt and shared-caller denominator; external limits remain institutionally supplied unless reconciled.
- Artifact storage owner’s spill path, rights, disk/quota enforcement, retention, root/GC overlap and cleanup behavior.
- An actual resource-enforcement owner if the present local transaction/admission seams do not cover all processes.


### Когда обоснованно отклониться

- If work spans processes not covered by one accepted resource owner, extend the one selected native owner to that process scope and qualify it with OPS-08; until demonstrated, refuse only work relying on the unproved aggregate cap, not unrelated preparation.
- If provider usage cannot be bounded or metered across all callers, report only the measured per-operation limit plus declared external-consumption uncertainty; do not claim a hard account-wide cap.
- If the host, backend, or spill destination changes after freeze, invalidate the resource measurement and reprice the bounded replay wave.

Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.


### Исследование и предел переноса

- [Handling Overload, Site Reliability Engineering](https://sre.google/sre-book/handling-overload/) — Request counts and static request attributes can be poor capacity proxies because work costs differ and change. The source recommends graceful degradation and transparent errors under overload, and describes isolating batch load from higher-priority traffic. **Граница:** A serving-system design discussion, not a PolicyOS resource contract or evidence that any local resource is currently measured or enforced.
- [Dominant Resource Fairness: Fair Allocation of Multiple Resource Types](https://www.usenix.org/conference/nsdi11/dominant-resource-fairness-fair-allocation-multiple-resource-types) — Dominant Resource Fairness generalizes max-min fairness to heterogeneous multi-resource demands and studies properties including strategy-proofness and envy-freeness under its model. **Граница:** Fair allocation is not a normative rule for custody duties, urgency, protected actions, or legal priority. The paper does not implement reservations, terminal fan-in, or PolicyOS process accounting.
- [Control Group v2, Linux Kernel Documentation](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html) — cgroup v2 provides hierarchical CPU, memory, and I/O controls and accounting. Its documentation distinguishes weights, protections, and limits; memory.high throttles under reclaim while memory.max can invoke the OOM killer and may be exceeded temporarily. **Граница:** Only applies where the host, kernel, filesystem, controller, and process placement support the relevant controls. It does not meter every network/provider spend or supply a product-level reserve protocol.
- [Memory Management in DuckDB](https://duckdb.org/docs/current/operations_manual/limits) — DuckDB's documented memory_limit only applies to its buffer manager, and its temporary-directory limit is configurable (the documented default is unlimited). This shows why an engine-specific memory setting is not a whole-process or disk cap. **Граница:** DuckDB documents limits for its own operators. It is not a governed PolicyOS spill destination or a universal bound on native/process memory.
- [Memory Management in DuckDB](https://duckdb.org/2024/07/09/memory-management) — DuckDB can stream and spill larger-than-memory intermediates to a temporary directory. If memory is exceeded and spilling is disabled, the temporary-directory limit is exceeded, or spilling is unavailable for a query, DuckDB reports an out-of-memory error and cancels the query. **Граница:** DuckDB documents behavior for its own operators. It does not establish a governed PolicyOS spill destination, retention/right scope, or whole-process memory bound.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="LIF-07"></a>

## LIF-07 — Bind derived outputs, caches and learning to exact influence

Исходная запись: [tasks.json](../tasks.json), `tasks[id=LIF-07]`. Review: [root-review](root-review.md#LIF-07).

### Предпочтительное решение

Extend the canonical ArtifactManifest/InputRef and existing ArtifactLineageGraph path so each derivative and cache use can bind its exact influence parents, then let current owner generations drive scoped invalidation and reassessment. Begin with conservative cache misses or full recomputation through the current owner; add incremental closure/invalidation only if a representative measured workload demonstrates a crossover that justifies its complexity. Cache identity and present admissibility are separate: a matching key is only a candidate reuse result, and the consumer must recheck current rights, audience, purpose, rules, and source/model generations. Missing or unresolved influence is a cache miss or a limited candidate, never proof of no effect or equivalence. Independence is checked only for a specific verification claim that depends on it; graph topology can contribute dependency facts but never proves independence. Confirmatory learning must enter the existing method-valid correction path; exploratory output remains lower authority. Preserve unresolved competing causal worlds and validated joint alternatives in the existing model/world owner rather than caching one alternative as if it were uniquely established.


### Что переиспользовать

- `policy-engine/src/polisyos/core/artifacts/manifest.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `InputRef; ArtifactRef; ArtifactManifest.inputs; input_ref_from_artifact_ref`. Verified at the planning source pin: manifests persist typed direct input references, roles, artifact identity, and selected manifest-profile hash; references also carry kind/media type. Current fields do not encode the full rights/audience/model/selection proof required by this row.
- `policy-engine/src/polisyos/ir/artifacts/lineage.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `ArtifactLineageGraph; build_artifact_lineage_graph; derived_from; invalidated_by`. Verified at the planning source pin: graph reconstructs direct derivation from manifest inputs and supports transitive upstream lookup plus task invalidation edges. Graph topology does not establish semantic adequacy, complete runtime selection influence, rights, or scientific independence.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.


### Последовательность реализации

1. After E02 rebind, inventory all derivative producers, cache-key builders, model/training producers, selection/frontier producers, and actual claim/evaluation consumers. Extend the existing artifact/lineage owner only where the accepted native contract is insufficient; do not create another lineage graph.
2. Record dependencies with distinct roles: exact computational/selection/model/semantic inputs, current-use predicates, and retention/disclosure constraints. Bind right/use generation, audience and purpose into the computational key only when they actually affect selection, redaction, computation or output meaning; retain the other roles in the per-use decision/fence. Persist selection trace and method provenance where learning is involved.
3. Derive reuse identity from the complete computational/semantic dependency closure, then independently resolve current use and LIF-05 retention eligibility at the actual consumer. An admission-only grant rotation may change allowed use without rerunning an unchanged lawful assessment. A changed selected dataset/redaction, model, predicate rule or other computational influence causes a cache miss/reassessment. Unknown role or incomplete closure cannot be treated as irrelevant.
4. Use coarse invalidation for unknown or lagging reverse-index influence, then bounded precise reassessment for known affected uses. Never turn no-hit, ANN recall unknown, byte equality, a cached certificate, or shared graph ancestry into equivalence or independence credit.
5. Bind the evaluated alternative set and joint-assessment generation where a derivative depends on competing causal worlds. Retain unresolved plurality and validated joint alternatives as typed owner output; a winning selection remains a decision-layer choice, not evidence that other worlds are false.
6. Route confirmatory outcome learning through the existing method owner’s correction/reassessment protocol; mark exploratory proposals as candidate. Persist each resulting artifact/event and prove a fresh consumer observes the downgraded/stale/reassessed state.


### Рассмотренные альтернативы

- **Use content hashes or existing lineage labels as the complete cache key.** — Equal bytes do not imply equal audience, purpose, applicable right, rule, resolved model, or training/selection basis; the required cross-audience cache negative would still hit.
- **Adopt a generic build cache or duplicate a second semantic dependency graph.** — Bazel/DVC show the value of exact declared inputs, but do not model rights or PolicyOS authority. The existing manifest and graph are canonical owners; any additional semantics belong there or in a linked native owner record, not in a parallel graph/cache authority. No new incremental engine is mandatory: measure a representative workload and demonstrate a crossover before paying for more complex incremental behavior.
- **Invalidate all descendants forever after any change.** — This is safe but can destroy usable candidate work and create unbounded operational fanout. Prefer conservative scoped stale/limited state and bounded reassessment; shrink the closure only with independently reconciled exact dependencies.


### Free-grow и ресурсы

- **data or config growth:** Add versioned model, rule, source, use, audience, and selection-generation references through existing owners; supported model/outcome classes can be added as typed data/config while retaining full producer provenance.
- **extension boundary:** A genuinely new learner, selection method, semantic predicate, or influence source needs the owning producer and consuming method to define its provenance and correction behavior. Unknown/unregistered event types or hidden inputs cannot be treated as inert.
- **resource behavior:** Dependency-set and reverse-closure work grows with declared influence and affected consumers; selection frontiers may increase invalidation fanout. Persist bounded queues and use coarse invalidation under pressure. Unresolved selection causes a cache miss or narrower claim, not suppressed invalidation.


### Миграция и восстановление

Backfill only parent, model, rule, right, audience and selection edges that resolve from retained authoritative artifacts. Legacy derivatives with incomplete edges become cache misses and candidate/unknown for current use. Retain older derivatives as historical evidence, mark their current use stale or contested, and rebuild only under current rights and exact generations. Rollback never repoints authority to an older generation or converts missing lineage into equivalence.


### Композиция и owners

- Artifact ID, selected manifest profile, input role, output identity, semantic predicate, producer/method version, and rule generation remain bound across persisted artifact and consumer.
- Cache identity is not a permission token; current use-specific rights/audience checks occur on every admitted reuse path.
- A confirmed correction invalidates only independently reconciled affected uses; an incomplete influence set uses a declared broader limitation or candidate status. Any independence analysis is scoped to a verification claim that explicitly depends on it, not required for every derivative or rebuild.
- Exploratory model proposals cannot update confirmatory claim standing without method-valid outcome/exposure provenance and correction/reassessment.
- Uncertain competing causal worlds, validated joint alternatives, and inference plurality remain explicit in their existing owner records; a cache key or selected frontier cannot silently erase them.
- Historical capture identity is not source-currentness. For a claim presented as current, bind actual CAP/LIF-02 revision/cut/high-water and validity; same-ID correction with a lagging feed makes currentness limited/stale. Explicitly historical/as-of use may retain the old derivative. Bind actual material influence roles, not every possible metadata field on every artifact.
- LIF-01 owns assertion/assessment/use meanings; LIF-07 supplies role-qualified influence, cache identity and invalidation. A retained analytic result can remain mathematically unchanged while its current use is denied. Retain neither result nor its identifiers beyond actual LIF-05 permission; a cache hit cannot bypass deletion or authorize publication.
- Qualify reuse against the native method guarantee and invocation intent. Returning the same retained realization/assessment is distinct from requesting a new replicate, stochastic evaluation or provider response. Reuse identity binds relevant executable/backend, initial state and random-stream/draw provenance where the method needs them; one integer seed is not a universal replay proof. Cache-off comparison fixes the same admissible basis, use cut and declared guarantee: exact sample-path equality only for a qualified deterministic replay profile; otherwise use the preselected numerical/statistical criterion with its full uncertainty and failure denominator. Distributional agreement cannot substitute one artifact for another exact referenced realization, and replaying one result never creates another independent observation. A fresh-draw request cannot be satisfied by the old draw. This extends existing method/lineage contracts, not a central whitelist of stochastic methods or a mandatory RNG schema for every verifier.
- Recover a stochastic invocation through its existing native intent/trial/attempt owner: bind the selected realization or method-qualified realization set to that intent and its accepted result. Late, duplicate or changed replies under the same intent remain attempt outputs, not additional independent evidence; preserve their actual outcomes/cost and dependence. A safe pure retry may reconstruct a qualified frozen stream/state or use a method-qualified replacement realization with an explicit successor basis and full failure/selection denominator. Do not silently replace an already referenced realization, use retry-until-favourable selection, or force every pure local retry into external-effect reconciliation. Only an explicit new replicate changes the replicate basis; independence still needs the method criterion. No universal one-draw-per-job restriction, RNG schema, new intent ledger or global result lock; see R16 C3/C5 R24 companion.


### Acceptance и различающие проверки

- Positive: identical exact parents, profile, rule/model generation, purpose and audience can reuse a verified derivative; a fresh selected reader resolves the same persisted lineage.
- Adversarial: same bytes under a different audience/purpose; changed model or alias-resolved selection frontier; missing training parent; unknown ANN/event type; withdrawn semantic generation; cold derivative unavailable; no-hit versus equivalence.
- Removal: remove exact selection/model/right parent binding while retaining lineage labels; remove the live rights check while retaining cache-key fields; remove confirmatory correction while retaining a learning label. The consumer must miss/refuse/downgrade in each case.
- For a verification claim that explicitly relies on independence, test its exact method/source-dependence analysis against shared cohorts, methods, authors, training inputs and derivatives. A lineage graph may inform this claim-scoped test but cannot prove independence by topology. Claims that do not require independence do not gain a mandatory extra gate.
- Revise or withdraw the source under the same locator while delaying its event feed: a historically correct cached root must not produce an unjustified current claim.
- Rotate only the grant generation for unchanged lawfully retained inputs/method: the analytic verifier call count stays flat while fresh admission consumes the new generation. Revoke permission and the sink blocks. Change permission-driven redaction or selected rows and recomputation is required. Remove the live-use check or the computational role binding while retaining lineage markers: the corresponding denied-use or changed-input probe fails; cache-off preserves the declared guarantee for the qualified basis/use cut; exact realization replay and a fresh draw remain distinct.
- Under a qualified frozen-realization profile, cache-on/off reaches the same referenced computation and permitted use; under a fresh-replicate profile it produces a distinct invocation with the method-required draw/dependence accounting and is compared by the selected guarantee, not scalar equality. A reused realization does not increment independent evidence/sample count. Remove invocation/draw identity while keeping seed and cache markers: the repeated-draw-as-new-evidence control fails. Do not weaken an exact historical-artifact claim to distributional similarity.
- For the selected stochastic method, interrupt between evaluation and result persistence, retry the same native intent and deliver the old completion late. The fresh trial/reuse consumer resolves one accepted realization set for that intent, counts no extra independent replicate, and preserves failed/unknown attempts and selection effects. Qualified pure replay/replacement progresses without a generic human gate; an explicit new replicate has a distinct basis and declared dependence. Remove intent-to-realization/result binding but retain seed, retry and artifact markers: double counting or silent substitution must fail the discriminator.


### Входы и ответственность за их получение

- Existing CAS manifest and lineage owners, including canonical artifact identity/profile resolution.
- Resolved model, training-input, selection/frontier, and confirmatory-method producers and their rule/version provenance.
- Rights owner’s purpose-, audience-, derivative- and cache-specific use decisions and rebuild eligibility.
- Claim/evaluation consumer’s exact affected-use and admissibility composition.


### Когда обоснованно отклониться

- If a model or selector reads an input outside the bound producer interface, mark influence incomplete and force miss/limited candidate until it is enrolled. Preserve multiple unresolved model/world alternatives and their validated joint outputs; do not silently reduce plurality to one model generation.
- If reverse lineage is incomplete or stale, broaden invalidation to the reconciled owner scope; do not claim exact minimal invalidation.
- If the downstream method cannot supply valid correction semantics, keep the learned result exploratory and do not promote it through this task.

Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.


### Исследование и предел переноса

- [Skyframe, Bazel Reference](https://bazel.googlesource.com/bazel/+/3b9ed6e9d3570a0c67e0d59e65b3785bbc1fad99/site/en/reference/skyframe.md) — Incremental recomputation depends on functions declaring all inputs through the dependency graph; Bazel describes reverse-transitive invalidation and change pruning after recomputation. **Граница:** Build-system dependencies do not encode PolicyOS rights, semantic validity, audiences, authority, or scientific independence. Unregistered reads defeat the incremental correctness model.
- [dvc.yaml Files and dvc.lock, DVC Documentation](https://doc.dvc.org/user-guide/project-structure/dvcyaml-files) — DVC lockfiles record stage definitions, dependencies, parameters, and output hashes so the pipeline can detect changed stages and decide which stages to reproduce. **Граница:** A reproducible pipeline cache does not decide current legal use or whether a derivative is admissible for a particular audience and purpose.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="LIF-08"></a>

## LIF-08 — Compose a second source and its compatibility lifecycle

Исходная запись: [tasks.json](../tasks.json), `tasks[id=LIF-08]`. Review: [root-review](root-review.md#LIF-08).

### Предпочтительное решение

Add one materially distinct source through CAP’s existing capture and receipt path, then admit its source/profile/parser generation through the existing SourceContract and catalog registry seams. Correctly implemented supported sources must be discovered and executed through generic registry/contract interpretation, without central per-source capability branches. Compose only after its exact source-specific cut, trust/profile, semantic mapping, selected reader, and compatibility receipt are bound. Compatibility is directional: establish the writer/producer-to-reader behavior for the selected rollout and every supported old reader. Consumer-requiredness decides whether an unknown facet is inert or blocks the affected use. Preserve independently sourced cuts as separate unless their producers provide a verified common cut; a second source never proves scientific independence by itself.

### Что переиспользовать

- `policy-engine/src/polisyos/fabric/connectors/contracts/source_contract.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `SourceContract`. Verified at the planning source pin: versioned strict source contract already groups schema, semantics, security, quality, SLA, terms, replay, lineage, source trust, processing and retention. Contract checks do not themselves prove an actual CAP capture or semantic compatibility with every reader.
- `policy-engine/src/polisyos/data_forge/domains/catalog/source_modules.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `CatalogSourceModuleSpec; CatalogSourceStageContract`. Verified at the planning source pin: existing per-source module/asset registry seam distinguishes source, stage, dependencies, schema ID and output paths.
- `policy-engine/src/polisyos/data_forge/domains/catalog/registry.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `CatalogSourceRegistryEntry; CatalogSourceRegistrySpec`. Verified at the planning source pin: existing registry maps source entries into module specs and run profiles. The proposed second-source capture itself remains CAP-owned and is not established by registry presence.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Select the second source/profile that is materially different in the declared layout or pagination/transport pattern after the first slice source/profile and acceptance criteria are frozen. Bind CAP-02’s actual persisted receipt; a first-route WDI receipt does not satisfy this producer prerequisite.
2. Have CAP own capture, redirects/external references, parser fetch, source-specific receipt and cut/continuity evidence. Record the exact source ID, profile, parser version, source/schema generation, per-source cut, receipt root and any limitation on joint cuts. LIF consumes those typed facts and does not implement a second network or cursor owner.
3. Use the existing SourceContract and registry to map producer facets to the selected consumer’s required concepts. Evaluate compatibility in both directions that rollout requires (new output to old reader and old output to new reader), including the full retained reader window where old/offline readers remain supported. A schema parse/compatibility pass is necessary but not semantic proof.
4. Prove generic discovery/execution with a correctly implemented source profile and adapter registered through the owner contract, without editing central capability/per-source branches. Keep malformed or unsupported required capabilities fail-closed; an enum/status value alone must never dispatch or authorize source execution.
5. Preserve unknown optional facets as inert and lossless; reject or limit only the affected use when a required facet is unknown, missing, downgraded, or semantically changed. Bind actual reader/profile generation and source cut at publication so mixed-generation index reads refuse.
6. Run a fresh selected reader over the real CAP artifact, prove API/catalog status and bounded source-cut limitations, then retain separate roots/readers until old readers, backup recovery obligations, references, and GC roots are reconciled.

### Рассмотренные альтернативы

- **Treat successful parsing or schema registry compatibility as sufficient.** — Avro and Confluent define structural writer-reader compatibility and directional rollout modes; neither proves that a stable field retained its meaning, that a consumer considers it optional, or that the source cut is current.
- **Union the two source IDs and publish one global snapshot/cut.** — Independent cuts, late/backdated events, and asynchronous indexing do not form a shared snapshot without producer participation in a named protocol. Preserve source-specific cuts and expose the limited joint-currentness claim.
- **Build a second source connector, source registry, trust bootstrap, or universal schema compatibility service in LIF.** — CAP owns capture/protocol and OPS owns trust/bootstrap/restore. Use SourceContract and catalog source registry. A truly new transport/meaning crosses those owners and requires their typed adapter plus conformance rather than hidden duplication here.

### Free-grow и ресурсы

- **data or config growth:** A source of an already-supported transport and semantic class can add versioned SourceContract and registry data, including per-source facet mapping, profile, requiredness and compatibility policy. Correctly implemented source resources are discovered and executed through generic owner interpretation, not a central per-source branch.
- **extension boundary:** A genuinely new transport, parser execution mode, trust succession path, or semantic capability requires a typed CAP/OPS/native-owner extension and consumer conformance. Once implemented to that contract it is discovered through the generic path; schema/status enums cannot serve as a capability allowlist, and no arbitrary plugin code or `trusted=true` setting becomes authority by registration.
- **resource behavior:** Each added source profile increases capture, parser, indexing, reader-version and GC-root work; account for it in LIF-06. Unknown required facets and unresolved trust/source cuts fail closed for the affected use. No pagination, common snapshot, or independence claim is inferred from a distinct source ID.


### Миграция и восстановление

Run the new source/profile and reader under distinct roots alongside the accepted old reader. Promote only after CAP’s current receipt, source-specific cut, compatibility matrix, rights/trust profile, and fresh consumer pass. On rollback, serve the old reader only within its recorded validity and current rights; suspend or limit new use if its source receipt is stale. Retain old roots until references, migration, backup/recovery and GC obligations are reconciled; operational rollback does not rewind authority or erase a newer correction/revocation.


### Композиция и owners

- CAP supplies actual capture bytes/root, producer identity, source/profile/parser version, source cut, external-fetch scope and completeness limits; LIF binds but does not self-attest these facts.
- OPS supplies accepted bootstrap/trust-root, service continuity, backup/restore and resource profile; a valid historical signature is not automatically current authority.
- Consumer-requiredness is authoritative for the selected use. Unknown optional facets remain inert; unknown or silently downgraded required facets make that use limited or blocked.
- Source/schema/rule/model/reader generations and time roles are immutable across the persisted receipt, migration root, public/source-status projection and fresh reader.
- Independence is a property of a particular verification claim and method. Require relevant evidence only where that claim depends on independence; never substitute source count or graph topology.


### Acceptance и различающие проверки

- Positive: a materially distinct CAP-captured layout is discovered through the generic source registry, admitted and consumed by a fresh selected reader with the exact source/profile and cut bound. Add a second valid owner-conforming profile and show discovery/execution without a central per-capability change.
- Adversarial: independent/backdated cuts, mutation during index build, same schema with changed meaning, required facet downgraded to optional, old offline reader after validity, stale/rolled-back trust root, incomplete provider receipt.
- Removal: remove consumer requiredness while retaining producer optionality; remove exact source/profile/reader generation while retaining source ID; remove trust/continuity receipt while retaining bootstrap labels. Each must block a current-authority claim or limit the selected use.
- Surface: existing catalog/source status and selected API reader disclose the source-specific cut and compatibility limitation; no global snapshot badge is issued.


### Входы и ответственность за их получение

- CAP-02 actual second-source capture and persisted receipt for the selected materially distinct source/profile; CAP-03/CAP-04 evidence only where the claim activates those mechanisms.
- OPS deployment, trust-root succession, backup/restore and service continuity evidence for the selected profile.
- Selected consumer owner’s directional reader matrix and required/optional facet semantics.
- Source issuer’s actual cut, mutation, continuity and release semantics; institutional facts stay institutionally supplied unless independently reconciled.


### Когда обоснованно отклониться

- If selected CAP evidence is only a first-route WDI receipt, keep LIF-08 `producer_missing` until a real second-source artifact is emitted.
- If the layout distinction, reader version, trust bootstrap, or requiredness cannot be bound, preserve `not_established` and keep the affected result candidate/limited.
- If the selected source has no cross-source cut protocol, report separate source-specific cuts; do not implement a global snapshot adapter as a local workaround.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [Apache Avro Specification](https://avro.apache.org/docs/1.8.1/spec.html) — Avro requires a writer schema to interpret encoded data and defines reader/writer schema resolution, including field matching and default behavior. **Граница:** Structural schema resolution cannot prove that a field retained the same substantive meaning or is sufficient for a selected consumer.
- [Schema Evolution and Compatibility for Schema Registry](https://docs.confluent.io/platform/current/schema-registry/fundamentals/schema-evolution.html) — Backward, forward, full, and transitive compatibility answer different old/new reader questions; transitive checks cover more than the latest prior version, and compatibility choices constrain producer/consumer rollout order. **Граница:** These compatibility checks are schema-format specific and do not establish semantic equivalence, rights, or source-cut consistency.
- [The Update Framework Specification v1.0.33](https://theupdateframework.github.io/specification/v1.0.33/) — TUF separates trust roles and uses versioned, expiring metadata and snapshots to address rollback, freeze, and mix-and-match attacks in software update repositories. **Граница:** TUF is a software-update trust framework; it cannot bootstrap PolicyOS institutional authority, settle source rights, or certify semantic compatibility.
- [Language Guide (proto3), Protocol Buffers](https://protobuf.dev/programming-guides/proto3/) — Proto3 preserves unknown fields in binary messages in common round trips, while converting through JSON or rebuilding messages field-by-field can lose them; parseability alone does not protect unknown data through every transformation. **Граница:** Wire-format compatibility is not a consumer-requiredness or semantic adequacy decision.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="LIF-09"></a>

## LIF-09 — Run frozen cross-owner lifecycle acceptance and publish evidence

Исходная запись: [tasks.json](../tasks.json), `tasks[id=LIF-09]`. Review: [root-review](root-review.md#LIF-09).

### Предпочтительное решение

Make LIF-09 the frozen, independently reviewed composed-acceptance shard using the existing plan journal and the native receipts emitted by LIF/CAP/OPS owners; it is not a new lifecycle mechanism, receipt service, or authority ledger. Freeze one accepted source tree, criteria and consumer closure, then bind the exact inputs, code/schema/rule/runtime versions, outputs, complete active probe denominator, resource measurements, limitations, review identity, and fresh API/audit consumer result. Exercise the real cross-owner path and property-removal probes against that frozen identity. Rebind and rerun only the affected closure if a source, owner, consumer, or prerequisite changes after freeze. Keep E02 acceptance, owner delivery, composed acceptance, and original-obligation disposition separate; current product execution remains UNRUN until the accepted implementation is actually exercised.

### Что переиспользовать

- `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/workstreams/02-lifecycle.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `LIF-09 scope; W0-W6 and T01-T20 crosswalk`. Verified planning artifact: assigns LIF-09 to integrated acceptance/review, identifies native owners and probe families, and states runtime acceptance is UNRUN. It is not a product receipt.
- `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/execution/07-scoped-readiness.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `scoped readiness; FINAL-REVIEW and FINAL-REPLAY ordering`. Verified planning artifact: requires actual E02 acceptance, complete affected closure and source rebind; names LIF-09 as a final replay shard that joins at completion, with stage and resource constraints.
- `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/assurance/01-assurance.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `slice assurance; evidence algebra; optional handoff checklist`. Verified planning document: describes accepted evidence as an exact claim/source/input/version/time/artifact/bridge/consumer/verifier/surface tuple and states a checklist is not itself the receipt.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Wait for actual E02 acceptance and task-scoped rebind. Freeze the accepted source/tree, affected owners and sibling consumers, source/profile matrix, selected claim/use, review candidate, and conditional obligations in the existing program journal.
2. For each activated R/T/AP/W/E/X criterion, record its exact predicate, owner, input/source generation, producer, persisted output/event, bridge, fresh consumer, surface or explicit out-of-scope owner, verifier, outcome, and limitation. Preserve pass/refusal/partial/out-of-scope distinctions; an unrun or unresolved row stays explicit.
3. Classify each deciding gate predicate at admission as recomputed, independently reconciled, consumer asserted, institutionally supplied, or not established. Bind only recomputed/independently reconciled evidence to authority-grade positive; keep external source cut, grants and provider receipts in their actual institutional/producer class.
4. Run the exact selected positive, benign control, adversarial cases and matched property-removal probe through persisted state and a fresh authorized consumer. Include resource fan-in/cold recovery, source-reader migration, cache/use invalidation, rollback/currentness and every claimed API/audit surface in the frozen denominator.
5. Have the independent reviewer inspect the exact frozen candidate, verification design, and available bounded outputs; do not run a second full acceptance wave merely to prepare the final one. After review repair, record delta review; then run the one measured resource wave on the final replay identity and retain complete deciding outputs while citing tracked artifacts by path/hash. Read the accepted result back from that identity and preserve original obligation disposition separately.

### Рассмотренные альтернативы

- **Create a new universal acceptance service, parallel task registry, or second signed receipt schema.** — The existing plan journal, native owner artifacts, and assurance procedure already own scheduling and evidence composition. A parallel service would duplicate authority and still need the same producers, consumers, and verification.
- **Accept a single aggregate green, schema marker, exit code, or test count.** — Those are proxy predicates and can stay green after runtime property removal or denominator shrinkage. Each active obligation must retain its own disposition and a property-exercising consumer result.
- **Reuse SLSA provenance or Kubernetes conformance as PolicyOS semantic acceptance.** — SLSA binds build source/process claims and Kubernetes conformance checks a defined API profile. Neither establishes policy claim admissibility, complete PolicyOS consumer coverage, claim-specific independence, or legal authority. Reuse only their exact identity, repeatability, corpus and review ideas.

### Free-grow и ресурсы

- **data or config growth:** Add new approved source profiles and supported test cases as versioned inputs to the existing lifecycle acceptance matrix; each selected case gets its own exact owner, positive, negative, removal and result disposition. A correctly implemented resource/capability enters the existing generic discovery/execution path from its typed registration, not through central hardcoded allowlist edits.
- **extension boundary:** A new trust plane, audience surface, semantic method, source protocol, or owner changes the affected closure and needs a typed owner contract and independent decision. Once admitted to a supported extension contract, execution and discovery remain generic. This verification row must not become a universal policy interpretation engine or duplicate registry.
- **resource behavior:** The decisive wave grows with the selected active consumer/probe matrix, source profiles and measured fan-in. Keep the complete denominator, but serialize only shared stores, browser, provider, or backend resources. Changed sources/readers reprice affected replay; no hypothetical numerical runtime claim is made.


### Миграция и восстановление

Before freeze, source or owner change triggers exact-scope rebind. After freeze, a change to any gate input, consumer, CAP/OPS receipt or resource denominator invalidates transfer of the old green result and requires delta review plus a bounded replay of affected properties. If any required predicate fails or remains unresolved, keep the last admissible public head with its scoped stale/partial/refused state, append the failed attempt, and do not promote authority. Preserve old evidence as historical subject to rights; no destructive history rewrite or old-authority restoration.


### Композиция и owners

- E02 acceptance and task owner delivery are prerequisites, but neither alone proves the cross-owner producer → persisted artifact/event → bridge → fresh consumer → surface chain.
- Source/tree, inputs, schema/rule/runtime versions, backend/profile, command outputs, reviewer, resource denominator, audience and claim scope are exact identities; stale evidence cannot transfer to a sibling consumer or replacement dependency.
- Every active original obligation receives a pass, refusal, partial, out-of-scope, or unresolved disposition with an owner. Aggregate status cannot hide missing/failed rows.
- Only verified source-qualified evidence can support claim authority; signatures/receipts must resolve, content-bind to the exact claim/artifact/consumer, and carry verifier provenance. LLM output remains candidate.
- A complete diagnostic disposition containing refusal/limited/UNRUN does not satisfy an original criterion that requires a positive. The original obligation owner decides closure separately.


### Acceptance и различающие проверки

- Positive: one selected vertical shows the actual producer, durable artifact/event, lifecycle bridge, fresh permitted consumer and public/reviewer/MACHINE/audit surface with matching status, authority, provenance, rule and time semantics.
- Adversarial: source/right/effect/resource/cache/restore races; scheduler/control store unavailable; stale generation; replacement CAP/OPS dependency; altered sibling consumer; incomplete denominator; aggregate terminal fan-in; unsupported surface.
- Removal: delete the runtime property while retaining its fields, marker and declared predicate; the deciding gate must fail or downgrade. Replace one source/consumer after review; old evidence must not transfer.
- Completion: all activated obligations and outputs resolve against the final source/input/backend identity, independent review is on that identity, and all remaining limitations are bounded and surfaced. A plan artifact alone leaves verification UNRUN.


### Входы и ответственность за их получение

- Accepted E02 source/tree, original task dispositions, and root’s reconciled consumer/owner closure.
- CAP source receipts, selected source cuts and compatibility evidence; OPS process/trust/backup/restore profile; actual provider and rights decisions when those claims are activated.
- Native LIF-01 through LIF-08 artifacts/events, their owning runtime consumers, and each surface’s exact role/audience.
- Independent reviewer’s identity/role, exact source/input pins, complete probe denominator and deciding command outputs.


### Когда обоснованно отклониться

- Before actual E02 acceptance or complete task-scoped source rebind, no result is composed acceptance; allowed diagnostics remain candidate evidence.
- If an activated external source, legal act, trust profile, rights decision, or provider outcome is unavailable, classify it institutionally supplied or not established and limit only the affected claim/use.
- If the exact reader, source cut, resource denominator, reviewer, or fresh surface cannot be reproduced, retain `verification_missing`/`semantic_test_missing` or the more precise upstream capability label; do not certify from a plan or receipt-shaped file.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [The Update Framework Specification v1.0.33](https://theupdateframework.github.io/specification/v1.0.33/) — TUF separates trust roles and uses versioned, expiring metadata and snapshots to address rollback, freeze, and mix-and-match attacks in software update repositories. **Граница:** TUF is a software-update trust framework; it cannot bootstrap PolicyOS institutional authority, settle source rights, or certify semantic compatibility.
- [Stateful Stream Processing, Apache Flink Documentation](https://nightlies.apache.org/flink/flink-docs-stable/docs/concepts/stateful-stream-processing/) — Flink checkpoints bind positions in input streams to corresponding operator state; recovery restores the latest completed checkpoint and replays sources from those positions. Exactly-once state consistency depends on replayable sources, and unaligned checkpoints trade lower barrier delay for persisted in-flight data and extra I/O. **Граница:** This is a coordinated stream-processing snapshot, not evidence that independently sampled PolicyOS sources share a global cut or that a policy claim is true.
- [SLSA Build Provenance v1.2](https://slsa.dev/spec/v1.2/build-provenance) — SLSA provenance defines verifiable build information, including the subject, builder identity, build type, invocation parameters, resolved dependencies, metadata, and useful byproducts. **Граница:** Build provenance traces how an artifact was built; it does not establish semantic acceptance, complete consumer coverage, independent scientific evidence, or PolicyOS authority.
- [Certified Kubernetes Software Conformance, CNCF](https://www.cncf.io/training/certification/software-conformance/) — The Kubernetes conformance program runs an identical open-source test application, submits results for review, and lets end users rerun that application to check interoperability against required APIs. **Граница:** The tested Kubernetes API profile and certification do not generalize to PolicyOS semantics; the useful transfer is an exact version/profile-scoped test corpus plus review and rerun identity.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.
