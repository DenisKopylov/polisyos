"""Remove the actual staging capacity while keeping limits and receipt markers."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path


def main() -> None:
    from polisyos.data_forge.domains.academic.batch import _graph_staging
    from tests.unit.data_forge.domains.academic.batch.test_campaign_graph_finalization import (
        test_capacity_refusal_preserves_inputs_and_publishes_no_graph,
    )

    scratch = Path(".tmp") / "graph-finalizer-removal"
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as directory:
        root = Path(directory).resolve()
        test_capacity_refusal_preserves_inputs_and_publishes_no_graph(root / "control")
        print(json.dumps({"synthetic": True, "control": "valid",  # noqa: T201
                          "removed_property": "actual_staging_capacity_check",
                          "declared_limits_and_receipt_markers": "preserved"}))
        _graph_staging.StagingStore.check = lambda *_args, **_kwargs: None
        # The original semantic gate must now fail at its over-budget expectation.
        test_capacity_refusal_preserves_inputs_and_publishes_no_graph(root / "removed")
        raise RuntimeError("removed_capacity_was_not_detected_by_original_gate")


if __name__ == "__main__":
    main()
