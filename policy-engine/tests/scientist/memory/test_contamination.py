from __future__ import annotations

import pytest

from polisyos.scientist.memory import (
    MemoryContaminationPolicy,
    assert_reusable_memory_clean,
    detect_memory_contamination,
)


def test_hidden_ref_suite_and_canary_tokens_are_blocked_from_reusable_memory() -> None:
    policy = MemoryContaminationPolicy(
        hidden_ref_ids={"hidden-artifact-123"},
        hidden_suite_ids={"hidden-suite-456"},
        canary_tokens={"CANARY_TOKEN_789"},
    )
    payload = {
        "summary": "Recovered failure card hidden-artifact-123.",
        "metadata": {"suite": "hidden-suite-456"},
        "notes": ["CANARY_TOKEN_789"],
    }

    findings = detect_memory_contamination(payload, policy=policy)

    assert {finding.token_kind for finding in findings} >= {
        "artifact_id",
        "suite_id",
        "canary",
    }
    with pytest.raises(ValueError, match="reusable memory contamination"):
        assert_reusable_memory_clean(payload, policy=policy)


def test_hidden_eval_metadata_keys_are_blocked() -> None:
    findings = detect_memory_contamination(
        {"metadata": {"hidden_holdout_answer": "do not reuse"}}
    )

    assert findings
    assert findings[0].token_kind == "metadata_key"
