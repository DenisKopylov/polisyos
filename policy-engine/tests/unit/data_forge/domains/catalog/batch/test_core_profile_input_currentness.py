from __future__ import annotations

import asyncio
import json
from dataclasses import replace

from polisyos.data_forge.domains.catalog.batch import core_sources_ingest as core_ingest
from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
from polisyos.data_forge.domains.catalog.batch.core_sources import (
    api as core_api,
)
from polisyos.data_forge.domains.catalog.batch.core_sources import validators, writers
from polisyos.data_forge.domains.catalog.batch.core_sources_ingest import (
    ObservationPlan,
)


def _shard(shard_id: str, profile_id: str) -> core_ingest.ObservationShard:
    plan = ObservationPlan(
        dataset_id="source-dataset",
        source="worldbank",
        raw_variable="NY.GDP.PCAP.CD",
        canonical_var="income",
        connector_id="worldbank.api",
        profile_id=profile_id,
        request_dataset_id="NY.GDP.PCAP.CD",
        default_filters={"unit": ["usd"]},
        update_frequency="annual",
    )
    return core_ingest.ObservationShard(
        shard_id=shard_id,
        plan=plan,
        country_code="UA",
        start_year=2022,
        end_year=2022,
        filters={"unit": ["usd"]},
    )


def test_unknown_profile_basis_invalidates_all_checkpoint_reuse(tmp_path, monkeypatch) -> None:
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap")
    config.resume = True
    config.resume_mode = "smart"
    config.observation_ingest_checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    prior = {
        "completed": {"shard-a": {"status": "complete_with_rows"}},
        "failed": {"shard-b": {"status": "failed"}},
        "deferred": {"shard-c": {"status": "deferred"}},
        "unsupported_signatures": {"unsupported": {"cached": True}},
        "empty_signatures": {"empty": {"cached": True}},
        "inflight_leases": {"lease": {"pending": True}},
        "async_fetch_leases": {"async": {"job_id": "old-profile-job"}},
        "capability_snapshots": {"profile:dataset": {"resolved_dataset_id": "dataset"}},
        "capability_failures": {"profile:dataset": {"status": 401}},
        "source_budgets": {"profile": {"remaining": 3}},
        "writer_state": {"flush_count": 4},
        "support_sketches": {"sketch": {"source": "worldbank"}},
        "work_packages": {"shard-a": {"shard_id": "shard-a", "phase": "publishable_core"}},
        "planner_phase": "publishable_core",
        "publishable_core_complete": True,
        "negative_cache_version": 2,
        "planner_signature": "unchanged-run-signature",
        "core_output_receipt": None,
        "core_profile_input_currentness": "not_established",
        "core_profile_input_coverage": {"profile-a": "excluded_present"},
    }
    config.observation_ingest_checkpoint_path.write_text(json.dumps(prior), encoding="utf-8")
    monkeypatch.setattr(
        validators,
        "_runtime_profile_input_snapshot",
        lambda: ("not_established", {"profile-a": "excluded_present"}),
    )

    validators._prepare_core_output_resume(config)

    saved = json.loads(config.observation_ingest_checkpoint_path.read_text(encoding="utf-8"))
    cache_fields = (
        "completed",
        "failed",
        "deferred",
        "unsupported_signatures",
        "empty_signatures",
        "inflight_leases",
        "async_fetch_leases",
        "capability_snapshots",
        "capability_failures",
        "support_sketches",
        "work_packages",
    )
    assert all(saved[name] == {} for name in cache_fields)
    assert saved["planner_signature"] == ""
    assert saved["publishable_core_complete"] is False
    assert saved["core_output_receipt"] is None
    assert saved["core_profile_input_currentness"] == "not_established"
    assert saved["core_profile_input_coverage"] == {"profile-a": "excluded_present"}
    assert saved["source_budgets"] == prior["source_budgets"]
    assert saved["writer_state"] == prior["writer_state"]

    shard = _shard("shard-a", "profile-a")
    assert not validators._shard_completed(
        config,
        shard,
        completed=prior["completed"],
        failed=prior["failed"],
        deferred=prior["deferred"],
        profile_input_currentness="not_established",
    )
    assert validators._shard_completed(
        config,
        shard,
        completed=prior["completed"],
        failed=prior["failed"],
        deferred=prior["deferred"],
        profile_input_currentness="established",
    )


