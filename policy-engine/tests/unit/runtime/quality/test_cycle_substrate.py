from __future__ import annotations

import hashlib
from typing import Any

import pytest

from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality import cycle_substrate as cycle_substrate_owner
from polisyos.runtime.quality.cycle_substrate import (
    CandidateLeverEvidence,
    CycleSubstrateContext,
    TransportContextEvidence,
    TransportCovariateObservation,
    build_cycle_substrate_context,
    cycle_substrate_context_binding_hash,
    cycle_substrate_context_content_hash,
)
from polisyos.runtime.quality.intervention_substrate import (
    InterventionSubstrateBundle,
    InterventionSubstrateError,
    resolve_intervention_lever,
    resolve_law_bound_lever,
    route_observation_family_method,
)
from polisyos.runtime.quality.substrate_registry import (
    SubstrateCoverage,
    SubstrateLayer,
    SubstrateRegistration,
    SubstrateRegistry,
    SubstrateSchemaRegime,
    SubstrateTrustTier,
    build_substrate_registry,
    build_substrate_registry_entry,
)
from polisyos.runtime.quality.world_model_record import (
    BranchMode,
    DataForgeBindingRef,
    FabricWorldRef,
    FoundryBindingRef,
    PolicySlotBinding,
    ResolvedSubstrateEntryRef,
    SimulationModelRef,
    SkgCausalPriorRef,
    SubstrateRegistryRef,
    WorldModelRecord,
    WorldModelRecordError,
    world_model_record_content_hash,
)


