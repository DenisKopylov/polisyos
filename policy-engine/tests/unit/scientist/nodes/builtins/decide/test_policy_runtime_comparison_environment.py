"""Behavioral comparison controls built from an actual public Foundry source."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any

import pytest
from unit.scientist.nodes.builtins.decide.test_policy_runtime_method_metrics import (
    _exercise_public_execute_method_metric_source,
)

from polisyos.core.artifacts import validate_core_model_json_artifact
from polisyos.core.contracts.foundry import MethodExecutionBundle
from polisyos.scientist.nodes.builtins.decide import policy_runtime_method_metrics as metrics

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def comparison_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Keep the real captured environment and selected plan; execute no replacement."""
    source = _exercise_public_execute_method_metric_source(tmp_path, monkeypatch)
    store = source["store"]
    bundle = validate_core_model_json_artifact(MethodExecutionBundle, store, source["bundle_ref"])
    ref = bundle.environment_manifest_ref
    assert ref is not None
    import json

    return {
        **source,
        "raw": json.loads(store.get_bytes(ref)),
        "manifest": store.get_manifest(ref),
        "plan_ref": bundle.exec_plan_ref,
    }


def test_actual_environment_reconciles_plan_without_erasing_semantics(
    comparison_source: dict[str, Any],
) -> None:
    """A captured producer source is projected without changing its persisted bytes."""
    source = comparison_source
    raw = source["raw"]
    original = deepcopy(raw)
    projected = metrics._ex_ante_comparison_environment(
        raw, manifest=source["manifest"], plan_ref=source["plan_ref"]
    )
    assert raw == original
    assert raw["custom_metadata"]["exec_plan_id"] == str(source["plan_ref"].artifact_id)
    assert projected == {
        **{key: value for key, value in original.items() if key != "captured_at"},
        "custom_metadata": {
            key: value
            for key, value in original["custom_metadata"].items()
            if key != "exec_plan_id"
        },
    }


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong_id",
        "missing_id",
        "malformed_id",
        "profile",
        "missing_edge",
        "unknown_top_level",
        "unknown",
    ],
)
def test_ranking_refuses_environment_with_unreconciled_plan_or_unknown_metadata(
    comparison_source: dict[str, Any], monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    """The actual ranking path must consume reconciliation, not just carry its markers."""
    source = comparison_source
    original = metrics._ex_ante_comparison_environment

    def corrupt(raw: Any, *, manifest: Any, plan_ref: Any) -> dict[str, Any]:
        changed = deepcopy(raw)
        if mutation == "wrong_id":
            changed["custom_metadata"]["exec_plan_id"] = "sha256:" + "f" * 64
        elif mutation == "missing_id":
            del changed["custom_metadata"]["exec_plan_id"]
        elif mutation == "malformed_id":
            changed["custom_metadata"]["exec_plan_id"] = [str(plan_ref.artifact_id)]
        elif mutation == "profile":
            plan_ref = plan_ref.model_copy(update={"manifest_profile_sha256": "sha256:" + "f" * 64})
        elif mutation == "missing_edge":
            manifest = manifest.model_copy(
                update={"inputs": [edge for edge in manifest.inputs if edge.role != "exec_plan"]}
            )
        elif mutation == "unknown_top_level":
            changed["unregistered_environment_switch"] = True
        else:
            changed["custom_metadata"]["unknown_semantic_switch"] = True
        return original(changed, manifest=manifest, plan_ref=plan_ref)

    monkeypatch.setattr(metrics, "_ex_ante_comparison_environment", corrupt)
    result = metrics.recompute_completed_ex_ante_rank_projection(
        source["store"], basis=source["projection"].basis, candidate_ref=source["candidate_ref"]
    )
    assert result.status != "selected"
    assert result.comparison_contract_sha256 is None
    assert result.maximizing_coordinate is None


@pytest.mark.parametrize("field", ["seed", "loaded_method_identities", "backend"])
def test_ranking_comparison_retains_actual_environment_semantic_fields(
    comparison_source: dict[str, Any], monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    """Same numerical result with a changed semantic environment cannot compare equal."""
    source = comparison_source
    before = metrics.recompute_completed_ex_ante_rank_projection(
        source["store"], basis=source["projection"].basis, candidate_ref=source["candidate_ref"]
    )
    original = metrics._ex_ante_comparison_environment

    def drift(raw: Any, *, manifest: Any, plan_ref: Any) -> dict[str, Any]:
        changed = deepcopy(raw)
        if field == "backend":
            changed["jax"]["default_backend"] = "different_actual_backend"
        elif field == "seed":
            changed["custom_metadata"][field] += 1
        else:
            changed["custom_metadata"][field] = [
                *changed["custom_metadata"][field],
                {"additional_actual_method": True},
            ]
        return original(changed, manifest=manifest, plan_ref=plan_ref)

    monkeypatch.setattr(metrics, "_ex_ante_comparison_environment", drift)
    after = metrics.recompute_completed_ex_ante_rank_projection(
        source["store"], basis=source["projection"].basis, candidate_ref=source["candidate_ref"]
    )
    assert before.status == after.status == "selected"
    assert before.maximizing_coordinate == after.maximizing_coordinate
    assert before.comparison_contract_sha256 != after.comparison_contract_sha256
