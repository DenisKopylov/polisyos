"""Recompute bounded technical inspection facts for an exact source-owned CAS view.

This extends Foundry's existing method-output reader and Runtime's concrete
source-read owner check. Persisted evidence is a candidate until both selected
views and the current enforcing owner have been rechecked. It grants no claim,
publication, producer-authenticity, or runtime-closeout authority.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, ClassVar, Final, Literal, Protocol, cast

from pydantic import BaseModel, ConfigDict

from polisyos.core.artifacts import (
    ArtifactID,
    ArtifactRef,
    CanonInfo,
    ProducerInfo,
    PutOptions,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.canonical_profile import (
    CoreJsonArtifactBoundedRead,
    CoreJsonReadLimits,
    read_core_json_artifact_bounded,
    validate_core_model_bounded_read,
)
from polisyos.core.canon import CanonicalResourceLimits, CanonSpec, to_bounded_canonical_bytes
from polisyos.core.contracts.foundry import MethodArtifactOutputRef
from polisyos.foundry.execute import read_method_artifact_output_bounded

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import CoreJSONArtifactBoundedMemberReader


class _EvidenceWriter(Protocol):
    def put_bytes(
        self, data: bytes, opts: PutOptions, *, return_selected_profile: bool = False
    ) -> ArtifactRef: ...


TECHNICAL_INSPECTION_PURPOSE: Final = "technical_artifact_inspection"
TECHNICAL_INSPECTION_EVIDENCE_KIND: Final = "runtime.technical_inspection_evidence"
TECHNICAL_INSPECTION_EVIDENCE_MEDIA_TYPE: Final = "application/json"
TECHNICAL_INSPECTION_RULE_VERSION: Final = "runtime.technical_artifact_inspection/1"
TECHNICAL_INSPECTION_DENIED_PURPOSES: Final = (
    "runtime_closeout_authority",
    "publication",
    "claim_evidence",
    "producer_authenticity",
    "method_adequacy",
    "policy_admissibility",
)
_EVIDENCE_CANON = CanonSpec()
_EVIDENCE_LIMITS = CoreJsonReadLimits(32768, 32, 8192, 8192)
# A is read once using its defining owner policy; E is read once using the
# explicit evidence policy. Each selected manifest is read and verified once.
_SUBJECT_PAYLOAD_CAP = 65536
_MAX_SOURCE_BYTES = 65536 + 2 * 4096 + 32768 + 2 * 8192


class TechnicalInspectionEvidence(BaseModel):
    """Persist only the fact whose complete content is freshly recomputed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ARTIFACT_KIND: ClassVar[str] = TECHNICAL_INSPECTION_EVIDENCE_KIND
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = TECHNICAL_INSPECTION_EVIDENCE_MEDIA_TYPE
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "TechnicalInspectionEvidence"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"

    schema_version: Literal["1.0"] = "1.0"
    purpose: Literal["technical_artifact_inspection"] = "technical_artifact_inspection"
    rule_version: Literal["runtime.technical_artifact_inspection/1"] = (
        "runtime.technical_artifact_inspection/1"
    )
    fact: dict[str, Any]


@dataclass(frozen=True, slots=True, init=False)
class VerifiedTechnicalInspection:
    """Return a freshly verified fact; no consumer accepts this as an input grant."""

    selected_ref: ArtifactRef
    evidence_ref: ArtifactRef
    subject_read: CoreJsonArtifactBoundedRead
    observed_source_bytes: int


class TechnicalInspectionOwnerNotEstablishedError(ValueError):
    """Refuse an unqualified current enforcement provider before protected I/O."""

    code: ClassVar[str] = "technical_inspection_owner_not_established"

    def __init__(self, reason: str) -> None:
        """Retain a typed absence verdict and the failed provider relation."""
        self.reason = reason
        super().__init__(f"{self.code}:{reason}")


