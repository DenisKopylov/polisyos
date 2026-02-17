# ir.governance

`ir.governance` описывает policy-governance контракты Trinity: формулировку задачи, спецификацию интервенций, селекторы, расписание и gate-решения.

## Роль в Trinity

```text
ProblemFrame (Why)
       +
PolicySpec (What)
       +
ModelSpec (How, вне этой папки)
       =
TrinityBundle
```

См. также: [`../trinity/README.md`](../trinity/README.md)

## Состав

| Файл | Назначение |
|---|---|
| `problem_frame.py` | `ProblemFrame`, objectives/KPI/constraints/stakeholders |
| `policy_spec.py` | `PolicySpec`, interventions, mechanism bindings, tunable params |
| `selector_expr.py` | AST селекторов (`predicate/all_of/any_of/not`) |
| `schedule.py` | `ScheduleSpec`, `schedule_range()` |
| `gate.py` | `GateRequest`, `GateDecision`, `GateEvent` контракты |
| `validation.py` | утилиты отчётов/диффов pydantic-валидации |

## Ключевые ограничения

- `ProblemFrame`:
  - уникальность id для objectives/KPIs/criteria/constraints/stakeholders;
  - `success_criteria.kpi_id` должен ссылаться на существующий KPI;
  - в `hard_constraints` допускается только `constraint_type=HARD`, в `soft_constraints` только `SOFT`.
- `PolicySpec`:
  - уникальность id для interventions/bindings/parameters;
  - `MechanismBinding.intervention_ids` и `ParameterSpec.intervention_id` должны ссылаться на существующие interventions.
- Selector AST:
  - лимиты сложности: `MAX_SELECTOR_DEPTH=10`, `MAX_SELECTOR_NODES=50`.
- `ScheduleSpec`:
  - требуется `end_step` или `duration_steps`;
  - если заданы оба, они должны быть согласованы.

## Где используется

| Директория | Использование |
|---|---|
| `ir/trinity` | включает `ProblemFrame` и `PolicySpec` в `TrinityBundle` |
| `ir/linker` | валидирует interventions/constraints/selectors/schedules |
| `scientist/governance` | preflight и gate-protocol (`Gate*`) |
| `core/governance` | policy/legal passes и совместимые контракты |

## Быстрый импорт

```python
from polisyos.ir.governance import ProblemFrame, PolicySpec, GateRequest
```