def _hash(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _registry(domain: str) -> SubstrateRegistry:
    registration = SubstrateRegistration(
        source_id=f"l2_scholar_kg:{domain}.duckdb",
        family_id=f"{domain}_causal_priors",
        layer=SubstrateLayer.L2,
        coverage=SubstrateCoverage(
            coverage_score=0.8,
            coverage_kind="lane0.causal_claim_coverage",
            coverage_rule_ref=f"lane0://{domain}/coverage",
            observation_count=4,
            metric_binding_count=4,
        ),
        trust_tier=SubstrateTrustTier(
            tier="derived_proxy",
            trust_cap=0.5,
            trust_multiplier=0.6,
            min_coverage=0.0,
            max_coverage=1.0,
            authority_ref=f"lane0://{domain}/trust",
        ),
        identification_mode="causal_prior_candidate",
        schema_regime=SubstrateSchemaRegime(
            schema_regime_id=f"{domain}_schema_v1",
            authority_ref=f"lane0://{domain}/schema",
            source_version="1",
        ),
        data_version=f"{domain}-data-v1",
        snapshot_id=f"{domain}-snapshot-v1",
        source_snapshot_id=f"{domain}-snapshot-v1",
        provenance_refs=(f"lane0://{domain}/causal-claims",),
        authority_refs=(f"lane0://{domain}/registry-owner",),
    )
    entry = build_substrate_registry_entry(registration)
    return build_substrate_registry(
        (entry,),
        producer_ref="tests.unit.runtime.quality.test_cycle_substrate",
        source_catalog_refs=registration.authority_refs,
    )


def _world_record(
    domain: str,
    registry: SubstrateRegistry,
    *,
    resolved_entry_content_hash: str | None = None,
    resolved_family_id: str | None = None,
    duplicate_resolved_family_id: str | None = None,
    world_model_record_id: str | None = None,
    region_or_jurisdiction: str | None = None,
) -> WorldModelRecord:
    entry = registry.entries[0]
    resolved_entry = ResolvedSubstrateEntryRef(
        source_id=entry.source_id,
        family_id=resolved_family_id or entry.family_id,
        layer=entry.layer,
        coverage_score=entry.coverage.coverage_score,
        trust_tier=entry.trust_tier.tier,
        trust_cap=entry.trust_tier.trust_cap,
        identification_mode=entry.identification_mode,
        schema_regime_id=entry.schema_regime.schema_regime_id,
        data_version=entry.data_version,
        snapshot_id=entry.snapshot_id,
        source_snapshot_id=entry.source_snapshot_id,
        entry_content_hash=(
            resolved_entry_content_hash or entry.entry_content_hash
        ),
    )
    resolved_entries = (resolved_entry,)
    if duplicate_resolved_family_id is not None:
        resolved_entries = (
            resolved_entry.model_copy(
                update={"family_id": duplicate_resolved_family_id}
            ),
            resolved_entry,
        )
    registry_ref = SubstrateRegistryRef(
        substrate_version_id=registry.substrate_version_id,
        content_hash=registry.content_hash,
        registry_artifact_ref=f"lane0://{domain}/substrate-registry",
        resolved_entries=resolved_entries,
    )
    fields: dict[str, Any] = {
        "schema_version": "policyos.runtime.world_model_record.v1",
        "authority_status": "limited",
        "created_at": "2026-07-12T00:00:00+00:00",
        "producer_ref": "tests.unit.runtime.quality.test_cycle_substrate",
        "region_or_jurisdiction": region_or_jurisdiction or f"lane0-{domain}",
        "population_scope": f"{domain}_population",
        "policy_domain": domain,
        "valid_time_scope": "2020/2025",
        "tx_time_scope": "2026-07-12T00:00:00+00:00",
        "resolution": "entity_year",
        "branch_mode": BranchMode.OBSERVED,
        "fabric_world_ref": FabricWorldRef(
            snapshot_root=f"/lane0/{domain}",
            snapshot_id=f"{domain}-snapshot-v1",
            branch="observed",
            world_query_policy="lane0_content_bound",
            provenance_manifest_ref=f"lane0://{domain}/manifest",
            content_query_digest=_hash(f"{domain}:world-query"),
            content_query_row_count=4,
        ),
        "data_forge_binding_ref": DataForgeBindingRef(
            snapshot_id=f"{domain}-snapshot-v1",
            release_id=f"{domain}-release-v1",
            role="domain",
            read_api_identity=f"lane0.{domain}.read_api",
            snapshot_ref=f"lane0://{domain}/snapshot",
            merkle_root=f"merkle:{domain}:v1",
            data_hash=_hash(f"{domain}:data"),
            provenance_manifest_ref=f"lane0://{domain}/data-manifest",
        ),
        "simulation_model_ref": SimulationModelRef(
            model_spec_ref=_hash(f"{domain}:model-spec"),
            model_spec_hash=_hash(f"{domain}:model-hash"),
            model_id=f"model_{domain}",
            data_snapshot_ref=_hash(f"{domain}:data-snapshot"),
            registry_bundle_ref=_hash(f"{domain}:registry-bundle"),
            fidelity_level="boundary",
            calibrated=False,
        ),
        "foundry_binding_ref": FoundryBindingRef(
            input_bindings_ref=_hash(f"{domain}:input-bindings"),
            bound_state_snapshot_ref=_hash(f"{domain}:bound-state"),
            mapping_rules_ref=_hash(f"{domain}:mapping-rules"),
            state_slot_digest=_hash(f"{domain}:state-slots"),
        ),
        "skg_causal_prior_ref": SkgCausalPriorRef(
            skg_snapshot_ref=f"lane0://{domain}/skg",
            skg_version_id=f"{domain}-skg-v1",
            source_data_snapshot_id=f"{domain}-snapshot-v1",
        ),
        "substrate_registry_ref": registry_ref,
        "policy_slot_map": (
            PolicySlotBinding(
                slot_id=f"{domain}_outcome",
                state_path=f"substrate.{domain}.outcome",
                entity_scope="population",
                temporal_granularity="year",
            ),
        ),
    }
    draft = WorldModelRecord.model_construct(
        world_model_record_id="world_model_record_0000000000000000",
        content_hash=_hash(f"{domain}:placeholder"),
        **fields,
    )
    content_hash = world_model_record_content_hash(draft)
    return WorldModelRecord(
        world_model_record_id=world_model_record_id
        or f"world_model_record_{content_hash.removeprefix('sha256:')[:16]}",
        content_hash=content_hash,
        **fields,
    )


def _cycle_context(
    *,
    domain: str = "education",
    lever_id: str = "education_teaching_method",
    instrument: str = "education.teaching_method",
    target_concept: str = "education.learning_outcomes",
    transport_covariate: str = "school_quality",
    registry: SubstrateRegistry | None = None,
    world_model_record: WorldModelRecord | None = None,
    intervention_substrate: InterventionSubstrateBundle | None = None,
    design_problem_ref: str | None = None,
) -> CycleSubstrateContext:
    registry = registry or _registry(domain)
    world_model_record = world_model_record or _world_record(domain, registry)
    selected_hash = registry.entries[0].entry_content_hash
    design_problem_ref = design_problem_ref or _hash(f"{domain}:design-problem")
    substrate_input_hash = _hash(f"{domain}:substrate-input")
    context_binding_hash = cycle_substrate_context_binding_hash(
        design_problem_ref=design_problem_ref,
        domain=domain,
        substrate_input_content_hash=substrate_input_hash,
        substrate_registry_content_hash=registry.content_hash,
        world_model_record_id=world_model_record.world_model_record_id,
        world_model_record_content_hash=world_model_record.content_hash,
        world_model_record_authority_status=world_model_record.authority_status,
        selected_registry_entry_hashes=(selected_hash,),
    )
    candidate = CandidateLeverEvidence(
        lever_id=lever_id,
        instrument=instrument,
        target_concept=target_concept,
        status="candidate_unbound",
        entry_content_hash=gy_content_hash(
            {
                "lever_id": lever_id,
                "instrument": instrument,
                "target_concept": target_concept,
            }
        ),
        substrate_input_content_hash=substrate_input_hash,
        selected_registry_entry_hash=selected_hash,
        context_binding_hash=context_binding_hash,
        source_refs=(f"lane0://{domain}/candidate-lever",),
    )
    transport = TransportContextEvidence(
        status="candidate_context_only_not_transport_authority",
        source_context_id=f"{domain}:source",
        target_context_id=f"{domain}:target",
        source_profile_content_hash=_hash(f"{domain}:source-profile"),
        target_profile_content_hash=_hash(f"{domain}:target-profile"),
        substrate_input_content_hash=substrate_input_hash,
        context_binding_hash=context_binding_hash,
        covariates=(
            TransportCovariateObservation(
                canonical_var=transport_covariate,
                source_value=1.0,
                target_value=2.0,
                source_row_content_hash=_hash(f"{domain}:{transport_covariate}:source"),
                target_row_content_hash=_hash(f"{domain}:{transport_covariate}:target"),
            ),
        ),
    )
    return build_cycle_substrate_context(
        design_problem_ref=design_problem_ref,
        domain=domain,
        substrate_registry=registry,
        selected_registry_entry_hashes=(selected_hash,),
        world_model_record=world_model_record,
        intervention_substrate=intervention_substrate,
        candidate_levers=(candidate,),
        transport_context=transport,
        source_pack_content_hash=_hash(f"{domain}:source-pack"),
        substrate_input_content_hash=substrate_input_hash,
    )


def test_world_context_resolution_uses_problem_and_wmr_evidence_not_domain_label() -> None:
    """A producer-scoped label cannot hide an exact content-bound world match."""

    registry = _registry("fiscal_credit")
    world = _world_record(
        "fiscal_credit",
        registry,
        region_or_jurisdiction="UA",
    )
    context = _cycle_context(
        domain="Ukraine economic policy",
        registry=registry,
        world_model_record=world,
    )

    resolved = cycle_substrate_owner.resolve_cycle_substrate_context_for_world(
        (context,),
        design_problem_ref=context.design_problem_ref,
        region_or_jurisdiction="UA",
    )

    assert resolved.content_hash == context.content_hash
    assert resolved.domain == "Ukraine economic policy"
    assert resolved.world_model_record.policy_domain == "fiscal_credit"


def test_world_context_resolution_refuses_no_match_and_ambiguity() -> None:
    """Missing or competing worlds must fail closed instead of selecting first."""

    problem_ref = _hash("shared-design-problem")
    contexts: list[CycleSubstrateContext] = []
    for domain in ("fiscal_credit", "public_finance"):
        registry = _registry(domain)
        contexts.append(
            _cycle_context(
                domain=f"producer-label-{domain}",
                registry=registry,
                world_model_record=_world_record(
                    domain,
                    registry,
                    region_or_jurisdiction="UA",
                ),
                design_problem_ref=problem_ref,
            )
        )

    with pytest.raises(
        WorldModelRecordError,
        match="cycle_substrate_context_unresolved",
    ):
        cycle_substrate_owner.resolve_cycle_substrate_context_for_world(
            tuple(contexts),
            design_problem_ref=problem_ref,
            region_or_jurisdiction="unseen-world",
        )

    with pytest.raises(
        WorldModelRecordError,
        match="cycle_substrate_context_ambiguous",
    ):
        cycle_substrate_owner.resolve_cycle_substrate_context_for_world(
            tuple(contexts),
            design_problem_ref=problem_ref,
            region_or_jurisdiction="UA",
        )


def test_cycle_substrate_context_binds_registry_wmr_and_pack_hashes() -> None:
    context = _cycle_context()

    assert context.substrate_registry_content_hash == context.substrate_registry.content_hash
    assert context.world_model_record_content_hash == context.world_model_record.content_hash
    assert context.source_pack_content_hash == _hash("education:source-pack")
    assert context.substrate_input_content_hash == _hash("education:substrate-input")
    assert {row.status for row in context.candidate_levers} == {"candidate_unbound"}
    assert context.authority_purpose == "cycle_input_candidate_only"


def test_cycle_substrate_context_rejects_stale_registry_hash() -> None:
    payload = _cycle_context().model_dump(mode="python")
    payload["substrate_registry_content_hash"] = _hash("stale")

    with pytest.raises(ValueError, match="cycle_substrate_registry_hash_mismatch"):
        CycleSubstrateContext.model_validate(payload)


def test_cycle_substrate_context_rejects_cross_context_candidate() -> None:
    education = _cycle_context()
    water = _cycle_context(
        domain="water_quality",
        lever_id="riparian_buffer_width",
        instrument="water.riparian_buffer_width",
        target_concept="water.nutrient_load",
        transport_covariate="watershed_slope",
    )
    payload = education.model_dump(mode="python")
    payload["candidate_levers"] = [
        water.candidate_levers[0].model_dump(mode="python")
    ]

    with pytest.raises(ValueError, match="candidate_context_binding_mismatch"):
        CycleSubstrateContext.model_validate(payload)


def test_cycle_substrate_context_rejects_wmr_registry_mismatch() -> None:
    education_registry = _registry("education")
    water_world = _world_record("water_quality", _registry("water_quality"))

    with pytest.raises(ValueError, match="wmr_registry_content_mismatch"):
        _cycle_context(
            registry=education_registry,
            world_model_record=water_world,
        )


def test_cycle_substrate_context_rejects_selected_entry_absent_from_wmr() -> None:
    registry = _registry("education")
    world = _world_record(
        "education",
        registry,
        resolved_entry_content_hash=_hash("unrelated-resolved-entry"),
    )

    with pytest.raises(
        ValueError,
        match="cycle_substrate_selected_entry_wmr_unresolved",
    ):
        _cycle_context(registry=registry, world_model_record=world)


def test_cycle_substrate_context_rejects_shaped_wmr_entry_projection() -> None:
    registry = _registry("education")
    shaped_world = _world_record(
        "education",
        registry,
        resolved_family_id="wrong_family_with_valid_entry_hash",
    )

    with pytest.raises(
        ValueError,
        match="cycle_substrate_selected_entry_projection_mismatch",
    ):
        _cycle_context(registry=registry, world_model_record=shaped_world)


def test_cycle_substrate_context_rejects_duplicate_wmr_entry_hashes() -> None:
    registry = _registry("education")
    duplicate_world = _world_record(
        "education",
        registry,
        duplicate_resolved_family_id="contradictory_family",
    )

    with pytest.raises(
        ValueError,
        match="cycle_substrate_wmr_resolved_entry_hash_duplicate",
    ):
        _cycle_context(registry=registry, world_model_record=duplicate_world)


def test_cycle_substrate_context_records_domain_label_drift_as_provenance() -> None:
    registry = _registry("education")
    water_labeled_world = _world_record("water_quality", registry)

    context = _cycle_context(
        domain="education",
        registry=registry,
        world_model_record=water_labeled_world,
    )

    assert context.domain == "education"
    assert context.world_model_record.policy_domain == "water_quality"
    assert context.world_model_record_content_hash == water_labeled_world.content_hash


def test_cycle_substrate_context_rejects_wmr_id_not_derived_from_content() -> None:
    registry = _registry("education")
    shaped_world = _world_record(
        "education",
        registry,
        world_model_record_id="world_model_record_ffffffffffffffff",
    )

    with pytest.raises(ValueError, match="cycle_substrate_wmr_id_mismatch"):
        _cycle_context(registry=registry, world_model_record=shaped_world)


def test_cycle_substrate_context_binds_wmr_authority_status() -> None:
    registry = _registry("education")
    limited_world = _world_record("education", registry)
    publishable_world = limited_world.model_copy(
        update={"authority_status": "publishable"}
    )

    limited = _cycle_context(registry=registry, world_model_record=limited_world)
    publishable = _cycle_context(
        registry=registry,
        world_model_record=publishable_world,
    )

    assert limited.context_binding_hash != publishable.context_binding_hash
    assert limited.content_hash != publishable.content_hash


def test_cycle_substrate_context_rejects_cross_context_transport() -> None:
    education = _cycle_context()
    water = _cycle_context(
        domain="water_quality",
        lever_id="riparian_buffer_width",
        instrument="water.riparian_buffer_width",
        target_concept="water.nutrient_load",
        transport_covariate="watershed_slope",
    )
    payload = education.model_dump(mode="python")
    payload["transport_context"] = water.transport_context.model_dump(mode="python")
    payload["content_hash"] = cycle_substrate_context_content_hash(payload)

    with pytest.raises(ValueError, match="transport_context_binding_mismatch"):
        CycleSubstrateContext.model_validate(payload)


def _intervention_bundle() -> InterventionSubstrateBundle:
    fields: dict[str, Any] = {
        "knob_dictionary": {
            "lane0_knob": {
                "type": "float",
                "min": 0.0,
                "max": 1.0,
            }
        },
        "lex_intervention_map": {},
        "observation_manifest": {},
        "source_refs": {"intervention_knob_dictionary": "lane0://l6/knobs"},
        "source_content_hashes": {
            "intervention_knob_dictionary": _hash("lane0:l6:knobs")
        },
    }
    return InterventionSubstrateBundle(
        **fields,
        content_hash=gy_content_hash(
            {
                "schema_version": "policyos.runtime.intervention_substrate_lift.v1",
                "policy_scenario_templates": {},
                "slot_family_manifest": {},
                "world_mechanism_manifest": {},
                "lex_authority_manifest": {},
                "owner_authority_manifest": {},
                **fields,
            }
        ),
    )


def test_cycle_substrate_context_revalidates_mutated_intervention_bundle() -> None:
    bundle = _intervention_bundle()
    context = _cycle_context(intervention_substrate=bundle)
    bundle.knob_dictionary["forged_after_validation"] = {"type": "float"}
    revalidate = getattr(
        __import__(
            "polisyos.runtime.quality.cycle_substrate",
            fromlist=["revalidate_cycle_substrate_context"],
        ),
        "revalidate_cycle_substrate_context",
        None,
    )

    assert callable(revalidate), "cycle substrate consumption revalidator missing"
    with pytest.raises(
        ValueError,
        match="cycle_substrate_intervention_bundle_hash_mismatch",
    ):
        revalidate(context)


def test_intervention_substrate_bundle_rejects_claimed_hash_at_owner_intake() -> None:
    payload = _intervention_bundle().model_dump(mode="python")
    payload["knob_dictionary"]["forged_before_intake"] = {"type": "float"}

    with pytest.raises(
        ValueError,
        match="intervention_substrate_bundle_content_hash_mismatch",
    ):
        InterventionSubstrateBundle.model_validate(payload)


def test_intervention_resolver_rechecks_bundle_hash_after_nested_mutation() -> None:
    bundle = _intervention_bundle()
    bundle.knob_dictionary["forged_after_intake"] = {"type": "float"}

    with pytest.raises(InterventionSubstrateError) as error:
        resolve_intervention_lever(
            bundle,
            operator_kind="lane0_knob",
            parameter_value=0.5,
        )

    assert error.value.code == "intervention_substrate_bundle_content_hash_mismatch"


def test_law_resolver_rechecks_bundle_hash_before_lex_authority_use() -> None:
    bundle = _intervention_bundle()
    law_ref = "forged_law"
    bundle.lex_intervention_map[law_ref] = {"knob_ids": ["lane0_knob"]}

    with pytest.raises(InterventionSubstrateError) as error:
        resolve_law_bound_lever(
            bundle,
            law_token=law_ref,
            knob_id="lane0_knob",
            parameter_value=0.5,
            legal_store=object(),  # type: ignore[arg-type]
        )

    assert error.value.code == "intervention_substrate_bundle_content_hash_mismatch"


def test_method_router_rechecks_bundle_hash_before_manifest_use() -> None:
    bundle = _intervention_bundle()
    bundle.observation_manifest["forged_route"] = {"family": "forged_family"}

    with pytest.raises(InterventionSubstrateError) as error:
        route_observation_family_method(bundle, family="forged_family")

    assert error.value.code == "intervention_substrate_bundle_content_hash_mismatch"


def test_third_pack_vocabulary_needs_no_engine_branch() -> None:
    context = _cycle_context(
        domain="water_quality",
        lever_id="riparian_buffer_width",
        instrument="water.riparian_buffer_width",
        target_concept="water.nutrient_load",
        transport_covariate="watershed_slope",
    )

    assert context.candidate_levers[0].lever_id == "riparian_buffer_width"
    assert context.candidate_levers[0].instrument == "water.riparian_buffer_width"
    assert context.transport_context is not None
    assert context.transport_context.covariates[0].canonical_var == "watershed_slope"


def test_third_pack_lever_reaches_typed_resolver_refusal_without_code_branch() -> None:
    """A third pack-shaped vocabulary follows the same exact resolver owner."""

    bundle = _intervention_bundle()
    context = _cycle_context(
        domain="water_quality",
        lever_id="riparian_buffer_width",
        instrument="water.riparian_buffer_width",
        target_concept="water.nutrient_load",
        transport_covariate="watershed_slope",
        intervention_substrate=bundle,
    )

    result = resolve_intervention_lever(
        bundle,
        operator_kind="water.riparian_buffer_width",
        parameter_value=3.0,
        cycle_substrate_context=context,
    )

    assert result.status == "candidate_unbound"
    assert result.lever_id == "riparian_buffer_width"
    assert result.reason_code == "knob_operator_unresolved"
    assert result.context_binding_hash == context.context_binding_hash


def test_candidate_resolver_requires_context_bound_l6_owner() -> None:
    """A loose valid bundle cannot fabricate a pack-side refusal."""

    bundle = _intervention_bundle()
    context = _cycle_context(
        domain="water_quality",
        lever_id="riparian_buffer_width",
        instrument="water.riparian_buffer_width",
        target_concept="water.nutrient_load",
        transport_covariate="watershed_slope",
    )

    with pytest.raises(InterventionSubstrateError) as error:
        resolve_intervention_lever(
            bundle,
            operator_kind="water.riparian_buffer_width",
            parameter_value=3.0,
            cycle_substrate_context=context,
        )

    assert error.value.code == "cycle_substrate_l6_bundle_missing"


def test_cycle_substrate_context_rejects_content_hash_tamper() -> None:
    payload = _cycle_context().model_dump(mode="python")
    payload["content_hash"] = _hash("tampered-context")

    with pytest.raises(ValueError, match="cycle_substrate_content_hash_mismatch"):
        CycleSubstrateContext.model_validate(payload)
