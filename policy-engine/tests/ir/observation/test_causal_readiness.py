from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.ir.observation.causal_readiness import (
    CausalReadinessBundle,
    InterferenceReadinessEntry,
    ProxyIdentificationEntry,
    StrategicResponseEntry,
)
from polisyos.ir.observation.contracts import ObservationFamily, StrategicResponseChannel


def test_interference_readiness_rejects_empty_dotted_path_segments() -> None:
    with pytest.raises(
        ValidationError,
        match="predicted_metric_path must be a non-empty dotted path",
    ):
        InterferenceReadinessEntry(
            spec_id="spillover_procurement",
            family=ObservationFamily.PROCUREMENT_FLOWS,
            predicted_metric_path="metrics..procurement_spillover",
        )


def test_areal_interference_readiness_requires_structured_maup_flags() -> None:
    with pytest.raises(
        ValidationError,
        match="maup_scale_declared must be set when supports_areal_interference is true",
    ):
        InterferenceReadinessEntry(
            spec_id="spillover_procurement",
            family=ObservationFamily.PROCUREMENT_FLOWS,
            predicted_metric_path="metrics.procurement_spillover",
            supports_areal_interference=True,
        )


def test_causal_readiness_bundle_rejects_duplicate_proxy_rule() -> None:
    with pytest.raises(ValidationError, match="duplicate proxy_results"):
        CausalReadinessBundle(
            proxy_results=[
                ProxyIdentificationEntry(
                    family=ObservationFamily.PROCUREMENT_FLOWS,
                    proxy_variable="bid_proxy",
                    latent_variable="supplier_entry",
                    status="identified",
                ),
                ProxyIdentificationEntry(
                    family=ObservationFamily.PROCUREMENT_FLOWS,
                    proxy_variable="bid_proxy",
                    latent_variable="supplier_entry",
                    status="oracle_needed",
                ),
            ]
        )


def test_causal_readiness_bundle_rejects_duplicate_strategic_key() -> None:
    with pytest.raises(ValidationError, match="duplicate strategic_results"):
        CausalReadinessBundle(
            strategic_results=[
                StrategicResponseEntry(
                    channel=StrategicResponseChannel.PROCUREMENT_CHANNEL,
                    intervention_kind="threshold_change",
                    status="ready",
                ),
                StrategicResponseEntry(
                    channel=StrategicResponseChannel.PROCUREMENT_CHANNEL,
                    intervention_kind="threshold_change",
                    status="blocked",
                ),
            ]
        )
