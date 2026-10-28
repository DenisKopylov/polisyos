"""Neutral trusted-composition port for registered materialization admission.

Private minting operations belong only to the appointed Runtime factory and the
actual canonical registered producer. An HTTP field, manifest, or authorial DTO
cannot populate this port. This module does not implement that producer bridge.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from threading import RLock
from typing import Literal, get_args
from weakref import WeakKeyDictionary

from polisyos.core.artifacts.manifest import ArtifactRef, artifact_ref_identity_key
from polisyos.core.contracts.decision_validity import RegisteredMaterialization

SourceAdmissionOperation = Literal[
    "genesis", "admit", "withdraw", "readmit", "supersede", "read_event"
]


@dataclass(frozen=True, slots=True)
class _AuthorityState:
    issuer_key: str
    tenant_id: str
    cell_id: str
    provider_id: str
    registration_key: str
    effective_view_contract_ref: ArtifactRef
    use_contract_ref: ArtifactRef
    permitted_operations: frozenset[SourceAdmissionOperation]
    validate_issuer: Callable[[], None]


@dataclass(frozen=True, slots=True)
class _MaterializationState:
    authority: SourceAdmissionAuthority
    materialization_json: str
    validate_capture: Callable[[], None]


_AUTHORITIES: WeakKeyDictionary[SourceAdmissionAuthority, _AuthorityState] = WeakKeyDictionary()
_MATERIALIZATIONS: WeakKeyDictionary[VerifiedRegisteredMaterialization, _MaterializationState] = (
    WeakKeyDictionary()
)
_REGISTRY_LOCK = RLock()


class SourceAdmissionAuthority:
    """Opaque exact identity minted by the trusted installed Runtime factory."""

    __slots__ = ("__weakref__",)

    def __init__(self) -> None:
        raise TypeError("source admission authority requires the configured Runtime factory")


class VerifiedRegisteredMaterialization:
    """Opaque observed producer relation; not constructible from a candidate DTO."""

    __slots__ = ("__weakref__",)

    def __init__(self) -> None:
        raise TypeError("source admission requires the canonical registered producer")


def _require_source_admission_authority(authority: object) -> _AuthorityState:
    if type(authority) is not SourceAdmissionAuthority:
        raise ValueError("source_admission_authority_not_established")
    with _REGISTRY_LOCK:
        state = _AUTHORITIES.get(authority)
    if state is None:
        raise ValueError("source_admission_authority_not_established")
    if state.validate_issuer() is not None:
        raise ValueError("source_admission_factory_validation_not_established")
    return state


def _bind_source_admission_authority(
    *,
    issuer_key: str,
    tenant_id: str,
    cell_id: str,
    provider_id: str,
    registration_key: str,
    effective_view_contract_ref: ArtifactRef,
    use_contract_ref: ArtifactRef,
    permitted_operations: frozenset[SourceAdmissionOperation],
    validate_issuer: Callable[[], None],
) -> SourceAdmissionAuthority:
    """Private Runtime factory seam, never a request/candidate composition API.

    The caller must validate its actual installed factory/config/grant binding;
    an arbitrary validator is not itself evidence. C106 owns that concrete call.
    """
    if (
        any(
            not isinstance(v, str) or not v.strip()
            for v in (issuer_key, tenant_id, cell_id, provider_id, registration_key)
        )
        or validate_issuer() is not None
    ):
        raise ValueError("source_admission_factory_validation_not_established")
    if (
        type(permitted_operations) is not frozenset
        or not permitted_operations
        or not permitted_operations <= frozenset(get_args(SourceAdmissionOperation))
    ):
        raise ValueError("source_admission_operation_scope_not_established")
    view = ArtifactRef.model_validate_json(
        effective_view_contract_ref.model_dump_json(), strict=True
    )
    use = ArtifactRef.model_validate_json(use_contract_ref.model_dump_json(), strict=True)
    if view.manifest_profile_sha256 is None or use.manifest_profile_sha256 is None:
        raise ValueError("source_admission_selected_profile_required")
    authority = object.__new__(SourceAdmissionAuthority)
    with _REGISTRY_LOCK:
        _AUTHORITIES[authority] = _AuthorityState(
            issuer_key,
            tenant_id,
            cell_id,
            provider_id,
            registration_key,
            view,
            use,
            permitted_operations,
            validate_issuer,
        )
    return authority


def _require_source_admission_scope(
    state: _AuthorityState,
    *,
    operation: SourceAdmissionOperation,
    registration_key: str,
    effective_view_contract_ref: ArtifactRef,
    use_contract_ref: ArtifactRef,
) -> None:
    if (
        operation not in state.permitted_operations
        or registration_key != state.registration_key
        or artifact_ref_identity_key(effective_view_contract_ref)
        != artifact_ref_identity_key(state.effective_view_contract_ref)
        or artifact_ref_identity_key(use_contract_ref)
        != artifact_ref_identity_key(state.use_contract_ref)
    ):
        raise ValueError("source_admission_operation_scope_not_established")


def _capture_registered_materialization(
    *,
    authority: SourceAdmissionAuthority,
    materialization: RegisteredMaterialization,
    validate_capture: Callable[[], None],
) -> VerifiedRegisteredMaterialization:
    """Private real-producer seam; supplied ref lists cannot mint its witness.

    C106 must call this only inside the actual appointed producer closure after
    exact live registry, applied-view and output/occurrence reconciliation. The
    kernel independently resolves all typed owner refs/edges again at intake.
    """
    state = _require_source_admission_authority(authority)
    frozen = RegisteredMaterialization.model_validate_json(
        materialization.model_dump_json(), strict=True
    )
    registration = frozen.registration
    _require_source_admission_scope(
        state,
        operation="admit",
        registration_key=registration.registration_key,
        effective_view_contract_ref=registration.effective_view_contract_ref,
        use_contract_ref=registration.use_contract_ref,
    )
    if (
        registration.tenant_id,
        registration.cell_id,
        registration.provider_id,
        registration.issuer_key,
    ) != (
        state.tenant_id,
        state.cell_id,
        state.provider_id,
        state.issuer_key,
    ) or validate_capture() is not None:
        raise ValueError("source_admission_producer_relation_not_established")
    proof = object.__new__(VerifiedRegisteredMaterialization)
    with _REGISTRY_LOCK:
        _MATERIALIZATIONS[proof] = _MaterializationState(
            authority, frozen.model_dump_json(), validate_capture
        )
    return proof


def _require_registered_materialization(
    proof: object,
) -> tuple[_AuthorityState, RegisteredMaterialization]:
    if type(proof) is not VerifiedRegisteredMaterialization:
        raise ValueError("source_admission_producer_relation_not_established")
    with _REGISTRY_LOCK:
        state = _MATERIALIZATIONS.get(proof)
    if state is None:
        raise ValueError("source_admission_producer_relation_not_established")
    authority = _require_source_admission_authority(state.authority)
    if state.validate_capture() is not None:
        raise ValueError("source_admission_producer_relation_not_established")
    return authority, RegisteredMaterialization.model_validate_json(
        state.materialization_json, strict=True
    )