def _require_stock_enforcement_provider(store: object) -> None:
    """Qualify the complete stock provider and its root/configuration plane.

    This narrow cohort trusts pinned stock Python classes, not an outer CAS flag
    around a constructor-injected provider. Exact known wrappers are inspected;
    the configured guarded handle remains the handle used for all actual I/O.
    Private/class/interpreter mutation is outside this supported stock domain.
    """
    from pathlib import Path

    from polisyos.core.artifacts._atomic_write import AtomicFileWriter
    from polisyos.core.artifacts._layout import CASPathLayout
    from polisyos.core.artifacts._manifest_lifecycle import ManifestLifecycle
    from polisyos.core.artifacts.ir_adapter import CoreToIRArtifactStoreAdapter
    from polisyos.core.artifacts.ownership import (
        ArtifactOwnershipIndex,
        _RootTransactionCoordinator,
    )
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.runtime.http.resilience import GuardedDependencyProxy

    owner = store
    seen: set[int] = set()
    while type(owner) in (CoreToIRArtifactStoreAdapter, GuardedDependencyProxy):
        if id(owner) in seen:
            raise TechnicalInspectionOwnerNotEstablishedError("adapter_cycle")
        seen.add(id(owner))
        owner = (
            cast("CoreToIRArtifactStoreAdapter", owner).store
            if type(owner) is CoreToIRArtifactStoreAdapter
            else cast("GuardedDependencyProxy", owner)._target
        )
    if type(owner) is not FileSystemCAS:
        raise TechnicalInspectionOwnerNotEstablishedError("cas_provider_not_stock")
    owner = cast("FileSystemCAS", owner)
    index, coordinator = owner._ownership_index, owner._coordinator
    if (
        type(index) is not ArtifactOwnershipIndex
        or type(coordinator) is not _RootTransactionCoordinator
        or type(owner._layout) is not CASPathLayout
        or type(owner._files) is not AtomicFileWriter
        or type(owner._manifests) is not ManifestLifecycle
    ):
        raise TechnicalInspectionOwnerNotEstablishedError("enforcement_provider_not_stock")
    root = owner.root
    path_type = type(Path("."))
    if type(root) is not path_type or not root.is_absolute() or root.resolve(strict=True) != root:
        raise TechnicalInspectionOwnerNotEstablishedError("cas_root_not_canonical")
    directory = root / "artifacts" / "ownership"
    transaction_root = directory / "transactions"
    # These are the stock constructors' complete path/configuration relations,
    # not a list of admission-method names. A custom provider is refused whole.
    expected_paths = (
        (index.root, root),
        (index.directory, directory),
        (index.path, directory / "index.json"),
        (index.signature_path, directory / "index.signature.json"),
        (index._lock_path, directory / "index.lock"),
        (coordinator.root, root),
        (coordinator.transaction_root, transaction_root),
        (coordinator.lock_directory, transaction_root / "locks"),
        (coordinator.root_lock_path, transaction_root / "root.lock"),
        (owner._layout.root, root),
        (owner._layout.base, root / "artifacts" / "sha256"),
        (owner.base, root / "artifacts" / "sha256"),
    )
    if (
        index._coordinator is not coordinator
        or type(owner._read_only) is not bool
        or type(index.read_only) is not bool
        or index.read_only is not owner._read_only
        or owner._ownership_enforced is not True
        or any(
            type(actual) is not path_type or actual != expected
            for actual, expected in expected_paths
        )
    ):
        raise TechnicalInspectionOwnerNotEstablishedError(
            "enforcement_provider_root_or_config_mismatch"
        )


def _current_owner(store: object) -> tuple[str, str | None]:
    """Reconcile the existing active reader and the concrete enforcing resolver."""
    from polisyos.runtime.http.services.control.observational_source_access import (
        _current_source_read_scope,
        _reader_source_read_scope,
        _require_source_read_owner,
    )

    current = _current_source_read_scope()
    if current.tenant_id is None:
        raise ValueError("technical_inspection_current_tenant_missing")
    scope = _reader_source_read_scope(current.tenant_id, current.cell_id)
    _require_source_read_owner(store, scope)
    _require_stock_enforcement_provider(store)
    return current.tenant_id, scope.cell_id


