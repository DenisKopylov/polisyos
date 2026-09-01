"""Read-only composition of exact epoch evidence into temporal surface chrome.

This module does not appoint authorities, adjudicate perturbations, or execute
derivations. It projects verified owner results and preserves their typed
nonreceipts. Positive transition fixtures are explicitly marked so test/demo
evidence cannot become production authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from polisyos.core import artifacts as core_artifacts
from polisyos.core.contracts import (
    DecisionValidityStatus,
    EngineeringCapabilityAbsenceView,
    EpochBoundaryLineageView,
    EpochCertificateStalenessView,
    EpochDependencyStalenessView,
    EpochDerivedRecomputeView,
    EpochOpenWorldRiskComponentView,
    EpochOpenWorldRiskView,
    EpochPerturbationView,
    EpochProjectionDenominatorView,
    EpochProjectionStatus,
    EpochStalenessProjectionView,
    EpochValidityGateNonReceipt,
    EpochValidityN9Projection,
    InstitutionalAuthorityAbsenceView,
    NativeChronologyPolicyResolutionFailed,
    PolicyAdmissionMissingFailure,
    TemporalScope,
    epoch_staleness_semantic_hash,
)
from polisyos.scientist.governance.continuous import (
    AppealPerturbation,
    CorrectionPerturbation,
    DiscoveredBiasPerturbation,
    IncidentPerturbation,
    LegalChangePerturbation,
    PersistedGovernanceMonitorEvent,
    RetractionPerturbation,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from datetime import datetime

from .derived_observations import (
    EPOCH_INHERITANCE_RECOMPUTE_RECEIPT_KIND,
    DerivationRefusalCode,
    DerivationRefusalError,
    EpochInheritanceRecomputeReceipt,
    read_epoch_inheritance_recompute_receipt,
)
from .epoch_validity_cascade import (
    EpochDependencyDenominatorReceipt,
    EpochTransitionSigningNonReceipt,
    EpochValidityTransitionArtifact,
    TargetDispositionRow,
)
from .open_world_risk import (
    OpenWorldRiskProductionNonReceipt,
    OpenWorldRiskPublicLimitation,
    OpenWorldRiskResolutionNonReceipt,
    VerifiedOpenWorldRiskVector,
)

_RECOMPUTE_OWNER_MODULE = "polisyos.runtime.quality.derived_observations"
_RECOMPUTE_OWNER_PATH = "src/polisyos/runtime/quality/derived_observations.py"
_EpochDependencyKey = tuple[str, str, str, str, str, str, str, str]


def _dependency_key(
    *,
    source_ref: core_artifacts.ArtifactRef,
    target_ref: core_artifacts.ArtifactRef,
    relation: str,
    authority_purpose: str,
) -> _EpochDependencyKey:
    return (
        str(source_ref.artifact_id),
        source_ref.kind,
        source_ref.media_type,
        str(target_ref.artifact_id),
        target_ref.kind,
        target_ref.media_type,
        relation,
        authority_purpose,
    )


@dataclass(frozen=True, slots=True)
class _EpochRecomputeResolution:
    transition: EpochValidityTransitionArtifact | None
    receipts: Mapping[_EpochDependencyKey, EpochInheritanceRecomputeReceipt]
    recomputes: Mapping[_EpochDependencyKey, EpochDerivedRecomputeView]
    complete: bool


class EpochInheritanceRecomputeProjectionReader:
    """Exact-read owner recompute receipts at one requested temporal coordinate."""

    def __init__(self, *, artifact_store: core_artifacts.ArtifactStore) -> None:
        self._artifact_store = artifact_store

    def resolve(
        self,
        *,
        requested_query_context_ref: str,
        authority_purpose: str,
    ) -> _EpochRecomputeResolution:
        """Resolve one transition's exact recompute rows without claiming it is head."""

        verified: list[
            tuple[
                EpochInheritanceRecomputeReceipt,
                EpochDerivedRecomputeView,
                EpochValidityTransitionArtifact,
            ]
        ] = []
        store = cast("core_artifacts.FileSystemCAS", self._artifact_store)
        for artifact_id in sorted(self._artifact_store.iter_artifact_ids(), key=str):
            manifest = self._artifact_store.get_manifest(artifact_id)
            if manifest.kind != EPOCH_INHERITANCE_RECOMPUTE_RECEIPT_KIND:
                continue
            if manifest.media_type != "application/json":
                raise DerivationRefusalError(
                    DerivationRefusalCode.EPOCH_RECOMPUTE_DRIFT,
                    "epoch recompute receipt manifest profile mismatch",
                )
            receipt_ref = core_artifacts.ArtifactRef(
                artifact_id=manifest.artifact_id,
                kind=manifest.kind,
                media_type=manifest.media_type,
            )
            try:
                receipt = EpochInheritanceRecomputeReceipt.model_validate_json(
                    self._artifact_store.get_bytes(artifact_id)
                )
            except (OSError, TypeError, ValueError) as exc:
                raise DerivationRefusalError(
                    DerivationRefusalCode.EPOCH_RECOMPUTE_DRIFT,
                    "epoch recompute receipt candidate readback failed",
                ) from exc
            if (
                receipt.requested_query_context_ref != requested_query_context_ref
                or receipt.authority_purpose != authority_purpose
            ):
                continue
            persisted = read_epoch_inheritance_recompute_receipt(
                store,
                receipt_ref=receipt_ref,
                expected_previous_epoch_ref=receipt.previous_epoch_ref,
                expected_current_epoch_ref=receipt.current_epoch_ref,
                requested_query_context_ref=requested_query_context_ref,
                authority_purpose=authority_purpose,
                source_ref=receipt.source_ref,
                target_ref=receipt.target_ref,
                relation=receipt.relation,
                expected_target_disposition=receipt.target_disposition,
                certificate_ref=receipt.certificate_artifact_ref,
            )
            try:
                transition = EpochValidityTransitionArtifact.model_validate_json(
                    self._artifact_store.get_bytes(
                        receipt.transition_artifact_ref.artifact_id
                    )
                )
            except (OSError, TypeError, ValueError) as exc:
                raise DerivationRefusalError(
                    DerivationRefusalCode.EPOCH_RECOMPUTE_DRIFT,
                    "epoch recompute transition projection readback failed",
                ) from exc
            if (
                transition.transition_content_hash != receipt.transition_content_hash
                or transition.previous_epoch_ref != receipt.previous_epoch_ref
                or transition.current_epoch_ref != receipt.current_epoch_ref
                or transition.requested_query_context_ref != requested_query_context_ref
                or transition.authority_purpose != authority_purpose
            ):
                raise DerivationRefusalError(
                    DerivationRefusalCode.EPOCH_RECOMPUTE_DRIFT,
                    "epoch recompute receipt differs from requested transition coordinate",
                )
            verified.append(
                (
                    receipt,
                    EpochDerivedRecomputeView(
                        status="completed",
                        predicate_provenance="recomputed",
                        evidence_ref=persisted.receipt_artifact_ref,
                        evidence_content_hash=persisted.receipt_content_hash,
                    ),
                    transition,
                )
            )

        if not verified:
            return _EpochRecomputeResolution(
                transition=None,
                receipts={},
                recomputes={},
                complete=False,
            )
        transition_identities = {
            (
                str(receipt.transition_artifact_ref.artifact_id),
                receipt.transition_content_hash,
            )
            for receipt, _view, _transition in verified
        }
        if len(transition_identities) != 1:
            raise DerivationRefusalError(
                DerivationRefusalCode.EPOCH_RECOMPUTE_DRIFT,
                "multiple epoch transitions answer one requested temporal coordinate",
            )
        transition = verified[0][2]
        receipts: dict[_EpochDependencyKey, EpochInheritanceRecomputeReceipt] = {}
        recomputes: dict[_EpochDependencyKey, EpochDerivedRecomputeView] = {}
        for receipt, view, candidate_transition in verified:
            if candidate_transition != transition:
                raise DerivationRefusalError(
                    DerivationRefusalCode.EPOCH_RECOMPUTE_DRIFT,
                    "epoch transition projections differ at one temporal coordinate",
                )
            key = _dependency_key(
                source_ref=receipt.source_ref,
                target_ref=receipt.target_ref,
                relation=receipt.relation,
                authority_purpose=receipt.authority_purpose,
            )
            if key in receipts:
                raise DerivationRefusalError(
                    DerivationRefusalCode.EPOCH_RECOMPUTE_DRIFT,
                    "multiple completed receipts answer one dependency edge",
                )
            receipts[key] = receipt
            recomputes[key] = view
        edge_keys = {
            _dependency_key(
                source_ref=edge.source_ref,
                target_ref=edge.target_ref,
                relation=edge.relation,
                authority_purpose=edge.authority_purpose,
            )
            for edge in transition.dependency_graph.edges
        }
        return _EpochRecomputeResolution(
            transition=transition,
            receipts=receipts,
            recomputes=recomputes,
            complete=bool(edge_keys) and set(recomputes) == edge_keys,
        )


