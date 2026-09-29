# R13 / B12 — bind selected world state to the N5 engine input

Status: scoped engineering task and owner-decision inventory, **not** an accepted
world-growth capability or a new finding. This is the existing R13
selected-row-to-N5 class one level deeper (P40). Source-path review:
`/Users/deniskopylov/.codex/scratch/e02-r13-n5-owner-seam-review-20260930/REVIEW.md@sha256:dc8cd758e8a5e867518b02145d549b9185c0d75f999db8c2cd13ab8b1b5fd390`.

## Property and current divergence

An acquired observation can affect N5 only if Data Forge's exact admitted row
changes the `DataSnapshot.data_ref` payload, Foundry binds that payload into a
state snapshot, and the selected N5 engine actually reads the corresponding
state/slot under the same tenant and cycle context. Matching artifact IDs alone
are insufficient. The production caller is the served WDI acquisition port
through `AcquisitionWorldGrowthBridge.resume` and
`GenerationCycleController.reenter_after_active_acquisition_overlay` to
`JointSimulationPort._build_joint_simulation_request` and the N5 horizon.

Today re-entry offers the projection to N8 and retains the previous N5 context.
The candidate DataSnapshot retains the baseline `data_ref`. The N5 request
builder checks a WMR, discards `consume_world_model_record_for_simulation`'s
resolved refs, and takes numeric state from `runtime_hints`; the horizon uses
the resolved WMR only for identity/diagnostics. Varying a hint while preserving
the WMR can change N5's numerical input. This is the P38 divergent case.

## Owner-first work that can proceed now

1. Use the existing N5 `program_graph` runner as the first controlled engine.
   It already calls Foundry's `execute_program_graph` for each horizon step.
   Resolve the WMR's exact `bound_state_snapshot_ref` through Foundry's
   `load_state_snapshot` on N5's injected tenant-bound `ArtifactStore`. Supply
   that state as `program_base_state` and its typed `StateSnapshotRef` as
   `program_base_ref`; do not accept a caller-supplied state or store in their
   place. `WorldModelSimulationInput.to_execute_request` and Foundry's public
   `execute` own whole-plan execution, but they are not drop-in replacements
   for this N5 horizon loop.
2. Require `program_graph_ref` in the WMR's
   `simulation_model_ref.program_graph_refs`, load the `ExecPlan` through the
   injected store, verify its `program_ref` matches that graph, and resolve
   registry/runtime objects through WMR-bound Foundry owners. The WMR v1 has
   no `exec_plan_ref`: graph association does not establish the plan's order
   or provenance. Persist `exec_plan_provenance=not_established` as a typed
   candidate limitation and prevent N9, S8 and publication from treating this
   run as authority. A foreign graph or tenant must refuse; an unresolvable
   plan cannot run. Hold the exact plan fixed across the
   two-state numerical probe. The controlled fixture must establish that every
   WMR input uses a selector-free primary CAS view *before* WMR v1 reduces its
   refs to bare IDs. WMR v1 cannot replay an
   `ArtifactRef.manifest_profile_sha256` selected view. Multi-view source
   custody stays in the existing R9/P07 residual and cannot gain authority
   through this slice. Do not use caller hint objects to claim WMR plan
   authority. Keep the ordinary no-acquisition candidate path on its
   explicitly declared inputs. Owner-bound plan issuance is a separate
   capability/decision, with a versioned WMR transition if it adds a field.
3. Persist the actual consumption in the content-bound N5 result: typed state
   snapshot wrapper ref, loaded state blob hash, graph/plan identities, and
   the typed `PolicySlotBinding` state path with the WMR's `state_slot_digest` relevant
   to the observed output. The binding DTO has no independent rule-version
   field today; any rule-version requirement remains an explicit owner premise.
   New writes require a bumped result version; v1 artifacts must dispatch to
   a historical DTO and receipt projection preserving their original payload
   semantics and bytes. A marker-only receipt does not establish that the
   engine used the state. Other N5 engines need their own owner-approved
   typed state mappings before they may claim WMR consumption; do not flatten
   arbitrary `GlobalState` into NCM evidence or system-dynamics stocks.
