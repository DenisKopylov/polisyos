"""Enable JAX float64 for calibration tests that use finite-difference Hessian."""

import os

os.environ.setdefault("JAX_ENABLE_X64", "1")
