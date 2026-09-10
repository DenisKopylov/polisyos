"""Synthetic source custody controls; no protected admission is manufactured."""

from __future__ import annotations

import pytest

from polisyos.runtime.quality import design_generation as n4
from polisyos.runtime.quality.generation_cycle import N4GenerationPort
from tests.unit.runtime.quality.test_design_generation import (
    _bundle,
    _intervention,
    _test_design_problem,
)


@pytest.mark.asyncio
async def test_default_n4_port_preserves_actual_organ_bundle(monkeypatch):
    """The real N4 port must not erase the producer's enclosing source object."""
    problem = _test_design_problem()
    intervention = _intervention("corr_synthetic_source").model_copy(
        update={"measurement_expectations": {"synthetic": True}}
    )
    result = n4.GenerationUnderAResult(
        status="generation_unavailable",
        design_problem_ref=n4.gy_content_hash(problem.model_dump(mode="json")),
        model_id="synthetic-c2",
        preflight=n4.ModelProfilePreflight(status="gateway_unavailable", model_id="synthetic-c2"),
        diversity_report=n4.GenerationDiversityReport(
            min_required=1, candidate_count=0, unique_diversity_key_count=0
        ),
    )
    organ = result.as_organ_run(trinity_bundle=_bundle([intervention]))
    incoming_context = object()  # Transport-only witness, never an admitted/persisted context.

    async def produce(_problem, **kwargs):
        assert _problem is problem
        assert kwargs["cycle_substrate_context"] is incoming_context
        return organ

    monkeypatch.setattr(n4, "generate_design_candidate_bundle_under_a", produce)
    port = N4GenerationPort(model_id="synthetic-c2", cycle_substrate_context=incoming_context)

    observed = await port(problem, cycle_index=0)

    assert observed is organ
    assert observed.trinity_bundle is organ.trinity_bundle


def test_synthetic_cg2_contract_mechanism_remains_non_promotable():
    """A v2 synthetic seed may exercise mechanics only in its explicit contract lane."""
    from polisyos.runtime.quality.grounding_bind import (
        GroundingBindGate,
        resolve_grounding_decision_promotability,
        resolve_grounding_decision_promotability_for_contract_testing,
    )
    from polisyos.runtime.quality.grounding_relation import GroundingRelationEngine
    from polisyos.runtime.quality.promotion_sequence import (
        _cg2_resolution_is_contract_lane_bind,
    )
    from tests.unit.runtime.quality.test_grounding_bind import _pure_synonym_probe, _reference

    reference = _reference()
    engine = GroundingRelationEngine(reference)
    relation = engine.certificate_for(_pure_synonym_probe(engine), proposal_id="corr-synthetic")
    decision = GroundingBindGate.for_contract_testing(
        reference,
        calibration_seed_anchor=True,
    ).certificate_for(relation)
    mechanical = resolve_grounding_decision_promotability_for_contract_testing(decision, reference)
    actual = resolve_grounding_decision_promotability(decision, reference)

    assert decision.synthetic is True
    assert mechanical.reason == "synthetic_input_cannot_grant_authority"
    assert not mechanical.promotable
    assert not actual.promotable
    assert _cg2_resolution_is_contract_lane_bind(mechanical)
    assert not _cg2_resolution_is_contract_lane_bind(actual)
    for mutation in (
        {"owned_anchor_id": None},
        {"store_anchor_content_hash": None},
        {"store_anchor_content_hash": "sha256:" + "f" * 64},
        {"certificate_promotable_claim": True},
        {"promotable": True},
        {"authority_scope": "production"},
        {"store_authority_scope": "production"},
    ):
        assert not _cg2_resolution_is_contract_lane_bind(mechanical.model_copy(update=mutation)), (
            mutation
        )


