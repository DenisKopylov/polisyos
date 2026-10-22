# Delta red-team: lineage and operations

**Scope:** contradiction-only review of the consolidated solutions/preferred-solutions.json and solutions/00-shared-decisions.md against prior findings RLO-01–RLO-08 and the assigned LIF-06–09 / OPS-01–12 rows. README.md was checked for the governing rebind and scope boundaries. No product acceptance is claimed; E02 remains explicitly not_established_by_this_documentation, and product execution remains UNRUN. No tests, builds, imports, installs, production reads, or broad research were performed.

**Result:** all eight prior redlines are addressed in the consolidated text; I found no remaining contradiction across the 16 assigned rows. The residual inputs below are genuine deployment/source/provider facts, not reasons to block unrelated preparation or to claim a property that has not been demonstrated.

## Prior findings

### RLO-01 — HIGH — LIF-06, OPS-08 — Canonical resource owner

**Exact anchors:** preferred-solutions.json#/tasks[task_id=LIF-06]/preferred_solution (“LIF-06 owns the single shared admission contract and minimal native mechanism”; at rebind it extends the accepted E02 owner or receives the smallest typed extension); #/tasks[task_id=LIF-06]/implementation_steps[1]; #/tasks[task_id=OPS-08]/preferred_solution (“Consume the single LIF-06 native admission contract”); shared decisions §S07.

**Delta reasoning:** This removes the prior ownerless seam. LIF-06 is the canonical admission-contract/mechanism task; OPS-08 qualifies selected host adapters. LIF-06 does not claim cross-process enforcement is already implemented, and its deviation trigger limits refusal to work depending on an unproved aggregate cap. That preserves scoped progress.

**Correction:** None beyond keeping this exact owner split at rebind; do not mark a multi-process cap satisfied before OPS-08's selected-profile witness.

**Genuine external input:** Exact host process placement and available enforcement controls. Their absence limits that profile's aggregate-cap claim; it does not make assignment of the missing code an external blocker.

### RLO-02 — HIGH — LIF-06, OPS-08 — Physical custody/control reserve

**Exact anchors:** preferred-solutions.json#/tasks[task_id=LIF-06]/implementation_steps[3,6], /acceptance_discriminators[5]; #/tasks[task_id=OPS-08]/implementation_steps[4], /acceptance_discriminators[0]; shared decisions §S07.

**Delta reasoning:** The reserve is now a physical process-group/bulk-limit plus scratch-quota property, not a permit marker. The plan separates pre-exhaustion shedding from OOM containment and requires native-allocation/spill saturation while terminal writes and recovery run. It leaves the hard-bound claim unavailable if the selected host cannot preserve the reserve.

**Correction:** None; retain the real saturation/recovery witness and avoid treating memory.high, memory.max, or a ledger entry alone as graceful reserve enforcement.

**Genuine external input:** Host owner confirms actual cgroup/platform hierarchy, process membership, storage quota and selected topology; measured workload determines the headroom. This does not transfer resource-owner allocation to an institution.

### RLO-03 — MEDIUM — OPS-04, OPS-05 — Complete retained-reader denominator

**Exact anchors:** preferred-solutions.json#/tasks[task_id=OPS-04]/implementation_steps[3]; #/tasks[task_id=OPS-05]/implementation_steps[0], /acceptance_discriminators[0].

**Delta reasoning:** Both rows expressly make N-1 insufficient as the denominator and require the complete affected supported reader/writer/schema/rule/backend directions. OPS-04 limits mixed-version qualification to independently rolling API/worker profiles; the atomic same-host profile gains no incidental rolling-upgrade barrier. This matches R12-07 without making a sample or N-1 pair stand in for the retained set.

**Correction:** None; at rebind derive the actual retained set and justify any equivalence classes.

**Genuine external input:** Operators/native owners identify supported offline readers, retained semantic versions and backup/restore windows.

### RLO-04 — MEDIUM — OPS-07 — One provider-budget owner

**Exact anchors:** preferred-solutions.json#/tasks[task_id=OPS-07]/preferred_solution, /implementation_steps[1-3].

**Delta reasoning:** The row now branches on the accepted E02 source: extend its monetary/budget owner if its scope covers provider-principal reservations; otherwise OPS-07 owns one minimal extension. ControlPlaneStore holds attempt references, not duplicate budget authority. This resolves the previous unpinned “existing owner” assumption without prematurely declaring either E02 topology.

**Correction:** None; bind the selected branch to the re-read accepted source at rebind.

