"""Node-collection boundary for the DS9 publication-packet visual path."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DASHBOARD_ROOT = REPO_ROOT / "apps/runtime-dashboard"
PUBLICATION_PACKET_ENTRY = "src/features/runs/domain/publicationPacket.ts"
PURE_EPOCH_OWNER = "src/shared/lib/domain/epochSemantics.ts"


def test_publication_packet_collection_closure_excludes_react_and_locale_catalogs() -> None:
    """Keep the DS9 Node collection path out of React/i18n presentation modules."""

    completed = subprocess.run(  # noqa: S603 - fixed read-only dependency census.
        [
            "corepack",
            "pnpm",
            "exec",
            "depcruise",
            "--config",
            ".dependency-cruiser.mjs",
            "--output-type",
            "json",
            PUBLICATION_PACKET_ENTRY,
        ],
        cwd=DASHBOARD_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    modules = payload["modules"]
    sources = {str(module["source"]) for module in modules}

    assert PURE_EPOCH_OWNER in sources, (
        "publication packets must consume the pure epoch-semantics owner"
    )
    presentation_sources = sorted(
        source
        for source in sources
        if source.endswith((".tsx", ".json"))
        or source.startswith("src/shared/i18n/")
        or "node_modules/.pnpm/react@" in source
        or source in {"react", "react/jsx-runtime"}
    )
    assert presentation_sources == [], (
        "publication-packet Node collection reached presentation modules: "
        f"{presentation_sources}"
    )
