# Legacy Scientist APIs.
# This package exists only for compatibility during the compat window.
# Do not use in new code.
from __future__ import annotations

import warnings

warnings.warn(
    "polisyos.scientist._legacy is deprecated. Use polisyos.scientist.build_workflow()/run_experiment() instead.",
    DeprecationWarning,
    stacklevel=2,
)
