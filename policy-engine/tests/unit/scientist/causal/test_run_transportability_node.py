from __future__ import annotations

import importlib.util
import logging

import pytest

_Y0_INSTALLED = importlib.util.find_spec("y0") is not None

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.data_forge.domains.catalog.knowledge.proxy_resolver import ProxyCandidate, ProxyChain
from polisyos.data_forge.domains.catalog.knowledge.types import PStarZResult
from polisyos.ir.analytics.causal import (
    CausalEffectReport,
    CausalMethod,
    EstimationStatus,
    load_causal_effect_report,
    persist_causal_effect_report,
)
from polisyos.ir.analytics.causal_ensemble import (
    CausalModelEnsemble,
    EnsembleMember,
    persist_causal_model_ensemble,
)
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    GraphType,
    persist_causal_graph_model,
)
from polisyos.ir.analytics.context import ContextProfile, IncomeLevel
from polisyos.ir.analytics.privacy_transportability import (
    PrivacyAwareTransportCertificate,
    PrivacyObservedMode,
    load_privacy_aware_transport_certificate,
)
from polisyos.ir.analytics.transportability import (
    StratificationVariable,
    TransportabilityResult,
    TransportabilityStatus,
    TransportFormula,
    TransportMode,
    load_transportability_result,
)
from polisyos.ir.refs import PrivacyAwareTransportCertificateRef
from polisyos.lex.legal_evaluation.transport_constraints import (
    ConstraintSeverity,
    LegalConstraint,
    LegalConstraintSet,
)
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.causal.resolve_transport import (
    RunTransportabilityNode,
    TransportabilityResolutionLoop,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_ENSEMBLE_REF,
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
    ARTIFACT_TRANSPORTABILITY_RESULT_REF,
)


def _build_ctx(tmp_path, *, run_id: str) -> ExecutionContext:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id=run_id)
    return ExecutionContext(store=store, run=run, logger=logging.getLogger(f"test.{run_id}"))


def _blocked_privacy_transport_certificate() -> PrivacyAwareTransportCertificate:
    return PrivacyAwareTransportCertificate(
        certificate_id="transport_node_privacy_blocked",
        query="P*(gdp_growth|do(tax_rate))",
        selection_diagram_ref="selection_diagram:test",
        latent_transport_status=TransportabilityStatus.IDENTIFIED,
        privacy_observed_mode=PrivacyObservedMode.BLOCKED,
        source_domains=("DE",),
        target_domain="DE",
        blocking_reasons=("privacy_transport_blocked",),
        assumptions=("test_privacy_gate",),
    )


def _base_report() -> CausalEffectReport:
    return CausalEffectReport(
        method=CausalMethod.DOWHY_BACKDOOR,
        status=EstimationStatus.SUCCESS,
        estimand="ATE",
        point_estimate=1.0,
        confidence_interval=(0.8, 1.2),
        inference_method="backdoor.linear_regression",
        sample_size=100,
        n_treated=50,
        n_control=50,
        pre_periods=0,
        post_periods=0,
        method_params={"treatment": "tax_rate", "outcome": "gdp_growth"},
    )


def _mediator_graph() -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["tax_rate", "tax_compliance", "gdp_growth"],
        edges=[
            CausalEdge(src="tax_rate", dst="tax_compliance"),
            CausalEdge(src="tax_compliance", dst="gdp_growth"),
        ],
    )


class _MissingDatasetRegistry:
    def find_datasets_for_variable(
        self,
        canonical_var: str,
        country_code: str,
        year_range: tuple[int, int] | None = None,
    ) -> list[object]:
        del canonical_var, country_code, year_range
        return []

    def compute_p_star_z(
        self,
        canonical_var: str,
        country_code: str,
        year: int,
        *,
        condition_on: dict[str, float] | None = None,
    ) -> PStarZResult:
        del country_code, year
        return PStarZResult(
            canonical_variable=canonical_var,
            value=None,
            dataset_id=None,
            raw_variable=None,
            is_proxy=False,
            confidence=0.0,
            penalty_breakdown={"missing": 1.0},
            is_conditional=bool(condition_on),
            condition_on=condition_on or {},
        )


