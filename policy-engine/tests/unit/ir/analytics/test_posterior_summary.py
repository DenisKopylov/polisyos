from __future__ import annotations

import base64

import numpy as np
import pytest
from pydantic import ValidationError

import polisyos.ir.analytics.posterior_summary as posterior_module
from polisyos import ir as ir_facade
from polisyos.foundry.methods.catalog.bayesian.protocols import canonical_draws_artifact
from polisyos.ir import analytics as analytics_facade
from polisyos.ir.analytics.posterior_summary import (
    PosteriorParameterSummary,
    PosteriorPointRole,
    PosteriorSummaryRef,
    PosteriorSummaryV11,
    summarize_posterior_draw_artifact,
)
from polisyos.ir.analytics.uncertainty import (
    IntervalSemantics,
    UncertaintyEnvelope,
    UncertaintySource,
)
from polisyos.ir.model_layer.canon import CanonSpec, content_hash, to_canonical_bytes


def test_posterior_summary_types_are_exported_by_the_curated_ir_facade() -> None:
    source_types = {
        "PosteriorPointRole": PosteriorPointRole,
        "PosteriorParameterSummary": PosteriorParameterSummary,
        "PosteriorSummaryRef": PosteriorSummaryRef,
        "PosteriorSummaryV11": PosteriorSummaryV11,
    }

    assert set(source_types).issubset(set(analytics_facade.__all__))
    for name, source_type in source_types.items():
        assert getattr(analytics_facade, name) is source_type
        assert getattr(ir_facade, name) is source_type


def _serialized_draws(samples: dict[str, np.ndarray]) -> tuple[str, dict[str, object], str]:
    artifact_ref, payload, artifact_hash, _layout = canonical_draws_artifact(
        samples,
        method_name="test_posterior_summary",
        sampler_kernel="hmc",
        stage="posterior",
    )
    return artifact_ref, payload, artifact_hash


@pytest.mark.parametrize(
    ("point_role", "expected_point"),
    [
        (PosteriorPointRole.POSTERIOR_MEAN, 1.0),
        (PosteriorPointRole.POSTERIOR_MEDIAN, 0.0),
    ],
)
def test_b201_keeps_named_point_functional_separate_from_equal_tail_interval(
    point_role: PosteriorPointRole,
    expected_point: float,
) -> None:
    artifact_ref, payload, artifact_hash = _serialized_draws(
        {"theta": np.asarray([[0.0] * 99 + [100.0]], dtype=np.float64)}
    )

    summary = summarize_posterior_draw_artifact(
        artifact_ref=artifact_ref,
        artifact_payload=payload,
        artifact_hash=artifact_hash,
        credible_mass=0.9,
        point_role=point_role,
    )

    theta = summary.parameters["theta"]
    assert theta.posterior_mean == 1.0
    assert theta.posterior_median == 0.0
    assert theta.equal_tail_interval == (0.0, 0.0)
    assert summary.point_role is point_role
    assert theta.selected_point == expected_point
    assert summary.gate_eligible is False
    assert summary.unit_binding_status == "not_established"
    assert summary.source_weights is None
    assert summary.draw_order == tuple(range(100))

    with pytest.raises(ValidationError, match="must lie within"):
        UncertaintyEnvelope(
            point_estimate=1.0,
            confidence_interval=(0.0, 0.0),
            confidence_level=0.9,
            source=UncertaintySource.CALIBRATION,
            interval_semantics=IntervalSemantics.CREDIBLE_INTERVAL,
        )


