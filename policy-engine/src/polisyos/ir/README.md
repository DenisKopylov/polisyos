# IR (`polisyos.ir`)

## Purpose

`polisyos.ir` defines PolicyOS's canonical contract layer for policy
authoring, schema-backed reflection, registry-aware linking, observation-driven
readiness bundles, and analytical results. The root package acts as a lazy
facade for the most common import paths and as a local navigation point for the
IR subsystem.

The root facade does not mirror all code under `src/polisyos/ir/**`.
`TrinityBundle` is implemented in [`trinity`](./trinity/README.md) and exposed
through the root facade; linker entry points are in
[`linker`](./linker/README.md).

## Where to Start

- [`__init__.py`](./__init__.py) — stable lazy facade and supported root import surface.
- [`api.py`](./api.py) — public-surface manifest and shared lazy-facade helpers.
- [`model_layer`](./model_layer/README.md) — canonical model contracts: `ModelSpec`, canon, predicates, queries, types, and units.
- [`loading`](./loading/README.md) — loader and load-time contracts, including `load_policy()`.
- [`registry`](./registry/README.md) — registry fragments, artifact refs, and public-surface metadata.
- [`schemas`](./schemas/__init__.py) — reflection API that powers generated reference pages.
- [`trinity/README.md`](./trinity/README.md) — canonical `ProblemFrame + PolicySpec + ModelSpec` payload.
- [`governance/README.md`](./governance/README.md) — authoring surface for `ProblemFrame` and `PolicySpec`.
- [`observation/README.md`](./observation/README.md) — measurement, readiness, and execution bundles.
- [`analytics/README.md`](./analytics/README.md) — causal, transportability, HTE, uncertainty, and frontier result contracts.
- Neighboring packages useful for navigation: [`kernel/README.md`](./kernel/README.md), [`migrations/README.md`](./migrations/README.md), [`linker/README.md`](./linker/README.md), [`artifacts/README.md`](./artifacts/README.md), [`world/README.md`](./world/README.md).

## Public API

| Entrypoint                                                                | Use when                                                                     | Defined in                                               |
| ------------------------------------------------------------------------- | ---------------------------------------------------------------------------- | -------------------------------------------------------- |
| `polisyos.ir.load_policy()`                                               | Load a canonical policy payload from a `dict`, JSON, YAML, or bytes          | [`loading/loaders.py`](./loading/loaders.py)             |
| `polisyos.ir.ProblemFrame`, `PolicySpec`, `ModelSpec`                     | Use the base Trinity contracts through the root import path                  | [`__init__.py`](./__init__.py)                           |
| `polisyos.ir.ArtifactRefModel`                                            | Use a typed reference to a persisted IR/CAS artifact through the root facade | [`registry/refs.py`](./registry/refs.py)                 |
| `polisyos.ir.get_ir_schema_catalog()`, `list_ir_types()`, `get_ir_type()` | Use the reflection/catalog API for local discovery and generated docs        | [`schemas`](./schemas/__init__.py)                       |
| `polisyos.ir.load_simulation_result_subject_uncertainty_projection()`    | Fresh-read one metric or state-slot uncertainty subject with explicit limits | [`analytics/uncertainty.py`](./analytics/uncertainty.py) |
| `polisyos.ir.ObservationRecord`, `ObservationPanel`                       | Use the base observation surface for record/panel payloads                   | [`observation/contracts.py`](./observation/contracts.py) |
| `polisyos.ir.CausalReadinessBundle`, `CausalExecutionBundle`              | Use readiness/execution bundles for downstream Foundry/Scientist execution   | [`observation`](./observation/README.md)                 |
| `polisyos.ir.CausalEffectReport`, `TransportabilityResult`, `HTEResult`   | Use the canonical analytics result models                                    | [`analytics`](./analytics/README.md)                     |
| `polisyos.ir.HTEOutcome`, `HTEPointResultRef`, `HTEResultEvidenceRef`   | Read a selected-profile candidate HTE outcome and its point/native-inference evidence | [`analytics/hte.py`](./analytics/hte.py)           |
| `polisyos.ir.TrinityBundle`                                               | Use the canonical Trinity container                                          | [`trinity/__init__.py`](./trinity/__init__.py)           |
| `polisyos.ir.linker.link_trinity()`                                       | Link a Trinity payload to the registry surface before compilation/runtime    | [`linker/README.md`](./linker/README.md)                 |

The HTE physical materialization-binding reference records selected input
array positions, payload digests, and row order. It does not establish that a
requested variable ID names an outcome or treatment array, nor does it
establish units, query semantics, or population coverage.

## Internal Layout

