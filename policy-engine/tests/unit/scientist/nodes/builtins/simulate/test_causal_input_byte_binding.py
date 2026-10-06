"""Actual CAS input binding controls; these do not issue evaluation authority."""

from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from polisyos.core.artifacts import ArtifactRef, PutOptions, SchemaInfo
from polisyos.core.canon import CanonSpec
from polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation import (
    RunCausalEvaluationNode,
    _actual_causal_input_identities,
    _append_input_ref,
    _load_observational_data,
)


def test_selected_typed_view_survives_resolver_loader_and_lineage(execution_context, minimal_state):
    import numpy as np

    from polisyos.foundry.methods.causal import PanelObservationalData
    from polisyos.ir.observation import OBSERVATION_METHOD_INPUT_KIND

    data = PanelObservationalData(
        outcome=np.arange(12, dtype=float).reshape(4, 3),
        treatment=np.array([1, 1, 0, 0]),
        time_treatment=1,
    )
    store = execution_context.store
    first = store.put_json(
        data.model_dump(mode="json"),
        PutOptions(kind=OBSERVATION_METHOD_INPUT_KIND, media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    selected = store.put_json(
        data.model_dump(mode="json"),
        PutOptions(kind="ir.observational_data", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    assert first.artifact_id == selected.artifact_id
    assert store.get_manifest(selected.artifact_id).kind == first.kind
    assert store.get_manifest(selected).kind == selected.kind
    state = _state(minimal_state, selected)
    assert _actual_causal_input_identities(state, store=store)
    loaded = _load_observational_data(
        execution_context, state, "causal.inference.did.standard@1.0.0"
    )
    np.testing.assert_array_equal(loaded.outcome, data.outcome)
    lineage = []
    _append_input_ref(lineage, artifact_ref=selected, role="selected-source")
    assert lineage[0].manifest_profile_sha256 == selected.manifest_profile_sha256
    assert lineage[0].artifact_id == selected.artifact_id


from polisyos.scientist.nodes.builtins.state_keys import (
    INPUT_UKRAINE_FOUNDRY_METHOD_BUNDLE_REF,
    INPUT_UKRAINE_SELECTED_METHOD_CONTRACT_REF,
)


def _persist(store, kind="ir.observational_data", index=0):
    return store.put_json(
        {"source": index},
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name="binding-fixture", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def _state(state, ref, *, inputs=None, artifacts_index=None):
    return state.model_copy(
        update={
            "observational_data_ref": ref,
            "inputs": inputs or {},
            "artifacts_index": artifacts_index or {},
        }
    )


def test_resolved_source_uses_actual_bytes(execution_context, minimal_state):
    store = execution_context.store
    ref = _persist(store)
    state = _state(minimal_state, ref)
    digest = "sha256:" + sha256(store.get_bytes(ref)).hexdigest()
    assert _actual_causal_input_identities(state, store=store) == ((str(ref.artifact_id), digest),)
    # Equality is a property of this declared Core CAS byte profile. A PDC
    # semantic projection has a different owner and is not inferred here.


def test_complete_optional_source_set_resolves_all_refs(execution_context, minimal_state):
    store = execution_context.store
    refs = [
        _persist(store, kind, i)
        for i, kind in enumerate(
            [
                "ir.observational_data",
                "foundry.ukraine_method_input",
                "foundry.ukraine_method_input_bundle",
                "foundry.ukraine_intake_receipt",
            ]
        )
    ]
    state = _state(
        minimal_state,
        refs[0],
        inputs={
            INPUT_UKRAINE_SELECTED_METHOD_CONTRACT_REF: refs[1],
            INPUT_UKRAINE_FOUNDRY_METHOD_BUNDLE_REF: refs[2],
        },
        artifacts_index={"ukraine_foundry_intake_receipt_ref": refs[3]},
    )
    assert _actual_causal_input_identities(state, store=store) == tuple(
        (str(ref.artifact_id), "sha256:" + sha256(store.get_bytes(ref)).hexdigest()) for ref in refs
    )
    for key in state.inputs:
        partial = state.model_copy(
            update={"inputs": {k: v for k, v in state.inputs.items() if k != key}}
        )
        with pytest.raises(ValueError, match="incomplete"):
            _actual_causal_input_identities(partial, store=store)


@pytest.mark.parametrize("mutation", ["ghost", "kind", "media_type", "bytes", "size", "integrity"])
def test_invalid_source_refuses_before_verifier_load_or_job(
    execution_context, minimal_state, monkeypatch, mutation
):
    from polisyos.scientist.nodes.builtins.simulate import run_causal_evaluation as owner

    store = execution_context.store
    ref = _persist(store)
    if mutation == "ghost":
        ref = ArtifactRef(
            artifact_id="sha256:" + "0" * 64, kind=ref.kind, media_type=ref.media_type
        )
    elif mutation in {"kind", "media_type"}:
        ref = ref.model_copy(update={mutation: "wrong"})
    else:
        # Exercise the public store read boundary against an altered backend
        # projection. The real FileSystemCAS remains the source of every read.
        if mutation == "bytes":
            original = store.get_bytes
            monkeypatch.setattr(store, "get_bytes", lambda r: original(r) + b" ")
        else:
            original = store.get_manifest

            def altered(r):
                manifest = original(r)
                if mutation == "size":
                    return manifest.model_copy(update={"byte_size": manifest.byte_size + 1})
                return manifest.model_copy(
                    update={"integrity": manifest.integrity.model_copy(update={"sha256": "0" * 64})}
                )

            monkeypatch.setattr(store, "get_manifest", altered)
    node = RunCausalEvaluationNode()
    # A favorable but untrusted offered context is useful only as a negative.
    verifier, loader, job = Mock(), Mock(), Mock()
    offered = SimpleNamespace(
        mode_resolution=SimpleNamespace(status="accepted"),
        evaluator_owner_id=node.spec.metadata.component_id,
    )
    ctx = SimpleNamespace(
        **{
            **vars(execution_context),
            "eval_safety_execution_context": offered,
            "eval_safety_verifier": verifier,
        }
    )
    monkeypatch.setattr(owner, "_load_observational_data", loader)
    monkeypatch.setattr(owner, "run_job", job)
    outcome = node.execute(ctx, _state(minimal_state, ref))
    assert outcome.status == "fail"
    assert outcome.error.details["blocker_codes"] == [
        "polisyos.eval_safety.execution_input_resolution_failed@1.0.0"
    ]
    verifier.require_admission.assert_not_called()
    loader.assert_not_called()
    job.assert_not_called()


@pytest.mark.parametrize(
    "variant", ["wrong_hash", "missing", "extra", "duplicate", "provenance_duplicate"]
)
def test_offered_input_denominator_refuses_before_verifier(
    execution_context, minimal_state, monkeypatch, variant
):
    from polisyos.scientist.nodes.builtins.simulate import run_causal_evaluation as owner

    ref = _persist(execution_context.store)
    identity = SimpleNamespace(artifact_id=str(ref.artifact_id), content_hash=str(ref.artifact_id))
    refs = [identity]
    provenance = [SimpleNamespace(input_ref=identity, predicate_provenance="recomputed")]
    if variant == "wrong_hash":
        refs = [
            SimpleNamespace(artifact_id=identity.artifact_id, content_hash="sha256:" + "0" * 64)
        ]
    elif variant == "missing":
        refs = []
    elif variant == "extra":
        refs += [
            SimpleNamespace(artifact_id="sha256:" + "0" * 64, content_hash="sha256:" + "0" * 64)
        ]
    elif variant == "duplicate":
        refs += refs
    else:
        provenance += provenance
    node = RunCausalEvaluationNode()
    offered = SimpleNamespace(
        mode_resolution=SimpleNamespace(status="accepted"),
        evaluator_owner_id=node.spec.metadata.component_id,
        evaluation_input_refs=refs,
        evaluation_input_provenance=provenance,
        attempt_class="non_simulation",
    )
    verifier, loader, job = Mock(), Mock(), Mock()
    ctx = SimpleNamespace(
        **{
            **vars(execution_context),
            "eval_safety_execution_context": offered,
            "eval_safety_verifier": verifier,
        }
    )
    monkeypatch.setattr(owner, "_load_observational_data", loader)
    monkeypatch.setattr(owner, "run_job", job)
    outcome = node.execute(ctx, _state(minimal_state, ref))
    assert outcome.status == "fail"
    assert outcome.error.details["blocker_codes"] == [
        "polisyos.eval_safety.execution_context_binding_mismatch@1.0.0"
    ]
    verifier.require_admission.assert_not_called()
    loader.assert_not_called()
    job.assert_not_called()
