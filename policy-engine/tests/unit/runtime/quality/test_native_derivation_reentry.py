"""Native derivation reentry retains exact leaves without minting authority."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from polisyos.core import artifacts
from polisyos.core import derivations as derivation
from polisyos.core.contracts.variable_binding import (
    VariableRepresentationRef,
    load_variable_representation,
    variable_representation_manifest_inputs,
)
from polisyos.data_forge.read_api.catalog import OverlayAdmissionError
from polisyos.runtime.quality import acquisition_planner as planner
from polisyos.runtime.quality import acquisition_world_growth as owner
from tests._helpers.lane01_wdi_profiles import CandidateWDIProfile
from tests._helpers.semantic_epoch_native import make_native_live_measurement_history
from tests.unit.runtime.quality.test_n7_derivation_bundle import (
    _marker,
    _pending_source,
    _profile,
    _selected_target,
    _target_gap,
)


def _native_bundle(tmp_path: Path):
    """Use a genuine target obligation and a data-defined two-leaf plan.

    Both roles deliberately select the same declared source semantics. The
    collection establishes availability, not independence or the adequacy of
    this synthetic arithmetic model. No arithmetic or N5 is executed here.
    """
    case, set_ref, obligation_ref, target_basis, context = _selected_target(tmp_path)
    budget, budget_ref = _profile(case.store)
    supplier = _marker(case.store, "native-supplier-routing-selection")
    sources = tuple(
        _pending_source(
            node_id,
            target_basis,
            _target_gap(context, f"test.native.{node_id}"),
            alternatives=(supplier,),
        )
        for node_id in ("left", "right")
    )
    basis = derivation.BasisSignature(quantity_kind="stock", unit="usd")
    family = derivation.TransformFamily(
        family_id="test.native.two-leaf-sum",
        method_id="test.native.add",
        method_version="1.0",
        input_specs=tuple(
            derivation.TransformInputSpec(role=role, basis=basis) for role in ("left", "right")
        ),
        output_basis=basis,
        year_domain_role="left",
        expression=derivation.ArithmeticExpression(
            operator="add",
            operands=tuple(
                derivation.ArithmeticExpression(operator="current_value", role=role)
                for role in ("left", "right")
            ),
        ),
        assumption_rules=(
            derivation.AssumptionRule(name="model_status", literal_value="synthetic_candidate"),
        ),
    )
    registry_ref = derivation.persist_transform_family_registry(
        case.store,
        derivation.TransformFamilyRegistry(families=(family,)),
    )
    registry_ref = artifacts.artifact_ref_for_manifest(case.store.get_manifest(registry_ref))
    bundle = planner.N7DerivationBundle(
        obligation_set_ref=set_ref,
        model_input_obligation_ref=obligation_ref,
        target_basis=target_basis,
        dag_budget_profile_ref=budget_ref,
        dag_budget_profile=budget,
        source_nodes=sources,
        operation_nodes=(
            planner.N7DerivationOperationNode(
                node_id="sum",
                operator_ref=registry_ref,
                family_id=family.family_id,
                method_version=family.method_version,
                output_basis=target_basis,
                role_inputs=tuple(
                    planner.N7DerivationRoleInput(
                        role=node.node_id,
                        input_node_id=node.node_id,
                        source_basis=node.source_basis,
                    )
                    for node in sources
                ),
            ),
        ),
        root_node_id="sum",
        input_closure_status="partial",
    )
    bundle_ref = planner.persist_n7_derivation_bundle(case.store, bundle)
    return case, bundle, bundle_ref, supplier


def _native_profile() -> CandidateWDIProfile:
    return CandidateWDIProfile(
        construct="test.native.stock",
        indicator_id="POLICYOS.FIXTURE.NATIVE.STOCK",
        source_title="Test-owned native stock (current US$)",
        source_description=(
            "Synthetic nominal US dollar stock; empirical authority is not established."
        ),
        target_slot="test.native.stock",
        raw_unit="usd",
        canonical_unit="usd",
        transform="identity",
        transform_ref="fabric://units/usd-identity/v1",
        population="population:country",
        fixture_value=640.0,
        source_provenance_class="observed",
        valid_min=0.0,
        valid_max=10_000.0,
        country_code="UKR",
        country_id="UA",
        year=2022,
    )


def _fresh_replay(store, checkpoint_ref):
    script = """
