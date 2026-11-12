"""Adversarial checks for the bounded acquired-model revision classifier."""

from __future__ import annotations

import json
import struct
from copy import deepcopy
from dataclasses import asdict

import pytest

from polisyos.foundry.execute import StateSnapshotValueLeaf
from polisyos.runtime.quality.acquisition_evaluation import (
    AcquisitionEvaluationBasis,
    AcquisitionEvaluationBasisV2,
)
from polisyos.runtime.quality.acquisition_model_transition import (
    _native_facets,
    _require_model_revision_facets,
    _require_outcome_revision_facets,
    _require_outcome_state_baselines,
    is_prospective_candidate_model_revision,
)
from polisyos.runtime.quality.n5_execution_basis import exact_n5_content_bytes


def _basis(values: object) -> AcquisitionEvaluationBasis:
    # This is a pure encoding/classification test, not a persisted owner claim.
    return AcquisitionEvaluationBasis.model_construct(
        effective_native_values_hex=exact_n5_content_bytes(values).hex()
    )


def _implementation(ncm: object) -> dict[str, object]:
    return {
        "selected_engine_values": {
            "dataclass": "polisyos.runtime.quality.joint_simulation_horizon._SelectedEngine",
            "fields": {
                "plan": {
                    "model": "polisyos.runtime.quality.joint_simulation_horizon.EnginePlan",
                    "fields": {
                        "engine_kind": json.loads(exact_n5_content_bytes("ncm_parallel_worlds")),
                        "ncm_spec": json.loads(exact_n5_content_bytes(ncm)),
                        "objective_ref": json.loads(exact_n5_content_bytes("outcome")),
                    },
                }
            },
        },
        "native_origin": "same-loaded-numerics",
    }


def test_only_recomputed_coefficient_change_dispatches_as_prospective_model_revision() -> None:
    """Source, method and extra model changes cannot acquire the model-only path."""
    old = {
        "controlled_observation": {"value": 0.25, "year": 2020},
        "foundry_state": {"tax_rate": 0.25},
        "declared_model": {"outcome_per_target_unit": 1.0, "outcome_baseline": 2.0},
        "selected_native_ncm": b"ncm-one",
        "n5_execution_configuration": {"seed": 101},
    }
    changed = {
        **old,
        "declared_model": {"outcome_per_target_unit": 2.0, "outcome_baseline": 2.0},
        "selected_native_ncm": b"ncm-two",
    }

    def established(values: object) -> AcquisitionEvaluationBasis:
        return _basis(values).model_copy(
            update={"predicate_provenance": "recomputed", "reason_codes": ()}
        )

    prior = established(old)
    assert is_prospective_candidate_model_revision(prior, established(changed))
    for mutation in (
        old,
        {**changed, "selected_native_ncm": old["selected_native_ncm"]},
        {**changed, "controlled_observation": {"value": 0.25, "year": 2021}},
        {**changed, "n5_execution_configuration": {"seed": 102}},
        {
            **changed,
            "declared_model": {"outcome_per_target_unit": 2.0, "outcome_baseline": 3.0},
        },
    ):
        assert not is_prospective_candidate_model_revision(prior, established(mutation))
    unavailable = established(changed).model_copy(
        update={"predicate_provenance": "not_established", "reason_codes": ("source_missing",)}
    )
    assert not is_prospective_candidate_model_revision(prior, unavailable)