@pytest.fixture(scope="module")
def actual_n4_source():
    """Use the actual composed WMR/L6 owners and explicitly synthetic relation inputs."""
    import hashlib
    import os
    from dataclasses import replace
    from decimal import Decimal
    from pathlib import Path

    from polisyos.core import artifacts
    from polisyos.runtime.quality.credal_reference import _component_versions, _reference_hash
    from polisyos.runtime.quality.cycle_substrate import build_cycle_substrate_context
    from polisyos.runtime.quality.intervention_substrate import (
        load_l6_intervention_substrate,
        production_composed_world_model_record,
    )
    from polisyos.runtime.quality.substrate_registry import load_substrate_registry
    from polisyos.runtime.quality.world_model_record import load_world_model_record
    from tests.unit.runtime.quality.test_design_generation import _llm_call
    from tests.unit.runtime.quality.test_grounding_bind import _reference

    root = Path(__file__).resolve().parents[4]
    pin = tuple(
        os.environ.get(key)
        for key in ("CORR_C_WORLD_CAS", "CORR_C_WORLD_REF", "CORR_C_WORLD_HASH")
    )
    if any(value is not None for value in pin):
        assert all(pin), "A replay pin must declare its store, artifact and logical record hash."
        store = artifacts.FileSystemCAS(root / pin[0])
        assert store.verify(pin[1]).ok
        assert "sha256:" + hashlib.sha256(store.get_bytes(pin[1])).hexdigest() == pin[1]
        world = load_world_model_record(store, pin[1])
        assert world.content_hash == pin[2]
    else:
        world = production_composed_world_model_record(root)
        store = artifacts.FileSystemCAS(root / ".tmp/gy-s-composed-wmr-cas")
    registry = load_substrate_registry(store, world.substrate_registry_ref.registry_artifact_ref)
    problem = _test_design_problem()
    problem = problem.model_copy(
        update={"runtime_hints": {**problem.runtime_hints, "synthetic": True}}
    )
    problem_ref = n4.gy_content_hash(problem.model_dump(mode="json"))
    context = build_cycle_substrate_context(
        design_problem_ref=problem_ref,
        domain=problem.domain,
        substrate_registry=registry,
        selected_registry_entry_hashes=tuple(
            item.entry_content_hash for item in world.substrate_registry_ref.resolved_entries
        ),
        world_model_record=world,
        intervention_substrate=load_l6_intervention_substrate(root),
        candidate_levers=(),
        transport_context=None,
        source_pack_content_hash=None,
        substrate_input_content_hash=None,
    )
    reference = _reference()
    edges = {}
    for key, edge in reference.essential_edges.items():
        changed = replace(edge, provenance={**edge.provenance, "synthetic": True})
        edges[key] = changed.with_content_hash()
    versions = _component_versions(edges, world_model_record=world)
    reference_hash = _reference_hash(
        component_versions=versions,
        edge_index=edges,
        as_of=reference.as_of,
        schema_version=reference.schema_version,
    )
    reference = replace(
        reference,
        essential_edges=edges,
        component_versions=versions,
        reference_hash=reference_hash,
        reference_epoch="kref:" + reference_hash.removeprefix("sha256:")[:16],
    )
    intervention = _intervention("corr_synthetic_source").model_copy(
        update={
            "measurement_expectations": {"synthetic": True},
            "params": {
                "rate": Decimal("0.08"),
                "target_world_slot": "global.tax_rate",
                "sign": "decrease",
                "outcome_slots": ["government.balance"],
                "effect_path": ["tax_relief_rate", "global.tax_rate", "government.balance"],
                "estimand": "average_treatment_effect",
            },
        }
    )
    bundle = _bundle([intervention])
    capture = n4._N4SourceCapture()
    candidates, dispositions = n4._content_bound_candidates(
        design_problem=problem,
        design_problem_ref=problem_ref,
        bundle=bundle,
        model_id="synthetic-c2",
        draft_path="model_generated",
        formalizer_path="model_generated",
        critic_path="model_generated",
        critique_verdict="synthetic-mechanical-control",
        calls=(_llm_call(),),
        repo_root=root,
        world_model_record_ref=world.world_model_record_id,
        reference=reference,
        cycle_substrate_context=context,
        source_capture=capture,
    )
    assert candidates, [(item.disposition, item.rejected_cause) for item in dispositions]
    result = n4.GenerationUnderAResult(
        status="generated",
        design_problem_ref=problem_ref,
        model_id="synthetic-c2",
        preflight=n4.ModelProfilePreflight(status="supported", model_id="synthetic-c2"),
        candidates=candidates,
        grounding_dispositions=dispositions,
        grounding_disposition_summary=n4._grounding_disposition_summary(dispositions),
        diversity_report=n4.GenerationDiversityReport(
            min_required=1,
            candidate_count=len(dispositions),
            unique_diversity_key_count=1,
        ),
    )
    return problem, n4.DesignGenerationOrganRun(
        result=result,
        trinity_bundle=bundle,
        cycle_substrate_context=context,
        credal_reference=capture.reference,
        candidate_sources=tuple(capture.candidates),
    )


def _source_summary(organ, cycle=0):
    from polisyos.runtime.quality.generation_cycle import CandidateSummary

    candidate = organ.result.candidates[0]
    return CandidateSummary(
        candidate_id=candidate.candidate_id,
        content_hash=candidate.atom.content_hash,
        cycle_index=cycle,
        proxy_score=0.0,
        voi_estimate=0.0,
        grounding_status="grounding_failed",
        grounding_score=0.0,
        current_valid=False,
        front="research",
        high_proxy=False,
        low_grounding=True,
    )


def _produce_source_variant(problem, original, *, bundle=None, run_budget=None):
    """Run the actual N4 source emitter for changed data or an actual N6 budget handle."""
    from dataclasses import replace
    from pathlib import Path

    from tests.unit.runtime.quality.test_design_generation import _llm_call

    bundle = original.trinity_bundle if bundle is None else bundle
    capture = n4._N4SourceCapture()
    candidates, dispositions = n4._content_bound_candidates(
        design_problem=problem,
        design_problem_ref=original.result.design_problem_ref,
        bundle=bundle,
        model_id=original.result.model_id,
        draft_path="model_generated",
        formalizer_path="model_generated",
        critic_path="model_generated",
        critique_verdict="synthetic-mechanical-control",
        calls=(_llm_call(),),
        repo_root=Path(__file__).resolve().parents[4],
        world_model_record_ref=original.cycle_substrate_context.world_model_record.world_model_record_id,
        reference=original.credal_reference,
        cycle_substrate_context=original.cycle_substrate_context,
        grounding_run_budget=run_budget,
        source_capture=capture,
    )
    assert candidates, [(item.disposition, item.rejected_cause) for item in dispositions]
    result = original.result.model_copy(
        update={
            "candidates": candidates,
            "grounding_dispositions": dispositions,
            "grounding_disposition_summary": n4._grounding_disposition_summary(dispositions),
            "diversity_report": n4.GenerationDiversityReport(
                min_required=1,
                candidate_count=len(dispositions),
                unique_diversity_key_count=len({item.diversity_key for item in candidates}),
            ),
        }
    )
    return replace(
        original,
        result=result,
        trinity_bundle=bundle,
        credal_reference=capture.reference,
        candidate_sources=tuple(capture.candidates),
    )


