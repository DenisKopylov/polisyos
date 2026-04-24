"""Schema-aware cache helpers."""

from __future__ import annotations

from collections.abc import Callable

from polisyos.fabric.connectors.base import FetchRequest, FetchResult
from polisyos.fabric.connectors.contracts import ContractRegistry


def make_schema_hash_provider(
    contract_registry: ContractRegistry,
    *,
    connector_id: str | None = None,
) -> Callable[[FetchRequest, FetchResult], str | None]:
    """
    Build schema_hash provider for CachingConnectorProxy.

    The hash is derived from ConnectorSchemaContract.content_hash to guarantee
    automatic cache invalidation when contracts evolve.
    """

    def provider(request: FetchRequest, result: FetchResult) -> str | None:
        resolved_connector = connector_id or _connector_from_schema_id(result.schema_id)
        if not resolved_connector:
            return None

        contract = contract_registry.resolve(resolved_connector, request.dataset_id)
        if contract is None:
            return None
        return contract.content_hash

    return provider


def _connector_from_schema_id(schema_id: str) -> str | None:
    # Conventional schema IDs are often "<connector_id>.<dataset_id>".
    # This fallback intentionally conservative to avoid false positives.
    if "." not in schema_id:
        return None
    parts = schema_id.split(".")
    if len(parts) < 2:
        return None
    return ".".join(parts[:2])
