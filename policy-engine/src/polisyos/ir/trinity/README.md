# Trinity Bundle

`TrinityBundle` объединяет три независимых контракта:

- `ProblemFrame` (why)
- `PolicySpec` (what)
- `ModelSpec` (how)

## Example

```python
from polisyos.ir.model_spec import ModelSpec
from polisyos.ir.policy_spec import PolicySpec
from polisyos.ir.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.trinity import TrinityBundle

bundle = TrinityBundle(
    problem_frame=ProblemFrame(problem_id="p1", domain=ProblemDomain.FISCAL),
    policy_spec=PolicySpec(policy_id="s1"),
    model_spec=ModelSpec(model_id="m1", data_snapshot_ref="sha256:" + "0" * 64),
)
```

## Validation

```python
validated = TrinityBundle.model_validate(payload)
json_payload = validated.model_dump(mode="json")
```

## Runtime Contract

Foundry compile path принимает только `ArtifactRef(kind="ir.trinity_bundle")`.
