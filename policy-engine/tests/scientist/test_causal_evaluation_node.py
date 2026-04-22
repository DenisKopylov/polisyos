from __future__ import annotations

import importlib.util
import logging

import numpy as np
import pytest

_PYGRAPHVIZ_INSTALLED = importlib.util.find_spec("pygraphviz") is not None

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.foundry.methods.causal import (
    GraphCausalData,
    GraphCausalDataV1,
    HTEObservationalData,
    PanelObservationalData,
)
from polisyos.ir.analytics.causal import (
    CausalEffectReport,
    CausalMethod,
    DiagnosticTest,
    EstimationStatus,
    RefutationResult,
    RefutationTestType,
)
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    GraphType,
    EdgeMark,
    CausalGraphModel,
    persist_causal_graph_model,
)
from polisyos.ir.analytics.hte import HTEResult
from polisyos.ir.analytics.sensitivity import SensitivityResult
from polisyos.scientist.compute.job_spec import JobKey, JobResult
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation import RunCausalEvaluationNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_ENVELOPE_REF,
    ARTIFACT_CAUSAL_METHOD_RESULT_REF,
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_CAUSAL_VALIDITY_BUNDLE_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
    ARTIFACT_HTE_RESULT_REF,
    ARTIFACT_SENSITIVITY_RESULT_REF,
)


def test_causal_evaluation_node_skip_without_data(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_causal_skip")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.causal.skip"))
    state = ExperimentState(run_id="R_causal_skip")

    outcome = RunCausalEvaluationNode().execute(ctx, state)
    assert outcome.status == "skip"


