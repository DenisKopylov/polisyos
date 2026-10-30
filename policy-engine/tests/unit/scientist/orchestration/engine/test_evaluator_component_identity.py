"""Pin the evaluator used in the governance gate's source transition."""

from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.scientist.nodes.builtins.planning.run_evaluator import RunEvaluatorNode
from polisyos.scientist.orchestration.engine import component_identity
from polisyos.scientist.orchestration.engine.component_identity import (
    capture_engine_component_identity,
    matches_engine_component_identity,
)


def test_evaluator_identity_binds_real_code_and_rejects_counterfeits(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    node = RunEvaluatorNode()
    component_id = str(node.spec.metadata.component_id)
    identity = capture_engine_component_identity(node, component_id, {})
    assert identity is not None
    assert matches_engine_component_identity(identity, component_id, {})
    assert capture_engine_component_identity(object(), component_id, {}) is None
    assert not matches_engine_component_identity(identity, component_id, {"foreign": True})

    with monkeypatch.context() as changed:
        changed.setattr(RunEvaluatorNode, "execute", lambda *_args: None)
        assert capture_engine_component_identity(node, component_id, {}) is None
        assert not matches_engine_component_identity(identity, component_id, {})

    assert matches_engine_component_identity(identity, component_id, {})
    altered_source = tmp_path / "changed_evaluator_source.py"
    altered_source.write_text("# selected source differs from the imported evaluator\n")
    source_lookup = component_identity.inspect.getsourcefile
    with monkeypatch.context() as changed:
        changed.setattr(
            component_identity.inspect,
            "getsourcefile",
            lambda value: str(altered_source)
            if value is RunEvaluatorNode
            else source_lookup(value),
        )
        assert capture_engine_component_identity(node, component_id, {}) is None
        assert not matches_engine_component_identity(identity, component_id, {})

    assert matches_engine_component_identity(identity, component_id, {})
    with monkeypatch.context() as removed:
        removed.delitem(component_identity._OWNERS, component_id)
        assert capture_engine_component_identity(node, component_id, {}) is None
        assert not matches_engine_component_identity(identity, component_id, {})