def test_run_transportability_node_graceful_skip_without_source_context(tmp_path) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_transport_skip")
    report_ref = persist_causal_effect_report(ctx.store, _base_report())
    graph_ref = persist_causal_graph_model(ctx.store, _mediator_graph())

    state = ExperimentState(
        run_id="R_transport_skip",
        artifacts_index={
            ARTIFACT_CAUSAL_REPORT_REF: report_ref,
            ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref,
        },
        params={"target_context": {"context_id": "UA", "income_level": "lower_middle"}},
    )

    outcome = RunTransportabilityNode().execute(ctx, state)

    assert outcome.status == "skip"
    assert "transportability_warning" in outcome.state.params


@pytest.mark.parametrize("execution_profile", ["research", "governed", "production"])
def test_run_transportability_rejects_degraded_transport_outside_dev(
    tmp_path,
    execution_profile: str,
) -> None:
    ctx = _build_ctx(tmp_path, run_id=f"R_transport_strict_{execution_profile}")
    report_ref = persist_causal_effect_report(ctx.store, _base_report())
    graph_ref = persist_causal_graph_model(ctx.store, _mediator_graph())
    profile = {"context_id": "DE", "income_level": "high", "institutional_quality": 0.8}
    state = ExperimentState(
        run_id=f"R_transport_strict_{execution_profile}",
        artifacts_index={
            ARTIFACT_CAUSAL_REPORT_REF: report_ref,
            ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref,
        },
        params={
            "source_context": profile,
            "target_context": profile,
            "query_treatment": "tax_rate",
            "query_outcome": "gdp_growth",
            "allow_degraded_transport": True,
        },
        execution_profile=execution_profile,
    )

    outcome = RunTransportabilityNode().execute(ctx, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "node.invalid_state"
    assert "forbidden outside the dev execution profile" in outcome.error.message


def test_resolution_loop_hard_legal_constraint_sets_infeasible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_constraints(**kwargs):
        del kwargs
        hard = LegalConstraint(
            constraint_id="ua_tax_retroactive_ban",
            description="Retroactive policy application is prohibited.",
            jurisdiction="UA",
            legal_source="UA:legal_kg",
            severity=ConstraintSeverity.HARD,
            affects_mechanism=True,
        )
        return LegalConstraintSet(
            jurisdiction="UA",
            policy_domain="tax_policy",
            hard_constraints=[hard],
            soft_constraints=[],
            data_license_constraints=[],
            legal_dag_mappings=[],
        )

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.resolve_transport.evaluate_transport_constraints",
        _fake_constraints,
    )

    loop = TransportabilityResolutionLoop(
        dataset_registry=_MissingDatasetRegistry(),
        legal_kg_db_path=None,
        skg_query=object(),
    )
    source = ContextProfile(context_id="DE", income_level=IncomeLevel.HIGH)
    target = ContextProfile(context_id="UA", income_level=IncomeLevel.LOWER_MIDDLE)

    result = loop.resolve(
        source_context=source,
        target_context=target,
        causal_graph=_mediator_graph(),
        query_treatment="tax_rate",
        query_outcome="gdp_growth",
        policy_spec={"domain": "tax_policy", "retroactive": True},
    )

    assert result.feasible is False
    assert result.final_confidence == 0.0
    assert result.hard_legal_constraints


