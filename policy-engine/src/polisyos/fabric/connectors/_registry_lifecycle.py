"""Lifecycle mixin for ConnectorRegistry: bootstrap, register, unregister, and wrappers."""

from __future__ import annotations

import asyncio
import inspect
from functools import wraps
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Literal, Protocol

from polisyos.common.logger import get_logger
from polisyos.core.observability import get_metrics
from polisyos.fabric.connectors._registry_errors import (
    AmbiguousConnectorError,
    ConnectorAlreadyRegisteredError,
    ConnectorConfigError,
    ConnectorNotFoundError,
)
from polisyos.fabric.connectors._registry_models import (
    ConnectorEntry,
    _ConnectorRegistrationBinding,
)

if TYPE_CHECKING:
    from _thread import RLock as RLockType
    from collections import OrderedDict
    from collections.abc import Awaitable, Callable, Sequence
    from concurrent.futures import Future

    from polisyos.core.observability import MetricsRegistry
    from polisyos.core.registry import GenericRegistry
    from polisyos.fabric.connectors.base import (
        ConnectionConfig,
        FetchResult,
        SourceConnector,
        SourceConnectorInstance,
        SourceConnectorValue,
    )
    from polisyos.fabric.connectors.cache.store import ConnectorCacheStore
    from polisyos.fabric.connectors.contracts import (
        ConnectorSchemaContract,
        ContractRegistry,
        EvolutionReport,
        FetchResultContractValidation,
    )
    from polisyos.fabric.connectors.pool import ConnectionPool
    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry
    from polisyos.ir.connectors import ConnectorMetadataSpec

logger = get_logger(__name__)


def _wrap_fetch_with_slo_metrics[**FetchArgs, FetchResultT](
    fetch: Callable[FetchArgs, Awaitable[FetchResultT]],
    *,
    metrics: MetricsRegistry,
    connector_id: str,
) -> Callable[FetchArgs, Awaitable[FetchResultT]]:
    # Keep the owner fetch callable's complete parameter and result contract.
    @wraps(fetch)
    async def _wrapped_fetch(
        *args: FetchArgs.args,
        **kwargs: FetchArgs.kwargs,
    ) -> FetchResultT:
        try:
            result = await fetch(*args, **kwargs)
        except Exception:
            metrics.record_slo_connector_request("error", connector_id=connector_id)
            raise
        metrics.record_slo_connector_request("ok", connector_id=connector_id)
        return result

    return _wrapped_fetch


__all__ = ["RegistryLifecycleMixin"]


def _set_dynamic_attribute(target: object, name: str, value: object) -> None:
    """Set a runtime-only wrapper attribute without widening connector types."""
    setattr(target, name, value)


class _CloseablePool(Protocol):
    """Pool surface needed by registry lifecycle cleanup."""

    async def close_all(self) -> None: ...


class _StreamStartupTask(Protocol):
    """Task operations used to cancel and join an in-flight stream startup."""

    def cancel(self, msg: str | None = None) -> bool: ...

    def done(self) -> bool: ...

    def get_loop(self) -> asyncio.AbstractEventLoop: ...


class _StreamOwnerStartup(Protocol):
    """Startup ticket fields shared with the concrete registry lease record."""

    task: _StreamStartupTask
    loop: asyncio.AbstractEventLoop
    completed: Future[None]
    cleanup_started: bool


class _StreamOwnerLease(Protocol):
    """Registry-local logical owner fields needed by lifecycle cleanup."""

    fqid: str
    dataset_id: str
    partition_key: str
    pool: ConnectionPool[SourceConnectorValue[Any]] | None
    startup: _StreamOwnerStartup | None
    invalidated: bool

    @property
    def key(self) -> tuple[str, str, str]: ...


