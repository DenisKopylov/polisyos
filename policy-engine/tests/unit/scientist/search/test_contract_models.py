from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.ir import FailureSeverity, TypedFailureCard
from polisyos.ir import UncertaintyType as IRUncertaintyType
from polisyos.ir.registry.refs import ArtifactRefModel
from polisyos.scientist.methods.search.funnel.types import (
    TypedFailureCard as ReexportedTypedFailureCard,
)
from polisyos.scientist.methods.search.funnel.types import (
    UncertaintyEnvelope as ReexportedUncertaintyEnvelope,
)
from polisyos.scientist.methods.search.funnel.types import (
    UncertaintyType as ReexportedUncertaintyType,
)
from polisyos.scientist.methods.search.uncertainty import (
    UncertaintyEnvelope,
    UncertaintyEstimate,
    UncertaintyType,
)


def test_uncertainty_envelope_requires_all_types() -> None:
    with pytest.raises(ValidationError):
        UncertaintyEnvelope(
            uncertainties={
                UncertaintyType.STATISTICAL: UncertaintyEstimate(
                    level=0.2,
                    source="bootstrap",
                    quantification_method="bootstrap_ci",
                    is_reducible=True,
                )
            }
        )


def test_uncertainty_envelope_rejects_invalid_level() -> None:
    with pytest.raises(ValidationError):
        UncertaintyEstimate(
            level=1.5,
            source="bad",
            quantification_method="heuristic",
            is_reducible=True,
        )


def test_uncertainty_envelope_from_partial_fills_missing_types() -> None:
    envelope = UncertaintyEnvelope.from_partial(
        {
            UncertaintyType.STATISTICAL: UncertaintyEstimate(
                level=0.2,
                source="bootstrap",
                quantification_method="bootstrap_ci",
                is_reducible=True,
            )
        }
    )
    assert len(envelope.uncertainties) == len(UncertaintyType)
    assert envelope.uncertainties[UncertaintyType.STATISTICAL].level == 0.2
    assert envelope.uncertainties[UncertaintyType.STRUCTURAL].level == 1.0


def test_uncertainty_envelope_merge_max_prefers_higher_uncertainty() -> None:
    low = UncertaintyEnvelope.from_partial(
        {
            UncertaintyType.MODEL: UncertaintyEstimate(
                level=0.2,
                source="low",
                quantification_method="m1",
                is_reducible=True,
            )
        }
    )
    high = UncertaintyEnvelope.from_partial(
        {
            UncertaintyType.MODEL: UncertaintyEstimate(
                level=0.9,
                source="high",
                quantification_method="m2",
                is_reducible=False,
            )
        }
    )

    merged = UncertaintyEnvelope.merge_max([low, high])
    assert merged.uncertainties[UncertaintyType.MODEL].level == 0.9
    assert merged.uncertainties[UncertaintyType.MODEL].source == "high"


def test_failure_card_preserves_literal_pre_move_wire_payload() -> None:
    payload = {
        "judge_name": "judge",
        "failure_type": "timeout",
        "severity": "warning",
        "description": "Timed out",
        "uncertainty_type": "measurement",
        "remediation_hint": "Retry with a longer budget",
        "evidence_ref": {
            "artifact_id": (
                "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            ),
            "kind": "scientist.test",
            "media_type": "application/json",
        },
        "metric_name": "elapsed_seconds",
        "observed_value": 31.0,
        "threshold_value": 30.0,
        "threshold_direction": "max",
        "metadata": {"attempt": 2},
    }

    restored = TypedFailureCard.model_validate(payload)

    assert type(restored) is TypedFailureCard
    assert restored.severity is FailureSeverity.WARNING
    assert restored.evidence_ref is not None
    assert type(restored.evidence_ref) is ArtifactRefModel
    assert restored.model_dump(mode="json") == payload


def test_failure_card_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        TypedFailureCard(
            judge_name="judge",
            failure_type="timeout",
            severity=FailureSeverity.WARNING,
            description="Timed out",
            unsupported_authority=True,
        )


def test_funnel_types_reexport_search_contracts() -> None:
    assert ReexportedUncertaintyEnvelope is UncertaintyEnvelope
    assert UncertaintyType is IRUncertaintyType
    assert ReexportedUncertaintyType is UncertaintyType
    assert ReexportedTypedFailureCard is TypedFailureCard
