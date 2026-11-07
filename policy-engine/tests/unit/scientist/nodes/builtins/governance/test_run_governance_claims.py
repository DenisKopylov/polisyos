from __future__ import annotations

import logging

import pytest

from polisyos.core.artifacts import artifact_manifest_profile_sha256
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.nodes.builtins.governance.run_governance import (
    RunGovernanceNode,
    _extract_pii_scan_results,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CLAIMS_REF,
    INPUT_DATA_SNAPSHOT_REF,
    REPORT_GOVERNANCE_REPORT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.validation.policy_verified.models import (
    SourceVerificationReport,
    persist_source_verification_report,
)


def test_governance_rejects_selected_workflow_with_decision_artifact_without_claims_ref(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_governance_naked_claim_gate",
    )
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.governance.naked_claim_gate"),
    )
    policy_bundle_ref = ArtifactRef(
        artifact_id="sha256:" + "b" * 64,
        kind="scientist.policy_artifact_bundle",
        media_type="application/json",
    )
    source_report_ref = persist_source_verification_report(
        store, SourceVerificationReport(request_id="synthetic", notes=["fixture_only"])
    )
    state = ExperimentState(
        run_id="R_governance_naked_claim_gate",
        artifacts_index={
            "policy_output_bundle_ref": policy_bundle_ref,
            "source_verification_report_ref": source_report_ref,
        },
        params={
            "governance_profile": "fast",
            "workflow_id": "scientist_policy_design",
            "scientist.best_in_class.wave1.phase1_1.fail_on_naked_claims": True,
        },
    )

    outcome = RunGovernanceNode().execute(ctx, state)
    report_ref = outcome.state.reports_index[REPORT_GOVERNANCE_REPORT_REF]
    report = from_canonical_bytes(store.get_bytes(report_ref.artifact_id))
    report_manifest = store.get_manifest(report_ref)

    assert outcome.status == "ok"
    assert report["verdict"] == "reject"
    # The stale policy projection is archived, while the actual selected
    # source-verification artifact remains subject to the claims gate.
    assert "policy_output_bundle_ref" not in outcome.state.artifacts_index
    assert outcome.state.artifacts_index["source_verification_report_ref"] == source_report_ref
    assert report["links"]["source_verification_report_ref"]["artifact_id"] == str(
        source_report_ref.artifact_id
    )
    assert ARTIFACT_CLAIMS_REF not in outcome.state.artifacts_index
    assert report["links"].get("claims_ref") is None
    assert report_ref.kind == "scientist.governance_report"
    assert report_ref.media_type == "application/json"
    assert report_ref.manifest_profile_sha256 == artifact_manifest_profile_sha256(report_manifest)
    assert report_manifest.artifact_schema is not None
    assert report_manifest.artifact_schema.name == "polisyos.scientist.GovernanceReport"
    assert report_manifest.artifact_schema.version == "1.0"
    assert any(issue["code"] == "claim_ledger_owner_not_established" for issue in report["issues"])
    assert any(
        issue["code"] == "claim_spine.naked_decision_claims"
        and issue["details"]["status"] == "blocked"
        and issue["details"]["violations"] == ["missing_claims_ref_for_decision_bearing_state"]
        for issue in report["issues"]
    )


def test_governance_pii_reader_refuses_same_snapshot_bytes_under_wrong_schema(
    execution_context,
) -> None:
    store = execution_context.store
    data_ref = store.put_json(
        {"rows": []},
        PutOptions(kind="fabric.tabular_payload", media_type="application/json"),
    )
    snapshot_ref = store.put_json(
        DataSnapshot(
            data_ref=data_ref,
            pii_scan_summary={"max_severity": "none", "total_entities_found": 0},
        ),
        PutOptions(
            kind=DataSnapshot.ARTIFACT_KIND,
            media_type=DataSnapshot.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
                version=DataSnapshot.ARTIFACT_SCHEMA_VERSION,
            ),
        ),
    )
    manifest = store.get_manifest(snapshot_ref)
    wrong_profile_ref = store.put_bytes(
        store.get_bytes(snapshot_ref),
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=SchemaInfo(name="polisyos.test.DataSnapshot", version="9.9"),
            canon=manifest.canon,
        ),
        return_selected_profile=True,
    )
    state = ExperimentState(
        run_id="R_governance_wrong_snapshot_owner",
        inputs={INPUT_DATA_SNAPSHOT_REF: wrong_profile_ref},
    )

    with pytest.raises(ValueError, match="canon_profile_typed_artifact_schema_name_mismatch"):
        _extract_pii_scan_results(execution_context, state)
