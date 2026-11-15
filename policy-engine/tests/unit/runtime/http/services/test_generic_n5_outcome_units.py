"""Generic N5 unit projections reopen the selected model registry."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.core.artifacts import ArtifactRef, FileSystemCAS
from polisyos.core.registry import build_registry_bundle, load_registry_bundle_content
from polisyos.ir.kernel import (
    ConstraintRegistry,
    MechanismTypeRegistry,
    MergeRuleRef,
    MergeRuleRegistry,
    MoneyUnit,
    SlotKind,
    SlotRegistry,
    SlotScope,
    SlotSpec,
    SlotValueType,
    UnitRef,
    UnitsRegistry,
)
from polisyos.pdc import PolicySlotBinding
from polisyos.runtime.http.services import acquisition_n5_projection


def _selected_bundle(
    tmp_path: Path,
    *,
    unit_id: str = "eur",
    include_unit: bool = True,
) -> tuple[FileSystemCAS, ArtifactRef]:
    """Persist one selected, non-USD registry bundle for a displayed balance."""
    store = FileSystemCAS(tmp_path)
    slot = SlotSpec(
        slot_id="government.balance",
        scope=SlotScope.GLOBAL,
        kind=SlotKind.STOCK,
        value_type=SlotValueType.DECIMAL,
        unit=UnitRef(unit_id=unit_id),
        merge_rule=MergeRuleRef(rule_id="sum"),
        state_path="government.balance",
    )
    bundle = build_registry_bundle(
        store,
        slot_registry=SlotRegistry(slots={slot.slot_id: slot}),
        merge_registry=MergeRuleRegistry(),
        mechanism_registry=MechanismTypeRegistry(),
        constraint_registry=ConstraintRegistry(),
        units_registry=(
            UnitsRegistry(units={unit_id: MoneyUnit(currency="EUR" if unit_id == "eur" else "GBP")})
            if include_unit
            else UnitsRegistry()
        ),
        return_selected_profile=True,
    )
    return store, bundle.bundle_ref


def _unit_projection_request(
    store: Any,
    registry_ref: ArtifactRef,
) -> tuple[Any, Any, Any]:
    """Bind one plan and result to the actual reopened selected slot registry."""
    registries = load_registry_bundle_content(store, registry_ref)
    graph_ref = ArtifactRef(
        artifact_id="sha256:" + "a" * 64,
        kind="foundry.program_graph",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "b" * 64,
    )
    exec_plan_ref = ArtifactRef(
        artifact_id="sha256:" + "c" * 64,
        kind="foundry.exec_plan",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "d" * 64,
    )
    plan = SimpleNamespace(
        engine_kind="program_graph",
        program_graph_ref=graph_ref,
        exec_plan_ref=exec_plan_ref,
        slot_registry=registries.slot_registry,
        variable_map={"government.balance": "government.balance"},
        outcome_aggregations={},
    )
    request = SimpleNamespace(
        engine_plan=(plan,),
        selected_outcomes=("government.balance",),
        world_model_record=SimpleNamespace(
            policy_slot_map=(
                PolicySlotBinding(
                    slot_id="government.balance",
                    state_path="government.balance",
                    unit="eur",
                    entity_scope="government",
                    temporal_granularity="month",
                ),
            )
        ),
    )
    result = SimpleNamespace(
        selected_outcomes=("government.balance",),
        trajectories=(),
    )

    def selected_views(_record: object) -> object:
        return SimpleNamespace(
            program_graph_refs=(graph_ref,),
            registry_bundle_ref=registry_ref,
        )

    return request, result, selected_views


def test_generic_outcome_units_reopen_selected_non_usd_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A unit follows the selected slot and unit artifacts, not the outcome name."""
    store, registry_ref = _selected_bundle(tmp_path / "selected")
    request, result, selected_views = _unit_projection_request(store, registry_ref)
    monkeypatch.setattr(
        "polisyos.runtime.quality.world_model_record.world_model_artifact_views",
        selected_views,
    )

    fields = acquisition_n5_projection._generic_program_graph_outcome_unit_fields(
        store, request, result
    )

    assert fields == {
        "outcome_units": {"government.balance": "eur"},
        "outcome_units_status": "resolved",
        "outcome_unit_registry_ref": registry_ref,
    }