`load_simulation_result_subject_uncertainty_projection()` preserves the existing metric
admission path. Its `state_slot` path resolves the selected SimulationResult, propagation
report, output envelope, and exact manifest edges. It compares the complete
`response_context.*` input roster in both manifests with the producer-carried
selected source identities and resolves their selected CAS content and manifest
bytes. A legacy report without this roster remains a limited candidate; malformed,
foreign, orphaned, or mismatching selected identities suppress the projection.
A successful state-slot read remains candidate-only and gate-ineligible: this IR
reader does not recompute the Foundry response matrix or verify successful draw
identities.
## Supported owner facets

The supported subpackage facades are grouped by contract owner: `polisyos.ir.kernel` and `polisyos.ir.world` for their lazy owner maps; `polisyos.ir.connectors` for connector contracts; `polisyos.ir.loading` for fact-log and citation contracts; `polisyos.ir.registry` for typed artifact references; `polisyos.ir.model_layer` for shared model vocabulary; and `polisyos.ir.trinity` for Trinity contracts and its selected-CAS artifact loader. These routes preserve defining-object identity. The artifact loader validates the selected IR CAS view, manifest owner metadata, and payload schema; it does not establish issuer authority or currentness.


### Structural causal result compatibility

The root facade exports four canonical analytics objects:
`CausalResultKind`, `CausalEstimatorInterval`, `SCMTrainingRows`, and
`SCMFitProvenance`. They retain their defining objects and serialization behavior;
the facade does not duplicate their contracts. Causal query schema 1.2 and twin
schema 1.1 distinguish fixed-model outcome/ITE distributions and supported
conditional posterior spans from a separate iid-row refit estimator interval.
Selected source-bound GCM models use schema 1.1 and retain actual training rows
and worker provenance. Historical/manual SCM schema 1.0 remains readable without
supplying a new backend witness. Historical causal query schemas 1.0/1.1 and twin
schema 1.0 decode as limited, non-gating distributions; old CI/eligibility markers
do not acquire renewed authority. These local versions leave the shared global
uncertainty schema unchanged. See the
[analytics compatibility contract](./analytics/README.md) and
[structural causal models](../../../docs/reference/foundry/structural-causal-models.md).

- [`api.py`](./api.py) and [`__init__.py`](./__init__.py) own the stable lazy
  facade and install the deprecated-import alias hook. The default
  `_IR_LEGACY_MODULE_ALIASES` and `_IR_LEGACY_AGGREGATE_MODULES` maps are empty,
  so this configuration registers no legacy module import paths.
- [`_internal/`](./_internal/) is private implementation code. Do not import it
  from other packages.
- [`registry/public_surface.py`](./registry/public_surface.py) owns the
  public-surface metadata that used to be exposed through the retired
  `polisyos.ir.public_surface` compatibility alias.
- [`model_layer/`](./model_layer/README.md) owns model-layer semantics:
  canonicalization, `ModelSpec`, predicates, queries, shared types, and units.
- [`loading/`](./loading/README.md) owns loaders, citations, fact-log,
  migration-report, norm-pack, portfolio, and schema-catalog loading views.
- [`registry/`](./registry/README.md) owns registry fragments, artifact refs,
  and public-surface registry metadata. Citation refs live in
  [`loading/citations.py`](./loading/citations.py); the retired
  `polisyos.ir.references` aggregate no longer resolves.
- [`schemas/`](./schemas/__init__.py) remains schema wrapper and reflection code,
  [`trinity/`](./trinity/README.md), [`governance/`](./governance/README.md),
  [`observation/`](./observation/README.md), and
  [`analytics/`](./analytics/README.md) are the main public-adjacent contract
  owners.
- [`analytics/`](./analytics/README.md) remains the analytics contract package;
  it should import shared refs from `registry` and model primitives from
  `model_layer`.

## Extension Points

- IR is not a plugin host in `architecture/extension_points.toml`; it is the
  shared schema and contract layer consumed by extension hosts in Foundry,
  Scientist, Fabric, Lex, Runtime, and Data Forge.
- New schema-backed public IR types should follow
  [Add a schema-backed IR type](../../../docs/how-to/add-schema-backed-ir-type.md)
  and update the schema catalog/reference generation checks.

## Depends on / depended on by

- Depends on: [`kernel`](./kernel/README.md), [`trinity`](./trinity/README.md), [`governance`](./governance/README.md), [`analytics`](./analytics/README.md), [`observation`](./observation/README.md), [`artifacts`](./artifacts/README.md), [`linker`](./linker/README.md), [`migrations`](./migrations/README.md).
- Depended on by: `polisyos.foundry`, `polisyos.scientist`, `polisyos.fabric`, `polisyos.lex`, `polisyos.core`, plus docs/tooling that render IR schema and public-surface catalogs.

## Common commands

Run from the repository root (`policy-engine/`).

Smoke-tested on `2026-05-05`.

```bash
uv run python -c "from polisyos.ir import ProblemFrame, load_policy, list_ir_types; print(ProblemFrame.__name__, callable(load_policy), len(list_ir_types(section='governance', public_only=True)))"
```

