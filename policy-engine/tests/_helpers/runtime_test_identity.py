from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    import pytest
    from pydantic import BaseModel

    from polisyos.core.security.identity import UserIdentityClaims


@contextmanager
def fixture_identity_cell(
    monkeypatch: pytest.MonkeyPatch,
    *,
    cell_id: str,
) -> Iterator[None]:
    """Use an authenticated non-owner cell for requests in dev fixture identity tests."""
    from polisyos.runtime.http import dev_identity_middleware

    factory_attribute = "build_fixture_identity_claims"
    fixture_claims_factory = cast(
        "Callable[[], UserIdentityClaims]",
        getattr(dev_identity_middleware, factory_attribute),
    )

    def build_claims_for_cell() -> UserIdentityClaims:
        claims = fixture_claims_factory()
        return cast(
            "UserIdentityClaims",
            cast("BaseModel", claims).model_copy(update={"cell_id": cell_id}),
        )

    with monkeypatch.context() as scoped_monkeypatch:
        scoped_monkeypatch.setattr(
            dev_identity_middleware,
            "build_fixture_identity_claims",
            build_claims_for_cell,
        )
        yield
