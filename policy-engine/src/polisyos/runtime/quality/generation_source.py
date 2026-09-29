"""Persist N4 candidate sources for N6 custody and the existing N9 input bridge.

This owner preserves candidate inputs. It cannot appoint an authority, admit a
protected candidate, replace a missing producer, or promote a synthetic source.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import fields
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core import artifacts, canon
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


def _source_write_options() -> artifacts.ArtifactWriteOptions:
    return artifacts.ArtifactWriteOptions(
        kind=SOURCE_KIND,
        media_type="application/json",
        schema=artifacts.SchemaInfo(name=SOURCE_SCHEMA, version="1.0"),
        producer=artifacts.ProducerInfo(component=__name__, version="1.0"),
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
        return str(ref.artifact_id)

    def load(self, ref: str, *, run_id: str) -> GenerationSourceHandoff:
        """Verify Core custody, exact typed source and its canonical run binding."""
        if not self.store.verify(ref).ok:
            raise ValueError("generation_source_cas_integrity_failed")
        if not _has_source_owner_profile(self.store.get_manifest(ref)):
            raise ValueError("generation_source_owner_profile_mismatch")
        body = self.store.get_bytes(ref)
        if "sha256:" + hashlib.sha256(body).hexdigest() != ref:
            raise ValueError("generation_source_cas_content_mismatch")
        artifact = GenerationSourceHandoff.model_validate(canon.from_canonical_bytes(body))
        if artifact.run_id != run_id:
            raise ValueError("generation_source_run_mismatch")
        return artifact

    def resolve(
        self,
        *,
        refs: Sequence[str],
        run_id: str,
        summary: CandidateSummary,
        problem: DesignProblem,
    ) -> GenerationSourceResolution:
        """Resolve the whole source set before selecting one exact candidate occurrence."""
        if len(refs) != len(set(refs)):
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
                        source_ref=ref,
                    )
                result["effect_obligation_writer_input"] = writer.model_copy(
                    update={"proposal": proposal}
                )
        return GenerationSourceResolution(
            status="resolved", code="candidate_sources_replayed", source_ref=ref, context=result
        )

    def preservation_receipt(
        self,
        *,
        run_id: str,
        refs: Sequence[str],
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
        if len(refs) != len(set(refs)):
            issues.append("source_ref_duplicate")
        for ref in refs:
            try:
                artifact = self.load(ref, run_id=run_id)
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
            "source_refs": tuple(refs),
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
