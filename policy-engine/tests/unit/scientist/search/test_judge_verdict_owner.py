"""The judge verdict's exact owner profile must survive producer and reader."""

from __future__ import annotations

import pytest

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts import FileSystemCAS, PutOptions, SchemaInfo
from polisyos.scientist.governance.report import GovernanceReport
from polisyos.scientist.methods.search.judge_stack import (
    JudgeInputBundle,
    JudgeStack,
    JudgeVerdict,
    load_candidate_judge_verdict,
    load_judge_verdict,
    persist_candidate_judge_verdict,
    persist_judge_verdict,
)
from polisyos.scientist.methods.search.judge_thresholds import JudgeThresholdRegistry
from tests.unit.scientist.search.test_phase_b_policy_runtime import _candidate


@pytest.mark.parametrize("foreign", ["kind", "media", "schema"])
def test_real_six_judge_verdict_requires_selected_owner_profile(tmp_path, foreign: str) -> None:
    """Same verdict bytes in another owner occurrence cannot become this result."""
    registry = JudgeThresholdRegistry(root=tmp_path / "thresholds")
    registry.record(registry.snapshot().entries[0])
    store = FileSystemCAS(tmp_path / "cas")
    verdict = JudgeStack(
        threshold_registry=registry.frozen_view(), store=store
    ).evaluate_phase5_preflight(
        JudgeInputBundle(
            candidate=_candidate(),
            governance_report=GovernanceReport(verdict="human_gate"),
            run_id="synthetic-judge-owner",
        )
    )
    assert len(verdict.per_judge) == 6
    assert verdict.composite_decision == "defer_to_human"
    selected = persist_judge_verdict(store, verdict, return_selected_profile=True)
    assert selected.manifest_profile_sha256 is not None
    assert load_judge_verdict(store, selected).model_dump(mode="json") == verdict.model_dump(
        mode="json"
    )
    legacy = selected.model_copy(update={"manifest_profile_sha256": None})
    assert load_judge_verdict(store, legacy).model_dump(mode="json") == verdict.model_dump(
        mode="json"
    )
    original = store.get_manifest(selected)
    counterfeit = store.put_bytes(
        store.get_bytes(selected),
        PutOptions(
            kind="test.foreign_judge" if foreign == "kind" else original.kind,
            media_type="text/plain" if foreign == "media" else original.media_type,
            schema=(
                SchemaInfo(name="test.ForeignJudge", version="1.0")
                if foreign == "schema"
                else original.artifact_schema
            ),
            canon=original.canon,
        ),
        return_selected_profile=True,
    )
    assert counterfeit.artifact_id == selected.artifact_id
    assert counterfeit.manifest_profile_sha256 != selected.manifest_profile_sha256
    with pytest.raises(CanonicalProfileRefusalError):
        load_judge_verdict(store, counterfeit)


def test_candidate_judge_result_cannot_be_read_as_the_ordinary_verdict_kind(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    verdict = JudgeVerdict(per_judge={}, composite_decision="promote")
    ordinary = persist_judge_verdict(store, verdict, return_selected_profile=True)
    candidate = persist_candidate_judge_verdict(store, verdict)
    assert candidate.artifact_id == ordinary.artifact_id
    assert candidate.manifest_profile_sha256 != ordinary.manifest_profile_sha256
    assert load_candidate_judge_verdict(store, candidate) == verdict
    with pytest.raises(CanonicalProfileRefusalError):
        load_judge_verdict(store, candidate)
    with pytest.raises(ValueError, match="candidate_judge_verdict_profile_not_established"):
        load_candidate_judge_verdict(
            store, candidate.model_copy(update={"manifest_profile_sha256": None})
        )