## Tests

Run from the repository root (`policy-engine/`).

Conceptual in this README refresh; run these targeted checks before landing IR
changes.

```bash
uv run pytest tests/unit/ir/test_public_surface.py tests/unit/ir/test_schema_catalog.py tests/unit/ir/test_trinity_loaders.py tests/unit/ir/test_interoperability_bridges.py -q
uv run python tools/quality/diagnostics/generate_ir_reference_catalog.py --check
uv run --extra ml polisyos-tools diagnostics gen-schema --check
```

Package-local ownership is documented in
[tests/unit/ir/README.md](../../../tests/unit/ir/README.md) and high-complexity
analytics coverage is documented in
[tests/unit/ir/analytics/README.md](../../../tests/unit/ir/analytics/README.md).

## Operability Links

- [IR component SLO](../../../ops/components/ir/slo.yaml)
- [IR component runbooks](../../../ops/components/ir/runbooks.md)
- [IR schema catalog](../../../docs/reference/ir/schema-catalog.md)
- [Schema management how-to](../../../docs/how-to/manage-schemas.md)
- [Broken contract generation runbook](../../../docs/runbooks/broken-contract-generation.md)

## Known Shims/Deprecations

- The last-mile import aliases for `polisyos.ir.model_spec`,
  `polisyos.ir.refs`, and `polisyos.ir.types` are retired. Use
  `polisyos.ir.model_layer.model_spec`, `polisyos.ir.registry.refs`, and
  `polisyos.ir.model_layer.types`.
- `polisyos.ir.connectors` and `polisyos.ir.trinity` are real public IR
  contract surfaces, not shim debt.
- The high-complexity `ir/analytics/strategic.py` budget is tracked in
  [architecture/module_size_budget.toml](../../../architecture/module_size_budget.toml)
  with owner `team-ir` and sunset `2026-12-31`.

## Reference docs

- [IR reference index](../../../docs/reference/ir/index.md)
- [IR public surface](../../../docs/reference/ir/public-surface.md)
- [IR schema catalog](../../../docs/reference/ir/schema-catalog.md)
- [IR compiler pipeline](../../../docs/reference/ir/compiler-pipeline.md)
- [IR interoperability](../../../docs/reference/ir/interoperability.md)
- [IR governance](../../../docs/reference/ir/governance.md)
- [IR analytics](../../../docs/reference/ir/analytics.md)
- [IR observation](../../../docs/reference/ir/observation.md)
- [Shared schemas reference](../../../docs/reference/schemas.md)
- [Shared public surface reference](../../../docs/reference/public-surface.md)
- [TRINITY contract](../../../docs/contracts/TRINITY.md)
- [Merge semantics contract](../../../docs/contracts/MERGE_SEMANTICS.md)

- Last updated: 2026-10-14

`polisyos.ir.ArticleExtractionResult` lazily exposes the unchanged canonical
literature extraction contract to DataForge. `polisyos.ir.TrinityBundle` exposes
the existing Trinity container to runtime source custody. Both exports resolve
to their original defining objects; no contract, validation or serialization
semantics are duplicated.

The root also lazily exposes `LinkReport` as the exact linker-owned object for
bounded execution-input replay. A linker report is not an authority grant.

## R2075 exact-consumer compatibility routes

The `polisyos.ir` root lazy facade is the stable compatibility route for the cross-owner consumer symbols previously imported from deep analytics, registry, kernel, governance, and artifact modules. Each added export is an exact lazy alias to its defining owner binding; it does not define a second model or codec. The distinct `MechanismDesignFamily` and `ModelQueryDataViewRequest` aliases preserve their separate contracts from the existing `MechanismFamily` and `DataViewRequest` root bindings. `get_json_artifact_with_bytes` preserves selected-profile validation and the verified persisted bytes needed for content identity.


## Successor HTE outcome chain

The stable facade exposes the strict HTE successor models, typed refs, and CAS
readers while preserving defining-object identity. `HTEPointResult`,
`ATEInferenceBasis`, `HTERefusalDiagnostic`, and `HTEOutcome` are profile-selected
and versioned. An admitted interval uses the existing `ir.hte_result@1.0` artifact
as its sole CATE-vector and interval carrier, paired with `ATEInferenceBasis`.
A valid point whose native interval cannot satisfy the HTEResult v1 contract is
persisted as a point result with a basis that retains the rejected native bounds.
The discriminated outcome carries explicit request and computed scope/guarantee
fields and remains candidate-only.

An optional `SearchUncertaintyTaskBindingRef` is included only when the owning
Runtime request already contains that selected profiled ref. The IR producer
requires the same ref in each emitted model and its CAS input lineage; absent
means no Search task binding. Public consumers can inspect scalar summaries
without reading the full CATE vector, then use the strict artifact loaders for
content that their read path is allowed to resolve.
