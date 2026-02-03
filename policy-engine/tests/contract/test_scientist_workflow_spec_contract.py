from __future__ import annotations

from decimal import Decimal

from polisyos.core.canon import to_canonical_bytes
from polisyos.scientist.engine.workflow_spec import NodeInvocation, WorkflowSpec


def test_workflow_spec_roundtrip_and_canonical_json():
    spec = WorkflowSpec(
        workflow_id="engine_smoke",
        required_binds=["run_id"],
        nodes=[
            NodeInvocation(
                alias="set",
                node_id="scientist.node_set_state@1.0.0",
                params={"key": "foo", "value": "bar", "limit": Decimal("10")},
            ),
            NodeInvocation(
                alias="noop",
                node_id="scientist.node_noop@1.0.0",
                depends_on=["set"],
            ),
        ],
    )

    dumped = spec.model_dump_json()
    restored = WorkflowSpec.model_validate_json(dumped)
    assert restored == spec

    to_canonical_bytes(spec.model_dump())