def test_causal_evaluation_node_success(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_causal_ok")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.causal.ok"))

    t0 = 6
    donor_1 = np.array([10, 11, 12, 13, 14, 15, 16, 17, 18, 19], dtype=float)
    donor_2 = np.array([8, 9, 10, 11, 12, 13, 14, 15, 16, 17], dtype=float)
    treated = donor_1.copy()
    treated[t0:] += 4.0
    data = PanelObservationalData(
        outcome=np.vstack([treated, donor_1, donor_2]),
        treatment=np.array([1, 0, 0]),
        time_treatment=t0,
    )
    data_ref = store.put_json(
        data.model_dump(mode="json"),
        PutOptions(
            kind="ir.observational_data",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.ObservationalData", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )

    state = ExperimentState(
        run_id="R_causal_ok",
        observational_data_ref=data_ref,
        causal_method_fqn="causal.inference.synthetic_control@1.0.0",
        params={"random_seed": 42},
    )
    outcome = RunCausalEvaluationNode().execute(ctx, state)
    assert outcome.status == "ok"
    assert ARTIFACT_CAUSAL_REPORT_REF in outcome.state.artifacts_index
    assert ARTIFACT_CAUSAL_ENVELOPE_REF in outcome.state.artifacts_index

    report_ref = outcome.state.artifacts_index[ARTIFACT_CAUSAL_REPORT_REF]
    report_payload = from_canonical_bytes(store.get_bytes(report_ref.artifact_id))
    assert report_payload["status"] == "success"


def test_causal_evaluation_node_persists_hte_result(tmp_path, monkeypatch) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_causal_hte")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.causal.hte"))

    data = HTEObservationalData(
        outcome=np.linspace(0.0, 1.0, 50),
        treatment=np.array([0, 1] * 25),
        covariates=np.ones((50, 2), dtype=float),
    )
    data_ref = store.put_json(
        data.model_dump(mode="json"),
        PutOptions(
            kind="ir.observational_data",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.ObservationalData", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )

    def _fake_run_job(*args, **kwargs):
        del args, kwargs
        report = CausalEffectReport(
            method=CausalMethod.CAUSAL_FOREST,
            status=EstimationStatus.SUCCESS,
            estimand="ATE_from_CATE",
            point_estimate=0.2,
            confidence_interval=(0.1, 0.3),
            inference_method="causal_forest_dml",
            sample_size=50,
            n_treated=25,
            n_control=25,
            pre_periods=0,
            post_periods=0,
        )
        hte_result = HTEResult(
            method=CausalMethod.CAUSAL_FOREST,
            ate=0.2,
            ate_ci_lower=0.1,
            ate_ci_upper=0.3,
            cate_values=[0.2] * 50,
            n_samples=50,
            n_treated=25,
            n_control=25,
            n_features=2,
            feature_names=["x0", "x1"],
        )
        return JobResult(
            job_key=JobKey(value="job:test"),
            final_state={"report": report, "hte_result": hte_result},
            issues=[],
        )

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation.run_job",
        _fake_run_job,
    )

    state = ExperimentState(
        run_id="R_causal_hte",
        observational_data_ref=data_ref,
        causal_method_fqn="causal.hte.causal_forest@1.0.0",
        params={"random_seed": 7},
    )
    outcome = RunCausalEvaluationNode().execute(ctx, state)
    assert outcome.status == "ok"
    assert ARTIFACT_CAUSAL_REPORT_REF in outcome.state.artifacts_index
    assert ARTIFACT_HTE_RESULT_REF in outcome.state.artifacts_index


@pytest.mark.skipif(not _PYGRAPHVIZ_INSTALLED, reason="pygraphviz not installed — dowhy cannot build causal graphs")
def test_causal_evaluation_node_supports_graph_causal_data_v1(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_causal_graph")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.causal.graph"))

    rng = np.random.default_rng(8)
    z = rng.normal(size=300)
    x = 0.8 * z + rng.normal(0.0, 0.2, size=300)
    y = 1.1 * z + rng.normal(0.0, 0.2, size=300)
    data = GraphCausalDataV1(
        data=np.column_stack([x, y, z]),
        column_names=["X", "Y", "Z"],
        treatment="X",
        outcome="Y",
        graph_gml="digraph { Z -> X; Z -> Y; }",
        graph_ref="cas:graph:workflow",
    )
    data_ref = store.put_json(
        data.model_dump(mode="json"),
        PutOptions(
            kind="ir.observational_data",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.ObservationalData", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )

    state = ExperimentState(
        run_id="R_causal_graph",
        observational_data_ref=data_ref,
        causal_method_fqn="causal.inference.dowhy_identify_estimate@1.0.0",
        params={"random_seed": 11},
    )
    outcome = RunCausalEvaluationNode().execute(ctx, state)
    assert outcome.status == "ok"
    assert ARTIFACT_CAUSAL_REPORT_REF in outcome.state.artifacts_index

    report_ref = outcome.state.artifacts_index[ARTIFACT_CAUSAL_REPORT_REF]
    report_payload = from_canonical_bytes(store.get_bytes(report_ref.artifact_id))
    assert report_payload["method"].startswith("dowhy_")


@pytest.mark.skipif(not _PYGRAPHVIZ_INSTALLED, reason="pygraphviz not installed — dowhy cannot build causal graphs")
def test_causal_evaluation_node_supports_graph_causal_data_v2(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_causal_graph_v2")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.causal.graph.v2"))

    rng = np.random.default_rng(9)
    z = rng.normal(size=300)
    x = 0.8 * z + rng.normal(0.0, 0.2, size=300)
    y = 1.1 * z + rng.normal(0.0, 0.2, size=300)
    data = GraphCausalData(
        data=np.column_stack([x, y, z]),
        column_names=["X", "Y", "Z"],
        treatment="X",
        outcome="Y",
        graph_dot="digraph { Z -> X; Z -> Y; }",
        graph_ref="cas:graph:workflow-v2",
    )
    data_ref = store.put_json(
        data.model_dump(mode="json"),
        PutOptions(
            kind="ir.observational_data",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.ObservationalData", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )

    state = ExperimentState(
        run_id="R_causal_graph_v2",
        observational_data_ref=data_ref,
        causal_method_fqn="causal.inference.dowhy_identify_estimate@2.0.0",
        params={"random_seed": 13},
    )
    outcome = RunCausalEvaluationNode().execute(ctx, state)
    assert outcome.status == "ok"
    assert ARTIFACT_CAUSAL_REPORT_REF in outcome.state.artifacts_index


def test_causal_evaluation_node_wires_query_treatment_and_sutva_risk(tmp_path, monkeypatch) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_causal_sutva",
    )
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.causal.sutva"),
    )

    rng = np.random.default_rng(21)
    x = rng.normal(size=200)
    y = 0.8 * x + rng.normal(0.0, 0.2, size=200)
    data = GraphCausalData(
        data=np.column_stack([x, y]),
        column_names=["tax_rate", "gdp_growth"],
        treatment="tax_rate",
        outcome="gdp_growth",
        graph_dot="digraph { tax_rate -> gdp_growth; }",
    )
    data_ref = store.put_json(
        data.model_dump(mode="json"),
        PutOptions(
            kind="ir.observational_data",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.ObservationalData", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )

    def _fake_run_job(*args, **kwargs):
        del args, kwargs
        report = CausalEffectReport(
            method=CausalMethod.DOWHY_BACKDOOR,
            status=EstimationStatus.SUCCESS,
            estimand="ATE",
            point_estimate=0.5,
            confidence_interval=(0.3, 0.7),
            inference_method="backdoor.linear_regression",
            sample_size=200,
            n_treated=100,
            n_control=100,
            pre_periods=0,
            post_periods=0,
        )
        return JobResult(
            job_key=JobKey(value="job:sutva"),
            final_state={"report": report},
            issues=[],
        )

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation.ensure_causal_methods_registered",
        lambda: None,
    )
    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation.run_job",
        _fake_run_job,
    )

    state = ExperimentState(
        run_id="R_causal_sutva",
        observational_data_ref=data_ref,
        causal_method_fqn="causal.inference.dowhy_identify_estimate@2.0.0",
        params={"random_seed": 15, "enable_causal_refutation": False},
    )
    outcome = RunCausalEvaluationNode().execute(ctx, state)
    assert outcome.status == "ok"
    assert outcome.state.params.get("query_treatment") == "tax_rate"

    report_ref = outcome.state.artifacts_index[ARTIFACT_CAUSAL_REPORT_REF]
    report_payload = from_canonical_bytes(store.get_bytes(report_ref.artifact_id))
    assert report_payload["sutva_violation_risk"] == "high"


def test_causal_evaluation_node_auto_refutation_merges_and_persists_lineage(
    tmp_path,
    monkeypatch,
) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_causal_refutation",
    )
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.causal.refutation"),
    )

    rng = np.random.default_rng(10)
    z = rng.normal(size=256)
    x = 0.9 * z + rng.normal(0.0, 0.3, size=256)
    y = 1.2 * x + 1.0 * z + rng.normal(0.0, 0.3, size=256)
    data = GraphCausalData(
        data=np.column_stack([x, y, z]),
        column_names=["X", "Y", "Z"],
        treatment="X",
        outcome="Y",
        graph_dot="digraph { Z -> X; Z -> Y; X -> Y; }",
        graph_ref="cas:graph:auto-refute",
    )
    data_ref = store.put_json(
        data.model_dump(mode="json"),
        PutOptions(
            kind="ir.observational_data",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.ObservationalData", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )

    estimate_result_ref = store.put_json(
        {"estimate": "result"},
        PutOptions(kind="scientist.method_result", media_type="application/json"),
    )
    estimate_evidence_ref = store.put_json(
        {"estimate": "evidence"},
        PutOptions(kind="scientist.method_evidence", media_type="application/json"),
    )
    refute_result_ref = store.put_json(
        {"refute": "result"},
        PutOptions(kind="scientist.method_result", media_type="application/json"),
    )
    refute_evidence_ref = store.put_json(
        {"refute": "evidence"},
        PutOptions(kind="scientist.method_evidence", media_type="application/json"),
    )

    def _fake_run_job(spec, *, cas_root, method_state):
        del cas_root, method_state
        if spec.method_fqn == "causal.inference.dowhy_identify_estimate@2.0.0":
            estimate_report = CausalEffectReport(
                method=CausalMethod.DOWHY_BACKDOOR,
                status=EstimationStatus.SUCCESS,
                estimand="nonparametric-ate",
                point_estimate=1.2,
                confidence_interval=(1.0, 1.4),
                inference_method="backdoor.linear_regression",
                diagnostics=[
                    DiagnosticTest(
                        test_name="estimate.sanity",
                        statistic=1.0,
                        p_value=None,
                        passed=True,
                    )
                ],
                sample_size=256,
                n_treated=120,
                n_control=136,
                pre_periods=0,
                post_periods=0,
            )
            return JobResult(
                job_key=JobKey(value="job:estimate"),
                final_state={"report": estimate_report},
                method_result_ref=estimate_result_ref,
                method_evidence_ref=estimate_evidence_ref,
                issues=[],
            )

        if spec.method_fqn == "causal.refutation.dowhy_refute@1.0.0":
            ref_report = CausalEffectReport(
                method=CausalMethod.DOWHY_BACKDOOR,
                status=EstimationStatus.SUCCESS,
                estimand="nonparametric-ate",
                point_estimate=1.2,
                confidence_interval=(1.0, 1.4),
                inference_method="backdoor.linear_regression",
                diagnostics=[
                    DiagnosticTest(
                        test_name="refutation.random_common_cause",
                        statistic=1.01,
                        p_value=0.42,
                        passed=True,
                    )
                ],
                refutation_results=[
                    RefutationResult(
                        test_type=RefutationTestType.RANDOM_COMMON_CAUSE,
                        original_estimate=1.2,
                        refuted_estimate=1.212,
                        p_value=0.42,
                        passed=True,
                        effect_ratio=1.01,
                        details={"source": "unit_test"},
                    )
                ],
                sample_size=256,
                n_treated=120,
                n_control=136,
                pre_periods=0,
                post_periods=0,
            )
            return JobResult(
                job_key=JobKey(value="job:refute"),
                final_state={"report": ref_report},
                method_result_ref=refute_result_ref,
                method_evidence_ref=refute_evidence_ref,
                issues=[],
            )

        raise AssertionError(f"unexpected method_fqn: {spec.method_fqn}")

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation.ensure_causal_methods_registered",
        lambda: None,
    )
    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation.run_job",
        _fake_run_job,
    )

    state = ExperimentState(
        run_id="R_causal_refutation",
        observational_data_ref=data_ref,
        causal_method_fqn="causal.inference.dowhy_identify_estimate@2.0.0",
        params={"random_seed": 5, "enable_causal_sensitivity": False},
    )
    outcome = RunCausalEvaluationNode().execute(ctx, state)
    assert outcome.status == "ok"

    report_ref = outcome.state.artifacts_index[ARTIFACT_CAUSAL_REPORT_REF]
    report_payload = from_canonical_bytes(store.get_bytes(report_ref.artifact_id))
    assert len(report_payload["refutation_results"]) == 1
    assert report_payload["metadata"]["refutation_auto"]["status"] == "success"
    assert any(
        item["test_name"].startswith("refutation.")
        for item in report_payload["diagnostics"]
    )

    manifest = store.get_manifest(report_ref.artifact_id)
    roles = {item.role for item in manifest.inputs}
    assert "causal_method_result" in roles
    assert "causal_method_evidence" in roles
    assert "causal_refutation_method_result" in roles
    assert "causal_refutation_method_evidence" in roles

    assert ARTIFACT_CAUSAL_METHOD_RESULT_REF in outcome.state.artifacts_index
    assert (
        outcome.state.artifacts_index[ARTIFACT_CAUSAL_METHOD_RESULT_REF].artifact_id
        == estimate_result_ref.artifact_id
    )


