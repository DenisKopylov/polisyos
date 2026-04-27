from __future__ import annotations

import logging

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.governance.run_governance import RunGovernanceNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CLAIMS_REF,
    REPORT_GOVERNANCE_REPORT_REF,
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
    state = ExperimentState(
        run_id="R_governance_naked_claim_gate",
        artifacts_index={"policy_output_bundle_ref": policy_bundle_ref},
        params={
            "governance_profile": "fast",
            "workflow_id": "scientist_policy_design",
            "scientist.best_in_class.wave1.phase1_1.fail_on_naked_claims": True,
        },
    )

    outcome = RunGovernanceNode().execute(ctx, state)
    report_ref = outcome.state.reports_index[REPORT_GOVERNANCE_REPORT_REF]
    report = from_canonical_bytes(store.get_bytes(report_ref.artifact_id))

    assert outcome.status == "ok"
    assert report["verdict"] == "reject"
    assert ARTIFACT_CLAIMS_REF in outcome.state.artifacts_index
    assert report["links"]["claims_ref"]["artifact_id"] == str(
        outcome.state.artifacts_index[ARTIFACT_CLAIMS_REF].artifact_id
    )
    assert any(
        issue["code"] == "claim_spine.naked_decision_claims"
        and issue["details"]["status"] == "blocked"
        and issue["details"]["violations"]
        == ["missing_claims_ref_for_decision_bearing_state"]
        for issue in report["issues"]
    )
