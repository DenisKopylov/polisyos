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

_FULL_FAMILIES: tuple[CausalIdentificationFamily, ...] = (
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
            supported_families=list(_FULL_FAMILIES if y0_ok else ()),
            notes=["symbolic_backend:y0"],
        ),
        CausalBackendCapability(
            backend_id=CausalBackendId.R_CAUSALEFFECT,
            available=r_ok,
            disabled_reason=None if r_ok else r_reason,
            supported_families=list(_FULL_FAMILIES if r_ok else ()),
            notes=["symbolic_backend:r_causaleffect"],
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
        CausalIdentificationFamily.BOUNDS_MANSKI,
    }
    disabled_families: dict[str, str] = {}
    symbolic_reason = _symbolic_disabled_reason(y0_ok, y0_reason, r_ok, r_reason)
    if y0_ok or r_ok:
        supported_families.update(_FULL_FAMILIES)
    else:
        for family in _FULL_FAMILIES:
            disabled_families[family.value] = symbolic_reason

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
        "degradation_policy": "full_then_bounds_explicit_simplified",
    }
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()

    notes = [
        "full_backend_order:y0,r_causaleffect,bounds_only",
        "simplified_legacy_requires_explicit_opt_in",
    ]
    if symbolic_reason:
        notes.append(f"symbolic_unavailable:{symbolic_reason}")

    return CausalCapabilityContract(
        dependency_fingerprint=fingerprint,
        full_backend_order=[
            CausalBackendId.Y0,
            CausalBackendId.R_CAUSALEFFECT,
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
                    "Resolved causal backend availability for transport/do-calculus runs."
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
                "description": "Resolved runtime support for an identification family.",
                "category": "causal",
                "enabled": enabled,
                "stage": "active",
                "disabled_reason": None if enabled else contract.disabled_families.get(family.value),
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
    reasons: list[str] = []
    if not y0_ok and y0_reason:
        reasons.append(y0_reason)
    if not r_ok and r_reason:
        reasons.append(r_reason)
    return ";".join(reasons) or "symbolic_backend_unavailable"


__all__ = [
    "build_causal_capability_contract",
    "main",
    "project_capability_features",
]