@pytest.mark.skipif(
    _Y0_INSTALLED,
    reason="y0 is installed — symbolic identification succeeds; test verifies bounds fallback when unavailable",
)
def test_resolution_loop_data_gap_and_convergence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _no_constraints(**kwargs):
        del kwargs
        return LegalConstraintSet(
            jurisdiction="UA",
            policy_domain="tax_policy",
            hard_constraints=[],
            soft_constraints=[],
            data_license_constraints=[],
            legal_dag_mappings=[],
        )

    def _low_proxy(*args, **kwargs):
        del args, kwargs
        return ProxyChain(
            target_variable="tax_compliance",
            proxies=[
                ProxyCandidate(
                    proxy_variable="cpi_score",
                    proxy_dataset_id="TI_CPI",
                    proxy_raw_name="cpi_score",
                    base_correlation=0.4,
                    context_adjustment=0.5,
                    effective_confidence=0.2,
                    source="seed_table",
                )
            ],
            best_single_confidence=0.2,
        )

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.resolve_transport.evaluate_transport_constraints",
        _no_constraints,
    )
    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.resolve_transport.resolve_proxy",
        _low_proxy,
    )

    loop = TransportabilityResolutionLoop(
        dataset_registry=_MissingDatasetRegistry(),
        legal_kg_db_path=None,
        skg_query=object(),
    )
    source = ContextProfile(
        context_id="DE",
        income_level=IncomeLevel.HIGH,
        institutional_quality=0.85,
    )
    target = ContextProfile(
        context_id="UA",
        income_level=IncomeLevel.LOWER_MIDDLE,
        institutional_quality=0.35,
        time_period="2020-2024",
    )

    result = loop.resolve(
        source_context=source,
        target_context=target,
        causal_graph=_mediator_graph(),
        query_treatment="tax_rate",
        query_outcome="gdp_growth",
    )

    assert result.feasible is True
    assert result.resolution_rounds <= 3
    assert result.status is TransportabilityStatus.BOUNDED_NON_IDENTIFIED
    assert result.partial_identification_result is not None
    assert (
        "Exact transport identification unavailable; emitted transport-aware bounds fallback."
        in result.warnings
    )


def test_resolution_loop_without_privacy_context_does_not_crash() -> None:
    loop = TransportabilityResolutionLoop(
        dataset_registry=_MissingDatasetRegistry(),
        legal_kg_db_path=None,
        skg_query=object(),
    )
    profile = ContextProfile(
        context_id="DE",
        income_level=IncomeLevel.HIGH,
        institutional_quality=0.8,
    )

    result = loop.resolve(
        source_context=profile,
        target_context=profile,
        causal_graph=_mediator_graph(),
        query_treatment="tax_rate",
        query_outcome="gdp_growth",
    )

    assert result.status is TransportabilityStatus.IDENTIFIED
    assert result.metadata.get("privacy_observed_mode") is None


def test_run_transportability_node_updates_causal_report(tmp_path) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_transport_ok")
    report_ref = persist_causal_effect_report(ctx.store, _base_report())
    graph_ref = persist_causal_graph_model(ctx.store, _mediator_graph())

    profile = {"context_id": "DE", "income_level": "high", "institutional_quality": 0.8}
    state = ExperimentState(
        run_id="R_transport_ok",
        artifacts_index={
            ARTIFACT_CAUSAL_REPORT_REF: report_ref,
            ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref,
        },
        params={
            "source_context": profile,
            "target_context": profile,
            "query_treatment": "tax_rate",
            "query_outcome": "gdp_growth",
        },
    )

    outcome = RunTransportabilityNode().execute(ctx, state)

    assert outcome.status == "ok"
    assert ARTIFACT_TRANSPORTABILITY_RESULT_REF in outcome.state.artifacts_index
    updated_ref = outcome.state.artifacts_index[ARTIFACT_CAUSAL_REPORT_REF]
    updated = load_causal_effect_report(ctx.store, updated_ref)
    assert updated.transport_result is not None
    assert updated.transport_result.status is TransportabilityStatus.IDENTIFIED


