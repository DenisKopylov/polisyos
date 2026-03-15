from __future__ import annotations

from polisyos.foundry.methods.catalog.causal.parameter_transfer import ParameterTransfer
from polisyos.foundry.methods.catalog.causal.protocols import ParameterTransferData
from polisyos.ir.analytics.context import ContextProfile, IncomeLevel
from polisyos.ir.analytics.literature import EvidenceParameter
from polisyos.ir.analytics.parameters import ContextAdaptiveParameterBundle, ParameterApplicability
from polisyos.ir.analytics.transportability import TransportMode, TransportabilityStatus


def test_parameter_transfer_builds_bridge_payload() -> None:
    bundle = ContextAdaptiveParameterBundle(
        target_context=ContextProfile(context_id="UA", income_level=IncomeLevel.LOWER_MIDDLE),
        simulation_domain="fiscal",
        parameters={
            "fiscal_multiplier": EvidenceParameter(
                name="fiscal_multiplier",
                value=1.2,
                confidence_interval=(1.0, 1.4),
            )
        },
        applicability={
            "fiscal_multiplier": ParameterApplicability(
                parameter_id="fiscal_multiplier",
                target_context_id="UA",
                transport_status=TransportabilityStatus.IDENTIFIED,
                transport_mode=TransportMode.TRANSPORT_FORMULA,
                transport_confidence=0.6,
                context_distance=0.4,
                is_applicable=True,
                adjustment_required=True,
                uncertainty_multiplier=1.8,
                recommended_value=1.2,
            )
        },
        unsupported_parameters=["tax_elasticity"],
        skg_snapshot_ref="duckdb://mock#v42",
        skg_version_id=42,
    )

    output = ParameterTransfer.pure_step(
        ParameterTransferData(parameter_bundle=bundle),
        params={},
    )

    assert output["parameter_values"]["fiscal_multiplier"] == 1.2
    assert output["uncertainty_multipliers"]["fiscal_multiplier"] == 1.8
    assert output["literature_priors"]["fiscal_multiplier"]["__intercept__"]["mean"] == 1.2
    assert output["literature_priors"]["fiscal_multiplier"]["__intercept__"]["std"] > 0.0
    assert output["unsupported_parameters"] == ["tax_elasticity"]
    assert output["skg_version_id"] == 42
    assert output["runtime_backend_used"] in {"jax", "numpy", "numpyro"}
    assert output["runtime_ready"] is True
    assert "fiscal_multiplier" in output["runtime_parameter_intervals"]
    interval = output["runtime_parameter_intervals"]["fiscal_multiplier"]
    assert interval["ci_low"] < interval["ci_high"]