def test_causal_evaluation_node_auto_sensitivity_persists_and_links(tmp_path, monkeypatch) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_causal_sensitivity",
    )
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.causal.sensitivity"),
    )

    rng = np.random.default_rng(12)
    z = rng.normal(size=256)
    x = 0.9 * z + rng.normal(0.0, 0.3, size=256)
    y = 1.2 * x + 1.0 * z + rng.normal(0.0, 0.3, size=256)
    data = GraphCausalData(
        data=np.column_stack([x, y, z]),
        column_names=["X", "Y", "Z"],
        treatment="X",
        outcome="Y",
        graph_dot="digraph { Z -> X; Z -> Y; X -> Y; }",
        graph_ref="cas:graph:auto-sensitivity",
        covariates=["Z"],
    )
    data_ref = store.put_json(
        data.model_dump(mode="json"),
        PutOptions(
            kind="ir.observational_data",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.ObservationalData", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )

    estimate_result_ref = store.put_json(
        {"estimate": "result"},
        PutOptions(kind="scientist.method_result", media_type="application/json"),
    )
    estimate_evidence_ref = store.put_json(
        {"estimate": "evidence"},
        PutOptions(kind="scientist.method_evidence", media_type="application/json"),
    )
    sensitivity_result_ref = store.put_json(
        {"sensitivity": "result"},
        PutOptions(kind="scientist.method_result", media_type="application/json"),
    )
    sensitivity_evidence_ref = store.put_json(
        {"sensitivity": "evidence"},
        PutOptions(kind="scientist.method_evidence", media_type="application/json"),
    )

    def _fake_run_job(spec, *, cas_root, method_state):
        del cas_root, method_state
        if spec.method_fqn == "causal.inference.dowhy_identify_estimate@2.0.0":
            estimate_report = CausalEffectReport(
                method=CausalMethod.DOWHY_BACKDOOR,
                status=EstimationStatus.SUCCESS,
                estimand="nonparametric-ate",
                point_estimate=1.2,
                confidence_interval=(1.0, 1.4),
                inference_method="backdoor.linear_regression",
                sample_size=256,
                n_treated=120,
                n_control=136,
                pre_periods=0,
                post_periods=0,
            )
            return JobResult(
                job_key=JobKey(value="job:estimate"),
                final_state={"report": estimate_report},
                method_result_ref=estimate_result_ref,
                method_evidence_ref=estimate_evidence_ref,
                issues=[],
            )
        if spec.method_fqn == "causal.sensitivity.sensitivity_metrics@1.0.0":
            sensitivity = SensitivityResult(
                e_value=1.9,
                e_value_ci_lower=1.2,
                conversion_method="ate_to_rr_log",
                robustness_value=0.08,
                rosenbaum_gamma=1.5,
                rosenbaum_p_value=0.12,
                is_robust=True,
                interpretation="synthetic sensitivity summary",
            )
            return JobResult(
                job_key=JobKey(value="job:sensitivity"),
                final_state={"sensitivity_result": sensitivity, "warnings": ["unit_test"]},
                method_result_ref=sensitivity_result_ref,
                method_evidence_ref=sensitivity_evidence_ref,
                issues=[],
            )
        raise AssertionError(f"unexpected method_fqn: {spec.method_fqn}")

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation.ensure_causal_methods_registered",
        lambda: None,
    )
    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation.run_job",
        _fake_run_job,
    )

    state = ExperimentState(
        run_id="R_causal_sensitivity",
        observational_data_ref=data_ref,
        causal_method_fqn="causal.inference.dowhy_identify_estimate@2.0.0",
        params={"random_seed": 9, "enable_causal_refutation": False},
    )
    outcome = RunCausalEvaluationNode().execute(ctx, state)
    assert outcome.status == "ok"
    assert ARTIFACT_SENSITIVITY_RESULT_REF in outcome.state.artifacts_index

    report_ref = outcome.state.artifacts_index[ARTIFACT_CAUSAL_REPORT_REF]
    report_payload = from_canonical_bytes(store.get_bytes(report_ref.artifact_id))
    sensitivity_meta = report_payload["metadata"]["sensitivity_auto"]
    assert sensitivity_meta["status"] == "success"
    assert sensitivity_meta["is_robust"] is True

    manifest = store.get_manifest(report_ref.artifact_id)
    roles = {item.role for item in manifest.inputs}
    assert "causal_sensitivity_method_result" in roles
    assert "causal_sensitivity_method_evidence" in roles


