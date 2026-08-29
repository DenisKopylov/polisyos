from __future__ import annotations

from pathlib import Path

from polisyos.runtime.http.services.acquisition_surface_projection import (
    find_raw_acquisition_sibling_consumers,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def _consumer_sources() -> dict[str, str]:
    roots = (
        REPO_ROOT / "src/polisyos/runtime/http",
        REPO_ROOT / "apps/runtime-dashboard/src",
    )
    sources: dict[str, str] = {}
    for root in roots:
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in {".py", ".ts", ".tsx"}:
                sources[path.relative_to(REPO_ROOT).as_posix()] = path.read_text(encoding="utf-8")
    return sources


def test_all_server_consumers_use_the_admitted_acquisition_projection_seam() -> None:
    sources = _consumer_sources()

    assert find_raw_acquisition_sibling_consumers(sources) == ()


def test_new_raw_sibling_consumer_is_rejected_behaviorally() -> None:
    sources = _consumer_sources()
    sources["src/polisyos/runtime/http/services/raw_acquisition_sibling.py"] = """
from pathlib import Path

payload = Path(
    'architecture/policy_design_case/layer3_gy_n13b_acquisition_executor_contract.json'
).read_text()
action_eligibility = payload
"""

    assert find_raw_acquisition_sibling_consumers(sources) == (
        "src/polisyos/runtime/http/services/raw_acquisition_sibling.py",
    )