def _selected(ref: ArtifactRef) -> ArtifactRef:
    if type(ref) not in (ArtifactRef, MethodArtifactOutputRef):
        raise ValueError("technical_inspection_selected_ref_required")
    fields = object.__getattribute__(ref, "__dict__")
    if type(fields) is not dict or set(fields) != set(ArtifactRef.model_fields):
        raise ValueError("technical_inspection_selected_ref_required")
    aid, kind, media, profile = (
        fields["artifact_id"],
        fields["kind"],
        fields["media_type"],
        fields["manifest_profile_sha256"],
    )
    if (
        type(aid) is not ArtifactID
        or type(kind) is not str
        or not 0 < len(kind) <= 256
        or type(media) is not str
        or not 0 < len(media) <= 256
        or type(profile) is not str
        or re.fullmatch(r"sha256:[0-9a-f]{64}", profile) is None
    ):
        raise ValueError("technical_inspection_selected_ref_required")
    root = object.__getattribute__(aid, "__dict__").get("root")
    if type(root) is not str or re.fullmatch(r"sha256:[0-9a-f]{64}", root) is None:
        raise ValueError("technical_inspection_selected_ref_required")
    return ArtifactRef(
        artifact_id=ArtifactID.model_validate(root),
        kind=kind,
        media_type=media,
        manifest_profile_sha256=profile,
    )


def _subject_fact(
    store: object, selected_ref: ArtifactRef
) -> tuple[TechnicalInspectionEvidence, CoreJsonArtifactBoundedRead]:
    owner = _current_owner(store)
    selected_ref = _selected(selected_ref)
    read = read_method_artifact_output_bounded(store, selected_ref, max_bytes=_SUBJECT_PAYLOAD_CAP)
    if read.effective_ref != selected_ref or not read.payload_integrity_verified:
        raise ValueError("technical_inspection_subject_identity_invalid")
    if read.observed_source_bytes > _SUBJECT_PAYLOAD_CAP + 2 * 4096:
        raise ValueError("technical_inspection_subject_budget_exceeded")
    # Includes the complete owner/canon/input/metadata view, not a producer-name
    # proxy. The source owner reader already checks the exact profile contract.
    manifest = read.manifest.model_dump(mode="json", by_alias=True)
    manifest.pop("created_at", None)  # Creation time is outside the profile hash.
    fact = {
        "selected_ref": selected_ref.model_dump(mode="json"),
        "payload_sha256": "sha256:" + hashlib.sha256(read.raw_payload_bytes).hexdigest(),
        "manifest": manifest,
        "reader_policy_id": read.profile_read.reader_policy_id,
        "read_limits": asdict(read.limits),
        "evidence_read_limits": asdict(_EVIDENCE_LIMITS),
        "aggregate_source_byte_cap": _MAX_SOURCE_BYTES,
        "tenant_id": owner[0],
        "cell_id": owner[1],
        "predicate_provenance": "recomputed",
        "may_not_use_for": list(TECHNICAL_INSPECTION_DENIED_PURPOSES),
    }
    return TechnicalInspectionEvidence(fact=fact), read


def _evidence_options(selected_ref: ArtifactRef) -> PutOptions:
    return PutOptions(
        kind=TECHNICAL_INSPECTION_EVIDENCE_KIND,
        media_type=TECHNICAL_INSPECTION_EVIDENCE_MEDIA_TYPE,
        schema=SchemaInfo(name="TechnicalInspectionEvidence", version="1.0"),
        canon=CanonInfo.from_spec(_EVIDENCE_CANON),
        producer=ProducerInfo(
            component="runtime.quality.technical_inspection_evidence",
            version=TECHNICAL_INSPECTION_RULE_VERSION,
        ),
        inputs=[input_ref_from_artifact_ref(selected_ref, role="inspection_subject")],
    )


