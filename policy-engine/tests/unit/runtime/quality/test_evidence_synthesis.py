from __future__ import annotations

# ruff: noqa: S101
import pytest

from polisyos.runtime.quality.evidence_synthesis import (
    EvidenceSynthesisReportError,
    build_evidence_synthesis_report,
)


def test_synthesis_builder_requires_each_previous_wave_evidence_class() -> None:
    with pytest.raises(EvidenceSynthesisReportError) as raised:
        build_evidence_synthesis_report(
            report_id="report-wave-2",
            portfolio_id="portfolio-wave-2",
            claim_id="claim-a",
            multiverse_curve={
                "curve_id": "curve-wave-2",
                "specification_records": [
                    {"specification_id": "spec-a", "estimate": 0.1},
                ],
            },
            primary_synthesis_rule={"rule_id": "equal-weight", "weighting": "equal"},
            sensitivity_synthesis_rules=[
                {"rule_id": "sensitivity-equal", "weighting": "equal"},
            ],
            heterogeneity_model={},
            certainty_framework={},
            publication_bias_treatment={},
            inclusion_policy={},
            exclusion_policy={},
            information_saturation={},
            run_cost_proportionality={},
            previous_wave_refs={
                "portfolio_design_refs": ["portfolio-wave-2"],
                "evidence_line_refs": ["line-a"],
                "independence_map_refs": ["map-a"],
                "multiverse_curve_refs": ["curve-wave-2"],
            },
        )

    assert raised.value.code == "policy_design_synthesis_previous_wave_refs_missing"
    assert raised.value.field == "previous_wave_refs.disconfirming_ledger_refs"
