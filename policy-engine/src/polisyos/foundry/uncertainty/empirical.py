"""Canonical finite empirical weight, sampling, and moment operations."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction

import numpy as np

from polisyos.ir import PosteriorSamplesCarrier, UncertaintyEnvelope


class EmpiricalNumericResolutionError(ValueError):
    """The requested empirical operation cannot retain its finite numeric support."""


@dataclass(frozen=True)
class EmpiricalJointRows:
    """One aligned empirical row law and its optional admitted sampling CDF."""

    names: tuple[str, ...]
    sample_axis: str
    sample_count: int
    samples: Mapping[str, np.ndarray]
    probabilities: np.ndarray
    cumulative: np.ndarray | None
    joint_sample_id: str | None


def normalize_empirical_masses(weights: object) -> np.ndarray:
    """Normalize finite non-negative masses without erasing positive support.

    Args:
        weights: A nonempty vector with at least one positive finite mass.

    Returns:
        The normalized binary64 probabilities.

    Raises:
        ValueError: If masses are invalid or positive support cannot be represented.
    """
    from .covariance import _real_float64

    values = _real_float64(weights)
    if values.ndim != 1 or not values.size:
        raise ValueError("empirical weights must be a non-empty vector")
    if not np.all(np.isfinite(values)) or np.any(values < 0.0):
        raise ValueError("empirical weights must be finite and non-negative")
    with np.errstate(over="ignore", under="ignore", invalid="ignore"):
        total = float(np.sum(values, dtype=np.float64))
        if total == 0.0:
            raise ValueError("empirical weights must have positive mass")
        if math.isfinite(total):
            probabilities = values / total
        else:
            scaled = values / float(np.max(values))
            probabilities = scaled / np.sum(scaled, dtype=np.float64)
    if np.any((values > 0.0) & (probabilities == 0.0)):
        raise EmpiricalNumericResolutionError("empirical numeric resolution erased positive mass")
    return probabilities


def prepare_empirical_cdf(weights: object) -> tuple[np.ndarray, np.ndarray]:
    """Admit and normalize masses without erasing any positive CDF interval.

    Args:
        weights: Non-negative finite binary64 weights, with at least one positive.

    Returns:
        Normalized weights and the matching cumulative distribution.

    Raises:
        ValueError: If the weights are invalid or a positive interval is unreachable.
    """
    from .covariance import _real_float64

    values = _real_float64(weights)
    probabilities = normalize_empirical_masses(values)
    cumulative = np.cumsum(probabilities, dtype=np.float64)
    previous = np.concatenate((np.zeros(1, dtype=np.float64), cumulative[:-1]))
    lower = np.minimum(previous, 1.0)
    upper = np.minimum(cumulative, 1.0)
    if np.any((values > 0.0) & (upper <= lower)):
        raise EmpiricalNumericResolutionError(
            "empirical numeric resolution cannot represent a positive weight interval"
        )
    if not np.all(np.isfinite(cumulative)) or np.any(cumulative < previous):
        raise ValueError("empirical cumulative probabilities must be finite and monotone")
    return probabilities, cumulative


def empirical_indices_from_cdf(
    uniform_samples: object, probabilities: np.ndarray, cumulative: np.ndarray
) -> np.ndarray:
    """Map finite [0, 1) coordinates through an already-admitted empirical CDF.

    Args:
        uniform_samples: Finite uniform coordinates in [0, 1).
        probabilities: Normalized weights returned by ``prepare_empirical_cdf``.
        cumulative: Corresponding cumulative weights from the same admission.

    Returns:
        Integer source-row indices, with zero-weight atoms skipped.

    Raises:
        ValueError: If a coordinate is outside the admitted uniform domain.
    """
    from .covariance import _real_float64

    try:
        uniforms = _real_float64(uniform_samples)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("empirical uniform samples must be finite and in [0, 1)") from exc
    if not np.all(np.isfinite(uniforms)) or np.any((uniforms < 0.0) | (uniforms >= 1.0)):
        raise ValueError("empirical uniform samples must be finite and in [0, 1)")
    indices = np.searchsorted(cumulative, uniforms, side="right")
    last_positive = int(np.flatnonzero(probabilities > 0.0)[-1])
    return np.minimum(indices, last_positive)


def prepare_empirical_joint(
    names: Sequence[str],
    envelopes: Mapping[str, UncertaintyEnvelope],
    *,
    require_sampling_cdf: bool = True,
) -> tuple[EmpiricalJointRows | None, str | None]:
    """Reconcile ordered empirical carriers as one candidate joint row law.

    Args:
        names: Requested coordinate order.
        envelopes: Parameter envelopes carrying empirical sample rows.
        require_sampling_cdf: Also require each positive mass to have a CDF interval.

    Returns:
        The admitted rows and no error, or no rows and a named limitation.
        Joint IDs are declared alignment, not independent provenance.
    """
    # Reuse the same numeric-domain admission as the covariance owner without
    # importing it while that module is still initializing.
    from .covariance import _real_float64

    if len(set(names)) != len(names):
        raise ValueError("empirical coordinate names must be unique")
    carriers = {
        name: envelopes[name].distribution_payload
        for name in names
        if isinstance(envelopes[name].distribution_payload, PosteriorSamplesCarrier)
    }
    if not carriers:
        return None, None
    if len(carriers) != len(names):
        return None, "incompatible_joint_law"
    joint_id: str | None = None
    if len(carriers) > 1:
        ids = [envelopes[name].metadata.get("joint_sample_id") for name in names]
        if not all(isinstance(value, str) and value.strip() for value in ids):
            return None, "unestablished_joint_law"
        normalized_ids = {str(value).strip() for value in ids}
        if len(normalized_ids) != 1:
            return None, "incompatible_joint_law"
        joint_id = normalized_ids.pop()
    first = carriers[names[0]]
    assert isinstance(first, PosteriorSamplesCarrier)
    axis = first.sample_axis.strip()
    count = len(first.samples)
    if not axis or not count:
        return None, "incompatible_joint_law"
    samples: dict[str, np.ndarray] = {}
    probabilities: np.ndarray | None = None
    cumulative: np.ndarray | None = None
    for name in names:
        carrier = carriers[name]
        assert isinstance(carrier, PosteriorSamplesCarrier)
        if carrier.sample_axis.strip() != axis or len(carrier.samples) != count:
            return None, "incompatible_joint_law"
        try:
            column = _real_float64(carrier.samples)
            weights = (
                np.ones(count, dtype=np.float64)
                if carrier.weights is None
                else _real_float64(carrier.weights)
            )
            if column.shape != (count,) or weights.shape != (count,):
                return None, "incompatible_joint_law"
            if require_sampling_cdf:
                normalized, candidate_cdf = prepare_empirical_cdf(weights)
            else:
                normalized = normalize_empirical_masses(weights)
                candidate_cdf = None
        except EmpiricalNumericResolutionError:
            return None, "empirical_numeric_resolution"
        except (TypeError, ValueError, OverflowError):
            return None, "incompatible_joint_law"
        if probabilities is not None and not np.array_equal(normalized, probabilities):
            return None, "incompatible_joint_law"
        if probabilities is None:
            probabilities = normalized
            cumulative = candidate_cdf
        samples[name] = column
    assert probabilities is not None
    return (
        EmpiricalJointRows(
            names=tuple(names),
            sample_axis=axis,
            sample_count=count,
            samples=samples,
            probabilities=probabilities,
            cumulative=cumulative,
            joint_sample_id=joint_id,
        ),
        None,
    )


def empirical_weighted_moments(
    rows: Sequence[Sequence[float]], weights: Sequence[float]
) -> tuple[np.ndarray, np.ndarray]:
    """Compute weighted mean and population covariance for ordered joint rows.

    This operation does not require finite-PRNG CDF intervals: moments and sampling
    have different numeric admission boundaries. Positive mass and nonzero
    covariance must still survive the binary64 calculation.

    Args:
        rows: Nonempty joint sample rows in one shared coordinate order.
        weights: One non-negative finite mass for each row.

    Returns:
        Mean vector and covariance matrix for the declared weighted empirical law.

    Raises:
        ValueError: If the row law or its finite covariance is not representable.
    """
    from .covariance import _real_float64

    samples = _real_float64(rows)
    probabilities = normalize_empirical_masses(weights)
    if (
        samples.ndim != 2
        or not samples.shape[1]
        or samples.shape[0] != len(probabilities)
        or not np.all(np.isfinite(samples))
    ):
        raise ValueError("empirical joint rows must be finite and match the mass count")
    try:
        probability_total = math.fsum(float(value) for value in probabilities)
        first_positive = int(np.flatnonzero(probabilities > 0.0)[0])

        def weighted_center(column: np.ndarray) -> tuple[float, float, float]:
            anchor = float(column[first_positive])
            terms: list[float] = []
            for probability, value in zip(probabilities, column, strict=True):
                if probability == 0.0:
                    continue
                difference = float(value) - anchor
                term = float(probability) * difference
                if not math.isfinite(term) or (difference != 0.0 and term == 0.0):
                    return _exact_weighted_center(column, probabilities, anchor)
                terms.append(term)
            offset = math.fsum(terms) / probability_total
            result = anchor + offset
            if not math.isfinite(result) or (result == 0.0 and anchor != 0.0):
                return _exact_weighted_center(column, probabilities, anchor)
            return anchor, offset, result

        centers = [weighted_center(column) for column in samples.T]
        means = np.asarray([center[2] for center in centers], dtype=np.float64)
        centered_columns: list[list[float]] = []
        for column, (anchor, offset, _) in zip(samples.T, centers, strict=True):
            deltas: list[float] = []
            for probability, value in zip(probabilities, column, strict=True):
                if probability == 0.0:
                    deltas.append(0.0)
                    continue
                delta = (float(value) - anchor) - offset
                if not math.isfinite(delta):
                    raise EmpiricalNumericResolutionError("empirical moment contribution collapsed")
                deltas.append(delta)
            centered_columns.append(deltas)
        covariance = np.empty((len(means), len(means)), dtype=np.float64)
        for left, left_terms in enumerate(centered_columns):
            for right in range(left + 1):
                cross = _weighted_cross_moment(
                    left_terms, centered_columns[right], probabilities, probability_total
                )
                covariance[left, right] = covariance[right, left] = cross
    except (OverflowError, FloatingPointError) as exc:
        raise EmpiricalNumericResolutionError("empirical moments exceed binary64") from exc
    if not np.all(np.isfinite(means)) or not np.all(np.isfinite(covariance)):
        raise EmpiricalNumericResolutionError("empirical moments exceed binary64")
    return means, covariance


def _fraction_as_finite_float(value: Fraction, *, field: str) -> float:
    try:
        result = float(value)
    except OverflowError as exc:
        raise EmpiricalNumericResolutionError(f"empirical {field} is not representable") from exc
    if not math.isfinite(result) or (value != 0 and result == 0.0):
        raise EmpiricalNumericResolutionError(f"empirical {field} is not representable")
    return result


def _exact_weighted_center(
    column: np.ndarray, probabilities: np.ndarray, anchor: float
) -> tuple[float, float, float]:
    ratios = [Fraction.from_float(float(value)) for value in probabilities]
    numerator = sum(
        (
            weight * Fraction.from_float(float(value))
            for weight, value in zip(ratios, column, strict=True)
        ),
        Fraction(),
    )
    mean = numerator / sum(ratios, Fraction())
    offset = mean - Fraction.from_float(anchor)
    return (
        anchor,
        _fraction_as_finite_float(offset, field="center offset"),
        _fraction_as_finite_float(mean, field="mean"),
    )


def _weighted_cross_moment(
    left: list[float], right: list[float], probabilities: np.ndarray, probability_total: float
) -> float:
    """Use the same scaled, weighted dot product for diagonal and cross moments."""
    left_scale = max(map(abs, left), default=0.0)
    right_scale = max(map(abs, right), default=0.0)
    if left_scale == 0.0 or right_scale == 0.0:
        return 0.0
    left_scaled = [value / left_scale for value in left]
    right_scaled = [value / right_scale for value in right]
    products = [a * b for a, b in zip(left_scaled, right_scaled, strict=True)]
    # Only exceptional support collapse uses exact rational products; ordinary
    # zero covariance stays on the bounded float/stdlib path.
    tiny_product = math.ldexp(1.0, -969)
    if any(
        (original != 0.0 and scaled == 0.0)
        for original, scaled in zip(left + right, left_scaled + right_scaled, strict=True)
    ) or any(0.0 < abs(value) < tiny_product for value in products):
        return _exact_cross_moment(left, right, probabilities)
    if any(
        a != 0.0 and b != 0.0 and product == 0.0
        for a, b, product in zip(left_scaled, right_scaled, products, strict=True)
    ):
        return _exact_cross_moment(left, right, probabilities)
    weighted_products = [
        float(weight) * product for weight, product in zip(probabilities, products, strict=True)
    ]
    if any(
        float(weight) != 0.0 and product != 0.0 and weighted == 0.0
        for weight, product, weighted in zip(
            probabilities, products, weighted_products, strict=True
        )
    ) or any(0.0 < abs(value) < tiny_product for value in weighted_products):
        return _exact_cross_moment(left, right, probabilities)
    scaled_sum = math.sumprod(probabilities, products)
    if scaled_sum == 0.0 and any(products):
        # Recover cancellation residuals from both rounded multiplications.
        product_residuals = [
            math.fma(a, b, -product)
            for a, b, product in zip(left_scaled, right_scaled, products, strict=True)
        ]
        weight_residuals = [
            math.fma(float(weight), product, -weighted)
            for weight, product, weighted in zip(
                probabilities, products, weighted_products, strict=True
            )
        ]
        weighted_residuals = [
            float(weight) * residual
            for weight, residual in zip(probabilities, product_residuals, strict=True)
        ]
        if any(
            float(weight) != 0.0 and residual != 0.0 and weighted == 0.0
            for weight, residual, weighted in zip(
                probabilities, product_residuals, weighted_residuals, strict=True
            )
        ):
            return _exact_cross_moment(left, right, probabilities)
        scaled_sum = math.fsum([*weighted_products, *weight_residuals, *weighted_residuals])
    if not math.isfinite(scaled_sum):
        return _exact_cross_moment(left, right, probabilities)
    if scaled_sum == 0.0:
        return 0.0
    scaled_sum /= probability_total
    lm, le = math.frexp(left_scale)
    rm, re = math.frexp(right_scale)
    sm, se = math.frexp(scaled_sum)
    try:
        result = math.ldexp(lm * rm * sm, le + re + se)
    except OverflowError:
        return _exact_cross_moment(left, right, probabilities)
    if result == 0.0:
        return _exact_cross_moment(left, right, probabilities)
    return result


def _exact_cross_moment(left: list[float], right: list[float], probabilities: np.ndarray) -> float:
    """Resolve exceptional support collapse using the admitted binary64 masses."""
    weights = [Fraction.from_float(float(value)) for value in probabilities]
    exact = sum(
        (
            weight * Fraction.from_float(a) * Fraction.from_float(b)
            for a, b, weight in zip(left, right, weights, strict=True)
        ),
        Fraction(),
    ) / sum(weights, Fraction())
    return _fraction_as_finite_float(exact, field="covariance")


def empirical_joint_moments(
    joint: EmpiricalJointRows, envelopes: Mapping[str, UncertaintyEnvelope]
) -> tuple[np.ndarray, np.ndarray]:
    """Recompute moments from aligned rows and reconcile any declared covariance.

    Args:
        joint: Previously admitted joint rows, with or without a sampling CDF.
        envelopes: The same named source carriers used for admission.

    Returns:
        Source-weighted mean vector and covariance in the joint coordinate order.

    Raises:
        ValueError: If moments are unrepresentable or declared covariance conflicts.
    """
    from .covariance import _real_float64, calibration_covariance_blocks_agree_v1

    first = envelopes[joint.names[0]].distribution_payload
    if not isinstance(first, PosteriorSamplesCarrier):
        raise ValueError("empirical source carrier is missing")
    weights = tuple(1.0 for _ in first.samples) if first.weights is None else first.weights
    rows = list(zip(*(joint.samples[name] for name in joint.names), strict=True))
    means, covariance = empirical_weighted_moments(rows, weights)
    has_declared = any(
        "covariance_row" in envelopes[name].metadata
        or "covariance_params" in envelopes[name].metadata
        for name in joint.names
    )
    if has_declared:
        declared_rows: list[list[float]] = []
        for name in joint.names:
            metadata = envelopes[name].metadata
            row = metadata.get("covariance_row")
            order = metadata.get("covariance_params")
            if (
                not isinstance(row, list)
                or not isinstance(order, list)
                or not all(isinstance(item, str) for item in order)
                or len(order) != len(row)
                or len(set(order)) != len(order)
                or set(order) != set(joint.names)
            ):
                raise ValueError("empirical covariance metadata has incompatible row scope")
            declared_rows.append([row[order.index(field)] for field in joint.names])
        declared = _real_float64(declared_rows)
        if not calibration_covariance_blocks_agree_v1(covariance, declared):
            raise ValueError("declared covariance disagrees with empirical rows")
    return means, covariance
