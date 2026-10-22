# Post-E02 PolicyOS program: conflict-aware parallel execution

**Kind:** future execution design; not runtime evidence or an E02 acceptance record.
**Source pin:** worktree branch `codex/e02-integration`, HEAD `d40bca270ef5c456e8233196e4d8d65e099777a7` (2026-10-22).
**Purpose:** shape a future program spanning R9 lifecycle/acquisition work, remaining GY work, Atlas, and assigned debt. Root remains the sole admission authority and integrator. Future execution may use `root → lead → leaf` under a bounded root grant and actual runtime permission; leaf delegation is forbidden. If the runtime permits only direct agents, root dispatches every worker directly. This review itself uses direct agents only.

This document records a scheduling design only. No product tests, imports, builds, installs, or production-data reads were run for this note.

## Operating rule

Use four separate models at once:

1. **Readiness DAG:** which capability claims have their required upstream artifacts, accepted interfaces, and owners.
2. **Write-conflict graph:** which ready slices may not edit the same canonical file, API/DTO, generated family, or governed artifact at once.
3. **Resource graph:** which commands contend for a named browser, fixed port, DuckDB/WMR scratch, cache, provider quota, or finite CPU/RAM/disk budget.
4. **Integration and review queue:** how many source-pinned slices can be integrated and reviewed without making a stale or oversized batch.

These graphs answer different questions. A DAG edge delays a dependent claim; a path-conflict edge gives a single-writer lease; a resource edge serializes only the shared resource; a review queue limits the flow into integration. A dependency in one graph does not create a blanket lock in the others.

For time `t`, active writers are bounded by `min(available writer seats, ready claim slices with disjoint leased write sets, slices admitted by resource budgets)`. A task is dispatched only when its node is ready and its write/resource leases are available. The scheduler is work-conserving: a busy browser or expensive replay does not idle lint, type checks, architecture checks, logic tests, production builds, or read-only censuses that do not touch its resources. Worker count is capacity, never an execution quota. No speedup ratio is promised: critical-path work, review throughput, resource waits, and integration cost remain; measure representative workloads before revising a ceiling.

## Readiness DAG

The graph is claim- and artifact-based, not one lane per department. Expand each roadmap row into an executable slice just before it becomes ready, with exact paths, producer, persisted artifact, bridge, consumer, surface, negative semantic check, and owner. Keep unresolved research as a question or typed limitation; do not turn it into a contract by scheduling pressure.

**R0 — admit the program snapshot.** Root pins the branch/tree, records the actual E02 disposition, inventories only open/current slices and their source identities, and names an accountable owner and checkable claim for each. Reuse existing plans, owner maps, task registries, and admission tools. Do not reissue completed debt as new work. Example: GY §3.5.7 says GY-INFRA-2 A/B are complete and C was closed negative; GY-INFRA-3 Step 0 is the evidence gate before its later steps. A negative route closes that mechanism proposal but does not close the objective.

**R1 — owner and interface reconciliation.** One lead per program prepares a source-bound map: GY canonical producer/consumer and remaining DAG nodes; R9 lifecycle W0 / acquisition A0 native owners and first supported route; Atlas current slice/adoption state and shared surface contracts; debt row to owner, paths, and blocker. Root resolves overlapping claims, appoints one writer for each shared API/DTO/schema/generator/ledger, and freezes only the small cross-owner bindings needed to unblock independent work. This stage does not require a full artifact replay.

**R2 — independent owner seams fan out.** Once their own interfaces are pinned, GY slices, R9 owner slices, Atlas vertical slices, and debt closures can proceed together where their writes and resources are disjoint. Keep native ownership: Fabric capture, Core storage, Scientist claim/support, rights/security, and dashboard surface owners do not transfer merely because one integrator composes the path. For R9 specifically:

