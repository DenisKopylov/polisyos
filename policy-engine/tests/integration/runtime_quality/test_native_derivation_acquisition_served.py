"""Serve configured N7 leaves and independently admitted native partial actions.

Controlled transport bytes and signed test institutions exercise actual owners.
The partial route never enters N5 or establishes empirical source truth.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import ArtifactRef, artifact_ref_identity_key
from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
from polisyos.runtime.quality.acquisition_planner import (
    N7DerivationDagBudgetProfile,
    persist_n7_derivation_dag_budget_profile,
)
from polisyos.runtime.quality.acquisition_route_loop import (
    NativeDerivationLeafProviderSelection,
)
from polisyos.runtime.quality.acquisition_world_growth import (
    AcquisitionWorldGrowthConfig,
    NativeDerivationPlanningRoleSupplier,
    NativeDerivationPlanningSelection,
)
from polisyos.runtime.quality.candidate_simulation import CandidateSimulationContextInputs
from polisyos.runtime.quality.cycle_substrate import cycle_job_profile_selection_ref
from polisyos.runtime.quality.design_problem import DesignProblem
from polisyos.runtime.quality.generic_simulation_admission import (
    GenericCycleN5ProgramGraphRequestProfileV4,
    GenericCycleSimulationProfileV1,
)
from polisyos.runtime.quality.joint_simulation_horizon import HorizonSpec
from tests._helpers import world_model_record as world_fixture
from tests._helpers.derived_input_world import build_selected_method_base_world
from tests._helpers.lane01_wdi_profiles import (
    CandidateWDIProfile,
    FixtureWDIRegisteredSourceSemantics,
    FixtureWDIRoleBinding,
    build_fixture_wdi_authority_bundle,
)
from tests._helpers.registered_derived_method_input import (
    prepare_registered_method_input_profile,
)
from tests._helpers.selected_method_input import (
    prepare_selected_method_input_case,
    selected_method_tax_subsidy_policy,
)
from tests.integration.runtime_quality.test_program_graph_model_input_served import (
    _fiscal_problem,
)
from tests.integration.runtime_quality.test_program_graph_stock_n7_served import (
    controlled_candidate_gateway as _gateway_fixture,
)
from tests.integration.runtime_quality.test_program_graph_stock_n7_served import (
    served_blocked_generic_source_case,
)
from tests.unit.runtime.quality.test_generic_simulation_admission_program_graph import (
    _with_hash,
)

controlled_candidate_gateway = _gateway_fixture


def _problem() -> DesignProblem:
    payload = _fiscal_problem().model_dump(mode="json")
    payload["jurisdiction_time"].update(
        region="UKR", valid_time="2024", as_of="2024-12-31", policy_time="2024", data_time="2024"
    )
    payload["nl_provenance"]["raw_request"] = (
        "Evaluate one bounded 2024 tax subsidy and the government balance in USD. "
        "Use the selected registered method inputs. Do not promote generated candidates."
    )
    return DesignProblem.model_validate(payload)


def _selected_policy():
    policy = selected_method_tax_subsidy_policy()
    intervention = policy.interventions[0].model_copy(
        update={
            "notes": ["do.target=agents.income"],
            "measurement_expectations": {
                "sign": "increase",
                "outcome": ["agents.income"],
                "effect_path": ["tax_subsidy", "agents.income", "agents.income"],
                "estimand": "average_treatment_effect",
            },
        }
    )
    return type(policy).model_validate(
        {**policy.model_dump(mode="python"), "interventions": [intervention]}
    )


def _declared_native_fiscal_definitions(store: Any) -> dict[str, Any]:
    """Persist explicit controlled meanings before model/profile compilation."""
    from polisyos.core.artifacts import PutOptions, input_ref_from_artifact_ref
    from polisyos.core.contracts.variable_binding import (
        VariableSemanticDefinition,
        VariableSemanticDefinitionRef,
    )
    from tests.unit.core.contracts.test_semantic_derived_binding import _put_contract, _selected

    def declared(stable_id: str, meaning: str) -> VariableSemanticDefinitionRef:
        evidence = _selected(
            store,
            store.put_bytes(
                (
                    f"Controlled fixture definition: {stable_id}\n{meaning}\n"
                    "Definition data only; no observed value, empirical truth, currentness "
                    "or acquisition right is established."
                ).encode(),
                PutOptions(kind="fixture.semantic_definition", media_type="text/plain"),
                return_selected_profile=True,
            ),
        )
        value = VariableSemanticDefinition(
            namespace="fixture.native_fiscal",
            stable_id=stable_id,
            revision="1",
            meaning=meaning,
            definition_evidence_refs=(evidence,),
        )
        return VariableSemanticDefinitionRef.model_validate(
            _put_contract(
                store,
                value,
                inputs=(input_ref_from_artifact_ref(evidence, role="definition_evidence"),),
            ).model_dump(mode="python")
        )

    definitions = {
        "fiscal_flow": declared(
            "government_cash_surplus_deficit_period_total",
            "Signed government cash surplus or deficit over the selected calendar year, "
            "as a period flow in current United States dollars. The model accumulates "
            "these period balances from its origin; this does not denote cash assets "
            "or establish empirical financing effects.",
        ),
        "gdp": declared(
            "gross_domestic_product_current_usd_period_total",
            "Gross domestic product produced within the selected jurisdiction over a "
            "calendar year, valued at current market prices in United States dollars "
            "for that same year.",
        ),
    }
    definitions["fiscal_share"] = declared(
        "government_cash_surplus_deficit_share_of_gdp",
        "Signed quotient of the government cash surplus/deficit period total "
        f"({definitions['fiscal_flow'].artifact_id}) and gross domestic product period total "
        f"({definitions['gdp'].artifact_id}) for the same jurisdiction and calendar year.",
    )
    return definitions


def _declared_native_fiscal_representations(
    store: Any, definitions: dict[str, Any], money: Any
) -> dict[str, Any]:
    """Keep percentage meaning separate from its canonical ratio coordinate."""
    from tests.unit.core.contracts.test_semantic_derived_binding import _representation

    return {
        "fiscal_share": _representation(
            store,
            definitions["fiscal_share"],
            population="population:government",
            money=money,
            numerator_ref=definitions["fiscal_flow"],
            denominator_ref=definitions["gdp"],
        )[0],
        "gdp": _representation(
            store, definitions["gdp"], population="population:economy", money=money
        )[0],
    }


def _prepare_declared_native_fiscal_case(path: Path, *, store: Any) -> tuple[Any, dict[str, Any]]:
    """Compile the selected fiscal target after declaring all source meanings."""
    from polisyos.ir.kernel import MoneyUnit

    definitions = _declared_native_fiscal_definitions(store)
    money = MoneyUnit(currency="USD", nominal_year=2024, price_base="current")
    representations = _declared_native_fiscal_representations(store, definitions, money)
    case, metadata = prepare_selected_method_input_case(
        path,
        method_class=PeriodFlowToStock,
        mapped=True,
        method_input_slot="ledger.flow",
        snapshot_id=world_fixture.SNAPSHOT_ID,
        policy_spec=_selected_policy(),
        income_values=(2**26, 2**27),
        store=store,
        opening_balance_usd=10_000_000_000,
        money_unit=money,
        model_input_definition_refs={"ledger.flow": definitions["fiscal_flow"]},
    )
    metadata["native_definition_refs"] = definitions
    metadata["native_representation_refs"] = representations
    return case, metadata


def _install_two_role_wdi_declarations(
    *,
    store: Any,
    case: Any,
    metadata: dict[str, Any],
    root: Path,
    catalog_baseline_path: Path | None = None,
) -> tuple[Any, ArtifactRef, tuple[dict[str, Any], ...], dict[str, Any]]:
    """Persist the exact selected profile and two distinct fixture declarations."""
    from polisyos.core.artifacts import artifact_ref_identity_key
    from polisyos.core.contracts.semantic_composition_binding import (
        RegisteredDerivationRoleBasis,
        RegisteredSemanticBasis,
    )
    from polisyos.data_forge.read_api import catalog as catalog_read_api

    definitions = metadata["native_definition_refs"]
    representations = metadata["native_representation_refs"]
    port = metadata["port"]
    if artifact_ref_identity_key(port.semantic_definition_ref) != artifact_ref_identity_key(
        definitions["fiscal_flow"]
    ):
        raise ValueError("native_fixture_fiscal_target_definition_not_compiled")
    source_bases = tuple(
        RegisteredDerivationRoleBasis(
            role=role,
            basis=RegisteredSemanticBasis(
                semantic_definition_ref=definitions[key],
                representation_ref=representations[key],
                binding_profile_ref=port.binding_profile_ref,
            ),
        )
        for role, key in (("rate_input", "fiscal_share"), ("scale_input", "gdp"))
    )
    setup = prepare_registered_method_input_profile(case, metadata, source_bases=source_bases)
    metadata["native_source_bases"] = source_bases
    metadata["native_registered_setup"] = setup
    profiles: list[CandidateWDIProfile] = []
    bindings: dict[str, FixtureWDIRoleBinding] = {}
    denominator_definition_ref = next(
        row.basis.semantic_definition_ref
        for row in setup.profile.inputs
        if row.role == setup.profile.denominator_role
    )
    for spec in setup.source_specs:
        role = next(
            role for role, alias in setup.role_aliases.items() if alias == spec["target_variable"]
        )
        semantic_ref = spec["source_semantic_definition_ref"]
        representation_ref = spec["source_representation_ref"]
        alias = setup.role_aliases[role]
        source_scope = dict(spec["source_measure_scope"])
        if role == setup.profile.ratio_role:
            source_scope.update(
                denominator=str(denominator_definition_ref.artifact_id),
                quantity_kind="share_of_denominator",
            )
            indicator_id = "GC.BAL.CASH.GD.ZS"
            raw_unit = "percent"
            canonical_unit = "ratio"
            transform = "fixed_multiplicative"
            transform_ref = "fabric://units/fixed-multiplicative/v1"
            fixture_value = -3.0
            valid_min, valid_max = -1.0, 1.0
            title = "Controlled cash surplus/deficit (% of GDP)"
            description = (
                "Annual government cash balance as a percent of the same-year GDP "
                "denominator. Controlled synthetic fixture values; empirical source "
                "truth is not established."
            )
        else:
            indicator_id = "NY.GDP.MKTP.CD"
            raw_unit = canonical_unit = "usd"
            transform = "identity"
            transform_ref = "fabric://units/usd-identity/v1"
            fixture_value = 200_000_000_000.0
            valid_min, valid_max = 0.0, 300_000_000_000.0
            title = "Controlled GDP (current US$)"
            description = (
                "Annual gross domestic product in current US dollars for the same "
                "jurisdiction and calendar year. Controlled synthetic fixture values; "
                "empirical source truth is not established."
            )
        profiles.append(
            CandidateWDIProfile(
                construct=f"test.native.{role}",
                indicator_id=indicator_id,
                source_title=title,
                source_description=description,
                target_slot=alias,
                raw_unit=raw_unit,
                canonical_unit=canonical_unit,
                transform=transform,
                transform_ref=transform_ref,
                population=str(spec["source_measure_scope"]["population"]),
                fixture_value=fixture_value,
                source_provenance_class="observed",
                valid_min=valid_min,
                valid_max=valid_max,
                denominator=(
                    str(denominator_definition_ref.artifact_id)
                    if role == setup.profile.ratio_role
                    else None
                ),
                quantity_kind=(
                    "share_of_denominator" if role == setup.profile.ratio_role else "unconstrained"
                ),
                country_code="UKR",
                country_id="UA",
                year=2024,
                catalog_metric_id=f"test.native.{role}",
            )
        )
        bindings[alias] = FixtureWDIRoleBinding(
            attempt_ids=(f"configured-native-{role}",),
            registered_source_semantics=FixtureWDIRegisteredSourceSemantics(
                source_semantic_definition_ref=semantic_ref,
                source_representation_ref=representation_ref,
                source_measure_scope=source_scope,
                country_codes=("UKR",),
            ),
        )
    authority, entries = build_fixture_wdi_authority_bundle(
        root,
        tuple(profiles),
        role_bindings=bindings,
        baseline_path=catalog_baseline_path,
    )
    metadata["native_authority"] = authority
    metadata["native_profiles"] = tuple(profiles)
    rows: list[dict[str, Any]] = []
    for profile, entry in zip(profiles, entries, strict=True):
        role = next(
            role for role, alias in setup.role_aliases.items() if alias == profile.target_slot
        )
        declaration_ref = catalog_read_api.persist_acquisition_supplier_declaration(
            store, authority, entry_id=entry.entry_id
        )
        declaration = catalog_read_api.load_acquisition_supplier_declaration(store, declaration_ref)
        provider = NativeDerivationLeafProviderSelection(
            source_node_id=("input-a" if role == setup.profile.ratio_role else "input-b"),
            supplier_ref=declaration_ref,
            authority_entry_id=entry.entry_id,
            connector_id=declaration.connector_id,
        )
        rows.append(
            {
                "role": role,
                "ref": declaration_ref,
                "provider": provider,
                "selection_row": NativeDerivationPlanningRoleSupplier(
                    role=role,
                    provider=provider,
                    source_declaration_ref=declaration_ref,
                ),
            }
        )
    holder_oracle = {
        "ratio_raw_percent": -3.0,
        "ratio_canonical": -0.03,
        "denominator_usd": 200_000_000_000.0,
        "flow_usd": -6_000_000_000.0,
        "empirical_truth": "not_established",
    }
    return setup, setup.profile_ref, tuple(rows), holder_oracle


@contextmanager
def configured_native_source_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: Any,
    *,
    deployment_security_factory: Callable[[], Any] | None = None,
    claims: Any | None = None,
    request_headers: dict[str, str] | None = None,
    forbid_fetch: bool = True,
    catalog_ready: Callable[..., None] | None = None,
) -> Iterator[tuple[Any, dict[str, Any]]]:
    """Build one actual source/profile before any independently admitted leaf action."""
    problem = _problem()
    holder: dict[str, Any] = {}
    from polisyos.fabric.connectors.sources.world_bank import WorldBankConnector

    fetch_calls: list[str] = []

    async def reject_worldbank_fetch(_connector: Any, _handle: Any, request: Any):
        fetch_calls.append(request.dataset_id)
        raise AssertionError("unpriced native leaf attempted provider fetch")

    if forbid_fetch:
        monkeypatch.setattr(WorldBankConnector, "fetch", reject_worldbank_fetch)
    holder["fetch_calls"] = fetch_calls

    def prepare_case(path: Path, **kwargs: Any):
        case, metadata = _prepare_declared_native_fiscal_case(path, store=kwargs["store"])
        holder["metadata"] = metadata
        return case

    def prepare_catalog(*, store: Any, case: Any, root: Path, **kwargs: Any) -> None:
        from polisyos.runtime.quality.substrate_registry import default_substrate_catalog_paths

        setup, profile_ref, rows, oracle = _install_two_role_wdi_declarations(
            store=store,
            case=case,
            metadata=holder["metadata"],
            root=root,
            catalog_baseline_path=default_substrate_catalog_paths(root).l1_dcat_path,
        )
        holder.update(setup=setup, profile_ref=profile_ref, rows=rows, oracle=oracle)
        if catalog_ready is not None:
            catalog_ready(store=store, case=case, root=root, holder=holder, **kwargs)

    def profile_factory(
        case: Any, _trinity: Any, selected_problem: DesignProblem, path: Path, *, skg_prior: Any
    ):
        from polisyos.scientist.orchestration.engine import BudgetInvocationQuotaPolicy

        assert selected_problem == problem

        def selected_skg_ref(_path: Path, *, snapshot_id: str):
            assert snapshot_id == skg_prior.source_data_snapshot_id
            return skg_prior

        with monkeypatch.context() as selected_source:
            selected_source.setattr(world_fixture, "_skg_ref", selected_skg_ref)
            base, registry, registry_ref = build_selected_method_base_world(
                case,
                path,
                region_or_jurisdiction=selected_problem.jurisdiction_time.region,
                policy_domain=selected_problem.domain,
            )
        holder.update(base=base, registry=registry, registry_ref=registry_ref)
        return _with_hash(
            GenericCycleSimulationProfileV1.model_construct(
                profile_id="test-native-derived-source",
                profile_selection_ref=cycle_job_profile_selection_ref(selected_problem),
                world_model_record_ref=base.record_ref,
                substrate_registry_ref=registry_ref,
                context_inputs=CandidateSimulationContextInputs(
                    substrate_registry=registry,
                    selected_registry_entry_hashes=tuple(
                        entry.entry_content_hash for entry in registry.entries
                    ),
                    world_model_record=base.record,
                ),
                n5=GenericCycleN5ProgramGraphRequestProfileV4(
                    budget_ref="budget://test/native-source-preflight",
                    horizon=HorizonSpec(start=0, end=0, step=1),
                    baseline_state={"government.balance": 10_000_000_000.0},
                    compile_report_ref=ArtifactRef.model_validate(
                        case.compile_report_ref.model_dump(mode="python")
                    ),
                    invocation_quota_policy=BudgetInvocationQuotaPolicy(
                        allocation_id="test-native-source-preflight",
                        total_units=5,
                        protected_units=1,
                    ),
                ),
                limitations=(
                    "controlled_inputs_only",
                    "currentness_not_established",
                    "n5_simulation_not_world_evidence",
                    "n9_not_admitted",
                    "s8_blocked",
                    "source_truth_not_established",
                ),
            )
        )

    def before_dispatch(
        *, service: Any, store: Any, claims: Any, profile: Any, **_kwargs: Any
    ) -> None:
        budget_ref = persist_n7_derivation_dag_budget_profile(
            store,
            N7DerivationDagBudgetProfile(
                profile_id="test-native-source-dag-budget",
                max_nodes=16,
                max_edges=32,
                max_depth=8,
                max_unique_sources=16,
            ),
        )
        setup = holder["setup"]
        selection = NativeDerivationPlanningSelection(
            tenant_id=claims.tenant_id,
            cell_id=claims.cell_id,
            profile_selection_ref=profile.profile_selection_ref,
            registered_profile_ref=holder["profile_ref"],
            dag_budget_profile_ref=budget_ref,
            binding_id="configured-native-two-leaf",
            role_suppliers=tuple(row["selection_row"] for row in holder["rows"]),
        )
        configuration = AcquisitionWorldGrowthConfig(
            native_derivation_planning_selections=(selection,)
        )
        holder["configuration"] = configuration
        service.bind_native_derivation_route_configuration(configuration)

    with served_blocked_generic_source_case(
        tmp_path,
        monkeypatch,
        controlled_candidate_gateway,
        prepare_case=prepare_case,
        prepare_catalog=prepare_catalog,
        profile_factory=profile_factory,
        problem=problem,
        before_dispatch=before_dispatch,
        deployment_security_factory=deployment_security_factory,
        claims=claims,
        request_headers=request_headers,
    ) as served_case:
        yield served_case, holder


def test_fiscal_source_prerequisites_bind_units_and_meanings_before_app(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Close both actual source-role prerequisites without an app, fetch or N5."""
    from polisyos.core.artifacts import (
        FileSystemCAS,
        artifact_ref_identity_key,
        ensure_ir_artifact_store,
    )
    from polisyos.core.contracts.model_input_requirements import load_model_input_port_declaration
    from polisyos.core.contracts.variable_binding import load_variable_representation
    from polisyos.data_forge.read_api import catalog
    from polisyos.fabric.connectors.sources.world_bank import WorldBankConnector
    from polisyos.ir.trinity import load_trinity_bundle_artifact

    calls: list[object] = []

    def forbidden_fetch(*args: Any, **kwargs: Any) -> None:
        calls.append((args, kwargs))
        raise AssertionError("native_source_prerequisites_attempted_provider_fetch")

    monkeypatch.setattr(WorldBankConnector, "fetch", forbidden_fetch)
    store = FileSystemCAS(tmp_path / "cas")
    case, metadata = _prepare_declared_native_fiscal_case(tmp_path / "graph", store=store)
    try:
        port = metadata["port"]
        definitions = metadata["native_definition_refs"]
        declaration = load_model_input_port_declaration(
            store, case.model_input_port_declaration_ref
        )
        assert declaration.ports == (port,)
        assert artifact_ref_identity_key(port.semantic_definition_ref) == artifact_ref_identity_key(
            definitions["fiscal_flow"]
        )
        trinity = load_trinity_bundle_artifact(ensure_ir_artifact_store(store), case.trinity_ref)
        assert artifact_ref_identity_key(trinity.model_spec.model_input_port_declaration_ref) == (
            artifact_ref_identity_key(case.model_input_port_declaration_ref)
        )
        setup, _profile_ref, rows, oracle = _install_two_role_wdi_declarations(
            store=store, case=case, metadata=metadata, root=tmp_path / "catalog-owner"
        )
        bases = {item.role: item.basis for item in setup.profile.inputs}
        assert (
            bases[setup.profile.ratio_role].semantic_definition_ref == definitions["fiscal_share"]
        )
        assert bases[setup.profile.denominator_role].semantic_definition_ref == definitions["gdp"]
        ratio = load_variable_representation(
            store, bases[setup.profile.ratio_role].representation_ref
        )
        denominator = load_variable_representation(
            store, bases[setup.profile.denominator_role].representation_ref
        )
        assert ratio.numerator_ref == port.semantic_definition_ref
        assert ratio.denominator_ref == definitions["gdp"]
        assert ratio.unit_id == "ratio" and denominator.unit_id == "usd"
        assert denominator.quantity_kind == "flow" and denominator.time_support == "period_total"
        assert denominator.money_unit == metadata["money"]
        for row in rows:
            selected = catalog.load_acquisition_supplier_declaration(store, row["ref"])
            resolved = metadata["native_authority"].resolve(selected.entry.entry_id)
            expected_coordinate = "percent" if row["role"] == setup.profile.ratio_role else "usd"
            assert resolved.upstream_catalog_projection["catalog_unit"] == expected_coordinate
            assert resolved.field_binding.raw_unit == expected_coordinate
            assert resolved.field_binding.canonical_unit == (
                "ratio" if row["role"] == setup.profile.ratio_role else "usd"
            )
            source_representation = (
                ratio if row["role"] == setup.profile.ratio_role else denominator
            )
            role_scope = port.scope.model_copy(
                update={"population_ref": source_representation.population_ref}
            )
            assert (
                catalog.acquisition_supplier_declaration_scope_refusal(
                    store, row["ref"], scope=role_scope
                )
                is None
            )
            assert selected.semantic_authority == "not_established"
            assert selected.acquisition_permission == "not_established"
            assert selected.source_currentness == "not_established"
        assert oracle["ratio_raw_percent"] == -3.0
        assert oracle["ratio_canonical"] == -0.03
        assert oracle["denominator_usd"] == 200_000_000_000.0
        assert calls == []
        assert not store.manifest_inventory_snapshot(
            kind="catalog.scoped_measurement_occurrence"
        ).entries
    finally:
        case.close()


