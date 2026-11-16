"""Exercise explicit retained Native quote selection over real CAS artifacts.

The test quote/profile producer, profile reader, manifest checks and
FileSystemCAS remain real. Small adapters supply the already selected N7
source, bundle, planner, supplier-declaration and collection owner results;
they do not claim to prove a complete Native Source or acquisition authority
chain. Quote amounts are demonstrative fixture inputs only.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.core import artifacts
from polisyos.core.artifacts import load_core_json_artifact
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.data_forge.read_api import catalog
from polisyos.runtime.quality import (
    acquisition_planner as planner_owner,
)
from polisyos.runtime.quality import (
    acquisition_route_loop,
    acquisition_world_growth,
    generation_cycle,
)
from polisyos.runtime.quality.acquisition_planner import load_native_derivation_leaf_cost_profile


def _artifact_tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _preserves_prior_bytes(before: dict[str, bytes], after: dict[str, bytes]) -> bool:
    return set(before).issubset(after) and all(after[path] == data for path, data in before.items())


def _case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Build two quote leaves and adapt only canonical owner read boundaries."""
    from tests._helpers.native_derivation_quotes import _profile_for_scope
    from tests.unit.runtime.quality.test_native_derivation_leaf_cost_profile import (
        _profile_scope,
        _put_selected_fact,
    )

    root = tmp_path / "cas"
    store = FileSystemCAS(root)
    base_scope, _unused_quote_ref = _profile_scope(store)
    supplier_b = _put_selected_fact(store, kind="external.source_supplier_fact", name="supplier_b")
    scope_a = base_scope.model_copy(
        update={
            "source_node_id": "source:metric-a",
            "requirement_gap_id": "gap:metric-a",
            "compiled_requirement_ref": "compiled:metric-a",
            "planner_record_id": "record:metric-a",
            "missing_distribution": "metric-a",
        }
    )
    scope_b = base_scope.model_copy(
        update={
            "source_node_id": "source:metric-b",
            "requirement_gap_id": "gap:metric-b",
            "compiled_requirement_ref": "compiled:metric-b",
            "planner_record_id": "record:metric-b",
            "selected_supplier_ref": supplier_b,
            "missing_distribution": "metric-b",
        }
    )
    scopes = (scope_a, scope_b)
    actor = (scope_a.tenant_id, scope_a.cell_id, scope_a.run_id, scope_a.source_job_id)
    source = SimpleNamespace(
        tenant_id=scope_a.tenant_id,
        cell_id=scope_a.cell_id,
        run_id=scope_a.run_id,
        source_job_id=scope_a.source_job_id,
        derivation_bundle_ref=scope_a.derivation_bundle_ref,
    )
    gaps = {
        scope.requirement_gap_id: SimpleNamespace(
            requirement_gap_id=scope.requirement_gap_id,
            compiled_requirement_ref=scope.compiled_requirement_ref,
        )
        for scope in scopes
    }
    records = {
        scope.requirement_gap_id: SimpleNamespace(
            acquisition_id=scope.planner_record_id, recommended_strategy=scope.strategy
        )
        for scope in scopes
    }
    bundle = SimpleNamespace(
        obligation_set_ref=scope_a.obligation_set_ref,
        source_nodes=tuple(
            SimpleNamespace(
                node_id=scope.source_node_id,
                requirement_gap=gaps[scope.requirement_gap_id],
                selected_supplier_ref=scope.selected_supplier_ref,
                supplier_alternatives=(),
            )
            for scope in scopes
        ),
    )
    report = SimpleNamespace(
        candidate_lineage=SimpleNamespace(port_source_ref=scope_a.configured_port_source_ref)
    )
    declarations = {
        artifacts.artifact_ref_identity_key(scope.selected_supplier_ref): SimpleNamespace(
            entry=SimpleNamespace(
                entry_id=f"entry-{scope.source_node_id}",
                target_variable=scope.missing_distribution,
            ),
            connector_id=f"connector-{scope.source_node_id}",
        )
        for scope in scopes
    }
    case = SimpleNamespace(
        root=root,
        store=store,
        source=source,
        bundle=bundle,
        report=report,
        actor=actor,
        scope_a=scope_a,
        scope_b=scope_b,
        gaps=gaps,
        records=records,
        declarations=declarations,
        collection_ref=scope_a.derivation_bundle_ref,
        collection=SimpleNamespace(
            derivation_bundle_ref=scope_a.derivation_bundle_ref,
            source_inputs=(SimpleNamespace(source_node_id=scope_a.source_node_id),),
            pending_actions=(SimpleNamespace(source_node_id=scope_b.source_node_id),),
        ),
    )

    def load_source(_store: Any, ref: artifacts.ArtifactRef) -> Any:
        assert artifacts.artifact_ref_identity_key(ref) == artifacts.artifact_ref_identity_key(
            scope_a.configured_port_source_ref
        )
        return case.source

    def load_bundle(_store: Any, ref: artifacts.ArtifactRef) -> Any:
        assert artifacts.artifact_ref_identity_key(ref) == artifacts.artifact_ref_identity_key(
            scope_a.derivation_bundle_ref
        )
        return case.bundle

    def load_report(_store: Any, _ref: artifacts.ArtifactRef) -> Any:
        return case.report

    def load_declaration(_store: Any, ref: artifacts.ArtifactRef) -> Any:
        return case.declarations[artifacts.artifact_ref_identity_key(ref)]

    def select_record(_report: Any, gap: Any) -> Any:
        return case.records[gap.requirement_gap_id]

    def missing_distributions(gap: Any) -> tuple[str, ...]:
        scope = next(row for row in scopes if row.requirement_gap_id == gap.requirement_gap_id)
        return (scope.missing_distribution,)

    def replay_collection(_store: Any, ref: artifacts.ArtifactRef) -> Any:
        assert artifacts.artifact_ref_identity_key(ref) == artifacts.artifact_ref_identity_key(
            case.collection_ref
        )
        return SimpleNamespace(collection=case.collection)

    monkeypatch.setattr(planner_owner, "_n7_load_configured_candidate_port_source", load_source)
    monkeypatch.setattr(planner_owner, "load_n7_derivation_bundle", load_bundle)
    monkeypatch.setattr(planner_owner, "load_acquisition_planner_report", load_report)
    monkeypatch.setattr(
        planner_owner, "_n7_validate_configured_candidate_report_source", lambda **_kwargs: None
    )
    monkeypatch.setattr(catalog, "load_acquisition_supplier_declaration", load_declaration)
    monkeypatch.setattr(acquisition_route_loop, "_select_source_planner_record", select_record)
    monkeypatch.setattr(
        generation_cycle, "_requirement_missing_distributions", missing_distributions
    )
    monkeypatch.setattr(
        acquisition_world_growth, "replay_native_derivation_input_collection", replay_collection
    )

    def add_profile(scope: Any, amount: float) -> artifacts.ArtifactRef:
        return _profile_for_scope(
            store,
            scope,
            amount_usd=amount,
            now=datetime(2026, 11, 16, 12, tzinfo=UTC),
        )

    case.add_profile = add_profile
    return case


