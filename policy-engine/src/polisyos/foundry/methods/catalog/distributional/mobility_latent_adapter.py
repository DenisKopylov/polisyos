"""Adapter from latent earnings mobility output to the typed mobility IR."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

import numpy as np

from polisyos.core.observability.determinism import DeterminismTier
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
from polisyos.foundry.methods.catalog._phase1_artifacts import resolve_artifact_store
from polisyos.foundry.methods.catalog.econometrics.mobility_latent import (
    build_latent_mobility_report,
)
from polisyos.ir.analytics.mobility import MobilityReport, persist_mobility_report


@foundry_method(
    namespace="distributional.mobility",
    version="1.0.0",
    tags={"distributional", "mobility", "panel", "latent-heterogeneity", "estimation"},
)
class LatentMobilityReportAdapter:
    """Convert latent-mobility tensors into a ``MobilityReport`` contract."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="latent_mobility_report_adapter",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="transition_tensor",
                    slot_type=SlotType.TENSOR,
                    unit=Unit("transition_probability", "probability"),
                    shape=("n_horizons", "n_classes", "n_classes"),
                ),
                SlotSpec(
                    name="row_marginals",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("origin_share", "probability"),
                    shape=("n_horizons", "n_classes"),
                ),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    name="result",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("result", "json"),
                    contract_id=MobilityReport.contract_id,
                ),
                SlotSpec(
                    name="mobility_report_ref",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("artifact_ref", "json"),
                ),
            }
        ),
        parameters=(ParameterSpec(name="horizon", default=5),),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Adapter that exposes latent-heterogeneous earnings mobility estimates "
            "through the standard typed MobilityReport."
        ),
        tags=frozenset({"distributional", "mobility", "panel", "estimation"}),
        when_to_use=(
            "After econometrics.panel.latent_mobility when downstream distributional "
            "pipelines expect a MobilityReport contract."
        ),
        output_interpretation=(
            "The selected h-step transition matrix is embedded as the point estimate; "
            "latent diagnostics remain in report metadata."
        ),
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(state, Mapping):
            raise TypeError("state must provide latent mobility transition tensors")

        payload = dict(state)
        if "transition_tensor" in payload:
            payload["transition_tensor"] = np.asarray(payload["transition_tensor"], dtype=float)
        if "row_marginals" in payload:
            payload["row_marginals"] = np.asarray(payload["row_marginals"], dtype=float)

        report = build_latent_mobility_report(payload, horizon=int(params.get("horizon", 5)))
        artifact_store = resolve_artifact_store(state, params)
        report_ref = (
            persist_mobility_report(artifact_store, report) if artifact_store is not None else None
        )
        return {
            "result": report,
            "mobility_report_ref": None
            if report_ref is None
            else report_ref.model_dump(mode="json"),
        }


__all__ = ["LatentMobilityReportAdapter"]
