"""Consume one retained SQL result through aggregate-bounded source admission.

This opt-in target reopens the existing one-execute candidate. It does not query
SQL, execute a graph, issue source permission, or create a new artifact.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Literal, NoReturn, cast

import pytest

from polisyos.core.artifacts import (
    ArtifactBoundedManifestRead,
    ArtifactID,
    ArtifactRef,
    ArtifactStoreReadUsage,
    CoreJSONArtifactBoundedMemberAttempt,
    CoreJSONArtifactBoundedMemberReader,
    CoreJsonReadBoundsRefusalError,
    FileSystemCAS,
    InputRef,
    artifact_ref_identity_key,
    validate_core_model_json_artifact,
)
from polisyos.core.contracts import (
    DATA_SNAPSHOT_LINEAGE_SCHEMA_VERSION,
    DATA_SNAPSHOT_SEMANTIC_INPUT_LINEAGE_SCHEMA_VERSION,
    REGISTERED_SQL_MEASUREMENT_LIMITATIONS,
    FoundryInputBindingsRef,
    SimulationResultRef,
)
from polisyos.core.contracts.decision_validity import RegisteredSQLAdmissionBinding
from polisyos.core.contracts.foundry import StateSnapshot
from polisyos.core.security import tenant_scope
from polisyos.foundry.data_plane.bindings import (
    load_input_bindings,
    reconcile_semantic_input_bindings,
)
from polisyos.foundry.execute.api import (
    BoundedSemanticInputReader,
    ExecutionSourceAdmission,
    ExecutionSourceAdmissionRefusal,
    ExecutionSourceBoundedReadRefusal,
    admit_execution_source_bounded,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
    _BoundedExecutionSourceReader,
    _ProjectionReadBudget,
    _UnestablishedProjectionError,
)
from tests.integration.core_runtime.test_retained_registered_sql_semantic_execution import (
    _assert_original_sources,
    _immutable_source_hashes,
    _selection,
)

_WRONG_SOURCE_BINDING_ENV = "POLISYOS_TEST_RETAINED_SQL_WRONG_SOURCE_BINDING_REF"
_DEFAULT_REPLAY_BUDGET = 64 * 1024 * 1024
_UNBOUNDED_STORE_METHODS = (
    "get_manifest",
    "get_bytes",
    "get_raw_manifest_bytes",
    "verify",
    "open_member",
    "put_bytes",
    "put_json",
)


class _BoundedCASReceiptBoundary:
    """Expose only genuine bounded receipts from the configured read-only CAS."""

    __slots__ = ("_store", "manifest_receipts", "member_attempts")

    def __init__(self, store: CoreJSONArtifactBoundedMemberReader) -> None:
        self._store = store
        self.manifest_receipts: list[ArtifactStoreReadUsage] = []
        self.member_attempts: list[CoreJSONArtifactBoundedMemberAttempt] = []

    def read_raw_manifest_bytes_bounded(
        self,
        artifact_id: ArtifactID | ArtifactRef,
        *,
        max_manifest_bytes: int,
        manifest_profile_sha256: str | None = None,
    ) -> ArtifactBoundedManifestRead:
        """Delegate one bounded manifest read with its immutable owner receipt."""
        receipt = self._store.read_raw_manifest_bytes_bounded(
            artifact_id,
            max_manifest_bytes=max_manifest_bytes,
            manifest_profile_sha256=manifest_profile_sha256,
        )
        self.manifest_receipts.append(receipt.usage)
        return receipt

    def read_raw_manifest_bytes_bounded_for_input(
        self,
        input_ref: InputRef,
        *,
        max_manifest_bytes: int,
    ) -> ArtifactBoundedManifestRead:
        """Delegate one bounded lineage-manifest read with its owner receipt."""
        receipt = self._store.read_raw_manifest_bytes_bounded_for_input(
            input_ref,
            max_manifest_bytes=max_manifest_bytes,
        )
        self.manifest_receipts.append(receipt.usage)
        return receipt

    def open_member_bounded(
        self,
        artifact_id: ArtifactRef,
        member: Literal["blob"],
        *,
        max_manifest_bytes: int,
        expected_manifest_sha256: str,
        max_member_bytes: int,
    ) -> CoreJSONArtifactBoundedMemberAttempt:
        """Delegate one bounded selected-member attempt to the CAS owner."""
        attempt = self._store.open_member_bounded(
            artifact_id,
            member,
            max_manifest_bytes=max_manifest_bytes,
            expected_manifest_sha256=expected_manifest_sha256,
            max_member_bytes=max_member_bytes,
        )
        self.member_attempts.append(attempt)
        return attempt

    @property
    def observed_receipt_bytes(self) -> int:
        """Sum owner-reported bytes from the bounded receipts used so far."""
        observed = [usage.observed_source_bytes for usage in self.manifest_receipts]
        observed.extend(attempt.usage.observed_source_bytes for attempt in self.member_attempts)
        assert all(type(count) is int and count >= 0 for count in observed)
        return sum(cast("int", count) for count in observed)


class _RecordingBoundedExecutionSourceReader(_BoundedExecutionSourceReader):
    """Keep semantic views so the test can verify use of the shared owner budget."""

    def __init__(self, store: _BoundedCASReceiptBoundary, budget: _ProjectionReadBudget) -> None:
        super().__init__(store, budget)
        self.semantic_views: list[tuple[BoundedSemanticInputReader, int]] = []

    def semantic_input_reader(self) -> BoundedSemanticInputReader:
        """Retain the actual operation-local bounded view and its opening count."""
        view = super().semantic_input_reader()
        self.semantic_views.append((view, view.observed_source_bytes))
        return view


@contextmanager
def _temporarily_withheld_blob(path: Path) -> Iterator[None]:
    """Remove one selected immutable blob for a refusal probe, then restore it."""
    assert path.is_file()
    backup = path.with_name(path.name + ".temporarily-withheld")
    assert not backup.exists()
    path.rename(backup)
    try:
        yield
    finally:
        backup.rename(path)


def _blob_path(cas_root: Path, ref: ArtifactRef) -> Path:
    """Return the canonical CAS blob member for one full content reference."""
    digest = ref.artifact_id.hex
    return cas_root / "artifacts" / "sha256" / digest[:2] / digest[2:4] / f"{digest}.blob"


def _retained_case() -> tuple[
    Path,
    FoundryInputBindingsRef,
    SimulationResultRef,
    str,
    str,
]:
    """Read the explicit retained input, result, scope and output locators."""
    cas_root, input_ref, output, tenant, cell = _selection()
    report = json.loads(output.read_text())
    assert report["stage"] == "public_execute_returned"
    assert report["scope"] == "candidate_only_current_C105_permission_not_established"
    assert report["response"]["ok"] is True
    assert artifact_ref_identity_key(
        FoundryInputBindingsRef.model_validate(report["input_bindings_ref"])
    ) == artifact_ref_identity_key(input_ref)
    assert artifact_ref_identity_key(
        FoundryInputBindingsRef.model_validate(report["request"]["input_bindings_ref"])
    ) == artifact_ref_identity_key(input_ref)
    result_ref = SimulationResultRef.model_validate(report["response"]["simulation_result_ref"])
    assert result_ref.kind == "foundry.simulation_result"
    assert result_ref.media_type == "application/json"
    assert result_ref.manifest_profile_sha256 is not None
    return cas_root, input_ref, result_ref, tenant, cell


def _bounded_reader(
    store: CoreJSONArtifactBoundedMemberReader,
    *,
    max_bytes: int = _DEFAULT_REPLAY_BUDGET,
) -> tuple[
    _BoundedCASReceiptBoundary, _RecordingBoundedExecutionSourceReader, _ProjectionReadBudget
]:
    boundary = _BoundedCASReceiptBoundary(store)
    budget = _ProjectionReadBudget(max_bytes=max_bytes)
    return boundary, _RecordingBoundedExecutionSourceReader(boundary, budget), budget


def _forbid_new_production(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail if retained admission reaches execution, dispatch, or SQL production."""
    import polisyos.foundry.execute.api as execute_api
    from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
    from polisyos.scientist.adapters.fabric_bridge import DefaultFabricPort
    from polisyos.scientist.adapters.registered_sql_admission import RegisteredSQLProducer

    def unexpected(*_args: object, **_kwargs: object) -> NoReturn:
        pytest.fail("retained_bounded_source_admission_must_remain_read_only")

    monkeypatch.setattr(execute_api, "execute", unexpected)
    monkeypatch.setattr(execute_api, "execute_program_graph", unexpected)
    monkeypatch.setattr(MethodDispatcher, "dispatch", unexpected)
    monkeypatch.setattr(RegisteredSQLProducer, "acquire_and_admit", unexpected)
    monkeypatch.setattr(DefaultFabricPort, "_snapshot_with_execution", unexpected)