def _institutional_absences(
    *,
    epoch_gate: (
        EpochValidityN9Projection
        | EpochValidityGateNonReceipt
        | NativeChronologyPolicyResolutionFailed
    ),
    transition: EpochValidityTransitionArtifact | EpochTransitionSigningNonReceipt,
) -> tuple[InstitutionalAuthorityAbsenceView, ...]:
    rows: list[InstitutionalAuthorityAbsenceView] = []
    policy_missing = (
        isinstance(epoch_gate, EpochValidityGateNonReceipt)
        and epoch_gate.code == "policy_admission_missing"
    ) or (
        isinstance(epoch_gate, NativeChronologyPolicyResolutionFailed)
        and isinstance(epoch_gate.failure, PolicyAdmissionMissingFailure)
    )
    if policy_missing:
        source_refs = (
            (epoch_gate.subject_ref,) if isinstance(epoch_gate, EpochValidityGateNonReceipt) else ()
        )
        rows.append(
            InstitutionalAuthorityAbsenceView(
                role="epoch_predicate_policy_signer",
                authority_purpose="semantic_epoch_qualification",
                refusal_code="policy_admission_missing",
                consequence=(
                    "Epoch currentness is not established; the claim cannot be represented "
                    "as current or publishable."
                ),
                closure_condition=(
                    "A competent institution must establish the predicate-policy authority; "
                    "DS18 closes on truthful refusal rendering, not on that appointment."
                ),
                inspectable_capabilities=("history", "candidate", "replay", "MACHINE"),
                source_refs=source_refs,
            )
        )
    if (
        isinstance(transition, EpochTransitionSigningNonReceipt)
        and transition.code == "epoch_transition_signer_not_established"
    ):
        rows.append(
            InstitutionalAuthorityAbsenceView(
                role="epoch_transition_signer",
                authority_purpose="epoch_transition_issuance",
                refusal_code="epoch_transition_signer_not_established",
                consequence=(
                    "Transition issuance and revalidation completion are unavailable; "
                    "stale lineage remains inspectable and promotion stays frozen."
                ),
                closure_condition=(
                    "A competent institution must establish transition-signing authority; "
                    "DS18 closes on useful typed refusal rendering, not on that appointment."
                ),
                inspectable_capabilities=(
                    "history",
                    "stale_bindings",
                    "replay",
                    "MACHINE",
                ),
            )
        )
    return tuple(rows)


