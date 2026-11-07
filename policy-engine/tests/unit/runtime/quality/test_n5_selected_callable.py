"""Keep the selected numerical callable bound to its N5 capture."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.core.artifacts import ArtifactRef
from polisyos.foundry.methods.catalog.causal.ncm_engine import NCMEngineMethod
from polisyos.runtime.quality import n5_execution_basis as basis
from polisyos.runtime.quality.joint_simulation_horizon import (
    HorizonSpec,
    JointSimulationHorizonController,
)
from tests.unit.runtime.quality.test_joint_simulation_horizon import _request


def test_ncm_capture_keeps_invoked_callable_when_binding_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A replaced class binding cannot turn the held selected call into a witness."""
    selected = NCMEngineMethod.pure_step
    constructor = basis.N5ImplementationCapture.__init__
    captures: list[basis.N5ImplementationCapture] = []

    def substitute(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise AssertionError("the substituted class binding must never execute")

    def initialize(capture: basis.N5ImplementationCapture, **kwargs: Any) -> None:
        assert kwargs["selected_step"] is selected
        with monkeypatch.context() as changed:
            changed.setattr(NCMEngineMethod, "pure_step", staticmethod(substitute))
            constructor(capture, **kwargs)
            assert capture._entry is selected
            assert capture._supported is False
        assert NCMEngineMethod.pure_step is selected
        captures.append(capture)

    monkeypatch.setattr(basis.N5ImplementationCapture, "__init__", initialize)
    request = _request().model_copy(update={"horizon": HorizonSpec(start=0, end=0, step=1)})
    controller = JointSimulationHorizonController()
    result = controller.run(request)
    assert len(captures) == 1
    capture = captures[0]
    assert capture._entry is selected
    assert capture._supported is False
    assert "n5_selected_implementation_or_input_unsupported" in capture._reasons
    assert NCMEngineMethod.pure_step is selected
    joint = result.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    assert joint.points[-1].outcomes["firm_survival"] == pytest.approx(11.0)
    assert result.interaction_terms[0].by_step[0] == pytest.approx(5.0)

    # Isolate the capture gate after the real controller execution. The fake
    # input owner and observer cannot establish authority or numerical reuse.
    input_ref = ArtifactRef(
        artifact_id="sha256:" + "a" * 64,
        kind="n5_input",
        media_type="application/json",
    )
    capture._admission = SimpleNamespace(input_ref=input_ref)
    capture._observer = SimpleNamespace(completed=True, reason=None)
    capture._codes = {0: SimpleNamespace(code=selected.__code__)}
    monkeypatch.setattr(capture, "_current_implementation", lambda: {})
    witness = capture.seal(input_ref=input_ref, result=result)
    assert witness.predicate_provenance == "not_established"
    assert "n5_selected_implementation_or_input_unsupported" in witness.reason_codes
    assert witness.content_hash not in basis._ISSUED