def _admit(
    boundary: _BoundedCASReceiptBoundary,
    reader: _RecordingBoundedExecutionSourceReader,
    result_ref: SimulationResultRef,
) -> ExecutionSourceAdmission:
    return admit_execution_source_bounded(boundary, result_ref, reader=reader)


def _assert_retained_admission(
    admission: ExecutionSourceAdmission,
    input_ref: FoundryInputBindingsRef,
    result_ref: SimulationResultRef,
) -> None:
    """Check the exact retained source chain and candidate-only SQL limits."""
    assert admission.mode == "single_step_basis"
    assert artifact_ref_identity_key(admission.simulation_result_ref) == (
        artifact_ref_identity_key(result_ref)
    )
    assert admission.simulation_result.execution_source_status == "single_step_basis"
    assert admission.basis_ref is not None
    assert admission.basis_ref.manifest_profile_sha256 is not None
    assert admission.simulation_result.execution_input_basis_ref is not None
    assert artifact_ref_identity_key(admission.basis_ref) == artifact_ref_identity_key(
        admission.simulation_result.execution_input_basis_ref
    )
    assert admission.basis is not None
    assert artifact_ref_identity_key(admission.basis.input_bindings_ref) == (
        artifact_ref_identity_key(input_ref)
    )
    source_ref = admission.basis.registered_sql_admission_ref
    assert source_ref is not None
    assert source_ref.kind == RegisteredSQLAdmissionBinding.ARTIFACT_KIND
    assert source_ref.manifest_profile_sha256 is not None
    candidate_ref = admission.basis.candidate_ref
    assert candidate_ref.kind == "scientist.policy_design.candidate"
    assert candidate_ref.manifest_profile_sha256 is not None
    assert set(admission.semantic_input_limitation_codes or ()) == set(
        REGISTERED_SQL_MEASUREMENT_LIMITATIONS
    )
    assert len(admission.semantic_input_limitation_codes or ()) == 8