def test_b202_keeps_exact_joint_draw_rows_for_matched_marginals() -> None:
    same_rows = np.asarray([[-1.0, 1.0, -1.0, 1.0]], dtype=np.float64)
    reversed_rows = np.asarray([[1.0, -1.0, 1.0, -1.0]], dtype=np.float64)
    same_ref, same_payload, same_hash = _serialized_draws({"x": same_rows, "y": same_rows})
    reversed_ref, reversed_payload, reversed_hash = _serialized_draws(
        {"x": same_rows, "y": reversed_rows}
    )

    same = summarize_posterior_draw_artifact(
        artifact_ref=same_ref,
        artifact_payload=same_payload,
        artifact_hash=same_hash,
        credible_mass=0.9,
        point_role=PosteriorPointRole.POSTERIOR_MEAN,
    )
    reversed_pairing = summarize_posterior_draw_artifact(
        artifact_ref=reversed_ref,
        artifact_payload=reversed_payload,
        artifact_hash=reversed_hash,
        credible_mass=0.9,
        point_role=PosteriorPointRole.POSTERIOR_MEAN,
    )

    assert same.parameters["x"].posterior_mean == reversed_pairing.parameters["x"].posterior_mean
    assert same.parameters["y"].posterior_mean == reversed_pairing.parameters["y"].posterior_mean
    assert same.parameters["x"].draws == reversed_pairing.parameters["x"].draws
    assert same.parameters["y"].draws == tuple(reversed(reversed_pairing.parameters["y"].draws))
    assert same.source_draws_hash != reversed_pairing.source_draws_hash
    assert same.joint_row_values(("x", "y")) == ((-1.0, -1.0), (1.0, 1.0), (-1.0, -1.0), (1.0, 1.0))
    assert reversed_pairing.joint_row_values(("x", "y")) == (
        (-1.0, 1.0),
        (1.0, -1.0),
        (-1.0, 1.0),
        (1.0, -1.0),
    )


def test_posterior_draw_artifact_refuses_mismatched_axis_shapes() -> None:
    artifact_ref, payload, artifact_hash = _serialized_draws(
        {
            "x": np.asarray([[1.0, 2.0]], dtype=np.float64),
            "y": np.asarray([[3.0, 4.0, 5.0]], dtype=np.float64),
        }
    )

    with pytest.raises(ValueError, match="share chain/draw axes"):
        summarize_posterior_draw_artifact(
            artifact_ref=artifact_ref,
            artifact_payload=payload,
            artifact_hash=artifact_hash,
            credible_mass=0.9,
            point_role=PosteriorPointRole.POSTERIOR_MEAN,
        )


def test_posterior_draw_artifact_refuses_unhandled_source_weights() -> None:
    _artifact_ref, payload, _artifact_hash = _serialized_draws(
        {"theta": np.asarray([[1.0, 2.0, 3.0]], dtype=np.float64)}
    )
    weighted_payload = {**payload, "weights": [0.8, 0.1, 0.1]}
    weighted_hash = content_hash(
        to_canonical_bytes(weighted_payload, CanonSpec(forbid_floats=False)),
        prefix=True,
    )

    with pytest.raises(ValueError, match="weights unsupported"):
        summarize_posterior_draw_artifact(
            artifact_ref=f"artifact://foundry/bayesian/posterior/{weighted_hash}",
            artifact_payload=weighted_payload,
            artifact_hash=weighted_hash,
            credible_mass=0.9,
            point_role=PosteriorPointRole.POSTERIOR_MEAN,
        )


@pytest.mark.parametrize(
    "samples",
    [
        {"x": np.asarray([[[1.0], [2.0]]]), "x[0]": np.asarray([[10.0, 20.0]])},
        {
            "tensor": np.asarray([[[[1.0, 2.0]], [[3.0, 4.0]]]]),
            "tensor[0,1]": np.asarray([[10.0, 20.0]]),
        },
        {
            "x[0]": np.asarray([[[1.0], [2.0]], [[3.0], [4.0]]]),
            "x[0][0]": np.asarray([[10.0, 20.0], [30.0, 40.0]]),
        },
    ],
)
@pytest.mark.parametrize("reverse_source_order", [False, True])
def test_posterior_draw_artifact_refuses_ambiguous_scalar_coordinate_projection(
    samples: dict[str, np.ndarray], reverse_source_order: bool
) -> None:
    if reverse_source_order:
        samples = dict(reversed(tuple(samples.items())))
    artifact_ref, payload, artifact_hash = _serialized_draws(samples)

    with pytest.raises(ValueError, match="scalar coordinate projection is ambiguous"):
        summarize_posterior_draw_artifact(
            artifact_ref=artifact_ref,
            artifact_payload=payload,
            artifact_hash=artifact_hash,
            credible_mass=0.9,
            point_role=PosteriorPointRole.POSTERIOR_MEAN,
        )


