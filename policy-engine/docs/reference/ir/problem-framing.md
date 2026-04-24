# Problem Framing IR

Related explanation: [Trinity](../../explanation/trinity.md).

> The “why” layer: objectives, KPIs, constraints, stakeholders, and scope semantics.

`ProblemFrame` defines what PolicyOS is trying to optimize or protect before any
specific intervention is proposed. It stays stable while `PolicySpec` and
runtime strategies iterate around it.

In Trinity terms, `ProblemFrame = why`, `PolicySpec = what/intervention`,
and `ModelSpec = how`. This page documents the stable "why" contract and the
objective, KPI, constraint, and stakeholder vocabulary that downstream search
and governance should treat as fixed context.

Freshness: 2026-04-17
Owner: `@ir-owners`
Source of truth: `src/polisyos/ir/governance/problem_frame.py`, `src/polisyos/ir/trinity/**`, `src/polisyos/ir/observation/contracts.py`, `tests/contract/test_trinity_contracts.py`
Source plan phases: D1-L4 Phase 0 Trinity canon/linker contracts and Phase 5 governance contracts.

## Source Modules

| Module                                 | Focus                                                  | Key exports                                                                                                |
| -------------------------------------- | ------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------- |
| `polisyos.ir.governance.problem_frame` | Goals, objectives, criteria, constraints, stakeholders | `ProblemFrame`, `ProblemDomain`, `KPISpec`, `SuccessCriterion`, `ProblemConstraintSpec`, `StakeholderSpec` |
| `polisyos.ir.observation.contracts`    | Entity granularity shared with the observation layer   | Observation scope semantics                                                                                |

## Problem Frame Contracts

`ProblemConstraintSpec` is the root-facade name for `ConstraintSpec` in
`polisyos.ir.governance.problem_frame`.

::: polisyos.ir.governance.problem_frame

## Entity Scope Tie-In

Observation scope determines whether a KPI or downstream metric is interpreted
globally, per firm, per household, per cell, or by region/sector.

See also: [Observation IR](observation.md), where the observation-layer scope
enum is documented alongside the rest of the observation contracts.

## Validation Hooks

| Claim                                                      | Source of truth                                                             | Evidence                                                                                     |
| ---------------------------------------------------------- | --------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| Problem framing is the stable Trinity "why" layer          | `src/polisyos/ir/governance/problem_frame.py`, `src/polisyos/ir/trinity/**` | `schemas/snapshots/ir/problem_frame.schema.json`, `tests/contract/test_trinity_contracts.py` |
| Constraints and stakeholders remain schema-catalog visible | `src/polisyos/ir/governance/problem_frame.py`                               | [IR Schema Catalog](schema-catalog.md#polisyos-ir-governance-problem-frame-problemframe)     |
| Entity scope semantics align with observation contracts    | `src/polisyos/ir/observation/contracts.py`                                  | `schemas/snapshots/ir/entity_scope.schema.json`, `tests/ir/observation/test_contracts.py`    |
