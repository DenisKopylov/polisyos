# Trinity Contracts (ProblemFrame, PolicySpec, ModelSpec)

Owner: `@ir-owners`
Source of truth: `policy-engine/src/polisyos/ir/trinity/__init__.py`, `policy-engine/src/polisyos/core/contracts/trinity.py`, `policy-engine/src/polisyos/ir/loading/loaders.py`, `policy-engine/src/polisyos/ir/migrations/`, `policy-engine/src/polisyos/ir/linker/`
Snapshot and evidence level: inspected at commit `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`; implementation and listed tests were read, but not executed for this documentation update.

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

Use the nested IR payload for authoring, loading, and linking. Use the Core reference container when a boundary needs references to the three separately persisted artifacts. The Core container's `compatible` field is caller-provided data; constructing it does not resolve the references or establish compatibility.

These models validate their declared structure and field constraints. A successful DTO parse does not establish semantic adequacy, causal validity, admissibility, or publishability. `polisyos.ir.linker.link_trinity()` performs the separate registry-aware linking checks; downstream authority decisions require their own evidence and consumers.

The current owners are `polisyos.ir.trinity` for the nested payload, `polisyos.core.contracts.trinity` for reference contracts, `polisyos.ir.loading` for payload loading, and `polisyos.ir.migrations` for versioned canonical-IR migration.

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

The current loader entrypoints are `polisyos.ir.loading.loaders.load_trinity_bundle()`,
`load_trinity()`, and `load_policy()`. They parse mapping, JSON, YAML, or UTF-8
bytes input and validate it as the nested IR `TrinityBundle`. The retained
`auto_migrate` loader argument does not currently run a migration: malformed or
non-Trinity payloads are rejected.

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
