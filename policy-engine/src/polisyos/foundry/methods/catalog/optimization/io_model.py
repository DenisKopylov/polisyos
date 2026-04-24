"""Public optimization io model module API."""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any, ClassVar

import numpy as np
from numpy.linalg import LinAlgError

from polisyos.foundry.methods.backends.protocol import SolverStatus
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)

from .protocols import IOModelResult, emit_optimization_metrics


def _to_numpy_matrix(value: Any) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if arr.ndim != 2:
        raise ValueError("technical_coefficients must be a 2D matrix")
    return arr


def _to_numpy_vector(value: Any) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if arr.ndim != 1:
        raise ValueError("final_demand must be a 1D vector")
    return arr


def _is_productive(a: np.ndarray) -> bool:
    spectral_radius = max(abs(np.linalg.eigvals(a)))
    if spectral_radius >= 1.0:
        return False
    i_minus_a = np.eye(a.shape[0]) - a
    try:
        inv = np.linalg.inv(i_minus_a)
    except LinAlgError:
        return False
    return bool(np.all(inv >= -1e-10))


def _normalize_columns_for_productivity(a_pert: np.ndarray, a_base: np.ndarray) -> np.ndarray:
    col_sums = a_pert.sum(axis=0)
    base_col_sums = a_base.sum(axis=0)
    for idx, col_sum in enumerate(col_sums):
        if col_sum < 1.0:
            continue
        cap = min(0.99, float(base_col_sums[idx]) if base_col_sums[idx] < 1.0 else 0.99)
        scale = cap / (float(col_sum) + 1e-12)
        a_pert[:, idx] *= scale
    return a_pert


