# K closeout: complete lane deep-import review

Read-only source/architecture review. No source, baseline, public-surface metadata or generated artifact was edited. The two deciding complete inputs are the retained architecture gate output and `import-edge-reconciliation.json`; no new runtime gate was run.

## Reconciliation

The guardrail baseline contains **3,281** edges (JSON objects and independent serialized source-module keys agree). Applying its complete emitted diff gives **3,310** edges; an independent AST walk over every **2,631 src/**/*.py** file gives the exact same identity set. Filesystem `rglob` and independent `os.walk` reconcile the full file population, with no unreadable file. All **29** added identities exactly match the separate 29 creep messages; no old identity was removed. Edge identity is `(source_module, target_module, source_file)`, not a total.

The complete Git source history from lane base `43580c80b` attributes 6 edges to C1 `34852d5b2b3b511b7f0583a6316b2156e4e2dcb9`, 13 to C3 `504f995cd203f2efebee8566363b8987092e1e34`, 9 to D1 `4f54c80cc4f668da81943b773536c3b92e71eae8`, and 1 to current K. This is lane-owned drift, not inherited debt. Per-edge source hashes and actual import-line/symbol identities are in the reconciliation receipt.

## Decision

Do not blanket-accept 29 edges. The sole K addition is `scholar.search.providers -> ir.analytics.literature` for `OpenAlexWorkText`: this is a justified precise existing-owner edge, with no supported equivalent. The other decisions belong to the planned C3/C1 return. Existing public facade reuse is preferred where it already exports the exact contract. A direct owner with no equivalent facade may be accepted explicitly; private arithmetic coupling needs a narrow owner API if regularized. No API may be weakened to a structural protocol/callback merely to make the import scanner green.

Classification counts from all 29 measured rows: {"K_reviewed_existing_owner": 1, "existing_owner_no_supported_equivalent": 11, "mixed_supported_and_owner": 1, "owner_facade_gap": 2, "private_owner_dependency": 1, "reuse_existing_subpackage": 2, "reuse_supported": 11}. These are review categories, not capability-status claims.

## Every measured edge

### `fabric.retrieval.custody -> core.artifacts`

`reuse_supported` — Use `from polisyos.core import artifacts as core_artifacts` and its declared artifact symbols. Core explicitly exports this module; this is an existing stable facade, not arbitrary submodule hiding.

Actual import locations: `src/polisyos/fabric/retrieval/custody.py:17`.

### `fabric.retrieval.custody -> core.contracts.control`

`existing_owner_no_supported_equivalent` — `FetchPlan` is the actual shared retrieval-plan DTO. Complete `core.contracts` facade map has no export for it. A narrow DTO re-export or explicit reviewed owner dependency is appropriate; keep the plan bytes and all current fields.

Actual import locations: `src/polisyos/fabric/retrieval/custody.py:25`.

### `fabric.retrieval.custody -> ir.connectors`

`existing_owner_no_supported_equivalent` — `FetchRequest` and `FetchResult` are canonical full connector contracts. Supported IR root/api/analytics export maps do not expose them. This is an actual contract owner, not an invented transport DTO; precise reviewed edge acceptance is justified.

Actual import locations: `src/polisyos/fabric/retrieval/custody.py:27`.

### `fabric.retrieval.executor -> core.artifacts`

`reuse_supported` — Use `from polisyos.core import artifacts as core_artifacts` and its declared artifact symbols. Core explicitly exports this module; this is an existing stable facade, not arbitrary submodule hiding.

Actual import locations: `src/polisyos/fabric/retrieval/executor.py:12`.

### `runtime.quality.data_forge_binding -> data_forge.domains.ukraine.manifests`

`owner_facade_gap` — `CalibrationBundleManifest` is the concrete calibration-source DTO owner. The Ukraine read_api exports `ReleaseManifest`/`load_manifest` but not this DTO; neither has equivalent semantics. Prefer a narrow existing Ukraine read_api companion during C3 return, or explicitly record this direct schema dependency. No fabricated intake receipt.

