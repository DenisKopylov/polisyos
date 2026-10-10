# Governance gate selected-view decision packet

Candidate HEAD observed: `4699fdf8419dd2c89609f68a3edf5f3bfb7c851a` on `codex/e02-unified-local-20261009`. This is a G decision packet; no GateContext/GateRequest model, ABI snapshot, or gate-protocol change has been made.

## Finding and boundary

P40 bucket: **same P38 selected-view loss class one level deeper**, at the persisted governance request/decision consumer. The raw replay resolver now reads the exact `ArtifactRef` view and verifies typed content, but the request projection drops that selection before a reviewer decision can remain bound to it.

Property intended: a persisted human-gate request and any decision attached to it retain the exact selected replay-artifact views that were checked. Current code tests typed content and completeness (`_gate_replay_readiness`) but serializes `_collect_gate_artifact_refs` as `dict[str, str]` of bare artifact IDs; that projection also omits several keys in the replay-input registry. A concrete divergence is two refs with the same content ID but distinct `manifest_profile_sha256` values: the replay resolver can read different selected manifests, while the current request context cannot identify which view the reviewer saw. A same-run/same-phase/same-iteration replacement also has the same `request_id`, because the current ID formula hashes only those four scope fields. A previously supplied typed decision can therefore carry the same request ID after context replacement. Legacy string/bool decisions are additionally auto-bound to the current request by `_parse_gate_decision`.

The existing typed carriers are sufficient. `ArtifactRef` has optional `manifest_profile_sha256`; `InputRef` has the same field, and `input_ref_from_artifact_ref()` preserves it. The existing Core CAS reader preserves an explicit selected profile. No new hash/profile field is needed to distinguish selected views.

## Current replay producer census

`replay_producer_census.py` parses **all 2,746 `src/polisyos/**/*.py` files** and inventories source write-options calls for the eight replay kinds, including the repository's `_put_registry`, `_cas_put_json`, and `put_json_artifact` wrappers. Retained complete output: `replay_producer_census.txt`. The census reports 31 writer callsites: registry 2, data snapshot 12, input bindings 4, state snapshot 3, Trinity 7, NormPack 1, knowledge bundle 2, and persisted ResearchIntent 0.

The writer defaults are application/json throughout. Existing manifest schemas are derived from the actual producers/models: DataSnapshot 0.2.0 when declared plus schema-less writers; FoundryInputBindings 1.0 plus the schema-less Foundry quickstart; StateSnapshot payload 2.0→manifest 1.0, historical 2.1→2.1.0 in the canonical reader, current 2.2→2.2.0; Trinity writes use the bundle's `schema_version` or the current 1.0; NormPack and KnowledgeBundle are 1.0. Registry builder `_schema_info()` returns `None` because `RegistryBundlePayload` has no `schema_version`; the activity-worker bootstrap stub is also schema-less and fails typed bundle loading. ResearchIntent has no schema field on its strict model and no in-repo persisted producer, so no synthetic 1.0 is admitted. The selected view is on the typed `ArtifactRef`; write options do not accept `manifest_profile_sha256`.

This census supports only current source writer behavior. It does not attest historical producer choices or an external ResearchIntent writer. Schema-less current/historical artifacts are validated as strict payloads under the existing Core selection behavior; the reader does not fabricate a profile digest or producer version.

## Persisted gate contract and compatibility

Current writer: `HumanGateProtocol.request_gate()` in `src/polisyos/scientist/orchestration/kernel/gate_protocol.py` writes `ir.gate_request` with `SchemaInfo('polisyos.ir.GateRequest', request.schema_version)` and producer `ir.gate_protocol@1.0.0`. `GateRequest.schema_version` is 1.1. `GateContext` itself has no schema-version field and currently exposes only `artifact_refs: dict[str, str]` plus untyped `replay_summary: dict[str, Any]`. ABI inventory is `gate_context` version null and `gate_request` version 1.1; canonical snapshots are `schemas/snapshots/ir/gate_context.schema.json` and `gate_request.schema.json`.

`run_governance` is the request producer/consumer bridge: it places serialized requests and only a string artifact ID in state params, then accepts a decision when its `run_id` and `request_id` match. Request-cache admission hardcodes GateRequest 1.1 and rebuilds the request reference from that string. `HumanGateProtocol.persist_decision()` currently creates `InputRef(artifact_id=request_ref.artifact_id, role='gate_request')`, dropping the already-supported `InputRef.manifest_profile_sha256`. The actual tested receiver is the state-param `gate_request` plus CAS request and typed `gate_decision` path in `tests/integration/test_human_gate_audit.py`; no separate dashboard or HTTP human-gate route was found. `preflight_checks()` also constructs an in-memory GateRequest 1.1, but that request feeds automated postflight validation rather than `HumanGateProtocol.request_gate()`.

## Candidate options for G

