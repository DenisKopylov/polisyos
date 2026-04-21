from __future__ import annotations

import json
from pathlib import Path

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.components.cli import main
from polisyos.core.contracts.foundry import MetricObservationBundle, ModelOutputs
from polisyos.scientist.validation.metrics import persist_metric_observation_bundle


def test_metric_validate_cli_emits_summary_json(tmp_path: Path, capsys) -> None:
    cas_root = tmp_path / ".polisyos"
    store = FileSystemCAS(cas_root)
    bundle_ref = persist_metric_observation_bundle(
        store,
        MetricObservationBundle(
            dataset_id="holdout_cli",
            task="binary",
            sample_ids=["r1", "r2", "r3", "r4", "r5", "r6"],
            y_true=[0, 1, 0, 1, 1, 0],
            models={
                "baseline": ModelOutputs(
                    model_id="baseline",
                    y_pred=[0, 1, 0, 0, 1, 0],
                    y_score=[0.2, 0.9, 0.3, 0.4, 0.7, 0.2],
                ),
                "candidate": ModelOutputs(
                    model_id="candidate",
                    y_pred=[0, 1, 0, 1, 1, 0],
                    y_score=[0.1, 0.95, 0.25, 0.8, 0.75, 0.1],
                ),
            },
        ),
    )

    code = main(
        [
            "metric-validate",
            "--observation-bundle-ref",
            str(bundle_ref.artifact_id),
            "--baseline",
            "baseline",
            "--candidates",
            "candidate",
            "--metrics",
            "roc_auc",
            "accuracy",
            "--n-resamples",
            "500",
            "--random-seed",
            "11",
            "--cas-root",
            str(cas_root),
        ]
    )
    out = capsys.readouterr().out

    assert code == 0
    payload = json.loads(out)
    assert payload["family_method"] == "holm"
    assert payload["comparison_count"] == 2
    assert payload["cas_artifact_id"].startswith("sha256:")