Actual import locations: `src/polisyos/runtime/quality/data_forge_binding.py:1003`.

### `runtime.quality.data_forge_binding -> fabric.connectors.registry`

`owner_facade_gap` — N9 intentionally requires the real `ConnectorRegistry` and its current full-result contract validator. Supported Fabric `ConnectorRegistryLike` only covers `fabric_get_data` methods and lacks `validate_fetch_result`; substituting it would weaken owner provenance. A narrow public validation forwarding API that retains the concrete-owner check is the appropriate future companion; explicit direct-owner acceptance is truthful meanwhile.

Actual import locations: `src/polisyos/runtime/quality/data_forge_binding.py:769`.

### `runtime.quality.data_forge_binding -> fabric.retrieval.custody`

`existing_owner_no_supported_equivalent` — `ResolvedFabricFetch`/`resolve_persisted_fetch` are the new Fabric owner of full stored payload plus fresh connector replay. Existing `fabric_get_data` does not verify this chain. Export through the existing Fabric facade or accept this precise owner dependency; no generic callback substitute.

Actual import locations: `src/polisyos/runtime/quality/data_forge_binding.py:33, 861, 495`.

### `runtime.quality.data_forge_binding -> fabric.retrieval.providers`

`existing_owner_no_supported_equivalent` — `RetrievalProviders` and its resolver are already exposed by the retrieval subpackage facade, but not a supported Fabric entrypoint. They carry the real registry/provider dependency through producer and reader. A governed Fabric facade export or explicit precise edge acceptance is appropriate; changing to an untyped sentinel is not.

Actual import locations: `src/polisyos/runtime/quality/data_forge_binding.py:20`.

### `runtime.quality.data_forge_binding -> foundry.data_plane`

`existing_owner_no_supported_equivalent` — `materialize_method_contract` is an explicit data-plane facade export and the real typed input materializer. Supported compile/execute APIs do not replace this operation. Explicit reviewed edge acceptance is reasonable; optional governed facade promotion must retain the exact owner.

Actual import locations: `src/polisyos/runtime/quality/data_forge_binding.py:1136`.

### `runtime.quality.data_forge_binding -> foundry.methods`

`existing_owner_no_supported_equivalent` — `MethodRegistry` and, where used, `ensure_all_methods_registered` are exported by the documented stable methods facade. Supported Foundry root does not export them. The full-vocabulary owner cannot be replaced with candidate-selection metadata. Explicit reviewed edge acceptance is reasonable.

Actual import locations: `src/polisyos/runtime/quality/data_forge_binding.py:1137`.

### `runtime.quality.data_forge_binding -> foundry.methods.selection`

`reuse_supported` — Import the identical `method_accepts_input_contract` through `polisyos.foundry`; the root lazy map already resolves that exact owner function.

Actual import locations: `src/polisyos/runtime/quality/data_forge_binding.py:1138`.

### `runtime.quality.promotion_sequence -> core.canon`

`reuse_supported` — Use `from polisyos.core import canon as core_canon` with the same canonical owner functions. `canon` is explicitly exported by Core.

Actual import locations: `src/polisyos/runtime/quality/promotion_sequence.py:26`.

### `runtime.quality.promotion_sequence -> fabric.retrieval.providers`

`existing_owner_no_supported_equivalent` — `RetrievalProviders` and its resolver are already exposed by the retrieval subpackage facade, but not a supported Fabric entrypoint. They carry the real registry/provider dependency through producer and reader. A governed Fabric facade export or explicit precise edge acceptance is appropriate; changing to an untyped sentinel is not.

Actual import locations: `src/polisyos/runtime/quality/promotion_sequence.py:28`.

### `runtime.quality.workspace.foundry_consumption -> core.artifacts`

`reuse_supported` — Use `from polisyos.core import artifacts as core_artifacts` and its declared artifact symbols. Core explicitly exports this module; this is an existing stable facade, not arbitrary submodule hiding.