| Option | Shape | Compatibility and limitation |
| --- | --- | --- |
| A — typed v1.2 request context, context-bound identity (recommended for exact-view gating) | Add an optional typed `GateContext.selected_replay_refs: dict[str, ArtifactRef]`; populate it from the complete current replay-input key set using the exact selected refs. Keep the existing ID-only display field unchanged. New persisted requests use GateRequest 1.2. Reissue legacy 1.1 cache entries when exact selected refs are absent. Domain-separate the v1.2 request ID by hashing the deterministic request basis plus the canonical typed context, so a different selected view cannot reuse the same ID. Persist decision lineage with `input_ref_from_artifact_ref(request_ref, role='gate_request')` and keep the full typed request ref in state for request cache/decision processing. | Old 1.1 requests remain parseable/readable, but they are not exact-view-bound and cannot be upgraded by a reader-materialized selector; reissue from current state when present. A 1.1 request with no current refs remains incomplete/unknown. Additive optional model field is not silently put under 1.1: GateRequest storage version changes to 1.2. Root owns generated ABI snapshots. No existing external UI route is invented. |
| B — decision-ref binding instead of context-bound ID | Add a typed exact request ref to GateDecision and require the receiver to reconcile it with current persisted request; version GateDecision separately. | Strong explicit reference, but widens a second persisted contract and there is no separate human decision route/DTO to evolve here. The workflow's current decision input is state params. |
| C — bounded residual | Keep the current v1.1 context/decision wire shape, classify selected view and exact decision binding as `not_established`; do not use a human approval to promote an incomplete or unbound replay basis. | No wire migration, but this does not close the property. It needs a smallest-capability falsifier and an owner for later closure. |

Option A must also settle the current policy predicate: an incomplete/invalid replay basis may still produce a candidate review request, but an approval label cannot turn that basis into complete/admissible evidence. Whether the human gate can only acknowledge/record a limitation or may authorize a non-authority continuation is a G choice; current code has no typed constraint for that distinction. Do not invent the verdict rule in this patch.

## Required controls if G selects A

- Positive: two identical v1.2 current contexts reuse the same request and exact selected refs; a matching typed decision records a request lineage `InputRef` with the same selected profile.
- Negative: same artifact ID/different manifest-profile selectors produce distinct persisted request context and request identity; a cached v1.1 request or a decision for the old selection is rejected/reissued; malformed supplied refs fail closed, not treated as absent/default.
- History: schema-less/default selected artifacts remain profile-less when their refs are profile-less; the read path does not add the digest it observes. The distinction between `None` (existing Core default-view selector) and explicit profile remains intact.
- Completeness: the request carries all keys in the canonical replay-input contract registry, not only the seven currently displayed by `_collect_gate_artifact_refs`.
- Decision lineage: request profile is retained through `ArtifactRef` state/cache parsing and existing `InputRef` profile field; decision authorization cannot rely on `request_id` alone unless the new request identity is content-bound.

## Source references

- `src/polisyos/ir/governance/gate.py` SHA-256 `9eb88c95a41a83b61adcaa595fbd2622cbc196374cc1618f43fca970fb6b3add`.
- `src/polisyos/scientist/orchestration/kernel/gate_protocol.py` SHA-256 `e9fd4a6a65680391ba81a4fad1a3d77ac0466fcca4e81e62c20ea7d8eb4cba56`.
- `src/polisyos/scientist/nodes/builtins/governance/governance_gate_requests.py` SHA-256 `0cd2a3c49c62d76f8248aeb495c42b1303282c3e3a9c1ccb7be931db97e94417`.
- `src/polisyos/scientist/nodes/builtins/governance/run_governance.py` SHA-256 `00d8a514952785b0fd441932f71d9935d786672fe5c0dfb2d046124494f3de03`.
- `src/polisyos/core/artifacts/manifest.py`: `ArtifactRef`, `InputRef`, and `input_ref_from_artifact_ref()` are the existing typed profile carriers.
- `src/polisyos/core/registry/builder.py` SHA-256 `be523b3bef72b1b16773b1aefe3c493b854e47d2d9f2101d9d827d6270c0fda3`; `src/polisyos/core/artifacts/registry.py` SHA-256 `e665dc55703db9d4c4a9b4f4040c665a8a85c300ae9c668d67480f6241ccaf28`.
- `src/polisyos/core/contracts/scholar.py` SHA-256 `11eec3ac57e53d91b077a5f71658fb51e5ea46f1c1f86fe460253fbd91662e5b`; ResearchIntent has no version field.
- `src/polisyos/foundry/execute/_internal/snapshots/__init__.py` SHA-256 `63b92ac4e2210911cdab437dcbc6d2bb8bc81c4abe507a50e8222667203c7aa1`.
- `schemas/snapshots/ir/_manifest.json` SHA-256 `570df7bbcd0f636f0899003bd3040578c9b1883b51dc37aacdffecf625e57ddf`; schema snapshots: `gate_context.schema.json` `eba3222debbf96f7cfb7494c388008ac128e809362532a54f5766657290140e2`, `gate_request.schema.json` `174e4a38e31b392e27e540df9839e1e44e2ec91c00abd0864de97fb54401398e`.
- `tests/integration/test_human_gate_audit.py` SHA-256 `3a2834572f776102b470654a5b1bae5c48a67917a05240350d30a2278cc1006a`.
