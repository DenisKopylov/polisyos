"""Check compiler-to-owner candidate selection before any source execution."""

from __future__ import annotations

import copy
import hashlib
import json
import socket
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pytest

from polisyos.core import artifacts
from polisyos.core.contracts.capability_resolution import CapabilitySourceCandidate
from polisyos.data_forge.read_api import catalog
from polisyos.data_requirement import DataRequirementCompilationReport
from polisyos.runtime.quality import acquisition_executor
from polisyos.runtime.quality.acquisition_planner import (
    AcquisitionRequirementBasisBinding,
    persist_and_verify_data_requirement_compilation_report,
)
from polisyos.runtime.quality.candidate_acquisition_source import (
    validate_candidate_acquisition_selection,
)
from tests._helpers.lane01_candidate_source import compile_lane01_candidate_report
from tests._helpers.lane01_wdi_profiles import (
    UNEMPLOYMENT_PROFILE,
    build_fixture_wdi_authority,
)


@dataclass(frozen=True, slots=True)
class _PrefetchFixture:
    store: artifacts.FileSystemCAS
    report: DataRequirementCompilationReport
    binding: AcquisitionRequirementBasisBinding
    authority: catalog.CanonicalAcquisitionAuthority
    entry_id: str
    resolved: catalog.ResolvedAcquisitionAuthority
    compiled_ref: str
    requirement_id: str
    candidate: CapabilitySourceCandidate


def _forbid_execution(*_args: object, **_kwargs: object) -> None:
    pytest.fail("prefetch selection attempted network or source execution")


@pytest.fixture(autouse=True)
def _no_network_or_acquisition(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket.socket, "connect", _forbid_execution)
    monkeypatch.setattr(socket.socket, "connect_ex", _forbid_execution)
    monkeypatch.setattr(acquisition_executor, "execute_live_catalog_acquisition", _forbid_execution)


@pytest.fixture(scope="module")
def prefetch(tmp_path_factory: pytest.TempPathFactory) -> _PrefetchFixture:
    root = tmp_path_factory.mktemp("lane01-prefetch")
    with pytest.MonkeyPatch.context() as guarded:
        guarded.setattr(socket.socket, "connect", _forbid_execution)
        guarded.setattr(socket.socket, "connect_ex", _forbid_execution)
        report = compile_lane01_candidate_report()
        store = artifacts.FileSystemCAS(root / "cas")
        binding = persist_and_verify_data_requirement_compilation_report(
            store, report, expected_scenario_id="lane01-unemployment"
        )
        authority, entry = build_fixture_wdi_authority(root / "repo", UNEMPLOYMENT_PROFILE)
        resolved = authority.resolve(entry.entry_id)

    resolutions = [
        row
        for row in (report.capability_requirement_resolutions or ())
        if row.query.construct == UNEMPLOYMENT_PROFILE.construct
        and row.candidate_discovery is not None
        and row.candidate_discovery.candidates
    ]
    assert len(resolutions) == 1
    resolution = resolutions[0]
    discovery = resolution.candidate_discovery
    assert discovery is not None and len(discovery.candidates) == 1
    specs = [
        spec
        for spec in report.specs
        if isinstance(spec.metadata.get("capability_binding"), Mapping)
        and spec.metadata["capability_binding"].get("requirement_id")
        == resolution.query.requirement_id
    ]
    assert len(specs) == 1
    assert binding.compiler_report_ref.manifest_profile_sha256 is not None
    return _PrefetchFixture(
        store=store,
        report=report,
        binding=binding,
        authority=authority,
        entry_id=entry.entry_id,
        resolved=resolved,
        compiled_ref=specs[0].requirement_id,
        requirement_id=resolution.query.requirement_id,
        candidate=discovery.candidates[0],
    )


def _selection_args(case: _PrefetchFixture) -> dict[str, Any]:
    return {
        "requirement_basis_binding": case.binding,
        "compiled_requirement_ref": case.compiled_ref,
        "requirement_id": case.requirement_id,
        "candidate_digest": case.candidate.content_digest,
        "authority": case.authority,
        "entry_id": case.entry_id,
        "target_slot_id": UNEMPLOYMENT_PROFILE.target_slot,
        "country_code": UNEMPLOYMENT_PROFILE.country_code,
        "year": UNEMPLOYMENT_PROFILE.year,
        "population": UNEMPLOYMENT_PROFILE.population,
    }


