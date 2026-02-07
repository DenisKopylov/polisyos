from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    load_uncertainty_envelope,
    persist_uncertainty_envelope,
)


def test_uncertainty_envelope_basic_creation() -> None:
    env = UncertaintyEnvelope(
        point_estimate=2.35,
        confidence_interval=(1.92, 2.78),
        source=UncertaintySource.CALIBRATION,
        distribution_family=DistributionFamily.NORMAL,
        propagation_method=PropagationMethod.DELTA_METHOD,
    )
    assert env.confidence_level == 0.95
    assert env.interval_semantics == IntervalSemantics.CONFIDENCE_INTERVAL
    assert env.ci_width == pytest.approx(0.86)


def test_uncertainty_envelope_rejects_invalid_ci() -> None:
    with pytest.raises(ValidationError):
        UncertaintyEnvelope(
            point_estimate=2.0,
            confidence_interval=(3.0, 1.0),
            source=UncertaintySource.TRUST,
            confidence_level=None,
            interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
        )


def test_uncertainty_envelope_requires_confidence_level_for_statistical_interval() -> None:
    with pytest.raises(ValidationError):
        UncertaintyEnvelope(
            point_estimate=0.4,
            confidence_interval=(0.2, 0.6),
            source=UncertaintySource.CALIBRATION,
            confidence_level=None,
            interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        )


def test_uncertainty_envelope_heuristic_gate_constraints() -> None:
    with pytest.raises(ValidationError):
        UncertaintyEnvelope(
            point_estimate=0.7,
            confidence_interval=(0.6, 0.8),
            source=UncertaintySource.CONFLICT_RESOLUTION,
            confidence_level=None,
            interval_semantics=IntervalSemantics.HEURISTIC_RANGE,
            is_heuristic_ci=True,
            gate_eligible=True,
        )


def test_uncertainty_envelope_relative_uncertainty_near_zero() -> None:
    env = UncertaintyEnvelope(
        point_estimate=1e-16,
        confidence_interval=(-0.1, 0.1),
        source=UncertaintySource.MANUAL,
        confidence_level=None,
        interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
    )
    assert env.relative_uncertainty is None


def test_uncertainty_envelope_cas_roundtrip(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    env = UncertaintyEnvelope(
        point_estimate=42.0,
        confidence_interval=(40.0, 44.0),
        source=UncertaintySource.TRUST,
        confidence_level=None,
        interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
        metadata={"trust_policy_id": "strict"},
    )

    ref_1 = persist_uncertainty_envelope(store, env)
    ref_2 = persist_uncertainty_envelope(store, env)
    loaded = load_uncertainty_envelope(store, ref_1)

    assert ref_1.kind == "ir.uncertainty_envelope"
    assert ref_1.artifact_id == ref_2.artifact_id
    assert loaded == env
