from __future__ import annotations

import numpy as np

from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PosteriorSamplesCarrier,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)
from polisyos.scientist.nodes.builtins.simulate.welfare_covariance import (
    _resolve_empirical_row_sampler,
)
from polisyos.scientist.nodes.builtins.simulate.welfare_draws import _sample_empirical_row


def _envelope(
    name: str,
    samples: tuple[float, ...],
    *,
    joint_id: str = "declared-pair",
    sample_axis: str = "rows",
) -> UncertaintyEnvelope:
    return UncertaintyEnvelope(
        point_estimate=float(samples[0]),
        confidence_interval=(min(samples), max(samples)),
        distribution_family=DistributionFamily.BOOTSTRAP,
        distribution_payload=PosteriorSamplesCarrier(
            samples=samples,
            sample_axis=sample_axis,
        ),
        source=UncertaintySource.BOOTSTRAP,
        propagation_method=PropagationMethod.MONTE_CARLO,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        metadata={"param_name": name, "joint_sample_id": joint_id},
    )


def test_empirical_joint_sampler_preserves_row_pairing_not_just_marginals() -> None:
    aligned = {
        "left": _envelope("left", (1.0, 2.0)),
        "right": _envelope("right", (10.0, 20.0)),
    }
    reversed_rows = {
        "left": _envelope("left", (1.0, 2.0)),
        "right": _envelope("right", (20.0, 10.0)),
    }

    sampler, limitation = _resolve_empirical_row_sampler(
        ["left", "right"], aligned, calibration_coordinates_active=False
    )
    reversed_sampler, reversed_limitation = _resolve_empirical_row_sampler(
        ["left", "right"], reversed_rows, calibration_coordinates_active=False
    )

    assert limitation is None and reversed_limitation is None
    assert sampler is not None and reversed_sampler is not None
    assert sampler.dependence_note["strategy"] == "empirical_joint_rows"
    assert sampler.dependence_note["joint_identity_status"] == "declared_non_authoritative"
    first_pair = _sample_empirical_row(np.random.default_rng(12), sampler)
    second_pair = _sample_empirical_row(np.random.default_rng(12), reversed_sampler)
    assert first_pair["left"] == second_pair["left"]
    assert first_pair["right"] != second_pair["right"]


def test_empty_axis_does_not_admit_declared_joint_rows() -> None:
    envelopes = {
        "left": _envelope("left", (1.0, 2.0), sample_axis=" "),
        "right": _envelope("right", (10.0, 20.0), sample_axis=" "),
    }

    sampler, limitation = _resolve_empirical_row_sampler(
        ["left", "right"], envelopes, calibration_coordinates_active=False
    )

    assert sampler is None
    assert limitation == "empirical_joint_law_missing"
