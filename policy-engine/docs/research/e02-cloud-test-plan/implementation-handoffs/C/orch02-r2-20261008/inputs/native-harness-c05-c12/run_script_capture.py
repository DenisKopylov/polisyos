"""Capture real runtime origins of an external property driver without source edits."""
from __future__ import annotations

from pathlib import Path
import runpy
import sys

import orch02_capture


def main() -> None:
    script = Path(sys.argv[1]).resolve()
    sys.argv = [str(script), *sys.argv[2:]]
    status = 0
    try:
        runpy.run_path(str(script), run_name="__main__")
    except SystemExit as exc:
        status = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        raise
    except BaseException:
        status = 1
        raise
    finally:
        orch02_capture.pytest_sessionfinish(None, status)


if __name__ == "__main__":
    main()
