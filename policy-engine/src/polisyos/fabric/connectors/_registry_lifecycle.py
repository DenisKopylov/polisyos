"""Lifecycle mixin for ConnectorRegistry: bootstrap, register, unregister, and wrappers."""

from __future__ import annotations

import asyncio
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Literal

from polisyos.common.logger import get_logger
from polisyos.core.observability import get_metrics

from polisyos.fabric.connectors._registry_errors import (
    ConnectorAlreadyRegisteredError,
    ConnectorConfigError,
    ConnectorNotFoundError,
)
from polisyos.fabric.connectors._registry_models import ConnectorEntry

if TYPE_CHECKING:
    from polisyos.fabric.connectors.base import (
        ConnectionConfig,
        SourceConnector,
    )
    from polisyos.fabric.connectors.contracts import ContractRegistry
    from polisyos.fabric.connectors.pool import ConnectionPool
    from polisyos.ir.connectors import ConnectorMetadataSpec

logger = get_logger(__name__)

__all__ = ["RegistryLifecycleMixin"]


class RegistryLifecycleMixin:
    """Mixin providing bootstrap, registration, unregistration, and wrapper methods."""

    # These attributes are provided by the concrete ConnectorRegistry class.
    _instance_lock: Any
    _connectors: Any
    _connection_pools: dict
    _registration_count: int
    _bootstrapped: bool
    _cache_store: Any
    _enable_caching: bool
    _cache_wrappers: dict[str, Any]
    _contract_registry: "ContractRegistry | None"
    _contract_validation_mode: Literal["strict", "warn", "disabled"]
    _contract_wrappers: dict[str, Any]
    _schema_invalidation_callback_registered: bool

    # =========================================================================
    # Configuration
    # =========================================================================

    def configure_cache(
        self,
        cache_store: Any | None,
        *,
        enable_caching: bool = True,
        reset_wrappers: bool = True,
    ) -> None:
        """Configure optional connector caching behavior."""
        with self._instance_lock:
            self._cache_store = cache_store
            self._enable_caching = enable_caching
            if reset_wrappers:
                self._cache_wrappers.clear()
            if cache_store is not None:
                self._ensure_schema_invalidation_callback()

    def configure_contracts(
        self,
        contract_registry: "ContractRegistry | None",
        *,
        validation_mode: Literal["strict", "warn", "disabled"] = "strict",
        reset_wrappers: bool = True,
    ) -> None:
        """Configure optional contract validation and schema-aware caching."""
        with self._instance_lock:
            self._contract_registry = contract_registry
            self._contract_validation_mode = validation_mode
            if reset_wrappers:
                self._contract_wrappers.clear()
                self._cache_wrappers.clear()
            self._schema_invalidation_callback_registered = False
            self._ensure_schema_invalidation_callback()

    def _bootstrap_contract_registry(self) -> None:
        try:
            from polisyos.fabric.connectors.contracts import ContractRegistry
            from polisyos.fabric.connectors.sources._contracts import ALL_SOURCE_CONTRACTS

            registry = ContractRegistry()
            for contract in ALL_SOURCE_CONTRACTS:
                registry.register(contract, allow_breaking=True)
            self._contract_registry = registry
        except Exception as exc:
            logger.debug(
                "Connector contract bootstrap skipped",
                error=str(exc),
                error_type=type(exc).__name__,
            )

    def _ensure_schema_invalidation_callback(self) -> None:
        if (
            self._schema_invalidation_callback_registered
            or self._contract_registry is None
            or self._cache_store is None
        ):
            return
        try:
            from polisyos.fabric.connectors.cache import SchemaChangeInvalidationTrigger

            trigger = SchemaChangeInvalidationTrigger(self._cache_store)
            self._contract_registry.register_callback(trigger.on_contract_registered)
            self._schema_invalidation_callback_registered = True
        except Exception as exc:
            logger.warning(
                "Failed to configure schema-aware cache invalidation callback",
                error=str(exc),
                error_type=type(exc).__name__,
            )

    # =========================================================================
    # Bootstrap
    # =========================================================================

    def _bootstrap(self) -> None:
        """
        Initialize registry with discovered connectors.

        Uses entry points for plugin discovery.
        """
        if self._bootstrapped:
            return

        from polisyos.fabric.connectors.discovery import discover_connectors

        discovered_count = 0
        error_count = 0

        for connector_class in discover_connectors():
            try:
                self.register(connector_class)
                discovered_count += 1
            except ConnectorAlreadyRegisteredError:
                # Skip duplicates during bootstrap
                pass
            except Exception as e:
                error_count += 1
                logger.warning(
                    "Failed to register connector during bootstrap",
                    connector=getattr(connector_class, "connector_id", "unknown"),
                    error=str(e),
                    error_type=type(e).__name__,
                )

        self._bootstrapped = True
        logger.info(
            "ConnectorRegistry bootstrapped",
            discovered=discovered_count,
            errors=error_count,
            total_registered=self._connectors.count,
        )

    # =========================================================================
    # Registration
    # =========================================================================

    def register(
        self,
        connector_class: type["SourceConnector"],
        config: "ConnectionConfig | None" = None,
        *,
        override: bool = False,
        factory: Callable[[], "SourceConnector"] | None = None,
    ) -> str:
        """
        Register a connector class with optional default config.

        Args:
            connector_class: Class implementing SourceConnector protocol
            config: Optional default connection configuration
            override: Allow overwriting existing registration
            factory: Optional factory for instantiating connectors (DI-friendly)

        Returns:
            Fully qualified ID of registered connector

        Raises:
            ConnectorAlreadyRegisteredError: If connector exists and override=False
            ConnectorConfigError: If provided config is invalid
        """
        from polisyos.fabric.connectors.capabilities import validate_protocol_compliance

        # Validate protocol compliance
        violations = validate_protocol_compliance(connector_class)
        if violations:
            raise ConnectorConfigError(
                connector_id=getattr(connector_class, "connector_id", "unknown"),
                reason=f"Protocol violations: {violations}",
            )

        meta: ConnectorMetadataSpec = connector_class.metadata
        fqid = meta.fully_qualified_id
        caps = connector_class.capabilities

        connector_factory = factory or (lambda cls=connector_class: cls())

        with self._instance_lock:
            if self._connectors.get(fqid) is not None and not override:
                raise ConnectorAlreadyRegisteredError(fqid)

            # Validate config if provided
            if config is not None:
                validation = connector_class.validate_config(config)
                if hasattr(validation, "valid") and not validation.valid:
                    errors = getattr(validation, "issues", [])
                    raise ConnectorConfigError(
                        connector_id=fqid,
                        reason=f"Invalid configuration: {errors}",
                    )

            entry = ConnectorEntry(
                metadata=meta,
                capabilities=caps,
                connector_class=connector_class,
                factory=connector_factory,
                default_config=config,
                loaded=False,
            )

            self._connectors.register(entry, override=override)
            self._registration_count += 1

            logger.info(
                "Registered connector",
                connector_id=fqid,
                namespace=meta.namespace,
                capabilities=caps.value if hasattr(caps, "value") else str(caps),
                trust_level=meta.trust_level.name,
                override=override,
            )

            return fqid

    def unregister(self, connector_id: str) -> bool:
        """
        Unregister a connector.

        Args:
            connector_id: Short ID or fully qualified ID

        Returns:
            True if connector was found and removed, False otherwise
        """
        try:
            fqid = self._resolve_id(connector_id)
        except ConnectorNotFoundError:
            return False

        pools_to_close: list["ConnectionPool"] = []

        with self._instance_lock:
            entry = self._connectors.unregister(fqid)
            if entry is None:
                return False

            # Close any associated connection pools
            keys_to_remove = [key for key in self._connection_pools if key[0] == fqid]
            for key in keys_to_remove:
                pools_to_close.append(self._connection_pools.pop(key))

            logger.info("Unregistered connector", connector_id=fqid)

        if pools_to_close:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    for pool in pools_to_close:
                        asyncio.create_task(pool.close_all())
                else:
                    loop.run_until_complete(
                        asyncio.gather(*(pool.close_all() for pool in pools_to_close))
                    )
            except Exception:
                pass

        return True

    # =========================================================================
    # Wrappers (resilience, contract validation, SLO metrics)
    # =========================================================================

    def _apply_resilience_if_configured(
        self,
        connector: "SourceConnector",
        entry: ConnectorEntry,
    ) -> "SourceConnector":
        """
        Apply resilience wrappers to connector fetch if configured.

        Resilience is opt-in via metadata.resilience_config or connector.resilience_config.
        """
        if getattr(connector, "_resilience_wrapped", False):
            return connector

        config = getattr(connector, "resilience_config", None)
        if config is None:
            config = entry.metadata.resilience_config

        if config is None:
            return connector

        try:
            from polisyos.fabric.connectors.resilience import apply_resilience

            connector.fetch = apply_resilience(  # type: ignore[method-assign]
                connector.fetch,
                config=config,
                cache_store=self._cache_store,
            )
            setattr(connector, "_resilience_wrapped", True)
        except Exception as exc:
            logger.warning(
                "Failed to apply resilience wrappers",
                connector_id=entry.fqid,
                error=str(exc),
                error_type=type(exc).__name__,
            )

        return connector

    def _apply_slo_metrics_wrapper(
        self,
        connector: "SourceConnector",
        *,
        connector_id: str,
    ) -> "SourceConnector":
        if getattr(connector, "_slo_request_wrapped", False):
            return connector

        metrics = get_metrics()
        original_fetch = connector.fetch

        @wraps(original_fetch)
        async def _wrapped_fetch(*args: Any, **kwargs: Any):
            try:
                result = await original_fetch(*args, **kwargs)
            except Exception:
                metrics.record_slo_connector_request("error", connector_id=connector_id)
                raise
            metrics.record_slo_connector_request("ok", connector_id=connector_id)
            return result

        try:
            connector.fetch = _wrapped_fetch  # type: ignore[method-assign]
            setattr(connector, "_slo_request_wrapped", True)
        except Exception as exc:
            logger.warning(
                "Failed to wrap connector fetch with SLO metrics",
                connector_id=connector_id,
                error=str(exc),
                error_type=type(exc).__name__,
            )
        return connector

    def _apply_contract_validation_wrapper(
        self,
        connector: "SourceConnector",
        *,
        fqid: str,
    ) -> "SourceConnector":
        if self._contract_registry is None or self._contract_validation_mode == "disabled":
            return connector
        try:
            if not self._contract_registry.get_for_connector(connector.connector_id):
                return connector
        except Exception:
            return connector

        try:
            from polisyos.fabric.connectors.contracts import ContractValidatingProxy

            with self._instance_lock:
                wrapped = self._contract_wrappers.get(fqid)
                if wrapped is None:
                    wrapped = ContractValidatingProxy(
                        connector,
                        self._contract_registry,
                        mode=self._contract_validation_mode,
                    )
                    self._contract_wrappers[fqid] = wrapped
                return wrapped
        except Exception as exc:
            logger.warning(
                "Failed to wrap connector with contract validator",
                connector_id=fqid,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return connector

    def _build_schema_hash_provider(
        self,
        *,
        connector_short_id: str,
    ) -> Callable[[Any, Any], str | None] | None:
        if self._contract_registry is None:
            return None
        try:
            from polisyos.fabric.connectors.cache import make_schema_hash_provider

            return make_schema_hash_provider(
                self._contract_registry,
                connector_id=connector_short_id,
            )
        except Exception as exc:
            logger.warning(
                "Failed to configure schema hash provider",
                connector_id=connector_short_id,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return None
