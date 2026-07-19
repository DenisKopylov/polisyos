"""Public compatibility facade for runtime-owned sealed OPA inputs."""

from polisyos.runtime.http.authorization import (
    CANONICAL_ROLE_AUTHORIZATION_SOURCE,
    DEPLOYMENT_SERVICE_AUTHORIZATION_SOURCE,
)
from polisyos.runtime.http.authz_middleware import (
    RuntimeActionAuthzInput,
    RuntimePrincipalAuthzInput,
)

__all__ = [
    "CANONICAL_ROLE_AUTHORIZATION_SOURCE",
    "DEPLOYMENT_SERVICE_AUTHORIZATION_SOURCE",
    "RuntimeActionAuthzInput",
    "RuntimePrincipalAuthzInput",
]