def _engineering_absence() -> EngineeringCapabilityAbsenceView:
    return EngineeringCapabilityAbsenceView(
        missing_output=(
            "An owner-emitted epoch-inheritance/recompute-status projection and its "
            "temporal read bridge."
        ),
        consequence=(
            "Dependent derivations remain stale with recompute_status=not_established; "
            "no pending or completed execution is implied."
        ),
        closure_condition=(
            "Assign and implement the producer/read bridge in the named owner module, then "
            "prove a content-bound owner receipt changes the projected status."
        ),
    )


def _open_world_risk_view(
    value: (
        VerifiedOpenWorldRiskVector
        | OpenWorldRiskPublicLimitation
        | OpenWorldRiskResolutionNonReceipt
        | OpenWorldRiskProductionNonReceipt
        | None
    ),
) -> EpochOpenWorldRiskView:
    if isinstance(value, VerifiedOpenWorldRiskVector):
        vector = value.vector
        return EpochOpenWorldRiskView(
            status=vector.status,
            limitation_code=vector.limitation_code,
            vector_artifact_ref=value.vector_artifact_ref,
            components=tuple(
                EpochOpenWorldRiskComponentView(
                    component_id=row.component_id,
                    component_kind=row.component_kind,
                    status=row.status,
                    limitation_code=row.limitation_code,
                    evidence_ref=row.evidence_ref,
                    predicate_provenance=row.predicate_class,
                )
                for row in vector.components
            ),
            promotion_frozen=vector.status != "established",
        )
    if isinstance(value, OpenWorldRiskPublicLimitation):
        return EpochOpenWorldRiskView(
            status=value.status,
            limitation_code=value.code,
            vector_artifact_ref=value.vector_artifact_ref,
            promotion_frozen=True,
        )
    if isinstance(value, (OpenWorldRiskResolutionNonReceipt, OpenWorldRiskProductionNonReceipt)):
        return EpochOpenWorldRiskView(
            status="not_established",
            limitation_code=value.code,
            promotion_frozen=True,
        )
    return EpochOpenWorldRiskView(
        status="not_established",
        limitation_code="open_world_vector_unresolved",
        promotion_frozen=True,
    )


