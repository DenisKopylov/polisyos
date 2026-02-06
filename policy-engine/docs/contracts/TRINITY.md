# Trinity Contracts (ProblemFrame, PolicySpec, ModelSpec)

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

Typed references are provided in `polisyos.core.contracts.trinity`:
- ProblemFrameRef
- PolicySpecRef
- ModelSpecRef
- TrinityBundle
- TrinityManifest

## Usage Examples
Minimal ProblemFrame:
```python
from decimal import Decimal

from polisyos.ir.problem_frame import ProblemFrame, ProblemDomain, ObjectiveSpec
from polisyos.ir.types import OptimizationDirection

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

from polisyos.ir.policy_spec import PolicySpec, InterventionSpec
from polisyos.ir.schedule import ScheduleSpec
from polisyos.ir.selector_expr import SelectorPredicate

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
from polisyos.ir.model_spec import ModelSpec, FidelityLevel

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

artifact_id = ArtifactID.from_sha256_hex("0" * 64)
bundle = TrinityBundle(
    problem_frame_ref=ProblemFrameRef(artifact_id=artifact_id),
    policy_spec_ref=PolicySpecRef(artifact_id=artifact_id),
    model_spec_ref=ModelSpecRef(artifact_id=artifact_id),
)
```

## Migration Path (Phase 2)
PolicySurfaceIR is deprecated but still supported for backward compatibility.
Canonical migration utilities live under `polisyos.ir.legacy.migrations`:

```python
from polisyos.ir.legacy.migrations.surface_to_trinity import (
    migrate_surface_ir_to_trinity,
    migrate_trinity_to_surface_ir,
)

bundle, report = migrate_surface_ir_to_trinity(surface_ir)
surface_ir, report = migrate_trinity_to_surface_ir(bundle)
```

## JSON Schema Snapshots
Schema snapshots are generated via `tools/gen_schema.py` and stored under `schemas/snapshots/ir/`:
- `trinity_bundle.schema.json`
- `problem_frame.schema.json`
- `policy_spec.schema.json`
- `model_spec.schema.json`

Example schema fragment (ProblemFrame):
```json
{
  "title": "ProblemFrame",
  "type": "object",
  "properties": {
    "schema_version": { "type": "string" },
    "problem_id": { "type": "string" },
    "domain": { "type": "string" }
  },
  "required": ["problem_id", "domain"]
}
```
