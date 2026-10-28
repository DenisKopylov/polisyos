"""Neutral trusted-composition port for registered materialization admission.

Private minting operations belong only to the appointed Runtime factory and the
actual canonical registered producer. An HTTP field, manifest, or authorial DTO
cannot populate this port. This module does not implement that producer bridge.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import TYPE_CHECKING, Literal, Protocol, get_args
from weakref import WeakKeyDictionary

from polisyos.core.artifacts.manifest import ArtifactRef, artifact_ref_identity_key
from polisyos.core.contracts.decision_validity import (
    RegisteredMaterialization,
    SourceAdmissionCarrier,
    SourceRegistrationReceipt,
)

if TYPE_CHECKING:
    from collections.abc import Callable


SourceAdmissionOperation = Literal[
    "genesis", "admit", "withdraw", "readmit", "supersede", "read_event"
]


class SourceAdmissionReadBudget(Protocol):
    """Runtime-owned accounting for actual selected CAS transfer bytes.

    This resource port grants no source authority. It excludes owner-state,
    database, external-source and operating-system I/O.
    """

    max_manifest_bytes: int

    @property
    def remaining_bytes(self) -> int:
        """Return the remaining shared selected-store allowance."""
        ...

    @property
    def source_usage_established(self) -> bool:
        """Return whether every preceding selected-store transfer was measured."""
        ...

    def account_execution_source_bytes(self, observed_bytes: int) -> None:
        """Charge exact actual bytes from a successful owner read."""
        ...

    def account_refused_execution_source_bytes(self, observed_bytes: int) -> None:
        """Charge exact actual bytes transferred before a refusal."""
        ...

    def mark_source_usage_unestablished(self) -> None:
        """Invalidate an exact aggregate after an unmeasurable transfer."""
        ...


@dataclass(frozen=True, slots=True)
class SourceIssuerScope:
    """Verified coordinates returned by an owner-selected live issuer verifier.

    This value is never authority by itself; C105 accepts it only as the result
    of the exact verifier pinned into the installed validity owner.
    """

    issuer_key: str
    tenant_id: str
    cell_id: str
    provider_id: str
    registration_key: str
    effective_view_contract_ref: ArtifactRef
    use_contract_ref: ArtifactRef
    permitted_operations: frozenset[SourceAdmissionOperation]


@dataclass(frozen=True, slots=True)
class SourceIssuerCall:
    """The actual source operation the owner is about to execute."""

    operation: Literal["read_event", "current_head", "acquire", "admit", "genesis", "withdraw"]
    event_id: str
    expected_predecessor: str | None = None
    registration: SourceRegistrationReceipt | None = None
    materialization: RegisteredMaterialization | None = None
    target: SourceAdmissionCarrier | None = None


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
    validate_issuer: Callable[[], None] | None
    owner: object | None = None
    verifier: object | None = None
    witness: object | None = None
    initial_call: SourceIssuerCall | None = None


@dataclass(frozen=True, slots=True)
class _MaterializationState:
    authority: SourceAdmissionAuthority
    materialization_json: str
    validate_capture: Callable[[], None]
    producer_witness: object | None


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


def _verified_issuer_scope(
    owner: object, verifier: object, witness: object, call: SourceIssuerCall
) -> SourceIssuerScope:
    # Only an independently installed C105 owner pin chooses the verifier.
    # Supplying a callback or a scope DTO in a request cannot select it.
    require_pin = getattr(owner, "_require_registered_sql_issuer_verifier", None)
    if not callable(require_pin):
        raise ValueError("source_admission_issuer_not_pinned")
    require_pin(verifier)
    verify = getattr(verifier, "verify", None)
    if not callable(verify):
        raise ValueError("source_admission_issuer_not_pinned")
    scope = verify(witness, call)
    if type(scope) is not SourceIssuerScope:
        raise ValueError("source_admission_issuer_scope_not_established")
    return scope


def _state_scope(state: _AuthorityState) -> SourceIssuerScope:
    return SourceIssuerScope(
        issuer_key=state.issuer_key,
        tenant_id=state.tenant_id,
        cell_id=state.cell_id,
        provider_id=state.provider_id,
        registration_key=state.registration_key,
        effective_view_contract_ref=state.effective_view_contract_ref,
        use_contract_ref=state.use_contract_ref,
        permitted_operations=state.permitted_operations,
    )


def _require_source_admission_authority(authority: object) -> _AuthorityState:
    if type(authority) is not SourceAdmissionAuthority:
        raise ValueError("source_admission_authority_not_established")
    with _REGISTRY_LOCK:
        state = _AUTHORITIES.get(authority)
    if state is None:
        raise ValueError("source_admission_authority_not_established")
    if state.owner is None:
        if state.validate_issuer is None or state.validate_issuer() is not None:
            raise ValueError("source_admission_factory_validation_not_established")
    elif state.initial_call is None or _verified_issuer_scope(
        state.owner, state.verifier, state.witness, state.initial_call
    ) != _state_scope(state):
        raise ValueError("source_admission_factory_validation_not_established")
    return state


def _require_source_admission_call(
    authority: object, *, owner: object, call: SourceIssuerCall
) -> _AuthorityState:
    """Reverify the real operation with the same owner pin at its transaction."""
    state = _require_source_admission_authority(authority)
    if owner is not state.owner or type(call) is not SourceIssuerCall:
        raise ValueError("source_admission_owner_not_established")
    if _verified_issuer_scope(owner, state.verifier, state.witness, call) != _state_scope(state):
        raise ValueError("source_admission_issuer_scope_changed")
    if (
        call.operation in get_args(SourceAdmissionOperation)
        and call.operation not in state.permitted_operations
    ):
        raise ValueError("source_admission_operation_scope_not_established")
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


def _bind_runtime_source_admission_authority(
    *, owner: object, verifier: object, witness: object, initial_call: SourceIssuerCall
) -> SourceAdmissionAuthority:
    """Bind a live request only through the exact issuer selected by this owner.

    The installation of the owner pin is a separate Runtime factory duty; this
    function cannot establish it, and a caller-supplied validator is not used.
    """
    if type(initial_call) is not SourceIssuerCall or initial_call.operation not in {
        "acquire",
        "genesis",
        "withdraw",
    }:
        raise ValueError("source_admission_initial_call_invalid")
    scope = _verified_issuer_scope(owner, verifier, witness, initial_call)
    if any(
        not isinstance(v, str) or not v.strip()
        for v in (
            scope.issuer_key,
            scope.tenant_id,
            scope.cell_id,
            scope.provider_id,
            scope.registration_key,
        )
    ) or scope.permitted_operations not in (
        frozenset({"admit", "read_event"}),
        frozenset({"genesis", "read_event"}),
        frozenset({"withdraw", "read_event"}),
    ):
        raise ValueError("source_admission_issuer_scope_not_established")
    view = ArtifactRef.model_validate_json(
        scope.effective_view_contract_ref.model_dump_json(), strict=True
    )
    use = ArtifactRef.model_validate_json(scope.use_contract_ref.model_dump_json(), strict=True)
    if view.manifest_profile_sha256 is None or use.manifest_profile_sha256 is None:
        raise ValueError("source_admission_selected_profile_required")
    authority = object.__new__(SourceAdmissionAuthority)
    with _REGISTRY_LOCK:
        _AUTHORITIES[authority] = _AuthorityState(
            scope.issuer_key,
            scope.tenant_id,
            scope.cell_id,
            scope.provider_id,
            scope.registration_key,
            view,
            use,
            scope.permitted_operations,
            None,
            owner,
            verifier,
            witness,
            initial_call,
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
    producer_witness: object | None = None,
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
            authority, frozen.model_dump_json(), validate_capture, producer_witness
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


def _read_registered_materialization_candidate(
    proof: object,
) -> tuple[SourceAdmissionAuthority, RegisteredMaterialization, object | None]:
    """Expose candidate state to an owner verifier without running callbacks."""
    if type(proof) is not VerifiedRegisteredMaterialization:
        raise ValueError("source_admission_producer_relation_not_established")
    with _REGISTRY_LOCK:
        state = _MATERIALIZATIONS.get(proof)
    if state is None:
        raise ValueError("source_admission_producer_relation_not_established")
    return (
        state.authority,
        RegisteredMaterialization.model_validate_json(state.materialization_json, strict=True),
        state.producer_witness,
    )
