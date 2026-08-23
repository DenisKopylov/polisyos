"""Foundry-owned, negative-only dependency authority for N8 reconstruction.

The current production graph establishes the canonical tracked source and then
fails closed at the missing runtime-subtree cutoff.  It has no dormant positive
arm, performs no environment sync, and writes no evidence receipt.
"""

from __future__ import annotations

import ast
import ctypes
import inspect
import os
import shutil
import stat
import subprocess
import sys
import tomllib
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass, fields, is_dataclass
from enum import StrEnum
from functools import wraps
from pathlib import Path
from threading import RLock
from types import MappingProxyType, UnionType
from typing import (
    Annotated,
    Any,
    Generic,
    Literal,
    ParamSpec,
    Protocol,
    TypeVar,
    Union,
    cast,
    get_args,
    get_origin,
    get_type_hints,
)
from weakref import WeakKeyDictionary, finalize

from pydantic import Field, TypeAdapter, model_validator

from polisyos.core import artifacts as core_artifacts
from polisyos.foundry.methods.catalog import dependency_evidence as evidence_module
from polisyos.foundry.methods.catalog import dependency_profile as profile_module
from polisyos.foundry.methods.catalog.dependency_evidence import (
    AbsoluteRequestPath,
    AuthorityFailureCode,
    AuthorityPredicateFailure,
    AuthorityPredicateId,
    AuthorityPredicateSpec,
    AuthorityScalarRole,
    BidirectionalAuthorityPredicateSpec,
    BidirectionalUnestablishedAuthorityPredicate,
    DecodedDigestDomainRegistry,
    DigestDomain,
    DigestPredicateMismatch,
    DigestPreimageKind,
    DigestProducerId,
    DigestVerifierId,
    DomainDigest,
    ExactSignedArtifactEvidenceStatement,
    ExternalAuthorityKind,
    FoundryAuthorityModel,
    FoundryDependencyAuthorityCapsuleStatement,
    FoundryRecordRef,
    FoundryTrustBootstrapSnapshot,
    GitCommitId,
    GitCommitRelation,
    GitTreeId,
    LauncherProfileSpec,
    MissingEvidenceDomainsRequirement,
    MissingPredicateEvidence,
    PersistedFoundryDependencyAuthorityCapsule,
    PersistedPythonRuntimeInstallation,
    PersistedSignedFoundryRecordBinding,
    PersistedSignedRecordBindingIndex,
    PersistedTrustResolutionReceipt,
    ProductionDataCustodyStatement,
    ProductionDataInputAppointmentStatement,
    ProductionDataManifestInput,
    ProductionDataMountResolutionStatement,
    ProductionDataRootAccessChallenge,
    ProductionDataTrustPolicyStatement,
    PythonRuntimeAdmission,
    RejectedAuthorityPredicate,
    RootAccessAttestationStatement,
    SignedFoundryRecordBindingStatement,
    SignedRecordVerificationBasis,
    ToolchainArtifactAdmission,
    TrustPublicKey,
    TrustRole,
    UnestablishedAuthorityPredicate,
    canonical_json_bytes,
    domain_digest,
    load_digest_domain_registry,
    record_ref,
    sha256_wire,
)
from polisyos.foundry.methods.catalog.dependency_profile import (
    MethodCatalogProfileAdmission,
    declaration_ref,
    load_dependency_profile_registry,
    reconcile_bound_installed_environment,
    resolve_dependency_profile,
)

_PRODUCT_ROOT = Path(__file__).resolve().parents[5]
_GIT_ROOT = _PRODUCT_ROOT.parent
_PRODUCTION_QUALITY_ROOT = _PRODUCT_ROOT / "architecture" / "production_quality"
_PROFILE_REGISTRY_PATH = _PRODUCTION_QUALITY_ROOT / "method_catalog_dependency_profiles.toml"
_AUTHORITY_REGISTRY_PATH = _PRODUCTION_QUALITY_ROOT / "method_catalog_dependency_authority.toml"
_DIGEST_REGISTRY_PATH = (
    _PRODUCTION_QUALITY_ROOT / "method_catalog_dependency_digest_domains.toml"
)
_AUTHORITY_SOURCE_PATHS = (
    "policy-engine/architecture/production_quality/method_catalog_dependency_authority.toml",
    "policy-engine/architecture/production_quality/method_catalog_dependency_digest_domains.toml",
    "policy-engine/architecture/production_quality/method_catalog_dependency_profiles.toml",
    "policy-engine/pyproject.toml",
    "policy-engine/uv.lock",
    "policy-engine/src/polisyos/foundry/__init__.py",
    "policy-engine/src/polisyos/foundry/methods/catalog/__init__.py",
    "policy-engine/src/polisyos/foundry/methods/catalog/dependency_authority.py",
    "policy-engine/src/polisyos/foundry/methods/catalog/dependency_evidence.py",
    "policy-engine/src/polisyos/foundry/methods/catalog/dependency_profile.py",
    "policy-engine/src/polisyos/foundry/methods/catalog/snapshot.py",
    "policy-engine/tools/devx/foundry/sync_dependency_profile.py",
)


class OwnerCapabilityKind(StrEnum):
    CANONICAL_SOURCE = "canonical-source"
    RUNTIME_INSTALLATION = "runtime-installation"
    VERIFIED_RUNTIME = "verified-runtime"
    TRUST_BOOTSTRAP = "trust-bootstrap"
    RESOLVED_TRUST = "resolved-trust"
    PRODUCTION_APPOINTMENT = "production-appointment"
    PRODUCTION_MOUNT = "production-mount"
    ROOT_ACCESS = "root-access"
    SIGNED_RECORD = "signed-record"
    SIGNED_GRAPH = "signed-graph"
    RESOLVED_COMPONENTS = "resolved-components"


C = TypeVar("C")
P = TypeVar("P")
R = TypeVar("R")
PS = ParamSpec("PS")


class OwnerCapabilityFaultDisposition(StrEnum):
    REJECTED = "rejected"
    NOT_ESTABLISHED = "not_established"


class OwnerCapabilityFaultCode(StrEnum):
    WRONG_TOKEN_TYPE = "wrong_token_type"
    UNMINTED_TOKEN = "unminted_token"
    WRONG_CAPABILITY_FAMILY = "wrong_capability_family"
    RESOURCE_ALREADY_OWNED = "resource_already_owned"
    RESOURCE_IN_USE = "resource_in_use"
    WRONG_RECORD_DOMAIN = "wrong_record_domain"
    INVALID_NESTED_CAPABILITY = "invalid_nested_capability"
    FORKED_PROCESS = "forked_process"
    CHILD_RESOURCE_DISPOSAL_FAILED = "child_resource_disposal_failed"


class OwnerCapabilityFault(RuntimeError):
    def __init__(
        self,
        *,
        code: OwnerCapabilityFaultCode,
        disposition: OwnerCapabilityFaultDisposition,
        capability_kind: OwnerCapabilityKind | None,
        payload_path: tuple[str, ...] = (),
        expected_record_domain: DigestDomain | None = None,
        actual_record_domain: DigestDomain | None = None,
    ) -> None:
        super().__init__(code.value)
        self.code = code
        self.disposition = disposition
        self.capability_kind = capability_kind
        self.payload_path = payload_path
        self.expected_record_domain = expected_record_domain
        self.actual_record_domain = actual_record_domain


_OwnerResourceKey = tuple[Literal["posix_open_generation"], int, int]


class _OwnerChildDisposable(Protocol):
    def require_current_process_descriptor(self) -> int: ...

    def owner_resource_lease_key(self) -> _OwnerResourceKey: ...

    def close_owner_resource(self) -> None: ...


@dataclass(frozen=True, slots=True)
class _OwnerResourceClaim:
    lease: object
    resources: tuple[tuple[_OwnerResourceKey, _OwnerChildDisposable], ...]


class _ClaimOwnerResources(Protocol):
    def __call__(
        self,
        *,
        capability_kind: OwnerCapabilityKind,
        resources: tuple[_OwnerChildDisposable, ...],
    ) -> _OwnerResourceClaim: ...


class _ReleaseOwnerResources(Protocol):
    def __call__(self, claim: _OwnerResourceClaim, /) -> None: ...


class _RegisterOwnerForkParticipant(Protocol):
    def __call__(self, participant: Callable[[bool], None], /) -> None: ...


class _OwnerLifecycleSection(Protocol):
    def __call__(self) -> AbstractContextManager[None]: ...


@dataclass(frozen=True, slots=True)
class _OwnerPayloadLeafSpec:
    field_path: tuple[str, ...]
    exact_concrete_type: type[object]


class _OwnerNestedCardinality(StrEnum):
    SINGLE = "single"
    MANY = "many"


@dataclass(frozen=True, slots=True)
class _OwnerNestedTokenSpec:
    payload_path: tuple[str, ...]
    cardinality: _OwnerNestedCardinality
    token_path: tuple[str, ...]
    expected_domain_path: tuple[str, ...] | None
    nested_kind: OwnerCapabilityKind


@dataclass(frozen=True, slots=True)
class _OwnerPayloadSpec(Generic[C, P]):
    """Closed token/payload relation; never accepted from a request."""

    kind: OwnerCapabilityKind
    token_type: type[C]
    payload_type: type[P]
    exact_concrete_leaves: tuple[_OwnerPayloadLeafSpec, ...]
    dynamic_record_domain_path: tuple[str, ...] | None
    dynamic_record_ref_domain_path: tuple[str, ...] | None
    child_resource_paths: tuple[tuple[str, ...], ...]
    nested_tokens: tuple[_OwnerNestedTokenSpec, ...]


@dataclass(frozen=True, slots=True)
class _OwnerCapabilityEntry(Generic[C, P]):
    spec: _OwnerPayloadSpec[C, P]
    creator_pid: int
    process_instance: object
    payload: P
    resource_finalizer: finalize


class _OwnerMint(Protocol):
    def __call__(self, spec: _OwnerPayloadSpec[C, P], payload: P, /) -> C: ...


class _OwnerUnwrap(Protocol):
    def __call__(
        self,
        value: object,
        spec: _OwnerPayloadSpec[C, P],
        /,
        *,
        expected_record_domain: DigestDomain | None = None,
    ) -> AbstractContextManager[P]: ...


class _OwnerRelease(Protocol):
    def __call__(self, value: object, spec: _OwnerPayloadSpec[C, P], /) -> None: ...


class OwnerEntrypointFailureAdapterId(StrEnum):
    AUTHORITY_PREDICATE = "authority_predicate"
    MANIFEST_INPUT = "manifest_input"
    GIT_RELATION = "git_relation"
    METHOD_CATALOG_RESULT = "method_catalog_result"


class OwnerEntrypointTargetKind(StrEnum):
    METHOD = "method"
    MODULE_FUNCTION = "module_function"


@dataclass(frozen=True, slots=True)
class OwnerMethodTarget:
    target_kind: Literal[OwnerEntrypointTargetKind.METHOD]
    concrete_owner_type: type[object]
    protocol_type: type[object]
    method_name: str


@dataclass(frozen=True, slots=True)
class OwnerFunctionTarget:
    target_kind: Literal[OwnerEntrypointTargetKind.MODULE_FUNCTION]
    module_qualname: str
    function_name: str


OwnerEntrypointTarget = OwnerMethodTarget | OwnerFunctionTarget


@dataclass(frozen=True, slots=True)
class OwnerFaultPolicy:
    capability_parameter_name: str
    capability_kind: OwnerCapabilityKind
    predicate_id: AuthorityPredicateId
    rejected_code: AuthorityFailureCode
    not_established_code: AuthorityFailureCode
    evidence_argument_names: tuple[str, ...]
    missing_evidence_domains: tuple[DigestDomain, ...]


@dataclass(frozen=True, slots=True)
class OwnerEntrypointSpec:
    target: OwnerEntrypointTarget
    fault_policies: tuple[OwnerFaultPolicy, ...]
    failure_adapter_id: OwnerEntrypointFailureAdapterId


@dataclass(frozen=True, slots=True)
class OwnerBorrowTerminalEdge:
    evaluation_kind: Literal[
        "call",
        "attribute",
        "iteration",
        "context",
        "comparison",
        "truth",
        "hash",
        "index",
        "format",
        "repr",
        "binary",
        "unary",
    ]
    callable_qualified_name: str | None
    operand_exact_types: tuple[type[object], ...]
    implicit_method_names: tuple[str, ...]
    disposition: Literal["traversed", "no_user_dispatch"]
    traversed_qualified_functions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AstOccurrenceStep:
    field_name: str
    child_index: int | None


@dataclass(frozen=True, slots=True)
class AstOccurrenceId:
    ancestry: tuple[AstOccurrenceStep, ...]


@dataclass(frozen=True, slots=True)
class OwnerBorrowEvaluationNode:
    ast_node_type: type[ast.AST]
    occurrence_id: AstOccurrenceId
    source_span: tuple[int, int, int, int] | None
    disposition: Literal["lowered", "syntactic_container"]
    terminal_edges: tuple[OwnerBorrowTerminalEdge, ...]


@dataclass(frozen=True, slots=True)
class OwnerBorrowReachability:
    entrypoint: OwnerEntrypointTarget
    borrowed_name: str
    reachable_qualified_functions: tuple[str, ...]
    evaluated_nodes: tuple[OwnerBorrowEvaluationNode, ...]


class _OwnerBoundaryBase:
    """Marker for class-level guards installed from the independent census."""


_OWNER_TOKEN_CLASS_MARKER = object()


def _fieldless_owner_token(cls: type[C]) -> type[C]:
    """Create one fieldless token type; this decorator mints no authority."""

    if cls.__bases__ != (object,) or tuple(getattr(cls, "__annotations__", ())):
        raise TypeError("owner capability token classes must be fieldless")
    token_type = dataclass(
        frozen=True,
        init=False,
        slots=True,
        weakref_slot=True,
        eq=False,
    )(cls)
    token_type.__owner_token_class_marker__ = _OWNER_TOKEN_CLASS_MARKER
    return token_type


def _validate_fieldless_owner_token_type(token_type: type[object]) -> None:
    """Check behavior, not only the decorator marker."""

    parameters = getattr(token_type, "__dataclass_params__", None)
    if (
        vars(token_type).get("__owner_token_class_marker__")
        is not _OWNER_TOKEN_CLASS_MARKER
        or not is_dataclass(token_type)
        or token_type.__mro__ != (token_type, object)
        or fields(token_type) != ()
        or parameters is None
        or parameters.init
        or parameters.eq
        or not parameters.frozen
        or tuple(getattr(token_type, "__slots__", ())) != ("__weakref__",)
        or "__dict__" in vars(token_type)
        or token_type.__hash__ is not object.__hash__
        or token_type.__eq__ is not object.__eq__
    ):
        raise TypeError(
            "owner capability token class is not fieldless/frozen/identity-only"
        )
    probe = object.__new__(token_type)
    weak_probe: WeakKeyDictionary[object, bool] = WeakKeyDictionary()
    weak_probe[probe] = True
    try:
        probe.state = object()
    except (AttributeError, TypeError):
        pass
    else:
        raise TypeError("owner capability token admits instance state")


def _build_owner_capability_kernel(
    specs: tuple[_OwnerPayloadSpec[object, object], ...],
    *,
    claim_owner_resources: _ClaimOwnerResources,
    release_owner_resources: _ReleaseOwnerResources,
    register_fork_participant: _RegisterOwnerForkParticipant,
    lifecycle_section: _OwnerLifecycleSection,
) -> tuple[_OwnerMint, _OwnerUnwrap, _OwnerRelease]:
    """Build a sealed mint/borrow/release kernel for all owner capabilities."""

    def exact_path(value: object, *, allow_empty: bool = False) -> bool:
        return (
            type(value) is tuple
            and (allow_empty or bool(value))
            and all(type(member) is str and member for member in value)
        )

    if type(specs) is not tuple or len(specs) != len(OwnerCapabilityKind):
        raise TypeError("owner payload specs must exactly cover every capability kind")
    for spec in specs:
        if (
            type(spec) is not _OwnerPayloadSpec
            or type(spec.kind) is not OwnerCapabilityKind
            or not isinstance(spec.token_type, type)
            or not isinstance(spec.payload_type, type)
            or type(spec.exact_concrete_leaves) is not tuple
            or type(spec.child_resource_paths) is not tuple
            or type(spec.nested_tokens) is not tuple
        ):
            raise TypeError("owner payload spec has an invalid type/kind/token relation")
        _validate_fieldless_owner_token_type(spec.token_type)
        leaf_paths: list[tuple[str, ...]] = []
        for leaf in spec.exact_concrete_leaves:
            if (
                type(leaf) is not _OwnerPayloadLeafSpec
                or not exact_path(leaf.field_path)
                or not isinstance(leaf.exact_concrete_type, type)
            ):
                raise TypeError("owner payload leaf spec is not exact")
            leaf_paths.append(leaf.field_path)
        if len(leaf_paths) != len(set(leaf_paths)):
            raise TypeError("owner payload leaf paths must be unique")
        for child_path in spec.child_resource_paths:
            if not exact_path(child_path) or child_path not in leaf_paths:
                raise TypeError("child resource must name an exact registered leaf")
        if len(spec.child_resource_paths) != len(set(spec.child_resource_paths)):
            raise TypeError("child resource paths must be unique")
        if (spec.dynamic_record_domain_path is None) != (
            spec.dynamic_record_ref_domain_path is None
        ):
            raise TypeError("dynamic record and ref domains must be paired")
        for dynamic_path in (
            spec.dynamic_record_domain_path,
            spec.dynamic_record_ref_domain_path,
        ):
            if dynamic_path is not None and not exact_path(dynamic_path):
                raise TypeError("dynamic record domain paths must be exact")
        nested_paths: list[tuple[str, ...]] = []
        for nested in spec.nested_tokens:
            if (
                type(nested) is not _OwnerNestedTokenSpec
                or type(nested.cardinality) is not _OwnerNestedCardinality
                or type(nested.nested_kind) is not OwnerCapabilityKind
                or not exact_path(nested.payload_path)
                or not exact_path(nested.token_path, allow_empty=True)
                or (
                    nested.expected_domain_path is not None
                    and not exact_path(nested.expected_domain_path)
                )
            ):
                raise TypeError("nested owner-token spec is not exact")
            nested_paths.append(nested.payload_path)
        if len(nested_paths) != len(set(nested_paths)):
            raise TypeError("nested owner-token paths must be unique")

    spec_by_token = MappingProxyType({spec.token_type: spec for spec in specs})
    spec_by_kind = MappingProxyType({spec.kind: spec for spec in specs})
    if not (
        len(spec_by_token)
        == len(spec_by_kind)
        == len(specs)
        == len(OwnerCapabilityKind)
        and set(spec_by_kind) == set(OwnerCapabilityKind)
    ):
        raise TypeError("owner payload specs must be a kind-complete bijection")
    for spec in specs:
        if spec_by_token.get(spec.token_type) is not spec:
            raise TypeError("owner token-to-spec relation is not bijective")
        validate_owner_payload_spec_annotation_graph(
            spec=spec,
            spec_by_kind=cast(
                "Mapping[OwnerCapabilityKind, _OwnerPayloadSpec[object, object]]",
                spec_by_kind,
            ),
        )

    instances: WeakKeyDictionary[
        object, _OwnerCapabilityEntry[object, object]
    ] = WeakKeyDictionary()
    released_tokens: WeakKeyDictionary[
        object, _OwnerPayloadSpec[object, object]
    ] = WeakKeyDictionary()
    forked_tokens: WeakKeyDictionary[
        object, _OwnerPayloadSpec[object, object]
    ] = WeakKeyDictionary()
    active_borrows: WeakKeyDictionary[object, int] = WeakKeyDictionary()
    process_instance = object()
    child_disposal_failed = False

    def resolve_registered_spec(
        candidate: object,
    ) -> _OwnerPayloadSpec[object, object]:
        capability_kind = (
            candidate.kind
            if type(candidate) is _OwnerPayloadSpec
            and type(candidate.kind) is OwnerCapabilityKind
            else None
        )
        if type(candidate) is not _OwnerPayloadSpec or capability_kind is None:
            raise OwnerCapabilityFault(
                code=OwnerCapabilityFaultCode.WRONG_CAPABILITY_FAMILY,
                disposition=OwnerCapabilityFaultDisposition.REJECTED,
                capability_kind=capability_kind,
            )
        registered = spec_by_kind.get(capability_kind)
        if registered is not candidate:
            raise OwnerCapabilityFault(
                code=OwnerCapabilityFaultCode.WRONG_CAPABILITY_FAMILY,
                disposition=OwnerCapabilityFaultDisposition.REJECTED,
                capability_kind=capability_kind,
            )
        return registered

    def follow(value: object, field_path: tuple[str, ...]) -> object:
        for name in field_path:
            value = getattr(value, name)
        return value

    def validate_payload(
        spec: _OwnerPayloadSpec[object, object],
        payload: object,
        *,
        expected_record_domain: DigestDomain | None,
        bind_dynamic_domain_to_payload: bool = False,
    ) -> None:
        if type(payload) is not spec.payload_type:
            raise OwnerCapabilityFault(
                code=OwnerCapabilityFaultCode.WRONG_CAPABILITY_FAMILY,
                disposition=OwnerCapabilityFaultDisposition.REJECTED,
                capability_kind=spec.kind,
            )
        validate_owner_payload_annotation_graph(payload, spec_by_token=spec_by_token)
        for leaf in spec.exact_concrete_leaves:
            if type(follow(payload, leaf.field_path)) is not leaf.exact_concrete_type:
                raise OwnerCapabilityFault(
                    code=OwnerCapabilityFaultCode.WRONG_CAPABILITY_FAMILY,
                    disposition=OwnerCapabilityFaultDisposition.REJECTED,
                    capability_kind=spec.kind,
                    payload_path=leaf.field_path,
                )
        if spec.dynamic_record_domain_path is None:
            return
        actual = follow(payload, spec.dynamic_record_domain_path)
        ref_path = cast("tuple[str, ...]", spec.dynamic_record_ref_domain_path)
        bound_ref_domain = follow(payload, ref_path)
        required = actual if bind_dynamic_domain_to_payload else expected_record_domain
        if required is None or actual is not required or bound_ref_domain is not required:
            raise OwnerCapabilityFault(
                code=OwnerCapabilityFaultCode.WRONG_RECORD_DOMAIN,
                disposition=OwnerCapabilityFaultDisposition.REJECTED,
                capability_kind=spec.kind,
                payload_path=spec.dynamic_record_domain_path,
                expected_record_domain=required,
                actual_record_domain=cast("DigestDomain", actual),
            )

    def unwrap_impl(
        value: object,
        spec: _OwnerPayloadSpec[C, P],
        /,
        *,
        expected_record_domain: DigestDomain | None,
        seen_token_ids: set[int],
        payload_path: tuple[str, ...] = (),
    ) -> P:
        registered = cast("_OwnerPayloadSpec[C, P]", resolve_registered_spec(spec))
        if type(value) is not registered.token_type:
            raise OwnerCapabilityFault(
                code=OwnerCapabilityFaultCode.WRONG_TOKEN_TYPE,
                disposition=OwnerCapabilityFaultDisposition.REJECTED,
                capability_kind=registered.kind,
                payload_path=payload_path,
            )
        if child_disposal_failed:
            raise OwnerCapabilityFault(
                code=OwnerCapabilityFaultCode.CHILD_RESOURCE_DISPOSAL_FAILED,
                disposition=OwnerCapabilityFaultDisposition.NOT_ESTABLISHED,
                capability_kind=registered.kind,
                payload_path=payload_path,
            )
        if id(value) in seen_token_ids:
            raise OwnerCapabilityFault(
                code=OwnerCapabilityFaultCode.INVALID_NESTED_CAPABILITY,
                disposition=OwnerCapabilityFaultDisposition.REJECTED,
                capability_kind=registered.kind,
                payload_path=payload_path,
            )
        seen_token_ids.add(id(value))
        with lifecycle_section():
            forked = forked_tokens.get(value)
            entry = instances.get(value)
        if forked is registered:
            raise OwnerCapabilityFault(
                code=OwnerCapabilityFaultCode.FORKED_PROCESS,
                disposition=OwnerCapabilityFaultDisposition.NOT_ESTABLISHED,
                capability_kind=registered.kind,
                payload_path=payload_path,
            )
        if entry is None:
            raise OwnerCapabilityFault(
                code=OwnerCapabilityFaultCode.UNMINTED_TOKEN,
                disposition=OwnerCapabilityFaultDisposition.REJECTED,
                capability_kind=registered.kind,
                payload_path=payload_path,
            )
        if entry.spec is not registered:
            raise OwnerCapabilityFault(
                code=OwnerCapabilityFaultCode.WRONG_CAPABILITY_FAMILY,
                disposition=OwnerCapabilityFaultDisposition.REJECTED,
                capability_kind=registered.kind,
                payload_path=payload_path,
            )
        if entry.creator_pid != os.getpid() or entry.process_instance is not process_instance:
            raise OwnerCapabilityFault(
                code=OwnerCapabilityFaultCode.FORKED_PROCESS,
                disposition=OwnerCapabilityFaultDisposition.NOT_ESTABLISHED,
                capability_kind=registered.kind,
                payload_path=payload_path,
            )
        validate_payload(
            cast("_OwnerPayloadSpec[object, object]", registered),
            entry.payload,
            expected_record_domain=expected_record_domain,
        )
        for nested in registered.nested_tokens:
            raw = follow(entry.payload, nested.payload_path)
            members = (
                cast("tuple[object, ...]", raw)
                if nested.cardinality is _OwnerNestedCardinality.MANY
                else (raw,)
            )
            nested_spec = spec_by_kind[nested.nested_kind]
            for member in members:
                token = follow(member, nested.token_path) if nested.token_path else member
                expected_domain = (
                    cast("DigestDomain", follow(member, nested.expected_domain_path))
                    if nested.expected_domain_path is not None
                    else None
                )
                unwrap_impl(
                    token,
                    nested_spec,
                    expected_record_domain=expected_domain,
                    seen_token_ids=seen_token_ids,
                    payload_path=nested.payload_path,
                )
        return cast("P", entry.payload)

    def unwrap(
        value: object,
        spec: _OwnerPayloadSpec[C, P],
        /,
        *,
        expected_record_domain: DigestDomain | None = None,
    ) -> AbstractContextManager[P]:
        @contextmanager
        def borrow() -> Iterator[P]:
            with lifecycle_section():
                payload = unwrap_impl(
                    value,
                    spec,
                    expected_record_domain=expected_record_domain,
                    seen_token_ids=set(),
                )
                active_borrows[value] = active_borrows.get(value, 0) + 1
                try:
                    yield payload
                finally:
                    remaining = active_borrows[value] - 1
                    if remaining:
                        active_borrows[value] = remaining
                    else:
                        active_borrows.pop(value, None)

        return borrow()

    def mint(spec: _OwnerPayloadSpec[C, P], payload: P, /) -> C:
        nonlocal child_disposal_failed
        registered = cast("_OwnerPayloadSpec[C, P]", resolve_registered_spec(spec))
        with lifecycle_section():
            if child_disposal_failed:
                raise OwnerCapabilityFault(
                    code=OwnerCapabilityFaultCode.CHILD_RESOURCE_DISPOSAL_FAILED,
                    disposition=OwnerCapabilityFaultDisposition.NOT_ESTABLISHED,
                    capability_kind=registered.kind,
                )
            if type(payload) is not registered.payload_type:
                raise OwnerCapabilityFault(
                    code=OwnerCapabilityFaultCode.WRONG_CAPABILITY_FAMILY,
                    disposition=OwnerCapabilityFaultDisposition.REJECTED,
                    capability_kind=registered.kind,
                )
            exact_types = {
                leaf.field_path: leaf.exact_concrete_type
                for leaf in registered.exact_concrete_leaves
            }
            resources: list[_OwnerChildDisposable] = []
            for child_path in registered.child_resource_paths:
                raw_resource = follow(payload, child_path)
                if type(raw_resource) is not exact_types[child_path]:
                    raise OwnerCapabilityFault(
                        code=OwnerCapabilityFaultCode.WRONG_CAPABILITY_FAMILY,
                        disposition=OwnerCapabilityFaultDisposition.REJECTED,
                        capability_kind=registered.kind,
                        payload_path=child_path,
                    )
                resources.append(cast("_OwnerChildDisposable", raw_resource))
            claim: _OwnerResourceClaim | None = None
            try:
                claim = claim_owner_resources(
                    capability_kind=registered.kind,
                    resources=tuple(resources),
                )
                validate_payload(
                    cast("_OwnerPayloadSpec[object, object]", registered),
                    payload,
                    expected_record_domain=None,
                    bind_dynamic_domain_to_payload=(
                        registered.dynamic_record_domain_path is not None
                    ),
                )
                for child_path, claimed_resource in zip(
                    registered.child_resource_paths,
                    resources,
                    strict=True,
                ):
                    if follow(payload, child_path) is not claimed_resource:
                        raise OwnerCapabilityFault(
                            code=OwnerCapabilityFaultCode.WRONG_CAPABILITY_FAMILY,
                            disposition=OwnerCapabilityFaultDisposition.REJECTED,
                            capability_kind=registered.kind,
                            payload_path=child_path,
                        )
                token = object.__new__(registered.token_type)
                resource_finalizer = finalize(
                    token,
                    release_owner_resources,
                    claim,
                )
                instances[token] = _OwnerCapabilityEntry(
                    spec=cast("_OwnerPayloadSpec[object, object]", registered),
                    creator_pid=os.getpid(),
                    process_instance=process_instance,
                    payload=payload,
                    resource_finalizer=resource_finalizer,
                )
                return cast("C", token)
            except BaseException:
                if claim is not None:
                    release_owner_resources(claim)
                raise

    def release(value: object, spec: _OwnerPayloadSpec[C, P], /) -> None:
        nonlocal child_disposal_failed
        registered = cast("_OwnerPayloadSpec[C, P]", resolve_registered_spec(spec))
        if type(value) is not registered.token_type:
            raise OwnerCapabilityFault(
                code=OwnerCapabilityFaultCode.WRONG_TOKEN_TYPE,
                disposition=OwnerCapabilityFaultDisposition.REJECTED,
                capability_kind=registered.kind,
            )
        with lifecycle_section():
            if forked_tokens.get(value) is registered:
                raise OwnerCapabilityFault(
                    code=OwnerCapabilityFaultCode.FORKED_PROCESS,
                    disposition=OwnerCapabilityFaultDisposition.NOT_ESTABLISHED,
                    capability_kind=registered.kind,
                )
            entry = instances.get(value)
            if entry is None:
                if released_tokens.get(value) is registered:
                    return
                raise OwnerCapabilityFault(
                    code=OwnerCapabilityFaultCode.UNMINTED_TOKEN,
                    disposition=OwnerCapabilityFaultDisposition.REJECTED,
                    capability_kind=registered.kind,
                )
            if active_borrows.get(value, 0):
                raise OwnerCapabilityFault(
                    code=OwnerCapabilityFaultCode.RESOURCE_IN_USE,
                    disposition=OwnerCapabilityFaultDisposition.NOT_ESTABLISHED,
                    capability_kind=registered.kind,
                )
            instances.pop(value, None)
            released_tokens[value] = cast(
                "_OwnerPayloadSpec[object, object]", registered
            )
            try:
                entry.resource_finalizer()
            except BaseException as error:
                child_disposal_failed = True
                raise OwnerCapabilityFault(
                    code=OwnerCapabilityFaultCode.CHILD_RESOURCE_DISPOSAL_FAILED,
                    disposition=OwnerCapabilityFaultDisposition.NOT_ESTABLISHED,
                    capability_kind=registered.kind,
                ) from error

    def after_fork_token_sweep(is_child: bool) -> None:
        nonlocal child_disposal_failed
        if not is_child:
            return
        for token, entry in tuple(instances.items()):
            entry.resource_finalizer.detach()
            instances.pop(token, None)
            forked_tokens[token] = entry.spec
        active_borrows.clear()
        child_disposal_failed = False

    register_fork_participant(after_fork_token_sweep)
    return mint, unwrap, release


