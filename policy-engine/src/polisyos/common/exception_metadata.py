"""Minimal access to exception storage for owner-emitted diagnostic metadata."""

from __future__ import annotations


def _exception_instance_dict(error: BaseException) -> dict[str, object] | None:
    """Return real storage without invoking an exception subclass's hooks.

    Callers still own validation and authorization of any stored metadata. This
    primitive changes no args, cause, traceback, identity or public contract.
    """
    try:
        descriptor = BaseException.__dict__["__dict__"]
        metadata = descriptor.__get__(error)
    except Exception:
        return None
    return metadata if type(metadata) is dict else None