def test_causal_evaluation_node_sensitivity_failure_is_non_blocking(tmp_path, monkeypatch) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_causal_sensitivity_fail",
    )
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.causal.sensitivity.fail"),
    )

    rng = np.random.default_rng(13)
    z = rng.normal(size=256)
    x = 0.9 * z + rng.normal(0.0, 0.3, size=256)
    y = 1.2 * x + 1.0 * z + rng.normal(0.0, 0.3, size=256)
    data = GraphCausalData(
        data=np.column_stack([x, y, z]),
        column_names=["X", "Y", "Z"],
        treatment="X",
        outcome="Y",
        graph_dot="digraph { Z -> X; Z -> Y; X -> Y; }",
        graph_ref="cas:graph:auto-sensitivity-fail",
        covariates=["Z"],
    )
    data_ref = store.put_json(
        data.model_dump(mode="json"),
        PutOptions(
            kind="ir.observational_data",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.ObservationalData", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )

    def _fake_run_job(spec, *, cas_root, method_state):
        del cas_root, method_state
        if spec.method_fqn == "causal.inference.dowhy_identify_estimate@2.0.0":
            estimate_report = CausalEffectReport(
                method=CausalMethod.DOWHY_BACKDOOR,
                status=EstimationStatus.SUCCESS,
                estimand="nonparametric-ate",
                point_estimate=1.2,
                confidence_interval=(1.0, 1.4),
                inference_method="backdoor.linear_regression",
                sample_size=256,
                n_treated=120,
                n_control=136,
                pre_periods=0,
                post_periods=0,
            )
            return JobResult(
                job_key=JobKey(value="job:estimate-fail"),
                final_state={"report": estimate_report},
                issues=[],
            )
        if spec.method_fqn == "causal.sensitivity.sensitivity_metrics@1.0.0":
            return JobResult(
                job_key=JobKey(value="job:sensitivity-fail"),
                final_state={},
                issues=[{"error": "synthetic_failure"}],
            )
        raise AssertionError(f"unexpected method_fqn: {spec.method_fqn}")

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation.ensure_causal_methods_registered",
        lambda: None,
    )
    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation.run_job",
        _fake_run_job,
    )

    state = ExperimentState(
        run_id="R_causal_sensitivity_fail",
        observational_data_ref=data_ref,
        causal_method_fqn="causal.inference.dowhy_identify_estimate@2.0.0",
        params={"random_seed": 10, "enable_causal_refutation": False},
    )
    outcome = RunCausalEvaluationNode().execute(ctx, state)
    assert outcome.status == "ok"
    assert ARTIFACT_CAUSAL_REPORT_REF in outcome.state.artifacts_index
    assert ARTIFACT_SENSITIVITY_RESULT_REF not in outcome.state.artifacts_index

    report_ref = outcome.state.artifacts_index[ARTIFACT_CAUSAL_REPORT_REF]
    report_payload = from_canonical_bytes(store.get_bytes(report_ref.artifact_id))
    sensitivity_meta = report_payload["metadata"]["sensitivity_auto"]
    assert sensitivity_meta["status"] == "failed"
    assert "issues" in sensitivity_meta


