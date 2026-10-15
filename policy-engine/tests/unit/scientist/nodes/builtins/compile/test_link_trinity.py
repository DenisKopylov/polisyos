from __future__ import annotations

from unittest.mock import MagicMock, patch

from polisyos.core.artifacts import CanonInfo, PutOptions, SchemaInfo
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TRINITY_BUNDLE_SCHEMA_VERSION, TrinityBundle
from polisyos.scientist.nodes.builtins.compile.link_trinity import LinkTrinityNode
from polisyos.scientist.nodes.builtins.state_keys import (
    INPUT_TRINITY_BUNDLE_REF,
    REPORT_LINK_REPORT_REF,
)
from polisyos.scientist.orchestration.engine.state_branching import (
    branch_state as real_branch_state,
)


def test_link_success(execution_context, minimal_state, artifact_ref_factory):
    """Successful link produces a link report."""
    trinity_ref = _put_trinity_bundle(execution_context.store)

    state = minimal_state.model_copy(deep=True)
    state.inputs[INPUT_TRINITY_BUNDLE_REF] = trinity_ref

    mock_link_report = MagicMock()
    mock_link_report.ok = True
    link_report_ref = artifact_ref_factory(kind="compiler.link_report")

    _mod = "polisyos.scientist.nodes.builtins.compile.link_trinity"
    with (
        patch(f"{_mod}.load_registry_bundle_content", return_value=MagicMock()),
        patch(f"{_mod}.RegistryBundle", return_value=MagicMock()),
        patch(f"{_mod}.link_trinity", return_value=(MagicMock(), mock_link_report)),
        patch(f"{_mod}.put_link_report", return_value=link_report_ref),
    ):
        outcome = LinkTrinityNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert REPORT_LINK_REPORT_REF in outcome.state.reports_index


def test_link_missing_refs(execution_context, minimal_state):
    """Missing trinity or registry ref causes fail."""
    outcome = LinkTrinityNode().execute(execution_context, minimal_state)
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "node.missing_input"


def test_link_missing_trinity_only(execution_context, minimal_state):
    """With registry but no trinity ref, also fails."""
    # minimal_state already has registry_bundle_ref but no trinity_bundle_ref
    outcome = LinkTrinityNode().execute(execution_context, minimal_state)
    assert outcome.status == "fail"
    assert outcome.error.code == "node.missing_input"


def test_link_trinity_uses_branch_state_for_report_output(
    execution_context,
    minimal_state,
    artifact_ref_factory,
):
    trinity_ref = _put_trinity_bundle(execution_context.store)
    link_report_ref = artifact_ref_factory(kind="compiler.link_report")

    state = minimal_state.model_copy(deep=True)
    state.inputs[INPUT_TRINITY_BUNDLE_REF] = trinity_ref
    observed: dict[str, tuple[str, ...]] = {}

    def _spy_branch(base_state, *, write_paths=()):
        observed["write_paths"] = tuple(write_paths)
        return real_branch_state(base_state, write_paths=write_paths)

    _mod = "polisyos.scientist.nodes.builtins.compile.link_trinity"
    with (
        patch(f"{_mod}.branch_state", _spy_branch),
        patch(f"{_mod}.load_registry_bundle_content", return_value=MagicMock()),
        patch(f"{_mod}.RegistryBundle", return_value=MagicMock()),
        patch(f"{_mod}.link_trinity", return_value=(MagicMock(), MagicMock(ok=True))),
        patch(f"{_mod}.put_link_report", return_value=link_report_ref),
    ):
        outcome = LinkTrinityNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert observed["write_paths"] == ("reports_index.link_report_ref",)
    assert REPORT_LINK_REPORT_REF not in state.reports_index
    assert outcome.state.reports_index[REPORT_LINK_REPORT_REF] == link_report_ref


def test_link_route_refuses_trinity_bytes_with_unowned_schema_profile(
    execution_context,
    minimal_state,
):
    store = execution_context.store
    bundle = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="profile_owner", domain="social"),
        policy_spec=PolicySpec(policy_id="profile_owner"),
        model_spec=ModelSpec(
            model_id="profile_owner",
            data_snapshot_ref="sha256:" + "b" * 64,
        ),
    )
    spec = CanonSpec(forbid_floats=False, exclude_none=False)
    trinity_ref = store.put_bytes(
        to_canonical_bytes(bundle, spec),
        PutOptions(
            kind=TrinityBundle.ARTIFACT_KIND,
            media_type=TrinityBundle.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(name="polisyos.test.TrinityBundle", version="9.9"),
            canon=CanonInfo.from_spec(spec),
        ),
        return_selected_profile=True,
    )
    state = minimal_state.model_copy(deep=True)
    state.inputs[INPUT_TRINITY_BUNDLE_REF] = trinity_ref

    with (
        patch(
            "polisyos.scientist.nodes.builtins.compile.link_trinity.load_registry_bundle_content",
            return_value=MagicMock(),
        ) as load_registry,
        patch(
            "polisyos.scientist.nodes.builtins.compile.link_trinity.link_trinity",
            return_value=(MagicMock(), MagicMock(ok=True)),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.compile.link_trinity.put_link_report",
            return_value=MagicMock(),
        ),
    ):
        outcome = LinkTrinityNode().execute(execution_context, state)

    load_registry.assert_not_called()
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "node.invalid_state"
    assert "failed owner admission" in outcome.error.message


def _put_trinity_bundle(store):
    bundle = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="link_test", domain="social"),
        policy_spec=PolicySpec(policy_id="link_test"),
        model_spec=ModelSpec(
            model_id="link_test",
            data_snapshot_ref="sha256:" + "c" * 64,
        ),
    )
    return store.put_json(
        bundle,
        PutOptions(
            kind=TrinityBundle.ARTIFACT_KIND,
            media_type=TrinityBundle.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=TrinityBundle.ARTIFACT_SCHEMA_NAME,
                version=TRINITY_BUNDLE_SCHEMA_VERSION,
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
        return_selected_profile=True,
    )
