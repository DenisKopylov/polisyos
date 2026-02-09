from __future__ import annotations

from datetime import datetime, timedelta, timezone

from polisyos.core.contracts.scholar import FreshnessMetadata, FreshnessStatus
from polisyos.scholar.freshness import (
    FreshnessPolicy,
    build_freshness_metadata,
    resolve_domain_thresholds,
)
from polisyos.scholar.freshness_store import FreshnessRuntimeState
from polisyos.scholar.policies import ScholarPolicy
from polisyos.scholar.types import KnowledgeBundlePayloadV1


def test_freshness_status_transitions() -> None:
    now = datetime(2026, 2, 1, tzinfo=timezone.utc)
    meta = FreshnessMetadata(
        created_at=now - timedelta(days=10),
        source_freshness_at=now - timedelta(days=10),
        staleness_threshold_seconds=30 * 24 * 3600,
        expiry_threshold_seconds=90 * 24 * 3600,
    )
    assert meta.compute_status(now) is FreshnessStatus.FRESH

    stale_now = now + timedelta(days=25)
    assert meta.compute_status(stale_now) is FreshnessStatus.STALE

    expired_now = now + timedelta(days=95)
    assert meta.compute_status(expired_now) is FreshnessStatus.EXPIRED


def test_freshness_policy_respects_cooldown() -> None:
    now = datetime(2026, 2, 1, tzinfo=timezone.utc)
    meta = FreshnessMetadata(
        created_at=now - timedelta(days=60),
        source_freshness_at=now - timedelta(days=60),
        staleness_threshold_seconds=7 * 24 * 3600,
        expiry_threshold_seconds=90 * 24 * 3600,
        refresh_cooldown_seconds=3600,
        last_refresh_attempt_at=now - timedelta(minutes=20),
    )
    policy = FreshnessPolicy(refresh_cooldown_seconds=3600)
    result = policy.check(bundle_ref="sha256:" + "a" * 64, freshness=meta, now=now)
    assert result.status is FreshnessStatus.STALE
    assert result.blocked_by_cooldown
    assert not result.needs_refresh


def test_domain_threshold_resolution() -> None:
    health = resolve_domain_thresholds("health")
    fiscal = resolve_domain_thresholds("fiscal")
    default = resolve_domain_thresholds("unknown-domain")

    assert health.staleness_seconds == 14 * 24 * 3600
    assert fiscal.staleness_seconds == 90 * 24 * 3600
    assert default.staleness_seconds == 30 * 24 * 3600


def test_policy_threshold_resolution_overrides_defaults() -> None:
    policy = ScholarPolicy()
    thresholds = resolve_domain_thresholds("health", policy=policy)
    assert thresholds.staleness_seconds == 14 * 24 * 3600
    assert thresholds.expiry_seconds == 60 * 24 * 3600


def test_freshness_policy_honors_next_retry_from_runtime_state() -> None:
    now = datetime(2026, 2, 1, tzinfo=timezone.utc)
    freshness = FreshnessMetadata(
        created_at=now - timedelta(days=90),
        source_freshness_at=now - timedelta(days=90),
        staleness_threshold_seconds=7 * 24 * 3600,
        expiry_threshold_seconds=180 * 24 * 3600,
    )
    runtime = FreshnessRuntimeState(
        last_checked_at=now - timedelta(minutes=5),
        last_refresh_attempt_at=now - timedelta(minutes=5),
        next_retry_at=now + timedelta(minutes=30),
        failed_refresh_count=2,
    )
    policy = FreshnessPolicy(refresh_cooldown_seconds=3600)
    result = policy.check(
        bundle_ref="sha256:" + "b" * 64,
        freshness=freshness,
        runtime_state=runtime,
        now=now,
    )
    assert result.status is FreshnessStatus.STALE
    assert result.blocked_by_cooldown
    assert not result.needs_refresh
    assert result.retry_after_seconds is not None


def test_build_freshness_metadata_is_deterministic_with_source_timestamp() -> None:
    ts = datetime(2025, 12, 31, 0, 0, tzinfo=timezone.utc)
    meta = build_freshness_metadata(
        domain="labor",
        source_freshness_at=ts,
    )
    assert meta.created_at == ts


def test_backward_compatibility_legacy_bundle_without_freshness() -> None:
    legacy_payload = {
        "schema_version": "1.0",
        "bundle_id": "bundle.test",
        "intent": {},
        "doc_meta_artifact_ids": [],
        "doc_version_ids": [],
        "doc_source_ids": [],
        "claim_ids": [],
        "claim_set_artifact_ids": [],
        "conflict_set_ids": [],
        "conflict_set_artifact_ids": [],
        "conflict_resolution_artifact_ids": [],
        "trust_assessment_ids": [],
        "trust_assessment_artifact_ids_by_id": {},
        "quality_report_ids": [],
        "quality_report_artifact_ids": [],
        "policy_ids_used": {},
        "created_by": {},
        "summary": {},
    }
    bundle = KnowledgeBundlePayloadV1.model_validate(legacy_payload)
    assert bundle.freshness.enrichment_count == 1
    assert bundle.freshness.compute_status() in {
        FreshnessStatus.FRESH,
        FreshnessStatus.STALE,
        FreshnessStatus.EXPIRED,
    }
