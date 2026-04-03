# Problem Framing IR
Related explanation: [Trinity](../../explanation/trinity.md).

> The “why” layer: objectives, KPIs, constraints, stakeholders, and scope semantics.

`ProblemFrame` defines what PolicyOS is trying to optimize or protect before any
specific intervention is proposed. It stays stable while `PolicySpec` and
runtime strategies iterate around it.

## Source Modules

| Module | Focus | Key exports |
|--------|-------|-------------|
| `polisyos.ir.governance.problem_frame` | Goals, objectives, criteria, constraints, stakeholders | `ProblemFrame`, `ProblemDomain`, `KPISpec`, `SuccessCriterion`, `ProblemConstraintSpec`, `StakeholderSpec` |
| `polisyos.ir.observation.contracts` | Entity granularity shared with the observation layer | Observation scope semantics |

## Problem Frame Contracts

`ProblemConstraintSpec` is the root-facade name for `ConstraintSpec` in
`polisyos.ir.governance.problem_frame`.

::: polisyos.ir.governance.problem_frame

## Entity Scope Tie-In

Observation scope determines whether a KPI or downstream metric is interpreted
globally, per firm, per household, per cell, or by region/sector.

See also: [Observation IR](observation.md), where the observation-layer scope
enum is documented alongside the rest of the observation contracts.