import json, sys
from pathlib import Path
from polisyos.core import artifacts
from polisyos.runtime.quality.acquisition_world_growth import (
    replay_native_derivation_input_collection,
)
data = json.load(sys.stdin)
reader = artifacts.FileSystemCAS.open_existing_read_only(Path(data['root']))
ref = artifacts.ArtifactRef.model_validate(data['ref'])
result = replay_native_derivation_input_collection(reader, ref)
print(json.dumps({
    'collection': result.collection.model_dump(mode='json'),
    'source_value_replay': result.source_value_replay,
    'replayed_source_node_ids': result.replayed_source_node_ids,
    'native_currentness': result.native_currentness,
}, sort_keys=True))
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", script],
        input=json.dumps({"root": str(store.root), "ref": checkpoint_ref.model_dump(mode="json")}),
        text=True,
        capture_output=True,
        timeout=90,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_native_collection_replays_partial_complete_and_source_removal_without_refetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Actual native admission supplies facts; missing leaves never become values."""
    case, bundle, bundle_ref, supplier_ref = _native_bundle(tmp_path / "model")
    original_bundle_bytes = case.store.get_bytes(bundle_ref)
    history = make_native_live_measurement_history(
        tmp_path / "native",
        profile=_native_profile(),
        semantic_definition_ref=bundle.target_basis.semantic_definition_ref,
        representation_ref=bundle.target_basis.representation_ref,
        attempt_ids=("native-derivation-input-a",),
        artifact_store=case.store,
        monkeypatch=monkeypatch,
        source_measure_scope={
            "population": "population:country",
            "temporal_granularity": "annual",
            "source_geography_id": "UA",
            "geography_ref": "UA",
            "jurisdiction_ref": "UA",
            "time_period_basis": "calendar_year",
        },
    )
    try:
        active = history.admit(640.0)
        projection = active.projections[history.entry.target_variable]
        (observation,) = projection.observations
        leaf = owner.NativeDerivationSourceInput(
            source_node_id="left",
            supplier_ref=supplier_ref,
            overlay=history.overlay,
            receipt_ref=projection.receipt_ref,
            passport=active.passport,
            observation_id=observation.observation.observation_id,
        )

        def collect(*sources):
            return owner.collect_native_derivation_inputs(
                case.store,
                derivation_bundle_ref=bundle_ref,
                source_inputs=sources,
                authority=history.authority,
            )

        empty = collect()
        assert empty.input_closure_status == "partial"
        assert not empty.source_inputs
        assert tuple(row.source_node_id for row in empty.pending_actions) == ("left", "right")
        assert tuple(row.requirement_gap for row in empty.pending_actions) == tuple(
            row.requirement_gap for row in bundle.source_nodes
        )
        assert all(row.permission_status == "not_established" for row in empty.pending_actions)
        empty_ref = owner.persist_native_derivation_input_collection(case.store, empty)
        reader = artifacts.FileSystemCAS.open_existing_read_only(case.store.root)
        empty_replay = owner.replay_native_derivation_input_collection(reader, empty_ref)
        assert empty_replay.source_value_replay == "not_established"
        assert empty_replay.replayed_source_node_ids == ()
        assert empty_replay.native_currentness == "not_established"

        partial = collect(leaf)
        assert partial.input_closure_status == "partial"
        assert partial.target_satisfaction_status == "unsatisfied"
        assert tuple(row.source_node_id for row in partial.source_inputs) == ("left",)
        assert tuple(row.source_node_id for row in partial.pending_actions) == ("right",)
        assert partial.source_inputs[0].supplier_correspondence == "consumer_asserted"
        assert partial.source_inputs[0].empirical_authority == "not_established"
        partial_ref = owner.persist_native_derivation_input_collection(case.store, partial)
        partial_replay = owner.replay_native_derivation_input_collection(reader, partial_ref)
        assert partial_replay.source_value_replay == "recomputed"
        assert partial_replay.replayed_source_node_ids == ("left",)
        assert partial_replay.collection.semantic_admissibility == "not_established"

        complete = collect(replace(leaf, source_node_id="right"), leaf)
        assert complete.input_closure_status == "inputs_complete"
        assert not complete.pending_actions
        assert complete.target_satisfaction_status == "unsatisfied"
        assert complete.semantic_admissibility == "not_established"
        assert tuple(row.source_node_id for row in complete.source_inputs) == ("left", "right")
        assert case.store.get_bytes(bundle_ref) == original_bundle_bytes
        assert planner.load_n7_derivation_bundle(case.store, bundle_ref).model_dump(
            mode="json"
        ) == bundle.model_dump(mode="json")
        checkpoint_ref = owner.persist_native_derivation_input_collection(case.store, complete)
        fresh = _fresh_replay(case.store, checkpoint_ref)
        assert fresh["collection"] == complete.model_dump(mode="json")
        assert fresh["source_value_replay"] == "recomputed"
        assert fresh["replayed_source_node_ids"] == ["left", "right"]
        assert fresh["native_currentness"] == "not_established"

        with pytest.raises(ValueError, match="source_selection_duplicate"):
            collect(leaf, leaf)
        with pytest.raises(ValueError, match="source_selection_foreign"):
            collect(replace(leaf, source_node_id="unrelated"))
        with pytest.raises(ValueError, match="supplier_not_selected"):
            collect(replace(leaf, supplier_ref=_marker(case.store, "unselected-supplier")))
        with pytest.raises(ValueError):
            collect(replace(leaf, observation_id="missing-native-row"))

        original_representation = load_variable_representation(
            case.store, bundle.target_basis.representation_ref
        )
        revised_representation = original_representation.model_copy(
            update={"revision": "selected-revision-changed"}
        )
        revised_ref = case.store.put_json(
            revised_representation,
            artifacts.PutOptions(
                kind=revised_representation.ARTIFACT_KIND,
                media_type=revised_representation.ARTIFACT_MEDIA_TYPE,
                schema=artifacts.SchemaInfo(
                    name=revised_representation.ARTIFACT_SCHEMA_NAME,
                    version=case.store.get_manifest(
                        bundle.target_basis.representation_ref
                    ).artifact_schema.version,
                ),
                inputs=list(variable_representation_manifest_inputs(revised_representation)),
            ),
            return_selected_profile=True,
        )
        revised_basis = bundle.target_basis.model_copy(
            update={
                "representation_ref": VariableRepresentationRef.model_validate(
                    revised_ref.model_dump(mode="python")
                )
            }
        )
        revised_sources = tuple(
            row.model_copy(
                update={
                    "source_basis": revised_basis,
                    "supplier_alternatives": tuple(
                        alt.model_copy(update={"source_basis": revised_basis})
                        for alt in row.supplier_alternatives
                    ),
                }
            )
            for row in bundle.source_nodes
        )
        revised_operations = tuple(
            node.model_copy(
                update={
                    "role_inputs": tuple(
                        role.model_copy(update={"source_basis": revised_basis})
                        for role in node.role_inputs
                    )
                }
            )
            for node in bundle.operation_nodes
        )
        revised_bundle_ref = planner.persist_n7_derivation_bundle(
            case.store,
            bundle.model_copy(
                update={"source_nodes": revised_sources, "operation_nodes": revised_operations}
            ),
        )
        with pytest.raises(ValueError, match="source_semantic_selection_mismatch"):
            owner.collect_native_derivation_inputs(
                case.store,
                derivation_bundle_ref=revised_bundle_ref,
                source_inputs=(leaf,),
                authority=history.authority,
            )

        raw_ref = active.evidence.raw_artifact_ref
        assert raw_ref is not None
        actual_get = case.store.get_bytes

        def removed_raw(ref):
            if isinstance(ref, artifacts.ArtifactRef) and (
                artifacts.artifact_ref_identity_key(ref)
                == artifacts.artifact_ref_identity_key(raw_ref)
            ):
                raise FileNotFoundError("test removed the exact selected native source")
            return actual_get(ref)

        with monkeypatch.context() as context:
            context.setattr(case.store, "get_bytes", removed_raw)
            with pytest.raises(OverlayAdmissionError, match="live_source_execution_unresolved"):
                collect(leaf)
            with pytest.raises(ValueError):
                owner.replay_native_derivation_input_collection(case.store, checkpoint_ref)
        restored = collect(leaf, replace(leaf, source_node_id="right"))
        assert restored == complete
        assert history.transport_calls == 1
    finally:
        history.overlay.close()
        case.close()
