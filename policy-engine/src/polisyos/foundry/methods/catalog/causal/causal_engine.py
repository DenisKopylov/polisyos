"""Compatibility shim for the Phase 4.1 CausalEngine package split.

The importable implementation now lives in the sibling ``causal_engine/``
package. Python prefers that package over this legacy module path, and the
package re-exports the previous public and test-facing symbols.
"""

from __future__ import annotations

__all__: list[str] = []
