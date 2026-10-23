from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from polisyos.core.artifacts import ArtifactRef, artifact_manifest_profile_sha256
from polisyos.core.artifacts.manifest import (
    ArtifactGovernanceInfo,
    InputRef,
    ProducerInfo,
    SchemaInfo,
)
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec
from polisyos.fabric.catalog.source_selection_audit import build_fabric_source_selection_trace
from polisyos.runtime.http.services.control.artifacts import write_runtime_authority_artifact
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality.authority import GovernanceMetadata, SameInputClosure
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from tests.unit.fabric.test_source_selection_audit import _source
from tests.unit.tools.test_canary_evidence import (
    _completed_quality_job_payload,
    _quality_evidence_content_only,
)
from tools.ops_runners.runtime.canary_evidence import assemble_canary_evidence

pytestmark = pytest.mark.usefixtures("canary_diagnostic_output_root")


_FABRIC_TRACE_KIND = "fabric.retrieval_trace"
_FABRIC_TRACE_SCHEMA = "polisyos.fabric.SourceSelectionTrace"
_FABRIC_TRACE_COMPONENT = "polisyos.runtime.quality.fabric_retrieval_trace"
_FABRIC_TRACE_REF_KEY = "fabric_retrieval_trace_ref"
_RUN_ID = "R_runtime_quality_refs"
_JOB_ID = "job-runtime-quality-refs"
_TENANT_ID = "tenant-1"
_CELL_ID = "cell-a"

_FIELD_REFS_OMITTED = object()


def _fabric_trace_source_payload(
    field_refs: object,
    *,
    query_outcome: str,
    preprojected_field_refs: list[str] | None = None,
    include_required_fields: bool = True,
) -> dict[str, Any]:
    compatibility: dict[str, object] = {"status": "pass"}
    if include_required_fields:
        compatibility["required_fields"] = ["msme_survival_rate", "wartime_credit_support"]
    source = _source(
        source_id="production-msme-panel",
        schema_compatibility=compatibility,
    )
    if field_refs is _FIELD_REFS_OMITTED:
        source.pop("field_refs", None)
    else:
        source["field_refs"] = field_refs
    if preprojected_field_refs is not None:
        source["source_facets"] = {"field_refs": list(preprojected_field_refs)}
    return {
        "query_intent": {
            "policy_domain": "wartime_msme_support",
            "query_outcome": query_outcome,
            "query_treatment": "wartime_credit_support",
        },
        "candidate_sources": [source],
        "selected_source_ids": ["production-msme-panel"],
        "rejected_sources": [],
        "expected_source_families": ["production_msme_panel"],
        "canary_kind": "production",
    }


