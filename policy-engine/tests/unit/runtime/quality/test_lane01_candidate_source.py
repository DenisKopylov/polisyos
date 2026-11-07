"""Candidate WDI source custody replays the actual compiler and Fabric carriers."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from polisyos.core import artifacts, canon
from polisyos.data_forge.read_api import catalog
from polisyos.data_requirement import DataRequirementCompilationReport
from polisyos.fabric import data_plane
from polisyos.runtime.quality.acquisition_planner import (
    persist_and_verify_data_requirement_compilation_report,
)
from polisyos.runtime.quality.candidate_acquisition_source import (
    CANDIDATE_ACQUISITION_SOURCE_SCHEMA,
    CANDIDATE_ACQUISITION_SOURCE_SCHEMA_V2,
    CANDIDATE_ACQUISITION_SOURCE_SCHEMA_V3,
    CandidateAcquisitionSource,
    _write_options,
    persist_candidate_acquisition_source,
    read_candidate_acquisition_source,
)
from polisyos.runtime.quality.capability_resolver import RequirementToCapabilityResolver
from tests._helpers.lane01_candidate_source import (
    GDP_COMPILER_INPUT,
    UNEMPLOYMENT_COMPILER_INPUT,
    build_lane01_candidate_source,
    compile_lane01_candidate_report,
)
from tests._helpers.lane01_wdi_profiles import (
    GDP_PROFILE,
    UNEMPLOYMENT_PROFILE,
    CandidateWDIProfile,
    fixture_wdi_response,
)


def _generated_gdp_profile() -> CandidateWDIProfile:
    """Describe generated fixture bytes without relabeling the governed GDP row."""
    return replace(
        GDP_PROFILE,
        source_title="Controlled generated GDP candidate fixture",
        source_description=(
            "Test-owned generated GDP-shaped bytes in current US dollars; not an empirical "
            "observation, release, or current source value."
        ),
        source_provenance_class="model_output",
    )


def _generated_gdp_candidate_resolver() -> RequirementToCapabilityResolver:
    """Bind the synthetic GDP fixture semantics in a candidate-only resolver input."""
    governed = RequirementToCapabilityResolver.governed_fixture()
    capabilities = []
    found = False
    for capability in governed.capabilities:
        if capability.construct_id != "economic.gdp":
            capabilities.append(capability)
            continue
        found = True
        if len(capability.source_assets) != 1:
            raise AssertionError("governed GDP source candidate must have one source asset")
        asset = capability.source_assets[0]
        metadata = asset.metadata | {
            "observation_provenance": "model_output",
            "population_scope": "national_economy",
            "quantity_kind": "unconstrained",
        }
        capabilities.append(
            capability.model_copy(
                update={
                    "capability_id": "capability:test_owned_generated_gdp_candidate",
                    "evidence_mode": "model_output",
                    "limitations": (
                        *capability.limitations,
                        "test_owned_generated_bytes_not_empirical_gdp_or_source_authority",
                    ),
                    "metadata": {
                        **capability.metadata,
                        "test_fixture_title": "Controlled generated GDP candidate fixture",
                    },
                    "source_assets": (
                        asset.model_copy(
                            update={
                                "ref": "fixture://lane01/generated-gdp-candidate",
                                "source_layer": "test_fixture",
                                "metadata": metadata,
                            }
                        ),
                    ),
                }
            )
        )
    if not found:
        raise AssertionError("governed resolver must contain the economic.gdp candidate")
    return RequirementToCapabilityResolver(
        capabilities=capabilities,
        failure_modes=governed.failure_modes,
        acquisition_strategies=governed.acquisition_strategies,
        conflicts=governed.conflicts,
        capability_index_ref="capability-index:test-generated-gdp-candidate-v1",
    )


def test_candidate_source_reopens_owner_bytes_and_refuses_changed_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = build_lane01_candidate_source(tmp_path, monkeypatch)
    store = fixture.store
    source = fixture.source
    assert source.observation == pytest.approx(0.175)
    assert source.status == "candidate_only"
    assert source.purpose == "candidate_simulation"
    assert source.observation_class == "model_output"
    assert source.source_currentness == "source_currentness_not_established"
    assert "historical_transport_status_not_established" in source.limitations
    assert "current_run_job_route_ownership_not_established" in source.limitations
    assert source.population == "total_labor_force"
    assert source.denominator == "total_labor_force"
    assert source.quantity_kind == "share_of_denominator"
    assert source.schema_version == CANDIDATE_ACQUISITION_SOURCE_SCHEMA
    assert _write_options(source).schema.name == CANDIDATE_ACQUISITION_SOURCE_SCHEMA
    assert _write_options(source).schema.version == "1"
    assert source.canonical_unit == "ratio"
    assert {
        "measurement_validity_not_established",
        "causal_validity_not_established",
        "claim_evidence_not_established",
    }.issubset(source.limitations)
    assert all(
        ref.manifest_profile_sha256
        for ref in (
            fixture.source_ref,
            source.compiler_report_ref,
            source.raw_source_ref,
            source.normalized_source_ref,
            source.source_snapshot_ref,
            source.source_evidence_ref,
        )
    )
    assert (
        read_candidate_acquisition_source(
            store, source_ref=fixture.source_ref, authority=fixture.authority
        )
        == source
    )

    original_get_bytes = store.get_bytes
    source_payload_reads: list[object] = []

    def count_source_payload_reads(ref: object, *args: object, **kwargs: object) -> bytes:
        if str(getattr(ref, "artifact_id", ref)) == str(fixture.source_ref.artifact_id):
            source_payload_reads.append(ref)
        return original_get_bytes(ref, *args, **kwargs)

    with monkeypatch.context() as scoped:
        scoped.setattr(store, "get_bytes", count_source_payload_reads)
        assert read_candidate_acquisition_source(store, source_ref=fixture.source_ref) == source
    assert source_payload_reads == [fixture.source_ref]

    kwargs = {
        "authority": fixture.authority,
        "entry_id": fixture.entry.entry_id,
        "live_source_execution": fixture.evidence,
        "requirement_basis_binding": fixture.binding,
        "requirement_id": fixture.requirement_id,
        "candidate_digest": fixture.candidate_digest,
        "target_slot_id": source.target_slot_id,
        "country_code": source.country_code,
        "year": source.year,
        "population": source.population,
        "tenant_id": source.tenant_id,
        "cell_id": source.cell_id,
        "run_id": source.run_id,
        "job_id": source.job_id,
        "route_id": source.route_id,
    }
    for override, reason in (
        ({"population": "working_age_population"}, "owner_scope_mismatch"),
        ({"year": 2023}, "owner_scope_mismatch"),
        ({"target_slot_id": "global.income"}, "owner_scope_mismatch"),
        ({"requirement_id": "unrelated-requirement"}, "requirement_ambiguous_or_missing"),
        ({"candidate_digest": "sha256:" + "0" * 64}, "descriptor_ambiguous_or_missing"),
        (
            {
                "requirement_basis_binding": fixture.binding.model_copy(
                    update={"compiler_report_digest": "sha256:" + "0" * 64}
                )
            },
            "compiler_binding_invalid",
        ),
    ):
        with pytest.raises(ValueError, match=reason):
            persist_candidate_acquisition_source(store, **(kwargs | override))
    foreign_report = compile_lane01_candidate_report(scenario_id="different-scenario")
    foreign_binding = persist_and_verify_data_requirement_compilation_report(
        store, foreign_report, expected_scenario_id="different-scenario"
    )
    with pytest.raises(ValueError, match="requirement_ambiguous_or_missing"):
        persist_candidate_acquisition_source(
            store, **(kwargs | {"requirement_basis_binding": foreign_binding})
        )
    report = DataRequirementCompilationReport.model_validate(
        artifacts.load_core_json_artifact(store, fixture.binding.compiler_report_ref)
    )
    resolutions = report.capability_requirement_resolutions or ()
    selected_rows = [
        row for row in resolutions if row.query.requirement_id == fixture.requirement_id
    ]
    assert len(selected_rows) == 1
    ambiguous_report = report.model_copy(
        update={"capability_requirement_resolutions": (*resolutions, selected_rows[0])}
    )
    ambiguous_binding = persist_and_verify_data_requirement_compilation_report(
        store, ambiguous_report, expected_scenario_id="lane01-unemployment"
    )
    with pytest.raises(ValueError, match="requirement_ambiguous_or_missing"):
        persist_candidate_acquisition_source(
            store, **(kwargs | {"requirement_basis_binding": ambiguous_binding})
        )
    profileless_ref = fixture.binding.compiler_report_ref.model_copy(
        update={"manifest_profile_sha256": None}
    )
    profileless_binding = fixture.binding.model_copy(
        update={"compiler_report_ref": profileless_ref}
    )
    with pytest.raises(ValueError, match="compiler_profile_unselected"):
        persist_candidate_acquisition_source(
            store, **(kwargs | {"requirement_basis_binding": profileless_binding})
        )
    with pytest.raises(TypeError, match="live_execution_evidence_required"):
        persist_candidate_acquisition_source(
            store,
            **(
                kwargs | {"live_source_execution": SimpleNamespace(**fixture.evidence.model_dump())}
            ),
        )
    legacy_payload = fixture.evidence.model_dump(mode="json")
    legacy_payload.pop("raw_artifact_ref")
    legacy_payload["schema_version"] = "polisyos.data_forge.live_source_execution_evidence.v1"
    legacy_payload["content_sha256"] = data_plane.content_sha256(
        {key: value for key, value in legacy_payload.items() if key != "content_sha256"}
    )
    legacy_evidence = catalog.LiveSourceExecutionEvidence.model_validate(legacy_payload)
    with pytest.raises(ValueError, match="raw_profile_unselected"):
        persist_candidate_acquisition_source(
            store, **(kwargs | {"live_source_execution": legacy_evidence})
        )

    # Forging a content-addressed payload and matching manifest still cannot
    # make an in-range numeric value survive the owner's raw/normalized replay.
    forged = source.model_copy(update={"observation": 0.18})
    forged_ref = store.put_json(
        forged,
        _write_options(forged),
        canon_spec=canon.CanonSpec(forbid_floats=False, exclude_none=False),
        return_selected_profile=True,
    )
    with pytest.raises(ValueError, match="derived_value_or_limitations_mismatch"):
        read_candidate_acquisition_source(store, source_ref=forged_ref)

    # Same bytes and kind under a different writer profile are not the raw
    # source actually emitted by the live observer.
    raw_bytes = store.get_bytes(source.raw_source_ref)
    sibling = store.put_bytes(
        raw_bytes,
        artifacts.ArtifactWriteOptions(
            kind="fabric.acquisition.raw_evidence",
            media_type="application/json",
            producer=artifacts.ProducerInfo(component="test.other_writer", version="1"),
        ),
        return_selected_profile=True,
    )
    assert sibling.artifact_id == source.raw_source_ref.artifact_id
    assert sibling.manifest_profile_sha256 != source.raw_source_ref.manifest_profile_sha256
    sibling_proof = source.live_source_execution.model_dump(mode="json")
    sibling_proof["raw_artifact_ref"] = sibling.model_dump(mode="json")
    sibling_proof["content_sha256"] = data_plane.content_sha256(
        {key: value for key, value in sibling_proof.items() if key != "content_sha256"}
    )
    sibling_evidence = catalog.LiveSourceExecutionEvidence.model_validate(sibling_proof)
    forged_sibling = source.model_copy(
        update={"live_source_execution": sibling_evidence, "raw_source_ref": sibling}
    )
    sibling_ref = store.put_json(
        forged_sibling,
        _write_options(forged_sibling),
        canon_spec=canon.CanonSpec(forbid_floats=False, exclude_none=False),
        return_selected_profile=True,
    )
    with pytest.raises(catalog.AcquisitionAuthorityError, match="live_raw_selected_profile_drift"):
        read_candidate_acquisition_source(store, source_ref=sibling_ref)

    original_get_bytes = store.get_bytes
    for removed in (
        source.raw_source_ref,
        source.normalized_source_ref,
        source.compiler_report_ref,
    ):

        def get_bytes(
            ref: object,
            *args: object,
            removed_id: str = str(removed.artifact_id),
            **options: object,
        ) -> bytes:
            if str(getattr(ref, "artifact_id", ref)) == removed_id:
                raise FileNotFoundError("selected source bytes removed")
            return original_get_bytes(ref, *args, **options)

        with monkeypatch.context() as scoped:
            scoped.setattr(store, "get_bytes", get_bytes)
            with pytest.raises(
                (FileNotFoundError, ValueError), match=r"removed|compiler_binding_invalid"
            ):
                read_candidate_acquisition_source(store, source_ref=fixture.source_ref)

    journal = Path(fixture.evidence.request_ref.journal_path)
    unavailable = journal.with_name("temporarily-unavailable.jsonl")
    journal.rename(unavailable)
    try:
        assert read_candidate_acquisition_source(store, source_ref=fixture.source_ref) == source
        with pytest.raises(catalog.AcquisitionAuthorityError):
            read_candidate_acquisition_source(
                store, source_ref=fixture.source_ref, authority=fixture.authority
            )
    finally:
        unavailable.rename(journal)


def test_generated_gdp_candidate_source_reopens_with_independent_identity_oracle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Persist generated GDP-shaped bytes through the real compiler and source owners."""
    synthetic_profile = _generated_gdp_profile()
    resolver = _generated_gdp_candidate_resolver()
    fixture = build_lane01_candidate_source(
        tmp_path / "gdp-80",
        monkeypatch,
        profile=synthetic_profile,
        compiler_input=GDP_COMPILER_INPUT,
        capability_resolver=resolver,
        response_body=fixture_wdi_response(synthetic_profile, value=80.0),
    )
    source = fixture.source
    assert source.observation == 80.0
    assert source.target_slot_id == "global.gdp"
    assert source.canonical_unit == "usd"
    assert source.country_code == "USA" and source.year == 2024
    assert source.population == "national_economy"
    assert source.denominator is None
    assert source.quantity_kind == "unconstrained"
    assert source.schema_version == CANDIDATE_ACQUISITION_SOURCE_SCHEMA_V2
    assert _write_options(source).schema.name == CANDIDATE_ACQUISITION_SOURCE_SCHEMA_V2
    assert _write_options(source).schema.version == "2"
    assert source.status == "candidate_only"
    assert source.source_currentness == "source_currentness_not_established"
    report = DataRequirementCompilationReport.model_validate(
        artifacts.load_core_json_artifact(fixture.store, fixture.binding.compiler_report_ref)
    )
    (resolution,) = report.capability_requirement_resolutions or ()
    (candidate,) = resolution.candidate_discovery.candidates
    assert candidate.capability_ref == "capability:test_owned_generated_gdp_candidate"
    assert (
        candidate.descriptor["metadata"]["test_fixture_title"]
        == "Controlled generated GDP candidate fixture"
    )
    assert candidate.source_assets[0]["ref"] == "fixture://lane01/generated-gdp-candidate"
    assert candidate.descriptor["capability_lifecycle"]["state"] == "draft"
    assert candidate.descriptor["rights_envelope"]["claim_evidence_use_allowed"] is False
    assert "test_owned_generated_bytes_not_empirical_gdp_or_source_authority" in (
        candidate.limitations
    )
    assert {
        "measurement_validity_not_established",
        "causal_validity_not_established",
        "claim_evidence_not_established",
    }.issubset(source.limitations)
    assert (
        read_candidate_acquisition_source(
            fixture.store, source_ref=fixture.source_ref, authority=fixture.authority
        )
        == source
    )

    changed = build_lane01_candidate_source(
        tmp_path / "gdp-81",
        monkeypatch,
        profile=synthetic_profile,
        compiler_input=GDP_COMPILER_INPUT,
        capability_resolver=resolver,
        response_body=fixture_wdi_response(synthetic_profile, value=81.0),
    )
    assert changed.source.observation == 81.0
    assert changed.source.target_slot_id == "global.gdp"
    assert changed.source.canonical_unit == "usd"
    assert changed.source.status == "candidate_only"


