"""Candidate value method refusal routing and N8 boundary controls."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import ArtifactID, ArtifactOwnershipError, ArtifactRef, FileSystemCAS
from polisyos.runtime.http.errors import RuntimeDependencyError
from polisyos.runtime.quality import generation_cycle as gc
from polisyos.runtime.quality.candidate_value_method import (
    CandidateValueMethodImplementationError,
    project_candidate_value_method,
)
from polisyos.runtime.quality.generation_cycle import (
    SimulationPortObservation,
    ValuePortObservation,
)


def _selected_candidate_method_ref() -> ArtifactRef:
    """Return an exact typed pointer for removal controls; it has no backing CAS bytes."""
    return ArtifactRef(
        artifact_id=ArtifactID.from_sha256_hex("a" * 64),
        kind="runtime.candidate_value_method",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "b" * 64,
    )


def _projector_inputs(store: FileSystemCAS) -> dict[str, Any]:
    """Arguments reached before projection refuses an absent selected record."""
    return {
        "store": store,
        "candidate": object(),
        "problem": object(),
        "simulation": SimulationPortObservation(
            candidate_id="candidate-missing-method-record",
            status="simulation_pending_n5",
        ),
        "cycle_substrate_context": object(),
        "catalog_serving_source": None,
    }


def _validation_error_with_assertion_cause() -> ValueError:
    """Wrap an unexpected assertion the way an input validator could."""
    cause = AssertionError("owner invariant broke")
    failure = ValueError("validation wrapper")
    failure.__cause__ = cause
    return failure


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (ValueError("selected method input is invalid"), "input_refused"),
        (FileNotFoundError("selected CAS member is missing"), "not_established"),
        (
            RuntimeDependencyError(
                dependency="artifact_backend",
                status_code=503,
                code="artifact_backend_unavailable",
                detail="artifact backend is unavailable",
            ),
            "environment_unavailable",
        ),
    ],
    ids=["typed-input-refusal", "missing-selected-cas", "backend-unavailable"],
)
def test_value_owner_failure_kind_preserves_typed_refusal_class(
    failure: Exception, expected: str
) -> None:
    """Only typed input, missing-source and dependency failures become limitations."""
    assert gc._value_owner_failure_kind(failure) == expected


def test_value_owner_failure_kind_does_not_swallow_assertion_in_cause_chain() -> None:
    """A validation wrapper cannot disguise a broken owner assertion as input refusal."""
    failure = _validation_error_with_assertion_cause()
    cause = failure.__cause__
    assert isinstance(cause, AssertionError)
    with pytest.raises(AssertionError, match="owner invariant broke") as propagated:
        gc._value_owner_failure_kind(failure)
    assert propagated.value is cause


@pytest.mark.parametrize(
    "failure",
    [
        ArtifactOwnershipError("foreign artifact owner"),
        PermissionError("filesystem permission denied"),
    ],
    ids=["artifact-owner-denial", "filesystem-permission"],
)
def test_value_owner_failure_kind_propagates_ownership_and_permission_errors(
    failure: PermissionError,
) -> None:
    """Access refusals remain exceptions and never become candidate evidence."""
    with pytest.raises(type(failure)) as propagated:
        gc._value_owner_failure_kind(failure)
    assert propagated.value is failure


def test_fresh_projector_refuses_missing_selected_cas_without_method_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An absent record stays omitted; a dangling exact ref is limited before method replay."""
    store = FileSystemCAS(tmp_path / "missing-candidate-method-cas")

    def forbid_method_run(*_args: object, **_kwargs: object) -> None:
        pytest.fail("missing candidate method record reached numerical method replay")

    monkeypatch.setattr(gc.FoundryValuePort, "_evaluate_source_rows", forbid_method_run)
    monkeypatch.setattr(gc, "_value_outer_set_from_owner_method_run_basis", forbid_method_run)
    common = _projector_inputs(store)

    # No selected optional record means the source-row projection is absent.
    assert project_candidate_value_method(record_ref=None, **common) is None

    # The selected CAS view is intentionally missing. This is a removal control,
    # not a claim that the syntactically valid reference has backing evidence.
    projection = project_candidate_value_method(
        record_ref=_selected_candidate_method_ref(),
        **common,
    )
    assert projection is not None
    assert projection.status == "not_established"
    assert projection.failure_kind == "not_established"
    assert projection.record_ref == _selected_candidate_method_ref()


