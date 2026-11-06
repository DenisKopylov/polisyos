"""Candidate-only source-row method bridge alongside conditional N5 results.

Selection, native execution and report reconciliation remain owned by
``generation_cycle.FoundryValuePort`` and its existing source-row verifier.
Simulation draws are never supplied to an observational method.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import TYPE_CHECKING, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError, model_validator

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactUnavailableError,
    ensure_ir_artifact_store,
    input_ref_from_artifact_ref,
    load_core_json_artifact,
    raise_artifact_read_access_error,
)
from polisyos.core.contracts.runtime import RunCandidateValueMethodProjection
from polisyos.core.contracts.value_outer_set import DataTrust, ValueOuterSet
from polisyos.pdc import gy_content_hash

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.core.artifacts import ArtifactStore
    from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContext
    from polisyos.runtime.quality.design_problem import DesignProblem
    from polisyos.runtime.quality.generation_cycle import (
        RealValueOwnerGateway,
        SimulationPortObservation,
        ValueOwnerSourceProjectionRequestV1,
        ValuePortObservation,
        _DefaultSimulationBoundFoundryValuePort,
    )
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationProfileV1,
        GenericN5ExecutionJoinExpectation,
    )
    from polisyos.runtime.quality.substrate_registry import CatalogServingSourcePaths

_REQUEST_KIND = "runtime.value_owner_source_projection_request"
_RESULT_KIND = "runtime.candidate_value_method"


class CandidateValueMethodImplementationError(Exception):
    """Unexpected method faults, distinct from N5 lineage or source unavailability."""


class CandidateValueMethodRecord(BaseModel):
    """Persisted candidate method result bound to its actual generic source chain."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["policyos.runtime.candidate_value_method.v1"] = (
        "policyos.runtime.candidate_value_method.v1"
    )
    authority_purpose: Literal["candidate_source_rows_only"] = "candidate_source_rows_only"
    production_value_eligible: Literal[False] = False
    candidate_id: str = Field(min_length=1)
    candidate_content_hash: str
    design_problem_ref: str
    world_model_record_content_hash: str
    profile_ref: ArtifactRef
    source_request_ref: ArtifactRef
    n5_input_ref: ArtifactRef
    n5_result_ref: ArtifactRef
    n5_execution_ref: ArtifactRef
    cycle_index: int = Field(ge=0)
    selection_inputs: dict[str, JsonValue]
    status: Literal["completed", "refused"]
    limitation_codes: tuple[str, ...]
    reason: str = Field(min_length=1)
    discovery_limitations: tuple[str, ...] = ()
    failure_kind: Literal["input_refused", "environment_unavailable", "not_established"] | None = (
        None
    )
    selected_method_fqn: str | None = None
    run_basis_ref: ArtifactRef | None = None
    value_ref: ArtifactRef | None = None
    content_hash: str

    @model_validator(mode="after")
    def _validate_record(self) -> CandidateValueMethodRecord:
        if any(ref.manifest_profile_sha256 is None for ref in self.input_refs().values()):
            raise ValueError("candidate_value_method_selected_profile_missing")
        if self.source_request_ref.kind != _REQUEST_KIND:
            raise ValueError("candidate_value_method_source_request_kind_mismatch")
        if self.status == "completed":
            if self.run_basis_ref is None or self.value_ref is None or not self.selected_method_fqn:
                raise ValueError("candidate_value_method_completed_refs_missing")
            if self.run_basis_ref.kind != "runtime.value_owner_method_run_basis" or (
                self.value_ref.kind != "runtime.value_outer_set_candidate_fixture"
            ):
                raise ValueError("candidate_value_method_completed_ref_kind_mismatch")
        elif self.run_basis_ref is not None or self.value_ref is not None:
            raise ValueError("candidate_value_method_refused_has_output")
        if not self.limitation_codes:
            raise ValueError("candidate_value_method_limitation_missing")
        if self.content_hash != gy_content_hash(
            self.model_dump(mode="json", exclude={"content_hash"})
        ):
            raise ValueError("candidate_value_method_record_hash_mismatch")
        return self

    def input_refs(self) -> dict[str, ArtifactRef]:
        """Return the complete selected input/output denominator for this record."""
        result = {
            "generic_profile": self.profile_ref,
            "source_request": self.source_request_ref,
            "generic_n5_input": self.n5_input_ref,
            "generic_n5_result": self.n5_result_ref,
            "generic_n5_execution": self.n5_execution_ref,
        }
        if self.run_basis_ref is not None:
            result["owner_method_run_basis"] = self.run_basis_ref
        if self.value_ref is not None:
            result["owner_method_value"] = self.value_ref
        return result