@pytest.mark.integration
def test_configured_native_source_exposes_two_unpriced_leaf_routes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: Any,
) -> None:
    """Use actual source/N4 and N7 producers while stopping before fetch/N5."""
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http.services.acquisition_action_service import (
        NativeDerivationLeafRouteProjection,
    )
    from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRouteClosureError

    with configured_native_source_case(tmp_path, monkeypatch, controlled_candidate_gateway) as (
        served_case,
        holder,
    ):
        response = served_case.client.get(
            f"/api/v1/runs/{served_case.control_run_id}/acquisition-routes"
        )
        assert response.status_code == 200, response.text
        routes = response.json()["routes"]
        projections = tuple(
            row
            for row in routes
            if row["schema_version"] == "NativeDerivationLeafRouteProjection@1.0"
        )
        assert len(routes) == len(projections) == 2
        typed_projections = tuple(
            NativeDerivationLeafRouteProjection.model_validate(row) for row in projections
        )
        for row in projections:
            assert set(row) == set(NativeDerivationLeafRouteProjection.model_fields)
        assert len({row.route_id for row in typed_projections}) == 2
        assert len({row.requirement_gap_id for row in typed_projections}) == 2
        assert len({row.planner_record_id for row in typed_projections}) == 2
        assert (
            len({artifact_ref_identity_key(row.derivation_bundle_ref) for row in typed_projections})
            == 1
        )
        assert all(
            (row.tenant_id, row.cell_id, row.run_id)
            == (
                served_case.claims.tenant_id,
                served_case.claims.cell_id,
                served_case.control_run_id,
            )
            for row in typed_projections
        )
        expected_by_node = {row["provider"].source_node_id: row["ref"] for row in holder["rows"]}
        assert {row["source_node_id"] for row in projections} == set(expected_by_node)
        assert all(row["selected_supplier_ref"] for row in projections)
        for projection in projections:
            assert artifact_ref_identity_key(
                ArtifactRef.model_validate(projection["selected_supplier_ref"])
            ) == artifact_ref_identity_key(expected_by_node[projection["source_node_id"]])
        assert all(row.route_status == "inputs_pending" for row in typed_projections)
        assert all(
            row.reason_codes == ("native_leaf_owner_cost_profile_not_established",)
            for row in typed_projections
        )
        assert all("cost_basis" not in row and "replay_pins" not in row for row in projections)
        action_service = served_case.client.app.state.runtime_container.acquisition_action_service
        with tenant_scope(
            None,
            tenant_id=served_case.claims.tenant_id,
            cell_id=served_case.claims.cell_id,
        ):
            loop = action_service._route_loop(
                tenant_id=served_case.claims.tenant_id,
                cell_id=served_case.claims.cell_id,
            )
            for row in typed_projections:
                with pytest.raises(AcquisitionRouteClosureError) as refused:
                    loop.resolve_current_route(
                        run_id=served_case.control_run_id, route_id=row.route_id
                    )
                assert refused.value.code == "native_leaf_owner_cost_profile_not_established"
        assert holder["fetch_calls"] == []
        assert holder["oracle"] == {
            "ratio_raw_percent": -3.0,
            "ratio_canonical": -0.03,
            "denominator_usd": 200_000_000_000.0,
            "flow_usd": -6_000_000_000.0,
            "empirical_truth": "not_established",
        }
        for row in projections:
            detail = served_case.client.get(
                f"/api/v1/runs/{served_case.control_run_id}/acquisition-routes/{row['route_id']}"
            )
            assert detail.status_code == 200, detail.text
            assert detail.json() == row
        assert served_case.semantic_kernel_entries == []


