# Selected Mac dependency profile

Before the final source/input freeze, the existing candidate-local Python 3.14.3
environment contained 249 distributions. The actual `uv pip check --python
policy-engine/.venv/bin/python` found one incompatibility: `ruptures==1.1.10`
declares Python `>=3.9,<3.14`. The composed numerical queue does not select the
analytics extra; its source-only primary collection also completed without a
ruptures import failure. Collection does not prove optional backend behavior.

Root preserved the exact `ruptures` package and distribution metadata by renaming
those two directories into `.venv/.preserved-e02-20261010/unsupported-unselected-analytics/`.
The full targeted 68-file inventory was hashed before the move and read back
afterward. No bytes were deleted, no package cache was changed, and no project,
lock, scientific contract, or production input was edited. This is selection of
the executable profile, not repair of the analytics extra's compatibility.

The resulting environment contains 248 distributions; the complete installed
inventory and successful integrity output are retained under
`LOCAL/raw/mac-profile-unsupported-package-preservation-20261010/`. The actual
integrity output says `All installed packages are compatible`. A fresh process
also confirmed that `ruptures` is absent from the selected import path. The
preserved files remain locally available. Their preservation location is outside
the interpreter's site-packages, and is not an admitted runtime input.

The isolated Legal encoder profile, browser core profile, Linux root profile,
and Python 3.12 DoWhy worker retain their separate recipes and integrity
receipts. None is substituted for another backend. Numerical producer, consumer,
removal, browser, installed-artifact, and native gate execution remain pending
the final freeze. This profile operation establishes environment integrity only;
it closes no finding and creates no calibration, authority, or currentness fact.

The root analytics extra's Python/locked-ruptures combination remains
`not_established`. A future analytics claim needs a supported recipe or a typed
isolated worker and its real consumers; the package was not made compatible by
changing its declared Python range.
