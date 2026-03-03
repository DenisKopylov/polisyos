# ir.governance

`ir.governance` определяет governance-контракты Trinity: постановку задачи (`Why`), спецификацию интервенций (`What`), селекторы, расписание и gate-события.

## Роль в Trinity

```text
ProblemFrame (Why)
       +
PolicySpec (What)
       +
ModelSpec (How, в ../model_spec.py)
       =
TrinityBundle
```

См. также: [`../trinity/README.md`](../trinity/README.md)

## Состав

| Файл | Назначение |
|---|---|
| `problem_frame.py` | `ProblemFrame`, objectives/KPI/success criteria/constraints/stakeholders |
| `policy_spec.py` | `PolicySpec`, interventions, mechanism bindings, tunable parameters |
| `selector_expr.py` | AST селекторов (`predicate`, `all_of`, `any_of`, `not`) |
| `schedule.py` | `ScheduleSpec`, `schedule_range()` |
| `gate.py` | `GateRequest`, `GateDecision`, `GateEvent`, `GateVerdict/Priority/EventType` |
| `validation.py` | отчёты и диффы по pydantic validation errors |

## Ключевые ограничения

- `ProblemFrame`:
  - уникальность `objective_id`, `kpi_id`, `criterion_id`, `constraint_id`, `stakeholder_id`;
  - `success_criteria.kpi_id` должен ссылаться на существующий KPI;
  - в `hard_constraints` разрешены только `constraint_type=HARD`, в `soft_constraints` только `SOFT`.
- `PolicySpec`:
  - уникальность `intervention_id`, `binding_id`, `param_id`;
  - `MechanismBinding.intervention_ids` и `ParameterSpec.intervention_id` должны ссылаться на существующие interventions.
- Selector AST:
  - лимиты сложности: `MAX_SELECTOR_DEPTH=10`, `MAX_SELECTOR_NODES=50`;
  - `SelectorPredicate` отдельно валидирует семантику операторов (`in`, `between`, `contains`).
- `ScheduleSpec`:
  - требуется `end_step` или `duration_steps`;
  - при одновременной передаче обоих значений проверяется согласованность диапазона.

## Где используется

| Директория | Использование |
|---|---|
| `ir/trinity` | включает `ProblemFrame` и `PolicySpec` в `TrinityBundle` |
| `ir/linker` | валидирует interventions/constraints/selectors/schedules |
| `scientist/governance` | preflight, gate-протокол и audit trail |
| `core/governance` | policy/legal passes и совместимые контракты |

## Быстрый импорт

```python
from polisyos.ir.governance import ProblemFrame, PolicySpec, GateRequest
```