def test_posterior_draw_artifact_preserves_noncolliding_multichain_coordinates() -> None:
    samples = {
        "x": np.asarray([[[1.0, 2.0], [3.0, 4.0]], [[5.0, 6.0], [7.0, 8.0]]]),
        "x[2]": np.asarray([[10.0, 20.0], [30.0, 40.0]]),
    }
    artifact_ref, payload, artifact_hash = _serialized_draws(samples)

    summary = summarize_posterior_draw_artifact(
        artifact_ref=artifact_ref,
        artifact_payload=payload,
        artifact_hash=artifact_hash,
        credible_mass=0.9,
        point_role=PosteriorPointRole.POSTERIOR_MEAN,
    )

    assert summary.parameter_order == ("x[0]", "x[1]", "x[2]")
    assert summary.parameters["x[0]"].draws == (1.0, 3.0, 5.0, 7.0)
    assert summary.parameters["x[1]"].draws == (2.0, 4.0, 6.0, 8.0)
    assert summary.parameters["x[2]"].source_parameter == "x[2]"
    assert summary.parameters["x[2]"].source_coordinate == ()


def test_constructed_summary_cannot_bypass_coordinate_identity() -> None:
    artifact_ref, payload, artifact_hash = _serialized_draws({"x": np.asarray([[[1.0], [2.0]]])})
    valid = summarize_posterior_draw_artifact(
        artifact_ref=artifact_ref,
        artifact_payload=payload,
        artifact_hash=artifact_hash,
        credible_mass=0.9,
        point_role=PosteriorPointRole.POSTERIOR_MEAN,
    )
    forged = valid.model_dump(mode="python")
    forged["parameters"] = {"alias": forged["parameters"]["x[0]"]}
    forged["parameter_order"] = ("alias",)

    with pytest.raises(ValidationError, match="source axes or declarations are inconsistent"):
        PosteriorSummaryV11.model_validate(forged)


def test_posterior_source_projection_preserves_tensor_and_isolated_bracket_names() -> None:
    artifact_ref, payload, artifact_hash = _serialized_draws(
        {
            "tensor": np.arange(16, dtype=np.float64).reshape(2, 2, 2, 2),
            "tensor[2]": np.asarray([[20.0, 30.0], [40.0, 50.0]]),
        }
    )
    summary = summarize_posterior_draw_artifact(
        artifact_ref=artifact_ref,
        artifact_payload=payload,
        artifact_hash=artifact_hash,
        credible_mass=0.9,
        point_role=PosteriorPointRole.POSTERIOR_MEAN,
    )
    assert summary.parameter_order == (
        "tensor[0,0]",
        "tensor[0,1]",
        "tensor[1,0]",
        "tensor[1,1]",
        "tensor[2]",
    )
    assert summary.parameters["tensor[0,0]"].draws == (0.0, 4.0, 8.0, 12.0)
    assert summary.parameters["tensor[0,1]"].draws == (1.0, 5.0, 9.0, 13.0)
    assert summary.parameters["tensor[1,0]"].draws == (2.0, 6.0, 10.0, 14.0)
    assert summary.parameters["tensor[1,1]"].draws == (3.0, 7.0, 11.0, 15.0)
    assert summary.parameters["tensor[2]"].draws == (20.0, 30.0, 40.0, 50.0)
    assert summary.parameters["tensor[2]"].source_parameter == "tensor[2]"
    assert summary.parameters["tensor[2]"].source_coordinate == ()


