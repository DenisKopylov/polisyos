"""Bounded multilingual candidate assurance over Lex and canonical CAS custody.

Lex's legal_authority owner remains responsible for legal competence; its semantic
benchmark remains the legal readiness owner. This new rendition comparator reuses
FileSystemCAS integrity and Ed25519Verifier trust/identity/revocation semantics.
Caller-authored frames and synthetic ground truth never establish legal meaning.
W5-K06 permits only a finite diagnostic; no signer or equivalence issuer exists here.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.signing import Ed25519Verifier
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions

KIND = "lex.multilingual_assurance"
SCHEMA = "polisyos.lex.multilingual_assurance"


class AssuranceModel(BaseModel):
    """Strict frozen candidate data, never an appointment or authority assertion."""

    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always")


class ActionProfile(AssuranceModel):
    """Declared candidate action ground truth for one completely named context."""

    allowed: tuple[str, ...]
    required: tuple[str, ...]
    forbidden: tuple[str, ...]

    @model_validator(mode="after")
    def _consistent(self) -> ActionProfile:
        if (set(self.allowed) | set(self.required)) & set(self.forbidden):
            raise ValueError("contradictory_action_profile")
        for values in (self.allowed, self.required, self.forbidden):
            if len(values) != len(set(values)):
                raise ValueError("duplicate_action")
        return self


class CandidateRendition(AssuranceModel):
    """Whole text plus a content-bound synthetic semantic/action frame."""

    text: str = Field(min_length=1)
    digest: str = Field(pattern="^[0-9a-f]{64}$")
    status_ids: tuple[str, ...] = Field(min_length=1)
    modality: str = Field(min_length=1)
    action_profiles: dict[str, ActionProfile]


class AssurancePacket(AssuranceModel):
    """Complete finite candidate test denominator, never a legal source admission."""

    schema_version: Literal["1"]
    proposition_id: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    contexts: tuple[str, ...] = Field(min_length=1)
    source_language: str
    target_language: str
    jurisdiction: str
    ground_truth: Literal["synthetic_candidate"]
    valid_until: datetime
    excluded_contexts: tuple[str, ...]
    rule_refs: tuple[str, ...]
    qualified_holders: tuple[()]
    source: CandidateRendition
    target: CandidateRendition
    defective_target: CandidateRendition

    @model_validator(mode="after")
    def _complete_denominator(self) -> AssurancePacket:
        if len(set(self.contexts)) != len(self.contexts):
            raise ValueError("duplicate_context")
        if set(self.contexts) & set(self.excluded_contexts):
            raise ValueError("included_excluded_context_overlap")
        for rendition in (self.source, self.target, self.defective_target):
            if set(rendition.action_profiles) != set(self.contexts):
                raise ValueError("context_denominator_mismatch")
        if self.valid_until.tzinfo is None:
            raise ValueError("validity_timezone_missing")
        return self


class CandidateAssuranceResult(AssuranceModel):
    """Unsigned diagnostic certificate form with enforced scope and empty authority."""

    proposition_id: str
    purpose: str
    contexts: tuple[str, ...]
    excluded_contexts: tuple[str, ...]
    source_digest: str
    target_digest: str
    packet_digest: str
    comparison: Literal["candidate_match", "refused"]
    reasons: tuple[str, ...]
    valid_until: datetime
    signature_status: str = "not_checked"
    required_role: Literal["multilingual_authority_adjudicator"] = (
        "multilingual_authority_adjudicator"
    )
    predicate_provenance: Literal["consumer_asserted"] = "consumer_asserted"

    @property
    def equivalence_established(self) -> Literal[False]:
        """Refuse legal equivalence regardless of structural or fixture conformance."""
        return False

    @property
    def signer(self) -> None:
        """Keep the signature slot typed and empty by construction."""
        return None

    @property
    def qualified_holders(self) -> tuple[()]:
        """No institutional holder is appointed by candidate machinery."""
        return ()

    def projection(self) -> dict[str, Any]:
        """Expose scope and refusal explicitly for MACHINE/Lex audit consumers."""
        return {
            **self.model_dump(mode="json"),
            "equivalence_established": False,
            "signer": None,
            "qualified_holders": [],
            "trust_roots": [],
            "key_custody": None,
            "withheld_propositions": ["WP-11", "WP-12"],
            "authoritative_for": ["finite_candidate_action_comparison"],
            "may_not_use_for": [
                "legal_authority",
                "semantic_equivalence",
                "outside_tested_denominator",
                "operator_comprehension",
            ],
            "check_standing": {
                "source_content_integrity": "recomputed",
                "rendition_content_integrity": "recomputed",
                "declared_status_modality_action_comparison": "recomputed",
                "complete_declared_context_denominator": "recomputed",
                "candidate_semantic_frames": "consumer_asserted",
                "natural_language_frame_correspondence": "not_established",
                "glossary_release": "not_established",
                "institutional_adjudication": "not_established",
                "source_legal_authority": "not_established",
                "plain_language_adaptation": "not_established",
                "bidi_and_accessibility": "not_established",
                "numeric_temporal_uncertainty_frame_adequacy": "not_established",
                "human_comprehension": "not_established",
            },
            "limitations": [
                "natural_language_frame_correspondence_not_established",
                "institutional_adjudication_absent",
            ],
        }


class AssuranceReceipt(AssuranceModel):
    """Content-addressed producer result for bounded downstream readback."""

    artifact_ref: str


class RTLSourcePack(AssuranceModel):
    """Named candidate source-content fixture, distinct from RTL UI admission."""

    jurisdiction: Literal["IL-Hebr"] = "IL-Hebr"
    withheld_propositions: tuple[Literal["WP-11"], Literal["WP-12"]] = ("WP-11", "WP-12")

    @property
    def evidence_requirements(self) -> dict[str, None]:
        """Return WP-12's complete, deliberately unfilled evidence slots."""
        return dict.fromkeys(
            (
                "authoritative_scripts",
                "unicode_normalisation",
                "shaping",
                "bidi_isolation",
                "logical_focus_reading_order",
                "locale_formatting",
                "copy_search_export",
                "spoofing_controls",
                "accessibility",
                "mixed_direction_fixtures",
            )
        )

    @property
    def ui_locale_admitted(self) -> Literal[False]:
        """Source-content handling cannot admit a product locale."""
        return False

    @property
    def source_authority_established(self) -> Literal[False]:
        """A named pack without evidence supplies no jurisdiction authority."""
        return False


