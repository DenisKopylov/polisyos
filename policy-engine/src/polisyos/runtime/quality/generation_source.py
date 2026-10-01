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
from polisyos.data_forge.domains.academic.knowledge.skg_versioning import (
    ConfidenceLayerVintage,
    _confidence_layer_vintage_for_sha256,
)
from polisyos.ir import TrinityBundle  # noqa: TC001
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality import design_generation as n4
from polisyos.runtime.quality.candidate_simulation import (
    CandidateSimulationScenarioProfile,
    CandidateSimulationSyntheticModelDeclarationV1,
    candidate_simulation_profile_ref,
)
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
N4_CANDIDATE_SCENARIO_SOURCE_LOCATOR_SCHEMA = (
    "policyos.runtime.quality.n4_candidate_scenario_source_locator.v1"
)
Identity = tuple[str, str, str]
ExecutionScope = Literal["production", "contract_testing"]
_SOURCE_CANON = canon.CanonSpec(forbid_floats=False, exclude_none=False)
_CANDIDATE_SIMULATION_INPUT_KIND = "runtime.quality.candidate_simulation_n5_input"
_CANDIDATE_SIMULATION_EXECUTION_KIND = "runtime.quality.candidate_simulation_execution"
_N4_CANDIDATE_SCENARIO_SOURCE_KIND = "runtime.quality.n4_candidate_scenario_source"
_N4_CANDIDATE_SCENARIO_SOURCE_SCHEMA = (
    "policyos.runtime.quality.n4_candidate_scenario_source.v1"
)
_N4_CANDIDATE_SCENARIO_SOURCE_V2_SCHEMA = (
    "policyos.runtime.quality.n4_candidate_scenario_source.v2"
)
_CANDIDATE_MODEL_DECLARATION_KIND = (
    "runtime.quality.candidate_simulation_model_declaration"
)


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


def _candidate_scenario_source_write_options(
    *,
    job_id: str,
    run_id: str,
    tenant_id: str,
    cell_id: str,
    context_job_ref: ArtifactRef,
    source_ref: str,
) -> artifacts.ArtifactWriteOptions:
    """Bind the proposal-only N4 source to its selected context-job view."""

    return artifacts.ArtifactWriteOptions(
        kind=_N4_CANDIDATE_SCENARIO_SOURCE_KIND,
        media_type="application/json",
        schema=artifacts.SchemaInfo(
            name=_N4_CANDIDATE_SCENARIO_SOURCE_SCHEMA,
            version="1.0",
        ),
        producer=artifacts.ProducerInfo(component=__name__, version="1.0"),
        inputs=[
            input_ref_from_artifact_ref(
                context_job_ref,
                role="cycle_substrate_context_job",
            )
        ],
        tenant_context=ArtifactTenantContextInfo(tenant_id=tenant_id, cell_id=cell_id),
        same_input_closure=ArtifactSameInputClosureInfo(
            closure_id=f"candidate-scenario-source:{run_id}:{job_id}:{source_ref}",
            status="candidate_only",
            run_id=run_id,
            job_id=job_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        ),
    )