def test_run_transportability_node_applies_store_backed_blocked_privacy_gate(tmp_path) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_transport_privacy_blocked")
    report_ref = persist_causal_effect_report(ctx.store, _base_report())
    graph_ref = persist_causal_graph_model(ctx.store, _mediator_graph())

    profile = {"context_id": "DE", "income_level": "high", "institutional_quality": 0.8}
    state = ExperimentState(
        run_id="R_transport_privacy_blocked",
        artifacts_index={
            ARTIFACT_CAUSAL_REPORT_REF: report_ref,
            ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref,
        },
        params={
            "source_context": profile,
            "target_context": profile,
            "query_treatment": "tax_rate",
            "query_outcome": "gdp_growth",
            "privacy_transport_certificate": _blocked_privacy_transport_certificate().model_dump(
                mode="json"
            ),
        },
    )

    outcome = RunTransportabilityNode().execute(ctx, state)

    assert outcome.status == "ok"
    transport_ref = outcome.state.artifacts_index[ARTIFACT_TRANSPORTABILITY_RESULT_REF]
    transport_result = load_transportability_result(ctx.store, transport_ref)
    assert transport_result.status is TransportabilityStatus.UNSUPPORTED
    assert transport_result.transport_mode is TransportMode.NONE
    assert transport_result.transport_formula is None
    assert transport_result.unsupported_reason == "privacy_transport_blocked"
    assert transport_result.metadata["privacy_observed_mode"] == "blocked"
    privacy_ref_payload = transport_result.metadata["privacy_certificate_ref"]
    assert privacy_ref_payload is not None
    privacy_ref = PrivacyAwareTransportCertificateRef.model_validate(privacy_ref_payload)
    loaded_privacy_certificate = load_privacy_aware_transport_certificate(ctx.store, privacy_ref)
    assert loaded_privacy_certificate.privacy_observed_mode is PrivacyObservedMode.BLOCKED
    assert loaded_privacy_certificate.blocking_reasons == ("privacy_transport_blocked",)


def test_run_transportability_uses_ensemble_consensus_graph_when_available(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_transport_ensemble_graph")
    report_ref = persist_causal_effect_report(ctx.store, _base_report())

    reconciled_graph_ref = persist_causal_graph_model(
        ctx.store,
        CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=["reconciled_X", "reconciled_Y"],
            edges=[CausalEdge(src="reconciled_X", dst="reconciled_Y")],
        ),
    )
    consensus_graph_ref = persist_causal_graph_model(
        ctx.store,
        CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=["consensus_X", "consensus_Y"],
            edges=[CausalEdge(src="consensus_X", dst="consensus_Y")],
        ),
    )
    ensemble_ref = persist_causal_model_ensemble(
        ctx.store,
        CausalModelEnsemble(
            members=[
                EnsembleMember(
                    graph_ref=str(consensus_graph_ref.artifact_id),
                    discovery_method="pc",
                    weight=1.0,
                    bootstrap_stability=0.9,
                )
            ],
            consensus_graph_ref=str(consensus_graph_ref.artifact_id),
            edge_inclusion_frequency={"consensus_X→consensus_Y": 1.0},
        ),
    )

    captured_nodes: dict[str, list[str]] = {}

    def _fake_solver(**kwargs):
        diagram = kwargs["diagram"]
        captured_nodes["nodes"] = list(diagram.base_graph.nodes)
        result = TransportabilityResult(
            query="P*(Y|do(X))",
            status=TransportabilityStatus.IDENTIFIED,
            final_confidence=1.0,
            source_context_id=diagram.source_context.context_id,
            target_context_id=diagram.target_context.context_id,
        )
        return {"transport_result": result.model_dump(mode="json")}

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.resolve_transport._run_transport_solver",
        _fake_solver,
    )

    profile = {"context_id": "DE", "income_level": "high", "institutional_quality": 0.8}
    state = ExperimentState(
        run_id="R_transport_ensemble_graph",
        artifacts_index={
            ARTIFACT_CAUSAL_REPORT_REF: report_ref,
            ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: reconciled_graph_ref,
            ARTIFACT_CAUSAL_ENSEMBLE_REF: ensemble_ref,
        },
        params={
            "source_context": profile,
            "target_context": profile,
            "query_treatment": "tax_rate",
            "query_outcome": "gdp_growth",
        },
    )

    outcome = RunTransportabilityNode().execute(ctx, state)

    assert outcome.status == "ok"
    assert captured_nodes["nodes"] == ["consensus_X", "consensus_Y"]