def _guard_owner_entrypoint(
    function: Callable[PS, R],
    *,
    spec: OwnerEntrypointSpec,
    failure_factory: Callable[
        [OwnerCapabilityFault, inspect.BoundArguments, OwnerEntrypointSpec], R
    ],
) -> Callable[PS, R]:
    """Bind call context, return one exact typed failure and preserve signature."""

    call_signature = inspect.signature(function)

    @contextmanager
    def borrow_capabilities(
        bound: inspect.BoundArguments,
        policies: tuple[OwnerFaultPolicy, ...],
        index: int = 0,
    ) -> Iterator[None]:
        if index == len(policies):
            yield
            return
        policy = policies[index]
        owner_spec = next(
            candidate
            for candidate in _OWNER_CAPABILITY_SPECS
            if candidate.kind is policy.capability_kind
        )
        try:
            with (
                _unwrap_owner_capability(
                    bound.arguments[policy.capability_parameter_name],
                    owner_spec,
                ),
                borrow_capabilities(bound, policies, index + 1),
            ):
                yield
        except OwnerCapabilityFault as error:
            remaining_kinds = {
                candidate.capability_kind for candidate in policies[index:]
            }
            if error.capability_kind not in remaining_kinds:
                raise OwnerCapabilityFault(
                    code=error.code,
                    disposition=error.disposition,
                    capability_kind=policy.capability_kind,
                    payload_path=error.payload_path,
                    expected_record_domain=error.expected_record_domain,
                    actual_record_domain=error.actual_record_domain,
                ) from error
            raise

    @wraps(function)
    def guarded(*args: PS.args, **kwargs: PS.kwargs) -> R:
        bound = call_signature.bind(*args, **kwargs)
        try:
            with borrow_capabilities(bound, spec.fault_policies):
                return function(*args, **kwargs)
        except OwnerCapabilityFault as error:
            return failure_factory(error, bound, spec)

    return guarded


@dataclass(frozen=True, slots=True)
class _OpenedDescriptorIdentity:
    device_id: int
    inode: int
    mode_type: Literal["directory"]


class _OpenOwnerDirectory(Protocol):
    def __call__(
        self,
        *,
        directory: Path,
        owner_kind: OwnerCapabilityKind,
        handle_type: type[P],
    ) -> P: ...


class _RequireOwnerDescriptor(Protocol):
    def __call__(self, handle: object, /) -> int: ...


class _CloseOwnerDescriptor(Protocol):
    def __call__(self, handle: object, /) -> None: ...


class _OwnerDescriptorLeaseKey(Protocol):
    def __call__(self, handle: object, /) -> _OwnerResourceKey: ...


_require_owner_descriptor = cast("_RequireOwnerDescriptor", None)
_close_owner_descriptor = cast("_CloseOwnerDescriptor", None)
_owner_descriptor_lease_key = cast("_OwnerDescriptorLeaseKey", None)


@dataclass(slots=True)
class _DescriptorEntry:
    descriptor: int
    creator_pid: int
    generation: int
    identity: _OpenedDescriptorIdentity
    live: bool
    resource_finalizer: finalize


def _build_owner_resource_coordinator(
    *,
    specs: tuple[_OwnerPayloadSpec[object, object], ...],
) -> tuple[
    _OpenOwnerDirectory,
    _RequireOwnerDescriptor,
    _CloseOwnerDescriptor,
    _OwnerDescriptorLeaseKey,
    _ClaimOwnerResources,
    _ReleaseOwnerResources,
    _RegisterOwnerForkParticipant,
    _OwnerLifecycleSection,
    Callable[[], None],
    Callable[[], None],
    Callable[[], None],
]:
    """Coordinate descriptor generations, leases, finalizers and fork."""

    allowed_handle_types = {
        leaf.exact_concrete_type
        for spec in specs
        for leaf in spec.exact_concrete_leaves
        if leaf.field_path in spec.child_resource_paths
    }
    lock = RLock()
    entries: WeakKeyDictionary[object, _DescriptorEntry] = WeakKeyDictionary()
    leases: dict[_OwnerResourceKey, object] = {}
    participants: list[Callable[[bool], None]] = []
    next_generation = 0
    disposal_failed = False

    def identity_from_stat(result: os.stat_result) -> _OpenedDescriptorIdentity:
        if not stat.S_ISDIR(result.st_mode):
            raise OSError("owner resource is not a directory")
        return _OpenedDescriptorIdentity(
            device_id=result.st_dev,
            inode=result.st_ino,
            mode_type="directory",
        )

    def close_fd(descriptor: int) -> None:
        try:
            os.close(descriptor)
        except OSError:
            pass

    def register_fork_participant(participant: Callable[[bool], None], /) -> None:
        if not callable(participant):
            raise TypeError("fork participant must be callable")
        with lock:
            participants.append(participant)

    @contextmanager
    def lifecycle_section() -> Iterator[None]:
        with lock:
            yield

    def open_owner_directory(
        *,
        directory: Path,
        owner_kind: OwnerCapabilityKind,
        handle_type: type[P],
    ) -> P:
        nonlocal next_generation, disposal_failed
        if (
            not isinstance(directory, Path)
            or type(owner_kind) is not OwnerCapabilityKind
            or handle_type not in allowed_handle_types
        ):
            raise TypeError("owner directory request is outside the closed relation")
        flags = os.O_RDONLY | os.O_CLOEXEC
        flags |= getattr(os, "O_DIRECTORY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(directory, flags)
        try:
            observed = identity_from_stat(os.fstat(descriptor))
            with lock:
                if disposal_failed:
                    raise OwnerCapabilityFault(
                        code=OwnerCapabilityFaultCode.CHILD_RESOURCE_DISPOSAL_FAILED,
                        disposition=OwnerCapabilityFaultDisposition.NOT_ESTABLISHED,
                        capability_kind=owner_kind,
                    )
                next_generation += 1
                generation = next_generation
                handle = object.__new__(handle_type)
                handle.descriptor = descriptor
                handle.creator_pid = os.getpid()
                handle.owner_kind = owner_kind
                handle.open_generation = generation
                handle.opened_identity = observed
                resource_finalizer = finalize(handle, close_fd, descriptor)
                entries[handle] = _DescriptorEntry(
                    descriptor=descriptor,
                    creator_pid=os.getpid(),
                    generation=generation,
                    identity=observed,
                    live=True,
                    resource_finalizer=resource_finalizer,
                )
                return cast("P", handle)
        except BaseException:
            close_fd(descriptor)
            raise

    def require_owner_descriptor(handle: object, /) -> int:
        with lock:
            entry = entries.get(handle)
            if (
                entry is None
                or not entry.live
                or entry.creator_pid != os.getpid()
                or getattr(handle, "creator_pid", None) != os.getpid()
                or getattr(handle, "open_generation", None) != entry.generation
                or getattr(handle, "descriptor", None) != entry.descriptor
            ):
                raise OwnerCapabilityFault(
                    code=OwnerCapabilityFaultCode.FORKED_PROCESS,
                    disposition=OwnerCapabilityFaultDisposition.NOT_ESTABLISHED,
                    capability_kind=getattr(handle, "owner_kind", None),
                )
            try:
                observed = identity_from_stat(os.fstat(entry.descriptor))
            except OSError as error:
                raise OwnerCapabilityFault(
                    code=OwnerCapabilityFaultCode.FORKED_PROCESS,
                    disposition=OwnerCapabilityFaultDisposition.NOT_ESTABLISHED,
                    capability_kind=getattr(handle, "owner_kind", None),
                ) from error
            if observed != entry.identity:
                raise OwnerCapabilityFault(
                    code=OwnerCapabilityFaultCode.FORKED_PROCESS,
                    disposition=OwnerCapabilityFaultDisposition.NOT_ESTABLISHED,
                    capability_kind=getattr(handle, "owner_kind", None),
                )
            return entry.descriptor

    def owner_descriptor_lease_key(handle: object, /) -> _OwnerResourceKey:
        descriptor = require_owner_descriptor(handle)
        del descriptor
        entry = entries[handle]
        return ("posix_open_generation", entry.creator_pid, entry.generation)

    def close_owner_descriptor(handle: object, /) -> None:
        nonlocal disposal_failed
        with lock:
            entry = entries.get(handle)
            if entry is None or not entry.live:
                return
            entry.live = False
            entry.resource_finalizer.detach()
            try:
                os.close(entry.descriptor)
            except OSError:
                disposal_failed = True

    def claim_owner_resources(
        *,
        capability_kind: OwnerCapabilityKind,
        resources: tuple[_OwnerChildDisposable, ...],
    ) -> _OwnerResourceClaim:
        if type(resources) is not tuple:
            raise TypeError("owner resources must be an exact tuple")
        with lock:
            rows: list[tuple[_OwnerResourceKey, _OwnerChildDisposable]] = []
            keys: set[_OwnerResourceKey] = set()
            for resource in resources:
                key = resource.owner_resource_lease_key()
                if key in keys or key in leases:
                    raise OwnerCapabilityFault(
                        code=OwnerCapabilityFaultCode.RESOURCE_ALREADY_OWNED,
                        disposition=OwnerCapabilityFaultDisposition.REJECTED,
                        capability_kind=capability_kind,
                    )
                keys.add(key)
                rows.append((key, resource))
            lease = object()
            for key in keys:
                leases[key] = lease
            return _OwnerResourceClaim(lease=lease, resources=tuple(rows))

    def release_owner_resources(claim: _OwnerResourceClaim, /) -> None:
        nonlocal disposal_failed
        if type(claim) is not _OwnerResourceClaim:
            raise TypeError("owner resource claim has the wrong type")
        with lock:
            for key, resource in claim.resources:
                if leases.get(key) is claim.lease:
                    leases.pop(key, None)
                try:
                    resource.close_owner_resource()
                except BaseException:
                    disposal_failed = True

    def before_fork() -> None:
        lock.acquire()

    def after_fork_parent() -> None:
        lock.release()

    def after_fork_child() -> None:
        nonlocal lock, disposal_failed
        try:
            for handle, entry in tuple(entries.items()):
                entry.resource_finalizer.detach()
                if entry.live:
                    try:
                        os.close(entry.descriptor)
                    except OSError:
                        disposal_failed = True
                    entry.live = False
            leases.clear()
            for participant in tuple(participants):
                participant(True)
        finally:
            lock = RLock()

    return (
        open_owner_directory,
        require_owner_descriptor,
        close_owner_descriptor,
        owner_descriptor_lease_key,
        claim_owner_resources,
        release_owner_resources,
        register_fork_participant,
        lifecycle_section,
        before_fork,
        after_fork_parent,
        after_fork_child,
    )


@dataclass(slots=True, weakref_slot=True, eq=False, init=False)
class _PosixOpenedDirectoryHandle:
    descriptor: int
    creator_pid: int
    owner_kind: OwnerCapabilityKind
    open_generation: int
    opened_identity: _OpenedDescriptorIdentity

    def require_current_process_descriptor(self) -> int:
        return _require_owner_descriptor(self)

    def owner_resource_lease_key(self) -> _OwnerResourceKey:
        return _owner_descriptor_lease_key(self)

    def close_owner_resource(self) -> None:
        _close_owner_descriptor(self)


def _strip_annotated(annotation: object) -> object:
    while get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]
    return annotation


def _annotation_at_path(
    root_type: type[object], field_path: tuple[str, ...]
) -> object:
    current: object = root_type
    bindings: dict[object, object] = {}

    def substitute(annotation: object) -> object:
        try:
            if annotation in bindings:
                return bindings[annotation]
        except TypeError:
            pass
        origin = get_origin(annotation)
        if origin is None:
            if getattr(annotation, "__bound__", None) is DigestDomain:
                return DigestDomain
            return annotation
        arguments = get_args(annotation)
        replaced = tuple(substitute(argument) for argument in arguments)
        if replaced == arguments:
            return annotation
        copy_with = getattr(annotation, "copy_with", None)
        if callable(copy_with):
            return copy_with(replaced)
        return annotation

    for name in field_path:
        current = substitute(_strip_annotated(current))
        origin = get_origin(current)
        if origin is tuple:
            arguments = get_args(current)
            if len(arguments) != 2 or arguments[1] is not Ellipsis:
                raise TypeError("owner payload path crosses a non-homogeneous tuple")
            current = substitute(arguments[0])
            origin = get_origin(current)
        if origin is not None and isinstance(origin, type):
            parameters = tuple(getattr(origin, "__parameters__", ()))
            arguments = get_args(current)
            if parameters and len(parameters) == len(arguments):
                bindings.update(
                    {
                        parameter: substitute(argument)
                        for parameter, argument in zip(
                            parameters,
                            arguments,
                            strict=True,
                        )
                    }
                )
            current_type = origin
        elif isinstance(current, type):
            current_type = current
        else:
            raise TypeError("owner payload path has an unresolved annotation")
        hints = get_type_hints(current_type, include_extras=True)
        if name not in hints:
            raise TypeError("owner payload path does not resolve")
        current = substitute(hints[name])
    return substitute(_strip_annotated(current))


def validate_owner_payload_spec_annotation_graph(
    *,
    spec: _OwnerPayloadSpec[object, object],
    spec_by_kind: Mapping[
        OwnerCapabilityKind, _OwnerPayloadSpec[object, object]
    ],
) -> None:
    """Resolve every declared spec path against the exact payload annotations."""

    used_paths: set[tuple[str, ...]] = set()
    for leaf in spec.exact_concrete_leaves:
        annotation = _annotation_at_path(spec.payload_type, leaf.field_path)
        if annotation is not leaf.exact_concrete_type:
            raise TypeError("owner payload leaf annotation is not its exact concrete type")
        used_paths.add(leaf.field_path)
    for child_path in spec.child_resource_paths:
        child_type = _annotation_at_path(spec.payload_type, child_path)
        for method_name in (
            "require_current_process_descriptor",
            "owner_resource_lease_key",
            "close_owner_resource",
        ):
            if not callable(getattr(child_type, method_name, None)):
                raise TypeError("owner child resource lacks the closed disposal interface")
    if spec.dynamic_record_domain_path is not None:
        domain_annotation = _annotation_at_path(
            spec.payload_type, spec.dynamic_record_domain_path
        )
        ref_annotation = _annotation_at_path(
            spec.payload_type,
            cast("tuple[str, ...]", spec.dynamic_record_ref_domain_path),
        )
        if domain_annotation is not DigestDomain or ref_annotation is not DigestDomain:
            raise TypeError(
                "dynamic record-domain paths must terminate at DigestDomain: "
                f"{domain_annotation!r}, {ref_annotation!r}"
            )
    for nested in spec.nested_tokens:
        nested_spec = spec_by_kind.get(nested.nested_kind)
        if nested_spec is None:
            raise TypeError("nested capability kind is not registered")
        annotation = _annotation_at_path(spec.payload_type, nested.payload_path)
        if nested.cardinality is _OwnerNestedCardinality.MANY:
            if get_origin(annotation) is not tuple:
                raise TypeError("MANY nested capability requires tuple[T, ...]")
            arguments = get_args(annotation)
            if len(arguments) != 2 or arguments[1] is not Ellipsis:
                raise TypeError("MANY nested capability requires tuple[T, ...]")
            annotation = _strip_annotated(arguments[0])
        elif get_origin(annotation) is tuple:
            raise TypeError("SINGLE nested capability rejects a sequence")
        if nested.token_path:
            if not isinstance(annotation, type):
                raise TypeError("nested capability payload annotation is unresolved")
            token_annotation = _annotation_at_path(annotation, nested.token_path)
        else:
            token_annotation = annotation
        if token_annotation is not nested_spec.token_type:
            raise TypeError("nested capability token path has the wrong token type")
        if nested.expected_domain_path is not None:
            if not isinstance(annotation, type):
                raise TypeError("nested domain payload annotation is unresolved")
            domain_annotation = _annotation_at_path(
                annotation, nested.expected_domain_path
            )
            if domain_annotation is not DigestDomain:
                raise TypeError("nested expected-domain path is not DigestDomain")
        used_paths.add(nested.payload_path)
    declared = {leaf.field_path for leaf in spec.exact_concrete_leaves}
    if not set(spec.child_resource_paths).issubset(declared):
        raise TypeError("owner child resource path is not a declared exact leaf")


def validate_owner_payload_annotation_graph(
    payload: object,
    *,
    spec_by_token: Mapping[type[object], _OwnerPayloadSpec[object, object]],
) -> None:
    """Reject open-ended payload leaves and reconstruct every persisted DTO."""

    seen: set[int] = set()

    def walk(value: object) -> None:
        if id(value) in seen:
            return
        seen.add(id(value))
        if type(value) in spec_by_token:
            return
        if isinstance(value, FoundryAuthorityModel):
            type(value).model_validate(value.model_dump(mode="python"), strict=True)
            for field_name in type(value).model_fields:
                walk(getattr(value, field_name))
            return
        if is_dataclass(value) and not isinstance(value, type):
            for field in fields(value):
                walk(getattr(value, field.name))
            return
        if type(value) is tuple:
            for member in value:
                walk(member)
            return
        if type(value) in {str, bytes, int, bool, type(None), DigestDomain}:
            return
        if isinstance(value, Path):
            return
        if isinstance(value, StrEnum):
            return
        if type(value) in {list, dict, set} or value is Any:
            raise TypeError("owner payload contains an open-ended mutable leaf")

    walk(payload)


class DependencyAuthorityRegistryStatement(FoundryAuthorityModel):
    """Typed semantic authority registry; empty owner rows remain explicit."""

    schema_version: Literal[
        "polisyos.foundry.dependency-authority-registry.v1"
    ]
    purpose_admissions: tuple[MethodCatalogProfileAdmission, ...]
    toolchain_admissions: tuple[ToolchainArtifactAdmission, ...]
    launcher_profiles: tuple[LauncherProfileSpec, ...]
    foundry_trust_root_keys: tuple[TrustPublicKey, ...]
    production_data_trust_policies: tuple[ProductionDataTrustPolicyStatement, ...]

    @model_validator(mode="after")
    def validate_denominators(self) -> DependencyAuthorityRegistryStatement:
        for label, keys in (
            (
                "purpose admissions",
                tuple(
                    f"{row.authority_purpose}:{row.profile_id}"
                    for row in self.purpose_admissions
                ),
            ),
            (
                "toolchain admissions",
                tuple(
                    f"{row.artifact_role}:{row.platform_tag}"
                    for row in self.toolchain_admissions
                ),
            ),
            (
                "launcher profiles",
                tuple(row.profile_id.value for row in self.launcher_profiles),
            ),
            (
                "Foundry root keys",
                tuple(row.key_id for row in self.foundry_trust_root_keys),
            ),
        ):
            if keys and (keys != tuple(sorted(keys)) or len(keys) != len(set(keys))):
                raise ValueError(f"{label} must be sorted and unique")
        return self


class MethodCatalogDependencyAuthorityRequest(FoundryAuthorityModel):
    """Only caller-owned coordinates accepted by the Foundry authority."""

    authority_purpose: Literal["n8_method_catalog_reconstruction"]
    expected_source_freeze_commit: GitCommitId
    production_data_root: AbsoluteRequestPath
    environment_root: AbsoluteRequestPath


class DependencyAuthorityPreSourceRequestStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.dependency-pre-source-request.v1"]
    authority_purpose: Literal["n8_method_catalog_reconstruction"]
    expected_source_freeze_commit: GitCommitId
    production_data_request_token: DomainDigest[Literal[DigestDomain.ROOT_MOUNT_REQUEST]]
    environment_request_token: DomainDigest[Literal[DigestDomain.ENVIRONMENT_INSTANCE]]


class DependencyAuthorityResolvedSourceRequestStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.dependency-resolved-source-request.v1"]
    pre_source_request: DependencyAuthorityPreSourceRequestStatement
    expected_source_tree_id: GitTreeId


class NegativeDependencyAuthorityResultKind(StrEnum):
    SOURCE_REJECTED = "source_rejected"
    SOURCE_NOT_ESTABLISHED = "source_not_established"
    RUNTIME_CUTOFF_NOT_ESTABLISHED = "runtime_cutoff_not_established"


@dataclass(frozen=True, slots=True)
class SourceBootstrapFailureStageSpec:
    result_kind: NegativeDependencyAuthorityResultKind
    status: OwnerCapabilityFaultDisposition
    predicate_id: Literal[AuthorityPredicateId.SOURCE_FREEZE]
    failure_code: AuthorityFailureCode
    request_shape: Literal["pre_source", "resolved_source"]
    source_ref_rule: Literal["forbidden"]
    persistence: Literal["not_established"]
    persistence_capability: Literal["owner_resolved_resolution_receipt_store"]
    persistence_capability_state: Literal["absent/unallocated"]


@dataclass(frozen=True, slots=True)
class PostSourceNegativeAuthorityStageSpec:
    result_kind: Literal[
        NegativeDependencyAuthorityResultKind.RUNTIME_CUTOFF_NOT_ESTABLISHED
    ]
    status: Literal[OwnerCapabilityFaultDisposition.NOT_ESTABLISHED]
    predicate_id: AuthorityPredicateId
    required_branch_shape: Literal["not_established_only"]
    source_ref_rule: Literal["required"]
    persistence: Literal["not_established"]
    persistence_capability: Literal["owner_resolved_resolution_receipt_store"]
    persistence_capability_state: Literal["absent/unallocated"]


class NegativeResultPersistenceDisposition(FoundryAuthorityModel):
    status: Literal["not_established"]
    missing_capability: Literal["owner_resolved_resolution_receipt_store"]
    missing_capability_state: Literal["absent/unallocated"]


class CandidateRuntimeEvidenceNotRequested(FoundryAuthorityModel):
    status: Literal["not_requested"]
    reason: Literal["owner_enforced_runtime_subtree_cutoff_absent"]


class CandidateRuntimeEvidencePresent(FoundryAuthorityModel):
    status: Literal["present"]
    evidence_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME]]


RuntimeCandidateEvidenceDisposition = Annotated[
    CandidateRuntimeEvidenceNotRequested | CandidateRuntimeEvidencePresent,
    Field(discriminator="status"),
]


class SourceFreezeRejectedPredicate(FoundryAuthorityModel):
    status: Literal["rejected"]
    predicate_id: Literal[AuthorityPredicateId.SOURCE_FREEZE]
    predicate_class: Literal["recomputed"]
    failure_code: Literal[AuthorityFailureCode.SOURCE_FREEZE_MISMATCH]
    expected_source_freeze_commit: GitCommitId
    expected_source_tree_id: GitTreeId
    owner_observed_head_commit: GitCommitId
    owner_observed_tree_id: GitTreeId
    observation_producer: Literal["canonical_module_git_recompute_v1"]

    @model_validator(mode="after")
    def require_actual_source_difference(self) -> SourceFreezeRejectedPredicate:
        if (
            self.expected_source_freeze_commit == self.owner_observed_head_commit
            and self.expected_source_tree_id == self.owner_observed_tree_id
        ):
            raise ValueError("source rejection requires a commit or tree mismatch")
        return self


class SourceFreezeUnestablishedPredicate(FoundryAuthorityModel):
    status: Literal["not_established"]
    predicate_id: Literal[AuthorityPredicateId.SOURCE_FREEZE]
    predicate_class: Literal["not_established"]
    failure_code: Literal[AuthorityFailureCode.SOURCE_NOT_ESTABLISHED]
    missing_domains: tuple[Literal[DigestDomain.CANONICAL_SOURCE], ...]


class RuntimeCutoffUnestablishedPredicate(FoundryAuthorityModel):
    status: Literal["not_established"]
    predicate_id: Literal[AuthorityPredicateId.RUNTIME_SUBTREE_CUTOFF]
    predicate_class: Literal["not_established"]
    failure_code: Literal[
        AuthorityFailureCode.RUNTIME_SUBTREE_CUTOFF_NOT_ESTABLISHED
    ]
    missing_capability: Literal["owner_enforced_runtime_subtree_cutoff"]
    missing_capability_state: Literal["absent/unallocated"]
    candidate_runtime_evidence: RuntimeCandidateEvidenceDisposition


class SourceRejectedMethodCatalogDependencyProfile(FoundryAuthorityModel):
    result_kind: Literal[NegativeDependencyAuthorityResultKind.SOURCE_REJECTED]
    status: Literal["rejected"]
    persistence: NegativeResultPersistenceDisposition
    request: DependencyAuthorityResolvedSourceRequestStatement
    failure: SourceFreezeRejectedPredicate

    @model_validator(mode="after")
    def validate_stage(self) -> SourceRejectedMethodCatalogDependencyProfile:
        validate_source_bootstrap_failure(self)
        return self


class SourceUnestablishedMethodCatalogDependencyProfile(FoundryAuthorityModel):
    result_kind: Literal[NegativeDependencyAuthorityResultKind.SOURCE_NOT_ESTABLISHED]
    status: Literal["not_established"]
    persistence: NegativeResultPersistenceDisposition
    request: DependencyAuthorityPreSourceRequestStatement
    failure: SourceFreezeUnestablishedPredicate

    @model_validator(mode="after")
    def validate_stage(self) -> SourceUnestablishedMethodCatalogDependencyProfile:
        validate_source_bootstrap_failure(self)
        return self


