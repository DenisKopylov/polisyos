from __future__ import annotations

import pytest

from polisyos.foundry.methods.catalog.causal import (
    symbolic_identify as symbolic_module,
    transport_check as check_module,
    transport_engine as engine_module,
)
from polisyos.foundry.methods.catalog.causal.symbolic_identify import SymbolicIdentify
from polisyos.foundry.methods.catalog.causal.transport_check import CheckTransportability
from polisyos.ir.analytics.causal import ProofBundle
from polisyos.ir.analytics.causal_capabilities import (
    CausalBackendCapability,
    CausalBackendId,
    CausalCapabilityContract,
    CausalIdentificationFamily,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.context import ContextProfile, IncomeLevel
from polisyos.ir.analytics.transportability import (
    SelectionDiagram,
    SNode,
    SNodeOrigin,
    TransportabilityResult,
    TransportabilityStatus,
    TransportMode,
)


def _diagram(*, with_selection: bool) -> SelectionDiagram:
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "M", "Y"],
        edges=[CausalEdge(src="X", dst="M"), CausalEdge(src="M", dst="Y")],
    )
    return SelectionDiagram(
        base_graph=graph,
        s_nodes=(
            [
                SNode(
                    target_variable="M",
                    context_dimension="institutional_quality",
                    source_value=0.9,
                    target_value=0.2,
                    delta=0.7,
                    severity="high",
                    origin=SNodeOrigin.CONTEXT_DELTA,
                )
            ]
            if with_selection
            else []
        ),
        source_context=ContextProfile(
            context_id="DE", income_level=IncomeLevel.HIGH, institutional_quality=0.9
        ),
        target_context=ContextProfile(
            context_id="UA", income_level=IncomeLevel.LOWER_MIDDLE, institutional_quality=0.2
        ),
        context_distance=0.5,
    )


def _y0_contract(*families: CausalIdentificationFamily) -> CausalCapabilityContract:
    return CausalCapabilityContract(
        dependency_fingerprint="controlled-y0-contract",
        full_backend_order=[CausalBackendId.Y0],
        degradation_policy="explicit_only",
        backends=[
            CausalBackendCapability(
                backend_id=CausalBackendId.Y0,
                available=True,
                supported_families=list(families),
            )
        ],
        supported_families=list(families),
        disabled_families={},
        notes=[],
    )


def _limited_y0_result(reason: str) -> TransportabilityResult:
    return TransportabilityResult(
        query="P*(Y|do(X))",
        status=TransportabilityStatus.UNSUPPORTED,
        transport_mode=TransportMode.NONE,
        identification_engine="y0",
        unsupported_reason=reason,
        metadata={"backend_call_attempted": True, "backend_result": "not_returned"},
    )


def test_shared_solver_returns_the_y0_trso_result_without_local_heuristic_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    limited = _limited_y0_result("y0_trso_api_error:RuntimeError")
    monkeypatch.setattr(
        symbolic_module,
        "_run_y0_trso",
        lambda **_kwargs: (
            limited,
            ProofBundle(
                proof_status="oracle_needed",
                proof_stratum="A2_oracle_backed",
                theorem_family="y0:identify_target_outcomes",
                completeness_regime="sound_incomplete",
                implementation_coverage="y0_trso_expression_adapter",
                query_ref=limited.query,
            ),
        ),
    )
    monkeypatch.setattr(
        engine_module,
        "_try_tr_via_id_engine",
        lambda **_kwargs: pytest.fail("local TR heuristics must not run under the Y0 label"),
    )
    profile = {
        "schema_version": "policyos.y0.surrogate-data-profile.v1",
        "populations": [{"population_id": "pi1", "outcomes": ["Y"], "interventions": ["X"]}],
    }

    result = engine_module.solve_transportability(
        selection_diagram=_diagram(with_selection=True),
        query_treatment="X",
        query_outcome="Y",
        solver_mode="symbolic_y0",
        capability_contract=_y0_contract(CausalIdentificationFamily.TRSO),
        surrogate_data_profile=profile,
    )

    assert result.status is TransportabilityStatus.UNSUPPORTED
    assert result.identification_engine == "y0"
    assert result.unsupported_reason == "y0_trso_api_error:RuntimeError"
    assert result.transport_formula is None