def test_actual_source_roundtrip_and_repeat_identity(actual_n4_source, tmp_path):
    """The same exact owner source in two cycles is idempotent, not ambiguous."""
    from polisyos.core import artifacts
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository

    problem, organ = actual_n4_source
    repository = GenerationSourceRepository(artifacts.FileSystemCAS(tmp_path / "cas"))
    run_id = "generation_cycle_" + organ.result.design_problem_ref.removeprefix("sha256:")[:16]
    refs = tuple(
        repository.persist(run_id=run_id, cycle_index=i, problem=problem, organ=organ)
        for i in range(2)
    )
    for ref in refs:
        persisted = repository.load(ref, run_id=run_id)
        assert persisted.synthetic is True
        assert persisted.generation_result == organ.result
        assert persisted.trinity_bundle == organ.trinity_bundle
    resolved = repository.resolve(
        refs=refs, run_id=run_id, summary=_source_summary(organ), problem=problem
    )
    assert resolved.status == "resolved", resolved.code
    assert (
        resolved.context["effect_obligation_writer_input"].intervention_atom
        == organ.result.candidates[0].atom
    )
    identity = (
        organ.result.design_problem_ref,
        organ.result.candidates[0].candidate_id,
        organ.result.candidates[0].atom.content_hash,
    )
    receipt = repository.preservation_receipt(
        run_id=run_id, refs=refs, expected=(identity, identity)
    )
    assert receipt.status == "strangled", receipt.issues


def test_contract_scope_marks_each_persisted_capsule(tmp_path):
    """Explicit synthetic execution marks the new artifact even with unknown old inputs."""
    from polisyos.core import artifacts
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository

    problem = _test_design_problem()
    result = n4.GenerationUnderAResult(
        status="generation_unavailable",
        design_problem_ref=n4.gy_content_hash(problem.model_dump(mode="json")),
        model_id="synthetic-c2",
        preflight=n4.ModelProfilePreflight(status="gateway_unavailable", model_id="synthetic-c2"),
        diversity_report=n4.GenerationDiversityReport(
            min_required=1, candidate_count=0, unique_diversity_key_count=0
        ),
    )
    repository = GenerationSourceRepository(artifacts.FileSystemCAS(tmp_path / "cas"))
    ref = repository.persist(
        run_id="synthetic-scope",
        cycle_index=0,
        problem=problem,
        organ=result.as_organ_run(),
        execution_scope="contract_testing",
    )
    assert repository.load(ref, run_id="synthetic-scope").synthetic is True


def test_source_replay_requires_actual_persistence_owner_profile(tmp_path):
    """Valid source bytes under another persistence profile cannot claim N4 custody."""
    from dataclasses import replace

    from polisyos.core import artifacts
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository

    problem = _test_design_problem()
    result = n4.GenerationUnderAResult(
        status="generation_unavailable",
        design_problem_ref=n4.gy_content_hash(problem.model_dump(mode="json")),
        model_id="synthetic-owner-profile",
        preflight=n4.ModelProfilePreflight(
            status="gateway_unavailable", model_id="synthetic-owner-profile"
        ),
        diversity_report=n4.GenerationDiversityReport(
            min_required=1, candidate_count=0, unique_diversity_key_count=0
        ),
    )
    store = artifacts.FileSystemCAS(tmp_path / "original")
    repository = GenerationSourceRepository(store)
    ref = repository.persist(
        run_id="synthetic-owner-profile",
        cycle_index=0,
        problem=problem,
        organ=result.as_organ_run(),
        execution_scope="contract_testing",
    )
    body, manifest = store.get_bytes(ref), store.get_manifest(ref)
    assert store.verify(ref).ok
    assert repository.load(ref, run_id="synthetic-owner-profile").synthetic is True
    options = artifacts.ArtifactWriteOptions(
        kind=manifest.kind,
        media_type=manifest.media_type,
        schema=manifest.artifact_schema,
        producer=manifest.producer,
    )
    variants = {
        "kind": {"kind": "runtime.synthetic_other_source"},
        "media": {"media_type": "application/octet-stream"},
        "schema_name": {
            "schema": manifest.artifact_schema.model_copy(update={"name": "synthetic.other.v1"})
        },
        "schema_version": {
            "schema": manifest.artifact_schema.model_copy(update={"version": "0.0"})
        },
        "producer": {
            "producer": manifest.producer.model_copy(update={"component": "synthetic.other"})
        },
        "producer_version": {
            "producer": manifest.producer.model_copy(update={"version": "0.0"})
        },
        "producer_absent": {"producer": None},
    }
    for label, mutation in variants.items():
        other = artifacts.FileSystemCAS(tmp_path / label)
        observed_ref = other.put_bytes(body, replace(options, **mutation))
        assert str(observed_ref.artifact_id) == ref
        assert other.get_bytes(ref) == body
        assert other.verify(ref).ok  # Byte integrity alone is insufficient owner provenance.
        with pytest.raises(ValueError, match="generation_source_owner_profile_mismatch"):
            GenerationSourceRepository(other).load(ref, run_id="synthetic-owner-profile")