def test_causal_evaluation_node_can_disable_auto_sensitivity(tmp_path, monkeypatch) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_causal_sensitivity_disabled",
    )
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.causal.sensitivity.disabled"),
    )

    rng = np.random.default_rng(14)
    z = rng.normal(size=128)
    x = 0.7 * z + rng.normal(0.0, 0.2, size=128)
    y = 1.1 * x + 0.8 * z + rng.normal(0.0, 0.2, size=128)
    data = GraphCausalData(
        data=np.column_stack([x, y, z]),
        column_names=["X", "Y", "Z"],
        treatment="X",
        outcome="Y",
        graph_dot="digraph { Z -> X; Z -> Y; X -> Y; }",
        graph_ref="cas:graph:auto-sensitivity-disabled",
        covariates=["Z"],
    )
    data_ref = store.put_json(
        data.model_dump(mode="json"),
        PutOptions(
            kind="ir.observational_data",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.ObservationalData", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )

    called_fqns: list[str] = []

    def _fake_run_job(spec, *, cas_root, method_state):
        del cas_root, method_state
        called_fqns.append(spec.method_fqn or "")
        if spec.method_fqn == "causal.inference.dowhy_identify_estimate@2.0.0":
            estimate_report = CausalEffectReport(
                method=CausalMethod.DOWHY_BACKDOOR,
                status=EstimationStatus.SUCCESS,
                estimand="nonparametric-ate",
                point_estimate=1.1,
                confidence_interval=(0.9, 1.3),
                inference_method="backdoor.linear_regression",
                sample_size=128,
                n_treated=64,
                n_control=64,
                pre_periods=0,
                post_periods=0,
            )
            return JobResult(
                job_key=JobKey(value="job:estimate-disabled"),
                final_state={"report": estimate_report},
                issues=[],
            )
        raise AssertionError(f"unexpected method_fqn: {spec.method_fqn}")

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation.ensure_causal_methods_registered",
        lambda: None,
    )
    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation.run_job",
        _fake_run_job,
    )

    state = ExperimentState(
        run_id="R_causal_sensitivity_disabled",
        observational_data_ref=data_ref,
        causal_method_fqn="causal.inference.dowhy_identify_estimate@2.0.0",
        params={
            "random_seed": 4,
            "enable_causal_refutation": False,
            "enable_causal_sensitivity": False,
        },
    )
    outcome = RunCausalEvaluationNode().execute(ctx, state)
    assert outcome.status == "ok"
    assert called_fqns == ["causal.inference.dowhy_identify_estimate@2.0.0"]
    assert ARTIFACT_SENSITIVITY_RESULT_REF not in outcome.state.artifacts_index


