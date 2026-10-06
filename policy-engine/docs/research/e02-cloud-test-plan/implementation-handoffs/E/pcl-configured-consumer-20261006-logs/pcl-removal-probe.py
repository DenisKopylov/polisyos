"""Remove actual persistence at the shared summary choke point, retaining projections."""
import sys
import pytest
from polisyos.foundry.methods.catalog.econometrics import advanced

original = advanced._summarize_interval_diagnostics
def without_persistence(**kwargs):
    kwargs["calibration_store"] = None
    return original(**kwargs)
advanced._summarize_interval_diagnostics = without_persistence
raise SystemExit(pytest.main(sys.argv[1:]))
