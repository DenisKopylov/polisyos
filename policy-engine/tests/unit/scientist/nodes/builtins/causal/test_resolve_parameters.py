"""Gap-coverage tests for ResolveParametersNode."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from polisyos.core.artifacts import (
    ensure_ir_artifact_store as _ensure_ir_artifact_store,
)
from polisyos.core.artifacts import (
    input_ref_from_artifact_ref,
    profile_bound_ref,
)
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    InputRef,
    ProducerInfo,
)
from polisyos.core.artifacts.manifest import (
    CanonInfo as CoreCanonInfo,
)
from polisyos.core.artifacts.manifest import (
    SchemaInfo as CoreSchemaInfo,
)
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.data_forge.read_api.academic import RetainedSKGSourceBinding
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    GraphType,
    persist_causal_graph_model,
)
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.cross_graph import (
    CrossGraphEvidenceProfile,
    CrossGraphEvidenceSummary,
    persist_cross_graph_evidence_profile,
)
from polisyos.ir.analytics.parameters import (
    ContextAdaptiveParameterBundle,
    ContextAdaptiveParameterBundleV11,
    ContextAdaptiveParameterBundleV12,
    ParameterApplicability,
    load_context_adaptive_parameter_bundle,
    persist_context_adaptive_parameter_bundle,
    persist_context_adaptive_parameter_bundle_v1_1,
)
from polisyos.ir.analytics.transportability import TransportabilityStatus, TransportMode
from polisyos.ir.artifacts import put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import (
    CausalGraphModelRef,
    ContextAdaptiveParameterBundleRef,
    CrossGraphEvidenceProfileRef,
)
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.causal.resolve_parameters import (
    ResolveParametersNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF,
    ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
)
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome
from polisyos.scientist.orchestration.engine.state_branching import (
    branch_state as real_branch_state,
)


def _core_artifact_ref(
    ref: ArtifactRef
    | CausalGraphModelRef
    | ContextAdaptiveParameterBundleRef
    | CrossGraphEvidenceProfileRef,
) -> ArtifactRef:
    """Normalize an IR ref to the complete Core artifact-ref wire model."""
    return ArtifactRef.model_validate(ref.model_dump(mode="json"))


def _graph_profile_pair(store):
    """Persist one graph blob under two distinct manifest profiles."""
    ir_store = _ensure_ir_artifact_store(store)
    graph_ref = persist_causal_graph_model(
        ir_store,
        CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=["X", "Y"],
            edges=[CausalEdge(src="X", dst="Y")],
        ),
    )
    selected_v1 = profile_bound_ref(ir_store, graph_ref)
    original_manifest = ir_store.get_manifest(selected_v1)
    raw = ir_store.get_bytes(selected_v1)
    second_ref = ir_store.put_bytes(
        raw,
        ArtifactWriteOptions(
            kind="ir.causal_graph_model",
            media_type="application/json",
            schema=CoreSchemaInfo(name="ir.causal_graph_model", version="2.0"),
            canon=CoreCanonInfo.model_validate(original_manifest.canon.model_dump(mode="python")),
        ),
    )
    selected_v2 = profile_bound_ref(
        ir_store,
        CausalGraphModelRef.model_validate(second_ref.model_dump(mode="json")),
    )
    # These refs intentionally name the same blob while selecting different manifest views.
    assert selected_v1.artifact_id == selected_v2.artifact_id
    assert selected_v1.manifest_profile_sha256 != selected_v2.manifest_profile_sha256
    return selected_v1, selected_v2


def _cross_graph_profile_pair(store):
    """Persist one cross-graph profile blob under two manifest profiles."""
    ir_store = _ensure_ir_artifact_store(store)
    profile_ref = persist_cross_graph_evidence_profile(
        ir_store,
        CrossGraphEvidenceProfile(summary=CrossGraphEvidenceSummary()),
    )
    selected_v1 = profile_bound_ref(ir_store, profile_ref)
    original_manifest = ir_store.get_manifest(selected_v1)
    raw = ir_store.get_bytes(selected_v1)
    second_ref = ir_store.put_bytes(
        raw,
        ArtifactWriteOptions(
            kind="ir.cross_graph_evidence_profile",
            media_type="application/json",
            schema=CoreSchemaInfo(
                name="ir.cross_graph_evidence_profile",
                version="2.1",
            ),
            canon=CoreCanonInfo.model_validate(
                original_manifest.canon.model_copy(update={"exclude_none": False}).model_dump(
                    mode="python"
                )
            ),
        ),
    )
    selected_v2 = profile_bound_ref(
        ir_store,
        CrossGraphEvidenceProfileRef.model_validate(second_ref.model_dump(mode="json")),
    )
    # These refs intentionally name the same blob while selecting different manifest views.
    assert selected_v1.artifact_id == selected_v2.artifact_id
    assert selected_v1.manifest_profile_sha256 != selected_v2.manifest_profile_sha256
    return selected_v1, selected_v2


def _v1_1_bundle(bundle, inputs):
    """Build a v1.1 fixture bound to the selected manifest profile edge."""
    profile_inputs = [item for item in inputs if item.role == "cross_graph_evidence_profile"]
    selected_ref = None
    if profile_inputs:
        profile_input = profile_inputs[0]
        selected_ref = CrossGraphEvidenceProfileRef(
            artifact_id=profile_input.artifact_id,
            manifest_profile_sha256=profile_input.manifest_profile_sha256,
        )
    payload = bundle.model_dump(mode="python")
    payload["schema_version"] = "1.1"
    payload["selected_cross_graph_profile_ref"] = selected_ref
    return ContextAdaptiveParameterBundleV11.model_validate(payload)


def _persist_v1_1_bundle(store, bundle, *, inputs):
    return persist_context_adaptive_parameter_bundle_v1_1(
        store,
        _v1_1_bundle(bundle, inputs),
        inputs=inputs,
    )


def _persist_unchecked_v1_1_bundle(store, bundle, *, inputs):
    """Persist corrupt cache candidates so the reader's refusal is exercised."""
    versioned = _v1_1_bundle(bundle, inputs)
    return put_json_artifact(
        _ensure_ir_artifact_store(store),
        versioned.model_dump(mode="json"),
        kind="ir.context_adaptive_parameter_bundle",
        schema_name="ir.context_adaptive_parameter_bundle",
        schema_version="1.1",
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
    )