- Lifecycle W1 (capture/resume), W2 (semantic relation/use), W4 (purpose/copy/restore), and W5 (durable duty) may develop after W0's participant and protocol map, within their own owner areas.
- Acquisition A1 follows A0 and the fixed first-route contract. A2/A3 can advance in parallel after that capture contract is stable. A4 can run beside A5 when it uses the existing worker; a new remote site executor waits for A5's durable dispatch/receipt/cancel seam. A7 extends the named native integration contract, not a new institutional subsystem.
- W3 enrollment/change/fresh projection may be designed alongside owner work, but composed acceptance waits for the real W1/W2/W4 outputs and W0's binding. A6 follows a chosen deployment/backend profile and representative local path; it must not hold all useful local acquisition work. W6's second-source/rollout proof follows first-slice source freeze and independent review.
- Do not claim R9's proposed runtime probes are already passed: lifecycle06 and acquisition05, with the R9 receipt, explicitly mark them UNRUN / documentary.

**R3 — bridge and composed consumers.** Start integration nodes as soon as their named producer artifacts exist. Compose claim binding, event enrollment/reissue, lifecycle/provenance projection, source rights, Atlas API/MACHINE projections, and GY consumers through their canonical bridge. A consumer may be implemented against a frozen strict interface before its producer lands, but cannot be accepted until it consumes a produced, persisted, verifier-backed result. Keep contract edits and their representative usage together when possible; never land a decorative standalone contract and call the capability complete.

**R4 — second-source and deployment scope.** Add a second source or selected backend only where the first vertical establishes the reusable contract and an explicit semantic/transport distinction is named. Atlas migrations remain in the existing dashboard estate and close through a real consumer plus proof that the previous path is strangled. Deployment evidence names the selected cell/profile and workload; it does not claim universal connector, cloud, erasure, or capacity coverage.

**R5 — source freeze, review, then final replay.** Freeze the exact implementation and its dependency identities; run all independent reviews against that snapshot; batch accepted blocking repairs; review the delta against the original findings; then run the expensive closeout wave once. A cosmetic finding after freeze is recorded as debt. Only artifacts whose actual bound projection/input changed are reissued. Full closeout still runs where required; cache economics never weaken a semantic gate.

The critical path is the longest chain of actual dependencies (often interface reconciliation → owner producer → bridge/consumer → review → expensive closeout), not “GY before Atlas” or another invented program-wide sequence. Ready off-path slices continue while one chain or one resource waits.

## Write-conflict graph and leases

Each task envelope declares a **read set**, **write set**, **generated outputs**, **claimed property**, **interface versions**, **upstream artifact refs**, **resource keys**, and expected output. Root admits the task only after checking current branch attachment and exact paths. A conflict exists for overlapping writes or a shared semantic owner, not merely for two tasks having the same broad domain name.

Use one canonical writer per independently owned public API, DTO, generator, status grammar, or governed artifact. Consumers may work read-only against a pinned interface version. The generator owner owns the schema plus all generated outputs and regeneration receipt; generated files are regenerated from the canonical source, never hand-merged. Atlas’s explicit exclusive sets include (a) each shared `architecture/atlas_surfaces/**` artifact, (b) `schemas/runtime_api_v1.openapi.json` together with its four generated client/type outputs (five family artifacts including the schema), (c) the Playwright visual/snapshot lane, (d) Storybook, and (e) a fixed-port dev server. GY’s actual shared-state set includes the composed-WMR/DuckDB scratch, FTS index, owner caches, source-flip harness, and any same canonical artifact. The claim ledger, debt register/generated ledger, Atlas master plan, GY plan, and a shared append-only journal each have one writer while being changed. Do not lock all of `src/`, `apps/`, or `docs/` because one file in the tree is contested.

If a task discovers a new overlap, stop before writing the shared path. Return the exact conflicting path/owner and proposed boundary to root; root either serializes the writers or cuts the slice at a real API boundary. Never duplicate a DTO, generator, ledger rule, or “temporary” second implementation to avoid a lease. Keep established public surfaces strict and update actual consumers in the same slice or an explicitly dependent slice.

