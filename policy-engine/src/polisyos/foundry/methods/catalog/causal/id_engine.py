"""Compatibility shim for the Phase 4.1 id_engine package split.

The importable implementation now lives in the sibling ``id_engine/``
package, which re-exports the previous module surface.
"""

from __future__ import annotations

__all__: list[str] = []