def _persist_and_capture(store, bundle, *, inputs, observed):
    observed["inputs"] = inputs
    observed["bundle"] = bundle
    payload = put_json_artifact(
        _ensure_ir_artifact_store(store),
        bundle.model_dump(mode="json"),
        kind="ir.context_adaptive_parameter_bundle",
        schema_name="ir.context_adaptive_parameter_bundle",
        schema_version="1.2",
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
    )
    bundle_ref = ContextAdaptiveParameterBundleRef.model_validate(payload)
    observed["bundle_ref"] = bundle_ref
    return bundle_ref


def _cached_request_state(minimal_state, graph_ref, bundle_ref, *, profile_ref=None):
    state = minimal_state.model_copy(deep=True)
    state.params.update(
        {
            "target_context": ContextProfile(context_id="control").model_dump(mode="json"),
            "required_parameters": ["beta"],
            "domain": "fiscal",
        }
    )
    state.artifacts_index[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF] = graph_ref
    state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF] = bundle_ref
    if profile_ref is not None:
        state.artifacts_index[ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF] = profile_ref
    return state


def test_skip_when_missing_target_context(execution_context, minimal_state):
    """No params.target_context -> skip."""
    state = minimal_state.model_copy(
        update={
            "params": {
                "required_parameters": ["param_a"],
            },
        },
    )
    outcome = ResolveParametersNode().execute(execution_context, state)
    assert outcome.status == "skip"
    assert any("target_context" in e.message for e in outcome.events)


def test_skip_when_target_context_invalid(execution_context, minimal_state):
    """Invalid target_context payload that cannot parse as ContextProfile -> skip."""
    state = minimal_state.model_copy(
        update={
            "params": {
                "target_context": "not_a_dict",
                "required_parameters": ["beta"],
            },
        },
    )
    outcome = ResolveParametersNode().execute(execution_context, state)
    assert outcome.status == "skip"
    assert any("target_context" in e.message for e in outcome.events)