A writer lease is tied to `{task_id, owner, branch, base_commit/tree, write_set, interface/schema/rule versions, bound-input/projection identity, resource keys}`. It is released at a clean committed boundary or explicit blocked state. It is not held while waiting on dependencies. Renew on objective progress receipts, not heartbeat prose. If the source pin or upstream binding changes, pause dependent acceptance and ask root to re-evaluate the DAG; preserve the work and do not silently rebase its meaning.

Follow project history rules: verify attached branch with `git status -sb` before work and every commit; commit clean boundaries; do not leave reviewed work in a stash across a stop/handoff; no history rewrite; unexpected HEAD/tree state is an architect stop. Reassignment requires reading the worker’s current branch, commits, and exact worktree before another writer receives the lease. Pin immutable input commits in task handoffs; do not freeze a mutable procedural rule to an obsolete commit. For history-preservation rules, use the intended relationship.

## Resource graph, local/cloud split, and budgets

Attach a resource ticket to each run: CPU/thread demand, peak RSS, peak temporary-disk use and scratch path, fixed ports/processes, cache identity, browser/Storybook token, external request/pricing/quota scope, timeout basis, and whether any protected source data is present. Budget is a vector with a reserve for OS, recovery, logs, and the required cold closeout; do not infer capacity from agent count. If a lane has no measured cost, run and record one representative workload before setting its timeout or admitting concurrent copies. Stop a run only on the measured timeout/progress rule; CPU-active work with advancing milestones continues.

Only actual sharing creates a semaphore. A cold WMR/FTS/owner replay holds the GY owner-state token; another run using that scratch waits, while unrelated Lane-0 checks continue. One Playwright/visual task uses the browser/snapshot token, one Storybook task uses its runner, one server owns a fixed port, one writer owns each governed Atlas artifact, and one generator task owns the OpenAPI/client family. A one-process sweep reuses one content-identified build where the lane contract permits. Use Lane 0 for synthetic/logic checks with no owner I/O, Lane 1 for owner-derived checks through the valid cache, and Lane 2 for the cold full closeout once after freeze and review.

Do not send production payloads, credentials, or sensitive source bytes to a cloud worker. Keep protected reads and payload-bound runs in an authorized local environment; cloud workers may handle code, docs, synthetic fixtures, and explicitly approved metadata/content identities. A hash is not automatically safe to export if it reveals a protected object. The R9 deployment dossier calls for measured wall/RSS/bytes/I/O/threads/queue age and selected limits; it does not authorize moving large production data to cloud.

No global number of concurrent tests or runs is useful before their costs and shared resources are measured. Enforce live memory/disk/provider admission from the declared complete workload denominator, not a guessed hard cap. When budget is tight, queue only the jobs contending for that budget and keep work on disjoint inputs/resources active. An unknown external cost is not a zero-cost job.

## Roles and checkable outputs

A role is a task mode, not an independent department. Every worker, including a lead-created leaf, is admitted in the single root registry under the delegation rules below.

| Role | Write permission | Required output |
|---|---|---|
| Domain lead/planner (GY, R9, Atlas, debt) | The assigned plan slice only, if leased; otherwise read-only | Source paths and `@commit` pin; complete denominator for any set-level claim; exact capability nodes, dependencies, owner/API/write sets, conflicts, missing labels, pattern pass, and next acceptance signal. Lead may create only children explicitly covered by a root grant and permitted by the runtime; otherwise it returns the assignment proposal to root. |
| Owner implementer | Exact leased mechanism paths and its mirrored claim-scoped tests | One self-contained behavior change proving the assigned property; producer → persisted artifact/event → bridge → consumer → surface/out-of-scope; negative/removal witness; exact commands/results once implementation is authorized; versioned refs, migration, residual labels, and clean commit. |
| API/DTO/generator owner | One canonical schema/DTO/generator family and its generated outputs | Strict versioned contract plus one real use/consumer, regenerated outputs and parity/freshness evidence, compatibility and downstream handoff. No sibling implementation. |
| Independent reviewer | Read-only against an exact source snapshot | Review package identity; claims assessed; blocking findings with divergent case/property and source path; cosmetic debt distinguished; disposition per claim. After repair, delta-only review with the first findings as checklist. |
| Claim-scoped verifier / census reader | Read-only except a separately leased test-plan artifact | One property and its accepted input denominator; exact source/probe identity; falsifier; verdict and missing evidence. No count from sampled files or markers. |
| Resource-run steward | Runner output and its own scratch only | Resource ticket, measured time/peak use, full command and completion evidence, contention/cleanup state, and receipt identity. Does not edit owner code to make a run green. |
| Root integrator | Integration branch/artifact manifest and assigned integration files | Deterministic batch of compatible reviewed changes; exact changed paths and dependency identities; conflicts resolved at the owner boundary; branch readback and invalidated/downstream receipts identified. |

