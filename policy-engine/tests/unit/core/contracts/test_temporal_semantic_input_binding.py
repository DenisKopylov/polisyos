"""Temporal manifest subjects and lineage, separate from Foundry value replay."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import ArtifactID, FileSystemCAS, PutOptions, SchemaInfo
from polisyos.core.canon import to_canonical_bytes
from polisyos.core.contracts import model_input_requirements
from polisyos.core.contracts.semantic_derived_binding import (
    DerivedInputCorrespondenceRef,
    DerivedInputProfileRef,
)
from polisyos.core.contracts.semantic_input_binding import (
    ResolvedDerivedInput,
    ResolvedDerivedInputAtStep,
    ResolvedInputBindingManifest,
    ResolvedInputBindingManifestRef,
    load_resolved_input_binding_manifest,
    persist_resolved_input_binding_manifest,
)
from polisyos.core.contracts.semantic_step_binding import recompute_resolved_step_input_coverage
from polisyos.core.contracts.variable_binding import SelectedVariableBindingRef
from tests.unit.core.contracts.test_semantic_step_binding import _two_year_preflight


def _ref(index: int, kind: str) -> SelectedVariableBindingRef:
    return SelectedVariableBindingRef(
        artifact_id=ArtifactID.from_sha256_hex(f"{index:064x}"),
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256="sha256:" + f"{index + 100:064x}",
    )


def _manifest_case(tmp_path: Path):
    case, preflight = _two_year_preflight(tmp_path)
    selected_set, _ = model_input_requirements.load_model_input_obligation_set(
        case.store, preflight.obligation_set_ref
    )
    (obligation_ref,) = selected_set.obligation_refs
    assert selected_set.required_step_scopes is not None
    rows = tuple(
        ResolvedDerivedInputAtStep(
            step_scope=scope,
            selection=ResolvedDerivedInput(
                binding_id=f"selected_value_{scope.step}",
                model_input_obligation_ref=SelectedVariableBindingRef.model_validate(
                    obligation_ref.model_dump(mode="python")
                ),
                model_interface_ref=SelectedVariableBindingRef.model_validate(
                    selected_set.invocation.interface_ref.model_dump(mode="python")
                ),
                model_port_id=scope.port_id,
                recipe_ref=_ref(20 + scope.step, "polisyos.runtime.derivation_recipe"),
                certificate_ref=_ref(30 + scope.step, "polisyos.runtime.derivation_certificate"),
                output_ref=_ref(40 + scope.step, "polisyos.runtime.derived_economic_series"),
                year=scope.scope.period_start.year,
                correspondence_ref=DerivedInputCorrespondenceRef.model_validate(
                    _ref(50 + scope.step, "catalog.derived_input_correspondence").model_dump(
                        mode="python"
                    )
                ),
                profile_ref=DerivedInputProfileRef.model_validate(
                    _ref(60 + scope.step, "catalog.derived_input_profile").model_dump(mode="python")
                ),
                source_path=f"derived_inputs.value_{scope.step}.value",
            ),
        )
        for scope in selected_set.required_step_scopes
    )
    manifest = ResolvedInputBindingManifest(
        schema_version="3.0",
        data_snapshot_ref=SelectedVariableBindingRef.model_validate(
            case.data_snapshot_ref.model_dump(mode="python")
        ),
        model_input_obligation_set_ref=SelectedVariableBindingRef.model_validate(
            preflight.obligation_set_ref.model_dump(mode="python")
        ),
        method_input_steps=rows,
    )
    return case, manifest


def test_step_manifest_reopens_original_full_denominator_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case, manifest = _manifest_case(tmp_path)
    try:
        original = model_input_requirements.load_model_input_obligation_set
        calls = []

        def counted(*args, **kwargs):
            calls.append(args[1])
            return original(*args, **kwargs)

        monkeypatch.setattr(model_input_requirements, "load_model_input_obligation_set", counted)
        ref = persist_resolved_input_binding_manifest(case.store, manifest)
        loaded = load_resolved_input_binding_manifest(FileSystemCAS(case.store.root), ref)
        assert loaded == manifest
        assert calls == [manifest.model_input_obligation_set_ref]
        coverage = recompute_resolved_step_input_coverage(case.store, loaded)
        assert coverage.is_complete
        assert coverage.missing_step_scopes == ()
        assert "measurements" not in loaded.model_dump(mode="json")
        assert "derivations" not in loaded.model_dump(mode="json")
    finally:
        case.close()


def test_partial_step_manifest_preserves_missing_future_scope(tmp_path: Path) -> None:
    case, manifest = _manifest_case(tmp_path)
    try:
        partial = ResolvedInputBindingManifest.model_validate(
            manifest.model_dump(mode="python")
            | {"method_input_steps": manifest.method_input_steps[:1]}
        )
        ref = persist_resolved_input_binding_manifest(case.store, partial)
        loaded = load_resolved_input_binding_manifest(FileSystemCAS(case.store.root), ref)
        coverage = recompute_resolved_step_input_coverage(case.store, loaded)
        assert tuple(row.scope.period_start.year for row in coverage.supplied_step_scopes) == (
            2020,
        )
        assert tuple(row.scope.period_start.year for row in coverage.missing_step_scopes) == (2021,)
        with pytest.raises(ValueError, match=r"^model_input_step_coverage_incomplete$"):
            coverage.require_complete()
        assert loaded.authority_purpose == "candidate_simulation_input_only"
    finally:
        case.close()


def test_step_manifest_requires_complete_selected_lineage(tmp_path: Path) -> None:
    case, manifest = _manifest_case(tmp_path)
    try:
        ref = case.store.put_json(
            manifest,
            PutOptions(
                kind=manifest.ARTIFACT_KIND,
                media_type=manifest.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(name=manifest.ARTIFACT_SCHEMA_NAME, version="3.0"),
                inputs=[
                    edge for edge in manifest.lineage_inputs() if not edge.role.endswith(".output")
                ],
            ),
            return_selected_profile=True,
        )
        with pytest.raises(ValueError, match=r"^resolved_input_binding_manifest_lineage_mismatch$"):
            load_resolved_input_binding_manifest(
                FileSystemCAS(case.store.root),
                ResolvedInputBindingManifestRef.model_validate(ref.model_dump(mode="python")),
            )
    finally:
        case.close()


@pytest.mark.parametrize("mutation", ["foreign_origin", "foreign_interface", "scope_graft"])
def test_step_manifest_replays_scope_and_selected_origin(tmp_path: Path, mutation: str) -> None:
    case, manifest = _manifest_case(tmp_path)
    try:
        row = manifest.method_input_steps[0]
        if mutation == "foreign_origin":
            row = row.model_copy(
                update={
                    "selection": row.selection.model_copy(
                        update={
                            "model_input_obligation_ref": _ref(
                                90, "runtime.quality.model_input_obligation"
                            )
                        }
                    )
                }
            )
        elif mutation == "foreign_interface":
            row = row.model_copy(
                update={
                    "selection": row.selection.model_copy(
                        update={
                            "model_interface_ref": _ref(
                                90, "runtime.quality.program_graph_input_interface"
                            )
                        }
                    )
                }
            )
        else:
            row = row.model_copy(
                update={
                    "step_scope": row.step_scope.model_copy(
                        update={
                            "scope": row.step_scope.scope.model_copy(
                                update={"geography_ref": "foreign"}
                            )
                        }
                    )
                }
            )
        changed = manifest.model_copy(update={"method_input_steps": (row,)})
        ref = persist_resolved_input_binding_manifest(case.store, changed)
        with pytest.raises(ValueError, match=r"^model_input_step_selection_"):
            load_resolved_input_binding_manifest(FileSystemCAS(case.store.root), ref)
    finally:
        case.close()


@pytest.mark.parametrize("mutation", ["same_step", "same_binding", "same_path", "reverse"])
def test_step_manifest_refuses_ambiguous_or_noncanonical_inventory(
    tmp_path: Path, mutation: str
) -> None:
    case, manifest = _manifest_case(tmp_path)
    try:
        first, second = manifest.method_input_steps
        if mutation == "same_step":
            rows = (first, first)
        elif mutation == "reverse":
            rows = (second, first)
        else:
            field = "binding_id" if mutation == "same_binding" else "source_path"
            rows = (
                first,
                second.model_copy(
                    update={
                        "selection": second.selection.model_copy(
                            update={field: getattr(first.selection, field)}
                        )
                    }
                ),
            )
        with pytest.raises(ValidationError, match="resolved_input_binding_"):
            ResolvedInputBindingManifest.model_validate(
                manifest.model_dump(mode="python") | {"method_input_steps": rows}
            )
    finally:
        case.close()


@pytest.mark.parametrize("old_version", ["1.0", "2.0"])
def test_old_manifests_retain_exact_wire_and_reject_step_fields(
    tmp_path: Path, old_version: str
) -> None:
    case, manifest = _manifest_case(tmp_path)
    try:
        from polisyos.core.contracts.semantic_input_binding import ResolvedMeasurementInput
        from polisyos.core.contracts.variable_binding import (
            ScopedCorrespondenceBasisRef,
            ScopedMeasurementOccurrenceRef,
        )

        fields = {
            "schema_version": old_version,
            "data_snapshot_ref": manifest.data_snapshot_ref,
            "model_input_obligation_set_ref": manifest.model_input_obligation_set_ref,
        }
        if old_version == "1.0":
            selected = ResolvedMeasurementInput(
                binding_id="old",
                model_input_obligation_ref=manifest.method_input_steps[
                    0
                ].selection.model_input_obligation_ref,
                selected_occurrence_ref=ScopedMeasurementOccurrenceRef.model_validate(
                    _ref(70, "catalog.scoped_measurement_occurrence").model_dump(mode="python")
                ),
                correspondence_ref=ScopedCorrespondenceBasisRef.model_validate(
                    _ref(71, "catalog.scoped_correspondence_basis").model_dump(mode="python")
                ),
                source_path="old.value",
            )
            fields["measurements"] = (selected,)
            selection_field = "measurements"
        else:
            selected = manifest.method_input_steps[0].selection
            fields["derivations"] = (selected,)
            selection_field = "derivations"
        loaded = ResolvedInputBindingManifest.model_validate(fields)
        expected = {
            "schema_version": old_version,
            "authority_purpose": "candidate_simulation_input_only",
            "data_snapshot_ref": manifest.data_snapshot_ref.model_dump(mode="json"),
            "model_input_obligation_set_ref": manifest.model_input_obligation_set_ref.model_dump(
                mode="json"
            ),
            "retained_binding_ids": [],
            selection_field: [selected.model_dump(mode="json")],
        }
        assert to_canonical_bytes(loaded) == to_canonical_bytes(expected)
        assert "method_input_steps" not in loaded.model_dump(mode="json")
        with pytest.raises(ValidationError, match="step_inputs_version_mismatch"):
            ResolvedInputBindingManifest.model_validate(fields | {"method_input_steps": ()})
    finally:
        case.close()
