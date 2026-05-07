"""Compatibility bridge registry for additive Fabric product integrations."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict


class FabricCompatibilityBridge(BaseModel):
    """Governed temporary bridge between Fabric-native and downstream surfaces."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    source_surface: str
    target_surface: str
    owner: str
    reason: str
    sunset_date: date
    migration_issue: str
    status: Literal["active", "sunsetting"] = "active"
    compatibility_ref: str | None = None


FABRIC_COMPATIBILITY_BRIDGES: tuple[FabricCompatibilityBridge, ...] = (
    FabricCompatibilityBridge(
        id="runtime.fabric_decision_data_v1",
        source_surface="polisyos.fabric.decision_data.FabricDecisionData",
        target_surface="/api/v1/runs/{run_id}/fabric-decision-data",
        owner="@fabric-owners",
        reason="Expose trust envelopes to Runtime while downstream clients migrate to native QuantityValue rendering.",
        sunset_date=date(2026, 9, 30),
        migration_issue="FABRIC-P10-runtime-decision-data-native",
        compatibility_ref="docs/reference/fabric/product-api-integration.md#compatibility-bridges",
    ),
    FabricCompatibilityBridge(
        id="runtime.quantity_value_compat",
        source_surface="polisyos.core.contracts.runtime.RunQuantitiesResponse",
        target_surface="frontend.runtime-dashboard.Quantity fixtures",
        owner="@runtime-owners",
        reason="Keep Design Wave 2 quantity fixtures stable while Fabric envelopes become the default source.",
        sunset_date=date(2026, 8, 31),
        migration_issue="FABRIC-P10-quantity-envelope-unification",
        compatibility_ref="docs/reference/fabric/product-api-integration.md#compatibility-bridges",
    ),
    FabricCompatibilityBridge(
        id="frontend.runtime_api_client_compat",
        source_surface="schemas/runtime_api_v1.openapi.json",
        target_surface="packages/runtime-api-client/runtimeApiClient.ts",
        owner="@runtime-owners",
        reason="Generated client remains the compatibility surface for product fixtures and additive Fabric endpoints.",
        sunset_date=date(2026, 10, 31),
        migration_issue="FABRIC-P10-generated-client-sunset-review",
        compatibility_ref="docs/reference/fabric/product-api-integration.md#compatibility-bridges",
    ),
    FabricCompatibilityBridge(
        id="scientist.fabric_trust_gate_compat",
        source_surface="FabricDecisionData trust metadata",
        target_surface="Scientist DecisionReadinessEvaluator runtime_metadata",
        owner="@scientist-owners",
        reason="Scientist can cap readiness from Fabric quality/trust metadata before all passes emit native gates.",
        sunset_date=date(2026, 9, 15),
        migration_issue="FABRIC-P10-scientist-native-trust-gate",
        compatibility_ref="docs/reference/fabric/product-api-integration.md#compatibility-bridges",
    ),
    FabricCompatibilityBridge(
        id="product.fabric_evidence_path_adapter",
        source_surface="polisyos.fabric.product_integration.FabricProductEvidencePath",
        target_surface="Scholar, Lex, and Foundry provenance adapters",
        owner="@fabric-owners",
        reason="Share one evidence-path projection until each product owns a Fabric-native contract.",
        sunset_date=date(2026, 11, 30),
        migration_issue="FABRIC-P10-product-native-evidence-paths",
        compatibility_ref="docs/reference/fabric/product-api-integration.md#compatibility-bridges",
    ),
)


def validate_fabric_compatibility_bridges(
    bridges: tuple[FabricCompatibilityBridge, ...] = FABRIC_COMPATIBILITY_BRIDGES,
) -> list[str]:
    """Return compatibility governance errors without touching runtime behavior."""
    errors: list[str] = []
    seen: set[str] = set()
    today = date(2026, 4, 28)
    for bridge in bridges:
        if bridge.id in seen:
            errors.append(f"{bridge.id}: duplicate bridge id")
        seen.add(bridge.id)
        if not bridge.owner.startswith("@"):
            errors.append(f"{bridge.id}: owner must be an explicit owner handle")
        if not bridge.reason.strip():
            errors.append(f"{bridge.id}: reason is required")
        if not bridge.migration_issue.strip():
            errors.append(f"{bridge.id}: migration issue is required")
        if bridge.sunset_date <= today:
            errors.append(f"{bridge.id}: sunset date must be in the future")
    return errors


__all__ = [
    "FABRIC_COMPATIBILITY_BRIDGES",
    "FabricCompatibilityBridge",
    "validate_fabric_compatibility_bridges",
]