def _prepare_native_epoch_owner_inputs(
    *, store: Any, claims: Any, problem: DesignProblem, holder: dict[str, Any], **_kwargs: Any
) -> None:
    """Prepare the existing native owner before the serving source is captured."""
    import hashlib

    from polisyos.core import canon
    from tests._helpers.acquisition_epoch_production import production_admission_inputs
    from tests._helpers.acquisition_production import bind_fixture_l1_catalog_source

    scope = hashlib.sha256(canon.to_canonical_bytes([claims.tenant_id, claims.cell_id])).hexdigest()
    owner_root = store.root / "runtime/acquisition/world-growth" / scope
    authority = holder["metadata"]["native_authority"]
    bind_fixture_l1_catalog_source(
        authority.repo_root,
        authority.baseline_path,
        adopt_existing_regular_baseline=True,
    )
    holder["native_epoch_args"] = production_admission_inputs(
        owner_root,
        store=store,
        authority=authority,
        overlay_path=owner_root / "overlay.duckdb",
        epoch_history_root=owner_root / "epochs",
        scope_payload={
            "domain": problem.domain,
            "jurisdiction": problem.jurisdiction_time.region,
            "year": 2024,
            "population": holder["metadata"]["native_profiles"][0].population,
        },
        authority_purpose="candidate_simulation",
    )


def _native_fixture_port_factory(state: dict[str, Any]):
    """Compose actual Runtime/Catalog owners over the same predeclared fixture store."""
    from polisyos.data_forge.read_api import catalog as catalog_read_api
    from polisyos.runtime.http.services.acquisition_surface_execution import (
        WorldBankWDIAcquisitionExecutionPort,
    )
    from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthBridge
    from polisyos.runtime.quality.semantic_epoch_qualification import (
        build_semantic_epoch_native_deployment,
    )

    def build(*, control_service: Any, **_kwargs: Any):
        holder = state["holder"]
        authority = holder["metadata"]["native_authority"]
        registry = catalog_read_api.AcquisitionAuthorityRegistry.model_validate_json(
            authority.registry_path.read_bytes()
        )
        appointments = state["appointments"]
        configuration = holder.get("configuration", AcquisitionWorldGrowthConfig())
        control_service.bind_native_derivation_route_configuration(configuration)
        bridge = AcquisitionWorldGrowthBridge(
            config=configuration,
            repo_root=authority.repo_root,
            runtime_root=Path(control_service._cas_root),
            authority=authority,
            artifact_store=control_service._artifact_store,
            event_log=control_service._diagnostic_event_log,
            epoch_deployment=(
                build_semantic_epoch_native_deployment(appointments[-1].config)
                if appointments
                else None
            ),
            promotion_runtime=control_service._promotion_runtime,
            cycle_substrate_context_admission_owner=(
                control_service._cycle_substrate_context_admission_owner
            ),
            control_store=control_service._control_store,
            action_head_sink=control_service.acquisition_route_sink,
            source_control_service=control_service,
        )
        port = WorldBankWDIAcquisitionExecutionPort(
            authority=authority,
            registry=registry,
            provision=authority.provision,
            provision_content_sha256=authority.provision_content_sha256,
            runtime_state_root=Path(control_service._cas_root),
            artifact_store=control_service._artifact_store,
            world_growth_bridge=bridge,
        )
        return port

    return build


def _adopt_native_growth_routes(served: Any, holder: dict[str, Any], closures: tuple[Any, ...]):
    """Bind exact current leaf routes to the already prepared native owner evidence."""
    from decimal import Decimal

    from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthRoute

    args = holder["native_epoch_args"]
    routes = tuple(
        AcquisitionWorldGrowthRoute(
            **{
                name: args[name]
                for name in (
                    "epoch_scope_identity",
                    "authority_purpose",
                    "valid_effect_coordinate_evidence_ref",
                    "visibility_knowledge_cutoff_evidence_ref",
                    "purpose_admission_cutoff_evidence_ref",
                    "facet_source_refs",
                )
            },
            epoch_id=args["epoch_id"] + index,
            tenant_id=closure.tenant_id,
            cell_id=closure.cell_id,
            run_id=closure.run_id,
            route_id=closure.route_id,
            design_problem_ref=closure.design_problem_ref,
            reentry_budget_usd=Decimal("0.50"),
        )
        for index, closure in enumerate(closures)
    )
    configuration = AcquisitionWorldGrowthConfig.model_validate(
        {**holder["configuration"].model_dump(mode="python"), "routes": routes}
    )
    holder["configuration"] = configuration
    served.service.bind_native_derivation_route_configuration(configuration)


@contextmanager
def _live_native_fixture_bridge(*, served: Any, state: dict[str, Any]) -> Iterator[Any]:
    """Use a fresh current app owner only while its dependency guards are live."""
    from fastapi.testclient import TestClient

    from tests._helpers.control_worker import stop_embedded_control_worker

    with TestClient(served.app_factory()) as client:
        control = client.app.state.runtime_container.control_service
        stop_embedded_control_worker(control)
        port = _native_fixture_port_factory(state)(control_service=control)
        bridge = port._world_growth_bridge
        assert bridge is not None
        yield bridge