def test_skip_when_missing_required_parameters(execution_context, minimal_state):
    """No params.required_parameters -> skip at first guard (target_context absent)."""
    state = minimal_state.model_copy(
        update={
            "params": {},
        },
    )
    outcome = ResolveParametersNode().execute(execution_context, state)
    assert outcome.status == "skip"
    # Without target_context the first guard triggers
    assert len(outcome.events) >= 1


def test_skip_when_required_parameters_empty_list(execution_context, minimal_state):
    """Valid target_context but required_parameters is an empty list -> skip."""
    state = minimal_state.model_copy(
        update={
            "params": {
                "target_context": {"country": "US", "year": 2025},
                "required_parameters": [],
            },
        },
    )
    outcome = ResolveParametersNode().execute(execution_context, state)
    assert outcome.status == "skip"
    assert any(
        "required_parameters" in e.message or "parameter" in e.message.lower()
        for e in outcome.events
    )


def test_existing_bundle_requires_valid_cas_artifact(
    execution_context,
    minimal_state,
    artifact_ref_factory,
):
    """A valid persisted bundle reuses; a non-CAS ref cannot claim success."""
    valid_ref = persist_context_adaptive_parameter_bundle(
        _ensure_ir_artifact_store(execution_context.store),
        ContextAdaptiveParameterBundle(
            target_context=ContextProfile(context_id="control"),
            simulation_domain="unknown",
        ),
    )
    valid_state = minimal_state.model_copy(deep=True)
    valid_state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF] = valid_ref

    valid_outcome = ResolveParametersNode().execute(execution_context, valid_state)

    assert valid_outcome.status == "ok"
    assert valid_outcome.state is valid_state

    invalid_state = minimal_state.model_copy(deep=True)
    invalid_state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF] = (
        artifact_ref_factory(kind="ir.context_adaptive_parameter_bundle")
    )

    invalid_outcome = ResolveParametersNode().execute(execution_context, invalid_state)

    assert invalid_outcome.status == "skip"


def test_target_context_assertion_is_not_swallowed(
    execution_context, minimal_state, monkeypatch: pytest.MonkeyPatch
):
    state = minimal_state.model_copy(
        update={
            "params": {
                "target_context": {"country": "US", "year": 2025},
                "required_parameters": ["beta"],
            },
        }
    )

    def _boom(*args, **kwargs):
        del args, kwargs
        raise AssertionError("context-broken")

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.resolve_parameters.ContextProfile.model_validate",
        _boom,
    )

    with pytest.raises(AssertionError, match="context-broken"):
        ResolveParametersNode().execute(execution_context, state)