def _encode_evidence(evidence: TechnicalInspectionEvidence) -> bytes:
    return to_bounded_canonical_bytes(
        evidence.model_dump(mode="python"),
        _EVIDENCE_CANON,
        CanonicalResourceLimits(
            TECHNICAL_INSPECTION_RULE_VERSION,
            _EVIDENCE_LIMITS.max_bytes,
            _EVIDENCE_LIMITS.max_depth,
            _EVIDENCE_LIMITS.max_elements,
        ),
    )


def create_technical_inspection_evidence(store: object, selected_ref: ArtifactRef) -> ArtifactRef:
    """Persist a bounded CAN.2 fact after the actual guarded source-owned read.

    The existing CAS transaction owner publishes E and its selected ref; A is
    unchanged. Payload encoding and subsequent inspection reads are bounded.
    CAS's legacy CAN.2 transaction/recovery internals are not a bounded writer
    claim; the local-only CAN.3 writer does not support enforcing owner handles.
    """
    selected_ref = _selected(selected_ref)
    evidence, _read = _subject_fact(store, selected_ref)
    raw = _encode_evidence(evidence)
    _current_owner(store)
    # Preserve configured guards: never unwrap the handle for a read or write.
    ref = cast("_EvidenceWriter", store).put_bytes(
        raw, _evidence_options(selected_ref), return_selected_profile=True
    )
    ref = _selected(ref)
    verify_technical_inspection_evidence(store, selected_ref, ref)
    return ref


def verify_technical_inspection_evidence(
    store: object, selected_ref: ArtifactRef, evidence_ref: ArtifactRef
) -> VerifiedTechnicalInspection:
    """Resolve E and A, enforce current ownership, and recompute the whole fact.

    Matching existence, labels, hashes without bytes, or an old successful check
    do not satisfy this predicate. Current CAS exact-view claims are consulted by
    both bounded reads, including after access revocation or scope changes.
    """
    selected_ref, evidence_ref = _selected(selected_ref), _selected(evidence_ref)
    _current_owner(store)
    if (evidence_ref.kind, evidence_ref.media_type) != (
        TECHNICAL_INSPECTION_EVIDENCE_KIND,
        TECHNICAL_INSPECTION_EVIDENCE_MEDIA_TYPE,
    ):
        raise ValueError("technical_inspection_evidence_ref_owner_invalid")
    evidence_read = read_core_json_artifact_bounded(
        cast("CoreJSONArtifactBoundedMemberReader", store),
        evidence_ref,
        limits=_EVIDENCE_LIMITS,
    )
    validate_core_model_bounded_read(TechnicalInspectionEvidence, evidence_read)
    manifest = evidence_read.manifest
    options = _evidence_options(selected_ref)
    if (
        manifest.canon != options.canon
        or manifest.inputs != options.inputs
        or manifest.producer != options.producer
        or manifest.env is not None
        or manifest.governance is not None
        or manifest.tenant_context is not None
        or manifest.same_input_closure is not None
        or manifest.authority is not None
        or manifest.warnings
        or manifest.manifest_schema_version != "v3"
    ):
        raise ValueError("technical_inspection_evidence_profile_invalid")
    expected, subject_read = _subject_fact(store, selected_ref)
    # Python mapping equality conflates False and 0. Recompute canonical bytes
    # so every type, member and value in the full fact must match exactly.
    if evidence_read.raw_payload_bytes != _encode_evidence(expected):
        raise ValueError("technical_inspection_evidence_fact_mismatch")
    usage = evidence_read.observed_source_bytes + subject_read.observed_source_bytes
    if usage > _MAX_SOURCE_BYTES:
        raise ValueError("technical_inspection_aggregate_budget_exceeded")
    # Recheck after the reads as well; no earlier success is cached as access.
    _current_owner(store)
    result = object.__new__(VerifiedTechnicalInspection)
    for name, value in (
        ("selected_ref", selected_ref.model_copy(deep=True)),
        ("evidence_ref", evidence_ref.model_copy(deep=True)),
        ("subject_read", subject_read),
        ("observed_source_bytes", usage),
    ):
        object.__setattr__(result, name, value)
    return result