def test_causal_evaluation_node_persists_causal_validity_bundle_for_hte_inputs(
    tmp_path,
    monkeypatch,
) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_causal_validity_bundle",
    )
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.causal.validity.bundle"),
    )

    rng = np.random.default_rng(41)
    x = rng.normal(size=(96, 2))
    treatment = rng.binomial(1, 0.5, size=96).astype(float)
    outcome = 0.7 * treatment + 0.4 * x[:, 0] + rng.normal(0.0, 0.2, size=96)
    treatment_proxy = (0.8 * x[:, 0] + rng.normal(0.0, 0.1, size=96)).tolist()
    outcome_proxy = (0.6 * x[:, 1] + rng.normal(0.0, 0.1, size=96)).tolist()
    data = HTEObservationalData(
        outcome=outcome,
        treatment=treatment,
        covariates=x,
        feature_names=["x0", "x1"],
        metadata={
            "causal_validity": {
                "domain_labels": ["A"] * 48 + ["B"] * 48,
                "proximal": {
                    "treatment_proxy": treatment_proxy,
                    "outcome_proxy": outcome_proxy,
                    "n_bootstrap": 32,
                },
            }
        },
    )
    data_ref = store.put_json(
        data.model_dump(mode="json"),
        PutOptions(
            kind="ir.observational_data",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.ObservationalData", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )

    pag_graph = CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=["A", "B", "C"],
        edges=[
            CausalEdge(src="A", dst="B", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="B", dst="C", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.TAIL),
        ],
    )
    pag_ref = persist_causal_graph_model(store, pag_graph)

    def _fake_run_job(spec, *, cas_root, method_state):
        del cas_root, method_state
        if spec.method_fqn == "causal.hte.causal_forest@1.0.0":
            report = CausalEffectReport(
                method=CausalMethod.CAUSAL_FOREST,
                status=EstimationStatus.SUCCESS,
                estimand="ATE_from_CATE",
                point_estimate=0.7,
                confidence_interval=(0.5, 0.9),
                inference_method="causal_forest_dml",
                sample_size=96,
                n_treated=48,
                n_control=48,
                pre_periods=0,
                post_periods=0,
            )
            hte_result = HTEResult(
                method=CausalMethod.CAUSAL_FOREST,
                ate=0.7,
                ate_ci_lower=0.5,
                ate_ci_upper=0.9,
                cate_values=[0.7] * 96,
                n_samples=96,
                n_treated=48,
                n_control=48,
                n_features=2,
                feature_names=["x0", "x1"],
            )
            return JobResult(
                job_key=JobKey(value="job:hte-estimate"),
                final_state={"report": report, "hte_result": hte_result},
                issues=[],
            )
        if spec.method_fqn == "causal.sensitivity.sensitivity_metrics@1.0.0":
            return JobResult(
                job_key=JobKey(value="job:hte-sensitivity"),
                final_state={
                    "sensitivity_result": SensitivityResult(
                        e_value=2.1,
                        e_value_ci_lower=1.4,
                        conversion_method="ate_to_rr_log",
                        robustness_value=0.11,
                        rosenbaum_gamma=1.6,
                        rosenbaum_p_value=0.09,
                        is_robust=True,
                        interpretation="hte sensitivity",
                    )
                },
                issues=[],
            )
        if spec.method_fqn == "causal.diagnostics.invariance.icp_invariance@1.0.0":
            return JobResult(
                job_key=JobKey(value="job:icp"),
                final_state={
                    "result": {
                        "passed": True,
                        "n_rejected": 0,
                        "invariant_features": [0, 1],
                        "variant_features": [],
                        "p_values": {"feature_0": 0.44, "feature_1": 0.62},
                        "correction_method": "bh",
                        "metadata": {"n_obs": 96},
                    }
                },
                issues=[],
            )
        if spec.method_fqn == "causal.proximal.proximal_bridge@1.0.0":
            return JobResult(
                job_key=JobKey(value="job:proximal"),
                final_state={
                    "report": {"status": "success", "status_reason": None},
                    "proximal_result": {
                        "point_estimate": 0.68,
                        "confidence_interval": [0.51, 0.83],
                        "bridge_r_squared": 0.57,
                        "proxy_strength": 0.48,
                    },
                },
                issues=[],
            )
        raise AssertionError(f"unexpected method_fqn: {spec.method_fqn}")

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation.ensure_causal_methods_registered",
        lambda: None,
    )
    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation.run_job",
        _fake_run_job,
    )
    monkeypatch.setattr(
        "polisyos.scientist.causal.validity.run_job",
        _fake_run_job,
    )

    state = ExperimentState(
        run_id="R_causal_validity_bundle",
        observational_data_ref=data_ref,
        causal_method_fqn="causal.hte.causal_forest@1.0.0",
        params={"random_seed": 6},
        artifacts_index={ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: pag_ref},
    )
    outcome = RunCausalEvaluationNode().execute(ctx, state)
    assert outcome.status == "ok"
    assert ARTIFACT_SENSITIVITY_RESULT_REF in outcome.state.artifacts_index
    assert ARTIFACT_CAUSAL_VALIDITY_BUNDLE_REF in outcome.state.artifacts_index

    report_ref = outcome.state.artifacts_index[ARTIFACT_CAUSAL_REPORT_REF]
    report_payload = from_canonical_bytes(store.get_bytes(report_ref.artifact_id))
    assert report_payload["metadata"]["sensitivity_auto"]["status"] == "success"

    bundle_ref = outcome.state.artifacts_index[ARTIFACT_CAUSAL_VALIDITY_BUNDLE_REF]
    bundle_payload = from_canonical_bytes(store.get_bytes(bundle_ref.artifact_id))
    checks = bundle_payload["checks"]
    assert checks["sensitivity"]["status"] == "success"
    assert checks["icp_invariance"]["status"] == "success"
    assert checks["proximal_bridge"]["status"] == "success"
    assert checks["pag_refinement"]["status"] == "success"
    assert bundle_payload["confidence"]["honest_hte"]["enabled"] is True
    assert bundle_payload["capability_matrix"]["icp_invariance"] == "available"
    frontier_runtime = bundle_payload["frontier_runtime"]
    proximal = next(
        item for item in frontier_runtime["capabilities"]
        if item["capability_id"] == "proximal_causal"
    )
    assert proximal["status"] == "offline_gated"