@pytest.mark.parametrize("select_profile", [False, True])
def test_resolve_parameters_uses_branch_state_for_declared_outputs(
    execution_context, minimal_state, tmp_path, select_profile: bool
):
    graph_ref, _ = _graph_profile_pair(execution_context.store)
    db_path = tmp_path / "skg.duckdb"
    db_path.write_text("", encoding="utf-8")

    state = minimal_state.model_copy(deep=True)
    state.artifacts_index[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF] = graph_ref
    profile = None
    cross_graph_profile_ref = None
    if select_profile:
        profile = CrossGraphEvidenceProfile(summary=CrossGraphEvidenceSummary())
        cross_graph_profile_ref = persist_cross_graph_evidence_profile(
            _ensure_ir_artifact_store(execution_context.store),
            profile,
        )
        state.artifacts_index[ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF] = cross_graph_profile_ref
    state.params.update(
        {
            "target_context": {
                "context_id": "us-2025",
                "countries": ["US"],
                "publication_year": 2025,
            },
            "required_parameters": ["beta"],
            "skg_db_path": str(db_path),
            "nested": {"baseline": True},
        }
    )
    observed: dict[str, object] = {}

    def _spy_branch(base_state, *, write_paths=()):
        observed["write_paths"] = tuple(write_paths)
        return real_branch_state(base_state, write_paths=write_paths)

    with (
        patch(
            "polisyos.scientist.nodes.builtins.causal.resolve_parameters.branch_state",
            _spy_branch,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.resolve_parameters.load_causal_graph_model",
            return_value=MagicMock(),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.resolve_parameters.SKGQuery",
        ) as skg_query_cls,
        patch(
            "polisyos.scientist.nodes.builtins.causal.resolve_parameters.ParameterSelector",
        ) as selector_cls,
        patch(
            "polisyos.scientist.nodes.builtins.causal.resolve_parameters.retain_prepared_skg_read",
            side_effect=lambda *_args: observed["source_ref"],
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.resolve_parameters.retained_skg_source_binding",
            side_effect=lambda *_args: observed["source_binding"],
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.resolve_parameters.persist_context_adaptive_parameter_bundle_v1_2",
            side_effect=lambda store, bundle, *, inputs: _persist_and_capture(
                store, bundle, inputs=inputs, observed=observed
            ),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.resolve_parameters.ParameterTransferData",
            side_effect=lambda **kwargs: kwargs,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.resolve_parameters.ParameterTransfer.pure_step",
            return_value={
                "literature_priors": {"beta": {"mean": 1.0}},
                "uncertainty_multipliers": {"beta": 1.1},
                "runtime_backend_used": "numpy",
                "runtime_parameter_intervals": {"beta": [0.8, 1.2]},
                "runtime_ready": True,
            },
        ),
    ):
        source_payload_ref = execution_context.store.put_bytes(
            b"{}",
            ArtifactWriteOptions(
                kind="scientist.skg_source_snapshot",
                media_type="application/json",
                schema=CoreSchemaInfo(
                    name="scientist.skg_source_snapshot",
                    version="1.1",
                ),
                producer=ProducerInfo(component="tests.resolve_parameters", version="1.0"),
            ),
            return_selected_profile=True,
        )
        source_ref = ArtifactRef.model_validate(source_payload_ref.model_dump(mode="json"))
        source_binding = RetainedSKGSourceBinding(
            descriptor_ref=source_ref,
            source_reference="snapshot",
            source_sha256="a" * 64,
            source_version_id=1,
            source_binding_schema_version="academic.skg_source_binding.v2",
            query_version="skg-query-read.v3",
            version_identity_kind="content_digest",
        )
        observed["source_ref"] = source_ref
        observed["source_binding"] = source_binding
        prepared_read = skg_query_cls.prepare_read.return_value
        prepared_read.source_snapshot_ref = "snapshot"
        prepared_read.source_snapshot_sha256 = source_binding.source_sha256
        prepared_read.source_binding_schema_version = source_binding.source_binding_schema_version
        prepared_read.query_version = source_binding.query_version
        prepared_read.source_generation_matches.return_value = True
        skg_query = prepared_read.query
        skg_query.latest_skg_version_id.return_value = 1
        skg_query.skg_snapshot_ref.return_value = "snapshot"
        selector_cls.return_value.select_for_context.return_value = (
            None,
            ParameterApplicability(
                parameter_id="beta",
                target_context_id="us-2025",
                transport_status=TransportabilityStatus.UNSUPPORTED,
                transport_mode=TransportMode.NONE,
                transport_confidence=0.0,
                context_distance=0.0,
                is_applicable=False,
                adjustment_required=False,
            ),
        )
        outcome = ResolveParametersNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert observed["write_paths"] == (
        "artifacts_index.context_adaptive_parameter_bundle_ref",
        "params.literature_priors",
        "params.parameter_uncertainty_multipliers",
        "params.phase15_runtime_backend_used",
        "params.phase15_runtime_parameter_intervals",
        "params.phase15_runtime_ready",
    )
    assert state.params["nested"] == {"baseline": True}
    assert ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF not in state.artifacts_index
    produced_bundle_ref = outcome.state.artifacts_index[
        ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF
    ]
    persisted_ir_bundle_ref = ContextAdaptiveParameterBundleRef.model_validate(
        observed["bundle_ref"].model_dump(mode="json")
    )
    expected_bundle_ref = _core_artifact_ref(persisted_ir_bundle_ref)
    emitted_bundle_ref = _core_artifact_ref(produced_bundle_ref)
    assert emitted_bundle_ref.model_dump(mode="json") == expected_bundle_ref.model_dump(mode="json")
    assert outcome.state.params["phase15_runtime_ready"] is True
    persisted_inputs = observed["inputs"]
    assert (
        selector_cls.return_value.select_for_context.call_args.kwargs["cross_graph_profile"]
        == profile
    )
    selected_profile_ref = None
    if select_profile:
        selected_profile_ref = profile_bound_ref(
            _ensure_ir_artifact_store(execution_context.store),
            cross_graph_profile_ref,
        )
    ir_store = _ensure_ir_artifact_store(execution_context.store)
    persisted_manifest = ir_store.get_manifest(persisted_ir_bundle_ref)
    persisted_bundle = observed["bundle"]
    assert isinstance(persisted_bundle, ContextAdaptiveParameterBundleV12)
    expected_inputs = [
        input_ref_from_artifact_ref(
            _core_artifact_ref(graph_ref),
            role="causal_graph",
        )
    ]
    if selected_profile_ref is not None:
        expected_inputs.append(
            input_ref_from_artifact_ref(
                _core_artifact_ref(selected_profile_ref),
                role="cross_graph_evidence_profile",
            )
        )
    expected_inputs.append(input_ref_from_artifact_ref(source_ref, role="skg_source_snapshot"))
    assert persisted_inputs == expected_inputs
    assert persisted_manifest.inputs == expected_inputs
    if selected_profile_ref is None:
        assert persisted_bundle.selected_cross_graph_profile_ref is None
    else:
        assert persisted_bundle.selected_cross_graph_profile_ref == selected_profile_ref
    assert persisted_bundle.selected_skg_source == source_binding
    assert persisted_bundle.skg_version_id == 1


