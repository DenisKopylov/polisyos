"""Serve configured N7 leaves and independently admitted native partial actions.

Controlled transport bytes and signed test institutions exercise actual owners.
The partial route never enters N5 or establishes empirical source truth.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

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

if TYPE_CHECKING:
    from polisyos.runtime.http.services.acquisition_action_service import (
        AcquisitionCustodyRecoveryRequest,
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
        custodian=getattr(previous, "custodian", None),
        prior_admission_refs=(
            previous.config.predicate_policy_admission_refs if previous is not None else ()
        ),
    )
    if previous is not None:
        from polisyos.runtime.quality.epoch_deployment import EpochDeploymentConfig

        old = previous.config
        if old.evidence_cas_root != native.config.evidence_cas_root or (
            old.native_epoch_history_root != native.config.native_epoch_history_root
        ):
            raise ValueError("native_fixture_epoch_history_roots_differ")
        trusted = {
            (row.identity, str(row.public_key_path), row.roles): row
            for row in (*old.trusted_issuers, *native.config.trusted_issuers)
        }
        admissions = {
            artifact_ref_identity_key(ref): ref
            for ref in (
                *old.predicate_policy_admission_refs,
                *native.config.predicate_policy_admission_refs,
            )
        }
        native.config = EpochDeploymentConfig.model_validate(
            {
                **native.config.model_dump(mode="python"),
                "trusted_issuers": tuple(trusted.values()),
                "predicate_policy_admission_refs": tuple(admissions.values()),
                "revoked_key_ids": tuple(
                    dict.fromkeys((*old.revoked_key_ids, *native.config.revoked_key_ids))
                ),
            }
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
    executing_at: Any | None = None,
) -> str:
    """Read a known committed receipt through the authenticated canonical reader.

    The retained fixture supplies the exact owner-selected CAS reference. This
    does not implement public discovery of a lost POST receipt. The protected
    action still revalidates current PA2/DS9 evidence after this historical read.
    """
    from polisyos.core import artifacts
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http.services.human_decision_contracts import HumanDecisionRecord
    from polisyos.runtime.quality.agent_action_authority import AgentActionAuthorityDecision
    from tests._helpers.native_derivation_retained import (
        _verify_retained_selected_signature,
        require_retained_native_human_decision_current,
    )

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
    if executing_at is None:
        require_retained_native_human_decision_current(record)
    elif (
        record.valid_from is None
        or record.valid_until is None
        or not (record.valid_from <= executing_at < record.valid_until)
    ):
        raise ValueError("retained_native_resume_human_decision_not_effective_at_execution")
    return str(reference.artifact_id)


def _approve_native_request_through_exposure_routes(
    *,
    client: Any,
    control: Any,
    trust: Any,
    request: Any,
    resource_digest: str,
    closure: Any,
    signers: Any,
    identities: Any,
    cas_root: Path,
    submission_checkpoint: Path | None,
    authority_valid_until: Any | None,
) -> tuple[Any, str]:
    """Issue external predicates separately, then use Runtime exposure and submission routes."""
    from collections import Counter
    from datetime import UTC, datetime

    from polisyos.core import artifacts, canon
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http.services.human_decision_contracts import HumanDecisionGateResponse
    from polisyos.runtime.quality.agent_action_authority import AgentActionAuthorityDecision
    from tests._helpers.acquisition_human_decision import prepare_human_decision
    from tests._helpers.acquisition_served_history import _submit_served_human_decision

    route_path = f"/api/v1/runs/{closure.run_id}"
    route_template = "/api/v1/runs/{run_id}/acquisition-routes/{route_id}"
    response, observed_digest = trust.post(
        client,
        f"{route_path}/acquisition-routes/{closure.route_id}/decision-request",
        request.model_dump(mode="json"),
        route=route_template + "/decision-request",
    )
    assert response.status_code == 200 and observed_digest == resource_digest, response.text
    source_ref = response.json()["authority_decision_ref"]
    tenant_id, cell_id = closure.tenant_id, closure.cell_id
    service = client.app.state.runtime_container.human_decision_service
    fixture_issuer_store = artifacts.FileSystemCAS(cas_root, ownership_enforced=True).for_tenant(
        tenant_id, cell_id
    )
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        source = AgentActionAuthorityDecision.model_validate(
            canon.from_canonical_bytes(control._artifact_store.get_bytes(source_ref))
        )
        assert source.refusal_reasons == ("human_decision_missing",), source.refusal_reasons
        gate_input = prepare_human_decision(
            control,
            service,
            source_ref,
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=closure.run_id,
            signers=signers,
            identities=identities,
            now=datetime.now(UTC),
            audit_path=cas_root / "runtime" / "audit" / "access.jsonl",
            authority_valid_until=authority_valid_until,
            fixture_issuer_store=fixture_issuer_store,
            runtime_exposure_via_http=True,
        )

    reviewer_headers = {
        "Authorization": trust.authorization_header("human-reviewer-1"),
        "X-Tenant-ID": tenant_id,
    }
    gate_params: dict[str, str] = {
        "source_kind": gate_input.source_kind,
        "source_ref": gate_input.source_ref,
        "action_kind": gate_input.action_kind,
        "principal_binding_ref": gate_input.principal_binding_ref,
        "reviewer_separation_ref": gate_input.reviewer_separation_ref,
        "presentation_contract_ref": gate_input.presentation_contract_ref,
        "basis_digest": gate_input.basis_digest,
    }
    gate_url = f"{route_path}/human-decision-gate"
    gate_response = client.get(gate_url, params=gate_params, headers=reviewer_headers)
    assert gate_response.status_code == 200, gate_response.text
    gate = HumanDecisionGateResponse.model_validate(gate_response.json())
    session_ref = gate.exposure.exposure_session_ref
    assert session_ref is not None
    required_refs = gate.exposure.required_artifact_digests
    assert required_refs and gate.exposure.completed_artifact_digests == ()

    # Do not add a grant to the acquisition operator: this evidence-use path also
    # requires runs.human_decisions.create, which the signed fixture principal lacks.
    first_ref = required_refs[0]
    evidence_url = f"{route_path}/human-decision-evidence/{first_ref}/content"
    underprivileged_principal = client.get(
        evidence_url,
        headers={
            "Authorization": trust.authorization_header("acquisition-operator"),
            "X-Tenant-ID": tenant_id,
            "X-PolicyOS-Human-Decision-Exposure": session_ref,
        },
    )
    assert underprivileged_principal.status_code == 409, underprivileged_principal.text
    assert underprivileged_principal.json().get("code") == "DS9-DECISION-PERMISSION-UNVERIFIED"

    wrong_session_ref = "sha256:" + "0" * 64
    if wrong_session_ref == session_ref:
        wrong_session_ref = "sha256:" + "1" * 64
    missing_session = client.get(
        evidence_url,
        headers={
            **reviewer_headers,
            "X-PolicyOS-Human-Decision-Exposure": wrong_session_ref,
        },
    )
    assert missing_session.status_code == 400, missing_session.text
    assert missing_session.json().get("error") == "bad_request"
    assert missing_session.json().get("detail") == "DS9-DECISION-ARTIFACT-MISSING"

    for artifact_ref in required_refs:
        delivery = client.get(
            f"{route_path}/human-decision-evidence/{artifact_ref}/content",
            headers={
                **reviewer_headers,
                "X-PolicyOS-Human-Decision-Exposure": session_ref,
            },
        )
        assert delivery.status_code == 200, delivery.text
        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            expected_bytes = control._artifact_store.get_bytes(artifact_ref)
        assert delivery.content == expected_bytes
        assert delivery.headers.get("cache-control") == "no-store"
        assert delivery.headers.get("etag") == f'"{artifact_ref}"'
        assert delivery.headers.get("x-policyos-exposure-session") == session_ref

    gate_params["exposure_session_ref"] = session_ref
    admitted_response = client.get(gate_url, params=gate_params, headers=reviewer_headers)
    assert admitted_response.status_code == 200, admitted_response.text
    admitted = HumanDecisionGateResponse.model_validate(admitted_response.json())
    assert admitted.status == "available", admitted.reason_codes
    assert Counter(admitted.exposure.completed_artifact_digests) == Counter(required_refs)
    assert admitted.submission is not None
    body = admitted.submission.selector.model_dump(
        mode="json", exclude={"exposure_session_ref", "operational_authority"}
    )
    body.update(
        action="approve",
        decision_mode="ordinary",
        accountability_statement="I accept this bounded acquisition.",
        dissent_statement="The measurement limitations remain material and were reviewed.",
    )

    missing_session_submission, _ = trust.post(
        client,
        f"{route_path}/human-decisions",
        body,
        route="/api/v1/runs/{run_id}/human-decisions",
        subject="human-reviewer-1",
        extra_headers={"X-PolicyOS-Human-Decision-Exposure": wrong_session_ref},
    )
    assert missing_session_submission.status_code == 409, missing_session_submission.text
    assert missing_session_submission.json().get("code") == "DS9-DECISION-ARTIFACT-MISSING"
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        assert (
            control.human_decision_sink.get_reservation(
                tenant_id=tenant_id,
                governed_action_key=admitted.governed_action_key,
            )
            is None
        )

    record_ref = _submit_served_human_decision(
        client,
        run_id=closure.run_id,
        body=body,
        exposure_session_ref=session_ref,
        trust=trust,
        submission_checkpoint=submission_checkpoint,
    )
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        reservation = control.human_decision_sink.get_reservation(
            tenant_id=tenant_id,
            governed_action_key=admitted.governed_action_key,
        )
    assert reservation is not None and reservation.state == "committed"
    assert reservation.record_ref == record_ref
    return source, record_ref


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
    authority_valid_for_seconds: int | None = None,
    action_checkpoint_root: Path | None = None,
    runtime_exposure_via_http: bool = False,
    stop_before_execute: bool = False,
) -> dict[str, Any]:
    """Perform each real PA2/DS9 exchange and worker in fresh app instances."""
    from datetime import UTC, datetime, timedelta

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

    if authority_valid_for_seconds is not None:
        if retained_mandate is not None:
            raise ValueError("retained_native_validity_cannot_change_existing_acts")
        if type(authority_valid_for_seconds) is not int or not (
            600 <= authority_valid_for_seconds <= 3600
        ):
            raise ValueError("native_fixture_authority_window_out_of_bounds")

    def save_action(stage: str, *, job_id: str, request: Any, **values: Any) -> None:
        if action_checkpoint_root is None:
            return
        import json

        from tools.lib.fs import atomic_write_text

        action_checkpoint_root.mkdir(parents=True, exist_ok=True)
        payload = {
            "stage": stage,
            "job_id": job_id,
            "route_id": route_id,
            "run_id": served.control_run_id,
            "request": request.model_dump(mode="json"),
            **values,
        }
        atomic_write_text(
            action_checkpoint_root / f"{job_id}.json", json.dumps(payload, sort_keys=True) + "\n"
        )

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
        save_action(
            "mandate_selected",
            job_id=job_id,
            request=request,
            mandate_slot=slot,
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
                    authority_valid_until = (
                        datetime.now(UTC) + timedelta(seconds=authority_valid_for_seconds)
                        if authority_valid_for_seconds is not None
                        else None
                    )
                    if runtime_exposure_via_http:
                        _source, human_ref = _approve_native_request_through_exposure_routes(
                            client=client,
                            control=control,
                            trust=trust,
                            request=request,
                            resource_digest=resource_digest,
                            closure=closure,
                            signers=signers,
                            identities=identities,
                            cas_root=served.cas_root,
                            submission_checkpoint=submission_checkpoint,
                            authority_valid_until=authority_valid_until,
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
                            **(
                                {"authority_valid_until": authority_valid_until}
                                if authority_valid_until is not None
                                else {}
                            ),
                        )
                slot["human_decision_record_ref"] = human_ref
        save_action(
            "human_decision_selected",
            job_id=job_id,
            request=request,
            mandate_slot=slot,
            resource_digest=resource_digest,
        )
        if stop_before_execute:
            return {
                "job_id": job_id,
                "human_decision_record_ref": slot["human_decision_record_ref"],
                "execute_status": None,
            }
        with TestClient(served.app_factory()) as client:
            control = client.app.state.runtime_container.control_service
            stop_embedded_control_worker(control)
            accepted, observed_digest = trust.post(
                client,
                route_path + "/execute",
                request.model_dump(mode="json"),
                route=route_template + "/execute",
            )
            if action_checkpoint_root is not None:
                save_action(
                    "execute_response",
                    job_id=job_id,
                    request=request,
                    mandate_slot=slot,
                    response_status=accepted.status_code,
                    response=accepted.json(),
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
            save_action(
                "worker_returned",
                job_id=job_id,
                request=request,
                mandate_slot=slot,
                state=job.state if job else None,
                attempt=job.attempt if job else None,
                error_message=job.error_message if job else None,
                progress=job.progress if job else None,
            )
            assert job is not None and job.state == "completed", job
            with tenant_scope(None, tenant_id=closure.tenant_id, cell_id=closure.cell_id):
                outcome = control.acquisition_route_sink.current_action_outcome(
                    tenant_id=closure.tenant_id,
                    cell_id=closure.cell_id,
                    run_id=closure.run_id,
                    source_job_id=closure.source_job_id,
                    route_id=route_id,
                )
            if outcome is not None and action_checkpoint_root is not None:
                from dataclasses import asdict

                head = asdict(outcome.head)
                head["created_at"] = outcome.head.created_at.isoformat()
                save_action(
                    "canonical_outcome",
                    job_id=job_id,
                    request=request,
                    mandate_slot=slot,
                    progress=job.progress,
                    head=head,
                    terminal=outcome.latest_receipt.model_dump(mode="json"),
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


def assert_retained_native_action_resume(
    *,
    served: Any,
    checkpoint: Any,
    trust: Any,
    monkeypatch: pytest.MonkeyPatch,
    output_root: Path,
    idempotency_key: str,
    custody_recovery: AcquisitionCustodyRecoveryRequest | None = None,
) -> dict[str, Any]:
    """Resume custody of an already selected outcome from its stored request.

    The prior epoch policy and current institutional acts are separate inputs.
    No source, mandate, HumanDecision, provider call or numerical work is
    produced here. The canonical head must prove the protected effect already
    selected its owner outcome. This path does not request new protected use.
    """
    import json
    from datetime import UTC, datetime

    from fastapi.testclient import TestClient

    from polisyos.core import artifacts
    from tests._helpers.control_worker import dispatch_one_control_job, stop_embedded_control_worker
    from tests._helpers.native_derivation_retained import (
        forbid_retained_native_resume_effects,
        read_retained_native_action_resume_inputs,
        require_retained_native_resume_descendant,
        retained_native_owner_scope,
    )

    if checkpoint.human_decision_record_ref is None:
        raise ValueError("retained_native_resume_human_decision_missing")
    slot = dict(checkpoint.mandate_slot)
    slot["human_decision_record_ref"] = str(checkpoint.human_decision_record_ref.artifact_id)
    existing = trust.raw["acquisition_authority"]["mandates"]
    if slot not in existing:
        existing.append(slot)
    # The actual worker claims the already-existing expired lease. Prevent an
    # app startup thread from racing that claim before the caller can stop it.
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    saved: dict[str, Any] = {"job_id": checkpoint.action_job_id}
    output_root.mkdir(parents=True, exist_ok=True)

    def save() -> None:
        (output_root / "retained-native-resume.json").write_text(
            json.dumps(saved, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )

    with forbid_retained_native_resume_effects():
        with TestClient(served.app_factory()) as client:
            container = client.app.state.runtime_container
            control = container.control_service
            stop_embedded_control_worker(control)
            with retained_native_owner_scope(served, served.claims):
                inputs = read_retained_native_action_resume_inputs(
                    served,
                    checkpoint,
                    claims=served.claims,
                    control=control,
                    idempotency_key=idempotency_key,
                )
                admission = container.acquisition_action_service._validated_mutation(
                    tenant_id=served.tenant_id,
                    cell_id=served.cell_id,
                    run_id=served.control_run_id,
                    route_id=slot["route_id"],
                    request=inputs.request,
                )
                if admission.job_id != checkpoint.action_job_id:
                    raise ValueError("retained_native_resume_job_identity_changed")
                selected = control.acquisition_route_sink.current_action_outcome(
                    tenant_id=served.tenant_id,
                    cell_id=served.cell_id,
                    run_id=served.control_run_id,
                    source_job_id=served.job_id,
                    route_id=slot["route_id"],
                )
                if (
                    selected is None
                    or selected.head.job_id != checkpoint.action_job_id
                    or selected.head.receipt_phase
                    not in {"outcome_selected", "world_committed_reentry_pending", "terminal"}
                    or selected.selection_phase is None
                    or selected.executing_phase is None
                ):
                    raise ValueError("retained_native_resume_selected_outcome_required")
                if selected.head.receipt_manifest_profile_sha256 is None:
                    raise ValueError("retained_native_resume_ancestor_profile_required")
                before_ref = artifacts.artifact_ref_for_manifest(
                    artifacts.resolve_manifest_by_profile(
                        control._artifact_store,
                        selected.head.receipt_ref,
                        selected.head.receipt_manifest_profile_sha256,
                    )
                )
                baseline_head = selected.head
                if custody_recovery is not None:
                    # The explicit caller locator remains fixed across retries;
                    # never choose a later failed attempt automatically.
                    baseline_head = control._control_store.get_acquisition_action_head_by_receipt(
                        tenant_id=served.tenant_id,
                        cell_id=served.cell_id,
                        run_id=served.control_run_id,
                        source_job_id=served.job_id,
                        route_id=slot["route_id"],
                        action_generation=selected.head.action_generation,
                        receipt_ref=str(custody_recovery.head_ref.artifact_id),
                    )
                    if baseline_head is None:
                        raise ValueError("retained_native_recovery_selected_head_missing")
                    before_ref = custody_recovery.head_ref
                    require_retained_native_resume_descendant(
                        store=control._artifact_store,
                        control_store=control._control_store,
                        before_head=baseline_head,
                        before_ref=before_ref,
                        outcome=selected,
                    )
                saved.update(
                    payload_ref=inputs.payload_ref,
                    request=inputs.request.model_dump(mode="json"),
                    attempt_before=inputs.job.attempt,
                    selected_head_before=baseline_head.receipt_ref,
                    selected_head_phase_before=baseline_head.receipt_phase,
                    selected_head_before_ref=before_ref.model_dump(mode="json"),
                    action_generation=selected.head.action_generation,
                )
                save()
                _read_retained_native_human_decision(
                    client=client,
                    served=served,
                    trust=trust,
                    closure=admission.closure,
                    checkpoint=checkpoint,
                    resource_digest=slot["resource_digest"],
                    executing_at=selected.executing_phase.generated_at,
                )
            job = inputs.job
            if custody_recovery is not None:
                recovery_request = inputs.request.model_copy(
                    update={
                        "custody_recovery": custody_recovery,
                    }
                )
                route_path = (
                    f"/api/v1/runs/{served.control_run_id}/acquisition-routes/{slot['route_id']}"
                )
                saved["custody_recovery_submission"] = recovery_request.model_dump(mode="json")
                save()
                with trust.authorization_exchange("acquisition-operator"):
                    response, current_digest = trust.post(
                        client,
                        route_path + "/execute",
                        recovery_request.model_dump(mode="json"),
                        route="/api/v1/runs/{run_id}/acquisition-routes/{route_id}/execute",
                    )
                job = control._control_store.get_job(checkpoint.action_job_id)
                saved.update(
                    custody_recovery_status=response.status_code,
                    custody_recovery_response=response.json(),
                    custody_recovery_resource_digest=current_digest,
                    state_after_recovery_request=None if job is None else job.state,
                    attempt_after_recovery_request=None if job is None else job.attempt,
                )
                save()
                assert response.status_code in {200, 202}, response.text
                accepted = response.json()
                assert accepted["job_id"] == checkpoint.action_job_id
                assert accepted["authority_decision_ref"] == inputs.payload["decision_ref"]
                assert job is not None and job.payload_ref == inputs.payload_ref
            now = datetime.now(UTC)
            if job.state == "running" and (
                job.lease_expires_at is None or job.lease_expires_at > now
            ):
                raise ValueError("retained_native_resume_lease_still_current")
            if job.state in {"pending", "running"}:
                assert (
                    dispatch_one_control_job(
                        store=control._control_store,
                        handler=control._process_control_job,
                        expected_job_id=checkpoint.action_job_id,
                    )
                    == checkpoint.action_job_id
                )
            elif job.state != "completed":
                raise ValueError("retained_native_resume_job_not_recoverable")
            completed = control._control_store.get_job(checkpoint.action_job_id)
            with retained_native_owner_scope(served, served.claims):
                outcome = control.acquisition_route_sink.current_action_outcome(
                    tenant_id=served.tenant_id,
                    cell_id=served.cell_id,
                    run_id=served.control_run_id,
                    source_job_id=served.job_id,
                    route_id=slot["route_id"],
                )
            saved.update(
                state=None if completed is None else completed.state,
                head=(
                    {
                        field: getattr(outcome.head, field)
                        for field in (
                            "job_id",
                            "action_generation",
                            "head_generation",
                            "receipt_phase",
                            "receipt_ref",
                            "receipt_manifest_profile_sha256",
                        )
                    }
                    if outcome is not None
                    else None
                ),
                terminal=(
                    outcome.latest_receipt.model_dump(mode="json") if outcome is not None else None
                ),
                progress=None if completed is None else completed.progress,
            )
            save()
            assert completed is not None and outcome is not None
            with retained_native_owner_scope(served, served.claims):
                require_retained_native_resume_descendant(
                    store=control._artifact_store,
                    control_store=control._control_store,
                    before_head=baseline_head,
                    before_ref=before_ref,
                    outcome=outcome,
                )
                terminal_ref = artifacts.artifact_ref_for_manifest(
                    artifacts.resolve_manifest_by_profile(
                        control._artifact_store,
                        outcome.head.receipt_ref,
                        outcome.head.receipt_manifest_profile_sha256,
                    )
                )
            assert completed.job_id == checkpoint.action_job_id
            assert completed.state == "completed"
            assert outcome.latest_receipt.terminal_outcome == "inputs_pending"
            assert outcome.latest_receipt.native_input_collection_ref is not None

        with TestClient(served.app_factory()) as client:
            control = client.app.state.runtime_container.control_service
            stop_embedded_control_worker(control)
            response = client.get(
                f"/api/v1/runs/{served.core_run_id}",
                headers={
                    "Authorization": trust.authorization_header("acquisition-operator"),
                    "X-Tenant-ID": served.tenant_id,
                },
            )
            saved["fresh_api_status"] = response.status_code
            save()
            assert response.status_code == 200, response.text
            projection = response.json()["run"]["generic_cycle_simulation"]
            saved["fresh_generic_projection"] = projection
            save()
            assert projection["publication_authority"] is False
            assert projection["currentness_status"] == "not_established"
            assert any(
                row["terminal_outcome"] == "inputs_pending"
                and row["action_generation"] == selected.head.action_generation
                and artifact_ref_identity_key(ArtifactRef.model_validate(row["route_receipt_ref"]))
                == artifact_ref_identity_key(terminal_ref)
                for row in projection["acquisition_history"]
            )
            retried = read_retained_native_action_resume_inputs(
                served,
                checkpoint,
                claims=served.claims,
                control=control,
                idempotency_key=idempotency_key,
            )
            saved["fresh_stored_job_id"] = retried.job.job_id
            saved["fresh_stored_request"] = retried.request.model_dump(mode="json")
            save()
            assert retried.job.job_id == checkpoint.action_job_id
            assert retried.request == inputs.request
            assert retried.job.progress == completed.progress
    return saved


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
    authority_valid_for_seconds: int | None = None,
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
        authority_valid_for_seconds=authority_valid_for_seconds,
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
    epoch_policy_selection: Any | None = None,
    resume_existing_action: bool = False,
    custody_recovery: AcquisitionCustodyRecoveryRequest | None = None,
    authority_valid_for_seconds: int | None = None,
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
    if continuation_selection is not None and epoch_policy_selection is not None:
        raise ValueError("retained_native_policy_and_current_continuation_conflict")
    if resume_existing_action and continuation_selection is None:
        raise ValueError("retained_native_resume_current_selection_required")
    if custody_recovery is not None and not resume_existing_action:
        raise ValueError("retained_native_failed_recovery_requires_explicit_resume")
    if custody_recovery is not None:
        from polisyos.runtime.http.services.acquisition_action_service import (
            AcquisitionCustodyRecoveryRequest,
        )

        custody_recovery = AcquisitionCustodyRecoveryRequest.model_validate(custody_recovery)
    if authority_valid_for_seconds is not None and continuation_selection is not None:
        raise ValueError("retained_native_validity_cannot_change_existing_acts")

    from fastapi.testclient import TestClient

    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.fabric.data_plane import resolve_live_transport_trace
    from polisyos.runtime.http.services import acquisition_surface_execution as surface_owner
    from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRouteClosureError
    from tests._helpers.control_worker import stop_embedded_control_worker
    from tests._helpers.native_derivation_retained import (
        bind_retained_native_source_app,
        load_retained_native_action_resume_checkpoint,
        load_retained_native_admission_checkpoint,
        load_retained_native_epoch_policy,
        retained_native_demo_source_case,
    )

    with retained_native_demo_source_case(base, output_root) as demo:
        trust, signers, identities = demo.trust, demo.signers, demo.identities
        claims, deployment, case = demo.claims, demo.deployment, demo.case
        if continuation_selection is not None:
            with tenant_scope(None, tenant_id=claims.tenant_id, cell_id=claims.cell_id):
                loader = (
                    load_retained_native_action_resume_checkpoint
                    if resume_existing_action
                    else load_retained_native_admission_checkpoint
                )
                checkpoint = loader(
                    case, continuation_selection, institution_key_root=base / "trust"
                )
            from types import SimpleNamespace

            case.state["appointments"].append(SimpleNamespace(config=checkpoint.epoch_config))
            case.state["retained_admission_checkpoint"] = checkpoint
        elif epoch_policy_selection is not None:
            from types import SimpleNamespace

            with tenant_scope(None, tenant_id=claims.tenant_id, cell_id=claims.cell_id):
                epoch_config = load_retained_native_epoch_policy(case, epoch_policy_selection)
            case.state["appointments"].append(SimpleNamespace(config=epoch_config))
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
        if resume_existing_action:
            return assert_retained_native_action_resume(
                served=case,
                checkpoint=case.state["retained_admission_checkpoint"],
                trust=trust,
                monkeypatch=monkeypatch,
                output_root=output_root,
                idempotency_key=idempotency_key,
                custody_recovery=custody_recovery,
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
            authority_valid_for_seconds=authority_valid_for_seconds,
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


@pytest.mark.integration
def test_native_human_decision_exposure_uses_runtime_routes_before_worker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: Any,
) -> None:
    """Exercise issuer predicates and Runtime exposure without dispatching worker or N5."""
    from fastapi.testclient import TestClient

    from polisyos.core import artifacts, canon
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http import deployment_security as security
    from polisyos.runtime.http.services import acquisition_surface_execution as surface_owner
    from polisyos.runtime.quality.joint_simulation_horizon import JointSimulationHorizonController
    from tests._helpers.acquisition_served_history import _ExternalTrust, _key_config
    from tests._helpers.control_worker import stop_embedded_control_worker
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

    claims = deployment().identity_provider.extract_user_claims(
        trust.tokens["acquisition-operator"]
    )

    def catalog_ready(**kwargs: Any) -> None:
        state["holder"] = kwargs["holder"]
        _prepare_native_epoch_owner_inputs(**kwargs)

    monkeypatch.setattr(
        surface_owner,
        "build_production_world_bank_wdi_execution_port",
        _native_fixture_port_factory(state),
    )
    try:
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
            forbid_fetch=True,
            catalog_ready=catalog_ready,
        ) as (served, holder):
            with tenant_scope(None, tenant_id=claims.tenant_id, cell_id=claims.cell_id):
                closures = adopt_served_native_leaf_quotes(
                    served, holder, quote_usd_by_node={"input-a": 0.01, "input-b": 0.02}
                )
                _adopt_native_growth_routes(served, holder, closures)
            leaf_a = next(
                row
                for row in closures
                if row.native_derivation_leaf_scope.source_node_id == "input-a"
            )
            unexpected_n5_calls: list[bool] = []

            def refuse_n5(*_args: object, **_kwargs: object) -> None:
                unexpected_n5_calls.append(True)
                raise AssertionError("pre-execution decision path started N5")

            with monkeypatch.context() as pre_execution:
                pre_execution.setattr(JointSimulationHorizonController, "run", refuse_n5)
                result = _run_signed_native_leaf_action(
                    served=served,
                    trust=trust,
                    signers=signers,
                    identities=identities,
                    institution_key_root=trust_root,
                    route_id=leaf_a.route_id,
                    idempotency_key="native-preaction-exposure-without-worker",
                    human_decision_submission_root=tmp_path / "human-decision-submissions",
                    runtime_exposure_via_http=True,
                    stop_before_execute=True,
                )
            assert not unexpected_n5_calls
            assert result["execute_status"] is None
            assert holder["fetch_calls"] == []
            assert served.semantic_kernel_entries == []

            with TestClient(served.app_factory()) as client:
                from polisyos.runtime.http.services.human_decision_contracts import (
                    HumanDecisionRecord,
                )

                control = client.app.state.runtime_container.control_service
                stop_embedded_control_worker(control)
                with tenant_scope(None, tenant_id=claims.tenant_id, cell_id=claims.cell_id):
                    reference = artifacts.artifact_ref_for_manifest(
                        control._artifact_store.get_manifest(result["human_decision_record_ref"])
                    )
                    assert reference.manifest_profile_sha256 is not None
                    assert str(reference.artifact_id) == result["human_decision_record_ref"]
                    selected_bytes = control._artifact_store.get_bytes(reference)
                    selected_record = HumanDecisionRecord.model_validate(
                        canon.from_canonical_bytes(selected_bytes)
                    )
                    assert control._control_store.get_job(result["job_id"]) is None
                response = client.get(
                    f"/api/v1/runs/{served.control_run_id}/human-decisions",
                    params={
                        "record_ref": str(reference.artifact_id),
                        "manifest_profile_sha256": reference.manifest_profile_sha256,
                    },
                    headers={
                        "Authorization": trust.authorization_header("human-reviewer-1"),
                        "X-Tenant-ID": claims.tenant_id,
                    },
                )
                assert response.status_code == 200, response.text
                record = HumanDecisionRecord.model_validate(response.json())
                assert record.record_ref.startswith("runtime://human-decisions/")
                assert record.tenant_id == claims.tenant_id
                assert record.run_id == served.control_run_id
                assert record.decision_action_exercised == "approve"
                assert record == selected_record
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


def assert_retained_native_second_leaf_completion(
    *,
    base: Path,
    output_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: Any,
    original_purchase_ref: ArtifactRef,
    owned_a_terminal_ref: ArtifactRef,
    cost_profile_refs: tuple[ArtifactRef, ...],
    epoch_policy_selection: Any,
    pending_source_node_id: str,
    pending_quote_usd: float,
    transport_calls: list[Any],
    semantic_kernel_entry_count: Callable[[], int],
    purchase_idempotency_key: str,
    admission_idempotency_key: str,
    retained_b_purchase: dict[str, Any] | None = None,
    authority_valid_for_seconds: int = 3600,
) -> dict[str, Any]:
    """Acquire or resume one retained leaf, then consume both inputs.

    Exact existing A purchase/collection/profile selectors are server fixture
    inputs. An optional exact retained B purchase selector resumes its current
    terminal without repeating provider transport. Neither path renews A's
    quote, mandate or HumanDecision. The caller supplies controlled transport
    at the actual HTTP boundary and a real N5 entry observer; it must not
    replace provider, model or numerical owners.
    """
    import json
    from decimal import Decimal

    import numpy as np
    from fastapi.testclient import TestClient

    from polisyos.core import artifacts
    from polisyos.core.contracts import load_model_input_obligation_set
    from polisyos.core.contracts.semantic_input_binding import load_resolved_input_binding_manifest
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.data_forge.read_api import catalog
    from polisyos.fabric.data_plane import resolve_live_transport_trace
    from polisyos.foundry.data_plane import load_input_bindings, replay_selected_method_input_facts
    from polisyos.runtime.http.services import acquisition_surface_execution as surface_owner
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionRouteLoopReceipt,
        VerifiedAcquisitionRouteClosure,
    )
    from polisyos.runtime.quality.acquisition_world_growth import (
        AcquisitionWorldGrowthRoute,
        NativeDerivationWorldCheckpoint,
        replay_native_derivation_input_collection,
    )
    from polisyos.runtime.quality.generation_cycle import AcquisitionOverlayReentryReceipt
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationAdmissionOwner,
    )
    from polisyos.runtime.quality.n5_candidate_content import (
        _read_recorded_generic_method_call,
        read_generic_program_graph_n5_content_observation,
    )
    from polisyos.runtime.quality.native_source_reentry_history import (
        read_native_source_reentry_history,
    )
    from tests._helpers.control_worker import stop_embedded_control_worker
    from tests._helpers.native_derivation_quotes import prepare_retained_native_leaf_quote
    from tests._helpers.native_derivation_retained import (
        _selected_retained_ref,
        load_retained_native_epoch_policy,
        retained_native_demo_source_case,
    )
    from tests.integration.runtime_quality.test_program_graph_stock_n7_served import (
        _configure_stock_provider,
    )

    with retained_native_demo_source_case(
        base,
        output_root,
        cost_profile_refs=cost_profile_refs,
        original_purchase_ref=original_purchase_ref,
    ) as demo:
        case, trust = demo.case, demo.trust
        claims, state = demo.claims, demo.case.state
        with tenant_scope(None, tenant_id=claims.tenant_id, cell_id=claims.cell_id):
            # The immutable unpaired profile asks for one inclusive step. No
            # profile, horizon or seed is rewritten to manufacture dispatch.
            assert type(case.profile.n5) is GenericCycleN5ProgramGraphRequestProfileV4
            assert case.profile.n5.horizon.steps() == (0,)
            assert case.profile.n5.replications == 1
            assert case.profile.n5.seed == 0
            selected_terminal = _selected_retained_ref(
                case.store, owned_a_terminal_ref, "runtime_quality.acquisition_route_loop_receipt"
            )
            owned_a = AcquisitionRouteLoopReceipt.model_validate(
                artifacts.load_core_json_artifact(case.store, selected_terminal)
            )
            if (
                owned_a.route_id != case.terminal.route_id
                or owned_a.terminal_outcome != "inputs_pending"
                or owned_a.native_input_collection_ref is None
                or (owned_a.source_job_id, owned_a.run_id, owned_a.tenant_id, owned_a.cell_id)
                != (case.job_id, case.control_run_id, claims.tenant_id, claims.cell_id)
            ):
                raise ValueError("retained_native_owned_leaf_terminal_mismatch")
            collection = replay_native_derivation_input_collection(
                case.store, owned_a.native_input_collection_ref
            ).collection
            old_a_inputs = tuple(collection.source_inputs)
            if len(old_a_inputs) != 1 or collection.input_closure_status != "partial":
                raise ValueError("retained_native_owned_leaf_collection_not_partial")
            new_refs = (
                cost_profile_refs
                if retained_b_purchase is not None
                else prepare_retained_native_leaf_quote(
                    case.store,
                    collection_ref=owned_a.native_input_collection_ref,
                    cost_profile_refs=cost_profile_refs,
                    source_node_id=pending_source_node_id,
                    amount_usd=pending_quote_usd,
                )
            )
            selected_b_profile_ref = None
            expected_b_terminal_ref = None
            if retained_b_purchase is not None:
                selected_b_profile_ref = _selected_retained_ref(
                    case.store,
                    ArtifactRef.model_validate(retained_b_purchase["owner_declared_profile_ref"]),
                    "runtime.quality.native_derivation_leaf_cost_profile",
                )
                expected_b_terminal_ref = _selected_retained_ref(
                    case.store,
                    ArtifactRef.model_validate(retained_b_purchase["terminal_ref"]),
                    "runtime_quality.acquisition_route_loop_receipt",
                )
                expected_b_terminal = AcquisitionRouteLoopReceipt.model_validate(
                    artifacts.load_core_json_artifact(case.store, expected_b_terminal_ref)
                )
                if artifact_ref_identity_key(selected_b_profile_ref) not in {
                    artifact_ref_identity_key(ref) for ref in new_refs
                }:
                    raise ValueError("retained_native_b_profile_not_in_selected_cost_profiles")
            selected_config = case.configuration.native_derivation_routes[0]
            state["holder"]["configuration"] = AcquisitionWorldGrowthConfig.model_validate(
                {
                    **case.configuration.model_dump(mode="python"),
                    "native_derivation_routes": (
                        selected_config.model_copy(
                            update={
                                "owner_declared_cost_profile_refs": new_refs,
                            }
                        ),
                    ),
                }
            )
            config_path = output_root / "server-cost-profile-selection.json"
            selection_record = {
                "cost_profile_refs": [ref.model_dump(mode="json") for ref in new_refs],
                "original_purchase_ref": original_purchase_ref.model_dump(mode="json"),
                "owned_a_terminal_ref": owned_a_terminal_ref.model_dump(mode="json"),
            }
            if retained_b_purchase is not None:
                selection_record["retained_b_purchase"] = retained_b_purchase
            config_path.write_text(json.dumps(selection_record, sort_keys=True) + "\n")
            policy_config = load_retained_native_epoch_policy(case, epoch_policy_selection)
            from types import SimpleNamespace

            state["appointments"].append(SimpleNamespace(config=policy_config))
            source = GenerationSourceRepository(case.store).load(
                case.source.n4_source_ref,
                run_id=case.source.source_generation_run_id,
                expected_run_id=case.control_run_id,
                expected_job_id=case.job_id,
                expected_tenant_id=claims.tenant_id,
                expected_cell_id=claims.cell_id,
                context_job_ref=case.source.context_job_ref,
                profile_ref=case.compiled.generic_cycle_simulation_handoff.profile_ref,
            )
            if source.trinity_bundle is None:
                raise ValueError("retained_native_original_trinity_missing")
            model_id = _configure_stock_provider(
                controlled_candidate_gateway,
                problem=case.compiled.design_problem,
                trinity=source.trinity_bundle,
                evidence_root=output_root / "controlled-n4",
            )
            controlled_candidate_gateway.admit_compiled_problem(case.compiled.design_problem)
            raw_request = artifacts.load_core_json_artifact(case.store, case.source_payload_ref)
            if raw_request.get("llm_models") != [model_id]:
                raise ValueError("retained_native_controlled_model_alias_mismatch")
        monkeypatch.setenv("POLISYOS_RUNTIME_EXECUTION_PROFILE", "development")
        monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
        monkeypatch.setenv("POLISYOS_CONTROL_SQLITE_PATH", str(case.control_database))
        monkeypatch.setenv("POLISYOS_CACHE_HOME", str(base / "runtime-cache"))
        monkeypatch.setenv("POLISYOS_TEST_RETAIN_NATIVE_EPOCH_SIGNER", "1")
        monkeypatch.setattr(
            surface_owner,
            "build_production_world_bank_wdi_execution_port",
            _native_fixture_port_factory(state),
        )
        before_calls = tuple(transport_calls)
        before_kernels = semantic_kernel_entry_count()
        a_trace = resolve_live_transport_trace(case.attempt.evidence.raw_evidence_ref)
        a_journal = Path(case.attempt.evidence.request_ref.journal_path)
        a_journal_before = a_journal.read_bytes()
        retained_purchase = None
        with TestClient(case.app_factory()) as client:
            control = client.app.state.runtime_container.control_service
            stop_embedded_control_worker(control)
            action_service = client.app.state.runtime_container.acquisition_action_service
            with tenant_scope(None, tenant_id=claims.tenant_id, cell_id=claims.cell_id):
                route_loop = action_service._route_loop(
                    tenant_id=claims.tenant_id,
                    cell_id=claims.cell_id,
                )
                if retained_b_purchase is None:
                    routes = route_loop.resolve_native_derivation_leaf_routes(
                        run_id=case.control_run_id
                    )
                    chosen = tuple(
                        row
                        for row in routes
                        if (
                            getattr(row, "native_derivation_leaf_scope", None) is not None
                            and row.native_derivation_leaf_scope.source_node_id
                            == pending_source_node_id
                        )
                    )
                    if len(chosen) != 1:
                        raise ValueError("retained_native_pending_costed_route_not_unique")
                    leaf = chosen[0]
                else:
                    expected_route_id = retained_b_purchase["route_id"]
                    expected_job_id = retained_b_purchase["job_id"]
                    job = control._control_store.get_job(expected_job_id)
                    if (
                        job is None
                        or job.kind != "acquisition"
                        or job.run_id != case.control_run_id
                        or job.state != "completed"
                    ):
                        raise ValueError("retained_native_b_purchase_job_not_completed")
                    outcome = control.acquisition_route_sink.current_action_outcome(
                        tenant_id=claims.tenant_id,
                        cell_id=claims.cell_id,
                        run_id=case.control_run_id,
                        source_job_id=case.job_id,
                        route_id=expected_route_id,
                    )
                    if outcome is None:
                        raise ValueError("retained_native_b_purchase_head_missing")
                    head = outcome.head
                    if (
                        head.job_id != expected_job_id
                        or head.route_id != expected_route_id
                        or head.action_generation != retained_b_purchase["action_generation"]
                        or head.head_generation != retained_b_purchase["head_generation"]
                        or head.receipt_phase != "terminal"
                        or head.recovery_state != "complete"
                        or head.receipt_manifest_profile_sha256
                        != expected_b_terminal_ref.manifest_profile_sha256
                        or str(head.receipt_ref) != str(expected_b_terminal_ref.artifact_id)
                        or outcome.latest_receipt != expected_b_terminal
                        or outcome.latest_receipt.terminal_outcome != "quarantined_no_growth"
                        or outcome.latest_receipt.route_id != expected_route_id
                        or outcome.latest_receipt.source_job_id != case.job_id
                        or outcome.latest_receipt.job_id != expected_job_id
                        or outcome.latest_receipt.action_generation != head.action_generation
                        or (
                            outcome.latest_receipt.tenant_id,
                            outcome.latest_receipt.cell_id,
                            outcome.latest_receipt.run_id,
                        )
                        != (claims.tenant_id, claims.cell_id, case.control_run_id)
                        or outcome.latest_receipt.owner_declared_profile_ref
                        != selected_b_profile_ref
                        or outcome.executing_phase is None
                        or outcome.executing_phase.owner_declared_profile_ref
                        != selected_b_profile_ref
                    ):
                        raise ValueError("retained_native_b_purchase_head_binding_mismatch")
                    leaf = route_loop.resolve_current_route(
                        run_id=case.control_run_id,
                        route_id=expected_route_id,
                        action_job_id=expected_job_id,
                    )
                    if type(leaf) is not VerifiedAcquisitionRouteClosure:
                        raise ValueError("retained_native_b_current_route_unverified")
                    reconciled_outcome = control.acquisition_route_sink.current_action_outcome(
                        tenant_id=claims.tenant_id,
                        cell_id=claims.cell_id,
                        run_id=case.control_run_id,
                        source_job_id=case.job_id,
                        route_id=expected_route_id,
                    )
                    if (
                        reconciled_outcome is None
                        or reconciled_outcome.head != head
                        or reconciled_outcome.latest_receipt != expected_b_terminal
                        or leaf.route_id != expected_route_id
                        or leaf.owner_declared_profile_ref != selected_b_profile_ref
                        or leaf.native_derivation_leaf_scope is None
                        or leaf.native_derivation_leaf_scope.source_node_id
                        != pending_source_node_id
                    ):
                        raise ValueError("retained_native_b_current_route_binding_mismatch")
                    retained_purchase = {
                        "job_id": head.job_id,
                        "head": head,
                        "terminal": outcome.latest_receipt,
                        "closure": leaf,
                    }
        # A distinct B route uses the existing fixture's same declared scope
        # and independent time/facet evidence; no A action permit is copied.
        route = AcquisitionWorldGrowthRoute.model_validate(
            {
                **case.attempt.selection.model_dump(mode="python"),
                "route_id": leaf.route_id,
                "epoch_id": case.attempt.selection.epoch_id + 1,
                "design_problem_ref": leaf.design_problem_ref,
            }
        )
        state["holder"]["configuration"] = AcquisitionWorldGrowthConfig.model_validate(
            {
                **state["holder"]["configuration"].model_dump(mode="python"),
                "routes": (*case.configuration.routes, route),
            }
        )
        if retained_purchase is None:
            purchase = _run_signed_native_leaf_action(
                served=case,
                trust=trust,
                signers=demo.signers,
                identities=demo.identities,
                institution_key_root=base / "trust",
                route_id=leaf.route_id,
                idempotency_key=purchase_idempotency_key,
                authority_valid_for_seconds=authority_valid_for_seconds,
                human_decision_submission_root=output_root / "human-decision-submissions",
                action_checkpoint_root=output_root / "action-checkpoints",
                runtime_exposure_via_http=True,
            )
        else:
            purchase = retained_purchase
        assert purchase["terminal"].terminal_outcome == "quarantined_no_growth"
        assert len(transport_calls) == len(before_calls) + (
            0 if retained_b_purchase is not None else 1
        )
        assert semantic_kernel_entry_count() == before_kernels
        with (
            _live_native_fixture_bridge(served=case, state=state) as bridge,
            tenant_scope(None, tenant_id=claims.tenant_id, cell_id=claims.cell_id),
        ):
            _appoint_exact_native_epoch_policy(
                state=state,
                bridge=bridge,
                institution_store=case.store,
                closure=purchase["closure"],
                root=output_root / "new-b-epoch-institution",
            )
        b_attempt = state["paid_attempt"]
        b_trace = resolve_live_transport_trace(b_attempt.evidence.raw_evidence_ref)
        b_journal = Path(b_attempt.evidence.request_ref.journal_path)
        journals_after_purchase = {path: path.read_bytes() for path in {a_journal, b_journal}}
        after_purchase_calls = tuple(transport_calls)
        completed = _run_signed_native_leaf_action(
            served=case,
            trust=trust,
            signers=demo.signers,
            identities=demo.identities,
            institution_key_root=base / "trust",
            route_id=leaf.route_id,
            idempotency_key=admission_idempotency_key,
            authority_valid_for_seconds=authority_valid_for_seconds,
            human_decision_submission_root=output_root / "human-decision-submissions",
            action_checkpoint_root=output_root / "action-checkpoints",
            runtime_exposure_via_http=True,
        )
        if retained_b_purchase is not None:
            paid = completed["closure"].prior_paid_input_admission
            assert paid is not None
            assert paid.original_action_job_id == purchase["job_id"]
            assert artifact_ref_identity_key(paid.terminal_ref) == artifact_ref_identity_key(
                expected_b_terminal_ref
            )
        terminal = completed["terminal"]
        assert terminal.terminal_outcome == "reentry_completed"
        assert terminal.reentry_receipt_ref is not None
        assert completed["job_id"] != purchase["job_id"]
        assert tuple(transport_calls) == after_purchase_calls
        assert semantic_kernel_entry_count() - before_kernels == 1
        n4_receipts = {
            path.relative_to(output_root / "controlled-n4").as_posix(): path.read_bytes()
            for path in (output_root / "controlled-n4").rglob("receipt.json")
        }
        assert n4_receipts
        after_completion_kernels = semantic_kernel_entry_count()
        with TestClient(case.app_factory()) as client:
            control = client.app.state.runtime_container.control_service
            stop_embedded_control_worker(control)
            detail = client.get(
                f"/api/v1/runs/{case.core_run_id}",
                headers={
                    "Authorization": trust.authorization_header("acquisition-operator"),
                    "X-Tenant-ID": claims.tenant_id,
                },
            )
            assert detail.status_code == 200, detail.text
            generic = detail.json()["run"]["generic_cycle_simulation"]
            history = generic["acquisition_history"]
            rows = [row for row in history if row.get("action_job_id") == completed["job_id"]]
            assert len(rows) == 1
            assert rows[0]["terminal_outcome"] == "reentry_completed"
            assert rows[0]["n5_owner_join_status"] == "resolved"
            assert rows[0]["publication_authority"] is False
            completed_history_row = rows[0]
            with tenant_scope(None, tenant_id=claims.tenant_id, cell_id=claims.cell_id):
                restarted_outcome = control.acquisition_route_sink.current_action_outcome(
                    tenant_id=claims.tenant_id,
                    cell_id=claims.cell_id,
                    run_id=case.control_run_id,
                    source_job_id=case.job_id,
                    route_id=leaf.route_id,
                )
            assert restarted_outcome is not None
            assert restarted_outcome.head == completed["head"]
            assert restarted_outcome.latest_receipt == terminal
            actual_collection = replay_native_derivation_input_collection(
                case.store, ArtifactRef.model_validate(rows[0]["native_input_collection_ref"])
            ).collection
            assert actual_collection.input_closure_status == "inputs_complete"
            assert actual_collection.pending_actions == ()
            by_node = {row.source_node_id: row for row in actual_collection.source_inputs}
            assert by_node[old_a_inputs[0].source_node_id] == old_a_inputs[0]
            assert set(by_node) == {old_a_inputs[0].source_node_id, pending_source_node_id}
            for row in actual_collection.source_inputs:
                _record, replayed, _selection = catalog.replay_selected_scoped_measurement_facts(
                    case.store, row.occurrence_ref
                )
                expected = (
                    Decimal("-0.03")
                    if row.source_node_id == old_a_inputs[0].source_node_id
                    else Decimal("200000000000")
                )
                assert replayed.canonical_value == expected
            with tenant_scope(None, tenant_id=claims.tenant_id, cell_id=claims.cell_id):
                live_store = control._artifact_store
                result_row = completed_history_row
                world_checkpoint = NativeDerivationWorldCheckpoint.model_validate(
                    artifacts.load_core_json_artifact(
                        live_store,
                        ArtifactRef.model_validate(result_row["native_world_checkpoint_ref"]),
                    )
                )
                original_bindings = load_input_bindings(
                    live_store, world_checkpoint.input_bindings_ref
                )
                assert original_bindings.selected_method_inputs is not None
                (original_argument,) = original_bindings.selected_method_inputs
                assert original_argument.canonical_value == Decimal("-6000000000")
                historical_owner = GenericCycleSimulationAdmissionOwner(
                    profiles=(), store=live_store
                )
                historical_owner.bind_native_world_history(
                    control_store=control._control_store,
                    event_log=control._diagnostic_event_log,
                )
                verified = read_native_source_reentry_history(
                    store=live_store,
                    events=control._diagnostic_event_log,
                    owner=historical_owner,
                    input_ref=ArtifactRef.model_validate(result_row["n5_input_ref"]),
                    source_generation_run=completed["closure"].generation_run,
                    receipt=AcquisitionOverlayReentryReceipt.model_validate(
                        artifacts.load_core_json_artifact(
                            live_store,
                            ArtifactRef.model_validate(result_row["reentry_receipt_ref"]),
                        )
                    ),
                    expected_action_job_id=completed["job_id"],
                    expected_action_generation=completed["head"].action_generation,
                    expected_source_job_id=case.job_id,
                    expected_route_id=leaf.route_id,
                    expected_run_id=case.control_run_id,
                    expected_tenant_id=claims.tenant_id,
                    expected_cell_id=claims.cell_id,
                )
                actual_result, actual_request = verified.result.result, verified.result.request
                assert type(verified.input_record.n5) is GenericCycleN5ProgramGraphRequestProfileV4
                assert actual_request.horizon.steps() == (0,)
                assert actual_request.seed == case.profile.n5.seed == 0
                assert actual_request.replications == 1
                assert actual_request.program_graph_comparator_profile is None
                assert actual_request.comparator_profile is None
                assert len(actual_request.intervention_atoms) == 1
                (actual_plan,) = actual_request.engine_plan
                selected_bindings_ref = actual_plan.program_semantic_input_bindings_ref
                assert selected_bindings_ref is not None
                selected_bindings = load_input_bindings(live_store, selected_bindings_ref)
                selected_manifest = load_resolved_input_binding_manifest(
                    live_store, selected_bindings.resolved_binding_manifest_ref
                )
                selected_set, _ = load_model_input_obligation_set(
                    live_store, selected_manifest.model_input_obligation_set_ref
                )
                facts = replay_selected_method_input_facts(
                    live_store,
                    input_bindings_ref=selected_bindings_ref,
                    expected_invocation=selected_set.invocation,
                )
                (actual_argument,) = facts.records
                assert actual_argument.canonical_value == Decimal("-6000000000")
                assert actual_argument.slot_id == original_argument.slot_id
                selected_value = facts.values[actual_argument.slot_id]
                assert selected_value.size == 1
                assert float(selected_value.item()) == -6_000_000_000.0
                observation = read_generic_program_graph_n5_content_observation(
                    actual_result,
                    input_ref=ArtifactRef.model_validate(result_row["n5_input_ref"]),
                    expected_request=actual_request,
                    current_method_input_bindings_ref=(
                        verified.result.initial_method_input.current_method_input_bindings_ref
                        if verified.result.initial_method_input is not None
                        else None
                    ),
                    store=live_store,
                )
                assert observation.completion.status == "recomputed"
                assert len(observation.completion.planned_units) == 1
                assert (
                    observation.completion.completed_units == observation.completion.planned_units
                )
                (physical_work,) = actual_result.physical_work_observations
                assert physical_work.status == "completed"
                assert actual_result.diagnostics["physical_work_capture_status"] == "observed"
                assert (
                    actual_result.diagnostics["physical_work_usd_cost_status"] == "not_established"
                )
                assert len(observation.steps) == 1
                (method_step,) = observation.steps
                assert method_step.step == 0
                argument_calls = [
                    (payload, argument)
                    for call in method_step.calls
                    for payload in (_read_recorded_generic_method_call(call),)
                    for argument in payload["arguments"]
                    if argument["source_slot"] == actual_argument.slot_id
                ]
                assert len(argument_calls) == 1
                payload, actual_call_argument = argument_calls[0]
                assert payload["step"] == 0
                assert actual_call_argument["value_sha256"] == actual_argument.value_sha256
                delivered = np.frombuffer(
                    bytes.fromhex(actual_call_argument["value_hex"]),
                    dtype=np.dtype(actual_call_argument["dtype"]),
                ).reshape(actual_call_argument["shape"])
                assert delivered.size == 1
                assert float(delivered.item()) == -6_000_000_000.0
        with TestClient(case.app_factory()) as client:
            control = client.app.state.runtime_container.control_service
            stop_embedded_control_worker(control)
            repeated, _resource = trust.post(
                client,
                f"/api/v1/runs/{case.control_run_id}/acquisition-routes/{leaf.route_id}/execute",
                completed["request"].model_dump(mode="json"),
                route="/api/v1/runs/{run_id}/acquisition-routes/{route_id}/execute",
            )
            assert repeated.status_code in {200, 202}, repeated.text
            assert repeated.json()["job_id"] == completed["job_id"]
            exact_job = control._control_store.get_job(completed["job_id"])
            assert exact_job is not None and exact_job.state == "completed"
            assert exact_job.progress == completed["progress"]
            with tenant_scope(None, tenant_id=claims.tenant_id, cell_id=claims.cell_id):
                exact_outcome = control.acquisition_route_sink.current_action_outcome(
                    tenant_id=claims.tenant_id,
                    cell_id=claims.cell_id,
                    run_id=case.control_run_id,
                    source_job_id=case.job_id,
                    route_id=leaf.route_id,
                )
            assert exact_outcome is not None and exact_outcome.head == completed["head"]
            assert exact_outcome.latest_receipt == terminal
            detail_again = client.get(
                f"/api/v1/runs/{case.core_run_id}",
                headers={
                    "Authorization": trust.authorization_header("acquisition-operator"),
                    "X-Tenant-ID": claims.tenant_id,
                },
            )
            assert detail_again.status_code == 200, detail_again.text
            rows_again = [
                row
                for row in detail_again.json()["run"]["generic_cycle_simulation"][
                    "acquisition_history"
                ]
                if row.get("action_job_id") == completed["job_id"]
            ]
            assert rows_again == [completed_history_row]
        assert tuple(transport_calls) == after_purchase_calls
        assert semantic_kernel_entry_count() == after_completion_kernels
        assert {
            path.relative_to(output_root / "controlled-n4").as_posix(): path.read_bytes()
            for path in (output_root / "controlled-n4").rglob("receipt.json")
        } == n4_receipts
        # The connector may append B to the same physical journal. Every old
        # A byte remains an exact prefix; a distinct A journal cannot change.
        if a_journal == b_journal:
            assert a_journal.read_bytes().startswith(a_journal_before)
        else:
            assert a_journal.read_bytes() == a_journal_before
        assert all(path.read_bytes() == data for path, data in journals_after_purchase.items())
        assert resolve_live_transport_trace(case.attempt.evidence.raw_evidence_ref) == a_trace
        assert resolve_live_transport_trace(b_attempt.evidence.raw_evidence_ref) == b_trace
        return {
            "purchase_job_id": purchase["job_id"],
            "admission_job_id": completed["job_id"],
            "reentry_receipt_ref": terminal.reentry_receipt_ref,
            "native_input_collection_ref": rows[0]["native_input_collection_ref"],
            "new_provider_calls": len(transport_calls) - len(before_calls),
            "kernel_entries": after_completion_kernels - before_kernels,
            "physical_work_units": 1,
            "semantic_steps": [0],
            "derived_method_argument": "-6000000000",
            "actual_method_argument_value_sha256": actual_argument.value_sha256,
            "server_cost_profile_refs": [ref.model_dump(mode="json") for ref in new_refs],
        }


@pytest.mark.integration
def test_retained_native_second_leaf_completes_and_restart_reuses_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: Any,
) -> None:
    """Run the explicitly admitted retained-A/full-B case through actual owners.

    This selector mutates only its explicitly selected test-owned retained case.
    The server fixture selection is not an HTTP caller's authority assertion.
    Resource/source admission is required before enabling it.
    """
    import json
    import os

    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationHorizonController,
    )
    from tests._helpers.acquisition_production import intercepted_wdi_transport
    from tests._helpers.candidate_reentry_timing import _TimingObserver
    from tests._helpers.lane01_wdi_profiles import fixture_wdi_response
    from tests._helpers.native_derivation_retained import RetainedNativeEpochPolicySelection

    path = os.environ.get("POLISYOS_NATIVE_SECOND_LEAF_SELECTOR")
    if not path:
        pytest.skip("explicit retained A/source/quote and effect admission required")
    selected = json.loads(Path(path).read_text())
    if type(selected) is not dict:
        raise ValueError("retained_native_second_leaf_selector_untyped")
    expected = {
        "base",
        "original_purchase_ref",
        "owned_a_terminal_ref",
        "cost_profile_refs",
        "epoch_admission_evidence_ref",
        "epoch_public_key_path",
        "pending_source_node_id",
        "pending_quote_usd",
        "pending_provider_profile",
        "purchase_idempotency_key",
        "admission_idempotency_key",
    }
    retained_b_purchase = selected.get("retained_b_purchase")
    expected_retained_b_purchase = {
        "job_id",
        "route_id",
        "action_generation",
        "head_generation",
        "terminal_ref",
        "owner_declared_profile_ref",
    }
    if retained_b_purchase is None:
        if set(selected) != expected:
            raise ValueError("retained_native_second_leaf_selector_fields_invalid")
    elif (
        set(selected) != expected | {"retained_b_purchase"}
        or type(retained_b_purchase) is not dict
        or set(retained_b_purchase) != expected_retained_b_purchase
        or type(retained_b_purchase["job_id"]) is not str
        or type(retained_b_purchase["route_id"]) is not str
        or type(retained_b_purchase["action_generation"]) is not int
        or type(retained_b_purchase["head_generation"]) is not int
        or retained_b_purchase["action_generation"] < 1
        or retained_b_purchase["head_generation"] < 1
    ):
        raise ValueError("retained_native_second_leaf_selector_fields_invalid")
    if selected["purchase_idempotency_key"] == selected["admission_idempotency_key"]:
        raise ValueError("retained_native_second_leaf_action_identities_not_distinct")
    if retained_b_purchase is not None:
        retained_b_terminal = ArtifactRef.model_validate(retained_b_purchase["terminal_ref"])
        retained_b_profile = ArtifactRef.model_validate(
            retained_b_purchase["owner_declared_profile_ref"]
        )
        if (
            retained_b_terminal.kind != "runtime_quality.acquisition_route_loop_receipt"
            or retained_b_terminal.manifest_profile_sha256 is None
            or retained_b_profile.kind != "runtime.quality.native_derivation_leaf_cost_profile"
            or retained_b_profile.manifest_profile_sha256 is None
        ):
            raise ValueError("retained_native_second_leaf_purchase_selector_unselected")
    provider_profile = CandidateWDIProfile(**selected["pending_provider_profile"])

    def response_factory(_method: str, url: str, params: Any) -> bytes:
        if retained_b_purchase is not None:
            raise AssertionError("retained_native_b_purchase_must_not_refetch")
        assert provider_profile.indicator_id in url, url
        assert params["date"] in {
            str(provider_profile.year),
            f"{provider_profile.year}:{provider_profile.year}",
        }
        return fixture_wdi_response(provider_profile)

    transport_calls = intercepted_wdi_transport(
        monkeypatch, allow_loopback=True, response_factory=response_factory
    )
    output = tmp_path / "native-second-leaf"
    output.mkdir()
    # Observe the unmodified kernel code; neither a wrapper nor a replacement
    # producer is installed. The canonical timing helper owns setup and unwind.
    timing = _TimingObserver(
        {
            "semantic_kernel": JointSimulationHorizonController._run_semantic_program_graph_horizon.__code__
        },
        output / "kernel-observation.json",
        profile="native_second_leaf",
    )
    if not timing.enable():
        raise RuntimeError(timing.reason or "native_fixture_kernel_observer_unavailable")
    try:
        result = assert_retained_native_second_leaf_completion(
            base=Path(selected["base"]),
            output_root=output,
            monkeypatch=monkeypatch,
            controlled_candidate_gateway=controlled_candidate_gateway,
            original_purchase_ref=ArtifactRef.model_validate(selected["original_purchase_ref"]),
            owned_a_terminal_ref=ArtifactRef.model_validate(selected["owned_a_terminal_ref"]),
            cost_profile_refs=tuple(
                ArtifactRef.model_validate(ref) for ref in selected["cost_profile_refs"]
            ),
            epoch_policy_selection=RetainedNativeEpochPolicySelection(
                epoch_admission_evidence_ref=ArtifactRef.model_validate(
                    selected["epoch_admission_evidence_ref"]
                ),
                epoch_public_key_path=Path(selected["epoch_public_key_path"]),
            ),
            pending_source_node_id=selected["pending_source_node_id"],
            pending_quote_usd=selected["pending_quote_usd"],
            transport_calls=transport_calls,
            semantic_kernel_entry_count=lambda: timing.snapshot()["targets"]["semantic_kernel"][
                "calls"
            ],
            purchase_idempotency_key=selected["purchase_idempotency_key"],
            admission_idempotency_key=selected["admission_idempotency_key"],
            retained_b_purchase=retained_b_purchase,
        )
        (output / "result.json").write_text(json.dumps(result, sort_keys=True) + "\n")
    finally:
        timing.cleanup()
        timing.flush()
    assert timing.cleanup_status == "complete"
    assert timing.observer_errors == 0