def _native_epoch_scenario_for_paid_attempt(
    *,
    state: dict[str, Any],
    bridge: Any,
    institution_store: Any,
    closure: Any,
) -> Any:
    """Snapshot exact paid refs and reopen their existing prepared epoch without issuance."""
    from types import SimpleNamespace

    from polisyos.core import contracts
    from polisyos.runtime.quality import semantic_epoch
    from polisyos.runtime.quality.semantic_epoch_store import FileSemanticEpochHistoryRepository

    assert institution_store.root.resolve() == bridge.artifact_store.root.resolve()
    _ref, deferral, attempt = bridge._load_deferral(closure)
    state["paid_attempt"] = attempt
    assert deferral.negative_receipt.failure_codes == ("policy_admission_missing",)
    outcome = bridge.action_head_sink.current_action_outcome(
        tenant_id=closure.tenant_id,
        cell_id=closure.cell_id,
        run_id=closure.run_id,
        source_job_id=closure.source_job_id,
        route_id=closure.route_id,
    )
    assert outcome is not None
    assert outcome.latest_receipt.terminal_outcome == "quarantined_no_growth"
    assert outcome.executing_phase_ref == attempt.action_phase_ref
    executing_head = bridge.control_store.get_acquisition_action_head_by_receipt(
        tenant_id=closure.tenant_id,
        cell_id=closure.cell_id,
        run_id=closure.run_id,
        source_job_id=closure.source_job_id,
        route_id=closure.route_id,
        action_generation=outcome.head.action_generation,
        receipt_ref=outcome.executing_phase_ref,
    )
    assert executing_head is not None
    assert executing_head.receipt_manifest_profile_sha256 is not None
    assert outcome.head.receipt_manifest_profile_sha256 is not None
    pointer = bridge._growth_pointer(attempt.selection, create=False)
    attempt_ref = bridge._attempt_pointer_ref(
        pointer.with_suffix(".attempt.json"), require_selected=True
    )
    deferral_ref = bridge._attempt_pointer_ref(
        pointer.with_suffix(".deferred.json"),
        require_selected=True,
        expected_kind="runtime_quality.acquisition_world_growth_deferral",
    )
    assert str(attempt_ref.artifact_id) == deferral.attempt_ref
    assert str(deferral_ref.artifact_id) == _ref
    # Snapshot the actual purchase's independent SQL selections and owner
    # pointers before the new admission-selection producer can run.
    state["paid_reference_snapshot"] = {
        "original_action_job_id": outcome.head.job_id,
        "attempt_ref": attempt_ref,
        "executing_phase_ref": ArtifactRef(
            artifact_id=outcome.executing_phase_ref,
            kind="runtime_quality.acquisition_route_phase_receipt",
            media_type="application/json",
            manifest_profile_sha256=executing_head.receipt_manifest_profile_sha256,
        ),
        "terminal_ref": ArtifactRef(
            artifact_id=outcome.head.receipt_ref,
            kind="runtime_quality.acquisition_route_loop_receipt",
            media_type="application/json",
            manifest_profile_sha256=outcome.head.receipt_manifest_profile_sha256,
        ),
        "deferral_ref": deferral_ref,
        "negative_receipt_ref": deferral.negative_receipt.receipt_ref,
        "prepared_epoch_ref": deferral.negative_receipt.prepared_epoch_ref,
        "owner_declared_profile_ref": closure.owner_declared_profile_ref,
    }
    prepared_ref = deferral.negative_receipt.prepared_epoch_ref
    statement = contracts.epoch.load_verified_epoch_statement(
        store=bridge.artifact_store, ref=prepared_ref, expected_kind="epoch.prepared"
    )
    prepared = semantic_epoch.PreparedSemanticEpoch(
        **statement,
        prepared_epoch_ref=prepared_ref,
        prepared_content_hash=semantic_epoch._model_hash(
            b"polisyos.epoch.prepared.v1\0", statement
        ),
    )
    selected = bridge.selection(closure)
    assert selected is not None
    _overlay_path, history_root = bridge._paths(selected, create=False)
    history = FileSemanticEpochHistoryRepository(root=history_root, artifacts=institution_store)
    return SimpleNamespace(
        store=institution_store,
        prepared=prepared,
        query=prepared.query,
        history=history,
        service=None,
    )


def _appoint_exact_native_epoch_policy(
    *,
    state: dict[str, Any],
    bridge: Any,
    institution_store: Any,
    closure: Any,
    root: Path,
) -> None:
    """Supply independent test-root admission for the actual persisted prepared epoch."""
    from tests._helpers.semantic_epoch_native import sign_native_epoch_scenario

    scenario = _native_epoch_scenario_for_paid_attempt(
        state=state,
        bridge=bridge,
        institution_store=institution_store,
        closure=closure,
    )
    appointments = state["appointments"]
    previous = appointments[-1] if appointments else None
    native = sign_native_epoch_scenario(
        scenario,
        root,
        custodian=previous.custodian if previous is not None else None,
        prior_admission_refs=(
            previous.config.predicate_policy_admission_refs if previous is not None else ()
        ),
    )
    appointments.append(native)


def _read_retained_native_human_decision(
    *,
    client: Any,
    served: Any,
    trust: Any,
    closure: Any,
    checkpoint: Any,
    resource_digest: str,
) -> str:
    """Read a known committed receipt through the authenticated canonical reader.

    The retained fixture supplies the exact owner-selected CAS reference. This
    does not implement public discovery of a lost POST receipt. The protected
    action still revalidates current PA2/DS9 evidence after this historical read.
    """
    from datetime import UTC, datetime

    from polisyos.core import artifacts
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http.services.human_decision_contracts import HumanDecisionRecord
    from polisyos.runtime.quality.agent_action_authority import AgentActionAuthorityDecision
    from tests._helpers.native_derivation_retained import _verify_retained_selected_signature

    reference = checkpoint.human_decision_record_ref
    assert reference is not None and reference.manifest_profile_sha256 is not None
    response = client.get(
        f"/api/v1/runs/{served.control_run_id}/human-decisions",
        params={
            "record_ref": str(reference.artifact_id),
            "manifest_profile_sha256": reference.manifest_profile_sha256,
        },
        headers={
            "Authorization": trust.authorization_header("acquisition-operator"),
            "X-Tenant-ID": served.claims.tenant_id,
        },
    )
    assert response.status_code == 200, response.text
    record = HumanDecisionRecord.model_validate(response.json())
    container = client.app.state.runtime_container
    control = container.control_service
    with tenant_scope(None, tenant_id=closure.tenant_id, cell_id=closure.cell_id):
        store = control._artifact_store
        _verify_retained_selected_signature(
            store, reference, container.human_decision_service.custody.verifier
        )
        assert record == HumanDecisionRecord.model_validate(
            artifacts.load_core_json_artifact(store, reference)
        )
        reservation = control.human_decision_sink.get_reservation_generation(
            tenant_id=closure.tenant_id,
            governed_action_key=record.governed_action_key,
            reservation_version=record.reservation_version,
        )
        assert reservation is not None and reservation.state == "committed"
        assert reservation.reservation_id == record.reservation_id
        assert reservation.binding_sha256 == record.binding_sha256
        assert reservation.record_ref == reservation.record_sha256 == str(reference.artifact_id)
        assert reservation.durable_event_id is not None
        assert reservation == control.human_decision_sink.get_reservation(
            tenant_id=closure.tenant_id, governed_action_key=record.governed_action_key
        )
        source = AgentActionAuthorityDecision.model_validate(
            artifacts.load_core_json_artifact(store, record.source_ref)
        )
        source_context = store.get_manifest(record.source_ref).same_input_closure
    assert source_context is not None
    assert (
        source_context.tenant_id,
        source_context.cell_id,
        source_context.run_id,
        source_context.job_id,
    ) == (closure.tenant_id, closure.cell_id, closure.run_id, checkpoint.action_job_id)
    assert record.source_kind == "agent_action_authority"
    assert record.tenant_id == closure.tenant_id and record.run_id == closure.run_id
    assert record.decision_action_exercised == "approve"
    assert (
        source.contract_ref
        == record.basis_ref
        == checkpoint.mandate_slot["delegation_contract_ref"]
    )
    assert source.contract_ref in record.mandate_source_refs
    assert source.bound_resource_digest == resource_digest
    assert source.permission_snapshot is not None
    assert source.permission_snapshot.resource_digest == resource_digest
    now = datetime.now(UTC)
    if (
        record.valid_from is None
        or record.valid_until is None
        or not (record.valid_from <= now < record.valid_until)
    ):
        raise ValueError("retained_native_human_decision_not_current")
    return str(reference.artifact_id)