**Genuine external input:** Provider billing principal, usage/charge denominator, price/window rules and exact endpoint idempotency/reconciliation. The plan explicitly avoids an account-wide hard-cap claim if metering is incomplete.

### RLO-05 — MEDIUM — OPS-10 — Remote adapter activation and scale

**Exact anchors:** preferred-solutions.json#/tasks[task_id=OPS-10]/preferred_solution, /implementation_steps[0], /deviation_triggers[0-1]; shared decisions §S12.

**Delta reasoning:** Adapter implementation/conformance, deployment activation and replica sizing are separated. Custody, institutional topology, operability and availability can justify a selected remote profile without exhausting vertical capacity; a scale-specific choice still needs measured workload evidence. The deviation trigger prohibits a compulsory capacity-exhaustion gate for non-capacity objectives.

**Correction:** None; keep exact provider/config conformance separate from permission to deploy and from replica sizing.

**Genuine external input:** Institution/provider owner supplies the chosen backend, IAM/lifecycle/restore semantics and actual custody, service or failure-domain objective.

### RLO-06 — MEDIUM — OPS-02, OPS-08 — Profile-scoped concurrency

**Exact anchors:** preferred-solutions.json#/tasks[task_id=OPS-02]/preferred_solution; #/tasks[task_id=OPS-08]/preferred_solution, /implementation_steps[0-1], /deviation_triggers[0]; shared decisions §§S07, S12.

**Delta reasoning:** One worker is explicitly the initial unmeasured rehearsal-profile setting. A different commissioned, measured profile may raise concurrency in bounded steps with aggregate admission and the protected reserve intact. Unmeasured classes remain unadmitted only for work requiring the unproved bound; this is not a product-wide serialization invariant.

**Correction:** None; preserve the explicit profile boundary when dispatching and commissioning.

**Genuine external input:** The operator selects the workload/service envelope; host/provider owners supply capacity and quota evidence.

### RLO-07 — MEDIUM — LIF-07 — Source currentness vs captured-generation identity

**Exact anchors:** preferred-solutions.json#/tasks[task_id=LIF-07]/implementation_steps[2-3], /acceptance_discriminators[4]; shared decisions §S04.

**Delta reasoning:** A cache key remains candidate identity only; a consuming boundary separately resolves current-use validity. The same-locator revision/withdrawal with delayed-feed adversary must not yield an unjustified current claim. S04 supplies the time/cut rule: bind source cut and relevant generations; if a complete change feed is unavailable, state bounded freshness/cutoff and do not treat polling as proof of no change. This is consistent with historical/as-of use and does not require currentness for every historical claim.

**Correction:** None; retain an explicit as-of/limited result when the source cannot provide currentness evidence. Do not infer currentness from payload hash or cache identity.

**Genuine external input:** Source issuer/CAP owner supplies revision, correction/withdrawal, cut and feed semantics. The residual freshness guarantee is only as strong as those supplied facts.

### RLO-08 — LOW — OPS-10 — Conditional writes bound to the actual API operation

**Exact anchors:** preferred-solutions.json#/tasks[task_id=OPS-10]/deviation_triggers[1] (“Bind conditional-write guarantees to the exact provider API operation and multipart route”; the GCS XML multipart example); /implementation_steps[3], /acceptance_discriminators[0-1].

**Delta reasoning:** Although the preferred-solution summary names provider preconditions generically, the task's operative deviation and conformance conditions bind them to the selected API and upload route, demand a supported route or a separately proved owner-head protocol, and exercise the exact configuration. No generic provider-level label is accepted as proof. This is sufficient and does not conflict with the summary.

**Correction:** None; preserve the route-level qualification as a required part of adapter selection and acceptance.

**Genuine external input:** Selected provider/client API, upload mode, bucket/prefix, IAM and lifecycle/versioning settings.

## Cross-row contradiction check

LIF-07 still distinguishes computational lineage from causal/scientific independence and limits independence analysis to claims that rely on it. LIF-08 preserves separate source cuts unless producers establish a common cut. LIF-09 remains a frozen FINAL-REPLAY composition/completion join rather than a start barrier. OPS-05 pins the actual mount/backup topology; OPS-06/07/09 retain actor, tenant/cell, source permission, credential and provider-principal distinctions. Shared decisions §S13 explicitly preserves scoped rebind, independent preparation and final completion joins. I found no new cross-row hard dependency or authority/tenancy contradiction in LIF-06–09 / OPS-01–12.

**Disposition:** Delta resolves the prior eight planning redlines. This is not product implementation evidence, E02 acceptance, or closure of the original task criteria.