def test_tracked_owner_epochs_remain_exactly_readable():
    """Walk complete tracked owner records; historical nested CG2 gets no new defaults."""
    import json
    from pathlib import Path

    from polisyos.runtime.quality.generation_cycle import GenerationCycleRun
    from polisyos.runtime.quality.promotion_sequence import CanonicalPromotionReceipt
    from tests.unit.runtime.quality.historical_artifacts import historical_generation_cycle_v1

    root = Path(__file__).resolve().parents[4]
    models = {
        "policyos.runtime.generation_cycle_controller.v1": GenerationCycleRun,
        "policyos.policy_design_case.layer3_gy.n9_promotion.v6": CanonicalPromotionReceipt,
    }
    documents = {
        "historical_layer3_gy_generation_cycle_contract.v1": historical_generation_cycle_v1(),
        "layer3_gy_promotion_contract.json": json.loads(
            (root / "architecture/policy_design_case/layer3_gy_promotion_contract.json").read_bytes()
        ),
    }
    recursive = {}

    def walk(value, path):
        if isinstance(value, dict):
            if value.get("schema_version") in models:
                recursive[path] = value
            for key, item in value.items():
                walk(item, (*path, key))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, (*path, str(index)))

    for name, value in documents.items():
        walk(value, (name,))
    iterative = {}
    pending = [((name,), value) for name, value in documents.items()]
    while pending:
        path, value = pending.pop()
        if isinstance(value, dict):
            if value.get("schema_version") in models:
                iterative[path] = value
            pending.extend(((*path, key), item) for key, item in value.items())
        elif isinstance(value, list):
            pending.extend(((*path, str(index)), item) for index, item in enumerate(value))
    assert recursive.keys() == iterative.keys()
    assert recursive
    assert {payload["schema_version"] for payload in recursive.values()} == models.keys()

    def leaves(value, prefix=()):
        found = {}
        if isinstance(value, dict) and value:
            for key, item in value.items():
                found.update(leaves(item, (*prefix, key)))
        elif isinstance(value, list) and value:
            for index, item in enumerate(value):
                found.update(leaves(item, (*prefix, str(index))))
        else:
            found[prefix] = value
        return found

    differences = []
    for path, payload in recursive.items():
        observed = models[payload["schema_version"]].model_validate(payload).model_dump(mode="json")
        old, new = leaves(payload), leaves(observed)
        for identity in sorted(old.keys() | new.keys()):
            if identity not in old or identity not in new or old[identity] != new[identity]:
                differences.append(
                    {
                        "record": path,
                        "path": identity,
                        "old_present": identity in old,
                        "new_present": identity in new,
                        "old": old.get(identity, "ABSENT"),
                        "new": new.get(identity, "ABSENT"),
                    }
                )
    assert not differences, json.dumps(differences, sort_keys=True)


@pytest.mark.asyncio
async def test_default_controller_custody_and_missing_protected_admission(
    actual_n4_source,
    tmp_path,
    monkeypatch,
):
    """The real default N4/N6 handoff survives before the real protected N9 refusal."""
    from pathlib import Path

    from polisyos.core import artifacts
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleController,
        PendingN8ValuePort,
    )
    from polisyos.runtime.quality.open_world_risk import PromotionRuntime
    from tests.unit.runtime.quality.test_generation_cycle import _budget

    problem, organ = actual_n4_source
    supplied_budgets = []
    actual_emissions = []

    async def produce(_problem, **kwargs):
        assert _problem == problem
        assert kwargs["cycle_substrate_context"] == organ.cycle_substrate_context
        supplied_budgets.append(kwargs["grounding_run_budget"])
        emitted = _produce_source_variant(
            problem, organ, run_budget=kwargs["grounding_run_budget"]
        )
        actual_emissions.append(emitted)
        return emitted

    monkeypatch.setattr(n4, "generate_design_candidate_bundle_under_a", produce)
    runtime = PromotionRuntime(store=artifacts.FileSystemCAS(tmp_path / "runtime"))
    controller = GenerationCycleController(
        model_id="synthetic-c2",
        repo_root=Path(__file__).resolve().parents[4],
        cycle_substrate_context=organ.cycle_substrate_context,
        promotion_runtime=runtime,
        value_port=PendingN8ValuePort(),
        authority_scope="contract_testing",
    )
    run = await controller.run(problem, budget_state=_budget(), min_cycles=1, max_cycles=1)
    assert run.synthetic is True
    assert run.source_preservation_receipt.synthetic is True
    assert run.source_preservation_receipt.status == "strangled", (
        run.source_preservation_receipt.issues
    )
    assert run.source_handoff_refs
    assert not run.promotion_port.certified_candidate_ids
    assert controller._promotion_port(admitted_batch=None, problem=problem).reason == (
        "epoch_validity_refused:pre_n9_admitted_batch_missing"
    )
    assert supplied_budgets and supplied_budgets[0] is controller._grounding_run_budget
    for source in actual_emissions[0].candidate_sources:
        admission = source.grounding_decision_certificate.run_admission
        assert admission.run_id == run.run_id
        assert admission.charged_this_attempt == 0
    before = controller._grounding_run_budget
    controller._restore_source_run(run)
    assert controller._grounding_run_budget is before
    assert tuple(controller._source_handoff_refs) == run.source_handoff_refs
    # Repeating the actual default N4 handoff is permitted without changing the problem.
    await controller._generate_node({"problem": problem, "cycle_index": 1})
    assert supplied_budgets[-1] is before
    receipt = controller._source_preservation_receipt()
    assert receipt.status == "strangled", receipt.issues
    retained_organ = actual_emissions[0]
    actual_context = controller._promotion_source_context(_source_summary(retained_organ), problem)
    assert actual_context["world_model_record"] == organ.cycle_substrate_context.world_model_record
    assert (
        actual_context["effect_obligation_writer_input"].intervention_atom
        == retained_organ.result.candidates[0].atom
    )