def _profile_amount(case: SimpleNamespace, ref: artifacts.ArtifactRef) -> float:
    return load_native_derivation_leaf_cost_profile(case.store, ref).line_items[0].amount


def test_explicit_refs_select_exact_historical_or_newer_leaf_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A newer stored B profile never replaces the caller's explicit B ref."""
    from tests._helpers.native_derivation_quotes import select_native_fixture_cost_profiles

    case = _case(tmp_path, monkeypatch)
    profile_a = case.add_profile(case.scope_a, 10.0)
    profile_b_old = case.add_profile(case.scope_b, 20.0)
    profile_b_new = case.add_profile(case.scope_b, 30.0)
    before = _artifact_tree(case.root)

    old_rows = select_native_fixture_cost_profiles(
        case.store, (profile_a, profile_b_old), expected_source_actor=case.actor
    )
    new_rows = select_native_fixture_cost_profiles(
        case.store, (profile_a, profile_b_new), expected_source_actor=case.actor
    )

    assert tuple(row[0] for row in old_rows) == (profile_a, profile_b_old)
    assert tuple(row[0] for row in new_rows) == (profile_a, profile_b_new)
    assert _profile_amount(case, profile_b_old) == 20.0
    assert _profile_amount(case, profile_b_new) == 30.0
    assert profile_b_old != profile_b_new
    assert _artifact_tree(case.root) == before


