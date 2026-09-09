"""Remove actual whole-output disk enforcement while preserving marked artifacts."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path


def main() -> None:
    """Run the unchanged real finalizer gate before and after owner removal."""
    from polisyos.data_forge.domains.academic.batch import _graph_staging
    from tests.unit.data_forge.domains.academic.batch.test_campaign_graph_finalization import (
        test_completed_envelope_disk_refusal_precedes_publication,
    )

    scratch = Path(".tmp") / "graph-finalizer-disk-removal"
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as directory:
        root = Path(directory).resolve()
        test_completed_envelope_disk_refusal_precedes_publication(root / "control")
        print(json.dumps({"synthetic": True, "control": "valid",  # noqa: T201
                          "removed_property": "complete_owned_output_disk_enforcement",
                          "declared_limits_and_artifact_markers": "preserved"}))
        _graph_staging.enforce_owned_output_budget = lambda *_args, **_kwargs: 0
        test_completed_envelope_disk_refusal_precedes_publication(root / "removed")
        raise RuntimeError("removed_disk_enforcement_not_detected")


if __name__ == "__main__":
    main()
