from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.core.contracts.execution_plan import ExecutionPlan, MethodDagNode
from polisyos.core.contracts.method_input import (
    MethodOutputInputPortSource,
    RegistrySlotInputPortSource,
)


def test_method_input_source_is_tagged_and_strict() -> None:
    registry = RegistrySlotInputPortSource.model_validate(
        {"source_kind": "registry_slot", "slot_id": "ledger.flow"}
    )
    output = MethodOutputInputPortSource.model_validate(
        {
            "source_kind": "method_output",
            "producer_node_id": "upstream-node",
            "output_slot_id": "derived.flow",
        }
    )

    assert registry.model_dump(mode="json") == {
        "source_kind": "registry_slot",
        "slot_id": "ledger.flow",
    }
    assert output.model_dump(mode="json") == {
        "source_kind": "method_output",
        "producer_node_id": "upstream-node",
        "output_slot_id": "derived.flow",
    }


def test_method_input_source_preserves_unicode_and_bracketed_contract_names() -> None:
    output = MethodOutputInputPortSource.model_validate(
        {
            "source_kind": "method_output",
            "producer_node_id": "узел[1]",
            "output_slot_id": "derived.flow[0]",
        }
    )
    plan = ExecutionPlan(
        plan_id="unicode-abi-input",
        schema_version="1.2",
        method_dag=[
            MethodDagNode(
                node_id="consumer",
                method_fqn="policy.example@1.0.0",
                reads_slots=["поток[1]"],
                input_ports={"поток[1]": output},
            )
        ],
    )

    assert plan.method_dag[0].input_ports == {"поток[1]": output}


@pytest.mark.parametrize(
    "payload",
    [
        {"source_kind": "registry_slot", "slot_id": " ledger.flow"},
        {"source_kind": "registry_slot", "slot_id": "Ledger.Flow"},
        {"source_kind": "registry_slot", "slot_id": "ledger.flow", "extra": True},
        {"source_kind": "method_output", "producer_node_id": " node-a", "output_slot_id": "x"},
        {
            "source_kind": "method_output",
            "producer_node_id": "node-a",
            "output_slot_id": "x",
            "slot_id": "forged-alternate-source",
        },
    ],
)
def test_method_input_source_rejects_invalid_or_ambiguous_identifiers(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        if payload["source_kind"] == "registry_slot":
            RegistrySlotInputPortSource.model_validate(payload)
        else:
            MethodOutputInputPortSource.model_validate(payload)