def test_established_profile_basis_preserves_independent_caches_without_receipt(
    tmp_path, monkeypatch
) -> None:
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap")
    config.resume = True
    config.resume_mode = "smart"
    basis_identity = config.run_signature
    coverage = {"profile-a": "none"}
    config.observation_ingest_checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    prior = {
        "completed": {"shard-a": {"status": "complete_with_rows"}},
        "failed": {},
        "deferred": {},
        "unsupported_signatures": {"unsupported": {"cached": True}},
        "empty_signatures": {"empty": {"cached": True}},
        "inflight_leases": {"lease": {"pending": True}},
        "async_fetch_leases": {"async": {"job_id": "same-basis-job"}},
        "capability_snapshots": {"profile:dataset": {"resolved_dataset_id": "dataset"}},
        "capability_failures": {"profile:dataset": {"status": 401}},
        "source_budgets": {"profile": {"remaining": 3}},
        "writer_state": {"flush_count": 4},
        "support_sketches": {"sketch": {"source": "worldbank"}},
        "work_packages": {"shard-a": {"shard_id": "shard-a", "phase": "publishable_core"}},
        "planner_phase": "publishable_core",
        "publishable_core_complete": True,
        "negative_cache_version": 2,
        "planner_signature": "current-basis-signature",
        "core_output_receipt": None,
        "core_profile_input_basis_identity": basis_identity,
        "core_profile_input_currentness": "established",
        "core_profile_input_coverage": coverage,
    }
    config.observation_ingest_checkpoint_path.write_text(json.dumps(prior), encoding="utf-8")
    monkeypatch.setattr(
        validators, "_runtime_profile_input_snapshot", lambda: ("established", coverage)
    )

    validators._prepare_core_output_resume(config)

    saved = json.loads(config.observation_ingest_checkpoint_path.read_text(encoding="utf-8"))
    assert saved["completed"] == {}
    assert saved["unsupported_signatures"] == prior["unsupported_signatures"]
    assert saved["empty_signatures"] == prior["empty_signatures"]
    assert saved["inflight_leases"] == prior["inflight_leases"]
    assert saved["async_fetch_leases"] == prior["async_fetch_leases"]
    assert saved["capability_snapshots"] == prior["capability_snapshots"]
    assert saved["capability_failures"] == prior["capability_failures"]
    assert saved["source_budgets"] == prior["source_budgets"]
    assert saved["writer_state"] == prior["writer_state"]
    assert saved["support_sketches"] == {}
    assert saved["work_packages"] == {}
    assert saved["core_profile_input_basis_identity"] == basis_identity
    assert saved["core_profile_input_currentness"] == "established"


def test_core_output_receipt_currentness_requires_established_profile_basis() -> None:
    receipt = {
        "profile_input_currentness": "not_established",
        "profile_input_basis_identity": "run-basis-a",
        "profile_input_coverage": {"profile-a": "excluded_present"},
        "basis_digest": "matching-output-marker",
    }
    state = validators._CurrentCoreOutputReceiptState(
        expected=True,
        current_receipt=receipt,
        checkpoint_state={"core_output_receipt": receipt},
        core_stage_state={},
        stage_metadata={"core_output_receipt": receipt},
        live_profile_input_currentness="not_established",
        live_profile_input_coverage={"profile-a": "excluded_present"},
        live_profile_input_basis_identity="run-basis-a",
    )
    assert not state.is_current
    assert state.reconciled_receipt is None

    established_receipt = {
        **receipt,
        "profile_input_currentness": "established",
        "profile_input_coverage": {"profile-a": "none"},
    }
    established = validators._CurrentCoreOutputReceiptState(
        expected=True,
        current_receipt=established_receipt,
        checkpoint_state={"core_output_receipt": established_receipt},
        core_stage_state={},
        stage_metadata={"core_output_receipt": established_receipt},
        live_profile_input_currentness="established",
        live_profile_input_coverage={"profile-a": "none"},
        live_profile_input_basis_identity="run-basis-a",
    )
    assert established.is_current
    assert not replace(
        established,
        live_profile_input_basis_identity="run-basis-b",
    ).is_current


def test_observation_fetch_deduper_scopes_requests_by_profile_and_input_basis(
    tmp_path, monkeypatch
) -> None:
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap")
    producer_calls: list[str] = []

    async def fake_invoke(shard, *_args, **_kwargs):
        producer_calls.append(shard.shard_id)
        await asyncio.sleep(0.01)
        return [{"origin": shard.shard_id}]

    monkeypatch.setattr(core_api, "_invoke_fetch_observation_rows", fake_invoke)

    async def fetch(shard, *, basis: str, deduper):
        return await core_api._fetch_observation_rows_with_retries(
            shard,
            cache=None,
            config=config,
            policy=None,
            fetch_deduper=deduper,
            budget_windows={},
            state_lock=asyncio.Lock(),
            input_basis_identity=basis,
        )

    async def run():
        deduper = writers._ObservationFetchDeduper()
        return await asyncio.gather(
            fetch(_shard("same-a", "profile-a"), basis="basis-a", deduper=deduper),
            fetch(_shard("same-b", "profile-a"), basis="basis-a", deduper=deduper),
            fetch(_shard("other-profile", "profile-b"), basis="basis-a", deduper=deduper),
            fetch(_shard("changed-basis", "profile-a"), basis="basis-b", deduper=deduper),
        )

    results = asyncio.run(run())

    assert len(producer_calls) == 3
    assert results[0] == results[1]
    assert results[0] != results[2]
    assert results[0] != results[3]