def _assert_refusal(case: _PrefetchFixture, updates: dict[str, Any], code: str) -> None:
    with pytest.raises(ValueError) as refusal:
        validate_candidate_acquisition_selection(case.store, **(_selection_args(case) | updates))
    assert str(refusal.value).partition(":")[0] == code


def _persist_report(
    case: _PrefetchFixture, report: DataRequirementCompilationReport
) -> AcquisitionRequirementBasisBinding:
    return persist_and_verify_data_requirement_compilation_report(
        case.store, report, expected_scenario_id="lane01-unemployment"
    )


def _persist_descriptor_variant(
    case: _PrefetchFixture, descriptor: dict[str, Any]
) -> tuple[AcquisitionRequirementBasisBinding, str]:
    encoded = json.dumps(
        descriptor, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    digest = "sha256:" + hashlib.sha256(encoded).hexdigest()
    candidate = CapabilitySourceCandidate.model_validate(
        case.candidate.model_dump(mode="python")
        | {"descriptor": descriptor, "content_digest": digest}
    )
    assert candidate.construct_ref == case.candidate.construct_ref
    assert candidate.content_digest != case.candidate.content_digest
    rows = list(case.report.capability_requirement_resolutions or ())
    index = next(i for i, row in enumerate(rows) if row.query.requirement_id == case.requirement_id)
    discovery = rows[index].candidate_discovery
    assert discovery is not None
    rows[index] = rows[index].model_copy(
        update={"candidate_discovery": discovery.model_copy(update={"candidates": (candidate,)})}
    )
    report = case.report.model_copy(update={"capability_requirement_resolutions": tuple(rows)})
    return _persist_report(case, report), digest


def test_prefetch_resolves_compiler_candidate_without_source_execution(
    prefetch: _PrefetchFixture,
) -> None:
    before = {str(item) for item in prefetch.store.iter_artifact_ids()}
    selected, resolved = validate_candidate_acquisition_selection(
        prefetch.store, **_selection_args(prefetch)
    )
    assert isinstance(selected, CapabilitySourceCandidate)
    assert selected == prefetch.candidate
    assert resolved == prefetch.resolved
    assert resolved.entry.source_provenance_class == "model_output"
    metadata = selected.source_assets[0]["metadata"]
    assert metadata["observation_provenance"] == "model_output"
    assert metadata["source_release"] == "not_established"
    discovery = next(
        row.candidate_discovery
        for row in prefetch.report.capability_requirement_resolutions or ()
        if row.query.requirement_id == prefetch.requirement_id
    )
    assert discovery is not None
    assert discovery.satisfies_claim_evidence is False
    assert discovery.requires_native_source_admission is True
    assert {str(item) for item in prefetch.store.iter_artifact_ids()} == before


def test_prefetch_refuses_removed_unknown_scope_limitation(prefetch: _PrefetchFixture) -> None:
    original = prefetch.candidate
    missing_limitation = "source_jurisdiction_not_established"
    assert missing_limitation in original.limitations
    forged = CapabilitySourceCandidate.model_validate(
        original.model_dump(mode="python")
        | {
            "limitations": tuple(
                item for item in original.limitations if item != missing_limitation
            )
        }
    )
    assert forged.model_dump(exclude={"limitations"}) == original.model_dump(
        exclude={"limitations"}
    )
    assert forged.content_digest == original.content_digest
    rows = list(prefetch.report.capability_requirement_resolutions or ())
    index = next(
        i for i, row in enumerate(rows) if row.query.requirement_id == prefetch.requirement_id
    )
    discovery = rows[index].candidate_discovery
    assert discovery is not None and discovery.candidates == (original,)
    rows[index] = rows[index].model_copy(
        update={"candidate_discovery": discovery.model_copy(update={"candidates": (forged,)})}
    )
    report = prefetch.report.model_copy(update={"capability_requirement_resolutions": tuple(rows)})
    binding = _persist_report(prefetch, report)
    assert binding.compiler_report_ref.manifest_profile_sha256 is not None
    assert (
        binding.compiler_report_ref.artifact_id != prefetch.binding.compiler_report_ref.artifact_id
    )
    _assert_refusal(
        prefetch,
        {"requirement_basis_binding": binding},
        "candidate_source_scope_limitations_mismatch",
    )


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        (
            "candidate_digest",
            "sha256:" + "0" * 64,
            "candidate_source_descriptor_ambiguous_or_missing",
        ),
        (
            "compiled_requirement_ref",
            "data-requirement:foreign",
            "candidate_source_compiler_spec_ambiguous_or_missing",
        ),
        (
            "requirement_id",
            "requirement:foreign",
            "candidate_source_requirement_ambiguous_or_missing",
        ),
        ("target_slot_id", "global.foreign_unemployment", "candidate_source_owner_scope_mismatch"),
        ("country_code", "CAN", "candidate_source_compiler_relation_mismatch"),
        ("year", 2023, "candidate_source_compiler_relation_mismatch"),
        ("population", "working_age_population", "candidate_source_compiler_relation_mismatch"),
    ],
)
def test_prefetch_refuses_each_foreign_selection_component(
    prefetch: _PrefetchFixture, field: str, value: object, code: str
) -> None:
    _assert_refusal(prefetch, {field: value}, code)


