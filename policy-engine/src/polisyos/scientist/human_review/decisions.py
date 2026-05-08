"""Compatibility shim for human-review decision helpers."""

from __future__ import annotations

from polisyos.scientist._internal.compat import alias_module as _alias_module

_alias_module(__name__, "polisyos.scientist.governance.human_review.decisions", globals())