def _run_signed_native_leaf_action(
    *,
    served: Any,
    trust: Any,
    signers: Any,
    identities: Any,
    institution_key_root: Path,
    route_id: str,
    idempotency_key: str,
    retained_mandate: Any | None = None,
    human_decision_submission_root: Path | None = None,
) -> dict[str, Any]:
    """Perform each real PA2/DS9 exchange and worker in fresh app instances."""
    from fastapi.testclient import TestClient

    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http.services.acquisition_action_service import (
        AcquisitionRouteMutationRequest,
    )
    from tests._helpers.acquisition_served_history import (
        _appoint_served_acquisition_mandate,
        _approve_served_acquisition_request,
        _recover_served_human_decision,
    )
    from tests._helpers.control_worker import dispatch_one_control_job, stop_embedded_control_worker

    route_path = f"/api/v1/runs/{served.control_run_id}/acquisition-routes/{route_id}"
    route_template = "/api/v1/runs/{run_id}/acquisition-routes/{route_id}"
    slot = dict(retained_mandate.mandate_slot) if retained_mandate is not None else None
    if slot is not None:
        trust.raw["acquisition_authority"]["mandates"].append(slot)
    with trust.authorization_exchange("acquisition-operator") as authorization:
        with TestClient(served.app_factory()) as client:
            control = client.app.state.runtime_container.control_service
            stop_embedded_control_worker(control)
            projection = client.get(
                route_path,
                headers={
                    "Authorization": trust.authorization_header("acquisition-operator"),
                    "X-Tenant-ID": served.claims.tenant_id,
                },
            )
            assert projection.status_code == 200, projection.text
            row = projection.json()
            request = AcquisitionRouteMutationRequest(
                route_projection_hash=row["route_projection_hash"],
                planner_report_hash=row["planner_report_hash"],
                replay_pins=row["replay_pins"],
                idempotency_key=idempotency_key,
            )
            action_service = client.app.state.runtime_container.acquisition_action_service
            with tenant_scope(
                None, tenant_id=served.claims.tenant_id, cell_id=served.claims.cell_id
            ):
                closure = action_service._route_loop(
                    tenant_id=served.claims.tenant_id, cell_id=served.claims.cell_id
                ).resolve_current_route(run_id=served.control_run_id, route_id=route_id)
            refused, resource_digest = trust.post(
                client,
                route_path + "/decision-request",
                request.model_dump(mode="json"),
                route=route_template + "/decision-request",
            )
            assert refused.status_code == 200, refused.text
            if retained_mandate is None:
                if human_decision_submission_root is not None:
                    from polisyos.runtime.http.services.acquisition_action_service import (
                        AcquisitionActionService,
                    )

                    expected_job_id = AcquisitionActionService._job_id(closure, request)
                    if (human_decision_submission_root / f"{expected_job_id}.json").exists():
                        raise ValueError(
                            "saved_human_decision_requires_existing_mandate_checkpoint"
                        )
                slot, job_id = _appoint_served_acquisition_mandate(
                    control,
                    closure,
                    request,
                    resource_digest,
                    tmp_path=institution_key_root,
                    signers=signers,
                    identities=identities,
                )
            else:
                from polisyos.runtime.http.services.acquisition_action_service import (
                    AcquisitionActionService,
                )

                job_id = AcquisitionActionService._job_id(closure, request)
                assert job_id == retained_mandate.action_job_id
                assert slot["resource_digest"] == resource_digest
                assert (slot["tenant_id"], slot["cell_id"], slot["run_id"], slot["route_id"]) == (
                    closure.tenant_id,
                    closure.cell_id,
                    closure.run_id,
                    closure.route_id,
                )
                if retained_mandate.human_decision_record_ref is not None:
                    slot["human_decision_record_ref"] = _read_retained_native_human_decision(
                        client=client,
                        served=served,
                        trust=trust,
                        closure=closure,
                        checkpoint=retained_mandate,
                        resource_digest=resource_digest,
                    )
        if retained_mandate is None:
            trust.raw["acquisition_authority"]["mandates"].append(slot)
        if slot.get("human_decision_record_ref") is None:
            with TestClient(served.app_factory()) as client:
                control = client.app.state.runtime_container.control_service
                stop_embedded_control_worker(control)
                submission_checkpoint = (
                    human_decision_submission_root / f"{job_id}.json"
                    if human_decision_submission_root is not None
                    else None
                )
                if submission_checkpoint is not None and submission_checkpoint.exists():
                    human_ref = _recover_served_human_decision(
                        client, submission_checkpoint=submission_checkpoint, trust=trust
                    )
                else:
                    _source, human_ref = _approve_served_acquisition_request(
                        client,
                        request,
                        resource_digest,
                        closure=closure,
                        trust=trust,
                        signers=signers,
                        identities=identities,
                        cas_root=served.cas_root,
                        submission_checkpoint=submission_checkpoint,
                    )
                slot["human_decision_record_ref"] = human_ref
        with TestClient(served.app_factory()) as client:
            control = client.app.state.runtime_container.control_service
            stop_embedded_control_worker(control)
            accepted, observed_digest = trust.post(
                client,
                route_path + "/execute",
                request.model_dump(mode="json"),
                route=route_template + "/execute",
            )
            assert accepted.status_code in {200, 202}, accepted.text
            assert observed_digest == resource_digest
            assert accepted.json()["job_id"] == job_id
            # Dispatch before closing this stopped-worker app. A fresh app
            # would start an embedded worker against the already queued job.
            assert (
                dispatch_one_control_job(
                    store=control._control_store,
                    handler=control._process_control_job,
                    expected_job_id=job_id,
                )
                == job_id
            )
            job = control._control_store.get_job(job_id)
            assert job is not None and job.state == "completed", job
            with tenant_scope(None, tenant_id=closure.tenant_id, cell_id=closure.cell_id):
                outcome = control.acquisition_route_sink.current_action_outcome(
                    tenant_id=closure.tenant_id,
                    cell_id=closure.cell_id,
                    run_id=closure.run_id,
                    source_job_id=closure.source_job_id,
                    route_id=route_id,
                )
            assert outcome is not None and outcome.head.job_id == job_id
            assert outcome.head.receipt_manifest_profile_sha256 is not None
            return {
                "request": request,
                "job_id": job_id,
                "terminal": outcome.latest_receipt,
                "head": outcome.head,
                "progress": job.progress,
                "closure": closure,
                "authorization": authorization,
            }


def assert_paid_native_leaf_admission_and_restart(
    *,
    served: Any,
    state: dict[str, Any],
    trust: Any,
    signers: Any,
    identities: Any,
    institution_key_root: Path,
    institution_root: Path,
    route_id: str,
    original_action: dict[str, Any],
    transport_calls: list[Any],
    idempotency_key: str = "native-leaf-a-after-epoch-appointment",
) -> Any:
    """Admit the actual paid purchase under a new demo grant, then retry it.

    Fresh CI callers may first create one purchase. A retained-case caller must
    supply its existing selected terminal and original job; this body neither
    initializes a source nor performs a provider purchase.
    """
    from types import SimpleNamespace

    from fastapi.testclient import TestClient

    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.quality.acquisition_world_growth import (
        replay_native_derivation_input_collection,
    )
    from tests._helpers.control_worker import stop_embedded_control_worker

    claims = served.claims
    with (
        _live_native_fixture_bridge(served=served, state=state) as current_bridge,
        tenant_scope(None, tenant_id=claims.tenant_id, cell_id=claims.cell_id),
    ):
        if state["appointments"]:
            _native_epoch_scenario_for_paid_attempt(
                state=state,
                bridge=current_bridge,
                institution_store=served.store,
                closure=original_action["closure"],
            )
        else:
            _appoint_exact_native_epoch_policy(
                state=state,
                bridge=current_bridge,
                institution_store=served.store,
                closure=original_action["closure"],
                root=institution_root,
            )
    before_admission = tuple(transport_calls)
    from polisyos.fabric.data_plane import resolve_live_transport_trace

    paid_attempt = state["paid_attempt"]
    trace_before = resolve_live_transport_trace(paid_attempt.evidence.raw_evidence_ref)
    assert trace_before == paid_attempt.evidence.transport_trace
    assert trace_before.call_count == paid_attempt.evidence.authorization.budget.call_budget == 1
    journal_path = Path(paid_attempt.evidence.request_ref.journal_path)
    journal_before = journal_path.read_bytes()

    # Admission is a distinct action with a new exact mandate, DS9 record,
    # PA2 decision and job. It reopens the paid owner bytes, never fetches.
    pending = _run_signed_native_leaf_action(
        served=served,
        trust=trust,
        signers=signers,
        identities=identities,
        institution_key_root=institution_key_root,
        route_id=route_id,
        idempotency_key=idempotency_key,
        retained_mandate=state.get("retained_admission_checkpoint"),
        human_decision_submission_root=institution_root / "human-decision-submissions",
    )
    terminal = pending["terminal"]
    assert terminal.terminal_outcome == "inputs_pending"
    assert terminal.reentry_receipt_ref is None
    assert terminal.native_input_collection_ref is not None
    assert tuple(transport_calls) == before_admission
    assert pending["job_id"] != original_action["job_id"]
    assert terminal.decision_ref != original_action["terminal"].decision_ref
    with tenant_scope(None, tenant_id=claims.tenant_id, cell_id=claims.cell_id):
        collection = replay_native_derivation_input_collection(
            served.store, terminal.native_input_collection_ref
        ).collection
    assert collection.input_closure_status == "partial"
    assert {row.source_node_id for row in collection.source_inputs} == {"input-a"}
    assert {row.source_node_id for row in collection.pending_actions} == {"input-b"}
    from decimal import Decimal

    from polisyos.data_forge.read_api import catalog as catalog_read_api

    with tenant_scope(None, tenant_id=claims.tenant_id, cell_id=claims.cell_id):
        _stored, replayed, _selection = catalog_read_api.replay_selected_scoped_measurement_facts(
            served.store, collection.source_inputs[0].occurrence_ref
        )
    assert replayed.canonical_value == Decimal("-0.03")

    expected = state["paid_reference_snapshot"]
    prior = pending["closure"].prior_paid_input_admission
    assert prior is not None
    assert prior.original_action_job_id == expected["original_action_job_id"]
    assert prior.original_action_job_id == original_action["job_id"]
    for name, reference in expected.items():
        if name != "original_action_job_id":
            assert artifact_ref_identity_key(getattr(prior, name)) == artifact_ref_identity_key(
                reference
            ), name
    assert str(prior.terminal_ref.artifact_id) == original_action["head"].receipt_ref
    assert (
        prior.terminal_ref.manifest_profile_sha256
        == original_action["head"].receipt_manifest_profile_sha256
    )
    assert pending["closure"].current_projection_hash != route_id

    # Retry through a fresh live app with the same exact action credential.
    # This is the original current grant's idempotent request, not a renewal.
    with TestClient(served.app_factory()) as client:
        control = client.app.state.runtime_container.control_service
        stop_embedded_control_worker(control)
        retried, _resource_digest = trust.post(
            client,
            f"/api/v1/runs/{served.control_run_id}/acquisition-routes/{route_id}/execute",
            pending["request"].model_dump(mode="json"),
            route="/api/v1/runs/{run_id}/acquisition-routes/{route_id}/execute",
            extra_headers={"Authorization": pending["authorization"]},
        )
        assert retried.status_code in {200, 202}, retried.text
        assert retried.json()["job_id"] == pending["job_id"]
        job = control._control_store.get_job(pending["job_id"])
        assert job is not None and job.state == "completed"
        assert job.progress == pending["progress"]
        with tenant_scope(None, tenant_id=claims.tenant_id, cell_id=claims.cell_id):
            outcome = control.acquisition_route_sink.current_action_outcome(
                tenant_id=claims.tenant_id,
                cell_id=claims.cell_id,
                run_id=served.control_run_id,
                source_job_id=served.job_id,
                route_id=route_id,
            )
        assert outcome is not None and outcome.head == pending["head"]
        assert outcome.latest_receipt == terminal
        assert outcome.executing_phase is not None
        assert outcome.executing_phase.schema_version == "AcquisitionRoutePhaseReceipt@1.4"
        assert outcome.executing_phase.prior_paid_input_admission == prior
        response = client.get(
            f"/api/v1/runs/{served.core_run_id}",
            headers={
                "Authorization": trust.authorization_header("acquisition-operator"),
                "X-Tenant-ID": claims.tenant_id,
            },
        )
        assert response.status_code == 200, response.text
        generic_projection = response.json()["run"]["generic_cycle_simulation"]
        assert generic_projection["n4_source_status"] == "resolved"
        assert generic_projection.get("acquisition_history_limitation_code") is None
        history = generic_projection["acquisition_history"]
        pending_rows = [row for row in history if row["terminal_outcome"] == "inputs_pending"]
        assert len(pending_rows) == 1
        assert pending_rows[0]["model_goal_status"] == "inputs_pending"
        assert artifact_ref_identity_key(
            ArtifactRef.model_validate(pending_rows[0]["native_input_collection_ref"])
        ) == artifact_ref_identity_key(terminal.native_input_collection_ref)
        assert generic_projection["publication_authority"] is False
        assert generic_projection["currentness_status"] == "not_established"
    assert tuple(transport_calls) == before_admission
    assert journal_path.read_bytes() == journal_before
    assert resolve_live_transport_trace(paid_attempt.evidence.raw_evidence_ref) == trace_before
    assert served.semantic_kernel_entries == []
    return SimpleNamespace(
        action=pending,
        paid_attempt=paid_attempt,
        transport_trace=trace_before,
        journal_path=journal_path,
        journal_bytes=journal_before,
        provider_calls=before_admission,
        generic_projection=generic_projection,
    )


