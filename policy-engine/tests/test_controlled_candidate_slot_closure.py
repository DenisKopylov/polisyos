"""Behavioral tests for selected, persisted candidate owner-slot fixtures."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

CANDIDATE_HELPER_PATH = (
    Path(__file__).parent / "_helpers" / "controlled_candidate_profile.py"
).resolve()
CANDIDATE_MODULE_NAME = "n4_selected_owner_slot_closure_candidate"
CANDIDATE_SPEC = importlib.util.spec_from_file_location(
    CANDIDATE_MODULE_NAME,
    CANDIDATE_HELPER_PATH,
)
if CANDIDATE_SPEC is None or CANDIDATE_SPEC.loader is None:
    raise RuntimeError("controlled_candidate_profile_candidate_import_unavailable")
CANDIDATE_HELPER = importlib.util.module_from_spec(CANDIDATE_SPEC)
sys.modules[CANDIDATE_MODULE_NAME] = CANDIDATE_HELPER
CANDIDATE_SPEC.loader.exec_module(CANDIDATE_HELPER)


def test_each_controlled_alias_keeps_one_requested_registry_identity() -> None:
    """The fixture registry contains only the exact requested alias for each class."""
    aliases = CANDIDATE_HELPER._CONTROLLED_SLOT_ALIASES
    assert len(aliases) == 7
    assert len(set(aliases.values())) == 6
    normalized_collisions = {
        alias: canonical
        for alias, canonical in aliases.items()
        if CANDIDATE_HELPER._controlled_auto_binding_id(alias)
        == CANDIDATE_HELPER._controlled_auto_binding_id(canonical)
    }
    assert normalized_collisions == {
        "agents_income": "agents.income",
        "agents_is_employed": "agents.is_employed",
        "cells_distress_score": "cells.distress_score",
        "global_tax_rate": "global.tax_rate",
        "government_balance": "government.balance",
    }

    from polisyos.foundry.data_plane.bindings import _auto_rules_from_payload
    from polisyos.ir.kernel import DEFAULT_SLOT_REGISTRY, SlotRegistry

    for alias, canonical in normalized_collisions.items():
        alias_spec = CANDIDATE_HELPER._controlled_selected_slot_specs(
            policy_slot_ids=(alias,),
            declared_ncm_outcomes=frozenset(),
            candidate_baseline_state=None,
            candidate_outcome_state_paths=None,
        )[alias]
        canonical_spec = DEFAULT_SLOT_REGISTRY.slots[canonical]
        selected_registry = SlotRegistry.model_validate(
            {
                "schema_version": DEFAULT_SLOT_REGISTRY.schema_version,
                "slots": {alias: alias_spec, canonical: canonical_spec},
                "notes": ["Collision witness only; no binding is admitted."],
            }
        )
        payload: dict[str, object] = {}
        CANDIDATE_HELPER._controlled_set_payload_path(
            payload,
            canonical_spec.state_path or "",
            0.0,
        )
        rules = _auto_rules_from_payload(slot_registry=selected_registry, payload=payload)
        assert len(rules) == 2
        assert len({rule.binding_id for rule in rules}) == 1

    for alias, canonical in aliases.items():
        resolved = CANDIDATE_HELPER._controlled_resolve_policy_slot_ids((alias,))
        assert resolved == ((alias, canonical),)
        specs = CANDIDATE_HELPER._controlled_selected_slot_specs(
            policy_slot_ids=(alias,),
            declared_ncm_outcomes=frozenset(),
            candidate_baseline_state=None,
            candidate_outcome_state_paths=None,
        )
        assert tuple(specs) == (alias,)
        assert specs[alias].slot_id == alias
        assert specs[alias].state_path == DEFAULT_SLOT_REGISTRY.slots[canonical].state_path
        assert specs[alias].unit.unit_id == "synthetic_score"


def test_incompatible_aliases_and_normalized_binding_ids_fail_closed() -> None:
    """No requested policy identity is silently replaced or dropped."""
    conflicts = (
        (("agents.income", "agents_income"), "auto_binding_identity_collision"),
        (("agents.is_employed", "agents_is_employed"), "auto_binding_identity_collision"),
        (("cells.distress_score", "cells_distress_score"), "auto_binding_identity_collision"),
        (("global.tax_rate", "global_tax_rate"), "auto_binding_identity_collision"),
        (("government.balance", "government_balance"), "auto_binding_identity_collision"),
        (("cells.employment", "employment_retention"), "selected_slot_alias_collision"),
        (
            ("employment_retention", "employment_retention_rate"),
            "selected_slot_alias_collision",
        ),
        (("firm_survival", "firm.survival"), "auto_binding_identity_collision"),
    )
    for requested_ids, expected_code in conflicts:
        with pytest.raises(ValueError, match=expected_code):
            CANDIDATE_HELPER._controlled_resolve_policy_slot_ids(requested_ids)


def test_unregistered_ncm_outcome_requires_persisted_declaration_and_baseline() -> None:
    """A requested toy outcome cannot be inferred from a name or an absent baseline."""
    with pytest.raises(ValueError, match="controlled_wmr_ncm_outcome_not_declared"):
        CANDIDATE_HELPER._controlled_selected_slot_specs(
            policy_slot_ids=("firm_survival",),
            declared_ncm_outcomes=frozenset(),
            candidate_baseline_state={"firm_survival": 0.0},
            candidate_outcome_state_paths={"firm_survival": "market.total_supply"},
        )
    with pytest.raises(ValueError, match="controlled_wmr_ncm_outcome_baseline_not_established"):
        CANDIDATE_HELPER._controlled_selected_slot_specs(
            policy_slot_ids=("firm_survival",),
            declared_ncm_outcomes=frozenset({"firm_survival"}),
            candidate_baseline_state=None,
            candidate_outcome_state_paths={"firm_survival": "market.total_supply"},
        )


def test_owner_built_candidate_outcome_is_persisted_and_read_back(tmp_path: Path) -> None:
    """The NCM, selected registry, payload, WMR, bindings, and state share owner bytes."""
    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.contracts.foundry import FoundryInputBindings
    from polisyos.core.registry import load_registry_bundle_content
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.foundry.execute.executor import load_state_snapshot
    from polisyos.ir.analytics.ncm import candidate_ncm_spec_from_declaration, load_ncm_spec
    from polisyos.runtime.http.resilience import guard_runtime_cas
    from polisyos.runtime.quality.world_model_record import (
        load_world_model_record,
        world_model_artifact_views,
    )

    product_root = Path.cwd().resolve()
    assert (product_root / "src/polisyos").is_dir()
    store = guard_runtime_cas(
        FileSystemCAS(tmp_path / "runtime-cas").with_ambient_ownership_enforcement()
    )
    try:
        problem = CANDIDATE_HELPER._problem("selected_owner_slot_closure")
        profile, declaration, build = CANDIDATE_HELPER._build_configured_procurement_profile(
            recorded_problem=problem,
            artifact_store=store,
            tenant_id="tenant-selected-slot-closure",
            cell_id="cell-selected-slot-closure",
            tmp_path=tmp_path,
            repo_root=product_root,
        )
        world = build.record
        with tenant_scope(
            None,
            tenant_id="tenant-selected-slot-closure",
            cell_id="cell-selected-slot-closure",
        ):
            persisted_world = load_world_model_record(store, build.record_ref)
            assert persisted_world == world
            assert persisted_world.authority_status == "limited"
            assert persisted_world.limitations.admissibility_blockers == (
                "source_time_not_established",
                "source_to_target_measurement_contract_not_established",
                "causal_coupling_not_established",
            )
            assert profile.context_inputs.world_model_record == persisted_world
            assert declaration.outcome_variable == "firm_survival"
            assert declaration.outcome_baseline == profile.n5.baseline_state["firm_survival"]
            assert profile.n5.baseline_state["firm_survival"] == 0.0

            views = world_model_artifact_views(persisted_world)
            assert len(views.ncm_refs) == 1
            assert persisted_world.simulation_model_ref.ncm_refs == tuple(
                str(ref.artifact_id) for ref in views.ncm_refs
            )
            selected_ncm = load_ncm_spec(
                CANDIDATE_HELPER._ensure_ir_artifact_store(store),
                views.ncm_refs[0],
            )
            assert "firm_survival" in selected_ncm.endogenous_vars
            assert any(
                equation.variable == "firm_survival"
                for equation in selected_ncm.structural_equations
            )
            assert selected_ncm == candidate_ncm_spec_from_declaration(declaration)

            selected_bundle = load_registry_bundle_content(store, views.registry_bundle_ref)
            selected_slots = selected_bundle.slot_registry.slots
            assert set(selected_slots) == {item.slot_id for item in persisted_world.policy_slot_map}
            assert "firm_survival" in selected_slots
            assert "government_balance" in selected_slots
            assert "government.balance" not in selected_slots
            assert selected_slots["firm_survival"].state_path == "market.total_supply"
            assert selected_slots["firm_survival"].unit.unit_id == "synthetic_score"

            persisted_bindings = FoundryInputBindings.model_validate(
                load_core_json_artifact(store, build.input_bindings_ref)
            )
            outcome_bindings = [
                rule for rule in persisted_bindings.rules if rule.target_slot_id == "firm_survival"
            ]
            assert len(outcome_bindings) == 1
            assert outcome_bindings[0].binding_id == "auto.firm_survival"
            assert outcome_bindings[0].source_path == "market.total_supply"
            reloaded_state = load_state_snapshot(
                store,
                snapshot_ref=build.bound_state_snapshot_ref,
            )
            assert float(reloaded_state.market.total_supply) == 0.0
    finally:
        store.close()
