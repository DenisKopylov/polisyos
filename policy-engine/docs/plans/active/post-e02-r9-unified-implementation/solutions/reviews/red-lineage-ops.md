# Independent red-team: lineage and operations proposals

**Scope:** R13 planning artifacts only; `LIF-06`–`LIF-09` and `OPS-01`–`OPS-12` (16 task rows). Read the root instructions, R13 brief, original `tasks.json`, shared decisions, and solution README. No product code, tests, builds, installs, production data, or E02 acceptance was inspected or claimed. Planning source is the R13 brief's `dc075e7…` pin; the accepted E02 tree remains not established and all findings below require task-scoped rebind before implementation.

**Coverage:** All 16 assigned rows were reviewed. The findings below are the plan-level redlines; the other rows had no additional concrete redline after checking their stated owner, external-input and profile boundaries.

## Findings

### RLO-01 — HIGH — LIF-06, OPS-08 — Resource owner is left unallocated across a dependent task boundary

**Anchor:** `lineage-proposal.json#/task_solutions[task_id=LIF-06].preferred_solution` and `.implementation_steps[1]` (“no cross-process pool … if W0 cannot name … mark absent/unallocated”); `ops-proposal.json#/task_solutions[task_id=OPS-08].preferred_solution` and `.implementation_steps[1]`; original `tasks.json#LIF-06.owner_paths` and `#OPS-08.owner_paths`; `operations/01-deployment.md` “Resource isolation and cost”.

**Counterexample:** W0 finds no current shared admission owner. LIF-06 is left `absent/unallocated`, while OPS-08 (which depends on LIF-06) is the task proposing `runtime/resources/admission.py` and a shared cross-process owner. A multi-process accepted profile can then have no assigned task that closes the shared bound, or LIF-06 can be treated as complete using only local estimates before OPS-08 supplies the owner. The original LIF-06 deliverable already assigns terminal fan-in, native/IPC resources, nested-child admission and refusal behavior; the operations source says a shared cross-process owner is needed before claiming a global cap.

**Bucket:** Same class one level deeper: `P01` (capability owner left absent), exposed by the `P02` task-stage seam; do not relabel this an external authority question.

**Correction:** At scoped rebind, appoint one canonical resource-admission owner and define its native contract. Either LIF-06 owns the minimal owner and OPS-08 adds the selected host enforcement adapter, or OPS-08 owns the shared mechanism and LIF-06's interface/owner-local work is staged so its acceptance does not claim a global bound before that mechanism exists. Keep the actual multi-process reserve/overload consumer result as a required completion witness whenever the selected profile uses multiple processes. A missing implementation/bridge is engineering, not a reason to wait for a new institutional appointment.

**Genuine external input:** The selected host/platform owner must identify available enforcement and process-placement controls. If those controls cannot enforce the selected profile, scope only that profile's global-cap claim to `not_established` and deny work that relies on it.

### RLO-02 — HIGH — LIF-06, OPS-08 — A permit ledger does not itself preserve physical control capacity

**Anchor:** `lineage-proposal.json#/task_solutions[task_id=LIF-06].implementation_steps[3-6]`, `.composition_contracts[1]`, `.acceptance_discriminators[0]`; `ops-proposal.json#/task_solutions[task_id=OPS-08].preferred_solution`, `.implementation_steps[1-3]`, `.acceptance_discriminators[0]`.

**Counterexample:** Bulk/native work and the API/control-store/restore path share one host memory group. The shared store says the terminal reserve is untouched, but concurrent native allocations or spill-related buffers consume the remaining host budget. Linux `memory.high` throttles/reclaims but may be breached; `memory.max` is a hard cgroup boundary whose failure mode can be OOM killing, and usage may temporarily exceed it. If the control writer shares the bulk cgroup, the “reserved” transition may be the process killed at the point where it is needed. A durable permit or the word “reserve” does not create OS-held headroom.

**Bucket:** Same class one level deeper: `P38` proxy gate (reservation state standing in for physically protected capacity).