def assert_native_paid_negative_projection_is_profile_bound(
    *, bridge: Any, closure: Any, store: Any, output_root: Path
) -> None:
    """Keep a real selected negative unestablished and fail on its missing profile."""
    from polisyos.common.canonical_profile import CanonicalProfileRefusalError
    from polisyos.core import artifacts

    assert bridge.artifact_store.root.resolve() == store.root.resolve()
    assert bridge.project_growth_outcome(closure) == ("not_established", None)
    negative_ref = closure.prior_paid_input_admission.negative_receipt_ref
    selected_manifest = store._manifest_path_for_ref(
        negative_ref.artifact_id, negative_ref.manifest_profile_sha256
    )
    _negative_blob, default_manifest = store._paths(negative_ref.artifact_id)
    manifests = {selected_manifest}
    default_ref = artifacts.artifact_ref_for_manifest(store.get_manifest(negative_ref.artifact_id))
    if artifact_ref_identity_key(default_ref) == artifact_ref_identity_key(negative_ref):
        manifests.add(default_manifest)
    withheld_root = output_root / "withheld-original-negative-profile"
    withheld_root.mkdir()
    withheld = []
    try:
        for index, manifest_path in enumerate(sorted(manifests)):
            retained_path = withheld_root / f"{index}-{manifest_path.name}"
            manifest_path.replace(retained_path)
            withheld.append((manifest_path, retained_path))
        with pytest.raises(
            (
                ValueError,
                artifacts.ArtifactUnavailableError,
                CanonicalProfileRefusalError,
            )
        ):
            bridge.project_growth_outcome(closure)
    finally:
        for manifest_path, retained_path in reversed(withheld):
            retained_path.replace(manifest_path)
    assert bridge.project_growth_outcome(closure) == ("not_established", None)


def assert_retained_native_paid_input_admission(
    *,
    base: Path,
    output_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    transport_calls: list[Any],
    semantic_kernel_entries: list[Any],
    continuation_selection: Any | None = None,
    idempotency_key: str = "retained-native-a-new-current-admission",
    skip_qualified_historical_removal_checks: bool = False,
) -> dict[str, Any]:
    """Reuse a retained real purchase with new explicit fixture institutions.

    The caller must forbid fresh provider transport, reservation and N4/N5 at
    their original effect boundaries. No source initializer or old permission
    is restored here; retained signers are loaded by the canonical key loader.
    The opt-in skip omits only the already-qualified negative-profile removal
    probe. Current route, source, sibling, authority and restart checks remain.
    """
    from fastapi.testclient import TestClient

    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.fabric.data_plane import resolve_live_transport_trace
    from polisyos.runtime.http import deployment_security as security
    from polisyos.runtime.http.services import acquisition_surface_execution as surface_owner
    from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRouteClosureError
    from tests._helpers.acquisition_served_history import _existing_key_config, _ExternalTrust
    from tests._helpers.control_worker import stop_embedded_control_worker
    from tests._helpers.native_derivation_retained import (
        bind_retained_native_source_app,
        load_retained_native_admission_checkpoint,
        load_retained_native_source_fixture,
    )

    trust_root = output_root / "current-demo-trust"
    trust_root.mkdir(parents=True)
    trust = _ExternalTrust(trust_root)
    try:
        signers, identities = _existing_key_config(base / "trust", trust)

        def deployment():
            return security.build_deployment_security(
                security.DeploymentSecurityConfig.from_mapping(trust.raw)
            )

        claims = deployment().identity_provider.extract_user_claims(
            trust.tokens["acquisition-operator"]
        )
        with tenant_scope(None, tenant_id=claims.tenant_id, cell_id=claims.cell_id):
            case = load_retained_native_source_fixture(
                base, binding_id="configured-native-two-leaf"
            )
        assert (case.tenant_id, case.cell_id) == (claims.tenant_id, claims.cell_id)
        if continuation_selection is not None:
            with tenant_scope(None, tenant_id=claims.tenant_id, cell_id=claims.cell_id):
                checkpoint = load_retained_native_admission_checkpoint(
                    case, continuation_selection, institution_key_root=base / "trust"
                )
            from types import SimpleNamespace

            case.state["appointments"].append(SimpleNamespace(config=checkpoint.epoch_config))
            case.state["retained_admission_checkpoint"] = checkpoint
        case.claims = claims
        case.semantic_kernel_entries = semantic_kernel_entries
        bind_retained_native_source_app(case, deployment_security_factory=deployment)
        monkeypatch.setenv("POLISYOS_RUNTIME_EXECUTION_PROFILE", "development")
        monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
        monkeypatch.setenv("POLISYOS_CONTROL_SQLITE_PATH", str(case.control_database))
        monkeypatch.setenv("POLISYOS_CACHE_HOME", str(base / "runtime-cache"))
        monkeypatch.setenv("POLISYOS_TEST_RETAIN_NATIVE_EPOCH_SIGNER", "1")
        monkeypatch.setattr(
            surface_owner,
            "build_production_world_bank_wdi_execution_port",
            _native_fixture_port_factory(case.state),
        )
        trace_before = resolve_live_transport_trace(case.attempt.evidence.raw_evidence_ref)
        journal_path = Path(case.attempt.evidence.request_ref.journal_path)
        journal_before = journal_path.read_bytes()
        selected_before = {
            artifact_ref_identity_key(ref): case.store.get_bytes(ref)
            for ref in (case.compiled_ref, case.source_ref, case.attempt_ref, case.terminal_ref)
        }
        initial_calls = tuple(transport_calls)
        sibling = None
        sibling_refusal = None
        route_path = (
            f"/api/v1/runs/{case.control_run_id}/acquisition-routes/{case.terminal.route_id}"
        )
        headers = {
            "Authorization": trust.authorization_header("acquisition-operator"),
            "X-Tenant-ID": claims.tenant_id,
        }
        with TestClient(case.app_factory()) as client:
            container = client.app.state.runtime_container
            control = container.control_service
            stop_embedded_control_worker(control)
            with tenant_scope(None, tenant_id=claims.tenant_id, cell_id=claims.cell_id):
                outcome = control.acquisition_route_sink.current_action_outcome(
                    tenant_id=claims.tenant_id,
                    cell_id=claims.cell_id,
                    run_id=case.control_run_id,
                    source_job_id=case.job_id,
                    route_id=case.terminal.route_id,
                )
            assert outcome is not None and outcome.latest_receipt == case.terminal
            assert outcome.head.receipt_ref == str(case.terminal_ref.artifact_id)
            response = client.get(route_path, headers=headers)
            assert response.status_code == 200, response.text
            route = response.json()
            assert route["schema_version"] == "AcquisitionRouteProjection@1.2"
            assert route["route_status"] == "paid_input_admission_only"
            assert route["world_growth"] == "not_established"
            assert route.get("admitted_observation_delta") is None
            assert route["qualification_status"] == "pending_epoch_activation"
            assert artifact_ref_identity_key(
                ArtifactRef.model_validate(route["prior_paid_input_admission"]["attempt_ref"])
            ) == artifact_ref_identity_key(case.attempt_ref)
            if continuation_selection is None:
                listed = client.get(
                    f"/api/v1/runs/{case.control_run_id}/acquisition-routes", headers=headers
                )
                assert listed.status_code == 200, listed.text
                siblings = tuple(
                    row for row in listed.json()["routes"] if row.get("source_node_id") == "input-b"
                )
                assert len(siblings) == 1
                sibling = siblings[0]
                assert sibling["schema_version"] == "NativeDerivationLeafRouteProjection@1.0"
                assert sibling["route_status"] == "inputs_pending"
                assert sibling["reason_codes"] == ["native_leaf_owner_cost_profile_not_established"]
            original_response = client.get(f"/api/v1/runs/{case.core_run_id}", headers=headers)
            assert original_response.status_code == 200, original_response.text
            original_projection = original_response.json()["run"]["generic_cycle_simulation"]
            assert original_projection["n4_source_status"] == "resolved"
            assert original_projection.get("acquisition_history_limitation_code") is None
            assert any(
                row["terminal_outcome"] == "quarantined_no_growth"
                for row in original_projection["acquisition_history"]
            )
            loop = container.acquisition_action_service._route_loop(
                tenant_id=claims.tenant_id, cell_id=claims.cell_id
            )
            with tenant_scope(None, tenant_id=claims.tenant_id, cell_id=claims.cell_id):
                closure = loop.resolve_current_route(
                    run_id=case.control_run_id, route_id=case.terminal.route_id
                )
                if continuation_selection is None:
                    with pytest.raises(AcquisitionRouteClosureError) as denied:
                        loop.resolve_current_route(
                            run_id=case.control_run_id, route_id=sibling["route_id"]
                        )
                    if not skip_qualified_historical_removal_checks:
                        port = container.acquisition_action_service._production_execution_port
                        assert_native_paid_negative_projection_is_profile_bound(
                            bridge=port._world_growth_bridge,
                            closure=closure,
                            store=case.store,
                            output_root=output_root,
                        )
                    sibling_refusal = denied.value.code
                    assert sibling_refusal == "native_leaf_owner_cost_profile_not_established"
            original_action = {
                "job_id": outcome.head.job_id,
                "head": outcome.head,
                "terminal": outcome.latest_receipt,
                "closure": closure,
            }
        assert tuple(transport_calls) == initial_calls
        assert journal_path.read_bytes() == journal_before
        assert resolve_live_transport_trace(case.attempt.evidence.raw_evidence_ref) == trace_before
        for ref in (case.compiled_ref, case.source_ref, case.attempt_ref, case.terminal_ref):
            assert case.store.get_bytes(ref) == selected_before[artifact_ref_identity_key(ref)]

        admitted = assert_paid_native_leaf_admission_and_restart(
            served=case,
            state=case.state,
            trust=trust,
            signers=signers,
            identities=identities,
            institution_key_root=base / "trust",
            institution_root=output_root / "new-current-native-institution",
            route_id=case.terminal.route_id,
            original_action=original_action,
            transport_calls=transport_calls,
            idempotency_key=idempotency_key,
        )
        assert tuple(transport_calls) == initial_calls
        assert journal_path.read_bytes() == journal_before
        assert resolve_live_transport_trace(case.attempt.evidence.raw_evidence_ref) == trace_before
        assert (
            admitted.generic_projection["n5_observations"] == original_projection["n5_observations"]
        )
        return {
            "original_action_job_id": original_action["job_id"],
            "admission_job_id": admitted.action["job_id"],
            "original_terminal_ref": case.terminal_ref.model_dump(mode="json"),
            "attempt_ref": case.attempt_ref.model_dump(mode="json"),
            "collection_ref": admitted.action["terminal"].native_input_collection_ref.model_dump(
                mode="json"
            ),
            "new_provider_calls": len(transport_calls) - len(initial_calls),
            "sibling_status": sibling["route_status"] if sibling is not None else None,
            "sibling_refusal": sibling_refusal,
            "prior_prechecks_reused": continuation_selection is not None,
        }
    finally:
        trust.close()


