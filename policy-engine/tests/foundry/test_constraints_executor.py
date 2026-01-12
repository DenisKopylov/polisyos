from __future__ import annotations

from decimal import Decimal

import jax.numpy as jnp
import pytest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.registry import build_registry_bundle, load_registry_bundle_content
from polisyos.foundry.compiler import compile_surface_policy
from polisyos.foundry.domain.state import GlobalState
from polisyos.foundry.executor import execute_program_graph
from polisyos.ir.kernel import (
    DEFAULT_MECHANISM_REGISTRY,
    DEFAULT_MERGE_RULE_REGISTRY,
    DEFAULT_METRIC_REGISTRY,
    DEFAULT_SELECTOR_FIELD_REGISTRY,
    DEFAULT_SLOT_REGISTRY,
    DEFAULT_UNITS_REGISTRY,
)
from polisyos.ir.kernel.constraints import ConstraintRegistry, ConstraintSpec
from polisyos.ir.surface import PolicySemantic, PolicySurfaceIR

CTX_REF = "sha256:0000000000000000000000000000000000000000000000000000000000000000"


def _registries_with_constraint(store: FileSystemCAS, operator: str):
    constraint_registry = ConstraintRegistry(
        constraints={
            "budget_guard": ConstraintSpec(
                constraint_id="budget_guard",
                slot_id="government.balance",
                operator=operator,
                unit_id="usd",
            )
        }
    )
    bundle = build_registry_bundle(
        store,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        constraint_registry=constraint_registry,
        selector_field_registry=DEFAULT_SELECTOR_FIELD_REGISTRY,
        metric_registry=DEFAULT_METRIC_REGISTRY,
        units_registry=DEFAULT_UNITS_REGISTRY,
    )
    return load_registry_bundle_content(store, bundle.bundle_ref)


@pytest.mark.parametrize(
    ("operator", "state_value", "constraint_value", "should_pass"),
    [
        (">", 5.0, 1.0, True),
        (">", 0.0, 1.0, False),
        ("<", -1.0, 0.0, True),
        ("<", 1.0, 0.0, False),
        ("==", 2.0, 2.0, True),
        ("==", 2.0, 3.0, False),
        ("!=", 2.0, 3.0, True),
        ("!=", 2.0, 2.0, False),
        (">=", 1.0, 1.0, True),
        ("<=", 1.0, 1.0, True),
    ],
)
def test_constraint_operators(
    operator: str, state_value: float, constraint_value: float, should_pass: bool, tmp_path
) -> None:
    store = FileSystemCAS(tmp_path)
    registries = _registries_with_constraint(store, operator)

    policy = PolicySurfaceIR(
        semantic=PolicySemantic(
            context_snapshot_ref=CTX_REF,
            constraints=[
                {
                    "constraint_id": "budget_guard",
                    "value": Decimal(str(constraint_value)),
                }
            ],
            interventions=[],
        )
    )

    artifacts = compile_surface_policy(
        store,
        policy,
        mechanism_registry=registries.mechanism_registry,
        slot_registry=registries.slot_registry,
        merge_registry=registries.merge_registry,
        units_registry=registries.units_registry,
    )

    base_state = GlobalState.empty(n_agents=1, n_firms=1).replace(
        government_balance=jnp.array(state_value, dtype=jnp.float32)
    )

    exec_kwargs = dict(
        store=store,
        program_ref=artifacts.program_ref,
        exec_plan_ref=artifacts.exec_plan_ref,
        base_state=base_state,
        mechanism_registry=registries.mechanism_registry,
        slot_registry=registries.slot_registry,
        merge_registry=registries.merge_registry,
        selector_field_registry=registries.selector_field_registry,
        constraint_registry=registries.constraint_registry,
        step=0,
    )

    if should_pass:
        result = execute_program_graph(**exec_kwargs)
        assert result.metrics_ref is not None
        assert result.constraint_report_ref is not None
    else:
        with pytest.raises(ValueError):
            execute_program_graph(**exec_kwargs)