@pytest.mark.parametrize("source_class", ["model_output", "observed"])
def test_candidate_source_refuses_cross_version_selected_view(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source_class: str
) -> None:
    """Body versions bind the exact selected schema, even when source bytes are identical."""
    from tests._helpers.candidate_holdout_resource import wdi_response_for_year

    options = (
        {
            "profile": GDP_PROFILE,
            "compiler_input": GDP_COMPILER_INPUT,
            "response_body": wdi_response_for_year(2024),
        }
        if source_class == "observed"
        else {}
    )
    fixture = build_lane01_candidate_source(tmp_path, monkeypatch, **options)
    source = fixture.source
    wrong_schema = (
        CANDIDATE_ACQUISITION_SOURCE_SCHEMA
        if source_class == "observed"
        else CANDIDATE_ACQUISITION_SOURCE_SCHEMA_V3
    )
    alias = fixture.store.put_bytes(
        fixture.store.get_bytes(fixture.source_ref),
        replace(
            _write_options(source),
            schema=artifacts.SchemaInfo(name=wrong_schema, version=wrong_schema.rsplit("v", 1)[1]),
        ),
        return_selected_profile=True,
    )
    assert alias.artifact_id == fixture.source_ref.artifact_id
    assert alias.manifest_profile_sha256 != fixture.source_ref.manifest_profile_sha256
    fresh = artifacts.FileSystemCAS(fixture.store.root)
    assert fresh.verify(alias).ok
    with pytest.raises(ValueError, match="candidate_source_manifest_binding_mismatch"):
        read_candidate_acquisition_source(fresh, source_ref=alias)
    assert read_candidate_acquisition_source(fresh, source_ref=fixture.source_ref) == source


