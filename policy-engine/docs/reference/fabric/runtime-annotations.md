# Fabric runtime annotation compatibility

Owner: Fabric owners, with Core contract owners for runtime annotation types.
Source of truth: `src/polisyos/fabric/evidence/decision_data.py`, `src/polisyos/fabric/data_plane/__init__.py`, and their facade-reflection tests under `tests/unit/fabric/`.

Decision: `AD-E02-FABRIC-REFLECTION-01`, selected as alternative A in the G decision
pack at commit `8f8a0bf53e687c07c8de62d934a61c98448e5530`. The implementation
source reviewed for this candidate is commit `8533003b91961cf9ba1305ec296dab7f3ed40e4b`
(tree `2b6cf831d0211cedf3a2caa2543a9e8daa3ac766`). G selection is not code
acceptance: `code_acceptance=false`, `closure_ids=[]`, and no global source or
backend freeze is claimed.

## Contract

For the exact supported facade objects below, a normal import through the named
facade must leave the complete declared callable annotations resolvable by
`typing.get_type_hints` and `typing.get_type_hints(..., include_extras=True)` in
the object's ordinary namespace. The contract includes every declared
parameter and return annotation, actual nominal/generic/union/nullability
semantics, and declared metadata. A non-empty hints mapping is not sufficient.
For `WorldQueryRequest`, check the complete class annotation mapping and the
dataclass-field projection as separate reviewed sets; do not derive the oracle
from the candidate alone. The existing `Any` uses are not prohibited, and a
canonical generic alias need not be a nominal class or be forcibly expanded.

The decision is bounded to the project's supported Python range
(`>=3.14,<3.15`) and the actual supported Fabric dependency profile recorded by
the implementation test receipt. It does not promise every optional backend or
minimal dependency profile, and resolved annotations establish neither backend
availability nor data suitability nor authority.

## Supported facade objects

| Supported route | Objects covered |
| --- | --- |
| `polisyos.fabric.connectors` | `InvalidationTrigger.check_for_updates`; `InvalidationOrchestrator.__init__`; `SchemaChangeInvalidationTrigger.__init__`; `SchemaChangeInvalidationTrigger.on_contract_registered` |
| `polisyos.fabric` | `TemporalRef.from_runtime_scope`; `query_world_table`; `query_claims`; `query_events`; the `WorldQueryRequest` class |
| `polisyos.fabric.data_plane` | Its `query_world_table` export must be the same implementation object as `polisyos.fabric.query_world_table`; no wrapper is introduced. |

The object list is the current repair scope, not a registry or allowlist for
future APIs. A future reflection-facing API uses its normal facade documentation
and semantic tests; no central reflection framework is required.

## Bounded Data Plane compatibility

`run_batch_incremental`, `run_record_mode`, `run_replay_mode`, and
`run_streaming_windowed` remain documented direct-module routes at
`polisyos.fabric.data_plane.modes`. They are not exported by the supported
`polisyos.fabric.data_plane` facade. Their existing `ConnectionConfig` runtime
binding is retained as bounded compatibility; this does not promote the deep
route to a new stable facade export. The module binding also resolves other
annotations in `modes.py`, but that incidental reach is not a public promise.

The existing `ConnectorMetadataSpec` runtime binding and its current tests are
preserved as a separate, already-established obligation. It is not a newly
selected reflection route in this decision.

## Internal annotation placement

`RuntimeLineageRef` and `RuntimeQuantityValue` are used by internal conversion
helper annotations under the unsupported `polisyos.fabric.evidence` deep path.
They are moved to `TYPE_CHECKING` only after source-use inspection confirmed that
runtime conversion does not dispatch on those class bindings: helpers consume
the supplied value, while `to_runtime_quantity_value` imports canonical
constructors at its conversion site. Converter behavior remains unchanged.
Runtime resolution of those internal helper annotations is not promised. The
selected `TemporalRef.from_runtime_scope` surface separately retains the
runtime `RuntimeTemporalRef` and `RuntimeTemporalScope` bindings it needs.

No facade export, wrapper, reflection registry, custom resolver, annotation
mutation, or nominal type relocation is part of this change. The public-surface
contract and inventory were reviewed for membership changes; none are proposed.

## Evidence boundary

This page records the selected contract and implementation scope, not runtime
acceptance. The candidate source edits and the independent facade-reflection
tests must be reviewed and run on the exact composed candidate before any code
acceptance or closure claim. Required distinctions include ordinary facade
imports versus deep imports, full reviewed signatures versus current-only keys,
exact binding removal, and the alias identity check for `query_world_table`.
