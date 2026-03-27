from __future__ import annotations

import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.state_keys import (
    INPUT_GRAPH_PRIOR_BUNDLE_REF,
    INPUT_REGISTRY_BUNDLE_REF,
)
from polisyos.scientist.workflows.builder import (
    run_default_workflow,
    run_policy_design_workflow,
    run_policy_verified_workflow,
)


def _ref(seed: str, kind: str = "scientist.test") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.model_validate(f"sha256:{seed * 64}"),
        kind=kind,
        media_type="application/json",
    )


def test_policy_workflow_rejects_mismatched_graph_prior_refs_before_execution(tmp_path) -> None:
    state = ExperimentState(
        run_id="R_policy_pin_mismatch",
        params={
            "policy_mode": True,
            "graph_prior_bundle_ref": _ref("1", "scientist.graph_prior_bundle").model_dump(
                mode="json"
            ),
        },
        inputs={
            INPUT_GRAPH_PRIOR_BUNDLE_REF: _ref("2", "scientist.graph_prior_bundle"),
        },
    )

    with pytest.raises(ValueError, match="graph_prior_bundle_ref"):
        run_policy_design_workflow(
            state,
            store=FileSystemCAS(tmp_path),
        )


@pytest.mark.parametrize(
    ("runner", "workflow_id"),
    [
        (run_default_workflow, "scientist_default"),
        (run_policy_verified_workflow, "scientist_policy_verified"),
    ],
)
def test_non_policy_workflows_reject_mismatched_registry_refs_before_execution(
    tmp_path,
    runner,
    workflow_id: str,
) -> None:
    state = ExperimentState(
        run_id=f"R_{workflow_id}",
        params={
            "registry_bundle_ref": _ref("1", "core.registry_bundle").model_dump(mode="json"),
        },
        inputs={
            INPUT_REGISTRY_BUNDLE_REF: _ref("2", "core.registry_bundle"),
        },
    )

    with pytest.raises(ValueError, match="registry_bundle_ref"):
        runner(
            state,
            store=FileSystemCAS(tmp_path),
        )