def test_data_only_new_candidate_preserves_complete_source_identity(actual_n4_source, tmp_path):
    """New declared IDs and parameter data traverse unchanged producers and custody owners."""
    from decimal import Decimal

    from polisyos.core import artifacts
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from polisyos.runtime.quality.grounding_bind import GroundingRunBudget

    problem, original = actual_n4_source
    run_id = "generation_cycle_" + original.result.design_problem_ref.removeprefix("sha256:")[:16]
    budget = GroundingRunBudget.for_contract_testing(tmp_path / "budget", run_id=run_id)
    intervention = original.trinity_bundle.policy_spec.interventions[0]
    changed = intervention.model_copy(
        update={
            "intervention_id": "corr_data_only_new_candidate",
            "params": {**intervention.params, "rate": Decimal("0.09")},
        }
    )
    bundle = original.trinity_bundle.model_copy(
        update={
            "policy_spec": original.trinity_bundle.policy_spec.model_copy(
                update={"interventions": [changed]}
            )
        }
    )
    originals = (
        _produce_source_variant(problem, original, run_budget=budget),
        _produce_source_variant(problem, original, bundle=bundle, run_budget=budget),
    )
    expected = {
        (value.result.design_problem_ref, candidate.candidate_id, candidate.atom.content_hash)
        for value in originals
        for candidate in value.result.candidates
    }
    assert {item.candidate_id for item in originals[0].result.candidates} != {
        item.candidate_id for item in originals[1].result.candidates
    }
    repository = GenerationSourceRepository(artifacts.FileSystemCAS(tmp_path / "cas"))
    refs = tuple(
        repository.persist(run_id=run_id, cycle_index=i, problem=problem, organ=value)
        for i, value in enumerate(originals)
    )
    restored = {
        identity for ref in refs for identity in repository.load(ref, run_id=run_id).identities()
    }
    assert restored == expected
    for value in originals:
        resolved = repository.resolve(
            refs=refs, run_id=run_id, summary=_source_summary(value), problem=problem
        )
        assert resolved.status == "resolved", resolved.code
        assert resolved.context["effect_obligation_writer_input"].intervention_atom == (
            value.result.candidates[0].atom
        )
        assert not value.candidate_sources[0].grounding_decision_certificate.production_promotable
    receipt = repository.preservation_receipt(run_id=run_id, refs=refs, expected=tuple(expected))
    assert receipt.status == "strangled", receipt.issues
    assert receipt.synthetic is True


def test_actual_retained_source_drives_effect_writer_and_marks_bridge(actual_n4_source, tmp_path):
    """Real retained owners produce a refused EFFECT artifact with explicit ancestry."""
    import hashlib
    import json
    import os
    from pathlib import Path

    from polisyos.core import artifacts
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from polisyos.runtime.quality.promotion_sequence import (
        CanonicalPromotionInput,
        N9DesignProblemBinding,
        N9PromotionEvidenceBridgeRepository,
    )

    problem, organ = actual_n4_source
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    repository = GenerationSourceRepository(store)
    ref = repository.persist(
        run_id="synthetic-writer-control", cycle_index=0, problem=problem, organ=organ
    )
    resolved = repository.resolve(
        refs=(ref,),
        run_id="synthetic-writer-control",
        summary=_source_summary(organ),
        problem=problem,
    )
    assert resolved.status == "resolved", resolved.code
    context = resolved.context
    writer = context["effect_obligation_writer_input"]
    promotion_input = CanonicalPromotionInput(
        design_problem_binding=N9DesignProblemBinding.from_problem(problem),
        candidate_summary=_source_summary(organ),
        world_model_record=context["world_model_record"],
        grounding_decision_certificate=context["grounding_decision_certificate"],
        credal_reference=context["credal_reference"],
    )
    bridge_owner = N9PromotionEvidenceBridgeRepository(store=store)
    bridge_ref = bridge_owner.persist_effect_obligation(
        promotion_input=promotion_input,
        **{name: getattr(writer, name) for name in type(writer).model_fields},
    )
    raw = store.get_bytes(bridge_ref.artifact_id)
    bridge = json.loads(raw)
    source = json.loads(store.get_bytes(bridge["source_artifact_id"]))
    assert source["synthetic"] is True
    assert any(
        edge["provenance"].get("synthetic") is True
        for edge in source["credal_reference"]["essential_edges"]
    )
    disposition = bridge_owner.resolve(
        bridge_ref=bridge_ref, promotion_input=promotion_input, evidence_kind="effect_obligation"
    )
    assert disposition.status == "refused", disposition
    assert disposition.limitation_code == "synthetic_evidence_cannot_grant_authority"
    assert bridge["source_limitation_code"] == "effect_atom_binding_shadow_only"
    compatibility_path = os.environ.get("CORR_C2_LEGACY_EFFECT_BRIDGE_PATH")
    if compatibility_path and bridge["schema_version"].endswith(".v2"):
        path = Path(compatibility_path)
        assert not path.exists()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "synthetic": True,
                    "purpose": "exact historical owner emission compatibility",
                    "body_sha256": hashlib.sha256(raw).hexdigest(),
                    "body_utf8": raw.decode(),
                },
                sort_keys=True,
            )
            + "\n"
        )
    assert bridge.get("synthetic") is True


