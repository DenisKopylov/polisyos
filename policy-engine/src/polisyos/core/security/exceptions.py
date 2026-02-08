"""Security exception hierarchy for tenant isolation."""


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
