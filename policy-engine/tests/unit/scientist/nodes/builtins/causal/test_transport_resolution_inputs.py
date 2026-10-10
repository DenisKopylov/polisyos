"""Behavioral coverage for transport-resolution input and context helpers."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from polisyos.data_forge.read_api.academic import SKGQuery
from polisyos.data_forge.read_api.catalog import DatasetRegistry
from polisyos.ir.analytics.causal import CausalEffectReport, CausalMethod
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    GraphType,
    PAGIdentificationPolicy,
    persist_causal_graph_model,
)
from polisyos.ir.analytics.context import ContextProfile
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.causal.resolve_transport import RunTransportabilityNode
from polisyos.scientist.nodes.builtins.causal.transport_resolution_inputs import (
    InvalidTransportInput,
    _build_dataset_registry,
    _resolve_allow_degraded_transport,
    _resolve_causal_graph,
    _resolve_context_profile,
    _resolve_context_year,
    _resolve_or_build_capability_contract,
    _resolve_pag_identification_policy,
    _resolve_pag_max_dag_samples,
    _resolve_pag_seed,
    _resolve_pag_threshold,
    _resolve_query_outcome,
    _resolve_query_treatment,
    _resolve_transport_solver_mode,
    _resolve_treatment_value,
    build_skg_query,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_CAPABILITY_CONTRACT_REF,
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState


def _causal_report() -> CausalEffectReport:
    return CausalEffectReport(
        method=CausalMethod.DIFFERENCE_IN_DIFFERENCES,
        estimand="ATE",
        point_estimate=0.2,
        confidence_interval=(0.1, 0.3),
        inference_method="fixture",
        sample_size=20,
        n_treated=10,
        n_control=10,
        pre_periods=1,
        post_periods=1,
        method_params={"treatment_name": "report_policy", "outcome_name": "report_income"},
    )


def _causal_graph(graph_type: GraphType = GraphType.DAG) -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=graph_type,
        nodes=["policy", "outcome"],
        edges=[CausalEdge(src="policy", dst="outcome")],
    )


def test_query_subject_context_and_execution_profile_are_resolved_by_source_precedence() -> None:
    report = _causal_report()
    state = ExperimentState(
        run_id="query-source-precedence",
        params={"query_treatment": " run_policy ", "query_outcome": " run_income "},
    )
    assert _resolve_query_treatment(state, report) == "run_policy"
    assert _resolve_query_outcome(state, report) == "run_income"

    report_only = ExperimentState(run_id="query-report-fallback")
    assert _resolve_query_treatment(report_only, report) == "report_policy"
    assert _resolve_query_outcome(report_only, report) == "report_income"
    assert (
        _resolve_query_treatment(
            report_only,
            report.model_copy(update={"method_params": {}, "metadata": {}}),
        )
        == "treatment"
    )
    assert (
        _resolve_query_outcome(
            report_only,
            report.model_copy(update={"method_params": {}}),
        )
        == "outcome"
    )
    with pytest.raises(InvalidTransportInput, match="params.query_treatment"):
        _resolve_query_treatment(
            ExperimentState(run_id="invalid-query", params={"query_treatment": 9}),
            report,
        )
    with pytest.raises(InvalidTransportInput, match="report.method_params.treatment_name"):
        _resolve_query_treatment(
            report_only,
            report.model_copy(update={"method_params": {"treatment_name": []}}),
        )

    assert _resolve_treatment_value({"dose": "2.5"}) == 2.5
    with pytest.raises(InvalidTransportInput, match="policy_spec.value"):
        _resolve_treatment_value({"value": "invalid", "dose": 3})
    assert _resolve_treatment_value(None) == 1.0

    context = _resolve_context_profile(
        {"context_id": "UA", "publication_year": 2024, "countries": ["UA"]}
    )
    assert context == ContextProfile(context_id="UA", publication_year=2024, countries=["UA"])
    with pytest.raises(InvalidTransportInput, match="context profile is malformed"):
        _resolve_context_profile({"context_id": "UA", "unknown_context_field": True})
    assert (
        _resolve_context_year(ContextProfile(publication_year=2024, time_period="2018-2022"))
        == 2024
    )
    assert _resolve_context_year(ContextProfile(time_period="2018-2022")) == 2018

    dev_state = ExperimentState(
        run_id="degraded-dev",
        execution_profile="dev",
        params={"allow_degraded_transport": True, "transport_solver_mode": "SYMBOLIC_Y0"},
    )
    governed_state = ExperimentState(
        run_id="degraded-governed",
        execution_profile="governed",
        params={"allow_degraded_transport": True},
    )
    assert _resolve_allow_degraded_transport(dev_state) is True
    with pytest.raises(ValueError, match="forbidden outside the dev execution profile"):
        _resolve_allow_degraded_transport(governed_state)
    assert _resolve_transport_solver_mode(dev_state) == "symbolic_y0"
    with pytest.raises(InvalidTransportInput, match="unsupported: 'fastest'"):
        _resolve_transport_solver_mode(
            ExperimentState(run_id="invalid-solver", params={"transport_solver_mode": "fastest"})
        )


def test_graph_and_capability_resolution_reads_typed_cas_refs_and_rejects_foreign_kind(
    execution_context,
    minimal_state: ExperimentState,
    artifact_ref_factory,
) -> None:
    graph = _causal_graph()
    graph_ref = persist_causal_graph_model(execution_context.store, graph)
    graph_state = minimal_state.model_copy(
        update={"artifacts_index": {ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref}}
    )
    assert _resolve_causal_graph(execution_context, graph_state) == graph

    foreign_ref = artifact_ref_factory(kind="ir.foreign_graph_payload")
    foreign_state = minimal_state.model_copy(
        update={"artifacts_index": {ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: foreign_ref}}
    )
    assert _resolve_causal_graph(execution_context, foreign_state) is None

    contract, contract_ref = _resolve_or_build_capability_contract(execution_context, minimal_state)
    contract_state = minimal_state.model_copy(
        update={"artifacts_index": {ARTIFACT_CAUSAL_CAPABILITY_CONTRACT_REF: contract_ref}}
    )
    reread_contract, reread_ref = _resolve_or_build_capability_contract(
        execution_context,
        contract_state,
    )
    assert reread_contract == contract
    assert reread_ref == contract_ref
    assert reread_ref.kind == "ir.causal_capability_contract"


@pytest.mark.parametrize(
    ("invalid_params", "error_fragment"),
    [
        ({"query_treatment": 9}, "params.query_treatment"),
        (
            {"source_context": {"context_id": "source", "unknown": True}},
            "context profile is malformed",
        ),
        ({"policy_spec": {"value": "invalid", "dose": 3}}, "policy_spec.value"),
        ({"skg_db_path": 17}, "params.skg_db_path must be a filesystem path"),
        ({"dataset_registry_db_path": ""}, "params.dataset_registry_db_path"),
        ({"dataset_registry_db_path": "   "}, "params.dataset_registry_db_path"),
        ({"dataset_registry_db_path": Path("   ")}, "params.dataset_registry_db_path"),
        ({"legal_kg_db_path": ""}, "params.legal_kg_db_path"),
        ({"legal_kg_db_path": "   "}, "params.legal_kg_db_path"),
        ({"legal_kg_db_path": Path("   ")}, "params.legal_kg_db_path"),
        ({"skg_db_path": ""}, "params.skg_db_path"),
        ({"skg_db_path": "   "}, "params.skg_db_path"),
        ({"skg_db_path": Path("   ")}, "params.skg_db_path"),
        ({"skg_index_dir": ""}, "params.skg_index_dir"),
        ({"skg_index_dir": "   "}, "params.skg_index_dir"),
        ({"skg_index_dir": Path("   ")}, "params.skg_index_dir"),
        ({"privacy_context": {"unknown": True}}, "params.privacy_context is malformed"),
        ({"transport_solver_mode": "fastest"}, "transport_solver_mode is unsupported"),
        ({"policy_spec": []}, "policy_spec must be an object"),
        (
            {"pag_identification_policy": "unknown-policy"},
            "pag_identification_policy is unsupported",
        ),
        ({"pag_max_dag_samples": 1.5}, "pag_max_dag_samples must be an integer"),
        ({"pag_seed": -1}, "pag_seed must be in range 0..4294967295"),
    ],
)
def test_explicit_invalid_transport_input_fails_at_node_boundary(
    execution_context,
    minimal_state: ExperimentState,
    artifact_ref_factory,
    monkeypatch: pytest.MonkeyPatch,
    invalid_params: dict[str, object],
    error_fragment: str,
) -> None:
    state = minimal_state.model_copy(deep=True)
    state.artifacts_index[ARTIFACT_CAUSAL_REPORT_REF] = artifact_ref_factory(
        kind="ir.causal_effect_report"
    )
    state.params.update(
        {
            "source_context": {"context_id": "source"},
            "target_context": {"context_id": "target"},
            **invalid_params,
        }
    )
    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.resolve_transport.load_causal_effect_report",
        lambda *_args, **_kwargs: _causal_report(),
    )
    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.resolve_transport._resolve_causal_graph",
        lambda *_args, **_kwargs: _causal_graph(),
    )
    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.resolve_transport._resolve_or_build_capability_contract",
        lambda *_args, **_kwargs: pytest.fail("invalid input reached capability persistence"),
    )
    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.resolve_transport._build_dataset_registry",
        lambda *_args, **_kwargs: pytest.fail("invalid input selected a dataset adapter"),
    )
    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.resolve_transport._build_skg_query",
        lambda *_args, **_kwargs: pytest.fail("invalid input selected an SKG adapter"),
    )

    outcome = RunTransportabilityNode().execute(execution_context, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert error_fragment in outcome.error.message
    if any(
        field in invalid_params
        for field in (
            "dataset_registry_db_path",
            "legal_kg_db_path",
            "skg_db_path",
            "skg_index_dir",
        )
    ):
        assert outcome.error.code == node_errors.ERROR_INVALID_STATE


def test_pag_policy_admits_supported_enum_values_and_rejects_unknown_tokens() -> None:
    pag_graph = _causal_graph(GraphType.PAG)
    dag_graph = _causal_graph()
    assert _resolve_pag_identification_policy(ExperimentState(run_id="pag-default"), pag_graph) == (
        "probabilistic"
    )
    assert _resolve_pag_identification_policy(ExperimentState(run_id="dag-default"), dag_graph) == (
        "conservative"
    )
    for policy in PAGIdentificationPolicy:
        assert (
            _resolve_pag_identification_policy(
                ExperimentState(
                    run_id=f"pag-policy-{policy.value}",
                    params={"pag_identification_policy": policy.value},
                ),
                pag_graph,
            )
            == policy.value
        )
    with pytest.raises(InvalidTransportInput, match="pag_identification_policy is unsupported"):
        _resolve_pag_identification_policy(
            ExperimentState(
                run_id="unknown-pag-policy",
                params={"pag_identification_policy": "unknown-policy"},
            ),
            pag_graph,
        )


def test_pag_bounds_and_seed_preserve_consumer_domain(
    minimal_state: ExperimentState,
) -> None:
    pag_graph = _causal_graph(GraphType.PAG)

    bounded_state = ExperimentState(
        run_id="pag-bounds",
        params={"pag_max_dag_samples": 501, "pag_threshold": 1.5},
    )
    normalization_warnings: list[str] = []
    assert (
        _resolve_pag_max_dag_samples(
            bounded_state,
            normalization_warnings=normalization_warnings,
        )
        == 500
    )
    assert (
        _resolve_pag_threshold(
            bounded_state,
            normalization_warnings=normalization_warnings,
        )
        == 1.0
    )
    assert normalization_warnings == [
        "pag_max_dag_samples clamped from 501 to 500 (supported range 1..500)",
        "pag_threshold clamped from 1.5 to 1.0 (supported range 0..1)",
    ]
    with pytest.raises(InvalidTransportInput):
        _resolve_pag_max_dag_samples(
            ExperimentState(run_id="invalid-sample-count", params={"pag_max_dag_samples": 1.5})
        )
    with pytest.raises(InvalidTransportInput):
        _resolve_pag_threshold(
            ExperimentState(run_id="invalid-pag-threshold", params={"pag_threshold": "NaN"})
        )
    for seed in (-1, 2**32):
        with pytest.raises(InvalidTransportInput, match="pag_seed must be in range"):
            _resolve_pag_seed(
                ExperimentState(run_id=f"invalid-seed-{seed}", params={"pag_seed": seed}),
                pag_graph,
            )
    assert (
        _resolve_pag_seed(
            ExperimentState(run_id="minimum-seed", params={"pag_seed": 0}),
            pag_graph,
        )
        == 0
    )
    assert (
        _resolve_pag_seed(
            ExperimentState(run_id="maximum-seed", params={"pag_seed": 2**32 - 1}),
            pag_graph,
        )
        == 2**32 - 1
    )
    first_seed = _resolve_pag_seed(minimal_state, pag_graph)
    assert _resolve_pag_seed(minimal_state, pag_graph) == first_seed
    other_run = minimal_state.model_copy(update={"run_id": "other-run"})
    assert _resolve_pag_seed(other_run, pag_graph) != first_seed


def test_finite_numeric_inputs_accept_decimal_contract_values_and_reject_invalids() -> None:
    state = ExperimentState(
        run_id="decimal-pag-threshold",
        params={"pag_threshold": Decimal("0.25")},
    )
    assert state.params["pag_threshold"] == Decimal("0.25")
    assert _resolve_pag_threshold(state) == 0.25
    assert _resolve_treatment_value({"value": Decimal("2.5")}) == 2.5

    for invalid in (True, Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity"), {}):
        with pytest.raises(InvalidTransportInput):
            _resolve_treatment_value({"value": invalid})


def test_dataset_and_skg_adapters_read_existing_sources_and_degrade_for_missing_paths(
    tmp_path: Path,
) -> None:
    dataset_db = tmp_path / "datasets.duckdb"
    with duckdb.connect(str(dataset_db)) as connection:
        connection.execute(
            "CREATE TABLE ds_registry_datasets "
            "(dataset_id VARCHAR, coverage_json VARCHAR, update_freq VARCHAR)"
        )
        connection.execute(
            "CREATE TABLE ds_variable_alignments "
            "(dataset_id VARCHAR, raw_variable VARCHAR, canonical_var VARCHAR, "
            "confidence DOUBLE, is_proxy BOOLEAN, proxy_penalty DOUBLE, "
            "method VARCHAR, evidence VARCHAR)"
        )
        connection.execute(
            "CREATE TABLE ds_observations "
            "(dataset_id VARCHAR, raw_variable VARCHAR, country_code VARCHAR, "
            "survey_year INTEGER, year INTEGER, value DOUBLE, condition_json VARCHAR)"
        )
        connection.execute(
            "INSERT INTO ds_registry_datasets VALUES (?, ?, ?)",
            ["survey-1", '{"countries":["US"],"time_range":"2019-2021"}', "annual"],
        )
        connection.execute(
            "INSERT INTO ds_variable_alignments VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ["survey-1", "income_raw", "income", 0.91, False, 0.0, "manual", "catalog"],
        )
        connection.execute(
            "INSERT INTO ds_observations VALUES (?, ?, ?, ?, ?, ?, ?)",
            ["survey-1", "income_raw", "US", None, 2020, 51.0, "{}"],
        )

    registry = _build_dataset_registry(dataset_db)
    assert isinstance(registry, DatasetRegistry)
    matches = registry.find_datasets_for_variable("income", "US", (2020, 2020))
    assert len(matches) == 1
    assert matches[0].dataset_id == "survey-1"
    assert matches[0].temporal_match == "exact"
    assert matches[0].coverage_match == "full"
    wrong_country = registry.find_datasets_for_variable("income", "CA", (2020, 2020))
    assert len(wrong_country) == 1
    assert wrong_country[0].coverage_match == "none"

    missing_registry = _build_dataset_registry(tmp_path / "missing.duckdb")
    assert missing_registry.find_datasets_for_variable("income", "US") == []
    omitted_registry = _build_dataset_registry(None)
    assert omitted_registry.find_datasets_for_variable("income", "US") == []

    skg_db = tmp_path / "skg.duckdb"
    with duckdb.connect(str(skg_db)) as connection:
        connection.execute(
            "CREATE TABLE ac_causal_claims "
            "(id VARCHAR, work_id VARCHAR, cause VARCHAR, effect VARCHAR, "
            "direction VARCHAR, mechanism VARCHAR, trust_score DOUBLE, strength VARCHAR)"
        )
        connection.execute("CREATE TABLE ac_works (id VARCHAR, title VARCHAR, year INTEGER)")
    skg = build_skg_query(skg_db, tmp_path)
    assert isinstance(skg, SKGQuery)
    assert skg.query_claims(cause="policy", effect="income") == []
    missing_skg = build_skg_query(tmp_path / "missing-skg.duckdb", tmp_path)
    assert not isinstance(missing_skg, SKGQuery)
    assert missing_skg.query_claims(cause="policy", effect="income") == []
    omitted_skg = build_skg_query(None, None)
    assert not isinstance(omitted_skg, SKGQuery)
    assert omitted_skg.query_claims(cause="policy", effect="income") == []