def test_fresh_projector_surfaces_internal_classifier_fault_as_direct_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A broken refusal classifier is not flattened into a missing-source result."""
    assert not issubclass(CandidateValueMethodImplementationError, RuntimeError)
    store = FileSystemCAS(tmp_path / "candidate-method-classifier-fault-cas")

    def broken_classifier(_failure: Exception) -> str:
        raise AssertionError("failure classifier implementation fault")

    monkeypatch.setattr(gc, "_value_owner_failure_kind", broken_classifier)
    with pytest.raises(
        CandidateValueMethodImplementationError,
        match="candidate_value_method_replay_internal_error",
    ) as failure:
        project_candidate_value_method(
            record_ref=_selected_candidate_method_ref(),
            **_projector_inputs(store),
        )
    assert isinstance(failure.value.__cause__, AssertionError)


def test_conditional_n8_keeps_method_ref_candidate_only_and_rejects_owner_receipt() -> None:
    """An optional source method link cannot add owner receipts to conditional N8."""
    from polisyos.foundry.methods.selection import MethodSelectionReceipt

    selection = gc._select_value_method(candidate={}, problem={}, inputs={})
    assert selection["status"] == "selected"
    receipt = MethodSelectionReceipt.model_validate(selection["selection_receipt"])
    observation = ValuePortObservation(
        status="value_conditional",
        candidate_id="candidate-conditional-method-boundary",
        value_ref="sha256:" + "c" * 64,
        authority_blockers=(
            "interaction_numeric_classification_unsupported",
            "interaction_sampling_not_established",
        ),
        reason="The N5 result remains simulation-only.",
        evaluation_mode="simulate_only",
        decision_grade="low",
        candidate_value_method_ref=_selected_candidate_method_ref(),
        n5_interaction_schema_version="policyos.runtime.joint_simulation_horizon.v1",
        numeric_interaction="unsupported",
        numeric_interaction_basis="not_established",
        interaction_sampling_status="not_established",
    )
    assert observation.status == "value_conditional"
    assert observation.candidate_value_method_ref == _selected_candidate_method_ref()
    assert observation.method_selection_receipt is None
    assert observation.value_receipt is None

    payload = observation.model_dump(mode="python")
    payload["method_selection_receipt"] = receipt
    with pytest.raises(ValueError, match="value_conditional_cannot_carry_owner_receipts"):
        ValuePortObservation.model_validate(payload)


def test_fresh_projector_propagates_real_foreign_owner_denial(tmp_path: Path) -> None:
    """Selected foreign bytes are refused before record parsing or method replay."""
    from polisyos.core.artifacts import CanonInfo, PutOptions, SchemaInfo
    from polisyos.core.canon import CanonSpec
    from tests.unit.runtime.quality.test_cycle_substrate import _authenticated_tenant_scope

    root = tmp_path / "foreign-candidate-record-cas"
    writer = FileSystemCAS(root, tenant_id="owner-a", cell_id="cell-a", ownership_enforced=True)
    spec = CanonSpec(forbid_floats=False)
    with _authenticated_tenant_scope(tenant_id="owner-a", cell_id="cell-a"):
        ref = writer.put_json(
            {"not_a_method_result": "owner-a bytes are not evidence for owner-b"},
            PutOptions(
                kind="runtime.candidate_value_method",
                media_type="application/json",
                schema=SchemaInfo(name="policyos.runtime.candidate_value_method.v1", version="1.0"),
                canon=CanonInfo.from_spec(spec),
            ),
            canon_spec=spec,
            return_selected_profile=True,
        )
        assert writer.get_bytes(ref)
    reader = FileSystemCAS(root, tenant_id="owner-b", cell_id="cell-b", ownership_enforced=True)
    with (
        _authenticated_tenant_scope(tenant_id="owner-b", cell_id="cell-b"),
        pytest.raises(ArtifactOwnershipError),
    ):
        project_candidate_value_method(record_ref=ref, **_projector_inputs(reader))


def _completed_projection() -> Any:
    """Create a valid public candidate result for serialization and corruption controls."""
    from polisyos.core.contracts.runtime import RunCandidateValueMethodProjection
    from tests.unit.runtime.quality.test_value_gate import _unit_value_set

    def ref(kind: str) -> ArtifactRef:
        return _selected_candidate_method_ref().model_copy(update={"kind": kind})

    return RunCandidateValueMethodProjection(
        status="completed",
        record_ref=ref("runtime.candidate_value_method"),
        source_request_ref=ref("runtime.value_owner_source_projection_request"),
        run_basis_ref=ref("runtime.value_owner_method_run_basis"),
        value_ref=ref("runtime.value_outer_set_candidate_fixture"),
        native_report_ref=ref("ir.causal_effect_report"),
        method_selection_receipt_ref=ref("runtime.value_owner_method_selection_receipt"),
        selected_method_fqn="causal.treatment_effects.aipw@1.0.0",
        measurement_unit="m",
        point_estimate=2.0,
        statistical_interval=(1.0, 3.0),
        value_outer_set=_unit_value_set(lower=(-7.0,), upper=(9.0,), identification_mode="partial"),
        limitation_codes=("candidate_fixture_value_run_not_authority",),
    )


def test_completed_projection_roundtrips_derived_outer_width_and_refuses_tampering() -> None:
    """Public JSON preserves actual typed bounds and verifies their derived checksum."""
    from polisyos.core.contracts.runtime import RunCandidateValueMethodProjection

    projection = _completed_projection()
    decoded = RunCandidateValueMethodProjection.model_validate_json(projection.model_dump_json())
    assert decoded == projection
    assert decoded.value_outer_set is not None
    assert decoded.value_outer_set.width == (16.0,)
    assert decoded.publication_authority is False
    payload = projection.model_dump(mode="json")
    payload["value_outer_set"]["width"] = [0.0]
    with pytest.raises(ValueError, match="value_outer_set_width_tampered"):
        RunCandidateValueMethodProjection.model_validate(payload)

    payload = projection.model_dump(mode="python")
    payload["status"] = "not_established"
    with pytest.raises(ValueError, match="run_candidate_value_method_unverified_output_present"):
        RunCandidateValueMethodProjection.model_validate(payload)


def test_source_request_persistence_preserves_native_epoch_selected_lineage(
    tmp_path: Path,
) -> None:
    """The generic Core edge owner carries all native source-media selected views."""
    from collections import Counter

    from polisyos.runtime.quality.candidate_value_method import (
        persist_candidate_value_source_request,
    )
    from tests._helpers.candidate_value_source_panel import build_candidate_value_source_panel

    store = FileSystemCAS(tmp_path / "source-request-cas")
    panel = build_candidate_value_source_panel(tmp_path / "source", store=store)
    selected_ref = persist_candidate_value_source_request(store, panel.request)
    manifest = store.get_manifest(selected_ref)
    expected: Counter[tuple[str, str, str]] = Counter()
    for binding in panel.request.variable_projections:
        projection = panel.source.projections[binding.variable_id]
        assert projection.receipt_ref.media_type == "application/vnd.polisyos.epoch+json"
        for name in ("receipt_ref", "passport_ref"):
            ref = getattr(projection, name)
            assert ref.manifest_profile_sha256 is not None
            expected[
                (str(ref.artifact_id), f"{binding.role}:{name}", ref.manifest_profile_sha256)
            ] += 1
    actual = Counter(
        (str(edge.artifact_id), edge.role, edge.manifest_profile_sha256) for edge in manifest.inputs
    )
    assert sum(expected.values()) == 6
    assert actual == expected
    assert store.verify(selected_ref).ok
    assert selected_ref.manifest_profile_sha256 is not None

    # Prove each actual source/profile and S3 prerequisite before a served
    # request spends N4 or N5 work. This is method-neutral owner preparation,
    # not a fabricated atom-bound run intent or a replacement numerical result.
    from polisyos.runtime.quality.data_state_substrate import l1_dcat_variable_availability
    from polisyos.runtime.quality.intervention_substrate import (
        load_l6_intervention_substrate,
        project_value_method_route_constraint,
    )
    from polisyos.runtime.quality.substrate_registry import catalog_serving_source_scope

    code_root = Path(__file__).resolve().parents[4]
    bundle = load_l6_intervention_substrate(code_root, source_owner_root=panel.source.repo_root)
    route = project_value_method_route_constraint(bundle, family="agents.income")
    assert route.target_contract_id == "foundry.causal.hte_observational_data.v1"
    assert panel.request.selected_method_fqn in route.allowed_method_fqns
    profiles = {}
    with catalog_serving_source_scope(panel.catalog_source):
        for binding in panel.request.variable_projections:
            availability = l1_dcat_variable_availability(
                panel.source.repo_root,
                binding.variable_id,
                overlay_path=panel.source.overlay_path,
            )
            assert availability.status == "available"
            profile = gc._load_value_data_profile_from_l1_dcat(
                repo_root=panel.source.repo_root,
                outcome=binding.variable_id,
                owner_access_ref=availability.coverage_ref,
                overlay_path=panel.source.overlay_path,
                scope_region="UA",
                artifact_store=store,
                activated_observation_projection=panel.source.projections[binding.variable_id],
            )
            assert profile is not None
            assert len(profile.rows) == 200
            assert profile.measurement_unit == ("usd" if binding.role == "outcome" else "binary")
            profiles[binding.variable_id] = profile
    source_cells = [
        {(row.unit_id, row.period_id) for row in profile.rows} for profile in profiles.values()
    ]
    assert len(source_cells) == 3 and all(cells == source_cells[0] for cells in source_cells)
    assert {row.outcome_value for row in profiles["cells.distress_score"].rows} == {0.0, 1.0}
    selected = gc._select_value_method(
        candidate={},
        problem={},
        inputs={
            "method_fqn": panel.request.selected_method_fqn,
            "observation_to_contract_manifest": bundle.observation_manifest,
            "observation_family": "agents.income",
        },
    )
    assert selected["status"] == "selected", selected
    assert selected["selected_method_fqn"] == panel.request.selected_method_fqn


@pytest.mark.parametrize(
    "field_name",
    [
        "record_ref",
        "source_request_ref",
        "run_basis_ref",
        "value_ref",
        "native_report_ref",
        "method_selection_receipt_ref",
    ],
)
@pytest.mark.parametrize("defect", ["kind", "media_type", "profile"])
def test_candidate_method_projection_refuses_wrong_role_media_or_missing_view(
    field_name: str,
    defect: str,
) -> None:
    """Every serialized selected role retains the same contract as its API reader."""
    from polisyos.core.contracts.runtime import RunCandidateValueMethodProjection

    payload = _completed_projection().model_dump(mode="json")
    changes = {
        "kind": {"kind": "runtime.unrelated_artifact"},
        "media_type": {"media_type": "application/octet-stream"},
        "profile": {"manifest_profile_sha256": None},
    }
    payload[field_name].update(changes[defect])
    with pytest.raises(ValueError, match="run_candidate_value_method_selected_ref_invalid"):
        RunCandidateValueMethodProjection.model_validate(payload)