def test_current_effect_bridge_binds_actual_historical_emitter_epoch(
    actual_n4_source, tmp_path, monkeypatch
):
    """A new run of the pinned v1 emitter remains history under a claimed v2 bridge."""
    import hashlib
    import json
    import sys
    import types

    from polisyos.core import artifacts
    from polisyos.runtime.quality import promotion_sequence as current
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from tests.unit.runtime.quality.historical_artifacts import (
        PROMOTION_EMITTER_BASE_BLOB,
        historical_owner_bytes,
    )

    problem, organ = actual_n4_source
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    repository = GenerationSourceRepository(store)
    source_ref = repository.persist(
        run_id="synthetic-historical-writer", cycle_index=0, problem=problem, organ=organ
    )
    resolved = repository.resolve(
        refs=(source_ref,),
        run_id="synthetic-historical-writer",
        summary=_source_summary(organ),
        problem=problem,
    )
    assert resolved.status == "resolved", resolved.code
    context = resolved.context
    writer = context["effect_obligation_writer_input"]
    promotion_input = current.CanonicalPromotionInput(
        design_problem_binding=current.N9DesignProblemBinding.from_problem(problem),
        candidate_summary=_source_summary(organ),
        world_model_record=context["world_model_record"],
        grounding_decision_certificate=context["grounding_decision_certificate"],
        credal_reference=context["credal_reference"],
    )

    # Execute the entire pinned historical owner. No current receipt is restamped.
    name = "polisyos.runtime.quality._corr_historical_promotion_emitter"
    historical = types.ModuleType(name)
    historical.__package__ = "polisyos.runtime.quality"
    historical.__file__ = f"git:{PROMOTION_EMITTER_BASE_BLOB}"
    monkeypatch.setitem(sys.modules, name, historical)
    raw_module = historical_owner_bytes(PROMOTION_EMITTER_BASE_BLOB)
    exec(compile(raw_module, historical.__file__, "exec"), historical.__dict__)  # noqa: S102
    old_input = historical.CanonicalPromotionInput(
        design_problem_binding=historical.N9DesignProblemBinding.from_problem(problem),
        candidate_summary=_source_summary(organ),
        world_model_record=context["world_model_record"],
        grounding_decision_certificate=context["grounding_decision_certificate"],
        credal_reference=context["credal_reference"],
    )
    old_ref = historical.N9PromotionEvidenceBridgeRepository(store=store).persist_effect_obligation(
        promotion_input=old_input,
        **{name: getattr(writer, name) for name in type(writer).model_fields},
    )
    old_bridge = json.loads(store.get_bytes(old_ref.artifact_id))
    old_raw = store.get_bytes(old_bridge["source_artifact_id"])
    old_body = json.loads(old_raw)
    assert old_body["schema_version"] == (
        "policyos.policy_design_case.layer3_gy.n9_effect_obligation_source.v1"
    )
    parsed = current._read_model(
        store=store,
        ref=artifacts.ArtifactRef(
            artifact_id=artifacts.ArtifactID(old_bridge["source_artifact_id"]),
            kind=current._EFFECT_OBLIGATION_SOURCE_KIND,
            media_type="application/vnd.polisyos.chronology+json",
        ),
        model=current._EffectObligationProducerRecord,
        kind=current._EFFECT_OBLIGATION_SOURCE_KIND,
    )
    _, _, observed = current._persist_model(
        store=store, value=parsed, kind=current._EFFECT_OBLIGATION_SOURCE_KIND
    )
    assert observed == old_raw
    (tmp_path / "historical_effect_v1.json").write_text(
        json.dumps(
            {
                "synthetic": True,
                "purpose": "new execution of the exact historical owner, not recovered history",
                "producer_git_blob": PROMOTION_EMITTER_BASE_BLOB,
                "body_sha256": hashlib.sha256(old_raw).hexdigest(),
                "body_utf8": old_raw.decode(),
            },
            sort_keys=True,
        )
    )
    owner = current.N9PromotionEvidenceBridgeRepository(store=store)
    live_ref = owner.persist_effect_obligation(
        promotion_input=promotion_input,
        **{name: getattr(writer, name) for name in type(writer).model_fields},
    )
    assert owner.resolve(
        bridge_ref=live_ref, promotion_input=promotion_input, evidence_kind="effect_obligation"
    ).limitation_code == "synthetic_evidence_cannot_grant_authority"
    live = current.N9PromotionEvidenceBridgeRecord.model_validate_json(
        store.get_bytes(live_ref.artifact_id)
    )
    misleading = live.model_copy(
        update={
            "source_artifact_id": old_bridge["source_artifact_id"],
            "source_semantic_hash": current._semantic_hash(
                current._EFFECT_OBLIGATION_SOURCE_KIND, parsed
            ),
        }
    )
    assert misleading.source_schema_ref == current._EFFECT_OBLIGATION_SOURCE_SCHEMA_VERSION
    changed_ref, _, _ = current._persist_model(
        store=store, value=misleading, kind=current._PROMOTION_EVIDENCE_BRIDGE_KIND
    )
    reference = live_ref.model_copy(
        update={
            "artifact_id": str(changed_ref.artifact_id),
            "uri": f"cas://{changed_ref.artifact_id}",
            "content_hash": n4.gy_content_hash(misleading.model_dump(mode="json")),
        }
    )
    errors, attempts, outcomes = [], [], []
    actual_reader = owner._resolve_effect_record

    def observed_reader(record, *, promotion_input):
        attempts.append(record.source_artifact_id)
        try:
            result = actual_reader(record, promotion_input=promotion_input)
            outcomes.append(result)
            return result
        except ValueError as exc:
            errors.append(str(exc))
            raise

    monkeypatch.setattr(owner, "_resolve_effect_record", observed_reader)
    refusal = owner.resolve(
        bridge_ref=reference, promotion_input=promotion_input, evidence_kind="effect_obligation"
    )
    packet = {
        "actual_source_schema": parsed.schema_version,
        "claimed_source_schema": misleading.source_schema_ref,
        "consumed_source_ids": attempts,
        "mechanical_reader_outcomes": outcomes,
        "reader_errors": errors,
        "outer_disposition": refusal.model_dump(mode="json"),
    }
    print(json.dumps(packet, sort_keys=True))
    assert attempts == [old_bridge["source_artifact_id"]], refusal
    assert errors == ["effect_obligation_source_schema_mismatch"], packet
    assert refusal.status == "not_established"
    assert refusal.limitation_code == "effect_obligation_evidence_not_established"


