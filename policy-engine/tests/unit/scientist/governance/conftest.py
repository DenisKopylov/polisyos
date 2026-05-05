from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.governance.passes.base import PassContext
from polisyos.core.governance.profiles import ValidationProfile


@pytest.fixture
def cas_store(tmp_path) -> FileSystemCAS:
    return FileSystemCAS(tmp_path)


@pytest.fixture
def strict_profile() -> ValidationProfile:
    return ValidationProfile.strict()


@pytest.fixture
def mvp_profile() -> ValidationProfile:
    return ValidationProfile.mvp()


@pytest.fixture
def fast_profile() -> ValidationProfile:
    return ValidationProfile.fast()


@pytest.fixture
def pass_context_factory(cas_store) -> Callable[..., PassContext]:
    def _make(
        *,
        state: dict[str, Any] | None = None,
        profile: ValidationProfile | None = None,
        ir: Any = None,
        run_id: str = "R_gov_test",
    ) -> PassContext:
        s = state or {}
        s.setdefault("_store", cas_store)
        return PassContext(
            ir=ir,
            state=s,
            registry_bundle=None,
            profile=profile or ValidationProfile.strict(),
            run_id=run_id,
        )

    return _make
