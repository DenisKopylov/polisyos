from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.search.failure_cards import TypedFailureCard
from polisyos.scientist.search.funnel.types import (
    TypedFailureCard as ReexportedTypedFailureCard,
)
from polisyos.scientist.search.funnel.types import (
    UncertaintyEnvelope as ReexportedUncertaintyEnvelope,
)
from polisyos.scientist.search.funnel.types import (
    UncertaintyType as ReexportedUncertaintyType,
)
from polisyos.scientist.search.uncertainty import (
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


def test_failure_card_accepts_artifact_ref() -> None:
    ref = ArtifactRef(
        artifact_id=ArtifactID.from_sha256_hex("a" * 64),
        kind="scientist.test",
        media_type="application/json",
    )
    card = TypedFailureCard(
        judge_name="judge",
        failure_type="timeout",
        severity="warning",
        description="Timed out",
        evidence_ref=ref,
    )
    assert str(card.evidence_ref.artifact_id) == f"sha256:{'a' * 64}"


def test_funnel_types_reexport_search_contracts() -> None:
    assert ReexportedUncertaintyEnvelope is UncertaintyEnvelope
    assert ReexportedUncertaintyType is UncertaintyType
    assert ReexportedTypedFailureCard is TypedFailureCard
