from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("HYPOTHESIS_STORAGE_DIRECTORY", str(REPO_ROOT / "_cache" / "hypothesis"))

from hypothesis import settings
from hypothesis.database import DirectoryBasedExampleDatabase

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

settings.register_profile(
    "repo_quality",
    database=DirectoryBasedExampleDatabase(str(REPO_ROOT / "_cache" / "hypothesis" / "repo_quality")),
)
settings.load_profile("repo_quality")
