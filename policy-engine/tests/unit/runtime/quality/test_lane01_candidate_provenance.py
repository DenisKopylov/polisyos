"""Acquisition provenance remains distinct from fixture observation authority."""

from __future__ import annotations

import json
import socket
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar

import aiohttp
import duckdb
import pytest
from pydantic import ValidationError

from polisyos.core import artifacts, contracts
from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
    DEFAULT_ACQUISITION_AUTHORITY_REGISTRY,
    AcquisitionAuthorityError,
    AcquisitionAuthorityRegistry,
    build_authority_entry,
)
from polisyos.data_forge.domains.catalog.knowledge.overlay import (
    ObservationProvenanceClass,
    OverlayAdmissionError,
)
from polisyos.runtime.quality import acquisition_executor, semantic_epoch
from tests._helpers import lane01_wdi_profiles
from tests._helpers.acquisition_epoch_production import production_admission_inputs
from tests._helpers.lane01_wdi_profiles import (
    GDP_PROFILE,
    UNEMPLOYMENT_PROFILE,
    CandidateWDIProfile,
    fixture_wdi_response,
)
from tests._helpers.semantic_epoch_native import _build_acquisition_epoch_fixture_service


def _fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    profile: CandidateWDIProfile,
    *,
    omit_provenance: bool = False,
    override_class: str | None = None,
    entry_description: tuple[str, str] | None = None,
    proxy: bool = False,
    seed_sibling: bool = False,
) -> SimpleNamespace:
    """Run the Fabric fetch against fixture bytes and prepare its exact scope.

    The epoch service has only the catalog fixture boundary; it does not prove
    a production L5, chronology, publication, or external data admission.
    """

    def entry_builder(**values: object):
        if omit_provenance:
            values.pop("source_provenance_class", None)
        elif override_class is not None:
            values["source_provenance_class"] = override_class
        if entry_description is not None:
            values["title"], values["description"] = entry_description
        if proxy:
            values["is_proxy"] = True
            values["proxy_penalty"] = 0.1
        return build_authority_entry(**values)

    with monkeypatch.context() as local:
        local.setattr(lane01_wdi_profiles, "build_authority_entry", entry_builder)
        authority, entry = lane01_wdi_profiles.build_fixture_wdi_authority(
            tmp_path / "repo", profile
        )
    body = fixture_wdi_response(profile)

    class Response:
        status = 200
        headers: ClassVar[dict[str, str]] = {"content-type": "application/json"}

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: object) -> None:
            del args

        async def read(self) -> bytes:
            return body

        def release(self) -> None:
            pass

        async def wait_for_close(self) -> None:
            pass

        def close(self) -> None:
            pass

    async def intercept(_session: object, method: str, url: object, **kwargs: object):
        assert method == "GET"
        assert str(url).endswith(
            f"/country/{profile.country_code}/indicator/{profile.indicator_id}"
        )
        assert isinstance(kwargs["params"], Mapping)
        return Response()

    def forbid_socket(*args: object, **kwargs: object) -> None:
        del args, kwargs
        pytest.fail("fixture transport attempted a network socket")

    store = artifacts.FileSystemCAS(tmp_path / "cas")
    if seed_sibling:
        store.put_bytes(
            body,
            artifacts.PutOptions(
                kind="fabric.acquisition.raw_evidence",
                media_type="application/json",
                producer=artifacts.ProducerInfo(component="fixture.other-producer", version="1"),
            ),
        )
    constraints = acquisition_executor.LiveCatalogExecutionConstraints(
        country_code=profile.country_code,
        start_year=profile.year,
        end_year=profile.year,
        page_size=1000,
        max_response_bytes=65_536,
        max_decompressed_bytes=65_536,
        timeout_cap_seconds=15.0,
        heartbeat_cap_seconds=5.0,
    )
    with monkeypatch.context() as local:
        local.setattr(aiohttp.ClientSession, "_request", intercept)
        local.setattr(socket.socket, "connect", forbid_socket)
        local.setattr(socket.socket, "connect_ex", forbid_socket)
        evidence = acquisition_executor.execute_live_catalog_acquisition(
            authority=authority,
            entry_id=entry.entry_id,
            attempt_id="lane01-fixture-wdi-001",
            constraints=constraints,
            journal_path=tmp_path / "journal.jsonl",
            cas_root=tmp_path / "cas",
            artifact_store=store,
        )

    service, overlay, _ = _build_acquisition_epoch_fixture_service(
        store=store, authority=authority, root=tmp_path / "epoch"
    )
    scope = semantic_epoch.build_epoch_scope_identity(
        schema_profile="polisyos.epoch.policy-scope.v1",
        identity_bytes=contracts.epoch.canonical_epoch_bytes(
            {
                "domain": profile.construct.partition(".")[0],
                "jurisdiction": profile.country_code,
                "year": profile.year,
                "population": profile.population,
            }
        ),
    )

    def coordinate(kind: str, value: bytes) -> artifacts.ArtifactRef:
        return store.put_bytes(
            value,
            artifacts.PutOptions(kind=kind, media_type="application/vnd.polisyos.epoch+json"),
        )

    query = semantic_epoch.build_epoch_resolution_query_from_evidence(
        artifact_store=store,
        scope_identity=scope,
        authority_purpose="candidate_simulation",
        valid_effect_coordinate_evidence_ref=coordinate("fixture.valid-date", b"2025-01-01"),
        visibility_knowledge_cutoff_evidence_ref=coordinate(
            "fixture.knowledge-time", b"2025-02-01T00:00:00Z"
        ),
        purpose_admission_cutoff_evidence_ref=coordinate(
            "fixture.admission-time", b"2025-02-02T00:00:00Z"
        ),
    )
    source = artifacts.validate_core_model_json_artifact(
        contracts.DataSnapshot, store, evidence.data_snapshot_ref
    ).data_ref
    native_query = service.acquisition_owner_query(query=query)
    statement = contracts.epoch.AcquisitionSemanticBoundaryCandidateStatement(
        source_record_ref=source,
        source_record_content_hash=str(source.artifact_id),
        scope_identity_ref=native_query.scope_identity_ref,
        authority_purpose=native_query.authority_purpose,
        valid_effect_coordinate_ref=native_query.valid_effect_coordinate_ref,
        visibility_knowledge_cutoff_ref=native_query.visibility_knowledge_cutoff_ref,
        purpose_admission_cutoff_ref=native_query.purpose_admission_cutoff_ref,
        requested_query_context_ref=native_query.requested_query_context_ref,
    )
    candidate = acquisition_executor._persist_acquisition_semantic_candidate(
        artifact_store=store, statement=statement
    )
    prepared = service.prepare_acquisition_candidate(
        query=query, candidate_ref=candidate.candidate_ref
    )
    return SimpleNamespace(
        authority=authority,
        entry=entry,
        store=store,
        evidence=evidence,
        candidate=candidate,
        prepared=prepared,
        overlay=overlay,
    )


