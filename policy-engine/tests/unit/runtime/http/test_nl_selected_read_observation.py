"""Real admitted NL helper reads reach a freshly reopened diagnostic surface.

The trace witness invokes actual compiled nested helpers inside their real live
NL invocation, then stops before external/model work. It proves the bounded
mechanical read/progress bridge, not completed NL or temporal execution.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import CodeType, FrameType
from typing import Any

import pytest

from polisyos.core.artifacts import ArtifactRef, FileSystemCAS, ProducerInfo, PutOptions, SchemaInfo
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.fabric import DataSnapshotRef
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.http.execution_policy import RuntimeExecutionPolicyResolver
from polisyos.runtime.http.services.control import ControlPlaneService
from polisyos.runtime.http.services.control.nl_pipeline import NaturalLanguageRunMixin
from tests.unit.runtime.http.test_nl_pipeline_materialization import (
    _intent_context,
    _prepare_running_scoped_control_job,
    _registry_providers,
)


class _ObservationComplete(BaseException):
    """Stop the controlled invocation without being converted to workflow failure."""


def _pipeline_code() -> CodeType:
    return next(
        constant
        for constant in NaturalLanguageRunMixin._execute_nl_pipeline_impl.__code__.co_consts
        if isinstance(constant, CodeType) and constant.co_name == "_agent_pipeline"
    )


def _service(tmp_path: Path, store: FileSystemCAS) -> ControlPlaneService:
    return ControlPlaneService(
        artifact_store=store,
        cas_root=tmp_path / "cas",
        core_runs_root=tmp_path / "runs",
        policy_resolver=RuntimeExecutionPolicyResolver(
            default_profile="dev",
            worker_backend="external",
            state_store_backend="sqlite",
            sqlite_path=str(tmp_path / "control.sqlite3"),
            postgres_dsn=None,
        ),
        registry_providers=_registry_providers(),
    )


@pytest.mark.parametrize(
    "carrier", [ArtifactRef, DataSnapshotRef], ids=["core-ref", "real-subclass"]
)
def test_actual_selected_helper_read_persists_diagnostic_facts_to_fresh_job_surface(
    tmp_path: Path,
    carrier: type[ArtifactRef],
) -> None:
    store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-intent", cell_id="cell-intent")
    payload = {"observed": 7}
    options = PutOptions(
        kind="fabric.data_snapshot",
        media_type="application/json",
        schema=SchemaInfo(name="polisyos.tests.C38SelectedRead", version="1.0"),
        producer=ProducerInfo(component="polisyos.tests.selected_read", version="1.0"),
    )
    with tenant_scope(None, tenant_id="tenant-intent", cell_id="cell-intent"):
        # Same ASCII payload bytes, distinct full manifest/canonical profiles.
        # B is the default; explicitly selected A must never be changed to B.
        default_b = store.put_json(
            payload, options, CanonSpec(ensure_ascii=True), return_selected_profile=True
        )
        selected_a = store.put_json(
            payload, options, CanonSpec(ensure_ascii=False), return_selected_profile=True
        )
    assert selected_a.artifact_id == default_b.artifact_id
    assert selected_a.manifest_profile_sha256 != default_b.manifest_profile_sha256
    selected = carrier.model_validate(selected_a.model_dump(mode="json"))
    wrong_profile = selected_a.model_copy(update={"manifest_profile_sha256": "sha256:" + "0" * 64})
    missing = selected_a.model_copy(update={"artifact_id": "sha256:" + "f" * 64})
    run_id, job_id = "R_c38_observed", "job_c38_observed"
    context = _intent_context(requested_authority_level="dev")
    service = _service(tmp_path, store)
    fence = _prepare_running_scoped_control_job(
        service._control_store,
        job_id=job_id,
        run_id=run_id,
        effective_profile="dev",
        context=context,
    )
    code = _pipeline_code()
    observed: dict[str, Any] = {}
    prior_trace = sys.gettrace()

    def trace(frame: FrameType, event: str, argument: Any) -> Any:
        if event != "line" or frame.f_code is not code:
            return trace
        required = ("_load_json_artifact_payload", "_emit_job_progress", "_runtime_quality_profile")
        if not all(name in frame.f_locals for name in required) or observed:
            return trace
        helper = frame.f_locals["_load_json_artifact_payload"]
        emitter = frame.f_locals["_emit_job_progress"]
        # These are the actual nested production code objects in the real frame,
        # not AST copies, rewritten helpers, monkeypatches, or store callbacks.
        observed["selected"] = helper(selected)
        observed["second_profile"] = helper(default_b)
        observed["default"] = helper(str(default_b.artifact_id))
        observed["wrong_profile"] = helper(wrong_profile)
        observed["missing"] = helper(missing)
        emitter(phase="selected_read_regression_observed")
        raise _ObservationComplete

    try:
        with tenant_scope(None, tenant_id="tenant-intent", cell_id="cell-intent"), fence:
            sys.settrace(trace)
            with pytest.raises(_ObservationComplete):
                service._execute_nl_pipeline_for_contract_testing(
                    run_id=run_id,
                    nl_request="Bounded selected-read observation.",
                    context=context,
                    domain_hint=None,
                    data_source=None,
                    max_iterations=1,
                    llm_models=[],
                    max_parallel_models=1,
                    run_budget_usd=None,
                    per_model_budget_usd=None,
                    checkpoint_policy="strict",
                    execution_plan_ref=None,
                    execution_plan_payload=None,
                    stop_criteria_payload={},
                    governance_constraints_payload=[],
                    expected_outputs_payload=[],
                    control_job_id=job_id,
                    execution_profile="dev",
                )
    finally:
        sys.settrace(prior_trace)
        service.close()
    assert observed == {
        "selected": payload,
        "second_profile": payload,
        "default": payload,
        "wrong_profile": None,
        "missing": None,
    }
    # A separately opened service/store reads durable progress, not the captured
    # local list or a response returned from the producing invocation.
    fresh_store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-intent", cell_id="cell-intent")
    fresh_service = _service(tmp_path, fresh_store)
    try:
        with tenant_scope(None, tenant_id="tenant-intent", cell_id="cell-intent"):
            response = fresh_service.get_job_status(job_id).model_dump(mode="json")
        progress = response["progress"]
        assert progress["phase"] == "selected_read_regression_observed"
        facts = progress["selected_read_observations"]
        assert len(facts) == 3
        assert [fact["selected_ref"]["manifest_profile_sha256"] for fact in facts] == [
            selected_a.manifest_profile_sha256,
            default_b.manifest_profile_sha256,
            default_b.manifest_profile_sha256,
        ]
        assert [fact["selection_origin"] for fact in facts] == [
            "explicit_selected_ref",
            "explicit_selected_ref",
            "default_view_at_read",
        ]
        assert [fact["ordinal"] for fact in facts] == [0, 1, 2]
        for fact in facts:
            assert fact["payload_sha256"] == str(selected_a.artifact_id)
            assert fact["run_id"] == run_id and fact["job_id"] == job_id
            assert fact["tenant_id"] == "tenant-intent" and fact["cell_id"] == "cell-intent"
            assert fact["read_fact_basis"] == "recomputed"
            assert fact["purpose_completeness_basis"] == "not_established"
            assert fact["authority_role"] == "diagnostic_only"
            assert fact["matching_registered_output_owner"] is None
        assert response["projection_source"]["authority_level"] == "projection_only"
    finally:
        fresh_service.close()
