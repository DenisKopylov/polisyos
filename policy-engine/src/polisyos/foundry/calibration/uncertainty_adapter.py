"""Translate calibration Hessian diagnostics into governance-ready envelopes."""
from __future__ import annotations

import math
from statistics import NormalDist
from typing import Mapping

from polisyos.foundry.calibration.report import CalibrationReport
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)


def _z_score(confidence_level: float) -> float:
    if not (0.0 < confidence_level < 1.0):
        raise ValueError("confidence_level must be in (0, 1)")
    return NormalDist().inv_cdf((1.0 + confidence_level) / 2.0)


def envelope_from_calibration_param(
    report: CalibrationReport,
    param_name: str,
    *,
    confidence_level: float = 0.95,
) -> UncertaintyEnvelope | None:
    """Build a normal-approximation uncertainty envelope for one calibrated parameter.

    Args:
        report: Calibration report containing point estimates and optional
            `CalibrationUncertainty` diagnostics.
        param_name: Parameter key in `report.calibrated_params`.
        confidence_level: Two-sided confidence level in `(0, 1)`.

    Returns:
        `UncertaintyEnvelope` for the requested parameter, or `None` when the
        report does not contain enough finite uncertainty information.

    Raises:
        ValueError: If `confidence_level` is outside `(0, 1)`.
    """
    if report.uncertainties is None:
        return None

    unc = report.uncertainties
    if param_name not in unc.params:
        return None
    idx = unc.params.index(param_name)
    if idx >= len(unc.std):
        return None

    point = report.calibrated_params.get(param_name)
    if point is None:
        return None

    std = float(unc.std[idx])
    if not math.isfinite(std) or std < 0.0:
        return None
    if not math.isfinite(point):
        return None

    z = _z_score(confidence_level)
    ci_lower = float(point) - z * std
    ci_upper = float(point) + z * std

    metadata: dict[str, object] = {
        "param_name": param_name,
        "std": std,
        "hessian_rank": unc.hessian_rank,
        "hessian_condition": unc.hessian_condition,
        "damping": unc.damping,
        "method": unc.method,
        "non_identifiable": param_name in unc.non_identifiable,
        "covariance_row": list(unc.covariance[idx]) if idx < len(unc.covariance) else None,
        "covariance_params": list(unc.params),
    }

    if report.identifiability is not None:
        for p in report.identifiability.params:
            if p.name == param_name:
                metadata["identifiability_status"] = p.status.value
                metadata["identifiability_eigenvalue"] = p.eigenvalue
                break

    return UncertaintyEnvelope(
        point_estimate=float(point),
        confidence_interval=(ci_lower, ci_upper),
        confidence_level=confidence_level,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        sample_size=None,
        is_heuristic_ci=False,
        gate_eligible=True,
        metadata=metadata,
    )


def envelopes_from_calibration(
    report: CalibrationReport,
    *,
    confidence_level: float = 0.95,
) -> Mapping[str, UncertaintyEnvelope]:
    """Build uncertainty envelopes for every calibrated parameter with usable Hessian stats."""
    result: dict[str, UncertaintyEnvelope] = {}
    for param_name in report.calibrated_params:
        env = envelope_from_calibration_param(
            report,
            param_name,
            confidence_level=confidence_level,
        )
        if env is not None:
            result[param_name] = env
    return result


__all__ = [
    "envelope_from_calibration_param",
    "envelopes_from_calibration",
]
