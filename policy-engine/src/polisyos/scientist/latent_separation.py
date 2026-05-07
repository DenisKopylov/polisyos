"""Compatibility shim for `polisyos.scientist.latent_separation`.

Canonical module: `polisyos.scientist.methods.causal.latent_separation`.
Sunset: 2026-12-31.
"""

from __future__ import annotations

from polisyos.scientist._internal.shims import install_lazy_module_shim

install_lazy_module_shim(
    globals(),
    legacy_module=__name__,
    canonical_module="polisyos.scientist.methods.causal.latent_separation",
    public_names=(
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
    ),
    sunset_date="2026-12-31",
    migration_hint="Use polisyos.scientist.methods.causal.latent_separation for new imports.",
)
