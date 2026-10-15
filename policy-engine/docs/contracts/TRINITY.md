# Trinity Contracts (ProblemFrame, PolicySpec, ModelSpec)

Owner: `@ir-owners`
Source of truth: `policy-engine/src/polisyos/ir/trinity/__init__.py`, `policy-engine/src/polisyos/ir/trinity/loaders.py`, `policy-engine/src/polisyos/core/contracts/trinity.py`, `policy-engine/src/polisyos/ir/loading/loaders.py`, `policy-engine/src/polisyos/ir/migrations/`, `policy-engine/src/polisyos/ir/linker/`
Snapshot and evidence level: the DTO, loader, and migration sources were read at source pin `bafca83bff9ff49eef1466bc491a8420b5cd1dbb` and confirmed unchanged at frozen branch commit `378f08c50b61944667fb3de123dcd7f2415ce5f2`. Targeted loader and migration tests were read at the frozen commit but not executed for this documentation update.

## Rationale

PolicySurfaceIR bundled the entire problem definition, policy actions, and model
assumptions into a single artifact. This made sensitivity analysis difficult and
blurred ownership boundaries. The Trinity split enforces separation of concerns:

- ProblemFrame: Why we are solving the problem (goals, KPIs, constraints).
- PolicySpec: What we will do (interventions, parameters, schedules).
- ModelSpec: How we simulate (data snapshot, agents, assumptions, environment).

This enables testing one policy across multiple world models while keeping goals
stable across policy iterations.

## Artifact Overview

ProblemFrame (Why)

- Objectives, KPIs, success criteria.
- Hard and soft constraints.
- Stakeholders and narrative context.

PolicySpec (What)

- Policy interventions and targeting.
- Mechanism bindings and tunable parameters.
- Optional global scheduling and metadata.

ModelSpec (How)

- Data snapshot and registry bundle references.
- Agent configuration and assumptions.
- Environment parameters and fidelity level.

There are two different public types named `TrinityBundle`:

- `polisyos.ir.trinity.TrinityBundle` (also exported as `polisyos.ir.TrinityBundle`) is the nested payload containing `ProblemFrame`, `PolicySpec`, and `ModelSpec`. Its current declared/default schema version is `1.0`.
- `polisyos.core.contracts.trinity.TrinityBundle` is a Core container of `ProblemFrameRef`, `PolicySpecRef`, and `ModelSpecRef`. `TrinityBundleRef` points to one persisted nested IR bundle; `TrinityManifest` wraps the Core reference bundle with manifest metadata.

Use the nested IR payload for authoring, loading, and linking. Use the Core reference container when a boundary needs references to the three separately persisted artifacts. The Core container's `compatible` field is DTO data and defaults to `True` when omitted. Neither the default nor an explicitly supplied value resolves the references or establishes compatibility; this field is not a compatibility computation, evidence, or authority.

These models validate their declared structure and field constraints. A successful DTO parse does not establish semantic adequacy, causal validity, admissibility, or publishability. `polisyos.ir.linker.link_trinity()` performs the separate registry-aware linking checks; downstream authority decisions require their own evidence and consumers.

The current owners are `polisyos.ir.trinity` for the nested payload and
exact-version loaders, `polisyos.core.contracts.trinity` for reference
contracts, `polisyos.ir.loading.loaders` for `load_policy()`, `load_trinity()`,
and the tuple-returning `load_trinity_bundle()`, and `polisyos.ir.migrations`
for explicit versioned canonical-IR migration. These sources expose distinct
loading contracts; this page does not claim an end-to-end persisted-artifact,
orchestrated-admission, or publication path.

## Usage Examples

The constructor examples are illustrative and were not executed for this
documentation update. The reference example uses synthetic IDs to show the DTO
shape; it does not create or resolve CAS artifacts.

Minimal ProblemFrame:

```python
from decimal import Decimal

from polisyos.ir.governance.problem_frame import ProblemFrame, ProblemDomain, ObjectiveSpec
from polisyos.ir.model_layer.types import OptimizationDirection

problem = ProblemFrame(
    problem_id="reduce_inequality_2026",
    domain=ProblemDomain.SOCIAL,
    objectives=[
        ObjectiveSpec(
            objective_id="obj_1",
            metric_id="gini",
            direction=OptimizationDirection.MINIMIZE,
            weight=Decimal("1"),
        )
    ],
)
```

Minimal PolicySpec:

```python
from decimal import Decimal

from polisyos.ir.governance.policy_spec import PolicySpec, InterventionSpec
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate

policy = PolicySpec(
    policy_id="progressive_tax_v1",
    interventions=[
        InterventionSpec(
            intervention_id="income_tax",
            kind="income_tax",
            target=SelectorPredicate(
                kind="predicate",
                field="income",
                operator=">",
                value=Decimal("10000"),
            ),
            schedule=ScheduleSpec(start_step=0, duration_steps=12),
            params={"rate": Decimal("0.15")},
        )
    ],
)
```

Minimal ModelSpec:

```python
from polisyos.ir.model_layer.model_spec import ModelSpec, FidelityLevel

model = ModelSpec(
    model_id="baseline_2026",
    data_snapshot_ref="sha256:" + "0" * 64,
    fidelity_level=FidelityLevel.HYBRID,
)
```