def _selected_ref(ref: object) -> ArtifactRef:
    dump = getattr(ref, "model_dump", None)
    result = ArtifactRef.model_validate(dump(mode="json") if callable(dump) else ref)
    if result.manifest_profile_sha256 is None:
        raise ValueError("candidate_value_method_selected_profile_missing")
    return result


def persist_candidate_value_source_request(
    store: ArtifactStore,
    request: ValueOwnerSourceProjectionRequestV1,
) -> ArtifactRef:
    """Persist explicit candidate role inputs without granting source authority."""
    from polisyos.data_forge import read_api
    from polisyos.ir import CanonSpec, put_json_artifact
    from polisyos.runtime.quality.generation_cycle import ValueOwnerSourceProjectionRequestV1

    request = ValueOwnerSourceProjectionRequestV1.model_validate(request.model_dump(mode="python"))
    inputs = []
    for binding in request.variable_projections:
        projection = read_api.catalog.ActivatedAcquisitionObservationProjection.model_validate(
            binding.projection_payload
        )
        for name in ("receipt_ref", "passport_ref"):
            ref = _selected_ref(getattr(projection, name))
            inputs.append(input_ref_from_artifact_ref(ref, role=f"{binding.role}:{name}"))
    return _selected_ref(
        put_json_artifact(
            ensure_ir_artifact_store(store),
            request.model_dump(mode="json"),
            kind=_REQUEST_KIND,
            schema_name="policyos.runtime.value_owner_source_projection_request.v1",
            schema_version="1.0",
            canon_spec=CanonSpec(forbid_floats=False),
            inputs=inputs,
            return_selected_profile=True,
        )
    )


def _profile_and_request(
    store: ArtifactStore, simulation: SimulationPortObservation
) -> tuple[GenericCycleSimulationProfileV1 | None, ValueOwnerSourceProjectionRequestV1 | None]:
    from polisyos.runtime.quality.generation_cycle import ValueOwnerSourceProjectionRequestV1
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationProfileV1,
    )

    if simulation.generic_profile_ref is None:
        return None, None
    profile = GenericCycleSimulationProfileV1.model_validate(
        load_core_json_artifact(store, simulation.generic_profile_ref)
    )
    ref = profile.candidate_value_source_request_ref
    if ref is None:
        return profile, None
    request = ValueOwnerSourceProjectionRequestV1.model_validate(
        load_core_json_artifact(store, ref)
    )
    return profile, request


class _GatewayContext(Protocol):
    """The existing source owner inputs shared by producer and fresh reader."""

    repo_root: Path | None
    cycle_substrate_context: CycleSubstrateContext | None
    catalog_serving_source: CatalogServingSourcePaths | None
    artifact_store: ArtifactStore | None


def _gateway(
    *, port: _GatewayContext, request: ValueOwnerSourceProjectionRequestV1
) -> RealValueOwnerGateway:
    from polisyos.data_forge import read_api
    from polisyos.runtime.quality.generation_cycle import RealValueOwnerGateway

    outcome = next(binding for binding in request.variable_projections if binding.role == "outcome")
    projection = read_api.catalog.ActivatedAcquisitionObservationProjection.model_validate(
        outcome.projection_payload
    )
    return RealValueOwnerGateway(
        repo_root=port.repo_root,
        cycle_substrate_context=port.cycle_substrate_context,
        catalog_serving_source=port.catalog_serving_source,
        artifact_store=port.artifact_store,
        activated_observation_projection=projection,
        source_projection_request=request,
    )


