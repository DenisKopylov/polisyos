from __future__ import annotations

import polisyos.ddm_15_7 as ddm_15_7


def test_ddm_15_7_root_shim_reexports_canonical_facade() -> None:
    assert ddm_15_7.DriftAndDegradationMonitor.__module__.startswith("polisyos.ddm.")
    assert "DriftAndDegradationMonitor" in ddm_15_7.__all__
