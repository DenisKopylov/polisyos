"""Security exception hierarchy for tenant isolation and Zero Trust authn/authz."""

from polisyos.core.errors import ErrorCategory, PolicyOSError


class TenantIsolationError(PolicyOSError):
    """Base exception for tenant-isolation failures."""

    default_stage = "core.security"
    default_category = ErrorCategory.FATAL


class CrossTenantAccessError(TenantIsolationError):
    """Raised when access crosses tenant boundary."""

    def __init__(self, requesting_tenant: str, target_tenant: str, resource: str = "") -> None:
        self.requesting_tenant = requesting_tenant
        self.target_tenant = target_tenant
        self.resource = resource
        suffix = f" (resource={resource})" if resource else ""
        message = (
            f"Cross-tenant access denied: tenant={requesting_tenant} "
            f"attempted to access tenant={target_tenant}{suffix}"
        )
        super().__init__(message)


class TenantNotFoundError(TenantIsolationError):
    """Raised when tenant cannot be resolved in registry."""

    default_category = ErrorCategory.VALIDATION


class CellCapacityError(TenantIsolationError):
    """Raised when shared cell reached tenant capacity."""

    default_category = ErrorCategory.TRANSIENT


class TenantContextNotSetError(TenantIsolationError):
    """Raised when tenant-scoped operation runs without active context."""

    default_category = ErrorCategory.VALIDATION


class IdentityError(TenantIsolationError):
    """Base exception for identity operations."""

    default_stage = "core.security.identity"


class IdentityNotAvailableError(IdentityError):
    """Raised when service identity provider is unavailable."""

    default_category = ErrorCategory.TRANSIENT


class IdentityVerificationError(IdentityError):
    """Raised when service identity verification fails."""

    default_category = ErrorCategory.FATAL


class TokenValidationError(IdentityError):
    """Raised when JWT token validation fails."""

    default_category = ErrorCategory.VALIDATION


class MFARequiredError(TokenValidationError):
    """Raised when MFA is required but not present in token claims."""


class DelegationError(TenantIsolationError):
    """Base exception for delegation-token handling."""

    default_stage = "core.security.delegation"


class DelegationVerificationError(DelegationError):
    """Raised when delegation token cannot be verified."""

    default_category = ErrorCategory.VALIDATION


class AuthorizationError(TenantIsolationError):
    """Base exception for authorization checks."""

    default_stage = "core.security.authorization"


class AuthorizationDeniedError(AuthorizationError):
    """Raised when authorization policy denies access."""

    default_category = ErrorCategory.VALIDATION
