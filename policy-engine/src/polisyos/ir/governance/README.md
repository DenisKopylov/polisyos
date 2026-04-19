# Governance (`polisyos.ir.governance`)

## Purpose

`polisyos.ir.governance` задает policy-facing authoring surface Trinity:
problem framing, intervention specs, selector expressions, schedule semantics,
gate events, temporal logic и layered policy composition. Здесь находятся
контракты, которые отвечают на вопросы "зачем", "что именно делаем" и "какие
governance constraints должны соблюдаться" до compile/runtime стадии.

## Where to Start

- [`problem_frame.py`](./problem_frame.py) — `ProblemFrame`, objectives, KPI, constraints и stakeholders.
- [`policy_spec.py`](./policy_spec.py) — `PolicySpec`, `InterventionSpec`, bindings и temporal intervention sequencing.
- [`selector_expr.py`](./selector_expr.py) — targeting AST, quantifiers и temporal predicates.
- [`schedule.py`](./schedule.py) — step-based schedule semantics.
- [`temporal_logic.py`](./temporal_logic.py) — LTL/MTL-style policy constraints и execution semantics.
- [`policy_composition.py`](./policy_composition.py) — layered policy stacks, overrides и compatibility rules.
- [`game_design.py`](./game_design.py) — mechanism/game-design contracts для frontier governance surface.
- [`validation.py`](./validation.py) — validation diagnostics и report builders.

## Public entrypoints

| Entrypoint | Use when | Defined in |
|---|---|---|
| `polisyos.ir.governance.ProblemFrame` | Нужно описать policy problem, goals и success criteria | [`problem_frame.py`](./problem_frame.py) |
| `polisyos.ir.governance.PolicySpec` | Нужно описать interventions, bindings и execution metadata | [`policy_spec.py`](./policy_spec.py) |
| `polisyos.ir.governance.InterventionSpec` | Нужен contract одного intervention | [`policy_spec.py`](./policy_spec.py) |
| `polisyos.ir.governance.TemporalInterventionSequence` | Нужен staged rollout / temporal intervention plan | [`policy_spec.py`](./policy_spec.py) |
| `polisyos.ir.governance.ScheduleSpec` | Нужны step-based activation windows | [`schedule.py`](./schedule.py) |
| `polisyos.ir.governance.SelectorPredicate`, `SelectorAll`, `SelectorAny`, `SelectorNot` | Нужно описать targeting surface | [`selector_expr.py`](./selector_expr.py) |
| `polisyos.ir.governance.GateRequest`, `GateDecision`, `GateEvent` | Нужен typed governance gate protocol | [`gate.py`](./gate.py) |
| `polisyos.ir.governance.ValidationReport` | Нужны structured validation diagnostics | [`validation.py`](./validation.py) |

## Depends on / depended on by

- Depends on: [`../kernel/README.md`](../kernel/README.md), [`../observation/README.md`](../observation/README.md) for observation-aware metadata and mappings.
- Depended on by: [`../trinity/README.md`](../trinity/README.md), [`../linker/README.md`](../linker/README.md), `polisyos.foundry`, `polisyos.scientist.governance`, `polisyos.core.governance`, `polisyos.lex`.

## Common commands

Run from the repository root (`policy-engine/`).

Smoke-tested on `2026-04-17`.

```bash
uv run python -c "import polisyos.ir.governance as governance; from polisyos.ir.governance import ProblemFrame, PolicySpec; print(len(governance.__all__), ProblemFrame.__name__, PolicySpec.__name__)"
```

## Test/verification commands

Run from the repository root (`policy-engine/`).

Conceptual in this README refresh; run this governance suite before landing
policy-authoring contract changes.

```bash
uv run pytest tests/ir/governance/test_policy_spec_c0.py tests/ir/governance/test_phase5_governance_contracts.py tests/contract/test_trinity_contracts.py -q
```

## Reference docs

- [IR governance reference](../../../../docs/reference/ir/governance.md)
- [IR problem framing reference](../../../../docs/reference/ir/problem-framing.md)
- [TRINITY contract](../../../../docs/contracts/TRINITY.md)
- [IR root README](../README.md)
- [Trinity README](../trinity/README.md)
- [Linker README](../linker/README.md)

## Last updated

`2026-04-17`
