"""Exercise LA-057 consumers from an actual isolated installed project wheel.

The caller supplies the frozen wheel, source Git identity and isolated site path.
Run with Python ``-I``, no checkout PYTHONPATH, and pytest ``--noconftest``.
Missing wheel-profile inputs are errors, never an implicit source-checkout pass.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import importlib.metadata
import json
import os
import subprocess
import sys
import typing
import zipfile
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from pathlib import Path
from types import ModuleType

import pytest


def _required_path(name: str) -> Path:
    value = os.environ.get(name)
    assert value, f"explicit installed-wheel input missing: {name}"
    return Path(value).resolve(strict=True)


@pytest.fixture(scope="module")
def installed_bridge() -> ModuleType:
    """Bind the actual imported wheel members to the frozen canonical source."""
    wheel = _required_path("E02_LA057_WHEEL_PATH")
    site = _required_path("E02_LA057_INSTALLED_SITE")
    source_root = _required_path("E02_LA057_SOURCE_ROOT")
    source_sha = os.environ.get("E02_LA057_SOURCE_SHA")
    test_sha256 = os.environ.get("E02_LA057_TEST_SHA256")
    assert source_sha and test_sha256, "source and native-input identities must be explicit"
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == test_sha256
    assert sys.version_info[:2] == (3, 14), "the declared supported project profile is Python3.14"
    assert sys.flags.isolated == 1, "launcher must use Python -I"
    assert not os.environ.get("PYTHONPATH"), "checkout PYTHONPATH is not an installed-wheel profile"
    assert source_root.name == "policy-engine"
    assert site.is_relative_to(Path(sys.prefix).resolve())
    assert not any(
        Path(entry).resolve().is_relative_to(source_root / "src") for entry in sys.path if entry
    )
    distribution = importlib.metadata.distribution("policy-engine")
    bindings = []
    with zipfile.ZipFile(wheel) as archive:
        for module_name, member in (
            ("polisyos", "polisyos/__init__.py"),
            ("polisyos.common", "polisyos/common/__init__.py"),
            ("polisyos.common.async_tools", "polisyos/common/async_tools.py"),
        ):
            module = importlib.import_module(module_name)
            assert module.__file__ is not None
            actual = Path(module.__file__).resolve(strict=True)
            assert actual == site / member, f"wheel consumer imported a foreign origin: {actual}"
            tracked_path = "policy-engine/src/" + member
            frozen = subprocess.check_output(
                ["git", "show", f"{source_sha}:{tracked_path}"],
                cwd=source_root.parent,
            )
            assert (source_root / "src" / member).read_bytes() == frozen
            assert archive.read(member) == frozen == actual.read_bytes()
            assert Path(distribution.locate_file(member)).resolve() == actual
            bindings.append(
                {
                    "module": module_name,
                    "origin": str(actual),
                    "wheel_member": member,
                    "sha256": hashlib.sha256(frozen).hexdigest(),
                }
            )
        metadata_member = next(
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        )
        assert distribution.read_text("METADATA") == archive.read(metadata_member).decode()
    print(
        json.dumps(
            {
                "observation": "installed-wheel-source-identity",
                "source_sha": source_sha,
                "python": sys.executable,
                "python_version": sys.version,
                "installed_site": str(site),
                "wheel": str(wheel),
                "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
                "distribution_version": distribution.version,
                "test_sha256": test_sha256,
                "modules": bindings,
            },
            sort_keys=True,
        )
    )
    return importlib.import_module("polisyos.common.async_tools")


@pytest.mark.parametrize("consumer", ["direct", "alias", "facade", "star_reflection"])
def test_installed_generic_identities(installed_bridge: ModuleType, consumer: str) -> None:
    """Resolve the four genuine function-local parameters through real consumers."""
    from polisyos.common import async_tools as facade_alias
    from polisyos.common.async_tools import run_coro_sync as direct_alias

    if consumer == "direct":
        module = importlib.import_module("polisyos.common.async_tools")
        assert module is installed_bridge
    elif consumer == "alias":
        assert direct_alias is installed_bridge.run_coro_sync
        module = installed_bridge
    elif consumer == "facade":
        assert facade_alias is installed_bridge
        module = facade_alias
    else:
        namespace: dict[str, object] = {}
        # A real star-import consumer is part of the canonical compatibility criterion.
        exec("from polisyos.common.async_tools import *", namespace)  # noqa: S102
        assert namespace["run_coro_sync"] is installed_bridge.run_coro_sync
        assert "T" not in namespace and "TypeVar" not in namespace
        # Named reflection itself is a required compatibility consumer.
        assert getattr(installed_bridge, "run_coro_sync") is direct_alias  # noqa: B009
        module = installed_bridge
    helpers = (
        module._await_awaitable,
        module._run_coro_in_fresh_loop,
        module.run_coro_sync,
        module.run_blocking_async,
    )
    parameters = []
    for helper in helpers:
        (parameter,) = helper.__type_params__
        hints = typing.get_type_hints(
            helper,
            globalns={**vars(module), "Awaitable": Awaitable, "Callable": Callable},
            localns={"T": parameter},
        )
        assert hints["return"] is parameter
        parameters.append(parameter)
    assert len(set(parameters)) == 4
    assert not hasattr(module, "T") and not hasattr(module, "TypeVar")
    assert direct_alias(asyncio.sleep(0, result=17)) == 17


def test_installed_direct_and_running_loop_context(installed_bridge: ModuleType) -> None:
    """Carry actual contexts across both bridges without leaking the prior request."""
    scope: ContextVar[str | None] = ContextVar("installed_wheel_scope", default=None)

    async def read_scope() -> str | None:
        return scope.get()

    async def inside_loop() -> list[tuple[str | None, str | None]]:
        observed = []
        for value in ("request-A", "request-B"):
            token = scope.set(value)
            try:
                observed.append(
                    (
                        installed_bridge.run_coro_sync(read_scope()),
                        await installed_bridge.run_blocking_async(scope.get),
                    )
                )
            finally:
                scope.reset(token)
        observed.append(
            (
                installed_bridge.run_coro_sync(read_scope()),
                await installed_bridge.run_blocking_async(scope.get),
            )
        )
        return observed

    assert installed_bridge.run_coro_sync(asyncio.sleep(0, result=7)) == 7
    assert asyncio.run(inside_loop()) == [
        ("request-A", "request-A"),
        ("request-B", "request-B"),
        (None, None),
    ]
    assert scope.get() is None


def test_installed_timeout_cleans_real_pending_tasks(installed_bridge: ModuleType) -> None:
    """A cooperative timeout runs the parent and abandoned child's actual finally."""
    observations: list[str] = []
    abandoned_tasks: list[asyncio.Task[None]] = []

    async def abandoned_child(started: asyncio.Event) -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            observations.append("child-finally")

    async def outer() -> None:
        started = asyncio.Event()
        child = asyncio.create_task(abandoned_child(started))
        abandoned_tasks.append(child)
        await started.wait()
        try:
            await asyncio.Event().wait()
        finally:
            observations.append("outer-finally")

    with pytest.raises(TimeoutError):
        installed_bridge.run_coro_sync(outer(), timeout_seconds=0.2)
    print(json.dumps({"observation": "cooperative-timeout-finally", "actual": observations}))
    assert sorted(observations) == ["child-finally", "outer-finally"]
    assert len(abandoned_tasks) == 1 and abandoned_tasks[0].cancelled()


@pytest.mark.parametrize("inside_loop", [False, True])
def test_installed_cancel_reaches_awaitable_finally(
    installed_bridge: ModuleType, inside_loop: bool
) -> None:
    """Cancel the actual generic awaitable bridge before and inside a running loop."""
    observations: list[str] = []

    async def cancellable(started: asyncio.Event) -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            observations.append("finally")

    async def cancel_consumer() -> None:
        started = asyncio.Event()
        task = asyncio.create_task(installed_bridge._await_awaitable(cancellable(started)))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert task.cancelled()

    async def running_loop() -> None:
        installed_bridge.run_coro_sync(cancel_consumer())

    if inside_loop:
        asyncio.run(running_loop())
    else:
        installed_bridge.run_coro_sync(cancel_consumer())
    print(
        json.dumps(
            {
                "observation": "caller-cancellation-finally",
                "inside_loop": inside_loop,
                "actual": observations,
            }
        )
    )
    assert observations == ["finally"]
