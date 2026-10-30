"""Selected method evidence retains strict candidate semantics across its JSON boundary."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import read_core_json_artifact_bounded
from polisyos.core.artifacts.canonical_profile import CoreJsonReadLimits
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.runtime import (
    DirectMethodExecutionSelection,
    MethodExecutionCandidateOutcome,
)
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.http.services.control.run_lifecycle import (
    _validate_direct_method_execution_selection_artifacts,
)
from tests._helpers.observational_source_runtime import (
    selected_source_runtime_api_env as selected_source_runtime_api_env,
)
from tests.unit.runtime.http import test_observational_method_runtime as fixture


def _candidate() -> MethodExecutionCandidateOutcome:
    return MethodExecutionCandidateOutcome(
        status="success",
        estimand="ATE",
        point_estimate=1.25,
        confidence_interval=(0.25, 2.25),
        confidence_level=0.95,
        standard_error=0.5,
        p_value=0.01,
        sample_size=40,
        n_treated=20,
        n_control=20,
    )


def _selected_candidate_case(
    tmp_path: Path,
    candidate_payload: object,
) -> tuple[FileSystemCAS, DirectMethodExecutionSelection, CoreJsonReadLimits]:
    """Extend the existing real CAS lineage fixture with a complete candidate JSON value."""
    store, selection, limits = fixture._direct_method_cas_case(tmp_path)
    original = read_core_json_artifact_bounded(
        store,
        selection.method_evidence_ref,
        limits=limits,
    )
    payload = dict(original.value)
    payload["candidate_outcome"] = candidate_payload
    manifest = original.manifest
    selected_ref = fixture._put_selected_json(
        store,
        payload,
        kind=manifest.kind,
        schema=manifest.artifact_schema,
        inputs=tuple(manifest.inputs),
        governance=manifest.governance,
        tenant_context=manifest.tenant_context,
    )
    selection = selection.model_copy(
        update={"method_evidence_ref": selected_ref, "candidate_outcome": _candidate()}
    )
    # Reopen the actual CAS rather than reusing a decoded payload or model instance.
    fresh_store = FileSystemCAS(tmp_path / "cas").with_ambient_ownership_enforcement()
    return fresh_store, selection, limits


def _validate_selection(
    store: FileSystemCAS,
    selection: DirectMethodExecutionSelection,
    limits: CoreJsonReadLimits,
) -> None:
    _validate_direct_method_execution_selection_artifacts(
        store=store,
        selection=selection,
        limits=limits,
    )


def test_candidate_json_wire_intake_preserves_strict_python_contract() -> None:
    from polisyos.core.contracts import (
        MethodExecutionCandidateOutcome as FacadeCandidateOutcome,
    )

    assert FacadeCandidateOutcome is MethodExecutionCandidateOutcome
    candidate = _candidate()
    payload = candidate.model_dump(mode="json")
    assert type(payload["confidence_interval"]) is list
    assert type(payload["limitations"]) is list
    with pytest.raises(ValidationError) as error:
        MethodExecutionCandidateOutcome.model_validate(payload)
    assert {row["loc"] for row in error.value.errors()} == {
        ("confidence_interval",),
        ("limitations",),
    }
    parsed = FacadeCandidateOutcome.from_json_payload(payload)
    assert parsed == candidate
    assert parsed.model_dump(mode="json") == payload
    assert type(parsed.confidence_interval) is tuple
    assert type(parsed.limitations) is tuple


@pytest.mark.parametrize(
    "change",
    [
        {"point_estimate": "1.25"},
        {"point_estimate": True},
        {"sample_size": True},
        {"sample_size": "40"},
        {"confidence_interval": [2.25, 0.25]},
        {"confidence_interval": [0.25, 1.25, 2.25]},
        {"confidence_interval": ["0.25", 2.25]},
        {"candidate_only": False},
        {"method": "unowned_method"},
        {"limitations": ["scientific_validity_not_established"]},
        {"unexpected": "field"},
    ],
)
def test_selected_cas_candidate_refuses_invalid_complete_json_values(
    tmp_path: Path,
    change: dict[str, Any],
) -> None:
    payload = _candidate().model_dump(mode="json")
    payload.update(change)
    store, selection, limits = _selected_candidate_case(tmp_path, payload)
    with pytest.raises(ValueError, match="direct_method_execution_candidate_outcome_invalid"):
        _validate_selection(store, selection, limits)


def test_selected_cas_candidate_requires_every_declared_required_field(tmp_path: Path) -> None:
    required = [
        name
        for name, field in MethodExecutionCandidateOutcome.model_fields.items()
        if field.is_required()
    ]
    assert required
    for name in required:
        payload = _candidate().model_dump(mode="json")
        del payload[name]
        store, selection, limits = _selected_candidate_case(tmp_path / name, payload)
        with pytest.raises(ValueError, match="direct_method_execution_candidate_outcome_invalid"):
            _validate_selection(store, selection, limits)


@pytest.mark.parametrize("non_json", ["tuple", "set", "model", "non_string_key", "nan", "inf"])
def test_candidate_json_wire_intake_refuses_non_json_python_carriers(non_json: str) -> None:
    payload = _candidate().model_dump(mode="json")
    if non_json == "tuple":
        payload["confidence_interval"] = (0.25, 2.25)
    elif non_json == "set":
        payload["limitations"] = set(payload["limitations"])
    elif non_json == "model":
        payload = _candidate()
    elif non_json == "non_string_key":
        payload[1] = "not a wire key"
    elif non_json == "nan":
        payload["point_estimate"] = float("nan")
    else:
        payload["point_estimate"] = float("inf")
    with pytest.raises(ValueError, match="method_execution_candidate_outcome_wire_payload_invalid"):
        MethodExecutionCandidateOutcome.from_json_payload(payload)


def test_selected_cas_candidate_replays_full_wire_and_keeps_semantic_mismatch_refusal(
    tmp_path: Path,
) -> None:
    candidate = _candidate()
    payload = candidate.model_dump(mode="json")
    store, selection, limits = _selected_candidate_case(tmp_path, payload)
    bounded = read_core_json_artifact_bounded(store, selection.method_evidence_ref, limits=limits)
    assert bounded.value["candidate_outcome"] == payload
    assert type(bounded.value["candidate_outcome"]["confidence_interval"]) is list
    _validate_selection(store, selection, limits)
    changed = candidate.model_copy(update={"estimand": "unbound-estimand"})
    altered_selection = selection.model_copy(update={"candidate_outcome": changed})
    with pytest.raises(ValueError, match="direct_method_execution_candidate_outcome_mismatch"):
        _validate_selection(store, altered_selection, limits)
    _validate_selection(store, selection, limits)


@pytest.mark.parametrize(
    ("protocol", "normalization"),
    [
        ("method_input_envelope_v1", "canonical_passthrough"),
        ("legacy_hte_json_v1", "legacy_to_method_input_envelope_v1"),
    ],
)
def test_public_worker_producer_and_fresh_candidate_reader_require_wire_admission(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    protocol: str,
    normalization: str,
) -> None:
    """Reuse the actual public producer/worker oracle, then remove only JSON wire admission."""
    runtime_api_env = request.getfixturevalue("selected_source_runtime_api_env")
    accepted: list[dict[str, Any]] = []
    post = fixture._post_runtime_api_as_fixture_owner

    def observe_post(*args: Any, **kwargs: Any) -> Any:
        response = post(*args, **kwargs)
        if args[1] == "/api/v1/control/runs" and response.status_code == 200:
            accepted.append(response.json())
        return response

    monkeypatch.setattr(fixture, "_post_runtime_api_as_fixture_owner", observe_post)
    # This is a real selected source -> POST -> worker -> MethodBackend -> CAS -> GET
    # path with the existing bounded native fixture and assertions. It grants no
    # scientific or institutional authority to that candidate.
    fixture.test_post_worker_fenced_cas_and_fresh_run_get_preserve_candidate_limits(
        request,
        monkeypatch,
        protocol,
        normalization,
    )
    assert len(accepted) == 1
    owner = accepted[0]
    service = runtime_api_env["app"].state._control_service
    with tenant_scope(
        None,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    ):
        selected = service.get_method_execution_selection(
            run_id=owner["run_id"],
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=runtime_api_env["cell_a"],
        )
        assert isinstance(selected, DirectMethodExecutionSelection)
        assert selected.candidate_outcome is not None
        fresh_store = FileSystemCAS(Path(runtime_api_env["cas_root"]))
        fresh_store = fresh_store.with_ambient_ownership_enforcement()
        limits = CoreJsonReadLimits(
            max_bytes=1_048_576,
            max_depth=32,
            max_elements=100_000,
            max_manifest_bytes=65_536,
        )
        bounded = read_core_json_artifact_bounded(
            fresh_store,
            selected.method_evidence_ref,
            limits=limits,
        )
        payload = bounded.value["candidate_outcome"]
        assert type(payload["limitations"]) is list
        assert payload == selected.candidate_outcome.model_dump(mode="json")
        expected_payload = copy.deepcopy(payload)
        _validate_selection(fresh_store, selected, limits)

        def old_python_mode(
            cls: type[MethodExecutionCandidateOutcome],
            value: object,
        ) -> MethodExecutionCandidateOutcome:
            return cls.model_validate(value)

        with monkeypatch.context() as removal:
            removal.setattr(
                MethodExecutionCandidateOutcome,
                "from_json_payload",
                classmethod(old_python_mode),
            )
            with pytest.raises(
                ValueError,
                match="direct_method_execution_candidate_outcome_invalid",
            ) as error:
                _validate_selection(fresh_store, selected, limits)
            assert isinstance(error.value.__cause__, ValidationError)
            assert any(
                row["type"] == "tuple_type" and row["loc"] == ("limitations",)
                for row in error.value.__cause__.errors()
            )
        assert payload == expected_payload
        _validate_selection(fresh_store, selected, limits)