def test_causal_evaluation_node_surfaces_spatial_interference_validity_check(
    tmp_path,
    monkeypatch,
) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_spatial_validity_bundle",
    )
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.causal.spatial.validity.bundle"),
    )

    rng = np.random.default_rng(52)
    x = rng.normal(size=80)
    z = rng.normal(size=80)
    treatment = rng.binomial(1, 0.5, size=80).astype(float)
    outcome = 1.1 * treatment + 0.5 * x + rng.normal(0.0, 0.2, size=80)
    data = GraphCausalData(
        data=np.column_stack([treatment, outcome, x, z]),
        column_names=["T", "Y", "X", "Z"],
        treatment="T",
        outcome="Y",
        graph_dot="digraph { X -> T; X -> Y; Z -> T; T -> Y; }",
        covariates=["X", "Z"],
    )
    data_ref = store.put_json(
        data.model_dump(mode="json"),
        PutOptions(
            kind="ir.observational_data",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.ObservationalData", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )

    def _fake_run_job(spec, *, cas_root, method_state):
        del cas_root, method_state
        if spec.method_fqn == "causal.inference.dowhy_identify_estimate@2.0.0":
            return JobResult(
                job_key=JobKey(value="job:spatial-validity"),
                final_state={
                    "report": CausalEffectReport(
                        method=CausalMethod.DOWHY_BACKDOOR,
                        status=EstimationStatus.SUCCESS,
                        estimand="nonparametric-ate",
                        point_estimate=1.1,
                        confidence_interval=(0.8, 1.4),
                        inference_method="backdoor.linear_regression",
                        sample_size=80,
                        n_treated=40,
                        n_control=40,
                        pre_periods=0,
                        post_periods=0,
                        metadata={
                            "spatial_hodge_summary": {
                                "declared_scale_id": "district",
                                "declared_zoning_id": "admin_v1",
                                "aggregation_rule": "mean",
                                "weight_spec": "queen",
                                "zoning_hash": "zone_hash_1",
                                "weight_hash": "weight_hash_1",
                                "aggregation_hash": "agg_hash_1",
                                "eta_grad": 0.61,
                                "eta_curl": 0.14,
                                "eta_harm": 0.25,
                                "dominant_component": "grad",
                                "max_profile_l1_gap": 0.33,
                                "scale_instability": 0.33,
                                "zoning_instability": 0.18,
                                "topology_sensitivity": 0.07,
                                "candidate_partition_ids": ["admin_v2", "hex_2km"],
                                "warnings": [],
                                "blocker_codes": [],
                            },
                            "maup_invariance_certificate": {
                                "status": "warn",
                                "partitions_tested": 2,
                                "warnings": ["micro_ess_warn"],
                                "blocker_codes": [],
                            },
                        },
                    )
                },
                issues=[],
            )
        raise AssertionError(f"unexpected method_fqn: {spec.method_fqn}")

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation.ensure_causal_methods_registered",
        lambda: None,
    )
    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation.run_job",
        _fake_run_job,
    )
    monkeypatch.setattr("polisyos.scientist.causal.validity.run_job", _fake_run_job)

    state = ExperimentState(
        run_id="R_spatial_validity_bundle",
        observational_data_ref=data_ref,
        causal_method_fqn="causal.inference.dowhy_identify_estimate@2.0.0",
        params={
            "random_seed": 2,
            "enable_causal_refutation": False,
            "enable_causal_sensitivity": False,
            "causal_validity": {
                "enable_icp": False,
                "enable_proximal": False,
                "enable_recoverability": False,
                "enable_pag_refinement": False,
            },
        },
    )
    outcome = RunCausalEvaluationNode().execute(ctx, state)
    assert outcome.status == "ok"
    assert ARTIFACT_CAUSAL_VALIDITY_BUNDLE_REF in outcome.state.artifacts_index

    bundle_ref = outcome.state.artifacts_index[ARTIFACT_CAUSAL_VALIDITY_BUNDLE_REF]
    bundle_payload = from_canonical_bytes(store.get_bytes(bundle_ref.artifact_id))
    spatial_check = bundle_payload["checks"]["spatial_interference"]
    assert spatial_check["status"] == "success"
    assert spatial_check["declared_scale_id"] == "district"
    assert spatial_check["eta_grad"] == pytest.approx(0.61)
    assert spatial_check["maup_status"] == "warn"
    assert bundle_payload["capability_matrix"]["spatial_interference_hodge"] == "available"
    assert bundle_payload["capability_matrix"]["maup_stability_surface"] == "available"
