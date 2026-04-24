from __future__ import annotations

import json

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.runtime.http.services.artifact_inspector import ArtifactInspectorService
from polisyos.runtime.http.services.lineage import LineageService


def test_redaction_hook_failure_fails_closed(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    ref = store.put_bytes(
        b"super secret",
        PutOptions(kind="test.preview", media_type="text/plain"),
    )
    service = ArtifactInspectorService(
        store=store,
        lineage_service=LineageService(store=store),
        redaction_hooks={
            "test.preview": lambda preview, mode: (_ for _ in ()).throw(RuntimeError("boom"))
        },
    )

    preview = service.get_content_preview(ref.artifact_id)

    assert preview.preview == "[REDACTED]"


def test_decision_packet_preview_adds_typed_sidecar(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    payload = {
        "document_outline": [
            {
                "section_id": "policy_answer",
                "section_type": "policy",
                "title": "Recommendation",
            }
        ],
        "metric_significance_by_metric": {
            "gdp_change": {
                "effect_size": 0.23,
                "p_value": 0.02,
                "test_id": "paired_t",
                "test_label": "Paired t test",
            }
        },
        "metric_validation_comparison_rows": [
            {
                "metric_id": "gdp_change",
                "effect_size": 0.23,
                "ci_low": 0.12,
                "ci_high": 0.34,
                "resampling_method": "analytic",
                "test_id": "paired_t",
            }
        ],
    }
    ref = store.put_bytes(
        json.dumps(payload).encode("utf-8"),
        PutOptions(
            kind="scientist.decision_packet",
            media_type="application/json",
        ),
    )
    service = ArtifactInspectorService(
        store=store,
        lineage_service=LineageService(store=store),
    )

    preview = service.get_content_preview(ref.artifact_id)

    assert preview.decision_packet_preview is not None
    assert preview.decision_packet_preview.document_outline[0].section_type == "policy"
    structured_effect = preview.decision_packet_preview.metric_significance_by_metric[
        "gdp_change"
    ].effect_size
    assert structured_effect is not None
    assert structured_effect.point == 0.23
    assert structured_effect.ci_95 == (0.12, 0.34)
    assert structured_effect.method == "analytic"
