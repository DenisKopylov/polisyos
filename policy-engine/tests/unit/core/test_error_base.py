from __future__ import annotations

import pytest

from polisyos.core.errors import ErrorCategory, PolicyOSError


def test_policy_os_error_metadata_and_flags() -> None:
    err = PolicyOSError(
        "temporary outage",
        category="transient",
        stage="fabric.connectors",
        code="CONN_503",
        details={"connector": "eurostat"},
    )

    assert str(err) == "temporary outage"
    assert err.category == ErrorCategory.TRANSIENT
    assert err.stage == "fabric.connectors"
    assert err.code == "CONN_503"
    assert err.details["connector"] == "eurostat"
    assert err.is_transient
    assert not err.is_fatal
    assert not err.is_validation
    assert err.to_dict()["category"] == "transient"


def test_invalid_category_raises_clear_error() -> None:
    with pytest.raises(ValueError, match="Unsupported error category"):
        PolicyOSError("bad", category="unknown")


def test_subclass_defaults_are_applied() -> None:
    class _ValidationError(PolicyOSError):
        default_stage = "scientist.validation"
        default_category = ErrorCategory.VALIDATION

    err = _ValidationError("invalid bundle")
    assert err.stage == "scientist.validation"
    assert err.category == ErrorCategory.VALIDATION
    assert err.is_validation


def test_details_mapping_is_immutable() -> None:
    err = PolicyOSError("immutable details", details={"a": 1})
    with pytest.raises(TypeError):
        err.details["b"] = 2  # type: ignore[index]