def test_observed_source_refuses_conflicting_descriptor_provenance_with_actual_capture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Preserved candidate markers cannot substitute a model-output label for observed bytes."""
    from tests._helpers import lane01_candidate_source as source_helper
    from tests._helpers.candidate_holdout_resource import wdi_response_for_year

    governed = RequirementToCapabilityResolver.governed_fixture()
    capabilities = []
    for capability in governed.capabilities:
        if capability.construct_id == "economic.gdp":
            (asset,) = capability.source_assets
            capability = capability.model_copy(
                update={
                    "source_assets": (
                        asset.model_copy(
                            update={
                                "metadata": asset.metadata
                                | {"observation_provenance": "model_output"}
                            }
                        ),
                    )
                }
            )
        capabilities.append(capability)
    resolver = RequirementToCapabilityResolver(
        capabilities=capabilities,
        failure_modes=governed.failure_modes,
        acquisition_strategies=governed.acquisition_strategies,
        conflicts=governed.conflicts,
        capability_index_ref=governed.capability_index_ref,
    )
    capture = wdi_response_for_year(2024)
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    executions = []
    actual_persist = source_helper.persist_candidate_acquisition_source

    def retain_actual_execution(*args, **kwargs):
        executions.append(kwargs["live_source_execution"])
        return actual_persist(*args, **kwargs)

    monkeypatch.setattr(
        source_helper, "persist_candidate_acquisition_source", retain_actual_execution
    )
    with pytest.raises(ValueError, match="candidate_source_descriptor_scope_mismatch"):
        build_lane01_candidate_source(
            tmp_path,
            monkeypatch,
            store=store,
            profile=GDP_PROFILE,
            compiler_input=GDP_COMPILER_INPUT,
            capability_resolver=resolver,
            response_body=capture,
        )
    assert len(executions) == 1
    assert store.get_bytes(executions[0].raw_artifact_ref) == capture


@pytest.mark.parametrize(
    ("source_class", "direct_mode"),
    [("observed", "model_output"), ("model_output", "observed")],
)
def test_candidate_source_refuses_direct_descriptor_class_contradiction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source_class: str, direct_mode: str
) -> None:
    """Explicit source metadata cannot hide a conflicting direct capability declaration."""
    from tests._helpers.candidate_holdout_resource import wdi_response_for_year

    profile = GDP_PROFILE if source_class == "observed" else UNEMPLOYMENT_PROFILE
    compiler_input = (
        GDP_COMPILER_INPUT if source_class == "observed" else UNEMPLOYMENT_COMPILER_INPUT
    )
    governed = RequirementToCapabilityResolver.governed_fixture()
    capabilities = []
    for capability in governed.capabilities:
        if capability.construct_id == profile.construct:
            (asset,) = capability.source_assets
            capability = capability.model_copy(
                update={
                    "evidence_mode": direct_mode,
                    "source_assets": (
                        asset.model_copy(
                            update={
                                "metadata": asset.metadata
                                | {"observation_provenance": source_class}
                            }
                        ),
                    ),
                }
            )
        capabilities.append(capability)
    resolver = RequirementToCapabilityResolver(
        capabilities=capabilities,
        failure_modes=governed.failure_modes,
        acquisition_strategies=governed.acquisition_strategies,
        conflicts=governed.conflicts,
        capability_index_ref=governed.capability_index_ref,
    )
    with pytest.raises(ValueError, match="candidate_source_descriptor_scope_mismatch"):
        build_lane01_candidate_source(
            tmp_path,
            monkeypatch,
            profile=profile,
            compiler_input=compiler_input,
            capability_resolver=resolver,
            response_body=(
                wdi_response_for_year(2024)
                if source_class == "observed"
                else fixture_wdi_response(profile)
            ),
        )


def test_candidate_source_v2_rejects_share_without_denominator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """V2 permits a missing denominator only for an unconstrained quantity."""
    fixture = build_lane01_candidate_source(tmp_path, monkeypatch)
    payload = fixture.source.model_dump(mode="json")
    payload.update(
        {
            "schema_version": CANDIDATE_ACQUISITION_SOURCE_SCHEMA_V2,
            "denominator": None,
            "quantity_kind": "share_of_denominator",
        }
    )
    with pytest.raises(
        ValidationError, match="candidate_acquisition_source_share_requires_denominator"
    ):
        CandidateAcquisitionSource.model_validate(payload)


def test_candidate_source_v1_keeps_required_denominator_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Historical v1 remains strict when an unconstrained measure lacks a denominator."""
    fixture = build_lane01_candidate_source(tmp_path, monkeypatch)
    payload = fixture.source.model_dump(mode="json")
    payload["denominator"] = None
    with pytest.raises(
        ValidationError, match="candidate_acquisition_source_v1_requires_denominator"
    ):
        CandidateAcquisitionSource.model_validate(payload)


