from decimal import Decimal

import pytest
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.foundry import (
    ExecPlan,
    ProgramGraph,
    ProgramGraphRef,
    ProgramNode,
)
from polisyos.foundry.calibration.pure_executor import compile_program
from polisyos.foundry.contracts.state import GlobalState
from polisyos.ir.kernel.mechanisms import (
    MechanismTypeRegistry,
    MechanismTypeSpec,
    ParamSpec,
    ParamType,
)
from polisyos.ir.kernel.merge_rules import DEFAULT_MERGE_RULE_REGISTRY
from polisyos.ir.kernel.slots import DEFAULT_SLOT_REGISTRY


def _dummy_artifact() -> ArtifactID:
    return ArtifactID.from_sha256_hex("0" * 64)


def _build_graph(nodes: list[ProgramNode]) -> tuple[ProgramGraph, ExecPlan]:
    dummy_id = _dummy_artifact()
    program_ref = ProgramGraphRef(artifact_id=dummy_id)
    policy_ref = ArtifactRef(
        artifact_id=dummy_id,
        kind="ir.trinity_bundle",
        media_type="application/json",
    )
    program_graph = ProgramGraph(ir_ref=policy_ref, nodes=nodes, edges=[], entrypoints=[])
    exec_plan = ExecPlan(program_ref=program_ref, order=[node.node_id for node in nodes])
    return program_graph, exec_plan


def _mechanism_registry_with_fidelity() -> MechanismTypeRegistry:
    return MechanismTypeRegistry(
        mechanisms={
            "queue": MechanismTypeSpec(
                mechanism_id="queue",
                params={
                    "service_rate": ParamSpec(
                        param_id="service_rate",
                        required=True,
                        value_type=ParamType.DECIMAL,
                        min_value=Decimal("0"),
                        max_value=Decimal("1e9"),
                    ),
                    "arrival_rate": ParamSpec(
                        param_id="arrival_rate",
                        required=True,
                        value_type=ParamType.DECIMAL,
                        min_value=Decimal("0"),
                        max_value=Decimal("1e9"),
                    ),
                    "fidelity": ParamSpec(
                        param_id="fidelity",
                        required=False,
                        value_type=ParamType.ENUM,
                        enum_values=["fluid", "relaxed", "hard"],
                    ),
                    "temperature": ParamSpec(
                        param_id="temperature",
                        required=False,
                        value_type=ParamType.DECIMAL,
                        min_value=Decimal("0"),
                        max_value=Decimal("100"),
                    ),
                },
                reads_slots=[],
                writes_slots=[],
                default_merge={},
            )
        }
    )


def _loader(params: dict[str, float | str]) -> dict[str, object]:
    return {"params": params, "schedule": {"start_step": 0, "end_step": 1}}


def test_compile_forces_relaxed_fidelity_and_temperature():
    program_graph, exec_plan = _build_graph(
        [
            ProgramNode(
                node_id="queue",
                node_kind="mechanism",
                mechanism_type="queue",
                params_ref=None,
                outputs=[],
            )
        ]
    )
    registry = _mechanism_registry_with_fidelity()
    base_state = GlobalState.empty(n_agents=1, n_firms=0)

    bundle = compile_program(
        program_graph,
        exec_plan,
        mechanism_registry=registry,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        base_state=base_state,
        parameter_loader=lambda _: _loader({"service_rate": 1.0, "arrival_rate": 1.0}),
        force_fidelity="relaxed",
        default_temperature=0.5,
        force_override=True,
    )

    mech = bundle.nodes[0].mechanism
    assert mech.fidelity == "relaxed"
    assert pytest.approx(0.5) == float(mech.temperature)


def test_compile_respects_no_override():
    program_graph, exec_plan = _build_graph(
        [
            ProgramNode(
                node_id="queue",
                node_kind="mechanism",
                mechanism_type="queue",
                params_ref=None,
                outputs=[],
            )
        ]
    )
    registry = _mechanism_registry_with_fidelity()
    base_state = GlobalState.empty(n_agents=1, n_firms=0)

    bundle = compile_program(
        program_graph,
        exec_plan,
        mechanism_registry=registry,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        base_state=base_state,
        parameter_loader=lambda _: _loader(
            {
                "service_rate": 1.0,
                "arrival_rate": 1.0,
                "fidelity": "hard",
                "temperature": 2.0,
            }
        ),
        force_fidelity="relaxed",
        default_temperature=0.5,
        force_override=False,
    )

    mech = bundle.nodes[0].mechanism
    assert mech.fidelity == "hard"
    assert pytest.approx(2.0) == float(mech.temperature)


def test_compile_forces_discrete_fidelity():
    program_graph, exec_plan = _build_graph(
        [
            ProgramNode(
                node_id="queue",
                node_kind="mechanism",
                mechanism_type="queue",
                params_ref=None,
                outputs=[],
            )
        ]
    )
    registry = _mechanism_registry_with_fidelity()
    base_state = GlobalState.empty(n_agents=1, n_firms=0)

    bundle = compile_program(
        program_graph,
        exec_plan,
        mechanism_registry=registry,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        base_state=base_state,
        parameter_loader=lambda _: _loader(
            {"service_rate": 1.0, "arrival_rate": 1.0, "temperature": 0.5}
        ),
        force_fidelity="discrete",
        default_temperature=0.5,
        force_override=True,
    )

    mech = bundle.nodes[0].mechanism
    assert mech.fidelity == "hard"
    assert not hasattr(mech, "temperature") or float(mech.temperature) != 0.5
