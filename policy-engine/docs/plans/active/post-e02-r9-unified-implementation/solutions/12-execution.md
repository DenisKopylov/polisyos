# Вход, freeze, review и replay: предпочтительные решения

Статус: engineering recommendations; product execution UNRUN. Реализация только после E02 acceptance и полного affected-scope rebind. Исходные критерии не сокращаются; [общие решения](00-shared-decisions.md) предотвращают второго owner. [Нормативные уточнения](decision-clarifications.md) остаются предложениями.

<a id="P0-ACCEPT"></a>

## P0-ACCEPT — Resolve actual E02 acceptance

Исходная запись: [tasks.json](../tasks.json), `tasks[id=P0-ACCEPT]`. Review: [root-review](root-review.md#P0-ACCEPT).

### Предпочтительное решение

Use the existing G acceptance owner and decision as the sole entry warrant. Root reads back the actual acceptance record and binds its accepted commit and tree, precise scope, consumed inputs/backends, limitations, authority boundary, and decision provenance. Resolve moving branch names to immutable identities. Open only the work scopes covered by that decision; if acceptance or a required field is absent or contradictory, keep implementation entry closed and record the exact unresolved item. This is one external entry decision, not a second PolicyOS acceptance service.

### Что переиспользовать

- `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/execution/01-charter-and-entry.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `actual E02 G acceptance / entry`. The plan says the existing G decision, not this plan, establishes accepted sources, inputs, backends, and limits.
- `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/execution/stage-requirements.json@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `implementation_gate; supplier_stage_invariants.P0-ACCEPT`. P0-ACCEPT is fixed to actual_E02_G_acceptance.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Obtain the existing G decision and its source-qualified evidence from its competent owner.
2. Resolve the accepted source to full commit and tree identities; capture the exact acceptance boundary, inputs, backends, limitations, and exclusions.
3. Compare each proposed entry scope with that boundary and admit only matching scopes in the existing root journal.
4. Preserve the decision and append a rebind requirement if its source or scope changes.

### Рассмотренные альтернативы

- **Treat the E02 topic branch, a local green check, or a receipt-shaped file as acceptance.** — Those are proxies for the competent decision and can name a tree G did not accept; this violates the existing entry criterion.
- **Repeat G acceptance inside the programme.** — It creates duplicate authority and cannot repair absent authority by self-attestation.

### Free-grow и ресурсы

- **data or config growth:** Additional accepted scopes are appended as source-qualified decisions through the same G owner.
- **extension boundary:** No change to G authority or E02 meaning; any new acceptance class requires an explicit competent decision.
- **resource behavior:** No product compute is required; root resolves identities and opens only named scopes.


### Миграция и восстановление

Append corrections and supersession links; never rewrite or broaden an earlier acceptance. If the binding is wrong, suspend affected entry and rebind to the actual decision while preserving the old receipt.


### Композиция и owners

- P0-REBIND consumes the accepted tree and decision boundary, not a predicted completion.
- Every admitted task scope is a subset of that boundary and names its accepted inputs/profile.


### Acceptance и различающие проверки

- Positive: the exact G-accepted tree and scope are read back and resolve to the named inputs, backend, and limitations.
- Adversarial: a newer topic head or assumed completion cannot open a scope.
- Removal: remove the decision binding while leaving planning declarations; entry remains closed.


### Входы и ответственность за их получение

- The existing G acceptance decision and its competent owner.
- Accepted source, input, backend, and scope identities.


### Когда обоснованно отклониться

- No decision, ambiguous source identity, conflicting acceptance scope, or missing input/backend boundary.
- Any accepted-tree change after entry.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [SLSA v1.2 Build Provenance](https://slsa.dev/spec/v1.2/build-provenance) — Build provenance binds an artifact to its build definition, external parameters, resolved dependencies, builder, invocation, and produced subject; consumers verify external parameters and dependency identity. **Граница:** This is a software supply-chain specification. It informs source/input/run binding but does not prove a PolicyOS replay was semantically adequate, complete, or authorized.
- [Managing a merge queue](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue) — Required checks are rerun for a temporary integration group based on the latest target branch and queued changes ahead of it; failed or conflicting groups are removed. A PR-head result alone is not the combined-tree result. **Граница:** This is GitHub merge behavior, not a PolicyOS scheduler or a domain evidence rule. It supports binding final evidence to the integrated tree, not adopting a queue service.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="P0-REBIND"></a>

## P0-REBIND — Reconcile source, obligations, ownership and lease map

Исходная запись: [tasks.json](../tasks.json), `tasks[id=P0-REBIND]`. Review: [root-review](root-review.md#P0-REBIND).

### Предпочтительное решение

Keep one root-owned reconciliation journal and one canonical original-obligation inventory. Rebind from the accepted E02 tree by checking every original predicate and historical disposition, then map each affected predicate to its native semantic owner, actual readers, generated/test/API companions, selected conditional producers, consumer, and exact write/resource leases. Release a task or owner closure as soon as that affected closure is complete and its source, interface, stage, and lease evidence are read back; unrelated unresolved scopes stay visible but do not hold that closure. Keep the complete global inventory and pending map open until all original routes are reconciled, and require that complete reconciliation before FINAL-FREEZE. A dependency graph edge must say whether it means isolated preparation, owner readiness, composition evidence, execution permission, or original disposition. Do not add another scheduler or per-lead ledger.

### Что переиспользовать

- `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/execution/07-scoped-readiness.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `A complete affected scope, not a global waiting room; Edge stages`. Defines five recorded predicates for scoped release and retains complete global reconciliation before freeze.
- `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/execution/04-change-and-rebind.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `After actual E02 acceptance`. Specifies accepted-source diffing, exact predicate matching, prior plan pin, and remaining inputs.
- `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/execution/stage-requirements.json@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `supplier_stage_invariants; conditional_binding_rule`. Distinguishes global P0 completion and selected conditional bindings from task-stage edges.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Freeze the original inventory/source versions as the reconciliation denominator; retain historical statuses and source conflicts.
2. For each task, compare the accepted tree and exact original predicate; classify retained, satisfied by accepted output, partial reuse, or still required with evidence references.
3. Resolve the full affected owner/reader/generated/test/API closure and selected conditional facets; name one canonical writer per semantic owner and path family.
4. Release only completed affected closures through the existing root journal; maintain all unresolved rows until whole-program reconciliation is complete.

### Рассмотренные альтернативы

- **Wait for every source or ownership question before any implementation starts.** — It reinstates the R12 global waiting room and blocks disjoint, fully reconciled scopes.
- **Let each workstream create its own task inventory, dependency graph, or lease registry.** — It duplicates ownership state and makes omissions or conflicting writers invisible to the root.

### Free-grow и ресурсы

- **data or config growth:** Newly discovered original predicates, accepted outputs, and conditional facets are appended with source references and owner dispositions.
- **extension boundary:** New semantic owners or genuinely new transport classes receive an explicit bounded task/adapter; a free-text label cannot satisfy a producer edge.
- **resource behavior:** Only exact task write sets and phase resources are leased; unresolved closure means no speculative write lease. Static graph width is not capacity.


### Миграция и восстановление

If a new reader, shared rule, source conflict, or changed interface appears, fence only the affected writes and acceptance, rebind that closure, and retain prior dispositions and evidence in history.


### Композиция и owners

- A scoped release requires actual accepted E02 identity, exact original predicates, complete affected closure, resolved stage/conditional suppliers, and root-read-back leases.
- FINAL-FREEZE consumes completed global reconciliation; task-local releases cannot mark P0-REBIND complete.


### Acceptance и различающие проверки

- Positive: every source set is routed to exactly one canonical owner or a competent formal closure, with evidence and unresolved rows retained.
- Adversarial: a stale count, omitted predicate, duplicate semantic writer, or unknown affected consumer blocks the relevant closure.
- Removal: remove one source-obligation binding while retaining declarations; the census/reconciliation must reveal the missing original.


### Входы и ответственность за их получение

- Actual E02 acceptance boundary.
- Canonical GY, Atlas, debt, and R9 source inventories and competent closure-owner decisions.
- Actual path/readers/generated-family observations after accepted-source rebinding.


### Когда обоснованно отклониться

- New source conflict, downstream reader, shared semantic owner, conditional supplier, or source/input mismatch.
- The dispatcher treats global P0-REBIND completion as a prerequisite for a disjoint closure, or treats scoped release as global completion.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [Large-Scale Changes, Software Engineering at Google](https://abseil.io/resources/swe-book/html/ch22.html) — The described LSC process separates authorization, change creation, shard management, and cleanup; independent shards are tested and reviewed, while a train can run affected tests against the combined change set. **Граница:** This is a Google process with dedicated tooling and different scale. Transfer the shard, owner, and combined-integration principles only; it does not establish PolicyOS throughput, resource limits, acceptance authority, or a need to build an LSC platform.
- [Merging stacked pull requests](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/merging-stacked-pull-requests) — A dependent stack merges bottom-up; the status shown for a stack includes lower changes, and an intermediate change cannot be treated as an isolated integration when its lower dependencies are absent. **Граница:** Stack semantics vary by host and merge strategy. Use this only to motivate explicit bases and dependency-aware review; PolicyOS keeps its existing root-only integration owner.
- [Dismissing a pull request review](https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/dismissing-a-pull-request-review) — GitHub treats a review as potentially outdated after the reviewed change changes and requires a reason when an administrator dismisses it. **Граница:** The exact host behavior is not a universal review protocol. PolicyOS should carry review only across a proven unchanged scope and record why; it should not assume host approval state establishes semantic review.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="FINAL-FREEZE"></a>

## FINAL-FREEZE — Freeze internal source readiness and truthful current obligation dispositions

Исходная запись: [tasks.json](../tasks.json), `tasks[id=FINAL-FREEZE]`. Review: [root-review](root-review.md#FINAL-FREEZE).

### Предпочтительное решение

Freeze one immutable review candidate after all internal owner-readiness work and the complete original-inventory reconciliation are read back. Record the exact tree, planning/task manifest, selected case and deployment profile, relevant rule/schema versions, consumed upstream identities, required verification matrix, and current original dispositions. Bind genuine unavailable external facts as explicit unresolved inputs with their owners and reentry triggers; they do not receive closure or positive replay credit. An unresolved internal producer, unknown owner, or unselected mandatory scope blocks freeze. Start review from this candidate without making final replay a prerequisite to its own predecessor. Keep the candidate in the existing branch/journal workflow rather than building a freeze service.

### Что переиспользовать

- `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/execution/03-waves.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `Wave 5 — one final expensive wave`. Positions freeze before review and replay and says freeze grants no original-closure credit.
- `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/execution/05-stage-and-release-contracts.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `Freeze can preserve unresolved external facts honestly`. Owner readiness may be established while genuine external evidence stays open.
- `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/execution/stage-requirements.json@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `replay_identity.review_candidate`. Defines FINAL-FREEZE tree as the initial review candidate.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Confirm global P0-REBIND completion and every selected internal task's reviewed owner-readiness evidence.
2. Materialize the selected case/profile and full required original/replay denominator from canonical inventories and stage rules.
3. Read back immutable source, input, backend, rule/schema, and upstream references; record unresolved genuine external facts without closure credit.
4. Open independent review on this frozen candidate.

### Рассмотренные альтернативы

- **Wait for every external act or genuine input before freezing.** — It turns external uncertainty into a global engineering barrier even when internal readiness and truthful dispositions can be reviewed.
- **Use a task count, green dashboard, or moving branch name as freeze evidence.** — These are proxies that do not establish the exact source, inventory completeness, or selected profile.

### Free-grow и ресурсы

- **data or config growth:** Selected case/profile and verification rows grow from canonical original criteria and activation rules.
- **extension boundary:** New selected facets require their source criterion, producer, verifier/use owner, consumer, surface, and exact input reference before dispatch.
- **resource behavior:** Freeze itself is read-only apart from the existing journal record; it consumes no scarce replay/browser ticket.


### Миграция и восстановление

A changed source, profile, upstream output, or blocking repair creates a successor candidate. Preserve the old snapshot and review; rebind only affected scope and retain any review that demonstrably remains valid.


### Композиция и owners

- P0-REBIND global completion and internal owner readiness are necessary for freeze.
- Review consumes the exact candidate tree/profile and the original obligations/dispositions; replay consumes the later final replay identity.


### Acceptance и различающие проверки

- Positive: every internal mechanism is ready and every selected mandatory row appears in the frozen matrix or has a source-qualified unresolved external disposition.
- Adversarial: a missing internal owner cannot be renamed an unavailable external input; a genuine missing external act does not receive green credit.
- Removal: remove a selected conditional supplier binding while leaving its declaration; freeze shows the selected row unresolved or blocks.


### Входы и ответственность за их получение

- Actual source/input/backend availability and authorized case/profile selection.
- External decisions or evidence that are genuinely outside the internal producer system.


### Когда обоснованно отклониться

- Any selected profile, tree, rule/schema, or consumed upstream identity changes.
- A mandatory original predicate is missing from the frozen denominator or an internal capability is mislabeled external.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [SLSA v1.2 Build Provenance](https://slsa.dev/spec/v1.2/build-provenance) — Build provenance binds an artifact to its build definition, external parameters, resolved dependencies, builder, invocation, and produced subject; consumers verify external parameters and dependency identity. **Граница:** This is a software supply-chain specification. It informs source/input/run binding but does not prove a PolicyOS replay was semantically adequate, complete, or authorized.
- [Reproducible Builds documentation](https://reproducible-builds.org/docs/) — Reproduction requires a strategy for recreating the build environment and managing sources of variance such as timestamps, locale, paths, and input order. **Граница:** PolicyOS replay outputs may be nondeterministic and are not software binaries. Preserve exact conditions and outputs; do not promise bitwise replay equality absent a measured deterministic procedure.
- [Dismissing a pull request review](https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/dismissing-a-pull-request-review) — GitHub treats a review as potentially outdated after the reviewed change changes and requires a reason when an administrator dismisses it. **Граница:** The exact host behavior is not a universal review protocol. PolicyOS should carry review only across a proven unchanged scope and record why; it should not assume host approval state establishes semantic review.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="FINAL-REVIEW"></a>

## FINAL-REVIEW — Independent composed review and blocking delta closure

Исходная запись: [tasks.json](../tasks.json), `tasks[id=FINAL-REVIEW]`. Review: [root-review](root-review.md#FINAL-REVIEW).

### Предпочтительное решение

Run independent source and semantic review against the frozen candidate and its complete selected obligation matrix. Review packets name the exact source/input/profile identity, scope reviewed, criterion and evidence chain, changed surfaces, and reviewer competence; parallel reviewers may cover separate scopes, while root resolves cross-scope findings. Separate blocking property failures from nonblocking observations. Batch blocking repairs, apply them on the integration branch, then obtain independent delta review for each changed scope and any newly affected consumer. Root records the final replay identity only after all blocking findings are closed or explicitly dispositioned under the original competent criterion. A review stays valid only for demonstrably unchanged bound scope. This is a procedure over existing reviews and branch history, not a new approval authority.

### Что переиспользовать

- `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/execution/03-waves.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `Wave 5 review candidate and batched blocking fixes`. Requires independent reviews before the expensive wave and delta review after blocking fixes.
- `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/execution/07-scoped-readiness.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `Lease economy; changed review scope requires delta review`. Immutable-candidate review releases write leases; changed scope requires review against a compatible base.
- `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/assurance/self-review-r12.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `R12-08 and R12 boundary: no independent review claim`. R12 is explicitly a self-review, not independent acceptance of its own delta.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Assign independent reviewers by evidence/semantic scope and capture exact review identity and scope.
2. Review the actual owner binding, output, bridge, fresh consumer, status/authority/time behavior, and required surface against original predicates.
3. Classify findings by new class versus known class; batch blocking fixes and delta-review changed or newly affected scope.
4. Read back the integrated final tree and root-bind it with exact inputs, profile, and upstream identities for replay.
5. P40: on the second finding in the same class, stop instance repair. Widen the mechanism to the protected quantity or declare the bounded residual, smallest missing capability and its falsifier. Later instances fold into that residual without consuming another review round; new classes remain separately reviewed.
6. Before declaring a bounded residual, inspect the canonical owner and relevant surfaces and confirm the smallest closing capability does not already exist. Cite that source-bound search/consumer evidence; if absence is not established, continue reuse/widening rather than treat the capability as externally unavailable.

### Рассмотренные альтернативы

- **Let authors self-review, accept a stale review, or infer approval from a clean-looking diff.** — Authorship, immutable bytes, and review status are not independent semantic review; changes may invalidate the evidence.
- **Repeat the entire expensive final replay after every code review comment.** — Review resolves the source candidate before the one expensive replay; only blocking changes require affected-scope delta review and then the final replay.

### Free-grow и ресурсы

- **data or config growth:** Review coverage expands only when the bound affected closure or selected original matrix expands.
- **extension boundary:** New semantic classes require a qualified reviewer and distinguishing evidence; review cannot ratify a new system design decision by itself.
- **resource behavior:** Read-only reviews proceed in parallel on immutable candidates; no write or heavy execution lease is held solely while waiting for review.


### Миграция и восстановление

Review evidence remains attached to its candidate. A changed scope invalidates that scope's result; preserve the history, repair on the current integration base, and review the delta without rebasing or rewriting handed history.


### Композиция и owners

- The frozen candidate plus complete matrix feed review.
- FINAL-REPLAY consumes only the final integrated tree after blocking repair and independent delta review.


### Acceptance и различающие проверки

- Positive: every required review scope has an independent decision on the bound candidate; blockers are closed and the final replay tree is read back.
- Adversarial: a post-review change to a relevant authority/status/input path invalidates the affected review until delta review.
- Removal: removing the reviewer-to-scope binding while leaving a review receipt cannot satisfy the required review.
- Bind author and reviewer identities/roles to the exact immutable candidate. A same-principal or self-issued review packet cannot satisfy the required independent review even if all prose and hashes match.


### Входы и ответственность за их получение

- Independent reviewers with the competence required by each selected semantic/property scope.
- Competent owner decisions for any original obligation closure.


### Когда обоснованно отклониться

- Blocking review finding, changed source/profile/input, newly discovered affected consumer, or second finding of the same class.
- No independent qualified reviewer is available for a load-bearing semantic scope.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [What to look for in a code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html) — Reviewers should examine assigned changes in context and identify which portions they reviewed when review responsibility is split; qualified reviewers are needed for specialized concerns. **Граница:** This is guidance for code review, not evidence of policy admissibility or competent closure of original obligations.
- [Dismissing a pull request review](https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/dismissing-a-pull-request-review) — GitHub treats a review as potentially outdated after the reviewed change changes and requires a reason when an administrator dismisses it. **Граница:** The exact host behavior is not a universal review protocol. PolicyOS should carry review only across a proven unchanged scope and record why; it should not assume host approval state establishes semantic review.
- [Large-Scale Changes, Software Engineering at Google](https://abseil.io/resources/swe-book/html/ch22.html) — The described LSC process separates authorization, change creation, shard management, and cleanup; independent shards are tested and reviewed, while a train can run affected tests against the combined change set. **Граница:** This is a Google process with dedicated tooling and different scale. Transfer the shard, owner, and combined-integration principles only; it does not establish PolicyOS throughput, resource limits, acceptance authority, or a need to build an LSC platform.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="FINAL-REPLAY"></a>

## FINAL-REPLAY — One source-bound composed replay and commissioning wave

Исходная запись: [tasks.json](../tasks.json), `tasks[id=FINAL-REPLAY]`. Review: [root-review](root-review.md#FINAL-REPLAY).

### Предпочтительное решение

After final review, materialize the exact selected verification matrix and source/input/backend identities from the final replay candidate. Dispatch only independent shards that fit actual root-controlled write/resource leases and runtime capacity; shared browser/store/native-memory/provider work stays serialized where contended. LIF-09 and GYD-16–22 are completion witnesses in the same wave, not start barriers for resource-independent shards. Track the frozen expected set, shard identity, actual emitted output, and terminal state per row. Join when every expected row has a source-qualified PASS, FAIL, ERROR, SKIP, UNRUN, or genuine unavailable outcome; then evaluate original predicates over actual content and consumer behavior. Only complete required evidence with its predicates satisfied is accepted replay. A complete failed or incomplete diagnostic wave remains useful evidence but cannot become programme acceptance. Bind no result to a mutable branch alias or receipt count.

### Что переиспользовать

- `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/execution/07-scoped-readiness.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `Wave start and completion are different dependencies`. Allows independent shards to start after reviewed identity and joins lifecycle and GY results at completion.
- `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/execution/stage-requirements.json@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `overrides.FINAL-REPLAY; replay_identity`. Requires exact source/input/backend join, all frozen matrix rows, and preserves terminal states; receipt existence is not positive.
- `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/execution/03-waves.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `Wave 5 — one final expensive wave`. Retains GY output ordering and joins LIF-09 without making it a global start barrier.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Root freezes the exact final tree, input/profile, backend matrix, rule versions, and every selected required row before execution.
2. Partition only by real independent dependencies and resource conflicts; dispatch same-wave shards under actual capacity and execution permission.
3. Each shard emits its deciding output with run identity, row IDs, input references, source/tree, rule/schema versions, exact consumed upstream artifact identities and backend/profile; preserve full outputs per policy.
4. Reconcile the complete expected denominator against outputs and evaluate each original property; mark diagnostic versus accepted replay explicitly in the existing journal.

### Рассмотренные альтернативы

- **Start all shards only after LIF-09, or treat each verification task as a global serial stage.** — This reinstates the barrier R12 removed despite independent resources and inputs.
- **Join on all_done, receipt count, or a green command exit alone.** — Completion says execution ended; it does not say the expected row appeared, the artifact is authentic, or the original property passed.
- **Repeat the expensive wave for every already-reviewed nonblocking edit.** — It spends scarce resources without new deciding evidence; changed load-bearing scope instead triggers targeted rebind/review before the final bound replay.

### Free-grow и ресурсы

- **data or config growth:** The selected matrix expands from frozen case/profile conditions and original criteria; each activated conditional row names its own supplier and expected result.
- **extension boundary:** A new backend or semantic claim requires an original criterion, permitted native producer, consumer, verifier, and a qualified matrix row before it is claimed.
- **resource behavior:** One coordinated wave stays within measured runtime, root-only integration, shared-resource leases, and the applicable delegation cap; no concurrency is inferred from task graph width.


### Миграция и восстановление

Do not overwrite replay receipts. A changed tree/input/backend/upstream reference fences affected results, then rebinds and reruns only the necessary affected proof; preserve the original run as historical evidence.


### Композиция и owners

- FINAL-REVIEW emits the final immutable replay identity.
- Every selected conditional binding supplies an actual persisted artifact or typed absence, verifier/use owner, consumer, surface, stage, and exact execution input.
- FINAL-USE consumes accepted composed results and the full original disposition set.


### Acceptance и различающие проверки

- Positive: every selected frozen matrix row has the correct source/input/backend-qualified output, and every mandatory replay predicate passes through the real consumer.
- Adversarial: omit one required output, substitute a prior-tree receipt, or keep an ERROR/SKIP/UNRUN row; the wave cannot be accepted.
- Removal: remove a decisive producer binding but keep declarations and status markers; the real consumer fails the named property.
- Swap only a rule/schema version or upstream artifact with identical source/input/backend labels; the affected shard is stale and cannot join as accepted. Independent unaffected shards keep their valid receipts.


### Входы и ответственность за их получение

- Permitted source/input/backend availability and any required site/provider/run permissions.
- Actual external evidence required by selected criteria.


### Когда обоснованно отклониться

- Missing, stale, mismatched, failed, skipped, interrupted, or unverified required output.
- Changed final identity, newly activated conditional facet, resource conflict, or process whose termination is not confirmed.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [Large-Scale Changes, Software Engineering at Google](https://abseil.io/resources/swe-book/html/ch22.html) — The described LSC process separates authorization, change creation, shard management, and cleanup; independent shards are tested and reviewed, while a train can run affected tests against the combined change set. **Граница:** This is a Google process with dedicated tooling and different scale. Transfer the shard, owner, and combined-integration principles only; it does not establish PolicyOS throughput, resource limits, acceptance authority, or a need to build an LSC platform.
- [Managing a merge queue](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue) — Required checks are rerun for a temporary integration group based on the latest target branch and queued changes ahead of it; failed or conflicting groups are removed. A PR-head result alone is not the combined-tree result. **Граница:** This is GitHub merge behavior, not a PolicyOS scheduler or a domain evidence rule. It supports binding final evidence to the integrated tree, not adopting a queue service.
- [SLSA v1.2 Build Provenance](https://slsa.dev/spec/v1.2/build-provenance) — Build provenance binds an artifact to its build definition, external parameters, resolved dependencies, builder, invocation, and produced subject; consumers verify external parameters and dependency identity. **Граница:** This is a software supply-chain specification. It informs source/input/run binding but does not prove a PolicyOS replay was semantically adequate, complete, or authorized.
- [Reproducible Builds documentation](https://reproducible-builds.org/docs/) — Reproduction requires a strategy for recreating the build environment and managing sources of variance such as timestamps, locale, paths, and input order. **Граница:** PolicyOS replay outputs may be nondeterministic and are not software binaries. Preserve exact conditions and outputs; do not promise bitwise replay equality absent a measured deterministic procedure.
- [Dags: trigger rules](https://airflow.apache.org/docs/apache-airflow/stable/concepts/dags.html#trigger-rules) — Airflow distinguishes waiting for all upstream tasks to succeed from waiting for them merely to finish; some early-fire rules do not wait for every upstream task. **Граница:** This is an orchestration example, not a PolicyOS dependency engine. It supports the conceptual distinction between starting independent shards, joining their terminal outcomes, and accepting their results; no Airflow component is proposed.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="FINAL-USE"></a>

## FINAL-USE — Full programme disposition and first-use admission proposal

Исходная запись: [tasks.json](../tasks.json), `tasks[id=FINAL-USE]`. Review: [root-review](root-review.md#FINAL-USE).

### Предпочтительное решение

Treat FINAL-USE as a source-qualified release decision dossier and proposal to the competent human/institution, never as automatic authority to deploy. At the bound use date, reread the complete canonical GY/Atlas/debt/R9 original set and every original predicate. Each mandatory nonclosed original must have accepted evidence or formal closure by its competent owner; retain historic closures unless a material delta affects them. Reconcile genuine external facts, selected commissioning case, deployment profile, permissions, audience/surface, validity period, and outstanding limitations. A successful demo, owner-readiness, refusal mechanism, unselected tier, or clean replay receipt cannot close an original row by itself. If a human explicitly changes scope, record exact IDs, claims, risks, authority, and expiry/re-entry conditions before considering that changed scope; absent this, first-use admission stays unavailable. The root dossier does not sign another institution's decision.

### Что переиспользовать

- `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/execution/05-stage-and-release-contracts.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `Release remains a distinct complete-set decision`. Requires all rebound originals and FINAL-REPLAY; no automatic closure from local readiness.
- `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/tasks.json@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `tasks[FINAL-USE].required_original_dispositions`. Defines the four canonical source sets and says first use remains blocked by any unresolved mandatory original absent explicit human scope change.
- `policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `signature rule; three roles; scope adjudication`. PolicyOS owns its signatures for as long as they stand and integrates external institutional acts as typed evidence.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. At the proposed use date, resolve the accepted replay identity and revalidate time-sensitive source, law, data, calibration, and permission inputs.
2. Enumerate every original mandatory predicate and bind accepted evidence or competent formal closure; preserve material residuals and the decision history.
3. Confirm the actual commissioned case/profile and external permissions/surface audience; compute no scope reduction by executor preference.
4. Prepare the release dossier for the competent authorized human; record the decision and its validity/reissue triggers in the existing record.

### Рассмотренные альтернативы

- **Admit first use from one successful demonstration or a profile that happens to omit open work.** — This loses original obligations and changes programme scope without competent human authority.
- **Have PolicyOS issue external legal, institutional, or deployment authority itself.** — That creates a sovereign subsystem outside the ratified identity boundary.

### Free-grow и ресурсы

- **data or config growth:** The dossier enumerates original dispositions and the commissioned profile; new use cases add their selected original criteria and external evidence.
- **extension boundary:** PolicyOS can custody and project its own justification; external authorization remains a typed external act with its source institution and scope.
- **resource behavior:** This is a bounded read/reconciliation task. Do not schedule a new expensive replay unless a material input or identity change invalidates prior evidence.


### Миграция и восстановление

If a signed claim becomes stale or a predicate is invalidated, suspend the affected claim and reissue or withdraw under its existing owner lifecycle; preserve prior decisions and their time/source basis.


### Композиция и owners

- Accepted FINAL-REPLAY and complete original dispositions are both necessary.
- The final use decision is issued by the competent human/institution and binds case, profile, audience, validity, and unresolved limitations.


### Acceptance и различающие проверки

- Positive: all mandatory original predicates have accepted evidence or competent closure, current external facts are bound, and the authorized decision is explicit.
- Adversarial: leave GY-O0-NC-01 or any other mandatory row unresolved after local readiness; first use remains blocked.
- Removal: delete a source-row disposition binding while retaining a summary count; the complete-set reconciliation detects the omission.


### Входы и ответственность за их получение

- Competent-owner closures and actual external evidence.
- Commissioning and deployment/site/rights authorization from the relevant institution.
- Human decision to authorize this scoped first use.


### Когда обоснованно отклониться

- Any unresolved mandatory original, stale law/data/calibration, invalidated replay identity, changed audience/profile, or missing external permission.
- Any proposed scope deferral without explicit human change and bounded claim/risk record.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [SLSA v1.2 Build Provenance](https://slsa.dev/spec/v1.2/build-provenance) — Build provenance binds an artifact to its build definition, external parameters, resolved dependencies, builder, invocation, and produced subject; consumers verify external parameters and dependency identity. **Граница:** This is a software supply-chain specification. It informs source/input/run binding but does not prove a PolicyOS replay was semantically adequate, complete, or authorized.
- [Dismissing a pull request review](https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/dismissing-a-pull-request-review) — GitHub treats a review as potentially outdated after the reviewed change changes and requires a reason when an administrator dismisses it. **Граница:** The exact host behavior is not a universal review protocol. PolicyOS should carry review only across a proven unchanged scope and record why; it should not assume host approval state establishes semantic review.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.