Actual import locations: `src/polisyos/runtime/quality/workspace/foundry_consumption.py:15`.

### `runtime.quality.workspace.foundry_consumption -> foundry.data_plane`

`existing_owner_no_supported_equivalent` — `materialize_method_contract` is an explicit data-plane facade export and the real typed input materializer. Supported compile/execute APIs do not replace this operation. Explicit reviewed edge acceptance is reasonable; optional governed facade promotion must retain the exact owner.

Actual import locations: `src/polisyos/runtime/quality/workspace/foundry_consumption.py:402, 88`.

### `runtime.quality.workspace.foundry_consumption -> foundry.methods`

`existing_owner_no_supported_equivalent` — `MethodRegistry` and, where used, `ensure_all_methods_registered` are exported by the documented stable methods facade. Supported Foundry root does not export them. The full-vocabulary owner cannot be replaced with candidate-selection metadata. Explicit reviewed edge acceptance is reasonable.

Actual import locations: `src/polisyos/runtime/quality/workspace/foundry_consumption.py:89`.

### `runtime.quality.workspace.foundry_consumption -> foundry.methods.backends.dispatch`

`private_owner_dependency` — `_estimate_cost_usd` is the actual dispatcher arithmetic owner, with no public equivalent. The consumer correctly reuses it rather than copying arithmetic, but runtime directly depends on a private helper. Smallest structural companion: publish a narrowly typed owner cost-verification/projection API from existing Foundry methods facade; keep the real arithmetic/removal falsifier. Do not blanket-label this a stable public API.

Actual import locations: `src/polisyos/runtime/quality/workspace/foundry_consumption.py:521`.

### `runtime.quality.workspace.foundry_consumption -> foundry.methods.backends.protocol`

`reuse_existing_subpackage` — Consolidate `MethodTiming` / `ComputeBackend` through the already imported `polisyos.foundry.methods` facade, whose literal export map exposes both exact owners. That facade still requires a reviewed baseline edge, but these extra implementation edges are avoidable.

Actual import locations: `src/polisyos/runtime/quality/workspace/foundry_consumption.py:522`.

### `runtime.quality.workspace.foundry_consumption -> foundry.methods.base`

`reuse_existing_subpackage` — Consolidate `MethodTiming` / `ComputeBackend` through the already imported `polisyos.foundry.methods` facade, whose literal export map exposes both exact owners. That facade still requires a reviewed baseline edge, but these extra implementation edges are avoidable.

Actual import locations: `src/polisyos/runtime/quality/workspace/foundry_consumption.py:523`.

### `runtime.quality.workspace.foundry_consumption -> ir.analytics.causal`

`reuse_supported` — Import the identical `CausalEffectReport` and `EstimationStatus` through supported `polisyos.ir` (both are in its literal lazy export map).

Actual import locations: `src/polisyos/runtime/quality/workspace/foundry_consumption.py:90`.

### `runtime.quality.workspace.foundry_consumption -> scientist.compute`

`existing_owner_no_supported_equivalent` — `MethodBackend` is explicitly exported by the existing Scientist compute facade and is the actual method replay path. The supported root run_experiment API does not reproduce this operation. Precise reviewed owner dependency is justified; do not replace actual backend replay with self-attested result metadata.

Actual import locations: `src/polisyos/runtime/quality/workspace/foundry_consumption.py:456`.

### `runtime.quality.workspace.foundry_consumption -> scientist.orchestration.engine`

`reuse_supported` — Import the identical `ExperimentState` through supported `polisyos.scientist`; root lazy map resolves the same state owner.

Actual import locations: `src/polisyos/runtime/quality/workspace/foundry_consumption.py:33`.

### `runtime.quality.workspace.scientist_node_adapters -> core.artifacts`

`reuse_supported` — Use `from polisyos.core import artifacts as core_artifacts` and its declared artifact symbols. Core explicitly exports this module; this is an existing stable facade, not arbitrary submodule hiding.

Actual import locations: `src/polisyos/runtime/quality/workspace/scientist_node_adapters.py:12, 20`.