4. Keep the canonical Data Forge overlay → passport → native-epoch admission
   as the only world-growth path. Once a source-approved row-to-state rule
   exists, have the DataState/S1 owner emit new payload bytes behind
   `DataSnapshot.data_ref`, then call existing WMR/Foundry binding owners. The
   served resume owner must persist and re-resolve a refreshed problem-bound
   context under a live tenant/job/worker/attempt lease. No root-rebuilt CAS or
   caller-stamped SKG prior is admissible.

The controlled-profile N5 state-consumption slice may be implemented and
reviewed independently of the current WDI source mapping. It must be labeled
as that bounded engineering result, not as proof that WDI changed the world.

## Decisions and data that remain separate

- The selected WDI row is `government.balance`, 2024, `percent_gdp`, value
  `-17.1`; the existing `government.balance` state slot is a USD stock and the
  DataState WMR scope defaults through 2023-07. The data/slot owner must supply
  a conversion or a separate typed slot, a time/grain rule, and source-vintage
  semantics. Copying `-17.1` into the USD slot is forbidden.
- The SKG owner must establish whether its prior was derived from the changed
  snapshot, or carry an explicit unchanged-prior limitation. Copying a new
  snapshot ID onto the old prior is not derivation evidence.
- The WMR/Foundry plan owner must bind an exact `ExecPlanRef` and its execution
  order to the graph and registry before an authority-grade N5 claim can use
  this route. WMR v1 records only graph refs and the registry bundle; the
  controlled slice therefore remains candidate-grade with explicit plan
  provenance `not_established`.
- The core CAS/WMR owners must carry a selected manifest-view identity through
  persisted references before this route may claim multi-view replay. The
  current WMR v1 bare IDs do not establish it (existing R9/P07 class).
- The serving-scope owner must bind a refreshed context to the active job lease
  and authenticated tenant/cell. A context marker without a live scope check
  is insufficient. These premises are recorded in `OPEN_PREMISES.md` under
  OP-R13-N5-BOUND-STATE, OP-R13-ACQ, OP-R1-TIME, and OP-R13-SOURCE-UPDATE.

## Acceptance and falsifiers

- **Controlled positive:** two owner-produced WMR/Foundry state snapshots have
  different values at one declared `program_graph` slot while runtime hints,
  graph, exact loaded plan and markers remain identical. The actual Foundry runner receives
  the changed `base_state`, its numerical N5 output changes, and a reader
  reopens the content-bound consumption receipt with the typed plan limitation.
  Remove only the state-to-engine
  handoff while leaving WMR/receipt markers; this test must turn red. A
  no-acquisition candidate route remains usable.
- **Served acquisition positive, later:** one admitted physical row changes
  the S1 payload, DataSnapshot, Foundry state, refreshed context, and N5 engine
  input under a current tenant/job lease. Its output stays candidate-grade
  while time/unit/SKG authority is limited; no S8/N9/publication follows.
- **Negatives:** wrong physical row, same marker with changed payload bytes,
  stale job lease, and foreign tenant all refuse before an N5 input claims the
  changed state. A source with unsupported unit/time or no declared slot emits
  a typed limitation and does not masquerade as the USD slot.

The exact source/test write lease must be independently reviewed before code
changes. The first lease should cover N5 request construction in
`runtime/quality/generation_cycle.py`, the Foundry snapshot/plan/registry
readers and `execute_program_graph` write path needed to accept the injected
`ArtifactStore` without unwrapping or rebuilding it, and N5's existing
`runtime/quality/joint_simulation_horizon.py` runner and versioned result
reader/persistence, and mirrored controlled-profile tests. DataState, WDI,
SKG, and served lease refresh are a separate follow-on after their owner
contracts are known. The served acquisition tests belong in
`tests/integration/core_runtime/test_acquisition_world_growth_chain.py` and
`test_acquisition_tenant_custody.py`; they cannot be claimed by the controlled
slice. Four-base whole-file P41 and the removal probe are `UNRUN`. Use the existing linked read-only
`production_data`, `JAX_PLATFORMS=cpu`, a measured native-resource budget, and
the 8 GiB free-disk floor. No GY/Atlas plan or debt-register row is changed by
this task draft.
