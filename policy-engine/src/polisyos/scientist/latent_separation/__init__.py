"""Compatibility shim for a Phase 5/6 decomposition module move."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = (
    "SEPARATION_DIAGNOSTICS_KEY",
    "SEPARATION_DIAGNOSTIC_INPUTS_KEY",
    "LatentSeparationDiagnosticInputs",
    "LatentSeparationEnvironmentInput",
    "LatentSeparationMeasurementInput",
    "LatentSeparationProxyInput",
    "certified_latent_separation_pairs",
    "certify_latent_separation_trust",
    "compute_latent_separation_diagnostics",
    "compute_latent_separation_diagnostics_from_inputs",
    "latent_separation_assumption_surfaces",
    "latent_separation_falsification_surfaces",
    "merge_latent_separation_diagnostics_payloads",
    "metadata_with_computed_latent_separation",
    "separation_diagnostics_payload",
)

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "LatentSeparationDiagnosticInputs": (
        "polisyos.scientist.causal.latent_separation",
        "LatentSeparationDiagnosticInputs",
    ),
    "LatentSeparationEnvironmentInput": (
        "polisyos.scientist.causal.latent_separation",
        "LatentSeparationEnvironmentInput",
    ),
    "LatentSeparationMeasurementInput": (
        "polisyos.scientist.causal.latent_separation",
        "LatentSeparationMeasurementInput",
    ),
    "LatentSeparationProxyInput": (
        "polisyos.scientist.causal.latent_separation",
        "LatentSeparationProxyInput",
    ),
    "SEPARATION_DIAGNOSTICS_KEY": (
        "polisyos.scientist.causal.latent_separation",
        "SEPARATION_DIAGNOSTICS_KEY",
    ),
    "SEPARATION_DIAGNOSTIC_INPUTS_KEY": (
        "polisyos.scientist.causal.latent_separation",
        "SEPARATION_DIAGNOSTIC_INPUTS_KEY",
    ),
    "certified_latent_separation_pairs": (
        "polisyos.scientist.causal.latent_separation",
        "certified_latent_separation_pairs",
    ),
    "certify_latent_separation_trust": (
        "polisyos.scientist.causal.latent_separation",
        "certify_latent_separation_trust",
    ),
    "compute_latent_separation_diagnostics": (
        "polisyos.scientist.causal.latent_separation",
        "compute_latent_separation_diagnostics",
    ),
    "compute_latent_separation_diagnostics_from_inputs": (
        "polisyos.scientist.causal.latent_separation",
        "compute_latent_separation_diagnostics_from_inputs",
    ),
    "latent_separation_assumption_surfaces": (
        "polisyos.scientist.causal.latent_separation",
        "latent_separation_assumption_surfaces",
    ),
    "latent_separation_falsification_surfaces": (
        "polisyos.scientist.causal.latent_separation",
        "latent_separation_falsification_surfaces",
    ),
    "merge_latent_separation_diagnostics_payloads": (
        "polisyos.scientist.causal.latent_separation",
        "merge_latent_separation_diagnostics_payloads",
    ),
    "metadata_with_computed_latent_separation": (
        "polisyos.scientist.causal.latent_separation",
        "metadata_with_computed_latent_separation",
    ),
    "separation_diagnostics_payload": (
        "polisyos.scientist.causal.latent_separation",
        "separation_diagnostics_payload",
    ),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(
            f"module 'polisyos.scientist.latent_separation' has no attribute {name!r}"
        )
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