### `runtime.quality.workspace.scientist_node_adapters -> core.canon`

`reuse_supported` — Use `from polisyos.core import canon as core_canon` with the same canonical owner functions. `canon` is explicitly exported by Core.

Actual import locations: `src/polisyos/runtime/quality/workspace/scientist_node_adapters.py:23`.

### `runtime.quality.workspace.scientist_node_adapters -> scientist.orchestration.engine`

`mixed_supported_and_owner` — `ExperimentState` can use the supported Scientist root. `NodeOutcome` is absent there; its canonical engine facade is correct and the edge remains unless that contract is explicitly exported. Do not replace strict owner reconstruction with a weak protocol merely to remove an import.

Actual import locations: `src/polisyos/runtime/quality/workspace/scientist_node_adapters.py:746, 758`.

### `runtime.quality.workspace.workflow_playbook_projection -> core.artifacts.manifest`

`reuse_supported` — Use `from polisyos.core import artifacts as core_artifacts` and its declared artifact symbols. Core explicitly exports this module; this is an existing stable facade, not arbitrary submodule hiding.

Actual import locations: `src/polisyos/runtime/quality/workspace/workflow_playbook_projection.py:10`.

### `runtime.quality.workspace.workflow_playbook_projection -> core.canon`

`reuse_supported` — Use `from polisyos.core import canon as core_canon` with the same canonical owner functions. `canon` is explicitly exported by Core.

Actual import locations: `src/polisyos/runtime/quality/workspace/workflow_playbook_projection.py:13`.

### `runtime.quality.workspace.workflow_playbook_projection -> scientist.orchestration.engine`

`existing_owner_no_supported_equivalent` — `UnknownNodeError` is exported by the canonical engine facade, not the supported Scientist root. Preserve typed registry refusal; narrow export or explicit reviewed edge acceptance is needed.

Actual import locations: `src/polisyos/runtime/quality/workspace/workflow_playbook_projection.py:21`.

### `scholar.search.providers -> ir.analytics.literature`

`K_reviewed_existing_owner` — `OpenAlexWorkText` is the canonical source/work DTO and both TYPE_CHECKING/runtime imports need it. Supported IR root/api/analytics do not export it; analytics facade explicitly directs module-specific APIs to their defining owner. This sole new K edge is justified for precise baseline acceptance, without accepting other lane edges.

Actual import locations: `src/polisyos/scholar/search/providers.py:23, 229`.

## Concrete owner evidence

- `architecture/public_surface/contract.toml` defines the exact supported entrypoints; the full gate reports no package-direction violation.
- `core/__init__.py` explicitly exports `artifacts` and `canon`; each child facade explicitly exports the consumed types/functions. The suggested root-module imports preserve this documented API rather than hide arbitrary internals.
- `foundry/__init__.py` resolves `method_accepts_input_contract` directly to the selection owner. `foundry/methods/api.py` explicitly exports `MethodRegistry`, registration, `MethodTiming`, and `ComputeBackend`; it has no exported cost-arithmetic verifier.
- `scientist/__init__.py` explicitly exports `ExperimentState`; engine `__init__.py` exports `NodeOutcome`/`UnknownNodeError`; `scientist/compute/__init__.py` exports `MethodBackend`. The latter contracts have no supported-root equivalents.
- `ir/__init__.py` and `ir/api.py` expose the causal DTOs but not `OpenAlexWorkText` or full connector request/result DTOs. `ir/analytics/__init__.py` explicitly directs module-specific APIs to defining submodules.
- `fabric/api.py:53-81` defines the smaller registry protocol/resolver. It cannot stand in for D1's concrete current-contract verification. `data_forge/read_api/ukraine.py` has a genuine read facade but no `CalibrationBundleManifest` export.

The K P29 status-only correction removes filtering of detected corruption: every issue now turns the gate red. This matches the explicit user/P29 requirement; no new mechanism concern is identified. Its actual native red/green/CLI receipts remain root-owned.
