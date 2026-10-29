"""Bridge reconciliation against persisted Foundry rule permutations and views."""

from __future__ import annotations

import ast
import inspect
import textwrap
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import (
    FileSystemCAS,
    ProducerInfo,
    artifact_ref_for_manifest,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts._layout import CASPathLayout
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts import FoundryInputBindingRule
from polisyos.foundry.data_plane import load_input_bindings, prepare_json_input_binding_values
from polisyos.pdc import world_model_record_content_hash_from_fields
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality import data_state_substrate as owner
from polisyos.runtime.quality.acquisition_world_growth import (
    AcquisitionWorldGrowthBridge,
    AcquisitionWorldGrowthConfig,
)
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from polisyos.runtime.quality.substrate_registry import persist_substrate_registry
from polisyos.runtime.quality.world_model_record import (
    WorldModelRecord,
    load_world_model_record,
    persist_world_model_record,
    world_model_artifact_views,
)
from tests._helpers import world_model_record as world_fixture
from tests.integration.core_runtime.test_acquisition_data_preparation import _same_write_options
from tests.integration.core_runtime.test_acquisition_observation_semantics import _case
from tests.integration.core_runtime.test_acquisition_world_semantic_preparation import (
    _empty_selected_skg,
)


def _selected_identity(store: FileSystemCAS, ref: Any) -> tuple[str, str, str, str | None]:
    """Resolve a default, when present, through the actual selected manifest."""
    assert store.verify(ref).ok
    return artifact_ref_identity_key(artifact_ref_for_manifest(store.get_manifest(ref)))


def _persist_fixture_binding_world(
    store: FileSystemCAS,
    original: WorldModelRecord,
    *,
    rules: list[FoundryInputBindingRule] | None = None,
    altered_view: tuple[str, Any] | None = None,
) -> tuple[Any, Any]:
    """Persist test-created bindings plus a WMR selecting those exact CAS bytes."""
    views = world_model_artifact_views(original)
    bindings = load_input_bindings(store, views.input_bindings_ref)
    manifest = store.get_manifest(views.input_bindings_ref)
    payload = bindings.model_dump(mode="json")
    if rules is not None:
        payload["rules"] = [rule.model_dump(mode="json") for rule in rules]
    inputs = list(manifest.inputs)
    if altered_view is not None:
        field, alternative = altered_view
        roles = {
            "data_snapshot_ref": "input.data_snapshot_ref",
            "registry_bundle_ref": "input.registry_bundle_ref",
            "bound_state_snapshot_ref": "artifact.bound_state_snapshot_ref",
        }
        payload[field] = alternative.model_dump(mode="json")
        role = roles[field]
        matches = [i for i, item in enumerate(inputs) if item.role == role]
        assert len(matches) == 1
        inputs[matches[0]] = input_ref_from_artifact_ref(alternative, role=role)
    binding_ref = store.put_json(
        payload,
        _same_write_options(manifest, inputs=inputs),
        canon_spec=CanonSpec(),
        return_selected_profile=True,
    )
    assert binding_ref.artifact_id != views.input_bindings_ref.artifact_id
    world_payload = original.model_dump(mode="json")
    world_payload["foundry_binding_ref"]["input_bindings_ref"] = str(binding_ref.artifact_id)
    if world_payload.get("artifact_views") is not None:
        world_payload["artifact_views"]["input_bindings_ref"] = binding_ref.model_dump(mode="json")
    digest = world_model_record_content_hash_from_fields(world_payload)
    world_payload["content_hash"] = digest
    world_payload["world_model_record_id"] = (
        "world_model_record_" + digest.removeprefix("sha256:")[:16]
    )
    typed_world = WorldModelRecord.model_validate(world_payload)
    world_ref = persist_world_model_record(store, typed_world)
    return binding_ref, world_ref


def _same_bytes_other_selected_view(store: FileSystemCAS, ref: Any) -> Any:
    """Make a same-blob sidecar, then restore the fixture's actual default view."""
    manifest = store.get_manifest(ref)
    selected = artifact_ref_for_manifest(manifest)
    layout = CASPathLayout(store.root)
    _blob, default_path = layout.paths(selected.artifact_id)
    before = default_path.read_bytes()
    try:
        alternate = store.put_bytes(
            store.get_bytes(ref),
            _same_write_options(
                manifest, producer=ProducerInfo(component="test.fixture.alternate", version="1.0")
            ),
            return_selected_profile=True,
        )
    finally:
        default_path.write_bytes(before)
    assert alternate.artifact_id == selected.artifact_id
    assert alternate.manifest_profile_sha256 != selected.manifest_profile_sha256
    assert store.get_bytes(alternate) == store.get_bytes(ref)
    assert store.verify(alternate).ok and store.verify(ref).ok
    assert _selected_identity(store, ref) == artifact_ref_identity_key(selected)
    return alternate


def _bridge_mutant(mode: str):
    """Replace only the real bridge's rule comparison in the loaded source."""
    source = textwrap.dedent(
        inspect.getsource(AcquisitionWorldGrowthBridge._reconcile_acquired_candidate_values)
    )
    tree = ast.parse(source)

    class RemoveRuleRelation(ast.NodeTransformer):
        count = 0

        def visit_If(self, node: ast.If) -> ast.AST:
            self.generic_visit(node)
            if (
                mode == "omit_view"
                and isinstance(node.test, ast.UnaryOp)
                and isinstance(node.test.op, ast.Not)
                and isinstance(node.test.operand, ast.Call)
                and isinstance(node.test.operand.func, ast.Name)
                and node.test.operand.func.id == "same_selected_view"
            ):
                self.count += 1
                node.test = ast.copy_location(ast.Constant(value=False), node.test)
            return node

        def visit_Compare(self, node: ast.Compare) -> ast.AST:
            self.generic_visit(node)
            if (
                mode != "omit_view"
                and isinstance(node.left, ast.Attribute)
                and isinstance(node.left.value, ast.Name)
                and node.left.value.id == "replayed"
                and node.left.attr == "effective_rules"
                and len(node.ops) == 1
                and isinstance(node.ops[0], ast.NotEq)
                and len(node.comparators) == 1
                and isinstance(node.comparators[0], ast.Attribute)
                and isinstance(node.comparators[0].value, ast.Name)
                and node.comparators[0].value.id == "prospective_values"
                and node.comparators[0].attr == "effective_rules"
            ):
                self.count += 1
                if mode == "omit":
                    return ast.copy_location(ast.Constant(value=False), node)
                assert mode == "raw_order"
                node.left = ast.Call(
                    func=ast.Name(id="tuple", ctx=ast.Load()),
                    args=[
                        ast.Attribute(
                            value=ast.Name(id="actual_bindings", ctx=ast.Load()),
                            attr="rules",
                            ctx=ast.Load(),
                        )
                    ],
                    keywords=[],
                )
            return node

    transformer = RemoveRuleRelation()
    changed = transformer.visit(tree)
    assert transformer.count == 1
    ast.fix_missing_locations(changed)
    function = AcquisitionWorldGrowthBridge._reconcile_acquired_candidate_values
    scope: dict[str, Any] = {}
    # Test-only, source-bound removal of the single selected bridge predicate.
    exec(  # noqa: S102 - source-bound test-only mutation
        compile(changed, inspect.getsourcefile(function) or "<bridge>", "exec"),
        function.__globals__,
        scope,
    )
    return scope["_reconcile_acquired_candidate_values"]


def test_bridge_reopens_persisted_permutations_and_reconciles_full_owner_quantity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Real CAS views preserve equivalent order and refuse changed rule/state sources."""
    first = FoundryInputBindingRule(
        binding_id="overlap.a-income",
        source_path="agents.income",
        target_slot_id="agents.income",
        notes=["first owner operation"],
    )
    last = FoundryInputBindingRule(
        binding_id="overlap.z-income",
        source_path="agents.reported_income",
        target_slot_id="agents.income",
        notes=["last owner operation"],
    )
    case = _case(tmp_path / "source")
    monkeypatch.setattr(world_fixture, "FileSystemCAS", lambda _path: case.scenario.store)
    store, base, _model, _registry = world_fixture._build_record(
        tmp_path / "base",
        skg_ref_factory=_empty_selected_skg,
        foundry_binding_rules=[last, first],
    )
    substrate = world_fixture._substrate_registry()
    views = world_model_artifact_views(base.record)
    plan = owner._prepare_acquired_observation_world(
        store,
        base_world_model_record=base.record,
        acquired_rule=case.prepared.foundry_binding_rule,
        registry_bundle_ref=views.registry_bundle_ref,
        substrate_registry=substrate,
    )
    prospective = prepare_json_input_binding_values(
        store,
        payload_json=case.prepared.payload_json,
        registry_bundle_ref=views.registry_bundle_ref,
        rules=list(plan.rules),
    )
    assert tuple(rule.binding_id for rule in prospective.effective_rules) == (
        case.prepared.foundry_binding_rule.binding_id,
        first.binding_id,
        last.binding_id,
    )
    assert prospective.materialized_state.agents.income.tolist() == pytest.approx([1000.0, 1600.0])
    materialized = owner.materialize_acquired_observation_snapshot(
        store, **case.args, workspace_dir=case.workspace, prepared=case.prepared
    )
    actual = owner.build_acquired_observation_candidate_world(
        store,
        base_world_model=base.record,
        substrate_registry=substrate,
        substrate_registry_artifact_ref=persist_substrate_registry(store, substrate),
        materialization=materialized,
        workspace_dir=tmp_path / "world",
        transaction_time=case.args["transaction_time"],
    )
    fresh = FileSystemCAS(store.root)
    produced = load_world_model_record(fresh, actual.world_model.record_ref)
    assert produced == actual.world_model.record and produced is not actual.world_model.record
    produced_views = world_model_artifact_views(produced)
    produced_bindings = load_input_bindings(fresh, produced_views.input_bindings_ref)
    assert tuple(produced_bindings.rules) == prospective.effective_rules
    control = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite")
    bridge = AcquisitionWorldGrowthBridge(
        config=AcquisitionWorldGrowthConfig(),
        repo_root=tmp_path,
        runtime_root=tmp_path,
        authority=case.scenario.authority,
        artifact_store=fresh,
        event_log=RuntimeDiagnosticEventLog(store=control, artifact_store=fresh),
        epoch_deployment=None,
    )
    bridge._reconcile_acquired_candidate_values(
        prospective_values=prospective, world_model_record=produced
    )

    # A legacy default with no selected sidecar cannot be pinned by this CAS;
    # absence is explicit and the original fixture bytes are always restored.
    state_ref = produced_views.bound_state_snapshot_ref
    state_selected = artifact_ref_for_manifest(fresh.get_manifest(state_ref))
    assert state_selected.manifest_profile_sha256 is not None
    layout = CASPathLayout(fresh.root)
    state_sidecar = layout.view_manifest_path(
        state_selected.artifact_id, state_selected.manifest_profile_sha256
    )
    sidecar_bytes = state_sidecar.read_bytes()
    try:
        state_sidecar.unlink()
        with pytest.raises(ValueError, match="acquisition_prospective_selected_view_unverified"):
            bridge._reconcile_acquired_candidate_values(
                prospective_values=prospective, world_model_record=produced
            )
    finally:
        state_sidecar.write_bytes(sidecar_bytes)
    bridge._reconcile_acquired_candidate_values(
        prospective_values=prospective, world_model_record=produced
    )

    # After the source join, a default may move. The actual read must receive
    # and consume the already pinned selected state rather than the new default.
    import polisyos.foundry.execute as foundry_execute

    assert state_ref.manifest_profile_sha256 is None
    alternate_state = _same_bytes_other_selected_view(fresh, state_ref)
    assert alternate_state.manifest_profile_sha256 is not None
    _state_blob, state_default = layout.paths(state_ref.artifact_id)
    default_bytes = state_default.read_bytes()
    alternate_state_path = layout.view_manifest_path(
        alternate_state.artifact_id, alternate_state.manifest_profile_sha256
    )
    actual_load = foundry_execute.load_state_snapshot
    consumed: list[Any] = []

    def change_default_after_join(reader_store: Any, *, snapshot_ref: Any):
        consumed.append(snapshot_ref)
        state_default.write_bytes(alternate_state_path.read_bytes())
        return actual_load(reader_store, snapshot_ref=snapshot_ref)

    try:
        with monkeypatch.context() as switched:
            switched.setattr(foundry_execute, "load_state_snapshot", change_default_after_join)
            bridge._reconcile_acquired_candidate_values(
                prospective_values=prospective, world_model_record=produced
            )
    finally:
        state_default.write_bytes(default_bytes)
    assert len(consumed) == 1
    assert artifact_ref_identity_key(consumed[0]) == artifact_ref_identity_key(state_selected)
    bridge._reconcile_acquired_candidate_values(
        prospective_values=prospective, world_model_record=produced
    )

    permuted_ref, permuted_world_ref = _persist_fixture_binding_world(
        fresh, produced, rules=list(reversed(produced_bindings.rules))
    )
    cold = FileSystemCAS(store.root)
    permuted = load_world_model_record(cold, permuted_world_ref)
    permuted_views = world_model_artifact_views(permuted)
    assert _selected_identity(cold, permuted_views.input_bindings_ref) == _selected_identity(
        cold, permuted_ref
    )
    permuted_bindings = load_input_bindings(cold, permuted_views.input_bindings_ref)
    assert permuted_bindings.rules == list(reversed(produced_bindings.rules))
    assert permuted_bindings.rules != produced_bindings.rules
    for field in ("data_snapshot_ref", "registry_bundle_ref", "bound_state_snapshot_ref"):
        assert _selected_identity(cold, getattr(permuted_bindings, field)) == _selected_identity(
            cold, getattr(produced_bindings, field)
        )
        assert _selected_identity(cold, getattr(permuted_views, field)) == _selected_identity(
            cold, getattr(produced_views, field)
        )
        assert _selected_identity(cold, getattr(permuted_bindings, field)) == _selected_identity(
            cold, getattr(permuted_views, field)
        )
    bridge._reconcile_acquired_candidate_values(
        prospective_values=prospective, world_model_record=permuted
    )
    with monkeypatch.context() as removed:
        removed.setattr(
            AcquisitionWorldGrowthBridge,
            "_reconcile_acquired_candidate_values",
            _bridge_mutant("raw_order"),
        )
        with pytest.raises(
            ValueError, match="acquisition_prospective_rule_owner_reconciliation_failed"
        ):
            bridge._reconcile_acquired_candidate_values(
                prospective_values=prospective, world_model_record=permuted
            )
    bridge._reconcile_acquired_candidate_values(
        prospective_values=prospective, world_model_record=permuted
    )

    changed_rules = [
        rule.model_copy(update={"notes": ["changed retained note"]})
        if rule.binding_id == first.binding_id
        else rule
        for rule in produced_bindings.rules
    ]
    _changed_ref, changed_world_ref = _persist_fixture_binding_world(
        fresh, produced, rules=changed_rules
    )
    changed = load_world_model_record(cold, changed_world_ref)
    with pytest.raises(
        ValueError, match="acquisition_prospective_rule_owner_reconciliation_failed"
    ):
        bridge._reconcile_acquired_candidate_values(
            prospective_values=prospective, world_model_record=changed
        )
    with monkeypatch.context() as removed:
        removed.setattr(
            AcquisitionWorldGrowthBridge,
            "_reconcile_acquired_candidate_values",
            _bridge_mutant("omit"),
        )
        bridge._reconcile_acquired_candidate_values(
            prospective_values=prospective, world_model_record=changed
        )
    with pytest.raises(
        ValueError, match="acquisition_prospective_rule_owner_reconciliation_failed"
    ):
        bridge._reconcile_acquired_candidate_values(
            prospective_values=prospective, world_model_record=changed
        )

    swapped_rules = [
        rule.model_copy(update={"source_path": "agents.income"})
        if rule.binding_id == last.binding_id
        else rule
        for rule in produced_bindings.rules
    ]
    changed_state = prepare_json_input_binding_values(
        fresh,
        payload_json=case.prepared.payload_json,
        registry_bundle_ref=views.registry_bundle_ref,
        rules=swapped_rules,
    )
    assert changed_state.materialized_state.agents.income.tolist() == pytest.approx(
        [1200.0, 1800.0]
    )
    _swapped_ref, swapped_world_ref = _persist_fixture_binding_world(
        fresh, produced, rules=swapped_rules
    )
    swapped = load_world_model_record(cold, swapped_world_ref)
    with pytest.raises(
        ValueError, match="acquisition_prospective_rule_owner_reconciliation_failed"
    ):
        bridge._reconcile_acquired_candidate_values(
            prospective_values=prospective, world_model_record=swapped
        )

    for field in ("data_snapshot_ref", "registry_bundle_ref", "bound_state_snapshot_ref"):
        alternate = _same_bytes_other_selected_view(fresh, getattr(produced_bindings, field))
        _alt_ref, alt_world_ref = _persist_fixture_binding_world(
            fresh, produced, altered_view=(field, alternate)
        )
        altered_world = load_world_model_record(cold, alt_world_ref)
        altered_views = world_model_artifact_views(altered_world)
        altered_bindings = load_input_bindings(cold, altered_views.input_bindings_ref)
        assert _selected_identity(cold, getattr(altered_bindings, field)) == (
            artifact_ref_identity_key(alternate)
        )
        assert _selected_identity(cold, getattr(altered_views, field)) == _selected_identity(
            cold, getattr(produced_views, field)
        )
        assert _selected_identity(cold, getattr(altered_bindings, field)) != _selected_identity(
            cold, getattr(altered_views, field)
        )
        with pytest.raises(
            ValueError, match="acquisition_prospective_binding_source_view_mismatch"
        ):
            bridge._reconcile_acquired_candidate_values(
                prospective_values=prospective, world_model_record=altered_world
            )
        with monkeypatch.context() as removed:
            removed.setattr(
                AcquisitionWorldGrowthBridge,
                "_reconcile_acquired_candidate_values",
                _bridge_mutant("omit_view"),
            )
            bridge._reconcile_acquired_candidate_values(
                prospective_values=prospective, world_model_record=altered_world
            )
        with pytest.raises(
            ValueError, match="acquisition_prospective_binding_source_view_mismatch"
        ):
            bridge._reconcile_acquired_candidate_values(
                prospective_values=prospective, world_model_record=altered_world
            )