def test_prefetch_refuses_untyped_authority(prefetch: _PrefetchFixture) -> None:
    with pytest.raises(TypeError, match=r"^candidate_source_canonical_authority_required$"):
        validate_candidate_acquisition_selection(
            prefetch.store, **(_selection_args(prefetch) | {"authority": object()})
        )


@pytest.mark.parametrize(
    ("entry_id", "code"),
    [
        ("", "candidate_source_owner_entry_required"),
        ("acquisition-authority:sha256:" + "0" * 64, "candidate_source_live_owner_unavailable"),
    ],
)
def test_prefetch_refuses_missing_owner_entry(
    prefetch: _PrefetchFixture, entry_id: str, code: str
) -> None:
    _assert_refusal(prefetch, {"entry_id": entry_id}, code)


def test_prefetch_refuses_forged_report_digest(prefetch: _PrefetchFixture) -> None:
    wrong_digest = prefetch.binding.model_copy(
        update={"compiler_report_digest": "sha256:" + "0" * 64}
    )
    _assert_refusal(
        prefetch,
        {"requirement_basis_binding": wrong_digest},
        "candidate_source_compiler_binding_invalid",
    )


def test_prefetch_refuses_unselected_report_profile(prefetch: _PrefetchFixture) -> None:
    unselected_ref = prefetch.binding.compiler_report_ref.model_copy(
        update={"manifest_profile_sha256": None}
    )
    unselected = prefetch.binding.model_copy(update={"compiler_report_ref": unselected_ref})
    _assert_refusal(
        prefetch,
        {"requirement_basis_binding": unselected},
        "candidate_source_compiler_profile_unselected",
    )


def test_prefetch_refuses_same_report_bytes_from_foreign_writer(
    prefetch: _PrefetchFixture,
) -> None:
    original = prefetch.binding.compiler_report_ref
    manifest = prefetch.store.get_manifest(original)
    sibling = prefetch.store.put_bytes(
        prefetch.store.get_bytes(original),
        artifacts.ArtifactWriteOptions(
            kind=original.kind,
            media_type=original.media_type,
            schema=manifest.artifact_schema,
            canon=manifest.canon,
            producer=artifacts.ProducerInfo(component="test.foreign_compiler", version="1"),
        ),
        return_selected_profile=True,
    )
    assert sibling.artifact_id == original.artifact_id
    assert sibling.manifest_profile_sha256 != original.manifest_profile_sha256
    forged = prefetch.binding.model_copy(update={"compiler_report_ref": sibling})
    _assert_refusal(
        prefetch, {"requirement_basis_binding": forged}, "candidate_source_compiler_binding_invalid"
    )


@pytest.mark.parametrize("which", ["spec", "resolution"])
def test_prefetch_refuses_ambiguous_selected_report(prefetch: _PrefetchFixture, which: str) -> None:
    if which == "spec":
        selected = next(
            spec for spec in prefetch.report.specs if spec.requirement_id == prefetch.compiled_ref
        )
        report = prefetch.report.model_copy(update={"specs": (*prefetch.report.specs, selected)})
        expected = "candidate_source_compiler_spec_ambiguous_or_missing"
    else:
        rows = prefetch.report.capability_requirement_resolutions or ()
        selected = next(row for row in rows if row.query.requirement_id == prefetch.requirement_id)
        report = prefetch.report.model_copy(
            update={"capability_requirement_resolutions": (*rows, selected)}
        )
        expected = "candidate_source_requirement_ambiguous_or_missing"
    _assert_refusal(
        prefetch, {"requirement_basis_binding": _persist_report(prefetch, report)}, expected
    )