def test_run_transportability_symbolic_mode_records_backend_issue(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_transport_symbolic_unavailable")
    report_ref = persist_causal_effect_report(ctx.store, _base_report())
    graph_ref = persist_causal_graph_model(ctx.store, _mediator_graph())

    def _fake_solver(**kwargs):
        diagram = kwargs["diagram"]
        result = TransportabilityResult(
            query="P*(gdp_growth|do(tax_rate))",
            status=TransportabilityStatus.UNSUPPORTED,
            transport_mode=TransportMode.NONE,
            final_confidence=0.0,
            source_context_id=diagram.source_context.context_id,
            target_context_id=diagram.target_context.context_id,
            identification_engine="y0",
            identification_trace=["symbolic_backend_unavailable:y0_unavailable"],
            unsupported_reason="y0_unavailable",
            warnings=["Symbolic backend unavailable; y0 is not installed."],
        )
        return {"transport_result": result.model_dump(mode="json")}

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.resolve_transport._run_transport_solver",
        _fake_solver,
    )

    profile = {"context_id": "DE", "income_level": "high", "institutional_quality": 0.8}
    state = ExperimentState(
        run_id="R_transport_symbolic_unavailable",
        artifacts_index={
            ARTIFACT_CAUSAL_REPORT_REF: report_ref,
            ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref,
        },
        params={
            "source_context": profile,
            "target_context": profile,
            "query_treatment": "tax_rate",
            "query_outcome": "gdp_growth",
            "transport_solver_mode": "symbolic",
        },
    )

    outcome = RunTransportabilityNode().execute(ctx, state)

    assert outcome.status == "ok"
    updated_ref = outcome.state.artifacts_index[ARTIFACT_CAUSAL_REPORT_REF]
    updated = load_causal_effect_report(ctx.store, updated_ref)
    assert updated.transport_result is not None
    assert updated.transport_result.identification_engine == "y0"
    assert updated.transport_result.unsupported_reason == "y0_unavailable"
    assert outcome.state.params["transportability_identification_engine"] == "y0"


@pytest.mark.parametrize(
    "solver_mode",
    [
        "symbolic_r",
        "full_auto",
        "auto",
    ],
)
def test_run_transportability_solver_mode_maps_symbolic_backend_params(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    solver_mode: str,
) -> None:
    ctx = _build_ctx(tmp_path, run_id=f"R_transport_solver_mode_{solver_mode}")
    report_ref = persist_causal_effect_report(ctx.store, _base_report())
    graph_ref = persist_causal_graph_model(ctx.store, _mediator_graph())

    captured_params: dict[str, object] = {}

    def _fake_solver(**kwargs):
        captured_params.update(kwargs)
        diagram = kwargs["diagram"]
        result = TransportabilityResult(
            query="P*(gdp_growth|do(tax_rate))",
            status=TransportabilityStatus.UNSUPPORTED,
            transport_mode=TransportMode.NONE,
            final_confidence=0.0,
            source_context_id=diagram.source_context.context_id,
            target_context_id=diagram.target_context.context_id,
            identification_engine="y0",
            identification_trace=["symbolic_backend_unavailable:test_probe"],
            unsupported_reason="test_probe",
        )
        return {"transport_result": result.model_dump(mode="json")}

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.resolve_transport._run_transport_solver",
        _fake_solver,
    )

    profile = {"context_id": "DE", "income_level": "high", "institutional_quality": 0.8}
    state = ExperimentState(
        run_id=f"R_transport_solver_mode_{solver_mode}",
        artifacts_index={
            ARTIFACT_CAUSAL_REPORT_REF: report_ref,
            ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref,
        },
        params={
            "source_context": profile,
            "target_context": profile,
            "query_treatment": "tax_rate",
            "query_outcome": "gdp_growth",
            "transport_solver_mode": solver_mode,
        },
    )

    outcome = RunTransportabilityNode().execute(ctx, state)
    assert outcome.status == "ok"
    assert captured_params["solver_mode"] == solver_mode
    assert captured_params["allow_degraded_transport"] is False
    assert captured_params["capability_contract"] is not None


