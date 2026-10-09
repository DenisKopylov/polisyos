from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError

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
