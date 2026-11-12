"""Real owner replay for candidate-source basis values, never source authority.

The catalog, WDI response, measurement registry and SCM coefficient are controlled
test inputs. Their owner replay establishes software computation only; it does
not turn modeled unemployment into an observation or a publishable claim.
"""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

import aiohttp
import pytest

from polisyos.core.artifacts import ArtifactWriteOptions, FileSystemCAS, ProducerInfo
from polisyos.core.contracts.foundry import StateSnapshotRef
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.foundry.data_plane import load_input_bindings
from polisyos.foundry.execute import state_snapshot_value_projection
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.acquisition_evaluation import (
    _foundry_binding_numerical_values,
    _ordinary_numerical_binding_rules,
)
from polisyos.runtime.quality.acquisition_executor import (
    LiveCatalogExecutionConstraints,
    execute_live_catalog_acquisition,
)
from polisyos.runtime.quality.candidate_acquisition_source import (
    persist_candidate_acquisition_source,
)
from polisyos.runtime.quality.candidate_simulation import (
    CandidateScenarioN5Config,
    CandidateScenarioSetToRule,
    CandidateSimulationContextInputs,
    CandidateSimulationScenarioProfile,
    CandidateSimulationSyntheticModelDeclarationV1,
    candidate_simulation_profile_ref,
)
from polisyos.runtime.quality.candidate_source_basis import (
    CandidateSourceBasisInputs,
    _same_view,
    _selected_n5_world_model_matches_exact_n4_context,
    prepare_candidate_source_basis_values,
    prepare_candidate_source_numerical_basis_values_v2,
)
from polisyos.runtime.quality.data_state_substrate import build_candidate_acquisition_world
from polisyos.runtime.quality.joint_simulation_horizon import HorizonSpec
from polisyos.runtime.quality.n5_execution_basis import exact_n5_content_bytes
from polisyos.runtime.quality.world_model_record import (
    build_world_model_record,
    read_world_model_record_owner_values,
    world_model_artifact_views,
)
from tests._helpers.lane01_wdi_profiles import UNEMPLOYMENT_PROFILE, fixture_wdi_response
from tests.unit.runtime.quality.test_candidate_acquisition_world import (
    CELL_ID,
    TENANT_ID,
    TRANSACTION_TIME,
    _candidate_world_case,
)

if TYPE_CHECKING:
    from typing import Any

    from polisyos.core.artifacts import ArtifactRef
    from tests.unit.runtime.quality.test_candidate_acquisition_world import _CandidateWorldCase


def _case_with_explicit_empty_prior(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    candidate_case: _CandidateWorldCase | None = None,
) -> _CandidateWorldCase:
    """Retain real CAS/native owners, explicitly selecting no consumed SKG edges."""
    case = candidate_case or _candidate_world_case(tmp_path, monkeypatch)
    base = case.base.record
    views = world_model_artifact_views(base)
    owner = read_world_model_record_owner_values(
        case.store,
        world_model_record=base,
        registry_bundle_ref=views.registry_bundle_ref,
        substrate_registry=case.substrate_registry,
    )
    empty_prior = base.skg_causal_prior_ref.model_copy(
        update={"edge_prior_refs": (), "transport_score_refs": (), "query_trace_refs": ()}
    )
    rebuilt = build_world_model_record(
        case.store,
        fabric_world_ref=base.fabric_world_ref,
        data_forge_snapshot_binding_path=base.data_forge_binding_ref.binding_path,
        data_snapshot_ref=views.data_snapshot_ref,
        model_spec=owner.model_spec,
        skg_causal_prior_ref=empty_prior,
        substrate_registry=case.substrate_registry,
        substrate_registry_artifact_ref=case.substrate_registry_ref,
        registry_bundle_artifact_ref=views.registry_bundle_ref,
        region_or_jurisdiction=base.region_or_jurisdiction,
        population_scope=base.population_scope,
        policy_domain=base.policy_domain,
        valid_time_scope=base.valid_time_scope,
        tx_time_scope=base.tx_time_scope,
        resolution=base.resolution,
        branch_mode=base.branch_mode,
        policy_slot_ids=tuple(item.slot_id for item in base.policy_slot_map),
        producer_ref="test_candidate_source_basis.explicit_no_consumed_skg_edges",
        foundry_binding_rules=list(load_input_bindings(case.store, views.input_bindings_ref).rules),
        limitations=base.limitations,
        candidate_only=True,
        return_selected_profile=True,
    )
    return replace(case, base=rebuilt)