def test_governed_observed_gdp_candidate_source_reopens_with_observed_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real GDP owner, compiler descriptor, and derived identity remain observed."""
    fixture = build_lane01_candidate_source(
        tmp_path / "observed-gdp",
        monkeypatch,
        profile=GDP_PROFILE,
        compiler_input=GDP_COMPILER_INPUT,
        response_body=fixture_wdi_response(GDP_PROFILE),
    )
    source = fixture.source
    assert source.observation == GDP_PROFILE.fixture_value
    assert source.schema_version == CANDIDATE_ACQUISITION_SOURCE_SCHEMA_V3
    assert _write_options(source).schema.name == CANDIDATE_ACQUISITION_SOURCE_SCHEMA_V3
    assert _write_options(source).schema.version == "3"
    assert source.observation_class == "observed"
    assert source.resolved_source.entry.source_provenance_class == "observed"
    assert source.status == "candidate_only"
    assert source.purpose == "candidate_simulation"
    assert source.source_currentness == "source_currentness_not_established"
    assert {
        "measurement_validity_not_established",
        "causal_validity_not_established",
        "claim_evidence_not_established",
    }.issubset(source.limitations)

    report = DataRequirementCompilationReport.model_validate(
        artifacts.load_core_json_artifact(fixture.store, fixture.binding.compiler_report_ref)
    )
    (resolution,) = report.capability_requirement_resolutions or ()
    (candidate,) = resolution.candidate_discovery.candidates
    assert candidate.descriptor["evidence_mode"] == "observed"

    # Reopen through a fresh CAS handle so the result does not rely on the
    # in-memory object returned by the producer.
    reopened_store = artifacts.FileSystemCAS(fixture.store.root)
    reopened = read_candidate_acquisition_source(
        reopened_store, source_ref=fixture.source_ref, authority=fixture.authority
    )
    assert reopened == source

    # The source artifact's own provenance label is content-addressed but not
    # self-authorizing; a coherently written label that contradicts the live
    # owner's derived identity is refused on readback.
    forged = source.model_copy(
        update={"observation_class": catalog.ObservationProvenanceClass.MODEL_OUTPUT}
    )
    forged_ref = fixture.store.put_json(
        forged,
        _write_options(forged),
        canon_spec=canon.CanonSpec(forbid_floats=False, exclude_none=False),
        return_selected_profile=True,
    )
    with pytest.raises(ValueError, match="candidate_source_provenance_mismatch"):
        read_candidate_acquisition_source(fixture.store, source_ref=forged_ref)

    for scope_override in ({"canonical_unit": "ratio"}, {"year": source.year - 1}):
        forged_scope = source.model_copy(update=scope_override)
        forged_scope_ref = fixture.store.put_json(
            forged_scope,
            _write_options(forged_scope),
            canon_spec=canon.CanonSpec(forbid_floats=False, exclude_none=False),
            return_selected_profile=True,
        )
        with pytest.raises(ValueError, match="candidate_source_owner_scope_mismatch"):
            read_candidate_acquisition_source(fixture.store, source_ref=forged_scope_ref)

    # The legacy schemas remain model-output-only even when every other field
    # is structurally valid for that schema.
    for legacy_schema in (
        CANDIDATE_ACQUISITION_SOURCE_SCHEMA,
        CANDIDATE_ACQUISITION_SOURCE_SCHEMA_V2,
    ):
        legacy_payload = source.model_dump(mode="json")
        legacy_payload["schema_version"] = legacy_schema
        legacy_payload["denominator"] = "national_economy"
        with pytest.raises(
            ValidationError, match="candidate_acquisition_source_legacy_provenance_mismatch"
        ):
            CandidateAcquisitionSource.model_validate(legacy_payload)

    missing_v3_class = source.model_dump(mode="json")
    missing_v3_class.pop("observation_class")
    with pytest.raises(
        ValidationError, match="candidate_acquisition_source_v3_requires_observation_class"
    ):
        CandidateAcquisitionSource.model_validate(missing_v3_class)

    # A wrong writer profile and removed selected owner bytes cannot be made
    # valid merely by carrying the observed source label forward.
    wrong_writer_options = replace(
        _write_options(source),
        producer=artifacts.ProducerInfo(component="test.other_writer", version="3.0"),
    )
    wrong_writer_ref = fixture.store.put_json(
        source,
        wrong_writer_options,
        canon_spec=canon.CanonSpec(forbid_floats=False, exclude_none=False),
        return_selected_profile=True,
    )
    with pytest.raises(ValueError, match="candidate_source_manifest_binding_mismatch"):
        read_candidate_acquisition_source(fixture.store, source_ref=wrong_writer_ref)

    original_get_bytes = fixture.store.get_bytes
    for removed in (source.raw_source_ref, source.normalized_source_ref):

        def get_bytes(
            ref: object,
            *args: object,
            removed_id: str = str(removed.artifact_id),
            **options: object,
        ) -> bytes:
            if str(getattr(ref, "artifact_id", ref)) == removed_id:
                raise FileNotFoundError("selected observed source bytes removed")
            return original_get_bytes(ref, *args, **options)

        with monkeypatch.context() as scoped:
            scoped.setattr(fixture.store, "get_bytes", get_bytes)
            with pytest.raises(FileNotFoundError, match="selected observed source bytes removed"):
                read_candidate_acquisition_source(fixture.store, source_ref=fixture.source_ref)


def test_generated_gdp_candidate_refuses_observed_source_class(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A model-output candidate descriptor cannot admit an observed-class source owner."""
    observed_profile = replace(_generated_gdp_profile(), source_provenance_class="observed")
    with pytest.raises(ValueError, match="candidate_source_descriptor_scope_mismatch"):
        build_lane01_candidate_source(
            tmp_path,
            monkeypatch,
            profile=observed_profile,
            compiler_input=GDP_COMPILER_INPUT,
            capability_resolver=_generated_gdp_candidate_resolver(),
        )