@pytest.mark.integration
def test_paid_native_leaf_persists_pending_and_restart_does_not_refetch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: Any,
) -> None:
    """Keep one paid native input while a separately unauthorized sibling is pending."""
    from fastapi.testclient import TestClient

    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http import deployment_security as security
    from polisyos.runtime.http.services import acquisition_surface_execution as surface_owner
    from tests._helpers.acquisition_production import intercepted_wdi_transport
    from tests._helpers.acquisition_served_history import _ExternalTrust, _key_config
    from tests._helpers.control_worker import stop_embedded_control_worker
    from tests._helpers.lane01_wdi_profiles import fixture_wdi_response
    from tests._helpers.native_derivation_quotes import adopt_served_native_leaf_quotes

    trust_root = tmp_path / "trust"
    trust_root.mkdir()
    trust = _ExternalTrust(trust_root)
    signers, identities = _key_config(trust_root, trust)
    state: dict[str, Any] = {"appointments": []}

    def deployment():
        return security.build_deployment_security(
            security.DeploymentSecurityConfig.from_mapping(trust.raw)
        )

    try:
        claims = deployment().identity_provider.extract_user_claims(
            trust.tokens["acquisition-operator"]
        )

        def catalog_ready(**kwargs: Any) -> None:
            state["holder"] = kwargs["holder"]
            _prepare_native_epoch_owner_inputs(**kwargs)

        def response_factory(_method: str, url: str, params: Any) -> bytes:
            profiles = state["holder"]["metadata"]["native_profiles"]
            matching = tuple(profile for profile in profiles if profile.indicator_id in url)
            assert len(matching) == 1, url
            profile = matching[0]
            assert params["date"] in {str(profile.year), f"{profile.year}:{profile.year}"}
            return fixture_wdi_response(profile)

        transport_calls = intercepted_wdi_transport(
            monkeypatch, allow_loopback=True, response_factory=response_factory
        )
        monkeypatch.setattr(
            surface_owner,
            "build_production_world_bank_wdi_execution_port",
            _native_fixture_port_factory(state),
        )
        with configured_native_source_case(
            tmp_path,
            monkeypatch,
            controlled_candidate_gateway,
            deployment_security_factory=deployment,
            claims=claims,
            request_headers={
                "Authorization": trust.authorization_header("acquisition-operator"),
                "X-Tenant-ID": claims.tenant_id,
            },
            forbid_fetch=False,
            catalog_ready=catalog_ready,
        ) as (served, holder):
            with tenant_scope(None, tenant_id=claims.tenant_id, cell_id=claims.cell_id):
                closures = adopt_served_native_leaf_quotes(
                    served, holder, quote_usd_by_node={"input-a": 0.01, "input-b": 0.02}
                )
                _adopt_native_growth_routes(served, holder, closures)
            assert transport_calls == []
            assert served.semantic_kernel_entries == []
            initial_response = served.client.get(
                f"/api/v1/runs/{served.core_run_id}",
                headers={
                    "Authorization": trust.authorization_header("acquisition-operator"),
                    "X-Tenant-ID": claims.tenant_id,
                },
            )
            assert initial_response.status_code == 200, initial_response.text
            initial_generic = initial_response.json()["run"]["generic_cycle_simulation"]
            initial_n5_lineage = tuple(
                {
                    name: row[name]
                    for name in (
                        "node_ref",
                        "cycle_index",
                        "candidate_id",
                        "status",
                        "n5_input_ref",
                        "n5_execution_ref",
                        "simulation_result_ref",
                    )
                }
                for row in initial_generic["n5_observations"]
            )
            assert initial_n5_lineage
            assert all(
                row["status"] == "simulation_blocked" and row["simulation_result_ref"] is None
                for row in initial_n5_lineage
            )
            leaf_a = next(
                closure
                for closure in closures
                if closure.native_derivation_leaf_scope.source_node_id == "input-a"
            )

        # The first genuine action captures bytes, then truthfully stops because
        # no native institutional policy has yet been appointed for that basis.
        quarantined = _run_signed_native_leaf_action(
            served=served,
            trust=trust,
            signers=signers,
            identities=identities,
            institution_key_root=trust_root,
            route_id=leaf_a.route_id,
            idempotency_key="native-leaf-a-before-epoch-appointment",
            human_decision_submission_root=tmp_path / "human-decision-submissions",
        )
        assert quarantined["terminal"].terminal_outcome == "quarantined_no_growth"
        assert len(transport_calls) == 1
        admitted = assert_paid_native_leaf_admission_and_restart(
            served=served,
            state=state,
            trust=trust,
            signers=signers,
            identities=identities,
            institution_key_root=trust_root,
            institution_root=tmp_path / "native-institution",
            route_id=leaf_a.route_id,
            original_action=quarantined,
            transport_calls=transport_calls,
        )
        pending = admitted.action
        terminal = pending["terminal"]
        paid_attempt = admitted.paid_attempt
        before_admission = admitted.provider_calls
        trace_before = admitted.transport_trace
        journal_path = admitted.journal_path
        journal_before = admitted.journal_bytes
        from polisyos.fabric.data_plane import resolve_live_transport_trace

        # A fresh app reads the exact selected partial terminal and model-goal
        # status. No pending sibling mandate, fetch, or numerical result appears.
        with TestClient(served.app_factory()) as client:
            control = client.app.state.runtime_container.control_service
            stop_embedded_control_worker(control)
            with tenant_scope(None, tenant_id=claims.tenant_id, cell_id=claims.cell_id):
                outcome = control.acquisition_route_sink.current_action_outcome(
                    tenant_id=claims.tenant_id,
                    cell_id=claims.cell_id,
                    run_id=served.control_run_id,
                    source_job_id=served.job_id,
                    route_id=leaf_a.route_id,
                )
            assert outcome is not None and outcome.head == pending["head"]
            assert outcome.latest_receipt == terminal
            response = client.get(
                f"/api/v1/runs/{served.core_run_id}",
                headers={
                    "Authorization": trust.authorization_header("acquisition-operator"),
                    "X-Tenant-ID": claims.tenant_id,
                },
            )
            assert response.status_code == 200, response.text
            projection = response.json()["run"]["generic_cycle_simulation"]
            assert projection.get("acquisition_history_limitation_code") is None
            history = projection["acquisition_history"]
            pending_rows = tuple(
                row for row in history if row["terminal_outcome"] == "inputs_pending"
            )
            assert len(pending_rows) == 1
            assert pending_rows[0]["model_goal_status"] == "inputs_pending"
            assert artifact_ref_identity_key(
                ArtifactRef.model_validate(pending_rows[0]["native_input_collection_ref"])
            ) == artifact_ref_identity_key(terminal.native_input_collection_ref)
            assert (
                tuple(
                    {name: row[name] for name in initial_n5_lineage[index]}
                    for index, row in enumerate(projection["n5_observations"])
                )
                == initial_n5_lineage
            )
            assert projection["publication_authority"] is False
            assert projection["currentness_status"] == "not_established"

            # Removing the selected collection limits only action history. The
            # original blocked numerical observation remains exact and readable.
            collection_blob, _manifest = served.store._paths(
                terminal.native_input_collection_ref.artifact_id
            )
            withheld_collection = tmp_path / "withheld-native-input-collection"
            collection_blob.replace(withheld_collection)
            try:
                limited_response = client.get(
                    f"/api/v1/runs/{served.core_run_id}",
                    headers={
                        "Authorization": trust.authorization_header("acquisition-operator"),
                        "X-Tenant-ID": claims.tenant_id,
                    },
                )
                assert limited_response.status_code == 200, limited_response.text
                limited_projection = limited_response.json()["run"]["generic_cycle_simulation"]
                assert limited_projection.get("acquisition_history") is None
                assert limited_projection["acquisition_history_limitation_code"] == (
                    "acquisition_action_history_integrity_not_established"
                )
                assert (
                    tuple(
                        {name: row[name] for name in initial_n5_lineage[index]}
                        for index, row in enumerate(limited_projection["n5_observations"])
                    )
                    == initial_n5_lineage
                )
                assert tuple(transport_calls) == before_admission
                assert served.semantic_kernel_entries == []
            finally:
                withheld_collection.replace(collection_blob)
            restored_response = client.get(
                f"/api/v1/runs/{served.core_run_id}",
                headers={
                    "Authorization": trust.authorization_header("acquisition-operator"),
                    "X-Tenant-ID": claims.tenant_id,
                },
            )
            assert restored_response.status_code == 200, restored_response.text
            assert (
                restored_response.json()["run"]["generic_cycle_simulation"]["acquisition_history"]
                == history
            )

            # A present compiled source ref is not a replay. Withhold the
            # exact N4 body while keeping the compiled selection untouched.
            root_source_ref = served.compiled.n4_recursive_source_ref
            assert root_source_ref is not None
            source_blob, _source_manifest = served.store._paths(root_source_ref.artifact_id)
            withheld_source = tmp_path / "withheld-native-generic-n4-source"
            source_blob.replace(withheld_source)
            try:
                missing_source_response = client.get(
                    f"/api/v1/runs/{served.core_run_id}",
                    headers={
                        "Authorization": trust.authorization_header("acquisition-operator"),
                        "X-Tenant-ID": claims.tenant_id,
                    },
                )
                assert missing_source_response.status_code == 200, missing_source_response.text
                missing_source = missing_source_response.json()["run"]["generic_cycle_simulation"]
                assert missing_source["n4_source_status"] == "not_established"
                assert missing_source.get("acquisition_history") is None
                assert missing_source["acquisition_history_limitation_code"] is not None
                assert tuple(transport_calls) == before_admission
                assert served.semantic_kernel_entries == []
            finally:
                withheld_source.replace(source_blob)
            restored_source_response = client.get(
                f"/api/v1/runs/{served.core_run_id}",
                headers={
                    "Authorization": trust.authorization_header("acquisition-operator"),
                    "X-Tenant-ID": claims.tenant_id,
                },
            )
            assert restored_source_response.status_code == 200, restored_source_response.text
            restored_source = restored_source_response.json()["run"]["generic_cycle_simulation"]
            assert restored_source["n4_source_status"] == "resolved"
            assert restored_source["acquisition_history"] == history

            # The already approved A action is not a grant for the distinct B
            # route, even though its own quote and provider are configured.
            from polisyos.runtime.http.services.acquisition_action_service import (
                AcquisitionActionService,
                AcquisitionRouteMutationRequest,
            )

            leaf_b = next(
                closure
                for closure in closures
                if closure.native_derivation_leaf_scope.source_node_id == "input-b"
            )
            leaf_b_path = (
                f"/api/v1/runs/{served.control_run_id}/acquisition-routes/{leaf_b.route_id}"
            )
            response = client.get(
                leaf_b_path,
                headers={
                    "Authorization": trust.authorization_header("acquisition-operator"),
                    "X-Tenant-ID": claims.tenant_id,
                },
            )
            assert response.status_code == 200, response.text
            row = response.json()
            denied_request = AcquisitionRouteMutationRequest(
                route_projection_hash=row["route_projection_hash"],
                planner_report_hash=row["planner_report_hash"],
                replay_pins=row["replay_pins"],
                idempotency_key="native-leaf-b-without-independent-mandate",
            )
            denied_job_id = AcquisitionActionService._job_id(leaf_b, denied_request)
            refused, _digest = trust.post(
                client,
                leaf_b_path + "/execute",
                denied_request.model_dump(mode="json"),
                route="/api/v1/runs/{run_id}/acquisition-routes/{route_id}/execute",
            )
            assert refused.status_code == 409, refused.text
            assert refused.json()["code"] == "human_decision_required"
            assert control._control_store.get_job(denied_job_id) is None
        assert tuple(transport_calls) == before_admission
        assert journal_path.read_bytes() == journal_before
        assert resolve_live_transport_trace(paid_attempt.evidence.raw_evidence_ref) == trace_before
        assert served.semantic_kernel_entries == []
    finally:
        trust.close()