def _inputs(case: _CandidateWorldCase, *, coefficient: float = 0.5) -> CandidateSourceBasisInputs:
    base = case.base.record
    outcome_variable = case.problem.outcome_of_interest.target_variable
    inputs = CandidateSimulationContextInputs(
        substrate_registry=case.substrate_registry,
        selected_registry_entry_hashes=tuple(
            item.entry_content_hash for item in case.substrate_registry.entries
        ),
        world_model_record=base,
    )
    rule = CandidateScenarioSetToRule(
        operator_kind="set_to",
        parameter_id="research_budget",
        target_world_slot="government.balance",
        unit_id=base.slot_binding("government.balance").unit,
        minimum=0,
        maximum=1,
    )
    n5 = CandidateScenarioN5Config(
        budget_ref="budget://candidate-source-basis/controlled",
        horizon=HorizonSpec(start=0, end=0),
        baseline_state={
            "government.balance": 0.0,
            outcome_variable: 0.0,
            "global.tax_rate": 0.0,
        },
        seed=11,
        replications=2,
    )
    profile_fields = {
        "schema_version": "policyos.runtime.candidate_simulation_profile.v2",
        "profile_id": "candidate-source-basis.controlled-model",
        "purpose": "synthetic_candidate_scenario",
        "profile_selection_ref": case.binding.profile_selection_ref,
        "context_inputs": inputs.model_dump(mode="json"),
        "rule": rule.model_dump(mode="json"),
        "n5": n5.model_dump(mode="json"),
        "limitations": (
            "scenario_only",
            "real_profile_not_established",
            "real_time_not_established",
            "grounding_not_established",
            "s8_blocked",
            "n9_not_admitted",
        ),
    }
    profile = CandidateSimulationScenarioProfile.model_validate(
        {**profile_fields, "content_hash": gy_content_hash(profile_fields)}
    )
    declaration_fields = {
        "schema_version": "policyos.runtime.candidate_simulation.synthetic_model_declaration.v1",
        "profile_config_ref": candidate_simulation_profile_ref(profile),
        "profile_content_hash": profile.content_hash,
        "profile_selection_ref": profile.profile_selection_ref,
        "target_world_slot": rule.target_world_slot,
        "outcome_variable": outcome_variable,
        "target_unit_id": rule.unit_id,
        "outcome_unit_id": base.slot_binding(outcome_variable).unit,
        "target_baseline": 0.0,
        "outcome_baseline": 0.0,
        "outcome_per_target_unit": coefficient,
        "outcome_noise_stddev": 0.01,
        "assumption": "declared_candidate_scm_not_empirically_grounded",
    }
    declaration = CandidateSimulationSyntheticModelDeclarationV1.model_validate(
        {**declaration_fields, "content_hash": gy_content_hash(declaration_fields)}
    )
    return CandidateSourceBasisInputs(
        configured_profile=profile,
        original_model_declaration=declaration,
        base_data_snapshot_ref=world_model_artifact_views(base).data_snapshot_ref,
        candidate_source_ref=case.source_case.source_ref,
        slot_binding=case.binding,
        transaction_time=TRANSACTION_TIME,
    )