Typed reference bundle:

```python
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.contracts.trinity import (
    ModelSpecRef,
    PolicySpecRef,
    ProblemFrameRef,
    TrinityBundle,
)

problem_artifact_id = ArtifactID.from_sha256_hex("1" * 64)
policy_artifact_id = ArtifactID.from_sha256_hex("2" * 64)
model_artifact_id = ArtifactID.from_sha256_hex("3" * 64)
bundle = TrinityBundle(
    problem_frame_ref=ProblemFrameRef(artifact_id=problem_artifact_id),
    policy_spec_ref=PolicySpecRef(artifact_id=policy_artifact_id),
    model_spec_ref=ModelSpecRef(artifact_id=model_artifact_id),
)
```

## Loading and migration

Both `polisyos.ir.trinity.loaders` and `polisyos.ir.loading.loaders` expose a
function named `load_trinity_bundle`; their return and version-admission
contracts differ:

- `polisyos.ir.trinity.loaders.load_trinity_bundle()` returns the nested IR
  `TrinityBundle`. It requires a `schema_version` and compares it exactly with
  `target_schema_version`, which defaults to
  `TRINITY_BUNDLE_SCHEMA_VERSION` (`"1.0"`). Mapping inputs reach model
  validation only after this exact comparison; an already validated model
  instance is compared before return. This exact-value guard is not a
  schema-registry negotiation, migration, or handoff to a target version.
- `polisyos.ir.loading.loaders.load_trinity_bundle()` accepts mapping, JSON,
  YAML, or UTF-8 bytes and returns `(TrinityBundle, None)`. It calls
  `TrinityBundle.model_validate()` without an exact version comparison or a
  migration-registry lookup. `schema_version` defaults to `"1.0"` in the model
  and its declared field constraint checks only the `MAJOR.MINOR` shape; a
  structurally valid payload with another shape-matching value such as `"2.0"`
  can therefore pass this loader. `load_policy()` and `load_trinity()` in this
  module return the model only. The `auto_migrate` argument exposed by
  `load_policy()` and this module's `load_trinity_bundle()` does not invoke a
  migration; it only selects the validation-error message.

This is a partial admission boundary: callers that need exact equality for
the top-level `TrinityBundle.schema_version` must use the
`polisyos.ir.trinity.loaders` check.
Neither loader establishes semantic adequacy, evidence custody, or authority.
`migrate_policy_ir()` is a separate explicit operation; the exact-version
loader does not hand mismatched input to it, and the `auto_migrate` argument is
not a target-version handoff.

The versioned migration owner is `polisyos.ir.migrations.migrate_policy_ir()`.
It handles canonical Trinity-era `policy_ir` payloads; the current registered
baseline is version `1.0`, and no schema-transition edge is registered at this
source pin. The helper explicitly rejects legacy non-Trinity payloads,
including `schema_version` values beginning with `2.` and payloads containing
a `semantic` key. The package also provides `split_to_bundle()` and
`is_trinity_migrated()` as Trinity validation helpers in
`polisyos.ir.migrations.trinity_migration`.

Older planning and contract documents refer to `PolicySurfaceIR` and
`polisyos.ir.legacy.migrations`. Those are historical migration notes, not
current runtime compatibility guarantees: the pinned source contains neither a
`PolicySurfaceIR` implementation nor that migration package. No deprecated
legacy-module aliases are registered in the default IR owner configuration at
this source pin; the empty alias registries do not provide import compatibility.
This is separate from the canonical `policy_ir` schema-migration behavior
described above.

The code-inspected entrypoints are:

```python
from polisyos.ir.loading.loaders import load_policy, load_trinity_bundle
from polisyos.ir.migrations import migrate_policy_ir

bundle = load_policy(payload)
bundle, migration_report = load_trinity_bundle(payload)
payload = migrate_policy_ir(payload, target_version="1.0")
```

These examples are code-inspected but were not executed for this documentation
update. `migrate_policy_ir()` returns a payload mapping; the loaders return a
validated IR `TrinityBundle` (and the bundle loader's optional report is
currently `None`). A same-version migration validates the canonical bundle;
the API does not promise conversion from `PolicySurfaceIR`.

## Generated schemas

The generated [IR Schema Catalog](../reference/ir/schema-catalog.md) and
[JSON Schema Catalog](../reference/schemas.md) are the reference for current
schema fields and snapshots. Regenerate or check them with
`uv run --extra ml polisyos-tools diagnostics gen-schema --check` from
`policy-engine/`; this page intentionally does not duplicate the schema inventory.

## D1-L4 Validation Links

| Link type           | Current anchor                                                                                                                                                                                                                            |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Source plan phase   | D1-L4 Phase 0 canonicalization, registry/linker, and Phase 1 schema compatibility                                                                                                                                                         |
| Contract tests      | `policy-engine/tests/contract/test_trinity_contracts.py`, `policy-engine/tests/contract/test_trinity_migration.py`, `policy-engine/tests/contract/test_trinity_linker_contract.py`, `policy-engine/tests/unit/ir/test_trinity_loaders.py` |
| Generated reference | [IR Schema Catalog](../reference/ir/schema-catalog.md), [JSON Schema Catalog](../reference/schemas.md)                                                                                                                                    |
