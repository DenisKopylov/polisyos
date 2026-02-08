"""Security exception hierarchy for tenant isolation and Zero Trust authn/authz."""


class TenantIsolationError(Exception):
    """Base exception for tenant-isolation failures."""


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


class CellCapacityError(TenantIsolationError):
    """Raised when shared cell reached tenant capacity."""


class TenantContextNotSetError(TenantIsolationError):
    """Raised when tenant-scoped operation runs without active context."""


class IdentityError(TenantIsolationError):
    """Base exception for identity operations."""


class IdentityNotAvailableError(IdentityError):
    """Raised when service identity provider is unavailable."""


class IdentityVerificationError(IdentityError):
    """Raised when service identity verification fails."""


class TokenValidationError(IdentityError):
    """Raised when JWT token validation fails."""


class MFARequiredError(TokenValidationError):
    """Raised when MFA is required but not present in token claims."""


class DelegationError(TenantIsolationError):
    """Base exception for delegation-token handling."""


class DelegationVerificationError(DelegationError):
    """Raised when delegation token cannot be verified."""


class AuthorizationError(TenantIsolationError):
    """Base exception for authorization checks."""


class AuthorizationDeniedError(AuthorizationError):
    """Raised when authorization policy denies access."""
