"""Public causal capabilities module API."""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from importlib import util as importlib_util

from polisyos.ir.analytics.causal_capabilities import (
    CausalBackendCapability,
    CausalBackendId,
    CausalCapabilityContract,
    CausalIdentificationFamily,
)

from .full_transport_bridge import probe_backend_availability

_UNSUPPORTED_FAMILIES: tuple[CausalIdentificationFamily, ...] = (
    CausalIdentificationFamily.FRONTDOOR,
    CausalIdentificationFamily.DO_CALCULUS_RULE2,
    CausalIdentificationFamily.DO_CALCULUS_RULE3,
    CausalIdentificationFamily.C_COMPONENT_FACTORIZATION,
)


def build_causal_capability_contract() -> CausalCapabilityContract:
    """Build causal capability contract."""
    y0_ok, y0_reason = probe_backend_availability("y0")
    r_ok, r_reason = probe_backend_availability("r")

    backends = [
        CausalBackendCapability(
            backend_id=CausalBackendId.Y0,
            available=y0_ok,
            disabled_reason=None if y0_ok else y0_reason,
            supported_families=(
                [CausalIdentificationFamily.DIRECT, CausalIdentificationFamily.TRSO]
                if y0_ok
                else []
            ),
            notes=[
                "operation_api_available:y0_direct_id_and_trso",
                "direct_id and trso operations; trso requires explicit population profile",
                "availability does not establish per-query identification or evidence authority",
            ],
        ),
        CausalBackendCapability(
            backend_id=CausalBackendId.R_CAUSALEFFECT,
            available=r_ok,
            disabled_reason=None if r_ok else r_reason,
            supported_families=[],
            notes=["r_causaleffect_execution_adapter_not_implemented"],
        ),
        CausalBackendCapability(
            backend_id=CausalBackendId.BOUNDS_ONLY,
            available=True,
            supported_families=[CausalIdentificationFamily.BOUNDS_MANSKI],
            notes=["fallback:manski_bounds"],
        ),
        CausalBackendCapability(
            backend_id=CausalBackendId.SIMPLIFIED_LEGACY,
            available=True,
            supported_families=[CausalIdentificationFamily.DIRECT],
            notes=["legacy_only:explicit_opt_in"],
        ),
    ]

    supported_families = {
        CausalIdentificationFamily.DIRECT,
        CausalIdentificationFamily.TRSO,
        CausalIdentificationFamily.BOUNDS_MANSKI,
    }
    disabled_families: dict[str, str] = {}
    symbolic_reason = _symbolic_disabled_reason(y0_ok, y0_reason, r_ok, r_reason)
    for family in _UNSUPPORTED_FAMILIES:
        disabled_families[family.value] = "symbolic_family_execution_not_established"

    payload = {
        "python": platform.python_version(),
        "platform": sys.platform,
        "modules": {
            "y0": importlib_util.find_spec("y0") is not None,
            "rpy2": importlib_util.find_spec("rpy2") is not None,
            "dowhy": importlib_util.find_spec("dowhy") is not None,
            "econml": importlib_util.find_spec("econml") is not None,
        },
        "probes": {
            "y0": {"available": y0_ok, "reason": y0_reason},
            "r_causaleffect": {"available": r_ok, "reason": r_reason},
        },
        "degradation_policy": "direct_id_then_bounds_explicit_simplified",
        "family_claim_policy": "per_family_execution_evidence_required",
    }
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
            "utf-8"
        )
    ).hexdigest()

    notes = [
        "backend_availability_is_not_family_support",
        "y0_direct_id_operation_available_when_api_probe_passes",
        "y0_trso_requires_explicit_consumer_profile; source-data authority not established",
        "r_causaleffect_execution_adapter_not_implemented",
        "simplified_legacy_requires_explicit_opt_in",
    ]
    if symbolic_reason:
        notes.append(f"symbolic_unavailable:{symbolic_reason}")

    return CausalCapabilityContract(
        dependency_fingerprint=fingerprint,
        full_backend_order=[
            CausalBackendId.Y0,
            CausalBackendId.BOUNDS_ONLY,
        ],
        degradation_policy="full_then_bounds_explicit_simplified",
        backends=backends,
        supported_families=sorted(supported_families, key=lambda item: item.value),
        disabled_families=disabled_families,
        notes=notes,
    )


def project_capability_features(contract: CausalCapabilityContract) -> list[dict[str, object]]:
    """Project capability features helper."""
    features: list[dict[str, object]] = []
    for backend in contract.backends:
        features.append(
            {
                "key": f"causal_backend_{backend.backend_id.value}",
                "label": f"Causal backend: {backend.backend_id.value}",
                "description": (
                    "Backend import/API probe outcome; not per-query identification or evidence authority."
                ),
                "category": "causal",
                "enabled": backend.available,
                "stage": "active",
                "disabled_reason": backend.disabled_reason,
            }
        )
    for family in sorted(CausalIdentificationFamily, key=lambda item: item.value):
        enabled = contract.supports_family(family)
        features.append(
            {
                "key": f"causal_family_{family.value}",
                "label": f"Causal family: {family.value}",
                "description": "Identification-family support backed by an established executable family path.",
                "category": "causal",
                "enabled": enabled,
                "stage": "active",
                "disabled_reason": None
                if enabled
                else contract.disabled_families.get(family.value),
            }
        )
    return features


def main() -> int:
    """Main helper."""
    contract = build_causal_capability_contract()
    sys.stdout.write(json.dumps(contract.model_dump(mode="json"), indent=2, sort_keys=True) + "\n")
    return 0


def _symbolic_disabled_reason(
    y0_ok: bool,
    y0_reason: str | None,
    r_ok: bool,
    r_reason: str | None,
) -> str:
    del y0_ok, y0_reason, r_ok, r_reason
    return "symbolic_family_execution_not_established"


__all__ = [
    "build_causal_capability_contract",
    "main",
    "project_capability_features",
]
