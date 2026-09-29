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

1. Enumerate the actual selected engine runners and their typed state inputs.
   Name the existing Foundry state-snapshot reader and the policy-slot mapping
   owner for each proposed engine. Do not flatten an arbitrary `GlobalState`
   into model variables or introduce a second world-growth writer.
2. At the N5 request owner, consume the verified WMR's
   `bound_state_snapshot_ref` through that Foundry reader on the runtime-supplied
   tenant-bound store. For one engine with an admitted typed mapping, bind the
   exact state field, source state hash, slot rule/version, and engine input in
   the run evidence. An engine without such a mapping retains a typed
   candidate limitation; ordinary no-acquisition candidate computation remains
   available on explicitly declared inputs. Any hashed DTO extension needs a
   schema bump and historical serializer.
3. Keep the canonical Data Forge overlay → passport → native-epoch admission
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
- The serving-scope owner must bind a refreshed context to the active job lease
  and authenticated tenant/cell. A context marker without a live scope check
  is insufficient. These premises are recorded in `OPEN_PREMISES.md` under
  OP-R13-N5-BOUND-STATE, OP-R13-ACQ, OP-R1-TIME, and OP-R13-SOURCE-UPDATE.

## Acceptance and falsifiers

- **Controlled positive:** two owner-produced WMR/Foundry state snapshots have
  different values at one declared engine slot while runtime hints and markers
  remain identical. The selected N5 engine input and persisted receipt change
  with the state, and a reader reopens the exact consumed bytes. Remove only
  the state-to-engine handoff while leaving WMR/receipt markers; this test must
  turn red. A no-acquisition candidate route remains usable.
- **Served acquisition positive, later:** one admitted physical row changes
  the S1 payload, DataSnapshot, Foundry state, refreshed context, and N5 engine
  input under a current tenant/job lease. Its output stays candidate-grade
  while time/unit/SKG authority is limited; no S8/N9/publication follows.
- **Negatives:** wrong physical row, same marker with changed payload bytes,
  stale job lease, and foreign tenant all refuse before an N5 input claims the
  changed state. A source with unsupported unit/time or no declared slot emits
  a typed limitation and does not masquerade as the USD slot.

The exact source/test write lease must be proposed and independently reviewed
before code changes. Likely owners include `runtime/quality/generation_cycle.py`,
`runtime/quality/joint_simulation_horizon.py`, the existing Foundry state reader,
`runtime/quality/data_state_substrate.py`, and
`runtime/quality/acquisition_world_growth.py`; these are a census target, not
permission to edit every file. Candidate tests belong in the mirrored unit
files and `tests/integration/core_runtime/test_acquisition_world_growth_chain.py`
and `test_acquisition_tenant_custody.py`. Four-base whole-file P41 and the
served removal probe are `UNRUN`. Use the existing linked read-only
`production_data`, `JAX_PLATFORMS=cpu`, a measured native-resource budget, and
the 8 GiB free-disk floor. No GY/Atlas plan or debt-register row is changed by
this task draft.