def _assert_bounded_owner_usage(
    boundary: _BoundedCASReceiptBoundary,
    reader: _RecordingBoundedExecutionSourceReader,
    budget: _ProjectionReadBudget,
    admission: ExecutionSourceAdmission,
    *,
    starting_bytes: int = 0,
    starting_receipt_bytes: int = 0,
) -> None:
    """Reconcile the admission count to nonzero receipts from its shared owner."""
    assert budget.source_usage_established
    observed_bytes = budget.observed_execution_source_bytes - starting_bytes
    observed_receipt_bytes = boundary.observed_receipt_bytes - starting_receipt_bytes
    assert observed_bytes > 0
    assert admission.source_read_bytes == observed_bytes
    assert observed_receipt_bytes == observed_bytes
    assert len(reader.semantic_views) == 1
    view, opening_bytes = reader.semantic_views[0]
    assert not any(hasattr(view, name) for name in ("put_bytes", "put_json"))
    assert view.observed_source_bytes > opening_bytes


@pytest.mark.integration
def test_retained_registered_sql_semantic_input_uses_bounded_admission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reopen the exact saved SQL result and reconcile all 8 candidate limits."""
    cas_root, input_ref, result_ref, tenant, cell = _retained_case()
    original = _immutable_source_hashes(cas_root)
    _forbid_new_production(monkeypatch)
    with tenant_scope(None, tenant_id=tenant, cell_id=cell):
        store = FileSystemCAS.open_existing_read_only(cas_root)
        assert not any(hasattr(store, name) for name in ("put_bytes", "put_json"))
        boundary, reader, budget = _bounded_reader(store)
        assert not any(hasattr(boundary, name) for name in _UNBOUNDED_STORE_METHODS)
        admission = _admit(boundary, reader, result_ref)
        _assert_retained_admission(admission, input_ref, result_ref)
        _assert_bounded_owner_usage(boundary, reader, budget, admission)
    _assert_original_sources(cas_root, original)


@pytest.mark.integration
def test_retained_registered_sql_semantic_input_refuses_small_shared_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An aggregate cap returns the typed bounded-read refusal without fallback."""
    cas_root, _input_ref, result_ref, tenant, cell = _retained_case()
    _forbid_new_production(monkeypatch)
    with tenant_scope(None, tenant_id=tenant, cell_id=cell):
        store = FileSystemCAS.open_existing_read_only(cas_root)
        boundary, reader, budget = _bounded_reader(store, max_bytes=1)
        assert not any(hasattr(boundary, name) for name in _UNBOUNDED_STORE_METHODS)
        with pytest.raises(ExecutionSourceBoundedReadRefusal) as refused:
            _admit(boundary, reader, result_ref)
    assert refused.value.reason == "method_metric_source_bytes_exceed_bounded_admission"
    assert refused.value.limit_bytes == 1
    assert budget.observed_execution_source_bytes <= budget.max_bytes


