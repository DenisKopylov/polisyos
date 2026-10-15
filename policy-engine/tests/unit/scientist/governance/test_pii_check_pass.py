from __future__ import annotations

import pytest

from polisyos.core.contracts.lex import IssueSeverity
from polisyos.core.governance.passes.base import PassContext
from polisyos.ir.connectors import PIIScanSummary
from polisyos.scientist.governance.passes.pii_check_pass import PIICheckPass
from polisyos.scientist.governance.profiles import ValidationProfile


def test_blocks_critical_pii_on_shared_tier() -> None:
    pass_ = PIICheckPass()
    ctx = PassContext(
        ir=None,
        state={
            "tenant_tier": "shared",
            "pii_scan_results": {
                "max_severity": "critical",
                "total_entities_found": 3,
                "entities_by_type": {"TAX_ID": 2, "SOCIAL_SECURITY": 1},
            },
        },
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_test",
    )

    issues = pass_.validate(ctx)
    blockers = [issue for issue in issues if issue.severity == IssueSeverity.BLOCKER]
    assert len(blockers) == 1
    assert blockers[0].code == "PII_CEILING_EXCEEDED"


def test_warns_when_within_ceiling() -> None:
    pass_ = PIICheckPass()
    ctx = PassContext(
        ir=None,
        state={
            "tenant_tier": "shared",
            "pii_scan_results": {
                "max_severity": "low",
                "total_entities_found": 4,
                "entities_by_type": {"PERSON": 4},
            },
        },
        registry_bundle=None,
        profile=ValidationProfile.mvp(),
        run_id="R_test",
    )

    issues = pass_.validate(ctx)
    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.WARNING
    assert issues[0].code == "PII_DETECTED_WITHIN_CEILING"


def test_allows_critical_on_sovereign() -> None:
    pass_ = PIICheckPass()
    ctx = PassContext(
        ir=None,
        state={
            "tenant_tier": "sovereign",
            "pii_scan_results": {
                "max_severity": "critical",
                "total_entities_found": 2,
                "entities_by_type": {"SOCIAL_SECURITY": 2},
            },
        },
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_test",
    )

    issues = pass_.validate(ctx)
    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.WARNING
    assert issues[0].code == "PII_DETECTED_WITHIN_CEILING"


def test_missing_scan_results_warns() -> None:
    pass_ = PIICheckPass()
    ctx = PassContext(
        ir=None,
        state={},
        registry_bundle=None,
        profile=ValidationProfile.mvp(),
        run_id="R_test",
    )

    issues = pass_.validate(ctx)
    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.WARNING
    assert issues[0].code == "PII_SCAN_MISSING"


@pytest.mark.parametrize(
    "summary",
    [
        {"max_severity": "critical"},
        {"max_severity": "critical", "total_entities_found": "not-a-count"},
        {"max_severity": "critical", "total_entities_found": -1},
        {
            "max_severity": "critical",
            "total_entities_found": 3,
            "entities_by_type": {"TAX_ID": "bad"},
        },
        {
            "max_severity": "critical",
            "total_entities_found": 3,
            "entities_by_severity": {"unknown": 3},
        },
        {"max_severity": "critical", "total_entities_found": 3, "unexpected": True},
        {"max_severity": "catastrophic", "total_entities_found": 3},
    ],
)
def test_invalid_supplied_scan_is_a_blocker(summary: dict[str, object]) -> None:
    context = PassContext(
        ir=None,
        state={"tenant_tier": "shared", "pii_scan_results": summary},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_test",
    )

    issues = PIICheckPass().validate(context)

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.BLOCKER
    assert issues[0].code == "PII_SCAN_INVALID"


def test_canonical_producer_summary_keeps_critical_downstream_blocker() -> None:
    summary = PIIScanSummary(
        max_severity="critical",
        total_entities_found=3,
        entities_by_type={"TAX_ID": 2, "SOCIAL_SECURITY": 1},
        entities_by_severity={"critical": 3},
    ).model_dump(mode="json")
    context = PassContext(
        ir=None,
        state={"tenant_tier": "shared", "pii_scan_results": summary},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_test",
    )

    issues = PIICheckPass().validate(context)

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.BLOCKER
    assert issues[0].code == "PII_CEILING_EXCEEDED"