def _passport(case: SimpleNamespace):
    return acquisition_executor.build_admission_passport(
        epoch_id=1,
        raw_evidence_ref=case.evidence.raw_evidence_ref,
        artifact_store=case.store,
        raw_artifact_id=str(case.evidence.raw_artifact_id),
        authority=case.authority,
        boundary_candidate=case.candidate,
        prepared_epoch=case.prepared,
        live_source_execution=case.evidence,
    )


def test_model_output_is_quarantined_and_cannot_enter_observed_overlay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _fixture(tmp_path, monkeypatch, UNEMPLOYMENT_PROFILE)
    try:
        passport = _passport(case)
        assert passport.observation_class is ObservationProvenanceClass.MODEL_OUTPUT
        assert passport.status is acquisition_executor.AdmissionStatus.QUARANTINED
        assert "model_output_not_observation" in passport.rejection_codes
        assert (
            acquisition_executor.revalidate_admission_passport(
                passport, artifact_store=case.store, authority=case.authority
            )
            == passport
        )
        with pytest.raises(OverlayAdmissionError, match="passport_not_admitted"):
            case.overlay.admit_epoch(
                passport=passport,
                prepared_epoch=case.prepared,
                boundary_candidate=case.candidate,
                artifact_store=case.store,
                authority=case.authority,
            )
        with duckdb.connect(str(case.overlay.overlay_path), read_only=True) as con:
            assert con.execute("SELECT count(*) FROM ds_observations").fetchone() == (0,)
    finally:
        case.overlay.close()


