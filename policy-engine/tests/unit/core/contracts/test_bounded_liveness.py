from __future__ import annotations

# ruff: noqa: S101

import pytest
from pydantic import ValidationError

from polisyos.core.contracts.bounded_liveness import (
    BOUNDED_LIVENESS_CONFIG_SCHEMA_VERSION,
    BoundedLivenessConfig,
    bounded_liveness_config_from_mapping,
)


def test_bounded_liveness_config_resolves_deadline_and_retry_ceiling() -> None:
    config = BoundedLivenessConfig(
        config_id="bounded-liveness.test.v1",
        owner="team-runtime-quality",
        version="2026-05-22",
        default_deadline_s=30.0,
        default_retry_ceiling=2,
        producer_deadline_overrides_s={"scholar.deep_research_job": 0.25},
        producer_retry_ceiling_overrides={"scholar.deep_research_job": 1},
        feature_flag="universal_pdc_bounded_liveness",
        rollback_path="restore previous governed config artifact",
        promotion_evidence_ref="artifact://bounded-liveness/evidence",
    )

    resolved = config.resolve("scholar.deep_research_job")

    assert config.schema_version == BOUNDED_LIVENESS_CONFIG_SCHEMA_VERSION
    assert resolved.producer_key == "scholar.deep_research_job"
    assert resolved.deadline_s == pytest.approx(0.25)
    assert resolved.retry_ceiling == 1
    assert resolved.escalation == "runtime_escalation"


def test_bounded_liveness_config_rejects_ungoverned_runtime_config() -> None:
    with pytest.raises(ValidationError):
        BoundedLivenessConfig(
            config_id="bounded-liveness.invalid.v1",
            owner="",
            version="",
            default_deadline_s=30.0,
            default_retry_ceiling=2,
            feature_flag="",
            rollback_path="",
        )


def test_bounded_liveness_config_from_mapping_clamps_requested_deadline_to_ceiling() -> None:
    config = bounded_liveness_config_from_mapping(
        {
            "config_id": "bounded-liveness.test.v1",
            "owner": "team-runtime-quality",
            "version": "2026-05-22",
            "default_deadline_s": 30.0,
            "default_retry_ceiling": 3,
            "producer_deadline_overrides_s": {"fabric.shadow_run": 2.0},
            "producer_retry_ceiling_overrides": {"fabric.shadow_run": 1},
            "feature_flag": "universal_pdc_bounded_liveness",
            "rollback_path": "restore previous governed config artifact",
        }
    )

    resolved = config.resolve("fabric.shadow_run", requested_deadline_s=10.0, requested_retries=9)

    assert resolved.deadline_s == pytest.approx(2.0)
    assert resolved.retry_ceiling == 1
    assert resolved.notes == [
        "requested_deadline_clamped_to_governed_ceiling",
        "requested_retries_clamped_to_governed_ceiling",
    ]
