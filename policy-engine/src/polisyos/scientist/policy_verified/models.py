"""Compatibility shim for policy-verified models."""

from __future__ import annotations

from polisyos.scientist._internal.compat import alias_module as _alias_module

_alias_module(__name__, "polisyos.scientist.validation.policy_verified.models", globals())