class RuntimeCutoffPreflightRefusal(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.runtime-cutoff-preflight-refusal.v1"]
    persistence: NegativeResultPersistenceDisposition
    source_authority_ref: FoundryRecordRef[Literal[DigestDomain.CANONICAL_SOURCE]]
    request: DependencyAuthorityResolvedSourceRequestStatement
    failure: RuntimeCutoffUnestablishedPredicate


class UnestablishedMethodCatalogDependencyProfile(FoundryAuthorityModel):
    result_kind: Literal[
        NegativeDependencyAuthorityResultKind.RUNTIME_CUTOFF_NOT_ESTABLISHED
    ]
    status: Literal["not_established"]
    preflight_refusal: RuntimeCutoffPreflightRefusal


MethodCatalogDependencyAuthorityResult = Annotated[
    SourceRejectedMethodCatalogDependencyProfile
    | SourceUnestablishedMethodCatalogDependencyProfile
    | UnestablishedMethodCatalogDependencyProfile,
    Field(discriminator="result_kind"),
]
DependencyProfileResolutionFailure = MethodCatalogDependencyAuthorityResult


SourceBootstrapFailureResult = (
    SourceRejectedMethodCatalogDependencyProfile
    | SourceUnestablishedMethodCatalogDependencyProfile
)


def validate_source_bootstrap_failure(result: SourceBootstrapFailureResult) -> None:
    """Validate the pre-registry failure grammar without consulting source data."""

    stage = SOURCE_BOOTSTRAP_FAILURE_STAGES.get(result.result_kind)
    if stage is None:
        raise ValueError("source bootstrap result kind is not registered")
    if (
        result.status != stage.status.value
        or result.failure.predicate_id is not stage.predicate_id
        or result.failure.failure_code is not stage.failure_code
        or result.persistence.status != stage.persistence
        or result.persistence.missing_capability != stage.persistence_capability
        or result.persistence.missing_capability_state
        != stage.persistence_capability_state
    ):
        raise ValueError("source bootstrap result does not match its frozen stage")
    resolved = isinstance(result.request, DependencyAuthorityResolvedSourceRequestStatement)
    if resolved != (stage.request_shape == "resolved_source"):
        raise ValueError("source bootstrap request shape does not match its stage")
    if isinstance(result, SourceRejectedMethodCatalogDependencyProfile):
        if (
            result.failure.expected_source_freeze_commit
            != result.request.pre_source_request.expected_source_freeze_commit
            or result.failure.expected_source_tree_id
            != result.request.expected_source_tree_id
        ):
            raise ValueError("source rejection is not bound to its request source")


class CanonicalFoundrySourceAuthorityStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.canonical-source-authority.v1"]
    source_freeze_commit: GitCommitId
    source_tree_id: GitTreeId
    profile_registry_ref: FoundryRecordRef[Literal[DigestDomain.PROFILE_REGISTRY]]
    authority_registry_ref: FoundryRecordRef[Literal[DigestDomain.AUTHORITY_REGISTRY]]
    digest_registry_ref: FoundryRecordRef[Literal[DigestDomain.DIGEST_REGISTRY]]


def _strict_statement_types(statement_type: object) -> tuple[type[FoundryAuthorityModel], ...]:
    """Expand one strict model or discriminated union into its concrete models."""

    origin = get_origin(statement_type)
    if origin is Annotated:
        return _strict_statement_types(get_args(statement_type)[0])
    if origin in {Union, UnionType}:
        members = tuple(
            model
            for member in get_args(statement_type)
            for model in _strict_statement_types(member)
        )
        if not members or len(members) != len(set(members)):
            raise TypeError("statement union must contain unique strict model variants")
        return members
    if (
        isinstance(statement_type, type)
        and issubclass(statement_type, FoundryAuthorityModel)
    ):
        return (statement_type,)
    raise TypeError("statement codec target must be a strict Foundry model or union")


def _strict_schema_versions(
    statement_types: tuple[type[FoundryAuthorityModel], ...],
) -> frozenset[str]:
    versions: set[str] = set()
    for statement_type in statement_types:
        field = statement_type.model_fields.get("schema_version")
        if field is None or get_origin(field.annotation) is not Literal:
            raise TypeError("statement codec variant must declare a Literal schema_version")
        values = get_args(field.annotation)
        if len(values) != 1 or type(values[0]) is not str:
            raise TypeError("statement schema_version must be one exact string literal")
        versions.add(values[0])
    if len(versions) != len(statement_types):
        raise TypeError("statement union schema versions must be unique")
    return frozenset(versions)


@dataclass(frozen=True, slots=True)
class StrictStatementCodec:
    """One domain-specialized strict canonical-statement codec."""

    domain: DigestDomain
    statement_type: object
    statement_types: tuple[type[FoundryAuthorityModel], ...]
    schema_versions: frozenset[str]
    adapter: TypeAdapter[Any]

    def encode(self, statement: object) -> bytes:
        parsed = self.adapter.validate_python(statement, strict=True)
        if not isinstance(parsed, FoundryAuthorityModel):
            raise TypeError("statement codec did not produce a Foundry authority model")
        schema_version = getattr(parsed, "schema_version", None)
        if schema_version not in self.schema_versions:
            raise ValueError("statement schema version does not match its digest domain")
        return canonical_json_bytes(parsed.model_dump(mode="json"))

    def recompute_preimage(self, statement: object) -> bytes:
        """Independently reconstruct the preimage used by the verifier."""

        parsed = self.adapter.validate_python(statement, strict=True)
        if not isinstance(parsed, FoundryAuthorityModel):
            raise TypeError("statement verifier did not produce a Foundry authority model")
        if getattr(parsed, "schema_version", None) not in self.schema_versions:
            raise ValueError("statement schema version does not match its digest domain")
        dumped = parsed.model_dump(mode="json")
        return canonical_json_bytes(dumped)

    def decode(self, raw: bytes) -> FoundryAuthorityModel:
        if type(raw) is not bytes:
            raise TypeError("statement wire value must be exact bytes")
        parsed = self.adapter.validate_json(raw, strict=True)
        if not isinstance(parsed, FoundryAuthorityModel):
            raise TypeError("statement codec did not produce a Foundry authority model")
        schema_version = getattr(parsed, "schema_version", None)
        if schema_version not in self.schema_versions:
            raise ValueError("statement schema version does not match its digest domain")
        if canonical_json_bytes(parsed.model_dump(mode="json")) != raw:
            raise ValueError("statement bytes are not the canonical v1 encoding")
        return parsed


def _strict_statement_codec(
    domain: DigestDomain,
    statement_type: object,
) -> StrictStatementCodec:
    statement_types = _strict_statement_types(statement_type)
    return StrictStatementCodec(
        domain=domain,
        statement_type=statement_type,
        statement_types=statement_types,
        schema_versions=_strict_schema_versions(statement_types),
        adapter=TypeAdapter(statement_type),
    )


FOUNDRY_STATEMENT_CODECS: Mapping[DigestDomain, StrictStatementCodec] = (
    MappingProxyType(
        {
            DigestDomain.CANONICAL_SOURCE: _strict_statement_codec(
                DigestDomain.CANONICAL_SOURCE,
                CanonicalFoundrySourceAuthorityStatement,
            ),
            DigestDomain.PROFILE_DECLARATION: _strict_statement_codec(
                DigestDomain.PROFILE_DECLARATION,
                profile_module.MethodCatalogDependencyProfileDeclaration,
            ),
            DigestDomain.PROFILE_ADMISSION: _strict_statement_codec(
                DigestDomain.PROFILE_ADMISSION,
                profile_module.MethodCatalogProfileAdmission,
            ),
            DigestDomain.TOOLCHAIN_RUNTIME: _strict_statement_codec(
                DigestDomain.TOOLCHAIN_RUNTIME,
                evidence_module.PythonRuntimeManifestStatement,
            ),
            DigestDomain.TOOLCHAIN_RUNTIME_OBSERVED: _strict_statement_codec(
                DigestDomain.TOOLCHAIN_RUNTIME_OBSERVED,
                evidence_module.ObservedPythonRuntimeStatement,
            ),
            DigestDomain.TOOLCHAIN_RUNTIME_ROOT: _strict_statement_codec(
                DigestDomain.TOOLCHAIN_RUNTIME_ROOT,
                evidence_module.PythonRuntimeRootResolutionStatement,
            ),
            DigestDomain.TOOLCHAIN_RUNTIME_ROOT_TOKEN: _strict_statement_codec(
                DigestDomain.TOOLCHAIN_RUNTIME_ROOT_TOKEN,
                evidence_module.PosixRuntimeRootIdentityStatement,
            ),
            DigestDomain.TOOLCHAIN_RUNTIME_INSTALLATION: _strict_statement_codec(
                DigestDomain.TOOLCHAIN_RUNTIME_INSTALLATION,
                evidence_module.PythonRuntimeInstallationStatement,
            ),
            DigestDomain.TOOLCHAIN_RUNTIME_VERIFICATION: _strict_statement_codec(
                DigestDomain.TOOLCHAIN_RUNTIME_VERIFICATION,
                evidence_module.PythonRuntimeVerificationReceiptStatement,
            ),
            DigestDomain.TRUST_MATERIAL: _strict_statement_codec(
                DigestDomain.TRUST_MATERIAL,
                evidence_module.TrustMaterialStatement,
            ),
            DigestDomain.TRUST_REVOCATION: _strict_statement_codec(
                DigestDomain.TRUST_REVOCATION,
                evidence_module.TrustRevocationStatement,
            ),
            DigestDomain.TRUST_RESOLUTION: _strict_statement_codec(
                DigestDomain.TRUST_RESOLUTION,
                evidence_module.TrustResolutionReceiptStatement,
            ),
            DigestDomain.TRUST_POLICY: _strict_statement_codec(
                DigestDomain.TRUST_POLICY,
                evidence_module.ProductionDataTrustPolicyStatement,
            ),
            DigestDomain.VERIFIER_PROVENANCE: _strict_statement_codec(
                DigestDomain.VERIFIER_PROVENANCE,
                evidence_module.VerifierProvenanceStatement,
            ),
            DigestDomain.PRODUCTION_APPOINTMENT: _strict_statement_codec(
                DigestDomain.PRODUCTION_APPOINTMENT,
                evidence_module.ProductionDataInputAppointmentStatement,
            ),
            DigestDomain.PRODUCTION_CUSTODY: _strict_statement_codec(
                DigestDomain.PRODUCTION_CUSTODY,
                evidence_module.ProductionDataCustodyStatement,
            ),
            DigestDomain.ROOT_CHALLENGE: _strict_statement_codec(
                DigestDomain.ROOT_CHALLENGE,
                evidence_module.ProductionDataRootAccessChallenge,
            ),
            DigestDomain.ROOT_MOUNT_RESOLUTION: _strict_statement_codec(
                DigestDomain.ROOT_MOUNT_RESOLUTION,
                evidence_module.ProductionDataMountResolutionStatement,
            ),
            DigestDomain.ROOT_ACCESS: _strict_statement_codec(
                DigestDomain.ROOT_ACCESS,
                evidence_module.RootAccessAttestationStatement,
            ),
            DigestDomain.SELECTED_DISTRIBUTION: _strict_statement_codec(
                DigestDomain.SELECTED_DISTRIBUTION,
                evidence_module.SelectedDistributionArtifactEvidence,
            ),
            DigestDomain.WHEEL_RECORD: _strict_statement_codec(
                DigestDomain.WHEEL_RECORD,
                evidence_module.WheelRecordManifestStatement,
            ),
            DigestDomain.SOURCE_TREE: _strict_statement_codec(
                DigestDomain.SOURCE_TREE,
                evidence_module.SourceTreeManifestStatement,
            ),
            DigestDomain.BUILD_PROFILE: _strict_statement_codec(
                DigestDomain.BUILD_PROFILE,
                evidence_module.BuildProfileStatement,
            ),
            DigestDomain.BUILD_LINEAGE: _strict_statement_codec(
                DigestDomain.BUILD_LINEAGE,
                evidence_module.BuildLineageStatement,
            ),
            DigestDomain.ENVIRONMENT_MARKER: _strict_statement_codec(
                DigestDomain.ENVIRONMENT_MARKER,
                evidence_module.DependencyEnvironmentMarkerStatement,
            ),
            DigestDomain.ENVIRONMENT_RECEIPT: _strict_statement_codec(
                DigestDomain.ENVIRONMENT_RECEIPT,
                evidence_module.DependencyProfileEnvironmentStatement,
            ),
            DigestDomain.CAPSULE: _strict_statement_codec(
                DigestDomain.CAPSULE,
                evidence_module.FoundryDependencyAuthorityCapsuleStatement,
            ),
            DigestDomain.RESOLUTION_REQUEST: _strict_statement_codec(
                DigestDomain.RESOLUTION_REQUEST,
                Annotated[
                    DependencyAuthorityPreSourceRequestStatement
                    | DependencyAuthorityResolvedSourceRequestStatement,
                    Field(discriminator="schema_version"),
                ],
            ),
            DigestDomain.SIGNED_EVIDENCE: _strict_statement_codec(
                DigestDomain.SIGNED_EVIDENCE,
                evidence_module.ExactSignedArtifactEvidenceStatement,
            ),
        }
    )
)


DigestPreimageBuilder = Callable[[object], bytes]
DigestProducer = Callable[[DigestDomain, bytes], DomainDigest[DigestDomain]]
DigestVerifier = Callable[
    [DigestDomain, bytes, DomainDigest[DigestDomain]],
    bool,
]


def _require_exact_bytes(value: object) -> bytes:
    if type(value) is not bytes:
        raise TypeError("raw digest preimage must be exact bytes")
    return value


def _build_canonical_statement_preimage(value: object) -> bytes:
    if not isinstance(value, FoundryAuthorityModel):
        raise TypeError("canonical statement preimage must be a strict Foundry model")
    return canonical_json_bytes(value.model_dump(mode="json"))


def _build_tracked_toml_preimage(value: object) -> bytes:
    raw = _require_exact_bytes(value)
    parsed = tomllib.loads(raw.decode("utf-8"))
    return canonical_json_bytes(parsed)


def _require_exact_byte_rows(value: object) -> tuple[bytes, ...]:
    if type(value) is not tuple or any(type(row) is not bytes for row in value):
        raise TypeError("framed digest preimage must be an exact tuple of bytes")
    return value


def _frame_digest_rows(rows: tuple[bytes, ...]) -> bytes:
    return b"".join(len(row).to_bytes(8, byteorder="big") + row for row in rows)


def _build_ordered_rows_preimage(value: object) -> bytes:
    rows = _require_exact_byte_rows(value)
    if rows != tuple(sorted(rows)) or len(rows) != len(set(rows)):
        raise ValueError("ordered-row preimage must be sorted and unique")
    return _frame_digest_rows(rows)


def _build_relation_preimage(value: object) -> bytes:
    return _frame_digest_rows(_require_exact_byte_rows(value))


def _verify_raw_blob_preimage(value: object) -> bytes:
    if type(value) is not bytes:
        raise TypeError("raw digest verifier requires exact bytes")
    return value


def _reparse_tracked_toml_preimage(value: object) -> bytes:
    if type(value) is not bytes:
        raise TypeError("tracked TOML verifier requires exact bytes")
    decoded = value.decode("utf-8")
    reparsed = tomllib.loads(decoded)
    return canonical_json_bytes(reparsed)


def _recompute_ordered_rows_preimage(value: object) -> bytes:
    if type(value) is not tuple or any(type(row) is not bytes for row in value):
        raise TypeError("ordered-row verifier requires an exact tuple of bytes")
    independently_sorted = tuple(sorted(value))
    if value != independently_sorted or len(value) != len(set(value)):
        raise ValueError("ordered-row verifier requires sorted unique rows")
    return b"".join(
        len(row).to_bytes(8, byteorder="big") + row
        for row in independently_sorted
    )


def _recompute_relation_preimage(value: object) -> bytes:
    if type(value) is not tuple or any(type(part) is not bytes for part in value):
        raise TypeError("relation verifier requires an exact tuple of bytes")
    framed = bytearray()
    for part in value:
        framed.extend(len(part).to_bytes(8, byteorder="big"))
        framed.extend(part)
    return bytes(framed)


def _produce_canonical_statement_v1(
    domain: DigestDomain,
    preimage: bytes,
) -> DomainDigest[DigestDomain]:
    return domain_digest(domain, preimage)


def _produce_raw_blob_v1(
    domain: DigestDomain,
    preimage: bytes,
) -> DomainDigest[DigestDomain]:
    return domain_digest(domain, preimage)


def _produce_tracked_toml_v1(
    domain: DigestDomain,
    preimage: bytes,
) -> DomainDigest[DigestDomain]:
    return domain_digest(domain, preimage)


def _produce_ordered_rows_v1(
    domain: DigestDomain,
    preimage: bytes,
) -> DomainDigest[DigestDomain]:
    return domain_digest(domain, preimage)


def _produce_relation_v1(
    domain: DigestDomain,
    preimage: bytes,
) -> DomainDigest[DigestDomain]:
    return domain_digest(domain, preimage)


def _recompute_digest_v1(
    domain: DigestDomain,
    preimage: bytes,
    expected: DomainDigest[DigestDomain],
) -> bool:
    prefix = f"polisyos.foundry.{domain.value}.v1\0".encode("ascii")
    framed = prefix + len(preimage).to_bytes(8, byteorder="big") + preimage
    return expected.domain is domain and expected.value == sha256_wire(framed)


def _verify_canonical_statement_v1(
    domain: DigestDomain,
    preimage: bytes,
    expected: DomainDigest[DigestDomain],
) -> bool:
    return _recompute_digest_v1(domain, preimage, expected)


def _verify_raw_blob_v1(
    domain: DigestDomain,
    preimage: bytes,
    expected: DomainDigest[DigestDomain],
) -> bool:
    return _recompute_digest_v1(domain, preimage, expected)


def _verify_tracked_toml_v1(
    domain: DigestDomain,
    preimage: bytes,
    expected: DomainDigest[DigestDomain],
) -> bool:
    return _recompute_digest_v1(domain, preimage, expected)


def _verify_ordered_rows_v1(
    domain: DigestDomain,
    preimage: bytes,
    expected: DomainDigest[DigestDomain],
) -> bool:
    return _recompute_digest_v1(domain, preimage, expected)


def _verify_relation_v1(
    domain: DigestDomain,
    preimage: bytes,
    expected: DomainDigest[DigestDomain],
) -> bool:
    return _recompute_digest_v1(domain, preimage, expected)


DIGEST_PREIMAGE_BUILDERS: Mapping[DigestPreimageKind, DigestPreimageBuilder] = (
    MappingProxyType(
        {
            DigestPreimageKind.CANONICAL_STATEMENT: (
                _build_canonical_statement_preimage
            ),
            DigestPreimageKind.RAW_BLOB: _require_exact_bytes,
            DigestPreimageKind.TRACKED_TOML: _build_tracked_toml_preimage,
            DigestPreimageKind.ORDERED_ROWS: _build_ordered_rows_preimage,
            DigestPreimageKind.RELATION: _build_relation_preimage,
        }
    )
)
DIGEST_VERIFIER_PREIMAGE_BUILDERS: Mapping[
    DigestPreimageKind,
    DigestPreimageBuilder,
] = MappingProxyType(
    {
        DigestPreimageKind.CANONICAL_STATEMENT: (
            _build_canonical_statement_preimage
        ),
        DigestPreimageKind.RAW_BLOB: _verify_raw_blob_preimage,
        DigestPreimageKind.TRACKED_TOML: _reparse_tracked_toml_preimage,
        DigestPreimageKind.ORDERED_ROWS: _recompute_ordered_rows_preimage,
        DigestPreimageKind.RELATION: _recompute_relation_preimage,
    }
)
DIGEST_PRODUCERS: Mapping[DigestProducerId, DigestProducer] = MappingProxyType(
    {
        DigestProducerId.CANONICAL_STATEMENT_V1: _produce_canonical_statement_v1,
        DigestProducerId.RAW_BLOB_V1: _produce_raw_blob_v1,
        DigestProducerId.TRACKED_TOML_V1: _produce_tracked_toml_v1,
        DigestProducerId.ORDERED_ROWS_V1: _produce_ordered_rows_v1,
        DigestProducerId.RELATION_V1: _produce_relation_v1,
    }
)
DIGEST_VERIFIERS: Mapping[DigestVerifierId, DigestVerifier] = MappingProxyType(
    {
        DigestVerifierId.RECOMPUTE_CANONICAL_STATEMENT_V1: (
            _verify_canonical_statement_v1
        ),
        DigestVerifierId.REHASH_RAW_BLOB_V1: _verify_raw_blob_v1,
        DigestVerifierId.REPARSE_TRACKED_TOML_V1: _verify_tracked_toml_v1,
        DigestVerifierId.RECOMPUTE_ORDERED_ROWS_V1: _verify_ordered_rows_v1,
        DigestVerifierId.RECOMPUTE_RELATION_V1: _verify_relation_v1,
    }
)


@dataclass(frozen=True, slots=True)
class DigestDomainHandler:
    """Executable producer/verifier row derived from the owner registry."""

    domain: DigestDomain
    preimage_kind: DigestPreimageKind
    producer_id: DigestProducerId
    verifier_id: DigestVerifierId
    producer_preimage_builder: DigestPreimageBuilder
    verifier_preimage_builder: DigestPreimageBuilder
    producer: DigestProducer
    verifier: DigestVerifier
    statement_codec: StrictStatementCodec | None

    @property
    def preimage_builder(self) -> DigestPreimageBuilder:
        """Expose the registry-selected producer builder for introspection."""

        return self.producer_preimage_builder

    def build_preimage(self, value: object) -> bytes:
        if self.statement_codec is not None:
            return self.statement_codec.encode(value)
        return self.producer_preimage_builder(value)

    def recompute_preimage(self, value: object) -> bytes:
        if self.statement_codec is not None:
            return self.statement_codec.recompute_preimage(value)
        return self.verifier_preimage_builder(value)

    def produce(self, value: object) -> DomainDigest[DigestDomain]:
        return self.producer(self.domain, self.build_preimage(value))

    def verify(
        self,
        value: object,
        expected: DomainDigest[DigestDomain],
    ) -> bool:
        return self.verifier(self.domain, self.recompute_preimage(value), expected)


def build_digest_domain_handlers(
    registry: DecodedDigestDomainRegistry,
) -> Mapping[DigestDomain, DigestDomainHandler]:
    """Generate the complete executable digest algebra from one decoded table."""

    if frozenset(DIGEST_PREIMAGE_BUILDERS) != frozenset(DigestPreimageKind):
        raise ValueError("digest preimage builder denominator is incomplete")
    if frozenset(DIGEST_VERIFIER_PREIMAGE_BUILDERS) != frozenset(
        DigestPreimageKind
    ):
        raise ValueError("digest verifier preimage denominator is incomplete")
    if frozenset(DIGEST_PRODUCERS) != frozenset(DigestProducerId):
        raise ValueError("digest producer denominator is incomplete")
    if frozenset(DIGEST_VERIFIERS) != frozenset(DigestVerifierId):
        raise ValueError("digest verifier denominator is incomplete")
    handlers: dict[DigestDomain, DigestDomainHandler] = {}
    for row in registry.statement.domains:
        codec = FOUNDRY_STATEMENT_CODECS.get(row.domain_id)
        is_statement = row.algebra.preimage_kind is DigestPreimageKind.CANONICAL_STATEMENT
        if is_statement != (codec is not None):
            raise ValueError("statement codec and registry preimage kind disagree")
        if codec is not None and codec.domain is not row.domain_id:
            raise ValueError("statement codec key and owned domain disagree")
        handlers[row.domain_id] = DigestDomainHandler(
            domain=row.domain_id,
            preimage_kind=row.algebra.preimage_kind,
            producer_id=row.algebra.producer_id,
            verifier_id=row.algebra.verifier_id,
            producer_preimage_builder=DIGEST_PREIMAGE_BUILDERS[
                row.algebra.preimage_kind
            ],
            verifier_preimage_builder=DIGEST_VERIFIER_PREIMAGE_BUILDERS[
                row.algebra.preimage_kind
            ],
            producer=DIGEST_PRODUCERS[row.algebra.producer_id],
            verifier=DIGEST_VERIFIERS[row.algebra.verifier_id],
            statement_codec=codec,
        )
    if frozenset(handlers) != frozenset(DigestDomain):
        raise ValueError("digest handler denominator does not match DigestDomain")
    return MappingProxyType(handlers)


def load_strict_foundry_statement(
    *,
    record: FoundryRecordRef[DigestDomain],
    raw: bytes,
) -> FoundryAuthorityModel:
    """Content-bind and strictly decode one persisted canonical statement."""

    if type(raw) is not bytes:
        raise TypeError("statement wire value must be exact bytes")
    domain = record.semantic_hash.domain
    codec = FOUNDRY_STATEMENT_CODECS.get(domain)
    if codec is None:
        raise ValueError("digest domain does not carry a canonical statement")
    if record.schema_version not in codec.schema_versions:
        raise ValueError("statement schema version does not match its digest domain")
    if record.artifact_id != sha256_wire(raw):
        raise ValueError("statement artifact bytes do not match their CAS identity")
    if record.semantic_hash != domain_digest(domain, raw):
        raise ValueError("statement bytes do not match their semantic domain digest")
    statement = codec.decode(raw)
    if statement.schema_version != record.schema_version:
        raise ValueError("statement schema version does not match its persisted ref")
    return statement


def build_foundry_statement_ref(
    domain: DigestDomain,
    statement: FoundryAuthorityModel,
) -> FoundryRecordRef[DigestDomain]:
    """Build a statement pointer through the domain registry's real algebra."""

    schema_version = getattr(statement, "schema_version", None)
    if type(schema_version) is not str:
        raise TypeError("persisted Foundry statement needs one schema version")
    raw = canonical_json_bytes(statement.model_dump(mode="json"))
    registry = load_digest_domain_registry(_DIGEST_REGISTRY_PATH)
    handler = build_digest_domain_handlers(registry)[domain]
    if handler.preimage_kind is DigestPreimageKind.CANONICAL_STATEMENT:
        semantic_hash = handler.produce(statement)
    elif handler.preimage_kind is DigestPreimageKind.RELATION:
        semantic_hash = handler.produce((raw,))
    else:
        raise ValueError("statement domain does not use a statement/relation algebra")
    return FoundryRecordRef[DigestDomain](
        artifact_id=sha256_wire(raw),
        semantic_hash=semantic_hash,
        schema_version=schema_version,
    )


@dataclass(frozen=True, slots=True)
class CandidateRuntimeObservationHooks:
    """Deterministic mutation hooks for the reference two-pass observer."""

    relative_path: evidence_module.RootedRelativePath
    before_first_post_fstat: Callable[[], None] | None = None
    before_second_post_fstat: Callable[[], None] | None = None
    after_second_post_fstat: Callable[[], None] | None = None


@dataclass(frozen=True, slots=True)
class CandidatePythonRuntimeObservation:
    """Candidate-only observation; it never satisfies the production cutoff."""

    root_identity: evidence_module.PosixRuntimeRootIdentityStatement
    root_token: DomainDigest[Literal[DigestDomain.TOOLCHAIN_RUNTIME_ROOT_TOKEN]]
    first_manifest: evidence_module.PythonRuntimeManifestStatement
    second_manifest: evidence_module.PythonRuntimeManifestStatement


class _CandidateRuntimeObservationChanged(RuntimeError):
    """Internal signal for an unavailable or unstable candidate observation."""


def _candidate_runtime_not_established(
    digest_registry: DecodedDigestDomainRegistry,
) -> BidirectionalUnestablishedAuthorityPredicate:
    row = next(
        row
        for row in digest_registry.statement.predicates
        if row.predicate_id is AuthorityPredicateId.PYTHON_RUNTIME
    )
    if not isinstance(row, BidirectionalAuthorityPredicateSpec) or not isinstance(
        row.not_established_requirement,
        MissingEvidenceDomainsRequirement,
    ):
        raise AssertionError("python-runtime predicate is not bidirectional")
    return BidirectionalUnestablishedAuthorityPredicate(
        branch_shape="bidirectional",
        status="not_established",
        predicate_registry_ref=digest_registry.registry_ref,
        predicate_spec=row,
        predicate_id=AuthorityPredicateId.PYTHON_RUNTIME,
        predicate_class="not_established",
        failure_code=row.not_established_code,
        missing_domains=row.not_established_requirement.missing_domains,
    )


def _detect_candidate_runtime_filesystem_kind(
    runtime_root: Path,
) -> evidence_module.PosixRuntimeFilesystemKind | None:
    """Resolve the mounted filesystem itself; a caller never supplies its kind."""

    if not runtime_root.exists():
        return None
    resolved = Path(os.path.realpath(runtime_root))
    if sys.platform == "darwin":
        class _DarwinFsid(ctypes.Structure):
            _fields_ = (("values", ctypes.c_int32 * 2),)

        class _DarwinStatfs(ctypes.Structure):
            _fields_ = (
                ("block_size", ctypes.c_uint32),
                ("io_size", ctypes.c_int32),
                ("blocks", ctypes.c_uint64),
                ("blocks_free", ctypes.c_uint64),
                ("blocks_available", ctypes.c_uint64),
                ("files", ctypes.c_uint64),
                ("files_free", ctypes.c_uint64),
                ("filesystem_id", _DarwinFsid),
                ("owner", ctypes.c_uint32),
                ("filesystem_type", ctypes.c_uint32),
                ("flags", ctypes.c_uint32),
                ("filesystem_subtype", ctypes.c_uint32),
                ("filesystem_name", ctypes.c_char * 16),
                ("mounted_on", ctypes.c_char * 1024),
                ("mounted_from", ctypes.c_char * 1024),
                ("reserved", ctypes.c_uint32 * 8),
            )

        observed = _DarwinStatfs()
        libc = ctypes.CDLL(None, use_errno=True)
        statfs_call = libc.statfs
        statfs_call.argtypes = (ctypes.c_char_p, ctypes.POINTER(_DarwinStatfs))
        statfs_call.restype = ctypes.c_int
        if statfs_call(os.fsencode(resolved), ctypes.byref(observed)) != 0:
            return None
        if bytes(observed.filesystem_name).split(b"\0", 1)[0] == b"apfs":
            return evidence_module.PosixRuntimeFilesystemKind.APFS
        return None
    if sys.platform.startswith("linux"):
        try:
            rows = Path("/proc/self/mountinfo").read_text(encoding="utf-8").splitlines()
        except OSError:
            return None
        candidates = []
        for line in rows:
            before, separator, after = line.partition(" - ")
            if not separator:
                continue
            columns = before.split()
            after_columns = after.split()
            if len(columns) < 5 or not after_columns:
                continue
            mount_root = Path(columns[4].replace("\\040", " "))
            try:
                resolved.relative_to(mount_root)
            except ValueError:
                continue
            candidates.append((len(str(mount_root)), after_columns[0]))
        if candidates and max(candidates)[1] == "ext4":
            return evidence_module.PosixRuntimeFilesystemKind.EXT4
    return None


def _candidate_root_observation(
    descriptor: int,
) -> evidence_module.PosixRuntimeRootObservation:
    observed = os.fstat(descriptor)
    if not stat.S_ISDIR(observed.st_mode):
        raise _CandidateRuntimeObservationChanged("runtime root is not a directory")
    return evidence_module.PosixRuntimeRootObservation(
        device_id=observed.st_dev,
        inode=observed.st_ino,
        mode_type="directory",
        ctime_ns=observed.st_ctime_ns,
    )


def _candidate_runtime_file_role(
    relative_path: evidence_module.RootedRelativePath,
    executable_relative_path: evidence_module.RootedRelativePath,
) -> Literal["launcher", "stdlib", "libpython", "runtime_library"]:
    if relative_path == executable_relative_path:
        return "launcher"
    filename = Path(relative_path.value).name
    if filename.startswith("libpython"):
        return "libpython"
    if filename.endswith((".so", ".dylib")):
        return "runtime_library"
    return "stdlib"


def _candidate_runtime_paths(
    runtime_root: Path,
) -> tuple[evidence_module.RootedRelativePath, ...]:
    rows: list[evidence_module.RootedRelativePath] = []
    for candidate in runtime_root.rglob("*"):
        if candidate.is_symlink() or candidate.is_file():
            rows.append(
                evidence_module.RootedRelativePath(
                    value=candidate.relative_to(runtime_root).as_posix()
                )
            )
    if not rows:
        raise _CandidateRuntimeObservationChanged("runtime tree is empty")
    return tuple(sorted(rows, key=lambda row: row.value))


def _read_candidate_runtime_file(
    *,
    root_descriptor: int,
    relative_path: evidence_module.RootedRelativePath,
    walk_number: Literal[1, 2],
    hooks: CandidateRuntimeObservationHooks | None,
) -> tuple[bytes, os.stat_result]:
    flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(relative_path.value, flags, dir_fd=root_descriptor)
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise _CandidateRuntimeObservationChanged("runtime row is not regular")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        if hooks is not None and relative_path == hooks.relative_path:
            callback = (
                hooks.before_first_post_fstat
                if walk_number == 1
                else hooks.before_second_post_fstat
            )
            if callback is not None:
                callback()
        closed = os.fstat(descriptor)
        identity_fields = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        if any(getattr(opened, field) != getattr(closed, field) for field in identity_fields):
            raise _CandidateRuntimeObservationChanged(
                "runtime file changed during content observation"
            )
        if (
            walk_number == 2
            and hooks is not None
            and relative_path == hooks.relative_path
            and hooks.after_second_post_fstat is not None
        ):
            hooks.after_second_post_fstat()
        return b"".join(chunks), closed
    finally:
        os.close(descriptor)


def _walk_candidate_python_runtime(
    *,
    root_descriptor: int,
    runtime_root: Path,
    executable_relative_path: evidence_module.RootedRelativePath,
    version: str,
    platform_tag: str,
    abi_tag: str,
    walk_number: Literal[1, 2],
    hooks: CandidateRuntimeObservationHooks | None,
) -> evidence_module.PythonRuntimeManifestStatement:
    rows: list[evidence_module.PythonRuntimeFileRow] = []
    for relative_path in _candidate_runtime_paths(runtime_root):
        row_stat = os.stat(
            relative_path.value,
            dir_fd=root_descriptor,
            follow_symlinks=False,
        )
        role = _candidate_runtime_file_role(relative_path, executable_relative_path)
        if stat.S_ISLNK(row_stat.st_mode):
            target = os.readlink(relative_path.value, dir_fd=root_descriptor)
            rows.append(
                evidence_module.PythonRuntimeSymlinkRow(
                    row_kind="symlink",
                    relative_path=relative_path,
                    role=role,
                    symlink_target=evidence_module.RootedRelativePath(value=target),
                )
            )
            continue
        raw, closed = _read_candidate_runtime_file(
            root_descriptor=root_descriptor,
            relative_path=relative_path,
            walk_number=walk_number,
            hooks=hooks,
        )
        rows.append(
            evidence_module.PythonRuntimeRegularFileRow(
                row_kind="regular_file",
                relative_path=relative_path,
                role=role,
                byte_length=closed.st_size,
                content_hash=domain_digest(DigestDomain.RAW_BLOB, raw),
            )
        )
    return evidence_module.PythonRuntimeManifestStatement(
        schema_version="polisyos.foundry.python-runtime.v1",
        implementation="cpython",
        version=version,
        platform_tag=platform_tag,
        abi_tag=abi_tag,
        executable_relative_path=executable_relative_path,
        files=tuple(rows),
    )


def observe_candidate_python_runtime(
    *,
    environment_root: Path,
    runtime_root: Path,
    environment_creation_nonce: DomainDigest[
        Literal[DigestDomain.ENVIRONMENT_INSTANCE]
    ],
    executable_relative_path: evidence_module.RootedRelativePath,
    version: str,
    platform_tag: str,
    abi_tag: str,
    digest_registry: DecodedDigestDomainRegistry,
    hooks: CandidateRuntimeObservationHooks | None = None,
) -> CandidatePythonRuntimeObservation | BidirectionalUnestablishedAuthorityPredicate:
    """Observe a candidate POSIX runtime twice without claiming a common cutoff."""

    handle: _PosixOpenedDirectoryHandle | None = None
    try:
        platform_family: Literal["darwin", "linux"]
        if sys.platform == "darwin":
            platform_family = "darwin"
        elif sys.platform.startswith("linux"):
            platform_family = "linux"
        else:
            raise _CandidateRuntimeObservationChanged("unsupported runtime platform")
        filesystem_kind = _detect_candidate_runtime_filesystem_kind(runtime_root)
        if filesystem_kind is None:
            raise _CandidateRuntimeObservationChanged("unsupported runtime filesystem")
        if not environment_root.exists() or not runtime_root.exists():
            raise _CandidateRuntimeObservationChanged("runtime root is unavailable")
        environment_real = Path(os.path.realpath(environment_root))
        runtime_real = Path(os.path.realpath(runtime_root))
        handle = _open_owner_directory(
            directory=runtime_real,
            owner_kind=OwnerCapabilityKind.RUNTIME_INSTALLATION,
            handle_type=_PosixOpenedDirectoryHandle,
        )
        descriptor = handle.require_current_process_descriptor()
        opened_before = _candidate_root_observation(descriptor)
        first_manifest = _walk_candidate_python_runtime(
            root_descriptor=descriptor,
            runtime_root=runtime_real,
            executable_relative_path=executable_relative_path,
            version=version,
            platform_tag=platform_tag,
            abi_tag=abi_tag,
            walk_number=1,
            hooks=hooks,
        )
        first_ref = build_foundry_statement_ref(
            DigestDomain.TOOLCHAIN_RUNTIME,
            first_manifest,
        )
        second_manifest = _walk_candidate_python_runtime(
            root_descriptor=descriptor,
            runtime_root=runtime_real,
            executable_relative_path=executable_relative_path,
            version=version,
            platform_tag=platform_tag,
            abi_tag=abi_tag,
            walk_number=2,
            hooks=hooks,
        )
        second_ref = build_foundry_statement_ref(
            DigestDomain.TOOLCHAIN_RUNTIME,
            second_manifest,
        )
        opened_after = _candidate_root_observation(descriptor)
        flags = os.O_RDONLY | os.O_CLOEXEC
        flags |= getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        reopened_descriptor = os.open(runtime_real, flags)
        try:
            reopened = _candidate_root_observation(reopened_descriptor)
        finally:
            os.close(reopened_descriptor)
        root_identity = evidence_module.PosixRuntimeRootIdentityStatement(
            schema_version="polisyos.foundry.posix-runtime-root-identity.v1",
            predicate_class="candidate_observation",
            identity_profile="posix-open-directory-apfs-ext4-v1",
            platform_family=platform_family,
            filesystem_kind=filesystem_kind,
            environment_creation_nonce=environment_creation_nonce,
            environment_root_path_hash=domain_digest(
                DigestDomain.TOOLCHAIN_RUNTIME_ROOT_PATH,
                os.fsencode(environment_real),
            ),
            runtime_root_path_hash=domain_digest(
                DigestDomain.TOOLCHAIN_RUNTIME_ROOT_PATH,
                os.fsencode(runtime_real),
            ),
            opened_before=opened_before,
            opened_after_enumeration=opened_after,
            reopened_by_path=reopened,
            first_walk_manifest_ref=first_ref,
            second_walk_manifest_ref=second_ref,
        )
        return CandidatePythonRuntimeObservation(
            root_identity=root_identity,
            root_token=build_foundry_statement_ref(
                DigestDomain.TOOLCHAIN_RUNTIME_ROOT_TOKEN,
                root_identity,
            ).semantic_hash,
            first_manifest=first_manifest,
            second_manifest=second_manifest,
        )
    except (
        OSError,
        ValueError,
        OwnerCapabilityFault,
        _CandidateRuntimeObservationChanged,
    ):
        return _candidate_runtime_not_established(digest_registry)
    finally:
        if handle is not None:
            handle.close_owner_resource()


@dataclass(frozen=True, slots=True)
class _CanonicalFoundrySourceAuthorityPayload:
    source_root: _PosixOpenedDirectoryHandle
    authority_ref: FoundryRecordRef[Literal[DigestDomain.CANONICAL_SOURCE]]
    statement: CanonicalFoundrySourceAuthorityStatement
    digest_registry: DecodedDigestDomainRegistry

    def __post_init__(self) -> None:
        if self.statement.digest_registry_ref != self.digest_registry.registry_ref:
            raise ValueError("source authority and decoded digest registry disagree")


def _unestablished_from_registry(
    source_authority: _CanonicalFoundrySourceAuthorityPayload,
    predicate_id: AuthorityPredicateId,
) -> BidirectionalUnestablishedAuthorityPredicate:
    """Construct one exact missing-evidence branch from owner-bound registry data."""

    matches = tuple(
        row
        for row in source_authority.digest_registry.statement.predicates
        if row.predicate_id is predicate_id
    )
    if len(matches) != 1 or not isinstance(
        matches[0], BidirectionalAuthorityPredicateSpec
    ):
        raise ValueError("predicate does not have one bidirectional registry row")
    spec = matches[0]
    requirement = spec.not_established_requirement
    if not isinstance(requirement, MissingEvidenceDomainsRequirement):
        raise ValueError("predicate does not declare missing evidence domains")
    return BidirectionalUnestablishedAuthorityPredicate(
        branch_shape="bidirectional",
        status="not_established",
        predicate_registry_ref=source_authority.digest_registry.registry_ref,
        predicate_spec=spec,
        predicate_id=predicate_id,
        predicate_class="not_established",
        failure_code=spec.not_established_code,
        missing_domains=requirement.missing_domains,
    )


def _rejected_from_registry(
    source_authority: _CanonicalFoundrySourceAuthorityPayload,
    predicate_id: AuthorityPredicateId,
    *,
    evidence_refs: tuple[FoundryRecordRef[DigestDomain], ...],
) -> RejectedAuthorityPredicate:
    """Construct one exact rejected branch from independently derived evidence."""

    matches = tuple(
        row
        for row in source_authority.digest_registry.statement.predicates
        if row.predicate_id is predicate_id
    )
    if len(matches) != 1 or not isinstance(
        matches[0], BidirectionalAuthorityPredicateSpec
    ):
        raise ValueError("predicate does not have one bidirectional registry row")
    spec = matches[0]
    return RejectedAuthorityPredicate(
        branch_shape="bidirectional",
        status="rejected",
        predicate_registry_ref=source_authority.digest_registry.registry_ref,
        predicate_spec=spec,
        predicate_id=predicate_id,
        predicate_class="recomputed",
        failure_code=spec.rejected_code,
        evidence_refs=evidence_refs,
    )


def validate_appointment_custody_pair(
    appointment: ProductionDataInputAppointmentStatement,
    custody: ProductionDataCustodyStatement,
) -> None:
    """Recompute and reconcile one appointment/custody relation.

    Signature validity is established before this pure relation check.  Two
    independently authentic statements still cannot be combined unless every
    authority-bearing relation and the custody statement ref agree exactly.
    """

    custody_ref = record_ref(
        DigestDomain.PRODUCTION_CUSTODY,
        canonical_json_bytes(custody.model_dump(mode="json")),
        schema_version=custody.schema_version,
    )
    if (
        appointment.custody_statement_ref != custody_ref
        or appointment.appointed_root != custody.institutional_root
        or appointment.appointed_custodian != custody.appointed_custodian
        or appointment.expected_manifest_ref != custody.manifest_ref
        or custody.access_mode != "read_only"
        or custody.writer_access_disposition != "denied"
    ):
        raise ValueError("appointment and custody statements do not form one relation")


def validate_appointment_requested_root(
    appointment: ProductionDataInputAppointmentStatement,
    requested_root: evidence_module.ExternalAuthorityRef[
        Literal[ExternalAuthorityKind.INSTITUTIONAL_ROOT]
    ],
) -> None:
    """Reject a request for a different institutional root before opening it."""

    if requested_root != appointment.appointed_root:
        raise ValueError("requested institutional root is not the appointed root")


def validate_root_access_attestation(
    challenge: ProductionDataRootAccessChallenge,
    attestation: RootAccessAttestationStatement,
) -> None:
    """Bind one attestation to the exact fresh challenge and manifest."""

    challenge_ref = record_ref(
        DigestDomain.ROOT_CHALLENGE,
        canonical_json_bytes(challenge.model_dump(mode="json")),
        schema_version=challenge.schema_version,
    )
    if (
        attestation.challenge_ref != challenge_ref
        or attestation.request_ref != challenge.request_ref
        or attestation.challenge_nonce != challenge.challenge_nonce
        or attestation.institutional_root != challenge.expected_root
        or attestation.observed_manifest_ref != challenge.expected_manifest_ref
        or attestation.mount_resolution_ref != challenge.mount_resolution_ref
        or attestation.access_mode != "read_only"
        or attestation.writer_access_disposition != "denied"
    ):
        raise ValueError("root-access attestation does not satisfy its challenge")


def validate_trust_resolution_receipt(
    receipt: evidence_module.TrustResolutionReceiptStatement,
    material: evidence_module.TrustMaterialStatement,
) -> None:
    """Recompute the exact eligible-key denominator for one trust role."""

    material_ref = record_ref(
        DigestDomain.TRUST_MATERIAL,
        canonical_json_bytes(material.model_dump(mode="json")),
        schema_version=material.schema_version,
    )
    if receipt.trust_material_ref != material_ref:
        raise ValueError("trust resolution receipt does not bind its trust material")
    expected = tuple(
        sorted(
            (
                key.key_id,
                key.signer_identity,
                receipt.required_role,
            )
            for key in material.keys
            if receipt.required_role in key.roles
        )
    )
    observed = tuple(
        (
            key.key_id,
            key.signer_identity,
            key.selected_role,
        )
        for key in receipt.eligible_keys
    )
    if not expected or observed != expected:
        raise ValueError("eligible trust key denominator does not match material")
    material_revocations = tuple(
        ref.artifact_id for ref in material.revocation_refs
    )
    receipt_revocations = tuple(
        row.revocation_ref.artifact_id for row in receipt.revocation_dispositions
    )
    if receipt_revocations != material_revocations:
        raise ValueError("trust revocation denominator does not match material")


def validate_trust_bootstrap_basis(
    snapshot: FoundryTrustBootstrapSnapshot,
    *,
    expected_source_ref: FoundryRecordRef[
        Literal[DigestDomain.CANONICAL_SOURCE]
    ],
    expected_cutoff: GitCommitId,
) -> None:
    """Prevent a sealed bootstrap from moving between source bases."""

    if (
        snapshot.source_authority_ref != expected_source_ref
        or snapshot.source_freeze_commit != expected_cutoff
    ):
        raise ValueError("trust bootstrap basis differs from source/cutoff")


def validate_admitted_uv_executable(
    admission: MethodCatalogProfileAdmission,
    observed_bytes: bytes,
) -> None:
    """Rehash the exact uv bytes against the Foundry-owned admission."""

    if type(observed_bytes) is not bytes:
        raise TypeError("uv executable evidence must be exact bytes")
    observed = record_ref(
        DigestDomain.TOOLCHAIN_EXECUTABLE,
        observed_bytes,
        schema_version=admission.uv_executable_ref.schema_version,
    )
    if observed != admission.uv_executable_ref:
        raise ValueError("uv executable does not match the owner admission")


def validate_exact_signed_record(
    binding: PersistedSignedFoundryRecordBinding[DigestDomain],
    evidence: ExactSignedArtifactEvidenceStatement,
) -> None:
    """Content-bind the retained exact triple before semantic parsing."""

    expected_binding_ref = build_foundry_statement_ref(
        DigestDomain.SIGNED_RECORD_BINDING,
        binding.statement,
    )
    expected_evidence_ref = build_foundry_statement_ref(
        DigestDomain.SIGNED_EVIDENCE,
        evidence,
    )
    record = binding.statement.record_ref
    expected_record = record_ref(
        record.semantic_hash.domain,
        evidence.signed_blob_bytes,
        schema_version=record.schema_version,
    )
    if (
        binding.binding_ref != expected_binding_ref
        or binding.statement.signed_evidence_ref != expected_evidence_ref
        or record != expected_record
        or not evidence.exact_manifest_bytes
        or not evidence.detached_signature_bytes
    ):
        raise ValueError("signed evidence triple is not content-bound")


def validate_capsule_signed_binding_index(
    capsule: PersistedFoundryDependencyAuthorityCapsule,
    index: PersistedSignedRecordBindingIndex,
    bindings: tuple[PersistedSignedFoundryRecordBinding[DigestDomain], ...],
    *,
    digest_registry: DecodedDigestDomainRegistry,
) -> None:
    """Reconcile the capsule's direct signed-record graph as one bijection."""

    row_by_domain = {
        row.domain_id: row for row in digest_registry.statement.domains
    }
    if set(row_by_domain) != set(DigestDomain):
        raise ValueError("signed binding graph uses an incomplete digest registry")
    infrastructure = {
        DigestDomain.CAPSULE,
        DigestDomain.SIGNED_EVIDENCE,
        DigestDomain.SIGNED_RECORD_BINDING,
        DigestDomain.SIGNED_BINDING_INDEX,
    }
    if any(
        row_by_domain[domain].signature_requirement != "unsigned"
        or row_by_domain[domain].required_signer_role is not None
        for domain in infrastructure
    ):
        raise ValueError("recursive signed infrastructure is forbidden")
    statement = capsule.statement
    direct_refs: tuple[FoundryRecordRef[DigestDomain], ...] = (
        cast("FoundryRecordRef[DigestDomain]", statement.source_authority_ref),
        cast("FoundryRecordRef[DigestDomain]", statement.profile_admission_ref),
        cast("FoundryRecordRef[DigestDomain]", statement.appointment_ref),
        cast("FoundryRecordRef[DigestDomain]", statement.environment_receipt_ref),
        *cast(
            "tuple[FoundryRecordRef[DigestDomain], ...]",
            statement.selected_artifact_refs,
        ),
        *cast(
            "tuple[FoundryRecordRef[DigestDomain], ...]",
            statement.build_lineage_refs,
        ),
        *cast(
            "tuple[FoundryRecordRef[DigestDomain], ...]",
            statement.trust_material_refs,
        ),
    )
    expected_records = tuple(
        sorted(
            (
                ref
                for ref in direct_refs
                if row_by_domain[ref.semantic_hash.domain].signature_requirement
                == "signed"
            ),
            key=lambda ref: (
                ref.semantic_hash.domain.value,
                ref.artifact_id,
            ),
        )
    )
    actual_records = tuple(
        sorted(
            (binding.statement.record_ref for binding in bindings),
            key=lambda ref: (
                ref.semantic_hash.domain.value,
                ref.artifact_id,
            ),
        )
    )
    sorted_bindings = tuple(
        sorted(bindings, key=lambda row: row.binding_ref.artifact_id)
    )
    if (
        statement.signed_binding_index_ref != index.index_ref
        or statement.source_authority_ref != index.statement.source_authority_ref
        or index.index_ref
        != build_foundry_statement_ref(
            DigestDomain.SIGNED_BINDING_INDEX,
            index.statement,
        )
        or index.statement.binding_refs
        != tuple(row.binding_ref for row in sorted_bindings)
        or bindings != sorted_bindings
        or len({row.binding_ref.artifact_id for row in bindings}) != len(bindings)
        or expected_records != actual_records
    ):
        raise ValueError("signed binding graph is not an exact acyclic bijection")
    for binding in bindings:
        domain = binding.statement.record_ref.semantic_hash.domain
        registry_row = row_by_domain[domain]
        if (
            binding.binding_ref
            != build_foundry_statement_ref(
                DigestDomain.SIGNED_RECORD_BINDING,
                binding.statement,
            )
            or registry_row.signature_requirement != "signed"
            or binding.statement.required_role is not registry_row.required_signer_role
        ):
            raise ValueError("signed binding graph contains an invalid binding row")


@_fieldless_owner_token
class CanonicalFoundrySourceAuthority:
    pass


@dataclass(frozen=True, slots=True)
class _ResolvedPythonRuntimeInstallationPayload:
    persisted: PersistedPythonRuntimeInstallation
    opened_runtime_root: _PosixOpenedDirectoryHandle


@_fieldless_owner_token
class ResolvedPythonRuntimeInstallation:
    pass


@dataclass(frozen=True, slots=True)
class _VerifiedPythonRuntimePayload:
    observed_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME_OBSERVED]]
    verification_ref: FoundryRecordRef[
        Literal[DigestDomain.TOOLCHAIN_RUNTIME_VERIFICATION]
    ]


