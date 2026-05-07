from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.evals.authority import BenchmarkAuthority, PromotionEvidenceRequest
from polisyos.scientist.methods.search.benchmark_registry import BenchmarkRegistry
from pydantic import ValidationError


def _ref(seed: str, *, kind: str = "scientist.benchmark_evaluation") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.model_validate(
            f"sha256:{hashlib.sha256(seed.encode('utf-8')).hexdigest()}"
        ),
        kind=kind,
        media_type="application/json",
    )


def test_missing_hidden_holdout_blocks_estimation_promotion(tmp_path) -> None:
    registry = BenchmarkRegistry(tmp_path / "benchmarks")
    registry.record("selection", _ref("selection"), family="causal_core", loop_id="loop-a")
    authority = BenchmarkAuthority(registry)

    verdict = authority.verdict(
        PromotionEvidenceRequest(
            family="causal_core",
            claim_mode="estimation",
            loop_id="loop-a",
        )
    )

    assert verdict.default_enable_allowed is False
    assert verdict.missing == ["hidden_holdout_evaluation_ref"]


def test_non_core_family_without_rotating_challenge_blocks_promotion(tmp_path) -> None:
    registry = BenchmarkRegistry(tmp_path / "benchmarks")
    registry.record("selection", _ref("selection"), family="policy_design", loop_id="loop-a")
    registry.record(
        "hidden_holdout",
        _ref("hidden"),
        family="policy_design",
        loop_id="loop-a",
    )
    authority = BenchmarkAuthority(registry)

    verdict = authority.verdict(
        PromotionEvidenceRequest(
            family="policy_design",
            claim_mode="estimation",
            loop_id="loop-a",
        )
    )

    assert verdict.default_enable_allowed is False
    assert verdict.missing == ["rotating_challenge_evaluation_refs"]


def test_stale_benchmark_revision_blocks_default_enable(tmp_path) -> None:
    registry = BenchmarkRegistry(tmp_path / "benchmarks")
    expires_at = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    registry.record("selection", _ref("selection"), family="causal_core", loop_id="loop-a")
    registry.record(
        "hidden_holdout",
        _ref("hidden"),
        family="causal_core",
        loop_id="loop-a",
        suite_id="hidden-v1",
        metadata={"revision_status": "stale", "expires_at": expires_at},
    )
    authority = BenchmarkAuthority(registry)

    verdict = authority.verdict(
        PromotionEvidenceRequest(
            family="causal_core",
            claim_mode="estimation",
            loop_id="loop-a",
        )
    )

    assert verdict.missing == []
    assert verdict.default_enable_allowed is False
    assert any("hidden_holdout:hidden-v1:revision_stale" in item for item in verdict.stale)
    assert any("hidden_holdout:hidden-v1:expired" in item for item in verdict.stale)


def test_complete_non_core_bundle_allows_medium_risk_promotion(tmp_path) -> None:
    registry = BenchmarkRegistry(tmp_path / "benchmarks")
    registry.record("selection", _ref("selection"), family="policy_design", loop_id="loop-a")
    registry.record(
        "hidden_holdout",
        _ref("hidden"),
        family="policy_design",
        loop_id="loop-a",
    )
    registry.record(
        "rotating_challenge",
        _ref("rotating"),
        family="policy_design",
        loop_id="loop-a",
    )
    authority = BenchmarkAuthority(registry)

    verdict = authority.verdict(
        PromotionEvidenceRequest(
            family="policy_design",
            claim_mode="estimation",
            loop_id="loop-a",
        )
    )

    assert verdict.missing == []
    assert verdict.stale == []
    assert verdict.default_enable_allowed is True
    assert verdict.leakage_warnings == ["hidden_holdout_refs_present_internal_only"]


def test_high_risk_promotion_requires_sentinel_refs(tmp_path) -> None:
    registry = BenchmarkRegistry(tmp_path / "benchmarks")
    registry.record("selection", _ref("selection"), family="causal_core", loop_id="loop-a")
    registry.record(
        "hidden_holdout",
        _ref("hidden"),
        family="causal_core",
        loop_id="loop-a",
    )
    authority = BenchmarkAuthority(registry)

    verdict = authority.verdict(
        PromotionEvidenceRequest(
            family="causal_core",
            claim_mode="estimation",
            loop_id="loop-a",
            risk_tier="high",
        )
    )

    assert verdict.default_enable_allowed is False
    assert verdict.missing == ["sentinel_evaluation_refs"]


