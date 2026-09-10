"""Remove only the N9 source-authority property while retaining actual input markers."""

from __future__ import annotations

import argparse
import json
import sys
from unittest.mock import patch

import pytest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "property", choices=("synthetic_authority", "producer_identity", "strangle"),
    )
    args = parser.parse_args()
    if args.property == "strangle":
        return _strangle()
    if args.property == "synthetic_authority":
        from polisyos.runtime.quality import promotion_sequence

        with patch.object(promotion_sequence, "_synthetic_evidence_payload", lambda *_inputs: None):
            return int(pytest.main([
                "tests/unit/runtime/quality/test_generation_source.py::"
                "test_synthetic_independence_source_establishes_mechanics_but_never_authority",
                "-q", "--tb=short",
            ]))
    from polisyos.runtime.quality.grounding_bind import recompute_grounding_decision_content_hash
    from tools.quality.validation import check_layer3_gy_promotion_contract as checker

    original = checker._cg2_contract_bind

    def authored_after_production() -> tuple[
        checker.CredalReference, checker.GroundingDecisionCertificate,
    ]:
        reference, decision = original()
        changed = decision.model_copy(update={
            "closed_obligations": (*decision.closed_obligations, "posthoc_fabricated_closure"),
        })
        changed = changed.model_copy(update={
            "content_hash": recompute_grounding_decision_content_hash(changed),
        })
        return reference, changed

    with patch.object(checker, "_cg2_contract_bind", authored_after_production):
        return int(pytest.main([
            "tests/repo_quality/tools/test_layer3_gy_promotion_contract.py::"
            "test_n9_contract_input_preserves_actual_cg2_producer_output",
            "-q", "--tb=short",
        ]))


def _strangle() -> int:
    """Observe both real resolutions; exit status alone never decides the packet."""
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality import promotion_sequence as owner

    original_resolve = owner.N9PromotionEvidenceBridgeRepository.resolve
    original_ancestry = owner._synthetic_evidence_payload
    observations = []

    def observed_resolve(self: object, **kwargs: object) -> object:
        result = original_resolve(self, **kwargs)
        if not observations:
            bridge = json.loads(self._store.get_bytes(kwargs["bridge_ref"].artifact_id))
            source = json.loads(self._store.get_bytes(bridge["source_artifact_id"]))
            observations.append({
                "candidate_content_hash": bridge["candidate_content_hash"],
                "design_problem_binding": bridge["design_problem_binding"],
                "source_mechanism_hash": gy_content_hash({
                    key: value for key, value in source.items() if key != "synthetic"
                }),
                "actual_source_ancestry": original_ancestry(source),
                "source_disposition": bridge["source_disposition"],
                "bridge_synthetic": bridge.get("synthetic"),
                "resolution": result.model_dump(mode="json"),
            })
        return result

    node = (
        "tests/unit/runtime/quality/test_generation_source.py::"
        "test_synthetic_independence_source_establishes_mechanics_but_never_authority"
    )
    with patch.object(owner.N9PromotionEvidenceBridgeRepository, "resolve", observed_resolve):
        baseline_exit = int(pytest.main([node, "-q", "--tb=short"]))
        current = observations.pop() if observations else None
        with patch.object(owner, "_synthetic_evidence_payload", lambda *_inputs: None):
            removal_exit = int(pytest.main([node, "-q", "--tb=short"]))
        removed = observations.pop() if observations else None
    flipped = bool(
        current is not None and removed is not None
        and current["actual_source_ancestry"] is True
        and removed["actual_source_ancestry"] is True
        and current["source_disposition"] == removed["source_disposition"] == "established"
        and current["source_mechanism_hash"] == removed["source_mechanism_hash"]
        and current["candidate_content_hash"] == removed["candidate_content_hash"]
        and current["design_problem_binding"] == removed["design_problem_binding"]
        and current["bridge_synthetic"] is True
        and current["resolution"]["status"] == "refused"
        and current["resolution"]["limitation_code"] == "synthetic_evidence_cannot_grant_authority"
        and removed["resolution"]["status"] == "established"
    )
    packet = {
        "schema_version": "policyos.runtime.quality.n9_source_authority_strangle.v1",
        "packet_type": "StrangleReceipt", "synthetic": True,
        "scope": "one declared actual-N4 synthetic mechanism control, not a governed design",
        "predicate_provenance": "recomputed",
        "owner": "N9PromotionEvidenceBridgeRepository",
        "legacy_path": "producer_disposition_without_synthetic_source_authority_resolution",
        "default_path": "source_provenance_recomputed_before_authority_projection",
        "default_flipped": flipped,
        "baseline": current, "removal": removed,
        "baseline_test_returncode": baseline_exit, "removal_test_returncode": removal_exit,
    }
    sys.stdout.write(
        json.dumps({**packet, "content_hash": gy_content_hash(packet)}, indent=2) + "\n",
    )
    return 0 if flipped and baseline_exit == 0 and removal_exit == 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