@pytest.mark.parametrize("container", ["source", "layout", "array"])
def test_unweighted_source_format_refuses_any_undeclared_record_field(container: str) -> None:
    _ref, payload, _digest = _serialized_draws(
        {"theta": np.asarray([[0.0, 1.0], [2.0, 3.0]], dtype=np.float64)}
    )
    if container == "source":
        target = payload
    elif container == "layout":
        target = payload["draw_layout"]
    else:
        target = payload["parameters"]["theta"]
    target["undeclared_source_extension"] = {"mass": [0.7, 0.1, 0.1, 0.1]}
    digest = content_hash(to_canonical_bytes(payload, CanonSpec(forbid_floats=False)), prefix=True)
    ref = f"artifact://foundry/bayesian/posterior/{digest}"
    with pytest.raises(ValueError, match="source format is undeclared or malformed"):
        summarize_posterior_draw_artifact(
            artifact_ref=ref,
            artifact_payload=payload,
            artifact_hash=digest,
            credible_mass=0.9,
            point_role=PosteriorPointRole.POSTERIOR_MEAN,
        )


def test_source_hash_and_decoding_use_the_same_private_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ref, payload, digest = _serialized_draws(
        {"theta": np.asarray([[1.0, 2.0], [3.0, 4.0]], dtype="<f8")}
    )
    original_bytes = payload["parameters"]["theta"]["data_base64"]
    changed_bytes = base64.b64encode(
        np.asarray([[99.0, 2.0], [3.0, 4.0]], dtype="<f8").tobytes(order="C")
    ).decode("ascii")
    actual_hash = posterior_module.content_hash
    observed_hash_calls: list[bytes] = []

    def hash_then_change_caller_bytes(data: bytes, *, prefix: bool = False) -> str:
        # Never fake or weaken the real digest: mutate only the external
        # caller's data after the actual admitted bytes have been hashed.
        result = actual_hash(data, prefix=prefix)
        observed_hash_calls.append(data)
        if len(observed_hash_calls) == 1:
            payload["parameters"]["theta"]["data_base64"] = changed_bytes
        return result

    monkeypatch.setattr(posterior_module, "content_hash", hash_then_change_caller_bytes)
    captured = None
    captured_refusal: str | None = None
    try:
        captured = summarize_posterior_draw_artifact(
            artifact_ref=ref,
            artifact_payload=payload,
            artifact_hash=digest,
            credible_mass=0.9,
            point_role=PosteriorPointRole.POSTERIOR_MEAN,
        )
    except ValueError as exc:
        # Keep the actual refusal in the named failure; an import/setup error
        # does not qualify as the source-snapshot property removal.
        captured_refusal = str(exc)
    assert observed_hash_calls
    assert captured is not None, (
        f"admitted source snapshot was lost after the hash boundary: {captured_refusal}"
    )
    assert captured.source_draws_ref == ref
    assert captured.source_draws_hash == digest
    assert captured.source_draws_payload["parameters"]["theta"]["data_base64"] == original_bytes
    assert captured.parameters["theta"].draws == (1.0, 2.0, 3.0, 4.0)
    assert payload["parameters"]["theta"]["data_base64"] == changed_bytes
    payload.clear()
    assert captured.parameters["theta"].draws == (1.0, 2.0, 3.0, 4.0)
    assert captured.source_draws_payload["parameters"]["theta"]["data_base64"] == original_bytes


@pytest.mark.parametrize("parameter_name", ["sample_weight", "weights", "metadata"])
def test_fixed_source_record_does_not_ban_parameter_vocabulary(parameter_name: str) -> None:
    ref, payload, digest = _serialized_draws(
        {parameter_name: np.asarray([[1.0, 2.0], [3.0, 4.0]], dtype="<f8")}
    )
    summary = summarize_posterior_draw_artifact(
        artifact_ref=ref,
        artifact_payload=payload,
        artifact_hash=digest,
        credible_mass=0.9,
        point_role=PosteriorPointRole.POSTERIOR_MEAN,
    )
    assert summary.parameter_order == (parameter_name,)
    assert summary.parameters[parameter_name].draws == (1.0, 2.0, 3.0, 4.0)
    assert summary.parameters[parameter_name].posterior_mean == 2.5
