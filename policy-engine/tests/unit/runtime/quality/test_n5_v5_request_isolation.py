"""Keep the revalidated V5 request isolated from the caller's aliases."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from polisyos.core.artifacts import ArtifactRef
from polisyos.runtime.quality import n5_execution_basis as basis
from polisyos.runtime.quality.generation_cycle import JointSimulationPort
from polisyos.runtime.quality.generation_source import GenerationSourceRepository
from polisyos.runtime.quality.joint_simulation_horizon import HorizonSpec
from tests.unit.runtime.quality.test_joint_simulation_horizon import _request


def test_v5_rebuilt_request_survives_original_alias_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The controller consumes its owner-rebuilt request and detached world model."""
    original = _request().model_copy(update={"horizon": HorizonSpec(start=0, end=0, step=1)})
    source_template = original.model_copy(
        deep=True, update={"world_model_record": original.world_model_record}
    )
    port = JointSimulationPort()
    port._artifact_store = object()
    port._candidate_simulation_handoff = SimpleNamespace(
        job_id="job", run_id="run", tenant_id="tenant", cell_id="cell"
    )
    record = SimpleNamespace(content_hash="sha256:" + "b" * 64)
    ref = ArtifactRef(
        artifact_id="sha256:" + "a" * 64,
        kind="n5_input",
        media_type="application/json",
    )

    # The selected CAS reader and request builder are replaced only to isolate
    # the request handoff. The controller and NCM calculation remain real.
    def resolve(_repository: object, **kwargs: object) -> object:
        assert kwargs["ref"] == ref
        assert kwargs["expected_job_id"] == "job"
        return record

    def build(_port: object, **kwargs: object) -> object:
        assert kwargs["input_record"] is record
        return source_template.model_copy(
            deep=True, update={"world_model_record": original.world_model_record}
        )

    def implementation_unavailable(_capture: object) -> object:
        raise ValueError("n5_test_implementation_provenance_unavailable")

    monkeypatch.setattr(GenerationSourceRepository, "resolve_candidate_simulation_v5", resolve)
    monkeypatch.setattr(JointSimulationPort, "_build_candidate_simulation_request", build)
    monkeypatch.setattr(
        basis.N5ImplementationCapture, "_current_implementation", implementation_unavailable
    )
    candidate, problem = object(), object()
    stale = original.model_copy(deep=True)
    stale.baseline_state["income_delta"] = 999.0
    with (
        pytest.raises(ValueError, match="n5_implementation_input_request_mismatch"),
        basis.observe_candidate_n5_execution_input(
            port=port, candidate=candidate, problem=problem, request=stale, input_ref=ref
        ),
    ):
        pass

    with basis.observe_candidate_n5_execution_input(
        port=port, candidate=candidate, problem=problem, request=original, input_ref=ref
    ) as admitted:
        assert admitted is not original
        assert admitted.world_model_record is not original.world_model_record
        assert basis._ACTIVE_INPUT.get().request is admitted
        admitted_bytes = basis.exact_n5_content_bytes(admitted)
        equation = original.engine_plan[0].ncm_spec.structural_equations[-1]
        expression = equation.equation_params["noise_expression"]
        domain = original.world_model_record.policy_domain
        try:
            original.baseline_state["income_delta"] = 999.0
            equation.equation_params["noise_expression"] = "1000.0"
            object.__setattr__(original.world_model_record, "policy_domain", "foreign")
            assert basis.exact_n5_content_bytes(admitted) == admitted_bytes
            result = port._controller.run(admitted)
            assert basis.exact_n5_content_bytes(admitted) == admitted_bytes
        finally:
            equation.equation_params["noise_expression"] = expression
            object.__setattr__(original.world_model_record, "policy_domain", domain)

    capture = port._controller._last_n5_implementation_capture
    assert capture._admission.request is admitted
    assert "n5_test_implementation_provenance_unavailable" in capture._reasons
    joint = result.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    assert joint.points[-1].outcomes["firm_survival"] == pytest.approx(11.0)
    assert result.interaction_terms[0].by_step[0] == pytest.approx(5.0)
    assert result.world_model_record_content_hash == admitted.world_model_record.content_hash