def _files(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_selected_n5_world_model_is_bound_to_exact_n4_context_not_template() -> None:
    """Accept the selected acquired world and reject any broken N4/context/N5 join."""
    selected_world = "sha256:" + "a" * 64
    declared_template_world = "sha256:" + "b" * 64
    exact_binding = {
        "selected_world_model_hash": selected_world,
        "n4_source_world_model_hash": selected_world,
        "context_world_model_hash": selected_world,
        "context_world_model_record_hash": selected_world,
        "n5_input_world_model_hash": selected_world,
        "n5_execution_world_model_hash": selected_world,
    }

    assert declared_template_world != selected_world
    assert _selected_n5_world_model_matches_exact_n4_context(**exact_binding)

    for mismatched_field in (
        "selected_world_model_hash",
        "n4_source_world_model_hash",
        "context_world_model_hash",
        "context_world_model_record_hash",
        "n5_input_world_model_hash",
        "n5_execution_world_model_hash",
    ):
        mismatch = dict(exact_binding)
        mismatch[mismatched_field] = declared_template_world
        assert not _selected_n5_world_model_matches_exact_n4_context(**mismatch)


def test_live_source_basis_observer_preserves_return_and_exception_identity() -> None:
    """Diagnostic observation is bounded and cannot replace the preparer's result."""
    from types import SimpleNamespace

    from tests._helpers.candidate_experiment_served_execution import (
        _observe_candidate_experiment_source_basis_preparation,
    )

    observations = []
    prepared = SimpleNamespace(
        predicate_provenance="recomputed",
        reason_codes=tuple(f"reason-{index}-" + "x" * 300 for index in range(10)),
        inputs=object(),
    )
    intent_ref = object()
    intent = object()
    result = (prepared, intent_ref, intent)
    observed = _observe_candidate_experiment_source_basis_preparation(lambda: result, observations)

    assert observed() is result
    assert len(observations) == 1
    assert observations[0].predicate_provenance == "recomputed"
    assert len(observations[0].reason_codes) == 8
    assert all(len(reason) == 256 for reason in observations[0].reason_codes)
    assert observations[0].inputs_present
    assert observations[0].intent_ref_present
    assert observations[0].intent_present

    original_error = RuntimeError("source basis preparer failed")
    failing = _observe_candidate_experiment_source_basis_preparation(
        lambda: (_ for _ in ()).throw(original_error), observations
    )
    with pytest.raises(RuntimeError) as raised:
        failing()
    assert raised.value is original_error
    assert len(observations) == 1


def _another_real_source(
    case: _CandidateWorldCase,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    body: bytes | None = None,
) -> ArtifactRef:
    """Repeat the genuine producer against the same catalog with controlled HTTP bytes."""
    if body is not None:

        class Response:
            status = 200
            headers: ClassVar[dict[str, str]] = {"content-type": "application/json"}

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args: object) -> None:
                del args

            async def read(self) -> bytes:
                return body

            def release(self) -> None:
                pass

            async def wait_for_close(self) -> None:
                pass

            def close(self) -> None:
                pass

        async def intercept(_session: object, method: str, url: object, **kwargs: object):
            assert method == "GET"
            assert str(url).endswith("/country/USA/indicator/SL.UEM.TOTL.ZS")
            assert kwargs["params"]["date"] == "2024:2024"
            return Response()

        monkeypatch.setattr(aiohttp.ClientSession, "_request", intercept)
    evidence = execute_live_catalog_acquisition(
        authority=case.source_case.authority,
        entry_id=case.source_case.entry.entry_id,
        attempt_id="lane01-fixture-wdi-001",
        constraints=LiveCatalogExecutionConstraints(
            country_code="USA",
            start_year=2024,
            end_year=2024,
            page_size=1000,
            max_response_bytes=65_536,
            max_decompressed_bytes=65_536,
            timeout_cap_seconds=15.0,
            heartbeat_cap_seconds=5.0,
        ),
        journal_path=tmp_path / "second-journal.jsonl",
        cas_root=case.store.root,
        artifact_store=case.store,
    )
    return persist_candidate_acquisition_source(
        case.store,
        authority=case.source_case.authority,
        entry_id=case.source_case.entry.entry_id,
        live_source_execution=evidence,
        requirement_basis_binding=case.source_case.binding,
        requirement_id=case.source_case.requirement_id,
        candidate_digest=case.source_case.candidate_digest,
        target_slot_id="global.unemployment_rate",
        country_code="USA",
        year=2024,
        population="total_labor_force",
        tenant_id=TENANT_ID,
        cell_id=CELL_ID,
        run_id=case.source_case.source.run_id,
        job_id="second-controlled-source-job",
        route_id=case.source_case.source.route_id,
    )


def test_selected_view_identity_accepts_ref_subtype_but_rejects_sibling_profile(
    tmp_path: Path,
) -> None:
    """The selected manifest is load-bearing; its Python reference subclass is not."""
    store = FileSystemCAS(tmp_path / "identity-cas")
    payload = {"controlled_state": "same bytes"}

    def put(producer: str) -> ArtifactRef:
        return store.put_json(
            payload,
            ArtifactWriteOptions(
                kind="foundry.state_snapshot",
                media_type="application/json",
                producer=ProducerInfo(component=producer, version="1"),
            ),
            return_selected_profile=True,
        )

    selected = put("test.selected-state-owner")
    sibling = put("test.foreign-state-owner")
    assert selected.artifact_id == sibling.artifact_id
    assert selected.manifest_profile_sha256 != sibling.manifest_profile_sha256
    typed = StateSnapshotRef.model_validate(selected.model_dump(mode="python"))
    assert _same_view(store, typed, selected)
    assert not _same_view(store, typed, sibling)


