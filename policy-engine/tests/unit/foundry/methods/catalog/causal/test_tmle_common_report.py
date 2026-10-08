"""Real native MethodJob and typed report consumers for cross-sectional TMLE."""

from __future__ import annotations

import json
import pickle
import subprocess
import sys
from dataclasses import fields

import numpy as np
import pytest

from polisyos.common.serialization import to_python_data
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.foundry.methods.catalog.causal import tmle_core as core
from polisyos.foundry.methods.catalog.causal.protocols import HTEObservationalData
from polisyos.foundry.methods.catalog.causal.treatment_effects import TMLEEstimator
from polisyos.foundry.methods.components.io import dematerialize_method_output
from polisyos.ir.analytics.causal import (
    CausalEffectReport,
    CausalMethod,
    EstimationStatus,
)
from polisyos.ir.analytics.uncertainty import IntervalSemantics, UncertaintyEnvelope
from polisyos.scientist.compute.job_spec import JobSpec
from polisyos.scientist.compute.runner import run_job


def _data() -> HTEObservationalData:
    rng = np.random.default_rng(73)
    n = 600
    w = rng.normal(size=n)
    a = rng.binomial(1, 0.5, size=n).astype(float)
    # Known randomized DGP: E[Y(1)-Y(0)]=.30, bounded Bernoulli outcome.
    y = rng.binomial(1, 0.25 + 0.1 * np.sign(w) + 0.3 * a).astype(float)
    return HTEObservationalData(
        outcome=y,
        treatment=a,
        covariates=w[:, None],
        feature_names=["w"],
        sample_ids=np.arange(n),
    )


def _params(**changes: object) -> dict[str, object]:
    return {
        "propensity_backend": "logistic",
        "outcome_backend": "linear",
        "calibration_mode": "none",
        "outcome_scaling": "raw",
        "crossfit_folds": 3,
        "n_repeats": 2,
        "random_seed": 18,
        "ci_mode": "wald",
        "inference_profile": "regular_iid",
        "coverage_guard": "off",
        **changes,
    }


def _legacy(data: HTEObservationalData) -> dict[str, np.ndarray]:
    x = data.covariates
    if data.confounders is not None:
        x = np.column_stack((x, data.confounders))
    return {"X": x, "treatment": data.treatment, "outcome": data.outcome}