def test_cache_hit_requires_exact_graph_profile_and_role(
    execution_context,
    minimal_state,
):
    graph_v1, graph_v2 = _graph_profile_pair(execution_context.store)
    target_context = ContextProfile(context_id="control")
    bundle_ref = _persist_v1_1_bundle(
        _ensure_ir_artifact_store(execution_context.store),
        ContextAdaptiveParameterBundle(
            target_context=target_context,
            simulation_domain="fiscal",
            unsupported_parameters=["beta"],
        ),
        inputs=[
            input_ref_from_artifact_ref(
                ArtifactRef.model_validate(graph_v1.model_dump(mode="json")),
                role="causal_graph",
            )
        ],
    )
    cached_state = _cached_request_state(minimal_state, graph_v1, bundle_ref)
    cached_outcome = NodeOutcome(status="ok", state=cached_state)
    node = ResolveParametersNode()

    assert node.validate_cache_hit(execution_context, cached_state, cached_outcome)
    changed_view = _cached_request_state(minimal_state, graph_v2, bundle_ref)
    assert not node.validate_cache_hit(execution_context, changed_view, cached_outcome)
    different_id_ref = profile_bound_ref(
        _ensure_ir_artifact_store(execution_context.store),
        persist_causal_graph_model(
            _ensure_ir_artifact_store(execution_context.store),
            CausalGraphModel(
                graph_type=GraphType.DAG,
                nodes=["Z", "W"],
                edges=[CausalEdge(src="Z", dst="W")],
            ),
        ),
    )
    different_id = _cached_request_state(minimal_state, different_id_ref, bundle_ref)
    assert not node.validate_cache_hit(execution_context, different_id, cached_outcome)

    for wrong_inputs in (
        [],
        [
            InputRef(
                artifact_id=graph_v1.artifact_id,
                role="wrong_role",
                manifest_profile_sha256=graph_v1.manifest_profile_sha256,
            )
        ],
        [InputRef(artifact_id=graph_v1.artifact_id, role="causal_graph")],
        [
            InputRef(
                artifact_id=graph_v1.artifact_id,
                role="causal_graph",
                manifest_profile_sha256="sha256:" + "f" * 64,
            )
        ],
    ):
        wrong_bundle = _persist_unchecked_v1_1_bundle(
            _ensure_ir_artifact_store(execution_context.store),
            ContextAdaptiveParameterBundle(
                target_context=target_context,
                simulation_domain="fiscal",
                unsupported_parameters=["beta"],
            ),
            inputs=wrong_inputs,
        )
        wrong_state = _cached_request_state(minimal_state, graph_v1, wrong_bundle)
        assert not node.validate_cache_hit(
            execution_context, wrong_state, NodeOutcome(status="ok", state=wrong_state)
        )


