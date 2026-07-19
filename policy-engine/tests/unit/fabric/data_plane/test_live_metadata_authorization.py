from __future__ import annotations

import pytest

from polisyos.fabric.connectors.profiles.models import SourceProfile
from polisyos.fabric.data_plane import (
    LiveMetadataHarnessReceipt,
    build_live_metadata_execution_authorization,
    content_sha256,
)


def _profile() -> SourceProfile:
    return SourceProfile(
        profile_id="worldbank_wdi",
        display_name="World Bank WDI",
        description="fixture",
        connector_family="worldbank",
        base_url="https://api.worldbank.org/v2",
        auth_policy="none",
        timeout_seconds=30,
        rate_limit_rps=10.0,
        max_concurrency=1,
    )


def _harness() -> LiveMetadataHarnessReceipt:
    values: dict[str, object] = {
        "schema_version": "polisyos.fabric.live_metadata_harness_receipt.v1",
        "attempt_id": "gy-n13b-worldbank-wdi-government-balance-usd-metadata-001",
        "connector_id": "worldbank.wdi",
        "profile_id": "worldbank_wdi",
        "request_variable": "GC.BAL.CASH.CD",
        "call_class": "indicator_metadata",
        "endpoint_url": "https://api.worldbank.org/v2/indicator/GC.BAL.CASH.CD",
        "params": {"format": "json", "page": "1", "per_page": "1"},
        "simulator_mode": "replay",
        "simulator_call_count": 1,
        "transport_intercepted": True,
        "network_escape_attempt_count": 0,
        "actual_network_call_count": 0,
        "outcome": "replay_fixture_missing_after_interception",
        "safe_dry_run_passed": True,
    }
    return LiveMetadataHarnessReceipt(
        **values,
        receipt_sha256=content_sha256(values),
    )


def test_metadata_authorization_is_exact_call_class_and_latency_derived() -> None:
    request = {
        "variable_id": "GC.BAL.CASH.CD",
        "request_variables": ["GC.BAL.CASH.CD"],
        "connector_id": "worldbank.wdi",
        "profile_id": "worldbank_wdi",
        "call_class": "indicator_metadata",
        "schema_contract": {"envelope": "worldbank_v2_indicator_metadata"},
    }
    authorization = build_live_metadata_execution_authorization(
        request=request,
        schema_contract=request["schema_contract"],
        source_profile=_profile(),
        baseline_sha256="sha256:" + "1" * 64,
        harness_receipt=_harness(),
        paid_success_elapsed_seconds=6.945391583998571,
        timeout_multiplier=2,
        heartbeat_cap_seconds=3.0,
        max_response_bytes=16_384,
        max_decompressed_bytes=16_384,
    )

    assert authorization.call_class == "indicator_metadata"
    assert authorization.request_variable == "GC.BAL.CASH.CD"
    assert authorization.budget.timeout_cap_seconds == 14.0
    assert authorization.budget.timeout_seconds == 14.0
    assert authorization.budget.call_budget == authorization.budget.variable_budget == 1
    assert authorization.authorized is True


def test_data_fetch_receipt_shape_cannot_authorize_metadata() -> None:
    request = {
        "variable_id": "GC.BAL.CASH.CD",
        "request_variables": ["GC.BAL.CASH.CD"],
        "connector_id": "worldbank.wdi",
        "profile_id": "worldbank_wdi",
        "call_class": "data_fetch",
        "schema_contract": {"envelope": "worldbank_v2_indicator_metadata"},
    }

    with pytest.raises(Exception, match="metadata"):
        build_live_metadata_execution_authorization(
            request=request,
            schema_contract=request["schema_contract"],
            source_profile=_profile(),
            baseline_sha256="sha256:" + "1" * 64,
            harness_receipt=_harness(),
            paid_success_elapsed_seconds=6.945391583998571,
            timeout_multiplier=2,
            heartbeat_cap_seconds=3.0,
            max_response_bytes=16_384,
            max_decompressed_bytes=16_384,
        )


def test_metadata_harness_receipt_recomputes_safe_dry_run_and_identity() -> None:
    harness = _harness()

    for update in (
        {"safe_dry_run_passed": False},
        {"transport_intercepted": False},
        {"receipt_sha256": "sha256:" + "0" * 64},
    ):
        with pytest.raises(ValueError):
            LiveMetadataHarnessReceipt.model_validate(
                harness.model_copy(update=update).model_dump(mode="python")
            )