Tests stay claim-scoped: each capability owner writes the behavior test(s) with the change (including the seeded negative where the Atlas plan requires it); the independent verifier challenges whether the test measures the property, including a remove-the-property/keep-the-markers case. Constructor-only tests do not close a runtime claim. A slice is not “green” because its broad suite passes if the particular producer/consumer boundary was never exercised.

## Staffing envelopes (illustrative headcount, not work quotas)

The numbers count all non-root agents across both permitted levels; the single root is additional. Leads, writers, reviewers and nested leaves share this one pool. Four planning seats correspond to the four program streams; each permitted child consumes a seat already included in the table, never an additional per-lead quota. “Writers” are **maximum concurrent independent write leases**, never simultaneous edits to shared files. Use fewer if the ready/conflict/resource graphs expose fewer independent slices. Reallocate unneeded planning/read/run seats to the active review backlog; never invent tasks to fill a tier.

| Envelope | Program leads | Independent mechanism writers (lease ceiling) | Read-only source/contract mappers | Independent reviewers | Resource/run stewards | Arithmetic |
|---|---:|---:|---:|---:|---:|---:|
| 24 total worker seats | 4 | 10 | 4 | 4 | 2 | 4 + 10 + 4 + 4 + 2 = 24 |
| 48 total worker seats | 4 | 24 | 8 | 8 | 4 | 4 + 24 + 8 + 8 + 4 = 48 |
| 100 total worker seats | 4 | 48 | 20 | 20 | 8 | 4 + 48 + 20 + 20 + 8 = 100 |

**Stage allocation:** at program admission, leads and read-only mappers build the four source-bound maps; writers take only already-ready owner nodes, reviewers challenge completed frozen slices, and resource stewards admit only runs with a valid resource ticket. During fanout, the writer ceiling is further limited by the number of pairwise-disjoint ready write sets and measured budget. During integration, root serializes shared-file batches and may integrate independent reviewed slices from different streams in one deterministic batch. At freeze, writing on the reviewed slice stops; its reviewers work in parallel on the same exact snapshot. The expensive closeout token remains one per genuinely shared resource regardless of whether the staff envelope is 24, 48, or 100. No tier implies a fixed count of PRs, tests, file changes, or executions.

A work-conserving fair queue gives precedence to authority/status/soft-gate blockers, then producer/bridge and surface gaps per the repository repair order. Within each class, age ready tasks across GY, R9, Atlas, and debt (weighted deficit/oldest-ready) so one stream cannot starve. Dependencies that are not ready hold no worker lease. For a repeated finding, bucket it by class before repair; after the second same-class escape, widen the mechanism or record a bounded residual and its falsifier (P40) instead of consuming the team on ladder fixes.

## Integration and review cadence

Keep change packages small and self-contained, with their relevant test and actual use. Root integrates compatible ready slices serially at clean boundaries; it does not wait for an arbitrary number of tasks. Each candidate records its exact base and writer; after a batch lands, re-read branch state and source files, recompute which downstream nodes actually changed, and reissue only receipts whose bound input/projection changed. Do not let reviewers discover a contract change after its expensive receipt wave.