def test_resolution_loop_emits_outer_search_budget_events_when_truncated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _no_constraints(**kwargs):
        del kwargs
        return LegalConstraintSet(
            jurisdiction="UA",
            policy_domain="tax_policy",
            hard_constraints=[],
            soft_constraints=[],
            data_license_constraints=[],
            legal_dag_mappings=[],
        )

    def _fake_solver(**kwargs):
        diagram = kwargs["diagram"]
        result = TransportabilityResult(
            query="P*(gdp_growth|do(tax_rate))",
            status=TransportabilityStatus.IDENTIFIED,
            transport_formula=TransportFormula(
                formula_str="synthetic",
                stratification_variables=["z1", "z2", "z3"],
                stratification_details=[
                    StratificationVariable(
                        name="z1",
                        role="mediator",
                        requires_conditional=False,
                    ),
                    StratificationVariable(
                        name="z2",
                        role="mediator",
                        requires_conditional=False,
                    ),
                    StratificationVariable(
                        name="z3",
                        role="mediator",
                        requires_conditional=False,
                    ),
                ],
                source_quantities=["P(Y|do(X),z1)", "P(Y|do(X),z2)", "P(Y|do(X),z3)"],
                target_quantities=["P*(z1)", "P*(z2)", "P*(z3)"],
                adjustment_type="stratification",
            ),
            final_confidence=0.8,
            source_context_id=diagram.source_context.context_id,
            target_context_id=diagram.target_context.context_id,
        )
        return {"transport_result": result.model_dump(mode="json")}

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.resolve_transport.evaluate_transport_constraints",
        _no_constraints,
    )
    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.resolve_transport._run_transport_solver",
        _fake_solver,
    )

    loop = TransportabilityResolutionLoop(
        dataset_registry=_MissingDatasetRegistry(),
        legal_kg_db_path=None,
        skg_query=object(),
    )
    source = ContextProfile(
        context_id="DE",
        income_level=IncomeLevel.HIGH,
        institutional_quality=0.9,
    )
    target = ContextProfile(
        context_id="UA",
        income_level=IncomeLevel.LOWER_MIDDLE,
        institutional_quality=0.2,
    )
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["tax_rate", "gdp_growth", "z1", "z2", "z3"],
        edges=[
            CausalEdge(src="tax_rate", dst="z1"),
            CausalEdge(src="tax_rate", dst="z2"),
            CausalEdge(src="tax_rate", dst="z3"),
            CausalEdge(src="z1", dst="gdp_growth"),
            CausalEdge(src="z2", dst="gdp_growth"),
            CausalEdge(src="z3", dst="gdp_growth"),
        ],
    )

    result = loop.resolve(
        source_context=source,
        target_context=target,
        causal_graph=graph,
        query_treatment="tax_rate",
        query_outcome="gdp_growth",
    )

    assert result.outer_search_truncated is True
    assert result.search_budget_exhausted is True
    assert "outer_search_truncated" in result.search_events
    assert "search_budget_exhausted" in result.search_events