def _run(tmp_path, data: HTEObservationalData, params: dict[str, object]):
    store = FileSystemCAS(tmp_path / "cas")
    source = store.put_json(
        data.model_dump(mode="json"),
        PutOptions(kind="ir.observational_data", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    job = run_job(
        JobSpec(
            job_kind="method",
            method_fqn=TMLEEstimator.signature.fqn,
            method_params=params,
            seed=18,
            input_refs={"causal_observational_data": source},
        ),
        cas_root=store.root,
        method_state=data,
    )
    assert not job.issues, job.issues
    fresh = FileSystemCAS(store.root)
    saved = from_canonical_bytes(fresh.get_bytes(job.method_result_ref))
    assert saved == to_python_data(job.final_state, sort_keys=True)
    evidence = from_canonical_bytes(fresh.get_bytes(job.method_evidence_ref))
    assert evidence["authority_purpose"] == "method_execution"
    assert "method_validity" in evidence["may_not_use_for"]
    assert fresh.get_manifest(job.method_result_ref).inputs[0].artifact_id == source.artifact_id
    return saved, job


def test_real_configured_method_job_projects_exact_native_eif_and_cas_reader(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = _data()
    params = _params()
    calls = []
    native = core._fit_crossfit_fold

    def observe(**kwargs):
        calls.append((kwargs["rep_seed"], kwargs["fold_id"], kwargs["test_idx"].copy()))
        return native(**kwargs)

    monkeypatch.setattr(core, "_SHARED_NUISANCE_CACHE", {})
    monkeypatch.setattr(core, "_SHARED_NUISANCE_CACHE_ORDER", [])
    monkeypatch.setattr(core, "_fit_crossfit_fold", observe)
    saved, job = _run(tmp_path, data, params)
    assert len(calls) == 6
    assert {(seed, fold) for seed, fold, _ in calls} == {
        (seed, fold) for seed in (18, 1015) for fold in range(3)
    }
    for seed in (18, 1015):
        held_out = [i for current, _, indices in calls if current == seed for i in indices]
        assert sorted(held_out) == list(range(len(data.outcome)))
    result = saved["result"]
    report = CausalEffectReport.model_validate(saved["report"])
    envelope = UncertaintyEnvelope.model_validate(saved["envelope"])
    assert report.method is CausalMethod.TMLE
    assert report.status is EstimationStatus.SUCCESS
    assert report.point_estimate == result["ate"]
    assert report.standard_error == result["standard_error"]
    assert report.confidence_interval == (result["ci_lower"], result["ci_upper"])
    assert report.confidence_level == 0.95
    assert result["interval_method"] == "wald_eif_regular_iid"
    assert abs(report.point_estimate - 0.3) < 0.08
    assert report.sample_size == len(data.outcome)
    assert report.n_treated == np.count_nonzero(data.treatment)
    assert report.n_control == report.sample_size - report.n_treated
    assert envelope == report.to_uncertainty_envelope()
    assert envelope.gate_eligible is False and result["gate_eligible"] is False
    assert report.identified_estimand is None
    child = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json,sys; from polisyos.core.artifacts.manifest import ArtifactRef; "
            "from polisyos.core.artifacts.store import FileSystemCAS; "
            "from polisyos.core.canon import from_canonical_bytes; "
            "from polisyos.ir.analytics.causal import CausalEffectReport; "
            "from polisyos.ir.analytics.uncertainty import UncertaintyEnvelope; "
            "store=FileSystemCAS(sys.argv[1]); ref=ArtifactRef.model_validate_json(sys.argv[2]); "
            "saved=from_canonical_bytes(store.get_bytes(ref)); "
            "report=CausalEffectReport.model_validate(saved['report']); "
            "envelope=UncertaintyEnvelope.model_validate(saved['envelope']); "
            "assert envelope==report.to_uncertainty_envelope(); "
            "assert not envelope.gate_eligible; "
            "print(json.dumps({'method':report.method.value,'point':report.point_estimate,"
            "'ci':report.confidence_interval,'status':report.status.value}))",
            str(tmp_path / "cas"),
            job.method_result_ref.model_dump_json(),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    child_result = json.loads(child.stdout.splitlines()[-1])
    assert child_result == {
        "method": "tmle",
        "point": report.point_estimate,
        "ci": list(report.confidence_interval),
        "status": report.status.value,
    }
    assert result["nuisance_diagnostics"]["execution_policy"]["effective_fold_workers"] == 1
    # Genuine old raw-mapping result consumer is unchanged, reuses the same native core.
    legacy = TMLEEstimator.pure_step(_legacy(data), params)
    assert to_python_data(legacy["result"], sort_keys=True) == result
    assert len(calls) == 6
    mapped = dematerialize_method_output(
        method_class=TMLEEstimator,
        signature=TMLEEstimator.signature,
        output=legacy,
    )
    assert mapped["result"] is legacy["result"]
    assert mapped["report"] is legacy["report"]
    assert mapped["envelope"] is legacy["envelope"]


def test_typed_confounders_preserve_complete_native_adjustment_basis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = _data()
    confounder = np.linspace(-1.0, 1.0, len(data.outcome))[:, None]
    data = data.model_copy(update={"confounders": confounder, "confounder_names": ["calendar"]})
    shapes = []
    native = core._fit_crossfit_fold

    def observe(**kwargs):
        shapes.append(kwargs["X"].shape)
        return native(**kwargs)

    monkeypatch.setattr(core, "_SHARED_NUISANCE_CACHE", {})
    monkeypatch.setattr(core, "_SHARED_NUISANCE_CACHE_ORDER", [])
    monkeypatch.setattr(core, "_fit_crossfit_fold", observe)
    typed = TMLEEstimator.pure_step(data, _params())
    raw = TMLEEstimator.pure_step(_legacy(data), _params())
    assert typed["result"] == raw["result"]
    assert typed["report"] == raw["report"]
    assert shapes == [(600, 2)] * 6


@pytest.mark.parametrize(
    ("changes", "limitation", "status"),
    [
        (
            {"inference_profile": "clustered"},
            "unsupported_inference_profile",
            EstimationStatus.ASSUMPTION_FAILED,
        ),
        (
            {"propensity_clipping": 0.49},
            "observed_positivity_failure",
            EstimationStatus.ASSUMPTION_FAILED,
        ),
        (
            {"propensity_trimming": 0.48, "weak_overlap_mode": "trim"},
            "trimmed_target_not_population_ate",
            EstimationStatus.ASSUMPTION_FAILED,
        ),
        (
            {"max_targeting_iter": 1, "targeting_step_limit": 1e-10},
            "targeting_score_not_converged",
            EstimationStatus.NUMERICAL_FAILURE,
        ),
    ],
)
def test_actual_limited_profiles_preserve_result_and_emit_point_free_report(
    tmp_path,
    changes,
    limitation,
    status,
) -> None:
    saved, _ = _run(tmp_path, _data(), _params(**changes))
    result = saved["result"]
    report = CausalEffectReport.model_validate(saved["report"])
    envelope = UncertaintyEnvelope.model_validate(saved["envelope"])
    assert limitation in result["inference_limitations"]
    assert result["status"] == "limited" and np.isfinite(result["ate"])
    assert result["ci_lower"] is None and result["ci_upper"] is None
    assert report.status is status
    assert report.point_estimate is None and report.standard_error is None
    assert report.confidence_interval is None
    assert report.method is CausalMethod.TMLE
    assert envelope.interval_semantics is IntervalSemantics.HEURISTIC_RANGE
    assert envelope.is_heuristic_ci is True and envelope.gate_eligible is False
    assert envelope.metadata["failure_envelope"] is True
    assert report.to_uncertainty_envelope() == envelope


def test_public_projection_is_real_producer_seam_and_pickle_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = TMLEEstimator.report_from_result
    calls = []

    def observe(**kwargs):
        calls.append(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(TMLEEstimator, "report_from_result", staticmethod(observe))
    produced = TMLEEstimator.pure_step(_data(), _params())
    assert len(calls) == 1
    assert produced["report"] == original(**calls[0])
    assert original.__qualname__ == "TMLEEstimator.report_from_result"
    monkeypatch.setattr(TMLEEstimator, "report_from_result", staticmethod(original))
    assert pickle.loads(pickle.dumps(original)) is original  # noqa: S301 - trusted local function identity.
    report = produced["report"]
    decoded = CausalEffectReport.model_validate_json(report.model_dump_json())
    assert decoded.model_dump(mode="json") == report.model_dump(mode="json")


@pytest.mark.parametrize("method", [method for method in CausalMethod if method.value != "tmle"])
def test_existing_report_json_reader_and_candidate_semantics_remain(
    method: CausalMethod,
) -> None:
    report = CausalEffectReport(
        method=method,
        estimand="existing estimand",
        point_estimate=0.3,
        confidence_interval=(0.1, 0.5),
        inference_method="asymptotic",
        sample_size=100,
        n_treated=50,
        n_control=50,
        pre_periods=0,
        post_periods=0,
    )
    decoded = CausalEffectReport.model_validate(json.loads(report.model_dump_json()))
    assert decoded == report
    assert decoded.to_uncertainty_envelope().gate_eligible is False


def test_real_default_method_job_uses_current_public_contract_and_all_folds(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    defaults = core.ATENuisanceContract.from_params({})
    public = {p.name: p.default for p in TMLEEstimator.signature.parameters}
    assert public == {field.name: getattr(defaults, field.name) for field in fields(defaults)}
    assert public["outcome_scaling"] == "auto"
    data = _data()
    calls = []
    native = core._fit_crossfit_fold

    def observe(**kwargs):
        calls.append((kwargs["rep_seed"], kwargs["fold_id"], kwargs["test_idx"].copy()))
        return native(**kwargs)

    monkeypatch.setattr(core, "_SHARED_NUISANCE_CACHE", {})
    monkeypatch.setattr(core, "_SHARED_NUISANCE_CACHE_ORDER", [])
    monkeypatch.setattr(core, "_fit_crossfit_fold", observe)
    saved, _ = _run(tmp_path, data, {})
    assert len(calls) == defaults.crossfit_folds * defaults.n_repeats == 15
    for seed in (42, 1039, 2036):
        assert sorted(
            i for current, _, indices in calls if current == seed for i in indices
        ) == list(range(600))
    warm = TMLEEstimator.pure_step(_legacy(data), {})
    assert to_python_data(warm["result"], sort_keys=True) == saved["result"]
    assert len(calls) == 15
    report = CausalEffectReport.model_validate(saved["report"])
    assert report.point_estimate == saved["result"]["ate"]
    assert report.confidence_interval == (saved["result"]["ci_lower"], saved["result"]["ci_upper"])
    assert report.to_uncertainty_envelope().gate_eligible is False


def test_nonfinite_numerical_projection_is_point_free_without_reestimation() -> None:
    data = _data()
    result = TMLEEstimator.pure_step(data, _params())["result"]
    for changes in (
        {"ate": np.nan},
        {"standard_error": np.inf},
        {"ci_lower": 1.0, "ci_upper": -1.0},
    ):
        report = TMLEEstimator.report_from_result(
            data=data, params=_params(), result={**result, **changes}
        )
        assert report.status is EstimationStatus.NUMERICAL_FAILURE
        assert report.point_estimate is None and report.confidence_interval is None
        assert report.to_uncertainty_envelope().gate_eligible is False
