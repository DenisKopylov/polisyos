from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.analytics.alignment_certification import (
    AlignmentReport,
    AlignmentReviewerState,
    AlignmentType,
    VariableAlignmentCertificate,
)
from polisyos.ir.analytics.cross_graph import CompositionCertificate, InterfaceMapping
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import CompositionFailureCardBundleRef
from polisyos.scientist.search.failure_cards import FailureSeverity, TypedFailureCard

_COMPOSITION_FAILURE_CARD_BUNDLE_SCHEMA_NAME = "ir.composition_failure_card_bundle"
_COMPOSITION_FAILURE_CARD_BUNDLE_SCHEMA_VERSION = "1.0"


class CompositionFailureCardBundle(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    cards: list[TypedFailureCard] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def build_composition_failure_cards(
    *,
    alignment_report: AlignmentReport,
    interface_mapping: InterfaceMapping,
    composition_certificate: CompositionCertificate,
) -> list[TypedFailureCard]:
    cards: list[TypedFailureCard] = []
    blocking_reasons = [str(reason) for reason in composition_certificate.blocking_reasons]
    lowered_reasons = [reason.lower() for reason in blocking_reasons]
    disconnected_fragment_ids = [
        str(fragment_id)
        for fragment_id in composition_certificate.metadata.get("disconnected_fragment_ids", [])
        if str(fragment_id).strip()
    ]
    proxy_pairs = _pair_labels(
        certificate
        for certificate in alignment_report.per_variable_certificates
        if certificate.alignment_type is AlignmentType.PROXY
        and certificate.reviewer is AlignmentReviewerState.PENDING_REVIEW
    )
    latent_pairs = _pair_labels(
        certificate
        for certificate in alignment_report.per_variable_certificates
        if certificate.alignment_type is AlignmentType.LATENT_BRIDGE
        and certificate.reviewer is not AlignmentReviewerState.HUMAN_VERIFIED
    )

    if disconnected_fragment_ids:
        cards.append(
            TypedFailureCard(
                judge_name="composition_engine",
                failure_type="fragment_topology_disconnected",
                severity=FailureSeverity.BLOCKER,
                description="Selected fragment stitching topology does not connect all fragments into one composed bundle.",
                remediation_hint="Add a valid stitch path for the disconnected fragment or remove it from the composition request.",
                metadata={
                    "disconnected_fragment_ids": disconnected_fragment_ids,
                    "selected_stitch_pairs": list(
                        composition_certificate.metadata.get("selected_stitch_pairs", [])
                    ),
                },
            )
        )
    if alignment_report.incompatible_pairs or any(
        "incompatible" in reason or "missing alignment coverage" in reason for reason in lowered_reasons
    ):
        cards.append(
            TypedFailureCard(
                judge_name="composition_engine",
                failure_type="alignment_incompatible",
                severity=FailureSeverity.BLOCKER,
                description="Semantic alignment is incompatible for strict fragment composition.",
                remediation_hint="Provide compatible interface evidence or remove the conflicting fragment stitch.",
                metadata={
                    "incompatible_pairs": [list(pair) for pair in alignment_report.incompatible_pairs],
                    "blocking_reasons": [
                        reason
                        for reason in blocking_reasons
                        if "incompatible" in reason.lower()
                        or "missing alignment coverage" in reason.lower()
                    ],
                },
            )
        )
    if any("unobserved" in reason for reason in lowered_reasons):
        cards.append(
            TypedFailureCard(
                judge_name="composition_engine",
                failure_type="unobserved_interface",
                severity=FailureSeverity.BLOCKER,
                description="Composition attempted to stitch an interface that is not fully observed.",
                remediation_hint="Expose an observed interface or keep the fragments uncomposed.",
                metadata={
                    "blocking_reasons": [
                        reason for reason in blocking_reasons if "unobserved" in reason.lower()
                    ],
                    "interface_ids": [
                        entry.interface_id for entry in interface_mapping.entries if not entry.observed
                    ],
                },
            )
        )
    if any("cycle" in reason or "self-loop" in reason for reason in lowered_reasons):
        cards.append(
            TypedFailureCard(
                judge_name="composition_engine",
                failure_type="directed_cycle",
                severity=FailureSeverity.BLOCKER,
                description="Fragment composition would introduce a directed cycle or self-loop.",
                remediation_hint="Revise the interface mapping or graph structure before composing.",
                metadata={
                    "blocking_reasons": [
                        reason
                        for reason in blocking_reasons
                        if "cycle" in reason.lower() or "self-loop" in reason.lower()
                    ],
                },
            )
        )
    if composition_certificate.status == "deferred" and latent_pairs:
        cards.append(
            TypedFailureCard(
                judge_name="composition_engine",
                failure_type="latent_bridge_pending_review",
                severity=FailureSeverity.WARNING,
                description="Composition succeeded structurally but latent-bridge interfaces still require human verification.",
                remediation_hint="Human-verify the latent bridge before promoting the composition result.",
                metadata={
                    "pairs": latent_pairs,
                },
            )
        )
    if composition_certificate.status == "deferred" and proxy_pairs:
        cards.append(
            TypedFailureCard(
                judge_name="composition_engine",
                failure_type="proxy_alignment_pending_review",
                severity=FailureSeverity.WARNING,
                description="Composition succeeded structurally but proxy-style interfaces still require expert review.",
                remediation_hint="Review the proxy alignment evidence before promoting the composition result.",
                metadata={"pairs": proxy_pairs},
            )
        )
    if alignment_report.ontology_mismatch_warnings:
        cards.append(
            TypedFailureCard(
                judge_name="composition_engine",
                failure_type="ontology_warning",
                severity=FailureSeverity.INFO,
                description="Ontology mismatch warnings were surfaced during fragment alignment.",
                remediation_hint="Inspect semantic namespace mappings and approve or revise the stitch.",
                metadata={"warnings": list(alignment_report.ontology_mismatch_warnings)},
            )
        )

    return _dedupe_cards(cards)


def persist_composition_failure_card_bundle(
    store: ArtifactStore,
    bundle: CompositionFailureCardBundle,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _COMPOSITION_FAILURE_CARD_BUNDLE_SCHEMA_NAME,
    schema_version: str = _COMPOSITION_FAILURE_CARD_BUNDLE_SCHEMA_VERSION,
) -> CompositionFailureCardBundleRef:
    ref = put_json_artifact(
        store,
        bundle.model_dump(mode="json"),
        kind=_COMPOSITION_FAILURE_CARD_BUNDLE_SCHEMA_NAME,
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return CompositionFailureCardBundleRef.model_validate(ref)


def load_composition_failure_card_bundle(
    store: ArtifactStore,
    ref: CompositionFailureCardBundleRef,
) -> CompositionFailureCardBundle:
    payload = get_json_artifact(store, ref.artifact_id)
    return CompositionFailureCardBundle.model_validate(payload)


def _pair_labels(certificates: Sequence[VariableAlignmentCertificate]) -> list[str]:
    return sorted(
        {
            f"{certificate.fragment_a_id}:{certificate.variable_a}"
            f" <-> {certificate.fragment_b_id}:{certificate.variable_b}"
            for certificate in certificates
        }
    )


def _dedupe_cards(cards: Sequence[TypedFailureCard]) -> list[TypedFailureCard]:
    unique: dict[tuple[str, str, str], TypedFailureCard] = {}
    for card in cards:
        key = (
            card.failure_type,
            card.severity.value if hasattr(card.severity, "value") else str(card.severity),
            str(card.metadata),
        )
        unique.setdefault(key, card)
    return [unique[key] for key in sorted(unique)]


__all__ = [
    "CompositionFailureCardBundle",
    "build_composition_failure_cards",
    "load_composition_failure_card_bundle",
    "persist_composition_failure_card_bundle",
]