def test_cache_hit_requires_exact_cross_graph_profile_and_role(
    execution_context,
    minimal_state,
):
    graph_ref, _other_graph_ref = _graph_profile_pair(execution_context.store)
    profile_v1, profile_v2 = _cross_graph_profile_pair(execution_context.store)
    target_context = ContextProfile(context_id="control")
    bundle_ref = _persist_v1_1_bundle(
        _ensure_ir_artifact_store(execution_context.store),
        ContextAdaptiveParameterBundle(
            target_context=target_context,
            simulation_domain="fiscal",
            unsupported_parameters=["beta"],
        ),
        inputs=[
            input_ref_from_artifact_ref(
                ArtifactRef.model_validate(graph_ref.model_dump(mode="json")),
                role="causal_graph",
            ),
            input_ref_from_artifact_ref(
                ArtifactRef.model_validate(profile_v1.model_dump(mode="json")),
                role="cross_graph_evidence_profile",
            ),
        ],
    )
    state = _cached_request_state(
        minimal_state,
        graph_ref,
        bundle_ref,
        profile_ref=profile_v1,
    )
    cached = NodeOutcome(status="ok", state=state)
    node = ResolveParametersNode()

    assert node.validate_cache_hit(execution_context, state, cached)
    assert node.execute(execution_context, state).status == "ok"

    changed_view = _cached_request_state(
        minimal_state,
        graph_ref,
        bundle_ref,
        profile_ref=profile_v2,
    )
    assert not node.validate_cache_hit(
        execution_context,
        changed_view,
        NodeOutcome(status="ok", state=changed_view),
    )
    assert node.execute(execution_context, changed_view).status == "skip"

    absent_profile = _cached_request_state(minimal_state, graph_ref, bundle_ref)
    assert not node.validate_cache_hit(
        execution_context,
        absent_profile,
        NodeOutcome(status="ok", state=absent_profile),
    )

    wrong_bundle = _persist_unchecked_v1_1_bundle(
        _ensure_ir_artifact_store(execution_context.store),
        ContextAdaptiveParameterBundle(
            target_context=target_context,
            simulation_domain="fiscal",
            unsupported_parameters=["beta"],
        ),
        inputs=[
            input_ref_from_artifact_ref(
                ArtifactRef.model_validate(graph_ref.model_dump(mode="json")),
                role="causal_graph",
            ),
            InputRef(artifact_id=profile_v1.artifact_id, role="wrong_role"),
        ],
    )
    wrong_state = _cached_request_state(
        minimal_state,
        graph_ref,
        wrong_bundle,
        profile_ref=profile_v1,
    )
    assert not node.validate_cache_hit(
        execution_context,
        wrong_state,
        NodeOutcome(status="ok", state=wrong_state),
    )