def _persist_runtime_fabric_trace(
    store: FileSystemCAS,
    event_log: RuntimeDiagnosticEventLog,
    source_payload: dict[str, Any],
) -> tuple[ArtifactRef, dict[str, Any]]:
    """Persist a controlled trace; its input closure remains deliberately unclosed."""

    source_ref = store.put_json(
        source_payload,
        ArtifactWriteOptions(
            kind="fabric.source_selection_input",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.fabric.SourceSelectionInput", version="1.0"),
            producer=ProducerInfo(
                component="tests.fabric.source_selection_input",
                version="controlled-test-input",
            ),
        ),
        CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    persisted_source_payload = json.loads(store.get_bytes(source_ref))
    trace_payload = build_fabric_source_selection_trace(**persisted_source_payload)
    report_payload = {
        **trace_payload,
        "runtime_authority_payload": {
            "schema_version": "policyos.runtime.authority_payload_marker.v1",
            "report_key": "fabric_retrieval_trace",
            "ref_key": _FABRIC_TRACE_REF_KEY,
            "projection": False,
        },
    }
    source_input = InputRef(
        artifact_id=source_ref.artifact_id,
        role="fabric_source_selection_input",
        manifest_profile_sha256=source_ref.manifest_profile_sha256,
    )
    options = ArtifactWriteOptions(
        kind=_FABRIC_TRACE_KIND,
        media_type="application/json",
        schema=SchemaInfo(name=_FABRIC_TRACE_SCHEMA, version="1.0"),
        producer=ProducerInfo(
            component=_FABRIC_TRACE_COMPONENT,
            version="2026.05.15+hds-phase2.4",
        ),
        governance=ArtifactGovernanceInfo(classification="runtime_quality_evidence"),
        inputs=[source_input],
    )
    closure = SameInputClosure(
        closure_id=f"{_RUN_ID}:{_FABRIC_TRACE_REF_KEY}",
        status="not_closed",
        run_id=_RUN_ID,
        job_id=_JOB_ID,
        tenant_id=_TENANT_ID,
        cell_id=_CELL_ID,
        evidence_input_refs=(str(source_ref.artifact_id),),
    )
    result = write_runtime_authority_artifact(
        store,
        event_log,
        report_payload,
        options,
        evidence_id=f"runtime_quality_ref#{_FABRIC_TRACE_REF_KEY}",
        evidence_class="authority_bearing",
        authority_role="runtime_blocker",
        provenance_kind="runtime_blocker",
        owner="team-runtime",
        reader_contract="runtime_quality.fabric_retrieval_trace.v1",
        reader_contract_version="1.0",
        tenant_id=_TENANT_ID,
        cell_id=_CELL_ID,
        run_id=_RUN_ID,
        job_id=_JOB_ID,
        trace_id="trace-canary-fabric-admission-test",
        span_id="fabric-retrieval-trace:cas_write",
        parent_span_id=None,
        requested_execution_profile="production",
        effective_execution_profile="production",
        phase="fabric_retrieval_trace",
        generated_at="2026-10-23T08:30:00+00:00",
        as_of_time="2026-10-23T08:30:00+00:00",
        same_input_closure=closure,
        input_refs=(str(source_ref.artifact_id),),
        effective_mode_ref="runtime-mode:production",
        validation_status=("pass" if trace_payload["status"] == "pass" else "fail"),
        blocking_status="blocking",
        governance=GovernanceMetadata(
            classification="runtime_quality_evidence",
            authority_boundary="runtime_control_plane",
            pii="redacted_or_absent",
            retention_policy="runtime_quality_retention",
            review_status="machine_checked",
            override_policy="no_silent_override",
            approval_policy="scorecard_readiness_required",
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return result.cas_ref, trace_payload


@pytest.mark.parametrize(
    (
        "field_refs",
        "preprojected_field_refs",
        "include_required_fields",
        "expected_status",
        "expected_normalized_field_refs",
    ),
    [
        pytest.param(
            _FIELD_REFS_OMITTED,
            None,
            True,
            "pass",
            ["msme_survival_rate", "wartime_credit_support"],
            id="absent-uses-required-fields-fallback",
        ),
        pytest.param(None, None, True, "fail", [], id="present-null-does-not-fallback"),
        pytest.param([], None, True, "fail", [], id="present-empty-list-does-not-fallback"),
        pytest.param("", None, True, "fail", [], id="present-empty-string-does-not-fallback"),
        pytest.param(False, None, True, "fail", [], id="present-false-does-not-fallback"),
        pytest.param(17, None, True, "fail", [], id="present-scalar-does-not-fallback"),
        pytest.param(
            {"field_ref": 17},
            None,
            True,
            "fail",
            [],
            id="present-malformed-mapping-does-not-fallback",
        ),
        pytest.param(
            ["field:prod-msme-panel.income"],
            None,
            True,
            "pass",
            ["field:prod-msme-panel.income"],
            id="provided-recognized-reference-is-admitted",
        ),
        pytest.param(
            [],
            ["field:preprojected.valid"],
            True,
            "fail",
            [],
            id="present-empty-alias-overrides-valid-preprojected-facet",
        ),
        pytest.param(
            {"field_ref": 17},
            ["field:preprojected.valid"],
            True,
            "fail",
            [],
            id="present-malformed-alias-overrides-valid-preprojected-facet",
        ),
        pytest.param(
            _FIELD_REFS_OMITTED,
            ["field:preprojected.valid"],
            False,
            "pass",
            ["field:preprojected.valid"],
            id="absent-alias-preserves-preprojected-facet-without-fallback",
        ),
    ],
)
def test_canary_scorecard_recomputes_selected_field_references_from_runtime_cas(
    tmp_path: Path,
    field_refs: object,
    preprojected_field_refs: list[str] | None,
    include_required_fields: bool,
    expected_status: str,
    expected_normalized_field_refs: list[str],
) -> None:
    store = FileSystemCAS(tmp_path / "cas").for_tenant(_TENANT_ID, cell_id=_CELL_ID)
    control_store = ControlPlaneStore(
        backend="sqlite",
        sqlite_path=tmp_path / "control.sqlite3",
    )
    event_log = RuntimeDiagnosticEventLog(store=control_store, artifact_store=store)

    selected_ref, producer_trace = _persist_runtime_fabric_trace(
        store,
        event_log,
        _fabric_trace_source_payload(
            field_refs,
            query_outcome="msme_survival_rate",
            preprojected_field_refs=preprojected_field_refs,
            include_required_fields=include_required_fields,
        ),
    )
    manifest = store.get_manifest(selected_ref)
    selected_profile = artifact_manifest_profile_sha256(manifest)
    selector = ArtifactRef(
        artifact_id=selected_ref.artifact_id,
        kind=manifest.kind,
        media_type=manifest.media_type,
        manifest_profile_sha256=selected_profile,
    )
    assert manifest.kind == _FABRIC_TRACE_KIND
    assert manifest.same_input_closure is not None
    assert manifest.same_input_closure.status == "not_closed"
    assert manifest.same_input_closure.closure_sha256 is None
    assert manifest.artifact_schema is not None
    assert manifest.artifact_schema.name == _FABRIC_TRACE_SCHEMA
    assert manifest.producer is not None
    assert manifest.producer.component == _FABRIC_TRACE_COMPONENT
    assert selected_ref.manifest_profile_sha256 == selected_profile
    persisted_events = event_log.list_events(run_id=_RUN_ID, job_id=_JOB_ID)
    assert len(persisted_events) == 1
    assert persisted_events[0].event.payload_ref == str(selected_ref.artifact_id)
    assert producer_trace["status"] == expected_status

    job_payload = _completed_quality_job_payload(include_runtime_quality_refs=False)
    progress = job_payload["progress"]
    assert isinstance(progress, dict)
    details = progress["details"]
    assert isinstance(details, dict)
    details["runtime_quality_refs"] = {_FABRIC_TRACE_REF_KEY: str(selected_ref.artifact_id)}
    details["runtime_quality_artifact_refs"] = {
        _FABRIC_TRACE_REF_KEY: selector.model_dump(mode="json")
    }

    inline_trace = build_fabric_source_selection_trace(
        **_fabric_trace_source_payload(
            ["field:inline-overlay-only"],
            query_outcome="unselected-inline-overlay",
        )
    )
    quality_evidence = _quality_evidence_content_only()
    quality_evidence["fabric_retrieval_trace"] = inline_trace

    output = assemble_canary_evidence(
        output_root=tmp_path / "bundle",
        canary_kind="production",
        command_metadata={"argv": ["policyos-canary", "--real"]},
        request_payload={"request": "Evaluate Ukraine MSME support."},
        job_payload=job_payload,
        provider_preflight={"status": "passed"},
        quality_evidence=quality_evidence,
        artifact_store=store,
    )

    trace_path = output / "quality_evidence" / "fabric_retrieval_trace.json"
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    scorecard = json.loads(
        (output / "quality_evidence" / "quality_scorecard.json").read_text(encoding="utf-8")
    )
    semantic_gate_code = (
        "fabric_retrieval_trace_present"
        if expected_status == "pass"
        else "selected_source_missing_field_refs"
    )
    gate = next(
        item
        for item in scorecard["quality_gates"]
        if item["name"] == "fabric_retrieval_trace_present" and item["code"] == semantic_gate_code
    )
    authority_gate = next(
        item
        for item in scorecard["quality_gates"]
        if item["name"] == "fabric_retrieval_trace_present" and item["code"] != semantic_gate_code
    )
    assert authority_gate["status"] == "fail"
    assert authority_gate["blocking"] is True
    evidence_refs = scorecard["evidence_refs"]
    assert evidence_refs[_FABRIC_TRACE_REF_KEY] == str(selected_ref.artifact_id)
    assert trace["status"] == expected_status
    assert trace["query_intent"]["query_outcome"] == "msme_survival_rate"
    assert trace["query_intent"]["query_outcome"] != "unselected-inline-overlay"
    selected_source = trace["selected_sources"][0]
    if field_refs is _FIELD_REFS_OMITTED:
        assert "field_refs" not in selected_source
    else:
        assert selected_source["field_refs"] == field_refs
    assert selected_source["source_facets"]["field_refs"] == expected_normalized_field_refs
    assert gate["status"] == expected_status
    if expected_status == "fail":
        assert "selected_source_missing_field_refs" in {issue["code"] for issue in trace["issues"]}
        assert any(
            failure["gate"] == "fabric_retrieval_trace_present"
            and failure["code"] == "selected_source_missing_field_refs"
            for failure in scorecard["blocking_quality_failures"]
        )
    else:
        assert "selected_source_missing_field_refs" not in {
            issue["code"] for issue in trace["issues"]
        }