def rtl_source_pack() -> RTLSourcePack:
    """Produce the candidate RTL source-content pack with every evidence slot empty."""
    return RTLSourcePack()


def _digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def compare_candidate(payload: Mapping[str, Any] | AssurancePacket) -> CandidateAssuranceResult:
    """Compare every declared semantic/action context while refusing legal equivalence."""
    packet = AssurancePacket.model_validate(payload)
    reasons: set[str] = set()
    if hashlib.sha256(packet.source.text.encode()).hexdigest() != packet.source.digest:
        reasons.add("source_content_unbound")
    if hashlib.sha256(packet.target.text.encode()).hexdigest() != packet.target.digest:
        reasons.add("rendition_content_unbound")
    if packet.source.status_ids != packet.target.status_ids:
        reasons.add("status_profile_changed")
    if packet.source.modality != packet.target.modality:
        reasons.add("legal_modality_changed")
    for context in packet.contexts:
        source = packet.source.action_profiles[context]
        target = packet.target.action_profiles[context]
        if any(
            set(getattr(source, k)) != set(getattr(target, k))
            for k in ("allowed", "required", "forbidden")
        ):
            reasons.add("action_profile_changed")
    return CandidateAssuranceResult(
        proposition_id=packet.proposition_id,
        purpose=packet.purpose,
        contexts=packet.contexts,
        excluded_contexts=packet.excluded_contexts,
        source_digest=packet.source.digest,
        target_digest=packet.target.digest,
        packet_digest=_digest(packet.model_dump(mode="json")),
        comparison="refused" if reasons else "candidate_match",
        reasons=tuple(sorted(reasons)),
        valid_until=packet.valid_until,
    )


def _write(cas: FileSystemCAS, payload: Mapping[str, Any]) -> str:
    ref = cas.put_json(
        dict(payload),
        ArtifactWriteOptions(
            kind=KIND, media_type="application/json", schema=SchemaInfo(name=SCHEMA, version="1")
        ),
    )
    return str(ref.artifact_id)


def run_assurance(payload: Mapping[str, Any], *, cas: FileSystemCAS) -> AssuranceReceipt:
    """Persist a candidate comparison and its exact complete source/target denominator."""
    packet = AssurancePacket.model_validate(payload)
    result = compare_candidate(packet)
    ref = _write(
        cas,
        {
            "record_type": "candidate_result",
            "schema_version": "1",
            "generated_at": datetime.now(UTC).isoformat(),
            "packet": packet.model_dump(mode="json"),
            "result": result.model_dump(mode="json"),
        },
    )
    return AssuranceReceipt(artifact_ref=ref)


def recompute_assurance_payload(payload: Mapping[str, Any]) -> CandidateAssuranceResult:
    """Recompute every decisive output from resolved immutable candidate bytes."""
    if payload["record_type"] != "candidate_result":
        raise ValueError("assurance_wrong_record_type")
    result = compare_candidate(payload["packet"])
    if result.model_dump(mode="json") != payload["result"]:
        raise ValueError("assurance_result_recompute_mismatch")
    return result


def replay_assurance_result(cas: FileSystemCAS, artifact_ref: str) -> CandidateAssuranceResult:
    """Recompute historical bytes without asserting present validity or authority."""
    if not cas.verify(artifact_ref).ok or cas.get_manifest(artifact_ref).kind != KIND:
        raise ValueError("assurance_content_integrity_failed")
    return recompute_assurance_payload(json.loads(cas.get_bytes(artifact_ref)))