def test_synthetic_independence_source_establishes_mechanics_but_never_authority(
    actual_n4_source,
    tmp_path,
    monkeypatch,
):
    """A real established source cannot launder an explicitly synthetic evidence line."""
    import json

    from polisyos.core import artifacts
    from polisyos.runtime.quality.promotion_sequence import (
        _PROMOTION_EVIDENCE_BRIDGE_KIND,
        CanonicalPromotionInput,
        N9DesignProblemBinding,
        N9PromotionEvidenceBridgeRecord,
        N9PromotionEvidenceBridgeRepository,
        _persist_model,
    )
    from tests.unit.runtime.quality.test_promotion_sequence import (
        _independence_line,
        _independence_portfolio_design,
    )

    problem, organ = actual_n4_source
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    owner = N9PromotionEvidenceBridgeRepository(store=store)
    promotion_input = CanonicalPromotionInput(
        design_problem_binding=N9DesignProblemBinding.from_problem(problem),
        candidate_summary=_source_summary(organ),
        world_model_record=organ.cycle_substrate_context.world_model_record,
        grounding_decision_certificate=organ.candidate_sources[0].grounding_decision_certificate,
        credal_reference=organ.credal_reference,
    )
    line = {
        **_independence_line("corr-synthetic-paper", primary_source="journal"),
        "synthetic": True,
    }
    portfolio = {**_independence_portfolio_design(), "synthetic": True}
    bridge_ref = owner.persist_effective_independence(
        promotion_input=promotion_input,
        evidence_lines=(line,),
        portfolio_designs=(portfolio,),
        graph_id="synthetic-corr-independence",
    )
    resolution = owner.resolve(
        bridge_ref=bridge_ref,
        promotion_input=promotion_input,
        evidence_kind="effective_independence",
    )
    assert resolution.status == "refused", resolution
    assert resolution.limitation_code == "synthetic_evidence_cannot_grant_authority"
    bridge = json.loads(store.get_bytes(bridge_ref.artifact_id))
    assert bridge["synthetic"] is True
    assert bridge["source_disposition"] == "established"
    assert bridge["disposition"] == "blocked"
    source = json.loads(store.get_bytes(bridge["source_artifact_id"]))
    assert source["synthetic"] is True

    # A hostile synthetic control conceals the marker but keeps actual source,
    # current epoch, semantic outcomes and fully valid CAS/reference bindings.
    malicious = N9PromotionEvidenceBridgeRecord.model_validate(
        {
            **bridge,
            "synthetic": None,
            "disposition": "established",
            "limitation_code": bridge["source_limitation_code"],
        }
    )
    changed_ref, _semantic_hash, _raw = _persist_model(
        store=store, value=malicious, kind=_PROMOTION_EVIDENCE_BRIDGE_KIND
    )
    rebound = bridge_ref.model_copy(
        update={
            "artifact_id": str(changed_ref.artifact_id),
            "uri": f"cas://{changed_ref.artifact_id}",
            "content_hash": n4.gy_content_hash(malicious.model_dump(mode="json")),
        }
    )
    ancestry = []
    original_ancestry = owner._source_synthetic_provenance

    def observed_ancestry(source_ref, *, promotion_input):
        value = original_ancestry(source_ref, promotion_input=promotion_input)
        ancestry.append((source_ref, value))
        return value

    monkeypatch.setattr(owner, "_source_synthetic_provenance", observed_ancestry)
    concealed = owner.resolve(
        bridge_ref=rebound,
        promotion_input=promotion_input,
        evidence_kind="effective_independence",
    )
    assert ancestry == [(bridge["source_artifact_id"], True)]
    assert concealed.status == "not_established"
    assert concealed.limitation_code == "effective_independence_evidence_not_established"
    other = promotion_input.model_copy(
        update={
            "candidate_summary": promotion_input.candidate_summary.model_copy(
                update={"candidate_id": "different-synthetic-candidate"}
            )
        }
    )
    mismatch = owner.resolve(
        bridge_ref=bridge_ref, promotion_input=other, evidence_kind="effective_independence"
    )
    assert mismatch.status == "not_established"


def test_effect_writer_json_projection_preserves_complete_cg1(actual_n4_source, tmp_path):
    """Use the writer's serializer only when the actual relation owner stays identical."""
    import json

    from polisyos.core import artifacts
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from polisyos.runtime.quality.grounding_relation import GroundingRelationEngine

    problem, organ = actual_n4_source
    repository = GenerationSourceRepository(artifacts.FileSystemCAS(tmp_path / "cas"))
    ref = repository.persist(run_id="synthetic-json", cycle_index=0, problem=problem, organ=organ)
    result = repository.resolve(
        refs=(ref,), run_id="synthetic-json", summary=_source_summary(organ), problem=problem
    )
    writer = result.context["effect_obligation_writer_input"]
    original = organ.candidate_sources[0]
    projected = writer.model_dump(mode="json")["proposal"]
    engine = GroundingRelationEngine(organ.credal_reference)
    before = engine.certificate_for(original.proposal, proposal_id=original.proposal_id)
    after = engine.certificate_for(projected, proposal_id=original.proposal_id)
    assert before == after == original.grounding_relation_certificate
    # This is the actual existing writer intake, not a capsule codec approximation.
    assert json.loads(json.dumps(writer.proposal, sort_keys=True)) == projected


def test_candidate_custody_requires_actual_reference(actual_n4_source, tmp_path):
    """A complete-looking candidate without its original reference cannot be retained."""
    from dataclasses import replace

    from polisyos.core import artifacts
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository

    problem, organ = actual_n4_source
    repository = GenerationSourceRepository(artifacts.FileSystemCAS(tmp_path / "cas"))
    with pytest.raises(ValueError, match="generation_source_owner_input_missing"):
        repository.persist(
            run_id="synthetic-missing-reference",
            cycle_index=0,
            problem=problem,
            organ=replace(organ, credal_reference=None),
        )


