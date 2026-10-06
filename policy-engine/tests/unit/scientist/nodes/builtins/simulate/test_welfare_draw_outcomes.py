"""Independent bounded support controls through welfare persistence/readback."""

from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    UncertaintyEnvelope,
    UncertaintySource,
)
from polisyos.ir.analytics.welfare import (
    WelfareSampleBundle,
    load_welfare_sample_bundle,
)
from polisyos.ir.registry.refs import ArtifactRefModel
from polisyos.scientist.nodes.builtins.simulate import propagate_welfare as module


def _run(
    store,
    *,
    count=2048,
    evaluator=None,
    envelopes=None,
    method="monte_carlo",
    calibration_source=None,
):
    ctx = SimpleNamespace(store=store)
    state = SimpleNamespace(
        params={
            "propagation_config": {"mc_n_samples": count, "mc_min_valid_samples": 10, "mc_seed": 23}
        }
    )
    env = UncertaintyEnvelope(
        source=UncertaintySource.CALIBRATION,
        point_estimate=0.0,
        confidence_interval=(-1.0, 1.0),
        confidence_level=None,
        distribution_family=DistributionFamily.UNIFORM,
        interval_semantics=IntervalSemantics.HEURISTIC_RANGE,
        is_heuristic_ci=True,
        gate_eligible=False,
    )
    envelopes = envelopes or {"x": env}
    called = []

    def partial_evaluator(**params):
        called.append(params)
        value = params["x"] if params["x"] >= 0 else np.nan
        return dict.fromkeys(module._WELFARE_DRAW_METRICS, value)

    context = SimpleNamespace(
        dependence_context=module._ResolvedDependenceContext(
            ref=None,
            structure=None,
            correlation_matrix=None,
            parameter_order=tuple(envelopes),
            strategy="unknown",
            warnings=(),
            diagnostics={},
        ),
        dependence_structure_ref=None,
    )
    result = module._propagate_credible_interval(
        ctx,
        state,
        welfare_params={"credible_method": method},
        context=context,
        simulation_fn=evaluator or partial_evaluator,
        nominal_params=dict.fromkeys(envelopes, 0.0),
        input_envelopes=envelopes,
        calibration_source=calibration_source,
    )
    return result, called


def test_partial_support_retains_all_inputs_outcomes_and_only_conditional_estimates(tmp_path):
    store = FileSystemCAS(tmp_path)
    result, called = _run(store)
    fresh = FileSystemCAS(tmp_path)
    samples = module._load_verified_welfare_samples(fresh, result.sample_bundle_ref)
    receipt = module._load_welfare_draw_outcomes(
        fresh, ArtifactRef.model_validate(result.diagnostics["draw_outcomes_ref"])
    )
    inputs = np.asarray([row["x"] for row in called])
    success = inputs[inputs >= 0]
    assert len(called) == 2048
    assert len(success) == 1033
    assert receipt["requested_draw_count"] == receipt["attempted_draw_count"] == 2048
    assert receipt["successful_draw_count"] == 1033
    assert receipt["failed_draw_count"] == 1015
    assert receipt["unattempted_draw_count"] == 0
    assert (
        len(receipt["draw_records"])
        == len(receipt["sampled_inputs"])
        == len(receipt["output_records"])
        == 2048
    )
    assert [row["sampled_input"] for row in receipt["sampled_inputs"]] == called
    assert all(
        outcome["outcome_code"] == "non_finite_output"
        for row in receipt["failure_records"]
        for outcome in row["output_outcomes"]
    )
    np.testing.assert_array_equal(samples.welfare_draws, success)
    assert result.credible_interval is None
    assert result.result_map["welfare"]["point_estimate"] is None
    assert result.result_map["welfare"]["conditional_mean"] == pytest.approx(success.mean())
    assert success.mean() == pytest.approx(0.5, abs=0.03)
    assert inputs.mean() == pytest.approx(0.0, abs=0.03)
    assert samples.metadata["estimate_scope"] == "conditional_on_all_outputs_finite"
    assert samples.metadata["gate_eligible"] is False
    report = module.from_canonical_bytes(
        fresh.get_bytes(ArtifactRef.model_validate(result.report_ref.model_dump()))
    )
    assert report["input_parameter_sample_means"]["x"] == pytest.approx(inputs.mean())
    assert report["draw_summary"]["welfare_mean"] is None
    assert report["draw_summary"]["conditional_welfare_mean"] == pytest.approx(success.mean())
    assert report["nominal_parameter_values"] == {"x": 0.0}
    assert report["gate_eligible"] is False