def _revoked(cas: FileSystemCAS, artifact_ref: str) -> bool:
    # Enumerate the existing CAS owner's complete kind denominator: no parallel mutable ledger.
    for member in cas.iter_artifact_ids():
        if cas.get_manifest(member).kind != KIND:
            continue
        if not cas.verify(member).ok:
            raise ValueError("assurance_custody_integrity_failed")
        payload = json.loads(cas.get_bytes(member))
        if payload.get("record_type") == "candidate_revocation":
            if (
                set(payload)
                != {"record_type", "schema_version", "artifact_ref", "reason", "recorded_at"}
                or not payload["reason"]
            ):
                raise ValueError("assurance_revocation_ambiguous")
            if payload["artifact_ref"] == artifact_ref:
                return True
    return False


def read_assurance_result(
    cas: FileSystemCAS,
    artifact_ref: str,
    *,
    proposition_id: str,
    purpose: str,
    context_id: str,
    qualified_holder: str | None,
    now: datetime | None = None,
) -> CandidateAssuranceResult:
    """Enforce W5-K06 finite scope, current custody and vacant-holder refusal on read."""
    result = replay_assurance_result(cas, artifact_ref)
    if (
        proposition_id != result.proposition_id
        or purpose != result.purpose
        or context_id not in result.contexts
        or qualified_holder is not None
    ):
        raise ValueError("outside_declared_denominator")
    at = now or datetime.now(UTC)
    if at.tzinfo is None or at >= result.valid_until:
        raise ValueError("assurance_expired")
    if _revoked(cas, artifact_ref):
        raise ValueError("assurance_revoked")
    signature = cas.verify_signature(
        ArtifactID.model_validate(artifact_ref),
        Ed25519Verifier(strict_identity=True),
        strict_identity=True,
    )
    status = "missing_signature" if signature.status.value == "unsigned" else signature.status.value
    return CandidateAssuranceResult.model_validate(
        {**result.model_dump(), "signature_status": status}
    )


def revoke_assurance(cas: FileSystemCAS, artifact_ref: str, *, reason: str) -> str:
    """Append a conservative candidate invalidation; history is retained in canonical CAS."""
    replay_assurance_result(cas, artifact_ref)
    if not reason.strip():
        raise ValueError("revocation_reason_missing")
    return _write(
        cas,
        {
            "record_type": "candidate_revocation",
            "schema_version": "1",
            "artifact_ref": artifact_ref,
            "reason": reason,
            "recorded_at": datetime.now(UTC).isoformat(),
        },
    )


class CandidateSourceContent(AssuranceModel):
    """Explicitly scoped RTL source bytes; language/jurisdiction remain declarations."""

    jurisdiction: Literal["IL-Hebr"]
    language: Literal["he"]
    script: Literal["Hebr"]
    source_text: str = Field(min_length=1)


def run_source_content(
    payload: Mapping[str, Any],
    *,
    cas: FileSystemCAS,
) -> AssuranceReceipt:
    """Persist actual candidate source text without filling jurisdiction evidence slots."""
    content = CandidateSourceContent.model_validate(payload)
    source_digest = hashlib.sha256(content.source_text.encode("utf-8")).hexdigest()
    ref = _write(
        cas,
        {
            "record_type": "candidate_source_content",
            "schema_version": "1",
            "generated_at": datetime.now(UTC).isoformat(),
            "content": content.model_dump(mode="json"),
            "source_digest": source_digest,
        },
    )
    return AssuranceReceipt(artifact_ref=ref)


def recompute_source_content(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Recompute source content binding and retain every withheld evidence slot."""
    if payload.get("record_type") != "candidate_source_content":
        raise ValueError("source_content_record_type_mismatch")
    content = CandidateSourceContent.model_validate(payload["content"])
    if hashlib.sha256(content.source_text.encode("utf-8")).hexdigest() != payload["source_digest"]:
        raise ValueError("source_content_binding_mismatch")
    return {
        **content.model_dump(mode="json"),
        "source_digest": payload["source_digest"],
        "source_authority_established": False,
        "ui_locale_admitted": False,
        "withheld_propositions": ["WP-11", "WP-12"],
        "evidence_requirements": rtl_source_pack().evidence_requirements,
        "authoritative_for": ["candidate_source_content_custody"],
        "may_not_use_for": ["jurisdiction_admission", "source_authority", "ui_locale_admission"],
        "scope_provenance": "consumer_asserted",
        "bidi_and_accessibility": "not_established",
    }


def read_source_content(
    cas: FileSystemCAS,
    artifact_ref: str,
    *,
    jurisdiction: str,
    language: str,
    script: str,
) -> dict[str, Any]:
    """Resolve preserved bytes for the exact named source-content scope only."""
    if not cas.verify(artifact_ref).ok or cas.get_manifest(artifact_ref).kind != KIND:
        raise ValueError("source_content_integrity_failed")
    result = recompute_source_content(json.loads(cas.get_bytes(artifact_ref)))
    if (jurisdiction, language, script) != (
        result["jurisdiction"],
        result["language"],
        result["script"],
    ):
        raise ValueError("source_content_scope_mismatch")
    return result
