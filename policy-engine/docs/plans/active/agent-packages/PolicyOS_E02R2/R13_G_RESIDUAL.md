# R13-G — composed WMR / NCM store continuity

Status: **partial; bounded R13/P40 residual**. No mechanism change is proposed
from this candidate worktree. R13-D closes the N5/N8 leaf-result store path;
R13 as a whole remains open.

## Property

When N5 selects an NCM from a world-model record, the world-model producer and
NCM reader must use the exact tenant-bound store supplied by the runtime, and
the record must identify the exact selected manifest view. A missing owner NCM
must remain an explicit typed limitation. It must not block ordinary N4
candidate computation or be replaced by a model inferred from the candidate's
language.

## What exists at this head

The served control lifecycle already carries the right store owner: the runtime
container constructs `PromotionRuntime` with `runtime_api_context.store`, and
`ControlPlaneService.compile_and_run_recursive_generation_cycle` passes that
runtime into the HTTP generation-cycle composition. But
`_build_cycle_substrate_context_from_owner` receives only `repo_root`; the
composed-world-model owner then creates a new `FileSystemCAS` beneath that root.
The NCM consumer independently reconstructs the same local CAS. The two paths
therefore agree only when their filesystem roots happen to resolve alike.

The owner also caches by repository root alone (`lru_cache(maxsize=4)`). Its
workspace is shared at `.tmp/gy-s-composed-wmr-world`; the data-state builder
writes `fabric-world.duckdb` and a `fabric-world` snapshot there. Neither cache
key nor workspace binds the active tenant/cell, selected scope profile, or
current data epoch. A per-request temporary workspace cannot simply be deleted
after the build because `FabricWorldRef.snapshot_root` is persisted in the
WMR.

The NCM half has no production writer to connect. A complete tracked-source
walk of `policy-engine/src/polisyos` covered 2,905 tracked paths, including
2,695 Python files. The census found two `NCMSpec(` spellings (the class
declaration and one construction in `_twin_network_from_ncm`, which transforms
an already-existing model), one `persist_ncm_spec(` spelling (its definition,
with zero source callers), and one data-state WMR builder call (the definition
plus its call from the composed-WMR owner). That call omits `ncm_refs`, so the
served record has no NCM reference and N5 returns
`joint_simulation_ncm_spec_missing` for the NCM resource. The existing
`NCMEngineMethod` consumes an `NCMQueryData.ncm_spec`; it does not produce the
owner model.

The reference contract cannot preserve a selected view today. Core
`ArtifactRef` carries `manifest_profile_sha256`; IR `NCMSpecRef` carries only
`artifact_id`, `kind`, and `media_type`; and `SimulationModelRef.ncm_refs` is a
tuple of strings. Extending that hashed WMR shape requires a schema-version
bump and a historical serializer that keeps prior WMR projections byte-exact.

The source census was produced by walking the complete output of
`git ls-files -z -- policy-engine/src/polisyos` and counting matches in every
tracked `.py` file.
The earlier AST census and producer/reader trace are in
`/Users/deniskopylov/.codex/scratch/e02-r13-d-exact-store-20260926/R13G_NCM_OWNER_ATOMIC_MOVE.md@sha256:79e89a93c6683546fb5ef4a3352cdb2ccfb800d1bb8d76fcbb97bdd64f89188c`.

## Why this remains one residual

Changing only `_resolve_joint_simulation_ncm` would leave the WMR writer's
references in the old local CAS. Changing only the writer would leave N5
reopening a different store. Injecting a store into both while retaining the
root-only cache still permits a record built for another tenant or data epoch
to be reused. Removing that cache and choosing a short-lived workspace without
persisting the Fabric snapshot would make later WMR replay depend on a vanished
path. Finally, a hand-constructed NCM fixture can test persistence mechanics,
but it cannot stand in for a production owner that derives and admits an NCM
against the selected world.

These are parts of one producer → artifact → reader custody chain, not separate
sites to patch one at a time. The smallest missing capability is an
owner-bound composed-WMR/NCM admission path: it accepts the runtime store and
authenticated tenant/cell plus an owner-issued scope/epoch; persists the
selected NCM view and world snapshot through that store; and gives the consumer
the same exact selected reference. The repository has the WMR builder and NCM
consumer, but the NCM producer and that complete bridge are `producer_missing`
and `bridge_missing`.

