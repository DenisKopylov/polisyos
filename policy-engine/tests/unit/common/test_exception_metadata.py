"""Real exception metadata storage remains available behind subclass hooks."""

from __future__ import annotations

from typing import Any

import pytest

from polisyos.common.exception_metadata import _exception_instance_dict


def test_exception_instance_dict_uses_base_descriptor_without_subclass_hooks() -> None:
    """The shared primitive reads the actual backing dict without attribute dispatch."""

    class HostileError(RuntimeError):
        @property
        def __dict__(self) -> dict[str, Any]:
            raise RuntimeError("subclass dictionary descriptor refuses access")

        def __getattribute__(self, name: str) -> Any:
            if name in {"__dict__", "_diagnostic_marker"}:
                raise RuntimeError("subclass get refuses access")
            return super().__getattribute__(name)

        def __setattr__(self, name: str, value: Any) -> None:
            if name in {"__dict__", "_diagnostic_marker"}:
                raise RuntimeError("subclass set refuses access")
            super().__setattr__(name, value)

        def __delattr__(self, name: str) -> None:
            if name in {"__dict__", "_diagnostic_marker"}:
                raise RuntimeError("subclass delete refuses access")
            super().__delattr__(name)

    error = HostileError("original text")
    cause = LookupError("original cause")
    error.__cause__ = cause
    original = (type(error), error.args, str(error), error.__cause__, error.__traceback__)
    with pytest.raises(RuntimeError, match="subclass get refuses access"):
        _ = error.__dict__
    with pytest.raises(RuntimeError, match="subclass set refuses access"):
        error._diagnostic_marker = "unissued diagnostic"
    with pytest.raises(RuntimeError, match="subclass delete refuses access"):
        del error._diagnostic_marker

    metadata = _exception_instance_dict(error)
    assert type(metadata) is dict
    assert metadata is BaseException.__dict__["__dict__"].__get__(error)
    marker = object()
    metadata["_diagnostic_marker"] = marker
    assert _exception_instance_dict(error) is metadata
    assert metadata["_diagnostic_marker"] is marker
    assert metadata.pop("_diagnostic_marker") is marker
    assert "_diagnostic_marker" not in metadata
    assert (type(error), error.args, str(error), error.__cause__, error.__traceback__) == original
    assert error.__cause__ is cause
