from __future__ import annotations

import hashlib
import json

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.evals.authority import BenchmarkAuthority, PromotionEvidenceRequest
from polisyos.scientist.evals.leakage import (
    detect_benchmark_contamination,
    public_payload_contains_hidden_refs,
    redact_hidden_benchmark_refs,
)
from polisyos.scientist.search.benchmark_registry import BenchmarkRegistry


def _ref(seed: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.model_validate(
            f"sha256:{hashlib.sha256(seed.encode('utf-8')).hexdigest()}"
        ),
        kind="scientist.benchmark_evaluation",
        media_type="application/json",
    )


def test_public_verdict_export_redacts_hidden_holdout_refs(tmp_path) -> None:
    registry = BenchmarkRegistry(tmp_path / "benchmarks")
    hidden = _ref("hidden")
    registry.record("selection", _ref("selection"), family="policy_design", loop_id="loop-a")
    registry.record("hidden_holdout", hidden, family="policy_design", loop_id="loop-a")
    registry.record(
        "rotating_challenge", _ref("rotating"), family="policy_design", loop_id="loop-a"
    )

    verdict = BenchmarkAuthority(registry).verdict(
        PromotionEvidenceRequest(
            family="policy_design",
            claim_mode="estimation",
            loop_id="loop-a",
        )
    )
    public_payload = verdict.public_export()

    assert public_payload["bundle_summary"]["hidden_holdout_present"] is True
    assert not public_payload_contains_hidden_refs(
        public_payload,
        hidden_ref_ids={str(hidden.artifact_id)},
    )


def test_public_verdict_export_redacts_hidden_refs_nested_in_request(tmp_path) -> None:
    registry = BenchmarkRegistry(tmp_path / "benchmarks")
    hidden = _ref("hidden")
    registry.record("selection", _ref("selection"), family="policy_design", loop_id="loop-a")
    registry.record("hidden_holdout", hidden, family="policy_design", loop_id="loop-a")
    registry.record(
        "rotating_challenge", _ref("rotating"), family="policy_design", loop_id="loop-a"
    )

    verdict = BenchmarkAuthority(registry).verdict(
        PromotionEvidenceRequest(
            family="policy_design",
            claim_mode="estimation",
            loop_id="loop-a",
            benchmark_pack_ref=hidden,
        )
    )
    public_payload = verdict.public_export()
    rendered = json.dumps(public_payload, sort_keys=True, default=str)

    assert str(hidden.artifact_id) not in rendered
    assert "[redacted:hidden_benchmark_ref]" in rendered


def test_leakage_helpers_detect_and_redact_contamination_tokens() -> None:
    hidden_id = "sha256:" + "b" * 64
    payload = {
        "summary": f"accidentally exposed {hidden_id}",
        "suite": "hidden-suite-v1",
    }

    redacted = redact_hidden_benchmark_refs(payload, hidden_ref_ids={hidden_id})
    assert not public_payload_contains_hidden_refs(redacted, hidden_ref_ids={hidden_id})
    findings = detect_benchmark_contamination(
        payload,
        hidden_ref_ids={hidden_id},
        hidden_suite_ids={"hidden-suite-v1"},
    )

    assert {item.token_kind for item in findings} == {"artifact_id", "suite_id"}
