"""Injected capability-discovery composition owner for runtime HTTP."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import ValidationError

from polisyos.runtime.quality.capability_authority import CapabilityDiscoveryAuthorityResolver
from polisyos.runtime.quality.capability_discovery import (
    CapabilityDiscoveryComposer,
    CapabilityDiscoveryProvider,
    CapabilityProviderSearchResult,
    CapabilityProviderUnavailableError,
)
from polisyos.runtime.quality.capability_resolver import (
    CapabilityConformanceVerifier,
    CapabilityExecutionResolver,
    CapabilityLiveOperationRegistry,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from polisyos.core import contracts as core_contracts
    from polisyos.core.contracts import (
        CapabilityDiscoveryRequest,
        CapabilityDiscoveryResponse,
        CapabilityResourceKind,
    )
    from polisyos.runtime.http.execution_policy import RuntimeExecutionPolicyResolver
    from polisyos.runtime.quality import ProductionApprovalPacketResolver


class CapabilityDiscoveryService:
    """Own exactly one C02 composer assembled from independent injected owners."""

    def __init__(
        self,
        *,
        providers: Sequence[CapabilityDiscoveryProvider],
        operation_registry: CapabilityLiveOperationRegistry | None,
        conformance_verifier: CapabilityConformanceVerifier | None,
        policy_resolver: RuntimeExecutionPolicyResolver,
        production_approval_resolver: ProductionApprovalPacketResolver | None,
    ) -> None:
        self._composer = CapabilityDiscoveryComposer(
            providers=tuple(_ValidatedProvider(provider) for provider in providers),
            execution_resolver=CapabilityExecutionResolver(
                operation_registry=operation_registry,
                conformance_verifier=conformance_verifier,
                policy_resolver=policy_resolver,
            ),
            authority_resolver=CapabilityDiscoveryAuthorityResolver(
                production_approval_resolver=production_approval_resolver
            ),
        )

    def search(
        self,
        request: CapabilityDiscoveryRequest,
        *,
        meta: core_contracts.ApiMeta,
    ) -> CapabilityDiscoveryResponse:
        """Return C02 federation output without strengthening any posture."""
        return self._composer.search(request, meta=meta)


class _ValidatedProvider:
    """Fail malformed injected owner output into the existing typed outage arm."""

    def __init__(self, provider: CapabilityDiscoveryProvider) -> None:
        self._provider = provider

    @property
    def resource_kind(self) -> CapabilityResourceKind:
        return self._provider.resource_kind

    def search(self, request: CapabilityDiscoveryRequest) -> CapabilityProviderSearchResult:
        try:
            result = self._provider.search(request)
        except CapabilityProviderUnavailableError:
            raise
        except (AttributeError, TypeError, ValueError) as exc:
            raise CapabilityProviderUnavailableError("provider_result_invalid") from exc
        if type(result) is not CapabilityProviderSearchResult:
            raise CapabilityProviderUnavailableError("provider_result_invalid")
        try:
            validated = CapabilityProviderSearchResult.model_validate(
                result.model_dump(mode="python", round_trip=True, warnings=False)
            )
        except (AttributeError, TypeError, ValueError, ValidationError) as exc:
            raise CapabilityProviderUnavailableError("provider_result_invalid") from exc
        if (
            validated.resource_kind != self.resource_kind
            or validated.ledger.request_ref != request.search.request_id
        ):
            raise CapabilityProviderUnavailableError("provider_result_invalid")
        return validated


__all__ = ["CapabilityDiscoveryService"]
