"""
FaultInjector -- chaos-engineering primitives for resilience verification.

The FaultInjector wraps a connector instance and intercepts its fetch
calls, injecting configurable faults *before* the real implementation
runs. This lets tests verify that the Phase 2.9 resilience layer
(RetryPolicy, CircuitBreaker, FallbackChain) behaves correctly under
realistic failure conditions -- without touching a real API.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import pytest

from polisyos.fabric.connectors.base import (
    ConnectionConfig,
    ConnectionHandle,
    FetchRequest,
    FetchResult,
    HealthStatus,
    SourceConnector,
)

# ---------------------------------------------------------------------------
# Fault descriptors
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FaultProfile:
    """
    Specification for a single fault type and how many times to apply it.

    Attributes:
        kind:         One of "latency", "error", "disconnect".
        count:        How many consecutive calls this profile covers.
                      0 means "apply forever" (useful for permanent faults).
        latency_ms:   Delay in milliseconds (only used when kind="latency").
        status_code:  HTTP status to surface (only used when kind="error").
    """

    kind: str  # "latency" | "error" | "disconnect"
    count: int = 1
    latency_ms: int = 0
    status_code: int = 500

    def __post_init__(self) -> None:
        if self.kind not in ("latency", "error", "disconnect"):
            raise ValueError(
                f"Invalid fault kind '{self.kind}'. "
                "Must be one of: latency, error, disconnect."
            )
        if self.kind == "latency" and self.latency_ms <= 0:
            raise ValueError("latency_ms must be > 0 for kind='latency'.")
        if self.kind == "error" and self.status_code < 400:
            raise ValueError("status_code must be >= 400 for kind='error'.")


@dataclass
class FaultSequence:
    """
    Ordered list of FaultProfiles that plays back sequentially.

    Each profile consumes count calls. Once all profiles are
    exhausted, subsequent calls pass through to the real connector
    with no fault.

    count=0 means infinite repetition of the current profile.
    """

    profiles: list[FaultProfile] = field(default_factory=list)

    _profile_idx: int = field(default=0, init=False, repr=False)
    _calls_in_profile: int = field(default=0, init=False, repr=False)

    def next_fault(self) -> FaultProfile | None:
        """
        Return the active FaultProfile and advance the cursor, or None
        if the sequence is exhausted.

        A profile with count=0 repeats forever.
        """
        if self._profile_idx >= len(self.profiles):
            return None

        current = self.profiles[self._profile_idx]
        self._calls_in_profile += 1

        # count=0 means infinite repetition of this profile
        if current.count != 0 and self._calls_in_profile >= current.count:
            self._profile_idx += 1
            self._calls_in_profile = 0

        return current

    @property
    def is_exhausted(self) -> bool:
        """True once all profiles have been fully consumed."""
        return self._profile_idx >= len(self.profiles)

    def reset(self) -> None:
        """Rewind the sequence to the beginning."""
        self._profile_idx = 0
        self._calls_in_profile = 0


# ---------------------------------------------------------------------------
# HTTP-status-bearing exception (mirrors aiohttp shape)
# ---------------------------------------------------------------------------


class SimulatedHTTPError(Exception):
    """
    Exception that carries an HTTP status code.

    Phase 2.9's is_retryable_error() checks error.status to
    classify errors. This exception satisfies that contract so the
    resilience layer makes correct retry decisions under simulation.
    """

    def __init__(self, status_code: int, message: str = "") -> None:
        self.status = status_code
        self.status_code = status_code  # Some code checks status_code
        super().__init__(message or f"Simulated HTTP {status_code}")


# ---------------------------------------------------------------------------
# FaultInjector -- the wrapper
# ---------------------------------------------------------------------------


class FaultInjector:
    """
    Wraps a SourceConnector and injects faults into its fetch path.

    The injector proxies connect, disconnect, and health_check
    transparently. Only fetch is intercepted -- each call checks
    the active FaultSequence and either raises or sleeps before
    delegating to the real connector.
    """

    def __init__(
        self,
        connector: SourceConnector,
        sequence: FaultSequence | None = None,
    ) -> None:
        self._connector = connector
        self._sequence = sequence or FaultSequence()
        self._total_calls = 0
        self._faulted_calls = 0

    # ------------------------------------------------------------------
    # Pass-through methods
    # ------------------------------------------------------------------

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        return await self._connector.connect(config)

    async def disconnect(self, handle: ConnectionHandle) -> None:
        return await self._connector.disconnect(handle)

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        return await self._connector.health_check(handle)

    # ------------------------------------------------------------------
    # Fault-injected fetch
    # ------------------------------------------------------------------

    async def fetch(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> FetchResult:
        """
        Intercept fetch, apply the next fault in the sequence (if any),
        then delegate to the real connector.

        Fault application order:
            1. Check sequence for next fault profile.
            2. If fault is active: apply it (sleep / raise).
            3. If sequence is exhausted or no sequence: call real fetch.
        """
        self._total_calls += 1

        fault = self._sequence.next_fault()
        if fault is not None:
            self._faulted_calls += 1
            await self._apply_fault(fault)

        # If we reach here, either no fault or the fault was latency-only
        # (latency faults sleep but then let the real call proceed).
        return await self._connector.fetch(handle, request)

    async def _apply_fault(self, profile: FaultProfile) -> None:
        """
        Execute the fault described by profile.

        - latency    -> sleep, then return (real fetch still runs)
        - error      -> raise SimulatedHTTPError (real fetch never runs)
        - disconnect -> raise ConnectionError (real fetch never runs)
        """
        match profile.kind:
            case "latency":
                await asyncio.sleep(profile.latency_ms / 1000.0)
                # Latency is additive -- the real fetch still executes after.
            case "error":
                raise SimulatedHTTPError(profile.status_code)
            case "disconnect":
                raise ConnectionError(
                    "Simulated TCP disconnect (injected by FaultInjector)"
                )

    # ------------------------------------------------------------------
    # Convenience factory methods
    # ------------------------------------------------------------------

    @classmethod
    def with_latency(cls, connector: SourceConnector, latency_ms: int, count: int = 1) -> "FaultInjector":
        """Create an injector that adds latency to the next count fetches."""
        return cls(
            connector=connector,
            sequence=FaultSequence([
                FaultProfile(kind="latency", latency_ms=latency_ms, count=count),
            ]),
        )

    @classmethod
    def with_error(cls, connector: SourceConnector, status_code: int, count: int = 1) -> "FaultInjector":
        """Create an injector that raises HTTP errors for the next count fetches."""
        return cls(
            connector=connector,
            sequence=FaultSequence([
                FaultProfile(kind="error", status_code=status_code, count=count),
            ]),
        )

    @classmethod
    def with_disconnect(cls, connector: SourceConnector, count: int = 1) -> "FaultInjector":
        """Create an injector that drops connections for the next count fetches."""
        return cls(
            connector=connector,
            sequence=FaultSequence([
                FaultProfile(kind="disconnect", count=count),
            ]),
        )

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    @property
    def total_calls(self) -> int:
        """Total number of fetch() calls routed through the injector."""
        return self._total_calls

    @property
    def faulted_calls(self) -> int:
        """Number of fetch() calls that hit an active fault profile."""
        return self._faulted_calls

    @property
    def sequence_exhausted(self) -> bool:
        """True once all fault profiles have been consumed."""
        return self._sequence.is_exhausted

    def reset(self) -> None:
        """Rewind the fault sequence and zero call counters."""
        self._sequence.reset()
        self._total_calls = 0
        self._faulted_calls = 0


# ---------------------------------------------------------------------------
# pytest fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def fault_injector() -> FaultInjector:
    """
    Provide a bare FaultInjector with an empty sequence.

    Tests parametrise the sequence after receiving the fixture.
    """
    class _Placeholder:
        pass

    return FaultInjector(connector=_Placeholder(), sequence=FaultSequence())  # type: ignore[arg-type]
