"""Local active-bit-removal probe; loaded only when its env flag is set."""

from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

if os.environ.get("B61_REMOVE_CAS_EMISSION_GUARD") == "1":
    from polisyos.scientist.orchestration.engine.retry import _AttemptAuthority

    def _ignore_shared_active_bit(
        self: object,
        operation: Callable[..., object],
        *args: object,
        **kwargs: object,
    ) -> object | None:
        """Keep the child lock/deadline but remove shared parent revocation."""
        with self._lock:
            if self._deadline is not None and time.monotonic() >= self._deadline:
                return None
            return operation(*args, **kwargs)

    _AttemptAuthority.invoke = _ignore_shared_active_bit
