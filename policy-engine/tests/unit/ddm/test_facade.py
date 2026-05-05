from __future__ import annotations

import polisyos.ddm as ddm


def test_ddm_facade_imports_canonical_package() -> None:
    assert ddm.DriftAndDegradationMonitor.__module__.startswith("polisyos.ddm.")
    assert "DriftAndDegradationMonitor" in ddm.__all__
