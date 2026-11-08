"""Selected Foundry input fixture for the ProgramGraph tax-subsidy oracle.

All source rows are test-owned synthetic inputs. This helper proves only that
the selected Foundry ProgramGraph consumes a persisted opening-balance input;
it does not establish a production source, fiscal correspondence, or authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from polisyos.core.artifacts import ArtifactRef, CoreJSONArtifactStore, FileSystemCAS


INCOME_VALUES = (100, 200)
SUBSIDY_RATE = 0.125


@dataclass(frozen=True, slots=True)
class ProgramGraphTaxSubsidyInputCase:
    """Persisted test inputs and the selected compiled ProgramGraph."""

    store: Any
    store_root: Path
    source_ref: Any
    data_snapshot_ref: Any
    registry_bundle_ref: Any
    input_bindings_ref: Any
    bound_state_snapshot_ref: Any
    policy_candidate_ref: Any
    trinity_ref: Any
    compile_report_ref: ArtifactRef
    exec_plan_ref: Any
    program_graph_ref: Any
    model_input_port_declaration_ref: ArtifactRef | None
    _owns_store: bool = True

    def close(self) -> None:
        """Close the fixture CAS after the fresh reader has finished."""
        if self._owns_store:
            close = getattr(self.store, "close", None)
            if callable(close):
                close()


@dataclass(frozen=True, slots=True)
class ProgramGraphTaxSubsidyExecution:
    """Selected and persisted public Foundry execution result."""

    simulation_result_ref: Any


def prepare_program_graph_tax_subsidy_input_case(
    tmp_path: Path,
    *,
    opening_balance_usd: float | None,
    mechanism_start_step: int = 0,
    mechanism_duration_steps: int = 1,
    model_input_port_declaration_builder: Callable[[CoreJSONArtifactStore], ArtifactRef]
    | None = None,
    store: FileSystemCAS | None = None,
    snapshot_id: str | None = None,
) -> ProgramGraphTaxSubsidyInputCase:
    """Compile and bind a real candidate ProgramGraph against selected fixture data.

    ``opening_balance_usd=None`` omits the stock source and its binding entirely.
    The model-input preflight can reuse that case to prove the graph's actual
    prestate dependency is absent, without inserting a test-created requirement.
    A caller-supplied store retains its existing ownership and lifetime.
    `snapshot_id` opts into the synthetic world fixture's explicit version.
    """
    from decimal import Decimal

    from polisyos.common.async_tools import run_coro_sync
    from polisyos.core.artifacts import (
        ArtifactRef,
        ensure_ir_artifact_store,
        load_core_json_artifact,
    )
    from polisyos.core.artifacts.async_store import ensure_async_artifact_store
    from polisyos.core.artifacts.manifest import SchemaInfo, input_ref_from_artifact_ref
    from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
    from polisyos.core.canon import CanonSpec
    from polisyos.core.contracts.fabric import DataSnapshot
    from polisyos.core.contracts.foundry import (
        CompileRequest,
        FoundryInputBindingRule,
        FoundryInputBindingsRef,
    )
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.fabric.data_plane.orchestrator import (
        _build_snapshot_from_evidence_async,
        _ingestion_snapshot_write_options,
    )
    from polisyos.fabric.evidence import build_evidence_bundle, persist_evidence_bundle
    from polisyos.foundry.compile.api import compile as compile_foundry
    from polisyos.foundry.data_plane import build_input_bindings
    from polisyos.ir.governance.policy_spec import InterventionSpec, MechanismBinding, PolicySpec
    from polisyos.ir.governance.problem_frame import (
        ObjectiveSpec,
        ProblemDomain,
        ProblemFrame,
    )
    from polisyos.ir.governance.schedule import ScheduleSpec
    from polisyos.ir.governance.selector_expr import SelectorPredicate
    from polisyos.ir.model_layer.model_spec import (
        MODEL_SPEC_INPUT_PORT_DECLARATION_VERSION,
        ModelInputPortDeclarationRef,
        ModelSpec,
    )
    from polisyos.ir.model_layer.types import OptimizationDirection, SelectorOperator
    from polisyos.ir.trinity import TrinityBundle, persist_trinity_bundle_artifact
    from polisyos.scientist.policy_design.schema import (
        PolicyCandidateSchema,
        TargetPopulationSpec,
        persist_policy_candidate_schema,
    )

    owns_store = store is None
    if store is None:
        store = FileSystemCAS(tmp_path / "cas")
    try:
        payload: dict[str, Any] = {"agents": {"income": list(INCOME_VALUES)}}
        if opening_balance_usd is not None:
            payload["government_balance"] = opening_balance_usd
        source_ref = store.put_json(
            payload,
            PutOptions(
                kind="tests.program_graph.tax_subsidy_input",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.tests.ProgramGraphTaxSubsidyInput",
                    version="1.0",
                ),
            ),
            return_selected_profile=True,
        )
        evidence_ref = persist_evidence_bundle(
            store,
            build_evidence_bundle(
                sources=[source_ref],
                notes=["Synthetic data for a bounded Foundry input-consumption test."],
            ),
            return_selected_profile=True,
        )
        data_snapshot_ref = run_coro_sync(
            _build_snapshot_from_evidence_async(
                store=ensure_async_artifact_store(store),
                evidence_ref=evidence_ref,
                datasets_fetched=1,
                source="program_graph_tax_subsidy_test_fixture",
            )
        )
        if data_snapshot_ref is None or data_snapshot_ref.manifest_profile_sha256 is None:
            raise AssertionError("program_graph_input_snapshot_not_selected")
        if snapshot_id is not None:
            snapshot = DataSnapshot.model_validate(
                load_core_json_artifact(store, data_snapshot_ref)
            )
            snapshot = snapshot.model_copy(
                update={"stats": {**snapshot.stats, "snapshot_id": snapshot_id}}
            )
            data_snapshot_ref = store.put_json(
                snapshot,
                _ingestion_snapshot_write_options(snapshot),
                canon_spec=CanonSpec(forbid_floats=False),
                return_selected_profile=True,
            )

        registry_bundle = build_default_registry_bundle(store, return_selected_profile=True)
        rules = [
            FoundryInputBindingRule(
                binding_id="fixture-agents-income",
                source_path="agents.income",
                target_slot_id="agents.income",
            )
        ]
        if opening_balance_usd is not None:
            rules.append(
                FoundryInputBindingRule(
                    binding_id="fixture-government-opening-balance",
                    source_path="government_balance",
                    target_slot_id="government.balance",
                )
            )
        binding_result = build_input_bindings(
            store,
            data_snapshot_ref=data_snapshot_ref,
            registry_bundle_ref=registry_bundle.bundle_ref,
            rules=rules,
            return_selected_profile=True,
        )

        problem_frame = ProblemFrame(
            problem_id="program_graph_tax_subsidy_input",
            domain=ProblemDomain.FISCAL,
            objectives=[
                ObjectiveSpec(
                    objective_id="opening_balance",
                    metric_id="government_balance",
                    direction=OptimizationDirection.MAXIMIZE,
                )
            ],
        )
        policy_spec = PolicySpec(
            policy_id="program_graph_tax_subsidy_input",
            interventions=[
                InterventionSpec(
                    intervention_id="fixture_subsidy",
                    kind="tax_subsidy",
                    target=SelectorPredicate(
                        field="id",
                        operator=SelectorOperator.EQUALS,
                        value="all",
                    ),
                    schedule=ScheduleSpec(
                        start_step=mechanism_start_step, duration_steps=mechanism_duration_steps
                    ),
                    params={"rate": Decimal(str(SUBSIDY_RATE))},
                )
            ],
            mechanism_bindings=[
                MechanismBinding(
                    binding_id="fixture_subsidy_binding",
                    mechanism_id="tax_subsidy",
                    intervention_ids=["fixture_subsidy"],
                )
            ],
        )
        model_spec = ModelSpec(
            model_id="program_graph_tax_subsidy_input",
            data_snapshot_ref=str(data_snapshot_ref.artifact_id),
            registry_bundle_ref=str(registry_bundle.bundle_ref.artifact_id),
        )
        model_input_port_declaration_ref = None
        if model_input_port_declaration_builder is not None:
            model_input_port_declaration_ref = model_input_port_declaration_builder(store)
            model_spec = ModelSpec.model_validate(
                {
                    **model_spec.model_dump(mode="python"),
                    "schema_version": MODEL_SPEC_INPUT_PORT_DECLARATION_VERSION,
                    "model_input_port_declaration_ref": ModelInputPortDeclarationRef.model_validate(
                        model_input_port_declaration_ref.model_dump(mode="python")
                    ),
                }
            )
        trinity = TrinityBundle(
            problem_frame=problem_frame,
            policy_spec=policy_spec,
            model_spec=model_spec,
        )
        policy_candidate_ref = persist_policy_candidate_schema(
            store,
            PolicyCandidateSchema(
                candidate_id="program_graph_tax_subsidy_input",
                trinity_bundle=trinity,
                target_population=TargetPopulationSpec(
                    population_id="fixture_agents",
                    description="Synthetic agent rows for a candidate-only executor test.",
                ),
                implementation_notes=["Test-only numerical oracle; no empirical claim."],
            ),
            inputs=[
                input_ref_from_artifact_ref(
                    data_snapshot_ref,
                    role="world_model_data_snapshot",
                ),
                input_ref_from_artifact_ref(
                    registry_bundle.bundle_ref,
                    role="world_model_registry",
                ),
            ],
            return_selected_profile=True,
        )
        trinity_inputs = [
            input_ref_from_artifact_ref(policy_candidate_ref, role="policy_candidate")
        ]
        if model_input_port_declaration_ref is not None:
            trinity_inputs.append(
                input_ref_from_artifact_ref(
                    model_input_port_declaration_ref, role="model_input_port_declaration"
                )
            )
        selected_trinity_ref = persist_trinity_bundle_artifact(
            ensure_ir_artifact_store(store),
            trinity,
            inputs=trinity_inputs,
        )
        trinity_ref = ArtifactRef.model_validate(selected_trinity_ref.model_dump(mode="python"))
        if trinity_ref.manifest_profile_sha256 is None:
            raise AssertionError("program_graph_fixture_selected_trinity_view_missing")
        candidate_edges = [
            item
            for item in store.get_manifest(trinity_ref).inputs
            if item.role == "policy_candidate"
        ]
        if candidate_edges != [
            input_ref_from_artifact_ref(policy_candidate_ref, role="policy_candidate")
        ]:
            raise AssertionError("program_graph_fixture_candidate_lineage_missing")
        compiled = compile_foundry(
            store,
            CompileRequest(
                input_kind="trinity",
                policy_ref=trinity_ref,
                registry_bundle_ref=registry_bundle.bundle_ref,
                return_selected_profile=True,
            ),
        )
        if not compiled.ok or compiled.exec_plan_ref is None or compiled.compile_report_ref is None:
            raise AssertionError(f"program_graph_compile_failed: {compiled.notes!r}")
        graph_refs = [item.ref for item in compiled.derived_refs if item.role == "program_graph"]
        if len(graph_refs) != 1:
            raise AssertionError("program_graph_compile_selected_graph_missing")
        exec_plan_ref = compiled.exec_plan_ref
        compile_report_ref = ArtifactRef.model_validate(compiled.compile_report_ref.model_dump())
        program_graph_ref = graph_refs[0]
        if (
            exec_plan_ref.manifest_profile_sha256 is None
            or compile_report_ref.manifest_profile_sha256 is None
            or program_graph_ref.manifest_profile_sha256 is None
            or binding_result.input_bindings_ref.manifest_profile_sha256 is None
            or binding_result.bound_state_snapshot_ref.manifest_profile_sha256 is None
        ):
            raise AssertionError("program_graph_fixture_selected_view_missing")
        return ProgramGraphTaxSubsidyInputCase(
            store=store,
            store_root=store.root,
            source_ref=source_ref,
            data_snapshot_ref=data_snapshot_ref,
            registry_bundle_ref=registry_bundle.bundle_ref,
            input_bindings_ref=FoundryInputBindingsRef.model_validate(
                binding_result.input_bindings_ref.model_dump(mode="python")
            ),
            bound_state_snapshot_ref=binding_result.bound_state_snapshot_ref,
            policy_candidate_ref=policy_candidate_ref,
            trinity_ref=trinity_ref,
            compile_report_ref=compile_report_ref,
            exec_plan_ref=exec_plan_ref,
            program_graph_ref=program_graph_ref,
            model_input_port_declaration_ref=model_input_port_declaration_ref,
            _owns_store=owns_store,
        )
    except BaseException:
        if owns_store:
            close = getattr(store, "close", None)
            if callable(close):
                close()
        raise


def execute_program_graph_tax_subsidy_input_case(
    case: ProgramGraphTaxSubsidyInputCase,
) -> ProgramGraphTaxSubsidyExecution:
    """Execute the selected compiled graph through the public Foundry API."""
    from polisyos.core.contracts.foundry import ExecuteRequest, FoundryExecConfig
    from polisyos.foundry.execute.api import execute as execute_foundry

    result = execute_foundry(
        case.store,
        ExecuteRequest(
            exec_plan_ref=case.exec_plan_ref,
            input_bindings_ref=case.input_bindings_ref,
            registry_bundle_ref=case.registry_bundle_ref,
            exec_config=FoundryExecConfig(seed=41, mode="dev", capture_env=True),
            return_selected_profile=True,
        ),
    )
    if not result.ok or result.simulation_result_ref is None:
        raise AssertionError(f"program_graph_execution_failed: {result.notes!r}")
    return ProgramGraphTaxSubsidyExecution(simulation_result_ref=result.simulation_result_ref)