def test_model_revision_requires_both_model_facets_and_identical_other_values() -> None:
    """A changed model is not established by a new ID, hash, or scalar proxy."""

    old_ncm = {"coefficient": 1.0}
    new_ncm = {"coefficient": 2.0}
    old_implementation = _implementation(old_ncm)
    new_implementation = _implementation(new_ncm)
    previous = {
        "controlled_observation": {"value": 0.25, "year": 2020},
        "foundry_state": {"tax_rate": 0.25},
        "declared_model": {"outcome_per_target_unit": 1.0},
        "selected_native_ncm": b"selected-owner-ncm-one",
        "n5_execution_configuration": {"seed": 101, "replications": 5},
        "actual_live_implementation": old_implementation,
    }
    selected = {
        **previous,
        "declared_model": {"outcome_per_target_unit": 2.0},
        "selected_native_ncm": b"selected-owner-ncm-two",
        "actual_live_implementation": new_implementation,
    }
    prospective = {**selected, "actual_live_implementation": old_implementation}

    def compare(new_values: object, **updates: object) -> None:
        arguments = {
            "previous_implementation": old_implementation,
            "selected_implementation": new_implementation,
            "previous_ncm": old_ncm,
            "selected_ncm": new_ncm,
            **updates,
        }
        _require_model_revision_facets(
            _basis(previous), _basis(prospective), _basis(new_values), **arguments
        )

    compare(selected)
    for mutation in (
        {**selected, "controlled_observation": {"value": 0.25, "year": 2021}},
        {**selected, "foundry_state": {"tax_rate": 0.3}},
        {**selected, "n5_execution_configuration": {"seed": 102, "replications": 5}},
    ):
        with pytest.raises(ValueError, match="candidate_model_revision_non_model_basis_changed"):
            compare(mutation)
    for mutation in (
        previous,
        {**selected, "declared_model": previous["declared_model"]},
        {**selected, "selected_native_ncm": previous["selected_native_ncm"]},
    ):
        with pytest.raises(
            ValueError, match="candidate_model_revision_model_difference_not_established"
        ):
            compare(mutation)
    with pytest.raises(ValueError, match="candidate_model_revision_facet_denominator_changed"):
        compare({**selected, "new_facet": 1})

    changed_implementation = deepcopy(new_implementation)
    changed_implementation["native_origin"] = "different-loaded-numerics"
    with pytest.raises(ValueError, match="candidate_model_revision_implementation_changed"):
        compare(
            {**selected, "actual_live_implementation": changed_implementation},
            selected_implementation=changed_implementation,
        )
    with pytest.raises(ValueError, match="candidate_model_revision_selected_engine_mismatch"):
        compare(selected, selected_ncm=old_ncm)


def test_model_revision_rejects_invalid_or_duplicate_native_facets() -> None:
    for encoded in (
        b"not-json",
        b'{"mapping":[[{"str":"same"},1],[{"str":"same"},2]]}',
        json.dumps({"mapping": [[{"int": 1}, "value"]]}).encode(),
        json.dumps({"mapping": [], "extra": True}).encode(),
    ):
        basis = AcquisitionEvaluationBasis.model_construct(
            effective_native_values_hex=encoded.hex()
        )
        with pytest.raises(ValueError, match="candidate_model_revision_native_facets_invalid"):
            _native_facets(basis)