@pytest.mark.parametrize("corruption", ["malformed", "stale-profile"])
def test_invalid_supplied_graph_ref_is_not_treated_as_absence_or_cache_hit(
    execution_context,
    minimal_state,
    corruption: str,
) -> None:
    graph_v1, _graph_v2 = _graph_profile_pair(execution_context.store)
    bundle_ref = _persist_v1_1_bundle(
        _ensure_ir_artifact_store(execution_context.store),
        ContextAdaptiveParameterBundle(
            target_context=ContextProfile(context_id="control"),
            simulation_domain="fiscal",
            unsupported_parameters=["beta"],
        ),
        inputs=[
            input_ref_from_artifact_ref(
                ArtifactRef.model_validate(graph_v1.model_dump(mode="json")),
                role="causal_graph",
            )
        ],
    )
    if corruption == "malformed":
        supplied_ref = graph_v1.model_copy(update={"kind": "ir.not_a_causal_graph"})
    else:
        supplied_ref = graph_v1.model_copy(update={"manifest_profile_sha256": "sha256:" + "f" * 64})
    state = _cached_request_state(minimal_state, supplied_ref, bundle_ref)
    node = ResolveParametersNode()

    assert not node.validate_cache_hit(
        execution_context,
        state,
        NodeOutcome(status="ok", state=state),
    )
    outcome = node.execute(execution_context, state)
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == node_errors.ERROR_INVALID_STATE
    assert "Invalid supplied causal graph reference" in outcome.error.message


@pytest.mark.parametrize(
    "corruption",
    [
        "explicit-null",
        "malformed",
        "wrong-kind",
        "stale-profile",
        "unloadable",
        "incompatible-manifest-schema",
        "incompatible-payload-schema",
    ],
)
def test_invalid_supplied_cross_graph_profile_is_not_absence_or_cache_hit(
    execution_context,
    minimal_state,
    tmp_path,
    corruption: str,
) -> None:
    graph_ref, _graph_v2 = _graph_profile_pair(execution_context.store)
    bundle_ref = _persist_v1_1_bundle(
        _ensure_ir_artifact_store(execution_context.store),
        ContextAdaptiveParameterBundle(
            target_context=ContextProfile(context_id="control"),
            simulation_domain="fiscal",
            unsupported_parameters=["beta"],
        ),
        inputs=[
            input_ref_from_artifact_ref(
                ArtifactRef.model_validate(graph_ref.model_dump(mode="json")),
                role="causal_graph",
            )
        ],
    )
    state = _cached_request_state(minimal_state, graph_ref, bundle_ref)
    state.params["skg_db_path"] = str(tmp_path / "skg.duckdb")

    if corruption == "explicit-null":
        supplied_profile = None
    elif corruption == "malformed":
        supplied_profile = {"artifact_id": "not-an-artifact-reference"}
    elif corruption == "wrong-kind":
        graph_payload = graph_ref.model_dump(mode="json")
        graph_payload["kind"] = "ir.causal_graph_model"
        supplied_profile = graph_payload
    elif corruption == "stale-profile":
        profile_ref, _profile_v2 = _cross_graph_profile_pair(execution_context.store)
        supplied_profile = profile_ref.model_copy(
            update={"manifest_profile_sha256": "sha256:" + "0" * 64}
        )
    elif corruption == "unloadable":
        supplied_profile = CrossGraphEvidenceProfileRef(artifact_id="sha256:" + "f" * 64)
    elif corruption == "incompatible-manifest-schema":
        supplied_profile = persist_cross_graph_evidence_profile(
            _ensure_ir_artifact_store(execution_context.store),
            CrossGraphEvidenceProfile(summary=CrossGraphEvidenceSummary()),
            schema_version="9.9",
        )
    else:
        supplied_profile = persist_cross_graph_evidence_profile(
            _ensure_ir_artifact_store(execution_context.store),
            CrossGraphEvidenceProfile(
                schema_version="9.9",
                summary=CrossGraphEvidenceSummary(),
            ),
        )
    state.artifacts_index[ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF] = supplied_profile

    node = ResolveParametersNode()
    cached = NodeOutcome(status="ok", state=state)

    assert node.prepare_cache_input(execution_context, state) is None
    assert not node.validate_cache_hit(execution_context, state, cached)
    outcome = node.execute(execution_context, state)
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == node_errors.ERROR_INVALID_STATE
    assert "Invalid supplied cross-graph evidence profile reference" in outcome.error.message