def test_candidate_source_basis_replays_actual_float32_world_without_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Historical exact refs need no worker lease and agree with the real producer."""
    from polisyos.fabric.connectors.cache.store import ConnectorCacheStore

    setup_caches: list[ConnectorCacheStore] = []

    def capture_cache(*args: Any, **kwargs: Any) -> ConnectorCacheStore:
        cache = ConnectorCacheStore(*args, **kwargs)
        setup_caches.append(cache)
        return cache

    monkeypatch.setattr("polisyos.fabric.ingestion.ingestion.ConnectorCacheStore", capture_cache)
    with tenant_scope(None, tenant_id=TENANT_ID, cell_id=CELL_ID):
        case = _case_with_explicit_empty_prior(tmp_path, monkeypatch)
        inputs = _inputs(case)
        built = build_candidate_acquisition_world(
            case.store,
            problem=case.problem,
            base_world_model=case.base.record,
            substrate_registry=case.substrate_registry,
            substrate_registry_artifact_ref=case.substrate_registry_ref,
            materialization=case.materialization,
            workspace_dir=tmp_path / "actual-world",
            transaction_time=TRANSACTION_TIME,
            authority=case.source_case.authority,
        )
        # Finish the actual acquisition cache's WAL lifetime before measuring
        # replay: final connection cleanup may checkpoint/delete sidecar files.
        assert setup_caches
        for cache in setup_caches:
            cache.close()
            assert cache.closed
        before = _files(tmp_path)
        fresh = FileSystemCAS(case.store.root)
        prospective = prepare_candidate_source_basis_values(
            store=fresh, problem=case.problem, inputs=inputs
        )
        actual = prepare_candidate_source_basis_values(
            store=fresh,
            problem=case.problem,
            inputs=inputs,
            data_snapshot_ref=case.materialization.data_snapshot_ref,
            world_model_ref=built.world_model.record_ref,
        )
        assert prospective.reason_codes == actual.reason_codes == ()
        assert prospective.predicate_provenance == actual.predicate_provenance == "recomputed"
        assert exact_n5_content_bytes(prospective.effective_values) == exact_n5_content_bytes(
            actual.effective_values
        )
        numerical = prepare_candidate_source_numerical_basis_values_v2(
            store=fresh,
            problem=case.problem,
            inputs=inputs,
            data_snapshot_ref=case.materialization.data_snapshot_ref,
            world_model_ref=built.world_model.record_ref,
        )
        assert numerical.reason_codes == ()
        assert set(numerical.effective_values) == {
            "foundry_state",
            "applied_rules",
            "selected_native_ncm",
            "declared_model",
            "n5_request_values",
        }
        request = numerical.effective_values["n5_request_values"]
        assert "budget_ref" not in request.model_fields_set
        assert request.replications == actual.prospective_model.n5_config.replications
        assert _files(tmp_path) == before
        float32_rate = struct.unpack("!f", struct.pack("!f", 0.175))[0]
        assert (
            actual.prospective_model.n5_config.baseline_state["global.unemployment_rate"]
            == float32_rate
        )
        assert actual.prospective_model.declared_model_values.outcome_baseline == float32_rate
        assert actual.prospective_values.materialized_state.market.unemployment_rate == float32_rate
        source = actual.effective_values["candidate_source"]
        assert source["source"]["observation"] == 0.175
        assert source["source"]["quantity_kind"] == "share_of_denominator"
        assert (
            source["source"]["population"] == source["source"]["denominator"] == "total_labor_force"
        )
        assert source["scientific_authority"]["independence"] == "not_established"
        assert source["scientific_authority"]["publication_authority"] is False
        blockers = actual.effective_values["world"]["inherited_world"]["limitations"][
            "admissibility_blockers"
        ]
        assert {
            "candidate_source_not_an_observation",
            "publication_authority_not_established",
            "measurement_validity_not_established",
        }.issubset(blockers)
        retained = [
            item
            for item in actual.effective_values["applied_rules"]
            if item["binding_id"].startswith("base.")
        ]
        original = load_input_bindings(
            fresh, world_model_artifact_views(case.base.record).input_bindings_ref
        )
        assert retained == [item.model_dump(mode="json") for item in original.rules]


def test_v2_numerical_rules_separate_provenance_from_consumed_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Producer rules separate provenance notes while value and transforms remain decisive."""
    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.core.contracts.fabric import DataSnapshot
    from polisyos.runtime.quality.data_snapshot_lineage import (
        DataSnapshotSourceRowNotEstablishedError,
        validate_data_snapshot_owner_lineage,
    )

    with tenant_scope(None, tenant_id=TENANT_ID, cell_id=CELL_ID):
        results = []
        variants = (
            ("modeled", UNEMPLOYMENT_PROFILE.fixture_value),
            ("changed-value", UNEMPLOYMENT_PROFILE.fixture_value + 0.05),
        )
        for label, value in variants:
            profile = replace(UNEMPLOYMENT_PROFILE, fixture_value=value)
            root = tmp_path / label
            case = _case_with_explicit_empty_prior(
                root,
                monkeypatch,
                candidate_case=_candidate_world_case(root, monkeypatch, source_profile=profile),
            )
            inputs = _inputs(case)
            legacy = prepare_candidate_source_basis_values(
                store=case.store, problem=case.problem, inputs=inputs
            )
            numerical = prepare_candidate_source_numerical_basis_values_v2(
                store=case.store, problem=case.problem, inputs=inputs
            )
            assert legacy.predicate_provenance == numerical.predicate_provenance == "recomputed"
            assert not legacy.reason_codes and not numerical.reason_codes
            assert (
                legacy.effective_values["candidate_source"]["scientific_authority"][
                    "observation_class"
                ]
                == "model_output"
            )
            assert (
                legacy.effective_values["candidate_source"]["scientific_authority"][
                    "publication_authority"
                ]
                is False
            )
            snapshot = DataSnapshot.model_validate(
                load_core_json_artifact(case.store, case.materialization.data_snapshot_ref)
            )
            lineage = validate_data_snapshot_owner_lineage(
                case.store, case.materialization.data_snapshot_ref, snapshot, candidate_only=True
            )
            with pytest.raises(DataSnapshotSourceRowNotEstablishedError):
                validate_data_snapshot_owner_lineage(
                    case.store, case.materialization.data_snapshot_ref, snapshot
                )
            results.append((inputs, legacy, numerical, lineage))

        first, changed_value = results
        assert "candidate_source_not_an_observation" in first[3].required_admissibility_blockers
        assert (
            first[2].effective_values["foundry_state"]
            != (changed_value[2].effective_values["foundry_state"])
        )
        assert exact_n5_content_bytes(first[2].effective_values) != exact_n5_content_bytes(
            changed_value[2].effective_values
        )
        rules = first[1].effective_values["applied_rules"]
        target = first[0].slot_binding.target_slot_id
        hypothetical = tuple(
            {
                **rule,
                "notes": [
                    "source_provenance:observed"
                    if note == "source_provenance:model_output"
                    else note
                    for note in rule["notes"]
                ]
                + ["candidate_source_ref:other-occurrence", "evidence:review-required"],
            }
            if rule["target_slot_id"] == target
            else {**rule, "notes": [*rule["notes"], "retained:evidence-only"]}
            for rule in rules
        )
        assert hypothetical != rules  # V1 preserves this difference as evidence.
        assert (
            tuple(_foundry_binding_numerical_values(rule) for rule in hypothetical)
            == (first[2].effective_values["applied_rules"])
        )
        from polisyos.core.contracts import FoundryInputBindingRule

        def ordinary(values: object) -> tuple[dict[str, object], ...]:
            assert isinstance(values, tuple)
            return _ordinary_numerical_binding_rules(
                [FoundryInputBindingRule.model_validate(rule) for rule in values],
                owned_target_slot=target,
            )

        assert ordinary(rules) == ordinary(hypothetical)
        assert {next(iter(rule)) for rule in ordinary(rules)} == {
            "acquired_owner_values",
            "retained_rule",
        }
        with pytest.raises(ValueError, match="acquisition_numerical_rule_census_not_established"):
            _foundry_binding_numerical_values({**rules[0], "new_unknown_field": 1})
        for field, value in (
            ("transforms", [{"op": "scale", "params": {"factor": 2.0}}]),
            ("source_path", "different.input.value"),
            ("target_slot_id", "different.target"),
            ("binding_id", "different.binding"),
            ("default_value", 123.0),
            ("required", False),
        ):
            changed = tuple(
                {**rule, field: value} if rule["target_slot_id"] == target else rule
                for rule in rules
            )
            assert exact_n5_content_bytes(
                tuple(_foundry_binding_numerical_values(rule) for rule in changed)
            ) != (exact_n5_content_bytes(first[2].effective_values["applied_rules"]))
            assert ordinary(changed) != ordinary(rules)