class _RegistryLifecycleState(Protocol):
    """Concrete registry state read and mutated by the lifecycle mixin."""

    _instance_lock: RLockType
    _connectors: GenericRegistry[str, ConnectorEntry]
    _registered_owner_bindings: MappingProxyType[int, _ConnectorRegistrationBinding]
    _connection_pools: OrderedDict[tuple[str, str, int], ConnectionPool[SourceConnectorValue[Any]]]
    _pending_startup_cleanup: dict[int, tuple[str, ConnectionPool[SourceConnectorValue[Any]]]]
    _stream_owner_leases: dict[tuple[str, str, str], _StreamOwnerLease]
    _stream_owner_admissions_closed: bool
    _registration_count: int
    _bootstrapped: bool
    _cache_store: ConnectorCacheStore | None
    _enable_caching: bool
    _cache_wrappers: dict[tuple[str, int], SourceConnectorInstance[Any]]
    _contract_registry: ContractRegistry | None
    _contract_validation_mode: Literal["strict", "warn", "disabled"]
    _contract_wrappers: dict[tuple[str, int], SourceConnectorInstance[Any]]
    _schema_invalidation_callback_registered: bool

    def _resolve_id(self, connector_id: str, version: str | None = None) -> str: ...

    @staticmethod
    def _has_running_loop() -> bool: ...

    def _bootstrap_builtin_connectors_direct(self) -> int: ...

    def _bootstrap_default_configs(self) -> None: ...

    async def _close_pools_async(self, pools: Sequence[_CloseablePool]) -> None: ...

    def _close_pools_sync(self, pools: Sequence[_CloseablePool]) -> None: ...

    def _invalidate_stream_startups_for_pools(
        self,
        pools: Sequence[_CloseablePool],
    ) -> list[_StreamOwnerStartup]: ...

    @staticmethod
    def _cancel_stream_startup(task: _StreamStartupTask) -> None: ...

    @staticmethod
    async def _wait_stream_startup(ticket: _StreamOwnerStartup) -> None: ...

    def _pending_connector_id_locked(self, connector_id: str) -> str | None: ...

    def _pending_pools_for_connector_locked(
        self,
        fqid: str,
    ) -> list[ConnectionPool[SourceConnectorValue[Any]]]: ...

    def _pop_registered_connector_and_pools(
        self,
        connector_id: str,
    ) -> tuple[str | None, list[ConnectionPool[SourceConnectorValue[Any]]]]: ...

    def _release_stream_owner_for_pool(self, pool: _CloseablePool) -> None: ...

    def _assert_current_registration(
        self,
        entry: ConnectorEntry,
        binding: _ConnectorRegistrationBinding,
    ) -> None: ...

    def _ensure_schema_invalidation_callback(self) -> None: ...

    def register(
        self,
        connector_class: type[SourceConnector[Any]],
        config: ConnectionConfig | None = None,
        *,
        override: bool = False,
        factory: Callable[[], SourceConnector[Any]] | None = None,
    ) -> str: ...


def _default_source_profile_registry() -> SourceProfileRegistry:
    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry

    return SourceProfileRegistry.get_instance()


def _default_metrics() -> MetricsRegistry:
    return get_metrics()


def _configure_cache_state(
    state: _RegistryLifecycleState,
    cache_store: ConnectorCacheStore | None,
    enable_caching: bool,
) -> None:
    state._cache_store = cache_store
    state._enable_caching = enable_caching


def _configure_contract_state(
    state: _RegistryLifecycleState,
    contract_registry: ContractRegistry | None,
    validation_mode: Literal["strict", "warn", "disabled"],
) -> None:
    state._contract_registry = contract_registry
    state._contract_validation_mode = validation_mode


def _set_contract_registry(
    state: _RegistryLifecycleState,
    contract_registry: ContractRegistry,
) -> None:
    state._contract_registry = contract_registry


def _set_schema_callback_registered(
    state: _RegistryLifecycleState,
    registered: bool,
) -> None:
    state._schema_invalidation_callback_registered = registered


def _set_bootstrapped(state: _RegistryLifecycleState, bootstrapped: bool) -> None:
    state._bootstrapped = bootstrapped


def _set_stream_owner_admissions_closed(
    state: _RegistryLifecycleState,
    closed: bool,
) -> None:
    state._stream_owner_admissions_closed = closed


def _increment_registration_count(state: _RegistryLifecycleState) -> None:
    state._registration_count += 1


