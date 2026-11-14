"""Model-declared accounting transforms for policy simulations."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any, ClassVar

import numpy as np

from polisyos.core.observability import DeterminismTier
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodPatchTargetContract,
    MethodSignature,
    ParameterSpec,
    SideEffectProfile,
    SlotSpec,
    SlotType,
    foundry_method,
)
from polisyos.foundry.methods.types.units import Units


@foundry_method(
    namespace="policy.accounting",
    version="1.0.0",
    tags={"policy", "accounting", "simulation", "period-flow"},
)
class PeriodFlowToStock:
    """Emit one period-total flow as an additive model-declared stock patch.

    The target is selected by the static ``target_slot`` parameter. The model
    and execution owners must establish that it is an eligible SUM-merged
    stock slot with the matching unit. This method does not read or infer the
    target's semantic meaning from ambient simulation state.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    side_effect_profile: ClassVar[SideEffectProfile] = SideEffectProfile.PATCH_EMISSION

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="period_flow_to_stock",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="period_flow",
                    slot_type=SlotType.SCALAR,
                    unit=Units.USD,
                    description="A currency-denominated total for one model transition period.",
                )
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    name="result",
                    slot_type=SlotType.SCALAR,
                    unit=Units.USD,
                    description="The period total emitted as the target stock's additive delta.",
                )
            }
        ),
        parameters=(
            ParameterSpec(
                name="target_slot",
                default=None,
                is_static=True,
                description="Model-declared registered stock slot receiving the additive delta.",
            ),
        ),
        patch_targets=(
            MethodPatchTargetContract(
                target_parameter="target_slot",
                source_input="period_flow",
            ),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_1,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Emit an already aggregated one-period currency flow as an additive delta "
            "to a model-declared accumulated balance."
        ),
        tags=frozenset({"policy", "accounting", "simulation", "period-flow"}),
        equations={
            "result": "period_flow",
            "stock_end": "stock_start + period_flow",
        },
        assumptions={
            "empirical_status": "not_established",
            "period_semantics": (
                "period_flow is already the total for exactly one selected model transition; "
                "the method applies no additional duration multiplier"
            ),
            "target_semantics": (
                "the model declares the target as an accumulated balance from model start; "
                "this method does not establish cash-on-hand semantics"
            ),
            "authority": "candidate arithmetic only; no publication authority",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        side_effect_profile=SideEffectProfile.PATCH_EMISSION,
        when_to_use=(
            "Apply one already materialized period-total currency flow to a model-declared "
            "accumulated balance using the model's SUM merge rule."
        ),
        when_not_to_use=(
            "Do not use for a rate that needs time integration, for a multi-period value, "
            "or to infer cash-on-hand from a fiscal balance without financing flows."
        ),
        output_interpretation=(
            "result is the one-period additive delta; the resulting stock is determined by "
            "the declared target and the execution owner's merge operation."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        """Return the selected period flow and its additive patch record.

        Args:
            state: Closed-world method input mapping containing only ``period_flow``.
            params: Method parameters containing the required static ``target_slot``.

        Returns:
            A numeric ABI result and one additive patch record for ``target_slot``.

        Raises:
            ValueError: If the selected input or target parameter is invalid.
        """
        if not isinstance(state, Mapping) or set(state) != {"period_flow"}:
            raise ValueError("period_flow_method_input_mapping_invalid")

        target_slot = params.get("target_slot")
        if type(target_slot) is not str or not target_slot or target_slot != target_slot.strip():
            raise ValueError("period_flow_target_slot_required")

        selected_value = state["period_flow"]
        if not isinstance(selected_value, (np.ndarray, np.generic)):
            raise ValueError("period_flow_requires_numpy_float64_scalar")
        value = np.asarray(selected_value)
        if value.shape != () or value.dtype != np.dtype(np.float64):
            raise ValueError("period_flow_requires_numpy_float64_scalar")

        period_total = float(value.item())
        if not math.isfinite(period_total):
            raise ValueError("period_flow_requires_finite_value")

        return {
            "result": period_total,
            "patch_records": {target_slot: [{"delta": period_total}]},
        }
