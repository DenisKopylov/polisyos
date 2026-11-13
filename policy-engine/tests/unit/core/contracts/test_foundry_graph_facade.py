"""The stable graph facade exposes the actual Foundry-owned DTO classes."""

from __future__ import annotations

import polisyos.core.contracts as contracts
from polisyos.core.contracts import ProgramEdge, ProgramOp
from polisyos.core.contracts import foundry as owner


def test_program_graph_facade_preserves_owner_class_identity() -> None:
    """Both public imports retain the original classes and JSON contracts."""
    assert ProgramEdge is owner.ProgramEdge
    assert ProgramOp is owner.ProgramOp
    assert {"ProgramEdge", "ProgramOp"} <= set(contracts.__all__)
    edge = ProgramEdge(src="first", dst="second")
    op = ProgramOp(op_kind="check_constraints", params={"constraint_ids": ["a"]})
    assert owner.ProgramEdge.model_validate_json(edge.model_dump_json()) == edge
    assert owner.ProgramOp.model_validate_json(op.model_dump_json()) == op