The first independent review covers the full package at the frozen source identity. Reviewers may run independently across disjoint claims. Batch all accepted blocking fixes, then conduct delta-only rereview against that same finding list. Cosmetic post-freeze suggestions become debt. After review is clear, run one closeout wave over the exact content-bound chain. Poll long jobs silently and report only stage receipt, red, or stop condition. Measure timeouts once; an unmeasured timeout is a harness defect, and a timeout of advancing work is not a product verdict.

The integration bottleneck is deliberate: there is one accountable integrator, one canonical writer for each shared artifact/API family, and independent reviewers. If review-ready work grows while reviewer slots are saturated, stop admitting more writers onto that dependency cluster; use remaining capacity on off-path ready work, read-only censuses, or review. Do not confuse a burst of agent output with accepted throughput.

## Executor prompt outline

> You are a leaf assignment admitted by root, directly or under grant `<grant_id/parent_id>`. Do not create child workers. Only the separate lead prompt can receive a delegation grant. Own claim `<claim_id>` in stage `<stage>`. Base branch/tree is `<branch>@<commit>`; interface/schema/rule identity is `<version + hash>`. Your exclusive write set is `<paths>`; read-only inputs are `<paths/artifact refs>`; resources to lease are `<resource keys>`. Upstream accepted outputs are `<refs>`; the property and one distinguishing negative are `<property/falsifier>`; expected capability closure is `<producer → artifact/event → bridge → consumer → surface>`.
>
> First confirm the branch is attached and the source pin and file ownership still match. Apply reuse-first and the existing native owner boundaries. Keep the change self-contained and include its claim-scoped semantic test/negative. Do not alter shared APIs, generated files, ledgers, or another worker’s leased path; report the precise overlap to root before writing. Keep protected payload/credentials local; cloud scope is limited to approved code/docs/synthetic inputs. Use only the declared resource budget and measured timeout. Return exact changed paths, source/input identity, contract versions, commands and full deciding outputs, review status, residual capability labels, blockers, and a clean committed boundary. If an unexpected branch/tree or upstream identity appears, stop and preserve the work for root’s reassignment decision.

## Pattern pass and acceptance

Relevant recurring risks: P01/P02 contract-only or thin bridge; P03 hidden surface richness; P04/P05/P09/P15 status, authority, warning, or candidate laundering; P07/P08 replay/time semantics; P13 duplicate registries/contracts; P27/P28 owner bypass or parallel legacy path; P29/P32 form-based proof; P31 instance repair; P33/P34 probe-shaped or incomplete exclusion; P35/P36 denominator and adjacency claims; P37/P38 declared predicates and proxy gates; P39 budgets that count required records; P40 ladder repair; P41 inherited-red attribution. Closure is one behaviorally proven, owner-admitted vertical per claim, with exact boundaries and explicit residual labels. This scheduling note itself does not close any capability.

**Acceptance signal for this design:** every dispatched slice has an exact source pin, readiness predecessors, one named writer per shared contract/artifact, disjoint write/resource leases, claim-scoped semantic negative, review identity, evidence of resource admission, and an explicit output/blocked state. At program closeout, the deciding review precedes the one required expensive replay; branch/file readback agrees with the reported delivery.

## Inputs

- `AGENTS.md`; especially operation model, P31–P41, capability reality check, and history / verification rules.
- `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md` §3.5.7 E1–E14, GY-INFRA-2/3, and §3.5.13 W1–W5.
- `policy-engine/docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md` “Execution Doctrine”; Atlas shared resources, single-writer schema/generated family, review timing, and work preservation.
- `policy-engine/docs/research/universal-policy-design/external-foundations/lifecycle/06-delivery-and-review.md` §3 W0–W6 and §4 T01–T20 (design probes UNRUN).
- `policy-engine/docs/research/universal-policy-design/external-foundations/acquisition/05-implementation-and-review.md` §1 A0–A7, §2 handoff, §3 deployment dossier, §4 AP01–AP19 (conditional gates; not all first-route prerequisites).
- `policy-engine/docs/research/universal-policy-design/external-foundations/research-receipt-r9.json`: final documentary revision; nine direct reviewers, four delta reviews, root as sole tracked writer; runtime probes still UNRUN; `G_code_acceptance: false`.
- `policy-engine/docs/superpowers/plans/2026-08-30-debt-g-atlas-residuals.md`: exact owner/write fences, pattern pass, debt batching and closeout.