def test_shared_solver_uses_y0_direct_operation_only_when_explicitly_selected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = TransportabilityResult(
        query="P*(Y|do(X))",
        status=TransportabilityStatus.IDENTIFIED,
        transport_mode=TransportMode.DIRECT,
        identification_engine="y0",
        requires_expert_review=True,
        expert_review_reasons=["source_data_authority_not_established"],
    )
    observed: list[str] = []

    def run_direct(**kwargs):
        observed.append(kwargs["outcome"])
        return candidate, ProofBundle(
            proof_status="identified",
            proof_stratum="A2_oracle_backed",
            theorem_family="y0:identify_outcomes",
            completeness_regime="sound_incomplete",
            implementation_coverage="y0_direct_id_adapter",
            query_ref=candidate.query,
        )

    monkeypatch.setattr(symbolic_module, "_y0_direct_result", run_direct)
    monkeypatch.setattr(
        engine_module, "_direct_result", lambda **_kwargs: pytest.fail("wrong fallback producer")
    )

    result = engine_module.solve_transportability(
        selection_diagram=_diagram(with_selection=False),
        query_treatment="X",
        query_outcome="Y",
        solver_mode="symbolic_y0",
        capability_contract=_y0_contract(CausalIdentificationFamily.DIRECT),
    )

    assert observed == ["Y"]
    assert result.identification_engine == "y0"
    assert result.status is TransportabilityStatus.IDENTIFIED
    assert result.requires_expert_review is True


def test_bounds_api_failure_does_not_fabricate_a_nonidentification_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    diagram = _diagram(with_selection=True)
    monkeypatch.setattr(
        engine_module,
        "transport_bounds",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("bounds unavailable")),
    )

    result = engine_module._run_bounds_only(
        diagram=diagram, treatment="X", outcome="Y", trace=["test"]
    )

    assert result.status is TransportabilityStatus.UNSUPPORTED
    assert result.unsupported_reason == "transport_bounds_api_error:RuntimeError"
    assert result.partial_identification_result is None


def test_check_transportability_explicit_y0_preserves_limitations_without_negative_certificate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    diagram = _diagram(with_selection=True)
    limited = _limited_y0_result("y0_surrogate_data_profile_null")
    captured: dict[str, object] = {}

    def fake_solver(**kwargs):
        captured.update(kwargs)
        return limited

    monkeypatch.setattr(check_module, "solve_transportability", fake_solver)
    profile = {
        "schema_version": "policyos.y0.surrogate-data-profile.v1",
        "populations": [{"population_id": "pi1", "outcomes": ["Y"], "interventions": ["X"]}],
    }
    payload = CheckTransportability.pure_step(
        state={
            "selection_diagram": diagram.model_dump(mode="json"),
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        params={
            "transport_solver_mode": "symbolic_y0",
            "surrogate_data_profile": profile,
        },
    )

    assert captured["solver_mode"] == "symbolic_y0"
    assert captured["surrogate_data_profile"] == profile
    assert "negative_certificate" not in payload
    assert payload["proof_bundle"]["proof_status"] == "oracle_needed"
    result = TransportabilityResult.model_validate(payload["transport_result"])
    assert result.status is TransportabilityStatus.UNSUPPORTED


def test_check_transportability_default_remains_simplified() -> None:
    parameter_defaults = {
        parameter.name: parameter.default
        for parameter in CheckTransportability.signature.parameters
    }
    assert parameter_defaults.get("transport_solver_mode") == "simplified"
    assert SymbolicIdentify.signature.parameters
