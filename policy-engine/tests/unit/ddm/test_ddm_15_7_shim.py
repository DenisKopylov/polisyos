from __future__ import annotations

import polisyos.ddm as canonical_ddm
import polisyos.ddm_15_7 as ddm_15_7


def test_ddm_15_7_root_shim_reexports_canonical_facade_until_july_2026() -> None:
    assert "2026-07-31" in (ddm_15_7.__doc__ or "")
    assert ddm_15_7.__all__ == canonical_ddm.__all__
    assert ddm_15_7.DriftAndDegradationMonitor is canonical_ddm.DriftAndDegradationMonitor
