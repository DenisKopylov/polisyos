from __future__ import annotations

from typing import Any, Mapping, Union, overload

from polisyos.ir.surface import PolicySurfaceIR
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.migrations.trinity_migration import split_to_bundle


def _looks_like_surface(payload: Mapping[str, Any]) -> bool:
    """Detect if payload is legacy PolicySurfaceIR format."""
    return "semantic" in payload or payload.get("schema_version", "").startswith("2.")


def _looks_like_trinity(payload: Mapping[str, Any]) -> bool:
    """Detect if payload is Trinity format."""
    return (
        "problem_frame" in payload
        and "policy_spec" in payload
        and "model_spec" in payload
    )


def _get_schema_version(payload: Mapping[str, Any]) -> str | None:
    """Extract schema_version from any supported format."""
    if "schema_version" in payload:
        return str(payload["schema_version"])
    if "problem_frame" in payload:
        pf = payload["problem_frame"]
        if isinstance(pf, dict) and "schema_version" in pf:
            return str(pf["schema_version"])
    return None


PolicyArtifacts = Union[PolicySurfaceIR, TrinityBundle]


@overload
def load_policy(
    payload: Any,
    *,
    as_trinity: bool = False,
    auto_migrate: bool = True,
) -> PolicySurfaceIR: ...


@overload
def load_policy(
    payload: Any,
    *,
    as_trinity: bool = True,
    auto_migrate: bool = True,
) -> TrinityBundle: ...


def load_policy(
    payload: Any,
    *,
    as_trinity: bool = False,
    auto_migrate: bool = True,
) -> PolicyArtifacts:
    """
    Unified loader that handles both legacy and Trinity formats.

    Args:
        payload: Input data (dict, PolicySurfaceIR, or TrinityBundle)
        as_trinity: If True, always return TrinityBundle (auto-migrate if needed)
        auto_migrate: If True, apply schema migrations automatically

    Returns:
        PolicySurfaceIR if as_trinity=False, TrinityBundle if as_trinity=True

    Raises:
        ValueError: If payload format is unsupported
        TypeError: If payload type is invalid
    """
    # Handle already-typed inputs
    if isinstance(payload, PolicySurfaceIR):
        if as_trinity:
            return split_to_bundle(payload)
        return payload

    if isinstance(payload, TrinityBundle):
        if as_trinity:
            return payload
        from polisyos.ir.migrations.trinity_migration import merge_to_surface_ir

        return merge_to_surface_ir(
            payload.problem_frame,
            payload.policy_spec,
            payload.model_spec,
        )

    # Handle dict/mapping payloads
    if not isinstance(payload, Mapping):
        raise TypeError(f"Unsupported policy payload type: {type(payload)}")

    # Detect format and load
    if _looks_like_trinity(payload):
        bundle = TrinityBundle.model_validate(payload)
        if as_trinity:
            return bundle
        from polisyos.ir.migrations.trinity_migration import merge_to_surface_ir

        return merge_to_surface_ir(
            bundle.problem_frame,
            bundle.policy_spec,
            bundle.model_spec,
        )

    if _looks_like_surface(payload):
        ir = PolicySurfaceIR.model_validate(payload)
        if as_trinity:
            return split_to_bundle(ir)
        return ir

    raise ValueError(
        "Unsupported policy payload: expected PolicySurfaceIR (schema_version 2.x) "
        "or TrinityBundle format."
    )


def load_trinity(payload: Any) -> TrinityBundle:
    """Convenience function to always load as Trinity format."""
    return load_policy(payload, as_trinity=True)


def load_legacy(payload: Any) -> PolicySurfaceIR:
    """Convenience function to always load as legacy format."""
    return load_policy(payload, as_trinity=False)