def _disposition_by_target(
    transition: EpochValidityTransitionArtifact,
) -> dict[str, TargetDispositionRow]:
    return {str(row.target_ref.artifact_id): row for row in transition.target_vector.rows}


def _unique_refs(
    refs: Sequence[core_artifacts.ArtifactRef],
) -> tuple[core_artifacts.ArtifactRef, ...]:
    by_id: dict[str, core_artifacts.ArtifactRef] = {}
    for ref in refs:
        by_id.setdefault(str(ref.artifact_id), ref)
    return tuple(by_id.values())


def _certificate_views(
    transition: EpochValidityTransitionArtifact,
) -> tuple[EpochCertificateStalenessView, ...]:
    dispositions = _disposition_by_target(transition)
    rows: list[EpochCertificateStalenessView] = []
    for binding in transition.certificate_bindings:
        disposition = dispositions.get(str(binding.certificate_ref.artifact_id))
        stale_reasons: tuple[str, ...] = (
            ("bound_epoch_differs_from_current",)
            if binding.epoch_ref != transition.current_epoch_ref
            else ()
        )
        status: EpochProjectionStatus
        if disposition is not None and disposition.disposition == "contested":
            status = "contested"
            stale_reasons += ("owner_disposition_contested",)
        elif disposition is not None and disposition.disposition not in {
            "unchanged",
            "annotation_only",
        }:
            status = "revalidation_required"
            stale_reasons += (f"target_disposition:{disposition.disposition}",)
        elif stale_reasons:
            status = "stale"
        else:
            status = "current"
        rows.append(
            EpochCertificateStalenessView(
                certificate_ref=binding.certificate_ref,
                authority_purpose=binding.authority_purpose,
                bound_epoch_ref=binding.epoch_ref,
                current_epoch_ref=transition.current_epoch_ref,
                status=status,
                stale_reasons=stale_reasons,
                trigger_event_refs=(
                    disposition.advisory_event_refs if disposition is not None else ()
                ),
                input_certificate_refs=binding.input_certificate_refs,
                recipe_ref=binding.recipe.recipe_ref,
                native_coordinate_refs=binding.native_coordinate_refs,
                rule_schema_profile_refs=binding.rule_schema_profile_refs,
                revalidation_requirements=(
                    ("owner_revalidation_receipt",) if status == "revalidation_required" else ()
                ),
            )
        )
    return tuple(rows)