External large-change references (guidance only; PolicyOS rules take precedence):

- [Google Engineering Practices: Small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html) — focused self-contained changes, related tests, and planning how dependent changes split before implementation.
- [Google Engineering Practices: Speed of Code Reviews](https://google.github.io/eng-practices/review/reviewer/speed.html) — optimize team throughput and split oversized reviews rather than queueing one large package.
- [Trunk Based Development: Short-Lived Feature Branches](https://trunkbaseddevelopment.com/short-lived-feature-branches/) — isolated single-owner changes, short review/integration cycle, and review/merge capacity as a separate constraint from agent output.
- [Martin Fowler: Branch by Abstraction](https://martinfowler.com/bliki/BranchByAbstraction.html) — a gradual migration pattern where coexisting implementations sit behind one owned abstraction; use only when it fits the existing owner contract and Atlas strangling rule.


## Optional bounded delegation in future execution

Depth is `root=0`, `lead=1`, `leaf=2`; depth3 is forbidden. Nested creation requires both actual runtime permission and a root-issued grant. This document is a project execution procedure, not a request to build an agent-management service. Current research uses direct agents only.

Root retains one task/admission/write/resource journal. A grant binds parent and child IDs, permitted tasks, exact source/read/write sets, semantic-owner and generated-family leases, child-seat allowance, resource sub-budget, renewal/expiry, output location and cancellation/recovery responsibility. Root reserves each child seat before creation; a pre-authorized manifest may contain finite placeholders resolved to actual IDs immediately after spawn. A lead may narrow, never widen, its grant. Required companions remain part of the assigned capability, not a reason for a second uncontrolled writer.

The global limit is100 **non-root agents** because the requested capacity is100 subagents. All direct leads and nested leaves count together; waiting leads, starting workers, workers with pending outputs and cancellation-pending workers remain counted until terminal state is confirmed. Example: four leads with six leaves each use28 seats, leaving72 for all other roles. This is capacity arithmetic, not a speedup forecast. Resource tickets are likewise subdivisions of one global budget; a child gets no fresh CPU/RAM/provider allowance.

A failed or expired parent loses permission to spawn. Root fences new overlapping assignments, reconciles surviving children, exact branches, pending effects and outputs, then explicitly cancels or reissues leases. Revocation alone does not stop a process or release its memory/write lock. Preserve unique work before reassignment; confirm terminal state before returning capacity.

Independent review is assigned outside the authoring lead's subtree, with access to the exact candidate and complete deciding outputs. A lead may summarize results but cannot hide negatives, upgrade a leaf's evidence, accept its own capability, close an original finding or integrate the programme branch. Root remains the sole integrator. A shared owner discovered by a child returns to root for lease reconciliation before writing.

Future procedure challenges: deny depth3, runtime-disallowed creation, per-lead quota multiplication, out-of-lease writes, parent-failure reassignment before confirmed stop, and sibling-leaf independent review. Preserve a permitted two-level assignment and its evidence chain. These are future execution checks, not runtime results from this documentation task.

The [source-reviewed conflict registry](conflict-groups.json) and [dispatch procedure](06-conflicts-and-dispatch.md) distinguish confirmed write collisions from references whose role remains to be assigned. Absence of a collision in this bounded registry is not a disjointness certificate.

The [scoped-readiness correction](07-scoped-readiness.md) governs early task release, per-edge interface agreements, completion joins and lease lifetime. A lead cannot use it to bypass unresolved shared ownership or protected-action permissions. Collapsed task-ID levels are not dispatch waves. A reviewer of a pinned candidate does not hold its author’s mutation lease.
