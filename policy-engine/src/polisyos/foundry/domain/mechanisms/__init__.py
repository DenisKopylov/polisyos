"""Legacy namespace stub for retired Foundry domain mechanisms modules.

The old compat submodules under ``polisyos.foundry.domain.mechanisms`` must
stay absent, but the package itself remains importable so deprecation tests can
assert that no legacy reexports leak back into the public surface.
"""

from __future__ import annotations

__all__: list[str] = []