def test_candidate_source_refuses_wrong_indicator_scope_and_sensitive_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Use the real resolver and compiler over an isolated typed lifecycle
    # variant; neither the shared governed index nor its JSON is edited.
    with monkeypatch.context() as scoped:
        active = build_lane01_candidate_source(
            tmp_path / "active", scoped, lifecycle_override="active"
        )
        assert active.source.observation == pytest.approx(0.175)
        assert active.source.status == "candidate_only"
    with (
        monkeypatch.context() as scoped,
        pytest.raises(ValueError, match="descriptor_scope_mismatch"),
    ):
        build_lane01_candidate_source(
            tmp_path / "withdrawn", scoped, lifecycle_override="withdrawn"
        )

    wrong = replace(UNEMPLOYMENT_PROFILE, indicator_id="SL.UEM.TOTL.XX")
    with (
        monkeypatch.context() as scoped,
        pytest.raises(ValueError, match="descriptor_scope_mismatch"),
    ):
        build_lane01_candidate_source(tmp_path / "wrong-indicator", scoped, profile=wrong)

    # The descriptor and query agree while the independent owner declares a
    # different population or a different denominator.
    for case, wrong_owner, reason in (
        (
            "population",
            replace(UNEMPLOYMENT_PROFILE, population="working_age_population"),
            "owner_scope_mismatch",
        ),
        (
            "denominator",
            replace(UNEMPLOYMENT_PROFILE, denominator="working_age_population"),
            "descriptor_scope_mismatch",
        ),
        (
            "observed-class",
            replace(UNEMPLOYMENT_PROFILE, source_provenance_class="observed"),
            "owner_scope_mismatch",
        ),
    ):
        with (
            monkeypatch.context() as scoped,
            pytest.raises(ValueError, match=reason),
        ):
            build_lane01_candidate_source(
                tmp_path / f"wrong-owner-{case}",
                scoped,
                profile=wrong_owner,
                declared_population="total_labor_force",
            )

    wrong_unit = replace(
        UNEMPLOYMENT_PROFILE,
        raw_unit="ratio",
        transform="identity",
        transform_ref="fabric://units/ratio-identity/v1",
    )
    with (
        monkeypatch.context() as scoped,
        pytest.raises(catalog.AcquisitionAuthorityError, match="catalog_unit_mismatch"),
    ):
        build_lane01_candidate_source(tmp_path / "wrong-unit", scoped, profile=wrong_unit)

    # The field-binding maximum admits 1.5, so only the declared share
    # invariant can reject this independently produced 150 percent input.
    oversized_share = replace(UNEMPLOYMENT_PROFILE, fixture_value=150.0, valid_max=2.0)
    with (
        monkeypatch.context() as scoped,
        pytest.raises(ValueError, match="share_out_of_bounds"),
    ):
        build_lane01_candidate_source(tmp_path / "oversized-share", scoped, profile=oversized_share)

    # The real WDI/Fabric producer ignores this extra field during normalization;
    # the independent structured scan must nevertheless refuse the source.
    sensitive = json.loads(fixture_wdi_response(UNEMPLOYMENT_PROFILE))
    sensitive[1][0]["sensitive_data"] = "private-controlled-fixture"
    body = json.dumps(sensitive, sort_keys=True, separators=(",", ":")).encode()
    with (
        monkeypatch.context() as scoped,
        pytest.raises(ValueError, match="raw_pii_or_scan_version_unresolved"),
    ):
        build_lane01_candidate_source(tmp_path / "sensitive", scoped, response_body=body)
