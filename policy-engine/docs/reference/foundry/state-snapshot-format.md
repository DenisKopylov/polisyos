# Foundry StateSnapshot persistence formats

Owner: Core contract and Foundry persistence owners.
Source of truth: `src/polisyos/core/contracts/foundry.py` (`StateSnapshot`), `src/polisyos/foundry/execute/_internal/snapshots/__init__.py`, `tests/unit/foundry/runtime/test_method_metric_capture.py`, and `tests/unit/foundry/runtime/test_executor_snapshots.py`.

`StateSnapshot` is a Core-persisted DTO, with a `StateSnapshotRef` pointing to
its JSON wrapper and an NPZ state blob. Its payload version and artifact
manifest schema version are paired by the version registry on
`polisyos.core.contracts.foundry.StateSnapshot`.

| Payload version | Manifest schema | Persisted meaning | Reader boundary |
| --- | --- | --- | --- |
| `2.0` | `1.0` | Legacy wrapper whose lineage is taken from the manifest sidecar. | Legacy GlobalState loader. |
| `2.1` | `2.1.0` | Historical bare state-blob lineage. | Legacy GlobalState loader and selected-profile compatibility paths. |
| `2.2` | `2.2.0` | Selected state-blob view for full GlobalState snapshots. | GlobalState loader, N5, calibration, and simulation-state consumers. |
| `2.3` | `2.3.0` | Sparse, named method-input slot arrays. Requires the explicit `method_input_slots` layout. | Bounded method-input reader and its Scientist law consumer. It cannot be reconstructed as GlobalState. |

The generic snapshot writer keeps full dataclass states on the existing `2.2`
wire format. A layout-less `2.2` wrapper can still be a historical method-input
capture or a full state; the artifact alone cannot distinguish those meanings,
so the bounded method-input reader refuses it. Only newly persisted captures
with the explicit `2.3` layout qualify for that reader. The `layout` field is omitted for those payloads, preserving their
serialized bytes. A root mapping of bounded numeric vectors receives `2.3` and
its explicit layout. The bounded reader checks the selected wrapper and blob,
exact slot inventory, payload integrity, and profile identity before returning
arrays. Both GlobalState reconstruction entrypoints validate the complete root and
nested field layout before attempting backend discovery; unknown fields are
rejected instead of being dropped during dataclass construction.

`StateSnapshotRef` keeps its existing `foundry.state_snapshot` kind. The new
payload version does not change a reference's identity or grant authority. N5,
calibration, simulation-state objectives, and agent-state readers reject the
sparse layout; the bounded method-input consumer is the only path that reads
it. A replay gate may recognize the typed 2.3 artifact for transport, but that
recognition does not make its arrays a simulation state or a policy finding.

The generated JSON Schema catalog at `docs/reference/schemas.md` covers the ABI
snapshot registry and IR reflection catalog; it does not own this Core-persisted
DTO. The runtime OpenAPI schema exposes `StateSnapshotRef`, not the persisted
`StateSnapshot` payload. The DTO and its version registry remain the source of
truth for this internal CAS format, so no unrelated generated artifact is
hand-edited for this change.