def test_candidate_source_basis_distinguishes_model_coefficient_from_fixed_n5_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with tenant_scope(None, tenant_id=TENANT_ID, cell_id=CELL_ID):
        case = _case_with_explicit_empty_prior(tmp_path, monkeypatch)
        a = prepare_candidate_source_basis_values(
            store=case.store, problem=case.problem, inputs=_inputs(case, coefficient=0.5)
        )
        b = prepare_candidate_source_basis_values(
            store=case.store, problem=case.problem, inputs=_inputs(case, coefficient=0.75)
        )
        assert a.reason_codes == b.reason_codes == ()
        assert a.inputs.candidate_source_ref == b.inputs.candidate_source_ref
        assert a.inputs.slot_binding == b.inputs.slot_binding
        assert a.effective_values["n5_request_values"] == b.effective_values["n5_request_values"]
        assert a.effective_values["foundry_state"] == b.effective_values["foundry_state"]
        assert a.effective_values["declared_model"]["outcome_per_target_unit"] == 0.5
        assert b.effective_values["declared_model"]["outcome_per_target_unit"] == 0.75
        assert (
            a.effective_values["selected_native_ncm"] != b.effective_values["selected_native_ncm"]
        )
        assert exact_n5_content_bytes(a.effective_values) != exact_n5_content_bytes(
            b.effective_values
        )


