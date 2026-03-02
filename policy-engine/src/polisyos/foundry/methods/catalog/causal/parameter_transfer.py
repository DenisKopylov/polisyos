from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)
from polisyos.foundry.methods.catalog.causal.protocols import ParameterTransferData


@foundry_method(
    namespace="causal.structural",
    version="1.0.0",
    tags={"causal", "structural", "parameters", "bridge"},
)
class ParameterTransfer:
    """Bridge context-adaptive parameter bundles to JAX-ready payloads."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STRICT_CPU

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="parameter_transfer",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="parameter_transfer_data",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("request", "json"),
                ),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    name="parameter_transfer_payload",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("artifact", "json"),
                ),
            }
        ),
        parameters=(),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.JAX,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Convert ContextAdaptiveParameterBundle into deterministic parameter payload "
            "for JAX structural methods."
        ),
        assumptions={
            "runtime_scope": "Bridge layer only; NumPyro runtime is out of scope for phase 15.",
            "prior_shape": (
                "Output literature_priors follows SCMFitData shape: "
                "{target: {'__intercept__': {'mean': x, 'std': y}}}"
            ),
        },
        tags=frozenset({"causal", "structural", "parameters", "bridge"}),
    )

    @staticmethod
    def pure_step(
        state: ParameterTransferData | Mapping[str, Any],
        params: Mapping[str, Any],
    ) -> dict[str, Any]:
        del params
        payload = (
            state if isinstance(state, ParameterTransferData) else ParameterTransferData.model_validate(state)
        )
        bundle = payload.parameter_bundle

        parameter_values: dict[str, float] = {}
        uncertainty_multipliers: dict[str, float] = {}
        literature_priors: dict[str, dict[str, dict[str, float]]] = {}
        warnings: list[str] = []

        for parameter_name, parameter in sorted(bundle.parameters.items()):
            if parameter.value is None:
                warnings.append(
                    f"parameter '{parameter_name}' has no scalar value and was skipped"
                )
                continue

            try:
                mean_value = float(parameter.value)
            except Exception:
                warnings.append(
                    f"parameter '{parameter_name}' value is non-numeric and was skipped"
                )
                continue

            applicability = bundle.applicability.get(parameter_name)
            multiplier = 1.0
            if applicability is not None:
                multiplier = float(applicability.uncertainty_multiplier)
            multiplier = max(1.0, multiplier)

            base_std = _estimate_std(parameter)
            std_value = max(base_std * multiplier, 1.0e-6)

            parameter_values[parameter_name] = mean_value
            uncertainty_multipliers[parameter_name] = multiplier
            literature_priors[parameter_name] = {
                "__intercept__": {"mean": mean_value, "std": std_value}
            }

        if bundle.unsupported_parameters:
            warnings.append(
                "unsupported parameters: " + ", ".join(sorted(bundle.unsupported_parameters))
            )

        return {
            "parameter_values": parameter_values,
            "uncertainty_multipliers": uncertainty_multipliers,
            "literature_priors": literature_priors,
            "unsupported_parameters": list(bundle.unsupported_parameters),
            "warnings": warnings,
            "skg_snapshot_ref": bundle.skg_snapshot_ref,
            "skg_version_id": bundle.skg_version_id,
        }


def _estimate_std(parameter: Any) -> float:
    confidence_interval = getattr(parameter, "confidence_interval", None)
    if isinstance(confidence_interval, tuple) and len(confidence_interval) == 2:
        try:
            lo = float(confidence_interval[0])
            hi = float(confidence_interval[1])
        except Exception:
            lo, hi = 0.0, 0.0
        width = max(0.0, hi - lo)
        if width > 0.0:
            # Approximate 95% CI width for normal uncertainty.
            return max(width / 3.92, 1.0e-6)

    std_error = getattr(parameter, "std_error", None)
    if std_error is not None:
        try:
            parsed = float(std_error)
        except Exception:
            parsed = 0.0
        if parsed > 0.0:
            return parsed

    mean = getattr(parameter, "value", None)
    if mean is not None:
        try:
            return max(abs(float(mean)) * 0.1, 1.0e-6)
        except Exception:
            pass
    return 0.1


__all__ = ["ParameterTransfer"]
