from __future__ import annotations

import json
from pathlib import Path

import pytest

GOLDEN_RECORDS_PATH = (
    Path(__file__).resolve().parents[1] / "_golden" / "contract" / "golden_records.json"
)


@pytest.fixture(scope="session")
def golden_records() -> dict[str, object]:
    if not GOLDEN_RECORDS_PATH.exists():
        raise FileNotFoundError(f"Golden record file missing: {GOLDEN_RECORDS_PATH}")
    return json.loads(GOLDEN_RECORDS_PATH.read_text("utf-8"))
