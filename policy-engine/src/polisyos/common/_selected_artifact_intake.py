"""Internal selected-artifact read disposition shared by Common consumers."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

from polisyos.common.canonical_profile import CanonicalProfileRefusalError

_T = TypeVar("_T")
_R = TypeVar("_R")


def read_optional_selected_artifact(
    selector: _R | None,
    reader: Callable[[_R], _T],
    *,
    refusal_code: str,
    expected_errors: tuple[type[Exception], ...],
) -> _T | None:
    """Read a selected view without collapsing refusal into absence.

    ``None`` means the caller supplied no selector. Once a selector is supplied,
    expected storage, decoding, and validation failures become a typed refusal
    carrying the owner-provided code and the original exception as its cause.
    A reader returning ``None`` after selection is also a refusal. Unexpected
    exceptions keep their original type and propagate unchanged.
    """

    if selector is None:
        return None
    try:
        payload = reader(selector)
        if payload is None:
            raise CanonicalProfileRefusalError(refusal_code)
        return payload
    except CanonicalProfileRefusalError:
        raise
    except expected_errors as exc:
        raise CanonicalProfileRefusalError(refusal_code) from exc