@_fieldless_owner_token
class VerifiedPythonRuntime:
    pass


@dataclass(frozen=True, slots=True)
class _VerifiedFoundryTrustBootstrapPayload:
    snapshot: FoundryTrustBootstrapSnapshot


@_fieldless_owner_token
class VerifiedFoundryTrustBootstrap:
    pass


@dataclass(frozen=True, slots=True)
class _ResolvedFoundryTrustPayload:
    receipt: PersistedTrustResolutionReceipt
    verifier: core_artifacts.Ed25519Verifier


@_fieldless_owner_token
class ResolvedFoundryTrust:
    pass


@dataclass(frozen=True, slots=True)
class _VerifiedProductionDataAppointmentPayload:
    appointment_binding_ref: FoundryRecordRef[
        Literal[DigestDomain.SIGNED_RECORD_BINDING]
    ]
    custody_binding_ref: FoundryRecordRef[
        Literal[DigestDomain.SIGNED_RECORD_BINDING]
    ]
    appointment_ref: FoundryRecordRef[Literal[DigestDomain.PRODUCTION_APPOINTMENT]]
    custody_ref: FoundryRecordRef[Literal[DigestDomain.PRODUCTION_CUSTODY]]
    appointment_statement: ProductionDataInputAppointmentStatement
    custody_statement: ProductionDataCustodyStatement


@_fieldless_owner_token
class VerifiedProductionDataAppointment:
    pass


@dataclass(slots=True, weakref_slot=True, eq=False, init=False)
class _InstitutionalRootHandle:
    descriptor: int
    creator_pid: int
    owner_kind: Literal[OwnerCapabilityKind.PRODUCTION_MOUNT]
    open_generation: int
    opened_identity: _OpenedDescriptorIdentity

    def require_current_process_descriptor(self) -> int:
        return _require_owner_descriptor(self)

    def owner_resource_lease_key(self) -> _OwnerResourceKey:
        return _owner_descriptor_lease_key(self)

    def close_owner_resource(self) -> None:
        _close_owner_descriptor(self)


@dataclass(frozen=True, slots=True)
class _ResolvedProductionDataMountPayload:
    receipt_ref: FoundryRecordRef[Literal[DigestDomain.ROOT_MOUNT_RESOLUTION]]
    statement: ProductionDataMountResolutionStatement
    opened_root_handle: _InstitutionalRootHandle


@_fieldless_owner_token
class ResolvedProductionDataMount:
    pass


@dataclass(frozen=True, slots=True)
class _VerifiedProductionDataRootAccessPayload:
    statement: RootAccessAttestationStatement
    attestation_ref: FoundryRecordRef[Literal[DigestDomain.ROOT_ACCESS]]
    signed_binding_ref: FoundryRecordRef[
        Literal[DigestDomain.SIGNED_RECORD_BINDING]
    ]
    predicate_class: Literal["independently_reconciled"]


@_fieldless_owner_token
class VerifiedProductionDataRootAccess:
    pass


@dataclass(frozen=True, slots=True)
class _VerifiedSignedFoundryRecordPayload:
    record_domain: DigestDomain
    binding: PersistedSignedFoundryRecordBinding[DigestDomain]
    exact_record_bytes: bytes


@_fieldless_owner_token
class VerifiedSignedFoundryRecord:
    pass


@dataclass(frozen=True, slots=True)
class _VerifiedSignedGraphRecord:
    record_domain: DigestDomain
    binding_ref: FoundryRecordRef[Literal[DigestDomain.SIGNED_RECORD_BINDING]]
    record: VerifiedSignedFoundryRecord


@dataclass(frozen=True, slots=True)
class _VerifiedCapsuleSignedGraphPayload:
    index: PersistedSignedRecordBindingIndex
    verified_records: tuple[_VerifiedSignedGraphRecord, ...]


@_fieldless_owner_token
class VerifiedCapsuleSignedGraph:
    pass


PythonRuntimeInstallationResult = (
    ResolvedPythonRuntimeInstallation
    | RejectedAuthorityPredicate
    | UnestablishedAuthorityPredicate
)
PythonRuntimeObservationResult = (
    VerifiedPythonRuntime | RejectedAuthorityPredicate | UnestablishedAuthorityPredicate
)
TrustBootstrapResult = (
    VerifiedFoundryTrustBootstrap
    | RejectedAuthorityPredicate
    | UnestablishedAuthorityPredicate
)
TrustResolutionResult = (
    ResolvedFoundryTrust | RejectedAuthorityPredicate | UnestablishedAuthorityPredicate
)
ProductionDataAppointmentResolutionResult = (
    VerifiedProductionDataAppointment
    | RejectedAuthorityPredicate
    | UnestablishedAuthorityPredicate
)
ProductionDataMountResolutionResult = (
    ResolvedProductionDataMount
    | RejectedAuthorityPredicate
    | UnestablishedAuthorityPredicate
)
RootAccessAttestationResult = (
    VerifiedProductionDataRootAccess
    | RejectedAuthorityPredicate
    | UnestablishedAuthorityPredicate
)
SignedRecordVerificationResult = (
    VerifiedSignedFoundryRecord
    | RejectedAuthorityPredicate
    | UnestablishedAuthorityPredicate
)
CapsuleSignedGraphVerificationResult = (
    VerifiedCapsuleSignedGraph
    | RejectedAuthorityPredicate
    | UnestablishedAuthorityPredicate
)


class PythonRuntimeInstallationAuthority(Protocol):
    def attest_after_install(
        self,
        *,
        environment_root: Path,
        admission: PythonRuntimeAdmission,
        environment_creation_nonce: DomainDigest[
            Literal[DigestDomain.ENVIRONMENT_INSTANCE]
        ],
    ) -> PythonRuntimeInstallationResult: ...

    def resolve_installed_root(
        self,
        *,
        environment_root: Path,
        receipt_ref: FoundryRecordRef[
            Literal[DigestDomain.TOOLCHAIN_RUNTIME_INSTALLATION]
        ],
        admission: PythonRuntimeAdmission,
    ) -> PythonRuntimeInstallationResult: ...


class PythonRuntimeObserver(Protocol):
    def observe_and_verify(
        self,
        *,
        environment_root: Path,
        installation: ResolvedPythonRuntimeInstallation,
        admission: PythonRuntimeAdmission,
    ) -> PythonRuntimeObservationResult: ...


class GitCommitAncestryAuthority(Protocol):
    def compare(
        self,
        *,
        candidate: GitCommitId,
        source_cutoff: GitCommitId,
    ) -> GitCommitRelation | MissingPredicateEvidence: ...


class FoundryTrustResolver(Protocol):
    def resolve(
        self,
        *,
        policy_ref: FoundryRecordRef[Literal[DigestDomain.TRUST_POLICY]],
        required_role: TrustRole,
    ) -> TrustResolutionResult: ...


class ProductionDataAppointmentAuthority(Protocol):
    def resolve(
        self,
        *,
        source_authority: CanonicalFoundrySourceAuthority,
        capsule: PersistedFoundryDependencyAuthorityCapsule,
        signed_graph: VerifiedCapsuleSignedGraph,
    ) -> ProductionDataAppointmentResolutionResult: ...


class ProductionDataMountResolver(Protocol):
    def resolve(
        self,
        *,
        requested_root: Path,
        appointment: VerifiedProductionDataAppointment,
    ) -> ProductionDataMountResolutionResult: ...

    def read_manifest(
        self,
        *,
        mount: ResolvedProductionDataMount,
    ) -> (
        ProductionDataManifestInput
        | RejectedAuthorityPredicate
        | UnestablishedAuthorityPredicate
    ): ...


class ProductionDataRootAccessAttestor(Protocol):
    def attest(
        self,
        *,
        mount: ResolvedProductionDataMount,
        challenge: ProductionDataRootAccessChallenge,
    ) -> RootAccessAttestationResult: ...


class FoundryBootstrapEvidencePort(Protocol):
    """Read-only CAS transport; it neither decides trust nor writes."""

    def load_capsule_raw(self) -> PersistedFoundryDependencyAuthorityCapsule: ...

    def load_binding_index_raw(
        self,
        *,
        index_ref: FoundryRecordRef[Literal[DigestDomain.SIGNED_BINDING_INDEX]],
    ) -> PersistedSignedRecordBindingIndex: ...

    def load_binding_raw(
        self,
        *,
        binding_ref: FoundryRecordRef[Literal[DigestDomain.SIGNED_RECORD_BINDING]],
    ) -> PersistedSignedFoundryRecordBinding[DigestDomain]: ...

    def load_exact_evidence_raw(
        self,
        *,
        evidence_ref: FoundryRecordRef[Literal[DigestDomain.SIGNED_EVIDENCE]],
    ) -> ExactSignedArtifactEvidenceStatement: ...


class FoundrySourceTrustBootstrapper(Protocol):
    def bootstrap(
        self,
        *,
        source_authority: CanonicalFoundrySourceAuthority,
        evidence: FoundryBootstrapEvidencePort,
    ) -> TrustBootstrapResult: ...


class CanonicalSignedRecordRepository(Protocol):
    """Exact signed triples plus their complete content-bound binding graph."""

    def import_and_bind(
        self,
        *,
        record_ref: FoundryRecordRef[DigestDomain],
        evidence: ExactSignedArtifactEvidenceStatement,
        required_role: TrustRole,
        verification_basis: SignedRecordVerificationBasis,
        source_authority: CanonicalFoundrySourceAuthority,
    ) -> SignedRecordVerificationResult: ...

    def persist_binding_index(
        self,
        *,
        source_authority_ref: FoundryRecordRef[
            Literal[DigestDomain.CANONICAL_SOURCE]
        ],
        bindings: Sequence[PersistedSignedFoundryRecordBinding[DigestDomain]],
    ) -> PersistedSignedRecordBindingIndex: ...

    def load_and_verify_binding(
        self,
        *,
        binding_ref: FoundryRecordRef[
            Literal[DigestDomain.SIGNED_RECORD_BINDING]
        ],
        expected_record_domain: DigestDomain,
        source_authority: CanonicalFoundrySourceAuthority,
    ) -> SignedRecordVerificationResult: ...

    def verify_capsule_signed_graph(
        self,
        *,
        capsule: PersistedFoundryDependencyAuthorityCapsule,
        source_authority: CanonicalFoundrySourceAuthority,
    ) -> CapsuleSignedGraphVerificationResult: ...


class FoundryDependencyAuthorityEvidenceRepository(Protocol):
    def load_capsule(self) -> PersistedFoundryDependencyAuthorityCapsule: ...

    def signed_records(self) -> CanonicalSignedRecordRepository: ...

    def read_blob(self, *, record_ref: FoundryRecordRef[DigestDomain]) -> bytes: ...


class MethodCatalogDependencyAuthority(Protocol):
    """Resolve the complete current negative-only result union."""

    def resolve(
        self,
        request: MethodCatalogDependencyAuthorityRequest,
    ) -> MethodCatalogDependencyAuthorityResult: ...


def _persistence_gap() -> NegativeResultPersistenceDisposition:
    return NegativeResultPersistenceDisposition(
        status="not_established",
        missing_capability="owner_resolved_resolution_receipt_store",
        missing_capability_state="absent/unallocated",
    )


def _pre_source_statement(
    request: MethodCatalogDependencyAuthorityRequest,
) -> DependencyAuthorityPreSourceRequestStatement:
    return DependencyAuthorityPreSourceRequestStatement(
        schema_version="polisyos.foundry.dependency-pre-source-request.v1",
        authority_purpose=request.authority_purpose,
        expected_source_freeze_commit=request.expected_source_freeze_commit,
        production_data_request_token=DomainDigest(
            domain=DigestDomain.ROOT_MOUNT_REQUEST,
            value=_path_token(request.production_data_root),
        ),
        environment_request_token=DomainDigest(
            domain=DigestDomain.ENVIRONMENT_INSTANCE,
            value=_path_token(request.environment_root),
        ),
    )


def _path_token(path: AbsoluteRequestPath) -> str:
    from polisyos.foundry.methods.catalog.dependency_evidence import sha256_wire

    return sha256_wire(str(path.value).encode("utf-8"))


def _source_not_established(
    request: MethodCatalogDependencyAuthorityRequest,
) -> SourceUnestablishedMethodCatalogDependencyProfile:
    return SourceUnestablishedMethodCatalogDependencyProfile(
        result_kind=NegativeDependencyAuthorityResultKind.SOURCE_NOT_ESTABLISHED,
        status="not_established",
        persistence=_persistence_gap(),
        request=_pre_source_statement(request),
        failure=SourceFreezeUnestablishedPredicate(
            status="not_established",
            predicate_id=AuthorityPredicateId.SOURCE_FREEZE,
            predicate_class="not_established",
            failure_code=AuthorityFailureCode.SOURCE_NOT_ESTABLISHED,
            missing_domains=(DigestDomain.CANONICAL_SOURCE,),
        ),
    )


