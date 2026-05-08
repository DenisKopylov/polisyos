from __future__ import annotations

import json
from pathlib import Path

import pytest

from polisyos.data_forge.read_api.catalog import (
    load_catalog_readiness_package,
    load_catalog_shadow_bundle,
)
from polisyos.fabric.connectors.contracts import load_source_contracts
from _helpers.runtime_http import build_runtime_api_env
from tools.quality.validation import fabric_source_contracts

pytestmark = pytest.mark.integration

TESTS_ROOT = Path(__file__).resolve().parents[2]
CATALOG_FIXTURE_ROOT = TESTS_ROOT / "_data" / "data_forge" / "non_lex_split" / "catalog"
REPLAY_FIXTURE = (
    TESTS_ROOT / "_data" / "fabric" / "shared" / "source_contracts" / "worldbank.wdi.generic.replay.json"
)


def test_data_forge_catalog_fixture_source_contract_reaches_runtime_api(tmp_path) -> None:
    bundle = load_catalog_shadow_bundle(CATALOG_FIXTURE_ROOT)
    readiness = load_catalog_readiness_package(CATALOG_FIXTURE_ROOT)
    replay = json.loads(REPLAY_FIXTURE.read_text())
    contracts = load_source_contracts(
        json.loads(fabric_source_contracts.source_contract_snapshot_json())
    )
    contract = next(item for item in contracts if item.id == replay["source_contract_id"])

    assert readiness.consumer_ready is True
    assert bundle.source_by_id("worldbank").observation_count >= 1
    assert contract.source.connector_id == replay["connector_id"]
    assert contract.source.profile_id == replay["profile_id"]
    assert contract.replay.fixture_ref.endswith("worldbank.wdi.generic.replay.json")

    env = build_runtime_api_env(tmp_path, include_test_client=True)
    try:
        client = env["client"]
        scorecards_response = client.get("/api/v1/fabric/source-scorecards")
        assert scorecards_response.status_code == 200
        scorecards = scorecards_response.json()["scorecards"]
        assert contract.id in scorecards
        assert scorecards[contract.id]["source_contract_id"] == contract.id

        impact_response = client.post(
            "/api/v1/fabric/impact",
            json={
                "run_id": env["core_run_id"],
                "source_contract_ids": [contract.id],
            },
        )
        assert impact_response.status_code == 200
        impacts = {row["subject_id"]: row for row in impact_response.json()["impacts"]}
        assert contract.id in impacts
        assert impacts[contract.id]["lineage_status"] == "verified"
        assert impacts[contract.id]["affected_decision_data_ids"]
    finally:
        client_close = getattr(env.get("client"), "close", None)
        if callable(client_close):
            client_close()
        service_close = getattr(
            getattr(env["app"].state, "_control_service", None),
            "close",
            None,
        )
        if callable(service_close):
            service_close()
