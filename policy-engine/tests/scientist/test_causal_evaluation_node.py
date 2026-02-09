from __future__ import annotations

import logging

import numpy as np

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.foundry.methods.causal import PanelObservationalData
from polisyos.foundry.methods.causal.protocols import HTEObservationalData
from polisyos.ir.analytics.causal import CausalEffectReport, CausalMethod, EstimationStatus
from polisyos.ir.analytics.hte import HTEResult
from polisyos.scientist.compute.job_spec import JobKey, JobResult
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation import RunCausalEvaluationNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_ENVELOPE_REF,
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_HTE_RESULT_REF,
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