@pytest.mark.parametrize("selector_source", ["params", "artifacts_index"])
def test_explicit_null_graph_selector_is_not_treated_as_absence_or_cache_hit(
    execution_context,
    minimal_state,
    selector_source: str,
) -> None:
    graph_v1, _graph_v2 = _graph_profile_pair(execution_context.store)
    bundle_ref = _persist_v1_1_bundle(
        _ensure_ir_artifact_store(execution_context.store),
        ContextAdaptiveParameterBundle(
            target_context=ContextProfile(context_id="control"),
            simulation_domain="fiscal",
            unsupported_parameters=["beta"],
        ),
        inputs=[
            input_ref_from_artifact_ref(
                ArtifactRef.model_validate(graph_v1.model_dump(mode="json")),
                role="causal_graph",
            )
        ],
    )
    state = _cached_request_state(minimal_state, graph_v1, bundle_ref)
    if selector_source == "params":
        state.artifacts_index.pop(ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF)
        state.params["causal_graph_ref"] = None
    else:
        # Exercise corruption of the in-memory typed index after state parsing.
        state.artifacts_index[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF] = None  # type: ignore[assignment]
    node = ResolveParametersNode()
    cached_outcome = NodeOutcome(status="ok", state=state)

    assert not node.validate_cache_hit(execution_context, state, cached_outcome)
    outcome = node.execute(execution_context, state)
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == node_errors.ERROR_INVALID_STATE
    assert "explicitly null" in outcome.error.message


def test_true_graph_absence_keeps_the_existing_skip_boundary(
    execution_context,
    minimal_state,
) -> None:
    state = minimal_state.model_copy(deep=True)
    state.params.update(
        {
            "target_context": ContextProfile(context_id="control").model_dump(mode="json"),
            "required_parameters": ["beta"],
            "domain": "fiscal",
        }
    )

    outcome = ResolveParametersNode().execute(execution_context, state)

    assert outcome.status == "skip"
    assert outcome.error is None
    assert any("No causal graph reference available" in event.message for event in outcome.events)


def test_existing_bundle_reuse_requires_exact_graph_manifest_profile(
    execution_context,
    minimal_state,
):
    graph_v1, graph_v2 = _graph_profile_pair(execution_context.store)
    bundle_ref = _persist_v1_1_bundle(
        _ensure_ir_artifact_store(execution_context.store),
        ContextAdaptiveParameterBundle(
            target_context=ContextProfile(context_id="control"),
            simulation_domain="fiscal",
            unsupported_parameters=["beta"],
        ),
        inputs=[
            input_ref_from_artifact_ref(
                ArtifactRef.model_validate(graph_v1.model_dump(mode="json")),
                role="causal_graph",
            )
        ],
    )
    matching = _cached_request_state(minimal_state, graph_v1, bundle_ref)
    mismatching = _cached_request_state(minimal_state, graph_v2, bundle_ref)

    assert ResolveParametersNode().execute(execution_context, matching).status == "ok"
    assert ResolveParametersNode().execute(execution_context, mismatching).status == "skip"


def test_legacy_v1_0_bundle_is_readable_but_not_reused_for_active_request(
    execution_context,
    minimal_state,
) -> None:
    graph_ref, _graph_v2 = _graph_profile_pair(execution_context.store)
    bundle_ref = persist_context_adaptive_parameter_bundle(
        _ensure_ir_artifact_store(execution_context.store),
        ContextAdaptiveParameterBundle(
            target_context=ContextProfile(context_id="control"),
            simulation_domain="fiscal",
            unsupported_parameters=["beta"],
        ),
        inputs=[
            input_ref_from_artifact_ref(
                ArtifactRef.model_validate(graph_ref.model_dump(mode="json")),
                role="causal_graph",
            )
        ],
    )
    state = _cached_request_state(minimal_state, graph_ref, bundle_ref)
    node = ResolveParametersNode()
    cached = NodeOutcome(status="ok", state=state)

    assert isinstance(
        load_context_adaptive_parameter_bundle(
            _ensure_ir_artifact_store(execution_context.store), bundle_ref
        ),
        ContextAdaptiveParameterBundle,
    )
    assert not node.validate_cache_hit(execution_context, state, cached)
    assert node.execute(execution_context, state).status != "ok"