@foundry_method(
    namespace="optimization.io",
    version="1.0.0",
    tags={"optimization", "input-output", "leontief"},
)
class LeontiefInputOutput:
    """Leontief inter-industry input-output model using Numpy."""

    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    required_deps: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="leontief_io",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="technical_coefficients",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("io", "coefficients"),
                    shape=("n_sectors", "n_sectors"),
                ),
                SlotSpec(
                    name="final_demand",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("demand", "value"),
                    shape=("n_sectors",),
                ),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    name="result",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("result", "json"),
                    contract_id=IOModelResult.contract_id,
                )
            }
        ),
        parameters=(
            ParameterSpec(name="strict_productivity", default=True),
            ParameterSpec(name="perturbation_pct", default=0.05),
            ParameterSpec(name="n_perturbation_samples", default=100),
            ParameterSpec(name="normalize_perturbation_columns", default=True),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Leontief model for sectoral balance and demand multipliers.",
        tags=frozenset({"optimization", "input-output", "leontief"}),
        equations={
            "system": "x = (I - A)^(-1) d",
            "multiplier": "m_j = sum_i L_ij",
        },
        when_to_use="Inter-industry economic analysis; multiplier effects of demand shocks; supply chain impact",
        when_not_to_use="No IO table available; analysis is at firm level not sector level",
        output_interpretation="Leontief multipliers: how $1 increase in final demand propagates through economy. Employment/output multipliers.",
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(state, Mapping):
            from polisyos.ir.observation.contract_compilers import LeontiefIOInput

            if isinstance(state, LeontiefIOInput):
                state = state.model_dump(mode="python")
            else:
                raise TypeError("state must be a mapping or LeontiefIOInput")

        technical_coefficients = state.get("technical_coefficients")
        final_demand = state.get("final_demand")
        sector_names_raw = state.get("sector_names")

        if technical_coefficients is None or final_demand is None:
            raise ValueError("state must include 'technical_coefficients' and 'final_demand'")

        strict_productivity = bool(params.get("strict_productivity", True))
        perturbation_pct = max(0.0, float(params.get("perturbation_pct", 0.05)))
        n_samples = max(1, int(params.get("n_perturbation_samples", 100)))
        normalize_columns = bool(params.get("normalize_perturbation_columns", True))

        started = time.perf_counter()
        result = LeontiefInputOutput._solve(
            technical_coefficients=technical_coefficients,
            final_demand=final_demand,
            sector_names=sector_names_raw,
            strict_productivity=strict_productivity,
            perturbation_pct=perturbation_pct,
            n_perturbation_samples=n_samples,
            normalize_perturbation_columns=normalize_columns,
        )
        emit_optimization_metrics(
            method="leontief_io",
            status=result.status,
            duration_seconds=max(0.0, time.perf_counter() - started),
        )
        return result.to_payload()

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> Any:
        if not isinstance(fallback_state, Mapping):
            raise TypeError("LeontiefInputOutput fallback_state must be a mapping")
        payload = dict(fallback_state)
        payload.update(bound_inputs)
        return payload

    @staticmethod
    def _solve(
        *,
        technical_coefficients: Any,
        final_demand: Any,
        sector_names: Any,
        strict_productivity: bool,
        perturbation_pct: float,
        n_perturbation_samples: int,
        normalize_perturbation_columns: bool,
    ) -> IOModelResult:
        a = _to_numpy_matrix(technical_coefficients)
        d = _to_numpy_vector(final_demand)

        n = a.shape[0]
        if a.shape[1] != n:
            raise ValueError("technical_coefficients must be square")
        if d.shape[0] != n:
            raise ValueError("final_demand length must match matrix dimension")

        if sector_names is None:
            sector_names = [f"sector_{idx}" for idx in range(n)]
        if not isinstance(sector_names, list) or len(sector_names) != n:
            raise ValueError("sector_names must be a list with same length as matrix dimension")

        productive = _is_productive(a)
        if strict_productivity and not productive:
            return IOModelResult(
                status=SolverStatus.ERROR,
                output_vector=(),
                multipliers=(),
                leontief_inverse=(),
                sector_names=tuple(str(name) for name in sector_names),
                total_output=0.0,
                direct_requirements=tuple(tuple(float(v) for v in row) for row in a.tolist()),
                is_productive=False,
                uncertainty=None,
                metadata={"error": "System is unproductive (spectral radius >= 1)"},
            )

        i_minus_a = np.eye(n) - a
        try:
            leontief_inverse = np.linalg.inv(i_minus_a)
        except LinAlgError:
            return IOModelResult(
                status=SolverStatus.ERROR,
                output_vector=(),
                multipliers=(),
                leontief_inverse=(),
                sector_names=tuple(str(name) for name in sector_names),
                total_output=0.0,
                direct_requirements=tuple(tuple(float(v) for v in row) for row in a.tolist()),
                is_productive=False,
                uncertainty=None,
                metadata={"error": "(I - A) is singular"},
            )

        output_vector = leontief_inverse @ d
        multipliers = leontief_inverse.sum(axis=0)

        uncertainty = LeontiefInputOutput._compute_uncertainty(
            a,
            d,
            baseline_total=float(output_vector.sum()),
            perturbation_pct=perturbation_pct,
            n_perturbation_samples=n_perturbation_samples,
            normalize_perturbation_columns=normalize_perturbation_columns,
        )

        return IOModelResult(
            status=SolverStatus.OPTIMAL,
            output_vector=tuple(float(v) for v in output_vector.tolist()),
            multipliers=tuple(float(v) for v in multipliers.tolist()),
            leontief_inverse=tuple(
                tuple(float(v) for v in row) for row in leontief_inverse.tolist()
            ),
            sector_names=tuple(str(name) for name in sector_names),
            total_output=float(output_vector.sum()),
            direct_requirements=tuple(tuple(float(v) for v in row) for row in a.tolist()),
            is_productive=bool(productive),
            uncertainty=uncertainty,
            metadata={
                "n_sectors": n,
                "condition_number": float(np.linalg.cond(i_minus_a)),
                "strict_productivity": strict_productivity,
            },
        )

    @staticmethod
    def _compute_uncertainty(
        a: np.ndarray,
        d: np.ndarray,
        *,
        baseline_total: float,
        perturbation_pct: float,
        n_perturbation_samples: int,
        normalize_perturbation_columns: bool,
    ) -> UncertaintyEnvelope:
        rng = np.random.default_rng(42)
        n = a.shape[0]
        totals: list[float] = []

        for _ in range(n_perturbation_samples):
            noise_a = 1.0 + rng.uniform(-perturbation_pct, perturbation_pct, size=(n, n))
            noise_d = 1.0 + rng.uniform(-perturbation_pct, perturbation_pct, size=(n,))

            a_pert = a * noise_a
            if normalize_perturbation_columns:
                a_pert = _normalize_columns_for_productivity(a_pert, a)
            d_pert = d * noise_d

            try:
                inv = np.linalg.inv(np.eye(n) - a_pert)
                x_pert = inv @ d_pert
                total = float(np.sum(x_pert))
                if np.isfinite(total):
                    totals.append(total)
            except LinAlgError:
                continue

        if not totals:
            return UncertaintyEnvelope(
                point_estimate=baseline_total,
                confidence_interval=(baseline_total, baseline_total),
                confidence_level=None,
                source=UncertaintySource.CALIBRATION,
                propagation_method=PropagationMethod.MONTE_CARLO,
                interval_semantics=IntervalSemantics.HEURISTIC_RANGE,
                is_heuristic_ci=True,
                gate_eligible=False,
                metadata={"perturbation_failed": True},
            )

        arr = np.asarray(totals, dtype=float)
        lower = float(np.percentile(arr, 2.5))
        upper = float(np.percentile(arr, 97.5))

        point = baseline_total
        lo = min(lower, upper, point)
        hi = max(lower, upper, point)

        return UncertaintyEnvelope(
            point_estimate=point,
            confidence_interval=(lo, hi),
            confidence_level=0.95,
            distribution_family=DistributionFamily.BOOTSTRAP,
            source=UncertaintySource.CALIBRATION,
            propagation_method=PropagationMethod.MONTE_CARLO,
            interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
            sample_size=len(totals),
            is_heuristic_ci=False,
            gate_eligible=True,
            metadata={
                "perturbation_pct": perturbation_pct,
                "n_samples": len(totals),
            },
        )


__all__ = ["LeontiefInputOutput"]
