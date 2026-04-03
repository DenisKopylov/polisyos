"""Public core security package API."""
from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS: dict[str, tuple[str, str]] = {
    "CellAssignment": ("polisyos.core.security.cell", "CellAssignment"),
    "CellResolution": ("polisyos.core.security.registry", "CellResolution"),
    "CellSpec": ("polisyos.core.security.cell", "CellSpec"),
    "CellTier": ("polisyos.core.security.cell", "CellTier"),
    "IsolationLevel": ("polisyos.core.security.cell", "IsolationLevel"),
    "TenantSpec": ("polisyos.core.security.cell", "TenantSpec"),
    "AuditActor": ("polisyos.core.security.audit_models", "AuditActor"),
    "AuditCorrelation": ("polisyos.core.security.audit_models", "AuditCorrelation"),
    "AuditEventType": ("polisyos.core.security.audit_models", "AuditEventType"),
    "AuditResource": ("polisyos.core.security.audit_models", "AuditResource"),
    "ChainedLogEntry": ("polisyos.core.security.audit_models", "ChainedLogEntry"),
    "ChainedAuditSink": ("polisyos.core.security.audit_sink", "ChainedAuditSink"),
    "LocalJsonlBackend": ("polisyos.core.security.audit_sink", "LocalJsonlBackend"),
    "HotTierBackend": ("polisyos.core.security.audit_sink", "HotTierBackend"),
    "ColdTierBackend": ("polisyos.core.security.audit_sink", "ColdTierBackend"),
    "ChainVerificationResult": (
        "polisyos.core.security.audit_verifier",
        "ChainVerificationResult",
    ),
    "ChainVerifier": ("polisyos.core.security.audit_verifier", "ChainVerifier"),
    "build_default_audit_backends_from_env": (
        "polisyos.core.security.audit_sink",
        "build_default_audit_backends_from_env",
    ),
    "AccessScope": ("polisyos.core.security.access_scope", "AccessScope"),
    "PolicyOSRole": ("polisyos.core.security.identity", "PolicyOSRole"),
    "PIIAccessLevel": ("polisyos.core.security.identity", "PIIAccessLevel"),
    "UserIdentityClaims": ("polisyos.core.security.identity", "UserIdentityClaims"),
    "ServiceIdentity": ("polisyos.core.security.identity", "ServiceIdentity"),
    "ServiceIdentityInfo": ("polisyos.core.security.identity", "ServiceIdentityInfo"),
    "SPIFFEIdentityProvider": (
        "polisyos.core.security.identity",
        "SPIFFEIdentityProvider",
    ),
    "DelegationContextClaims": (
        "polisyos.core.security.delegation",
        "DelegationContextClaims",
    ),
    "DelegationTokenManager": (
        "polisyos.core.security.delegation",
        "DelegationTokenManager",
    ),
    "AuthzDecision": ("polisyos.core.security.authz", "AuthzDecision"),
    "AuthzInput": ("polisyos.core.security.authz", "AuthzInput"),
    "AuthzResult": ("polisyos.core.security.authz", "AuthzResult"),
    "OPAClient": ("polisyos.core.security.authz", "OPAClient"),
    "DatabaseBackend": ("polisyos.core.security.db_backend", "DatabaseBackend"),
    "PostgresBackend": ("polisyos.core.security.db_backend", "PostgresBackend"),
    "DuckDBLegacyBackend": ("polisyos.core.security.db_backend", "DuckDBLegacyBackend"),
    "TenantIsolationError": (
        "polisyos.core.security.exceptions",
        "TenantIsolationError",
    ),
    "CrossTenantAccessError": (
        "polisyos.core.security.exceptions",
        "CrossTenantAccessError",
    ),
    "TenantNotFoundError": ("polisyos.core.security.exceptions", "TenantNotFoundError"),
    "CellCapacityError": ("polisyos.core.security.exceptions", "CellCapacityError"),
    "TenantContextNotSetError": (
        "polisyos.core.security.exceptions",
        "TenantContextNotSetError",
    ),
    "IdentityError": ("polisyos.core.security.exceptions", "IdentityError"),
    "IdentityNotAvailableError": (
        "polisyos.core.security.exceptions",
        "IdentityNotAvailableError",
    ),
    "IdentityVerificationError": (
        "polisyos.core.security.exceptions",
        "IdentityVerificationError",
    ),
    "TokenValidationError": (
        "polisyos.core.security.exceptions",
        "TokenValidationError",
    ),
    "MFARequiredError": ("polisyos.core.security.exceptions", "MFARequiredError"),
    "DelegationError": ("polisyos.core.security.exceptions", "DelegationError"),
    "DelegationVerificationError": (
        "polisyos.core.security.exceptions",
        "DelegationVerificationError",
    ),
    "AuthorizationError": (
        "polisyos.core.security.exceptions",
        "AuthorizationError",
    ),
    "AuthorizationDeniedError": (
        "polisyos.core.security.exceptions",
        "AuthorizationDeniedError",
    ),
    "MissingTenantHeaderError": (
        "polisyos.core.security.router",
        "MissingTenantHeaderError",
    ),
    "TenantRoutingError": ("polisyos.core.security.router", "TenantRoutingError"),
    "CellRegistry": ("polisyos.core.security.registry", "CellRegistry"),
    "TenantContext": ("polisyos.core.security.tenant_context", "TenantContext"),
    "tenant_scope": ("polisyos.core.security.tenant_context", "tenant_scope"),
    "require_tenant_context": (
        "polisyos.core.security.tenant_context",
        "require_tenant_context",
    ),
    "get_current_tenant_id": (
        "polisyos.core.security.tenant_context",
        "get_current_tenant_id",
    ),
    "get_current_tenant_id_or_none": (
        "polisyos.core.security.tenant_context",
        "get_current_tenant_id_or_none",
    ),
    "get_current_cell_id": ("polisyos.core.security.tenant_context", "get_current_cell_id"),
    "get_current_access_scope_or_none": (
        "polisyos.core.security.tenant_context",
        "get_current_access_scope_or_none",
    ),
    "set_current_access_scope": (
        "polisyos.core.security.tenant_context",
        "set_current_access_scope",
    ),
    "reset_current_access_scope": (
        "polisyos.core.security.tenant_context",
        "reset_current_access_scope",
    ),
    "TENANT_HEADER": ("polisyos.core.security.router", "TENANT_HEADER"),
    "RoutingResult": ("polisyos.core.security.router", "RoutingResult"),
    "resolve_routing": ("polisyos.core.security.router", "resolve_routing"),
    "SecuritySettings": ("polisyos.core.security.settings", "SecuritySettings"),
    "get_security_settings": (
        "polisyos.core.security.settings",
        "get_security_settings",
    ),
    "TEEPlatform": ("polisyos.core.security.tee", "TEEPlatform"),
    "AttestationStatus": ("polisyos.core.security.tee", "AttestationStatus"),
    "AttestationReport": ("polisyos.core.security.tee", "AttestationReport"),
    "AttestationPolicy": ("polisyos.core.security.tee", "AttestationPolicy"),
    "AttestationResult": ("polisyos.core.security.tee", "AttestationResult"),
    "SEVSNPVerifier": ("polisyos.core.security.tee", "SEVSNPVerifier"),
    "NoOpVerifier": ("polisyos.core.security.tee", "NoOpVerifier"),
    "TEEGatekeeper": ("polisyos.core.security.tee_middleware", "TEEGatekeeper"),
    "AttestationDeniedError": (
        "polisyos.core.security.tee_middleware",
        "AttestationDeniedError",
    ),
    "SBOMGenerator": ("polisyos.core.security.sbom", "SBOMGenerator"),
    "SBOMVerifier": ("polisyos.core.security.sbom", "SBOMVerifier"),
    "SBOMMetadata": ("polisyos.core.security.sbom", "SBOMMetadata"),
    "SBOMVerificationResult": (
        "polisyos.core.security.sbom",
        "SBOMVerificationResult",
    ),
    "VulnerabilityRecord": ("polisyos.core.security.sbom", "VulnerabilityRecord"),
    "VulnerabilitySeverity": ("polisyos.core.security.sbom", "VulnerabilitySeverity"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = target
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
