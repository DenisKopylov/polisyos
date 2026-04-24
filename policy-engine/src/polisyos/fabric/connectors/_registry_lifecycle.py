"""Lifecycle mixin for ConnectorRegistry: bootstrap, register, unregister, and wrappers."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Any, Literal

from polisyos.common.logger import get_logger
from polisyos.core.observability import get_metrics
from polisyos.fabric.connectors._registry_errors import (
    ConnectorAlreadyRegisteredError,
    ConnectorConfigError,
    ConnectorNotFoundError,
)
from polisyos.fabric.connectors._registry_models import ConnectorEntry

if TYPE_CHECKING:
    from polisyos.core.observability import MetricsRegistry
    from polisyos.fabric.connectors.base import (
        ConnectionConfig,
        SourceConnector,
    )
    from polisyos.fabric.connectors.contracts import ContractRegistry
    from polisyos.fabric.connectors.pool import ConnectionPool
    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry
    from polisyos.ir.connectors import ConnectorMetadataSpec

logger = get_logger(__name__)

__all__ = ["RegistryLifecycleMixin"]


def _default_source_profile_registry() -> SourceProfileRegistry:
    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry

    return SourceProfileRegistry.get_instance()


def _default_metrics() -> MetricsRegistry:
    return get_metrics()


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
    _contract_registry: ContractRegistry | None
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
        contract_registry: ContractRegistry | None,
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
            from polisyos.fabric.connectors.sources._contracts import (
                build_builtin_contract_registry,
            )

            self._contract_registry = build_builtin_contract_registry()
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

        Uses component discovery + component bridge as canonical bootstrap path,
        with a direct-import fallback when the package is not pip-installed
        (entry points unavailable and dev-scan cannot resolve relative imports).
        """
        if self._bootstrapped:
            return

        from polisyos.core.components import ENTRY_POINT_GROUP_FABRIC_CONNECTORS
        from polisyos.core.components.bootstrap import build_components_index
        from polisyos.fabric.connectors.components_bridge import (
            bootstrap_connector_registry_from_components,
        )

        components_index, discovery_report = build_components_index(
            groups=[ENTRY_POINT_GROUP_FABRIC_CONNECTORS],
            include_dev_scan=True,
            include_legacy_group=False,
        )

        bridge_report = bootstrap_connector_registry_from_components(
            components_index,
            self,
        )

        discovered_count = len(bridge_report.registered)
        error_count = len(bridge_report.errors) + len(discovery_report.errors)

        # Always reconcile direct-import builtins as a source-tree backstop.
        # This fills gaps when the installed component entry points lag behind
        # the local workspace while still allowing entry-point discovery to win.
        discovered_count += self._bootstrap_builtin_connectors_direct()

        self._bootstrapped = True
        logger.info(
            "ConnectorRegistry bootstrapped",
            discovered=discovered_count,
            duplicates=len(bridge_report.duplicates),
            errors=error_count,
            component_sources_processed=discovery_report.sources_processed,
            total_registered=self._connectors.count,
        )

        self._bootstrap_default_configs()

    def _bootstrap_builtin_connectors_direct(self) -> int:
        """Direct-import fallback for registering builtin connectors.

        Used when the component discovery system finds no connectors
        (typical for source-tree runs without ``pip install -e``).
        """
        registered = 0
        try:
            from polisyos.fabric.connectors.components import __polisyos_components__

            for component in __polisyos_components__:
                connector_class = component.create()
                fqid = getattr(
                    getattr(connector_class, "metadata", None),
                    "fully_qualified_id",
                    None,
                )
                if fqid is None:
                    continue
                try:
                    self.register(connector_class, override=False)
                    registered += 1
                except Exception as exc:
                    logger.debug("Ignored exception: %s", exc)  # duplicate or validation — skip
        except Exception as exc:
            logger.debug(
                "Direct connector bootstrap fallback failed",
                error=str(exc),
                error_type=type(exc).__name__,
            )
        return registered

    def _bootstrap_default_configs(self) -> None:
        """Wire SourceProfile defaults to matching connector entries.

        For each registered profile whose ``connector_family`` matches a
        connector namespace, resolve the profile to a ``ConnectionConfig``
        and set it as the entry's ``default_config`` (first match wins —
        a connector that already has a default is not overwritten).
        """
        try:
            from polisyos.fabric.connectors.profiles.resolver import resolve_connection_config

            profile_registry = _default_source_profile_registry()
            wired = 0
            for profile in profile_registry.list_all():
                namespace_entries = list(
                    self._connectors.find("namespace", profile.connector_family)
                )
                for entry in namespace_entries:
                    if entry.default_config is None:
                        entry.default_config = resolve_connection_config(profile)
                        wired += 1
                        logger.debug(
                            "Wired profile default config",
                            profile_id=profile.profile_id,
                            connector_id=entry.fqid,
                        )
            if wired:
                logger.info(
                    "Default configs bootstrapped from profiles",
                    wired=wired,
                )
        except Exception as exc:
            logger.debug(
                "Default config bootstrap from profiles skipped",
                error=str(exc),
                error_type=type(exc).__name__,
            )

    # =========================================================================
    # Registration
    # =========================================================================

    @staticmethod
    def _has_running_loop() -> bool:
        try:
            asyncio.get_running_loop()
            return True
        except RuntimeError:
            return False

    @staticmethod
    def _close_pools_sync(pools: list[ConnectionPool]) -> None:
        if not pools:
            return
        if RegistryLifecycleMixin._has_running_loop():
            raise RuntimeError(
                "ConnectorRegistry synchronous cleanup cannot close pools while an "
                "event loop is running; use unregister_async() or shutdown_async()."
            )

        async def _close_all() -> None:
            await asyncio.gather(*(pool.close_all() for pool in pools))

        asyncio.run(_close_all())

    async def _close_pools_async(self, pools: list[ConnectionPool]) -> None:
        if not pools:
            return
        await asyncio.gather(*(pool.close_all() for pool in pools))

    def _pop_registered_connector_and_pools(
        self,
        connector_id: str,
    ) -> tuple[str | None, list[ConnectionPool]]:
        try:
            fqid = self._resolve_id(connector_id)
        except ConnectorNotFoundError:
            return None, []

        pools_to_close: list[ConnectionPool] = []

        with self._instance_lock:
            entry = self._connectors.unregister(fqid)
            if entry is None:
                return None, []

            keys_to_remove = [key for key in self._connection_pools if key[0] == fqid]
            for key in keys_to_remove:
                pools_to_close.append(self._connection_pools.pop(key))

            entry.instance = None
            entry.loaded = False
            self._cache_wrappers.pop(fqid, None)
            self._contract_wrappers.pop(fqid, None)
            logger.info("Unregistered connector", connector_id=fqid)

        return fqid, pools_to_close

    def register(
        self,
        connector_class: type[SourceConnector],
        config: ConnectionConfig | None = None,
        *,
        override: bool = False,
        factory: Callable[[], SourceConnector] | None = None,
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
                from polisyos.fabric.connectors.types import ValidationResult

                if not isinstance(validation, ValidationResult):
                    raise ConnectorConfigError(
                        connector_id=fqid,
                        reason=(
                            "validate_config() must return ValidationResult, "
                            f"got {type(validation).__name__}"
                        ),
                    )
                if not validation.valid:
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
        if self._has_running_loop():
            try:
                fqid = self._resolve_id(connector_id)
            except ConnectorNotFoundError:
                return False
            with self._instance_lock:
                has_pools = any(key[0] == fqid for key in self._connection_pools)
            if has_pools:
                raise RuntimeError(
                    "ConnectorRegistry.unregister() cannot close pools while an "
                    "event loop is running; use unregister_async()."
                )

        fqid, pools_to_close = self._pop_registered_connector_and_pools(connector_id)
        if fqid is None:
            return False
        self._close_pools_sync(pools_to_close)
        return True

    async def unregister_async(self, connector_id: str) -> bool:
        """Async variant of unregister that deterministically drains owned pools."""
        fqid, pools_to_close = self._pop_registered_connector_and_pools(connector_id)
        if fqid is None:
            return False
        await self._close_pools_async(pools_to_close)
        return True

    async def shutdown_async(self) -> None:
        """Unregister runtime wrappers and close all connection pools deterministically."""
        with self._instance_lock:
            pools_to_close = list(self._connection_pools.values())
            self._connection_pools.clear()
            self._cache_wrappers.clear()
            self._contract_wrappers.clear()
            self._schema_invalidation_callback_registered = False
        await self._close_pools_async(pools_to_close)

    def shutdown(self) -> None:
        """Synchronous shutdown bridge for contexts without a running event loop."""
        with self._instance_lock:
            pools_to_close = list(self._connection_pools.values())
            if pools_to_close and self._has_running_loop():
                raise RuntimeError(
                    "ConnectorRegistry.shutdown() cannot close pools while an event "
                    "loop is running; use shutdown_async()."
                )
            self._connection_pools.clear()
            self._cache_wrappers.clear()
            self._contract_wrappers.clear()
            self._schema_invalidation_callback_registered = False
        self._close_pools_sync(pools_to_close)

    # =========================================================================
    # Wrappers (resilience, contract validation, SLO metrics)
    # =========================================================================

    def _apply_resilience_if_configured(
        self,
        connector: SourceConnector,
        entry: ConnectorEntry,
    ) -> SourceConnector:
        """
        Apply resilience wrappers to connector fetch if configured.

        Resilience is opt-in via metadata.resilience_config or connector.resilience_config.
        """
        config = getattr(connector, "resilience_config", None)
        if config is None:
            config = entry.metadata.resilience_config

        if config is None:
            return connector

        try:
            from polisyos.fabric.connectors.resilience import apply_resilience

            with self._instance_lock:
                if getattr(connector, "_resilience_wrapped", False):
                    return connector
                connector.fetch = apply_resilience(  # type: ignore[method-assign]
                    connector.fetch,
                    config=config,
                    cache_store=self._cache_store,
                )
                connector._resilience_wrapped = True
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
        connector: SourceConnector,
        *,
        connector_id: str,
    ) -> SourceConnector:
        metrics = _default_metrics()
        try:
            with self._instance_lock:
                if getattr(connector, "_slo_request_wrapped", False):
                    return connector
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

                connector.fetch = _wrapped_fetch  # type: ignore[method-assign]
                connector._slo_request_wrapped = True
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
        connector: SourceConnector,
        *,
        fqid: str,
    ) -> SourceConnector:
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
