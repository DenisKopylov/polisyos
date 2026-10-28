"""Terminal run indexing selects the state and report bound by the workflow owner."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef, ArtifactTenantContextInfo, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.run.context import RunContext
from polisyos.core.trace import RunTerminality
from polisyos.runtime.http.services.adapters.core_run import load_core_run
from polisyos.scientist.orchestration.engine.executor import WorkflowReport
from polisyos.scientist.orchestration.engine.finalization import (
    FINAL_WORKFLOW_REPORT_STATE_PATH,
    FINALIZATION_KIND,
    FINALIZATION_SCHEMA_NAME,
    FINALIZATION_SCHEMA_VERSION,
    FinalizationOutputBinding,
    WorkflowStateFinalization,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import WorkflowSpec


def _put(
    store: FileSystemCAS,
    payload: Any,
    *,
    kind: str,
    name: str,
    version: str,
    tenant_context: ArtifactTenantContextInfo | None = None,
) -> ArtifactRef:
    return store.put_json(
        payload,
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name=name, version=version),
            tenant_context=tenant_context,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )


def _run_with_finalization(
    root: Path,
    *,
    fault: str = "",
    extra_finalization: bool = False,
    reverse_state_order: bool = False,
    earlier_report: bool = False,
) -> tuple[FileSystemCAS, Path, ArtifactRef, ArtifactRef, ArtifactRef]:
    store = FileSystemCAS(root / "cas")
    registry = _put(
        store, {"registry": "fixture"}, kind="core.registry_bundle", name="registry", version="1.0"
    )
    run_id = "R_terminal_index"
    run = RunContext.start(store=store, registry_bundle=registry, run_id=run_id)
    spec = WorkflowSpec(workflow_id="indexed_workflow")
    spec_ref = _put(
        store,
        spec.model_dump(),
        kind="scientist.workflow_spec",
        name="polisyos.scientist.orchestration.engine.WorkflowSpec",
        version="1.0",
    )
    run.add_input(spec_ref)
    report = WorkflowReport(
        workflow_id="wrong_workflow" if fault == "report_workflow" else spec.workflow_id,
        run_id="R_other" if fault == "report_run" else run_id,
        error_policy="continue",
        status="ok",
    )
    report_ref = _put(
        store,
        report.model_dump(),
        kind="scientist.workflow_report",
        name="polisyos.scientist.orchestration.engine.WorkflowReport",
        version="9.9" if fault == "report_schema" else "1.0",
    )
    prior = ExperimentState(
        run_id="R_other" if fault == "prior_state_run" else run_id,
        params={"marker": "producer state"},
    )
    prior_ref = _put(
        store,
        prior.model_dump(),
        kind="scientist.experiment_state",
        name="polisyos.scientist.orchestration.engine.ExperimentState",
        version=prior.schema_version,
    )
    final = prior.model_copy(deep=True)
    final.run_id = run_id
    final.reports_index["workflow_report"] = report_ref
    if fault == "state_payload_schema":
        final.schema_version = "9.9"
    if fault == "state_oversized":
        final.params["large_candidate"] = "x" * (9 * 1024 * 1024)
    if fault == "state_run":
        final.run_id = "R_other"
    if fault == "state_report_ref":
        final.reports_index = {}
    final_ref = _put(
        store,
        final.model_dump(),
        kind="scientist.experiment_state",
        name="polisyos.scientist.orchestration.engine.ExperimentState",
        version="9.9" if fault == "state_schema" else "1.3",
    )
    refs = [prior_ref, final_ref]
    if reverse_state_order:
        refs.reverse()
    if fault == "final_not_owned":
        refs.remove(final_ref)
    if earlier_report:
        earlier = report.model_copy(update={"status": "fail"})
        earlier_ref = _put(
            store,
            earlier.model_dump(),
            kind="scientist.workflow_report",
            name="polisyos.scientist.orchestration.engine.WorkflowReport",
            version="1.0",
        )
        run.add_output(earlier_ref)
    for ref in [*refs, report_ref]:
        run.add_output(ref)
    receipt = WorkflowStateFinalization.create(
        run_id="R_other" if fault == "receipt_run" else run_id,
        workflow_id="wrong_workflow" if fault == "receipt_workflow" else spec.workflow_id,
        workflow_spec_ref=spec_ref,
        prior_state_ref=prior_ref,
        final_state_ref=final_ref,
        output_refs={FINAL_WORKFLOW_REPORT_STATE_PATH: report_ref},
    )
    if fault == "final_profile_missing":
        receipt = receipt.model_copy(
            update={
                "final_state_ref": final_ref.model_copy(update={"manifest_profile_sha256": None})
            }
        )
    if fault == "final_profile_wrong":
        receipt = receipt.model_copy(
            update={
                "final_state_ref": final_ref.model_copy(
                    update={"manifest_profile_sha256": "sha256:" + "f" * 64}
                )
            }
        )
    if fault == "duplicate_binding":
        receipt = receipt.model_copy(
            update={"output_bindings": (*receipt.output_bindings, *receipt.output_bindings)}
        )
    if fault == "unknown_binding":
        receipt = receipt.model_copy(
            update={
                "output_bindings": (
                    *receipt.output_bindings,
                    FinalizationOutputBinding(state_path="params.fake", artifact_ref=report_ref),
                )
            }
        )
    if extra_finalization:
        decoy = receipt.model_copy(update={"run_id": "R_decoy"})
        decoy_ref = _put(
            store,
            decoy.model_dump(mode="json"),
            kind=FINALIZATION_KIND,
            name=FINALIZATION_SCHEMA_NAME,
            version=FINALIZATION_SCHEMA_VERSION,
        )
        run.add_output(decoy_ref)
    receipt_ref = _put(
        store,
        receipt.model_dump(mode="json"),
        kind="other.finalization" if fault == "receipt_kind" else FINALIZATION_KIND,
        name=FINALIZATION_SCHEMA_NAME,
        version="9.9" if fault == "receipt_schema" else FINALIZATION_SCHEMA_VERSION,
        tenant_context=(
            ArtifactTenantContextInfo(tenant_id="other-tenant", cell_id="other-cell")
            if fault == "receipt_tenant"
            else None
        ),
    )
    run.add_output(receipt_ref)
    if fault == "duplicate_terminal_ref":
        run.add_output(receipt_ref)
    run.finalize(
        status="ok",
        workflow_finalization_ref=None if fault == "terminal_ref_absent" else receipt_ref,
    )
    assert run.trace_path is not None
    return store, run.trace_path.parent, prior_ref, final_ref, report_ref


@pytest.mark.parametrize("reverse_state_order", [False, True])
@pytest.mark.parametrize("extra_finalization", [False, True])
@pytest.mark.parametrize("earlier_report", [False, True])
def test_terminal_index_selects_owner_final_state_not_output_order(
    tmp_path: Path, reverse_state_order: bool, extra_finalization: bool, earlier_report: bool
) -> None:
    store, run_dir, prior_ref, final_ref, report_ref = _run_with_finalization(
        tmp_path,
        reverse_state_order=reverse_state_order,
        extra_finalization=extra_finalization,
        earlier_report=earlier_report,
    )
    indexed = load_core_run(store=store, run_dir=run_dir)
    assert indexed is not None
    assert indexed.run_terminality is RunTerminality.TERMINAL
    assert prior_ref != final_ref
    assert indexed.experiment_state_ref == final_ref
    assert indexed.workflow_report_ref == report_ref
    assert "core_run_workflow_finalization_unavailable" not in indexed.warnings


@pytest.mark.parametrize(
    "fault",
    [
        "receipt_run",
        "receipt_workflow",
        "receipt_schema",
        "receipt_kind",
        "receipt_tenant",
        "state_run",
        "prior_state_run",
        "state_schema",
        "state_payload_schema",
        "state_oversized",
        "state_report_ref",
        "report_run",
        "report_workflow",
        "report_schema",
        "duplicate_binding",
        "unknown_binding",
        "final_not_owned",
        "final_profile_missing",
        "final_profile_wrong",
        "duplicate_terminal_ref",
        "terminal_ref_absent",
    ],
)
def test_terminal_index_does_not_fallback_to_prior_for_invalid_owner_selection(
    tmp_path: Path, fault: str
) -> None:
    store, run_dir, _prior, _final, _report = _run_with_finalization(tmp_path, fault=fault)
    indexed = load_core_run(store=store, run_dir=run_dir)
    assert indexed is not None
    assert indexed.experiment_state_ref is None
    assert indexed.workflow_report_ref is None
    assert "core_run_workflow_finalization_unavailable" in indexed.warnings


class _DenyFinalizationRead(FileSystemCAS):
    def open_member_bounded(self, artifact_id: ArtifactRef, member: Any, **kwargs: Any) -> Any:
        if artifact_id.kind == FINALIZATION_KIND:
            raise PermissionError("test owner refuses selected finalization")
        return super().open_member_bounded(artifact_id, member, **kwargs)


def test_terminal_index_does_not_fallback_after_owner_permission_refusal(tmp_path: Path) -> None:
    store, run_dir, _prior, _final, _report = _run_with_finalization(tmp_path)
    blocked = _DenyFinalizationRead(store.root)
    indexed = load_core_run(store=blocked, run_dir=run_dir)
    assert indexed is not None
    assert indexed.experiment_state_ref is None
    assert indexed.workflow_report_ref is None
    assert "core_run_workflow_finalization_unavailable" in indexed.warnings


class _NoBoundedFinalizationReader(FileSystemCAS):
    open_member_bounded = None  # type: ignore[assignment]


def test_terminal_index_never_uses_an_unbounded_backend_fallback(tmp_path: Path) -> None:
    store, run_dir, _prior, _final, _report = _run_with_finalization(tmp_path)
    unsupported = _NoBoundedFinalizationReader(store.root)
    indexed = load_core_run(store=unsupported, run_dir=run_dir)
    assert indexed is not None
    assert indexed.experiment_state_ref is None
    assert indexed.workflow_report_ref is None
    assert "core_run_workflow_finalization_unavailable" in indexed.warnings


def test_legacy_terminal_without_finalizer_remains_explicit_candidate_history(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "legacy-cas")
    registry = _put(
        store, {"registry": "legacy"}, kind="core.registry_bundle", name="registry", version="1.0"
    )
    run = RunContext.start(store=store, registry_bundle=registry, run_id="R_legacy_index")
    legacy_state = ExperimentState(run_id="R_legacy_index")
    state_ref = _put(
        store,
        legacy_state.model_dump(),
        kind="scientist.experiment_state",
        name="polisyos.scientist.orchestration.engine.ExperimentState",
        version=legacy_state.schema_version,
    )
    run.add_output(state_ref)
    run.finalize(status="ok")
    assert run.trace_path is not None
    indexed = load_core_run(store=store, run_dir=run.trace_path.parent)
    assert indexed is not None
    assert indexed.experiment_state_ref == state_ref
    assert "core_run_workflow_finalization_not_established" in indexed.warnings


def test_nonterminal_without_finalizer_does_not_invent_terminal_selection(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "active-cas")
    registry = _put(
        store, {"registry": "active"}, kind="core.registry_bundle", name="registry", version="1.0"
    )
    run = RunContext.start(store=store, registry_bundle=registry, run_id="R_nonterminal_index")
    assert run.trace_path is not None
    indexed = load_core_run(store=store, run_dir=run.trace_path.parent)
    assert indexed is not None
    assert indexed.run_terminality is not RunTerminality.TERMINAL
    assert indexed.experiment_state_ref is None
    assert indexed.workflow_report_ref is None
    run.suspend_for_resume()
