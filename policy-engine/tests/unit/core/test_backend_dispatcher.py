from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from polisyos.core.backends import BackendDispatcher, BackendNotAvailableError
from polisyos.core.governance.passes.legal_pass import LegalPass


def test_dispatcher_register_and_resolve() -> None:
    dispatcher = BackendDispatcher[str, int]()
    dispatcher.register("alpha", 42)

    assert dispatcher.resolve("alpha") == 42
    assert dispatcher.available_backends() == frozenset({"alpha"})


def test_dispatcher_factory_is_cached() -> None:
    calls = {"count": 0}

    def factory(key: str) -> int:
        calls["count"] += 1
        return len(key)

    dispatcher = BackendDispatcher[str, int](factory=factory)

    assert dispatcher.resolve("abc") == 3
    assert dispatcher.resolve("abc") == 3
    assert calls["count"] == 1


def test_dispatcher_availability_check() -> None:
    dispatcher = BackendDispatcher[str, int](
        factory=lambda _key: 0,
        availability_check=lambda value: value > 0,
    )

    with pytest.raises(BackendNotAvailableError):
        dispatcher.resolve("x")


def test_legal_pass_unknown_backend_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Unknown backend"):
        LegalPass(backend="unknown_backend")


def test_dispatcher_thread_safety_concurrent_resolve_single_factory_call() -> None:
    lock = threading.Lock()
    calls = {"count": 0}

    def factory(key: str) -> object:
        with lock:
            calls["count"] += 1
        return {"backend": key}

    dispatcher = BackendDispatcher[str, object](factory=factory)

    def worker() -> object:
        return dispatcher.resolve("shared")

    with ThreadPoolExecutor(max_workers=24) as pool:
        resolved = list(pool.map(lambda _i: worker(), range(200)))

    assert calls["count"] == 1
    first = resolved[0]
    assert all(item is first for item in resolved)


def test_dispatcher_thread_safety_concurrent_register_and_get() -> None:
    dispatcher = BackendDispatcher[int, int]()

    def worker(index: int) -> int:
        dispatcher.register(index, index)
        return dispatcher.resolve(index)

    with ThreadPoolExecutor(max_workers=16) as pool:
        values = list(pool.map(worker, range(200)))

    assert values == list(range(200))
    assert len(dispatcher.available_backends()) == 200