**Correction:** Keep one admission owner, but define the reserve property against the selected platform's actual process groups and scratch quota. Demonstrate either a separately protected control/custody/restore group or a hard bulk limit that leaves measured control headroom; distinguish graceful `memory.high` load shedding from `memory.max` containment/OOM. Saturate native RSS and scratch/spill while terminal transitions and recovery run; the fresh consumer must see persisted defer/refusal/unknown as appropriate, never inferred success from an issued permit. If the host cannot protect the reserve, record that bounded limitation and refuse protected work that needs it. Do not promise one universal mechanism for every OS/profile.

**Primary source checked:** The [Linux kernel cgroup v2 documentation](https://docs.kernel.org/7.0/admin-guide/cgroup-v2.html) says cgroup memory tracking is “not completely water-tight”; `memory.high` is best-effort throttling and may be breached, while `memory.max` invokes cgroup OOM handling and may be exceeded temporarily. Those semantics support the counterexample; they do not prove any selected PolicyOS host has the needed placement or reserve.

**Genuine external input:** Host owner confirms effective cgroup/platform hierarchy, limits, process membership and filesystem/project quota on the exact deployment. Provider account ceilings remain separately supplied/reconciled inputs.

### RLO-03 — MEDIUM — OPS-04, OPS-05 — “N-1” is a migration floor, not the retained-reader acceptance denominator

**Anchor:** `ops-proposal.json#/task_solutions[task_id=OPS-04].implementation_steps[3]` and `#/task_solutions[task_id=OPS-05].preferred_solution` / `.implementation_steps[0]`; original `tasks.json#OPS-05.deliverable`; `assurance/self-review-r12.md#R12-07`; `architecture/01-integration-boundaries.md` retained-schema cutover paragraph.

**Counterexample:** The plan tests the immediately previous API/worker reader and labels migration compatible, while a still-supported offline reader or another retained rule/schema generation interprets a required facet differently. This is exactly the R12-07 counterexample: one old/new/incompatible sample (or one N-1 pair) does not cover all retained versions and supported directions.

**Bucket:** Same class one level deeper: `P07` (version/replay coverage represented by a convenient N-1 proxy).

**Correction:** State that N-1 is the minimum rolling-upgrade gate only. Derive the composed matrix from the complete affected retained reader/writer/schema/rule/facet/backend denominator, cover every distinct supported direction and claimed unsupported-required-semantics refusal, and justify any equivalence-class witness. For OPS-04, require mixed-version compatibility only for a profile that actually rolls API and worker independently; an atomic single-host pair does not gain a new start prerequisite merely from the example.

**Genuine external input:** Operators identify supported old/offline reader versions and backup/restore windows; native owners decide which version/semantic classes remain supported.

### RLO-04 — MEDIUM — OPS-07 — Provider budget owner is assumed but not source-bound

**Anchor:** `ops-proposal.json#/task_solutions[task_id=OPS-07].preferred_solution` (“existing durable control/budget owner”) and `.reuse_anchors`; original `tasks.json#OPS-07.owner_paths` / `#OPS-07.requires_other_mechanisms`; `operations/01-deployment.md` “Secrets and provider spend”.

**Counterexample:** The only concrete reuse anchors named by the proposal are process-local tenant quota and the worker execution seam; neither establishes one durable account-principal reservation authority. The original task proposes `core/security/provider_budget.py`, while the proposal now says to place reservations in an “existing” owner without naming or pinning it. An implementation can therefore create a second counter beside an accepted E02 owner, or silently put monetary authority into the job store because it is durable.

**Bucket:** Same class one level deeper: `P27` owner-bypass/duplication risk; existence of an accepted E02 account-budget owner is **not established by these planning anchors**.

**Correction:** Rebind the accepted tree and name the canonical owner. If E02 already owns provider-principal reservations, extend it. If it does not, keep OPS-07's proposed typed owner as the single new account-budget mechanism; ControlPlaneStore may persist attempt references/events only under an explicit ownership contract. Do not turn unknown provider charges into zero or an account-wide cap.

**Genuine external input:** Provider billing owner supplies the principal, usage/charge denominator, price/window rules and endpoint idempotency/reconciliation semantics. Without those, retain only an approved per-operation ceiling and an explicit unknown account state.

### RLO-05 — MEDIUM — OPS-10 — Scale exhaustion is overused as the gate for remote-CAS work

**Anchor:** `ops-proposal.json#/task_solutions[task_id=OPS-10].preferred_solution`, `.implementation_steps[0]`, `.deviation_triggers`; original `tasks.json#OPS-10.title`, `.deliverable`, `.requires_other_mechanisms`.

**Counterexample:** A selected institution needs a remote cell for failure-domain, custody or operator-topology reasons while the single host still meets throughput/SLO targets. Requiring vertical capacity to be exhausted before even qualifying the remote CAS adapter blocks that profile for a condition unrelated to its reason for selection. The original task gates replica pools on justification, but its deliverable is adapter-specific tenant/cell and restore parity; the service-target miss is evidence for a chosen deployment, not an automatic substitute for completing or formally disposing the original adapter obligation.

**Bucket:** New class: production-tier activation is conflated with implementation/conformance and original-task disposition.

**Correction:** Separate (1) bounded adapter implementation/conformance for a selected remote profile, (2) permission to deploy/scale that profile, and (3) replica-pool sizing. Require a documented target miss for the particular objective being addressed; a failure-domain or institutional custody requirement need not be repaired by vertical scaling. If no remote profile/provider is selected and the original obligation is to be deferred, record the competent-owner disposition/human scope change instead of treating filesystem-only support as accepted closure.

**Genuine external input:** The institution/provider owner supplies the selected backend, identity/IAM, lifecycle/restore semantics and actual service, custody or failure-domain objective.

### RLO-06 — MEDIUM — OPS-02, OPS-08 — One-worker settings need an explicit profile boundary

**Anchor:** `ops-proposal.json#/task_solutions[task_id=OPS-02].preferred_solution` (“default to one active worker operation”) and `#/task_solutions[task_id=OPS-08].preferred_solution` / `.implementation_steps[0-1]` (“one active worker per measured resource class”); original `tasks.json#OPS-02.deliverable` and `#OPS-08.deliverable`.

**Counterexample:** A reader carries the safe first-pilot setting into a later commissioned local profile and serializes otherwise eligible independent work even after the profile has a measured aggregate bound and protected reserve. The source task asks for a finite local candidate journey; it does not impose one worker as a system-wide invariant. OPS-08 asks for measured classes and limits, not universal serialization.

**Bucket:** New class: profile-local bootstrap policy generalized into a product-wide concurrency rule.

**Correction:** Label one worker as the initial value for the named candidate-pilot profile only. Store concurrency as a commissioned profile ceiling, allow measured values above one when shared aggregate admission and terminal reserve pass, and keep per-tenant/provider quotas independent. Do not infer runtime capacity from agent/reviewer parallelism or make one-worker a permanent fallback for unmeasured profiles; those profiles remain unadmitted where the bound is required.

**Genuine external input:** Profile operator selects workload, target concurrency and service envelope; host/provider owners supply actual capacity and quota evidence.

### RLO-07 — MEDIUM — LIF-07 — A captured generation must not silently stand in for source currentness

**Anchor:** `lineage-proposal.json#/task_solutions[task_id=LIF-07].implementation_steps[1-3]`, `.composition_contracts[0-2]`, `.acceptance_discriminators[0-1]`; original `tasks.json#LIF-07.deliverable` / `.adversarial`.

**Counterexample:** A cached derivative binds the old immutable capture and its manifest hash correctly, but the source revises or withdraws the record under the same stable locator/alias and its correction feed is absent or lagging. A fresh reader that checks only the captured artifact/model/rule generation and current rights can reuse historically correct bytes for a claim that is presented as current.

**Bucket:** Same class one level deeper: `P08` (captured generation can be mistaken for the current-source time/cut).

**Correction:** For current-use claims, bind the source-issued revision/cut or the actual CAP/LIF-02 event high-water and its time role into derivative validity; falsify with same-ID source correction/withdrawal and a delayed or missing event. If no source-currentness feed exists, keep the derivative available as historical/as-of evidence but project currentness as limited/stale. Do not require current-source checks for a claim explicitly limited to immutable historical content.

**Genuine external input:** Source issuer/CAP owner provides revision, correction/withdrawal and cut semantics. Those facts cannot be synthesized from the cached artifact hash.

### RLO-08 — LOW — OPS-10 — Provider preconditions are API-operation specific

**Anchor:** `ops-proposal.json#/task_solutions[task_id=OPS-10].preferred_solution` and `.implementation_steps[1-3]`; source `R13-OPS-GCS-CAS`.

**Counterexample:** A GCS adapter uses the XML API multipart route and claims generation-precondition protection for that write path. Google’s request-preconditions documentation states that preconditions cannot be used in XML API multipart uploads. A generic “GCS supports preconditions” result would not prove the actual adapter operation's CAS property.

**Bucket:** Same class one level deeper: `P37` (the declared predicate “provider supports conditional writes” is not yet frozen to the selected operation); keep this subordinate to OPS-10's exact-adapter conformance, not a separate provider platform project.

**Correction:** Bind the API and multipart route in the selected adapter profile. Use a route that supports the required precondition, or refuse to claim conditional-CAS semantics for the unsupported route; retain the existing unambiguous/versioned-owner fallback only if its own consumer property is proved. Run the race/retry test on the actual route.

**Primary source checked:** [Google Cloud Storage request preconditions](https://docs.cloud.google.com/storage/docs/request-preconditions) explicitly says preconditions cannot be used in XML API multipart uploads; [Amazon S3 conditional writes](https://docs.aws.amazon.com/us_en/AmazonS3/latest/userguide/conditional-writes.html) documents operation-specific 409/404/412 behavior for multipart completion and concurrent deletion.

**Genuine external input:** Chosen provider, client API/endpoint, upload mode, IAM and versioning/lifecycle configuration.

## Required boundaries preserved

- No finding here changes the brief's E02 start gate or says E02 was accepted. Every task's actual-accepted-source rebind remains required.
- R12 scoped progress/completion joins remain: disjoint work can proceed after its own rebind; actual producer/consumer witnesses remain required at composition; LIF-09 is a FINAL-REPLAY completion join, not a barrier to independent shards. See `execution/07-scoped-readiness.md` §§ “A complete affected scope” and “Wave start and completion are different dependencies”.
- The proposal correctly states that computational lineage does not prove causal/scientific independence (`LIF-07`); the independence check is claim-scoped. OPS-06/07/09 separate object/source rights, actor/recipient, credentials and billing identity; OPS-05 pins mount semantics; these boundaries should remain intact.
- External checks confirmed the cited SQLite WAL same-host/network-filesystem restriction and Online Backup snapshot behavior ([SQLite WAL](https://www.sqlite.org/wal.html), [SQLite Online Backup API](https://www.sqlite.org/backup.html)); TUF's root rotation requires old/new root thresholds and sequential root version, while threshold compromise requires out-of-band root recovery ([TUF v1.0.37](https://theupdateframework.github.io/specification/v1.0.37/index.html)); and the OpenTelemetry overflow caveat is accurate ([OpenTelemetry metrics](https://opentelemetry.io/docs/concepts/signals/metrics/)). None of those sources proves PolicyOS deployment conformance.

**Conclusion:** These are planning-level redlines, not product findings, fixes, or acceptance. Close only against a source-bound plan delta with exact owner assignment, profile-scoped resource predicates, full retained-reader denominator, and genuine external inputs; leave unmeasured profile claims `not_established`.
