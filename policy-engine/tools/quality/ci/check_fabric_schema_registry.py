#!/usr/bin/env python3
"""CI wrapper for the Fabric schema governance gate."""
from __future__ import annotations

import sys
from pathlib import Path
from tools._lib.imports import repo_root_from

REPO_ROOT = repo_root_from(__file__)
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.quality.validation.fabric_schema_governance import main


if __name__ == "__main__":
    raise SystemExit(main())