def test_model_output_is_not_downgraded_to_proxy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _fixture(tmp_path, monkeypatch, UNEMPLOYMENT_PROFILE, proxy=True)
    try:
        passport = _passport(case)
        assert passport.field_binding.is_proxy
        assert passport.observation_class is ObservationProvenanceClass.MODEL_OUTPUT
        assert passport.status is acquisition_executor.AdmissionStatus.QUARANTINED
        assert "model_output_not_observation" in passport.rejection_codes
    finally:
        case.overlay.close()


def test_live_source_binds_selected_profile_and_refuses_v1_current_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _fixture(tmp_path, monkeypatch, GDP_PROFILE)
    try:
        evidence = case.evidence
        selected = evidence.raw_artifact_ref
        assert evidence.schema_version == "polisyos.data_forge.live_source_execution_evidence.v2"
        assert selected is not None and selected.manifest_profile_sha256 is not None
        raw = case.store.get_bytes(selected)
        sibling = case.store.put_bytes(
            raw,
            artifacts.PutOptions(
                kind="fabric.acquisition.raw_evidence",
                media_type="application/json",
                producer=artifacts.ProducerInfo(component="fixture.other-producer", version="1"),
            ),
            return_selected_profile=True,
        )
        assert sibling.artifact_id == selected.artifact_id
        assert sibling.manifest_profile_sha256 != selected.manifest_profile_sha256
        assert (
            case.authority.resolve_live_source_execution(
                case.entry.entry_id, evidence, case.store
            ).row_count
            == 1
        )

        forged = evidence.model_copy(update={"raw_artifact_ref": sibling})
        forged = forged.model_copy(
            update={
                "content_sha256": acquisition_executor.content_sha256(forged.identity_payload())
            }
        )
        forged = type(evidence).model_validate(forged.model_dump(mode="json"))
        with pytest.raises(AcquisitionAuthorityError, match="live_raw_selected_profile_drift"):
            case.authority.resolve_live_source_execution(case.entry.entry_id, forged, case.store)

        removed = evidence.model_copy(update={"raw_artifact_ref": None})
        removed = removed.model_copy(
            update={
                "content_sha256": acquisition_executor.content_sha256(removed.identity_payload())
            }
        )
        with pytest.raises(ValidationError, match="requires its raw artifact profile"):
            type(evidence).model_validate(removed.model_dump(mode="json"))

        # This is a synthetic v1 shape, not an archived historical receipt.
        legacy = evidence.model_copy(
            update={
                "schema_version": "polisyos.data_forge.live_source_execution_evidence.v1",
                "raw_artifact_ref": None,
            }
        )
        legacy = legacy.model_copy(
            update={
                "content_sha256": acquisition_executor.content_sha256(legacy.identity_payload())
            }
        )
        legacy_payload = legacy.model_dump(mode="json")
        assert "raw_artifact_ref" not in legacy_payload
        legacy = type(evidence).model_validate(legacy_payload)
        assert legacy.model_dump(mode="json") == legacy_payload
        with pytest.raises(
            AcquisitionAuthorityError, match="live_source_selected_profile_required"
        ):
            case.authority.resolve_live_source_execution(case.entry.entry_id, legacy, case.store)
    finally:
        case.overlay.close()