def test_candidate_source_basis_normalizes_only_verified_execution_occurrence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with tenant_scope(None, tenant_id=TENANT_ID, cell_id=CELL_ID):
        case = _case_with_explicit_empty_prior(tmp_path, monkeypatch)
        first = _inputs(case)
        second_ref = _another_real_source(case, tmp_path, monkeypatch)
        second = first.model_copy(update={"candidate_source_ref": second_ref})
        assert first.candidate_source_ref != second.candidate_source_ref
        a = prepare_candidate_source_basis_values(
            store=case.store, problem=case.problem, inputs=first
        )
        b = prepare_candidate_source_basis_values(
            store=case.store, problem=case.problem, inputs=second
        )
        assert a.reason_codes == b.reason_codes == ()
        assert exact_n5_content_bytes(a.effective_values) == exact_n5_content_bytes(
            b.effective_values
        )


def test_candidate_source_basis_preserves_scientific_scope_time_sample_and_independence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with tenant_scope(None, tenant_id=TENANT_ID, cell_id=CELL_ID):
        case = _case_with_explicit_empty_prior(tmp_path, monkeypatch)
        initial = _inputs(case)
        response = json.loads(fixture_wdi_response(UNEMPLOYMENT_PROFILE))
        scientific_scope = {
            "population": "declared_working_age_subpopulation",
            "denominator": "declared_subpopulation_labor_force",
            "sample_size": 317,
            "independence_group": "shared-modeled-input-panel",
            "replication_id": "replica-2",
            "reference_period": "2024-07-01/2024-12-31",
        }
        response[1][0]["scientific_scope"] = scientific_scope
        changed_ref = _another_real_source(
            case,
            tmp_path,
            monkeypatch,
            body=json.dumps(response, sort_keys=True, separators=(",", ":")).encode(),
        )
        changed = initial.model_copy(update={"candidate_source_ref": changed_ref})
        a = prepare_candidate_source_basis_values(
            store=case.store, problem=case.problem, inputs=initial
        )
        b = prepare_candidate_source_basis_values(
            store=case.store, problem=case.problem, inputs=changed
        )
        assert a.reason_codes == b.reason_codes == ()
        assert state_snapshot_value_projection(
            a.prospective_values.materialized_state
        ) == state_snapshot_value_projection(b.prospective_values.materialized_state)
        assert (
            a.effective_values["selected_native_ncm"] == b.effective_values["selected_native_ncm"]
        )
        assert (
            b.effective_values["candidate_source"]["raw_wdi_values"][1][0]["scientific_scope"]
            == scientific_scope
        )
        assert exact_n5_content_bytes(a.effective_values) != exact_n5_content_bytes(
            b.effective_values
        )


