"""Compatibility shim for human-review VOI escalation."""

from __future__ import annotations

from polisyos.scientist._internal.compat import alias_module as _alias_module

_alias_module(__name__, "polisyos.scientist.governance.human_review.voi_escalation", globals())