def test_native_fixture_bridge_uses_live_current_app_for_same_selected_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Closed app owners refuse while a fresh owner reopens the exact same CAS bytes."""
    from types import SimpleNamespace

    from polisyos.core import artifacts
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.fabric.connectors.sources.world_bank import WorldBankConnector
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from polisyos.runtime.http.dependencies import build_runtime_api_context
    from polisyos.runtime.http.errors import RuntimeDependencyUnavailableError
    from polisyos.runtime.http.security import build_fixture_identity_claims
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationHorizonController,
    )
    from tests._helpers.acquisition_production import _resolver, bind_fixture_l1_catalog_source

    effect_calls: list[str] = []

    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        effect_calls.append("provider_or_n5")
        raise AssertionError("native_fixture_lifecycle_attempted_provider_or_n5")

    monkeypatch.setattr(WorldBankConnector, "fetch", forbidden)
    monkeypatch.setattr(JointSimulationHorizonController, "run", forbidden)
    monkeypatch.setenv("POLISYOS_RUNTIME_EXECUTION_PROFILE", "development")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    monkeypatch.setenv("POLISYOS_CONTROL_SQLITE_PATH", str(tmp_path / "control.sqlite3"))
    monkeypatch.setenv("POLISYOS_CACHE_HOME", str(tmp_path / "cache"))
    authority, _entry = _resolver(tmp_path / "knowledge")
    bind_fixture_l1_catalog_source(authority.repo_root, authority.baseline_path)
    cas_root = tmp_path / "cas"
    runs_root = cas_root / "runs"
    state = {"holder": {"metadata": {"native_authority": authority}}, "appointments": []}

    def app_factory() -> Any:
        return create_runtime_api_app(
            cas_root=cas_root,
            core_runs_root=runs_root,
            container_overrides=RuntimeContainerOverrides(
                runtime_api_context=build_runtime_api_context(
                    cas_root=cas_root, core_runs_root=runs_root
                )
            ),
            allow_fixture_identity=True,
            repo_root=authority.repo_root,
        )

    served = SimpleNamespace(app_factory=app_factory)
    claims = build_fixture_identity_claims()
    with tenant_scope(None, tenant_id=claims.tenant_id, cell_id=claims.cell_id):
        with _live_native_fixture_bridge(served=served, state=state) as first:
            selected = first.artifact_store.put_bytes(
                b"selected fixture lifecycle bytes",
                artifacts.ArtifactWriteOptions(
                    kind="tests.native_fixture_lifecycle", media_type="application/octet-stream"
                ),
                return_selected_profile=True,
            )
            assert selected.manifest_profile_sha256 is not None
            assert first.artifact_store.get_bytes(selected) == b"selected fixture lifecycle bytes"
        with pytest.raises(RuntimeDependencyUnavailableError):
            first.artifact_store.get_bytes(selected)
        with _live_native_fixture_bridge(served=served, state=state) as second:
            assert second is not first
            assert second.artifact_store is not first.artifact_store
            assert second.artifact_store.root.resolve() == first.artifact_store.root.resolve()
            assert second.artifact_store.get_bytes(selected) == b"selected fixture lifecycle bytes"
    assert effect_calls == []
    assert "ports" not in state


def assert_retained_native_human_decision_recovery(
    *,
    base: Path,
    output_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    submission_body: dict[str, Any],
    exposure_session_ref: str,
    expected_record_ref: ArtifactRef,
    foreign_exposure_session_ref: str,
) -> dict[str, Any]:
    """Read a legacy receipt publicly using its original logical submission.

    The caller supplies the original submission selectors, not a SQL lookup to
    the recovery endpoint. The selected expected record is an independent test
    oracle. No old mandate, epoch appointment or protected-action permission is
    installed. Provider, source-initializer, create-record and N4/N5 boundaries
    must be forbidden by the caller's admitted driver.
    """
    from fastapi.testclient import TestClient

    from polisyos.core import artifacts
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http import deployment_security as security
    from polisyos.runtime.http.services import acquisition_surface_execution as surface_owner
    from tests._helpers.acquisition_served_history import _existing_key_config, _ExternalTrust
    from tests._helpers.control_worker import stop_embedded_control_worker
    from tests._helpers.native_derivation_retained import (
        bind_retained_native_source_app,
        load_retained_native_source_fixture,
    )

    trust_root = output_root / "current-read-demo-trust"
    trust_root.mkdir(parents=True)
    trust = _ExternalTrust(trust_root)
    try:
        _existing_key_config(base / "trust", trust)

        def deployment():
            return security.build_deployment_security(
                security.DeploymentSecurityConfig.from_mapping(trust.raw)
            )

        claims = deployment().identity_provider.extract_user_claims(
            trust.tokens["human-reviewer-1"]
        )
        with tenant_scope(None, tenant_id=claims.tenant_id, cell_id=claims.cell_id):
            case = load_retained_native_source_fixture(
                base, binding_id="configured-native-two-leaf"
            )
        case.claims = claims
        bind_retained_native_source_app(case, deployment_security_factory=deployment)
        monkeypatch.setenv("POLISYOS_RUNTIME_EXECUTION_PROFILE", "development")
        monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
        monkeypatch.setenv("POLISYOS_CONTROL_SQLITE_PATH", str(case.control_database))
        monkeypatch.setenv("POLISYOS_CACHE_HOME", str(base / "runtime-cache"))
        monkeypatch.setattr(
            surface_owner,
            "build_production_world_bank_wdi_execution_port",
            _native_fixture_port_factory(case.state),
        )
        path = f"/api/v1/runs/{case.control_run_id}/human-decisions/recovery"
        exposure = {"X-PolicyOS-Human-Decision-Exposure": exposure_session_ref}

        def recover(client, body, *, subject="human-reviewer-1", headers=exposure):
            return client.post(
                path,
                json=body,
                headers={
                    "Authorization": trust.authorization_header(subject),
                    "X-Tenant-ID": claims.tenant_id,
                    **headers,
                },
            )

        with TestClient(case.app_factory()) as client:
            stop_embedded_control_worker(client.app.state.runtime_container.control_service)
            response = recover(client, submission_body)
            assert response.status_code == 200, response.text
            receipt = response.json()
            assert receipt["status"] == "committed", receipt
            assert receipt["binding_rule"] == "legacy_record_v2"
            assert receipt["operational_authority"] is False
            assert artifact_ref_identity_key(
                ArtifactRef.model_validate(receipt["record_ref"])
            ) == artifact_ref_identity_key(expected_record_ref)
            known = client.get(
                f"/api/v1/runs/{case.control_run_id}/human-decisions",
                params={
                    "record_ref": str(expected_record_ref.artifact_id),
                    "manifest_profile_sha256": expected_record_ref.manifest_profile_sha256,
                },
                headers={
                    "Authorization": trust.authorization_header("human-reviewer-1"),
                    "X-Tenant-ID": claims.tenant_id,
                },
            )
            assert known.status_code == 200, known.text
            assert known.json()["reservation_id"] == receipt["reservation_id"]
            foreign = recover(client, submission_body, subject="acquisition-operator")
            assert foreign.status_code == 403, foreign.text
            different = recover(
                client,
                {**submission_body, "accountability_statement": "A different submitted decision."},
            )
            assert (
                different.status_code == 200 and different.json()["status"] == "not_established"
            ), different.text
            wrong_exposure = recover(
                client,
                submission_body,
                headers={"X-PolicyOS-Human-Decision-Exposure": foreign_exposure_session_ref},
            )
            assert (
                wrong_exposure.status_code == 200
                and wrong_exposure.json()["status"] == "not_established"
            ), wrong_exposure.text
            with tenant_scope(None, tenant_id=claims.tenant_id, cell_id=claims.cell_id):
                store = case.store
                selected_path = store._manifest_path_for_ref(
                    expected_record_ref.artifact_id, expected_record_ref.manifest_profile_sha256
                )
                default_path = store._paths(expected_record_ref.artifact_id)[1]
                paths = {selected_path}
                if (
                    artifacts.artifact_ref_for_manifest(
                        store.get_manifest(expected_record_ref.artifact_id)
                    )
                    == expected_record_ref
                ):
                    paths.add(default_path)
            held = []
            try:
                for index, manifest_path in enumerate(sorted(paths)):
                    saved = output_root / f"withheld-receipt-{index}-{manifest_path.name}"
                    manifest_path.replace(saved)
                    held.append((manifest_path, saved))
                missing = recover(client, submission_body)
                assert (
                    missing.status_code == 200 and missing.json()["status"] == "not_established"
                ), missing.text
            finally:
                for manifest_path, saved in reversed(held):
                    saved.replace(manifest_path)
            restored = recover(client, submission_body)
            assert restored.status_code == 200 and restored.json() == receipt, restored.text
        with TestClient(case.app_factory()) as client:
            stop_embedded_control_worker(client.app.state.runtime_container.control_service)
            restarted = recover(client, submission_body)
            assert restarted.status_code == 200 and restarted.json() == receipt, restarted.text
        return {
            "receipt": receipt,
            "known_record_get": 200,
            "foreign_subject": 403,
            "different_command": "not_established",
            "different_exposure": "not_established",
            "removed_profile": "not_established",
            "restored_and_fresh_app": "same_receipt",
        }
    finally:
        trust.close()
