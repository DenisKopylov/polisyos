"""Persist N4 candidate sources for N6 custody and the existing N9 input bridge.

This owner preserves candidate inputs. It cannot appoint an authority, admit a
protected candidate, replace a missing producer, or promote a synthetic source.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import fields
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core import artifacts, canon
from polisyos.core.artifacts._manifest_lifecycle import ManifestLifecycle
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    ArtifactSameInputClosureInfo,
    ArtifactTenantContextInfo,
    InputRef,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
)
from polisyos.ir import TrinityBundle  # noqa: TC001
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality import design_generation as n4
from polisyos.runtime.quality.cycle_substrate import (
    CycleSubstrateContext,
    revalidate_cycle_substrate_context,
)
from polisyos.runtime.quality.design_problem import DesignProblem  # noqa: TC001

if TYPE_CHECKING:
    from polisyos.runtime.quality.credal_reference import CredalReference
    from polisyos.runtime.quality.generation_cycle import (
        CandidateSummary,
        GenerationSourcePreservationReceipt,
    )

SOURCE_SCHEMA = "policyos.runtime.generation_source_handoff.v1"
SOURCE_KIND = "runtime.generation_source_handoff"
SOURCE_RULE = "policyos.runtime.generation_source_preservation.v1"
N4_CANDIDATE_PROPOSAL_SCHEMA = "policyos.runtime.quality.n4_candidate_proposal_record.v1"
N4_CANDIDATE_PROPOSAL_V2_SCHEMA = "policyos.runtime.quality.n4_candidate_proposal_record.v2"
N4_CANDIDATE_PROPOSAL_KIND = "runtime.quality.n4_candidate_proposal"
N4_CANDIDATE_PROPOSAL_LOCATOR_SCHEMA = (
    "policyos.runtime.quality.n4_candidate_proposal_locator.v1"
)
Identity = tuple[str, str, str]
ExecutionScope = Literal["production", "contract_testing"]
_SOURCE_CANON = canon.CanonSpec(forbid_floats=False, exclude_none=False)
_CANDIDATE_SIMULATION_INPUT_KIND = "runtime.quality.candidate_simulation_n5_input"
_CANDIDATE_SIMULATION_EXECUTION_KIND = "runtime.quality.candidate_simulation_execution"


def _source_write_options() -> artifacts.ArtifactWriteOptions:
    return artifacts.ArtifactWriteOptions(
        kind=SOURCE_KIND,
        media_type="application/json",
        schema=artifacts.SchemaInfo(name=SOURCE_SCHEMA, version="1.0"),
        producer=artifacts.ProducerInfo(component=__name__, version="1.0"),
    )


def _candidate_simulation_write_options(
    *,
    kind: str,
    schema_name: str,
    schema_version: str,
    job_id: str,
    run_id: str,
    tenant_id: str,
    cell_id: str,
    source_ref: str,
    input_refs: Sequence[InputRef] = (),
) -> artifacts.ArtifactWriteOptions:
    """Bind purpose-specific candidate records to the existing job/tenant."""

    return artifacts.ArtifactWriteOptions(
        kind=kind,
        media_type="application/json",
        schema=artifacts.SchemaInfo(name=schema_name, version=schema_version),
        producer=artifacts.ProducerInfo(component=__name__, version="1.0"),
        inputs=list(input_refs),
        tenant_context=ArtifactTenantContextInfo(tenant_id=tenant_id, cell_id=cell_id),
        same_input_closure=ArtifactSameInputClosureInfo(
            closure_id=f"candidate-simulation:{run_id}:{job_id}:{source_ref}",
            status="candidate_only",
            run_id=run_id,
            job_id=job_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        ),
    )


def _has_source_owner_profile(manifest: artifacts.ArtifactManifest) -> bool:
    return _has_owner_profile(manifest, _source_write_options())


def _n4_candidate_proposal_write_options() -> artifacts.ArtifactWriteOptions:
    return artifacts.ArtifactWriteOptions(
        kind=N4_CANDIDATE_PROPOSAL_KIND,
        media_type="application/json",
        schema=artifacts.SchemaInfo(name=N4_CANDIDATE_PROPOSAL_SCHEMA, version="1.0"),
        producer=artifacts.ProducerInfo(component=__name__, version="1.0"),
    )


def _n4_candidate_proposal_v2_write_options() -> artifacts.ArtifactWriteOptions:
    return artifacts.ArtifactWriteOptions(
        kind=N4_CANDIDATE_PROPOSAL_KIND,
        media_type="application/json",
        schema=artifacts.SchemaInfo(name=N4_CANDIDATE_PROPOSAL_V2_SCHEMA, version="2.0"),
        producer=artifacts.ProducerInfo(component=__name__, version="1.0"),
    )


def _has_n4_candidate_proposal_owner_profile(manifest: artifacts.ArtifactManifest) -> bool:
    return _has_owner_profile(manifest, _n4_candidate_proposal_write_options())


def _has_n4_candidate_proposal_v2_owner_profile(
    manifest: artifacts.ArtifactManifest,
) -> bool:
    return _has_owner_profile(manifest, _n4_candidate_proposal_v2_write_options())


def _has_owner_profile(
    manifest: artifacts.ArtifactManifest,
    options: artifacts.ArtifactWriteOptions,
) -> bool:
    actual = {
        field.alias or name: getattr(manifest, name)
        for name, field in type(manifest).model_fields.items()
    }
    # Compare the complete persistence profile, using Core's declared normalization.
    # Byte size, artifact identity and integrity remain Core verification's concern.
    for field in fields(options):
        expected = getattr(options, field.name)
        # Core's ManifestLifecycle persists absent collection options as empty lists.
        if field.name in {"inputs", "warnings"}:
            expected = list(expected or [])
        if field.name not in actual or actual[field.name] != expected:
            return False
    return True


def _ref_selects_manifest(ref: ArtifactRef, manifest: artifacts.ArtifactManifest) -> bool:
    """Check a typed default or explicit view against its selected manifest."""

    if ref.kind != manifest.kind or ref.media_type != manifest.media_type:
        return False
    return ref.manifest_profile_sha256 is None or (
        ref.manifest_profile_sha256 == ManifestLifecycle.profile_sha256(manifest)
    )


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class N4CandidateProposalRecord(_StrictModel):
    """Persist one tenant-bound N4 proposal with an explicit authority limitation."""

    schema_version: Literal[
        "policyos.runtime.quality.n4_candidate_proposal_record.v1"
    ] = N4_CANDIDATE_PROPOSAL_SCHEMA
    authority_purpose: Literal["candidate_proposal"] = "candidate_proposal"
    status: Literal["candidate_limited"] = "candidate_limited"
    execution_band: Literal["candidate"] = "candidate"
    stage: Literal["n4_proposal_only"] = "n4_proposal_only"
    limitation_code: Literal["cycle_substrate_context_unavailable"] = (
        "cycle_substrate_context_unavailable"
    )
    n5_status: Literal["not_run"] = "not_run"
    n8_status: Literal["not_run"] = "not_run"
    n9_status: Literal["not_run"] = "not_run"
    s8_status: Literal["not_run"] = "not_run"
    job_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    request_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    design_problem_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    problem: DesignProblem
    proposal: n4.N4CandidateProposalSource
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _candidate_proposal_bindings(self) -> N4CandidateProposalRecord:
        payload = self.model_dump(mode="python", exclude={"content_hash"})
        if self.content_hash != _source_content_hash(payload):
            raise ValueError("n4_candidate_proposal_content_hash_mismatch")
        problem_ref = gy_content_hash(self.problem.model_dump(mode="json"))
        if self.design_problem_ref != problem_ref:
            raise ValueError("n4_candidate_proposal_problem_ref_mismatch")
        if self.proposal.design_problem_ref != problem_ref:
            raise ValueError("n4_candidate_proposal_source_problem_mismatch")
        expected_request_hash = "sha256:" + hashlib.sha256(
            self.problem.nl_provenance.raw_request.encode("utf-8")
        ).hexdigest()
        if self.request_hash != expected_request_hash:
            raise ValueError("n4_candidate_proposal_request_binding_mismatch")
        if self.proposal.execution_band != self.execution_band:
            raise ValueError("n4_candidate_proposal_band_mismatch")
        if self.proposal.limitation_code != self.limitation_code:
            raise ValueError("n4_candidate_proposal_limitation_mismatch")
        if any(
            status != "not_run"
            for status in (self.n5_status, self.n8_status, self.n9_status, self.s8_status)
        ):
            raise ValueError("n4_candidate_proposal_crossed_unrun_stage")
        return self


class N4CandidateProposalSimulationDisposition(_StrictModel):
    """Bind a simulate-only attempt to its unavailable cycle-context outcome."""

    execution_intent_band: Literal["simulate_only_attempt"] = "simulate_only_attempt"
    status: Literal["simulation_unavailable"] = "simulation_unavailable"
    reason_code: Literal["cycle_substrate_context_not_established"] = (
        "cycle_substrate_context_not_established"
    )


class N4CandidateProposalSimulationRecord(N4CandidateProposalRecord):
    """Versioned N4 proposal carrying a content-bound simulation disposition."""

    schema_version: Literal[
        "policyos.runtime.quality.n4_candidate_proposal_record.v2"
    ] = N4_CANDIDATE_PROPOSAL_V2_SCHEMA
    simulation_disposition: N4CandidateProposalSimulationDisposition


class N4CandidateProposalLocator(_StrictModel):
    """Versioned job pointer retaining the Core CAS manifest-view selector."""

    schema_version: Literal[
        "policyos.runtime.quality.n4_candidate_proposal_locator.v1"
    ] = N4_CANDIDATE_PROPOSAL_LOCATOR_SCHEMA
    artifact_ref: artifacts.ArtifactRef

    @model_validator(mode="after")
    def _proposal_owner_view(self) -> N4CandidateProposalLocator:
        if (
            self.artifact_ref.kind != N4_CANDIDATE_PROPOSAL_KIND
            or self.artifact_ref.media_type != "application/json"
        ):
            raise ValueError("n4_candidate_proposal_locator_owner_profile_mismatch")
        return self


def _assert_n4_candidate_problem_owner_context(
    problem: DesignProblem,
    *,
    job_id: str,
    run_id: str,
    tenant_id: str,
    cell_id: str,
) -> None:
    """Bind current N4 provenance to its served job owner, not nested claims."""
    source_context = problem.nl_provenance.source_context
    for reserved_carrier in ("runtime_identity", "candidate_context"):
        if reserved_carrier in source_context:
            raise ValueError("n4_candidate_proposal_runtime_identity_not_owner_bound")
    expected = {
        "tenant_id": tenant_id,
        "cell_id": cell_id,
        "job_id": job_id,
        "run_id": run_id,
    }
    for field_name, value in expected.items():
        if source_context.get(field_name) != value:
            label = field_name.removesuffix("_id")
            raise ValueError(f"n4_candidate_proposal_{label}_scope_binding_mismatch")


def _has_synthetic_source(value: object) -> bool:
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, BaseModel):
            pending.append(item.model_dump(mode="python"))
        elif isinstance(item, Mapping):
            if item.get("synthetic") is True:
                return True
            pending.extend(item.values())
        elif isinstance(item, (tuple, list)):
            pending.extend(item)
    return False


def _source_content_hash(payload: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canon.to_canonical_bytes(payload, _SOURCE_CANON)).hexdigest()


def _organ_source_payload(organ: n4.DesignGenerationOrganRun) -> dict[str, Any]:
    from polisyos.runtime.quality.promotion_sequence import _CredalReferenceReplayRecord

    return {
        "generation_result": organ.result,
        "trinity_bundle": organ.trinity_bundle,
        "cycle_substrate_context": organ.cycle_substrate_context,
        "credal_reference_payload": (
            _CredalReferenceReplayRecord.from_reference(organ.credal_reference).model_dump(
                mode="python"
            )
            if organ.credal_reference is not None
            else None
        ),
        "candidate_sources": organ.candidate_sources,
    }


def _writer_projection_preserves_grounding(
    *,
    source: n4.GenerationCandidateSource,
    reference: CredalReference,
    proposal: Mapping[str, Any],
) -> bool:
    """Require the real relation owner to reproduce the entire emitted certificate."""
    from polisyos.runtime.quality.grounding_relation import GroundingRelationEngine

    owner = GroundingRelationEngine(reference)
    original = owner.certificate_for(source.proposal, proposal_id=source.proposal_id)
    projected = owner.certificate_for(proposal, proposal_id=source.proposal_id)
    return original == projected == source.grounding_relation_certificate


def generation_source_synthetic(
    source: object,
    *,
    problem: DesignProblem,
    execution_scope: ExecutionScope,
) -> Literal[True] | None:
    """Aggregate the whole retained source; absence never becomes a false assertion."""
    if execution_scope == "contract_testing":
        return True
    if isinstance(source, n4.DesignGenerationOrganRun):
        payload = _organ_source_payload(source)
    elif isinstance(source, n4.GenerationUnderAResult):
        payload = source.model_dump(mode="python")
    else:
        return None
    return (
        True
        if _has_synthetic_source(
            {
                "problem": problem.model_dump(mode="python"),
                "source": payload,
            }
        )
        else None
    )


class GenerationSourceHandoff(_StrictModel):
    """One immutable, source-bound N4 organ result, never an authority receipt."""

    schema_version: Literal["policyos.runtime.generation_source_handoff.v1"] = SOURCE_SCHEMA
    authority_purpose: Literal["candidate_source_custody"] = "candidate_source_custody"
    synthetic: bool | None
    execution_scope: ExecutionScope
    run_id: str = Field(min_length=1)
    cycle_index: int = Field(ge=0)
    problem: DesignProblem
    generation_result: n4.GenerationUnderAResult
    trinity_bundle: TrinityBundle | None
    cycle_substrate_context: CycleSubstrateContext | None
    credal_reference_payload: dict[str, Any] | None
    candidate_sources: tuple[n4.GenerationCandidateSource, ...]
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_source_bindings(self) -> GenerationSourceHandoff:
        payload = self.model_dump(mode="python", exclude={"content_hash"})
        if self.content_hash != _source_content_hash(payload):
            raise ValueError("generation_source_content_hash_mismatch")
        source_payload = {key: value for key, value in payload.items() if key != "synthetic"}
        expected_synthetic = (
            True
            if self.execution_scope == "contract_testing" or _has_synthetic_source(source_payload)
            else None
        )
        if self.synthetic is not expected_synthetic:
            raise ValueError("generation_source_synthetic_ancestry_lost")
        problem_ref = gy_content_hash(self.problem.model_dump(mode="json"))
        if self.generation_result.design_problem_ref != problem_ref:
            raise ValueError("generation_source_problem_mismatch")
        context = self.cycle_substrate_context
        if context is not None:
            context = revalidate_cycle_substrate_context(context)
            if context.design_problem_ref != problem_ref:
                raise ValueError("generation_source_substrate_problem_mismatch")
        reference = self.reference()
        if (
            reference is not None
            and context is not None
            and reference.component_versions.get("WMR") != context.world_model_record.content_hash
        ):
            raise ValueError("generation_source_reference_world_mismatch")
        candidates = self.generation_result.candidates
        candidate_ids = [candidate.candidate_id for candidate in candidates]
        source_ids = [source.candidate_id for source in self.candidate_sources]
        if (
            len(candidate_ids) != len(set(candidate_ids))
            or len(source_ids) != len(set(source_ids))
            or set(candidate_ids) != set(source_ids)
        ):
            raise ValueError("generation_source_complete_membership_mismatch")
        if not candidates:
            return self
        bundle = self.trinity_bundle
        if bundle is None or context is None or reference is None:
            raise ValueError("generation_source_owner_input_missing")
        interventions = {item.intervention_id: item for item in bundle.policy_spec.interventions}
        if len(interventions) != len(bundle.policy_spec.interventions):
            raise ValueError("generation_source_intervention_identity_ambiguous")
        sources = {source.candidate_id: source for source in self.candidate_sources}
        bundle_ref = gy_content_hash(bundle.model_dump(mode="json"))
        policy_ref = gy_content_hash(bundle.policy_spec.model_dump(mode="json"))
        for candidate in candidates:
            source = sources[candidate.candidate_id]
            intervention = interventions.get(source.intervention_id)
            if intervention is None:
                raise ValueError("generation_source_intervention_missing")
            expected_proposal = n4._grounding_proposal_for_intervention(
                intervention, design_problem=self.problem, bundle_ref=bundle_ref
            )
            if (
                source.proposal != expected_proposal
                or source.proposal_id != expected_proposal["proposal_id"]
            ):
                raise ValueError("generation_source_proposal_mismatch")
            cg1, cg2 = source.grounding_relation_certificate, source.grounding_decision_certificate
            if cg2.cg1_content_hash != cg1.content_hash or cg1.proposal_id != source.proposal_id:
                raise ValueError("generation_source_certificate_binding_mismatch")
            if reference is not None and (
                cg2.reference_hash != reference.reference_hash
                or cg2.reference_epoch != reference.reference_epoch
            ):
                raise ValueError("generation_source_certificate_reference_mismatch")
            provenance = candidate.provenance
            recomputed = n4._shadow_candidate_from_grounding(
                design_problem=self.problem,
                design_problem_ref=problem_ref,
                intervention=intervention,
                model_id=provenance.model_id,
                draft_path=provenance.draft_generator_path,
                formalizer_path=provenance.formalizer_generator_path,
                critic_path=provenance.critic_generator_path,
                critique_verdict=candidate.critique_verdict,
                bundle_ref=bundle_ref,
                policy_spec_ref=policy_ref,
                prompt_hashes=provenance.prompt_hashes,
                raw_responses=provenance.raw_llm_responses,
                cg1=cg1,
                cg2=cg2,
                resolved_world_model_record_ref=context.world_model_record.world_model_record_id,
                world_record=context.world_model_record,
            )
            if recomputed.model_dump(mode="json") != candidate.model_dump(mode="json"):
                raise ValueError("generation_source_original_candidate_mismatch")
        return self

    def reference(self) -> CredalReference | None:
        """Reuse the N9 full-reference replay owner, including every edge/hash check."""
        if self.credal_reference_payload is None:
            return None
        from polisyos.runtime.quality.promotion_sequence import _CredalReferenceReplayRecord

        return _CredalReferenceReplayRecord.model_validate(
            self.credal_reference_payload
        ).to_reference()

    def source_identity_hash(self) -> str:
        """Bind the entire source independently of its repeated cycle occurrence."""
        return _source_content_hash(
            self.model_dump(
                mode="python",
                exclude={"cycle_index", "content_hash"},
            )
        )

    def identities(self) -> tuple[Identity, ...]:
        """Enumerate the actual typed candidate denominator in this source artifact."""
        return tuple(
            (self.generation_result.design_problem_ref, item.candidate_id, item.atom.content_hash)
            for item in self.generation_result.candidates
        )


class GenerationSourceResolution(_StrictModel):
    """Typed candidate-source resolution; its context carries existing owner objects."""

    status: Literal["resolved", "not_established"]
    code: str
    source_ref: str | None = None
    context: dict[str, Any] = Field(default_factory=dict, exclude=True)


class GenerationSourceRepository:
    """Preserve and replay typed organ sources through the existing Core artifact store."""

    def __init__(self, store: artifacts.ArtifactStore) -> None:
        self.store = store

    def persist_candidate_simulation_input_v2(self, *, input_record: object) -> str:
        """Persist one v2 N5 input through the runtime-supplied artifact store."""

        from polisyos.runtime.quality.candidate_simulation import (
            CandidateSimulationN5InputV2,
        )

        if type(input_record) is not CandidateSimulationN5InputV2:
            raise TypeError("candidate_simulation_n5_input_untyped")
        record = CandidateSimulationN5InputV2.model_validate(
            input_record.model_dump(mode="python")
        )
        options = _candidate_simulation_write_options(
            kind=_CANDIDATE_SIMULATION_INPUT_KIND,
            schema_name=record.schema_version,
            schema_version="2.0",
            job_id=record.job_id,
            run_id=record.run_id,
            tenant_id=record.tenant_id,
            cell_id=record.cell_id,
            source_ref=record.n4_source_ref,
        )
        ref = self.store.put_bytes(canon.to_canonical_bytes(record, _SOURCE_CANON), options)
        return str(ref.artifact_id)

    def persist_candidate_simulation_input_v3(
        self, *, input_record: object
    ) -> ArtifactRef:
        """Persist N5 input while retaining the selected upstream CAS views."""

        from polisyos.runtime.quality.candidate_simulation import (
            CandidateSimulationN5InputV3,
        )

        if type(input_record) is not CandidateSimulationN5InputV3:
            raise TypeError("candidate_simulation_n5_input_untyped")
        record = CandidateSimulationN5InputV3.model_validate(
            input_record.model_dump(mode="python")
        )
        options = _candidate_simulation_write_options(
            kind=_CANDIDATE_SIMULATION_INPUT_KIND,
            schema_name=record.schema_version,
            schema_version="3.0",
            job_id=record.job_id,
            run_id=record.run_id,
            tenant_id=record.tenant_id,
            cell_id=record.cell_id,
            source_ref=str(record.n4_source_ref.artifact_id),
            input_refs=(
                input_ref_from_artifact_ref(record.n4_source_ref, role="n4_source"),
                input_ref_from_artifact_ref(
                    record.context_job_ref, role="cycle_substrate_context_job"
                ),
            ),
        )
        return self.store.put_bytes(canon.to_canonical_bytes(record, _SOURCE_CANON), options)

    def persist_candidate_simulation_execution_v2(
        self,
        *,
        input_ref: str,
        simulation: object,
        handoff: object,
    ) -> str:
        """Bind an actual persisted N5 result to the exact admitted input."""

        from polisyos.runtime.quality.candidate_simulation import (
            CandidateSimulationContextHandoff,
            CandidateSimulationExecutionV2,
            CandidateSimulationN5InputV2,
        )
        from polisyos.runtime.quality.generation_cycle import SimulationPortObservation

        if type(handoff) is not CandidateSimulationContextHandoff:
            raise TypeError("candidate_simulation_handoff_untyped")
        if type(simulation) is not SimulationPortObservation:
            raise TypeError("candidate_simulation_observation_untyped")
        if (
            simulation.status != "joint_simulated"
            or simulation.simulation_result_ref is None
            or simulation.simulation_ref is None
        ):
            raise ValueError("candidate_simulation_execution_requires_persisted_n5_result")
        input_record = self._load_candidate_simulation_input_v2(input_ref)
        if type(input_record) is not CandidateSimulationN5InputV2:
            raise ValueError("candidate_simulation_input_ref_not_input_record")
        if (
            input_record.context_job_ref != handoff.context_job_ref
            or input_record.job_id != handoff.job_id
            or input_record.run_id != handoff.run_id
            or input_record.tenant_id != handoff.tenant_id
            or input_record.cell_id != handoff.cell_id
            or input_record.profile.content_hash != handoff.profile.content_hash
            or input_record.materialization.context_hash != handoff.context.content_hash
        ):
            raise ValueError("candidate_simulation_execution_handoff_mismatch")
        result_ref = str(simulation.simulation_result_ref.artifact_id)
        if (
            simulation.k_world_ref_before != input_record.materialization.world_model_record_hash
            or simulation.k_world_ref_after != input_record.materialization.world_model_record_hash
        ):
            raise ValueError("candidate_simulation_execution_world_binding_mismatch")
        payload = {
            "schema_version": "policyos.runtime.candidate_simulation.execution.v2",
            "authority_purpose": "candidate_scenario_n5_only",
            "n5_input_ref": input_ref,
            "n4_source_ref": input_record.n4_source_ref,
            "context_job_ref": input_record.context_job_ref,
            "profile_config_ref": input_record.profile_config_ref,
            "job_id": input_record.job_id,
            "run_id": input_record.run_id,
            "tenant_id": input_record.tenant_id,
            "cell_id": input_record.cell_id,
            "original_candidate_id": input_record.original_candidate_id,
            "original_candidate_hash": input_record.original_candidate_hash,
            "original_n4_atom_hash": input_record.original_n4_atom_hash,
            "derived_n5_atom_hash": input_record.materialization.derived_n5_atom.content_hash,
            "problem_ref": input_record.materialization.problem_ref,
            "world_model_record_hash": input_record.materialization.world_model_record_hash,
            "n5_result_ref": result_ref,
            "n5_result_content_hash": simulation.simulation_ref,
            "k_world_ref_before": str(simulation.k_world_ref_before),
            "k_world_ref_after": str(simulation.k_world_ref_after),
        }
        record = CandidateSimulationExecutionV2.model_validate(
            {**payload, "content_hash": gy_content_hash(payload)}
        )
        options = _candidate_simulation_write_options(
            kind=_CANDIDATE_SIMULATION_EXECUTION_KIND,
            schema_name=record.schema_version,
            schema_version="2.0",
            job_id=record.job_id,
            run_id=record.run_id,
            tenant_id=record.tenant_id,
            cell_id=record.cell_id,
            source_ref=record.n4_source_ref,
        )
        ref = self.store.put_bytes(canon.to_canonical_bytes(record, _SOURCE_CANON), options)
        return str(ref.artifact_id)

    def persist_candidate_simulation_execution_v3(
        self,
        *,
        input_ref: ArtifactRef,
        simulation: object,
        handoff: object,
    ) -> ArtifactRef:
        """Persist N5 result binding with selected input/source/context views."""

        from polisyos.runtime.quality.candidate_simulation import (
            CandidateSimulationContextHandoff,
            CandidateSimulationExecutionV3,
            CandidateSimulationN5InputV3,
        )
        from polisyos.runtime.quality.generation_cycle import SimulationPortObservation

        if type(handoff) is not CandidateSimulationContextHandoff:
            raise TypeError("candidate_simulation_handoff_untyped")
        if type(simulation) is not SimulationPortObservation:
            raise TypeError("candidate_simulation_observation_untyped")
        if (
            simulation.status != "joint_simulated"
            or simulation.simulation_result_ref is None
            or simulation.simulation_ref is None
        ):
            raise ValueError("candidate_simulation_execution_requires_persisted_n5_result")
        input_record = self._load_candidate_simulation_input_v3(input_ref)
        if type(input_record) is not CandidateSimulationN5InputV3:
            raise ValueError("candidate_simulation_input_ref_not_input_record")
        if (
            artifact_ref_identity_key(input_record.context_job_ref)
            != artifact_ref_identity_key(handoff.context_job_ref)
            or input_record.job_id != handoff.job_id
            or input_record.run_id != handoff.run_id
            or input_record.tenant_id != handoff.tenant_id
            or input_record.cell_id != handoff.cell_id
            or input_record.profile.content_hash != handoff.profile.content_hash
            or input_record.materialization.context_hash != handoff.context.content_hash
        ):
            raise ValueError("candidate_simulation_execution_handoff_mismatch")
        if (
            simulation.k_world_ref_before != input_record.materialization.world_model_record_hash
            or simulation.k_world_ref_after != input_record.materialization.world_model_record_hash
        ):
            raise ValueError("candidate_simulation_execution_world_binding_mismatch")
        payload = {
            "schema_version": "policyos.runtime.candidate_simulation.execution.v3",
            "authority_purpose": "candidate_scenario_n5_only",
            "n5_input_ref": input_ref,
            "n4_source_ref": input_record.n4_source_ref,
            "context_job_ref": input_record.context_job_ref,
            "profile_config_ref": input_record.profile_config_ref,
            "job_id": input_record.job_id,
            "run_id": input_record.run_id,
            "tenant_id": input_record.tenant_id,
            "cell_id": input_record.cell_id,
            "original_candidate_id": input_record.original_candidate_id,
            "original_candidate_hash": input_record.original_candidate_hash,
            "original_n4_atom_hash": input_record.original_n4_atom_hash,
            "derived_n5_atom_hash": input_record.materialization.derived_n5_atom.content_hash,
            "problem_ref": input_record.materialization.problem_ref,
            "world_model_record_hash": input_record.materialization.world_model_record_hash,
            "n5_result_ref": simulation.simulation_result_ref,
            "n5_result_content_hash": simulation.simulation_ref,
            "k_world_ref_before": str(simulation.k_world_ref_before),
            "k_world_ref_after": str(simulation.k_world_ref_after),
        }
        record = CandidateSimulationExecutionV3.model_validate(
            {**payload, "content_hash": gy_content_hash(payload)}
        )
        options = _candidate_simulation_write_options(
            kind=_CANDIDATE_SIMULATION_EXECUTION_KIND,
            schema_name=record.schema_version,
            schema_version="3.0",
            job_id=record.job_id,
            run_id=record.run_id,
            tenant_id=record.tenant_id,
            cell_id=record.cell_id,
            source_ref=str(record.n4_source_ref.artifact_id),
            input_refs=(
                input_ref_from_artifact_ref(input_ref, role="n5_input"),
                input_ref_from_artifact_ref(record.n4_source_ref, role="n4_source"),
                input_ref_from_artifact_ref(
                    record.context_job_ref, role="cycle_substrate_context_job"
                ),
                input_ref_from_artifact_ref(record.n5_result_ref, role="n5_result"),
            ),
        )
        return self.store.put_bytes(canon.to_canonical_bytes(record, _SOURCE_CANON), options)

    def resolve_candidate_simulation_v2(
        self,
        *,
        ref: str,
        expected_run_id: str,
        expected_job_id: str | None = None,
        expected_tenant_id: str | None = None,
        expected_cell_id: str | None = None,
        require_current_lease: bool = False,
        current_lease_resolver: Callable[[object], bool] | None = None,
    ) -> object:
        """Resolve and replay one purpose-specific v2 input or execution record."""

        from polisyos.runtime.quality.candidate_simulation import (
            CandidateSimulationExecutionV2,
            CandidateSimulationN5InputV2,
        )

        if not self.store.verify(ref).ok:
            raise ValueError("candidate_simulation_v2_cas_integrity_failed")
        manifest = self.store.get_manifest(ref)
        body = self.store.get_bytes(ref)
        if "sha256:" + hashlib.sha256(body).hexdigest() != ref:
            raise ValueError("candidate_simulation_v2_cas_content_mismatch")
        try:
            payload = canon.from_canonical_bytes(body)
            if manifest.kind == _CANDIDATE_SIMULATION_INPUT_KIND:
                record: object = CandidateSimulationN5InputV2.model_validate(payload)
            elif manifest.kind == _CANDIDATE_SIMULATION_EXECUTION_KIND:
                record = CandidateSimulationExecutionV2.model_validate(payload)
            else:
                raise ValueError("candidate_simulation_v2_manifest_kind_mismatch")
        except (TypeError, ValueError) as exc:
            raise ValueError("candidate_simulation_v2_record_invalid") from exc
        is_input = type(record) is CandidateSimulationN5InputV2
        expected_schema = record.schema_version
        expected_kind = (
            _CANDIDATE_SIMULATION_INPUT_KIND
            if is_input
            else _CANDIDATE_SIMULATION_EXECUTION_KIND
        )
        if (
            manifest.kind != expected_kind
            or manifest.media_type != "application/json"
            or manifest.artifact_schema is None
            or manifest.artifact_schema.name != expected_schema
            or manifest.artifact_schema.version != "2.0"
        ):
            raise ValueError("candidate_simulation_v2_manifest_profile_mismatch")
        job_id = record.job_id
        run_id = record.run_id
        tenant_id = record.tenant_id
        cell_id = record.cell_id
        if (
            run_id != expected_run_id
            or (expected_job_id is not None and job_id != expected_job_id)
            or (expected_tenant_id is not None and tenant_id != expected_tenant_id)
            or (expected_cell_id is not None and cell_id != expected_cell_id)
        ):
            raise ValueError("candidate_simulation_v2_identity_mismatch")
        options = _candidate_simulation_write_options(
            kind=expected_kind,
            schema_name=expected_schema,
            schema_version="2.0",
            job_id=job_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            source_ref=record.n4_source_ref,
        )
        if not _has_owner_profile(manifest, options):
            raise ValueError("candidate_simulation_v2_owner_profile_mismatch")
        source = self.load(record.n4_source_ref, run_id=run_id)
        source_candidate = next(
            (
                candidate
                for candidate in source.generation_result.candidates
                if candidate.candidate_id == record.original_candidate_id
                and candidate.atom.content_hash == record.original_n4_atom_hash
            ),
            None,
        )
        if source_candidate is None:
            raise ValueError("candidate_simulation_v2_n4_source_membership_mismatch")
        from polisyos.runtime.quality.cycle_substrate import (
            CycleSubstrateContextArtifactOwner,
        )

        source_problem = source.problem
        context_job = CycleSubstrateContextArtifactOwner(
            store=self.store,
        ).resolve_historical_job_artifact(
            record.context_job_ref,
            problem=source_problem,
            expected_job_id=job_id,
            expected_run_id=run_id,
            expected_tenant_id=tenant_id,
            expected_cell_id=cell_id,
        )
        expected_problem_ref = (
            record.materialization.problem_ref
            if is_input
            else record.problem_ref
        )
        expected_context_hash = (
            record.materialization.context_hash
            if is_input
            else context_job.context.content_hash
        )
        if (
            context_job.design_problem_ref != expected_problem_ref
            or context_job.context.content_hash != expected_context_hash
            or source_problem != context_job.problem
            or source.cycle_substrate_context is None
            or source.cycle_substrate_context.content_hash != context_job.context.content_hash
        ):
            raise ValueError("candidate_simulation_v2_context_job_binding_mismatch")
        if not is_input and (
            context_job.context.world_model_record.content_hash
            != record.world_model_record_hash
        ):
            raise ValueError("candidate_simulation_v2_context_world_binding_mismatch")
        if require_current_lease and (
            current_lease_resolver is None or not current_lease_resolver(record)
        ):
            raise ValueError("candidate_simulation_v2_current_lease_not_established")
        if type(record) is CandidateSimulationExecutionV2:
            input_record = self._load_candidate_simulation_input_v2(record.n5_input_ref)
            if (
                type(input_record) is not CandidateSimulationN5InputV2
                or input_record.n4_source_ref != record.n4_source_ref
                or input_record.context_job_ref != record.context_job_ref
                or input_record.profile_config_ref != record.profile_config_ref
                or input_record.original_candidate_id != record.original_candidate_id
                or input_record.original_candidate_hash != record.original_candidate_hash
                or input_record.original_n4_atom_hash != record.original_n4_atom_hash
                or input_record.materialization.derived_n5_atom.content_hash
                != record.derived_n5_atom_hash
                or input_record.materialization.problem_ref != context_job.design_problem_ref
                or input_record.materialization.context_hash != context_job.context.content_hash
                or input_record.materialization.world_model_record_hash
                != record.world_model_record_hash
            ):
                raise ValueError("candidate_simulation_v2_execution_input_mismatch")
            from polisyos.runtime.quality.generation_cycle import (
                JOINT_SIMULATION_RESULT_ARTIFACT_KIND,
                load_joint_simulation_result,
            )

            result = load_joint_simulation_result(
                {
                    "artifact_id": record.n5_result_ref,
                    "kind": JOINT_SIMULATION_RESULT_ARTIFACT_KIND,
                    "media_type": "application/json",
                },
                store=self.store,
                expected_world_model_record_content_hash=record.world_model_record_hash,
                expected_atom_ids=(input_record.materialization.derived_n5_atom.intervention_id,),
            )
            if result.receipt.payload_hash != record.n5_result_content_hash:
                raise ValueError("candidate_simulation_v2_result_hash_mismatch")
        return record

    def _load_candidate_simulation_input_v2(self, ref: str) -> object:
        """Resolve one v2 input internally through the same owner and store."""

        from polisyos.runtime.quality.candidate_simulation import (
            CandidateSimulationN5InputV2,
        )

        if not self.store.verify(ref).ok:
            raise ValueError("candidate_simulation_v2_input_cas_integrity_failed")
        manifest = self.store.get_manifest(ref)
        body = self.store.get_bytes(ref)
        if (
            "sha256:" + hashlib.sha256(body).hexdigest() != ref
            or manifest.kind != _CANDIDATE_SIMULATION_INPUT_KIND
            or manifest.media_type != "application/json"
            or manifest.artifact_schema is None
            or manifest.artifact_schema.name
            != "policyos.runtime.candidate_simulation.n5_input.v2"
            or manifest.artifact_schema.version != "2.0"
        ):
            raise ValueError("candidate_simulation_v2_input_manifest_mismatch")
        record = CandidateSimulationN5InputV2.model_validate(
            canon.from_canonical_bytes(body)
        )
        options = _candidate_simulation_write_options(
            kind=_CANDIDATE_SIMULATION_INPUT_KIND,
            schema_name=record.schema_version,
            schema_version="2.0",
            job_id=record.job_id,
            run_id=record.run_id,
            tenant_id=record.tenant_id,
            cell_id=record.cell_id,
            source_ref=record.n4_source_ref,
        )
        if not _has_owner_profile(manifest, options):
            raise ValueError("candidate_simulation_v2_input_owner_profile_mismatch")
        return record

    def resolve_candidate_simulation_v3(
        self,
        *,
        ref: ArtifactRef,
        expected_run_id: str,
        expected_job_id: str | None = None,
        expected_tenant_id: str | None = None,
        expected_cell_id: str | None = None,
        require_current_lease: bool = False,
        current_lease_resolver: Callable[[object], bool] | None = None,
    ) -> object:
        """Resolve selector-preserving N5 input or execution through its owners."""

        from polisyos.runtime.quality.candidate_simulation import (
            CandidateSimulationExecutionV3,
            CandidateSimulationN5InputV3,
        )

        if not isinstance(ref, ArtifactRef):
            raise ValueError("candidate_simulation_v3_selected_ref_required")
        if not self.store.verify(ref).ok:
            raise ValueError("candidate_simulation_v3_cas_integrity_failed")
        manifest = self.store.get_manifest(ref)
        if not _ref_selects_manifest(ref, manifest):
            raise ValueError("candidate_simulation_v3_selected_view_mismatch")
        body = self.store.get_bytes(ref)
        artifact_id = str(ref.artifact_id)
        if "sha256:" + hashlib.sha256(body).hexdigest() != artifact_id:
            raise ValueError("candidate_simulation_v3_cas_content_mismatch")
        try:
            payload = canon.from_canonical_bytes(body)
            if manifest.kind == _CANDIDATE_SIMULATION_INPUT_KIND:
                record: object = CandidateSimulationN5InputV3.model_validate(payload)
            elif manifest.kind == _CANDIDATE_SIMULATION_EXECUTION_KIND:
                record = CandidateSimulationExecutionV3.model_validate(payload)
            else:
                raise ValueError("candidate_simulation_v3_manifest_kind_mismatch")
        except (TypeError, ValueError) as exc:
            raise ValueError("candidate_simulation_v3_record_invalid") from exc
        is_input = type(record) is CandidateSimulationN5InputV3
        expected_kind = (
            _CANDIDATE_SIMULATION_INPUT_KIND
            if is_input
            else _CANDIDATE_SIMULATION_EXECUTION_KIND
        )
        expected_schema = record.schema_version
        if (
            manifest.kind != expected_kind
            or manifest.media_type != "application/json"
            or manifest.artifact_schema is None
            or manifest.artifact_schema.name != expected_schema
            or manifest.artifact_schema.version != "3.0"
        ):
            raise ValueError("candidate_simulation_v3_manifest_profile_mismatch")
        if artifact_ref_identity_key(ref) != artifact_ref_identity_key(
            ArtifactRef(
                artifact_id=manifest.artifact_id,
                kind=manifest.kind,
                media_type=manifest.media_type,
                manifest_profile_sha256=(
                    ManifestLifecycle.profile_sha256(manifest)
                    if ref.manifest_profile_sha256 is not None
                    else None
                ),
            )
        ):
            raise ValueError("candidate_simulation_v3_selected_view_mismatch")
        options = _candidate_simulation_write_options(
            kind=expected_kind,
            schema_name=expected_schema,
            schema_version="3.0",
            job_id=record.job_id,
            run_id=record.run_id,
            tenant_id=record.tenant_id,
            cell_id=record.cell_id,
            source_ref=str(record.n4_source_ref.artifact_id),
            input_refs=(
                (
                    input_ref_from_artifact_ref(record.n4_source_ref, role="n4_source"),
                    input_ref_from_artifact_ref(
                        record.context_job_ref, role="cycle_substrate_context_job"
                    ),
                )
                if is_input
                else (
                    input_ref_from_artifact_ref(record.n5_input_ref, role="n5_input"),
                    input_ref_from_artifact_ref(record.n4_source_ref, role="n4_source"),
                    input_ref_from_artifact_ref(
                        record.context_job_ref, role="cycle_substrate_context_job"
                    ),
                    input_ref_from_artifact_ref(record.n5_result_ref, role="n5_result"),
                )
            ),
        )
        if not _has_owner_profile(manifest, options):
            raise ValueError("candidate_simulation_v3_owner_profile_mismatch")
        if (
            record.run_id != expected_run_id
            or (expected_job_id is not None and record.job_id != expected_job_id)
            or (expected_tenant_id is not None and record.tenant_id != expected_tenant_id)
            or (expected_cell_id is not None and record.cell_id != expected_cell_id)
        ):
            raise ValueError("candidate_simulation_v3_identity_mismatch")
        source = self.load(record.n4_source_ref, run_id=record.run_id)
        source_candidate = next(
            (
                candidate
                for candidate in source.generation_result.candidates
                if candidate.candidate_id == record.original_candidate_id
                and candidate.atom.content_hash == record.original_n4_atom_hash
            ),
            None,
        )
        if source_candidate is None:
            raise ValueError("candidate_simulation_v3_n4_source_membership_mismatch")
        from polisyos.runtime.quality.cycle_substrate import (
            CycleSubstrateContextArtifactOwner,
        )

        context_job = CycleSubstrateContextArtifactOwner(
            store=self.store
        ).resolve_historical_job_artifact(
            record.context_job_ref,
            problem=source.problem,
            expected_job_id=record.job_id,
            expected_run_id=record.run_id,
            expected_tenant_id=record.tenant_id,
            expected_cell_id=record.cell_id,
        )
        if (
            source.cycle_substrate_context is None
            or source.cycle_substrate_context.content_hash != context_job.context.content_hash
            or source.problem != context_job.problem
        ):
            raise ValueError("candidate_simulation_v3_context_job_binding_mismatch")
        if is_input:
            if (
                record.materialization.problem_ref != context_job.design_problem_ref
                or record.materialization.context_hash != context_job.context.content_hash
                or record.materialization.world_model_record_hash
                != context_job.context.world_model_record.content_hash
            ):
                raise ValueError("candidate_simulation_v3_input_context_mismatch")
        else:
            if (
                record.problem_ref != context_job.design_problem_ref
                or record.world_model_record_hash
                != context_job.context.world_model_record.content_hash
            ):
                raise ValueError("candidate_simulation_v3_execution_context_mismatch")
        if require_current_lease and (
            current_lease_resolver is None or not current_lease_resolver(record)
        ):
            raise ValueError("candidate_simulation_v3_current_lease_not_established")
        if type(record) is CandidateSimulationExecutionV3:
            input_record = self._load_candidate_simulation_input_v3(record.n5_input_ref)
            if (
                type(input_record) is not CandidateSimulationN5InputV3
                or artifact_ref_identity_key(input_record.n4_source_ref)
                != artifact_ref_identity_key(record.n4_source_ref)
                or artifact_ref_identity_key(input_record.context_job_ref)
                != artifact_ref_identity_key(record.context_job_ref)
                or input_record.profile_config_ref != record.profile_config_ref
                or input_record.original_candidate_id != record.original_candidate_id
                or input_record.original_candidate_hash != record.original_candidate_hash
                or input_record.original_n4_atom_hash != record.original_n4_atom_hash
                or input_record.materialization.derived_n5_atom.content_hash
                != record.derived_n5_atom_hash
                or input_record.materialization.problem_ref != record.problem_ref
                or input_record.materialization.world_model_record_hash
                != record.world_model_record_hash
            ):
                raise ValueError("candidate_simulation_v3_execution_input_mismatch")
            from polisyos.runtime.quality.generation_cycle import (
                JOINT_SIMULATION_RESULT_ARTIFACT_KIND,
                load_joint_simulation_result,
            )

            result = load_joint_simulation_result(
                record.n5_result_ref,
                store=self.store,
                expected_world_model_record_content_hash=record.world_model_record_hash,
                expected_atom_ids=(
                    input_record.materialization.derived_n5_atom.intervention_id,
                ),
            )
            if (
                result.receipt.payload_hash != record.n5_result_content_hash
                or record.n5_result_ref.kind != JOINT_SIMULATION_RESULT_ARTIFACT_KIND
            ):
                raise ValueError("candidate_simulation_v3_result_hash_mismatch")
        return record

    def _load_candidate_simulation_input_v3(self, ref: ArtifactRef) -> object:
        """Load one exact typed N5 input view through its persistence owner."""

        from polisyos.runtime.quality.candidate_simulation import (
            CandidateSimulationN5InputV3,
        )

        if not isinstance(ref, ArtifactRef):
            raise ValueError("candidate_simulation_v3_selected_ref_required")
        if not self.store.verify(ref).ok:
            raise ValueError("candidate_simulation_v3_input_cas_integrity_failed")
        manifest = self.store.get_manifest(ref)
        if not _ref_selects_manifest(ref, manifest):
            raise ValueError("candidate_simulation_v3_input_selected_view_mismatch")
        body = self.store.get_bytes(ref)
        if "sha256:" + hashlib.sha256(body).hexdigest() != str(ref.artifact_id):
            raise ValueError("candidate_simulation_v3_input_cas_content_mismatch")
        record = CandidateSimulationN5InputV3.model_validate(
            canon.from_canonical_bytes(body)
        )
        if (
            manifest.kind != _CANDIDATE_SIMULATION_INPUT_KIND
            or manifest.media_type != "application/json"
            or manifest.artifact_schema is None
            or manifest.artifact_schema.name != record.schema_version
            or manifest.artifact_schema.version != "3.0"
        ):
            raise ValueError("candidate_simulation_v3_input_manifest_mismatch")
        options = _candidate_simulation_write_options(
            kind=_CANDIDATE_SIMULATION_INPUT_KIND,
            schema_name=record.schema_version,
            schema_version="3.0",
            job_id=record.job_id,
            run_id=record.run_id,
            tenant_id=record.tenant_id,
            cell_id=record.cell_id,
            source_ref=str(record.n4_source_ref.artifact_id),
            input_refs=(
                input_ref_from_artifact_ref(record.n4_source_ref, role="n4_source"),
                input_ref_from_artifact_ref(
                    record.context_job_ref, role="cycle_substrate_context_job"
                ),
            ),
        )
        if not _has_owner_profile(manifest, options):
            raise ValueError("candidate_simulation_v3_input_owner_profile_mismatch")
        if artifact_ref_identity_key(ref) != artifact_ref_identity_key(
            ArtifactRef(
                artifact_id=manifest.artifact_id,
                kind=manifest.kind,
                media_type=manifest.media_type,
                manifest_profile_sha256=(
                    ManifestLifecycle.profile_sha256(manifest)
                    if ref.manifest_profile_sha256 is not None
                    else None
                ),
            )
        ):
            raise ValueError("candidate_simulation_v3_input_selected_view_mismatch")
        return record

    def persist_candidate_proposal(
        self,
        *,
        job_id: str,
        run_id: str,
        tenant_id: str,
        cell_id: str,
        raw_request: str,
        problem: DesignProblem,
        proposal: n4.N4CandidateProposalSource,
        simulation_disposition: N4CandidateProposalSimulationDisposition | None = None,
    ) -> artifacts.ArtifactRef:
        """Persist N4 output through the runtime-supplied CAS and its typed outcome."""
        if simulation_disposition is not None:
            simulation_disposition = N4CandidateProposalSimulationDisposition.model_validate(
                simulation_disposition.model_dump(mode="python")
            )
        if problem.nl_provenance.raw_request != raw_request:
            raise ValueError("n4_candidate_proposal_request_mismatch")
        _assert_n4_candidate_problem_owner_context(
            problem,
            job_id=job_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
        problem_ref = gy_content_hash(problem.model_dump(mode="json"))
        if proposal.design_problem_ref != problem_ref:
            raise ValueError("n4_candidate_proposal_problem_mismatch")
        payload = {
            "job_id": job_id,
            "run_id": run_id,
            "tenant_id": tenant_id,
            "cell_id": cell_id,
            "request_hash": "sha256:" + hashlib.sha256(raw_request.encode("utf-8")).hexdigest(),
            "design_problem_ref": problem_ref,
            "problem": problem,
            "proposal": proposal,
        }
        if simulation_disposition is None:
            draft = N4CandidateProposalRecord.model_construct(
                **payload,
                content_hash="sha256:" + "0" * 64,
            ).model_dump(mode="python", exclude={"content_hash"})
            write_options = _n4_candidate_proposal_write_options()
        else:
            payload["simulation_disposition"] = simulation_disposition
            draft = N4CandidateProposalSimulationRecord.model_construct(
                **payload,
                content_hash="sha256:" + "0" * 64,
            ).model_dump(mode="python", exclude={"content_hash"})
            write_options = _n4_candidate_proposal_v2_write_options()
        draft["content_hash"] = _source_content_hash(draft)
        artifact = (
            N4CandidateProposalRecord.model_validate(draft)
            if simulation_disposition is None
            else N4CandidateProposalSimulationRecord.model_validate(draft)
        )
        body = canon.to_canonical_bytes(artifact, _SOURCE_CANON)
        return self.store.put_bytes(body, write_options)

    def load_candidate_proposal(
        self,
        ref: artifacts.ArtifactRef | N4CandidateProposalLocator | Mapping[str, Any],
        *,
        job_id: str,
        run_id: str,
        tenant_id: str,
        cell_id: str,
        raw_request: str,
    ) -> N4CandidateProposalRecord | N4CandidateProposalSimulationRecord:
        """Verify exact bytes, owner profile, and served job/tenant identity."""
        locator = (
            ref
            if isinstance(ref, N4CandidateProposalLocator)
            else N4CandidateProposalLocator(artifact_ref=ref)
            if isinstance(ref, artifacts.ArtifactRef)
            else N4CandidateProposalLocator.model_validate(ref)
        )
        artifact_ref = locator.artifact_ref
        # Core's selector-aware API accepts the canonical ref. Keep a narrow
        # compatibility path while this slice is replayed on the pre-R9 base,
        # whose refs cannot express a selected manifest view.
        selected_ref: artifacts.ArtifactID | artifacts.ArtifactRef = (
            artifact_ref
            if "manifest_profile_sha256" in artifacts.ArtifactRef.model_fields
            else artifact_ref.artifact_id
        )
        if not self.store.verify(selected_ref).ok:
            raise ValueError("n4_candidate_proposal_cas_integrity_failed")
        manifest = self.store.get_manifest(selected_ref)
        v1_owner_profile = _has_n4_candidate_proposal_owner_profile(manifest)
        v2_owner_profile = _has_n4_candidate_proposal_v2_owner_profile(manifest)
        if v1_owner_profile == v2_owner_profile:
            raise ValueError("n4_candidate_proposal_owner_profile_mismatch")
        body = self.store.get_bytes(selected_ref)
        if "sha256:" + hashlib.sha256(body).hexdigest() != str(artifact_ref.artifact_id):
            raise ValueError("n4_candidate_proposal_cas_content_mismatch")
        payload = canon.from_canonical_bytes(body)
        record_type = (
            N4CandidateProposalRecord
            if v1_owner_profile
            else N4CandidateProposalSimulationRecord
        )
        artifact = record_type.model_validate(payload)
        expected = {
            "job_id": job_id,
            "run_id": run_id,
            "tenant_id": tenant_id,
            "cell_id": cell_id,
            "request_hash": "sha256:" + hashlib.sha256(raw_request.encode("utf-8")).hexdigest(),
        }
        for field_name, value in expected.items():
            if getattr(artifact, field_name) != value:
                label = "tenant" if field_name == "tenant_id" else field_name.removesuffix("_id")
                raise ValueError(f"n4_candidate_proposal_{label}_binding_mismatch")
        return artifact

    def load_candidate_proposal_for_served_job(
        self,
        ref: artifacts.ArtifactRef | N4CandidateProposalLocator | Mapping[str, Any],
        *,
        job_id: str,
        run_id: str,
        tenant_id: str,
        cell_id: str,
        raw_request: str,
    ) -> N4CandidateProposalRecord | N4CandidateProposalSimulationRecord:
        """Admit a current served proposal only when inner provenance matches its owner.

        Historical v1 proposals remain byte-exact; current workers use this
        owner-reconciling boundary before consuming either proposal schema.
        """
        artifact = self.load_candidate_proposal(
            ref,
            job_id=job_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            raw_request=raw_request,
        )
        _assert_n4_candidate_problem_owner_context(
            artifact.problem,
            job_id=job_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
        return artifact

    def persist(
        self,
        *,
        run_id: str,
        cycle_index: int,
        problem: DesignProblem,
        organ: n4.DesignGenerationOrganRun,
        execution_scope: ExecutionScope = "production",
    ) -> str:
        """Persist original producer objects once; never recover them from summaries."""
        return str(
            self.persist_ref(
                run_id=run_id,
                cycle_index=cycle_index,
                problem=problem,
                organ=organ,
                execution_scope=execution_scope,
            ).artifact_id
        )

    def persist_ref(
        self,
        *,
        run_id: str,
        cycle_index: int,
        problem: DesignProblem,
        organ: n4.DesignGenerationOrganRun,
        execution_scope: ExecutionScope = "production",
    ) -> ArtifactRef:
        """Persist original N4 bytes and return the exact owner-selected view."""

        payload = {
            "run_id": run_id,
            "cycle_index": cycle_index,
            "problem": problem,
            "execution_scope": execution_scope,
            **_organ_source_payload(organ),
        }
        draft = GenerationSourceHandoff.model_construct(
            **payload,
            synthetic=generation_source_synthetic(
                organ, problem=problem, execution_scope=execution_scope
            ),
            content_hash="sha256:" + "0" * 64,
        ).model_dump(mode="python", exclude={"content_hash"})
        draft["content_hash"] = _source_content_hash(draft)
        artifact = GenerationSourceHandoff.model_validate(draft)
        body = canon.to_canonical_bytes(artifact, _SOURCE_CANON)
        ref = self.store.put_bytes(
            body,
            _source_write_options(),
        )
        return ref

    def load(self, ref: ArtifactRef | str, *, run_id: str) -> GenerationSourceHandoff:
        """Verify Core custody, exact typed source and its canonical run binding."""
        artifact_id = str(ref.artifact_id) if isinstance(ref, ArtifactRef) else ref
        if not self.store.verify(ref).ok:
            raise ValueError("generation_source_cas_integrity_failed")
        manifest = self.store.get_manifest(ref)
        if isinstance(ref, ArtifactRef) and not _ref_selects_manifest(ref, manifest):
            raise ValueError("generation_source_selected_view_mismatch")
        if not _has_source_owner_profile(manifest):
            raise ValueError("generation_source_owner_profile_mismatch")
        body = self.store.get_bytes(ref)
        if "sha256:" + hashlib.sha256(body).hexdigest() != artifact_id:
            raise ValueError("generation_source_cas_content_mismatch")
        artifact = GenerationSourceHandoff.model_validate(canon.from_canonical_bytes(body))
        if artifact.run_id != run_id:
            raise ValueError("generation_source_run_mismatch")
        return artifact

    def resolve(
        self,
        *,
        refs: Sequence[ArtifactRef | str],
        run_id: str,
        summary: CandidateSummary,
        problem: DesignProblem,
    ) -> GenerationSourceResolution:
        """Resolve the whole source set before selecting one exact candidate occurrence."""
        ref_keys = tuple(
            artifact_ref_identity_key(ref)
            if isinstance(ref, ArtifactRef)
            else (ref, "", "", None)
            for ref in refs
        )
        if len(ref_keys) != len(set(ref_keys)):
            return GenerationSourceResolution(status="not_established", code="source_ref_duplicate")
        problem_ref = gy_content_hash(problem.model_dump(mode="json"))
        identity = (problem_ref, summary.candidate_id, summary.content_hash)
        identity_matches = []
        matched = []
        try:
            for ref in refs:
                artifact = self.load(ref, run_id=run_id)
                if identity in artifact.identities():
                    identity_matches.append((ref, artifact))
                    if artifact.cycle_index == summary.cycle_index:
                        matched.append((ref, artifact))
        except (KeyError, OSError, ValueError, TypeError):
            return GenerationSourceResolution(status="not_established", code="source_replay_failed")
        if not matched:
            return GenerationSourceResolution(
                status="not_established",
                code="source_occurrence_missing" if identity_matches else "source_missing",
            )
        if len({item.source_identity_hash() for _, item in matched}) != 1:
            return GenerationSourceResolution(
                status="not_established",
                code="source_ambiguous",
            )
        ref, artifact = matched[0]
        source = next(
            item for item in artifact.candidate_sources if item.candidate_id == identity[1]
        )
        candidate = next(
            item
            for item in artifact.generation_result.candidates
            if item.candidate_id == identity[1]
        )
        context = artifact.cycle_substrate_context
        context = revalidate_cycle_substrate_context(context)
        reference = artifact.reference()
        result = {
            "world_model_record": context.world_model_record,
            "grounding_decision_certificate": source.grounding_decision_certificate,
            "credal_reference": reference,
        }
        intervention = next(
            item
            for item in artifact.trinity_bundle.policy_spec.interventions
            if item.intervention_id == source.intervention_id
        )
        parameter = n4._candidate_parameter_value(intervention, default=None)
        if context.intervention_substrate is not None and parameter is not None:
            from polisyos.runtime.quality.promotion_sequence import _EffectObligationWriterInput

            # Non-scalar parameters stay absent; no catalog value is substituted.
            with suppress(ValueError):
                writer = _EffectObligationWriterInput(
                    intervention_atom=candidate.atom,
                    intervention_substrate=context.intervention_substrate,
                    world_model_record=context.world_model_record,
                    operator_kind=candidate.atom.operator_kind.trinity_kind,
                    parameter_value=parameter,
                    proposal=source.proposal,
                    proposal_id=source.proposal_id,
                    declared_estimand=artifact.problem.outcome_of_interest.estimand,
                    causal_mechanism_ref=None,
                )
                # Only the existing writer DTO owns its JSON wire projection.
                # The capsule above keeps the exact original typed proposal.
                proposal = writer.model_dump(mode="json")["proposal"]
                if not _writer_projection_preserves_grounding(
                    source=source, reference=reference, proposal=proposal
                ):
                    return GenerationSourceResolution(
                        status="not_established",
                        code="effect_writer_projection_grounding_mismatch",
                        source_ref=(
                            str(ref.artifact_id) if isinstance(ref, ArtifactRef) else ref
                        ),
                    )
                result["effect_obligation_writer_input"] = writer.model_copy(
                    update={"proposal": proposal}
                )
        return GenerationSourceResolution(
            status="resolved",
            code="candidate_sources_replayed",
            source_ref=(str(ref.artifact_id) if isinstance(ref, ArtifactRef) else ref),
            context=result,
        )

    def preservation_receipt(
        self,
        *,
        run_id: str,
        refs: Sequence[ArtifactRef | str],
        expected: Sequence[Identity],
        prior_issues: Sequence[str] = (),
        scope_synthetic: Literal[True] | None = None,
    ) -> GenerationSourcePreservationReceipt:
        """Re-read every persisted candidate and compare complete identity sets."""
        from polisyos.runtime.quality.generation_cycle import GenerationSourcePreservationReceipt

        issues = list(prior_issues)
        retained: list[Identity] = []
        owners: dict[Identity, str] = {}
        synthetic = scope_synthetic
        ref_keys = tuple(
            artifact_ref_identity_key(ref)
            if isinstance(ref, ArtifactRef)
            else (ref, "", "", None)
            for ref in refs
        )
        if len(ref_keys) != len(set(ref_keys)):
            issues.append("source_ref_duplicate")
        for ref in refs:
            try:
                artifact = self.load(ref, run_id=run_id)
                source_ref = str(ref.artifact_id) if isinstance(ref, ArtifactRef) else ref
                if isinstance(ref, ArtifactRef):
                    default_manifest = self.store.get_manifest(source_ref)
                    if not _ref_selects_manifest(ref, default_manifest):
                        issues.append("source_selected_view_not_retained_by_n6_id")
                source_hash = artifact.source_identity_hash()
                for identity in artifact.identities():
                    if identity in owners and owners[identity] != source_hash:
                        issues.append("source_identity_conflict")
                    owners[identity] = source_hash
                    retained.append(identity)
                if artifact.synthetic is True:
                    synthetic = True
            except (KeyError, OSError, ValueError, TypeError):
                issues.append("source_replay_failed")
        if set(expected) != set(retained):
            issues.append("source_identity_set_mismatch")
        payload = {
            "run_id": run_id,
            "source_refs": tuple(
                str(ref.artifact_id) if isinstance(ref, ArtifactRef) else ref
                for ref in refs
            ),
            "synthetic": synthetic,
            "expected_identity_count": len(set(expected)),
            "expected_identity_digest": gy_content_hash(sorted(set(expected))),
            "retained_identity_count": len(set(retained)),
            "retained_identity_digest": gy_content_hash(sorted(set(retained))),
            "issues": tuple(sorted(set(issues))),
            "status": "drift" if issues else ("strangled" if expected else "not_established"),
        }
        draft = GenerationSourcePreservationReceipt.model_construct(
            **payload, content_hash="sha256:" + "0" * 64
        ).model_dump(mode="json", exclude={"content_hash"})
        return GenerationSourcePreservationReceipt.model_validate(
            {**draft, "content_hash": gy_content_hash(draft)}
        )