def test_new_admission_refuses_downgraded_raw_profile_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A rehashed v1 shape cannot grant fresh admission via a sibling view."""
    case = _fixture(tmp_path, monkeypatch, GDP_PROFILE, seed_sibling=True)
    try:
        evidence = case.evidence
        selected = evidence.raw_artifact_ref
        assert selected is not None and selected.manifest_profile_sha256 is not None
        default_manifest = case.store.get_manifest(evidence.raw_artifact_id)
        assert default_manifest.producer is not None
        assert default_manifest.producer.component == "fixture.other-producer"
        legacy = evidence.model_copy(
            update={
                "schema_version": "polisyos.data_forge.live_source_execution_evidence.v1",
                "raw_artifact_ref": None,
            }
        )
        legacy = legacy.model_copy(
            update={
                "content_sha256": acquisition_executor.content_sha256(legacy.identity_payload())
            }
        )
        case.evidence = type(evidence).model_validate(legacy.model_dump(mode="json"))
        with pytest.raises(ValueError, match="live_source_execution_unresolved") as refused:
            _passport(case)
        assert isinstance(refused.value.__cause__, AcquisitionAuthorityError)
        assert refused.value.__cause__.code == "live_source_selected_profile_required"
    finally:
        case.overlay.close()


def test_declared_derived_source_is_quarantined(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _fixture(tmp_path, monkeypatch, GDP_PROFILE, override_class="derived")
    try:
        passport = _passport(case)
        assert passport.observation_class is ObservationProvenanceClass.DERIVED
        assert passport.status is acquisition_executor.AdmissionStatus.QUARANTINED
        assert "derived_cannot_enter_observed_overlay" in passport.rejection_codes
    finally:
        case.overlay.close()


@pytest.mark.parametrize("proxy", [False, True])
def test_unlabelled_source_is_not_admitted_without_a_model_hint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, proxy: bool
) -> None:
    case = _fixture(tmp_path, monkeypatch, GDP_PROFILE, omit_provenance=True, proxy=proxy)
    try:
        with pytest.raises(ValueError, match="source_provenance_not_established"):
            _passport(case)
    finally:
        case.overlay.close()


def test_production_wrapper_refuses_scoped_model_output_before_activation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _fixture(tmp_path, monkeypatch, UNEMPLOYMENT_PROFILE)
    overlay_path = tmp_path / "production-overlay.duckdb"
    try:
        inputs = production_admission_inputs(
            tmp_path,
            store=case.store,
            authority=case.authority,
            overlay_path=overlay_path,
            epoch_history_root=tmp_path / "production-history",
            scope_payload={
                "domain": "labor",
                "jurisdiction": "USA",
                "year": 2024,
                "population": "total_labor_force",
            },
            authority_purpose="candidate_simulation",
        )
        with pytest.raises(OverlayAdmissionError, match="passport_not_admitted"):
            acquisition_executor.admit_acquisition_with_production_semantic_epoch(
                **inputs,
                raw_evidence_ref=case.evidence.raw_evidence_ref,
                live_source_execution=case.evidence,
            )
        with duckdb.connect(str(overlay_path), read_only=True) as con:
            assert con.execute("SELECT count(*) FROM acquisition_epochs").fetchone() == (0,)
            assert con.execute("SELECT count(*) FROM ds_observations").fetchone() == (0,)
    finally:
        case.overlay.close()


def test_revalidation_rejects_rehashed_observed_forgery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _fixture(tmp_path, monkeypatch, UNEMPLOYMENT_PROFILE)
    try:
        passport = _passport(case)
        forged = passport.model_copy(
            update={"observation_class": ObservationProvenanceClass.OBSERVED}
        )
        rejections = forged.recomputed_rejection_codes()
        status = acquisition_executor._derive_status(
            rejection_codes=rejections,
            field_binding=forged.field_binding,
            observation_class=forged.observation_class,
            l5_trust=forged.l5_trust,
            schema_validation=forged.schema_validation,
            source_authority_verified=forged.source_authority_verified,
        )
        forged = forged.model_copy(update={"rejection_codes": rejections, "status": status})
        forged = forged.model_copy(update={"passport_id": forged.recomputed_passport_id()})
        forged = acquisition_executor.AdmissionPassport.model_validate(forged.model_dump())
        assert forged.status is not acquisition_executor.AdmissionStatus.QUARANTINED
        with pytest.raises(ValueError, match="source_provenance_drift"):
            acquisition_executor.revalidate_admission_passport(
                forged, artifact_store=case.store, authority=case.authority
            )
        # Overlay has its own owner intake and must not trust a self-consistent
        # passport that the executor's owner revalidation already rejected.
        with pytest.raises(OverlayAdmissionError, match="source_provenance"):
            case.overlay.admit_epoch(
                passport=forged,
                prepared_epoch=case.prepared,
                boundary_candidate=case.candidate,
                artifact_store=case.store,
                authority=case.authority,
            )
        with duckdb.connect(str(case.overlay.overlay_path), read_only=True) as con:
            assert con.execute("SELECT count(*) FROM ds_observations").fetchone() == (0,)
    finally:
        case.overlay.close()


@pytest.mark.parametrize("override_class", [None, "observed", "proxy", "derived"])
def test_upstream_modeled_descriptor_without_matching_class_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, override_class: str | None
) -> None:
    case = _fixture(
        tmp_path,
        monkeypatch,
        UNEMPLOYMENT_PROFILE,
        omit_provenance=override_class is None,
        override_class=override_class,
        entry_description=("Annual unemployment percentage", "Labor force data in percent."),
    )
    try:
        with pytest.raises(ValueError, match="source_provenance_"):
            _passport(case)
    finally:
        case.overlay.close()


@pytest.mark.parametrize(
    "source_title",
    [
        "Labor share (% of total labor force), modelled estimate",
        "Labor share (% of total labor force), model-based estimate",
        "Labor share (% of total labor force), estimated by a statistical model",
    ],
)
def test_owner_descriptor_variants_refuse_missing_source_class(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source_title: str
) -> None:
    profile = replace(
        UNEMPLOYMENT_PROFILE,
        source_title=source_title,
        source_description="Annual percentage for the total labor force.",
    )
    case = _fixture(tmp_path, monkeypatch, profile, omit_provenance=True)
    try:
        with pytest.raises(ValueError, match="source_provenance_not_established"):
            _passport(case)
    finally:
        case.overlay.close()


def test_declared_observed_fixture_still_admits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _fixture(tmp_path, monkeypatch, GDP_PROFILE)
    try:
        passport = _passport(case)
        assert passport.observation_class is ObservationProvenanceClass.OBSERVED
        assert passport.status is not acquisition_executor.AdmissionStatus.QUARANTINED
        assert (
            acquisition_executor.revalidate_admission_passport(
                passport, artifact_store=case.store, authority=case.authority
            )
            == passport
        )
    finally:
        case.overlay.close()


def test_missing_or_corrupt_upstream_projection_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _fixture(tmp_path, monkeypatch, GDP_PROFILE)
    try:
        passport = _passport(case)
        resolved = case.authority.resolve(case.entry.entry_id)

        class AlteredAuthority:
            def __init__(self, mode: str) -> None:
                self.mode = mode

            def resolve(self, entry_id: str) -> object:
                assert entry_id == case.entry.entry_id
                if self.mode == "mutate_model":
                    value = resolved.model_copy(deep=True)
                    assert value.upstream_catalog_projection is not None
                    value.upstream_catalog_projection["title"] = "altered model output"
                    return value
                payload = resolved.model_dump(mode="python")
                if self.mode == "remove":
                    payload.pop("upstream_catalog_projection", None)
                else:
                    payload["upstream_catalog_projection"]["title"] = "altered model output"
                return payload

            def __getattr__(self, name: str) -> object:
                return getattr(case.authority, name)

        for mode in ("remove", "corrupt", "mutate_model"):
            with pytest.raises(
                ValueError, match=r"source_provenance_|acquisition_authority_unresolved"
            ):
                acquisition_executor.revalidate_admission_passport(
                    passport, artifact_store=case.store, authority=AlteredAuthority(mode)
                )
    finally:
        case.overlay.close()


def test_frozen_v1_registry_retains_original_entry_and_registry_bytes() -> None:
    root = Path(__file__).resolve().parents[4]
    raw = (root / DEFAULT_ACQUISITION_AUTHORITY_REGISTRY).read_bytes()
    original = json.loads(raw)
    registry = AcquisitionAuthorityRegistry.model_validate(original)
    assert registry.model_dump(mode="json") == original
    assert all("source_provenance_class" not in entry for entry in original["entries"])
    assert json.dumps(
        registry.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode() == raw.rstrip(b"\n")
