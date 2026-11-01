"""Workflow input values retain their type through persisted canonical bytes."""

from decimal import Decimal

from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
from polisyos.scientist.orchestration.engine.workflow_spec import WorkflowSpec


def test_workflow_params_roundtrip_preserves_typed_numbers_and_legacy_strings() -> None:
    workflow = WorkflowSpec.model_validate(
        {
            "workflow_id": "typed_parameters",
            "nodes": [
                {
                    "alias": "node",
                    "node_id": "scientist.node_noop@1.0.0",
                    "params": {
                        "float_input": 0.25,
                        "decimal_input": Decimal("0.75"),
                        "legacy_string": "0.25",
                        "integer": 2,
                        "boolean": True,
                        "empty": None,
                    },
                }
            ],
        }
    )
    encoded = to_canonical_bytes(workflow.model_dump(mode="python"), CanonSpec(forbid_floats=False))
    restored = WorkflowSpec.model_validate(from_canonical_bytes(encoded))
    assert restored == workflow
    values = restored.nodes[0].params
    assert type(values["float_input"]) is Decimal
    assert type(values["decimal_input"]) is Decimal
    assert values["legacy_string"] == "0.25"
    assert type(values["integer"]) is int
    assert type(values["boolean"]) is bool
    assert values["empty"] is None