def _dependency_views(
    transition: EpochValidityTransitionArtifact,
    *,
    recomputes: Mapping[_EpochDependencyKey, EpochDerivedRecomputeView] | None = None,
) -> tuple[EpochDependencyStalenessView, ...]:
    dispositions = _disposition_by_target(transition)
    resolved_recomputes = recomputes or {}
    rows: list[EpochDependencyStalenessView] = []
    for edge in transition.dependency_graph.edges:
        disposition = dispositions.get(str(edge.target_ref.artifact_id))
        rows.append(
            EpochDependencyStalenessView(
                source_ref=edge.source_ref,
                target_ref=edge.target_ref,
                relation=edge.relation,
                authority_purpose=edge.authority_purpose,
                disposition=(disposition.disposition if disposition is not None else "unchanged"),
                source_classes=(disposition.source_classes if disposition is not None else ()),
                advisory_event_refs=(
                    disposition.advisory_event_refs if disposition is not None else ()
                ),
                owner_evidence_refs=(
                    disposition.owner_evidence_refs if disposition is not None else ()
                ),
                recompute=resolved_recomputes.get(
                    _dependency_key(
                        source_ref=edge.source_ref,
                        target_ref=edge.target_ref,
                        relation=edge.relation,
                        authority_purpose=edge.authority_purpose,
                    ),
                    EpochDerivedRecomputeView(
                        status="not_established",
                        predicate_provenance="not_established",
                    ),
                ),
            )
        )
    return tuple(rows)


def _recompute_only_dependency_views(
    resolution: _EpochRecomputeResolution,
) -> tuple[EpochDependencyStalenessView, ...]:
    """Project exact recompute coordinates without transition lifecycle authority."""

    return tuple(
        EpochDependencyStalenessView(
            source_ref=receipt.source_ref,
            target_ref=receipt.target_ref,
            relation=receipt.relation,
            authority_purpose=receipt.authority_purpose,
            # The frozen surface requires the transition-bound disposition. Here it
            # is only a replay coordinate; lifecycle fields stay on the signer path.
            disposition=receipt.target_disposition,
            source_classes=(),
            advisory_event_refs=(),
            owner_evidence_refs=(),
            recompute=resolution.recomputes[key],
        )
        for key, receipt in resolution.receipts.items()
    )


def _source_evidence_refs(
    event: PersistedGovernanceMonitorEvent,
) -> tuple[core_artifacts.ArtifactRef, ...]:
    perturbation = event.event.perturbation
    if isinstance(perturbation, IncidentPerturbation):
        return (perturbation.incident_report_ref,)
    if isinstance(perturbation, AppealPerturbation):
        return (perturbation.appeal_evidence_ref,)
    if isinstance(perturbation, CorrectionPerturbation):
        return (perturbation.evidence_validity_event_ref, *perturbation.replacement_refs)
    if isinstance(perturbation, RetractionPerturbation):
        return (perturbation.evidence_validity_event_ref,)
    if isinstance(perturbation, LegalChangePerturbation):
        return (perturbation.legal_change_evidence_ref,)
    if isinstance(perturbation, DiscoveredBiasPerturbation):
        return (perturbation.bias_evidence_ref,)
    return ()


def _perturbation_views(
    events: Sequence[PersistedGovernanceMonitorEvent],
    transition: EpochValidityTransitionArtifact | EpochTransitionSigningNonReceipt,
) -> tuple[EpochPerturbationView, ...]:
    disposition_by_event: dict[str, TargetDispositionRow] = {}
    if isinstance(transition, EpochValidityTransitionArtifact):
        for row in transition.target_vector.rows:
            for ref in row.advisory_event_refs:
                key = str(ref.artifact_id)
                previous = disposition_by_event.get(key)
                if previous is not None and previous != row:
                    raise ValueError("one perturbation event cannot bind multiple target rows")
                disposition_by_event[key] = row
    rows: list[EpochPerturbationView] = []
    for persisted in events:
        event = persisted.event
        perturbation = event.perturbation
        if perturbation is None:
            continue
        disposition = disposition_by_event.get(str(persisted.event_ref.artifact_id))
        if disposition is not None and perturbation.source_class not in disposition.source_classes:
            raise ValueError("persisted monitor source class differs from transition vector")
        rows.append(
            EpochPerturbationView(
                source_class=perturbation.source_class,
                event_ref=persisted.event_ref,
                target_ref=(
                    disposition.target_ref if disposition is not None else event.decision_packet_ref
                ),
                scope=(
                    "instance"
                    if isinstance(perturbation, AppealPerturbation)
                    else "dependency_descendants"
                ),
                observed_at=event.occurred_at,
                advisory_posture=event.advisory_posture,
                adjudicated_disposition=(
                    disposition.disposition
                    if disposition is not None and disposition.disposition != "unchanged"
                    else event.advisory_posture
                ),
                source_evidence_refs=_source_evidence_refs(persisted),
                owner_evidence_refs=(
                    disposition.owner_evidence_refs if disposition is not None else ()
                ),
            )
        )
    return tuple(rows)