def produce_candidate_value_method(
    *,
    port: _DefaultSimulationBoundFoundryValuePort,
    candidate: object,
    simulation: SimulationPortObservation,
    problem: DesignProblem,
    conditional: ValuePortObservation,
    cycle_index: int,
) -> ArtifactRef | None:
    """Run the canonical source-row consumer only after real generic N5 admission.

    Missing configuration is omitted. Supplied invalid configuration raises a
    precise refusal for the caller to retain alongside its valid N5 result.
    """
    from polisyos.ir import CanonSpec, put_json_artifact
    from polisyos.runtime.quality.generation_cycle import (
        FoundryValuePort,
        _candidate_content_hash,
        _candidate_id,
        _generic_n5_observation_refusal,
        _problem_ref,
        _value_input_ref,
    )

    store = port.artifact_store
    if store is None or simulation.generic_profile_ref is None:
        return None
    profile, request = _profile_and_request(store, simulation)
    if request is None:
        return None
    if port.requested_method_fqn is not None and (
        port.requested_method_fqn != request.selected_method_fqn
    ):
        raise ValueError("candidate_value_method_explicit_method_conflict")
    if conditional.status != "value_conditional" or conditional.value_ref != str(
        simulation.simulation_result_ref.artifact_id
    ):
        raise ValueError("candidate_value_method_conditional_n5_not_established")
    world = simulation.world_model_record
    if world is None or world != profile.context_inputs.world_model_record:
        raise ValueError("candidate_value_method_world_binding_mismatch")
    if port.generic_cycle_simulation_currentness_resolver is None or (
        port.generic_cycle_simulation_currentness_resolver() is not True
    ):
        raise ValueError("candidate_value_method_source_not_current")
    refusal = _generic_n5_observation_refusal(
        simulation=simulation,
        candidate=candidate,
        problem=problem,
        world_model_record_content_hash=world.content_hash,
        artifact_store=store,
        cycle_index=cycle_index,
        handoff=port.generic_handoff,
        child_selection=port.generic_child_selection,
        verified_scope=port.generic_verified_scope,
        source_run_id=port.generic_source_run_id,
    )
    if refusal is not None:
        raise ValueError("candidate_value_method_n5_execution_not_established:" + refusal)
    consumer = FoundryValuePort(
        owner_gateway=_gateway(port=port, request=request),
        artifact_store=store,
        repo_root=port.repo_root,
        cycle_substrate_context=port.cycle_substrate_context,
        catalog_serving_source=port.catalog_serving_source,
        **{
            key: value
            for key, value in port._selection_configuration().items()
            if key
            not in {"cycle_substrate_context", "catalog_serving_source", "requested_method_fqn"}
        },
        requested_method_fqn=request.selected_method_fqn,
    )
    observation = consumer._evaluate_source_rows(
        candidate=candidate,
        problem=problem,
        world_record=world,
        mode="simulate_only",
        started=time.monotonic(),
        candidate_id=_candidate_id(candidate),
    )
    basis = observation._candidate_method_run_basis_ref
    value = observation._candidate_method_value_ref
    completed = basis is not None and value is not None
    if port.generic_cycle_simulation_currentness_resolver() is not True:
        raise ValueError("candidate_value_method_source_changed_during_execution")
    payload = {
        "schema_version": "policyos.runtime.candidate_value_method.v1",
        "authority_purpose": "candidate_source_rows_only",
        "production_value_eligible": False,
        "candidate_id": _candidate_id(candidate),
        "candidate_content_hash": _candidate_content_hash(candidate),
        "design_problem_ref": _problem_ref(problem),
        "world_model_record_content_hash": world.content_hash,
        "profile_ref": simulation.generic_profile_ref.model_dump(mode="json"),
        "source_request_ref": profile.candidate_value_source_request_ref.model_dump(mode="json"),
        "n5_input_ref": _selected_ref(simulation.generic_n5_input_ref).model_dump(mode="json"),
        "n5_result_ref": _selected_ref(simulation.simulation_result_ref).model_dump(mode="json"),
        "n5_execution_ref": _selected_ref(simulation.generic_n5_execution_ref).model_dump(
            mode="json"
        ),
        "cycle_index": cycle_index,
        "selection_inputs": consumer._selection_inputs(),
        "status": "completed" if completed else "refused",
        "limitation_codes": tuple(
            dict.fromkeys(
                (
                    *observation.authority_blockers,
                    *observation._candidate_method_scope_limitations,
                    *(
                        ("outcome_query_coordinates_proposed_unverified",)
                        if problem.outcome_of_interest.query_coordinate_status is not None
                        else ()
                    ),
                )
            )
        ),
        "reason": observation.reason
        + (
            " Query coordinates remain candidate-proposed; "
            "agreement with user intent is not established."
            if problem.outcome_of_interest.query_coordinate_status is not None
            else ""
        ),
        "discovery_limitations": observation._candidate_method_scope_limitations,
        "failure_kind": observation._candidate_method_failure_kind,
        "selected_method_fqn": observation.selected_method_fqn,
        "run_basis_ref": _selected_ref(basis).model_dump(mode="json") if completed else None,
        "value_ref": _selected_ref(value).model_dump(mode="json") if completed else None,
    }
    record = CandidateValueMethodRecord.model_validate(
        {**payload, "content_hash": gy_content_hash(payload)}
    )
    ref = put_json_artifact(
        ensure_ir_artifact_store(store),
        record.model_dump(mode="json"),
        kind=_RESULT_KIND,
        schema_name="policyos.runtime.candidate_value_method.v1",
        schema_version="1.0",
        canon_spec=CanonSpec(forbid_floats=False),
        inputs=[_value_input_ref(ref, role=role) for role, ref in record.input_refs().items()],
        return_selected_profile=True,
    )
    return _selected_ref(ref)