def test_semantically_changed_writer_projection_refuses(actual_n4_source, tmp_path, monkeypatch):
    """A valid-looking JSON projection may not alter a decisive grounding axis."""
    from polisyos.core import artifacts
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from polisyos.runtime.quality.grounding_relation import GroundingRelationEngine
    from polisyos.runtime.quality.promotion_sequence import _EffectObligationWriterInput

    problem, organ = actual_n4_source
    repository = GenerationSourceRepository(artifacts.FileSystemCAS(tmp_path / "cas"))
    ref = repository.persist(run_id="synthetic-projection", cycle_index=0, problem=problem, organ=organ)
    serializer = _EffectObligationWriterInput.model_dump
    changed_proposals = []

    def changed(self, *args, **kwargs):
        payload = serializer(self, *args, **kwargs)
        if kwargs.get("mode") == "json":
            payload["proposal"]["signature"]["sign"] = "increase"
            changed_proposals.append(payload["proposal"])
        return payload

    monkeypatch.setattr(_EffectObligationWriterInput, "model_dump", changed)
    observed = repository.resolve(
        refs=(ref,), run_id="synthetic-projection", summary=_source_summary(organ), problem=problem
    )
    assert changed_proposals, "the existing writer serializer was not consumed"
    original = organ.candidate_sources[0]
    engine = GroundingRelationEngine(organ.credal_reference)
    altered = engine.certificate_for(changed_proposals[0], proposal_id=original.proposal_id)
    assert altered != original.grounding_relation_certificate
    assert observed.status == "not_established"
    assert observed.code == "effect_writer_projection_grounding_mismatch"
    assert "effect_obligation_writer_input" not in observed.context


def test_conflicting_complete_source_for_same_triple_refuses(actual_n4_source, tmp_path):
    """Different actual source provenance cannot collapse into an idempotent candidate."""
    from dataclasses import replace

    from polisyos.core import artifacts
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository

    problem, organ = actual_n4_source
    candidate = organ.result.candidates[0]
    altered = candidate.model_copy(
        update={
            "provenance": candidate.provenance.model_copy(
                update={"raw_llm_responses": ("synthetic second occurrence: different raw input",)}
            )
        }
    )
    other = replace(organ, result=organ.result.model_copy(update={"candidates": (altered,)}))
    repository = GenerationSourceRepository(artifacts.FileSystemCAS(tmp_path / "cas"))
    refs = tuple(
        repository.persist(run_id="synthetic-conflict", cycle_index=i, problem=problem, organ=value)
        for i, value in enumerate((organ, other))
    )
    resolved = repository.resolve(
        refs=refs, run_id="synthetic-conflict", summary=_source_summary(organ), problem=problem
    )
    assert resolved.status == "not_established"
    assert resolved.code == "source_ambiguous"
    assert not resolved.context
    receipt = repository.preservation_receipt(
        run_id="synthetic-conflict",
        refs=refs,
        expected=((organ.result.design_problem_ref, candidate.candidate_id, candidate.atom.content_hash),),
    )
    assert receipt.status == "drift"
    assert "source_identity_conflict" in receipt.issues


def test_source_intake_recomputes_original_candidate_provenance(actual_n4_source, tmp_path):
    """A resealed capsule cannot replace the original parsed intervention with a summary."""
    from polisyos.core import artifacts, canon
    from polisyos.runtime.quality.generation_source import (
        _SOURCE_CANON,
        GenerationSourceRepository,
        _source_content_hash,
    )

    problem, organ = actual_n4_source
    repository = GenerationSourceRepository(artifacts.FileSystemCAS(tmp_path / "cas"))
    ref = repository.persist(run_id="synthetic-reseal", cycle_index=0, problem=problem, organ=organ)
    artifact = repository.load(ref, run_id="synthetic-reseal")
    payload = artifact.model_dump(mode="python", exclude={"content_hash"})
    payload["generation_result"]["candidates"][0]["provenance"]["parsed_candidate"] = {
        "synthetic": True,
        "summary": "the original typed intervention has been discarded",
    }
    payload["content_hash"] = _source_content_hash(payload)
    manifest = repository.store.get_manifest(ref)
    changed_ref = repository.store.put_bytes(
        canon.to_canonical_bytes(payload, _SOURCE_CANON),
        artifacts.ArtifactWriteOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            producer=manifest.producer,
        ),
    )
    assert repository.store.verify(changed_ref.artifact_id).ok
    with pytest.raises(ValueError, match="generation_source_original_candidate_mismatch"):
        repository.load(str(changed_ref.artifact_id), run_id="synthetic-reseal")


def test_n4_nonbinding_surface_retains_actual_cg3_authority_limitation():
    """The actual synthetic CG3 admission stays visible in N4's refusal-path output."""
    from polisyos.runtime.quality.grounding_admission import GroundingAdmissionEngine
    from tests.unit.runtime.quality.test_grounding_admission import (
        _cg2_novel,
        _novel_transfer_probe,
        _reference,
    )

    reference = _reference(include_mechanism=True)
    cg1, cg2 = _cg2_novel(reference, _novel_transfer_probe())
    cg3 = GroundingAdmissionEngine(reference).decide(cg2, cg1_certificate=cg1)
    assert cg3.synthetic is True
    assert not cg3.production_promotable
    observed = n4._non_binding_cause(cg1, cg2, cg3)
    assert observed["synthetic"] is True
    assert observed["authority_limitation"] == cg3.authority_limitation