def _validate_positive_inputs(
    *,
    transition: EpochValidityTransitionArtifact,
    dependency_denominator: EpochDependencyDenominatorReceipt | None,
    requested_query_context_ref: str,
) -> EpochProjectionDenominatorView:
    if transition.requested_query_context_ref != requested_query_context_ref:
        raise ValueError("epoch transition query context mismatch")
    if dependency_denominator is None:
        return EpochProjectionDenominatorView(
            predicate_provenance="not_established",
            source_count=0,
            target_count=len(transition.target_vector.rows),
        )
    if (
        dependency_denominator.denominator_ref != transition.dependency_denominator_ref
        or dependency_denominator.dependency_graph != transition.dependency_graph
        or dependency_denominator.certificate_bindings != transition.certificate_bindings
    ):
        raise ValueError("epoch dependency denominator differs from transition")
    source_count = len(
        {str(edge.source_ref.artifact_id) for edge in dependency_denominator.dependency_graph.edges}
    )
    return EpochProjectionDenominatorView(
        predicate_provenance=dependency_denominator.predicate_class,
        denominator_ref=dependency_denominator.denominator_ref,
        source_count=source_count,
        target_count=len(dependency_denominator.target_refs),
    )


def compile_epoch_staleness_projection(
    *,
    run_id: str,
    decision_packet_ref: core_artifacts.ArtifactRef | None,
    temporal_scope: TemporalScope,
    requested_query_context_ref: str,
    owner_as_of: datetime | None,
    observed_at: datetime,
    epoch_gate: (
        EpochValidityN9Projection
        | EpochValidityGateNonReceipt
        | NativeChronologyPolicyResolutionFailed
    ),
    transition: EpochValidityTransitionArtifact | EpochTransitionSigningNonReceipt,
    dependency_denominator: EpochDependencyDenominatorReceipt | None = None,
    monitor_events: Sequence[PersistedGovernanceMonitorEvent] = (),
    open_world_risk: (
        VerifiedOpenWorldRiskVector
        | OpenWorldRiskPublicLimitation
        | OpenWorldRiskResolutionNonReceipt
        | OpenWorldRiskProductionNonReceipt
        | None
    ) = None,
    recompute_reader: EpochInheritanceRecomputeProjectionReader | None = None,
    recompute_authority_purpose: str | None = None,
    fixture_only: bool = False,
) -> EpochStalenessProjectionView:
    """Compose a strict projection without upgrading any input's authority band."""

    gate_query_context_ref = (
        epoch_gate.query.requested_query_context_ref
        if isinstance(epoch_gate, NativeChronologyPolicyResolutionFailed)
        else epoch_gate.requested_query_context_ref
    )
    if gate_query_context_ref != requested_query_context_ref:
        raise ValueError("epoch gate query context mismatch")
    if isinstance(transition, EpochValidityTransitionArtifact) and not fixture_only:
        raise ValueError("positive transition projection requires an exact owner reader")
    recompute_resolution = _EpochRecomputeResolution(
        transition=None,
        receipts={},
        recomputes={},
        complete=False,
    )
    if recompute_reader is not None:
        if not recompute_authority_purpose:
            raise ValueError("recompute reader requires an exact authority purpose")
        recompute_resolution = recompute_reader.resolve(
            requested_query_context_ref=requested_query_context_ref,
            authority_purpose=recompute_authority_purpose,
        )

    absences = _institutional_absences(epoch_gate=epoch_gate, transition=transition)
    certificates: tuple[EpochCertificateStalenessView, ...] = ()
    dependencies: tuple[EpochDependencyStalenessView, ...] = ()
    lineage: tuple[EpochBoundaryLineageView, ...] = ()
    current_epoch_ref: str | None = None
    denominator = EpochProjectionDenominatorView(predicate_provenance="not_established")
    if isinstance(transition, EpochValidityTransitionArtifact):
        denominator = _validate_positive_inputs(
            transition=transition,
            dependency_denominator=dependency_denominator,
            requested_query_context_ref=requested_query_context_ref,
        )
        current_epoch_ref = transition.current_epoch_ref
        certificates = _certificate_views(transition)
        if (
            recompute_resolution.transition is not None
            and recompute_resolution.transition != transition
        ):
            raise ValueError("recompute receipt transition differs from projected transition")
        dependencies = _dependency_views(
            transition,
            recomputes=recompute_resolution.recomputes,
        )
        lineage = (
            EpochBoundaryLineageView(
                previous_epoch_ref=transition.previous_epoch_ref,
                current_epoch_ref=transition.current_epoch_ref,
                trigger_event_refs=_unique_refs(
                    tuple(
                        event_ref
                        for row in transition.target_vector.rows
                        for event_ref in row.advisory_event_refs
                    )
                ),
            ),
        )
    elif recompute_resolution.transition is not None:
        dependencies = _recompute_only_dependency_views(recompute_resolution)

    if absences:
        status: EpochProjectionStatus = "not_established"
    elif any(row.status == "contested" for row in certificates):
        status = "contested"
    elif any(row.status == "revalidation_required" for row in certificates):
        status = "revalidation_required"
    elif any(row.status == "stale" for row in certificates):
        status = "stale"
    elif (
        isinstance(epoch_gate, EpochValidityN9Projection)
        and denominator.predicate_provenance in {"recomputed", "independently_reconciled"}
        and current_epoch_ref is not None
    ):
        status = "current"
    else:
        status = "not_established"

    decision_status = {
        "current": DecisionValidityStatus.ACTIVE,
        "stale": DecisionValidityStatus.STALE,
        "revalidation_required": DecisionValidityStatus.REVIEW_REQUIRED,
        "contested": DecisionValidityStatus.REVIEW_REQUIRED,
        "not_established": None,
    }[status]
    perturbations = _perturbation_views(monitor_events, transition)
    revalidation_required = status == "revalidation_required" or any(
        row.status == "revalidation_required" for row in certificates
    )
    limitations = []
    if denominator.predicate_provenance == "not_established":
        limitations.append("epoch_dependency_denominator_not_established")
    if absences:
        limitations.extend(row.refusal_code for row in absences)
    if not recompute_resolution.complete:
        limitations.append("derived_recompute_status_not_established")

    draft = EpochStalenessProjectionView.model_construct(
        run_id=run_id,
        decision_packet_ref=decision_packet_ref,
        temporal_scope=temporal_scope,
        requested_query_context_ref=requested_query_context_ref,
        owner_as_of=owner_as_of,
        owner_time_reason=(None if owner_as_of is not None else "owner_time_not_established"),
        observed_at=observed_at,
        status=status,
        current_epoch_ref=current_epoch_ref,
        scoped_epoch_refs=(
            (transition.previous_epoch_ref, transition.current_epoch_ref)
            if isinstance(transition, EpochValidityTransitionArtifact)
            else ()
        ),
        decision_validity_status=decision_status,
        revalidation_required=revalidation_required,
        denominator=denominator,
        certificates=certificates,
        dependencies=dependencies,
        perturbations=perturbations,
        lineage=lineage,
        open_world_risk=_open_world_risk_view(open_world_risk),
        institutional_absences=absences,
        engineering_absences=(
            () if recompute_reader is not None else (_engineering_absence(),)
        ),
        limitations=tuple(dict.fromkeys(limitations)),
        predicate_provenance=denominator.predicate_provenance,
        fixture_only=fixture_only,
        projection_semantic_hash="sha256:" + "0" * 64,
    )
    return EpochStalenessProjectionView.model_validate(
        {
            **draft.model_dump(mode="json"),
            "projection_semantic_hash": epoch_staleness_semantic_hash(draft),
        }
    )


__all__ = [
    "EpochInheritanceRecomputeProjectionReader",
    "compile_epoch_staleness_projection",
]