## P37 / P38

- **P37:** the runtime container supplies `PromotionRuntime.store`, and the
  N5 controller checks store object identity. The WMR cache identity, current
  tenant/cell, scope profile, data epoch, and selected NCM manifest are
  `not_established` at this owner boundary. A root path or a SHA-shaped string
  is not the owner predicate.
- **P38:** the property is that N5 consumes the exact owner-admitted NCM view
  from the current runtime scope. The implementation instead opens a
  root-reconstructed `FileSystemCAS` and loads by artifact ID. A divergent case
  is the same root path behind two guarded store instances, or two manifest
  views over identical bytes: path equality and blob identity still agree while
  tenant custody or the selected typed view differs.

The current absence remains a typed N5 result, not a positive NCM capability.
R13-D's three-tenant served N4 candidate control passed at its recorded head;
that is evidence that the ordinary candidate route is available, but it does
not test this WMR/NCM producer-reader chain:
`R13_D_REPAIR.md@sha256:a1732cef53ed18822ca898e89495c76222da6698000778774b6ad6f29cbaa855`.

## Direction and closure signal

This residual follows owner-first placement (P27), class-level repair (P31),
and exact evidence over markers (P32). GY §3.5.6 requires deriving bindings
through the real owner; §3.5.7 requires content-bound cache identity and reuse
without stale hits; GY-N13b and Atlas DS15 keep acquired data on the canonical
overlay/passport/epoch route. Atlas surfaces consume runtime truth; this
internal residual does not authorize a new surface or a register closure.

Close R13-G only after an independent served witness proves all of these
properties together: WMR and NCM writes use the exact runtime store; N5 reads
the selected manifest view from that same store; a foreign tenant/store is
denied; absent NCM remains typed while N4 candidate work still proceeds; the
workspace and cache separate tenant/scope/epoch and preserve replay; and a
marker-retaining removal probe turns the witness red. Until an owner-produced
NCM and versioned reference exist, report the NCM positive path as
`UNRUN`/`producer_missing` rather than manufacturing one in a fixture.

This residual does not replace or resolve the R13 principal decision draft in
`DECISION_RECORDS.md`.

## Evidence references

- Current R13-D implementation: `generation_cycle.py@sha256:a40239a067ade9336b0edec3fbbe2ee3c09223cb42031bea39900b60385a1c42`;
  its NCM reader still reconstructs `.tmp/gy-s-composed-wmr-cas`.
- Composed WMR owner: `intervention_substrate.py@sha256:1783a4ecfd67e0010e4e4ccc5c19a022da5786e517c70f356cd5f639cbc726df`.
- Data-state builder/workspace: `data_state_substrate.py@sha256:b29a8cab49c2a01312b27246cebc88829dbf1f0fa3e80f38bb13b76c0de80de4`.
- Hashed WMR contract: `world_model_record.py@sha256:de9aab34f6afc17d2db695f22f86952c5494a5307da08f9e2216a8df92f1e823`;
  `pdc/_impl/world_model_record.py@sha256:87d742058b0aa5dd857bc1d25f524ff235263e74cc46022ffbe5f92f674a1c69`.
- NCM persistence/ref contracts: `ir/analytics/ncm.py@sha256:db8a83e3b4767005cdc210ca25f434cd4bdbbc582567100d2cb132a5c81f0aab`;
  `ir/registry/refs.py@sha256:4135199d208ea8970114df0d53a45b92f4e880b32451387a59de43be4987ed19`.
- GY plan: `GY-engine-subordination.md@sha256:5d06f4cc55541fb28030ec4f6c75f2a10537df53c60f792df84de118d0aeb4c5`;
  Atlas master: `POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md@sha256:35c1b64c91aa4209cffed4aed42d89258e5f975afab44464f201111ba0b4d725`;
  DS15: `DS15-acquisition-routes.md@sha256:5402b3e403ddf070a66969ebe2fa7244fd05df7e50a232bc2c4da6927b564b33`;
  failure/repair register: `policy-design-case-failure-patterns.md@sha256:64f9fa40453980d9128443ee34a4bf3298b71c157a5ebcc3bd6cb786abeb090a`.

No code or test file changed in this bounded residual. No new JUnit was
produced; the existing R13-D focused and served-candidate JUnits remain the
only test receipts cited above.