def test_resolution_loop_proxy_exclusion_violation_requires_expert_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _no_constraints(**kwargs):
        del kwargs
        return LegalConstraintSet(
            jurisdiction="UA",
            policy_domain="tax_policy",
            hard_constraints=[],
            soft_constraints=[],
            data_license_constraints=[],
            legal_dag_mappings=[],
        )

    def _fake_proxy(*args, **kwargs):
        del args, kwargs
        return ProxyChain(
            target_variable="tax_compliance",
            proxies=[
                ProxyCandidate(
                    proxy_variable="proxy_direct",
                    proxy_dataset_id="PX1",
                    proxy_raw_name="proxy_direct_raw",
                    base_correlation=0.85,
                    context_adjustment=0.8,
                    effective_confidence=0.82,
                    source="seed_table",
                )
            ],
            best_single_confidence=0.82,
        )

    def _fake_solver(**kwargs):
        diagram = kwargs["diagram"]
        result = TransportabilityResult(
            query="P*(gdp_growth|do(tax_rate))",
            status=TransportabilityStatus.IDENTIFIED,
            transport_formula=TransportFormula(
                formula_str="synthetic_proxy",
                stratification_variables=["tax_compliance"],
                stratification_details=[
                    StratificationVariable(
                        name="tax_compliance",
                        role="mediator",
                        requires_conditional=False,
                    )
                ],
                source_quantities=["P(Y|do(X),tax_compliance)"],
                target_quantities=["P*(tax_compliance)"],
                adjustment_type="stratification",
            ),
            final_confidence=0.75,
            source_context_id=diagram.source_context.context_id,
            target_context_id=diagram.target_context.context_id,
        )
        return {"transport_result": result.model_dump(mode="json")}

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.resolve_transport.evaluate_transport_constraints",
        _no_constraints,
    )
    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.resolve_transport.resolve_proxy",
        _fake_proxy,
    )
    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.resolve_transport._run_transport_solver",
        _fake_solver,
    )

    loop = TransportabilityResolutionLoop(
        dataset_registry=_MissingDatasetRegistry(),
        legal_kg_db_path=None,
        skg_query=object(),
    )
    source = ContextProfile(context_id="DE", income_level=IncomeLevel.HIGH)
    target = ContextProfile(context_id="UA", income_level=IncomeLevel.LOWER_MIDDLE)
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["tax_rate", "gdp_growth", "tax_compliance", "proxy_direct"],
        edges=[
            CausalEdge(src="tax_rate", dst="tax_compliance"),
            CausalEdge(src="tax_compliance", dst="gdp_growth"),
            CausalEdge(src="proxy_direct", dst="tax_compliance"),
            CausalEdge(src="proxy_direct", dst="gdp_growth"),
        ],
    )

    result = loop.resolve(
        source_context=source,
        target_context=target,
        causal_graph=graph,
        query_treatment="tax_rate",
        query_outcome="gdp_growth",
    )

    assert result.requires_expert_review is True
    assert result.expert_review_reasons
    assert "tax_compliance" in result.proxy_validity
    assert result.proxy_validity["tax_compliance"]["exclusion_check"] is False


def test_resolution_loop_non_transportable_adds_manski_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _no_constraints(**kwargs):
        del kwargs
        return LegalConstraintSet(
            jurisdiction="UA",
            policy_domain="tax_policy",
            hard_constraints=[],
            soft_constraints=[],
            data_license_constraints=[],
            legal_dag_mappings=[],
        )

    def _fake_solver(**kwargs):
        diagram = kwargs["diagram"]
        result = TransportabilityResult(
            query="P*(gdp_growth|do(tax_rate))",
            status=TransportabilityStatus.UNSUPPORTED,
            transport_mode=TransportMode.NONE,
            final_confidence=0.0,
            source_context_id=diagram.source_context.context_id,
            target_context_id=diagram.target_context.context_id,
            unsupported_reason="synthetic_non_transportable",
        )
        return {"transport_result": result.model_dump(mode="json")}

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.resolve_transport.evaluate_transport_constraints",
        _no_constraints,
    )
    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.resolve_transport._run_transport_solver",
        _fake_solver,
    )

    loop = TransportabilityResolutionLoop(
        dataset_registry=_MissingDatasetRegistry(),
        legal_kg_db_path=None,
        skg_query=object(),
    )
    source = ContextProfile(context_id="DE", income_level=IncomeLevel.HIGH)
    target = ContextProfile(context_id="UA", income_level=IncomeLevel.LOWER_MIDDLE)

    result = loop.resolve(
        source_context=source,
        target_context=target,
        causal_graph=_mediator_graph(),
        query_treatment="tax_rate",
        query_outcome="gdp_growth",
    )

    assert result.status is TransportabilityStatus.UNSUPPORTED
    assert result.partial_identification_result is not None
    assert result.partial_identification_result.method.value == "manski_bounds"
    assert "partial_identification_non_informative:manski_bounds" in result.warnings