def test_prefetch_refuses_mismatched_compiled_spec_relation(prefetch: _PrefetchFixture) -> None:
    specs = list(prefetch.report.specs)
    index = next(i for i, spec in enumerate(specs) if spec.requirement_id == prefetch.compiled_ref)
    selected = specs[index]
    metadata = copy.deepcopy(selected.metadata)
    metadata["capability_binding"]["requirement_id"] = "requirement:foreign"
    specs[index] = selected.model_copy(update={"metadata": metadata})
    report = prefetch.report.model_copy(update={"specs": tuple(specs)})
    _assert_refusal(
        prefetch,
        {"requirement_basis_binding": _persist_report(prefetch, report)},
        "candidate_source_compiler_relation_mismatch",
    )


def test_prefetch_refuses_rehashed_descriptor_with_same_metric_and_foreign_target(
    prefetch: _PrefetchFixture,
) -> None:
    descriptor = copy.deepcopy(prefetch.candidate.descriptor)
    descriptor["source_assets"][0]["metadata"]["target_world_slot"] = "global.foreign_unemployment"
    binding, digest = _persist_descriptor_variant(prefetch, descriptor)
    _assert_refusal(
        prefetch,
        {"requirement_basis_binding": binding, "candidate_digest": digest},
        "candidate_source_descriptor_scope_mismatch",
    )


@pytest.mark.parametrize(
    "scope_update",
    [
        {"geography": "CAN"},
        {"geography": "multi_context", "jurisdiction": "CAN"},
        {"time_end": "2023-12-31"},
    ],
    ids=["foreign-geography", "foreign-jurisdiction", "expired-time-window"],
)
def test_prefetch_refuses_rehashed_foreign_descriptor_scope(
    prefetch: _PrefetchFixture, scope_update: dict[str, str]
) -> None:
    descriptor = copy.deepcopy(prefetch.candidate.descriptor)
    descriptor["scope"].update(scope_update)
    assert descriptor["source_assets"] == prefetch.candidate.descriptor["source_assets"]
    assert descriptor["construct"] == prefetch.candidate.descriptor["construct"]
    binding, digest = _persist_descriptor_variant(prefetch, descriptor)
    _assert_refusal(
        prefetch,
        {"requirement_basis_binding": binding, "candidate_digest": digest},
        "candidate_source_descriptor_scope_mismatch",
    )


def test_prefetch_refuses_foreign_resolved_owner_for_original_selection(
    prefetch: _PrefetchFixture, tmp_path: Path
) -> None:
    foreign = replace(UNEMPLOYMENT_PROFILE, target_slot="global.foreign_unemployment")
    authority, entry = build_fixture_wdi_authority(tmp_path / "foreign-repo", foreign)
    resolved = authority.resolve(entry.entry_id)
    assert resolved.entry.upstream_metric_id == prefetch.resolved.entry.upstream_metric_id
    _assert_refusal(
        prefetch,
        {"authority": authority, "entry_id": entry.entry_id},
        "candidate_source_owner_scope_mismatch",
    )


@pytest.mark.parametrize("difference", ["population", "measurement", "target"])
def test_prefetch_refuses_coherent_foreign_authority_scope(
    prefetch: _PrefetchFixture, tmp_path: Path, difference: str
) -> None:
    if difference == "population":
        foreign = replace(
            UNEMPLOYMENT_PROFILE,
            population="working_age_population",
            denominator="working_age_population",
        )
    elif difference == "measurement":
        foreign = replace(UNEMPLOYMENT_PROFILE, quantity_kind="unconstrained")
    else:
        foreign = replace(UNEMPLOYMENT_PROFILE, target_slot="global.foreign_unemployment")
    authority, entry = build_fixture_wdi_authority(tmp_path / "foreign-repo", foreign)
    resolved = authority.resolve(entry.entry_id)
    assert resolved.entry.upstream_metric_id == prefetch.resolved.entry.upstream_metric_id
    _assert_refusal(
        prefetch,
        {
            "authority": authority,
            "entry_id": entry.entry_id,
            "target_slot_id": foreign.target_slot,
            "country_code": foreign.country_code,
            "year": foreign.year,
            "population": foreign.population,
        },
        (
            "candidate_source_compiler_relation_mismatch"
            if difference == "population"
            else "candidate_source_descriptor_scope_mismatch"
        ),
    )