@pytest.mark.parametrize("duplicate", ["same_profile", "same_leaf_different_profile"])
def test_duplicate_profile_or_duplicate_leaf_refuses_without_cas_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    duplicate: str,
) -> None:
    """The selector rejects duplicate refs and two prices for one required leaf."""
    from tests._helpers.native_derivation_quotes import select_native_fixture_cost_profiles

    case = _case(tmp_path, monkeypatch)
    profile_a = case.add_profile(case.scope_a, 10.0)
    profile_b_one = case.add_profile(case.scope_b, 20.0)
    profile_b_two = case.add_profile(case.scope_b, 21.0)
    refs = (
        (profile_a, profile_b_one, profile_b_one)
        if duplicate == "same_profile"
        else (profile_a, profile_b_one, profile_b_two)
    )
    before = _artifact_tree(case.root)
    expected = (
        "native_fixture_cost_selection_duplicate"
        if duplicate == "same_profile"
        else "native_fixture_cost_leaf_scope_mismatch"
    )

    with pytest.raises(ValueError, match=expected):
        select_native_fixture_cost_profiles(case.store, refs, expected_source_actor=case.actor)
    assert _artifact_tree(case.root) == before


def test_foreign_expected_source_actor_refuses_without_cas_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The caller's actor expectation must match the canonical source reader."""
    from tests._helpers.native_derivation_quotes import select_native_fixture_cost_profiles

    case = _case(tmp_path, monkeypatch)
    refs = (case.add_profile(case.scope_a, 10.0), case.add_profile(case.scope_b, 20.0))
    before = _artifact_tree(case.root)

    with pytest.raises(ValueError, match="native_fixture_cost_source_actor_mismatch"):
        select_native_fixture_cost_profiles(
            case.store,
            refs,
            expected_source_actor=("foreign-tenant", *case.actor[1:]),
        )
    assert _artifact_tree(case.root) == before


@pytest.mark.parametrize(
    ("mismatch", "expected"),
    [
        ("source", "native_fixture_cost_leaf_scope_mismatch"),
        ("bundle", "native_fixture_cost_leaf_scope_mismatch"),
        ("supplier", "native_fixture_cost_supplier_not_selected"),
        ("supplier_target", "native_fixture_cost_provider_unresolved"),
    ],
)
def test_foreign_source_bundle_or_supplier_profile_refuses_without_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mismatch: str,
    expected: str,
) -> None:
    """Leaf scope, selected declaration, and target must agree end to end."""
    from tests._helpers.native_derivation_quotes import select_native_fixture_cost_profiles
    from tests.unit.runtime.quality.test_native_derivation_leaf_cost_profile import (
        _put_selected_fact,
    )

    case = _case(tmp_path, monkeypatch)
    profile_a = case.add_profile(case.scope_a, 10.0)
    scope_b = case.scope_b
    if mismatch in {"source", "bundle"}:
        field = "configured_port_source_ref" if mismatch == "source" else "derivation_bundle_ref"
        original = getattr(scope_b, field)
        foreign = _put_selected_fact(
            case.store, kind=original.kind, name=f"foreign_selected_{mismatch}"
        )
        assert artifacts.artifact_ref_identity_key(foreign) != artifacts.artifact_ref_identity_key(
            original
        )
        scope_b = scope_b.model_copy(update={field: foreign})
    elif mismatch == "supplier":
        scope_b = scope_b.model_copy(
            update={"selected_supplier_ref": case.scope_a.selected_supplier_ref}
        )
    else:
        key = artifacts.artifact_ref_identity_key(case.scope_b.selected_supplier_ref)
        case.declarations[key] = SimpleNamespace(
            entry=SimpleNamespace(entry_id="entry-b", target_variable="wrong-target"),
            connector_id="connector-b",
        )
    profile_b = case.add_profile(scope_b, 20.0)
    before = _artifact_tree(case.root)

    with pytest.raises(ValueError, match=expected):
        select_native_fixture_cost_profiles(
            case.store, (profile_a, profile_b), expected_source_actor=case.actor
        )
    assert _artifact_tree(case.root) == before


