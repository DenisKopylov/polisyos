# IR Module (Trinity-Only)

`polisyos.ir` содержит канонические контракты политики и утилиты загрузки/линковки.

## Canonical Contracts

- `ProblemFrame` (`problem_frame.py`): почему и в каких границах решаем задачу.
- `PolicySpec` (`policy_spec.py`): какие интервенции и параметры применяются.
- `ModelSpec` (`model_spec.py`): как симулируется мир/данные.
- `TrinityBundle` (`trinity/__init__.py`): transport-бандл из трёх артефактов.

## Runtime Entry Points

- `load_policy(payload)` -> `TrinityBundle`
- `load_trinity_bundle(payload)` -> `(TrinityBundle, MigrationReport | None)`
- `link_trinity(...)` -> `LinkReport`

`load_policy` всегда возвращает `TrinityBundle`.

## Minimal Example

```python
from polisyos.ir.model_spec import ModelSpec
from polisyos.ir.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.schedule import ScheduleSpec
from polisyos.ir.selector_expr import SelectorPredicate
from polisyos.ir.trinity import TrinityBundle

bundle = TrinityBundle(
    problem_frame=ProblemFrame(
        problem_id="fiscal_problem",
        domain=ProblemDomain.FISCAL,
    ),
    policy_spec=PolicySpec(
        policy_id="fiscal_policy",
        interventions=[
            InterventionSpec(
                intervention_id="tax_cut",
                kind="income_tax",
                target=SelectorPredicate(field="id", operator="==", value="all"),
                schedule=ScheduleSpec(start_step=0, duration_steps=1),
                params={"rate": "0.1"},
            )
        ],
    ),
    model_spec=ModelSpec(
        model_id="fiscal_model",
        data_snapshot_ref="sha256:" + "0" * 64,
    ),
)
```

## Schemas

Схемы генерируются через ABI registry:

```bash
python tools/gen_schema.py --check --output-dir schemas/snapshots
```

## Notes

- Legacy surface IR удалён из runtime путей.
- Для миграции внешних интеграций см. `docs/migration/phase4_trinity_only.md`.