@pytest.mark.integration
def test_retained_registered_sql_semantic_input_rejects_grafted_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A valid profile from another artifact cannot select this result's manifest."""
    cas_root, input_ref, result_ref, tenant, cell = _retained_case()
    _forbid_new_production(monkeypatch)
    with tenant_scope(None, tenant_id=tenant, cell_id=cell):
        store = FileSystemCAS.open_existing_read_only(cas_root)
        boundary, reader, _budget = _bounded_reader(store)
        admitted = _admit(boundary, reader, result_ref)
        _assert_retained_admission(admitted, input_ref, result_ref)
        assert admitted.basis is not None
        assert admitted.basis.registered_sql_admission_ref is not None
        foreign_profile = admitted.basis.registered_sql_admission_ref.manifest_profile_sha256
        assert foreign_profile is not None
        assert foreign_profile != result_ref.manifest_profile_sha256
        grafted_result_ref = result_ref.model_copy(
            update={"manifest_profile_sha256": foreign_profile}
        )
        denied_boundary, denied_reader, _denied_budget = _bounded_reader(store)
        with pytest.raises(_UnestablishedProjectionError) as refused:
            _admit(denied_boundary, denied_reader, grafted_result_ref)
    assert str(refused.value) == "selected_manifest_bounded_read_outcome_not_established"
    core_refusal = refused.value.__cause__
    assert type(core_refusal) is CoreJsonReadBoundsRefusalError
    assert getattr(core_refusal, "code", None) == "selected_artifact_not_found"
    assert getattr(core_refusal, "failure_stage", None) == "selected_manifest_open_status"
    assert type(core_refusal.__cause__) is FileNotFoundError