def _git(*args: str) -> str:
    git_bin = shutil.which("git")
    if git_bin is None or not Path(git_bin).is_absolute():
        raise OSError("git executable is not resolvable to an absolute path")
    completed = subprocess.run(  # noqa: S603 - resolved executable; argv is owner-fixed
        [git_bin, *args],
        cwd=_GIT_ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return completed.stdout.strip()


def _git_bytes(*args: str) -> bytes:
    git_bin = shutil.which("git")
    if git_bin is None or not Path(git_bin).is_absolute():
        raise OSError("git executable is not resolvable to an absolute path")
    completed = subprocess.run(  # noqa: S603 - resolved executable; argv is owner-fixed
        [git_bin, *args],
        cwd=_GIT_ROOT,
        check=True,
        capture_output=True,
        timeout=10,
    )
    return completed.stdout


def _authority_source_is_bound_to_head() -> bool:
    """Require every decisive source byte to be tracked, clean and attached."""

    symbolic_head = _git("symbolic-ref", "-q", "HEAD")
    if not symbolic_head.startswith("refs/heads/"):
        return False
    status = _git(
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--",
        *_AUTHORITY_SOURCE_PATHS,
    )
    if status:
        return False
    for relative_path in _AUTHORITY_SOURCE_PATHS:
        tracked = _git("ls-files", "--error-unmatch", "--", relative_path)
        if tracked != relative_path:
            return False
        worktree_bytes = (_GIT_ROOT / relative_path).read_bytes()
        if worktree_bytes != _git_bytes("show", f"HEAD:{relative_path}"):
            return False
    return True


def _validate_authority_registry(
    raw: bytes,
    *,
    profile_id: str,
    declaration_artifact_id: str,
    declaration_semantic_hash: str,
) -> bytes:
    """Validate the exact data-owned purpose row and explicit absent capability."""

    wire = tomllib.loads(raw.decode("utf-8"))
    if set(wire) != {
        "schema_version",
        "purpose_admissions",
        "toolchain_admissions",
        "launcher_profiles",
        "root_keys",
        "production_data_trust_policies",
        "capabilities",
    }:
        raise ValueError("authority registry has unknown or missing top-level fields")
    if wire["schema_version"] != "polisyos.foundry.dependency-authority-registry.v1":
        raise ValueError("authority registry schema mismatch")
    admissions = wire["purpose_admissions"]
    if type(admissions) is not list or len(admissions) != 1:
        raise ValueError("authority purpose must resolve to exactly one admission")
    admission = admissions[0]
    if set(admission) != {
        "authority_purpose",
        "profile_id",
        "declaration_artifact_id",
        "declaration_semantic_hash",
        "predicate_class",
    } or admission != {
        "authority_purpose": "n8_method_catalog_reconstruction",
        "profile_id": profile_id,
        "declaration_artifact_id": declaration_artifact_id,
        "declaration_semantic_hash": declaration_semantic_hash,
        "predicate_class": "recomputed",
    }:
        raise ValueError("authority purpose admission mismatch")
    for empty_denominator in (
        "toolchain_admissions",
        "launcher_profiles",
        "root_keys",
        "production_data_trust_policies",
    ):
        if wire[empty_denominator] != []:
            raise ValueError(f"unappointed authority denominator: {empty_denominator}")
    capabilities = wire["capabilities"]
    if type(capabilities) is not list or capabilities != [
        {
            "capability_id": "owner_enforced_runtime_subtree_cutoff",
            "state": "absent/unallocated",
        },
        {
            "capability_id": "owner_resolved_resolution_receipt_store",
            "state": "absent/unallocated",
        },
        {
            "capability_id": "platform_toolchain_admission",
            "state": "absent/unallocated",
        },
        {
            "capability_id": "production_data_trust_policy",
            "state": "absent/unallocated",
        },
    ]:
        raise ValueError("authority capability denominator mismatch")
    return canonical_json_bytes(wire)


CanonicalFoundrySourceResolution = (
    CanonicalFoundrySourceAuthority
    | SourceRejectedMethodCatalogDependencyProfile
    | SourceUnestablishedMethodCatalogDependencyProfile
)


class CanonicalFoundrySourceAuthorityResolver(Protocol):
    def resolve(
        self,
        *,
        request: MethodCatalogDependencyAuthorityRequest,
    ) -> CanonicalFoundrySourceResolution: ...


class _ProductionCanonicalFoundrySourceAuthorityResolver(
    _OwnerBoundaryBase,
    CanonicalFoundrySourceAuthorityResolver,
):
    def resolve(
        self,
        *,
        request: MethodCatalogDependencyAuthorityRequest,
    ) -> (
        _CanonicalFoundrySourceAuthorityPayload
        | SourceRejectedMethodCatalogDependencyProfile
        | SourceUnestablishedMethodCatalogDependencyProfile
    ):
        pre_source = _pre_source_statement(request)
        try:
            observed_root = Path(_git("rev-parse", "--show-toplevel")).resolve()
            if observed_root != _GIT_ROOT.resolve():
                return _source_not_established(request)
            observed_commit = _git("rev-parse", "HEAD")
            observed_tree = _git("rev-parse", "HEAD^{tree}")
            expected_tree = _git(
                "rev-parse", f"{request.expected_source_freeze_commit}^{{tree}}"
            )
        except (OSError, subprocess.SubprocessError, ValueError):
            return _source_not_established(request)
        resolved_request = DependencyAuthorityResolvedSourceRequestStatement(
            schema_version="polisyos.foundry.dependency-resolved-source-request.v1",
            pre_source_request=pre_source,
            expected_source_tree_id=expected_tree,
        )
        if (
            observed_commit != request.expected_source_freeze_commit
            or observed_tree != expected_tree
        ):
            return SourceRejectedMethodCatalogDependencyProfile(
                result_kind=NegativeDependencyAuthorityResultKind.SOURCE_REJECTED,
                status="rejected",
                persistence=_persistence_gap(),
                request=resolved_request,
                failure=SourceFreezeRejectedPredicate(
                    status="rejected",
                    predicate_id=AuthorityPredicateId.SOURCE_FREEZE,
                    predicate_class="recomputed",
                    failure_code=AuthorityFailureCode.SOURCE_FREEZE_MISMATCH,
                    expected_source_freeze_commit=request.expected_source_freeze_commit,
                    expected_source_tree_id=expected_tree,
                    owner_observed_head_commit=observed_commit,
                    owner_observed_tree_id=observed_tree,
                    observation_producer="canonical_module_git_recompute_v1",
                ),
            )
        try:
            if not _authority_source_is_bound_to_head():
                return _source_not_established(request)
        except (OSError, subprocess.SubprocessError, ValueError):
            return _source_not_established(request)
        try:
            profile_registry_raw = _PROFILE_REGISTRY_PATH.read_bytes()
            profile_registry = load_dependency_profile_registry(_PROFILE_REGISTRY_PATH)
            authority_registry_raw = _AUTHORITY_REGISTRY_PATH.read_bytes()
            digest_registry = load_digest_domain_registry(_DIGEST_REGISTRY_PATH)
            declaration = profile_registry.declarations[0]
            declaration_identity = declaration_ref(declaration)
            authority_registry_canonical = _validate_authority_registry(
                authority_registry_raw,
                profile_id=declaration.profile_id,
                declaration_artifact_id=declaration_identity.artifact_id,
                declaration_semantic_hash=declaration_identity.semantic_hash.value,
            )
            profile_registry_ref = FoundryRecordRef(
                artifact_id=sha256_wire(profile_registry_raw),
                semantic_hash=domain_digest(
                    DigestDomain.PROFILE_REGISTRY,
                    canonical_json_bytes(profile_registry.model_dump(mode="json")),
                ),
                schema_version=profile_registry.schema_version,
            )
            authority_registry_ref = FoundryRecordRef(
                artifact_id=sha256_wire(authority_registry_raw),
                semantic_hash=domain_digest(
                    DigestDomain.AUTHORITY_REGISTRY,
                    authority_registry_canonical,
                ),
                schema_version="polisyos.foundry.dependency-authority-registry.v1",
            )
            statement = CanonicalFoundrySourceAuthorityStatement(
                schema_version="polisyos.foundry.canonical-source-authority.v1",
                source_freeze_commit=observed_commit,
                source_tree_id=observed_tree,
                profile_registry_ref=profile_registry_ref,
                authority_registry_ref=authority_registry_ref,
                digest_registry_ref=digest_registry.registry_ref,
            )
            statement_bytes = canonical_json_bytes(statement.model_dump(mode="json"))
            source_ref = record_ref(
                DigestDomain.CANONICAL_SOURCE,
                statement_bytes,
                schema_version=statement.schema_version,
            )
        except (OSError, UnicodeDecodeError, ValueError, tomllib.TOMLDecodeError):
            return _source_not_established(request)
        source_root = _open_owner_directory(
            directory=_GIT_ROOT,
            owner_kind=OwnerCapabilityKind.CANONICAL_SOURCE,
            handle_type=_PosixOpenedDirectoryHandle,
        )
        try:
            payload = _CanonicalFoundrySourceAuthorityPayload(
                source_root=source_root,
                authority_ref=source_ref,
                statement=statement,
                digest_registry=digest_registry,
            )
            return _mint_owner_capability(_CANONICAL_SOURCE_SPEC, payload)
        except BaseException:
            source_root.close_owner_resource()
            raise


class RuntimeSubtreeCutoffAuthority(Protocol):
    def preflight(self) -> RuntimeCutoffUnestablishedPredicate: ...


class _NoRuntimeSubtreeCutoffAuthority(
    _OwnerBoundaryBase, RuntimeSubtreeCutoffAuthority
):
    """Explicit current owner disposition; no observation can promote it."""

    def preflight(self) -> RuntimeCutoffUnestablishedPredicate:
        return RuntimeCutoffUnestablishedPredicate(
            status="not_established",
            predicate_id=AuthorityPredicateId.RUNTIME_SUBTREE_CUTOFF,
            predicate_class="not_established",
            failure_code=AuthorityFailureCode.RUNTIME_SUBTREE_CUTOFF_NOT_ESTABLISHED,
            missing_capability="owner_enforced_runtime_subtree_cutoff",
            missing_capability_state="absent/unallocated",
            candidate_runtime_evidence=CandidateRuntimeEvidenceNotRequested(
                status="not_requested",
                reason="owner_enforced_runtime_subtree_cutoff_absent",
            ),
        )


class _ProductionFoundrySourceTrustBootstrapper(
    _OwnerBoundaryBase,
    FoundrySourceTrustBootstrapper,
):
    """B0 reference owner; current tracked registry appoints no root key."""

    def bootstrap(
        self,
        *,
        source_authority: CanonicalFoundrySourceAuthority,
        evidence: FoundryBootstrapEvidencePort,
    ) -> TrustBootstrapResult:
        del evidence
        with _unwrap_owner_capability(
            source_authority,
            _CANONICAL_SOURCE_SPEC,
        ) as source:
            return _unestablished_from_registry(
                source,
                AuthorityPredicateId.TRUST_SIGNATURE,
            )


class _ProductionGitCommitAncestryAuthority(
    _OwnerBoundaryBase,
    GitCommitAncestryAuthority,
):
    def __init__(
        self,
        *,
        source_authority: _CanonicalFoundrySourceAuthorityPayload,
    ) -> None:
        self._source_authority = source_authority
        self._git_root = _GIT_ROOT

    def compare(
        self,
        *,
        candidate: GitCommitId,
        source_cutoff: GitCommitId,
    ) -> GitCommitRelation | MissingPredicateEvidence:
        if candidate == source_cutoff:
            return GitCommitRelation.EQUAL
        git_bin = shutil.which("git")
        if git_bin is None or not Path(git_bin).is_absolute():
            return MissingPredicateEvidence(
                kind="not_established",
                predicate_id=AuthorityPredicateId.TRUST_SIGNATURE,
                code=AuthorityFailureCode.TRUST_NOT_ESTABLISHED,
                missing_domains=(DigestDomain.TRUST_REVOCATION,),
                predicate_class="not_established",
            )

        def is_ancestor(older: str, newer: str) -> bool | None:
            completed = subprocess.run(  # noqa: S603 - resolved fixed executable
                [git_bin, "merge-base", "--is-ancestor", older, newer],
                cwd=self._git_root,
                check=False,
                capture_output=True,
                timeout=10,
            )
            if completed.returncode == 0:
                return True
            if completed.returncode == 1:
                return False
            return None

        forward = is_ancestor(candidate, source_cutoff)
        reverse = is_ancestor(source_cutoff, candidate)
        if forward is None or reverse is None:
            return MissingPredicateEvidence(
                kind="not_established",
                predicate_id=AuthorityPredicateId.TRUST_SIGNATURE,
                code=AuthorityFailureCode.TRUST_NOT_ESTABLISHED,
                missing_domains=(DigestDomain.TRUST_REVOCATION,),
                predicate_class="not_established",
            )
        if forward:
            return GitCommitRelation.ANCESTOR
        if reverse:
            return GitCommitRelation.DESCENDANT
        return GitCommitRelation.INCOMPARABLE


class _ProductionFoundryTrustResolver(_OwnerBoundaryBase, FoundryTrustResolver):
    def __init__(
        self,
        *,
        source_authority: _CanonicalFoundrySourceAuthorityPayload,
    ) -> None:
        self._source_authority = source_authority

    def resolve(
        self,
        *,
        policy_ref: FoundryRecordRef[Literal[DigestDomain.TRUST_POLICY]],
        required_role: TrustRole,
    ) -> TrustResolutionResult:
        del policy_ref, required_role
        return _unestablished_from_registry(
            self._source_authority,
            AuthorityPredicateId.TRUST_SIGNATURE,
        )


class _ProductionDataAppointmentAuthority(
    _OwnerBoundaryBase,
    ProductionDataAppointmentAuthority,
):
    def __init__(
        self,
        *,
        source_authority: _CanonicalFoundrySourceAuthorityPayload,
    ) -> None:
        self._source_authority = source_authority

    def resolve(
        self,
        *,
        source_authority: CanonicalFoundrySourceAuthority,
        capsule: PersistedFoundryDependencyAuthorityCapsule,
        signed_graph: VerifiedCapsuleSignedGraph,
    ) -> ProductionDataAppointmentResolutionResult:
        with (
            _unwrap_owner_capability(
                source_authority,
                _CANONICAL_SOURCE_SPEC,
            ) as source,
            _unwrap_owner_capability(
                signed_graph,
                _SIGNED_GRAPH_SPEC,
            ) as graph,
        ):
            evidence_refs = (
                cast("FoundryRecordRef[DigestDomain]", capsule.statement.appointment_ref),
            )

            def rejected() -> RejectedAuthorityPredicate:
                return _rejected_from_registry(
                    source,
                    AuthorityPredicateId.PRODUCTION_APPOINTMENT,
                    evidence_refs=evidence_refs,
                )

            if (
                source is not self._source_authority
                or capsule.statement.source_authority_ref != source.authority_ref
                or graph.index.statement.source_authority_ref != source.authority_ref
            ):
                return rejected()
            appointment_rows = tuple(
                row
                for row in graph.verified_records
                if row.record_domain is DigestDomain.PRODUCTION_APPOINTMENT
            )
            if len(appointment_rows) != 1:
                return rejected()
            appointment_row = appointment_rows[0]
            try:
                with _unwrap_owner_capability(
                    appointment_row.record,
                    _SIGNED_RECORD_SPEC,
                    expected_record_domain=DigestDomain.PRODUCTION_APPOINTMENT,
                ) as appointment_record:
                    if (
                        appointment_record.binding.statement.record_ref
                        != capsule.statement.appointment_ref
                    ):
                        return rejected()
                    appointment_statement = load_strict_foundry_statement(
                        record=appointment_record.binding.statement.record_ref,
                        raw=appointment_record.exact_record_bytes,
                    )
                    if not isinstance(
                        appointment_statement,
                        ProductionDataInputAppointmentStatement,
                    ):
                        return rejected()
                    custody_rows = tuple(
                        row
                        for row in graph.verified_records
                        if row.record_domain is DigestDomain.PRODUCTION_CUSTODY
                    )
                    custody_row: _VerifiedSignedGraphRecord | None = None
                    for candidate in custody_rows:
                        with _unwrap_owner_capability(
                            candidate.record,
                            _SIGNED_RECORD_SPEC,
                            expected_record_domain=DigestDomain.PRODUCTION_CUSTODY,
                        ) as candidate_record:
                            if (
                                candidate_record.binding.statement.record_ref
                                == appointment_statement.custody_statement_ref
                            ):
                                custody_row = candidate
                                break
                    if custody_row is None:
                        return rejected()
                    with _unwrap_owner_capability(
                        custody_row.record,
                        _SIGNED_RECORD_SPEC,
                        expected_record_domain=DigestDomain.PRODUCTION_CUSTODY,
                    ) as custody_record:
                        custody_statement = load_strict_foundry_statement(
                            record=custody_record.binding.statement.record_ref,
                            raw=custody_record.exact_record_bytes,
                        )
                        if not isinstance(
                            custody_statement,
                            ProductionDataCustodyStatement,
                        ):
                            return rejected()
                        validate_appointment_custody_pair(
                            appointment_statement,
                            custody_statement,
                        )
                        return _unestablished_from_registry(
                            source,
                            AuthorityPredicateId.PRODUCTION_APPOINTMENT,
                        )
            except (OwnerCapabilityFault, ValueError):
                return rejected()


class _ProductionDataMountResolver(_OwnerBoundaryBase, ProductionDataMountResolver):
    def __init__(
        self,
        *,
        source_authority: _CanonicalFoundrySourceAuthorityPayload,
    ) -> None:
        self._source_authority = source_authority

    def resolve(
        self,
        *,
        requested_root: Path,
        appointment: VerifiedProductionDataAppointment,
    ) -> ProductionDataMountResolutionResult:
        del requested_root, appointment
        return _unestablished_from_registry(
            self._source_authority,
            AuthorityPredicateId.PRODUCTION_APPOINTMENT,
        )

    def read_manifest(
        self,
        *,
        mount: ResolvedProductionDataMount,
    ) -> (
        ProductionDataManifestInput
        | RejectedAuthorityPredicate
        | UnestablishedAuthorityPredicate
    ):
        del mount
        return _unestablished_from_registry(
            self._source_authority,
            AuthorityPredicateId.PRODUCTION_MANIFEST,
        )


class _ProductionDataRootAccessAttestor(
    _OwnerBoundaryBase,
    ProductionDataRootAccessAttestor,
):
    def __init__(
        self,
        *,
        source_authority: _CanonicalFoundrySourceAuthorityPayload,
    ) -> None:
        self._source_authority = source_authority

    def attest(
        self,
        *,
        mount: ResolvedProductionDataMount,
        challenge: ProductionDataRootAccessChallenge,
    ) -> RootAccessAttestationResult:
        del mount, challenge
        return _unestablished_from_registry(
            self._source_authority,
            AuthorityPredicateId.ROOT_ACCESS,
        )


class _ProductionPythonRuntimeInstallationAuthority(
    _OwnerBoundaryBase,
    PythonRuntimeInstallationAuthority,
):
    def __init__(
        self,
        *,
        source_authority: _CanonicalFoundrySourceAuthorityPayload,
        cutoff_authority: _NoRuntimeSubtreeCutoffAuthority,
    ) -> None:
        self._source_authority = source_authority
        self._cutoff_authority = cutoff_authority

    def attest_after_install(
        self,
        *,
        environment_root: Path,
        admission: PythonRuntimeAdmission,
        environment_creation_nonce: DomainDigest[
            Literal[DigestDomain.ENVIRONMENT_INSTANCE]
        ],
    ) -> PythonRuntimeInstallationResult:
        del environment_root, admission, environment_creation_nonce
        self._cutoff_authority.preflight()
        return _unestablished_from_registry(
            self._source_authority,
            AuthorityPredicateId.PYTHON_RUNTIME,
        )

    def resolve_installed_root(
        self,
        *,
        environment_root: Path,
        receipt_ref: FoundryRecordRef[
            Literal[DigestDomain.TOOLCHAIN_RUNTIME_INSTALLATION]
        ],
        admission: PythonRuntimeAdmission,
    ) -> PythonRuntimeInstallationResult:
        del environment_root, receipt_ref, admission
        self._cutoff_authority.preflight()
        return _unestablished_from_registry(
            self._source_authority,
            AuthorityPredicateId.PYTHON_RUNTIME,
        )


class _ProductionPythonRuntimeObserver(_OwnerBoundaryBase, PythonRuntimeObserver):
    def __init__(
        self,
        *,
        source_authority: _CanonicalFoundrySourceAuthorityPayload,
    ) -> None:
        self._source_authority = source_authority

    def observe_and_verify(
        self,
        *,
        environment_root: Path,
        installation: ResolvedPythonRuntimeInstallation,
        admission: PythonRuntimeAdmission,
    ) -> PythonRuntimeObservationResult:
        with _unwrap_owner_capability(
            installation,
            _RUNTIME_INSTALLATION_SPEC,
        ) as installation_payload:
            return _observe_and_verify_candidate_python_runtime(
                source_authority=self._source_authority,
                environment_root=environment_root,
                installation=installation_payload,
                admission=admission,
            )


def _strict_artifact_id(
    record: FoundryRecordRef[DigestDomain],
) -> core_artifacts.ArtifactID:
    artifact_id = core_artifacts.ArtifactID.model_validate(record.artifact_id)
    if str(artifact_id) != record.artifact_id:
        raise ValueError("artifact ID did not round-trip through the live wire ABI")
    return artifact_id


def _require_exact_statement_ref(
    *,
    domain: DigestDomain,
    expected_ref: FoundryRecordRef[DigestDomain],
    statement: FoundryAuthorityModel,
    raw: bytes,
    label: str,
) -> None:
    observed_ref = build_foundry_statement_ref(domain, statement)
    observed_raw = canonical_json_bytes(statement.model_dump(mode="json"))
    if observed_ref != expected_ref or observed_raw != raw:
        raise ValueError(f"{label} is not content-bound")


def _load_content_bound_capsule(
    capsule_index_path: Path,
) -> PersistedFoundryDependencyAuthorityCapsule:
    raw = capsule_index_path.read_bytes()
    capsule = PersistedFoundryDependencyAuthorityCapsule.model_validate_json(raw)
    _require_exact_statement_ref(
        domain=DigestDomain.CAPSULE,
        expected_ref=cast("FoundryRecordRef[DigestDomain]", capsule.capsule_ref),
        statement=capsule.statement,
        raw=canonical_json_bytes(capsule.statement.model_dump(mode="json")),
        label="capsule",
    )
    if raw != canonical_json_bytes(capsule.model_dump(mode="json")):
        raise ValueError("capsule wrapper is not canonical")
    return capsule


def _load_cas_statement_bytes(
    store: core_artifacts.FileSystemCAS,
    record: FoundryRecordRef[DigestDomain],
) -> bytes:
    return store.get_bytes(_strict_artifact_id(record))


class FileSystemCASFoundryBootstrapEvidencePort(FoundryBootstrapEvidencePort):
    """Read strict bootstrap records from an existing CAS without trusting them."""

    def __init__(
        self,
        *,
        store: core_artifacts.FileSystemCAS,
        capsule_index_path: Path,
    ) -> None:
        self._store = store
        self._capsule_index_path = capsule_index_path

    def load_capsule_raw(self) -> PersistedFoundryDependencyAuthorityCapsule:
        return _load_content_bound_capsule(self._capsule_index_path)

    def load_binding_index_raw(
        self,
        *,
        index_ref: FoundryRecordRef[Literal[DigestDomain.SIGNED_BINDING_INDEX]],
    ) -> PersistedSignedRecordBindingIndex:
        raw = _load_cas_statement_bytes(
            self._store,
            cast("FoundryRecordRef[DigestDomain]", index_ref),
        )
        statement = evidence_module.SignedRecordBindingIndexStatement.model_validate_json(
            raw
        )
        _require_exact_statement_ref(
            domain=DigestDomain.SIGNED_BINDING_INDEX,
            expected_ref=cast("FoundryRecordRef[DigestDomain]", index_ref),
            statement=statement,
            raw=raw,
            label="signed binding index",
        )
        return PersistedSignedRecordBindingIndex(
            index_ref=index_ref,
            statement=statement,
        )

    def load_binding_raw(
        self,
        *,
        binding_ref: FoundryRecordRef[Literal[DigestDomain.SIGNED_RECORD_BINDING]],
    ) -> PersistedSignedFoundryRecordBinding[DigestDomain]:
        raw = _load_cas_statement_bytes(
            self._store,
            cast("FoundryRecordRef[DigestDomain]", binding_ref),
        )
        statement = SignedFoundryRecordBindingStatement[DigestDomain].model_validate_json(
            raw
        )
        _require_exact_statement_ref(
            domain=DigestDomain.SIGNED_RECORD_BINDING,
            expected_ref=cast("FoundryRecordRef[DigestDomain]", binding_ref),
            statement=statement,
            raw=raw,
            label="signed record binding",
        )
        return PersistedSignedFoundryRecordBinding[DigestDomain](
            binding_ref=binding_ref,
            statement=statement,
        )

    def load_exact_evidence_raw(
        self,
        *,
        evidence_ref: FoundryRecordRef[Literal[DigestDomain.SIGNED_EVIDENCE]],
    ) -> ExactSignedArtifactEvidenceStatement:
        raw = _load_cas_statement_bytes(
            self._store,
            cast("FoundryRecordRef[DigestDomain]", evidence_ref),
        )
        statement = ExactSignedArtifactEvidenceStatement.model_validate_json(raw)
        _require_exact_statement_ref(
            domain=DigestDomain.SIGNED_EVIDENCE,
            expected_ref=cast("FoundryRecordRef[DigestDomain]", evidence_ref),
            statement=statement,
            raw=raw,
            label="exact signed evidence",
        )
        return statement


class FileSystemCASSignedRecordRepository(
    _OwnerBoundaryBase,
    CanonicalSignedRecordRepository,
):
    """Read-only v1 repository; no receipt writer is appointed in Cluster 1."""

    def __init__(
        self,
        *,
        store: core_artifacts.FileSystemCAS,
        trust_resolver: FoundryTrustResolver,
    ) -> None:
        self._store = store
        self._trust_resolver = trust_resolver

    def _missing_trust(
        self,
        source_authority: CanonicalFoundrySourceAuthority,
    ) -> BidirectionalUnestablishedAuthorityPredicate:
        with _unwrap_owner_capability(
            source_authority,
            _CANONICAL_SOURCE_SPEC,
        ) as source:
            return _unestablished_from_registry(
                source,
                AuthorityPredicateId.TRUST_SIGNATURE,
            )

    def _rejected_signature(
        self,
        source_authority: CanonicalFoundrySourceAuthority,
        *,
        evidence_refs: tuple[FoundryRecordRef[DigestDomain], ...],
    ) -> RejectedAuthorityPredicate:
        with _unwrap_owner_capability(
            source_authority,
            _CANONICAL_SOURCE_SPEC,
        ) as source:
            return _rejected_from_registry(
                source,
                AuthorityPredicateId.TRUST_SIGNATURE,
                evidence_refs=evidence_refs,
            )

    def _load_binding(
        self,
        binding_ref: FoundryRecordRef[
            Literal[DigestDomain.SIGNED_RECORD_BINDING]
        ],
    ) -> PersistedSignedFoundryRecordBinding[DigestDomain]:
        return FileSystemCASFoundryBootstrapEvidencePort(
            store=self._store,
            capsule_index_path=Path("unused-candidate-capsule"),
        ).load_binding_raw(binding_ref=binding_ref)

    def _load_evidence(
        self,
        evidence_ref: FoundryRecordRef[Literal[DigestDomain.SIGNED_EVIDENCE]],
    ) -> ExactSignedArtifactEvidenceStatement:
        return FileSystemCASFoundryBootstrapEvidencePort(
            store=self._store,
            capsule_index_path=Path("unused-candidate-capsule"),
        ).load_exact_evidence_raw(evidence_ref=evidence_ref)

    def import_and_bind(
        self,
        *,
        record_ref: FoundryRecordRef[DigestDomain],
        evidence: ExactSignedArtifactEvidenceStatement,
        required_role: TrustRole,
        verification_basis: SignedRecordVerificationBasis,
        source_authority: CanonicalFoundrySourceAuthority,
    ) -> SignedRecordVerificationResult:
        del record_ref, evidence, required_role, verification_basis
        return self._missing_trust(source_authority)

    def persist_binding_index(
        self,
        *,
        source_authority_ref: FoundryRecordRef[
            Literal[DigestDomain.CANONICAL_SOURCE]
        ],
        bindings: Sequence[PersistedSignedFoundryRecordBinding[DigestDomain]],
    ) -> PersistedSignedRecordBindingIndex:
        del source_authority_ref, bindings
        raise RuntimeError(
            "owner_resolved_resolution_receipt_store is absent/unallocated"
        )

    def load_and_verify_binding(
        self,
        *,
        binding_ref: FoundryRecordRef[
            Literal[DigestDomain.SIGNED_RECORD_BINDING]
        ],
        expected_record_domain: DigestDomain,
        source_authority: CanonicalFoundrySourceAuthority,
    ) -> SignedRecordVerificationResult:
        failure_evidence_refs: tuple[FoundryRecordRef[DigestDomain], ...] | None = None
        trust: ResolvedFoundryTrust | None = None
        try:
            binding = self._load_binding(binding_ref)
            record = binding.statement.record_ref
            if record.semantic_hash.domain is not expected_record_domain:
                raise ValueError("signed record domain differs from its requested domain")
            with _unwrap_owner_capability(
                source_authority,
                _CANONICAL_SOURCE_SPEC,
            ) as source:
                registry_row = next(
                    row
                    for row in source.digest_registry.statement.domains
                    if row.domain_id is expected_record_domain
                )
                if (
                    registry_row.signature_requirement != "signed"
                    or registry_row.required_signer_role
                    is not binding.statement.required_role
                ):
                    raise ValueError("signed record role differs from its registry row")
                source_ref = source.authority_ref
                source_cutoff = source.statement.source_freeze_commit
            basis = binding.statement.verification_basis
            if basis.kind == "source_authority":
                if basis.source_authority_ref != source_ref:
                    raise ValueError("source trust basis differs from canonical source")
                return self._missing_trust(source_authority)
            receipt_raw = _load_cas_statement_bytes(
                self._store,
                cast("FoundryRecordRef[DigestDomain]", basis.trust_resolution_receipt_ref),
            )
            receipt_statement = load_strict_foundry_statement(
                record=cast(
                    "FoundryRecordRef[DigestDomain]",
                    basis.trust_resolution_receipt_ref,
                ),
                raw=receipt_raw,
            )
            if not isinstance(
                receipt_statement,
                evidence_module.TrustResolutionReceiptStatement,
            ):
                raise ValueError("trust basis does not name a trust-resolution receipt")
            failure_evidence_refs = (
                cast(
                    "FoundryRecordRef[DigestDomain]",
                    binding.statement.signed_evidence_ref,
                ),
                cast(
                    "FoundryRecordRef[DigestDomain]",
                    receipt_statement.trust_material_ref,
                ),
            )
            evidence = self._load_evidence(binding.statement.signed_evidence_ref)
            validate_exact_signed_record(binding, evidence)
            record_raw = _load_cas_statement_bytes(self._store, record)
            manifest_raw = self._store.get_manifest_bytes(_strict_artifact_id(record))
            if (
                record_raw != evidence.signed_blob_bytes
                or manifest_raw != evidence.exact_manifest_bytes
            ):
                raise ValueError("signed evidence differs from the retained CAS triple")
            signature = core_artifacts.DetachedSignature.model_validate_json(
                evidence.detached_signature_bytes
            )
            if not signature.signer_identity:
                raise ValueError("signed evidence has no signer identity")
            if (
                receipt_statement.source_authority_ref != source_ref
                or receipt_statement.source_freeze_commit != source_cutoff
                or receipt_statement.required_role is not binding.statement.required_role
                or receipt_statement.verifier_provenance_ref
                != binding.statement.verifier_provenance_ref
            ):
                raise ValueError("signed binding differs from its resolved trust basis")
            resolved = self._trust_resolver.resolve(
                policy_ref=receipt_statement.trust_policy_ref,
                required_role=binding.statement.required_role,
            )
            if not isinstance(resolved, ResolvedFoundryTrust):
                return resolved
            trust = resolved
            with _unwrap_owner_capability(
                trust,
                _RESOLVED_TRUST_SPEC,
            ) as trust_payload:
                if (
                    trust_payload.receipt.receipt_ref
                    != basis.trust_resolution_receipt_ref
                    or trust_payload.receipt.statement != receipt_statement
                ):
                    raise ValueError("trust resolver returned a different receipt")
                verification = trust_payload.verifier.verify(
                    _strict_artifact_id(record),
                    record_raw,
                    manifest_raw,
                    signature,
                    strict_identity=True,
                )
                if (
                    verification.status
                    is not core_artifacts.SignatureVerificationStatus.VALID
                ):
                    raise ValueError("detached signature is not valid for the bound record")
            load_strict_foundry_statement(record=record, raw=record_raw)
            return _mint_owner_capability(
                _SIGNED_RECORD_SPEC,
                _VerifiedSignedFoundryRecordPayload(
                    record_domain=expected_record_domain,
                    binding=binding,
                    exact_record_bytes=record_raw,
                ),
            )
        except (FileNotFoundError, OSError, TypeError, ValueError):
            if failure_evidence_refs is None:
                return self._missing_trust(source_authority)
            return self._rejected_signature(
                source_authority,
                evidence_refs=failure_evidence_refs,
            )
        finally:
            if trust is not None:
                _release_owner_capability(trust, _RESOLVED_TRUST_SPEC)

    def verify_capsule_signed_graph(
        self,
        *,
        capsule: PersistedFoundryDependencyAuthorityCapsule,
        source_authority: CanonicalFoundrySourceAuthority,
    ) -> CapsuleSignedGraphVerificationResult:
        del capsule
        return self._missing_trust(source_authority)


class ArtifactStoreFoundryDependencyAuthorityRepository(
    FoundryDependencyAuthorityEvidenceRepository
):
    def __init__(
        self,
        *,
        store: core_artifacts.ArtifactStore,
        signed_records: CanonicalSignedRecordRepository,
        capsule_index_path: Path,
    ) -> None:
        self._store = store
        self._signed_records = signed_records
        self._capsule_index_path = capsule_index_path

    def load_capsule(self) -> PersistedFoundryDependencyAuthorityCapsule:
        return _load_content_bound_capsule(self._capsule_index_path)

    def signed_records(self) -> CanonicalSignedRecordRepository:
        return self._signed_records

    def read_blob(self, *, record_ref: FoundryRecordRef[DigestDomain]) -> bytes:
        return self._store.get_bytes(_strict_artifact_id(record_ref))


@dataclass(frozen=True, slots=True)
class _ResolvedDependencyAuthorityComponentsPayload:
    capsule: PersistedFoundryDependencyAuthorityCapsule
    signed_graph: VerifiedCapsuleSignedGraph
    trust_resolver: _ProductionFoundryTrustResolver
    signed_records: FileSystemCASSignedRecordRepository
    appointments: _ProductionDataAppointmentAuthority
    mounts: _ProductionDataMountResolver
    root_attestor: _ProductionDataRootAccessAttestor
    python_installations: _ProductionPythonRuntimeInstallationAuthority
    python_observer: _ProductionPythonRuntimeObserver


@_fieldless_owner_token
class ResolvedDependencyAuthorityComponents:
    pass


_CANONICAL_SOURCE_SPEC: _OwnerPayloadSpec[
    CanonicalFoundrySourceAuthority,
    _CanonicalFoundrySourceAuthorityPayload,
] = _OwnerPayloadSpec(
    kind=OwnerCapabilityKind.CANONICAL_SOURCE,
    token_type=CanonicalFoundrySourceAuthority,
    payload_type=_CanonicalFoundrySourceAuthorityPayload,
    exact_concrete_leaves=(
        _OwnerPayloadLeafSpec(("source_root",), _PosixOpenedDirectoryHandle),
    ),
    dynamic_record_domain_path=None,
    dynamic_record_ref_domain_path=None,
    child_resource_paths=(("source_root",),),
    nested_tokens=(),
)
_RUNTIME_INSTALLATION_SPEC: _OwnerPayloadSpec[
    ResolvedPythonRuntimeInstallation,
    _ResolvedPythonRuntimeInstallationPayload,
] = _OwnerPayloadSpec(
    kind=OwnerCapabilityKind.RUNTIME_INSTALLATION,
    token_type=ResolvedPythonRuntimeInstallation,
    payload_type=_ResolvedPythonRuntimeInstallationPayload,
    exact_concrete_leaves=(
        _OwnerPayloadLeafSpec(
            ("opened_runtime_root",),
            _PosixOpenedDirectoryHandle,
        ),
    ),
    dynamic_record_domain_path=None,
    dynamic_record_ref_domain_path=None,
    child_resource_paths=(("opened_runtime_root",),),
    nested_tokens=(),
)
_VERIFIED_RUNTIME_SPEC: _OwnerPayloadSpec[
    VerifiedPythonRuntime,
    _VerifiedPythonRuntimePayload,
] = _OwnerPayloadSpec(
    kind=OwnerCapabilityKind.VERIFIED_RUNTIME,
    token_type=VerifiedPythonRuntime,
    payload_type=_VerifiedPythonRuntimePayload,
    exact_concrete_leaves=(),
    dynamic_record_domain_path=None,
    dynamic_record_ref_domain_path=None,
    child_resource_paths=(),
    nested_tokens=(),
)
_TRUST_BOOTSTRAP_SPEC: _OwnerPayloadSpec[
    VerifiedFoundryTrustBootstrap,
    _VerifiedFoundryTrustBootstrapPayload,
] = _OwnerPayloadSpec(
    kind=OwnerCapabilityKind.TRUST_BOOTSTRAP,
    token_type=VerifiedFoundryTrustBootstrap,
    payload_type=_VerifiedFoundryTrustBootstrapPayload,
    exact_concrete_leaves=(),
    dynamic_record_domain_path=None,
    dynamic_record_ref_domain_path=None,
    child_resource_paths=(),
    nested_tokens=(),
)
_RESOLVED_TRUST_SPEC: _OwnerPayloadSpec[
    ResolvedFoundryTrust,
    _ResolvedFoundryTrustPayload,
] = _OwnerPayloadSpec(
    kind=OwnerCapabilityKind.RESOLVED_TRUST,
    token_type=ResolvedFoundryTrust,
    payload_type=_ResolvedFoundryTrustPayload,
    exact_concrete_leaves=(
        _OwnerPayloadLeafSpec(("verifier",), core_artifacts.Ed25519Verifier),
    ),
    dynamic_record_domain_path=None,
    dynamic_record_ref_domain_path=None,
    child_resource_paths=(),
    nested_tokens=(),
)
_PRODUCTION_APPOINTMENT_SPEC: _OwnerPayloadSpec[
    VerifiedProductionDataAppointment,
    _VerifiedProductionDataAppointmentPayload,
] = _OwnerPayloadSpec(
    kind=OwnerCapabilityKind.PRODUCTION_APPOINTMENT,
    token_type=VerifiedProductionDataAppointment,
    payload_type=_VerifiedProductionDataAppointmentPayload,
    exact_concrete_leaves=(),
    dynamic_record_domain_path=None,
    dynamic_record_ref_domain_path=None,
    child_resource_paths=(),
    nested_tokens=(),
)
_PRODUCTION_MOUNT_SPEC: _OwnerPayloadSpec[
    ResolvedProductionDataMount,
    _ResolvedProductionDataMountPayload,
] = _OwnerPayloadSpec(
    kind=OwnerCapabilityKind.PRODUCTION_MOUNT,
    token_type=ResolvedProductionDataMount,
    payload_type=_ResolvedProductionDataMountPayload,
    exact_concrete_leaves=(
        _OwnerPayloadLeafSpec(("opened_root_handle",), _InstitutionalRootHandle),
    ),
    dynamic_record_domain_path=None,
    dynamic_record_ref_domain_path=None,
    child_resource_paths=(("opened_root_handle",),),
    nested_tokens=(),
)
_ROOT_ACCESS_SPEC: _OwnerPayloadSpec[
    VerifiedProductionDataRootAccess,
    _VerifiedProductionDataRootAccessPayload,
] = _OwnerPayloadSpec(
    kind=OwnerCapabilityKind.ROOT_ACCESS,
    token_type=VerifiedProductionDataRootAccess,
    payload_type=_VerifiedProductionDataRootAccessPayload,
    exact_concrete_leaves=(),
    dynamic_record_domain_path=None,
    dynamic_record_ref_domain_path=None,
    child_resource_paths=(),
    nested_tokens=(),
)
_SIGNED_RECORD_SPEC: _OwnerPayloadSpec[
    VerifiedSignedFoundryRecord,
    _VerifiedSignedFoundryRecordPayload,
] = _OwnerPayloadSpec(
    kind=OwnerCapabilityKind.SIGNED_RECORD,
    token_type=VerifiedSignedFoundryRecord,
    payload_type=_VerifiedSignedFoundryRecordPayload,
    exact_concrete_leaves=(),
    dynamic_record_domain_path=("record_domain",),
    dynamic_record_ref_domain_path=(
        "binding",
        "statement",
        "record_ref",
        "semantic_hash",
        "domain",
    ),
    child_resource_paths=(),
    nested_tokens=(),
)
_SIGNED_GRAPH_SPEC: _OwnerPayloadSpec[
    VerifiedCapsuleSignedGraph,
    _VerifiedCapsuleSignedGraphPayload,
] = _OwnerPayloadSpec(
    kind=OwnerCapabilityKind.SIGNED_GRAPH,
    token_type=VerifiedCapsuleSignedGraph,
    payload_type=_VerifiedCapsuleSignedGraphPayload,
    exact_concrete_leaves=(),
    dynamic_record_domain_path=None,
    dynamic_record_ref_domain_path=None,
    child_resource_paths=(),
    nested_tokens=(
        _OwnerNestedTokenSpec(
            payload_path=("verified_records",),
            cardinality=_OwnerNestedCardinality.MANY,
            token_path=("record",),
            expected_domain_path=("record_domain",),
            nested_kind=OwnerCapabilityKind.SIGNED_RECORD,
        ),
    ),
)
_RESOLVED_COMPONENTS_SPEC: _OwnerPayloadSpec[
    ResolvedDependencyAuthorityComponents,
    _ResolvedDependencyAuthorityComponentsPayload,
] = _OwnerPayloadSpec(
    kind=OwnerCapabilityKind.RESOLVED_COMPONENTS,
    token_type=ResolvedDependencyAuthorityComponents,
    payload_type=_ResolvedDependencyAuthorityComponentsPayload,
    exact_concrete_leaves=(
        _OwnerPayloadLeafSpec(("trust_resolver",), _ProductionFoundryTrustResolver),
        _OwnerPayloadLeafSpec(
            ("signed_records",),
            FileSystemCASSignedRecordRepository,
        ),
        _OwnerPayloadLeafSpec(
            ("appointments",),
            _ProductionDataAppointmentAuthority,
        ),
        _OwnerPayloadLeafSpec(("mounts",), _ProductionDataMountResolver),
        _OwnerPayloadLeafSpec(
            ("root_attestor",),
            _ProductionDataRootAccessAttestor,
        ),
        _OwnerPayloadLeafSpec(
            ("python_installations",),
            _ProductionPythonRuntimeInstallationAuthority,
        ),
        _OwnerPayloadLeafSpec(
            ("python_observer",),
            _ProductionPythonRuntimeObserver,
        ),
    ),
    dynamic_record_domain_path=None,
    dynamic_record_ref_domain_path=None,
    child_resource_paths=(),
    nested_tokens=(
        _OwnerNestedTokenSpec(
            payload_path=("signed_graph",),
            cardinality=_OwnerNestedCardinality.SINGLE,
            token_path=(),
            expected_domain_path=None,
            nested_kind=OwnerCapabilityKind.SIGNED_GRAPH,
        ),
    ),
)

_OWNER_CAPABILITY_SPECS = (
    _CANONICAL_SOURCE_SPEC,
    _RUNTIME_INSTALLATION_SPEC,
    _VERIFIED_RUNTIME_SPEC,
    _TRUST_BOOTSTRAP_SPEC,
    _RESOLVED_TRUST_SPEC,
    _PRODUCTION_APPOINTMENT_SPEC,
    _PRODUCTION_MOUNT_SPEC,
    _ROOT_ACCESS_SPEC,
    _SIGNED_RECORD_SPEC,
    _SIGNED_GRAPH_SPEC,
    _RESOLVED_COMPONENTS_SPEC,
)
(
    _open_owner_directory,
    _require_owner_descriptor,
    _close_owner_descriptor,
    _owner_descriptor_lease_key,
    _claim_owner_resources,
    _release_owner_resources,
    _register_owner_fork_participant,
    _owner_lifecycle_section,
    _before_owner_fork,
    _after_owner_fork_parent,
    _after_owner_fork_child,
) = _build_owner_resource_coordinator(
    specs=cast(
        "tuple[_OwnerPayloadSpec[object, object], ...]",
        _OWNER_CAPABILITY_SPECS,
    )
)
(
    _mint_owner_capability,
    _unwrap_owner_capability,
    _release_owner_capability,
) = _build_owner_capability_kernel(
    cast(
        "tuple[_OwnerPayloadSpec[object, object], ...]",
        _OWNER_CAPABILITY_SPECS,
    ),
    claim_owner_resources=_claim_owner_resources,
    release_owner_resources=_release_owner_resources,
    register_fork_participant=_register_owner_fork_participant,
    lifecycle_section=_owner_lifecycle_section,
)
os.register_at_fork(
    before=_before_owner_fork,
    after_in_parent=_after_owner_fork_parent,
    after_in_child=_after_owner_fork_child,
)


@dataclass(frozen=True, slots=True)
class CandidatePythonRuntimeInstallation:
    """Candidate installation plus its live owner token for reference verification."""

    persisted: PersistedPythonRuntimeInstallation
    capability: ResolvedPythonRuntimeInstallation
    observation: CandidatePythonRuntimeObservation


def _runtime_marker_mismatch(
    *,
    expected: FoundryRecordRef[DigestDomain],
    observed: FoundryRecordRef[DigestDomain],
) -> DigestPredicateMismatch:
    return DigestPredicateMismatch(
        kind="digest_mismatch",
        predicate_id=AuthorityPredicateId.PYTHON_RUNTIME,
        code=AuthorityFailureCode.PYTHON_RUNTIME_MISMATCH,
        expected=expected.semantic_hash,
        observed=observed.semantic_hash,
        predicate_class="independently_reconciled",
    )


def _resolve_marked_python_runtime_before_observation(
    *,
    environment_root: Path,
    environment_receipt: profile_module.DependencyProfileEnvironmentReceipt,
    evidence: profile_module.DependencyProfileEnvironmentEvidence,
    installation_authority: PythonRuntimeInstallationAuthority,
    observer: PythonRuntimeObserver,
    admission: PythonRuntimeAdmission,
) -> PythonRuntimeObservationResult | AuthorityPredicateFailure:
    """Resolve the marker-owned installation before invoking the observer."""

    statement = environment_receipt.statement
    reopened = profile_module._reopen_bound_environment_marker(
        environment_root=environment_root,
        expected_marker_ref=statement.marker_ref,
        evidence=evidence,
    )
    if not isinstance(reopened, evidence_module.DependencyEnvironmentMarkerStatement):
        return reopened
    marker = reopened
    ref_pairs = (
        (admission.expected_runtime_manifest_ref, marker.python_runtime_ref),
        (
            statement.python_runtime_installation_ref,
            marker.python_runtime_installation_ref,
        ),
        (
            statement.python_runtime_verification_ref,
            marker.python_runtime_verification_ref,
        ),
    )
    for expected, observed in ref_pairs:
        if expected != observed:
            return _runtime_marker_mismatch(
                expected=cast("FoundryRecordRef[DigestDomain]", expected),
                observed=cast("FoundryRecordRef[DigestDomain]", observed),
            )

    installation = installation_authority.resolve_installed_root(
        environment_root=environment_root,
        receipt_ref=marker.python_runtime_installation_ref,
        admission=admission,
    )
    if not isinstance(installation, ResolvedPythonRuntimeInstallation):
        return installation
    try:
        with _unwrap_owner_capability(
            installation,
            _RUNTIME_INSTALLATION_SPEC,
        ):
            return observer.observe_and_verify(
                environment_root=environment_root,
                installation=installation,
                admission=admission,
            )
    finally:
        _release_owner_capability(
            installation,
            _RUNTIME_INSTALLATION_SPEC,
        )


@dataclass(frozen=True, slots=True)
class CandidateProductionDataRootAccess:
    """Candidate-only live root result; never part of the public N8 result union."""

    mount: ResolvedProductionDataMount
    access: VerifiedProductionDataRootAccess
    exact_manifest_bytes: bytes
    mount_ref: FoundryRecordRef[Literal[DigestDomain.ROOT_MOUNT_RESOLUTION]]
    access_ref: FoundryRecordRef[Literal[DigestDomain.ROOT_ACCESS]]


@dataclass(frozen=True, slots=True)
class CandidateInstalledSourceBinding:
    """Candidate source relation recomputed from retained owner evidence."""

    selected_evidence: evidence_module.SelectedDistributionArtifactEvidence
    statement: evidence_module.InstalledSourceBindingStatement
    binding_ref: FoundryRecordRef[Literal[DigestDomain.INSTALLED_BINDING]]

    def to_locked_distribution_identity(
        self,
        *,
        source_kind: Literal["registry", "url", "git", "path"],
        marker_expression: evidence_module.MarkerExpressionText | None,
    ) -> evidence_module.LockedDistributionIdentity:
        """Join independently derived selected and installed-binding refs."""

        # The content DAG is deliberately one-way: derive S from the selected
        # evidence, derive B from the binding that names S, then join S and B.
        selected_ref = cast(
            "FoundryRecordRef[Literal[DigestDomain.SELECTED_DISTRIBUTION]]",
            build_foundry_statement_ref(
                DigestDomain.SELECTED_DISTRIBUTION,
                self.selected_evidence,
            ),
        )
        if self.statement.selected_evidence_ref != selected_ref:
            raise ValueError("candidate selected evidence ref is not derived")
        derived_binding_ref = cast(
            "FoundryRecordRef[Literal[DigestDomain.INSTALLED_BINDING]]",
            build_foundry_statement_ref(DigestDomain.INSTALLED_BINDING, self.statement),
        )
        if self.binding_ref != derived_binding_ref:
            raise ValueError("candidate installed binding ref is not derived")
        if (
            self.statement.stable_manifest_ref
            != self.selected_evidence.expected_stable_manifest_ref
        ):
            raise ValueError("candidate stable manifest ref is not selected evidence")
        return evidence_module.LockedDistributionIdentity(
            normalized_name=self.selected_evidence.normalized_name,
            version=self.selected_evidence.version,
            source_kind=source_kind,
            selected_artifact_ref=selected_ref,
            expected_stable_manifest_ref=self.statement.stable_manifest_ref,
            expected_source_binding_ref=derived_binding_ref,
            marker_expression=marker_expression,
        )


def recompute_candidate_installed_source_binding(
    *,
    source_authority: _CanonicalFoundrySourceAuthorityPayload,
    selected_evidence: evidence_module.SelectedDistributionArtifactEvidence,
    observed_stable_manifest_ref: FoundryRecordRef[
        Literal[DigestDomain.INSTALLED_STABLE]
    ],
    observed_artifact_bytes: bytes | None = None,
    resolved_build_lineage: evidence_module.PersistedBuildLineageEvidence | None = None,
) -> CandidateInstalledSourceBinding | AuthorityPredicateFailure:
    """Recompute one candidate installed-source relation without ambient inputs."""

    expected_stable = selected_evidence.expected_stable_manifest_ref
    if observed_stable_manifest_ref != expected_stable:
        return _rejected_from_registry(
            source_authority,
            AuthorityPredicateId.INSTALLED_SOURCE,
            evidence_refs=(
                cast("FoundryRecordRef[DigestDomain]", observed_stable_manifest_ref),
            ),
        )

    selected_ref = cast(
        "FoundryRecordRef[Literal[DigestDomain.SELECTED_DISTRIBUTION]]",
        build_foundry_statement_ref(
            DigestDomain.SELECTED_DISTRIBUTION,
            selected_evidence,
        ),
    )
    if isinstance(selected_evidence, evidence_module.SelectedBuiltArtifactEvidence):
        if resolved_build_lineage is None:
            return _unestablished_from_registry(
                source_authority,
                AuthorityPredicateId.INSTALLED_SOURCE,
            )
        expected_lineage_ref = build_foundry_statement_ref(
            DigestDomain.BUILD_LINEAGE,
            resolved_build_lineage.statement,
        )
        if (
            resolved_build_lineage != selected_evidence.build_lineage
            or resolved_build_lineage.record_ref != expected_lineage_ref
            or resolved_build_lineage.statement.output_wheel_ref
            != selected_evidence.output_wheel_ref
        ):
            return _rejected_from_registry(
                source_authority,
                AuthorityPredicateId.INSTALLED_SOURCE,
                evidence_refs=(
                    cast(
                        "FoundryRecordRef[DigestDomain]",
                        resolved_build_lineage.record_ref,
                    ),
                ),
            )
        if observed_artifact_bytes is not None:
            observed_wheel_ref = record_ref(
                DigestDomain.SELECTED_WHEEL,
                observed_artifact_bytes,
                schema_version=selected_evidence.output_wheel_ref.schema_version,
            )
            if observed_wheel_ref != selected_evidence.output_wheel_ref:
                observed_selected = selected_evidence.model_copy(
                    update={"output_wheel_ref": observed_wheel_ref}
                )
                return _rejected_from_registry(
                    source_authority,
                    AuthorityPredicateId.SELECTED_ARTIFACT,
                    evidence_refs=(
                        build_foundry_statement_ref(
                            DigestDomain.SELECTED_DISTRIBUTION,
                            observed_selected,
                        ),
                    ),
                )
        statement: evidence_module.InstalledSourceBindingStatement = (
            evidence_module.BuiltInstalledSourceBindingStatement(
                binding_kind="built_source",
                schema_version="polisyos.foundry.installed-source-binding.v1",
                locked_source_ref=selected_evidence.locked_source_ref,
                selected_evidence_ref=selected_ref,
                stable_manifest_ref=observed_stable_manifest_ref,
                transform_profile="wheel_install_tree_v1",
                build_lineage_ref=resolved_build_lineage.record_ref,
            )
        )
    elif isinstance(selected_evidence, evidence_module.SelectedWheelArtifactEvidence):
        if observed_artifact_bytes is None:
            return _unestablished_from_registry(
                source_authority,
                AuthorityPredicateId.INSTALLED_SOURCE,
            )
        observed_wheel_ref = record_ref(
            DigestDomain.SELECTED_WHEEL,
            observed_artifact_bytes,
            schema_version=selected_evidence.wheel_blob_ref.schema_version,
        )
        if observed_wheel_ref != selected_evidence.wheel_blob_ref:
            observed_selected = selected_evidence.model_copy(
                update={"wheel_blob_ref": observed_wheel_ref}
            )
            return _rejected_from_registry(
                source_authority,
                AuthorityPredicateId.SELECTED_ARTIFACT,
                evidence_refs=(
                    build_foundry_statement_ref(
                        DigestDomain.SELECTED_DISTRIBUTION,
                        observed_selected,
                    ),
                ),
            )
        statement = evidence_module.WheelInstalledSourceBindingStatement(
            binding_kind="wheel",
            schema_version="polisyos.foundry.installed-source-binding.v1",
            locked_source_ref=selected_evidence.locked_source_ref,
            selected_evidence_ref=selected_ref,
            stable_manifest_ref=observed_stable_manifest_ref,
            transform_profile="wheel_install_tree_v1",
        )
    else:
        statement = evidence_module.SourceFirstInstalledSourceBindingStatement(
            binding_kind="source_first",
            schema_version="polisyos.foundry.installed-source-binding.v1",
            locked_source_ref=selected_evidence.locked_source_ref,
            selected_evidence_ref=selected_ref,
            stable_manifest_ref=observed_stable_manifest_ref,
            transform_profile="source_first_tree_v1",
            source_tree_ref=selected_evidence.source_tree_manifest_ref,
        )

    return CandidateInstalledSourceBinding(
        selected_evidence=selected_evidence,
        statement=statement,
        binding_ref=cast(
            "FoundryRecordRef[Literal[DigestDomain.INSTALLED_BINDING]]",
            build_foundry_statement_ref(DigestDomain.INSTALLED_BINDING, statement),
        ),
    )


class CandidateInstitutionalRootResolver(Protocol):
    def __call__(
        self,
        requested_root: Path,
    ) -> evidence_module.ExternalAuthorityRef[
        Literal[ExternalAuthorityKind.INSTITUTIONAL_ROOT]
    ] | None: ...


class CandidateRootAccessAttestor(Protocol):
    def __call__(
        self,
        challenge: ProductionDataRootAccessChallenge,
    ) -> RootAccessAttestationStatement | None: ...


def _read_candidate_manifest_from_mount(
    mount: _ResolvedProductionDataMountPayload,
) -> bytes:
    descriptor = mount.opened_root_handle.require_current_process_descriptor()
    flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
    manifest_descriptor = os.open("manifest.json", flags, dir_fd=descriptor)
    try:
        before = os.fstat(manifest_descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise OSError("production manifest is not a regular file")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(manifest_descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(manifest_descriptor)
        fields = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns")
        if any(getattr(before, field) != getattr(after, field) for field in fields):
            raise OSError("production manifest changed during observation")
        return b"".join(chunks)
    finally:
        os.close(manifest_descriptor)


def _candidate_root_access_rejected(
    *,
    source_authority: _CanonicalFoundrySourceAuthorityPayload,
    access_ref: FoundryRecordRef[Literal[DigestDomain.ROOT_ACCESS]],
    mount_ref: FoundryRecordRef[Literal[DigestDomain.ROOT_MOUNT_RESOLUTION]],
) -> RejectedAuthorityPredicate:
    return _rejected_from_registry(
        source_authority,
        AuthorityPredicateId.ROOT_ACCESS,
        evidence_refs=(
            cast("FoundryRecordRef[DigestDomain]", access_ref),
            cast("FoundryRecordRef[DigestDomain]", mount_ref),
        ),
    )


def resolve_candidate_production_data_root_access(
    *,
    source_authority: _CanonicalFoundrySourceAuthorityPayload,
    appointment: _VerifiedProductionDataAppointmentPayload,
    requested_root: Path,
    request_ref: FoundryRecordRef[Literal[DigestDomain.RESOLUTION_REQUEST]],
    institutional_resolver: CandidateInstitutionalRootResolver | None,
    root_access_attestor: CandidateRootAccessAttestor | None,
) -> CandidateProductionDataRootAccess | AuthorityPredicateFailure:
    """Run the candidate root pipeline while retaining institutional unknowns."""

    if institutional_resolver is None:
        return _unestablished_from_registry(
            source_authority,
            AuthorityPredicateId.ROOT_ACCESS,
        )
    resolved_root = institutional_resolver(requested_root)
    if resolved_root is None or not requested_root.exists():
        return _unestablished_from_registry(
            source_authority,
            AuthorityPredicateId.ROOT_ACCESS,
        )
    requested_token = domain_digest(
        DigestDomain.ROOT_MOUNT_REQUEST,
        os.fsencode(Path(os.path.realpath(requested_root))),
    )
    mount_statement = ProductionDataMountResolutionStatement(
        schema_version="polisyos.foundry.production-data-mount.v1",
        appointment_ref=appointment.appointment_ref,
        institutional_root=resolved_root,
        requested_root_token=requested_token,
        access_mode="read_only",
    )
    mount_ref = cast(
        "FoundryRecordRef[Literal[DigestDomain.ROOT_MOUNT_RESOLUTION]]",
        build_foundry_statement_ref(
            DigestDomain.ROOT_MOUNT_RESOLUTION,
            mount_statement,
        ),
    )
    opened_root: _InstitutionalRootHandle | None = None
    mount_token: ResolvedProductionDataMount | None = None
    access_token: VerifiedProductionDataRootAccess | None = None
    try:
        opened_root = _open_owner_directory(
            directory=Path(os.path.realpath(requested_root)),
            owner_kind=OwnerCapabilityKind.PRODUCTION_MOUNT,
            handle_type=_InstitutionalRootHandle,
        )
        mount_token = _mint_owner_capability(
            _PRODUCTION_MOUNT_SPEC,
            _ResolvedProductionDataMountPayload(
                receipt_ref=mount_ref,
                statement=mount_statement,
                opened_root_handle=opened_root,
            ),
        )
        opened_root = None
        with _unwrap_owner_capability(
            mount_token,
            _PRODUCTION_MOUNT_SPEC,
        ) as mount_payload:
            descriptor = mount_payload.opened_root_handle.require_current_process_descriptor()
            opened_stat = os.fstat(descriptor)
            manifest_bytes = _read_candidate_manifest_from_mount(mount_payload)
            manifest_ref = record_ref(
                DigestDomain.PRODUCTION_MANIFEST,
                manifest_bytes,
                schema_version="polisyos.foundry.production-data-manifest.v1",
            )
            challenge = ProductionDataRootAccessChallenge(
                schema_version="polisyos.foundry.root-access-challenge.v1",
                request_ref=request_ref,
                challenge_nonce=domain_digest(DigestDomain.ROOT_NONCE, os.urandom(32)),
                expected_root=appointment.appointment_statement.appointed_root,
                expected_manifest_ref=appointment.appointment_statement.expected_manifest_ref,
                mount_resolution_ref=mount_ref,
            )
            if root_access_attestor is None:
                return _unestablished_from_registry(
                    source_authority,
                    AuthorityPredicateId.ROOT_ACCESS,
                )
            attestation = root_access_attestor(challenge)
            if attestation is None:
                return _unestablished_from_registry(
                    source_authority,
                    AuthorityPredicateId.ROOT_ACCESS,
                )
            access_ref = cast(
                "FoundryRecordRef[Literal[DigestDomain.ROOT_ACCESS]]",
                build_foundry_statement_ref(DigestDomain.ROOT_ACCESS, attestation),
            )
            rejected = False
            try:
                validate_root_access_attestation(challenge, attestation)
            except ValueError:
                rejected = True
            try:
                reopened = os.open(
                    Path(os.path.realpath(requested_root)),
                    os.O_RDONLY
                    | os.O_CLOEXEC
                    | getattr(os, "O_DIRECTORY", 0)
                    | getattr(os, "O_NOFOLLOW", 0),
                )
            except OSError:
                return _unestablished_from_registry(
                    source_authority,
                    AuthorityPredicateId.ROOT_ACCESS,
                )
            try:
                reopened_stat = os.fstat(reopened)
            finally:
                os.close(reopened)
            post_attestation_manifest = _read_candidate_manifest_from_mount(mount_payload)
            writable_bits = stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH
            if (
                resolved_root != appointment.appointment_statement.appointed_root
                or manifest_ref != appointment.appointment_statement.expected_manifest_ref
                or post_attestation_manifest != manifest_bytes
                or opened_stat.st_dev != reopened_stat.st_dev
                or opened_stat.st_ino != reopened_stat.st_ino
                or bool(opened_stat.st_mode & writable_bits)
            ):
                rejected = True
            if rejected:
                return _candidate_root_access_rejected(
                    source_authority=source_authority,
                    access_ref=access_ref,
                    mount_ref=mount_ref,
                )
            access_token = _mint_owner_capability(
                _ROOT_ACCESS_SPEC,
                _VerifiedProductionDataRootAccessPayload(
                    statement=attestation,
                    attestation_ref=access_ref,
                    signed_binding_ref=appointment.appointment_binding_ref,
                    predicate_class="independently_reconciled",
                ),
            )
        result = CandidateProductionDataRootAccess(
            mount=mount_token,
            access=access_token,
            exact_manifest_bytes=manifest_bytes,
            mount_ref=mount_ref,
            access_ref=access_ref,
        )
        mount_token = None
        access_token = None
        return result
    except (OSError, OwnerCapabilityFault):
        return _unestablished_from_registry(
            source_authority,
            AuthorityPredicateId.ROOT_ACCESS,
        )
    finally:
        if access_token is not None:
            _release_owner_capability(access_token, _ROOT_ACCESS_SPEC)
        if mount_token is not None:
            _release_owner_capability(mount_token, _PRODUCTION_MOUNT_SPEC)
        if opened_root is not None:
            opened_root.close_owner_resource()


def validate_python_runtime_installation(
    persisted: PersistedPythonRuntimeInstallation,
) -> None:
    """Recompute the installation receipt and its embedded root-token relation."""

    expected_root_token = build_foundry_statement_ref(
        DigestDomain.TOOLCHAIN_RUNTIME_ROOT_TOKEN,
        persisted.statement.runtime_root_identity,
    ).semantic_hash
    expected_receipt_ref = build_foundry_statement_ref(
        DigestDomain.TOOLCHAIN_RUNTIME_INSTALLATION,
        persisted.statement,
    )
    if (
        persisted.statement.runtime_root_instance != expected_root_token
        or persisted.statement.runtime_manifest_ref
        != persisted.statement.runtime_root_identity.second_walk_manifest_ref
        or persisted.receipt_ref != expected_receipt_ref
    ):
        raise ValueError("python runtime installation receipt is not content-bound")


def build_candidate_python_runtime_installation(
    *,
    source_authority: _CanonicalFoundrySourceAuthorityPayload,
    environment_root: Path,
    admission: PythonRuntimeAdmission,
    environment_creation_nonce: DomainDigest[
        Literal[DigestDomain.ENVIRONMENT_INSTANCE]
    ],
    installer_provenance_ref: FoundryRecordRef[
        Literal[DigestDomain.VERIFIER_PROVENANCE]
    ],
) -> CandidatePythonRuntimeInstallation | BidirectionalUnestablishedAuthorityPredicate:
    """Build reference installation evidence without entering the production graph."""

    observation = observe_candidate_python_runtime(
        environment_root=environment_root,
        runtime_root=environment_root,
        environment_creation_nonce=environment_creation_nonce,
        executable_relative_path=evidence_module.RootedRelativePath(value="bin/python"),
        version=admission.version,
        platform_tag=admission.platform_tag,
        abi_tag="cp314",
        digest_registry=source_authority.digest_registry,
    )
    if isinstance(observation, BidirectionalUnestablishedAuthorityPredicate):
        return observation
    runtime_manifest_ref = observation.root_identity.second_walk_manifest_ref
    source_binding = evidence_module.PythonRuntimeSourceBindingStatement(
        schema_version="polisyos.foundry.python-runtime-source-binding.v1",
        selected_artifact_ref=admission.selected_artifact_ref,
        runtime_manifest_ref=runtime_manifest_ref,
        installation_transform="python_runtime_installation_v1",
    )
    source_binding_ref = build_foundry_statement_ref(
        DigestDomain.TOOLCHAIN_RUNTIME_BINDING,
        source_binding,
    )
    if (
        runtime_manifest_ref != admission.expected_runtime_manifest_ref
        or source_binding_ref != admission.expected_runtime_source_binding_ref
    ):
        return _candidate_runtime_not_established(source_authority.digest_registry)
    statement = evidence_module.PythonRuntimeInstallationStatement(
        schema_version="polisyos.foundry.python-runtime-installation.v1",
        source_authority_ref=source_authority.authority_ref,
        selected_artifact_ref=admission.selected_artifact_ref,
        runtime_manifest_ref=runtime_manifest_ref,
        runtime_source_binding_ref=source_binding_ref,
        environment_creation_nonce=environment_creation_nonce,
        runtime_root_identity=observation.root_identity,
        runtime_root_instance=observation.root_token,
        installer_provenance_ref=installer_provenance_ref,
    )
    persisted = PersistedPythonRuntimeInstallation(
        receipt_ref=build_foundry_statement_ref(
            DigestDomain.TOOLCHAIN_RUNTIME_INSTALLATION,
            statement,
        ),
        statement=statement,
    )
    opened_root = _open_owner_directory(
        directory=environment_root.resolve(strict=True),
        owner_kind=OwnerCapabilityKind.RUNTIME_INSTALLATION,
        handle_type=_PosixOpenedDirectoryHandle,
    )
    try:
        capability = _mint_owner_capability(
            _RUNTIME_INSTALLATION_SPEC,
            _ResolvedPythonRuntimeInstallationPayload(
                persisted=persisted,
                opened_runtime_root=opened_root,
            ),
        )
    except BaseException:
        opened_root.close_owner_resource()
        raise
    return CandidatePythonRuntimeInstallation(
        persisted=persisted,
        capability=capability,
        observation=observation,
    )


def _candidate_executable_runtime_root(
    environment_root: Path,
    executable_relative_path: evidence_module.RootedRelativePath,
) -> tuple[Path, evidence_module.RootedRelativePath, bytes | None]:
    child = environment_root / executable_relative_path.value
    raw_link = os.fsencode(os.readlink(child)) if child.is_symlink() else None
    if not child.exists():
        raise FileNotFoundError(child)
    resolved_executable = Path(os.path.realpath(child))
    actual_root = resolved_executable
    for _part in Path(executable_relative_path.value).parts:
        actual_root = actual_root.parent
    resolved_relative = evidence_module.RootedRelativePath(
        value=resolved_executable.relative_to(actual_root).as_posix()
    )
    return actual_root, resolved_relative, raw_link


def _observe_and_verify_candidate_python_runtime(
    *,
    source_authority: _CanonicalFoundrySourceAuthorityPayload,
    environment_root: Path,
    installation: _ResolvedPythonRuntimeInstallationPayload,
    admission: PythonRuntimeAdmission,
) -> PythonRuntimeObservationResult:
    """Independently re-open and reconcile one sealed candidate installation."""

    installation.opened_runtime_root.require_current_process_descriptor()
    statement = installation.persisted.statement
    executable_relative_path = evidence_module.RootedRelativePath(value="bin/python")
    try:
        actual_root, resolved_executable, raw_link = _candidate_executable_runtime_root(
            Path(os.path.realpath(environment_root)),
            executable_relative_path,
        )
    except (OSError, ValueError):
        return _unestablished_from_registry(
            source_authority,
            AuthorityPredicateId.PYTHON_RUNTIME,
        )
    observed = observe_candidate_python_runtime(
        environment_root=environment_root,
        runtime_root=actual_root,
        environment_creation_nonce=statement.environment_creation_nonce,
        executable_relative_path=resolved_executable,
        version=admission.version,
        platform_tag=admission.platform_tag,
        abi_tag="cp314",
        digest_registry=source_authority.digest_registry,
    )
    if isinstance(observed, BidirectionalUnestablishedAuthorityPredicate):
        return observed
    recomputed_runtime_ref = observed.root_identity.second_walk_manifest_ref
    source_binding = evidence_module.PythonRuntimeSourceBindingStatement(
        schema_version="polisyos.foundry.python-runtime-source-binding.v1",
        selected_artifact_ref=admission.selected_artifact_ref,
        runtime_manifest_ref=recomputed_runtime_ref,
        installation_transform="python_runtime_installation_v1",
    )
    observed_source_binding_ref = build_foundry_statement_ref(
        DigestDomain.TOOLCHAIN_RUNTIME_BINDING,
        source_binding,
    )
    resolution_chain: tuple[evidence_module.PythonRuntimeResolutionHop, ...] = ()
    if raw_link is not None:
        resolution_chain = (
            evidence_module.PythonRuntimeResolutionHop(
                source_root_instance=statement.runtime_root_instance,
                source_relative_path=executable_relative_path,
                target_root_instance=observed.root_token,
                target_relative_path=resolved_executable,
                raw_link_hash=domain_digest(DigestDomain.RAW_BLOB, raw_link),
            ),
        )
    root_resolution = evidence_module.PythonRuntimeRootResolutionStatement(
        schema_version="polisyos.foundry.python-runtime-root-resolution.v1",
        environment_creation_nonce=statement.environment_creation_nonce,
        installation_receipt_ref=installation.persisted.receipt_ref,
        environment_python_relative_path=executable_relative_path,
        resolved_executable_relative_path=resolved_executable,
        resolution_chain=resolution_chain,
        runtime_root_identity=observed.root_identity,
        runtime_root_instance=observed.root_token,
        recomputed_runtime_manifest_ref=recomputed_runtime_ref,
        recomputed_source_binding_ref=observed_source_binding_ref,
    )
    root_resolution_ref = build_foundry_statement_ref(
        DigestDomain.TOOLCHAIN_RUNTIME_ROOT,
        root_resolution,
    )
    observed_statement = evidence_module.ObservedPythonRuntimeStatement(
        schema_version="polisyos.foundry.python-runtime-observed.v1",
        environment_creation_nonce=statement.environment_creation_nonce,
        expected_runtime_ref=admission.expected_runtime_manifest_ref,
        installation_receipt_ref=installation.persisted.receipt_ref,
        root_resolution_ref=root_resolution_ref,
        recomputed_runtime_manifest_ref=recomputed_runtime_ref,
        observed_source_binding_ref=observed_source_binding_ref,
        implementation="cpython",
        version=admission.version,
        platform_tag=admission.platform_tag,
        abi_tag="cp314",
        files=observed.second_manifest.files,
    )
    observed_ref = build_foundry_statement_ref(
        DigestDomain.TOOLCHAIN_RUNTIME_OBSERVED,
        observed_statement,
    )
    verification = evidence_module.PythonRuntimeVerificationReceiptStatement(
        schema_version="polisyos.foundry.python-runtime-verification.v1",
        expected_runtime_ref=admission.expected_runtime_manifest_ref,
        installation_receipt_ref=installation.persisted.receipt_ref,
        recomputed_runtime_manifest_ref=recomputed_runtime_ref,
        expected_source_binding_ref=admission.expected_runtime_source_binding_ref,
        observed_source_binding_ref=observed_source_binding_ref,
        root_resolution_ref=root_resolution_ref,
        observed_runtime_ref=observed_ref,
        verifier_provenance_ref=admission.verifier_provenance_ref,
        predicate_class="independently_reconciled",
    )
    verification_ref = build_foundry_statement_ref(
        DigestDomain.TOOLCHAIN_RUNTIME_VERIFICATION,
        verification,
    )
    if (
        statement.source_authority_ref != source_authority.authority_ref
        or statement.selected_artifact_ref != admission.selected_artifact_ref
        or statement.runtime_manifest_ref != admission.expected_runtime_manifest_ref
        or statement.runtime_source_binding_ref
        != admission.expected_runtime_source_binding_ref
        or statement.runtime_root_instance != observed.root_token
        or statement.runtime_root_identity != observed.root_identity
        or recomputed_runtime_ref != admission.expected_runtime_manifest_ref
        or observed_source_binding_ref != admission.expected_runtime_source_binding_ref
    ):
        return _rejected_from_registry(
            source_authority,
            AuthorityPredicateId.PYTHON_RUNTIME,
            evidence_refs=(cast("FoundryRecordRef[DigestDomain]", verification_ref),),
        )
    return _mint_owner_capability(
        _VERIFIED_RUNTIME_SPEC,
        _VerifiedPythonRuntimePayload(
            observed_ref=cast(
                "FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME_OBSERVED]]",
                observed_ref,
            ),
            verification_ref=cast(
                "FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME_VERIFICATION]]",
                verification_ref,
            ),
        ),
    )

DependencyAuthorityComponentResolution = (
    ResolvedDependencyAuthorityComponents
    | RejectedAuthorityPredicate
    | UnestablishedAuthorityPredicate
)


def _open_source_trust_bootstrapper() -> _ProductionFoundrySourceTrustBootstrapper:
    return _ProductionFoundrySourceTrustBootstrapper()


def _open_git_commit_ancestry_authority(
    *,
    source_authority: _CanonicalFoundrySourceAuthorityPayload,
) -> _ProductionGitCommitAncestryAuthority:
    return _ProductionGitCommitAncestryAuthority(
        source_authority=source_authority,
    )


def _build_sealed_foundry_trust_resolver(
    *,
    bootstrap: _VerifiedFoundryTrustBootstrapPayload,
    ancestry: GitCommitAncestryAuthority,
) -> _ProductionFoundryTrustResolver:
    if not isinstance(ancestry, _ProductionGitCommitAncestryAuthority):
        raise TypeError("trust resolver requires the owner Git ancestry authority")
    if bootstrap.snapshot.source_authority_ref != ancestry._source_authority.authority_ref:
        raise ValueError("trust bootstrap is not bound to the source authority")
    return _ProductionFoundryTrustResolver(
        source_authority=ancestry._source_authority,
    )


def _open_owner_production_data_appointment_authority(
    *,
    source_authority: _CanonicalFoundrySourceAuthorityPayload,
    signed_records: CanonicalSignedRecordRepository,
) -> _ProductionDataAppointmentAuthority:
    if not isinstance(signed_records, FileSystemCASSignedRecordRepository):
        raise TypeError("appointment authority requires the canonical signed repository")
    return _ProductionDataAppointmentAuthority(source_authority=source_authority)


def _open_owner_production_data_mount_resolver(
    *,
    source_authority: _CanonicalFoundrySourceAuthorityPayload,
) -> _ProductionDataMountResolver:
    return _ProductionDataMountResolver(source_authority=source_authority)


def _open_owner_root_access_attestor(
    *,
    source_authority: _CanonicalFoundrySourceAuthorityPayload,
    trust_resolver: FoundryTrustResolver,
    signed_records: CanonicalSignedRecordRepository,
) -> _ProductionDataRootAccessAttestor:
    if not isinstance(trust_resolver, _ProductionFoundryTrustResolver) or not isinstance(
        signed_records,
        FileSystemCASSignedRecordRepository,
    ):
        raise TypeError("root attestor dependencies are not owner-sealed")
    return _ProductionDataRootAccessAttestor(source_authority=source_authority)


def _open_owner_python_runtime_installation_authority(
    *,
    source_authority: _CanonicalFoundrySourceAuthorityPayload,
    cutoff_authority: _NoRuntimeSubtreeCutoffAuthority,
) -> _ProductionPythonRuntimeInstallationAuthority:
    if type(cutoff_authority) is not _NoRuntimeSubtreeCutoffAuthority:
        raise TypeError("runtime installation requires the exact cutoff owner")
    return _ProductionPythonRuntimeInstallationAuthority(
        source_authority=source_authority,
        cutoff_authority=cutoff_authority,
    )


def _open_owner_python_runtime_observer(
    *,
    source_authority: _CanonicalFoundrySourceAuthorityPayload,
    installations: PythonRuntimeInstallationAuthority,
) -> _ProductionPythonRuntimeObserver:
    if not isinstance(installations, _ProductionPythonRuntimeInstallationAuthority):
        raise TypeError("runtime observer requires owner-sealed installation authority")
    return _ProductionPythonRuntimeObserver(source_authority=source_authority)


def _resolve_owner_components_for_request(
    *,
    request: MethodCatalogDependencyAuthorityRequest,
    source_authority: CanonicalFoundrySourceAuthority,
    bootstrapper: FoundrySourceTrustBootstrapper,
    ancestry: GitCommitAncestryAuthority,
) -> DependencyAuthorityComponentResolution:
    """Fail before CAS/component construction while source trust is unappointed."""

    del request, bootstrapper, ancestry
    with _unwrap_owner_capability(
        source_authority,
        _CANONICAL_SOURCE_SPEC,
    ) as source:
        return _unestablished_from_registry(
            source,
            AuthorityPredicateId.TRUST_SIGNATURE,
        )


def build_runtime_cutoff_refusal(
    *,
    source_authority: _CanonicalFoundrySourceAuthorityPayload,
    request: DependencyAuthorityResolvedSourceRequestStatement,
    candidate_runtime_evidence: RuntimeCandidateEvidenceDisposition,
) -> UnestablishedMethodCatalogDependencyProfile:
    """Construct the sole post-source result and validate its registry branch."""

    cutoff_rows = tuple(
        row
        for row in source_authority.digest_registry.statement.predicates
        if row.predicate_id is AuthorityPredicateId.RUNTIME_SUBTREE_CUTOFF
    )
    if len(cutoff_rows) != 1 or cutoff_rows[0].branch_shape != "not_established_only":
        raise ValueError("runtime cutoff registry branch is not one-sided")
    predicate = RuntimeCutoffUnestablishedPredicate(
        status="not_established",
        predicate_id=AuthorityPredicateId.RUNTIME_SUBTREE_CUTOFF,
        predicate_class="not_established",
        failure_code=AuthorityFailureCode.RUNTIME_SUBTREE_CUTOFF_NOT_ESTABLISHED,
        missing_capability="owner_enforced_runtime_subtree_cutoff",
        missing_capability_state="absent/unallocated",
        candidate_runtime_evidence=candidate_runtime_evidence,
    )
    result = UnestablishedMethodCatalogDependencyProfile(
        result_kind=NegativeDependencyAuthorityResultKind.RUNTIME_CUTOFF_NOT_ESTABLISHED,
        status="not_established",
        preflight_refusal=RuntimeCutoffPreflightRefusal(
            schema_version="polisyos.foundry.runtime-cutoff-preflight-refusal.v1",
            persistence=_persistence_gap(),
            source_authority_ref=source_authority.authority_ref,
            request=request,
            failure=predicate,
        ),
    )
    validate_negative_dependency_authority_stage(result, source_authority=source_authority)
    return result


def validate_negative_dependency_authority_stage(
    result: UnestablishedMethodCatalogDependencyProfile,
    *,
    source_authority: _CanonicalFoundrySourceAuthorityPayload,
) -> None:
    """Reconcile the emitted cutoff result to the owner-bound registry row."""

    failure = result.preflight_refusal.failure
    cutoff_rows = tuple(
        row
        for row in source_authority.digest_registry.statement.predicates
        if row.predicate_id is AuthorityPredicateId.RUNTIME_SUBTREE_CUTOFF
    )
    if len(cutoff_rows) != 1:
        raise ValueError("runtime cutoff predicate is ambiguous")
    row = cutoff_rows[0]
    requirement = row.not_established_requirement
    if (
        row.branch_shape != "not_established_only"
        or row.not_established_code is not failure.failure_code
        or requirement.capability_id != failure.missing_capability
        or requirement.capability_state != failure.missing_capability_state
        or result.preflight_refusal.source_authority_ref != source_authority.authority_ref
    ):
        raise ValueError("runtime cutoff result does not match the owner registry")


class _ProductionMethodCatalogDependencyAuthority(
    _OwnerBoundaryBase,
    MethodCatalogDependencyAuthority,
):
    def __init__(
        self,
        *,
        source_resolver: _ProductionCanonicalFoundrySourceAuthorityResolver,
        cutoff_authority: _NoRuntimeSubtreeCutoffAuthority,
    ) -> None:
        self._source_resolver = source_resolver
        self._cutoff_authority = cutoff_authority

    def resolve(
        self,
        request: MethodCatalogDependencyAuthorityRequest,
    ) -> MethodCatalogDependencyAuthorityResult:
        source = self._source_resolver.resolve(request=request)
        if isinstance(
            source,
            (
                SourceRejectedMethodCatalogDependencyProfile,
                SourceUnestablishedMethodCatalogDependencyProfile,
            ),
        ):
            return source
        try:
            with _unwrap_owner_capability(
                source,
                _CANONICAL_SOURCE_SPEC,
            ) as source_payload:
                resolved_request = DependencyAuthorityResolvedSourceRequestStatement(
                    schema_version=(
                        "polisyos.foundry.dependency-resolved-source-request.v1"
                    ),
                    pre_source_request=_pre_source_statement(request),
                    expected_source_tree_id=source_payload.statement.source_tree_id,
                )
                predicate = self._cutoff_authority.preflight()
                return build_runtime_cutoff_refusal(
                    source_authority=source_payload,
                    request=resolved_request,
                    candidate_runtime_evidence=predicate.candidate_runtime_evidence,
                )
        finally:
            _release_owner_capability(source, _CANONICAL_SOURCE_SPEC)


def _build_production_canonical_source_resolver(
) -> _ProductionCanonicalFoundrySourceAuthorityResolver:
    """Construct the exact source owner; callers cannot inject a snapshot."""

    return _ProductionCanonicalFoundrySourceAuthorityResolver()


def build_production_method_catalog_dependency_authority() -> MethodCatalogDependencyAuthority:
    """Build the closed production graph with its explicit absent cutoff owner."""

    return _ProductionMethodCatalogDependencyAuthority(
        source_resolver=_build_production_canonical_source_resolver(),
        cutoff_authority=_NoRuntimeSubtreeCutoffAuthority(),
    )


def validate_negative_only_dependency_authority_abi() -> None:
    """Fail if the public result union gains a positive or unregistered arm."""

    annotation = MethodCatalogDependencyAuthorityResult
    union = get_args(annotation)[0]
    variants = set(get_args(union))
    expected = {
        SourceRejectedMethodCatalogDependencyProfile,
        SourceUnestablishedMethodCatalogDependencyProfile,
        UnestablishedMethodCatalogDependencyProfile,
    }
    if variants != expected:
        raise AssertionError("dependency authority result denominator changed")
    statuses = {
        variant.model_fields["status"].annotation
        for variant in variants
    }
    if not statuses:
        raise AssertionError("dependency authority result status denominator is empty")
    validate_public_catalog_negative_graph()


def _all_foundry_authority_models() -> tuple[type[FoundryAuthorityModel], ...]:
    pending = [FoundryAuthorityModel]
    observed: set[type[FoundryAuthorityModel]] = set()
    while pending:
        parent = pending.pop()
        for child in parent.__subclasses__():
            if child not in observed:
                observed.add(child)
                pending.append(child)
    return tuple(sorted(observed, key=lambda item: f"{item.__module__}.{item.__qualname__}"))


def _walk_annotation(annotation: object) -> Iterator[object]:
    yield annotation
    for argument in get_args(annotation):
        if argument is not Ellipsis:
            yield from _walk_annotation(argument)


def validate_no_owner_capability_in_persisted_schemas() -> None:
    """Reject any live owner token reachable from a persisted Pydantic DTO."""

    token_types = {
        value
        for value in globals().values()
        if isinstance(value, type)
        and vars(value).get("__owner_token_class_marker__")
        is _OWNER_TOKEN_CLASS_MARKER
    }
    if len(token_types) != len(OwnerCapabilityKind):
        raise AssertionError("owner token denominator is not capability-complete")
    for model in _all_foundry_authority_models():
        hints = get_type_hints(model, include_extras=True)
        for field_name, annotation in hints.items():
            if token_types.intersection(_walk_annotation(annotation)):
                raise AssertionError(
                    f"persisted schema {model.__qualname__}.{field_name} contains "
                    "an owner capability"
                )


def validate_authority_scalar_role_coverage() -> None:
    """Require semantic roles on every non-literal scalar in authority DTOs."""

    failures: list[str] = []

    def inspect_annotation(
        annotation: object,
        *,
        role: AuthorityScalarRole | None,
        location: str,
    ) -> None:
        origin = get_origin(annotation)
        if origin is Annotated:
            base, *metadata = get_args(annotation)
            semantic_roles = tuple(
                item for item in metadata if isinstance(item, AuthorityScalarRole)
            )
            if len(semantic_roles) > 1:
                failures.append(f"{location}: multiple scalar roles")
                return
            inspect_annotation(
                base,
                role=semantic_roles[0] if semantic_roles else role,
                location=location,
            )
            return
        if origin is Literal:
            return
        if isinstance(annotation, type) and issubclass(annotation, StrEnum):
            return
        if annotation in {str, bytes, int, Path}:
            if role is None:
                failures.append(f"{location}: untyped scalar {annotation!r}")
            return
        for argument in get_args(annotation):
            if argument is not Ellipsis and argument is not type(None):
                inspect_annotation(argument, role=role, location=location)

    for model in _all_foundry_authority_models():
        for field_name, annotation in get_type_hints(
            model,
            include_extras=True,
        ).items():
            inspect_annotation(
                annotation,
                role=None,
                location=f"{model.__qualname__}.{field_name}",
            )
    if failures:
        raise AssertionError("authority scalar role gaps: " + "; ".join(failures))


def validate_decisive_domain_coverage() -> None:
    """Reconcile every typed digest/ref annotation to the frozen domain registry."""

    registry = load_digest_domain_registry(_DIGEST_REGISTRY_PATH)
    registered = tuple(row.domain_id for row in registry.statement.domains)
    if set(registered) != set(DigestDomain) or len(registered) != len(DigestDomain):
        raise AssertionError("digest registry is not an enum-complete bijection")
    if len({row.prefix_hex for row in registry.statement.domains}) != len(registered):
        raise AssertionError("digest registry prefixes are not unique")

    failures: list[str] = []
    for model in _all_foundry_authority_models():
        for field_name, annotation in get_type_hints(
            model,
            include_extras=True,
        ).items():
            for member in _walk_annotation(annotation):
                origin = get_origin(member)
                if origin not in {DomainDigest, FoundryRecordRef}:
                    continue
                arguments = get_args(member)
                if len(arguments) != 1:
                    failures.append(f"{model.__qualname__}.{field_name}: unbound domain")
                    continue
                domain = arguments[0]
                domain_origin = get_origin(domain)
                if domain is DigestDomain:
                    continue
                if domain_origin is Literal:
                    literal_values = get_args(domain)
                    if (
                        len(literal_values) == 1
                        and type(literal_values[0]) is DigestDomain
                    ):
                        continue
                if getattr(domain, "__bound__", None) is DigestDomain:
                    continue
                failures.append(
                    f"{model.__qualname__}.{field_name}: non-semantic domain {domain!r}"
                )
    if failures:
        raise AssertionError("decisive domain gaps: " + "; ".join(failures))


def validate_authority_predicate_coverage() -> None:
    """Require one executable branch grammar for every authority predicate."""

    registry = load_digest_domain_registry(_DIGEST_REGISTRY_PATH)
    rows = registry.statement.predicates
    ids = tuple(row.predicate_id for row in rows)
    if set(ids) != set(AuthorityPredicateId) or len(ids) != len(AuthorityPredicateId):
        raise AssertionError("authority predicate registry is not enum-complete")
    one_sided = tuple(row for row in rows if row.branch_shape == "not_established_only")
    if (
        len(one_sided) != 1
        or one_sided[0].predicate_id is not AuthorityPredicateId.RUNTIME_SUBTREE_CUTOFF
    ):
        raise AssertionError("runtime cutoff must be the sole one-sided predicate")
    for row in rows:
        if row.branch_shape == "bidirectional":
            if not isinstance(row, BidirectionalAuthorityPredicateSpec):
                raise AssertionError("predicate branch did not decode discriminately")
            if not row.admitted_classes:
                raise AssertionError("bidirectional predicate has no admitted P37 class")
        elif row.not_established_code is not AuthorityFailureCode.RUNTIME_SUBTREE_CUTOFF_NOT_ESTABLISHED:
            raise AssertionError("one-sided predicate uses the wrong failure code")


def validate_public_catalog_negative_graph(
    *,
    snapshot_file: Path | None = None,
    scan_roots: tuple[Path, ...] | None = None,
) -> None:
    """Strangle both public builders and every source caller to the owner request."""

    snapshot_file = snapshot_file or (
        _PRODUCT_ROOT / "src/polisyos/foundry/methods/catalog/snapshot.py"
    )
    snapshot_tree = ast.parse(
        snapshot_file.read_text(encoding="utf-8"),
        filename=str(snapshot_file),
    )
    public_names = {
        "build_method_catalog_runtime_identity",
        "build_method_catalog_provenance_manifest",
    }
    definitions = {
        node.name: node
        for node in snapshot_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in public_names
    }
    if set(definitions) != public_names:
        raise AssertionError("public catalog negative graph lost a builder")
    forbidden_calls = {
        "_build_candidate_method_catalog_runtime_identity",
        "_build_candidate_method_catalog_provenance_manifest",
        "platform",
        "safe_version",
        "resolve_dependency_profile",
        "reconcile_bound_installed_environment",
    }
    for name, definition in definitions.items():
        keyword_only = {argument.arg for argument in definition.args.kwonlyargs}
        if "dependency_authority_request" not in keyword_only:
            raise AssertionError(
                f"public catalog negative graph {name} lost its owner request"
            )
        calls = tuple(
            call_name
            for node in ast.walk(definition)
            if isinstance(node, ast.Call)
            and (call_name := _call_name(node)) is not None
        )
        if (
            calls.count("build_production_method_catalog_dependency_authority") != 1
            or calls.count("resolve") != 1
            or forbidden_calls.intersection(calls)
        ):
            raise AssertionError(
                f"public catalog negative graph {name} reaches candidate posture"
            )

    if scan_roots is None:
        scan_roots = (
            _PRODUCT_ROOT / "src",
            _PRODUCT_ROOT / "tools",
            _PRODUCT_ROOT / "tests",
        )
    missing_request: list[str] = []
    for scan_root in scan_roots:
        for candidate in sorted(scan_root.rglob("*.py")):
            tree = ast.parse(
                candidate.read_text(encoding="utf-8"),
                filename=str(candidate),
            )
            aliases = {
                alias.asname or alias.name: alias.name
                for node in tree.body
                if isinstance(node, ast.ImportFrom)
                for alias in node.names
                if alias.name in public_names
            }
            for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
                called_name = _call_name(call)
                canonical_name = aliases.get(called_name, called_name)
                if canonical_name not in public_names:
                    continue
                if not any(
                    keyword.arg == "dependency_authority_request"
                    for keyword in call.keywords
                ):
                    missing_request.append(
                        f"{candidate.relative_to(_PRODUCT_ROOT)}:{call.lineno}"
                    )
    if missing_request:
        raise AssertionError(
            "public catalog negative graph caller lacks owner request: "
            + ", ".join(missing_request)
        )


def _ast_base_name(node: ast.expr) -> str | None:
    while isinstance(node, ast.Subscript):
        node = node.value
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def derive_owner_protocol_concrete_pairs_from_source(
    *,
    module_file: Path,
    namespace: Mapping[str, object],
) -> tuple[tuple[type[object], type[object]], ...]:
    """Derive every owner Protocol/concrete pair from source and live MROs."""

    tree = ast.parse(module_file.read_text(encoding="utf-8"), filename=str(module_file))
    source_classes = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
    }
    bases = {
        name: tuple(
            base_name
            for base in node.bases
            if (base_name := _ast_base_name(base)) is not None
        )
        for name, node in source_classes.items()
    }

    def inherits(name: str, target: str, seen: frozenset[str] = frozenset()) -> bool:
        if name in seen:
            raise AssertionError("owner class graph contains a cycle")
        direct = bases.get(name, ())
        return target in direct or any(
            parent in bases and inherits(parent, target, seen | {name})
            for parent in direct
        )

    source_owner_names = {
        name
        for name in source_classes
        if name != "_OwnerBoundaryBase" and inherits(name, "_OwnerBoundaryBase")
    }
    live_owners = {
        name: value
        for name, value in namespace.items()
        if isinstance(value, type)
        and value is not _OwnerBoundaryBase
        and _OwnerBoundaryBase in value.__mro__[1:]
    }
    if set(live_owners) != source_owner_names:
        raise AssertionError("owner source and live class denominators differ")

    pairs: list[tuple[type[object], type[object]]] = []
    for concrete_name in sorted(source_owner_names):
        concrete = live_owners[concrete_name]
        protocols = tuple(
            candidate
            for candidate in concrete.__mro__[1:]
            if candidate.__module__ == __name__
            and getattr(candidate, "_is_protocol", False)
            and candidate is not Protocol
        )
        protocols = tuple(dict.fromkeys(protocols))
        if len(protocols) != 1:
            raise AssertionError(
                f"owner concrete {concrete_name} must implement one owner Protocol"
            )
        protocol = protocols[0]
        if protocol.__name__ not in source_classes or not inherits(
            concrete_name,
            protocol.__name__,
        ):
            raise AssertionError("owner Protocol relation is not source-derived")
        protocol_methods = {
            name
            for name, member in protocol.__dict__.items()
            if callable(member) and not name.startswith("_")
        }
        for method_name in protocol_methods:
            implementation = concrete.__dict__.get(method_name)
            if not callable(implementation):
                raise AssertionError(
                    f"{concrete_name} inherits an unimplemented Protocol method "
                    f"{method_name}"
                )
            protocol_signature = inspect.signature(protocol.__dict__[method_name])
            concrete_signature = inspect.signature(implementation)
            if tuple(protocol_signature.parameters) != tuple(
                concrete_signature.parameters
            ):
                raise AssertionError(
                    f"{concrete_name}.{method_name} changes Protocol parameters"
                )
        pairs.append((concrete, protocol))
    return tuple(pairs)


def _annotation_contains_type(annotation: object, target: type[object]) -> bool:
    return annotation is target or any(
        _annotation_contains_type(argument, target)
        for argument in get_args(annotation)
        if argument is not Ellipsis
    )


def derive_owner_entrypoint_denominator_from_source(
    *,
    module_file: Path,
    protocol_concrete_pairs: tuple[tuple[type[object], type[object]], ...],
) -> tuple[OwnerEntrypointSpec, ...]:
    """Derive owner methods and every module function consuming a live token."""

    tree = ast.parse(module_file.read_text(encoding="utf-8"), filename=str(module_file))
    source_functions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    spec_by_token = {
        spec.token_type: spec
        for spec in _OWNER_CAPABILITY_SPECS
    }
    predicate_by_kind = {
        OwnerCapabilityKind.CANONICAL_SOURCE: AuthorityPredicateId.SOURCE_FREEZE,
        OwnerCapabilityKind.RUNTIME_INSTALLATION: AuthorityPredicateId.PYTHON_RUNTIME,
        OwnerCapabilityKind.VERIFIED_RUNTIME: AuthorityPredicateId.PYTHON_RUNTIME,
        OwnerCapabilityKind.TRUST_BOOTSTRAP: AuthorityPredicateId.TRUST_SIGNATURE,
        OwnerCapabilityKind.RESOLVED_TRUST: AuthorityPredicateId.TRUST_SIGNATURE,
        OwnerCapabilityKind.PRODUCTION_APPOINTMENT: AuthorityPredicateId.PRODUCTION_APPOINTMENT,
        OwnerCapabilityKind.PRODUCTION_MOUNT: AuthorityPredicateId.ROOT_ACCESS,
        OwnerCapabilityKind.ROOT_ACCESS: AuthorityPredicateId.ROOT_ACCESS,
        OwnerCapabilityKind.SIGNED_RECORD: AuthorityPredicateId.TRUST_SIGNATURE,
        OwnerCapabilityKind.SIGNED_GRAPH: AuthorityPredicateId.TRUST_SIGNATURE,
        OwnerCapabilityKind.RESOLVED_COMPONENTS: AuthorityPredicateId.TRUST_SIGNATURE,
    }
    registry = load_digest_domain_registry(_DIGEST_REGISTRY_PATH)
    row_by_id = {
        row.predicate_id: row for row in registry.statement.predicates
    }

    def policies(function: Callable[..., object]) -> tuple[OwnerFaultPolicy, ...]:
        hints = get_type_hints(function, include_extras=True)
        output: list[OwnerFaultPolicy] = []
        for parameter_name, annotation in hints.items():
            if parameter_name == "return":
                continue
            matches = tuple(
                spec
                for token_type, spec in spec_by_token.items()
                if _annotation_contains_type(annotation, token_type)
            )
            if not matches:
                continue
            if len(matches) != 1:
                raise AssertionError("entrypoint parameter has ambiguous token family")
            owner_spec = matches[0]
            predicate_id = predicate_by_kind[owner_spec.kind]
            predicate = row_by_id[predicate_id]
            if isinstance(predicate, BidirectionalAuthorityPredicateSpec):
                rejected_code = predicate.rejected_code
                not_established_code = predicate.not_established_code
                missing = predicate.not_established_requirement
                missing_domains = (
                    missing.missing_domains
                    if isinstance(missing, MissingEvidenceDomainsRequirement)
                    else ()
                )
            else:
                rejected_code = predicate.not_established_code
                not_established_code = predicate.not_established_code
                missing_domains = ()
            output.append(
                OwnerFaultPolicy(
                    capability_parameter_name=parameter_name,
                    capability_kind=owner_spec.kind,
                    predicate_id=predicate_id,
                    rejected_code=rejected_code,
                    not_established_code=not_established_code,
                    evidence_argument_names=tuple(
                        sorted(
                            name
                            for name, candidate in hints.items()
                            if name not in {"return", parameter_name}
                            and any(
                                get_origin(member) is FoundryRecordRef
                                for member in _walk_annotation(candidate)
                            )
                        )
                    ),
                    missing_evidence_domains=missing_domains,
                )
            )
        return tuple(output)

    def adapter_for(
        protocol: type[object] | None,
        method_name: str,
    ) -> OwnerEntrypointFailureAdapterId:
        if protocol is GitCommitAncestryAuthority:
            return OwnerEntrypointFailureAdapterId.GIT_RELATION
        if method_name == "read_manifest":
            return OwnerEntrypointFailureAdapterId.MANIFEST_INPUT
        if protocol in {
            MethodCatalogDependencyAuthority,
            CanonicalFoundrySourceAuthorityResolver,
        }:
            return OwnerEntrypointFailureAdapterId.METHOD_CATALOG_RESULT
        return OwnerEntrypointFailureAdapterId.AUTHORITY_PREDICATE

    rows: list[OwnerEntrypointSpec] = []
    for concrete, protocol in protocol_concrete_pairs:
        for method_name, protocol_member in protocol.__dict__.items():
            if method_name.startswith("_") or not callable(protocol_member):
                continue
            concrete_member = concrete.__dict__.get(method_name)
            if not callable(concrete_member):
                raise AssertionError("owner Protocol method has no concrete implementation")
            rows.append(
                OwnerEntrypointSpec(
                    target=OwnerMethodTarget(
                        target_kind=OwnerEntrypointTargetKind.METHOD,
                        concrete_owner_type=concrete,
                        protocol_type=protocol,
                        method_name=method_name,
                    ),
                    fault_policies=policies(concrete_member),
                    failure_adapter_id=adapter_for(protocol, method_name),
                )
            )

    for function_name in sorted(source_functions):
        function = globals().get(function_name)
        if not callable(function):
            continue
        function_policies = policies(function)
        if not function_policies:
            continue
        rows.append(
            OwnerEntrypointSpec(
                target=OwnerFunctionTarget(
                    target_kind=OwnerEntrypointTargetKind.MODULE_FUNCTION,
                    module_qualname=__name__,
                    function_name=function_name,
                ),
                fault_policies=function_policies,
                failure_adapter_id=adapter_for(None, function_name),
            )
        )
    return tuple(
        sorted(
            rows,
            key=lambda row: (
                row.target.target_kind.value,
                (
                    f"{row.target.concrete_owner_type.__qualname__}."
                    f"{row.target.method_name}"
                    if isinstance(row.target, OwnerMethodTarget)
                    else row.target.function_name
                ),
            ),
        )
    )


def derive_owner_borrow_reachability_from_source(
    *,
    module_file: Path,
    owner_entrypoints: tuple[OwnerEntrypointSpec, ...],
) -> tuple[OwnerBorrowReachability, ...]:
    """Enumerate every AST occurrence in each lexical owner-payload borrow."""

    tree = ast.parse(module_file.read_text(encoding="utf-8"), filename=str(module_file))
    entrypoint_keys = {
        (
            target.concrete_owner_type.__name__,
            target.method_name,
        )
        if isinstance(target, OwnerMethodTarget)
        else (None, target.function_name)
        for target in (row.target for row in owner_entrypoints)
    }
    forbidden_calls = {
        "fork",
        "forkpty",
        "Popen",
        "run",
        "call",
        "check_call",
        "check_output",
        "Process",
        "Pool",
    }

    valid_unwrap_calls = {
        id(item.context_expr)
        for candidate in ast.walk(tree)
        if isinstance(candidate, ast.With)
        for item in candidate.items
        if isinstance(item.context_expr, ast.Call)
        and _call_name(item.context_expr) == "_unwrap_owner_capability"
    }
    for candidate in ast.walk(tree):
        if (
            isinstance(candidate, ast.Call)
            and _call_name(candidate) == "_unwrap_owner_capability"
            and id(candidate) not in valid_unwrap_calls
        ):
            raise AssertionError("bare unwrap exists outside a lexical payload borrow")

    function_nodes: dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]] = {}
    for candidate in ast.walk(tree):
        if isinstance(candidate, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function_nodes.setdefault(candidate.name, []).append(candidate)

    callable_aliases: dict[str, str] = {}
    changed = True
    while changed:
        changed = False
        for candidate in ast.walk(tree):
            if (
                not isinstance(candidate, (ast.Assign, ast.AnnAssign))
                or not isinstance(candidate.value, (ast.Name, ast.Attribute))
            ):
                continue
            targets = (
                candidate.targets
                if isinstance(candidate, ast.Assign)
                else (candidate.target,)
            )
            source_name = (
                candidate.value.id
                if isinstance(candidate.value, ast.Name)
                else candidate.value.attr
            )
            terminal = callable_aliases.get(source_name, source_name)
            if terminal not in forbidden_calls and terminal not in function_nodes:
                continue
            for target in targets:
                if (
                    isinstance(target, ast.Name)
                    and callable_aliases.get(target.id) != terminal
                ):
                    callable_aliases[target.id] = terminal
                    changed = True

    _TaintInfo = tuple[type[object], tuple[str, ...]]

    def taint_annotation(info: _TaintInfo | None) -> object | None:
        if info is None:
            return None
        root_type, field_path = info
        if not field_path:
            return root_type
        try:
            return _annotation_at_path(root_type, field_path)
        except TypeError:
            return None

    def exact_builtin_tuple(info: _TaintInfo | None) -> bool:
        annotation = taint_annotation(info)
        return annotation is tuple or get_origin(annotation) is tuple

    pure_calls = {
        "all",
        "any",
        "cast",
        "enumerate",
        "isinstance",
        "len",
        "load_strict_foundry_statement",
        "next",
        "set",
        "sorted",
        "tuple",
        "zip",
    }
    active_analyses: set[tuple[int, tuple[str, ...]]] = set()

    def analyze_statements(
        statements: Sequence[ast.stmt],
        taints: dict[str, _TaintInfo],
        callback_targets: dict[str, tuple[str, ...]],
    ) -> None:
        def expression_info(expression: ast.AST | None) -> _TaintInfo | None:
            if expression is None:
                return None
            if isinstance(expression, ast.Name):
                return taints.get(expression.id)
            if isinstance(expression, ast.Attribute):
                base = expression_info(expression.value)
                if base is None:
                    return None
                return (base[0], (*base[1], expression.attr))
            if isinstance(expression, ast.Subscript):
                return expression_info(expression.value)
            if isinstance(expression, ast.IfExp):
                left = expression_info(expression.body)
                right = expression_info(expression.orelse)
                return left if left == right else None
            return None

        def bind_target(target: ast.AST, info: _TaintInfo | None) -> None:
            if isinstance(target, ast.Name):
                if info is None:
                    taints.pop(target.id, None)
                else:
                    taints[target.id] = info
                return
            if info is not None and isinstance(target, (ast.Attribute, ast.Subscript)):
                raise AssertionError("owner payload escapes into mutable state")
            if isinstance(target, (ast.Tuple, ast.List)):
                for member in target.elts:
                    bind_target(member, None)

        def argument_binding(
            function: ast.FunctionDef | ast.AsyncFunctionDef,
            call: ast.Call,
            argument_infos: tuple[_TaintInfo | None, ...],
        ) -> tuple[dict[str, _TaintInfo], dict[str, tuple[str, ...]]]:
            parameters = (
                *function.args.posonlyargs,
                *function.args.args,
            )
            nested_taints: dict[str, _TaintInfo] = {}
            nested_callbacks: dict[str, tuple[str, ...]] = {}
            for parameter, info, argument in zip(
                parameters,
                argument_infos,
                call.args,
            ):
                if info is not None:
                    nested_taints[parameter.arg] = info
                if isinstance(argument, ast.Name):
                    targets = callback_targets.get(argument.id)
                    if targets is None and argument.id in function_nodes:
                        targets = (argument.id,)
                    if targets is not None:
                        nested_callbacks[parameter.arg] = targets
            keyword_parameters = {
                parameter.arg: parameter
                for parameter in (*function.args.args, *function.args.kwonlyargs)
            }
            for keyword in call.keywords:
                if keyword.arg is None or keyword.arg not in keyword_parameters:
                    continue
                info = expression_info(keyword.value)
                if info is not None:
                    nested_taints[keyword.arg] = info
                if isinstance(keyword.value, ast.Name):
                    targets = callback_targets.get(keyword.value.id)
                    if targets is None and keyword.value.id in function_nodes:
                        targets = (keyword.value.id,)
                    if targets is not None:
                        nested_callbacks[keyword.arg] = targets
            return nested_taints, nested_callbacks

        def analyze_function_call(
            function: ast.FunctionDef | ast.AsyncFunctionDef,
            call: ast.Call,
            argument_infos: tuple[_TaintInfo | None, ...],
        ) -> None:
            nested_taints, nested_callbacks = argument_binding(
                function,
                call,
                argument_infos,
            )
            key = (id(function), tuple(sorted(nested_taints)))
            if key in active_analyses:
                return
            active_analyses.add(key)
            try:
                analyze_statements(function.body, nested_taints, nested_callbacks)
            finally:
                active_analyses.remove(key)

        def analyze_expression(expression: ast.AST | None) -> _TaintInfo | None:
            if expression is None:
                return None
            if isinstance(expression, (ast.Name, ast.Attribute, ast.Subscript)):
                if isinstance(expression, ast.Subscript):
                    analyze_expression(expression.slice)
                if isinstance(expression, ast.Attribute):
                    analyze_expression(expression.value)
                return expression_info(expression)
            if isinstance(expression, ast.Call):
                receiver_info = (
                    analyze_expression(expression.func.value)
                    if isinstance(expression.func, ast.Attribute)
                    else None
                )
                argument_infos = tuple(
                    analyze_expression(argument) for argument in expression.args
                )
                keyword_infos = tuple(
                    analyze_expression(keyword.value) for keyword in expression.keywords
                )
                name = _call_name(expression)
                terminal_name = callable_aliases.get(name or "", name)
                if terminal_name in forbidden_calls:
                    raise AssertionError(
                        f"owner borrow reaches process primitive {terminal_name}"
                    )
                if name in {"len", "iter"} and argument_infos:
                    if argument_infos[0] is not None and not exact_builtin_tuple(
                        argument_infos[0]
                    ):
                        raise AssertionError(
                            f"owner payload reaches implicit dispatch {name}"
                        )
                if name in pure_calls:
                    return None
                target_names = callback_targets.get(name or "")
                if target_names is None and terminal_name in function_nodes:
                    target_names = (cast("str", terminal_name),)
                if target_names is not None:
                    for target_name in target_names:
                        for function in function_nodes.get(target_name, ()):
                            analyze_function_call(function, expression, argument_infos)
                    return None
                global_target = globals().get(name or "")
                if global_target is None:
                    global_target = getattr(evidence_module, name or "", None)
                safe_model_constructor = (
                    isinstance(global_target, type)
                    and issubclass(global_target, FoundryAuthorityModel)
                )
                if (
                    not safe_model_constructor
                    and name not in pure_calls
                    and (
                        receiver_info is not None
                        or any(info is not None for info in argument_infos)
                        or any(info is not None for info in keyword_infos)
                    )
                ):
                    raise AssertionError(
                        "owner payload escapes through callback "
                        f"{name or '<dynamic>'} at line {expression.lineno}"
                    )
                return None
            if isinstance(expression, (ast.GeneratorExp, ast.ListComp, ast.SetComp)):
                local_infos: list[tuple[ast.comprehension, _TaintInfo | None]] = []
                for generator in expression.generators:
                    info = analyze_expression(generator.iter)
                    if info is not None and not exact_builtin_tuple(info):
                        raise AssertionError(
                            "owner payload reaches implicit dispatch iteration"
                        )
                    bind_target(generator.target, info)
                    local_infos.append((generator, info))
                    for condition in generator.ifs:
                        analyze_expression(condition)
                analyze_expression(expression.elt)
                for generator, _info in local_infos:
                    bind_target(generator.target, None)
                return None
            if isinstance(expression, ast.DictComp):
                for generator in expression.generators:
                    info = analyze_expression(generator.iter)
                    if info is not None and not exact_builtin_tuple(info):
                        raise AssertionError(
                            "owner payload reaches implicit dispatch iteration"
                        )
                    bind_target(generator.target, info)
                    for condition in generator.ifs:
                        analyze_expression(condition)
                analyze_expression(expression.key)
                analyze_expression(expression.value)
                return None
            if isinstance(expression, ast.Lambda):
                if any(
                    expression_info(candidate) is not None
                    for candidate in ast.walk(expression.body)
                ):
                    raise AssertionError("owner payload escapes through a callback")
                return None
            for child in ast.iter_child_nodes(expression):
                analyze_expression(child)
            return expression_info(expression)

        for statement in statements:
            if isinstance(statement, (ast.Assign, ast.AnnAssign)):
                value = analyze_expression(statement.value)
                targets = (
                    statement.targets
                    if isinstance(statement, ast.Assign)
                    else (statement.target,)
                )
                for target in targets:
                    bind_target(target, value)
                continue
            if isinstance(statement, ast.AugAssign):
                info = analyze_expression(statement.value)
                if info is not None or expression_info(statement.target) is not None:
                    raise AssertionError("owner payload escapes into mutable state")
                continue
            if isinstance(statement, (ast.Return, ast.Yield, ast.YieldFrom)):
                if analyze_expression(statement.value) is not None:
                    raise AssertionError("owner payload escapes its lexical borrow")
                continue
            if isinstance(statement, ast.Expr):
                analyze_expression(statement.value)
                continue
            if isinstance(statement, ast.If):
                info = analyze_expression(statement.test)
                if info is not None and taint_annotation(info) is not bool:
                    raise AssertionError("owner payload reaches implicit dispatch bool")
                analyze_statements(statement.body, dict(taints), dict(callback_targets))
                analyze_statements(statement.orelse, dict(taints), dict(callback_targets))
                continue
            if isinstance(statement, (ast.For, ast.AsyncFor)):
                info = analyze_expression(statement.iter)
                if info is not None and not exact_builtin_tuple(info):
                    raise AssertionError(
                        "owner payload reaches implicit dispatch iteration"
                    )
                nested_taints = dict(taints)
                if isinstance(statement.target, ast.Name) and info is not None:
                    nested_taints[statement.target.id] = info
                analyze_statements(statement.body, nested_taints, dict(callback_targets))
                analyze_statements(statement.orelse, dict(taints), dict(callback_targets))
                continue
            if isinstance(statement, ast.Match):
                if analyze_expression(statement.subject) is not None:
                    raise AssertionError("owner payload reaches implicit dispatch match")
                for case in statement.cases:
                    analyze_expression(case.guard)
                    analyze_statements(case.body, dict(taints), dict(callback_targets))
                continue
            if isinstance(statement, ast.With):
                for item in statement.items:
                    analyze_expression(item.context_expr)
                analyze_statements(statement.body, dict(taints), dict(callback_targets))
                continue
            if isinstance(statement, ast.Try):
                analyze_statements(statement.body, dict(taints), dict(callback_targets))
                for handler in statement.handlers:
                    analyze_statements(handler.body, dict(taints), dict(callback_targets))
                analyze_statements(statement.orelse, dict(taints), dict(callback_targets))
                analyze_statements(statement.finalbody, dict(taints), dict(callback_targets))
                continue
            for child in ast.iter_child_nodes(statement):
                if isinstance(child, ast.expr):
                    analyze_expression(child)

    for candidate in ast.walk(tree):
        if not isinstance(candidate, ast.With):
            continue
        for item in candidate.items:
            expression = item.context_expr
            if (
                not isinstance(expression, ast.Call)
                or _call_name(expression) != "_unwrap_owner_capability"
                or not isinstance(item.optional_vars, ast.Name)
            ):
                continue
            payload_type: type[object] = object
            if len(expression.args) >= 2 and isinstance(expression.args[1], ast.Name):
                spec = globals().get(expression.args[1].id)
                if type(spec) is _OwnerPayloadSpec:
                    payload_type = spec.payload_type
            analyze_statements(
                candidate.body,
                {item.optional_vars.id: (payload_type, ())},
                {},
            )

    def occurrences(
        root: ast.AST,
    ) -> Iterator[tuple[ast.AST, tuple[AstOccurrenceStep, ...]]]:
        def visit(
            node: ast.AST,
            ancestry: tuple[AstOccurrenceStep, ...],
        ) -> Iterator[tuple[ast.AST, tuple[AstOccurrenceStep, ...]]]:
            yield node, ancestry
            for field_name, value in ast.iter_fields(node):
                if isinstance(value, ast.AST):
                    yield from visit(
                        value,
                        (*ancestry, AstOccurrenceStep(field_name, None)),
                    )
                elif isinstance(value, list):
                    for index, child in enumerate(value):
                        if isinstance(child, ast.AST):
                            yield from visit(
                                child,
                                (*ancestry, AstOccurrenceStep(field_name, index)),
                            )

        yield from visit(root, ())

    rows: list[OwnerBorrowReachability] = []
    class_stack: list[str] = []

    class Visitor(ast.NodeVisitor):
        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            class_stack.append(node.name)
            self.generic_visit(node)
            class_stack.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            owner_class = class_stack[-1] if class_stack else None
            lexical_key = (owner_class, node.name)
            for with_node in (
                candidate
                for candidate in ast.walk(node)
                if isinstance(candidate, ast.With)
            ):
                for item in with_node.items:
                    expression = item.context_expr
                    if (
                        not isinstance(expression, ast.Call)
                        or _call_name(expression) != "_unwrap_owner_capability"
                        or not isinstance(item.optional_vars, ast.Name)
                    ):
                        continue
                    borrowed = item.optional_vars.id
                    synthetic = ast.Module(body=with_node.body, type_ignores=[])
                    evaluated: list[OwnerBorrowEvaluationNode] = []
                    for occurrence, occurrence_path in occurrences(synthetic):
                        call_name = (
                            _call_name(occurrence)
                            if isinstance(occurrence, ast.Call)
                            else None
                        )
                        if call_name in forbidden_calls:
                            raise AssertionError(
                                f"owner borrow {owner_class}.{node.name} reaches "
                                f"process primitive {call_name}"
                            )
                        if isinstance(occurrence, (ast.Return, ast.Yield, ast.YieldFrom)):
                            value = getattr(occurrence, "value", None)
                            if isinstance(value, (ast.Name, ast.Attribute)) and any(
                                isinstance(member, ast.Name) and member.id == borrowed
                                for member in ast.walk(value)
                            ):
                                raise AssertionError("owner payload escapes its lexical borrow")
                        if isinstance(occurrence, (ast.Global, ast.Nonlocal)) and borrowed in occurrence.names:
                            raise AssertionError("owner payload is declared nonlocal/global")
                        if isinstance(occurrence, ast.Assign) and any(
                            isinstance(target, (ast.Attribute, ast.Subscript))
                            for target in occurrence.targets
                        ) and any(
                            isinstance(member, ast.Name) and member.id == borrowed
                            for member in ast.walk(occurrence.value)
                        ):
                            raise AssertionError("owner payload escapes into mutable state")
                        span = (
                            (
                                occurrence.lineno,
                                occurrence.col_offset,
                                occurrence.end_lineno,
                                occurrence.end_col_offset,
                            )
                            if hasattr(occurrence, "lineno")
                            and occurrence.end_lineno is not None
                            and occurrence.end_col_offset is not None
                            else None
                        )
                        terminal_edges: tuple[OwnerBorrowTerminalEdge, ...] = ()
                        if isinstance(occurrence, ast.Call):
                            terminal_edges = (
                                OwnerBorrowTerminalEdge(
                                    evaluation_kind="call",
                                    callable_qualified_name=call_name,
                                    operand_exact_types=(),
                                    implicit_method_names=(),
                                    disposition=(
                                        "traversed"
                                        if call_name is not None
                                        else "no_user_dispatch"
                                    ),
                                    traversed_qualified_functions=(
                                        (call_name,) if call_name is not None else ()
                                    ),
                                ),
                            )
                        elif isinstance(occurrence, ast.Attribute):
                            terminal_edges = (
                                OwnerBorrowTerminalEdge(
                                    evaluation_kind="attribute",
                                    callable_qualified_name=None,
                                    operand_exact_types=(),
                                    implicit_method_names=("__getattribute__",),
                                    disposition="no_user_dispatch",
                                    traversed_qualified_functions=(),
                                ),
                            )
                        evaluated.append(
                            OwnerBorrowEvaluationNode(
                                ast_node_type=type(occurrence),
                                occurrence_id=AstOccurrenceId(occurrence_path),
                                source_span=span,
                                disposition=(
                                    "lowered"
                                    if terminal_edges
                                    else "syntactic_container"
                                ),
                                terminal_edges=terminal_edges,
                            )
                        )
                    if lexical_key in entrypoint_keys and owner_class is not None:
                        entrypoint: OwnerEntrypointTarget = OwnerMethodTarget(
                            target_kind=OwnerEntrypointTargetKind.METHOD,
                            concrete_owner_type=cast(
                                "type[object]",
                                globals()[owner_class],
                            ),
                            protocol_type=next(
                                row.target.protocol_type
                                for row in owner_entrypoints
                                if isinstance(row.target, OwnerMethodTarget)
                                and row.target.concrete_owner_type.__name__ == owner_class
                                and row.target.method_name == node.name
                            ),
                            method_name=node.name,
                        )
                    else:
                        entrypoint = OwnerFunctionTarget(
                            target_kind=OwnerEntrypointTargetKind.MODULE_FUNCTION,
                            module_qualname=(
                                __name__
                                if owner_class is None
                                else f"{__name__}.{owner_class}"
                            ),
                            function_name=node.name,
                        )
                    rows.append(
                        OwnerBorrowReachability(
                            entrypoint=entrypoint,
                            borrowed_name=borrowed,
                            reachable_qualified_functions=tuple(
                                sorted(
                                    {
                                        edge.callable_qualified_name
                                        for row in evaluated
                                        for edge in row.terminal_edges
                                        if edge.callable_qualified_name is not None
                                    }
                                )
                            ),
                            evaluated_nodes=tuple(evaluated),
                        )
                    )
            self.generic_visit(node)

        visit_AsyncFunctionDef = visit_FunctionDef

    Visitor().visit(tree)
    if not rows:
        raise AssertionError("owner entrypoints contain no lexical payload borrow")
    return tuple(
        sorted(
            rows,
            key=lambda row: (
                row.entrypoint.target_kind.value,
                row.entrypoint.function_name
                if isinstance(row.entrypoint, OwnerFunctionTarget)
                else f"{row.entrypoint.concrete_owner_type.__name__}."
                f"{row.entrypoint.method_name}",
                row.borrowed_name,
            ),
        )
    )


def _unestablished_from_bound_call(
    bound: inspect.BoundArguments,
    predicate_id: AuthorityPredicateId,
) -> BidirectionalUnestablishedAuthorityPredicate | None:
    owner = bound.arguments.get("self")
    source = getattr(owner, "_source_authority", None)
    if type(source) is _CanonicalFoundrySourceAuthorityPayload:
        return _unestablished_from_registry(source, predicate_id)
    for value in bound.arguments.values():
        if type(value) is CanonicalFoundrySourceAuthority:
            try:
                with _unwrap_owner_capability(
                    value,
                    _CANONICAL_SOURCE_SPEC,
                ) as payload:
                    return _unestablished_from_registry(payload, predicate_id)
            except OwnerCapabilityFault:
                return None
    return None


def _owner_fault_result(
    error: OwnerCapabilityFault,
    bound: inspect.BoundArguments,
    entrypoint: OwnerEntrypointSpec,
) -> object:
    matching = tuple(
        policy
        for policy in entrypoint.fault_policies
        if policy.capability_kind is error.capability_kind
    )
    if len(matching) != 1:
        raise error
    policy = matching[0]
    # A malformed or forged capability supplies no independently resolvable
    # rejection evidence.  The owner-bound not-established branch is therefore
    # the exact typed result for both kernel fault dispositions; promoting the
    # kernel's local ``REJECTED`` classification would fabricate P37 evidence.
    result = _unestablished_from_bound_call(bound, policy.predicate_id)
    if result is None:
        raise error
    return result


def install_owner_entrypoint_guards(
    specs: tuple[OwnerEntrypointSpec, ...],
) -> None:
    """Install idempotent fault guards over the independent denominator."""

    for spec in specs:
        target = spec.target
        if isinstance(target, OwnerMethodTarget):
            owner = target.concrete_owner_type
            function = owner.__dict__.get(target.method_name)
            if not callable(function):
                raise AssertionError("owner method disappeared before guard install")
            if getattr(function, "__gy_n12_owner_guard__", None) is spec:
                continue
            if getattr(function, "__gy_n12_owner_guard__", None) is not None:
                raise AssertionError("owner method has a guard from another denominator")
            guarded = _guard_owner_entrypoint(
                function,
                spec=spec,
                failure_factory=_owner_fault_result,
            )
            guarded.__gy_n12_owner_guard__ = spec
            setattr(owner, target.method_name, guarded)
            continue
        function = globals().get(target.function_name)
        if not callable(function):
            raise AssertionError("owner function disappeared before guard install")
        if getattr(function, "__gy_n12_owner_guard__", None) is spec:
            continue
        if getattr(function, "__gy_n12_owner_guard__", None) is not None:
            raise AssertionError("owner function has a guard from another denominator")
        guarded = _guard_owner_entrypoint(
            function,
            spec=spec,
            failure_factory=_owner_fault_result,
        )
        guarded.__gy_n12_owner_guard__ = spec
        globals()[target.function_name] = guarded


def validate_owner_entrypoint_failure_mapping() -> None:
    """Recompute owner pairs, entrypoints and lexical borrow closure."""

    module_file = Path(__file__)
    pairs = derive_owner_protocol_concrete_pairs_from_source(
        module_file=module_file,
        namespace=globals(),
    )
    entrypoints = derive_owner_entrypoint_denominator_from_source(
        module_file=module_file,
        protocol_concrete_pairs=pairs,
    )
    derive_owner_borrow_reachability_from_source(
        module_file=module_file,
        owner_entrypoints=entrypoints,
    )
    token_kinds = {
        policy.capability_kind
        for row in entrypoints
        for policy in row.fault_policies
    }
    if not token_kinds.issubset(set(OwnerCapabilityKind)):
        raise AssertionError("owner fault policy names an unregistered capability")
    for row in entrypoints:
        target = row.target
        function = (
            target.concrete_owner_type.__dict__.get(target.method_name)
            if isinstance(target, OwnerMethodTarget)
            else globals().get(target.function_name)
        )
        if getattr(function, "__gy_n12_owner_guard__", None) != row:
            raise AssertionError("owner entrypoint guard denominator differs from source")


def _module_ast() -> ast.Module:
    return ast.parse(Path(__file__).read_text(encoding="utf-8"), filename=__file__)


def _call_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _qualified_function_calls(
    tree: ast.Module,
) -> tuple[tuple[str, str, int], ...]:
    rows: list[tuple[str, str, int]] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.scope: list[str] = []

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self.scope.append(node.name)
            self.generic_visit(node)
            self.scope.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self.scope.append(node.name)
            self.generic_visit(node)
            self.scope.pop()

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Call(self, node: ast.Call) -> None:
            name = _call_name(node)
            if name is not None:
                rows.append((".".join(self.scope), name, node.lineno))
            self.generic_visit(node)

    Visitor().visit(tree)
    return tuple(rows)


def validate_runtime_cutoff_constructor_bijection() -> None:
    """Require one owner-validated constructor for both cutoff result DTOs."""

    calls = _qualified_function_calls(_module_ast())
    targets = {
        "RuntimeCutoffPreflightRefusal",
        "UnestablishedMethodCatalogDependencyProfile",
    }
    constructors = tuple(row for row in calls if row[1] in targets)
    if len(constructors) != 2 or {row[1] for row in constructors} != targets:
        raise AssertionError("runtime cutoff result constructor denominator changed")
    if any(row[0] != "build_runtime_cutoff_refusal" for row in constructors):
        raise AssertionError("runtime cutoff result has a sibling constructor")
    validation_calls = tuple(
        row
        for row in calls
        if row[0] == "build_runtime_cutoff_refusal"
        and row[1] == "validate_negative_dependency_authority_stage"
    )
    if len(validation_calls) != 1:
        raise AssertionError("cutoff constructor must owner-validate exactly once")


def validate_production_owner_composition_bijection() -> None:
    """Recompute the two-owner negative factory and its cutoff-first ordering."""

    tree = _module_ast()
    calls = _qualified_function_calls(tree)
    factory_calls = tuple(
        name
        for scope, name, _line in calls
        if scope == "build_production_method_catalog_dependency_authority"
    )
    expected_factory_calls = (
        "_ProductionMethodCatalogDependencyAuthority",
        "_build_production_canonical_source_resolver",
        "_NoRuntimeSubtreeCutoffAuthority",
    )
    if factory_calls != expected_factory_calls:
        raise AssertionError("production authority factory graph changed")
    source_factory_calls = tuple(
        name
        for scope, name, _line in calls
        if scope == "_build_production_canonical_source_resolver"
    )
    if source_factory_calls != ("_ProductionCanonicalFoundrySourceAuthorityResolver",):
        raise AssertionError("canonical source factory is not a closed exact constructor")

    resolve_calls = tuple(
        name
        for scope, name, _line in calls
        if scope == "_ProductionMethodCatalogDependencyAuthority.resolve"
    )
    if resolve_calls.count("resolve") != 1 or resolve_calls.count("preflight") != 1:
        raise AssertionError("production resolution must resolve source then preflight once")
    if resolve_calls.count("build_runtime_cutoff_refusal") != 1:
        raise AssertionError("production resolution must delegate to the sole refusal builder")
    ordering = {
        name: resolve_calls.index(name)
        for name in ("resolve", "preflight", "build_runtime_cutoff_refusal")
    }
    if not (
        ordering["resolve"]
        < ordering["preflight"]
        < ordering["build_runtime_cutoff_refusal"]
    ):
        raise AssertionError("production negative graph is not cutoff-first")
    forbidden = {
        "_open_production_dependency_authority_repository",
        "_open_owner_python_runtime_installation_authority",
        "_open_owner_python_runtime_observer",
        "_resolve_owner_components_for_request",
        "resolve_dependency_profile",
        "reconcile_bound_installed_environment",
    }
    if forbidden.intersection(resolve_calls):
        raise AssertionError("production negative graph reaches candidate machinery")
    validate_runtime_cutoff_constructor_bijection()
    validate_negative_only_dependency_authority_abi()


# This named edge remains unreachable before the cutoff.  No local substitute
# is allowed for the absent owner-resolved receipt store.
def _open_production_dependency_authority_repository(
    *,
    environment_root: Path,
    source_authority: _CanonicalFoundrySourceAuthorityPayload,
    trust_resolver: FoundryTrustResolver,
) -> ArtifactStoreFoundryDependencyAuthorityRepository:
    del environment_root, source_authority, trust_resolver
    raise RuntimeError("dependency authority repository is absent/unallocated")


SOURCE_BOOTSTRAP_FAILURE_STAGES = MappingProxyType(
    {
        NegativeDependencyAuthorityResultKind.SOURCE_REJECTED: (
            SourceBootstrapFailureStageSpec(
                result_kind=NegativeDependencyAuthorityResultKind.SOURCE_REJECTED,
                status=OwnerCapabilityFaultDisposition.REJECTED,
                predicate_id=AuthorityPredicateId.SOURCE_FREEZE,
                failure_code=AuthorityFailureCode.SOURCE_FREEZE_MISMATCH,
                request_shape="resolved_source",
                source_ref_rule="forbidden",
                persistence="not_established",
                persistence_capability="owner_resolved_resolution_receipt_store",
                persistence_capability_state="absent/unallocated",
            )
        ),
        NegativeDependencyAuthorityResultKind.SOURCE_NOT_ESTABLISHED: (
            SourceBootstrapFailureStageSpec(
                result_kind=NegativeDependencyAuthorityResultKind.SOURCE_NOT_ESTABLISHED,
                status=OwnerCapabilityFaultDisposition.NOT_ESTABLISHED,
                predicate_id=AuthorityPredicateId.SOURCE_FREEZE,
                failure_code=AuthorityFailureCode.SOURCE_NOT_ESTABLISHED,
                request_shape="pre_source",
                source_ref_rule="forbidden",
                persistence="not_established",
                persistence_capability="owner_resolved_resolution_receipt_store",
                persistence_capability_state="absent/unallocated",
            )
        ),
    }
)
POST_SOURCE_NEGATIVE_AUTHORITY_STAGES = MappingProxyType(
    {
        NegativeDependencyAuthorityResultKind.RUNTIME_CUTOFF_NOT_ESTABLISHED: (
            PostSourceNegativeAuthorityStageSpec(
                result_kind=(
                    NegativeDependencyAuthorityResultKind.RUNTIME_CUTOFF_NOT_ESTABLISHED
                ),
                status=OwnerCapabilityFaultDisposition.NOT_ESTABLISHED,
                predicate_id=AuthorityPredicateId.RUNTIME_SUBTREE_CUTOFF,
                required_branch_shape="not_established_only",
                source_ref_rule="required",
                persistence="not_established",
                persistence_capability="owner_resolved_resolution_receipt_store",
                persistence_capability_state="absent/unallocated",
            )
        )
    }
)

_OWNER_PROTOCOL_CONCRETE_PAIRS = derive_owner_protocol_concrete_pairs_from_source(
    module_file=Path(__file__),
    namespace=globals(),
)
_OWNER_ENTRYPOINT_SPECS = derive_owner_entrypoint_denominator_from_source(
    module_file=Path(__file__),
    protocol_concrete_pairs=_OWNER_PROTOCOL_CONCRETE_PAIRS,
)
_OWNER_BORROW_REACHABILITY = derive_owner_borrow_reachability_from_source(
    module_file=Path(__file__),
    owner_entrypoints=_OWNER_ENTRYPOINT_SPECS,
)
validate_no_owner_capability_in_persisted_schemas()
validate_authority_scalar_role_coverage()
validate_decisive_domain_coverage()
validate_authority_predicate_coverage()
validate_runtime_cutoff_constructor_bijection()
validate_production_owner_composition_bijection()
install_owner_entrypoint_guards(_OWNER_ENTRYPOINT_SPECS)


__all__ = [
    "AbsoluteRequestPath",
    "AuthorityFailureCode",
    "AuthorityPredicateId",
    "CandidateRuntimeEvidenceNotRequested",
    "CandidateRuntimeEvidencePresent",
    "DependencyProfileResolutionFailure",
    "MethodCatalogDependencyAuthority",
    "MethodCatalogDependencyAuthorityRequest",
    "MethodCatalogDependencyAuthorityResult",
    "NegativeDependencyAuthorityResultKind",
    "RuntimeCutoffPreflightRefusal",
    "SourceRejectedMethodCatalogDependencyProfile",
    "SourceUnestablishedMethodCatalogDependencyProfile",
    "UnestablishedMethodCatalogDependencyProfile",
    "build_production_method_catalog_dependency_authority",
    "build_runtime_cutoff_refusal",
    "validate_negative_only_dependency_authority_abi",
]
