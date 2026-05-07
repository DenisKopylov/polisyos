"""Canonical package for IR citation and artifact reference contracts."""

from __future__ import annotations

from polisyos.ir.references.citations import *  # noqa: F403
from polisyos.ir.references.citations import __all__ as _citation_exports
from polisyos.ir.references.refs import *  # noqa: F403
from polisyos.ir.references.refs import __all__ as _ref_exports

__all__ = sorted({*_citation_exports, *_ref_exports})
