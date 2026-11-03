"""Live acquisition reopens the exact cache owner's selected write profile."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from polisyos.core import artifacts
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.fabric.connectors import resolve_connection_config
from polisyos.fabric.connectors.cache import verify_selected_cache_payload_ref
from polisyos.fabric.connectors.cache._store_core import (
    _direct_cache_payload_write_options,
)
from polisyos.fabric.connectors.cache._store_models import _SOURCE_INTENT_KIND
from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry
from polisyos.ir.connectors import FetchRequest
from tests._helpers.lane01_wdi_profiles import GDP_PROFILE
from tests.unit.runtime.quality.test_lane01_candidate_provenance import _fixture


def test_live_cache_profile_rejects_foreign_payload_and_source_intent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Real Fabric output cannot swap either same-byte selected manifest."""
    case = _fixture(tmp_path, monkeypatch, GDP_PROFILE)
    try:
        proof = case.evidence
        snapshot = artifacts.validate_core_model_json_artifact(
            DataSnapshot, case.store, proof.data_snapshot_ref
        )
        ref = snapshot.data_ref
        profile = SourceProfileRegistry.get_instance().get("worldbank_wdi")
        assert profile is not None
        config = replace(
            resolve_connection_config(profile),
            timeout_seconds=max(1, int(proof.authorization.budget.timeout_seconds)),
            max_retries=1,
            max_connections=1,
        )
        request = FetchRequest(
            dataset_id=GDP_PROFILE.indicator_id,
            filters=(("country", (GDP_PROFILE.country_code,)),),
            date_start=datetime(GDP_PROFILE.year, 1, 1, tzinfo=UTC),
            date_end=datetime(GDP_PROFILE.year, 12, 31, tzinfo=UTC),
            include_metadata=True,
            include_schema=True,
            retryable=False,
            page_size=1000,
        )
        kwargs = {
            "connector_id": "worldbank.wdi",
            "request": request,
            "source_config": config,
        }
        assert verify_selected_cache_payload_ref(case.store, ref, **kwargs)
        assert verify_selected_cache_payload_ref(
            case.store, ref, **kwargs, require_writer_profile=True, classification="public"
        )
        manifest = case.store.get_manifest(ref)
        foreign_payload = case.store.put_bytes(
            case.store.get_bytes(ref),
            artifacts.ArtifactWriteOptions(
                kind=ref.kind,
                media_type=ref.media_type,
                schema=manifest.artifact_schema,
                inputs=manifest.inputs,
                canon=manifest.canon,
                governance=manifest.governance,
                producer=artifacts.ProducerInfo(component="fixture.foreign", version="1"),
            ),
            return_selected_profile=True,
        )
        assert foreign_payload.artifact_id == ref.artifact_id
        assert foreign_payload.manifest_profile_sha256 != ref.manifest_profile_sha256
        assert verify_selected_cache_payload_ref(case.store, foreign_payload, **kwargs)
        assert not verify_selected_cache_payload_ref(
            case.store,
            foreign_payload,
            **kwargs,
            require_writer_profile=True,
            classification="public",
        )

        (edge,) = manifest.inputs
        intent_ref = artifacts.ArtifactRef(
            artifact_id=edge.artifact_id,
            kind=_SOURCE_INTENT_KIND,
            media_type="application/json",
            manifest_profile_sha256=edge.manifest_profile_sha256,
        )
        intent_manifest = case.store.get_manifest(intent_ref)
        foreign_intent = case.store.put_bytes(
            case.store.get_bytes(intent_ref),
            artifacts.ArtifactWriteOptions(
                kind=intent_ref.kind,
                media_type=intent_ref.media_type,
                schema=intent_manifest.artifact_schema,
                inputs=intent_manifest.inputs,
                canon=intent_manifest.canon,
                governance=intent_manifest.governance,
                producer=artifacts.ProducerInfo(component="fixture.foreign", version="1"),
            ),
            return_selected_profile=True,
        )
        rebound_payload = case.store.put_bytes(
            case.store.get_bytes(ref),
            _direct_cache_payload_write_options(
                media_type=ref.media_type,
                source_intent_ref=foreign_intent,
                execution_inputs=[],
                governance=manifest.governance,
            ),
            return_selected_profile=True,
        )
        assert verify_selected_cache_payload_ref(case.store, rebound_payload, **kwargs)
        assert not verify_selected_cache_payload_ref(
            case.store,
            rebound_payload,
            **kwargs,
            require_writer_profile=True,
            classification="public",
        )
    finally:
        case.overlay.close()