def test_free_form_benchmark_refs_are_rejected_when_registry_lookup_is_required() -> None:
    with pytest.raises(ValidationError):
        PromotionEvidenceRequest.model_validate(
            {
                "family": "policy_design",
                "claim_mode": "estimation",
                "registry_lookup_required": True,
                "benchmark_pack_ref": "sha256:" + "a" * 64,
            }
        )


def test_typed_benchmark_ref_must_resolve_when_registry_lookup_is_required(
    tmp_path,
) -> None:
    registry = BenchmarkRegistry(tmp_path / "benchmarks")
    registry.record("selection", _ref("selection"), family="policy_design", loop_id="loop-a")
    registry.record(
        "hidden_holdout",
        _ref("hidden"),
        family="policy_design",
        loop_id="loop-a",
    )
    registry.record(
        "rotating_challenge",
        _ref("rotating"),
        family="policy_design",
        loop_id="loop-a",
    )
    authority = BenchmarkAuthority(registry)

    verdict = authority.verdict(
        PromotionEvidenceRequest(
            family="policy_design",
            claim_mode="estimation",
            loop_id="loop-a",
            benchmark_pack_ref=_ref("unregistered-pack"),
        )
    )

    assert verdict.default_enable_allowed is False
    assert verdict.missing == ["registered_benchmark_pack_ref"]


def test_registered_benchmark_ref_can_support_lookup_required_request(tmp_path) -> None:
    registry = BenchmarkRegistry(tmp_path / "benchmarks")
    pack_ref = _ref("selection")
    registry.record("selection", pack_ref, family="policy_design", loop_id="loop-a")
    registry.record(
        "hidden_holdout",
        _ref("hidden"),
        family="policy_design",
        loop_id="loop-a",
    )
    registry.record(
        "rotating_challenge",
        _ref("rotating"),
        family="policy_design",
        loop_id="loop-a",
    )
    authority = BenchmarkAuthority(registry)

    verdict = authority.verdict(
        PromotionEvidenceRequest(
            family="policy_design",
            claim_mode="estimation",
            loop_id="loop-a",
            benchmark_pack_ref=pack_ref,
        )
    )

    assert verdict.missing == []
    assert verdict.default_enable_allowed is True


def test_near_frontier_promotion_requires_fresh_rotating_challenge_lineage(tmp_path) -> None:
    registry = BenchmarkRegistry(tmp_path / "benchmarks")
    registry.record("selection", _ref("selection"), family="causal_core", loop_id="loop-a")
    registry.record(
        "hidden_holdout",
        _ref("hidden"),
        family="causal_core",
        loop_id="loop-a",
    )
    authority = BenchmarkAuthority(registry)

    verdict = authority.verdict(
        PromotionEvidenceRequest(
            family="causal_core",
            claim_mode="estimation",
            loop_id="loop-a",
            near_frontier=True,
        )
    )

    assert verdict.default_enable_allowed is False
    assert "fresh_rotating_challenge_evidence_missing" in verdict.missing


def test_benchmark_authority_tracks_challenge_pack_lineage(tmp_path) -> None:
    registry = BenchmarkRegistry(tmp_path / "benchmarks")
    lineage = {
        "pack_id": "rotating-v1",
        "kind": "rotating_challenge",
        "source_challenge_ids": ["challenge-a"],
        "source_failure_ref_ids": ["failure-a"],
        "lineage_key": "lineage-a",
        "status": "active",
    }
    registry.record("selection", _ref("selection"), family="policy_design", loop_id="loop-a")
    registry.record(
        "hidden_holdout",
        _ref("hidden"),
        family="policy_design",
        loop_id="loop-a",
    )
    registry.record(
        "rotating_challenge",
        _ref("rotating"),
        family="policy_design",
        loop_id="loop-a",
        suite_id="rotating-v1",
        metadata={"challenge_pack_lineage": lineage},
    )
    authority = BenchmarkAuthority(registry)

    verdict = authority.verdict(
        PromotionEvidenceRequest(
            family="policy_design",
            claim_mode="estimation",
            loop_id="loop-a",
            near_frontier=True,
        )
    )

    assert verdict.default_enable_allowed is True
    assert verdict.challenge_pack_lineage[0]["lineage_key"] == "lineage-a"
    assert verdict.public_export()["challenge_pack_lineage"][0]["source_challenge_ids"] == [
        "challenge-a"
    ]
