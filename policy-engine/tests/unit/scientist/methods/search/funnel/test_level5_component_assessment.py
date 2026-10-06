"""Declared challenge components remain substantive at the actual L5 consumer."""

from pathlib import Path
from runpy import run_path

import pytest

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.scientist.methods.doe.stress_report import StressTestReport
from polisyos.scientist.methods.search.funnel.level5_refutation_governance import (
    Level5RefutationGovernanceStage,
)
from polisyos.scientist.methods.search.uncertainty import UncertaintyType
from polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime import (
    _merge_stress_test_reports,
    _recompute_stress_test_report,
)

_producer = run_path(
    str(Path(__file__).parents[3] / "search" / "test_challenge_scenario_projection.py")
)


@pytest.mark.parametrize("component", ["complete", "empty", "unknown"])
def test_actual_case_components_keep_conditional_fraction_at_level5(tmp_path, component):
    store_path = tmp_path / "cas"
    store = FileSystemCAS(store_path)
    complete = _producer["_suite"](
        store, [_producer["_case"](index, True) for index in range(4)]
    ).stress_test_report
    other_cases = (
        [_producer["_case"](10, True)]
        if component == "complete"
        else [_producer["_case"](10, False, status="error")]
        if component == "unknown"
        else []
    )
    other = _producer["_suite"](store, other_cases).stress_test_report
    other.metadata["challenge_suite_id"] = "declared-additional-suite"
    report = _recompute_stress_test_report(_merge_stress_test_reports(complete, [other]))
    ref = store.put_json(
        report,
        PutOptions(kind="scientist.stress_test_report", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    restored = StressTestReport.model_validate(
        from_canonical_bytes(FileSystemCAS(store_path).get_bytes(ref))
    )
    result = Level5RefutationGovernanceStage(require_hidden_holdout=False).evaluate(
        {"candidate_id": "candidate-1"}, {"stress_test_report": restored}
    )
    expected = "complete" if component == "complete" else "partial"
    assessment = result.feedback["stress_observed_sample_assessment"]
    assert restored.set_adequacy_status == assessment["status"] == expected
    assert assessment["observed_fraction"] == restored.robustness_score == 1
    assert assessment["population_probability"] == "not_established"
    assert result.feedback["stress_robust"] is (True if expected == "complete" else None)
    assert result.is_promising
    assert any(
        card.failure_type == "stress_observed_sample_incomplete" for card in result.failure_cards
    ) is (expected == "partial")
    assert result.uncertainty_envelope.uncertainties[UncertaintyType.MODEL].level == 1