def test_outcome_revision_requires_changed_source_state_and_actual_n5() -> None:
    old_ncm = {"target": "tax_rate", "outcome_baseline": 100.0}
    new_ncm = {"target": "tax_rate", "outcome_baseline": 120.0}
    old_implementation = _implementation(old_ncm)
    new_implementation = _implementation(new_ncm)

    def state(value: float, *, tax_rate: float = 0.25) -> tuple[StateSnapshotValueLeaf, ...]:
        return (
            StateSnapshotValueLeaf("gdp", "<f8", (), struct.pack("<d", value)),
            StateSnapshotValueLeaf("tax_rate", "<f8", (), struct.pack("<d", tax_rate)),
        )

    def values(value: float, leaves: tuple[StateSnapshotValueLeaf, ...]) -> dict[str, object]:
        data = {
            "observation": {
                "canonical_var": "economic.gdp",
                "country_code": "US",
                "year": 2024,
                "value": value,
                "source_watermark": f"watermark-{value}",
                "dataset_version": f"version-{value}",
            },
            "slot_binding": {"target_slot_id": "global.gdp"},
            "source_time_status": "not_established",
        }
        consumed_state = tuple(asdict(leaf) for leaf in leaves)
        artifact = {"observation": data, "consumed_state": consumed_state}
        world = {
            "data": data,
            "state": consumed_state,
            "registry": {"unchanged": True},
            "data_forge_binding": {
                "manifest": {"pipeline": "candidate"},
                "row": {"builder": "data_forge"},
                "artifact_meanings": (artifact,),
                "lineage_meanings": ({"base": "same"}, data, data, artifact),
            },
        }
        return {
            "controlled_observation": data,
            "world": world,
            "foundry_state": leaves,
            "declared_model": {"outcome_baseline": value},
            "selected_native_ncm": f"model-with-gdp-{value}".encode(),
            "n5_request_values": {"tax_rate": 0.25, "gdp": value},
            "n5_execution_configuration": {"seed": 101},
            "applied_rules": ("same-owner-rule",),
        }

    old_state = state(100.0)
    new_state = state(120.0)
    _require_outcome_state_baselines(100.0, 120.0, 100.0, 120.0)
    with pytest.raises(ValueError, match="acquired_outcome_revision_state_baseline_mismatch"):
        _require_outcome_state_baselines(100.0, 120.0, 100.0, 999.0)
    previous = {**values(100.0, old_state), "actual_live_implementation": old_implementation}
    selected = {**values(120.0, new_state), "actual_live_implementation": new_implementation}
    prospective = {**selected, "actual_live_implementation": old_implementation}

    def compare(new_values: object, **updates: object) -> None:
        arguments = {
            "previous_implementation": old_implementation,
            "selected_implementation": new_implementation,
            "previous_ncm": old_ncm,
            "selected_ncm": new_ncm,
            "previous_state": old_state,
            "selected_state": new_state,
            "state_path": "gdp",
            **updates,
        }
        _require_outcome_revision_facets(
            _basis(previous), _basis(prospective), _basis(new_values), **arguments
        )

    compare(selected)
    # V2 has an independent NCM facet and a content/profile/callable mapping;
    # it must not be interpreted as the legacy selected-engine witness.
    identity = {"content_image": "same", "execution_profile": "same", "callable_identity": "same"}
    old_owner = values(100.0, old_state)
    new_owner = values(120.0, new_state)
    v2_previous = {
        **{k: v for k, v in old_owner.items() if k not in {"controlled_observation", "world"}},
        "n5_declared_implementation": identity,
    }
    v2_selected = {
        **{k: v for k, v in new_owner.items() if k not in {"controlled_observation", "world"}},
        "n5_declared_implementation": identity,
    }

    def v2_basis(value: object) -> AcquisitionEvaluationBasisV2:
        return AcquisitionEvaluationBasisV2.model_construct(
            effective_native_values_hex=exact_n5_content_bytes(value).hex()
        )

    v2_arguments = {
        "previous_implementation": identity,
        "selected_implementation": identity,
        "previous_ncm": old_ncm,
        "selected_ncm": new_ncm,
        "previous_state": old_state,
        "selected_state": new_state,
        "state_path": "gdp",
        "source_owner_values": (
            {k: old_owner[k] for k in ("controlled_observation", "world")},
            {k: new_owner[k] for k in ("controlled_observation", "world")},
        ),
    }
    _require_outcome_revision_facets(
        v2_basis(v2_previous), v2_basis(v2_selected), v2_basis(v2_selected), **v2_arguments
    )
    changed_identity = {**identity, "callable_identity": "changed"}
    with pytest.raises(ValueError, match="acquired_outcome_revision_implementation_changed"):
        _require_outcome_revision_facets(
            v2_basis(v2_previous),
            v2_basis(v2_selected),
            v2_basis({**v2_selected, "n5_declared_implementation": changed_identity}),
            **{**v2_arguments, "selected_implementation": changed_identity},
        )

    for name in (
        "controlled_observation",
        "foundry_state",
        "declared_model",
        "selected_native_ncm",
        "n5_request_values",
    ):
        with pytest.raises(
            ValueError, match="acquired_outcome_revision_source_state_model_not_changed"
        ):
            compare({**selected, name: previous[name]})
    changed_implementation = deepcopy(new_implementation)
    changed_implementation["native_origin"] = "other-loaded-numerics"
    with pytest.raises(ValueError, match="acquired_outcome_revision_implementation_changed"):
        compare(
            {**selected, "actual_live_implementation": changed_implementation},
            selected_implementation=changed_implementation,
        )
    with pytest.raises(ValueError, match="acquired_outcome_revision_unrelated_basis_changed"):
        compare({**selected, "n5_execution_configuration": {"seed": 102}})
    other_state = state(120.0, tax_rate=0.3)
    with pytest.raises(ValueError, match="acquired_outcome_revision_unrelated_state_changed"):
        compare(
            {**values(120.0, other_state), "actual_live_implementation": new_implementation},
            selected_state=other_state,
        )
    unrelated_world = deepcopy(selected)
    unrelated_world["world"]["registry"] = {"unchanged": False}
    with pytest.raises(ValueError, match="acquired_outcome_revision_world_dependency_changed"):
        compare(unrelated_world)