@pytest.mark.parametrize("problem", ["unselected_profile", "removed_quote_bytes"])
def test_unselected_profile_or_removed_quote_bytes_refuses_without_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    problem: str,
) -> None:
    """Profile or quote bytes cannot be replaced by their references alone."""
    from tests._helpers.native_derivation_quotes import select_native_fixture_cost_profiles

    case = _case(tmp_path, monkeypatch)
    profile_a = case.add_profile(case.scope_a, 10.0)
    profile_b = case.add_profile(case.scope_b, 20.0)
    if problem == "unselected_profile":
        profile_b = profile_b.model_copy(update={"manifest_profile_sha256": None})
        expected = "native_fixture_cost_selection_unselected"
    else:
        loaded = load_native_derivation_leaf_cost_profile(case.store, profile_b)
        quote_bytes = case.store._paths(loaded.quote_evidence_ref.artifact_id)[0]
        quote_bytes.unlink()
        expected = "native_derivation_leaf_cost_profile_input_unverified"
    before = _artifact_tree(case.root)

    with pytest.raises(ValueError, match=expected):
        select_native_fixture_cost_profiles(
            case.store, (profile_a, profile_b), expected_source_actor=case.actor
        )
    assert _artifact_tree(case.root) == before


def test_pending_leaf_quote_reprices_only_pending_b_and_preserves_a_and_prior_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A pending B refresh writes a new quote/profile while A remains byte stable."""
    from tests._helpers.native_derivation_quotes import prepare_retained_native_leaf_quote

    case = _case(tmp_path, monkeypatch)
    profile_a = case.add_profile(case.scope_a, 10.0)
    profile_b_old = case.add_profile(case.scope_b, 20.0)
    before = _artifact_tree(case.root)

    selected = prepare_retained_native_leaf_quote(
        case.store,
        collection_ref=case.collection_ref,
        cost_profile_refs=(profile_a, profile_b_old),
        source_node_id=case.scope_b.source_node_id,
        amount_usd=35.0,
    )

    after = _artifact_tree(case.root)
    assert selected[0] == profile_a
    assert selected[1] != profile_b_old
    assert _preserves_prior_bytes(before, after)
    assert len(after) > len(before)
    assert _profile_amount(case, profile_a) == 10.0
    assert _profile_amount(case, profile_b_old) == 20.0
    assert _profile_amount(case, selected[1]) == 35.0
    selected_profile = load_native_derivation_leaf_cost_profile(case.store, selected[1])
    quote = load_core_json_artifact(case.store, selected_profile.quote_evidence_ref)
    assert quote["line_items"][0]["amount_usd"] == 35.0


def test_owned_leaf_quote_request_refuses_before_quote_or_profile_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An already owned A leaf is not eligible for retained quote replacement."""
    from tests._helpers.native_derivation_quotes import prepare_retained_native_leaf_quote

    case = _case(tmp_path, monkeypatch)
    profile_a = case.add_profile(case.scope_a, 10.0)
    profile_b = case.add_profile(case.scope_b, 20.0)
    before = _artifact_tree(case.root)

    with pytest.raises(ValueError, match="native_fixture_quote_leaf_not_pending"):
        prepare_retained_native_leaf_quote(
            case.store,
            collection_ref=case.collection_ref,
            cost_profile_refs=(profile_a, profile_b),
            source_node_id=case.scope_a.source_node_id,
            amount_usd=99.0,
        )
    assert _artifact_tree(case.root) == before
