from __future__ import annotations

from polisyos.common.async_tools import get_shared_executor
from polisyos.runtime.http.resilience import (
    build_runtime_cas_guard,
    build_runtime_control_store_guard,
)


def test_runtime_blocking_dependency_guards_reuse_shared_executor() -> None:
    cas_guard = build_runtime_cas_guard()
    control_store_guard = build_runtime_control_store_guard()

    try:
        assert cas_guard._executor is get_shared_executor()
        assert control_store_guard._executor is get_shared_executor()
    finally:
        cas_guard.close()
        control_store_guard.close()