def project_candidate_value_method(
    *,
    store: ArtifactStore,
    record_ref: ArtifactRef | None,
    candidate: object,
    problem: DesignProblem,
    simulation: SimulationPortObservation,
    cycle_substrate_context: CycleSubstrateContext,
    catalog_serving_source: CatalogServingSourcePaths | None,
    limitation_code: str | None = None,
    n5_expectation: GenericN5ExecutionJoinExpectation | None = None,
) -> RunCandidateValueMethodProjection | None:
    """Reopen the selected owner and reconcile the persisted native method report.

    The source-row verifier reruns the selected method for reconciliation. It
    never reruns N5 or upgrades candidate data to empirical authority.
    """
    if record_ref is None:
        if limitation_code is None:
            return None
        return RunCandidateValueMethodProjection(
            status="not_established",
            limitation_codes=(limitation_code,),
        )
    from contextlib import ExitStack
    from types import SimpleNamespace

    from polisyos.foundry.methods import (
        UnboundFoundryDiscoveryInputError,
        bootstrap_foundry_method_registry,
        registry_scope,
    )
    from polisyos.runtime.quality.generation_cycle import (
        FoundryValuePort,
        _candidate_content_hash,
        _candidate_id,
        _problem_ref,
        _value_artifact_ref,
        _value_load_ref_payload,
        _value_manifest_has_exact_inputs,
        _value_outer_set_from_owner_method_run_basis,
    )

    try:
        record_ref = _selected_ref(record_ref)
        if record_ref.kind != _RESULT_KIND:
            raise ValueError("candidate_value_method_record_kind_mismatch")
        record = CandidateValueMethodRecord.model_validate(
            load_core_json_artifact(store, record_ref)
        )
        profile, request = _profile_and_request(store, simulation)
        if profile is None or request is None:
            raise ValueError("candidate_value_method_selected_source_request_missing")
        # Simulation keeps its WMR only in memory. Fresh readers recover the
        # exact persisted owner from the selected profile, then reconcile it
        # against the recorded hash and the canonical N5 execution join below.
        world = profile.context_inputs.world_model_record
        if simulation.world_model_record is not None and simulation.world_model_record != world:
            raise ValueError("candidate_value_method_runtime_world_binding_mismatch")
        if (
            record.candidate_id != _candidate_id(candidate)
            or record.candidate_content_hash != _candidate_content_hash(candidate)
            or record.design_problem_ref != _problem_ref(problem)
            or record.world_model_record_content_hash != world.content_hash
            or record.profile_ref != simulation.generic_profile_ref
            or record.source_request_ref != profile.candidate_value_source_request_ref
            or record.n5_input_ref != simulation.generic_n5_input_ref
            or record.n5_result_ref != simulation.simulation_result_ref
            or record.n5_execution_ref != simulation.generic_n5_execution_ref
        ):
            raise ValueError("candidate_value_method_source_binding_mismatch")
        from polisyos.runtime.quality.generic_simulation_admission import (
            GenericCycleSimulationAdmissionOwner,
        )

        if n5_expectation is None or (
            n5_expectation.input_ref != record.n5_input_ref
            or n5_expectation.result_ref != record.n5_result_ref
            or n5_expectation.profile_ref != record.profile_ref
            or n5_expectation.candidate_id != record.candidate_id
            or n5_expectation.candidate_atom_hash != record.candidate_content_hash
            or n5_expectation.design_problem_ref != record.design_problem_ref
            or n5_expectation.cycle_index != record.cycle_index
            or n5_expectation.world_model_record_content_hash
            != record.world_model_record_content_hash
        ):
            raise ValueError("candidate_value_method_n5_expectation_missing_or_mismatched")
        join = GenericCycleSimulationAdmissionOwner(
            profiles=(), store=store
        ).resolve_n5_execution_join(
            record.n5_execution_ref,
            expected=n5_expectation,
        )
        if join.status != "resolved":
            raise ValueError(
                "candidate_value_method_n5_execution_not_established:" + str(join.code)
            )
        if problem.outcome_of_interest.query_coordinate_status is not None and (
            "outcome_query_coordinates_proposed_unverified" not in record.limitation_codes
        ):
            raise ValueError("candidate_value_method_query_coordinate_limitation_missing")
        ir_store = ensure_ir_artifact_store(store)
        if not _value_manifest_has_exact_inputs(
            ir_store,
            _value_artifact_ref(record_ref),
            tuple((_value_artifact_ref(ref), role) for role, ref in record.input_refs().items()),
        ):
            raise ValueError("candidate_value_method_manifest_binding_mismatch")
        if record.status == "refused":
            return RunCandidateValueMethodProjection(
                status="refused",
                record_ref=record_ref,
                source_request_ref=record.source_request_ref,
                selected_method_fqn=record.selected_method_fqn,
                limitation_codes=record.limitation_codes,
                reason=record.reason,
                discovery_limitations=record.discovery_limitations,
                failure_kind=record.failure_kind,
            )
        if catalog_serving_source is None:
            raise ValueError("candidate_value_method_current_source_owner_missing")
        port = SimpleNamespace(
            repo_root=catalog_serving_source.repo_root,
            artifact_store=store,
            cycle_substrate_context=cycle_substrate_context,
            catalog_serving_source=catalog_serving_source,
        )
        gateway = _gateway(port=port, request=request)
        from polisyos.runtime.quality.generation_cycle import _OBSERVATION_MANIFEST_UNSUPPLIED

        consumer = FoundryValuePort(
            owner_gateway=gateway,
            artifact_store=store,
            repo_root=port.repo_root,
            cycle_substrate_context=cycle_substrate_context,
            catalog_serving_source=catalog_serving_source,
            requested_method_fqn=request.selected_method_fqn,
            observation_to_contract_manifest=record.selection_inputs.get(
                "observation_to_contract_manifest",
                _OBSERVATION_MANIFEST_UNSUPPLIED,
            ),
            observation_family=record.selection_inputs.get("observation_family"),
            runtime_budget_ms=record.selection_inputs.get("runtime_budget_ms"),
        )
        selection_inputs = consumer._selection_inputs()
        if gy_content_hash(selection_inputs) != gy_content_hash(record.selection_inputs):
            raise ValueError("candidate_value_method_selection_configuration_mismatch")
        with ExitStack() as stack:
            registry = stack.enter_context(registry_scope())
            try:
                report = bootstrap_foundry_method_registry(
                    registry,
                    include_builtins=True,
                    include_entry_points=True,
                    include_dev_scan=False,
                    require_bound_discovery_manifest=True,
                )
            except UnboundFoundryDiscoveryInputError:
                if (
                    "value_method_entrypoint_scope_not_established"
                    not in record.discovery_limitations
                ):
                    raise ValueError(
                        "candidate_value_method_discovery_scope_limitation_missing"
                    ) from None
                stack.close()
                registry = stack.enter_context(registry_scope())
                report = bootstrap_foundry_method_registry(
                    registry,
                    include_builtins=True,
                    include_entry_points=False,
                    include_dev_scan=False,
                    require_bound_discovery_manifest=True,
                )
            if not report.success:
                raise ValueError("candidate_value_method_registry_unavailable")
            stack.enter_context(registry.snapshot_scope())
            outer = _value_outer_set_from_owner_method_run_basis(
                store=ir_store,
                run_basis_ref=_value_artifact_ref(record.run_basis_ref),
                world_record=world,
                data_trust=DataTrust(
                    tier="candidate_fixture",
                    trust_cap=0.0,
                    trust_multiplier=0.0,
                    min_coverage=0.0,
                    max_coverage=1.0,
                    promotion_floor=1.0,
                    authority_ref="candidate_fixture://value_method_run",
                ),
                source_gateway=gateway,
                candidate=candidate,
                problem=problem,
                registry=registry,
                registry_report=report,
                selection_inputs=selection_inputs,
            )
        selected_outer = ValueOuterSet.from_persisted_payload(
            _value_load_ref_payload(ir_store, _value_artifact_ref(record.value_ref))
        )
        if selected_outer != outer or not _value_manifest_has_exact_inputs(
            ir_store,
            _value_artifact_ref(record.value_ref),
            ((_value_artifact_ref(record.run_basis_ref), "owner_method_run_basis"),),
        ):
            raise ValueError("candidate_value_method_outer_reconciliation_mismatch")
        basis = _value_load_ref_payload(ir_store, _value_artifact_ref(record.run_basis_ref))
        if not isinstance(basis, Mapping) or (
            basis.get("selected_method_fqn") != record.selected_method_fqn
        ):
            raise ValueError("candidate_value_method_selected_method_mismatch")
        from polisyos.ir import CausalEffectReportRef, load_causal_effect_report
        from polisyos.runtime.quality.generation_cycle import ValueDataProfile

        report_ref = _selected_ref(basis["report_ref"])
        native_report = load_causal_effect_report(
            ir_store, CausalEffectReportRef.model_validate(report_ref.model_dump(mode="python"))
        )
        owner_profile = ValueDataProfile.model_validate(
            _value_load_ref_payload(ir_store, _value_artifact_ref(basis["profile_ref"]))
        )
        runner_ref = _value_artifact_ref(basis["runner_request_ref"])
        runner_manifest = ir_store.get_manifest_by_profile(
            runner_ref.artifact_id,
            runner_ref.manifest_profile_sha256,
        )
        receipt_edges = tuple(
            edge for edge in runner_manifest.inputs if edge.role == "method_selection_receipt"
        )
        if len(receipt_edges) != 1:
            raise ValueError("candidate_value_method_selection_receipt_edge_missing")
        selection_ref = _selected_ref(
            {
                "artifact_id": str(receipt_edges[0].artifact_id),
                "kind": "runtime.value_owner_method_selection_receipt",
                "media_type": "application/json",
                "manifest_profile_sha256": receipt_edges[0].manifest_profile_sha256,
            }
        )
        return RunCandidateValueMethodProjection(
            status="completed",
            record_ref=record_ref,
            source_request_ref=record.source_request_ref,
            run_basis_ref=record.run_basis_ref,
            value_ref=record.value_ref,
            selected_method_fqn=record.selected_method_fqn,
            value_outer_set=outer,
            native_report_ref=report_ref,
            method_selection_receipt_ref=selection_ref,
            measurement_unit=owner_profile.measurement_unit,
            point_estimate=native_report.point_estimate,
            statistical_interval=native_report.confidence_interval,
            limitation_codes=record.limitation_codes,
            reason=record.reason,
            discovery_limitations=record.discovery_limitations,
            failure_kind=record.failure_kind,
        )
    except (
        FileNotFoundError,
        ValueError,
        CanonicalProfileRefusalError,
        ArtifactUnavailableError,
    ) as exc:
        from polisyos.runtime.quality.generation_cycle import _value_owner_failure_kind

        raise_artifact_read_access_error(exc)
        try:
            failure_kind = _value_owner_failure_kind(exc)
        except PermissionError:
            raise
        except Exception as internal:
            raise CandidateValueMethodImplementationError(
                "candidate_value_method_replay_internal_error"
            ) from internal
        code = getattr(exc, "code", None)
        if (
            code is None
            and isinstance(exc, ValueError)
            and str(exc).startswith(
                (
                    "candidate_value_method_",
                    "value_owner_",
                    "value_method_",
                )
            )
        ):
            code = str(exc)
        if isinstance(exc, ValueError) and code is None and not isinstance(exc, ValidationError):
            raise CandidateValueMethodImplementationError(
                "candidate_value_method_replay_internal_error"
            ) from exc
        return RunCandidateValueMethodProjection(
            status="not_established",
            record_ref=record_ref,
            limitation_codes=(str(code or "candidate_value_method_replay_refused"),),
            failure_kind=failure_kind,
        )
    except PermissionError:
        raise
    except Exception as exc:
        raise CandidateValueMethodImplementationError(
            "candidate_value_method_replay_internal_error"
        ) from exc