def test_candidate_source_basis_unknown_consumed_skg_values_are_not_established(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with tenant_scope(None, tenant_id=TENANT_ID, cell_id=CELL_ID):
        case = _candidate_world_case(tmp_path, monkeypatch)
        before = _files(tmp_path)
        result = prepare_candidate_source_basis_values(
            store=case.store, problem=case.problem, inputs=_inputs(case)
        )
        assert result.predicate_provenance == "not_established"
        assert result.reason_codes == ("acquisition_world_skg_consumed_values_not_established",)
        assert _files(tmp_path) == before


def test_candidate_source_basis_same_scalar_cannot_cross_declared_country_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with tenant_scope(None, tenant_id=TENANT_ID, cell_id=CELL_ID):
        case = _case_with_explicit_empty_prior(tmp_path, monkeypatch)
        problem = case.problem.model_copy(
            update={
                "jurisdiction_time": case.problem.jurisdiction_time.model_copy(
                    update={"region": "CAN"}
                )
            }
        )
        result = prepare_candidate_source_basis_values(
            store=case.store, problem=problem, inputs=_inputs(case)
        )
        assert result.predicate_provenance == "not_established"
        assert result.reason_codes == ("candidate_source_world_scope_mismatch",)


@pytest.mark.parametrize(
    ("context_state", "expected_initial_replays"),
    [
        ("direct", 1),
        ("reused", 0),
        ("foreign_scope", 0),
        ("same_bytes_wrong_profile", 0),
        ("changed_head", 0),
        ("changed_admission", 0),
        ("changed_final_owner", 0),
    ],
)
def test_live_source_basis_reuses_exact_context_and_keeps_final_fence(
    monkeypatch: pytest.MonkeyPatch,
    context_state: str,
    expected_initial_replays: int,
) -> None:
    """Reuse the fresh owner once, reject foreign/stale bindings, and keep final replay."""
    from datetime import UTC, datetime, timedelta
    from types import SimpleNamespace

    import polisyos.runtime.quality.candidate_acquisition_source as source_module
    from polisyos.runtime.http.services.control_plane_store import (
        ControlJobExecutionAdmission,
        ControlJobExecutionScope,
        ControlJobRecord,
    )
    from polisyos.runtime.quality import candidate_acquisition_action as action_module
    from polisyos.runtime.quality import candidate_source_basis as basis_module
    from polisyos.runtime.quality import world_model_record as world_model_record_module
    from polisyos.runtime.quality.acquisition_world_growth import (
        AcquisitionWorldGrowthBridge,
    )
    from polisyos.runtime.quality.candidate_acquisition_action import (
        _VerifiedCurrentCandidateExperimentReentryAction,
    )
    from polisyos.runtime.quality.candidate_source_basis import CandidateSourceBasisValues
    from tests.unit.runtime.quality.test_candidate_experiment_current_outcome import (
        _hash,
        _ref,
        _selection_case,
    )
    from tests.unit.runtime.quality.test_candidate_experiment_dispatch_currentness import (
        _reentry_receipts,
    )

    origin, outcomes = _selection_case(1)
    pending = outcomes[-1].latest_receipt
    phase_template, action, _action_phase_ref = _reentry_receipts()
    action = action.model_copy(update={"action_job_id": pending.job_id})
    phase = pending.model_copy(
        update={
            "candidate_receipt_ref": phase_template.candidate_receipt_ref,
            "owner_receipt_refs": (str(phase_template.candidate_receipt_ref.artifact_id),),
        }
    )
    selection = action.selection
    canonical_head = outcomes[-1].head
    context_head = canonical_head
    context_phase = phase
    if context_state == "foreign_scope":
        context_head = replace(canonical_head, tenant_id="foreign-tenant")
        context_phase = phase.model_copy(update={"tenant_id": "foreign-tenant"})
    elif context_state == "same_bytes_wrong_profile":
        context_head = replace(canonical_head, receipt_manifest_profile_sha256=_hash("e"))
    context_outcome = replace(
        outcomes[-1],
        head=context_head,
        latest_receipt=context_phase,
        phase_chain=(replace(outcomes[-1].phase_chain[-1], receipt=context_phase),),
    )

    now = datetime(2026, 11, 8, tzinfo=UTC)
    job = ControlJobRecord(
        job_id=phase.job_id,
        kind="acquisition",
        state="running",
        run_id=origin.run_id,
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=origin.capability_manifest_ref,
        payload_ref=origin.source_payload_ref,
        submitted_by="candidate-source-basis-unit",
        created_at=now,
        started_at=now,
        finished_at=None,
        lease_owner="candidate-source-basis-worker",
        lease_expires_at=now + timedelta(minutes=2),
        attempt=1,
        error_message=None,
        progress={},
    )
    scope = ControlJobExecutionScope(
        status="established",
        tenant_id=origin.tenant_id,
        cell_id=origin.cell_id,
        actor_subject="candidate-source-basis-unit",
        actor_authenticated=True,
        actor_roles=("operator",),
    )
    context_admission = ControlJobExecutionAdmission(
        job=job,
        scope=scope,
        admission_capability_manifest_ref=job.capability_manifest_ref,
        attempt=1,
        manifest_pointer_state="admission_current",
    )
    current_admission = context_admission
    if context_state == "changed_admission":
        current_job = replace(job, attempt=2)
        current_admission = ControlJobExecutionAdmission(
            job=current_job,
            scope=scope,
            admission_capability_manifest_ref=current_job.capability_manifest_ref,
            attempt=2,
            manifest_pointer_state="admission_current",
        )
    current_head = canonical_head
    if context_state == "changed_head":
        current_head = replace(canonical_head, receipt_ref=_hash("0"), receipt_sha256=_hash("0"))
    control_store = SimpleNamespace(
        get_acquisition_action_head=lambda **_kwargs: current_head,
        current_execution_job_admission=lambda: current_admission,
    )
    bridge = object.__new__(AcquisitionWorldGrowthBridge)
    bridge.artifact_store = object()
    bridge.authority = object()
    bridge.control_store = control_store
    context = _VerifiedCurrentCandidateExperimentReentryAction(
        selection=selection,
        phase=context_phase,
        admission=context_admission,
        action=action,
        head=context_head,
        outcome=context_outcome,
        budget_window=object(),
    )
    profile = SimpleNamespace(context_inputs=SimpleNamespace(world_model_record=object()))
    prior_owner = SimpleNamespace(
        profile=profile,
        model_declaration=object(),
        selected_evaluation=None,
        generation_run=origin.generation_run,
        source_cycle=origin.source_cycle,
        first_n4_source=None,
    )
    intent = SimpleNamespace(action_phase_ref=action.action_phase_ref, transaction_time=now)
    intent_ref = action.candidate_source_ref
    monkeypatch.setattr(bridge, "_candidate_experiment_prior_owner", lambda **_kwargs: prior_owner)
    monkeypatch.setattr(
        bridge,
        "_candidate_world_materialization_intent",
        lambda **_kwargs: (intent_ref, intent),
    )
    monkeypatch.setattr(
        action_module, "_candidate_experiment_source_selection", lambda *_args: selection
    )
    monkeypatch.setattr(
        action_module,
        "read_candidate_experiment_acquisition_action",
        lambda **_kwargs: action,
    )
    initial_replays: list[object] = []
    monkeypatch.setattr(
        action_module,
        "_current_candidate_experiment_reentry_action_context",
        lambda *_args: initial_replays.append(context) or context,
    )
    final_replays: list[object] = []
    monkeypatch.setattr(
        action_module,
        "_current_candidate_experiment_reentry_action",
        lambda *_args: final_replays.append(context)
        or (
            selection,
            context.phase,
            context.admission,
            action.model_copy(update={"decision_ref": _hash("d")})
            if context_state == "changed_final_owner"
            else action,
        ),
    )
    monkeypatch.setattr(
        source_module,
        "read_candidate_acquisition_source",
        lambda *_args, **_kwargs: SimpleNamespace(
            tenant_id=origin.tenant_id,
            cell_id=origin.cell_id,
            run_id=origin.run_id,
            job_id=action.action_job_id,
            route_id=origin.route_id,
            candidate_digest=selection.candidate_digest,
        ),
    )
    predecessor_reads: list[object] = []
    monkeypatch.setattr(
        basis_module,
        "_candidate_source_predecessors_for_verified_experiment_origin",
        lambda **_kwargs: predecessor_reads.append(None) or (),
    )
    monkeypatch.setattr(
        world_model_record_module,
        "world_model_artifact_views",
        lambda _record: SimpleNamespace(data_snapshot_ref=_ref("fabric.data_snapshot", "9")),
    )
    monkeypatch.setattr(
        basis_module,
        "CandidateAcquisitionSourceSlotBinding",
        lambda **kwargs: SimpleNamespace(**kwargs),
    )
    monkeypatch.setattr(
        basis_module, "CandidateSourceBasisInputs", lambda **kwargs: SimpleNamespace(**kwargs)
    )
    prepared_inputs: list[object] = []

    def prepare_values(**kwargs: object) -> CandidateSourceBasisValues:
        prepared_inputs.append(kwargs["inputs"])
        return CandidateSourceBasisValues("recomputed", (), inputs=kwargs["inputs"])

    monkeypatch.setattr(basis_module, "prepare_candidate_source_basis_values", prepare_values)
    initial_context = None if context_state == "direct" else context
    result, _result_ref, result_intent = (
        basis_module.prepare_live_candidate_experiment_source_basis_values(
            bridge=bridge,
            origin=origin,
            candidate_action_ref=phase.candidate_receipt_ref,
            pending_phase_ref=canonical_head.receipt_ref,
            initial_reentry_context=initial_context,
        )
    )

    if context_state in {
        "foreign_scope",
        "same_bytes_wrong_profile",
        "changed_head",
        "changed_admission",
    }:
        assert result.predicate_provenance == "not_established"
        assert (
            "candidate_experiment_source_basis_reentry_context_not_current" in result.reason_codes
        )
        assert prepared_inputs == []
        assert final_replays == []
        return

    if context_state == "changed_final_owner":
        assert result.predicate_provenance == "not_established"
        assert result.reason_codes == ("candidate_experiment_source_basis_owner_changed",)
        assert prepared_inputs
        assert len(final_replays) == 1
        return

    assert result.predicate_provenance == "recomputed"
    assert result_intent == intent
    assert prepared_inputs
    assert len(initial_replays) == expected_initial_replays
    assert len(final_replays) == 1
    assert len(predecessor_reads) == 2


def test_v2_blocker_carries_verified_source_without_a_physical_predecessor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A V2 blocker preserves its verified prior source but creates no source edge."""
    from polisyos.runtime.quality import candidate_source_basis as basis_module
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentTerminalReceiptV2,
        _candidate_experiment_effective_source,
    )
    from tests.unit.runtime.quality.test_acquisition_route_loop import (
        _reuse_effective_source_case,
    )

    origin, generation_run, source_cycle, history, _frontier = _reuse_effective_source_case(
        "candidate_blocked"
    )
    assert type(history.terminal) is AcquisitionCandidateExperimentTerminalReceiptV2
    assert history.terminal.terminal_outcome == "candidate_blocked"
    effective_run, effective_cycle = _candidate_experiment_effective_source(origin)
    assert effective_run is generation_run
    assert effective_cycle is source_cycle

    captured: list[tuple[object, ...]] = []

    def capture_transitions(**kwargs: object) -> tuple[()]:
        captured.append(kwargs["transitions"])
        return ()

    monkeypatch.setattr(
        basis_module,
        "_candidate_source_predecessors_from_selected_transitions",
        capture_transitions,
    )

    predecessors = basis_module._candidate_source_predecessors_for_verified_experiment_origin(
        store=object(), origin=origin
    )

    assert predecessors == ()
    assert captured == [()]