@pytest.mark.parametrize(
    "corruption",
    [
        "count",
        "removed_failure",
        "input_hash",
        "successful_input_removed",
        "input_index_type",
        "orphan",
        "failed_count_type",
        "support_type",
        "parameter_order_type",
        "scope",
        "sample_order",
    ],
)
def test_fresh_cas_reader_rejects_marker_preserving_outcome_corruption(tmp_path, corruption):
    store = FileSystemCAS(tmp_path)
    result, _ = _run(store, count=128)
    samples = module._load_verified_welfare_samples(store, result.sample_bundle_ref)
    receipt = module._load_welfare_draw_outcomes(
        store, ArtifactRef.model_validate(samples.metadata["draw_outcomes_ref"])
    )
    forged = deepcopy(receipt)
    metadata = dict(samples.metadata)
    values = samples.welfare_draws
    if corruption == "count":
        forged["successful_draw_count"] = 128
    elif corruption == "removed_failure":
        forged["failure_records"].pop()
    elif corruption == "input_hash":
        forged["sampled_inputs"][0]["sampled_input"]["x"] += 0.1
    elif corruption == "successful_input_removed":
        index = forged["successful_sample_draw_indices"][0]
        forged["sampled_inputs"][index]["sampled_input"] = None
        forged["draw_records"][index]["sampled_input_sha256"] = module.sampling_content_digest(None)
    elif corruption == "input_index_type":
        forged["sampled_inputs"][0]["draw_index"] = False
    elif corruption == "orphan":
        forged["output_records"].append({"draw_index": 128, "successful_values": {}})
    elif corruption == "failed_count_type":
        forged["failed_draw_count"] = float(forged["failed_draw_count"])
    elif corruption == "support_type":
        forged["support_complete"] = 0
    elif corruption == "parameter_order_type":
        forged["parameter_order"] = "x"
    elif corruption == "scope":
        metadata["estimate_scope"] = "all_requested_draws"
    else:
        values = tuple(reversed(values))
    outcome_ref = store.put_json(
        forged,
        PutOptions(
            kind="foundry.welfare_draw_outcomes",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.foundry.WelfareDrawOutcomes", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    metadata["draw_outcomes_ref"] = outcome_ref.model_dump(mode="json")
    fake_samples = WelfareSampleBundle(
        welfare_draws=values,
        welfare_pe_draws=samples.welfare_pe_draws,
        welfare_ge_draws=samples.welfare_ge_draws,
        metadata=metadata,
    )
    fake_ref = store.put_json(
        fake_samples.model_dump(mode="json"),
        PutOptions(
            kind="ir.welfare_sample_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="ir.welfare_sample_bundle", version="1.0"),
            inputs=[
                InputRef(
                    artifact_id=outcome_ref.artifact_id,
                    role="draw_outcomes",
                    manifest_profile_sha256=outcome_ref.manifest_profile_sha256,
                )
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    fresh = FileSystemCAS(tmp_path)
    # The former payload-only reader accepts the same plausible success array.
    assert len(load_welfare_sample_bundle(fresh, fake_ref).welfare_draws) == len(values)
    with pytest.raises(ValueError):
        module._load_verified_welfare_samples(fresh, fake_ref)


def test_evaluator_exceptions_are_terminal_outcomes_in_the_full_denominator(tmp_path):
    def evaluator(x):
        if x < 0:
            raise ArithmeticError("synthetic undefined region")
        return dict.fromkeys(module._WELFARE_DRAW_METRICS, x)

    store = FileSystemCAS(tmp_path)
    result, _ = _run(store, count=128, evaluator=evaluator)
    receipt = module._load_welfare_draw_outcomes(
        FileSystemCAS(tmp_path), ArtifactRef.model_validate(result.diagnostics["draw_outcomes_ref"])
    )
    assert receipt["failed_draw_count"] > 0
    assert all(
        outcome["outcome_code"] == "simulation_exception"
        and outcome["error_type"] == "ArithmeticError"
        for row in receipt["failure_records"]
        for outcome in row["output_outcomes"]
    )
    assert result.credible_interval is None


def test_all_failed_budget_still_persists_complete_terminal_receipt(tmp_path):
    store = FileSystemCAS(tmp_path)
    with pytest.raises(module._WelfareNodeFailure) as error:
        _run(
            store,
            count=128,
            evaluator=lambda **_: dict.fromkeys(module._WELFARE_DRAW_METRICS, np.nan),
        )
    receipt = module._load_welfare_draw_outcomes(
        FileSystemCAS(tmp_path),
        ArtifactRef.model_validate(error.value.error.details["draw_outcomes_ref"]),
    )
    assert receipt["attempted_draw_count"] == receipt["failed_draw_count"] == 128
    assert receipt["successful_draw_count"] == receipt["unattempted_draw_count"] == 0


@pytest.mark.parametrize("method", ["monte_carlo", "delta"])
def test_missing_joint_law_is_unknown_before_any_stochastic_callback(tmp_path, method):
    env = UncertaintyEnvelope(
        source=UncertaintySource.CALIBRATION,
        point_estimate=0.0,
        confidence_interval=(-0.1, 0.1),
        distribution_family=DistributionFamily.NORMAL,
        metadata={"std": 0.05},
    )
    calls = []

    def evaluator(**params):
        calls.append(params)
        return dict.fromkeys(module._WELFARE_DRAW_METRICS, params["a"] - params["b"])

    result, _ = _run(
        FileSystemCAS(tmp_path),
        count=128,
        evaluator=evaluator,
        envelopes={"a": env, "b": env},
        method=method,
    )
    assert result.credible_interval is None
    assert result.diagnostics["limitation_codes"] == ["welfare_joint_law_not_established"]
    assert calls == []  # admission precedes every evaluator callback
    if method == "monte_carlo":
        receipt = module._load_welfare_draw_outcomes(
            FileSystemCAS(tmp_path),
            ArtifactRef.model_validate(result.diagnostics["draw_outcomes_ref"]),
        )
        assert receipt["attempted_draw_count"] == 0
        assert receipt["unattempted_draw_count"] == 128
        assert receipt["unattempted_draw_indices"] == list(range(128))
    with pytest.raises(ValueError, match="not established"):
        module._build_parameter_covariance(
            None, param_names=["a", "b"], input_envelopes={"a": env, "b": env}
        )


@pytest.mark.parametrize("failed_channel", ["welfare_pe", "welfare_ge"])
def test_one_failed_channel_does_not_hide_success_values_or_unconditional_moments(
    tmp_path, failed_channel
):
    def evaluator(x):
        values = dict.fromkeys(module._WELFARE_DRAW_METRICS, x)
        if x < 0:
            values.pop(failed_channel)
        return values

    store = FileSystemCAS(tmp_path)
    result, _ = _run(store, count=128, evaluator=evaluator)
    receipt = module._load_welfare_draw_outcomes(
        FileSystemCAS(tmp_path), ArtifactRef.model_validate(result.diagnostics["draw_outcomes_ref"])
    )
    assert result.credible_interval is None
    for row in receipt["draw_records"]:
        assert row["failed_outputs"] in ([], [failed_channel])
        if row["failed_outputs"]:
            assert set(row["successful_outputs"]) == set(module._WELFARE_DRAW_METRICS) - {
                failed_channel
            }
    report = module.from_canonical_bytes(
        store.get_bytes(ArtifactRef.model_validate(result.report_ref.model_dump()))
    )
    summary = report["draw_summary"]
    assert summary["estimate_scope"] == "conditional_on_all_outputs_finite"
    assert all(
        summary[key] is None
        for key in ("welfare_mean", "welfare_std", "welfare_pe_mean", "welfare_ge_mean")
    )
    assert all(
        summary[key] is not None
        for key in (
            "conditional_welfare_mean",
            "conditional_welfare_std",
            "conditional_welfare_pe_mean",
            "conditional_welfare_ge_mean",
        )
    )


@pytest.mark.parametrize("method", ["monte_carlo", "delta"])
def test_invalid_report_covariance_refuses_before_any_evaluator_callback(tmp_path, method):
    store = FileSystemCAS(tmp_path)
    source_ref = store.put_json(
        {}, PutOptions(kind="test.calibration_source", media_type="application/json")
    )
    source = module._CalibrationCovarianceSource(
        report_ref=ArtifactRefModel(
            artifact_id=source_ref.artifact_id,
            kind=source_ref.kind,
            media_type=source_ref.media_type,
        ),
        report_schema_version="2.0",
        projection_status="complete",
        field_order=("x",),
        projection_present=True,
        coordinate_projection=None,
        coordinate_order=("x",),
        coordinate_covariance=((-1.0,),),
    )
    env = UncertaintyEnvelope(
        point_estimate=0.0,
        confidence_interval=(-1.0, 1.0),
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        metadata={"std": 1.0, "covariance_params": ["x"], "covariance_row": [-1.0]},
    )
    calls = []

    def evaluator(**params):
        calls.append(params)
        return dict.fromkeys(module._WELFARE_DRAW_METRICS, 0.0)

    result, _ = _run(
        store,
        count=128,
        evaluator=evaluator,
        envelopes={"x": env},
        method=method,
        calibration_source=source,
    )
    assert calls == []
    assert result.credible_interval is None
    assert result.diagnostics["limitation_codes"] == ["calibration_covariance_invalid"]