def test_generic_outcome_units_limit_foreign_registry_and_missing_unit(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A foreign selected bundle or absent UnitSpec cannot produce a unit."""
    selected_store, selected_ref = _selected_bundle(tmp_path / "selected")
    foreign_store, foreign_ref = _selected_bundle(tmp_path / "foreign", unit_id="gbp")
    request, result, selected_views = _unit_projection_request(selected_store, selected_ref)
    monkeypatch.setattr(
        "polisyos.runtime.quality.world_model_record.world_model_artifact_views",
        lambda _record: SimpleNamespace(
            program_graph_refs=(request.engine_plan[0].program_graph_ref,),
            registry_bundle_ref=foreign_ref,
        ),
    )

    foreign = acquisition_n5_projection._generic_program_graph_outcome_unit_fields(
        foreign_store, request, result
    )
    assert foreign == {
        "outcome_units_status": "not_established",
        "outcome_units_limitation_code": "generic_n5_outcome_unit_slot_registry_mismatch",
    }
    assert "outcome_units" not in foreign
    assert "outcome_unit_registry_ref" not in foreign

    missing_store, missing_ref = _selected_bundle(tmp_path / "missing", include_unit=False)
    request, result, selected_views = _unit_projection_request(missing_store, missing_ref)
    monkeypatch.setattr(
        "polisyos.runtime.quality.world_model_record.world_model_artifact_views",
        selected_views,
    )
    missing = acquisition_n5_projection._generic_program_graph_outcome_unit_fields(
        missing_store, request, result
    )
    assert missing == {
        "outcome_units_status": "not_established",
        "outcome_units_limitation_code": "generic_n5_outcome_unit_policy_binding_mismatch",
    }


def test_generic_outcome_units_require_matching_aggregation_and_execution_witness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A caller aggregation declaration cannot replace the recorded slot witness."""
    store, registry_ref = _selected_bundle(tmp_path / "selected")
    request, result, selected_views = _unit_projection_request(store, registry_ref)
    monkeypatch.setattr(
        "polisyos.runtime.quality.world_model_record.world_model_artifact_views",
        selected_views,
    )
    request.engine_plan[0].outcome_aggregations = {
        "government.balance": SimpleNamespace(unit="usd")
    }
    mismatch = acquisition_n5_projection._generic_program_graph_outcome_unit_fields(
        store, request, result
    )
    assert mismatch == {
        "outcome_units_status": "not_established",
        "outcome_units_limitation_code": "generic_n5_outcome_unit_aggregation_mismatch",
    }

    request.engine_plan[0].outcome_aggregations = {
        "government.balance": SimpleNamespace(unit="eur")
    }
    missing_witness = acquisition_n5_projection._generic_program_graph_outcome_unit_fields(
        store, request, result
    )
    assert missing_witness == {
        "outcome_units_status": "not_established",
        "outcome_units_limitation_code": "generic_n5_outcome_unit_execution_witness_missing",
    }

    result.trajectories = (
        SimpleNamespace(
            points=(
                SimpleNamespace(
                    engine_state={
                        "replication_engine_states": [
                            {
                                "outcome_aggregation_basis": {
                                    "government.balance": {
                                        "unit": "eur",
                                        "unit_binding_status": "matched_producer_slot",
                                        "unit_slot_id": "government.balance",
                                    }
                                }
                            }
                        ]
                    }
                ),
            )
        ),
    )
    matched = acquisition_n5_projection._generic_program_graph_outcome_unit_fields(
        store, request, result
    )
    assert matched == {
        "outcome_units": {"government.balance": "eur"},
        "outcome_units_status": "resolved",
        "outcome_unit_registry_ref": registry_ref,
    }


@pytest.mark.parametrize("engine_plan_count", [1, 2])
def test_present_unsupported_n5_request_keeps_unit_status_limited(
    engine_plan_count: int,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A present non-ProgramGraph or multi-engine request is explicit NE."""
    store, registry_ref = _selected_bundle(tmp_path / "selected")
    request, result, selected_views = _unit_projection_request(store, registry_ref)
    request.engine_plan = (
        (SimpleNamespace(engine_kind="ncm_parallel_worlds"),)
        if engine_plan_count == 1
        else (
            request.engine_plan[0],
            SimpleNamespace(engine_kind="ncm_parallel_worlds"),
        )
    )
    monkeypatch.setattr(
        "polisyos.runtime.quality.world_model_record.world_model_artifact_views",
        selected_views,
    )

    fields = acquisition_n5_projection._generic_program_graph_outcome_unit_fields(
        store, request, result
    )

    assert fields == {
        "outcome_units_status": "not_established",
        "outcome_units_limitation_code": "generic_n5_outcome_unit_program_graph_not_selected",
    }