@pytest.mark.integration
@pytest.mark.parametrize(
    "missing_member",
    ["fabric_tabular_payload_json", "state_snapshot_npz"],
)
def test_retained_registered_sql_semantic_input_denies_missing_payload_and_restores(
    missing_member: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing selected SQL payload or NPZ bytes refuse, restore, then admit unchanged."""
    cas_root, input_ref, result_ref, tenant, cell = _retained_case()
    original = _immutable_source_hashes(cas_root)
    _forbid_new_production(monkeypatch)
    with tenant_scope(None, tenant_id=tenant, cell_id=cell):
        store = FileSystemCAS.open_existing_read_only(cas_root)
        boundary, reader, _baseline_budget = _bounded_reader(store)
        baseline = _admit(boundary, reader, result_ref)
        _assert_retained_admission(baseline, input_ref, result_ref)
        assert baseline.basis is not None
        if missing_member == "fabric_tabular_payload_json":
            assert baseline.basis.registered_sql_admission_ref is not None
            view = reader.semantic_input_reader()
            source = validate_core_model_json_artifact(
                RegisteredSQLAdmissionBinding,
                view,
                baseline.basis.registered_sql_admission_ref,
            )
            assert source.materialization.payload_ref.kind == "fabric.tabular_payload"
            selected_blob = _blob_path(cas_root, source.materialization.payload_ref)
            snapshot_manifest, _ = reader.read_selected_manifest(baseline.basis.data_snapshot_ref)
            snapshot_schema_version = (
                snapshot_manifest.artifact_schema.version
                if snapshot_manifest.artifact_schema is not None
                else None
            )
        else:
            _state_manifest, state_snapshot, _manifest_bytes, _payload_bytes = (
                reader.read_typed_model(
                    StateSnapshot,
                    baseline.basis.bound_state_snapshot_ref,
                )
            )
            selected_blob = _blob_path(cas_root, state_snapshot.state_ref)
        expected_blob_digest = hashlib.sha256(selected_blob.read_bytes()).hexdigest()
        with _temporarily_withheld_blob(selected_blob):
            denied_boundary, denied_reader, _denied_budget = _bounded_reader(store)
            if missing_member == "fabric_tabular_payload_json":
                owner_lineage_schemas = {
                    DATA_SNAPSHOT_LINEAGE_SCHEMA_VERSION,
                    DATA_SNAPSHOT_SEMANTIC_INPUT_LINEAGE_SCHEMA_VERSION,
                }
                expected_reason = (
                    "DataSnapshot owner-lineage child ref is unverified"
                    if snapshot_schema_version in owner_lineage_schemas
                    else "DataSnapshot selected nested reference profile does not resolve: data_ref"
                )
                with pytest.raises(ExecutionSourceAdmissionRefusal) as refused:
                    _admit(denied_boundary, denied_reader, result_ref)
                assert refused.value.reason == expected_reason
                wrapped_refusal = refused.value.__cause__
                assert type(wrapped_refusal) is ValueError
                core_refusal = wrapped_refusal.__cause__
                assert type(core_refusal) is CoreJsonReadBoundsRefusalError
                assert getattr(core_refusal, "code", None) == "selected_artifact_not_found"
                assert getattr(core_refusal, "failure_stage", None) == "bounded_member_open_status"
                assert type(core_refusal.__cause__) is FileNotFoundError
                assert core_refusal.__cause__.filename == str(selected_blob)
            else:
                with pytest.raises(FileNotFoundError) as refused:
                    _admit(denied_boundary, denied_reader, result_ref)
                assert type(refused.value) is FileNotFoundError
                assert refused.value.filename == str(selected_blob)
        assert selected_blob.is_file()
        assert hashlib.sha256(selected_blob.read_bytes()).hexdigest() == expected_blob_digest
        restored_boundary, restored_reader, restored_budget = _bounded_reader(store)
        restored = _admit(restored_boundary, restored_reader, result_ref)
        _assert_retained_admission(restored, input_ref, result_ref)
        _assert_bounded_owner_usage(restored_boundary, restored_reader, restored_budget, restored)
    _assert_original_sources(cas_root, original)


@pytest.mark.integration
def test_retained_registered_sql_semantic_replay_rejects_same_value_wrong_source_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A persisted sibling's same payload cannot substitute its source snapshot."""
    negative_json = os.environ.get(_WRONG_SOURCE_BINDING_ENV)
    if negative_json is None:
        pytest.skip(f"requires {_WRONG_SOURCE_BINDING_ENV} with an explicit full ref JSON")
    cas_root, input_ref, _result_ref, tenant, cell = _retained_case()
    wrong_source_ref = FoundryInputBindingsRef.model_validate_json(negative_json)
    _forbid_new_production(monkeypatch)
    with tenant_scope(None, tenant_id=tenant, cell_id=cell):
        store = FileSystemCAS.open_existing_read_only(cas_root)
        boundary, reader, budget = _bounded_reader(store)
        assert not any(hasattr(boundary, name) for name in _UNBOUNDED_STORE_METHODS)
        view = reader.semantic_input_reader()
        correct_bindings = load_input_bindings(view, input_ref)
        wrong_bindings = load_input_bindings(view, wrong_source_ref)
        assert correct_bindings.schema_version == "1.3"
        assert wrong_bindings.schema_version == "1.3"
        assert artifact_ref_identity_key(wrong_bindings.data_snapshot_ref) == (
            artifact_ref_identity_key(correct_bindings.data_snapshot_ref)
        )
        assert correct_bindings.registered_sql_admission_ref is not None
        assert wrong_bindings.registered_sql_admission_ref is not None
        assert artifact_ref_identity_key(wrong_bindings.registered_sql_admission_ref) != (
            artifact_ref_identity_key(correct_bindings.registered_sql_admission_ref)
        )
        correct_source = validate_core_model_json_artifact(
            RegisteredSQLAdmissionBinding,
            view,
            correct_bindings.registered_sql_admission_ref,
        )
        wrong_source = validate_core_model_json_artifact(
            RegisteredSQLAdmissionBinding,
            view,
            wrong_bindings.registered_sql_admission_ref,
        )
        assert artifact_ref_identity_key(correct_source.materialization.payload_ref) == (
            artifact_ref_identity_key(wrong_source.materialization.payload_ref)
        )
        assert artifact_ref_identity_key(correct_source.materialization.snapshot_ref) != (
            artifact_ref_identity_key(wrong_source.materialization.snapshot_ref)
        )
        with pytest.raises(ValueError, match=r"^registered_sql_binding_snapshot_mismatch$"):
            reconcile_semantic_input_bindings(view, wrong_bindings)
        assert budget.source_usage_established
        assert budget.remaining_bytes > 0
        assert budget.observed_execution_source_bytes == view.observed_source_bytes
        assert boundary.observed_receipt_bytes == budget.observed_execution_source_bytes
        assert not any(hasattr(view, name) for name in ("put_bytes", "put_json"))