def _invalidate_registration_wrappers_locked(
    state: _RegistryLifecycleState,
    fqid: str,
) -> None:
    """Drop every derived wrapper for one FQID while holding the registry lock."""
    for wrappers in (state._cache_wrappers, state._contract_wrappers):
        for key in tuple(wrappers):
            if key[0] == fqid:
                wrappers.pop(key, None)


class RegistryLifecycleMixin:
    """Mixin providing bootstrap, registration, unregistration, and wrapper methods."""

    # =========================================================================
    # Configuration
    # =========================================================================

    def configure_cache(
        self: _RegistryLifecycleState,
        cache_store: ConnectorCacheStore | None,
        *,
        enable_caching: bool = True,
        reset_wrappers: bool = True,
    ) -> None:
        """Configure optional connector caching behavior."""
        with self._instance_lock:
            _configure_cache_state(self, cache_store, enable_caching)
            if reset_wrappers:
                self._cache_wrappers.clear()
            if cache_store is not None:
                self._ensure_schema_invalidation_callback()

    def configure_contracts(
        self: _RegistryLifecycleState,
        contract_registry: ContractRegistry | None,
        *,
        validation_mode: Literal["strict", "warn", "disabled"] = "strict",
        reset_wrappers: bool = True,
    ) -> None:
        """Configure optional contract validation and schema-aware caching."""
        with self._instance_lock:
            _configure_contract_state(self, contract_registry, validation_mode)
            if reset_wrappers:
                self._contract_wrappers.clear()
                self._cache_wrappers.clear()
            _set_schema_callback_registered(self, False)
            self._ensure_schema_invalidation_callback()

    def _assert_current_registration(
        self: _RegistryLifecycleState,
        entry: ConnectorEntry,
        binding: _ConnectorRegistrationBinding,
    ) -> None:
        """Require the expected private origin and mutable entry view to remain current."""
        with self._instance_lock:
            current = self._registered_owner_bindings.get(id(entry))
            if (
                current is None
                or current is not binding
                or current.entry is not entry
                or self._connectors.get(entry.fqid) is not entry
            ):
                raise ConnectorConfigError(
                    connector_id=entry.fqid,
                    reason="Connector registration changed while deriving its runtime surface",
                )

            if entry.runtime_connector_id != binding.runtime_connector_id:
                detail = "runtime owner"
            elif entry.connector_class is not binding.connector_class:
                detail = "connector class"
            elif entry.factory is not binding.factory:
                detail = "factory"
            elif entry.instance is not binding.instance:
                detail = "admitted instance"
            elif entry.loaded is not (binding.instance is not None):
                detail = "loaded state"
            else:
                return

            raise ConnectorConfigError(
                connector_id=entry.fqid,
                reason=(
                    f"Connector entry {detail} differs from its registry-owned registration "
                    "binding; "
                    "re-register to replace the selected connector"
                ),
            )

    def validate_fetch_result(
        self: _RegistryLifecycleState,
        *,
        connector_id: str,
        dataset_id: str,
        result: FetchResult[Any],
    ) -> FetchResultContractValidation:
        """Validate against the current configured full contract without fetching.

        Fetch-time warn/disabled modes do not weaken this explicit admission
        check. Identity and errors come from the same resolved contract. Missing
        or changing contract custody fails closed without mutating the registry.
        """
        from polisyos.fabric.connectors.contracts import (
            ConnectorSchemaContract,
            ContractRegistry,
            ContractValidatingProxy,
            FetchResultContractValidation,
        )

        with self._instance_lock:
            registry = self._contract_registry
            if not isinstance(registry, ContractRegistry):
                return FetchResultContractValidation(
                    errors=("connector_contract_registry_not_established",)
                )
            revision = registry.revision
            selected = registry.resolve(connector_id, dataset_id)
            if selected is None:
                return FetchResultContractValidation(errors=("connector_contract_not_established",))
            contract = ConnectorSchemaContract.model_validate(selected.model_dump(mode="python"))
            errors = ContractValidatingProxy.validate_result_against_contract(result, contract)
            if registry.revision != revision:
                errors.append("connector_contract_changed_during_validation")
            return FetchResultContractValidation(
                contract_id=contract.contract_id,
                contract_version=str(contract.schema_version),
                contract_content_hash=contract.content_hash,
                errors=tuple(errors),
            )

    def resolve_schema_contract(
        self: _RegistryLifecycleState,
        *,
        connector_id: str,
        dataset_id: str,
    ) -> tuple[ConnectorSchemaContract | None, int]:
        """Resolve one immutable stream schema contract and its registry revision.

        The caller should retain this pair for the lifetime of one stream job.
        A stream must not resolve a different contract independently for each
        technical batch.
        """
        from polisyos.fabric.connectors.contracts import ContractRegistry

        with self._instance_lock:
            registry = self._contract_registry
            if not isinstance(registry, ContractRegistry):
                return None, 0
            selected = registry.resolve(connector_id, dataset_id)
            revision = registry.revision
            if selected is None:
                return None, revision
            return selected.model_copy(deep=True), revision

    def _bootstrap_contract_registry(self: _RegistryLifecycleState) -> None:
        try:
            from polisyos.fabric.connectors.sources._contracts import (
                build_builtin_contract_registry,
            )

            _set_contract_registry(self, build_builtin_contract_registry())
        except Exception as exc:
            logger.debug(
                "Connector contract bootstrap skipped",
                error=str(exc),
                error_type=type(exc).__name__,
            )

    def _ensure_schema_invalidation_callback(self: _RegistryLifecycleState) -> None:
        if (
            self._schema_invalidation_callback_registered
            or self._contract_registry is None
            or self._cache_store is None
        ):
            return
        try:
            from polisyos.fabric.connectors.cache import SchemaChangeInvalidationTrigger

            trigger = SchemaChangeInvalidationTrigger(self._cache_store)

            def invalidate_contract_cache(
                contract: ConnectorSchemaContract,
                report: EvolutionReport | None,
            ) -> None:
                trigger.on_contract_registered(contract, report)

            self._contract_registry.register_callback(invalidate_contract_cache)
            _set_schema_callback_registered(self, True)
        except Exception as exc:
            logger.warning(
                "Failed to configure schema-aware cache invalidation callback",
                error=str(exc),
                error_type=type(exc).__name__,
            )

    # =========================================================================
    # Bootstrap
    # =========================================================================

    def _bootstrap(self: _RegistryLifecycleState) -> None:
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
        from polisyos.fabric.connectors._components_bootstrap import (
            bootstrap_components_into_registry,
        )

        components_index, discovery_report = build_components_index(
            groups=[ENTRY_POINT_GROUP_FABRIC_CONNECTORS],
            include_dev_scan=True,
            include_legacy_group=False,
        )

        bridge_report = bootstrap_components_into_registry(
            components_index,
            self,
        )

        discovered_count = len(bridge_report.registered)
        error_count = len(bridge_report.errors) + len(discovery_report.errors)

        # Always reconcile direct-import builtins as a source-tree backstop.
        # This fills gaps when the installed component entry points lag behind
        # the local workspace while still allowing entry-point discovery to win.
        discovered_count += self._bootstrap_builtin_connectors_direct()

        _set_bootstrapped(self, True)
        logger.info(
            "ConnectorRegistry bootstrapped",
            discovered=discovered_count,
            duplicates=len(bridge_report.duplicates),
            errors=error_count,
            component_sources_processed=discovery_report.sources_processed,
            total_registered=self._connectors.count,
        )

        self._bootstrap_default_configs()

    def _bootstrap_builtin_connectors_direct(self: _RegistryLifecycleState) -> int:
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

    def _bootstrap_default_configs(self: _RegistryLifecycleState) -> None:
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

    def _close_pools_sync(self: _RegistryLifecycleState, pools: Sequence[_CloseablePool]) -> None:
        if not pools:
            return
        if RegistryLifecycleMixin._has_running_loop():
            raise RuntimeError(
                "ConnectorRegistry synchronous cleanup cannot close pools while an "
                "event loop is running; use unregister_async() or shutdown_async()."
            )

        async def _close_all() -> None:
            await self._close_pools_async(pools)

        asyncio.run(_close_all())

    async def _close_pools_async(
        self: _RegistryLifecycleState, pools: Sequence[_CloseablePool]
    ) -> None:
        if not pools:
            with self._instance_lock:
                if not self._pending_startup_cleanup and not self._stream_owner_leases:
                    _set_stream_owner_admissions_closed(self, False)
            return

        unique_pools: list[_CloseablePool] = []
        seen: set[int] = set()
        for pool in pools:
            pool_identity = id(pool)
            if pool_identity in seen:
                continue
            seen.add(pool_identity)
            unique_pools.append(pool)

        startup_tickets = self._invalidate_stream_startups_for_pools(unique_pools)
        current_task = asyncio.current_task()
        if any(ticket.task is current_task for ticket in startup_tickets):
            raise RuntimeError(
                "ConnectorRegistry lifecycle cannot wait for the stream startup "
                "that invoked it; the pool remains pending for a later retry."
            )

        for ticket in startup_tickets:
            if ticket.cleanup_started or ticket.task.done():
                continue
            try:
                ticket.loop.call_soon_threadsafe(self._cancel_stream_startup, ticket.task)
            except RuntimeError:
                if not ticket.task.done():
                    raise

        if startup_tickets:
            await asyncio.gather(*(self._wait_stream_startup(ticket) for ticket in startup_tickets))

        failures: list[BaseException] = []

        async def _close_one(pool: _CloseablePool) -> None:
            try:
                await pool.close_all()
            except BaseException as exc:
                failures.append(exc)
                return
            with self._instance_lock:
                pending = self._pending_startup_cleanup.get(id(pool))
                if pending is not None and pending[1] is pool:
                    self._pending_startup_cleanup.pop(id(pool), None)
                self._release_stream_owner_for_pool(pool)

        await asyncio.gather(*(_close_one(pool) for pool in unique_pools))
        if failures:
            raise failures[0]
        with self._instance_lock:
            if not self._pending_startup_cleanup and not self._stream_owner_leases:
                _set_stream_owner_admissions_closed(self, False)

    @staticmethod
    def _cancel_stream_startup(task: _StreamStartupTask) -> None:
        """Cancel a startup task on the loop that owns it."""
        if not task.done():
            task.cancel()

    @staticmethod
    async def _wait_stream_startup(ticket: _StreamOwnerStartup) -> None:
        """Wait for a ticket from any event loop without transferring cancellation."""
        wrapped = asyncio.wrap_future(ticket.completed)
        while not wrapped.done():
            try:
                await asyncio.shield(wrapped)
            except asyncio.CancelledError:
                # Teardown remains the owner until startup has stopped touching
                # the pool. The caller can retry lifecycle cleanup if cancelled.
                raise

    def _invalidate_stream_startups_for_pools(
        self: _RegistryLifecycleState,
        pools: Sequence[_CloseablePool],
    ) -> list[_StreamOwnerStartup]:
        """Invalidate owners atomically and return active startup tickets to drain."""
        pool_ids = {id(pool) for pool in pools}
        tickets: list[_StreamOwnerStartup] = []
        with self._instance_lock:
            for lease in self._stream_owner_leases.values():
                pool = lease.pool
                if pool is None or id(pool) not in pool_ids:
                    continue
                lease.invalidated = True
                if lease.startup is not None:
                    tickets.append(lease.startup)
        return tickets

    def retain_pending_startup_cleanup(
        self: _RegistryLifecycleState,
        connector_id: str,
        pool: ConnectionPool[SourceConnectorValue[Any]],
    ) -> None:
        """Retain an unresolved startup pool outside the ordinary LRU cache."""
        try:
            fqid = self._resolve_id(connector_id)
        except (ConnectorNotFoundError, AmbiguousConnectorError):
            # The connector may already be unregistering.  The supplied ID is
            # still enough to route an internal retry to this owner.
            fqid = connector_id
        with self._instance_lock:
            self._pending_startup_cleanup[id(pool)] = (fqid, pool)

    def _release_stream_owner_for_pool(self: _RegistryLifecycleState, pool: _CloseablePool) -> None:
        """Release any stream lease after this exact pool is confirmed closed."""
        with self._instance_lock:
            for key, lease in tuple(self._stream_owner_leases.items()):
                if lease.pool is pool:
                    self._stream_owner_leases.pop(key, None)
            pending = self._pending_startup_cleanup.get(id(pool))
            if pending is not None and pending[1] is pool:
                self._pending_startup_cleanup.pop(id(pool), None)

    def _pending_connector_id_locked(
        self: _RegistryLifecycleState, connector_id: str
    ) -> str | None:
        """Resolve a connector ID from retained startup owners after removal."""
        for fqid, _pool in self._pending_startup_cleanup.values():
            if fqid == connector_id:
                return fqid
            short_id = fqid.split("@", 1)[0].rsplit(".", 1)[-1]
            if connector_id in {short_id, fqid.split("@", 1)[0]}:
                return fqid
        return None

    def _pending_pools_for_connector_locked(
        self: _RegistryLifecycleState,
        fqid: str,
    ) -> list[ConnectionPool[SourceConnectorValue[Any]]]:
        """Return retained startup owners for one connector without removing them."""
        return [
            pool
            for pending_fqid, pool in self._pending_startup_cleanup.values()
            if pending_fqid == fqid
        ]

    def _pop_registered_connector_and_pools(
        self: _RegistryLifecycleState,
        connector_id: str,
    ) -> tuple[str | None, list[ConnectionPool[SourceConnectorValue[Any]]]]:
        try:
            fqid = self._resolve_id(connector_id)
        except ConnectorNotFoundError:
            return None, []

        pools_to_close: list[ConnectionPool[SourceConnectorValue[Any]]] = []

        with self._instance_lock:
            entry = self._connectors.unregister(fqid)
            if entry is None:
                return None, []

            owner_bindings = dict(self._registered_owner_bindings)
            owner_bindings.pop(id(entry), None)
            self._registered_owner_bindings = MappingProxyType(owner_bindings)

            keys_to_remove = [key for key in self._connection_pools if key[0] == fqid]
            for key in keys_to_remove:
                pool = self._connection_pools.pop(key)
                self._pending_startup_cleanup[id(pool)] = (fqid, pool)
                pools_to_close.append(pool)

            for lease in self._stream_owner_leases.values():
                if lease.fqid == fqid and lease.pool is not None:
                    lease.invalidated = True
                    self._pending_startup_cleanup[id(lease.pool)] = (fqid, lease.pool)
                    pools_to_close.append(lease.pool)

            entry.instance = None
            entry.loaded = False
            _invalidate_registration_wrappers_locked(self, fqid)
            logger.info("Unregistered connector", connector_id=fqid)

        return fqid, pools_to_close

    def register(
        self: _RegistryLifecycleState,
        connector_class: type[SourceConnector[Any]],
        config: ConnectionConfig | None = None,
        *,
        override: bool = False,
        factory: Callable[[], SourceConnector[Any]] | None = None,
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

        from polisyos.fabric.connectors.base import validate_connector_owner_id

        try:
            runtime_connector_id = validate_connector_owner_id(connector_class.connector_id)
        except (AttributeError, ValueError) as exc:
            raise ConnectorConfigError(
                connector_id=fqid,
                reason=f"Invalid runtime connector owner: {exc}",
            ) from exc

        def instantiate_registered_connector(
            cls: type[SourceConnector[Any]] = connector_class,
        ) -> SourceConnector[Any]:
            return cls()

        connector_factory: Callable[[], SourceConnector[Any]] = (
            factory or instantiate_registered_connector
        )

        with self._instance_lock:
            previous_entry = self._connectors.get(fqid)
            if previous_entry is not None and not override:
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
                runtime_connector_id=runtime_connector_id,
                default_config=config,
                loaded=False,
            )

            self._connectors.register(entry, override=override)
            _invalidate_registration_wrappers_locked(self, fqid)
            owner_bindings = dict(self._registered_owner_bindings)
            if previous_entry is not None:
                owner_bindings.pop(id(previous_entry), None)
            owner_bindings[id(entry)] = _ConnectorRegistrationBinding(
                entry=entry,
                runtime_connector_id=runtime_connector_id,
                connector_class=connector_class,
                factory=connector_factory,
                registration_generation=self._registration_count + 1,
            )
            self._registered_owner_bindings = MappingProxyType(owner_bindings)
            _increment_registration_count(self)

            logger.info(
                "Registered connector",
                connector_id=fqid,
                namespace=meta.namespace,
                capabilities=caps.value if hasattr(caps, "value") else str(caps),
                trust_level=meta.trust_level.name,
                override=override,
            )

            return fqid

    def unregister(self: _RegistryLifecycleState, connector_id: str) -> bool:
        """
        Unregister a connector.

        Args:
            connector_id: Short ID or fully qualified ID

        Returns:
            True if connector was found and removed, False otherwise
        """
        if self._has_running_loop():
            try:
                resolved_fqid = self._resolve_id(connector_id)
            except ConnectorNotFoundError:
                return False
            with self._instance_lock:
                has_pools = any(key[0] == resolved_fqid for key in self._connection_pools)
                has_pending = bool(self._pending_pools_for_connector_locked(resolved_fqid))
                has_stream_owners = any(
                    lease.fqid == resolved_fqid for lease in self._stream_owner_leases.values()
                )
            if has_pools or has_pending or has_stream_owners:
                raise RuntimeError(
                    "ConnectorRegistry.unregister() cannot close pools while an "
                    "event loop is running; use unregister_async()."
                )

        fqid, pools_to_close = self._pop_registered_connector_and_pools(connector_id)
        if fqid is None:
            with self._instance_lock:
                fqid = self._pending_connector_id_locked(connector_id)
                pools_to_close = (
                    self._pending_pools_for_connector_locked(fqid) if fqid is not None else []
                )
            if fqid is None:
                return False
        else:
            with self._instance_lock:
                pools_to_close.extend(self._pending_pools_for_connector_locked(fqid))
        self._close_pools_sync(pools_to_close)
        return True

    async def unregister_async(self: _RegistryLifecycleState, connector_id: str) -> bool:
        """Async variant of unregister that deterministically drains owned pools."""
        fqid, pools_to_close = self._pop_registered_connector_and_pools(connector_id)
        if fqid is None:
            with self._instance_lock:
                fqid = self._pending_connector_id_locked(connector_id)
                pools_to_close = (
                    self._pending_pools_for_connector_locked(fqid) if fqid is not None else []
                )
            if fqid is None:
                return False
        else:
            with self._instance_lock:
                pools_to_close.extend(self._pending_pools_for_connector_locked(fqid))
        await self._close_pools_async(pools_to_close)
        return True

    async def shutdown_async(self: _RegistryLifecycleState) -> None:
        """Unregister runtime wrappers and close all connection pools deterministically."""
        with self._instance_lock:
            _set_stream_owner_admissions_closed(self, True)
            pools_to_close = []
            for pool_key, pool in self._connection_pools.items():
                self._pending_startup_cleanup[id(pool)] = (pool_key[0], pool)
                pools_to_close.append(pool)
            for lease in self._stream_owner_leases.values():
                lease.invalidated = True
                if lease.pool is not None:
                    self._pending_startup_cleanup[id(lease.pool)] = (lease.fqid, lease.pool)
                    pools_to_close.append(lease.pool)
            self._connection_pools.clear()
            pools_to_close.extend(pool for _fqid, pool in self._pending_startup_cleanup.values())
            self._cache_wrappers.clear()
            self._contract_wrappers.clear()
            _set_schema_callback_registered(self, False)
        await self._close_pools_async(pools_to_close)

    def shutdown(self: _RegistryLifecycleState) -> None:
        """Synchronous shutdown bridge for contexts without a running event loop."""
        with self._instance_lock:
            pools_to_close = []
            for pool_key, pool in self._connection_pools.items():
                self._pending_startup_cleanup[id(pool)] = (pool_key[0], pool)
                pools_to_close.append(pool)
            for lease in self._stream_owner_leases.values():
                if lease.pool is not None:
                    self._pending_startup_cleanup[id(lease.pool)] = (lease.fqid, lease.pool)
                    pools_to_close.append(lease.pool)
            pools_to_close.extend(pool for _fqid, pool in self._pending_startup_cleanup.values())
            if pools_to_close and self._has_running_loop():
                raise RuntimeError(
                    "ConnectorRegistry.shutdown() cannot close pools while an event "
                    "loop is running; use shutdown_async()."
                )
            _set_stream_owner_admissions_closed(self, True)
            for lease in self._stream_owner_leases.values():
                lease.invalidated = True
            self._connection_pools.clear()
            self._cache_wrappers.clear()
            self._contract_wrappers.clear()
            _set_schema_callback_registered(self, False)
        self._close_pools_sync(pools_to_close)

    # =========================================================================
    # Wrappers (resilience, contract validation, SLO metrics)
    # =========================================================================

    def _apply_resilience_if_configured(
        self: _RegistryLifecycleState,
        connector: SourceConnectorValue[Any],
        entry: ConnectorEntry,
    ) -> SourceConnectorValue[Any]:
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
                _set_dynamic_attribute(
                    connector,
                    "fetch",
                    apply_resilience(
                        connector.fetch,
                        config=config,
                        cache_store=self._cache_store,
                    ),
                )
                _set_dynamic_attribute(connector, "_resilience_wrapped", True)
        except Exception as exc:
            logger.warning(
                "Failed to apply resilience wrappers",
                connector_id=entry.fqid,
                error=str(exc),
                error_type=type(exc).__name__,
            )

        return connector

    def _apply_slo_metrics_wrapper(
        self: _RegistryLifecycleState,
        connector: SourceConnectorValue[Any],
        *,
        connector_id: str,
    ) -> SourceConnectorValue[Any]:
        metrics = _default_metrics()
        try:
            with self._instance_lock:
                if getattr(connector, "_slo_request_wrapped", False):
                    return connector
                original_fetch = connector.fetch
                original_fetch_with_receipt: Callable[..., Awaitable[object]] | None = getattr(
                    connector, "fetch_with_receipt", None
                )

                _set_dynamic_attribute(
                    connector,
                    "fetch",
                    _wrap_fetch_with_slo_metrics(
                        original_fetch,
                        metrics=metrics,
                        connector_id=connector_id,
                    ),
                )
                if callable(original_fetch_with_receipt):

                    @wraps(original_fetch_with_receipt)
                    async def _wrapped_fetch_with_receipt(
                        *args: object, **kwargs: object
                    ) -> object:
                        try:
                            receipt_result = original_fetch_with_receipt(*args, **kwargs)
                            if not inspect.isawaitable(receipt_result):
                                raise TypeError("fetch_with_receipt() must return an awaitable")
                            result = await receipt_result
                        except Exception:
                            metrics.record_slo_connector_request(
                                "error",
                                connector_id=connector_id,
                            )
                            raise
                        metrics.record_slo_connector_request("ok", connector_id=connector_id)
                        return result

                    _set_dynamic_attribute(
                        connector,
                        "fetch_with_receipt",
                        _wrapped_fetch_with_receipt,
                    )
                _set_dynamic_attribute(connector, "_slo_request_wrapped", True)
        except Exception as exc:
            logger.warning(
                "Failed to wrap connector fetch with SLO metrics",
                connector_id=connector_id,
                error=str(exc),
                error_type=type(exc).__name__,
            )
        return connector

    def _apply_contract_validation_wrapper(
        self: _RegistryLifecycleState,
        connector: SourceConnectorValue[Any],
        *,
        fqid: str,
        entry: ConnectorEntry,
        binding: _ConnectorRegistrationBinding,
    ) -> SourceConnectorValue[Any]:
        self._assert_current_registration(entry, binding)
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
                self._assert_current_registration(entry, binding)
                wrapper_key = (fqid, binding.registration_generation)
                wrapped = self._contract_wrappers.get(wrapper_key)
                if wrapped is None:
                    wrapped = ContractValidatingProxy(
                        connector,
                        self._contract_registry,
                        mode=self._contract_validation_mode,
                    )
                    self._contract_wrappers[wrapper_key] = wrapped
                return wrapped
        except ConnectorConfigError:
            raise
        except Exception as exc:
            logger.warning(
                "Failed to wrap connector with contract validator",
                connector_id=fqid,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return connector

    def _build_schema_hash_provider(
        self: _RegistryLifecycleState,
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