def _candidate_scenario_source_v2_write_options(
    *,
    source: N4CandidateScenarioSourceRecordV1,
    model_declaration_ref: ArtifactRef,
    ncm_ref: ArtifactRef,
) -> artifacts.ArtifactWriteOptions:
    """Bind V2 source to the context and exact selected model views."""
    return artifacts.ArtifactWriteOptions(
        kind=_N4_CANDIDATE_SCENARIO_SOURCE_KIND,
        media_type="application/json",
        schema=artifacts.SchemaInfo(
            name=_N4_CANDIDATE_SCENARIO_SOURCE_V2_SCHEMA,
            version="2.0",
        ),
        producer=artifacts.ProducerInfo(component=__name__, version="1.0"),
        inputs=[
            input_ref_from_artifact_ref(
                source.context_job_ref,
                role="cycle_substrate_context_job",
            ),
            input_ref_from_artifact_ref(
                model_declaration_ref,
                role="candidate_model_declaration",
            ),
            input_ref_from_artifact_ref(ncm_ref, role="candidate_ncm_spec"),
        ],
        tenant_context=ArtifactTenantContextInfo(
            tenant_id=source.tenant_id,
            cell_id=source.cell_id,
        ),
        same_input_closure=ArtifactSameInputClosureInfo(
            closure_id=(
                f"candidate-scenario-source-v2:{source.run_id}:{source.job_id}:"
                f"{source.design_problem_ref}"
            ),
            status="candidate_only",
            run_id=source.run_id,
            job_id=source.job_id,
            tenant_id=source.tenant_id,
            cell_id=source.cell_id,
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


class N4CandidateScenarioSourceLocator(_StrictModel):
    """Versioned pointer to a configured-profile N4 scenario-source record."""

    schema_version: Literal[
        "policyos.runtime.quality.n4_candidate_scenario_source_locator.v1"
    ] = N4_CANDIDATE_SCENARIO_SOURCE_LOCATOR_SCHEMA
    artifact_ref: artifacts.ArtifactRef

    @model_validator(mode="after")
    def _scenario_source_owner_view(self) -> N4CandidateScenarioSourceLocator:
        if (
            self.artifact_ref.kind != _N4_CANDIDATE_SCENARIO_SOURCE_KIND
            or self.artifact_ref.media_type != "application/json"
        ):
            raise ValueError(
                "n4_candidate_scenario_source_locator_owner_profile_mismatch"
            )
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


class N4CandidateScenarioSourceRecordV1(_StrictModel):
    """Versioned proposal source for a profile-limited N5 candidate scenario.

    This record is not a normal CGF generation handoff. It retains the exact
    proposal and candidate atom, while explicitly excluding K_ref confidence
    and all grounding/authority claims.
    """

    schema_version: Literal[
        "policyos.runtime.quality.n4_candidate_scenario_source.v1"
    ] = _N4_CANDIDATE_SCENARIO_SOURCE_SCHEMA
    authority_purpose: Literal["candidate_scenario_n5_only"] = (
        "candidate_scenario_n5_only"
    )
    status: Literal["candidate_unverified", "candidate_limited"] = "candidate_limited"
    n5_status: Literal["not_run"] = "not_run"
    n8_status: Literal["not_run"] = "not_run"
    n9_status: Literal["not_admitted"] = "not_admitted"
    s8_status: Literal["blocked"] = "blocked"
    job_id: str = Field(..., min_length=1, strict=True)
    run_id: str = Field(..., min_length=1, strict=True)
    tenant_id: str = Field(..., min_length=1, strict=True)
    cell_id: str = Field(..., min_length=1, strict=True)
    design_problem_ref: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$", strict=True)
    cycle_problem_ref: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$", strict=True)
    problem: DesignProblem
    proposal: n4.N4CandidateProposalSource
    candidate: n4.N4CandidateScenarioProposalCandidate | None = None
    profile: CandidateSimulationScenarioProfile
    profile_config_ref: str = Field(..., min_length=1, strict=True)
    candidate_limitation_code: Literal[
        "candidate_scenario_profile_action_not_matched",
        "candidate_scenario_worker_lease_not_current",
        "candidate_scenario_proposal_atom_not_established",
    ] | None = None
    context_job_ref: ArtifactRef
    context_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$", strict=True)
    world_model_record_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$", strict=True)
    k_ref_limitation_code: Literal[
        "candidate_scenario_l2_not_consumed",
        "historical_l2_confidence_withheld",
        "full_credal_reference_not_established",
        "full_credal_reference_not_consumed",
    ]
    l2_confidence_vintage: ConfidenceLayerVintage | None = None
    credal_reference_payload: Literal[None] = None
    l2_confidence_forwarded: Literal[False] = False
    content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$", strict=True)

    @model_validator(mode="after")
    def _verify_proposal_source_bindings(self) -> N4CandidateScenarioSourceRecordV1:
        from polisyos.runtime.quality.cycle_substrate import (
            _cycle_job_v1_design_problem_ref,
            _cycle_job_v1_profile_selection_ref,
        )

        if type(self.profile) is not CandidateSimulationScenarioProfile:
            raise ValueError("n4_candidate_scenario_profile_untyped")
        if self.context_job_ref.kind != "runtime.quality.cycle_substrate_context_job":
            raise ValueError("n4_candidate_scenario_context_job_kind_mismatch")
        if self.context_job_ref.media_type != "application/json":
            raise ValueError("n4_candidate_scenario_context_job_media_mismatch")
        if self.profile_config_ref != candidate_simulation_profile_ref(self.profile):
            raise ValueError("n4_candidate_scenario_profile_ref_mismatch")
        if (
            self.design_problem_ref != gy_content_hash(self.problem.model_dump(mode="json"))
            or self.proposal.design_problem_ref != self.design_problem_ref
            or self.cycle_problem_ref != _cycle_job_v1_design_problem_ref(self.problem)
            or self.profile.profile_selection_ref
            != _cycle_job_v1_profile_selection_ref(self.problem)
        ):
            raise ValueError("n4_candidate_scenario_problem_binding_mismatch")
        if self.candidate is None:
            if (
                self.status != "candidate_limited"
                or self.candidate_limitation_code is None
            ):
                raise ValueError("n4_candidate_scenario_candidate_missing")
        else:
            interventions = tuple(
                item
                for item in self.proposal.trinity_bundle.policy_spec.interventions
                if item.intervention_id == self.candidate.intervention_id
            )
            if (
                len(interventions) != 1
                or self.candidate.atom.problem_frame_ref != self.design_problem_ref
            ):
                raise ValueError("n4_candidate_scenario_proposal_membership_mismatch")
            if (
                self.candidate.atom.intervention_id != interventions[0].intervention_id
                or self.candidate.atom.operator_kind.trinity_kind != interventions[0].kind
                or self.candidate.atom.direct_effect_bundle.params != interventions[0].params
                or self.candidate.atom.target_world_slots
                != (self.profile.rule.target_world_slot,)
                or self.candidate.atom.causal_do_expr.write_variables
                != (self.profile.rule.target_world_slot,)
                or self.status != "candidate_unverified"
                or self.candidate_limitation_code is not None
            ):
                raise ValueError("n4_candidate_scenario_atom_proposal_binding_mismatch")
            if self.candidate.atom.status != "candidate_unverified":
                raise ValueError("n4_candidate_scenario_atom_not_candidate")
        if self.l2_confidence_vintage is not None:
            if type(self.l2_confidence_vintage) is not ConfidenceLayerVintage:
                raise ValueError("n4_candidate_scenario_l2_vintage_untyped")
            owner_vintage = _confidence_layer_vintage_for_sha256(
                self.l2_confidence_vintage.snapshot_sha256
            )
            if (
                self.k_ref_limitation_code != "historical_l2_confidence_withheld"
                or owner_vintage != self.l2_confidence_vintage
            ):
                raise ValueError("n4_candidate_scenario_l2_vintage_mismatch")
        elif self.k_ref_limitation_code == "historical_l2_confidence_withheld":
            raise ValueError("n4_candidate_scenario_l2_vintage_missing")
        if self.l2_confidence_forwarded or self.credal_reference_payload is not None:
            raise ValueError("n4_candidate_scenario_l2_confidence_forwarded")
        if self.content_hash != _source_content_hash(
            self.model_dump(mode="python", exclude={"content_hash"})
        ):
            raise ValueError("n4_candidate_scenario_source_content_hash_mismatch")
        return self


class N4CandidateScenarioSourceRecordV2(_StrictModel):
    """Versioned selected-view extension around unchanged historical source V1."""

    schema_version: Literal[
        "policyos.runtime.quality.n4_candidate_scenario_source.v2"
    ] = _N4_CANDIDATE_SCENARIO_SOURCE_V2_SCHEMA
    source_record: N4CandidateScenarioSourceRecordV1
    model_declaration: CandidateSimulationSyntheticModelDeclarationV1
    model_declaration_ref: ArtifactRef
    ncm_ref: ArtifactRef
    world_model_record_id: str = Field(..., min_length=1, strict=True)
    content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$", strict=True)

    @model_validator(mode="after")
    def _verify_v2_bindings(self) -> N4CandidateScenarioSourceRecordV2:
        source = self.source_record
        declaration = self.model_declaration
        if (
            source.profile_config_ref != declaration.profile_config_ref
            or source.profile.content_hash != declaration.profile_content_hash
            or source.profile.profile_selection_ref != declaration.profile_selection_ref
            or source.profile.rule.target_world_slot != declaration.target_world_slot
            or source.profile.rule.unit_id != declaration.target_unit_id
            or source.profile.n5.baseline_state.get(declaration.target_world_slot)
            != declaration.target_baseline
            or source.profile.n5.baseline_state.get(declaration.outcome_variable)
            != declaration.outcome_baseline
            or self.model_declaration_ref.kind != _CANDIDATE_MODEL_DECLARATION_KIND
            or self.model_declaration_ref.media_type != "application/json"
            or self.ncm_ref.kind != "ir.ncm_spec"
            or self.ncm_ref.media_type != "application/json"
            or not self.world_model_record_id
        ):
            raise ValueError("n4_candidate_scenario_v2_model_binding_mismatch")
        if self.content_hash != _source_content_hash(
            self.model_dump(mode="python", exclude={"content_hash"})
        ):
            raise ValueError("n4_candidate_scenario_v2_content_hash_mismatch")
        return self

    @property
    def status(self) -> str:
        return self.source_record.status

    @property
    def job_id(self) -> str:
        return self.source_record.job_id

    @property
    def run_id(self) -> str:
        return self.source_record.run_id

    @property
    def tenant_id(self) -> str:
        return self.source_record.tenant_id

    @property
    def cell_id(self) -> str:
        return self.source_record.cell_id

    @property
    def design_problem_ref(self) -> str:
        return self.source_record.design_problem_ref

    @property
    def cycle_problem_ref(self) -> str:
        return self.source_record.cycle_problem_ref

    @property
    def problem(self) -> DesignProblem:
        return self.source_record.problem

    @property
    def proposal(self) -> n4.N4CandidateProposalSource:
        return self.source_record.proposal

    @property
    def candidate(self) -> n4.N4CandidateScenarioProposalCandidate | None:
        return self.source_record.candidate

    @property
    def profile(self) -> CandidateSimulationScenarioProfile:
        return self.source_record.profile

    @property
    def profile_config_ref(self) -> str:
        return self.source_record.profile_config_ref

    @property
    def candidate_limitation_code(self) -> str | None:
        return self.source_record.candidate_limitation_code

    @property
    def context_job_ref(self) -> ArtifactRef:
        return self.source_record.context_job_ref

    @property
    def context_hash(self) -> str:
        return self.source_record.context_hash

    @property
    def world_model_record_hash(self) -> str:
        return self.source_record.world_model_record_hash

    @property
    def k_ref_limitation_code(self) -> str:
        return self.source_record.k_ref_limitation_code

    @property
    def l2_confidence_vintage(self) -> ConfidenceLayerVintage | None:
        return self.source_record.l2_confidence_vintage


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

    def persist_candidate_model_declaration(
        self,
        *,
        declaration: CandidateSimulationSyntheticModelDeclarationV1,
        job_id: str,
        run_id: str,
        tenant_id: str,
        cell_id: str,
    ) -> ArtifactRef:
        """Persist the server-declared candidate model in the active job scope."""
        if type(declaration) is not CandidateSimulationSyntheticModelDeclarationV1:
            raise TypeError("candidate_simulation_model_declaration_untyped")
        record = CandidateSimulationSyntheticModelDeclarationV1.model_validate(
            declaration.model_dump(mode="python")
        )
        options = _candidate_simulation_write_options(
            kind=_CANDIDATE_MODEL_DECLARATION_KIND,
            schema_name=record.schema_version,
            schema_version="1.0",
            job_id=job_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            source_ref=record.profile_content_hash,
        )
        return self.store.put_bytes(canon.to_canonical_bytes(record, _SOURCE_CANON), options)

    def load_candidate_model_declaration(
        self,
        ref: ArtifactRef,
        *,
        expected_profile: CandidateSimulationScenarioProfile,
        expected_run_id: str,
        expected_job_id: str,
        expected_tenant_id: str,
        expected_cell_id: str,
    ) -> CandidateSimulationSyntheticModelDeclarationV1:
        """Replay one selected or default declaration view with its owner profile."""
        if not isinstance(ref, ArtifactRef):
            raise ValueError("candidate_simulation_model_declaration_selected_ref_required")
        if not self.store.verify(ref).ok:
            raise ValueError("candidate_simulation_model_declaration_integrity_failed")
        manifest = self.store.get_manifest(ref)
        if not _ref_selects_manifest(ref, manifest):
            raise ValueError("candidate_simulation_model_declaration_selected_view_mismatch")
        body = self.store.get_bytes(ref)
        if "sha256:" + hashlib.sha256(body).hexdigest() != str(ref.artifact_id):
            raise ValueError("candidate_simulation_model_declaration_content_mismatch")
        try:
            record = CandidateSimulationSyntheticModelDeclarationV1.model_validate(
                canon.from_canonical_bytes(body)
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("candidate_simulation_model_declaration_invalid") from exc
        if (
            manifest.kind != _CANDIDATE_MODEL_DECLARATION_KIND
            or manifest.media_type != "application/json"
            or manifest.artifact_schema is None
            or manifest.artifact_schema.name != record.schema_version
            or manifest.artifact_schema.version != "1.0"
        ):
            raise ValueError("candidate_simulation_model_declaration_manifest_mismatch")
        options = _candidate_simulation_write_options(
            kind=_CANDIDATE_MODEL_DECLARATION_KIND,
            schema_name=record.schema_version,
            schema_version="1.0",
            job_id=expected_job_id,
            run_id=expected_run_id,
            tenant_id=expected_tenant_id,
            cell_id=expected_cell_id,
            source_ref=record.profile_content_hash,
        )
        if not _has_owner_profile(manifest, options):
            raise ValueError("candidate_simulation_model_declaration_owner_profile_mismatch")
        if (
            record.profile_content_hash != expected_profile.content_hash
            or record.profile_selection_ref != expected_profile.profile_selection_ref
            or record.profile_config_ref != candidate_simulation_profile_ref(expected_profile)
        ):
            raise ValueError("candidate_simulation_model_declaration_profile_mismatch")
        return record

    def persist_candidate_ncm_selected_view(
        self,
        *,
        ncm_spec: object,
        declaration_ref: ArtifactRef,
        job_id: str,
        run_id: str,
        tenant_id: str,
        cell_id: str,
        profile_content_hash: str,
    ) -> ArtifactRef:
        """Use the existing IR NCM serializer with the runtime's full input ref."""
        from polisyos.ir.analytics.ncm import NCMSpec, persist_ncm_spec_selected_view

        if type(ncm_spec) is not NCMSpec:
            raise TypeError("candidate_simulation_ncm_spec_untyped")
        if not isinstance(declaration_ref, ArtifactRef):
            raise ValueError("candidate_simulation_ncm_declaration_ref_required")
        options = _candidate_simulation_write_options(
            kind="ir.ncm_spec",
            schema_name="ir.ncm_spec",
            schema_version="1.0",
            job_id=job_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            source_ref=profile_content_hash,
            input_refs=(
                input_ref_from_artifact_ref(
                    declaration_ref,
                    role="candidate_model_declaration",
                ),
            ),
        )
        ref = persist_ncm_spec_selected_view(
            self.store,
            ncm_spec,
            write_options=options,
        )
        if not isinstance(ref, ArtifactRef):
            raise ValueError("candidate_simulation_ncm_selected_ref_untyped")
        return ref

    def create_candidate_scenario_source_v2(
        self,
        *,
        source_record: N4CandidateScenarioSourceRecordV1,
        model_declaration: CandidateSimulationSyntheticModelDeclarationV1,
        model_declaration_ref: ArtifactRef,
        ncm_ref: ArtifactRef,
        world_model_record_id: str,
    ) -> N4CandidateScenarioSourceRecordV2:
        """Add selected model refs without changing the historical SourceV1 body."""
        payload = {
            "source_record": source_record,
            "model_declaration": model_declaration,
            "model_declaration_ref": model_declaration_ref,
            "ncm_ref": ncm_ref,
            "world_model_record_id": world_model_record_id,
        }
        draft = N4CandidateScenarioSourceRecordV2.model_construct(
            **payload,
            content_hash="sha256:" + "0" * 64,
        ).model_dump(mode="python", exclude={"content_hash"})
        return N4CandidateScenarioSourceRecordV2.model_validate(
            {**payload, "content_hash": _source_content_hash(draft)}
        )

    def persist_candidate_scenario_source_v2(
        self,
        *,
        source_record: N4CandidateScenarioSourceRecordV2,
    ) -> ArtifactRef:
        """Persist selected-view N4 source V2 with exact upstream manifest inputs."""
        if type(source_record) is not N4CandidateScenarioSourceRecordV2:
            raise TypeError("n4_candidate_scenario_source_v2_untyped")
        record = N4CandidateScenarioSourceRecordV2.model_validate(
            source_record.model_dump(mode="python")
        )
        options = _candidate_scenario_source_v2_write_options(
            source=record.source_record,
            model_declaration_ref=record.model_declaration_ref,
            ncm_ref=record.ncm_ref,
        )
        return self.store.put_bytes(canon.to_canonical_bytes(record, _SOURCE_CANON), options)

    def load_candidate_scenario_source_v2(
        self,
        ref: ArtifactRef,
        *,
        expected_run_id: str,
        expected_job_id: str,
        expected_tenant_id: str,
        expected_cell_id: str,
    ) -> N4CandidateScenarioSourceRecordV2:
        """Replay selected source, context, declaration, and NCM exact views."""
        if not isinstance(ref, ArtifactRef):
            raise ValueError("n4_candidate_scenario_source_selected_ref_required")
        if not self.store.verify(ref).ok:
            raise ValueError("n4_candidate_scenario_source_cas_integrity_failed")
        manifest = self.store.get_manifest(ref)
        if not _ref_selects_manifest(ref, manifest):
            raise ValueError("n4_candidate_scenario_source_selected_view_mismatch")
        body = self.store.get_bytes(ref)
        if "sha256:" + hashlib.sha256(body).hexdigest() != str(ref.artifact_id):
            raise ValueError("n4_candidate_scenario_source_cas_content_mismatch")
        try:
            source = N4CandidateScenarioSourceRecordV2.model_validate(
                canon.from_canonical_bytes(body)
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("n4_candidate_scenario_source_v2_invalid") from exc
        if (
            manifest.kind != _N4_CANDIDATE_SCENARIO_SOURCE_KIND
            or manifest.media_type != "application/json"
            or manifest.artifact_schema is None
            or manifest.artifact_schema.name != source.schema_version
            or manifest.artifact_schema.version != "2.0"
        ):
            raise ValueError("n4_candidate_scenario_source_v2_manifest_mismatch")
        options = _candidate_scenario_source_v2_write_options(
            source=source.source_record,
            model_declaration_ref=source.model_declaration_ref,
            ncm_ref=source.ncm_ref,
        )
        if not _has_owner_profile(manifest, options):
            raise ValueError("n4_candidate_scenario_source_v2_owner_profile_mismatch")
        if (
            source.run_id != expected_run_id
            or source.job_id != expected_job_id
            or source.tenant_id != expected_tenant_id
            or source.cell_id != expected_cell_id
        ):
            raise ValueError("n4_candidate_scenario_source_identity_mismatch")
        source_v1 = source.source_record
        from polisyos.runtime.quality.cycle_substrate import (
            CycleSubstrateContextArtifactOwner,
        )

        context_job = (
            CycleSubstrateContextArtifactOwner(store=self.store).resolve_historical_job_artifact(
                source_v1.context_job_ref,
                problem=source_v1.problem,
                expected_job_id=source_v1.job_id,
                expected_run_id=source_v1.run_id,
                expected_tenant_id=source_v1.tenant_id,
                expected_cell_id=source_v1.cell_id,
            )
        )
        context_slot_units = {
            item.slot_id: item.unit
            for item in context_job.context.world_model_record.policy_slot_map
        }
        if (
            context_job.problem != source_v1.problem
            or context_job.design_problem_ref != source_v1.cycle_problem_ref
            or context_job.context.content_hash != source_v1.context_hash
            or context_job.context.world_model_record.content_hash
            != source_v1.world_model_record_hash
            or context_job.context.world_model_record.world_model_record_id
            != source.world_model_record_id
            or str(source.ncm_ref.artifact_id)
            not in context_job.context.world_model_record.simulation_model_ref.ncm_refs
        ):
            raise ValueError("n4_candidate_scenario_source_v2_context_binding_mismatch")
        declaration = self.load_candidate_model_declaration(
            source.model_declaration_ref,
            expected_profile=source_v1.profile,
            expected_run_id=source_v1.run_id,
            expected_job_id=source_v1.job_id,
            expected_tenant_id=source_v1.tenant_id,
            expected_cell_id=source_v1.cell_id,
        )
        if (
            context_slot_units.get(declaration.target_world_slot)
            != declaration.target_unit_id
            or context_slot_units.get(declaration.outcome_variable)
            != declaration.outcome_unit_id
        ):
            raise ValueError("n4_candidate_scenario_source_v2_unit_binding_mismatch")
        ncm_manifest = self.store.get_manifest(source.ncm_ref)
        ncm_options = _candidate_simulation_write_options(
            kind="ir.ncm_spec",
            schema_name="ir.ncm_spec",
            schema_version="1.0",
            job_id=expected_job_id,
            run_id=expected_run_id,
            tenant_id=expected_tenant_id,
            cell_id=expected_cell_id,
            source_ref=declaration.profile_content_hash,
            input_refs=(
                input_ref_from_artifact_ref(
                    source.model_declaration_ref,
                    role="candidate_model_declaration",
                ),
            ),
        )
        if not _ref_selects_manifest(source.ncm_ref, ncm_manifest) or not _has_owner_profile(
            ncm_manifest, ncm_options
        ):
            raise ValueError("n4_candidate_scenario_source_v2_ncm_owner_profile_mismatch")
        from polisyos.ir.analytics.ncm import (
            candidate_ncm_spec_from_declaration,
            load_ncm_spec_selected_view,
        )

        ncm_spec = load_ncm_spec_selected_view(
            self.store,
            source.ncm_ref,
            expected_tenant_id=source_v1.tenant_id,
            expected_cell_id=source_v1.cell_id,
            expected_declaration_ref=source.model_declaration_ref,
        )
        expected_ncm_spec = candidate_ncm_spec_from_declaration(declaration)
        if ncm_spec.model_dump(mode="json") != expected_ncm_spec.model_dump(mode="json"):
            raise ValueError("n4_candidate_scenario_source_v2_ncm_declaration_mismatch")
        return source

    def load_candidate_scenario_source_for_n5(
        self,
        ref: ArtifactRef,
        *,
        expected_run_id: str,
        expected_job_id: str,
        expected_tenant_id: str,
        expected_cell_id: str,
    ) -> N4CandidateScenarioSourceRecordV1 | N4CandidateScenarioSourceRecordV2:
        """Dispatch a scenario source by its persisted manifest schema version."""
        manifest = self.store.get_manifest(ref)
        schema = manifest.artifact_schema
        if schema is None:
            raise ValueError("n4_candidate_scenario_source_manifest_mismatch")
        if schema.name == _N4_CANDIDATE_SCENARIO_SOURCE_SCHEMA and schema.version == "1.0":
            return self.load_candidate_scenario_source_v1(
                ref,
                expected_run_id=expected_run_id,
                expected_job_id=expected_job_id,
                expected_tenant_id=expected_tenant_id,
                expected_cell_id=expected_cell_id,
            )
        if schema.name == _N4_CANDIDATE_SCENARIO_SOURCE_V2_SCHEMA and schema.version == "2.0":
            return self.load_candidate_scenario_source_v2(
                ref,
                expected_run_id=expected_run_id,
                expected_job_id=expected_job_id,
                expected_tenant_id=expected_tenant_id,
                expected_cell_id=expected_cell_id,
            )
        raise ValueError("n4_candidate_scenario_source_schema_unsupported")

    def create_candidate_scenario_source_v1(
        self,
        *,
        status: Literal["candidate_unverified", "candidate_limited"],
        job_id: str,
        run_id: str,
        tenant_id: str,
        cell_id: str,
        design_problem_ref: str,
        cycle_problem_ref: str,
        problem: DesignProblem,
        proposal: n4.N4CandidateProposalSource,
        candidate: n4.N4CandidateScenarioProposalCandidate | None,
        profile: CandidateSimulationScenarioProfile,
        profile_config_ref: str,
        candidate_limitation_code: Literal[
            "candidate_scenario_profile_action_not_matched",
            "candidate_scenario_worker_lease_not_current",
            "candidate_scenario_proposal_atom_not_established",
        ] | None,
        context_job_ref: ArtifactRef,
        context_hash: str,
        world_model_record_hash: str,
        k_ref_limitation_code: Literal[
            "candidate_scenario_l2_not_consumed",
            "historical_l2_confidence_withheld",
            "full_credal_reference_not_established",
            "full_credal_reference_not_consumed",
        ],
        l2_confidence_vintage: ConfidenceLayerVintage | None,
        credal_reference_payload: None,
        l2_confidence_forwarded: Literal[False],
    ) -> N4CandidateScenarioSourceRecordV1:
        """Issue one immutable proposal-source record through this source owner."""

        payload = {
            "status": status,
            "job_id": job_id,
            "run_id": run_id,
            "tenant_id": tenant_id,
            "cell_id": cell_id,
            "design_problem_ref": design_problem_ref,
            "cycle_problem_ref": cycle_problem_ref,
            "problem": problem,
            "proposal": proposal,
            "candidate": candidate,
            "profile": profile,
            "profile_config_ref": profile_config_ref,
            "candidate_limitation_code": candidate_limitation_code,
            "context_job_ref": context_job_ref,
            "context_hash": context_hash,
            "world_model_record_hash": world_model_record_hash,
            "k_ref_limitation_code": k_ref_limitation_code,
            "l2_confidence_vintage": l2_confidence_vintage,
            "credal_reference_payload": credal_reference_payload,
            "l2_confidence_forwarded": l2_confidence_forwarded,
        }
        draft = N4CandidateScenarioSourceRecordV1.model_construct(
            **payload,
            content_hash="sha256:" + "0" * 64,
        ).model_dump(mode="python", exclude={"content_hash"})
        return N4CandidateScenarioSourceRecordV1.model_validate(
            {**payload, "content_hash": _source_content_hash(draft)}
        )

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

    def persist_candidate_scenario_source_v1(
        self,
        *,
        source_record: object,
    ) -> ArtifactRef:
        """Persist one typed N4 proposal source through the runtime artifact store."""

        if type(source_record) is not N4CandidateScenarioSourceRecordV1:
            raise TypeError("n4_candidate_scenario_source_untyped")
        record = N4CandidateScenarioSourceRecordV1.model_validate(
            source_record.model_dump(mode="python")
        )
        options = _candidate_scenario_source_write_options(
            job_id=record.job_id,
            run_id=record.run_id,
            tenant_id=record.tenant_id,
            cell_id=record.cell_id,
            context_job_ref=record.context_job_ref,
            source_ref=record.design_problem_ref,
        )
        return self.store.put_bytes(
            canon.to_canonical_bytes(record, _SOURCE_CANON),
            options,
        )

    def load_candidate_scenario_source_v1(
        self,
        ref: ArtifactRef,
        *,
        expected_run_id: str,
        expected_job_id: str,
        expected_tenant_id: str,
        expected_cell_id: str,
    ) -> N4CandidateScenarioSourceRecordV1:
        """Replay the exact selected proposal-source view and its context owner."""

        if not isinstance(ref, ArtifactRef):
            raise ValueError("n4_candidate_scenario_source_selected_ref_required")
        if not self.store.verify(ref).ok:
            raise ValueError("n4_candidate_scenario_source_cas_integrity_failed")
        manifest = self.store.get_manifest(ref)
        if not _ref_selects_manifest(ref, manifest):
            raise ValueError("n4_candidate_scenario_source_selected_view_mismatch")
        body = self.store.get_bytes(ref)
        artifact_id = str(ref.artifact_id)
        if "sha256:" + hashlib.sha256(body).hexdigest() != artifact_id:
            raise ValueError("n4_candidate_scenario_source_cas_content_mismatch")
        try:
            source = N4CandidateScenarioSourceRecordV1.model_validate(
                canon.from_canonical_bytes(body)
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("n4_candidate_scenario_source_record_invalid") from exc
        if (
            manifest.kind != _N4_CANDIDATE_SCENARIO_SOURCE_KIND
            or manifest.media_type != "application/json"
            or manifest.artifact_schema is None
            or manifest.artifact_schema.name != source.schema_version
            or manifest.artifact_schema.version != "1.0"
        ):
            raise ValueError("n4_candidate_scenario_source_manifest_mismatch")
        options = _candidate_scenario_source_write_options(
            job_id=source.job_id,
            run_id=source.run_id,
            tenant_id=source.tenant_id,
            cell_id=source.cell_id,
            context_job_ref=source.context_job_ref,
            source_ref=source.design_problem_ref,
        )
        if not _has_owner_profile(manifest, options):
            raise ValueError("n4_candidate_scenario_source_owner_profile_mismatch")
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
            raise ValueError("n4_candidate_scenario_source_selected_view_mismatch")
        if (
            source.run_id != expected_run_id
            or source.job_id != expected_job_id
            or source.tenant_id != expected_tenant_id
            or source.cell_id != expected_cell_id
        ):
            raise ValueError("n4_candidate_scenario_source_identity_mismatch")

        from polisyos.runtime.quality.cycle_substrate import (
            CycleSubstrateContextArtifactOwner,
        )

        context_job = CycleSubstrateContextArtifactOwner(
            store=self.store,
        ).resolve_historical_job_artifact(
            source.context_job_ref,
            problem=source.problem,
            expected_job_id=source.job_id,
            expected_run_id=source.run_id,
            expected_tenant_id=source.tenant_id,
            expected_cell_id=source.cell_id,
        )
        if (
            context_job.problem != source.problem
            or context_job.design_problem_ref != source.cycle_problem_ref
            or context_job.context.content_hash != source.context_hash
            or context_job.context.world_model_record.content_hash
            != source.world_model_record_hash
            or source.profile.context_inputs.world_model_record.content_hash
            != source.world_model_record_hash
            or source.profile.context_inputs.intervention_substrate is None
            or context_job.context.intervention_substrate is None
            or source.profile.context_inputs.intervention_substrate.content_hash
            != context_job.context.intervention_substrate.content_hash
        ):
            raise ValueError("n4_candidate_scenario_source_context_binding_mismatch")
        return source

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

    def persist_candidate_simulation_input_v4(
        self,
        *,
        input_record: object,
    ) -> ArtifactRef:
        """Persist the additive proposal-source N5 input with exact CAS views."""

        from polisyos.runtime.quality.candidate_simulation import (
            CandidateSimulationN5InputV4,
        )

        if type(input_record) is not CandidateSimulationN5InputV4:
            raise TypeError("candidate_simulation_n5_input_untyped")
        record = CandidateSimulationN5InputV4.model_validate(
            input_record.model_dump(mode="python")
        )
        options = _candidate_simulation_write_options(
            kind=_CANDIDATE_SIMULATION_INPUT_KIND,
            schema_name=record.schema_version,
            schema_version="4.0",
            job_id=record.job_id,
            run_id=record.run_id,
            tenant_id=record.tenant_id,
            cell_id=record.cell_id,
            source_ref=str(record.n4_source_ref.artifact_id),
            input_refs=(
                input_ref_from_artifact_ref(record.n4_source_ref, role="n4_source"),
                input_ref_from_artifact_ref(
                    record.context_job_ref,
                    role="cycle_substrate_context_job",
                ),
            ),
        )
        return self.store.put_bytes(canon.to_canonical_bytes(record, _SOURCE_CANON), options)

    def persist_candidate_simulation_input_v5(
        self,
        *,
        input_record: object,
    ) -> ArtifactRef:
        """Persist the declared-model N5 input with every selected CAS view."""
        from polisyos.runtime.quality.candidate_simulation import (
            CandidateSimulationN5InputV5,
        )

        if type(input_record) is not CandidateSimulationN5InputV5:
            raise TypeError("candidate_simulation_n5_input_untyped")
        record = CandidateSimulationN5InputV5.model_validate(
            input_record.model_dump(mode="python")
        )
        options = _candidate_simulation_write_options(
            kind=_CANDIDATE_SIMULATION_INPUT_KIND,
            schema_name=record.schema_version,
            schema_version="5.0",
            job_id=record.job_id,
            run_id=record.run_id,
            tenant_id=record.tenant_id,
            cell_id=record.cell_id,
            source_ref=str(record.n4_source_ref.artifact_id),
            input_refs=(
                input_ref_from_artifact_ref(record.n4_source_ref, role="n4_source"),
                input_ref_from_artifact_ref(
                    record.context_job_ref,
                    role="cycle_substrate_context_job",
                ),
                input_ref_from_artifact_ref(
                    record.model_declaration_ref,
                    role="candidate_model_declaration",
                ),
                input_ref_from_artifact_ref(record.ncm_ref, role="candidate_ncm_spec"),
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

    def persist_candidate_simulation_execution_v4(
        self,
        *,
        input_ref: ArtifactRef,
        simulation: object,
        handoff: object,
    ) -> ArtifactRef:
        """Persist the N5 result joined to exact proposal source and input views."""

        from polisyos.runtime.quality.candidate_simulation import (
            CandidateSimulationContextHandoff,
            CandidateSimulationExecutionV4,
            CandidateSimulationN5InputV4,
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
        input_record = self._load_candidate_simulation_input_v4(input_ref)
        if type(input_record) is not CandidateSimulationN5InputV4:
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
            "schema_version": "policyos.runtime.candidate_simulation.execution.v4",
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
        record = CandidateSimulationExecutionV4.model_validate(
            {**payload, "content_hash": gy_content_hash(payload)}
        )
        options = _candidate_simulation_write_options(
            kind=_CANDIDATE_SIMULATION_EXECUTION_KIND,
            schema_name=record.schema_version,
            schema_version="4.0",
            job_id=record.job_id,
            run_id=record.run_id,
            tenant_id=record.tenant_id,
            cell_id=record.cell_id,
            source_ref=str(record.n4_source_ref.artifact_id),
            input_refs=(
                input_ref_from_artifact_ref(input_ref, role="n5_input"),
                input_ref_from_artifact_ref(record.n4_source_ref, role="n4_source"),
                input_ref_from_artifact_ref(
                    record.context_job_ref,
                    role="cycle_substrate_context_job",
                ),
                input_ref_from_artifact_ref(record.n5_result_ref, role="n5_result"),
            ),
        )
        return self.store.put_bytes(canon.to_canonical_bytes(record, _SOURCE_CANON), options)

    def persist_candidate_simulation_execution_v5(
        self,
        *,
        input_ref: ArtifactRef,
        simulation: object,
        handoff: object,
    ) -> ArtifactRef:
        """Persist a served N5 result with the complete declared-model lineage."""
        from polisyos.runtime.quality.candidate_simulation import (
            CandidateSimulationContextHandoff,
            CandidateSimulationExecutionV5,
            CandidateSimulationN5InputV5,
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
        input_record = self._load_candidate_simulation_input_v5(input_ref)
        if type(input_record) is not CandidateSimulationN5InputV5:
            raise ValueError("candidate_simulation_input_ref_not_input_record")
        if (
            artifact_ref_identity_key(input_record.context_job_ref)
            != artifact_ref_identity_key(handoff.context_job_ref)
            or input_record.model_declaration_ref != handoff.model_declaration_ref
            or input_record.ncm_ref != handoff.ncm_ref
            or input_record.job_id != handoff.job_id
            or input_record.run_id != handoff.run_id
            or input_record.tenant_id != handoff.tenant_id
            or input_record.cell_id != handoff.cell_id
            or input_record.profile.content_hash != handoff.profile.content_hash
            or input_record.materialization.context_hash != handoff.context.content_hash
        ):
            raise ValueError("candidate_simulation_execution_handoff_mismatch")
        if (
            simulation.k_world_ref_before
            != input_record.materialization.world_model_record_hash
            or simulation.k_world_ref_after
            != input_record.materialization.world_model_record_hash
        ):
            raise ValueError("candidate_simulation_execution_world_binding_mismatch")
        payload = {
            "schema_version": "policyos.runtime.candidate_simulation.execution.v5",
            "authority_purpose": "candidate_scenario_n5_only",
            "n5_input_ref": input_ref,
            "n4_source_ref": input_record.n4_source_ref,
            "context_job_ref": input_record.context_job_ref,
            "model_declaration_ref": input_record.model_declaration_ref,
            "ncm_ref": input_record.ncm_ref,
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
        record = CandidateSimulationExecutionV5.model_validate(
            {**payload, "content_hash": gy_content_hash(payload)}
        )
        options = _candidate_simulation_write_options(
            kind=_CANDIDATE_SIMULATION_EXECUTION_KIND,
            schema_name=record.schema_version,
            schema_version="5.0",
            job_id=record.job_id,
            run_id=record.run_id,
            tenant_id=record.tenant_id,
            cell_id=record.cell_id,
            source_ref=str(record.n4_source_ref.artifact_id),
            input_refs=(
                input_ref_from_artifact_ref(input_ref, role="n5_input"),
                input_ref_from_artifact_ref(record.n4_source_ref, role="n4_source"),
                input_ref_from_artifact_ref(
                    record.context_job_ref,
                    role="cycle_substrate_context_job",
                ),
                input_ref_from_artifact_ref(
                    record.model_declaration_ref,
                    role="candidate_model_declaration",
                ),
                input_ref_from_artifact_ref(record.ncm_ref, role="candidate_ncm_spec"),
                input_ref_from_artifact_ref(
                    record.n5_result_ref,
                    role="n5_result",
                ),
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

    def resolve_candidate_simulation_v4(
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
        """Replay one proposal-profile input or execution with exact selected views."""

        from polisyos.runtime.quality.candidate_simulation import (
            CandidateSimulationExecutionV4,
            CandidateSimulationN5InputV4,
        )

        if not isinstance(ref, ArtifactRef):
            raise ValueError("candidate_simulation_v4_selected_ref_required")
        if not self.store.verify(ref).ok:
            raise ValueError("candidate_simulation_v4_cas_integrity_failed")
        manifest = self.store.get_manifest(ref)
        if not _ref_selects_manifest(ref, manifest):
            raise ValueError("candidate_simulation_v4_selected_view_mismatch")
        body = self.store.get_bytes(ref)
        if "sha256:" + hashlib.sha256(body).hexdigest() != str(ref.artifact_id):
            raise ValueError("candidate_simulation_v4_cas_content_mismatch")
        try:
            payload = canon.from_canonical_bytes(body)
            if manifest.kind == _CANDIDATE_SIMULATION_INPUT_KIND:
                record: object = CandidateSimulationN5InputV4.model_validate(payload)
            elif manifest.kind == _CANDIDATE_SIMULATION_EXECUTION_KIND:
                record = CandidateSimulationExecutionV4.model_validate(payload)
            else:
                raise ValueError("candidate_simulation_v4_manifest_kind_mismatch")
        except (TypeError, ValueError) as exc:
            raise ValueError("candidate_simulation_v4_record_invalid") from exc
        is_input = type(record) is CandidateSimulationN5InputV4
        expected_kind = (
            _CANDIDATE_SIMULATION_INPUT_KIND
            if is_input
            else _CANDIDATE_SIMULATION_EXECUTION_KIND
        )
        if (
            manifest.kind != expected_kind
            or manifest.media_type != "application/json"
            or manifest.artifact_schema is None
            or manifest.artifact_schema.name != record.schema_version
            or manifest.artifact_schema.version != "4.0"
        ):
            raise ValueError("candidate_simulation_v4_manifest_profile_mismatch")
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
            raise ValueError("candidate_simulation_v4_selected_view_mismatch")

        options = _candidate_simulation_write_options(
            kind=expected_kind,
            schema_name=record.schema_version,
            schema_version="4.0",
            job_id=record.job_id,
            run_id=record.run_id,
            tenant_id=record.tenant_id,
            cell_id=record.cell_id,
            source_ref=str(record.n4_source_ref.artifact_id),
            input_refs=(
                (
                    input_ref_from_artifact_ref(record.n4_source_ref, role="n4_source"),
                    input_ref_from_artifact_ref(
                        record.context_job_ref,
                        role="cycle_substrate_context_job",
                    ),
                )
                if is_input
                else (
                    input_ref_from_artifact_ref(record.n5_input_ref, role="n5_input"),
                    input_ref_from_artifact_ref(record.n4_source_ref, role="n4_source"),
                    input_ref_from_artifact_ref(
                        record.context_job_ref,
                        role="cycle_substrate_context_job",
                    ),
                    input_ref_from_artifact_ref(record.n5_result_ref, role="n5_result"),
                )
            ),
        )
        if not _has_owner_profile(manifest, options):
            raise ValueError("candidate_simulation_v4_owner_profile_mismatch")
        if (
            record.run_id != expected_run_id
            or (expected_job_id is not None and record.job_id != expected_job_id)
            or (expected_tenant_id is not None and record.tenant_id != expected_tenant_id)
            or (expected_cell_id is not None and record.cell_id != expected_cell_id)
        ):
            raise ValueError("candidate_simulation_v4_identity_mismatch")

        source = self.load_candidate_scenario_source_v1(
            record.n4_source_ref,
            expected_run_id=record.run_id,
            expected_job_id=record.job_id,
            expected_tenant_id=record.tenant_id,
            expected_cell_id=record.cell_id,
        )
        if (
            source.candidate is None
            or source.candidate.candidate_id != record.original_candidate_id
            or source.candidate.atom.content_hash != record.original_n4_atom_hash
            or source.candidate.atom.content_hash != record.original_candidate_hash
            or source.profile.content_hash != record.profile.content_hash
            or source.profile_config_ref != record.profile_config_ref
            or artifact_ref_identity_key(source.context_job_ref)
            != artifact_ref_identity_key(record.context_job_ref)
        ):
            raise ValueError("candidate_simulation_v4_n4_source_membership_mismatch")
        if is_input:
            materialization = record.materialization
            if (
                artifact_ref_identity_key(materialization.n4_source_ref)
                != artifact_ref_identity_key(record.n4_source_ref)
                or artifact_ref_identity_key(materialization.context_job_ref)
                != artifact_ref_identity_key(record.context_job_ref)
                or materialization.profile_hash != source.profile.content_hash
                or materialization.problem_ref != source.cycle_problem_ref
                or materialization.context_hash != source.context_hash
                or materialization.world_model_record_hash
                != source.world_model_record_hash
                or materialization.original_atom_hash != source.candidate.atom.content_hash
            ):
                raise ValueError("candidate_simulation_v4_input_context_mismatch")
        else:
            input_record = self._load_candidate_simulation_input_v4(record.n5_input_ref)
            if (
                type(input_record) is not CandidateSimulationN5InputV4
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
                raise ValueError("candidate_simulation_v4_execution_input_mismatch")
            from polisyos.runtime.quality.generation_cycle import (
                JOINT_SIMULATION_RESULT_ARTIFACT_KIND,
                load_joint_simulation_result,
            )

            result = load_joint_simulation_result(
                record.n5_result_ref,
                store=self.store,
                expected_world_model_record_content_hash=record.world_model_record_hash,
                expected_atom_ids=(input_record.materialization.derived_n5_atom.intervention_id,),
            )
            if (
                result.receipt.payload_hash != record.n5_result_content_hash
                or record.n5_result_ref.kind != JOINT_SIMULATION_RESULT_ARTIFACT_KIND
            ):
                raise ValueError("candidate_simulation_v4_result_hash_mismatch")
        if require_current_lease and (
            current_lease_resolver is None or not current_lease_resolver(record)
        ):
            raise ValueError("candidate_simulation_v4_current_lease_not_established")
        return record

    def resolve_candidate_simulation_v5(
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
        """Resolve the versioned selected-model input or its N5 execution."""
        import hashlib

        from polisyos.runtime.quality.candidate_simulation import (
            CandidateSimulationExecutionV5,
            CandidateSimulationN5InputV5,
        )

        if not isinstance(ref, ArtifactRef):
            raise ValueError("candidate_simulation_v5_selected_ref_required")
        if not self.store.verify(ref).ok:
            raise ValueError("candidate_simulation_v5_cas_integrity_failed")
        manifest = self.store.get_manifest(ref)
        if not _ref_selects_manifest(ref, manifest):
            raise ValueError("candidate_simulation_v5_selected_view_mismatch")
        body = self.store.get_bytes(ref)
        if "sha256:" + hashlib.sha256(body).hexdigest() != str(ref.artifact_id):
            raise ValueError("candidate_simulation_v5_cas_content_mismatch")
        try:
            payload = canon.from_canonical_bytes(body)
            if manifest.kind == _CANDIDATE_SIMULATION_INPUT_KIND:
                record: object = CandidateSimulationN5InputV5.model_validate(payload)
            elif manifest.kind == _CANDIDATE_SIMULATION_EXECUTION_KIND:
                record = CandidateSimulationExecutionV5.model_validate(payload)
            else:
                raise ValueError("candidate_simulation_v5_manifest_kind_mismatch")
        except (TypeError, ValueError) as exc:
            raise ValueError("candidate_simulation_v5_record_invalid") from exc
        is_input = type(record) is CandidateSimulationN5InputV5
        expected_kind = (
            _CANDIDATE_SIMULATION_INPUT_KIND
            if is_input
            else _CANDIDATE_SIMULATION_EXECUTION_KIND
        )
        if (
            manifest.kind != expected_kind
            or manifest.media_type != "application/json"
            or manifest.artifact_schema is None
            or manifest.artifact_schema.name != record.schema_version
            or manifest.artifact_schema.version != "5.0"
        ):
            raise ValueError("candidate_simulation_v5_manifest_profile_mismatch")
        record_input_refs = (
            (
                input_ref_from_artifact_ref(record.n4_source_ref, role="n4_source"),
                input_ref_from_artifact_ref(
                    record.context_job_ref,
                    role="cycle_substrate_context_job",
                ),
                input_ref_from_artifact_ref(
                    record.model_declaration_ref,
                    role="candidate_model_declaration",
                ),
                input_ref_from_artifact_ref(record.ncm_ref, role="candidate_ncm_spec"),
            )
            if is_input
            else (
                input_ref_from_artifact_ref(record.n5_input_ref, role="n5_input"),
                input_ref_from_artifact_ref(record.n4_source_ref, role="n4_source"),
                input_ref_from_artifact_ref(
                    record.context_job_ref,
                    role="cycle_substrate_context_job",
                ),
                input_ref_from_artifact_ref(
                    record.model_declaration_ref,
                    role="candidate_model_declaration",
                ),
                input_ref_from_artifact_ref(record.ncm_ref, role="candidate_ncm_spec"),
                input_ref_from_artifact_ref(record.n5_result_ref, role="n5_result"),
            )
        )
        options = _candidate_simulation_write_options(
            kind=expected_kind,
            schema_name=record.schema_version,
            schema_version="5.0",
            job_id=record.job_id,
            run_id=record.run_id,
            tenant_id=record.tenant_id,
            cell_id=record.cell_id,
            source_ref=str(record.n4_source_ref.artifact_id),
            input_refs=record_input_refs,
        )
        if not _has_owner_profile(manifest, options):
            raise ValueError("candidate_simulation_v5_owner_profile_mismatch")
        if (
            record.run_id != expected_run_id
            or (expected_job_id is not None and record.job_id != expected_job_id)
            or (expected_tenant_id is not None and record.tenant_id != expected_tenant_id)
            or (expected_cell_id is not None and record.cell_id != expected_cell_id)
        ):
            raise ValueError("candidate_simulation_v5_identity_mismatch")

        source = self.load_candidate_scenario_source_v2(
            record.n4_source_ref,
            expected_run_id=record.run_id,
            expected_job_id=record.job_id,
            expected_tenant_id=record.tenant_id,
            expected_cell_id=record.cell_id,
        )
        source_v1 = source.source_record
        if (
            artifact_ref_identity_key(source_v1.context_job_ref)
            != artifact_ref_identity_key(record.context_job_ref)
            or source.model_declaration_ref != record.model_declaration_ref
            or source.ncm_ref != record.ncm_ref
            or source_v1.profile.content_hash != record.profile.content_hash
            or source_v1.profile_config_ref != record.profile_config_ref
            or source_v1.candidate is None
            or source_v1.candidate.candidate_id != record.original_candidate_id
            or source_v1.candidate.atom.content_hash != record.original_candidate_hash
            or source_v1.candidate.atom.content_hash != record.original_n4_atom_hash
        ):
            raise ValueError("candidate_simulation_v5_n4_source_membership_mismatch")
        if is_input:
            materialization = record.materialization
            if (
                artifact_ref_identity_key(materialization.n4_source_ref)
                != artifact_ref_identity_key(record.n4_source_ref)
                or artifact_ref_identity_key(materialization.context_job_ref)
                != artifact_ref_identity_key(record.context_job_ref)
                or materialization.model_declaration_ref != record.model_declaration_ref
                or materialization.ncm_ref != record.ncm_ref
                or materialization.profile_hash != source_v1.profile.content_hash
                or materialization.problem_ref != source_v1.cycle_problem_ref
                or materialization.context_hash != source_v1.context_hash
                or materialization.world_model_record_hash
                != source_v1.world_model_record_hash
                or materialization.original_atom_hash
                != source_v1.candidate.atom.content_hash
                or materialization.outcome_variable
                != source_v1.problem.outcome_of_interest.target_variable
            ):
                raise ValueError("candidate_simulation_v5_input_context_mismatch")
        else:
            input_record = self._load_candidate_simulation_input_v5(record.n5_input_ref)
            if (
                type(input_record) is not CandidateSimulationN5InputV5
                or artifact_ref_identity_key(input_record.n4_source_ref)
                != artifact_ref_identity_key(record.n4_source_ref)
                or artifact_ref_identity_key(input_record.context_job_ref)
                != artifact_ref_identity_key(record.context_job_ref)
                or input_record.model_declaration_ref != record.model_declaration_ref
                or input_record.ncm_ref != record.ncm_ref
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
                raise ValueError("candidate_simulation_v5_execution_input_mismatch")
            from polisyos.runtime.quality.generation_cycle import (
                JOINT_SIMULATION_RESULT_ARTIFACT_KIND,
                load_joint_simulation_result,
            )

            result = load_joint_simulation_result(
                record.n5_result_ref,
                store=self.store,
                expected_world_model_record_content_hash=record.world_model_record_hash,
                expected_atom_ids=(input_record.materialization.derived_n5_atom.intervention_id,),
            )
            if (
                result.receipt.payload_hash != record.n5_result_content_hash
                or record.n5_result_ref.kind != JOINT_SIMULATION_RESULT_ARTIFACT_KIND
            ):
                raise ValueError("candidate_simulation_v5_result_hash_mismatch")
        if require_current_lease and (
            current_lease_resolver is None or not current_lease_resolver(record)
        ):
            raise ValueError("candidate_simulation_v5_current_lease_not_established")
        return record

    def _load_candidate_simulation_input_v5(self, ref: ArtifactRef) -> object:
        """Resolve one exact V5 input and its upstream candidate source."""
        from polisyos.runtime.quality.candidate_simulation import CandidateSimulationN5InputV5

        if not isinstance(ref, ArtifactRef):
            raise ValueError("candidate_simulation_v5_selected_ref_required")
        if not self.store.verify(ref).ok:
            raise ValueError("candidate_simulation_v5_input_cas_integrity_failed")
        body = self.store.get_bytes(ref)
        try:
            record = CandidateSimulationN5InputV5.model_validate(
                canon.from_canonical_bytes(body)
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("candidate_simulation_v5_input_invalid") from exc
        return self.resolve_candidate_simulation_v5(
            ref=ref,
            expected_run_id=record.run_id,
            expected_job_id=record.job_id,
            expected_tenant_id=record.tenant_id,
            expected_cell_id=record.cell_id,
        )

    def _load_candidate_simulation_input_v4(self, ref: ArtifactRef) -> object:
        """Load one v4 input only after the shared resolver replays its lineage."""

        from polisyos.runtime.quality.candidate_simulation import (
            CandidateSimulationN5InputV4,
        )

        if not isinstance(ref, ArtifactRef):
            raise ValueError("candidate_simulation_v4_selected_ref_required")
        if not self.store.verify(ref).ok:
            raise ValueError("candidate_simulation_v4_input_cas_integrity_failed")
        manifest = self.store.get_manifest(ref)
        if not _ref_selects_manifest(ref, manifest):
            raise ValueError("candidate_simulation_v4_input_selected_view_mismatch")
        body = self.store.get_bytes(ref)
        try:
            record = CandidateSimulationN5InputV4.model_validate(
                canon.from_canonical_bytes(body)
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("candidate_simulation_v4_input_invalid") from exc
        return self.resolve_candidate_simulation_v4(
            ref=ref,
            expected_run_id=record.run_id,
            expected_job_id=record.job_id,
            expected_tenant_id=record.tenant_id,
            expected_cell_id=record.cell_id,
        )

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

    def load_candidate_proposal_projection_for_served_job(
        self,
        locator: (
            N4CandidateProposalLocator
            | N4CandidateScenarioSourceLocator
            | Mapping[str, Any]
        ),
        *,
        job_id: str,
        run_id: str,
        tenant_id: str,
        cell_id: str,
        raw_request: str,
        expected_design_problem: DesignProblem | None = None,
    ) -> (
        N4CandidateProposalRecord
        | N4CandidateProposalSimulationRecord
        | N4CandidateScenarioSourceRecordV1
        | N4CandidateScenarioSourceRecordV2
    ):
        """Dispatch the existing progress pointer to its exact N4 source owner."""

        typed_locator: N4CandidateProposalLocator | N4CandidateScenarioSourceLocator
        if type(locator) is N4CandidateProposalLocator or type(
            locator
        ) is N4CandidateScenarioSourceLocator:
            typed_locator = locator
        elif isinstance(locator, Mapping):
            schema_version = locator.get("schema_version")
            if schema_version == N4_CANDIDATE_PROPOSAL_LOCATOR_SCHEMA:
                typed_locator = N4CandidateProposalLocator.model_validate(locator)
            elif schema_version == N4_CANDIDATE_SCENARIO_SOURCE_LOCATOR_SCHEMA:
                typed_locator = N4CandidateScenarioSourceLocator.model_validate(locator)
            else:
                raise ValueError("n4_candidate_proposal_locator_schema_unsupported")
        else:
            raise TypeError("n4_candidate_proposal_locator_untyped")

        if type(typed_locator) is N4CandidateProposalLocator:
            artifact = self.load_candidate_proposal_for_served_job(
                typed_locator,
                job_id=job_id,
                run_id=run_id,
                tenant_id=tenant_id,
                cell_id=cell_id,
                raw_request=raw_request,
            )
            if (
                expected_design_problem is not None
                and artifact.problem != expected_design_problem
            ):
                raise ValueError("n4_candidate_proposal_projection_problem_mismatch")
            return artifact

        artifact = self.load_candidate_scenario_source_for_n5(
            typed_locator.artifact_ref,
            expected_run_id=run_id,
            expected_job_id=job_id,
            expected_tenant_id=tenant_id,
            expected_cell_id=cell_id,
        )
        if artifact.problem.nl_provenance.raw_request != raw_request:
            raise ValueError("n4_candidate_scenario_projection_request_mismatch")
        if (
            expected_design_problem is not None
            and artifact.problem != expected_design_problem
        ):
            raise ValueError("n4_candidate_scenario_projection_problem_mismatch")
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
